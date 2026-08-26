"""A simple turn is decided on how long the founder waits.

Measured before this existed, on a trivial public generation:

    desktop providers, serially   ~74s
    healthy free Gemini            ~5.4s
    overall                       ~90s

`tiered_runner` walked local -> desktop -> gemini -> browser and scoped
the Broker to one locality at a time, so an adequate fast provider could
not win until every slower one had been exhausted. Locality ordering is a
cost-and-privacy answer; for a founder waiting on three words it is the
wrong question answered well.

The correction is entirely in the owners: `broker/policy.py` gained a
named, versioned `fast_free` policy and the mapping from workload class to
policy, and `tiered_runner` stopped pre-deciding by locality for an
interactive turn. No provider is named anywhere in either.
"""
from __future__ import annotations

import dataclasses

from master_agent.ai_infrastructure.workload import EXECUTION, INTERACTIVE
from master_agent.broker.broker import CapabilityBroker
from master_agent.broker.policy import (
    FAST_FREE,
    PREFER_FREE,
    get_policy,
    policy_for_request_class,
)
from master_agent.broker.profiles import CLOUD, DESKTOP, ProviderProfile, TaskProfile


def provider(pid, *, quality, latency, cost=0.0, locality=CLOUD,
             privacy="third_party", available=True):
    return ProviderProfile(
        provider_id=pid, capabilities=frozenset({"reasoning"}), locality=locality,
        privacy=privacy, quality=quality, cost=cost, latency_ms=latency,
        available=available, requires_network=locality != "local",
    )


def decide(providers, policy, **task_kwargs):
    task = TaskProfile(capability="reasoning", task_id="t-1", **task_kwargs)
    return CapabilityBroker(policy=policy).select(task, list(providers))


class TestTheFastPathChoosesOnLatency:

    def test_A_an_adequate_fast_free_provider_beats_an_adequate_slow_one(self):
        """Both free, both clearing the floor. The founder is waiting."""
        fast = provider("fast.api", quality=0.88, latency=2_000)
        slow = provider("slow.desktop", quality=0.90, latency=3_000, locality=DESKTOP)

        assert decide([slow, fast], FAST_FREE).winner == "fast.api"

    def test_B_an_inadequate_fast_provider_loses_to_a_slower_adequate_one(self):
        """Speed never buys its way under the quality floor."""
        quick_but_poor = provider("quick.api", quality=0.30, latency=200)
        slower_adequate = provider("good.desktop", quality=0.85, latency=3_000,
                                   locality=DESKTOP)

        assert decide([quick_but_poor, slower_adequate], FAST_FREE).winner == (
            "good.desktop"
        )

    def test_C_sensitive_work_still_obeys_the_privacy_constraint(self):
        """`fast_free` keeps require_private_for_sensitive, so a fast
        third-party provider must not win a sensitive request."""
        fast_third_party = provider("fast.api", quality=0.9, latency=500)
        private_slow = provider("local.runtime", quality=0.75, latency=9_000,
                                locality="local", privacy="private")

        decision = decide([fast_third_party, private_slow], FAST_FREE,
                          sensitivity="sensitive")

        assert decision.winner == "local.runtime"

    def test_D_a_paid_provider_does_not_win_the_free_fast_path(self):
        """`cost == 0` currently conflates a free API, an installed
        subscription and a local runtime. Until that is modelled
        truthfully, nothing paid may win on speed."""
        paid_and_fast = provider("paid.api", quality=0.95, latency=100, cost=0.02)
        free_and_slower = provider("free.api", quality=0.80, latency=4_000)

        assert decide([paid_and_fast, free_and_slower], FAST_FREE).winner == "free.api"
        assert FAST_FREE.allow_paid is False


