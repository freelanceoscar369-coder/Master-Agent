"""BrowserSession / BrowserSessionManager unit tests -- the Environment
Session Manager (KALPAVRIKSHA_VISION_V2.md §8.3). See
BROWSER_WORKER_ARCHITECTURE.md §4.

BrowserSession is only ever constructed by BrowserSessionManager (one
shared Playwright driver + Browser process per manager, multiplexed across
sessions as separate BrowserContexts) -- these tests exercise it that way,
the same way real callers do.
"""
from __future__ import annotations

import pytest

from master_agent.environment.browser_session import BrowserSessionError, BrowserSessionManager


def test_session_is_open_immediately_after_the_manager_opens_it():
    manager = BrowserSessionManager()
    manager.open_session("s1")
    try:
        session = manager.get("s1")
        assert session.is_open is True
        assert session.page is not None
    finally:
        manager.close_all()


def test_session_page_raises_a_structured_error_once_closed():
    manager = BrowserSessionManager()
    manager.open_session("s1")
    session = manager.get("s1")
    manager.close_session("s1")
    assert session.is_open is False
    with pytest.raises(BrowserSessionError):
        _ = session.page


def test_manager_open_get_close_lifecycle():
    manager = BrowserSessionManager()
    handle = manager.open_session("s1")
    assert handle.session_id == "s1"
    assert handle.headless is True

    session = manager.get("s1")
    assert session.is_open is True

    warnings = manager.close_session("s1")
    assert warnings == []
    with pytest.raises(BrowserSessionError):
        manager.get("s1")


def test_manager_rejects_duplicate_session_id():
    manager = BrowserSessionManager()
    manager.open_session("s1")
    try:
        with pytest.raises(BrowserSessionError):
            manager.open_session("s1")
    finally:
        manager.close_all()


def test_manager_get_unknown_session_is_a_structured_error_not_a_crash():
    manager = BrowserSessionManager()
    with pytest.raises(BrowserSessionError):
        manager.get("does-not-exist")


def test_manager_supports_multiple_concurrent_sessions_on_one_shared_browser():
    """Regression guard: each session must be its own BrowserContext on one
    shared Playwright driver/Browser -- not one independent Playwright
    driver per session, which Playwright's sync API does not support
    within a single thread."""
    manager = BrowserSessionManager()
    manager.open_session("s1")
    manager.open_session("s2")
    try:
        assert manager.get("s1").is_open
        assert manager.get("s2").is_open
        assert manager.get("s1") is not manager.get("s2")
    finally:
        manager.close_all()


def test_manager_list_sessions_reflects_open_sessions_only():
    manager = BrowserSessionManager()
    assert manager.list_sessions() == []
    manager.open_session("s1")
    manager.open_session("s2")
    try:
        ids = {handle.session_id for handle in manager.list_sessions()}
        assert ids == {"s1", "s2"}
    finally:
        manager.close_all()
    assert manager.list_sessions() == []


def test_manager_close_all_is_best_effort_and_never_raises():
    manager = BrowserSessionManager()
    manager.open_session("s1")
    manager.open_session("s2")
    warnings = manager.close_all()
    assert set(warnings) == {"s1", "s2"}
    assert manager.list_sessions() == []


def test_manager_can_reopen_a_new_browser_after_closing_all_sessions():
    """Closing the last session tears down the shared Browser/Playwright
    driver; a later open_session() must be able to start a fresh one."""
    manager = BrowserSessionManager()
    manager.open_session("s1")
    manager.close_session("s1")
    manager.open_session("s2")
    try:
        assert manager.get("s2").is_open
    finally:
        manager.close_all()
