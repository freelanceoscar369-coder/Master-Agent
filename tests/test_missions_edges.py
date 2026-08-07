"""Mission Brief 037 — the edges.

Each of these is a branch the happy path never reaches, and every one of
them is a real situation: an event for a step that is not in the plan, a
mission with no steps, a memory that is not wired, a plan rejected by the
translation gate. Left untested they are the branches that fail first,
because they only run on the day something has already gone wrong.
"""
from __future__ import annotations

from typing import Any

import pytest

from master_agent.missions.history import (
    COMPLETED,
    PlanHistory,
    PlanRecord,
    Replay,
    ReplayStep,
    StepRecord,
)
from master_agent.brain import IntentLayer
from master_agent.missions.service import (
    ACCEPTED,
    REJECTED,
    MissionOutcome,
    MissionService,
)
from master_agent.planner.plan import MissionPlan, Step
from master_agent.verification.evidence import ExpectedOutcome, ObservationCheck
from tests.missions_test_support import pipeline, plan_text, step
from tests.planner_test_support import CREATE, WRITE, success

TWO_STEPS = plan_text(
    step("a", CREATE.name, {"name": "demo"}),
    step("b", WRITE.name, {"path": "demo/x"}, depends_on=["a"],
         success_doc=success("written")),
)


# =========================================================================
# Records with nothing in them
# =========================================================================


def test_a_record_with_no_steps_reports_zero_progress_rather_than_dividing_by_zero():
    assert PlanRecord(plan_id="p", objective="nothing").progress == 0.0


def test_a_record_with_no_steps_has_no_current_step():
    assert PlanRecord(plan_id="p", objective="nothing").current is None


def test_a_record_with_no_steps_has_empty_reads():
    record = PlanRecord(plan_id="p", objective="nothing")

    assert record.completed == []
    assert record.remaining == []
    assert record.blocked == []
    assert record.failed == []
    assert record.unverified == []


def test_a_step_depending_on_one_that_is_not_in_the_record_is_treated_as_blocked():
    """Defensive: `objective_from_plan` cannot produce this, but a
    hand-written or hand-edited history file can, and a missing
    dependency must read as "not ready" rather than crash."""
    record = PlanRecord(
        plan_id="p",
        objective="o",
        steps=[StepRecord(step_id="b", capability="X.Y", depends_on=["ghost"])],
    )

    assert record.is_ready(record.steps[0]) is False
    assert [s.step_id for s in record.blocked] == ["b"]


# =========================================================================
# Replay reads
# =========================================================================


def test_a_replay_can_report_only_the_steps_that_verified():
    replay = Replay(
        plan_id="p",
        objective="o",
        steps=(
            ReplayStep(1, "a", "X.Y", {}, "", COMPLETED, "matched", "ev-a"),
            ReplayStep(2, "b", "X.Z", {}, "", COMPLETED, "not_matched", "ev-b"),
        ),
    )

    assert [s.step_id for s in replay.verified_steps] == ["a"]
    assert replay.evidence_ids == ("ev-a", "ev-b")


def test_a_replay_with_no_evidence_reports_none():
    replay = Replay(
        plan_id="p",
        objective="o",
        steps=(ReplayStep(1, "a", "X.Y", {}, "", "pending", "", None),),
    )

    assert replay.evidence_ids == ()
    assert replay.verified_steps == ()


# =========================================================================
# Events for work the history does not know about
# =========================================================================


def test_an_event_for_an_unknown_step_of_a_known_plan_is_ignored(tmp_path):
    """The plan is ours; the task id is not. Ignoring it in silence is
    correct -- guessing which step was meant would corrupt the record."""
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)
    outcome = system.start()

    system.mission_control.bus.publish  # noqa: B018 - the bus is real below
    from master_agent.mission_control.events import Event, EventType

    system.mission_control.bus.publish(
        Event(
            event_type=EventType.TASK_STARTED,
            source="test",
            objective_id=outcome.objective_id,
            task_id="not-in-this-plan",
        )
    )

    record = system.record(outcome.objective_id)
    assert [s.state for s in record.steps] == ["pending", "pending"]


