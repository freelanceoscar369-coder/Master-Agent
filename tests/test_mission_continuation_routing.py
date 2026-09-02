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

    assert "route = route_brain_action(" in source
    assert "if not route.calls_planner:" in source
    # and it stops rather than falling through to `mission_service.start`
    assert "_stop_for_route(route, status, needed," in source
    # the paused mission's attempts travel with the question
    assert "objective_ids=attempts_made" in source


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


# ---------------------------------------------------------------------
# GATE A -- the founder decision round-trip
# ---------------------------------------------------------------------


def founder_question_state():
    """The exact live Stage-4 state: an irreducible tie, parked."""
    from master_agent.missions.execution_status import ExecutionStatus

    need = kd._evidence_question(
        decided_with(tie=True),
        MissionProgress(
            objective="the founder's own words",
            satisfied=tuple(f"req_{i}" for i in range(1, 9)),
            unresolved=("req_9", "req_10"),
            evidence_ids=("ev_1", "ev_2", "ev_3"),
        ),
        [],
    )
    status = ExecutionStatus()
    kd._stop_for_route(kd.route_brain_action(need), status, need,
                       "the founder's own words",
                       objective_ids=("obj_1", "obj_2"))
    return need, status


def test_gate_a_the_question_carries_the_mission_it_interrupted():
    """The attempts are the only handle on established Evidence."""
    _, status = founder_question_state()
    pending = status.pending_clarification

    assert pending.mission_objective_ids == ("obj_1", "obj_2")
    assert pending.decision["action"] == "ask_founder"
    assert pending.objective == "the founder's own words"
    assert pending.clarification_id            # correlation already existed


def test_gate_a_the_answer_resumes_rather_than_restarts():
    """`_carried_objective_ids` is what makes the resumed mission read the
    Evidence the paused one established."""
    _, status = founder_question_state()
    pending = status.pending_clarification

    class Result:
        intent = type("I", (), {"context": {}})()

    Result.intent.context["founder_decision"] = {
        "answer": "Claude Computer Use",
        "objective_ids": list(pending.mission_objective_ids),
    }

    assert kd._carried_objective_ids(Result) == ("obj_1", "obj_2")


def test_gate_a_an_answered_decision_is_not_asked_again():
    """Without this the founder cannot escape: the Brain re-derives the
    same tie from the same Evidence every cycle, because Evidence was
    never what was missing."""
    need, _ = founder_question_state()
    answered = {
        "answer": "Claude Computer Use",
        "target_requirements": list(need["target_requirements"]),
    }

    routed = kd.route_brain_action(need, founder_decision=answered)

    assert routed.calls_planner is True
    assert routed.action == "finalize_from_canonical_decision"
    assert routed.terminal is False


def test_gate_a_the_answer_reaches_the_brain_not_the_planner_directly():
    """§8: an answer is authoritative mission information, not a plan."""
    need, _ = founder_question_state()
    answered = {"answer": "Claude Computer Use",
                "target_requirements": list(need["target_requirements"])}

    routed = kd.route_brain_action(need, founder_decision=answered)

    # It routes to the Planner only because the BRAIN's next action is
    # now finalisation -- the answer never names a capability or a step.
    assert routed.consumer == "planner"
    assert "answer" not in routed.reason
    assert set(answered) == {"answer", "target_requirements"}


def test_gate_a_a_stale_answer_does_not_settle_a_different_decision():
    """§7. An answer about req_9 must not silently resolve a later
    question about a different requirement."""
    need, _ = founder_question_state()
    stale = {"answer": "Claude Computer Use", "target_requirements": ["req_4"]}

    routed = kd.route_brain_action(need, founder_decision=stale)

    assert routed.calls_planner is False
    assert routed.consumer == "founder_question"


def test_gate_a_an_empty_answer_settles_nothing():
    need, _ = founder_question_state()

    for empty in ({}, None, {"target_requirements": ["req_9"]},
                  {"answer": "", "target_requirements": ["req_9"]}):
        routed = kd.route_brain_action(need, founder_decision=empty)
        assert routed.consumer == "founder_question", empty


def test_gate_a_the_resume_path_attaches_the_judgement_to_the_mission():
    source = inspect.getsource(kd._submit_objective)

    assert 'pending.key == "founder_decision"' in source
    assert '"objective_ids": list(pending.mission_objective_ids)' in source
    assert '"clarification_id": pending.clarification_id' in source


