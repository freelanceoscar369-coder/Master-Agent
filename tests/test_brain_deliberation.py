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
        model, which ADR-0011 exists to prevent.

        Asserted function by function rather than over the module,
        because the module now also owns ONE reasoning door --
        `candidates_from`, which reads prose into structure and decides
        nothing. Narrowing this guard to the judgement functions is the
        point of it: extraction may ask a model, adjudication may not.
        """
        import inspect

        from master_agent.brain import deliberation

        for judgement in (deliberation.shortlist, deliberation.adjudicate,
                          deliberation.sufficient, deliberation.serves,
                          deliberation.depth_for, deliberation.frame_for,
                          deliberation.recovery_for,
                          deliberation.classify_failure):
            source = inspect.getsource(judgement).lower()
            for forbidden in ("runner.run", ".run(", "budgetedselection",
                              "routingcontext", "prompt"):
                assert forbidden not in source, (
                    f"{judgement.__name__} reaches a model for a judgement "
                    f"that is arithmetic: {forbidden}"
                )

    def test_the_one_reasoning_door_only_extracts(self):
        """`candidates_from` may read prose. It may not conclude: the
        states it returns are fed to `shortlist()`, which decides."""
        from master_agent.brain import deliberation

        # The compiled names it actually references, not its prose --
        # the docstring legitimately explains that `shortlist()` is what
        # decides, and a text search would trip over the explanation.
        called = set(deliberation.candidates_from.__code__.co_names)
        assert "shortlist" not in called
        assert "DeliberationResult" not in called
        assert "sufficient" not in called

    def test_it_produces_no_verdict_and_no_evidence(self):
        """Reasoning says "option A appears strongest". Verification says
        "reality matched, or did not". A codebase that spells them the
        same way will eventually treat them the same way.

        It may READ a verdict -- judging whether verified reality
        advanced the objective is the whole job, and `progress_of` cannot
        do it blind. What it may never do is DEFINE or MINT one.
        Asserted against the module's actual names rather than its prose,
        because `EvidenceAssessment` is a reading OF Evidence and a text
        search cannot tell the two apart.
        """
        from master_agent.brain import deliberation

        exported = set(dir(deliberation))
        assert "Verdict" not in exported
        assert "Evidence" not in exported, (
            "deliberation defines an Evidence type; Verification is the "
            "only thing that may produce Evidence (ADR-0011)"
        )
        # The reading it IS allowed to hold, named so the two cannot be
        # confused at a glance.
        assert "EvidenceAssessment" in exported


# =====================================================================
# Method failure is not objective failure
# =====================================================================


class TestRecovery:
    """The founder saw "That didn't complete." about a mission that never
    reached the web. One step failed to open a browser; the objective was
    declared failed 1.3 seconds later; nine planned steps never ran, and
    at least two of them named different sources.

    `MissionDispatcher` was right to stop -- its own comment says
    auto-retry "would be a strategic recovery decision, which belongs to
    the Brain". The seam was correct and nothing stood behind it."""

    def test_a_failed_source_with_alternatives_is_a_method_failure(self):
        from master_agent.brain.deliberation import METHOD_FAILURE, classify_failure

        assert classify_failure(
            unmet_requirements=["req_1"], alternatives_available=True
        ) == METHOD_FAILURE

    def test_only_no_safe_route_left_is_an_objective_failure(self):
        from master_agent.brain.deliberation import OBJECTIVE_FAILURE, classify_failure

        assert classify_failure(
            unmet_requirements=["req_1"], alternatives_available=False
        ) == OBJECTIVE_FAILURE

    def test_nothing_unmet_is_only_a_source_failure(self):
        """A site that would not answer, on a mission that got what it
        needed anyway, is not a failure the founder should hear about as
        one."""
        from master_agent.brain.deliberation import SOURCE_FAILURE, classify_failure

        assert classify_failure(
            unmet_requirements=[], alternatives_available=False
        ) == SOURCE_FAILURE

    def test_it_replans_while_a_requirement_is_unmet_and_a_route_remains(self):
        from master_agent.brain.deliberation import recovery_for

        decision = recovery_for(
            unmet_requirements=["req_1", "req_2"], alternatives_available=True
        )
        assert decision.should_replan is True
        assert decision.attempts_remaining == 2

    def test_it_does_not_replan_a_satisfied_objective(self):
        from master_agent.brain.deliberation import recovery_for

        decision = recovery_for(
            unmet_requirements=[], alternatives_available=True
        )
        assert decision.should_replan is False
        assert "already satisfied" in decision.reason

    def test_recovery_is_bounded(self):
        """Recovery exists to survive a bad source, not to grind. Every
        attempt is time the founder sits through."""
        from master_agent.brain.deliberation import recovery_for

        decision = recovery_for(
            unmet_requirements=["req_1"], alternatives_available=True,
            attempts_used=2, budget=2,
        )
        assert decision.should_replan is False
        assert "budget" in decision.reason
        assert decision.attempts_remaining == 0

    def test_repeating_a_failed_method_is_not_recovery(self):
        from master_agent.brain.deliberation import recovery_for

        decision = recovery_for(
            unmet_requirements=["req_1"], alternatives_available=True,
            previous_methods=["navigate steam"], proposed_method="navigate steam",
        )
        assert decision.should_replan is False
        assert "already tried" in decision.reason

    def test_a_transient_failure_may_legitimately_retry_the_same_method(self):
        """The one exception, and it has to be established from Evidence
        rather than assumed -- otherwise every failure becomes
        "transient" and the bound disappears."""
        from master_agent.brain.deliberation import recovery_for

        decision = recovery_for(
            unmet_requirements=["req_1"], alternatives_available=False,
            previous_methods=["navigate steam"], proposed_method="navigate steam",
            transient=True,
        )
        assert decision.should_replan is True

    def test_a_new_attempt_must_differ_in_something_nameable(self):
        from master_agent.brain.deliberation import DIFFERENTIATORS, recovery_for

        decision = recovery_for(
            unmet_requirements=["req_1"], alternatives_available=True
        )
        assert decision.must_differ == DIFFERENTIATORS
        assert "try again" not in DIFFERENTIATORS

    def test_exhausted_recovery_still_names_the_failure_class(self):
        """The founder is owed what kind of failure it was even when
        nothing more will be attempted."""
        from master_agent.brain.deliberation import recovery_for

        decision = recovery_for(
            unmet_requirements=["req_1"], alternatives_available=True,
            attempts_used=5, budget=2,
        )
        assert decision.failure_class in ("method_failure", "objective_failure")
        assert decision.should_replan is False


