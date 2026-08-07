"""Mission Brief 033 — the Token Economy: the cache interface, the
execution record, and the counting.

The brief's hardest instruction is a negative one:

> Do NOT estimate imaginary savings. Only count executions that actually
> occurred.

Most of this file exists to hold that line. It is easy to write a "money
saved" number that grows on its own, flatters whoever reads it, and is
unfalsifiable — and every one of those properties is a reason not to.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from master_agent.ai_infrastructure.cache import (
    CACHE_STATES,
    HIT,
    MISS,
    NOT_CONSULTED,
    CachedResponse,
    CacheLookup,
    ExactPromptCache,
    NullPromptCache,
    PromptCache,
    cache_key,
)
from master_agent.ai_infrastructure.economy import (
    CLOUD,
    COUNTED,
    NO_CACHE,
    NOTHING_YET,
    TokenEconomy,
    summarise,
)
from master_agent.ai_infrastructure.ledger import (
    CACHE_HIT,
    DecisionLedger,
    ExecutionRecord,
    InMemoryDecisionStore,
    JsonFileDecisionStore,
    UnknownDecision,
)
from tests.broker_test_support import Harness

WHEN = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)


def cached(**kwargs) -> CachedResponse:
    defaults = {
        "text": "an answer",
        "provider_id": "alpha-local",
        "model": "m",
        "verified": True,
        "stored_at": WHEN,
    }
    defaults.update(kwargs)
    return CachedResponse(**defaults)


def execution(**kwargs) -> ExecutionRecord:
    defaults = {
        "provider_id": "alpha-local",
        "outcome": "succeeded",
        "latency_ms": 1200.0,
        "cost": 0.0,
        "locality": "local",
        "cache": MISS,
        "executed_at": WHEN,
    }
    defaults.update(kwargs)
    return ExecutionRecord(**defaults)


# =========================================================================
# The cache key
# =========================================================================


def test_the_same_question_hashes_the_same_way():
    assert cache_key("reasoning", "p", "m", "hello") == cache_key(
        "reasoning", "p", "m", "hello"
    )


@pytest.mark.parametrize(
    "changed",
    [
        ("coding", "p", "m", "hello"),
        ("reasoning", "other", "m", "hello"),
        ("reasoning", "p", "other", "hello"),
        ("reasoning", "p", "m", "goodbye"),
    ],
)
def test_changing_any_part_changes_the_key(changed):
    """All four matter. The same prompt to a different model is a
    different answer; the same prompt for a different capability was asked
    for a different reason."""
    assert cache_key(*changed) != cache_key("reasoning", "p", "m", "hello")


def test_the_key_does_not_carry_the_prompt_around_in_the_clear():
    key = cache_key("reasoning", "p", "m", "my private business plan")

    assert "private" not in key
    assert "business" not in key


def test_the_key_is_a_fixed_length_digest():
    short = cache_key("r", "p", "m", "x")
    long = cache_key("r", "p", "m", "x" * 10_000)

    assert len(short) == len(long) == 32


def test_parts_cannot_be_smeared_into_each_other():
    """Concatenating without a separator would make ("ab", "c") and
    ("a", "bc") the same question."""
    assert cache_key("ab", "c", "m", "p") != cache_key("a", "bc", "m", "p")


@pytest.mark.parametrize("missing", [None, ""])
def test_a_missing_part_is_tolerated(missing):
    assert cache_key(missing, "p", "m", "prompt")


# =========================================================================
# The interface, and the two implementations
# =========================================================================


@pytest.mark.parametrize("implementation", [NullPromptCache(), ExactPromptCache()])
def test_both_caches_satisfy_the_protocol(implementation):
    assert isinstance(implementation, PromptCache)


def test_the_protocol_is_exactly_the_three_methods_the_brief_names():
    members = {name for name in dir(PromptCache) if not name.startswith("_")}

    assert members == {"lookup", "store", "invalidate"}


def test_the_states_a_lookup_can_report_are_closed():
    assert set(CACHE_STATES) == {HIT, MISS, NOT_CONSULTED}


def test_a_miss_and_a_never_looked_are_different_facts():
    """ADR-0016 again: "we looked and found nothing" and "we never looked"
    are not the same, and a panel that showed both as MISS would be
    lying about one of them."""
    assert MISS != NOT_CONSULTED


# ---- the shipped default ------------------------------------------------


def test_the_default_cache_never_hits():
    lookup = NullPromptCache().lookup("any-key")

    assert lookup.state == MISS
    assert lookup.hit is False
    assert lookup.entry is None


def test_the_default_cache_stores_nothing_and_says_so():
    assert NullPromptCache().store("k", cached()) is False


def test_the_default_cache_has_nothing_to_invalidate():
    assert NullPromptCache().invalidate() == 0
    assert NullPromptCache().invalidate("k") == 0
    assert len(NullPromptCache()) == 0


def test_a_lookup_always_carries_the_key_back():
    """So a caller stores against the same key rather than recomputing it
    and risking a different one."""
    assert NullPromptCache().lookup("abc").key == "abc"


# ---- the reference implementation ---------------------------------------


def test_verified_work_can_be_stored_and_found_again():
    cache = ExactPromptCache()

    assert cache.store("k", cached()) is True
    assert cache.lookup("k").hit is True
    assert cache.lookup("k").entry.text == "an answer"


def test_unverified_work_is_refused_by_default():
    """Rule 2 at the only door that can break it. A cache that stored
    unchecked output would make Kalpavriksha repeat a wrong answer
    faster, which is worse than not caching."""
    cache = ExactPromptCache()

    assert cache.store("k", cached(verified=False)) is False
    assert cache.lookup("k").hit is False


def test_unverified_storage_can_be_turned_on_explicitly():
    cache = ExactPromptCache(allow_unverified=True)

    assert cache.store("k", cached(verified=False)) is True


def test_a_different_key_is_a_miss():
    cache = ExactPromptCache()
    cache.store("k", cached())

    assert cache.lookup("other").hit is False


def test_matching_is_exact_and_never_approximate():
    """No embeddings, no similarity, no "close enough". Close enough is a
    judgement, and judgements belong to the Broker."""
    cache = ExactPromptCache()
    cache.store(cache_key("reasoning", "p", "m", "what is 2+2"), cached())

    assert cache.lookup(cache_key("reasoning", "p", "m", "what is 2 + 2")).hit is False


def test_hits_and_misses_are_counted():
    cache = ExactPromptCache()
    cache.store("k", cached())

    cache.lookup("k")
    cache.lookup("k")
    cache.lookup("nope")

    assert cache.hits == 2
    assert cache.misses == 1


def test_storing_the_same_key_twice_replaces_rather_than_duplicates():
    cache = ExactPromptCache()
    cache.store("k", cached(text="first"))
    cache.store("k", cached(text="second"))

    assert len(cache) == 1
    assert cache.lookup("k").entry.text == "second"


def test_one_entry_can_be_invalidated():
    cache = ExactPromptCache()
    cache.store("a", cached())
    cache.store("b", cached())

    assert cache.invalidate("a") == 1
    assert len(cache) == 1


def test_invalidating_everything_reports_how_much_went():
    cache = ExactPromptCache()
    cache.store("a", cached())
    cache.store("b", cached())

    assert cache.invalidate() == 2
    assert len(cache) == 0


def test_invalidating_something_that_was_never_there_is_not_an_error():
    assert ExactPromptCache().invalidate("never") == 0


def test_a_cached_response_remembers_what_the_original_cost():
    """The only honest basis for "money saved": an execution that
    happened once, with its cost attached."""
    entry = cached(cost=0.02, locality=CLOUD)

    assert entry.cost == 0.02
    assert entry.locality == CLOUD


def test_a_cached_response_stamps_itself_when_it_was_not_given_a_time():
    entry = CachedResponse(text="x", provider_id="p")

    assert entry.stored_at is not None


def test_a_cached_response_serialises():
    payload = cached(cost=0.5).as_dict()

    assert payload["text"] == "an answer"
    assert payload["cost"] == 0.5
    assert payload["verified"] is True


def test_a_lookup_result_is_frozen():
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        CacheLookup(state=MISS, key="k").state = HIT  # type: ignore[misc]


# =========================================================================
# The execution record (Rule 3)
# =========================================================================


@pytest.mark.parametrize(
    "field",
    [
        "latency_ms",
        "prompt_tokens",
        "completion_tokens",
        "cost",
        "quality_declared",
        "retries",
        "cache",
    ],
)
def test_the_record_carries_everything_rule_three_names(field):
    assert hasattr(execution(), field)


def test_a_successful_execution_says_so():
    assert execution(outcome="succeeded").succeeded is True


def test_a_failed_execution_says_so():
    assert execution(outcome="timed_out").succeeded is False


def test_a_cache_hit_counts_as_a_success_but_not_as_an_execution():
    """It produced an answer, which is success. It contacted nobody, which
    is why the economy counts it separately."""
    record = execution(outcome=CACHE_HIT)

    assert record.succeeded is True
    assert record.from_cache is True


def test_a_real_execution_did_not_come_from_the_cache():
    assert execution().from_cache is False


def test_tokens_are_summed_only_when_both_halves_are_known():
    assert execution(prompt_tokens=10, completion_tokens=5).total_tokens == 15
    assert execution(prompt_tokens=10).total_tokens is None
    assert execution().total_tokens is None


def test_latency_is_offered_in_seconds_for_a_human():
    assert execution(latency_ms=1700.0).latency_seconds == 1.7


def test_an_unmeasured_latency_stays_unmeasured():
    assert execution(latency_ms=None).latency_seconds is None


def test_an_execution_record_round_trips_through_plain_data():
    original = execution(
        prompt_tokens=23,
        completion_tokens=2,
        quality_declared=0.72,
        quality_basis="declared",
        model="m:latest",
        retries=1,
        error="",
    )

    assert ExecutionRecord.from_dict(original.as_dict()) == original


def test_a_record_with_no_timestamp_round_trips_too():
    original = execution(executed_at=None)

    assert ExecutionRecord.from_dict(original.as_dict()).executed_at is None


def test_the_serialised_record_carries_the_derived_total():
    """A reader of the JSON should not have to know the summing rule."""
    payload = execution(prompt_tokens=3, completion_tokens=4).as_dict()

    assert payload["total_tokens"] == 7


# =========================================================================
# The ledger, extended
# =========================================================================


def test_a_decision_starts_with_no_execution():
    harness = Harness("alpha_runtime")
    harness.decide()

    assert harness.ledger.last().execution is None
    assert harness.ledger.last().executed is False


def test_an_execution_is_attached_to_the_decision_that_chose_it():
    harness = Harness("alpha_runtime")
    harness.decide()

    updated = harness.ledger.record_execution(1, execution())

    assert updated.execution is not None
    assert updated.executed is True


def test_recording_an_execution_never_touches_the_decision_record():
    """A decision stays replayable no matter how its execution went."""
    harness = Harness("alpha_runtime")
    harness.decide()
    before = harness.ledger.get(1).record

    harness.ledger.record_execution(1, execution())

    assert harness.ledger.get(1).record is before
    assert harness.ledger.replay_matches(1) is True


def test_recording_an_execution_does_not_add_a_second_entry():
    """A decision and its execution are two moments in the life of one
    task; two entries would read as the Broker deciding twice."""
    harness = Harness("alpha_runtime")
    harness.decide()

    harness.ledger.record_execution(1, execution())

    assert len(harness.ledger) == 1


def test_recording_against_an_unknown_decision_is_refused():
    with pytest.raises(UnknownDecision):
        Harness("alpha_runtime").ledger.record_execution(99, execution())


def test_a_later_execution_replaces_an_earlier_one_for_the_same_decision():
    harness = Harness("alpha_runtime")
    harness.decide()

    harness.ledger.record_execution(1, execution(outcome="timed_out"))
    harness.ledger.record_execution(1, execution(outcome="succeeded"))

    assert harness.ledger.get(1).execution.outcome == "succeeded"


def test_executions_lists_only_what_actually_ran():
    harness = Harness("alpha_runtime")
    harness.decide(task_id="a")
    harness.decide(task_id="b")
    harness.ledger.record_execution(2, execution())

    assert [e.task_id for e in harness.ledger.executions()] == ["b"]


def test_the_last_execution_is_the_most_recent_one():
    harness = Harness("alpha_runtime")
    harness.decide(task_id="a")
    harness.decide(task_id="b")
    harness.ledger.record_execution(1, execution())
    harness.ledger.record_execution(2, execution())

    assert harness.ledger.last_execution().task_id == "b"


def test_there_is_no_last_execution_before_anything_runs():
    harness = Harness("alpha_runtime")
    harness.decide()

    assert harness.ledger.last_execution() is None


def test_an_execution_survives_a_round_trip_through_storage():
    harness = Harness("alpha_runtime")
    harness.decide()
    harness.ledger.record_execution(1, execution(prompt_tokens=7, model="m"))

    rebuilt = DecisionLedger()
    rebuilt.restore(harness.ledger.as_dicts())

    assert rebuilt.get(1).execution.prompt_tokens == 7
    assert rebuilt.get(1).execution.model == "m"


def test_an_execution_survives_a_round_trip_through_a_file(tmp_path):
    store = JsonFileDecisionStore(tmp_path / "decisions.json")
    harness = Harness("alpha_runtime", store=store)
    harness.decide()
    harness.ledger.record_execution(1, execution(latency_ms=1234.0))

    reloaded = DecisionLedger(store=JsonFileDecisionStore(tmp_path / "decisions.json"))
    reloaded.load()

    assert reloaded.get(1).execution.latency_ms == 1234.0
    assert reloaded.replay_matches(1) is True


def test_a_ledger_written_before_this_brief_still_loads():
    """Every entry MB032 wrote has no `execution` key. Missing means "not
    executed", which is exactly what those entries were."""
    harness = Harness("alpha_runtime")
    harness.decide()
    rows = harness.ledger.as_dicts()
    del rows[0]["execution"]

    rebuilt = DecisionLedger()
    rebuilt.restore(rows)

    assert rebuilt.get(1).execution is None
    assert rebuilt.replay_matches(1) is True