def test_gate_a_an_ordinary_clarification_carries_no_mission():
    """A Stage-1 missing field has no mission to resume, and must not
    acquire one."""
    from master_agent.missions.execution_status import PendingClarification

    ordinary = PendingClarification(
        question="What should the folder be called?", key="name",
        objective="Create a folder on my Desktop")

    assert ordinary.mission_objective_ids == ()
    assert ordinary.decision is None


# ---------------------------------------------------------------------
# GATE B -- continuation throughput, on controlled provider output
#
# The live sample says the same Brain decision produces a different
# defect nearly every attempt. These pin what the system does with each
# defect, so throughput is a property of the correction loop rather than
# of whichever mistake a provider happened to make that minute.
# ---------------------------------------------------------------------

import json as _json

from master_agent.verification.evidence import Verdict as _Verdict

from master_agent.planner.catalogue import CapabilityOption
from master_agent.planner.plan import Intent as PlanIntent
from master_agent.planner.plan import SemanticRequirement as Req
from master_agent.planner.planner import Planner

RIDS = ("req_1", "req_2", "req_3")


def gate_b_options():
    return (
        CapabilityOption(name="Browser.Search", description="search",
                         required_args=("query",), optional_args=("query",),
                         output_fields=("text",)),
        CapabilityOption(name="Browser.ReadPageText", description="read",
                         required_args=("url",), optional_args=("url",),
                         output_fields=("text",)),
        CapabilityOption(name="Reasoning.Transform", description="reason",
                         required_args=("instruction",),
                         optional_args=("instruction", "text", "context"),
                         output_fields=("text",)),
    )


def gate_b_intent(target="req_1", satisfied=()):
    context = {"raw_input": "objective",
               "decision_frame": {"objective": "objective"},
               "evidence_needed": {"action": "acquire_evidence",
                                   "target_requirements": [target]}}
    if satisfied:
        context["recovery"] = {"satisfied": list(satisfied), "unresolved": []}
    intent = PlanIntent(goal="objective", context=context)
    intent.requirements = tuple(
        Req(requirement_id=r, kind="information", description="do " + r,
            provenance="founder", founder_evidence="founder")
        for r in RIDS
    )
    return intent


def plan_step(step_id, capability, covers, **extra):
    step = {"id": step_id, "capability": capability, "covers": list(covers),
            "payload": {"query": "public sources"},
            "success": {"description": "usable evidence"}}
    if capability == "Browser.ReadPageText":
        step["payload"] = {"url": "https://example.test"}
    if capability == "Reasoning.Transform":
        step["payload"] = {"instruction": "summarise"}
    step.update(extra)
    return step


class ScriptedRunner:
    """A provider that says exactly what the test tells it to say.

    Drives the REAL `Planner.plan()`, so the correction pass, the
    coverage contract and every validator are the production ones.
    """

    def __init__(self, *replies):
        self._replies = list(replies)
        self.prompts = []

    def run(self, prompt, request=None, **kwargs):
        self.prompts.append(prompt)
        document = self._replies.pop(0) if self._replies else {"steps": []}
        text = _json.dumps(document)

        class Reply:
            """Only what `Planner.plan()` actually reads off an outcome."""

            refused = False
            ok = True
            reason = ""
            refusal = None
            entry_id = 1
            provider_id = "scripted"
            # The Planner checks the plan TEXT against an expectation
            # before parsing it, so a stand-in carries a verdict the way
            # the real Evidence does -- the same shape
            # `test_planner_self_correction.py` already uses.
            evidence = type(
                "PlanEvidence", (),
                {"observation": {"json": document, "text": text},
                 "verdict": _Verdict.MATCHED},
            )()

        Reply.text = text
        return Reply()


def gate_b_plan(*replies, target="req_1", satisfied=()):
    runner = ScriptedRunner(*replies)
    outcome = Planner(runner, gate_b_options()).plan(
        gate_b_intent(target, satisfied))
    return outcome, runner


def test_t1_a_clean_narrow_plan_is_admitted():
    outcome, runner = gate_b_plan(
        {"steps": [plan_step("s1", "Browser.Search", ["req_1"])]})

    assert outcome.refusal is None, outcome.refusal
    assert len(runner.prompts) == 1, "a valid plan must not cost a correction"


def test_t2_whole_mission_expansion_is_rejected():
    whole = {"steps": [plan_step("s" + str(i), "Browser.Search", [r])
                       for i, r in enumerate(RIDS, start=1)]}

    outcome, _ = gate_b_plan(whole, whole)

    assert outcome.plan is None
    assert "untargeted" in outcome.refusal.reason


