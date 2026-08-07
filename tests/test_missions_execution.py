"""Mission Brief 037 — the plan actually running, through the real Runtime.

The claims this file exists for:

- A step is verified **before** it completes, so a dependent step can
  never unlock on unverified work.
- A verification failure fails the task, and nothing repairs it.
- The Runtime never infers a missing input.
- Memory learns from the outcome through MB034's existing subscriptions,
  not through a second path.

Everything is the shipped `RuntimeEngine`, the shipped Dispatcher, the
shipped gateway contract and the shipped `TextVerifier`.
"""
from __future__ import annotations

from typing import Any

from master_agent.mission_control.events import EventType
from master_agent.mission_control.tasks import TaskState
from master_agent.missions.history import COMPLETED, FAILED
from master_agent.runtime.config import RuntimeConfig
from master_agent.runtime.engine import RuntimeEngine
from master_agent.runtime.gateway import GatewayResult
from tests.missions_test_support import pipeline, plan_text, step
from tests.planner_test_support import CREATE, WRITE, success

TWO_STEPS = plan_text(
    step("make_folder", CREATE.name, {"name": "demo"},
         success_doc=success("the folder is created", must_contain=["created"])),
    step("write_readme", WRITE.name, {"path": "demo/README.md"},
         depends_on=["make_folder"],
         success_doc=success("the file is written", must_contain=["written"])),
)


class RecordingGateway:
    """An Executive gateway that returns scripted text and verifies it with
    MB035's real `TextVerifier`.

    This is what a real Executive gateway does -- `PluginGateway` invokes
    the plugin and asks its Verifier -- with the plugin replaced by a
    script. The verification path is not simulated.
    """

    def __init__(self, results: dict[str, str] | None = None) -> None:
        self.results = results or {}
        self.invoked: list[tuple[str, dict]] = []
        self.verified: list[str] = []

    def capabilities(self) -> list[str]:
        return ["create_folder", "write_file"]

    def invoke(self, capability: str, payload: dict) -> GatewayResult:
        self.invoked.append((capability, dict(payload)))
        return GatewayResult(success=True, output=self.results.get(capability, "created"))

    def verify(self, capability: str, payload: dict, expected: Any) -> Any:
        from master_agent.ai_infrastructure.text_verifier import verify_text

        self.verified.append(capability)
        return verify_text(self.results.get(capability, "created"), expected)


class AlwaysApprove:
    """MB028.0's `ApprovalGate`: `check()` returns None to authorise.

    Wired so these tests exercise the plan path rather than the approval
    path -- MB028.1 already proves the boundary, and a step blocked on a
    founder decision would prove nothing about dependency ordering.
    """

    def check(self, _request: Any) -> None:
        return None


def wired(tmp_path, results=None, plan=TWO_STEPS):
    system = pipeline(plan, tmp_path=tmp_path)
    gateway = RecordingGateway(results)
    runtime = RuntimeEngine(
        mission_control=system.mission_control,
        config=RuntimeConfig(max_cycles=12),
        approval_gate=AlwaysApprove(),
    )
    runtime.register_gateway("filesystem", gateway)
    return system, gateway, runtime


GOOD = {"create_folder": "created demo", "write_file": "written"}
BAD = {"create_folder": "nothing happened"}


# =========================================================================
# Verification gates completion
# =========================================================================


def test_a_step_is_verified_before_it_is_marked_complete(tmp_path):
    """"Never unlock a dependent step before verification." The Runtime
    calls `verify()` and only then `task_completed()`, so the ordering is
    a property of the shipped engine rather than of this brief."""
    system, gateway, runtime = wired(tmp_path, GOOD)
    system.start()

    seen: list[str] = []
    for event_type in (EventType.VERIFICATION_COMPLETED, EventType.TASK_COMPLETED):
        system.mission_control.bus.subscribe(
            lambda e: seen.append(e.event_type.value), event_type
        )

    runtime.run_once()

    assert seen[:2] == ["verification_completed", "task_completed"]
    assert gateway.verified == ["create_folder"]


def test_the_whole_plan_runs_in_dependency_order(tmp_path):
    system, gateway, runtime = wired(tmp_path, GOOD)
    outcome = system.start()

    for _ in range(4):
        runtime.run_once()

    assert [name for name, _ in gateway.invoked] == ["create_folder", "write_file"]
    assert system.objective(outcome.objective_id).is_complete


def test_every_step_of_a_completed_mission_carries_a_matched_verdict(tmp_path):
    system, _gateway, runtime = wired(tmp_path, GOOD)
    outcome = system.start()

    for _ in range(4):
        runtime.run_once()

    record = system.record(outcome.objective_id)
    assert record.state == COMPLETED
    assert [s.verdict for s in record.steps] == ["matched", "matched"]
    assert record.unverified == []
    assert record.progress == 1.0


