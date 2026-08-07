"""The plan vocabulary (Mission Brief 036).

`Intent`, `Step` and `MissionPlan` predate this brief -- MB001 wrote them
and the Orchestrator has walked them ever since. They move here so the
Planner's own modules can import the vocabulary without importing the
Planner, and `planner/planner.py` re-exports all three so every existing
`from master_agent.planner.planner import MissionPlan, Step` keeps
working. Nothing that consumed them was changed.

## What is new: `Step.expected_outcome`

Constitution §3.2 says every Step names an Expected Outcome, and
`ExpectedOutcome`'s own docstring in the frozen `verification/` package
names the Planner as the thing that attaches one. Until MB035 there was
nothing to attach it *for*; now there is.

The field is **optional on the dataclass and mandatory in the Planner**,
and that split is deliberate. Hand-built Steps exist -- MB022's browser
tests, `cli.py`'s regex stand-in -- and making the field required would
turn a vocabulary change into a rewrite of five briefs, which is not what
§3.2 is asking for. §3.2 is a rule about *planning*, so it is enforced
where planning happens: `validate()` in `parsing.py` refuses a plan whose
step has no expectation, and `test_planner_architecture.py` asserts the
Planner cannot emit one. A rule enforced at the door it is about beats a
type signature that forces unrelated code to lie.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from master_agent.verification.evidence import Evidence, ExpectedOutcome

# ---- refusal codes -------------------------------------------------------
#
# A closed vocabulary, the way MB033's five named failure outcomes are: a
# caller can branch on the code and a founder can read the reason, and
# neither has to parse a sentence. Every one of these means *no plan was
# produced* -- there is no partial plan, because half a plan executed is
# worse than none.

NO_CAPABILITIES = "no_capabilities"
BROKER_REFUSED = "broker_refused"
PROVIDER_FAILED = "provider_failed"
UNVERIFIED = "unverified"
NOT_JSON = "not_json"
MALFORMED = "malformed"
NO_STEPS = "no_steps"
UNKNOWN_CAPABILITY = "unknown_capability"
MISSING_EXPECTATION = "missing_expectation"
BAD_DEPENDENCY = "bad_dependency"
#: MB039. A step whose payload does not satisfy its capability's
#: contract. Caught at plan time, which is the whole point: MB037's
#: first live plan named the right capabilities and got both payloads
#: wrong, and nothing noticed until the Runtime tried to execute it.
BAD_PAYLOAD = "bad_payload"
CYCLIC = "cyclic"


@dataclass
class Intent:
    """Structured intent -- the output of the Intent Layer, the input to
    the Planner. Never a raw prompt string (see "Intent over prompts").
    """

    goal: str
    constraints: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    success_criteria: list[str] = field(default_factory=list)
    is_sensitive: bool = False


#: MB037. Closed vocabularies, both of them, for the same reason every
#: other vocabulary in this system is closed: an open one drifts, and
#: neither of these is worth a free-text field a founder has to interpret.
PRIORITIES = ("low", "normal", "high", "critical")
COMPLEXITIES = ("trivial", "small", "moderate", "large")

DEFAULT_PRIORITY = "normal"
DEFAULT_COMPLEXITY = "moderate"


@dataclass
class Step:
    step_id: str
    capability: str
    payload: dict[str, Any]
    depends_on: list[str] = field(default_factory=list)
    #: MB036. What this Step is expected to produce, stated before it runs
    #: so the verdict on it is falsifiable rather than a rationalisation.
    #: `None` means nobody said -- which MB035's founder page renders as
    #: `not checked`, deliberately distinct from `not matched`.
    expected_outcome: ExpectedOutcome | None = None
    #: MB037. **Descriptive, never directive.** Mission Control owns
    #: execution order and resolves it from `depends_on`; a Planner that
    #: could reorder execution by labelling a step `critical` would own
    #: lifecycle, which the Constitution gives to Mission Control alone.
    #: These two exist so a founder reading a plan knows what matters and
    #: what is big -- and a test asserts the dispatcher ignores them.
    priority: str = DEFAULT_PRIORITY
    estimated_complexity: str = DEFAULT_COMPLEXITY


@dataclass
class MissionPlan:
    steps: list[Step]
    #: The goal these steps were derived from, carried so a stored plan
    #: explains itself without needing the Intent that produced it.
    objective: str = ""


@dataclass(frozen=True)
class PlanRefusal:
    """Why no plan exists. Frozen, and it carries the facts a founder
    needs to fix the situation rather than only the verdict -- the MB033
    discipline where a missing model is reported *with the list of models
    that are installed*."""

    code: str
    reason: str
    detail: str = ""
    #: For `unknown_capability`: what actually is registered. Empty
    #: otherwise.
    known_capabilities: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "reason": self.reason,
            "detail": self.detail,
            "known_capabilities": list(self.known_capabilities),
        }


@dataclass(frozen=True)
class PlanOutcome:
    """Two shapes, and the caller can tell them apart without parsing a
    string: a plan, or a refusal explaining why there isn't one.

    `evidence` is MB035's record for the *plan text itself*. The plan is
    generated text like any other, so it is checked against an expectation
    stated before it was asked for, and a plan that fails that check is
    never parsed. `entry_id` ties the whole thing back to the Broker's
    decision on the ledger.
    """

    plan: MissionPlan | None = None
    refusal: PlanRefusal | None = None
    evidence: Evidence | None = None
    entry_id: int | None = None
    provider_id: str | None = None
    #: What the provider actually said. Kept so a malformed plan can be
    #: read by a founder rather than only described to them.
    raw: str = ""

    @property
    def planned(self) -> bool:
        return self.plan is not None

    @property
    def reason(self) -> str:
        return self.refusal.reason if self.refusal is not None else ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "planned": self.planned,
            "steps": len(self.plan.steps) if self.plan else 0,
            "provider_id": self.provider_id,
            "entry_id": self.entry_id,
            "verdict": self.evidence.verdict.value if self.evidence else "",
            "refusal": self.refusal.as_dict() if self.refusal else None,
        }
