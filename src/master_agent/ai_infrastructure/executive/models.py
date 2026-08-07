"""AI Infrastructure Executive — models.

Data shapes for the machine-touching Worker that discovers, probes, benchmarks,
and inventories AI providers. It produces facts; the Broker consumes them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class ProviderClass(str, Enum):
    """Open vocabulary string per ADR-0017 §4.3."""

    LOCAL_RUNTIME = "local_runtime"
    DESKTOP_APPLICATION = "desktop_application"
    CLOUD_API = "cloud_api"
    CLOUD_AGGREGATOR = "cloud_aggregator"
    REMOTE_SELF_HOSTED = "remote_self_hosted"
    EMBEDDED = "embedded"


class DiscoverySource(str, Enum):
    """How a provider was discovered."""

    FILESYSTEM_SCAN = "filesystem_scan"
    REGISTRY_QUERY = "registry_query"
    PROCESS_LIST = "process_list"
    CONFIG_DECLARED = "config_declared"
    SUBPROCESS_PROBE = "subprocess_probe"
    HTTP_PROBE = "http_probe"
    MANUAL_DECLARATION = "manual_declaration"


@dataclass(frozen=True)
class ProviderIdentity:
    """Stable identity for a discovered provider."""

    provider_id: str
    display_name: str
    provider_class: ProviderClass
    version: str | None = None
    install_path: str | None = None
    executable_path: str | None = None
    discovery_source: DiscoverySource = DiscoverySource.FILESYSTEM_SCAN
    discovered_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "display_name": self.display_name,
            "provider_class": self.provider_class.value,
            "version": self.version,
            "install_path": self.install_path,
            "executable_path": self.executable_path,
            "discovery_source": self.discovery_source.value,
            "discovered_at": self.discovered_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProviderIdentity:
        return cls(
            provider_id=data["provider_id"],
            display_name=data["display_name"],
            provider_class=ProviderClass(data["provider_class"]),
            version=data.get("version"),
            install_path=data.get("install_path"),
            executable_path=data.get("executable_path"),
            discovery_source=DiscoverySource(data.get("discovery_source", "filesystem_scan")),
            discovered_at=datetime.fromisoformat(data["discovered_at"]),
        )


@dataclass(frozen=True)
class ProviderCapabilities:
    """What AI capabilities a provider offers."""

    ai_capabilities: frozenset[str] = frozenset()  # e.g., {"reasoning", "vision.ocr"}
    execution_capability: str = ""  # PascalCase.PascalCase for Operator dispatch
    execution_parameters: frozenset[tuple[str, Any]] = frozenset()
    max_context_tokens: int | None = None
    supports_streaming: bool = False
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "ai_capabilities": sorted(self.ai_capabilities),
            "execution_capability": self.execution_capability,
            "execution_parameters": [list(kv) for kv in self.execution_parameters],
            "max_context_tokens": self.max_context_tokens,
            "supports_streaming": self.supports_streaming,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProviderCapabilities:
        return cls(
            ai_capabilities=frozenset(data.get("ai_capabilities", ())),
            execution_capability=data.get("execution_capability", ""),
            execution_parameters=frozenset(
                tuple(kv) for kv in data.get("execution_parameters", [])
            ),
            max_context_tokens=data.get("max_context_tokens"),
            supports_streaming=data.get("supports_streaming", False),
            notes=data.get("notes", ""),
        )


@dataclass(frozen=True)
class ProviderHealth:
    """Health state of a provider."""

    is_available: bool = False
    is_healthy: bool = False
    last_probe_at: datetime | None = None
    latency_ms: float | None = None
    error_message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "is_available": self.is_available,
            "is_healthy": self.is_healthy,
            "last_probe_at": self.last_probe_at.isoformat() if self.last_probe_at else None,
            "latency_ms": self.latency_ms,
            "error_message": self.error_message,
            "details": dict(self.details),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProviderHealth:
        return cls(
            is_available=data.get("is_available", False),
            is_healthy=data.get("is_healthy", False),
            last_probe_at=datetime.fromisoformat(data["last_probe_at"]) if data.get("last_probe_at") else None,
            latency_ms=data.get("latency_ms"),
            error_message=data.get("error_message"),
            details=data.get("details", {}),
        )


@dataclass(frozen=True)
class ProviderInventoryEntry:
    """One entry in the provider inventory — identity + capabilities + health."""

    identity: ProviderIdentity
    capabilities: ProviderCapabilities
    health: ProviderHealth

    def as_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity.as_dict(),
            "capabilities": self.capabilities.as_dict(),
            "health": self.health.as_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProviderInventoryEntry:
        return cls(
            identity=ProviderIdentity.from_dict(data["identity"]),
            capabilities=ProviderCapabilities.from_dict(data["capabilities"]),
            health=ProviderHealth.from_dict(data["health"]),
        )


@dataclass(frozen=True)
class ProviderInventory:
    """Complete inventory of discovered AI providers."""

    entries: tuple[ProviderInventoryEntry, ...] = ()
    scanned_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    scan_duration_seconds: float = 0.0
    scan_errors: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "entries": [e.as_dict() for e in self.entries],
            "scanned_at": self.scanned_at.isoformat(),
            "scan_duration_seconds": self.scan_duration_seconds,
            "scan_errors": list(self.scan_errors),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProviderInventory:
        return cls(
            entries=tuple(ProviderInventoryEntry.from_dict(e) for e in data.get("entries", ())),
            scanned_at=datetime.fromisoformat(data["scanned_at"]),
            scan_duration_seconds=data.get("scan_duration_seconds", 0.0),
            scan_errors=tuple(data.get("scan_errors", ())),
        )

    def by_provider_id(self, provider_id: str) -> ProviderInventoryEntry | None:
        for entry in self.entries:
            if entry.identity.provider_id == provider_id:
                return entry
        return None

    def available(self) -> tuple[ProviderInventoryEntry, ...]:
        return tuple(e for e in self.entries if e.health.is_available)


class BenchmarkStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class BenchmarkRequest:
    """Request to benchmark a provider for a capability."""

    provider_id: str
    ai_capability: str
    task_class: str
    test_prompts: tuple[str, ...] = ()
    expected_outputs: tuple[str, ...] = ()  # For verification
    max_latency_ms: float | None = None
    iterations: int = 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "ai_capability": self.ai_capability,
            "task_class": self.task_class,
            "test_prompts": list(self.test_prompts),
            "expected_outputs": list(self.expected_outputs),
            "max_latency_ms": self.max_latency_ms,
            "iterations": self.iterations,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BenchmarkRequest:
        return cls(
            provider_id=data["provider_id"],
            ai_capability=data["ai_capability"],
            task_class=data["task_class"],
            test_prompts=tuple(data.get("test_prompts", ())),
            expected_outputs=tuple(data.get("expected_outputs", ())),
            max_latency_ms=data.get("max_latency_ms"),
            iterations=data.get("iterations", 1),
        )


@dataclass(frozen=True)
class BenchmarkResult:
    """Result of a benchmark run."""

    request: BenchmarkRequest
    status: BenchmarkStatus
    samples: tuple[dict[str, Any], ...] = ()  # Individual run results
    aggregate_quality: float = 0.0
    aggregate_latency_ms: float | None = None
    aggregate_tokens_per_second: float | None = None
    aggregate_cost: float = 0.0
    confidence: float = 0.0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "request": self.request.as_dict(),
            "status": self.status.value,
            "samples": list(self.samples),
            "aggregate_quality": self.aggregate_quality,
            "aggregate_latency_ms": self.aggregate_latency_ms,
            "aggregate_tokens_per_second": self.aggregate_tokens_per_second,
            "aggregate_cost": self.aggregate_cost,
            "confidence": self.confidence,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BenchmarkResult:
        return cls(
            request=BenchmarkRequest.from_dict(data["request"]),
            status=BenchmarkStatus(data["status"]),
            samples=tuple(data.get("samples", ())),
            aggregate_quality=data.get("aggregate_quality", 0.0),
            aggregate_latency_ms=data.get("aggregate_latency_ms"),
            aggregate_tokens_per_second=data.get("aggregate_tokens_per_second"),
            aggregate_cost=data.get("aggregate_cost", 0.0),
            confidence=data.get("confidence", 0.0),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            error_message=data.get("error_message"),
        )