"""Observing whether a browser session exists — including when it should not.

## Why the page verifier cannot do this

`BrowserVerifier` observes a *page*: it calls `sessions.get(session_id)`
and reads the live `Page` behind it. That is right for Navigate and
Observe, and structurally wrong for Close, because `get()` raises
`BrowserSessionError` for a session that is gone. The generic `Verifier`
turns a failed observation into `Verdict.ERROR` -- so a session that was
closed exactly as asked would be reported as *"the observation itself
could not be captured"*, which is the opposite of the truth.

For Close, **absence is the expected environmental fact**, so something
has to be able to observe absence without treating it as a failure. This
verifier observes the session registry rather than a page, and answers
one question: is this session id currently open?

It is deliberately not folded into `BrowserVerifier`. That class promises
a page observation; a session-presence observation is a different fact
about a different subject, and a verifier that silently returned one when
it could not get the other would make `ERROR` unreadable.

## What it never does

It never consults the Action's own report. `CloseBrowserSession` returning
`{"closed": true}` is the Worker's claim about its own work, and ADR-0011
exists precisely so a claim like that is not what completion rests on.
"""
from __future__ import annotations

from typing import Any

from master_agent.environment.browser_session import BrowserSessionManager
from master_agent.verification.verifier import Verifier


class BrowserSessionVerifier(Verifier):
    """Observes whether a named session is open, fresh, from the manager."""

    worker_name = "browser"
    environment_name = "browser_environment"

    def __init__(self, sessions: BrowserSessionManager, session_id: str) -> None:
        self._sessions = sessions
        self._session_id = session_id

    def capture_observation_dict(self) -> dict[str, Any]:
        # Read the registry fresh at the moment verify() is called, never a
        # remembered value from whenever the Action ran -- the same
        # independence `BrowserVerifier` keeps for pages.
        #
        # `list_sessions()` rather than `get()`: `get()` raises for an
        # absent session, and absence is a legitimate answer here, not a
        # failure to observe.
        try:
            open_ids = {
                getattr(handle, "session_id", None)
                for handle in self._sessions.list_sessions()
            }
        except Exception:  # noqa: BLE001 -- a registry that cannot be read is
            # a genuine observation failure, and the base class turns the
            # raised error into Verdict.ERROR, which is correct here.
            raise

        return {
            "session_id": self._session_id,
            "session_exists": self._session_id in open_ids,
            "open_session_count": len(open_ids),
        }
