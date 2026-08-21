"""Build 2 — the Gemini provider, Kalpavriksha's first cloud reasoning
execution path (Founder decision: provider search closed).

Mirrors `test_ollama_provider.py`'s method: everything here runs against a
scripted transport. The property under test is *what this provider does
with what the API says*, never whether the network works.
"""
from __future__ import annotations

import json

import pytest

from master_agent.plugins.base import ModelProvider
from master_agent.providers.gemini import (
    DEFAULT_MODEL,
    GEMINI_PROVIDER_ID,
    NO_API_KEY,
    GeminiProvider,
)
from master_agent.providers.ollama import ProviderExecutionFailed
from master_agent.providers.response import (
    MALFORMED,
    REJECTED,
    SUCCEEDED,
    TIMED_OUT,
    UNAVAILABLE,
)
from master_agent.providers.transport import (
    HttpResponse,
    TransportTimeout,
    TransportUnavailable,
)


class FakeTransport:
    """Scripted HTTP for `post_json` only — the one method
    `GeminiProvider.complete()` calls."""

    def __init__(self, response=None) -> None:
        self._response = response if response is not None else _ok()
        self.posts: list[tuple[str, dict, float]] = []

    def post_json(self, url: str, payload: dict, timeout: float) -> HttpResponse:
        self.posts.append((url, payload, timeout))
        if isinstance(self._response, Exception):
            raise self._response
        return self._response

    def get(self, url: str, timeout: float) -> HttpResponse:  # pragma: no cover
        raise AssertionError("GeminiProvider never calls transport.get()")

    def stream_json(self, url, payload, timeout):  # pragma: no cover
        raise AssertionError("GeminiProvider never streams")


