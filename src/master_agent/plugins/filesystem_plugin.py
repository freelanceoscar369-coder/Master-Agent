"""Filesystem capability plugin — a thin Plugin-contract adapter over the
LocalExecutor (Mission Brief 002). All real logic (validation, error
handling, the actual filesystem work) lives in executor/actions/ — this
class exists only so the Orchestrator/PluginRegistry can resolve each
capability the same way it resolves every other one (ADR-0003).

Mission Brief 005 turned this from "three capabilities, each registered
and manifested by hand" into a toolbox: eleven new primitive Actions
(read/list/search/exists-checks, write/append, rename/copy/move,
delete-file/delete-folder) plus the two that already existed
(`create_folder`, `write_file`) and the one composite
(`workspace_bootstrap`). Registration and manifest-building are both
declarative loops over `_PRIMITIVE_ACTION_CLASSES` now, not one
hand-written line and one hand-written CapabilityManifest per capability —
see FILESYSTEM_CAPABILITIES.md §4-5 for why: adding capability #12 (or
#200) costs one new class in that tuple, never an edit to this file's
logic.

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
directly. Unchanged by this Miracle — every one of the fourteen
capabilities below goes through the exact same relay-then-execute path,
including the three IRREVERSIBLE ones (see permissions/permission_system.py
for the additional rule that makes those specifically harder to
pre-approve).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from master_agent.executor.action import Action
from master_agent.executor.actions.append_file import APPEND_FILE, AppendFileAction
from master_agent.executor.actions.copy_file import COPY_FILE, CopyFileAction
from master_agent.executor.actions.create_folder import CREATE_FOLDER, CreateFolderAction
from master_agent.executor.actions.delete_file import DELETE_FILE, DeleteFileAction
from master_agent.executor.actions.delete_folder import DELETE_FOLDER, DeleteFolderAction
from master_agent.executor.actions.directory_exists import DIRECTORY_EXISTS, DirectoryExistsAction
from master_agent.executor.actions.file_exists import FILE_EXISTS, FileExistsAction
from master_agent.executor.actions.list_directory import LIST_DIRECTORY, ListDirectoryAction
from master_agent.executor.actions.move_file import MOVE_FILE, MoveFileAction
from master_agent.executor.actions.read_file import READ_FILE, ReadFileAction
from master_agent.executor.actions.rename_file import RENAME_FILE, RenameFileAction
from master_agent.executor.actions.search_files import SEARCH_FILES, SearchFilesAction
from master_agent.executor.actions.workspace_bootstrap import WORKSPACE_BOOTSTRAP, WorkspaceBootstrapAction
from master_agent.executor.actions.write_file import WRITE_FILE, WriteFileAction
from master_agent.executor.executor import LocalExecutor
from master_agent.permissions.permission_system import GrantScope
from master_agent.plugins.base import CapabilityManifest, InvocationResult, Plugin, PluginManifest

# Re-exported for callers (cli.py, tests) that reference a capability name
# without wanting to import each action module individually.
__all__ = [
    "APPEND_FILE",
    "COPY_FILE",
    "CREATE_FOLDER",
    "DELETE_FILE",
    "DELETE_FOLDER",
    "DIRECTORY_EXISTS",
    "FILE_EXISTS",
    "LIST_DIRECTORY",
    "MOVE_FILE",
    "READ_FILE",
    "RENAME_FILE",
    "SEARCH_FILES",
    "WORKSPACE_BOOTSTRAP",
    "WRITE_FILE",
    "FilesystemPlugin",
]

# Every primitive Action this plugin owns, in one place. Each must share
# the `__init__(self, locations: dict[str, Path] | None = None)`
# constructor — that uniform shape is what makes the registration loop
# below possible without an if/else per Action. Composite Actions
# (currently just WorkspaceBootstrapAction) need the executor itself
# injected too, so they're registered separately, just below — see
# FILESYSTEM_CAPABILITIES.md §5 for why that split is fine at scale
# (composites are meant to stay few and deliberate; primitives are meant
# to grow into the hundreds).
_PRIMITIVE_ACTION_CLASSES: tuple[type[Action], ...] = (
    CreateFolderAction,
    WriteFileAction,
    ReadFileAction,
    ListDirectoryAction,
    SearchFilesAction,
    FileExistsAction,
    DirectoryExistsAction,
    AppendFileAction,
    RenameFileAction,
    CopyFileAction,
    MoveFileAction,
    DeleteFileAction,
    DeleteFolderAction,
)


class FilesystemPlugin(Plugin):
    """Exposes every registered filesystem Action as a same-named
    capability.

    `executor` is injected (dependency injection, consistent with the
    rest of the codebase) — this plugin registers its actions on
    whatever executor it's given rather than owning one itself, so
    multiple filesystem-backed plugins could someday share one executor's
    log. `locations` is passed straight through to each action; see
    `executor/action.py`'s `default_locations()` for the default
    (desktop/downloads/documents) and CreateFolderAction for why it's
    injected too (tests point "desktop" at a tmp_path).
    """

    def __init__(self, executor: LocalExecutor, locations: dict[str, Path] | None = None) -> None:
        self._executor = executor
        self._actions: dict[str, Action] = {}

        for action_cls in _PRIMITIVE_ACTION_CLASSES:
            self._register(action_cls(locations))

        # WorkspaceBootstrapAction needs the executor itself (to relay
        # grants to, and invoke, its own sub-actions — ADR-0006) — this
        # is why composites aren't part of the generic loop above.
        self._register(WorkspaceBootstrapAction(executor, locations))

    def _register(self, action: Action) -> None:
        self._executor.register(action)
        self._actions[action.name] = action

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="filesystem",
            version="0.5.0",
            capabilities=[
                CapabilityManifest(
                    name=action.name,
                    description=action.description,
                    risk_tier=action.risk_tier,
                    permission_category=action.permission_category,
                )
                for action in self._actions.values()
            ],
        )

    def invoke(self, capability: str, payload: dict[str, Any]) -> InvocationResult:
        if capability not in self._actions:
            return InvocationResult(success=False, error=f"unsupported capability: {capability}")

        # Relay this call's already-obtained approval to the Executor's
        # own grant key — see module docstring. Deliberately NOT wrapped
        # in a try/except: ApprovalRequired should never actually be
        # raised by this check (a fresh ONCE grant always satisfies the
        # very next check for the same key), but if it somehow were, it
        # must propagate to the Orchestrator like any other
        # ApprovalRequired, not be swallowed here. True for all fourteen
        # capabilities, whether primitive or composite.
        self._executor.permissions.grant(self._executor.name, capability, GrantScope.ONCE)

        result = self._executor.execute(capability, payload)

        if not result.success:
            return InvocationResult(
                success=False,
                error="; ".join(result.errors) or "unknown executor failure",
                execution_time_seconds=result.execution_time_seconds,
            )
        return InvocationResult(
            success=True,
            output=result.output,
            execution_time_seconds=result.execution_time_seconds,
        )
