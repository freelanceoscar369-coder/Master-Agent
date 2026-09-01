"""Mission Brief 036 — reading a plan, and reading what a step expects.

`validate()` and `outcomes.from_document()` directly, without a provider
in the way. These are the checks that decide whether a document is a plan
at all, so they are worth testing at the door rather than only through
the Planner: several of them are unreachable from above precisely because
the layer above already refused, and a check that is only exercised
transitively is a check nobody has read.
"""
from __future__ import annotations

import pytest

from master_agent.planner import outcomes
from master_agent.planner.catalogue import CapabilityOption, catalogue_from, names, render
from master_agent.planner.parsing import validate
from master_agent.planner.plan import (
    BAD_DEPENDENCY,
    BAD_PAYLOAD,
    CYCLIC,
    MALFORMED,
    MISSING_EXPECTATION,
    NO_STEPS,
    UNKNOWN_CAPABILITY,
)
from tests.planner_test_support import CATALOGUE, CREATE, DELETE, WRITE, document, step, success


def refusal_for(*steps, options=CATALOGUE):
    plan, refusal = validate(document(*steps), options)
    assert plan is None, "expected a refusal"
    return refusal


# =========================================================================
# The document
# =========================================================================


@pytest.mark.parametrize("document_value", ["a string", 42, None, True])
def test_anything_that_is_not_an_object_is_not_a_plan(document_value):
    plan, refusal = validate(document_value, CATALOGUE)

    assert plan is None
    assert refusal.code == MALFORMED
    assert refusal.detail == "the reply was not a JSON object"


@pytest.mark.parametrize("steps_value", [None, "one, then two", 3])
def test_steps_must_be_a_list(steps_value):
    plan, refusal = validate({"steps": steps_value}, CATALOGUE)

    assert plan is None
    assert refusal.code == MALFORMED
    assert "`steps` is missing or is not a list" == refusal.detail


def test_a_single_step_object_is_the_unambiguous_list_of_one():
    plan, refusal = validate({"steps": step("only")}, CATALOGUE)

    assert refusal is None
    assert [item.step_id for item in plan.steps] == ["only"]


def test_a_bare_step_list_is_the_unambiguous_steps_value():
    plan, refusal = validate([step("only")], CATALOGUE)

    assert refusal is None
    assert [item.step_id for item in plan.steps] == ["only"]


def test_an_empty_step_list_is_the_providers_honest_refusal():
    plan, refusal = validate({"steps": []}, CATALOGUE)

    assert plan is None
    assert refusal.code == NO_STEPS
    assert refusal.known_capabilities == names(CATALOGUE)


# =========================================================================
# One step
# =========================================================================


@pytest.mark.parametrize("entry", ["make a folder", 7, None, ["a"]])
def test_a_step_that_is_not_an_object_is_refused_by_position(entry):
    refusal = refusal_for(step("first"), entry)

    assert refusal.code == MALFORMED
    assert "step 2" in refusal.detail


@pytest.mark.parametrize("step_id", ["", "   ", None, 4, {"id": "a"}])
def test_a_step_needs_a_usable_id(step_id):
    refusal = refusal_for({"id": step_id, "capability": CREATE.name, "success": success()})

    assert refusal.code == MALFORMED
    assert "no usable `id`" in refusal.detail


@pytest.mark.parametrize("capability", ["", "  ", None, 9])
def test_a_step_needs_a_capability(capability):
    refusal = refusal_for({"id": "a", "capability": capability, "success": success()})

    assert refusal.code == MALFORMED
    assert "names no capability" in refusal.detail


def test_a_capability_outside_the_catalogue_is_refused_with_the_catalogue():
    refusal = refusal_for(step("a", "Filesystem.Teleport"))

    assert refusal.code == UNKNOWN_CAPABILITY
    assert refusal.known_capabilities == names(CATALOGUE)
    assert "not registered" in refusal.detail


def test_surrounding_whitespace_in_ids_and_capabilities_is_not_a_failure():
    """A model that writes `"capability": " Filesystem.WriteFile "` meant
    the capability. Refusing over whitespace would be pedantry, and there
    is exactly one reading."""
    plan, refusal = validate(
        document({"id": "  a  ", "capability": f" {WRITE.name} ", "success": success()}),
        CATALOGUE,
    )

    assert refusal is None
    assert plan.steps[0].step_id == "a"
    assert plan.steps[0].capability == WRITE.name


@pytest.mark.parametrize("payload", ["path=/tmp", 5, ["a"], True])
def test_a_payload_that_is_not_an_object_is_refused(payload):
    refusal = refusal_for(step("a", payload=payload))

    assert refusal.code == MALFORMED
    assert "`payload` must be an object" in refusal.detail


