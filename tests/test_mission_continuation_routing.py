"""Stage 4: the mission keeps thinking, and the Brain's action decides
which subsystem thinks next.

The continuation loop is real and it lives in the composition root: it
builds `MissionProgress` from what execution actually established, writes
it back onto the SAME `Intent`, asks the Brain again, and re-admits the
mission through the same `MissionService`. What it does not do is read
the Brain's `action` as a control decision -- every need it receives is
sent to the Planner, including one that says only the Founder can settle
this.

These probes drive the real composition-root functions and the real
Brain. Nothing here executes a mission.
"""
from __future__ import annotations

import inspect

import kalpavriksha_desktop as kd
from master_agent.brain.deliberation import (
    DECIDED,
    MET,
    UNVERIFIED,
    Candidate,
    Criterion,
    DecisionFrame,
    DeliberationResult,
    MissionProgress,
    next_evidence_need,
    no_useful_progress,
    progress_of,
    recovery_for,
)

CRITERIA = ("pricing", "browser", "autonomy", "memory")


def frame(objective="the founder's own words"):
    return DecisionFrame(
        objective=objective,
        requirement_ids=tuple(f"req_{i}" for i in range(1, 11)),
        decision_requirement_ids=("req_9",),
        decision_type="selection",
        mandatory=tuple(
            Criterion(criterion_id=name, description=f"compare {name}",
                      requirement_id=f"req_{i}", mandatory=True)
            for i, name in enumerate(CRITERIA, start=3)
        ),
    )


def decided_with(*, tie=True, unverified=False):
    """A real DeliberationResult in the shape production produces."""
    criteria = {c.criterion_id: c.description for c in frame().mandatory}
    verdict = {name: (UNVERIFIED if unverified else MET) for name in criteria}
    names = ("Adept ACT-1", "Claude Computer Use") if tie else ("Adept ACT-1",)
    shortlist = tuple(
        Candidate(candidate_id=name.lower().replace(" ", "_"),
                  summary=name, criteria=dict(verdict))
        for name in names
    )
    f = frame()
    return DeliberationResult(
        state=DECIDED, shortlist=shortlist, candidates=shortlist,
        requirement_ids=f.requirement_ids,
        decision_requirement_ids=f.decision_requirement_ids,
        candidate_prerequisite_ids=f.candidate_prerequisite_ids,
        criteria=criteria,
        criterion_requirements={
            c.criterion_id: c.requirement_id for c in f.mandatory},
    )


# ---------------------------------------------------------------------
# P1 / P7 / P8 -- the continuation owner, and the state it produces
# ---------------------------------------------------------------------


def test_p1_the_continuation_owner_exists_and_is_one_bounded_loop():
    """It is the composition root, not a new engine, and it is bounded."""
    source = inspect.getsource(kd)

    assert "_RESEARCH_BUDGET" in source
    assert "attempts < _RESEARCH_BUDGET" in source
    # the same mission is re-admitted through the existing owner
    assert "retried = mission_service.start(intent_result.intent)" in source


def test_p7_the_loop_produces_the_recovery_state_the_planner_reads():
    """`strategy_coverage` reads `context["recovery"]`; this writes it."""
    source = inspect.getsource(kd)

    assert 'intent_result.intent.context["recovery"] = before.as_dict()' in source


def test_p8_the_recovery_owner_is_the_brain_not_a_second_policy():
    assert "recovery_for" in inspect.getsource(kd._recovery_decision)


def test_p11_activity_is_not_progress():
    """Two cycles that established nothing must not read as advancement."""
    before = progress_of("objective", (), ())
    after = progress_of("objective", (), ())

    assert no_useful_progress(before, after) is True


def test_p11b_the_loop_stops_when_nothing_was_established():
    assert "if no_useful_progress(before, after):" in inspect.getsource(kd)


# ---------------------------------------------------------------------
# P19 / P20 / P21 -- one mission across cycles
# ---------------------------------------------------------------------


