"""The standard Worker lifecycle (Mission Brief 023 deliverable #4).

Same shape as the existing Mission state machine
(mission_manager/mission.py): a closed enum plus one explicit table of
legal transitions, consulted before any state is mutated. That table is
what makes "what is this Worker doing right now" trustworthy for anything
reading it.

Transitions here are MECHANICAL. `RECOVERING` records that recovery is in
progress; it does not choose a recovery strategy. Strategic recovery is a
Brain responsibility (Constitution §11) and must never migrate into this
module. See MISSION_CONTROL_ARCHITECTURE.md §6.
"""
from __future__ import annotations

from enum import Enum


class WorkerState(str, Enum):
    CREATED = "created"
    INITIALIZED = "initialized"
    READY = "ready"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    RECOVERING = "recovering"
    STOPPED = "stopped"


# COMPLETED -> READY is deliberate and is the one edge that does not appear
# in the brief's linear diagram: this is a *Worker* lifecycle, and a Worker
# that finishes a task is available for the next one. Reading the brief's
# arrow list as literal one-way transitions would mean one Worker per task
# forever, contradicting Mission Brief 022's own BrowserSessionManager
# (many tasks, one live session). See MISSION_CONTROL_ARCHITECTURE.md §6.
_ALLOWED_TRANSITIONS: dict[WorkerState, set[WorkerState]] = {
    WorkerState.CREATED: {WorkerState.INITIALIZED, WorkerState.STOPPED},
    WorkerState.INITIALIZED: {WorkerState.READY, WorkerState.FAILED, WorkerState.STOPPED},
    WorkerState.READY: {WorkerState.RUNNING, WorkerState.STOPPED},
    WorkerState.RUNNING: {WorkerState.WAITING, WorkerState.COMPLETED, WorkerState.FAILED},
    WorkerState.WAITING: {WorkerState.RUNNING, WorkerState.FAILED, WorkerState.STOPPED},
    WorkerState.COMPLETED: {WorkerState.READY, WorkerState.STOPPED},
    WorkerState.FAILED: {WorkerState.RECOVERING, WorkerState.STOPPED},
    WorkerState.RECOVERING: {WorkerState.READY, WorkerState.FAILED, WorkerState.STOPPED},
    WorkerState.STOPPED: set(),
}

TERMINAL_STATES = frozenset({WorkerState.STOPPED})


class IllegalWorkerTransition(Exception):
    """Raised instead of silently allowing an impossible state change — the
    same posture mission_manager/mission.py's IllegalTransition takes."""


def can_transition(current: WorkerState, new: WorkerState) -> bool:
    return new in _ALLOWED_TRANSITIONS[current]


def assert_transition(current: WorkerState, new: WorkerState) -> None:
    if not can_transition(current, new):
        raise IllegalWorkerTransition(f"{current.value} -> {new.value} is not allowed")


def allowed_transitions(current: WorkerState) -> set[WorkerState]:
    return set(_ALLOWED_TRANSITIONS[current])