def test_t3_forbidden_satisfied_work_is_repaired_without_scope_drift():
    """The bounded correction may fix the plan; it may not renegotiate
    which requirement the plan is for."""
    bad = {"steps": [plan_step("s1", "Browser.Search", ["req_1"]),
                     plan_step("s2", "Browser.Search", ["req_2"])]}
    good = {"steps": [plan_step("s1", "Browser.Search", ["req_1"])]}

    outcome, runner = gate_b_plan(bad, good, target="req_1",
                                  satisfied=("req_2",))

    assert outcome.refusal is None, outcome.refusal
    assert outcome.corrected is True
    assert len(runner.prompts) == 2
    claims = sorted({c for s in outcome.plan.steps for c in s.covers})
    assert claims == ["req_1"], "the repair widened the scope of the plan"


def test_t4_an_invented_output_field_is_rejected():
    """`answers_founder` must name a field the capability publishes."""
    invented = {"steps": [plan_step("s1", "Browser.Search", ["req_1"],
                                    answers_founder="verdict")]}

    outcome, _ = gate_b_plan(invented, invented)

    assert outcome.plan is None
    assert "not published" in outcome.refusal.reason


def test_t4b_a_real_published_field_is_accepted():
    outcome, _ = gate_b_plan(
        {"steps": [plan_step("s1", "Browser.Search", ["req_1"],
                             answers_founder="text")]})

    assert outcome.refusal is None, outcome.refusal


def test_t5_missing_covers_is_corrected_not_inferred():
    """One target, one step -- and still nobody guesses. The plan is
    refused until the model itself says what the step is for."""
    missing = {"steps": [{"id": "s1", "capability": "Browser.Search",
                          "payload": {"query": "x"},
                          "success": {"description": "d"}}]}

    outcome, _ = gate_b_plan(missing, missing)

    assert outcome.plan is None, "responsibility was inferred"


def test_t6_a_malformed_binding_is_corrected_without_target_expansion():
    # A real dataflow binding is an OBJECT. A bare string under
    # `input_bindings` is a literal by design (see
    # `materialise_binding_dependencies`), so this names a step that does
    # not exist -- the defect the correction pass has to repair.
    malformed = {"steps": [
        plan_step("s1", "Browser.Search", ["req_1"]),
        dict(plan_step("s2", "Reasoning.Transform", ["req_1"]),
             input_bindings={
                 "text": {"from_step": {"step_id": "s_nope", "field": "text"}}},
             depends_on=[]),
    ]}
    repaired = {"steps": [
        plan_step("s1", "Browser.Search", ["req_1"]),
        dict(plan_step("s2", "Reasoning.Transform", ["req_1"]),
             input_bindings={
                 "text": {"from_step": {"step_id": "s1", "field": "text"}}},
             depends_on=["s1"]),
    ]}

    outcome, runner = gate_b_plan(malformed, repaired)

    assert outcome.refusal is None, outcome.refusal
    assert len(runner.prompts) == 2
    claims = sorted({c for s in outcome.plan.steps for c in s.covers})
    assert claims == ["req_1"]


def test_t7_a_correction_that_repeats_the_defect_ends_in_refusal():
    """Bounded at one. A model that cannot fix it given the exact error
    is not going to on the third try, and the founder waits through each."""
    same = {"steps": [plan_step("s" + str(i), "Browser.Search", [r])
                      for i, r in enumerate(RIDS, start=1)]}

    outcome, runner = gate_b_plan(same, same, same)

    assert outcome.plan is None
    assert len(runner.prompts) == 2, "the correction pass is not bounded at one"


def test_t8_a_verbose_but_contract_valid_plan_is_admitted():
    """Throughput is about the contract, not about brevity."""
    verbose = {"steps": [plan_step("s" + str(i), "Browser.Search", ["req_1"])
                         for i in range(1, 13)]}

    outcome, _ = gate_b_plan(verbose)

    assert outcome.refusal is None, outcome.refusal
    assert len(outcome.plan.steps) == 12


# ---------------------------------------------------------------------
# GATE C / GATE D -- one mission, seven cycles, through the real chain
#
# The Brain, the router, the coverage contract and every validator are
# production. Only two things are controlled: what execution established
# between cycles, and what the provider replies -- so this proves the
# continuation chain rather than whichever plan a provider happened to
# produce that minute. Live admission rate is measured separately.
# ---------------------------------------------------------------------

MISSION_IDS = tuple("req_%d" % i for i in range(1, 11))


def mission_requirements():
    return tuple(
        Req(requirement_id=r, kind="information", description="obligation " + r,
            provenance="founder said", founder_evidence="founder said",
            candidate_property=r in ("req_3", "req_4", "req_5", "req_6"))
        for r in MISSION_IDS
    )


