"""A failed mission must not make the next one impossible.

## The failure

    attempt 1 opens session "main"
    -> a step fails before the planned CloseBrowserSession
    -> mission ends
    -> recovery starts a second attempt
    -> OpenBrowserSession("main")
    -> "session already open: 'main'"

The second mission failed for a reason the founder's request had nothing
to do with. One attempt's leftovers made the next one impossible, which
is what took autonomous recovery off the table.

## The line that must hold

Anonymous sessions are ephemeral by construction -- a fresh automated
context that starts empty and forgets everything, belonging to the task
that opened it and to nothing else. An IDENTITY session carries the
founder's signed-in state, and closing it would sign them out of
something they were using. Cleanup releases the first and never touches
the second.

Releasing an environment is not a claim about the mission. A cleaned-up
failure is still a failure.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from master_agent.environment.browser_session import (
    BrowserSessionHandle,
    BrowserSessionManager,
)


class Recorder(BrowserSessionManager):
    """A manager whose sessions are bookkeeping rather than browsers, so
    the ownership rule can be tested without launching anything."""

    def __init__(self, handles):
        super().__init__()
        self.closed: list[str] = []
        for handle in handles:
            self._handles[handle.session_id] = handle
            self._sessions[handle.session_id] = object()

    def close_session(self, session_id: str):
        self.closed.append(session_id)
        self._handles.pop(session_id, None)
        self._sessions.pop(session_id, None)
        return []


def handle(session_id: str, identity_id: str | None = None):
    return BrowserSessionHandle(
        session_id=session_id,
        opened_at=datetime.now(UTC),
        headless=False,
        channel="chrome",
        identity_id=identity_id,
    )


class TestTaskOwnedSessionsAreReleased:
    def test_an_anonymous_session_is_closed(self):
        manager = Recorder([handle("main")])
        manager.close_anonymous()
        assert manager.closed == ["main"]

    def test_every_anonymous_session_is_closed(self):
        manager = Recorder([handle("main"), handle("second")])
        manager.close_anonymous()
        assert sorted(manager.closed) == ["main", "second"]

    def test_the_next_mission_can_open_the_same_session_id(self):
        """The whole point. `'main'` has to be free again."""
        manager = Recorder([handle("main")])
        manager.close_anonymous()
        assert [h.session_id for h in manager.list_sessions()] == []

    def test_releasing_nothing_is_not_an_error(self):
        manager = Recorder([])
        assert manager.close_anonymous() == {}


class TestTheFoundersOwnBrowserIsNeverTouched:
    def test_an_identity_session_survives_cleanup(self):
        """It carries their signed-in state. Closing it would sign them
        out of something they were using."""
        manager = Recorder([handle("founder", identity_id="founder")])
        manager.close_anonymous()
        assert manager.closed == []

    def test_a_mixed_set_releases_only_the_anonymous_one(self):
        manager = Recorder([
            handle("main"),
            handle("founder", identity_id="founder"),
        ])
        manager.close_anonymous()
        assert manager.closed == ["main"]

    def test_close_all_still_closes_everything(self):
        """The distinction is `close_anonymous`'s, not a change to what
        shutdown means."""
        manager = Recorder([
            handle("main"),
            handle("founder", identity_id="founder"),
        ])
        manager.close_all()
        assert sorted(manager.closed) == ["founder", "main"]


class TestTheSurfaceReleasesOnMissionEnd:
    def test_cleanup_runs_whether_the_mission_passed_or_failed(self):
        import inspect

        import kalpavriksha_desktop as kd

        source = inspect.getsource(kd._submit_objective)
        assert "_release_task_browsers()" in source
        # Before the success/failure branch, so a failed mission is
        # cleaned up too -- which is the case that caused this.
        before_branch = source.split("if state.errors:")[0]
        assert "_release_task_browsers()" in before_branch

    def test_cleanup_never_becomes_the_failure(self):
        """Housekeeping that raised would turn a completed mission into a
        crash."""
        import kalpavriksha_desktop as kd

        class Exploding:
            def close_anonymous(self):
                raise RuntimeError("the driver is gone")

        original = kd._BROWSER_SESSIONS
        kd._BROWSER_SESSIONS = Exploding()
        try:
            kd._release_task_browsers()  # must not raise
        finally:
            kd._BROWSER_SESSIONS = original

    def test_no_session_manager_yet_is_not_an_error(self):
        import kalpavriksha_desktop as kd

        original = kd._BROWSER_SESSIONS
        kd._BROWSER_SESSIONS = None
        try:
            kd._release_task_browsers()
        finally:
            kd._BROWSER_SESSIONS = original

    def test_cleanup_says_nothing_about_mission_success(self):
        """A cleaned-up failure is still a failure. Nothing in the
        release path touches the founder-facing outcome."""
        import inspect

        import kalpavriksha_desktop as kd

        source = inspect.getsource(kd._release_task_browsers)
        for forbidden in ("status.", "message", "COMPLETED", "success"):
            assert forbidden not in source, forbidden
