"""Mission Brief 037 — the founder objective, end to end.

```
objective -> Planner -> MissionPlan -> Mission Control -> Runtime
          -> Verifier -> Evidence -> Memory
```

Everything here drives the real components: real `MissionControl`, real
Dispatcher, real `RuntimeEngine`, real `TextVerifier` through the
Runtime's own gateway call, real `MemoryService`. The only invented thing
is the provider that returns the plan, which is the same line MB033 and
MB036 drew.
"""
from __future__ import annotations

from typing import Any

import pytest

from master_agent.missions.history import COMPLETED, FAILED, RUNNING
from master_agent.missions.service import ACCEPTED, REFUSED, REJECTED
from tests.missions_test_support import (
    capability_registry,
    pipeline,
    plan_text,
    step,
)
from tests.planner_test_support import CREATE, WRITE, refused, success

TWO_STEPS = plan_text(
    step("make_folder", CREATE.name, {"name": "demo"}),
    step(
        "write_readme",
        WRITE.name,
        {"path": "demo/README.md"},
        depends_on=["make_folder"],
        success_doc=success("the file is written", must_contain=["README"]),
    ),
)


# =========================================================================
# The path
# =========================================================================


def test_a_founder_objective_becomes_a_submitted_mission(tmp_path):
    """The Definition of Done, as far as this layer is responsible for it:
    one sentence in, one dependency-ordered Objective sitting in Mission
    Control, and nothing bypassed on the way."""
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)

    outcome = system.start("Set up a demo project")

    assert outcome.status == ACCEPTED
    assert outcome.steps == 2
    objective = system.objective(outcome.objective_id)
    assert objective.description == "Set up a demo project"
    assert [task.task_id for task in objective.tasks] == ["make_folder", "write_readme"]


def test_every_submitted_task_carries_its_expected_outcome(tmp_path):
    """The whole reason the Runtime can verify at all: MB023 gave `Task`
    the field, MB036 gave the Planner the ability to fill it, and this is
    the arrow between them."""
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)

    outcome = system.start()

    for task in system.objective(outcome.objective_id).tasks:
        assert task.expected_outcome is not None, task.task_id
        assert task.expected_outcome.checks


def test_the_planner_is_given_mission_controls_own_capability_registry(tmp_path):
    """No hardcoded capability names anywhere: the Planner can only name
    something that is really registered, because the catalogue *is* the
    registry."""
    registry = capability_registry("Desktop.ScanMachine")
    system = pipeline(
        plan_text(step("scan", "Desktop.ScanMachine", {})),
        tmp_path=tmp_path,
        registry=registry,
    )

    outcome = system.start("Look at this machine")

    assert outcome.accepted
    assert "Desktop.ScanMachine" in system.runner.prompt
    assert CREATE.name not in system.runner.prompt


def test_a_capability_that_is_deregistered_can_no_longer_be_planned(tmp_path):
    registry = capability_registry()
    system = pipeline(TWO_STEPS, tmp_path=tmp_path, registry=registry)
    registry.remove_executive("filesystem")

    outcome = system.start()

    assert outcome.status == REFUSED
    assert "nothing is registered" in outcome.reason


def test_the_objective_reaches_mission_control_only_once(tmp_path):
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)

    system.start()

    assert len(system.mission_control.dispatcher.objectives()) == 1


# =========================================================================
# Dependency order is Mission Control's, and it is respected
# =========================================================================


def test_a_dependent_task_is_not_dispatched_until_its_dependency_completes(tmp_path):
    """Mission Control owns execution order. This asserts the Planner's
    `depends_on` actually reaches the Dispatcher and is honoured."""
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)
    outcome = system.start()

    ready = system.mission_control.ready_tasks(outcome.objective_id)

    assert [task.task_id for task in ready] == ["make_folder"]


