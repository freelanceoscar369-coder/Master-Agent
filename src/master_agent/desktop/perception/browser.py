"""C27 · Browser Observer — read-only, over the existing Browser Worker.

Determines whether a browser is active, its current URL, whether the page
has finished loading, whether navigation is complete, and how many tabs
are open. **Every fact but one comes from `ObserveBrowserAction`
(`executor/actions/browser/observe.py`, Mission Brief 022) and
`BrowserSessionManager.list_sessions()` — this file adds no second
Playwright driver and duplicates no navigation logic.**

## The one new read, and why it is safe

Neither `ObserveBrowserAction` nor `BrowserSessionManager` currently
exposes whether a page has *finished loading* — `normalize_observation()`
reads `url`/`title`, never `document.readyState`. This module adds
exactly one new call: `page.evaluate("document.readyState")`, a
standard, read-only DOM query already sandboxed by Playwright's own
`Page.evaluate` (it cannot navigate, click, or mutate anything — it
returns a JavaScript expression's value). `page_loaded` and
`navigation_complete` are both derived from it, and both say so plainly:
this layer performs one static read and cannot distinguish *"nothing is
happening"* from *"a new navigation is about to begin"* without the
event-listening this project's Browser Worker deliberately does not add
(`BROWSER_WORKER_ARCHITECTURE.md` §8: mechanical failures only).

## Do NOT inspect — enforced by absence

The brief: *"Never inspect history, cookies, credentials, conversations,
private content."* This file calls exactly three things on a session or
its manager: `list_sessions()`, `ObserveBrowserAction` (url/title only,
no selectors requested), and one `page.evaluate("document.readyState")`
— a fixed, hardcoded expression, never a caller-supplied string.
`tests/test_desktop_perception.py`'s guard checks this by AST.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from master_agent.desktop.perception.evidence import (
    Confidence,
    Observation,
    unknown_observation,
)

SOURCE_SESSIONS = "BrowserSessionManager.list_sessions()"
SOURCE_OBSERVE = "ObserveBrowserAction"
SOURCE_READY_STATE = "Page.evaluate('document.readyState')"

_READY_STATE_EXPRESSION = "document.readyState"


class BrowserUnavailable(RuntimeError):
    """The Browser Worker's dependency (Playwright) is not available, or
    no `BrowserSessionManager` was supplied. Structural, never raised for
    an ordinary observation failure."""


@dataclass(frozen=True)
class BrowserPerception:
    """One browser snapshot. Named distinctly from `plugins
    .browser_observation.BrowserObservation` (C22/MB022's own type, which
    this does not replace) to keep the two apart in a reader's mind."""

    browser_active: Observation
    """`.value` is `bool`."""

    current_url: Observation
    """`.value` is `str | None`."""

    page_loaded: Observation
    """`.value` is `bool | None`."""

    navigation_complete: Observation
    """`.value` is `bool | None` — see the module docstring for why this
    and `page_loaded` share one underlying signal."""

    tab_count: Observation
    """`.value` is `int`."""

    timestamp: datetime

    def as_dict(self) -> dict[str, Any]:
        return {
            "browser_active": self.browser_active.as_dict(),
            "current_url": self.current_url.as_dict(),
            "page_loaded": self.page_loaded.as_dict(),
            "navigation_complete": self.navigation_complete.as_dict(),
            "tab_count": self.tab_count.as_dict(),
            "timestamp": self.timestamp.isoformat(),
        }


