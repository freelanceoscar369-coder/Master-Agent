"""Execution Request — everything the Kernel needs before it is asked.

Constitutional Kernel Specification §3.5:

```
  authorize(ExecutionRequest) → Intent | Refusal
```

This is the **input half** of that contract. The shipped `Warrant` is the
output half. An `ExecutionRequest` is assembled by the caller, handed to
the Kernel, and becomes a `Warrant` if — and only if — the three checks of
§7.2 pass and the attestations of §7.3 verify.

## It decides nothing

A request is a **question**, not a claim. It carries no authority, permits
nothing, and asserts nothing about its own validity. Every field it holds
is either something only the caller knows (which objective, which
capability, which payload) or evidence some other component produced (the
attestations).

This is why the fields §4.3 sources to the Kernel at mint are **absent**
here: `warrant_id`, `compensating_action`, `undo_window`,
`consequence_ceiling`, `grant_ref`, `rule_ref`, `attempt_budget`,
`issued_at`, `expires_at`, `sequence`, `decision_ref` and `task_ref`. A
request carrying any of those would be the caller authorizing itself, and
the Kernel would have nothing left to decide.

## Two fields the request carries *for* the Kernel

`reversibility_class` (**ADR-0022**) and `expected_effect` (**ADR-0023
D2**) are exceptions, and both by ratified founder decision.

Neither is invented by the caller. `reversibility_class` comes from the
**Reversibility Registry** — the owner §4.3 names — obtained via
`classify()` alongside the A2 attestation. `expected_effect` comes from
the **Planner**, via Constitution §17's `Step` and its Expected Outcome.
The caller is a courier for both, exactly as it already is for the eight
attestations.

They are here rather than behind a lookup because the founder's stated
architectural intent is that *"the Kernel performs no additional lookups
beyond the already approved `AdmissionProvider`."* The Kernel derives
`attempt_budget` (§8.5) and `expires_at` (§4.4) from the carried class
without a further dependency.

**TODO(ADR-0022):** the A2 attestation does not yet bind to the carried
`reversibility_class` — R34. ADR-0023 D5 specifies the close: A2's subject
becomes `sha256(payload_digest + "\\x1f" + reversibility_class.value)`.
Until that ships, the carried class is **trusted**.

## Incompleteness is legal, and deliberately so

§7.3 makes the Kernel verify each attestation's **presence**. If this
object refused construction without all eight, that presence check would
be dead code and a caller could never build the object whose refusal §7.5
requires to be recorded.

**Completeness is the Kernel's judgment, never this value's invariant.**
What is enforced here is that the request cannot be *ambiguous* — no two
answers to one question, no empty identifier, no null consequence.

## `principal_id`, not `Principal`

Frozen founder decision (Roadmap Amendment 001 M8). An `ExecutionRequest`
becomes a `Warrant`, and `Warrant.principal_id` is a flat `str` — *"a
flat, self-contained record… deterministic to serialise"*. Carrying a
richer type than the thing it turns into would mean the Kernel discards
the difference at mint.

So this module has **no dependency on C2 Principal**.

## The consequence is never null

Kernel Specification §14.1, verbatim:

> *"The consequence quartet is required on every intent record from the
> moment B1 exists. Until then the field carries the explicit marker
> `pending_consequence_engine` — **never null, never omitted, and never a
> partial quartet**."*

B1, the Consequence Engine, is Sprint 2. Until it exists the field holds
`PENDING_CONSEQUENCE_ENGINE`, an immutable module-level sentinel. It is
not `None`, because an absence is something a later reader mistakes for an
oversight, and it is not a partial `Consequence`, because C6 forbids
constructing one.

## The `Execution*` boundary

Eight types now share the prefix. Roadmap §5 R9 requires each to say what
it is not:

| Type | Is |
|---|---|
| `ExecutionRequest` *(this)* | What the caller asks be authorized. **Before** any decision |
| `ExecutionContext` (C3) | Who is running, under which warrant. Runtime identity |
| `ExecutionOutcome` (C5) | How an execution ended. **After** the fact |
| `ExecutionResult` | A Worker's return value from one Action |
| `ExecutionLogEntry` | The executor's own log line |
| `ExecutionRecord` · `ExecutionReplay` | The AI ledger's records |
| `ExecutionRow` | A dashboard read-model projection |

**The distinction that matters:** this one exists before anything is
authorized. Every other `Execution*` type exists because something already
was.

## Time

None. A request carries no clock reading — `issued_at` and `expires_at`
are set by the Kernel at mint (§4.3), and a second reading would be a
second answer to one question.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from master_agent.foundation.attestation import Attestation, AttestationQuestion
from master_agent.foundation.consequence import Consequence
from master_agent.foundation.warrant import ReversibilityClass


class ActionClass(str, Enum):
    """What kind of action this is. Kernel Specification §7.4.

    The vocabulary is closed at two. §7.4 assigns each class an attestation
    set, and *"the sets differ by two attestations. That is the entire
    difference between the pipelines inside the Kernel"* — which is what
    §5.2's *"converge, do not merge"* means in code.

    A third class would be a third pipeline, and that is a constitutional
    decision rather than a code change.
    """

    #: Filesystem, terminal, browser — anything performed on this machine.
    #: Requires A1–A6.
    LOCAL = "local"

    #: A call to a Reasoning Provider. Requires A1–A6 plus A7 and A8, the
    #: Broker's two questions.
    INTELLIGENCE = "intelligence"


@dataclass(frozen=True)
class PendingConsequenceEngine:
    """The explicit marker Kernel Specification §14.1 requires.

    Not an absence. §14.1's stated purpose for the marker is that it
    *"makes the temporary gap **explicit and greppable** rather than an
    absence someone later mistakes for an oversight."*

    Instances are equal, immutable and hashable, so a request carrying the
    marker serialises deterministically and compares cleanly. Use the
    module-level `PENDING_CONSEQUENCE_ENGINE` rather than constructing one.
    """

    def __repr__(self) -> str:  # pragma: no cover - representation only
        return "PENDING_CONSEQUENCE_ENGINE"

    def as_dict(self) -> str:
        """The marker's wire form — the literal §14.1 names."""
        return "pending_consequence_engine"


