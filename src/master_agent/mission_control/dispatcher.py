"""The Task Dispatcher (Mission Brief 023 deliverable #5).

Receives objectives, tracks dependencies, decides what is ready to run
next, and assigns each ready task to a registered Executive that provides
its capability.

It never invokes anything. `dispatch_ready()` returns tasks marked
DISPATCHED and assigned; an outside caller (today a test or demo,
eventually the Operator) performs the work through the Worker machinery
Mission Brief 022 already built and reports back via task_started /
task_completed / task_failed. Mission Control is the switchboard, never
the hands — MISSION_CONTROL_ARCHITECTURE.md §1, §7.
"""
from __future__ import annotations

from datetime import UTC, datetime

from master_agent.mission_control.capabilities import CapabilityRegistry
from master_agent.mission_control.events import MISSION_CONTROL_SOURCE, Event, EventBus, EventType
from master_agent.mission_control.executives import ExecutiveRegistry
from master_agent.mission_control.tasks import Objective, Task, TaskState


class UnknownObjective(Exception):
    pass


class TaskDispatcher:
    def __init__(
        self,
        capabilities: CapabilityRegistry,
        executives: ExecutiveRegistry,
        bus: EventBus,
    ) -> None:
        self._capabilities = capabilities
        self._executives = executives
        self._bus = bus
        self._objectives: dict[str, Objective] = {}

    # ---- submission -------------------------------------------------

    def submit(self, objective: Objective) -> Objective:
        """Validates structure up front (unknown dependencies, cycles,
        duplicate ids) so an impossible objective is refused when written,
        not discovered as a hang later."""
        objective.validate()
        self._objectives[objective.objective_id] = objective

        self._publish(EventType.OBJECTIVE_SUBMITTED, objective_id=objective.objective_id,
                      payload={"description": objective.description,
                               "task_count": len(objective.tasks)})
        for task in objective.tasks:
            self._publish(
                EventType.TASK_CREATED,
                objective_id=objective.objective_id,
                task_id=task.task_id,
                capability=task.capability,
                # `depends_on` is carried so a system rebuilt by event
                # replay (MB025 deliverable #9) reconstructs the dependency
                # graph, not just the task list. Without it a replay-
                # recovered system could dispatch a task before its
                # prerequisite -- found by MB025's replay tests. Additive
                # data inside an existing payload; the Event schema is
                # unchanged and no consumer is affected.
                payload={"depends_on": list(task.depends_on)},
            )
        self._recompute_readiness(objective)
        return objective

    def restore_objective(self, objective: Objective) -> Objective:
        """Re-admit an objective that was persisted in an earlier process,
        **without publishing creation events**.

        Added by Mission Brief 025 as the single additive contract that
        Mission Brief's Rule 4 ("no component reaches into another
        component's private state") makes necessary: `submit()` is
        otherwise the only way in, and it would republish
        OBJECTIVE_SUBMITTED/TASK_CREATED for work submitted hours ago,
        making a restored audit claim every objective was submitted twice.

        This is an extension, not a redesign. Validation and readiness
        recomputation are identical to `submit()`; the only difference is
        silence, because the events this would announce already happened
        and are already in the persisted log. See
        docs/adr/0015-persistence-strategy.md (Decision 3) -- that ADR is
        *Proposed*, and this method is what it proposes.
        """
        objective.validate()
        self._objectives[objective.objective_id] = objective
        self._recompute_readiness(objective)
        return objective

    def objective(self, objective_id: str) -> Objective:
        objective = self._objectives.get(objective_id)
        if objective is None:
            raise UnknownObjective(f"unknown objective: {objective_id}")
        return objective

    def objectives(self) -> list[Objective]:
        return list(self._objectives.values())

    # ---- readiness and dispatch -------------------------------------

    def _recompute_readiness(self, objective: Objective) -> None:
        """A task becomes READY when every dependency has COMPLETED, and
        BLOCKED when any dependency FAILED. A blocked task is never
        silently skipped and never auto-retried — auto-retry would be a
        strategic recovery decision, which belongs to the Brain
        (Constitution §11), not here."""
        by_id = {task.task_id: task for task in objective.tasks}

        for task in objective.tasks:
            if task.state in {TaskState.RUNNING, TaskState.DISPATCHED, TaskState.COMPLETED,
                              TaskState.FAILED}:
                continue

            dependencies = [by_id[dep] for dep in task.depends_on]
            if any(dep.state is TaskState.FAILED or dep.state is TaskState.BLOCKED
                   for dep in dependencies):
                if task.state is not TaskState.BLOCKED:
                    task.state = TaskState.BLOCKED
                    self._publish(
                        EventType.TASK_BLOCKED,
                        objective_id=objective.objective_id,
                        task_id=task.task_id,
                        capability=task.capability,
                        error="a dependency failed or is blocked",
                    )
                continue

            if all(dep.state is TaskState.COMPLETED for dep in dependencies):
                task.state = TaskState.READY

    def ready_tasks(self, objective_id: str) -> list[Task]:
        objective = self.objective(objective_id)
        self._recompute_readiness(objective)
        return [task for task in objective.tasks if task.state is TaskState.READY]

    def dispatch_ready(self, objective_id: str) -> list[Task]:
        """Assigns every currently-ready task to an available Executive
        providing its capability. A ready task with no available provider
        stays READY (not failed) — the system simply cannot run it yet,
        which is a scheduling fact, not an error."""
        objective = self.objective(objective_id)
        dispatched: list[Task] = []

        for task in self.ready_tasks(objective_id):
            if not self._capabilities.has(task.capability):
                self._fail_task(
                    objective,
                    task,
                    f"no registered capability named '{task.capability}'",
                )
                continue

            provider = self._executives.available_provider_of(task.capability)
            if provider is None:
                continue

            task.state = TaskState.DISPATCHED
            task.assigned_executive = provider.executive_id
            self._executives.set_current_task(provider.executive_id, task.task_id)
            dispatched.append(task)
            self._publish(
                EventType.TASK_ASSIGNED,
                objective_id=objective.objective_id,
                task_id=task.task_id,
                capability=task.capability,
                payload={"executive_id": provider.executive_id},
            )

        return dispatched

    # ---- reports back from whoever actually executed -----------------

    def task_started(self, objective_id: str, task_id: str) -> Task:
        objective = self.objective(objective_id)
        task = objective.task(task_id)
        task.state = TaskState.RUNNING
        task.started_at = datetime.now(UTC)
        self._publish(
            EventType.TASK_STARTED,
            objective_id=objective_id,
            task_id=task_id,
            capability=task.capability,
            payload={"executive_id": task.assigned_executive},
        )
        return task

    def task_completed(
        self, objective_id: str, task_id: str, result: object = None,
        evidence_id: str | None = None,
    ) -> Task:
        objective = self.objective(objective_id)
        task = objective.task(task_id)
        task.state = TaskState.COMPLETED
        task.result = result
        task.evidence_id = evidence_id
        task.ended_at = datetime.now(UTC)
        self._release_executive(task)

        self._publish(
            EventType.TASK_COMPLETED,
            objective_id=objective_id,
            task_id=task_id,
            capability=task.capability,
            payload={"executive_id": task.assigned_executive, "evidence_id": evidence_id},
        )
        self._recompute_readiness(objective)
        self._publish_objective_terminal_state(objective)
        return task

    def task_failed(self, objective_id: str, task_id: str, error: str) -> Task:
        objective = self.objective(objective_id)
        task = objective.task(task_id)
        self._fail_task(objective, task, error)
        return task

    def _fail_task(self, objective: Objective, task: Task, error: str) -> None:
        task.state = TaskState.FAILED
        task.errors.append(error)
        task.ended_at = datetime.now(UTC)
        self._release_executive(task)

        self._publish(
            EventType.TASK_FAILED,
            objective_id=objective.objective_id,
            task_id=task.task_id,
            capability=task.capability,
            error=error,
            payload={"executive_id": task.assigned_executive},
        )
        self._recompute_readiness(objective)
        self._publish_objective_terminal_state(objective)

    def _release_executive(self, task: Task) -> None:
        if task.assigned_executive and self._executives.has(task.assigned_executive):
            self._executives.set_current_task(task.assigned_executive, None)

    def _publish_objective_terminal_state(self, objective: Objective) -> None:
        if objective.is_complete:
            self._publish(
                EventType.OBJECTIVE_COMPLETED,
                objective_id=objective.objective_id,
                payload={"task_count": len(objective.tasks)},
            )
            return

        # An objective is only *failed* once nothing further can run --
        # a single failed task alongside still-runnable work is not yet a
        # failed objective.
        runnable = [
            task for task in objective.tasks
            if task.state not in {TaskState.COMPLETED, TaskState.FAILED, TaskState.BLOCKED}
        ]
        if objective.has_failure and not runnable:
            self._publish(
                EventType.OBJECTIVE_FAILED,
                objective_id=objective.objective_id,
                error="objective has failed tasks and no remaining runnable work",
            )

    # ---- internals ---------------------------------------------------

    def _publish(self, event_type: EventType, **kwargs: object) -> None:
        self._bus.publish(Event(event_type=event_type, source=MISSION_CONTROL_SOURCE, **kwargs))
