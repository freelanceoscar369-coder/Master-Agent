"""Browser capability plugin — a thin Plugin-contract adapter over the
LocalExecutor, mirroring filesystem_plugin.py's shape exactly (Mission
Brief 002/005's pattern, reused unchanged for a second, unrelated
capability family). All real logic lives in executor/actions/browser/ —
this class exists only so the Orchestrator/PluginRegistry can resolve
browser capabilities the same way it resolves every other one (ADR-0003).

See BROWSER_WORKER_ARCHITECTURE.md §11 for why this adapter exists
side-by-side with BrowserWorker (plugins/browser_worker.py) rather than
instead of it: this is the execution-only integration surface proving
Orchestrator/PluginRegistry compatibility; BrowserWorker is the
Constitution-complete facade (execute + verify + audit) this Mission
Brief's demonstration uses.
"""
from __future__ import annotations

from typing import Any

from master_agent.environment.browser_session import BrowserSessionManager
from master_agent.executor.action import Action
from master_agent.executor.actions.browser.click import CLICK, ClickAction
from master_agent.executor.actions.browser.close_session import (
    CLOSE_BROWSER_SESSION,
    CloseBrowserSessionAction,
)
from master_agent.executor.actions.browser.navigate import NAVIGATE, NavigateAction
from master_agent.executor.actions.browser.observe import OBSERVE_BROWSER, ObserveBrowserAction
from master_agent.executor.actions.browser.open_session import (
    OPEN_BROWSER_SESSION,
    OpenBrowserSessionAction,
)
from master_agent.executor.actions.browser.press_key import PRESS_KEY, PressKeyAction
from master_agent.executor.actions.browser.scroll import SCROLL, ScrollAction
from master_agent.executor.actions.browser.type_text import TYPE_TEXT, TypeTextAction
from master_agent.executor.actions.browser.wait_for_selector import (
    WAIT_FOR_SELECTOR,
    WaitForSelectorAction,
)
from master_agent.executor.executor import LocalExecutor
from master_agent.permissions.permission_system import GrantScope
from master_agent.plugins.base import CapabilityManifest, InvocationResult, Plugin, PluginManifest

__all__ = [
    "CLICK",
    "CLOSE_BROWSER_SESSION",
    "NAVIGATE",
    "OBSERVE_BROWSER",
    "OPEN_BROWSER_SESSION",
    "PRESS_KEY",
    "SCROLL",
    "TYPE_TEXT",
    "WAIT_FOR_SELECTOR",
    "BrowserPlugin",
]

# Every Action this plugin owns, in one place. Each shares the
# `__init__(self, sessions: BrowserSessionManager)` constructor shape,
# the same uniform-constructor trick FilesystemPlugin's
# _PRIMITIVE_ACTION_CLASSES loop relies on (FILESYSTEM_CAPABILITIES.md §5)
# -- adding Action #10 costs one new class here, never an edit to this
# file's logic.
_ACTION_CLASSES: tuple[type[Action], ...] = (
    OpenBrowserSessionAction,
    CloseBrowserSessionAction,
    NavigateAction,
    ClickAction,
    TypeTextAction,
    PressKeyAction,
    ScrollAction,
    WaitForSelectorAction,
    ObserveBrowserAction,
)


class BrowserPlugin(Plugin):
    """`sessions` is injected (dependency injection, consistent with the
    rest of the codebase) so multiple browser-backed plugins/Workers could
    share one BrowserSessionManager's live sessions, the same reasoning
    FilesystemPlugin already applies to its injected `executor`."""

    def __init__(self, executor: LocalExecutor, sessions: BrowserSessionManager) -> None:
        self._executor = executor
        self._sessions = sessions
        self._actions: dict[str, Action] = {}

        for action_cls in _ACTION_CLASSES:
            self._register(action_cls(sessions))

    def _register(self, action: Action) -> None:
        self._executor.register(action)
        self._actions[action.name] = action

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="browser",
            version="0.1.0",
            capabilities=[
                CapabilityManifest(
                    name=action.name,
                    description=action.description,
                    risk_tier=action.risk_tier,
                    permission_category=action.permission_category,
                )
                for action in self._actions.values()
            ],
        )

    def invoke(self, capability: str, payload: dict[str, Any]) -> InvocationResult:
        if capability not in self._actions:
            return InvocationResult(success=False, error=f"unsupported capability: {capability}")

        # Relay this call's already-obtained approval to the Executor's own
        # grant key -- identical pattern to FilesystemPlugin.invoke(); see
        # docs/adr/0005-executor-permission-relay.md.
        self._executor.permissions.grant(self._executor.name, capability, GrantScope.ONCE)

        result = self._executor.execute(capability, payload)

        if not result.success:
            return InvocationResult(
                success=False,
                error="; ".join(result.errors) or "unknown executor failure",
                execution_time_seconds=result.execution_time_seconds,
            )
        return InvocationResult(
            success=True,
            output=result.output,
            execution_time_seconds=result.execution_time_seconds,
        )
