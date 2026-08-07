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
    UNAVAILABLE,
    ApprovalPanelData,
    ApprovalRow,
    AuditPanelData,
    AuditRow,
    BrokerDecisionRow,
    BrokerPanelData,
    CapabilityPanelData,
    DashboardSnapshot,
    ExecutionRow,
    ExecutivePanelData,
    ExecutiveRow,
    FounderStatePanelData,
    MachinePanelData,
    MachineRow,
    MemoryPanelData,
    MemoryRow,
    MissionPanelData,
    PanelStatus,
    PersistencePanelData,
    PlanPanelData,
    PlanStepRow,
    RuntimePanelData,
    SystemHealthPanelData,
    TokenEconomyRow,
)

DEFAULT_AUDIT_WINDOW = 20
#: How many Broker decisions the founder page shows. Small on purpose: the
#: panel answers "what is it choosing, and why", not "what has it ever
#: chosen" -- the ledger keeps the whole history for that.
DEFAULT_DECISION_WINDOW = 3


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


def _duration(latency_ms: float | None) -> str:
    """`1.7 s`, or the marker. MB033's founder view names seconds, because
    a founder waiting for a local model is counting in seconds, not
    milliseconds."""
    if latency_ms is None:
        return UNAVAILABLE
    if latency_ms < 1000:
        return f"{round(latency_ms)} ms"
    return f"{latency_ms / 1000:.1f} s"


def _money(cost: float | None) -> str:
    """`Free`, or the number. Never a bare `0` -- see `tiers.cost_tier`
    for why an unrecorded cost is not a free one."""
    if cost is None:
        return UNAVAILABLE
    return "Free" if cost <= 0 else f"{cost:.4f}"


def _execution_row(entry: Any) -> ExecutionRow | None:
    """MB033: the last execution, as plain data. Nothing is computed here
    that the execution record did not already state."""
    if entry is None or entry.execution is None:
        return None
    execution = entry.execution
    return ExecutionRow(
        provider_id=execution.provider_id,
        outcome=execution.outcome,
        succeeded=execution.succeeded,
        latency=_duration(execution.latency_ms),
        cost=_money(execution.cost),
        cache=execution.cache,
        model=execution.model,
        tokens=execution.total_tokens,
        retries=execution.retries,
        error=execution.error,
        verified=_verdict(execution.verdict),
        budget=_budget_line(execution.budget),
        bound_by=((execution.budget or {}).get("derivation") or {}).get(
            "total_bound_by", ""
        ),
        timeout_reason=(execution.timeout or {}).get("reason", ""),
        admission=execution.admission,
        lifecycle=execution.lifecycle,
    )


def _budget_line(budget: Any) -> str:
    """The three deadlines, as one readable line.

    Absent when the call carried no budget. A founder seeing nothing here
    is being told the truth about a pre-MB038 or unbudgeted call, not
    shown a zero.
    """
    if not budget:
        return ""
    total = (budget.get("total_ms") or 0) / 1000
    ttft = (budget.get("ttft_ms") or 0) / 1000
    itl = (budget.get("itl_ms") or 0) / 1000
    return f"{total:.0f}s total / {ttft:.0f}s first token / {itl:.0f}s stall"


def _verdict(verdict: str) -> str:
    """MB035, in the founder's words. "not checked" and "not matched" are
    different facts and must not both render as a blank."""
    if not verdict:
        return "not checked"
    return verdict.replace("_", " ")


def _plan_step_row(step: Any, record: Any, blocked: set[str]) -> PlanStepRow:
    """One step, with *why* it is not running when it is not.

    `blocked_by` names the dependencies that have not completed, rather
    than only saying "waiting" -- MB029's rule that a founder-facing state
    carries its reason, applied to the one state that is otherwise
    indistinguishable from being stuck.
    """
    waiting = (
        [
            dependency
            for dependency in step.depends_on
            if (record.step(dependency) is None or record.step(dependency).state != "completed")
        ]
        if step.step_id in blocked
        else []
    )
    # Found by running MB037: a step whose dependency *failed* was
    # reported as "waiting on step_1" -- true, and misleading, because it
    # will never run. Mission Control already marks the task BLOCKED; the
    # founder page had no word for it.
    unreachable = any(
        (record.step(dependency) is not None and record.step(dependency).state == "failed")
        for dependency in waiting
    )
    return PlanStepRow(
        step_id=step.step_id,
        capability=step.capability,
        state=step.state,
        verdict=step.verdict,
        priority=step.priority,
        complexity=step.estimated_complexity,
        expectation=step.expectation,
        blocked_by=waiting,
        unreachable=unreachable,
        errors=list(step.errors),
    )


