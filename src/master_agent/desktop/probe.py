"""The one place the Desktop Executive touches the real machine.

Everything else in `desktop/` is pure logic over what a probe returns.
That split is what makes a hundred tests possible without launching
Chrome on the founder's laptop, and it is the same shape MB024 used for
`ExecutiveGateway`: a small protocol, one real implementation, and a fake
in tests.

**This module knows nothing about AI.** It answers "is this executable on
the PATH", "what did `--version` print", "what is running". It does not
know what a model is, cannot compare two providers, and has no opinion
about which of two installed things is better — those belong exclusively
to the future AI Capability Broker (MB030 Rules 2 and 11).
"""
from __future__ import annotations

import os
import shutil
import subprocess

from master_agent.foundation.windowless import NO_WINDOW
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, List, Dict, Optional

#: How long any probed subprocess is allowed to take. A version check that
#: hangs must never hang the Runtime cycle that asked for it.
PROBE_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    output: str = ""
    error: str = ""


@dataclass(frozen=True)
class ProcessInfo:
    """One running process, as the machine reports it. `owner` is the
    application this process is judged to belong to, or None when nothing
    in the catalog claims it -- absent rather than guessed.
    """

    pid: int
    name: str
    owner: str | None = None
    window_title: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "pid": self.pid,
            "name": self.name,
            "owner": self.owner,
            "window_title": self.window_title,
        }


class SystemProbe(Protocol):
    """What the Desktop Executive is allowed to ask the machine."""

    @property
    def platform(self) -> str: ...

    def which(self, executable: str) -> str | None: ...

    def exists(self, path: str) -> bool: ...

    def run(self, command: List[str]) -> CommandResult: ...

    def processes(self) -> List[ProcessInfo]: ...

    def start(self, command: List[str]) -> CommandResult: ...

    # New methods for generic Windows application discovery
    def get_store_apps(self) -> List[Dict[str, Optional[str]]]: ...
    def get_uninstall_apps(self) -> List[Dict[str, Optional[str]]]: ...
    def get_start_apps(self) -> List[Dict[str, Optional[str]]]: ...


