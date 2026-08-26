"""Tonight's launch rescue — transient-provider recovery and Founder-facing
error hygiene.

Two separate claims, proven against the real shipped classes:

1. `GeminiProvider` retries a *transient* HTTP condition (503 high demand,
   429 rate limit, 5xx) a bounded number of times, and never retries a
   condition that repeating cannot fix (400, 404, a timeout).
2. No raw HTTP status, provider prose, URL, or exception text ever reaches
   the sentence a founder reads — while the full diagnostic survives on
   `ExecutionStatus.errors` for whoever is debugging.

No real network call anywhere: the transport is the same injected seam
`test_gemini_provider`-style tests already use.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kalpavriksha_desktop as kd  # noqa: E402

from master_agent.missions.execution_status import ExecutionStatus  # noqa: E402
from master_agent.providers.gemini import (  # noqa: E402
    DEFAULT_MAX_ATTEMPTS,
    GeminiProvider,
)
from master_agent.providers.response import REJECTED, SUCCEEDED  # noqa: E402
from master_agent.providers.transport import (  # noqa: E402
    HttpResponse,
    TransportTimeout,
    TransportUnavailable,
)
from tests.test_kalpavriksha_desktop_mission_bridge import (  # noqa: E402
    _FakeFounderState,
    _FakeMissionControl,
    _FakeMissionService,
    _FakeObjective,
    _FakeOutcome,
    _FakeRuntime,
)


# ---- transport doubles ----------------------------------------------------


BUSY_503 = HttpResponse(
    status=503,
    body=(
        '{"error": {"code": 503, "message": "This model is currently '
        'experiencing high demand. Please try again later.", '
        '"status": "UNAVAILABLE"}}'
    ),
)
GOOD = HttpResponse(
    status=200,
    body='{"candidates": [{"content": {"parts": [{"text": "hello"}]}}]}',
)
BAD_REQUEST = HttpResponse(
    status=400, body='{"error": {"code": 400, "message": "Invalid argument"}}'
)


class ScriptedTransport:
    """Returns each scripted response in turn; the last one repeats. A
    scripted `Exception` instance is raised rather than returned."""

    def __init__(self, *responses) -> None:
        self._responses = list(responses)
        self.calls = 0

    def post_json(self, url, payload, timeout):
        self.calls += 1
        item = (
            self._responses.pop(0) if len(self._responses) > 1 else self._responses[0]
        )
        if isinstance(item, Exception):
            raise item
        return item

    def get(self, url, timeout):  # pragma: no cover — unused here
        raise NotImplementedError

    def stream_json(self, url, payload, timeout):  # pragma: no cover — unused
        raise NotImplementedError


def provider(*responses, max_attempts=DEFAULT_MAX_ATTEMPTS):
    slept: list[float] = []
    transport = ScriptedTransport(*responses)
    gemini = GeminiProvider(
        api_key="test-key",
        transport=transport,
        max_attempts=max_attempts,
        sleep=slept.append,  # never actually sleeps in tests
    )
    return gemini, transport, slept


# ---- 1. transient retry ---------------------------------------------------


def test_a_transient_503_is_retried_and_a_later_success_is_returned():
    gemini, transport, slept = provider(BUSY_503, GOOD)

    result = gemini.complete("plan something")

    assert result.ok
    assert result.outcome == SUCCEEDED
    assert result.text == "hello"
    assert transport.calls == 2
    assert len(slept) == 1  # one backoff, between the two attempts


def test_retries_are_bounded_and_the_last_failure_is_returned():
    gemini, transport, slept = provider(BUSY_503)

    result = gemini.complete("plan something")

    assert not result.ok
    assert result.outcome == REJECTED
    assert transport.calls == DEFAULT_MAX_ATTEMPTS  # never unbounded
    assert len(slept) == DEFAULT_MAX_ATTEMPTS - 1


def test_a_429_rate_limit_is_also_treated_as_transient():
    rate_limited = HttpResponse(
        status=429, body='{"error": {"message": "Resource has been exhausted"}}'
    )
    gemini, transport, _slept = provider(rate_limited, GOOD)

    assert gemini.complete("plan").ok
    assert transport.calls == 2


def test_a_non_transient_4xx_is_never_retried():
    """Repeating a malformed request cannot change its answer — and doing
    so would burn a founder's free-tier quota for nothing."""
    gemini, transport, slept = provider(BAD_REQUEST)

    result = gemini.complete("plan something")

    assert not result.ok
    assert transport.calls == 1
    assert slept == []


