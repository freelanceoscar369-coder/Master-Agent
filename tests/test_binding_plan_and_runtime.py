"""Plan-time refusal, and the one payload that reaches all three boundaries.

Two halves of the same guarantee:

* a plan that would guess a dependency value is refused before a mission
  exists, rather than discovered when a file already holds the wrong text;
* the values the founder approved are the values written, and the values
  verified. Approving a placeholder, writing something else and verifying
  a third thing would make each boundary individually true and the whole
  meaningless.
"""
from __future__ import annotations

import json

import pytest

from master_agent.planner.catalogue import CapabilityOption
from master_agent.planner.parsing import validate

OBSERVE = CapabilityOption(
    name="Browser.ObserveBrowser",
    description="Capture a generic observation of a browser session.",
    required_args=("session_id",),
    args_complete=True,
    output_fields=("url", "title"),
)
WRITE = CapabilityOption(
    name="Filesystem.WriteFile",
    description="Write text content to a file.",
    required_args=("path",),
    optional_args=("location", "content"),
    args_complete=True,
)
FOLDER = CapabilityOption(
    name="Filesystem.CreateFolder",
    description="Create a folder.",
    required_args=("name",),
    optional_args=("location",),
    args_complete=True,
    output_fields=(),          # publishes no outputs
)
OPTIONS = (OBSERVE, WRITE, FOLDER)

CONTENT_BINDING = {"concat": [
    {"literal": "Title: "},
    {"from_step": {"step_id": "step_3", "field": "title"}},
    {"literal": "\nURL: "},
    {"from_step": {"step_id": "step_3", "field": "url"}},
]}


def success(text="ok"):
    return {"description": text, "must_contain": [], "must_exclude": [],
            "must_be_json": False, "must_have_fields": [], "min_words": 0}


def document(write_step: dict, extra_steps: list | None = None) -> dict:
    steps = [
        {"id": "step_3", "capability": "Browser.ObserveBrowser",
         "payload": {"session_id": "s1"}, "depends_on": [], "success": success()},
    ]
    steps.extend(extra_steps or [])
    steps.append(write_step)
    return {"steps": steps}


def refusal_of(write_step, extra_steps=None):
    plan_obj, refusal = validate(document(write_step, extra_steps), options=OPTIONS)
    assert plan_obj is None, "expected a refusal, got a plan"
    return refusal


def accepted(write_step, extra_steps=None):
    plan_obj, refusal = validate(document(write_step, extra_steps), options=OPTIONS)
    assert plan_obj is not None, f"expected a plan, refused: {getattr(refusal, 'detail', refusal)}"
    return plan_obj


VALID_WRITE = {
    "id": "step_5", "capability": "Filesystem.WriteFile",
    "payload": {"path": "KV/page_info.txt", "location": "Desktop"},
    "input_bindings": {"content": CONTENT_BINDING},
    "depends_on": ["step_3"], "success": success(),
}


