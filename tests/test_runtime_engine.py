"""Runtime Engine tests (Mission Brief 024) — states, config, the loop,
retry/escalation, health, and graceful shutdown.

The autonomous end-to-end proof lives in
tests/test_runtime_autonomous.py; this file covers the mechanics.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from master_agent.mission_control.capabilities import CapabilityDescriptor, qualified_name
from master_agent.mission_control.events import EventType
from master_agent.mission_control.executives import ExecutiveHealth
from master_agent.mission_control.mission_control import MissionControl
from master_agent.mission_control.tasks import Objective, Task, TaskState
from master_agent.runtime.config import InvalidRuntimeConfig, RuntimeConfig
from master_agent.runtime.engine import RuntimeEngine
from master_agent.runtime.gateway import GatewayResult, PluginGateway
from master_agent.runtime.states import (
    IllegalRuntimeTransition,
    RuntimeState,
    allowed_transitions,
    assert_transition,
    can_transition,
)
from master_agent.verification.evidence import Evidence, ExpectedOutcome, ObservationCheck, Verdict
from tests.runtime_test_support import RaisingGateway, RecordingGateway

NO_SLEEP = lambda _seconds: None


def make_control(capabilities: list[str] | None = None) -> MissionControl:
    mc = MissionControl()
    caps = capabilities or ["do_thing", "do_other"]
    mc.register_executive(
        executive_id="demo",
        version="1.0.0",
        capabilities=[
            CapabilityDescriptor(
                qualified_name=qualified_name("demo", cap),
                executive_id="demo",
                capability=cap,
            )
            for cap in caps
        ],
        health=ExecutiveHealth.HEALTHY,
    )
    mc.mark_executive_ready("demo")
    return mc


def make_engine(mc: MissionControl, gateway, **config_kwargs) -> RuntimeEngine:
    config_kwargs.setdefault("poll_interval_seconds", 0)
    config = RuntimeConfig(**config_kwargs)
    engine = RuntimeEngine(mc, config, sleep=NO_SLEEP)
    engine.register_gateway("demo", gateway)
    return engine


def one_task_objective(capability: str = "Demo.DoThing", **task_kwargs) -> Objective:
    return Objective(
        description="demo objective",
        tasks=[Task(capability=capability, task_id="t1", **task_kwargs)],
    )


# ---- states -------------------------------------------------------------


def test_all_eight_brief_named_states_exist():
    assert {member.value for member in RuntimeState} == {
        "initializing",
        "idle",
        "dispatching",
        "waiting",
        "verifying",
        "recovering",
        "stopping",
        "stopped",
    }


def test_idle_is_reachable_from_dispatching_for_the_empty_poll_case():
    assert can_transition(RuntimeState.DISPATCHING, RuntimeState.IDLE)


def test_recovering_can_resume_waiting_which_is_what_a_retry_does():
    """Regression guard: the first draft of the table omitted this edge,
    which made every retry crash its own cycle."""
    assert can_transition(RuntimeState.RECOVERING, RuntimeState.WAITING)


def test_stopped_is_terminal():
    assert allowed_transitions(RuntimeState.STOPPED) == set()


def test_illegal_transition_raises():
    with pytest.raises(IllegalRuntimeTransition):
        assert_transition(RuntimeState.IDLE, RuntimeState.VERIFYING)


def test_every_state_has_a_transition_table_entry():
    for state in RuntimeState:
        allowed_transitions(state)


# ---- configuration ------------------------------------------------------


def test_config_defaults_are_sane():
    config = RuntimeConfig()
    assert config.poll_interval_seconds == 1.0
    assert config.max_concurrent_tasks == 1
    assert config.max_attempts == 3
    assert config.verify_when_expected_outcome_present is True


@pytest.mark.parametrize(
    "kwargs",
    [
        {"poll_interval_seconds": -1},
        {"max_concurrent_tasks": 0},
        {"max_attempts": 0},
        {"retry_delay_seconds": -1},
        {"shutdown_timeout_seconds": -1},
        {"max_cycles": 0},
    ],
)
def test_nonsensical_config_fails_at_construction_not_hours_later(kwargs):
    with pytest.raises(InvalidRuntimeConfig):
        RuntimeConfig(**kwargs)


# ---- the loop -----------------------------------------------------------


def test_a_cycle_with_no_work_goes_idle_rather_than_erroring():
    mc = make_control()
    engine = make_engine(mc, RecordingGateway())
    handled = engine.run_once()

    assert handled == []
    assert engine.state is RuntimeState.IDLE
    assert mc.audit.of_type(EventType.RUNTIME_IDLE)


def test_a_ready_task_is_dispatched_executed_and_reported_without_a_human():
    mc = make_control()
    gateway = RecordingGateway()
    engine = make_engine(mc, gateway)
    mc.submit_objective(one_task_objective())

    handled = engine.run_once()

    assert [t.task_id for t in handled] == ["t1"]
    assert gateway.calls == [("do_thing", {})], "gateway must receive the LOCAL capability name"
    assert mc.dispatcher.objectives()[0].task("t1").state is TaskState.COMPLETED


def test_the_gateway_receives_the_local_capability_not_the_qualified_one():
    """Mission Control speaks 'Demo.DoThing'; the Executive speaks
    'do_thing'. The translation is resolved through Mission Control."""
    mc = make_control()
    gateway = RecordingGateway()
    engine = make_engine(mc, gateway)
    mc.submit_objective(one_task_objective())
    engine.run_once()

    assert gateway.calls[0][0] == "do_thing"


def test_dependency_order_is_honoured_across_cycles_automatically():
    mc = make_control()
    gateway = RecordingGateway()
    engine = make_engine(mc, gateway)
    mc.submit_objective(
        Objective(
            description="chain",
            tasks=[
                Task(capability="Demo.DoThing", task_id="t1"),
                Task(capability="Demo.DoOther", task_id="t2", depends_on=["t1"]),
            ],
        )
    )

    engine.run_once()
    engine.run_once()

    assert [call[0] for call in gateway.calls] == ["do_thing", "do_other"]
    assert mc.founder_state().progress == 1.0


def test_max_concurrent_tasks_bounds_work_taken_on_in_one_cycle():
    mc = MissionControl()
    for name in ("a", "b"):
        mc.register_executive(
            executive_id=name,
            version="1",
            capabilities=[
                CapabilityDescriptor(
                    qualified_name=qualified_name(name, "go"),
                    executive_id=name,
                    capability="go",
                )
            ],
            health=ExecutiveHealth.HEALTHY,
        )
        mc.mark_executive_ready(name)

    gateway = RecordingGateway()
    engine = RuntimeEngine(
        mc, RuntimeConfig(poll_interval_seconds=0, max_concurrent_tasks=1), sleep=NO_SLEEP
    )
    engine.register_gateway("a", gateway)
    engine.register_gateway("b", gateway)
    mc.submit_objective(
        Objective(
            description="two independent",
            tasks=[
                Task(capability="A.Go", task_id="t1"),
                Task(capability="B.Go", task_id="t2"),
            ],
        )
    )

    handled = engine.run_once()
    assert len(handled) == 1


def test_a_task_assigned_to_an_executive_with_no_gateway_fails_loudly():
    mc = make_control()
    engine = RuntimeEngine(mc, RuntimeConfig(poll_interval_seconds=0), sleep=NO_SLEEP)
    # deliberately no gateway registered
    mc.submit_objective(one_task_objective())

    engine.run_once()

    assert mc.dispatcher.objectives()[0].task("t1").state is TaskState.FAILED
    assert mc.audit.of_type(EventType.RUNTIME_ERROR)


# ---- retry and escalation ----------------------------------------------


def test_a_failing_task_is_retried_up_to_the_policy_limit():
    mc = make_control()
    gateway = RecordingGateway(
        results=[
            GatewayResult(success=False, errors=["boom"]),
            GatewayResult(success=False, errors=["boom"]),
            GatewayResult(success=True, output="recovered"),
        ]
    )
    engine = make_engine(mc, gateway, max_attempts=3, retry_delay_seconds=0)
    mc.submit_objective(one_task_objective())

    engine.run_once()

    assert len(gateway.calls) == 3
    assert mc.dispatcher.objectives()[0].task("t1").state is TaskState.COMPLETED
    assert engine.health().retries_performed == 2


def test_exhausted_retries_escalate_exactly_once():
    mc = make_control()
    gateway = RecordingGateway(
        results=[GatewayResult(success=False, errors=["always"]) for _ in range(5)]
    )
    engine = make_engine(mc, gateway, max_attempts=3, retry_delay_seconds=0)
    mc.submit_objective(one_task_objective())

    engine.run_once()

    assert len(gateway.calls) == 3
    assert mc.audit.of_type(EventType.TASK_ESCALATED)
    assert engine.health().escalations == 1
    assert mc.dispatcher.objectives()[0].task("t1").state is TaskState.FAILED


def test_mission_control_never_sees_a_retry_only_the_final_outcome():
    """MB023's dispatcher guarantee -- 'never auto-retries' -- must stay
    literally true: retries happen inside one Runtime cycle, and Mission
    Control is told exactly once."""
    mc = make_control()
    gateway = RecordingGateway(
        results=[GatewayResult(success=False, errors=["always"]) for _ in range(5)]
    )
    engine = make_engine(mc, gateway, max_attempts=3, retry_delay_seconds=0)
    mc.submit_objective(one_task_objective())

    engine.run_once()

    assert len(mc.audit.of_type(EventType.TASK_FAILED)) == 1
    assert len(mc.audit.of_type(EventType.TASK_STARTED)) == 1


def test_retry_never_alters_the_payload_or_the_capability():
    """Mechanical retry, not strategic recovery (Constitution §11)."""
    mc = make_control()
    gateway = RecordingGateway(
        results=[GatewayResult(success=False, errors=["x"]) for _ in range(3)]
    )
    engine = make_engine(mc, gateway, max_attempts=3, retry_delay_seconds=0)
    mc.submit_objective(one_task_objective(payload={"a": 1}))

    engine.run_once()

    assert gateway.calls == [("do_thing", {"a": 1})] * 3


def test_a_gateway_that_raises_is_a_failed_attempt_not_a_dead_runtime():
    mc = make_control()
    gateway = RaisingGateway()
    engine = make_engine(mc, gateway, max_attempts=2, retry_delay_seconds=0)
    mc.submit_objective(one_task_objective())

    engine.run_once()

    assert gateway.attempts == 2
    assert engine.state is RuntimeState.IDLE
    assert mc.dispatcher.objectives()[0].task("t1").state is TaskState.FAILED


# ---- verification -------------------------------------------------------


def make_evidence(verdict: Verdict) -> Evidence:
    return Evidence(
        evidence_id="ev-1",
        worker="demo",
        environment="demo_env",
        captured_at=datetime.now(UTC),
        expected=ExpectedOutcome(description="d", checks=[]),
        observation={},
        verdict=verdict,
    )


def test_verification_is_invoked_automatically_when_an_outcome_is_expected():
    mc = make_control()
    gateway = RecordingGateway(evidence=make_evidence(Verdict.MATCHED))
    engine = make_engine(mc, gateway)
    mc.submit_objective(
        one_task_objective(
            expected_outcome=ExpectedOutcome(
                description="it worked",
                checks=[ObservationCheck(field="x", operator="exists")],
            )
        )
    )

    engine.run_once()

    assert gateway.verify_calls == ["do_thing"]
    assert mc.audit.of_type(EventType.VERIFICATION_STARTED)
    assert mc.audit.of_type(EventType.VERIFICATION_COMPLETED)


def test_no_expected_outcome_means_no_verification_attempt():
    mc = make_control()
    gateway = RecordingGateway()
    engine = make_engine(mc, gateway)
    mc.submit_objective(one_task_objective())

    engine.run_once()

    assert gateway.verify_calls == []


def test_execution_success_with_a_not_matched_verdict_is_reported_as_failure():
    """ADR-0011's whole point: those are different claims, and the
    Runtime must not let one imply the other."""
    mc = make_control()
    gateway = RecordingGateway(evidence=make_evidence(Verdict.NOT_MATCHED))
    engine = make_engine(mc, gateway)
    mc.submit_objective(
        one_task_objective(
            expected_outcome=ExpectedOutcome(description="d", checks=[])
        )
    )

    engine.run_once()

    task = mc.dispatcher.objectives()[0].task("t1")
    assert task.state is TaskState.FAILED
    assert "not_matched" in task.errors[0]


def test_an_executive_with_no_verifier_records_that_honestly():
    mc = make_control()
    gateway = RecordingGateway(evidence=None)
    engine = make_engine(mc, gateway)
    mc.submit_objective(
        one_task_objective(expected_outcome=ExpectedOutcome(description="d", checks=[]))
    )

    engine.run_once()

    completed = mc.audit.of_type(EventType.VERIFICATION_COMPLETED)
    assert completed[0].payload["verifier"] == "none"
    assert completed[0].payload["verdict"] is None


def test_verification_can_be_disabled_by_policy():
    mc = make_control()
    gateway = RecordingGateway(evidence=make_evidence(Verdict.MATCHED))
    engine = make_engine(mc, gateway, verify_when_expected_outcome_present=False)
    mc.submit_objective(
        one_task_objective(expected_outcome=ExpectedOutcome(description="d", checks=[]))
    )

    engine.run_once()

    assert gateway.verify_calls == []


# ---- health -------------------------------------------------------------


def test_health_exposes_all_seven_brief_named_fields():
    mc = make_control()
    engine = make_engine(mc, RecordingGateway())
    data = engine.health().as_dict()
    for required in (
        "uptime_seconds",
        "active_cycle",
        "queue_length",
        "executives_online",
        "executives_busy",
        "last_dispatch_at",
        "last_verification_at",
    ):
        assert required in data


def test_health_is_read_from_mission_control_not_a_shadow_copy():
    mc = make_control()
    engine = make_engine(mc, RecordingGateway())
    mc.submit_objective(
        Objective(
            description="two",
            tasks=[
                Task(capability="Demo.DoThing", task_id="t1"),
                Task(capability="Demo.DoOther", task_id="t2"),
            ],
        )
    )
    assert engine.health().queue_length == 2
    assert engine.health().executives_online == 1


def test_uptime_advances_with_the_injected_clock():
    mc = make_control()
    base = datetime.now(UTC)
    ticks = iter([base, base + timedelta(seconds=5)])
    engine = RuntimeEngine(
        mc, RuntimeConfig(poll_interval_seconds=0), clock=lambda: next(ticks), sleep=NO_SLEEP
    )
    engine.register_gateway("demo", RecordingGateway())
    engine._begin()
    assert engine.health().uptime_seconds == pytest.approx(5.0)


# ---- observability ------------------------------------------------------


def test_every_cycle_publishes_runtime_events():
    mc = make_control()
    engine = make_engine(mc, RecordingGateway())
    mc.submit_objective(one_task_objective())
    engine.run_once()

    emitted = {entry.event_type for entry in mc.audit.entries}
    for expected in (
        EventType.RUNTIME_STARTED,
        EventType.DISPATCH_STARTED,
        EventType.TASK_ASSIGNED,
        EventType.TASK_STARTED,
        EventType.TASK_COMPLETED,
        EventType.RUNTIME_IDLE,
        EventType.RUNTIME_STATE_CHANGED,
    ):
        assert expected in emitted, f"missing runtime event: {expected}"


def test_runtime_events_are_attributed_to_the_runtime_not_mission_control():
    mc = make_control()
    engine = make_engine(mc, RecordingGateway())
    engine.run_once()
    started = mc.audit.of_type(EventType.RUNTIME_STARTED)[0]
    assert started.source == "runtime_engine"


# ---- shutdown -----------------------------------------------------------


def test_stop_transitions_cleanly_and_publishes_a_final_snapshot():
    mc = make_control()
    engine = make_engine(mc, RecordingGateway())
    engine.run_once()
    engine.stop()

    assert engine.state is RuntimeState.STOPPED
    stopped = mc.audit.of_type(EventType.RUNTIME_STOPPED)
    assert stopped
    assert stopped[0].payload["state"] == "stopped"
    assert "uptime_seconds" in stopped[0].payload


def test_max_cycles_bounds_a_run_and_shuts_down():
    mc = make_control()
    engine = make_engine(mc, RecordingGateway(), max_cycles=3)
    engine.run_forever()

    assert engine.health().active_cycle == 3
    assert engine.state is RuntimeState.STOPPED


def test_a_background_run_starts_and_stops_gracefully():
    mc = make_control()
    gateway = RecordingGateway()
    engine = RuntimeEngine(
        mc, RuntimeConfig(poll_interval_seconds=0.01, shutdown_timeout_seconds=5), sleep=NO_SLEEP
    )
    engine.register_gateway("demo", gateway)
    mc.submit_objective(one_task_objective())

    engine.start_background()
    deadline = datetime.now(UTC) + timedelta(seconds=5)
    while datetime.now(UTC) < deadline:
        if mc.dispatcher.objectives()[0].task("t1").state is TaskState.COMPLETED:
            break
    engine.stop()

    assert engine.state is RuntimeState.STOPPED
    assert mc.dispatcher.objectives()[0].task("t1").state is TaskState.COMPLETED


def test_starting_twice_is_refused():
    mc = make_control()
    engine = make_engine(mc, RecordingGateway(), poll_interval_seconds=0.01, max_cycles=1)
    engine.start_background()
    try:
        with pytest.raises(RuntimeError):
            engine.start_background()
    finally:
        engine.stop()


# ---- gateway ------------------------------------------------------------


def test_plugin_gateway_is_generic_across_unrelated_executives(tmp_path):
    """One gateway class serves any Plugin -- there is no per-Executive
    gateway to write."""
    from master_agent.executor.executor import LocalExecutor
    from master_agent.permissions.permission_system import PermissionSystem
    from master_agent.plugins.filesystem_plugin import FilesystemPlugin

    executor = LocalExecutor(PermissionSystem())
    plugin = FilesystemPlugin(executor, locations={"desktop": tmp_path})
    gateway = PluginGateway(plugin)

    result = gateway.invoke("create_folder", {"name": "Gatewayed"})
    assert result.success
    assert (tmp_path / "Gatewayed").exists()


def test_plugin_gateway_reports_failure_without_raising(tmp_path):
    from master_agent.executor.executor import LocalExecutor
    from master_agent.permissions.permission_system import PermissionSystem
    from master_agent.plugins.filesystem_plugin import FilesystemPlugin

    executor = LocalExecutor(PermissionSystem())
    plugin = FilesystemPlugin(executor, locations={"desktop": tmp_path})
    result = PluginGateway(plugin).invoke("not_a_capability", {})

    assert not result.success
    assert result.errors


def test_plugin_gateway_produces_no_evidence_and_says_so(tmp_path):
    from master_agent.executor.executor import LocalExecutor
    from master_agent.permissions.permission_system import PermissionSystem
    from master_agent.plugins.filesystem_plugin import FilesystemPlugin

    executor = LocalExecutor(PermissionSystem())
    plugin = FilesystemPlugin(executor, locations={"desktop": tmp_path})
    evidence = PluginGateway(plugin).verify(
        "create_folder", {}, ExpectedOutcome(description="d", checks=[])
    )
    assert evidence is None
