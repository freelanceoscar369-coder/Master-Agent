"""Fire-and-Forget — characterization + acceptance contract (read-only
review, no production changes).

These tests define the target behavior traced in
`docs/audits/FIRE_AND_FORGET_DESIGN.md`. Several are written to FAIL
against today's synchronous `kalpavriksha_desktop._submit_objective()` on
purpose — that failure *is* the characterization. They should turn green
once (and only once) the smallest correct implementation described in
that document lands.

Nothing here is a mock of `MissionControl`, `RuntimeEngine`, or
`MissionService` — where a test needs their real semantics (Founder
completion boundary, verification-before-completion, event ordering) it
uses the same real-pipeline-over-a-stubbed-provider harness
`test_missions_execution.py` already built (`wired()`/`pipeline()`/
`StubRunner`). Where a test only needs `kalpavriksha_desktop._submit_objective()`'s
own control flow, it reuses the exact fakes already written for it in
`test_kalpavriksha_desktop_mission_bridge.py`, rather than inventing new
ones.

No real Gemini call, no real browser, no installed application.
"""
from __future__ import annotations

import os
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kalpavriksha_desktop as kd  # noqa: E402

from master_agent.missions.execution_status import (  # noqa: E402
    AWAITING_FOUNDER_COMPLETION,
    COMPLETED,
    ExecutionStatus,
)
from master_agent.mission_control.events import EventType  # noqa: E402
from master_agent.runtime.approval import ApprovalDenied  # noqa: E402
from master_agent.runtime.config import RuntimeConfig  # noqa: E402
from master_agent.runtime.engine import RuntimeEngine  # noqa: E402
from tests.missions_test_support import pipeline  # noqa: E402
from tests.planner_test_support import plan_text, refused, step  # noqa: E402
from tests.test_kalpavriksha_desktop_mission_bridge import (  # noqa: E402
    _FakeDispatcher,
    _FakeFounderState,
    _FakeMissionControl,
    _FakeMissionService,
    _FakeObjective,
    _FakeOutcome,
    _FakeRuntime,
)
from tests.test_missions_execution import GOOD, BAD, TWO_STEPS, AlwaysApprove, RecordingGateway


# =========================================================================
# Shared helpers
# =========================================================================


class DenyingGate:
    """The opposite of `AlwaysApprove` — for the permission-block
    characterization (§8). Real `ApprovalDenied`, the same exception
    `PermissionSystemGate` raises; nothing invented."""

    def check(self, request):
        raise ApprovalDenied(request, "founder approval required")


def wired_with_gate(tmp_path, gate, results=None, plan=TWO_STEPS):
    """`test_missions_execution.wired()`'s own body, with the approval
    gate as a parameter instead of hardcoded `AlwaysApprove()` — that
    function is intentionally not modified; this is a local variant."""
    system = pipeline(plan, tmp_path=tmp_path)
    gateway = RecordingGateway(results)
    runtime = RuntimeEngine(
        mission_control=system.mission_control,
        config=RuntimeConfig(max_cycles=12),
        approval_gate=gate,
    )
    runtime.register_gateway("filesystem", gateway)
    return system, gateway, runtime


# =========================================================================
# 1. Immediate acknowledgement
# =========================================================================


def test_acknowledgement_returns_promptly_without_waiting_for_terminal_state():
    """CHARACTERIZATION — expected to FAIL today.

    A `_FakeRuntime` whose objective never reaches a terminal state (it
    stays `complete=False` forever) forces today's bounded while-loop to
    run out its full `timeout_seconds` before returning. Under
    fire-and-forget, acceptance alone should return in a small fraction of
    that budget.
    """
    mission_service = _FakeMissionService(_FakeOutcome(accepted=True, objective_id="obj-ff-1"))
    runtime = _FakeRuntime()
    mission_control = _FakeMissionControl([_FakeObjective(complete=False)], _FakeFounderState())
    status = ExecutionStatus()

    t0 = time.monotonic()
    result = kd._submit_objective(
        mission_service, runtime, mission_control, status, "open chrome",
        timeout_seconds=2.0,
    )
    elapsed = time.monotonic() - t0

    assert elapsed < 0.5, (
        f"took {elapsed:.2f}s against a 2.0s budget — the bridge call waited "
        "for terminal state instead of returning on acceptance"
    )
    assert "reply" in result


