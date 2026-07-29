"""Mission Brief 024's Definition of Done, as a test.

    A founder can launch Kalpavriksha and observe:
      Start Runtime -> Runtime Running -> Mission Control Dispatching ->
      Browser Executive Working -> Verification -> Audit Updated ->
      Waiting For Next Task
    without manually triggering each execution cycle.

The founder here does exactly three things: wire the system, submit an
objective, and start the Runtime. Nothing after that calls
`dispatch_ready()`, `task_started()`, or `task_completed()`.

## A real constraint these tests surfaced

Playwright's sync API is **thread-affine**: a browser session must be used
from the thread that created it. The autonomous Runtime drives work from
its own thread, so a test cannot open a session on the main thread and
then let the Runtime act on it -- that raises "Sync API inside the asyncio
loop". Single-threaded MIT-001 never hit this; the heartbeat found it
immediately.

So every browser interaction below happens *inside a task*, on whichever
thread the Runtime is using -- page content arrives via a `data:` URL
navigation rather than a main-thread `set_content()`. That is also how a
real objective would be written, which is a good sign rather than a
workaround. See RUNTIME_ENGINE_ARCHITECTURE.md §5.
"""
from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from master_agent.environment.browser_session import BrowserSessionManager
from master_agent.executor.executor import LocalExecutor
from master_agent.mission_control.adapters import discover_executives
from master_agent.mission_control.events import EventType
from master_agent.mission_control.mission_control import MissionControl
from master_agent.mission_control.tasks import Objective, Task, TaskState
from master_agent.permissions.permission_system import PermissionSystem
from master_agent.plugins.browser_plugin import BrowserPlugin
from master_agent.plugins.browser_worker import BrowserWorker
from master_agent.plugins.registry import PluginRegistry
from master_agent.runtime.config import RuntimeConfig
from master_agent.runtime.engine import RuntimeEngine
from master_agent.runtime.states import RuntimeState
from master_agent.verification.evidence import ExpectedOutcome, ObservationCheck
from tests.runtime_test_support import BrowserGateway

DEMO_HTML = (
    "<html><head><title>Heartbeat Demo</title></head>"
    "<body><h1 id='heading'>It beats</h1></body></html>"
)
DEMO_URL = "data:text/html," + quote(DEMO_HTML)


def build_system(**config_kwargs):
    """Founder-side wiring -- the only place a specific Executive is
    named. The Runtime is constructed knowing none of it; it receives a
    gateway keyed by an Executive ID."""
    config_kwargs.setdefault("poll_interval_seconds", 0.01)
    config_kwargs.setdefault("max_attempts", 2)
    config_kwargs.setdefault("retry_delay_seconds", 0)

    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    sessions = BrowserSessionManager()

    registry = PluginRegistry()
    registry.register(BrowserPlugin(executor, sessions))

    mission_control = MissionControl()
    discover_executives(mission_control, registry)

    worker = BrowserWorker(executor, sessions)
    engine = RuntimeEngine(mission_control, RuntimeConfig(**config_kwargs))
    engine.register_gateway("browser", BrowserGateway(worker, permissions, executor.name))
    return mission_control, engine, sessions


def browsing_objective(description: str, session_id: str, observe_task: Task) -> Objective:
    """Open a session, load a deterministic local page, then whatever the
    caller wants observed -- and always close the session, so teardown
    happens on the Runtime's own thread."""
    return Objective(
        description=description,
        tasks=[
            Task(
                capability="Browser.OpenBrowserSession",
                payload={"session_id": session_id},
                task_id="open",
            ),
            Task(
                capability="Browser.Navigate",
                payload={"session_id": session_id, "url": DEMO_URL},
                task_id="load",
                depends_on=["open"],
            ),
            observe_task,
        ],
    )


def wait_until(predicate, timeout_seconds: float = 60.0) -> bool:
    deadline = datetime.now(UTC) + timedelta(seconds=timeout_seconds)
    while datetime.now(UTC) < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def run_until_settled(engine: RuntimeEngine, objective: Objective, cycles: int = 12) -> None:
    """Drive the loop on the *calling* thread until nothing is left to do.

    Still fully autonomous -- the Runtime decides what to dispatch, runs
    it, verifies it, and reports it. The test only says "keep beating",
    never "run this task now". Used where a background thread would put
    Playwright on two threads (see module docstring).
    """
    for _ in range(cycles):
        engine.run_once()
        if objective.is_complete or objective.has_failure:
            return


