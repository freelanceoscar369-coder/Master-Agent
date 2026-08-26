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
from typing import Any

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
    #: Which installed browser this session is driving, when it is not the
    #: bundled build — `"chrome"` for the founder's real Google Chrome.
    #: Reported so a caller (and an audit record) can tell a founder-
    #: visible session from a bundled headless one after the fact.
    channel: str | None = None
    #: Which named browser identity this session was opened as, or `None`
    #: for an anonymous session. Reported for the same reason `channel` is:
    #: a caller and an audit record can tell a session that carries the
    #: founder's signed-in state from one that starts empty and forgets
    #: everything. The *id* only — never a path, and never anything from
    #: inside the profile.
    identity_id: str | None = None


def _launch(
    playwright: Playwright, headless: bool, channel: str | None = None
) -> Browser:
    """The one place in the whole Browser Worker that names a specific
    Playwright engine. Everything above this function — BrowserSession,
    every Action, BrowserVerifier, BrowserWorker — only ever sees "a
    browser," never which one. Swapping this for a different engine, or a
    different browser-automation library entirely, is a one-function
    change; see BROWSER_WORKER_ARCHITECTURE.md §5.

    `channel` is Playwright's own first-class parameter for *"use a
    browser already installed on this machine rather than the bundled
    build"* — `"chrome"` resolves to the founder's real Google Chrome
    installation. It stays confined to this one function for exactly the
    reason above, and it is why satisfying "open Chrome" needs no second
    browser subsystem: the same session Playwright drives, observes and
    verifies *is* the founder's visible Chrome. `None` keeps Playwright's
    bundled Chromium — the unchanged default for every existing caller.
    """
    if channel:
        return playwright.chromium.launch(headless=headless, channel=channel)
    return playwright.chromium.launch(headless=headless)


def _launch_persistent(
    playwright: Playwright,
    user_data_dir: str,
    headless: bool,
    channel: str | None = None,
) -> BrowserContext:
    """The identity-backed twin of `_launch`, and the second and last
    place that names a Playwright engine.

    Playwright draws the line here, not us: an ordinary `launch()` gives a
    Browser whose every `new_context()` starts empty, while
    `launch_persistent_context()` gives *one* context backed by a real
    Chrome user-data directory that survives the process. There is no
    variant that is both, which is why an identity session is a different
    call rather than a flag — a persistent context IS the browser, so it
    has no `new_context()` to hand out.

    `storage_state` was the smaller mechanism and was considered first. It
    round-trips cookies and localStorage, and for a Google session that is
    not the whole of what a signed-in browser is: Google binds a session to
    profile state that `storage_state` does not represent at all, so a
    restored context can hold every cookie and still be asked to sign in.
    The dedicated user-data directory keeps whatever Chrome itself decided
    a signed-in profile needs, which is the only definition that stays
    true when Google changes its mind.

    The directory is Kalpavriksha's own (see
    `environment/browser_identity.py`) and never the founder's everyday
    Chrome profile.
    """
    if channel:
        return playwright.chromium.launch_persistent_context(
            user_data_dir, headless=headless, channel=channel
        )
    return playwright.chromium.launch_persistent_context(
        user_data_dir, headless=headless
    )


