"""`brain/utterance.py` — a pending question is context, not ownership.

Every case in the "EXACT INTENT REGRESSIONS" section of the canonical
convergence brief appears here as a test, using the founder's own words
from that brief rather than paraphrases, so a future session can match
them up one for one.
"""
from __future__ import annotations

import pytest

from master_agent.brain.utterance import (
    UtteranceRole,
    clauses,
    opens_an_instruction,
    role_of,
)


class TestTheBriefsExactRegressions:
    """The six exchanges the brief requires to work."""

    def test_nothing_thanks_closes_the_question_it_does_not_name_a_file(self):
        """Somesh: "Which file should I read?" / Founder: "nothing thanks".

        The shipped behaviour took `nothing thanks` as a filename, planned
        it as a file-reading objective, and asked the same question again.
        """
        assert role_of("nothing thanks", awaiting_answer=True) is UtteranceRole.CANCEL_OR_STOP

    def test_a_redirect_is_not_swallowed_by_the_open_question(self):
        """Pending clarification / Founder: "open example.com instead"."""
        assert (
            role_of("open example.com instead", awaiting_answer=True)
            is UtteranceRole.MODIFY_OR_REDIRECT
        )

    def test_a_question_back_is_a_follow_up_not_field_data(self):
        """Pending clarification / Founder: "why are you asking me that?"."""
        assert (
            role_of("why are you asking me that?", awaiting_answer=True)
            is UtteranceRole.FOLLOW_UP
        )

    def test_a_real_answer_is_still_an_answer(self):
        """Pending: "What should the folder be called?" / Founder: "Research".

        The whole point of the module is that it did not break this.
        """
        assert role_of("Research", awaiting_answer=True) is UtteranceRole.ANSWER_TO_CLARIFICATION

    def test_a_location_answer_is_still_an_answer(self):
        """Pending: "Where should I create it?" / Founder: "Desktop"."""
        assert role_of("Desktop", awaiting_answer=True) is UtteranceRole.ANSWER_TO_CLARIFICATION

    def test_what_is_ready_asks_about_what_was_just_said(self):
        """Somesh: "...Everything is ready." / Founder: "what is ready?"

        Nothing is pending, so this is not a clarification answer; it is a
        question about the previous turn, and must not become mission work.
        """
        assert role_of("what is ready?") is UtteranceRole.FOLLOW_UP


class TestAPendingQuestionIsContextNotOwnership:
    """The invariant, stated directly."""

    @pytest.mark.parametrize("text,expected", [
        ("never mind", UtteranceRole.CANCEL_OR_STOP),
        ("forget it", UtteranceRole.CANCEL_OR_STOP),
        ("cancel that", UtteranceRole.CANCEL_OR_STOP),
        ("stop", UtteranceRole.CANCEL_OR_STOP),
        ("no thanks", UtteranceRole.CANCEL_OR_STOP),
        ("don't bother", UtteranceRole.CANCEL_OR_STOP),
        ("actually, leave it", UtteranceRole.CANCEL_OR_STOP),
        ("read the other file instead", UtteranceRole.MODIFY_OR_REDIRECT),
        ("create a folder on the Desktop", UtteranceRole.MODIFY_OR_REDIRECT),
        ("what do you mean?", UtteranceRole.FOLLOW_UP),
        ("why?", UtteranceRole.FOLLOW_UP),
    ])
    def test_an_open_question_does_not_claim_these(self, text, expected):
        assert role_of(text, awaiting_answer=True) is expected

    @pytest.mark.parametrize("text", [
        "Research", "Desktop", "my notes folder", "C:/Users/Onkar/Desktop",
        "the second one", "Quarterly Report",
    ])
    def test_but_it_does_claim_a_plain_value(self, text):
        assert role_of(text, awaiting_answer=True) is UtteranceRole.ANSWER_TO_CLARIFICATION


class TestOfferedOptionsWinOutright:
    """A founder picking an option they were offered is answering, even
    when the option reads like a refusal. This is what keeps the stated
    limit from biting wherever a producer can enumerate choices."""

    def test_an_offered_option_that_looks_like_a_refusal_is_still_an_answer(self):
        assert role_of(
            "none", awaiting_answer=True, options=("none", "all", "the first"),
        ) is UtteranceRole.ANSWER_TO_CLARIFICATION

    def test_option_matching_ignores_case_and_padding(self):
        assert role_of(
            "  Stop  ", awaiting_answer=True, options=("stop", "continue"),
        ) is UtteranceRole.ANSWER_TO_CLARIFICATION

    def test_without_that_option_the_same_word_closes_the_question(self):
        """The stated limit, asserted rather than left implicit."""
        assert role_of("stop", awaiting_answer=True) is UtteranceRole.CANCEL_OR_STOP


class TestWithNothingPending:
    @pytest.mark.parametrize("text,expected", [
        ("open example.com", UtteranceRole.NEW_OBJECTIVE),
        ("create a folder called Research", UtteranceRole.NEW_OBJECTIVE),
        ("read my notes", UtteranceRole.NEW_OBJECTIVE),
        ("what is ready?", UtteranceRole.FOLLOW_UP),
        ("why did that fail?", UtteranceRole.FOLLOW_UP),
        ("never mind", UtteranceRole.CANCEL_OR_STOP),
    ])
    def test_roles(self, text, expected):
        assert role_of(text) is expected

    def test_empty_input_is_not_an_objective(self):
        assert role_of("") is UtteranceRole.ORDINARY_CONVERSATION
        assert role_of("   ") is UtteranceRole.ORDINARY_CONVERSATION


class TestAnAbandonmentMustBeTheWholeUtterance:
    """Substring matching is what would make a folder named "Stop That"
    into a cancellation. The match is whole-utterance, modulo filler."""

    @pytest.mark.parametrize("text", [
        "Stop That Nonsense",
        "cancel the subscription form",
        "no results folder",
        "nothing_important.txt",
    ])
    def test_a_value_containing_an_abandonment_word_is_still_an_answer(self, text):
        assert role_of(text, awaiting_answer=True) is UtteranceRole.ANSWER_TO_CLARIFICATION


class TestSentenceStructureHelpers:
    """These are duplicated from `conversation_engine/intent.py` because an
    enforced boundary forbids sharing them (see the module docstring).
    Tested here so the copy cannot silently drift into different behaviour."""

    @pytest.mark.parametrize("clause,expected", [
        ("check what you can improve", True),
        ("what can you check", False),
        ("please open the file", True),
        ("then read it", True),
        ("the file is open", False),
        ("", False),
    ])
    def test_opens_an_instruction_reads_the_first_word_only(self, clause, expected):
        assert opens_an_instruction(clause) is expected

    def test_clauses_split_on_enders_and_joins(self):
        assert clauses("open the file and then read it") == ["open the file", "read it"]
        assert clauses("do this. then that") == ["do this", "then that"]
        assert clauses("") == []
