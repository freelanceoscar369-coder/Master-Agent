"""A clarification answer is evidence, not a field value.

## The defect

    Somesh: Where should I create the Abhishek folder?
    Onkar:  on desktop
    → unknown location 'on desktop'
      (known: d_drive, desktop, documents, downloads)

`clarify()` did `answers[question.key] = answer`, so the founder's words
travelled untouched into a capability argument. The founder had answered
correctly; nothing had *understood* the answer, because nothing was asked
to — the layer whose constitutional job is turning language into
structure was copying a string.

The first repair attempted here was a regex that stripped prepositions.
That was rejected, correctly: it makes one phrasing work and leaves the
next one to be discovered by the founder. It has been removed.

## What replaces it

`IntentLayer.understand()` reads an utterance against **every field the
parser is gathering**, so one answer may settle several and a correction
may revise one already given. Two stages:

* **Stated** — a closed field is matched against *the values the
  capability can actually act on*. Nothing enumerates English. What is
  enumerated is the vocabulary the capability publishes anyway, so
  "Desktop", "on desktop", "put it on my desktop please" and "let's use
  my Desktop" all resolve without any of them appearing in the source.
* **Reasoned** — when structure cannot settle it, the Brain's existing
  reasoning door returns a narrow structured extraction, validated
  before it is believed.

Neither stage guesses. An utterance that cannot be pinned down is a
question, not a coin toss.

## How these tests are written

By **semantic class and equivalence**, not by phrase. The phrasings below
are evidence that a class works; they are test data and must never become
a production table. A new phrasing nobody listed should pass for the same
reason the listed ones do.
"""
from __future__ import annotations

import json

import pytest

from master_agent.brain.intent import (
    REASONED,
    STATED,
    ClarificationQuestion,
    IntentLayer,
)

#: The vocabulary the filesystem capability actually publishes, including
#: the founder's D: drive as the composition root widens it.
PLACES = ("d_drive", "desktop", "documents", "downloads")

FOLDER_FIELDS = ("folder_name", "location")


def name_question() -> ClarificationQuestion:
    return ClarificationQuestion(
        question="What should the folder be called?",
        key="folder_name", required=True, gathering=FOLDER_FIELDS,
    )


def where_question(name: str = "Notes") -> ClarificationQuestion:
    return ClarificationQuestion(
        question=f"Where should I create the {name} folder?",
        key="location", required=True, gathering=FOLDER_FIELDS,
    )


class Reasoner:
    """The Brain's door, stubbed. Records what it was asked."""

    def __init__(self, reply: str = "") -> None:
        self.reply = reply
        self.prompts: list[str] = []

    def run(self, prompt, request, **kwargs):
        self.prompts.append(prompt)

        class Outcome:
            ok = True
            text = self.reply

        return Outcome()


class DeadReasoner:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def run(self, prompt, request, **kwargs):
        self.prompts.append(prompt)
        raise RuntimeError("no provider configured")


def layer(reasoner=None) -> IntentLayer:
    return IntentLayer(reasoner=reasoner, vocabularies={"location": PLACES})


def resolve(answer: str, *, question=None, known=None, reasoner=None,
            original: str = "create a folder"):
    """One clarification turn. Returns (payload, question_asked)."""
    result = layer(reasoner).clarify(
        original, answer, question or where_question(),
        supplied=known if known is not None else {"folder_name": "Notes"},
    )
    if result.needs_clarification:
        return None, result.clarification.question
    return dict(result.intent.payload or {}), None


# =====================================================================
# The vocabulary is the capability's, and nothing enumerates English
# =====================================================================