# =====================================================================
# Framing, and the asymmetry that keeps it honest
# =====================================================================


class TestFramingFromCanonicalInformationOnly:
    """A frame must not become a second semantic authority. Its criteria
    ARE the requirements the Intent Layer already derived, one for one,
    ids preserved -- so every criterion traces to a requirement and every
    requirement keeps its founder evidence."""

    def requirements(self):
        from master_agent.planner.plan import (
            DELIVERABLE, INFORMATION, SemanticRequirement,
        )

        return (
            SemanticRequirement("req_1", INFORMATION,
                                "action RPG games released in 2026",
                                founder_evidence="search for action rpg games"),
            SemanticRequirement("req_2", DELIVERABLE,
                                "free demo download links",
                                founder_evidence="search for action rpg games"),
        )

    def test_a_typed_capability_gets_no_frame(self):
        """The asymmetry. A founder asking for a folder is not facing a
        decision: the capability is known, the arguments are settled, and
        a frame would buy latency they feel for a question that was never
        in doubt."""
        from master_agent.brain.deliberation import frame_for
        from master_agent.planner.plan import EFFECT, SemanticRequirement

        assert frame_for(
            objective="create a folder called Notes on my desktop",
            requirements=(SemanticRequirement("req_1", EFFECT, "create a folder"),),
            capability="create_folder",
        ) is None

    def test_an_objective_with_no_requirements_gets_no_frame(self):
        from master_agent.brain.deliberation import frame_for

        assert frame_for(objective="hello", requirements=()) is None

    def test_a_compound_objective_is_framed(self):
        from master_agent.brain.deliberation import frame_for

        frame = frame_for(objective="research", requirements=self.requirements())
        assert frame is not None
        assert len(frame.mandatory) == 2

    def test_every_criterion_traces_to_a_requirement(self):
        from master_agent.brain.deliberation import frame_for

        frame = frame_for(objective="research", requirements=self.requirements())
        assert [c.requirement_id for c in frame.mandatory] == ["req_1", "req_2"]

    def test_it_invents_no_criteria_of_its_own(self):
        """One criterion per requirement, and nothing else. A frame that
        added its own would be reinterpreting founder meaning, which is
        exactly what ADR-0026 removed."""
        from master_agent.brain.deliberation import frame_for

        requirements = self.requirements()
        frame = frame_for(objective="research", requirements=requirements)
        assert len(frame.mandatory) == len(requirements)
        described = {c.description for c in frame.mandatory}
        assert described == {r.description for r in requirements}

    def test_explicit_mission_level_requirements_are_not_candidate_properties(self):
        """The mission still owns every requirement, but a product cannot
        itself 'save the report' or 'recommend one'.  Candidate shortlisting
        must not require it to."""
        from master_agent.brain.deliberation import frame_for
        from master_agent.planner.plan import INFORMATION, SemanticRequirement

        requirements = (
            SemanticRequirement(
                "req_1", INFORMATION, "free access/pricing",
                candidate_property=True,
            ),
            SemanticRequirement(
                "req_2", INFORMATION, "recommend one",
                candidate_property=False,
            ),
            SemanticRequirement(
                "req_3", INFORMATION, "save the verified report",
                candidate_property=False,
            ),
        )

        frame = frame_for(objective="compare products", requirements=requirements)

        assert frame.requirement_ids == ("req_1", "req_2", "req_3")
        assert [c.requirement_id for c in frame.mandatory] == ["req_1"]

    def test_every_requirement_is_kept_even_when_it_is_not_a_candidate_property(self):
        """Filtering to the requirements that ARE candidate properties was
        tried and taken back out -- see `frame_for`.

        A frame carrying "Source must be <url>" makes qualifying partly
        arbitrary, which is bad. A frame that has DROPPED the founder's
        second question is worse: it produces a confident answer to half
        the request. The Intent Layer labelled that very source line
        `information` on a live run while the Saturday question did not
        survive at all, so the filter cannot be trusted to keep the right
        ones."""
        from master_agent.brain.deliberation import frame_for
        from master_agent.planner.plan import (
            CONSTRAINT, INFORMATION, SemanticRequirement,
        )

        frame = frame_for(objective="which workshops", requirements=(
            SemanticRequirement("req_1", INFORMATION, "accepts laptops"),
            SemanticRequirement("req_2", CONSTRAINT, "open on Saturday"),
            SemanticRequirement("req_3", CONSTRAINT, "Source must be http://x/"),
        ))

        assert [c.requirement_id for c in frame.mandatory] == [
            "req_1", "req_2", "req_3"]

    def test_the_brain_and_the_planner_spell_information_the_same(self):
        from master_agent.brain import deliberation
        from master_agent.planner import plan

        assert deliberation.INFORMATION == plan.INFORMATION

    def test_framing_does_not_depend_on_a_models_choice_of_kind(self):
        """Measured twice on the same research objective, the extractor
        labelled its requirements `information` + `deliverable` on one
        run and `information` + three `constraint`s on the next. Keying
        the EXISTENCE of a frame off those labels made "does this mission
        think at all" depend on a word a model happened to choose."""
        from master_agent.brain.deliberation import frame_for
        from master_agent.planner.plan import CONSTRAINT, SemanticRequirement

        awkward = (
            SemanticRequirement("req_1", CONSTRAINT, "released in 2026"),
            SemanticRequirement("req_2", CONSTRAINT, "the demo is free"),
        )
        frame = frame_for(objective="research", requirements=awkward)
        assert frame is not None, (
            "a research mission stopped being framed because a model "
            "chose a different kind label"
        )
        assert len(frame.mandatory) == 2

    def test_it_asks_no_model(self):
        """Framing is deterministic, so it costs nothing and cannot be
        wrong about something a model guessed."""
        import inspect

        from master_agent.brain import deliberation

        source = inspect.getsource(deliberation.frame_for).lower()
        for forbidden in ("run(", "prompt", "reasoner", "provider"):
            assert forbidden not in source, forbidden

    def test_the_stop_conditions_are_stated_up_front(self):
        """Written BEFORE evidence arrives. A frame written afterwards is
        a rationalisation of whatever turned up."""
        from master_agent.brain.deliberation import frame_for

        frame = frame_for(objective="research", requirements=self.requirements())
        joined = " ".join(frame.stop_conditions)
        assert "established" in joined
        assert "disagree" in joined
        assert "budget" in joined


