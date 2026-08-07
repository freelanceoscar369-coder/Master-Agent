"""The Ollama provider — Kalpavriksha's first real AI execution path
(Mission Brief 033).

**It executes. It never decides.** It cannot rank, route, fall back,
install, benchmark, or choose a model; it is handed one and runs it. That
is MB033 Rule 4, and it is the same split ADR-0017 drew for the Broker
from the other side: *the Broker decides and never executes; a provider
executes and never decides.* A test parses this package for the
vocabulary of deciding and fails on any of it.

## What it does with a failure

Nothing clever. Ollama not running, the model not installed, a request
that outran its timeout, a body that is not the JSON it claimed — each
comes back as a `ProviderResult` naming which one, plus whatever a founder
needs to fix it (the address tried, the models actually installed). MB033
Rule 5: **never silently fall back.** Asking a different provider is a
selection, selection belongs to the Broker, and a provider that quietly
retried elsewhere would make the `DecisionRecord` a lie about what ran.

## Retries: there are none (MB038)

This adapter used to re-attempt a refused connection once. It no longer
retries anything at all. **A retry belongs to the layer that owns the
failure's meaning**, and a refused socket means nothing here — only the
Runtime knows what the work was for, and it has owned mechanical retry
with escalation since MB024. Two retry mechanisms with no written
boundary between them was one too many.

A timeout was never retried and still is not: a timeout means the model
is slower than the time allowed, and asking again under the same budget
is how a 120-second wait becomes a 240-second one for the same answer.

## Three deadlines, not one (MB038)

A call carrying a `CallBudget` streams, and is held to a time-to-first-
token deadline, an inter-token stall deadline, and a total deadline —
because "it never started", "it stopped halfway" and "it was healthy but
too slow" have different causes and different fixes. A call without a
budget takes the older single-request path, which cannot tell them apart.
"""
from __future__ import annotations

import json
import time
from typing import Any

from master_agent.plugins.base import (
    CapabilityManifest,
    ModelProvider,
    PluginManifest,
    RiskTier,
)
from master_agent.providers.deadline import (
    DeadlineExceeded,
    read_timeout_seconds,
    supervise,
)
from master_agent.providers.response import (
    MALFORMED,
    REJECTED,
    SUCCEEDED,
    TIMED_OUT,
    TIMED_OUT_ITL,
    TIMED_OUT_TTFT,
    UNAVAILABLE,
    Availability,
    ProviderResponse,
    ProviderResult,
    failure,
)
from master_agent.providers.stream import StreamMonitor
from master_agent.providers.transport import (
    DEFAULT_TIMEOUT_SECONDS,
    Transport,
    TransportTimeout,
    TransportUnavailable,
    UrllibTransport,
)

#: Must equal the `provider_id` the AI Infrastructure catalogue uses for
#: this provider. Deliberately *not* imported from there: this package
#: sits below the wiring layer and must not depend on it. A test asserts
#: the two agree, which is how two vocabularies stay in step without one
#: dragging in the other.
OLLAMA_PROVIDER_ID = "ollama.local"

OLLAMA_VERSION = "1.0.0"
DEFAULT_BASE_URL = "http://localhost:11434"
GENERATE_PATH = "/api/generate"
TAGS_PATH = "/api/tags"

# MB038 removed this adapter's retry entirely. It used to re-attempt a
# connection failure once, which was defensible when the adapter was the
# only thing that knew a call had failed -- but the Runtime owns
# mechanical retry with escalation (MB024), and two retry mechanisms with
# no written boundary is one too many.
#
# The rule that replaces it: **a retry belongs to the layer that owns the
# failure's meaning.** A refused connection means nothing to an adapter;
# a failed task means something to the mission. So the adapter reports,
# and the Runtime decides.
#
# `attempts` survives on `ProviderResult` and is now always 1 from here.
# It is kept rather than deleted because a *record* of how many attempts
# were made is still true of older records, and a future provider whose
# protocol genuinely requires a handshake retry would need it.


class ProviderExecutionFailed(Exception):
    """Raised only by `generate()`, which must return a string or nothing
    at all because `ModelProvider` says so (ADR-0003, frozen).

    Every other caller uses `complete()` and gets the failure as data.
    This exists so the older, narrower contract stays honest rather than
    returning an error message *as if it were generated text* — which is
    the one failure mode that would poison everything downstream.
    """

    def __init__(self, result: ProviderResult) -> None:
        super().__init__(f"{result.outcome}: {result.error}")
        self.result = result


