"""Mission Brief 037 — the record, and replaying from it.

Replay is the claim worth testing hardest: *"replay must never invoke a
provider; replay uses recorded evidence only."* A replay that quietly
re-ran the work would answer a different question than the one asked, and
would spend money doing it.
"""
from __future__ import annotations

import json

import pytest

from master_agent.missions.history import (
    COMPLETED,
    FAILED,
    HISTORY_FILENAME,
    PENDING,
    PLANNED,
    RUNNING,
    InMemoryPlanStore,
    JsonFilePlanStore,
    PlanHistory,
    PlanRecord,
    StepRecord,
)
from tests.missions_test_support import pipeline, plan_text, step
from tests.planner_test_support import CREATE, WRITE, success

THREE_STEPS = plan_text(
    step("a", CREATE.name, {"name": "demo"}),
    step("b", WRITE.name, {"path": "demo/one"}, depends_on=["a"]),
    step("c", WRITE.name, {"path": "demo/two"}, depends_on=["b"],
         success_doc=success("the second file is written")),
)


def started(tmp_path, plan=THREE_STEPS):
    system = pipeline(plan, tmp_path=tmp_path)
    outcome = system.start("Set up a demo project")
    return system, outcome.objective_id


def complete(system, plan_id, step_id, verdict="matched"):
    mc = system.mission_control
    mc.task_started(step_id, objective_id=plan_id)
    mc.verification_completed(
        step_id, verdict=verdict, evidence_id=f"ev-{step_id}", objective_id=plan_id
    )
    mc.task_completed(step_id, objective_id=plan_id)


# =========================================================================
# The record follows the mission
# =========================================================================


def test_a_new_record_starts_planned_with_every_step_pending(tmp_path):
    system, plan_id = started(tmp_path)

    record = system.record(plan_id)

    assert record.state == PLANNED
    assert [s.state for s in record.steps] == [PENDING, PENDING, PENDING]
    assert record.progress == 0.0


def test_the_first_step_is_current_and_the_rest_are_blocked(tmp_path):
    system, plan_id = started(tmp_path)

    record = system.record(plan_id)

    assert record.current.step_id == "a"
    assert [s.step_id for s in record.blocked] == ["b", "c"]


def test_a_running_step_is_the_current_one(tmp_path):
    system, plan_id = started(tmp_path)
    system.mission_control.task_started("a", objective_id=plan_id)

    record = system.record(plan_id)

    assert record.current.step_id == "a"
    assert record.state == RUNNING
    assert [s.step_id for s in record.running] == ["a"]


def test_completing_a_step_makes_the_next_one_current(tmp_path):
    system, plan_id = started(tmp_path)

    complete(system, plan_id, "a")

    record = system.record(plan_id)
    assert record.current.step_id == "b"
    assert [s.step_id for s in record.completed] == ["a"]
    assert [s.step_id for s in record.blocked] == ["c"]


def test_progress_is_completed_over_total(tmp_path):
    system, plan_id = started(tmp_path)

    complete(system, plan_id, "a")

    assert system.record(plan_id).progress == pytest.approx(1 / 3)


def test_a_step_that_completed_without_a_matched_verdict_counts_as_unverified(tmp_path):
    """MB035's line, kept: done and verified are different facts."""
    system, plan_id = started(tmp_path)

    system.mission_control.task_completed("a", objective_id=plan_id)

    record = system.record(plan_id)
    assert [s.step_id for s in record.completed] == ["a"]
    assert [s.step_id for s in record.unverified] == ["a"]


def test_a_matched_verdict_clears_the_unverified_list(tmp_path):
    system, plan_id = started(tmp_path)

    complete(system, plan_id, "a")

    assert system.record(plan_id).unverified == []


def test_an_objective_completing_finishes_the_record(tmp_path):
    system, plan_id = started(tmp_path)
    for step_id in ("a", "b", "c"):
        complete(system, plan_id, step_id)

    record = system.record(plan_id)
    assert record.state == COMPLETED
    assert record.finished_at
    assert record.current is None


