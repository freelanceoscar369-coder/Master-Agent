"""LocalExecutor — the only component allowed to perform local actions.

Every future local capability (create/read/rename/delete/copy/move file,
run PowerShell/CMD, git, VS Code, Obsidian, ...) registers an Action here
and runs through execute(). Nothing else in the codebase should touch the
filesystem, a shell, or any other local resource directly — that's the
whole point of this layer. See docs/MISSION_BRIEF_002.md.

## Why this checks permission itself, and how that interacts with the
## Orchestrator's existing check (read this before changing either)

The Orchestrator already gates plugin invocation on the Permission System
(orchestrator/orchestrator.py, unchanged by this module). A naive
second check here — on the same (plugin_name, capability) grant — would
break GrantScope.ONCE: the Orchestrator's check consumes the grant before
this code ever runs, so a second check on the same key always fails,
even immediately after a human approved it.

The fix is not to skip this check (that would make "the Executor is the
only component allowed to perform local actions" a lie for anything that
calls the Executor directly, bypassing a Plugin/Orchestrator entirely —
a real future case once actions like RunPowerShell exist). Instead, this
check uses its OWN grant key: (self.name, action.name) — a different key
from whatever a Plugin adapter is gated on. See
docs/adr/0005-executor-permission-relay.md for the full reasoning and
FilesystemPlugin.invoke() for how a Plugin adapter relays an
already-obtained human approval down to this key without asking twice.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from master_agent.executor.action import Action, ExecutionResult
from master_agent.permissions.permission_system import ApprovalRequired, PermissionSystem


@dataclass
class ExecutionLogEntry:
    action_name: str
    started_at: datetime
    ended_at: datetime
    duration_seconds: float
    status: str  # "success" | "failed" | "blocked_on_approval" | "invalid_parameters" | "unknown_action"


class LocalExecutor:
    def __init__(self, permissions: PermissionSystem, name: str = "local_executor") -> None:
        self._permissions = permissions
        self.name = name
        self._actions: dict[str, Action] = {}
        self._log: list[ExecutionLogEntry] = []

    @property
    def permissions(self) -> PermissionSystem:
        """Exposed so a Plugin adapter can relay an already-obtained
        approval to this executor's grant key — see module docstring."""
        return self._permissions

    def register(self, action: Action) -> None:
        if action.name in self._actions:
            raise ValueError(f"action already registered: {action.name}")
        self._actions[action.name] = action

    @property
    def log(self) -> list[ExecutionLogEntry]:
        return list(self._log)

    def execute(self, action_name: str, parameters: dict[str, Any]) -> ExecutionResult:
        """Never raises for ordinary failure — returns a structured
        ExecutionResult instead (unknown action, invalid parameters,
        or an action that crashed internally). The one exception this
        DOES let propagate is ApprovalRequired: that's not a failure,
        it's a request for a human decision, and callers (the Orchestrator,
        or any direct caller) must catch it and treat it as such, the same
        way Plugin.invoke() already does.
        """
        start = time.monotonic()
        started_at = datetime.now(timezone.utc)
        status = "failed"
        result: ExecutionResult

        action = self._actions.get(action_name)
        if action is None:
            duration = time.monotonic() - start
            result = ExecutionResult(
                success=False,
                errors=[f"unknown action: '{action_name}'"],
                execution_time_seconds=duration,
            )
            status = "unknown_action"
            self._record(action_name, started_at, start, status, duration)
            return result

        try:
            validation_errors = action.validate(parameters)
            if validation_errors:
                result = ExecutionResult(success=False, errors=validation_errors)
                status = "invalid_parameters"
                return result

            self._permissions.check(self.name, action.name, action.risk_tier)

            result = action.run(parameters)
            status = "success" if result.success else "failed"
            return result
        except ApprovalRequired:
            status = "blocked_on_approval"
            raise
        except Exception as exc:  # noqa: BLE001 — deliberate: never crash, never leak a traceback
            status = "failed"
            result = ExecutionResult(success=False, errors=[f"executor failure: {exc}"])
            return result
        finally:
            duration = time.monotonic() - start
            if status != "blocked_on_approval":
                result.execution_time_seconds = duration
            self._record(action.name, started_at, start, status, duration)

    def _record(self, action_name: str, started_at: datetime, start_monotonic: float, status: str, duration: float | None = None) -> None:
        if duration is None:
            duration = time.monotonic() - start_monotonic
        self._log.append(
            ExecutionLogEntry(
                action_name=action_name,
                started_at=started_at,
                ended_at=datetime.now(timezone.utc),
                duration_seconds=duration,
                status=status,
            )
        )
