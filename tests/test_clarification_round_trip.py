"""The clarification round trip, closed.

Before this, Kalpavriksha could ask a question and could not hear the
answer. The question was displayed, the objective was marked COMPLETED --
as though showing a question were an outcome -- and nothing was pending,
so the founder's reply arrived as a brand-new mission. `"Research"` became
an objective in its own right.

Worse, `IntentLayer.clarify()` could not have resolved it anyway: it
rejoined the two strings, and `"Create a folder" + "Research"` produces
`"Create a folder Research"`, which has no `called`, so the parser found
no name and asked the identical question again. A loop with no exit.

These tests drive the real production entry point,
`kalpavriksha_desktop._submit_objective`, with a real `IntentLayer` and
spies on `MissionService` and the Planner -- so "the Planner was not
called" is recorded evidence, not an assumption.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kalpavriksha_desktop as kd  # noqa: E402

from master_agent.brain.intent import ClarificationQuestion, IntentLayer  # noqa: E402
from master_agent.conversation_engine.pipeline import Disposition  # noqa: E402
from master_agent.missions.execution_status import (  # noqa: E402
    AWAITING_CLARIFICATION,
    COMPLETED,
    TERMINAL_STATUSES,
    ExecutionStatus,
    PendingClarification,
)
from master_agent.missions.service import MissionService  # noqa: E402
from master_agent.planner.plan import (  # noqa: E402
    SYSTEM,
    Intent,
    PlanOutcome,
    PlanRefusal,
)
from tests.test_conversation_engine import T0, engine  # noqa: E402
from tests.test_kalpavriksha_desktop_mission_bridge import (  # noqa: E402
    _FakeFounderState,
    _FakeMissionControl,
    _FakeObjective,
    _FakeRuntime,
)


# =========================================================================
# The production rig
# =========================================================================


class PlannerSpy:
    def __init__(self) -> None:
        self.calls: list[Intent] = []

    def plan(self, intent, *, task_id="", objective_id=None):
        self.calls.append(intent)
        return PlanOutcome(refusal=PlanRefusal(code="no_steps", reason="nothing registered"))


class MissionControlSpy:
    def submit_objective(self, mission):
        return mission


class Surface:
    """One founder conversation, driven through the real composition.

    A real `MissionService` with a real `IntentLayer`, a spied Planner,
    and one `ExecutionStatus` carried across turns -- which is what makes
    a *round trip* testable at all: the pending question lives on that
    status, so a rig that built a fresh one per turn would prove nothing.
    """

    def __init__(self, intent_layer=None) -> None:
        self.planner = PlannerSpy()
        self.service = MissionService(
            planner=self.planner,
            mission_control=MissionControlSpy(),
            intent_layer=intent_layer or IntentLayer(),
        )
        self.admissions: list[Intent] = []
        inner = self.service.start

        def counting(objective, **kwargs):
            self.admissions.append(objective)
            return inner(objective, **kwargs)

        self.service.start = counting
        self.status = ExecutionStatus()

    def say(self, text: str) -> str:
        result = kd._submit_objective(
            self.service, _FakeRuntime(),
            _FakeMissionControl([_FakeObjective(complete=True)], _FakeFounderState()),
            self.status, text, timeout_seconds=1.0,
        )
        return result["reply"]

    @property
    def pending(self):
        return self.status.pending_clarification


# =========================================================================
# A. The basic round trip
# =========================================================================


class TestA_BasicFolderClarification:

    def test_the_question_is_asked_and_nothing_is_started(self):
        surface = Surface()
        reply = surface.say("Create a folder")

        assert reply == "What should the folder be called?"
        assert surface.admissions == [], "MissionService was entered"
        assert surface.planner.calls == [], "the Planner was called"
        assert surface.pending is not None, "no pending Intent was stored"

    def test_the_objective_is_not_completed_by_asking(self):
        """Showing a question is not an outcome. This was the specific
        defect: `status.status = COMPLETED` the moment the question was
        displayed."""
        surface = Surface()
        surface.say("Create a folder")

        assert surface.status.status == AWAITING_CLARIFICATION
        assert surface.status.status != COMPLETED
        assert surface.status.status not in TERMINAL_STATUSES
        assert not surface.status.terminal_state

    def test_the_location_is_asked_for_before_anything_is_admitted(self):
        """The founder requirement this suite gained: a name alone does
        not finish a folder request. Onkar said "Create a folder" and
        "Research" -- he never said where, and nothing may run until he
        does."""
        surface = Surface()
        surface.say("Create a folder")
        reply = surface.say("Research")

        assert reply == "Where should I create the Research folder?"
        assert surface.admissions == [], "MissionService was entered without a location"
        assert surface.planner.calls == [], "the Planner was called without a location"
        assert surface.pending is not None

    def test_the_answer_resumes_the_same_objective(self):
        surface = Surface()
        surface.say("Create a folder")
        first_id = surface.pending.clarification_id

        surface.say("Research")
        surface.say("Desktop")

        assert len(surface.admissions) == 1, "the answer did not reach MissionService"
        assert len(surface.planner.calls) == 1, "the answer did not reach the Planner"
        admitted = surface.admissions[0]
        assert isinstance(admitted, Intent)
        assert admitted.goal == "Create folder 'Research'"
        assert admitted.context["folder_name"] == "Research"
        assert first_id  # the question carried a correlation identity

    def test_the_answer_never_becomes_a_mission_of_its_own(self):
        """The whole point. "Research" is a folder name, not an objective."""
        surface = Surface()
        surface.say("Create a folder")
        surface.say("Research")
        surface.say("Desktop")

        assert len(surface.admissions) == 1
        goals = [i.goal for i in surface.admissions]
        assert "Research" not in goals, "the answer was admitted as its own mission"
        assert "Desktop" not in goals, "the location answer became its own mission"

    def test_the_pending_question_is_cleared_once_answered(self):
        surface = Surface()
        surface.say("Create a folder")
        surface.say("Research")
        assert surface.pending is not None, "still missing the location"
        surface.say("Desktop")
        assert surface.pending is None

    def test_the_objective_reported_is_the_original_request(self):
        surface = Surface()
        surface.say("Create a folder")
        surface.say("Research")
        surface.say("Desktop")
        assert surface.status.objective == "Create a folder"


# =========================================================================
# B. Equivalence with the direct command
# =========================================================================


class TestB_ClarifiedEqualsDirect:

    def test_clarified_and_direct_produce_the_same_intent(self):
        """Two rounds of questions must land in the same place as saying
        it all at once. If they diverge, clarification is building a
        different Intent rather than resolving the founder's."""
        surface = Surface()
        surface.say("Create a folder")
        surface.say("Research")
        surface.say("Desktop")
        clarified = surface.admissions[0]

        direct = IntentLayer().parse("Create a folder called Research on Desktop").intent

        assert clarified.goal == direct.goal
        assert clarified.constraints == direct.constraints
        assert clarified.success_criteria == direct.success_criteria
        assert clarified.actor == direct.actor
        assert clarified.beneficiary == direct.beneficiary
        assert clarified.context["folder_name"] == direct.context["folder_name"]
        assert clarified.context["location"] == direct.context["location"]
        assert clarified.payload == direct.payload

    def test_the_clarified_intent_keeps_its_agency(self):
        surface = Surface()
        surface.say("Create a folder")
        surface.say("Research")
        surface.say("Desktop")
        assert surface.admissions[0].actor == SYSTEM

    @pytest.mark.parametrize("answer,location", [
        ("Call it Finance and put it in Documents", "Documents"),
        ("Name it Finance, then create it on Desktop", "Desktop"),
        ("Put it in Documents and call it Finance", "Documents"),
    ])
    def test_one_reply_can_resolve_every_missing_folder_field(
        self, answer, location,
    ):
        surface = Surface(IntentLayer(vocabularies={
            "location": ("Desktop", "Documents", "Downloads", "d_drive"),
        }))

        surface.say("Create a folder")
        surface.say(answer)

        assert len(surface.admissions) == 1
        assert len(surface.planner.calls) == 1
        admitted = surface.admissions[0]
        assert admitted.context["raw_input"] == "Create a folder"
        assert admitted.context["folder_name"] == "Finance"
        assert admitted.context["location"] == location
        assert admitted.payload == {"name": "Finance", "location": location}
        assert admitted.requirements

    def test_an_accounted_multi_field_answer_needs_no_model_call(self):
        class ReasonerSpy:
            def __init__(self):
                self.calls = 0

            def run(self, *_args, **_kwargs):
                self.calls += 1

        reasoner = ReasonerSpy()
        surface = Surface(IntentLayer(
            reasoner=reasoner,
            vocabularies={"location": ("desktop", "documents")},
        ))

        surface.say("Create a folder")
        surface.say("Call it Finance and put it in Documents")

        assert len(surface.admissions) == 1
        assert reasoner.calls == 0


