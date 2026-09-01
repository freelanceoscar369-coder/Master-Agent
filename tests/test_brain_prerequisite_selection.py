"""The Brain selects actionable state gaps, not merely unresolved rows.

These proofs start with the exact requirement shape exposed by the failed
Primary live probe, then exercise the same contract with domain-neutral
candidate states.  No provider, browser or alternate planning owner is
involved.
"""
from __future__ import annotations

from master_agent.brain.conformance import SATISFIED, UNKNOWN, assess
from master_agent.brain.deliberation import (
    DECIDED,
    INSUFFICIENT_EVIDENCE,
    MET,
    UNVERIFIED,
    Candidate,
    DeliberationResult,
    MissionProgress,
    frame_for,
    initial_evidence_need,
    next_evidence_need,
)
from master_agent.missions.service import MissionService
from master_agent.planner.catalogue import CapabilityOption
from master_agent.planner.plan import (
    CONSTRAINT,
    DELIVERABLE,
    INFORMATION,
    Intent,
    PlanOutcome,
    PlanRefusal,
    SemanticRequirement,
    strategy_coverage,
)
from master_agent.planner.prompting import build_prompt

PRIMARY_OBJECTIVE = (
    "Research the current AI-agent products most relevant to Kalpavriksha. "
    "Compare the top 3 across pricing/free access, computer/browser use, "
    "autonomous task execution, persistence/memory and major differentiators. "
    "Use sufficient public evidence, tell me which poses the closest "
    "competitive threat and why, and save a verified competitive brief as "
    "Kalpavriksha_Competitive_Brief.md on my Desktop."
)


def requirement(
    requirement_id: str,
    description: str,
    *,
    candidate_property: bool,
    kind: str = INFORMATION,
) -> SemanticRequirement:
    return SemanticRequirement(
        requirement_id,
        kind,
        description,
        founder_evidence=description,
        candidate_property=candidate_property,
    )


PRIMARY_REQUIREMENTS = (
    requirement("req_1", "Research current AI-agent products most relevant to Kalpavriksha",
                candidate_property=False),
    requirement("req_2", "Compare the top 3 products", candidate_property=False),
    requirement("req_3", "Compare pricing and free access", candidate_property=True),
    requirement("req_4", "Compare computer and browser use", candidate_property=True),
    requirement("req_5", "Compare autonomous task execution", candidate_property=True),
    requirement("req_6", "Compare persistence and memory", candidate_property=True),
    requirement("req_7", "Compare major differentiators", candidate_property=True),
    requirement("req_8", "Use sufficient public evidence", candidate_property=False,
                kind=CONSTRAINT),
    requirement("req_9", "Tell which product poses the closest competitive threat and why",
                candidate_property=False),
    requirement("req_10", "Save a verified competitive brief on Desktop",
                candidate_property=False, kind=DELIVERABLE),
)


def primary_frame():
    frame = frame_for(objective=PRIMARY_OBJECTIVE, requirements=PRIMARY_REQUIREMENTS)
    assert frame is not None
    return frame


def result_with(candidates, *, state=INSUFFICIENT_EVIDENCE, shortlist=()):
    frame = primary_frame()
    return DeliberationResult(
        state=state,
        shortlist=tuple(shortlist),
        candidates=tuple(candidates),
        requirement_ids=frame.requirement_ids,
        decision_requirement_ids=frame.decision_requirement_ids,
        candidate_prerequisite_ids=frame.candidate_prerequisite_ids,
        criteria={criterion.criterion_id: criterion.description
                  for criterion in frame.mandatory},
        criterion_requirements={criterion.criterion_id: criterion.requirement_id
                                for criterion in frame.mandatory},
        more_research=state != DECIDED,
    )


def progress(*, unresolved=None, successful=()) -> MissionProgress:
    return MissionProgress(
        objective=PRIMARY_OBJECTIVE,
        unresolved=tuple(unresolved or (r.requirement_id for r in PRIMARY_REQUIREMENTS)),
        successful_routes=tuple(successful),
    )


def test_exact_primary_intent_is_semantically_complete_and_ordered():
    assert [r.requirement_id for r in PRIMARY_REQUIREMENTS] == [
        f"req_{index}" for index in range(1, 11)
    ]
    joined = " | ".join(r.description.lower() for r in PRIMARY_REQUIREMENTS)
    for meaning in (
        "current ai-agent products", "top 3", "pricing", "computer",
        "autonomous", "persistence", "differentiators", "public evidence",
        "closest competitive threat", "verified competitive brief",
    ):
        assert meaning in joined


def test_no_candidates_means_discovery_before_comparison():
    frame = primary_frame()

    need = initial_evidence_need(frame, PRIMARY_REQUIREMENTS)

    assert frame.candidate_prerequisite_ids == ("req_1", "req_2")
    assert need is not None
    assert need.action == "discover_candidates"
    assert need.target_requirements == ("req_1",)
    assert not need.candidate_ids
    assert "no canonical candidate state" in need.reason


