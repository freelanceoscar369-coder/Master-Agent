"""Planner translation varies in punctuation, never in semantics.

The corpus exercises the production normaliser, parser, semantic admission,
correction prompt and Brain/MissionProgress contracts without contacting a
provider.  Its examples are intentionally domain-neutral.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from master_agent.brain.deliberation import (
    DECIDED,
    INSUFFICIENT_EVIDENCE,
    MET,
    UNVERIFIED,
    Candidate,
    DeliberationResult,
    MissionProgress,
    next_evidence_need,
    progress_of,
)
from master_agent.planner.catalogue import CapabilityOption
from master_agent.planner.parsing import validate
from master_agent.planner.plan import (
    DELIVERABLE,
    INFORMATION,
    Intent,
    SemanticRequirement,
)
from master_agent.planner.planner import Planner
from tests.planner_test_support import StubRunner

OBSERVE = CapabilityOption(
    name="Research.Observe",
    required_args=("url",),
    args_complete=True,
    output_fields=("text", "url"),
)
TRANSFORM = CapabilityOption(
    name="Reasoning.Transform",
    required_args=("instruction",),
    optional_args=("context",),
    args_complete=True,
    output_fields=("text",),
)
OPTIONS = (OBSERVE, TRANSFORM)

REQ_FACT = SemanticRequirement(
    "req_fact", INFORMATION, "establish the missing fact",
    founder_evidence="compare the options",
    candidate_property=True,
)
REQ_RESULT = SemanticRequirement(
    "req_result", DELIVERABLE, "produce the final result",
    founder_evidence="produce the result",
    candidate_property=False,
)
REQUIREMENTS = (REQ_FACT, REQ_RESULT)


def success() -> dict:
    return {"description": "the source observation is returned"}


def observation_step(
    url: str = "https://source.invalid/one",
    *,
    covers: object = ("req_fact",),
) -> dict:
    return {
        "id": "observe",
        "capability": OBSERVE.name,
        "covers": list(covers) if isinstance(covers, tuple) else covers,
        "payload": {"url": url},
        "input_bindings": {},
        "depends_on": [],
        "founder_checkpoint": "",
        "answers_founder": "",
        "success": success(),
    }


def admit(document, *, required=("req_fact",), forbidden=("req_result",)):
    return validate(
        document,
        OPTIONS,
        requirements=REQUIREMENTS,
        required_coverage=required,
        forbidden_coverage=forbidden,
    )


@pytest.mark.parametrize(
    "document",
    [
        {"steps": [observation_step()]},
        [observation_step()],
        {"steps": observation_step()},
        {"plan": {"steps": [observation_step()]}},
        {"mission_plan": {"steps": observation_step()}},
        observation_step(),
        {"steps": [{
            "success": success(),
            "depends_on": [],
            "payload": {"url": "https://source.invalid/one"},
            "covers": "req_fact",
            "capability": OBSERVE.name,
            "id": "observe",
        }]},
        {"steps": [{
            "id": "observe",
            "capability": OBSERVE.name,
            "covers": "req_fact",
            "payload": {"url": "https://source.invalid/one"},
            "success": success(),
        }]},
    ],
)
def test_semantically_equivalent_plan_shapes_are_admitted(document):
    plan, refusal = admit(document)

    assert refusal is None
    assert plan is not None
    assert plan.steps[0].covers == ("req_fact",)


def test_ambiguous_wrapper_is_not_normalised_by_guessing():
    document = {
        "plan": {"steps": [observation_step()]},
        "comment": "choose the plan field",
    }

    plan, refusal = admit(document)

    assert plan is None
    assert refusal is not None
    assert refusal.detail == "`steps` is missing or is not a list"


def test_unknown_capability_is_still_rejected():
    document = {"steps": [{
        **observation_step(),
        "capability": "Research.Invented",
    }]}

    plan, refusal = admit(document)

    assert plan is None
    assert "does not exist" in refusal.reason


def test_invented_requirement_is_still_rejected():
    document = {"steps": [{
        **observation_step(),
        "covers": ["req_invented"],
    }]}

    plan, refusal = admit(document)

    assert plan is None
    assert "unknown Founder requirement" in refusal.reason


def test_impossible_output_binding_is_still_rejected():
    document = {"steps": [
        observation_step(),
        {
            "id": "synthesise",
            "capability": TRANSFORM.name,
            "covers": ["req_fact"],
            "payload": {"instruction": "summarise the observation"},
            "input_bindings": {
                "context": {
                    "from_step": {"step_id": "observe", "field": "answer"},
                },
            },
            "depends_on": ["observe"],
            "success": {"description": "a summary is returned"},
        },
    ]}

    plan, refusal = admit(document)

    assert plan is None
    assert "output field that is not published" in refusal.reason


def test_missing_strategy_target_is_still_rejected():
    document = {"steps": [{
        **observation_step(),
        "covers": ["req_result"],
    }]}

    plan, refusal = admit(document)

    assert plan is None
    assert "req_fact" in refusal.detail


def test_already_satisfied_or_untargeted_replay_is_still_rejected():
    document = {"steps": [{
        **observation_step(),
        "covers": ["req_fact", "req_result"],
    }]}

    plan, refusal = admit(document)

    assert plan is None
    assert "untargeted or already-satisfied" in refusal.reason


def planner_for(reply: object) -> Planner:
    runner = StubRunner(json.dumps(reply))
    planner = Planner.__new__(Planner)
    planner._runner = runner
    planner._offline = False
    planner._requires_strong_reasoning = False
    planner._requester = "test"
    planner.options = lambda: OPTIONS
    planner.mode = lambda: "both"
    return planner


def continuation_intent(need: dict) -> Intent:
    return Intent(
        goal="compare the options and produce the result",
        requirements=REQUIREMENTS,
        context={
            "decision_frame": {
                "requirement_ids": ["req_fact", "req_result"],
            },
            "recovery": {
                "satisfied": [],
                "unresolved": ["req_fact", "req_result"],
            },
            "evidence_needed": need,
        },
    )


def test_production_planner_admits_a_normalised_brain_selected_subset():
    need = {
        "target_requirements": ["req_fact"],
        "missing_claim": "establish the missing fact",
        "exhausted_strategies": [],
    }
    wrapped_single_step = {"result": {"steps": observation_step()}}

    outcome = planner_for(wrapped_single_step).plan(continuation_intent(need))

    assert outcome.refusal is None
    assert outcome.plan is not None
    assert outcome.plan.steps[0].covers == ("req_fact",)
    assert tuple(r.requirement_id for r in outcome.plan.requirements) == (
        "req_fact", "req_result",
    )


def task(task_id: str, url: str, evidence_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        task_id=task_id,
        capability=OBSERVE.name,
        payload={"url": url},
        covers=("req_fact",),
        evidence={
            "evidence_id": evidence_id,
            "verdict": "matched",
            "observation": {"url": url, "text": evidence_id},
        },
    )


def test_adaptive_loop_uses_two_admitted_strategies_and_changes_requirement_state():
    candidate = Candidate(
        candidate_id="atlas",
        summary="Atlas",
        criteria={"crit_fact": UNVERIFIED},
    )
    unresolved_decision = DeliberationResult(
        state=INSUFFICIENT_EVIDENCE,
        candidates=(candidate,),
        rejected=(),
        criteria={"crit_fact": "establish the missing fact"},
        criterion_requirements={"crit_fact": "req_fact"},
        more_research=True,
    )
    initial = MissionProgress(
        objective="compare the options and produce the result",
        unresolved=("req_fact", "req_result"),
    )

    first_need = next_evidence_need(unresolved_decision, initial)
    assert first_need is not None
    first_document = {"steps": observation_step("https://source.invalid/one")}
    first = planner_for(first_document).plan(
        continuation_intent(first_need.as_dict())
    )
    assert first.plan is not None

    first_task = task("observe-one", "https://source.invalid/one", "ev-one")
    after_first = progress_of(
        initial.objective,
        REQUIREMENTS,
        (first_task,),
        deliberation=unresolved_decision,
    )
    second_need = next_evidence_need(unresolved_decision, after_first)
    assert second_need is not None
    assert "Research.Observe https://source.invalid/one" in (
        second_need.exhausted_strategies
    )

    second_document = {
        "plan": {
            "steps": observation_step("https://source.invalid/two"),
        },
    }
    second = planner_for(second_document).plan(
        continuation_intent(second_need.as_dict())
    )
    assert second.plan is not None
    assert second.plan.steps[0].payload["url"] == "https://source.invalid/two"

    second_task = task("observe-two", "https://source.invalid/two", "ev-two")
    supported_candidate = Candidate(
        candidate_id="atlas",
        summary="Atlas",
        criteria={"crit_fact": MET},
        criterion_evidence={"crit_fact": ("ev-two",)},
        criterion_claims={"crit_fact": "the second source establishes the fact"},
    )
    decided = DeliberationResult(
        state=DECIDED,
        shortlist=(supported_candidate,),
        candidates=(supported_candidate,),
        criteria={"crit_fact": "establish the missing fact"},
        criterion_requirements={"crit_fact": "req_fact"},
    )
    after_second = progress_of(
        initial.objective,
        REQUIREMENTS,
        (first_task, second_task),
        deliberation=decided,
    )

    assert after_first.unresolved == ("req_fact", "req_result")
    assert after_second.satisfied == ("req_fact",)
    assert after_second.unresolved == ("req_result",)
    final_need = next_evidence_need(decided, after_second)
    assert final_need is not None
    assert final_need.action == "finalize_from_canonical_decision"
    assert final_need.target_requirements == ("req_result",)
