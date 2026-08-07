"""Mission Brief 035 — verifying generated text.

The second concrete `Verifier` against ADR-0011's frozen subsystem, and
the piece MB033 and MB034 were both blocked on: until something could say
whether an answer was any good, the Prompt Cache could never hit and the
Prompt Library could never be written.

Most of this file is about the two things that make a verdict worth
having: that it is computed from the text by arithmetic a second reader
could repeat, and that **nothing asks a model whether a model did well** —
the recursion ADR-0017 refused to start.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from master_agent.ai_infrastructure import text_verifier as module
from master_agent.ai_infrastructure.text_verifier import (
    ENVIRONMENT,
    MAX_OBSERVED,
    VERIFIER_NAME,
    TextVerifier,
    at_least_words,
    contains,
    excludes,
    expect,
    is_json,
    json_equals,
    json_has,
    matches,
    not_empty,
    observe,
    passed,
    verify_text,
)
from master_agent.verification.evidence import (
    Evidence,
    ExpectedOutcome,
    ObservationCheck,
    Verdict,
)
from master_agent.verification.verifier import Verifier

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "master_agent"
    / "ai_infrastructure"
    / "text_verifier.py"
)


# =========================================================================
# The observation — facts a second reader could recompute
# =========================================================================


def test_the_text_itself_is_observed():
    assert observe("Blue")["text"] == "Blue"


def test_an_answer_is_measured_rather_than_judged():
    observation = observe("one two three")

    assert observation["word_count"] == 3
    assert observation["length"] == len("one two three")
    assert observation["empty"] is False


@pytest.mark.parametrize("blank", ["", "   ", "\n\n", "\t "])
def test_a_blank_answer_is_reported_as_empty(blank):
    assert observe(blank)["empty"] is True


def test_leading_and_trailing_space_does_not_count_towards_length():
    assert observe("  hi  ")["length"] == 2


def test_the_normalised_view_is_lowercased_and_collapsed():
    """So a `contains` check can be written without guessing the model's
    casing or line breaks."""
    assert observe("The   SKY\nis Blue")["normalised"] == "the sky is blue"


def test_lines_are_counted_ignoring_blank_ones():
    observation = observe("first\n\n  \nsecond\n")

    assert observation["line_count"] == 2
    assert observation["first_line"] == "first"
    assert observation["last_line"] == "second"


def test_an_empty_answer_has_no_lines():
    observation = observe("")

    assert observation["line_count"] == 0
    assert observation["first_line"] == ""
    assert observation["last_line"] == ""


def test_prose_is_not_json():
    observation = observe("The sky is blue.")

    assert observation["is_json"] is False
    assert "json" not in observation


def test_json_is_parsed_so_checks_can_reach_inside_it():
    observation = observe('{"name": "Ved", "items": [{"id": 1}]}')

    assert observation["is_json"] is True
    assert observation["json"]["name"] == "Ved"


def test_a_fenced_json_block_still_parses():
    """A model asked for JSON very often returns it inside ```json … ```,
    and refusing that would be pedantry rather than verification."""
    observation = observe('```json\n{"ok": true}\n```')

    assert observation["is_json"] is True
    assert observation["json"] == {"ok": True}


def test_a_fenced_block_without_a_language_parses_too():
    assert observe('```\n{"ok": true}\n```')["is_json"] is True


def test_broken_json_is_not_json():
    assert observe('{"unclosed": ')["is_json"] is False


@pytest.mark.parametrize("scalar", ["1", '"a string"', "true", "null"])
def test_a_bare_json_scalar_is_still_json(scalar):
    assert observe(scalar)["is_json"] is True


def test_a_very_long_answer_is_clipped_and_says_so():
    """Truncating the thing under test would make a check pass or fail on
    where the cut fell, so the fact that it happened is recorded."""
    observation = observe("x" * (MAX_OBSERVED + 10))

    assert observation["truncated"] is True
    assert len(observation["text"]) == MAX_OBSERVED


def test_a_normal_answer_is_not_truncated():
    assert observe("short")["truncated"] is False


@pytest.mark.parametrize("junk", [None, 12, [], {}])
def test_something_that_is_not_text_observes_as_empty(junk):
    assert observe(junk)["empty"] is True


def test_the_observation_is_json_shaped():
    """Evidence has to survive being logged, persisted, or replayed —
    §9.2's rule, and the reason `observation` is a plain dict."""
    json.dumps(observe('{"a": 1}'))


