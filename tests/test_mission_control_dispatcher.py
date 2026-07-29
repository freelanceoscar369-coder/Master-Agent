"""Task Dispatcher tests (Mission Brief 023 deliverable #5).
See MISSION_CONTROL_ARCHITECTURE.md §7.
"""
from __future__ import annotations

import pytest

from master_agent.mission_control.capabilities import CapabilityDescriptor, qualified_name
from master_agent.mission_control.events import EventType
from master_agent.mission_control.executives import ExecutiveHealth
from master_agent.mission_control.mission_control import MissionControl
from master_agent.mission_control.tasks import InvalidObjective, Objective, Task, TaskState


def descriptor(executive: str, capability: str) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        qualified_name=qualified_name(executive, capability),
        executive_id=executive,
        capability=capability,
    )


def control_with_executive(capabilities: list[str] | None = None) -> MissionControl:
    mc = MissionControl()
    caps = capabilities or ["navigate", "click"]
    mc.register_executive(
        executive_id="browser",
        version="0.1.0",
        capabilities=[descriptor("browser", cap) for cap in caps],
        health=ExecutiveHealth.HEALTHY,
    )
    mc.mark_executive_ready("browser")
    return mc


# ---- objective validation ----------------------------------------------


def test_objective_with_unknown_dependency_is_refused_at_submission():
    mc = control_with_executive()
    objective = Objective(
        description="bad",
        tasks=[Task(capability="Browser.Navigate", task_id="t1", depends_on=["ghost"])],
    )
    with pytest.raises(InvalidObjective):
        mc.submit_objective(objective)


def test_objective_with_a_dependency_cycle_is_refused_not_deadlocked():
    mc = control_with_executive()
    objective = Objective(
        description="cycle",
        tasks=[
            Task(capability="Browser.Navigate", task_id="t1", depends_on=["t2"]),
            Task(capability="Browser.Click", task_id="t2", depends_on=["t1"]),
        ],
    )
    with pytest.raises(InvalidObjective):
        mc.submit_objective(objective)


def test_objective_with_duplicate_task_ids_is_refused():
    mc = control_with_executive()
    objective = Objective(
        description="dupes",
        tasks=[
            Task(capability="Browser.Navigate", task_id="t1"),
            Task(capability="Browser.Click", task_id="t1"),
        ],
    )
    with pytest.raises(InvalidObjective):
        mc.submit_objective(objective)


def test_self_dependency_is_refused():
    mc = control_with_executive()
    objective = Objective(
        description="self",
        tasks=[Task(capability="Browser.Navigate", task_id="t1", depends_on=["t1"])],
    )
    with pytest.raises(InvalidObjective):
        mc.submit_objective(objective)


# ---- readiness and dependency order ------------------------------------


def test_only_dependency_free_tasks_are_ready_initially():
    mc = control_with_executive()
    mc.submit_objective(
        Objective(
            description="chain",
            tasks=[
                Task(capability="Browser.Navigate", task_id="t1"),
                Task(capability="Browser.Click", task_id="t2", depends_on=["t1"]),
            ],
        )
    )
    assert [task.task_id for task in mc.ready_tasks()] == ["t1"]


def test_a_dependent_task_becomes_ready_only_after_its_dependency_completes():
    mc = control_with_executive()
    mc.submit_objective(
        Objective(
            description="chain",
            tasks=[
                Task(capability="Browser.Navigate", task_id="t1"),
                Task(capability="Browser.Click", task_id="t2", depends_on=["t1"]),
            ],
        )
    )
    mc.dispatch_ready()
    mc.task_started("t1")
    assert [t.task_id for t in mc.ready_tasks()] == []
    mc.task_completed("t1")
    assert [t.task_id for t in mc.ready_tasks()] == ["t2"]


def test_a_task_whose_dependency_failed_becomes_blocked_never_silently_skipped():
    mc = control_with_executive()
    mc.submit_objective(
        Objective(
            description="chain",
            tasks=[
                Task(capability="Browser.Navigate", task_id="t1"),
                Task(capability="Browser.Click", task_id="t2", depends_on=["t1"]),
            ],
        )
    )
    mc.dispatch_ready()
    mc.task_started("t1")
    mc.task_failed("t1", "navigation timed out")

    objective = mc.dispatcher.objectives()[0]
    assert objective.task("t2").state is TaskState.BLOCKED
    assert mc.ready_tasks() == []


