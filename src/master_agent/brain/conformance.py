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


def _verdict_of(task: Any) -> str:
    evidence = getattr(task, "evidence", None) or {}
    return str(evidence.get("verdict") or "")


def assess(requirements: Any, tasks: Any) -> OutcomeConformance:
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

    outcomes: list[RequirementOutcome] = []
    for requirement in requirements:
        covering = by_requirement.get(requirement.requirement_id, [])
        ids = tuple(str(getattr(t, "task_id", "")) for t in covering)

        if not covering:
            outcomes.append(RequirementOutcome(
                requirement_id=requirement.requirement_id,
                description=requirement.description,
                required=bool(requirement.required),
                state=UNKNOWN,
                reason="no step took responsibility for this",
            ))
            continue

        verdicts = [_verdict_of(task) for task in covering]
        if any(v and v != _MATCHED for v in verdicts):
            outcomes.append(RequirementOutcome(
                requirement_id=requirement.requirement_id,
                description=requirement.description,
                required=bool(requirement.required),
                state=NOT_SATISFIED,
                covered_by=ids,
                reason="what was observed did not match what was expected",
            ))
            continue

        if any(v == _MATCHED for v in verdicts):
            # At least one covering step was independently verified, and
            # none contradicted it. That is as strong as this can get:
            # Evidence is what makes a requirement satisfied, and a
            # requirement covered by several steps needs only one of them
            # to have actually observed the world.
            outcomes.append(RequirementOutcome(
                requirement_id=requirement.requirement_id,
                description=requirement.description,
                required=bool(requirement.required),
                state=SATISFIED,
                covered_by=ids,
                reason="independently verified",
            ))
            continue

        outcomes.append(RequirementOutcome(
            requirement_id=requirement.requirement_id,
            description=requirement.description,
            required=bool(requirement.required),
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