def test_the_provider_is_never_asked_whether_it_did_well():
    """The coupling ADR-0011 exists to prevent, stated for a medium it did
    not originally have in mind: every field is derived from the text, and
    none of them is a claim by whoever produced it."""
    observation = observe("some answer")

    for suspicious in ("success", "ok", "finish_reason", "confidence", "score"):
        assert suspicious not in observation


# =========================================================================
# The Verifier itself
# =========================================================================


def test_it_is_a_real_verifier():
    assert isinstance(TextVerifier("x"), Verifier)


def test_it_names_what_it_observed():
    verifier = TextVerifier("x")

    assert verifier.worker_name == VERIFIER_NAME
    assert verifier.environment_name == ENVIRONMENT


def test_the_worker_name_can_say_which_provider_answered():
    assert TextVerifier("x", worker="ollama.local").worker_name == "ollama.local"


def test_the_observation_is_recomputed_on_every_verify():
    """Never a stored verdict: a judgement is always derived from the text
    in hand, which is the "re-observe fresh" rule for a medium where the
    answer *is* the artefact."""
    verifier = TextVerifier("blue")

    first = verifier.capture_observation_dict()
    second = verifier.capture_observation_dict()

    assert first == second
    assert first is not second


def test_verifying_produces_evidence_not_a_bare_verdict():
    evidence = verify_text("blue", expect(contains_all=["blue"]))

    assert isinstance(evidence, Evidence)
    assert evidence.evidence_id
    assert evidence.observation["text"] == "blue"


def test_the_evidence_carries_what_each_check_actually_saw():
    """So "why did that fail?" is answerable from the record."""
    evidence = verify_text("red", expect(contains_all=["blue"]))
    failed = [r for r in evidence.check_results if not r.passed]

    assert failed
    assert failed[0].check.description == "mentions 'blue'"


def test_the_evidence_carries_what_was_asked_for():
    evidence = verify_text("blue", expect(description="a colour"))

    assert evidence.expected.description == "a colour"


def test_an_answer_meeting_every_check_matches():
    assert verify_text("blue", expect(contains_all=["blue"])).verdict is Verdict.MATCHED


def test_an_answer_meeting_none_does_not_match():
    evidence = verify_text("", ExpectedOutcome("x", [contains("blue")]))

    assert evidence.verdict is Verdict.NOT_MATCHED


def test_an_answer_meeting_some_is_only_partially_matched():
    evidence = verify_text("blue", expect(contains_all=["blue", "sky"]))

    assert evidence.verdict is Verdict.PARTIALLY_MATCHED


def test_an_expectation_with_no_checks_is_an_error_never_a_pass():
    """ADR-0011's rule, inherited rather than reimplemented: an empty
    checks list must not default to MATCHED."""
    evidence = verify_text("anything", ExpectedOutcome("nothing asked", []))

    assert evidence.verdict is Verdict.ERROR


def test_only_a_full_match_counts_as_verified():
    """`PARTIALLY_MATCHED` is deliberately not enough: half of what was
    asked for is not what was asked for, and a cache that remembered it
    would serve the same half answer forever."""
    assert passed(verify_text("blue", expect(contains_all=["blue"]))) is True
    assert passed(verify_text("blue", expect(contains_all=["blue", "sky"]))) is False
    assert passed(verify_text("red", expect(contains_all=["blue"]))) is False
    assert passed(None) is False


def test_the_same_text_and_expectation_always_give_the_same_verdict():
    expectation = expect(contains_all=["blue"], min_words=1)

    verdicts = {verify_text("the sky is blue", expectation).verdict for _ in range(5)}

    assert verdicts == {Verdict.MATCHED}


# =========================================================================
# The check builders — sugar over the five frozen operators
# =========================================================================


def test_every_builder_produces_the_frozen_shape():
    for check in (
        not_empty(),
        contains("x"),
        excludes("x"),
        matches("x"),
        is_json(),
        json_has("a"),
        json_equals("a", 1),
        at_least_words(3),
    ):
        assert isinstance(check, ObservationCheck)
        assert check.description


