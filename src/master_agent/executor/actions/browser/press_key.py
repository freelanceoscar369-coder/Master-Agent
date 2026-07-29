"""PressKeyAction — wraps Playwright's keyboard.press() / Locator.press().
Distinct from TypeTextAction: this sends one control/character key (Enter,
Tab, Escape, ...), not a text value.
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

PRESS_KEY = "press_key"


class PressKeyAction(Action):
    name = PRESS_KEY
    description = "Press a keyboard key in an open browser session."
    risk_tier = RiskTier.REVERSIBLE_WRITE
    permission_category = PermissionCategory.MODIFY
    expected_result = "The given key was sent to the page or the matched element."

    def __init__(self, sessions: BrowserSessionManager) -> None:
        self._sessions = sessions

    def required_parameters(self) -> list[str]:
        return ["session_id", "key"]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not (parameters.get("session_id") or "").strip():
            errors.append("missing required parameter: session_id")
        if not (parameters.get("key") or "").strip():
            errors.append("missing required parameter: key")
        return errors

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        try:
            session = self._sessions.get(parameters["session_id"].strip())
        except BrowserSessionError as exc:
            return ExecutionResult(success=False, errors=[str(exc)])

        key = parameters["key"].strip()
        selector = (parameters.get("selector") or "").strip()
        timeout_ms = parameters.get("timeout_ms", DEFAULT_TIMEOUT_MS)

        try:
            if selector:
                session.page.locator(selector).press(key, timeout=timeout_ms)
            else:
                session.page.keyboard.press(key)
        except PlaywrightError as exc:
            return ExecutionResult(success=False, errors=[describe_playwright_failure(exc, "press_key")])
        except Exception as exc:  # noqa: BLE001
            return ExecutionResult(success=False, errors=[f"unexpected error during press_key: {exc}"])

        return ExecutionResult(success=True, output={"key": key, "selector": selector or None})