def test_a_failed_step_records_the_error_once_not_once_per_retry(tmp_path):
    system, plan_id = started(tmp_path)
    mc = system.mission_control

    mc.task_failed("a", "the same problem", objective_id=plan_id)
    mc.task_failed("a", "the same problem", objective_id=plan_id)

    assert system.record(plan_id).step("a").errors == ["the same problem"]


def test_an_unknown_step_id_reads_as_nothing(tmp_path):
    system, plan_id = started(tmp_path)

    assert system.record(plan_id).step("nowhere") is None


# =========================================================================
# Replay
# =========================================================================


def test_replay_reconstructs_the_mission_in_plan_order(tmp_path):
    system, plan_id = started(tmp_path)
    for step_id in ("a", "b", "c"):
        complete(system, plan_id, step_id)

    replay = system.history.replay(plan_id)

    assert replay.objective == "Set up a demo project"
    assert [s.step_id for s in replay.steps] == ["a", "b", "c"]
    assert [s.order for s in replay.steps] == [1, 2, 3]
    assert replay.complete


def test_replay_carries_the_recorded_evidence_and_nothing_else(tmp_path):
    system, plan_id = started(tmp_path)
    complete(system, plan_id, "a")

    replay = system.history.replay(plan_id)

    first = replay.steps[0]
    assert first.verdict == "matched"
    assert first.evidence_id == "ev-a"
    assert first.verified
    assert replay.evidence_ids == ("ev-a",)


def test_replay_never_contacts_a_provider(tmp_path):
    """The claim, asserted the only way that means anything: the provider
    is watched, and replay is run over a fully recorded mission."""
    system, plan_id = started(tmp_path)
    for step_id in ("a", "b", "c"):
        complete(system, plan_id, step_id)
    calls_before = len(system.runner.calls)

    for _ in range(3):
        system.history.replay(plan_id)

    assert len(system.runner.calls) == calls_before


def test_replay_is_deterministic(tmp_path):
    system, plan_id = started(tmp_path)
    complete(system, plan_id, "a")

    assert system.history.replay(plan_id).as_dict() == system.history.replay(plan_id).as_dict()


def test_replaying_an_unfinished_mission_says_so(tmp_path):
    """A reader must never be shown a partial history as though it were
    the whole story."""
    system, plan_id = started(tmp_path)
    complete(system, plan_id, "a")

    replay = system.history.replay(plan_id)

    assert replay.complete is False
    assert replay.steps[1].state == PENDING


def test_a_failed_mission_replays_as_failed(tmp_path):
    system, plan_id = started(tmp_path)
    system.mission_control.task_failed("a", "no such folder", objective_id=plan_id)

    replay = system.history.replay(plan_id)

    assert replay.steps[0].state == FAILED
    assert replay.steps[0].errors == ("no such folder",)


def test_replaying_a_mission_that_does_not_exist_is_nothing_not_a_crash(tmp_path):
    system, _plan_id = started(tmp_path)

    assert system.history.replay("no-such-mission") is None


def test_the_replay_reports_who_planned_it(tmp_path):
    system, plan_id = started(tmp_path)

    assert system.history.replay(plan_id).planned_by == "alpha-local"


def test_a_replay_serialises_to_plain_json(tmp_path):
    """It has to survive being handed to a front-end that imports none of
    this."""
    system, plan_id = started(tmp_path)
    complete(system, plan_id, "a")

    json.dumps(system.history.replay(plan_id).as_dict())


# =========================================================================
# Reading the history
# =========================================================================


def test_the_current_mission_is_the_one_in_flight(tmp_path):
    system = pipeline(THREE_STEPS, THREE_STEPS, tmp_path=tmp_path)
    first = system.start("first")
    for step_id in ("a", "b", "c"):
        complete(system, first.objective_id, step_id)
    second = system.start("second")

    assert system.history.current().plan_id == second.objective_id


