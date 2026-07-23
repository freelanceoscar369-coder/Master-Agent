"""Filesystem capability plugin — a thin Plugin-contract adapter over the
LocalExecutor (Mission Brief 002). All real logic (idempotency, error
handling, the actual mkdir/write) lives in executor/actions/ — this class
exists only so the Orchestrator/PluginRegistry can resolve each capability
the same way it resolves every other one (ADR-0003) — nothing about that
resolution changed.

Mission Brief 003 added two capabilities on top of `create_folder`:
`write_file` (a second filesystem primitive) and `workspace_bootstrap`
(a composite action built from the first two — see
executor/actions/workspace_bootstrap.py and
docs/adr/0006-composite-action-relay.md). This adapter's job is unchanged
by that addition: relay the approval it already has, delegate to
execute(), translate the result shape. It does not know or care that one
of its three capabilities happens to be composed of the other two
underneath — that composition is entirely the Executor/Action layer's
concern.

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
from master_agent.executor.actions.workspace_bootstrap import WORKSPACE_BOOTSTRAP, WorkspaceBootstrapAction
from master_agent.executor.actions.write_file import WRITE_FILE, WriteFileAction
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
    """Exposes CreateFolderAction, WriteFileAction, and
    WorkspaceBootstrapAction as the `create_folder`, `write_file`, and
    `workspace_bootstrap` capabilities.

    `executor` is injected (dependency injection, consistent with the rest
    of the codebase) — this plugin registers its actions on whatever
    executor it's given rather than owning one itself, so multiple
    filesystem-backed plugins could someday share one executor's log.
    `locations` is passed straight through to each action; see
    CreateFolderAction for why it's injected too (tests point "desktop" at
    a tmp_path).
    """

    _SUPPORTED = {CREATE_FOLDER, WRITE_FILE, WORKSPACE_BOOTSTRAP}

    def __init__(self, executor: LocalExecutor, locations: dict[str, Path] | None = None) -> None:
        self._executor = executor
        self._executor.register(CreateFolderAction(locations))
        self._executor.register(WriteFileAction(locations))
        self._executor.register(WorkspaceBootstrapAction(executor, locations))

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="filesystem",
            version="0.3.0",
            capabilities=[
                CapabilityManifest(
                    name=CREATE_FOLDER,
                    description="Create a new folder in a known location.",
                    risk_tier=RiskTier.REVERSIBLE_WRITE,
                    input_schema={"name": "str", "location": "str (optional, default 'desktop')"},
                    output_schema={"path": "str — absolute path of the created (or existing) folder"},
                ),
                CapabilityManifest(
                    name=WRITE_FILE,
                    description="Write text content to a file in a known location.",
                    risk_tier=RiskTier.REVERSIBLE_WRITE,
                    input_schema={
                        "path": "str — relative path, may include subfolders",
                        "content": "str (optional, default '')",
                        "location": "str (optional, default 'desktop')",
                    },
                    output_schema={"path": "str — absolute path of the written file"},
                ),
                CapabilityManifest(
                    name=WORKSPACE_BOOTSTRAP,
                    description=(
                        "Create a workspace root folder plus requested subfolders and "
                        "seed files, composed from create_folder and write_file."
                    ),
                    risk_tier=RiskTier.REVERSIBLE_WRITE,
                    input_schema={
                        "name": "str — workspace root folder name",
                        "location": "str (optional, default 'desktop')",
                        "folders": "list[str] (optional) — relative subfolder paths under the root",
                        "files": "list[{path: str, content: str}] (optional) — seed files under the root",
                    },
                    output_schema={
                        "root": "str — absolute path of the workspace root",
                        "created_folders": "list[str]",
                        "written_files": "list[str]",
                    },
                ),
            ],
        )

    def invoke(self, capability: str, payload: dict[str, Any]) -> InvocationResult:
        if capability not in self._SUPPORTED:
            return InvocationResult(success=False, error=f"unsupported capability: {capability}")

        # Relay this call's already-obtained approval to the Executor's
        # own grant key — see module docstring. Deliberately NOT wrapped
        # in a try/except: ApprovalRequired should never actually be
        # raised by this check (a fresh ONCE grant always satisfies the
        # very next check for the same key), but if it somehow were, it
        # must propagate to the Orchestrator like any other
        # ApprovalRequired, not be swallowed here. This is true whether
        # `capability` resolves to a single primitive action or, for
        # workspace_bootstrap, a composite that goes on to relay its own
        # grants to its sub-actions (docs/adr/0006-composite-action-relay.md)
        # — from this adapter's perspective it's one execute() call either way.
        self._executor.permissions.grant(self._executor.name, capability, GrantScope.ONCE)

        result = self._executor.execute(capability, payload)

        if not result.success:
            return InvocationResult(success=False, error="; ".join(result.errors) or "unknown executor failure")
        return InvocationResult(success=True, output=result.output)
