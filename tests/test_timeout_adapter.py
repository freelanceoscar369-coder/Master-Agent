"""MB038 Step 8 — the adapter under a CallBudget.

Every test drives a fake clock through `on_chunk`, so a stall is produced
by advancing time rather than by waiting. No sleeps, no wall clock.
"""
from __future__ import annotations

import json

import pytest

from master_agent.providers.budget import CallBudget
from master_agent.providers.ollama import OllamaProvider, _carries_text
from master_agent.providers.response import (
    MALFORMED,
    SUCCEEDED,
    TIMED_OUT_ITL,
    TIMED_OUT_TOTAL,
    TIMED_OUT_TTFT,
    UNAVAILABLE,
)
from master_agent.providers.transport import TransportTimeout, TransportUnavailable
from tests.broker_test_support import FakeTransport

START = 500.0


class FakeClock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def frame(text: str = "hi", done: bool = False, **extra) -> str:
    payload = {"model": "test-model", "response": text, "done": done}
    payload.update(extra)
    return json.dumps(payload)


def budget(ttft_s: float = 60.0, total_s: float = 300.0, itl_ms: float = 5_000.0,
           enforce_itl: bool = True) -> CallBudget:
    ttft_s = min(ttft_s, total_s)
    return CallBudget(
        total_deadline=START + total_s,
        ttft_deadline=START + ttft_s,
        itl_ms=itl_ms,
        enforce_itl=enforce_itl,
        total_ms=total_s * 1000,
        ttft_ms=ttft_s * 1000,
    )


def provider_with(stream, clock, on_chunk=None) -> OllamaProvider:
    return OllamaProvider(
        model="test-model",
        transport=FakeTransport(stream=stream, on_chunk=on_chunk),
        clock=clock,
    )


# ---- the happy path ------------------------------------------------------


def test_a_budgeted_call_streams_and_reassembles_the_whole_answer():
    clock = FakeClock()
    stream = [frame("Hello "), frame("world"), frame("", done=True, eval_count=2)]
    provider = provider_with(stream, clock, on_chunk=lambda _i: clock.advance(1.0))

    result = provider.complete("q", budget=budget())

    assert result.outcome == SUCCEEDED
    assert result.text == "Hello world"
    assert result.response.completion_tokens == 2


def test_a_budgeted_call_asks_the_daemon_to_stream():
    clock = FakeClock()
    provider = provider_with([frame("x", done=True)], clock,
                             on_chunk=lambda _i: clock.advance(1.0))

    provider.complete("q", budget=budget())

    _url, payload, _timeout = provider._transport.streamed[0]
    assert payload["stream"] is True


def test_an_unbudgeted_call_still_takes_the_single_request_path():
    """The pre-MB038 path survives for callers that have no budget yet."""
    clock = FakeClock()
    provider = OllamaProvider(
        model="test-model", transport=FakeTransport(), clock=clock
    )

    result = provider.complete("q")

    assert result.ok is True
    assert provider._transport.posts, "it did not use the blocking path"
    assert provider._transport.streamed == []


def test_the_observation_and_budget_travel_with_a_successful_result():
    clock = FakeClock()
    provider = provider_with([frame("a"), frame("", done=True)], clock,
                             on_chunk=lambda _i: clock.advance(2.0))

    result = provider.complete("q", budget=budget())

    assert result.detail["observation"]["token_count"] == 1
    assert result.detail["observation"]["ttft_ms"] == pytest.approx(2_000.0)
    assert result.detail["budget"]["itl_ms"] == 5_000.0


# ---- the three timeouts --------------------------------------------------


def test_a_stream_that_never_produces_fails_on_ttft():
    clock = FakeClock()
    stream = [frame("", done=True)]
    provider = provider_with(stream, clock, on_chunk=lambda _i: clock.advance(90.0))

    result = provider.complete("q", budget=budget(ttft_s=60.0))

    assert result.outcome == TIMED_OUT_TTFT
    assert result.detail["timeout"]["limit_ms"] == 60_000.0
    assert "no first token" in result.error


def test_a_stream_that_goes_quiet_fails_on_itl_not_on_total():
    """A provider that stopped at second 10 of a 300-second budget did not
    run out of time; it stalled."""
    clock = FakeClock()
    gaps = [1.0, 60.0]
    provider = provider_with(
        [frame("a"), frame("b")], clock,
        on_chunk=lambda i: clock.advance(gaps[i]),
    )

    result = provider.complete("q", budget=budget(itl_ms=5_000.0))

    assert result.outcome == TIMED_OUT_ITL
    assert result.detail["timeout"]["limit_ms"] == 5_000.0