class TestAPlaceIsRecognisedByWhatTheMachineCanDo:
    @pytest.mark.parametrize("answer", [
        "desktop",
        "Desktop",
        "on desktop",
        "on my desktop",
        "put it on the desktop please",
        "Desktop is fine",
        "use Desktop",
        "let's use my Desktop",
        "I'd like it on the Desktop, thanks",
    ])
    def test_every_way_of_naming_a_place_resolves_to_that_place(self, answer):
        """Test DATA, not a production table. Each of these mentions a
        value the capability publishes; none of them is written down
        anywhere in `src/`."""
        payload, asked = resolve(answer)
        assert asked is None, asked
        assert payload["location"] == "desktop"

    @pytest.mark.parametrize("answer,place", [
        ("in my Documents", "documents"),
        ("the downloads folder", "downloads"),
        ("stick it in Downloads", "downloads"),
        ("d drive", "d_drive"),
        ("put it on the D drive", "d_drive"),
    ])
    def test_the_other_published_places_resolve_too(self, answer, place):
        payload, asked = resolve(answer)
        assert asked is None, asked
        assert payload["location"] == place

    def test_no_provider_is_needed_for_any_of_them(self):
        """The fast path is the point. A founder naming a place the
        machine has must not pay for a model to notice."""
        reasoner = Reasoner()
        payload, asked = resolve("put it on my desktop please", reasoner=reasoner)
        assert payload["location"] == "desktop"
        assert reasoner.prompts == []

    def test_the_source_records_that_structure_settled_it(self):
        result = layer().clarify(
            "create a folder", "on my desktop", where_question(),
            supplied={"folder_name": "Notes"},
        )
        evidence = result.intent.context["field_evidence"]["location"]
        assert evidence["source"] == STATED
        assert evidence["evidence"] == "on my desktop"


class TestTheVocabularyIsNotHardcodedHere:
    def test_a_place_the_capability_does_not_publish_is_not_resolved(self):
        """Nothing is special about the names above. Change the
        vocabulary and the understanding changes with it."""
        narrow = IntentLayer(vocabularies={"location": ("documents",)})
        result = narrow.clarify(
            "create a folder", "on my desktop", where_question(),
            supplied={"folder_name": "Notes"},
        )
        assert result.needs_clarification

    def test_a_place_only_this_machine_has_is_resolved(self):
        wide = IntentLayer(vocabularies={"location": ("desktop", "vault")})
        result = wide.clarify(
            "create a folder", "put it in the vault", where_question(),
            supplied={"folder_name": "Notes"},
        )
        assert dict(result.intent.payload)["location"] == "vault"


# =====================================================================
# Metamorphic: different roads, same canonical Intent
# =====================================================================


class TestSemanticEquivalence:
    def canonical(self, original: str, answers: list[str]):
        """Walk a real conversation: parse, then answer whatever it asks.

        The questions are NOT supplied by the test. Whatever the layer
        decides to ask is what gets answered, which is the only way to
        prove that the conversation converges rather than that a fixture
        does.
        """
        brain = layer()
        result = brain.parse(original)
        known: dict[str, str] = {}
        for answer in answers:
            assert result.needs_clarification, "nothing was asked"
            result = brain.clarify(
                original, answer, result.clarification, supplied=known
            )
            known = dict(result.resolved or known)
        assert result.intent is not None, "the conversation never resolved"
        return dict(result.intent.payload or {})

    def test_one_sentence_and_two_turns_agree(self):
        """*"Create Abhishek on my desktop"* and the same thing said over
        two turns must mean the same thing. This is the property that
        matters: not that a phrase parses, but that roads converge."""
        direct = dict(
            layer().parse(
                "create a folder called Abhishek on the Desktop"
            ).intent.payload
        )
        staged = self.canonical("create a folder", ["Abhishek", "on my desktop"])
        assert staged["name"] == direct["name"] == "Abhishek"
        assert staged["location"].lower() == direct["location"].lower() == "desktop"

    def test_the_order_the_founder_supplies_things_in_does_not_matter(self):
        first = self.canonical("create a folder", ["Abhishek", "Documents"])
        second = dict(
            layer().parse(
                "create a folder called Abhishek in Documents"
            ).intent.payload
        )
        assert first["name"] == second["name"]
        assert first["location"].lower() == second["location"].lower()

    def test_utterances_that_mean_different_things_stay_different(self):
        """The guard on the guard. An equivalence test that passes for
        everything proves nothing."""
        desktop, _ = resolve("on my desktop")
        documents, _ = resolve("in Documents")
        assert desktop["location"] != documents["location"]


# =====================================================================
# Context: the same word, two questions
# =====================================================================


