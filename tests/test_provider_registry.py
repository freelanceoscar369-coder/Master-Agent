"""Tests for the Persistent Provider Registry (Mission Brief 031 Deliverable 2)."""
from __future__ import annotations

import pytest
from datetime import UTC, datetime, timedelta

from master_agent.broker.registry import (
    ProviderRegistry,
    ProviderDescriptor,
    ProviderHealth,
    RegistrationProvenance,
)
from master_agent.broker.profiles import ProviderProfile


class TestProviderDescriptor:
    """Test the ProviderDescriptor dataclass."""

    def test_descriptor_creation(self):
        """Test creating a provider descriptor."""
        descriptor = ProviderDescriptor(
            provider_id="test-provider",
            display_name="Test Provider",
            provider_class="local_runtime",
            capabilities=frozenset({"reasoning", "coding"}),
            execution_capability="GenerateText",
            cost_per_call=0.0,
            locality="local",
            privacy="private",
            declared_quality=0.8,
        )
        assert descriptor.provider_id == "test-provider"
        assert descriptor.effective_quality == 0.8
        assert descriptor.serves("reasoning")
        assert descriptor.serves("coding")
        assert not descriptor.serves("vision")

    def test_effective_quality_uses_benchmark(self):
        """Measured benchmark beats declared quality."""
        descriptor = ProviderDescriptor(
            provider_id="test",
            display_name="Test",
            provider_class="local_runtime",
            declared_quality=0.5,
            benchmark=0.9,
            benchmark_confidence=0.8,
        )
        assert descriptor.effective_quality == 0.9

    def test_descriptor_to_profile(self):
        """Test conversion to ProviderProfile for Broker."""
        descriptor = ProviderDescriptor(
            provider_id="test-provider",
            display_name="Test Provider",
            provider_class="local_runtime",
            capabilities=frozenset({"reasoning"}),
            cost_per_call=0.0,
            locality="local",
            privacy="private",
            declared_quality=0.8,
            requires_network=False,
        )
        profile = descriptor.to_profile()
        assert isinstance(profile, ProviderProfile)
        assert profile.provider_id == "test-provider"
        assert profile.capabilities == frozenset({"reasoning"})
        assert profile.cost == 0.0
        assert profile.locality == "local"
        assert profile.privacy == "private"

    def test_descriptor_serialization(self):
        """Test round-trip serialization."""
        descriptor = ProviderDescriptor(
            provider_id="test-provider",
            display_name="Test Provider",
            provider_class="local_runtime",
            capabilities=frozenset({"reasoning"}),
            cost_per_call=0.0,
            locality="local",
            privacy="private",
            declared_quality=0.8,
            registered_at=datetime(2026, 1, 1, tzinfo=UTC),
            verified_at=datetime(2026, 1, 2, tzinfo=UTC),
            health=ProviderHealth.HEALTHY,
        )
        data = descriptor.as_dict()
        restored = ProviderDescriptor.from_dict(data)
        assert restored.provider_id == descriptor.provider_id
        assert restored.capabilities == descriptor.capabilities
        assert restored.registered_at == descriptor.registered_at
        assert restored.verified_at == descriptor.verified_at
        assert restored.health == descriptor.health


