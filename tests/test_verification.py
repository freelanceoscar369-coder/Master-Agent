"""Verification unit tests -- exercises the generic verification/ package
directly, with no Browser Worker, no Playwright, no Environment involved
at all. This is deliberately the point: this package must work for any
future Worker, not just Browser's. See BROWSER_WORKER_ARCHITECTURE.md §8.
"""
from __future__ import annotations

from typing import Any

from master_agent.verification.evaluator import evaluate_check, evaluate_checks, get_field
from master_agent.verification.evidence import ExpectedOutcome, ObservationCheck, Verdict
from master_agent.verification.verifier import Verifier


class FakeVerifier(Verifier):
    """A minimal, non-browser Verifier -- proves the base class's shared
    logic (building Evidence, computing a Verdict) works for any Worker
    that can produce a dict observation, not just Browser's."""

    worker_name = "fake"
    environment_name = "fake_environment"

    def __init__(self, observation: dict[str, Any] | None = None, raise_error: bool = False) -> None:
        self._observation = observation or {}
        self._raise_error = raise_error

    def capture_observation_dict(self) -> dict[str, Any]:
        if self._raise_error:
            raise RuntimeError("could not observe")
        return self._observation


def test_get_field_top_level():
    assert get_field({"url": "about:blank"}, "url") == (True, "about:blank")


def test_get_field_missing_key():
    assert get_field({"url": "about:blank"}, "title") == (False, None)


def test_get_field_dotted_list_index():
    obs = {"elements": [{"text": "Hello"}, {"text": "World"}]}
    assert get_field(obs, "elements.0.text") == (True, "Hello")
    assert get_field(obs, "elements.1.text") == (True, "World")


def test_get_field_out_of_range_index():
    obs = {"elements": [{"text": "Hello"}]}
    assert get_field(obs, "elements.5.text") == (False, None)


def test_evaluate_check_equals_pass_and_fail():
    check = ObservationCheck(field="title", operator="equals", value="Sample")
    assert evaluate_check({"title": "Sample"}, check).passed is True
    assert evaluate_check({"title": "Other"}, check).passed is False


def test_evaluate_check_contains():
    check = ObservationCheck(field="title", operator="contains", value="amp")
    assert evaluate_check({"title": "Sample"}, check).passed is True


def test_evaluate_check_not_contains():
    check = ObservationCheck(field="title", operator="not_contains", value="zzz")
    assert evaluate_check({"title": "Sample"}, check).passed is True


def test_evaluate_check_matches_regex():
    check = ObservationCheck(field="url", operator="matches_regex", value=r"^about:")
    assert evaluate_check({"url": "about:blank"}, check).passed is True
    assert evaluate_check({"url": "data:text/html"}, check).passed is False


def test_evaluate_check_exists():
    check = ObservationCheck(field="title", operator="exists")
    assert evaluate_check({"title": "Sample"}, check).passed is True
    assert evaluate_check({}, check).passed is False


def test_evaluate_check_missing_field_is_a_clean_failure_not_an_exception():
    check = ObservationCheck(field="nope", operator="equals", value="x")
    result = evaluate_check({}, check)
    assert result.passed is False
    assert result.error is not None


def test_evaluate_check_unknown_operator_is_reported_not_raised():
    check = ObservationCheck(field="title", operator="unknown_operator", value="x")
    result = evaluate_check({"title": "Sample"}, check)
    assert result.passed is False
    assert "unknown operator" in result.error


def test_evaluate_checks_all_pass_is_matched():
    checks = [
        ObservationCheck(field="title", operator="equals", value="Sample"),
        ObservationCheck(field="url", operator="exists"),
    ]
    verdict, results = evaluate_checks({"title": "Sample", "url": "about:blank"}, checks)
    assert verdict == Verdict.MATCHED
    assert len(results) == 2


def test_evaluate_checks_none_pass_is_not_matched():
    checks = [ObservationCheck(field="title", operator="equals", value="Wrong")]
    verdict, _ = evaluate_checks({"title": "Sample"}, checks)
    assert verdict == Verdict.NOT_MATCHED


def test_evaluate_checks_some_pass_is_partially_matched():
    checks = [
        ObservationCheck(field="title", operator="equals", value="Sample"),
        ObservationCheck(field="title", operator="equals", value="Wrong"),
    ]
    verdict, _ = evaluate_checks({"title": "Sample"}, checks)
    assert verdict == Verdict.PARTIALLY_MATCHED


def test_evaluate_checks_empty_list_is_error_not_a_silent_pass():
    """An ExpectedOutcome with no checks can never be verified -- this must
    never default to MATCHED, per KALPAVRIKSHA_VISION_V2.md §10.2's 'do not
    allow execution success to imply mission success'."""
    verdict, results = evaluate_checks({"title": "Sample"}, [])
    assert verdict == Verdict.ERROR
    assert results == []


def test_verifier_verify_produces_matched_evidence():
    verifier = FakeVerifier({"value": 42})
    expected = ExpectedOutcome(
        description="value is 42", checks=[ObservationCheck(field="value", operator="equals", value=42)]
    )
    evidence = verifier.verify(expected)
    assert evidence.verdict == Verdict.MATCHED
    assert evidence.worker == "fake"
    assert evidence.environment == "fake_environment"
    assert evidence.observation == {"value": 42}
    assert evidence.expected is expected
    assert evidence.evidence_id  # non-empty


def test_verifier_verify_never_reads_an_execution_result():
    """Structural guarantee: Verifier.verify()'s signature takes only an
    ExpectedOutcome -- there is no ExecutionResult parameter anywhere on
    this contract, so a caller cannot even accidentally pass one in and
    have it influence the Verdict (ADR-0011)."""
    import inspect

    signature = inspect.signature(Verifier.verify)
    assert list(signature.parameters) == ["self", "expected"]


def test_verifier_verify_handles_observation_failure_as_error_evidence():
    verifier = FakeVerifier(raise_error=True)
    expected = ExpectedOutcome(description="anything", checks=[ObservationCheck(field="x", operator="exists")])
    evidence = verifier.verify(expected)
    assert evidence.verdict == Verdict.ERROR
    assert evidence.observation == {}
    assert evidence.errors
    assert "could not observe" in evidence.errors[0]


def test_evidence_and_expected_outcome_are_plain_serializable_shapes():
    """Evidence.observation must always be a plain dict -- never a live
    object from whatever Environment produced it (KALPAVRIKSHA_VISION_V2.md
    §9.2). This is what lets Evidence be logged, persisted, or handed to a
    future Knowledge Candidate nomination regardless of which Worker
    produced it."""
    verifier = FakeVerifier({"a": 1, "b": [1, 2, 3]})
    evidence = verifier.verify(ExpectedOutcome(description="d", checks=[ObservationCheck(field="a", operator="exists")]))
    assert isinstance(evidence.observation, dict)
    import json

    json.dumps(evidence.observation)  # must not raise -- proves it's JSON-plain
