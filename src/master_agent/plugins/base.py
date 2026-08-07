"""The Plugin contract. Every capability, model provider, and voice adapter
in Master Agent implements this — see ADR-0003. Nothing outside this file
and registry.py should need to know about a concrete plugin's internals.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RiskTier(str, Enum):
    """How much human oversight a capability invocation requires.

    The Permission System (permissions/) gates anything above READ_ONLY.
    Plugins must classify honestly — this is a trust boundary, not a
    formality.
    """

    READ_ONLY = "read_only"
    REVERSIBLE_WRITE = "reversible_write"
    IRREVERSIBLE = "irreversible"


class PermissionCategory(str, Enum):
    """Human-facing classification of *what kind* of thing a capability
    does — orthogonal to `RiskTier`, which answers *how much oversight*
    it needs. `RiskTier` is what `PermissionSystem.check()` actually
    gates on (unchanged mechanism, permissions/permission_system.py);
    `PermissionCategory` is what an approval prompt or a Memory record
    says out loud. Lives here, next to `RiskTier`, for the same reason
    `RiskTier` does — declared by the plugin/Action, consumed by the
    Permission System. See `FILESYSTEM_CAPABILITIES.md` §5 (Mission
    Brief 005).

    `SYSTEM` has no Action using it yet in this codebase — reserved the
    same way Memory's Layers 4-6 are reserved, ahead of the capability
    (a shell/process action) that will eventually need it.
    """

    READ = "read"
    WRITE = "write"
    MODIFY = "modify"
    DELETE = "delete"
    SYSTEM = "system"


@dataclass
class CapabilityManifest:
    """Describes one capability a plugin exposes."""

    name: str
    description: str
    risk_tier: RiskTier
    # Input/output schemas — populated from capability contracts (MB039).
    # Declared as dict for Plugin contract compatibility; the extraction
    # system produces Schema objects which serialise to this shape.
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    # Optional — mirrors an Action's `permission_category` for plugins
    # backed by the Action Contract. None for plugins that predate this
    # field (e.g. ModelProvider) or don't have a natural category.
    permission_category: PermissionCategory | None = None


@dataclass
class PluginManifest:
    """Describes a plugin as a whole. The registry indexes plugins by the
    capabilities in here, not by plugin name — the Orchestrator resolves
    "who can do X" without caring which plugin it turns out to be.
    """

    name: str
    version: str
    capabilities: list[CapabilityManifest]


@dataclass
class InvocationResult:
    success: bool
    output: Any = None
    error: str | None = None
    # Optional — populated by plugins that have a real timing to report
    # (e.g. FilesystemPlugin, forwarding LocalExecutor's measured
    # ExecutionResult.execution_time_seconds; Mission Brief 003.1). 0.0
    # for any plugin that doesn't set it, not a claim that invocation was
    # instantaneous.
    execution_time_seconds: float = 0.0


class Plugin(ABC):
    """Base class every plugin implements.

    Keep this interface small on purpose — the more we put here, the
    harder it is to write a new plugin, and "everything is a plugin" only
    holds up if writing one stays cheap.
    """

    @property
    @abstractmethod
    def manifest(self) -> PluginManifest:
        ...

    @abstractmethod
    def invoke(self, capability: str, payload: dict[str, Any]) -> InvocationResult:
        """Execute one capability. Must not perform anything above
        READ_ONLY risk without having already been cleared by the
        Permission System — the Orchestrator is responsible for checking
        that before calling invoke(), but plugins should not assume that
        check can never be bypassed by a future caller. Fail closed.
        """
        ...


class ModelProvider(Plugin):
    """Specialization of Plugin for LLM providers (ChatGPT, Hermes, ...).

    Concrete providers implement `generate`; `invoke()` is provided so a
    ModelProvider is still a valid Plugin the registry can index like any
    other, which is what lets the Model Router treat "call a model" as
    just another capability lookup.
    """

    CAPABILITY_NAME = "generate_text"

    @abstractmethod
    def generate(self, prompt: str, context: dict[str, Any] | None = None, **opts: Any) -> str:
        ...

    def invoke(self, capability: str, payload: dict[str, Any]) -> InvocationResult:
        if capability != self.CAPABILITY_NAME:
            return InvocationResult(success=False, error=f"unknown capability: {capability}")
        try:
            text = self.generate(payload.get("prompt", ""), payload.get("context"))
            return InvocationResult(success=True, output=text)
        except Exception as exc:  # noqa: BLE001 — surfaced to caller, not swallowed
            return InvocationResult(success=False, error=str(exc))
