"""Central config. Deliberately tiny and explicit — no hidden env magic.

Every module that needs a setting should import from here rather than
reading os.environ directly, so all configurable knobs are discoverable in
one file.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ModelRouterConfig:
    """How to *reach* a provider, never which one to use.

    `default_provider` used to live here and was deleted by MB032: choosing
    a provider is the AI Capability Broker's job now (ADR-0017, Constitution
    Amendment 2 §3.3), and a default sitting in configuration is the same
    hardcoded ladder in a different file. What remains is connection detail
    — the endpoint and model name a provider plugin needs once it has
    already been selected.
    """

    chatgpt_model: str = "gpt-4.1"
    hermes_model: str = "hermes3"  # confirm exact checkpoint before build (see ADR-0002)
    hermes_base_url: str = "http://localhost:11434/v1"  # Ollama's OpenAI-compatible endpoint


@dataclass
class BrokerConfig:
    """AI Capability Broker settings (Mission Brief 032).

    Three knobs, all founder-facing. `policy` names one of the eight
    shipped `SelectionPolicy` objects — the *policy* is what evolves
    (ADR-0018 Decision 1), never the engine reading it.

    `strong_reasoning_min_quality` is the quality floor a request asking
    for strong reasoning raises the bar to. It replaces
    `ModelRouter.select_provider()`'s old `return self._provider("chatgpt")`
    branch: "I need this done well" is a statement about *quality*, and
    turning it into a product name was the bug.

    `enabled_cloud_providers` is empty by default, so a provider that needs
    credentials is reported unavailable until the founder says otherwise.
    Absence of a key is a fact, not a reason to try anyway.
    """

    policy: str = "balanced"
    strong_reasoning_min_quality: float = 0.8
    enabled_cloud_providers: tuple[str, ...] = ()


@dataclass
class OllamaConfig:
    """How to reach the local Ollama daemon (Mission Brief 033).

    `model` is **configuration, never a choice** — nothing in Kalpavriksha
    picks a checkpoint. ADR-0002 selected Hermes as the local model, so
    that is the default; a founder running something else changes this one
    line, and a model that is not installed produces a structured failure
    naming the ones that are, rather than a stack trace.

    `enabled` is separate from "is Ollama installed": the Desktop
    Executive answers the second, and this answers "should Kalpavriksha
    run prompts through it". Both must be true.
    """

    enabled: bool = True
    base_url: str = "http://localhost:11434"
    model: str = "hermes3"
    #: Long on purpose: a local model on a laptop CPU genuinely takes this
    #: long, and a timeout shorter than the work turns a working system
    #: into a broken-looking one.
    #: MB038 demoted this to the **provider ceiling** and the health-probe
    #: timeout. A budgeted call ignores it entirely and is held to three
    #: derived deadlines instead. It is no longer the number planning waits
    #: on -- being both was the defect MB036 and MB037 hit.
    timeout_seconds: float = 120.0
    # `max_attempts` and `retry_delay_seconds` were removed by MB038. The
    # adapter no longer retries anything: retry belongs to the layer that
    # owns the failure's meaning, and that is the Runtime (MB024), which
    # keeps its own `max_attempts` in `runtime/config.py`.


@dataclass
class PromptCacheConfig:
    """Whether to reuse work already done (Mission Brief 033 Rule 2).

    **On since MB035**, because the reason it was off is gone: a verifier
    for generated text now exists, and the cache only ever stores an
    answer that was checked against an `ExpectedOutcome` stated in
    advance. A request that asks for nothing specific still stores
    nothing — so turning this on makes reuse *reachable* without making
    anything unverified cacheable.

    `store_unverified` remains off, and is the one switch that would undo
    all of that: it lets the cache remember work nobody checked, which is
    how a wrong answer starts repeating faster.
    """

    enabled: bool = True
    store_unverified: bool = False


@dataclass
class ClockConfig:
    """The one canonical timezone source (VEDA 04 §7).

    `founder_timezone` is what "Friday 00:00" means. It is configuration
    and **never the machine's local setting** — a laptop that travels would
    otherwise silently change when a subscription renews, and §7 forbids
    ambient local time anywhere in the decision path.

    The default is `UTC` rather than the system zone on purpose. UTC is
    wrong for most founders, but it is wrong *visibly and identically on
    every machine*; a system-local default would be wrong invisibly and
    differently on each one. Set it once, deliberately.

    Storage is always UTC regardless of this setting. This affects only
    what the founder is told.
    """

    founder_timezone: str = "UTC"


@dataclass
class MasterAgentConfig:
    """Root config. `app_dir` is where local memory, logs, and plugin state live."""

    app_dir: Path = field(default_factory=lambda: Path.home() / ".master_agent")
    clock: ClockConfig = field(default_factory=ClockConfig)
    model_router: ModelRouterConfig = field(default_factory=ModelRouterConfig)
    broker: BrokerConfig = field(default_factory=BrokerConfig)
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    prompt_cache: PromptCacheConfig = field(default_factory=PromptCacheConfig)
    require_approval_above: str = "read_only"  # risk tiers gated by the Permission System


def load_config() -> MasterAgentConfig:
    """Load config. Founder Edition: defaults only. Extend to read a TOML/env
    override file once there's more than one person configuring this."""
    return MasterAgentConfig()
