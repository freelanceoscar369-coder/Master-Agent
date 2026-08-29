"""How the Brain decides, when deciding is more than looking something up.

## The failure this answers

Founder acceptance failed on:

    search for action rpg games released in 2026 and give me free demo
    download links

and the founder was told *"That didn't complete."* The immediate cause
was a browser that never opened. The reason that mattered is different:
there was no faculty that could have turned a pile of page text into a
justified shortlist even if every page had loaded. A ten-step plan
existed, and nothing in the system owned the questions *which of these
qualify*, *is this evidence enough*, *do these two sources disagree*, and
*is another source worth the cost*.

Strong Workers with a weak Brain produce fast mistakes. This module is
the Brain's side of that bargain (ADR-0027).

## What is deliberately NOT here

**No model is required for the discipline.** Framing and synthesis need
reasoning; deciding whether a candidate cleared its mandatory criteria is
arithmetic, and a model asked to grade that would be a model grading a
model -- which ADR-0026 rejects and ADR-0011 exists to prevent. So the
shortlist, the contradiction bookkeeping, the sufficiency rule and the
utility gate below are all pure functions over recorded facts. The same
argument, and the same shape, as `brain/conformance.py`.

**No execution, no environment, no providers.** This module never opens a
browser, never reads a file, never names a provider. It states what kind
of reasoning is needed; the Broker alone decides who does it (ADR-0017).

**No hidden chain-of-thought.** What is stored is reviewable: claims,
Evidence references, criteria states and explicit reasons. A transcript
is not a rationale.

**Reasoning is never Verification.** Nothing here produces a `Verdict` or
Evidence. A critique is an input to a decision, not an observation of
reality (ADR-0011).
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------
# How much thinking this deserves
# ---------------------------------------------------------------------

#: A deterministic fact or action. No model, no deliberation.
DIRECT = "direct"
#: One bounded reasoning operation -- extract, summarise, compare two.
REASONED = "reasoned"
#: Several evidence items, ranking or shortlisting, live alternatives,
#: or information that disagrees with itself.
DELIBERATIVE = "deliberative"
#: Consequential or hard to reverse, or materially uncertain.
CRITICAL = "critical"

DEPTHS: tuple[str, ...] = (DIRECT, REASONED, DELIBERATIVE, CRITICAL)

# ---------------------------------------------------------------------
# What a statement IS -- never collapsed into one prose answer
# ---------------------------------------------------------------------

FACT = "fact"                    #: supported by authoritative Evidence
INFERENCE = "inference"          #: reasoned from facts, not observed
ASSUMPTION = "assumption"        #: temporary, and explicit
UNKNOWN = "unknown"              #: unresolved
CONFLICT = "conflict"            #: the evidence disagrees
RECOMMENDATION = "recommendation"  #: proposed action given criteria

CLAIM_STATES: tuple[str, ...] = (
    FACT, INFERENCE, ASSUMPTION, UNKNOWN, CONFLICT, RECOMMENDATION,
)

# ---------------------------------------------------------------------
# Source quality, stated as principles rather than as a domain list
# ---------------------------------------------------------------------

#: The party the claim is ABOUT, or direct observation of it.
PRIMARY = "primary"
#: An independent party that corroborates.
CORROBORATION = "corroboration"
#: Useful for FINDING a candidate; not authoritative about it.
DISCOVERY = "discovery"

#: Ordered, strongest first. Domain-agnostic on purpose: "Steam is good,
#: Reddit is bad" is a hardcoded opinion that stops being true the moment
#: the claim type changes. An official product page is authoritative for
#: whether a demo exists and weak evidence about whether the game is any
#: good; an independent review is the reverse. The CLAIM decides which
#: source is strong, so the class travels with the assessment and not
#: with the hostname.
SOURCE_CLASSES: tuple[str, ...] = (PRIMARY, CORROBORATION, DISCOVERY)

# ---------------------------------------------------------------------
# Criterion states
# ---------------------------------------------------------------------

MET = "met"
UNMET = "unmet"
#: Not established either way. Never rounded up to MET -- an unverified
#: candidate that looks attractive is exactly the one that gets promoted
#: by accident.
UNVERIFIED = "unverified"

CRITERION_STATES: tuple[str, ...] = (MET, UNMET, UNVERIFIED)

# ---------------------------------------------------------------------
# How a deliberation ends
# ---------------------------------------------------------------------

DECIDED = "decided"
INSUFFICIENT_EVIDENCE = "insufficient_evidence"
CONTESTED = "contested"
FOUNDER_DECISION_REQUIRED = "founder_decision_required"

DECISION_STATES: tuple[str, ...] = (
    DECIDED, INSUFFICIENT_EVIDENCE, CONTESTED, FOUNDER_DECISION_REQUIRED,
)

# ---------------------------------------------------------------------
# Decision utility -- the anti-drift gate
# ---------------------------------------------------------------------

SATISFIES = "satisfies"                        #: directly satisfies a requirement
OBTAINS_EVIDENCE = "obtains_evidence"          #: evidence needed to assess one
REDUCES_UNCERTAINTY = "reduces_uncertainty"    #: unblocks a material unknown
RESOLVES_CONTRADICTION = "resolves_contradiction"
REDUCES_RISK = "reduces_risk"
UNBLOCKS = "unblocks"                          #: unblocks a covered step

#: The complete set of reasons an action may exist. Closed, and
#: load-bearing: an action that serves none of these is drift, however
#: interesting it looks. "While I am here, let me also collect..." is how
#: a research mission spends a budget and answers nothing.
UTILITY_GROUNDS: tuple[str, ...] = (
    SATISFIES, OBTAINS_EVIDENCE, REDUCES_UNCERTAINTY,
    RESOLVES_CONTRADICTION, REDUCES_RISK, UNBLOCKS,
)


@dataclass(frozen=True)
class Criterion:
    """One thing a candidate must (or would prefer to) satisfy.

    `mandatory` is the whole point of the split. A candidate failing a
    mandatory criterion is not a weak candidate -- it is not a candidate.
    A preference may only order the survivors, and may never rescue a
    disqualified one.
    """

    criterion_id: str
    description: str
    #: Which founder requirement this serves. A criterion serving none is
    #: a preference somebody invented.
    requirement_id: str = ""
    mandatory: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "description": self.description,
            "requirement_id": self.requirement_id,
            "mandatory": self.mandatory,
        }


@dataclass(frozen=True)
class DecisionFrame:
    """What is being decided, and what would settle it.

    Written BEFORE evidence is gathered. That order is deliberate: a
    frame written afterwards is a rationalisation of whatever turned up,
    and the criteria quietly become the shape of the data instead of the
    shape of the founder's request.
    """

    objective: str
    #: The founder requirements this decision serves.
    requirement_ids: tuple[str, ...] = ()
    decision_type: str = ""
    mandatory: tuple[Criterion, ...] = ()
    preferences: tuple[Criterion, ...] = ()
    constraints: tuple[str, ...] = ()
    #: Higher stakes buy deeper deliberation, not a different answer.
    stakes: str = ""
    reversible: bool = True
    #: What must be answered before this can be decided.
    questions: tuple[str, ...] = ()
    #: Used temporarily, and never silently.
    assumptions: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()
    stop_conditions: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "requirement_ids": list(self.requirement_ids),
            "decision_type": self.decision_type,
            "mandatory": [c.as_dict() for c in self.mandatory],
            "preferences": [c.as_dict() for c in self.preferences],
            "constraints": list(self.constraints),
            "stakes": self.stakes,
            "reversible": self.reversible,
            "questions": list(self.questions),
            "assumptions": list(self.assumptions),
            "unknowns": list(self.unknowns),
            "stop_conditions": list(self.stop_conditions),
        }


@dataclass(frozen=True)
class EvidenceAssessment:
    """One claim, and what the record actually supports about it.

    `evidence_ids` reference canonical Evidence. This is not a second
    Evidence store and never becomes one -- it is a reading OF Evidence,
    and a reading is not an observation.
    """

    claim: str
    evidence_ids: tuple[str, ...] = ()
    requirement_id: str = ""
    source_class: str = DISCOVERY
    state: str = UNKNOWN
    corroborated_by: tuple[str, ...] = ()
    contradicted_by: tuple[str, ...] = ()
    #: Freshness only where it is material to the claim.
    observed_at: str = ""
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim,
            "evidence_ids": list(self.evidence_ids),
            "requirement_id": self.requirement_id,
            "source_class": self.source_class,
            "state": self.state,
            "corroborated_by": list(self.corroborated_by),
            "contradicted_by": list(self.contradicted_by),
            "observed_at": self.observed_at,
            "note": self.note,
        }


@dataclass(frozen=True)
class Candidate:
    """One option, and how it stands against the frame."""

    candidate_id: str
    summary: str
    #: criterion_id -> MET / UNMET / UNVERIFIED
    criteria: Mapping[str, str] = field(default_factory=dict)
    supporting: tuple[str, ...] = ()
    contradicting: tuple[str, ...] = ()
    strengths: tuple[str, ...] = ()
    weaknesses: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "summary": self.summary,
            "criteria": dict(self.criteria),
            "supporting": list(self.supporting),
            "contradicting": list(self.contradicting),
            "strengths": list(self.strengths),
            "weaknesses": list(self.weaknesses),
            "risks": list(self.risks),
            "unknowns": list(self.unknowns),
        }


@dataclass(frozen=True)
class RejectedCandidate:
    candidate_id: str
    summary: str
    reason: str
    #: The mandatory criteria that were not met, by id.
    failed: tuple[str, ...] = ()
    unverified: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "summary": self.summary,
            "reason": self.reason,
            "failed": list(self.failed),
            "unverified": list(self.unverified),
        }


@dataclass(frozen=True)
class DeliberationResult:
    """What was decided, why, and what is still not known."""

    state: str
    shortlist: tuple[Candidate, ...] = ()
    rejected: tuple[RejectedCandidate, ...] = ()
    rationale: str = ""
    requirement_ids: tuple[str, ...] = ()
    unresolved: tuple[str, ...] = ()
    #: criterion_id -> what it actually asks, carried from the frame.
    #:
    #: A result that only knows `crit_2` cannot say what is missing to
    #: anything except the frame it came from. The Planner was being told
    #: "still unresolved: crit_2" and asked to go and settle it, which is
    #: not a question anybody can act on. What is unresolved is "the
    #: reading room is open on Sunday", and that is a sentence a plan can
    #: be built from.
    criteria: Mapping[str, str] = field(default_factory=dict)
    more_research: bool = False
    replan_needed: bool = False
    founder_decision_required: bool = False
    critique_performed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "shortlist": [c.as_dict() for c in self.shortlist],
            "rejected": [r.as_dict() for r in self.rejected],
            "rationale": self.rationale,
            "requirement_ids": list(self.requirement_ids),
            "unresolved": list(self.unresolved),
            "criteria": dict(self.criteria),
            "more_research": self.more_research,
            "replan_needed": self.replan_needed,
            "founder_decision_required": self.founder_decision_required,
            "critique_performed": self.critique_performed,
        }


# ---------------------------------------------------------------------
# The discipline. Arithmetic over recorded facts, not prompting.
# ---------------------------------------------------------------------


def serves(ground: str, requirement_id: str) -> bool:
    """Is a proposed action useful, and useful FOR WHAT?

    The anti-drift gate of ADR-0027. An action must name both a ground
    from the closed set and the requirement it serves. Naming neither is
    how a research mission wanders; naming a ground with no requirement
    is how it wanders while sounding rigorous.
    """
    return bool(requirement_id) and ground in UTILITY_GROUNDS


def depth_for(
    *,
    capability_is_deterministic: bool = False,
    evidence_items: int = 0,
    alternatives: int = 0,
    has_conflict: bool = False,
    reversible: bool = True,
    material_uncertainty: bool = False,
) -> str:
    """How much thinking this decision has earned.

    A deterministic capability with settled arguments is DIRECT and must
    stay DIRECT: creating a folder does not deliberate. "More
    intelligence" must not mean "AI everywhere" -- that is a cost the
    founder pays on every trivial request, and a latency they feel.

    Ordered so the expensive answers require a reason. Irreversibility
    and material uncertainty are the two things that buy CRITICAL,
    because those are the decisions whose mistakes cannot be walked back
    or noticed.
    """
    if capability_is_deterministic:
        return DIRECT
    if not reversible or material_uncertainty:
        return CRITICAL
    if has_conflict or alternatives > 1 or evidence_items > 2:
        return DELIBERATIVE
    return REASONED


def shortlist(
    candidates: Sequence[Candidate], frame: DecisionFrame
) -> tuple[tuple[Candidate, ...], tuple[RejectedCandidate, ...]]:
    """Only candidates that actually cleared every mandatory criterion.

    Three states, and the third is the one that matters. `UNMET` is a
    rejection. `UNVERIFIED` is ALSO a rejection from the shortlist --
    kept separately, because "we could not establish this" is a different
    thing to tell the founder than "this failed", and because it is the
    one worth gathering more evidence about.

    A candidate is never promoted because it looks strong on the
    preferences. Preferences order survivors; they do not rescue the
    disqualified.
    """
    selected: list[Candidate] = []
    rejected: list[RejectedCandidate] = []
    required = tuple(c.criterion_id for c in frame.mandatory if c.mandatory)

    for candidate in candidates:
        states = dict(candidate.criteria or {})
        failed = tuple(cid for cid in required if states.get(cid) == UNMET)
        unverified = tuple(
            cid for cid in required if states.get(cid, UNVERIFIED) != MET
            and states.get(cid) != UNMET
        )
        if failed:
            rejected.append(RejectedCandidate(
                candidate_id=candidate.candidate_id,
                summary=candidate.summary,
                reason="a mandatory criterion was not met",
                failed=failed, unverified=unverified,
            ))
            continue
        if unverified:
            rejected.append(RejectedCandidate(
                candidate_id=candidate.candidate_id,
                summary=candidate.summary,
                reason="a mandatory criterion could not be established",
                unverified=unverified,
            ))
            continue
        selected.append(candidate)

    return tuple(selected), tuple(rejected)


def adjudicate(assessments: Sequence[EvidenceAssessment]) -> tuple[EvidenceAssessment, ...]:
    """Settle disagreeing evidence by authority, or record that it stands.

    Never by averaging, by whichever source arrived first, or by whichever
    wording reads better. Those are the three ways a system launders a
    contradiction into a confident sentence.

    A claim contradicted by something weaker than a PRIMARY source, where
    a PRIMARY source exists for the same claim, is resolved in favour of
    the primary. Anything else stays `CONFLICT` and becomes something the
    founder is told about and, if it matters, something worth more
    research.
    """
    by_claim: dict[str, list[EvidenceAssessment]] = {}
    for item in assessments:
        by_claim.setdefault(item.claim.strip().lower(), []).append(item)

    settled: list[EvidenceAssessment] = []
    for group in by_claim.values():
        if len(group) == 1:
            settled.append(group[0])
            continue
        primaries = [a for a in group if a.source_class == PRIMARY]
        if len(primaries) == 1:
            winner = primaries[0]
            others = tuple(
                a.source_class for a in group if a is not winner
            )
            settled.append(EvidenceAssessment(
                claim=winner.claim,
                evidence_ids=winner.evidence_ids,
                requirement_id=winner.requirement_id,
                source_class=PRIMARY,
                state=FACT if winner.state in (FACT, UNKNOWN, CONFLICT) else winner.state,
                corroborated_by=winner.corroborated_by,
                contradicted_by=winner.contradicted_by,
                observed_at=winner.observed_at,
                note=(
                    "a primary source settled a disagreement with "
                    + ", ".join(others)
                ),
            ))
            continue
        # No single primary source. The disagreement is real and stays
        # visible -- an unresolved conflict reported as a conflict is a
        # true answer; one resolved by preference is a false one.
        merged_ids = tuple(dict.fromkeys(i for a in group for i in a.evidence_ids))
        settled.append(EvidenceAssessment(
            claim=group[0].claim,
            evidence_ids=merged_ids,
            requirement_id=group[0].requirement_id,
            source_class=min(
                (a.source_class for a in group), key=SOURCE_CLASSES.index
            ),
            state=CONFLICT,
            contradicted_by=merged_ids,
            note="sources disagree and no primary source resolves it",
        ))
    return tuple(settled)


def sufficient(
    frame: DecisionFrame,
    candidates: Sequence[Candidate],
    assessments: Sequence[EvidenceAssessment] = (),
    *,
    budget_exhausted: bool = False,
) -> tuple[bool, str]:
    """Should research stop? Returns `(stop, why)`.

    A strong researcher does not stop because the first page loaded, and
    does not stop because a token budget is nearly spent. It stops when
    the decision is supported.

    `budget_exhausted` stops it too -- but that is a different answer,
    and the caller must report the remaining uncertainty truthfully
    rather than presenting a budget stop as a finished one.
    """
    required = tuple(c.criterion_id for c in frame.mandatory if c.mandatory)
    qualifying, _ = shortlist(candidates, frame)

    if budget_exhausted:
        return True, "the research budget was reached; unknowns remain unresolved"

    unresolved = [a.claim for a in assessments if a.state == CONFLICT]
    if unresolved:
        return False, (
            "credible sources still disagree about: " + "; ".join(unresolved[:3])
        )

    # Before anything is judged: an empty field is not a field of
    # failures. "No candidate can qualify" and "we have not looked yet"
    # are opposite answers, and reaching the first one from zero
    # candidates would end a research mission before it started.
    if not candidates:
        return False, "nothing has been found yet"

    if required and not qualifying:
        unverified = any(
            (c.criteria or {}).get(cid, UNVERIFIED) not in (MET, UNMET)
            for c in candidates for cid in required
        )
        if unverified:
            return False, "mandatory criteria remain unestablished for every candidate"
        return True, "no candidate can satisfy the mandatory criteria"

    return True, "every mandatory criterion is established for at least one candidate"


# ---------------------------------------------------------------------
# Method failure is not objective failure
# ---------------------------------------------------------------------

#: One source could not supply evidence. Other sources exist.
SOURCE_FAILURE = "source_failure"
#: This plan cannot continue. The objective may still be reachable.
METHOD_FAILURE = "method_failure"
#: No safe executable route remains within policy and budget.
OBJECTIVE_FAILURE = "objective_failure"

FAILURE_CLASSES: tuple[str, ...] = (
    SOURCE_FAILURE, METHOD_FAILURE, OBJECTIVE_FAILURE,
)


@dataclass(frozen=True)
class RecoveryDecision:
    """Whether a failed method is worth replacing, and with what.

    The founder saw *"That didn't complete."* about a mission that had
    never reached the web: one step failed to open a browser and the
    objective was declared failed 1.3 seconds later. Nine planned steps
    never ran, and at least two of them named different sources.

    `MissionDispatcher` was right to stop -- its own comment says
    auto-retry "would be a strategic recovery decision, which belongs to
    the Brain". The seam was correct and nothing stood behind it.
    """

    failure_class: str
    should_replan: bool
    reason: str
    #: What the next attempt must change. A re-plan that differs in
    #: nothing is the same plan run twice.
    must_differ: tuple[str, ...] = ()
    attempts_remaining: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "failure_class": self.failure_class,
            "should_replan": self.should_replan,
            "reason": self.reason,
            "must_differ": list(self.must_differ),
            "attempts_remaining": self.attempts_remaining,
        }


#: How many times one mission may change its method. Small on purpose:
#: recovery exists to survive a bad source, not to grind. Each attempt
#: costs the founder time they are sitting through.
DEFAULT_RECOVERY_BUDGET = 2

#: What a new attempt may differ in. Closed, because "try again" is not a
#: difference and retrying an identical plan is the loop this bounds.
DIFFERENTIATORS: tuple[str, ...] = (
    "source", "method", "capability", "environment",
    "evidence_question", "strategy",
)


def classify_failure(
    *,
    unmet_requirements: Sequence[str],
    alternatives_available: bool,
    transient: bool = False,
) -> str:
    """Which of the three failures this is.

    The distinction the founder paid for. A site that will not answer is
    a SOURCE failure; a plan that cannot continue is a METHOD failure;
    only "nothing safe remains" is an OBJECTIVE failure. Collapsing the
    first two into the third is how a founder is told their request
    cannot be done when it was never attempted.
    """
    if not unmet_requirements:
        return SOURCE_FAILURE
    if alternatives_available or transient:
        return METHOD_FAILURE
    return OBJECTIVE_FAILURE


def recovery_for(
    *,
    unmet_requirements: Sequence[str],
    alternatives_available: bool,
    attempts_used: int = 0,
    budget: int = DEFAULT_RECOVERY_BUDGET,
    transient: bool = False,
    previous_methods: Sequence[str] = (),
    proposed_method: str = "",
) -> RecoveryDecision:
    """Is another attempt worth making, and what must it change?

    Bounded in both directions. It refuses to give up while a safe
    untried route exists and a requirement is unmet; it equally refuses
    to keep going once the budget is spent, once nothing is left to try,
    or once the only proposal on offer repeats something already tried.
    """
    failure_class = classify_failure(
        unmet_requirements=unmet_requirements,
        alternatives_available=alternatives_available,
        transient=transient,
    )
    remaining = max(0, budget - attempts_used)

    if not unmet_requirements:
        return RecoveryDecision(
            failure_class, False,
            "every founder requirement is already satisfied",
            attempts_remaining=remaining,
        )
    if remaining <= 0:
        return RecoveryDecision(
            failure_class, False,
            "the recovery budget for this mission is spent",
            attempts_remaining=0,
        )
    if not alternatives_available and not transient:
        return RecoveryDecision(
            OBJECTIVE_FAILURE, False,
            "no safe alternative method remains",
            attempts_remaining=remaining,
        )
    if proposed_method and proposed_method in set(previous_methods):
        # Repeating a method that already failed is not recovery. The
        # exception is a genuinely transient failure, where the SAME
        # method is the right thing to try -- and that is why `transient`
        # has to be established from Evidence rather than assumed.
        if not transient:
            return RecoveryDecision(
                failure_class, False,
                f"the proposed method was already tried and failed: {proposed_method}",
                must_differ=DIFFERENTIATORS, attempts_remaining=remaining,
            )

    return RecoveryDecision(
        failure_class, True,
        "a founder requirement is unmet and a safe untried route remains",
        must_differ=DIFFERENTIATORS, attempts_remaining=remaining,
    )


# ---------------------------------------------------------------------
# Framing, from what is already canonical
# ---------------------------------------------------------------------

#: Requirement kinds whose satisfaction is a matter of judgement rather
#: than of a single deterministic act. An EFFECT ("create a folder") is
#: done or not; INFORMATION and DELIVERABLE requirements are the ones
#: where candidates, sources and sufficiency exist at all.
_JUDGED_KINDS = frozenset({"information", "deliverable"})


def frame_for(
    *,
    objective: str,
    requirements: Sequence[Any] = (),
    capability: str = "",
    reversible: bool = True,
) -> DecisionFrame | None:
    """The decision this mission actually faces, or `None` if none.

    `None` is the common answer and the important one. A founder asking
    for a folder is not facing a decision: the capability is known, the
    arguments are settled, and there is nothing to weigh. Returning a
    frame there would buy a reasoning call, latency the founder feels,
    and an opportunity to be wrong about something that was never in
    doubt. "More intelligence" must not mean "AI everywhere" (ADR-0027).

    Nothing here reinterprets what the founder meant. The criteria are
    the requirements the Intent Layer already derived, one for one, with
    their ids preserved -- so every criterion traces to a requirement and
    every requirement keeps its founder evidence. A frame that invented
    its own criteria would be a second semantic authority, which is
    exactly what ADR-0026 removed.
    """
    kept = tuple(requirements or ())
    if not kept:
        # Nothing was established to decide about.
        return None

    # ONE owner for "how much thinking has this earned".
    #
    # `depth_for` was written as that owner and then never called, while
    # this function decided the same thing again from the capability name
    # -- two answers to one question, free to drift, and the kind of
    # duplication only ever noticed once they disagree. A typed
    # capability with settled arguments is DIRECT, and DIRECT does not
    # deliberate.
    if depth_for(
        capability_is_deterministic=bool(capability),
        alternatives=len(kept),
        reversible=reversible,
    ) == DIRECT:
        return None

    # Every requirement becomes a criterion, and the KIND only chooses
    # the label.
    #
    # Framing deliberately does not hinge on the kind, because the kind
    # comes from a model. Measured twice on the same research objective,
    # the extractor labelled its requirements `information` +
    # `deliverable` on one run and `information` + three `constraint`s on
    # the next -- so keying the existence of a frame off those labels
    # made "does this mission think at all" depend on a word a model
    # happened to choose. The stable fact is structural: an intent with
    # no typed capability took the compound lane, which is where evidence
    # is gathered and candidates exist.
    judged = tuple(
        requirement for requirement in kept
        if str(getattr(requirement, "kind", "")).lower() in _JUDGED_KINDS
    )

    mandatory = tuple(
        Criterion(
            criterion_id=f"crit_{index}",
            description=str(getattr(requirement, "description", "")),
            requirement_id=str(getattr(requirement, "requirement_id", "")),
            mandatory=bool(getattr(requirement, "required", True)),
        )
        for index, requirement in enumerate(kept, start=1)
    )
    return DecisionFrame(
        objective=objective,
        requirement_ids=tuple(
            str(getattr(r, "requirement_id", "")) for r in kept
        ),
        decision_type="research_shortlist" if len(judged) > 1 else "assessment",
        mandatory=mandatory,
        stakes="reversible" if reversible else "consequential",
        reversible=reversible,
        questions=tuple(
            f"what evidence establishes: {c.description}" for c in mandatory
        ),
        stop_conditions=(
            "every mandatory criterion is established for at least one candidate",
            "credible sources disagree and no primary source resolves it",
            "the research budget for this mission is reached",
        ),
    )


# ---------------------------------------------------------------------
# Turning observations into a decision
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class Observation:
    """One thing a Worker actually saw, with its canonical Evidence id.

    A Worker reports *what a page said*. It does not report whether that
    qualifies -- that is the Brain's, and keeping the two apart is the
    whole reason this type exists rather than passing raw text around.
    """

    evidence_id: str
    text: str
    source_class: str = DISCOVERY
    url: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "text": self.text,
            "source_class": self.source_class,
            "url": self.url,
        }


def source_labels(observations: Sequence[Observation]) -> dict[str, str]:
    """`source_1`, `source_2`, ... -> the real evidence id.

    The guard in `candidates_from` requires every `met` to cite an
    observation that was actually supplied, and that guard is right. What
    was wrong was asking a model to prove it by transcribing a 36-
    character UUID.

    Measured. The live H objective, with ONE observation, decided
    cleanly. The demo centrepiece, with two, rejected the one candidate
    that needed to cite BOTH of them -- the correct answer -- as "a
    mandatory criterion could not be established", while correctly
    rejecting the two candidates that each needed only one citation. A
    correct claim was being lost to a copying error, and it looked
    exactly like the model failing to establish a fact it had in front of
    it.

    Short labels change nothing about what is enforced: a citation naming
    no supplied source is still refused, and `met` with no citation at
    all is still refused. They only stop a right answer from failing on
    transcription.
    """
    return {
        f"source_{index}": observation.evidence_id
        for index, observation in enumerate(observations, start=1)
    }


def _extraction_prompt(frame: DecisionFrame, observations: Sequence[Observation]) -> str:
    lines = [
        "You are reading observations that were gathered for one decision.",
        "",
        f"THE DECISION: {frame.objective}",
        "",
        "CRITERIA. Each candidate must be reported against every one:",
    ]
    for criterion in frame.mandatory:
        lines.append(f"  {criterion.criterion_id}: {criterion.description}")
    lines += ["", "OBSERVATIONS. Each has a label you must cite exactly:"]
    labels = {evidence_id: label for label, evidence_id in
              source_labels(observations).items()}
    for observation in observations:
        lines.append(
            f"  [{labels[observation.evidence_id]}] ({observation.source_class}) "
            f"{observation.text[:1500]}"
        )
    lines += [
        "",
        "Reply with JSON only:",
        '  {"candidates": [{"id": "...", "summary": "<the candidate\'s NAME only>",',
        '     "criteria": {"<criterion_id>": {"state": "met|unmet|unverified",',
        '                                     "evidence_id": "<source label, or empty>"}}}]}',
        "",
        "Rules. Report only what the observations SUPPORT. A state of met "
        "requires a source label from the list above that actually shows it, "
        "copied exactly as written -- different criteria of the same "
        "candidate often come from different sources, and each must cite "
        "the one that shows IT; "
        "if the observations do not establish a criterion, say unverified -- "
        "that is a useful answer and guessing is not. A state of unmet means "
        "an observation shows it is false, not that you could not find it. "
        "Report EVERY candidate the observations mention, including ones "
        "you cannot fully assess -- a candidate with an unverified "
        "criterion is the useful answer, because it says what to go and "
        "find next. Returning nothing because you could not confirm "
        "everything throws that away. "
        "Do not add candidates the observations do not mention. "
        "`summary` is the candidate's NAME and nothing else -- not a "
        "description, not the evidence, not your reasoning about it. A "
        "founder reads that field.",
    ]
    return "\n".join(lines)


def candidates_from(
    frame: DecisionFrame,
    observations: Sequence[Observation],
    reasoner: Any = None,
) -> tuple[Candidate, ...]:
    """What the observations offer as options, structurally validated.

    A model reads prose into structure here, and that is all it does. It
    does not decide what qualifies: `shortlist()` does, deterministically,
    from the states below.

    ## The guard that matters

    Every `met` must cite an evidence id that was actually supplied. A
    model asserting a criterion with no reference -- or citing an id
    nobody gave it -- has its claim **downgraded to `unverified`**, not
    accepted and not discarded. That is the difference between "the demo
    is free" and "something said the demo is free", and it is exactly
    where a research answer turns into a dead link in a founder's hands.

    ADR-0026 settled the principle: prompt compliance is not a
    constraint. The instruction above asks the model not to guess; this
    check is what makes it true.
    """
    if reasoner is None or not observations or not frame.mandatory:
        return ()

    from master_agent.ai_infrastructure.budgeted_request import (
        BudgetedSelectionRequest,
    )
    from master_agent.ai_infrastructure.workload import INTERACTIVE
    from master_agent.plugins.model_router import (
        REASONING,
        RoutingContext,
        SelectionRequest,
    )

    prompt = _extraction_prompt(frame, observations)
    context = RoutingContext(
        is_online=True,
        # Reading several sources into candidates is a real judgement,
        # unlike the narrow field extraction the Intent Layer does.
        requires_strong_reasoning=True,
        # The REGISTERED capability name, not the action's name.
        #
        # This asked for "reasoning.transform" and the Broker answered
        # "11 provider(s) considered, none eligible: does not offer this
        # capability" -- every time, silently, because `candidates_from`
        # returns `()` on any unusable answer. Deliberation reported
        # "nothing has been found yet" about pages it had never actually
        # been given a model to read.
        capability=REASONING,
        requester="brain_deliberation_candidates",
    )
    request = BudgetedSelectionRequest(
        **vars(SelectionRequest.from_context(context)),
        request_class=INTERACTIVE,
        prompt=prompt,
    )
    try:
        outcome = reasoner.run(prompt, request)
    except Exception:  # noqa: BLE001 -- a dead ladder decides nothing
        return ()
    if outcome is None or not getattr(outcome, "ok", False):
        return ()

    import json
    import re

    text = getattr(outcome, "text", "") or ""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return ()
    try:
        document = json.loads(match.group(0))
    except Exception:  # noqa: BLE001 -- unverified output never becomes a decision
        return ()

    known_criteria = {c.criterion_id for c in frame.mandatory}
    known_evidence = {o.evidence_id for o in observations}
    # `source_2` -> the real id. A model that quotes the real id instead
    # is not wrong either, so both are accepted; anything else is still
    # a citation of nothing.
    by_label = source_labels(observations)
    built: list[Candidate] = []

    for index, row in enumerate(document.get("candidates") or [], start=1):
        if not isinstance(row, dict):
            continue
        # The NAME, enforced rather than requested.
        #
        # Measured on the first real run: the model returned summaries
        # like "Free Steam demo listed with a 15 Jun 2026 date. Evidence:
        # c43598d0-...: crit_2" -- the whole of its working, in the one
        # field a founder reads. ADR-0026 settled the principle that an
        # instruction to a model is not a constraint; this is the
        # constraint.
        summary = str(row.get("summary") or row.get("id") or "").strip()
        summary = summary.splitlines()[0].strip() if summary else ""
        for separator in (". Evidence:", " Evidence:", " -- ", ": crit_"):
            if separator in summary:
                summary = summary.split(separator, 1)[0].strip()
        summary = summary[:80].strip()
        if not summary:
            continue
        states: dict[str, str] = {}
        supporting: list[str] = []
        unknowns: list[str] = []
        offered = row.get("criteria")
        if not isinstance(offered, dict):
            offered = {}
        for criterion_id in known_criteria:
            claim = offered.get(criterion_id)
            if not isinstance(claim, dict):
                states[criterion_id] = UNVERIFIED
                continue
            state = str(claim.get("state") or "").strip().lower()
            cited = str(claim.get("evidence_id") or "").strip()
            evidence_id = by_label.get(cited.lower(), cited)
            if state not in CRITERION_STATES:
                states[criterion_id] = UNVERIFIED
                continue
            if state == MET and evidence_id not in known_evidence:
                # Asserted without anything to stand on. Downgraded
                # rather than believed -- this is the line between a
                # supported link and a plausible one.
                states[criterion_id] = UNVERIFIED
                unknowns.append(
                    f"{criterion_id} was claimed met with no usable evidence"
                )
                continue
            states[criterion_id] = state
            if evidence_id in known_evidence and evidence_id not in supporting:
                supporting.append(evidence_id)
        built.append(Candidate(
            candidate_id=str(row.get("id") or f"cand_{index}"),
            summary=summary,
            criteria=states,
            supporting=tuple(supporting),
            unknowns=tuple(unknowns),
        ))
    return tuple(built)


def deliberate(
    frame: DecisionFrame,
    observations: Sequence[Observation],
    reasoner: Any = None,
    *,
    budget_exhausted: bool = False,
) -> DeliberationResult:
    """The whole decision, from what was observed to what is concluded.

    The model's only job was reading prose into structure. Everything
    from here is arithmetic over that structure: which candidates cleared
    their criteria, whether sources disagree, and whether the evidence is
    enough. A model asked to grade this would be a model grading a model.
    """
    candidates = candidates_from(frame, observations, reasoner)

    by_evidence = {o.evidence_id: o for o in observations}
    # Keyed by CANDIDATE and criterion, not by summary text.
    #
    # `adjudicate` groups assessments that make the same claim, which is
    # how genuine disagreement between sources is found. Building the
    # claim from the summary alone made every criterion of every
    # similarly-named candidate collide, and the first real run came back
    # CONTESTED because six Steam listings shared a phrase -- a
    # contradiction invented out of string equality, about sources that
    # never disagreed with each other.
    assessments = tuple(
        EvidenceAssessment(
            claim=f"{candidate.candidate_id}/{criterion_id}: {candidate.summary}",
            evidence_ids=candidate.supporting,
            requirement_id=next(
                (c.requirement_id for c in frame.mandatory
                 if c.criterion_id == criterion_id), "",
            ),
            source_class=next(
                (by_evidence[e].source_class for e in candidate.supporting
                 if e in by_evidence), DISCOVERY,
            ),
            state=FACT if state == MET else UNKNOWN,
        )
        for candidate in candidates
        for criterion_id, state in (candidate.criteria or {}).items()
    )
    settled = adjudicate(assessments)
    selected, rejected = shortlist(candidates, frame)
    stop, why = sufficient(
        frame, candidates, settled, budget_exhausted=budget_exhausted
    )

    # CONFLICT only ever means sources that actually contradict each
    # other. An unestablished criterion is not a contradiction -- it is
    # something nobody has shown yet, which `shortlist` already reports
    # as `unverified` and which more research can answer.
    contested = tuple(
        a.claim for a in settled
        if a.state == CONFLICT and a.contradicted_by
    )
    unresolved = tuple(dict.fromkeys(
        list(contested)
        + [u for candidate in candidates for u in candidate.unknowns]
    ))

    if contested:
        state = CONTESTED
    elif selected and stop:
        state = DECIDED
    else:
        state = INSUFFICIENT_EVIDENCE

    return DeliberationResult(
        state=state,
        shortlist=selected,
        rejected=rejected,
        rationale=why,
        requirement_ids=frame.requirement_ids,
        unresolved=unresolved,
        criteria={c.criterion_id: c.description for c in frame.mandatory},
        more_research=not stop,
        founder_decision_required=False,
    )


# ---------------------------------------------------------------------
# Where the mission actually stands
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class MissionProgress:
    """What a mission has verifiably achieved, and what it has not.

    ## The distinction this exists to hold

    The founder's research run produced, all of them true at once:

        OpenBrowserSession   matched
        Navigate             matched
        ReadPageText         matched
        page text            "Error 500 - Server Internal Error"

    Every step was independently verified. No founder requirement was
    satisfied. **A verified step is not a satisfied requirement**, and a
    recovery that confused the two would either throw away real evidence
    or believe the objective was progressing when it was not.

    Derived, never stored: requirements come from the Intent Layer,
    verdicts and Evidence from Verification, routes from the plan. This
    reads those records; it does not become a second one.
    """

    objective: str = ""
    satisfied: tuple[str, ...] = ()
    unresolved: tuple[str, ...] = ()
    #: Steps that verified. Real facts about execution that may satisfy
    #: nothing -- opening a browser is one.
    verified_steps: tuple[str, ...] = ()
    #: Canonical Evidence already gathered. Kept across a replan: it was
    #: independently observed and does not stop being true because a
    #: later step failed.
    evidence_ids: tuple[str, ...] = ()
    #: What was attempted and did not work -- capability plus target, so
    #: a new plan can differ from it rather than repeat it.
    failed_routes: tuple[str, ...] = ()
    #: Routes that DID work, so a replan need not rediscover them.
    successful_routes: tuple[str, ...] = ()

    @property
    def anything_satisfied(self) -> bool:
        return bool(self.satisfied)

    @property
    def useful_progress(self) -> bool:
        """Did the attempt move the objective, or only spend time?

        A failed source still counts when it produced Evidence or
        eliminated a route: knowing a source is unusable is knowledge,
        and it is what stops the next attempt repeating it. What does not
        count is an attempt that satisfied nothing, learned nothing and
        ruled nothing out.
        """
        return bool(self.satisfied or self.evidence_ids or self.failed_routes)

    def as_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "satisfied": list(self.satisfied),
            "unresolved": list(self.unresolved),
            "verified_steps": list(self.verified_steps),
            "evidence_ids": list(self.evidence_ids),
            "failed_routes": list(self.failed_routes),
            "successful_routes": list(self.successful_routes),
        }


def _route_of(task: Any) -> str:
    """A step as a comparable route: what it did, and to what.

    The target matters as much as the capability -- two Navigates are the
    same capability and entirely different attempts. Read off the payload
    rather than named here, so nothing in the Brain has to know what a
    URL is.
    """
    capability = str(getattr(task, "capability", "") or "")
    payload = getattr(task, "payload", None) or {}
    target = ""
    if isinstance(payload, dict):
        for key in ("url", "path", "query", "instruction"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                target = value.strip()
                break
    return f"{capability} {target}".strip()


def progress_of(objective: str, requirements: Sequence[Any], tasks: Sequence[Any]) -> MissionProgress:
    """Read the mission's standing off the records that already hold it.

    Requirement status comes from `conformance.assess` -- the same
    judgement the founder is shown, so recovery and reporting can never
    disagree about what was achieved.
    """
    from master_agent.brain.conformance import _MATCHED, SATISFIED, assess

    outcome = assess(requirements, tasks)
    satisfied = tuple(
        row.requirement_id for row in outcome.requirements
        if row.state == SATISFIED
    )
    unresolved = tuple(
        row.requirement_id for row in outcome.requirements
        if row.state != SATISFIED
    )

    verified: list[str] = []
    evidence: list[str] = []
    failed: list[str] = []
    succeeded: list[str] = []
    for task in tasks or ():
        record = getattr(task, "evidence", None) or {}
        verdict = str(record.get("verdict") or "") if isinstance(record, dict) else ""
        route = _route_of(task)
        if verdict == _MATCHED:
            verified.append(str(getattr(task, "task_id", "")))
            if route:
                succeeded.append(route)
        elif verdict or str(getattr(task, "errors", "") or ""):
            if route:
                failed.append(route)
        if isinstance(record, dict):
            evidence_id = str(record.get("evidence_id") or "")
            if evidence_id:
                evidence.append(evidence_id)

    return MissionProgress(
        objective=objective,
        satisfied=satisfied,
        unresolved=unresolved,
        verified_steps=tuple(verified),
        evidence_ids=tuple(dict.fromkeys(evidence)),
        failed_routes=tuple(dict.fromkeys(failed)),
        successful_routes=tuple(dict.fromkeys(succeeded)),
    )


def no_useful_progress(previous: MissionProgress, current: MissionProgress) -> bool:
    """Did this attempt change anything that matters?

    The rule, stated once:

        same requirement standing
        + no new canonical Evidence
        + no route eliminated
        = NO USEFUL PROGRESS

    Repeating after this is not persistence, it is a loop. The caller
    changes strategy or says truthfully that it is blocked.
    """
    return (
        set(current.satisfied) == set(previous.satisfied)
        and set(current.evidence_ids) <= set(previous.evidence_ids)
        and set(current.failed_routes) <= set(previous.failed_routes)
    )