def test_p19_the_next_cycle_reuses_the_same_intent_object():
    """Not a rebuilt Intent: the same object, with knowledge added.

    A reconstructed Intent would be a new mission wearing the old
    objective's words, and every requirement id would be freshly minted.
    """
    source = inspect.getsource(kd)

    assert 'intent_result.intent.context["evidence_needed"] = needed' in source
    assert "mission_service.start(intent_result.intent)" in source
    # every attempt this objective made, not just the newest record
    assert "attempts_made.append(objective_id)" in source


def test_p21_progress_reads_every_attempt_not_only_the_last():
    """Evidence accumulates across cycles."""
    assert "objective_ids" in inspect.signature(kd._observations_from).parameters


# ---------------------------------------------------------------------
# P2 / P12 / P18 -- the Brain's action as a control decision
# ---------------------------------------------------------------------


def test_the_brain_really_does_ask_for_a_founder_judgement():
    """Not hypothetical: this is the Stage-2 last-resort question, from
    the real Brain, in the state that produces it."""
    result = decided_with(tie=True)
    progress = MissionProgress(
        objective="the founder's own words",
        satisfied=tuple(f"req_{i}" for i in range(1, 9)),
        unresolved=("req_9", "req_10"),
    )

    need = next_evidence_need(result, progress)

    assert need is not None
    assert need.action == "ask_founder"


def test_p12_a_founder_judgement_must_not_be_routed_to_the_planner():
    """THE Stage-4 defect.

    `_evidence_question` hands the loop whatever the Brain decided, and
    the loop sends every need it receives to `mission_service.start()`,
    which plans. An `ask_founder` need therefore becomes a research plan:
    the system goes looking for evidence to settle a question that no
    amount of evidence can settle, because what is missing is the
    Founder's preference between two candidates that already satisfy
    every stated criterion.
    """
    need = kd._evidence_question(
        decided_with(tie=True),
        MissionProgress(
            objective="the founder's own words",
            satisfied=tuple(f"req_{i}" for i in range(1, 9)),
            unresolved=("req_9", "req_10"),
        ),
        [],
    )

    assert need is not None
    assert need["action"] == "ask_founder"

    routed = kd.route_brain_action(need)

    assert routed.calls_planner is False, (
        "an ask_founder decision was routed to the Planner")
    assert routed.consumer == "founder_question"


def test_p14_an_evidence_need_still_routes_to_the_planner():
    need = {"action": "acquire_evidence", "target_requirements": ["req_3"]}

    routed = kd.route_brain_action(need)

    assert routed.calls_planner is True
    assert routed.terminal is False


def test_p14b_finalisation_routes_to_the_planner():
    routed = kd.route_brain_action(
        {"action": "finalize_from_canonical_decision",
         "target_requirements": ["req_10"]})

    assert routed.calls_planner is True
    assert routed.consumer == "planner"


def test_p15_completion_does_not_call_the_planner():
    """No need at all is the Brain saying there is nothing left to find."""
    routed = kd.route_brain_action(None)

    assert routed.calls_planner is False
    assert routed.terminal is True
    assert routed.consumer == "mission_complete"


def test_p18_an_unknown_brain_action_fails_closed():
    """It does not guess the Planner, and it does not quietly complete."""
    routed = kd.route_brain_action({"action": "teleport_the_founder"})

    assert routed.calls_planner is False
    assert routed.terminal is True
    assert routed.consumer == "unsupported"
    assert "teleport_the_founder" in routed.reason


def test_p17_a_terminal_route_is_not_the_same_as_mission_complete():
    """Stop-state truth: an unsupported action and a completed mission
    both stop the loop, and they are not the same outcome."""
    unsupported = kd.route_brain_action({"action": "teleport_the_founder"})
    complete = kd.route_brain_action(None)
    question = kd.route_brain_action({"action": "ask_founder"})

    consumers = {unsupported.consumer, complete.consumer, question.consumer}
    assert len(consumers) == 3, "three different stops collapsed into one"


def test_p2_every_action_the_brain_can_emit_has_a_consumer():
    """No produced action may be left without a production consumer."""
    emitted = ("discover_candidates", "qualify_candidates", "acquire_evidence",
               "finalize_from_canonical_decision", "ask_founder")

    for action in emitted:
        routed = kd.route_brain_action({"action": action})
        assert routed.consumer, f"{action} has no consumer"
        assert routed.consumer != "unsupported", f"{action} is unrouted"


