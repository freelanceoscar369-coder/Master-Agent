"""Receipt — the permanent record of what one execution attempt did.

A Receipt is evidence. It is written after an attempt completes and is
never touched again.

## Where it sits in VEDA 04 A1's two phases

A1 requires *intent record → execute → outcome record*, with the invariant
that a failed intent write aborts the action. Those two phases are two
different objects here:

| Phase | Object | Written |
|---|---|---|
| Intent | `Warrant` (Component 3) | Before execution, by the Kernel |
| Outcome | `Receipt` (this module) | After the attempt completes |

`warrant_id` is the link, and it is the same identifier A1's
`recordIntent()` returns as `intentId` — so the pair is one event recorded
twice, once as permission and once as consequence. **A receipt with no
warrant would be a record of something nobody authorized**, which is why
the field is required and never blank.

## One receipt per attempt

A `Warrant` carries an `attempt_budget`. Each attempt that completes writes
its own receipt, so `attempt` is 1-based and several receipts may share one
`warrant_id`. That is the Kernel Specification's *"one warrant, N attempts,
one outcome"* — the attempt records and the outcome record are merged here
into a single evidence object per attempt, which is what the Component 4
brief specifies.

## What it never does

| Never | Because |
|---|---|
| executes or authorizes | It is written after the fact. It has no method that acts. |
| owns an Objective, Warrant, or Execution Context | It holds their ids. Each is owned elsewhere and stays owned there. |
| mutates | Frozen. Evidence that could be edited is not evidence. |
| holds business logic | Two derived properties and a projection. Nothing decides. |
| references Learning | Learning subscribes to the receipt stream; the stream does not know it exists. |

## Time

Every timestamp is timezone-aware and normalised to UTC on construction.
Nothing here reads a wall clock — the Kernel supplies the moments from the
canonical `Clock`, which is what keeps a receipt reproducible and its
ordering trustworthy.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any


class ExecutionOutcome(str, Enum):
    """What an attempt actually did.

    The four kinds are the Constitutional Kernel Specification §6.3
    settlement kinds, unchanged. The vocabulary is closed: an outcome that
    does not fit one of these is not a fifth kind, it is a caller who has
    not finished deciding what happened.
    """

    #: The effect occurred as expected.
    SUCCEEDED = "succeeded"

    #: The effect did not occur, and this is known.
    FAILED = "failed"

    #: Some effect occurred. **Requires a compensating action reference.**
    #: The most dangerous outcome and the one most often mis-recorded as a
    #: failure — a half-written file is not a file that was not written.
    PARTIAL = "partial"

    #: The caller cannot determine whether the effect occurred. Exists
    #: because pretending otherwise is how a system double-charges a card.
    #: Never auto-retried; escalates.
    UNKNOWN = "unknown"


class InvalidReceipt(ValueError):
    """Raised at construction for a receipt that could not be evidence.

    At construction, never at read time: a receipt is what every later
    audit trusts, so one that should not exist must not be constructible.
    """


@dataclass(frozen=True)
class Receipt:
    """One completed execution attempt, recorded permanently.

    Immutable and hashable. Two receipts with identical fields are the same
    receipt; a receipt's fields never change.
    """

    #: This record's identity.
    receipt_id: str

    #: The Objective this execution advanced. An id — the Objective Engine
    #: remains the single source of truth.
    objective_id: str

    #: The founder or delegate who authorized it. Answers *"which human
    #: authorized this?"*, which is the question the ledger exists for.
    principal_id: str

    #: The Warrant that permitted it. The link to A1's intent phase.
    warrant_id: str

    #: From the Execution Context: the logical unit of work this belonged
    #: to. Several executions share one.
    correlation_id: str

    #: From the Execution Context: **this** execution. Together with
    #: `correlation_id` this identifies the Execution Context exactly —
    #: see ED-006, and `test_it_references_the_execution_context_as_c2_
    #: defines_it`.
    trace_id: str

    #: What ran, qualified, e.g. `Filesystem.WriteFile`.
    capability: str

    #: Which attempt this was, 1-based. Several receipts may share a
    #: `warrant_id` when a warrant's attempt budget is above one.
    attempt: int

    #: What happened.
    outcome: ExecutionOutcome

    #: When it ran. Supplied by the Kernel from the canonical Clock.
    started_at: datetime
    completed_at: datetime

    #: How to undo a partial effect. Required for `PARTIAL` and refused for
    #: every other outcome, so the field cannot quietly become optional.
    compensation_ref: str | None = None

    #: Diagnostic text only — a failure reason, never load-bearing and
    #: never read to make a decision. If something here would change what
    #: the system does, it belongs in a named field or nowhere.
    detail: str | None = None

    # ---- construction-time invariants --------------------------------

    def __post_init__(self) -> None:
        for name in (
            "receipt_id",
            "objective_id",
            "principal_id",
            "warrant_id",
            "correlation_id",
            "trace_id",
            "capability",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise InvalidReceipt(f"{name} must be a non-empty identifier")

        if not isinstance(self.outcome, ExecutionOutcome):
            raise InvalidReceipt("outcome must be an ExecutionOutcome")

        if not isinstance(self.attempt, int) or isinstance(self.attempt, bool):
            raise InvalidReceipt("attempt must be an int")
        if self.attempt < 1:
            raise InvalidReceipt(
                "attempt is 1-based; there is no attempt zero to record"
            )

        object.__setattr__(self, "started_at", _as_utc(self.started_at, "started_at"))
        object.__setattr__(
            self, "completed_at", _as_utc(self.completed_at, "completed_at")
        )
        if self.completed_at < self.started_at:
            raise InvalidReceipt(
                "completed_at precedes started_at; an execution cannot finish "
                "before it began"
            )

        if self.outcome is ExecutionOutcome.PARTIAL:
            if not (self.compensation_ref or "").strip():
                raise InvalidReceipt(
                    "a partial outcome requires a compensating action "
                    "reference (Kernel Specification §6.3); some effect "
                    "occurred and the record must say how to undo it"
                )
        elif self.compensation_ref is not None:
            raise InvalidReceipt(
                f"compensation_ref is only meaningful for a partial outcome, "
                f"not {self.outcome.value!r}"
            )

    # ---- immutable helpers -------------------------------------------

    @property
    def duration(self) -> timedelta:
        """How long the attempt took."""
        return self.completed_at - self.started_at

    @property
    def is_success(self) -> bool:
        return self.outcome is ExecutionOutcome.SUCCEEDED

    @property
    def requires_escalation(self) -> bool:
        """Whether a human must look at this.

        `UNKNOWN` means the caller could not determine whether the effect
        occurred. The constitutionally honest response is to ask, never to
        try again — so this is the one outcome that always escalates
        regardless of any remaining attempt budget.
        """
        return self.outcome is ExecutionOutcome.UNKNOWN

    def as_dict(self) -> dict[str, Any]:
        """A deterministic, JSON-ready projection.

        Fixed key order, ISO-8601 UTC timestamps, enum values as strings.
        Equal receipts always produce identical dictionaries, and the same
        receipt produces an identical dictionary every time — which is what
        lets evidence written today be compared to evidence written in
        fifteen years.
        """
        return {
            "receipt_id": self.receipt_id,
            "objective_id": self.objective_id,
            "principal_id": self.principal_id,
            "warrant_id": self.warrant_id,
            "correlation_id": self.correlation_id,
            "trace_id": self.trace_id,
            "capability": self.capability,
            "attempt": self.attempt,
            "outcome": self.outcome.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "compensation_ref": self.compensation_ref,
            "detail": self.detail,
        }


def _as_utc(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise InvalidReceipt(f"{field_name} must be a datetime")
    if value.tzinfo is None:
        raise InvalidReceipt(
            f"{field_name} must be timezone-aware; every moment in a receipt "
            "comes from the canonical clock and is aware"
        )
    return value.astimezone(UTC)