def test_a_blocked_task_is_never_auto_retried():
    """Auto-retry would be a strategic recovery decision, which belongs to
    the Brain (Constitution §11), not Mission Control."""
    mc = control_with_executive()
    mc.submit_objective(
        Objective(
            description="chain",
            tasks=[
                Task(capability="Browser.Navigate", task_id="t1"),
                Task(capability="Browser.Click", task_id="t2", depends_on=["t1"]),
            ],
        )
    )
    mc.dispatch_ready()
    mc.task_started("t1")
    mc.task_failed("t1", "boom")

    for _ in range(3):
        assert mc.dispatch_ready() == []


# ---- dispatch ----------------------------------------------------------


def test_dispatch_assigns_a_provider_and_marks_the_executive_busy():
    mc = control_with_executive()
    mc.submit_objective(
        Objective(description="one", tasks=[Task(capability="Browser.Navigate", task_id="t1")])
    )
    dispatched = mc.dispatch_ready()
    assert [t.task_id for t in dispatched] == ["t1"]
    assert dispatched[0].assigned_executive == "browser"
    assert mc.executives.get("browser").current_task_id == "t1"


def test_completing_a_task_frees_its_executive():
    mc = control_with_executive()
    mc.submit_objective(
        Objective(description="one", tasks=[Task(capability="Browser.Navigate", task_id="t1")])
    )
    mc.dispatch_ready()
    mc.task_started("t1")
    mc.task_completed("t1")
    assert mc.executives.get("browser").current_task_id is None


def test_a_task_naming_an_unregistered_capability_fails_with_a_clear_reason():
    mc = control_with_executive(capabilities=["navigate"])
    mc.submit_objective(
        Objective(description="x", tasks=[Task(capability="Desktop.WindowDetect", task_id="t1")])
    )
    mc.dispatch_ready()
    objective = mc.dispatcher.objectives()[0]
    assert objective.task("t1").state is TaskState.FAILED
    assert "no registered capability" in objective.task("t1").errors[0]


def test_a_ready_task_with_no_available_provider_stays_ready_not_failed():
    """Not having a free Worker right now is a scheduling fact, not an
    error -- the task must remain runnable later."""
    mc = control_with_executive()
    mc.submit_objective(
        Objective(
            description="two",
            tasks=[
                Task(capability="Browser.Navigate", task_id="t1"),
                Task(capability="Browser.Click", task_id="t2"),
            ],
        )
    )
    dispatched = mc.dispatch_ready()
    assert len(dispatched) == 1  # only one executive, so only one task goes out

    objective = mc.dispatcher.objectives()[0]
    remaining = next(t for t in objective.tasks if t.task_id != dispatched[0].task_id)
    assert remaining.state is TaskState.READY


# ---- events ------------------------------------------------------------


def test_the_full_task_event_sequence_is_emitted():
    mc = control_with_executive()
    mc.submit_objective(
        Objective(description="one", tasks=[Task(capability="Browser.Navigate", task_id="t1")])
    )
    mc.dispatch_ready()
    mc.task_started("t1")
    mc.task_completed("t1")

    emitted = [entry.event_type for entry in mc.audit.entries]
    for expected in (
        EventType.OBJECTIVE_SUBMITTED,
        EventType.TASK_CREATED,
        EventType.TASK_DISPATCHED,
        EventType.TASK_STARTED,
        EventType.TASK_COMPLETED,
        EventType.OBJECTIVE_COMPLETED,
    ):
        assert expected in emitted, f"missing event: {expected}"


def test_objective_is_not_marked_failed_while_runnable_work_remains():
    mc = control_with_executive()
    mc.submit_objective(
        Objective(
            description="two independent",
            tasks=[
                Task(capability="Browser.Navigate", task_id="t1"),
                Task(capability="Browser.Click", task_id="t2"),
            ],
        )
    )
    mc.dispatch_ready()
    mc.task_started("t1")
    mc.task_failed("t1", "boom")

    emitted = [entry.event_type for entry in mc.audit.entries]
    assert EventType.OBJECTIVE_FAILED not in emitted, (
        "t2 is still runnable, so the objective has not failed yet"
    )
