"""The Communication Contract (Mission Brief 023 deliverable #10).

"Every Executive reports using exactly the same schema. No custom logging.
No custom event formats."

This module is that contract made concrete: `ExecutiveReporter` is the one
helper an Executive uses to say anything, and everything it emits is an
`Event` (events.py) — the single schema. There is deliberately no
`log()`, no `message()`, no free-text channel, and no per-Executive
formatter here. An Executive that wants to report something reports it as
a typed Event or it isn't heard.

The reporter is a thin, stateless binding of "who am I" to the bus, so an
Executive never has to remember to stamp its own identity onto an event —
a per-caller detail that would drift the moment a second Executive existed.
"""
from __future__ import annotations

from typing import Any

from master_agent.mission_control.events import Event, EventBus, EventType


class ExecutiveReporter:
    def __init__(self, executive_id: str, bus: EventBus) -> None:
        self._executive_id = executive_id
        self._bus = bus

    @property
    def executive_id(self) -> str:
        return self._executive_id

    def report(
        self,
        event_type: EventType,
        objective_id: str | None = None,
        task_id: str | None = None,
        capability: str | None = None,
        payload: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> Event:
        """The only way an Executive says anything. Returns the Event it
        published so a caller can correlate (e.g. record the event id
        alongside its own result) without reaching into the bus."""
        event = Event(
            event_type=event_type,
            source=self._executive_id,
            objective_id=objective_id,
            task_id=task_id,
            capability=capability,
            payload=dict(payload or {}),
            error=error,
        )
        self._bus.publish(event)
        return event