class BrowserObserver:
    """Read-only. Takes the existing `BrowserSessionManager` directly —
    the Browser Worker itself — never a second driver."""

    __slots__ = ("_sessions",)

    def __init__(self, sessions: object | None = None) -> None:
        self._sessions = sessions

    def observe(self, timestamp: datetime, session_id: str | None = None) -> BrowserPerception:
        if self._sessions is None:
            unavailable = unknown_observation(
                reason="no BrowserSessionManager was supplied",
                source=SOURCE_SESSIONS, timestamp=timestamp,
            )
            return BrowserPerception(
                browser_active=Observation(
                    value=False, confidence=Confidence.OBSERVED,
                    reason="no BrowserSessionManager was supplied",
                    source=SOURCE_SESSIONS, timestamp=timestamp,
                ),
                current_url=unavailable, page_loaded=unavailable,
                navigation_complete=unavailable, tab_count=Observation(
                    value=0, confidence=Confidence.OBSERVED,
                    reason="no BrowserSessionManager was supplied",
                    source=SOURCE_SESSIONS, timestamp=timestamp,
                ),
                timestamp=timestamp,
            )

        handles = self._sessions.list_sessions()
        tab_count_obs = Observation(
            value=len(handles), confidence=Confidence.OBSERVED,
            reason=f"{len(handles)} browser session(s) are open",
            source=SOURCE_SESSIONS, timestamp=timestamp,
        )
        active_obs = Observation(
            value=bool(handles), confidence=Confidence.OBSERVED,
            reason=(
                f"{len(handles)} browser session(s) are open" if handles
                else "no browser session is open"
            ),
            source=SOURCE_SESSIONS, timestamp=timestamp,
        )

        target = session_id or (handles[0].session_id if handles else None)
        if target is None:
            empty = unknown_observation(
                reason="no browser session is open", source=SOURCE_OBSERVE, timestamp=timestamp,
            )
            return BrowserPerception(
                browser_active=active_obs, current_url=empty, page_loaded=empty,
                navigation_complete=empty, tab_count=tab_count_obs, timestamp=timestamp,
            )

        from master_agent.executor.actions.browser.observe import ObserveBrowserAction

        action = ObserveBrowserAction(self._sessions)
        errors = action.validate({"session_id": target})
        result = action.run({"session_id": target}) if not errors else None

        if errors or result is None or not result.success:
            reason = "; ".join(errors or (result.errors if result else ["observation failed"]))
            failed = unknown_observation(reason=reason, source=SOURCE_OBSERVE, timestamp=timestamp)
            return BrowserPerception(
                browser_active=active_obs, current_url=failed, page_loaded=failed,
                navigation_complete=failed, tab_count=tab_count_obs, timestamp=timestamp,
            )

        url = result.output["url"]
        url_obs = Observation(
            value=url, confidence=Confidence.OBSERVED,
            reason=f"session {target!r} is at {url!r}",
            source=SOURCE_OBSERVE, timestamp=timestamp,
        )

        ready_state = _read_ready_state(self._sessions, target)
        if ready_state is None:
            loaded = unknown_observation(
                reason=f"document.readyState could not be read for session {target!r}",
                source=SOURCE_READY_STATE, timestamp=timestamp,
            )
            nav_complete = loaded
        else:
            is_complete = ready_state == "complete"
            loaded = Observation(
                value=is_complete, confidence=Confidence.OBSERVED,
                reason=f"document.readyState is {ready_state!r}",
                source=SOURCE_READY_STATE, timestamp=timestamp,
            )
            nav_complete = Observation(
                value=is_complete, confidence=Confidence.OBSERVED,
                reason=(
                    f"document.readyState is {ready_state!r}; this layer "
                    "cannot distinguish 'idle' from 'about to navigate' "
                    "without event-listening it does not perform"
                ),
                source=SOURCE_READY_STATE, timestamp=timestamp,
            )

        return BrowserPerception(
            browser_active=active_obs, current_url=url_obs, page_loaded=loaded,
            navigation_complete=nav_complete, tab_count=tab_count_obs, timestamp=timestamp,
        )


def _read_ready_state(sessions: object, session_id: str) -> str | None:
    from master_agent.environment.browser_session import BrowserSessionError

    try:
        session = sessions.get(session_id)
        return session.page.evaluate(_READY_STATE_EXPRESSION)
    except BrowserSessionError:
        return None
    except Exception:  # noqa: BLE001 — mechanical failure, e.g. session closed mid-call
        return None