def test_the_second_task_unlocks_only_after_the_first_is_completed(tmp_path):
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)
    outcome = system.start()
    mc = system.mission_control

    mc.dispatch_ready(outcome.objective_id)
    mc.task_started("make_folder", objective_id=outcome.objective_id)
    assert mc.ready_tasks(outcome.objective_id) == []

    mc.task_completed("make_folder", objective_id=outcome.objective_id)

    assert [t.task_id for t in mc.ready_tasks(outcome.objective_id)] == ["write_readme"]


def test_a_failed_task_never_unlocks_what_depended_on_it(tmp_path):
    """"Never unlock a dependent step before verification" -- and the
    Runtime only calls `task_completed` after a matched verdict, so a
    verification failure lands here as a failed task."""
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)
    outcome = system.start()
    mc = system.mission_control

    mc.dispatch_ready(outcome.objective_id)
    mc.task_started("make_folder", objective_id=outcome.objective_id)
    mc.task_failed("make_folder", "verification verdict was 'not_matched'",
                   objective_id=outcome.objective_id)

    assert mc.ready_tasks(outcome.objective_id) == []


def test_priority_never_changes_the_order_anything_runs_in(tmp_path):
    """Deliverable: the Planner produces a priority, and it is
    descriptive. A Planner that could reorder execution by labelling a
    step `critical` would own lifecycle, which belongs to Mission
    Control."""
    system = pipeline(
        plan_text(
            {**step("first", CREATE.name), "priority": "low"},
            {**step("second", WRITE.name, depends_on=["first"]), "priority": "critical"},
        ),
        tmp_path=tmp_path,
    )

    outcome = system.start()

    ready = system.mission_control.ready_tasks(outcome.objective_id)
    assert [task.task_id for task in ready] == ["first"], "priority reordered execution"


def test_priority_and_complexity_reach_the_record_but_not_the_task(tmp_path):
    """They describe the plan for a human. Mission Control's `Task` has no
    field for them, and inventing one would mean editing a frozen file to
    carry something the Dispatcher must ignore."""
    system = pipeline(
        plan_text({**step("one", CREATE.name), "priority": "high", "complexity": "large"}),
        tmp_path=tmp_path,
    )

    outcome = system.start()

    task = system.objective(outcome.objective_id).tasks[0]
    assert not hasattr(task, "priority")
    record_step = system.record(outcome.objective_id).steps[0]
    assert record_step.priority == "high"
    assert record_step.estimated_complexity == "large"


# =========================================================================
# Refusal and rejection — nothing is repaired
# =========================================================================


def test_a_broker_refusal_submits_nothing(tmp_path):
    system = pipeline(refused("no provider clears the floor"), tmp_path=tmp_path)

    outcome = system.start()

    assert outcome.status == REFUSED
    assert "no provider clears the floor" in outcome.reason
    assert system.mission_control.dispatcher.objectives() == []


def test_an_unplannable_objective_submits_nothing(tmp_path):
    system = pipeline('{"steps": []}', tmp_path=tmp_path)

    outcome = system.start("Build me a rocket")

    assert outcome.status == REFUSED
    assert system.mission_control.dispatcher.objectives() == []


def test_a_plan_missing_an_expected_outcome_is_rejected_not_submitted(tmp_path):
    """The Planner's own validator refuses this first, so it never reaches
    the translation gate -- but either way nothing is submitted, and that
    is the property that matters."""
    system = pipeline(plan_text(step("one", CREATE.name, success_doc=None)), tmp_path=tmp_path)

    outcome = system.start()

    assert outcome.status in (REFUSED, REJECTED)
    assert system.mission_control.dispatcher.objectives() == []


def test_nothing_is_ever_repaired_or_re_planned(tmp_path):
    """Deliverable 9: no automatic repair. One refusal means one call to
    the provider, not a retry with a nudged prompt."""
    system = pipeline("not a plan at all", tmp_path=tmp_path)

    system.start()

    assert len(system.runner.calls) == 1, "the Planner was asked twice"


def test_a_second_objective_is_a_second_call_not_a_re_plan(tmp_path):
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)

    system.start("first thing")
    system.start("second thing")

    assert len(system.runner.calls) == 2
    assert len(system.mission_control.dispatcher.objectives()) == 2