def test_a_step_whose_answer_does_not_match_fails_rather_than_completing(tmp_path):
    """The expectation said the result must mention "created". It does
    not. MB035's verdict decides, and the Runtime fails the task."""
    system, _gateway, runtime = wired(tmp_path, BAD)
    outcome = system.start()

    runtime.run_once()

    task = system.objective(outcome.objective_id).task("make_folder")
    assert task.state is TaskState.FAILED
    assert any("verification" in error for error in task.errors)


def test_a_failed_verification_never_unlocks_the_dependent_step(tmp_path):
    """The property the whole brief turns on."""
    system, gateway, runtime = wired(tmp_path, BAD)
    outcome = system.start()

    for _ in range(4):
        runtime.run_once()

    assert [name for name, _ in gateway.invoked] == ["create_folder"]
    # BLOCKED, not CREATED: Mission Control does not merely fail to
    # schedule it, it records *why* it will never run. That is the
    # stronger form of the guarantee.
    dependent = system.objective(outcome.objective_id).task("write_readme")
    assert dependent.state is TaskState.BLOCKED
    assert "write_file" not in [name for name, _ in gateway.invoked]


def test_a_failed_verification_is_recorded_with_its_evidence(tmp_path):
    system, _gateway, runtime = wired(tmp_path, BAD)
    outcome = system.start()

    runtime.run_once()

    written = system.record(outcome.objective_id).step("make_folder")
    assert written.state == FAILED
    # `partially_matched`: "nothing happened" is not blank, so the weakest
    # check passed. MB035's `passed()` requires MATCHED and the Runtime
    # requires the same -- half a match is not a step that worked.
    assert written.verdict == "partially_matched"
    assert not written.verified
    assert written.evidence_id


def test_nothing_repairs_a_failed_step(tmp_path):
    """Deliverable 9: no automatic repair. The Planner is not asked again,
    the payload is not adjusted, and the expectation is not relaxed."""
    system, gateway, runtime = wired(tmp_path, BAD)
    system.start()
    planning_calls = len(system.runner.calls)

    for _ in range(6):
        runtime.run_once()

    assert len(system.runner.calls) == planning_calls, "the Planner was asked to re-plan"
    payloads = [payload for name, payload in gateway.invoked if name == "create_folder"]
    assert all(payload == {"name": "demo"} for payload in payloads), "a payload was adjusted"


def test_the_runtime_passes_the_planners_inputs_through_untouched(tmp_path):
    """Deliverable 5: execution never infers missing information."""
    system, gateway, runtime = wired(
        tmp_path,
        {"create_folder": "created demo"},
        plan_text(step("one", CREATE.name, {"name": "demo", "location": "desktop"})),
    )
    system.start()

    runtime.run_once()

    assert gateway.invoked == [("create_folder", {"name": "demo", "location": "desktop"})]


def test_a_step_with_no_inputs_reaches_the_executive_with_no_inputs(tmp_path):
    """Nothing fills an empty payload in on the way."""
    system, gateway, runtime = wired(
        tmp_path, {"create_folder": "created"}, plan_text(step("one", CREATE.name, {}))
    )
    system.start()

    runtime.run_once()

    assert gateway.invoked == [("create_folder", {})]


# =========================================================================
# Memory learns from the outcome, through the path that already existed
# =========================================================================


def test_a_completed_mission_is_remembered_by_the_founders_own_words(tmp_path):
    system, _gateway, runtime = wired(tmp_path, GOOD)
    system.start("Set up a demo project")

    for _ in range(4):
        runtime.run_once()

    titles = [record.title for record in system.memory.all()]
    assert "Mission completed: Set up a demo project" in titles


def test_a_failed_mission_lands_in_the_failure_library(tmp_path):
    system, _gateway, runtime = wired(tmp_path, BAD)
    system.start("Set up a demo project")

    for _ in range(6):
        runtime.run_once()

    failures = [r for r in system.memory.all() if r.category == "Failure Library"]
    assert any("Set up a demo project" in r.title for r in failures)


def test_the_verdict_itself_reaches_memory(tmp_path):
    """MB034 already subscribed to `VERIFICATION_COMPLETED`. MB037 adds no
    second path -- it just gives that subscription something to hear."""
    system, _gateway, runtime = wired(tmp_path, GOOD)
    system.start("Set up a demo project")
    before = system.memory.summary().total

    for _ in range(4):
        runtime.run_once()

    assert system.memory.summary().total > before


def test_memory_is_written_once_per_outcome_not_once_per_subscriber(tmp_path):
    """Two subscribers now watch the same events -- MB034's memory and
    MB037's history. The history must not cause a second memory write."""
    system, _gateway, runtime = wired(tmp_path, GOOD)
    system.start("Set up a demo project")

    for _ in range(4):
        runtime.run_once()

    completions = [
        r for r in system.memory.all() if r.title == "Mission completed: Set up a demo project"
    ]
    assert len(completions) == 1
