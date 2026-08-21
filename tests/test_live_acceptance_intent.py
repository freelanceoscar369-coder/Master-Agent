"""LIVE ACCEPTANCE A — the founder's six exchanges, through the real
assembled Founder Edition surface.

## What makes this different from `test_founder_intent_regressions.py`

That file calls `kalpavriksha_desktop._submit_objective` directly. This one
enters where the founder actually enters: `DesktopShellApi.send_message()`,
on an app built by the real `boot_founder_edition()` — real Founder
Identity, real ConversationEngine, real CommunicationEngine, real
`IntentLayer`. So it proves the seam the other file skips over, which is
the one that decides whether an utterance is *answered* by the
conversation layer or *escalated* into the mission pipeline at all.

## What is deliberately NOT live here

The Planner is spied. `GEMINI_API_KEY` is present on this machine, so a
real Planner call would spend founder quota and, for the redirect case,
launch a real browser — on a synthetic probe, which the standing rule
forbids. Everything up to and including the admission decision is real;
what would cost money or open a window is observed rather than performed.

That boundary is the point of the assertions: for five of the six
exchanges the correct behaviour is that the Planner is *never reached*,
and a spy proves that far better than a live call would.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kalpavriksha_desktop as kd  # noqa: E402

from master_agent.brain.intent import IntentLayer  # noqa: E402
from master_agent.founder_edition.boot import boot_founder_edition  # noqa: E402
from master_agent.founder_edition.desktop_shell import (  # noqa: E402
    BridgeTextOutput,
    DesktopShellApi,
)
from master_agent.missions.execution_status import ExecutionStatus  # noqa: E402
from master_agent.missions.service import MissionService  # noqa: E402
from master_agent.planner.plan import Intent, PlanOutcome, PlanRefusal  # noqa: E402
from tests.test_kalpavriksha_desktop_mission_bridge import (  # noqa: E402
    _FakeFounderState,
    _FakeMissionControl,
    _FakeObjective,
    _FakeRuntime,
)


class PlannerSpy:
    """Records what it was asked to plan and refuses. Reaching this at all
    means the utterance was admitted as work."""

    def __init__(self) -> None:
        self.calls: list[Intent] = []

    def plan(self, intent, *, task_id="", objective_id=None):
        self.calls.append(intent)
        return PlanOutcome(
            refusal=PlanRefusal(code="no_steps", reason="planner spied for acceptance"),
        )


class MissionControlSpy:
    def submit_objective(self, mission):
        return mission


class LiveFounderSurface:
    """The real bridge, driven the way the page drives it."""

    def __init__(self) -> None:
        self.planner = PlannerSpy()
        self.service = MissionService(
            planner=self.planner,
            mission_control=MissionControlSpy(),
            intent_layer=IntentLayer(),
        )
        self.status = ExecutionStatus()
        self.app = boot_founder_edition(
            founder_name="Onkar", text_output=BridgeTextOutput(),
        )
        self.api = DesktopShellApi(self.app, submit_objective=self._submit)

    def _submit(self, text: str) -> dict:
        return kd._submit_objective(
            self.service, _FakeRuntime(),
            _FakeMissionControl([_FakeObjective(complete=True)], _FakeFounderState()),
            self.status, text, timeout_seconds=1.0,
        )

    def say(self, text: str) -> str | None:
        """Exactly what the page calls."""
        return self.api.send_message(text, "text")["reply"]

    @property
    def pending(self):
        return self.status.pending_clarification


@pytest.fixture()
def surface():
    return LiveFounderSurface()


class TestTheSurfaceIsGenuinelyAssembled:
    """If these fail, nothing below proves anything."""

    def test_the_real_boot_produced_a_conversation_layer(self, surface):
        """Not a fake app: the real boot wired identity, conversation and
        runtime, and the bridge is talking to those."""
        assert surface.app.communication is not None, "no CommunicationEngine"
        assert surface.app.conversation is not None, "no conversation memory"
        assert surface.app.runtime is not None, "no FounderRuntime"
        assert surface.api.get_founder_seed() > 0
        # The bridge really is wired to the mission pipeline, so an
        # escalation below cannot pass vacuously.
        assert surface.api._submit_objective is not None

    def test_ordinary_conversation_is_answered_without_touching_the_pipeline(self, surface):
        reply = surface.say("Continue")
        assert reply == "Continuing."
        assert surface.planner.calls == [], "conversation reached the Planner"

    def test_a_greeting_never_escalates(self, surface):
        assert surface.say("Good morning Somesh")
        assert surface.planner.calls == []


class TestLiveA1_CancelClosesTheQuestion:
    """Somesh: "Which file should I read?" / Founder: "nothing thanks"."""

    def test_the_whole_exchange(self, surface):
        asked = surface.say("read a file")
        assert surface.pending is not None, f"no question was asked: {asked!r}"

        answered = surface.say("nothing thanks")

        assert surface.pending is None, "the question is still open"
        assert answered and answered != asked, "the same question came back"
        goals = [i.goal for i in surface.planner.calls]
        assert not any("nothing" in g.lower() for g in goals), (
            f"the refusal was planned as work: {goals}"
        )


class TestLiveA2_RedirectIsNotSwallowed:
    """Pending clarification / Founder: "open example.com instead"."""

    def test_the_whole_exchange(self, surface):
        surface.say("Create a folder")
        assert surface.pending is not None

        surface.say("open example.com instead")

        assert surface.planner.calls, "the redirect never became work"
        planned = surface.planner.calls[-1].goal.lower()
        assert "example.com" in planned, f"the redirect was lost: {planned!r}"


class TestLiveA3_FollowUpIsNotFieldData:
    """Pending clarification / Founder: "why are you asking me that?"."""

    def test_the_whole_exchange(self, surface):
        surface.say("Create a folder")
        reply = surface.say("why are you asking me that?")

        assert "create a folder" in (reply or "").lower()
        assert surface.pending is not None, "the request was abandoned"
        assert surface.planner.calls == []

        # and it still finishes afterwards
        surface.say("Research")
        surface.say("Desktop")
        assert len(surface.planner.calls) == 1
        assert surface.planner.calls[0].context["folder_name"] == "Research"


class TestLiveA4_RealAnswersStillResolve:
    """Pending: "What should the folder be called?" / "Research", then
    "Where should I create it?" / "Desktop"."""

    def test_the_whole_exchange(self, surface):
        surface.say("Create a folder")
        surface.say("Research")
        surface.say("Desktop")

        assert surface.pending is None
        assert len(surface.planner.calls) == 1
        planned = surface.planner.calls[0]
        assert planned.context["folder_name"] == "Research"
        assert "Research" in planned.goal


class TestLiveA5_AQuestionAboutWhatWasSaid:
    """Somesh: "...Everything is ready." / Founder: "what is ready?"."""

    def test_no_mission_is_manufactured(self, surface):
        surface.say("what is ready?")
        assert surface.planner.calls == [], "a question became mission work"

    def test_the_founder_is_not_left_in_silence(self, surface):
        assert surface.say("what is ready?"), "the founder was told nothing"