def mission_frame():
    from master_agent.brain.deliberation import frame_for

    return frame_for(objective="the founder's own words",
                     requirements=mission_requirements())


def continuation_intent():
    """THE one Intent. Built once, and never rebuilt after this."""
    intent = PlanIntent(goal="the founder's own words", context={
        "raw_input": "the founder's own words",
        "decision_frame": mission_frame().as_dict(),
    })
    intent.requirements = mission_requirements()
    return intent


def insufficient(frame):
    from master_agent.brain.deliberation import DeliberationResult

    return DeliberationResult(
        state="insufficient_evidence",
        requirement_ids=frame.requirement_ids,
        decision_requirement_ids=frame.decision_requirement_ids,
        candidate_prerequisite_ids=frame.candidate_prerequisite_ids,
        criteria={c.criterion_id: c.description for c in frame.mandatory},
        criterion_requirements={c.criterion_id: c.requirement_id
                                for c in frame.mandatory},
        more_research=True,
    )


def plan_for(intent, target, capability="Browser.Search"):
    """Plan this continuation with a provider that answers correctly."""
    from master_agent.planner.plan import strategy_coverage

    runner = ScriptedRunner(
        {"steps": [plan_step("s1", capability, [target])]})
    outcome = Planner(runner, gate_b_options()).plan(intent)
    _, forbidden = strategy_coverage(intent)
    return outcome, forbidden


