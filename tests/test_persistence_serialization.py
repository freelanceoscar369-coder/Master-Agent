"""Serialization round-trips, and the quarantine policy for interrupted
work (ADR-0015 Decision 4).
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from master_agent.mission_control.audit import AuditEntry
from master_agent.mission_control.capabilities import CapabilityDescriptor
from master_agent.mission_control.events import Event, EventType
from master_agent.mission_control.executives import ExecutiveHealth, ExecutiveRecord
from master_agent.mission_control.lifecycle import WorkerState
from master_agent.mission_control.tasks import Objective, Task, TaskState
from master_agent.persistence.serialization import (
    INTERRUPTED_ERROR,
    INTERRUPTED_STATES,
    audit_entry_to_event,
    capability_from_dict,
    capability_to_dict,
    event_from_dict,
    event_to_dict,
    executive_from_dict,
    executive_to_dict,
    objective_from_dict,
    objective_to_dict,
    task_from_dict,
    task_to_dict,
)

# ---- tasks --------------------------------------------------------------


def test_task_round_trips_with_every_field():
    task = Task(
        capability="Browser.Navigate",
        payload={"url": "about:blank"},
        depends_on=["t0"],
        task_id="t1",
        state=TaskState.COMPLETED,
        assigned_executive="browser",
        result={"ok": True},
        evidence_id="ev-1",
        errors=["a warning"],
    )
    task.started_at = datetime.now(UTC)
    task.ended_at = datetime.now(UTC)

    restored = task_from_dict(task_to_dict(task))

    assert restored.task_id == task.task_id
    assert restored.capability == task.capability
    assert restored.payload == task.payload
    assert restored.depends_on == task.depends_on
    assert restored.state is TaskState.COMPLETED
    assert restored.assigned_executive == "browser"
    assert restored.result == {"ok": True}
    assert restored.evidence_id == "ev-1"
    assert restored.errors == ["a warning"]
    assert restored.started_at == task.started_at
    assert restored.ended_at == task.ended_at


def test_a_serialised_task_is_json_plain():
    task = Task(capability="X.Y", payload={"a": 1}, task_id="t1")
    json.dumps(task_to_dict(task))  # must not raise


@pytest.mark.parametrize("state", sorted(INTERRUPTED_STATES, key=lambda s: s.value))
def test_an_interrupted_task_is_quarantined_never_silently_rerun(state):
    """ADR-0015 Decision 4: side effects are unknown, so it must not be
    handed back as runnable."""
    task = Task(capability="X.Y", task_id="t1", state=state)
    restored = task_from_dict(task_to_dict(task))

    assert restored.state is TaskState.FAILED
    assert any(INTERRUPTED_ERROR in error for error in restored.errors)


@pytest.mark.parametrize(
    "state", [TaskState.CREATED, TaskState.READY, TaskState.BLOCKED, TaskState.COMPLETED,
              TaskState.FAILED]
)
def test_a_task_that_was_not_in_flight_restores_unchanged(state):
    task = Task(capability="X.Y", task_id="t1", state=state)
    assert task_from_dict(task_to_dict(task)).state is state


def test_quarantine_can_be_disabled_for_inspection_paths():
    task = Task(capability="X.Y", task_id="t1", state=TaskState.RUNNING)
    restored = task_from_dict(task_to_dict(task), quarantine_interrupted=False)
    assert restored.state is TaskState.RUNNING


def test_expected_outcome_is_deliberately_not_persisted():
    """It is a live object, not JSON state -- named in the mission brief
    rather than silently dropped."""
    assert "expected_outcome" not in task_to_dict(Task(capability="X.Y", task_id="t1"))


# ---- objectives ---------------------------------------------------------


def test_objective_round_trips_with_its_tasks_and_order():
    objective = Objective(
        description="demo",
        tasks=[
            Task(capability="A.B", task_id="t1", state=TaskState.COMPLETED),
            Task(capability="C.D", task_id="t2", depends_on=["t1"]),
        ],
        objective_id="obj-1",
    )
    restored = objective_from_dict(objective_to_dict(objective))

    assert restored.objective_id == "obj-1"
    assert restored.description == "demo"
    assert [t.task_id for t in restored.tasks] == ["t1", "t2"]
    assert restored.tasks[1].depends_on == ["t1"]
    assert restored.created_at == objective.created_at


def test_a_restored_objective_still_validates():
    objective = Objective(
        description="d",
        tasks=[Task(capability="A.B", task_id="t1")],
        objective_id="o",
    )
    objective_from_dict(objective_to_dict(objective)).validate()


def test_objective_progress_survives_the_round_trip():
    objective = Objective(
        description="d",
        tasks=[
            Task(capability="A.B", task_id="t1", state=TaskState.COMPLETED),
            Task(capability="A.B", task_id="t2", state=TaskState.CREATED),
        ],
    )
    assert objective_from_dict(objective_to_dict(objective)).progress == 0.5


# ---- executives and capabilities ----------------------------------------


def test_executive_round_trips_as_metadata():
    record = ExecutiveRecord(
        executive_id="browser",
        version="0.1.0",
        capabilities=["Browser.Navigate"],
        health=ExecutiveHealth.HEALTHY,
        state=WorkerState.READY,
        dependencies=["filesystem"],
    )
    restored = executive_from_dict(executive_to_dict(record))

    assert restored.executive_id == "browser"
    assert restored.version == "0.1.0"
    assert restored.capabilities == ["Browser.Navigate"]
    assert restored.health is ExecutiveHealth.HEALTHY
    assert restored.state is WorkerState.READY
    assert restored.dependencies == ["filesystem"]


def test_a_restored_executive_is_never_still_holding_a_task():
    """Its work was interrupted and quarantined; claiming it is busy would
    make it permanently undispatchable."""
    record = ExecutiveRecord(executive_id="browser", version="1", current_task_id="t1")
    assert executive_from_dict(executive_to_dict(record)).current_task_id is None


def test_no_transient_handle_is_serialised():
    """MB025 deliverable #5: metadata only."""
    record = ExecutiveRecord(executive_id="browser", version="1")
    data = executive_to_dict(record)
    json.dumps(data)
    assert set(data) == {
        "executive_id",
        "version",
        "capabilities",
        "health",
        "state",
        "dependencies",
        "current_task_id",
        "registered_at",
        "updated_at",
    }