class TestTheQuestionIsPartOfTheMeaning:
    def test_a_bare_reply_answers_the_question_that_was_asked(self):
        """"Desktop" answering *what should it be called* is a NAME. A
        vocabulary scan that ran regardless would file the founder's
        chosen name as a location as well."""
        result = layer().clarify(
            "create a folder", "Desktop", name_question(), supplied={},
        )
        # The name is settled; the place has not been asked about yet.
        assert result.needs_clarification
        assert "Desktop folder" in result.clarification.question
        assert result.clarification.key == "location"

    def test_the_same_word_answering_where_is_a_place(self):
        payload, asked = resolve("Desktop")
        assert asked is None
        assert payload["location"] == "desktop"
        assert payload["name"] == "Notes"


# =====================================================================
# Uncertainty is a question, never a guess
# =====================================================================


class TestItAsksRatherThanGuesses:
    def test_two_places_in_one_answer_is_ambiguity(self):
        payload, asked = resolve("desktop or documents")
        assert payload is None
        assert asked

    def test_a_referent_with_nothing_to_refer_to_is_ambiguity(self):
        """"put it there" names nowhere. Reasoning is asked, says so, and
        the founder is asked again."""
        reasoner = Reasoner(json.dumps({"fields": {}, "ambiguous": True}))
        payload, asked = resolve("put it there", reasoner=reasoner)
        assert payload is None
        assert asked
        assert reasoner.prompts, "the reasoning door was never consulted"

    def test_somewhere_the_machine_cannot_reach_is_not_invented(self):
        reasoner = Reasoner(json.dumps({"fields": {"location": "moon"}}))
        payload, asked = resolve("on the moon", reasoner=reasoner)
        assert payload is None, "a value outside the vocabulary was accepted"
        assert asked

    def test_a_dead_reasoning_ladder_asks_rather_than_fails(self):
        reasoner = DeadReasoner()
        payload, asked = resolve("wherever the last one went", reasoner=reasoner)
        assert payload is None
        assert asked
        assert reasoner.prompts, "the door was not even tried"

    @pytest.mark.parametrize("reply", [
        "not json at all",
        '{"fields": "documents"}',
        '{"ambiguous": false}',
        "",
    ])
    def test_unvalidated_output_never_becomes_intent(self, reply):
        payload, asked = resolve(
            "wherever we put the last one", reasoner=Reasoner(reply),
        )
        assert payload is None
        assert asked


# =====================================================================
# One answer, several fields — and corrections
# =====================================================================


class TestAnAnswerMayCarryMoreThanWasAsked:
    def test_a_reply_can_settle_two_fields_at_once(self):
        reasoner = Reasoner(json.dumps({
            "fields": {"folder_name": "Finance", "location": "documents"},
        }))
        payload, asked = resolve(
            "actually call it Finance and put it in Documents",
            question=where_question("Notes"),
            known={"folder_name": "Notes"},
            reasoner=reasoner,
        )
        assert asked is None, asked
        assert payload["name"] == "Finance"
        assert payload["location"] == "documents"

    def test_a_correction_replaces_the_stale_value(self):
        result = layer().clarify(
            "create a folder", "actually use Documents instead",
            where_question("Notes"), supplied={"folder_name": "Notes",
                                               "location": "desktop"},
        )
        assert dict(result.intent.payload)["location"] == "documents"

    def test_the_record_says_what_was_replaced(self):
        result = layer().clarify(
            "create a folder", "use Documents instead",
            where_question("Notes"), supplied={"folder_name": "Notes",
                                               "location": "desktop"},
        )
        evidence = result.intent.context["field_evidence"]["location"]
        assert evidence["value"] == "documents"
        assert evidence["replaced"] == "desktop"

    def test_a_reasoned_field_is_recorded_as_reasoned(self):
        reasoner = Reasoner(json.dumps({"fields": {"location": "documents"}}))
        result = layer(reasoner).clarify(
            "create a folder", "same place as the report from last week",
            where_question("Notes"), supplied={"folder_name": "Notes"},
        )
        evidence = result.intent.context["field_evidence"]["location"]
        assert evidence["source"] == REASONED

    def test_the_reasoning_prompt_asks_for_extraction_not_for_a_decision(self):
        """The failure mode this avoids is documented in
        `_submit_objective`: an unconstrained reasoner asked what to do
        proposes an action. This one is asked only which named fields the
        sentence supplies."""
        reasoner = Reasoner(json.dumps({"fields": {}}))
        resolve("somewhere sensible", reasoner=reasoner)
        prompt = reasoner.prompts[0]
        assert "which of these fields" in prompt.lower()
        assert "ONLY what the founder actually said" in prompt
        for place in PLACES:
            assert place in prompt, "the vocabulary was not offered"


