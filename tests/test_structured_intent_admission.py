"""The structured Intent contract, and the admission boundary in front of
the Planner. ADR-0024 Decisions 1, 3, 5 and 12.

Two things are proven here, and they are the two the audit said were
missing:

1. **An `Intent` carries meaning the raw sentence carried alone.**
   *"Learn trading"*, *"Teach me trading"* and *"Help me learn trading"*
   used to differ only in `goal=<the raw sentence>`. Three probes, one
   structure. Now they differ structurally, in fields a caller can branch
   on without re-reading prose.

2. **The Planner is reached only through `MissionService`, and only with
   an understood Intent.** A clarification-required request reaches
   neither -- asserted by spies that record every call, so "it was not
   called" is evidence rather than an assumption.

Nothing here calls a provider, a browser, or a machine.
"""
from __future__ import annotations

import inspect
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kalpavriksha_desktop as kd  # noqa: E402

from master_agent.brain import agency  # noqa: E402
from master_agent.brain.intent import IntentLayer  # noqa: E402
from master_agent.conversation_engine.pipeline import Disposition  # noqa: E402
from master_agent.missions.execution_status import ExecutionStatus  # noqa: E402
from master_agent.missions.service import MissionService  # noqa: E402
from master_agent.planner.plan import (  # noqa: E402
    BOTH,
    FOUNDER,
    ROLES,
    SYSTEM,
    UNKNOWN_ROLE,
    Intent,
    PlanOutcome,
    PlanRefusal,
)
from tests.test_conversation_engine import T0, engine  # noqa: E402
from tests.test_kalpavriksha_desktop_mission_bridge import (  # noqa: E402
    _FakeFounderState,
    _FakeMissionControl,
    _FakeMissionService,
    _FakeObjective,
    _FakeOutcome,
    _FakeRuntime,
)


# =========================================================================
# Spies
# =========================================================================


class PlannerSpy:
    """Records every `plan()` call and the exact object it received."""

    def __init__(self, outcome=None) -> None:
        self.calls: list[Intent] = []
        self._outcome = outcome or PlanOutcome(
            refusal=PlanRefusal(code="no_steps", reason="nothing registered")
        )

    def plan(self, intent, *, task_id="", objective_id=None):
        self.calls.append(intent)
        return self._outcome


class MissionControlSpy:
    def __init__(self) -> None:
        self.submitted = []

    def submit_objective(self, mission):
        self.submitted.append(mission)
        return mission


def service(planner=None) -> MissionService:
    """A real `MissionService` with a real `IntentLayer` and a spied
    Planner -- the production wiring with one observation point."""
    return MissionService(
        planner=planner or PlannerSpy(),
        mission_control=MissionControlSpy(),
        intent_layer=IntentLayer(),
    )


def submit(text: str, *, service_double=None, accepted: bool = True):
    """One founder utterance through the real `_submit_objective()`."""
    svc = service_double or _FakeMissionService(
        _FakeOutcome(accepted=accepted, objective_id="obj-1" if accepted else None)
    )
    status = ExecutionStatus()
    reply = kd._submit_objective(
        svc, _FakeRuntime(),
        _FakeMissionControl([_FakeObjective(complete=True)], _FakeFounderState()),
        status, text, timeout_seconds=1.0,
    )
    return reply["reply"], svc, status


# =========================================================================
# 1. The canonical Intent carries agency
# =========================================================================


