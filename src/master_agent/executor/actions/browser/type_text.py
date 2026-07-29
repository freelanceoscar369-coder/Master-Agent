"""TypeTextAction — wraps Playwright's Locator.fill(). Sets an input/
textarea's value directly (clearing whatever was there first), which is
Playwright's own recommended way to enter text reliably — this Worker
does not reimplement keystroke simulation.
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

TYPE_TEXT = "type_text"


class TypeTextAction(Action):
    name = TYPE_TEXT
    description = "Set an element's text content in an open browser session."
    risk_tier = RiskTier.REVERSIBLE_WRITE
    permission_category = PermissionCategory.WRITE
    expected_result = "The matched element's value equals the given text."

    def __init__(self, sessions: BrowserSessionManager) -> None:
        self._sessions = sessions

    def required_parameters(self) -> list[str]:
        return ["session_id", "selector", "text"]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not (parameters.get("session_id") or "").strip():
            errors.append("missing required parameter: session_id")
        if not (parameters.get("selector") or "").strip():
            errors.append("missing required parameter: selector")
        if not isinstance(parameters.get("text", ""), str):
            errors.append("'text' must be a string")
        return errors

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        try:
            session = self._sessions.get(parameters["session_id"].strip())
        except BrowserSessionError as exc:
            return ExecutionResult(success=False, errors=[str(exc)])

        selector = parameters["selector"].strip()
        text = parameters.get("text", "")
        timeout_ms = parameters.get("timeout_ms", DEFAULT_TIMEOUT_MS)

        try:
            session.page.locator(selector).fill(text, timeout=timeout_ms)
        except PlaywrightError as exc:
            return ExecutionResult(success=False, errors=[describe_playwright_failure(exc, "type_text")])
        except Exception as exc:  # noqa: BLE001
            return ExecutionResult(success=False, errors=[f"unexpected error during type_text: {exc}"])

        return ExecutionResult(success=True, output={"selector": selector, "text": text})
