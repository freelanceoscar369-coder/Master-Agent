"""Stage 1E: downstream refines trusted meaning, it does not re-derive it.

Live Probe #4 (2026-09-02, 3791206) established ten independently
stateful Founder obligations -- no correction, no fusion, no omission --
and then handed requirement decomposition the raw sentence alone. With
only a sentence it did what anyone would: it read the sentence again, and
produced five requirements, re-fusing the top-three selection with all
five comparison dimensions Stage 1 had just separated.

The captured payloads in tests/fixtures/probe4_*.json are verbatim.

The second half of this file guards the Founder clarification path: the
system may ask the Founder for judgement it genuinely cannot supply, and
must never ask because its own machinery misbehaved.
"""
from __future__ import annotations

import json
import pathlib
from types import SimpleNamespace

from master_agent.brain.intent import IntentLayer
from master_agent.planner.plan import Intent

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


TRUSTED = captured("probe4_trusted_anchors")


# ---------------------------------------------------------------------
# Gate 1 - the captured failure, and Gate 2 - the handoff
# ---------------------------------------------------------------------


def test_probe_4_left_the_decomposition_blind():
    """The captured live prompt carried no obligations at all."""
    prompt = (FIXTURES / "probe4_decomposition_prompt.txt").read_text(
        encoding="utf-8")

    assert "anchor_id" not in prompt
    assert "TRUSTED FOUNDER OBLIGATIONS" not in prompt
    # ...and it produced five rows for ten trusted obligations.
    assert len(captured("probe4_decomposition")["requirements"]) == 5
    assert len(TRUSTED) == 10


def test_the_decomposition_now_receives_the_trusted_obligations():
    prompt = IntentLayer._requirement_decomposition_prompt(
        FOUNDER_INPUT, TRUSTED)

    assert "TRUSTED FOUNDER OBLIGATIONS" in prompt
    for anchor in TRUSTED:
        assert anchor["anchor_id"] in prompt
    assert "Do not merge them" in prompt
    assert "Do not omit them" in prompt
    assert "Do not reinterpret the original request" in prompt


def test_the_raw_founder_objective_remains_present_as_provenance():
    prompt = IntentLayer._requirement_decomposition_prompt(
        FOUNDER_INPUT, TRUSTED)

    assert "Kalpavriksha_Competitive_Brief.md" in prompt
    assert "The founder said:" in prompt
    # ...but it does not outrank what was established.
    assert "the trusted obligations are what was established" in prompt


def test_without_a_trusted_set_the_prompt_is_unchanged():
    """The obligation-free path -- offline and deterministic pipelines --
    keeps exactly the contract it had."""
    prompt = IntentLayer._requirement_decomposition_prompt(FOUNDER_INPUT)

    assert "TRUSTED FOUNDER OBLIGATIONS" not in prompt
    assert "The founder said:" in prompt


def test_one_obligation_may_still_become_several_requirements():
    prompt = IntentLayer._requirement_decomposition_prompt(
        FOUNDER_INPUT, TRUSTED)

    assert "several MORE PRECISE requirements" in prompt
    # but never the reverse
    assert "never become part of a requirement that also carries another" in prompt


# ---------------------------------------------------------------------
# Gate 6 - the Founder clarification path
# ---------------------------------------------------------------------

AMBIGUOUS = "Create Finance on my Desktop"


def test_a_genuine_ambiguity_asks_the_founder():
    """Two materially different interpretations remain and only the
    Founder can choose between them."""
    layer = IntentLayer()

    result = layer.parse(AMBIGUOUS)

    assert result.needs_clarification is True
    assert result.clarification is not None
    assert "folder or a file" in result.clarification.question
    assert result.clarification.options
    # The Founder's own words are kept intact while the question is open.
    assert result.raw_input == AMBIGUOUS
    # Nothing downstream was reached.
    assert result.intent is None


def test_the_founder_answer_never_replaces_the_original_request():
    """The answer settles a field; it does not become the request.

    On the TYPED path the goal is normalised to the capability command --
    which is what the typed parser always does, clarification or not --
    so the Founder's words are carried on IntentResult.raw_input and on
    each requirement's provenance rather than in the goal string.

    Recorded, not asserted away: `Intent.context` has no `raw_input` key
    on this path, so a consumer reading only the Intent would not see the
    original sentence. The compound path does set it. That asymmetry is
    a real observability gap for whatever consumes Intent next.
    """
    layer = IntentLayer()

    asked = layer.parse(AMBIGUOUS)
    answered = layer.parse(
        AMBIGUOUS, supplied={asked.clarification.key: "folder"},
    )

    assert answered.needs_clarification is False
    intent = answered.intent
    assert intent is not None

    # ORIGINAL REQUEST PRESERVED -- authoritative, on the result.
    assert answered.raw_input == AMBIGUOUS

    # The answer settled the KIND; it did not replace the request with
    # itself. "folder" alone is not the goal.
    assert intent.goal.strip().casefold() != "folder"
    assert "Finance" in intent.goal

    # The gap, stated as a fact rather than a hope.
    assert intent.context.get("raw_input") is None


