"""Receipt Ledger — the append-only store nothing executes without.

VEDA 04 A1, verbatim, and the reason this component exists:

> *"if the intent write fails, the action does not occur. **No exceptions,
> no buffering, no fire-and-forget.**"*

Kernel Specification §7.2 K3 states the Kernel's half: the receipt intent
write *"runs last, after every other check has passed. If the write fails,
the Kernel refuses and **nothing executes**."*

## It records. It never decides.

The ledger evaluates nothing, authorizes nothing, retries nothing, and
mutates nothing. It has no `update` and no `delete` **at any privilege
level** — not a private one, not a test hook. The append-only property is
not a policy this module follows; it is the only behaviour it has.

`record_intent()` returns the identifier it was given. It does not mint
one: the Kernel mints the warrant, and §9.2's rule is *"every arrow is an
identifier, never a copy."* Echoing is recording; minting would be
deciding.

## Three record types, and the shapes §9.1 fixes

```
   IntentRecord ──┬── AttemptRecord (0..n)
                  └── OutcomeRecord (0..1, terminal)
```

The outcome record **is** the shipped `Receipt` (C5). That is why Roadmap
Amendment 001 M1 lists C5 among this component's dependencies — there is
no second outcome type, and building one would be a second description of
one event.

`CompensationRecord`, §9.1's fourth type, is **not** implemented here.
Roadmap §2 C13's declared surface is `record_intent / record_attempt /
record_outcome / read`, and adding a fourth writer would exceed it. The
gap is recorded rather than filled.

## The consequence is never null

Kernel Specification §14.1 and Amendment 001 M1's note for this component:
an intent record written in Sprint 1 carries the explicit marker
`pending_consequence_engine` — **never null, never omitted, never a
partial quartet** — because B1, the Consequence Engine, is Sprint 2. The
type makes the alternative unconstructable.

## Fail closed, and loudly

§11.3: *"An in-memory queue of pending receipts 'until the ledger
recovers' is exactly the fire-and-forget A1 forbids, and it fails
precisely when it matters — a crash loses the queue and the actions
already happened."*

So there is no buffer, no batch, no background writer and no retry. Every
write reaches the store synchronously and either returns or raises
`LedgerUnavailable`. A caller that catches it must refuse the action; that
is K3.

## Referential integrity is not a decision

An attempt or an outcome for a warrant with no recorded intent is refused,
and so is an attempt recorded after the outcome that §9.1 marks terminal.
Neither is the ledger judging the action — both are the linkage graph in
§9.2 being true rather than aspirational. An orphaned outcome is the
condition §9.5 calls a reconciliation gap, and it is cheaper to make it
unwritable than to detect it later.

## Storage

A `StateStore` (shipped, `persistence.store`) supplied by the caller. Its
`append_events()` flushes and `fsync()`s before returning, which is what
makes a synchronous write honest rather than merely blocking.

This module never opens a file. `persistence` is *"the only place in
Kalpavriksha that reads or writes persistence files"*, and that stays
true.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from master_agent.foundation.consequence import (
    Consequence,
    Cost,
    CostBasis,
)
from master_agent.foundation.execution_request import (
    PENDING_CONSEQUENCE_ENGINE,
    PendingConsequenceEngine,
)
from master_agent.foundation.receipt import ExecutionOutcome, Receipt
from master_agent.foundation.warrant import ReversibilityClass
from master_agent.persistence.store import StateStore


class RecordKind(str, Enum):
    """The record types §9.1 fixes, as they appear on the wire.

    Closed. A fourth kind is a change to the ledger's shape, which is a
    constitutional decision rather than a code change.
    """

    INTENT = "intent"
    ATTEMPT = "attempt"
    OUTCOME = "outcome"


class InvalidLedgerRecord(ValueError):
    """Raised at construction for a record that could not be evidence."""


class LedgerUnavailable(RuntimeError):
    """The write did not reach the store.

    **This is the fail-closed signal.** §11.3 — the ledger is a hard
    dependency of all execution, and a caller that sees this must refuse
    the action. It is deliberately not a `ValueError`: a caller wrapping
    construction in `except ValueError` must never absorb a storage
    failure by accident.
    """


class LedgerIntegrityError(LedgerUnavailable):
    """The write would have broken §9.1's shape or §9.2's linkage.

    A subclass of `LedgerUnavailable` so that **every** refusal to write is
    caught by one `except`. A caller must not be able to handle "the disk
    is gone" and accidentally proceed past "this outcome has no intent".
    """


@dataclass(frozen=True)
class IntentRecord:
    """The first phase of A1's contract. Immutable.

    VEDA 04 A1: *"Intent carries actor, rule (if any), reversibility class,
    expected effect, and the consequence quartet."* Every one of those is
    a field below; nothing else is.
    """

    #: The warrant this intent authorizes. A1 calls the returned value
    #: `intentId`; the shipped `Warrant`, `ExecutionContext`, `Receipt` and
    #: `AttemptToken` all name it `warrant_id`, and this follows them.
    warrant_id: str

    #: The constitutional anchor. K1 refuses without one.
    objective_id: str

    #: A1's *actor* — the founder or delegate on whose authority this runs.
    principal_id: str

    #: A1's *actionType*, qualified.
    capability: str

    #: What this action does to the world. C4's vocabulary.
    reversibility_class: ReversibilityClass

    #: What the world should look like afterwards, in the caller's terms.
    expected_effect: str

    #: The quartet, or §14.1's marker. **Never `None`.**
    consequence: Consequence | PendingConsequenceEngine

    #: When the intent was recorded. From the canonical clock.
    recorded_at: datetime

    #: The standing rule this fired under, if any. **Opaque** — nothing
    #: here resolves it (§4.3).
    rule_ref: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "warrant_id",
            "objective_id",
            "principal_id",
            "capability",
            "expected_effect",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise InvalidLedgerRecord(f"{name} must be a non-empty value")

        if not isinstance(self.reversibility_class, ReversibilityClass):
            raise InvalidLedgerRecord(
                "reversibility_class must be a ReversibilityClass"
            )

        if not isinstance(
            self.consequence, (Consequence, PendingConsequenceEngine)
        ):
            raise InvalidLedgerRecord(
                "consequence must be a Consequence or "
                "PENDING_CONSEQUENCE_ENGINE; it is never null, never omitted "
                "and never a partial quartet (Kernel Specification §14.1)"
            )

        if self.rule_ref is not None and (
            not isinstance(self.rule_ref, str) or not self.rule_ref.strip()
        ):
            raise InvalidLedgerRecord(
                "rule_ref is absent or a reference, never blank"
            )

        object.__setattr__(
            self, "recorded_at", _as_utc(self.recorded_at, "recorded_at")
        )

    def as_dict(self) -> dict[str, Any]:
        """Deterministic, JSON-ready. Fixed key order."""
        return {
            "kind": RecordKind.INTENT.value,
            "warrant_id": self.warrant_id,
            "objective_id": self.objective_id,
            "principal_id": self.principal_id,
            "capability": self.capability,
            "reversibility_class": self.reversibility_class.value,
            "expected_effect": self.expected_effect,
            "consequence": self.consequence.as_dict(),
            "recorded_at": self.recorded_at.isoformat(),
            "rule_ref": self.rule_ref,
        }


@dataclass(frozen=True)
class AttemptRecord:
    """One attempt opened against a warrant. Immutable.

    Carries §8.6's idempotency key — `(warrant_id, attempt_seq)` — as two
    flat identifiers rather than an `AttemptToken`, per §9.2: *"every arrow
    is an identifier, never a copy."*
    """

    warrant_id: str

    #: 1-based, matching `Receipt.attempt` and `AttemptToken.attempt_seq`.
    attempt_seq: int

    recorded_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.warrant_id, str) or not self.warrant_id.strip():
            raise InvalidLedgerRecord("warrant_id must be a non-empty value")

        if isinstance(self.attempt_seq, bool) or not isinstance(
            self.attempt_seq, int
        ):
            raise InvalidLedgerRecord("attempt_seq must be an integer")
        if self.attempt_seq < 1:
            raise InvalidLedgerRecord(
                "attempt_seq is 1-based; there is no attempt zero to record"
            )

        object.__setattr__(
            self, "recorded_at", _as_utc(self.recorded_at, "recorded_at")
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": RecordKind.ATTEMPT.value,
            "warrant_id": self.warrant_id,
            "attempt_seq": self.attempt_seq,
            "recorded_at": self.recorded_at.isoformat(),
        }


class ReceiptLedger:
    """The append-only store. **No update. No delete. At any privilege level.**

    State is the recorded history, rebuilt from the store at construction
    so a restart sees exactly what a crash left behind.
    """

    __slots__ = ("_attempts", "_entries", "_intents", "_outcomes", "_store")

    def __init__(self, store: StateStore) -> None:
        self._store = store
        self._entries: list[IntentRecord | AttemptRecord | Receipt] = []
        self._intents: set[str] = set()
        self._attempts: set[tuple[str, int]] = set()
        self._outcomes: set[str] = set()
        self._replay()

    # ---- writing ------------------------------------------------------

    def record_intent(self, record: IntentRecord) -> str:
        """A1's first phase. Returns the identifier it was given.

        Refuses a second intent for one warrant: §9.1's graph roots each
        tree at exactly one intent, and two would make the tree ambiguous.
        """
        if not isinstance(record, IntentRecord):
            raise InvalidLedgerRecord("record_intent expects an IntentRecord")
        if record.warrant_id in self._intents:
            raise LedgerIntegrityError(
                f"{record.warrant_id!r} already has an intent record; an "
                "intent is written once and never rewritten"
            )
        self._append(record)
        self._intents.add(record.warrant_id)
        return record.warrant_id

    def record_attempt(self, record: AttemptRecord) -> None:
        """§9.1's `AttemptRecord (0..n)`.

        Refuses an unknown warrant, a duplicate sequence, and any attempt
        after the outcome — §9.1 marks the outcome **terminal**.
        """
        if not isinstance(record, AttemptRecord):
            raise InvalidLedgerRecord("record_attempt expects an AttemptRecord")
        self._require_intent(record.warrant_id, "attempt")
        if record.warrant_id in self._outcomes:
            raise LedgerIntegrityError(
                f"{record.warrant_id!r} is already settled; the outcome record "
                "is terminal and nothing follows it (§9.1)"
            )
        key = (record.warrant_id, record.attempt_seq)
        if key in self._attempts:
            raise LedgerIntegrityError(
                f"attempt {record.attempt_seq} of {record.warrant_id!r} is "
                "already recorded; the pair is §8.6's idempotency key"
            )
        self._append(record)
        self._attempts.add(key)

    def record_outcome(self, receipt: Receipt) -> None:
        """§9.1's `OutcomeRecord (0..1, terminal)`.

        The outcome record is the shipped `Receipt` (C5). Refuses an
        unknown warrant and a second outcome.
        """
        if not isinstance(receipt, Receipt):
            raise InvalidLedgerRecord("record_outcome expects a Receipt")
        self._require_intent(receipt.warrant_id, "outcome")
        if receipt.warrant_id in self._outcomes:
            raise LedgerIntegrityError(
                f"{receipt.warrant_id!r} already has an outcome record; the "
                "outcome is terminal and written once (§9.1)"
            )
        self._append(receipt)
        self._outcomes.add(receipt.warrant_id)

    # ---- reading ------------------------------------------------------

    def read(
        self, warrant_id: str | None = None
    ) -> tuple[IntentRecord | AttemptRecord | Receipt, ...]:
        """Every record, in the order it was appended.

        Passing a `warrant_id` narrows to one tree of §9.2's graph. The
        tuple is a copy: a reader cannot reach the ledger's own history.
        """
        if warrant_id is None:
            return tuple(self._entries)
        return tuple(e for e in self._entries if e.warrant_id == warrant_id)

    def has_intent(self, warrant_id: str) -> bool:
        """Whether an intent exists. Answers; never asserts."""
        return warrant_id in self._intents

    def is_settled(self, warrant_id: str) -> bool:
        """Whether the terminal outcome record has been written."""
        return warrant_id in self._outcomes

    def __len__(self) -> int:
        return len(self._entries)

    # ---- internals ----------------------------------------------------

    def _require_intent(self, warrant_id: str, what: str) -> None:
        if warrant_id not in self._intents:
            raise LedgerIntegrityError(
                f"no intent record for {warrant_id!r}; an {what} without one "
                "is the reconciliation gap §9.5 exists to make impossible, "
                "and K3 writes the intent before anything executes"
            )

    def _append(self, record: IntentRecord | AttemptRecord | Receipt) -> None:
        """One synchronous write. No buffer, no batch, no retry.

        Any storage failure becomes `LedgerUnavailable` and **nothing is
        added to the in-memory history** — a ledger that remembered a write
        the store rejected would be lying to the next reader.
        """
        try:
            self._store.append_events([_envelope(record)])
        except Exception as exc:
            raise LedgerUnavailable(
                f"the receipt ledger could not write: {exc}"
            ) from exc
        self._entries.append(record)

    def _replay(self) -> None:
        """Rebuild the history from the store, in append order."""
        try:
            events = self._store.read_events()
        except Exception as exc:
            raise LedgerUnavailable(
                f"the receipt ledger could not be read: {exc}"
            ) from exc

        for event in events:
            kind = event.get("kind")
            if kind == RecordKind.INTENT.value:
                record = _intent_from_dict(event)
                self._entries.append(record)
                self._intents.add(record.warrant_id)
            elif kind == RecordKind.ATTEMPT.value:
                record = _attempt_from_dict(event)
                self._entries.append(record)
                self._attempts.add((record.warrant_id, record.attempt_seq))
            elif kind == RecordKind.OUTCOME.value:
                receipt = _receipt_from_dict(event)
                self._entries.append(receipt)
                self._outcomes.add(receipt.warrant_id)


# ---- serialisation ----------------------------------------------------


def _envelope(record: IntentRecord | AttemptRecord | Receipt) -> dict[str, Any]:
    if isinstance(record, Receipt):
        return {"kind": RecordKind.OUTCOME.value, **record.as_dict()}
    return record.as_dict()


def _as_utc(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise InvalidLedgerRecord(f"{field_name} must be a datetime")
    if value.tzinfo is None:
        raise InvalidLedgerRecord(
            f"{field_name} must be timezone-aware; every moment in the ledger "
            "comes from the canonical clock and is aware"
        )
    return value.astimezone(UTC)


def _consequence_from(raw: Any) -> Consequence | PendingConsequenceEngine:
    if raw == PENDING_CONSEQUENCE_ENGINE.as_dict():
        return PENDING_CONSEQUENCE_ENGINE
    cost = raw["cost"]
    amount = cost["amount"]
    return Consequence(
        what_changes=raw["what_changes"],
        cost=Cost(
            description=cost["description"],
            basis=CostBasis(cost["basis"]),
            amount=None if amount is None else Decimal(amount),
            currency=cost["currency"],
        ),
        if_nothing=raw["if_nothing"],
        reversibility=ReversibilityClass(raw["reversibility"]),
    )


def _intent_from_dict(raw: dict[str, Any]) -> IntentRecord:
    return IntentRecord(
        warrant_id=raw["warrant_id"],
        objective_id=raw["objective_id"],
        principal_id=raw["principal_id"],
        capability=raw["capability"],
        reversibility_class=ReversibilityClass(raw["reversibility_class"]),
        expected_effect=raw["expected_effect"],
        consequence=_consequence_from(raw["consequence"]),
        recorded_at=datetime.fromisoformat(raw["recorded_at"]),
        rule_ref=raw["rule_ref"],
    )


def _attempt_from_dict(raw: dict[str, Any]) -> AttemptRecord:
    return AttemptRecord(
        warrant_id=raw["warrant_id"],
        attempt_seq=raw["attempt_seq"],
        recorded_at=datetime.fromisoformat(raw["recorded_at"]),
    )


def _receipt_from_dict(raw: dict[str, Any]) -> Receipt:
    return Receipt(
        receipt_id=raw["receipt_id"],
        objective_id=raw["objective_id"],
        principal_id=raw["principal_id"],
        warrant_id=raw["warrant_id"],
        correlation_id=raw["correlation_id"],
        trace_id=raw["trace_id"],
        capability=raw["capability"],
        attempt=raw["attempt"],
        outcome=ExecutionOutcome(raw["outcome"]),
        started_at=datetime.fromisoformat(raw["started_at"]),
        completed_at=datetime.fromisoformat(raw["completed_at"]),
        compensation_ref=raw["compensation_ref"],
        detail=raw["detail"],
    )
