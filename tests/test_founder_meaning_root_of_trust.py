"""Stage 1C: the Founder obligation set is itself a root of trust.

Stage 1B proved that a truthful anchor set is policed correctly. These
tests attack the anchor set itself, which Stage 1B took on faith:

    1. an anchor set that silently omits an obligation
    2. an anchor whose meaning its own real quote does not entail

Both were ADMITTED at bd740d4. Neither may be admitted again.

The fake reasoner answers by ``requester`` rather than by call order, so
each test states what each boundary was asked and is unaffected by how
many calls the pipeline makes.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from master_agent.brain.intent import (
    IntentLayer,
    _obligation_trust_decision,
    _source_coverage_regions,
)
from master_agent.planner.plan import Intent

LANDSCAPE = (
    "Research the current AI-agent products most relevant to Kalpavriksha "
    "and give me the top 3."
)
BRIEF = "Save a verified competitive brief on my Desktop."

#: Every way admission may refuse an untrusted obligation set. After a
#: bounded correction the meaning is simply not settled, which is the
#: contract MissionService already refuses on.
REFUSALS = frozenset({
    "unsettled_interpretation",
    "obligation_set_untrusted",
    "obligation_audit_unusable",
})


class ByRequester:
    """Answers each boundary independently; records what each one saw."""

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


def row(kind, description, quote, candidate=False, success=None):
    return {
        "kind": kind,
        "description": description,
        "candidate_property": candidate,
        "source_quote": quote,
        "success_meaning": success or description,
    }


# ---------------------------------------------------------------------
# The deterministic scaffold
# ---------------------------------------------------------------------


def test_scaffold_makes_a_dropped_predicate_visible():
    regions = _source_coverage_regions(LANDSCAPE)

    joined = " | ".join(regions).casefold()
    assert "research the current ai-agent products" in joined
    assert "top 3" in joined
    # Two coordinated predicates, so the first cannot vanish unexplained.
    assert len(regions) >= 2


def test_scaffold_is_not_a_requirement_splitter():
    # It offers candidate regions; it never decides they are obligations.
    regions = _source_coverage_regions("Save and verify report.md")
    assert regions  # visible
    # The scaffold makes no claim about how many obligations these are.
    assert all(isinstance(region, str) for region in regions)


# ---------------------------------------------------------------------
# 1 - the incomplete anchor set
# ---------------------------------------------------------------------


def test_incomplete_anchor_set_is_refused_when_the_auditor_reports_it():
    """The producer omits the landscape obligation; the blind auditor
    sees the raw Founder input and says so. Admission must refuse."""
    reasoner = ByRequester(
        brain_founder_obligations={
            "anchors": [{
                "anchor_id": "a1",
                "source_quote": (
                    "Research the current AI-agent products most relevant to "
                    "Kalpavriksha and give me the top 3"
                ),
                "meaning": "Identify the top three relevant products",
                "depends_on": [],
            }],
        },
        brain_founder_obligation_audit={
            "regions": [
                {"region_index": 1, "disposition": "represented_by_anchor",
                 "anchor_id": "a1"},
                {"region_index": 2, "disposition": "omitted",
                 "reason": "establishing the relevant product landscape is a "
                           "separate state and no anchor carries it"},
            ],
            "anchors": [{"anchor_id": "a1", "entailed": True}],
            "omissions": [{
                "source_quote": "Research the current AI-agent products",
                "meaning": "Establish the relevant product landscape",
            }],
            "collapses": [],
            "invented": [],
            "valid": True,
        },
    )

    admission, requirements = admit(LANDSCAPE, reasoner)

    assert requirements == ()
    assert admission["valid"] is False
    assert admission["semantic_verdict"] in REFUSALS
    # The refusal names the Founder meaning that went missing.
    assert any(
        "no anchor" in issue or "omitted" in issue
        for issue in admission["obligation_issues"]
    ), admission["obligation_issues"]
    assert "brain_founder_obligations" in reasoner.seen
    assert "brain_founder_obligation_audit" in reasoner.seen


def test_a_colluding_auditor_cannot_leave_a_source_region_unexplained():
    """Even if the auditor certifies the set, an unexplained deterministic
    region refuses admission. The model's word is not the authority."""
    reasoner = ByRequester(
        brain_founder_obligations={
            "anchors": [{
                "anchor_id": "a1",
                "source_quote": "give me the top 3",
                "meaning": "Identify the top three relevant products",
                "depends_on": [],
            }],
        },
        brain_founder_obligation_audit={
            # Region 1 is simply not mentioned at all.
            "regions": [
                {"region_index": 2, "disposition": "represented_by_anchor",
                 "anchor_id": "a1"},
            ],
            "anchors": [{"anchor_id": "a1", "entailed": True}],
            "omissions": [],
            "collapses": [],
            "invented": [],
            "valid": True,
        },
    )

    admission, requirements = admit(LANDSCAPE, reasoner)

    assert requirements == ()
    assert admission["valid"] is False


