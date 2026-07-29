"""ScrollAction — wraps Playwright's Locator.scroll_into_view_if_needed()
(when a selector is given) or Mouse.wheel() (when raw deltas are given).
"""
from __future__ import annotations

from typing import Any

from master_agent.environment.browser_session import BrowserSessionError, BrowserSessionManager
from master_agent.executor.action import Action, ExecutionResult
from master_agent.executor.actions.browser._common import (
    PlaywrightError,
    describe_playwright_failure,
)
from master_agent.plugins.base import PermissionCategory, RiskTier

SCROLL = "scroll"


class ScrollAction(Action):
    name = SCROLL
    description = "Scroll an open browser session, either to an element or by a pixel delta."
    risk_tier = RiskTier.REVERSIBLE_WRITE
    permission_category = PermissionCategory.MODIFY
    expected_result = "The page or the matched element has scrolled."

    def __init__(self, sessions: BrowserSessionManager) -> None:
        self._sessions = sessions

    def required_parameters(self) -> list[str]:
        return ["session_id"]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not (parameters.get("session_id") or "").strip():
            errors.append("missing required parameter: session_id")

        selector = (parameters.get("selector") or "").strip()
        delta_x = parameters.get("delta_x", 0)
        delta_y = parameters.get("delta_y", 0)
        if not selector and not delta_x and not delta_y:
            errors.append("provide either 'selector' or a non-zero 'delta_x'/'delta_y'")
        if not isinstance(delta_x, (int, float)) or not isinstance(delta_y, (int, float)):
            errors.append("'delta_x'/'delta_y' must be numbers")

        return errors

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        try:
            session = self._sessions.get(parameters["session_id"].strip())
        except BrowserSessionError as exc:
            return ExecutionResult(success=False, errors=[str(exc)])

        selector = (parameters.get("selector") or "").strip()
        delta_x = parameters.get("delta_x", 0)
        delta_y = parameters.get("delta_y", 0)

        try:
            if selector:
                session.page.locator(selector).scroll_into_view_if_needed()
            else:
                session.page.mouse.wheel(delta_x, delta_y)
        except PlaywrightError as exc:
            return ExecutionResult(success=False, errors=[describe_playwright_failure(exc, "scroll")])
        except Exception as exc:  # noqa: BLE001
            return ExecutionResult(success=False, errors=[f"unexpected error during scroll: {exc}"])

        return ExecutionResult(
            success=True,
            output={"selector": selector or None, "delta_x": delta_x, "delta_y": delta_y},
        )