class TestThePolicyOwnerDecidesWhichPolicyApplies:

    def test_an_interactive_turn_is_decided_under_fast_free(self):
        assert policy_for_request_class(INTERACTIVE) is FAST_FREE

    def test_every_other_class_keeps_what_production_configured(self):
        """Planning is emphatically NOT made latency-first by this."""
        configured = get_policy("prefer_free")
        for name in (EXECUTION, "planning", "verification", None, ""):
            assert policy_for_request_class(name, configured) is configured

    def test_fast_free_is_versioned_like_every_other_policy(self):
        assert FAST_FREE.policy_version == "fast_free/1"
        assert get_policy("fast_free") is FAST_FREE
        assert PREFER_FREE.ranking != FAST_FREE.ranking


@dataclasses.dataclass(frozen=True)
class Request:
    request_class: str
    exclude_providers: frozenset = frozenset()


class TestTheRunnerStopsPreDecidingByLocality:

    def _runner(self):
        from master_agent.ai_infrastructure.tiered_runner import TieredPromptRunner

        return TieredPromptRunner(
            prompt_executor=object(),
            gemini_provider_ids=frozenset({"gemini.api"}),
            desktop_provider_ids=frozenset({"a.desktop", "b.desktop"}),
            browser_provider_ids=frozenset({"browser.free-ai"}),
            local_provider_ids=frozenset(),
        )

    def test_E_an_interactive_turn_sees_every_provider_in_one_attempt(self):
        """One attempt, every candidate -- and `_attempt_tier()` already
        falls through candidate by candidate inside one attempt, so a
        selected provider that fails still yields to the next eligible
        one, bounded by the candidate count."""
        from master_agent.ai_infrastructure.tiered_runner import TIER_ANY

        attempts = self._runner()._ordered_attempts(Request(INTERACTIVE))

        assert len(attempts) == 1
        name, ids = attempts[0]
        assert name == TIER_ANY
        assert {"gemini.api", "a.desktop", "b.desktop", "browser.free-ai"} <= set(ids)

    def test_every_other_class_still_walks_the_ladder_unchanged(self):
        runner = self._runner()

        assert runner._ordered_attempts(Request(EXECUTION)) == runner._tiers


class TestDeterministicWorkStillCallsNoProvider:

    def test_F_a_fully_dictated_objective_contacts_no_provider(self):
        """The fast path is about which provider answers, never about
        whether one is asked. Deterministic work still asks nobody."""
        from master_agent.capabilities.extraction import contracts_from_actions
        from master_agent.capabilities.index import build_index
        from master_agent.executor.executor import LocalExecutor
        from master_agent.mission_control.capabilities import qualified_name
        from master_agent.permissions.permission_system import PermissionSystem
        from master_agent.planner.catalogue import catalogue_from_index
        from master_agent.planner.direct import direct_plan
        from master_agent.planner.plan import Intent
        from master_agent.plugins.filesystem_plugin import FilesystemPlugin

        plugin = FilesystemPlugin(LocalExecutor(PermissionSystem()))
        contracts = contracts_from_actions(
            plugin._actions, plugin.manifest.name, qualified_name
        )
        index = build_index(contracts, loader={c.canonical_id: c for c in contracts}.get)

        goal = (
            "Create a folder called KV_Fast on the Desktop. Then show me the text "
            "before you write it into notes.txt inside that folder. The text "
            "should be: hello."
        )

        plan = direct_plan(Intent(goal=goal), catalogue_from_index(index))

        assert plan is not None, "a dictated objective was sent to a provider"
        assert [step.capability for step in plan.steps] == [
            "Filesystem.CreateFolder", "Filesystem.WriteFile",
        ]


