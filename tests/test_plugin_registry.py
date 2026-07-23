"""Exercises the two contracts everything else depends on: the Plugin
Registry (capability -> plugin resolution) and the Permission System gate.
If these break, every other module breaks with them — worth testing first.
"""
from __future__ import annotations

import pytest

from master_agent.orchestrator.orchestrator import Orchestrator
from master_agent.permissions.permission_system import GrantScope, PermissionSystem
from master_agent.planner.planner import Step
from master_agent.plugins.base import (
    CapabilityManifest,
    InvocationResult,
    Plugin,
    PluginManifest,
    RiskTier,
)
from master_agent.plugins.registry import PluginRegistry


class FakeCalendarPlugin(Plugin):
    """A minimal capability plugin used only to exercise the registry and
    orchestrator without depending on a real model provider.
    """

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="fake_calendar",
            version="0.0.1",
            capabilities=[
                CapabilityManifest(
                    name="list_events",
                    description="List calendar events (read-only).",
                    risk_tier=RiskTier.READ_ONLY,
                ),
                CapabilityManifest(
                    name="delete_event",
                    description="Delete a calendar event (irreversible).",
                    risk_tier=RiskTier.IRREVERSIBLE,
                ),
            ],
        )

    def invoke(self, capability: str, payload: dict) -> InvocationResult:
        return InvocationResult(success=True, output=f"did {capability}")


def build_registry() -> PluginRegistry:
    registry = PluginRegistry()
    registry.register(FakeCalendarPlugin())
    return registry


def test_registry_resolves_capability_to_plugin():
    registry = build_registry()
    matches = registry.find_for_capability("list_events")
    assert len(matches) == 1
    assert matches[0].manifest.name == "fake_calendar"


def test_registry_raises_on_duplicate_plugin_name():
    registry = build_registry()
    with pytest.raises(ValueError):
        registry.register(FakeCalendarPlugin())


def test_read_only_step_executes_without_approval():
    registry = build_registry()
    permissions = PermissionSystem()
    orchestrator = Orchestrator(registry, permissions)

    step = Step(step_id="s1", capability="list_events", payload={})
    result = orchestrator.execute_step(step)

    assert not result.blocked_on_approval
    assert result.result is not None
    assert result.result.success


def test_irreversible_step_blocks_until_granted():
    registry = build_registry()
    permissions = PermissionSystem()
    orchestrator = Orchestrator(registry, permissions)

    step = Step(step_id="s2", capability="delete_event", payload={})

    blocked = orchestrator.execute_step(step)
    assert blocked.blocked_on_approval

    permissions.grant("fake_calendar", "delete_event", GrantScope.ONCE)
    allowed = orchestrator.execute_step(step)
    assert not allowed.blocked_on_approval
    assert allowed.result.success