# =====================================================================
# The same mechanism, other Intent families
# =====================================================================


class TestThisIsNotAFolderPatch:
    def test_a_project_name_answer_is_consumed(self):
        """`CreateProjectIntent` asked for a name and never read the
        reply -- the same class of defect, in an open-vocabulary field."""
        result = layer().clarify(
            "create a project",
            "Atlas",
            ClarificationQuestion(
                question="What should the project be called?",
                key="project_name", required=True, gathering=("project_name",),
            ),
            supplied={},
        )
        assert result.intent is not None, "the answer was ignored again"
        assert result.intent.context["project_name"] == "Atlas"

    def test_a_list_directory_answer_is_understood_against_the_vocabulary(self):
        """`ListDirectoryIntent` shares the closed vocabulary, so it
        inherits the understanding rather than reimplementing it."""
        result = layer().clarify(
            "list files",
            "in my Downloads please",
            ClarificationQuestion(
                question="Which folder should I list?",
                key="location", required=True, gathering=("location",),
            ),
            supplied={},
        )
        assert result.intent is not None
        assert result.intent.context["location"] == "downloads"

    def test_all_three_families_share_one_implementation(self):
        """Structural, not incidental: understanding happens in
        `clarify()`, so a parser gets it by asking a question rather than
        by copying code."""
        import inspect

        from master_agent.brain import intent as module

        source = inspect.getsource(module.IntentLayer.clarify)
        assert "self.understand(" in source
        assert source.count("self.understand(") == 1


# =====================================================================
# Nothing that used to work stopped working
# =====================================================================


class TestTheDirectPathIsUntouched:
    @pytest.mark.parametrize("sentence,name,place", [
        ("create a folder called Research on the Desktop", "Research", "desktop"),
        ("create a folder called Notes in Documents", "Notes", "documents"),
    ])
    def test_a_fully_dictated_sentence_still_parses_structurally(
        self, sentence, name, place
    ):
        payload = dict(layer().parse(sentence).intent.payload)
        assert payload["name"] == name
        assert payload["location"].lower() == place

    def test_an_under_specified_request_still_asks(self):
        result = layer().parse("create a folder")
        assert result.needs_clarification
        assert result.clarification.key == "folder_name"

    def test_the_question_carries_the_whole_field_set(self):
        result = layer().parse("create a folder")
        assert result.clarification.gathering == FOLDER_FIELDS

    def test_an_empty_answer_is_still_no_answer(self):
        result = layer().clarify(
            "create a folder", "   ", where_question(),
            supplied={"folder_name": "Notes"},
        )
        assert result.needs_clarification


# =====================================================================
# When a place genuinely is not one the machine has
# =====================================================================


