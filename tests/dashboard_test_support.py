"""Shared fixtures for the Founder Dashboard suite (not a test module).

Builds real systems -- real MissionControl, real RuntimeEngine, real
persistence -- because MB026's central claim is that the Dashboard works
against *published contracts*, and a fake shaped for the Dashboard would
not test that claim.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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
from master_agent.executor.executor import LocalExecutor
from master_agent.mission_control.adapters import discover_executives
from master_agent.mission_control.mission_control import MissionControl
from master_agent.mission_control.tasks import Objective, Task
from master_agent.permissions.permission_system import GrantScope, PermissionSystem
from master_agent.persistence.service import PersistenceService
from master_agent.persistence.store import JsonFileStateStore
from master_agent.plugins.base import RiskTier
from master_agent.plugins.filesystem_plugin import FilesystemPlugin
from master_agent.plugins.registry import PluginRegistry
from master_agent.runtime.approval import PermissionSystemGate
from master_agent.runtime.config import RuntimeConfig
from master_agent.runtime.engine import RuntimeEngine
from master_agent.runtime.gateway import PluginGateway

FIXED_NOW = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)


class System:
    """A complete, real Kalpavriksha wired the way a launcher would."""

    def __init__(self, state_dir: Path, work_dir: Path, max_cycles: int = 4):
        self.permissions = PermissionSystem()
        self.executor = LocalExecutor(self.permissions)
        self.plugin = FilesystemPlugin(self.executor, locations={"desktop": work_dir})
        self.registry = PluginRegistry()
        self.registry.register(self.plugin)

        self.mission_control = MissionControl()
        self.service = PersistenceService(JsonFileStateStore(state_dir), self.mission_control)
        self.service.start_recording()
        discover_executives(self.mission_control, self.registry)

        # MB028.0: the real approval boundary, not a stand-in. This
        # fixture's whole claim is that it is "a complete, real
        # Kalpavriksha wired the way a launcher would" -- so it uses the
        # same `PermissionSystemGate` the launcher does, delegating to the
        # same Permission System the Orchestrator uses. `approve_all()`
        # below is what stands in for the founder.
        self.approval_gate = PermissionSystemGate(self.permissions, self.registry)
        self.engine = RuntimeEngine(
            self.mission_control,
            RuntimeConfig(poll_interval_seconds=0, max_cycles=max_cycles),
            sleep=lambda _s: None,
            checkpoint_sink=self.service,
            approval_gate=self.approval_gate,
        )
        self.approve_all()
        self.engine.register_gateway(
            "filesystem",
            PluginGateway(
                self.plugin,
                grant_permission=lambda c: self.permissions.grant(
                    self.executor.name, c, GrantScope.ONCE
                ),
            ),
        )

    def approve_all(self) -> None:
        """The founder, having approved. Grants on the **plugin/capability**
        key -- the key the approval boundary checks -- which is a different
        key from the Executor's (ADR-0005). `IRREVERSIBLE` capabilities are
        excluded because ADR-0009 makes a standing grant unable to satisfy
        them anyway; asking for one here would be asking for something the
        Permission System is built to refuse."""
        for capability in self.plugin.manifest.capabilities:
            if capability.risk_tier is RiskTier.IRREVERSIBLE:
                continue
            self.permissions.grant(
                self.plugin.manifest.name, capability.name, GrantScope.THIS_SESSION
            )

    def submit(self, description: str = "Increase Founder Net Worth") -> Objective:
        return self.mission_control.submit_objective(
            Objective(
                description=description,
                tasks=[
                    Task(
                        capability="Filesystem.CreateFolder",
                        payload={"name": "W"},
                        task_id="t1",
                    ),
                    Task(
                        capability="Filesystem.WriteFile",
                        payload={"path": "W/a.txt", "content": "x"},
                        task_id="t2",
                        depends_on=["t1"],
                    ),
                    Task(
                        capability="Filesystem.WriteFile",
                        payload={"path": "W/b.txt", "content": "y"},
                        task_id="t3",
                        depends_on=["t2"],
                    ),
                ],
            )
        )

    def run(self) -> None:
        self.engine.run_forever()

    def save(self) -> None:
        self.service.save(self.mission_control, self.engine.checkpoint())


# ---- read-model builders for pure panel tests --------------------------


def runtime_data(**kwargs: Any) -> RuntimePanelData:
    defaults = {
        "state": "idle",
        "uptime_seconds": 125.0,
        "active_cycle": 7,
        "queue_length": 2,
        "last_dispatch_at": FIXED_NOW,
        "last_verification_at": FIXED_NOW,
        "executives_online": 1,
        "executives_busy": 0,
        "tasks_completed": 3,
        "tasks_failed": 0,
    }
    defaults.update(kwargs)
    return RuntimePanelData(**defaults)


def mission_data(**kwargs: Any) -> MissionPanelData:
    defaults = {
        "objective": "Increase Founder Net Worth",
        "objective_id": "obj-1",
        "progress": 0.5,
        "active_executive": "browser",
        "active_capability": "Browser.Navigate",
        "eta_seconds": 30.0,
        "mission_status": "in progress",
        "evidence_count": 1,
    }
    defaults.update(kwargs)
    return MissionPanelData(**defaults)


def executive_data(count: int = 1, **kwargs: Any) -> ExecutivePanelData:
    rows = [
        ExecutiveRow(
            executive_id=f"exec{index}",
            health="healthy",
            version="1.0.0",
            state="ready",
            capability_count=9,
        )
        for index in range(count)
    ]
    return ExecutivePanelData(executives=kwargs.pop("executives", rows), **kwargs)


def capability_data(**kwargs: Any) -> CapabilityPanelData:
    defaults = {
        "registered": ["Browser.Navigate", "Browser.Click"],
        "pending": 1,
        "active": 1,
        "completed": 2,
        "failed": 0,
        "blocked": 0,
    }
    defaults.update(kwargs)
    return CapabilityPanelData(**defaults)


def audit_data(rows: int = 3, **kwargs: Any) -> AuditPanelData:
    recent = [
        AuditRow(
            sequence=index,
            event_type="task_completed",
            occurred_at=FIXED_NOW,
            source="mission_control",
            task_id=f"t{index}",
            capability="Browser.Navigate",
        )
        for index in range(rows)
    ]
    defaults = {"recent": recent, "total_entries": rows, "failures": 0}
    defaults.update(kwargs)
    return AuditPanelData(**defaults)


def persistence_data(**kwargs: Any) -> PersistencePanelData:
    defaults = {
        "last_checkpoint_at": FIXED_NOW,
        "snapshot_schema_version": 1,
        "snapshot_created_at": FIXED_NOW,
        "event_log_size": 42,
        "recovery_status": "recovered",
        "recovery_source": "snapshot",
        "quarantined_tasks": 0,
    }
    defaults.update(kwargs)
    return PersistencePanelData(**defaults)


def system_health_data(**kwargs: Any) -> SystemHealthPanelData:
    defaults = {
        "executives_online": 1,
        "runtime_health": "healthy",
        "queue_health": "healthy",
        "audit_health": "healthy",
        "persistence_health": "healthy",
    }
    defaults.update(kwargs)
    return SystemHealthPanelData(**defaults)


def founder_state_data(**kwargs: Any) -> FounderStatePanelData:
    defaults = {
        "state": {
            "current_mission": "Increase Founder Net Worth",
            "progress": 0.5,
            "errors": [],
        }
    }
    defaults.update(kwargs)
    return FounderStatePanelData(**defaults)


def full_snapshot(**kwargs: Any) -> DashboardSnapshot:
    defaults = {
        "captured_at": FIXED_NOW,
        "runtime": runtime_data(),
        "mission": mission_data(),
        "executives": executive_data(),
        "capabilities": capability_data(),
        "audit": audit_data(),
        "persistence": persistence_data(),
        "system_health": system_health_data(),
        "founder_state": founder_state_data(),
    }
    defaults.update(kwargs)
    return DashboardSnapshot(**defaults)


def empty_snapshot() -> DashboardSnapshot:
    """Every panel unavailable -- what a Dashboard wired to nothing sees."""
    missing = PanelStatus.missing("not attached")
    return DashboardSnapshot(
        captured_at=FIXED_NOW,
        runtime=RuntimePanelData(status=missing),
        mission=MissionPanelData(status=missing),
        executives=ExecutivePanelData(status=missing),
        capabilities=CapabilityPanelData(status=missing),
        audit=AuditPanelData(status=missing),
        persistence=PersistencePanelData(status=missing),
        system_health=SystemHealthPanelData(status=missing),
        founder_state=FounderStatePanelData(status=missing),
    )
