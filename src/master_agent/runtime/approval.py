"""The Runtime's approval boundary (Mission Brief 028.0, ADR-0019).

Constitution Rule 5 says the Permission System is consulted before any
step above `READ_ONLY`, **regardless of which Operator Instance executes
it**. Until MB028.0 that was true on the Orchestrator path and false on
the Runtime path: the Runtime calls an `ExecutiveGateway` directly, so the
Orchestrator's check never ran, and the Executor's check was pre-satisfied
by the ADR-0005 relay that exists to carry the Orchestrator's decision
down. Two gates, two paths, both gates on one path.

This module is the fix. `ApprovalGate` is a protocol **defined inside
`runtime/`** — the same move MB025 made with `CheckpointSink` — so the
Runtime consults a boundary without acquiring a dependency on the
Permission System, the Capability Registry, or any plugin. What the
Runtime knows is: *there is a gate, and it may refuse.*

`PermissionSystemGate` is the real implementation. It lives here for the
same reason `PluginGateway` lives in `runtime/gateway.py`: it is typed
against protocols and **imports nothing concrete**, so this package still
knows no specific Executive, no specific plugin, and no specific
Permission System class.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

# The one tier that needs no approval, per Constitution Rule 5's own
# wording ("any step above READ_ONLY"). Kept as a string so this module
# imports no enum from plugins/.
READ_ONLY = "read_only"

# `source` on every approval event, so the audit distinguishes a boundary
# decision from the Runtime's own reporting.
APPROVAL_SOURCE = "approval_boundary"


@dataclass(frozen=True)
class ApprovalRequest:
    """What the Runtime knows about a task at the moment it must be
    approved. Frozen: a gate inspects a request, it never edits one.

    Deliberately does **not** carry a risk tier. The Runtime does not know
    what is risky — that classification belongs to the capability's own
    manifest, and making the Runtime carry it would mean the Runtime
    reasoning about Executives, which MB024's Rule 2 forbids and an
    import-parsing test enforces. The gate resolves the tier itself.
    """

    executive_id: str
    qualified_capability: str
    local_capability: str
    task_id: str
    objective_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "executive_id": self.executive_id,
            "capability": self.qualified_capability,
            "local_capability": self.local_capability,
            "task_id": self.task_id,
            "objective_id": self.objective_id,
        }


class ApprovalDenied(Exception):
    """Raised by a gate that will not authorise a request.

    A distinct type from `permissions.ApprovalRequired` on purpose: the
    Runtime must be able to catch a refusal without importing the
    Permission System. `PermissionSystemGate` translates one into the
    other at the boundary.
    """

    def __init__(self, request: ApprovalRequest, reason: str) -> None:
        super().__init__(f"{reason} (capability '{request.qualified_capability}')")
        self.request = request
        self.reason = reason


@runtime_checkable
class ApprovalGate(Protocol):
    """The boundary. `check()` returns None to authorise, or raises
    `ApprovalDenied`. It must never execute anything."""

    def check(self, request: ApprovalRequest) -> None: ...


class PermissionSystemGate:
    """Delegates to Shared Infrastructure's Permission System — the single
    grant ledger the Orchestrator already uses (Constitution §5.2). There
    is no second ledger and no second policy; this is an adapter, not a
    decision-maker.

    `permissions` needs `check(plugin_name, capability, risk_tier)`, and
    `registry` needs `risk_tier_for(plugin_name, capability)` — exactly the
    two calls `Orchestrator.execute_step()` makes, so both paths now ask
    the same question of the same objects in the same way. Typed as `Any`
    so `runtime/` imports nothing concrete.

    `on_decision` is an optional callback invoked with (request, granted,
    reason) after every decision, so a caller can publish approval
    evidence without this class knowing what an event bus is.
    """

    def __init__(
        self,
        permissions: Any,
        registry: Any,
        on_decision: Any = None,
    ) -> None:
        self._permissions = permissions
        self._registry = registry
        self._on_decision = on_decision
        self.reporting_failures: list[str] = []

    def report_to(self, bus: Any, decided_by: str = "founder") -> PermissionSystemGate:
        """Wire evidence publishing after construction. Returns self, so a
        composition root reads as one expression."""
        self._on_decision = self.publishing_reporter(bus, decided_by)
        return self

    def check(self, request: ApprovalRequest) -> None:
        try:
            risk_tier = self._registry.risk_tier_for(
                request.executive_id, request.local_capability
            )
        except Exception as exc:
            # Fail closed on an unknown classification. A capability whose
            # risk cannot be established is not thereby safe.
            self._decided(request, False, f"risk tier unresolvable: {exc}")
            raise ApprovalDenied(request, f"risk tier unresolvable: {exc}") from exc

        tier_value = getattr(risk_tier, "value", risk_tier)
        if tier_value == READ_ONLY:
            # Not "approved" — outside the boundary entirely, per Rule 5.
            # Deliberately not reported as a decision: recording an
            # approval that never happened would corrupt the evidence
            # Deliverable 8 depends on.
            return

        try:
            self._permissions.check(
                request.executive_id, request.local_capability, risk_tier
            )
        except Exception as exc:
            self._decided(request, False, str(exc) or "approval required")
            raise ApprovalDenied(request, "founder approval required") from exc

        self._decided(request, True, f"grant satisfied for tier '{tier_value}'")

    def publishing_reporter(self, bus: Any, decided_by: str = "founder") -> Any:
        """An `on_decision` callback that publishes approval evidence.

        Lives here, not in the launcher, so that **the code under test is
        the code that ships**: an earlier draft duplicated this in
        `launcher/boot.py`, which meant the boundary tests exercised a
        different reporter than a real founder ever would.

        `decided_by` is required-with-a-default rather than optional:
        Deliverable 8 asks the audit to prove *who* approved, and
        "approval existed" is a weaker claim than "the founder approved."
        """
        from master_agent.mission_control.events import Event, EventType

        def report(request: ApprovalRequest, granted: bool, reason: str) -> None:
            bus.publish(
                Event(
                    event_type=(
                        EventType.APPROVAL_GRANTED
                        if granted
                        else EventType.APPROVAL_DENIED
                    ),
                    source=APPROVAL_SOURCE,
                    task_id=request.task_id,
                    objective_id=request.objective_id,
                    capability=request.qualified_capability,
                    payload={
                        **request.as_dict(),
                        "decided_by": decided_by,
                        "granted": granted,
                        "reason": reason,
                    },
                )
            )

        return report

    def _decided(self, request: ApprovalRequest, granted: bool, reason: str) -> None:
        """Report the decision, and never let reporting change it.

        A broken reporter is a reporting problem: it must not turn a
        granted request into a refused one, and — more importantly — must
        not turn a refusal into an exception the Runtime mistakes for
        something else. The failure is collected so a caller can surface
        it rather than being silently discarded.
        """
        if self._on_decision is None:
            return
        try:
            self._on_decision(request, granted, reason)
        except Exception as exc:  # noqa: BLE001 - reporting never gates work
            self.reporting_failures.append(f"{request.task_id}: {exc}")