def _memory_row(record: Any) -> MemoryRow | None:
    if record is None:
        return None
    return MemoryRow(
        id=record.id,
        title=record.title,
        category=record.category,
        importance=record.importance,
        written_at=record.updated_at.strftime("%d %b %H:%M"),
        tags=list(record.tags),
    )


def _economy_row(economy: Any) -> TokenEconomyRow:
    if economy is None:
        return TokenEconomyRow()
    return TokenEconomyRow(
        local_executions=economy.local_executions,
        cloud_executions=economy.cloud_executions,
        cache_hits=economy.cache_hits,
        cache_misses=economy.cache_misses,
        avoided_cloud_executions=economy.avoided_cloud_executions,
        money_saved=economy.money_saved,
        total_spend=economy.total_spend,
        failed_executions=economy.failed_executions,
        total_tokens=economy.total_tokens,
        basis=economy.basis,
    )


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
        inventory_provider: Any = None,
        runtime: RuntimeReader | None = None,
        persistence: PersistenceReader | None = None,
        recovery_report: Any = None,
        audit_window: int = DEFAULT_AUDIT_WINDOW,
        clock: Any = None,
        broker_provider: Any = None,
        decision_window: int = DEFAULT_DECISION_WINDOW,
        memory_provider: Any = None,
        plan_provider: Any = None,
    ) -> None:
        self._mc = mission_control
        self._inventory_provider = inventory_provider
        self._broker_provider = broker_provider
        self._decision_window = decision_window
        self._memory_provider = memory_provider
        self._plan_provider = plan_provider
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
            approvals=self._collect_approvals(),
            machine=self._collect_machine(),
            broker=self._collect_broker(),
            memory=self._collect_memory(),
            plan=self._collect_plan(),
        )

    # ---- panels ------------------------------------------------------

    def _collect_plan(self) -> PlanPanelData:
        """MB037's CURRENT MISSION section. Reads a `PlanHistory` handed in
        by the launcher; derives no state of its own beyond counting the
        rows the history already classified."""
        if self._plan_provider is None:
            return PlanPanelData(status=PanelStatus.missing("no planner attached"))
        try:
            history = self._plan_provider()
        except Exception as exc:  # noqa: BLE001 - a failed read is absent data
            return PlanPanelData(status=PanelStatus.missing(str(exc)))
        if history is None:
            return PlanPanelData(status=PanelStatus.missing("no plan history"))

        record = history.current()
        if record is None:
            return PlanPanelData(
                status=PanelStatus.missing("nothing planned yet"),
                history_count=len(history.all()),
            )

        blocked = {step.step_id for step in record.blocked}
        rows = [_plan_step_row(step, record, blocked) for step in record.steps]
        current = record.current
        return PlanPanelData(
            # Explicit: `PlanPanelData` defaults to *absent*, because a
            # plan does not exist until somebody asks for something. This
            # is the one place that knows one does.
            status=PanelStatus(),
            objective=record.objective,
            plan_id=record.plan_id,
            state=record.state,
            steps=rows,
            current=_plan_step_row(current, record, blocked) if current else None,
            completed=len(record.completed),
            remaining=len(record.remaining),
            blocked=len(blocked),
            failed=len(record.failed),
            unverified=len(record.unverified),
            progress=record.progress,
            planned_by=record.planned_by,
            history_count=len(history.all()),
        )

    def _collect_memory(self) -> MemoryPanelData:
        """MB034's MEMORY section. Reads a `MemorySummary` handed in by the
        launcher; counts nothing and classifies nothing of its own."""
        if self._memory_provider is None:
            return MemoryPanelData(
                status=PanelStatus.missing("no founder memory attached")
            )
        try:
            summary = self._memory_provider()
        except Exception as exc:  # noqa: BLE001 - a failed read is absent data
            return MemoryPanelData(status=PanelStatus.missing(str(exc)))
        if summary is None:
            return MemoryPanelData(
                status=PanelStatus.missing("founder memory reported nothing")
            )

        return MemoryPanelData(
            total=summary.total,
            critical=summary.critical,
            recent=[_memory_row(record) for record in summary.recent],
            top_tags=[(tag, count) for tag, count in summary.top_tags],
            last_written=_memory_row(summary.last_written),
            problems=list(summary.problems),
        )

    def _collect_broker(self) -> BrokerPanelData:
        """MB032 Deliverable 9. Reads a `BrokerReport` handed in by the
        launcher -- already tiered, already counted -- and reshapes it into
        rows. No classification happens here, and none can: there is
        nothing to classify with."""
        if self._broker_provider is None:
            return BrokerPanelData(
                status=PanelStatus.missing("no AI Capability Broker attached")
            )
        try:
            report = self._broker_provider()
        except Exception as exc:  # noqa: BLE001 - a failed read is absent data
            return BrokerPanelData(status=PanelStatus.missing(str(exc)))
        if report is None:
            return BrokerPanelData(
                status=PanelStatus.missing("the Broker reported nothing")
            )

        window = list(report.decisions)[: self._decision_window]
        return BrokerPanelData(
            policy_version=report.policy_version,
            providers_available=report.providers_available,
            providers_total=report.providers_total,
            scanned=report.scanned,
            total_decisions=report.total_decisions,
            awaiting_approval=report.awaiting_approval,
            decisions=[
                BrokerDecisionRow(
                    task_id=entry.task_id,
                    capability=entry.capability,
                    outcome=entry.outcome,
                    provider_id=entry.provider_id,
                    reason=entry.reason,
                    cost_tier=entry.cost_tier,
                    quality_tier=entry.quality_tier,
                    cost_detail=entry.cost_detail,
                    quality_detail=entry.quality_detail,
                    policy_version=entry.policy_version,
                    decided_at=entry.decided_at.strftime("%H:%M"),
                    approval_state=entry.approval_state,
                    locality=entry.locality,
                )
                for entry in window
            ],
            recording_failures=list(report.recording_failures),
            last_execution=_execution_row(report.last_execution),
            economy=_economy_row(report.economy),
        )

    def _collect_machine(self) -> MachinePanelData:
        """MB030 Deliverables 4 and 9. The inventory is *handed in* by the
        launcher, never discovered here: a render that scanned the machine
        would mean looking at the screen changes what the screen reports
        (ADR-0016 Decision 5, ADR-0016's read-only rule)."""
        if self._inventory_provider is None:
            return MachinePanelData(
                status=PanelStatus.missing("no desktop executive attached")
            )
        try:
            inventory = self._inventory_provider()
        except Exception as exc:  # noqa: BLE001 - a failed read is absent data
            return MachinePanelData(status=PanelStatus.missing(str(exc)))
        if inventory is None:
            return MachinePanelData(
                status=PanelStatus.missing("no machine scan has run yet")
            )

        from master_agent.desktop.catalog import BY_KEY, READINESS_KEYS

        def row(application) -> MachineRow:
            return MachineRow(
                label=application.name,
                status=application.status,
                version=application.version,
                detail=application.detail,
            )

        readiness = []
        for key in READINESS_KEYS:
            application = inventory.get(key)
            if application is None:
                spec = BY_KEY.get(key)
                readiness.append(
                    MachineRow(
                        label=spec.label if spec else key, status="unavailable"
                    )
                )
            else:
                readiness.append(row(application))

        owners = {p.owner for p in inventory.processes if p.owner}
        return MachinePanelData(
            readiness=readiness,
            installed=[row(a) for a in inventory.installed()],
            running=sorted(
                BY_KEY[key].label for key in owners if key in BY_KEY
            ),
            unavailable=[row(a) for a in inventory.unavailable()],
            missing_recommended=[a.name for a in inventory.missing_recommended()],
            ai_installed=[
                a.name for a in inventory.ai_applications() if a.installed
            ],
        )

    def _collect_approvals(self) -> ApprovalPanelData:
        """Reads `MissionControl.approvals` -- a public attribute, so this
        is contract use, not private access. Tolerant like every other
        read: an unreadable queue becomes absent data with a reason, never
        an empty list that looks like "nothing is waiting on you"."""
        if self._mc is None:
            return ApprovalPanelData(
                status=PanelStatus.missing("no mission control attached")
            )
        try:
            rows = [
                ApprovalRow(
                    index=position,
                    approval_id=approval.approval_id,
                    capability=approval.capability,
                    executive_id=approval.executive_id,
                    risk_tier=approval.risk_tier,
                    reason=approval.reason,
                    impact=approval.impact,
                    requested_at=approval.requested_at.strftime("%H:%M"),
                    state=approval.state.value,
                    objective=approval.objective,
                )
                for position, approval in enumerate(
                    self._mc.approvals.open(), start=1
                )
            ]
            return ApprovalPanelData(approvals=rows)
        except Exception as exc:  # noqa: BLE001 - a failed read is absent data
            return ApprovalPanelData(status=PanelStatus.missing(str(exc)))


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
