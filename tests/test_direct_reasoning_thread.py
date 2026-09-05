"""The Reasoning thread a DIRECT mission owns.

A material mission must be able to say what it decided and why. That has
to be as true of the missions that decide instantly as of the ones that
deliberate -- otherwise the fastest, cheapest, most certain missions are
the only ones that reach the founder unable to account for themselves,
and from outside that is indistinguishable from never having thought.

Measured live 2026-09-05: the SIMPLE anchor executed correctly, verified
both steps, produced the exact artifact, and created no decision record
at all. Correct work is not acceptance.
"""
from __future__ import annotations

from master_agent.brain.deliberation import DIRECT, direct_decision_record
from master_agent.mission_control.events import EventType


class _Bus:
    def __init__(self):
        self.events = []

    def publish(self, event):
        self.events.append(event)

    def of(self, event_type):
        return [e for e in self.events if e.event_type == event_type]


class _MissionControl:
    def __init__(self, bus):
        self.bus = bus


def _service(bus):
    """A MissionService with only what these tests touch."""
    from master_agent.missions.service import MissionService

    return MissionService(
        planner=object(), mission_control=_MissionControl(bus),
        intent_layer=object(),
    )


class _Intent:
    def __init__(self, eligible=True, requirements=()):
        self.goal = "Ensure a folder R exists on my Desktop."
        self.requirements = requirements
        self.context = {}
        if eligible:
            self.context["direct_eligibility"] = {
                "eligible": True, "model_required": False,
                "effects": ["The folder R exists in desktop."],
            }


class _Requirement:
    requirement_id = "req_1"
    description = "The folder R exists in desktop."


class TestADirectMissionOwnsAReasoningThread:

    def test_a_direct_mission_creates_a_thread(self):
        bus = _Bus()
        service = _service(bus)
        intent = _Intent(requirements=(_Requirement(),))

        record = service._record_direct_decision(intent, "plan-1", None, intent.goal)

        assert record is not None
        assert bus.of(EventType.MISSION_DECISION_RECORDED), "nothing was published"

    def test_the_depth_is_direct(self):
        service = _service(_Bus())
        record = service._record_direct_decision(_Intent(), "plan-1", None, "obj")
        assert record["depth"] == DIRECT

    def test_no_model_was_required(self):
        service = _service(_Bus())
        record = service._record_direct_decision(_Intent(), "plan-1", None, "obj")
        assert record["model_required"] is False
        assert record["uncertainty"] == "NONE"

    def test_no_reasoning_provider_is_invoked(self):
        """The decision being recorded is that none was needed. Consulting
        one to say so would be self-refuting."""
        class _Exploding:
            def run(self, *a, **k):
                raise AssertionError("a provider was consulted for a DIRECT mission")

        service = _service(_Bus())
        service.runner = _Exploding()
        record = service._record_direct_decision(_Intent(), "plan-1", None, "obj")
        assert record is not None

    def test_the_record_exists_before_execution(self):
        """Published at the decision, not rebuilt from the outcome. A record
        assembled after a success is a rationalisation."""
        bus = _Bus()
        service = _service(bus)
        service._record_direct_decision(_Intent(), "plan-1", None, "obj")

        published = bus.of(EventType.MISSION_DECISION_RECORDED)
        assert published, "the thread must exist before anything runs"
        assert not bus.of(EventType.TASK_STARTED)
        assert published[0].payload["status"] == "decided"

    def test_the_record_carries_the_mission_id(self):
        service = _service(_Bus())
        record = service._record_direct_decision(_Intent(), "plan-1", "mission-a", "obj")
        assert record["mission_id"] == "mission-a"

    def test_a_second_mission_gets_a_new_thread_id(self):
        service = _service(_Bus())
        first = service._record_direct_decision(_Intent(), "plan-1", "m1", "obj")
        second = service._record_direct_decision(_Intent(), "plan-2", "m2", "obj")
        assert first["reasoning_thread_id"] != second["reasoning_thread_id"]

    def test_a_previous_missions_thread_cannot_be_reused(self):
        """Retrieval is by mission id and only by mission id. A thread
        fetchable without naming the mission is one that can be handed to
        the wrong mission -- the stale-record defect this system has
        already paid for once."""
        service = _service(_Bus())
        first = service._record_direct_decision(_Intent(), "plan-1", "m1", "obj")
        service._threads["m1"] = first

        assert service.reasoning_thread("m2") is None
        assert service.reasoning_thread("m1")["reasoning_thread_id"] == (
            first["reasoning_thread_id"]
        )

    def test_verified_completion_updates_the_same_thread(self):
        bus = _Bus()
        service = _service(bus)
        record = service._record_direct_decision(_Intent(), "plan-1", "m1", "obj")
        service._threads["m1"] = record

        closed = service.note_mission_outcome(
            "m1", status="completed", verification="matched",
        )

        assert closed["reasoning_thread_id"] == record["reasoning_thread_id"], (
            "completion must update the SAME thread, never open a second"
        )
        assert closed["status"] == "completed"
        assert closed["verification"] == "matched"

    def test_an_ineligible_mission_records_nothing(self):
        """This is for DIRECT missions. A mission that genuinely needed a
        model has its own deliberation record and must not get this one."""
        service = _service(_Bus())
        assert service._record_direct_decision(
            _Intent(eligible=False), "plan-1", None, "obj",
        ) is None


class TestTheRecordIsProductSafe:

    def test_it_states_what_and_why_without_a_transcript(self):
        record = direct_decision_record(
            thread_id="t", objective="obj", created_at="now",
        )
        assert record["decision"]
        assert record["why"]
        assert "prompt" not in record
        assert "reasoning" not in " ".join(
            k for k in record if k != "reasoning_thread_id"
        )