def test_recording_an_execution_persists_immediately():
    store = InMemoryDecisionStore()
    harness = Harness("alpha_runtime", store=store)
    harness.decide()

    harness.ledger.record_execution(1, execution())

    assert store.rows[0]["execution"] is not None


# =========================================================================
# The counting (and what it refuses to count)
# =========================================================================


def entries_with(*records: ExecutionRecord):
    """A ledger holding one decision per execution, so the summariser has
    real entries to total rather than a hand-built list."""
    harness = Harness("alpha_runtime")
    for index, record in enumerate(records, start=1):
        harness.decide(task_id=f"t{index}")
        harness.ledger.record_execution(index, record)
    return harness.ledger.entries()


def test_nothing_run_is_reported_as_nothing_run():
    """Not as zeros that could equally mean a broken counter."""
    economy = summarise(())

    assert economy.total_executions == 0
    assert economy.basis == NOTHING_YET


def test_a_decision_that_never_ran_counts_for_nothing():
    harness = Harness("alpha_runtime")
    harness.decide()

    assert summarise(harness.ledger.entries()).total_executions == 0


def test_a_local_execution_is_counted_as_local():
    economy = summarise(entries_with(execution(locality="local")))

    assert economy.local_executions == 1
    assert economy.cloud_executions == 0


