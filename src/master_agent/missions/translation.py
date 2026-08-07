"""`MissionPlan` -> `Objective` (Mission Brief 037).

The Planner speaks Steps; Mission Control speaks Tasks. This is the one
place that knows both words, and the mapping is **1:1 and lossless** --
asserted by a test that compares every field rather than trusted here.

## Why translate rather than teach the Runtime to read a MissionPlan

The Runtime, Mission Control and the Dispatcher have been frozen since
MB025, and MB037 is explicitly a compose-only brief. Teaching them a
second work vocabulary would need a ratified exception, and it would buy
nothing: MB023 already gave `Task` a `capability`, a `payload`, a
`depends_on` **and an `expected_outcome`**, with a comment naming
Constitution §3.2 and the Planner that did not exist yet. The seam was
cut for this. Translation is not a workaround; it is the seam being used.

Deliverable 5 says execution must consume a plan without modifying it and
must never infer missing information. Both are properties of this module:
it copies, it never fills in, and a plan missing anything is **rejected
before an Objective exists** -- so there is no path on which execution
could have inferred something, because there is nothing to execute.
"""
from __future__ import annotations

from typing import Any

from master_agent.mission_control.tasks import Objective, Task

#: What Deliverable 4 requires of every Step. Named rather than implied,
#: because "reject plans missing any of these" is only checkable against
#: a list somebody can read.
REQUIRED_STEP_FIELDS = ("capability", "inputs", "expected_outcome", "dependencies")


class PlanIncomplete(Exception):
    """A plan that cannot be executed as written.

    Carries every reason at once rather than the first one: a founder
    fixing a plan should see all of what is wrong with it, and a Planner
    being debugged against this should too.
    """

    def __init__(self, reasons: tuple[str, ...] | list[str]) -> None:
        self.reasons = tuple(reasons)
        super().__init__("; ".join(self.reasons))


def _step_problems(step: Any, index: int) -> list[str]:
    label = getattr(step, "step_id", "") or f"step {index + 1}"
    problems: list[str] = []

    capability = getattr(step, "capability", None)
    if not isinstance(capability, str) or not capability.strip():
        problems.append(f"{label}: no capability")

    # "Inputs" means the field is present and is a mapping -- **not** that
    # it is non-empty. `Desktop.ScanMachine` takes no arguments, and a rule
    # that forced one would make the Planner invent a payload, which is
    # exactly the guessing Deliverable 9 forbids.
    payload = getattr(step, "payload", None)
    if not isinstance(payload, dict):
        problems.append(f"{label}: inputs are missing or are not a mapping")

    expected = getattr(step, "expected_outcome", None)
    if expected is None:
        problems.append(f"{label}: no expected outcome")
    elif not getattr(expected, "checks", None):
        # MB035: an ExpectedOutcome with no checks evaluates to ERROR under
        # the frozen evaluator. Accepting one would put a step into the
        # Runtime that can never be verified, which is worse than a step
        # with no expectation at all -- that one at least reports as
        # `not checked`.
        problems.append(f"{label}: expected outcome states no checks")

    depends_on = getattr(step, "depends_on", None)
    if not isinstance(depends_on, list):
        problems.append(f"{label}: dependency information is missing")

    return problems


def incomplete_steps(plan: Any) -> tuple[str, ...]:
    """Every reason this plan cannot be executed. Empty means it can.

    Deliverable 4, as a function rather than as a comment. Note that a
    plan produced by MB036's Planner can never fail these checks -- its
    own validator is stricter. That is not a reason to skip them: this is
    the gate for *any* producer, and the day a second one appears the
    guarantee has to already be here rather than in the first one's
    docstring.
    """
    steps = getattr(plan, "steps", None)
    if not isinstance(steps, list) or not steps:
        return ("the plan has no steps",)

    problems: list[str] = []
    for index, step in enumerate(steps):
        problems.extend(_step_problems(step, index))
    return tuple(problems)


def task_from_step(step: Any) -> Task:
    """One Step, as a Task. Every field copied, nothing derived.

    `task_id` is the Planner's own `step_id` rather than a fresh UUID:
    a founder reading `write_readme` in the Dashboard and `write_readme`
    in the plan should be reading about the same thing, and `depends_on`
    already refers to steps by that name.
    """
    return Task(
        capability=step.capability,
        payload=dict(step.payload),
        depends_on=list(step.depends_on),
        expected_outcome=step.expected_outcome,
        task_id=step.step_id,
    )


def objective_from_plan(plan: Any, description: str = "") -> Objective:
    """The plan, as work Mission Control can dispatch.

    Raises `PlanIncomplete` rather than repairing anything. Validation
    runs before the `Objective` is built, so an incomplete plan never
    becomes a submittable object that somebody could submit anyway.
    """
    problems = incomplete_steps(plan)
    if problems:
        raise PlanIncomplete(problems)

    return Objective(
        description=description or getattr(plan, "objective", "") or "Mission",
        tasks=[task_from_step(step) for step in plan.steps],
    )
