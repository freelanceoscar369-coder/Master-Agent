"""The Desktop Executive's twelve capabilities (Mission Brief 030).

Each one is an `Action` on the existing contract (MB002), registered on
the existing `LocalExecutor`, exposed through the existing `Plugin`
interface, discovered by the existing Mission Control adapter. **No
architecture changed to make this work** — which is the strongest evidence
that MB002's contract generalises, and MB030's Rule 5 asked for exactly
that restraint.

Risk tiers are declared honestly, because the approval boundary (MB028.0)
gates on them and a wrong tier here is a wrong tier everywhere:

- **READ_ONLY** — asking. Installed, version, running, listings.
- **REVERSIBLE_WRITE** — launching, opening, focusing. Undone by closing.
- **IRREVERSIBLE** — closing an application (unsaved work is gone) and
  running an arbitrary command (anything at all). ADR-0009 guarantees no
  standing grant can ever satisfy these, so each is a fresh founder
  decision every time.

Deliberately absent (Deliverable 7): no click, no type, no mouse, no OCR,
no vision, no keyboard automation. Discover, launch, close, inspect.
"""
from __future__ import annotations

import os
from typing import Any

from master_agent.desktop import catalog
from master_agent.desktop.inventory import MachineInventory, discover, observations, refresh_processes_only
from master_agent.desktop.probe import NullSystemProbe, SystemProbe
from master_agent.executor.action import Action, ExecutionResult
from master_agent.plugins.base import PermissionCategory, RiskTier

LAUNCH_APPLICATION = "launch_application"
CLOSE_APPLICATION = "close_application"
IS_INSTALLED = "is_installed"
GET_VERSION = "get_version"
LIST_INSTALLED_SOFTWARE = "list_installed_software"
LIST_RUNNING_PROCESSES = "list_running_processes"
IS_RUNNING = "is_running"
BRING_TO_FRONT = "bring_to_front"
FOCUS_WINDOW = "focus_window"
OPEN_FILE = "open_file"
OPEN_FOLDER = "open_folder"
EXECUTE_COMMAND = "execute_command"


class DesktopContext:
    """Shared state for every Desktop action: the probe, and the last
    inventory taken.

    The cache exists because discovery shells out once per application and
    a founder asking "is Git installed" should not pay for a full machine
    scan. `refresh()` is what a discovery capability calls; everything
    else reads. The Dashboard reads it too — see `plugin.inventory()`.
    """

    def __init__(self, probe: SystemProbe | None = None) -> None:
        self.probe: SystemProbe = probe or NullSystemProbe()
        self._inventory: MachineInventory | None = None
        #: Whether `self._inventory` was populated by a deep scan.
        #: `refresh(deep=False)` overwrites `self._inventory` with a
        #: cheap, process-only snapshot (deliberately — that is its whole
        #: point), which would otherwise silently downgrade a previously
        #: deep-scanned cache: launch Chrome (deep scan, cached) -> focus
        #: Chrome (`refresh(deep=False)`, cache now shallow) -> launch
        #: Claude next would see the *stale shallow* cache and miss its
        #: Start Menu match, since `inventory()`'s only prior staleness
        #: signal was "is there a cache at all", not "is it deep enough
        #: for what I'm asking". Tracking this explicitly is what lets
        #: `inventory(deep=True)` notice and re-scan instead.
        self._inventory_is_deep = False

    def refresh(self, read_versions: bool = True, deep: bool = True) -> MachineInventory:
        """`deep=True` (default) is Universal Windows Environment
        Discovery's DEEP PATH — `Get-StartApps`/`Get-AppxPackage`/the
        registry uninstall keys, several real seconds of subprocess cost.
        `deep=False` is the FAST PATH: running-process attribution plus
        each catalog spec's own PATH/known-path check — nothing a
        per-action refresh (confirming a window still exists, say)
        should ever pay for. Every caller that calls `refresh()`
        specifically because it wants *current* process state, not a
        fresh full machine scan, must pass `deep=False` explicitly.

        When a deep scan is already cached, `deep=False` reuses its
        Start Menu/MSIX/registry-derived records and only re-reads the
        process list (`inventory.refresh_processes_only`) instead of
        discarding them — live evidence this mattered: without it, every
        verified interaction action's own fast "is the window still
        there" refresh silently downgraded the shared cache, so
        launching Chrome then Notepad back-to-back each independently
        re-paid the full ~25s deep-scan cost instead of the second call
        being instant.
        """
        if not deep and self._inventory is not None and self._inventory_is_deep:
            self._inventory = refresh_processes_only(self.probe, self._inventory)
            return self._inventory
        self._inventory = discover(self.probe, read_versions=read_versions, deep=deep)
        self._inventory_is_deep = deep
        return self._inventory

    def inventory(self, read_versions: bool = True, deep: bool = True) -> MachineInventory:
        if self._inventory is None or (deep and not self._inventory_is_deep):
            return self.refresh(read_versions=read_versions, deep=deep)
        return self._inventory

    @property
    def cached(self) -> MachineInventory | None:
        return self._inventory