@pytest.mark.parametrize(
    "event_type",
    ["TASK_STARTED", "TASK_COMPLETED", "TASK_FAILED", "VERIFICATION_COMPLETED"],
)
def test_every_handler_ignores_an_event_for_an_unknown_step(tmp_path, event_type):
    from master_agent.mission_control.events import Event, EventType

    system = pipeline(TWO_STEPS, tmp_path=tmp_path)
    outcome = system.start()

    system.mission_control.bus.publish(
        Event(
            event_type=getattr(EventType, event_type),
            source="test",
            objective_id=outcome.objective_id,
            task_id="ghost",
            payload={"verdict": "matched", "evidence_id": "ev-x"},
        )
    )

    record = system.record(outcome.objective_id)
    assert record.step("ghost") is None
    assert [s.state for s in record.steps] == ["pending", "pending"]


def test_an_objective_finishing_that_was_never_planned_is_ignored(tmp_path):
    from master_agent.mission_control.events import Event, EventType

    system = pipeline(TWO_STEPS, tmp_path=tmp_path)
    system.start()

    system.mission_control.bus.publish(
        Event(event_type=EventType.OBJECTIVE_COMPLETED, source="test", objective_id="other")
    )

    assert len(system.history.all()) == 1


def test_a_failure_event_carrying_its_error_in_the_payload_is_still_recorded(tmp_path):
    """`Event.error` is the usual home, but the payload is where some
    publishers put it. Both are read, because a failure with no
    explanation is the least useful record there is."""
    from master_agent.mission_control.events import Event, EventType

    system = pipeline(TWO_STEPS, tmp_path=tmp_path)
    outcome = system.start()

    system.mission_control.bus.publish(
        Event(
            event_type=EventType.TASK_FAILED,
            source="test",
            objective_id=outcome.objective_id,
            task_id="a",
            payload={"error": "disk full"},
        )
    )

    assert system.record(outcome.objective_id).step("a").errors == ["disk full"]


def test_a_failure_with_no_error_at_all_records_no_empty_string(tmp_path):
    from master_agent.mission_control.events import Event, EventType

    system = pipeline(TWO_STEPS, tmp_path=tmp_path)
    outcome = system.start()

    system.mission_control.bus.publish(
        Event(
            event_type=EventType.TASK_FAILED,
            source="test",
            objective_id=outcome.objective_id,
            task_id="a",
        )
    )

    assert system.record(outcome.objective_id).step("a").errors == []


# =========================================================================
# MissionOutcome's own reads
# =========================================================================


def test_an_outcome_with_no_plan_counts_zero_steps():
    assert MissionOutcome().steps == 0


def test_a_rejected_outcome_explains_itself_from_its_reasons():
    outcome = MissionOutcome(status=REJECTED, reasons=("a: no capability", "b: no inputs"))

    assert "the plan was not executable" in outcome.reason
    assert "a: no capability" in outcome.reason
    assert "b: no inputs" in outcome.reason


def test_an_outcome_with_neither_a_refusal_nor_reasons_still_says_something():
    """Never an empty sentence: a founder reading a blank line learns
    nothing, and this branch only runs when something unexpected
    happened."""
    assert MissionOutcome().reason == "no plan"


def test_an_accepted_outcome_has_no_reason():
    assert MissionOutcome(status=ACCEPTED).reason == ""


# =========================================================================
# The translation gate, reached through the service
# =========================================================================


class IncompletePlanner:
    """A Planner that reports success while returning an unusable plan.

    MB036's own validator makes this impossible, which is exactly why the
    gate has to be tested with something else: the guarantee belongs to
    the pipeline, not to one producer's good behaviour.
    """

    planned = True
    refusal = None
    provider_id = "somewhere"
    entry_id = 11

    def __init__(self, produced: Any) -> None:
        # Named `produced`, not `plan`: an attribute called `plan` would
        # shadow the `plan()` method this class exists to provide.
        self.produced = produced

    def plan(self, _intent: Any, **_kwargs: Any) -> Any:
        return _Produced(self.produced)


class _Produced:
    """A `PlanOutcome`-shaped result carrying a hand-built plan."""

    planned = True
    refusal = None
    provider_id = "somewhere"
    entry_id = 11

    def __init__(self, plan: Any) -> None:
        self.plan = plan


