"""Restart recovery (Mission Brief 025 deliverable #8).

    On startup: detect existing state, restore Runtime, restore Queue,
    restore Mission Control, resume execution safely. No duplicate task
    execution. Founder performs no manual recovery.

`recover()` is the one call a launcher makes. Everything about *how*
state comes back -- snapshot versus replay, what happens to interrupted
work -- is decided here, so no caller has to know.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from master_agent.mission_control.mission_control import MissionControl
from master_agent.persistence.replay import replay_events_into
from master_agent.persistence.schema import CorruptSnapshot, UnsupportedSchemaVersion
from master_agent.persistence.service import PersistenceService
from master_agent.runtime.checkpoint import RuntimeCheckpoint


@dataclass
class RecoveryReport:
    """What recovery actually did -- returned rather than logged, so a
    launcher can surface it and a test can assert on it."""

    recovered: bool = False
    source: str = "none"  # "none" | "snapshot" | "event_replay"
    executives: int = 0
    capabilities: int = 0
    objectives: int = 0
    audit_entries: int = 0
    quarantined_tasks: int = 0
    checkpoint: RuntimeCheckpoint | None = None
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "recovered": self.recovered,
            "source": self.source,
            "executives": self.executives,
            "capabilities": self.capabilities,
            "objectives": self.objectives,
            "audit_entries": self.audit_entries,
            "quarantined_tasks": self.quarantined_tasks,
            "warnings": list(self.warnings),
        }


def count_quarantined(mission_control: MissionControl) -> int:
    from master_agent.persistence.serialization import INTERRUPTED_ERROR

    return sum(
        1
        for objective in mission_control.dispatcher.objectives()
        for task in objective.tasks
        if any(INTERRUPTED_ERROR in error for error in task.errors)
    )


def recover(
    service: PersistenceService,
    mission_control: MissionControl,
    runtime: Any = None,
) -> RecoveryReport:
    """Restore everything that survived, into a fresh Mission Control.

    Falls back from snapshot to event replay when the snapshot is missing
    or unusable -- a corrupt snapshot must never mean "start from
    nothing" while a perfectly good event log sits next to it.
    """
    report = RecoveryReport()

    if not service.has_state():
        return report

    envelope = None
    try:
        envelope = service.load()
    except (CorruptSnapshot, UnsupportedSchemaVersion) as exc:
        report.warnings.append(f"snapshot unusable ({exc}); falling back to event replay")

    if envelope is not None:
        counts = service.restore_into(mission_control, envelope)
        report.source = "snapshot"
        report.executives = counts["executives"]
        report.capabilities = counts["capabilities"]
        report.objectives = counts["objectives"]
        report.audit_entries = counts["audit_entries"]
        runtime_payload = envelope.payload.get("runtime")
        if runtime_payload:
            report.checkpoint = RuntimeCheckpoint.from_dict(runtime_payload)
    else:
        events = service.store.read_events()
        if not events:
            return report
        counts = replay_events_into(mission_control, events)
        report.source = "event_replay"
        report.executives = counts["executives"]
        report.capabilities = counts["capabilities"]
        report.objectives = counts["objectives"]
        report.audit_entries = service.restore_audit_into(mission_control)

    report.recovered = (
        report.objectives > 0 or report.executives > 0 or report.audit_entries > 0
    )
    report.quarantined_tasks = count_quarantined(mission_control)

    if runtime is not None and report.checkpoint is not None:
        runtime.restore_from(report.checkpoint)

    return report
