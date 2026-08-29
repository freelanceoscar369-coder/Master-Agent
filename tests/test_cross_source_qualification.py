"""One criterion from one source, another from another, same candidate.

This is the shape the demo centrepiece is built on and the shape that
was intermittent: a candidate qualifies only by combining two
independent Evidence records, while its rivals are each ruled out by a
single record.

    E1  Candidate A accepts laptops        Candidate B accepts laptops
                                           Candidate C does not
    E2  Candidate A opens Saturday         Candidate B does not
                                           Candidate C opens Saturday

    -> A qualifies. B and C are rejected, for different reasons.

**No requirement that one Evidence item prove a whole candidate.** That
is the point: cross-source truth is truth.

Deterministic. The model's only job -- reading prose into structure --
is played by a stub here, so what is under test is the arithmetic that
follows it: adjudication, sufficiency, and the shortlist. Model variance
cannot hide a missing semantic rule, because there is no model.
"""
from __future__ import annotations

import json
import types

from master_agent.brain.deliberation import (
    DECIDED,
    MET,
    PRIMARY,
    UNMET,
    Criterion,
    DecisionFrame,
    Observation,
    candidates_from,
    deliberate,
)

LAPTOPS = Criterion("crit_1", "the workshop accepts laptops", requirement_id="req_1")
SATURDAY = Criterion("crit_2", "the workshop is open on Saturday", requirement_id="req_2")

FRAME = DecisionFrame(
    objective="which workshops accept laptops and are open on Saturday",
    requirement_ids=("req_1", "req_2"),
    decision_type="research_shortlist",
    mandatory=(LAPTOPS, SATURDAY),
)

#: What each source says. Neither can answer the objective alone.
ACCEPTS = Observation(
    "ev-directory",
    "Ashcombe Repair Workshop - accepts laptops and phones\n"
    "Brindle Repair Workshop - accepts laptops and bicycles\n"
    "Calder Repair Workshop - bicycles only, no electronics",
    source_class=PRIMARY,
    url="http://x.test/directory.html",
)
HOURS = Observation(
    "ev-weekend",
    "Ashcombe Repair Workshop - open Saturday 10:00-16:00\n"
    "Brindle Repair Workshop - closed at weekends\n"
    "Calder Repair Workshop - open Saturday 09:00-13:00",
    source_class=PRIMARY,
    url="http://x.test/weekend.html",
)

#: The structure a correct reading produces, with each criterion citing
#: the source that actually shows it -- `source_1` and `source_2` are the
#: labels the prompt hands out, and the Brain maps them back.
READING = {
    "candidates": [
        {"id": "c1", "summary": "Ashcombe Repair Workshop", "criteria": {
            "crit_1": {"state": "met", "evidence_id": "source_1"},
            "crit_2": {"state": "met", "evidence_id": "source_2"}}},
        {"id": "c2", "summary": "Brindle Repair Workshop", "criteria": {
            "crit_1": {"state": "met", "evidence_id": "source_1"},
            "crit_2": {"state": "unmet", "evidence_id": "source_2"}}},
        {"id": "c3", "summary": "Calder Repair Workshop", "criteria": {
            "crit_1": {"state": "unmet", "evidence_id": "source_1"},
            "crit_2": {"state": "met", "evidence_id": "source_2"}}},
    ]
}


class Reading:
    """A stub that reads the two pages exactly as they read."""

    def __init__(self, document=None):
        self.document = document if document is not None else READING
        self.prompts: list[str] = []

    def run(self, prompt, request=None):
        self.prompts.append(prompt)
        return types.SimpleNamespace(ok=True, text=json.dumps(self.document))


