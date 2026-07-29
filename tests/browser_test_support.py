"""Shared test fixtures for the Browser Worker test suite (not itself a
test module — no test_* functions live here, so pytest does not collect
it). Every page used across these tests is generated locally via
page.set_content() — no navigation to any real website, network access,
or named product, per Mission Brief 022's product-independence rule.
"""
from __future__ import annotations

from master_agent.environment.browser_session import BrowserSessionManager
from master_agent.executor.executor import LocalExecutor
from master_agent.permissions.permission_system import GrantScope, PermissionSystem

SAMPLE_HTML = """
<html>
<head><title>Sample Test Page</title></head>
<body>
  <h1 id="heading">Hello</h1>
  <button id="btn">Click me</button>
  <button id="disabled-btn" disabled>Disabled</button>
  <input id="box" />
  <a id="visible-link" href="#somewhere">Go somewhere</a>
  <a id="missing-link" style="display:none">Hidden</a>
</body>
</html>
"""


def make_executor_and_sessions():
    executor = LocalExecutor(PermissionSystem())
    sessions = BrowserSessionManager()
    return executor, sessions


def grant_once(executor: LocalExecutor, capability: str) -> None:
    executor.permissions.grant(executor.name, capability, GrantScope.ONCE)


def open_sample_session(sessions: BrowserSessionManager, session_id: str = "s1"):
    """Opens a session directly through the manager (bypassing the Action/
    Executor/Permission layers, which is the point for tests that only
    want a live page to act against) and loads SAMPLE_HTML into it."""
    sessions.open_session(session_id)
    session = sessions.get(session_id)
    session.page.set_content(SAMPLE_HTML)
    return session
