"""Mission Brief 037 — mission lifecycle, checkpoint and recovery.

The brief lists these as Mission Control's, and they are: this file
asserts that MB037 composed onto the lifecycle that already existed
rather than growing a second one, and that a plan survives a restart.

It also records, in a test rather than only in prose, the one thing MB037
did **not** build: pause, resume and cancel do not exist, on any layer.
"""
from __future__ import annotations

from typing import Any

import pytest

from master_agent.missions.history import (
    COMPLETED,
    FAILED,
    HISTORY_FILENAME,
    PLANNED,
    RUNNING,
    JsonFilePlanStore,
    PlanHistory,
)
from master_agent.brain import IntentLayer
from master_agent.missions.service import MissionService
from tests.missions_test_support import pipeline, plan_text, step
from tests.planner_test_support import CREATE, WRITE, success

TWO_STEPS = plan_text(
    step("a", CREATE.name, {"name": "demo"}),
    step("b", WRITE.name, {"path": "demo/x"}, depends_on=["a"],
         success_doc=success("written")),
)


def finish(system, plan_id, step_id, verdict="matched"):
    mc = system.mission_control
    mc.task_started(step_id, objective_id=plan_id)
    mc.verification_completed(
        step_id, verdict=verdict, evidence_id=f"ev-{step_id}", objective_id=plan_id
    )
    mc.task_completed(step_id, objective_id=plan_id)


# =========================================================================
# The lifecycle is Mission Control's, and MB037 rides it
# =========================================================================


def test_a_mission_moves_planned_then_running_then_completed(tmp_path):
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)
    outcome = system.start()

    assert system.record(outcome.objective_id).state == PLANNED
    system.mission_control.task_started("a", objective_id=outcome.objective_id)
    assert system.record(outcome.objective_id).state == RUNNING

    finish(system, outcome.objective_id, "a")
    finish(system, outcome.objective_id, "b")

    assert system.record(outcome.objective_id).state == COMPLETED


def test_a_mission_that_fails_is_recorded_as_failed(tmp_path):
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)
    outcome = system.start()

    system.mission_control.task_failed("a", "no such folder", objective_id=outcome.objective_id)

    assert system.record(outcome.objective_id).state == FAILED
    assert system.record(outcome.objective_id).finished_at


def test_mission_control_still_reports_progress_for_a_planned_mission(tmp_path):
    """`founder_state()` is Mission Control's own read. MB037 did not
    replace it and must not have broken it."""
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)
    outcome = system.start("Set up a demo project")

    state = system.mission_control.founder_state(outcome.objective_id)

    assert state.progress == 0.0
    finish(system, outcome.objective_id, "a")
    assert system.mission_control.founder_state(outcome.objective_id).progress == 0.5


def test_two_missions_run_independently(tmp_path):
    system = pipeline(TWO_STEPS, TWO_STEPS, tmp_path=tmp_path)
    first = system.start("first")
    second = system.start("second")

    finish(system, first.objective_id, "a")

    assert system.record(first.objective_id).step("a").state == COMPLETED
    assert system.record(second.objective_id).step("a").state == "pending"


def test_a_mission_records_the_objective_it_was_asked_for_not_a_summary(tmp_path):
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)

    outcome = system.start("Create a Python project called Demo")

    assert system.record(outcome.objective_id).objective == (
        "Create a Python project called Demo"
    )
    assert system.objective(outcome.objective_id).description == (
        "Create a Python project called Demo"
    )


# =========================================================================
# Checkpoint and resume
# =========================================================================


def test_a_plan_survives_a_restart(tmp_path):
    """A new process, a new `PlanHistory`, the same file: the mission and
    every verdict it earned are still there."""
    path = tmp_path / HISTORY_FILENAME
    first = pipeline(TWO_STEPS, tmp_path=tmp_path)
    first.history = PlanHistory(store=JsonFilePlanStore(path))
    first.history.attach_to(first.mission_control)
    first.missions.history = first.history
    outcome = first.start("Set up a demo project")
    finish(first, outcome.objective_id, "a")

    reopened = PlanHistory(store=JsonFilePlanStore(path))

    record = reopened.get(outcome.objective_id)
    assert record.state == RUNNING
    assert record.step("a").verdict == "matched"
    assert [s.step_id for s in record.remaining] == ["b"]
    assert record.current.step_id == "b"


def test_a_restart_can_replay_what_the_previous_process_did(tmp_path):
    path = tmp_path / HISTORY_FILENAME
    first = pipeline(TWO_STEPS, tmp_path=tmp_path)
    first.history = PlanHistory(store=JsonFilePlanStore(path))
    first.history.attach_to(first.mission_control)
    first.missions.history = first.history
    outcome = first.start("Set up a demo project")
    finish(first, outcome.objective_id, "a")
    finish(first, outcome.objective_id, "b")

    replay = PlanHistory(store=JsonFilePlanStore(path)).replay(outcome.objective_id)

    assert replay.complete
    assert replay.evidence_ids == ("ev-a", "ev-b")
    assert all(step.verified for step in replay.steps)