def _ok(text: str = "hello from gemini", prompt_tokens: int = 5, completion_tokens: int = 3) -> HttpResponse:
    return HttpResponse(
        200,
        json.dumps(
            {
                "candidates": [
                    {
                        "content": {"parts": [{"text": text}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": prompt_tokens,
                    "candidatesTokenCount": completion_tokens,
                },
            }
        ),
    )


def _error(status: int, message: str) -> HttpResponse:
    return HttpResponse(
        status, json.dumps({"error": {"code": status, "message": message}})
    )


# ---- construction / identity -------------------------------------------


def test_it_is_a_model_provider():
    assert isinstance(GeminiProvider(api_key="k"), ModelProvider)


def test_provider_id_matches_the_catalog_id():
    from master_agent.ai_infrastructure.catalog import BY_PROVIDER_ID

    assert GEMINI_PROVIDER_ID == "gemini.api"
    assert BY_PROVIDER_ID["gemini.api"].provider_id == GEMINI_PROVIDER_ID


def test_default_model_is_documented_and_used():
    provider = GeminiProvider(api_key="k")
    assert provider.model == DEFAULT_MODEL


def test_manifest_names_the_provider_id():
    provider = GeminiProvider(api_key="k", provider_id="gemini.api")
    assert provider.manifest.name == "gemini.api"


# ---- missing credential --------------------------------------------------


def test_missing_api_key_is_reported_as_unavailable_without_a_network_call():
    transport = FakeTransport()
    provider = GeminiProvider(api_key="", transport=transport)

    result = provider.complete("hello")

    assert result.outcome == UNAVAILABLE
    assert NO_API_KEY in result.error
    assert transport.posts == []  # no doomed call was attempted


def test_availability_reports_missing_key_honestly():
    provider = GeminiProvider(api_key="", transport=FakeTransport())
    availability = provider.availability()

    assert availability.reachable is False
    assert NO_API_KEY in availability.detail


def test_availability_reports_configured_when_key_present():
    provider = GeminiProvider(api_key="real-key", transport=FakeTransport())
    availability = provider.availability()

    assert availability.reachable is True


# ---- successful response --------------------------------------------------


def test_a_successful_call_returns_the_candidate_text():
    transport = FakeTransport(_ok(text="the plan is..."))
    provider = GeminiProvider(api_key="real-key", transport=transport)

    result = provider.complete("plan something harmless")

    assert result.ok is True
    assert result.outcome == SUCCEEDED
    assert result.text == "the plan is..."
    assert result.response.prompt_tokens == 5
    assert result.response.completion_tokens == 3


def test_the_api_key_travels_in_the_url_never_in_the_body():
    transport = FakeTransport(_ok())
    provider = GeminiProvider(api_key="super-secret", transport=transport)

    provider.complete("hi")

    url, payload, _ = transport.posts[0]
    assert "super-secret" in url
    assert "super-secret" not in json.dumps(payload)


# ---- Gemini 3.x sampling-parameter compatibility (migration from 2.5) -----


def test_temperature_top_p_top_k_are_stripped_before_sending():
    """Gemini 3.x ignores custom values for these silently; sending them
    anyway would be misleading about what the call actually did."""
    transport = FakeTransport(_ok())
    provider = GeminiProvider(api_key="k", transport=transport)

    provider.complete("hi", options={"temperature": 0.7, "top_p": 0.9, "top_k": 40})

    _, payload, _ = transport.posts[0]
    assert "generationConfig" not in payload


def test_frequency_and_presence_penalty_are_stripped_before_sending():
    """Gemini 3.x errors outright on these two rather than ignoring them —
    stripped here so a caller's request is never rejected for a
    constraint it had no way to know about."""
    transport = FakeTransport(_ok())
    provider = GeminiProvider(api_key="k", transport=transport)

    provider.complete(
        "hi", options={"frequency_penalty": 0.5, "presence_penalty": 0.5}
    )

    _, payload, _ = transport.posts[0]
    assert "generationConfig" not in payload


def test_a_supported_option_still_reaches_generation_config():
    """Stripping is narrow: this provider still executes, it does not
    decide what a caller may ask for beyond the one documented, verified
    exception."""
    transport = FakeTransport(_ok())
    provider = GeminiProvider(api_key="k", transport=transport)

    provider.complete("hi", options={"maxOutputTokens": 256})

    _, payload, _ = transport.posts[0]
    assert payload["generationConfig"] == {"maxOutputTokens": 256}


def test_generate_returns_plain_text_on_success():
    transport = FakeTransport(_ok(text="ok"))
    provider = GeminiProvider(api_key="k", transport=transport)

    assert provider.generate("hi") == "ok"


def test_generate_raises_on_failure_rather_than_returning_an_apology_as_text():
    provider = GeminiProvider(api_key="", transport=FakeTransport())

    with pytest.raises(ProviderExecutionFailed):
        provider.generate("hi")


# ---- authentication failure ------------------------------------------------


def test_authentication_failure_is_rejected_with_the_api_message():
    transport = FakeTransport(_error(401, "API key not valid"))
    provider = GeminiProvider(api_key="bad-key", transport=transport)

    result = provider.complete("hi")

    assert result.outcome == REJECTED
    assert "API key not valid" in result.error
    assert result.text == ""


# ---- rate limit / quota exhaustion -----------------------------------------


def test_rate_limit_is_reported_as_rejected_with_the_reason():
    transport = FakeTransport(_error(429, "Resource has been exhausted"))
    provider = GeminiProvider(api_key="k", transport=transport)

    result = provider.complete("hi")

    assert result.outcome == REJECTED
    assert "exhausted" in result.error.lower()


def test_quota_exhaustion_never_falls_back_to_a_different_provider():
    """MB033 Rule 5, applied here: a provider never silently substitutes a
    different provider or a fabricated answer."""
    transport = FakeTransport(_error(429, "quota exceeded"))
    provider = GeminiProvider(api_key="k", transport=transport)

    result = provider.complete("hi")

    assert result.ok is False
    assert result.provider_id == GEMINI_PROVIDER_ID


# ---- network / timeout -----------------------------------------------------


def test_a_timeout_is_reported_as_timed_out():
    transport = FakeTransport(TransportTimeout("no answer within 60s"))
    provider = GeminiProvider(api_key="k", transport=transport)

    result = provider.complete("hi")

    assert result.outcome == TIMED_OUT


def test_an_unreachable_endpoint_is_reported_as_unavailable():
    transport = FakeTransport(TransportUnavailable("name resolution failed"))
    provider = GeminiProvider(api_key="k", transport=transport)

    result = provider.complete("hi")

    assert result.outcome == UNAVAILABLE


# ---- malformed / empty response --------------------------------------------


def test_a_non_json_body_is_malformed():
    transport = FakeTransport(HttpResponse(200, "not json"))
    provider = GeminiProvider(api_key="k", transport=transport)

    result = provider.complete("hi")

    assert result.outcome == MALFORMED


def test_json_with_no_candidates_is_malformed():
    transport = FakeTransport(HttpResponse(200, json.dumps({"candidates": []})))
    provider = GeminiProvider(api_key="k", transport=transport)

    result = provider.complete("hi")

    assert result.outcome == MALFORMED


def test_a_result_with_no_readable_text_is_malformed_not_a_silent_empty_success():
    body = json.dumps({"candidates": [{"content": {"parts": []}}]})
    transport = FakeTransport(HttpResponse(200, body))
    provider = GeminiProvider(api_key="k", transport=transport)

    result = provider.complete("hi")

    assert result.outcome == MALFORMED


# ---- bounded retry on transient conditions ------------------------------
#
# The founder hit a real 503 ("This model is currently experiencing high
# demand") mid-mission. These tests pin the policy that answers it: which
# statuses are worth asking again about, how many times, and — just as
# importantly — everything that must NOT be retried, because repeating a
# malformed or unauthorised request cannot change its answer.
#
# Nothing here sleeps. `GeminiProvider` takes `sleep` as an injected seam
# for exactly this reason, the same way `transport` and `clock` already
# are, so the delays are asserted as values rather than waited out.


class SequencedTransport:
    """Scripted responses in order, one per attempt. Raises if asked for
    more attempts than were scripted — an over-eager retry loop fails as a
    loud error rather than by quietly reusing the last response."""

    def __init__(self, *responses) -> None:
        self._responses = list(responses)
        self.posts: list[tuple[str, dict, float]] = []

    def post_json(self, url: str, payload: dict, timeout: float) -> HttpResponse:
        self.posts.append((url, payload, timeout))
        if not self._responses:
            raise AssertionError("the provider attempted more calls than were scripted")
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    def get(self, url, timeout):  # pragma: no cover
        raise AssertionError("GeminiProvider never calls transport.get()")

    def stream_json(self, url, payload, timeout):  # pragma: no cover
        raise AssertionError("GeminiProvider never streams")


class RecordingSleep:
    def __init__(self) -> None:
        self.waited: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.waited.append(seconds)


def _provider(*responses, **kwargs):
    transport = SequencedTransport(*responses)
    slept = RecordingSleep()
    provider = GeminiProvider(
        api_key="k", transport=transport, sleep=slept, **kwargs,
    )
    return provider, transport, slept


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_a_transient_status_is_retried_and_a_later_success_is_returned(status):
    provider, transport, slept = _provider(_error(status, "try again"), _ok("recovered"))

    result = provider.complete("hi")

    assert result.outcome == SUCCEEDED
    assert result.text == "recovered"
    assert len(transport.posts) == 2
    assert slept.waited == [0.6]


def test_retrying_stops_at_the_attempt_cap_and_returns_the_last_failure():
    """Three attempts total — one call plus at most two retries — not
    three retries on top of the first call."""
    provider, transport, slept = _provider(
        _error(503, "busy"), _error(503, "busy"), _error(503, "still busy"),
    )

    result = provider.complete("hi")

    assert len(transport.posts) == 3
    assert result.outcome != SUCCEEDED
    assert slept.waited == [0.6, 1.4], "the documented delays were not used"


def test_no_wait_happens_after_the_final_attempt():
    """A sleep the founder waits through and gains nothing from."""
    provider, transport, slept = _provider(
        _error(503, "busy"), _error(503, "busy"), _error(503, "busy"),
    )
    provider.complete("hi")

    assert len(slept.waited) == len(transport.posts) - 1


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_a_non_transient_client_error_is_never_retried(status):
    """Repeating a malformed or unauthorised request cannot change its
    answer, so the founder must not wait while it is repeated."""
    provider, transport, slept = _provider(_error(status, "no"))

    result = provider.complete("hi")

    assert len(transport.posts) == 1
    assert slept.waited == []
    assert result.outcome != SUCCEEDED


def test_success_on_the_first_attempt_costs_nothing_extra():
    """The ordinary path is unchanged in both behaviour and latency."""
    provider, transport, slept = _provider(_ok())

    result = provider.complete("hi")

    assert result.outcome == SUCCEEDED
    assert len(transport.posts) == 1
    assert slept.waited == []


def test_a_timeout_is_deliberately_not_retried():
    """The deadline that just expired is the caller's own budget; spending
    it again would multiply a wait the founder already found too long."""
    provider, transport, slept = _provider(TransportTimeout("too slow"))

    result = provider.complete("hi")

    assert result.outcome == TIMED_OUT
    assert len(transport.posts) == 1
    assert slept.waited == []


def test_an_unreachable_transport_is_retried_then_reported():
    provider, transport, slept = _provider(
        TransportUnavailable("no route"), TransportUnavailable("no route"),
        TransportUnavailable("no route"),
    )

    result = provider.complete("hi")

    assert result.outcome == UNAVAILABLE
    assert len(transport.posts) == 3


def test_an_unreachable_transport_that_recovers_returns_the_success():
    provider, transport, _ = _provider(TransportUnavailable("no route"), _ok("back"))

    result = provider.complete("hi")

    assert result.outcome == SUCCEEDED
    assert result.text == "back"
    assert len(transport.posts) == 2


def test_a_malformed_body_is_not_retried():
    """A 200 that is not JSON is an answer, and asking again will not make
    it parse."""
    provider, transport, slept = _provider(HttpResponse(200, "not json at all"))

    result = provider.complete("hi")

    assert result.outcome == MALFORMED
    assert len(transport.posts) == 1
    assert slept.waited == []


def test_the_attempt_cap_is_configurable():
    provider, transport, _ = _provider(
        _error(503, "busy"), _error(503, "busy"), max_attempts=2,
    )
    provider.complete("hi")
    assert len(transport.posts) == 2


def test_the_attempt_cap_is_never_below_one():
    """`max(1, max_attempts)` — a caller asking for zero attempts still
    gets the one call they actually wanted, rather than a result composed
    without ever asking the provider."""
    provider, transport, _ = _provider(_error(503, "busy"), max_attempts=0)

    result = provider.complete("hi")

    assert len(transport.posts) == 1
    assert result.outcome != SUCCEEDED
