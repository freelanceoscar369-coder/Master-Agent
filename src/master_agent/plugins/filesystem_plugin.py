"""Filesystem capability plugin — a thin Plugin-contract adapter over the
LocalExecutor (Mission Brief 002). All real logic (idempotency, error
handling, the actual mkdir) now lives in
executor/actions/create_folder.py's CreateFolderAction; this class exists
only so the Orchestrator/PluginRegistry can resolve "create_folder" the
same way it resolves every other capability (ADR-0003) — nothing about
that resolution changed.

## Why this relays a permission grant instead of just calling execute()

The Orchestrator already gates entry to invoke() on the Permission System,
keyed to (this plugin's manifest name, capability) — see
orchestrator/orchestrator.py, unchanged by this refactor. By the time
invoke() runs at all, a human has already approved this exact action.

The LocalExecutor also checks permission before running an action — it
has to, because it's meant to be safely callable on its own, without a
Plugin/Orchestrator in front of it (see executor/executor.py's module
docstring and docs/adr/0005-executor-permission-relay.md). But it checks
a *different* grant key (the executor's own name, not this plugin's), so
its check doesn't collide with — and doesn't get skipped by — the
Orchestrator's already-consumed grant. That means this adapter has to
relay the approval it already received down to the Executor's key,
scoped ONCE, immediately before calling execute(). The human is never
asked twice; the Executor's gate stays real for anyone who calls it
directly.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from master_agent.executor.actions.create_folder import CREATE_FOLDER, CreateFolderAction
from master_agent.executor.executor import LocalExecutor
from master_agent.permissions.permission_system import GrantScope
from master_agent.plugins.base import (
    CapabilityManifest,
    InvocationResult,
    Plugin,
    PluginManifest,
    RiskTier,
)


class FilesystemPlugin(Plugin):
    """Exposes CreateFolderAction as the `create_folder` capability.

    `executor` is injected (dependency injection, consistent with the rest
    of the codebase) — this plugin registers its action on whatever
    executor it's given rather than owning one itself, so multiple
    filesystem-backed plugins could someday share one executor's log.
    `locations` is passed straight through to CreateFolderAction; see that
    class for why it's injected too (tests point "desktop" at a tmp_path).
    """

    def __init__(self, executor: LocalExecutor, locations: dict[str, Path] | None = None) -> None:
        self._executor = executor
        self._executor.register(CreateFolderAction(locations))

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="filesystem",
            version="0.2.0",
            capabilities=[
                CapabilityManifest(
                    name=CREATE_FOLDER,
                    description="Create a new folder in a known location.",
                    risk_tier=RiskTier.REVERSIBLE_WRITE,
                    input_schema={"name": "str", "location": "str (optional, default 'desktop')"},
                    output_schema={"path": "str — absolute path of the created (or existing) folder"},
                ),
            ],
        )

    def invoke(self, capability: str, payload: dict[str, Any]) -> InvocationResult:
        if capability != CREATE_FOLDER:
            return InvocationResult(success=False, error=f"unsupported capability: {capability}")

        # Relay this call's already-obtained approval to the Executor's
        # own grant key — see module docstring. Deliberately NOT wrapped
        # in a try/except: ApprovalRequired should never actually be
        # raised by this check (a fresh ONCE grant always satisfies the
        # very next check for the same key), but if it somehow were, it
        # must propagate to the Orchestrator like any other
        # ApprovalRequired, not be swallowed here.
        self._executor.permissions.grant(self._executor.name, capability, GrantScope.ONCE)

        result = self._executor.execute(capability, payload)

        if not result.success:
            return InvocationResult(success=False, error="; ".join(result.errors) or "unknown executor failure")
        return InvocationResult(success=True, output=result.output)
