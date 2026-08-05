"""Reversibility Registry — what each capability does to the world, and how it is undone.

VEDA 04 A2, verbatim:

> *"A declared classification for every action type in the system:
> reversible / reversible-until-T / irreversible. Each reversible class
> names its **compensating action** and its window. Unclassified action
> types are **non-executable by default** — the registry fails closed."*
>
> **Invariant:** *"'probably reversible' cannot be represented. The type
> system must not permit an unclassified action to reach execution."*

Kernel Specification §7.3 A2 is the same rule from the Kernel's side —
*"Unclassified. Fails closed — no default classification exists."*

## "Classification" means reversibility, and nothing else

The name is generic and the module is not. A `Classification` here answers
one question: **what does this capability do to the world, and how is that
undone.** It says nothing about permission, risk tier, cost, or whether an
invocation is allowed — those belong to the Permission System and the
standing rules, and §3.4 assigns them elsewhere.

## Fail closed, two ways

`classify()` **raises** `Unclassified`. There is no default, no
`.get(capability, REVERSIBLE)`, and no optional return that a caller could
treat as permission. A capability nobody classified is a capability nobody
may run.

`attest()` **refuses**. §7.5 requires refusals to be recorded, so asking
the registry for an attestation over an unclassified capability produces a
`REFUSED` attestation naming why — an answer the Kernel can carry into a
receipt, rather than an exception it must translate.

Both are the same fail-closed posture from two angles: nothing is
classified by omission, and nothing is silently permitted.

## The registry is immutable

`register()` returns a **new** registry rather than mutating this one,
following `PrincipalRegistry` (C2), which takes its entries at
construction and exposes no mutator. A classification that could change
under a holder's feet would mean the class an action was authorized
against is not necessarily the class it executes under — and §8.3 lists
*"reversibility class changing"* as requiring a **new Intent**, not a
silent substitution.

Re-registering a capability is refused for the same reason: overwriting a
classification is how a reversible action becomes irreversible with
nobody noticing.

## What each class must carry

Derived from Kernel Specification §4.3 — `compensating_action` is *"How to
undo, or explicitly `none`"*, `undo_window` is *"Present only for
`reversible_until`"* — and from VEDA 04 A2's requirement that a reversible
class name its compensating action and its window.

| Class | Compensating capability | Undo window |
|---|---|---|
| `READ_ONLY` | refused — nothing happened to undo | refused |
| `REVERSIBLE` | **required** | refused |
| `REVERSIBLE_UNTIL` | **required** | **required**, strictly positive |
| `IRREVERSIBLE` | refused — §8.4, there is no undo | refused |

Every row is enforced at construction. A `REVERSIBLE` classification with
no compensating capability is exactly the *"probably reversible"* VEDA 04
A2 forbids representing, so it cannot be built.

## Dependencies

`ReversibilityClass` from C4 — the shipped vocabulary, reused rather than
restated — and `Attestation` from C7, which this module constructs per
Roadmap Amendment 001 M7. Nothing else. No clock: `attested_at` is passed
in, as everywhere else in `foundation/`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from master_agent.foundation.attestation import (
    Attestation,
    AttestationQuestion,
    AttestationVerdict,
)
from master_agent.foundation.warrant import ReversibilityClass

#: Classes that name how the action is undone. The other two do not,
#: because nothing happened (`READ_ONLY`) or nothing can (`IRREVERSIBLE`).
_COMPENSATED = frozenset(
    {ReversibilityClass.REVERSIBLE, ReversibilityClass.REVERSIBLE_UNTIL}
)


class InvalidClassification(ValueError):
    """Raised at construction for a classification that could not be relied on.

    At construction, never at lookup. The Kernel treats a classification as
    settled fact when it mints, so one that should not exist must not be
    constructible.
    """


class Unclassified(LookupError):
    """Raised when a capability has no declared classification.

    **This is the fail-closed path**, and it is an exception rather than a
    default on purpose. VEDA 04 A2: *"Unclassified action types are
    non-executable by default."* A method that returned `None` here would
    put the decision in the caller's hands, and some caller would
    eventually read it as permission.
    """

    def __init__(self, capability: str) -> None:
        super().__init__(
            f"{capability!r} has no reversibility classification; no default "
            "exists and an unclassified capability may not execute "
            "(VEDA 04 A2)"
        )
        self.capability = capability


@dataclass(frozen=True)
class Classification:
    """One capability's reversibility, and how it is undone.

    Immutable and hashable. Two classifications with identical fields are
    the same classification.
    """

    #: The capability this describes, qualified — e.g.
    #: `Filesystem.DeleteFolder`.
    capability: str

    #: What this capability does to the world. The shipped C4 vocabulary,
    #: so there is one ordering of reversibility in the system rather than
    #: two.
    cls: ReversibilityClass

    #: The capability that undoes it. Required on the compensated classes,
    #: refused on the others. A name, not a callable — the registry knows
    #: *what* undoes an action, never *how* to run it.
    compensating_capability: str | None = None

    #: How long the undo remains available. Present only for
    #: `REVERSIBLE_UNTIL` (§4.3), and §8.5 notes it is **not extended by
    #: retrying**.
    undo_window: timedelta | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.capability, str) or not self.capability.strip():
            raise InvalidClassification("capability must be a non-empty name")

        if not isinstance(self.cls, ReversibilityClass):
            raise InvalidClassification("cls must be a ReversibilityClass")

        self._validate_compensating_capability()
        self._validate_undo_window()

    def _validate_compensating_capability(self) -> None:
        needs_one = self.cls in _COMPENSATED
        given = self.compensating_capability

        if needs_one:
            if not isinstance(given, str) or not given.strip():
                raise InvalidClassification(
                    f"{self.cls.value!r} must name its compensating "
                    "capability; a reversible action that cannot say how it "
                    "is undone is the 'probably reversible' VEDA 04 A2 "
                    "forbids representing"
                )
            return

        if given is not None:
            raise InvalidClassification(
                f"{self.cls.value!r} has no compensating capability: nothing "
                "happened to undo, or nothing can undo it (§8.4)"
            )

    def _validate_undo_window(self) -> None:
        window = self.undo_window
        timed = self.cls is ReversibilityClass.REVERSIBLE_UNTIL

        if timed:
            if not isinstance(window, timedelta):
                raise InvalidClassification(
                    "'reversible_until' must name the window it is reversible "
                    "until; without one it is indistinguishable from "
                    "'reversible'"
                )
            if window <= timedelta(0):
                raise InvalidClassification(
                    "undo_window must be positive; a window of zero or less "
                    "is an irreversible action wearing a reversible name"
                )
            return

        if window is not None:
            raise InvalidClassification(
                "undo_window is present only for 'reversible_until' "
                "(Kernel Specification §4.3)"
            )

    # ---- reading ------------------------------------------------------

    @property
    def is_irreversible(self) -> bool:
        """A fact, not a policy.

        What follows from it — §8.4's rule that an irreversible action is
        never automatically retried, and A3's requirement of contemporaneous
        approval — is decided by the Kernel and the Permission System.
        """
        return self.cls is ReversibilityClass.IRREVERSIBLE

    def as_dict(self) -> dict[str, Any]:
        """A deterministic, JSON-ready projection.

        Fixed key order; the window as whole seconds, so a record written
        today reads identically years later without a duration parser.
        """
        return {
            "capability": self.capability,
            "cls": self.cls.value,
            "compensating_capability": self.compensating_capability,
            "undo_window_seconds": (
                None if self.undo_window is None
                else int(self.undo_window.total_seconds())
            ),
        }


class ReversibilityRegistry:
    """The declared classification of every capability in the system.

    Immutable: `register()` returns a new registry. Follows
    `PrincipalRegistry` (C2), which likewise takes its entries at
    construction and exposes no mutator.

    **An empty registry is valid and classifies nothing.** That is the
    correct starting state, not a defect: every capability is
    non-executable until it is declared, which is what failing closed
    means.
    """

    __slots__ = ("_by_capability",)

    def __init__(self, classifications: tuple[Classification, ...] = ()) -> None:
        by_capability: dict[str, Classification] = {}
        for item in classifications:
            if not isinstance(item, Classification):
                raise InvalidClassification(
                    "every entry must be a Classification"
                )
            if item.capability in by_capability:
                raise InvalidClassification(
                    f"{item.capability!r} is classified twice; a capability "
                    "with two classifications is one the Kernel cannot mint "
                    "against"
                )
            by_capability[item.capability] = item
        object.__setattr__(self, "_by_capability", by_capability)

    # ---- building -----------------------------------------------------

    def register(self, classification: Classification) -> ReversibilityRegistry:
        """Return a **new** registry carrying one more classification.

        Never mutates. §8.3 lists *"reversibility class changing"* as
        requiring a new Intent rather than a silent substitution, and a
        registry a holder could edit would make that guarantee
        unenforceable.

        Re-registering a capability is refused, including with an identical
        classification: overwriting is how a reversible action becomes
        irreversible with nobody noticing.
        """
        if not isinstance(classification, Classification):
            raise InvalidClassification("register expects a Classification")
        if classification.capability in self._by_capability:
            raise InvalidClassification(
                f"{classification.capability!r} is already classified; a "
                "classification is declared once and never overwritten"
            )
        return ReversibilityRegistry(
            (*self._by_capability.values(), classification)
        )

    # ---- reading ------------------------------------------------------

    def classify(self, capability: str) -> Classification:
        """The declared classification, or `Unclassified`.

        **Raises rather than returning a default.** VEDA 04 A2 — no default
        classification exists, and an optional return is a default waiting
        to be written by a caller under deadline pressure.
        """
        try:
            return self._by_capability[capability]
        except KeyError:
            raise Unclassified(capability) from None

    def is_classified(self, capability: str) -> bool:
        """Whether a classification exists. Answers, never asserts."""
        return capability in self._by_capability

    @property
    def capabilities(self) -> tuple[str, ...]:
        """Every classified capability, in registration order."""
        return tuple(self._by_capability)

    def __len__(self) -> int:
        return len(self._by_capability)

    def __contains__(self, capability: object) -> bool:
        return capability in self._by_capability

    # ---- attesting ----------------------------------------------------

    def attest(
        self, capability: str, subject: str, attested_at: datetime
    ) -> Attestation:
        """Answer §7.3's A2 question about one capability.

        Roadmap Amendment 001 M7: the registry constructs the attestation
        rather than answering through an adapter. `Attestation` imports
        nothing, so the coupling is to a leaf.

        An unclassified capability yields a **`REFUSED` attestation, not an
        exception** — §7.5 requires refusals to be recorded, and a refusal
        the Kernel can carry into a receipt is more useful than one it must
        translate. `classify()` remains the raising path for callers that
        want the classification itself.

        `attested_at` is supplied by the caller from the canonical clock;
        this module never reads one.
        """
        if self.is_classified(capability):
            return Attestation(
                question=AttestationQuestion.REVERSIBILITY,
                attestor=AttestationQuestion.REVERSIBILITY.canonical_attestor,
                subject=subject,
                verdict=AttestationVerdict.SATISFIED,
                attested_at=attested_at,
            )

        return Attestation(
            question=AttestationQuestion.REVERSIBILITY,
            attestor=AttestationQuestion.REVERSIBILITY.canonical_attestor,
            subject=subject,
            verdict=AttestationVerdict.REFUSED,
            attested_at=attested_at,
            reason=(
                f"{capability!r} has no reversibility classification; the "
                "registry fails closed (VEDA 04 A2)"
            ),
        )
