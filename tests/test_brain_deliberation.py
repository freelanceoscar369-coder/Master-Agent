"""Judgement, tested as judgement rather than as plumbing.

Every case here is a way a plausible-looking decision is wrong: a
candidate promoted on a criterion nobody established, a contradiction
laundered into a confident sentence, research that never stops, research
that stops too early, or a trivial request that summons a model it did
not need.

None of these need a provider to test, because none of them need a
provider to get right. That is the design (ADR-0027): framing and
synthesis are reasoning, but whether a candidate cleared its mandatory
criteria is arithmetic, and a model asked to grade that would be a model
grading a model.
"""
from __future__ import annotations

import pytest

from master_agent.brain.deliberation import (
    CONFLICT,
    CORROBORATION,
    CRITICAL,
    DELIBERATIVE,
    DIRECT,
    DISCOVERY,
    FACT,
    MET,
    PRIMARY,
    REASONED,
    UNMET,
    UNVERIFIED,
    UTILITY_GROUNDS,
    Candidate,
    Criterion,
    DecisionFrame,
    EvidenceAssessment,
    adjudicate,
    depth_for,
    serves,
    shortlist,
    sufficient,
)

# The founder's own failed objective, as a frame.
IS_ARPG = Criterion("c1", "is an action RPG", requirement_id="req_1")
IN_2026 = Criterion("c2", "released in 2026", requirement_id="req_1")
HAS_DEMO = Criterion("c3", "a demo actually exists", requirement_id="req_2")
IS_FREE = Criterion("c4", "the demo is free", requirement_id="req_2")

FRAME = DecisionFrame(
    objective="search for action rpg games released in 2026 and give me "
              "free demo download links",
    requirement_ids=("req_1", "req_2"),
    decision_type="research_shortlist",
    mandatory=(IS_ARPG, IN_2026, HAS_DEMO, IS_FREE),
)

ALL_MET = {"c1": MET, "c2": MET, "c3": MET, "c4": MET}


def candidate(cid, **overrides):
    states = dict(ALL_MET)
    states.update(overrides)
    return Candidate(candidate_id=cid, summary=f"game {cid}", criteria=states)


# =====================================================================
# Trivial work must not think expensively
# =====================================================================


class TestIntelligenceOnlyWhenMaterial:
    def test_a_deterministic_capability_never_deliberates(self):
        """"More intelligence" must not mean "AI everywhere". Creating a
        folder is a fact and an action, and a founder pays for every
        model call in latency they can feel."""
        assert depth_for(capability_is_deterministic=True) == DIRECT

    def test_a_deterministic_capability_stays_direct_under_pressure(self):
        """Even where the surrounding mission is complicated. The
        capability decides this, not the mood of the mission."""
        assert depth_for(
            capability_is_deterministic=True,
            evidence_items=9, alternatives=5, has_conflict=True,
        ) == DIRECT

    def test_one_simple_synthesis_is_reasoned_not_deliberative(self):
        assert depth_for(evidence_items=1) == REASONED

    def test_several_evidence_items_earn_deliberation(self):
        assert depth_for(evidence_items=5) == DELIBERATIVE

    def test_disagreement_earns_deliberation_on_its_own(self):
        assert depth_for(evidence_items=1, has_conflict=True) == DELIBERATIVE

    def test_real_alternatives_earn_deliberation(self):
        assert depth_for(alternatives=3) == DELIBERATIVE

    def test_irreversible_work_is_critical(self):
        assert depth_for(reversible=False) == CRITICAL

    def test_material_uncertainty_is_critical(self):
        assert depth_for(material_uncertainty=True) == CRITICAL


# =====================================================================
# Decision utility -- the anti-drift gate
# =====================================================================


class TestEveryActionMustServeARequirement:
    def test_an_action_serving_a_requirement_is_useful(self):
        assert serves("obtains_evidence", "req_2") is True

    def test_an_action_serving_no_requirement_is_not(self):
        """"While I am here, let me also collect..." is how a research
        mission spends a budget and answers nothing."""
        assert serves("obtains_evidence", "") is False

    def test_an_invented_ground_is_not_useful(self):
        assert serves("looks_interesting", "req_1") is False

    def test_the_grounds_are_closed(self):
        assert set(UTILITY_GROUNDS) == {
            "satisfies", "obtains_evidence", "reduces_uncertainty",
            "resolves_contradiction", "reduces_risk", "unblocks",
        }


