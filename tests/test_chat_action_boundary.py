"""A conversational word inside an instruction must not claim the instruction.

The founder asked Kalpavriksha to read their CVs, compare them, propose
improvements, and search for matching work. The Conversation Engine
answered with a paragraph about what it can do, and the Planner never saw
the objective.

`_is_capability_inquiry()` was a bag of words over the whole utterance:
`what` anywhere, plus `you`/`your`, plus one of
`do/does/capable/able/help/handle/use/offer/support`. A hundred-word
instruction supplied all three by accident -- *"show me **what you**
propose"* and *"Then **use** the revised profile"*. One word, `use`, was
the difference between a mission and a brochure.

The invariant these tests hold: **a recogniser may claim an utterance only
when the conversational intent describes the utterance as a whole.** Words
in different clauses are not doing the same job. When that cannot be
shown, the engine escalates and the Mission pipeline decides -- an
objective wrongly answered here never reaches the Planner at all, which is
far worse than a question wrongly passed on.
"""
from __future__ import annotations

import pytest

from master_agent.conversation_engine.intent import Intent, IntentClassifier

#: The founder's real objective, verbatim. Not simplified, and `use` is
#: not replaced -- the whole point is that this exact sentence routes.
CV_OBJECTIVE = (
    "Check all of my CVs available in the D drive. Read and compare the relevant "
    "CV files, understand my experience, skills and profile, identify which CV is "
    "the strongest starting point and clearly identify important gaps or "
    "weaknesses. Before changing any CV, show me what you propose to improve and "
    "ask for my permission. After I approve, create a revised CV as a new file "
    "without overwriting my originals. Then use the revised profile to search the "
    "web for current opportunities that genuinely fit me. Give me the best "
    "matching opportunities with company name, role, location, actual job link, "
    "job description or key responsibilities, why the role fits my profile, and "
    "any remaining skill gap I should know about."
)

CONVERSATIONAL = (Intent.CAPABILITY_QUERY, Intent.STATUS_QUERY,
                  Intent.ACTIVITY_QUERY, Intent.PRIORITY_QUERY,
                  Intent.GREETING, Intent.CONTINUATION)


@pytest.fixture
def classify():
    return IntentClassifier().classify


class TestCapabilityQuestionsAreStillAnswered:
    """High precision must not become no recall."""

    @pytest.mark.parametrize("text", [
        "What can you do?",
        "What are your capabilities?",
        "What are your current capabilities?",
        "Can you use a browser?",
        "What can you help me with?",
        "Tell me what you can do.",
        "Tell me what capabilities you have.",
        "What can you actually do?",
        "What are your current browser capabilities?",
        "What are you capable of?",
        "What capabilities do you have?",
        "How can I extend your capabilities?",
    ])
    def test_it_is_a_capability_query(self, text, classify):
        assert classify(text) is Intent.CAPABILITY_QUERY

    def test_the_founders_own_production_phrasing(self, classify):
        """Verbatim from the screenshot that first exposed this route."""
        assert classify(
            "I want to know what are your current capabilities and how can "
            "we add more capabilities to you."
        ) is Intent.CAPABILITY_QUERY


class TestInstructionsWin:
    """Every one of these contains conversational vocabulary and is a job."""

    @pytest.mark.parametrize("text", [
        "Check my CV and tell me what you can improve.",
        "Read all my CVs, show me what you propose to change, then use the "
        "revised profile to search for opportunities.",
        "Use the browser and tell me what you find.",
        "Check what you can improve in this document.",
        "Search my files and tell me what needs attention.",
        "Find the best way you can handle this task and complete it.",
        "Open the website and show me what you can find there.",
    ])
    def test_it_is_not_a_capability_query(self, text, classify):
        assert classify(text) not in CONVERSATIONAL

    def test_the_real_cv_objective_routes_as_an_instruction(self, classify):
        """§12: the exact live objective, unmodified."""
        assert classify(CV_OBJECTIVE) is not Intent.CAPABILITY_QUERY
        assert classify(CV_OBJECTIVE) not in CONVERSATIONAL

    def test_one_word_no_longer_decides(self, classify):
        """`use` was the entire difference. It must not be any more."""
        with_use = CV_OBJECTIVE
        without_use = CV_OBJECTIVE.replace(
            "Then use the revised profile", "Then take the revised profile"
        )
        assert classify(with_use) == classify(without_use)


