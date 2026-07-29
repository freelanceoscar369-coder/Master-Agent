"""Mission Brief 029 — Founder Dashboard V2.

The Definition of Done is a claim about a person, not a program: a
first-time founder should understand what Kalpavriksha is doing, whether
it needs them, and what to do next, in five seconds. That is not directly
testable, so these tests hold the things that make it true — the right
answers, in the right order, with no engineering leakage and no invented
numbers.
"""
from __future__ import annotations

import io
from datetime import UTC, datetime

import pytest

from master_agent.dashboard.app import (
    FOUNDER_PAGE,
    TECHNICAL_PAGE,
    build_dashboard,
)
from master_agent.dashboard.charset import ASCII, UNICODE, detect
from master_agent.dashboard.founder import (
    NEEDS_ATTENTION,
    WAITING_ON_YOU,
    WORKING,
    as_dict,
    build_daily_summary,
    build_founder_view,
)
from master_agent.dashboard.founder_panels import (
    render_daily_summary,
    render_decisions,
    render_founder_frame,
    render_mission,
    render_readiness,
    render_recommendations,
    render_self_development,
    render_status,
)
from master_agent.dashboard.readmodel import (
    ApprovalPanelData,
    ApprovalRow,
    CapabilityPanelData,
    DashboardSnapshot,
    ExecutivePanelData,
    ExecutiveRow,
    MissionPanelData,
    RuntimePanelData,
)
from master_agent.dashboard.roadmap import (
    EXPECTED_EXECUTIVES,
    MISSING,
    PLANNED,
    READY,
    RECOMMENDATIONS,
    SELF_DEVELOPMENT_PHASES,
)
from master_agent.launcher.console import FounderConsole, NullKeyReader
from master_agent.mission_control.approvals import PendingApproval
from master_agent.mission_control.mission_control import MissionControl

NOW = datetime(2026, 7, 29, 22, 13, tzinfo=UTC)


def snapshot(**kwargs) -> DashboardSnapshot:
    defaults = {
        "captured_at": NOW,
        "runtime": RuntimePanelData(state="idle", uptime_seconds=3600),
        "capabilities": CapabilityPanelData(
            registered=["Filesystem.CreateFolder"],
            pending=2,
            active=4,
            completed=31,
            failed=0,
            blocked=0,
        ),
        "executives": ExecutivePanelData(
            executives=[
                ExecutiveRow("filesystem", "healthy", "1.0.0", "ready", 14),
                ExecutiveRow("browser", "healthy", "1.0.0", "ready", 9),
            ]
        ),
    }
    defaults.update(kwargs)
    return DashboardSnapshot(**defaults)


def with_decision(**kwargs) -> DashboardSnapshot:
    return snapshot(
        approvals=ApprovalPanelData(
            approvals=[
                ApprovalRow(
                    index=1,
                    approval_id="ab12cd34",
                    capability="Filesystem.DeleteFolder",
                    executive_id="filesystem",
                    risk_tier="irreversible",
                    reason="Delete Folder",
                    impact="Deletes 14 files",
                    requested_at="22:13",
                    state="pending",
                    objective="Clear out old reports",
                )
            ]
        ),
        **kwargs,
    )


def mission_snapshot(**mission) -> DashboardSnapshot:
    defaults = {
        "objective": "Build AI Capability Broker",
        "progress": 0.52,
        "active_capability": "Filesystem.WriteFile",
        "eta_seconds": 900.0,
        "evidence_count": 6,
    }
    defaults.update(mission)
    return snapshot(mission=MissionPanelData(**defaults))


# ---- Deliverable 1: the executive summary --------------------------------


def test_the_founder_page_is_the_default():
    dashboard = build_dashboard(writer=lambda _t: None)

    assert dashboard.page == FOUNDER_PAGE


def test_the_frame_opens_with_the_product_name():
    frame = render_founder_frame(build_founder_view(snapshot()), ASCII)

    assert frame.splitlines()[1].strip() == "KALPAVRIKSHA"


def test_every_deliverable_1_section_is_present():
    frame = render_founder_frame(build_founder_view(with_decision()), ASCII)

    for heading in (
        "STATUS",
        "FOUNDER DECISIONS",
        "CURRENT MISSION",
        "TODAY'S WORK",
        "EXECUTIVES",
        "SELF DEVELOPMENT",
        "RECOMMENDATIONS",
        "NEXT RECOMMENDED STEP",
    ):
        assert heading in frame, f"missing section: {heading}"


