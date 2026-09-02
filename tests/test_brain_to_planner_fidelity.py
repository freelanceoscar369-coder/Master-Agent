"""Stage 3: the Planner translates the Brain's decision, it does not
re-read the mission.

The mission always owns every Founder requirement. The CURRENT
continuation owns only the subset the Brain selected. A requirement that
is not in this plan is still required -- it is unresolved mission state,
not finished work -- and a Planner that quietly widened its own scope
would become a second Brain deciding what matters next.

These probes drive the existing coverage contract and plan validator.
Nothing here executes a plan.
"""
from __future__ import annotations

from master_agent.planner.parsing import validate
from master_agent.planner.plan import Intent, SemanticRequirement, strategy_coverage

# The frozen canonical mission, by requirement id.
LANDSCAPE, TOP_THREE = "req_1", "req_2"
PRICING, BROWSER, AUTONOMY, MEMORY, DIFFERENTIATORS = (
    "req_3", "req_4", "req_5", "req_6", "req_7")
EVIDENCE, THREAT, BRIEF = "req_8", "req_9", "req_10"
ALL = (LANDSCAPE, TOP_THREE, PRICING, BROWSER, AUTONOMY, MEMORY,
       DIFFERENTIATORS, EVIDENCE, THREAT, BRIEF)


def requirements():
    return tuple(
        SemanticRequirement(
            requirement_id=rid, kind="information",
            description=f"obligation {rid}", provenance="founder said",
            founder_evidence="founder said",
        )
        for rid in ALL
    )


def mission(*, targets=(), satisfied=(), framed=True, action="acquire_evidence",
            exhausted=()):
    """A canonical Intent carrying a real Brain decision."""
    context = {"raw_input": "the founder's own words"}
    if framed:
        context["decision_frame"] = {"objective": "the founder's own words"}
    if targets:
        context["evidence_needed"] = {
            "target_requirements": list(targets),
            "action": action,
            "exhausted_strategies": list(exhausted),
            "reason": "brain reason",
        }
    if satisfied:
        context["recovery"] = {"satisfied": list(satisfied), "unresolved": []}
    intent = Intent(goal="the founder's own words", context=context)
    intent.requirements = requirements()
    return intent


def step(step_id, capability, requirement_id, **payload):
    """One plan step in the shape the real validator reads."""
    return {
        "id": step_id,
        "capability": capability,
        "payload": payload or {"query": "public sources"},
        "covers": [requirement_id],
        "success": {"description": f"{capability} produced usable evidence"},
    }


# ---------------------------------------------------------------------
# P1 / P2 - the Brain's target reaches the Planner and bounds it
# ---------------------------------------------------------------------


def test_p1_the_brain_target_becomes_the_planner_coverage_contract():
    selected, forbidden = strategy_coverage(mission(targets=(LANDSCAPE,)))

    assert selected == (LANDSCAPE,)
    # Every other canonical requirement is off-limits for THIS plan...
    for other in ALL:
        if other != LANDSCAPE:
            assert other in forbidden


def test_p2_discovery_stays_discovery_and_the_mission_keeps_the_rest():
    intent = mission(targets=(LANDSCAPE,))
    selected, forbidden = strategy_coverage(intent)

    # The mission still owns all ten; only the continuation is narrow.
    assert len(intent.requirements) == len(ALL)
    assert selected == (LANDSCAPE,)
    assert THREAT in forbidden and BRIEF in forbidden


def test_p3_qualification_targets_only_the_canonical_set():
    selected, forbidden = strategy_coverage(mission(targets=(TOP_THREE,)))

    assert selected == (TOP_THREE,)
    assert PRICING in forbidden
    assert BROWSER in forbidden


def test_p4_one_comparison_criterion_stays_one_criterion():
    selected, forbidden = strategy_coverage(mission(targets=(PRICING,)))

    assert selected == (PRICING,)
    for sibling in (BROWSER, AUTONOMY, MEMORY, DIFFERENTIATORS):
        assert sibling in forbidden


def test_p5_a_legitimate_multi_target_set_is_preserved_exactly():
    selected, forbidden = strategy_coverage(
        mission(targets=(EVIDENCE, THREAT)))

    assert set(selected) == {EVIDENCE, THREAT}
    assert BRIEF in forbidden
    assert LANDSCAPE in forbidden


