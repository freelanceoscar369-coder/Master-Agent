"""OpenBrowserSessionAction — starts one Environment Session (a live
Playwright browser+context+page) that later Actions in the same Mission
act against by session_id. See BROWSER_WORKER_ARCHITECTURE.md §4, §6.

REVERSIBLE_WRITE / SYSTEM: launching a local browser process is the first
real use of PermissionCategory.SYSTEM (reserved, unused, since ADR-0009).
Reversible because closing the session undoes it completely — nothing
about opening a browser is destructive.
"""
from __future__ import annotations

from typing import Any

from master_agent.environment.browser_identity import IDENTITY_ID_PATTERN
from master_agent.environment.browser_session import BrowserSessionError, BrowserSessionManager
from master_agent.executor.action import Action, ExecutionResult
from master_agent.plugins.base import PermissionCategory, RiskTier

OPEN_BROWSER_SESSION = "open_browser_session"


class OpenBrowserSessionAction(Action):
    name = OPEN_BROWSER_SESSION
    description = "Open a new browser Environment Session."
    risk_tier = RiskTier.REVERSIBLE_WRITE
    permission_category = PermissionCategory.SYSTEM
    expected_result = "A new browser session is open and ready for subsequent actions."

    def __init__(self, sessions: BrowserSessionManager) -> None:
        self._sessions = sessions

    def required_parameters(self) -> list[str]:
        return ["session_id"]

    def optional_parameters(self) -> list[dict[str, Any]] | None:
        return [
            {
                "name": "headless",
                "type": "boolean",
                "description": (
                    "Whether the browser window is invisible (true) or "
                    "visible so the founder can watch this session "
                    "(false). Set false whenever the objective names a "
                    "browser the founder can see, asks to be shown "
                    "something, or says to open a browser application."
                ),
                "default": True,
            },
            {
                "name": "channel",
                "type": "string",
                "description": (
                    "Which installed browser to drive: 'chrome' uses the "
                    "founder's real Google Chrome application; omit it to "
                    "use the built-in browser. Set 'chrome' whenever the "
                    "objective names Chrome specifically."
                ),
                "default": None,
            },
            {
                "name": "identity_id",
                "type": "string",
                "description": (
                    "Open this session as a named, signed-in browser "
                    "identity (for example 'founder') so websites the "
                    "founder has already signed into stay signed in. Omit "
                    "it for an ordinary anonymous session that starts with "
                    "no cookies and forgets everything on close — which is "
                    "what almost every objective wants. Only name an "
                    "identity when the objective needs a site the founder "
                    "is signed into."
                ),
                "default": None,
            },
        ]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        session_id = (parameters.get("session_id") or "").strip()
        if not session_id:
            errors.append("missing required parameter: session_id")

        headless = parameters.get("headless")
        if headless is not None and not isinstance(headless, bool):
            errors.append("'headless' must be a boolean if provided")

        channel = parameters.get("channel")
        if channel is not None and not isinstance(channel, str):
            errors.append("'channel' must be a string if provided")

        identity_id = parameters.get("identity_id")
        if identity_id is not None:
            if not isinstance(identity_id, str):
                errors.append("'identity_id' must be a string if provided")
            elif identity_id and not IDENTITY_ID_PATTERN.match(identity_id):
                # Refused here as well as in the identity store, and for a
                # different reason: this parameter can be written by the
                # Planner, so `../../../Google/Chrome/User Data` is a
                # spelling a *plan* could contain. Catching it at validate()
                # keeps it from ever reaching a filesystem call, and makes
                # the refusal a plan-level error the founder can read rather
                # than a launch failure.
                errors.append(
                    "'identity_id' must be lowercase letters, digits, '_' or "
                    "'-' (no path separators, drive letters or dots)"
                )

        return errors

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        session_id = parameters["session_id"].strip()
        # `None` (absent) is passed through rather than defaulted here:
        # the session manager owns what "unspecified" means, so a
        # composition root can configure founder-visible defaults without
        # this Action having to know a founder exists.
        headless = parameters.get("headless")
        channel = parameters.get("channel") or None
        identity_id = parameters.get("identity_id") or None

        try:
            handle = self._sessions.open_session(
                session_id,
                headless=headless,
                channel=channel,
                identity_id=identity_id,
            )
        except BrowserSessionError as exc:
            return ExecutionResult(success=False, errors=[str(exc)])
        except Exception as exc:  # noqa: BLE001 — mechanical failure, e.g. browser failed to launch
            return ExecutionResult(success=False, errors=[f"failed to open browser session: {exc}"])

        return ExecutionResult(
            success=True,
            output={
                "session_id": handle.session_id,
                "opened_at": handle.opened_at.isoformat(),
                "headless": handle.headless,
                "channel": handle.channel,
                "identity_id": handle.identity_id,
            },
        )
