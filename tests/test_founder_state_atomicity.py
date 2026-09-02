"""Stage 1D: one anchor holds one satisfaction state.

Live Founder->Intent Probe #2 (2026-09-02, b519db8) trusted an obligation
set in which a single anchor carried six Founder meanings:

    anchor_2  "Compare the top 3 across pricing/free access,
               computer/browser use, autonomous task execution,
               persistence/memory ..."

fusing the SELECTION of the top three with five requested COMPARISONS.
The auditor returned valid=true, collapses=[], everything entailed, so
deterministic reconciliation had no contradiction to act on. One anchor
exposes one satisfaction state, so "top three selected" could never be
SATISFIED while "pricing compared" stayed UNRESOLVED.

The producer anchors and the audit below are the VERBATIM live payloads
from that probe, not an approximation of them.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from master_agent.brain.intent import (
    IntentLayer,
    _intra_anchor_fusion,
    _obligation_trust_decision,
    _source_state_candidates,
)
from master_agent.planner.plan import Intent

FOUNDER_INPUT = (
    "Research the current AI-agent products most relevant to Kalpavriksha.\n"
    "Compare the top 3 across pricing/free access, computer/browser use,\n"
    "autonomous task execution, persistence/memory and major differentiators.\n"
    "Use sufficient public evidence, tell me which poses the closest competitive\n"
    "threat and why, and save a verified competitive brief as\n"
    "Kalpavriksha_Competitive_Brief.md on my Desktop."
)

# --- verbatim Probe #2 payloads --------------------------------------

PROBE2_ANCHORS = [
    {
        "anchor_id": "anchor_1",
        "source_quote": (
            "Research the current AI-agent products most relevant to "
            "Kalpavriksha"
        ),
        "meaning": (
            "Identify and establish the candidate set of current AI-agent "
            "products most relevant to Kalpavriksha"
        ),
        "depends_on": [],
    },
    {
        "anchor_id": "anchor_2",
        "source_quote": (
            "Compare the top 3 across pricing/free access, computer/browser "
            "use, autonomous task execution, persistence/memory and major "
            "differentiators"
        ),
        "meaning": (
            "Compare the top 3 AI-agent products across pricing/free access, "
            "computer/browser use, autonomous task execution, "
            "persistence/memory and major differentiators"
        ),
        "depends_on": ["anchor_1"],
    },
    {
        "anchor_id": "anchor_3",
        "source_quote": (
            "Use sufficient public evidence, tell me which poses the closest "
            "competitive threat and why"
        ),
        "meaning": (
            "Identify which product poses the closest competitive threat and "
            "explain why using sufficient public evidence"
        ),
        "depends_on": ["anchor_2"],
    },
    {
        "anchor_id": "anchor_4",
        "source_quote": (
            "save a verified competitive brief as "
            "Kalpavriksha_Competitive_Brief.md on my Desktop"
        ),
        "meaning": (
            "Save the verified competitive brief document as "
            "Kalpavriksha_Competitive_Brief.md on the Desktop"
        ),
        "depends_on": ["anchor_2", "anchor_3"],
    },
]

PROBE2_AUDIT = {
    "regions": [
        {"region_index": 1, "disposition": "represented_by_anchor",
         "anchor_id": "anchor_1"},
        {"region_index": 2, "disposition": "represented_by_anchor",
         "anchor_id": "anchor_2"},
        {"region_index": 3, "disposition": "represented_by_anchor",
         "anchor_id": "anchor_2"},
        {"region_index": 4, "disposition": "represented_by_anchor",
         "anchor_id": "anchor_3"},
    ],
    "anchors": [
        {"anchor_id": "anchor_1", "entailed": True},
        {"anchor_id": "anchor_2", "entailed": True},
        {"anchor_id": "anchor_3", "entailed": True},
        {"anchor_id": "anchor_4", "entailed": True},
    ],
    "omissions": [],
    "collapses": [],
    "invented": [],
    "valid": True,
}

REFUSALS = frozenset({
    "unsettled_interpretation",
    "obligation_set_untrusted",
    "obligation_audit_unusable",
})


class ByRequester:
    def __init__(self, **documents):
        self.documents = documents
        self.seen: dict[str, list[str]] = {}

    def run(self, prompt, request=None):
        requester = getattr(request, "requester", "")
        self.seen.setdefault(requester, []).append(prompt)
        document = self.documents.get(requester)
        if document is None:
            return SimpleNamespace(ok=False, text="")
        if callable(document):
            document = document(len(self.seen[requester]))
        return SimpleNamespace(ok=True, text=json.dumps(document))


def layer(reasoner):
    result = IntentLayer.__new__(IntentLayer)
    result._reasoner = reasoner
    return result


def admit(objective, reasoner):
    canonical = Intent(goal=objective, context={"raw_input": objective})
    requirements = layer(reasoner).requirements_for(canonical, raw=objective)
    return canonical.context["requirement_admission"], requirements


def placements(pairs, context_reason="descriptive context"):
    """candidate_index -> (relationship, anchor_id) placements."""
    rows = []
    for index, value in pairs.items():
        if isinstance(value, tuple):
            relationship, anchor_id = value
            rows.append({"candidate_index": index,
                         "relationship": relationship,
                         "anchor_id": anchor_id})
        else:
            rows.append({"candidate_index": index, "relationship": value,
                         "reason": context_reason})
    return rows


# ---------------------------------------------------------------------
# The scaffold now exposes the states that were fused
# ---------------------------------------------------------------------


def test_the_live_fused_clause_now_exposes_each_requested_state():
    texts = [c["text"] for c in _source_state_candidates(FOUNDER_INPUT)]
    joined = " | ".join(texts).casefold()

    assert "compare the top 3" in joined
    for dimension in ("pricing/free access", "computer/browser use",
                      "autonomous task execution", "persistence/memory",
                      "major differentiators"):
        assert dimension.casefold() in joined, dimension


def test_list_syntax_alone_does_not_force_splitting():
    # No comma, no list: one cohesive unit each.
    assert len(_source_state_candidates("Save and verify report.md")) == 1
    assert len(
        _source_state_candidates("Tell me which option is best and why")
    ) == 1


# ---------------------------------------------------------------------
# 1 - the exact Probe #2 failure
# ---------------------------------------------------------------------


def test_the_exact_probe_2_audit_can_no_longer_certify_the_fused_anchor():
    """The live auditor answered at region scale and never placed the six
    state units. Silence is not consent."""
    reasoner = ByRequester(
        brain_founder_obligations={"anchors": PROBE2_ANCHORS},
        brain_founder_obligation_audit=PROBE2_AUDIT,
        brain_founder_obligation_correction={"anchors": PROBE2_ANCHORS},
    )

    admission, requirements = admit(FOUNDER_INPUT, reasoner)

    assert requirements == ()
    assert admission["valid"] is False
    assert admission["semantic_verdict"] in REFUSALS
    assert any(
        "state_candidates" in issue or "state candidate" in issue
        for issue in admission["obligation_issues"]
    ), admission["obligation_issues"]


def test_a_truthful_audit_of_the_probe_2_anchors_proves_intra_anchor_fusion():
    """When the auditor DOES place each unit honestly, the fusion is
    derived deterministically from its own placements."""
    candidates = _source_state_candidates(FOUNDER_INPUT)
    # c2..c7 are the selection and the five requested dimensions; the live
    # producer put every one of them inside anchor_2.
    mapping = {
        1: ("independent_outcome", "anchor_1"),
        2: ("prerequisite_state", "anchor_2"),
        3: ("evaluation_criterion", "anchor_2"),
        4: ("evaluation_criterion", "anchor_2"),
        5: ("evaluation_criterion", "anchor_2"),
        6: ("evaluation_criterion", "anchor_2"),
        7: ("evaluation_criterion", "anchor_2"),
        8: ("constraint_unit", "anchor_3"),
        9: ("independent_outcome", "anchor_3"),
    }
    for index in range(10, len(candidates) + 1):
        mapping[index] = ("independent_outcome", "anchor_4")
    audit = dict(PROBE2_AUDIT, state_candidates=placements(mapping))

    fused = _intra_anchor_fusion(candidates, PROBE2_ANCHORS, audit)
    decision = _obligation_trust_decision(
        [c["text"] for c in candidates], PROBE2_ANCHORS, audit, candidates,
    )

    # Stage 1 convergence: a constraint holds its own status, so
    # anchor_3 (evidence constraint + threat decision) is a second proven
    # fusion. Collecting both is what lets ONE correction repair
    # everything the evidence shows.
    by_id = {row["anchor_id"]: row for row in fused}
    assert set(by_id) == {"anchor_2", "anchor_3"}
    assert len(by_id["anchor_2"]["states"]) == 6
    assert decision["trusted"] is False
    assert any("fuses independently trackable" in issue
               for issue in decision["issues"])


def test_model_valid_true_cannot_override_atomicity_evidence():
    candidates = _source_state_candidates(FOUNDER_INPUT)
    audit = dict(PROBE2_AUDIT, valid=True, state_candidates=placements({
        index: (("evaluation_criterion", "anchor_2") if 2 <= index <= 7
                else ("independent_outcome", "anchor_1"))
        for index in range(1, len(candidates) + 1)
    }))

    decision = _obligation_trust_decision(
        [c["text"] for c in candidates], PROBE2_ANCHORS, audit, candidates,
    )

    assert audit["valid"] is True
    assert decision["trusted"] is False


def test_an_auditor_declaring_multiple_states_does_not_decide():
    candidates = _source_state_candidates("Save and verify report.md")
    anchors = [{"anchor_id": "a1", "source_quote": "Save and verify report.md",
                "meaning": "one deliverable", "depends_on": []}]
    audit = {
        "regions": [{"region_index": 1,
                     "disposition": "represented_by_anchor",
                     "anchor_id": "a1"}],
        "anchors": [{"anchor_id": "a1", "entailed": True,
                     "contains_multiple_states": True}],
        "state_candidates": placements({1: ("independent_outcome", "a1")}),
        "omissions": [], "collapses": [], "invented": [], "valid": True,
    }

    decision = _obligation_trust_decision(
        [c["text"] for c in candidates], anchors, audit, candidates,
    )

    # Its own placements show ONE trackable state. A declaration with no
    # structured support is the mirror image of valid=true -- recorded,
    # never authoritative. Live Probe #3 refused a legitimate anchor on
    # exactly such a declaration.
    assert decision["trusted"] is True, decision["issues"]


# ---------------------------------------------------------------------
# 2 - cohesion must survive
# ---------------------------------------------------------------------


def _clean(objective, anchors, mapping):
    # These cases exercise the STATE layer, so the candidate texts stand in
    # as the region list; one disposition per candidate keeps the region
    # boundary satisfied without asserting anything about it.
    candidates = _source_state_candidates(objective)
    audit = {
        "regions": [
            {"region_index": index, "disposition": "represented_by_anchor",
             "anchor_id": anchors[0]["anchor_id"]}
            for index in range(1, len(candidates) + 1)
        ],
        "anchors": [{"anchor_id": a["anchor_id"], "entailed": True,
                     "contains_multiple_states": False} for a in anchors],
        "state_candidates": placements(mapping),
        "omissions": [], "collapses": [], "invented": [], "valid": True,
    }
    return _obligation_trust_decision(
        [c["text"] for c in candidates], anchors, audit, candidates,
    )


def test_save_and_verify_remains_one_cohesive_deliverable():
    anchors = [{"anchor_id": "a1", "source_quote": "Save and verify report.md",
                "meaning": "report.md exists and readback matches",
                "depends_on": []}]
    decision = _clean("Save and verify report.md", anchors,
                      {1: ("independent_outcome", "a1")})
    assert decision["trusted"] is True, decision["issues"]


def test_a_decision_and_its_rationale_remain_one_outcome():
    objective = "Tell me which option is best and why"
    anchors = [{"anchor_id": "a1",
                "source_quote": "Tell me which option is best and why",
                "meaning": "the best option, with the reason",
                "depends_on": []}]
    decision = _clean(objective, anchors, {1: ("independent_outcome", "a1")})
    assert decision["trusted"] is True, decision["issues"]


def test_a_success_condition_may_share_its_anchor():
    """Two units, one anchor, but the second is not separately
    satisfiable -- so it is not fusion."""
    objective = "Save report.md, verified against the source."
    candidates = _source_state_candidates(objective)
    anchors = [{"anchor_id": "a1", "source_quote": "Save report.md",
                "meaning": "report.md exists and readback matches",
                "depends_on": []}]
    audit = {
        "regions": [
            {"region_index": index, "disposition": "represented_by_anchor",
             "anchor_id": "a1"}
            for index in range(1, len(candidates) + 1)
        ],
        "anchors": [{"anchor_id": "a1", "entailed": True}],
        "state_candidates": placements({
            1: ("independent_outcome", "a1"),
            2: ("success_condition", "a1"),
        }),
        "omissions": [], "collapses": [], "invented": [], "valid": True,
    }
    decision = _obligation_trust_decision(
        [c["text"] for c in candidates], anchors, audit, candidates,
    )
    assert len(candidates) == 2
    assert decision["trusted"] is True, decision["issues"]


# ---------------------------------------------------------------------
# 3 - the battery
# ---------------------------------------------------------------------


def test_selection_and_comparison_stay_separately_satisfiable():
    objective = "Find the top three suppliers and compare their prices."
    anchors = [
        {"anchor_id": "a1", "source_quote": "Find the top three suppliers",
         "meaning": "the qualified supplier set", "depends_on": []},
        {"anchor_id": "a2", "source_quote": "compare their prices",
         "meaning": "price comparison across the set", "depends_on": ["a1"]},
    ]
    decision = _clean(objective, anchors, {
        1: ("independent_outcome", "a1"),
        2: ("evaluation_criterion", "a2"),
    })
    assert decision["trusted"] is True, decision["issues"]


def test_collapsing_selection_into_comparison_is_refused():
    objective = "Find the top three suppliers and compare their prices."
    anchors = [{"anchor_id": "a1",
                "source_quote": "Find the top three suppliers",
                "meaning": "find three suppliers and compare their prices",
                "depends_on": []}]
    decision = _clean(objective, anchors, {
        1: ("independent_outcome", "a1"),
        2: ("evaluation_criterion", "a1"),
    })
    assert decision["trusted"] is False
    assert any("fuses independently trackable" in issue
               for issue in decision["issues"])


def test_each_requested_comparison_dimension_stays_trackable():
    objective = (
        "Compare the three tools across price, offline support and "
        "integrations."
    )
    candidates = _source_state_candidates(objective)
    assert len(candidates) == 4  # the set, then three dimensions

    anchors = [
        {"anchor_id": "a1", "source_quote": "Compare the three tools",
         "meaning": "the three tools under comparison", "depends_on": []},
        {"anchor_id": "a2", "source_quote": "price",
         "meaning": "price comparison", "depends_on": ["a1"]},
        {"anchor_id": "a3", "source_quote": "offline support",
         "meaning": "offline support comparison", "depends_on": ["a1"]},
        {"anchor_id": "a4", "source_quote": "integrations",
         "meaning": "integrations comparison", "depends_on": ["a1"]},
    ]
    decision = _clean(objective, anchors, {
        1: ("independent_outcome", "a1"),
        2: ("evaluation_criterion", "a2"),
        3: ("evaluation_criterion", "a3"),
        4: ("evaluation_criterion", "a4"),
    })
    assert decision["trusted"] is True, decision["issues"]


def test_a_decision_and_a_following_external_action_stay_separate():
    objective = "Choose the best supplier and email them."
    anchors = [
        {"anchor_id": "a1", "source_quote": "Choose the best supplier",
         "meaning": "one supplier is selected", "depends_on": []},
        {"anchor_id": "a2", "source_quote": "email them",
         "meaning": "the selected supplier has been emailed",
         "depends_on": ["a1"]},
    ]
    decision = _clean(objective, anchors, {
        1: ("independent_outcome", "a1"),
        2: ("independent_outcome", "a2"),
    })
    assert decision["trusted"] is True, decision["issues"]


def test_a_research_chain_keeps_its_three_states():
    objective = (
        "Find 2026 action RPGs with free demos and give verified download "
        "links."
    )
    anchors = [
        {"anchor_id": "a1",
         "source_quote": "Find 2026 action RPGs with free demos",
         "meaning": "eligible titles with demo availability established",
         "depends_on": []},
        {"anchor_id": "a2", "source_quote": "give verified download links",
         "meaning": "a verified link per eligible title",
         "depends_on": ["a1"]},
    ]
    decision = _clean(objective, anchors, {
        1: ("independent_outcome", "a1"),
        2: ("independent_outcome", "a2"),
    })
    assert decision["trusted"] is True, decision["issues"]


def test_a_descriptive_list_may_be_context_without_forcing_obligations():
    objective = (
        "Review the vendor shortlist, which is already agreed, and send it "
        "to finance."
    )
    candidates = _source_state_candidates(objective)
    anchors = [
        {"anchor_id": "a1", "source_quote": "Review the vendor shortlist",
         "meaning": "the shortlist has been reviewed", "depends_on": []},
        {"anchor_id": "a2", "source_quote": "send it to finance",
         "meaning": "the shortlist reached finance", "depends_on": ["a1"]},
    ]
    mapping = {1: ("independent_outcome", "a1")}
    for index in range(2, len(candidates)):
        mapping[index] = "context"
    mapping[len(candidates)] = ("independent_outcome", "a2")

    decision = _clean(objective, anchors, mapping)

    assert decision["trusted"] is True, decision["issues"]


def test_the_bounded_correction_names_the_fused_states():
    reasoner = ByRequester(
        brain_founder_obligations={"anchors": PROBE2_ANCHORS},
        brain_founder_obligation_audit=lambda n: dict(
            PROBE2_AUDIT, state_candidates=placements({
                index: (("evaluation_criterion", "anchor_2")
                        if 2 <= index <= 7 else
                        ("independent_outcome", "anchor_1"))
                for index in range(
                    1, len(_source_state_candidates(FOUNDER_INPUT)) + 1)
            })),
        brain_founder_obligation_correction={"anchors": PROBE2_ANCHORS},
    )

    admission, requirements = admit(FOUNDER_INPUT, reasoner)

    assert requirements == ()
    assert admission["obligation_correction_attempted"] is True
    correction = reasoner.seen["brain_founder_obligation_correction"][0]
    assert "independently satisfiable Founder states" in correction
    assert "pricing/free access" in correction
    # exactly one correction, then a complete fresh audit
    assert len(reasoner.seen["brain_founder_obligation_correction"]) == 1
    assert len(reasoner.seen["brain_founder_obligation_audit"]) == 2