# =========================================================================
# C. Optional fields are still the action's business
# =========================================================================


class TestC_NoInventedDefaults:
    """The principle is unchanged and its consequence has moved.

    Nothing may invent where a folder goes. Previously that meant the
    Intent stayed silent about location and `CreateFolderAction` applied
    its default downstream -- which is invention with an extra step, as
    the live session showed: Onkar got a Desktop folder he never asked
    for. Now not-inventing means *asking*.
    """

    def test_an_unstated_location_is_asked_for_rather_than_invented(self):
        surface = Surface()
        surface.say("Create a folder")
        surface.say("Research")

        assert surface.admissions == [], "admitted without a location"
        assert surface.pending is not None
        assert surface.pending.key == "location"

    def test_the_admitted_intent_carries_only_what_the_founder_said(self):
        surface = Surface()
        surface.say("Create a folder")
        surface.say("Research")
        surface.say("Documents")
        admitted = surface.admissions[0]

        assert admitted.context["location"] == "Documents"
        assert "Desktop" not in str(admitted.context), "a default overrode the founder"
        assert admitted.payload["location"] == "Documents"

    def test_a_request_missing_only_the_location_is_still_asked_about(self):
        """Superseded: this asserted that a name-only command asks
        nothing, because location was optional. It is required now."""
        surface = Surface()
        surface.say("Create a folder called Research")
        assert surface.pending is not None
        assert surface.pending.key == "location"
        assert surface.admissions == []

    def test_an_unresolved_personal_place_never_reaches_the_planner(self):
        surface = Surface(IntentLayer(vocabularies={
            "location": ("desktop", "documents", "downloads", "d_drive"),
        }))

        reply = surface.say(
            "create a folder called KVH_G where I normally keep these"
        )

        assert reply == "Where should I create the KVH_G folder?"
        assert surface.pending.key == "location"
        assert surface.pending.supplied == {"folder_name": "KVH_G"}
        assert surface.admissions == []
        assert surface.planner.calls == []

        surface.say("Documents")
        admitted = surface.admissions[0]
        assert admitted.payload == {"name": "KVH_G", "location": "documents"}


