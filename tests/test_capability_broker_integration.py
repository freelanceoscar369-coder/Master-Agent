"""Mission Brief 031 Deliverable 12 — Broker integration tests.

The unit tests check one decision at a time. These check *histories*: a
sequence of decisions, taken under changing policies, written down, read
back, and replayed — which is the only way to test the claim that actually
matters for auditability.

Still no model, no network, no subprocess. Every provider is invented.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from master_agent.broker.broker import CapabilityBroker, replay_matches
from master_agent.broker.decision import (
    NO_PROVIDER_AVAILABLE,
    SELECTED,
    DecisionRecord,
)
from master_agent.broker.policy import (
    BALANCED,
    BEST_QUALITY,
    LOWEST_COST,
    OFFLINE_ONLY,
    POLICIES,
    PREFER_FREE,
    PREFER_LOCAL,
    PRIVACY_FIRST,
    get_policy,
)
from master_agent.broker.profiles import ProviderProfile, TaskProfile

START = datetime(2026, 7, 30, 9, 0, tzinfo=UTC)


class Clock:
    """A clock that advances a minute per read, so a history has an order
    without any test having to sleep."""

    def __init__(self, start: datetime = START) -> None:
        self._now = start

    def __call__(self) -> datetime:
        self._now += timedelta(minutes=1)
        return self._now


def fleet() -> list[ProviderProfile]:
    """A plausible mixed estate: two things on this machine, one installed
    application, two hosted services, one that needs approval, one down."""
    return [
        ProviderProfile(
            "aa-local-fast",
            frozenset({"reasoning", "coding"}),
            locality="local",
            privacy="private",
            quality=0.62,
            cost=0.0,
            latency_ms=600.0,
            requires_network=False,
        ),
        ProviderProfile(
            "bb-local-strong",
            frozenset({"reasoning", "coding", "reasoning.planning"}),
            locality="local",
            privacy="private",
            quality=0.84,
            benchmark=0.79,
            benchmark_confidence=0.7,
            cost=0.0,
            latency_ms=5200.0,
            requires_network=False,
        ),
        ProviderProfile(
            "cc-desktop-app",
            frozenset({"reasoning", "vision.ocr"}),
            locality="desktop",
            privacy="private",
            quality=0.71,
            cost=0.0,
            latency_ms=1500.0,
            requires_network=False,
        ),
        ProviderProfile(
            "dd-hosted-cheap",
            frozenset({"reasoning", "coding", "vision.ocr"}),
            locality="cloud",
            quality=0.78,
            cost=0.0015,
            latency_ms=450.0,
        ),
        ProviderProfile(
            "ee-hosted-strong",
            frozenset({"reasoning", "reasoning.planning", "coding"}),
            locality="cloud",
            quality=0.94,
            cost=0.018,
            latency_ms=1100.0,
        ),
        ProviderProfile(
            "ff-hosted-premium",
            frozenset({"reasoning", "reasoning.planning"}),
            locality="cloud",
            quality=0.97,
            cost=0.09,
            latency_ms=1400.0,
            requires_approval=True,
        ),
        ProviderProfile(
            "gg-offline-now",
            frozenset({"reasoning"}),
            locality="cloud",
            quality=0.9,
            cost=0.004,
            available=False,
        ),
    ]


#: A day's worth of varied work.
WORKLOAD = (
    TaskProfile(capability="reasoning", task_id="w1"),
    TaskProfile(capability="coding", task_id="w2", min_quality=0.75),
    TaskProfile(capability="reasoning.planning", task_id="w3", min_quality=0.8),
    TaskProfile(capability="vision.ocr", task_id="w4", min_quality=0.7),
    TaskProfile(
        capability="reasoning", task_id="w5", sensitivity="sensitive", min_quality=0.6
    ),
    TaskProfile(capability="reasoning", task_id="w6", offline=True, min_quality=0.6),
    TaskProfile(capability="speech.transcribe", task_id="w7"),
    TaskProfile(capability="reasoning", task_id="w8", max_cost=0.001, min_quality=0.7),
    TaskProfile(capability="reasoning", task_id="w9", max_latency_ms=700, min_quality=0.6),
    TaskProfile(capability="reasoning", task_id="w10", min_quality=0.99),
)


def run_workload(policy=BALANCED) -> CapabilityBroker:
    engine = CapabilityBroker(policy=policy, clock=Clock())
    for task in WORKLOAD:
        engine.select(task, fleet())
    return engine


# ---- a whole history replays ---------------------------------------------


def test_a_full_workload_produces_a_decision_for_every_task():
    engine = run_workload()

    assert len(engine.records()) == len(WORKLOAD)


def test_every_decision_in_a_history_replays_identically():
    """Deliverable 6 and 12's core claim, over a real sequence rather than
    one hand-picked case."""
    engine = run_workload()

    for record in engine.records():
        assert replay_matches(record), f"{record.decision.task.task_id} did not replay"


@pytest.mark.parametrize("policy_name", sorted(POLICIES))
def test_a_full_workload_replays_under_every_policy(policy_name):
    engine = run_workload(get_policy(policy_name))

    assert all(replay_matches(record) for record in engine.records())


def test_a_history_survives_being_written_down_and_read_back():
    engine = run_workload()
    serialised = json.dumps([r.as_dict() for r in engine.records()])

    restored = [DecisionRecord.from_dict(d) for d in json.loads(serialised)]

    assert len(restored) == len(WORKLOAD)
    for original, back in zip(engine.records(), restored, strict=True):
        assert back.winner == original.winner
        assert back.policy_version == original.policy_version
        assert replay_matches(back)


def test_a_restored_history_keeps_its_order():
    engine = run_workload()
    restored = [
        DecisionRecord.from_dict(json.loads(json.dumps(r.as_dict())))
        for r in engine.records()
    ]

    assert [r.decision.task.task_id for r in restored] == [t.task_id for t in WORKLOAD]
    timestamps = [r.decision.decided_at for r in restored]
    assert timestamps == sorted(timestamps)


# ---- the workload's actual answers ---------------------------------------


def winners(policy=BALANCED) -> dict[str, str | None]:
    engine = run_workload(policy)
    return {r.decision.task.task_id: r.winner for r in engine.records()}


def test_the_default_policy_prefers_free_capable_providers():
    chosen = winners()

    # w1 has no explicit floor, so `balanced`'s 0.6 applies; the free
    # local strong model clears it and costs nothing.
    assert chosen["w1"] == "bb-local-strong"


def test_a_capability_nothing_offers_is_refused():
    engine = run_workload()
    speech = next(r for r in engine.records() if r.decision.task.task_id == "w7")

    assert speech.decision.outcome == NO_PROVIDER_AVAILABLE
    assert speech.winner is None


def test_an_impossible_floor_is_refused_within_a_working_history():
    """One refusal must not disturb the decisions around it."""
    engine = run_workload()
    outcomes = {r.decision.task.task_id: r.decision.outcome for r in engine.records()}

    assert outcomes["w10"] == NO_PROVIDER_AVAILABLE
    assert outcomes["w9"] == SELECTED


def test_sensitive_work_stays_private_across_the_whole_workload():
    engine = run_workload()

    for record in engine.records():
        if record.decision.task.sensitivity != "sensitive":
            continue
        winner = next(
            p for p in record.providers if p.provider_id == record.winner
        )
        assert winner.privacy == "private"


def test_offline_work_never_picks_something_needing_the_network():
    engine = run_workload()
    offline = next(r for r in engine.records() if r.decision.task.offline)

    winner = next(p for p in offline.providers if p.provider_id == offline.winner)
    assert winner.requires_network is False


def test_a_cost_ceiling_is_respected_across_the_workload():
    engine = run_workload()
    capped = next(
        r for r in engine.records() if r.decision.task.max_cost is not None
    )

    winner = next(p for p in capped.providers if p.provider_id == capped.winner)
    assert winner.cost <= capped.decision.task.max_cost


def test_a_latency_ceiling_is_respected():
    engine = run_workload()
    quick = next(
        r for r in engine.records() if r.decision.task.max_latency_ms is not None
    )

    winner = next(p for p in quick.providers if p.provider_id == quick.winner)
    assert winner.latency_ms <= quick.decision.task.max_latency_ms


def test_a_provider_needing_approval_is_never_chosen_anywhere():
    """Across an entire day of decisions, not once."""
    engine = run_workload(BEST_QUALITY)

    assert all(r.winner != "ff-hosted-premium" for r in engine.records())


def test_an_unavailable_provider_is_never_chosen_anywhere():
    engine = run_workload(BEST_QUALITY)

    assert all(r.winner != "gg-offline-now" for r in engine.records())


# ---- policy switching (Deliverable 12) -----------------------------------


def test_switching_policy_changes_later_decisions_and_not_earlier_ones():
    engine = CapabilityBroker(policy=LOWEST_COST, clock=Clock())
    task = TaskProfile(capability="reasoning", task_id="same", min_quality=0.75)

    cheap = engine.select(task, fleet())
    engine.use_policy(BEST_QUALITY)
    best = engine.select(task, fleet())

    assert cheap.winner != best.winner
    assert cheap.policy_version == "lowest_cost/1"
    assert best.policy_version == "best_quality/1"
    # The first record still says what it said.
    assert engine.records()[0].decision.winner == cheap.winner


def test_every_record_replays_after_the_policy_changed_underneath_it():
    """The property that makes ADR-0018's learning loop safe: history is
    readable under the rules it was made under, not today's."""
    engine = CapabilityBroker(policy=LOWEST_COST, clock=Clock())
    task = TaskProfile(capability="reasoning", task_id="t", min_quality=0.7)

    engine.select(task, fleet())
    engine.use_policy(BEST_QUALITY)
    engine.select(task, fleet())
    engine.use_policy(PRIVACY_FIRST)
    engine.select(task, fleet())

    assert [r.policy_version for r in engine.records()] == [
        "lowest_cost/1",
        "best_quality/1",
        "privacy_first/1",
    ]
    assert all(replay_matches(r) for r in engine.records())


