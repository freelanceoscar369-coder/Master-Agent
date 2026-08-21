"""Gemini API Provider — Kalpavriksha's first cloud reasoning execution
path (Founder decision: provider search closed, Gemini API selected).

Mirrors `providers/ollama.py`'s shape exactly: **it executes, it never
decides.** No ranking, no fallback, no retry beyond what the transport
itself reports — the same MB033 split applies here as it does to Ollama:
the Broker decides, the provider executes and never silently substitutes
a different provider or a different answer.

## Transport

Plain REST over the existing `Transport` protocol
(`providers/transport.py`), the same `UrllibTransport` Ollama already
uses. No SDK dependency added: the surface needed — one POST, JSON in,
JSON out — does not earn one, the same judgment `transport.py`'s own
docstring already made for Ollama.

## Credential

`api_key` is handed in at construction, never read from this module. A
missing key is reported as `UNAVAILABLE` — the same outcome Ollama uses
for "nothing is listening" — because from Gemini's perspective an
unauthenticated caller cannot be reached any more than a stopped daemon
can. No call is attempted with an empty key.
"""
from __future__ import annotations

import time
from typing import Any

from master_agent.plugins.base import (
    CapabilityManifest,
    ModelProvider,
    PluginManifest,
    RiskTier,
)
from master_agent.providers.response import (
    MALFORMED,
    REJECTED,
    SUCCEEDED,
    TIMED_OUT,
    UNAVAILABLE,
    Availability,
    ProviderResponse,
    ProviderResult,
    failure,
)
from master_agent.providers.transport import (
    DEFAULT_TIMEOUT_SECONDS,
    Transport,
    TransportTimeout,
    TransportUnavailable,
    UrllibTransport,
)

#: Must equal the `provider_id` the AI Infrastructure catalogue uses for
#: this provider. Not imported from there, the same reason `ollama.py`
#: does not: this package sits below the wiring layer.
GEMINI_PROVIDER_ID = "gemini.api"

GEMINI_VERSION = "1.0.0"
DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
#: Founder decision: free-tier-eligible model via a Google AI Studio API
#: key. Configuration, never a choice made here — see `config.py`'s
#: `GeminiConfig.model` docstring for how a founder changes it.
#: `gemini-2.5-flash` -> `gemini-3.6-flash`: model migration, verified
#: live against `models.list` and a real request before the switch.
DEFAULT_MODEL = "gemini-3.6-flash"

NO_API_KEY = "no GEMINI_API_KEY configured"

#: HTTP statuses that mean *"ask again shortly"* rather than *"this request
#: is wrong"*. 503 is the one a founder actually hit ("This model is
#: currently experiencing high demand"); 429 is free-tier rate limiting;
#: 500/502/504 are Google-side transients. A 4xx that is not 429 is never
#: retried — repeating a malformed or unauthorised request cannot change
#: its answer.
TRANSIENT_STATUSES = frozenset({429, 500, 502, 503, 504})

#: Total attempts, not extra ones: 3 means one call plus at most two
#: retries. Bounded deliberately — MB033 Rule 4 puts retry policy in the
#: provider, and `transport.py`'s own docstring is explicit that "burying a
#: retry loop underneath a provider is how 'no retries beyond its own
#: transport layer' quietly becomes six." This is that one policy, stated
#: once, in the layer that owns it.
DEFAULT_MAX_ATTEMPTS = 3

#: Seconds to wait before each retry, indexed by the retry number. Fixed
#: and short rather than exponential-with-jitter: the founder is sitting in
#: front of a desktop app waiting for a reply, so the whole retry budget
#: has to stay inside a few seconds of added latency, and a transient
#: 503 from a large provider either clears quickly or is not clearing
#: within any delay a founder would tolerate.
RETRY_DELAYS_SECONDS = (0.6, 1.4)