def test_definition_of_done_a_founder_starts_the_runtime_and_walks_away():
    """The headline claim, on a real background thread: the founder
    submits work, starts the Runtime, and touches nothing else."""
    mission_control, engine, sessions = build_system()
    objective = browsing_objective(
        "Open a browser, load a page, and read its heading",
        "heartbeat",
        Task(
            capability="Browser.ObserveBrowser",
            payload={"session_id": "heartbeat", "selectors": ["#heading"]},
            task_id="observe",
            depends_on=["load"],
        ),
    )
    objective.tasks.append(
        Task(
            capability="Browser.CloseBrowserSession",
            payload={"session_id": "heartbeat"},
            task_id="close",
            depends_on=["observe"],
        )
    )

    mission_control.submit_objective(objective)
    engine.start_background()  # <-- the last founder action
    completed = wait_until(lambda: objective.is_complete or objective.has_failure)
    engine.stop()

    assert completed, f"did not settle: {[(t.task_id, t.state.value) for t in objective.tasks]}"
    assert objective.is_complete, (
        f"objective did not complete autonomously: "
        f"{[(t.task_id, t.state.value, t.errors) for t in objective.tasks]}"
    )
    assert mission_control.founder_state().progress == 1.0
    assert engine.state is RuntimeState.STOPPED
    assert sessions.list_sessions() == [], "the Runtime should have closed its own session"


def test_the_autonomous_run_produces_the_full_observable_trail():
    mission_control, engine, sessions = build_system()
    objective = browsing_objective(
        "autonomous trail",
        "trail",
        Task(
            capability="Browser.CloseBrowserSession",
            payload={"session_id": "trail"},
            task_id="observe",
            depends_on=["load"],
        ),
    )
    mission_control.submit_objective(objective)
    try:
        run_until_settled(engine, objective)
        engine.stop()
    finally:
        sessions.close_all()

    assert objective.is_complete
    emitted = {entry.event_type for entry in mission_control.audit.entries}
    for expected in (
        EventType.RUNTIME_STARTED,   # Start Runtime
        EventType.DISPATCH_STARTED,  # Mission Control Dispatching
        EventType.TASK_ASSIGNED,     # Browser Executive assigned
        EventType.TASK_STARTED,      # Browser Executive Working
        EventType.TASK_COMPLETED,    # Audit Updated
        EventType.RUNTIME_IDLE,      # Waiting For Next Task
        EventType.RUNTIME_STOPPED,   # graceful shutdown
    ):
        assert expected in emitted, f"missing from the trail: {expected}"


def test_verification_runs_automatically_inside_the_autonomous_loop():
    """Deliverable #4: the Runtime invokes the Verification subsystem
    after execution, with no founder involvement."""
    mission_control, engine, sessions = build_system()
    objective = browsing_objective(
        "observe and verify",
        "verify",
        Task(
            capability="Browser.ObserveBrowser",
            payload={"session_id": "verify", "selectors": ["#heading"]},
            task_id="observe",
            depends_on=["load"],
            expected_outcome=ExpectedOutcome(
                description="the heading reads 'It beats'",
                checks=[
                    ObservationCheck(
                        field="elements.0.text", operator="equals", value="It beats"
                    )
                ],
            ),
        ),
    )
    mission_control.submit_objective(objective)
    try:
        run_until_settled(engine, objective)
        engine.stop()
    finally:
        sessions.close_all()

    assert objective.is_complete, (
        f"{[(t.task_id, t.state.value, t.errors) for t in objective.tasks]}"
    )
    verifications = mission_control.audit.of_type(EventType.VERIFICATION_COMPLETED)
    assert verifications, "verification never ran"
    assert verifications[-1].payload["verdict"] == "matched"

    task = objective.task("observe")
    assert task.evidence_id is not None
    assert task.evidence_id in mission_control.founder_state().evidence


def test_a_failing_verification_stops_the_task_autonomously():
    """The other half of ADR-0011: if reality does not match what was
    expected, the autonomous loop must not mark the task done."""
    mission_control, engine, sessions = build_system()
    objective = browsing_objective(
        "expect something untrue",
        "mismatch",
        Task(
            capability="Browser.ObserveBrowser",
            payload={"session_id": "mismatch", "selectors": ["#heading"]},
            task_id="observe",
            depends_on=["load"],
            expected_outcome=ExpectedOutcome(
                description="the heading says something it does not",
                checks=[
                    ObservationCheck(
                        field="elements.0.text",
                        operator="equals",
                        value="Never going to match",
                    )
                ],
            ),
        ),
    )
    mission_control.submit_objective(objective)
    try:
        run_until_settled(engine, objective)
        engine.stop()
    finally:
        sessions.close_all()

    task = objective.task("observe")
    assert task.state is TaskState.FAILED, (
        "a NOT_MATCHED verdict must never be reported as success"
    )
    assert "not_matched" in task.errors[0]
    assert mission_control.founder_state().errors


def test_runtime_health_reflects_a_real_autonomous_run():
    mission_control, engine, sessions = build_system()
    objective = browsing_objective(
        "health",
        "health",
        Task(
            capability="Browser.CloseBrowserSession",
            payload={"session_id": "health"},
            task_id="observe",
            depends_on=["load"],
        ),
    )
    mission_control.submit_objective(objective)
    try:
        run_until_settled(engine, objective)
        health = engine.health()
        engine.stop()
    finally:
        sessions.close_all()

    assert objective.is_complete
    assert health.executives_online == 1
    assert health.tasks_completed == 3
    assert health.last_dispatch_at is not None
    assert health.active_cycle >= 3