@pytest.mark.parametrize(
    "check",
    [
        not_empty(),
        contains("x"),
        excludes("x"),
        matches("x"),
        is_json(),
        json_has("a"),
        json_equals("a", 1),
        at_least_words(3),
    ],
)
def test_no_builder_invents_a_sixth_operator(check):
    """A new operator would mean editing a frozen file to save writing a
    regex."""
    assert check.operator in {
        "equals",
        "contains",
        "not_contains",
        "exists",
        "matches_regex",
    }


def test_not_empty_rejects_a_blank_answer():
    assert verify_text("   ", ExpectedOutcome("x", [not_empty()])).verdict is (
        Verdict.NOT_MATCHED
    )


@pytest.mark.parametrize("answer", ["Blue.", "BLUE", "  blue  ", "the sky is Blue"])
def test_contains_ignores_case_and_spacing(answer):
    """A model that answers "Blue." when asked for "blue" has answered."""
    assert verify_text(answer, expect(contains_all=["blue"])).verdict is Verdict.MATCHED


def test_contains_matches_a_multi_word_phrase_across_line_breaks():
    evidence = verify_text("the sky\nis blue", expect(contains_all=["sky is blue"]))

    assert evidence.verdict is Verdict.MATCHED


def test_excludes_fails_when_the_phrase_is_present():
    evidence = verify_text("I cannot help", expect(excludes_all=["cannot help"]))

    assert evidence.verdict is Verdict.PARTIALLY_MATCHED


def test_excludes_passes_when_it_is_absent():
    assert verify_text("here you go", expect(excludes_all=["cannot"])).verdict is (
        Verdict.MATCHED
    )


def test_matches_applies_a_regex_to_the_raw_text():
    assert verify_text("Total: 42", expect(pattern=r"\d+")).verdict is Verdict.MATCHED
    assert verify_text("Total: none", expect(pattern=r"\d+")).verdict is (
        Verdict.PARTIALLY_MATCHED
    )


def test_a_regex_sees_the_original_casing():
    """`matches` deliberately reads `text`, not `normalised` — a caller
    writing a case-sensitive pattern means it."""
    assert verify_text("ABC", expect(pattern=r"[A-Z]{3}")).verdict is Verdict.MATCHED


def test_json_body_requires_parseable_json():
    assert verify_text('{"a": 1}', expect(json_body=True)).verdict is Verdict.MATCHED
    assert verify_text("not json", expect(json_body=True)).verdict is (
        Verdict.PARTIALLY_MATCHED
    )


def test_a_json_field_can_be_required():
    assert verify_text('{"name": "Ved"}', expect(json_fields=["name"])).verdict is (
        Verdict.MATCHED
    )


def test_a_missing_json_field_fails():
    evidence = verify_text('{"other": 1}', expect(json_fields=["name"]))

    assert evidence.verdict is Verdict.PARTIALLY_MATCHED


def test_a_nested_json_field_can_be_required():
    """`get_field` already walks dicts and lists, so no new machinery."""
    evidence = verify_text(
        '{"items": [{"name": "a"}]}',
        ExpectedOutcome("x", [json_has("items.0.name")]),
    )

    assert evidence.verdict is Verdict.MATCHED


def test_a_json_field_can_be_required_to_equal_something():
    matched = verify_text('{"ok": true}', ExpectedOutcome("x", [json_equals("ok", True)]))
    missed = verify_text('{"ok": false}', ExpectedOutcome("x", [json_equals("ok", True)]))

    assert matched.verdict is Verdict.MATCHED
    assert missed.verdict is Verdict.NOT_MATCHED


def test_a_json_check_against_prose_fails_honestly():
    """Rather than matching nothing in particular."""
    evidence = verify_text("just words", ExpectedOutcome("x", [json_has("name")]))

    assert evidence.verdict is Verdict.NOT_MATCHED


@pytest.mark.parametrize(
    ("text", "required", "expected"),
    [
        ("one two three", 3, Verdict.MATCHED),
        ("one two three", 2, Verdict.MATCHED),
        ("one two", 3, Verdict.NOT_MATCHED),
        ("", 1, Verdict.NOT_MATCHED),
        ("   ", 1, Verdict.NOT_MATCHED),
        ("one", 1, Verdict.MATCHED),
        ("one", 0, Verdict.MATCHED),
        ("", 0, Verdict.NOT_MATCHED),
    ],
)
def test_a_minimum_word_count_can_be_required(text, required, expected):
    assert verify_text(text, ExpectedOutcome("x", [at_least_words(required)])).verdict is (
        expected
    )


