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
#: LOCAL mode was chosen and no registered capability completes the
#: objective on its own. Distinct from `NO_STEPS`, which is a provider
#: saying the catalogue cannot achieve it: here no provider was asked,
#: because the founder asked for none to be.
LOCAL_ONLY = "local_only"
UNKNOWN_CAPABILITY = "unknown_capability"
MISSING_EXPECTATION = "missing_expectation"
BAD_DEPENDENCY = "bad_dependency"
#: MB039. A step whose payload does not satisfy its capability's
#: contract. Caught at plan time, which is the whole point: MB037's
#: first live plan named the right capabilities and got both payloads
#: wrong, and nothing noticed until the Runtime tried to execute it.
BAD_PAYLOAD = "bad_payload"
CYCLIC = "cyclic"


# ---- semantic roles ------------------------------------------------------
#
# ADR-0024 Decision 5: an Intent must preserve *who is expected to act* and
# *who receives or benefits from the result*. Before these existed,
#
#     "Learn trading"        -> Intent(goal="Learn trading", ...)
#     "Teach me trading"     -> Intent(goal="Teach me trading", ...)
#     "Help me learn trading"-> Intent(goal="Help me learn trading", ...)
#
# were structurally identical, and agency survived only because the raw
# sentence was carried downstream for a model to re-derive it from -- which
# is the "send the raw string to a model" pattern Constitution §3.1 says the
# Intent Layer deliberately is not.
#
# A closed vocabulary, like PRIORITIES and COMPLEXITIES below, and for the
# same reason: an open one drifts, and a founder-facing surface must be able
# to branch on these without parsing prose.
#
# UNKNOWN is a first-class member, not a failure. ADR-0024 §6: "For semantic
# dimensions that cannot yet be established confidently, unknown is
# preferable to guessing." Nothing may fabricate a role it did not derive.

SYSTEM = "system"
FOUNDER = "founder"
BOTH = "both"
UNKNOWN_ROLE = "unknown"

ROLES = (SYSTEM, FOUNDER, BOTH, UNKNOWN_ROLE)


#: What a requirement IS, closed like every other vocabulary here.
#:
#: Four kinds, and the boundary between them is what the founder would
#: notice if it were missing:
#:
#: * `EFFECT`      -- the world must change. A folder exists that did not.
#: * `INFORMATION` -- the founder must be TOLD something.
#: * `DELIVERABLE` -- an artefact must exist and be handed over.
#: * `CONSTRAINT`  -- a condition another requirement must satisfy.
#:
#: Deliberately not a taxonomy of domains. "filesystem", "browser" and
#: "research" are things the Planner reasons about from the capability
#: catalogue; a requirement describes WHAT the founder wants, and naming
#: a domain here would be the semantic layer starting to choose tools.
EFFECT = "effect"
INFORMATION = "information"
DELIVERABLE = "deliverable"
CONSTRAINT = "constraint"

REQUIREMENT_KINDS: tuple[str, ...] = (EFFECT, INFORMATION, DELIVERABLE, CONSTRAINT)

#: Whether the system is confident it understood the evidence.
#:
#: Closed, and load-bearing: `UNCERTAIN` may not execute and may not be
#: reported as satisfied. The two are the same rule seen from either end
#: of the mission.
#: Refusal code for a mission whose meaning was never settled. Not a
#: planning failure -- the Planner is never reached -- so it is reported
#: as its own thing rather than borrowing a capability refusal.
UNSETTLED_INTERPRETATION = "unsettled_interpretation"

KNOWN = "known"
UNCERTAIN = "uncertain"
INTERPRETATION_STATES: tuple[str, ...] = (KNOWN, UNCERTAIN)


@dataclass(frozen=True)
class SemanticRequirement:
    """One thing the founder requires, as a fact rather than as prose.

    ## Why this exists

    Three defects in three days had one shape in common: the founder's
    meaning was never a first-class object. It was prose at the front,
    arguments in the middle, verdicts at the end, and nothing carried it
    across. So a mission could report every step verified without being
    able to say whether the thing that was asked for happened -- which
    `reporter.py` admitted in as many words, reporting
    `founder_outcome_conformance: "not_evaluated"`.

    A requirement is what survives. It is extracted once, at the layer
    that understands language, and everything downstream refers to it by
    id rather than re-deriving it from the sentence.

    ## What it deliberately is not

    It names no capability. "Create a folder called Research on the
    Desktop" yields *an effect: the requested folder exists*, and two
    constraints -- not `Filesystem.CreateFolder`. Requirements describe
    WHAT; the Planner joins them to contracts and decides HOW. A
    requirement that named a capability would make the semantic layer a
    second tool selector, which ADR-0026 rejects by name.
    """

    requirement_id: str
    kind: str
    #: The system's CURRENT INTERPRETATION -- "location = d_drive".
    description: str
    #: False for something the founder mentioned but did not require.
    #: An unmet optional requirement never fails a mission.
    required: bool = True
    #: Which founder evidence established this -- their original sentence,
    #: a clarification answer, a correction. Provenance, never a provider
    #: transcript: "this fact came from this evidence", not "here is the
    #: hidden reasoning that produced it".
    provenance: str = ""
    #: The founder's OWN WORDS for this particular field.
    #:
    #: ## Why this is not the same as `description`
    #:
    #: `description` is what the system decided. This is what the founder
    #: said. Keeping only the first makes outcome conformance CIRCULAR --
    #: it compares execution against an interpretation, and proves
    #: consistency with itself rather than correspondence with meaning.
    #:
    #: Measured, live, twice. The founder said "d drive in onkar folder";
    #: the Brain resolved `location = d_drive`; the requirement was
    #: written from the RESOLVED value; execution created `D:\Rudra`;
    #: Verification confirmed it existed; and conformance reported
    #: SATISFIED about a folder in the wrong place -- because both sides
    #: of its comparison came from the same wrong reading.
    #:
    #: With the founder's words kept beside the interpretation, an audit
    #: can ask the question that matters: does what we did correspond to
    #: what they said?
    founder_evidence: str = ""
    #: Whether the interpretation of that evidence is settled.
    #: `UNCERTAIN` may never reach execution and may never be reported as
    #: satisfied.
    interpretation: str = "known"

    def as_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "kind": self.kind,
            "description": self.description,
            "required": self.required,
            "provenance": self.provenance,
            "founder_evidence": self.founder_evidence,
            "interpretation": self.interpretation,
        }


