"""Create Folder: both the name and the place are the founder's to give.

The defect these lock, observed live:

    Onkar:  Create a folder.
    Somesh: What should the folder be called?
    Onkar:  Research
    ->      created Research on the Desktop

Onkar never said Desktop. `CreateFolderAction` publishes `location` as
optional with a `"desktop"` default and applies it in `run()`, and the
Intent Layer treated a name alone as a complete Intent -- so the action's
default quietly supplied a piece of founder meaning the founder had not
given, and by then there was nothing left to ask.

An action default answers *"what should this argument be when a caller
omits it"*. Founder intent asks *"what did Onkar mean"*. These tests hold
those apart: completeness is decided in the Intent Layer, and no
capability schema may decide it.
"""
from __future__ import annotations

import pytest

from master_agent.brain.intent import ClarificationQuestion, IntentLayer


@pytest.fixture
def layer() -> IntentLayer:
    return IntentLayer()


def _ask(result) -> ClarificationQuestion:
    assert result.needs_clarification, (
        f"expected a question, got intent {getattr(result.intent, 'payload', None)}"
    )
    return result.clarification


class TestWhatTheFounderMustSupply:
    """Cases 1-5 of the required matrix."""

    def test_bare_request_asks_for_the_name_first(self, layer):
        assert _ask(layer.parse("Create a folder")).key == "folder_name"

    def test_a_named_folder_with_no_place_asks_where(self, layer):
        question = _ask(layer.parse("Create a folder called Research"))
        assert question.key == "location"

    def test_a_place_with_no_name_asks_what_it_is_called(self, layer):
        question = _ask(layer.parse("Create a folder on Desktop"))
        assert question.key == "folder_name"

    def test_a_fully_specified_request_needs_nothing(self, layer):
        result = layer.parse("Create a folder called Research on Desktop")
        assert not result.needs_clarification
        assert result.intent.payload == {"name": "Research", "location": "Desktop"}

    def test_an_explicit_non_default_place_survives(self, layer):
        """The location the founder named is the location that is used --
        Documents must not become Desktop on the way through."""
        result = layer.parse("Create a folder called Research in Documents")
        assert not result.needs_clarification
        assert result.intent.payload["location"] == "Documents"


class TestTheQuestionUsesWhatIsAlreadyKnown:
    """Part 7. Deterministic string composition -- no model is asked to
    phrase a question this layer already has all the words for."""

    def test_the_location_question_names_the_folder(self, layer):
        question = _ask(layer.parse("Create a folder called Research"))
        assert "Research" in question.question
        assert question.question == "Where should I create the Research folder?"


class TestMultiRoundResolvesOneLogicalIntent:
    """Part 4. Two answers, one objective. `Research` is not a mission and
    neither is `Desktop`; both are fields of the request Onkar already
    made."""

    def test_both_answers_survive_two_rounds(self, layer):
        original = "Create a folder"

        first = _ask(layer.parse(original))
        assert first.key == "folder_name"

        second_result = layer.clarify(original, "Research", first, supplied={})
        second = _ask(second_result)
        assert second.key == "location"

        # Everything resolved so far travels with the question. Without
        # this the round below re-parses "Create a folder" carrying only a
        # location, the name is gone, and the founder is asked for a name
        # they already gave.
        final = layer.clarify(original, "Desktop", second, supplied={"folder_name": "Research"})
        assert not final.needs_clarification
        assert final.intent.payload == {"name": "Research", "location": "Desktop"}

    def test_the_founders_original_words_remain_the_provenance(self, layer):
        """Part 9 item 10. The Intent grows richer; the record of what was
        actually asked for does not change."""
        original = "Create a folder"
        first = _ask(layer.parse(original))
        second = _ask(layer.clarify(original, "Research", first, supplied={}))
        final = layer.clarify(original, "Desktop", second, supplied={"folder_name": "Research"})

        assert final.intent.context["raw_input"] == original

    def test_every_answer_is_recorded_not_only_the_last(self, layer):
        original = "Create a folder"
        first = _ask(layer.parse(original))
        second = _ask(layer.clarify(original, "Research", first, supplied={}))
        final = layer.clarify(original, "Desktop", second, supplied={"folder_name": "Research"})

        assert final.intent.context["clarified"] == {
            "folder_name": "Research",
            "location": "Desktop",
        }

    def test_a_location_the_founder_already_stated_is_not_asked_for_again(self, layer):
        """"Create a folder on Desktop" -> answer the name -> done. The
        place came from their own sentence, so only one round is needed."""
        original = "Create a folder on Desktop"
        first = _ask(layer.parse(original))
        assert first.key == "folder_name"

        final = layer.clarify(original, "Research", first, supplied={})
        assert not final.needs_clarification
        assert final.intent.payload == {"name": "Research", "location": "Desktop"}


