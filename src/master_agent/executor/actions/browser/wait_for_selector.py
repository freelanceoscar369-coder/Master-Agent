"""WaitForSelectorAction — wraps Playwright's Locator.wait_for().
READ_ONLY: waiting observes; it never mutates page state.
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

WAIT_FOR_SELECTOR = "wait_for_selector"
_VALID_STATES = {"attached", "detached", "visible", "hidden"}


class WaitForSelectorAction(Action):
    name = WAIT_FOR_SELECTOR
    description = "Wait for an element to reach a given state in an open browser session."
    risk_tier = RiskTier.READ_ONLY
    permission_category = PermissionCategory.READ
    expected_result = "The matched element reached the requested state before the timeout."

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
        state = parameters.get("state", "visible")
        if state not in _VALID_STATES:
            errors.append(f"'state' must be one of {sorted(_VALID_STATES)}")
        return errors

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        try:
            session = self._sessions.get(parameters["session_id"].strip())
        except BrowserSessionError as exc:
            return ExecutionResult(success=False, errors=[str(exc)])

        selector = parameters["selector"].strip()
        state = parameters.get("state", "visible")
        timeout_ms = parameters.get("timeout_ms", DEFAULT_TIMEOUT_MS)

        try:
            session.page.locator(selector).wait_for(state=state, timeout=timeout_ms)
        except PlaywrightError as exc:
            return ExecutionResult(
                success=False, errors=[describe_playwright_failure(exc, "wait_for_selector")]
            )
        except Exception as exc:  # noqa: BLE001
            return ExecutionResult(success=False, errors=[f"unexpected error during wait_for_selector: {exc}"])

        return ExecutionResult(success=True, output={"selector": selector, "state": state})
