"""Stage 1: a provider proposes requirements; IntentLayer admits meaning.

The invariant is semantic state, not a requirement count and not the word
``and``.  A prerequisite and the judgement that consumes it must remain
independently representable; one inseparable outcome must not be fragmented
because execution could use several capabilities.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from master_agent.brain.intent import IntentLayer, requirement_structure_issues
from master_agent.missions.service import MissionService
from master_agent.planner.plan import UNSETTLED_INTERPRETATION, Intent

PRIMARY = (
    "Research the current AI-agent products most relevant to Kalpavriksha. "
    "Compare the top 3 across pricing/free access, computer/browser use, "
    "autonomous task execution, persistence/memory and major differentiators. "
    "Use sufficient public evidence, tell me which poses the closest competitive "
    "threat and why, and save a verified competitive brief as "
    "Kalpavriksha_Competitive_Brief.md on my Desktop."
)


def row(kind, description, quote, candidate=False, success=None):
    return {
        "kind": kind,
        "description": description,
        "candidate_property": candidate,
        "source_quote": quote,
        "success_meaning": success or description,
    }


PRIMARY_ATOMIC = [
    row("information", "Establish relevant current AI-agent products",
        "Research the current AI-agent products most relevant to Kalpavriksha"),
    row("information", "Establish the selected top-three candidate set", "top 3",
        success="Exactly three qualified candidates form the canonical set"),
    row("information", "Compare pricing and free access", "pricing/free access", True),
    row("information", "Compare computer and browser use", "computer/browser use", True),
    row("information", "Compare autonomous task execution",
        "autonomous task execution", True),
    row("information", "Compare persistence and memory", "persistence/memory", True),
    row("information", "Compare major differentiators", "major differentiators", True),
    row("constraint", "Use sufficient public Evidence", "sufficient public evidence"),
    row("information", "Decide the closest competitive threat with rationale",
        "which poses the closest competitive threat and why"),
    row("deliverable", "Save and verify the named Desktop brief",
        "save a verified competitive brief as Kalpavriksha_Competitive_Brief.md on my Desktop",
        success="The named Desktop brief exists and independent readback matches"),
]

PRIMARY_MERGED = [
    PRIMARY_ATOMIC[0],
    row("information", "Select the top three and compare pricing/free access",
        "top 3 across pricing/free access", True,
        "The top three are selected and their pricing/free access is compared"),
    *PRIMARY_ATOMIC[3:],
]


class Scripted:
    def __init__(self, *documents):
        self.documents = list(documents)
        self.prompts = []
        self.requesters = []

    def run(self, prompt, request=None):
        self.prompts.append(prompt)
        self.requesters.append(getattr(request, "requester", ""))
        position = min(len(self.prompts) - 1, len(self.documents) - 1)
        return SimpleNamespace(ok=True, text=json.dumps(self.documents[position]))


def layer(reasoner):
    result = IntentLayer.__new__(IntentLayer)
    result._reasoner = reasoner
    return result


def intent(objective):
    return Intent(goal=objective, context={"raw_input": objective})


def valid_audit(rows):
    return {
        "valid": True,
        "independently_verifiable": True,
        "preserved": [
            {"requirement_index": index, "source_quote": item["source_quote"]}
            for index, item in enumerate(rows, start=1)
        ],
        "merged": [],
        "lost": [],
        "invented": [],
    }


def merged_audit(index, *obligations):
    return {
        "valid": False,
        "independently_verifiable": False,
        "preserved": [],
        "merged": [{
            "requirement_index": index,
            "obligations": [
                {"source_quote": quote, "meaning": meaning}
                for quote, meaning in obligations
            ],
            "reason": "one state can be established before the other",
        }],
        "lost": [],
        "invented": [],
    }


def derive(objective, reasoner):
    canonical = intent(objective)
    requirements = layer(reasoner).requirements_for(canonical, raw=objective)
    return canonical, requirements


def test_primary_merged_selection_and_pricing_is_corrected_without_count_hardcoding():
    reasoner = Scripted(
        {"requirements": PRIMARY_MERGED},
        merged_audit(
            2,
            ("top 3", "establish the selected candidate set"),
            ("pricing/free access", "compare a property of that set"),
        ),
        {"requirements": PRIMARY_ATOMIC},
        valid_audit(PRIMARY_ATOMIC),
    )

    canonical, requirements = derive(PRIMARY, reasoner)

    descriptions = [requirement.description.casefold() for requirement in requirements]
    selection = [text for text in descriptions if "top-three candidate set" in text]
    pricing = [text for text in descriptions if "pricing and free access" in text]
    assert selection and pricing and selection[0] != pricing[0]
    assert all(not ("top-three" in text and "pricing" in text) for text in descriptions)
    admission = canonical.context["requirement_admission"]
    assert admission["valid"] is True
    assert admission["semantic_verdict"] == "valid_after_correction"
    assert admission["correction_attempted"] is True
    assert admission["lost_obligations"] == []
    assert admission["invented_obligations"] == []
    assert admission["detected_merged_obligations"]
    assert "independent Founder obligations were merged" in reasoner.prompts[2]
    assert "top 3" in reasoner.prompts[2]
    assert "pricing/free access" in reasoner.prompts[2]


def test_find_three_tools_keeps_candidate_set_independent_from_two_comparisons():
    objective = "Find three project-management tools and compare pricing and offline use."
    merged = [row(
        "information", "Find three tools and compare pricing and offline use",
        "Find three project-management tools and compare pricing and offline use",
        True,
    )]
    atomic = [
        row("information", "Establish three project-management tools",
            "Find three project-management tools"),
        row("information", "Compare pricing", "pricing", True),
        row("information", "Compare offline use", "offline use", True),
    ]
    reasoner = Scripted(
        {"requirements": merged},
        merged_audit(
            1,
            ("Find three project-management tools", "establish candidate set"),
            ("pricing", "compare pricing"),
            ("offline use", "compare offline capability"),
        ),
        {"requirements": atomic},
        valid_audit(atomic),
    )

    _, requirements = derive(objective, reasoner)

    assert [requirement.candidate_property for requirement in requirements] == [
        False, True, True,
    ]


def test_selection_and_external_action_are_independently_stateful():
    objective = "Find the best suitable supplier and send them the purchase request."
    merged = [row("effect", "Choose and contact the best supplier", objective)]
    atomic = [
        row("information", "Establish the best suitable supplier",
            "Find the best suitable supplier"),
        row("effect", "Send the selected supplier the purchase request",
            "send them the purchase request"),
    ]
    reasoner = Scripted(
        {"requirements": merged},
        merged_audit(
            1,
            ("Find the best suitable supplier", "selection"),
            ("send them the purchase request", "external action"),
        ),
        {"requirements": atomic},
        valid_audit(atomic),
    )

    _, requirements = derive(objective, reasoner)

    assert [requirement.kind for requirement in requirements] == [
        "information", "effect",
    ]


def test_eligibility_state_is_separate_from_top_five_ranking():
    objective = "Identify eligible investors and rank the top five by fit."
    merged = [row("information", "Identify and rank the investors", objective, True)]
    atomic = [
        row("information", "Establish eligible investors", "Identify eligible investors"),
        row("information", "Rank the top five eligible investors by fit",
            "rank the top five by fit", True),
    ]
    reasoner = Scripted(
        {"requirements": merged},
        merged_audit(
            1,
            ("Identify eligible investors", "eligibility state"),
            ("rank the top five by fit", "ranking over eligible set"),
        ),
        {"requirements": atomic},
        valid_audit(atomic),
    )

    _, requirements = derive(objective, reasoner)

    assert requirements[0].candidate_property is False
    assert requirements[1].candidate_property is True


def test_research_eligibility_and_verified_demo_availability_are_separate():
    objective = "Research action RPGs released in 2026 and give verified demo links."
    merged = [row("information", "Find games and provide their demos", objective, True)]
    atomic = [
        row("information", "Establish action RPGs released in 2026",
            "Research action RPGs released in 2026"),
        row("information", "Provide verified demo links", "verified demo links", True),
    ]
    reasoner = Scripted(
        {"requirements": merged},
        merged_audit(
            1,
            ("Research action RPGs released in 2026", "eligibility state"),
            ("verified demo links", "verified availability for eligible games"),
        ),
        {"requirements": atomic},
        valid_audit(atomic),
    )

    _, requirements = derive(objective, reasoner)

    assert requirements[0].candidate_property is False
    assert requirements[1].candidate_property is True


def test_an_invented_requirement_is_corrected_even_with_a_grounded_quote():
    objective = "Create a launch checklist and save it as launch.md."
    wanted = row("deliverable", "Create and save launch.md", objective)
    invented = row(
        "effect", "Email the checklist to the launch team",
        "Create a launch checklist",
    )
    initial = [wanted, invented]
    invalid = {
        "valid": False,
        "independently_verifiable": True,
        "preserved": [{"requirement_index": 1, "source_quote": objective}],
        "merged": [],
        "lost": [],
        "invented": [{
            "requirement_index": 2,
            "reason": "the Founder did not ask to email anybody",
        }],
    }
    corrected = [wanted]
    reasoner = Scripted(
        {"requirements": initial}, invalid,
        {"requirements": corrected}, valid_audit(corrected),
    )

    canonical, requirements = derive(objective, reasoner)

    assert [requirement.description for requirement in requirements] == [
        "Create and save launch.md",
    ]
    assert canonical.context["requirement_admission"]["invented_obligations"] == []
    assert canonical.context["requirement_admission"][
        "detected_invented_obligations"
    ]
    assert "unstated obligation was invented" in reasoner.prompts[2]


def test_an_ungrounded_source_quote_fails_before_semantic_review():
    objective = "Create a launch checklist."
    invalid = [row("effect", "Email the team", "email the team")]
    corrected = [row("deliverable", "Create a launch checklist", objective)]
    reasoner = Scripted(
        {"requirements": invalid},
        {"requirements": corrected},
        valid_audit(corrected),
    )

    canonical, requirements = derive(objective, reasoner)

    assert requirements
    assert canonical.context["requirement_admission"]["valid"] is True
    assert reasoner.requesters == [
        "brain_semantic_requirements",
        "brain_semantic_requirements_correction",
        "brain_semantic_requirement_validation",
    ]


def test_save_and_verify_one_artifact_is_not_split():
    objective = "Save a verified report to Desktop."
    offered = [row(
        "deliverable", "Save and verify the Desktop report", objective,
        success="The saved Desktop report matches independent readback",
    )]
    _, requirements = derive(
        objective, Scripted({"requirements": offered}, valid_audit(offered)),
    )

    assert [requirement.description for requirement in requirements] == [
        "Save and verify the Desktop report",
    ]


def test_execution_capability_count_does_not_fragment_one_deliverable():
    objective = "Think of three names and save them to names.txt."
    offered = [row(
        "deliverable", "Save three generated names to names.txt", objective,
        success="names.txt contains exactly three generated names",
    )]
    reasoner = Scripted({"requirements": offered}, valid_audit(offered))

    _, requirements = derive(objective, reasoner)

    assert len(requirements) == 1
    assert len(reasoner.prompts) == 2


def test_word_and_does_not_force_research_suitability_into_two_rows():
    objective = "Research X and tell me whether it is suitable."
    offered = [row(
        "information", "Give an evidence-backed suitability answer", objective,
        success="The Founder receives a supported suitability conclusion",
    )]

    _, requirements = derive(
        objective, Scripted({"requirements": offered}, valid_audit(offered)),
    )

    assert len(requirements) == 1


def test_typed_folder_fast_path_makes_no_reasoning_call():
    reasoner = Scripted({"requirements": []})
    canonical = Intent(
        goal="Create a folder called X on Desktop.",
        capability="create_folder",
        payload={"name": "X", "location": "desktop"},
        context={"raw_input": "Create a folder called X on Desktop."},
    )

    requirements = layer(reasoner).requirements_for(canonical, raw=canonical.goal)

    assert requirements
    assert reasoner.prompts == []
    assert canonical.context["requirement_admission"]["semantic_verdict"] == (
        "valid_deterministic"
    )


def test_question_with_rationale_remains_one_information_outcome():
    reasoner = Scripted({"requirements": []})
    canonical = Intent(
        goal="Tell me whether the mission succeeded and why.",
        answers_founder="text",
        context={"raw_input": "Tell me whether the mission succeeded and why."},
    )

    requirements = layer(reasoner).requirements_for(canonical, raw=canonical.goal)

    assert len(requirements) == 1
    assert reasoner.prompts == []


def test_two_invalid_semantic_answers_refuse_before_brain_or_planner():
    objective = "Find three hotels and compare their cancellation policies."
    merged = [row("information", "Find and compare three hotels", objective, True)]
    invalid = merged_audit(
        1,
        ("Find three hotels", "establish hotel set"),
        ("compare their cancellation policies", "compare that set"),
    )
    reasoner = Scripted(
        {"requirements": merged}, invalid,
        {"requirements": merged}, invalid,
    )
    brain = layer(reasoner)

    class PlannerThatMustNotRun:
        called = False

        def plan(self, *_args, **_kwargs):
            self.called = True
            raise AssertionError("Planner received semantically invalid Intent")

    planner = PlannerThatMustNotRun()
    service = MissionService(
        planner=planner,
        mission_control=SimpleNamespace(),
        intent_layer=brain,
    )

    outcome = service.start(intent(objective))

    assert outcome.refusal.code == UNSETTLED_INTERPRETATION
    assert planner.called is False
    assert len(reasoner.prompts) == 4
    trace = outcome.micro_trace[0]
    assert trace["stage"] == "FOUNDER_INPUT_TO_INTENT"
    assert trace["output_valid"] is False
    assert trace["next_consumer_accepted"] is False
    assert trace["semantic_drift"] is True
    assert trace["information_lost"], "merged obligations must be visible"
    assert trace["output"]["semantic_admission"]["valid"] is False


def test_structural_gate_has_no_subject_vocabulary_or_conjunction_splitter():
    import inspect

    source = inspect.getsource(requirement_structure_issues).casefold()
    for domain_word in ("hotel", "supplier", "pricing", "folder", "investor"):
        assert domain_word not in source
    assert "split(" not in source
