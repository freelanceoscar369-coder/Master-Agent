"""Surgical proofs for adaptive pursuit inside the existing owners.

These are deliberately domain-neutral.  They exercise the contracts that
failed live without encoding an acceptance objective, product name, site or
artifact filename in production.
"""
from __future__ import annotations

from types import SimpleNamespace

from master_agent.brain.conformance import SATISFIED, UNKNOWN, assess
from master_agent.brain.deliberation import (
    INSUFFICIENT_EVIDENCE,
    UNVERIFIED,
    Candidate,
    DeliberationResult,
    MissionProgress,
    next_evidence_need,
    no_useful_progress,
)
from master_agent.planner.catalogue import CapabilityOption
from master_agent.planner.parsing import validate
from master_agent.planner.plan import (
    DELIVERABLE,
    INFORMATION,
    Intent,
    SemanticRequirement,
    strategy_coverage,
)


def requirement(
    requirement_id: str,
    description: str,
    *,
    candidate_property: bool,
    kind: str = INFORMATION,
) -> SemanticRequirement:
    return SemanticRequirement(
        requirement_id=requirement_id,
        kind=kind,
        description=description,
        founder_evidence=description,
        candidate_property=candidate_property,
    )


def success(description: str = "the observation is returned") -> dict:
    return {
        "description": description,
        "must_contain": [],
        "must_exclude": [],
        "must_be_json": False,
        "must_have_fields": [],
        "min_words": 0,
    }


def observe_step(url: str, covers: tuple[str, ...] = ("req_2",)) -> dict:
    return {
        "id": "observe",
        "capability": "Research.Observe",
        "covers": list(covers),
        "payload": {"url": url},
        "input_bindings": {},
        "depends_on": [],
        "success": success(),
    }


OPTIONS = (
    CapabilityOption(name="Research.Observe", required_args=("url",), output_fields=("text",)),
)


def test_probe_a_partial_continuation_keeps_untargeted_requirements_unresolved():
    from master_agent.planner.prompting import build_prompt

    requirements = (
        requirement("req_1", "establish criterion one", candidate_property=True),
        requirement("req_2", "establish criterion two", candidate_property=True),
        requirement("req_3", "produce the final report", candidate_property=False,
                    kind=DELIVERABLE),
    )
    intent = Intent(
        goal="evaluate the options and report",
        requirements=requirements,
        context={
            "decision_frame": {"requirement_ids": ["req_1", "req_2", "req_3"]},
            "recovery": {"satisfied": [], "unresolved": ["req_1", "req_2", "req_3"]},
            "evidence_needed": {
                "target_requirements": ["req_2"],
                "missing_claim": "establish criterion two",
            },
        },
    )

    targets, forbidden = strategy_coverage(intent)
    plan, refusal = validate(
        {"steps": [observe_step("https://second.invalid/fact")]},
        OPTIONS,
        objective=intent.goal,
        requirements=requirements,
        required_coverage=targets,
        forbidden_coverage=forbidden,
    )

    assert refusal is None and plan is not None
    assert targets == ("req_2",)
    assert tuple(r.requirement_id for r in plan.requirements) == (
        "req_1", "req_2", "req_3",
    )
    outcome = assess(requirements, [SimpleNamespace(
        task_id="observe", covers=("req_2",),
        evidence={"verdict": "matched"},
    )])
    states = {row.requirement_id: row.state for row in outcome.requirements}
    assert states == {"req_1": UNKNOWN, "req_2": SATISFIED, "req_3": UNKNOWN}
    prompt = build_prompt(intent, OPTIONS)
    assert "req_2: establish criterion two [CURRENT STRATEGY TARGET]" in prompt
    assert "req_1: establish criterion one [MISSION-OWNED, NOT TARGETED" in prompt
    assert "req_3: produce the final report [MISSION-OWNED, NOT TARGETED" in prompt


def test_probe_b_insufficient_source_selects_one_need_and_requires_new_route():
    candidate = Candidate(
        candidate_id="atlas",
        summary="Atlas",
        criteria={"crit_2": UNVERIFIED},
    )
    decision = DeliberationResult(
        state=INSUFFICIENT_EVIDENCE,
        candidates=(candidate,),
        criteria={"crit_2": "establish criterion two"},
        criterion_requirements={"crit_2": "req_2"},
        more_research=True,
    )
    before = MissionProgress(
        unresolved=("req_2", "req_3"),
        observation_signatures=("same-observation",),
        successful_routes=("Research.Observe https://first.invalid/fact",),
    )

    need = next_evidence_need(decision, before)

    assert need is not None
    assert need.target_requirements == ("req_2",)
    assert need.candidate_ids == ("atlas",)
    assert need.missing_claim == "establish criterion two"

    repeated, refusal = validate(
        {"steps": [observe_step("https://first.invalid/fact")]},
        OPTIONS,
        requirements=(requirement("req_2", "criterion two", candidate_property=True),),
        required_coverage=("req_2",),
        exhausted_routes=need.exhausted_strategies,
    )
    assert repeated is None
    assert refusal is not None
    assert "exhausted strategy" in refusal.reason

    changed, refusal = validate(
        {"steps": [observe_step("https://second.invalid/fact")]},
        OPTIONS,
        requirements=(requirement("req_2", "criterion two", candidate_property=True),),
        required_coverage=("req_2",),
        exhausted_routes=need.exhausted_strategies,
    )
    assert refusal is None and changed is not None
    after = MissionProgress(
        unresolved=before.unresolved,
        observation_signatures=("same-observation", "new-observation"),
        successful_routes=before.successful_routes
        + ("Research.Observe https://second.invalid/fact",),
    )
    assert not no_useful_progress(before, after)