# =========================================================================
# D. Already-known information survives
# =========================================================================


class TestD_KnownInformationIsNotLost:

    def test_an_explicit_location_survives_the_clarification(self):
        """`"Create a folder in Documents"` matches neither name pattern,
        so before this the location was simply gone by the time the name
        arrived -- the founder had said where, and the folder would have
        been created somewhere else."""
        surface = Surface()
        question = surface.say("Create a folder in Documents")
        assert question == "What should the folder be called?"

        surface.say("Research")
        admitted = surface.admissions[0]

        assert admitted.context["location"] == "Documents"
        assert "Location: Documents" in admitted.constraints
        assert admitted.context["folder_name"] == "Research"

    def test_provenance_distinguishes_the_request_from_the_answer(self):
        surface = Surface()
        surface.say("Create a folder in Documents")
        surface.say("Research")
        context = surface.admissions[0].context

        assert context["raw_input"] == "Create a folder in Documents"
        assert context["clarified"] == {"folder_name": "Research"}


# =========================================================================
# E. The Planner block, stated as its own invariant
# =========================================================================


class TestE_PlannerBlockedUntilResolved:

    def test_zero_until_every_required_field_is_resolved(self):
        """The Planner is reached once, after the LAST missing field --
        not after the first answer. Two fields, two questions, one plan."""
        surface = Surface()

        surface.say("Create a folder")
        assert len(surface.planner.calls) == 0
        assert len(surface.admissions) == 0

        surface.say("Research")
        assert len(surface.planner.calls) == 0, "planned before the location was known"
        assert len(surface.admissions) == 0, "admitted before the location was known"

        surface.say("Desktop")
        assert len(surface.planner.calls) == 1
        assert len(surface.admissions) == 1

    def test_an_unanswerable_reply_still_does_not_reach_the_planner(self):
        """A blank answer names nothing. It must ask again rather than
        create a nameless folder -- a missing parameter is not permission
        to invent one."""
        surface = Surface()
        surface.say("Create a folder")
        reply = surface.say("   ")

        assert reply == "What should the folder be called?"
        assert surface.planner.calls == []
        assert surface.admissions == []
        assert surface.pending is not None, "the question was abandoned"
        assert surface.status.status == AWAITING_CLARIFICATION

    def test_re_asking_keeps_the_original_objective(self):
        surface = Surface()
        surface.say("Create a folder in Documents")
        surface.say("")
        assert surface.pending.objective == "Create a folder in Documents"

        surface.say("Research")
        assert surface.admissions[0].context["location"] == "Documents"


