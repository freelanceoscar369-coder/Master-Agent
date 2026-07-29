"""ObserveBrowserAction — the Observation layer's entry point as a
capability a Brain/caller can request directly. Calls the exact same
normalize_observation() function BrowserVerifier uses internally (see
plugins/browser_observation.py) — one shared implementation, two callers,
per ENGINEERING_PRINCIPLES.md #7.
"""
from __future__ import annotations

from typing import Any

from master_agent.environment.browser_session import BrowserSessionError, BrowserSessionManager
from master_agent.executor.action import Action, ExecutionResult
from master_agent.plugins.base import PermissionCategory, RiskTier
from master_agent.plugins.browser_observation import normalize_observation

OBSERVE_BROWSER = "observe_browser"


class ObserveBrowserAction(Action):
    name = OBSERVE_BROWSER
    description = "Capture a generic observation of an open browser session's current state."
    risk_tier = RiskTier.READ_ONLY
    permission_category = PermissionCategory.READ
    expected_result = "A BrowserObservation describing the current page is returned."

    def __init__(self, sessions: BrowserSessionManager) -> None:
        self._sessions = sessions

    def required_parameters(self) -> list[str]:
        return ["session_id"]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not (parameters.get("session_id") or "").strip():
            errors.append("missing required parameter: session_id")

        selectors = parameters.get("selectors", [])
        if not isinstance(selectors, list) or not all(isinstance(s, str) for s in selectors):
            errors.append("'selectors' must be a list of strings if provided")

        for flag in ("include_accessibility_tree", "include_available_actions"):
            if not isinstance(parameters.get(flag, False), bool):
                errors.append(f"'{flag}' must be a boolean if provided")

        return errors

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        try:
            session = self._sessions.get(parameters["session_id"].strip())
        except BrowserSessionError as exc:
            return ExecutionResult(success=False, errors=[str(exc)])

        try:
            observation = normalize_observation(
                session.page,
                parameters.get("selectors", []),
                include_accessibility_tree=parameters.get("include_accessibility_tree", False),
                include_available_actions=parameters.get("include_available_actions", False),
            )
        except Exception as exc:  # noqa: BLE001 — mechanical failure, e.g. session closed mid-call
            return ExecutionResult(success=False, errors=[f"observation failed: {exc}"])

        return ExecutionResult(success=True, output=observation.as_dict())