@pytest.mark.parametrize("locality", ["local", "desktop"])
def test_anything_not_cloud_is_local_spend_free_thinking(locality):
    assert summarise(entries_with(execution(locality=locality))).local_executions == 1


def test_a_cloud_execution_is_counted_as_cloud_and_as_spend():
    economy = summarise(entries_with(execution(locality=CLOUD, cost=0.02)))

    assert economy.cloud_executions == 1
    assert economy.total_spend == 0.02


def test_a_failed_execution_is_counted_separately_from_a_successful_one():
    """A failure that counted as a local execution would make the local
    share look better the more often things broke."""
    economy = summarise(entries_with(execution(outcome="timed_out")))

    assert economy.failed_executions == 1
    assert economy.local_executions == 0


def test_a_failure_costs_nothing_it_did_not_spend():
    economy = summarise(
        entries_with(execution(outcome="unavailable", locality=CLOUD, cost=0.05))
    )

    assert economy.total_spend == 0.0


def test_cache_hits_and_misses_are_counted_from_what_was_recorded():
    economy = summarise(
        entries_with(
            execution(cache=MISS),
            execution(outcome=CACHE_HIT, cache=HIT),
            execution(cache=NOT_CONSULTED),
        )
    )

    assert economy.cache_hits == 1
    assert economy.cache_misses == 1


