"""Runtime health (Mission Brief 024 deliverable #6).

Exactly the seven fields the brief names. Every one is derived by
*reading* Mission Control at the moment it is asked, never by maintaining
a shadow copy that could drift out of agreement with it -- the same
principle that keeps Founder State honest.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from master_agent.runtime.states import RuntimeState


@dataclass(frozen=True)
class RuntimeHealth:
    state: RuntimeState
    uptime_seconds: float
    active_cycle: int
    queue_length: int
    executives_online: int
    executives_busy: int
    last_dispatch_at: datetime | None
    last_verification_at: datetime | None
    tasks_completed: int = 0
    tasks_failed: int = 0
    retries_performed: int = 0
    escalations: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "uptime_seconds": self.uptime_seconds,
            "active_cycle": self.active_cycle,
            "queue_length": self.queue_length,
            "executives_online": self.executives_online,
            "executives_busy": self.executives_busy,
            "last_dispatch_at": (
                self.last_dispatch_at.isoformat() if self.last_dispatch_at else None
            ),
            "last_verification_at": (
                self.last_verification_at.isoformat() if self.last_verification_at else None
            ),
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "retries_performed": self.retries_performed,
            "escalations": self.escalations,
        }
