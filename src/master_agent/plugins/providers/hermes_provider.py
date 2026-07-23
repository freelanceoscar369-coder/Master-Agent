"""Hermes model provider — local-first, via Ollama's OpenAI-compatible
endpoint (see ADR-0002). This is the provider the Model Router falls back
to when offline or when the Intent Layer flags sensitive context.
"""
from __future__ import annotations

from typing import Any

from master_agent.plugins.base import (
    CapabilityManifest,
    ModelProvider,
    PluginManifest,
    RiskTier,
)


class HermesProvider(ModelProvider):
    def __init__(self, base_url: str = "http://localhost:11434/v1", model: str = "hermes3") -> None:
        self._base_url = base_url
        self._model = model
        # Real client construction (httpx.Client or openai.OpenAI(base_url=...))
        # deferred until wired up — see ChatGPTProvider for the same reasoning.
        self._client: Any = None

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="hermes",
            version="0.1.0",
            capabilities=[
                CapabilityManifest(
                    name=self.CAPABILITY_NAME,
                    description="Generate text via a local Hermes model served by Ollama.",
                    risk_tier=RiskTier.READ_ONLY,
                ),
            ],
        )

    def generate(self, prompt: str, context: dict[str, Any] | None = None, **opts: Any) -> str:
        raise NotImplementedError(
            "Wire up the local Ollama call here (POST {base_url}/chat/completions). "
            "Kept stubbed so the scaffold imports cleanly without Ollama running."
        )
