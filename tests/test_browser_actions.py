"""Browser Actions unit tests -- exercises validate()/run() directly for
each of the nine Actions, with no Plugin, Orchestrator, or Permission
System involved. Mirrors test_read_actions.py's style for the filesystem
family. See BROWSER_WORKER_ARCHITECTURE.md §6.
"""
from __future__ import annotations

from master_agent.environment.browser_session import BrowserSessionManager
from master_agent.executor.actions.browser.click import ClickAction
from master_agent.executor.actions.browser.close_session import CloseBrowserSessionAction
from master_agent.executor.actions.browser.navigate import NavigateAction
from master_agent.executor.actions.browser.observe import ObserveBrowserAction
from master_agent.executor.actions.browser.open_session import OpenBrowserSessionAction
from master_agent.executor.actions.browser.press_key import PressKeyAction
from master_agent.executor.actions.browser.scroll import ScrollAction
from master_agent.executor.actions.browser.type_text import TypeTextAction
from master_agent.executor.actions.browser.wait_for_selector import WaitForSelectorAction
from tests.browser_test_support import open_sample_session

# ---- open_browser_session ----


def test_open_session_action_validate_requires_session_id():
    action = OpenBrowserSessionAction(BrowserSessionManager())
    errors = action.validate({})
    assert any("session_id" in e for e in errors)


def test_open_session_action_validate_rejects_non_bool_headless():
    action = OpenBrowserSessionAction(BrowserSessionManager())
    errors = action.validate({"session_id": "s1", "headless": "yes"})
    assert any("headless" in e for e in errors)


def test_open_session_action_run_opens_a_real_session():
    sessions = BrowserSessionManager()
    action = OpenBrowserSessionAction(sessions)
    try:
        result = action.run({"session_id": "s1"})
        assert result.success
        assert result.output["session_id"] == "s1"
        assert sessions.get("s1").is_open
    finally:
        sessions.close_all()


def test_open_session_action_run_reports_duplicate_session_as_a_clean_failure():
    sessions = BrowserSessionManager()
    action = OpenBrowserSessionAction(sessions)
    try:
        action.run({"session_id": "s1"})
        result = action.run({"session_id": "s1"})
        assert not result.success
        assert "already open" in result.errors[0]
    finally:
        sessions.close_all()


# ---- close_browser_session ----


def test_close_session_action_run_closes_a_real_session():
    sessions = BrowserSessionManager()
    sessions.open_session("s1")
    action = CloseBrowserSessionAction(sessions)
    result = action.run({"session_id": "s1"})
    assert result.success
    assert result.output["closed"] is True


def test_close_session_action_run_reports_unknown_session_as_a_clean_failure():
    action = CloseBrowserSessionAction(BrowserSessionManager())
    result = action.run({"session_id": "does-not-exist"})
    assert not result.success


# ---- navigate ----


def test_navigate_action_validate_requires_url_and_session_id():
    action = NavigateAction(BrowserSessionManager())
    errors = action.validate({})
    assert any("session_id" in e for e in errors)
    assert any("url" in e for e in errors)


def test_navigate_action_run_navigates_and_reports_url_and_title():
    sessions = BrowserSessionManager()
    open_sample_session(sessions)
    action = NavigateAction(sessions)
    try:
        result = action.run({"session_id": "s1", "url": "about:blank"})
        assert result.success
        assert result.output["url"] == "about:blank"
    finally:
        sessions.close_all()


def test_navigate_action_run_reports_unknown_session_as_a_clean_failure():
    action = NavigateAction(BrowserSessionManager())
    result = action.run({"session_id": "does-not-exist", "url": "about:blank"})
    assert not result.success


# ---- click ----


def test_click_action_run_clicks_a_real_element():
    sessions = BrowserSessionManager()
    open_sample_session(sessions)
    action = ClickAction(sessions)
    try:
        result = action.run({"session_id": "s1", "selector": "#btn"})
        assert result.success
        assert result.output["clicked"] is True
    finally:
        sessions.close_all()


def test_click_action_run_reports_a_mechanical_timeout_for_a_missing_element():
    sessions = BrowserSessionManager()
    open_sample_session(sessions)
    action = ClickAction(sessions)
    try:
        result = action.run({"session_id": "s1", "selector": "#does-not-exist", "timeout_ms": 200})
        assert not result.success
        assert "click" in result.errors[0]
    finally:
        sessions.close_all()


# ---- type_text ----


def test_type_text_action_run_fills_a_real_input():
    sessions = BrowserSessionManager()
    open_sample_session(sessions)
    action = TypeTextAction(sessions)
    try:
        result = action.run({"session_id": "s1", "selector": "#box", "text": "hello"})
        assert result.success
        value = sessions.get("s1").page.locator("#box").input_value()
        assert value == "hello"
    finally:
        sessions.close_all()


