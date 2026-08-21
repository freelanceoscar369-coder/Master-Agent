"""The Intent Layer as the gate in front of the Planner.

`KALPAVRIKSHA_VISION_V2.md` §3.1 (FROZEN) makes this layer's job explicit:
it "turns raw input into a structured Intent" and "owns follow-up
clarification when intent is ambiguous", deliberately as "a real
parsing/clarification step **so the Planner never has to guess**".

Nothing tested that boundary, which is how a greedy regex shipped: asked
to create a folder "called Research in Documents", the layer produced
name="Research in Documents" and silently replaced the founder's stated
location with a default. These tests assert the contract itself, and
§12's requirement that the routing DECISION -- not merely the wording --
is correct.
"""
from __future__ import annotations

from master_agent.brain import IntentLayer


def parse(text: str):
    return IntentLayer().parse(text)


class TestAFullySpecifiedObjectiveResolves:
    def test_name_and_location_are_separated(self):
        intent = parse("Create a folder called Research on my Desktop.").intent
        assert intent is not None
        assert intent.context["folder_name"] == "Research"
        assert intent.context["location"] == "Desktop"

    def test_the_name_never_swallows_the_location_clause(self):
        """The exact defect: a greedy name group consumed the tail."""
        intent = parse("Create a folder called Research on my Desktop.").intent
        assert "Desktop" not in intent.context["folder_name"]
        assert "on my" not in intent.context["folder_name"]


class TestAnExplicitLocationIsPreservedExactly:
    def test_documents_is_not_silently_replaced_by_desktop(self):
        """The serious case. The founder said Documents; the old parser
        produced location="Desktop" and would have created the folder
        somewhere they never asked for."""
        intent = parse("Create a folder called Research in Documents").intent
        assert intent.context["folder_name"] == "Research"
        assert intent.context["location"] == "Documents"

    def test_downloads_is_preserved_too(self):
        intent = parse("Create a folder called Notes in Downloads").intent
        assert intent.context["location"] == "Downloads"


class TestMissingRequiredInformationClarifies:
    def test_a_bare_folder_request_asks_for_the_name(self):
        result = parse("Create a folder")
        assert result.needs_clarification
        assert result.intent is None
        assert "folder" in result.clarification.question.lower()

    def test_a_location_without_a_name_still_asks_for_the_name(self):
        """Knowing WHERE is not knowing WHAT. Nothing may be inferred
        from the location -- least of all a folder named "Desktop"."""
        result = parse("Create a folder on my Desktop")
        assert result.needs_clarification
        assert result.intent is None

    def test_no_required_value_is_ever_invented(self):
        for text in ("Create a folder", "Create a folder on my Desktop", "create folder"):
            result = parse(text)
            assert result.needs_clarification, text
            assert result.intent is None, text


class TestOptionalInformationUsesTheActionsOwnDefault:
    def test_an_unstated_location_is_asked_about_not_defaulted(self):
        """SUPERSEDED CONTRACT. This asserted that an unstated location is
        left unstated, on the reasoning that `CreateFolderAction` owns the
        default and the Brain should not write product policy.

        That reasoning was right about where a DEFAULT belongs and wrong
        about what completes founder MEANING, and the gap showed up live:
        Onkar said "Create a folder", was asked only for a name, answered
        "Research", and got a folder on the Desktop he had never named.
        The action's default had silently completed his sentence.

        Location is now founder-required, so an unstated one is a question
        rather than an omission. The action keeps its default for its
        other callers -- proven by the test below, which is unchanged.
        """
        result = parse("Create a folder called Research")
        assert result.intent is None, "an unstated location must not yield an admissible Intent"
        assert result.clarification.key == "location"

    def test_the_action_still_supplies_the_default_downstream(self):
        """The default did not disappear -- it moved to the one place
        that owns it."""
        from master_agent.executor.actions.create_folder import CreateFolderAction

        optional = {o["name"]: o for o in CreateFolderAction().optional_parameters()}
        assert optional["location"]["default"] == "desktop"


class TestUnrelatedInputIsNotClarified:
    def test_ordinary_requests_are_not_dragged_into_clarification(self):
        for text in ("Open Chrome and go to https://example.com/", "look at this machine"):
            assert not parse(text).needs_clarification, text

    def test_project_requests_keep_their_own_clarification(self):
        result = parse("Create a project")
        assert result.needs_clarification
        assert "project" in result.clarification.question.lower()