class TestPlanTimeValidation:
    """Cases A-H of the required matrix."""

    def test_a_valid_medium_binding_is_accepted(self):
        built = accepted(VALID_WRITE)
        step = next(s for s in built.steps if s.step_id == "step_5")

        assert "content" not in step.payload, (
            "the plan carries a predicted value for a bound argument"
        )
        assert "content" in step.input_bindings

    def test_a_literal_and_a_binding_for_one_argument_is_refused(self):
        bad = dict(VALID_WRITE)
        bad["payload"] = {**VALID_WRITE["payload"], "content": "Example Domain"}
        assert "twice" in refusal_of(bad).reason

    def test_a_binding_to_a_missing_step_is_refused(self):
        bad = dict(VALID_WRITE)
        bad["input_bindings"] = {
            "content": {"from_step": {"step_id": "ghost", "field": "url"}}
        }
        bad["depends_on"] = ["ghost"]
        assert refusal_of(bad) is not None

    def test_a_binding_to_a_step_outside_depends_on_is_refused(self):
        """A binding may read a dependency; it may not create one."""
        bad = dict(VALID_WRITE)
        bad["depends_on"] = []
        assert "does not depend on" in refusal_of(bad).reason

    def test_an_unpublished_output_field_is_refused(self):
        bad = dict(VALID_WRITE)
        bad["input_bindings"] = {
            "content": {"from_step": {"step_id": "step_3", "field": "invented"}}
        }
        assert "not published" in refusal_of(bad).reason

    def test_a_source_publishing_no_outputs_is_refused(self):
        """`CreateFolder` declares none, so any field would be a guess."""
        folder = {"id": "step_4", "capability": "Filesystem.CreateFolder",
                  "payload": {"name": "KV"}, "depends_on": [], "success": success()}
        bad = dict(VALID_WRITE)
        bad["input_bindings"] = {
            "content": {"from_step": {"step_id": "step_4", "field": "path"}}
        }
        bad["depends_on"] = ["step_4"]
        assert "publishes no outputs" in refusal_of(bad, [folder]).reason

    def test_a_required_argument_may_be_satisfied_by_a_binding(self):
        """`path` is required; supplying it by binding must be accepted,
        or the contract refuses the plans it exists to allow."""
        step = {
            "id": "step_5", "capability": "Filesystem.WriteFile",
            "payload": {"location": "Desktop"},
            "input_bindings": {
                "path": {"from_step": {"step_id": "step_3", "field": "title"}}
            },
            "depends_on": ["step_3"], "success": success(),
        }
        assert accepted(step) is not None

    def test_a_plan_with_no_bindings_is_unaffected(self):
        step = {
            "id": "step_5", "capability": "Filesystem.WriteFile",
            "payload": {"path": "a.txt", "location": "Desktop", "content": "hi"},
            "depends_on": [], "success": success(),
        }
        built = accepted(step)
        assert next(s for s in built.steps if s.step_id == "step_5").input_bindings == {}

    def test_a_malformed_binding_is_refused(self):
        bad = dict(VALID_WRITE)
        bad["input_bindings"] = {"content": {"concat": []}}
        assert refusal_of(bad) is not None


class TestTranslationIsLossless:

    def test_bindings_reach_the_task_unresolved(self):
        from master_agent.missions.translation import task_from_step

        step = next(s for s in accepted(VALID_WRITE).steps if s.step_id == "step_5")
        task = task_from_step(step)

        assert task.input_bindings == step.input_bindings
        assert "content" not in task.payload, "translation resolved a binding"


