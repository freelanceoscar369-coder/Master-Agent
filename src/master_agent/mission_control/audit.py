"""The Audit Stream (Mission Brief 023 deliverable #8) — immutable
execution history.

Subscribes to the Event Bus and records every event. Append-only: no
update, no delete, no truncation, no rewrite. Reads return copies, so a
caller cannot mutate history by holding a reference into it.

## Why this is not a duplicate of verification/audit.py

`verification.AuditLog` (Mission Brief 022) is a *per-Worker, per-step*
record of one Execute -> Verify -> Audit cycle for one capability call.
This stream is *system-wide and event-level*: objectives, dispatch
decisions, health changes, queue movements, and Worker step records alike.
A Worker's AuditRecord can be ingested here as an event; this is not a
second copy of it. See MISSION_CONTROL_ARCHITECTURE.md §11.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from master_agent.mission_control.events import Event, EventBus, EventType


@dataclass(frozen=True)
class AuditEntry:
    """Frozen, and holding only plain data copied out of the event — an
    audit entry that could be edited after the fact, or that held a
    reference to something mutable, would not be an audit record."""

    sequence: int
    event_id: str
    event_type: EventType
    occurred_at: datetime
    source: str
    objective_id: str | None
    task_id: str | None
    capability: str | None
    payload: dict[str, Any]
    error: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
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


class AuditStream:
    """Attach with `AuditStream(bus)` — it subscribes to every event type,
    including ones added later, because it subscribes to *all* rather than
    enumerating types it knows about."""

    def __init__(self, bus: EventBus | None = None) -> None:
        self._entries: list[AuditEntry] = []
        if bus is not None:
            bus.subscribe(self.record)

    def record(self, event: Event) -> None:
        self._entries.append(
            AuditEntry(
                sequence=len(self._entries),
                event_id=event.event_id,
                event_type=event.event_type,
                occurred_at=event.occurred_at,
                source=event.source,
                objective_id=event.objective_id,
                task_id=event.task_id,
                capability=event.capability,
                payload=dict(event.payload),
                error=event.error,
            )
        )

    @property
    def entries(self) -> list[AuditEntry]:
        """A copy of the list. The entries themselves are frozen
        dataclasses, so neither the sequence nor any record in it can be
        altered through this accessor."""
        return list(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def for_objective(self, objective_id: str) -> list[AuditEntry]:
        return [entry for entry in self._entries if entry.objective_id == objective_id]

    def for_task(self, task_id: str) -> list[AuditEntry]:
        return [entry for entry in self._entries if entry.task_id == task_id]

    def of_type(self, event_type: EventType) -> list[AuditEntry]:
        return [entry for entry in self._entries if entry.event_type is event_type]

    def failures(self) -> list[AuditEntry]:
        """Every entry carrying an error — the direct answer to "every
        failure is auditable"."""
        return [entry for entry in self._entries if entry.error is not None]
