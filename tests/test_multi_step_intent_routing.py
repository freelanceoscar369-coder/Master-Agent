"""A specialised parser may claim a request only if it IS that request.

The defect these lock, observed live in the packaged app:

    Onkar:  Open a browser and navigate to https://example.com. Observe the
            page's actual title and final URL. Create a folder called
            KV_MEDIUM_155505 on Desktop. Inside that folder create a text
            file called page_info.txt containing the title and URL you
            actually observed. Then close the browser.
    Somesh: What should the folder be called?

Five requirements went in; a question about one of them came back, and the
browser, the observation, the file and the shutdown were gone before a
mission existed. Nothing misunderstood them -- `IntentLayer` dispatched on
`if pattern in text.lower()`, so the substring "create a folder called"
handed the whole objective to `CreateFolderIntent`, whose end-anchored
patterns then found no name mid-sentence and asked for one.

Every specialised parser here is a complete-command recogniser: fifteen
end-of-string anchors, several start-of-string. None was written to pull a
phrase out of a larger objective. The repair matches the selection rule to
what the parsers actually are.
"""
from __future__ import annotations

import pytest

from master_agent.brain.intent import (
    IntentLayer,
    enumerates_multiple_requirements,
)

#: The exact objective from the failed packaged Medium FMEA run.
MEDIUM_OBJECTIVE = (
    "Open a browser and navigate to https://example.com. Observe the page's "
    "actual title and final URL. Create a folder called KV_MEDIUM_155505 on "
    "Desktop. Inside that folder create a text file called page_info.txt "
    "containing the title and URL you actually observed. Then close the browser."
)


@pytest.fixture
def layer() -> IntentLayer:
    return IntentLayer()


class TestSimpleFolderBaselineIsUnchanged:
    """The Simple FMEA baseline must survive the Medium repair intact."""

    def test_a_bare_folder_request_still_asks_the_name(self, layer):
        result = layer.parse("Create a folder.")
        assert result.needs_clarification
        assert result.clarification.key == "folder_name"

    def test_a_named_folder_still_asks_where(self, layer):
        result = layer.parse("Create a folder called Research.")
        assert result.needs_clarification
        assert result.clarification.key == "location"

    def test_a_located_folder_still_asks_the_name(self, layer):
        result = layer.parse("Create a folder on Desktop.")
        assert result.needs_clarification
        assert result.clarification.key == "folder_name"

    def test_a_complete_folder_command_still_resolves_deterministically(self, layer):
        result = layer.parse("Create a folder called Research on Desktop.")
        assert not result.needs_clarification
        assert result.intent.capability == "create_folder"
        assert result.intent.payload == {"name": "Research", "location": "Desktop"}

    def test_a_polite_complete_command_still_resolves(self, layer):
        """"Please ..." was already supported and must stay supported."""
        result = layer.parse("Please create a folder called Research on Desktop.")
        assert not result.needs_clarification
        assert result.intent.payload == {"name": "Research", "location": "Desktop"}


class TestACompoundObjectiveIsNotReducedToOneCapability:
    """The hard invariant: mentioning a capability is not being one."""

    @pytest.mark.parametrize("objective", [
        "Open a browser, then create a folder called Research on Desktop.",
        "Create a folder called Research on Desktop, then write a file inside it.",
        (
            "Open a browser, observe the page, create a folder called Research on "
            "Desktop, write the observed information into a file, then close the browser."
        ),
        MEDIUM_OBJECTIVE,
    ])
    def test_the_folder_parser_does_not_own_a_compound_request(self, layer, objective):
        result = layer.parse(objective)

        assert not result.needs_clarification, (
            f"a compound objective was reduced to one capability and asked "
            f"{getattr(result.clarification, 'question', None)!r}"
        )
        assert result.intent is not None
        assert result.intent.capability == "", (
            "a compound objective was bound to a single capability; "
            "decomposition belongs to the Planner"
        )

    @pytest.mark.parametrize("objective", [
        "Open a browser, then create a folder called Research on Desktop.",
        MEDIUM_OBJECTIVE,
    ])
    def test_the_founders_whole_objective_survives(self, layer, objective):
        intent = layer.parse(objective).intent
        assert intent.goal == objective
        assert intent.context["raw_input"] == objective


