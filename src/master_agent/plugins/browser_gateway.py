"""BrowserGateway -- pairs BrowserWorker with the ExecutiveGateway protocol.

The production counterpart of the gateway that has existed in
`tests/runtime_test_support.py` since MB022. That test double already
proved the composition pattern; the Founder Edition was still registering
the generic `PluginGateway`, whose `verify()` returns `None`
unconditionally, so no browser step in the packaged app could ever produce
Evidence.

It lives beside the browser plugin, not in `runtime/`, precisely so the
Runtime stays ignorant of Executives: the Runtime asks for verification
and consumes Evidence, and never learns what a browser is.

Verification here does not read the Worker's report. `CloseBrowserSession`
returning `{"closed": true}` is the Worker's claim about its own work, and
ADR-0011 exists so completion does not rest on a claim like that.
"""
from __future__ import annotations

from typing import Any

from master_agent.permissions.permission_system import GrantScope, PermissionSystem
from master_agent.runtime.gateway import GatewayResult
from master_agent.verification.evidence import Evidence, ExpectedOutcome


class BrowserGateway:
    """Pairs BrowserWorker with the ExecutiveGateway protocol."""

    def __init__(
        self,
        worker: Any,
        permissions: PermissionSystem,
        executor_name: str,
    ) -> None:
        self._worker = worker
        self._permissions = permissions
        self._executor_name = executor_name
        self._last_evidence: Evidence | None = None

    def _approve(self, capability: str) -> None:
        # Relayed to the Executor's own grant key -- the ADR-0005 pattern,
        # identical to FilesystemGateway.
        self._permissions.grant(self._executor_name, capability, GrantScope.ONCE)

    def invoke(self, capability: str, payload: dict[str, Any]) -> GatewayResult:
        self._approve(capability)
        report = self._worker.run_step(capability, payload, requested_by="runtime_engine")
        self._last_evidence = report.evidence
        if report.execution.success:
            return GatewayResult(success=True, output=report.execution.output)
        return GatewayResult(success=False, errors=list(report.execution.errors))

    def verify(
        self,
        capability: str,
        payload: dict[str, Any],
        expected: ExpectedOutcome,
    ) -> Evidence | None:
        from master_agent.plugins.browser_expectations import (
            PAGE,
            SESSION,
            bind_for_environment,
            subject,
        )

        # The Planner's `expected` states WHAT this step is for; its checks
        # are text-shaped because the Planner does not know what a browser
        # observation looks like and must not learn. This package does.
        effective = bind_for_environment(
            capability=capability,
            payload=payload,
            description=expected.description,
        )
        if effective is None:
            # No domain expectation can be stated for this capability yet
            # (Click, TypeText, Scroll, PressKey, WaitForSelector). Saying
            # so truthfully means the step cannot claim completion under
            # the fail-closed runtime -- far better than falling back to
            # the Planner's text checks, which would fail a correct step,
            # or inventing a pass.
            return None

        sessions = getattr(self._worker, "_sessions", None)
        if sessions is None:
            return None

        session_id = str(payload.get("session_id") or "")

        if subject(capability) == SESSION:
            from master_agent.plugins.browser_session_verifier import (
                BrowserSessionVerifier,
            )

            # Observes the session registry, so a session that is correctly
            # GONE reads as `session_exists == False` rather than as a
            # failure to observe a page that no longer exists.
            return BrowserSessionVerifier(sessions, session_id).verify(effective)

        if subject(capability) == PAGE:
            from master_agent.plugins.browser_verifier import BrowserVerifier

            # Text only where the step exists to read text. Every
            # Evidence record pays for what it carries, and a Navigate
            # does not need the page's prose to prove it arrived.
            from master_agent.plugins.browser_expectations import _local

            return BrowserVerifier(
                sessions, session_id, payload.get("selectors"),
                include_text=_local(capability) == "readpagetext",
            ).verify(effective)

        return None
