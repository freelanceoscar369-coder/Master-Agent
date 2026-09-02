"""Stage 1: a provider proposes requirements; IntentLayer admits meaning.

The invariant is semantic state, not a requirement count and not the word
``and``.  A prerequisite and the judgement that consumes it must remain
independently representable; one inseparable outcome must not be fragmented
because execution could use several capabilities.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from master_agent.brain.intent import (
    IntentLayer,
    _audit_structure_issues,
    _coverage_decision,
    requirement_structure_issues,
)
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

CAPTURED_PRIMARY = (
    "Research the current AI-agent products most relevant to Kalpavriksha.\n"
    "Compare the top 3 across pricing/free access, computer/browser use,\n"
    "autonomous task execution, persistence/memory and major differentiators.\n"
    "Use sufficient public evidence, tell me which poses the closest competitive\n"
    "threat and why, and save a verified competitive brief as\n"
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

CAPTURED_LIVE_NINE = [
    row(
        "information",
        "Identify the top 3 AI-agent products most relevant to Kalpavriksha.",
        "Research the current AI-agent products most relevant to Kalpavriksha.",
        success=(
            "A set of 3 AI-agent products most relevant to Kalpavriksha is "
            "identified."
        ),
    ),
    row(
        "information",
        "Evaluate the pricing and free access options of each candidate product.",
        "Compare the top 3 across pricing/free access, computer/browser use, "
        "autonomous task execution, persistence/memory and major differentiators.",
        True,
        success=(
            "Pricing structure and free access availability are determined for "
            "each candidate product."
        ),
    ),
    row(
        "information",
        "Evaluate the computer and browser use capabilities of each candidate product.",
        "Compare the top 3 across pricing/free access, computer/browser use, "
        "autonomous task execution, persistence/memory and major differentiators.",
        True,
        success=(
            "Computer and browser interaction capabilities are determined for "
            "each candidate product."
        ),
    ),
    row(
        "information",
        "Evaluate the autonomous task execution capabilities of each candidate product.",
        "Compare the top 3 across pricing/free access, computer/browser use, "
        "autonomous task execution, persistence/memory and major differentiators.",
        True,
        success=(
            "Autonomous task execution capabilities are determined for each "
            "candidate product."
        ),
    ),
    row(
        "information",
        "Evaluate the persistence and memory capabilities of each candidate product.",
        "Compare the top 3 across pricing/free access, computer/browser use, "
        "autonomous task execution, persistence/memory and major differentiators.",
        True,
        success=(
            "Persistence and memory capabilities are determined for each "
            "candidate product."
        ),
    ),
    row(
        "information",
        "Identify the major differentiators of each candidate product.",
        "Compare the top 3 across pricing/free access, computer/browser use, "
        "autonomous task execution, persistence/memory and major differentiators.",
        True,
        success=(
            "Key unique differentiators are identified for each candidate product."
        ),
    ),
    row(
        "constraint",
        "The research and comparative findings must be substantiated by public "
        "evidence.",
        "Use sufficient public evidence",
        success=(
            "All statements and comparisons made regarding the products are "
            "backed by verifiable public evidence."
        ),
    ),
    row(
        "information",
        "Identify which candidate product represents the closest competitive "
        "threat to Kalpavriksha and explain the reasons why.",
        "tell me which poses the closest competitive threat and why",
        success=(
            "The product representing the closest competitive threat is "
            "explicitly named along with an explanatory justification."
        ),
    ),
    row(
        "deliverable",
        "Save a verified competitive brief as a Markdown file named "
        "Kalpavriksha_Competitive_Brief.md on the Desktop.",
        "save a verified competitive brief as Kalpavriksha_Competitive_Brief.md "
        "on my Desktop.",
        success=(
            "A file named Kalpavriksha_Competitive_Brief.md containing the "
            "verified competitive brief exists on the user's Desktop."
        ),
    ),
]


#: Stage 1C establishes the Founder obligation set upstream, blind to the
#: decomposition. These cases are about the REQUIREMENT boundary below it,
#: so they need a trusted obligation set to exist -- exactly as production
#: does. The anchors are taken from the review document the case already
#: supplies, so every assertion below still tests the same anchor set it
#: always did; nothing here weakens what Stage 1B is asked to prove.
STAGE_1C_REQUESTERS = (
    "brain_founder_obligations",
    "brain_founder_obligation_audit",
    "brain_founder_obligation_correction",
)


def _anchors_from(documents):
    # The TRUE obligation set: production establishes it once, upstream,
    # and carries it across a requirement correction. The richest review
    # document names it, because a merge review must name both obligations
    # it found collapsed.
    best = []
    for document in documents:
        if isinstance(document, dict) and isinstance(
            document.get("anchors"), list
        ):
            if len(document["anchors"]) > len(best):
                best = document["anchors"]
    if best:
        return best
    for document in documents:
        if isinstance(document, dict) and isinstance(
            document.get("anchors"), list
        ):
            return document["anchors"]
    return []


def _regions_in(prompt):
    import re

    return sorted({int(found) for found in re.findall(
        r'"region_index":\s*(\d+)', prompt)})


def _span(text):
    return " ".join(str(text or "").casefold().split())


def _match(quote, by_quote):
    """Resolve a source span to a trusted anchor id.

    Exact first, then punctuation-insensitive, then containment either
    way: two fixtures may quote the same Founder obligation with or
    without its trailing full stop.
    """
    if not quote:
        return ""
    if quote in by_quote:
        return by_quote[quote]
    trimmed = quote.strip(" .,;:")
    for candidate, anchor_id in by_quote.items():
        if candidate.strip(" .,;:") == trimmed:
            return anchor_id
    for candidate, anchor_id in by_quote.items():
        if trimmed and (trimmed in candidate or candidate in trimmed):
            return anchor_id
    return ""


def _retargeted(document, trusted):
    """Point a review's coverage at the trusted anchors, by source quote.

    Production settles one obligation set upstream and reuses it across a
    requirement correction. These fixtures were written when each review
    round carried its own anchors; retargeting keeps every coverage SHAPE
    the case asserts while making the ids refer to the one trusted set.
    """
    if not isinstance(document, dict) or not isinstance(
        document.get("coverage"), list
    ):
        return document
    trusted_ids = {
        str(anchor.get("anchor_id", "") or "")
        for anchor in trusted if isinstance(anchor, dict)
    }
    if trusted_ids and all(
        str(row.get("anchor_id", "") or "") in trusted_ids
        for row in document["coverage"] if isinstance(row, dict)
    ):
        # Already expressed in the trusted vocabulary; remapping such a
        # document could only damage it.
        return {**document, "anchors": list(trusted)}
    own = {
        str(anchor.get("anchor_id", "") or ""): _span(anchor.get("source_quote"))
        for anchor in document.get("anchors", ()) or ()
        if isinstance(anchor, dict)
    }
    by_quote = {}
    for anchor in trusted:
        if isinstance(anchor, dict):
            by_quote.setdefault(
                _span(anchor.get("source_quote")),
                str(anchor.get("anchor_id", "") or ""),
            )
    merged: dict[str, dict] = {}
    order: list[str] = []
    for row in document["coverage"]:
        if not isinstance(row, dict):
            continue
        anchor_id = str(row.get("anchor_id", "") or "")
        # Always resolve through the source quote. An id that merely
        # LOOKS familiar can name a different obligation in the trusted
        # set -- "anchor_3" means different things in the two schemes.
        if own:
            anchor_id = _match(own.get(anchor_id, ""), by_quote) or anchor_id
        existing = merged.get(anchor_id)
        if existing is None:
            merged[anchor_id] = {**row, "anchor_id": anchor_id}
            order.append(anchor_id)
            continue
        # One obligation legitimately exposed by several more precise
        # requirements: union the indices rather than emit a second row.
        indices = list(existing.get("requirement_indices") or ())
        for index in row.get("requirement_indices") or ():
            if index not in indices:
                indices.append(index)
        existing["requirement_indices"] = indices
        existing["independently_trackable"] = bool(
            existing.get("independently_trackable")
        ) and bool(row.get("independently_trackable"))
    return {
        **document,
        "anchors": list(trusted),
        "coverage": [merged[key] for key in order],
    }


class Scripted:
    def __init__(self, *documents, anchors=None):
        self.documents = list(documents)
        self.trusted = list(anchors) if anchors is not None else None
        self.prompts = []
        self.requesters = []
        self.stage_1c_prompts = []

    def _obligation_document(self, requester, prompt):
        anchors = (
            self.trusted if self.trusted is not None
            else _anchors_from(self.documents)
        )
        if requester in ("brain_founder_obligations",
                         "brain_founder_obligation_correction"):
            return {"anchors": anchors}
        first = ""
        if anchors and isinstance(anchors[0], dict):
            first = str(anchors[0].get("anchor_id", "") or "")
        return {
            "regions": [
                {"region_index": index,
                 "disposition": "represented_by_anchor",
                 "anchor_id": first}
                for index in _regions_in(prompt)
            ],
            "anchors": [
                {"anchor_id": str(anchor.get("anchor_id", "") or ""),
                 "entailed": True}
                for anchor in anchors if isinstance(anchor, dict)
            ],
            "omissions": [], "collapses": [], "invented": [], "valid": True,
        }

    def run(self, prompt, request=None):
        requester = getattr(request, "requester", "")
        if requester in STAGE_1C_REQUESTERS:
            self.stage_1c_prompts.append(prompt)
            return SimpleNamespace(
                ok=True,
                text=json.dumps(self._obligation_document(requester, prompt)),
            )
        self.prompts.append(prompt)
        self.requesters.append(requester)
        position = min(len(self.prompts) - 1, len(self.documents) - 1)
        document = self.documents[position]
        if requester == "brain_semantic_requirement_validation":
            document = _retargeted(document, (
                self.trusted if self.trusted is not None
                else _anchors_from(self.documents)
            ))
        return SimpleNamespace(ok=True, text=json.dumps(document))


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
        "anchors": [
            {
                "anchor_id": f"anchor_{index}",
                "source_quote": item["source_quote"],
                "meaning": item["success_meaning"],
                "depends_on": [],
            }
            for index, item in enumerate(rows, start=1)
        ],
        "coverage": [
            {
                "anchor_id": f"anchor_{index}",
                "requirement_indices": [index],
                "independently_trackable": True,
            }
            for index, _item in enumerate(rows, start=1)
        ],
        "invented": [],
    }


def merged_audit(rows, index, *obligations):
    anchors = []
    coverage = []
    for position, item in enumerate(rows, start=1):
        if position == index:
            for offset, (quote, meaning) in enumerate(obligations, start=1):
                anchor_id = f"anchor_{position}_{offset}"
                anchors.append({
                    "anchor_id": anchor_id,
                    "source_quote": quote,
                    "meaning": meaning,
                    "depends_on": [],
                })
                coverage.append({
                    "anchor_id": anchor_id,
                    "requirement_indices": [position],
                    "independently_trackable": True,
                })
            continue
        anchor_id = f"anchor_{position}"
        anchors.append({
            "anchor_id": anchor_id,
            "source_quote": item["source_quote"],
            "meaning": item["success_meaning"],
            "depends_on": [],
        })
        coverage.append({
            "anchor_id": anchor_id,
            "requirement_indices": [position],
            "independently_trackable": True,
        })
    return {
        # Deliberately false-positive: deterministic coverage, not this
        # self-certification, must reject the many-anchors-to-one-state merge.
        "valid": True,
        "independently_verifiable": True,
        "anchors": anchors,
        "coverage": coverage,
        "invented": [],
    }


def captured_landscape_selection_false_positive():
    anchors = [
        {
            "anchor_id": "landscape",
            "source_quote": (
                "Research the current AI-agent products most relevant to "
                "Kalpavriksha."
            ),
            "meaning": "establish the current relevant product landscape",
            "depends_on": [],
        },
        {
            "anchor_id": "selection",
            "source_quote": "top 3",
            "meaning": "establish the selected top-three comparison set",
            "depends_on": ["landscape"],
        },
    ]
    coverage = [
        {
            "anchor_id": "landscape",
            "requirement_indices": [1],
            "independently_trackable": True,
        },
        {
            "anchor_id": "selection",
            "requirement_indices": [1],
            "independently_trackable": True,
        },
    ]
    for index, item in enumerate(CAPTURED_LIVE_NINE[1:], start=2):
        anchor_id = f"anchor_{index}"
        anchors.append({
            "anchor_id": anchor_id,
            "source_quote": item["source_quote"],
            "meaning": item["success_meaning"],
            "depends_on": ["selection"] if item["candidate_property"] else [],
        })
        coverage.append({
            "anchor_id": anchor_id,
            "requirement_indices": [index],
            "independently_trackable": True,
        })
    return {
        # This is the live failure's decisive condition. It must have no
        # authority over the deterministic many-anchors-to-one-state check.
        "valid": True,
        "independently_verifiable": True,
        "anchors": anchors,
        "coverage": coverage,
        "invented": [],
    }


def derive(objective, reasoner):
    canonical = intent(objective)
    requirements = layer(reasoner).requirements_for(canonical, raw=objective)
    return canonical, requirements


def test_captured_live_nine_row_valid_true_is_deterministically_rejected():
    audit = captured_landscape_selection_false_positive()

    assert requirement_structure_issues(CAPTURED_PRIMARY, CAPTURED_LIVE_NINE) == []
    assert _audit_structure_issues(
        CAPTURED_PRIMARY, CAPTURED_LIVE_NINE, audit,
    ) == []
    decision = _coverage_decision(CAPTURED_LIVE_NINE, audit)

    assert audit["valid"] is True, "replay must retain the false certification"
    assert decision["valid"] is False
    assert decision["merged"]
    assert decision["merged"][0]["requirement_index"] == 1
    assert {
        anchor["anchor_id"] for anchor in decision["merged"][0]["obligations"]
    } == {"landscape", "selection"}


def test_exact_captured_global_review_cannot_self_certify_without_anchors():
    captured_review = {
        "valid": True,
        "independently_verifiable": True,
        "preserved": [
            {
                "requirement_index": index,
                "source_quote": item["source_quote"],
            }
            for index, item in enumerate(CAPTURED_LIVE_NINE, start=1)
        ],
        "merged": [],
        "lost": [],
        "invented": [],
    }

    issues = _audit_structure_issues(
        CAPTURED_PRIMARY, CAPTURED_LIVE_NINE, captured_review,
    )
    assert any("'anchors'" in issue for issue in issues)
    assert any("'coverage'" in issue for issue in issues)

    # Replay the retained legacy decomposition and reviewer response through
    # the production admission path.  The old global self-certification must
    # stop before canonical SemanticRequirements are constructed.
    # Stage 1C settles the obligation set upstream. This case is about
    # what happens to a LEGACY review that carries no anchors at all, so
    # the trusted set is supplied here exactly as production would have
    # produced it -- otherwise the run refuses before ever reaching the
    # review boundary this case exists to test.
    reasoner = Scripted(
        {"requirements": CAPTURED_LIVE_NINE},
        captured_review,
        anchors=[
            {"anchor_id": f"anchor_{index}",
             "source_quote": item["source_quote"],
             "meaning": item["success_meaning"], "depends_on": []}
            for index, item in enumerate(CAPTURED_LIVE_NINE, start=1)
        ],
    )
    canonical, requirements = derive(CAPTURED_PRIMARY, reasoner)
    admission = canonical.context["requirement_admission"]

    assert requirements == ()
    assert admission["valid"] is False
    assert admission["semantic_verdict"] == "semantic_review_unusable"
    assert admission["final_provider_output"] == CAPTURED_LIVE_NINE
    assert reasoner.requesters == [
        "brain_semantic_requirements",
        "brain_semantic_requirement_validation",
    ]


def test_captured_live_merge_triggers_one_correction_and_admits_losslessly():
    # The TRUE obligation set for this objective, settled upstream by
    # Stage 1C before either decomposition existed. The captured live
    # decomposition is then measured against it, exactly as production
    # measures one.
    reasoner = Scripted(
        {"requirements": CAPTURED_LIVE_NINE},
        captured_landscape_selection_false_positive(),
        {"requirements": PRIMARY_ATOMIC},
        {
            "valid": True,
            "independently_verifiable": True,
            "coverage": [
                {"anchor_id": anchor["anchor_id"],
                 "requirement_indices": [index],
                 "independently_trackable": True}
                for index, anchor in enumerate(
                    captured_landscape_selection_false_positive()["anchors"],
                    start=1,
                )
            ],
            "invented": [],
        },
        anchors=captured_landscape_selection_false_positive()["anchors"],
    )

    canonical, requirements = derive(CAPTURED_PRIMARY, reasoner)
    admission = canonical.context["requirement_admission"]

    assert admission["valid"] is True
    assert admission["semantic_verdict"] == "valid_after_correction"
    assert admission["correction_attempted"] is True
    assert admission["detected_merged_obligations"]
    assert admission["unmapped_anchors"] == []
    assert admission["improper_merges"] == []
    assert admission["invented_requirements"] == []
    assert len(admission["founder_obligation_anchors"]) == len(requirements)
    assert "current relevant product landscape" in reasoner.prompts[2]
    assert "selected top-three comparison set" in reasoner.prompts[2]


def test_primary_merged_selection_and_pricing_is_corrected_without_count_hardcoding():
    reasoner = Scripted(
        {"requirements": PRIMARY_MERGED},
        merged_audit(PRIMARY_MERGED,
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
        merged_audit(merged,
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
        merged_audit(merged,
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


def test_qualified_supplier_set_is_independent_from_best_supplier_selection():
    objective = "Identify qualified suppliers and choose the best supplier."
    merged = [row("information", "Identify and choose the best supplier", objective)]
    atomic = [
        row("information", "Establish the qualified supplier set",
            "Identify qualified suppliers"),
        row("information", "Choose the best supplier from the qualified set",
            "choose the best supplier"),
    ]
    reasoner = Scripted(
        {"requirements": merged},
        merged_audit(
            merged, 1,
            ("Identify qualified suppliers", "establish qualification state"),
            ("choose the best supplier", "select from the qualified set"),
        ),
        {"requirements": atomic},
        valid_audit(atomic),
    )

    _, requirements = derive(objective, reasoner)

    assert [requirement.description for requirement in requirements] == [
        "Establish the qualified supplier set",
        "Choose the best supplier from the qualified set",
    ]


def test_supplier_selection_is_independent_from_emailing_the_selection():
    objective = "Choose a supplier and email the selected supplier."
    merged = [row("effect", "Choose and email a supplier", objective)]
    atomic = [
        row("information", "Choose the supplier", "Choose a supplier"),
        row("effect", "Email the selected supplier", "email the selected supplier"),
    ]
    reasoner = Scripted(
        {"requirements": merged},
        merged_audit(
            merged, 1,
            ("Choose a supplier", "establish the selected supplier"),
            ("email the selected supplier", "perform the external action"),
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
        merged_audit(merged,
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
        merged_audit(merged,
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


def test_game_eligibility_demo_availability_and_verified_link_are_three_states():
    objective = (
        "Find action RPGs released in 2026 with free demos and give me verified "
        "download links."
    )
    merged = [row("information", "Find games with verified demo links", objective)]
    atomic = [
        row("information", "Establish eligible action RPGs released in 2026",
            "action RPGs released in 2026"),
        row("information", "Establish free-demo availability for eligible games",
            "free demos", True),
        row("information", "Provide verified demo download links",
            "verified download links", True),
    ]
    reasoner = Scripted(
        {"requirements": merged},
        merged_audit(
            merged, 1,
            ("action RPGs released in 2026", "establish candidate eligibility"),
            ("free demos", "establish demo availability"),
            ("verified download links", "establish verified link state"),
        ),
        {"requirements": atomic},
        valid_audit(atomic),
    )

    _, requirements = derive(objective, reasoner)

    assert len(requirements) == 3
    assert [requirement.candidate_property for requirement in requirements] == [
        False, True, True,
    ]


def test_an_invented_requirement_is_corrected_even_with_a_grounded_quote():
    objective = "Create a launch checklist and save it as launch.md."
    wanted = row("deliverable", "Create and save launch.md", objective)
    invented = row(
        "effect", "Email the checklist to the launch team",
        "Create a launch checklist",
    )
    initial = [wanted, invented]
    invalid = {
        "valid": True,
        "independently_verifiable": True,
        "anchors": [{
            "anchor_id": "anchor_1",
            "source_quote": objective,
            "meaning": wanted["success_meaning"],
            "depends_on": [],
        }],
        "coverage": [{
            "anchor_id": "anchor_1",
            "requirement_indices": [1],
            "independently_trackable": True,
        }],
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
    invalid = merged_audit(merged,
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
    semantic_evidence = trace["output"]["semantic_admission_evidence"]
    assert semantic_evidence["founder_obligation_anchors"] == 2
    assert semantic_evidence["canonical_requirements"] == 0
    assert semantic_evidence["improper_merges"]
    assert semantic_evidence["invented_requirements"] == []
    assert semantic_evidence["correction_attempted"] is True
    assert semantic_evidence["final_admission"] == (
        "invalid_semantics_after_correction"
    )


def test_structural_gate_has_no_subject_vocabulary_or_conjunction_splitter():
    import inspect

    source = "\n".join((
        inspect.getsource(requirement_structure_issues),
        inspect.getsource(_audit_structure_issues),
        inspect.getsource(_coverage_decision),
    )).casefold()
    for domain_word in ("hotel", "supplier", "pricing", "folder", "investor"):
        assert domain_word not in source
    assert ".split(\" and \"" not in source