def test_type_text_action_validate_rejects_non_string_text():
    action = TypeTextAction(BrowserSessionManager())
    errors = action.validate({"session_id": "s1", "selector": "#box", "text": 123})
    assert any("text" in e for e in errors)


# ---- press_key ----


def test_press_key_action_run_sends_a_key_to_the_page():
    sessions = BrowserSessionManager()
    open_sample_session(sessions)
    action = PressKeyAction(sessions)
    try:
        result = action.run({"session_id": "s1", "key": "Tab"})
        assert result.success
        assert result.output["key"] == "Tab"
    finally:
        sessions.close_all()


def test_press_key_action_run_sends_a_key_to_a_specific_element():
    sessions = BrowserSessionManager()
    open_sample_session(sessions)
    action = PressKeyAction(sessions)
    try:
        result = action.run({"session_id": "s1", "key": "A", "selector": "#box"})
        assert result.success
        value = sessions.get("s1").page.locator("#box").input_value()
        assert value == "A"
    finally:
        sessions.close_all()


# ---- scroll ----


def test_scroll_action_validate_requires_selector_or_delta():
    action = ScrollAction(BrowserSessionManager())
    errors = action.validate({"session_id": "s1"})
    assert any("selector" in e for e in errors)


def test_scroll_action_run_scrolls_to_an_element():
    sessions = BrowserSessionManager()
    open_sample_session(sessions)
    action = ScrollAction(sessions)
    try:
        result = action.run({"session_id": "s1", "selector": "#heading"})
        assert result.success
    finally:
        sessions.close_all()


def test_scroll_action_run_scrolls_by_delta():
    sessions = BrowserSessionManager()
    open_sample_session(sessions)
    action = ScrollAction(sessions)
    try:
        result = action.run({"session_id": "s1", "delta_x": 0, "delta_y": 100})
        assert result.success
    finally:
        sessions.close_all()


# ---- wait_for_selector ----


def test_wait_for_selector_action_run_succeeds_for_a_visible_element():
    sessions = BrowserSessionManager()
    open_sample_session(sessions)
    action = WaitForSelectorAction(sessions)
    try:
        result = action.run({"session_id": "s1", "selector": "#heading"})
        assert result.success
    finally:
        sessions.close_all()


def test_wait_for_selector_action_run_times_out_mechanically_for_a_missing_element():
    sessions = BrowserSessionManager()
    open_sample_session(sessions)
    action = WaitForSelectorAction(sessions)
    try:
        result = action.run({"session_id": "s1", "selector": "#does-not-exist", "timeout_ms": 200})
        assert not result.success
        assert "timed out" in result.errors[0] or "wait_for_selector" in result.errors[0]
    finally:
        sessions.close_all()


def test_wait_for_selector_action_validate_rejects_unknown_state():
    action = WaitForSelectorAction(BrowserSessionManager())
    errors = action.validate({"session_id": "s1", "selector": "#x", "state": "not_a_real_state"})
    assert any("state" in e for e in errors)


# ---- observe_browser ----


def test_observe_browser_action_run_returns_a_generic_observation():
    sessions = BrowserSessionManager()
    open_sample_session(sessions)
    action = ObserveBrowserAction(sessions)
    try:
        result = action.run({"session_id": "s1", "selectors": ["#heading"]})
        assert result.success
        assert result.output["title"] == "Sample Test Page"
        assert result.output["elements"][0]["text"] == "Hello"
    finally:
        sessions.close_all()


def test_observe_browser_action_validate_rejects_non_list_selectors():
    action = ObserveBrowserAction(BrowserSessionManager())
    errors = action.validate({"session_id": "s1", "selectors": "not-a-list"})
    assert any("selectors" in e for e in errors)


def test_observe_browser_action_validate_rejects_non_bool_observation_flags():
    action = ObserveBrowserAction(BrowserSessionManager())
    errors = action.validate({"session_id": "s1", "include_accessibility_tree": "yes"})
    assert any("include_accessibility_tree" in e for e in errors)


def test_observe_browser_action_exposes_accessibility_tree_and_available_actions():
    """The two page-sized observation facets Mission Brief 022 named must
    be reachable as capability payload options, not just as library-level
    parameters."""
    sessions = BrowserSessionManager()
    open_sample_session(sessions)
    action = ObserveBrowserAction(sessions)
    try:
        result = action.run(
            {
                "session_id": "s1",
                "include_accessibility_tree": True,
                "include_available_actions": True,
            }
        )
        assert result.success
        assert isinstance(result.output["accessibility_tree"], str)
        assert result.output["available_actions"]
    finally:
        sessions.close_all()