# =====================================================================
# The failure point: what does a stopped mission MEAN?
# =====================================================================


class TestTheSurfaceAsksTheBrainAndDecidesNothing:
    """`MissionDispatcher`'s own comment says auto-retry "would be a
    strategic recovery decision, which belongs to the Brain". The surface
    observes that a mission stopped, hands the Brain the facts, and
    relays the answer to the lifecycle authority that already exists."""

    class Task:
        def __init__(self, task_id, covers, verdict):
            self.task_id = task_id
            self.covers = covers
            self.evidence = {"verdict": verdict} if verdict else None

    class Objective:
        def __init__(self, tasks):
            self.tasks = tasks

    class Control:
        def __init__(self, tasks):
            self.dispatcher = type("D", (), {
                "objective": lambda _self, _id, _t=tasks: TestTheSurfaceAsksTheBrainAndDecidesNothing.Objective(_t)
            })()

    def intent(self):
        from master_agent.planner.plan import (
            CONSTRAINT, EFFECT, Intent, SemanticRequirement,
        )

        intent = Intent(goal="research", constraints=[], context={},
                        success_criteria=[])
        intent.requirements = (
            SemanticRequirement("req_1", EFFECT, "find the games",
                                founder_evidence="search for action rpg games"),
            SemanticRequirement("req_2", CONSTRAINT, "give demo links",
                                founder_evidence="search for action rpg games"),
        )
        return intent

    def test_a_mission_that_verified_nothing_is_worth_another_method(self):
        """The founder's exact failure: step one could not open a
        browser, and nine planned steps naming several sources never
        ran."""
        import kalpavriksha_desktop as kd

        control = self.Control([self.Task("t1", ("req_1",), "not_matched")])
        decision = kd._recovery_decision(control, self.intent(), "obj-1", 0)
        assert decision is not None
        assert decision.should_replan is True
        assert decision.failure_class == "method_failure"

    def test_recovery_is_bounded_by_the_brains_own_budget(self):
        import kalpavriksha_desktop as kd

        control = self.Control([self.Task("t1", ("req_1",), "not_matched")])
        decision = kd._recovery_decision(control, self.intent(), "obj-1", 9)
        assert decision.should_replan is False
        assert "budget" in decision.reason

    def test_partial_success_still_recovers(self):
        """A mission most of the way there is the one most worth
        finishing. This used to return `None` on any satisfied
        requirement, because a replan would have redone it -- and for a
        capability with an external effect that is a second real change
        to the founder's machine, not a wasted step. The Planner is now
        told which requirements are already satisfied and not to redo
        them, so abandoning here would waste the work instead of
        protecting it."""
        import kalpavriksha_desktop as kd

        control = self.Control([
            self.Task("t1", ("req_1",), "matched"),
            self.Task("t2", ("req_2",), "not_matched"),
        ])
        decision = kd._recovery_decision(control, self.intent(), "obj-1", 0)
        assert decision is not None
        assert decision.should_replan is True

    def test_a_mission_with_no_requirements_decides_nothing(self):
        import kalpavriksha_desktop as kd
        from master_agent.planner.plan import Intent

        bare = Intent(goal="x", constraints=[], context={}, success_criteria=[])
        control = self.Control([self.Task("t1", (), "not_matched")])
        assert kd._recovery_decision(control, bare, "obj-1", 0) is None

    def test_the_surface_holds_no_recovery_policy_of_its_own(self):
        """It must relay a decision, not make one. A threshold or a
        retry count written here would be a second recovery policy
        drifting from the Brain's."""
        import inspect

        import kalpavriksha_desktop as kd

        source = inspect.getsource(kd._recovery_decision)
        assert "recovery_for" in source
        for invented in ("range(", "< 3", "<= 3", "max_retries", "MAX_"):
            assert invented not in source, invented