def test_acknowledgement_carries_the_objective_id():
    """CHARACTERIZATION — expected to FAIL today.

    `_submit_objective()`'s return dict never carries `objective_id` in
    any branch today; the acknowledgement contract (§8 of the design doc)
    requires it so the Founder Surface can later poll status/confirm
    completion for the right mission.
    """
    mission_service = _FakeMissionService(_FakeOutcome(accepted=True, objective_id="obj-ff-2"))
    runtime = _FakeRuntime()
    mission_control = _FakeMissionControl([_FakeObjective(complete=True)], _FakeFounderState())
    status = ExecutionStatus()

    result = kd._submit_objective(
        mission_service, runtime, mission_control, status, "open chrome"
    )

    assert result.get("objective_id") == "obj-ff-2"


def test_acknowledgement_does_not_claim_success_verification_or_completion():
    """CHARACTERIZATION — expected to FAIL today.

    Today's synchronous call runs to completion and returns the finished
    result sentence ("Done — ..."); an acknowledgement returned on
    acceptance must not contain that sentence, and must not report a
    completed/terminal status.
    """
    mission_service = _FakeMissionService(_FakeOutcome(accepted=True, objective_id="obj-ff-3"))
    runtime = _FakeRuntime()
    mission_control = _FakeMissionControl(
        [_FakeObjective(complete=False)], _FakeFounderState(progress=0.0, result=None)
    )
    status = ExecutionStatus()

    result = kd._submit_objective(
        mission_service, runtime, mission_control, status, "open chrome",
        timeout_seconds=2.0,
    )

    reply = result.get("reply", "")
    assert "Done" not in reply
    assert "loaded with title" not in reply
    assert status.status != COMPLETED
    assert status.terminal_state is False


# =========================================================================
# 2. Runtime continues independently of the original bridge call
# =========================================================================


def test_the_objective_can_reach_completion_through_further_run_once_calls_alone(tmp_path):
    """Not a mock of Runtime/MissionControl — the real pipeline. Calls
    `mission_service.start()` directly (not through `_submit_objective()`,
    which today would drive the loop itself) and then drives completion
    purely through repeated `runtime.run_once()` calls, exactly what a
    background thread started once at boot (`RuntimeEngine.start_background()`,
    already shipped) would do on its own. No new scheduler, no new loop —
    this is `run_once()` called from ordinary test code."""
    system, gateway, runtime = wired_with_gate(tmp_path, AlwaysApprove(), GOOD)
    outcome = system.start()
    assert outcome.accepted

    for _ in range(12):
        if system.objective(outcome.objective_id).is_complete:
            break
        runtime.run_once()

    assert system.objective(outcome.objective_id).is_complete
    assert [name for name, _ in gateway.invoked] == ["create_folder", "write_file"]


# =========================================================================
# 3. ExecutionStatus remains observable after acknowledgement
# =========================================================================


def test_execution_status_is_observable_through_the_existing_mechanism_alone(tmp_path):
    """Imports the real backend status definition (`ExecutionStatus`) —
    no invented vocabulary. Subscribes it to the real bus the same way
    `kalpavriksha_desktop._build_mission_pipeline()` already does, then
    proves the same objective stays observable purely by reading
    `status.as_dict()`, without any further call to the function that
    submitted it."""
    system, gateway, runtime = wired_with_gate(tmp_path, AlwaysApprove(), GOOD)
    status = ExecutionStatus()
    system.mission_control.bus.subscribe(status.record, event_type=None)

    status.begin("Set up a demo project")
    outcome = system.start()
    assert status.objective_id == outcome.objective_id

    runtime.run_once()
    assert status.status is not None
    assert status.current_step >= 1


# =========================================================================
# 4. Final result reachable without the original call remaining alive
# =========================================================================


def test_the_underlying_result_is_available_through_founder_state_after_late_completion(
    tmp_path,
):
    """`_submit_objective()` called with a timeout too short to reach
    terminal state (so it returns early — the fire-and-forget shape),
    then the mission is driven to completion by further `run_once()`
    calls the way a background thread would. The result must still be
    obtainable through Mission Control's own existing read path
    (`founder_state()`), which does not depend on `_submit_objective()`
    ever being reentered."""
    system, gateway, runtime = wired_with_gate(tmp_path, AlwaysApprove(), GOOD)
    status = ExecutionStatus()
    system.mission_control.bus.subscribe(status.record, event_type=None)

    kd._submit_objective(
        system.missions, runtime, system.mission_control, status,
        "Set up a demo project", timeout_seconds=0.01,
    )
    objective_id = status.objective_id
    assert objective_id is not None

    for _ in range(12):
        if system.objective(objective_id).is_complete:
            break
        runtime.run_once()

    state = system.mission_control.founder_state(objective_id)
    assert state.result is not None


