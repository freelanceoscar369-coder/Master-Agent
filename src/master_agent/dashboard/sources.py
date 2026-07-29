"""Collecting a DashboardSnapshot from published contracts.

The only layer that touches live systems. Everything above it sees plain,
frozen data (ADR-0016 Decision 1).

Two disciplines hold throughout:

  - **Read-only.** Every call here is a getter. This module never
    dispatches, never mutates, and holds narrow Protocols rather than
    concrete engines so it cannot reach a mutating method even by
    accident.
  - **Absence is a value.** Every read is wrapped so a failure becomes
    absent data *with a reason*, never an exception that blanks the view
    (ADR-0016 Decision 2). `0` never stands in for "unknown".
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from master_agent.dashboard.health import (
    audit_health,
    persistence_health,
    queue_health,
    runtime_health,
)
from master_agent.dashboard.readmodel import (
    AuditPanelData,
    AuditRow,
    CapabilityPanelData,
    DashboardSnapshot,
    ExecutivePanelData,
    ExecutiveRow,
    FounderStatePanelData,
    MissionPanelData,
    PanelStatus,
    PersistencePanelData,
    RuntimePanelData,
    SystemHealthPanelData,
)

DEFAULT_AUDIT_WINDOW = 20


@runtime_checkable
class RuntimeReader(Protocol):
    """What the Dashboard needs from a Runtime: one getter.

    Deliberately narrow. Given the whole `RuntimeEngine`, a careless panel
    could call `run_once()`; given this, there is nothing to call but
    `health()`.
    """

    def health(self) -> Any: ...


@runtime_checkable
class PersistenceReader(Protocol):
    """What the Dashboard needs from persistence -- all reads."""

    def load(self) -> Any: ...

    def load_checkpoint(self) -> Any: ...

    @property
    def store(self) -> Any: ...


class DashboardSources:
    """Reads published contracts into a snapshot.

    `mission_control`, `runtime`, and `persistence` are each optional: a
    Dashboard attached to a half-wired system renders a complete, honest
    frame rather than failing (MB026 Rule 3).

    `recovery_report` is handed in by the launcher that ran `recover()` --
    the Dashboard never calls recovery itself, because that would be both
    a mutation and orchestration (ADR-0016 Decision 5).
    """

    def __init__(
        self,
        mission_control: Any = None,
        runtime: RuntimeReader | None = None,
        persistence: PersistenceReader | None = None,
        recovery_report: Any = None,
        audit_window: int = DEFAULT_AUDIT_WINDOW,
        clock: Any = None,
    ) -> None:
        self._mc = mission_control
        self._runtime = runtime
        self._persistence = persistence
        self._recovery = recovery_report
        self._audit_window = audit_window
        self._clock = clock or (lambda: datetime.now(UTC))

    # ---- collection --------------------------------------------------

    def collect(self) -> DashboardSnapshot:
        runtime = self._collect_runtime()
        capabilities = self._collect_capabilities()
        audit = self._collect_audit()
        persistence = self._collect_persistence()

        return DashboardSnapshot(
            captured_at=self._clock(),
            runtime=runtime,
            mission=self._collect_mission(),
            executives=self._collect_executives(),
            capabilities=capabilities,
            audit=audit,
            persistence=persistence,
            system_health=self._collect_system_health(
                runtime, capabilities, audit, persistence
            ),
            founder_state=self._collect_founder_state(),
        )

    # ---- panels ------------------------------------------------------

    def _collect_runtime(self) -> RuntimePanelData:
        if self._runtime is None:
            return RuntimePanelData(status=PanelStatus.missing("no runtime attached"))
        try:
            health = self._runtime.health()
        except Exception as exc:  # noqa: BLE001 — a failed read is absent data, not a crash
            return RuntimePanelData(status=PanelStatus.missing(f"runtime unreadable: {exc}"))

        state = getattr(health, "state", None)
        return RuntimePanelData(
            state=getattr(state, "value", state),
            uptime_seconds=getattr(health, "uptime_seconds", None),
            active_cycle=getattr(health, "active_cycle", None),
            queue_length=getattr(health, "queue_length", None),
            last_dispatch_at=getattr(health, "last_dispatch_at", None),
            last_verification_at=getattr(health, "last_verification_at", None),
            tasks_completed=getattr(health, "tasks_completed", None),
            tasks_failed=getattr(health, "tasks_failed", None),
            retries_performed=getattr(health, "retries_performed", None),
            escalations=getattr(health, "escalations", None),
            executives_online=getattr(health, "executives_online", None),
            executives_busy=getattr(health, "executives_busy", None),
        )

    def _collect_mission(self) -> MissionPanelData:
        if self._mc is None:
            return MissionPanelData(status=PanelStatus.missing("no mission control attached"))
        try:
            state = self._mc.founder_state()
        except Exception as exc:  # noqa: BLE001
            return MissionPanelData(
                status=PanelStatus.missing(f"founder state unreadable: {exc}")
            )

        return MissionPanelData(
            objective=state.current_objective,
            objective_id=state.current_objective_id,
            progress=state.progress,
            active_executive=state.current_executive,
            active_capability=state.current_capability,
            eta_seconds=state.eta_seconds,
            mission_status=self._mission_status(state.current_objective_id),
            errors=list(state.errors),
            evidence_count=len(state.evidence),
        )

    def _mission_status(self, objective_id: str | None) -> str | None:
        """Reads the Objective's own published properties. Not a
        judgement the Dashboard invents -- `is_complete` and `has_failure`
        are Mission Control's, and this only reports which is true."""
        if objective_id is None or self._mc is None:
            return None
        try:
            objective = self._mc.dispatcher.objective(objective_id)
        except Exception:  # noqa: BLE001
            return None
        if objective.is_complete:
            return "completed"
        if objective.has_failure:
            return "attention required"
        return "in progress"

    def _collect_executives(self) -> ExecutivePanelData:
        if self._mc is None:
            return ExecutivePanelData(status=PanelStatus.missing("no mission control attached"))
        try:
            records = self._mc.executives.all()
        except Exception as exc:  # noqa: BLE001
            return ExecutivePanelData(
                status=PanelStatus.missing(f"executive registry unreadable: {exc}")
            )

        rows = [
            ExecutiveRow(
                executive_id=record.executive_id,
                health=getattr(record.health, "value", str(record.health)),
                version=record.version,
                state=getattr(record.state, "value", str(record.state)),
                capability_count=len(record.capabilities),
                current_task=record.current_task_id,
            )
            for record in records
        ]
        return ExecutivePanelData(executives=rows)

    def _collect_capabilities(self) -> CapabilityPanelData:
        if self._mc is None:
            return CapabilityPanelData(status=PanelStatus.missing("no mission control attached"))
        try:
            registered = self._mc.capabilities.names()
            counts = self._task_state_counts()
        except Exception as exc:  # noqa: BLE001
            return CapabilityPanelData(
                status=PanelStatus.missing(f"capability registry unreadable: {exc}")
            )

        return CapabilityPanelData(
            registered=list(registered),
            pending=counts["pending"],
            active=counts["active"],
            completed=counts["completed"],
            failed=counts["failed"],
            blocked=counts["blocked"],
        )

    def _task_state_counts(self) -> dict[str, int]:
        """Counts task states across every objective, using published
        `TaskState` values. Counting is not deciding."""
        counts = {"pending": 0, "active": 0, "completed": 0, "failed": 0, "blocked": 0}
        for objective in self._mc.dispatcher.objectives():
            for task in objective.tasks:
                value = getattr(task.state, "value", str(task.state))
                if value in {"created", "ready"}:
                    counts["pending"] += 1
                elif value in {"dispatched", "running"}:
                    counts["active"] += 1
                elif value == "completed":
                    counts["completed"] += 1
                elif value == "failed":
                    counts["failed"] += 1
                elif value == "blocked":
                    counts["blocked"] += 1
        return counts

    def _collect_audit(self) -> AuditPanelData:
        if self._mc is None:
            return AuditPanelData(status=PanelStatus.missing("no mission control attached"))
        try:
            entries = self._mc.audit.entries
            failures = len(self._mc.audit.failures())
        except Exception as exc:  # noqa: BLE001
            return AuditPanelData(status=PanelStatus.missing(f"audit unreadable: {exc}"))

        window = entries[-self._audit_window :] if self._audit_window else entries
        rows = [
            AuditRow(
                sequence=entry.sequence,
                event_type=getattr(entry.event_type, "value", str(entry.event_type)),
                occurred_at=entry.occurred_at,
                source=entry.source,
                task_id=entry.task_id,
                capability=entry.capability,
                error=entry.error,
            )
            for entry in window
        ]
        return AuditPanelData(recent=rows, total_entries=len(entries), failures=failures)

    def _collect_persistence(self) -> PersistencePanelData:
        if self._persistence is None:
            return PersistencePanelData(status=PanelStatus.missing("no persistence attached"))

        schema_version: int | None = None
        snapshot_created: datetime | None = None
        try:
            envelope = self._persistence.load()
            if envelope is not None:
                schema_version = envelope.schema_version
                snapshot_created = envelope.created_at
        except Exception:  # noqa: BLE001 — a corrupt snapshot is reported, never fatal
            schema_version = None

        checkpoint_at: datetime | None = None
        try:
            checkpoint = self._persistence.load_checkpoint()
            if checkpoint is not None:
                checkpoint_at = checkpoint.captured_at
        except Exception:  # noqa: BLE001
            checkpoint_at = None

        # Known cost, named in ADR-0016: read_events() returns the whole
        # log. Acceptable at Founder Edition volumes and refreshed on a
        # slower cadence than runtime data; the real fix is a
        # count_events() on the StateStore contract, which is a frozen
        # persistence component and deliberately not changed here.
        event_log_size: int | None = None
        try:
            event_log_size = len(self._persistence.store.read_events())
        except Exception:  # noqa: BLE001
            event_log_size = None

        recovery_status = None
        recovery_source = None
        quarantined = None
        if self._recovery is not None:
            recovered = getattr(self._recovery, "recovered", None)
            recovery_status = (
                "recovered" if recovered else "no prior state" if recovered is False else None
            )
            recovery_source = getattr(self._recovery, "source", None)
            quarantined = getattr(self._recovery, "quarantined_tasks", None)

        return PersistencePanelData(
            last_checkpoint_at=checkpoint_at,
            snapshot_schema_version=schema_version,
            snapshot_created_at=snapshot_created,
            event_log_size=event_log_size,
            recovery_status=recovery_status,
            recovery_source=recovery_source,
            quarantined_tasks=quarantined,
        )

    def _collect_system_health(
        self,
        runtime: RuntimePanelData,
        capabilities: CapabilityPanelData,
        audit: AuditPanelData,
        persistence: PersistencePanelData,
    ) -> SystemHealthPanelData:
        """Composed from data already collected -- no second read, so the
        health line can never disagree with the panels above it."""
        return SystemHealthPanelData(
            executives_online=runtime.executives_online,
            runtime_health=runtime_health(runtime.state).value,
            queue_health=queue_health(
                capabilities.pending, capabilities.blocked, capabilities.failed
            ).value,
            audit_health=audit_health(audit.total_entries, audit.failures).value,
            persistence_health=persistence_health(
                persistence.event_log_size,
                persistence.snapshot_schema_version,
                persistence.quarantined_tasks,
            ).value,
        )

    def _collect_founder_state(self) -> FounderStatePanelData:
        if self._mc is None:
            return FounderStatePanelData(
                status=PanelStatus.missing("no mission control attached")
            )
        try:
            return FounderStatePanelData(state=self._mc.founder_state().as_dict())
        except Exception as exc:  # noqa: BLE001
            return FounderStatePanelData(
                status=PanelStatus.missing(f"founder state unreadable: {exc}")
            )