def test_a_steady_stream_that_overruns_fails_on_total():
    clock = FakeClock()
    provider = provider_with(
        [frame("a")] * 8, clock, on_chunk=lambda _i: clock.advance(4.0)
    )

    result = provider.complete("q", budget=budget(total_s=20.0, itl_ms=90_000.0))

    assert result.outcome == TIMED_OUT_TOTAL


def test_the_three_timeouts_are_distinguishable_from_one_another():
    """`TIMED_OUT` named three failures with three different fixes."""
    assert len({TIMED_OUT_TTFT, TIMED_OUT_ITL, TIMED_OUT_TOTAL}) == 3


def test_a_timeout_carries_the_budget_and_what_was_observed():
    clock = FakeClock()
    gaps = [1.0, 60.0]
    provider = provider_with(
        [frame("a"), frame("b")], clock, on_chunk=lambda i: clock.advance(gaps[i])
    )

    result = provider.complete("q", budget=budget(itl_ms=5_000.0))

    event = result.detail["timeout"]
    assert event["provider_id"] == "ollama.local"
    assert event["capability"] == "generate_text"
    assert event["observation"]["token_count"] == 1
    assert event["budget"]["itl_ms"] == 5_000.0
    assert event["overran_by_ms"] == pytest.approx(55_000.0)


def test_a_done_frame_does_not_reset_the_stall_clock():
    """It carries no text. Counting it would let a stalled stream look
    alive right up to the moment it ends."""
    assert _carries_text({"response": "hi"}) is True
    assert _carries_text({"response": "", "done": True}) is False
    assert _carries_text("not a dict") is False


# ---- transport failures --------------------------------------------------


def test_a_socket_timeout_before_any_token_is_reported_as_a_ttft_timeout():
    """The socket gave up before the enforcer did; which deadline that was
    is still knowable."""
    clock = FakeClock()
    provider = provider_with(TransportTimeout("no answer within 60s"), clock)

    result = provider.complete("q", budget=budget())

    assert result.outcome == TIMED_OUT_TTFT
    assert result.detail["observation"]["ttft_ms"] is None


def test_a_socket_timeout_after_a_token_is_reported_as_a_stall():
    clock = FakeClock()
    stream = [frame("a"), TransportTimeout("no answer within 5s")]
    provider = provider_with(stream, clock, on_chunk=lambda _i: clock.advance(1.0))

    result = provider.complete("q", budget=budget())

    assert result.outcome == TIMED_OUT_ITL
    assert result.detail["observation"]["token_count"] == 1


def test_a_dead_daemon_on_the_streaming_path_still_says_where_it_looked():
    clock = FakeClock()
    provider = provider_with(TransportUnavailable("connection refused"), clock)

    result = provider.complete("q", budget=budget())

    assert result.outcome == UNAVAILABLE
    assert "is Ollama running at" in result.error


def test_a_non_json_line_in_the_stream_is_malformed_not_a_crash():
    clock = FakeClock()
    provider = provider_with(["{not json"], clock,
                             on_chunk=lambda _i: clock.advance(1.0))

    result = provider.complete("q", budget=budget())

    assert result.outcome == MALFORMED


# ---- no retry ------------------------------------------------------------


def test_the_streaming_path_never_retries_a_transport_failure():
    clock = FakeClock()
    provider = provider_with(TransportUnavailable("refused"), clock)

    provider.complete("q", budget=budget())

    assert len(provider._transport.streamed) == 1


def test_the_read_window_handed_to_the_transport_is_the_prefill_window():
    """Not the configured `timeout_seconds`. That number no longer decides
    how long a budgeted call may wait."""
    clock = FakeClock()
    provider = OllamaProvider(
        model="test-model",
        transport=FakeTransport(stream=[frame("a", done=True)],
                                on_chunk=lambda _i: clock.advance(1.0)),
        clock=clock,
        timeout_seconds=7.0,
    )

    provider.complete("q", budget=budget(ttft_s=45.0))

    _url, _payload, timeout = provider._transport.streamed[0]
    assert timeout == pytest.approx(45.0)
    assert timeout != 7.0