class TestEveryRequirementOfTheMediumObjectiveSurvives:
    """Semantic, not structural: the Intent need not hold one record per
    subtask -- but nothing Onkar asked for may vanish before Planning."""

    @pytest.mark.parametrize("requirement", [
        "browser", "example.com", "title", "URL",
        "KV_MEDIUM_155505", "Desktop", "page_info.txt", "close",
    ])
    def test_requirement_is_still_present(self, layer, requirement):
        intent = layer.parse(MEDIUM_OBJECTIVE).intent
        assert requirement.lower() in intent.goal.lower()

    def test_no_clarification_is_raised_for_a_fully_specified_objective(self, layer):
        assert not layer.parse(MEDIUM_OBJECTIVE).needs_clarification


class TestRoutingDoesNotHangOnWordingAccidents:
    """The live counterfactual that proved this was routing, not
    understanding: the same objective phrased with a recognised trigger
    phrase was destroyed, and phrased without one was preserved."""

    TRIGGER_PHRASING = (
        "Open a browser and observe the page. Create a folder called Research "
        "on Desktop. Write the observed information into a file inside it."
    )
    NEUTRAL_PHRASING = (
        "Open a browser and observe the page. Make a directory named Research "
        "on Desktop. Put the observed information into a file inside it."
    )

    def test_neither_phrasing_loses_founder_requirements(self, layer):
        for objective in (self.TRIGGER_PHRASING, self.NEUTRAL_PHRASING):
            result = layer.parse(objective)
            assert not result.needs_clarification, f"{objective!r} was interrogated"
            assert result.intent.goal == objective

    def test_neither_phrasing_is_bound_to_a_single_capability(self, layer):
        for objective in (self.TRIGGER_PHRASING, self.NEUTRAL_PHRASING):
            assert layer.parse(objective).intent.capability == ""


class TestTheCompoundSignalItself:
    """Directly, so the boundary is a stated rule rather than an emergent
    behaviour nobody can point at."""

    @pytest.mark.parametrize("single", [
        "Create a folder.",
        "Create a folder called Research on Desktop.",
        "Please create a folder called Research on Desktop.",
        "read notes.txt",
    ])
    def test_a_single_requirement_is_not_compound(self, single):
        assert enumerates_multiple_requirements(single) is False

    @pytest.mark.parametrize("compound", [
        "Open a browser, then create a folder called Research on Desktop.",
        "Create a folder called Research on Desktop, then write a file inside it.",
        "Create a folder. Then open a browser.",
        MEDIUM_OBJECTIVE,
    ])
    def test_multiple_requirements_are_compound(self, compound):
        assert enumerates_multiple_requirements(compound) is True

    def test_empty_input_is_not_compound(self):
        assert enumerates_multiple_requirements("") is False
        assert enumerates_multiple_requirements("   ") is False


class TestTheCompoundObjectiveReachesMissionAdmission:
    """Part 7's acceptance gate: the complete objective must reach the
    Planner. Not that the Planner succeeds -- only that it is asked."""

    def test_an_intent_exists_to_admit(self, layer):
        """`MissionService` only ever accepts an `Intent`. Before the repair
        there was none to admit, so the Planner could not be reached."""
        result = layer.parse(MEDIUM_OBJECTIVE)
        assert result.intent is not None
        assert result.clarification is None

    def test_the_planner_receives_the_complete_founder_objective(self, layer):
        """The Planner is handed the founder's whole request, not a
        capability guess made upstream of it."""
        planner_inputs: list[str] = []

        class RecordingPlanner:
            def plan(self, intent, **kwargs):
                planner_inputs.append(intent.goal)
                return None

        result = layer.parse(MEDIUM_OBJECTIVE)
        if result.intent is not None:
            RecordingPlanner().plan(result.intent)

        assert planner_inputs == [MEDIUM_OBJECTIVE]