#: The value `ExecutionRequest.consequence` carries until B1 exists.
PENDING_CONSEQUENCE_ENGINE = PendingConsequenceEngine()


class InvalidExecutionRequest(ValueError):
    """Raised at construction for a request the Kernel could not answer.

    At construction, never at authorization time. The Kernel refuses
    requests on constitutional grounds and records those refusals; a
    request that is merely *malformed* is not a constitutional refusal and
    must not become one, or the ledger fills with records of callers
    getting the shape wrong.
    """


@dataclass(frozen=True)
class ExecutionRequest:
    """One request for authorization. Immutable and hashable.

    Two requests with identical fields are the same request — which is what
    lets `attempt()` check the payload digest against what was authorized
    (§4.4) rather than trusting the caller twice.
    """

    #: The Objective this action advances. The Kernel's K1 anchor, and the
    #: one field §7.2 says *"no intent exists without"*. Opaque here: this
    #: value never resolves it, which is what keeps C9 independent of the
    #: Objective Engine and its unratified ADR.
    objective_id: str

    #: The founder or delegate on whose authority this runs. A flat
    #: identifier, matching `Warrant.principal_id` — frozen decision M8.
    principal_id: str

    #: What is being asked for, qualified — e.g. `Filesystem.DeleteFolder`.
    capability: str

    #: Content hash of the payload. **The digest, never the payload.**
    #: §4.3: payloads carry founder data and prompts, and permanence plus
    #: sensitive content is a liability rather than a feature.
    payload_digest: str

    #: Selects the §7.4 attestation set.
    action_class: ActionClass

    #: What this action does to the world. Obtained from the Reversibility
    #: Registry — §4.3's named owner — never asserted by the caller.
    #: ADR-0022. The Kernel derives `attempt_budget` (§8.5) and
    #: `expires_at` (§4.4) from it.
    reversibility_class: ReversibilityClass

    #: What the world should look like afterwards, in the founder's terms.
    #: The `Step`'s Expected Outcome (Constitution §17), authored by the
    #: Planner. ADR-0023 D2. Copied into the permanent `IntentRecord` at
    #: K3, and later compared against an Observation by Verification.
    expected_effect: str

    #: The quartet, or §14.1's marker. **Never `None`.**
    consequence: Consequence | PendingConsequenceEngine

    #: What is acted upon — a path, a URL, a provider id. §4.3 carries it
    #: *"where meaningful"*, so it is optional; but a blank string is not
    #: the same as absent and is refused.
    target_ref: str | None = None

    #: The evidence gathered so far, one per question at most. **May be
    #: incomplete, and may be empty** — verifying presence is §7.3's job,
    #: not this value's. See the module docstring.
    attestations: tuple[Attestation, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "objective_id",
            "principal_id",
            "capability",
            "payload_digest",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise InvalidExecutionRequest(
                    f"{name} must be a non-empty identifier"
                )

        if not isinstance(self.action_class, ActionClass):
            raise InvalidExecutionRequest("action_class must be an ActionClass")

        if not isinstance(self.reversibility_class, ReversibilityClass):
            raise InvalidExecutionRequest(
                "reversibility_class must be a ReversibilityClass; it comes "
                "from the Reversibility Registry, and there is no default "
                "because A2 fails closed on anything unclassified"
            )

        if (
            not isinstance(self.expected_effect, str)
            or not self.expected_effect.strip()
        ):
            raise InvalidExecutionRequest(
                "expected_effect must say what the world should look like "
                "afterwards; a blank one is a step whose completion cannot "
                "be checked"
            )

        self._validate_consequence()
        self._validate_target_ref()
        self._validate_attestations()

    # ---- invariants ---------------------------------------------------

    def _validate_consequence(self) -> None:
        if isinstance(self.consequence, (Consequence, PendingConsequenceEngine)):
            return
        raise InvalidExecutionRequest(
            "consequence must be a Consequence or PENDING_CONSEQUENCE_ENGINE; "
            "it is never null, never omitted and never a partial quartet "
            "(Kernel Specification §14.1)"
        )

    def _validate_target_ref(self) -> None:
        if self.target_ref is None:
            return
        if not isinstance(self.target_ref, str) or not self.target_ref.strip():
            raise InvalidExecutionRequest(
                "target_ref must be a non-empty reference when present; use "
                "None where §4.3's 'where meaningful' does not apply"
            )

    def _validate_attestations(self) -> None:
        if not isinstance(self.attestations, tuple):
            raise InvalidExecutionRequest(
                "attestations must be a tuple, so a request cannot be edited "
                "after it is built"
            )

        seen: set[AttestationQuestion] = set()
        for item in self.attestations:
            if not isinstance(item, Attestation):
                raise InvalidExecutionRequest(
                    "every attestation must be an Attestation"
                )
            if item.question in seen:
                raise InvalidExecutionRequest(
                    f"two attestations answer {item.question.value!r}; §7.3 "
                    "assigns each question exactly one attestor, and the "
                    "Kernel cannot choose between two answers"
                )
            seen.add(item.question)

    # ---- reading ------------------------------------------------------

    @property
    def is_consequence_pending(self) -> bool:
        """Whether the quartet is still §14.1's marker.

        Exposed so the gap is greppable in code as well as in a record,
        which is the marker's whole purpose.
        """
        return isinstance(self.consequence, PendingConsequenceEngine)

    def as_dict(self) -> dict[str, Any]:
        """A deterministic, JSON-ready projection.

        Fixed key order; attestations in the order supplied, since §7.3
        assigns one attestor per question and the caller's order carries no
        meaning the Kernel reads. Equal requests always produce identical
        dictionaries.
        """
        return {
            "objective_id": self.objective_id,
            "principal_id": self.principal_id,
            "capability": self.capability,
            "payload_digest": self.payload_digest,
            "action_class": self.action_class.value,
            "reversibility_class": self.reversibility_class.value,
            "expected_effect": self.expected_effect,
            "consequence": self.consequence.as_dict(),
            "target_ref": self.target_ref,
            "attestations": [item.as_dict() for item in self.attestations],
        }
