"""Runtime Engine states (Mission Brief 024 deliverable #2).

Same shape as every other state machine in this codebase (`Mission`,
`WorkerState`): a closed enum plus one explicit table of legal
transitions, consulted before any state is mutated.
"""
from __future__ import annotations

from enum import Enum


class RuntimeState(str, Enum):
    INITIALIZING = "initializing"
    IDLE = "idle"
    DISPATCHING = "dispatching"
    WAITING = "waiting"
    VERIFYING = "verifying"
    RECOVERING = "recovering"
    STOPPING = "stopping"
    STOPPED = "stopped"


# IDLE is where a healthy Runtime spends most of its life -- there is
# usually no work ready, and that is a resting state, not an error.
# DISPATCHING -> IDLE therefore exists for the common case of a poll that
# found nothing. See RUNTIME_ENGINE_ARCHITECTURE.md §3.
_ALLOWED_TRANSITIONS: dict[RuntimeState, set[RuntimeState]] = {
    RuntimeState.INITIALIZING: {
        RuntimeState.IDLE,
        RuntimeState.STOPPING,
        RuntimeState.STOPPED,
    },
    RuntimeState.IDLE: {RuntimeState.DISPATCHING, RuntimeState.STOPPING},
    RuntimeState.DISPATCHING: {
        RuntimeState.WAITING,
        RuntimeState.VERIFYING,
        RuntimeState.IDLE,
        RuntimeState.RECOVERING,
        RuntimeState.STOPPING,
    },
    RuntimeState.WAITING: {
        RuntimeState.VERIFYING,
        RuntimeState.RECOVERING,
        RuntimeState.IDLE,
        RuntimeState.STOPPING,
    },
    RuntimeState.VERIFYING: {
        RuntimeState.IDLE,
        RuntimeState.RECOVERING,
        RuntimeState.STOPPING,
    },
    RuntimeState.RECOVERING: {
        RuntimeState.DISPATCHING,
        # RECOVERING -> WAITING is the retry-resume edge: a mechanical
        # retry recovers, then goes back to waiting on the same Executive
        # for the next attempt. Missing from the first draft of this
        # table, which made every retry crash its own cycle -- found by
        # the smoke test, not by inspection.
        RuntimeState.WAITING,
        RuntimeState.IDLE,
        RuntimeState.STOPPING,
    },
    RuntimeState.STOPPING: {RuntimeState.STOPPED},
    RuntimeState.STOPPED: set(),
}

TERMINAL_STATES = frozenset({RuntimeState.STOPPED})


class IllegalRuntimeTransition(Exception):
    pass


def can_transition(current: RuntimeState, new: RuntimeState) -> bool:
    return new in _ALLOWED_TRANSITIONS[current]


def assert_transition(current: RuntimeState, new: RuntimeState) -> None:
    if not can_transition(current, new):
        raise IllegalRuntimeTransition(f"{current.value} -> {new.value} is not allowed")


def allowed_transitions(current: RuntimeState) -> set[RuntimeState]:
    return set(_ALLOWED_TRANSITIONS[current])
