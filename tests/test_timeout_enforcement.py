"""MB038 Step 7 — three-deadline enforcement.

Every test drives a fake clock. No sleeps, no wall clock, and therefore
no flakiness: a stall is produced by advancing time, not by waiting.
"""
from __future__ import annotations

import pytest

from master_agent.providers.budget import CallBudget
from master_agent.providers.deadline import (
    DeadlineExceeded,
    TimeoutEvent,
    check,
    read_timeout_seconds,
    supervise,
)
from master_agent.providers.response import (
    TIMED_OUT_ITL,
    TIMED_OUT_TOTAL,
    TIMED_OUT_TTFT,
    TIMEOUTS,
)
from master_agent.providers.stream import StreamMonitor

START = 1_000.0


class FakeClock:
    def __init__(self, start: float = START) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> float:
        self.now += seconds
        return self.now


def setup(ttft_s: float = 60.0, total_s: float = 300.0, itl_ms: float = 5_000.0,
          enforce_itl: bool = True):
    clock = FakeClock()
    # The invariant `CallBudget` enforces: a first token may not be owed
    # after the whole call is due. A test asking for a short total gets a
    # correspondingly short prefill window rather than an invalid budget.
    ttft_s = min(ttft_s, total_s)
    budget = CallBudget(
        total_deadline=START + total_s,
        ttft_deadline=START + ttft_s,
        itl_ms=itl_ms,
        enforce_itl=enforce_itl,
        total_ms=total_s * 1000,
        ttft_ms=ttft_s * 1000,
    )
    monitor = StreamMonitor(clock=clock, started_at=START)
    return clock, budget, monitor


# ---- 1. TTFT deadline ----------------------------------------------------


def test_no_first_token_before_the_ttft_deadline_is_a_ttft_timeout():
    clock, budget, monitor = setup(ttft_s=60.0)
    clock.advance(60.0)

    breach = check(budget, monitor, clock.now)

    assert breach.reason == TIMED_OUT_TTFT
    assert breach.limit_ms == 60_000.0
    assert breach.observed_ms == 60_000.0


def test_the_ttft_deadline_is_inclusive_of_its_own_instant():
    """A deadline is an instant you must not pass. At the instant, it is
    gone."""
    clock, budget, monitor = setup(ttft_s=60.0)

    clock.advance(59.999)
    assert check(budget, monitor, clock.now) is None

    clock.advance(0.001)
    assert check(budget, monitor, clock.now).reason == TIMED_OUT_TTFT


def test_a_token_before_the_deadline_retires_the_ttft_check_permanently():
    clock, budget, monitor = setup(ttft_s=60.0)
    clock.advance(10.0)
    monitor.token()
    clock.advance(120.0)

    breach = check(budget, monitor, clock.now)

    assert breach.reason != TIMED_OUT_TTFT


def test_total_is_reported_before_a_first_token_only_when_ttft_has_not_fired():
    """Reachable only for a non-streaming budget, where ttft == total."""
    clock, budget, monitor = setup(ttft_s=300.0, total_s=300.0)
    object.__setattr__(budget, "ttft_deadline", START + 400.0)
    clock.advance(300.0)

    assert check(budget, monitor, clock.now).reason == TIMED_OUT_TOTAL


# ---- 2. ITL deadline -----------------------------------------------------


def test_a_gap_larger_than_the_stall_budget_is_an_itl_timeout():
    clock, budget, monitor = setup(itl_ms=5_000.0)
    clock.advance(5.0)
    monitor.token()
    clock.advance(6.0)

    breach = check(budget, monitor, clock.now)

    assert breach.reason == TIMED_OUT_ITL
    assert breach.limit_ms == 5_000.0
    assert breach.observed_ms == pytest.approx(6_000.0)


def test_a_gap_of_exactly_the_stall_budget_is_still_within_it():
    """A gap budget is a duration you are allowed to use. Only passing it
    fails -- unlike a deadline, which is an instant."""
    clock, budget, monitor = setup(itl_ms=5_000.0)
    clock.advance(5.0)
    monitor.token()
    clock.advance(5.0)

    assert check(budget, monitor, clock.now) is None


def test_each_token_resets_the_stall_clock():
    clock, budget, monitor = setup(itl_ms=5_000.0)
    clock.advance(1.0)
    monitor.token()
    for _ in range(10):
        clock.advance(4.0)
        assert check(budget, monitor, clock.now) is None
        monitor.token()


def test_a_stall_outranks_an_expired_total_because_it_explains_more():
    """A provider that went quiet at second 30 of a 600-second budget did
    not run out of time; it stopped."""
    clock, budget, monitor = setup(total_s=100.0, itl_ms=5_000.0)
    clock.advance(10.0)
    monitor.token()
    clock.advance(120.0)

    assert check(budget, monitor, clock.now).reason == TIMED_OUT_ITL


