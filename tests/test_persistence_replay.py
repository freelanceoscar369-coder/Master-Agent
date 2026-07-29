"""Event replay (MB025 deliverable #9) — Mission Control rebuilt from the
event log alone, with no snapshot involved.
"""
from __future__ import annotations

from master_agent.mission_control.capabilities import CapabilityDescriptor, qualified_name
from master_agent.mission_control.events import EventType
from master_agent.mission_control.executives import ExecutiveHealth
from master_agent.mission_control.mission_control import MissionControl
from master_agent.mission_control.tasks import Objective, Task, TaskState
from master_agent.persistence.replay import replay_events_into
from master_agent.persistence.service import PersistenceService
from master_agent.persistence.store import InMemoryStateStore


def recorded_system():
    """A Mission Control whose *entire* life is captured from the first
    event, so replay has everything it needs."""
    mc = MissionControl()
    store = InMemoryStateStore()
    service = PersistenceService(store, mc)
    service.start_recording()

    mc.register_executive(
        executive_id="demo",
        version="2.0.0",
        capabilities=[
            CapabilityDescriptor(
                qualified_name=qualified_name("demo", cap),
                executive_id="demo",
                capability=cap,
            )
            for cap in ("do_thing", "do_other")
        ],
        health=ExecutiveHealth.HEALTHY,
    )
    mc.mark_executive_ready("demo")
    return mc, store, service


def demo_objective() -> Objective:
    return Objective(
        description="replayable",
        tasks=[
            Task(capability="Demo.DoThing", task_id="t1"),
            Task(capability="Demo.DoOther", task_id="t2", depends_on=["t1"]),
        ],
    )


def test_replay_rebuilds_executives_from_events_alone():
    _mc, store, _ = recorded_system()
    fresh = MissionControl()

    counts = replay_events_into(fresh, store.read_events())

    assert counts["executives"] == 1
    assert fresh.executives.has("demo")
    assert fresh.executives.get("demo").version == "2.0.0"


def test_replay_rebuilds_capabilities_and_links_them_to_their_executive():
    _mc, store, _ = recorded_system()
    fresh = MissionControl()

    counts = replay_events_into(fresh, store.read_events())

    assert counts["capabilities"] == 2
    assert fresh.capabilities.has("Demo.DoThing")
    assert fresh.capabilities.get("Demo.DoThing").executive_id == "demo"
    assert "Demo.DoThing" in fresh.executives.get("demo").capabilities


def test_replay_restores_executive_lifecycle_state():
    _mc, store, _ = recorded_system()
    fresh = MissionControl()
    replay_events_into(fresh, store.read_events())

    from master_agent.mission_control.lifecycle import WorkerState

    assert fresh.executives.get("demo").state is WorkerState.READY


def test_replay_restores_executive_health_changes():
    mc, store, _ = recorded_system()
    mc.set_executive_health("demo", ExecutiveHealth.DEGRADED)

    fresh = MissionControl()
    replay_events_into(fresh, store.read_events())
    assert fresh.executives.get("demo").health is ExecutiveHealth.DEGRADED


def test_replay_rebuilds_objectives_and_their_tasks():
    mc, store, _ = recorded_system()
    mc.submit_objective(demo_objective())

    fresh = MissionControl()
    counts = replay_events_into(fresh, store.read_events())

    assert counts["objectives"] == 1
    assert counts["tasks"] == 2
    restored = fresh.dispatcher.objectives()[0]
    assert restored.description == "replayable"
    assert [t.task_id for t in restored.tasks] == ["t1", "t2"]


def test_replay_reconstructs_completed_task_state_and_evidence():
    mc, store, _ = recorded_system()
    mc.submit_objective(demo_objective())
    mc.dispatch_ready()
    mc.task_started("t1")
    mc.task_completed("t1", evidence_id="ev-9")

    fresh = MissionControl()
    replay_events_into(fresh, store.read_events())

    task = fresh.dispatcher.objectives()[0].task("t1")
    assert task.state is TaskState.COMPLETED
    assert task.evidence_id == "ev-9"
    assert task.assigned_executive == "demo"