class TestNothingRunsWhileTheIntentIsIncomplete:
    """Parts 5 and 9 items 7-8. An incomplete request must not reach the
    Planner or the filesystem -- proven by counting, not by inspection."""

    @pytest.mark.parametrize(
        "text",
        ["Create a folder", "Create a folder called Research", "Create a folder on Desktop"],
    )
    def test_an_incomplete_request_produces_no_intent_to_admit(self, layer, text):
        result = layer.parse(text)
        assert result.intent is None, "an incomplete request must not yield an admissible Intent"

    def test_the_planner_is_never_called_while_a_field_is_missing(self, layer):
        """`MissionService` is the admission boundary and it is only ever
        handed an `Intent`. A clarification result has none, so there is
        nothing to admit and the Planner is not reached."""
        calls: list[object] = []

        class CountingPlanner:
            def plan(self, intent, **kwargs):  # pragma: no cover - must not run
                calls.append(intent)
                raise AssertionError("planner called for an incomplete Intent")

        planner = CountingPlanner()
        for text in ("Create a folder", "Create a folder called Research"):
            result = layer.parse(text)
            if result.intent is not None:
                planner.plan(result.intent)

        assert calls == []

    def test_the_filesystem_is_never_touched_while_a_field_is_missing(self, layer, tmp_path):
        from master_agent.executor.actions.create_folder import CreateFolderAction

        runs: list[dict] = []

        class CountingAction(CreateFolderAction):
            def run(self, parameters):  # pragma: no cover - must not run
                runs.append(parameters)
                raise AssertionError("filesystem reached for an incomplete Intent")

        action = CountingAction(locations={"desktop": tmp_path})
        for text in ("Create a folder", "Create a folder called Research"):
            result = layer.parse(text)
            if result.intent is not None:
                action.run(result.intent.payload)

        assert runs == []
        assert list(tmp_path.iterdir()) == []


class TestTheCapabilityDefaultDoesNotDefineFounderMeaning:
    """Part 8. The regression guard that matters most.

    The action keeps its default -- other callers rely on it, and Part 6
    says not to break them. What it no longer does is complete a founder's
    sentence. Changing the default must have NO effect on what Onkar is
    asked.
    """

    @pytest.mark.parametrize("default_location", ["desktop", "documents", "downloads"])
    def test_intent_completeness_is_unchanged_by_the_actions_default(
        self, layer, tmp_path, default_location
    ):
        from master_agent.executor.actions.create_folder import CreateFolderAction

        class DifferentlyDefaultedAction(CreateFolderAction):
            def optional_parameters(self):
                return [{
                    "name": "location",
                    "type": "string",
                    "description": "where",
                    "default": default_location,
                }]

        DifferentlyDefaultedAction(locations={default_location: tmp_path})

        # Whatever the action would have defaulted to, the founder is
        # still asked -- the Intent Layer never consults it.
        assert _ask(layer.parse("Create a folder called Research")).key == "location"

    def test_the_intent_layer_does_not_import_the_action(self):
        """Structural, not behavioural: completeness cannot be derived
        from a capability schema if the layer cannot see one.

        Checked over the parsed AST rather than the source text. A
        substring search would pass or fail on prose -- the comment in
        this very module explains the action's default by name -- and
        "the identifier appears somewhere" is not the property under
        test. What matters is that nothing is imported.
        """
        import ast
        import inspect

        from master_agent.brain import intent as intent_module

        tree = ast.parse(inspect.getsource(intent_module))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imported.add(module)
                imported.update(f"{module}.{alias.name}" for alias in node.names)

        offenders = [name for name in imported
                     if "executor" in name or "capabilit" in name or "action" in name.lower()]
        assert offenders == [], (
            f"the Intent Layer can see a capability schema: {offenders}"
        )

    def test_the_action_still_defaults_for_its_other_callers(self, tmp_path):
        """Part 6: do not break unrelated direct internal callers. The
        default is intact -- it simply no longer stands in for a founder."""
        from master_agent.executor.actions.create_folder import CreateFolderAction

        action = CreateFolderAction(locations={"desktop": tmp_path})
        result = action.run({"name": "InternalCaller"})

        assert result.success
        assert (tmp_path / "InternalCaller").is_dir()


class TestTheResolvedIntentReachesTheCapabilityCorrectly:
    """The end of the chain: what the founder resolved is what runs."""

    def test_the_payload_carries_the_founder_resolved_location(self, layer, tmp_path):
        from master_agent.executor.actions.create_folder import CreateFolderAction

        documents = tmp_path / "Documents"
        documents.mkdir()
        desktop = tmp_path / "Desktop"
        desktop.mkdir()

        result = layer.parse("Create a folder called Research in Documents")
        action = CreateFolderAction(locations={"desktop": desktop, "documents": documents})
        outcome = action.run(result.intent.payload)

        assert outcome.success
        assert (documents / "Research").is_dir()
        assert not (desktop / "Research").exists(), "Documents must not become Desktop"