class GeminiProvider(ModelProvider):
    """A `ModelProvider` backed by the Gemini REST API.

    `model` and `api_key` are configuration, never a choice made here —
    the same discipline `OllamaProvider.model` already states.
    """

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        transport: Transport | None = None,
        clock: Any = None,
        provider_id: str = GEMINI_PROVIDER_ID,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        sleep: Any = None,
    ) -> None:
        self._api_key = api_key or ""
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._transport: Transport = transport or UrllibTransport()
        self._clock = clock or time.monotonic
        self._provider_id = provider_id
        self._max_attempts = max(1, max_attempts)
        # Injected for testability, the same seam `clock` and `transport`
        # already are — a test proving the retry policy must not actually
        # sleep for it.
        self._sleep = sleep or time.sleep

    # ---- identity -------------------------------------------------------

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def model(self) -> str:
        return self._model

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name=self._provider_id,
            version=GEMINI_VERSION,
            capabilities=[
                CapabilityManifest(
                    name=self.CAPABILITY_NAME,
                    description=f"Generate text with Gemini ({self._model}).",
                    risk_tier=RiskTier.READ_ONLY,
                )
            ],
        )

    # ---- availability ---------------------------------------------------

    def availability(self) -> Availability:
        """Whether a call could be attempted right now. A missing key is
        reported here rather than only at call time, the same way
        `OllamaProvider.availability()` reports a stopped daemon."""
        if not self._api_key:
            return Availability(self._provider_id, False, detail=NO_API_KEY)
        return Availability(
            self._provider_id, True, models=(self._model,), detail="configured"
        )

    # ---- execution ------------------------------------------------------

    def complete(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
        budget: Any = None,
        cancellation: Any = None,
    ) -> ProviderResult:
        """Run one prompt. Returns an answer or a reason — never both, and
        never an exception for an operational failure.

        Non-streaming only (`generateContent`, not `streamGenerateContent`):
        the smallest correct implementation for a synchronous
        prompt-in/text-out reasoning call. A budget's total deadline is
        honoured as the request timeout when one is supplied; the finer
        TTFT/ITL split Ollama's streaming path measures does not apply to
        a non-streaming call.
        """
        started = self._clock()
        if not self._api_key:
            return failure(
                self._provider_id,
                UNAVAILABLE,
                NO_API_KEY,
                latency_ms=self._elapsed_ms(started),
            )

        timeout = _timeout_for(budget, self._timeout)
        url = (
            f"{self._base_url}/models/{self._model}:generateContent"
            f"?key={self._api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": self._compose(prompt, context)}]}],
        }
        merged_options = _drop_unsupported_sampling_params(dict(options or {}))
        if merged_options:
            payload["generationConfig"] = merged_options

        # Bounded retry on transient conditions only (see
        # `TRANSIENT_STATUSES`/`DEFAULT_MAX_ATTEMPTS`). Every non-transient
        # outcome — success, a 4xx that is not 429, malformed JSON —
        # returns on the first pass exactly as before, so the ordinary
        # path is unchanged in both behaviour and latency.
        last: ProviderResult | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = self._transport.post_json(url, payload, timeout)
            except TransportTimeout as exc:
                # A timeout is not retried: the deadline that just expired
                # is the caller's own budget, and spending it again would
                # multiply the wait a founder already found too long.
                return failure(
                    self._provider_id,
                    TIMED_OUT,
                    str(exc),
                    latency_ms=self._elapsed_ms(started),
                    timeout_seconds=timeout,
                    url=self._base_url,
                )
            except TransportUnavailable as exc:
                last = failure(
                    self._provider_id,
                    UNAVAILABLE,
                    f"{exc} (could not reach {self._base_url})",
                    latency_ms=self._elapsed_ms(started),
                    url=self._base_url,
                )
                if attempt >= self._max_attempts:
                    return last
                self._wait_before_retry(attempt)
                continue

            if response.ok or response.status not in TRANSIENT_STATUSES:
                return self._read(response, started)

            last = self._read(response, started)
            if attempt >= self._max_attempts:
                return last
            self._wait_before_retry(attempt)

        return last if last is not None else failure(
            self._provider_id,
            UNAVAILABLE,
            "no attempt was made",
            latency_ms=self._elapsed_ms(started),
        )

    def _wait_before_retry(self, attempt: int) -> None:
        delay = (
            RETRY_DELAYS_SECONDS[attempt - 1]
            if attempt - 1 < len(RETRY_DELAYS_SECONDS)
            else RETRY_DELAYS_SECONDS[-1]
        )
        self._sleep(delay)

    # ---- the ModelProvider contract -------------------------------------

    def generate(
        self, prompt: str, context: dict[str, Any] | None = None, **opts: Any
    ) -> str:
        """The frozen `ModelProvider` contract: a string, or nothing.

        Raises on failure, the same discipline `OllamaProvider.generate()`
        already applies and for the same reason: a caller that cannot
        tell an answer from an apology will store the apology as an
        answer.
        """
        result = self.complete(prompt, context, options=opts or None)
        if not result.ok:
            from master_agent.providers.ollama import ProviderExecutionFailed

            raise ProviderExecutionFailed(result)
        return result.text

    # ---- internals -------------------------------------------------------

    def _read(self, response: Any, started: float) -> ProviderResult:
        latency = self._elapsed_ms(started)

        if not response.ok:
            return failure(
                self._provider_id,
                self._outcome_for_status(response.status),
                self._rejection(response),
                latency_ms=latency,
                status=response.status,
                model=self._model,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            return failure(
                self._provider_id,
                MALFORMED,
                f"Gemini answered with something that is not JSON: {exc}",
                latency_ms=latency,
                body=response.body[:200],
            )

        text = _extract_text(payload)
        if text is None:
            return failure(
                self._provider_id,
                MALFORMED,
                "Gemini answered JSON with no readable candidate text",
                latency_ms=latency,
                body=response.body[:200],
            )

        usage = payload.get("usageMetadata") or {}
        candidates = payload.get("candidates") or [{}]
        finish_reason = str((candidates[0] or {}).get("finishReason", ""))

        return ProviderResult(
            provider_id=self._provider_id,
            outcome=SUCCEEDED,
            response=ProviderResponse(
                text=text,
                model=self._model,
                latency_ms=latency,
                prompt_tokens=_count(usage.get("promptTokenCount")),
                completion_tokens=_count(usage.get("candidatesTokenCount")),
                finish_reason=finish_reason,
            ),
            latency_ms=latency,
        )

    def _outcome_for_status(self, status: int) -> str:
        """429 is quota/rate-limit exhaustion (Founder's free-tier
        constraint, §8 of the build brief) — reported as `REJECTED`
        exactly like Ollama reports "model not found": the provider *is*
        reachable, and the reason is in the body, never invented here."""
        return REJECTED

    def _rejection(self, response: Any) -> str:
        """A refusal a founder can act on. Gemini's error body carries
        `error.message`; dropping it in favour of "HTTP 429" would throw
        away the only useful half — the same principle
        `OllamaProvider._rejection()` already applies."""
        detail = ""
        try:
            parsed = response.json()
            if isinstance(parsed, dict):
                error = parsed.get("error")
                if isinstance(error, dict) and error.get("message"):
                    detail = str(error["message"])
        except ValueError:
            detail = (response.body or "").strip()[:200]
        return f"HTTP {response.status}{f': {detail}' if detail else ''}"

    def _compose(self, prompt: str, context: dict[str, Any] | None) -> str:
        """Context is appended as plain labelled lines — the same,
        deliberately un-templated composition `OllamaProvider._compose()`
        uses. Templating is a decision about how to get a better answer,
        and this class does not make those."""
        if not context:
            return prompt
        lines = [f"{key}: {value}" for key, value in sorted(context.items())]
        return f"{prompt}\n\n" + "\n".join(lines)

    def _elapsed_ms(self, started: float) -> float:
        return max(0.0, (self._clock() - started) * 1000.0)


#: Gemini 3.x models do not accept caller-set sampling parameters:
#: temperature/top_p/top_k are silently ignored if sent, and
#: frequency_penalty/presence_penalty cause a request error (Google's own
#: migration guidance, verified 2026-08-12 against the live API docs
#: while migrating this provider's default model from gemini-2.5-flash to
#: gemini-3.6-flash). Nothing in the current wiring sets any of these —
#: `PromptExecutor.run()` never passes `options` — but `generate()`'s
#: frozen `**opts` contract forwards whatever a future caller supplies,
#: so they are dropped here rather than left to surface as a confusing
#: per-call API error for a constraint the caller had no way to know
#: about. Every other option is passed through unexamined, unchanged:
#: this provider still executes, it does not decide.
_UNSUPPORTED_SAMPLING_PARAMS = frozenset(
    {
        "temperature",
        "top_p",
        "topP",
        "top_k",
        "topK",
        "frequency_penalty",
        "frequencyPenalty",
        "presence_penalty",
        "presencePenalty",
    }
)


def _drop_unsupported_sampling_params(options: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in options.items() if k not in _UNSUPPORTED_SAMPLING_PARAMS}


def _timeout_for(budget: Any, default: float) -> float:
    """A budget's total deadline, in seconds, or the provider's own
    default when no budget was supplied or it carries nothing usable.
    Deliberately tolerant of shape: this provider does not depend on the
    exact `CallBudget` fields Ollama's streaming path enforces, since it
    never streams."""
    if budget is None:
        return default
    total_ms = getattr(budget, "total_deadline_ms", None)
    if isinstance(total_ms, (int, float)) and total_ms > 0:
        return total_ms / 1000.0
    return default


def _extract_text(payload: Any) -> str | None:
    """The first candidate's concatenated text, or `None` when the shape
    is not what was promised. `None` is a distinct outcome from `""`: an
    empty string is a real (if useless) answer, and this function must
    never confuse the two."""
    if not isinstance(payload, dict):
        return None
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return None
    first = candidates[0]
    if not isinstance(first, dict):
        return None
    content = first.get("content")
    if not isinstance(content, dict):
        return None
    parts = content.get("parts")
    if not isinstance(parts, list):
        return None
    texts = [
        str(part["text"])
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ]
    if not texts:
        return None
    return "".join(texts)


def _count(value: Any) -> int | None:
    """A token count, or None. Never 0 for "unreported" — the same rule
    `ollama.py::_count()` already states."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value >= 0 else None