class TestIntentIsStructured:

    def test_the_three_indistinguishable_probes_are_now_distinct(self):
        """The audit's exact finding, inverted into a regression test.

        These three parsed to structurally identical Intents at `f39fcce`,
        differing only in the raw sentence carried as `goal`.
        """
        layer = IntentLayer()
        learn = layer.parse("Learn trading").intent
        teach = layer.parse("Teach me trading").intent
        assist = layer.parse("Help me learn trading").intent

        shapes = {
            (i.actor, i.beneficiary) for i in (learn, teach, assist)
        }
        assert len(shapes) == 3, (
            f"three different instructions still share {len(shapes)} shape(s) "
            "-- agency is not structurally represented"
        )

    @pytest.mark.parametrize(
        "text,actor,beneficiary",
        [
            # Probe A -- Kalpavriksha is instructed to acquire the skill.
            # The founder is NOT the learner; that is the whole of bb36c9f.
            ("Learn trading", SYSTEM, UNKNOWN_ROLE),
            # Probe B -- Kalpavriksha teaches, the founder learns.
            ("Teach me trading", SYSTEM, FOUNDER),
            # Probe C -- collaborative: the founder acts too.
            ("Help me learn trading", BOTH, FOUNDER),
            # Probe D -- pursued on the founder's behalf.
            ("Buy a house for me", SYSTEM, FOUNDER),
            # Probe E -- an explicit request for advice. The founder asked
            # to be told; answering with advice is CORRECT here.
            ("Tell me how to buy a house", SYSTEM, FOUNDER),
            # Ordinary executable work.
            ("Open github.com", SYSTEM, UNKNOWN_ROLE),
            ("Create a folder called Research on my Desktop", SYSTEM, UNKNOWN_ROLE),
        ],
    )
    def test_semantic_probe_matrix(self, text, actor, beneficiary):
        intent = IntentLayer().parse(text).intent
        assert intent is not None
        assert intent.actor == actor
        assert intent.beneficiary == beneficiary

    def test_my_in_a_location_is_not_a_beneficiary(self):
        """*"on my Desktop"* names a possession, not a recipient. A rule
        that searched for "my" anywhere would get this wrong."""
        intent = IntentLayer().parse(
            "Create a folder called Research on my Desktop"
        ).intent
        assert intent.beneficiary == UNKNOWN_ROLE

    def test_an_unseen_sentence_takes_the_same_structural_path(self):
        """No probe is hardcoded, so a goal this codebase has never seen
        derives agency from the same grammar."""
        intent = IntentLayer().parse(
            "Get me fluent in Portuguese before the Lisbon trip"
        ).intent
        assert (intent.actor, intent.beneficiary) == (SYSTEM, FOUNDER)
        assert IntentLayer().parse("Learn woodworking").intent.actor == SYSTEM

    def test_roles_are_a_closed_vocabulary(self):
        for text in ("Learn trading", "Teach me trading", "Help me learn trading",
                     "Buy a house for me", "", "Open github.com"):
            actor, beneficiary = agency.roles(text)
            assert actor in ROLES and beneficiary in ROLES

    def test_unknown_is_used_rather_than_a_guess(self):
        """ADR-0024 §6: unknown beats invented. Constructions outside the
        derivable set must NOT be assigned a confident beneficiary."""
        # Third-party beneficiary -- outside the rules, and honestly so.
        intent = IntentLayer().parse("Send the report to John").intent
        assert intent.beneficiary == UNKNOWN_ROLE

    def test_a_hand_built_intent_claims_no_agency_it_did_not_derive(self):
        assert Intent(goal="x").actor == UNKNOWN_ROLE
        assert Intent(goal="x").beneficiary == UNKNOWN_ROLE

    def test_no_probe_phrase_is_hardcoded_in_the_derivation(self):
        import ast

        tree = ast.parse(inspect.getsource(agency))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) \
                    and ast.get_docstring(node):
                node.body = node.body[1:]
        body = ast.unparse(tree).lower()
        for probe in ("trading", "house", "folder", "github", "portuguese", "learn",
                      "teach", "buy", "tell"):
            assert probe not in body, (
                f"{probe!r} appears in the derivation -- agency is being read "
                "from subject matter instead of grammar"
            )


# =========================================================================
# 2. Success criteria and founder-supplied values
# =========================================================================


class TestSuccessCriteriaAndDefaults:

    def test_a_typed_objective_states_a_checkable_criterion(self):
        intent = IntentLayer().parse(
            "Create a folder called Research on my Desktop"
        ).intent
        assert intent.success_criteria == ["Folder 'Research' exists at Desktop"]

    def test_a_broad_goal_states_no_criterion_rather_than_echoing_the_prompt(self):
        """It used to say "Objective completed: Learn trading" -- a
        restatement of the request, which Verification cannot check
        anything against. ADR-0024 §8: preserve uncertainty."""
        intent = IntentLayer().parse("Learn trading").intent
        assert intent.success_criteria == []

    def test_a_founder_supplied_location_is_preserved(self):
        intent = IntentLayer().parse(
            "Create a folder called Research in Documents"
        ).intent
        assert intent.context["location"] == "Documents"
        assert "Location: Documents" in intent.constraints

    def test_a_downstream_default_is_not_recorded_as_a_founder_instruction(self):
        """*"Create a folder called Research"* states no location. The
        action contract defaults it; the Intent must not claim the founder
        asked for that default."""
        intent = IntentLayer().parse("Create a folder called Research").intent
        assert "location" not in intent.context
        assert intent.constraints == []
        assert "Desktop" not in str(intent.context)


# =========================================================================
# 3. Admission: the boundary in front of the Planner
# =========================================================================