# =====================================================================
# Observations become a decision, and a model cannot smuggle one in
# =====================================================================


class TestCandidateConstruction:
    """The model reads prose into structure. It decides nothing.

    Every case below is a way an attractive answer is unsupported, which
    is how a research reply turns into a dead link in a founder's hands.
    """

    OBS = None

    def observations(self):
        from master_agent.brain.deliberation import (
            CORROBORATION, DISCOVERY, PRIMARY, Observation,
        )

        return (
            Observation("ev1", "Ashen Vale is an action RPG, released 2026. "
                               "A free demo is on the official page.",
                        source_class=PRIMARY, url="https://example.invalid/a"),
            Observation("ev2", "Ashen Vale looks great", source_class=DISCOVERY),
            Observation("ev3", "Mirebound: action RPG, 2026.",
                        source_class=CORROBORATION),
        )

    def reasoner(self, payload):
        import json

        class R:
            def __init__(self, text):
                self.text = text
                self.prompts = []

            def run(self, prompt, request, **kwargs):
                self.prompts.append(prompt)
                outer = self

                class Outcome:
                    ok = True
                    text = outer.text

                return Outcome()

        return R(json.dumps(payload))

    def test_a_fully_supported_candidate_survives(self):
        from master_agent.brain.deliberation import MET, candidates_from

        reasoner = self.reasoner({"candidates": [{
            "id": "ashen", "summary": "Ashen Vale",
            "criteria": {c: {"state": "met", "evidence_id": "ev1"}
                         for c in ("c1", "c2", "c3", "c4")},
        }]})
        built = candidates_from(FRAME, self.observations(), reasoner)
        assert len(built) == 1
        assert set(built[0].criteria.values()) == {MET}
        assert built[0].supporting == ("ev1",)

    def test_a_met_with_no_evidence_is_downgraded_not_believed(self):
        """The guard that matters. "The demo is free" and "something said
        the demo is free" are different claims, and only one of them
        belongs in a founder's hands."""
        from master_agent.brain.deliberation import UNVERIFIED, candidates_from

        reasoner = self.reasoner({"candidates": [{
            "id": "ashen", "summary": "Ashen Vale",
            "criteria": {
                "c1": {"state": "met", "evidence_id": "ev1"},
                "c2": {"state": "met", "evidence_id": "ev1"},
                "c3": {"state": "met", "evidence_id": ""},
                "c4": {"state": "met", "evidence_id": "ev1"},
            },
        }]})
        built = candidates_from(FRAME, self.observations(), reasoner)
        assert built[0].criteria["c3"] == UNVERIFIED
        assert any("c3" in u for u in built[0].unknowns)

    def test_an_invented_evidence_id_is_downgraded(self):
        """Citing a reference nobody supplied is the same failure wearing
        a citation."""
        from master_agent.brain.deliberation import UNVERIFIED, candidates_from

        reasoner = self.reasoner({"candidates": [{
            "id": "ghost", "summary": "Ghostlight",
            "criteria": {c: {"state": "met", "evidence_id": "ev99"}
                         for c in ("c1", "c2", "c3", "c4")},
        }]})
        built = candidates_from(FRAME, self.observations(), reasoner)
        assert set(built[0].criteria.values()) == {UNVERIFIED}
        assert built[0].supporting == ()

    def test_a_criterion_the_model_omitted_is_unverified(self):
        """Silence is not a pass."""
        from master_agent.brain.deliberation import UNVERIFIED, candidates_from

        reasoner = self.reasoner({"candidates": [{
            "id": "ashen", "summary": "Ashen Vale",
            "criteria": {"c1": {"state": "met", "evidence_id": "ev1"}},
        }]})
        built = candidates_from(FRAME, self.observations(), reasoner)
        for criterion in ("c2", "c3", "c4"):
            assert built[0].criteria[criterion] == UNVERIFIED

    def test_an_unusable_reply_yields_no_candidates(self):
        from master_agent.brain.deliberation import candidates_from

        class Broken:
            def run(self, prompt, request, **kwargs):
                class Outcome:
                    ok = True
                    text = "I could not do that"

                return Outcome()

        assert candidates_from(FRAME, self.observations(), Broken()) == ()

    def test_a_dead_reasoner_yields_no_candidates_and_does_not_raise(self):
        from master_agent.brain.deliberation import candidates_from

        class Dead:
            def run(self, prompt, request, **kwargs):
                raise RuntimeError("no provider configured")

        assert candidates_from(FRAME, self.observations(), Dead()) == ()

    def test_no_reasoner_means_no_candidates(self):
        from master_agent.brain.deliberation import candidates_from

        assert candidates_from(FRAME, self.observations(), None) == ()

    def test_one_prompt_carries_every_source_with_a_citable_label(self):
        """One call sees everything, because the cross-source join needs
        to. Reading each source alone was tried and measured worse -- see
        `candidates_from`. The labels are what make the citation easy."""
        from master_agent.brain.deliberation import candidates_from, source_labels

        reasoner = self.reasoner({"candidates": []})
        observations = self.observations()
        candidates_from(FRAME, observations, reasoner)

        assert len(reasoner.prompts) == 1
        prompt = reasoner.prompts[0]
        for label in source_labels(observations):
            assert f"[{label}]" in prompt
        for criterion in ("c1", "c2", "c3", "c4"):
            assert criterion in prompt

    def test_a_label_cites_the_observation_it_stands_for(self):
        """One source in, one label out. `source_1` resolves to whichever
        observation that call was given."""
        from master_agent.brain.deliberation import candidates_from

        observations = self.observations()
        reasoner = self.reasoner({"candidates": [{
            "id": "cand_1", "summary": "A Thing",
            "criteria": {c.criterion_id: {"state": "met",
                                          "evidence_id": "source_2"}
                         for c in FRAME.mandatory},
        }]})

        built = candidates_from(FRAME, observations, reasoner)

        assert built and built[0].supporting == (observations[1].evidence_id,)

    def test_a_source_that_was_cut_short_says_so(self):
        """Silence about a cut is how a criterion in row 40 of a table
        becomes "unestablished" while nobody was ever shown it."""
        from master_agent.brain.deliberation import (
            MAX_OBSERVATION_CHARS,
            Observation,
            candidates_from,
        )

        long_one = Observation("ev-long", "x" * (MAX_OBSERVATION_CHARS + 500))
        reasoner = self.reasoner({"candidates": []})

        candidates_from(FRAME, (long_one,), reasoner)

        assert "cut short" in reasoner.prompts[0]

    def test_a_label_nobody_offered_is_still_a_citation_of_nothing(self):
        """The guard is unchanged. Only the thing being copied changed."""
        from master_agent.brain.deliberation import UNVERIFIED, candidates_from

        reasoner = self.reasoner({"candidates": [{
            "id": "cand_1", "summary": "A Thing",
            "criteria": {c.criterion_id: {"state": "met",
                                          "evidence_id": "source_99"}
                         for c in FRAME.mandatory},
        }]})

        built = candidates_from(FRAME, self.observations(), reasoner)

        assert built
        assert all(state == UNVERIFIED for state in built[0].criteria.values())
        assert built[0].supporting == ()

    def test_it_names_no_provider(self):
        """The Brain states what reasoning it needs. The Broker decides
        who does it (ADR-0017)."""
        import inspect

        from master_agent.brain import deliberation

        source = inspect.getsource(deliberation.candidates_from).lower()
        for provider in ("gemini", "openrouter", "chatgpt", "claude",
                         "ollama", "perplexity", "kimi"):
            assert provider not in source, provider


