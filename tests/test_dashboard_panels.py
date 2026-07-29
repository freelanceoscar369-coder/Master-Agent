"""UI rendering tests — every panel, present and absent (MB026 Rule 3).

Pure: not one of these needs a Runtime, a Mission Control, or a browser,
because panels render from plain data (ADR-0016 Decision 1).
"""
from __future__ import annotations

import pytest

from master_agent.dashboard.charset import ASCII, UNICODE
from master_agent.dashboard.panels import (
    WIDTH,
    format_duration,
    format_timestamp,
    progress_bar,
    render_audit,
    render_capabilities,
    render_executives,
    render_founder_state,
    render_header,
    render_mission,
    render_persistence,
    render_runtime,
    render_system_health,
    rule,
    value,
)
from master_agent.dashboard.readmodel import (
    AuditPanelData,
    CapabilityPanelData,
    ExecutivePanelData,
    ExecutiveRow,
    FounderStatePanelData,
    MissionPanelData,
    PanelStatus,
    PersistencePanelData,
    RuntimePanelData,
    SystemHealthPanelData,
)
from tests.dashboard_test_support import (
    FIXED_NOW,
    audit_data,
    capability_data,
    executive_data,
    full_snapshot,
    mission_data,
    persistence_data,
    runtime_data,
    system_health_data,
)

MISSING = PanelStatus.missing("not attached")


# ---- primitives ---------------------------------------------------------


def test_rule_is_exactly_the_frame_width():
    assert len(rule(charset=ASCII)) == WIDTH


def test_value_renders_none_as_the_charset_marker():
    assert value(None, ASCII) == ASCII.unavailable
    assert value(None, UNICODE) == UNICODE.unavailable


def test_value_never_renders_the_literal_string_none():
    assert value(None, ASCII) != "None"


def test_value_renders_booleans_readably():
    assert value(True, ASCII) == "yes"
    assert value(False, ASCII) == "no"


def test_value_renders_zero_as_zero_not_as_missing():
    """`0` and "unknown" are different facts (ADR-0016 Decision 2)."""
    assert value(0, ASCII) == "0"


@pytest.mark.parametrize(
    "seconds,expected", [(0, "0s"), (45, "45s"), (90, "1m 30s"), (3700, "1h 1m")]
)
def test_duration_formatting(seconds, expected):
    assert format_duration(seconds, ASCII) == expected


def test_duration_of_none_is_the_missing_marker():
    assert format_duration(None, ASCII) == ASCII.unavailable


def test_timestamp_formatting_and_absence():
    assert format_timestamp(FIXED_NOW, ASCII) == "12:00:00"
    assert format_timestamp(None, ASCII) == ASCII.unavailable


@pytest.mark.parametrize(
    "progress,filled", [(0.0, 0), (0.25, 4), (0.5, 8), (1.0, 16)]
)
def test_progress_bar_fills_proportionally(progress, filled):
    bar = progress_bar(progress, charset=ASCII)
    assert bar.count(ASCII.bar_full) == filled
    assert len(bar) == 16


def test_progress_bar_for_unknown_progress_is_empty_not_zero_percent():
    """An unreadable mission must not look like a mission sitting at 0%."""
    assert progress_bar(None, charset=ASCII) == ASCII.bar_empty * 16


def test_progress_bar_clamps_out_of_range_values():
    assert len(progress_bar(5.0, charset=ASCII)) == 16
    assert len(progress_bar(-1.0, charset=ASCII)) == 16


# ---- runtime panel ------------------------------------------------------


def test_runtime_panel_shows_all_six_required_fields():
    lines = "\n".join(render_runtime(runtime_data(), ASCII))
    for label in (
        "State",
        "Uptime",
        "Active Cycle",
        "Queue Length",
        "Last Dispatch",
        "Last Verification",
    ):
        assert label in lines


def test_runtime_panel_reports_unavailability_with_a_reason():
    lines = render_runtime(RuntimePanelData(status=MISSING), ASCII)
    assert "RUNTIME" in lines[0]
    assert "not attached" in lines[1]


def test_runtime_panel_never_invents_a_state():
    lines = "\n".join(render_runtime(RuntimePanelData(status=MISSING), ASCII))
    assert "IDLE" not in lines
    assert "RUNNING" not in lines


def test_runtime_panel_distinguishes_zero_queue_from_unknown_queue():
    zero = "\n".join(render_runtime(runtime_data(queue_length=0), ASCII))
    unknown = "\n".join(render_runtime(runtime_data(queue_length=None), ASCII))
    assert "Queue Length      0" in zero
    assert f"Queue Length      {ASCII.unavailable}" in unknown