class _DesktopAction(Action):
    """Base: holds the context, and resolves an application name the way a
    founder would type it."""

    permission_category = PermissionCategory.READ

    def __init__(self, context: DesktopContext) -> None:
        self._context = context

    @property
    def probe(self) -> SystemProbe:
        return self._context.probe

    def _spec(self, name: str) -> catalog.ApplicationSpec | None:
        return catalog.resolve(name)

    def _require_known_application(self, parameters: dict[str, Any]) -> list[str]:
        name = (parameters.get("application") or "").strip()
        if not name:
            return ["missing required parameter: application"]
        if self._spec(name) is None:
            known = ", ".join(sorted(s.key for s in catalog.CATALOG))
            return [f"unknown application '{name}' (known: {known})"]
        return []


# ---- asking (READ_ONLY) -------------------------------------------------


class IsInstalledAction(_DesktopAction):
    name = IS_INSTALLED
    description = "Report whether a known application is installed."
    risk_tier = RiskTier.READ_ONLY
    expected_result = "Whether the application is installed is reported; nothing changes."

    def required_parameters(self) -> list[str]:
        return ["application"]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        return self._require_known_application(parameters)

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        spec = self._spec(parameters["application"])
        found = self._context.inventory().get(spec.key)
        return ExecutionResult(success=True, output=found.as_dict())


class GetVersionAction(_DesktopAction):
    name = GET_VERSION
    description = "Report the installed version of a known application."
    risk_tier = RiskTier.READ_ONLY
    expected_result = "The reported version string, or that none was reported."

    def required_parameters(self) -> list[str]:
        return ["application"]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        return self._require_known_application(parameters)

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        spec = self._spec(parameters["application"])
        found = self._context.refresh().get(spec.key)
        return ExecutionResult(
            success=True,
            output={
                "application": spec.key,
                "name": spec.label,
                "version": found.version,
                "installed": found.installed,
            },
        )


class ListInstalledSoftwareAction(_DesktopAction):
    name = LIST_INSTALLED_SOFTWARE
    description = "List every known application and whether it is installed."
    risk_tier = RiskTier.READ_ONLY
    expected_result = "The machine inventory is returned; nothing changes."

    def required_parameters(self) -> list[str]:
        return []

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        category = (parameters.get("category") or "").strip().lower()
        known = {spec.category for spec in catalog.CATALOG}
        if category and category not in known:
            return [f"unknown category '{category}' (known: {', '.join(sorted(known))})"]
        return []

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        inventory = self._context.refresh()
        category = (parameters.get("category") or "").strip().lower()
        applications = [
            a for a in inventory.applications if not category or a.category == category
        ]
        return ExecutionResult(
            success=True,
            output={
                "platform": inventory.platform,
                "applications": [a.as_dict() for a in applications],
                "installed_count": sum(1 for a in applications if a.installed),
                "observations": observations(inventory),
            },
        )


