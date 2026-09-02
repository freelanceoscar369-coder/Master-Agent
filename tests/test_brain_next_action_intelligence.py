"""Stage 2: unresolved is not the same thing as actionable.

The Brain's job between reality changes is to answer one question --
what is the most useful thing that can actually be done NOW -- and to
answer it differently when reality moves. These probes drive the existing
``next_evidence_need`` boundary across a mission's whole life, using the
canonical requirement shape the frozen Stage-1 live PASS produced.

Nothing here calls the Planner. The Brain decides WHAT must change and
WHY; translating that into capabilities is somebody else's boundary.
"""
from __future__ import annotations

import pytest

from master_agent.brain.deliberation import (
    DECIDED,
    DISCOVERY,
    INSUFFICIENT_EVIDENCE,
    MET,
    UNVERIFIED,
    Candidate,
    DeliberationResult,
    MissionProgress,
    RejectedCandidate,
    frame_for,
    next_evidence_need,
)
from master_agent.planner.plan import SemanticRequirement

# --- the frozen live Intent, by requirement id ------------------------
# Labels are for reading the test; production hardcodes none of them.
LANDSCAPE, TOP_THREE = "req_1", "req_2"
PRICING, BROWSER, AUTONOMY, MEMORY, DIFFERENTIATORS = (
    "req_3", "req_4", "req_5", "req_6", "req_7")
EVIDENCE, THREAT, BRIEF = "req_8", "req_9", "req_10"

ALL = (LANDSCAPE, TOP_THREE, PRICING, BROWSER, AUTONOMY, MEMORY,
       DIFFERENTIATORS, EVIDENCE, THREAT, BRIEF)

CRITERIA = {
    "crit_3": "pricing and free access compared",
    "crit_4": "computer and browser use compared",
    "crit_5": "autonomous task execution compared",
    "crit_6": "persistence and memory compared",
    "crit_7": "major differentiators compared",
}
CRITERION_REQUIREMENTS = {
    "crit_3": PRICING, "crit_4": BROWSER, "crit_5": AUTONOMY,
    "crit_6": MEMORY, "crit_7": DIFFERENTIATORS,
}


def candidate(name, **verdicts):
    return Candidate(
        candidate_id=name.lower(),
        summary=name,
        criteria={key: verdicts.get(key, UNVERIFIED) for key in CRITERIA},
    )


def result(state=INSUFFICIENT_EVIDENCE, *, candidates=(), shortlist=(),
           rejected=(), criteria=None, prerequisites=(LANDSCAPE, TOP_THREE)):
    return DeliberationResult(
        state=state,
        candidates=tuple(candidates),
        shortlist=tuple(shortlist),
        rejected=tuple(rejected),
        requirement_ids=ALL,
        candidate_prerequisite_ids=tuple(prerequisites),
        criteria=dict(CRITERIA if criteria is None else criteria),
        criterion_requirements=dict(CRITERION_REQUIREMENTS),
    )


def progress(satisfied=(), *, failed=(), succeeded=()):
    return MissionProgress(
        objective="frozen live objective",
        satisfied=tuple(satisfied),
        unresolved=tuple(r for r in ALL if r not in satisfied),
        failed_routes=tuple(failed),
        successful_routes=tuple(succeeded),
    )


# ---------------------------------------------------------------------
# P1 - the canonical Intent reaches the Brain intact
# ---------------------------------------------------------------------


def test_p1_every_canonical_requirement_reaches_the_decision_frame():
    requirements = tuple(
        SemanticRequirement(
            requirement_id=rid, kind="information",
            description=f"obligation {rid}", provenance="founder said",
            founder_evidence="founder said",
        )
        for rid in ALL
    )

    frame = frame_for(objective="frozen live objective",
                      requirements=requirements)

    assert frame is not None
    # No requirement is dropped and none is invented on the way in:
    # every canonical id is carried, and every mandatory criterion traces
    # back to one of them.
    assert set(frame.requirement_ids) == set(ALL)
    traced = {c.requirement_id for c in frame.mandatory}
    assert traced <= set(ALL)
    assert traced, "no criterion traces to a Founder requirement"
    # The prerequisite chain the Brain needs is identified, not inferred
    # later from requirement order.
    assert set(frame.candidate_prerequisite_ids) <= set(ALL)


