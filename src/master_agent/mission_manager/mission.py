"""The Mission entity and its state machine. See ARCHITECTURE.md §4.3."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class MissionStatus(str, Enum):
    DRAFT = "draft"
    PLANNED = "planned"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Only these transitions are legal. The Mission Manager is the single place
# that mutates status, and it must consult this table before doing so —
# this is what keeps "what is happening right now" trustworthy for every
# other module reading it.
_ALLOWED_TRANSITIONS: dict[MissionStatus, set[MissionStatus]] = {
    MissionStatus.DRAFT: {MissionStatus.PLANNED, MissionStatus.CANCELLED},
    MissionStatus.PLANNED: {MissionStatus.AWAITING_APPROVAL, MissionStatus.EXECUTING, MissionStatus.CANCELLED},
    MissionStatus.AWAITING_APPROVAL: {MissionStatus.EXECUTING, MissionStatus.CANCELLED},
    MissionStatus.EXECUTING: {MissionStatus.AWAITING_APPROVAL, MissionStatus.VERIFYING, MissionStatus.FAILED, MissionStatus.CANCELLED},
    MissionStatus.VERIFYING: {MissionStatus.COMPLETED, MissionStatus.FAILED},
    MissionStatus.COMPLETED: set(),
    MissionStatus.FAILED: set(),
    MissionStatus.CANCELLED: set(),
}


class IllegalTransition(Exception):
    pass


@dataclass
class Mission:
    intent_summary: str
    mission_id: str = field(default_factory=lambda: str(uuid4()))
    status: MissionStatus = MissionStatus.DRAFT
    plan: Any = None  # MissionPlan, set once the Planner runs
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    outcome: dict[str, Any] | None = None

    def transition(self, new_status: MissionStatus) -> None:
        if new_status not in _ALLOWED_TRANSITIONS[self.status]:
            raise IllegalTransition(f"{self.status} -> {new_status} is not allowed")
        self.status = new_status
        self.updated_at = datetime.now(UTC)
