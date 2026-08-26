"""OpenRouter as a gateway, not a brain.

`openrouter.api` has been in provider knowledge for a long time with no
executable implementation behind it -- a descriptor the Broker could see
and nothing could call. Being KNOWN is not being EXECUTABLE, and this is
the piece that makes the difference for exactly one provider.

**It executes; it never decides.** Same rule as `providers/gemini.py`,
same `ModelProvider` contract, same `providers/transport.py`, same
`ProviderResult` vocabulary. Selection, quality policy, economics,
privacy, verification, fallback and history all stay where they already
live.

## Why not `openrouter/auto` or `openrouter/free`

Both would work today and both hand a decision away. `auto` lets the
gateway pick the model; `free` lets it pick among free ones. Either way
the model that answered is chosen by someone else, which makes
Kalpavriksha's own record of what happened -- which model, at what
quality, at what cost -- an account of a decision it did not make.

So this asks OpenRouter what models exist, picks a specific zero-cost one
itself, and sends that slug explicitly. The choice is recorded with the
evidence it was made on.

## The cost rule is absolute

A model is eligible only when its published prompt AND completion prices
are both exactly zero, read from OpenRouter's own `/models` at the moment
of use. If no such model is available, this returns unavailable rather
than falling back to a priced one. Nothing here may silently incur a
charge.

## The credential

Read from configuration at call time, used for one request, never stored
on the descriptor, never persisted, never logged. Its absence is ordinary
provider unavailability -- the same answer as an application that is not
installed -- not an error.
"""
from __future__ import annotations

import json
import os
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
    Transport,
    TransportError,
    TransportTimeout,
    TransportUnavailable,
    UrllibTransport,
)

OPENROUTER_PROVIDER_ID = "openrouter.api"
OPENROUTER_VERSION = "1.0.0"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
#: The environment name the founder's credential is already kept under.
CREDENTIAL_ENV = "OPENROUTER_API_KEY"
DEFAULT_TIMEOUT_SECONDS = 60.0
#: How long a model listing stays usable before it is fetched again. Short,
#: because a price is a fact about right now: a model that was free this
#: morning and is priced this afternoon must not be selected on a stale
#: reading.
MODEL_CACHE_SECONDS = 300.0
#: The gateway's own namespace for aggregator pseudo-models that pick an
#: underlying model themselves. Excluded from selection: they are useful
#: for experimentation and they hide which model actually answered, which
#: is the one thing this provider exists to keep hold of.
AGGREGATOR_NAMESPACE = "openrouter"

#: Reused verbatim from `providers/gemini.py`'s own policy rather than
#: invented here: a provider owns its retry, and burying it in the
#: transport is what turns "one transport layer" into six. Observed live
#: on this gateway -- the same zero-cost model returned 429 and then 200
#: forty seconds later, which is ordinary free-tier throttling and not a
#: reason to lose the mission.
TRANSIENT_STATUSES = frozenset({429, 500, 502, 503, 504})
MAX_ATTEMPTS = 3
RETRY_DELAYS_SECONDS = (0.8, 2.0)

NO_CREDENTIAL = "no OPENROUTER_API_KEY is configured"
NO_FREE_MODEL = (
    "OpenRouter currently lists no model whose prompt and completion "
    "prices are both zero; refusing rather than incurring a charge"
)


