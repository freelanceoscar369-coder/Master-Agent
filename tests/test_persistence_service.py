"""PersistenceService — event capture, snapshots, checkpoints, restore.

Covers deliverables #1-#7: the service itself, runtime checkpoints,
objective/queue/registry/audit/founder-state persistence.
"""
from __future__ import annotations

import pytest

from master_agent.mission_control.capabilities import CapabilityDescriptor, qualified_name
from master_agent.mission_control.events import EventType
from master_agent.mission_control.executives import ExecutiveHealth
from master_agent.mission_control.mission_control import MissionControl
from master_agent.mission_control.tasks import Objective, Task, TaskState
from master_agent.persistence.schema import CorruptSnapshot, SnapshotEnvelope
from master_agent.persistence.service import PersistenceService
from master_agent.persistence.store import InMemoryStateStore, JsonFileStateStore
from master_agent.runtime.checkpoint import CheckpointSink, RuntimeCheckpoint
from master_agent.runtime.states import RuntimeState


def make_control(executive: str = "demo", caps=("do_thing", "do_other")) -> MissionControl:
    mc = MissionControl()
    mc.register_executive(
        executive_id=executive,
        version="1.0.0",
        capabilities=[
            CapabilityDescriptor(
                qualified_name=qualified_name(executive, cap),
                executive_id=executive,
                capability=cap,
            )
            for cap in caps
        ],
        health=ExecutiveHealth.HEALTHY,
    )
    mc.mark_executive_ready(executive)
    return mc


def make_service(mc: MissionControl | None = None, **kwargs):
    store = InMemoryStateStore()
    service = PersistenceService(store, mc, **kwargs)
    if mc is not None:
        service.start_recording()
    return service, store


def demo_objective() -> Objective:
    return Objective(
        description="demo",
        tasks=[
            Task(capability="Demo.DoThing", task_id="t1"),
            Task(capability="Demo.DoOther", task_id="t2", depends_on=["t1"]),
        ],
    )


# ---- event capture (deliverable #6) --------------------------------------


def test_events_are_captured_as_they_happen():
    mc = make_control()
    _service, store = make_service(mc)
    mc.submit_objective(demo_objective())

    types = {e["event_type"] for e in store.read_events()}
    assert "objective_submitted" in types
    assert "task_created" in types


def test_recording_without_a_mission_control_is_refused():
    service = PersistenceService(InMemoryStateStore())
    with pytest.raises(ValueError):
        service.start_recording()


def test_buffering_defers_writes_until_flush():
    mc = make_control()
    service, store = make_service(mc, flush_every=1000)
    mc.submit_objective(demo_objective())

    assert store.read_events() == []
    service.flush()
    assert store.read_events() != []


def test_flushing_an_empty_buffer_is_a_no_op():
    service, store = make_service()
    service.flush()
    assert store.read_events() == []


def test_the_default_writes_every_event_immediately():
    """An event that is only in memory is an event that does not survive
    a kill -- so no buffering by default."""
    mc = make_control()
    _, store = make_service(mc)
    before = len(store.read_events())
    mc.request_knowledge("something")
    assert len(store.read_events()) > before


def test_recording_captures_event_types_added_later():
    """Subscribing to *all* events is what makes this survive new event
    types being introduced."""
    mc = make_control()
    _, store = make_service(mc)
    mc.reporter_for("demo").report(EventType.RUNTIME_IDLE, payload={"cycle": 1})
    assert any(e["event_type"] == "runtime_idle" for e in store.read_events())


def test_archiving_an_already_running_system_preserves_its_history():
    mc = make_control()
    mc.submit_objective(demo_objective())
    before = len(mc.audit)

    service, store = make_service()
    archived = service.archive_audit(mc)

    assert archived == before
    assert len(store.read_events()) == before


# ---- snapshots (deliverables #2-#5, #7) ---------------------------------


def test_a_snapshot_captures_every_required_section():
    mc = make_control()
    service, _ = make_service(mc)
    mc.submit_objective(demo_objective())

    payload = service.build_snapshot().payload
    for section in ("executives", "capabilities", "objectives", "founder_state", "runtime"):
        assert section in payload


def test_a_snapshot_is_sealed_and_verifiable():
    mc = make_control()
    service, _ = make_service(mc)
    service.build_snapshot().verify()


def test_a_snapshot_records_registries_and_objectives():
    mc = make_control()
    service, _ = make_service(mc)
    mc.submit_objective(demo_objective())

    payload = service.build_snapshot().payload
    assert len(payload["executives"]) == 1
    assert len(payload["capabilities"]) == 2
    assert len(payload["objectives"]) == 1
    assert len(payload["objectives"][0]["tasks"]) == 2


def test_a_snapshot_includes_founder_state_for_the_future_dashboard():
    mc = make_control()
    service, _ = make_service(mc)
    mc.submit_objective(demo_objective())

    founder = service.build_snapshot().payload["founder_state"]
    for field in ("current_mission", "progress", "evidence", "errors", "eta_seconds"):
        assert field in founder