def test_replay_reconstructs_failed_tasks_with_their_error():
    mc, store, _ = recorded_system()
    mc.submit_objective(demo_objective())
    mc.dispatch_ready()
    mc.task_started("t1")
    mc.task_failed("t1", "it broke")

    fresh = MissionControl()
    replay_events_into(fresh, store.read_events())

    task = fresh.dispatcher.objectives()[0].task("t1")
    assert task.state is TaskState.FAILED
    assert any("it broke" in error for error in task.errors)


def test_replay_reconstructs_blocked_dependents():
    mc, store, _ = recorded_system()
    mc.submit_objective(demo_objective())
    mc.dispatch_ready()
    mc.task_started("t1")
    mc.task_failed("t1", "boom")

    fresh = MissionControl()
    replay_events_into(fresh, store.read_events())

    assert fresh.dispatcher.objectives()[0].task("t2").state is TaskState.BLOCKED


def test_replay_quarantines_tasks_that_were_still_running():
    mc, store, _ = recorded_system()
    mc.submit_objective(demo_objective())
    mc.dispatch_ready()
    mc.task_started("t1")  # never completed -- the process "died" here

    fresh = MissionControl()
    replay_events_into(fresh, store.read_events())

    task = fresh.dispatcher.objectives()[0].task("t1")
    assert task.state is TaskState.FAILED
    assert any("duplicate execution" in error for error in task.errors)


def test_replay_quarantines_tasks_that_were_merely_assigned():
    mc, store, _ = recorded_system()
    mc.submit_objective(demo_objective())
    mc.dispatch_ready()  # DISPATCHED but never started

    fresh = MissionControl()
    replay_events_into(fresh, store.read_events())
    assert fresh.dispatcher.objectives()[0].task("t1").state is TaskState.FAILED


def test_replay_quarantine_can_be_disabled():
    mc, store, _ = recorded_system()
    mc.submit_objective(demo_objective())
    mc.dispatch_ready()
    mc.task_started("t1")

    fresh = MissionControl()
    replay_events_into(fresh, store.read_events(), quarantine_interrupted=False)
    assert fresh.dispatcher.objectives()[0].task("t1").state is TaskState.RUNNING


def test_replay_publishes_nothing_so_history_is_not_doubled():
    mc, store, _ = recorded_system()
    mc.submit_objective(demo_objective())

    fresh = MissionControl()
    replay_events_into(fresh, store.read_events())

    assert fresh.audit.of_type(EventType.OBJECTIVE_SUBMITTED) == []
    assert fresh.audit.of_type(EventType.TASK_CREATED) == []


def test_replay_sets_the_current_objective_so_founder_state_works():
    mc, store, _ = recorded_system()
    objective = mc.submit_objective(demo_objective())

    fresh = MissionControl()
    replay_events_into(fresh, store.read_events())

    assert fresh.founder_state().current_objective_id == objective.objective_id


def test_replaying_an_empty_log_is_harmless():
    fresh = MissionControl()
    counts = replay_events_into(fresh, [])
    assert counts == {"executives": 0, "capabilities": 0, "objectives": 0, "tasks": 0}


def test_replay_skips_unparseable_entries_rather_than_failing():
    """A log written by a newer build, or with one bad line, should replay
    as far as it can."""
    mc, store, _ = recorded_system()
    mc.submit_objective(demo_objective())

    events = store.read_events()
    events.insert(1, {"not": "an event"})
    events.insert(3, {"event_id": "x", "event_type": "totally_unknown", "source": "y"})

    fresh = MissionControl()
    counts = replay_events_into(fresh, events)
    assert counts["objectives"] == 1


def test_replay_ignores_events_that_are_history_not_state():
    """Runtime heartbeats are worth auditing but carry no state."""
    mc, store, _ = recorded_system()
    mc.reporter_for("runtime_engine").report(EventType.RUNTIME_IDLE, payload={"cycle": 3})

    fresh = MissionControl()
    counts = replay_events_into(fresh, store.read_events())
    assert counts["objectives"] == 0


def test_a_replayed_objective_is_still_dispatchable():
    """Replay must produce a working system, not a read-only picture."""
    mc, store, _ = recorded_system()
    mc.submit_objective(demo_objective())

    fresh = MissionControl()
    replay_events_into(fresh, store.read_events())
    fresh.executives.set_current_task("demo", None)

    assert [t.task_id for t in fresh.dispatch_ready()] == ["t1"]
