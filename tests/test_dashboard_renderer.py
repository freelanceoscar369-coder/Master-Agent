"""Frame composition — the whole rendering contract is one function."""
from __future__ import annotations

from master_agent.dashboard.charset import ASCII, UNICODE
from master_agent.dashboard.panels import WIDTH
from master_agent.dashboard.renderer import CLEAR_SCREEN, render_frame
from tests.dashboard_test_support import empty_snapshot, full_snapshot


def frame(**kwargs) -> str:
    kwargs.setdefault("charset", ASCII)
    return render_frame(full_snapshot(), **kwargs)


def test_the_frame_contains_every_panel():
    text = frame()
    for heading in (
        "RUNTIME",
        "MISSION",
        "EXECUTIVES",
        "CAPABILITIES",
        "AUDIT",
        "PERSISTENCE",
        "SYSTEM HEALTH",
        "FOUNDER STATE",
    ):
        assert heading in text


def test_the_frame_opens_with_the_product_header():
    lines = frame().splitlines()
    assert set(lines[0]) == {ASCII.rule}
    assert "KALPAVRIKSHA" in lines[1]


def test_panel_order_puts_what_is_happening_now_first():
    """A founder glancing at the top should see whether it is working."""
    text = frame()
    assert text.index("RUNTIME") < text.index("MISSION") < text.index("EXECUTIVES")
    assert text.index("EXECUTIVES") < text.index("AUDIT")
    assert text.index("AUDIT") < text.index("SYSTEM HEALTH")


def test_founder_state_can_be_omitted():
    assert "FOUNDER STATE" not in frame(include_founder_state=False)


def test_the_audit_limit_is_honoured_in_the_frame():
    from tests.dashboard_test_support import audit_data

    text = render_frame(
        full_snapshot(audit=audit_data(rows=30)), audit_limit=3, charset=ASCII
    )
    assert text.count("task_completed") == 3


def test_the_frame_ends_with_a_full_rule():
    lines = frame().splitlines()
    assert set(lines[-1]) == {ASCII.rule}


def test_no_line_exceeds_a_sane_terminal_width():
    for line in frame().splitlines():
        assert len(line) <= 80, f"line too wide: {line!r}"


def test_rules_are_exactly_the_frame_width():
    for line in frame().splitlines():
        if set(line) in ({ASCII.rule}, {ASCII.sub_rule}):
            assert len(line) == WIDTH


def test_a_completely_unwired_system_still_renders_a_full_frame():
    """MB026 Rule 3, at frame level: status everywhere, never a blank
    screen and never a fabricated value."""
    text = render_frame(empty_snapshot(), charset=ASCII)
    for heading in ("RUNTIME", "MISSION", "EXECUTIVES", "AUDIT", "PERSISTENCE"):
        assert heading in text
    assert text.count("not attached") >= 7


def test_an_unwired_frame_contains_no_fabricated_numbers():
    text = render_frame(empty_snapshot(), charset=ASCII)
    assert "0%" not in text
    assert "IDLE" not in text


def test_the_frame_is_a_single_string_not_a_side_effect():
    """Rendering returns text; printing is somebody else's decision."""
    assert isinstance(frame(), str)


def test_ascii_rendering_is_encodable_on_a_legacy_console():
    """The portability defect the first smoke run found."""
    render_frame(full_snapshot(), charset=ASCII).encode("cp1252")


def test_unicode_rendering_uses_the_nicer_glyphs():
    text = render_frame(full_snapshot(), charset=UNICODE)
    assert UNICODE.rule in text
    assert UNICODE.bar_full in text


def test_clear_screen_sequence_is_available_but_not_embedded_in_the_frame():
    """A caller decides whether to clear; the frame itself stays clean so
    it can be logged or asserted on."""
    assert CLEAR_SCREEN not in frame()
    assert CLEAR_SCREEN.startswith("\033")


def test_rendering_is_deterministic_for_a_fixed_snapshot():
    snapshot = full_snapshot()
    assert render_frame(snapshot, charset=ASCII) == render_frame(snapshot, charset=ASCII)
