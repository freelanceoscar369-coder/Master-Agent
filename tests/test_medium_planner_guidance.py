"""The Planner prompt must teach a method, not only a shape.

A founder asked Kalpavriksha to read a CV from a drive, understand it,
search for suitable current openings, and return matched roles with
links, rationale and skill gaps. The audit shows the Intent Layer
preserved that request byte for byte and asked no clarification -- and
that no plan ever came back, because every reasoning provider was
unavailable.

So this is not a repair for an observed bad plan; none was produced. It
closes a latent gap the failure exposed. Rules 1-6 teach the *shape* of a
plan -- exact names, argument spelling, binding syntax, stated
expectations -- and say nothing about *method*. For a compound objective
the only two rules that spoke, "use the fewest steps" and "reply with
steps: [] if the catalogue cannot achieve the goal", both point toward
collapse: a model that asks "is there one capability that does this whole
job?" answers no and stops.

These tests assert the instructions exist and are generic. They do not
assert a model obeys them -- that is not knowable from a prompt -- and
they never execute a mission.
"""
from __future__ import annotations

import pytest

from master_agent.planner.catalogue import CapabilityOption
from master_agent.planner.plan import Intent
from master_agent.planner.prompting import build_prompt

#: A deliberately mixed catalogue: local reading, search, and browsing.
#: No capability performs a judgement, which is the condition rule 13
#: exists for.
CATALOGUE = (
    CapabilityOption(
        name="Filesystem.SearchFiles",
        description="Search for files matching a glob pattern under a known location.",
        required_args=("pattern",), optional_args=("location",), args_complete=True,
        output_fields=("matches",),
    ),
    CapabilityOption(
        name="Filesystem.ReadFile",
        description="Read a text file's content from a known location.",
        required_args=("path",), optional_args=("location",), args_complete=True,
        output_fields=("content",),
    ),
    CapabilityOption(
        name="Browser.Navigate",
        description="Navigate an open browser session to a URL.",
        required_args=("session_id", "url"), args_complete=True,
    ),
    CapabilityOption(
        name="Browser.ObserveBrowser",
        description="Capture the current page's state.",
        required_args=("session_id",), args_complete=True,
        output_fields=("url", "title"),
    ),
    CapabilityOption(
        name="Filesystem.WriteFile",
        description="Write text to a file.",
        required_args=("path",), optional_args=("location", "content"),
        args_complete=True,
    ),
)


@pytest.fixture
def prompt():
    """One generic objective. The rules must be present for ANY objective,
    so nothing about this sentence may be load-bearing."""
    return build_prompt(Intent(goal="do a thing that takes several steps"), CATALOGUE)


def says(prompt: str, *phrases: str) -> bool:
    lowered = prompt.lower()
    return all(phrase.lower() in lowered for phrase in phrases)


class TestCompoundObjectivesAreNormal:

    def test_it_rejects_the_one_capability_question(self, prompt):
        assert says(prompt, "capability that does all of this")
        assert says(prompt, "used together")

    def test_it_asks_for_compositional_evaluation(self, prompt):
        assert says(prompt, "compositionally")
        assert says(prompt, "several capabilities")

    def test_a_multi_capability_goal_is_not_a_refusal(self, prompt):
        assert says(prompt, "normal, not a reason to refuse")


class TestDiscoverBeforeGuessing:

    def test_it_instructs_acquisition_of_discoverable_facts(self, prompt):
        assert says(prompt, "discover before guessing")
        assert says(prompt, "plan the step that finds out")

    def test_unknown_is_not_a_reason_to_stop_or_to_ask(self, prompt):
        assert says(prompt, "not a reason to stop", "not a reason to ask")

    def test_it_separates_discoverable_from_founder_owned(self, prompt):
        assert says(prompt, "discoverable")
        assert says(prompt, "only the founder holds")

    def test_resolvable_uncertainty_is_not_impossibility(self, prompt):
        assert says(prompt, "uncertainty you could have resolved is not impossibility")


class TestAcquireBeforeUse:

    def test_producing_steps_come_first(self, prompt):
        assert says(prompt, "acquire a fact before using it")

    def test_future_values_must_use_bindings(self, prompt):
        assert says(prompt, "input_bindings")
        assert says(prompt, "never plan a step that reads something and, in the same "
                            "plan, state what it will say")

    def test_observation_outranks_the_objectives_wording(self, prompt):
        """The trailing-slash lesson, generalised."""
        assert says(prompt, "observed reality outranks")
        assert says(prompt, "never from what the founder's sentence made look likely")


class TestFullRequirementCoverage:

    def test_every_material_requirement_must_be_covered(self, prompt):
        assert says(prompt, "cover the whole request")
        assert says(prompt, "material requirement")

    def test_the_first_action_is_not_the_whole_plan(self, prompt):
        assert says(prompt, "not merely its first executable action")

    def test_the_coverage_check_is_not_to_be_written_out(self, prompt):
        """A reasoning trace in the reply would break the JSON contract."""
        assert says(prompt, "do not show this checking")

    def test_fewest_does_not_mean_incomplete(self, prompt):
        assert says(prompt, "does not mean dropping")
        assert says(prompt, "beats a two-step plan")


