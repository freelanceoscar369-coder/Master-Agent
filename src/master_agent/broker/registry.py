"""Persistent Provider Registry (Mission Brief 031 Deliverable 2).

The Broker owns the Provider Registry — what intelligence exists. Descriptors
only, never live objects. No provider known to Broker's code. Registration
idempotent by `provider_id`.

This is the *persistent* registry — the canonical source of truth for provider
descriptors that survives process restarts. It is distinct from the
`ProviderSource` in `ai_infrastructure.profiles` which builds profiles fresh
on every request from the machine scan + catalogue.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from master_agent.broker.profiles import ProviderProfile


class RegistrationProvenance(str, Enum):
    """Who registered this provider, per ADR-0017 §4.3."""

    DECLARED = "declared"           # Founder via Configuration
    DISCOVERED = "discovered"       # AI Infrastructure Executive
    SELF_REGISTERED = "self_registered"  # Executive that provides intelligence


class ProviderHealth(str, Enum):
    """Provider health state."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNREACHABLE = "unreachable"
    UNVERIFIED = "unverified"


@dataclass(frozen=True)
class ProviderDescriptor:
    """Canonical persistent descriptor for a Provider.

    This is what the registry stores. It is a `ProviderProfile` plus
    provenance, registration timestamps, and health state — the full
    administrative record the Broker needs to make decisions and the
    Executive needs to maintain.
    """

    # Core identity
    provider_id: str
    display_name: str
    provider_class: str  # open vocabulary, NOT an enum

    # Capability matrix row
    capabilities: frozenset[str] = frozenset()

    # Execution binding — must name an already-registered Capability
    execution_capability: str = ""
    execution_parameters: frozenset[tuple[str, Any]] = frozenset()

    # Economics
    cost_per_call: float = 0.0
    is_free: bool = True
    currency: str = "USD"

    # Licensing
    licence_id: str = ""
    permits_commercial_use: bool = True
    permits_redistribution: bool = False
    requires_attribution: bool = False
    requires_paid_activation: bool = False
    licence_source_url: str = ""

    # Operational
    locality: str = "cloud"  # local, desktop, cloud
    privacy: str = "third_party"  # private, third_party
    requires_network: bool = True
    requires_approval: bool = False
    max_context_tokens: int | None = None
    latency_ms: float | None = None

    # Quality
    declared_quality: float = 0.0
    benchmark: float | None = None
    benchmark_confidence: float = 0.0

    # MB038 throughput
    prefill_tokens_per_second: float | None = None
    decode_tokens_per_second: float | None = None
    expected_itl_ms: float | None = None
    supports_streaming: bool = False
    chars_per_token: float | None = None
    serialises: bool = False
    model_load_ms: float | None = None

    # Registration metadata
    provenance: RegistrationProvenance = RegistrationProvenance.DECLARED
    version: str = "1.0.0"
    registered_at: datetime = datetime.now(UTC)
    verified_at: datetime | None = None
    health: ProviderHealth = ProviderHealth.UNVERIFIED
    notes: str = ""

    @property
    def effective_quality(self) -> float:
        """Measured beats declared (ADR-0017 Decision 5)."""
        return self.declared_quality if self.benchmark is None else self.benchmark

    def serves(self, capability: str) -> bool:
        """Exact or prefix match (from ProviderProfile.serves)."""
        return any(
            offered == capability or offered.startswith(f"{capability}.")
            for offered in self.capabilities
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "display_name": self.display_name,
            "provider_class": self.provider_class,
            "capabilities": sorted(self.capabilities),
            "execution_capability": self.execution_capability,
            "execution_parameters": [list(kv) for kv in self.execution_parameters],
            "cost_per_call": self.cost_per_call,
            "is_free": self.is_free,
            "currency": self.currency,
            "licence_id": self.licence_id,
            "permits_commercial_use": self.permits_commercial_use,
            "permits_redistribution": self.permits_redistribution,
            "requires_attribution": self.requires_attribution,
            "requires_paid_activation": self.requires_paid_activation,
            "licence_source_url": self.licence_source_url,
            "locality": self.locality,
            "privacy": self.privacy,
            "requires_network": self.requires_network,
            "requires_approval": self.requires_approval,
            "max_context_tokens": self.max_context_tokens,
            "latency_ms": self.latency_ms,
            "declared_quality": self.declared_quality,
            "benchmark": self.benchmark,
            "benchmark_confidence": self.benchmark_confidence,
            "effective_quality": self.effective_quality,
            "prefill_tokens_per_second": self.prefill_tokens_per_second,
            "decode_tokens_per_second": self.decode_tokens_per_second,
            "expected_itl_ms": self.expected_itl_ms,
            "supports_streaming": self.supports_streaming,
            "chars_per_token": self.chars_per_token,
            "serialises": self.serialises,
            "model_load_ms": self.model_load_ms,
            "provenance": self.provenance.value,
            "version": self.version,
            "registered_at": self.registered_at.isoformat(),
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "health": self.health.value,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProviderDescriptor:
        return cls(
            provider_id=data["provider_id"],
            display_name=data["display_name"],
            provider_class=data["provider_class"],
            capabilities=frozenset(data.get("capabilities", ())),
            execution_capability=data.get("execution_capability", ""),
            execution_parameters=frozenset(
                tuple(kv) for kv in data.get("execution_parameters", [])
            ),
            cost_per_call=data.get("cost_per_call", 0.0),
            is_free=data.get("is_free", True),
            currency=data.get("currency", "USD"),
            licence_id=data.get("licence_id", ""),
            permits_commercial_use=data.get("permits_commercial_use", True),
            permits_redistribution=data.get("permits_redistribution", False),
            requires_attribution=data.get("requires_attribution", False),
            requires_paid_activation=data.get("requires_paid_activation", False),
            licence_source_url=data.get("licence_source_url", ""),
            locality=data.get("locality", "cloud"),
            privacy=data.get("privacy", "third_party"),
            requires_network=data.get("requires_network", True),
            requires_approval=data.get("requires_approval", False),
            max_context_tokens=data.get("max_context_tokens"),
            latency_ms=data.get("latency_ms"),
            declared_quality=data.get("declared_quality", 0.0),
            benchmark=data.get("benchmark"),
            benchmark_confidence=data.get("benchmark_confidence", 0.0),
            prefill_tokens_per_second=data.get("prefill_tokens_per_second"),
            decode_tokens_per_second=data.get("decode_tokens_per_second"),
            expected_itl_ms=data.get("expected_itl_ms"),
            supports_streaming=data.get("supports_streaming", False),
            chars_per_token=data.get("chars_per_token"),
            serialises=data.get("serialises", False),
            model_load_ms=data.get("model_load_ms"),
            provenance=RegistrationProvenance(data.get("provenance", "declared")),
            version=data.get("version", "1.0.0"),
            registered_at=datetime.fromisoformat(data["registered_at"]),
            verified_at=datetime.fromisoformat(data["verified_at"]) if data.get("verified_at") else None,
            health=ProviderHealth(data.get("health", "unverified")),
            notes=data.get("notes", ""),
        )

    def to_profile(self) -> ProviderProfile:
        """Convert to a ProviderProfile for the Broker's decision engine."""
        return ProviderProfile(
            provider_id=self.provider_id,
            capabilities=self.capabilities,
            locality=self.locality,
            privacy=self.privacy,
            quality=self.declared_quality,
            benchmark=self.benchmark,
            benchmark_confidence=self.benchmark_confidence,
            cost=self.cost_per_call,
            latency_ms=self.latency_ms,
            available=self.health in (ProviderHealth.HEALTHY, ProviderHealth.DEGRADED),
            requires_network=self.requires_network,
            requires_approval=self.requires_approval,
            max_context_tokens=self.max_context_tokens,
            notes=self.notes,
            prefill_tokens_per_second=self.prefill_tokens_per_second,
            decode_tokens_per_second=self.decode_tokens_per_second,
            expected_itl_ms=self.expected_itl_ms,
            supports_streaming=self.supports_streaming,
            chars_per_token=self.chars_per_token,
            serialises=self.serialises,
            model_load_ms=self.model_load_ms,
        )


class ProviderRegistry:
    """The Persistent Provider Registry.

    Owned exclusively by the AI Capability Broker (ADR-0017 Decision 1).
    Holds descriptors only — never live objects, never imports provider SDKs.

    Registration is idempotent by `provider_id`. Re-registration with changes
    updates the record and emits an audit event (via sink if configured).
    """

    def __init__(self, sink: Any = None) -> None:
        self._descriptors: dict[str, ProviderDescriptor] = {}
        self._sink = sink
        self._audit_log: list[dict[str, Any]] = []

    def register(self, descriptor: ProviderDescriptor) -> ProviderDescriptor:
        """Register or update a provider descriptor. Idempotent by provider_id."""
        existing = self._descriptors.get(descriptor.provider_id)
        now = datetime.now(UTC)

        if existing is None:
            # New registration
            final = replace(descriptor, registered_at=now, verified_at=now)
            self._descriptors[descriptor.provider_id] = final
            event_type = "registered"
        else:
            # Update — preserve original registration time, update verified_at
            final = replace(
                descriptor,
                registered_at=existing.registered_at,
                verified_at=now,
            )
            self._descriptors[descriptor.provider_id] = final
            event_type = "updated"

        self._audit(event_type, final, existing)
        return final

    def unregister(self, provider_id: str) -> bool:
        """Remove a provider from the registry. Returns True if existed."""
        if provider_id in self._descriptors:
            removed = self._descriptors.pop(provider_id)
            self._audit("unregistered", removed)
            return True
        return False

    def get(self, provider_id: str) -> ProviderDescriptor | None:
        """Get a provider descriptor by ID."""
        return self._descriptors.get(provider_id)

    def all(self) -> tuple[ProviderDescriptor, ...]:
        """All registered providers, sorted by provider_id for determinism."""
        return tuple(sorted(self._descriptors.values(), key=lambda d: d.provider_id))

    def available(self) -> tuple[ProviderDescriptor, ...]:
        """Providers currently healthy or degraded (not unreachable/unverified)."""
        return tuple(
            d for d in self.all()
            if d.health in (ProviderHealth.HEALTHY, ProviderHealth.DEGRADED)
        )

    def by_capability(self, capability: str) -> tuple[ProviderDescriptor, ...]:
        """Providers offering a capability (exact or prefix match).

        Returns all registered providers with this capability, regardless
        of health. Callers that need only available providers should
        filter the result themselves or use `available()` first.
        """
        return tuple(d for d in self.all() if d.serves(capability))

    def by_provenance(self, provenance: RegistrationProvenance) -> tuple[ProviderDescriptor, ...]:
        """Providers registered via a specific path."""
        return tuple(d for d in self.all() if d.provenance == provenance)

    def by_class(self, provider_class: str) -> tuple[ProviderDescriptor, ...]:
        """Providers of a specific class (open vocabulary)."""
        return tuple(d for d in self.all() if d.provider_class == provider_class)

    def update_health(self, provider_id: str, health: ProviderHealth) -> bool:
        """Update provider health. Returns True if provider exists."""
        descriptor = self._descriptors.get(provider_id)
        if descriptor is None:
            return False
        updated = replace(descriptor, health=health, verified_at=datetime.now(UTC))
        self._descriptors[provider_id] = updated
        self._audit("health_changed", updated, descriptor)
        return True

    def update_benchmark(
        self,
        provider_id: str,
        benchmark: float,
        confidence: float,
    ) -> bool:
        """Update benchmark quality for a provider. Returns True if provider exists."""
        descriptor = self._descriptors.get(provider_id)
        if descriptor is None:
            return False
        updated = replace(
            descriptor,
            benchmark=benchmark,
            benchmark_confidence=confidence,
            verified_at=datetime.now(UTC),
        )
        self._descriptors[provider_id] = updated
        self._audit("benchmark_updated", updated, descriptor)
        return True

    def profiles(self) -> tuple[ProviderProfile, ...]:
        """All available providers as Broker-ready profiles."""
        return tuple(d.to_profile() for d in self.available())

    def audit_log(self) -> tuple[dict[str, Any], ...]:
        """Immutable audit log."""
        return tuple(self._audit_log)

    def _audit(
        self,
        event_type: str,
        descriptor: ProviderDescriptor,
        previous: ProviderDescriptor | None = None,
    ) -> None:
        event = {
            "event_type": event_type,
            "provider_id": descriptor.provider_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "descriptor": descriptor.as_dict(),
            "previous": previous.as_dict() if previous else None,
        }
        self._audit_log.append(event)
        if self._sink is not None:
            try:
                self._sink(event)
            except Exception:
                pass  # Recording never gates a decision