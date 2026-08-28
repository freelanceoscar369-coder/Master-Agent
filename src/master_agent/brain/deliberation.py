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
    if capability:
        # A typed capability with settled arguments. Deterministic, and
        # it stays that way.
        return None
    if not kept:
        # Nothing was established to decide about.
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