def test_discovered_candidates_move_the_brain_to_canonical_set_qualification():
    candidates = tuple(
        Candidate(
            candidate_id=f"candidate-{index}",
            summary=f"Candidate {index}",
            criteria={"crit_1": UNVERIFIED},
        )
        for index in range(1, 9)
    )

    need = next_evidence_need(result_with(candidates), progress())

    assert need is not None
    assert need.action == "qualify_candidates"
    assert need.target_requirements == ("req_2",)
    assert len(need.candidate_ids) == 8


def test_canonical_three_select_one_high_value_missing_criterion():
    candidates = tuple(
        Candidate(
            candidate_id=f"candidate-{index}",
            summary=f"Candidate {index}",
            criteria={
                "crit_1": UNVERIFIED,
                "crit_2": MET,
                "crit_3": UNVERIFIED,
            },
        )
        for index in range(1, 4)
    )

    need = next_evidence_need(
        result_with(candidates, shortlist=candidates), progress()
    )

    assert need is not None
    assert need.target_requirements == ("req_3",)
    assert need.criterion_id == "crit_1"
    assert len(need.candidate_ids) == 3


def test_exhausted_candidate_source_is_visible_to_the_next_decision():
    candidate = Candidate(
        candidate_id="candidate-a",
        summary="Candidate A",
        criteria={"crit_1": UNVERIFIED},
    )
    route = "Research.Observe https://source.invalid/pricing-a"

    need = next_evidence_need(
        result_with((candidate,), shortlist=(candidate,)),
        progress(successful=(route,)),
    )

    assert need is not None
    assert route in need.exhausted_strategies


def test_settled_candidate_evidence_moves_to_canonical_finalization():
    candidate = Candidate(
        candidate_id="candidate-a",
        summary="Candidate A",
        criteria={f"crit_{index}": MET for index in range(1, 6)},
    )
    decided = result_with((candidate,), state=DECIDED, shortlist=(candidate,))

    need = next_evidence_need(
        decided,
        progress(unresolved=("req_9", "req_10")),
    )

    assert need is not None
    assert need.action == "finalize_from_canonical_decision"
    assert need.target_requirements == ("req_9", "req_10")


def test_candidate_observation_can_settle_discovery_before_final_decision():
    candidate = Candidate(
        candidate_id="candidate-a",
        summary="Candidate A",
        criteria={"crit_1": UNVERIFIED},
    )
    decision = result_with((candidate,))
    task = type("Task", (), {
        "task_id": "discover",
        "covers": ("req_1",),
        "evidence": {"verdict": "matched", "evidence_id": "ev-discover"},
    })()

    outcome = assess(PRIMARY_REQUIREMENTS, (task,), deliberation=decision)
    states = {row.requirement_id: row.state for row in outcome.requirements}

    assert states["req_1"] == SATISFIED
    assert states["req_2"] == UNKNOWN
    assert states["req_3"] == UNKNOWN


class PlannerSpy:
    def __init__(self):
        self.intent = None

    def plan(self, intent, **_kwargs):
        self.intent = intent
        return PlanOutcome(refusal=PlanRefusal("stop", "stop after capture"))


def test_mission_service_gives_the_planner_the_brain_selected_first_need():
    planner = PlannerSpy()
    service = MissionService(
        planner=planner,
        mission_control=None,
        intent_layer=object(),
    )
    intent = Intent(
        goal=PRIMARY_OBJECTIVE,
        context={"raw_input": PRIMARY_OBJECTIVE},
        requirements=PRIMARY_REQUIREMENTS,
    )

    service.start(intent)

    assert planner.intent is intent
    need = intent.context["evidence_needed"]
    assert need["action"] == "discover_candidates"
    assert need["target_requirements"] == ["req_1"]
    targets, forbidden = strategy_coverage(intent)
    assert targets == ("req_1",)
    assert forbidden == tuple(f"req_{index}" for index in range(2, 11))


def test_brain_output_reaches_the_planner_prompt_without_semantic_drift():
    frame = primary_frame()
    need = initial_evidence_need(frame, PRIMARY_REQUIREMENTS)
    intent = Intent(
        goal=PRIMARY_OBJECTIVE,
        context={
            "raw_input": PRIMARY_OBJECTIVE,
            "decision_frame": frame.as_dict(),
            "evidence_needed": need.as_dict(),
        },
        requirements=PRIMARY_REQUIREMENTS,
    )

    prompt = build_prompt(intent, (CapabilityOption(name="Research.Observe"),))

    assert f"Objective: {PRIMARY_OBJECTIVE}" in prompt
    assert "req_1: Research current AI-agent products" in prompt
    assert "[CURRENT STRATEGY TARGET]" in prompt
    for requirement in PRIMARY_REQUIREMENTS[1:]:
        assert requirement.requirement_id in prompt
        assert "MISSION-OWNED, NOT TARGETED" in prompt
    assert need.missing_claim in prompt
    assert "Plan ONLY what is needed to settle it" in prompt