def test_todays_work_counts_come_from_the_snapshot():
    view = build_founder_view(with_decision())

    assert view.work.completed == 31
    assert view.work.running == 4
    assert view.work.awaiting_approval == 1


def test_the_frame_is_short_enough_to_take_in_at_once():
    """Five seconds is a length claim as much as a content one. Sixty
    lines is roughly one terminal; more than that and a founder scrolls,
    which is where the old dashboard lost them."""
    frame = render_founder_frame(build_founder_view(with_decision()), ASCII)

    assert len(frame.splitlines()) <= 60


# ---- panel ordering ------------------------------------------------------


def test_status_comes_first_and_decisions_second():
    """A founder asks "is it OK" then "does it need me". Anything else
    above those two is in the way."""
    frame = render_founder_frame(build_founder_view(with_decision()), ASCII)

    positions = {
        heading: frame.index(heading)
        for heading in ("STATUS", "FOUNDER DECISIONS", "CURRENT MISSION")
    }

    assert positions["STATUS"] < positions["FOUNDER DECISIONS"]
    assert positions["FOUNDER DECISIONS"] < positions["CURRENT MISSION"]


def test_recommendations_come_last_before_the_next_step():
    frame = render_founder_frame(build_founder_view(snapshot()), ASCII)

    assert frame.index("RECOMMENDATIONS") < frame.index("NEXT RECOMMENDED STEP")
    assert frame.index("SELF DEVELOPMENT") < frame.index("RECOMMENDATIONS")


def test_decisions_outrank_the_mission_even_when_a_mission_is_running():
    frame = render_founder_frame(
        build_founder_view(
            with_decision(
                mission=MissionPanelData(objective="Something big", progress=0.9)
            )
        ),
        ASCII,
    )

    assert frame.index("FOUNDER DECISIONS") < frame.index("CURRENT MISSION")


# ---- Deliverable 2: no engineering leakage -------------------------------

ENGINEERING_TERMS = (
    "snapshot version",
    "event log size",
    "audit entries",
    "active cycle",
    "queue length",
    "objective_id",
    "capability registered",
    "event_id",
    "schema_version",
    "last checkpoint",
    "founder state",
    "learning_progress",
    "waiting_approval",
)


@pytest.mark.parametrize("term", ENGINEERING_TERMS)
def test_the_founder_page_leaks_no_engineering_detail(term):
    frame = render_founder_frame(build_founder_view(with_decision()), ASCII).lower()

    assert term not in frame, f"engineering detail leaked onto the founder page: {term}"


def test_the_founder_page_shows_no_raw_identifiers():
    """An approval id, an objective id, or a task id on the founder page
    is a thing a founder cannot act on and must learn to ignore."""
    frame = render_founder_frame(build_founder_view(with_decision()), ASCII)

    assert "ab12cd34" not in frame


def test_the_technical_page_still_has_everything_it_had():
    """MB029 moves engineering detail; it does not delete it."""
    dashboard = build_dashboard(writer=lambda _t: None, page=TECHNICAL_PAGE)

    frame = dashboard.render()

    for heading in ("RUNTIME", "CAPABILITIES", "AUDIT", "PERSISTENCE"):
        assert heading in frame


def test_the_two_pages_render_from_one_snapshot():
    mc = MissionControl()
    dashboard = build_dashboard(mission_control=mc, writer=lambda _t: None)

    founder = dashboard.render()
    dashboard.show(TECHNICAL_PAGE)
    technical = dashboard.render()

    assert founder != technical
    assert "SELF DEVELOPMENT" in founder
    assert "SELF DEVELOPMENT" not in technical


def test_toggling_returns_to_the_founder_page():
    dashboard = build_dashboard(writer=lambda _t: None)

    assert dashboard.toggle_page() == TECHNICAL_PAGE
    assert dashboard.toggle_page() == FOUNDER_PAGE


def test_switching_page_marks_the_view_dirty():
    dashboard = build_dashboard(writer=lambda _t: None)
    dashboard.render_once(clear=False)
    assert dashboard._dirty is False

    dashboard.show(TECHNICAL_PAGE)

    assert dashboard._dirty is True