class TestKnownButNotConfiguredIsNeverACandidate:
    """`_all_ids` is the universe needed to EXCLUDE everything not allowed
    in an attempt. It was briefly used as the candidate set, which turned
    "every provider this codebase has a descriptor for" into "every
    provider we may send a prompt to" -- and a live interactive run duly
    reported `ollama.local` as eligible.

    Founder Edition's no-Ollama contract rests on exactly this: the
    descriptor stays in PROVIDER_CATALOG deliberately, is never
    constructed, registered or probed, and its presence in the exclusion
    universe is what keeps it out. The invariant is generic -- known but
    not configured is never a candidate -- and needs no exclusion table.
    """

    def _runner(self, **overrides):
        from master_agent.ai_infrastructure.tiered_runner import TieredPromptRunner

        kwargs = dict(
            prompt_executor=object(),
            gemini_provider_ids=frozenset({"gemini.api"}),
            desktop_provider_ids=frozenset({"chatgpt-desktop", "kimi-desktop"}),
            browser_provider_ids=frozenset({"browser.free-ai"}),
            local_provider_ids=frozenset(),
            all_known_provider_ids=frozenset({
                "gemini.api", "chatgpt-desktop", "kimi-desktop", "browser.free-ai",
                # Known to ProviderSource, configured by nobody.
                "ollama.local", "lm-studio.local", "openai.api", "openrouter.api",
            }),
        )
        kwargs.update(overrides)
        return TieredPromptRunner(**kwargs)

    def _interactive_ids(self, runner):
        attempts = runner._ordered_attempts(Request(INTERACTIVE))
        assert len(attempts) == 1
        return set(attempts[0][1])

    def test_A_the_attempt_contains_only_configured_tier_ids(self):
        assert self._interactive_ids(self._runner()) == {
            "gemini.api", "chatgpt-desktop", "kimi-desktop", "browser.free-ai",
        }

    def test_B_a_provider_known_only_to_the_universe_is_excluded(self):
        runner = self._runner()

        candidates = self._interactive_ids(runner)

        for known_only in ("ollama.local", "lm-studio.local", "openai.api",
                           "openrouter.api"):
            assert known_only in runner._all_ids, "the exclusion universe changed"
            assert known_only not in candidates

    def test_C_ollama_stays_in_the_catalogue_and_never_in_an_attempt(self):
        from master_agent.ai_infrastructure.catalog import PROVIDER_CATALOG

        catalogued = {spec.provider_id for spec in PROVIDER_CATALOG}
        assert "ollama.local" in catalogued, (
            "the descriptor is kept on purpose -- removing it is not the fix"
        )
        assert "ollama.local" not in self._interactive_ids(self._runner())

    def test_D_unconfigured_providers_cannot_arrive_via_the_descriptor_set(self):
        """Every attempt, not merely the interactive one."""
        runner = self._runner()

        for request_class in (INTERACTIVE, EXECUTION):
            for _name, ids in runner._ordered_attempts(Request(request_class)):
                assert not ({"ollama.local", "lm-studio.local", "openai.api",
                             "openrouter.api"} & set(ids))

    def test_E_configured_providers_still_compete_together(self):
        """The fast path is still cross-tier: Gemini, desktop and browser
        in ONE attempt, ranked by the Broker."""
        candidates = self._interactive_ids(self._runner())

        assert "gemini.api" in candidates
        assert {"chatgpt-desktop", "kimi-desktop"} <= candidates
        assert "browser.free-ai" in candidates

    def test_F_the_scope_still_excludes_everything_outside_the_attempt(self):
        """`_all_ids` keeps its original meaning, which is what makes the
        fallback in `_attempt_tier()` safe: a request scoped to the
        remaining candidates excludes every other id the Broker can see."""
        runner = self._runner()
        remaining = {"chatgpt-desktop"}

        scoped = runner._scope(Request(INTERACTIVE), remaining)

        assert "ollama.local" in scoped.exclude_providers
        assert "gemini.api" in scoped.exclude_providers
        assert "chatgpt-desktop" not in scoped.exclude_providers

    def test_a_deployment_configuring_nothing_falls_back_to_the_ladder(self):
        runner = self._runner(
            gemini_provider_ids=frozenset(), desktop_provider_ids=frozenset(),
            browser_provider_ids=frozenset(),
        )

        assert runner._ordered_attempts(Request(INTERACTIVE)) == runner._tiers
