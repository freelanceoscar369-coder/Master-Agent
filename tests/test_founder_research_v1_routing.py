"""Founder Research Mission V1: the reusable routing contract.

These tests deliberately use the existing ProviderRegistry,
CapabilityBroker, approval gate, Intent and MissionProgress owners.  The
capability name is the public-research semantic need; no research-specific
broker or registry is introduced for the test.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import inspect

import kalpavriksha_desktop as desktop

from master_agent.ai_infrastructure.approval import ProviderApprovalGate
from master_agent.brain.deliberation import MissionProgress, no_useful_progress
from master_agent.broker.broker import CapabilityBroker
from master_agent.broker.decision import BELOW_FLOOR, EXCLUDED, NO_CAPABILITY, UNAVAILABLE
from master_agent.broker.policy import FREE_FIRST
from master_agent.broker.profiles import ProviderProfile, TaskProfile
from master_agent.broker.registry import EconomicClass, ProviderDescriptor, ProviderHealth
from master_agent.planner.plan import Intent


CAPABILITY = "public_research.acquire"


def provider(
    provider_id: str,
    *,
    quality: float,
    economic_class: EconomicClass,
    cost: float,
    available: bool = True,
    capabilities: frozenset[str] = frozenset({CAPABILITY}),
) -> ProviderProfile:
    return ProviderProfile(
        provider_id=provider_id,
        capabilities=capabilities,
        quality=quality,
        cost=cost,
        available=available,
        economic_class=economic_class.value,
    )


def request(**changes) -> TaskProfile:
    values = {
        "capability": CAPABILITY,
        "task_id": "research-route-1",
        "min_quality": 0.75,
    }
    values.update(changes)
    return TaskProfile(**values)


def decide(*providers: ProviderProfile, task: TaskProfile | None = None):
    return CapabilityBroker(policy=FREE_FIRST).select(
        task or request(), list(providers)
    )


class TestEligibilityBeforeEconomics:
    def test_ineligible_candidates_are_excluded_before_ranking(self):
        wrong = provider(
            "wrong-capability",
            quality=1.0,
            economic_class=EconomicClass.NO_LICENCE_FEE,
            cost=0.0,
            capabilities=frozenset({"unrelated"}),
        )
        unavailable = provider(
            "unavailable-free",
            quality=1.0,
            economic_class=EconomicClass.NO_LICENCE_FEE,
            cost=0.0,
            available=False,
        )
        adequate = provider(
            "adequate-free",
            quality=0.8,
            economic_class=EconomicClass.RECURRING_FREE,
            cost=0.0,
        )

        decision = decide(wrong, unavailable, adequate)

        assert decision.winner == "adequate-free"
        rejected = {candidate.provider_id: candidate.reason for candidate in decision.rejected}
        assert rejected["wrong-capability"] == NO_CAPABILITY
        assert rejected["unavailable-free"] == UNAVAILABLE

    def test_free_but_inadequate_loses_to_adequate_paid(self):
        weak_free = provider(
            "weak-free",
            quality=0.5,
            economic_class=EconomicClass.RECURRING_FREE,
            cost=0.0,
        )
        adequate_paid = provider(
            "adequate-paid",
            quality=0.9,
            economic_class=EconomicClass.PAID,
            cost=0.02,
        )

        decision = decide(weak_free, adequate_paid)

        assert decision.winner == "adequate-paid"
        assert {c.provider_id: c.reason for c in decision.rejected}["weak-free"] == BELOW_FLOOR

    def test_adequate_free_beats_incremental_paid(self):
        free = provider(
            "adequate-free",
            quality=0.8,
            economic_class=EconomicClass.RECURRING_FREE,
            cost=0.0,
        )
        paid = provider(
            "excellent-paid",
            quality=0.99,
            economic_class=EconomicClass.PAID,
            cost=0.001,
        )

        decision = decide(paid, free)

        assert decision.winner == "adequate-free"
        assert decision.ranked[0].economic_class == EconomicClass.RECURRING_FREE.value


class TestBoundedReselection:
    def test_failed_route_is_excluded_and_the_next_eligible_route_wins(self):
        first = provider(
            "route-a",
            quality=0.85,
            economic_class=EconomicClass.NO_LICENCE_FEE,
            cost=0.0,
        )
        second = provider(
            "route-b",
            quality=0.82,
            economic_class=EconomicClass.RECURRING_FREE,
            cost=0.0,
        )
        initial = decide(first, second)
        retry = decide(
            first,
            second,
            task=replace(request(), exclude_providers=frozenset({initial.winner})),
        )

        assert initial.winner == "route-a"
        assert retry.winner == "route-b"
        assert {c.provider_id: c.reason for c in retry.rejected}["route-a"] == EXCLUDED
        assert len({initial.winner, retry.winner}) == 2

    def test_route_change_does_not_change_the_canonical_intent(self):
        intent = Intent(
            goal="compare three current products and save a verified report",
            constraints=["use public evidence"],
            context={"raw_input": "founder words"},
            success_criteria=["report saved to Desktop"],
        )
        before = (
            intent.goal,
            tuple(intent.constraints),
            tuple(intent.success_criteria),
        )

        intent.context["recovery"] = {
            "failed_routes": ["public_research.acquire route-a"],
            "evidence_ids": ["ev-1"],
        }

        assert (
            intent.goal,
            tuple(intent.constraints),
            tuple(intent.success_criteria),
        ) == before

    def test_no_progress_is_detected_without_discarding_evidence(self):
        before = MissionProgress(
            objective="research",
            unresolved=("req-2",),
            evidence_ids=("ev-1",),
            failed_routes=("route-a",),
        )
        repeated = MissionProgress(
            objective="research",
            unresolved=("req-2",),
            evidence_ids=("ev-1",),
            failed_routes=("route-a",),
        )
        changed = MissionProgress(
            objective="research",
            unresolved=("req-2",),
            evidence_ids=("ev-1", "ev-2"),
            failed_routes=("route-a", "route-b"),
        )

        assert no_useful_progress(before, repeated) is True
        assert no_useful_progress(before, changed) is False
        assert "ev-1" in changed.evidence_ids


class TestEconomicTruthAndApprovalWiring:
    def test_unknown_economics_remains_unknown_in_broker_projection_and_record(self):
        descriptor = ProviderDescriptor(
            provider_id="unknown-route",
            display_name="Unknown Route",
            provider_class="web",
            capabilities=frozenset({CAPABILITY}),
            declared_quality=0.8,
            cost_per_call=0.0,
            economic_class=EconomicClass.UNKNOWN,
            health=ProviderHealth.HEALTHY,
            registered_at=datetime(2026, 8, 30, tzinfo=UTC),
        )

        profile = descriptor.to_profile()
        decision = decide(profile)

        assert profile.economic_class == EconomicClass.UNKNOWN.value
        assert decision.candidates[0].economic_class == EconomicClass.UNKNOWN.value
        assert decision.as_dict()["candidates"][0]["economic_class"] == "unknown"

    def test_founder_edition_uses_existing_provider_approval_gate(self):
        # The full composition imports Windows UI Automation and therefore
        # is not a hermetic unit fixture.  Existing approval integration
        # tests exercise ProviderApprovalGate behaviour; this assertion
        # pins the production composition root to that proven owner.
        source = inspect.getsource(desktop._build_mission_pipeline)

        assert 'get_policy("free_first")' in source
        assert "ProviderApprovalGate(mission_control, permissions)" in source
        assert ProviderApprovalGate is not None
        assert FREE_FIRST.allow_paid is True
