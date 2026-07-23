"""Model Router — picks which ModelProvider handles a given generation
call. See ARCHITECTURE.md §5. Deliberately a thin policy layer over the
PluginRegistry, not a new source of truth about what providers exist.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from master_agent.plugins.base import ModelProvider
from master_agent.plugins.registry import PluginRegistry


@dataclass
class RoutingContext:
    is_online: bool = True
    is_sensitive: bool = False
    requires_strong_reasoning: bool = False
    preferred_provider: str | None = None  # explicit user override, always wins


class ModelRouter:
    def __init__(self, registry: PluginRegistry, default_provider: str = "hermes") -> None:
        self._registry = registry
        self._default_provider = default_provider

    def select_provider(self, ctx: RoutingContext) -> ModelProvider:
        if ctx.preferred_provider:
            return self._provider(ctx.preferred_provider)

        if not ctx.is_online:
            return self._provider("hermes")

        if ctx.is_sensitive:
            return self._provider("hermes")

        if ctx.requires_strong_reasoning:
            return self._provider("chatgpt")

        return self._provider(self._default_provider)

    def generate(self, prompt: str, ctx: RoutingContext, context: dict[str, Any] | None = None) -> str:
        provider = self.select_provider(ctx)
        return provider.generate(prompt, context)

    def _provider(self, name: str) -> ModelProvider:
        plugin = self._registry.get(name)
        assert isinstance(plugin, ModelProvider), f"{name} is not a ModelProvider"
        return plugin
