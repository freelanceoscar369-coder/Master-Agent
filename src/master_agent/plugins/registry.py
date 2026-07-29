"""Plugin discovery and lookup.

Founder Edition scope: plugins are local Python objects registered at
startup (see ADR-0004 — no marketplace/installer needed yet). The registry
is still the only thing the Orchestrator and Model Router talk to, so
swapping this for a dynamic-discovery mechanism later doesn't touch either
of them.
"""
from __future__ import annotations

from master_agent.plugins.base import Plugin, RiskTier


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}
        self._capability_index: dict[str, list[str]] = {}  # capability -> [plugin names]

    def register(self, plugin: Plugin) -> None:
        manifest = plugin.manifest
        if manifest.name in self._plugins:
            raise ValueError(f"plugin already registered: {manifest.name}")
        self._plugins[manifest.name] = plugin
        for cap in manifest.capabilities:
            self._capability_index.setdefault(cap.name, []).append(manifest.name)

    def get(self, plugin_name: str) -> Plugin:
        return self._plugins[plugin_name]

    def find_for_capability(self, capability: str) -> list[Plugin]:
        return [self._plugins[name] for name in self._capability_index.get(capability, [])]

    def all_plugins(self) -> list[Plugin]:
        """Every registered plugin, in registration order.

        Added for MIT-001 so Mission Control can *discover* what is
        installed rather than being handed a hardcoded list. Deliberately
        a read-only accessor on the existing contract rather than letting
        a caller reach into `_plugins` — "extend the contract, don't route
        around it" (ENGINEERING_PRINCIPLES.md #8). Nothing about existing
        callers changes.
        """
        return list(self._plugins.values())

    def risk_tier_for(self, plugin_name: str, capability: str) -> RiskTier:
        manifest = self._plugins[plugin_name].manifest
        for cap in manifest.capabilities:
            if cap.name == capability:
                return cap.risk_tier
        raise KeyError(f"{plugin_name} does not expose capability {capability}")