def requirement_ids(requirements: Any) -> tuple[str, ...]:
    return tuple(r.requirement_id for r in (requirements or ()))


def required_ids(requirements: Any) -> tuple[str, ...]:
    return tuple(r.requirement_id for r in (requirements or ()) if r.required)


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
    #: Who is expected to do the work. One of `ROLES`. Defaults to
    #: `UNKNOWN_ROLE` rather than `SYSTEM` so that an `Intent` built by
    #: hand -- in a test, or by a caller that has not thought about it --
    #: never silently claims an agency nobody derived.
    actor: str = UNKNOWN_ROLE
    #: Who receives, learns, or benefits from the result. One of `ROLES`.
    beneficiary: str = UNKNOWN_ROLE
    #: A dot-path into the named capability's OUTPUT that answers the
    #: founder, when the Intent Layer knows they asked a question rather
    #: than ordered work. `"text"` for `Reasoning.Transform`.
    #:
    #: Empty for every ordinary intent. Carried here rather than derived
    #: in the Planner because "this founder asked a question" is what the
    #: Intent Layer determined; the Planner's job is to check the
    #: capability actually publishes the field before promising it.
    answers_founder: str = ""
    #: The capability this intent names, when the Intent Layer recognised
    #: a typed action rather than free prose -- e.g. `"create_folder"`.
    #: Empty whenever nothing was recognised, which is most input.
    #:
    #: This is not the Brain deciding what is executable; the Planner still
    #: checks the capability is registered and that its contract is
    #: satisfied, and refuses or reasons if it is not (ADR-0024 Decision
    #: 2). It is the Intent Layer stating what it already parsed, so the
    #: Planner does not have to pay a model to rediscover it.
    #:
    #: The pair is `cli.py`'s own `ParsedActionIntent` contract, which has
    #: said since MB005 that `capability` "becomes the plan's
    #: Step.capability directly" -- adopted here rather than re-invented,
    #: so there is one shape for "a parsed action and its arguments".
    capability: str = ""
    #: Arguments for `capability`, keyed by the capability contract's OWN
    #: published argument names (`name`, `location`, ...), never by the
    #: parser's internal vocabulary. Becomes `Step.payload` verbatim.
    payload: dict[str, Any] = field(default_factory=dict)
    #: What the founder requires, in the order they said it.
    #:
    #: Empty is legitimate and means "nobody has extracted these yet" --
    #: a hand-built Intent in a test, or a legacy record. It never means
    #: "the founder required nothing", and downstream code must not read
    #: it that way: an absent trace yields `UNKNOWN` conformance, never
    #: `SATISFIED`.
    requirements: tuple[SemanticRequirement, ...] = ()


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
    #: Destination argument -> binding, for inputs produced by an earlier
    #: Step rather than known at planning time.
    #:
    #: `depends_on` says WHEN a step may run. This says WHAT flows into it.
    #: A Medium mission had the first and not the second: it correctly
    #: declared that the write depended on the observation, then filled the
    #: content from the founder's own sentence because there was no way to
    #: say "that argument comes from step_3". The file recorded
    #: `https://example.com` for a page that had actually reported
    #: `https://example.com/`.
    input_bindings: dict[str, Any] = field(default_factory=dict)
    #: MB036. What this Step is expected to produce, stated before it runs
    #: so the verdict on it is falsifiable rather than a rationalisation.
    #: `None` means nobody said -- which MB035's founder page renders as
    #: `not checked`, deliberately distinct from `not matched`.
    expected_outcome: ExpectedOutcome | None = None
    #: A pause the FOUNDER asked for, in their own objective -- "show me
    #: what you propose before you change it". Empty for almost every
    #: step, because almost no objective asks.
    #:
    #: Deliberately not a permission concept. Destructive, financial and
    #: privacy boundaries hold their own steps automatically and need no
    #: help from a plan; this exists for the opposite case, where policy
    #: would let the work run and the founder said they wanted to look
    #: first. Conflating the two is what produced a planner rule claiming
    #: every change pauses for approval, which was never the policy.
    #:
    #: The text is what the founder will be shown described, not the
    #: content itself -- the content comes from the step's resolved inputs
    #: at run time, so what they read is what the earlier steps actually
    #: produced rather than what the plan predicted.
    founder_checkpoint: str = ""
    #: A dot-path into THIS step's observation naming the value the
    #: founder asked to be told -- `"elements.0.text"` for "tell me the
    #: current text shown by #state". Empty on every step of almost every
    #: plan, exactly like `founder_checkpoint` above, and for the same
    #: reason: it exists because an objective asked for it.
    #:
    #: The defect it removes is a reporting one. `FounderState.result` is
    #: the LAST COMPLETED task's result, which for any mission that tidies
    #: up after itself is the cleanup step -- a browser workflow ending in
    #: `CloseBrowserSession` reported the close, never the answer. The
    #: founder asked a question and was told "Done".
    #:
    #: Deliberately a path and not a sentence: selecting a named field
    #: from an observation is projection, and projection is deterministic.
    #: The moment this held prose, something would have to compose it, and
    #: composing an answer is precisely the authority the reporting path
    #: does not have.
    #:
    #: Set only by the deterministic lane, which knows what the founder
    #: dictated. The planning prompt does not mention it and the plan
    #: parser does not read it, so a model cannot designate an answer for
    #: work it merely guessed the shape of.
    answers_founder: str = ""
    #: MB037. **Descriptive, never directive.** Mission Control owns
    #: execution order and resolves it from `depends_on`; a Planner that
    #: could reorder execution by labelling a step `critical` would own
    #: lifecycle, which the Constitution gives to Mission Control alone.
    #: These two exist so a founder reading a plan knows what matters and
    #: what is big -- and a test asserts the dispatcher ignores them.
    #: The semantic requirement ids this step is responsible for.
    #:
    #: **Descriptive, never directive** -- the same discipline `priority`
    #: carries. Mission Control resolves execution order from
    #: `depends_on` and permission from the capability's risk tier;
    #: neither reads this, and a test asserts the dispatcher ignores it.
    #:
    #: It is a claim of RESPONSIBILITY, not a claim about reality. A plan
    #: saying "step_2 covers req_4" has said only that it intends step_2
    #: to satisfy req_4. Whether it did is Evidence's answer, later.
    covers: tuple[str, ...] = ()
    #: Why this capability was chosen for those requirements, composed at
    #: planning time from published FACTS -- the requirement, the
    #: capability's own description, its argument contract.
    #:
    #: Recorded so that "why did you use that tool?" is answered from what
    #: was decided, not by a model inventing a plausible reason after the
    #: fact. Descriptive, like `covers`: nothing dispatches on it.
    selection_reason: str = ""
    priority: str = DEFAULT_PRIORITY
    estimated_complexity: str = DEFAULT_COMPLEXITY


