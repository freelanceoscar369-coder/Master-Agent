"""Task 2.5 — browser visibility, real execution state, timing telemetry,
and the founder-completion boundary.

Three independent claims, each proven against the real shipped classes
(no second classifier/router/orchestrator/approval system anywhere here):

1. `headless` reaches the Planner's actual prompt vocabulary, through the
   existing MB039 extraction -> index -> catalogue pipeline, unmodified in
   shape.
2. `ExecutionStatus` reports only what real `Event`s said — no fabricated
   states, no timers of its own.
3. A verified objective does not become founder-facing COMPLETED without
   an explicit `confirm_completion()` call, proven through the real
   `MissionControl`/`RuntimeEngine`, not a mock of either.
"""
from __future__ import annotations

from datetime import UTC, datetime

from master_agent.capabilities.extraction import contract_from_action
from master_agent.capabilities.index import build_index, entry_for
from master_agent.executor.actions.browser.open_session import OpenBrowserSessionAction
from master_agent.mission_control.events import Event, EventType
from master_agent.missions.execution_status import (
    AWAITING_APPROVAL,
    AWAITING_FOUNDER_COMPLETION,
    COMPLETED,
    EXECUTING,
    OBSERVING,
    PLANNING,
    RECOVERING,
    UNDERSTANDING,
    ExecutionStatus,
)
from master_agent.planner.catalogue import catalogue_from_index, render
from master_agent.runtime.config import RuntimeConfig
from master_agent.runtime.engine import RuntimeEngine
from tests.test_missions_execution import GOOD, TWO_STEPS, AlwaysApprove, RecordingGateway, wired


def test_status_serializes_and_resets_brain_decisions():
    status = ExecutionStatus()
    status.deliberation = {"state": "decided"}
    status.recovery = {"should_replan": False}
    assert status.as_dict()["deliberation"] == {"state": "decided"}
    assert status.as_dict()["recovery"] == {"should_replan": False}

    status.begin("another objective")
    assert status.deliberation is None
    assert status.recovery is None

# ---- 1. headless reaches the Planner's actual prompt -----------------------


def test_headless_is_an_optional_parameter_on_the_action():
    action = OpenBrowserSessionAction(sessions=None)
    optional = action.optional_parameters()
    assert optional is not None
    by_name = {item["name"]: item for item in optional}
    # `headless` is the parameter Task 2.5 published; `channel` joined it
    # for the visible-Chrome golden path (see
    # `test_golden_path_visible_chrome.py`). Asserted by containment so a
    # future published parameter does not break this claim.
    assert "headless" in by_name
    assert by_name["headless"]["type"] == "boolean"
    assert by_name["headless"]["default"] is True


def test_the_extracted_contract_publishes_headless_and_claims_closed():
    action = OpenBrowserSessionAction(sessions=None)
    contract = contract_from_action(action, "Browser.OpenBrowserSession", "browser")
    assert contract.inputs.known is True
    assert contract.inputs.closed is True
    field = contract.inputs.field("headless")
    assert field is not None
    assert field.required is False
    assert field.type == "boolean"
    assert field.default is True
    # required_parameters() is unaffected — session_id still required.
    assert contract.inputs.required_names == ("session_id",)


def test_an_action_that_never_declared_optional_args_stays_open():
    """The honesty floor this whole mechanism depends on: an Action that
    has not opted in must not suddenly claim completeness merely because
    a sibling Action now does."""

    class _NoOptIn:
        def required_parameters(self):
            return ["name"]

        def optional_parameters(self):
            return None

        risk_tier = None
        permission_category = None
        description = ""
        expected_result = ""
        name = "create_folder"

    contract = contract_from_action(_NoOptIn(), "Filesystem.CreateFolder", "filesystem")
    assert contract.inputs.closed is False


def test_headless_reaches_the_index_entry_and_the_catalogue_option():
    action = OpenBrowserSessionAction(sessions=None)
    contract = contract_from_action(action, "Browser.OpenBrowserSession", "browser")
    entry = entry_for(contract)
    assert "headless" in entry.optional_args

    index = build_index([contract])
    options = catalogue_from_index(index)
    assert len(options) == 1
    assert "headless" in options[0].optional_args


def test_headless_appears_in_the_rendered_prompt_text():
    """The line Gemini actually reads. Without this, `headless` could be
    fully known to the Schema/Contract layer and still never reach the
    model — exactly the gap Task 2's live run demonstrated."""
    action = OpenBrowserSessionAction(sessions=None)
    contract = contract_from_action(action, "Browser.OpenBrowserSession", "browser")
    index = build_index([contract])
    options = catalogue_from_index(index)
    text = render(options)
    assert "optional: headless" in text
    assert "session_id" in text


# ---- 2. ExecutionStatus reports only real events ---------------------------


def _event(event_type, **kwargs):
    return Event(event_type=event_type, source="test", **kwargs)


def test_begin_resets_and_stamps_a_real_start_time():
    status = ExecutionStatus()
    status.begin("open chrome", timeout_seconds=45.0)
    assert status.objective == "open chrome"
    assert status.timeout_ms == 45000
    assert status.started_at is not None
    assert status.elapsed_ms is not None
    assert status.elapsed_ms >= 0