def test_p6_satisfied_work_is_forbidden_not_merely_omitted():
    selected, forbidden = strategy_coverage(
        mission(targets=(BROWSER,), satisfied=(PRICING,)))

    assert selected == (BROWSER,)
    assert PRICING in forbidden


def test_p7_blocked_downstream_work_is_not_in_scope():
    """The Brain targets discovery; pricing is unresolved but blocked."""
    selected, forbidden = strategy_coverage(mission(targets=(LANDSCAPE,)))

    assert PRICING in forbidden
    assert PRICING not in selected


def test_p13_an_unframed_mission_keeps_the_whole_objective():
    """Without a Brain frame there is no continuation to be faithful to,
    so the plan legitimately covers the whole mission -- the simple
    deterministic path is not damaged by Stage 3."""
    selected, forbidden = strategy_coverage(mission(framed=False))

    assert set(selected) == set(ALL)
    assert forbidden == ()


# ---------------------------------------------------------------------
# The attack battery, through the real validator
# ---------------------------------------------------------------------

def options():
    from master_agent.planner.catalogue import CapabilityOption

    return (
        CapabilityOption(
            name="Browser.Search", description="search public sources",
            required_args=("query",), optional_args=("query",),
        ),
        CapabilityOption(
            name="Browser.ReadPageText", description="read a page",
            required_args=("url",), optional_args=("url",),
        ),
        CapabilityOption(
            name="Reasoning.Transform", description="transform text",
            required_args=("instruction",), optional_args=("instruction", "text"),
        ),
        CapabilityOption(
            name="Filesystem.WriteFile", description="write a file",
            required_args=("path", "text"), optional_args=("path", "text"),
        ),
    )


def run(steps, *, targets, satisfied=(), exhausted=()):
    intent = mission(targets=targets, satisfied=satisfied)
    selected, forbidden = strategy_coverage(intent)
    return validate(
        {"steps": steps},
        options(),
        objective=intent.goal,
        requirements=intent.requirements,
        required_coverage=selected,
        forbidden_coverage=forbidden,
        exhausted_routes=exhausted,
    )


def test_attack_a_whole_mission_expansion_is_refused():
    """Brain targets the landscape; the model proposes the whole mission."""
    steps = [step(f"s{i}", "Browser.Search", rid, query="x")
             for i, rid in enumerate(ALL, start=1)]

    plan, refusal = run(steps, targets=(LANDSCAPE,))

    assert plan is None
    assert refusal is not None
    assert "untargeted" in refusal.reason


def test_attack_b_a_downstream_jump_is_refused():
    """Brain targets the landscape; the model selects a top three and
    compares pricing from its own assumptions."""
    steps = [step("s1", "Browser.Search", TOP_THREE, query="top three"),
             step("s2", "Browser.ReadPageText", PRICING, url="https://x.test")]

    plan, refusal = run(steps, targets=(LANDSCAPE,))

    assert plan is None
    # Two correct grounds, and it may cite either: the plan claims
    # untargeted requirements AND abandons the one it was given.
    assert ("untargeted" in refusal.reason
            or "does not cover every current strategy target" in refusal.reason)
    assert LANDSCAPE in refusal.detail or "untargeted" in refusal.reason


def test_attack_c_target_loss_is_refused():
    """Brain targets pricing; the model plans a browser comparison."""
    steps = [step("s1", "Browser.ReadPageText", BROWSER, url="https://x.test")]

    plan, refusal = run(steps, targets=(PRICING,))

    assert plan is None
    assert refusal is not None


def test_attack_e_an_invented_capability_is_refused():
    steps = [{"step_id": "s1", "capability": "Browser.MagicallyKnowEverything",
              "payload": {"query": "x"}, "requirement_ids": [LANDSCAPE]}]

    plan, refusal = run(steps, targets=(LANDSCAPE,))

    assert plan is None
    assert refusal is not None


def test_attack_g_reintroducing_satisfied_work_is_refused():
    steps = [step("s1", "Browser.ReadPageText", BROWSER, url="https://x.test"),
             step("s2", "Browser.ReadPageText", PRICING, url="https://y.test")]

    plan, refusal = run(steps, targets=(BROWSER,), satisfied=(PRICING,))

    assert plan is None
    assert "already satisfied" in refusal.detail or "untargeted" in refusal.reason


