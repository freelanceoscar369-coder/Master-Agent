"""ClickAction — wraps Playwright's Locator.click(). Selectors are
Playwright's vocabulary (CSS/text/XPath), passed through verbatim; this
Worker never interprets or reasons about a selector's meaning.
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

CLICK = "click"


class ClickAction(Action):
    name = CLICK
    description = "Click an element in an open browser session."
    risk_tier = RiskTier.REVERSIBLE_WRITE
    permission_category = PermissionCategory.MODIFY
    expected_result = "The matched element received a click."

    def __init__(self, sessions: BrowserSessionManager) -> None:
        self._sessions = sessions

    def required_parameters(self) -> list[str]:
        return ["session_id", "selector"]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not (parameters.get("session_id") or "").strip():
            errors.append("missing required parameter: session_id")
        if not (parameters.get("selector") or "").strip():
            errors.append("missing required parameter: selector")
        return errors

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        try:
            session = self._sessions.get(parameters["session_id"].strip())
        except BrowserSessionError as exc:
            return ExecutionResult(success=False, errors=[str(exc)])

        selector = parameters["selector"].strip()
        timeout_ms = parameters.get("timeout_ms", DEFAULT_TIMEOUT_MS)

        try:
            session.page.locator(selector).click(timeout=timeout_ms)
        except PlaywrightError as exc:
            return ExecutionResult(success=False, errors=[describe_playwright_failure(exc, "click")])
        except Exception as exc:  # noqa: BLE001
            return ExecutionResult(success=False, errors=[f"unexpected error during click: {exc}"])

        return ExecutionResult(success=True, output={"selector": selector, "clicked": True})