def test_a_missing_or_null_payload_becomes_an_empty_one():
    """Absent arguments and no arguments are the same thing, and a step
    with neither is a legitimate step -- `Desktop.ScanMachine` takes
    nothing."""
    plan, refusal = validate(
        document(
            {"id": "a", "capability": CREATE.name, "success": success()},
            {"id": "b", "capability": WRITE.name, "payload": None, "success": success()},
        ),
        CATALOGUE,
    )

    assert refusal is None
    assert [s.payload for s in plan.steps] == [{}, {}]


@pytest.mark.parametrize("depends", [5, [1], [""], ["  "], {"a": 1}])
def test_depends_on_must_be_a_list_of_step_ids(depends):
    refusal = refusal_for(step("a", depends_on=depends))

    assert refusal.code == MALFORMED
    assert "`depends_on` must be a list of step ids" in refusal.detail


def test_a_single_dependency_written_as_a_string_is_read_as_a_list_of_one():
    plan, refusal = validate(
        document(step("a"), {**step("b"), "depends_on": "a"}), CATALOGUE
    )

    assert refusal is None
    assert plan.steps[1].depends_on == ["a"]


def test_a_null_depends_on_is_no_dependencies():
    plan, refusal = validate(document({**step("a"), "depends_on": None}), CATALOGUE)

    assert refusal is None
    assert plan.steps[0].depends_on == []


def test_a_published_output_may_be_designated_as_the_founder_answer():
    reason = CapabilityOption(
        name="Reasoning.Transform",
        required_args=("instruction",),
        args_complete=True,
        output_fields=("text", "sensitivity"),
    )
    entry = {
        "id": "answer",
        "capability": reason.name,
        "payload": {"instruction": "recommend one"},
        "answers_founder": " text ",
        "success": success(),
    }

    plan, refusal = validate(document(entry), (reason,))

    assert refusal is None
    assert plan.steps[0].answers_founder == "text"


def test_an_unpublished_founder_answer_field_is_refused():
    reason = CapabilityOption(
        name="Reasoning.Transform", output_fields=("text",),
    )
    refusal = refusal_for(
        {**step("answer", reason.name), "answers_founder": "rationale"},
        options=(reason,),
    )

    assert refusal.code == BAD_PAYLOAD
    assert "publishes: text" in refusal.detail


def test_more_than_one_step_cannot_designate_the_founder_answer():
    reason = CapabilityOption(
        name="Reasoning.Transform", output_fields=("text",),
    )
    refusal = refusal_for(
        {**step("first", reason.name), "answers_founder": "text"},
        {**step("second", reason.name), "answers_founder": "text"},
        options=(reason,),
    )

    assert refusal.code == BAD_PAYLOAD
    assert "first, second" in refusal.detail


def test_non_string_founder_answer_designation_is_malformed():
    reason = CapabilityOption(
        name="Reasoning.Transform", output_fields=("text",),
    )
    refusal = refusal_for(
        {**step("answer", reason.name), "answers_founder": ["text"]},
        options=(reason,),
    )

    assert refusal.code == MALFORMED


# =========================================================================
# What a step expects — Constitution §3.2, at the door
# =========================================================================


@pytest.mark.parametrize("success_doc", [None, "it works", 5, ["ok"]])
def test_a_step_without_a_success_object_fails_the_plan(success_doc):
    refusal = refusal_for({"id": "a", "capability": CREATE.name, "success": success_doc})

    assert refusal.code == MISSING_EXPECTATION
    assert "step `a` has no `success` object" in refusal.detail


@pytest.mark.parametrize("description", ["", "   ", None, 7])
def test_a_success_object_must_actually_describe_success(description):
    refusal = refusal_for(step("a", success_doc={"description": description}))

    assert refusal.code == MISSING_EXPECTATION
    assert "must describe what success looks like" in refusal.detail


def test_an_unsupported_success_key_is_refused_rather_than_dropped():
    """A silently ignored key is an expectation the founder believes is
    being checked and is not. The supported ones are listed in the error,
    because the model can be told."""
    refusal = refusal_for(
        step("a", success_doc=success("ok", must_look_correct=True, vibe="good"))
    )

    assert refusal.code == MISSING_EXPECTATION
    assert "must_look_correct, vibe" in refusal.detail
    assert "must_contain" in refusal.detail


@pytest.mark.parametrize("value", ["yes", 1, None])
def test_must_be_json_has_to_be_a_boolean(value):
    refusal = refusal_for(step("a", success_doc=success("ok", must_be_json=value)))

    assert refusal.code == MISSING_EXPECTATION
    assert "`must_be_json` must be true or false" in refusal.detail


