"""Audit Stream tests (Mission Brief 023 deliverable #8) — immutable
execution history. See MISSION_CONTROL_ARCHITECTURE.md §11.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from master_agent.mission_control.audit import AuditStream
from master_agent.mission_control.events import Event, EventBus, EventType
from master_agent.mission_control.mission_control import MissionControl
from master_agent.mission_control.tasks import Objective, Task


def test_audit_stream_records_every_published_event():
    bus = EventBus()
    stream = AuditStream(bus)
    bus.publish(Event(event_type=EventType.TASK_CREATED, source="x"))
    bus.publish(Event(event_type=EventType.TASK_COMPLETED, source="x"))
    assert len(stream) == 2


def test_entries_are_sequenced_in_publication_order():
    bus = EventBus()
    stream = AuditStream(bus)
    for _ in range(5):
        bus.publish(Event(event_type=EventType.TASK_CREATED, source="x"))
    assert [entry.sequence for entry in stream.entries] == [0, 1, 2, 3, 4]


def test_an_audit_entry_cannot_be_edited_after_the_fact():
    bus = EventBus()
    stream = AuditStream(bus)
    bus.publish(Event(event_type=EventType.TASK_CREATED, source="x"))
    entry = stream.entries[0]
    with pytest.raises(FrozenInstanceError):
        entry.source = "tampered"  # type: ignore[misc]


def test_history_cannot_be_mutated_through_the_entries_accessor():
    bus = EventBus()
    stream = AuditStream(bus)
    bus.publish(Event(event_type=EventType.TASK_CREATED, source="x"))

    borrowed = stream.entries
    borrowed.clear()
    assert len(stream) == 1, "entries must return a copy, not the live list"


def test_the_stream_exposes_no_delete_or_truncate_surface():
    """Immutable means there is no supported way to remove history, not
    that callers are asked politely not to."""
    public = {name for name in dir(AuditStream) if not name.startswith("_")}
    for forbidden in ("clear", "delete", "remove", "truncate", "prune", "reset"):
        assert forbidden not in public


def test_failures_are_individually_retrievable():
    """'Every failure is auditable' -- the direct query for it."""
    mc = MissionControl()
    mc.register_executive(executive_id="e", version="1")
    mc.mark_executive_ready("e")
    mc.submit_objective(
        Objective(description="x", tasks=[Task(capability="Missing.Capability", task_id="t1")])
    )
    mc.dispatch_ready()

    failures = mc.audit.failures()
    assert failures
    assert any(entry.event_type is EventType.TASK_FAILED for entry in failures)


def test_audit_can_be_filtered_by_objective_task_and_type():
    mc = MissionControl()
    from master_agent.mission_control.capabilities import CapabilityDescriptor, qualified_name

    mc.register_executive(
        executive_id="browser",
        version="1",
        capabilities=[
            CapabilityDescriptor(
                qualified_name=qualified_name("browser", "navigate"),
                executive_id="browser",
                capability="navigate",
            )
        ],
    )
    mc.mark_executive_ready("browser")
    from master_agent.mission_control.executives import ExecutiveHealth

    mc.set_executive_health("browser", ExecutiveHealth.HEALTHY)

    objective = mc.submit_objective(
        Objective(description="x", tasks=[Task(capability="Browser.Navigate", task_id="t1")])
    )
    mc.dispatch_ready()
    mc.task_started("t1")

    assert mc.audit.for_objective(objective.objective_id)
    assert mc.audit.for_task("t1")
    assert mc.audit.of_type(EventType.TASK_STARTED)


def test_a_worker_audit_record_from_mission_brief_022_can_be_ingested_as_an_event():
    """The Audit Stream is system-wide and event-level; verification's
    AuditLog is per-Worker and step-level. One can feed the other -- they
    are not two copies of the same thing (MISSION_CONTROL_ARCHITECTURE.md
    §11)."""
    mc = MissionControl()
    reporter = mc.reporter_for("browser")
    reporter.report(
        EventType.VERIFICATION_COMPLETED,
        task_id="t1",
        capability="Browser.Click",
        payload={"verdict": "matched", "evidence_id": "ev-1"},
    )

    entries = mc.audit.of_type(EventType.VERIFICATION_COMPLETED)
    assert len(entries) == 1
    assert entries[0].source == "browser"
    assert entries[0].payload["evidence_id"] == "ev-1"