# ---- Deliverable 3: human health -----------------------------------------


def test_a_healthy_system_says_working_normally():
    view = build_founder_view(snapshot())

    assert view.status == WORKING
    assert view.status_reason == ""


def test_a_missing_executive_needs_attention_and_says_which():
    view = build_founder_view(
        snapshot(executives=ExecutivePanelData(executives=[]))
    )

    assert view.status == NEEDS_ATTENTION
    assert "Filesystem" in view.status_reason


def test_failures_need_attention():
    view = build_founder_view(
        snapshot(capabilities=CapabilityPanelData(completed=3, failed=2))
    )

    assert view.status == NEEDS_ATTENTION
    assert "2 failed" in view.status_reason


def test_a_pending_decision_outranks_a_missing_executive():
    """Blocked-on-you and broken feel very different at 22:13, and the
    founder should be told the one they can act on."""
    view = build_founder_view(
        with_decision(executives=ExecutivePanelData(executives=[]))
    )

    assert view.status == WAITING_ON_YOU
    assert "1 decision" in view.status_reason


def test_the_status_line_never_shows_a_subsystem_name():
    frame = "\n".join(render_status(build_founder_view(snapshot()), ASCII))

    for subsystem in ("audit", "persistence", "runtime", "dispatcher"):
        assert subsystem not in frame.lower()


# ---- Deliverable 4: mission progress -------------------------------------


def test_the_mission_shows_name_step_remaining_and_estimate():
    view = build_founder_view(mission_snapshot())

    assert view.mission.name == "Build AI Capability Broker"
    assert view.mission.current_step == "Filesystem.WriteFile"
    assert view.mission.steps_remaining == 6
    assert view.mission.estimated_seconds == 900.0


def test_confidence_is_read_from_verification_not_invented():
    high = build_founder_view(mission_snapshot())

    assert high.mission.confidence == "High"
    assert "verified" in high.mission.confidence_basis


def test_confidence_is_low_when_steps_have_failed():
    view = build_founder_view(
        snapshot(
            mission=MissionPanelData(objective="M", progress=0.5),
            capabilities=CapabilityPanelData(completed=4, failed=1, pending=0, active=0),
        )
    )

    assert view.mission.confidence == "Low"


def test_confidence_is_absent_rather_than_guessed_when_nothing_completed():
    view = build_founder_view(
        snapshot(
            mission=MissionPanelData(objective="M"),
            capabilities=CapabilityPanelData(completed=0, pending=3, active=0),
        )
    )

    assert view.mission.confidence is None
    rendered = "\n".join(render_mission(view, ASCII))
    assert "Confidence       not measured" in rendered
    assert "nothing has completed yet" in rendered


def test_unverified_work_says_so_rather_than_claiming_confidence():
    view = build_founder_view(
        snapshot(
            mission=MissionPanelData(objective="M", evidence_count=0),
            capabilities=CapabilityPanelData(completed=5, failed=0, pending=0, active=0),
        )
    )

    assert view.mission.confidence == "Unverified"


def test_no_mission_is_a_normal_state_not_a_missing_panel():
    lines = render_mission(build_founder_view(snapshot()), ASCII)

    assert lines[1].strip() == "nothing in flight"


def test_an_unknown_estimate_says_unknown_rather_than_zero():
    view = build_founder_view(mission_snapshot(eta_seconds=None))

    assert "unknown" in "\n".join(render_mission(view, ASCII))


def test_the_progress_bar_reflects_the_fraction():
    lines = render_mission(build_founder_view(mission_snapshot(progress=0.5)), ASCII)

    bar = next(line for line in lines if ASCII.bar_full in line)
    assert bar.count(ASCII.bar_full) == 6
    assert "50%" in bar


# ---- Deliverable 5: executive readiness ----------------------------------


def test_registered_executives_read_as_ready():
    view = build_founder_view(snapshot())
    statuses = {e.label: e.status for e in view.executives}

    assert statuses["Filesystem"] == READY
    assert statuses["Browser"] == READY