class TestOneResolvedPayloadReachesEveryBoundary:
    """Approval, execution and verification must see the same values."""

    def _engine_with(self, seen: dict):
        from master_agent.mission_control.mission_control import MissionControl
        from master_agent.runtime.engine import RuntimeEngine
        from master_agent.verification.evidence import ExpectedOutcome

        class Gate:
            def check(self, request):
                seen["approval"] = dict(request.payload)

        class Gateway:
            def invoke(self, capability, payload):
                from master_agent.runtime.gateway import GatewayResult

                seen.setdefault("invocations", []).append(dict(payload))
                return GatewayResult(success=True, output={"written": True})

            def verify(self, capability, payload, expected):
                seen["verify"] = dict(payload)
                return None

        mc = MissionControl()
        from master_agent.mission_control.events import EventType

        mc.bus.subscribe(
            lambda e: seen.setdefault("started", []).append(e),
            EventType.TASK_STARTED,
        )
        engine = RuntimeEngine(mc, approval_gate=Gate())
        engine.register_gateway("filesystem", Gateway())
        return mc, engine, ExpectedOutcome

    def _run(self, seen, *, bindings=True):
        from master_agent.mission_control.capabilities import (
            CapabilityDescriptor,
            qualified_name,
        )
        from master_agent.mission_control.executives import ExecutiveHealth
        from master_agent.capabilities.input_bindings import bindings_from_dict
        from master_agent.mission_control.tasks import Objective, Task

        mc, engine, ExpectedOutcome = self._engine_with(seen)
        for executive, capability in (("browser", "observe_browser"),
                                      ("filesystem", "write_file")):
            mc.register_executive(
                executive_id=executive, version="0.1.0",
                capabilities=[CapabilityDescriptor(
                    qualified_name=qualified_name(executive, capability),
                    executive_id=executive, capability=capability,
                )],
                health=ExecutiveHealth.HEALTHY,
            )
            mc.mark_executive_ready(executive)

        write = Task(
            capability="Filesystem.WriteFile", task_id="step_5",
            payload={"path": "KV/page_info.txt", "location": "Desktop"},
            depends_on=["step_3"],
            expected_outcome=ExpectedOutcome(description="written"),
        )
        if bindings:
            # THE PRODUCTION WIRE FORM: plain JSON, exactly what translation
            # copies off a Step and what survives the bus and a restart.
            #
            # This used to pass `bindings_from_dict(...)` -- Binding objects
            # the tests built and production never sends. Everything passed
            # and the first live mission died on
            # `'dict' object has no attribute 'ref'`.
            write.input_bindings = {"content": CONTENT_BINDING}

        objective = mc.submit_objective(Objective(
            description="medium", tasks=[
                Task(capability="Browser.ObserveBrowser", task_id="step_3"),
                write,
            ],
        ))

        source = objective.task("step_3")
        source.state = type(source.state).COMPLETED
        source.result = {"url": "https://example.com/", "title": "Example Domain"}
        source.evidence = {
            "evidence_id": "ev1", "worker": "browser",
            "environment": "browser_environment",
            "captured_at": "2026-08-19T18:00:00+00:00",
            "expected": {"description": "d", "checks": []},
            "observation": {"url": "https://example.com/", "title": "Example Domain"},
            "verdict": "matched", "check_results": [], "errors": [],
        }

        # Driven through the real cycle rather than by calling the
        # handler directly -- the engine's own state machine is part of
        # what makes the boundaries happen in order.
        for _ in range(6):
            if not engine.run_once():
                break
        return objective

    EXPECTED = "Title: Example Domain\nURL: https://example.com/"

    def test_approval_sees_the_resolved_values(self):
        seen: dict = {}
        self._run(seen)
        assert seen["approval"]["content"] == self.EXPECTED

    def test_execution_sees_the_resolved_values(self):
        seen: dict = {}
        self._run(seen)
        assert seen["invocations"][0]["content"] == self.EXPECTED

    def test_verification_sees_the_resolved_values(self):
        seen: dict = {}
        self._run(seen)
        assert seen["verify"]["content"] == self.EXPECTED, (
            "verification checked a payload nobody executed"
        )

    def test_all_three_boundaries_agree(self):
        seen: dict = {}
        self._run(seen)
        assert seen["approval"] == seen["invocations"][0] == seen["verify"]

    def test_the_stored_task_payload_is_never_rewritten(self):
        seen: dict = {}
        objective = self._run(seen)
        assert "content" not in objective.task("step_5").payload

    def test_the_task_started_event_carries_provenance(self):
        seen: dict = {}
        self._run(seen)
        started = [e for e in seen.get("started", []) if e.task_id == "step_5"]
        assert started, "step_5 never started"
        provenance = (started[-1].payload or {}).get("input_provenance")
        assert provenance, "a bound task started without recording where its input came from"
        assert provenance[0]["target"] == "content"
        assert {s["step_id"] for s in provenance[0]["sources"]} == {"step_3"}
        assert {s["field"] for s in provenance[0]["sources"]} == {"title", "url"}
        assert all(s["evidence_id"] == "ev1" for s in provenance[0]["sources"])

    def test_a_binding_failure_stops_before_any_side_effect(self):
        """No approval, no invoke -- the failure happens first."""
        from master_agent.mission_control.capabilities import (
            CapabilityDescriptor,
            qualified_name,
        )
        from master_agent.mission_control.executives import ExecutiveHealth
        from master_agent.capabilities.input_bindings import bindings_from_dict
        from master_agent.mission_control.tasks import Objective, Task
        from master_agent.verification.evidence import ExpectedOutcome

        seen: dict = {}
        mc, engine, _ = self._engine_with(seen)
        mc.register_executive(
            executive_id="filesystem", version="0.1.0",
            capabilities=[CapabilityDescriptor(
                qualified_name=qualified_name("filesystem", "write_file"),
                executive_id="filesystem", capability="write_file",
            )],
            health=ExecutiveHealth.HEALTHY,
        )
        mc.mark_executive_ready("filesystem")

        write = Task(
            capability="Filesystem.WriteFile", task_id="step_5",
            payload={"path": "a.txt"}, depends_on=["step_3"],
            expected_outcome=ExpectedOutcome(description="written"),
        )
        write.input_bindings = {"content": CONTENT_BINDING}
        objective = mc.submit_objective(Objective(
            description="x", tasks=[
                Task(capability="Filesystem.WriteFile", task_id="step_3"), write,
            ],
        ))
        # step_3 completes with NO Evidence -- the value may not flow.
        source = objective.task("step_3")
        source.state = type(source.state).COMPLETED
        source.result = {"url": "u", "title": "t"}

        for _ in range(6):
            if not engine.run_once():
                break

        assert "approval" not in seen, "approved a payload that could not resolve"
        assert "invocations" not in seen, "executed before resolving inputs"
        assert objective.task("step_5").state.value == "failed"
