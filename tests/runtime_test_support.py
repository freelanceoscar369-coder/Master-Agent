"""Shared fixtures for the Runtime Engine suite (not itself a test module).

Note where the browser-aware gateway lives: **here, in test support** --
not in `runtime/`. That is the point of Mission Brief 024's Rule 2. The
Runtime package knows no Executive; assembling a specific Executive into
a gateway is founder-wiring, and this file plays the founder.
"""
from __future__ import annotations

from typing import Any

from master_agent.mission_control.adapters import discover_executives
from master_agent.mission_control.mission_control import MissionControl
from master_agent.permissions.permission_system import GrantScope, PermissionSystem
from master_agent.runtime.gateway import GatewayResult
from master_agent.verification.evidence import Evidence, ExpectedOutcome


class RecordingGateway:
    """A gateway with no Executive behind it at all -- it just records what
    it was asked to do. Used to test the loop's orchestration without
    dragging a real Environment into unit tests."""

    def __init__(
        self,
        results: list[GatewayResult] | None = None,
        evidence: Evidence | None = None,
    ) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.verify_calls: list[str] = []
        self._results = list(results or [])
        self._evidence = evidence

    def invoke(self, capability: str, payload: dict[str, Any]) -> GatewayResult:
        self.calls.append((capability, dict(payload)))
        if self._results:
            return self._results.pop(0)
        return GatewayResult(success=True, output={"ran": capability})

    def verify(
        self, capability: str, payload: dict[str, Any], expected: ExpectedOutcome
    ) -> Evidence | None:
        self.verify_calls.append(capability)
        return self._evidence


class RaisingGateway:
    """Raises instead of returning a failure result -- a badly-behaved
    Executive. The loop must survive it."""

    def __init__(self) -> None:
        self.attempts = 0

    def invoke(self, capability: str, payload: dict[str, Any]) -> GatewayResult:
        self.attempts += 1
        raise RuntimeError("executive exploded")

    def verify(
        self, capability: str, payload: dict[str, Any], expected: ExpectedOutcome
    ) -> Evidence | None:
        return None


class BrowserGateway:
    """Pairs MB022's BrowserWorker with the ExecutiveGateway protocol.

    This is what a real founder-side wiring looks like: it knows about the
    Browser Executive, and it lives outside `runtime/` precisely so the
    Runtime does not. Execution and verification both go through
    `BrowserWorker.run_step()`, so the Execute -> Verify -> Audit
    discipline MB022 established is preserved, not bypassed.
    """

    def __init__(self, worker: Any, permissions: PermissionSystem, executor_name: str) -> None:
        self._worker = worker
        self._permissions = permissions
        self._executor_name = executor_name
        self._last_evidence: Evidence | None = None

    def _approve(self, capability: str) -> None:
        # Stands in for a human approving this mission's steps. Relayed to
        # the Executor's own grant key -- the ADR-0005 pattern.
        self._permissions.grant(self._executor_name, capability, GrantScope.ONCE)

    def invoke(self, capability: str, payload: dict[str, Any]) -> GatewayResult:
        self._approve(capability)
        report = self._worker.run_step(capability, payload, requested_by="runtime_engine")
        self._last_evidence = report.evidence
        if report.execution.success:
            return GatewayResult(success=True, output=report.execution.output)
        return GatewayResult(success=False, errors=list(report.execution.errors))

    def verify(
        self, capability: str, payload: dict[str, Any], expected: ExpectedOutcome
    ) -> Evidence | None:
        from master_agent.plugins.browser_verifier import BrowserVerifier

        verifier = BrowserVerifier(
            self._worker._sessions,
            payload.get("session_id", ""),
            payload.get("selectors"),
        )
        return verifier.verify(expected)


class FilesystemGateway:
    """Pairs FilesystemWorker with the ExecutiveGateway protocol.

    This is what a real founder-side wiring looks like: it knows about the
    Filesystem Executive, and it lives outside `runtime/` precisely so the
    Runtime does not. Execution and verification both go through
    `FilesystemWorker.run_step()`, so the Execute -> Verify -> Audit
    discipline is preserved, not bypassed.
    """

    def __init__(self, worker: Any, permissions: PermissionSystem, executor_name: str) -> None:
        self._worker = worker
        self._permissions = permissions
        self._executor_name = executor_name
        self._last_evidence: Evidence | None = None

    def _approve(self, capability: str) -> None:
        # Stands in for a human approving this mission's steps. Relayed to
        # the Executor's own grant key -- the ADR-0005 pattern.
        self._permissions.grant(self._executor_name, capability, GrantScope.ONCE)

    def invoke(self, capability: str, payload: dict[str, Any]) -> GatewayResult:
        self._approve(capability)
        report = self._worker.run_step(capability, payload, requested_by="runtime_engine")
        self._last_evidence = report.evidence
        if report.execution.success:
            return GatewayResult(success=True, output=report.execution.output)
        return GatewayResult(success=False, errors=list(report.execution.errors))

    def verify(
        self, capability: str, payload: dict[str, Any], expected: ExpectedOutcome
    ) -> Evidence | None:
        from master_agent.plugins.filesystem_verifier import FilesystemVerifier
        from pathlib import Path

        # Resolve target path from payload
        location_key = (payload.get("location") or "desktop").strip().lower()
        # Get locations from worker
        locations = getattr(self._worker, "_locations", {})
        if not locations:
            from master_agent.executor.action import default_locations
            locations = default_locations()
        base = locations.get(location_key) or list(locations.values())[0]

        if "path" in payload:
            path = payload["path"].strip()
        elif "name" in payload:
            path = payload["name"].strip()
        elif "source" in payload:
            path = payload["source"].strip()
        elif "destination" in payload:
            path = payload["destination"].strip()
        else:
            path = "."

        target_path = Path(base) / path

        verifier = FilesystemVerifier(
            target_path=str(target_path),
            base_path=str(base),
            include_content_preview=payload.get("include_content_preview", False),
            include_directory_listing=payload.get("include_directory_listing", False),
        )
        return verifier.verify(expected)


def control_with(plugin: Any, registry: Any) -> MissionControl:
    registry.register(plugin)
    mc = MissionControl()
    discover_executives(mc, registry)
    return mc