def test_execution_status_result_gap_after_late_completion(tmp_path):
    """CHARACTERIZATION — expected to FAIL today.

    The companion to the test above: `ExecutionStatus.record()` never
    populates `result`/`message` from an `Event` (see the design doc's
    "ExecutionStatus relationship" section) — only `_submit_objective()`'s
    own post-loop code does, and that code is never reached when the call
    returns early. This is the one gap the design doc names as needing a
    small, explicit fix before Hyper Agent can show a real result under
    fire-and-forget.
    """
    system, gateway, runtime = wired_with_gate(tmp_path, AlwaysApprove(), GOOD)
    status = ExecutionStatus()
    system.mission_control.bus.subscribe(status.record, event_type=None)

    kd._submit_objective(
        system.missions, runtime, system.mission_control, status,
        "Set up a demo project", timeout_seconds=0.01,
    )
    objective_id = status.objective_id

    for _ in range(12):
        if system.objective(objective_id).is_complete:
            break
        runtime.run_once()

    assert status.result is not None, (
        "ExecutionStatus.result was never populated by the late completion — "
        "the gap docs/audits/FIRE_AND_FORGET_DESIGN.md names explicitly"
    )


# =========================================================================
# 5. Founder completion boundary
# =========================================================================


def test_acknowledgement_is_never_mistaken_for_completion(tmp_path):
    system, gateway, runtime = wired_with_gate(tmp_path, AlwaysApprove(), GOOD)
    status = ExecutionStatus()
    system.mission_control.bus.subscribe(status.record, event_type=None)

    kd._submit_objective(
        system.missions, runtime, system.mission_control, status,
        "Set up a demo project", timeout_seconds=0.01,
    )

    assert status.terminal_state is False
    assert status.status != COMPLETED


def test_execution_success_is_not_final_completion_without_founder_confirmation(tmp_path):
    """Already true today (Task 2.5) — kept here as an acceptance test for
    the fire-and-forget contract specifically, since a background-thread
    implementation must not accidentally shortcut this boundary."""
    system, gateway, runtime = wired_with_gate(tmp_path, AlwaysApprove(), GOOD)
    status = ExecutionStatus()
    system.mission_control.bus.subscribe(status.record, event_type=None)

    status.begin("Set up a demo project")
    outcome = system.start()
    for _ in range(12):
        runtime.run_once()
        if system.objective(outcome.objective_id).is_complete:
            break

    assert system.objective(outcome.objective_id).is_complete
    assert status.status == AWAITING_FOUNDER_COMPLETION
    assert status.requires_founder_completion is True
    assert status.terminal_state is False

    system.mission_control.confirm_completion(status.completion_id, founder="Onkar")

    assert status.status == COMPLETED
    assert status.terminal_state is True


# =========================================================================
# 6. Conversation responsiveness while Mission A runs
# =========================================================================


class _SlowFakeRuntime:
    """A `run_once()` that takes real wall-clock time per cycle and needs
    several cycles before the objective completes — long enough that, if
    something serialized around it, a concurrent read would visibly wait
    too."""

    def __init__(self, cycles_to_complete: int, per_cycle_seconds: float = 0.2) -> None:
        self._remaining = cycles_to_complete
        self._per_cycle = per_cycle_seconds
        self.run_once_calls = 0

    def run_once(self):
        time.sleep(self._per_cycle)
        self._remaining -= 1
        self.run_once_calls += 1


def test_a_second_independent_read_is_not_blocked_by_an_in_flight_mission():
    """Proves the load-bearing primitive conversation-responsiveness
    depends on: nothing in `_submit_objective()`'s own path holds a lock
    that a separate, independent call would also need. This models the
    same per-request-thread shape pywebview's `ThreadingMixIn` already
    gives every real bridge call (see the design doc's Threading Model
    section) — it does not add any concurrency primitive to production
    code, only to this test.

    What this test cannot exercise: the real `DesktopShellApi.send_message()`
    conversation path itself, because collecting `test_desktop_shell.py`
    currently fails on a pre-existing, unrelated circular import in
    `founder_edition/boot.py` (confirmed earlier this engagement, out of
    scope here). This is the closest live proof available without that
    import chain.
    """
    mission_service = _FakeMissionService(_FakeOutcome(accepted=True, objective_id="obj-ff-6"))
    slow_runtime = _SlowFakeRuntime(cycles_to_complete=10, per_cycle_seconds=0.3)
    mission_control = _FakeMissionControl(
        [_FakeObjective(complete=False)], _FakeFounderState()
    )
    status = ExecutionStatus()

    mission_a_done = threading.Event()

    def run_mission_a():
        kd._submit_objective(
            mission_service, slow_runtime, mission_control, status, "open chrome",
            timeout_seconds=5.0,
        )
        mission_a_done.set()

    thread = threading.Thread(target=run_mission_a, daemon=True)
    t0 = time.monotonic()
    thread.start()
    time.sleep(0.1)  # let Mission A genuinely start before the "conversation" read

    # The independent operation a founder's own conversational turn would
    # make: a plain, read-only status check — nothing mission-execution
    # related, nothing that should ever need to wait on Mission A.
    read_start = time.monotonic()
    _ = status.as_dict()
    read_elapsed = time.monotonic() - read_start

    assert read_elapsed < 0.1, (
        f"an independent read took {read_elapsed:.2f}s while Mission A was "
        "in flight — something is serializing them"
    )
    assert not mission_a_done.is_set(), "test setup issue: Mission A finished too fast to prove anything"

    thread.join(timeout=5.0)