# ---------------------------------------------------------------------
# 2 - fake grounding
# ---------------------------------------------------------------------


def test_a_real_quote_carrying_an_unentailed_meaning_is_refused():
    reasoner = ByRequester(
        brain_founder_obligations={
            "anchors": [{
                "anchor_id": "b1",
                "source_quote": "Save a verified competitive brief on my Desktop",
                "meaning": "Email the competitive brief to the whole team",
                "depends_on": [],
            }],
        },
        brain_founder_obligation_audit={
            "regions": [
                {"region_index": 1, "disposition": "represented_by_anchor",
                 "anchor_id": "b1"},
            ],
            "anchors": [{
                "anchor_id": "b1", "entailed": False,
                "reason": "the Founder asked for the brief to be saved and "
                          "verified on the Desktop, not emailed to anyone",
            }],
            "omissions": [],
            "collapses": [],
            "invented": [],
            "valid": True,
        },
    )

    admission, requirements = admit(BRIEF, reasoner)

    assert requirements == ()
    assert admission["valid"] is False
    assert admission["semantic_verdict"] in REFUSALS
    assert any(
        "does not entail" in issue
        for issue in admission["obligation_issues"]
    ), admission["obligation_issues"]


def test_a_missing_entailment_verdict_is_refused_not_assumed():
    """Silence is not consent: an anchor with no entailment evidence
    cannot be admitted."""
    reasoner = ByRequester(
        brain_founder_obligations={
            "anchors": [{
                "anchor_id": "b1",
                "source_quote": "Save a verified competitive brief on my Desktop",
                "meaning": "Email the competitive brief to the whole team",
                "depends_on": [],
            }],
        },
        brain_founder_obligation_audit={
            "regions": [
                {"region_index": 1, "disposition": "represented_by_anchor",
                 "anchor_id": "b1"},
            ],
            "anchors": [],  # no verdict at all
            "omissions": [],
            "collapses": [],
            "invented": [],
            "valid": True,
        },
    )

    admission, requirements = admit(BRIEF, reasoner)

    assert requirements == ()
    assert admission["valid"] is False


# ---------------------------------------------------------------------
# The producer must be blind to the decomposition it will be policed by
# ---------------------------------------------------------------------


def test_the_obligation_producer_never_sees_a_requirement_decomposition():
    reasoner = ByRequester(
        brain_founder_obligations={
            "anchors": [{
                "anchor_id": "a1", "source_quote": "give me the top 3",
                "meaning": "Identify the top three relevant products",
                "depends_on": [],
            }],
        },
        brain_founder_obligation_audit={
            "regions": [], "anchors": [], "omissions": [],
            "collapses": [], "invented": [], "valid": False,
        },
    )

    admit(LANDSCAPE, reasoner)

    produced = reasoner.seen["brain_founder_obligations"][0]
    assert "requirement" not in produced.casefold().replace(
        "requirements they", "")
    assert "candidate_property" not in produced
    # The auditor may see the anchors and the Founder input, never the
    # downstream decomposition.
    audited = reasoner.seen["brain_founder_obligation_audit"][0]
    assert "candidate_property" not in audited


# ---------------------------------------------------------------------
# The deterministic reconciliation itself
# ---------------------------------------------------------------------


def test_model_valid_true_cannot_override_a_reported_omission():
    regions = ("Research the current AI-agent products", "give me the top 3")
    anchors = ({"anchor_id": "a1", "source_quote": "give me the top 3",
                "meaning": "top three", "depends_on": []},)
    audit = {
        "valid": True,
        "regions": [
            {"region_index": 1, "disposition": "represented_by_anchor",
             "anchor_id": "a1"},
            {"region_index": 2, "disposition": "represented_by_anchor",
             "anchor_id": "a1"},
        ],
        "anchors": [{"anchor_id": "a1", "entailed": True}],
        "omissions": [{"source_quote": "Research the current AI-agent products",
                       "meaning": "Establish the landscape"}],
        "collapses": [], "invented": [],
    }

    decision = _obligation_trust_decision(regions, anchors, audit)

    assert decision["trusted"] is False
    assert decision["omissions"]


def test_a_clean_obligation_set_is_trusted():
    regions = _source_coverage_regions(BRIEF)
    anchors = ({
        "anchor_id": "b1",
        "source_quote": "Save a verified competitive brief on my Desktop",
        "meaning": "The named brief exists on the Desktop and readback matches",
        "depends_on": [],
    },)
    audit = {
        "valid": True,
        "regions": [
            {"region_index": index, "disposition": "represented_by_anchor",
             "anchor_id": "b1"}
            for index in range(1, len(regions) + 1)
        ],
        "anchors": [{"anchor_id": "b1", "entailed": True}],
        "omissions": [], "collapses": [], "invented": [],
    }

    decision = _obligation_trust_decision(regions, anchors, audit)

    assert decision["trusted"] is True, decision["issues"]


