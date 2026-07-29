"""Mission Brief 025's Definition of Done, as a test.

    A founder can:
      1. Start Kalpavriksha.  2. Submit work.  3. Kill the process.
      4. Restart Kalpavriksha.  5. Watch it resume exactly where it left off.

Each "process" below is a completely fresh object graph -- new
MissionControl, new RuntimeEngine, new store handle -- sharing only the
state directory on disk. Nothing is carried over in memory, which is what
makes this a genuine restart rather than a reset.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from master_agent.executor.executor import LocalExecutor
from master_agent.mission_control.adapters import discover_executives
from master_agent.mission_control.mission_control import MissionControl
from master_agent.mission_control.tasks import Objective, Task, TaskState
from master_agent.permissions.permission_system import GrantScope, PermissionSystem
from master_agent.persistence.recovery import recover
from master_agent.persistence.service import PersistenceService
from master_agent.persistence.store import JsonFileStateStore
from master_agent.plugins.filesystem_plugin import FilesystemPlugin
from master_agent.plugins.registry import PluginRegistry
from master_agent.runtime.config import RuntimeConfig
from master_agent.runtime.engine import RuntimeEngine
from master_agent.runtime.gateway import PluginGateway
from tests.approval_test_support import ApprovingGate


class Process:
    """One boot of Kalpavriksha, wired the way a launcher would: create,
    recover, discover, run."""

    def __init__(self, state_dir: Path, work_dir: Path, max_cycles: int = 4):
        self.permissions = PermissionSystem()
        self.executor = LocalExecutor(self.permissions)
        self.plugin = FilesystemPlugin(self.executor, locations={"desktop": work_dir})
        self.registry = PluginRegistry()
        self.registry.register(self.plugin)

        self.mission_control = MissionControl()
        self.service = PersistenceService(JsonFileStateStore(state_dir), self.mission_control)
        self.service.start_recording()

        self.engine = RuntimeEngine(
            self.mission_control,
            RuntimeConfig(poll_interval_seconds=0, max_cycles=max_cycles),
            sleep=lambda _s: None,
            checkpoint_sink=self.service,
            approval_gate=ApprovingGate(),
        )
        self.engine.register_gateway(
            "filesystem",
            PluginGateway(
                self.plugin,
                grant_permission=lambda c: self.permissions.grant(
                    self.executor.name, c, GrantScope.ONCE
                ),
            ),
        )

    def recover(self):
        report = recover(self.service, self.mission_control, self.engine)
        discover_executives(self.mission_control, self.registry)
        return report

    def discover(self):
        discover_executives(self.mission_control, self.registry)

    def run(self):
        self.engine.run_forever()

    def kill(self):
        """A clean kill: whatever is already checkpointed is what
        survives. No graceful hand-off beyond what the runtime already
        wrote at cycle end."""
        self.service.flush()


@pytest.fixture
def dirs(tmp_path):
    state = tmp_path / "state"
    work = tmp_path / "work"
    work.mkdir()
    return state, work


def three_step_objective() -> Objective:
    return Objective(
        description="build a folder and two files",
        tasks=[
            Task(capability="Filesystem.CreateFolder", payload={"name": "P"}, task_id="t1"),
            Task(
                capability="Filesystem.WriteFile",
                payload={"path": "P/a.txt", "content": "one"},
                task_id="t2",
                depends_on=["t1"],
            ),
            Task(
                capability="Filesystem.WriteFile",
                payload={"path": "P/b.txt", "content": "two"},
                task_id="t3",
                depends_on=["t2"],
            ),
        ],
    )


def test_definition_of_done_kill_restart_and_resume(dirs):
    state, work = dirs

    # --- Process 1: start, submit, run partway, die ---
    first = Process(state, work, max_cycles=2)
    first.discover()
    first.mission_control.submit_objective(three_step_objective())
    first.run()
    first.kill()

    partial = first.mission_control.founder_state().progress
    assert 0 < partial < 1, "the first process should finish some but not all of the work"

    # --- Process 2: a completely fresh boot over the same state ---
    second = Process(state, work, max_cycles=4)
    report = second.recover()

    assert report.recovered is True
    assert report.source == "snapshot"
    assert second.mission_control.founder_state().progress == partial, (
        "progress must come back exactly where it stopped, before running anything"
    )

    second.run()

    assert second.mission_control.founder_state().progress == 1.0
    assert (work / "P" / "a.txt").read_text() == "one"
    assert (work / "P" / "b.txt").read_text() == "two"


def test_no_work_is_repeated_across_the_restart(dirs):
    """Tasks the first process completed must not run again."""
    state, work = dirs

    first = Process(state, work, max_cycles=2)
    first.discover()
    first.mission_control.submit_objective(three_step_objective())
    first.run()
    completed_first = {
        task.task_id
        for task in first.mission_control.dispatcher.objectives()[0].tasks
        if task.state is TaskState.COMPLETED
    }
    first.kill()

    second = Process(state, work, max_cycles=4)
    second.recover()
    before = {
        task.task_id
        for task in second.mission_control.dispatcher.objectives()[0].tasks
        if task.state is TaskState.COMPLETED
    }
    assert before == completed_first

    second.run()

    # Every task ran exactly once across both processes: the audit for the
    # restored objective contains one TASK_COMPLETED per task.
    from master_agent.mission_control.events import EventType

    completions = [
        entry.task_id
        for entry in second.mission_control.audit.of_type(EventType.TASK_COMPLETED)
    ]
    assert sorted(completions) == ["t1", "t2", "t3"]
    assert len(completions) == len(set(completions)), "a task was executed twice"


def test_audit_history_from_the_first_process_survives(dirs):
    state, work = dirs

    first = Process(state, work, max_cycles=2)
    first.discover()
    first.mission_control.submit_objective(three_step_objective())
    first.run()
    first_events = len(first.service.store.read_events())
    first.kill()

    second = Process(state, work, max_cycles=1)
    report = second.recover()

    assert report.audit_entries == first_events
    assert len(second.mission_control.audit) >= first_events


def test_the_runtime_cycle_counter_resumes_rather_than_restarting_at_zero(dirs):
    state, work = dirs

    first = Process(state, work, max_cycles=3)
    first.discover()
    first.mission_control.submit_objective(three_step_objective())
    first.run()
    cycles = first.engine.health().active_cycle
    first.kill()

    second = Process(state, work, max_cycles=1)
    second.recover()

    assert second.engine.health().active_cycle == cycles


def test_registries_come_back_before_anything_is_rediscovered(dirs):
    """Recovery restores the Executive and its capabilities from state,
    not by re-running discovery -- discovery afterwards is idempotent."""
    state, work = dirs

    first = Process(state, work, max_cycles=1)
    first.discover()
    first.mission_control.submit_objective(three_step_objective())
    first.run()
    first.kill()

    second = Process(state, work, max_cycles=1)
    report = recover(second.service, second.mission_control, second.engine)

    assert report.executives == 1
    assert report.capabilities == 14
    assert second.mission_control.capabilities.has("Filesystem.CreateFolder")


def test_a_restart_with_nothing_persisted_starts_cleanly(dirs):
    """The first ever boot must not need special handling."""
    state, work = dirs
    process = Process(state, work, max_cycles=1)
    report = process.recover()

    assert report.recovered is False
    process.mission_control.submit_objective(three_step_objective())
    process.run()
    assert process.mission_control.founder_state().progress > 0


def test_three_consecutive_restarts_still_converge(dirs):
    """Persistence must be stable under repetition, not just once."""
    state, work = dirs

    first = Process(state, work, max_cycles=1)
    first.discover()
    first.mission_control.submit_objective(three_step_objective())
    first.run()
    first.kill()

    for _ in range(3):
        process = Process(state, work, max_cycles=1)
        process.recover()
        process.run()
        process.kill()

    final = Process(state, work, max_cycles=2)
    final.recover()
    final.run()

    assert final.mission_control.founder_state().progress == 1.0
    assert (work / "P" / "b.txt").exists()


def test_state_survives_being_read_by_a_completely_independent_service(dirs):
    """Nothing in the restored state depends on the object that wrote it."""
    state, work = dirs

    first = Process(state, work, max_cycles=2)
    first.discover()
    first.mission_control.submit_objective(three_step_objective())
    first.run()
    first.kill()

    lone_control = MissionControl()
    lone_service = PersistenceService(JsonFileStateStore(state), lone_control)
    counts = lone_service.restore_into(lone_control)

    assert counts["objectives"] == 1
    assert counts["executives"] == 1
    assert lone_control.founder_state().current_mission == "build a folder and two files"
