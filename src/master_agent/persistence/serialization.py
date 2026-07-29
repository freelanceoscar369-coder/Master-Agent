"""Turning live objects into plain data and back.

Every function here is a pure translation between a frozen component's
*public* dataclasses and JSON-shaped dicts. Nothing reads a private
attribute (Rule 4), and nothing here writes to storage -- that is
store.py's sole job.

Transient runtime handles are never serialised. An ExecutiveRecord's
metadata is persisted; the live Plugin it describes is not, because a
process that has just started has no such object and must not pretend it
does (MB025 deliverable #5: "Do not persist transient runtime handles.
Only metadata").
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from master_agent.mission_control.audit import AuditEntry
from master_agent.mission_control.capabilities import CapabilityDescriptor
from master_agent.mission_control.events import Event, EventType
from master_agent.mission_control.executives import ExecutiveHealth, ExecutiveRecord
from master_agent.mission_control.lifecycle import WorkerState
from master_agent.mission_control.tasks import Objective, Task, TaskState

# Tasks in these states were in flight when the process died. Their side
# effects are unknown, so they are never silently re-run -- see
# PERSISTENCE_ARCHITECTURE.md §6 and ADR-0015 Decision 4.
INTERRUPTED_STATES = frozenset({TaskState.RUNNING, TaskState.DISPATCHED})

INTERRUPTED_ERROR = (
    "interrupted by shutdown; outcome unknown -- not retried automatically "
    "to avoid duplicate execution"
)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


# ---- tasks and objectives ------------------------------------------------


def task_to_dict(task: Task) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "capability": task.capability,
        "payload": dict(task.payload),
        "depends_on": list(task.depends_on),
        "state": task.state.value,
        "assigned_executive": task.assigned_executive,
        "result": task.result,
        "evidence_id": task.evidence_id,
        "errors": list(task.errors),
        "created_at": _iso(task.created_at),
        "started_at": _iso(task.started_at),
        "ended_at": _iso(task.ended_at),
        # expected_outcome is deliberately NOT persisted: it is a live
        # ExpectedOutcome object supplied by whoever built the plan, not
        # JSON-shaped state. A restored task keeps its history; a future
        # Planner re-attaches expectations when it re-plans. Named in
        # docs/MISSION_BRIEF_025.md rather than silently dropped.
    }


def task_from_dict(data: dict[str, Any], quarantine_interrupted: bool = True) -> Task:
    state = TaskState(data["state"])
    errors = list(data.get("errors", []))

    if quarantine_interrupted and state in INTERRUPTED_STATES:
        state = TaskState.FAILED
        errors.append(INTERRUPTED_ERROR)

    task = Task(
        capability=data["capability"],
        payload=dict(data.get("payload", {})),
        depends_on=list(data.get("depends_on", [])),
        task_id=data["task_id"],
        state=state,
        assigned_executive=data.get("assigned_executive"),
        result=data.get("result"),
        evidence_id=data.get("evidence_id"),
        errors=errors,
    )
    created = _parse_dt(data.get("created_at"))
    if created:
        task.created_at = created
    task.started_at = _parse_dt(data.get("started_at"))
    task.ended_at = _parse_dt(data.get("ended_at"))
    return task


def objective_to_dict(objective: Objective) -> dict[str, Any]:
    return {
        "objective_id": objective.objective_id,
        "description": objective.description,
        "created_at": _iso(objective.created_at),
        "tasks": [task_to_dict(task) for task in objective.tasks],
    }


def objective_from_dict(
    data: dict[str, Any], quarantine_interrupted: bool = True
) -> Objective:
    objective = Objective(
        description=data["description"],
        tasks=[
            task_from_dict(task, quarantine_interrupted) for task in data.get("tasks", [])
        ],
        objective_id=data["objective_id"],
    )
    created = _parse_dt(data.get("created_at"))
    if created:
        objective.created_at = created
    return objective


# ---- executives and capabilities ----------------------------------------


def executive_to_dict(record: ExecutiveRecord) -> dict[str, Any]:
    return {
        "executive_id": record.executive_id,
        "version": record.version,
        "capabilities": list(record.capabilities),
        "health": record.health.value,
        "state": record.state.value,
        "dependencies": list(record.dependencies),
        "current_task_id": record.current_task_id,
        "registered_at": _iso(record.registered_at),
        "updated_at": _iso(record.updated_at),
    }


def executive_from_dict(data: dict[str, Any]) -> ExecutiveRecord:
    """A restored Executive never keeps `current_task_id`: whatever it was
    working on was interrupted and quarantined, so claiming it is still
    busy would make it permanently unavailable for dispatch."""
    record = ExecutiveRecord(
        executive_id=data["executive_id"],
        version=data["version"],
        capabilities=list(data.get("capabilities", [])),
        health=ExecutiveHealth(data.get("health", "unknown")),
        state=WorkerState(data.get("state", "created")),
        dependencies=list(data.get("dependencies", [])),
        current_task_id=None,
    )
    registered = _parse_dt(data.get("registered_at"))
    if registered:
        record.registered_at = registered
    updated = _parse_dt(data.get("updated_at"))
    if updated:
        record.updated_at = updated
    return record


def capability_to_dict(descriptor: CapabilityDescriptor) -> dict[str, Any]:
    return {
        "qualified_name": descriptor.qualified_name,
        "executive_id": descriptor.executive_id,
        "capability": descriptor.capability,
        "description": descriptor.description,
        "risk_tier": descriptor.risk_tier,
        "permission_category": descriptor.permission_category,
        "metadata": dict(descriptor.metadata),
    }


def capability_from_dict(data: dict[str, Any]) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        qualified_name=data["qualified_name"],
        executive_id=data["executive_id"],
        capability=data["capability"],
        description=data.get("description", ""),
        risk_tier=data.get("risk_tier"),
        permission_category=data.get("permission_category"),
        metadata=dict(data.get("metadata", {})),
    )


# ---- events and audit ----------------------------------------------------


def event_to_dict(event: Event) -> dict[str, Any]:
    return event.as_dict()


def event_from_dict(data: dict[str, Any]) -> Event:
    """Rebuilds an Event faithfully -- same event_id, same timestamp. This
    is what lets AuditStream.record() reconstruct history identically,
    with no change to the frozen audit component."""
    occurred = _parse_dt(data.get("occurred_at")) or datetime.now(UTC)
    return Event(
        event_type=EventType(data["event_type"]),
        source=data["source"],
        event_id=data["event_id"],
        occurred_at=occurred,
        objective_id=data.get("objective_id"),
        task_id=data.get("task_id"),
        capability=data.get("capability"),
        payload=dict(data.get("payload", {})),
        error=data.get("error"),
    )


def audit_entry_to_dict(entry: AuditEntry) -> dict[str, Any]:
    return entry.as_dict()


def audit_entry_to_event(entry: AuditEntry) -> Event:
    """An AuditEntry carries everything an Event does, so history can be
    replayed back through the audit's own public `record()`."""
    return Event(
        event_type=entry.event_type,
        source=entry.source,
        event_id=entry.event_id,
        occurred_at=entry.occurred_at,
        objective_id=entry.objective_id,
        task_id=entry.task_id,
        capability=entry.capability,
        payload=dict(entry.payload),
        error=entry.error,
    )