# =========================================================================
# F / G. Conversation is untouched
# =========================================================================


class TestFG_ConversationUnaffected:

    @pytest.mark.parametrize("text", ["Good morning", "What can you do?"])
    def test_conversation_is_handled_and_creates_nothing(self, text):
        turn = engine().reply(text, moment=T0)
        assert turn.disposition is Disposition.HANDLED
        assert turn.reply

    def test_no_pending_question_is_created_by_ordinary_work(self):
        surface = Surface()
        surface.say("Open github.com")
        assert surface.pending is None
        assert len(surface.admissions) == 1

    def test_a_greeting_cannot_be_eaten_as_an_answer(self):
        """The Conversation Engine runs BEFORE this function, so a
        greeting is HANDLED and never reaches the open question. That is
        an existing property of the architecture, and it is what makes
        "the next escalated message is the answer" a bounded rule rather
        than a trap."""
        assert engine().reply("Good morning", moment=T0).disposition is Disposition.HANDLED
        assert engine().reply(
            "What can you do?", moment=T0
        ).disposition is Disposition.HANDLED


# =========================================================================
# Transport
# =========================================================================


class TestClarificationTransport:
    """§20 -- the bridge must carry enough to RESUME, not just enough to
    display. Asserting `reply == "What should I call it?"` would pass
    against the old broken build."""

    def test_the_status_contract_carries_the_full_question(self):
        surface = Surface()
        surface.say("Create a folder")
        carried = surface.status.as_dict()["pending_clarification"]

        assert carried["question"] == "What should the folder be called?"
        assert carried["key"] == "folder_name", "the semantic key was dropped again"
        assert carried["required"] is True
        assert carried["options"] == []
        assert carried["gathering"] == ["folder_name", "location", "parent"]
        assert carried["clarification_id"]

    def test_the_key_travels_as_data_not_as_prose(self):
        """The key must not be recoverable only by re-reading the
        question text."""
        surface = Surface()
        surface.say("Create a folder")
        assert surface.pending.key == "folder_name"
        assert surface.pending.key not in surface.pending.question

    def test_options_are_preserved_when_a_question_has_them(self):
        """No producer populates `options` today, so this proves the
        TRANSPORT rather than a producer: a question that has them keeps
        them all the way to the founder-facing contract."""
        pending = PendingClarification(
            question="Which drive?", key="drive", objective="x",
            options=("C:", "D:"), required=False,
        )
        assert pending.as_dict()["options"] == ["C:", "D:"]
        assert pending.as_dict()["required"] is False

    def test_every_field_being_gathered_survives_the_surface_transport(self):
        surface = Surface()
        surface.say("Create a folder")

        assert surface.pending.gathering == (
            "folder_name", "location", "parent",
        )

    def test_free_text_answers_are_possible(self):
        """A finite option list must never be a precondition. This value
        appears in no list anywhere."""
        surface = Surface()
        surface.say("Create a folder")
        surface.say(r"D:\Projects\Research")
        surface.say("Desktop")
        assert surface.admissions[0].context["folder_name"] == r"D:\Projects\Research"

    def test_each_question_carries_its_own_identity(self):
        first, second = Surface(), Surface()
        first.say("Create a folder")
        second.say("Create a folder")
        assert first.pending.clarification_id != second.pending.clarification_id

    def test_a_new_objective_clears_any_stale_question(self):
        status = ExecutionStatus()
        status.pending_clarification = PendingClarification(
            question="q", key="k", objective="o",
        )
        status.begin("something else")
        assert status.pending_clarification is None


