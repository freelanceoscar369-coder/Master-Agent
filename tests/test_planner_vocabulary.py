"""Mission Brief 037 — priority and estimated complexity.

The brief adds two fields to what a Planner produces. Both are **closed
vocabularies**, both are **descriptive rather than directive**, and both
are **optional in the document** so every plan written against MB036's
shape is still a valid plan.
"""
from __future__ import annotations

import pytest

from master_agent.planner.parsing import validate
from master_agent.planner.plan import (
    COMPLEXITIES,
    DEFAULT_COMPLEXITY,
    DEFAULT_PRIORITY,
    MALFORMED,
    PRIORITIES,
    Intent,
)
from master_agent.planner.planner import Planner
from master_agent.planner.prompting import PLAN_SHAPE, build_prompt
from tests.planner_test_support import (
    CATALOGUE,
    CREATE,
    StubRunner,
    document,
    plan_text,
    step,
)


def planned(*steps, catalogue=CATALOGUE):
    outcome = Planner(StubRunner(plan_text(*steps)), catalogue).plan(Intent(goal="go"))
    return outcome


# =========================================================================
# The vocabularies
# =========================================================================


def test_the_two_vocabularies_are_closed_and_ordered():
    assert PRIORITIES == ("low", "normal", "high", "critical")
    assert COMPLEXITIES == ("trivial", "small", "moderate", "large")


def test_the_defaults_are_the_middle_of_each_scale():
    """A step nobody described is not automatically urgent or trivial."""
    assert DEFAULT_PRIORITY == "normal"
    assert DEFAULT_COMPLEXITY == "moderate"


@pytest.mark.parametrize("priority", PRIORITIES)
def test_every_priority_is_accepted(priority):
    outcome = planned({**step("one", CREATE.name), "priority": priority})

    assert outcome.planned
    assert outcome.plan.steps[0].priority == priority


@pytest.mark.parametrize("complexity", COMPLEXITIES)
def test_every_complexity_is_accepted(complexity):
    outcome = planned({**step("one", CREATE.name), "complexity": complexity})

    assert outcome.planned
    assert outcome.plan.steps[0].estimated_complexity == complexity


@pytest.mark.parametrize("value", ["urgent", "MASSIVE", "9", "", "  "])
def test_a_priority_outside_the_vocabulary_fails_the_plan(value):
    """Silently substituting the default would tell a founder the step is
    `normal` when the provider said `urgent` -- a lie about what was
    planned."""
    outcome = planned({**step("one", CREATE.name), "priority": value})

    assert outcome.plan is None
    assert outcome.refusal.code == MALFORMED
    assert "`priority` must be one of" in outcome.refusal.detail


@pytest.mark.parametrize("value", ["enormous", "XL", "3", ""])
def test_a_complexity_outside_the_vocabulary_fails_the_plan(value):
    outcome = planned({**step("one", CREATE.name), "complexity": value})

    assert outcome.plan is None
    assert "`complexity` must be one of" in outcome.refusal.detail


@pytest.mark.parametrize("value", [5, True, ["high"], {"a": 1}])
def test_a_priority_that_is_not_a_string_fails_the_plan(value):
    outcome = planned({**step("one", CREATE.name), "priority": value})

    assert outcome.plan is None
    assert outcome.refusal.code == MALFORMED


@pytest.mark.parametrize("value", ["HIGH", " high ", "High"])
def test_casing_and_whitespace_are_not_a_failure(value):
    """A model writing `"priority": "High"` meant high. There is exactly
    one reading, and refusing over punctuation would fail a good plan."""
    outcome = planned({**step("one", CREATE.name), "priority": value})

    assert outcome.plan.steps[0].priority == "high"


def test_a_step_that_says_nothing_gets_the_defaults():
    """MB036's plan shape had neither key. A plan written against it is
    still a valid plan."""
    outcome = planned(step("one", CREATE.name))

    assert outcome.plan.steps[0].priority == DEFAULT_PRIORITY
    assert outcome.plan.steps[0].estimated_complexity == DEFAULT_COMPLEXITY


def test_an_explicit_null_is_the_same_as_saying_nothing():
    outcome = planned({**step("one", CREATE.name), "priority": None, "complexity": None})

    assert outcome.plan.steps[0].priority == DEFAULT_PRIORITY
    assert outcome.plan.steps[0].estimated_complexity == DEFAULT_COMPLEXITY


# =========================================================================
# Descriptive, never directive
# =========================================================================


def test_priority_does_not_reorder_the_plan():
    """Mission Control owns execution order. A Planner that could reorder
    execution by labelling a step would own lifecycle."""
    plan, refusal = validate(
        document(
            {**step("first", CREATE.name), "priority": "low"},
            {**step("second", CREATE.name, depends_on=["first"]), "priority": "critical"},
        ),
        CATALOGUE,
    )

    assert refusal is None
    assert [s.step_id for s in plan.steps] == ["first", "second"]


def test_complexity_does_not_reorder_the_plan():
    plan, _refusal = validate(
        document(
            {**step("big", CREATE.name), "complexity": "large"},
            {**step("small", CREATE.name), "complexity": "trivial"},
        ),
        CATALOGUE,
    )

    assert [s.step_id for s in plan.steps] == ["big", "small"]


def test_neither_field_can_stand_in_for_a_dependency():
    """Two independent steps stay independent however they are labelled."""
    plan, _refusal = validate(
        document(
            {**step("a", CREATE.name), "priority": "critical"},
            {**step("b", CREATE.name), "priority": "low"},
        ),
        CATALOGUE,
    )

    assert all(s.depends_on == [] for s in plan.steps)


# =========================================================================
# The provider is told about them
# =========================================================================


def test_the_plan_shape_shows_both_fields():
    assert '"priority"' in PLAN_SHAPE
    assert '"complexity"' in PLAN_SHAPE


def test_the_prompt_says_they_do_not_change_execution_order():
    """Told to the model as well as enforced in the parser, because a
    model that believes priority schedules will write plans shaped by that
    belief."""
    prompt = build_prompt(Intent(goal="go"), CATALOGUE)

    assert "never change the order steps run in" in prompt
    assert "`depends_on` decides that" in prompt


def test_the_prompt_lists_both_vocabularies():
    prompt = build_prompt(Intent(goal="go"), CATALOGUE)

    for word in PRIORITIES:
        assert word in prompt
    for word in COMPLEXITIES:
        assert word in prompt


def test_the_prompt_is_still_deterministic_with_the_new_fields():
    first = build_prompt(Intent(goal="go"), CATALOGUE)
    second = build_prompt(Intent(goal="go"), CATALOGUE)

    assert first == second
