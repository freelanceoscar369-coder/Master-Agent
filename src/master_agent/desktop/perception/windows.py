"""C27 · Window Observer — read-only, and only the read-only half of C26.

Determines the active window, the focused application, its title,
process, minimized/maximized state, and whether it is the OS foreground
window. **Never mutates.** Only three `WindowManager` (C26) methods are
ever called — `enumerate()`, `active()`, `locate_by_process()` — and
`bring_to_front`/`minimize`/`maximize`/`restore`/`close` are never
referenced anywhere in this file, checked by AST in `tests/
test_desktop_perception.py`.

**"Focused application" is resolved without a second inventory.** The
active window's `process_id` is looked up against `MachineInventory
.processes`, whose `owner` field `desktop/inventory.py`'s existing
`attribute_processes()` already computed — the same fact `desktop
.actions.IsRunningAction` reads. No new process-to-application mapping is
invented here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from master_agent.desktop.execution.backends import WindowInfo
from master_agent.desktop.execution.window import WindowManager
from master_agent.desktop.inventory import MachineInventory
from master_agent.desktop.perception.evidence import (
    Confidence,
    Observation,
    unknown_observation,
)

SOURCE_ENUMERATE = "WindowManager.enumerate()"
SOURCE_ACTIVE = "WindowManager.active()"


@dataclass(frozen=True)
class WindowObservation:
    """Every window on the desktop, as of `timestamp`, plus which one
    (if any) is the OS foreground window and which catalogued
    application (if known) owns it."""

    windows: Observation
    """`.value` is `tuple[WindowInfo, ...]` when known."""

    active_window: Observation
    """`.value` is a `WindowInfo` or `None` when nothing is active."""

    active_application: Observation
    """`.value` is an application key (`str`) or `None` — resolved from
    `MachineInventory`'s own process attribution, never guessed from a
    window title."""

    timestamp: datetime

    def is_foreground(self, window: WindowInfo) -> bool:
        """Whether `window` is the one this observation found active.
        Computed, never stored twice — the same *"one source of truth"*
        discipline `CapabilityGraph.reaches()` (C22) already applies."""
        active = self.active_window.value
        return active is not None and active.handle == window.handle

    def as_dict(self) -> dict[str, Any]:
        return {
            "windows": self.windows.as_dict(),
            "active_window": self.active_window.as_dict(),
            "active_application": self.active_application.as_dict(),
            "timestamp": self.timestamp.isoformat(),
        }


class WindowObserver:
    """Read-only. Every method call this class makes against
    `WindowManager` is one of its three non-mutating methods."""

    __slots__ = ("_windows",)

    def __init__(self, window_manager: WindowManager | None = None) -> None:
        self._windows = window_manager or WindowManager()

    def observe(
        self, timestamp: datetime, inventory: MachineInventory | None = None
    ) -> WindowObservation:
        # `visible_only=False`: perception must see a *hidden* window to
        # ever report `WINDOW_HIDDEN` (`failures.py`) — the mutation-side
        # default (visible windows only, C26) would silently make that
        # failure kind undetectable.
        enumerated = self._windows.enumerate(visible_only=False)
        if enumerated.success:
            windows = tuple(
                WindowInfo(**w) for w in enumerated.output["windows"]
            )
            windows_obs = Observation(
                value=windows, confidence=Confidence.OBSERVED,
                reason=f"{len(windows)} visible window(s) enumerated",
                source=SOURCE_ENUMERATE, timestamp=timestamp,
            )
        else:
            windows_obs = unknown_observation(
                reason="; ".join(enumerated.errors) or "enumeration failed",
                source=SOURCE_ENUMERATE, timestamp=timestamp,
            )

        active_result = self._windows.active()
        if active_result.success:
            active_window = WindowInfo(**active_result.output)
            active_obs = Observation(
                value=active_window, confidence=Confidence.OBSERVED,
                reason=f"the foreground window is {active_window.title!r}",
                source=SOURCE_ACTIVE, timestamp=timestamp,
            )
        else:
            active_window = None
            active_obs = unknown_observation(
                reason="; ".join(active_result.errors) or "no active window",
                source=SOURCE_ACTIVE, timestamp=timestamp,
            )

        active_application = _resolve_owner(active_window, inventory)
        if active_application is not None:
            app_obs = Observation(
                value=active_application, confidence=Confidence.OBSERVED,
                reason=(
                    f"process {active_window.process_id} is attributed to "
                    f"{active_application!r} in the machine inventory"
                ),
                source="MachineInventory.processes[].owner",
                timestamp=timestamp,
            )
        elif active_window is None:
            app_obs = unknown_observation(
                reason="no window is active, so no application can be focused",
                source="MachineInventory.processes[].owner", timestamp=timestamp,
            )
        elif inventory is None:
            app_obs = unknown_observation(
                reason="no machine inventory was supplied to attribute the active window's process",
                source="MachineInventory.processes[].owner", timestamp=timestamp,
            )
        else:
            app_obs = unknown_observation(
                reason=(
                    f"process {active_window.process_id} is not attributed "
                    "to any catalogued application"
                ),
                source="MachineInventory.processes[].owner", timestamp=timestamp,
            )

        return WindowObservation(
            windows=windows_obs, active_window=active_obs,
            active_application=app_obs, timestamp=timestamp,
        )


def _resolve_owner(
    active_window: WindowInfo | None, inventory: MachineInventory | None
) -> str | None:
    if active_window is None or inventory is None:
        return None
    for process in inventory.processes:
        if process.pid == active_window.process_id:
            return process.owner
    return None
