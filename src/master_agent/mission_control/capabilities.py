"""The Capability Registry (Mission Brief 023 deliverable #2) — Mission
Control's coordination catalogue of what this system can do.

Deliberately NOT the same thing as Shared Infrastructure's Capability
Registry (Constitution §5.1, implemented today as plugins/registry.py):
that one resolves "which live Plugin object services this capability"
at execution time; this one answers "what does the system possess, at what
version, owned by whom, and is it healthy" at coordination time. It holds
descriptors, never live objects it could invoke — Mission Control must not
be able to perform work even by accident. See
MISSION_CONTROL_ARCHITECTURE.md §4.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _pascal_case(raw: str) -> str:
    """`read_file` -> `ReadFile`, `browser` -> `Browser`."""
    return "".join(part[:1].upper() + part[1:] for part in raw.replace("-", "_").split("_") if part)


def qualified_name(executive_id: str, capability: str) -> str:
    """One deterministic rule instead of a hand-maintained lookup table
    that would need an entry per capability forever — the same "design for
    many, not for three" principle FILESYSTEM_CAPABILITIES.md §1 applies to
    Actions.

    `qualified_name("filesystem", "read_file")` -> `"Filesystem.ReadFile"`.

    Mission Brief 023 writes its examples as `Filesystem.Read`; those are
    illustrative. The deterministic rule yields `Filesystem.ReadFile` for
    the capability that actually exists, which is the honest name.
    """
    executive_part = _pascal_case(executive_id)
    capability_part = _pascal_case(capability)
    if not executive_part or not capability_part:
        raise ValueError(
            f"cannot build a qualified name from executive_id={executive_id!r}, "
            f"capability={capability!r}"
        )
    return f"{executive_part}.{capability_part}"


@dataclass(frozen=True)
class CapabilityDescriptor:
    """What Mission Control knows about one capability. `risk_tier` and
    `permission_category` are carried as plain strings, mirrored from the
    providing plugin's manifest rather than importing the enums — Mission
    Control describes capabilities, it never gates them (the Permission
    System does, and it remains the only thing that does)."""

    qualified_name: str
    executive_id: str
    capability: str
    description: str = ""
    risk_tier: str | None = None
    permission_category: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class CapabilityAlreadyRegistered(Exception):
    pass


class UnknownCapability(Exception):
    pass


class CapabilityRegistry:
    def __init__(self) -> None:
        self._by_qualified_name: dict[str, CapabilityDescriptor] = {}
        self._by_executive: dict[str, list[str]] = {}

    def register(self, descriptor: CapabilityDescriptor) -> None:
        if descriptor.qualified_name in self._by_qualified_name:
            raise CapabilityAlreadyRegistered(
                f"capability already registered: {descriptor.qualified_name}"
            )
        self._by_qualified_name[descriptor.qualified_name] = descriptor
        self._by_executive.setdefault(descriptor.executive_id, []).append(
            descriptor.qualified_name
        )

    def get(self, qualified: str) -> CapabilityDescriptor:
        descriptor = self._by_qualified_name.get(qualified)
        if descriptor is None:
            raise UnknownCapability(f"unknown capability: {qualified}")
        return descriptor

    def has(self, qualified: str) -> bool:
        return qualified in self._by_qualified_name

    def for_executive(self, executive_id: str) -> list[CapabilityDescriptor]:
        return [
            self._by_qualified_name[name] for name in self._by_executive.get(executive_id, [])
        ]

    def remove_executive(self, executive_id: str) -> list[str]:
        """Used when an Executive deregisters. Returns the qualified names
        that are no longer available, so the caller can report exactly what
        the system just lost rather than silently shrinking."""
        removed = self._by_executive.pop(executive_id, [])
        for name in removed:
            self._by_qualified_name.pop(name, None)
        return list(removed)

    def all(self) -> list[CapabilityDescriptor]:
        return list(self._by_qualified_name.values())

    def names(self) -> list[str]:
        return sorted(self._by_qualified_name)

    def __len__(self) -> int:
        return len(self._by_qualified_name)