def test_a_policy_version_bump_is_a_different_decision_lineage():
    """ADR-0018: learning produces v2 as a discrete artifact. A decision
    made under v1 must not silently be re-read as v2."""
    v1 = BALANCED
    v2 = BALANCED.with_version("2")
    task = TaskProfile(capability="reasoning", task_id="t", min_quality=0.7)

    first = CapabilityBroker(v1, clock=Clock()).select(task, fleet())
    second = CapabilityBroker(v2, clock=Clock()).select(task, fleet())

    assert first.policy_version == "balanced/1"
    assert second.policy_version == "balanced/2"
    assert first.inputs_digest != second.inputs_digest


def test_the_same_task_under_every_policy_is_internally_consistent():
    """Different policies may disagree about the winner. None of them may
    pick something that failed a hard filter."""
    task = TaskProfile(capability="reasoning", task_id="t", min_quality=0.7)

    for name in sorted(POLICIES):
        decision = CapabilityBroker(get_policy(name), clock=Clock()).select(
            task, fleet()
        )
        if decision.winner is None:
            continue
        chosen = next(c for c in decision.candidates if c.provider_id == decision.winner)
        assert chosen.eligible is True
        assert chosen.quality >= decision.quality_floor


# ---- historical consistency ----------------------------------------------


def test_replaying_a_history_twice_gives_the_same_answers_both_times():
    engine = run_workload()
    records = engine.records()

    first = [engine.replay(r).winner for r in records]
    second = [engine.replay(r).winner for r in records]

    assert first == second


