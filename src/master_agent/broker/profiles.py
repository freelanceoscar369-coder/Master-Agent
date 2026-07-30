"""What the Broker decides *about* (Mission Brief 031).

Two shapes, and neither of them names a product. A `ProviderProfile` is
what some intelligence can do and what it costs; a `TaskProfile` is what
a caller needs. The Broker matches one against the other.

**There is no provider registry in this module and no provider names
anywhere in this package.** Profiles are supplied by the caller — the AI
Infrastructure Executive discovers them (MB027 §11, not yet built), a
founder declares them in configuration, or a test constructs them. The
Broker is handed facts; it never goes looking (ADR-0017 Decision 1).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ---- vocabularies, deliberately open ------------------------------------

#: Where a provider physically runs. The tier ladder is derived from this
#: plus cost, never from a product name (ADR-0017 §4.1 rule 3).
LOCAL = "local"
DESKTOP = "desktop"
CLOUD = "cloud"
LOCALITIES = (LOCAL, DESKTOP, CLOUD)

#: How data is handled. `PRIVATE` means it never leaves the machine.
PRIVATE = "private"
THIRD_PARTY = "third_party"

#: Sensitivity of the *task*, matched against the above.
UNRESTRICTED = "unrestricted"
SENSITIVE = "sensitive"


@dataclass(frozen=True)
class ProviderProfile:
    """One intelligence the Broker may choose between.

    Frozen: a profile describes a provider as it was when observed, and a
    decision must be reproducible from exactly the profiles that produced
    it (Deliverable 6).

    `quality` and `benchmark` are deliberately separate. `quality` is what
    the profile *claims*; `benchmark` is what was *measured* here. Where
    both exist, measurement wins — Constitution Rule 8, the Evidence
    Hierarchy, applied to provider selection (ADR-0017 Decision 5).
    """

    provider_id: str
    capabilities: frozenset[str] = frozenset()
    locality: str = CLOUD
    privacy: str = THIRD_PARTY
    #: Declared quality, 0..1. What the provider says of itself.
    quality: float = 0.0
    #: Measured quality, 0..1, or None when nothing has been measured.
    benchmark: float | None = None
    #: Confidence in `benchmark`, 0..1. Low when samples are scarce.
    benchmark_confidence: float = 0.0
    #: Cost per unit of work, in whatever currency the caller uses
    #: consistently. 0.0 means free.
    cost: float = 0.0
    latency_ms: float | None = None
    available: bool = True
    requires_network: bool = True
    #: True when using this provider needs a founder decision that has not
    #: been made. The Broker never grants approval; it refuses to select
    #: something unapproved (ADR-0017 Decision 2).
    requires_approval: bool = False
    max_context_tokens: int | None = None
    notes: str = ""

    @property
    def effective_quality(self) -> float:
        """Measured beats declared. A provider cannot market its way up
        the ranking."""
        return self.quality if self.benchmark is None else self.benchmark

    @property
    def is_free(self) -> bool:
        return self.cost <= 0.0

    @property
    def is_local(self) -> bool:
        return self.locality in (LOCAL, DESKTOP)

    def serves(self, capability: str) -> bool:
        """Exact or prefix match. A request for `vision` is served by
        `vision.ocr`; a request for `vision.ocr` is **not** served by a
        provider offering only `vision`. Specific requests never get
        generic answers (ADR-0017 §5.2)."""
        return any(
            offered == capability or offered.startswith(f"{capability}.")
            for offered in self.capabilities
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "capabilities": sorted(self.capabilities),
            "locality": self.locality,
            "privacy": self.privacy,
            "quality": self.quality,
            "benchmark": self.benchmark,
            "benchmark_confidence": self.benchmark_confidence,
            "effective_quality": self.effective_quality,
            "cost": self.cost,
            "latency_ms": self.latency_ms,
            "available": self.available,
            "requires_network": self.requires_network,
            "requires_approval": self.requires_approval,
            "max_context_tokens": self.max_context_tokens,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProviderProfile:
        return cls(
            provider_id=data["provider_id"],
            capabilities=frozenset(data.get("capabilities", ())),
            locality=data.get("locality", CLOUD),
            privacy=data.get("privacy", THIRD_PARTY),
            quality=data.get("quality", 0.0),
            benchmark=data.get("benchmark"),
            benchmark_confidence=data.get("benchmark_confidence", 0.0),
            cost=data.get("cost", 0.0),
            latency_ms=data.get("latency_ms"),
            available=data.get("available", True),
            requires_network=data.get("requires_network", True),
            requires_approval=data.get("requires_approval", False),
            max_context_tokens=data.get("max_context_tokens"),
            notes=data.get("notes", ""),
        )


@dataclass(frozen=True)
class TaskProfile:
    """What a caller needs done.

    `min_quality` is the quality floor, and `None` means "use the
    policy's". It is the single most important field here: without it the
    Broker would hand every task to the cheapest thing that technically
    matched (ADR-0017 Decision 3).
    """

    capability: str
    task_id: str = ""
    sensitivity: str = UNRESTRICTED
    min_quality: float | None = None
    max_cost: float | None = None
    max_latency_ms: float | None = None
    required_context_tokens: int | None = None
    offline: bool = False
    exclude_providers: frozenset[str] = frozenset()
    requester: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "task_id": self.task_id,
            "sensitivity": self.sensitivity,
            "min_quality": self.min_quality,
            "max_cost": self.max_cost,
            "max_latency_ms": self.max_latency_ms,
            "required_context_tokens": self.required_context_tokens,
            "offline": self.offline,
            "exclude_providers": sorted(self.exclude_providers),
            "requester": self.requester,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskProfile:
        return cls(
            capability=data["capability"],
            task_id=data.get("task_id", ""),
            sensitivity=data.get("sensitivity", UNRESTRICTED),
            min_quality=data.get("min_quality"),
            max_cost=data.get("max_cost"),
            max_latency_ms=data.get("max_latency_ms"),
            required_context_tokens=data.get("required_context_tokens"),
            offline=data.get("offline", False),
            exclude_providers=frozenset(data.get("exclude_providers", ())),
            requester=data.get("requester", ""),
        )
