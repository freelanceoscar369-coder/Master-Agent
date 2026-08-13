"""C26 · Browser Executive — `open_url()`, `new_tab()`, `close_tab()`,
`switch_tab()`, `focus_browser()`, using the existing Browser Worker.

**Every navigation and every session is the existing `BrowserSessionManager`
(`environment/browser_session.py`, Mission Brief 022) and its existing
`Action`s** — `OpenBrowserSessionAction`, `NavigateAction`,
`CloseBrowserSessionAction`. This file adds no second way to drive
Playwright; it adds the vocabulary the brief asks for on top of the one
that already exists. A Browser Worker "session" is one `BrowserContext` +
one `Page` — which is exactly what the brief calls a *"tab"* — so
`new_tab()` opens a session, `close_tab()` closes one, and `switch_tab()`
changes which session subsequent calls act on **without touching
Playwright at all**: it is bookkeeping local to this class.

**`focus_browser()` is the one place this file reaches outside the
browser itself.** Playwright has no concept of an OS window in front of
other windows — that is `window.py`'s job. `focus_browser()` finds the
browser's own process (reusing `desktop.inventory`'s existing process
attribution — never a second inventory) and asks the Window Manager to
bring its window to the front.

## Do NOT inspect — enforced by absence, not by a runtime check

The brief: *"Do NOT inspect: conversations, cookies, passwords,
history."* This file calls exactly four things on a session or its
manager: `open_session`, `navigate` (via `NavigateAction`),
`close_session`, `get`/`list_sessions`. It never calls `.cookies()`,
`.storage_state()`, `page.content()`, or reads a page's own text —
`tests/test_desktop_execution.py`'s guard checks this by AST across the
whole package.

## Optional dependency, handled the way `browser = ["playwright>=1.55"]`
already declares it

`environment.browser_session` imports Playwright at module scope. Nothing
in this file imports it at module scope — every reference is inside a
method, so a machine without Playwright installed can still import
`desktop.execution.browser`; only *using* it raises `BrowserUnavailable`,
naming the real reason.
"""
from __future__ import annotations

from master_agent.desktop.actions import DesktopContext
from master_agent.desktop.execution.window import WindowManager
from master_agent.executor.action import Action, ExecutionResult


class BrowserUnavailable(RuntimeError):
    """The Browser Worker's own dependency (Playwright) is not available
    here. Structural, like `BackendUnavailable` — never raised for an
    ordinary navigation failure."""


def _run_browser_action(action_cls: type[Action], sessions: object, **parameters: object) -> ExecutionResult:
    action = action_cls(sessions)
    errors = action.validate(parameters)
    if errors:
        return ExecutionResult(success=False, errors=errors)
    return action.run(parameters)


class BrowserExecutive:
    __slots__ = ("_context", "_counter", "_current", "_headless", "_manager", "_windows")

    def __init__(
        self,
        window_manager: WindowManager | None = None,
        desktop_context: DesktopContext | None = None,
        headless: bool = True,
    ) -> None:
        self._manager = None
        self._current: str | None = None
        self._counter = 0
        self._headless = headless
        self._windows = window_manager or WindowManager()
        self._context = desktop_context

    def _ensure_manager(self):
        if self._manager is None:
            try:
                from master_agent.environment.browser_session import (
                    BrowserSessionManager,
                )
            except ImportError as exc:
                raise BrowserUnavailable(
                    "the Browser Worker's dependency (Playwright) is not "
                    "installed; the 'browser' extra is required"
                ) from exc
            self._manager = BrowserSessionManager()
        return self._manager

    def open_url(self, url: str, session_id: str | None = None) -> ExecutionResult:
        """Navigate the given (or the current) tab, opening a new one if
        neither exists yet."""
        try:
            manager = self._ensure_manager()
        except BrowserUnavailable as exc:
            return ExecutionResult(success=False, errors=[str(exc)])

        target = session_id or self._current
        known = {h.session_id for h in manager.list_sessions()}
        if target is None or target not in known:
            return self.new_tab(url, session_id=session_id)

        from master_agent.executor.actions.browser.navigate import NavigateAction

        result = _run_browser_action(NavigateAction, manager, session_id=target, url=url)
        if result.success:
            self._current = target
        return result

    def new_tab(self, url: str | None = None, session_id: str | None = None) -> ExecutionResult:
        try:
            manager = self._ensure_manager()
        except BrowserUnavailable as exc:
            return ExecutionResult(success=False, errors=[str(exc)])

        from master_agent.executor.actions.browser.open_session import (
            OpenBrowserSessionAction,
        )

        self._counter += 1
        sid = session_id or f"tab-{self._counter}"
        opened = _run_browser_action(
            OpenBrowserSessionAction, manager, session_id=sid, headless=self._headless
        )
        if not opened.success:
            return opened
        self._current = sid

        if url is None:
            return opened

        from master_agent.executor.actions.browser.navigate import NavigateAction

        navigated = _run_browser_action(NavigateAction, manager, session_id=sid, url=url)
        if not navigated.success:
            return navigated
        return ExecutionResult(success=True, output={"session_id": sid, "url": url})

    def close_tab(self, session_id: str | None = None) -> ExecutionResult:
        try:
            manager = self._ensure_manager()
        except BrowserUnavailable as exc:
            return ExecutionResult(success=False, errors=[str(exc)])

        sid = session_id or self._current
        if sid is None:
            return ExecutionResult(success=False, errors=["no tab is open or specified"])

        from master_agent.executor.actions.browser.close_session import (
            CloseBrowserSessionAction,
        )

        result = _run_browser_action(CloseBrowserSessionAction, manager, session_id=sid)
        if result.success and sid == self._current:
            self._current = None
        return result

    def switch_tab(self, session_id: str) -> ExecutionResult:
        """Bookkeeping only — no Playwright call. `session_id` must
        already be open."""
        try:
            manager = self._ensure_manager()
        except BrowserUnavailable as exc:
            return ExecutionResult(success=False, errors=[str(exc)])

        from master_agent.environment.browser_session import BrowserSessionError

        try:
            manager.get(session_id)
        except BrowserSessionError as exc:
            return ExecutionResult(success=False, errors=[str(exc)])
        self._current = session_id
        return ExecutionResult(success=True, output={"session_id": session_id})

    def focus_browser(self, application: str) -> ExecutionResult:
        """Bring the named browser's OS window to the front. Reuses
        `desktop.inventory`'s existing process attribution — the same
        facts `desktop.actions.IsRunningAction` reads — to find the
        window precisely, never by guessing at a title."""
        if self._context is None:
            return ExecutionResult(
                success=False,
                errors=[
                    (
                        "no DesktopContext was supplied; focus_browser needs "
                        "one to find the browser's own process"
                    )
                ],
            )
        inventory = self._context.refresh(read_versions=False, deep=False)
        running = inventory.running(application)
        if not running:
            return ExecutionResult(success=False, errors=[f"{application} is not running"])

        pids = frozenset(p.pid for p in running)
        return self._windows.focus_process(pids)

    @property
    def current_tab(self) -> str | None:
        return self._current
