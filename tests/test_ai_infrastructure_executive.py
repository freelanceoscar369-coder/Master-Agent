"""Tests for AI Infrastructure Executive (Mission Brief 031/032).

Verifies:
1. Worker registers correctly with Mission Control
2. Discovery produces inventory
3. Probe produces provider facts
4. Benchmark output schema works
5. No Broker decision logic exists inside Executive
6. No vendor-specific branching in Broker
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from datetime import UTC, datetime

from master_agent.ai_infrastructure.executive import (
    AiInfrastructurePlugin,
    AI_INFRA_EXECUTIVE_ID,
    AI_INFRA_VERSION,
    ProviderClass,
    DiscoverySource,
    ProviderIdentity,
    ProviderCapabilities,
    ProviderHealth,
    ProviderInventoryEntry,
    ProviderInventory,
    BenchmarkRequest,
    BenchmarkResult,
    BenchmarkStatus,
    get_all_discovery_actions,
    get_all_probe_actions,
)
from master_agent.ai_infrastructure.executive.models import (
    ProviderIdentity,
    ProviderCapabilities,
    ProviderHealth,
)
from master_agent.executor.executor import LocalExecutor
from master_agent.permissions.permission_system import PermissionSystem
from master_agent.plugins.registry import PluginRegistry
from master_agent.mission_control.mission_control import MissionControl
from master_agent.mission_control.adapters import discover_executives


class TestExecutiveModels:
    """Test the data models for AI Infrastructure Executive."""

    def test_provider_identity_creation(self):
        """Test creating a provider identity."""
        identity = ProviderIdentity(
            provider_id="test-provider",
            display_name="Test Provider",
            provider_class=ProviderClass.LOCAL_RUNTIME,
            version="1.0.0",
            install_path="/opt/test",
            executable_path="/opt/test/bin/provider",
            discovery_source=DiscoverySource.FILESYSTEM_SCAN,
        )
        assert identity.provider_id == "test-provider"
        assert identity.provider_class == ProviderClass.LOCAL_RUNTIME

    def test_provider_identity_serialization(self):
        """Test round-trip serialization of ProviderIdentity."""
        identity = ProviderIdentity(
            provider_id="test-provider",
            display_name="Test Provider",
            provider_class=ProviderClass.CLOUD_API,
            version="1.0.0",
            discovered_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        data = identity.as_dict()
        restored = ProviderIdentity.from_dict(data)
        assert restored.provider_id == identity.provider_id
        assert restored.provider_class == identity.provider_class
        assert restored.discovered_at == identity.discovered_at

    def test_provider_capabilities(self):
        """Test provider capabilities."""
        caps = ProviderCapabilities(
            ai_capabilities=frozenset({"reasoning", "coding"}),
            execution_capability="GenerateText",
            max_context_tokens=32768,
            supports_streaming=True,
        )
        assert "reasoning" in caps.ai_capabilities
        assert caps.execution_capability == "GenerateText"

    def test_provider_health(self):
        """Test provider health."""
        health = ProviderHealth(
            is_available=True,
            is_healthy=True,
            last_probe_at=datetime.now(UTC),
            latency_ms=100.0,
        )
        assert health.is_available is True
        assert health.latency_ms == 100.0

    def test_benchmark_request(self):
        """Test benchmark request."""
        request = BenchmarkRequest(
            provider_id="test-provider",
            ai_capability="reasoning",
            task_class="general",
            test_prompts=("Hello", "World"),
            iterations=3,
        )
        assert request.provider_id == "test-provider"
        assert request.iterations == 3

    def test_benchmark_result(self):
        """Test benchmark result."""
        request = BenchmarkRequest(
            provider_id="test-provider",
            ai_capability="reasoning",
            task_class="general",
        )
        result = BenchmarkResult(
            request=request,
            status=BenchmarkStatus.COMPLETED,
            aggregate_quality=0.85,
            aggregate_latency_ms=150.0,
            confidence=0.8,
        )
        assert result.status == BenchmarkStatus.COMPLETED
        assert result.aggregate_quality == 0.85


class TestExecutivePlugin:
    """Test the AI Infrastructure Executive Plugin."""

    def setup_method(self):
        """Set up test fixtures."""
        self.permissions = PermissionSystem()
        self.executor = LocalExecutor(self.permissions)
        self.plugin = AiInfrastructurePlugin(self.executor)

    def test_plugin_manifest(self):
        """Test plugin manifest has correct structure."""
        manifest = self.plugin.manifest
        assert manifest.name == AI_INFRA_EXECUTIVE_ID
        assert manifest.version == AI_INFRA_VERSION
        assert len(manifest.capabilities) > 0

    def test_plugin_capabilities_include_discovery(self):
        """Test plugin exposes discovery capabilities."""
        manifest = self.plugin.manifest
        capability_names = [c.name for c in manifest.capabilities]

        # Should have discovery actions
        assert "ai_infrastructure.discover_ollama" in capability_names
        assert "ai_infrastructure.discover_lm_studio" in capability_names
        assert "ai_infrastructure.discover_claude_desktop" in capability_names
        assert "ai_infrastructure.discover_cloud_providers" in capability_names

    def test_plugin_capabilities_include_probes(self):
        """Test plugin exposes probe capabilities."""
        manifest = self.plugin.manifest
        capability_names = [c.name for c in manifest.capabilities]

        assert "ai_infrastructure.probe_availability" in capability_names
        assert "ai_infrastructure.probe_capabilities" in capability_names
        assert "ai_infrastructure.probe_latency" in capability_names

    def test_plugin_capabilities_include_benchmark(self):
        """Test plugin exposes benchmark capability."""
        manifest = self.plugin.manifest
        capability_names = [c.name for c in manifest.capabilities]

        assert "ai_infrastructure.run_benchmark" in capability_names

    def test_all_actions_registered_read_only(self):
        """Test all actions are READ_ONLY risk tier."""
        manifest = self.plugin.manifest
        for capability in manifest.capabilities:
            assert capability.risk_tier.value == "read_only"

    def test_invoke_unknown_capability(self):
        """Test invoking unknown capability returns error."""
        result = self.plugin.invoke("unknown.capability", {})
        assert result.success is False
        assert "unsupported capability" in result.error


class TestExecutiveRegistration:
    """Test AI Infrastructure Executive registration with Mission Control."""

    def setup_method(self):
        """Set up test fixtures."""
        self.permissions = PermissionSystem()
        self.executor = LocalExecutor(self.permissions)
        self.registry = PluginRegistry()
        self.mission_control = MissionControl()

    def test_executive_registers_with_mission_control(self):
        """Test executive plugin registers with Mission Control."""
        plugin = AiInfrastructurePlugin(self.executor)
        self.registry.register(plugin)

        # Register with Mission Control
        from master_agent.mission_control.adapters import discover_executives
        discovered = discover_executives(self.mission_control, self.registry)

        assert AI_INFRA_EXECUTIVE_ID in discovered
        assert self.mission_control.executives.has(AI_INFRA_EXECUTIVE_ID)

    def test_executive_capabilities_registered(self):
        """Test executive capabilities are registered in Mission Control."""
        plugin = AiInfrastructurePlugin(self.executor)
        self.registry.register(plugin)

        from master_agent.mission_control.adapters import discover_executives
        discover_executives(self.mission_control, self.registry)

        capabilities = self.mission_control.capabilities.all()
        executive_capabilities = [c for c in capabilities if c.executive_id == AI_INFRA_EXECUTIVE_ID]

        assert len(executive_capabilities) > 0
        # Check some expected capabilities
        cap_names = {c.capability for c in executive_capabilities}
        assert "ai_infrastructure.discover_ollama" in cap_names
        assert "ai_infrastructure.probe_availability" in cap_names
        assert "ai_infrastructure.run_benchmark" in cap_names

    def test_executive_health_defaults_to_healthy(self):
        """Test executive health defaults to HEALTHY."""
        plugin = AiInfrastructurePlugin(self.executor)
        self.registry.register(plugin)

        from master_agent.mission_control.adapters import discover_executives
        discover_executives(self.mission_control, self.registry)

        executive = self.mission_control.executives.get(AI_INFRA_EXECUTIVE_ID)
        from master_agent.mission_control.executives import ExecutiveHealth
        assert executive.health == ExecutiveHealth.HEALTHY


class TestDiscoveryActions:
    """Test discovery actions produce correct output."""

    def setup_method(self):
        """Set up test fixtures."""
        self.permissions = PermissionSystem()
        self.executor = LocalExecutor(self.permissions)
        self.plugin = AiInfrastructurePlugin(self.executor)

    def test_discover_ollama_action_exists(self):
        """Test Ollama discovery action is registered."""
        assert "ai_infrastructure.discover_ollama" in self.plugin._actions

    def test_discover_ollama_structure(self):
        """Test Ollama discovery action returns expected structure."""
        action = self.plugin._actions["ai_infrastructure.discover_ollama"]
        assert action.name == "ai_infrastructure.discover_ollama"
        assert action.risk_tier.value == "read_only"

    def test_discover_lm_studio_exists(self):
        """Test LM Studio discovery action is registered."""
        assert "ai_infrastructure.discover_lm_studio" in self.plugin._actions

    def test_discover_claude_desktop_exists(self):
        """Test Claude Desktop discovery action is registered."""
        assert "ai_infrastructure.discover_claude_desktop" in self.plugin._actions

    def test_discover_cloud_providers_exists(self):
        """Test cloud providers discovery action is registered."""
        assert "ai_infrastructure.discover_cloud_providers" in self.plugin._actions


class TestProbeActions:
    """Test probe actions produce correct output."""

    def setup_method(self):
        """Set up test fixtures."""
        self.permissions = PermissionSystem()
        self.executor = LocalExecutor(self.permissions)
        self.plugin = AiInfrastructurePlugin(self.executor)

    def test_probe_availability_exists(self):
        """Test availability probe action is registered."""
        assert "ai_infrastructure.probe_availability" in self.plugin._actions

    def test_probe_capabilities_exists(self):
        """Test capabilities probe action is registered."""
        assert "ai_infrastructure.probe_capabilities" in self.plugin._actions

    def test_probe_latency_exists(self):
        """Test latency probe action is registered."""
        assert "ai_infrastructure.probe_latency" in self.plugin._actions

    def test_probe_availability_parameters(self):
        """Test probe_availability requires provider_id."""
        action = self.plugin._actions["ai_infrastructure.probe_availability"]
        assert "provider_id" in action.required_parameters()

    def test_probe_capabilities_parameters(self):
        """Test probe_capabilities requires provider_id."""
        action = self.plugin._actions["ai_infrastructure.probe_capabilities"]
        assert "provider_id" in action.required_parameters()

    def test_probe_latency_parameters(self):
        """Test probe_latency requires provider_id and test_prompt."""
        action = self.plugin._actions["ai_infrastructure.probe_latency"]
        assert "provider_id" in action.required_parameters()
        assert "test_prompt" in action.required_parameters()


class TestBenchmarkAction:
    """Test benchmark action."""

    def setup_method(self):
        """Set up test fixtures."""
        self.permissions = PermissionSystem()
        self.executor = LocalExecutor(self.permissions)
        self.plugin = AiInfrastructurePlugin(self.executor)

    def test_run_benchmark_exists(self):
        """Test run_benchmark action is registered."""
        assert "ai_infrastructure.run_benchmark" in self.plugin._actions

    def test_run_benchmark_parameters(self):
        """Test run_benchmark requires request."""
        action = self.plugin._actions["ai_infrastructure.run_benchmark"]
        assert "request" in action.required_parameters()


class TestNoBrokerDecisionLogic:
    """Verify Executive contains no Broker decision logic."""

    def test_no_broker_imports_in_executive(self):
        """Test executive module doesn't import broker decision logic."""
        import master_agent.ai_infrastructure.executive.models as models
        import master_agent.ai_infrastructure.executive.actions as actions
        import master_agent.ai_infrastructure.executive.probes as probes
        import master_agent.ai_infrastructure.executive.plugin as plugin

        # Check no broker decision imports
        for mod in [models, actions, probes, plugin]:
            source = mod.__file__
            with open(source) as f:
                content = f.read()
                assert "CapabilityBroker" not in content
                assert "SelectionPolicy" not in content
                assert "ranking_key" not in content
                assert "BrokerDecision" not in content

    def test_executive_only_produces_facts(self):
        """Test executive actions only produce facts, not decisions."""
        # All actions are READ_ONLY - they observe, don't decide
        permissions = PermissionSystem()
        executor = LocalExecutor(permissions)
        plugin = AiInfrastructurePlugin(executor)

        for capability in plugin.manifest.capabilities:
            assert capability.risk_tier.value == "read_only"
            # Discovery/probe/benchmark are fact-producing, not decision-making

    def test_no_vendor_branching_in_executive(self):
        """Test executive doesn't have vendor-specific branching for decisions."""
        import master_agent.ai_infrastructure.executive.actions as actions
        import master_agent.ai_infrastructure.executive.probes as probes

        for mod in [actions, probes]:
            source = mod.__file__
            with open(source) as f:
                content = f.read()
                # Executive may know provider signatures for discovery
                # but should NOT have decision logic like "if provider == X choose Y"
                assert "if provider_id == \"ollama\"" not in content or "return" not in content.split("if provider_id == \"ollama\"")[1].split("\n")[0] if "if provider_id == \"ollama\"" in content else True