class BrowserSession:
    """One BrowserContext + Page, taken from a BrowserSessionManager's
    shared Browser. Never exposed outside plugins/browser_*.py and this
    module — Actions receive a session_id and resolve it through
    BrowserSessionManager, never a live Playwright object handed to them
    directly."""

    def __init__(self, context: BrowserContext, owns_browser: bool = False) -> None:
        self._context: BrowserContext | None = context
        # A persistent context opens with a page already on it; taking that
        # one rather than adding a second is what keeps an identity session
        # a single visible window instead of a stray blank tab beside it.
        existing = list(context.pages)
        self._page: Page | None = existing[0] if existing else context.new_page()
        #: True for an identity-backed session, whose context *is* its
        #: browser process — closing the context ends it, so the manager
        #: must not also look for a shared Browser to close.
        self.owns_browser = owns_browser

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

    def __init__(
        self,
        default_headless: bool = True,
        default_channel: str | None = None,
        identities: Any = None,
    ) -> None:
        self._sessions: dict[str, BrowserSession] = {}
        self._handles: dict[str, BrowserSessionHandle] = {}
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._browser_headless: bool | None = None
        self._browser_channel: str | None = None
        # What a caller gets when it does not say. Defaults preserve the
        # pre-existing behaviour exactly (bundled Chromium, headless), so
        # every existing caller and test is unaffected; the one place that
        # overrides them is the Founder Edition composition root, where a
        # founder is literally sitting in front of the machine and "open
        # Chrome" has to mean the Chrome they can see.
        self._default_headless = default_headless
        self._default_channel = default_channel
        #: The `BrowserIdentityStore` this manager resolves identity ids
        #: through, or None for a deployment that declared no identities.
        #: Injected rather than constructed: *where* identity state lives
        #: is the deployment's decision (its application directory), and a
        #: session manager that picked a directory itself would be making
        #: a configuration choice on the founder's disk.
        self._identities = identities

    def _ensure_playwright(self) -> Playwright:
        """One driver process per manager, shared by anonymous and
        identity-backed sessions alike — the module docstring's rule,
        unchanged. Only the *browser* differs between the two."""
        if self._playwright is None:
            self._playwright = sync_playwright().start()
        return self._playwright

    def _ensure_browser(self, headless: bool, channel: str | None = None) -> Browser:
        if self._browser is not None:
            if self._browser_headless != headless or self._browser_channel != channel:
                raise BrowserSessionError(
                    "a browser is already running with a different 'headless'/'channel' "
                    "setting; close all sessions before changing it"
                )
            return self._browser
        playwright = self._ensure_playwright()
        try:
            self._browser = _launch(playwright, headless, channel)
        except Exception:
            # Don't leave a half-started Playwright driver behind if launch fails.
            self._stop_playwright()
            raise
        self._browser_headless = headless
        self._browser_channel = channel
        return self._browser

    def _open_identity_context(
        self, identity_id: str, headless: bool, channel: str | None
    ) -> BrowserContext:
        """A context backed by this identity's own persistent profile.

        Separate from `_ensure_browser`'s shared Browser on purpose: an
        identity's profile directory can be open in exactly one Chrome
        process, so identity sessions neither share nor conflict with the
        anonymous browser. That also means the `headless`/`channel`
        agreement `_ensure_browser` enforces does not apply here — two
        identities may legitimately differ.
        """
        if self._identities is None:
            raise BrowserSessionError(
                f"no browser identities are configured, so identity "
                f"'{identity_id}' cannot be resolved"
            )
        try:
            user_data_dir = self._identities.path_for(identity_id)
        except Exception as exc:
            # A refused id is a structured failure, never a traceback:
            # the Action boundary above turns this into an
            # ExecutionResult the founder can read.
            raise BrowserSessionError(str(exc)) from exc

        playwright = self._ensure_playwright()
        try:
            return _launch_persistent(
                playwright, str(user_data_dir), headless, channel
            )
        except Exception:
            if not self._sessions and self._browser is None:
                self._stop_playwright()
            raise

    def open_session(
        self,
        session_id: str,
        headless: bool | None = None,
        channel: str | None = None,
        identity_id: str | None = None,
    ) -> BrowserSessionHandle:
        """Open one Environment Session, anonymously or as a named identity.

        `identity_id` omitted is the whole of the previous behaviour and is
        unchanged down to the call: a context off the shared Browser, empty
        cookies and storage, forgotten on close. That is still the right
        default — a scripted mission should not inherit whoever was signed
        in last, and an Action that never says otherwise cannot silently
        acquire the founder's authenticated identity.

        `identity_id` given opens a context backed by that identity's own
        persistent profile, so a Gemini tab signed in yesterday is still
        signed in today. The id is resolved through the configured
        `BrowserIdentityStore` and never used as a path.
        """
        if session_id in self._sessions:
            raise BrowserSessionError(f"session already open: '{session_id}'")

        # `None` means "the caller did not say" — distinct from an explicit
        # False, which is a caller deliberately asking to be shown.
        resolved_headless = (
            self._default_headless if headless is None else headless
        )
        resolved_channel = self._default_channel if channel is None else channel

        if identity_id is None:
            browser = self._ensure_browser(resolved_headless, resolved_channel)
            context = browser.new_context()
            session = BrowserSession(context)
        else:
            context = self._open_identity_context(
                identity_id, resolved_headless, resolved_channel
            )
            session = BrowserSession(context, owns_browser=True)

        self._sessions[session_id] = session
        handle = BrowserSessionHandle(
            session_id=session_id,
            opened_at=datetime.now(UTC),
            headless=resolved_headless,
            channel=resolved_channel,
            identity_id=identity_id,
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
        """Stop the shared Browser, then the driver.

        An identity session has no shared Browser to close — closing its
        context already ended its own Chrome process — but it does share
        the driver, so this still runs and the `self._browser and ...`
        guards make the first step a no-op. Getting that wrong leaks a
        Playwright driver per identity session, which the founder sees as
        `node.exe` processes that never go away.
        """
        warnings: list[str] = []
        try:
            if self._browser is not None:
                self._browser.close()
        except Exception as exc:  # noqa: BLE001 — deliberate: teardown must not raise
            warnings.append(f"browser teardown warning: {exc}")
        self._browser = None
        self._browser_headless = None
        self._browser_channel = None
        warnings.extend(self._stop_playwright())
        return warnings

    def _stop_playwright(self) -> list[str]:
        warnings: list[str] = []
        try:
            if self._playwright is not None:
                self._playwright.stop()
        except Exception as exc:  # noqa: BLE001 — deliberate: teardown must not raise
            warnings.append(f"playwright teardown warning: {exc}")
        self._playwright = None
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