# ---------------------------------------------------------------------
# P2 - State 0: unresolved everywhere, actionable only at the root
# ---------------------------------------------------------------------


def test_p2_state_0_targets_the_landscape_not_a_comparison():
    need = next_evidence_need(result(), progress())

    assert need is not None
    assert need.action == "discover_candidates"
    assert need.target_requirements == (LANDSCAPE,)
    assert need.preferred_source_class == DISCOVERY
    # It must NOT pick a comparison, a decision or the deliverable.
    for blocked in (PRICING, BROWSER, AUTONOMY, MEMORY, DIFFERENTIATORS,
                    THREAT, BRIEF):
        assert blocked not in need.target_requirements
    assert "no canonical candidate state" in need.reason


# ---------------------------------------------------------------------
# P3 - State 1: reality moved, so the decision moves
# ---------------------------------------------------------------------


def test_p3_state_1_selects_the_canonical_set_once_subjects_exist():
    found = (candidate("Alpha"), candidate("Beta"), candidate("Gamma"),
             candidate("Delta"))

    need = next_evidence_need(
        result(candidates=found), progress(satisfied=(LANDSCAPE,)))

    assert need is not None
    assert need.action == "qualify_candidates"
    assert need.target_requirements == (TOP_THREE,)
    # It does not repeat discovery, and does not jump to a comparison.
    assert need.action != "discover_candidates"
    assert PRICING not in need.target_requirements
    assert set(need.candidate_ids) == {"alpha", "beta", "gamma", "delta"}


# ---------------------------------------------------------------------
# P4 - State 2: candidate properties become actionable
# ---------------------------------------------------------------------


def test_p4_state_2_asks_for_one_specific_missing_comparison():
    trio = (candidate("Alpha"), candidate("Beta"), candidate("Gamma"))

    need = next_evidence_need(
        result(candidates=trio, shortlist=trio),
        progress(satisfied=(LANDSCAPE, TOP_THREE)))

    assert need is not None
    # ONE criterion, not "do everything that is left".
    assert len(need.target_requirements) == 1
    assert need.target_requirements[0] in (
        PRICING, BROWSER, AUTONOMY, MEMORY, DIFFERENTIATORS)
    assert need.criterion_id in CRITERIA
    assert set(need.candidate_ids) == {"alpha", "beta", "gamma"}
    assert need.reason  # inspectable


# ---------------------------------------------------------------------
# P5 - State 3: satisfied work is not redone
# ---------------------------------------------------------------------


def test_p5_state_3_skips_criteria_that_are_already_established():
    settled = {"crit_3": MET, "crit_6": MET}
    trio = (candidate("Alpha", **settled), candidate("Beta", **settled),
            candidate("Gamma", **settled))

    need = next_evidence_need(
        result(candidates=trio, shortlist=trio),
        progress(satisfied=(LANDSCAPE, TOP_THREE, PRICING, MEMORY)))

    assert need is not None
    # Pricing and memory are established for every candidate; asking again
    # would spend the Founder's time to learn nothing.
    assert need.criterion_id not in ("crit_3", "crit_6")
    assert need.target_requirements[0] not in (PRICING, MEMORY)
    assert need.target_requirements[0] in (BROWSER, AUTONOMY, DIFFERENTIATORS)


# ---------------------------------------------------------------------
# P6 - State 4: an exhausted route must not be handed back
# ---------------------------------------------------------------------


def test_p6_state_4_carries_the_exhausted_routes_into_the_next_decision():
    trio = (candidate("Alpha"), candidate("Beta"), candidate("Gamma"))
    tried = ("Browser.ReadPageText:https://vendor-a.example/pricing",
             "Browser.Navigate:https://vendor-a.example/pricing")

    need = next_evidence_need(
        result(candidates=trio, shortlist=trio),
        progress(satisfied=(LANDSCAPE, TOP_THREE), failed=tried))

    assert need is not None
    # The same mission gap, with what has already failed attached, so the
    # continuation can differ rather than repeat.
    for route in tried:
        assert route in need.exhausted_strategies


# ---------------------------------------------------------------------
# P7 / P8 - evidence is sufficient: finalise rather than keep gathering
# ---------------------------------------------------------------------