def test_unbuilt_executives_read_as_planned_not_missing():
    """Planned and Missing are different facts: one is unfinished, the
    other is wrong."""
    view = build_founder_view(snapshot())
    statuses = {e.label: e.status for e in view.executives}

    assert statuses["Desktop"] == PLANNED
    assert statuses["AI Broker"] == PLANNED


def test_an_expected_but_absent_executive_reads_as_missing():
    view = build_founder_view(
        snapshot(
            executives=ExecutivePanelData(
                executives=[ExecutiveRow("filesystem", "healthy", "1.0.0", "ready", 14)]
            )
        )
    )
    statuses = {e.label: e.status for e in view.executives}

    assert statuses["Browser"] == MISSING


def test_readiness_never_shows_a_capability_count():
    frame = "\n".join(render_readiness(build_founder_view(snapshot()), ASCII))

    assert "14" not in frame
    assert "capabilit" not in frame.lower()


def test_a_degraded_executive_is_still_ready_but_says_why():
    view = build_founder_view(
        snapshot(
            executives=ExecutivePanelData(
                executives=[
                    ExecutiveRow("filesystem", "degraded", "1.0.0", "ready", 14),
                    ExecutiveRow("browser", "healthy", "1.0.0", "ready", 9),
                ]
            )
        )
    )
    filesystem = next(e for e in view.executives if e.label == "Filesystem")

    assert filesystem.status == READY
    assert "degraded" in filesystem.detail


# ---- Deliverable 6: self development -------------------------------------


def test_every_roadmap_phase_is_shown():
    lines = "\n".join(render_self_development(build_founder_view(snapshot()), ASCII))

    for phase in SELF_DEVELOPMENT_PHASES:
        assert phase.label in lines


def test_phase_progress_is_declared_not_computed():
    """Every phase names what its number is a reading of, so a founder can
    check it and a future session can update it honestly."""
    for phase in SELF_DEVELOPMENT_PHASES:
        assert phase.basis, f"{phase.label} has no stated basis"
        assert 0.0 <= phase.fraction <= 1.0


def test_phase_bars_render_at_the_declared_fraction():
    view = build_founder_view(snapshot())
    testing = next(p for p in view.phases if p.label == "Testing")

    assert testing.fraction == 1.0
    line = next(
        line
        for line in render_self_development(view, ASCII)
        if line.strip().startswith("Testing")
    )
    assert line.count(ASCII.bar_empty) == 0


# ---- Deliverable 7: founder decisions ------------------------------------


def test_the_decisions_panel_is_visible_even_when_empty():
    """A panel that disappears when empty trains a founder to stop
    looking for it."""
    lines = render_decisions(build_founder_view(snapshot()), ASCII)

    assert lines[0] == "FOUNDER DECISIONS"
    assert "none pending" in lines[1]


def test_a_decision_shows_what_it_is_and_what_it_costs():
    lines = "\n".join(render_decisions(build_founder_view(with_decision()), ASCII))

    assert "Delete Folder" in lines
    assert "Deletes 14 files" in lines
    assert "IRREVERSIBLE" in lines
    assert "22:13" in lines


def test_the_decision_offers_the_documented_keys():
    lines = "\n".join(render_decisions(build_founder_view(with_decision()), ASCII))

    assert "[Y]es" in lines
    assert "[N]o" in lines
    assert "[D]efer" in lines


def test_decisions_are_numbered_for_the_console():
    view = build_founder_view(with_decision())

    assert view.decisions[0].index == 1
    assert view.needs_founder is True


# ---- Deliverable 8: recommendations --------------------------------------


def test_recommendations_come_from_the_roadmap():
    view = build_founder_view(snapshot())
    roadmap_texts = {r.text for r in RECOMMENDATIONS}

    assert view.recommendations
    for text in view.recommendations:
        assert text in roadmap_texts


def test_every_roadmap_recommendation_names_its_source():
    for recommendation in RECOMMENDATIONS:
        assert recommendation.source, f"{recommendation.text} has no source"


def test_a_recommendation_disappears_once_its_executive_exists():
    """Recommending something already built is noise a founder learns to
    scroll past."""
    with_broker = snapshot(
        executives=ExecutivePanelData(
            executives=[
                ExecutiveRow("filesystem", "healthy", "1.0.0", "ready", 14),
                ExecutiveRow("browser", "healthy", "1.0.0", "ready", 9),
                ExecutiveRow("ai_broker", "healthy", "1.0.0", "ready", 3),
            ]
        )
    )

    before = build_founder_view(snapshot()).recommendations
    after = build_founder_view(with_broker).recommendations

    assert any("AI Capability Broker" in r for r in before)
    assert not any("AI Capability Broker" in r for r in after)


