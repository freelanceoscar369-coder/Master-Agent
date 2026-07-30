"""Mission Brief 031 — the AI Capability Broker core decision engine.

The claim under test: *given these provider profiles and this task, which
provider should be used?* — answered deterministically, auditably, and
**without ever contacting a real AI model.**

Every provider here is invented. There is no network, no subprocess, no
model, and no provider name from the real world in this file or in the
package it tests.
"""
from __future__ import annotations

import ast
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from master_agent.broker.broker import CapabilityBroker, replay_matches
from master_agent.broker.decision import (
    BELOW_FLOOR,
    CLOUD_FORBIDDEN,
    CONTEXT_TOO_SMALL,
    EXCLUDED,
    NEEDS_APPROVAL,
    NEEDS_NETWORK,
    NO_CAPABILITY,
    NO_PROVIDER_AVAILABLE,
    NOT_PRIVATE,
    OVER_COST,
    OVER_LATENCY,
    PAID_FORBIDDEN,
    SELECTED,
    UNAVAILABLE,
    DecisionRecord,
    compute_digest,
)
from master_agent.broker.policy import (
    BALANCED,
    BEST_QUALITY,
    BY_COST,
    BY_QUALITY,
    CLOUD_ALLOWED,
    LOWEST_COST,
    OFFLINE_ONLY,
    POLICIES,
    PREFER_FREE,
    PREFER_LOCAL,
    PRIVACY_FIRST,
    SelectionPolicy,
    UnknownRanking,
    get_policy,
    sort_key,
)
from master_agent.broker.profiles import ProviderProfile, TaskProfile

BROKER_DIR = Path(__file__).resolve().parents[1] / "src" / "master_agent" / "broker"
FIXED = datetime(2026, 7, 30, 9, 0, tzinfo=UTC)


def provider(pid: str, **kwargs) -> ProviderProfile:
    defaults = {
        "capabilities": frozenset({"reasoning"}),
        "locality": "cloud",
        "privacy": "third_party",
        "quality": 0.8,
        "cost": 0.01,
        "latency_ms": 500.0,
        "requires_network": True,
    }
    defaults.update(kwargs)
    return ProviderProfile(provider_id=pid, **defaults)


#: A small, deliberately invented world.
LOCAL_SMALL = provider(
    "alpha-local-small",
    locality="local",
    privacy="private",
    quality=0.55,
    cost=0.0,
    latency_ms=900.0,
    requires_network=False,
)
LOCAL_BIG = provider(
    "beta-local-big",
    locality="local",
    privacy="private",
    quality=0.82,
    cost=0.0,
    latency_ms=4000.0,
    requires_network=False,
)
CLOUD_CHEAP = provider("gamma-cloud-cheap", quality=0.75, cost=0.002, latency_ms=400.0)
CLOUD_BEST = provider("delta-cloud-best", quality=0.95, cost=0.02, latency_ms=900.0)

WORLD = [LOCAL_SMALL, LOCAL_BIG, CLOUD_CHEAP, CLOUD_BEST]


def broker(policy: SelectionPolicy = BALANCED) -> CapabilityBroker:
    return CapabilityBroker(policy=policy, clock=lambda: FIXED)


def task(**kwargs) -> TaskProfile:
    defaults = {"capability": "reasoning", "task_id": "t1"}
    defaults.update(kwargs)
    return TaskProfile(**defaults)


# ---- Deliverable 2: a decision comes out ---------------------------------


def test_a_task_and_providers_produce_a_decision():
    decision = broker().select(task(), WORLD)

    assert decision.outcome == SELECTED
    assert decision.winner is not None


def test_the_broker_reports_its_current_policy():
    assert broker(PRIVACY_FIRST).policy is PRIVACY_FIRST


def test_a_selected_decision_says_it_was_selected():
    assert broker().select(task(min_quality=0.7), WORLD).selected is True
    assert broker().select(task(min_quality=0.99), WORLD).selected is False


def test_locality_tells_local_from_cloud():
    assert LOCAL_BIG.is_local is True
    assert CLOUD_BEST.is_local is False
    assert provider("app", locality="desktop").is_local is True


def test_free_tells_free_from_paid():
    assert LOCAL_BIG.is_free is True
    assert CLOUD_BEST.is_free is False