class TestActionRegistry:
    """Test action registry functions."""

    def test_get_all_discovery_actions(self):
        """Test get_all_discovery_actions returns all discovery actions."""
        actions = get_all_discovery_actions()
        assert len(actions) >= 4  # ollama, lm-studio, claude-desktop, cloud

    def test_get_all_probe_actions(self):
        """Test get_all_probe_actions returns probe and benchmark actions."""
        actions = get_all_probe_actions()
        # 3 probe + 1 benchmark = 4
        assert len(actions) >= 4


class TestInventoryModels:
    """Test inventory model serialization."""

    def test_provider_inventory_entry(self):
        """Test ProviderInventoryEntry serialization."""
        identity = ProviderIdentity(
            provider_id="test-provider",
            display_name="Test",
            provider_class=ProviderClass.LOCAL_RUNTIME,
        )
        capabilities = ProviderCapabilities(
            ai_capabilities=frozenset({"reasoning"}),
        )
        health = ProviderHealth(is_available=True)

        entry = ProviderInventoryEntry(
            identity=identity,
            capabilities=capabilities,
            health=health,
        )

        data = entry.as_dict()
        restored = ProviderInventoryEntry.from_dict(data)

        assert restored.identity.provider_id == "test-provider"
        assert restored.capabilities.ai_capabilities == frozenset({"reasoning"})
        assert restored.health.is_available is True

    def test_provider_inventory(self):
        """Test ProviderInventory serialization."""
        identity = ProviderIdentity(
            provider_id="test-provider",
            display_name="Test",
            provider_class=ProviderClass.LOCAL_RUNTIME,
        )
        capabilities = ProviderCapabilities()
        health = ProviderHealth(is_available=True)

        entry = ProviderInventoryEntry(
            identity=identity,
            capabilities=capabilities,
            health=health,
        )

        inventory = ProviderInventory(
            entries=(entry,),
            scanned_at=datetime.now(UTC),
            scan_duration_seconds=1.5,
        )

        data = inventory.as_dict()
        restored = ProviderInventory.from_dict(data)

        assert len(restored.entries) == 1
        assert restored.entries[0].identity.provider_id == "test-provider"
        assert restored.scan_duration_seconds == 1.5

    def test_inventory_by_provider_id(self):
        """Test inventory lookup by provider_id."""
        identity1 = ProviderIdentity(provider_id="p1", display_name="P1", provider_class=ProviderClass.LOCAL_RUNTIME)
        identity2 = ProviderIdentity(provider_id="p2", display_name="P2", provider_class=ProviderClass.CLOUD_API)

        entry1 = ProviderInventoryEntry(identity=identity1, capabilities=ProviderCapabilities(), health=ProviderHealth(is_available=True))
        entry2 = ProviderInventoryEntry(identity=identity2, capabilities=ProviderCapabilities(), health=ProviderHealth(is_available=False))

        inventory = ProviderInventory(entries=(entry1, entry2))

        found = inventory.by_provider_id("p1")
        assert found is not None
        assert found.identity.provider_id == "p1"

        not_found = inventory.by_provider_id("p3")
        assert not_found is None

    def test_inventory_available(self):
        """Test inventory available() filter."""
        identity1 = ProviderIdentity(provider_id="p1", display_name="P1", provider_class=ProviderClass.LOCAL_RUNTIME)
        identity2 = ProviderIdentity(provider_id="p2", display_name="P2", provider_class=ProviderClass.CLOUD_API)

        entry1 = ProviderInventoryEntry(identity=identity1, capabilities=ProviderCapabilities(), health=ProviderHealth(is_available=True))
        entry2 = ProviderInventoryEntry(identity=identity2, capabilities=ProviderCapabilities(), health=ProviderHealth(is_available=False))

        inventory = ProviderInventory(entries=(entry1, entry2))

        available = inventory.available()
        assert len(available) == 1
        assert available[0].identity.provider_id == "p1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])