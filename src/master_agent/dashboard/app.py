"""FounderDashboard — the live view (MB026 deliverables #1 and #10).

Subscribes to Mission Control's Event Bus and re-renders when anything
happens; also re-renders on a clock tick, because uptime advances with no
event to announce it (ADR-0016 Decision 4).

Read-only throughout. This class has no dispatch surface, no gateway, and
no way to mutate anything it observes -- `tests/test_dashboard_architecture.py`
asserts that mechanically.
"""
from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from typing import Any

from master_agent.dashboard.founder import build_founder_view
from master_agent.dashboard.founder_panels import render_founder_frame
from master_agent.dashboard.readmodel import DashboardSnapshot
from master_agent.dashboard.renderer import CLEAR_SCREEN, render_frame
from master_agent.dashboard.sources import DashboardSources

#: The two pages MB029 defines. Founder first, because a founder who
#: has to switch pages to find out whether the system needs them has been
#: shown the wrong thing by default.
FOUNDER_PAGE = "founder"
TECHNICAL_PAGE = "technical"


class FounderDashboard:
    def __init__(
        self,
        sources: DashboardSources,
        refresh_interval_seconds: float = 1.0,
        audit_limit: int | None = 8,
        include_founder_state: bool = True,
        writer: Any = None,
        sleep: Any = None,
        page: str = FOUNDER_PAGE,
    ) -> None:
        self._sources = sources
        self._refresh_interval = refresh_interval_seconds
        self._audit_limit = audit_limit
        self._include_founder_state = include_founder_state
        self._write = writer or (lambda text: print(text, end="", flush=True))
        self._sleep = sleep or time.sleep

        self._page = page
        self._dirty = True
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._frames_rendered = 0
        self._last_snapshot: DashboardSnapshot | None = None

    # ---- live updates -------------------------------------------------

    def attach_to(self, mission_control: Any) -> None:
        """Subscribe to every event type -- not an enumerated list -- so a
        future Executive emitting events this build has never heard of
        still refreshes the view."""
        mission_control.bus.subscribe(self._on_event)

    def _on_event(self, _event: Any) -> None:
        """Marks dirty and returns immediately. Rendering happens on the
        Dashboard's own loop, never on the publisher's thread: a slow
        render must never slow down execution."""
        self._dirty = True

    @property
    def frames_rendered(self) -> int:
        return self._frames_rendered

    @property
    def last_snapshot(self) -> DashboardSnapshot | None:
        return self._last_snapshot

    # ---- rendering ----------------------------------------------------

    def snapshot(self) -> DashboardSnapshot:
        snapshot = self._sources.collect()
        self._last_snapshot = snapshot
        return snapshot

    def render(self) -> str:
        """Collect and compose one frame. Pure with respect to the
        observed system -- calling this a thousand times changes nothing
        about Kalpavriksha.

        Two pages (MB029). FOUNDER answers "what is it doing, does it need
        me, what next"; TECHNICAL is the nine engineering panels MB026
        shipped, unchanged. Same snapshot, two views -- which is the point
        of having a read model at all.
        """
        snapshot = self.snapshot()
        if self._page == FOUNDER_PAGE:
            frame = render_founder_frame(build_founder_view(snapshot))
        else:
            frame = render_frame(
                snapshot,
                audit_limit=self._audit_limit,
                include_founder_state=self._include_founder_state,
            )
        self._frames_rendered += 1
        return frame

    @property
    def page(self) -> str:
        return self._page

    def show(self, page: str) -> str:
        """Switch page. Returns the page now showing, so a caller can
        report it without re-reading state."""
        self._page = FOUNDER_PAGE if page == FOUNDER_PAGE else TECHNICAL_PAGE
        self._dirty = True
        return self._page

    def toggle_page(self) -> str:
        return self.show(
            TECHNICAL_PAGE if self._page == FOUNDER_PAGE else FOUNDER_PAGE
        )

    def founder_view(self):
        """The view model, for a caller that wants the data rather than
        the text -- a web or desktop front-end (Deliverable 10)."""
        return build_founder_view(self.snapshot())

    def render_once(self, clear: bool = True) -> str:
        frame = self.render()
        self._write((CLEAR_SCREEN if clear else "") + frame + "\n")
        self._dirty = False
        return frame

    # ---- loop ---------------------------------------------------------

    def tick(self, clear: bool = True) -> str | None:
        """One iteration: render if something happened or the interval
        elapsed. Returns the frame if one was drawn, else None."""
        if not self._dirty:
            return None
        return self.render_once(clear=clear)

    def run_forever(self, clear: bool = True, max_frames: int | None = None) -> None:
        drawn = 0
        while not self._stop.is_set():
            if max_frames is not None and drawn >= max_frames:
                break
            self.render_once(clear=clear)
            drawn += 1
            # Time-based fields (uptime) change with no event to announce
            # them, so the next tick is always due.
            self._dirty = True
            self._sleep(self._refresh_interval)

    def start_background(self, clear: bool = True) -> None:
        if self._thread is not None:
            raise RuntimeError("dashboard is already running")
        self._stop.clear()
        self._thread = threading.Thread(
            target=lambda: self.run_forever(clear=clear), daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)
            self._thread = None


def build_dashboard(
    mission_control: Any = None,
    runtime: Any = None,
    persistence: Any = None,
    recovery_report: Any = None,
    **kwargs: Any,
) -> FounderDashboard:
    """One call a launcher makes. Attaches live updates when there is a
    Mission Control to attach to; everything is optional, so a partially
    wired system still yields a working, honest dashboard."""
    sources = DashboardSources(
        mission_control=mission_control,
        runtime=runtime,
        persistence=persistence,
        recovery_report=recovery_report,
        inventory_provider=kwargs.pop("inventory_provider", None),
        clock=kwargs.pop("clock", None) or (lambda: datetime.now(UTC)),
    )
    dashboard = FounderDashboard(sources, **kwargs)
    if mission_control is not None:
        dashboard.attach_to(mission_control)
    return dashboard