def test_a_plan_that_slips_past_its_producer_is_rejected_by_the_gate(tmp_path):
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)
    unusable = MissionPlan(
        steps=[Step(step_id="x", capability="Filesystem.CreateFolder", payload={})],
        objective="o",
    )
    service = MissionService(
        planner=IncompletePlanner(unusable),
        mission_control=system.mission_control,
        intent_layer=IntentLayer(),
        history=system.history,
        memory=system.memory,
    )

    outcome = service.start("do it")

    assert outcome.status == REJECTED
    assert outcome.reasons == ("x: no expected outcome",)
    assert system.mission_control.dispatcher.objectives() == []


def test_a_rejected_plan_is_remembered_as_a_lesson(tmp_path):
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)
    unusable = MissionPlan(
        steps=[Step(step_id="x", capability="Filesystem.CreateFolder", payload={})],
        objective="o",
    )
    service = MissionService(
        planner=IncompletePlanner(unusable),
        mission_control=system.mission_control,
        intent_layer=IntentLayer(),
        history=system.history,
        memory=system.memory,
    )

    service.start("Set up a demo project")

    lesson = next(r for r in system.memory.all() if "Rejected an unusable plan" in r.title)
    assert "no expected outcome" in lesson.full_text
    assert "nothing was repaired" in lesson.full_text.lower()


def test_a_rejected_plan_with_no_memory_wired_still_rejects_cleanly(tmp_path):
    system = pipeline(TWO_STEPS, tmp_path=tmp_path, with_memory=False)
    unusable = MissionPlan(
        steps=[Step(step_id="x", capability="Filesystem.CreateFolder", payload={})],
        objective="o",
    )
    service = MissionService(
        planner=IncompletePlanner(unusable),
        mission_control=system.mission_control,
        intent_layer=IntentLayer(),
        history=None,
        memory=None,
    )

    assert service.start("do it").status == REJECTED


def test_a_plan_whose_expectation_has_no_checks_is_rejected_too(tmp_path):
    """MB035: an empty `ExpectedOutcome` evaluates to ERROR. Admitting one
    would put an unverifiable step into the Runtime."""
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)
    unusable = MissionPlan(
        steps=[
            Step(
                step_id="x",
                capability="Filesystem.CreateFolder",
                payload={},
                expected_outcome=ExpectedOutcome(description="nothing checked", checks=[]),
            )
        ],
        objective="o",
    )
    service = MissionService(
        planner=IncompletePlanner(unusable),
        mission_control=system.mission_control,
        intent_layer=IntentLayer(),
    )

    outcome = service.start("do it")

    assert outcome.status == REJECTED
    assert outcome.reasons == ("x: expected outcome states no checks",)


def test_a_complete_hand_built_plan_is_accepted_by_the_gate(tmp_path):
    """The gate judges fields, not producers -- so a correct plan from
    anywhere is admitted."""
    system = pipeline(TWO_STEPS, tmp_path=tmp_path)
    usable = MissionPlan(
        steps=[
            Step(
                step_id="x",
                capability="Filesystem.CreateFolder",
                payload={"name": "demo"},
                expected_outcome=ExpectedOutcome(
                    description="a folder",
                    checks=[
                        ObservationCheck(
                            field="empty", operator="equals", value=False, description="not blank"
                        )
                    ],
                ),
            )
        ],
        objective="o",
    )
    service = MissionService(
        planner=IncompletePlanner(usable),
        mission_control=system.mission_control,
        intent_layer=IntentLayer(),
        history=system.history,
    )

    outcome = service.start("do it")

    assert outcome.status == ACCEPTED
    assert outcome.provider_id == "somewhere"
    assert outcome.entry_id == 11


# =========================================================================
# A history with no store behaviour to speak of
# =========================================================================


def test_recording_the_same_plan_id_twice_replaces_rather_than_duplicates():
    """Only reachable if a caller reuses an objective id. One row per
    mission is the invariant every read here assumes."""
    history = PlanHistory()
    plan = MissionPlan(
        steps=[Step(step_id="a", capability="X.Y", payload={})], objective="o"
    )

    history.record_plan("same", "first", plan)
    history.record_plan("same", "second", plan)

    assert len(history.all()) == 1
    assert history.get("same").objective == "second"


def test_a_history_reads_back_what_it_recorded_without_a_store():
    history = PlanHistory()
    plan = MissionPlan(
        steps=[Step(step_id="a", capability="X.Y", payload={})], objective="o"
    )

    record = history.record_plan("p1", "do it", plan)

    assert history.get("p1") is record
    assert history.latest() is record
    assert history.current() is record
