"""The Self-Development Queue (Mission Brief 023 deliverable #6).

What the system knows it lacks: pending capabilities, learning tasks,
architecture improvements, research requests, and implementation work.

Mission Control *queues and orders* these. It never implements them —
writing a new capability is work, and Mission Control never performs work
(MISSION_CONTROL_ARCHITECTURE.md §1). This queue is the honest, inspectable
answer to "what does this system still need in order to grow", which is
what makes self-development a tracked process rather than an aspiration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class SelfDevelopmentType(str, Enum):
    """The brief's five categories, as a closed vocabulary — a new kind of
    self-development is a deliberate addition here, not a free-text string
    each caller invents."""

    PENDING_CAPABILITY = "pending_capability"
    LEARNING_TASK = "learning_task"
    ARCHITECTURE_IMPROVEMENT = "architecture_improvement"
    RESEARCH_REQUEST = "research_request"
    IMPLEMENTATION = "implementation"


class SelfDevelopmentState(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    REJECTED = "rejected"


_ALLOWED_TRANSITIONS: dict[SelfDevelopmentState, set[SelfDevelopmentState]] = {
    SelfDevelopmentState.PROPOSED: {SelfDevelopmentState.ACCEPTED, SelfDevelopmentState.REJECTED},
    SelfDevelopmentState.ACCEPTED: {
        SelfDevelopmentState.IN_PROGRESS,
        SelfDevelopmentState.REJECTED,
    },
    SelfDevelopmentState.IN_PROGRESS: {SelfDevelopmentState.DONE, SelfDevelopmentState.REJECTED},
    SelfDevelopmentState.DONE: set(),
    SelfDevelopmentState.REJECTED: set(),
}


class IllegalSelfDevelopmentTransition(Exception):
    pass


class UnknownSelfDevelopmentItem(Exception):
    pass


@dataclass
class SelfDevelopmentItem:
    item_type: SelfDevelopmentType
    title: str
    detail: str = ""
    item_id: str = field(default_factory=lambda: str(uuid4()))
    state: SelfDevelopmentState = SelfDevelopmentState.PROPOSED
    priority: int = 100  # lower sorts first; ties broken by insertion order
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def as_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "type": self.item_type.value,
            "title": self.title,
            "detail": self.detail,
            "state": self.state.value,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
        }


class SelfDevelopmentQueue:
    def __init__(self) -> None:
        self._items: dict[str, SelfDevelopmentItem] = {}
        self._order: list[str] = []

    def add(self, item: SelfDevelopmentItem) -> SelfDevelopmentItem:
        self._items[item.item_id] = item
        self._order.append(item.item_id)
        return item

    def get(self, item_id: str) -> SelfDevelopmentItem:
        item = self._items.get(item_id)
        if item is None:
            raise UnknownSelfDevelopmentItem(f"unknown self-development item: {item_id}")
        return item

    def transition(self, item_id: str, new_state: SelfDevelopmentState) -> SelfDevelopmentItem:
        item = self.get(item_id)
        if new_state not in _ALLOWED_TRANSITIONS[item.state]:
            raise IllegalSelfDevelopmentTransition(
                f"{item.state.value} -> {new_state.value} is not allowed"
            )
        item.state = new_state
        item.updated_at = datetime.now(UTC)
        return item

    def all(self) -> list[SelfDevelopmentItem]:
        return [self._items[item_id] for item_id in self._order]

    def by_type(self, item_type: SelfDevelopmentType) -> list[SelfDevelopmentItem]:
        return [item for item in self.all() if item.item_type is item_type]

    def by_state(self, state: SelfDevelopmentState) -> list[SelfDevelopmentItem]:
        return [item for item in self.all() if item.state is state]

    def pending(self) -> list[SelfDevelopmentItem]:
        """Everything not yet finished or rejected, in priority order —
        insertion order breaks ties, so the queue is deterministic rather
        than dependent on dict iteration."""
        open_items = [
            item
            for item in self.all()
            if item.state not in {SelfDevelopmentState.DONE, SelfDevelopmentState.REJECTED}
        ]
        return sorted(open_items, key=lambda item: (item.priority, self._order.index(item.item_id)))

    def __len__(self) -> int:
        return len(self._items)