def test_p7_state_5_finalises_once_the_candidate_evidence_is_settled():
    met = {key: MET for key in CRITERIA}
    winner = candidate("Alpha", **met)

    need = next_evidence_need(
        DeliberationResult(
            state=DECIDED, shortlist=(winner,), candidates=(winner,),
            requirement_ids=ALL,
            candidate_prerequisite_ids=(LANDSCAPE, TOP_THREE),
            criteria=dict(CRITERIA),
            criterion_requirements=dict(CRITERION_REQUIREMENTS),
        ),
        progress(satisfied=(LANDSCAPE, TOP_THREE, PRICING, BROWSER,
                            AUTONOMY, MEMORY, DIFFERENTIATORS)))

    assert need is not None
    assert need.action == "finalize_from_canonical_decision"
    assert THREAT in need.target_requirements
    assert "alpha" in need.candidate_ids


def test_p8_state_6_finalises_the_deliverable_without_re_researching():
    met = {key: MET for key in CRITERIA}
    winner = candidate("Alpha", **met)

    need = next_evidence_need(
        DeliberationResult(
            state=DECIDED, shortlist=(winner,), candidates=(winner,),
            requirement_ids=ALL,
            candidate_prerequisite_ids=(LANDSCAPE, TOP_THREE),
            criteria=dict(CRITERIA),
            criterion_requirements=dict(CRITERION_REQUIREMENTS),
        ),
        progress(satisfied=(LANDSCAPE, TOP_THREE, PRICING, BROWSER, AUTONOMY,
                            MEMORY, DIFFERENTIATORS, EVIDENCE, THREAT)))

    assert need is not None
    assert need.action == "finalize_from_canonical_decision"
    assert need.target_requirements == (BRIEF,)
    assert need.action != "discover_candidates"


# ---------------------------------------------------------------------
# P9 - State 7: knowing when to stop
# ---------------------------------------------------------------------


def test_p9_state_7_a_satisfied_mission_asks_for_nothing_further():
    met = {key: MET for key in CRITERIA}
    winner = candidate("Alpha", **met)

    need = next_evidence_need(
        DeliberationResult(
            state=DECIDED, shortlist=(winner,), candidates=(winner,),
            requirement_ids=ALL,
            candidate_prerequisite_ids=(LANDSCAPE, TOP_THREE),
            criteria=dict(CRITERIA),
            criterion_requirements=dict(CRITERION_REQUIREMENTS),
        ),
        progress(satisfied=ALL))

    assert need is None


# ---------------------------------------------------------------------
# P13 / P14 - the same intelligence on unrelated missions
# ---------------------------------------------------------------------


def test_p13_supplier_mission_respects_its_own_prerequisite_chain():
    eligible, chosen, emailed = "s_1", "s_2", "s_3"
    criteria = {"crit_price": "supplier pricing compared"}
    frame = DeliberationResult(
        state=INSUFFICIENT_EVIDENCE,
        requirement_ids=(eligible, chosen, emailed),
        candidate_prerequisite_ids=(eligible, chosen),
        criteria=criteria,
        criterion_requirements={"crit_price": chosen},
    )
    empty = MissionProgress(objective="suppliers",
                            unresolved=(eligible, chosen, emailed))

    need = next_evidence_need(frame, empty)

    assert need.action == "discover_candidates"
    assert need.target_requirements == (eligible,)
    assert emailed not in need.target_requirements


def test_p14_game_research_respects_its_own_prerequisite_chain():
    titles, demos, links = "g_1", "g_2", "g_3"
    frame = DeliberationResult(
        state=INSUFFICIENT_EVIDENCE,
        requirement_ids=(titles, demos, links),
        candidate_prerequisite_ids=(titles,),
        criteria={"crit_demo": "a free demo is available"},
        criterion_requirements={"crit_demo": demos},
    )
    empty = MissionProgress(objective="games",
                            unresolved=(titles, demos, links))

    need = next_evidence_need(frame, empty)

    assert need.action == "discover_candidates"
    assert need.target_requirements == (titles,)


# ---------------------------------------------------------------------
# P15 - the deterministic fast path deliberates about nothing
# ---------------------------------------------------------------------


