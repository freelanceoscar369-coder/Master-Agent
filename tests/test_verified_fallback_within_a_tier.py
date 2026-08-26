"""A provider that answers badly must not end the attempt.

`run()` already knew that a result carrying a failed expectation is not an
answer. `_attempt_tier()` stopped on `ok` alone. The two disagreed, and
the disagreement was invisible while every tier held one locality: an
unverified outcome returned to `run()`, which moved to the next tier, and
the next tier had different providers in it.

An interactive turn has ONE tier holding every configured provider. There
is no next tier -- so a provider that executed fine while failing the
expectation ended the whole attempt with untried candidates sitting beside
it. Measured live: a forced fallback reached a desktop provider, which
returned `ok=True` and one line against a three-line expectation, and the
run stopped there.

The two loops now read one predicate, so "acceptable" cannot mean two
things in one module.
"""
from __future__ import annotations

import dataclasses

from master_agent.ai_infrastructure.tiered_runner import TIER_ANY, TieredPromptRunner
from master_agent.ai_infrastructure.workload import INTERACTIVE


@dataclasses.dataclass(frozen=True)
class Request:
    request_class: str = INTERACTIVE
    exclude_providers: frozenset = frozenset()


@dataclasses.dataclass(frozen=True)
class Outcome:
    """The three fields the acceptance rule reads.

    `evidence is None` means nothing was asked, which is exactly what
    `PromptOutcome` documents -- so an unchecked request keeps its old
    behaviour without a special case.
    """

    provider_id: str
    ok: bool
    evidence: object = None
    verified: bool = False
    text: str = ""


class ScriptedExecutor:
    """Answers as whichever provider the Broker would have ranked first
    among those still allowed, using a fixed preference order."""

    def __init__(self, order, outcomes):
        self._order = list(order)
        self._outcomes = dict(outcomes)
        self.asked: list[str] = []

    def run(self, prompt, request, **kwargs):
        excluded = set(getattr(request, "exclude_providers", ()) or ())
        for provider_id in self._order:
            if provider_id in excluded:
                continue
            self.asked.append(provider_id)
            return self._outcomes[provider_id]
        return Outcome(provider_id="", ok=False)


CONFIGURED = ("fast.api", "second.desktop", "third.desktop")
KNOWN_ONLY = ("unconfigured.local", "unconfigured.api")


def runner(executor):
    return TieredPromptRunner(
        prompt_executor=executor,
        gemini_provider_ids=frozenset({"fast.api"}),
        desktop_provider_ids=frozenset({"second.desktop", "third.desktop"}),
        browser_provider_ids=frozenset(),
        local_provider_ids=frozenset(),
        all_known_provider_ids=frozenset(CONFIGURED) | frozenset(KNOWN_ONLY),
    )


def verified(pid):
    return Outcome(pid, ok=True, evidence={"id": pid}, verified=True, text="three names")


def unverified(pid):
    return Outcome(pid, ok=True, evidence={"id": pid}, verified=False, text="one name")


def crashed(pid):
    return Outcome(pid, ok=False)


def unchecked(pid):
    return Outcome(pid, ok=True, evidence=None, verified=False, text="anything")


class TestOneAcceptanceRule:

    def test_A_a_verified_first_answer_stops_immediately(self):
        executor = ScriptedExecutor(CONFIGURED, {
            "fast.api": verified("fast.api"),
            "second.desktop": verified("second.desktop"),
            "third.desktop": verified("third.desktop"),
        })

        outcome = runner(executor).run("p", Request())

        assert outcome.provider_id == "fast.api"
        assert executor.asked == ["fast.api"], "a settled answer was not enough"

    def test_B_an_unverified_answer_yields_to_the_next_candidate(self):
        """The live case: executed fine, failed the expectation, and the
        remaining candidates sat untried inside the same tier."""
        executor = ScriptedExecutor(CONFIGURED, {
            "fast.api": unverified("fast.api"),
            "second.desktop": verified("second.desktop"),
            "third.desktop": verified("third.desktop"),
        })

        outcome = runner(executor).run("p", Request())

        assert outcome.provider_id == "second.desktop"
        assert executor.asked == ["fast.api", "second.desktop"]

    def test_C_execution_failure_then_unverified_then_verified(self):
        executor = ScriptedExecutor(CONFIGURED, {
            "fast.api": crashed("fast.api"),
            "second.desktop": unverified("second.desktop"),
            "third.desktop": verified("third.desktop"),
        })

        outcome = runner(executor).run("p", Request())

        assert outcome.provider_id == "third.desktop"
        assert executor.asked == ["fast.api", "second.desktop", "third.desktop"]
        assert len(executor.asked) == len(set(executor.asked)), "a provider was retried"

    def test_D_an_unchecked_request_is_still_answered_by_the_first_provider(self):
        """Nothing was asked, so nothing failed. This must not start
        walking candidates looking for a verification nobody wanted."""
        executor = ScriptedExecutor(CONFIGURED, {
            "fast.api": unchecked("fast.api"),
            "second.desktop": verified("second.desktop"),
            "third.desktop": verified("third.desktop"),
        })

        outcome = runner(executor).run("p", Request())

        assert outcome.provider_id == "fast.api"
        assert executor.asked == ["fast.api"]

    def test_E_every_candidate_unverified_exhausts_boundedly(self):
        executor = ScriptedExecutor(CONFIGURED, {
            "fast.api": unverified("fast.api"),
            "second.desktop": crashed("second.desktop"),
            "third.desktop": unverified("third.desktop"),
        })

        outcome = runner(executor).run("p", Request())

        assert executor.asked == list(CONFIGURED)
        assert len(executor.asked) == len(set(executor.asked)), "a provider was retried"
        # The founder still gets the last thing that happened, truthfully
        # unverified, rather than silence.
        assert outcome is not None
        assert outcome.verified is False

    def test_F_known_but_unconfigured_providers_are_never_asked(self):
        executor = ScriptedExecutor(
            tuple(KNOWN_ONLY) + CONFIGURED,
            {pid: unverified(pid) for pid in KNOWN_ONLY + CONFIGURED},
        )

        runner(executor).run("p", Request())

        for known_only in KNOWN_ONLY:
            assert known_only not in executor.asked

    def test_the_whole_candidate_set_is_one_interactive_attempt(self):
        executor = ScriptedExecutor(CONFIGURED, {p: verified(p) for p in CONFIGURED})
        attempts = runner(executor)._ordered_attempts(Request())

        assert len(attempts) == 1
        assert attempts[0][0] == TIER_ANY
        assert set(attempts[0][1]) == set(CONFIGURED)
