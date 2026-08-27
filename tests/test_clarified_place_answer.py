r"""Answering "where?" with a preposition is not a mistake.

## The defect, from the live session

    Onkar:  create a folder
    Somesh: What should the folder be called?
    Onkar:  Abhishek
    Somesh: Where should I create the Abhishek folder?
    Onkar:  on desktop

    → unknown location 'on desktop'
      (known: d_drive, desktop, documents, downloads)
    → retried three times, escalated, mission failed
    → "That didn't complete. I've kept the details for review."

Every inline pattern in `CreateFolderIntent` strips exactly this grammar:
`(?:on|in)\s+(?:my\s+|the\s+)?` is written into all three of them, which
is why *"create a folder called X **on the Desktop**"* has always worked.
A clarification answer never goes through a pattern, so whatever the
founder typed reached the capability verbatim.

Two paths, one capability, two ideas of what a place is.

## What was fixed, and what deliberately was not

`BaseIntentParser._place()` removes the grammar — a leading preposition,
an article, a trailing "folder"/"directory" — and nothing else. It does
**not** validate. Which places exist is the capability's vocabulary, not
the Brain's, so a founder naming somewhere genuinely unknown still gets
the capability's own answer.

And that answer now reaches them. `_founder_failure_sentence()` used to
flatten it to "That didn't complete", which is true and useless for a
problem the founder could fix in one word. It now repeats the
capability's own list back — read out of the error rather than written
into the surface, because a second copy of that vocabulary is one that
drifts from the list that actually decides.
"""
from __future__ import annotations

import pytest

from master_agent.brain.intent import ClarificationQuestion, IntentLayer

WHERE = ClarificationQuestion(
    question="Where should I create the Abhishek folder?",
    key="location",
    options=(),
    required=True,
)


def clarified(answer: str, *, name: str = "Abhishek") -> dict:
    result = IntentLayer().clarify(
        "create a folder", answer, WHERE, supplied={"folder_name": name}
    )
    assert result.intent is not None, result.clarification
    return dict(result.intent.payload or {})


class TestThePlaceIsUnderstood:
    @pytest.mark.parametrize("answer", [
        "on desktop",
        "Desktop",
        "on the Desktop",
        "on my desktop",
        "the desktop folder",
        "  desktop  ",
        "to the desktop",
        "inside my desktop directory",
    ])
    def test_every_way_a_founder_says_desktop_reaches_the_same_place(self, answer):
        assert clarified(answer)["location"].lower() == "desktop"

    @pytest.mark.parametrize("answer,place", [
        ("in my Documents", "documents"),
        ("the downloads folder", "downloads"),
        ("into Downloads", "downloads"),
    ])
    def test_the_other_places_normalise_too(self, answer, place):
        assert clarified(answer)["location"].lower() == place

    def test_the_answer_the_founder_gave_earlier_still_survives(self):
        """The name came from an earlier round. Normalising the place must
        not disturb the clarification thread."""
        assert clarified("on desktop")["name"] == "Abhishek"

    def test_a_dictated_sentence_is_unchanged(self):
        """The inline path already worked, and must keep working
        identically -- this fix exists to make the two agree, not to move
        the one that was right."""
        result = IntentLayer().parse("create a folder called Research on the Desktop")
        assert result.intent is not None
        payload = dict(result.intent.payload or {})
        assert payload["name"] == "Research"
        assert payload["location"].lower() == "desktop"


class TestItNormalisesGrammarAndNothingElse:
    def test_an_unknown_place_is_passed_through_not_guessed(self):
        """The Brain does not own the capability's vocabulary. A place it
        has never heard of travels on, and the capability answers for
        itself."""
        assert clarified("on the moon")["location"].lower() == "moon"

    def test_a_multi_word_place_keeps_its_words(self):
        assert clarified("in my project archive")["location"].lower() == (
            "project archive"
        )

    def test_an_empty_answer_is_still_no_answer(self):
        """A founder who pressed enter on a blank line has named nothing,
        and a nameless place must not become one."""
        result = IntentLayer().clarify(
            "create a folder", "   ", WHERE, supplied={"folder_name": "Abhishek"}
        )
        assert result.needs_clarification


class TestTheFounderIsToldHowToFixIt:
    def test_an_unknown_place_names_the_places_that_work(self):
        from kalpavriksha_desktop import _founder_failure_sentence

        sentence = _founder_failure_sentence(
            "unknown location 'on the moon' "
            "(known: d_drive, desktop, documents, downloads)"
        )
        assert "on the moon" in sentence
        for place in ("desktop", "documents", "downloads"):
            assert place in sentence.lower()
        assert "didn't complete" not in sentence.lower()

    def test_the_list_is_read_from_the_error_not_written_in_the_surface(self):
        """A vocabulary the surface keeps its own copy of is one that
        drifts from the list that actually decides. Change what the
        capability knows and the sentence follows."""
        from kalpavriksha_desktop import _founder_failure_sentence

        sentence = _founder_failure_sentence(
            "unknown location 'x' (known: alpha, beta_gamma)"
        )
        assert "alpha" in sentence
        assert "beta gamma" in sentence, "an internal key was shown verbatim"

    def test_an_ordinary_failure_is_unchanged(self):
        from kalpavriksha_desktop import _founder_failure_sentence

        assert _founder_failure_sentence("disk exploded") == (
            "That didn't complete. I've kept the details for review."
        )