# =========================================================================
# The real clarify() is the one that runs
# =========================================================================


class TestIntentLayerClarifyIsTheProductionPath:

    def test_the_surface_calls_clarify_not_parse(self):
        import inspect

        source = inspect.getsource(kd._submit_objective)
        assert "intent_layer.clarify(" in source, (
            "the production path does not reach IntentLayer.clarify() -- "
            "clarification merging has been built somewhere else"
        )

    def test_clarify_is_reached_with_the_pending_question(self):
        calls = []

        class Recording(IntentLayer):
            def clarify(self, original, answer, question=None, supplied=None,
                        evidence=None):
                calls.append((original, answer, question))
                return super().clarify(original, answer, question, supplied)

        surface = Surface()
        surface.service.intent_layer = Recording()
        surface.say("Create a folder")
        surface.say("Research")

        assert len(calls) == 1
        original, answer, question = calls[0]
        assert original == "Create a folder"
        assert answer == "Research"
        assert isinstance(question, ClarificationQuestion)
        assert question.key == "folder_name"

    def test_clarify_fills_the_key_rather_than_rejoining_prose(self):
        """The rejoin could not resolve this case at all: "Create a
        folder Research" has no `called`, so the parser found no name."""
        layer = IntentLayer()
        question = layer.parse("Create a folder").clarification

        rejoined = layer.parse("Create a folder Research")
        assert rejoined.needs_clarification, (
            "this test's premise is gone -- the rejoin now works, so the "
            "key-based fix may no longer be what is being exercised"
        )

        # The key-based fill is what is under test, and it worked: the
        # name was taken from the answer rather than from prose. The
        # request is not finished, because a folder also needs a place --
        # and the question proves the name landed.
        keyed = layer.clarify("Create a folder", "Research", question)
        assert keyed.needs_clarification
        assert keyed.clarification.key == "location"
        assert "Research" in keyed.clarification.question

        finished = layer.clarify("Create a folder", "Desktop", keyed.clarification,
                                 supplied={"folder_name": "Research"})
        assert not finished.needs_clarification
        assert finished.intent.context["folder_name"] == "Research"

    def test_the_two_argument_form_still_works(self):
        """Callers with no question to hand keep the old behaviour."""
        result = IntentLayer().clarify("Create a folder called", "Research")
        assert result.needs_clarification, "the rejoin no longer resolves the name"
        assert result.clarification.key == "location"
        assert result.clarification.question == "Where should I create the Research folder?"