def test_p15_a_typed_folder_task_faces_no_decision_at_all():
    requirement = SemanticRequirement(
        requirement_id="req_1", kind="effect",
        description="Create folder KalpavrikshaAccept on the Desktop",
        provenance="founder said", founder_evidence="founder said",
    )

    frame = frame_for(
        objective="Create folder KalpavrikshaAccept on the Desktop",
        requirements=(requirement,), capability="Filesystem.CreateFolder",
    )

    # No frame means no deliberation, no provider call, no latency.
    assert frame is None
    assert next_evidence_need(None, progress()) is None


# ---------------------------------------------------------------------
# A rejected candidate still names what it could not establish
# ---------------------------------------------------------------------


def test_an_unverified_criterion_on_a_rejected_candidate_is_still_a_gap():
    rejected = RejectedCandidate(
        candidate_id="beta", summary="Beta", reason="pricing unknown",
        unverified=("crit_3",),
    )
    alpha = candidate("Alpha", **{key: MET for key in CRITERIA})

    need = next_evidence_need(
        result(candidates=(alpha,), shortlist=(alpha,), rejected=(rejected,)),
        progress(satisfied=(LANDSCAPE, TOP_THREE)))

    assert need is not None
    assert need.criterion_id == "crit_3"
    assert "beta" in need.candidate_ids


# ---------------------------------------------------------------------
# P10 / P11 / P12 - when the Founder should be asked, and when not
# ---------------------------------------------------------------------


def test_p10_two_equally_qualified_candidates_need_founder_judgement():
    """Both satisfy every stated requirement. Nothing further that can be
    OBSERVED separates them, so choosing between them is the Founder's
    tradeoff, not a gap more evidence can close."""
    met = {key: MET for key in CRITERIA}
    alpha, beta = candidate("Alpha", **met), candidate("Beta", **met)

    decision = DeliberationResult(
        state=DECIDED, shortlist=(alpha, beta), candidates=(alpha, beta),
        requirement_ids=ALL,
        # The threat call is the judgement the founder is still owed.
        decision_requirement_ids=(LANDSCAPE, TOP_THREE, THREAT),
        candidate_prerequisite_ids=(LANDSCAPE, TOP_THREE),
        criteria=dict(CRITERIA),
        criterion_requirements=dict(CRITERION_REQUIREMENTS),
    )
    need = next_evidence_need(
        decision,
        progress(satisfied=(LANDSCAPE, TOP_THREE, PRICING, BROWSER,
                            AUTONOMY, MEMORY, DIFFERENTIATORS)))

    assert need is not None
    assert need.action == "ask_founder"
    assert THREAT in need.target_requirements
    # The question is grounded in the actual tie, not "what do you want?"
    assert {"alpha", "beta"} <= set(need.candidate_ids)
    assert need.missing_claim
    assert "alpha" in need.missing_claim.casefold()
    assert "beta" in need.missing_claim.casefold()


def test_p10_a_single_qualified_candidate_is_not_a_founder_question():
    met = {key: MET for key in CRITERIA}
    alpha = candidate("Alpha", **met)

    need = next_evidence_need(
        DeliberationResult(
            state=DECIDED, shortlist=(alpha,), candidates=(alpha,),
            requirement_ids=ALL,
            candidate_prerequisite_ids=(LANDSCAPE, TOP_THREE),
            criteria=dict(CRITERIA),
            criterion_requirements=dict(CRITERION_REQUIREMENTS),
        ),
        progress(satisfied=(LANDSCAPE, TOP_THREE, PRICING, BROWSER,
                            AUTONOMY, MEMORY, DIFFERENTIATORS)))

    assert need.action == "finalize_from_canonical_decision"


def test_p11_an_exhausted_route_is_kalpavrikshas_problem_not_the_founders():
    """A dead source is a strategy problem. It must never become a
    question, because the Founder cannot answer it and did not cause it."""
    trio = (candidate("Alpha"), candidate("Beta"), candidate("Gamma"))

    need = next_evidence_need(
        result(candidates=trio, shortlist=trio),
        progress(satisfied=(LANDSCAPE, TOP_THREE),
                 failed=("Browser.ReadPageText:https://dead.example",)))

    assert need is not None
    assert need.action != "ask_founder"
    assert need.exhausted_strategies