def test_replay_does_not_grow_the_ledger_however_often_it_runs():
    engine = run_workload()
    before = len(engine.records())

    for record in engine.records():
        engine.replay(record)
        engine.replay(record)

    assert len(engine.records()) == before


def test_two_brokers_given_the_same_history_agree():
    """Determinism across instances, not just across calls -- what makes a
    decision reproducible on another machine."""
    first = run_workload()
    second = CapabilityBroker(policy=BALANCED, clock=Clock())

    replayed = [second.replay(r).winner for r in first.records()]

    assert replayed == [r.winner for r in first.records()]


def test_a_digest_identifies_a_decision_across_a_whole_history():
    engine = run_workload()
    digests = [r.decision.inputs_digest for r in engine.records()]

    # w1's task differs from w2's, so their digests must too; and the two
    # refusals differ from everything else.
    assert len(set(digests)) == len(
        {t.as_dict()["capability"] + str(t.min_quality) + str(t.sensitivity)
         + str(t.offline) + str(t.max_cost) + str(t.max_latency_ms) + t.task_id
         for t in WORKLOAD}
    )


def test_a_changed_fleet_produces_a_different_digest_for_the_same_task():
    task = TaskProfile(capability="reasoning", task_id="t", min_quality=0.7)
    thinner = [p for p in fleet() if p.provider_id != "ee-hosted-strong"]

    full = CapabilityBroker(BALANCED, clock=Clock()).select(task, fleet())
    reduced = CapabilityBroker(BALANCED, clock=Clock()).select(task, thinner)

    assert full.inputs_digest != reduced.inputs_digest


