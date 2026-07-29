"""NavigateAction — wraps Playwright's page.goto(). Kalpavriksha owns
nothing about navigation semantics; Playwright owns navigation entirely.
See BROWSER_WORKER_ARCHITECTURE.md §6.
"""
from __future__ import annotations

from typing import Any

from master_agent.environment.browser_session import BrowserSessionError, BrowserSessionManager
from master_agent.executor.action import Action, ExecutionResult
from master_agent.executor.actions.browser._common import (
    DEFAULT_TIMEOUT_MS,
    PlaywrightError,
    describe_playwright_failure,
)
from master_agent.plugins.base import PermissionCategory, RiskTier

NAVIGATE = "navigate"


class NavigateAction(Action):
    name = NAVIGATE
    description = "Navigate an open browser session to a URL."
    risk_tier = RiskTier.REVERSIBLE_WRITE
    permission_category = PermissionCategory.MODIFY
    expected_result = "The session's current page is the given URL."

    def __init__(self, sessions: BrowserSessionManager) -> None:
        self._sessions = sessions

    def required_parameters(self) -> list[str]:
        return ["session_id", "url"]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not (parameters.get("session_id") or "").strip():
            errors.append("missing required parameter: session_id")
        if not (parameters.get("url") or "").strip():
            errors.append("missing required parameter: url")
        timeout_ms = parameters.get("timeout_ms", DEFAULT_TIMEOUT_MS)
        if not isinstance(timeout_ms, (int, float)) or timeout_ms <= 0:
            errors.append("'timeout_ms' must be a positive number if provided")
        return errors

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        try:
            session = self._sessions.get(parameters["session_id"].strip())
        except BrowserSessionError as exc:
            return ExecutionResult(success=False, errors=[str(exc)])

        url = parameters["url"].strip()
        timeout_ms = parameters.get("timeout_ms", DEFAULT_TIMEOUT_MS)

        try:
            session.page.goto(url, timeout=timeout_ms)
        except PlaywrightError as exc:
            return ExecutionResult(success=False, errors=[describe_playwright_failure(exc, "navigate")])
        except Exception as exc:  # noqa: BLE001 — mechanical failure, never re-raised
            return ExecutionResult(success=False, errors=[f"unexpected error during navigate: {exc}"])

        return ExecutionResult(
            success=True,
            output={"url": session.page.url, "title": session.page.title()},
        )