def test_the_next_step_is_the_first_recommendation():
    view = build_founder_view(snapshot())

    assert view.next_step == view.recommendations[0]


def test_nothing_needed_is_a_real_answer():
    from master_agent.dashboard.roadmap import NOTHING_NEEDED

    everything = snapshot(
        executives=ExecutivePanelData(
            executives=[
                ExecutiveRow(expected.executive_id, "healthy", "1.0.0", "ready", 1)
                for expected in EXPECTED_EXECUTIVES
            ]
        )
    )
    view = build_founder_view(everything)
    view = type(view)(
        **{**view.__dict__, "recommendations": [], "next_step": NOTHING_NEEDED}
    )

    assert "nothing needed" in "\n".join(render_recommendations(view, ASCII)).lower()


# ---- Deliverable 9: daily summary ----------------------------------------


def test_the_daily_summary_reports_what_happened():
    summary = build_daily_summary(snapshot(), approvals_decided=3, recovered=1)

    assert summary.completed == 31
    assert summary.approvals_decided == 3
    assert summary.recovered == 1


def test_the_daily_summary_names_tomorrow():
    summary = build_daily_summary(snapshot())

    assert summary.tomorrow == build_founder_view(snapshot()).next_step


def test_time_saved_is_reported_as_unmeasured_rather_than_invented():
    """MB029 asks for "Time Saved". Nothing measures what a task would
    have cost a human, so there is no honest number — and a founder would
    read an invented one as fact."""
    rendered = render_daily_summary(build_daily_summary(snapshot()))

    assert "not measured" in rendered
    assert "Time saved" in rendered


def test_the_daily_summary_renders_every_named_field():
    rendered = render_daily_summary(build_daily_summary(snapshot()))

    for field in (
        "Tasks completed",
        "Failures",
        "Recovered",
        "Learning",
        "Time saved",
        "TOMORROW",
    ):
        assert field in rendered


# ---- Deliverable 10: future ready ----------------------------------------


def test_the_view_model_serialises_without_a_renderer():
    """A web, desktop, or phone front-end consumes this and writes its own
    rendering. Nothing here knows a terminal exists."""
    data = as_dict(build_founder_view(with_decision()))

    assert data["status"] == WAITING_ON_YOU
    assert data["decisions"][0]["impact"] == "Deletes 14 files"
    assert data["executives"][0]["label"] == "Filesystem"
    assert data["next_step"]


def test_the_view_model_is_json_shaped():
    import json

    payload = json.dumps(as_dict(build_founder_view(with_decision())))

    assert json.loads(payload)["needs_founder"] is True


def test_the_view_is_a_pure_function_of_the_snapshot():
    """Same snapshot, same view — which is what lets a web front-end
    render exactly what the console rendered."""
    fixed = with_decision()

    assert as_dict(build_founder_view(fixed)) == as_dict(build_founder_view(fixed))


def test_the_dashboard_exposes_the_view_model_directly():
    dashboard = build_dashboard(writer=lambda _t: None)

    view = dashboard.founder_view()

    assert view.status in (WORKING, NEEDS_ATTENTION, WAITING_ON_YOU)


def test_rendering_the_founder_page_mutates_nothing():
    mc = MissionControl()
    mc.request_approval(
        PendingApproval(
            capability="Filesystem.DeleteFolder",
            local_capability="delete_folder",
            executive_id="filesystem",
            risk_tier="irreversible",
            reason="Delete Folder",
            task_id="t1",
        )
    )
    dashboard = build_dashboard(mission_control=mc, writer=lambda _t: None)

    for _ in range(20):
        dashboard.render()

    assert len(mc.approvals.open()) == 1
    assert len(mc.approvals.ledger()) == 0


# ---- charset -------------------------------------------------------------