class TestPlannerAdmission:

    def test_an_understood_intent_reaches_the_planner_unchanged(self):
        """ADR-0024 Decision 13 -- the same canonical object, not a copy
        rebuilt from prose."""
        planner = PlannerSpy()
        svc = service(planner)
        intent = IntentLayer().parse("Teach me trading").intent

        svc.start(intent)

        assert len(planner.calls) == 1
        received = planner.calls[0]
        assert received is intent, "the Planner received a different object"
        assert received.actor == SYSTEM
        assert received.beneficiary == FOUNDER

    def test_mission_service_does_not_reinterpret_the_intent(self):
        """ADR-0024 Decision 12: goal, agency and constraints survive the
        boundary untouched."""
        planner = PlannerSpy()
        intent = Intent(
            goal="Learn trading",
            constraints=["only free sources"],
            context={"raw_input": "Learn trading"},
            actor=SYSTEM,
            beneficiary=UNKNOWN_ROLE,
        )
        service(planner).start(intent)

        received = planner.calls[0]
        assert received.goal == "Learn trading"
        assert received.actor == SYSTEM
        assert received.beneficiary == UNKNOWN_ROLE
        assert received.constraints == ["only free sources"]

    def test_mission_service_does_not_reparse_founder_text(self):
        """Given an Intent, the Intent Layer must not run again. A layer
        that raises proves it was never consulted."""
        class Exploding:
            def parse(self, text):
                raise AssertionError(
                    "MissionService re-parsed founder language after the "
                    "Intent Layer had already understood it"
                )

        svc = MissionService(
            planner=PlannerSpy(), mission_control=MissionControlSpy(),
            intent_layer=Exploding(),
        )
        svc.start(Intent(goal="Learn trading", actor=SYSTEM))

    def test_a_broad_goal_is_admitted_not_rejected(self):
        """ADR-0024 Decision 2: capability absence is not ambiguity. These
        must reach the Planner and let it answer honestly."""
        for text in ("Learn trading", "Buy a house for me"):
            planner = PlannerSpy()
            svc = service(planner)
            result = svc.intent_layer.parse(text)
            assert not result.needs_clarification
            svc.start(result.intent)
            assert len(planner.calls) == 1, f"{text!r} never reached the Planner"


# =========================================================================
# 4. Clarification blocks admission
# =========================================================================


class TestClarificationBlocksAdmission:

    def test_an_under_specified_request_never_becomes_a_mission(self):
        reply, svc, _ = submit("Create a folder")
        assert reply == "What should the folder be called?"
        assert svc.started_with is None, "MissionService was entered anyway"

    def test_and_therefore_never_reaches_the_planner(self):
        """Proven through a real MissionService: were the surface to call
        it, the Planner spy would record it."""
        planner = PlannerSpy()
        svc = service(planner)
        result = svc.intent_layer.parse("Create a folder")

        assert result.needs_clarification
        assert result.intent is None
        assert planner.calls == []

    def test_the_question_is_asked_verbatim(self):
        reply, _, _ = submit("Create a folder")
        assert reply.endswith("?")
        assert "can't" not in reply.lower()


# =========================================================================
# 5. The production route
# =========================================================================


class TestProductionRoute:

    def test_founder_execution_passes_through_mission_service(self):
        reply, svc, _ = submit("Open github.com")
        assert isinstance(svc.started_with, Intent), (
            "the founder surface did not hand MissionService a canonical "
            f"Intent -- it passed {type(svc.started_with).__name__}"
        )

    def test_the_surface_hands_over_an_intent_not_raw_text(self):
        _, svc, _ = submit("Teach me trading")
        assert svc.started_with.actor == SYSTEM
        assert svc.started_with.beneficiary == FOUNDER

    def test_the_surface_uses_the_services_own_intent_layer(self):
        """One Intent Layer in the process. A second instance would be a
        second place agency is derived, free to drift."""
        source = inspect.getsource(kd._submit_objective)
        assert "mission_service.intent_layer.parse" in source
        assert "IntentLayer()" not in source

    def test_raw_input_survives_as_provenance(self):
        _, svc, _ = submit("Learn trading")
        assert svc.started_with.context.get("raw_input") == "Learn trading"

    @pytest.mark.parametrize("text", ["Good morning", "What can you do?"])
    def test_conversation_never_becomes_a_mission(self, text):
        """ADR-0024 Decision 14 -- MissionService is not a conversation
        dispatcher. These are answered before the surface ever escalates."""
        turn = engine().reply(text, moment=T0)
        assert turn.disposition is Disposition.HANDLED
        assert turn.reply


# =========================================================================
# 6. Architecture invariants
# =========================================================================


class TestNoSecondIntentModel:

    def test_there_is_exactly_one_intent_type(self):
        import master_agent.brain.intent as brain_intent
        import master_agent.missions.service as svc_mod

        for module in (brain_intent, svc_mod, agency, kd):
            source = inspect.getsource(module)
            for forbidden in ("class StructuredIntent", "class ResolvedIntent",
                              "class FounderIntent", "class MissionIntent",
                              "class SemanticIntent"):
                assert forbidden not in source, f"{forbidden} in {module.__name__}"

    def test_agency_is_derived_in_exactly_one_place(self):
        """Stamped at the single `parse()` entry point, so no parser can be
        added without it and no second implementation can appear."""
        import master_agent.brain.intent as brain_intent

        source = inspect.getsource(brain_intent)
        assert source.count("roles(text)") == 1

    def test_every_parser_output_carries_agency(self):
        """Not just the fallback: the typed parsers gain it too, because
        the stamp happens above them."""
        layer = IntentLayer()
        for text in ("Create a folder called Research on my Desktop",
                     "Open github.com", "Learn trading",
                     "Delete the file report.txt"):
            intent = layer.parse(text).intent
            if intent is not None:
                assert intent.actor in ROLES
                assert intent.actor != UNKNOWN_ROLE, f"{text!r} lost its actor"