def test_the_decision_names_the_policy_version():
    assert broker().select(task(), WORLD).policy_version == "balanced/1"


def test_the_decision_records_the_floor_applied():
    assert broker().select(task(min_quality=0.7), WORLD).quality_floor == 0.7


def test_the_decision_carries_the_task_it_answered():
    decision = broker().select(task(task_id="abc"), WORLD)

    assert decision.task.task_id == "abc"


def test_the_decision_explains_itself():
    decision = broker().select(task(min_quality=0.7), WORLD)

    assert "clears the floor" in decision.reason


# ---- Deliverable 8: cheapest that clears the floor -----------------------


def test_the_cheapest_provider_clearing_the_floor_wins():
    """MB031 Deliverable 8, stated exactly."""
    decision = broker().select(task(min_quality=0.7), WORLD)

    assert decision.winner == LOCAL_BIG.provider_id


def test_a_cheaper_provider_below_the_floor_is_not_chosen():
    """The whole point of a floor. `alpha-local-small` is free and would
    win on cost alone."""
    decision = broker().select(task(min_quality=0.7), WORLD)

    assert decision.winner != LOCAL_SMALL.provider_id
    rejected = {c.provider_id: c.reason for c in decision.rejected}
    assert rejected[LOCAL_SMALL.provider_id] == BELOW_FLOOR


def test_lowering_the_floor_admits_the_cheaper_one_as_a_candidate():
    """Both local providers are free, so cost ties and quality breaks it --
    `beta-local-big` still wins. What lowering the floor changes is that
    `alpha-local-small` becomes *eligible* rather than rejected, which is
    the property worth asserting."""
    high = broker().select(task(min_quality=0.7), WORLD)
    low = broker().select(task(min_quality=0.5), WORLD)

    assert LOCAL_SMALL.provider_id in {c.provider_id for c in high.rejected}
    assert LOCAL_SMALL.provider_id in {c.provider_id for c in low.ranked}
    assert low.winner == LOCAL_BIG.provider_id


def test_quality_breaks_a_cost_tie():
    """Among equally-priced providers, take the better one. Both local
    providers here are free."""
    decision = broker().select(task(min_quality=0.5), [LOCAL_SMALL, LOCAL_BIG])

    assert decision.winner == LOCAL_BIG.provider_id
    assert LOCAL_SMALL.cost == LOCAL_BIG.cost


def test_a_genuinely_cheaper_provider_wins_on_cost():
    dearer = provider("zeta-dearer", quality=0.9, cost=0.05)
    cheaper = provider("eta-cheaper", quality=0.75, cost=0.001)

    decision = broker().select(task(min_quality=0.7), [dearer, cheaper])

    assert decision.winner == "eta-cheaper"


def test_the_policy_floor_applies_when_the_task_names_none():
    decision = broker(BEST_QUALITY).select(task(), WORLD)

    assert decision.quality_floor == BEST_QUALITY.default_min_quality


def test_a_task_may_raise_the_floor_above_the_policy():
    decision = broker(LOWEST_COST).select(task(min_quality=0.9), WORLD)

    assert decision.quality_floor == 0.9
    assert decision.winner == CLOUD_BEST.provider_id


def test_a_policy_hard_floor_cannot_be_lowered_by_a_task():
    """A task may raise the bar; nothing may lower it past the policy's
    hard minimum -- which is what stops "just this once" becoming the
    default."""
    strict = SelectionPolicy(name="strict", version="1", hard_floor=0.8)

    decision = CapabilityBroker(strict, clock=lambda: FIXED).select(
        task(min_quality=0.1), WORLD
    )

    assert decision.quality_floor == 0.8


# ---- Deliverable 10: refusal ---------------------------------------------


def test_an_impossible_floor_refuses_rather_than_guessing():
    decision = broker().select(task(min_quality=0.99), WORLD)

    assert decision.outcome == NO_PROVIDER_AVAILABLE
    assert decision.winner is None


def test_the_refusal_says_how_close_the_best_candidate_got():
    """A refusal a founder can act on: lower the bar, install something,
    or grant an approval."""
    decision = broker().select(task(min_quality=0.99), WORLD)

    assert "0.99" in decision.reason
    assert CLOUD_BEST.provider_id in decision.reason
    assert "0.95" in decision.reason