@pytest.mark.parametrize("value", [-1, "three", 2.5, True, None])
def test_min_words_has_to_be_a_whole_number(value):
    """`True` is in that list on purpose: `bool` is an `int` in Python, so
    `"min_words": true` would otherwise become a silent 1."""
    refusal = refusal_for(step("a", success_doc=success("ok", min_words=value)))

    assert refusal.code == MISSING_EXPECTATION
    assert "`min_words` must be a whole number" in refusal.detail


@pytest.mark.parametrize("key", ["must_contain", "must_exclude", "must_have_fields"])
@pytest.mark.parametrize("value", [5, {"a": 1}, [1], [""], ["  "], [None]])
def test_the_string_lists_have_to_be_lists_of_real_strings(key, value):
    refusal = refusal_for(step("a", success_doc=success("ok", **{key: value})))

    assert refusal.code == MISSING_EXPECTATION
    assert f"`{key}`" in refusal.detail


@pytest.mark.parametrize("key", ["must_contain", "must_exclude", "must_have_fields"])
def test_one_phrase_written_as_a_string_is_read_as_a_list_of_one(key):
    spec = outcomes.from_document(success("ok", **{key: "created"}), step_id="a")

    assert getattr(spec, key) == ("created",)


@pytest.mark.parametrize("key", ["must_contain", "must_exclude", "must_have_fields"])
def test_a_null_string_list_is_no_phrases(key):
    spec = outcomes.from_document(success("ok", **{key: None}), step_id="a")

    assert getattr(spec, key) == ()


def test_a_spec_with_nothing_but_a_description_still_produces_an_evaluable_check():
    """MB035: an `ExpectedOutcome` with no checks evaluates to ERROR under
    the frozen evaluator, so `require_non_empty` is always on."""
    expected = outcomes.from_document(success("something comes back"), step_id="a")

    outcome = expected.to_expected_outcome()

    assert outcome.description == "something comes back"
    assert [check.field for check in outcome.checks] == ["empty"]


def test_every_supported_key_is_one_the_frozen_verifier_can_actually_check():
    """The closed vocabulary exists so a provider cannot invent a check
    against an observation field that does not exist. This asserts the
    other half: every key it *may* use maps onto a real check."""
    spec = outcomes.SuccessSpec(
        description="everything at once",
        must_contain=("a",),
        must_exclude=("b",),
        must_be_json=True,
        must_have_fields=("c",),
        min_words=2,
    )

    from master_agent.ai_infrastructure.text_verifier import observe

    observation = observe('{"c": "a"}')
    for check in spec.to_expected_outcome().checks:
        root = check.field.split(".")[0]
        assert root in observation, check.field


def test_the_supported_keys_are_exactly_the_fields_a_spec_can_hold():
    assert outcomes.SUCCESS_KEYS == {
        "description",
        "must_contain",
        "must_exclude",
        "must_be_json",
        "must_have_fields",
        "min_words",
    }


# =========================================================================
# Dependencies
# =========================================================================


def test_a_step_cannot_wait_for_itself():
    refusal = refusal_for(step("a", depends_on=["a"]))

    assert refusal.code == BAD_DEPENDENCY
    assert "its own id" in refusal.detail


def test_a_step_cannot_wait_for_a_step_that_was_never_declared():
    refusal = refusal_for(step("a"), step("b", depends_on=["nowhere"]))

    assert refusal.code == BAD_DEPENDENCY
    assert "`nowhere`" in refusal.detail


def test_a_dependency_declared_before_the_step_it_names_is_fine():
    """Order in the document is not order of execution, so a forward
    reference is legitimate and the sort is what resolves it."""
    plan, refusal = validate(
        document(step("a", depends_on=["b"]), step("b")), CATALOGUE
    )

    assert refusal is None
    assert [s.step_id for s in plan.steps] == ["b", "a"]


def test_a_three_step_circle_is_caught_and_named():
    refusal = refusal_for(
        step("a", depends_on=["c"]),
        step("b", depends_on=["a"]),
        step("c", depends_on=["b"]),
    )

    assert refusal.code == CYCLIC
    assert "a, b, c" in refusal.detail


def test_a_circle_beside_a_clean_chain_still_fails_the_plan():
    """Only the circle is stuck, but half a plan executed is worse than
    none, so the whole document is refused."""
    refusal = refusal_for(
        step("clean"),
        step("a", depends_on=["b"]),
        step("b", depends_on=["a"]),
    )

    assert refusal.code == CYCLIC
    assert "clean" not in refusal.detail