class TestTheWholeDecision:
    def observations(self):
        from master_agent.brain.deliberation import PRIMARY, Observation

        return (Observation("ev1", "Ashen Vale, action RPG, 2026, free demo.",
                            source_class=PRIMARY),)

    def reasoner(self, payload):
        import json

        class R:
            def run(self, prompt, request, **kwargs):
                class Outcome:
                    ok = True
                    text = json.dumps(payload)

                return Outcome()

        return R()

    def test_a_supported_candidate_produces_a_decision(self):
        from master_agent.brain.deliberation import DECIDED, deliberate

        result = deliberate(FRAME, self.observations(), self.reasoner(
            {"candidates": [{"id": "a", "summary": "Ashen Vale",
                             "criteria": {c: {"state": "met",
                                              "evidence_id": "ev1"}
                                          for c in ("c1", "c2", "c3", "c4")}}]}
        ))
        assert result.state == DECIDED
        assert [c.summary for c in result.shortlist] == ["Ashen Vale"]
        assert result.more_research is False

    def test_an_unsupported_candidate_is_rejected_and_research_continues(self):
        """No candidate qualified, and the honest answer is that the
        question is still open -- not an empty list presented as an
        answer."""
        from master_agent.brain.deliberation import (
            INSUFFICIENT_EVIDENCE, deliberate,
        )

        result = deliberate(FRAME, self.observations(), self.reasoner(
            {"candidates": [{"id": "a", "summary": "Ashen Vale",
                             "criteria": {
                                 "c1": {"state": "met", "evidence_id": "ev1"},
                                 "c2": {"state": "met", "evidence_id": "ev1"},
                                 "c3": {"state": "met", "evidence_id": ""},
                                 "c4": {"state": "met", "evidence_id": "ev1"},
                             }}]}
        ))
        assert result.state == INSUFFICIENT_EVIDENCE
        assert result.shortlist == ()
        assert result.rejected and result.rejected[0].unverified
        assert result.more_research is True

    def test_the_result_names_the_requirements_it_serves(self):
        from master_agent.brain.deliberation import deliberate

        result = deliberate(FRAME, self.observations(), self.reasoner(
            {"candidates": []}
        ))
        assert result.requirement_ids == FRAME.requirement_ids

    def test_no_observations_means_no_decision_and_more_research(self):
        from master_agent.brain.deliberation import deliberate

        result = deliberate(FRAME, (), self.reasoner({"candidates": []}))
        assert result.shortlist == ()
        assert result.more_research is True

    def test_it_stores_no_chain_of_thought(self):
        """Reviewable conclusions, evidence references and reasons. Not a
        transcript."""
        from master_agent.brain.deliberation import deliberate

        result = deliberate(FRAME, self.observations(), self.reasoner(
            {"candidates": [{"id": "a", "summary": "Ashen Vale",
                             "criteria": {c: {"state": "met",
                                              "evidence_id": "ev1"}
                                          for c in ("c1", "c2", "c3", "c4")}}]}
        ))
        stored = result.as_dict()
        blob = str(stored).lower()
        for leak in ("you are reading observations", "reply with json",
                     "rules.", "criteria. each candidate"):
            assert leak not in blob, leak


