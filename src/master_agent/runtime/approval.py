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

from dataclasses import dataclass, field
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
    # The task's payload, carried so a composition root can estimate
    # impact ("Deletes 14 files") without the Runtime knowing what any
    # payload means. Read-only here: nothing in `runtime/` interprets it.
    payload: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "executive_id": self.executive_id,
            "capability": self.qualified_capability,
            "local_capability": self.local_capability,
            "task_id": self.task_id,
            "objective_id": self.objective_id,
        }


class ApprovalPending(Exception):
    """The founder has been asked and has not answered.

    **Not a refusal, and deliberately not a subclass of one.** A refusal
    is a decision and ends the task; pending is an open question and the
    task waits. Conflating them is how "the founder was asleep" becomes
    "the mission failed" (MB028.1 Deliverable 6 vs 7).
    """

    def __init__(self, request: ApprovalRequest, approval_id: str, reason: str) -> None:
        super().__init__(f"{reason} (approval {approval_id})")
        self.request = request
        self.approval_id = approval_id
        self.reason = reason


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
        approvals: Any = None,
    ) -> None:
        self._permissions = permissions
        self._registry = registry
        self._on_decision = on_decision
        # Mission Control, when the composition root has one. Given it,
        # a capability the grant ledger will not authorise becomes a
        # QUESTION FOR THE FOUNDER (`ApprovalPending`) instead of a
        # refusal. Without it the previous behaviour is unchanged, so
        # every existing caller and test is unaffected.
        self._approvals = approvals
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
            # THE BOUNDARY THAT WAS COLLAPSING TWO DIFFERENT ANSWERS.
            #
            # The Permission System raising here means "no standing grant
            # covers this" -- which is a question for the founder, not a
            # verdict. Translating it straight into `ApprovalDenied` sent
            # the Runtime down `_refuse()`, which reports a FAILED task,
            # so the founder was told "Couldn't finish" about work that
            # had merely not been asked about yet. `ApprovalPending`'s own
            # docstring names this exact failure mode: "Conflating them is
            # how 'the founder was asleep' becomes 'the mission failed'."
            #
            # With Mission Control wired, the question is opened (or
            # re-read if already open -- `request_approval` is idempotent
            # per task+capability precisely because the Runtime re-checks
            # every cycle) and the task WAITS. Once the founder answers,
            # this same code path reads the decision and either authorises
            # or refuses. Without Mission Control, the old behaviour
            # stands unchanged.
            if self._approvals is not None:
                decision = self._ask_founder(request, risk_tier, str(exc))
                if decision is not None:
                    return decision
            self._decided(request, False, str(exc) or "approval required")
            raise ApprovalDenied(request, "founder approval required") from exc

        self._decided(request, True, f"grant satisfied for tier '{tier_value}'")

    def _ask_founder(self, request: ApprovalRequest, risk_tier: Any, reason: str) -> None:
        """Open (or re-read) the founder's question for this request.

        Returns `None` to mean "authorised, carry on". Raises
        `ApprovalPending` while the answer is outstanding, or
        `ApprovalDenied` once the founder has actually said no -- which is
        a real decision and genuinely ends the task.
        """
        from master_agent.mission_control.approvals import ApprovalState
        from master_agent.mission_control.approvals import PendingApproval

        tier_value = getattr(risk_tier, "value", risk_tier)
        approval, _is_new = self._approvals.request_approval(
            PendingApproval(
                capability=request.qualified_capability,
                local_capability=request.local_capability,
                executive_id=request.executive_id,
                risk_tier=str(tier_value),
                reason=reason or "founder approval required",
                task_id=request.task_id,
                objective_id=request.objective_id,
            )
        )
        state = approval.state
        if state == ApprovalState.APPROVED:
            self._decided(request, True, f"founder approved ({approval.approval_id})")
            return None
        if state == ApprovalState.REJECTED:
            self._decided(request, False, f"founder rejected ({approval.approval_id})")
            raise ApprovalDenied(request, "the founder declined this")
        if state == ApprovalState.EXPIRED:
            self._decided(request, False, f"approval expired ({approval.approval_id})")
            raise ApprovalDenied(request, "the approval expired before it was answered")
        # PENDING or DEFERRED -- still an open question, so the task holds.
        raise ApprovalPending(request, approval.approval_id, "awaiting founder approval")

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