# =====================================================================
# Shortlist discipline
# =====================================================================


class TestOnlyQualifyingCandidatesAreShortlisted:
    def test_a_fully_qualifying_candidate_is_shortlisted(self):
        selected, rejected = shortlist([candidate("a")], FRAME)
        assert [c.candidate_id for c in selected] == ["a"]
        assert rejected == ()

    def test_a_failed_mandatory_criterion_disqualifies(self):
        selected, rejected = shortlist([candidate("b", c4=UNMET)], FRAME)
        assert selected == ()
        assert rejected[0].failed == ("c4",)
        assert "not met" in rejected[0].reason

    def test_an_unestablished_criterion_is_not_rounded_up(self):
        """The important one. A candidate whose demo nobody could confirm
        is not a candidate with a demo -- and silently promoting it is
        how a founder ends up with a dead link."""
        selected, rejected = shortlist([candidate("c", c3=UNVERIFIED)], FRAME)
        assert selected == ()
        assert rejected[0].unverified == ("c3",)
        assert "could not be established" in rejected[0].reason

    def test_a_missing_criterion_state_is_treated_as_unverified(self):
        """Absence of an answer is not an answer. A candidate that was
        never assessed against a criterion must not pass it by
        omission."""
        thin = Candidate("d", "game d", criteria={"c1": MET, "c2": MET})
        selected, rejected = shortlist([thin], FRAME)
        assert selected == ()
        assert set(rejected[0].unverified) == {"c3", "c4"}

    def test_failed_and_unestablished_are_reported_differently(self):
        """"This failed" and "we could not establish this" are different
        things to tell a founder, and only the second is worth more
        research."""
        _selected, rejected = shortlist(
            [candidate("e", c4=UNMET), candidate("f", c3=UNVERIFIED)], FRAME
        )
        reasons = {r.candidate_id: r.reason for r in rejected}
        assert reasons["e"] != reasons["f"]

    def test_a_preference_cannot_rescue_a_disqualified_candidate(self):
        """Preferences order survivors. They do not resurrect."""
        framed = DecisionFrame(
            objective=FRAME.objective, requirement_ids=("req_1",),
            mandatory=(IS_ARPG, HAS_DEMO),
            preferences=(Criterion("p1", "well reviewed", mandatory=False),),
        )
        loser = Candidate("g", "beloved but no demo",
                          criteria={"c1": MET, "c3": UNMET, "p1": MET})
        selected, rejected = shortlist([loser], framed)
        assert selected == ()
        assert rejected[0].failed == ("c3",)

    def test_the_shortlist_preserves_only_survivors_out_of_a_mixed_field(self):
        field = [candidate("ok1"), candidate("bad", c1=UNMET),
                 candidate("unsure", c2=UNVERIFIED), candidate("ok2")]
        selected, rejected = shortlist(field, FRAME)
        assert [c.candidate_id for c in selected] == ["ok1", "ok2"]
        assert {r.candidate_id for r in rejected} == {"bad", "unsure"}


# =====================================================================
# Contradiction
# =====================================================================


