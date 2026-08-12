"""What intelligences might exist on this machine (Mission Brief 032).

**This is the one file in Kalpavriksha permitted to name a provider.**
Everything above it — the Model Router, the Runtime, Mission Control, the
Dashboard — speaks in AI Capabilities (`reasoning`) and provider ids
handed to it by a `DecisionRecord`. Everything below it — `broker/` — is
provider-agnostic by architecture and enforced by a vendor-name grep
(ADR-0017, MB031 §2).

The same shape `desktop/catalog.py` uses: adding a provider is one entry
and nothing else changes.

## Every number here is *declared*, and none of them is measured

`ProviderProfile` deliberately separates `quality` (what a provider claims)
from `benchmark` (what this system measured), and measurement wins where
both exist (ADR-0017 Decision 5). **No benchmark store exists yet**, so
every profile built from this catalogue carries `benchmark=None` and the
declared number is what ranks it. Each entry states its `basis` so a
reader can see it is a first guess rather than evidence, and the Dashboard
labels the tier `declared` rather than letting it read as a measurement.

The founder can edit these. The Broker records which values produced every
decision, so changing one does not silently rewrite history.

## What a "provider" is here

A **runtime or service**, not a model: `ollama.local` is the local runtime,
whatever checkpoint it happens to be serving. Per-model profiles (this
weight class versus that one on the same runtime) need the benchmark store
to tell them apart, and are named in MB032's debt list rather than
invented here.
"""
from __future__ import annotations

from dataclasses import dataclass

# Localities and privacy classes, mirrored from `broker.profiles` as plain
# strings. Mirrored rather than imported so this module stays readable as a
# data file; `tests/test_broker_integration.py` asserts the two vocabularies
# have not drifted apart.
LOCAL = "local"
DESKTOP = "desktop"
CLOUD = "cloud"
PRIVATE = "private"
THIRD_PARTY = "third_party"

#: The AI Capability every reasoning request asks for. `lowercase.dotted`,
#: per ADR-0017 Decision 8 — distinguishable *mechanically* from a
#: Constitution Capability (`Filesystem.CreateFolder`), which is
#: `PascalCase.PascalCase`.
REASONING = "reasoning"
PLANNING = "reasoning.planning"
CODING = "coding"


@dataclass(frozen=True)
class ProviderSpec:
    """One intelligence Kalpavriksha knows how to describe.

    `inventory_key` is the join to `desktop/catalog.py`: when it is set,
    whether this provider is *available* is read from the Desktop
    Executive's last machine scan rather than assumed here (MB032
    Deliverable 3). When it is None, the provider is a remote service and
    presence is a question about credentials instead.
    """

    provider_id: str
    label: str
    capabilities: frozenset[str]
    locality: str
    privacy: str
    #: Declared quality, 0..1. See the module docstring: not a measurement.
    declared_quality: float
    #: Marginal cost of one call, in whatever unit the founder keeps
    #: consistently. 0.0 means this call costs nothing *extra*.
    cost_per_call: float
    latency_ms: float | None = None
    requires_network: bool = True
    max_context_tokens: int | None = None
    #: A key in `desktop.catalog.BY_KEY`, or None for a remote service.
    inventory_key: str | None = None
    #: True when the provider cannot be reached without a credential the
    #: founder has to supply. Unavailable until they do.
    needs_credentials: bool = False
    #: True when *using this provider at all* is a founder decision that
    #: has not been made — the Broker then never selects it (ADR-0017
    #: Decision 2). Distinct from being paid: a paid provider is
    #: selectable and gated afterwards, at the Approval Queue.
    requires_approval: bool = False
    basis: str = ""
    notes: str = ""
    # ---- MB038 throughput ------------------------------------------------
    #
    # `None` means **not measured on this machine**. Only a provider that
    # has actually been timed here carries numbers; everything else stays
    # unknown and the Broker falls back to the class ceiling rather than
    # pretending to derive a budget from a figure nobody measured.
    #
    # These belong to a *provider on a machine*, not to the class table:
    # the same model is several times faster on a GPU box, and a shared
    # constant would be wrong everywhere except the laptop it came from.
    prefill_tokens_per_second: float | None = None
    decode_tokens_per_second: float | None = None
    expected_itl_ms: float | None = None
    supports_streaming: bool = False
    #: Characters per token for this provider's tokenizer, measured.
    #: Without it a prompt cannot be turned into the token count the rates
    #: are expressed in, so the deriver treats the provider as unsized.
    chars_per_token: float | None = None
    #: True when the provider runs one call at a time. Declared, not
    #: measured: a local runtime serialises per model, a hosted API does
    #: not.
    serialises: bool = False
    #: MB038A. How long this provider takes to get the model into memory
    #: before any work starts. **Neither prefill nor decode** -- it does
    #: not scale with the prompt and no rate represents it, which is why
    #: the acceptance run failed: a cold call spent longer loading than
    #: the whole budget allowed.
    #:
    #: Always added to the prefill estimate, because nothing tracks
    #: whether a model is currently resident. Budgeting every call as
    #: though it were cold over-waits on warm calls and never under-waits
    #: on cold ones -- and under-waiting is the failure that reports a
    #: healthy provider as broken.
    #:
    #: `None` means not measured, and adds nothing.
    model_load_ms: float | None = None


