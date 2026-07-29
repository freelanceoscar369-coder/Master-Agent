"""Restart recovery (MB025 deliverable #8) — detect, restore, resume, with
no duplicate execution and no manual founder intervention.
"""
from __future__ import annotations

from master_agent.mission_control.capabilities import CapabilityDescriptor, qualified_name
from master_agent.mission_control.executives import ExecutiveHealth
from master_agent.mission_control.mission_control import MissionControl
from master_agent.mission_control.tasks import Objective, Task, TaskState
from master_agent.persistence.recovery import RecoveryReport, recover
from master_agent.persistence.schema import SnapshotEnvelope
from master_agent.persistence.service import PersistenceService
from master_agent.persistence.store import InMemoryStateStore, JsonFileStateStore
from master_agent.runtime.checkpoint import RuntimeCheckpoint
from master_agent.runtime.config import RuntimeConfig
from master_agent.runtime.engine import RuntimeEngine
from master_agent.runtime.states import RuntimeState


def build(store):
    mc = MissionControl()
    service = PersistenceService(store, mc)
    service.start_recording()
    mc.register_executive(
        executive_id="demo",
        version="1.0.0",
        capabilities=[
            CapabilityDescriptor(
                qualified_name=qualified_name("demo", "do_thing"),
                executive_id="demo",
                capability="do_thing",
            )
        ],
        health=ExecutiveHealth.HEALTHY,
    )
    mc.mark_executive_ready("demo")
    return mc, service


def demo_objective() -> Objective:
    return Objective(
        description="recoverable",
        tasks=[
            Task(capability="Demo.DoThing", task_id="t1"),
            Task(capability="Demo.DoThing", task_id="t2", depends_on=["t1"]),
        ],
    )


# ---- detection ----------------------------------------------------------


def test_recovering_with_no_prior_state_reports_nothing_recovered():
    fresh = MissionControl()
    report = recover(PersistenceService(InMemoryStateStore(), fresh), fresh)

    assert report.recovered is False
    assert report.source == "none"
    assert report.objectives == 0


def test_recovery_report_is_serialisable_for_a_launcher_to_surface():
    report = RecoveryReport(recovered=True, source="snapshot", objectives=2)
    data = report.as_dict()
    assert data["recovered"] is True
    assert data["source"] == "snapshot"
    import json

    json.dumps(data)


# ---- snapshot recovery --------------------------------------------------


def test_recovery_restores_from_a_snapshot():
    store = InMemoryStateStore()
    mc, service = build(store)
    mc.submit_objective(demo_objective())
    service.save()

    fresh = MissionControl()
    report = recover(PersistenceService(store, fresh), fresh)

    assert report.recovered is True
    assert report.source == "snapshot"
    assert report.executives == 1
    assert report.capabilities == 1
    assert report.objectives == 1
    assert report.audit_entries > 0


def test_recovery_restores_the_runtime_checkpoint_into_an_engine():
    store = InMemoryStateStore()
    mc, service = build(store)
    mc.submit_objective(demo_objective())
    service.save(mc, RuntimeCheckpoint(state=RuntimeState.IDLE, cycle=11, tasks_completed=4))

    fresh = MissionControl()
    engine = RuntimeEngine(fresh, RuntimeConfig(poll_interval_seconds=0))
    report = recover(PersistenceService(store, fresh), fresh, engine)

    assert report.checkpoint is not None
    assert report.checkpoint.cycle == 11
    assert engine.health().active_cycle == 11
    assert engine.health().tasks_completed == 4


def test_recovery_without_a_runtime_still_restores_mission_control():
    store = InMemoryStateStore()
    mc, service = build(store)
    mc.submit_objective(demo_objective())
    service.save()

    fresh = MissionControl()
    report = recover(PersistenceService(store, fresh), fresh, runtime=None)
    assert report.objectives == 1


# ---- corruption fallback ------------------------------------------------


def test_a_corrupt_snapshot_falls_back_to_event_replay_rather_than_starting_empty():
    store = InMemoryStateStore()
    mc, service = build(store)
    mc.submit_objective(demo_objective())
    service.save()

    # Corrupt the snapshot, leaving the event log intact.
    store.save_snapshot(
        SnapshotEnvelope(payload={"objectives": ["tampered"]}, checksum="wrong")
    )

    fresh = MissionControl()
    report = recover(PersistenceService(store, fresh), fresh)

    assert report.source == "event_replay"
    assert report.objectives == 1
    assert report.warnings
    assert "falling back" in report.warnings[0]