class TestFounderAnswerDesignation:

    def test_the_requested_value_is_designated_on_its_producer(self, prompt):
        assert says(prompt, "answers_founder", "dot-path")
        assert says(prompt, "exactly one evidence-producing step")

    def test_cleanup_is_not_mistaken_for_the_answer(self, prompt):
        assert says(prompt, "not a later write, close or cleanup step")


class TestRefusalIsTheLastAnswer:

    def test_empty_steps_only_after_considering_composition(self, prompt):
        assert says(prompt, "is the last answer, not the first")
        assert says(prompt, "chained")

    def test_no_single_capability_is_not_a_reason_to_refuse(self, prompt):
        assert says(prompt, "no single capability performs the mission is not a reason")

    def test_a_later_observable_value_is_not_a_reason_to_refuse(self, prompt):
        assert says(prompt, "if a step could observe it later")


class TestNeverInventCapabilities:

    def test_transformations_need_a_registered_capability(self, prompt):
        assert says(prompt, "never invent a capability")
        assert says(prompt, "only if the catalogue actually lists a capability")

    def test_planning_reasoning_is_not_an_executable_step(self, prompt):
        """The distinction that decides whether a mission is honest: the
        provider helping write the plan is not a capability the Runtime
        has at run time."""
        assert says(prompt, "reasoning you are doing now")
        assert says(prompt, "is not a capability the machine has at run time")

    def test_a_missing_transformation_is_reported_not_faked(self, prompt):
        assert says(prompt, "rather than naming something that does not exist")


class TestPhaseAndOrderingHeuristics:

    def test_it_offers_a_phase_habit_without_mandating_it(self, prompt):
        assert says(prompt, "acquire, inspect")
        assert says(prompt, "a habit of thought, not a required shape")

    def test_local_source_before_dependent_external_research(self, prompt):
        assert says(prompt, "acquire and inspect the local source first")


class TestTheGuidanceIsGeneric:
    """The rules were written after a CV objective. If any of them names
    it, they stop being rules."""

    @pytest.mark.parametrize("word", [
        "cv", "resume", "curriculum", "job", "vacancy", "career",
        "d drive", "d:", "linkedin", "naukri", "indeed", "recruit",
    ])
    def test_no_task_specific_vocabulary_appears(self, word):
        rendered = build_prompt(Intent(goal="something entirely unrelated"), CATALOGUE)
        # Compare against the rules only: the catalogue and the founder's
        # own objective are echoed into the prompt and are not ours.
        from master_agent.planner.prompting import _RULES

        import re

        rules = " ".join(_RULES).lower()
        # Word boundaries: "allowed: {" contains "d:", and a naive
        # substring test would report a leak that is not there.
        assert not re.search(rf"(?<![a-z]){re.escape(word)}(?![a-z])", rules), (
            f"the guidance names {word!r}"
        )
        assert rendered  # the prompt still builds

    def test_the_rules_hold_for_an_objective_of_any_subject(self):
        for goal in ("tidy up my photos", "find out what a page says",
                     "compare two documents and tell me the difference"):
            rendered = build_prompt(Intent(goal=goal), CATALOGUE)
            assert says(rendered, "compositionally", "discover before guessing",
                        "cover the whole request")


class TestTheOriginalContractSurvives:
    """Everything rules 1-6 already taught must still be taught."""

    @pytest.mark.parametrize("phrase", [
        "reply with json only",
        "copied exactly from the catalogue",
        "never invent one",
        "depends_on",
        "input_bindings",
        "from_step",
        "concat",
        "fewest steps",
    ])
    def test_existing_guidance_is_preserved(self, phrase, prompt):
        assert says(prompt, phrase)

    def test_the_binding_syntax_example_is_a_whole_step(self, prompt):
        """A fragment was not enough, proven live: a local model copied the
        placeholder key `"argument"` verbatim and nested the binding inside
        `payload`, and a thirteen-minute plan was rejected for it. The
        example is a complete step now, with `input_bindings` visibly
        beside `payload`."""
        assert '"from_step": {"step_id": "step_3", "field": "text"}' in prompt
        assert '"capability": "Document.WriteDocument"' in prompt
        assert says(prompt, "sits beside `payload`, never inside it")
        assert says(prompt, "and not in `payload`")

    def test_the_concat_form_is_still_taught(self, prompt):
        assert '"concat": [{"literal": "Title: "}' in prompt

    def test_declared_argument_values_must_be_used(self, prompt):
        """Also observed live: a real drive path written where a named
        location was offered."""
        assert says(prompt, "use one of those values exactly")
        assert says(prompt, "the whole vocabulary that argument has")

    def test_an_argument_may_not_be_set_twice(self, prompt):
        assert says(prompt, "must NOT also appear in `payload`")


class TestVerifiedResearchDeliverables:

    def test_a_verified_write_is_not_followed_by_a_weaker_query(self, prompt):
        assert says(prompt, "verified write", "fresh independent read")
        assert says(prompt, "do not add fileexists or readfile merely")

    def test_research_keeps_sources_and_unknowns(self, prompt):
        assert says(prompt, "bind the observed source url")
        assert says(prompt, "sources/provenance section")
        assert says(prompt, "never fill a missing fact from model memory")