def test_a_snapshot_includes_the_runtime_checkpoint_when_given_one():
    mc = make_control()
    service, _ = make_service(mc)
    checkpoint = RuntimeCheckpoint(state=RuntimeState.IDLE, cycle=7, tasks_completed=3)

    runtime = service.build_snapshot(checkpoint=checkpoint).payload["runtime"]
    assert runtime["cycle"] == 7
    assert runtime["tasks_completed"] == 3


def test_snapshotting_without_a_mission_control_is_refused():
    service = PersistenceService(InMemoryStateStore())
    with pytest.raises(ValueError):
        service.build_snapshot()


def test_save_flushes_events_before_writing_the_snapshot():
    mc = make_control()
    service, store = make_service(mc, flush_every=1000)
    mc.submit_objective(demo_objective())
    service.save()
    assert store.read_events() != []
    assert store.load_snapshot() is not None


def test_load_returns_none_when_nothing_was_saved():
    service, _ = make_service()
    assert service.load() is None


def test_load_refuses_a_tampered_snapshot():
    mc = make_control()
    service, store = make_service(mc)
    service.save()
    tampered = SnapshotEnvelope(
        payload={"objectives": ["tampered"]},
        checksum=store.load_snapshot().checksum,
    )
    store.save_snapshot(tampered)
    with pytest.raises(CorruptSnapshot):
        service.load()


def test_has_state_becomes_true_once_anything_is_recorded():
    mc = make_control()
    service, _ = make_service(mc)
    # make_control() registered before recording began, so nothing is
    # captured yet -- recording only sees what happens after it starts.
    assert service.has_state() is False
    mc.submit_objective(demo_objective())
    assert service.has_state() is True


def test_audit_is_restored_even_when_no_snapshot_exists():
    """A missing snapshot must not throw away a perfectly good event log
    -- deliverable #6 does not depend on a snapshot existing."""
    mc = make_control()
    _service, store = make_service(mc)
    mc.submit_objective(demo_objective())
    # deliberately no save()

    fresh = MissionControl()
    counts = PersistenceService(store, fresh).restore_into(fresh)

    assert counts["objectives"] == 0
    assert counts["audit_entries"] > 0


# ---- CheckpointSink (Rule 3) --------------------------------------------


def test_the_service_satisfies_the_runtime_checkpoint_protocol():
    service, _ = make_service()
    assert isinstance(service, CheckpointSink)


def test_a_checkpoint_round_trips_through_the_sink():
    mc = make_control()
    service, _ = make_service(mc)
    service.save_checkpoint(
        RuntimeCheckpoint(state=RuntimeState.IDLE, cycle=5, retries_performed=2)
    )
    restored = service.load_checkpoint()
    assert restored.cycle == 5
    assert restored.retries_performed == 2


def test_a_checkpoint_without_a_mission_control_still_persists():
    service, _ = make_service()
    service.save_checkpoint(RuntimeCheckpoint(state=RuntimeState.IDLE, cycle=3))
    assert service.load_checkpoint().cycle == 3


def test_loading_a_checkpoint_when_none_exists_returns_none():
    service, _ = make_service()
    assert service.load_checkpoint() is None


def test_a_corrupt_snapshot_yields_no_checkpoint_rather_than_raising():
    """The Runtime asking for a checkpoint must never be the thing that
    crashes startup."""
    service, store = make_service()
    store.save_snapshot(SnapshotEnvelope(payload={"runtime": {"cycle": 1}}, checksum="wrong"))
    assert service.load_checkpoint() is None


def test_a_checkpoint_with_a_mission_control_keeps_both_consistent():
    """Runtime counters and Mission Control state must describe the same
    moment, not two different ones."""
    mc = make_control()
    service, _ = make_service(mc)
    mc.submit_objective(demo_objective())
    service.save_checkpoint(RuntimeCheckpoint(state=RuntimeState.IDLE, cycle=9))

    envelope = service.load()
    assert envelope.payload["runtime"]["cycle"] == 9
    assert len(envelope.payload["objectives"]) == 1


# ---- restore (deliverable #8) -------------------------------------------


def test_restore_rebuilds_registries_and_objectives_into_a_fresh_control():
    mc = make_control()
    service, store = make_service(mc)
    mc.submit_objective(demo_objective())
    service.save()

    fresh = MissionControl()
    counts = PersistenceService(store, fresh).restore_into(fresh)

    assert counts["executives"] == 1
    assert counts["capabilities"] == 2
    assert counts["objectives"] == 1
    assert fresh.executives.has("demo")
    assert fresh.capabilities.has("Demo.DoThing")
    assert len(fresh.dispatcher.objectives()) == 1


