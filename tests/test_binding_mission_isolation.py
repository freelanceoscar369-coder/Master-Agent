"""A bound value may only come from the consuming Task's own Mission.

`_dependency_tasks()` searched every Objective for a matching `task_id`.
A dependency id is meaningful inside one Objective's DAG and nowhere
else, so Mission B's `depends_on: ["step_3"]` could be satisfied by
Mission A's `step_3` -- and Mission A's verified browser observation
could be written into Mission B's file. Every check the resolver makes
would pass: completed, has Evidence, verdict matched, result agrees with
observation. All true, about the wrong mission.

Step ids are contextual on purpose. Two missions each having a `step_3`
is normal, and the fix is scoping the lookup, not forcing the Planner to
mint globally unique ids.

Everything here uses the production JSON wire form for `input_bindings`,
because a previous round's tests used pre-parsed objects and passed
against code that could not run.
"""
from __future__ import annotations

import pytest

from master_agent.mission_control.capabilities import (
    CapabilityDescriptor,
    qualified_name,
)
from master_agent.mission_control.executives import ExecutiveHealth
from master_agent.mission_control.mission_control import MissionControl
from master_agent.mission_control.tasks import Objective, Task, TaskState
from master_agent.runtime.engine import RuntimeEngine
from master_agent.runtime.gateway import GatewayResult
from master_agent.verification.evidence import ExpectedOutcome

A_URL = "https://mission-a.test/"
B_URL = "https://mission-b.test/"

#: The production wire form -- plain JSON, exactly what translation copies
#: off a Step and what survives the bus and a restart.
URL_BINDING = {"content": {"from_step": {"step_id": "step_3", "field": "url"}}}


def evidence(url: str, evidence_id: str) -> dict:
    return {
        "evidence_id": evidence_id,
        "worker": "browser",
        "environment": "browser_environment",
        "captured_at": "2026-08-20T01:00:00+00:00",
        "expected": {"description": "observed", "checks": []},
        "observation": {"url": url},
        "verdict": "matched",
        "check_results": [],
        "errors": [],
    }


class Harness:
    """Two live Missions in one Mission Control, as production has."""

    def __init__(self) -> None:
        self.seen: dict = {}
        self.mc = MissionControl()
        for executive, capability in (("browser", "observe_browser"),
                                      ("filesystem", "write_file")):
            self.mc.register_executive(
                executive_id=executive, version="0.1.0",
                capabilities=[CapabilityDescriptor(
                    qualified_name=qualified_name(executive, capability),
                    executive_id=executive, capability=capability,
                )],
                health=ExecutiveHealth.HEALTHY,
            )
            self.mc.mark_executive_ready(executive)

        harness = self

        class Gate:
            def check(self, request):
                harness.seen["approval"] = dict(request.payload)

        class Gateway:
            def invoke(self, capability, payload):
                harness.seen.setdefault("invocations", []).append(dict(payload))
                return GatewayResult(success=True, output={"written": True})

            def verify(self, capability, payload, expected):
                harness.seen["verify"] = dict(payload)
                return None

        self.engine = RuntimeEngine(self.mc, approval_gate=Gate())
        self.engine.register_gateway("filesystem", Gateway())
        self.engine.register_gateway("browser", Gateway())

    def observer_mission(self, url: str, evidence_id: str) -> Objective:
        """A mission whose `step_3` observed `url`, verified."""
        objective = self.mc.submit_objective(Objective(
            description=f"observe {url}",
            tasks=[Task(capability="Browser.ObserveBrowser", task_id="step_3")],
        ))
        source = objective.task("step_3")
        source.state = TaskState.COMPLETED
        source.result = {"url": url}
        source.evidence = evidence(url, evidence_id)
        return objective

    def consumer_mission(self, url: str, evidence_id: str) -> Objective:
        """A mission with its OWN `step_3` and a `step_5` bound to it."""
        write = Task(
            capability="Filesystem.WriteFile", task_id="step_5",
            payload={"path": "out.txt", "location": "Desktop"},
            depends_on=["step_3"],
            expected_outcome=ExpectedOutcome(description="written"),
        )
        write.input_bindings = URL_BINDING
        objective = self.mc.submit_objective(Objective(
            description="write what step_3 saw",
            tasks=[
                Task(capability="Browser.ObserveBrowser", task_id="step_3"),
                write,
            ],
        ))
        source = objective.task("step_3")
        source.state = TaskState.COMPLETED
        source.result = {"url": url}
        source.evidence = evidence(url, evidence_id)
        return objective

    def run(self) -> None:
        for _ in range(8):
            if not self.engine.run_once():
                break