class ListRunningProcessesAction(_DesktopAction):
    name = LIST_RUNNING_PROCESSES
    description = "List running processes, with the application each belongs to."
    risk_tier = RiskTier.READ_ONLY
    expected_result = "The running process list is returned; nothing changes."

    def required_parameters(self) -> list[str]:
        return []

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        return []

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        inventory = self._context.refresh(read_versions=False, deep=False)
        owned_only = bool(parameters.get("owned_only"))
        processes = [
            p for p in inventory.processes if not owned_only or p.owner is not None
        ]
        return ExecutionResult(
            success=True,
            output={
                "count": len(processes),
                "processes": [p.as_dict() for p in processes],
            },
        )


class IsRunningAction(_DesktopAction):
    name = IS_RUNNING
    description = "Report whether a known application is currently running."
    risk_tier = RiskTier.READ_ONLY
    expected_result = "Whether the application is running is reported; nothing changes."

    def required_parameters(self) -> list[str]:
        return ["application"]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        return self._require_known_application(parameters)

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        spec = self._spec(parameters["application"])
        inventory = self._context.refresh(read_versions=False, deep=False)
        running = inventory.running(spec.key)
        return ExecutionResult(
            success=True,
            output={
                "application": spec.key,
                "running": bool(running),
                "processes": [p.as_dict() for p in running],
            },
        )


# ---- acting (REVERSIBLE_WRITE) ------------------------------------------


class LaunchApplicationAction(_DesktopAction):
    name = LAUNCH_APPLICATION
    description = "Launch a known installed application."
    risk_tier = RiskTier.REVERSIBLE_WRITE
    permission_category = PermissionCategory.SYSTEM
    expected_result = "The application is started; closing it undoes this."

    def required_parameters(self) -> list[str]:
        return ["application"]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        return self._require_known_application(parameters)

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        spec = self._spec(parameters["application"])
        found = self._context.inventory().get(spec.key)
        if not found.installed or not found.path:
            return ExecutionResult(
                success=False, errors=[f"{spec.label} is not installed"]
            )
        result = self.probe.start([found.path])
        if not result.ok:
            return ExecutionResult(success=False, errors=[result.error])
        return ExecutionResult(
            success=True, output={"application": spec.key, "launched": found.path}
        )


class OpenFileAction(_DesktopAction):
    name = OPEN_FILE
    description = "Open a file with the system's default application."
    risk_tier = RiskTier.REVERSIBLE_WRITE
    permission_category = PermissionCategory.SYSTEM
    expected_result = "The file is opened in whatever the system associates with it."

    def required_parameters(self) -> list[str]:
        return ["path"]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        path = (parameters.get("path") or "").strip()
        if not path:
            return ["missing required parameter: path"]
        if not self.probe.exists(path):
            return [f"no such path: {path}"]
        return []

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        path = os.path.expandvars(parameters["path"].strip())
        result = self.probe.start(_open_command(self.probe.platform, path))
        if not result.ok:
            return ExecutionResult(success=False, errors=[result.error])
        return ExecutionResult(success=True, output={"opened": path})


class OpenFolderAction(OpenFileAction):
    name = OPEN_FOLDER
    description = "Open a folder in the system's file browser."
    expected_result = "The folder is opened in the system file browser."


class BringToFrontAction(_DesktopAction):
    """Focus is a *window* operation, and this Executive deliberately has
    no window automation (Deliverable 7). So it reports honestly that it
    cannot, rather than pretending — a capability that silently does
    nothing is worse than one that says it is not built."""

    name = BRING_TO_FRONT
    description = "Bring a running application's window to the front."
    risk_tier = RiskTier.REVERSIBLE_WRITE
    permission_category = PermissionCategory.SYSTEM
    expected_result = "The application's window is focused, where supported."

    def required_parameters(self) -> list[str]:
        return ["application"]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        return self._require_known_application(parameters)

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        spec = self._spec(parameters["application"])
        inventory = self._context.refresh(read_versions=False, deep=False)
        running = inventory.running(spec.key)
        if not running:
            return ExecutionResult(
                success=False, errors=[f"{spec.label} is not running"]
            )
        return ExecutionResult(
            success=False,
            errors=[
                (
                    "window focus needs desktop interaction, which MB030 "
                    "deliberately excludes (Deliverable 7); a later Desktop "
                    "Interaction brief owns this"
                )
            ],
            output={"application": spec.key, "pids": [p.pid for p in running]},
        )


