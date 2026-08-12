"""The Founder Completion Queue (Task 2.5).

MB028.1's `ApprovalQueue` (`approvals.py`) answers *"may this risky action
run"* — a capability-risk question, gated by the Permission System, asked
**before** a task executes. This module answers a different question that
arises **after** every task in an objective has already run and verified
cleanly: *"is this result acceptable to close out."*

Deliberately the same shape as `ApprovalQueue` — request/confirm, an
append-only decision, one event pair on the same bus — because
`approvals.py`'s own docstring already states the right move for a new
kind of founder question: *"A third queue of the same shape belongs beside
them, not in a new layer."* It is not the same queue, though: nothing here
touches the Permission System, grants any authority, or gates whether
anything executes. An objective that never gets confirmed already ran to
completion: confirmation gates only the founder-facing terminal state
(`AWAITING_FOUNDER_COMPLETION` vs. `COMPLETED`), never the work itself.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class CompletionState(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"


class UnknownCompletion(Exception):
    pass


class CompletionAlreadyConfirmed(Exception):
    """A confirmed completion never changes — the same "a decision, once
    made, is final" rule `approvals.py` applies to its own ledger."""


@dataclass
class PendingCompletion:
    """One objective whose execution finished and is waiting for the
    founder to say the result is acceptable.

    Mutable only through the queue's `confirm()` — never edited in place
    by a reader, the same discipline `PendingApproval` follows."""

    objective_id: str
    objective: str
    requested_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completion_id: str = field(default_factory=lambda: uuid4().hex[:8])
    state: CompletionState = CompletionState.PENDING
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
    note: str = ""

    @property
    def is_open(self) -> bool:
        return self.state is CompletionState.PENDING

    def as_dict(self) -> dict[str, Any]:
        return {
            "completion_id": self.completion_id,
            "objective_id": self.objective_id,
            "objective": self.objective,
            "requested_at": self.requested_at.isoformat(),
            "state": self.state.value,
            "confirmed_by": self.confirmed_by,
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PendingCompletion:
        confirmed_at = data.get("confirmed_at")
        return cls(
            objective_id=data["objective_id"],
            objective=data.get("objective", ""),
            requested_at=datetime.fromisoformat(data["requested_at"]),
            completion_id=data["completion_id"],
            state=CompletionState(data.get("state", "pending")),
            confirmed_by=data.get("confirmed_by"),
            confirmed_at=datetime.fromisoformat(confirmed_at) if confirmed_at else None,
            note=data.get("note", ""),
        )


class CompletionQueue:
    """Pending completions, in the order they were opened, plus the
    append-only record of every confirmation. See `approvals.ApprovalQueue`
    for the pattern this copies."""

    def __init__(self, clock: Any = None) -> None:
        self._items: dict[str, PendingCompletion] = {}
        self._order: list[str] = []
        self._clock = clock or (lambda: datetime.now(UTC))

    def request(self, item: PendingCompletion) -> tuple[PendingCompletion, bool]:
        """Open a completion question, or return the existing open one for
        this objective. Idempotent per objective_id — the same reason
        `ApprovalQueue.request()` is: nothing re-asks the founder twice."""
        existing = self.find_open(item.objective_id)
        if existing is not None:
            return existing, False
        item.requested_at = self._clock()
        self._items[item.completion_id] = item
        self._order.append(item.completion_id)
        return item, True

    def find_open(self, objective_id: str) -> PendingCompletion | None:
        for completion_id in reversed(self._order):
            item = self._items[completion_id]
            if item.objective_id == objective_id and item.is_open:
                return item
        return None

    def confirm(
        self, completion_id: str, founder: str = "founder", note: str = ""
    ) -> PendingCompletion:
        item = self.get(completion_id)
        if item.state is CompletionState.CONFIRMED:
            raise CompletionAlreadyConfirmed(
                f"completion {completion_id} is already confirmed"
            )
        item.state = CompletionState.CONFIRMED
        item.confirmed_by = founder
        item.confirmed_at = self._clock()
        item.note = note
        return item

    def get(self, completion_id: str) -> PendingCompletion:
        item = self._items.get(completion_id)
        if item is None:
            raise UnknownCompletion(f"unknown completion: {completion_id}")
        return item

    def open(self) -> list[PendingCompletion]:
        return [
            self._items[i] for i in self._order if self._items[i].state is CompletionState.PENDING
        ]

    def all(self) -> list[PendingCompletion]:
        return [self._items[i] for i in self._order]

    def __len__(self) -> int:
        return len(self.open())

    # ---- persistence, the same shape as ApprovalQueue.restore() ----------

    def as_dict(self) -> dict[str, Any]:
        return {"completions": [item.as_dict() for item in self.all()]}

    def restore(self, data: dict[str, Any]) -> None:
        for entry in data.get("completions", []):
            item = PendingCompletion.from_dict(entry)
            if item.completion_id in self._items:
                continue
            self._items[item.completion_id] = item
            self._order.append(item.completion_id)
