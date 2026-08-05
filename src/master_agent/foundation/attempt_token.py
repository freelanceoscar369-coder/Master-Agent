"""Attempt Token — permission to open one attempt against a live warrant.

Constitutional Kernel Specification §3.5:

```
  attempt(intent_id) → AttemptToken | Refusal
      Open one attempt against a live intent. Refuses when expired,
      cancelled, settled, or out of attempt budget. (§8)
```

## What it is for

§8.6 states the token's whole purpose:

> *"VEDA 04 §7 requires every action to be idempotent against its intent
> record. **The Kernel provides the key — `(intent_id, attempt_seq)`** — and
> requires Workers to honour it where the underlying operation permits."*

This value **is** that key, plus the moment the attempt opened. One
warrant authorizes one logical action; each attempt against it gets one
token, numbered.

## What it deliberately cannot do

**It cannot say whether the attempt was allowed.** The Kernel decides that
before minting a token — §3.5 refuses when the warrant is *"expired,
cancelled, settled, or out of attempt budget."* By the time a token
exists, every one of those questions has been answered.

So this value carries **no budget, no ceiling, no expiry and no warrant
object**. Each would let a holder re-derive a decision the Kernel already
made, and §8.5 is explicit that the budget is *"set at mint from the
capability's class, never by the retry loop."* A token that knew its own
budget is a retry loop one field away from enforcing its own policy.

**It also cannot say whether a retry is permitted.** §8.4 — *"an action
classified `irreversible` is never automatically retried. Ever."* That is
the Reversibility Registry's classification and the Kernel's refusal, and
this value has no access to either. A `may_retry` flag here would place
the most important clause in §8 inside the thing being retried.

## Attempts are counted, not retried

`attempt_seq` starts at **1** and there is no zero. §8.5 sets an
`irreversible` budget of exactly 1, which means one attempt and no second
— unambiguous in a way *"0 retries"* is not. This is the same discipline
`Warrant.attempt_budget` records, and it is why a sequence of 0 is refused
at construction rather than tolerated.

## Naming

`warrant_id`, following Roadmap v2 §2 C10 and the shipped `Warrant` and
`ExecutionContext`, both of which name the field `warrant_id`. The Kernel
Specification writes `intent_id` for the same value; Objective Engine
Specification §13.1 records that they are one identifier under two names.
Nothing new is decided here — this module follows the shipped precedent.

## Dependencies

**None.** Not the Warrant — §3.5's operation takes an id, and Roadmap
Amendment 001 M4 corrects the roadmap's declared dependency to *"nothing.
Not even the Clock."* `opened_at` is supplied by the caller from the
canonical clock, exactly as `Warrant.issued_at` and
`Attestation.attested_at` are.

This module imports nothing from `master_agent` at all.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

#: The first attempt's sequence number. There is no attempt zero — §8.5's
#: `irreversible` budget of 1 means one attempt and no second.
FIRST_ATTEMPT = 1


class InvalidAttemptToken(ValueError):
    """Raised at construction for a token that could not authorize an attempt.

    At construction, never at use. A Worker holding a token treats it as
    settled fact — §8.6 makes it the idempotency key — so one that should
    not exist must not be constructible.
    """


@dataclass(frozen=True)
class AttemptToken:
    """One attempt against one warrant. Immutable and hashable.

    Two tokens with identical fields are the same attempt, which is what
    makes `(warrant_id, attempt_seq)` usable as an idempotency key: a
    Worker that sees the pair twice has seen one attempt twice, not two.
    """

    #: The warrant this attempt runs under. The Kernel has already
    #: confirmed it is live; this value never re-checks it.
    warrant_id: str

    #: Which attempt this is, starting at 1. Monotonic per warrant, and
    #: bounded by the warrant's `attempt_budget` — a bound this value does
    #: not carry and cannot enforce.
    attempt_seq: int

    #: When the attempt opened. Supplied from the canonical clock; this
    #: module never reads one.
    opened_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.warrant_id, str) or not self.warrant_id.strip():
            raise InvalidAttemptToken("warrant_id must be a non-empty identifier")

        # `bool` is a subclass of `int`, so `True` would otherwise pass as
        # attempt 1. An attempt numbered `True` is a caller error, not a
        # first attempt.
        if isinstance(self.attempt_seq, bool) or not isinstance(
            self.attempt_seq, int
        ):
            raise InvalidAttemptToken("attempt_seq must be an integer")

        if self.attempt_seq < FIRST_ATTEMPT:
            raise InvalidAttemptToken(
                f"attempt_seq starts at {FIRST_ATTEMPT}; there is no attempt "
                "zero, because a budget of 1 means one attempt and no second "
                "(Kernel Specification §8.5)"
            )

        if not isinstance(self.opened_at, datetime):
            raise InvalidAttemptToken("opened_at must be a datetime")
        if self.opened_at.tzinfo is None:
            raise InvalidAttemptToken(
                "opened_at must be timezone-aware; every moment in "
                "Kalpavriksha comes from the canonical clock and is aware"
            )
        object.__setattr__(self, "opened_at", self.opened_at.astimezone(UTC))

    # ---- reading ------------------------------------------------------

    @property
    def idempotency_key(self) -> tuple[str, int]:
        """The key §8.6 requires Workers to honour.

        *"The Kernel provides the key — `(intent_id, attempt_seq)`."* The
        moment is deliberately not part of it: two attempts opened at the
        same instant are still two attempts, and one attempt retried by a
        Worker is still one attempt however long it takes.
        """
        return (self.warrant_id, self.attempt_seq)

    @property
    def is_first_attempt(self) -> bool:
        """Whether this is the only attempt an `irreversible` action gets.

        A fact, not a policy. What follows from it — §8.4's rule that an
        irreversible action is never automatically retried — is decided by
        the Kernel against the Reversibility Registry's classification,
        neither of which this value can see.
        """
        return self.attempt_seq == FIRST_ATTEMPT

    def as_dict(self) -> dict[str, Any]:
        """A deterministic, JSON-ready projection.

        Fixed key order, ISO-8601 UTC timestamp. Equal tokens always
        produce identical dictionaries, so an attempt record written today
        is comparable to one written years later.
        """
        return {
            "warrant_id": self.warrant_id,
            "attempt_seq": self.attempt_seq,
            "opened_at": self.opened_at.isoformat(),
        }