def test_p11_missing_but_findable_evidence_is_not_a_founder_question():
    trio = (candidate("Alpha"), candidate("Beta"), candidate("Gamma"))

    need = next_evidence_need(
        result(candidates=trio, shortlist=trio),
        progress(satisfied=(LANDSCAPE, TOP_THREE)))

    assert need.action != "ask_founder"
    assert need.criterion_id  # a specific observable gap


def test_p12_the_brain_decision_carries_the_founder_objective_forward():
    """Whatever the Brain decides, the mission it is deciding about is
    still the Founder's -- not the latest fragment of it."""
    state = progress(satisfied=(LANDSCAPE,))

    assert state.objective == "frozen live objective"
    need = next_evidence_need(
        result(candidates=(candidate("Alpha"),)), state)

    assert need is not None
    assert need.target_requirements
    assert set(need.target_requirements) <= set(ALL)


def test_a_mission_whose_answer_is_a_set_does_not_ask_the_founder():
    """"Find three tools and save a report" owes a deliverable, not a
    judgement. Three qualifying candidates is the ANSWER, not a tie."""
    tools, report = "t_1", "t_2"
    criteria = {"crit_price": "pricing compared"}
    trio = tuple(
        Candidate(candidate_id=name, summary=name.title(),
                  criteria={"crit_price": MET})
        for name in ("alpha", "beta", "gamma")
    )

    need = next_evidence_need(
        DeliberationResult(
            state=DECIDED, shortlist=trio, candidates=trio,
            requirement_ids=(tools, report),
            # The set requirement is already satisfied; nothing is owed
            # but the artefact.
            decision_requirement_ids=(tools,),
            candidate_prerequisite_ids=(tools,),
            criteria=criteria,
            criterion_requirements={"crit_price": tools},
        ),
        MissionProgress(objective="three tools", satisfied=(tools,),
                        unresolved=(report,)))

    assert need is not None
    assert need.action == "finalize_from_canonical_decision"
    assert need.target_requirements == (report,)


def test_a_tie_with_an_unverified_criterion_is_evidence_not_judgement():
    """If anything observable is still unknown, that is a gap to close --
    asking the founder would be outsourcing Kalpavriksha's own work."""
    partial = {key: MET for key in CRITERIA}
    partial["crit_5"] = UNVERIFIED
    alpha, beta = candidate("Alpha", **partial), candidate("Beta", **partial)

    need = next_evidence_need(
        DeliberationResult(
            state=DECIDED, shortlist=(alpha, beta), candidates=(alpha, beta),
            requirement_ids=ALL,
            decision_requirement_ids=(LANDSCAPE, TOP_THREE, THREAT),
            candidate_prerequisite_ids=(LANDSCAPE, TOP_THREE),
            criteria=dict(CRITERIA),
            criterion_requirements=dict(CRITERION_REQUIREMENTS),
        ),
        progress(satisfied=(LANDSCAPE, TOP_THREE, PRICING, BROWSER,
                            MEMORY, DIFFERENTIATORS)))

    assert need is not None
    assert need.action != "ask_founder"


# ---------------------------------------------------------------------
# Microtrace - structured decision state, never chain-of-thought
# ---------------------------------------------------------------------


def test_the_brain_decision_is_inspectable_without_reasoning_transcripts():
    met = {key: MET for key in CRITERIA}
    alpha, beta = candidate("Alpha", **met), candidate("Beta", **met)
    tried = ("Browser.ReadPageText:https://dead.example",)

    need = next_evidence_need(
        DeliberationResult(
            state=DECIDED, shortlist=(alpha, beta), candidates=(alpha, beta),
            requirement_ids=ALL,
            decision_requirement_ids=(LANDSCAPE, TOP_THREE, THREAT),
            candidate_prerequisite_ids=(LANDSCAPE, TOP_THREE),
            criteria=dict(CRITERIA),
            criterion_requirements=dict(CRITERION_REQUIREMENTS),
        ),
        progress(satisfied=(LANDSCAPE, TOP_THREE, PRICING, BROWSER,
                            AUTONOMY, MEMORY, DIFFERENTIATORS),
                 failed=tried))

    trace = need.as_dict()

    # WHAT is being advanced, WHY, for WHICH subjects, and what is spent.
    for key in ("action", "reason", "target_requirements", "missing_claim",
                "candidate_ids", "exhausted_strategies"):
        assert key in trace, key
    assert trace["action"] == "ask_founder"
    assert trace["target_requirements"] == [THREAT]
    assert list(tried)[0] in trace["exhausted_strategies"]
    assert trace["reason"]

    # No transcript, no hidden deliberation -- product state only.
    flat = " ".join(str(v) for v in trace.values()).casefold()
    for banned in ("let me think", "step 1", "reasoning:", "chain of thought"):
        assert banned not in flat