# ---- regression suite ----------------------------------------------------
#
# Golden answers for the workload under the default policy. If a future
# change to scoring, ranking, or filtering alters any of these, it should
# have to say so out loud rather than drift silently.

GOLDEN_BALANCED = {
    # no floor given -> balanced's 0.6; bb measures 0.79, free, clears it
    "w1": "bb-local-strong",
    # coding at 0.75: bb (0.79) and dd (0.78) both clear, bb is free
    "w2": "bb-local-strong",
    # planning at 0.8: only ee (0.94) and ff clear, and ff needs approval
    "w3": "ee-hosted-strong",
    # vision.ocr at 0.7: cc (0.71, free) and dd (0.78, paid); cc is free
    "w4": "cc-desktop-app",
    # sensitive: private only, so bb over the hosted ones
    "w5": "bb-local-strong",
    # offline: no network, so bb over the hosted ones
    "w6": "bb-local-strong",
    # nothing offers speech.transcribe
    "w7": None,
    # max_cost 0.001 rules out both hosted; bb and cc are free, bb better
    "w8": "bb-local-strong",
    # max_latency 700ms: only aa (600) and dd (450) qualify; aa is free
    "w9": "aa-local-fast",
    # floor 0.99: nothing reaches it
    "w10": None,
}


def test_the_workload_matches_its_golden_answers():
    assert winners(BALANCED) == GOLDEN_BALANCED


def test_the_golden_answers_are_stable_across_runs():
    assert winners(BALANCED) == winners(BALANCED)


def test_prefer_local_never_leaves_the_machine_when_it_does_not_have_to():
    chosen = winners(PREFER_LOCAL)
    local_ids = {"aa-local-fast", "bb-local-strong", "cc-desktop-app"}

    # w3 needs planning at 0.8, which only hosted providers offer above
    # the floor, so it is the one honest exception.
    assert chosen["w3"] == "ee-hosted-strong"
    for task_id in ("w1", "w5", "w6"):
        assert chosen[task_id] in local_ids


def test_prefer_free_never_spends_anything():
    engine = run_workload(PREFER_FREE)

    for record in engine.records():
        if record.winner is None:
            continue
        winner = next(p for p in record.providers if p.provider_id == record.winner)
        assert winner.cost == 0.0


def test_offline_only_never_picks_a_networked_provider():
    engine = run_workload(OFFLINE_ONLY)

    for record in engine.records():
        if record.winner is None:
            continue
        winner = next(p for p in record.providers if p.provider_id == record.winner)
        assert winner.requires_network is False


def test_best_quality_never_picks_below_what_balanced_picked():
    """A stricter policy must never return a worse provider."""
    balanced = run_workload(BALANCED).records()
    best = run_workload(BEST_QUALITY).records()

    for cheap, strong in zip(balanced, best, strict=True):
        if cheap.winner is None or strong.winner is None:
            continue
        cheap_q = next(
            p.effective_quality for p in cheap.providers if p.provider_id == cheap.winner
        )
        strong_q = next(
            p.effective_quality for p in strong.providers if p.provider_id == strong.winner
        )
        assert strong_q >= cheap_q


def test_a_measured_benchmark_is_used_across_the_workload():
    """`bb-local-strong` claims 0.84 and measured 0.79. A task with a 0.8
    floor must therefore reject it -- the measurement, not the claim."""
    engine = CapabilityBroker(BALANCED, clock=Clock())
    decision = engine.select(
        TaskProfile(capability="reasoning", task_id="t", min_quality=0.8), fleet()
    )

    rejected = {c.provider_id for c in decision.rejected}
    assert "bb-local-strong" in rejected
    assert decision.winner == "ee-hosted-strong"