# =========================================================================
# 7. One-current-mission rule — PENDING EVIDENCE
# =========================================================================


def test_one_current_mission_enforcement_is_currently_absent():
    """PENDING EVIDENCE — this does not assert a policy, because reading
    `kalpavriksha_desktop._submit_objective()` end to end shows no check
    for "is a mission already active" anywhere in it: it unconditionally
    calls `mission_service.start(text)` every time it is invoked. The
    design doc's "one-current-mission constraint" section proposes this be
    enforced as a founder-surface policy gate — but that gate does not
    exist yet. This test documents *today's actual (unguarded) behavior*
    so it cannot be mistaken for a validated rule: a second call is
    accepted exactly like the first, with no rejection of any kind.

    If/when Hermes's investigation or the implementation adds an explicit
    gate, this test should be replaced with one that asserts the gate's
    real behavior — not amended to keep passing.
    """
    mission_service = _FakeMissionService(_FakeOutcome(accepted=True, objective_id="obj-A"))
    runtime = _FakeRuntime()
    mission_control = _FakeMissionControl([_FakeObjective(complete=True)], _FakeFounderState())
    status = ExecutionStatus()

    first = kd._submit_objective(mission_service, runtime, mission_control, status, "mission A")

    mission_service._outcome = _FakeOutcome(accepted=True, objective_id="obj-B")
    second = kd._submit_objective(mission_service, runtime, mission_control, status, "mission B")

    # Current behavior: both are accepted unconditionally. Not asserted as
    # correct — only as what happens today, pending Hermes's own finding.
    assert "reply" in first
    assert "reply" in second


# =========================================================================
# 8. Failure / blocked mission characterization
# =========================================================================


def test_planning_refusal_does_not_report_success():
    system = pipeline(refused("no eligible provider"))
    runtime = _FakeRuntime()
    status = ExecutionStatus()

    result = kd._submit_objective(
        system.missions, runtime, system.mission_control, status, "do something impossible"
    )

    # Founder-facing hygiene (tonight's launch rescue): the refusal must
    # not claim success, and must not leak the provider's own text either.
    # The developer diagnostic remains on `status.errors`.
    assert "Done" not in result["reply"]
    assert "no eligible provider" not in result["reply"]
    assert any("no eligible provider" in err for err in status.errors)
    assert runtime.run_once_calls == 0


def test_permission_block_does_not_report_success(tmp_path):
    system, gateway, runtime = wired_with_gate(tmp_path, DenyingGate(), GOOD)
    status = ExecutionStatus()

    result = kd._submit_objective(
        system.missions, runtime, system.mission_control, status,
        "Set up a demo project", timeout_seconds=1.0,
    )

    assert "Done" not in result["reply"]
    assert gateway.invoked == []  # denied before the gateway was ever reached


def test_execution_failure_does_not_report_success(tmp_path):
    system, gateway, runtime = wired_with_gate(tmp_path, AlwaysApprove(), BAD)
    status = ExecutionStatus()

    result = kd._submit_objective(
        system.missions, runtime, system.mission_control, status,
        "Set up a demo project", timeout_seconds=1.0,
    )

    assert "Done" not in result["reply"]
    assert "didn't complete" in result["reply"] or "taking longer" in result["reply"]


def test_verification_failure_does_not_report_success(tmp_path):
    """`BAD`'s reply for `create_folder` ("nothing happened") fails MB035's
    real verifier against the plan's own stated success criteria
    ("created") — the same real verification path
    `test_a_step_is_verified_before_it_is_marked_complete` exercises, not
    a shortcut."""
    system, gateway, runtime = wired_with_gate(tmp_path, AlwaysApprove(), BAD)
    status = ExecutionStatus()

    result = kd._submit_objective(
        system.missions, runtime, system.mission_control, status,
        "Set up a demo project", timeout_seconds=1.0,
    )

    assert "Done" not in result["reply"]
    assert gateway.verified  # verification was actually attempted, and failed