def test_mission_progress_is_the_brain_input_record():
    state = progress(satisfied=(LANDSCAPE,), failed=("A:1",), succeeded=("B:2",))

    trace = state.as_dict()

    for key in ("objective", "satisfied", "unresolved", "failed_routes",
                "successful_routes", "evidence_ids"):
        assert key in trace, key
    assert trace["objective"] == "frozen live objective"
    assert LANDSCAPE in trace["satisfied"]
    assert TOP_THREE in trace["unresolved"]


# ---------------------------------------------------------------------
# Q1-Q6 - asking the Founder is the LAST resort, in a fixed order
# ---------------------------------------------------------------------


def _decided(shortlist, *, satisfied, criteria=None, decision_ids=None,
             failed=()):
    return next_evidence_need(
        DeliberationResult(
            state=DECIDED, shortlist=tuple(shortlist),
            candidates=tuple(shortlist),
            requirement_ids=ALL,
            decision_requirement_ids=tuple(
                decision_ids if decision_ids is not None
                else (LANDSCAPE, TOP_THREE, THREAT)),
            candidate_prerequisite_ids=(LANDSCAPE, TOP_THREE),
            criteria=dict(CRITERIA if criteria is None else criteria),
            criterion_requirements=dict(CRITERION_REQUIREMENTS),
        ),
        progress(satisfied=satisfied, failed=failed))


ALL_MET = {key: MET for key in CRITERIA}
EVERY_COMPARISON = (LANDSCAPE, TOP_THREE, PRICING, BROWSER, AUTONOMY,
                    MEMORY, DIFFERENTIATORS)


def test_q1_a_tie_with_missing_mandatory_evidence_acquires_evidence():
    """Order step 1. Evidence first: a gap is never a question.

    An unverified mandatory criterion means `shortlist` selects nobody,
    so production never reaches DECIDED here -- the mission is still
    INSUFFICIENT_EVIDENCE and the gap is what gets targeted.
    """
    partial = dict(ALL_MET, crit_5=UNVERIFIED)
    pair = (candidate("Alpha", **partial), candidate("Beta", **partial))
    need = next_evidence_need(
        result(candidates=pair),
        progress(satisfied=(LANDSCAPE, TOP_THREE, PRICING, BROWSER, MEMORY,
                            DIFFERENTIATORS)))

    assert need.action != "ask_founder"
    assert need.criterion_id == "crit_5"


def test_q2_an_exhausted_source_adapts_strategy_rather_than_asking():
    """Order step 2. A dead route is Kalpavriksha's to route around."""
    partial = dict(ALL_MET, crit_5=UNVERIFIED)
    pair = (candidate("Alpha", **partial), candidate("Beta", **partial))
    need = next_evidence_need(
        result(candidates=pair, shortlist=pair),
        progress(satisfied=(LANDSCAPE, TOP_THREE, PRICING, BROWSER, MEMORY,
                            DIFFERENTIATORS),
                 failed=("Browser.ReadPageText:https://dead.example",)))

    assert need.action != "ask_founder"
    assert "Browser.ReadPageText:https://dead.example" in need.exhausted_strategies


def test_q3_a_stated_founder_priority_decides_without_asking():
    """Order steps 3 and 4. A priority the Founder DID state is a
    criterion, so the existing shortlist applies it and one candidate is
    excluded -- there is no tie left to ask about."""
    criteria = dict(CRITERIA, crit_cost="the lower recurring cost option")
    requirements = dict(CRITERION_REQUIREMENTS, crit_cost=THREAT)
    cheap = Candidate(candidate_id="alpha", summary="Alpha",
                      criteria=dict(ALL_MET, crit_cost=MET))

    need = next_evidence_need(
        DeliberationResult(
            state=DECIDED, shortlist=(cheap,), candidates=(cheap,),
            rejected=(RejectedCandidate(
                candidate_id="beta", summary="Beta",
                reason="higher recurring cost", failed=("crit_cost",)),),
            requirement_ids=ALL,
            decision_requirement_ids=(LANDSCAPE, TOP_THREE, THREAT),
            candidate_prerequisite_ids=(LANDSCAPE, TOP_THREE),
            criteria=criteria, criterion_requirements=requirements,
        ),
        progress(satisfied=EVERY_COMPARISON))

    assert need.action == "finalize_from_canonical_decision"