def test_with_nothing_running_the_current_mission_is_the_last_one(tmp_path):
    """A founder asking "what is it doing?" while nothing runs should see
    what it just did, not a blank panel."""
    system, plan_id = started(tmp_path)
    for step_id in ("a", "b", "c"):
        complete(system, plan_id, step_id)

    assert system.history.current().plan_id == plan_id


def test_an_empty_history_has_no_current_mission():
    assert PlanHistory().current() is None
    assert PlanHistory().latest() is None
    assert PlanHistory().all() == ()


# =========================================================================
# Durability
# =========================================================================


def test_a_json_store_survives_a_restart(tmp_path):
    path = tmp_path / HISTORY_FILENAME
    system = pipeline(THREE_STEPS, tmp_path=tmp_path)
    system.history = PlanHistory(store=JsonFilePlanStore(path))
    system.history.attach_to(system.mission_control)
    system.missions.history = system.history
    outcome = system.start("Set up a demo project")
    complete(system, outcome.objective_id, "a")

    reopened = PlanHistory(store=JsonFilePlanStore(path))

    record = reopened.get(outcome.objective_id)
    assert record.objective == "Set up a demo project"
    assert record.step("a").verdict == "matched"
    assert record.step("a").evidence_id == "ev-a"
    assert reopened.replay(outcome.objective_id).steps[0].verified


def test_an_unreadable_history_is_moved_aside_never_overwritten(tmp_path):
    """MB034's rule. A founder can open a `.corrupt` file and read what
    their system did; they cannot recover a file the program replaced."""
    path = tmp_path / HISTORY_FILENAME
    path.write_text("{ this is not json", encoding="utf-8")
    store = JsonFilePlanStore(path)

    assert store.load() == {}
    assert path.with_suffix(path.suffix + ".corrupt").exists()
    assert store.problems and "moved to" in store.problems[0]


def test_a_history_file_missing_its_plans_key_is_treated_as_corrupt(tmp_path):
    path = tmp_path / HISTORY_FILENAME
    path.write_text(json.dumps({"version": 1}), encoding="utf-8")

    assert JsonFilePlanStore(path).load() == {}


def test_a_missing_history_file_is_simply_an_empty_history(tmp_path):
    store = JsonFilePlanStore(tmp_path / "never-written.json")

    assert store.load() == {}
    assert store.problems == []


def test_the_store_writes_a_versioned_document(tmp_path):
    path = tmp_path / HISTORY_FILENAME
    store = JsonFilePlanStore(path)

    store.save({"p1": PlanRecord(plan_id="p1", objective="do it")})

    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["version"] == 1
    assert document["plans"][0]["plan_id"] == "p1"


def test_a_record_round_trips_through_its_dict_form():
    record = PlanRecord(
        plan_id="p1",
        objective="do it",
        planned_by="alpha-local",
        entry_id=4,
        steps=[
            StepRecord(
                step_id="a",
                capability="Filesystem.CreateFolder",
                payload={"name": "demo"},
                depends_on=[],
                expectation="the folder exists",
                checks=["not blank"],
                priority="high",
                estimated_complexity="small",
                state=COMPLETED,
                verdict="matched",
                evidence_id="ev-a",
            )
        ],
    )

    assert PlanRecord.from_dict(record.as_dict()) == record


def test_a_step_record_round_trips_with_only_its_required_fields():
    minimal = StepRecord(step_id="a", capability="X.Y")

    assert StepRecord.from_dict(minimal.as_dict()) == minimal


def test_the_in_memory_store_is_the_default_and_keeps_nothing_on_disk(tmp_path):
    history = PlanHistory()

    assert isinstance(history._store, InMemoryPlanStore)
    assert list(tmp_path.iterdir()) == []
