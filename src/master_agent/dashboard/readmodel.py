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