# =========================================================================
# Memory — the lesson nobody else can record
# =========================================================================


def test_a_refused_plan_is_remembered_because_no_event_will_be_published(tmp_path):
    """A plan that never became an objective publishes nothing on the bus,
    so MB034's subscriptions cannot learn about it. This is the one thing
    the pipeline writes to memory itself."""
    system = pipeline(refused("nothing is installed"), tmp_path=tmp_path)

    system.start("Set up a demo project")

    titles = [record.title for record in system.memory.all()]
    assert any("Could not plan: Set up a demo project" in title for title in titles)


def test_the_remembered_lesson_names_the_reason_and_the_code(tmp_path):
    system = pipeline(refused("nothing is installed"), tmp_path=tmp_path)

    system.start("Set up a demo project")

    lesson = next(r for r in system.memory.all() if "Could not plan" in r.title)
    assert "nothing is installed" in lesson.full_text
    assert "Refusal code: broker_refused" in lesson.full_text
    assert lesson.category == "Failure Library"


def test_a_successful_plan_writes_no_planning_lesson(tmp_path):
    """Memory records outcomes, not intentions. MB034 made that call for
    missions and it holds here: a plan that was made is not a lesson."""
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)

    system.start()

    assert not any("Could not plan" in r.title for r in system.memory.all())


def test_a_memory_that_fails_does_not_stop_the_founder(tmp_path):
    """MB034's posture: memory is a record of the work, never a
    precondition for it."""

    class BrokenMemory:
        def write(self, **_kwargs: Any) -> None:
            raise RuntimeError("disk is gone")

    system = pipeline(refused(), tmp_path=tmp_path)
    system.missions.memory = BrokenMemory()

    outcome = system.start()

    assert outcome.status == REFUSED, "a broken memory changed the answer"


def test_the_pipeline_works_with_no_memory_at_all(tmp_path):
    system = pipeline(TWO_STEPS, tmp_path=tmp_path, with_memory=False)

    assert system.start().accepted


def test_the_pipeline_works_with_no_history_at_all(tmp_path):
    system = pipeline(TWO_STEPS, tmp_path=tmp_path, with_history=False)

    outcome = system.start()

    assert outcome.accepted
    assert outcome.record is None


# =========================================================================
# What the pipeline does not do
# =========================================================================


def test_the_pipeline_executes_nothing_itself(tmp_path):
    """It submits. The Runtime pulls.

    `READY` is expected on the dependency-free task: that is the
    Dispatcher's own bookkeeping at submission, and it is exactly the
    boundary being asserted -- Mission Control has decided what *could*
    run, and nothing has run.
    """
    from master_agent.mission_control.tasks import TaskState

    system = pipeline(TWO_STEPS, tmp_path=tmp_path)

    outcome = system.start()

    tasks = system.objective(outcome.objective_id).tasks
    assert {task.state for task in tasks} == {TaskState.READY, TaskState.CREATED}
    assert all(task.started_at is None for task in tasks), "something ran"
    assert all(task.result is None for task in tasks)
    assert all(task.evidence_id is None for task in tasks)


def test_the_pipeline_names_no_provider(tmp_path):
    """The Planner asks the Broker for `reasoning`; the Broker answers.
    This layer never learns who was chosen except to record it."""
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)

    system.start()

    request = system.runner.calls[0]["request"]
    assert request.capability == "reasoning"
    assert request.preferred_provider is None


def test_each_objective_gets_its_own_planning_task_id(tmp_path):
    """So a Broker decision can be traced back to the objective that
    caused it, rather than every plan sharing one id."""
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)

    system.start("first")
    system.start("second")

    ids = [call["request"].task_id for call in system.runner.calls]
    assert ids == ["plan-1", "plan-2"]
    assert len(set(ids)) == 2


