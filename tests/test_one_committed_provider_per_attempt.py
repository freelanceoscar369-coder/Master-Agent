"""One question must not be put to four applications.

Measured live 2026-09-05, on the first model-backed mission: a single
Brain sub-call (`brain_founder_obligations`) walked

    chatgpt-desktop     timed_out    137s
    perplexity-desktop  unavailable   31s
    kimi-desktop        timed_out    129s
    trusted-founder-web timed_out    322s

Four of the founder's applications driven for one question, because each
was invoked, failed, and the attempt loop quietly asked the Broker for
the next one.

Unreachable and unhelpful are different facts. A provider that could not
be REACHED was never asked, so asking someone else is still one question.
A provider that WAS asked and failed is a method failure, and ADR-0027
gives that to the Brain to adjudicate -- retry, another resource, another
method, clarification, or an honest stop. It does not give it to a loop.
"""
from __future__ import annotations

import dataclasses

from master_agent.ai_infrastructure.tiered_runner import TieredPromptRunner
from master_agent.providers.response import (
    MALFORMED,
    REJECTED,
    SUCCEEDED,
    TIMED_OUT,
    UNAVAILABLE,
)


class _Outcome:
    def __init__(self, provider_id, outcome, text="an answer"):
        self.provider_id = provider_id
        self.outcome = outcome
        self.ok = outcome == SUCCEEDED
        self.text = text if outcome == SUCCEEDED else ""


class _Executor:
    """Answers with a scripted outcome per provider, in Broker order."""

    def __init__(self, script):
        self._script = list(script)
        self.invoked: list[str] = []

    def run(self, prompt, request, **kwargs):
        excluded = frozenset(getattr(request, "exclude_providers", ()) or ())
        for provider_id, outcome in self._script:
            if provider_id in excluded:
                continue
            self.invoked.append(provider_id)
            return _Outcome(provider_id, outcome)
        return _Outcome(None, UNAVAILABLE)


@dataclasses.dataclass
class _Request:
    #: `_scope()` rebuilds the request with `dataclasses.replace`, so the
    #: double has to be one too.
    exclude_providers: frozenset = frozenset()
    request_class: str = "interactive"


def _runner(executor):
    ids = frozenset({"chatgpt-desktop", "perplexity-desktop", "kimi-desktop"})
    return TieredPromptRunner(
        executor,
        gemini_provider_ids=frozenset(),
        desktop_provider_ids=ids,
        browser_provider_ids=frozenset(),
        all_known_provider_ids=ids,
    )


class TestOneCommittedProviderPerAttempt:

    def test_a_timeout_does_not_silently_invoke_the_next_provider(self):
        """The live defect. ChatGPT was asked and timed out; Perplexity
        must not then be driven for the same question."""
        executor = _Executor([
            ("chatgpt-desktop", TIMED_OUT),
            ("perplexity-desktop", SUCCEEDED),
        ])
        _runner(executor).run("q", _Request())

        assert executor.invoked == ["chatgpt-desktop"], (
            "a provider that was asked and failed handed the question on"
        )

    def test_a_rejection_does_not_invoke_the_next_provider(self):
        executor = _Executor([
            ("chatgpt-desktop", REJECTED),
            ("kimi-desktop", SUCCEEDED),
        ])
        _runner(executor).run("q", _Request())
        assert executor.invoked == ["chatgpt-desktop"]

    def test_a_malformed_answer_does_not_invoke_the_next_provider(self):
        """It answered. A bad answer is the Brain's to judge."""
        executor = _Executor([
            ("chatgpt-desktop", MALFORMED),
            ("kimi-desktop", SUCCEEDED),
        ])
        _runner(executor).run("q", _Request())
        assert executor.invoked == ["chatgpt-desktop"]

    def test_an_unreachable_provider_may_be_replaced_before_any_send(self):
        """Never asked is not asked-and-failed. Nothing was spent and no
        application was driven, so selecting another is still one
        question -- which is what keeps a closed or broken provider from
        stopping the mission."""
        executor = _Executor([
            ("chatgpt-desktop", UNAVAILABLE),
            ("kimi-desktop", SUCCEEDED),
        ])
        outcome = _runner(executor).run("q", _Request())

        assert executor.invoked == ["chatgpt-desktop", "kimi-desktop"]
        assert outcome.outcome == SUCCEEDED

    def test_the_failure_is_returned_rather_than_swallowed(self):
        """Brain adjudicates a method failure, so it has to receive it."""
        executor = _Executor([("chatgpt-desktop", TIMED_OUT)])
        outcome = _runner(executor).run("q", _Request())

        assert outcome.outcome == TIMED_OUT
        assert outcome.provider_id == "chatgpt-desktop"

    def test_a_working_provider_is_still_used_once(self):
        executor = _Executor([("chatgpt-desktop", SUCCEEDED)])
        outcome = _runner(executor).run("q", _Request())

        assert executor.invoked == ["chatgpt-desktop"]
        assert outcome.ok is True