def test_gate_c_one_mission_seven_cycles_end_to_end():
    from master_agent.brain.deliberation import MissionProgress

    frame = mission_frame()
    intent = continuation_intent()
    identity = id(intent)
    log = []

    def cycle(label, result, progress, founder_decision=None):
        need = (kd._evidence_question(result, progress, [])
                if result is not None else None)
        route = kd.route_brain_action(need, founder_decision=founder_decision)
        log.append((label, (need or {}).get("action", "complete"), route.consumer))
        return need, route

    # -- CYCLE 1: nothing established --------------------------------
    p1 = MissionProgress(objective=intent.goal, unresolved=MISSION_IDS)
    need1, route1 = cycle("c1", insufficient(frame), p1)
    assert route1.calls_planner is True
    target1 = need1["target_requirements"][0]
    assert target1 == "req_1"
    intent.context["recovery"] = p1.as_dict()
    intent.context["evidence_needed"] = need1
    out1, forbidden1 = plan_for(intent, target1)
    assert out1.refusal is None, out1.refusal
    assert sorted({c for s in out1.plan.steps for c in s.covers}) == [target1]
    assert not set(forbidden1) & {target1}

    # -- CONTROLLED RESULT 1: landscape established ------------------
    p2 = MissionProgress(objective=intent.goal, satisfied=("req_1",),
                         unresolved=MISSION_IDS[1:], evidence_ids=("ev_1",),
                         observation_signatures=("landscape",))

    # -- CYCLE 2: qualification --------------------------------------
    need2, route2 = cycle("c2", insufficient(frame), p2)
    assert route2.calls_planner is True
    target2 = need2["target_requirements"][0]
    assert target2 == "req_2", target2
    intent.context["recovery"] = p2.as_dict()
    intent.context["evidence_needed"] = need2
    out2, _ = plan_for(intent, target2, "Reasoning.Transform")
    assert out2.refusal is None, out2.refusal

    # -- CYCLE 3: criterion evidence ---------------------------------
    p3 = MissionProgress(objective=intent.goal, satisfied=MISSION_IDS[:2],
                         unresolved=MISSION_IDS[2:],
                         evidence_ids=("ev_1", "ev_2"),
                         observation_signatures=("landscape", "top-three"))
    need3, route3 = cycle("c3", insufficient(frame), p3)
    assert route3.calls_planner is True
    target3 = need3["target_requirements"][0]
    intent.context["recovery"] = p3.as_dict()
    intent.context["evidence_needed"] = need3
    out3, _ = plan_for(intent, target3, "Browser.ReadPageText")
    assert out3.refusal is None, out3.refusal

    # -- GATE D: strategy A exhausted, no useful progress ------------
    from master_agent.brain.deliberation import no_useful_progress
    from master_agent.planner.planner import _exhausted_routes

    dead = "Browser.ReadPageText https://dead.example"
    p4 = MissionProgress(objective=intent.goal, satisfied=MISSION_IDS[:2],
                         unresolved=MISSION_IDS[2:],
                         evidence_ids=("ev_1", "ev_2"),
                         observation_signatures=("landscape", "top-three"),
                         failed_routes=(dead,))
    assert no_useful_progress(p3, p4) is False, (
        "eliminating a route IS progress")
    need4, route4 = cycle("recovery", insufficient(frame), p4)
    assert route4.calls_planner is True
    assert need4["exhausted_strategies"] == [dead]
    intent.context["evidence_needed"] = need4
    assert _exhausted_routes(intent) == (dead,)
    assert need4["target_requirements"] == need3["target_requirements"], (
        "recovery abandoned the requirement instead of the route")

    # -- CYCLE 4: an irreducible founder tradeoff --------------------
    p5 = MissionProgress(objective=intent.goal, satisfied=MISSION_IDS[:8],
                         unresolved=MISSION_IDS[8:],
                         evidence_ids=("ev_1", "ev_2", "ev_3"))
    need5, route5 = cycle("founder", decided_with(tie=True), p5)
    assert need5["action"] == "ask_founder"
    assert route5.calls_planner is False
    assert route5.consumer == "founder_question"

    status = ExecutionStatusFor()
    kd._stop_for_route(route5, status, need5, intent.goal,
                       objective_ids=("obj_1", "obj_2", "obj_3"))
    assert status.pending_clarification.mission_objective_ids == (
        "obj_1", "obj_2", "obj_3")

    # -- CONTROLLED FOUNDER ANSWER, through the carried question -----
    pending = status.pending_clarification
    answer = {
        "clarification_id": pending.clarification_id,
        "answer": "Claude Computer Use",
        "target_requirements": list(pending.decision["target_requirements"]),
        "objective_ids": list(pending.mission_objective_ids),
    }
    intent.context["founder_decision"] = answer

    # -- CYCLE 5: the same mission resumes ---------------------------
    need6, route6 = cycle("post-answer", decided_with(tie=True), p5,
                          founder_decision=answer)
    assert route6.calls_planner is True
    assert route6.action == "finalize_from_canonical_decision"

    # -- CYCLE 6: finalisation plans the deliverable -----------------
    p6 = MissionProgress(objective=intent.goal, satisfied=MISSION_IDS[:9],
                         unresolved=("req_10",),
                         evidence_ids=("ev_1", "ev_2", "ev_3"))
    intent.context["recovery"] = p6.as_dict()
    intent.context["evidence_needed"] = {
        "action": "finalize_from_canonical_decision",
        "target_requirements": ["req_10"]}
    out6, _ = plan_for(intent, "req_10", "Reasoning.Transform")
    assert out6.refusal is None, out6.refusal
    assert sorted({c for s in out6.plan.steps for c in s.covers}) == ["req_10"]

    # -- CYCLE 7: complete -------------------------------------------
    need7, route7 = cycle("complete", None, p6)
    assert route7.calls_planner is False
    assert route7.consumer == "mission_complete"
    assert route7.terminal is True

    # -- the invariants ----------------------------------------------
    assert id(intent) == identity, "the mission was rebuilt"
    assert tuple(r.requirement_id for r in intent.requirements) == MISSION_IDS
    actions = [row[1] for row in log]
    assert actions[0] != actions[-1]
    assert "ask_founder" in actions
    assert len(set(actions)) >= 3, actions


def ExecutionStatusFor():
    from master_agent.missions.execution_status import ExecutionStatus

    return ExecutionStatus()


def test_gate_d_a_cycle_that_established_nothing_stops_the_loop():
    """Activity is not progress, and the loop must not spend the founder's
    time proving it twice."""
    from master_agent.brain.deliberation import no_useful_progress, progress_of

    before = progress_of("objective", (), ())
    after = progress_of("objective", (), ())

    assert no_useful_progress(before, after) is True
    assert "if no_useful_progress(before, after):" in inspect.getsource(kd)


def test_plan_completion_is_not_mission_completion():
    """§20/§21. A finished plan returns control to the Brain; only the
    Brain's own 'nothing further' ends the mission."""
    from master_agent.brain.deliberation import MissionProgress

    frame = mission_frame()
    # every plan so far has succeeded, and the mission is NOT complete
    progress = MissionProgress(objective="the founder's own words",
                               satisfied=MISSION_IDS[:2],
                               unresolved=MISSION_IDS[2:],
                               evidence_ids=("ev_1", "ev_2"))
    need = kd._evidence_question(insufficient(frame), progress, [])

    assert need is not None, "a finished plan was taken for a finished mission"
    assert kd.route_brain_action(need).calls_planner is True
    # and the mission ends only when the Brain has nothing further
    assert kd.route_brain_action(None).consumer == "mission_complete"
