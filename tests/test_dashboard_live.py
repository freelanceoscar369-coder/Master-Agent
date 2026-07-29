"""Live update and restart tests — MB026's acceptance criteria.

    1. Start Runtime. 2. Submit Objective. 3. Dashboard updates
    automatically. 4-7. Observe progression, transitions, verification,
    completion. 8. Restart Runtime. 9. Dashboard reconnects.
    10. Restored state is displayed correctly.
"""
from __future__ import annotations

import pytest

from master_agent.dashboard.app import FounderDashboard, build_dashboard
from master_agent.dashboard.charset import ASCII
from master_agent.mission_control.events import EventType
from master_agent.persistence.recovery import recover
from tests.dashboard_test_support import System


@pytest.fixture
def dirs(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    return tmp_path / "state", work


def dashboard_for(system: System, **kwargs) -> FounderDashboard:
    kwargs.setdefault("writer", lambda _text: None)
    return build_dashboard(
        mission_control=system.mission_control,
        runtime=system.engine,
        persistence=system.service,
        **kwargs,
    )


# ---- live updates -------------------------------------------------------


def test_the_dashboard_subscribes_to_mission_control_on_build(dirs):
    state, work = dirs
    system = System(state, work)
    dashboard = dashboard_for(system)

    dashboard.render_once(clear=False)
    assert dashboard._dirty is False

    system.submit()
    assert dashboard._dirty is True, "an event should have marked the view stale"


def test_a_tick_renders_only_when_something_changed(dirs):
    state, work = dirs
    system = System(state, work)
    dashboard = dashboard_for(system)

    assert dashboard.tick(clear=False) is not None  # first render
    assert dashboard.tick(clear=False) is None, "nothing changed; no redraw"

    system.submit()
    assert dashboard.tick(clear=False) is not None


def test_every_kind_of_event_refreshes_the_view_including_unknown_ones(dirs):
    """Subscribing to *all* events is what lets a future Executive's new
    event types still refresh the dashboard."""
    state, work = dirs
    system = System(state, work)
    dashboard = dashboard_for(system)
    dashboard.render_once(clear=False)

    system.mission_control.reporter_for("some_future_executive").report(
        EventType.RUNTIME_IDLE, payload={"cycle": 99}
    )
    assert dashboard._dirty is True


def test_the_dashboard_reflects_progress_as_the_runtime_advances(dirs):
    state, work = dirs
    system = System(state, work, max_cycles=1)
    dashboard = dashboard_for(system)
    system.submit()

    before = dashboard.snapshot().mission.progress
    system.run()
    after = dashboard.snapshot().mission.progress

    assert before == 0.0
    assert after > before


def test_the_dashboard_observes_executive_transitions(dirs):
    state, work = dirs
    system = System(state, work, max_cycles=1)
    dashboard = dashboard_for(system)
    system.submit()

    idle = dashboard.snapshot().executives.executives[0]
    assert idle.current_task is None

    system.mission_control.dispatch_ready()
    busy = dashboard.snapshot().executives.executives[0]
    assert busy.current_task is not None, "a dispatched executive should show its task"


def test_the_dashboard_observes_verification_events(dirs):
    state, work = dirs
    system = System(state, work, max_cycles=1)
    dashboard = dashboard_for(system)
    system.submit()
    system.mission_control.dispatch_ready()
    system.mission_control.task_started("t1")
    system.mission_control.verification_completed("t1", verdict="matched", evidence_id="ev-1")

    audit = dashboard.snapshot().audit
    assert any(row.event_type == "verification_completed" for row in audit.recent)


def test_the_dashboard_observes_completion(dirs):
    state, work = dirs
    system = System(state, work, max_cycles=6)
    dashboard = dashboard_for(system)
    system.submit()
    system.run()

    snapshot = dashboard.snapshot()
    assert snapshot.mission.progress == 1.0
    assert snapshot.mission.mission_status == "completed"


def test_a_failing_subscriber_cannot_take_down_execution(dirs):
    """MB023's bus isolates subscribers -- which is what makes attaching a
    dashboard to a live system safe."""
    state, work = dirs
    system = System(state, work, max_cycles=6)

    def exploding(_event):
        raise RuntimeError("dashboard crashed")

    system.mission_control.bus.subscribe(exploding)
    system.submit()
    system.run()

    assert system.mission_control.founder_state().progress == 1.0


def test_rendering_counts_frames(dirs):
    state, work = dirs
    dashboard = dashboard_for(System(state, work))
    for _ in range(3):
        dashboard.render()
    assert dashboard.frames_rendered == 3


def test_the_last_snapshot_is_retained_for_inspection(dirs):
    state, work = dirs
    dashboard = dashboard_for(System(state, work))
    assert dashboard.last_snapshot is None
    dashboard.render()
    assert dashboard.last_snapshot is not None


def test_run_forever_can_be_bounded_by_frame_count(dirs):
    state, work = dirs
    frames: list[str] = []
    dashboard = build_dashboard(
        mission_control=System(state, work).mission_control,
        writer=frames.append,
        sleep=lambda _s: None,
    )
    dashboard.run_forever(clear=False, max_frames=4)
    assert len(frames) == 4


def test_the_background_loop_starts_and_stops(dirs):
    state, work = dirs
    frames: list[str] = []
    dashboard = build_dashboard(
        mission_control=System(state, work).mission_control,
        writer=frames.append,
        sleep=lambda _s: None,
        refresh_interval_seconds=0.001,
    )
    dashboard.start_background(clear=False)
    dashboard.stop()
    assert frames, "the background loop should have drawn at least one frame"


def test_starting_the_loop_twice_is_refused(dirs):
    state, work = dirs
    dashboard = build_dashboard(
        mission_control=System(state, work).mission_control,
        writer=lambda _t: None,
        sleep=lambda _s: None,
    )
    dashboard.start_background(clear=False)
    try:
        with pytest.raises(RuntimeError):
            dashboard.start_background(clear=False)
    finally:
        dashboard.stop()


def test_render_once_writes_through_the_injected_writer(dirs):
    state, work = dirs
    written: list[str] = []
    dashboard = build_dashboard(
        mission_control=System(state, work).mission_control, writer=written.append
    )
    dashboard.render_once(clear=False)
    assert written and "KALPAVRIKSHA" in written[0]


def test_clearing_can_be_disabled_so_frames_can_be_logged(dirs):
    from master_agent.dashboard.renderer import CLEAR_SCREEN

    state, work = dirs
    written: list[str] = []
    dashboard = build_dashboard(
        mission_control=System(state, work).mission_control, writer=written.append
    )
    dashboard.render_once(clear=False)
    assert CLEAR_SCREEN not in written[0]


# ---- restart / reconnect ------------------------------------------------


def test_the_dashboard_reconnects_to_a_restarted_system_and_shows_restored_state(dirs):
    """Acceptance criteria 8-10."""
    state, work = dirs

    first = System(state, work, max_cycles=2)
    first.submit()
    first.run()
    first.save()
    before = dashboard_for(first).snapshot()
    assert 0 < before.mission.progress < 1

    # A completely fresh process, then a fresh Dashboard attached to it.
    second = System(state, work, max_cycles=6)
    report = recover(second.service, second.mission_control, second.engine)
    reconnected = build_dashboard(
        mission_control=second.mission_control,
        runtime=second.engine,
        persistence=second.service,
        recovery_report=report,
        writer=lambda _t: None,
    )

    restored = reconnected.snapshot()
    assert restored.mission.objective == before.mission.objective
    assert restored.mission.progress == before.mission.progress
    assert restored.persistence.recovery_status == "recovered"
    assert restored.persistence.recovery_source == "snapshot"


def test_a_reconnected_dashboard_shows_restored_audit_history(dirs):
    state, work = dirs
    first = System(state, work, max_cycles=2)
    first.submit()
    first.run()
    first.save()
    before_entries = len(first.mission_control.audit)

    second = System(state, work, max_cycles=1)
    recover(second.service, second.mission_control, second.engine)
    snapshot = dashboard_for(second).snapshot()

    assert snapshot.audit.total_entries >= before_entries


def test_a_reconnected_dashboard_shows_the_resumed_cycle_counter(dirs):
    state, work = dirs
    first = System(state, work, max_cycles=2)
    first.submit()
    first.run()
    first.save()
    cycles = first.engine.health().active_cycle

    second = System(state, work, max_cycles=1)
    recover(second.service, second.mission_control, second.engine)

    assert dashboard_for(second).snapshot().runtime.active_cycle == cycles


def test_the_dashboard_keeps_updating_after_the_restart(dirs):
    state, work = dirs
    first = System(state, work, max_cycles=1)
    first.submit()
    first.run()
    first.save()

    second = System(state, work, max_cycles=6)
    recover(second.service, second.mission_control, second.engine)
    dashboard = dashboard_for(second)

    before = dashboard.snapshot().mission.progress
    second.run()
    assert dashboard.snapshot().mission.progress > before


def test_the_dashboard_surfaces_quarantined_work_after_an_unclean_restart(dirs):
    state, work = dirs
    first = System(state, work, max_cycles=1)
    first.submit()
    first.mission_control.dispatch_ready()
    first.mission_control.task_started("t1")  # in flight when the process dies
    first.save()

    second = System(state, work, max_cycles=1)
    report = recover(second.service, second.mission_control, second.engine)
    snapshot = build_dashboard(
        mission_control=second.mission_control,
        runtime=second.engine,
        persistence=second.service,
        recovery_report=report,
        writer=lambda _t: None,
    ).snapshot()

    assert snapshot.persistence.quarantined_tasks == 1
    assert snapshot.mission.errors
    assert snapshot.system_health.persistence_health == "warning"


# ---- definition of done -------------------------------------------------


def test_definition_of_done_a_founder_sees_the_system_without_issuing_commands(dirs):
    """Start, submit, and the dashboard shows everything -- no further
    founder action."""
    state, work = dirs
    system = System(state, work, max_cycles=6)
    frames: list[str] = []
    dashboard = build_dashboard(
        mission_control=system.mission_control,
        runtime=system.engine,
        persistence=system.service,
        writer=frames.append,
        sleep=lambda _s: None,
    )

    system.submit("Increase Founder Net Worth")
    system.run()
    system.save()

    from master_agent.dashboard.renderer import render_frame

    frame = render_frame(dashboard.snapshot(), charset=ASCII)

    assert "KALPAVRIKSHA" in frame
    assert "Increase Founder Net Worth" in frame
    assert "RUNTIME" in frame
    assert "filesystem" in frame          # the Executive
    assert "Filesystem." in frame         # registered capabilities, by name
    assert "PERSISTENCE" in frame
    assert "AUDIT" in frame
    assert "100%" in frame                # progress, completed
