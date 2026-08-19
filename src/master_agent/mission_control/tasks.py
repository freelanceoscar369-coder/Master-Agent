"""Objectives and Tasks — what the Task Dispatcher schedules.

An Objective is what the founder wants. A Task is one executable
capability call within it. Tasks name a *qualified capability*
(`Browser.Navigate`), never an Executive — resolution to a provider
happens at dispatch time, exactly as the Constitution's plans stay
portable by naming capabilities rather than Workers (§3.2).

TaskState is deliberately its own small enum rather than a reuse of
WorkerState (lifecycle.py): those states describe a *Worker's* life
("Initialized", "Recovering"), which does not fit a unit of work. These
states map one-to-one onto the TASK_* events the brief names, plus the two
(BLOCKED, DISPATCHED) that dependency tracking genuinely requires.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class TaskState(str, Enum):
    CREATED = "created"
    BLOCKED = "blocked"
    READY = "ready"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


TERMINAL_TASK_STATES = frozenset({TaskState.COMPLETED, TaskState.FAILED})


@dataclass
class Task:
    capability: str  # qualified, e.g. "Browser.Navigate"
    payload: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    # What "done" looks like for this task, so Verification has something
    # concrete to compare a fresh Observation against (Constitution §3.2 --
    # every Step a Planner emits should name one). A real field rather
    # than an entry in `payload`: payload is forwarded to the Executive
    # and mirrored into audit records, which must stay JSON-plain, and an
    # ExpectedOutcome is neither the Executive's business nor JSON.
    # Typed loosely to keep mission_control free of a hard dependency on
    # the verification package.
    expected_outcome: Any = None
    task_id: str = field(default_factory=lambda: str(uuid4()))
    state: TaskState = TaskState.CREATED
    assigned_executive: str | None = None
    result: Any = None
    evidence_id: str | None = None
    #: Destination argument -> `Binding`. Declared by the Planner, resolved
    #: by the Runtime immediately before execution. Separate from `payload`
    #: on purpose: `payload` means "arguments for the capability", and
    #: putting `${step_3.url}` placeholders inside one would force every
    #: Action to understand references it has no business knowing about.
    input_bindings: dict[str, Any] = field(default_factory=dict)
    #: The canonical Evidence projection Verification produced for THIS
    #: task, stored by Mission Control when it transports the verification
    #: event.
    #:
    #: `evidence_id` alone was enough while nothing downstream needed the
    #: record. A dependent step binding to this task's output does: it must
    #: check that the reported value and the independently observed value
    #: agree, and an id cannot answer that. Mission State is Shared
    #: Infrastructure's own responsibility, so the Runtime reads it here
    #: rather than reaching into PlanHistory or the Reporter.
    evidence: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    ended_at: datetime | None = None

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at is None or self.ended_at is None:
            return None
        return (self.ended_at - self.started_at).total_seconds()

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "capability": self.capability,
            "state": self.state.value,
            "assigned_executive": self.assigned_executive,
            "depends_on": list(self.depends_on),
            "evidence_id": self.evidence_id,
            "input_bindings": dict(self.input_bindings),
            "evidence": self.evidence,
            "errors": list(self.errors),
            "duration_seconds": self.duration_seconds,
        }


class InvalidObjective(Exception):
    """Raised at submission time for a structurally impossible objective (an
    unknown dependency, a dependency cycle, a duplicate task id) — caught
    when the objective is written, never discovered as a hang at dispatch
    time."""


@dataclass
class Objective:
    """What the founder wants, decomposed into capability calls."""

    description: str
    tasks: list[Task] = field(default_factory=list)
    objective_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def validate(self) -> None:
        ids = [task.task_id for task in self.tasks]
        duplicates = {task_id for task_id in ids if ids.count(task_id) > 1}
        if duplicates:
            raise InvalidObjective(f"duplicate task ids: {sorted(duplicates)}")

        known = set(ids)
        for task in self.tasks:
            unknown = [dep for dep in task.depends_on if dep not in known]
            if unknown:
                raise InvalidObjective(
                    f"task {task.task_id} depends on unknown task(s): {sorted(unknown)}"
                )
            if task.task_id in task.depends_on:
                raise InvalidObjective(f"task {task.task_id} depends on itself")

        self._assert_acyclic()

    def _assert_acyclic(self) -> None:
        """Iterative depth-first cycle detection. A cycle is a design error
        in whoever built the objective, so it is refused loudly at
        submission rather than deadlocking the dispatcher later."""
        graph = {task.task_id: list(task.depends_on) for task in self.tasks}
        unvisited, visiting, done = 0, 1, 2
        marks: dict[str, int] = dict.fromkeys(graph, unvisited)

        for root in graph:
            if marks[root] != unvisited:
                continue
            stack: list[tuple[str, bool]] = [(root, False)]
            while stack:
                node, closing = stack.pop()
                if closing:
                    marks[node] = done
                    continue
                if marks[node] == visiting:
                    raise InvalidObjective(f"dependency cycle involving task {node}")
                if marks[node] == done:
                    continue
                marks[node] = visiting
                stack.append((node, True))
                for dependency in graph[node]:
                    if marks[dependency] != done:
                        stack.append((dependency, False))

    @property
    def is_complete(self) -> bool:
        return all(task.state is TaskState.COMPLETED for task in self.tasks)

    @property
    def has_failure(self) -> bool:
        return any(task.state is TaskState.FAILED for task in self.tasks)

    @property
    def progress(self) -> float:
        """Fraction of tasks in a terminal-success state, 0.0-1.0. An
        objective with no tasks is complete by definition, not divided by
        zero."""
        if not self.tasks:
            return 1.0
        completed = sum(1 for task in self.tasks if task.state is TaskState.COMPLETED)
        return completed / len(self.tasks)

    def task(self, task_id: str) -> Task:
        for task in self.tasks:
            if task.task_id == task_id:
                return task
        raise KeyError(f"unknown task: {task_id}")