def test_refusing_with_no_providers_at_all_says_so():
    decision = broker().select(task(), [])

    assert decision.outcome == NO_PROVIDER_AVAILABLE
    assert "no providers were offered" in decision.reason


def test_a_refusal_still_lists_every_candidate_and_why():
    decision = broker().select(task(min_quality=0.99), WORLD)

    assert len(decision.rejected) == len(WORLD)
    assert all(c.reason for c in decision.rejected)


def test_a_refusal_for_mixed_reasons_lists_them():
    decision = broker(OFFLINE_ONLY).select(
        task(capability="vision", min_quality=0.9), WORLD
    )

    assert decision.outcome == NO_PROVIDER_AVAILABLE
    assert NO_CAPABILITY in decision.reason


def test_the_broker_never_invents_a_provider():
    decision = broker().select(task(capability="nothing_offers_this"), WORLD)

    assert decision.winner is None
    assert decision.ranked == ()


# ---- Deliverable 9: ranked candidates ------------------------------------


def test_every_eligible_candidate_is_ranked():
    decision = broker().select(task(min_quality=0.7), WORLD)

    assert [c.rank for c in decision.ranked] == [1, 2, 3]


def test_the_ranking_is_cheapest_first_under_a_cost_policy():
    decision = broker(LOWEST_COST).select(task(min_quality=0.7), WORLD)

    assert [c.provider_id for c in decision.ranked] == [
        LOCAL_BIG.provider_id,
        CLOUD_CHEAP.provider_id,
        CLOUD_BEST.provider_id,
    ]


def test_the_ranking_is_best_first_under_a_quality_policy():
    decision = broker(BEST_QUALITY).select(task(min_quality=0.7), WORLD)

    assert decision.ranked[0].provider_id == CLOUD_BEST.provider_id


def test_the_winner_is_the_first_ranked():
    decision = broker().select(task(min_quality=0.7), WORLD)

    assert decision.winner == decision.ranked[0].provider_id


def test_rejected_candidates_are_never_ranked():
    decision = broker().select(task(min_quality=0.7), WORLD)

    assert all(c.rank is None for c in decision.rejected)


def test_candidates_carry_their_numbers_for_audit():
    decision = broker().select(task(min_quality=0.7), WORLD)
    winner = decision.ranked[0]

    assert winner.cost == 0.0
    assert winner.quality == 0.82
    assert winner.locality == "local"


# ---- Deliverable 3: what scoring considers -------------------------------


def test_capability_mismatch_is_rejected():
    decision = broker().select(task(capability="speech"), WORLD)

    assert {c.reason for c in decision.rejected} == {NO_CAPABILITY}


def test_a_prefix_capability_match_is_served():
    ocr = provider("ocr-one", capabilities=frozenset({"vision.ocr"}), quality=0.9)

    decision = broker().select(task(capability="vision", min_quality=0.7), [ocr])

    assert decision.winner == "ocr-one"


def test_a_specific_request_is_not_served_by_a_generic_provider():
    """Specific requests never get generic answers."""
    generic = provider("generic", capabilities=frozenset({"vision"}), quality=0.9)

    decision = broker().select(task(capability="vision.ocr"), [generic])

    assert decision.outcome == NO_PROVIDER_AVAILABLE


def test_an_unavailable_provider_is_rejected():
    down = provider("down", quality=0.9, available=False)

    decision = broker().select(task(min_quality=0.7), [down])

    assert decision.rejected[0].reason == UNAVAILABLE


def test_an_excluded_provider_is_rejected():
    decision = broker().select(
        task(min_quality=0.7, exclude_providers=frozenset({LOCAL_BIG.provider_id})),
        WORLD,
    )

    assert decision.winner != LOCAL_BIG.provider_id
    reasons = {c.provider_id: c.reason for c in decision.rejected}
    assert reasons[LOCAL_BIG.provider_id] == EXCLUDED


def test_a_too_expensive_provider_is_rejected():
    decision = broker().select(task(min_quality=0.7, max_cost=0.001), WORLD)

    reasons = {c.reason for c in decision.rejected}
    assert OVER_COST in reasons
    assert decision.winner == LOCAL_BIG.provider_id


