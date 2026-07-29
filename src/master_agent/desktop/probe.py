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
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

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
    in the catalog claims it -- absent rather than guessed."""

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

    def run(self, command: list[str]) -> CommandResult: ...

    def processes(self) -> list[ProcessInfo]: ...

    def start(self, command: list[str]) -> CommandResult: ...


class RealSystemProbe:
    """The real machine. Every method is defensive: a probe that raises
    would turn "we could not tell whether Docker is installed" into a
    failed mission, and not knowing is a normal answer here."""

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

    def run(self, command: list[str]) -> CommandResult:
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=False,
            )
        except FileNotFoundError:
            return CommandResult(ok=False, error=f"not found: {command[0]}")
        except subprocess.TimeoutExpired:
            return CommandResult(ok=False, error=f"timed out after {self._timeout}s")
        except Exception as exc:  # noqa: BLE001
            return CommandResult(ok=False, error=str(exc))

        output = (completed.stdout or "").strip() or (completed.stderr or "").strip()
        return CommandResult(
            ok=completed.returncode == 0,
            output=output,
            error="" if completed.returncode == 0 else (completed.stderr or "").strip(),
        )

    def start(self, command: list[str]) -> CommandResult:
        """Launch and do not wait. A founder asking for VS Code wants the
        editor, not a Runtime cycle blocked until they close it."""
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

    def processes(self) -> list[ProcessInfo]:
        if self.platform == "win32":
            return self._windows_processes()
        return self._posix_processes()

    def _windows_processes(self) -> list[ProcessInfo]:
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

    def _posix_processes(self) -> list[ProcessInfo]:
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


class NullSystemProbe:
    """A machine with nothing on it. Not a test double -- a real fallback,
    so a Desktop Executive constructed without a probe reports "nothing
    found" rather than crashing, and the Dashboard shows an honest empty
    inventory instead of a traceback."""

    platform = "null"

    def which(self, executable: str) -> str | None:
        return None

    def exists(self, path: str) -> bool:
        return False

    def run(self, command: list[str]) -> CommandResult:
        return CommandResult(ok=False, error=f"no probe configured: {command[0]}")

    def start(self, command: list[str]) -> CommandResult:
        return CommandResult(ok=False, error=f"no probe configured: {command[0]}")

    def processes(self) -> list[ProcessInfo]:
        return []
