"""Worker Lifecycle tests (Mission Brief 023 deliverable #4).
See MISSION_CONTROL_ARCHITECTURE.md §6.
"""
from __future__ import annotations

from itertools import pairwise

import pytest

from master_agent.mission_control.lifecycle import (
    IllegalWorkerTransition,
    WorkerState,
    allowed_transitions,
    assert_transition,
    can_transition,
)


def test_all_nine_brief_named_states_exist():
    expected = {
        "created",
        "initialized",
        "ready",
        "running",
        "waiting",
        "completed",
        "failed",
        "recovering",
        "stopped",
    }
    assert {member.value for member in WorkerState} == expected


def test_the_happy_path_walks_created_to_completed():
    path = [
        WorkerState.CREATED,
        WorkerState.INITIALIZED,
        WorkerState.READY,
        WorkerState.RUNNING,
        WorkerState.COMPLETED,
    ]
    for current, following in pairwise(path):
        assert can_transition(current, following), f"{current} -> {following} should be legal"


def test_completed_returns_to_ready_so_a_worker_can_take_another_task():
    """The one edge not in the brief's linear diagram, and the reason is
    architectural: a Worker that finishes a task is available for the next
    one (MISSION_CONTROL_ARCHITECTURE.md §6)."""
    assert can_transition(WorkerState.COMPLETED, WorkerState.READY)


def test_failure_can_only_reach_ready_through_recovering():
    assert can_transition(WorkerState.FAILED, WorkerState.RECOVERING)
    assert can_transition(WorkerState.RECOVERING, WorkerState.READY)
    assert not can_transition(WorkerState.FAILED, WorkerState.READY)
    assert not can_transition(WorkerState.FAILED, WorkerState.RUNNING)


def test_waiting_can_resume_or_fail():
    assert can_transition(WorkerState.WAITING, WorkerState.RUNNING)
    assert can_transition(WorkerState.WAITING, WorkerState.FAILED)


def test_stopped_is_terminal():
    assert allowed_transitions(WorkerState.STOPPED) == set()


def test_illegal_transition_raises_rather_than_being_silently_accepted():
    with pytest.raises(IllegalWorkerTransition):
        assert_transition(WorkerState.CREATED, WorkerState.RUNNING)


def test_cannot_skip_initialization():
    assert not can_transition(WorkerState.CREATED, WorkerState.READY)


def test_every_state_has_an_entry_in_the_transition_table():
    """A state with no table entry would raise KeyError at runtime instead
    of refusing cleanly -- guard against adding a state and forgetting."""
    for state in WorkerState:
        allowed_transitions(state)  # must not raise