def test_a_too_slow_provider_is_rejected():
    decision = broker().select(task(min_quality=0.7, max_latency_ms=1000), WORLD)

    reasons = {c.provider_id: c.reason for c in decision.rejected}
    assert reasons[LOCAL_BIG.provider_id] == OVER_LATENCY


def test_a_provider_with_too_small_a_context_is_rejected():
    small = provider("small-context", quality=0.9, max_context_tokens=1000)

    decision = broker().select(
        task(min_quality=0.7, required_context_tokens=50_000), [small]
    )

    assert decision.rejected[0].reason == CONTEXT_TOO_SMALL


def test_a_provider_needing_approval_is_never_selected():
    """The Broker never grants approval and never assumes it."""
    paid = provider("needs-yes", quality=0.99, requires_approval=True)

    decision = broker().select(task(min_quality=0.7), [paid])

    assert decision.outcome == NO_PROVIDER_AVAILABLE
    assert decision.rejected[0].reason == NEEDS_APPROVAL


def test_latency_is_a_ranking_dimension():
    fast = provider("fast", quality=0.8, cost=0.01, latency_ms=100.0)
    slow = provider("slow", quality=0.8, cost=0.01, latency_ms=9000.0)

    decision = broker().select(task(min_quality=0.7), [slow, fast])

    assert decision.winner == "fast"


def test_a_measured_benchmark_beats_a_declared_quality():
    """Constitution Rule 8: observed reality wins. A provider cannot
    market its way up the ranking."""
    boastful = provider("boastful", quality=0.99, benchmark=0.4, cost=0.0)
    honest = provider("honest", quality=0.7, benchmark=0.85, cost=0.001)

    decision = broker().select(task(min_quality=0.6), [boastful, honest])

    assert decision.winner == "honest"


def test_effective_quality_falls_back_to_declared_when_unmeasured():
    assert provider("p", quality=0.6).effective_quality == 0.6
    assert provider("p", quality=0.6, benchmark=0.9).effective_quality == 0.9


# ---- Deliverable 7: founder policies -------------------------------------


@pytest.mark.parametrize("name", sorted(POLICIES))
def test_every_named_policy_resolves(name):
    assert get_policy(name).name == name


@pytest.mark.parametrize("name", sorted(POLICIES))
def test_every_policy_has_a_version_and_a_description(name):
    policy = get_policy(name)

    assert policy.version
    assert policy.description
    assert policy.policy_version == f"{name}/{policy.version}"


@pytest.mark.parametrize("name", sorted(POLICIES))
def test_every_policy_makes_a_decision_over_the_world(name):
    decision = broker(get_policy(name)).select(task(min_quality=0.4), WORLD)

    assert decision.outcome in (SELECTED, NO_PROVIDER_AVAILABLE)


def test_an_unknown_policy_is_refused_with_the_known_list():
    with pytest.raises(UnknownRanking) as raised:
        get_policy("wishful")

    assert "balanced" in str(raised.value)


def test_prefer_local_chooses_a_local_provider():
    decision = broker(PREFER_LOCAL).select(task(min_quality=0.7), WORLD)

    assert decision.winner == LOCAL_BIG.provider_id


def test_prefer_free_rejects_everything_paid():
    decision = broker(PREFER_FREE).select(task(min_quality=0.5), WORLD)

    reasons = {c.reason for c in decision.rejected}
    assert PAID_FORBIDDEN in reasons
    assert decision.winner in (LOCAL_SMALL.provider_id, LOCAL_BIG.provider_id)


def test_offline_only_rejects_cloud_providers():
    decision = broker(OFFLINE_ONLY).select(task(min_quality=0.5), WORLD)

    reasons = {c.reason for c in decision.rejected}
    assert CLOUD_FORBIDDEN in reasons


def test_an_offline_task_rejects_anything_needing_the_network():
    decision = broker().select(task(min_quality=0.5, offline=True), WORLD)

    reasons = {c.provider_id: c.reason for c in decision.rejected}
    assert reasons[CLOUD_CHEAP.provider_id] == NEEDS_NETWORK
    assert reasons[CLOUD_BEST.provider_id] == NEEDS_NETWORK
    assert decision.winner == LOCAL_BIG.provider_id


def test_cloud_allowed_permits_cloud_providers():
    decision = broker(CLOUD_ALLOWED).select(task(min_quality=0.9), WORLD)

    assert decision.winner == CLOUD_BEST.provider_id