# =====================================================================
# What the first real deliberation got wrong
# =====================================================================


class TestTheOutputAFounderActuallyReads:
    """Three defects visible the first time this ran against live Steam
    evidence. All three were mine, and all three made a correct decision
    unusable."""

    def observations(self):
        from master_agent.brain.deliberation import PRIMARY, Observation

        return (Observation("ev1", "Ashen Vale - free demo, 15 Jun 2026",
                            source_class=PRIMARY),)

    def reasoner(self, payload):
        import json

        class R:
            def run(self, prompt, request, **kwargs):
                class Outcome:
                    ok = True
                    text = json.dumps(payload)

                return Outcome()

        return R()

    def test_a_summary_is_a_name_not_the_models_working(self):
        """Measured: summaries came back as "Free Steam demo listed with a
        15 Jun 2026 date. Evidence: c43598d0-...: crit_2" -- the whole of
        its reasoning, in the one field a founder reads."""
        from master_agent.brain.deliberation import candidates_from

        built = candidates_from(FRAME, self.observations(), self.reasoner(
            {"candidates": [{
                "id": "a",
                "summary": ("Free Steam demo listed with a 15 Jun 2026 date. "
                            "Evidence: c43598d0-2143-449c: crit_2"),
                "criteria": {"c1": {"state": "met", "evidence_id": "ev1"}},
            }]}
        ))
        assert built[0].summary == "Free Steam demo listed with a 15 Jun 2026 date"
        assert "Evidence" not in built[0].summary
        assert "crit_" not in built[0].summary

    def test_a_summary_is_bounded(self):
        from master_agent.brain.deliberation import candidates_from

        built = candidates_from(FRAME, self.observations(), self.reasoner(
            {"candidates": [{"id": "a", "summary": "x" * 400,
                             "criteria": {}}]}
        ))
        assert len(built[0].summary) <= 80

    def test_similarly_named_candidates_do_not_invent_a_contradiction(self):
        """`adjudicate` groups assessments making the same claim, which is
        how genuine disagreement is found. Keying the claim on summary
        text alone made six Steam listings that shared a phrase come back
        CONTESTED -- a contradiction manufactured out of string equality,
        about sources that never disagreed."""
        from master_agent.brain.deliberation import CONTESTED, deliberate

        result = deliberate(FRAME, self.observations(), self.reasoner(
            {"candidates": [
                {"id": "a", "summary": "Free Steam demo 2026",
                 "criteria": {c: {"state": "unverified", "evidence_id": ""}
                              for c in ("c1", "c2", "c3", "c4")}},
                {"id": "b", "summary": "Free Steam demo 2026",
                 "criteria": {c: {"state": "unverified", "evidence_id": ""}
                              for c in ("c1", "c2", "c3", "c4")}},
            ]}
        ))
        assert result.state != CONTESTED, (
            "two unproven candidates with the same name were reported as "
            "sources disagreeing"
        )

    def test_unproven_is_not_contested(self):
        """An unestablished criterion is not a contradiction. It is
        something nobody has shown yet, and more research can answer
        it."""
        from master_agent.brain.deliberation import (
            INSUFFICIENT_EVIDENCE, deliberate,
        )

        result = deliberate(FRAME, self.observations(), self.reasoner(
            {"candidates": [{"id": "a", "summary": "Ashen Vale",
                             "criteria": {c: {"state": "unverified",
                                              "evidence_id": ""}
                                          for c in ("c1", "c2", "c3", "c4")}}]}
        ))
        assert result.state == INSUFFICIENT_EVIDENCE
        assert result.more_research is True


