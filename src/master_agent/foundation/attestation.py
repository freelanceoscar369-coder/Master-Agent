"""Attestation — one component's answer to one of the Kernel's questions.

Constitutional Kernel Specification §7.3:

> *"The Kernel verifies each attestation's **presence, attestor identity,
> subject match, and freshness**. It never re-derives the verdict. An
> attestation whose attestor is wrong, whose subject does not match this
> request, or which is stale is treated as absent."*

That sentence is the Kernel's entire design — §1.2 states it as
*"attestation, not reimplementation"* — and this is the type it operates
on.

## What it is, and what it is not

An attestation is **evidence that a required constitutional check was
performed**, signed by the component that owns the question.

| Not | Because |
|---|---|
| a permission | The Permission System decides. A3 records that it was asked. |
| a warrant | A warrant permits execution. This permits nothing. |
| an execution record | That is the Receipt, written afterwards. |
| a verdict the Kernel re-derives | §7.3 — *"It never re-derives the verdict."* |

## The attestor is a component, never a person

All eight attestors in §7.3 are **components**: Mission Control, the
Reversibility Registry, the Permission System, the Standing Rule Engine,
the Principal registry, the capability contract, and the Broker twice.

A `Principal` is a human authority — the founder or a delegate — and is
never an attestor. Conflating the two is the error Component 2's conflict
report documented at length: a non-human principal is Kalpavriksha holding
authority under another name.

So `attestor` is a component identifier, and this module has **no
dependency on `Principal`**. See ED-018.

## Attestor identity is enforced here, not merely checked later

Each question knows the component that owns it, because §7.3 assigns them
one to one. Constructing an attestation whose attestor does not own its
question raises, rather than being caught downstream — the same posture
that makes an over-ceiling `Warrant` and a compensation-less `PARTIAL`
`Receipt` unconstructable.

This does not replace the Kernel's §7.3 check. The Kernel still verifies
presence, subject match and freshness; this makes one of the four
impossible to get wrong in the first place.

## No dependency on the Warrant

Per the frozen integration decision for Component 7: `Warrant` stays
byte-compatible with `kalpavriksha-s1-c3.0`. The Kernel aggregates
attestations during authorization; an attestation itself knows nothing
about warrants, and nothing here imports one.

## Time

`attested_at` is timezone-aware and normalised to UTC. `is_stale()` takes
the moment as an argument and never reads a clock — the pattern
`Warrant.is_expired()` established, which is what keeps this a pure value.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any


class AttestationQuestion(str, Enum):
    """The eight questions of Kernel Specification §7.3.

    The vocabulary is closed. A ninth question is a change to the Kernel's
    precondition set, which is a constitutional decision rather than a code
    change — and an open enum is where one appears without anyone noticing.
    """

    #: A1 — Is this task ready: dependencies satisfied, correctly assigned?
    TASK_READY = "task_ready"

    #: A2 — What is this action's reversibility class, and how is it undone?
    REVERSIBILITY = "reversibility"

    #: A3 — Is there a valid grant for this capability at this tier?
    PERMISSION = "permission"

    #: A4 — If firing under a rule: headroom, exclusions, not expired?
    RULE = "rule"

    #: A5 — Who is acting, and on whose authority?
    PRINCIPAL = "principal"

    #: A6 — Does the payload conform to the capability's input schema?
    PAYLOAD_SCHEMA = "payload_schema"

    #: A7 — *(intelligence only)* Provider, budget, deadline?
    PROVIDER = "provider"

    #: A8 — *(intelligence only)* Should this call be made at all?
    ADMISSION = "admission"

    @property
    def canonical_attestor(self) -> str:
        """The component that owns this question.

        §7.3 assigns each question exactly one attestor. Holding the mapping
        with the question keeps it in one place, and means the Kernel needs
        no table of its own to check attestor identity against.
        """
        return _CANONICAL_ATTESTOR[self]

    @property
    def is_intelligence_only(self) -> bool:
        """Whether this question applies only to intelligence actions.

        §7.4: a `local` action requires A1–A6; an `intelligence` action
        requires those plus A7 and A8. *"The sets differ by two
        attestations. That is the entire difference between the pipelines
        inside the Kernel."*
        """
        return self in _INTELLIGENCE_ONLY


#: §7.3's question → attestor assignment, verbatim. Identifiers are stable
#: strings rather than imports: this module depends on none of these
#: components, and several do not exist yet.
_CANONICAL_ATTESTOR: dict[AttestationQuestion, str] = {
    AttestationQuestion.TASK_READY: "mission_control",
    AttestationQuestion.REVERSIBILITY: "reversibility_registry",
    AttestationQuestion.PERMISSION: "permission_system",
    AttestationQuestion.RULE: "standing_rule_engine",
    AttestationQuestion.PRINCIPAL: "principal_registry",
    AttestationQuestion.PAYLOAD_SCHEMA: "capability_contract",
    AttestationQuestion.PROVIDER: "broker",
    AttestationQuestion.ADMISSION: "broker",
}

_INTELLIGENCE_ONLY = frozenset(
    {AttestationQuestion.PROVIDER, AttestationQuestion.ADMISSION}
)


class AttestationVerdict(str, Enum):
    """What the attestor found.

    **Two values, not three.** There is no `UNKNOWN` and no `ABSENT`,
    because §7.3 says an attestation that is missing, stale, wrongly
    attributed, or subject-mismatched *"is treated as absent"* — absence is
    the lack of an attestation, never a value one can carry. A third
    verdict would let a component record uncertainty where the Kernel
    expects an answer, and the Kernel would have to decide what that meant.
    """

    SATISFIED = "satisfied"
    REFUSED = "refused"


class InvalidAttestation(ValueError):
    """Raised at construction for an attestation that could not be evidence.

    At construction, never at verification time: the Kernel trusts these,
    so one that should not exist must not be constructible.
    """


@dataclass(frozen=True)
class Attestation:
    """One component's signed answer to one constitutional question.

    Immutable and hashable. Two attestations with identical fields are the
    same attestation.
    """

    #: Which of the eight was asked.
    question: AttestationQuestion

    #: The component that answered. Must be the one §7.3 assigns to this
    #: question — a component identifier, never a `Principal`.
    attestor: str

    #: What this attestation is about. Opaque here: the Kernel compares it
    #: against the request it is authorizing (§7.3's subject match), and
    #: what identifies a subject is the Kernel's business, not this value's.
    subject: str

    verdict: AttestationVerdict

    #: When the attestor answered. Supplied from the canonical Clock.
    attested_at: datetime

    #: Why, when refused. Required on `REFUSED` and refused on `SATISFIED`,
    #: so the field cannot drift into a general-purpose note — the same
    #: symmetry `Receipt.compensation_ref` uses for `PARTIAL`.
    reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.question, AttestationQuestion):
            raise InvalidAttestation("question must be an AttestationQuestion")
        if not isinstance(self.verdict, AttestationVerdict):
            raise InvalidAttestation("verdict must be an AttestationVerdict")

        for name in ("attestor", "subject"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise InvalidAttestation(f"{name} must be a non-empty identifier")

        expected = self.question.canonical_attestor
        if self.attestor != expected:
            raise InvalidAttestation(
                f"{self.question.value!r} is attested by {expected!r}, not "
                f"{self.attestor!r}; an attestation attributed to the wrong "
                "component is treated as absent (Kernel Specification §7.3)"
            )

        object.__setattr__(
            self, "attested_at", _as_utc(self.attested_at, "attested_at")
        )

        if self.verdict is AttestationVerdict.REFUSED:
            if not (self.reason or "").strip():
                raise InvalidAttestation(
                    "a refused attestation requires a reason; a refusal that "
                    "cannot say what failed is not answerable"
                )
        elif self.reason is not None:
            raise InvalidAttestation(
                "reason is only meaningful on a refused attestation, not on "
                "a satisfied one"
            )

    # ---- immutable helpers -------------------------------------------

    @property
    def is_satisfied(self) -> bool:
        return self.verdict is AttestationVerdict.SATISFIED

    def is_stale(self, at: datetime, max_age: timedelta) -> bool:
        """Whether this attestation is too old to be relied on.

        Takes the moment rather than a `Clock`, so this stays a pure value
        with no dependencies. The caller reads the canonical clock once and
        passes what it said.

        A negative `max_age` is refused: it would make every attestation
        stale, including the one just written, which is a configuration
        error rather than a very strict policy.
        """
        if max_age < timedelta(0):
            raise InvalidAttestation("max_age must not be negative")
        return _as_utc(at, "at") - self.attested_at > max_age

    def as_dict(self) -> dict[str, Any]:
        """A deterministic, JSON-ready projection.

        Fixed key order, ISO-8601 UTC timestamp, enum values as strings.
        Equal attestations always produce identical dictionaries, so a
        receipt recording what was attested is comparable years later.
        """
        return {
            "question": self.question.value,
            "attestor": self.attestor,
            "subject": self.subject,
            "verdict": self.verdict.value,
            "attested_at": self.attested_at.isoformat(),
            "reason": self.reason,
        }


def _as_utc(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise InvalidAttestation(f"{field_name} must be a datetime")
    if value.tzinfo is None:
        raise InvalidAttestation(
            f"{field_name} must be timezone-aware; every moment in "
            "Kalpavriksha comes from the canonical clock and is aware"
        )
    return value.astimezone(UTC)