class TestTheFounderIsToldHowToFixIt:
    """The dictated path can still name somewhere unreachable -- *"create
    a folder called X on the moon"* is parsed structurally and refused by
    the capability. The founder used to read "That didn't complete",
    which is true and useless for something they could fix in one word.

    Carried over from the superseded phrase-normalising work, because
    this half of it was right: the improvement is about what the founder
    is told, not about how their words are parsed.
    """

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
        drifts from the list that actually decides."""
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


# =====================================================================
# A question you cannot answer is a trap
# =====================================================================


class TestNoParserCanAskForever:
    """The loop a founder can only escape by giving up.

        Onkar:  search for new 2026 action rpg games and give me demo
                version download links
        Somesh: What should I search for?
        Onkar:  Action RPG games released in 2026
        Somesh: What should I search for?
        Onkar:  Action RPG games released in 2026
        Somesh: What should I search for?
        Onkar:  stop

    Two defects at once. `SearchFilesIntent` claimed a WEB research
    request because the substring "search for" appears in it — routing it
    to the wrong capability family entirely — and then, having claimed
    it, never read the answers, so the same question came back forever.

    These are structural guards over the whole pattern table, not tests
    of the two parsers that happened to fail. A parser added tomorrow is
    held to the same rule.
    """

    def parsers(self):
        return list(layer()._patterns)

    def test_every_parser_that_asks_can_use_the_answer(self):
        """If a parser asks for a field, giving it that field must move
        the conversation forward. Asking again is the loop."""
        brain = layer()
        stuck = []
        for trigger, _handler in self.parsers():
            first = brain.parse(trigger)
            if not first.needs_clarification:
                continue
            key = first.clarification.key
            again = brain.parse(trigger, supplied={key: "AcceptanceValue"})
            if (again.needs_clarification
                    and again.clarification.key == key):
                stuck.append(f"{trigger!r} keeps asking for {key!r}")
        assert not stuck, "; ".join(stuck)

    def test_a_parser_that_cannot_use_its_answer_declines_instead(self):
        """The backstop, for a parser whose own reading genuinely fails.
        It must hand the sentence on rather than ask a third time."""
        from master_agent.brain.intent import _may_claim

        class Stuck:
            needs_clarification = True
            clarification = ClarificationQuestion(
                question="What should I search for?", key="pattern",
            )

        assert _may_claim("search for x", "search for", Stuck(),
                          {"pattern": "already answered"}) is False

    def test_a_first_question_is_still_allowed(self):
        from master_agent.brain.intent import _may_claim

        class Asking:
            needs_clarification = True
            clarification = ClarificationQuestion(
                question="What should I search for?", key="pattern",
            )

        assert _may_claim("search for", "search for", Asking(), {}) is True


class TestAParserOnlyClaimsWhatItCanRead:
    def test_a_web_request_is_not_a_file_search(self):
        """The founder's own sentence. It must not be claimed by the
        filesystem parser merely because "search for" appears in it."""
        result = layer().parse(
            "search for new 2026 action rpg games and give me demo "
            "version download links"
        )
        assert not result.needs_clarification, (
            "a web research request was claimed by a filesystem parser"
        )
        assert result.intent is not None
        assert result.intent.capability == "", (
            "a typed capability was asserted over a request nobody parsed"
        )

    @pytest.mark.parametrize("sentence", [
        "search for new 2026 action rpg games and give me demo version download links",
        "delete everything we no longer need from last quarter's archive folder",
        "read through the competitor pricing pages and tell me what changed",
    ])
    def test_a_sentence_saying_far_more_than_its_trigger_travels_on(self, sentence):
        """Declining is safe: the sentence reaches the Planner, which
        holds the whole capability catalogue and owns decomposition."""
        result = layer().parse(sentence)
        assert not result.needs_clarification
        assert result.intent.capability == ""

    @pytest.mark.parametrize("sentence,question", [
        ("create a folder", "What should the folder be called?"),
        ("create a folder on the Desktop", "What should the folder be called?"),
        ("list files", "Which folder should I list?"),
        ("search for", "What should I search for?"),
    ])
    def test_a_sentence_that_is_its_trigger_still_asks(self, sentence, question):
        """The genuine missing-field case, which clarification exists
        for, is untouched."""
        result = layer().parse(sentence)
        assert result.needs_clarification, sentence
        assert result.clarification.question == question

    def test_a_sentence_a_parser_can_read_is_still_claimed(self):
        payload = dict(
            layer().parse(
                "create a folder called Research on the Desktop"
            ).intent.payload
        )
        assert payload["name"] == "Research"


    def test_an_empty_reply_is_not_an_answer_already_given(self):
        """The loop-breaker must not fire on silence. A founder who
        pressed enter on a blank line has said nothing, and the question
        is still owed to them -- treating that as answered made a folder
        request fall through to the project parser and get asked about a
        project it never mentioned."""
        from master_agent.brain.intent import _may_claim

        class Asking:
            needs_clarification = True
            clarification = ClarificationQuestion(
                question="What should the folder be called?", key="folder_name",
            )

        assert _may_claim("create a folder", "create a folder", Asking(),
                          {"folder_name": ""}) is True
        assert _may_claim("create a folder", "create a folder", Asking(),
                          {"folder_name": "   "}) is True
        assert _may_claim("create a folder", "create a folder", Asking(),
                          {"folder_name": "Research"}) is False