def test_a_diamond_is_ordered_so_every_dependency_comes_first():
    plan, refusal = validate(
        document(
            step("join", depends_on=["left", "right"]),
            step("left", depends_on=["root"]),
            step("right", depends_on=["root"]),
            step("root"),
        ),
        CATALOGUE,
    )

    assert refusal is None
    order = [s.step_id for s in plan.steps]
    assert order.index("root") < order.index("left") < order.index("join")
    assert order.index("right") < order.index("join")


def test_unordered_operations_cannot_share_one_stateful_browser_session():
    options = CATALOGUE + (
        CapabilityOption(name="Browser.Navigate"),
        CapabilityOption(name="Browser.ReadPageText"),
    )
    plan, refusal = validate(
        document(
            step("open", capability="Browser.Navigate", payload={"session_id": "s"}),
            step(
                "left", capability="Browser.Navigate",
                payload={"session_id": "s"}, depends_on=["open"],
            ),
            step(
                "right", capability="Browser.ReadPageText",
                payload={"session_id": "s"}, depends_on=["open"],
            ),
        ),
        options,
    )

    assert plan is None
    assert refusal.code == BAD_DEPENDENCY
    assert "stateful browser session `s`" in refusal.detail
    assert "left" in refusal.detail and "right" in refusal.detail


def test_ordered_operations_may_share_one_stateful_browser_session():
    options = CATALOGUE + (
        CapabilityOption(name="Browser.Navigate"),
        CapabilityOption(name="Browser.ReadPageText"),
    )
    plan, refusal = validate(
        document(
            step("open", capability="Browser.Navigate", payload={"session_id": "s"}),
            step(
                "navigate", capability="Browser.Navigate",
                payload={"session_id": "s"}, depends_on=["open"],
            ),
            step(
                "read", capability="Browser.ReadPageText",
                payload={"session_id": "s"}, depends_on=["navigate"],
            ),
        ),
        options,
    )

    assert refusal is None
    assert [item.step_id for item in plan.steps] == ["open", "navigate", "read"]


def test_independent_browser_sessions_do_not_need_cross_dependencies():
    options = CATALOGUE + (CapabilityOption(name="Browser.Navigate"),)
    plan, refusal = validate(
        document(
            step("one", capability="Browser.Navigate", payload={"session_id": "s1"}),
            step("two", capability="Browser.Navigate", payload={"session_id": "s2"}),
        ),
        options,
    )

    assert refusal is None
    assert plan is not None


def test_the_objective_travels_with_the_plan():
    plan, _ = validate(document(step("a")), CATALOGUE, objective="Do the thing")

    assert plan.objective == "Do the thing"


# =========================================================================
# The catalogue
# =========================================================================


class FakeDescriptor:
    def __init__(self, qualified_name, description="", risk_tier=None):
        self.qualified_name = qualified_name
        self.description = description
        self.risk_tier = risk_tier


class FakeRegistry:
    def __init__(self, *descriptors):
        self._descriptors = descriptors

    def all(self):
        return list(self._descriptors)


def test_a_catalogue_is_always_sorted_no_matter_how_it_was_registered():
    registry = FakeRegistry(
        FakeDescriptor("Zulu.Act"), FakeDescriptor("Alpha.Act"), FakeDescriptor("Mike.Act")
    )

    assert names(catalogue_from(registry)) == ("Alpha.Act", "Mike.Act", "Zulu.Act")


def test_a_descriptor_with_no_description_or_risk_renders_as_just_its_name():
    registry = FakeRegistry(FakeDescriptor("Alpha.Act", description=None))

    # MB039: the signature is rendered even when nothing is published --
    # `(...)` says "arguments exist and were not declared", which is a
    # different claim from "takes none".
    assert render(catalogue_from(registry)) == "- Alpha.Act | args: none declared"


def test_a_description_is_trimmed_so_the_prompt_does_not_inherit_stray_whitespace():
    registry = FakeRegistry(FakeDescriptor("Alpha.Act", description="  Does a thing.  "))

    assert render(catalogue_from(registry)) == "- Alpha.Act | args: none declared | Does a thing."


def test_an_irreversible_capability_is_visibly_the_more_expensive_choice():
    rendered = render([DELETE])

    assert rendered == (
        "- Filesystem.DeleteFolder | args: none declared | "
        "Delete a folder and its contents. [risk: irreversible]"
    )


def test_an_empty_catalogue_renders_as_nothing_rather_than_as_a_bullet():
    assert render(()) == ""
    assert names(()) == ()


def test_a_capability_option_carries_only_what_planning_needs():
    """Not the permission category. The Permission System owns gating and
    nothing else does -- so nothing else is given the vocabulary to start
    reasoning about it."""
    option = CapabilityOption("Alpha.Act")

    assert option.description == ""
    assert option.risk_tier is None
    assert not hasattr(option, "permission_category")