def test_a_lookup_that_never_happened_is_neither_a_hit_nor_a_miss():
    economy = summarise(entries_with(execution(cache=NOT_CONSULTED)))

    assert economy.cache_hits == 0
    assert economy.cache_misses == 0


def test_a_cache_hit_is_not_an_execution():
    """The entire point of counting it separately: it is the *absence* of
    one."""
    economy = summarise(entries_with(execution(outcome=CACHE_HIT, cache=HIT)))

    assert economy.total_executions == 0
    assert economy.cache_hits == 1


def test_reusing_a_cloud_answer_is_one_cloud_call_that_did_not_happen():
    economy = summarise(
        entries_with(execution(outcome=CACHE_HIT, cache=HIT, locality=CLOUD, cost=0.02))
    )

    assert economy.avoided_cloud_executions == 1
    assert economy.money_saved == 0.02


def test_reusing_a_local_answer_saves_time_not_money():
    """And claiming otherwise would be the imaginary saving the brief
    forbids."""
    economy = summarise(
        entries_with(execution(outcome=CACHE_HIT, cache=HIT, locality="local", cost=0.0))
    )

    assert economy.avoided_cloud_executions == 0
    assert economy.money_saved == 0.0


def test_money_saved_is_never_what_a_more_expensive_provider_would_have_cost():
    """The counterfactual is unfalsifiable, always flattering, and would
    grow fastest on the days Kalpavriksha did the least. A local
    execution with an expensive provider available saves nothing, because
    nothing was avoided -- something was simply not chosen."""
    harness = Harness("alpha_runtime", enabled=("delta-cloud", "epsilon-cloud"))
    harness.decide()
    harness.ledger.record_execution(1, execution(locality="local", cost=0.0))

    assert summarise(harness.ledger.entries()).money_saved == 0.0