class TestConflictingEvidence:
    def test_a_primary_source_resolves_a_disagreement(self):
        settled = adjudicate([
            EvidenceAssessment("release date is 2026", ("e1",),
                               source_class=DISCOVERY, state=FACT),
            EvidenceAssessment("release date is 2026", ("e2",),
                               source_class=PRIMARY, state=FACT),
        ])
        assert len(settled) == 1
        assert settled[0].source_class == PRIMARY
        assert settled[0].state == FACT
        assert "primary source settled" in settled[0].note

    def test_two_non_primary_sources_leave_the_conflict_standing(self):
        """Not averaged, not first-wins, not nicest-wording. Those are
        the three ways a system launders a contradiction into a
        confident sentence."""
        settled = adjudicate([
            EvidenceAssessment("a demo exists", ("e1",),
                               source_class=DISCOVERY, state=FACT),
            EvidenceAssessment("a demo exists", ("e2",),
                               source_class=CORROBORATION, state=FACT),
        ])
        assert settled[0].state == CONFLICT
        assert "no primary source resolves it" in settled[0].note
        assert set(settled[0].evidence_ids) == {"e1", "e2"}

    def test_two_primary_sources_disagreeing_stays_contested(self):
        """Authority does not break a tie with itself."""
        settled = adjudicate([
            EvidenceAssessment("the demo is free", ("e1",), source_class=PRIMARY),
            EvidenceAssessment("the demo is free", ("e2",), source_class=PRIMARY),
        ])
        assert settled[0].state == CONFLICT

    def test_an_uncontested_claim_passes_through_untouched(self):
        one = EvidenceAssessment("a demo exists", ("e1",),
                                 source_class=PRIMARY, state=FACT)
        assert adjudicate([one]) == (one,)


# =====================================================================
# Stop or keep going
# =====================================================================


class TestResearchSufficiency:
    def test_it_stops_when_a_candidate_is_fully_established(self):
        stop, why = sufficient(FRAME, [candidate("a")])
        assert stop is True
        assert "established" in why

    def test_it_continues_while_a_mandatory_criterion_is_unestablished(self):
        stop, why = sufficient(FRAME, [candidate("a", c3=UNVERIFIED)])
        assert stop is False
        assert "unestablished" in why

    def test_it_continues_while_credible_sources_disagree(self):
        stop, why = sufficient(
            FRAME, [candidate("a")],
            [EvidenceAssessment("the demo is free", ("e1",), state=CONFLICT)],
        )
        assert stop is False
        assert "disagree" in why

    def test_it_does_not_browse_forever_when_nothing_can_qualify(self):
        """Every candidate definitively fails. More searching of the same
        kind will not change that, and saying so is the useful answer."""
        stop, why = sufficient(FRAME, [candidate("a", c1=UNMET)])
        assert stop is True
        assert "no candidate" in why

    def test_it_continues_when_nothing_has_been_found_at_all(self):
        stop, why = sufficient(FRAME, [])
        assert stop is False
        assert "nothing has been found" in why

    def test_a_budget_stop_is_reported_as_a_budget_stop(self):
        """Stopping because the money ran out is a different answer to
        stopping because the question is settled, and the founder is
        owed the difference."""
        stop, why = sufficient(
            FRAME, [candidate("a", c3=UNVERIFIED)], budget_exhausted=True
        )
        assert stop is True
        assert "budget" in why
        assert "unknowns remain" in why


# =====================================================================
# Boundaries this module must never cross
# =====================================================================


class TestTheBrainKeepsItsHandsOff:
    def test_it_touches_no_environment_and_names_no_provider(self):
        import inspect

        from master_agent.brain import deliberation

        source = inspect.getsource(deliberation).lower()
        for forbidden in ("playwright", "subprocess", "requests.", "open(",
                          "webbrowser", "pathlib"):
            assert forbidden not in source, forbidden
        for provider in ("gemini", "openrouter", "chatgpt", "ollama",
                         "claude", "perplexity", "kimi"):
            assert provider not in source, provider

    def test_the_discipline_asks_no_model(self):
        """Deciding whether a candidate cleared its criteria is
        arithmetic. A model asked to grade it would be a model grading a
        model, which ADR-0011 exists to prevent."""
        import inspect

        from master_agent.brain import deliberation

        source = inspect.getsource(deliberation).lower()
        for forbidden in ("runner.run", "budgetedselection", "routingcontext",
                          "prompt ="):
            assert forbidden not in source, forbidden

    def test_it_produces_no_verdict_and_no_evidence(self):
        """Reasoning says "option A appears strongest". Verification says
        "reality matched, or did not". A codebase that spells them the
        same way will eventually treat them the same way."""
        import inspect

        from master_agent.brain import deliberation

        source = inspect.getsource(deliberation)
        assert "matched" not in source.lower().replace("not_matched", "")
        assert "class Verdict" not in source