class RealSystemProbe:
    """The real machine. Every method is defensive: a probe that raises
    would turn "we could not tell whether Docker is installed" into a
    failed mission, and not knowing is a normal answer here.
    """

    def __init__(self, timeout: float = PROBE_TIMEOUT_SECONDS) -> None:
        self._timeout = timeout

    @property
    def platform(self) -> str:
        return sys.platform

    def which(self, executable: str) -> str | None:
        try:
            return shutil.which(executable)
        except Exception:  # noqa: BLE001 - not knowing is an answer
            return None

    def exists(self, path: str) -> bool:
        try:
            return Path(os.path.expandvars(path)).exists()
        except Exception:  # noqa: BLE001
            return False

    def run(self, command: List[str]) -> CommandResult:
        return self._run(command, timeout=self._timeout)

    def _run(self, command: List[str], timeout: float) -> CommandResult:
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                creationflags=NO_WINDOW,
                text=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError:
            return CommandResult(ok=False, error=f"not found: {command[0]}")
        except subprocess.TimeoutExpired:
            return CommandResult(ok=False, error=f"timed out after {timeout}s")
        except Exception as exc:  # noqa: BLE001
            return CommandResult(ok=False, error=str(exc))

        output = (completed.stdout or "").strip() or (completed.stderr or "").strip()
        return CommandResult(
            ok=completed.returncode == 0,
            output=output,
            error="" if completed.returncode == 0 else (completed.stderr or "").strip(),
        )

    def start(self, command: List[str]) -> CommandResult:
        """Launch and do not wait. A founder asking for VS Code wants the
        editor, not a Runtime cycle blocked until they close it.
        """
        try:
            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except FileNotFoundError:
            return CommandResult(ok=False, error=f"not found: {command[0]}")
        except Exception as exc:  # noqa: BLE001
            return CommandResult(ok=False, error=str(exc))
        return CommandResult(ok=True, output=" ".join(command))

    def processes(self) -> List[ProcessInfo]:
        if self.platform == "win32":
            return self._windows_processes()
        return self._posix_processes()

    def _windows_processes(self) -> List[ProcessInfo]:
        result = self.run(["tasklist", "/FO", "CSV", "/NH"])
        if not result.ok:
            return []
        found = []
        for line in result.output.splitlines():
            fields = [field.strip('"') for field in line.split('","')]
            if len(fields) < 2:
                continue
            name = fields[0].strip('"')
            try:
                pid = int(fields[1].strip('"'))
            except ValueError:
                continue
            found.append(ProcessInfo(pid=pid, name=name))
        return found

    def _posix_processes(self) -> List[ProcessInfo]:
        result = self.run(["ps", "-eo", "pid=,comm="])
        if not result.ok:
            return []
        found = []
        for line in result.output.splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) != 2:
                continue
            try:
                pid = int(parts[0])
            except ValueError:
                continue
            found.append(ProcessInfo(pid=pid, name=Path(parts[1]).name))
        return found

    def get_store_apps(self) -> List[Dict[str, Optional[str]]]:
        """Return a list of dictionaries representing installed Store/AppX applications.
        Each dictionary contains:
            - Name: the display name of the application.
            - PackageFullName: the full package name.
            - PackageFamilyName: the package family name.
            - Publisher: the publisher of the application.
            - Version: the version of the application.
            - InstallLocation: the installation location of the application.
            - AppUserModelID: the AppUserModelID for launching the application.
        """
        apps: List[Dict[str, Optional[str]]] = []
        if self.platform != "win32":
            return apps
        try:
            # Get-AppxPackage returns all apps for the current user.
            # We select the properties we need.
            command = [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-AppxPackage | Select-Object Name, PackageFullName, PackageFamilyName, Publisher, Version, InstallLocation | ConvertTo-Json",
            ]
            result = self.run(command)
            if not result.ok:
                return apps
            import json

            # The output might be a single object or an array of objects.
            data = json.loads(result.output)
            if isinstance(data, dict):
                data = [data]
            for app in data:
                package_family_name = app.get("PackageFamilyName")
                app_user_model_id = None
                if package_family_name:
                    app_user_model_id = f"{package_family_name}!App"
                apps.append(
                    {
                        "Name": app.get("Name"),
                        "PackageFullName": app.get("PackageFullName"),
                        "PackageFamilyName": package_family_name,
                        "Publisher": app.get("Publisher"),
                        "Version": app.get("Version"),
                        "InstallLocation": app.get("InstallLocation"),
                        "AppUserModelID": app_user_model_id,
                    }
                )
        except Exception:  # noqa: BLE001
            # If anything goes wrong, we return an empty list.
            # Not knowing is an answer.
            pass
        return apps

    def get_uninstall_apps(self) -> List[Dict[str, Optional[str]]]:
        """Return a list of dictionaries representing installed applications from the uninstall registry.
        Each dictionary contains:
            - DisplayName: the display name of the application.
            - Publisher: the publisher of the application.
            - DisplayVersion: the version of the application.
            - InstallLocation: the installation location of the application.
            - UninstallString: the uninstall command.
        """
        apps: List[Dict[str, Optional[str]]] = []
        if self.platform != "win32":
            return apps
        try:
            # We query the uninstall registry keys for both 32-bit and 64-bit, and for current user and local machine.
            registry_paths = [
                "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall",
                "HKLM:\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall",
                "HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall",
            ]
            for path in registry_paths:
                command = [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"Get-ItemProperty -Path '{path}\\*' | Select-Object DisplayName, Publisher, DisplayVersion, InstallLocation, UninstallString | Where-Object {{$_.DisplayName -ne ''}} | ConvertTo-Json",
                ]
                result = self.run(command)
                if not result.ok:
                    continue
                import json

                data = json.loads(result.output)
                if isinstance(data, dict):
                    data = [data]
                for app in data:
                    apps.append(
                        {
                            "DisplayName": app.get("DisplayName"),
                            "Publisher": app.get("Publisher"),
                            "DisplayVersion": app.get("DisplayVersion"),
                            "InstallLocation": app.get("InstallLocation"),
                            "UninstallString": app.get("UninstallString"),
                        }
                    )
        except Exception:  # noqa: BLE001
            pass
        return apps

    def get_start_apps(self) -> List[Dict[str, Optional[str]]]:
        """Return every application Windows itself considers launchable
        from the Start Menu — `Get-StartApps`' own `shell:AppsFolder`
        backing store. This is the single strongest universal discovery
        source available without a third-party dependency: it covers
        traditional installers (a `.lnk` shortcut with a registered
        AppUserModelID), MSIX/UWP packages, and PWAs alike, in one call,
        without this module needing to know which install mechanism any
        given application used.

        Each dictionary contains:
            - Name: the display name Windows shows for it.
            - AppID: either a real AppUserModelID (launchable via
              `explorer.exe shell:AppsFolder\\<AppID>`) or, for some
              legacy shortcuts, a raw file/special-folder path Windows
              had nothing better to report — `discover()` tells these
              apart before choosing how to launch either.
        """
        apps: List[Dict[str, Optional[str]]] = []
        if self.platform != "win32":
            return apps
        try:
            command = [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json",
            ]
            # `Get-StartApps` walks the whole shell:AppsFolder namespace
            # (163 entries on a real dev machine) — measured live at
            # ~2-5s even with `-NoProfile`, wide enough variance that
            # `self._timeout`'s general-purpose default (sized for a
            # single `--version` invocation) cuts it close. This is the
            # one probe call whose own cost genuinely varies with how
            # much is installed, so it gets its own longer allowance
            # rather than raising the default for every other probe.
            result = self._run(command, timeout=max(self._timeout, 15.0))
            if not result.ok:
                return apps
            import json

            data = json.loads(result.output)
            if isinstance(data, dict):
                data = [data]
            for app in data:
                name = app.get("Name")
                app_id = app.get("AppID")
                if name and app_id:
                    apps.append({"Name": name, "AppID": app_id})
        except Exception:  # noqa: BLE001
            pass
        return apps


class NullSystemProbe:
    """A machine with nothing on it. Not a test double -- a real fallback,
    so a Desktop Executive constructed without a probe reports "nothing
    found" rather than crashing, and the Dashboard shows an honest empty
    inventory instead of a traceback.
    """

    platform = "null"

    def which(self, executable: str) -> str | None:
        return None

    def exists(self, path: str) -> bool:
        return False

    def run(self, command: List[str]) -> CommandResult:
        return CommandResult(ok=False, error=f"no probe configured: {command[0]}")

    def start(self, command: List[str]) -> CommandResult:
        return CommandResult(ok=False, error=f"no probe configured: {command[0]}")

    def processes(self) -> List[ProcessInfo]:
        return []

    def get_store_apps(self) -> List[Dict[str, Optional[str]]]:
        return []

    def get_uninstall_apps(self) -> List[Dict[str, Optional[str]]]:
        return []

    def get_start_apps(self) -> List[Dict[str, Optional[str]]]:
        return []