def test_probe_c_unverified_candidate_claim_prevents_satisfied_conformance():
    requirements = (
        requirement("req_1", "compare criterion one", candidate_property=True),
    )
    tasks = [SimpleNamespace(
        task_id="observed", covers=("req_1",),
        evidence={"verdict": "matched"},
    )]
    decision = DeliberationResult(
        state=INSUFFICIENT_EVIDENCE,
        candidates=(Candidate(
            candidate_id="atlas", summary="Atlas",
            criteria={"crit_1": UNVERIFIED}, criterion_evidence={},
        ),),
        criteria={"crit_1": "compare criterion one"},
        criterion_requirements={"crit_1": "req_1"},
        more_research=True,
    )

    outcome = assess(requirements, tasks, deliberation=decision)

    assert outcome.state == UNKNOWN
    assert outcome.requirements[0].state == UNKNOWN
    assert "canonical Evidence" in outcome.requirements[0].reason


def test_probe_d_unpublished_cross_step_field_is_rejected_before_execution():
    options = (
        CapabilityOption(name="Research.Observe", output_fields=("text",)),
        CapabilityOption(name="Reasoning.Transform", required_args=("instruction",),
                         optional_args=("context",), output_fields=("text",)),
    )
    document = {"steps": [
        {
            "id": "producer", "capability": "Research.Observe",
            "covers": ["req_1"], "payload": {}, "depends_on": [],
            "success": success(),
        },
        {
            "id": "consumer", "capability": "Reasoning.Transform",
            "covers": ["req_1"], "payload": {"instruction": "summarise"},
            "input_bindings": {
                "context": {"from_step": {"step_id": "producer", "field": "answer"}},
            },
            "depends_on": ["producer"], "success": success(),
        },
    ]}

    plan, refusal = validate(
        document, options,
        requirements=(requirement("req_1", "produce a summary", candidate_property=True),),
        required_coverage=("req_1",),
    )

    assert plan is None
    assert refusal is not None
    assert refusal.reason == "a step binds to an output field that is not published"


def test_probe_e_provider_exhaustion_falls_back_without_mutating_mission_state():
    from tests.test_reasoning_fallback_ladder import (
        FakeProvider,
        _build_system,
        _failure,
        _request,
        _success,
    )

    first = FakeProvider("gemini.api", [_failure("gemini.api", "quota exhausted")])
    second = FakeProvider("openrouter.api", [_success("openrouter.api")])
    runner = _build_system(gemini=first, browser=second)
    mission_state = MissionProgress(
        objective="compare the options",
        satisfied=("req_1",), unresolved=("req_2",),
        evidence_ids=("ev-1",), observation_signatures=("fact-1",),
    )

    outcome = runner.run("continue the same objective", _request())

    assert outcome.ok and outcome.provider_id == "openrouter.api"
    assert first.complete_calls == 1 and second.complete_calls == 1
    assert mission_state == MissionProgress(
        objective="compare the options",
        satisfied=("req_1",), unresolved=("req_2",),
        evidence_ids=("ev-1",), observation_signatures=("fact-1",),
    )


def test_canonical_synthesis_binds_candidate_state_and_observed_urls_to_write():
    from master_agent.planner.planner import _canonical_synthesis_document

    decision = {
        "state": "decided",
        "shortlist": [{"candidate_id": "atlas", "summary": "Atlas"}],
        "candidates": [{
            "candidate_id": "atlas", "summary": "Atlas",
            "criteria": {"crit_1": "met"},
            "criterion_claims": {"crit_1": "the observed capability is present"},
            "criterion_evidence": {"crit_1": ["ev-1"]},
        }],
        "evidence_provenance": {
            "ev-1": {"url": "https://source.invalid/atlas", "source_class": "primary"},
        },
    }
    intent = Intent(
        goal="write the result",
        context={"canonical_decision": decision},
    )
    document = {"steps": [
        {
            "id": "synth", "capability": "Reasoning.Transform",
            "covers": ["req_2"],
            "payload": {"instruction": "produce the report", "sensitive": False},
            "input_bindings": {}, "depends_on": [], "success": success(),
        },
        {
            "id": "write", "capability": "Document.WriteDocument",
            "covers": ["req_2"], "payload": {"path": "report.md"},
            "input_bindings": {
                "content": {"from_step": {"step_id": "synth", "field": "text"}},
            },
            "depends_on": ["synth"], "success": success("the report is written"),
        },
    ]}

    bound, refusal = _canonical_synthesis_document(document, intent)

    assert refusal is None
    transform = bound["steps"][0]
    assert '"candidate_id":"atlas"' in transform["payload"]["context"]
    assert "Atlas" in transform["payload"]["must_contain"]
    assert "https://source.invalid/atlas" in transform["payload"]["must_contain"]
    assert "independently select candidates" in transform["payload"]["instruction"]
