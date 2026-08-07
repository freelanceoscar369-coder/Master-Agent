"""The Dashboard read model (ADR-0016 Decision 1).

Frozen dataclasses of plain data. Panels render only from these, never
from a live object -- which is what makes "read-only" a property of the
data flow rather than a rule someone has to remember, and what makes a
panel testable without a Runtime, a Mission Control, or a browser.

Every field is optional (ADR-0016 Decision 2): absence is a first-class
value, and `0` never stands in for "unknown".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# Rendered wherever a value could not be read. A visible marker, never a
# plausible-looking zero.
UNAVAILABLE = "—"


@dataclass(frozen=True)
class PanelStatus:
    """Whether a panel's data could be read, and why not if it could not.

    Carried per panel rather than globally: a Dashboard wired to Mission
    Control but no persistence should show four healthy panels and one
    honest "not wired", not a single global failure.
    """

    available: bool = True
    reason: str | None = None

    @staticmethod
    def missing(reason: str) -> PanelStatus:
        return PanelStatus(available=False, reason=reason)


@dataclass(frozen=True)
class RuntimePanelData:
    status: PanelStatus = PanelStatus()
    state: str | None = None
    uptime_seconds: float | None = None
    active_cycle: int | None = None
    queue_length: int | None = None
    last_dispatch_at: datetime | None = None
    last_verification_at: datetime | None = None
    tasks_completed: int | None = None
    tasks_failed: int | None = None
    retries_performed: int | None = None
    escalations: int | None = None
    executives_online: int | None = None
    executives_busy: int | None = None


@dataclass(frozen=True)
class MissionPanelData:
    status: PanelStatus = PanelStatus()
    objective: str | None = None
    objective_id: str | None = None
    progress: float | None = None
    active_executive: str | None = None
    active_capability: str | None = None
    eta_seconds: float | None = None
    mission_status: str | None = None
    errors: list[str] = field(default_factory=list)
    evidence_count: int | None = None


@dataclass(frozen=True)
class ExecutiveRow:
    executive_id: str
    health: str
    version: str
    state: str
    capability_count: int
    current_task: str | None = None


@dataclass(frozen=True)
class ExecutivePanelData:
    status: PanelStatus = PanelStatus()
    executives: list[ExecutiveRow] = field(default_factory=list)


@dataclass(frozen=True)
class CapabilityPanelData:
    status: PanelStatus = PanelStatus()
    registered: list[str] = field(default_factory=list)
    pending: int | None = None
    active: int | None = None
    completed: int | None = None
    failed: int | None = None
    blocked: int | None = None


@dataclass(frozen=True)
class AuditRow:
    sequence: int
    event_type: str
    occurred_at: datetime
    source: str
    task_id: str | None = None
    capability: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class AuditPanelData:
    status: PanelStatus = PanelStatus()
    recent: list[AuditRow] = field(default_factory=list)
    total_entries: int | None = None
    failures: int | None = None


@dataclass(frozen=True)
class PersistencePanelData:
    status: PanelStatus = PanelStatus()
    last_checkpoint_at: datetime | None = None
    snapshot_schema_version: int | None = None
    snapshot_created_at: datetime | None = None
    event_log_size: int | None = None
    recovery_status: str | None = None
    recovery_source: str | None = None
    quarantined_tasks: int | None = None


@dataclass(frozen=True)
class SystemHealthPanelData:
    status: PanelStatus = PanelStatus()
    executives_online: int | None = None
    runtime_health: str | None = None
    queue_health: str | None = None
    audit_health: str | None = None
    persistence_health: str | None = None


@dataclass(frozen=True)
class FounderStatePanelData:
    """The published Founder State, rendered verbatim. Deliberately a raw
    dict: MB026 says "display the published Founder State exactly as
    exposed. Do not derive values independently", so this panel must not
    reshape it."""

    status: PanelStatus = PanelStatus()
    state: dict[str, Any] | None = None


@dataclass(frozen=True)
class ApprovalRow:
    """One pending approval, as plain data. Frozen like every other row:
    the Approval panel *displays* decisions, it never makes them -- the
    founder does, through Mission Control (ADR-0016 preserved, ADR-0020)."""

    index: int
    approval_id: str
    capability: str
    executive_id: str
    risk_tier: str
    reason: str
    impact: str
    requested_at: str
    state: str
    objective: str | None = None


@dataclass(frozen=True)
class ApprovalPanelData:
    status: PanelStatus = PanelStatus()
    approvals: list[ApprovalRow] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.approvals)


@dataclass(frozen=True)
class MachineRow:
    """One thing the machine either has or does not (MB030 Deliverable 9)."""

    label: str
    status: str
    version: str | None = None
    detail: str = ""


@dataclass(frozen=True)
class MachinePanelData:
    """What the Desktop Executive last observed. Handed in by the
    launcher, never discovered by the Dashboard -- ADR-0016 Decision 5,
    the same rule that keeps recovery status out of here."""

    status: PanelStatus = PanelStatus()
    readiness: list[MachineRow] = field(default_factory=list)
    installed: list[MachineRow] = field(default_factory=list)
    running: list[str] = field(default_factory=list)
    unavailable: list[MachineRow] = field(default_factory=list)
    missing_recommended: list[str] = field(default_factory=list)
    ai_installed: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BrokerDecisionRow:
    """One AI provider decision, as plain data (MB032 Deliverable 9).

    Every field is already resolved -- the tiers especially. A panel that
    worked out for itself what "expensive" means would be a second opinion
    about cost in the layer least able to defend it (ADR-0016).
    """

    task_id: str
    capability: str
    outcome: str
    provider_id: str | None
    reason: str
    cost_tier: str
    quality_tier: str
    cost_detail: str
    quality_detail: str
    policy_version: str
    decided_at: str
    approval_state: str
    locality: str = ""


@dataclass(frozen=True)
class ExecutionRow:
    """The last piece of thinking that actually happened (MB033).

    Separate from `BrokerDecisionRow` because a decision and its execution
    are different events: one chose, the other ran, and one can happen
    without the other in both directions.
    """

    provider_id: str
    outcome: str
    succeeded: bool
    latency: str
    cost: str
    cache: str
    model: str = ""
    tokens: int | None = None
    retries: int = 0
    error: str = ""
    # ---- MB038 reporting ----------------------------------------------
    #
    # Transcribed, never computed. Empty strings mean "this call had none"
    # -- a pre-MB038 execution, or one made without a budget -- which is a
    # different fact from a budget of zero.
    budget: str = ""
    bound_by: str = ""
    timeout_reason: str = ""
    admission: str = ""
    lifecycle: str = ""
    #: MB035. The Verification verdict, already worded for a founder, or
    #: the marker when nothing was asked of the answer -- which is a
    #: different fact from "it was checked and failed".
    verified: str = ""


@dataclass(frozen=True)
class TokenEconomyRow:
    """What the founder's quota has gone on. Counts only -- every value is
    a total over executions that actually occurred (MB033)."""

    local_executions: int = 0
    cloud_executions: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    avoided_cloud_executions: int = 0
    money_saved: float = 0.0
    total_spend: float = 0.0
    failed_executions: int = 0
    total_tokens: int | None = None
    basis: str = ""


@dataclass(frozen=True)
class BrokerPanelData:
    """What the AI Capability Broker last decided. Handed in by the
    launcher exactly as the machine inventory is -- the Dashboard reads
    decisions and can no more cause one than it can cause a machine scan
    (ADR-0016 Decision 5)."""

    status: PanelStatus = PanelStatus()
    policy_version: str | None = None
    providers_available: int | None = None
    providers_total: int | None = None
    scanned: bool = False
    total_decisions: int | None = None
    awaiting_approval: int | None = None
    decisions: list[BrokerDecisionRow] = field(default_factory=list)
    recording_failures: list[str] = field(default_factory=list)
    #: None until something has actually run -- absence rather than a row
    #: of zeroes that reads as "it ran and achieved nothing".
    last_execution: ExecutionRow | None = None
    economy: TokenEconomyRow = field(default_factory=TokenEconomyRow)

    @property
    def count(self) -> int:
        return len(self.decisions)


@dataclass(frozen=True)
class MemoryRow:
    """One remembered thing, as the panel shows it (MB034)."""

    id: str
    title: str
    category: str
    importance: str
    written_at: str
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MemoryPanelData:
    """What Kalpavriksha knows about the founder. Handed in by the
    launcher like every other live read (ADR-0016 Decision 5) -- the
    Dashboard displays memory and can no more write one than it can
    trigger a machine scan."""

    status: PanelStatus = PanelStatus()
    total: int | None = None
    critical: int | None = None
    recent: list[MemoryRow] = field(default_factory=list)
    top_tags: list[tuple[str, int]] = field(default_factory=list)
    last_written: MemoryRow | None = None
    problems: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PlanStepRow:
    """One planned step, as the panel shows it (MB037)."""

    step_id: str
    capability: str
    state: str
    verdict: str = ""
    priority: str = "normal"
    complexity: str = "moderate"
    expectation: str = ""
    blocked_by: list[str] = field(default_factory=list)
    #: True when something this step waits on has *failed*. "Waiting on
    #: step_1" is true but misleading once step_1 will never finish, and
    #: a founder reading it would keep waiting too.
    unreachable: bool = False
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PlanPanelData:
    """The mission the Planner produced, and how far through it is.

    Handed in by the launcher like every other live read (ADR-0016
    Decision 5). The Dashboard renders a plan and can no more create one
    than it can trigger a machine scan.

    Deliberately absent: the prompt, the raw reply, and anything else
    resembling a provider's reasoning. MB037 forbids showing internal LLM
    reasoning on the founder page, and the cheapest way to honour that is
    for the read model to have nowhere to put it.
    """

    # Absent by default, unlike every panel above it. Those describe
    # subsystems that exist as soon as the system boots; a *plan* does not
    # exist until somebody asks for something. Defaulting to available
    # would render "0/0 steps" for a mission nobody started -- `0`
    # standing in for "unknown", which ADR-0016 exists to prevent.
    status: PanelStatus = field(
        default_factory=lambda: PanelStatus.missing("nothing planned yet")
    )
    objective: str = ""
    plan_id: str = ""
    state: str = ""
    steps: list[PlanStepRow] = field(default_factory=list)
    current: PlanStepRow | None = None
    completed: int = 0
    remaining: int = 0
    blocked: int = 0
    failed: int = 0
    unverified: int = 0
    progress: float = 0.0
    planned_by: str | None = None
    history_count: int = 0


@dataclass(frozen=True)
class DashboardSnapshot:
    """One complete, self-consistent view. Everything a frame needs, and
    nothing live."""

    captured_at: datetime
    runtime: RuntimePanelData = field(default_factory=RuntimePanelData)
    mission: MissionPanelData = field(default_factory=MissionPanelData)
    executives: ExecutivePanelData = field(default_factory=ExecutivePanelData)
    capabilities: CapabilityPanelData = field(default_factory=CapabilityPanelData)
    audit: AuditPanelData = field(default_factory=AuditPanelData)
    persistence: PersistencePanelData = field(default_factory=PersistencePanelData)
    system_health: SystemHealthPanelData = field(default_factory=SystemHealthPanelData)
    founder_state: FounderStatePanelData = field(default_factory=FounderStatePanelData)
    approvals: ApprovalPanelData = field(default_factory=ApprovalPanelData)
    machine: MachinePanelData = field(default_factory=MachinePanelData)
    broker: BrokerPanelData = field(default_factory=BrokerPanelData)
    memory: MemoryPanelData = field(default_factory=MemoryPanelData)
    plan: PlanPanelData = field(default_factory=PlanPanelData)