def test_a_timeout_is_not_retried():
    """The deadline that just expired is the caller's own budget; spending
    it again would multiply a wait the founder already found too long."""
    gemini, transport, slept = provider(TransportTimeout("no answer within 120s"))

    result = gemini.complete("plan something")

    assert not result.ok
    assert transport.calls == 1
    assert slept == []


def test_an_unreachable_endpoint_is_retried_then_reported():
    gemini, transport, _slept = provider(TransportUnavailable("connection refused"))

    result = gemini.complete("plan something")

    assert not result.ok
    assert transport.calls == DEFAULT_MAX_ATTEMPTS


def test_success_on_the_first_attempt_is_unchanged():
    """The ordinary path must not gain latency or an extra call."""
    gemini, transport, slept = provider(GOOD)

    result = gemini.complete("plan something")

    assert result.ok
    assert result.text == "hello"
    assert transport.calls == 1
    assert slept == []


# ---- 2. Founder-facing error hygiene -------------------------------------

RAW_503 = (
    "no plan: the provider could not answer (HTTP 503: This model is "
    "currently experiencing high demand. Please try again later.)"
)

#: Everything a founder must never be shown.
LEAKS = (
    "HTTP", "503", "429", "500", "502", "504",
    "http://", "https://", "Traceback", "Exception",
    "generativelanguage", "googleapis", "gemini", "Gemini",
    "provider", "urllib", "playwright", "Playwright",
)


def _assert_clean(sentence: str) -> None:
    for leak in LEAKS:
        assert leak not in sentence, f"founder-facing text leaked {leak!r}: {sentence!r}"


def test_a_503_refusal_becomes_a_clean_founder_sentence():
    sentence = kd._founder_refusal_sentence(RAW_503)
    _assert_clean(sentence)
    assert "temporarily busy" in sentence.lower()


@pytest.mark.parametrize(
    "raw",
    [
        RAW_503,
        "no plan: the provider could not answer (HTTP 429: Resource exhausted)",
        "no plan: the provider could not answer (no answer within 120s)",
        "no plan: the provider could not answer (connection refused (could not reach https://generativelanguage.googleapis.com/v1beta))",
        "no plan: the provider could not answer (HTTP 401: API key not valid)",
        "no plan: nothing is registered to plan with",
        "no plan: the available capabilities cannot achieve this objective",
        "something nobody has ever seen before",
    ],
)
def test_no_refusal_reason_ever_leaks_raw_text_to_the_founder(raw):
    _assert_clean(kd._founder_refusal_sentence(raw))


@pytest.mark.parametrize(
    "raw",
    [
        "failed to open browser session: BrowserType.launch: Executable doesn't exist at "
        "C:\\Program Files\\Kalpavriksha\\_internal\\playwright\\driver\\package\\.local-browsers\\"
        "chromium_headless_shell-1223\\chrome-headless-shell.exe",
        "navigate timed out: Page.goto: Timeout 5000ms exceeded.",
        "approval denied: founder approval required",
        "HTTP 503: upstream busy",
        "some unmapped executive error",
    ],
)
def test_no_execution_failure_ever_leaks_raw_text_to_the_founder(raw):
    _assert_clean(kd._founder_failure_sentence(raw))


def test_the_full_diagnostic_survives_for_developers_even_though_the_founder_sees_a_sentence():
    """Hygiene must not become amnesia — the raw reason still has to be
    reachable by whoever is debugging."""
    mission_service = _FakeMissionService(
        _FakeOutcome(accepted=False, refusal=type("R", (), {"reason": RAW_503})())
    )
    runtime = _FakeRuntime()
    mission_control = _FakeMissionControl([_FakeObjective()], _FakeFounderState())
    status = ExecutionStatus()

    result = kd._submit_objective(
        mission_service, runtime, mission_control, status, "do something"
    )

    _assert_clean(result["reply"])
    assert runtime.run_once_calls == 0
    # ...but the developer-facing diagnostic is intact:
    assert any("503" in err for err in status.errors)


def test_a_successful_mission_reply_is_unchanged_by_the_hygiene_layer():
    mission_service = _FakeMissionService(
        _FakeOutcome(accepted=True, objective_id="obj-ok")
    )
    runtime = _FakeRuntime()
    mission_control = _FakeMissionControl(
        [_FakeObjective(complete=True)],
        _FakeFounderState(
            progress=1.0,
            result={"url": "https://example.com/", "title": "Example Domain"},
        ),
    )
    status = ExecutionStatus()

    result = kd._submit_objective(
        mission_service, runtime, mission_control, status, "open chrome"
    )

    assert result["reply"] == (
        'Done — the page at https://example.com/ loaded with title "Example Domain".'
    )