def test_the_clarification_answer_is_preserved_as_evidence():
    layer = IntentLayer()

    asked = layer.parse(AMBIGUOUS)
    answered = layer.parse(
        AMBIGUOUS, supplied={asked.clarification.key: "folder"},
    )

    settled = " ".join([
        answered.intent.goal,
        json.dumps(answered.intent.context, default=str),
        json.dumps(answered.resolved, default=str),
    ]).casefold()
    assert "folder" in settled


# ---------------------------------------------------------------------
# Gate 6 - and it must NOT ask when the fault is Kalpavriksha's own
# ---------------------------------------------------------------------

ROWS = [
    {"kind": "information", "description": "Establish the relevant products",
     "candidate_property": False,
     "source_quote": "Research the current AI-agent products",
     "success_meaning": "the relevant product landscape is established"},
    {"kind": "information", "description": "Establish the top-three set",
     "candidate_property": False, "source_quote": "give me the top 3",
     "success_meaning": "exactly three qualified candidates form the set"},
]

SMALL_OBJECTIVE = (
    "Research the current AI-agent products and give me the top 3."
)

SMALL_ANCHORS = [
    {"anchor_id": "anchor_1",
     "source_quote": "Research the current AI-agent products",
     "meaning": "the relevant product landscape is established",
     "depends_on": []},
    {"anchor_id": "anchor_2", "source_quote": "give me the top 3",
     "meaning": "the selected top-three set", "depends_on": ["anchor_1"]},
]

SMALL_AUDIT = {
    "regions": [
        {"region_index": index, "disposition": "represented_by_anchor",
         "anchor_id": "anchor_1"} for index in (1, 2)
    ],
    "anchors": [{"anchor_id": "anchor_1", "entailed": True},
                {"anchor_id": "anchor_2", "entailed": True}],
    "state_candidates": [
        {"candidate_index": 1, "relationship": "independent_outcome",
         "anchor_id": "anchor_1"},
        {"candidate_index": 2, "relationship": "independent_outcome",
         "anchor_id": "anchor_2"},
    ],
    "omissions": [], "collapses": [], "invented": [], "valid": True,
}

BROKEN_REVIEW = {"valid": True, "independently_verifiable": True,
                 "coverage": "not even a list", "invented": []}

GOOD_REVIEW = {
    "valid": True, "independently_verifiable": True,
    "coverage": [
        {"anchor_id": "anchor_1", "requirement_indices": [1],
         "independently_trackable": True},
        {"anchor_id": "anchor_2", "requirement_indices": [2],
         "independently_trackable": True},
    ],
    "invented": [],
}


class ByRequester:
    def __init__(self, **documents):
        self.documents = documents
        self.seen: dict[str, list[str]] = {}

    def run(self, prompt, request=None):
        name = getattr(request, "requester", "")
        turn = len(self.seen.setdefault(name, [])) + 1
        self.seen[name].append(prompt)
        document = self.documents.get(name)
        if document is None:
            return SimpleNamespace(ok=False, text="")
        if callable(document):
            document = document(turn)
        return SimpleNamespace(ok=True, text=json.dumps(document))


def test_a_malformed_semantic_review_is_repaired_not_escalated():
    """Kalpavriksha's own representation fault is Kalpavriksha's problem."""
    reasoner = ByRequester(
        brain_founder_obligations={"anchors": SMALL_ANCHORS},
        brain_founder_obligation_audit=SMALL_AUDIT,
        brain_semantic_requirements={"requirements": ROWS},
        brain_semantic_requirement_validation=BROKEN_REVIEW,
        brain_semantic_review_correction=GOOD_REVIEW,
    )
    layer = IntentLayer.__new__(IntentLayer)
    layer._reasoner = reasoner
    canonical = Intent(goal=SMALL_OBJECTIVE,
                       context={"raw_input": SMALL_OBJECTIVE})

    requirements = layer.requirements_for(canonical, raw=SMALL_OBJECTIVE)
    admission = canonical.context["requirement_admission"]

    # It repaired its own review and carried on.
    assert len(reasoner.seen["brain_semantic_review_correction"]) == 1
    assert admission["valid"] is True
    assert len(requirements) == 2
    # And it never turned its own defect into a Founder question.
    assert "clarification" not in json.dumps(admission).casefold()