def test_a_budget_that_does_not_enforce_itl_never_reports_a_stall():
    clock, budget, monitor = setup(enforce_itl=False, total_s=300.0)
    clock.advance(1.0)
    monitor.token()
    clock.advance(200.0)

    assert check(budget, monitor, clock.now) is None


# ---- 3. TOTAL deadline ---------------------------------------------------


def test_a_steady_stream_that_overruns_is_a_total_timeout():
    clock, budget, monitor = setup(total_s=30.0, itl_ms=5_000.0)
    clock.advance(1.0)
    monitor.token()
    for _ in range(20):
        clock.advance(2.0)
        monitor.token()

    breach = check(budget, monitor, clock.now)

    assert breach.reason == TIMED_OUT_TOTAL
    assert breach.limit_ms == 30_000.0


def test_the_total_deadline_is_inclusive_of_its_own_instant():
    # A generous stall budget, so this test is about the total deadline
    # and not about a stall that would fire first.
    clock, budget, monitor = setup(total_s=30.0, itl_ms=90_000.0)
    clock.advance(1.0)
    monitor.token()

    clock.advance(28.999)
    assert check(budget, monitor, clock.now) is None

    clock.advance(0.001)
    assert check(budget, monitor, clock.now).reason == TIMED_OUT_TOTAL


# ---- the read window -----------------------------------------------------


def test_before_a_first_token_a_read_may_block_for_the_prefill_window():
    clock, budget, monitor = setup(ttft_s=60.0, total_s=300.0)

    assert read_timeout_seconds(budget, monitor, clock.now) == pytest.approx(60.0)


def test_the_prefill_window_shrinks_as_it_is_consumed():
    clock, budget, monitor = setup(ttft_s=60.0)
    clock.advance(45.0)

    assert read_timeout_seconds(budget, monitor, clock.now) == pytest.approx(15.0)


def test_after_a_first_token_a_read_may_block_only_for_the_stall_budget():
    """Otherwise a stall would not surface until the socket's own timeout,
    which is the one-number failure this brief exists to remove."""
    clock, budget, monitor = setup(total_s=600.0, itl_ms=5_000.0)
    clock.advance(1.0)
    monitor.token()

    assert read_timeout_seconds(budget, monitor, clock.now) == pytest.approx(5.0)


def test_the_read_window_never_outlives_the_whole_call():
    clock, budget, monitor = setup(total_s=30.0, itl_ms=90_000.0)
    clock.advance(1.0)
    monitor.token()

    assert read_timeout_seconds(budget, monitor, clock.now) == pytest.approx(29.0)


def test_a_non_streaming_budget_reads_for_whatever_is_left():
    clock, budget, monitor = setup(total_s=300.0, enforce_itl=False)
    clock.advance(1.0)
    monitor.token()

    assert read_timeout_seconds(budget, monitor, clock.now) == pytest.approx(299.0)


def test_the_read_window_is_never_negative():
    clock, budget, monitor = setup(ttft_s=10.0, total_s=10.0)
    clock.advance(500.0)

    assert read_timeout_seconds(budget, monitor, clock.now) == 0.0


# ---- supervise -----------------------------------------------------------


def token_line(text: str = "hi") -> dict:
    return {"response": text}


def is_token(chunk) -> bool:
    return bool(chunk.get("response"))


def run(chunks, clock, budget, monitor, **kwargs):
    return list(
        supervise(chunks, budget, monitor, clock, is_token=is_token, **kwargs)
    )


def test_a_healthy_stream_passes_every_chunk_through_untouched():
    clock, budget, monitor = setup()

    def chunks():
        for _ in range(4):
            clock.advance(1.0)
            yield token_line()

    assert run(chunks(), clock, budget, monitor) == [token_line()] * 4
    assert monitor.token_count == 4


def test_a_chunk_carrying_no_text_does_not_reset_the_stall_clock():
    """An Ollama `done` frame is not a token. Counting it would hide a
    stall behind a heartbeat that carries nothing."""
    clock, budget, monitor = setup(itl_ms=5_000.0)

    def chunks():
        clock.advance(1.0)
        yield token_line()
        clock.advance(4.0)
        yield {"response": "", "done": True}
        clock.advance(4.0)
        yield token_line()

    with pytest.raises(DeadlineExceeded) as caught:
        run(chunks(), clock, budget, monitor)

    assert caught.value.event.reason == TIMED_OUT_ITL