class TestTwoMissionsWithTheSameStepId:

    def test_the_consumer_uses_its_own_missions_value(self):
        harness = Harness()
        harness.observer_mission(A_URL, "ev-mission-a")       # registered FIRST
        consumer = harness.consumer_mission(B_URL, "ev-mission-b")
        harness.run()

        written = harness.seen["invocations"][-1]["content"]
        assert written == B_URL
        assert written != A_URL, "a value crossed a mission boundary"
        assert consumer.task("step_5").state is TaskState.COMPLETED

    def test_it_still_holds_when_the_other_mission_is_registered_last(self):
        """Reversed order. A "last write wins" dict would flip here."""
        harness = Harness()
        consumer = harness.consumer_mission(B_URL, "ev-mission-b")
        harness.observer_mission(A_URL, "ev-mission-a")       # registered LAST
        harness.run()

        written = harness.seen["invocations"][-1]["content"]
        assert written == B_URL
        assert written != A_URL
        assert consumer.task("step_5").state is TaskState.COMPLETED

    def test_both_missions_may_legitimately_contain_step_3(self):
        """The fix is scoping, not globally unique ids."""
        harness = Harness()
        a = harness.observer_mission(A_URL, "ev-mission-a")
        b = harness.consumer_mission(B_URL, "ev-mission-b")

        assert a.task("step_3").task_id == b.task("step_3").task_id == "step_3"
        assert a.objective_id != b.objective_id

    def test_provenance_names_the_consumers_own_evidence(self):
        harness = Harness()
        started: list = []
        from master_agent.mission_control.events import EventType

        harness.mc.bus.subscribe(started.append, EventType.TASK_STARTED)
        harness.observer_mission(A_URL, "ev-mission-a")
        harness.consumer_mission(B_URL, "ev-mission-b")
        harness.run()

        events = [e for e in started if e.task_id == "step_5"]
        assert events, "step_5 never started"
        provenance = (events[-1].payload or {}).get("input_provenance")
        assert provenance, "no provenance recorded"

        ids = {s["evidence_id"] for s in provenance[0]["sources"]}
        assert ids == {"ev-mission-b"}
        assert "ev-mission-a" not in ids, "provenance points at another mission"

    def test_the_consuming_mission_is_identifiable_from_the_event(self):
        """Provenance is unambiguous by containment: the event carries the
        objective, so each record need not repeat it."""
        harness = Harness()
        started: list = []
        from master_agent.mission_control.events import EventType

        harness.mc.bus.subscribe(started.append, EventType.TASK_STARTED)
        harness.observer_mission(A_URL, "ev-mission-a")
        consumer = harness.consumer_mission(B_URL, "ev-mission-b")
        harness.run()

        event = [e for e in started if e.task_id == "step_5"][-1]
        assert event.objective_id == consumer.objective_id


class TestOwnershipMustBeEstablished:

    def test_a_task_whose_mission_is_unknown_cannot_resolve_bindings(self):
        """No guessing: a task Mission Control does not own has no
        answerable `step_3`, so it fails before approval or invocation."""
        harness = Harness()
        harness.observer_mission(A_URL, "ev-mission-a")

        orphan = Task(
            capability="Filesystem.WriteFile", task_id="step_5",
            payload={"path": "out.txt"}, depends_on=["step_3"],
            expected_outcome=ExpectedOutcome(description="written"),
        )
        orphan.input_bindings = URL_BINDING
        orphan.assigned_executive = "filesystem"

        harness.engine._handle_task(orphan)

        assert "approval" not in harness.seen, "approved an unresolvable payload"
        assert "invocations" not in harness.seen, "executed before resolving inputs"


class TestNoGlobalLookupRemains:

    def test_dependency_lookup_requires_an_objective(self):
        import inspect

        from master_agent.runtime.engine import RuntimeEngine

        signature = inspect.signature(RuntimeEngine._dependency_tasks)
        assert "objective_id" in signature.parameters, (
            "dependency lookup is not scoped to a Mission"
        )

    def test_ownership_is_decided_by_identity_not_by_id(self):
        """Two tasks sharing an id must not be confusable."""
        harness = Harness()
        a = harness.observer_mission(A_URL, "ev-mission-a")
        b = harness.consumer_mission(B_URL, "ev-mission-b")

        assert harness.engine._objective_of(a.task("step_3")) == a.objective_id
        assert harness.engine._objective_of(b.task("step_3")) == b.objective_id