def test_q4_an_irreducible_subjective_tradeoff_asks_the_founder():
    """Order step 5, and only step 5."""
    need = _decided(
        (candidate("Alpha", **ALL_MET), candidate("Beta", **ALL_MET)),
        satisfied=EVERY_COMPARISON)

    assert need.action == "ask_founder"
    assert set(need.candidate_ids) == {"alpha", "beta"}
    # The question names what has already been applied, so it is minimal
    # and grounded rather than "which one do you want?".
    claim = need.missing_claim.casefold()
    assert "every stated requirement" in claim
    assert "pricing" in claim
    assert "no further observation distinguishes them" in claim
    assert "judgement the objective does not contain" in claim
    assert need.reason


def test_q5_a_set_answer_mission_never_reaches_the_question():
    tools, report = "t_1", "t_2"
    trio = tuple(
        Candidate(candidate_id=name, summary=name.title(),
                  criteria={"crit_price": MET})
        for name in ("alpha", "beta", "gamma")
    )
    need = next_evidence_need(
        DeliberationResult(
            state=DECIDED, shortlist=trio, candidates=trio,
            requirement_ids=(tools, report),
            decision_requirement_ids=(tools,),
            candidate_prerequisite_ids=(tools,),
            criteria={"crit_price": "pricing compared"},
            criterion_requirements={"crit_price": tools},
        ),
        MissionProgress(objective="three tools", satisfied=(tools,),
                        unresolved=(report,)))

    assert need.action == "finalize_from_canonical_decision"


def test_q6_an_internal_failure_never_becomes_a_founder_question():
    """No provider fault, quota or malformed response reaches the Founder
    through this boundary -- there is no path from a route failure to
    ask_founder while any criterion is still open."""
    trio = (candidate("Alpha"), candidate("Beta"), candidate("Gamma"))
    need = next_evidence_need(
        result(candidates=trio, shortlist=trio),
        progress(satisfied=(LANDSCAPE, TOP_THREE),
                 failed=("Reasoning.Transform:quota-exhausted",
                         "Browser.Navigate:https://blocked.example")))

    assert need.action != "ask_founder"
    assert len(need.exhausted_strategies) == 2


# ---------------------------------------------------------------------
# What the Brain is given when a clarification happened
# ---------------------------------------------------------------------


def test_a_clarified_prose_objective_reaches_the_brain_whole():
    """The Brain reasons about the objective STRING. On the compound path
    -- the one a multi-requirement mission takes, and therefore the one
    that reaches deliberation -- the clarified goal carries the Founder's
    original request AND the answer they gave, not the answer alone."""
    from master_agent.brain.intent import IntentLayer

    request = ("Create Finance on my Desktop, then write the summary into "
               "it and tell me when done")
    layer = IntentLayer()

    asked = layer.parse(request)
    assert asked.needs_clarification is True

    answered = layer.parse(request, supplied={asked.clarification.key: "folder"})
    goal = answered.intent.goal

    # ORIGINAL REQUEST, verbatim, is what the Brain deliberates about.
    assert request in goal
    # ...and the Founder's answer travels with it rather than replacing it.
    assert "folder" in goal.casefold()
    assert answered.intent.context["raw_input"] == request

    # And that goal is what a DecisionFrame is built from.
    frame = frame_for(
        objective=goal,
        requirements=(
            SemanticRequirement(
                requirement_id="req_1", kind="effect",
                description="create the named folder", provenance=request,
                founder_evidence=request),
            SemanticRequirement(
                requirement_id="req_2", kind="deliverable",
                description="write the summary into it", provenance=request,
                founder_evidence=request),
        ),
    )
    if frame is not None:
        assert request in frame.objective
