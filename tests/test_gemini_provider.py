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