@dataclass
class MissionPlan:
    steps: list[Step]
    #: The goal these steps were derived from, carried so a stored plan
    #: explains itself without needing the Intent that produced it.
    objective: str = ""
    #: The founder requirements this plan was built against.
    #:
    #: Carried on the plan as well as the Intent because a stored plan
    #: must explain itself: conformance later asks "which requirements
    #: did this mission owe?", and answering from the plan means the
    #: answer cannot drift from the coverage the steps declare.
    requirements: tuple[SemanticRequirement, ...] = ()
    #: The Intent Layer's sensitivity judgement. It is execution metadata,
    #: not a provider choice, and is projected onto Tasks so model output
    #: cannot lower it.
    is_sensitive: bool | None = None


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
    #: True when the first proposal was rejected and a bounded correction
    #: pass produced this plan instead. Recorded rather than hidden: a
    #: plan that needed repairing is a fact about how it was made, and an
    #: audit asking why planning took two provider calls deserves the
    #: answer.
    corrected: bool = False
    #: The founder's LOCAL / AI MODE / BOTH selection at plan time, and
    #: the mode this mission actually ran under. They differ when the
    #: objective required resources the selection did not name -- an AI
    #: preference meeting an objective that needs Hands. Carried on the
    #: outcome rather than in a separate audit store: the plan and the
    #: reason it was planned that way belong together.
    selected_mode: str = ""
    effective_mode: str = ""
    #: Why they differ, when they do. Empty when nothing was broadened.
    mode_reason: str = ""
    #: The reasoning ladder's own attempt sequence, when a provider was
    #: asked at all. `TieredPromptRunner` has recorded this on
    #: `last_attempts` since it was written -- "report which tier actually
    #: handled the request, not just a final yes/no" -- and nothing ever
    #: read it, so it was overwritten by the next call and never survived.
    #: Empty for a deterministic plan, which asked nobody.
    attempts: tuple[dict[str, Any], ...] = ()


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