# ---------------------------------------------------------------------
# The router is wired, not merely defined
# ---------------------------------------------------------------------


def test_the_loop_consults_the_router_before_replanning():
    """A router nobody calls is the declared-but-never-produced shape
    every stage before this one kept finding."""
    source = inspect.getsource(kd)

    assert "route = route_brain_action(needed)" in source
    assert "if not route.calls_planner:" in source
    # and it stops rather than falling through to `mission_service.start`
    assert "_stop_for_route(route, status, needed," in source


def test_a_founder_judgement_becomes_a_real_pending_question():
    """It reaches the mechanism that already exists for a fact only the
    founder holds, carrying the Brain's own question and options."""
    from master_agent.missions.execution_status import (
        AWAITING_CLARIFICATION, ExecutionStatus,
    )

    status = ExecutionStatus()
    need = kd._evidence_question(
        decided_with(tie=True),
        MissionProgress(
            objective="the founder's own words",
            satisfied=tuple(f"req_{i}" for i in range(1, 9)),
            unresolved=("req_9", "req_10"),
        ),
        [],
    )
    route = kd.route_brain_action(need)

    kd._stop_for_route(route, status, need, "the founder's own words")

    assert status.status == AWAITING_CLARIFICATION
    assert status.pending_clarification is not None
    assert status.pending_clarification.key == "founder_decision"
    assert status.pending_clarification.question
    assert len(status.pending_clarification.options) == 2


def test_an_unsupported_action_fails_closed_on_the_status():
    from master_agent.missions.execution_status import ExecutionStatus, FAILED

    status = ExecutionStatus()
    route = kd.route_brain_action({"action": "teleport_the_founder"})

    kd._stop_for_route(route, status, {"action": "teleport_the_founder"}, "x")

    assert status.status == FAILED
    assert any("teleport_the_founder" in e for e in status.errors)
    assert status.pending_clarification is None


def test_a_completion_stop_writes_neither_a_failure_nor_a_question():
    from master_agent.missions.execution_status import ExecutionStatus

    status = ExecutionStatus()
    kd._stop_for_route(kd.route_brain_action(None), status, None, "x")

    assert status.pending_clarification is None
    assert status.errors == []


# ---------------------------------------------------------------------
# P9 / P10 -- an exhausted strategy reaches the Planner as a constraint
# ---------------------------------------------------------------------


def test_p9_an_exhausted_route_travels_from_progress_to_the_planner():
    """Proven live. The Brain keeps targeting the requirement -- it is
    still unresolved, so that is the right target -- and what must differ is
    the ROUTE. The exhausted one reaches the Planner as a constraint
    rather than as advice, and `validate()` refuses a plan that repeats
    it unchanged.
    """
    from master_agent.planner.plan import Intent
    from master_agent.planner.planner import _exhausted_routes

    dead = "Browser.ReadPageText https://dead.example/pricing"
    result = DeliberationResult(
        state="insufficient_evidence",
        requirement_ids=frame().requirement_ids,
        decision_requirement_ids=frame().decision_requirement_ids,
        criteria={c.criterion_id: c.description for c in frame().mandatory},
        criterion_requirements={
            c.criterion_id: c.requirement_id for c in frame().mandatory},
        more_research=True,
    )
    progress = MissionProgress(
        objective="the founder's own words",
        satisfied=("req_1", "req_2"),
        unresolved=tuple(f"req_{i}" for i in range(3, 11)),
        failed_routes=(dead,),
    )

    need = kd._evidence_question(result, progress, [])

    assert need["exhausted_strategies"] == [dead]

    intent = Intent(goal="x", context={"evidence_needed": need})
    assert _exhausted_routes(intent) == (dead,)


def test_p10_a_recovery_need_still_routes_to_the_planner():
    """Recovery is executable work; it is not a founder question."""
    routed = kd.route_brain_action({
        "action": "acquire_evidence", "target_requirements": ["req_3"],
        "exhausted_strategies": ["Browser.ReadPageText https://dead.example"],
    })

    assert routed.calls_planner is True
    assert routed.terminal is False