class TestTheOtherConversationalFamilies:
    """§9: status, activity and priority phrases must not hijack either."""

    @pytest.mark.parametrize("text", [
        "Check system status and save it to a file.",
        "Tell me what's happening on this webpage and summarize it.",
        "Find what needs my attention in this report and highlight it.",
        "Find what needs my attention in this report.",
        "Check if everything is working and write a report about it.",
    ])
    def test_an_instruction_containing_the_phrase_is_not_claimed(
        self, text, classify
    ):
        assert classify(text) not in CONVERSATIONAL

    @pytest.mark.parametrize("text,expected", [
        ("How's the system?", Intent.STATUS_QUERY),
        ("System status", Intent.STATUS_QUERY),
        ("Is everything working?", Intent.STATUS_QUERY),
        ("What's happening?", Intent.ACTIVITY_QUERY),
        ("What are you doing?", Intent.ACTIVITY_QUERY),
        ("What's my priority?", Intent.PRIORITY_QUERY),
        ("What needs my attention?", Intent.PRIORITY_QUERY),
    ])
    def test_the_bare_question_keeps_its_route(self, text, expected, classify):
        assert classify(text) is expected


class TestTheRuleIsStructural:
    """Clause-local, and read from word order -- not a longer word list."""

    def test_a_clause_that_opens_with_an_instruction_is_never_claimed(
        self, classify
    ):
        """"what can you check" is a question; "check what you can do" is a
        job. The words are the same; only the order differs."""
        assert classify("What can you check?") is Intent.CAPABILITY_QUERY
        assert classify("Check what you can do.") not in CONVERSATIONAL

    def test_words_in_separate_clauses_do_not_combine(self, classify):
        """The exact shape of the production failure, in miniature."""
        assert classify(
            "Show me what you propose, then use the revised profile."
        ) not in CONVERSATIONAL

    def test_a_question_mark_is_evidence_not_a_requirement(self, classify):
        """§7: both directions."""
        assert classify("Tell me what you can do") is Intent.CAPABILITY_QUERY
        assert classify(
            'Search my notes for "what can you do?" and list the matches.'
        ) not in CONVERSATIONAL

    def test_trailing_instructions_are_seen_wherever_they_are(self, classify):
        assert classify("What can you do? Also create a folder called Demo.") \
            not in CONVERSATIONAL


class TestUncertaintyEscalates:
    """§8: when it cannot be shown, the Mission pipeline decides."""

    @pytest.mark.parametrize("text", [
        "Sort out the thing we discussed.",
        "The report from yesterday.",
        "Onward.",
    ])
    def test_unrecognised_speech_is_not_claimed(self, text, classify):
        assert classify(text) not in CONVERSATIONAL


class TestDispositionsAreUnchanged:
    """§1: the architecture is preserved -- this changed a recogniser, not
    the pipeline's vocabulary."""

    def test_the_dispositions_still_exist(self):
        from master_agent.conversation_engine.pipeline import Disposition

        assert {"HANDLED", "ESCALATE", "UNAVAILABLE"} <= set(Disposition.__members__)

    def test_an_unrecognised_intent_escalates_rather_than_refusing(self):
        import inspect

        from master_agent.conversation_engine import pipeline

        source = inspect.getsource(pipeline.ResponsePipeline._compose)
        # The final branch is the escalation, and BUILD_REQUEST escalates
        # too -- both were deliberate and neither is this mission's to
        # change.
        assert source.rstrip().endswith("return None, Disposition.ESCALATE")
        assert "Intent.BUILD_REQUEST" in source