# ---------------------------------------------------------------------
# Gate 5 / Gate 7 - the whole path on the captured Probe #4 trusted set
# ---------------------------------------------------------------------

#: One requirement per trusted obligation, built from the obligations
#: themselves -- which is what a decomposition that can SEE them returns.
PROBE4_ROWS = [
    {"kind": ("constraint" if "evidence" in str(a["meaning"]).casefold()
              else "deliverable" if "save" in str(a["meaning"]).casefold()
              else "information"),
     "description": str(a["meaning"]),
     "candidate_property": "compare the top 3 products across" in str(
         a["meaning"]).casefold(),
     "source_quote": str(a["source_quote"]).strip(" ,"),
     "success_meaning": str(a["meaning"])}
    for a in TRUSTED
]

PROBE4_REVIEW = {
    "valid": True, "independently_verifiable": True,
    "coverage": [
        {"anchor_id": a["anchor_id"], "requirement_indices": [index],
         "independently_trackable": True}
        for index, a in enumerate(TRUSTED, start=1)
    ],
    "invented": [],
}

PROBE4_AUDIT = {
    "regions": [
        {"region_index": index, "disposition": "represented_by_anchor",
         "anchor_id": "anchor_1"} for index in range(1, 5)
    ],
    "anchors": [{"anchor_id": a["anchor_id"], "entailed": True,
                 "contains_multiple_states": False} for a in TRUSTED],
    "state_candidates": [
        {"candidate_index": index, "relationship": (
            "constraint_unit" if index == 8 else "independent_outcome"),
         "anchor_id": TRUSTED[index - 1]["anchor_id"]}
        for index in range(1, 11)
    ],
    "omissions": [], "collapses": [], "invented": [], "valid": True,
}


def test_the_probe_4_trusted_set_now_becomes_canonical_intent():
    reasoner = ByRequester(
        brain_founder_obligations={"anchors": TRUSTED},
        brain_founder_obligation_audit=PROBE4_AUDIT,
        brain_semantic_requirements={"requirements": PROBE4_ROWS},
        brain_semantic_requirement_validation=PROBE4_REVIEW,
    )
    layer = IntentLayer.__new__(IntentLayer)
    layer._reasoner = reasoner
    canonical = Intent(goal=FOUNDER_INPUT, context={"raw_input": FOUNDER_INPUT})

    requirements = layer.requirements_for(canonical, raw=FOUNDER_INPUT)
    admission = canonical.context["requirement_admission"]

    assert admission["valid"] is True, admission["structural_issues"]
    assert admission["obligation_correction_attempted"] is False
    assert admission["unmapped_anchors"] == []
    assert admission["improper_merges"] == []
    assert admission["invented_requirements"] == []

    # The decomposition was shown the obligations, not left to re-read
    # the sentence.
    decomposition = reasoner.seen["brain_semantic_requirements"][0]
    assert "TRUSTED FOUNDER OBLIGATIONS" in decomposition
    assert "anchor_10" in decomposition

    # Each Founder state independently representable. The invariant is
    # structural, not lexical: every trusted obligation owns its own
    # requirement index, so any one can be SATISFIED while its neighbour
    # stays UNRESOLVED. (Counting keywords would fail here for an honest
    # reason -- the deliverable's own wording mentions the threat
    # assessment it contains.)
    coverage = {row["anchor_id"]: tuple(row["requirement_indices"])
                for row in admission["coverage_mapping"]}
    assert set(coverage) == {a["anchor_id"] for a in TRUSTED}
    assert all(indices for indices in coverage.values())

    owned = [index for indices in coverage.values() for index in indices]
    assert len(owned) == len(set(owned)), "two obligations share a requirement"

    for left, right in (
        ("anchor_1", "anchor_2"),    # landscape / top-three
        ("anchor_2", "anchor_3"),    # top-three / pricing
        ("anchor_3", "anchor_4"),    # pricing / browser use
        ("anchor_9", "anchor_8"),    # threat decision / sufficient evidence
    ):
        assert set(coverage[left]).isdisjoint(coverage[right])

    assert len(requirements) == len(TRUSTED)
