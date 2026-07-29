"""CloseBrowserSessionAction — tears down an Environment Session opened by
OpenBrowserSessionAction. See BROWSER_WORKER_ARCHITECTURE.md §4.
"""
from __future__ import annotations

from typing import Any

from master_agent.environment.browser_session import BrowserSessionError, BrowserSessionManager
from master_agent.executor.action import Action, ExecutionResult
from master_agent.plugins.base import PermissionCategory, RiskTier

CLOSE_BROWSER_SESSION = "close_browser_session"


class CloseBrowserSessionAction(Action):
    name = CLOSE_BROWSER_SESSION
    description = "Close an open browser Environment Session."
    risk_tier = RiskTier.REVERSIBLE_WRITE
    permission_category = PermissionCategory.SYSTEM
    expected_result = "The named browser session is closed and its resources released."

    def __init__(self, sessions: BrowserSessionManager) -> None:
        self._sessions = sessions

    def required_parameters(self) -> list[str]:
        return ["session_id"]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not (parameters.get("session_id") or "").strip():
            errors.append("missing required parameter: session_id")
        return errors

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        session_id = parameters["session_id"].strip()
        try:
            warnings = self._sessions.close_session(session_id)
        except BrowserSessionError as exc:
            return ExecutionResult(success=False, errors=[str(exc)])

        return ExecutionResult(
            success=True,
            output={"session_id": session_id, "closed": True},
            warnings=warnings,
        )
