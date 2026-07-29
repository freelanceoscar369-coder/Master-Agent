"""BrowserVerifier — the first concrete Verifier (verification/verifier.py).
See BROWSER_WORKER_ARCHITECTURE.md §8. Implements exactly one method;
everything else (building Evidence, computing the Verdict) is inherited,
unchanged, from the generic base.
"""
from __future__ import annotations

from typing import Any

from master_agent.environment.browser_session import BrowserSessionManager
from master_agent.plugins.browser_observation import normalize_observation
from master_agent.verification.verifier import Verifier


class BrowserVerifier(Verifier):
    worker_name = "browser"
    environment_name = "browser_environment"

    def __init__(
        self,
        sessions: BrowserSessionManager,
        session_id: str,
        selectors: list[str] | None = None,
        include_accessibility_tree: bool = False,
        include_available_actions: bool = False,
    ) -> None:
        self._sessions = sessions
        self._session_id = session_id
        self._selectors = selectors or []
        self._include_accessibility_tree = include_accessibility_tree
        self._include_available_actions = include_available_actions

    def capture_observation_dict(self) -> dict[str, Any]:
        # Always resolves the session and re-reads the page fresh at the
        # moment verify() is called -- never a cached Observation from
        # whenever the Action ran. This is what keeps Verification
        # structurally independent of Execution (ADR-0011).
        session = self._sessions.get(self._session_id)
        observation = normalize_observation(
            session.page,
            self._selectors,
            include_accessibility_tree=self._include_accessibility_tree,
            include_available_actions=self._include_available_actions,
        )
        return observation.as_dict()