def test_a_second_process_appends_rather_than_replacing(tmp_path):
    path = tmp_path / HISTORY_FILENAME
    first = pipeline(TWO_STEPS, tmp_path=tmp_path)
    first.history = PlanHistory(store=JsonFilePlanStore(path))
    first.history.attach_to(first.mission_control)
    first.missions.history = first.history
    first_id = first.start("first").objective_id

    second = pipeline(TWO_STEPS, tmp_path=tmp_path / "two")
    second.history = PlanHistory(store=JsonFilePlanStore(path))
    second.history.attach_to(second.mission_control)
    second.missions.history = second.history
    second_id = second.start("second").objective_id

    reopened = PlanHistory(store=JsonFilePlanStore(path))
    assert {r.plan_id for r in reopened.all()} == {first_id, second_id}


def test_the_history_is_written_as_each_event_arrives_not_at_the_end(tmp_path):
    """A process killed mid-mission must leave a readable record. Writing
    only on completion would lose exactly the missions worth studying."""
    path = tmp_path / HISTORY_FILENAME
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)
    system.history = PlanHistory(store=JsonFilePlanStore(path))
    system.history.attach_to(system.mission_control)
    system.missions.history = system.history
    outcome = system.start("Set up a demo project")

    system.mission_control.task_started("a", objective_id=outcome.objective_id)

    mid_flight = PlanHistory(store=JsonFilePlanStore(path)).get(outcome.objective_id)
    assert mid_flight.step("a").state == RUNNING
    assert mid_flight.step("a").started_at


# =========================================================================
# Failure propagation
# =========================================================================


def test_a_failure_stops_the_mission_rather_than_the_process(tmp_path):
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)
    outcome = system.start()

    system.mission_control.task_failed("a", "boom", objective_id=outcome.objective_id)

    assert system.objective(outcome.objective_id).has_failure
    assert system.record(outcome.objective_id).state == FAILED
    # And the pipeline is still usable.
    assert system.missions.start("something else") is not None


def test_a_failure_does_not_silently_complete_the_mission(tmp_path):
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)
    outcome = system.start()

    system.mission_control.task_failed("a", "boom", objective_id=outcome.objective_id)

    assert not system.objective(outcome.objective_id).is_complete
    assert system.record(outcome.objective_id).progress == 0.0


def test_the_planner_is_not_consulted_again_after_a_failure(tmp_path):
    """"Planner does not re-plan automatically." Adaptive planning is a
    later brief with its own safety argument."""
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)
    outcome = system.start()
    calls = len(system.runner.calls)

    system.mission_control.task_failed("a", "boom", objective_id=outcome.objective_id)

    assert len(system.runner.calls) == calls


# =========================================================================
# What MB037 did not build, recorded so it is not mistaken for working
# =========================================================================


@pytest.mark.parametrize("verb", ["pause", "resume", "cancel"])
def test_pause_resume_and_cancel_do_not_exist_anywhere(verb):
    """The brief asks Mission Control to own these. It publishes none of
    them, and MB037 could not add them: doing so means editing frozen
    `mission_control/` (the brief allows zero frozen files and no ADR),
    and building them outside would be a second orchestration authority
    (which the brief forbids outright).

    So they are absent, deliberately, and this test says so out loud
    rather than letting a founder discover it by typing `pause`. It fails
    the day somebody adds one, which is the point: that addition needs a
    ratified ADR, and this is where the conversation restarts.
    """
    from master_agent.mission_control.mission_control import MissionControl
    from master_agent.missions.service import MissionService as Service

    assert not hasattr(MissionControl, verb), f"MissionControl grew {verb}()"
    assert not hasattr(Service, verb), f"the pipeline grew its own {verb}()"


def test_the_console_offers_no_pause_verb(tmp_path):
    """Following from the above: a verb that cannot work must not be
    advertised."""
    from master_agent.launcher.console import HELP

    for verb in ("pause", "resume", "cancel"):
        assert verb not in HELP


# =========================================================================
# The service's own edges
# =========================================================================


def test_a_service_with_no_history_still_reports_an_accepted_mission(tmp_path):
    system = pipeline(TWO_STEPS, tmp_path=tmp_path, with_history=False)

    outcome = system.start()

    assert outcome.accepted
    assert outcome.objective_id


def test_a_service_with_no_memory_still_refuses_cleanly(tmp_path):
    from tests.planner_test_support import refused

    system = pipeline(refused("nothing"), tmp_path=tmp_path, with_memory=False)

    assert system.start().status == "refused"


def test_a_refusal_with_no_refusal_object_writes_no_memory(tmp_path):
    """Defensive: an outcome that is neither planned nor carrying a
    refusal should not produce a lesson titled after nothing."""

    class Blank:
        planned = False
        refusal = None
        provider_id = None
        entry_id = None

    class BlankPlanner:
        def plan(self, _intent: Any, **_kwargs: Any) -> Blank:
            return Blank()

    system = pipeline(TWO_STEPS, tmp_path=tmp_path)
    service = MissionService(
        planner=BlankPlanner(),
        mission_control=system.mission_control,
        intent_layer=IntentLayer(),
        history=system.history,
        memory=system.memory,
    )
    before = system.memory.summary().total

    outcome = service.start("something")

    assert not outcome.accepted
    assert system.memory.summary().total == before


def test_an_objective_id_can_be_supplied_for_tracing(tmp_path):
    """So a plan made for an existing objective can be tied to it on the
    Broker's ledger."""
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)

    system.missions.start("do it", objective_id="obj-42")

    assert system.runner.calls[0]["request"].objective_id == "obj-42"