# ---- mission panel ------------------------------------------------------


def test_mission_panel_shows_all_required_fields():
    lines = "\n".join(render_mission(mission_data(), ASCII))
    for label in ("Progress", "Status", "Active Executive", "Capability", "ETA"):
        assert label in lines
    assert "Increase Founder Net Worth" in lines


def test_mission_panel_renders_a_progress_bar_and_percentage():
    lines = "\n".join(render_mission(mission_data(progress=0.5), ASCII))
    assert "50%" in lines
    assert ASCII.bar_full in lines


def test_mission_panel_with_no_objective_says_so():
    lines = "\n".join(render_mission(mission_data(objective=None), ASCII))
    assert "no objective in flight" in lines


def test_mission_panel_shows_an_absent_eta_without_inventing_one():
    lines = "\n".join(render_mission(mission_data(eta_seconds=None), ASCII))
    assert f"ETA               {ASCII.unavailable}" in lines


def test_mission_panel_surfaces_errors():
    lines = "\n".join(render_mission(mission_data(errors=["disk on fire"]), ASCII))
    assert "Errors" in lines
    assert "disk on fire" in lines


def test_mission_panel_caps_the_error_list():
    data = mission_data(errors=[f"error {index}" for index in range(10)])
    lines = "\n".join(render_mission(data, ASCII))
    assert lines.count(ASCII.warning) <= 3


def test_mission_panel_unavailable_state():
    lines = render_mission(MissionPanelData(status=MISSING), ASCII)
    assert "not attached" in lines[1]


# ---- executive panel ----------------------------------------------------


def test_executive_panel_lists_every_executive_with_required_columns():
    lines = "\n".join(render_executives(executive_data(count=2), ASCII))
    for label in ("NAME", "HEALTH", "STATUS", "VER", "CAPS"):
        assert label in lines
    assert "exec0" in lines
    assert "exec1" in lines


def test_executive_panel_with_none_registered():
    lines = "\n".join(render_executives(ExecutivePanelData(), ASCII))
    assert "none registered" in lines


def test_executive_panel_unavailable_state():
    lines = render_executives(ExecutivePanelData(status=MISSING), ASCII)
    assert "not attached" in lines[1]


def test_executive_panel_truncates_long_names_without_breaking_layout():
    row = ExecutiveRow(
        executive_id="a" * 50,
        health="healthy",
        version="1.0.0",
        state="ready",
        capability_count=1,
    )
    lines = render_executives(ExecutivePanelData(executives=[row]), ASCII)
    assert all(len(line) < 90 for line in lines)


# ---- capability panel ---------------------------------------------------


def test_capability_panel_shows_registered_pending_active_completed():
    lines = "\n".join(render_capabilities(capability_data(), ASCII))
    for label in ("Registered", "Pending", "Active", "Completed"):
        assert label in lines


def test_capability_panel_hides_blocked_and_failed_when_zero():
    lines = "\n".join(render_capabilities(capability_data(blocked=0, failed=0), ASCII))
    assert "Blocked" not in lines
    assert "Failed" not in lines


def test_capability_panel_shows_blocked_and_failed_when_present():
    lines = "\n".join(render_capabilities(capability_data(blocked=2, failed=1), ASCII))
    assert "Blocked" in lines
    assert "Failed" in lines


def test_capability_panel_unavailable_state():
    lines = render_capabilities(CapabilityPanelData(status=MISSING), ASCII)
    assert "not attached" in lines[1]


# ---- audit panel --------------------------------------------------------


def test_audit_panel_lists_recent_events_with_totals():
    lines = "\n".join(render_audit(audit_data(rows=3), charset=ASCII))
    assert "AUDIT" in lines
    assert "3 events" in lines
    assert "task_completed" in lines


def test_audit_panel_supports_a_scroll_window():
    """Deliverable 6 asks for scrolling; the limit is the window."""
    data = audit_data(rows=30)
    lines = render_audit(data, limit=5, charset=ASCII)
    assert len(lines) == 6  # header + 5 rows


def test_audit_panel_shows_the_most_recent_events_not_the_oldest():
    data = audit_data(rows=10)
    lines = render_audit(data, limit=2, charset=ASCII)
    assert "    9" in "\n".join(lines)


