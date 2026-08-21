"""`IntentLayer.decide_role()` — the Brain's one reasoning door, used for
one decision.

The Intent Layer used to say of itself *"Never calls a model directly —
the Planner handles model calls."* `VISION_V2` §3.3 calls the Model Router
*"the Brain's single door to reasoning"*, and ADR-0024 Decision 7 states
normatively that this means **every** reasoning call the Brain makes,
whatever it is reasoning about — planning is one such thing, not the only
one. This is that correction.

What these tests care about, in order of how much they'd cost a founder if
they were wrong:

1. The ordinary path never reaches a provider. A founder answering
   "Research" must not pay latency or tokens because a harder case exists.
2. When it does reason, it goes through the SAME routed seam everything
   else uses — no second provider path, no bespoke client.
3. Every failure mode leaves the founder no worse off than the structural
   default, which is what shipped before the door existed.
"""
from __future__ import annotations

import pytest

from master_agent.brain.intent import IntentLayer
from master_agent.brain.utterance import UtteranceRole

#: Neither a question, an instruction, an offered option, nor short enough
#: to read as a value -- the one shape structure reports as undecided.
AMBIGUOUS = "the weather today is quite bad actually"


class RunnerSpy:
    """Stands in for `TieredPromptRunner`, recording what it was asked."""

    def __init__(self, text: str = "answer", ok: bool = True) -> None:
        self.calls: list[tuple[str, object]] = []
        self._text = text
        self._ok = ok

    def run(self, prompt, request, **kwargs):
        self.calls.append((prompt, request))
        outcome = type("Outcome", (), {})()
        outcome.ok = self._ok
        outcome.text = self._text
        return outcome


class DeadRunner:
    def run(self, *args, **kwargs):
        raise RuntimeError("every tier is down")


def _ask(layer, text=AMBIGUOUS, **kwargs):
    kwargs.setdefault("awaiting_answer", True)
    kwargs.setdefault("question", "What should the folder be called?")
    kwargs.setdefault("objective", "Create a folder")
    return layer.decide_role(text, **kwargs)


class TestTheOrdinaryPathNeverReachesAProvider:
    """The most important property here. A door that opened on every turn
    would make the cheapest possible interaction — answering a question
    with one word — the most expensive."""

    @pytest.mark.parametrize("text", [
        "Research", "Desktop", "the second one", "Quarterly Report",
        "nothing thanks", "why are you asking me that?",
        "open example.com instead",
    ])
    def test_structure_settles_it_without_asking(self, text):
        runner = RunnerSpy()
        _ask(IntentLayer(reasoner=runner), text)
        assert runner.calls == [], f"{text!r} cost a provider call"

    def test_nothing_pending_never_asks(self):
        runner = RunnerSpy()
        layer = IntentLayer(reasoner=runner)
        for text in ("open example.com", "what is ready?", "never mind", AMBIGUOUS):
            layer.decide_role(text)
        assert runner.calls == []


class TestItAsksOnlyForTheUndecidedShape:
    def test_a_long_statement_while_a_question_is_open_is_asked_about(self):
        runner = RunnerSpy(text="redirect")
        role = _ask(IntentLayer(reasoner=runner))

        assert len(runner.calls) == 1
        assert role is UtteranceRole.MODIFY_OR_REDIRECT

    @pytest.mark.parametrize("word,expected", [
        ("answer", UtteranceRole.ANSWER_TO_CLARIFICATION),
        ("redirect", UtteranceRole.MODIFY_OR_REDIRECT),
        ("cancel", UtteranceRole.CANCEL_OR_STOP),
        ("question", UtteranceRole.FOLLOW_UP),
    ])
    def test_each_permitted_word_maps_to_its_role(self, word, expected):
        assert _ask(IntentLayer(reasoner=RunnerSpy(text=word))) is expected

    def test_a_wordy_answer_still_resolves(self):
        """Providers add punctuation and prose however firmly they are
        told not to. The first permitted word wins."""
        runner = RunnerSpy(text="redirect. It asks for something different.")
        assert _ask(IntentLayer(reasoner=runner)) is UtteranceRole.MODIFY_OR_REDIRECT