class TestProviderRegistry:
    """Test the ProviderRegistry."""

    def test_register_new_provider(self):
        """Test registering a new provider."""
        registry = ProviderRegistry()
        descriptor = ProviderDescriptor(
            provider_id="test-provider",
            display_name="Test Provider",
            provider_class="local_runtime",
            capabilities=frozenset({"reasoning"}),
        )
        registered = registry.register(descriptor)
        assert registered.provider_id == "test-provider"
        assert registry.get("test-provider") is not None
        assert len(registry.all()) == 1

    def test_register_idempotent(self):
        """Test that re-registering updates the descriptor."""
        registry = ProviderRegistry()
        descriptor1 = ProviderDescriptor(
            provider_id="test-provider",
            display_name="Test Provider v1",
            provider_class="local_runtime",
            declared_quality=0.7,
        )
        descriptor2 = ProviderDescriptor(
            provider_id="test-provider",
            display_name="Test Provider v2",
            provider_class="local_runtime",
            declared_quality=0.8,
        )
        registry.register(descriptor1)
        # Get the registered_at from the first registration
        first_registered_at = registry.get("test-provider").registered_at
        registered = registry.register(descriptor2)
        assert registered.display_name == "Test Provider v2"
        assert registered.declared_quality == 0.8
        # Original registration time preserved
        assert registered.registered_at == first_registered_at
        # But verified_at updated (or at least not before registration)
        assert registered.verified_at >= first_registered_at
        assert len(registry.all()) == 1

    def test_unregister(self):
        """Test unregistering a provider."""
        registry = ProviderRegistry()
        descriptor = ProviderDescriptor(
            provider_id="test-provider",
            display_name="Test Provider",
            provider_class="local_runtime",
        )
        registry.register(descriptor)
        assert registry.unregister("test-provider") is True
        assert registry.get("test-provider") is None
        assert len(registry.all()) == 0
        assert registry.unregister("test-provider") is False  # Already gone

    def test_get_nonexistent(self):
        """Test getting a non-existent provider returns None."""
        registry = ProviderRegistry()
        assert registry.get("nonexistent") is None

    def test_all_sorted(self):
        """Test all() returns providers sorted by provider_id."""
        registry = ProviderRegistry()
        registry.register(ProviderDescriptor(
            provider_id="zebra", display_name="Z", provider_class="local_runtime",
        ))
        registry.register(ProviderDescriptor(
            provider_id="alpha", display_name="A", provider_class="local_runtime",
        ))
        registry.register(ProviderDescriptor(
            provider_id="beta", display_name="B", provider_class="local_runtime",
        ))
        ids = [d.provider_id for d in registry.all()]
        assert ids == ["alpha", "beta", "zebra"]

    def test_available_filters_health(self):
        """Test available() only returns healthy/degraded providers."""
        registry = ProviderRegistry()
        healthy = ProviderDescriptor(
            provider_id="healthy", display_name="H", provider_class="local_runtime",
            health=ProviderHealth.HEALTHY,
        )
        degraded = ProviderDescriptor(
            provider_id="degraded", display_name="D", provider_class="local_runtime",
            health=ProviderHealth.DEGRADED,
        )
        unreachable = ProviderDescriptor(
            provider_id="unreachable", display_name="U", provider_class="local_runtime",
            health=ProviderHealth.UNREACHABLE,
        )
        unverified = ProviderDescriptor(
            provider_id="unverified", display_name="V", provider_class="local_runtime",
            health=ProviderHealth.UNVERIFIED,
        )
        registry.register(healthy)
        registry.register(degraded)
        registry.register(unreachable)
        registry.register(unverified)

        available = registry.available()
        assert len(available) == 2
        assert {d.provider_id for d in available} == {"healthy", "degraded"}

    def test_by_capability(self):
        """Test filtering by capability."""
        registry = ProviderRegistry()
        registry.register(ProviderDescriptor(
            provider_id="p1", display_name="P1", provider_class="local_runtime",
            capabilities=frozenset({"reasoning", "coding"}),
        ))
        registry.register(ProviderDescriptor(
            provider_id="p2", display_name="P2", provider_class="local_runtime",
            capabilities=frozenset({"reasoning"}),
        ))
        registry.register(ProviderDescriptor(
            provider_id="p3", display_name="P3", provider_class="local_runtime",
            capabilities=frozenset({"vision.ocr"}),
        ))

        reasoning = registry.by_capability("reasoning")
        assert len(reasoning) == 2
        assert {d.provider_id for d in reasoning} == {"p1", "p2"}

        # Prefix match
        reasoning_planning = registry.by_capability("reasoning.planning")
        assert len(reasoning_planning) == 0  # None declare this exactly

    def test_by_capability_prefix_match(self):
        """Test prefix matching for capabilities."""
        registry = ProviderRegistry()
        registry.register(ProviderDescriptor(
            provider_id="p1", display_name="P1", provider_class="local_runtime",
            capabilities=frozenset({"vision.ocr", "vision.detection"}),
        ))

        vision = registry.by_capability("vision")
        assert len(vision) == 1

    def test_by_provenance(self):
        """Test filtering by registration provenance."""
        registry = ProviderRegistry()
        registry.register(ProviderDescriptor(
            provider_id="declared", display_name="D", provider_class="local_runtime",
            provenance=RegistrationProvenance.DECLARED,
        ))
        registry.register(ProviderDescriptor(
            provider_id="discovered", display_name="D", provider_class="local_runtime",
            provenance=RegistrationProvenance.DISCOVERED,
        ))
        registry.register(ProviderDescriptor(
            provider_id="self_reg", display_name="S", provider_class="local_runtime",
            provenance=RegistrationProvenance.SELF_REGISTERED,
        ))

        declared = registry.by_provenance(RegistrationProvenance.DECLARED)
        assert len(declared) == 1
        assert declared[0].provider_id == "declared"

    def test_by_class(self):
        """Test filtering by provider class."""
        registry = ProviderRegistry()
        registry.register(ProviderDescriptor(
            provider_id="local1", display_name="L1", provider_class="local_runtime",
        ))
        registry.register(ProviderDescriptor(
            provider_id="local2", display_name="L2", provider_class="local_runtime",
        ))
        registry.register(ProviderDescriptor(
            provider_id="cloud1", display_name="C1", provider_class="cloud_api",
        ))

        local = registry.by_class("local_runtime")
        assert len(local) == 2

    def test_update_health(self):
        """Test updating provider health."""
        registry = ProviderRegistry()
        descriptor = ProviderDescriptor(
            provider_id="test", display_name="Test", provider_class="local_runtime",
            health=ProviderHealth.UNVERIFIED,
        )
        registry.register(descriptor)
        assert registry.update_health("test", ProviderHealth.HEALTHY) is True
        assert registry.get("test").health == ProviderHealth.HEALTHY
        assert registry.update_health("nonexistent", ProviderHealth.HEALTHY) is False

    def test_update_benchmark(self):
        """Test updating provider benchmark."""
        registry = ProviderRegistry()
        descriptor = ProviderDescriptor(
            provider_id="test", display_name="Test", provider_class="local_runtime",
            declared_quality=0.5,
            benchmark=None,
            benchmark_confidence=0.0,
        )
        registry.register(descriptor)
        assert registry.update_benchmark("test", 0.9, 0.8) is True
        updated = registry.get("test")
        assert updated.benchmark == 0.9
        assert updated.benchmark_confidence == 0.8
        assert updated.effective_quality == 0.9  # Benchmark beats declared

    def test_profiles(self):
        """Test profiles() returns Broker-ready profiles."""
        registry = ProviderRegistry()
        registry.register(ProviderDescriptor(
            provider_id="test", display_name="Test", provider_class="local_runtime",
            capabilities=frozenset({"reasoning"}),
            cost_per_call=0.0,
            locality="local",
            privacy="private",
            declared_quality=0.8,
            health=ProviderHealth.HEALTHY,
        ))
        profiles = registry.profiles()
        assert len(profiles) == 1
        assert isinstance(profiles[0], ProviderProfile)
        assert profiles[0].provider_id == "test"

    def test_audit_log(self):
        """Test audit log records events."""
        sink_events = []
        def sink(event):
            sink_events.append(event)

        registry = ProviderRegistry(sink=sink)
        descriptor = ProviderDescriptor(
            provider_id="test", display_name="Test", provider_class="local_runtime",
        )
        registry.register(descriptor)
        assert len(sink_events) == 1
        assert sink_events[0]["event_type"] == "registered"

        registry.update_health("test", ProviderHealth.HEALTHY)
        assert len(sink_events) == 2
        assert sink_events[1]["event_type"] == "health_changed"

    def test_unregister_audits(self):
        """Test unregister creates audit event."""
        sink_events = []
        registry = ProviderRegistry(sink=lambda e: sink_events.append(e))
        registry.register(ProviderDescriptor(
            provider_id="test", display_name="Test", provider_class="local_runtime",
        ))
        registry.unregister("test")
        assert len(sink_events) == 2
        assert sink_events[1]["event_type"] == "unregistered"


class TestProviderHealth:
    """Test ProviderHealth enum."""

    def test_health_values(self):
        assert ProviderHealth.HEALTHY.value == "healthy"
        assert ProviderHealth.DEGRADED.value == "degraded"
        assert ProviderHealth.UNREACHABLE.value == "unreachable"
        assert ProviderHealth.UNVERIFIED.value == "unverified"


class TestRegistrationProvenance:
    """Test RegistrationProvenance enum."""

    def test_provenance_values(self):
        assert RegistrationProvenance.DECLARED.value == "declared"
        assert RegistrationProvenance.DISCOVERED.value == "discovered"
        assert RegistrationProvenance.SELF_REGISTERED.value == "self_registered"