def test_best_quality_prefers_quality_over_cost():
    decision = broker(BEST_QUALITY).select(task(min_quality=0.7), WORLD)

    assert decision.winner == CLOUD_BEST.provider_id


def test_lowest_cost_prefers_cost_over_quality():
    decision = broker(LOWEST_COST).select(task(min_quality=0.7), WORLD)

    assert decision.winner == LOCAL_BIG.provider_id


def test_balanced_still_takes_the_cheapest_that_clears():
    """The bug a smoke run caught: a blended quality-per-cost score
    silently overrode Deliverable 8 and picked the paid provider."""
    decision = broker(BALANCED).select(task(min_quality=0.7), WORLD)

    assert decision.winner == LOCAL_BIG.provider_id
    assert LOCAL_BIG.cost == 0.0


def test_balanced_differs_from_lowest_cost_only_by_its_floor():
    assert BALANCED.ranking == (BY_COST, BY_QUALITY, "latency")
    assert BALANCED.default_min_quality > LOWEST_COST.default_min_quality


# ---- privacy -------------------------------------------------------------


def test_sensitive_work_never_goes_to_a_third_party():
    decision = broker().select(task(sensitivity="sensitive", min_quality=0.7), WORLD)

    reasons = {c.reason for c in decision.rejected}
    assert NOT_PRIVATE in reasons
    assert decision.winner == LOCAL_BIG.provider_id


def test_sensitive_work_refuses_when_nothing_is_private():
    decision = broker().select(
        task(sensitivity="sensitive", min_quality=0.7), [CLOUD_CHEAP, CLOUD_BEST]
    )

    assert decision.outcome == NO_PROVIDER_AVAILABLE


def test_privacy_first_ranks_private_providers_ahead():
    decision = broker(PRIVACY_FIRST).select(task(min_quality=0.7), WORLD)

    assert decision.ranked[0].provider_id == LOCAL_BIG.provider_id


def test_unrestricted_work_may_use_a_third_party():
    decision = broker().select(task(min_quality=0.9), WORLD)

    assert decision.winner == CLOUD_BEST.provider_id


def test_a_policy_can_waive_the_privacy_rule():
    """Configurable, but never silently: the policy says so by name."""
    lax = SelectionPolicy(
        name="lax", version="1", require_private_for_sensitive=False
    )

    decision = CapabilityBroker(lax, clock=lambda: FIXED).select(
        task(sensitivity="sensitive", min_quality=0.9), WORLD
    )

    assert decision.winner == CLOUD_BEST.provider_id


# ---- Deliverables 4 & 6: determinism, versioning, replay ------------------


def test_the_same_inputs_produce_the_same_decision():
    first = broker().select(task(min_quality=0.7), WORLD)
    second = broker().select(task(min_quality=0.7), WORLD)

    assert first.as_dict() == second.as_dict()


def test_provider_order_does_not_change_the_decision():
    """A digest that recorded the caller's list order would record
    something that is not an input to anything."""
    forward = broker().select(task(min_quality=0.7), WORLD)
    backward = broker().select(task(min_quality=0.7), list(reversed(WORLD)))

    assert forward.winner == backward.winner
    assert forward.inputs_digest == backward.inputs_digest


def test_ties_break_deterministically_on_provider_id():
    twin_a = provider("aaa", quality=0.8, cost=0.01, latency_ms=500.0)
    twin_b = provider("bbb", quality=0.8, cost=0.01, latency_ms=500.0)

    assert broker().select(task(min_quality=0.7), [twin_b, twin_a]).winner == "aaa"


def test_a_changed_provider_changes_the_digest():
    changed = [*WORLD[:-1], provider("delta-cloud-best", quality=0.5)]

    assert (
        broker().select(task(), WORLD).inputs_digest
        != broker().select(task(), changed).inputs_digest
    )


def test_a_changed_policy_changes_the_digest():
    assert (
        broker(BALANCED).select(task(), WORLD).inputs_digest
        != broker(BEST_QUALITY).select(task(), WORLD).inputs_digest
    )


def test_a_changed_task_changes_the_digest():
    assert (
        broker().select(task(min_quality=0.5), WORLD).inputs_digest
        != broker().select(task(min_quality=0.7), WORLD).inputs_digest
    )