# =========================================================================
# Stated behaviour: what happens to an unrelated message while a question
# is open (§17), and how many questions one request can raise (§15)
# =========================================================================


class TestPendingConversationPolicy:
    """The rule is: **the next ESCALATED message answers the open
    question.** Conversation never escalates, so it can never be consumed.

    That boundary is not chosen here -- it falls out of the Conversation
    Engine running first, which is existing architecture. These tests pin
    the consequences in both directions so the behaviour is deterministic
    and recorded rather than discovered later by a founder.
    """

    def test_a_handled_turn_cannot_reach_an_open_question(self):
        """Greetings, status, activity, priority and capability questions
        are all HANDLED, so none of them can be eaten as a folder name."""
        for text in ("Good morning", "What can you do?", "How's the system?",
                     "What are you doing?", "What should I work on?"):
            assert engine().reply(text, moment=T0).disposition is Disposition.HANDLED, text

    def test_an_unrelated_escalated_question_is_NOT_taken_as_the_answer(self):
        """The limitation this used to assert is gone, and this is the
        test that was nominated to fail when it went.

        Its previous form pinned the opposite behaviour -- "What's the
        weather today?" became the folder's name -- and said so, adding:
        *"If this ever becomes wrong for the founder, this test is the
        place the decision gets revisited."* The founder's convergence
        brief revisited it: a pending clarification is CONTEXT and does
        not own the next utterance.

        A question is now read as a question. The open request is not
        abandoned and not answered with nonsense -- it is put back,
        intact, and the founder can still finish it.
        """
        surface = Surface()
        surface.say("Create a folder")
        reply = surface.say("What's the weather today?")

        assert "What should the folder be called?" in reply
        assert surface.pending is not None, "the open request was abandoned"
        assert surface.admissions == [], "a question was admitted as a mission"

        # And the original request is still finishable afterwards.
        surface.say("Research")
        surface.say("Desktop")
        assert len(surface.admissions) == 1
        assert surface.admissions[0].context["folder_name"] == "Research"

    def test_the_founder_is_never_trapped(self):
        """The failure this replaces was a loop with no exit: the rejoin
        could not resolve the answer, so the same question came back
        forever. Any non-empty answer now resolves or re-asks with the
        objective intact -- never both stuck and silent."""
        surface = Surface()
        surface.say("Create a folder")
        for _ in range(3):
            reply = surface.say("")
            assert reply == "What should the folder be called?"
            assert surface.pending is not None
        surface.say("Research")
        surface.say("Desktop")
        assert len(surface.planner.calls) == 1


class TestMultipleMissingFields:
    """§15 audit, recorded as executable fact rather than prose.

    Each parse returns at most ONE `ClarificationQuestion`; parsers
    needing two values either ask for both under a composite key
    (`rename_details`, `copy_details`, `move_details`) or ask in
    sequence. So there is still no interview engine and none is built.

    `CreateFolderIntent` is the sequential case, and it uses exactly the
    mechanism this note said a second required field would use if one
    were ever added: the loop re-evaluates the whole original sentence on
    every answer, so ask -> answer -> re-evaluate -> ask again resolves
    one logical Intent field by field. Answers accumulate on
    `PendingClarification.supplied`; without that the second round would
    re-parse the original sentence and lose the first answer.
    """

    def test_one_request_raises_at_most_one_question_at_a_time(self):
        layer = IntentLayer()
        for text in ("Create a folder", "Create a project", "read",
                     "delete", "list files", "search for"):
            result = layer.parse(text)
            if result.needs_clarification:
                assert isinstance(result.clarification, ClarificationQuestion)
                assert result.clarification.key, f"{text!r} asked without a key"

    def test_composite_questions_ask_for_everything_they_need_at_once(self):
        result = IntentLayer().parse("rename")
        assert result.needs_clarification
        assert result.clarification.key == "rename_details"
        assert "and" in result.clarification.question.lower()