def test_the_founder_page_renders_on_a_cp1252_console():
    """MB026's bug, twice re-learned. The founder page uses check marks
    and block bars; a Windows console cannot encode either."""
    charset = detect(io.TextIOWrapper(io.BytesIO(), encoding="cp1252"))
    frame = render_founder_frame(build_founder_view(with_decision()), charset)

    frame.encode("cp1252")


def test_a_utf8_console_gets_the_nicer_glyphs():
    charset = detect(io.TextIOWrapper(io.BytesIO(), encoding="utf-8"))

    assert charset is UNICODE
    frame = render_founder_frame(build_founder_view(snapshot()), charset)
    assert UNICODE.ok in frame or UNICODE.healthy in frame


# ---- console integration -------------------------------------------------


def console_for(mission_control, dashboard=None):
    dashboard = dashboard or build_dashboard(
        mission_control=mission_control, writer=lambda _t: None
    )
    return FounderConsole(
        dashboard,
        mission_control,
        founder="onkar",
        reader=NullKeyReader(),
        writer=lambda _t: None,
        sleep=lambda _s: None,
    )


def seeded() -> MissionControl:
    mc = MissionControl()
    mc.request_approval(
        PendingApproval(
            capability="Filesystem.DeleteFolder",
            local_capability="delete_folder",
            executive_id="filesystem",
            risk_tier="irreversible",
            reason="Delete Folder",
            task_id="t1",
            impact="Deletes 14 files",
        )
    )
    return mc


def test_v_switches_to_the_technical_page():
    mc = seeded()
    dashboard = build_dashboard(mission_control=mc, writer=lambda _t: None)
    console = console_for(mc, dashboard)

    message = console.execute("v")

    assert dashboard.page == TECHNICAL_PAGE
    assert "technical" in message


def test_v_switches_back():
    mc = seeded()
    dashboard = build_dashboard(mission_control=mc, writer=lambda _t: None)
    console = console_for(mc, dashboard)

    console.execute("v")
    console.execute("v")

    assert dashboard.page == FOUNDER_PAGE


def test_y_approves_and_n_rejects():
    mc = seeded()
    console = console_for(mc)

    console.execute("y 1")

    assert mc.approvals.ledger()[0].decision == "approved"

    mc2 = seeded()
    console_for(mc2).execute("n 1")
    assert mc2.approvals.ledger()[0].decision == "rejected"


def test_the_console_prompt_advertises_the_view_command():
    console = console_for(seeded())

    frame = console.render_once()

    assert "[V]iew details" in frame


def test_the_console_renders_the_founder_page_by_default():
    console = console_for(seeded())

    frame = console.render_once()

    assert "FOUNDER DECISIONS" in frame
    assert "SELF DEVELOPMENT" in frame


# ---- startup and shutdown ------------------------------------------------


def test_the_launcher_starts_on_the_founder_page(tmp_path):
    from master_agent.launcher.boot import build_system

    system = build_system(
        state_dir=tmp_path / "state", dashboard_kwargs={"writer": lambda _t: None}
    )

    assert system.dashboard.page == FOUNDER_PAGE


def test_a_freshly_launched_system_renders_a_complete_founder_page(tmp_path):
    from master_agent.launcher.boot import build_system

    system = build_system(
        state_dir=tmp_path / "state", dashboard_kwargs={"writer": lambda _t: None}
    )

    frame = system.dashboard.render()

    assert "KALPAVRIKSHA" in frame
    assert "STATUS" in frame
    assert "NEXT RECOMMENDED STEP" in frame


def test_a_live_system_reports_its_real_executives(tmp_path):
    from master_agent.launcher.boot import build_system

    system = build_system(
        state_dir=tmp_path / "state", dashboard_kwargs={"writer": lambda _t: None}
    )

    view = system.dashboard.founder_view()
    statuses = {e.label: e.status for e in view.executives}

    assert statuses["Filesystem"] == READY
    assert statuses["Browser"] == MISSING, "browser is not wired by the launcher yet"


def test_shutdown_produces_a_summary_from_a_real_system(tmp_path):
    from master_agent.launcher.boot import build_system

    system = build_system(
        state_dir=tmp_path / "state", dashboard_kwargs={"writer": lambda _t: None}
    )

    rendered = render_daily_summary(build_daily_summary(system.dashboard.snapshot()))

    assert "TODAY'S SUMMARY" in rendered
    assert "TOMORROW" in rendered
