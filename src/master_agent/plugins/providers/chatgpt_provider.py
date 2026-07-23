"""ChatGPT model provider — cloud, opt-in via the Model Router (ARCHITECTURE.md §5)."""
from __future__ import annotations

from typing import Any

from master_agent.plugins.base import (
    CapabilityManifest,
    ModelProvider,
    PluginManifest,
    RiskTier,
)


class ChatGPTProvider(ModelProvider):
    def __init__(self, api_key: str, model: str = "gpt-4.1") -> None:
        self._api_key = api_key
        self._model = model
        # Real client construction (openai.OpenAI(api_key=...)) deferred until
        # this stub is wired up — kept out so importing this module never
        # requires network/credentials.
        self._client: Any = None

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="chatgpt",
            version="0.1.0",
            capabilities=[
                CapabilityManifest(
                    name=self.CAPABILITY_NAME,
                    description="Generate text via OpenAI ChatGPT (cloud).",
                    risk_tier=RiskTier.READ_ONLY,  # generation itself is read-only;
                    # any side effect it recommends still needs its own capability + risk tier
                ),
            ],
        )

    def generate(self, prompt: str, context: dict[str, Any] | None = None, **opts: Any) -> str:
        raise NotImplementedError(
            "Wire up the OpenAI client here. Kept stubbed so the scaffold "
            "imports cleanly without an API key present."
        )
