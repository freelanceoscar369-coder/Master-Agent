"""The seam that lets produced text become a bound value.

`Reasoning.Transform` produces text; `Filesystem.WriteFile` wants it:

    Reasoning.Transform.text  ->  Filesystem.WriteFile.content

`runtime/input_resolution.py` resolves that only from a source carrying
canonical Evidence whose verdict is `matched` and whose *observation*
holds the field. Registered through the generic `PluginGateway` — whose
`verify()` returns `None` by contract — Reasoning executed correctly,
produced real text, and every binding out of it failed. Nothing was
broken; the Executive that produces text and the Verifier that measures
text were simply never joined.

These tests pin the join and, just as importantly, pin where it refuses.
"""
from __future__ import annotations

import pytest

from master_agent.plugins.reasoning_gateway import ReasoningGateway
from master_agent.planner.outcomes import SuccessSpec
from master_agent.verification.evidence import Verdict


class FakePluginResult:
    def __init__(self, success, output=None, error=""):
        self.success = success
        self.output = output
        self.error = error


class FakeReasoningPlugin:
    """Returns whatever it is told to, and records what it was asked."""

    def __init__(self, result):
        self._result = result
        self.calls = []

    def invoke(self, capability, payload):
        self.calls.append((capability, dict(payload)))
        return self._result


def expectation(description="Text is produced", **kwargs):
    return SuccessSpec(description=description, **kwargs).to_expected_outcome()


PAYLOAD = {"instruction": "Think of three short names for a gardening notes app"}


class TestTheProducedTextBecomesEvidence:
    def test_verify_returns_canonical_evidence_for_the_text_just_produced(self):
        plugin = FakeReasoningPlugin(
            FakePluginResult(True, {"text": "Sprout, Flora, Bud"})
        )
        gateway = ReasoningGateway(plugin)

        result = gateway.invoke("transform", PAYLOAD)
        assert result.success

        evidence = gateway.verify("transform", PAYLOAD, expectation(min_words=1))

        assert evidence is not None
        assert evidence.verdict is Verdict.MATCHED
        # The field `Filesystem.WriteFile.content` binds to.
        assert evidence.observation["text"] == "Sprout, Flora, Bud"

    def test_the_observation_is_measured_not_claimed(self):
        """`TextVerifier` re-derives its observation from the artefact.
        The plugin is never asked whether it thinks it did well — that
        coupling is what ADR-0011 exists to prevent."""
        plugin = FakeReasoningPlugin(
            FakePluginResult(True, {"text": "one two three", "self_rating": "excellent"})
        )
        gateway = ReasoningGateway(plugin)
        gateway.invoke("transform", PAYLOAD)

        evidence = gateway.verify("transform", PAYLOAD, expectation(min_words=1))

        assert evidence.observation["word_count"] == 3
        assert "self_rating" not in evidence.observation

    def test_an_answer_that_misses_the_expectation_does_not_match(self):
        """The verdict is arithmetic over an expectation stated before the
        step ran — which is the only kind of verdict that can fail. An
        unmatched verdict is what stops the binding downstream."""
        plugin = FakeReasoningPlugin(FakePluginResult(True, {"text": "short"}))
        gateway = ReasoningGateway(plugin)
        gateway.invoke("transform", PAYLOAD)

        evidence = gateway.verify(
            "transform", PAYLOAD, expectation(must_contain=["gardening"])
        )

        assert evidence is not None
        assert evidence.verdict is not Verdict.MATCHED


class TestItFailsClosed:
    """No Evidence is the truthful answer whenever the artefact under test
    cannot be identified with certainty. Evidence about some *other*
    answer would not be, and a binding is about to trust this."""

    def test_no_evidence_when_the_capability_produced_no_text(self):
        plugin = FakeReasoningPlugin(FakePluginResult(True, {"pages": 3}))
        gateway = ReasoningGateway(plugin)
        gateway.invoke("transform", PAYLOAD)

        assert gateway.verify("transform", PAYLOAD, expectation()) is None

    def test_no_evidence_when_the_invocation_failed(self):
        plugin = FakeReasoningPlugin(FakePluginResult(False, None, "no provider"))
        gateway = ReasoningGateway(plugin)

        result = gateway.invoke("transform", PAYLOAD)

        assert result.success is False
        assert gateway.verify("transform", PAYLOAD, expectation()) is None

    def test_no_evidence_before_anything_has_been_invoked(self):
        gateway = ReasoningGateway(FakeReasoningPlugin(FakePluginResult(True, {"text": "x"})))

        assert gateway.verify("transform", PAYLOAD, expectation()) is None

    def test_no_evidence_for_a_verify_that_belongs_to_a_different_call(self):
        """The Runtime hands `verify()` the *payload*, not the artefact.
        If that payload is not the one the held text came from, this is
        being asked about a different question and must not answer."""
        plugin = FakeReasoningPlugin(FakePluginResult(True, {"text": "Sprout, Flora, Bud"}))
        gateway = ReasoningGateway(plugin)
        gateway.invoke("transform", PAYLOAD)

        other = {"instruction": "Summarise the quarterly report"}
        assert gateway.verify("transform", other, expectation()) is None

    def test_a_second_invocation_replaces_the_first_artefact(self):
        """Stale text must never outlive the call that produced it."""
        plugin = FakeReasoningPlugin(FakePluginResult(True, {"text": "first"}))
        gateway = ReasoningGateway(plugin)
        gateway.invoke("transform", PAYLOAD)

        plugin._result = FakePluginResult(True, {"pages": 1})  # produces no text
        gateway.invoke("transform", PAYLOAD)

        assert gateway.verify("transform", PAYLOAD, expectation()) is None


class TestExecutionIsUnchanged:
    def test_the_payload_reaches_the_plugin_verbatim(self):
        plugin = FakeReasoningPlugin(FakePluginResult(True, {"text": "ok"}))
        ReasoningGateway(plugin).invoke("transform", PAYLOAD)

        assert plugin.calls == [("transform", PAYLOAD)]

    def test_permission_is_relayed_before_the_call(self):
        """The ADR-0005 relay pattern the generic gateway already uses."""
        granted = []
        plugin = FakeReasoningPlugin(FakePluginResult(True, {"text": "ok"}))
        gateway = ReasoningGateway(plugin, grant_permission=granted.append)

        gateway.invoke("transform", PAYLOAD)

        assert granted == ["transform"]
