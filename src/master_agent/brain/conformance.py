"""Did the mission satisfy what the founder asked for?

## The gap this closes

`brain/reporter.py` reported, in as many words:

    "founder_outcome_conformance": "not_evaluated"

An honest admission, and a serious one. The system could tell a founder
that every step had been independently verified without being able to say
whether the thing they asked for had happened. Those are different
questions, and only the second one is theirs.

## What this is, and what it is emphatically not

Verification answers *"what did reality show for this Step?"* — freshly
observed, independent of the Executive that acted, per ADR-0011. This
answers a different question that can only be asked afterwards:

    Given those independently verified facts, did the Mission satisfy the
    founder's stated requirements?

So it consumes Evidence and never produces any. Its vocabulary is
deliberately different — `SATISFIED` / `NOT_SATISFIED` / `UNKNOWN`, never
`MATCHED` / `NOT_MATCHED` — because a conformance state is a Brain
judgement about correspondence and a `Verdict` is an observation of
reality, and a codebase that spells them the same way will eventually
treat them the same way.

## No model is involved

None is needed. Requirements are recorded, coverage is recorded, Evidence
is recorded; the relationship between them is arithmetic. A model asked
to grade this would be a model grading a model, which ADR-0026 rejects
and ADR-0011 exists to prevent.

## Conservative on purpose

`UNKNOWN` is a real answer and is never rounded up. A requirement with no
coverage, a covering step that produced no Evidence, a mission with no
semantic trace at all: each of those is something the machine does not
know, and saying "Done" about any of them is the failure this module was
built to end.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

#: Brain semantic states. Deliberately NOT `Verdict` -- see the module
#: docstring, and ADR-0026's rejected alternative 5.
SATISFIED = "satisfied"
NOT_SATISFIED = "not_satisfied"
UNKNOWN = "unknown"

#: Verification's own vocabulary, read but never written here.
_MATCHED = "matched"


@dataclass(frozen=True)
class RequirementOutcome:
    """One requirement, and what the evidence says about it."""

    requirement_id: str
    description: str
    required: bool
    state: str
    #: The steps that claimed responsibility for it.
    covered_by: tuple[str, ...] = ()
    #: Why this state, in terms a founder could be shown.
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "description": self.description,
            "required": self.required,
            "state": self.state,
            "covered_by": list(self.covered_by),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class OutcomeConformance:
    """Whether the mission satisfied the founder, and why."""

    state: str
    requirements: tuple[RequirementOutcome, ...] = field(default_factory=tuple)
    reason: str = ""

    @property
    def unmet(self) -> tuple[RequirementOutcome, ...]:
        return tuple(r for r in self.requirements if r.state == NOT_SATISFIED)

    @property
    def unproven(self) -> tuple[RequirementOutcome, ...]:
        return tuple(r for r in self.requirements if r.state == UNKNOWN)

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "reason": self.reason,
            "requirements": [r.as_dict() for r in self.requirements],
        }


def _field(row: Any, name: str, default: Any = "") -> Any:
    """One field of a requirement, however it arrived.

    Durable history stores requirements as plain JSON; the Planner holds
    them as `SemanticRequirement`. Both are legitimate shapes of the same
    fact, and reading them through one accessor is cheaper -- and harder
    to get wrong -- than a parallel adapter class that has to be
    remembered at every call site.

    It was got wrong: `assess()` took attributes only, the Reporter
    handed it stored rows, the `AttributeError` was swallowed by the
    reporting path's own guard, and a mission that had genuinely
    succeeded reported "I can't reconstruct a verified mission summary".
    """
    if isinstance(row, Mapping):
        value = row.get(name, default)
    else:
        value = getattr(row, name, default)
    return default if value is None else value


def _verdict_of(task: Any) -> str:
    evidence = getattr(task, "evidence", None) or {}
    return str(evidence.get("verdict") or "")


def _decision_field(decision: Any, name: str, default: Any = None) -> Any:
    if decision is None:
        return default
    if isinstance(decision, Mapping):
        value = decision.get(name, default)
    else:
        value = getattr(decision, name, default)
    return default if value is None else value


def _canonical_evidence_gaps(decision: Any) -> tuple[set[str], set[str]]:
    """Requirement ids the canonical candidate decision cannot support.

    Candidate deliberation and Founder conformance used to read the same
    Evidence through unrelated projections: every covering task could be
    ``matched`` while every candidate still had a mandatory criterion
    marked ``unverified``.  This is the join.  It never creates Evidence;
    it only prevents task-level success from outranking the Brain's
    claim-level reading of that Evidence.
    """
    if decision is None:
        return set(), set()

    criterion_requirements = dict(
        _decision_field(decision, "criterion_requirements", {}) or {}
    )
    raw_candidates = tuple(_decision_field(decision, "candidates", ()) or ())
    if not raw_candidates:
        # Backward-compatible durable records may have only the two
        # projections. Rejected rows now retain full criterion state.
        raw_candidates = tuple(
            _decision_field(decision, "shortlist", ()) or ()
        ) + tuple(_decision_field(decision, "rejected", ()) or ())

    gaps: set[str] = set()
    for criterion_id, requirement_id in criterion_requirements.items():
        requirement_id = str(requirement_id or "")
        if not requirement_id:
            continue
        if not raw_candidates:
            gaps.add(requirement_id)
            continue
        for candidate in raw_candidates:
            states = dict(_decision_field(candidate, "criteria", {}) or {})
            evidence = dict(
                _decision_field(candidate, "criterion_evidence", {}) or {}
            )
            state = str(states.get(criterion_id) or "unverified")
            cited = tuple(evidence.get(criterion_id) or ())
            if state not in ("met", "unmet") or not cited:
                gaps.add(requirement_id)
                break

    undecided: set[str] = set()
    if str(_decision_field(decision, "state", "") or "") != "decided":
        undecided.update(
            str(item) for item in (
                _decision_field(decision, "decision_requirement_ids", ()) or ()
            ) if str(item)
        )

        # A progressive candidate mission may establish its prerequisite
        # states before the final recommendation is possible.  Treating
        # every mission-level decision requirement as blocked until the
        # whole candidate decision was final made verified discovery stay
        # UNKNOWN, so MissionProgress could never reflect the observation
        # that was meant to advance it.
        prerequisites = tuple(
            str(item) for item in (
                _decision_field(decision, "candidate_prerequisite_ids", ()) or ()
            ) if str(item)
        )
        candidates_present = bool(
            _decision_field(decision, "candidates", ())
            or _decision_field(decision, "rejected", ())
            or _decision_field(decision, "shortlist", ())
        )
        shortlist_present = bool(_decision_field(decision, "shortlist", ()))
        if candidates_present and prerequisites:
            # The first prerequisite is the state that introduces the
            # subjects. Candidate state is canonical proof that it exists;
            # task Evidence still decides whether its requirement is
            # satisfied below.
            undecided.discard(prerequisites[0])
        if shortlist_present:
            # A canonical shortlist establishes every candidate-set
            # prerequisite. It does not establish any criterion or final
            # recommendation requirement.
            undecided.difference_update(prerequisites)
    return gaps, undecided


def assess(
    requirements: Any, tasks: Any, deliberation: Any = None,
) -> OutcomeConformance:
    """The mission's conformance, from requirements, coverage and Evidence.

    `tasks` are Mission Control's own tasks -- each carrying the
    `covers` its Step declared and whatever Evidence Verification
    produced for it. Nothing here re-derives meaning from prose, and
    nothing here asks a provider.
    """
    requirements = tuple(requirements or ())
    tasks = list(tasks or ())

    if not requirements:
        # A mission with no semantic trace. Legacy records and
        # hand-built plans land here, and the honest answer is that
        # correspondence was never established -- not that it failed,
        # and certainly not that it held.
        return OutcomeConformance(
            state=UNKNOWN,
            reason="this mission carries no recorded founder requirements",
        )

    by_requirement: dict[str, list[Any]] = {}
    for task in tasks:
        for requirement_id in tuple(getattr(task, "covers", ()) or ()):
            by_requirement.setdefault(str(requirement_id), []).append(task)

    evidence_gaps, undecided_requirements = _canonical_evidence_gaps(deliberation)

    outcomes: list[RequirementOutcome] = []
    for requirement in requirements:
        requirement_id = str(_field(requirement, "requirement_id"))
        description = str(_field(requirement, "description"))
        required = bool(_field(requirement, "required", True))
        covering = by_requirement.get(requirement_id, [])
        ids = tuple(str(getattr(t, "task_id", "")) for t in covering)

        if str(_field(requirement, "interpretation", "known")) != "known":
            # The system is not sure it understood this. Whatever
            # execution proved, it proved it about a reading nobody
            # confirmed -- and reporting that as satisfied is the
            # circular validation this module exists to end.
            outcomes.append(RequirementOutcome(
                requirement_id=requirement_id,
                description=description,
                required=required,
                state=UNKNOWN,
                covered_by=ids,
                reason="what the founder meant here was never settled",
            ))
            continue

        if not covering:
            outcomes.append(RequirementOutcome(
                requirement_id=requirement_id,
                description=description,
                required=required,
                state=UNKNOWN,
                reason="no step took responsibility for this",
            ))
            continue

        verdicts = [_verdict_of(task) for task in covering]
        if any(v and v != _MATCHED for v in verdicts):
            outcomes.append(RequirementOutcome(
                requirement_id=requirement_id,
                description=description,
                required=required,
                state=NOT_SATISFIED,
                covered_by=ids,
                reason="what was observed did not match what was expected",
            ))
            continue

        if requirement_id in evidence_gaps:
            outcomes.append(RequirementOutcome(
                requirement_id=requirement_id,
                description=description,
                required=required,
                state=UNKNOWN,
                covered_by=ids,
                reason=(
                    "a mandatory candidate claim remains unresolved in "
                    "canonical Evidence"
                ),
            ))
            continue

        if requirement_id in undecided_requirements:
            outcomes.append(RequirementOutcome(
                requirement_id=requirement_id,
                description=description,
                required=required,
                state=UNKNOWN,
                covered_by=ids,
                reason="the canonical candidate decision is not yet supported",
            ))
            continue

        silent = [task for task in covering if not _verdict_of(task)]
        if silent and any(v == _MATCHED for v in verdicts):
            # Some covering step never produced Evidence at all, so this
            # is not known either way.
            #
            # "Any covering step matched" is right when the steps are
            # ALTERNATIVES -- several ways to establish one fact, and one
            # of them observed the world. It is wrong when they are
            # STAGES, which is what an AI-planned mission produces: open
            # a browser, navigate, read, write the answer. Every stage
            # covers the same requirement and only the last one delivers
            # it.
            #
            # Measured on the founder's own research objective. Step 1
            # opened a browser and verified `matched`; step 2 failed;
            # steps 4-6 never ran -- and "give me free demo download
            # links" was reported SATISFIED, on the strength of a browser
            # having opened. That is a false completion of exactly the
            # kind a visible truthful failure is always preferable to.
            #
            # Failing toward UNKNOWN costs a founder a hedge on a mission
            # that really did finish. The other direction costs them a
            # dead link they were told was checked.
            outcomes.append(RequirementOutcome(
                requirement_id=requirement_id,
                description=description,
                required=required,
                state=UNKNOWN,
                covered_by=ids,
                reason=(
                    "some steps responsible for this never ran, so it "
                    "cannot be confirmed"
                ),
            ))
            continue

        if any(v == _MATCHED for v in verdicts):
            # Every covering step reported, and at least one was
            # independently verified with nothing contradicting it. That
            # is as strong as this can get: Evidence is what makes a
            # requirement satisfied.
            outcomes.append(RequirementOutcome(
                requirement_id=requirement_id,
                description=description,
                required=required,
                state=SATISFIED,
                covered_by=ids,
                reason="independently verified",
            ))
            continue

        outcomes.append(RequirementOutcome(
            requirement_id=requirement_id,
            description=description,
            required=required,
            state=UNKNOWN,
            covered_by=ids,
            reason="the steps responsible for this produced no independent evidence",
        ))

    required = [o for o in outcomes if o.required]
    if any(o.state == NOT_SATISFIED for o in required):
        state, reason = NOT_SATISFIED, "a required part of the request was not met"
    elif any(o.state == UNKNOWN for o in required):
        state, reason = UNKNOWN, "part of the request could not be independently confirmed"
    elif required:
        state, reason = SATISFIED, "every required part of the request was verified"
    else:
        state, reason = UNKNOWN, "nothing about this request was required"

    return OutcomeConformance(
        state=state, requirements=tuple(outcomes), reason=reason
    )