def test_understanding_then_planning_are_reported_before_any_task_exists():
    status = ExecutionStatus()
    status.begin("open chrome")
    status.record(_event(EventType.MISSION_UNDERSTANDING_STARTED, task_id="plan-1"))
    assert status.status == UNDERSTANDING
    status.record(_event(EventType.MISSION_PLANNING_STARTED, task_id="plan-1"))
    assert status.status == PLANNING


def test_total_steps_counts_real_task_created_events():
    status = ExecutionStatus()
    status.begin("open chrome")
    for task_id in ("step_1", "step_2", "step_3"):
        status.record(_event(EventType.TASK_CREATED, task_id=task_id, objective_id="obj-1"))
    assert status.total_steps == 3
    assert status.current_step == 0  # nothing has started yet


def test_task_started_advances_current_step_and_distinguishes_observe():
    status = ExecutionStatus()
    status.begin("open chrome")
    status.record(
        _event(EventType.TASK_STARTED, task_id="step_1", capability="Browser.OpenBrowserSession")
    )
    assert status.status == EXECUTING
    assert status.current_step == 1
    assert status.current_capability == "Browser.OpenBrowserSession"

    status.record(
        _event(EventType.TASK_STARTED, task_id="step_2", capability="Browser.ObserveBrowser")
    )
    assert status.status == OBSERVING
    assert status.current_step == 2


def test_retry_reports_the_real_attempt_and_max_attempts():
    status = ExecutionStatus()
    status.begin("open chrome")
    status.record(_event(EventType.RUNTIME_STARTED, payload={"max_attempts": 3}))
    assert status.max_attempts == 3
    status.record(
        _event(
            EventType.TASK_RETRY_SCHEDULED,
            task_id="step_2",
            payload={"attempt": 1, "of": 3},
            error="navigate timed out",
        )
    )
    assert status.status == RECOVERING
    assert status.attempt == 1
    assert status.max_attempts == 3


def test_approval_required_is_reported_honestly():
    status = ExecutionStatus()
    status.begin("delete something")
    status.record(_event(EventType.APPROVAL_REQUIRED, task_id="step_1"))
    assert status.status == AWAITING_APPROVAL


def test_no_state_is_fabricated_before_any_event_arrives():
    status = ExecutionStatus()
    status.begin("open chrome")
    assert status.status is None  # honest absence, not a guessed "idle"


# ---- 3. verified is not founder-completed without confirmation -------------


def test_objective_completed_opens_a_founder_completion_question(tmp_path):
    system, gateway, runtime = wired(tmp_path, GOOD, TWO_STEPS)
    outcome = system.start()
    assert outcome.accepted
    objective_id = outcome.objective_id

    for _ in range(12):
        runtime.run_once()
        if system.mission_control.dispatcher.objective(objective_id).is_complete:
            break

    objective = system.mission_control.dispatcher.objective(objective_id)
    assert objective.is_complete

    state = system.mission_control.founder_state(objective_id)
    assert state.requires_founder_completion is True
    assert state.completion_id is not None

    # The internal OBJECTIVE_COMPLETED bookkeeping (Memory/History) is
    # untouched — only the founder-facing gate is new.
    open_completions = system.mission_control.completions.open()
    assert len(open_completions) == 1
    assert open_completions[0].objective_id == objective_id


def test_confirming_completion_clears_the_gate_and_is_the_only_way_to():
    from master_agent.mission_control.mission_control import MissionControl

    mc = MissionControl()
    mc.bus.publish(
        Event(
            event_type=EventType.OBJECTIVE_COMPLETED,
            source="test",
            objective_id="obj-1",
            payload={"task_count": 1},
        )
    )
    # No real Objective was submitted, so the completion question carries
    # an honestly-empty description rather than crashing.
    pending = mc.completions.find_open("obj-1")
    assert pending is not None

    confirmed = mc.confirm_completion(pending.completion_id, founder="Onkar")
    assert confirmed.confirmed_by == "Onkar"
    assert mc.completions.find_open("obj-1") is None


def test_execution_status_reaches_awaiting_completion_then_completed_only_after_confirm(
    tmp_path,
):
    system, gateway, runtime = wired(tmp_path, GOOD, TWO_STEPS)
    status = ExecutionStatus()
    system.mission_control.bus.subscribe(status.record, event_type=None)

    status.begin("Set up a demo project")
    outcome = system.start()
    objective_id = outcome.objective_id

    for _ in range(12):
        runtime.run_once()
        if system.mission_control.dispatcher.objective(objective_id).is_complete:
            break

    assert status.status == AWAITING_FOUNDER_COMPLETION
    assert status.requires_founder_completion is True
    assert status.terminal_state is False  # not done yet — a founder must still say so

    system.mission_control.confirm_completion(status.completion_id, founder="Onkar")

    assert status.status == COMPLETED
    assert status.requires_founder_completion is False
    assert status.terminal_state is True
