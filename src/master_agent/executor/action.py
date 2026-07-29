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
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from master_agent.plugins.base import PermissionCategory, RiskTier


def is_unsafe_relative_path(path: str) -> bool:
    """Shared by every action that accepts a relative path/name meant to
    be joined onto a configured location's base directory (CreateFolderAction's
    `name`, WriteFileAction's `path`, WorkspaceBootstrapAction's `name`/
    `folders`/`files[].path`). Rejects anything that is not a plain
    relative path — the one thing standing between that trust and a
    payload that escapes the base directory entirely.

    ## Why both path flavours are checked (Mission Brief 023.1)

    The original implementation used `Path(...)`, which is whichever
    flavour the *host* happens to be, and that made the guard weaker on
    Windows than on POSIX for exactly the inputs an attacker would try:

        PureWindowsPath("/etc/passwd").is_absolute()  -> False
        PureWindowsPath("D:config").is_absolute()     -> False

    Both are root- or drive-anchored and neither is a safe relative path,
    but on Windows the old check passed them. Separator handling had the
    mirror problem: `PurePosixPath("..\\\\escape").parts` is one opaque
    segment, so a backslash traversal was invisible to a POSIX host.

    Checking the string against *both* flavours, and rejecting on
    `anchor` rather than only `is_absolute()`, makes the guard identical
    on every platform — a sandbox boundary that depends on which OS you
    happen to run is not a boundary.
    """
    if not isinstance(path, str) or not path.strip():
        return True

    for flavour in (PurePosixPath, PureWindowsPath):
        candidate = flavour(path)
        # `anchor` catches drive-relative ("D:config") and root-relative
        # ("/etc/passwd") forms that is_absolute() misses on Windows.
        if candidate.is_absolute() or candidate.anchor:
            return True
        if ".." in candidate.parts:
            return True

    return False


def to_portable_relative_str(path: Path, root: Path) -> str:
    """Render `path` relative to `root` with forward slashes on every
    platform.

    Action output travels: it lands in an `ExecutionResult`, then in a
    persisted `MissionRecord`, and eventually in Evidence a future
    Planner reads. Emitting the host's native separator would make that
    stored history platform-dependent — the same mission recorded on two
    machines would not compare equal. Forward slashes are the portable
    choice and are valid input back into `Path()` on Windows too.
    """
    return path.relative_to(root).as_posix()


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
