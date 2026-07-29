"""The Runtime's checkpoint seam (Mission Brief 025 deliverable #2, Rule 3).

    Rule 3: Runtime remains pure. Runtime requests checkpoints.
            It never performs storage operations.

`CheckpointSink` is defined **here, inside `runtime/`**, not in the
persistence package. That is deliberate and load-bearing: if the Runtime
imported `master_agent.persistence`, MB024's architecture test -- which
asserts `runtime/` imports nothing but `mission_control` and itself --
would fail, and the Runtime would have acquired the storage dependency
Rule 3 forbids.

Dependency inversion: the Runtime declares what it needs; the persistence
service satisfies it. The Runtime never learns that a file exists.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from master_agent.runtime.states import RuntimeState


@dataclass(frozen=True)
class RuntimeCheckpoint:
    """Everything needed to resume the loop where it stopped. Counters and
    state only -- no gateways, no sessions, no live handles, because none
    of those survive a process boundary and pretending otherwise is how a
    restored system lies about itself."""

    state: RuntimeState
    cycle: int
    tasks_completed: int = 0
    tasks_failed: int = 0
    retries_performed: int = 0
    escalations: int = 0
    last_dispatch_at: datetime | None = None
    last_verification_at: datetime | None = None
    captured_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "cycle": self.cycle,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "retries_performed": self.retries_performed,
            "escalations": self.escalations,
            "last_dispatch_at": (
                self.last_dispatch_at.isoformat() if self.last_dispatch_at else None
            ),
            "last_verification_at": (
                self.last_verification_at.isoformat() if self.last_verification_at else None
            ),
            "captured_at": self.captured_at.isoformat(),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> RuntimeCheckpoint:
        def parse(value: str | None) -> datetime | None:
            if not value:
                return None
            parsed = datetime.fromisoformat(value)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

        return RuntimeCheckpoint(
            # A restored Runtime is never resumed mid-cycle: it comes back
            # IDLE and re-observes Mission Control, because whatever it was
            # doing did not finish and must not be assumed to have.
            state=RuntimeState(data.get("state", RuntimeState.IDLE.value)),
            cycle=int(data.get("cycle", 0)),
            tasks_completed=int(data.get("tasks_completed", 0)),
            tasks_failed=int(data.get("tasks_failed", 0)),
            retries_performed=int(data.get("retries_performed", 0)),
            escalations=int(data.get("escalations", 0)),
            last_dispatch_at=parse(data.get("last_dispatch_at")),
            last_verification_at=parse(data.get("last_verification_at")),
            captured_at=parse(data.get("captured_at")) or datetime.now(UTC),
        )


@runtime_checkable
class CheckpointSink(Protocol):
    """What the Runtime needs from persistence, and nothing more."""

    def save_checkpoint(self, checkpoint: RuntimeCheckpoint) -> None: ...

    def load_checkpoint(self) -> RuntimeCheckpoint | None: ...