def test_a_late_token_does_not_rescue_a_stream_that_already_stalled():
    """Checked before the arrival is recorded, or the token would reset
    the clock that had already failed."""
    clock, budget, monitor = setup(itl_ms=5_000.0)

    def chunks():
        clock.advance(1.0)
        yield token_line()
        clock.advance(60.0)
        yield token_line()

    with pytest.raises(DeadlineExceeded) as caught:
        run(chunks(), clock, budget, monitor)

    assert caught.value.event.reason == TIMED_OUT_ITL


def test_a_stream_that_ends_after_the_total_deadline_still_fails():
    clock, budget, monitor = setup(total_s=10.0, itl_ms=90_000.0)

    def chunks():
        clock.advance(1.0)
        yield token_line()
        clock.advance(60.0)
        yield token_line()

    with pytest.raises(DeadlineExceeded) as caught:
        run(chunks(), clock, budget, monitor)

    assert caught.value.event.reason == TIMED_OUT_TOTAL


def test_a_stream_that_produces_nothing_at_all_fails_on_ttft():
    clock, budget, monitor = setup(ttft_s=30.0)

    def chunks():
        clock.advance(45.0)
        yield {"response": "", "done": True}

    with pytest.raises(DeadlineExceeded) as caught:
        run(chunks(), clock, budget, monitor)

    assert caught.value.event.reason == TIMED_OUT_TTFT


def test_an_empty_stream_that_ends_late_is_caught_after_the_loop():
    clock, budget, monitor = setup(ttft_s=30.0)
    clock.advance(45.0)

    with pytest.raises(DeadlineExceeded) as caught:
        run(iter(()), clock, budget, monitor)

    assert caught.value.event.reason == TIMED_OUT_TTFT


def test_an_empty_stream_that_ends_in_time_is_not_a_timeout():
    """Nothing arrived, but nothing was owed yet. Whether an empty answer
    is acceptable is the verifier's question, not this module's."""
    clock, budget, monitor = setup(ttft_s=30.0)

    assert run(iter(()), clock, budget, monitor) == []


def test_the_default_token_predicate_is_plain_truthiness():
    clock, budget, monitor = setup()

    def chunks():
        clock.advance(1.0)
        yield "text"
        clock.advance(1.0)
        yield ""

    assert list(supervise(chunks(), budget, monitor, clock)) == ["text", ""]
    assert monitor.token_count == 1


# ---- the structured event ------------------------------------------------


def test_a_breach_records_everything_needed_to_explain_it():
    clock, budget, monitor = setup(itl_ms=5_000.0)

    def chunks():
        clock.advance(1.0)
        yield token_line()
        clock.advance(30.0)
        yield token_line()

    with pytest.raises(DeadlineExceeded) as caught:
        run(
            chunks(), clock, budget, monitor,
            provider_id="ollama.local", capability="reasoning",
        )

    event = caught.value.event
    assert event.provider_id == "ollama.local"
    assert event.capability == "reasoning"
    assert event.reason in TIMEOUTS
    assert event.budget["itl_ms"] == 5_000.0
    assert event.budget["derivation"]["request_class"] == ""
    assert event.observation["token_count"] == 1
    assert event.observation["ttft_ms"] == pytest.approx(1_000.0)
    assert event.overran_by_ms == pytest.approx(25_000.0)


def test_the_event_reports_itself_as_plain_json_shaped_data():
    import json

    event = TimeoutEvent(
        reason=TIMED_OUT_TTFT, limit_ms=1000.0, observed_ms=2500.0,
        provider_id="p", capability="reasoning",
    )

    assert json.dumps(event.as_dict())
    assert event.as_dict()["overran_by_ms"] == 1500.0


@pytest.mark.parametrize(
    "reason,words",
    [
        (TIMED_OUT_TTFT, "no first token"),
        (TIMED_OUT_ITL, "stopped producing"),
        (TIMED_OUT_TOTAL, "did not finish"),
    ],
)
def test_each_reason_reads_as_a_different_sentence(reason, words):
    """Three distinct causes must not render as one message."""
    event = TimeoutEvent(reason=reason, limit_ms=5_000.0, observed_ms=7_500.0)

    assert words in event.summary
    assert "7.5s" in event.summary
    assert "5.0s" in event.summary


def test_the_exception_message_is_the_summary():
    event = TimeoutEvent(reason=TIMED_OUT_ITL, limit_ms=1000.0, observed_ms=4000.0)

    assert str(DeadlineExceeded(event)) == event.summary


# ---- replay determinism --------------------------------------------------


def test_the_same_stream_replayed_produces_an_identical_breach():
    def once():
        clock, budget, monitor = setup(itl_ms=5_000.0)

        def chunks():
            clock.advance(2.0)
            yield token_line()
            clock.advance(40.0)
            yield token_line()

        with pytest.raises(DeadlineExceeded) as caught:
            run(chunks(), clock, budget, monitor, provider_id="p")
        return caught.value.event.as_dict()

    assert once() == once()