class OllamaProvider(ModelProvider):
    """A `ModelProvider` backed by a local Ollama daemon.

    `model` is configuration, never a choice made here. A model that is
    not installed produces a `REJECTED` result naming the ones that are,
    so the founder fixes their config instead of reading a stack trace.
    """

    def __init__(
        self,
        model: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        transport: Transport | None = None,
        clock: Any = None,
        provider_id: str = OLLAMA_PROVIDER_ID,
        options: dict[str, Any] | None = None,
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        # MB038: the pre-budget fallback only. A call that arrives with a
        # `CallBudget` ignores this entirely and enforces three deadlines
        # instead. It remains for the health probe, which is a fixed, tiny
        # request that no workload class describes.
        self._timeout = timeout_seconds
        self._transport: Transport = transport or UrllibTransport()
        # Monotonic, not wall-clock: a latency measured across an NTP step
        # or a laptop waking up is not a latency.
        self._clock = clock or time.monotonic
        self._provider_id = provider_id
        self._options = dict(options or {})

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
        """Named for the **provider id**, so the Broker's answer resolves
        straight to this object through the registry with no translation
        table in between."""
        return PluginManifest(
            name=self._provider_id,
            version=OLLAMA_VERSION,
            capabilities=[
                CapabilityManifest(
                    name=self.CAPABILITY_NAME,
                    description=f"Generate text with a local model ({self._model}).",
                    # Generation itself reads and returns text. Anything it
                    # *recommends* still needs its own capability and its
                    # own tier -- the reasoning MB001's manifest gave, and
                    # it has not changed.
                    risk_tier=RiskTier.READ_ONLY,
                )
            ],
        )

    # ---- availability ---------------------------------------------------

    def availability(self) -> Availability:
        """What the daemon says it has. A fact, never a shortlist —
        nothing here reads this to make a choice."""
        try:
            response = self._transport.get(
                f"{self._base_url}{TAGS_PATH}", timeout=self._timeout
            )
        except TransportTimeout as exc:
            return Availability(self._provider_id, False, detail=str(exc))
        except TransportUnavailable as exc:
            return Availability(self._provider_id, False, detail=str(exc))

        if not response.ok:
            return Availability(
                self._provider_id, False, detail=f"HTTP {response.status}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            return Availability(self._provider_id, False, detail=f"unreadable: {exc}")

        models = tuple(
            str(entry.get("name", ""))
            for entry in (payload or {}).get("models", [])
            if isinstance(entry, dict) and entry.get("name")
        )
        return Availability(self._provider_id, True, models=models, detail="reachable")

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

        With a `CallBudget` the call streams and is held to three
        deadlines. Without one it takes the pre-MB038 path: a single
        blocking request under a single timeout, which cannot tell prefill
        from a stall. Step 14 makes budgets mandatory and removes it.
        """
        started = self._clock()
        payload: dict[str, Any] = {
            "model": self._model,
            "prompt": self._compose(prompt, context),
            "stream": budget is not None,
        }
        merged = {**self._options, **(options or {})}
        if merged:
            payload["options"] = merged

        if budget is not None:
            return self._stream(payload, budget, started, cancellation)

        try:
            response = self._transport.post_json(
                f"{self._base_url}{GENERATE_PATH}", payload, self._timeout
            )
        except TransportTimeout as exc:
            return failure(
                self._provider_id,
                TIMED_OUT,
                str(exc),
                latency_ms=self._elapsed_ms(started),
                timeout_seconds=self._timeout,
                url=self._base_url,
            )
        except TransportUnavailable as exc:
            # No retry. The Runtime owns that decision now (MB024).
            return failure(
                self._provider_id,
                UNAVAILABLE,
                f"{exc} (is Ollama running at {self._base_url}?)",
                latency_ms=self._elapsed_ms(started),
                url=self._base_url,
            )
        return self._read(response, 1, started)

    # ---- the budgeted path ----------------------------------------------

    def _stream(
        self,
        payload: dict[str, Any],
        budget: Any,
        started: float,
        cancellation: Any = None,
    ) -> ProviderResult:
        """One generation, held to three deadlines.

        This adapter parses; `deadline.supervise()` decides. Which frames
        count as tokens is settled here because that means knowing
        Ollama's frame shape — a `done` frame carries no text and must not
        reset the stall clock.
        """
        monitor = StreamMonitor(clock=self._clock, started_at=started)
        collected: list[str] = []
        final: dict[str, Any] = {}

        try:
            for frame in supervise(
                self._frames(payload, budget, monitor),
                budget,
                monitor,
                self._clock,
                is_token=_carries_text,
                provider_id=self._provider_id,
                capability=self.CAPABILITY_NAME,
                cancellation=cancellation,
            ):
                text = frame.get("response")
                if text:
                    collected.append(str(text))
                if frame.get("done"):
                    monitor.complete()
                    final = frame
        except DeadlineExceeded as exc:
            return failure(
                self._provider_id,
                exc.event.reason,
                exc.event.summary,
                latency_ms=monitor.elapsed_ms(self._clock()),
                timeout=exc.event.as_dict(),
            )
        except TransportTimeout as exc:
            # The socket gave up before the enforcer did. Which deadline
            # that was is still knowable: the monitor knows whether
            # anything ever arrived.
            return failure(
                self._provider_id,
                TIMED_OUT_ITL if monitor.started else TIMED_OUT_TTFT,
                str(exc),
                latency_ms=monitor.elapsed_ms(self._clock()),
                observation=monitor.observe().as_dict(),
                budget=budget.as_dict(),
            )
        except TransportUnavailable as exc:
            return failure(
                self._provider_id,
                UNAVAILABLE,
                f"{exc} (is Ollama running at {self._base_url}?)",
                latency_ms=monitor.elapsed_ms(self._clock()),
                url=self._base_url,
            )
        except ValueError as exc:
            return failure(
                self._provider_id,
                MALFORMED,
                f"the daemon streamed something that is not JSON: {exc}",
                latency_ms=monitor.elapsed_ms(self._clock()),
            )

        observation = monitor.observe()
        return ProviderResult(
            provider_id=self._provider_id,
            outcome=SUCCEEDED,
            response=ProviderResponse(
                text="".join(collected),
                model=str(final.get("model", self._model)),
                latency_ms=observation.elapsed_ms,
                prompt_tokens=_count(final.get("prompt_eval_count")),
                completion_tokens=_count(final.get("eval_count")),
                finish_reason=str(final.get("done_reason", "")),
            ),
            latency_ms=observation.elapsed_ms,
            detail={
                "observation": observation.as_dict(),
                "budget": budget.as_dict(),
            },
        )

    def _frames(self, payload: dict[str, Any], budget: Any, monitor: Any) -> Any:
        """Parsed NDJSON frames, each read bounded by whichever deadline
        could fire while it blocks."""
        for line in self._transport.stream_json(
            f"{self._base_url}{GENERATE_PATH}",
            payload,
            read_timeout_seconds(budget, monitor, self._clock()),
        ):
            yield json.loads(line)

    def _read(self, response: Any, attempts: int, started: float) -> ProviderResult:
        latency = self._elapsed_ms(started)

        if not response.ok:
            return failure(
                self._provider_id,
                REJECTED,
                self._rejection(response),
                attempts=attempts,
                latency_ms=latency,
                status=response.status,
                model=self._model,
                installed=list(self.availability().models),
            )

        try:
            payload = response.json()
        except ValueError as exc:
            return failure(
                self._provider_id,
                MALFORMED,
                f"the daemon answered with something that is not JSON: {exc}",
                attempts=attempts,
                latency_ms=latency,
                body=response.body[:200],
            )

        if not isinstance(payload, dict) or "response" not in payload:
            return failure(
                self._provider_id,
                MALFORMED,
                "the daemon answered JSON with no 'response' field",
                attempts=attempts,
                latency_ms=latency,
                body=response.body[:200],
            )

        return ProviderResult(
            provider_id=self._provider_id,
            outcome=SUCCEEDED,
            response=ProviderResponse(
                text=str(payload.get("response", "")),
                model=str(payload.get("model", self._model)),
                latency_ms=latency,
                prompt_tokens=_count(payload.get("prompt_eval_count")),
                completion_tokens=_count(payload.get("eval_count")),
                finish_reason=str(payload.get("done_reason", "")),
            ),
            attempts=attempts,
            latency_ms=latency,
        )

    def _rejection(self, response: Any) -> str:
        """A refusal a founder can act on. Ollama puts "model X not found"
        in the body, and dropping it in favour of "HTTP 404" would throw
        away the only useful half."""
        body = (response.body or "").strip()
        detail = ""
        try:
            parsed = response.json()
            if isinstance(parsed, dict) and parsed.get("error"):
                detail = str(parsed["error"])
        except ValueError:
            detail = body[:200]
        return f"HTTP {response.status}{f': {detail}' if detail else ''}"

    # ---- the ModelProvider contract -------------------------------------

    def generate(
        self, prompt: str, context: dict[str, Any] | None = None, **opts: Any
    ) -> str:
        """The frozen `ModelProvider` contract: a string, or nothing.

        Raises on failure rather than returning the error text, because a
        caller that cannot tell an answer from an apology will store the
        apology as an answer.
        """
        result = self.complete(prompt, context, options=opts or None)
        if not result.ok:
            raise ProviderExecutionFailed(result)
        return result.text

    # ---- internals -------------------------------------------------------

    def _compose(self, prompt: str, context: dict[str, Any] | None) -> str:
        """Context is appended as plain labelled lines.

        Deliberately not a chat template or a system prompt: templating is
        a decision about how to get a better answer, and this class does
        not make those. A caller that wants a template builds one and
        passes it as the prompt.
        """
        if not context:
            return prompt
        lines = [f"{key}: {value}" for key, value in sorted(context.items())]
        return f"{prompt}\n\n" + "\n".join(lines)

    def _elapsed_ms(self, started: float) -> float:
        return max(0.0, (self._clock() - started) * 1000.0)


def _carries_text(frame: Any) -> bool:
    """Does this frame count as a token arriving?

    Ollama's final frame has `response: ""` and `done: true`. It is a
    completion signal, not content, and treating it as a token would let
    a stalled stream look alive right up to the moment it ends.
    """
    return bool(isinstance(frame, dict) and frame.get("response"))


def _count(value: Any) -> int | None:
    """A token count, or None. Never 0 for "unreported" — see
    `ProviderResponse`."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value >= 0 else None