class TestItGoesThroughTheRoutedSeamNotABespokePath:
    """No second provider path and no second semantic router — ADR-0024
    Decision 7 names both as forbidden."""

    def test_the_request_asks_for_the_same_capability_the_planner_asks_for(self):
        runner = RunnerSpy()
        _ask(IntentLayer(reasoner=runner))
        _prompt, request = runner.calls[0]

        assert getattr(request, "capability", None) == "reasoning"

    def test_the_request_identifies_this_caller(self):
        """So a decision trail can say which Brain component asked."""
        runner = RunnerSpy()
        _ask(IntentLayer(reasoner=runner))
        _prompt, request = runner.calls[0]

        assert getattr(request, "requester", None) == "brain_intent_role"

    def test_it_does_not_demand_strong_reasoning_for_a_small_judgement(self):
        """Pushing a cheap, latency-sensitive call up the ladder would
        spend a stronger tier on deciding what a sentence is doing."""
        runner = RunnerSpy()
        _ask(IntentLayer(reasoner=runner))
        _prompt, request = runner.calls[0]

        assert getattr(request, "requires_strong_reasoning", None) is not True

    def test_the_prompt_carries_the_question_and_the_reply(self):
        runner = RunnerSpy()
        _ask(IntentLayer(reasoner=runner))
        prompt, _request = runner.calls[0]

        assert "What should the folder be called?" in prompt
        assert AMBIGUOUS in prompt
        assert "Create a folder" in prompt


class TestEveryFailureLeavesTheFounderNoWorseOff:
    """Reasoning here can only improve on structure. It must never be able
    to make things worse than having no door at all."""

    def test_no_reasoner_at_all_behaves_exactly_as_before(self):
        assert _ask(IntentLayer()) is UtteranceRole.ANSWER_TO_CLARIFICATION

    def test_a_dead_ladder_falls_back_rather_than_raising(self):
        assert _ask(IntentLayer(reasoner=DeadRunner())) is UtteranceRole.ANSWER_TO_CLARIFICATION

    def test_a_refused_request_falls_back(self):
        assert _ask(IntentLayer(reasoner=RunnerSpy(ok=False))) is UtteranceRole.ANSWER_TO_CLARIFICATION

    def test_an_answer_outside_the_four_words_falls_back(self):
        """A provider inventing a seventh role must not be able to invent
        behaviour with it."""
        runner = RunnerSpy(text="it seems like a change of subject to me")
        assert _ask(IntentLayer(reasoner=runner)) is UtteranceRole.ANSWER_TO_CLARIFICATION

    def test_an_empty_answer_falls_back(self):
        assert _ask(IntentLayer(reasoner=RunnerSpy(text="   "))) is UtteranceRole.ANSWER_TO_CLARIFICATION

    def test_a_runner_returning_none_falls_back(self):
        class NoneRunner:
            def run(self, *args, **kwargs):
                return None

        assert _ask(IntentLayer(reasoner=NoneRunner())) is UtteranceRole.ANSWER_TO_CLARIFICATION


class TestParsingIsUnaffected:
    """The door is for role, not for parsing. Adding it must not have
    changed what the layer understands."""

    def test_a_reasoner_does_not_change_parse(self):
        with_door = IntentLayer(reasoner=RunnerSpy(text="cancel"))
        without = IntentLayer()

        a = with_door.parse("create a folder called Research")
        b = without.parse("create a folder called Research")

        assert a.needs_clarification == b.needs_clarification
        assert (a.intent is None) == (b.intent is None)
        if a.intent is not None:
            assert a.intent.goal == b.intent.goal

    def test_parsing_never_calls_the_reasoner(self):
        runner = RunnerSpy()
        layer = IntentLayer(reasoner=runner)

        layer.parse("create a folder called Research")
        layer.parse("read my notes")
        layer.parse("something it has never seen before at all")

        assert runner.calls == [], "parsing reached a provider"
