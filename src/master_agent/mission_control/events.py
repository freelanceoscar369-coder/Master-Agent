"""The Universal Event Bus and the single event schema every Executive
reports with. See MISSION_CONTROL_ARCHITECTURE.md §5.

Deliverable #10 (Communication Contract) is not a separate component: it
is the constraint that `Event` below is the *only* reporting shape in the
system. No custom logging, no per-Executive event formats. An Executive
that needs to say something says it as an Event, through
reporting.ExecutiveReporter, or it isn't heard.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class EventType(str, Enum):
    """Every state change worth observing. The ten Mission Brief 023 named
    explicitly, plus the transitions the lifecycle genuinely requires — a
    state change that isn't observable can't be audited, which would break
    "every failure is auditable."
    """

    # --- the ten named in the brief ---
    TASK_CREATED = "task_created"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    VERIFICATION_STARTED = "verification_started"
    VERIFICATION_COMPLETED = "verification_completed"
    KNOWLEDGE_ACQUIRED = "knowledge_acquired"
    CAPABILITY_REGISTERED = "capability_registered"
    SELF_DEVELOPMENT_STARTED = "self_development_started"
    SELF_DEVELOPMENT_COMPLETED = "self_development_completed"

    # --- required by the lifecycle this coordination layer actually runs ---
    OBJECTIVE_SUBMITTED = "objective_submitted"
    OBJECTIVE_COMPLETED = "objective_completed"
    OBJECTIVE_FAILED = "objective_failed"
    # Named TASK_ASSIGNED (not TASK_DISPATCHED) to match the event
    # sequence MIT-001 specifies. One name per event -- an alias would be
    # exactly the drift the Constitution's terminology freeze forbids.
    TASK_ASSIGNED = "task_assigned"
    TASK_BLOCKED = "task_blocked"
    EXECUTIVE_REGISTERED = "executive_registered"
    EXECUTIVE_HEALTH_CHANGED = "executive_health_changed"
    WORKER_STATE_CHANGED = "worker_state_changed"
    KNOWLEDGE_REQUESTED = "knowledge_requested"
    KNOWLEDGE_STAGE_ADVANCED = "knowledge_stage_advanced"
    KNOWLEDGE_REJECTED = "knowledge_rejected"
    APPROVAL_REQUIRED = "approval_required"
    # MB028.0 / ADR-0019. Approval evidence must outlive the process: the
    # grant ledger is in-memory by design (persisting it would silently
    # re-arm every approval ever given at each restart), so the event log
    # and Audit Stream are the only durable record that an approval
    # happened, who made it, when, and for which capability.
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    # MB028.1 -- the founder workflow. REQUESTED opens a question,
    # DEFERRED moves it out of the way without answering it, EXPIRED
    # closes it unanswered. GRANTED/DENIED above remain the *answers*.
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_DEFERRED = "approval_deferred"
    APPROVAL_EXPIRED = "approval_expired"
    SUBSCRIBER_FAILED = "subscriber_failed"

    # --- Runtime Engine (MB024). Every cycle must be observable, so each
    # runtime state change and each mechanical retry is an event too.
    RUNTIME_STARTED = "runtime_started"
    RUNTIME_STATE_CHANGED = "runtime_state_changed"
    DISPATCH_STARTED = "dispatch_started"
    RUNTIME_IDLE = "runtime_idle"
    RUNTIME_ERROR = "runtime_error"
    RUNTIME_STOPPING = "runtime_stopping"
    RUNTIME_STOPPED = "runtime_stopped"
    TASK_RETRY_SCHEDULED = "task_retry_scheduled"
    TASK_ESCALATED = "task_escalated"


MISSION_CONTROL_SOURCE = "mission_control"


@dataclass(frozen=True)
class Event:
    """The one schema. Frozen: an event describes something that already
    happened, so it is not editable after the fact — the same principle
    the Audit Stream enforces at the collection level.

    `payload` must stay a plain, JSON-shaped dict — never a live object —
    for the same reason Evidence.observation must (Constitution §9.2): an
    event has to survive being logged, persisted, or replayed without its
    consumer knowing what produced it.
    """

    event_type: EventType
    source: str
    event_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    objective_id: str | None = None
    task_id: str | None = None
    capability: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "occurred_at": self.occurred_at.isoformat(),
            "source": self.source,
            "objective_id": self.objective_id,
            "task_id": self.task_id,
            "capability": self.capability,
            "payload": dict(self.payload),
            "error": self.error,
        }


Subscriber = Callable[[Event], None]


class EventBus:
    """Synchronous, in-process publish/subscribe.

    Synchronous on purpose (MISSION_CONTROL_ARCHITECTURE.md §5): a broker
    is the wrong answer for a single-process, local-first Founder Edition,
    and in-order delivery is what makes the Audit Stream's ordering
    trustworthy. The interface is small enough that an async or
    cross-process implementation is a drop-in replacement, not a redesign.
    """

    def __init__(self) -> None:
        self._typed: dict[EventType, list[Subscriber]] = {}
        self._all: list[Subscriber] = []
        self._published = 0

    @property
    def published_count(self) -> int:
        return self._published

    def subscribe(self, handler: Subscriber, event_type: EventType | None = None) -> None:
        """`event_type=None` subscribes to everything (what the Audit
        Stream does). A subscriber that doesn't know about a newly-added
        event type simply never fires for it, rather than breaking — which
        is what lets an old consumer survive a new Executive."""
        if event_type is None:
            self._all.append(handler)
        else:
            self._typed.setdefault(event_type, []).append(handler)

    def publish(self, event: Event) -> None:
        """A subscriber that raises is isolated: its failure is captured
        and re-emitted as a SUBSCRIBER_FAILED event rather than allowed to
        break the publisher or starve the remaining subscribers. A broken
        dashboard must never take down execution.
        """
        self._published += 1
        failures: list[tuple[Subscriber, Exception]] = []

        for handler in list(self._all) + list(self._typed.get(event.event_type, [])):
            try:
                handler(event)
            except Exception as exc:  # noqa: BLE001 — deliberate: see docstring
                failures.append((handler, exc))

        for handler, exc in failures:
            self._emit_subscriber_failure(handler, exc, event)

    def _emit_subscriber_failure(
        self, handler: Subscriber, exc: Exception, original: Event
    ) -> None:
        """Emitted without re-entering the failing handler's own path: only
        subscribers that did not just fail are notified, so a subscriber
        that always raises cannot cause infinite recursion."""
        failure_event = Event(
            event_type=EventType.SUBSCRIBER_FAILED,
            source=MISSION_CONTROL_SOURCE,
            objective_id=original.objective_id,
            task_id=original.task_id,
            payload={
                "handler": getattr(handler, "__name__", repr(handler)),
                "original_event_id": original.event_id,
                "original_event_type": original.event_type.value,
            },
            error=str(exc),
        )
        self._published += 1
        for candidate in list(self._all) + list(self._typed.get(EventType.SUBSCRIBER_FAILED, [])):
            if candidate is handler:
                continue
            try:
                candidate(failure_event)
            except Exception:  # noqa: BLE001, S110
                # Deliberately swallowed, and deliberately not logged: this
                # is a subscriber failing while being told that another
                # subscriber failed. Reporting it would publish another
                # failure event, which is exactly the recursion this
                # method exists to stop. The original failure is already
                # captured in the SUBSCRIBER_FAILED event above.
                pass
