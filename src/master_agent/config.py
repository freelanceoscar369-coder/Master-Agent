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
    default_provider: str = "hermes"  # local-first by default
    chatgpt_model: str = "gpt-4.1"
    hermes_model: str = "hermes3"  # confirm exact checkpoint before build (see ADR-0002)
    hermes_base_url: str = "http://localhost:11434/v1"  # Ollama's OpenAI-compatible endpoint


@dataclass
class MasterAgentConfig:
    """Root config. `app_dir` is where local memory, logs, and plugin state live."""

    app_dir: Path = field(default_factory=lambda: Path.home() / ".master_agent")
    model_router: ModelRouterConfig = field(default_factory=ModelRouterConfig)
    require_approval_above: str = "read_only"  # risk tiers gated by the Permission System


def load_config() -> MasterAgentConfig:
    """Load config. Founder Edition: defaults only. Extend to read a TOML/env
    override file once there's more than one person configuring this."""
    return MasterAgentConfig()
