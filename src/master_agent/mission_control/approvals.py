"""The Founder Approval Queue (Mission Brief 028.1).

MB028.0 gave Kalpavriksha a boundary: nothing irreversible executes
without founder approval. It did not give the founder a way to *answer*.
This is the inbox.

**Where it lives, and why here.** Mission Control already owns two
human-gated queues (Self-Development, Knowledge Acquisition) and already
publishes `APPROVAL_REQUIRED`; `FounderState` already has a
`waiting_approval` field. A third queue of the same shape belongs beside
them, not in a new layer.

**What it is not.** It is not a second permission system. The Permission
System (Constitution §5.2) remains the single ledger of *granted
authority*; this queue holds *unanswered questions*. A founder approving
here causes a grant to be issued there — one authority, one inbox, and
the boundary stays singular (ADR-0019 unweakened).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import uuid4


class ApprovalState(str, Enum):
    PENDING = "pending"
    DEFERRED = "deferred"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


#: A decision, once made, is final. Nothing moves out of these.
TERMINAL_APPROVAL_STATES = frozenset(
    {ApprovalState.APPROVED, ApprovalState.REJECTED, ApprovalState.EXPIRED}
)

#: States that still block execution and still need a founder.
OPEN_APPROVAL_STATES = frozenset({ApprovalState.PENDING, ApprovalState.DEFERRED})


class UnknownApproval(Exception):
    pass


class ApprovalAlreadyDecided(Exception):
    """A decided approval never changes. Re-approving a rejection would
    make the ledger a lie about what the founder actually said."""


@dataclass
class PendingApproval:
    """One unanswered question, carrying everything Deliverable 1 names.

    Mutable only through the queue's `approve`/`reject`/`defer`/`expire`
    methods — never edited in place by a reader, which is why every
    accessor hands back `as_dict()` rather than the object.
    """

    capability: str
    local_capability: str
    executive_id: str
    risk_tier: str
    reason: str
    task_id: str
    objective_id: str | None = None
    objective: str | None = None
    impact: str = "unknown"
    requested_by: str = "runtime"
    requested_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    approval_id: str = field(default_factory=lambda: uuid4().hex[:8])
    state: ApprovalState = ApprovalState.PENDING
    decided_by: str | None = None
    decided_at: datetime | None = None
    note: str = ""

    @property
    def is_open(self) -> bool:
        return self.state in OPEN_APPROVAL_STATES

    def age_seconds(self, now: datetime) -> float:
        return (now - self.requested_at).total_seconds()

    def as_dict(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "objective": self.objective,
            "objective_id": self.objective_id,
            "task_id": self.task_id,
            "executive_id": self.executive_id,
            "capability": self.capability,
            "local_capability": self.local_capability,
            "risk_tier": self.risk_tier,
            "reason": self.reason,
            "impact": self.impact,
            "requested_at": self.requested_at.isoformat(),
            "requested_by": self.requested_by,
            "state": self.state.value,
            "decided_by": self.decided_by,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PendingApproval:
        decided_at = data.get("decided_at")
        return cls(
            capability=data["capability"],
            local_capability=data.get("local_capability", ""),
            executive_id=data.get("executive_id", ""),
            risk_tier=data.get("risk_tier", ""),
            reason=data.get("reason", ""),
            task_id=data.get("task_id", ""),
            objective_id=data.get("objective_id"),
            objective=data.get("objective"),
            impact=data.get("impact", "unknown"),
            requested_by=data.get("requested_by", "runtime"),
            requested_at=datetime.fromisoformat(data["requested_at"]),
            approval_id=data["approval_id"],
            state=ApprovalState(data.get("state", "pending")),
            decided_by=data.get("decided_by"),
            decided_at=datetime.fromisoformat(decided_at) if decided_at else None,
            note=data.get("note", ""),
        )


@dataclass(frozen=True)
class ApprovalRecord:
    """Immutable evidence of one founder decision (Deliverable 4).

    Frozen, and the queue only ever appends: an approval ledger you can
    edit is not evidence of anything.
    """

    approval_id: str
    decision: str
    decided_by: str
    decided_at: datetime
    capability: str
    risk_tier: str
    task_id: str
    objective_id: str | None
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "decision": self.decision,
            "decided_by": self.decided_by,
            "decided_at": self.decided_at.isoformat(),
            "capability": self.capability,
            "risk_tier": self.risk_tier,
            "task_id": self.task_id,
            "objective_id": self.objective_id,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApprovalRecord:
        return cls(
            approval_id=data["approval_id"],
            decision=data["decision"],
            decided_by=data["decided_by"],
            decided_at=datetime.fromisoformat(data["decided_at"]),
            capability=data["capability"],
            risk_tier=data.get("risk_tier", ""),
            task_id=data.get("task_id", ""),
            objective_id=data.get("objective_id"),
            note=data.get("note", ""),
        )


class ApprovalQueue:
    """Pending approvals, in the order they were asked, plus an
    append-only ledger of every decision ever made."""

    def __init__(self, clock: Any = None) -> None:
        self._approvals: dict[str, PendingApproval] = {}
        self._order: list[str] = []
        self._ledger: list[ApprovalRecord] = []
        self._clock = clock or (lambda: datetime.now(UTC))

    # ---- asking -------------------------------------------------------

    def request(self, approval: PendingApproval) -> tuple[PendingApproval, bool]:
        """Enqueue a request, or return the existing one for the same
        (task, capability). Returns `(approval, is_new)`.

        **Idempotency is not an optimisation here, it is the design.** The
        Runtime re-checks the boundary on every cycle while a task waits,
        so without this a five-second wait would produce five hundred
        identical entries and five hundred `APPROVAL_REQUIRED` events. The
        founder is asked once and answers once.
        """
        existing = self.find_open(approval.task_id, approval.capability)
        if existing is not None:
            return existing, False
        # The queue stamps arrival, like any inbox. One clock, so a
        # timeout measured against `requested_at` and a decision stamped
        # by `_decide` can never disagree about what time it is.
        approval.requested_at = self._clock()
        self._approvals[approval.approval_id] = approval
        self._order.append(approval.approval_id)
        return approval, True

    def find_open(self, task_id: str, capability: str) -> PendingApproval | None:
        """The most recent *undecided* request for this task+capability.

        Scoped to open ones on purpose: once a request is decided, a later
        request for the same task is a genuinely new question. A rejected
        delete does not silently authorise the next delete, and an
        approved one does not silently authorise a repeat — which is the
        same rule ADR-0009 applies to `ONCE` grants.
        """
        for approval_id in reversed(self._order):
            approval = self._approvals[approval_id]
            if (
                approval.task_id == task_id
                and approval.capability == capability
                and approval.is_open
            ):
                return approval
        return None

    # ---- answering ----------------------------------------------------

    def approve(self, approval_id: str, founder: str, note: str = "") -> PendingApproval:
        return self._decide(approval_id, ApprovalState.APPROVED, founder, note)

    def reject(self, approval_id: str, founder: str, note: str = "") -> PendingApproval:
        return self._decide(approval_id, ApprovalState.REJECTED, founder, note)

    def expire(self, approval_id: str, note: str = "timed out") -> PendingApproval:
        return self._decide(approval_id, ApprovalState.EXPIRED, "system", note)

    def defer(self, approval_id: str, founder: str, note: str = "") -> PendingApproval:
        """Defer is *not* a decision. It changes how the queue presents the
        request — moved out of the founder's immediate way — and nothing
        else. The task stays blocked, the request stays open, and it is
        still there after a restart (Deliverable 5)."""
        approval = self.get(approval_id)
        self._refuse_if_decided(approval)
        approval.state = ApprovalState.DEFERRED
        approval.note = note
        return approval

    def _decide(
        self, approval_id: str, state: ApprovalState, founder: str, note: str
    ) -> PendingApproval:
        approval = self.get(approval_id)
        self._refuse_if_decided(approval)
        approval.state = state
        approval.decided_by = founder
        approval.decided_at = self._clock()
        approval.note = note
        self._ledger.append(
            ApprovalRecord(
                approval_id=approval.approval_id,
                decision=state.value,
                decided_by=founder,
                decided_at=approval.decided_at,
                capability=approval.capability,
                risk_tier=approval.risk_tier,
                task_id=approval.task_id,
                objective_id=approval.objective_id,
                note=note,
            )
        )
        return approval

    def _refuse_if_decided(self, approval: PendingApproval) -> None:
        if approval.state in TERMINAL_APPROVAL_STATES:
            raise ApprovalAlreadyDecided(
                f"approval {approval.approval_id} is already {approval.state.value}"
            )

    # ---- timeout ------------------------------------------------------

    def expire_due(self, timeout_seconds: float | None) -> list[PendingApproval]:
        """Expire every open request older than the timeout.

        `None` disables expiry entirely, which is the default: a request
        that vanishes while the founder is asleep is worse than one that
        waits, and "safe" here means *not executing*, which waiting
        already achieves.
        """
        if not timeout_seconds:
            return []
        now = self._clock()
        cutoff = timedelta(seconds=timeout_seconds)
        expired = []
        for approval in self.open():
            if now - approval.requested_at >= cutoff:
                self.expire(approval.approval_id)
                expired.append(approval)
        return expired

    # ---- reading ------------------------------------------------------

    def get(self, approval_id: str) -> PendingApproval:
        approval = self._approvals.get(approval_id)
        if approval is None:
            raise UnknownApproval(f"unknown approval: {approval_id}")
        return approval

    def open(self) -> list[PendingApproval]:
        """Everything still awaiting a founder, oldest first — pending
        before deferred, because deferring means "not now"."""
        pending = [
            self._approvals[i]
            for i in self._order
            if self._approvals[i].state is ApprovalState.PENDING
        ]
        deferred = [
            self._approvals[i]
            for i in self._order
            if self._approvals[i].state is ApprovalState.DEFERRED
        ]
        return pending + deferred

    def all(self) -> list[PendingApproval]:
        return [self._approvals[i] for i in self._order]

    def ledger(self) -> list[ApprovalRecord]:
        """Copies, not the list: evidence nobody can reach in and edit."""
        return list(self._ledger)

    def by_index(self, index: int) -> PendingApproval:
        """The founder types `approve 1`, not a hex id. Indexes are
        1-based and refer to the *currently displayed* open queue."""
        entries = self.open()
        if index < 1 or index > len(entries):
            raise UnknownApproval(f"no pending approval numbered {index}")
        return entries[index - 1]

    def __len__(self) -> int:
        return len(self.open())

    # ---- persistence (Deliverable 5) ----------------------------------

    def as_dict(self) -> dict[str, Any]:
        return {
            "approvals": [a.as_dict() for a in self.all()],
            "ledger": [r.as_dict() for r in self._ledger],
        }

    def restore(self, data: dict[str, Any]) -> None:
        """Rebuild from a snapshot. Restores *questions and evidence* —
        never authority. A restored `APPROVED` entry is a record that the
        founder once said yes; the grant it produced lived in the
        Permission System and is deliberately gone (ADR-0019)."""
        for entry in data.get("approvals", []):
            approval = PendingApproval.from_dict(entry)
            if approval.approval_id in self._approvals:
                continue
            self._approvals[approval.approval_id] = approval
            self._order.append(approval.approval_id)
        for record in data.get("ledger", []):
            self._ledger.append(ApprovalRecord.from_dict(record))
