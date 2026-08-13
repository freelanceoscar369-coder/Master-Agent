"""Desktop Intelligence · Part F — runtime integration boundary.

`DesktopIntelligence.observe_desktop()` is the stable API the mission
asks for: `observe_desktop(application) -> DesktopObservation`. It
resolves an already-running application's window the same read-only way
`_VerifiedInteractionAction._resolve_window()` (`actions_interaction.py`)
already does — process attribution, then `WindowManager.locate_by_process()`
— but never focuses, maximizes, or otherwise touches the window it finds;
observation must never depend on bringing anything to the foreground.

**Does not touch the reasoning-provider architecture.** This class holds
no `ReasoningSessionManager`, calls no `DesktopAppReasoningProvider`
method, and is never constructed by either — a deliberately separate,
optional capability a *future* Plan/Act layer can call, not something
wired into the existing, frozen `complete()` path this mission (Part F,
Hard Scope Boundary) is explicit must not change.
"""
from __future__ import annotations

from datetime import UTC, datetime

from master_agent.app_knowledge.profile import KnowledgeType
from master_agent.desktop import catalog
from master_agent.desktop.actions import DesktopContext
from master_agent.desktop.execution.backends import WindowInfo
from master_agent.desktop.execution.uia_control import UiaAutomationBridge
from master_agent.desktop.execution.win32_backends import Win32WindowBackend
from master_agent.desktop.execution.window import WindowManager
from master_agent.desktop.intelligence.app_knowledge_bridge import resolve_app_knowledge
from master_agent.desktop.intelligence.evidence import capture_evidence
from master_agent.desktop.intelligence.models import DesktopObservation, unknown_observation
from master_agent.desktop.intelligence.screenshot import ScreenshotBackend

SOURCE = "DesktopIntelligence.observe_desktop()"


class DesktopIntelligence:
    """One entry point, callable by any future mission:
    `observe_desktop(application) -> DesktopObservation`. Holds only
    read-only collaborators — a `UiaAutomationBridge` and a
    `WindowManager` — the same collaborators `_VerifiedInteractionAction`
    already holds, reused rather than re-instantiated per call for the
    same COM-overhead reason `actions_interaction.py`'s own module-level
    `_uia_bridge` is shared."""

    def __init__(
        self,
        context: DesktopContext,
        *,
        uia: UiaAutomationBridge | None = None,
        windows: WindowManager | None = None,
        screenshot_backend: ScreenshotBackend | None = None,
    ) -> None:
        self._context = context
        self._uia = uia or UiaAutomationBridge()
        self._windows = windows or WindowManager(Win32WindowBackend())
        self._screenshot_backend = screenshot_backend

    def observe_desktop(
        self,
        application: str,
        *,
        baseline: dict | None = None,
        capture_screenshot: bool = False,
        now: datetime | None = None,
    ) -> DesktopObservation:
        """Read-only, end to end. `capture_screenshot=False` by default —
        Part C's own capability exists and is exercised by any caller
        that opts in, but observation itself never requires a screenshot
        to succeed."""
        now = now or datetime.now(UTC)

        spec = catalog.resolve(application)
        if spec is None:
            return unknown_observation(
                reason=f"{application!r} is not a known application",
                source=SOURCE, timestamp=now, application=application,
            )

        inventory = self._context.refresh(read_versions=False, deep=False)
        running = inventory.running(spec.key)
        if not running:
            return unknown_observation(
                reason=f"{spec.label} is not running", source=SOURCE, timestamp=now, application=application,
            )
        pids = frozenset(p.pid for p in running)

        located = self._windows.locate_by_process(pids)
        if not located.success or not located.output.get("windows"):
            return unknown_observation(
                reason=f"{spec.label} is running (pid(s): {sorted(pids)}) but no window was found for it",
                source=SOURCE, timestamp=now, application=application,
            )
        window = WindowInfo(**located.output["windows"][0])

        app_knowledge = resolve_app_knowledge(application)

        return capture_evidence(
            uia=self._uia, window=window, application=application,
            application_confidence=KnowledgeType.OBSERVED,
            application_reason=(
                f"window {window.handle} attributed to {application!r} via "
                f"process id(s) {sorted(pids)}"
            ),
            app_knowledge=app_knowledge, baseline=baseline,
            screenshot_backend=self._screenshot_backend if capture_screenshot else None,
            now=now,
        )