def test_p8_an_exhausted_route_repeated_unchanged_is_refused():
    dead = "Browser.ReadPageText https://dead.example"
    steps = [step("s1", "Browser.ReadPageText", PRICING,
                  url="https://dead.example")]

    plan, refusal = run(steps, targets=(PRICING,), exhausted=(dead,))

    assert plan is None
    assert "exhausted strategy" in refusal.reason


def test_a_faithful_plan_for_the_brain_target_is_admitted():
    """The control: stay inside the Brain's target and the plan stands."""
    steps = [step("s1", "Browser.Search", LANDSCAPE, query="ai agent products"),
             step("s2", "Browser.ReadPageText", LANDSCAPE,
                  url="https://example.test/list")]

    plan, refusal = run(steps, targets=(LANDSCAPE,))

    assert refusal is None, refusal
    assert plan is not None
    # The whole canonical mission travels on the plan even though the
    # continuation is narrow -- untargeted is not finished.
    assert len(plan.requirements) == len(ALL)


# ---------------------------------------------------------------------
# Generalisation
# ---------------------------------------------------------------------


def test_p17_supplier_mission_bounds_its_continuation_the_same_way():
    eligible, chosen, emailed = "s_1", "s_2", "s_3"
    intent = Intent(goal="suppliers", context={
        "decision_frame": {"objective": "suppliers"},
        "evidence_needed": {"target_requirements": [eligible],
                            "action": "discover_candidates"},
    })
    intent.requirements = tuple(
        SemanticRequirement(requirement_id=rid, kind="information",
                            description=rid, provenance="f",
                            founder_evidence="f")
        for rid in (eligible, chosen, emailed)
    )

    selected, forbidden = strategy_coverage(intent)

    assert selected == (eligible,)
    assert chosen in forbidden and emailed in forbidden


def test_p18_game_research_does_not_rediscover_established_candidates():
    titles, demos, links = "g_1", "g_2", "g_3"
    intent = Intent(goal="games", context={
        "decision_frame": {"objective": "games"},
        "evidence_needed": {"target_requirements": [demos],
                            "action": "acquire_evidence"},
        "recovery": {"satisfied": [titles], "unresolved": [demos, links]},
    })
    intent.requirements = tuple(
        SemanticRequirement(requirement_id=rid, kind="information",
                            description=rid, provenance="f",
                            founder_evidence="f")
        for rid in (titles, demos, links)
    )

    selected, forbidden = strategy_coverage(intent)

    assert selected == (demos,)
    assert titles in forbidden          # already established
    assert links in forbidden           # not this continuation


# ---------------------------------------------------------------------
# The rest of the battery: the decision travels, and nothing else does
# ---------------------------------------------------------------------


def test_p9_the_coverage_contract_does_not_depend_on_who_answered():
    """A provider fallback is not a strategy change.

    The contract is a pure function of the canonical Intent, so the same
    mission state yields the same target whichever provider planned it.
    """
    intent = mission(targets=(PRICING,))

    first = strategy_coverage(intent)
    second = strategy_coverage(intent)

    assert first == second
    assert first[0] == (PRICING,)


def test_p10_a_target_id_the_mission_does_not_own_is_not_trusted():
    """The Brain names ids; the Intent decides which exist."""
    selected, forbidden = strategy_coverage(
        mission(targets=(PRICING, "req_invented")))

    assert selected == (PRICING,)
    assert "req_invented" not in selected
    assert "req_invented" not in forbidden


def test_p10b_a_wholly_unknown_target_leaves_no_admissible_plan():
    """Every canonical requirement is forbidden, so nothing can be
    claimed. Refusing beats guessing which requirement was meant."""
    intent = mission(targets=("req_invented",))
    selected, forbidden = strategy_coverage(intent)

    assert selected == ()
    assert set(forbidden) == set(ALL)

    plan, refusal = validate(
        {"steps": [step("s1", "Browser.Search", LANDSCAPE, query="x")]},
        options(), objective=intent.goal, requirements=intent.requirements,
        required_coverage=selected, forbidden_coverage=forbidden,
    )
    assert plan is None
    assert refusal is not None