class TestTheFounderNeverReadsAnEvidenceId:
    """Provenance belongs in the record, which keeps it. The sentence
    gets the part a person can act on -- the first real run put four
    UUIDs into the founder's reply, twice over."""

    def test_ids_are_stripped_from_the_sentence(self):
        import kalpavriksha_desktop as kd

        plain = kd._plain([
            "cand_1/crit_2: Ashen Vale. Evidence: c43598d0-2143-449c-a1b5, "
            "3f2b0bd6-a499-475a",
        ])
        assert "Ashen Vale" in plain
        assert "c43598d0" not in plain
        assert "crit_2" not in plain

    def test_duplicates_are_said_once(self):
        import kalpavriksha_desktop as kd

        plain = kd._plain(["a/c1: Ashen Vale", "a/c2: Ashen Vale"])
        assert plain == "Ashen Vale"

    def test_nothing_nameable_still_says_something_honest(self):
        import kalpavriksha_desktop as kd

        assert kd._plain([]) == "something it could not name"


class TestOneOwnerForHowMuchThinking:
    """`depth_for` was written as the owner of that question and then
    never called, while `frame_for` decided the same thing again from a
    capability name. Two answers to one question, free to drift, and the
    kind of duplication only ever noticed once they disagree."""

    def test_framing_defers_to_the_depth_policy(self):
        from master_agent.brain.deliberation import frame_for

        assert "depth_for" in frame_for.__code__.co_names

    def test_a_deterministic_capability_is_still_never_framed(self):
        from master_agent.brain.deliberation import frame_for
        from master_agent.planner.plan import EFFECT, SemanticRequirement

        requirement = SemanticRequirement(
            "req_1", EFFECT, "create a folder",
            founder_evidence="create a folder called X",
        )
        assert frame_for(
            objective="create a folder called X",
            requirements=(requirement,),
            capability="create_folder",
        ) is None

    def test_a_compound_objective_is_still_framed(self):
        from master_agent.brain.deliberation import frame_for
        from master_agent.planner.plan import INFORMATION, SemanticRequirement

        requirements = (
            SemanticRequirement("req_1", INFORMATION, "find the options",
                                founder_evidence="compare these"),
            SemanticRequirement("req_2", INFORMATION, "compare them",
                                founder_evidence="compare these"),
        )
        frame = frame_for(objective="compare these", requirements=requirements)
        assert frame is not None
        assert len(frame.mandatory) == 2
