"""Consequence — the four questions every request for judgment answers.

VEDA 01 §5 Approvals:

> *"Every request for judgment answers four questions before asking for a
> verdict: **what changes, what it costs, what happens if you do nothing,
> and whether it can be undone.** A request missing any of the four is not
> a request; it is a guess dressed as one, and it does not ship."*

VEDA 04 B1 states the same four and adds the invariant: *"a judgment
request missing any field cannot be emitted. This is a schema-level gate,
not a UI concern — enforce it where requests are constructed, or it will
be worked around."*

This module is that gate. All four fields are mandatory and none has a
default, so a partial quartet is not constructible — VEDA 04's contract
says the engine *"returns an error, never a partial."*

## When it exists

**Before a decision, never after one.** The quartet is computed for a
judgment request and shown to the founder while the action is still
hypothetical. *"What happens if you do nothing?"* is a question that only
has meaning at that moment; after execution it has no answer.

This is what separates it from the `Receipt`, which records what actually
happened. The two never overlap and never reference each other. The one
future component that reads both is the Mistake Protocol (VEDA 04 D3),
which compares what was predicted against what occurred — and that
comparison is only possible because they are separate objects.

## An action can execute without one

A quartet is built for an **escalation**. An action firing under a standing
rule is never escalated, so no quartet is ever computed — yet it still
writes a receipt. Requiring one would make every auto-handled action
escalate, which inverts the product.

## Why money is a Decimal and never a float

VEDA 04 R3 rates cumulative accounting over money as high severity and says
to *"treat as ledger arithmetic; never approximate."* VEDA 01 §5 requires
that swept approvals show an aggregate — *"nine small approvals hide a
total that one large one would not"* — so costs must sum exactly. Binary
floating point cannot represent ₹0.10, and a total that drifts is a total
the founder cannot rely on.

## Dependency direction

```
   Consequence  →  ReversibilityClass  (vocabulary only, from warrant.py)

   Warrant       →  Consequence?   optional, pending B1 (Kernel Spec §14.1)
   Judgment req  →  Consequence    mandatory (VEDA 04 B1) — future component
   Receipt       →  (nothing)      the two never touch
```

Nothing here references a Warrant, a Receipt, an Execution Context or a
Clock. The thing that *has* a consequence holds it; the consequence knows
nothing about what it describes, which is what keeps it independently
testable and free of any cycle.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any

from master_agent.foundation.warrant import ReversibilityClass


class CostBasis(str, Enum):
    """Why a cost is the number it is — or why it is not a number.

    The three are distinguishable on purpose. Ranking (VEDA 03:
    `irreversibility × log(exposure) × deadline_proximity × novelty`) must
    treat *"this is free"* and *"I cannot price this"* differently: the
    first is a low-exposure fact, the second is uncertainty, and collapsing
    them into a missing amount would hide the difference exactly where it
    matters.

    VEDA 01 §8 requires the same distinction in language — *I don't know*
    is not *I haven't checked* — and this is that distinction in data.
    """

    #: An amount and a currency are present.
    PRICED = "priced"

    #: Explicitly nothing. Not unknown — known to be zero.
    FREE = "free"

    #: Cannot be determined, and the description says why. Honest
    #: uncertainty, never a silent zero.
    UNPRICEABLE = "unpriceable"


class InvalidConsequence(ValueError):
    """Raised at construction for a quartet that could not be shown to the
    founder.

    VEDA 04 B1 is explicit that the gate belongs where requests are
    constructed *"or it will be worked around"*. There is no validate()
    step a caller can skip.
    """


@dataclass(frozen=True)
class Cost:
    """What an action costs, stated so it can be both read and summed.

    `description` is always required and is what the founder actually
    reads. `amount` exists so costs can be aggregated and ranked; it is
    absent whenever the basis is not `PRICED`.
    """

    #: In the founder's terms. For an unpriceable cost this is where the
    #: reason lives — *"depends on how long the migration runs"* — because
    #: an unexplained blank is indistinguishable from an oversight.
    description: str

    basis: CostBasis

    #: Exact, never a float. Present only when `basis` is `PRICED`.
    amount: Decimal | None = None

    #: Accompanies `amount` and never appears without it.
    currency: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.description, str) or not self.description.strip():
            raise InvalidConsequence(
                "cost description is required; a blank cost is "
                "indistinguishable from an unanswered one"
            )
        if not isinstance(self.basis, CostBasis):
            raise InvalidConsequence("cost basis must be a CostBasis")

        if self.basis is CostBasis.PRICED:
            if self.amount is None or self.currency is None:
                raise InvalidConsequence(
                    "a priced cost requires both an amount and a currency"
                )
            if not isinstance(self.amount, Decimal):
                raise InvalidConsequence(
                    "amount must be a Decimal; binary floats cannot represent "
                    "a currency exactly and a total that drifts is a total the "
                    "founder cannot rely on"
                )
            if self.amount < 0:
                raise InvalidConsequence("amount must not be negative")
            if not self.currency.strip():
                raise InvalidConsequence("currency must be a non-empty code")
        elif self.amount is not None or self.currency is not None:
            raise InvalidConsequence(
                f"a {self.basis.value!r} cost carries no amount or currency; "
                "state the reason in the description instead"
            )

    @property
    def is_priced(self) -> bool:
        return self.basis is CostBasis.PRICED

    def as_dict(self) -> dict[str, Any]:
        """Deterministic projection. `amount` renders as a string so no
        precision is lost crossing JSON, where every number is a float."""
        return {
            "description": self.description,
            "basis": self.basis.value,
            "amount": None if self.amount is None else str(self.amount),
            "currency": self.currency,
        }


@dataclass(frozen=True)
class Consequence:
    """The four mandatory fields of a judgment request.

    Immutable and hashable. A quartet is what the founder was shown when
    they decided; editing it afterwards would restate the basis of a
    decision already made.

    No field has a default. VEDA 04's contract — *"returns an error, never
    a partial"* — means a caller cannot accidentally omit one and discover
    it at render time.
    """

    #: What changes. The effect on the world, in the founder's terms.
    what_changes: str

    #: What it costs.
    cost: Cost

    #: What happens if you do nothing. The question that makes silence a
    #: decision rather than a debt, and the one that has no answer once the
    #: action has already run.
    if_nothing: str

    #: Whether it can be undone. Shares the vocabulary the Warrant uses, so
    #: there is one ordering of consequence in the system rather than two.
    reversibility: ReversibilityClass

    def __post_init__(self) -> None:
        for name in ("what_changes", "if_nothing"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise InvalidConsequence(
                    f"{name} is required; a request missing any of the four "
                    "is not a request (VEDA 01 §5)"
                )

        if not isinstance(self.cost, Cost):
            raise InvalidConsequence("cost must be a Cost")
        if not isinstance(self.reversibility, ReversibilityClass):
            raise InvalidConsequence("reversibility must be a ReversibilityClass")

    @property
    def is_irreversible(self) -> bool:
        """Whether this can never be undone.

        A fact, not a policy. What follows from it — that irreversible items
        are never batched (VEDA 01 §5) and never routed to a batchable tier
        (VEDA 04 B3) — is decided by the router, not here.
        """
        return self.reversibility is ReversibilityClass.IRREVERSIBLE

    def as_dict(self) -> dict[str, Any]:
        """A deterministic, JSON-ready projection.

        Fixed key order and no floats. Equal quartets always produce
        identical dictionaries, which is what lets Provenance (VEDA 04 E1)
        show a founder years later exactly what they were shown at the
        moment they decided.
        """
        return {
            "what_changes": self.what_changes,
            "cost": self.cost.as_dict(),
            "if_nothing": self.if_nothing,
            "reversibility": self.reversibility.value,
        }