def test_audit_panel_marks_failures():
    rows = audit_data(rows=1).recent
    failing = [
        type(rows[0])(
            sequence=1,
            event_type="task_failed",
            occurred_at=FIXED_NOW,
            source="runtime_engine",
            task_id="t1",
            capability=None,
            error="boom",
        )
    ]
    lines = "\n".join(render_audit(AuditPanelData(recent=failing, total_entries=1, failures=1), charset=ASCII))
    assert ASCII.warning in lines


def test_audit_panel_with_no_events():
    lines = "\n".join(render_audit(AuditPanelData(), charset=ASCII))
    assert "no events recorded yet" in lines


def test_audit_panel_unavailable_state():
    lines = render_audit(AuditPanelData(status=MISSING), charset=ASCII)
    assert "not attached" in lines[1]


# ---- persistence panel --------------------------------------------------


def test_persistence_panel_shows_all_four_required_fields():
    lines = "\n".join(render_persistence(persistence_data(), ASCII))
    for label in ("Last Checkpoint", "Snapshot Version", "Event Log Size", "Recovery"):
        assert label in lines


def test_persistence_panel_shows_recovery_source_when_present():
    lines = "\n".join(render_persistence(persistence_data(recovery_source="snapshot"), ASCII))
    assert "(snapshot)" in lines


def test_persistence_panel_with_nothing_persisted_yet():
    data = persistence_data(
        last_checkpoint_at=None,
        snapshot_schema_version=None,
        event_log_size=None,
        recovery_status=None,
        recovery_source=None,
    )
    lines = "\n".join(render_persistence(data, ASCII))
    assert lines.count(ASCII.unavailable) >= 4


def test_persistence_panel_unavailable_state():
    lines = render_persistence(PersistencePanelData(status=MISSING), ASCII)
    assert "not attached" in lines[1]


# ---- system health panel ------------------------------------------------


def test_system_health_panel_shows_all_five_required_fields():
    lines = "\n".join(render_system_health(system_health_data(), ASCII))
    for label in ("Executives Online", "Runtime", "Queue", "Audit", "Persistence"):
        assert label in lines


def test_system_health_panel_renders_unknown_without_inventing_health():
    data = system_health_data(runtime_health="unknown", queue_health="unknown")
    lines = "\n".join(render_system_health(data, ASCII))
    assert "unknown" in lines
    assert "healthy" in lines  # the others are still reported


def test_system_health_panel_unavailable_state():
    lines = render_system_health(SystemHealthPanelData(status=MISSING), ASCII)
    assert "not attached" in lines[1]


# ---- founder state panel ------------------------------------------------


def test_founder_state_panel_renders_published_keys_verbatim():
    """MB026: display exactly as exposed; do not derive independently."""
    data = FounderStatePanelData(state={"current_mission": "X", "progress": 0.25})
    lines = "\n".join(render_founder_state(data, ASCII))
    assert "current_mission" in lines
    assert "progress" in lines
    assert "0.25" in lines


def test_founder_state_panel_renders_a_future_field_with_no_code_change():
    data = FounderStatePanelData(state={"a_field_invented_later": "value"})
    lines = "\n".join(render_founder_state(data, ASCII))
    assert "a_field_invented_later" in lines


def test_founder_state_panel_truncates_very_long_values():
    data = FounderStatePanelData(state={"k": "v" * 200})
    lines = render_founder_state(data, ASCII)
    assert all(len(line) < 80 for line in lines)


def test_founder_state_panel_when_not_published():
    lines = "\n".join(render_founder_state(FounderStatePanelData(state=None), ASCII))
    assert "not published" in lines


def test_founder_state_panel_unavailable_state():
    lines = render_founder_state(FounderStatePanelData(status=MISSING), ASCII)
    assert "not attached" in lines[1]


# ---- header -------------------------------------------------------------


def test_header_names_the_product_and_the_capture_time():
    lines = render_header(full_snapshot(), ASCII)
    joined = "\n".join(lines)
    assert "KALPAVRIKSHA" in joined
    assert "FOUNDER EDITION" in joined
    assert "12:00:00" in joined


# ---- charset ------------------------------------------------------------


def test_ascii_charset_produces_pure_ascii_output():
    """The portability bug that crashed the first smoke run: a cp1252
    console cannot encode box-drawing glyphs."""
    lines = render_runtime(runtime_data(), ASCII) + render_mission(mission_data(), ASCII)
    joined = "\n".join(lines)
    joined.encode("ascii")  # must not raise


def test_unicode_charset_uses_box_drawing_glyphs():
    assert UNICODE.bar_full in progress_bar(1.0, charset=UNICODE)