class TestClarificationResolution:
    def test_the_answer_is_not_polluted_by_the_separator(self):
        """`clarify()` rejoins the original with the answer and re-parses.

        The separator was an em-dash, which the parsers read as part of
        the value: answering "Research" produced a folder named
        "— Research".
        """
        layer = IntentLayer()
        assert layer.parse("Create a folder").needs_clarification

        # The rejoin form now lands on the location question rather than a
        # finished Intent -- location became founder-required. What this
        # test is about is unchanged: the NAME must come through clean.
        # The question quotes it back, which is where a polluted value
        # would show ("Where should I create the -- Research folder?").
        resolved = layer.clarify("Create a folder called", "Research")
        assert resolved.needs_clarification
        assert resolved.clarification.key == "location"
        assert resolved.clarification.question == "Where should I create the Research folder?"

    def test_the_resolution_loop_now_has_its_production_caller(self):
        """The gap this used to assert is closed, and this is the test
        that was written to notice.

        Its previous form asserted that **nothing** called `clarify()` --
        clarification was one-way, the founder was asked a question the
        system could not hear the answer to, and ADR-0024 records that as
        its Gap 1. The composition root closes it: `kalpavriksha_desktop
        ._submit_objective` calls `clarify()` with the question's own
        `key`, `options` and everything answered in earlier rounds.

        Two things were wrong with how it checked, both fixed here.

        It searched `src/` only, while the composition root lives at the
        repository root -- so it could never have seen the caller it was
        watching for. And it matched raw source text, so it fired on
        `brain/utterance.py`, whose module docstring *quotes* the old
        `intent_layer.clarify(...)` line to explain what changed. A
        comment describing history is not a call. This asserts the
        behaviour instead, which cannot be tripped by prose.
        """
        layer = IntentLayer()
        opened = layer.parse("Create a folder")
        assert opened.needs_clarification, "precondition: a question is asked"

        resolved = layer.clarify(
            "Create a folder", "Research", opened.clarification,
        )

        # The answer was absorbed as DATA against the question's key --
        # the round trip the previous form said did not exist.
        assert resolved.clarification is None or resolved.clarification.key != "folder_name"
        if resolved.intent is not None:
            assert resolved.intent.context.get("folder_name") == "Research"


class TestThePlannerIsNotReachedForUnresolvedIntent:
    """§12 -- the acceptance criterion is the routing DECISION.

    `MissionService.start()` consults the Intent Layer and must return
    before the Planner when clarification is required. A spy proves the
    Planner was never asked, rather than inferring it from the reply text.
    """

    class _PlannerSpy:
        def __init__(self):
            self.calls = 0

        def plan(self, *args, **kwargs):
            self.calls += 1
            raise AssertionError("the Planner must not be asked to guess")

    def _service(self, spy):
        from master_agent.missions.service import MissionService

        return MissionService(
            planner=spy, mission_control=None, intent_layer=IntentLayer(), reporter=None,
        )

    def test_unresolved_intent_never_reaches_the_planner(self):
        spy = self._PlannerSpy()
        service = self._service(spy)

        outcome = service.start("Create a folder")

        assert spy.calls == 0, "clarification must block the Planner"
        assert not outcome.accepted
        assert outcome.refusal is not None
        assert outcome.refusal.code == "CLARIFICATION_REQUIRED"

    def test_resolved_intent_does_reach_the_planner(self):
        """The other half of the boundary. A gate that blocks everything
        is not a gate, so the spy must also record exactly one call for a
        sufficiently specified objective."""
        from master_agent.missions.service import MissionService

        class _CountingPlanner:
            def __init__(self):
                self.calls = 0
                self.received = None

            def plan(self, intent, *args, **kwargs):
                self.calls += 1
                self.received = intent
                raise RuntimeError("stop here -- reaching the Planner is the assertion")

        spy = _CountingPlanner()
        service = MissionService(
            planner=spy, mission_control=None, intent_layer=IntentLayer(), reporter=None,
        )

        try:
            service.start("Create a folder called Research on my Desktop.")
        except Exception:
            pass

        assert spy.calls == 1, "a resolved Intent must reach the Planner"
        # ...and it must arrive already understood, not as raw prose.
        assert spy.received is not None
        assert spy.received.context["folder_name"] == "Research"
        assert spy.received.context["location"] == "Desktop"

    def test_the_founder_receives_the_actual_question(self):
        """Clarification is a decision, not a refusal: the question has to
        survive as the question."""
        spy = self._PlannerSpy()
        outcome = self._service(spy).start("Create a folder")

        assert "folder" in (outcome.refusal.detail or "").lower()
