"""The ExecutiveGateway — the seam between orchestration and work.

This is the resolution of Mission Brief 024's central tension: Mission
Control never performs work, and the Runtime Engine never performs work,
yet something must actually invoke an Executive or nothing ever executes.
See RUNTIME_ENGINE_ARCHITECTURE.md §2.1.

A gateway is the thing that *does* perform work. The Runtime holds
gateways keyed by Executive ID and resolves which one to use from the
assignment Mission Control already made -- it never asks an Executive
anything, never imports one, and has no Executive-specific knowledge.

Nothing in this module imports a concrete Executive, and
`tests/test_runtime_architecture.py` enforces that for the whole
`runtime/` package.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from master_agent.verification.evidence import Evidence, ExpectedOutcome


@dataclass
class GatewayResult:
    """What one invocation produced. Deliberately mirrors the shape the
    rest of the system already uses (`success`, `output`, `errors`) rather
    than inventing a fourth result type."""

    success: bool
    output: Any = None
    errors: list[str] = field(default_factory=list)
    evidence: Evidence | None = None

    @property
    def error_text(self) -> str:
        return "; ".join(self.errors) or "unknown gateway failure"


@runtime_checkable
class ExecutiveGateway(Protocol):
    """What the Runtime needs from an Executive, and nothing more.

    Two methods, both Executive-agnostic. A gateway implementation is
    where product knowledge lives; the protocol itself has none.
    """

    def invoke(self, capability: str, payload: dict[str, Any]) -> GatewayResult:
        """Perform one capability call. Must not raise for ordinary
        failure -- return `GatewayResult(success=False, errors=[...])`, the
        same contract `Action.run()` already follows."""
        ...

    def verify(
        self,
        capability: str,
        payload: dict[str, Any],
        expected: ExpectedOutcome,
    ) -> Evidence | None:
        """Produce Evidence by re-observing reality, or None if this
        Executive has no Verifier. Never derived from the invoke() result
        -- that would collapse the Execution/Verification distinction
        ADR-0011 exists to maintain."""
        ...


@runtime_checkable
class ObjectiveFinalizer(Protocol):
    """Optional gateway extension for mission-scoped resource release.

    Runtime owns the terminal moment and the concrete gateway owns how its
    environment is cleaned.  Keeping this separate from ``ExecutiveGateway``
    means stateless gateways do not acquire a meaningless method.
    """

    def finalize_objective(self, tasks: list[Any]) -> list[str]:
        """Release resources owned by these terminal Objective tasks.

        Best effort: return warnings and do not raise for ordinary teardown
        failure.  Finalization never changes task outcome or creates Evidence.
        """
        ...


class PluginGateway:
    """A gateway over any object implementing the `Plugin` contract.

    Generic on purpose: this one class serves the Browser Executive, the
    Filesystem Executive, and every future Executive that implements the
    same long-standing contract -- there is no per-Executive gateway to
    write. It performs no verification (`verify()` returns None), because
    the `Plugin` contract has no verification surface; an Executive with a
    Verifier supplies a gateway that pairs the two (see
    `tests/runtime_test_support.py` for the Browser example).

    Note this class lives in `runtime/` but imports nothing concrete: it
    is typed against the `Plugin` protocol only, so the Runtime package
    still knows no specific Executive.
    """

    def __init__(self, plugin: Any, grant_permission: Any = None) -> None:
        """`grant_permission` is an optional callable invoked with the
        capability name immediately before each invocation. It exists so a
        caller can relay an already-obtained human approval down to the
        Executor's grant key (the ADR-0005 pattern) without this class
        knowing anything about the Permission System. Left None, the
        gateway relies on approval having been arranged some other way,
        and an unapproved call correctly raises rather than silently
        proceeding."""
        self._plugin = plugin
        self._grant_permission = grant_permission

    def invoke(self, capability: str, payload: dict[str, Any]) -> GatewayResult:
        if self._grant_permission is not None:
            self._grant_permission(capability)

        result = self._plugin.invoke(capability, payload)
        if result.success:
            return GatewayResult(success=True, output=result.output)
        return GatewayResult(
            success=False, errors=[result.error or "unknown plugin failure"]
        )

    def verify(
        self,
        capability: str,
        payload: dict[str, Any],
        expected: ExpectedOutcome,
    ) -> Evidence | None:
        # The Plugin contract has no verification surface. Returning None
        # is honest: this gateway cannot verify, so the Runtime records
        # that no Evidence was produced rather than inventing a verdict.
        return None
