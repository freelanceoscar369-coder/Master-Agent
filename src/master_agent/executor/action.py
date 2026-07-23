"""The Action Contract — the foundation every future local capability
(create/read/rename/delete/copy/move file, run PowerShell/CMD, git,
VS Code, Obsidian, ...) plugs into. See docs/MISSION_BRIEF_002.md for why
this exists and docs/adr/0005-executor-permission-relay.md for how it
interacts with the Permission System.

Deliberately small: name, description, risk tier, required parameters,
a validation step, and a run step. Anything more here makes writing a
new action expensive, which defeats the point of having a contract at
all.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from master_agent.plugins.base import PermissionCategory, RiskTier


def is_unsafe_relative_path(path: str) -> bool:
    """Shared by every action that accepts a relative path/name meant to
    be joined onto a configured location's base directory (CreateFolderAction's
    `name`, WriteFileAction's `path`, WorkspaceBootstrapAction's `name`/
    `folders`/`files[].path`). Rejects absolute paths and '..' segments —
    the one thing standing between that trust and a payload that escapes
    the base directory entirely."""
    parts = Path(path).parts
    return Path(path).is_absolute() or ".." in parts


def default_locations() -> dict[str, Path]:
    """The standard named location roots every filesystem Action resolves
    relative paths against when a caller doesn't inject its own (tests
    always inject one pointed at a tmp_path). Shared here — Mission
    Brief 002/003 had this dict literal duplicated once per Action
    (`{"desktop": Path.home() / "Desktop"}`); Mission Brief 005 adds two
    more roots (needed for "List files inside Downloads" to mean
    anything) and consolidates the default to one place, so a future
    fourth root is a one-line change instead of an N-line one. See
    FILESYSTEM_CAPABILITIES.md §6."""
    home = Path.home()
    return {
        "desktop": home / "Desktop",
        "downloads": home / "Downloads",
        "documents": home / "Documents",
    }


def resolve_into_or_as(source: Path, destination: Path) -> Path:
    """Shared by CopyFileAction/MoveFileAction: "copy X to backup folder"
    means *into* backup (keeping X's filename); "copy X to X.bak" means
    *as* that literal new path. If `destination` already exists as a
    directory, the source lands inside it under its own name; otherwise
    `destination` is the final path itself. One small function instead of
    this resolution logic living twice — FILESYSTEM_CAPABILITIES.md §2
    ("Never duplicate business logic")."""
    if destination.exists() and destination.is_dir():
        return destination / source.name
    return destination


def resolve_overwrite_error(target: Path, overwrite: bool) -> str | None:
    """Shared by RenameFileAction/CopyFileAction/MoveFileAction: refuse to
    replace an existing destination unless the caller explicitly opted in
    via `payload["overwrite"] = True`. Returns an error message if the
    operation should be refused, or None if it's safe to proceed. See
    FILESYSTEM_CAPABILITIES.md §6 ("Overwrite behaviour")."""
    if target.exists() and not overwrite:
        return f"{target} already exists (set 'overwrite': true to replace it)"
    return None


@dataclass
class ExecutionResult:
    """What every action run — and every executor.execute() call —
    returns. `execution_time_seconds` is set by the Executor, not the
    Action itself (the Action doesn't know how long it took; timing is
    the Executor's job, not the action's)."""

    success: bool
    output: Any = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    execution_time_seconds: float = 0.0


class Action(ABC):
    """One executable local action. Implementations declare the contract
    fields as class attributes and implement validate()/run().

    validate() must never touch the filesystem or perform side effects —
    it's a pure check, called before permission is even consulted, so a
    malformed request fails fast without ever bothering the human or the
    Permission System.

    run() performs the actual work. It should not raise for ordinary
    failures — return `ExecutionResult(success=False, errors=[...])`
    instead. The Executor catches anything that escapes anyway (see
    executor.py), but a well-behaved action returns structured failures
    on its own.
    """

    name: str
    description: str
    risk_tier: RiskTier
    permission_category: PermissionCategory
    expected_result: str

    @abstractmethod
    def required_parameters(self) -> list[str]:
        """Names of parameters this action requires in its payload —
        documentation as much as contract; validate() is what's actually
        enforced."""

    @abstractmethod
    def validate(self, parameters: dict[str, Any]) -> list[str]:
        """Return validation error messages; empty list means valid."""

    @abstractmethod
    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        """Perform the work. Only ever called after validate() passed and
        permission (if the risk tier requires it) was granted."""
