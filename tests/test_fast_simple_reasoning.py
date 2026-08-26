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