def test_savings_accumulate_across_several_reuses():
    economy = summarise(
        entries_with(
            execution(outcome=CACHE_HIT, cache=HIT, locality=CLOUD, cost=0.02),
            execution(outcome=CACHE_HIT, cache=HIT, locality=CLOUD, cost=0.03),
        )
    )

    assert economy.avoided_cloud_executions == 2
    assert economy.money_saved == pytest.approx(0.05)


def test_tokens_are_totalled_where_they_were_reported():
    economy = summarise(
        entries_with(
            execution(prompt_tokens=10, completion_tokens=5),
            execution(prompt_tokens=1, completion_tokens=2),
        )
    )

    assert economy.total_tokens == 18


def test_unreported_tokens_leave_the_total_unknown_rather_than_zero():
    assert summarise(entries_with(execution())).total_tokens is None


def test_a_mix_totals_only_what_was_reported():
    economy = summarise(
        entries_with(execution(prompt_tokens=3, completion_tokens=4), execution())
    )

    assert economy.total_tokens == 7


def test_latency_is_totalled():
    economy = summarise(
        entries_with(execution(latency_ms=1000.0), execution(latency_ms=500.0))
    )

    assert economy.total_latency_ms == 1500.0


def test_the_local_share_is_the_number_this_brief_is_about():
    economy = summarise(
        entries_with(
            execution(locality="local"),
            execution(locality="local"),
            execution(locality=CLOUD, cost=0.01),
        )
    )

    assert economy.local_share == pytest.approx(2 / 3)


def test_the_local_share_is_unknown_before_anything_runs():
    assert summarise(()).local_share is None


def test_a_hit_rate_over_no_lookups_is_unknown_rather_than_zero():
    """0/0 rendered as 0% reads as "the cache is useless" rather than "the
    cache has not been asked"."""
    assert summarise(()).cache_hit_rate is None


def test_a_hit_rate_is_reported_once_something_has_been_looked_up():
    economy = summarise(
        entries_with(execution(cache=MISS), execution(outcome=CACHE_HIT, cache=HIT))
    )

    assert economy.cache_hit_rate == 0.5


@pytest.mark.parametrize(
    ("records", "expected"),
    [
        ((), NOTHING_YET),
        ((execution(),), NO_CACHE),
        ((execution(outcome=CACHE_HIT, cache=HIT),), COUNTED),
    ],
)
def test_the_basis_says_which_of_the_three_states_the_zeros_mean(records, expected):
    """A row of zeroes is otherwise ambiguous between "nothing ran",
    "nothing was reused", and "this is real"."""
    assert summarise(entries_with(*records) if records else ()).basis == expected


def test_the_economy_serialises_for_a_front_end():
    payload = summarise(entries_with(execution(locality="local"))).as_dict()

    assert payload["local_executions"] == 1
    assert payload["basis"] == NO_CACHE
    assert "money_saved" in payload


def test_an_empty_economy_is_all_zeroes_and_says_why():
    economy = TokenEconomy()

    assert economy.total_executions == 0
    assert economy.money_saved == 0.0
    assert economy.basis == NOTHING_YET


def test_the_cloud_vocabulary_matches_the_brokers():
    """Two modules naming the same fact. Kept in step by a test rather
    than by one importing the other."""
    from master_agent.ai_infrastructure.economy import LOCAL_LOCALITIES
    from master_agent.broker.profiles import CLOUD as BROKER_CLOUD
    from master_agent.broker.profiles import DESKTOP, LOCAL

    assert CLOUD == BROKER_CLOUD
    assert set(LOCAL_LOCALITIES) == {LOCAL, DESKTOP}


def test_totals_are_recomputed_rather_than_accumulated():
    """A counter and a ledger eventually disagree, and the counter is the
    one on the screen. Asserted by summarising the same ledger twice and
    getting the same answer, then again after a change."""
    harness = Harness("alpha_runtime")
    harness.decide()
    harness.ledger.record_execution(1, execution())

    first = summarise(harness.ledger.entries())
    second = summarise(harness.ledger.entries())

    assert first == second