class FounderApprovalGate:
    """The MB028.1 gate: when authority is missing, **ask** instead of
    refusing outright.

    Wraps `PermissionSystemGate` rather than replacing it, so the
    boundary stays singular (ADR-0019 unweakened) and the Permission
    System remains the only ledger of granted authority. What this adds is
    the third outcome the founder workflow needs:

    | Permission System says | MB028.0 | MB028.1 |
    |---|---|---|
    | granted | execute | execute |
    | not granted | fail the task | **ask the founder; the task waits** |
    | founder rejected / expired | — | fail the task, never retried |

    `approvals` needs `find_open`, `request`, and `expire_due`;
    `mission_control` needs `request_approval` and `expire_approvals` — so
    this class is typed against `Any` and `runtime/` still imports nothing
    concrete, exactly as `PluginGateway` and `PermissionSystemGate` are.
    """

    def __init__(
        self,
        inner: Any,
        mission_control: Any,
        grant_on_approval: Any,
        timeout_seconds: float | None = None,
        describe_impact: Any = None,
    ) -> None:
        self._inner = inner
        self._mc = mission_control
        self._grant = grant_on_approval
        self._timeout_seconds = timeout_seconds
        self._describe_impact = describe_impact or (lambda _request: "unknown")

    def check(self, request: ApprovalRequest) -> None:
        # Expiry is evaluated here rather than on a timer: the Runtime
        # re-checks the boundary every cycle while a task waits, so this
        # is already the system's heartbeat for pending approvals. A
        # separate timer would be a second clock to keep honest.
        self._mc.expire_approvals(self._timeout_seconds)

        existing = self._mc.approvals.find_open(
            request.task_id, request.qualified_capability
        )
        decided = self._decided_for(request)

        if decided is not None:
            state = decided.state.value
            if state == "approved":
                # Turn the founder's answer into real authority, once, in
                # the one place authority lives. The task then passes the
                # inner gate exactly as if it had been granted up front.
                self._grant(request)
            elif state in ("rejected", "expired"):
                raise ApprovalDenied(
                    request,
                    "founder rejected this request"
                    if state == "rejected"
                    else "approval expired before a decision was made",
                )

        try:
            self._inner.check(request)
        except ApprovalDenied:
            if existing is not None:
                raise ApprovalPending(
                    request, existing.approval_id, "awaiting founder approval"
                ) from None
            approval = self._ask(request)
            raise ApprovalPending(
                request, approval.approval_id, "awaiting founder approval"
            ) from None

    def _decided_for(self, request: ApprovalRequest) -> Any:
        """The most recent *decided* entry for this exact task+capability.
        Scanned newest-first so a fresh question always wins over an old
        answer -- an approval is consumed, never reused (ADR-0009)."""
        for approval in reversed(self._mc.approvals.all()):
            if (
                approval.task_id == request.task_id
                and approval.capability == request.qualified_capability
                and not approval.is_open
            ):
                return approval
        return None

    def _ask(self, request: ApprovalRequest) -> Any:
        from master_agent.mission_control.approvals import PendingApproval

        risk_tier = self._risk_tier(request)
        approval, _is_new = self._mc.request_approval(
            PendingApproval(
                capability=request.qualified_capability,
                local_capability=request.local_capability,
                executive_id=request.executive_id,
                risk_tier=risk_tier,
                reason=_human_reason(request.local_capability),
                impact=self._describe_impact(request),
                task_id=request.task_id,
                objective_id=request.objective_id,
                objective=self._objective_description(request.objective_id),
                requested_by="runtime",
            )
        )
        return approval

    def _risk_tier(self, request: ApprovalRequest) -> str:
        try:
            tier = self._inner._registry.risk_tier_for(
                request.executive_id, request.local_capability
            )
            return getattr(tier, "value", str(tier))
        except Exception:  # noqa: BLE001 - an unknown tier is still worth asking about
            return "unknown"

    def _objective_description(self, objective_id: str | None) -> str | None:
        if objective_id is None:
            return None
        try:
            for objective in self._mc.dispatcher.objectives():
                if objective.objective_id == objective_id:
                    return objective.description
        except Exception:  # noqa: BLE001 - a missing description is not a reason to refuse
            return None
        return None


def _human_reason(local_capability: str) -> str:
    """`delete_folder` -> `Delete Folder`. A founder deciding at 22:13
    should not have to read snake_case to work out what they are being
    asked. Deliberately mechanical rather than a lookup table -- a table
    would need editing every time a capability is added, which is exactly
    the coupling Rule 3 forbids."""
    return local_capability.replace("_", " ").title()