# ---------------------------------------------------------------------
# Generalization: state independence, not grammar splitting
# ---------------------------------------------------------------------


def test_two_obligations_are_visible_but_one_deliverable_is_not_split():
    """The same scaffold must separate genuinely independent states and
    leave one cohesive outcome alone. Grammar is not the discriminator."""
    two = _source_coverage_regions(
        "Find three project-management tools and compare their pricing."
    )
    assert len(two) == 2
    assert "project-management tools" in two[0]
    assert "pricing" in two[1]

    # An outcome and its completion condition stay one region: the left
    # side is a bare verb, so there is nothing to coordinate.
    assert len(_source_coverage_regions("Save and verify report.md")) == 1

    # A decision and its requested rationale likewise.
    assert len(
        _source_coverage_regions("Tell me which option is best and why")
    ) == 1


def test_the_deterministic_fast_path_asks_no_semantic_question():
    reasoner = ByRequester()
    typed = Intent(
        goal="Create folder KalpavrikshaAccept on the Desktop",
        capability="Filesystem.CreateFolder",
        payload={"path": r"C:\Users\DELL\Desktop\KalpavrikshaAccept"},
        context={"raw_input": "Create folder KalpavrikshaAccept on the Desktop"},
    )

    requirements = layer(reasoner).requirements_for(
        typed, raw="Create folder KalpavrikshaAccept on the Desktop",
    )

    assert requirements
    assert reasoner.seen == {}
    assert typed.context["requirement_admission"]["semantic_verdict"] == (
        "valid_deterministic"
    )


def test_an_invented_obligation_the_founder_never_stated_is_refused():
    reasoner = ByRequester(
        brain_founder_obligations={
            "anchors": [
                {"anchor_id": "c1", "source_quote": "Save a verified competitive brief",
                 "meaning": "The brief exists and readback matches",
                 "depends_on": []},
                {"anchor_id": "c2", "source_quote": "on my Desktop",
                 "meaning": "Also post the brief to Slack", "depends_on": []},
            ],
        },
        brain_founder_obligation_audit={
            "regions": [{"region_index": 1,
                         "disposition": "represented_by_anchor",
                         "anchor_id": "c1"}],
            "anchors": [{"anchor_id": "c1", "entailed": True},
                        {"anchor_id": "c2", "entailed": True}],
            "omissions": [], "collapses": [],
            "invented": [{"anchor_id": "c2",
                          "reason": "the Founder never mentioned Slack"}],
            "valid": True,
        },
    )

    admission, requirements = admit(BRIEF, reasoner)

    assert requirements == ()
    assert admission["valid"] is False


def test_an_ungrounded_anchor_quote_is_refused_before_any_audit_verdict():
    reasoner = ByRequester(
        brain_founder_obligations={
            "anchors": [{"anchor_id": "d1",
                         "source_quote": "email the whole team immediately",
                         "meaning": "Email the team", "depends_on": []}],
        },
        brain_founder_obligation_audit={
            "regions": [{"region_index": 1,
                         "disposition": "represented_by_anchor",
                         "anchor_id": "d1"}],
            "anchors": [{"anchor_id": "d1", "entailed": True}],
            "omissions": [], "collapses": [], "invented": [], "valid": True,
        },
    )

    admission, requirements = admit(BRIEF, reasoner)

    assert requirements == ()
    assert admission["valid"] is False


def test_a_bounded_correction_is_attempted_exactly_once():
    """One repair of the obligation set, then the meaning is unsettled."""
    reasoner = ByRequester(
        brain_founder_obligations={
            "anchors": [{"anchor_id": "e1", "source_quote": "give me the top 3",
                         "meaning": "top three", "depends_on": []}],
        },
        brain_founder_obligation_correction={
            "anchors": [{"anchor_id": "e1", "source_quote": "give me the top 3",
                         "meaning": "top three", "depends_on": []}],
        },
        brain_founder_obligation_audit={
            "regions": [{"region_index": 2,
                         "disposition": "represented_by_anchor",
                         "anchor_id": "e1"}],
            "anchors": [{"anchor_id": "e1", "entailed": True}],
            "omissions": [], "collapses": [], "invented": [], "valid": True,
        },
    )

    admission, requirements = admit(LANDSCAPE, reasoner)

    assert requirements == ()
    assert admission["semantic_verdict"] == "unsettled_interpretation"
    assert admission["obligation_correction_attempted"] is True
    # Exactly one correction, and exactly one re-audit after it.
    assert len(reasoner.seen["brain_founder_obligation_correction"]) == 1
    assert len(reasoner.seen["brain_founder_obligation_audit"]) == 2
    # The failed first attempt is preserved, not rewritten away.
    assert admission["initial_obligation_anchors"]
