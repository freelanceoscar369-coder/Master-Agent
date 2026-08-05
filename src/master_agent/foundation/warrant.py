"""Warrant — the proof that one execution was authorized.

A `Warrant` is what the Constitutional Kernel mints when every check has
passed and the receipt intent has been written. It is the instrument
without which nothing executes.

It is **evidence of** authorization, never the **act of** authorizing. The
Permission System decides; the Kernel checks and mints; this records what
was decided. Nothing on this object performs, permits, or re-evaluates
anything — it answers questions and holds no state.

## Why it holds ids and not objects

`objective_id`, `principal_id`, `grant_ref` and `rule_ref` are opaque
strings on purpose. Each names something owned elsewhere — the Objective
Engine, the Principal registry, the Permission System, the Rule Engine —
and holding the id rather than the object keeps each single source of
truth single. It is also why this module imports nothing from
`master_agent` at all: a warrant is a flat, self-contained record, which
is what makes it deterministic to serialise and safe to keep forever.

`rule_ref` in particular is **opaque here and stays opaque**: per the
Kernel Specification, the Trust Spine never resolves a rule reference, or
the layer everything is verified against would acquire a dependency on the
layer above it.

## Three invariants that are constitutional, not defensive

**An action may not exceed its objective's ceiling.**
`reversibility_class` is what this action *is*; `consequence_ceiling` is
the limit the founder approved for the objective. Recording both is what
makes the Kernel's envelope check auditable after the fact rather than
only at the moment it ran.

**An irreversible action gets exactly one attempt.**
Kernel Specification §8.4: *"An action classified irreversible is never
automatically retried. Ever."* A timed-out payment may have succeeded, and
retrying is potentially doing it twice. A warrant that permitted a second
attempt would make that rule advisory.

**No rule ever grants irreversible authority.**
VEDA 01 §10 Ethics 3: *"It never acts irreversibly without explicit,
contemporaneous permission. No rule, however broad, ever grants
irreversible authority."* So an irreversible warrant carries a
`grant_ref` and no `rule_ref`, and one that carried both would be a rule
firing irreversibly.

## What is deliberately absent

**No `execution_context_id`.** The Component 3 brief lists one as a
candidate field; it cannot exist. `ExecutionContext` (Component 2,
`kalpavriksha-s1-c2.0`) carries `warrant_id`, because a context describes
one execution and execution happens *after* authorization. A warrant
pointing back at a context would be circular, and would reference
something that does not exist at the moment the warrant is minted. The
dependency runs one way: **Warrant → (nothing). ExecutionContext →
Warrant.**

**No attempt counter, no status, no result.** Those are runtime state and
belong to the receipt records the Kernel writes — `AttemptRecord`,
`OutcomeRecord`. A warrant that knew how many attempts had been used would
be a mutable object wearing a frozen decorator.

**No `sequence`, `deadline`, `decision_ref`, `attestations`, or
`consequence` quartet.** All are named in the Kernel Specification §4.3
and all are additive: each arrives with the component that produces it,
and none changes the shape of what is here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class ReversibilityClass(str, Enum):
    """How far an action can be walked back.

    Ordered by consequence, least to worst. The ordering is the point:
    *"does this action exceed what the founder approved?"* is a comparison,
    and a set of unordered labels cannot answer it.

    `REVERSIBLE_UNTIL` sits between the other two because it *becomes*
    irreversible when its window closes — it is reversible in the way a
    sent-but-recallable message is, which is to say temporarily.

    **The vocabulary is closed.** VEDA 04 A2 requires the registry to fail
    closed on anything unclassified, and an open enum is where a
    `probably_reversible` eventually appears.
    """

    READ_ONLY = "read_only"
    REVERSIBLE = "reversible"
    REVERSIBLE_UNTIL = "reversible_until"
    IRREVERSIBLE = "irreversible"

    @property
    def severity(self) -> int:
        """Position in the consequence ordering. Higher is worse."""
        return _SEVERITY[self]

    def exceeds(self, ceiling: ReversibilityClass) -> bool:
        """Whether this class is worse than a stated limit."""
        return self.severity > ceiling.severity


_SEVERITY: dict[ReversibilityClass, int] = {
    ReversibilityClass.READ_ONLY: 0,
    ReversibilityClass.REVERSIBLE: 1,
    ReversibilityClass.REVERSIBLE_UNTIL: 2,
    ReversibilityClass.IRREVERSIBLE: 3,
}


class InvalidWarrant(ValueError):
    """Raised at construction for a warrant that could not be constitutional.

    At construction, never at use: a warrant is the thing every later check
    trusts, so one that should not exist must not be constructible. There
    is no validation step a caller can forget to call.
    """


@dataclass(frozen=True)
class Warrant:
    """Authorization for exactly one constitutional execution lifecycle.

    Immutable and hashable. Two warrants with identical fields are the same
    warrant, and a warrant's fields never change — an authorization that
    could be edited after the fact would make every receipt anchored to it
    unfalsifiable.
    """

    #: This warrant's identity. The same value VEDA 04 A1's
    #: `recordIntent()` returns as `intentId` — one event, one identifier.
    #: Named `warrant_id` to match `ExecutionContext.warrant_id`, shipped in
    #: Component 2.
    warrant_id: str

    #: The Objective this execution advances. The Kernel's K1 anchor.
    objective_id: str

    #: The founder or delegate on whose authority this runs. Never the
    #: system — see `foundation.principal`.
    principal_id: str

    #: What is authorized, qualified, e.g. `Filesystem.DeleteFolder`. A
    #: warrant that did not name a capability would permit everything.
    capability: str

    #: Content hash of the payload — the digest, never the payload. A
    #: warrant is permanent and payloads carry founder data.
    payload_digest: str

    #: What this action is.
    reversibility_class: ReversibilityClass

    #: The limit the founder approved for the objective. This action may
    #: not exceed it.
    consequence_ceiling: ReversibilityClass

    #: Attempts authorized, set at mint and never by a retry loop. Counts
    #: attempts, not retries: a budget of 1 means one attempt and no
    #: second, which is unambiguous in a way "0 retries" is not.
    attempt_budget: int

    #: Validity window. Both timezone-aware; normalised to UTC on
    #: construction so equality and serialisation do not depend on the
    #: caller's zone.
    issued_at: datetime
    expires_at: datetime

    #: The permission that satisfied this, if it was granted
    #: contemporaneously.
    grant_ref: str | None = None

    #: The standing rule this fired under, if any. Opaque — nothing here
    #: resolves it.
    rule_ref: str | None = None

    # ---- construction-time invariants --------------------------------

    def __post_init__(self) -> None:
        for name in (
            "warrant_id",
            "objective_id",
            "principal_id",
            "capability",
            "payload_digest",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise InvalidWarrant(f"{name} must be a non-empty identifier")

        for name in ("reversibility_class", "consequence_ceiling"):
            if not isinstance(getattr(self, name), ReversibilityClass):
                raise InvalidWarrant(f"{name} must be a ReversibilityClass")

        object.__setattr__(self, "issued_at", _as_utc(self.issued_at, "issued_at"))
        object.__setattr__(self, "expires_at", _as_utc(self.expires_at, "expires_at"))

        if self.expires_at <= self.issued_at:
            raise InvalidWarrant(
                "expires_at must be after issued_at; a warrant that is "
                "expired at birth authorizes nothing"
            )

        if not isinstance(self.attempt_budget, int) or isinstance(
            self.attempt_budget, bool
        ):
            raise InvalidWarrant("attempt_budget must be an int")
        if self.attempt_budget < 1:
            raise InvalidWarrant(
                "attempt_budget must be at least 1; a warrant permitting no "
                "attempt is not an authorization"
            )

        if self.reversibility_class.exceeds(self.consequence_ceiling):
            raise InvalidWarrant(
                f"a {self.reversibility_class.value!r} action exceeds this "
                f"objective's {self.consequence_ceiling.value!r} ceiling; the "
                "founder approved a limit and this is past it"
            )

        if self.reversibility_class is ReversibilityClass.IRREVERSIBLE:
            if self.attempt_budget != 1:
                raise InvalidWarrant(
                    "an irreversible action is never automatically retried "
                    "(Kernel Specification §8.4); attempt_budget must be 1"
                )
            if self.rule_ref is not None:
                raise InvalidWarrant(
                    "no rule, however broad, ever grants irreversible "
                    "authority (VEDA 01 §10 Ethics 3); an irreversible "
                    "warrant requires contemporaneous permission"
                )

    # ---- immutable helpers -------------------------------------------

    def is_expired(self, at: datetime) -> bool:
        """Whether this warrant has lapsed at a given moment.

        Takes the moment rather than a `Clock`, so a warrant remains a pure
        value with no dependencies. The caller reads the canonical clock
        once and passes what it said.
        """
        return _as_utc(at, "at") >= self.expires_at

    def matches(self, capability: str, payload_digest: str) -> bool:
        """Whether this warrant covers a given call.

        A comparison, not a decision: it reports whether the capability and
        payload are the ones authorized. Presenting a warrant for anything
        else is how an authorization for a harmless action gets redirected
        to a harmful one.
        """
        return self.capability == capability and self.payload_digest == payload_digest

    @property
    def fired_under_rule(self) -> bool:
        """Whether a standing rule authorized this, rather than the founder
        answering in the moment."""
        return self.rule_ref is not None

    @property
    def is_irreversible(self) -> bool:
        return self.reversibility_class is ReversibilityClass.IRREVERSIBLE

    def as_dict(self) -> dict[str, Any]:
        """A deterministic, JSON-ready projection.

        Fixed key order, ISO-8601 UTC timestamps, enum values as strings.
        Equal warrants always produce identical dictionaries, and the same
        warrant produces an identical dictionary every time — which is what
        lets a receipt written today be compared to one written in five
        years.
        """
        return {
            "warrant_id": self.warrant_id,
            "objective_id": self.objective_id,
            "principal_id": self.principal_id,
            "capability": self.capability,
            "payload_digest": self.payload_digest,
            "reversibility_class": self.reversibility_class.value,
            "consequence_ceiling": self.consequence_ceiling.value,
            "attempt_budget": self.attempt_budget,
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "grant_ref": self.grant_ref,
            "rule_ref": self.rule_ref,
        }


def _as_utc(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise InvalidWarrant(f"{field_name} must be a datetime")
    if value.tzinfo is None:
        raise InvalidWarrant(
            f"{field_name} must be timezone-aware; every moment in "
            "Kalpavriksha comes from the canonical clock and is aware"
        )
    return value.astimezone(UTC)
