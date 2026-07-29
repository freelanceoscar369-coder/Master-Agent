"""BrowserSession / BrowserSessionManager — the Browser Environment's
Environment Session Manager (KALPAVRIKSHA_VISION_V2.md §8.3). Owned by
whichever Operator Instance opens it; never Shared Infrastructure (§5.7).

This is the one new architectural mechanism this Mission Brief introduces:
the existing `Action` contract (executor/action.py) is one-shot and
stateless, but a browser session is neither — `navigate` then `click` then
`type_text` must all act on the *same* open page. See
BROWSER_WORKER_ARCHITECTURE.md §4 for why this lives here rather than as a
change to the Action contract itself.

One Playwright driver process per BrowserSessionManager (i.e. per Operator
Instance), started lazily on the first `open_session()` call and stopped
when the last session closes — not one driver per session. Playwright's
sync API supports exactly one active driver per thread; multiple browser
Environment Sessions are multiplexed onto it as separate BrowserContexts
(Playwright's own isolation boundary: separate cookies/storage per
context), which also maps cleanly onto "one Operator Instance manages many
Environment Instances" (KALPAVRIKSHA_VISION_V2.md §8.2).

Playwright is the only thing in this file that is browser-specific in a
way that would need to change for a different browser-automation library;
see §5 of the architecture doc for why the choice of which underlying
browser engine to launch is confined to the one private `_launch()`
function below and never exposed on BrowserSession's or
BrowserSessionManager's public surface.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright


class BrowserSessionError(Exception):
    """Raised for session-lifecycle problems (opening an already-open
    session id, acting on a missing/closed one). Actions catch this and
    turn it into a structured ExecutionResult — it must never propagate
    as a raw traceback past the Action boundary (executor/action.py's
    contract)."""


@dataclass
class BrowserSessionHandle:
    """The generic, Playwright-free view of a session — safe to return to
    a caller outside this module (an Action's ExecutionResult.output, or
    an audit record)."""

    session_id: str
    opened_at: datetime
    headless: bool


def _launch(playwright: Playwright, headless: bool) -> Browser:
    """The one place in the whole Browser Worker that names a specific
    Playwright engine. Everything above this function — BrowserSession,
    every Action, BrowserVerifier, BrowserWorker — only ever sees "a
    browser," never which one. Swapping this for a different engine, or a
    different browser-automation library entirely, is a one-function
    change; see BROWSER_WORKER_ARCHITECTURE.md §5."""
    return playwright.chromium.launch(headless=headless)


class BrowserSession:
    """One BrowserContext + Page, taken from a BrowserSessionManager's
    shared Browser. Never exposed outside plugins/browser_*.py and this
    module — Actions receive a session_id and resolve it through
    BrowserSessionManager, never a live Playwright object handed to them
    directly."""

    def __init__(self, context: BrowserContext) -> None:
        self._context: BrowserContext | None = context
        self._page: Page | None = context.new_page()

    @property
    def is_open(self) -> bool:
        return self._page is not None

    @property
    def page(self) -> Page:
        if self._page is None:
            raise BrowserSessionError("session is not open")
        return self._page

    def close(self) -> list[str]:
        """Returns a list of non-fatal teardown warnings rather than
        raising — closing a session must never fail loudly (see module
        docstring)."""
        warnings: list[str] = []
        for label, closer in (
            ("page", lambda: self._page and self._page.close()),
            ("context", lambda: self._context and self._context.close()),
        ):
            try:
                closer()
            except Exception as exc:  # noqa: BLE001 — deliberate: teardown must not raise
                warnings.append(f"{label} teardown warning: {exc}")
        self._page = None
        self._context = None
        return warnings


class BrowserSessionManager:
    """Tracks every live BrowserSession for one Operator Instance, keyed by
    session_id, over one shared Playwright driver and Browser process. This
    is the Constitution's Environment Session Manager
    (KALPAVRIKSHA_VISION_V2.md §8.3), specialized for the Browser
    Environment. See BROWSER_WORKER_ARCHITECTURE.md §4 for why this is not
    yet a generic EnvironmentSessionManager base class."""

    def __init__(self) -> None:
        self._sessions: dict[str, BrowserSession] = {}
        self._handles: dict[str, BrowserSessionHandle] = {}
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._browser_headless: bool | None = None

    def _ensure_browser(self, headless: bool) -> Browser:
        if self._browser is not None:
            if self._browser_headless != headless:
                raise BrowserSessionError(
                    "a browser is already running with a different 'headless' setting; "
                    "close all sessions before changing it"
                )
            return self._browser
        self._playwright = sync_playwright().start()
        try:
            self._browser = _launch(self._playwright, headless)
        except Exception:
            # Don't leave a half-started Playwright driver behind if launch fails.
            self._playwright.stop()
            self._playwright = None
            raise
        self._browser_headless = headless
        return self._browser

    def open_session(self, session_id: str, headless: bool = True) -> BrowserSessionHandle:
        if session_id in self._sessions:
            raise BrowserSessionError(f"session already open: '{session_id}'")

        browser = self._ensure_browser(headless)
        context = browser.new_context()
        session = BrowserSession(context)
        self._sessions[session_id] = session
        handle = BrowserSessionHandle(
            session_id=session_id,
            opened_at=datetime.now(UTC),
            headless=headless,
        )
        self._handles[session_id] = handle
        return handle

    def get(self, session_id: str) -> BrowserSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise BrowserSessionError(f"unknown or closed session: '{session_id}'")
        return session

    def close_session(self, session_id: str) -> list[str]:
        session = self.get(session_id)
        warnings = session.close()
        del self._sessions[session_id]
        del self._handles[session_id]
        if not self._sessions:
            warnings.extend(self._stop_browser())
        return warnings

    def _stop_browser(self) -> list[str]:
        warnings: list[str] = []
        for label, closer in (
            ("browser", lambda: self._browser and self._browser.close()),
            ("playwright", lambda: self._playwright and self._playwright.stop()),
        ):
            try:
                closer()
            except Exception as exc:  # noqa: BLE001 — deliberate: teardown must not raise
                warnings.append(f"{label} teardown warning: {exc}")
        self._browser = None
        self._playwright = None
        self._browser_headless = None
        return warnings

    def list_sessions(self) -> list[BrowserSessionHandle]:
        return list(self._handles.values())

    def close_all(self) -> dict[str, list[str]]:
        """Best-effort cleanup — used by test teardown and by a future
        Operator Instance shutdown path. Never raises; per-session
        warnings are returned keyed by session_id."""
        warnings: dict[str, list[str]] = {}
        for session_id in list(self._sessions):
            warnings[session_id] = self.close_session(session_id)
        return warnings