def test_restore_publishes_no_events_so_history_is_not_duplicated():
    """The reason ADR-0015's additive contract exists."""
    mc = make_control()
    service, store = make_service(mc)
    mc.submit_objective(demo_objective())
    service.save()

    fresh = MissionControl()
    PersistenceService(store, fresh).restore_into(fresh, restore_audit=False)

    submitted = [e for e in fresh.audit.entries if e.event_type is EventType.OBJECTIVE_SUBMITTED]
    assert submitted == [], "restoring must not republish creation events"


def test_restore_reestablishes_the_current_objective_for_founder_state():
    """Without this, founder_state() reports an empty snapshot after a
    successful recovery -- found by a real kill-and-resume run."""
    mc = make_control()
    service, store = make_service(mc)
    objective = mc.submit_objective(demo_objective())
    mc.dispatch_ready()
    mc.task_started("t1")
    mc.task_completed("t1")
    service.save()

    fresh = MissionControl()
    PersistenceService(store, fresh).restore_into(fresh)

    state = fresh.founder_state()
    assert state.current_objective_id == objective.objective_id
    assert state.progress == 0.5


def test_restore_preserves_task_states_and_evidence():
    mc = make_control()
    service, store = make_service(mc)
    mc.submit_objective(demo_objective())
    mc.dispatch_ready()
    mc.task_started("t1")
    mc.task_completed("t1", evidence_id="ev-1")
    service.save()

    fresh = MissionControl()
    PersistenceService(store, fresh).restore_into(fresh)

    task = fresh.dispatcher.objectives()[0].task("t1")
    assert task.state is TaskState.COMPLETED
    assert task.evidence_id == "ev-1"


def test_restore_rebuilds_audit_history_identically():
    """Entries come back with their original event ids and timestamps --
    which is what makes `AuditStream.record()` sufficient, with no change
    to the frozen audit component."""
    mc = make_control()
    service, store = make_service(mc)
    mc.submit_objective(demo_objective())
    service.save()

    # Only events recorded after start_recording() are in the log; that is
    # the honest comparison set.
    logged = store.read_events()
    original = [(e["event_id"], e["event_type"], e["occurred_at"]) for e in logged]

    fresh = MissionControl()
    PersistenceService(store, fresh).restore_into(fresh, restore_audit=True)

    restored = [
        (e.event_id, e.event_type.value, e.occurred_at.isoformat())
        for e in fresh.audit.entries
    ]
    assert restored == original


def test_restore_is_idempotent_and_skips_what_already_exists():
    mc = make_control()
    service, store = make_service(mc)
    mc.submit_objective(demo_objective())
    service.save()

    fresh = make_control()  # same executive already registered
    counts = PersistenceService(store, fresh).restore_into(fresh, restore_audit=False)

    assert counts["executives"] == 0
    assert counts["capabilities"] == 0
    assert len(fresh.executives) == 1


def test_restoring_from_nothing_returns_zero_counts():
    fresh = MissionControl()
    counts = PersistenceService(InMemoryStateStore(), fresh).restore_into(fresh)
    assert counts == {
        "executives": 0,
        "capabilities": 0,
        "objectives": 0,
        "audit_entries": 0,
    }


def test_restore_quarantines_interrupted_tasks():
    mc = make_control()
    service, store = make_service(mc)
    mc.submit_objective(demo_objective())
    mc.dispatch_ready()
    mc.task_started("t1")  # RUNNING when the process "dies"
    service.save()

    fresh = MissionControl()
    PersistenceService(store, fresh).restore_into(fresh)

    task = fresh.dispatcher.objectives()[0].task("t1")
    assert task.state is TaskState.FAILED
    assert any("duplicate execution" in error for error in task.errors)


def test_restore_can_be_asked_not_to_quarantine():
    mc = make_control()
    service, store = make_service(mc)
    mc.submit_objective(demo_objective())
    mc.dispatch_ready()
    mc.task_started("t1")
    service.save()

    fresh = MissionControl()
    PersistenceService(store, fresh).restore_into(fresh, quarantine_interrupted=False)
    assert fresh.dispatcher.objectives()[0].task("t1").state is TaskState.RUNNING


def test_a_restored_system_can_be_snapshotted_again():
    """Restore must produce a genuinely usable system, not a read-only
    reconstruction."""
    mc = make_control()
    service, store = make_service(mc)
    mc.submit_objective(demo_objective())
    service.save()

    fresh = MissionControl()
    second = PersistenceService(store, fresh)
    second.restore_into(fresh)
    second.build_snapshot(fresh).verify()


def test_persisting_to_a_real_directory_survives_a_new_store_object(tmp_path):
    mc = make_control()
    store = JsonFileStateStore(tmp_path)
    service = PersistenceService(store, mc)
    service.start_recording()
    mc.submit_objective(demo_objective())
    service.save()

    fresh_control = MissionControl()
    fresh_service = PersistenceService(JsonFileStateStore(tmp_path), fresh_control)
    counts = fresh_service.restore_into(fresh_control)

    assert counts["objectives"] == 1
    assert counts["audit_entries"] > 0