def test_p11_the_correction_pass_recomputes_the_same_contract():
    """One bounded repair may fix the plan; it may not renegotiate scope.

    `Planner._correct` recomputes the contract from the same Intent
    rather than carrying a contract the failed plan implied.
    """
    import inspect

    from master_agent.planner.planner import Planner

    source = inspect.getsource(Planner._correct)
    assert "self._coverage_contract(intent)" in source
    assert "required_coverage=required_coverage" in source
    assert "forbidden_coverage=forbidden_coverage" in source


def test_p12_a_corrected_plan_that_widened_scope_is_still_refused():
    """The second pass is validated under the first pass's contract."""
    widened = [step("s1", "Browser.Search", PRICING, query="pricing"),
               step("s2", "Browser.Search", THREAT, query="threat")]

    plan, refusal = run(widened, targets=(PRICING,))

    assert plan is None
    assert "untargeted" in refusal.reason


def test_p14_finalisation_may_not_reopen_satisfied_research():
    """The Brain finalises from the canonical decision. A plan that also
    re-gathers an established requirement is refused."""
    steps = [step("s1", "Reasoning.Transform", BRIEF, instruction="synthesise"),
             step("s2", "Browser.Search", LANDSCAPE, query="re-research")]

    plan, refusal = run(steps, targets=(BRIEF,), satisfied=(LANDSCAPE,))

    assert plan is None
    assert "untargeted" in refusal.reason or "already satisfied" in refusal.detail


def test_p16_a_framed_mission_with_no_brain_target_is_refused_not_guessed():
    """The strongest fidelity property already built: the Planner will
    not select a next move for a mission that has a decision frame."""
    from master_agent.planner.planner import Planner

    intent = mission(framed=True)          # frame, but no evidence_needed
    intent.context.pop("evidence_needed", None)

    class Never:
        def run(self, *a, **k):            # pragma: no cover - must not run
            raise AssertionError("the Planner asked a model to choose a target")

    outcome = Planner(Never(), options()).plan(intent)

    assert outcome.refusal is not None
    assert "has not selected a current strategy target" in outcome.refusal.reason


def test_p19_the_deterministic_path_is_untouched_by_stage_three():
    """A typed filesystem mission has no frame, so it keeps the whole
    objective and reaches no coverage restriction at all."""
    intent = Intent(goal="Create folder 'Finance'", context={})
    intent.requirements = ()

    selected, forbidden = strategy_coverage(intent)

    assert selected == ()
    assert forbidden == ()


def test_p20_the_prompt_states_the_contract_it_will_be_judged_against():
    """Refusing a plan the Planner was never told the rules for is a
    trap. The prompt names the target rows and the satisfied rows."""
    from master_agent.planner.prompting import build_prompt

    prompt = build_prompt(mission(targets=(PRICING,), satisfied=(LANDSCAPE,)),
                          options())

    assert "CURRENT STRATEGY TARGET" in prompt
    assert "ALREADY SATISFIED -- DO NOT REDO" in prompt
    # and the mission is not misrepresented as finished
    assert "The MISSION owns every one" in prompt


def test_attack_d_a_plan_that_covers_nothing_is_refused():
    steps = [{"id": "s1", "capability": "Browser.Search",
              "payload": {"query": "x"}, "covers": [],
              "success": {"description": "found something"}}]

    plan, refusal = run(steps, targets=(LANDSCAPE,))

    assert plan is None
    assert refusal is not None


def test_attack_f_the_deliverable_may_not_be_smuggled_in_early():
    """Brain targets discovery; the plan writes the final brief anyway."""
    steps = [step("s1", "Browser.Search", LANDSCAPE, query="landscape"),
             step("s2", "Filesystem.WriteFile", BRIEF,
                  path="C:/Users/x/Desktop/brief.md", text="early")]

    plan, refusal = run(steps, targets=(LANDSCAPE,))

    assert plan is None
    assert refusal is not None


def test_p20b_the_microtrace_names_the_planner_as_the_consumer():
    """The handoff is reviewable: the Brain's chosen need is recorded as
    the input the Planner was given (ADR-0027)."""
    import inspect

    from master_agent.missions.service import MissionService

    source = inspect.getsource(MissionService)
    assert "INTENT_TO_BRAIN_NEXT_ACTION" in source
    assert '"next_consumer": "Planner"' in source
    assert 'intent.context["evidence_needed"] = first_need.as_dict()' in source