def test_capability_round_trips():
    descriptor = CapabilityDescriptor(
        qualified_name="Browser.Navigate",
        executive_id="browser",
        capability="navigate",
        description="go somewhere",
        risk_tier="reversible_write",
        permission_category="modify",
        metadata={"note": "x"},
    )
    restored = capability_from_dict(capability_to_dict(descriptor))
    assert restored == descriptor


# ---- events and audit ---------------------------------------------------


def test_event_round_trips_preserving_identity_and_timestamp():
    """This is what lets audit history rebuild identically through the
    frozen AuditStream.record()."""
    event = Event(
        event_type=EventType.TASK_COMPLETED,
        source="browser",
        objective_id="o1",
        task_id="t1",
        capability="Browser.Navigate",
        payload={"evidence_id": "ev-1"},
        error=None,
    )
    restored = event_from_dict(event_to_dict(event))

    assert restored.event_id == event.event_id
    assert restored.occurred_at == event.occurred_at
    assert restored.event_type is event.event_type
    assert restored.source == event.source
    assert restored.objective_id == "o1"
    assert restored.task_id == "t1"
    assert restored.capability == "Browser.Navigate"
    assert restored.payload == {"evidence_id": "ev-1"}


def test_an_event_error_survives_the_round_trip():
    event = Event(event_type=EventType.TASK_FAILED, source="x", error="it broke")
    assert event_from_dict(event_to_dict(event)).error == "it broke"


def test_audit_entry_converts_to_an_equivalent_event():
    entry = AuditEntry(
        sequence=3,
        event_id="ev-abc",
        event_type=EventType.VERIFICATION_COMPLETED,
        occurred_at=datetime.now(UTC),
        source="browser",
        objective_id="o1",
        task_id="t1",
        capability="Browser.Click",
        payload={"verdict": "matched"},
        error=None,
    )
    event = audit_entry_to_event(entry)

    assert event.event_id == "ev-abc"
    assert event.occurred_at == entry.occurred_at
    assert event.payload == {"verdict": "matched"}


def test_a_naive_timestamp_is_read_back_as_utc():
    """Defensive: an externally-edited log should not produce a naive
    datetime that then fails to compare with aware ones."""
    event = event_from_dict(
        {
            "event_id": "e",
            "event_type": "task_created",
            "source": "x",
            "occurred_at": "2026-07-26T10:00:00",
        }
    )
    assert event.occurred_at.tzinfo is not None
