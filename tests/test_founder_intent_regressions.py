"""The founder's exact Intent regressions, driven through the real
composition root.

`tests/test_utterance_role.py` proves the Brain's role decision in
isolation. This file proves the same six exchanges end to end through
`kalpavriksha_desktop._submit_objective` -- with a real `IntentLayer`, a
real `MissionService`, and a spied Planner, so "the Planner was never
called" is recorded evidence rather than an assumption.

The rig is `tests/test_clarification_round_trip.Surface`, reused rather
than rebuilt: a second harness for the same entry point would be a second
place for the two to disagree about what production does.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from master_agent.missions.execution_status import (  # noqa: E402
    AWAITING_CLARIFICATION,
    TERMINAL_STATUSES,
)
from tests.test_clarification_round_trip import Surface  # noqa: E402


class TestCancellingAnOpenQuestion:
    """Somesh: "Which file should I read?" / Founder: "nothing thanks"."""

    def test_nothing_thanks_does_not_become_a_filename(self):
        surface = Surface()
        surface.say("read a file")
        assert surface.pending is not None, "precondition: a question is open"

        surface.say("nothing thanks")

        goals = [intent.goal for intent in surface.admissions]
        assert not any("nothing" in goal.lower() for goal in goals), (
            f"the refusal was admitted as an objective: {goals}"
        )
        assert surface.planner.calls == [], "the Planner was asked to plan a refusal"

    def test_the_question_is_not_asked_again(self):
        surface = Surface()
        first = surface.say("read a file")
        second = surface.say("nothing thanks")

        assert second != first, "the same question came back"
        assert "which file" not in second.lower()

    def test_the_pending_work_is_closed(self):
        surface = Surface()
        surface.say("read a file")
        surface.say("nothing thanks")

        assert surface.pending is None, "the abandoned question is still open"

    def test_nothing_is_reported_as_completed_or_failed(self):
        """No mission was ever created -- clarification happens before
        `MissionService.start()` -- so neither terminal status is true."""
        surface = Surface()
        surface.say("read a file")
        surface.say("nothing thanks")

        assert surface.status.status not in TERMINAL_STATUSES
        assert surface.admissions == []


class TestRedirectingWhileAQuestionIsOpen:
    """Pending clarification / Founder: "open example.com instead"."""

    def test_the_old_question_does_not_hijack_the_new_request(self):
        surface = Surface()
        surface.say("Create a folder")
        assert surface.pending is not None

        surface.say("open example.com instead")

        assert surface.planner.calls, "the redirect never reached the Planner"
        planned = surface.planner.calls[-1].goal.lower()
        assert "example.com" in planned, f"the redirect was lost: {planned!r}"

    def test_the_redirect_is_not_stored_as_a_folder_name(self):
        surface = Surface()
        surface.say("Create a folder")
        surface.say("open example.com instead")

        for intent in surface.admissions:
            assert intent.context.get("folder_name") != "open example.com instead"

    def test_the_abandoned_question_does_not_linger(self):
        surface = Surface()
        surface.say("Create a folder")
        surface.say("open example.com instead")

        pending = surface.pending
        if pending is not None:
            assert "folder" not in pending.question.lower(), (
                "the redirected-away question is still waiting"
            )


class TestAskingAboutTheQuestion:
    """Pending clarification / Founder: "why are you asking me that?"."""

    def test_the_follow_up_is_not_stored_as_field_data(self):
        surface = Surface()
        surface.say("Create a folder")
        surface.say("why are you asking me that?")

        for intent in surface.admissions:
            assert "why are you asking" not in str(intent.context).lower()
        assert surface.planner.calls == []

    def test_the_founder_is_told_why(self):
        surface = Surface()
        surface.say("Create a folder")
        reply = surface.say("why are you asking me that?")

        assert "create a folder" in reply.lower(), (
            "the answer did not say what it was blocked on"
        )

    def test_the_open_request_survives_the_interruption(self):
        """Asking why must not abandon what the founder asked for."""
        surface = Surface()
        surface.say("Create a folder")
        surface.say("why are you asking me that?")

        assert surface.pending is not None
        assert surface.status.status == AWAITING_CLARIFICATION

        surface.say("Research")
        surface.say("Desktop")
        assert len(surface.admissions) == 1
        assert surface.admissions[0].context["folder_name"] == "Research"


class TestRealAnswersStillWork:
    """The regressions must not be fixed by breaking the ordinary path."""

    def test_a_name_answer_is_still_an_answer(self):
        surface = Surface()
        surface.say("Create a folder")
        surface.say("Research")
        surface.say("Desktop")

        assert len(surface.admissions) == 1
        assert surface.admissions[0].context["folder_name"] == "Research"

    def test_a_location_answer_is_still_an_answer(self):
        surface = Surface()
        surface.say("Create a folder")
        surface.say("Research")
        reply = surface.say("Desktop")

        assert surface.pending is None
        assert reply


class TestAQuestionAboutWhatJustHappened:
    """Somesh: "...Everything is ready." / Founder: "what is ready?"

    Nothing is pending, so this is not a clarification answer. It must not
    become mission work either.
    """

    def test_no_mission_is_manufactured_from_a_question(self):
        surface = Surface()
        surface.say("what is ready?")

        assert surface.admissions == [], "a question became a mission"
        assert surface.planner.calls == [], "a question reached the Planner"

    def test_the_founder_gets_an_answer_rather_than_silence(self):
        surface = Surface()
        reply = surface.say("what is ready?")

        assert reply, "the founder was told nothing at all"
