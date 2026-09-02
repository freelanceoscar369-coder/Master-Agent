"""Gate A: statefulness is a property, not a type label.

Live Founder->Intent Probe #3 (2026-09-02, 1ff9e33) ended
UNSETTLED_INTERPRETATION. The mechanism caught the Probe #2 fusion on the
first round, the bounded correction separated the top-three selection and
all five comparison dimensions -- and then the second audit refused
``anchor_8``, which held

    c8  "Use sufficient public evidence"   placed constraint_unit
    c9  the threat decision + why          placed independent_outcome

Two things were wrong at once:

    1. a constraint was assumed to be a property of whatever it sat
       beside, so the PLACEMENTS showed only one trackable state and the
       refusal rested entirely on the auditor's own flag; and
    2. because the first round could not see that same pair fused inside
       anchor_3, the one bounded correction was spent on a partial
       repair and the second defect had no budget left.

Evidence sufficiency can be UNMET while a recommendation already exists,
so it is its own state. These tests replay the VERBATIM captured payloads
from tests/fixtures/probe3_*.json.
"""
from __future__ import annotations

import json
import pathlib

from master_agent.brain.intent import (
    _intra_anchor_fusion,
    _obligation_trust_decision,
    _source_state_candidates,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

FOUNDER_INPUT = (
    "Research the current AI-agent products most relevant to Kalpavriksha.\n"
    "Compare the top 3 across pricing/free access, computer/browser use,\n"
    "autonomous task execution, persistence/memory and major differentiators.\n"
    "Use sufficient public evidence, tell me which poses the closest competitive\n"
    "threat and why, and save a verified competitive brief as\n"
    "Kalpavriksha_Competitive_Brief.md on my Desktop."
)


def captured(name):
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


CANDIDATES = _source_state_candidates(FOUNDER_INPUT)
REGIONS = [row["text"] for row in CANDIDATES]


def decide(anchors, audit):
    return _obligation_trust_decision(
        [""] * 0 or _regions(), anchors, audit, CANDIDATES,
    )


def _regions():
    from master_agent.brain.intent import _source_coverage_regions

    return list(_source_coverage_regions(FOUNDER_INPUT))


# ---------------------------------------------------------------------
# The live c8 / c9 pair
# ---------------------------------------------------------------------


def test_the_live_evidence_constraint_is_its_own_trackable_state():
    """A recommendation can exist while the evidence behind it is still
    insufficient, so the two cannot share one satisfaction state."""
    anchors = captured("probe3_corrected_anchors")["anchors"]
    audit = captured("probe3_audit_2")

    placements = {
        row["candidate_index"]: row for row in audit["state_candidates"]
    }
    assert placements[8]["relationship"] == "constraint_unit"
    assert placements[9]["relationship"] == "independent_outcome"
    assert placements[8]["anchor_id"] == placements[9]["anchor_id"] == "anchor_8"

    fused = _intra_anchor_fusion(CANDIDATES, anchors, audit)

    # Structurally proven now, from the placements themselves.
    assert [row["anchor_id"] for row in fused] == ["anchor_8"]
    held = {state["candidate_index"] for state in fused[0]["states"]}
    assert held == {8, 9}


def test_the_first_round_already_shows_both_fusions():
    """Gate A4: one correction must be able to repair everything the
    evidence proves, so every fusion is collected before correcting."""
    anchors = captured("probe3_initial_anchors")["anchors"]
    audit = captured("probe3_audit_1")

    fused = _intra_anchor_fusion(CANDIDATES, anchors, audit)
    by_id = {row["anchor_id"]: row for row in fused}

    # anchor_2 fused the selection with the five comparison dimensions;
    # anchor_3 fused the evidence constraint with the threat decision. The
    # live run only ever saw the first of these.
    assert set(by_id) == {"anchor_2", "anchor_3"}
    assert len(by_id["anchor_2"]["states"]) == 6
    assert {s["candidate_index"] for s in by_id["anchor_3"]["states"]} == {8, 9}


def test_the_correction_request_names_every_proven_fusion():
    anchors = captured("probe3_initial_anchors")["anchors"]
    audit = captured("probe3_audit_1")

    decision = _obligation_trust_decision(
        _regions(), anchors, audit, CANDIDATES,
    )

    assert decision["trusted"] is False
    named = " | ".join(decision["issues"])
    assert "anchor_2" in named and "anchor_3" in named
    for wanted in ("pricing/free access", "computer/browser use",
                   "autonomous task execution", "persistence/memory",
                   "Use sufficient public evidence"):
        assert wanted in named, wanted


# ---------------------------------------------------------------------
# Global auditor flags are supporting evidence, never authority
# ---------------------------------------------------------------------


def test_a_declared_multiple_over_one_trackable_state_does_not_veto():
    """The mirror image of valid=true: an unsupported declaration is an
    opinion, and opinions do not decide admission."""
    anchors = [{"anchor_id": "a1", "source_quote": "Save and verify report.md",
                "meaning": "report.md exists and readback matches",
                "depends_on": []}]
    candidates = _source_state_candidates("Save and verify report.md")
    audit = {
        "regions": [{"region_index": 1,
                     "disposition": "represented_by_anchor",
                     "anchor_id": "a1"}],
        "anchors": [{"anchor_id": "a1", "entailed": True,
                     "contains_multiple_states": True}],
        "state_candidates": [
            {"candidate_index": 1, "relationship": "independent_outcome",
             "anchor_id": "a1"},
        ],
        "collapses": [{"anchor_id": "a1", "reason": "looks like two verbs"}],
        "omissions": [], "invented": [], "valid": True,
    }

    decision = _obligation_trust_decision(
        [c["text"] for c in candidates], anchors, audit, candidates,
    )

    assert _intra_anchor_fusion(candidates, anchors, audit) == []
    assert decision["trusted"] is True, decision["issues"]


def test_placements_prove_fusion_even_when_the_auditor_denies_it():
    anchors = [{"anchor_id": "a1", "source_quote": "Find the top three suppliers",
                "meaning": "suppliers found and priced", "depends_on": []}]
    objective = "Find the top three suppliers and compare their prices."
    candidates = _source_state_candidates(objective)
    audit = {
        "regions": [
            {"region_index": index, "disposition": "represented_by_anchor",
             "anchor_id": "a1"}
            for index in range(1, len(candidates) + 1)
        ],
        "anchors": [{"anchor_id": "a1", "entailed": True,
                     "contains_multiple_states": False}],
        "state_candidates": [
            {"candidate_index": 1, "relationship": "independent_outcome",
             "anchor_id": "a1"},
            {"candidate_index": 2, "relationship": "evaluation_criterion",
             "anchor_id": "a1"},
        ],
        "omissions": [], "collapses": [], "invented": [], "valid": True,
    }

    decision = _obligation_trust_decision(
        [c["text"] for c in candidates], anchors, audit, candidates,
    )

    assert decision["trusted"] is False
    assert decision["intra_anchor_fusion"][0]["anchor_id"] == "a1"


# ---------------------------------------------------------------------
# Gate A adversarial battery
# ---------------------------------------------------------------------


def _decide(objective, anchors, mapping):
    candidates = _source_state_candidates(objective)
    audit = {
        "regions": [
            {"region_index": index, "disposition": "represented_by_anchor",
             "anchor_id": anchors[0]["anchor_id"]}
            for index in range(1, len(candidates) + 1)
        ],
        "anchors": [{"anchor_id": a["anchor_id"], "entailed": True}
                    for a in anchors],
        "state_candidates": [
            {"candidate_index": index, "relationship": value[0],
             "anchor_id": value[1]} if isinstance(value, tuple) else
            {"candidate_index": index, "relationship": value,
             "reason": "descriptive"}
            for index, value in mapping.items()
        ],
        "omissions": [], "collapses": [], "invented": [], "valid": True,
    }
    return _obligation_trust_decision(
        [c["text"] for c in candidates], anchors, audit, candidates,
    )


def test_a_privacy_constraint_is_independent_of_the_action_it_governs():
    objective = "Send the report to finance, without exposing salary data."
    anchors = [
        {"anchor_id": "a1", "source_quote": "Send the report to finance",
         "meaning": "finance received the report", "depends_on": []},
        {"anchor_id": "a2", "source_quote": "without exposing salary data",
         "meaning": "no salary data was exposed", "depends_on": []},
    ]
    assert _decide(objective, anchors, {
        1: ("independent_outcome", "a1"),
        2: ("constraint_unit", "a2"),
    })["trusted"] is True

    # Fusing them is now refused: the send can succeed while privacy fails.
    fused = _decide(objective, [anchors[0]], {
        1: ("independent_outcome", "a1"),
        2: ("constraint_unit", "a1"),
    })
    assert fused["trusted"] is False


def test_a_budget_constraint_is_independent_of_the_purchase():
    objective = "Buy the licence, and keep it under 500 dollars."
    anchors = [
        {"anchor_id": "a1", "source_quote": "Buy the licence",
         "meaning": "the licence is purchased", "depends_on": []},
        {"anchor_id": "a2", "source_quote": "keep it under 500 dollars",
         "meaning": "spend stayed under the cap", "depends_on": []},
    ]
    assert _decide(objective, anchors, {
        1: ("independent_outcome", "a1"),
        2: ("constraint_unit", "a2"),
    })["trusted"] is True

    assert _decide(objective, [anchors[0]], {
        1: ("independent_outcome", "a1"),
        2: ("constraint_unit", "a1"),
    })["trusted"] is False


def test_verification_that_defines_completion_may_still_share_its_anchor():
    objective = "Save report.md, verified against the source."
    anchors = [{"anchor_id": "a1", "source_quote": "Save report.md",
                "meaning": "report.md exists and readback matches",
                "depends_on": []}]
    assert _decide(objective, anchors, {
        1: ("independent_outcome", "a1"),
        2: ("success_condition", "a1"),
    })["trusted"] is True


def test_a_rationale_that_defines_completeness_may_still_share_its_anchor():
    objective = "Tell me which option is best, and why."
    anchors = [{"anchor_id": "a1",
                "source_quote": "Tell me which option is best",
                "meaning": "the best option, with its reason",
                "depends_on": []}]
    assert _decide(objective, anchors, {
        1: ("independent_outcome", "a1"),
        2: ("rationale", "a1"),
    })["trusted"] is True


def test_selection_and_the_action_that_follows_it_stay_separate():
    objective = "Choose the best supplier and email them."
    anchors = [
        {"anchor_id": "a1", "source_quote": "Choose the best supplier",
         "meaning": "one supplier selected", "depends_on": []},
        {"anchor_id": "a2", "source_quote": "email them",
         "meaning": "the supplier was emailed", "depends_on": ["a1"]},
    ]
    assert _decide(objective, anchors, {
        1: ("independent_outcome", "a1"),
        2: ("independent_outcome", "a2"),
    })["trusted"] is True

    assert _decide(objective, [anchors[0]], {
        1: ("independent_outcome", "a1"),
        2: ("independent_outcome", "a1"),
    })["trusted"] is False


# ---------------------------------------------------------------------
# Gate A6 - the complete correction yields a trusted obligation set
# ---------------------------------------------------------------------

#: The live correction was itself defective -- it repaired anchor_2 and
#: left the evidence/decision pair fused, because the first round could
#: not see that second fusion to ask about it. This is what a producer
#: given the COMPLETE correction request returns: the live corrected set
#: with its one remaining fusion separated. Modelled, and labelled as
#: modelled: no external call is made in this gate.
COMPLETE_CORRECTION = [
    {"anchor_id": "anchor_1",
     "source_quote": "Research the current AI-agent products most relevant to Kalpavriksha",
     "meaning": "the relevant current product landscape is established",
     "depends_on": []},
    {"anchor_id": "anchor_2", "source_quote": "Compare the top 3",
     "meaning": "the selected top-three candidate set",
     "depends_on": ["anchor_1"]},
    {"anchor_id": "anchor_3", "source_quote": "pricing/free access",
     "meaning": "pricing and free access compared", "depends_on": ["anchor_2"]},
    {"anchor_id": "anchor_4", "source_quote": "computer/browser use",
     "meaning": "computer and browser use compared", "depends_on": ["anchor_2"]},
    {"anchor_id": "anchor_5", "source_quote": "autonomous task execution",
     "meaning": "autonomous task execution compared", "depends_on": ["anchor_2"]},
    {"anchor_id": "anchor_6", "source_quote": "persistence/memory",
     "meaning": "persistence and memory compared", "depends_on": ["anchor_2"]},
    {"anchor_id": "anchor_7", "source_quote": "major differentiators",
     "meaning": "major differentiators compared", "depends_on": ["anchor_2"]},
    {"anchor_id": "anchor_8", "source_quote": "Use sufficient public evidence",
     "meaning": "the evidence behind the comparison is sufficient and public",
     "depends_on": []},
    {"anchor_id": "anchor_9",
     "source_quote": "tell me which poses the closest competitive threat and why",
     "meaning": "the closest competitive threat is named, with its reason",
     "depends_on": ["anchor_3", "anchor_4", "anchor_5", "anchor_6", "anchor_7"]},
    {"anchor_id": "anchor_10",
     "source_quote": "save a verified competitive brief as Kalpavriksha_Competitive_Brief.md on my Desktop",
     "meaning": "the named Desktop brief exists and readback matches",
     "depends_on": ["anchor_9"]},
]

#: Each candidate state unit on its own anchor -- the placement a truthful
#: audit of the corrected set returns.
COMPLETE_PLACEMENT = [
    {"candidate_index": 1, "relationship": "prerequisite_state",
     "anchor_id": "anchor_1"},
    {"candidate_index": 2, "relationship": "prerequisite_state",
     "anchor_id": "anchor_2"},
    {"candidate_index": 3, "relationship": "evaluation_criterion",
     "anchor_id": "anchor_3"},
    {"candidate_index": 4, "relationship": "evaluation_criterion",
     "anchor_id": "anchor_4"},
    {"candidate_index": 5, "relationship": "evaluation_criterion",
     "anchor_id": "anchor_5"},
    {"candidate_index": 6, "relationship": "evaluation_criterion",
     "anchor_id": "anchor_6"},
    {"candidate_index": 7, "relationship": "evaluation_criterion",
     "anchor_id": "anchor_7"},
    {"candidate_index": 8, "relationship": "constraint_unit",
     "anchor_id": "anchor_8"},
    {"candidate_index": 9, "relationship": "independent_outcome",
     "anchor_id": "anchor_9"},
    {"candidate_index": 10, "relationship": "independent_outcome",
     "anchor_id": "anchor_10"},
]


def test_the_complete_correction_is_trusted_with_every_state_separate():
    audit = {
        "regions": [
            {"region_index": index, "disposition": "represented_by_anchor",
             "anchor_id": "anchor_1"}
            for index in range(1, len(_regions()) + 1)
        ],
        "anchors": [{"anchor_id": a["anchor_id"], "entailed": True,
                     "contains_multiple_states": False}
                    for a in COMPLETE_CORRECTION],
        "state_candidates": COMPLETE_PLACEMENT,
        "omissions": [], "collapses": [], "invented": [], "valid": True,
    }

    decision = _obligation_trust_decision(
        _regions(), COMPLETE_CORRECTION, audit, CANDIDATES,
    )

    assert decision["trusted"] is True, decision["issues"]
    assert decision["intra_anchor_fusion"] == []

    # Every pair the founder named can now hold DIFFERENT truthful states,
    # because each sits on its own anchor.
    by_anchor = {row["anchor_id"]: row["candidate_index"]
                 for row in COMPLETE_PLACEMENT}
    for left, right in (
        ("anchor_1", "anchor_2"),    # landscape / top-three
        ("anchor_2", "anchor_3"),    # top-three / pricing
        ("anchor_3", "anchor_4"),    # pricing / browser
        ("anchor_4", "anchor_5"),    # browser / autonomy
        ("anchor_5", "anchor_6"),    # autonomy / memory
        ("anchor_6", "anchor_7"),    # memory / differentiators
        ("anchor_9", "anchor_8"),    # threat decision / sufficient evidence
    ):
        assert left in by_anchor and right in by_anchor
        assert by_anchor[left] != by_anchor[right]


# ---------------------------------------------------------------------
# Gate C - the complete Stage-1 path, every gate in one run
# ---------------------------------------------------------------------

import json as _json  # noqa: E402
from types import SimpleNamespace  # noqa: E402

from master_agent.brain.intent import IntentLayer  # noqa: E402
from master_agent.planner.plan import Intent  # noqa: E402

GATE_C_ROWS = [
    {"kind": "information", "description": "Establish the relevant products",
     "candidate_property": False,
     "source_quote": "Research the current AI-agent products most relevant to Kalpavriksha",
     "success_meaning": "the relevant product landscape is established"},
    {"kind": "information", "description": "Establish the top-three set",
     "candidate_property": False, "source_quote": "Compare the top 3",
     "success_meaning": "exactly three qualified candidates form the set"},
    {"kind": "information", "description": "Compare pricing and free access",
     "candidate_property": True, "source_quote": "pricing/free access",
     "success_meaning": "pricing compared for each candidate"},
    {"kind": "information", "description": "Compare computer and browser use",
     "candidate_property": True, "source_quote": "computer/browser use",
     "success_meaning": "browser use compared for each candidate"},
    {"kind": "information", "description": "Compare autonomous task execution",
     "candidate_property": True, "source_quote": "autonomous task execution",
     "success_meaning": "autonomy compared for each candidate"},
    {"kind": "information", "description": "Compare persistence and memory",
     "candidate_property": True, "source_quote": "persistence/memory",
     "success_meaning": "memory compared for each candidate"},
    {"kind": "information", "description": "Compare major differentiators",
     "candidate_property": True, "source_quote": "major differentiators",
     "success_meaning": "differentiators compared for each candidate"},
    {"kind": "constraint", "description": "Use sufficient public evidence",
     "candidate_property": False,
     "source_quote": "Use sufficient public evidence",
     "success_meaning": "the evidence behind the comparison is sufficient and public"},
    {"kind": "information",
     "description": "Decide the closest competitive threat with rationale",
     "candidate_property": False,
     "source_quote": "tell me which poses the closest competitive threat and why",
     "success_meaning": "one product named as closest threat, with its reason"},
    {"kind": "deliverable", "description": "Save and verify the named brief",
     "candidate_property": False,
     "source_quote": "save a verified competitive brief as Kalpavriksha_Competitive_Brief.md on my Desktop",
     "success_meaning": "the named Desktop brief exists and readback matches"},
]

GATE_C_AUDIT_2 = {
    "regions": [
        {"region_index": index, "disposition": "represented_by_anchor",
         "anchor_id": "anchor_1"}
        for index in range(1, 5)
    ],
    "anchors": [{"anchor_id": a["anchor_id"], "entailed": True,
                 "contains_multiple_states": False}
                for a in COMPLETE_CORRECTION],
    "state_candidates": COMPLETE_PLACEMENT,
    "omissions": [], "collapses": [], "invented": [], "valid": True,
}

GATE_C_REVIEW_ZERO_BASED = {
    "valid": True, "independently_verifiable": True,
    "coverage": [
        {"anchor_id": a["anchor_id"], "requirement_indices": [index],
         "independently_trackable": True}
        for index, a in enumerate(COMPLETE_CORRECTION)          # 0-based!
    ],
    "invented": [],
}

GATE_C_REVIEW_ONE_BASED = {
    "valid": True, "independently_verifiable": True,
    "coverage": [
        {"anchor_id": a["anchor_id"], "requirement_indices": [index],
         "independently_trackable": True}
        for index, a in enumerate(COMPLETE_CORRECTION, start=1)
    ],
    "invented": [],
}


class _GateC:
    def __init__(self):
        self.seen: dict[str, list[str]] = {}

    def run(self, prompt, request=None):
        name = getattr(request, "requester", "")
        turn = len(self.seen.setdefault(name, [])) + 1
        self.seen[name].append(prompt)
        documents = {
            "brain_founder_obligations": captured("probe3_initial_anchors"),
            "brain_founder_obligation_audit": (
                captured("probe3_audit_1") if turn == 1 else GATE_C_AUDIT_2),
            "brain_founder_obligation_correction": {
                "anchors": COMPLETE_CORRECTION},
            "brain_semantic_requirements": {"requirements": GATE_C_ROWS},
            "brain_semantic_requirement_validation": GATE_C_REVIEW_ZERO_BASED,
            "brain_semantic_review_correction": GATE_C_REVIEW_ONE_BASED,
        }
        if name not in documents:
            return SimpleNamespace(ok=False, text="")
        return SimpleNamespace(ok=True, text=_json.dumps(documents[name]))


def test_gate_c_the_whole_stage_1_path_admits_every_founder_state():
    """Fused live anchors -> one complete correction -> trusted set ->
    decomposition -> a 0-based review -> one review repair -> Intent."""
    reasoner = _GateC()
    layer = IntentLayer.__new__(IntentLayer)
    layer._reasoner = reasoner
    canonical = Intent(goal=FOUNDER_INPUT, context={"raw_input": FOUNDER_INPUT})

    requirements = layer.requirements_for(canonical, raw=FOUNDER_INPUT)
    admission = canonical.context["requirement_admission"]

    assert admission["valid"] is True, admission["structural_issues"]
    assert admission["obligation_correction_attempted"] is True
    assert admission["review_correction_attempted"] is True
    # exactly one of each bounded repair
    assert len(reasoner.seen["brain_founder_obligation_correction"]) == 1
    assert len(reasoner.seen["brain_semantic_review_correction"]) == 1
    assert len(reasoner.seen["brain_founder_obligation_audit"]) == 2

    # Every Founder state independently represented -- by state, not count.
    said = [r.description.casefold() for r in requirements]
    for needle in ("relevant products", "top-three", "pricing",
                   "browser", "autonomous", "memory", "differentiators",
                   "public evidence", "threat", "brief"):
        assert sum(1 for d in said if needle in d) == 1, needle

    # The trace keeps the failed first attempt rather than tidying it away.
    assert admission["initial_obligation_anchors"]
    assert len(admission["initial_obligation_anchors"]) == 4
    assert len(admission["founder_obligation_anchors"]) == 10
    assert admission["state_candidates"] and admission["state_placements"]