def test_the_digest_is_stable_across_processes():
    """A hash of the inputs, not of object identity."""
    assert compute_digest(task(), tuple(WORLD), BALANCED) == compute_digest(
        task(), tuple(WORLD), BALANCED
    )


def test_every_decision_is_recorded():
    engine = broker()
    engine.select(task(), WORLD)
    engine.select(task(min_quality=0.9), WORLD)

    assert len(engine.records()) == 2


def test_records_are_returned_as_copies():
    engine = broker()
    engine.select(task(), WORLD)

    engine.records()  # a tuple; mutating the result is impossible

    assert len(engine.records()) == 1


def test_a_record_carries_the_providers_as_they_were():
    engine = broker()
    engine.select(task(), WORLD)
    record = engine.records()[0]

    assert len(record.providers) == len(WORLD)
    assert record.policy.policy_version == "balanced/1"


def test_replay_reproduces_a_decision():
    engine = broker()
    engine.select(task(min_quality=0.7), WORLD)
    record = engine.records()[0]

    assert replay_matches(record) is True


@pytest.mark.parametrize("name", sorted(POLICIES))
def test_replay_reproduces_a_decision_under_every_policy(name):
    engine = broker(get_policy(name))
    engine.select(task(min_quality=0.4), WORLD)

    assert replay_matches(engine.records()[0]) is True


def test_replay_reproduces_a_refusal():
    engine = broker()
    engine.select(task(min_quality=0.99), WORLD)

    assert replay_matches(engine.records()[0]) is True


def test_replay_uses_the_recorded_policy_not_the_current_one():
    """Replaying against today's policy would not be reproducing history;
    it would be making a new decision and calling it history."""
    engine = broker(BEST_QUALITY)
    engine.select(task(min_quality=0.7), WORLD)
    record = engine.records()[0]

    engine.use_policy(LOWEST_COST)

    assert engine.replay(record).winner == CLOUD_BEST.provider_id


def test_replay_does_not_append_to_the_ledger():
    """Replaying history must not change it."""
    engine = broker()
    engine.select(task(), WORLD)
    engine.replay(engine.records()[0])

    assert len(engine.records()) == 1


def test_switching_policy_leaves_past_decisions_readable():
    engine = broker(BALANCED)
    engine.select(task(min_quality=0.7), WORLD)
    engine.use_policy(BEST_QUALITY)
    engine.select(task(min_quality=0.7), WORLD)

    versions = [r.policy_version for r in engine.records()]
    assert versions == ["balanced/1", "best_quality/1"]


def test_a_new_policy_version_is_a_different_policy_version():
    v2 = BALANCED.with_version("2")

    assert v2.policy_version == "balanced/2"
    assert broker(v2).select(task(), WORLD).policy_version == "balanced/2"


def test_a_record_round_trips_through_json():
    """History has to survive being written down."""
    engine = broker()
    engine.select(task(min_quality=0.7), WORLD)
    record = engine.records()[0]

    restored = DecisionRecord.from_dict(json.loads(json.dumps(record.as_dict())))

    assert restored.winner == record.winner
    assert restored.policy_version == record.policy_version
    assert replay_matches(restored) is True


def test_a_restored_record_replays_identically():
    engine = broker(PRIVACY_FIRST)
    engine.select(task(sensitivity="sensitive", min_quality=0.6), WORLD)
    restored = DecisionRecord.from_dict(engine.records()[0].as_dict())

    assert [c.provider_id for c in engine.replay(restored).ranked] == [
        c.provider_id for c in restored.decision.ranked
    ]


# ---- the sink ------------------------------------------------------------


def test_a_sink_receives_every_decision():
    seen = []
    engine = CapabilityBroker(BALANCED, sink=seen.append, clock=lambda: FIXED)

    engine.select(task(), WORLD)

    assert len(seen) == 1
    assert seen[0].winner == engine.records()[0].winner


def test_a_broken_sink_never_changes_a_decision():
    def explode(_record):
        raise RuntimeError("sink down")

    engine = CapabilityBroker(BALANCED, sink=explode, clock=lambda: FIXED)

    decision = engine.select(task(min_quality=0.7), WORLD)

    assert decision.outcome == SELECTED
    assert engine.recording_failures == ["sink down"]