class FocusWindowAction(BringToFrontAction):
    name = FOCUS_WINDOW
    description = "Focus a specific window of a running application."


# ---- irreversible -------------------------------------------------------


class CloseApplicationAction(_DesktopAction):
    """`IRREVERSIBLE` on purpose. Closing an editor with unsaved work
    destroys it, and no amount of "it usually prompts" makes that
    reversible. ADR-0009 therefore guarantees no standing grant can ever
    authorise it."""

    name = CLOSE_APPLICATION
    description = "Close a running application."
    risk_tier = RiskTier.IRREVERSIBLE
    permission_category = PermissionCategory.SYSTEM
    expected_result = "The application is closed; unsaved work in it is lost."

    def required_parameters(self) -> list[str]:
        return ["application"]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        return self._require_known_application(parameters)

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        spec = self._spec(parameters["application"])
        inventory = self._context.refresh(read_versions=False, deep=False)
        running = inventory.running(spec.key)
        if not running:
            return ExecutionResult(
                success=False, errors=[f"{spec.label} is not running"]
            )
        closed, failures = [], []
        for process in running:
            result = self.probe.run(_kill_command(self.probe.platform, process.pid))
            (closed if result.ok else failures).append(process.pid)
        if failures and not closed:
            return ExecutionResult(
                success=False, errors=[f"could not close pids: {failures}"]
            )
        return ExecutionResult(
            success=True,
            output={"application": spec.key, "closed": closed, "failed": failures},
        )


class ExecuteCommandAction(_DesktopAction):
    """`IRREVERSIBLE`, and the reason is not subtle: this runs whatever it
    is given. It is argv-only — never a shell string — so a payload cannot
    smuggle a pipeline or a redirect, and every invocation is a fresh
    founder decision (ADR-0009)."""

    name = EXECUTE_COMMAND
    description = "Run a command and return its output."
    risk_tier = RiskTier.IRREVERSIBLE
    permission_category = PermissionCategory.SYSTEM
    expected_result = "The command runs and its output is returned."

    def required_parameters(self) -> list[str]:
        return ["command"]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        command = parameters.get("command")
        if isinstance(command, str):
            return [
                (
                    "command must be a list of arguments, not a string - a "
                    "shell string would let a payload smuggle pipelines and "
                    "redirects"
                )
            ]
        if not isinstance(command, list) or not command:
            return ["missing required parameter: command (a non-empty list)"]
        if not all(isinstance(part, str) and part.strip() for part in command):
            return ["every command argument must be a non-empty string"]
        return []

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        command = [str(part) for part in parameters["command"]]
        result = self.probe.run(command)
        return ExecutionResult(
            success=result.ok,
            output={"command": command, "output": result.output},
            errors=[] if result.ok else [result.error or "command failed"],
        )


def _open_command(platform: str, path: str) -> list[str]:
    if platform == "win32":
        return ["cmd", "/c", "start", "", path]
    if platform == "darwin":
        return ["open", path]
    return ["xdg-open", path]


def _kill_command(platform: str, pid: int) -> list[str]:
    if platform == "win32":
        return ["taskkill", "/PID", str(pid), "/T"]
    return ["kill", str(pid)]


#: Registered declaratively, so capability #13 is one new class in this
#: tuple and no edit anywhere else (Constitution Rule 3).
DESKTOP_ACTION_CLASSES: tuple[type[_DesktopAction], ...] = (
    IsInstalledAction,
    GetVersionAction,
    ListInstalledSoftwareAction,
    ListRunningProcessesAction,
    IsRunningAction,
    LaunchApplicationAction,
    OpenFileAction,
    OpenFolderAction,
    BringToFrontAction,
    FocusWindowAction,
    CloseApplicationAction,
    ExecuteCommandAction,
)