def test_asking_for_no_minimum_words_adds_no_check():
    assert len(expect(min_words=0).checks) == 1  # just not_empty


def test_a_word_count_check_never_passes_on_a_blank_answer():
    """The first version's regex ended in `\\S*`, which matches the empty
    string — so "at least 1 word" passed on nothing at all."""
    for count in (1, 2, 5):
        evidence = verify_text("", ExpectedOutcome("x", [at_least_words(count)]))
        assert evidence.verdict is Verdict.NOT_MATCHED, count


# ---- the expectation builder ---------------------------------------------


def test_an_expectation_requires_a_non_empty_answer_by_default():
    assert expect().checks == [not_empty()]


def test_the_non_empty_requirement_can_be_dropped():
    assert expect(require_non_empty=False).checks == []


def test_an_expectation_with_nothing_asked_stays_empty_so_the_evaluator_errors():
    """Reproducing ADR-0011's "no checks means ERROR" rule here would be a
    second opinion about it."""
    assert expect(require_non_empty=False).checks == []
    assert verify_text("x", expect(require_non_empty=False)).verdict is Verdict.ERROR


def test_an_expectation_carries_its_description():
    assert expect(description="a colour name").description == "a colour name"


def test_every_requested_check_appears_once():
    expectation = expect(
        contains_all=["a", "b"],
        excludes_all=["c"],
        pattern=r"\d",
        json_body=True,
        json_fields=["x", "y"],
        min_words=5,
    )

    assert len(expectation.checks) == 1 + 2 + 1 + 1 + 1 + 2 + 1


def test_the_builder_is_deterministic():
    assert expect(contains_all=["a", "b"]).checks == expect(contains_all=["a", "b"]).checks


# =========================================================================
# Architecture purity
# =========================================================================


def _imported(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


@pytest.mark.parametrize(
    "forbidden",
    ["openai", "anthropic", "httpx", "requests", "urllib", "socket", "subprocess"],
)
def test_the_verifier_cannot_call_anything(forbidden):
    """**No model judges another model.** Asking an LLM whether an LLM's
    answer was good needs an LLM to judge *that*, and something has to
    break the recursion (ADR-0017, MB034)."""
    for name in _imported(MODULE_PATH):
        assert not name.startswith(forbidden), name


def test_the_verifier_reaches_no_provider_and_no_broker():
    for name in _imported(MODULE_PATH):
        assert not name.startswith("master_agent.providers")
        assert not name.startswith("master_agent.broker")


def test_the_verifier_uses_the_frozen_contracts_rather_than_new_ones():
    internal = {n for n in _imported(MODULE_PATH) if n.startswith("master_agent")}

    assert internal <= {
        "master_agent.verification.evidence",
        "master_agent.verification.verifier",
    }


def test_nothing_was_added_to_the_frozen_verification_package():
    """`verification/` has been frozen since MB025. MB035 implements
    against it from outside, which is what a Worker's Verifier is supposed
    to do anyway."""
    package = MODULE_PATH.parents[1] / "verification"

    assert sorted(p.name for p in package.glob("*.py")) == [
        "__init__.py",
        "audit.py",
        "evaluator.py",
        "evidence.py",
        "verifier.py",
    ]


@pytest.mark.parametrize("forbidden", ["score", "rate", "grade", "judge", "guess"])
def test_the_verifier_defines_no_opinion_forming_function(forbidden):
    """A verdict is arithmetic over an expectation stated in advance, not
    an assessment formed after the fact."""
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            assert forbidden not in node.name.lower(), node.name


def test_the_module_names_no_vendor():
    text = MODULE_PATH.read_text(encoding="utf-8").lower()

    for vendor in ("openai", "gemini", "gpt-", "claude", "mistral", "qwen"):
        assert vendor not in text


def test_the_module_says_which_brief_it_serves():
    head = " ".join(MODULE_PATH.read_text(encoding="utf-8")[:600].split())

    assert "Mission Brief 035" in head


def test_the_module_states_the_interpretation_it_had_to_make():
    """The one place ADR-0011's "re-observe fresh" rule needed reading for
    a new medium. A future reader must find the reasoning, not infer it."""
    assert "the answer is the artefact" in (module.__doc__ or "")
