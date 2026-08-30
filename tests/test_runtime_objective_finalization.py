"""Mission-scoped environment resources are released at terminal state."""
from __future__ import annotations

from types import SimpleNamespace

from master_agent.mission_control.capabilities import CapabilityDescriptor, qualified_name
from master_agent.mission_control.executives import ExecutiveHealth
from master_agent.mission_control.mission_control import MissionControl
from master_agent.mission_control.tasks import Objective, Task
from master_agent.permissions.permission_system import PermissionSystem
from master_agent.plugins.browser_gateway import BrowserGateway
from master_agent.runtime.config import RuntimeConfig
from master_agent.runtime.engine import RuntimeEngine
from master_agent.runtime.gateway import GatewayResult
from tests.approval_test_support import ApprovingGate
from tests.runtime_test_support import RecordingGateway


class FinalizingGateway(RecordingGateway):
    def __init__(self, results=None):
        super().__init__(results=results)
        self.finalized: list[list[str]] = []

    def finalize_objective(self, tasks):
        self.finalized.append([task.task_id for task in tasks])
        return []


def system(gateway):
    control = MissionControl()
    control.register_executive(
        executive_id="demo",
        version="1",
        capabilities=[
            CapabilityDescriptor(
                qualified_name=qualified_name("demo", name),
                executive_id="demo",
                capability=name,
            )
            for name in ("open", "use")
        ],
        health=ExecutiveHealth.HEALTHY,
    )
    control.mark_executive_ready("demo")
    runtime = RuntimeEngine(
        control,
        RuntimeConfig(poll_interval_seconds=0, max_attempts=1),
        sleep=lambda _seconds: None,
        approval_gate=ApprovingGate(),
    )
    runtime.register_gateway("demo", gateway)
    return control, runtime


def objective():
    return Objective(
        description="open then use",
        tasks=[
            Task(task_id="open", capability="Demo.Open"),
            Task(task_id="use", capability="Demo.Use", depends_on=["open"]),
        ],
    )


def test_runtime_finalizes_once_after_a_terminal_failure():
    gateway = FinalizingGateway(results=[
        GatewayResult(success=True, output={"session_id": "owned"}),
        GatewayResult(success=False, errors=["deterministic failure"]),
    ])
    control, runtime = system(gateway)
    control.submit_objective(objective())

    runtime.run_once()
    assert gateway.finalized == []
    runtime.run_once()

    assert gateway.finalized == [["open", "use"]]


def test_runtime_finalizes_once_after_success():
    gateway = FinalizingGateway()
    control, runtime = system(gateway)
    control.submit_objective(objective())

    runtime.run_once()
    runtime.run_once()

    assert gateway.finalized == [["open", "use"]]


class FakeSessions:
    def __init__(self):
        self.live = {"owned", "also-owned", "unrelated"}
        self.closed: list[str] = []

    def list_sessions(self):
        return [SimpleNamespace(session_id=value) for value in sorted(self.live)]

    def close_session(self, session_id):
        self.live.remove(session_id)
        self.closed.append(session_id)
        return []


def test_browser_gateway_releases_only_sessions_owned_by_these_tasks():
    sessions = FakeSessions()
    worker = SimpleNamespace(_sessions=sessions)
    gateway = BrowserGateway(worker, PermissionSystem(), "local")
    tasks = [
        SimpleNamespace(
            payload={"session_id": "owned"},
            result={"session_id": "also-owned"},
        ),
        SimpleNamespace(payload={"session_id": "owned"}, result=None),
    ]

    warnings = gateway.finalize_objective(tasks)

    assert warnings == []
    assert sessions.closed == ["also-owned", "owned"]
    assert sessions.live == {"unrelated"}
