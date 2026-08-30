"""NavigateAction — wraps Playwright's page.goto(). Kalpavriksha owns
nothing about navigation semantics; Playwright owns navigation entirely.
See BROWSER_WORKER_ARCHITECTURE.md §6.
"""
from __future__ import annotations

from typing import Any

from master_agent.environment.browser_session import BrowserSessionError, BrowserSessionManager
from master_agent.executor.action import Action, ExecutionResult
from master_agent.executor.actions.browser._common import (
    DEFAULT_NAVIGATION_TIMEOUT_MS,
    PlaywrightError,
    describe_playwright_failure,
)
from master_agent.plugins.base import PermissionCategory, RiskTier

NAVIGATE = "navigate"


class NavigateAction(Action):
    name = NAVIGATE
    # The Planner reads this line to decide how to fill the arguments, so
    # what this lane can actually REACH has to be stated here or it is not
    # stated at all.
    #
    # Observed, repeatedly, on the founder's own research objective: a
    # plan whose first two sources were general-web-search query URLs
    # landed on that engine's automation-refusal page instead of on
    # results, and Verification correctly reported `not_matched`. Nothing
    # malfunctioned. The mission failed because it was sent somewhere
    # this lane cannot go.
    #
    # Named as a CLASS of destination and never as a product, which is
    # the Browser Worker's standing rule and is enforced by
    # `test_browser_constitution_compliance.py` -- a guard that caught an
    # earlier draft of this very comment.
    #
    # This is a fact about the environment, not a hardcoded answer and
    # not a result. It names no site as good and no site as bad; it says
    # which kind of page an automated browser is served, which is
    # something only observation could establish and which the Planner
    # otherwise has no way to know.
    description = (
        "Navigate an open browser session to a URL. This is an ordinary "
        "automated browser, not a signed-in one: general web search "
        "engines serve it an anti-bot interstitial instead of results, so "
        "a search-engine URL will not return search results. Go directly "
        "to a site that publishes what is needed."
    )
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
        timeout_ms = parameters.get("timeout_ms", DEFAULT_NAVIGATION_TIMEOUT_MS)
        if not isinstance(timeout_ms, (int, float)) or timeout_ms <= 0:
            errors.append("'timeout_ms' must be a positive number if provided")
        return errors

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        try:
            session = self._sessions.get(parameters["session_id"].strip())
        except BrowserSessionError as exc:
            return ExecutionResult(success=False, errors=[str(exc)])

        url = parameters["url"].strip()
        timeout_ms = parameters.get("timeout_ms", DEFAULT_NAVIGATION_TIMEOUT_MS)

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
