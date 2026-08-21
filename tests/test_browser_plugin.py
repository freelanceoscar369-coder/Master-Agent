"""Unit tests for BrowserPlugin as a thin Plugin-contract adapter over
LocalExecutor -- mirrors test_filesystem_plugin.py's coverage exactly:
manifest shape, delegation, error-shape translation, and the permission-
grant relay to the Executor's own gate (docs/adr/0005-executor-permission-relay.md).
"""
from __future__ import annotations

from master_agent.plugins.base import PermissionCategory, RiskTier
from master_agent.executor.actions.browser.read_page_text import READ_PAGE_TEXT
from master_agent.plugins.browser_plugin import (
    CLICK,
    CLOSE_BROWSER_SESSION,
    NAVIGATE,
    OBSERVE_BROWSER,
    OPEN_BROWSER_SESSION,
    PRESS_KEY,
    SCROLL,
    TYPE_TEXT,
    WAIT_FOR_SELECTOR,
    BrowserPlugin,
)
from tests.browser_test_support import make_executor_and_sessions


def make_plugin():
    executor, sessions = make_executor_and_sessions()
    return BrowserPlugin(executor, sessions), executor, sessions


def test_manifest_declares_all_ten_capabilities():
    """Ten, not nine: `read_page_text` joined the Browser Executive after
    this was written. The set is asserted rather than the count alone, so
    a capability arriving unnoticed on the founder-facing Executive fails
    here rather than being discovered in a mission."""
    plugin, _, _ = make_plugin()
    names = {cap.name for cap in plugin.manifest.capabilities}
    assert names == {
        OPEN_BROWSER_SESSION,
        CLOSE_BROWSER_SESSION,
        NAVIGATE,
        CLICK,
        TYPE_TEXT,
        PRESS_KEY,
        SCROLL,
        WAIT_FOR_SELECTOR,
        OBSERVE_BROWSER,
        READ_PAGE_TEXT,
    }


def test_manifest_declares_honest_risk_tiers():
    plugin, _, _ = make_plugin()
    by_name = {cap.name: cap for cap in plugin.manifest.capabilities}
    assert by_name[OPEN_BROWSER_SESSION].risk_tier == RiskTier.REVERSIBLE_WRITE
    assert by_name[OPEN_BROWSER_SESSION].permission_category == PermissionCategory.SYSTEM
    assert by_name[OBSERVE_BROWSER].risk_tier == RiskTier.READ_ONLY
    assert by_name[WAIT_FOR_SELECTOR].risk_tier == RiskTier.READ_ONLY
    assert by_name[TYPE_TEXT].permission_category == PermissionCategory.WRITE
    # None of the nine are IRREVERSIBLE -- every browser effect is undone
    # by closing the session (BROWSER_WORKER_ARCHITECTURE.md §6).
    assert all(cap.risk_tier != RiskTier.IRREVERSIBLE for cap in plugin.manifest.capabilities)


def test_invoke_delegates_to_executor_and_relays_permission():
    plugin, _executor, sessions = make_plugin()
    try:
        result = plugin.invoke(OPEN_BROWSER_SESSION, {"session_id": "s1"})
        assert result.success
        assert result.output["session_id"] == "s1"
        assert sessions.get("s1").is_open
    finally:
        sessions.close_all()


def test_invoke_unsupported_capability_is_a_clean_error():
    plugin, _, _ = make_plugin()
    result = plugin.invoke("not_a_real_capability", {})
    assert not result.success
    assert "unsupported capability" in result.error


def test_invoke_translates_executor_failure_into_invocation_result():
    plugin, _executor, _sessions = make_plugin()
    # close_browser_session on a session that was never opened -- a clean,
    # expected failure path, not a crash.
    result = plugin.invoke(CLOSE_BROWSER_SESSION, {"session_id": "never-opened"})
    assert not result.success
    assert result.error


def test_invoke_does_not_ask_twice_for_the_same_mission():
    """The Orchestrator's own check already approved this call once; the
    relay must consume exactly the grant it creates, not accumulate a
    standing approval. Reflected here by two invoke() calls each getting
    their own successful relay, never colliding with each other's grant."""
    plugin, _executor, sessions = make_plugin()
    try:
        r1 = plugin.invoke(OPEN_BROWSER_SESSION, {"session_id": "s1"})
        r2 = plugin.invoke(OPEN_BROWSER_SESSION, {"session_id": "s2"})
        assert r1.success and r2.success
    finally:
        sessions.close_all()