def test_a_broker_with_no_sink_decides_identically():
    with_sink = CapabilityBroker(BALANCED, sink=lambda _r: None, clock=lambda: FIXED)
    without = broker()

    assert (
        with_sink.select(task(), WORLD).winner == without.select(task(), WORLD).winner
    )


# ---- serialisation -------------------------------------------------------


def test_a_provider_profile_round_trips():
    restored = ProviderProfile.from_dict(LOCAL_BIG.as_dict())

    assert restored == LOCAL_BIG


def test_a_task_profile_round_trips():
    original = task(min_quality=0.7, exclude_providers=frozenset({"x"}))

    assert TaskProfile.from_dict(original.as_dict()) == original


def test_a_policy_round_trips():
    assert SelectionPolicy.from_dict(PRIVACY_FIRST.as_dict()) == PRIVACY_FIRST


def test_a_decision_serialises_to_json():
    payload = json.dumps(broker().select(task(), WORLD).as_dict())

    assert json.loads(payload)["policy_version"] == "balanced/1"


# ---- sort keys -----------------------------------------------------------


@pytest.mark.parametrize("ranking", ["cost", "quality", "latency", "locality", "privacy"])
def test_every_ranking_key_is_computable(ranking):
    assert isinstance(sort_key(ranking, LOCAL_BIG), tuple)


def test_an_unknown_ranking_is_refused():
    with pytest.raises(UnknownRanking):
        sort_key("vibes", LOCAL_BIG)


def test_missing_latency_sorts_last_rather_than_first():
    """Unknown must never look like "instant"."""
    unknown = provider("unknown-latency", quality=0.8, latency_ms=None)
    known = provider("known-latency", quality=0.8, latency_ms=10.0)

    assert sort_key("latency", known) < sort_key("latency", unknown)


# ---- architecture purity (the Absolutely Forbidden list) -----------------

FORBIDDEN_MODULES = (
    "subprocess",
    "socket",
    "http",
    "httpx",
    "requests",
    "urllib",
    "openai",
    "anthropic",
)


@pytest.mark.parametrize("module", FORBIDDEN_MODULES)
def test_the_broker_imports_nothing_that_could_execute(module):
    """It decides. A package that cannot reach the network or spawn a
    process cannot accidentally start calling models."""
    for path in BROKER_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                assert not name.startswith(module), f"{path.name} imports {name}"


@pytest.mark.parametrize(
    "vendor",
    ["openrouter", "ollama", "claude", "gemini", "gpt-", "llama", "mistral"],
)
def test_no_provider_name_appears_anywhere_in_the_package(vendor):
    """Completely provider-agnostic. Profiles come from the caller."""
    for path in BROKER_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        assert vendor not in text, f"'{vendor}' appears in {path.name}"


@pytest.mark.parametrize(
    "forbidden", ["def invoke", "def execute", "def launch", "def download", "def install"]
)
def test_the_broker_exposes_no_execution_surface(forbidden):
    for path in BROKER_DIR.rglob("*.py"):
        assert forbidden not in path.read_text(encoding="utf-8")


def test_the_broker_depends_on_no_other_kalpavriksha_subsystem():
    """A kernel service consulted from everywhere must depend on nothing,
    or it drags its dependencies into every caller (ADR-0017)."""
    allowed = "master_agent.broker"
    for path in BROKER_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            module = ""
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
            elif isinstance(node, ast.Import):
                module = node.names[0].name
            if module.startswith("master_agent"):
                assert module.startswith(allowed), f"{path.name} imports {module}"


def test_the_broker_never_reads_a_clock_it_was_not_given():
    """Determinism: `decided_at` is stamped from an injected clock, and
    nothing else consults time."""
    engine = CapabilityBroker(BALANCED, clock=lambda: FIXED)

    assert engine.select(task(), WORLD).decided_at == FIXED


def test_decided_at_is_excluded_from_the_digest():
    early = CapabilityBroker(BALANCED, clock=lambda: FIXED).select(task(), WORLD)
    later = CapabilityBroker(
        BALANCED, clock=lambda: datetime(2030, 1, 1, tzinfo=UTC)
    ).select(task(), WORLD)

    assert early.inputs_digest == later.inputs_digest
