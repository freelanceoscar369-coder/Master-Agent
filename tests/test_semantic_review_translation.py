"""Gate B: an unreadable review is a translation fault, not a verdict.

Live Founder->Intent Probe #2 (2026-09-02, b519db8) lost an entire
mission because the semantic reviewer answered in 0-based indices:

    coverage: [{anchor_1: [0]}, {anchor_2: [1]},
               {anchor_3: [2, 3]}, {anchor_4: [4]}]

Production refused with ``semantic_review_unusable`` and stopped. Every
other Stage-1 failure -- a lost obligation, an invented one, a fused
anchor -- gets one grounded repair. This one had none, so a formatting
slip was fatal where a genuine semantic violation was not, and the
refusal also dropped the already-trusted obligation set from the record.

The indices below are the VERBATIM live response.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from master_agent.brain.intent import IntentLayer, _audit_structure_issues
from master_agent.planner.plan import Intent

OBJECTIVE = (
    "Research the current AI-agent products most relevant to Kalpavriksha "
    "and give me the top 3."
)

ANCHORS = [
    {"anchor_id": "anchor_1",
     "source_quote": "Research the current AI-agent products most relevant to Kalpavriksha",
     "meaning": "the relevant product landscape is established",
     "depends_on": []},
    {"anchor_id": "anchor_2", "source_quote": "give me the top 3",
     "meaning": "the selected top-three set", "depends_on": ["anchor_1"]},
]

ROWS = [
    {"kind": "information", "description": "Establish the relevant products",
     "candidate_property": False,
     "source_quote": "Research the current AI-agent products most relevant to Kalpavriksha",
     "success_meaning": "the relevant product landscape is established"},
    {"kind": "information", "description": "Establish the top-three set",
     "candidate_property": False, "source_quote": "give me the top 3",
     "success_meaning": "exactly three qualified candidates form the set"},
]

#: The Probe #2 fault: indices one lower than the contract.
ZERO_BASED_REVIEW = {
    "valid": True, "independently_verifiable": True,
    "coverage": [
        {"anchor_id": "anchor_1", "requirement_indices": [0],
         "independently_trackable": True},
        {"anchor_id": "anchor_2", "requirement_indices": [1],
         "independently_trackable": True},
    ],
    "invented": [],
}

ONE_BASED_REVIEW = {
    "valid": True, "independently_verifiable": True,
    "coverage": [
        {"anchor_id": "anchor_1", "requirement_indices": [1],
         "independently_trackable": True},
        {"anchor_id": "anchor_2", "requirement_indices": [2],
         "independently_trackable": True},
    ],
    "invented": [],
}

STATE_PLACEMENT = [
    {"candidate_index": 1, "relationship": "independent_outcome",
     "anchor_id": "anchor_1"},
    {"candidate_index": 2, "relationship": "independent_outcome",
     "anchor_id": "anchor_2"},
]

AUDIT = {
    "regions": [
        {"region_index": 1, "disposition": "represented_by_anchor",
         "anchor_id": "anchor_1"},
        {"region_index": 2, "disposition": "represented_by_anchor",
         "anchor_id": "anchor_2"},
    ],
    "anchors": [{"anchor_id": "anchor_1", "entailed": True},
                {"anchor_id": "anchor_2", "entailed": True}],
    "state_candidates": STATE_PLACEMENT,
    "omissions": [], "collapses": [], "invented": [], "valid": True,
}


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


def admit(reasoner):
    layer = IntentLayer.__new__(IntentLayer)
    layer._reasoner = reasoner
    canonical = Intent(goal=OBJECTIVE, context={"raw_input": OBJECTIVE})
    requirements = layer.requirements_for(canonical, raw=OBJECTIVE)
    return canonical.context["requirement_admission"], requirements, reasoner


def _reasoner(review_documents):
    return ByRequester(
        brain_founder_obligations={"anchors": ANCHORS},
        brain_founder_obligation_audit=AUDIT,
        brain_semantic_requirements={"requirements": ROWS},
        brain_semantic_requirement_validation=lambda n: review_documents[0],
        brain_semantic_review_correction=lambda n: review_documents[1],
    )


def test_the_zero_based_review_is_still_rejected_not_normalised():
    """No index+1 rule: the contract stays strict."""
    issues = _audit_structure_issues(OBJECTIVE, ROWS, dict(
        ZERO_BASED_REVIEW, anchors=ANCHORS))

    assert any("invalid requirement index 0" in issue for issue in issues)


def test_the_reviewer_is_told_the_indices_it_may_use():
    """The convention is machine-readable, not merely described."""
    admission, _, reasoner = admit(_reasoner([ONE_BASED_REVIEW, ONE_BASED_REVIEW]))
    prompt = reasoner.seen["brain_semantic_requirement_validation"][0]

    assert '"requirement_index": 1' in prompt
    assert "1-based" in prompt
    assert "no index 0" in prompt


def test_one_bounded_review_correction_recovers_the_live_failure():
    """The exact Probe #2 response, then a corrected restatement."""
    admission, requirements, reasoner = admit(
        _reasoner([ZERO_BASED_REVIEW, ONE_BASED_REVIEW]))

    assert len(reasoner.seen["brain_semantic_review_correction"]) == 1
    assert admission["review_correction_attempted"] is True
    assert admission["valid"] is True
    assert [r.description for r in requirements] == [
        "Establish the relevant products", "Establish the top-three set",
    ]


def test_the_correction_reconsiders_nothing_semantic():
    _, _, reasoner = admit(_reasoner([ZERO_BASED_REVIEW, ONE_BASED_REVIEW]))
    correction = reasoner.seen["brain_semantic_review_correction"][0]

    assert "only restate your mapping" in correction
    assert "Do not reconsider the Founder's meaning" in correction
    # The obligations were not regenerated, and neither were requirements.
    assert len(reasoner.seen["brain_founder_obligations"]) == 1
    assert len(reasoner.seen["brain_semantic_requirements"]) == 1


def test_a_second_unusable_review_refuses_and_keeps_the_trusted_anchors():
    admission, requirements, reasoner = admit(
        _reasoner([ZERO_BASED_REVIEW, ZERO_BASED_REVIEW]))

    assert requirements == ()
    assert admission["valid"] is False
    assert admission["semantic_verdict"] == "semantic_review_unusable"
    assert admission["review_correction_attempted"] is True
    # Gate B4: the obligation boundary passed, and refusing the review
    # must not erase that from the record.
    assert [a["anchor_id"] for a in admission["founder_obligation_anchors"]] == [
        "anchor_1", "anchor_2",
    ]
    assert admission["source_regions"]
    assert admission["anchor_entailment"]
    assert admission["state_placements"]