def test_an_unsupported_schema_version_also_falls_back_to_replay():
    store = InMemoryStateStore()
    mc, service = build(store)
    mc.submit_objective(demo_objective())
    service.save()

    store.save_snapshot(
        SnapshotEnvelope(payload={"objectives": []}, schema_version=99).sealed()
    )

    fresh = MissionControl()
    report = recover(PersistenceService(store, fresh), fresh)

    assert report.source == "event_replay"
    assert report.warnings


def test_a_corrupt_snapshot_with_no_event_log_recovers_nothing_but_does_not_crash():
    store = InMemoryStateStore()
    store.save_snapshot(SnapshotEnvelope(payload={"a": 1}, checksum="wrong"))

    fresh = MissionControl()
    report = recover(PersistenceService(store, fresh), fresh)

    assert report.recovered is False


# ---- no duplicate execution ---------------------------------------------


def test_an_interrupted_task_is_quarantined_and_counted():
    store = InMemoryStateStore()
    mc, service = build(store)
    mc.submit_objective(demo_objective())
    mc.dispatch_ready()
    mc.task_started("t1")  # in flight when the process dies
    service.save()

    fresh = MissionControl()
    report = recover(PersistenceService(store, fresh), fresh)

    assert report.quarantined_tasks == 1
    assert fresh.dispatcher.objectives()[0].task("t1").state is TaskState.FAILED


def test_a_quarantined_task_is_never_dispatched_again():
    """The brief's "no duplicate task execution", asserted directly."""
    store = InMemoryStateStore()
    mc, service = build(store)
    mc.submit_objective(demo_objective())
    mc.dispatch_ready()
    mc.task_started("t1")
    service.save()

    fresh = MissionControl()
    recover(PersistenceService(store, fresh), fresh)

    assert fresh.dispatch_ready() == []


def test_a_dependent_of_a_quarantined_task_is_blocked_not_silently_dropped():
    store = InMemoryStateStore()
    mc, service = build(store)
    mc.submit_objective(demo_objective())
    mc.dispatch_ready()
    mc.task_started("t1")
    service.save()

    fresh = MissionControl()
    recover(PersistenceService(store, fresh), fresh)

    assert fresh.dispatcher.objectives()[0].task("t2").state is TaskState.BLOCKED


def test_a_quarantined_task_is_visible_in_founder_state():
    store = InMemoryStateStore()
    mc, service = build(store)
    mc.submit_objective(demo_objective())
    mc.dispatch_ready()
    mc.task_started("t1")
    service.save()

    fresh = MissionControl()
    recover(PersistenceService(store, fresh), fresh)

    assert any("duplicate execution" in error for error in fresh.founder_state().errors)


def test_work_that_had_not_started_resumes_normally():
    """The other half: "resume unfinished work"."""
    store = InMemoryStateStore()
    mc, service = build(store)
    mc.submit_objective(demo_objective())
    mc.dispatch_ready()
    mc.task_started("t1")
    mc.task_completed("t1")
    service.save()

    fresh = MissionControl()
    recover(PersistenceService(store, fresh), fresh)

    assert fresh.dispatcher.objectives()[0].task("t1").state is TaskState.COMPLETED
    assert [t.task_id for t in fresh.dispatch_ready()] == ["t2"]


def test_a_restored_executive_is_free_to_take_work_again():
    """It must not come back believing it is still busy with a task that
    was quarantined."""
    store = InMemoryStateStore()
    mc, service = build(store)
    mc.submit_objective(demo_objective())
    mc.dispatch_ready()
    mc.task_started("t1")
    service.save()

    fresh = MissionControl()
    recover(PersistenceService(store, fresh), fresh)

    assert fresh.executives.get("demo").current_task_id is None


# ---- founder state ------------------------------------------------------


def test_founder_state_survives_recovery(tmp_path):
    store = JsonFileStateStore(tmp_path)
    mc, service = build(store)
    objective = mc.submit_objective(demo_objective())
    mc.dispatch_ready()
    mc.task_started("t1")
    mc.task_completed("t1")
    service.save()

    fresh = MissionControl()
    recover(PersistenceService(JsonFileStateStore(tmp_path), fresh), fresh)

    state = fresh.founder_state()
    assert state.current_mission == "recoverable"
    assert state.current_objective_id == objective.objective_id
    assert state.progress == 0.5


def test_audit_history_survives_recovery(tmp_path):
    store = JsonFileStateStore(tmp_path)
    mc, service = build(store)
    mc.submit_objective(demo_objective())
    service.save()
    logged = len(store.read_events())

    fresh = MissionControl()
    report = recover(PersistenceService(JsonFileStateStore(tmp_path), fresh), fresh)

    assert report.audit_entries == logged
    assert len(fresh.audit) == logged
