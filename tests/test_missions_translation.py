"""Mission Brief 037 — MissionPlan -> Objective, and the gate in front of it.

Two claims, both asserted rather than described:

1. The mapping is **1:1 and lossless**. Execution consumes the plan
   without modification (Deliverable 5).
2. A plan missing a capability, inputs, an expected outcome or dependency
   information is **rejected before an Objective exists** (Deliverable 4),
   so there is no path on which execution could infer the missing part.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from master_agent.mission_control.tasks import Objective, Task
from master_agent.missions.translation import (
    REQUIRED_STEP_FIELDS,
    PlanIncomplete,
    incomplete_steps,
    objective_from_plan,
    task_from_step,
)
from master_agent.planner.plan import MissionPlan, Step
from master_agent.verification.evidence import ExpectedOutcome, ObservationCheck


def check(description: str = "not blank") -> ObservationCheck:
    return ObservationCheck(
        field="empty", operator="equals", value=False, description=description
    )


def expectation(description: str = "something comes back") -> ExpectedOutcome:
    return ExpectedOutcome(description=description, checks=[check()])


def a_step(
    step_id: str = "one",
    capability: str = "Filesystem.CreateFolder",
    payload: Any = None,
    depends_on: Any = None,
    expected: Any = ...,
    **extra: Any,
) -> Step:
    return Step(
        step_id=step_id,
        capability=capability,
        payload={"name": "demo"} if payload is None else payload,
        depends_on=[] if depends_on is None else depends_on,
        expected_outcome=expectation() if expected is ... else expected,
        **extra,
    )


def a_plan(*steps: Step, objective: str = "Do the thing") -> MissionPlan:
    return MissionPlan(steps=list(steps) or [a_step()], objective=objective)


# =========================================================================
# 1:1 and lossless
# =========================================================================


def test_every_field_of_a_step_survives_the_crossing():
    """Deliverable 5: execution consumes a plan without modification. The
    strongest form of that is that nothing is lost on the way in."""
    expected = expectation("the folder exists")
    step = Step(
        step_id="make_folder",
        capability="Filesystem.CreateFolder",
        payload={"name": "demo", "location": "desktop"},
        depends_on=["earlier"],
        expected_outcome=expected,
    )

    task = task_from_step(step)

    assert task.task_id == step.step_id
    assert task.capability == step.capability
    assert task.payload == step.payload
    assert task.depends_on == step.depends_on
    assert task.expected_outcome is expected


def test_the_planners_step_id_becomes_the_task_id():
    """A founder reading `write_readme` in the plan and `write_readme` in
    the Dashboard must be reading about the same thing -- and `depends_on`
    already refers to steps by that name, so a fresh UUID would break the
    graph as well as the reading."""
    plan = a_plan(a_step("first"), a_step("second", depends_on=["first"]))

    objective = objective_from_plan(plan)

    assert [task.task_id for task in objective.tasks] == ["first", "second"]
    assert objective.tasks[1].depends_on == ["first"]


def test_the_payload_is_copied_rather_than_shared():
    """A Task handed to an Executive must not be able to mutate the plan
    it came from -- the record of what was planned has to stay what was
    planned."""
    step = a_step(payload={"name": "demo"})
    plan = a_plan(step)

    task = objective_from_plan(plan).tasks[0]
    task.payload["name"] = "tampered"

    assert step.payload == {"name": "demo"}


def test_the_dependency_list_is_copied_too():
    step = a_step("b", depends_on=["a"])
    plan = a_plan(a_step("a"), step)

    objective_from_plan(plan).tasks[1].depends_on.append("c")

    assert step.depends_on == ["a"]


def test_the_objective_is_described_by_the_founders_own_words():
    plan = a_plan(objective="planner's copy")

    assert objective_from_plan(plan, description="what the founder typed").description == (
        "what the founder typed"
    )


def test_without_a_description_the_plans_own_objective_is_used():
    assert objective_from_plan(a_plan(objective="from the plan")).description == "from the plan"


def test_a_plan_with_no_objective_at_all_still_names_the_mission_something():
    """Never an empty description: Mission Control renders it, and a blank
    row is worse than a generic one."""
    plan = MissionPlan(steps=[a_step()], objective="")

    assert objective_from_plan(plan).description == "Mission"


def test_the_result_is_a_real_objective_that_mission_control_accepts():
    plan = a_plan(a_step("a"), a_step("b", depends_on=["a"]))

    objective = objective_from_plan(plan)

    assert isinstance(objective, Objective)
    assert all(isinstance(task, Task) for task in objective.tasks)
    objective.validate()  # raises InvalidObjective if it would not dispatch


def test_canonical_intent_sensitivity_is_projected_onto_every_task():
    plan = MissionPlan(
        steps=[a_step("a"), a_step("b", depends_on=["a"])],
        objective="private work",
        is_sensitive=True,
    )

    objective = objective_from_plan(plan)

    assert [task.intent_sensitive for task in objective.tasks] == [True, True]


def test_legacy_plan_without_sensitivity_remains_unknown_not_public():
    objective = objective_from_plan(a_plan())

    assert objective.tasks[0].intent_sensitive is None


# =========================================================================
# Deliverable 4 — reject a plan missing anything
# =========================================================================


def test_the_required_fields_are_named_rather_than_implied():
    assert REQUIRED_STEP_FIELDS == (
        "capability",
        "inputs",
        "expected_outcome",
        "dependencies",
    )


def test_a_plan_with_no_steps_is_rejected():
    assert incomplete_steps(MissionPlan(steps=[])) == ("the plan has no steps",)


@pytest.mark.parametrize("plan", [None, "a plan", 42, object()])
def test_something_that_is_not_a_plan_is_rejected(plan):
    assert incomplete_steps(plan) == ("the plan has no steps",)


@pytest.mark.parametrize("capability", ["", "   ", None, 7])
def test_a_step_with_no_capability_is_rejected(capability):
    problems = incomplete_steps(a_plan(a_step(capability=capability)))

    assert problems == ("one: no capability",)


@pytest.mark.parametrize("payload", ["name=demo", 5, ["name"], True])
def test_a_step_whose_inputs_are_not_a_mapping_is_rejected(payload):
    problems = incomplete_steps(a_plan(a_step(payload=payload)))

    assert problems == ("one: inputs are missing or are not a mapping",)


def test_a_step_with_no_inputs_at_all_is_fine():
    """`Desktop.ScanMachine` takes no arguments. A rule that forced a
    non-empty payload would make the Planner invent one, which is exactly
    the guessing Deliverable 9 forbids."""
    assert incomplete_steps(a_plan(a_step(payload={}))) == ()


def test_a_step_with_no_expected_outcome_is_rejected():
    """Constitution §3.2, and the reason MB035 exists. No ExpectedOutcome
    means the Verifier cannot operate, so the mission is refused."""
    problems = incomplete_steps(a_plan(a_step(expected=None)))

    assert problems == ("one: no expected outcome",)


def test_an_expected_outcome_that_states_no_checks_is_rejected():
    """MB035 documents that an empty `ExpectedOutcome` evaluates to ERROR
    under the frozen evaluator. Admitting one would put a step into the
    Runtime that can never be verified -- worse than a step with no
    expectation, which at least reports as `not checked`."""
    problems = incomplete_steps(a_plan(a_step(expected=ExpectedOutcome("empty", []))))

    assert problems == ("one: expected outcome states no checks",)


@pytest.mark.parametrize("depends_on", ["earlier", 5, {"a": 1}])
def test_a_step_whose_dependency_information_is_not_a_list_is_rejected(depends_on):
    problems = incomplete_steps(a_plan(a_step(depends_on=depends_on)))

    assert problems == ("one: dependency information is missing",)


def test_every_reason_is_reported_at_once_not_just_the_first():
    """A founder fixing a plan should see all of what is wrong with it."""
    problems = incomplete_steps(
        a_plan(
            a_step("one", capability=""),
            a_step("two", expected=None),
            a_step("three", depends_on="nope"),
        )
    )

    assert problems == (
        "one: no capability",
        "two: no expected outcome",
        "three: dependency information is missing",
    )


def test_a_step_with_several_problems_reports_all_of_them():
    problems = incomplete_steps(a_plan(a_step(capability="", payload=7, expected=None)))

    assert len(problems) == 3


def test_a_step_with_no_id_is_still_reported_by_position():
    """A plan malformed enough to have no ids must still produce a
    readable complaint rather than `: no capability`."""
    problems = incomplete_steps(a_plan(a_step(step_id="", capability="")))

    assert problems == ("step 1: no capability",)


def test_an_incomplete_plan_raises_before_an_objective_exists():
    """The gate is *before* construction on purpose: an incomplete plan
    must never become a submittable object that somebody could submit
    anyway."""
    with pytest.raises(PlanIncomplete) as raised:
        objective_from_plan(a_plan(a_step(expected=None)))

    assert raised.value.reasons == ("one: no expected outcome",)
    assert "no expected outcome" in str(raised.value)


def test_the_exception_carries_every_reason():
    with pytest.raises(PlanIncomplete) as raised:
        objective_from_plan(a_plan(a_step("a", expected=None), a_step("b", capability="")))

    assert len(raised.value.reasons) == 2


def test_a_complete_plan_produces_no_complaints():
    assert incomplete_steps(a_plan(a_step("a"), a_step("b", depends_on=["a"]))) == ()


# =========================================================================
# The gate accepts any producer, not just this one
# =========================================================================


@dataclass
class ForeignStep:
    """A Step-shaped object from somewhere else. The gate must judge it on
    its fields, not on its type -- otherwise the guarantee lives in the
    Planner's docstring rather than here."""

    step_id: str = "x"
    capability: str = "Filesystem.CreateFolder"
    payload: dict = field(default_factory=dict)
    depends_on: list = field(default_factory=list)
    expected_outcome: Any = None


@dataclass
class ForeignPlan:
    steps: list = field(default_factory=list)
    objective: str = "foreign"


def test_a_plan_from_another_producer_is_held_to_the_same_rules():
    assert incomplete_steps(ForeignPlan(steps=[ForeignStep()])) == (
        "x: no expected outcome",
    )


def test_a_foreign_plan_that_is_complete_is_accepted():
    complete = ForeignStep(expected_outcome=expectation())

    objective = objective_from_plan(ForeignPlan(steps=[complete]))

    assert objective.tasks[0].task_id == "x"
