"""MB038 Step 6 — streaming transport and stream measurement.

The monitor measures; it never judges. Nothing in this file asserts that a
call should have failed, because deciding that is Step 7's job and the
separation is the point.
"""
from __future__ import annotations

import json

import pytest

from master_agent.providers.stream import StreamMonitor, StreamObservation
from master_agent.providers.transport import (
    DEFAULT_TIMEOUT_SECONDS,
    Transport,
    TransportUnavailable,
    UrllibTransport,
)


class FakeClock:
    """A clock that only moves when a test says so. No wall clock anywhere
    in these tests, so timing assertions are exact rather than flaky."""

    def __init__(self, start: float = 100.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> float:
        self.now += seconds
        return self.now


def monitor(start: float = 100.0) -> tuple[StreamMonitor, FakeClock]:
    clock = FakeClock(start)
    return StreamMonitor(clock=clock), clock


# ---- nothing arrived -----------------------------------------------------


def test_a_stream_that_never_produces_reports_ttft_as_unknown():
    """`None`, never `0.0`. Zero would read as instant, which is the
    opposite of what happened -- this is the prefill-stall signature."""
    subject, clock = monitor()
    clock.advance(300.0)

    observation = subject.observe()

    assert observation.ttft_ms is None
    assert observation.started is False
    assert observation.token_count == 0
    assert observation.elapsed_ms == 300_000.0


def test_decode_time_is_unknown_when_nothing_ever_arrived():
    """With no first token there is no boundary between thinking and
    generating, and inventing one would blame the wrong phase."""
    subject, clock = monitor()
    clock.advance(60.0)

    assert subject.observe().decode_ms is None


def test_silence_is_measured_from_the_start_before_any_token():
    subject, clock = monitor()

    assert subject.silence_ms(clock.advance(45.0)) == 45_000.0


# ---- first token ---------------------------------------------------------


def test_ttft_measures_the_whole_wait_the_caller_experienced():
    subject, clock = monitor()
    clock.advance(90.0)
    subject.token()

    observation = subject.observe()

    assert observation.ttft_ms == 90_000.0
    assert observation.started is True


def test_one_token_produces_no_gap_to_report():
    """A single token has nothing to be spaced from. `0.0` would claim a
    cadence nobody observed."""
    subject, clock = monitor()
    clock.advance(10.0)
    subject.token()

    observation = subject.observe()

    assert observation.max_gap_ms is None
    assert observation.observed_itl_ms is None
    assert observation.token_count == 1


def test_silence_is_measured_from_the_last_token_once_one_arrives():
    subject, clock = monitor()
    clock.advance(10.0)
    subject.token()

    assert subject.silence_ms(clock.advance(4.0)) == 4_000.0


# ---- cadence -------------------------------------------------------------


def test_the_largest_silence_between_tokens_is_kept():
    subject, clock = monitor()
    clock.advance(5.0)
    subject.token()
    clock.advance(0.1)
    subject.token()
    clock.advance(2.5)
    subject.token()
    clock.advance(0.1)
    subject.token()

    assert subject.observe().max_gap_ms == pytest.approx(2500.0)


def test_mean_cadence_is_measured_across_the_gaps_not_the_tokens():
    """Three tokens are two gaps. Dividing by three would understate the
    cadence by a third."""
    subject, clock = monitor()
    clock.advance(5.0)
    subject.token()
    clock.advance(1.0)
    subject.token()
    clock.advance(1.0)
    subject.token()

    assert subject.observe().observed_itl_ms == pytest.approx(1000.0)


def test_decode_time_excludes_the_prefill_wait():
    subject, clock = monitor()
    clock.advance(80.0)
    subject.token()
    clock.advance(20.0)
    subject.token()

    observation = subject.observe()

    assert observation.ttft_ms == 80_000.0
    assert observation.decode_ms == pytest.approx(20_000.0)


def test_a_chunk_carrying_several_tokens_counts_as_several():
    subject, clock = monitor()
    clock.advance(1.0)
    subject.token(count=7)

    assert subject.observe().token_count == 7


def test_a_zero_or_negative_count_still_counts_as_one_arrival():
    """Something arrived. Recording nothing would make the stream look
    silent while it was in fact producing."""
    subject, clock = monitor()
    clock.advance(1.0)
    subject.token(count=0)

    assert subject.observe().token_count == 1


# ---- completion ----------------------------------------------------------


def test_completion_is_distinct_from_merely_stopping():
    subject, clock = monitor()
    clock.advance(1.0)
    subject.token()

    assert subject.observe().completed is False

    subject.complete()
    assert subject.observe().completed is True


def test_observing_at_a_supplied_instant_reads_no_clock():
    """Replay hands in the instant; the monitor must not consult its own
    clock and produce a different answer."""
    subject, clock = monitor()
    clock.advance(10.0)
    subject.token()
    clock.advance(500.0)

    frozen = subject.observe(now=clock.now - 400.0)

    assert frozen.elapsed_ms == pytest.approx(110_000.0)


def test_the_observation_is_frozen_and_json_shaped():
    from dataclasses import FrozenInstanceError

    subject, clock = monitor()
    clock.advance(2.0)
    subject.token()
    observation = subject.observe()

    with pytest.raises(FrozenInstanceError):
        observation.token_count = 99  # type: ignore[misc]

    reported = observation.as_dict()
    assert set(reported) == {
        "ttft_ms",
        "elapsed_ms",
        "decode_ms",
        "token_count",
        "max_gap_ms",
        "observed_itl_ms",
        "completed",
    }
    assert json.dumps(reported)


def test_an_empty_observation_is_a_usable_value():
    assert StreamObservation().started is False
    assert StreamObservation().decode_ms is None


def test_a_monitor_can_be_told_when_the_request_was_issued():
    """The executor may have started timing before the adapter did."""
    clock = FakeClock(100.0)
    subject = StreamMonitor(clock=clock, started_at=60.0)
    clock.advance(0.0)
    subject.token()

    assert subject.observe().ttft_ms == pytest.approx(40_000.0)


# ---- the live accessors an enforcer reads mid-stream ---------------------


def test_elapsed_is_readable_without_taking_a_full_observation():
    """An enforcer checks this on every chunk; building a frozen
    observation each time would be waste."""
    subject, clock = monitor()

    assert subject.elapsed_ms(clock.advance(12.0)) == 12_000.0


def test_started_is_readable_live_so_an_enforcer_knows_which_deadline_applies():
    subject, clock = monitor()

    assert subject.started is False
    clock.advance(1.0)
    subject.token()
    assert subject.started is True


def test_token_count_is_readable_live():
    subject, clock = monitor()
    clock.advance(1.0)
    subject.token()
    subject.token()

    assert subject.token_count == 2


def test_token_returns_the_instant_it_recorded():
    """The enforcer reuses it rather than reading the clock a second time
    and getting a slightly different answer."""
    subject, clock = monitor()
    expected = clock.advance(3.0)

    assert subject.token() == expected


# ---- the transport contract ---------------------------------------------


def test_streaming_is_part_of_the_transport_protocol():
    assert hasattr(Transport, "stream_json")
    assert callable(UrllibTransport.stream_json)


def test_the_real_transport_still_refuses_a_non_http_url():
    """The `file://` guard must cover the streaming path too -- a hole in
    one method is a hole."""
    stream = UrllibTransport().stream_json("file:///etc/passwd", {}, timeout=1.0)

    with pytest.raises(TransportUnavailable) as caught:
        next(stream)

    assert "refusing non-http URL" in str(caught.value)


def test_the_streaming_timeout_defaults_to_the_same_socket_value():
    """Mechanism, not policy: the adapter supplies the real budget."""
    import inspect

    signature = inspect.signature(UrllibTransport.stream_json)
    assert signature.parameters["timeout"].default == DEFAULT_TIMEOUT_SECONDS
