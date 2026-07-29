"""Universal Event Bus tests (Mission Brief 023 deliverable #1) and the
Communication Contract (#10). See MISSION_CONTROL_ARCHITECTURE.md §5.
"""
from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import pytest

from master_agent.mission_control.events import (
    MISSION_CONTROL_SOURCE,
    Event,
    EventBus,
    EventType,
)
from master_agent.mission_control.reporting import ExecutiveReporter


def test_all_ten_brief_named_event_types_exist():
    """The ten Mission Brief 023 names explicitly, by exact value."""
    expected = {
        "task_created",
        "task_started",
        "task_completed",
        "task_failed",
        "verification_started",
        "verification_completed",
        "knowledge_acquired",
        "capability_registered",
        "self_development_started",
        "self_development_completed",
    }
    actual = {member.value for member in EventType}
    assert expected <= actual


def test_event_is_frozen_so_history_cannot_be_edited_after_the_fact():
    event = Event(event_type=EventType.TASK_CREATED, source="x")
    with pytest.raises(FrozenInstanceError):
        event.source = "y"  # type: ignore[misc]


def test_event_as_dict_is_json_plain():
    event = Event(
        event_type=EventType.TASK_COMPLETED,
        source="browser",
        task_id="t1",
        capability="Browser.Navigate",
        payload={"a": 1},
    )
    json.dumps(event.as_dict())  # must not raise


def test_subscribe_to_a_specific_type_only_receives_that_type():
    bus = EventBus()
    seen: list[Event] = []
    bus.subscribe(seen.append, EventType.TASK_FAILED)

    bus.publish(Event(event_type=EventType.TASK_CREATED, source="x"))
    bus.publish(Event(event_type=EventType.TASK_FAILED, source="x"))

    assert [e.event_type for e in seen] == [EventType.TASK_FAILED]


def test_subscribe_to_all_receives_every_type_including_ones_added_later():
    """A subscriber to *all* is how the Audit Stream survives a new event
    type being added without touching it."""
    bus = EventBus()
    seen: list[Event] = []
    bus.subscribe(seen.append)

    bus.publish(Event(event_type=EventType.TASK_CREATED, source="x"))
    bus.publish(Event(event_type=EventType.KNOWLEDGE_ACQUIRED, source="x"))

    assert len(seen) == 2


def test_a_failing_subscriber_does_not_break_the_publisher_or_other_subscribers():
    bus = EventBus()
    delivered: list[Event] = []

    def broken(_event: Event) -> None:
        raise RuntimeError("dashboard exploded")

    bus.subscribe(broken)
    bus.subscribe(delivered.append)

    bus.publish(Event(event_type=EventType.TASK_CREATED, source="x"))

    # The healthy subscriber still got the original event, plus the
    # SUBSCRIBER_FAILED event reporting the broken one.
    types = [e.event_type for e in delivered]
    assert EventType.TASK_CREATED in types
    assert EventType.SUBSCRIBER_FAILED in types


def test_a_permanently_failing_subscriber_cannot_cause_infinite_recursion():
    bus = EventBus()

    def always_broken(_event: Event) -> None:
        raise RuntimeError("always")

    bus.subscribe(always_broken)
    bus.publish(Event(event_type=EventType.TASK_CREATED, source="x"))  # must return


def test_executive_reporter_stamps_identity_and_publishes_the_single_schema():
    bus = EventBus()
    seen: list[Event] = []
    bus.subscribe(seen.append)

    reporter = ExecutiveReporter("browser", bus)
    returned = reporter.report(
        EventType.TASK_STARTED, task_id="t1", capability="Browser.Navigate"
    )

    assert returned.source == "browser"
    assert seen[0].source == "browser"
    assert seen[0].task_id == "t1"
    assert isinstance(seen[0], Event)


def test_reporter_exposes_no_free_text_or_custom_logging_channel():
    """Deliverable #10: 'No custom logging. No custom event formats.' The
    reporter must offer exactly one typed way to say something."""
    public = {name for name in dir(ExecutiveReporter) if not name.startswith("_")}
    assert public == {"report", "executive_id"}


def test_mission_control_source_constant_is_used_for_system_events():
    assert MISSION_CONTROL_SOURCE == "mission_control"