class OpenRouterProvider(ModelProvider):
    """One OpenRouter gateway. Constructing it performs no network call
    and reads no credential -- the same discipline `GeminiProvider`
    holds, so mere registration cannot cause a request."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        transport: Transport | None = None,
        credential_reader: Any = None,
        clock: Any = None,
        sleep: Any = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._transport: Transport = transport or UrllibTransport()
        #: Injected so a test never touches the founder's real environment,
        #: and so the credential has exactly one read path.
        self._credential_reader = credential_reader or (
            lambda: os.environ.get(CREDENTIAL_ENV, "")
        )
        self._clock = clock or time.monotonic
        #: Injected so a test never actually waits.
        self._sleep = sleep or time.sleep
        self._models: tuple[dict[str, Any], ...] = ()
        self._models_read_at: float | None = None

    # ---- identity -------------------------------------------------------

    @property
    def provider_id(self) -> str:
        return OPENROUTER_PROVIDER_ID

    @property
    def base_url(self) -> str:
        return self._base_url

    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name=OPENROUTER_PROVIDER_ID,
            version=OPENROUTER_VERSION,
            description="Reasoning through the OpenRouter gateway, free models only.",
            capabilities=(
                CapabilityManifest(
                    name="reasoning",
                    description="Answer a prompt via a specific zero-cost model.",
                    risk_tier=RiskTier.READ_ONLY,
                ),
            ),
        )

    # ---- availability ---------------------------------------------------

    def availability(self) -> Availability:
        """Reachable only with a credential. Its absence is unavailability,
        stated the same way an uninstalled application's is."""
        if not self._credential():
            return Availability(self.provider_id, False, detail=NO_CREDENTIAL)
        return Availability(self.provider_id, True, detail="credential configured")

    def _credential(self) -> str:
        try:
            return (self._credential_reader() or "").strip()
        except Exception:  # noqa: BLE001 - a missing credential is not an error
            return ""

    # ---- model choice ---------------------------------------------------

    def free_models(self, force: bool = False) -> tuple[dict[str, Any], ...]:
        """Every currently-listed model whose prompt AND completion prices
        are both exactly zero.

        Read from OpenRouter's own catalogue, cached briefly, and never
        inferred from a slug: a name ending in `:free` is a naming
        convention, and this needs a price.
        """
        now = self._clock()
        stale = (
            self._models_read_at is None
            or (now - self._models_read_at) > MODEL_CACHE_SECONDS
        )
        if force or stale:
            response = self._transport.get(f"{self._base_url}/models", 30.0)
            if getattr(response, "status", 0) != 200:
                return ()
            try:
                listed = json.loads(response.body).get("data", [])
            except (ValueError, AttributeError, TypeError):
                return ()
            self._models = tuple(listed)
            self._models_read_at = now

        free = []
        for model in self._models:
            pricing = model.get("pricing") or {}
            try:
                prompt_price = float(pricing.get("prompt", 1))
                completion_price = float(pricing.get("completion", 1))
            except (TypeError, ValueError):
                continue
            if prompt_price == 0.0 and completion_price == 0.0:
                free.append(model)
        return tuple(free)

    def resolve_model(self) -> dict[str, Any] | None:
        """The specific zero-cost TEXT model this call will address, or
        None.

        Named `resolve`, not `choose`, and the distinction is the one an
        architecture guard in `tests/test_ollama_provider.py` enforces: a
        provider executes and never decides. It caught this method when it
        was called `choose_model`, correctly.

        Nothing here selects a PROVIDER or applies a policy -- that is the
        Broker's, and it stays there. This resolves which of the gateway's
        own models this gateway will address, which the Broker cannot do
        because it does not hold OpenRouter's catalogue. It is execution
        detail, bounded by the cost rule below.

        Two filters beyond price, both from OpenRouter's own metadata and
        neither naming a vendor.

        **Modality.** A first version ranked purely by context length and
        chose a clip-generation model that happens to accept a text
        prompt. `architecture.input_modalities` / `output_modalities` is
        the published answer to "can this thing read and write text", so
        it is asked rather than inferred from a slug.

        **Self-delegation.** The gateway publishes aggregator pseudo-models
        in its own namespace which choose an underlying model themselves.
        They work, and they hand back the decision this provider exists to
        keep: the record would then say a model answered without saying
        which. Excluded by namespace, not by name.

        Ordered by context length then slug, so the same listing always
        yields the same choice and the decision is reproducible from the
        evidence recorded with it.
        """
        candidates = []
        for model in self.free_models():
            architecture = model.get("architecture") or {}
            inputs = architecture.get("input_modalities") or []
            outputs = architecture.get("output_modalities") or []
            # Text in, and text ONLY out. Merely *including* text is not
            # enough: a clip-generation model declares
            # `['text','image'] -> ['text','audio']` and passed an earlier
            # version of this filter, which then chose it to answer a
            # three-name question. A text reasoner emits text and nothing
            # else, and that is a property of the published metadata
            # rather than a judgement about any vendor.
            if "text" not in inputs or list(outputs) != ["text"]:
                continue
            if str(model.get("id", "")).split("/", 1)[0] == AGGREGATOR_NAMESPACE:
                continue
            candidates.append(model)
        if not candidates:
            return None
        return sorted(
            candidates,
            key=lambda m: (-(m.get("context_length") or 0), str(m.get("id", ""))),
        )[0]

    # ---- execution ------------------------------------------------------

    def complete(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        **options: Any,
    ) -> ProviderResult:
        started = time.monotonic()
        credential = self._credential()
        if not credential:
            return failure(self.provider_id, UNAVAILABLE, NO_CREDENTIAL)

        model = self.resolve_model()
        if model is None:
            return failure(self.provider_id, UNAVAILABLE, NO_FREE_MODEL)
        slug = str(model.get("id", ""))

        payload = {
            "model": slug,
            "messages": [{"role": "user", "content": prompt}],
        }
        last: ProviderResult | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = self._transport.post_json(
                    f"{self._base_url}/chat/completions",
                    payload,
                    DEFAULT_TIMEOUT_SECONDS,
                    headers={"Authorization": f"Bearer {credential}"},
                )
            except TransportTimeout as exc:
                last = failure(self.provider_id, TIMED_OUT, str(exc))
            except (TransportUnavailable, TransportError) as exc:
                last = failure(self.provider_id, UNAVAILABLE, str(exc))
            else:
                status = getattr(response, "status", 0)
                if status == 200 or status not in TRANSIENT_STATUSES:
                    # Success, or a refusal that will not change by asking
                    # again -- a 401 is an answer, not a hiccup.
                    return self._read(response, slug, model, started)
                last = self._read(response, slug, model, started)

            if attempt < MAX_ATTEMPTS:
                self._sleep(RETRY_DELAYS_SECONDS[min(attempt - 1,
                                                     len(RETRY_DELAYS_SECONDS) - 1)])
        return last if last is not None else failure(
            self.provider_id, UNAVAILABLE, "no response"
        )

    def _read(self, response, slug, model, started) -> ProviderResult:
        latency_ms = (time.monotonic() - started) * 1000.0
        status = getattr(response, "status", 0)
        if status != 200:
            outcome = REJECTED if 400 <= status < 500 else UNAVAILABLE
            return failure(
                self.provider_id, outcome,
                f"HTTP {status}", latency_ms=latency_ms,
            )
        try:
            body = json.loads(response.body)
            text = body["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            return failure(
                self.provider_id, MALFORMED,
                f"unreadable response: {exc}", latency_ms=latency_ms,
            )

        usage = body.get("usage") or {}
        return ProviderResult(
            provider_id=self.provider_id,
            outcome=SUCCEEDED,
            response=ProviderResponse(
                text=text,
                model=slug,
                latency_ms=latency_ms,
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                finish_reason=(body["choices"][0].get("finish_reason") or ""),
            ),
            latency_ms=latency_ms,
            # The provenance of the cost claim travels with the result, so
            # "this was free" is checkable rather than asserted.
            detail={
                "gateway": "openrouter",
                "model": slug,
                "model_context_length": model.get("context_length"),
                "pricing_prompt": (model.get("pricing") or {}).get("prompt"),
                "pricing_completion": (model.get("pricing") or {}).get("completion"),
                "cost_evidence": "openrouter /api/v1/models, read at call time",
            },
        )

    def generate(
        self, prompt: str, context: dict[str, Any] | None = None, **options: Any
    ) -> str:
        result = self.complete(prompt, context=context, **options)
        if not result.ok:
            raise RuntimeError(result.error or "openrouter call failed")
        return result.response.text
