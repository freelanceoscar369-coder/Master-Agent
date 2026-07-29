"""Event replay (Mission Brief 025 deliverable #9).

    "Mission Control must be capable of rebuilding its internal state by
     replaying persisted events."

This is a genuine, tested capability -- not the everyday restart path.
Snapshot restore is primary because its cost is O(live state) rather than
O(all history); replay exists as a repair path for when a snapshot is
missing or corrupt, and as the answer to "can we reconstruct from the log
alone?"

Replay reads the event log and reconstructs state through Mission
Control's public contracts only (Rule 4). It publishes nothing: the
events being replayed already happened, and announcing them again would
make the rebuilt history claim everything occurred twice.
"""
from __future__ import annotations

from typing import Any

from master_agent.mission_control.capabilities import CapabilityDescriptor
from master_agent.mission_control.events import EventType
from master_agent.mission_control.executives import ExecutiveHealth, ExecutiveRecord
from master_agent.mission_control.lifecycle import WorkerState
from master_agent.mission_control.mission_control import MissionControl
from master_agent.mission_control.tasks import Objective, Task, TaskState
from master_agent.persistence.serialization import INTERRUPTED_ERROR, event_from_dict


def replay_events_into(
    mission_control: MissionControl,
    events: list[dict[str, Any]],
    quarantine_interrupted: bool = True,
) -> dict[str, int]:
    """Rebuild executives, capabilities, objectives, and task states from
    an ordered event log. Returns counts of what was reconstructed.

    Only the event types that *carry* state are interpreted; everything
    else (runtime heartbeats, idle notices) is history, not state, and is
    skipped. An unknown event type is skipped rather than fatal, so a log
    written by a newer build still replays as far as it can.
    """
    counts = {"executives": 0, "capabilities": 0, "objectives": 0, "tasks": 0}
    objectives: dict[str, Objective] = {}
    task_index: dict[str, tuple[str, Task]] = {}

    for raw in events:
        try:
            event = event_from_dict(raw)
        except (KeyError, ValueError):
            continue

        payload = event.payload or {}

        if event.event_type is EventType.EXECUTIVE_REGISTERED:
            executive_id = payload.get("executive_id")
            if executive_id and not mission_control.executives.has(executive_id):
                try:
                    health = ExecutiveHealth(payload.get("health", "unknown"))
                except ValueError:
                    health = ExecutiveHealth.UNKNOWN
                mission_control.executives.register(
                    ExecutiveRecord(
                        executive_id=executive_id,
                        version=str(payload.get("version", "unknown")),
                        health=health,
                        dependencies=list(payload.get("dependencies", [])),
                    )
                )
                counts["executives"] += 1

        elif event.event_type is EventType.CAPABILITY_REGISTERED:
            qualified = event.capability
            executive_id = payload.get("executive_id")
            if qualified and executive_id and not mission_control.capabilities.has(qualified):
                mission_control.capabilities.register(
                    CapabilityDescriptor(
                        qualified_name=qualified,
                        executive_id=executive_id,
                        capability=qualified.split(".", 1)[-1],
                        risk_tier=payload.get("risk_tier"),
                    )
                )
                counts["capabilities"] += 1
                record = mission_control.executives.get(executive_id) if (
                    mission_control.executives.has(executive_id)
                ) else None
                if record is not None and qualified not in record.capabilities:
                    record.capabilities.append(qualified)

        elif event.event_type is EventType.WORKER_STATE_CHANGED:
            executive_id = payload.get("executive_id")
            target = payload.get("to")
            if executive_id and target and mission_control.executives.has(executive_id):
                record = mission_control.executives.get(executive_id)
                try:
                    record.state = WorkerState(target)
                except ValueError:
                    pass

        elif event.event_type is EventType.EXECUTIVE_HEALTH_CHANGED:
            executive_id = payload.get("executive_id")
            target = payload.get("to")
            if executive_id and target and mission_control.executives.has(executive_id):
                try:
                    mission_control.executives.set_health(
                        executive_id, ExecutiveHealth(target)
                    )
                except ValueError:
                    pass

        elif event.event_type is EventType.OBJECTIVE_SUBMITTED:
            if event.objective_id and event.objective_id not in objectives:
                objectives[event.objective_id] = Objective(
                    description=str(payload.get("description", "restored objective")),
                    tasks=[],
                    objective_id=event.objective_id,
                )
                counts["objectives"] += 1

        elif event.event_type is EventType.TASK_CREATED:
            objective = objectives.get(event.objective_id or "")
            if objective is not None and event.task_id and event.capability:
                task = Task(
                    capability=event.capability,
                    task_id=event.task_id,
                    depends_on=list(payload.get("depends_on", [])),
                    state=TaskState.CREATED,
                )
                objective.tasks.append(task)
                task_index[event.task_id] = (objective.objective_id, task)
                counts["tasks"] += 1

        elif event.event_type is EventType.TASK_ASSIGNED:
            entry = task_index.get(event.task_id or "")
            if entry:
                entry[1].state = TaskState.DISPATCHED
                entry[1].assigned_executive = payload.get("executive_id")

        elif event.event_type is EventType.TASK_STARTED:
            entry = task_index.get(event.task_id or "")
            if entry:
                entry[1].state = TaskState.RUNNING
                entry[1].started_at = event.occurred_at

        elif event.event_type is EventType.TASK_COMPLETED:
            entry = task_index.get(event.task_id or "")
            if entry:
                entry[1].state = TaskState.COMPLETED
                entry[1].evidence_id = payload.get("evidence_id")
                entry[1].ended_at = event.occurred_at

        elif event.event_type is EventType.TASK_FAILED:
            entry = task_index.get(event.task_id or "")
            if entry:
                entry[1].state = TaskState.FAILED
                entry[1].ended_at = event.occurred_at
                if event.error:
                    entry[1].errors.append(event.error)

        elif event.event_type is EventType.TASK_BLOCKED:
            entry = task_index.get(event.task_id or "")
            if entry and entry[1].state not in {TaskState.COMPLETED, TaskState.FAILED}:
                entry[1].state = TaskState.BLOCKED

    # Reconcile each Executive's capability list in a second pass.
    # CAPABILITY_REGISTERED is published *before* EXECUTIVE_REGISTERED, so
    # a single forward pass cannot link them -- doing it here makes the
    # result independent of event ordering.
    for descriptor in mission_control.capabilities.all():
        if not mission_control.executives.has(descriptor.executive_id):
            continue
        record = mission_control.executives.get(descriptor.executive_id)
        if descriptor.qualified_name not in record.capabilities:
            record.capabilities.append(descriptor.qualified_name)

    for objective in objectives.values():
        if quarantine_interrupted:
            for task in objective.tasks:
                if task.state in {TaskState.RUNNING, TaskState.DISPATCHED}:
                    task.state = TaskState.FAILED
                    task.errors.append(INTERRUPTED_ERROR)
        mission_control.restore_objective(objective)

    return counts