DECLARED = (
    "declared, unmeasured (MB032). Replaced by a benchmark when ADR-0017's "
    "benchmark store exists"
)


PROVIDER_CATALOG: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        provider_id="claude-desktop",
        label="Claude Desktop",
        capabilities=frozenset({REASONING, PLANNING, CODING}),
        locality=DESKTOP,
        privacy=THIRD_PARTY,
        declared_quality=0.90,
        # Zero *marginal* cost: an installed desktop application runs on a
        # subscription that is already paid, so one more call costs
        # nothing extra. That is what `cost` measures (ADR-0017's
        # "existing subscription" rung sits below "paid API" for exactly
        # this reason). It is still a third party, which is why sensitive
        # work never reaches it under any policy that requires privacy.
        cost_per_call=0.0,
        latency_ms=3000.0,
        max_context_tokens=200_000,
        inventory_key="claude_desktop",
        basis=DECLARED,
        notes="installed desktop application; runs on an existing subscription",
    ),
    ProviderSpec(
        provider_id="lm-studio.local",
        label="LM Studio",
        capabilities=frozenset({REASONING, CODING}),
        locality=LOCAL,
        privacy=PRIVATE,
        declared_quality=0.70,
        cost_per_call=0.0,
        latency_ms=5000.0,
        requires_network=False,
        max_context_tokens=32_768,
        inventory_key="lm_studio",
        basis=DECLARED,
        notes="local runtime; nothing leaves the machine",
    ),
    ProviderSpec(
        provider_id="ollama.local",
        label="Ollama",
        capabilities=frozenset({REASONING, CODING}),
        locality=LOCAL,
        privacy=PRIVATE,
        declared_quality=0.72,
        cost_per_call=0.0,
        latency_ms=4000.0,
        requires_network=False,
        max_context_tokens=32_768,
        inventory_key="ollama",
        basis=DECLARED,
        notes="local runtime; nothing leaves the machine",
        # MB038A. **Re-measured in the planning regime** after acceptance
        # failed. The Step 0 figures (20 prefill, 12 decode) came from
        # 24-token completions on short prompts and did not extrapolate:
        # a real planning call is ~1100 tokens in and ~1000 out.
        #
        # Measured 2026-07-31 against `gemma4:latest`, cold:
        #     load_duration      33.4 s
        #     observed TTFT     136.9 s   (1095 prompt tokens)
        #     eval              165.0 s   for 834 tokens
        #
        # **Calibrated on observed wall-clock TTFT, not on the daemon's
        # `prompt_eval_duration`.** The daemon reported 45.3 s of prefill
        # but the caller waited 103.5 s after load for the first token --
        # a 58 s gap this brief did not explain. Budgeting against the
        # internal counter would have under-budgeted by more than half,
        # and under-budgeting is the failure that calls a healthy provider
        # broken. What we must cover is what the caller waits.
        #
        #     prefill  (136.9 - 33.4) s / 1095 tok = 10.6 tok/s -> 10
        #     decode                  834 / 165.0  =  5.1 tok/s -> 4
        #                             1115 / 238.6 =  4.7 tok/s
        #
        # Rates rounded **down** and load rounded **up**: an optimistic
        # rate yields a budget that is too small, which is the failure
        # mode MB036, MB037 and MB038 acceptance all hit.
        prefill_tokens_per_second=10.0,
        decode_tokens_per_second=4.0,
        # Observed 238.6 s across 1115 tokens = 214 ms between tokens.
        # The class floor (5 s) is what actually binds; this is recorded
        # because it is true, not because it decides anything.
        expected_itl_ms=200.0,
        # Measured directly from the daemon's own `load_duration` on a
        # cold start. Neither prefill nor decode, and modelled nowhere
        # before MB038A -- the acceptance run spent longer here than its
        # entire budget allowed.
        model_load_ms=35_000.0,
        supports_streaming=True,
        # Measured in the same spike: 1600 words of prose reported
        # `prompt_eval_count` 1831, which is ~4.8 characters per token.
        # Rounded **down**, because fewer characters per token means more
        # tokens, which means a larger prefill estimate -- erring toward
        # the budget that does not report a healthy provider as broken.
        chars_per_token=4.0,
        # A local runtime holds the model for one call at a time, so a
        # second request queues behind the first rather than running
        # beside it.
        serialises=True,
    ),
    ProviderSpec(
        provider_id="openai.api",
        label="OpenAI API",
        capabilities=frozenset({REASONING, PLANNING, CODING}),
        locality=CLOUD,
        privacy=THIRD_PARTY,
        declared_quality=0.92,
        cost_per_call=0.02,
        latency_ms=1500.0,
        max_context_tokens=128_000,
        needs_credentials=True,
        basis=DECLARED,
        notes="metered API; every call spends money",
    ),
    ProviderSpec(
        provider_id="gemini.api",
        label="Gemini API",
        capabilities=frozenset({REASONING, PLANNING, CODING}),
        locality=CLOUD,
        privacy=THIRD_PARTY,
        declared_quality=0.88,
        # Founder decision: selected specifically for its free API tier.
        # Zero *marginal* cost describes that tier, the same way
        # claude-desktop's 0.0 describes an existing subscription rather
        # than a claim that every possible usage is free.
        cost_per_call=0.0,
        latency_ms=2000.0,
        max_context_tokens=1_000_000,
        needs_credentials=True,
        basis=DECLARED,
        notes=(
            "REST API; requires GEMINI_API_KEY; free tier as of this "
            "writing — see GeminiConfig for the model default"
        ),
    ),
    ProviderSpec(
        provider_id="openrouter.api",
        label="OpenRouter",
        capabilities=frozenset({REASONING, CODING}),
        locality=CLOUD,
        privacy=THIRD_PARTY,
        declared_quality=0.85,
        cost_per_call=0.005,
        latency_ms=2000.0,
        max_context_tokens=128_000,
        needs_credentials=True,
        basis=DECLARED,
        notes="metered aggregator; every call spends money",
    ),
)

BY_PROVIDER_ID = {spec.provider_id: spec for spec in PROVIDER_CATALOG}


def find(provider_id: str) -> ProviderSpec | None:
    return BY_PROVIDER_ID.get((provider_id or "").strip())


def inventory_backed() -> tuple[ProviderSpec, ...]:
    """Specs whose availability is a question for the machine scan rather
    than for configuration."""
    return tuple(spec for spec in PROVIDER_CATALOG if spec.inventory_key)


def credentialled() -> tuple[ProviderSpec, ...]:
    return tuple(spec for spec in PROVIDER_CATALOG if spec.needs_credentials)