class TestCrossSourceQualification:
    def test_the_candidate_that_needs_both_sources_qualifies(self):
        result = deliberate(FRAME, (ACCEPTS, HOURS), Reading())

        assert [c.summary for c in result.shortlist] == ["Ashcombe Repair Workshop"]
        assert result.state == DECIDED

    def test_the_rivals_are_rejected_for_their_own_reasons(self):
        result = deliberate(FRAME, (ACCEPTS, HOURS), Reading())

        rejected = {r.summary: r for r in result.rejected}
        assert set(rejected) == {"Brindle Repair Workshop", "Calder Repair Workshop"}
        assert rejected["Brindle Repair Workshop"].failed == ("crit_2",)
        assert rejected["Calder Repair Workshop"].failed == ("crit_1",)

    def test_no_single_source_has_to_prove_a_whole_candidate(self):
        """The rule, stated as an assertion: one criterion established by
        one Evidence record and another by a different one is enough."""
        built = candidates_from(FRAME, (ACCEPTS, HOURS), Reading())

        ashcombe = next(c for c in built if c.summary.startswith("Ashcombe"))
        assert ashcombe.criteria["crit_1"] == MET
        assert ashcombe.criteria["crit_2"] == MET
        assert set(ashcombe.supporting) == {"ev-directory", "ev-weekend"}

    def test_each_citation_resolves_to_the_record_it_names(self):
        built = candidates_from(FRAME, (ACCEPTS, HOURS), Reading())

        brindle = next(c for c in built if c.summary.startswith("Brindle"))
        assert brindle.criteria["crit_2"] == UNMET
        assert "ev-weekend" in brindle.supporting

    def test_a_claim_citing_no_supplied_source_is_still_refused(self):
        """The provenance guard is not relaxed by any of this."""
        from master_agent.brain.deliberation import UNVERIFIED

        invented = {"candidates": [{
            "id": "c1", "summary": "Ashcombe Repair Workshop", "criteria": {
                "crit_1": {"state": "met", "evidence_id": "source_9"},
                "crit_2": {"state": "met", "evidence_id": ""}}}]}

        built = candidates_from(FRAME, (ACCEPTS, HOURS), Reading(invented))

        assert built[0].criteria["crit_1"] == UNVERIFIED
        assert built[0].criteria["crit_2"] == UNVERIFIED
        assert built[0].supporting == ()

    def test_it_is_stable_across_repeated_runs(self):
        """The centrepiece failed four times in five on identical pages.
        Nothing about this arithmetic may vary run to run."""
        for _ in range(20):
            result = deliberate(FRAME, (ACCEPTS, HOURS), Reading())
            assert [c.summary for c in result.shortlist] == [
                "Ashcombe Repair Workshop"]

    def test_both_sources_reach_the_reading_in_one_prompt(self):
        """Reading each source alone was tried and measured worse: the
        model turns cautious about facts it can plainly see. One prompt,
        both sources, short citable labels."""
        reader = Reading()
        candidates_from(FRAME, (ACCEPTS, HOURS), reader)

        assert len(reader.prompts) == 1
        assert "[source_1]" in reader.prompts[0]
        assert "[source_2]" in reader.prompts[0]
        assert "closed at weekends" in reader.prompts[0]
        assert "bicycles only" in reader.prompts[0]


class TestOnlyCandidatePropertiesAreCriteria:
    """The root cause of the intermittency, asserted at the frame.

    The live centrepiece frame carried four mandatory criteria: the two
    real questions, the answer SET restated as a deliverable, and "Source
    must be <url>". No workshop can BE a list, and no workshop can BE a
    source -- but `shortlist()` required every mandatory criterion to be
    met, so qualifying depended on how a model happened to mark two
    criteria that mean nothing about a candidate.
    """

    def _requirements(self):
        from master_agent.planner.plan import (
            CONSTRAINT, DELIVERABLE, EFFECT, INFORMATION, SemanticRequirement,
        )

        return (
            SemanticRequirement("req_1", DELIVERABLE,
                                "List of workshops that accept laptops and "
                                "are open on Saturday"),
            SemanticRequirement("req_2", INFORMATION,
                                "the workshop accepts laptops"),
            SemanticRequirement("req_3", INFORMATION,
                                "the workshop is open on Saturday"),
            SemanticRequirement("req_4", CONSTRAINT,
                                "Source must be http://x.test/directory.html"),
            SemanticRequirement("req_5", EFFECT, "open a browser session"),
        )

    def test_the_frame_asks_only_what_a_candidate_can_answer(self):
        from master_agent.brain.deliberation import frame_for

        frame = frame_for(objective="which workshops",
                          requirements=self._requirements())

        assert [c.requirement_id for c in frame.mandatory] == ["req_2", "req_3"]

    def test_the_dropped_requirements_are_not_lost_only_relocated(self):
        """They remain requirements of the MISSION. Conformance judges
        them at mission level, which is where a source constraint and a
        deliverable were always judged."""
        from master_agent.brain.deliberation import frame_for

        frame = frame_for(objective="which workshops",
                          requirements=self._requirements())

        assert "req_4" not in frame.requirement_ids
        assert "req_1" not in frame.requirement_ids