def test_an_outcome_reports_itself_without_anybody_parsing_a_sentence(tmp_path):
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)

    reported = system.start("Set up a demo project").as_dict()

    assert reported["status"] == ACCEPTED
    assert reported["steps"] == 2
    assert reported["reason"] == ""


def test_a_refusal_reports_itself_the_same_way(tmp_path):
    system = pipeline(refused("nothing available"), tmp_path=tmp_path)

    reported = system.start().as_dict()

    assert reported["status"] == REFUSED
    assert reported["steps"] == 0
    assert "nothing available" in reported["reason"]


@pytest.mark.parametrize("blank", ["", "   ", "\n"])
def test_a_blank_objective_still_goes_through_the_one_path(tmp_path, blank):
    """No special case. An empty objective is a bad objective, and the
    Planner is what says so -- adding a guard here would be a second place
    that decides what is plannable."""
    system = pipeline('{"steps": []}', tmp_path=tmp_path)

    outcome = system.start(blank)

    assert outcome.status == REFUSED
    assert len(system.runner.calls) == 1


# =========================================================================
# The history record
# =========================================================================


def test_the_plan_is_recorded_before_anything_runs(tmp_path):
    """A mission that dies halfway must still be answerable for what it
    intended. A history that only records successes is a marketing
    document."""
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)

    outcome = system.start("Set up a demo project")

    record = system.record(outcome.objective_id)
    assert record.objective == "Set up a demo project"
    assert record.state == "planned"
    assert [s.step_id for s in record.steps] == ["make_folder", "write_readme"]
    assert all(s.state == "pending" for s in record.steps)


def test_the_record_keeps_the_expectation_as_text_not_as_a_live_object(tmp_path):
    """A record has to survive being written to disk and read by a process
    that does not import `verification/`."""
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)

    outcome = system.start()

    written = system.record(outcome.objective_id).steps[1]
    assert written.expectation == "the file is written"
    assert "mentions 'README'" in " ".join(written.checks)
    assert all(isinstance(check, str) for check in written.checks)


def test_the_record_names_who_planned_it(tmp_path):
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)

    outcome = system.start()

    assert system.record(outcome.objective_id).planned_by == "alpha-local"


def test_the_history_follows_the_mission_as_events_arrive(tmp_path):
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)
    outcome = system.start()
    mc = system.mission_control

    mc.dispatch_ready(outcome.objective_id)
    mc.task_started("make_folder", objective_id=outcome.objective_id)
    assert system.record(outcome.objective_id).step("make_folder").state == RUNNING
    assert system.record(outcome.objective_id).state == RUNNING

    mc.verification_completed(
        "make_folder", verdict="matched", evidence_id="ev-1",
        objective_id=outcome.objective_id,
    )
    mc.task_completed("make_folder", objective_id=outcome.objective_id)

    written = system.record(outcome.objective_id).step("make_folder")
    assert written.state == COMPLETED
    assert written.verdict == "matched"
    assert written.evidence_id == "ev-1"
    assert written.verified


def test_a_failed_step_records_its_error(tmp_path):
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)
    outcome = system.start()

    system.mission_control.task_failed(
        "make_folder", "missing required parameter: name",
        objective_id=outcome.objective_id,
    )

    written = system.record(outcome.objective_id).step("make_folder")
    assert written.state == FAILED
    assert "missing required parameter: name" in written.errors


def test_history_ignores_work_it_never_planned(tmp_path):
    """The launcher submits a machine-scan objective at every boot and it
    did not come from the Planner. Ignoring it is the common case, not an
    anomaly."""
    from master_agent.mission_control.tasks import Objective, Task

    system = pipeline(TWO_STEPS, tmp_path=tmp_path)
    system.start()
    other = system.mission_control.submit_objective(
        Objective(description="scan", tasks=[Task(capability="Desktop.ScanMachine",
                                                  task_id="scan-1")])
    )

    system.mission_control.task_started("scan-1", objective_id=other.objective_id)

    assert system.history.get(other.objective_id) is None
    assert len(system.history.all()) == 1
