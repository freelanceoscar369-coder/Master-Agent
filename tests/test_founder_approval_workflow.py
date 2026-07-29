"""Mission Brief 028.1 — the Founder Approval Workflow.

MB028.0 made the system safe. This suite asks whether it is *usable*:
can a founder see what is being asked, decide, and have the system act on
the decision — without flags, harnesses, or internal commands.
"""
from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from master_agent.dashboard.app import TECHNICAL_PAGE, build_dashboard
from master_agent.executor.executor import LocalExecutor
from master_agent.launcher.console import FounderConsole, NullKeyReader
from master_agent.mission_control.adapters import discover_executives
from master_agent.mission_control.approvals import (
    ApprovalAlreadyDecided,
    ApprovalQueue,
    ApprovalState,
    PendingApproval,
)
from master_agent.mission_control.events import EventType
from master_agent.mission_control.mission_control import MissionControl
from master_agent.mission_control.tasks import Objective, Task, TaskState
from master_agent.permissions.permission_system import GrantScope, PermissionSystem
from master_agent.persistence.service import PersistenceService
from master_agent.persistence.store import JsonFileStateStore
from master_agent.plugins.filesystem_plugin import FilesystemPlugin
from master_agent.plugins.registry import PluginRegistry
from master_agent.runtime.approval import FounderApprovalGate, PermissionSystemGate
from master_agent.runtime.config import RuntimeConfig
from master_agent.runtime.engine import RuntimeEngine
from master_agent.runtime.gateway import PluginGateway


class World:
    """A real system wired exactly as `kalpavriksha` wires one."""

    def __init__(self, work: Path, timeout: float | None = None, clock=None):
        self.permissions = PermissionSystem()
        self.executor = LocalExecutor(self.permissions)
        self.plugin = FilesystemPlugin(self.executor, locations={"desktop": work})
        self.registry = PluginRegistry()
        self.registry.register(self.plugin)
        self.mission_control = MissionControl()
        if clock is not None:
            self.mission_control.approvals._clock = clock
        discover_executives(self.mission_control, self.registry)

        inner = PermissionSystemGate(self.permissions, self.registry).report_to(
            self.mission_control.bus
        )
        self.gate = FounderApprovalGate(
            inner=inner,
            mission_control=self.mission_control,
            grant_on_approval=lambda r: self.permissions.grant(
                r.executive_id, r.local_capability, GrantScope.ONCE
            ),
            timeout_seconds=timeout,
            describe_impact=lambda r: f"acts on {r.payload.get('path') or r.payload.get('name')}",
        )
        self.engine = RuntimeEngine(
            self.mission_control,
            RuntimeConfig(poll_interval_seconds=0, max_cycles=3),
            sleep=lambda _s: None,
            approval_gate=self.gate,
        )
        self.engine.register_gateway("filesystem", PluginGateway(self.plugin))

    def submit(self, capability: str, payload: dict, task_id: str = "t1") -> Objective:
        return self.mission_control.submit_objective(
            Objective(
                description="founder workflow test",
                tasks=[Task(capability=capability, payload=payload, task_id=task_id)],
            )
        )

    def run(self) -> None:
        self.engine._cycles_this_process = 0
        self.engine._state = self.engine._state.__class__.INITIALIZING
        self.engine._stop_requested.clear()
        self.engine.run_forever()

    def task(self, index: int = 0, task_id: str = "t1") -> Task:
        return self.mission_control.dispatcher.objectives()[index].task(task_id)


@pytest.fixture
def work(tmp_path):
    d = tmp_path / "work"
    d.mkdir()
    return d


# ---- the request appears -------------------------------------------------


def test_an_unapproved_task_waits_instead_of_failing(work):
    """The MB028.0 -> MB028.1 change in one test: unapproved work used to
    fail. Now it waits, because a founder who has not answered yet is not
    a founder who said no."""
    (work / "Precious").mkdir()
    world = World(work)
    world.submit("Filesystem.DeleteFolder", {"path": "Precious"})

    world.run()

    assert world.task().state is not TaskState.FAILED
    assert (work / "Precious").exists()
    assert len(world.mission_control.approvals.open()) == 1


def test_the_request_carries_everything_deliverable_1_names(work):
    (work / "Precious").mkdir()
    world = World(work)
    world.submit("Filesystem.DeleteFolder", {"path": "Precious"})
    world.run()

    approval = world.mission_control.approvals.open()[0]

    assert approval.approval_id
    assert approval.objective == "founder workflow test"
    assert approval.objective_id
    assert approval.task_id == "t1"
    assert approval.executive_id == "filesystem"
    assert approval.capability == "Filesystem.DeleteFolder"
    assert approval.risk_tier == "irreversible"
    assert approval.reason == "Delete Folder"
    assert "Precious" in approval.impact
    assert approval.requested_at is not None
    assert approval.requested_by == "runtime"


def test_the_founder_is_asked_once_however_many_cycles_pass(work):
    """The Runtime re-checks the boundary every cycle while a task waits.
    Without idempotency that is one queue entry and one event per cycle."""
    (work / "Precious").mkdir()
    world = World(work)
    world.submit("Filesystem.DeleteFolder", {"path": "Precious"})

    world.run()
    world.run()
    world.run()

    assert len(world.mission_control.approvals.all()) == 1
    requested = world.mission_control.audit.of_type(EventType.APPROVAL_REQUESTED)
    assert len(requested) == 1


def test_the_approval_appears_in_the_dashboard(work):
    (work / "Precious").mkdir()
    world = World(work)
    world.submit("Filesystem.DeleteFolder", {"path": "Precious"})
    world.run()

    dashboard = build_dashboard(
        mission_control=world.mission_control, writer=lambda _t: None
    )

    # The founder page (MB029 default) leads with the decision.
    founder = dashboard.render()
    assert "FOUNDER DECISIONS (1)" in founder
    assert "Delete Folder" in founder
    assert "IRREVERSIBLE" in founder

    # The technical page still carries MB028.1's panel, unchanged.
    dashboard.show(TECHNICAL_PAGE)
    technical = dashboard.render()
    assert "PENDING APPROVALS (1)" in technical
    assert "Filesystem.DeleteFolder" in technical
    assert "[A]pprove" in technical


# ---- approve / reject / defer --------------------------------------------


def test_approving_lets_the_task_run(work):
    doomed = work / "Precious"
    doomed.mkdir()
    world = World(work)
    world.submit("Filesystem.DeleteFolder", {"path": "Precious"})
    world.run()

    approval = world.mission_control.approvals.open()[0]
    world.mission_control.approve(approval.approval_id, "onkar")
    world.run()

    assert world.task().state is TaskState.COMPLETED
    assert not doomed.exists()


def test_rejecting_fails_the_task_gracefully_and_audibly(work):
    """Deliverable 6: fail gracefully, notify Mission Control, update
    Founder State, publish an audit event. No retry, no disappearance."""
    doomed = work / "Precious"
    doomed.mkdir()
    world = World(work)
    world.submit("Filesystem.DeleteFolder", {"path": "Precious"})
    world.run()

    approval = world.mission_control.approvals.open()[0]
    world.mission_control.reject(approval.approval_id, "onkar", "not that folder")
    world.run()

    assert world.task().state is TaskState.FAILED
    assert doomed.exists(), "a rejected delete must not delete"
    assert world.mission_control.audit.of_type(EventType.APPROVAL_DENIED)
    assert world.mission_control.approvals.open() == []
    assert not world.mission_control.audit.of_type(EventType.TASK_RETRY_SCHEDULED)


def test_a_rejected_request_is_never_re_asked(work):
    (work / "Precious").mkdir()
    world = World(work)
    world.submit("Filesystem.DeleteFolder", {"path": "Precious"})
    world.run()
    world.mission_control.reject(
        world.mission_control.approvals.open()[0].approval_id, "onkar"
    )

    world.run()

    assert world.mission_control.approvals.open() == []
    assert len(world.mission_control.approvals.all()) == 1


def test_deferring_keeps_the_request_open_and_the_task_waiting(work):
    doomed = work / "Precious"
    doomed.mkdir()
    world = World(work)
    world.submit("Filesystem.DeleteFolder", {"path": "Precious"})
    world.run()

    approval = world.mission_control.approvals.open()[0]
    world.mission_control.defer(approval.approval_id, "onkar", "decide tomorrow")
    world.run()

    assert approval.state is ApprovalState.DEFERRED
    assert world.mission_control.approvals.open() == [approval]
    assert world.task().state is not TaskState.FAILED
    assert doomed.exists()


def test_a_deferred_request_can_still_be_approved(work):
    doomed = work / "Precious"
    doomed.mkdir()
    world = World(work)
    world.submit("Filesystem.DeleteFolder", {"path": "Precious"})
    world.run()
    approval = world.mission_control.approvals.open()[0]
    world.mission_control.defer(approval.approval_id, "onkar")

    world.mission_control.approve(approval.approval_id, "onkar")
    world.run()

    assert world.task().state is TaskState.COMPLETED
    assert not doomed.exists()


# ---- timeout -------------------------------------------------------------


def test_an_unanswered_request_expires_after_the_timeout(work):
    now = datetime(2026, 7, 29, 22, 13, tzinfo=UTC)
    doomed = work / "Precious"
    doomed.mkdir()
    world = World(work, timeout=60.0, clock=lambda: now)
    world.submit("Filesystem.DeleteFolder", {"path": "Precious"})
    world.run()
    assert len(world.mission_control.approvals.open()) == 1

    world.mission_control.approvals._clock = lambda: now + timedelta(seconds=61)
    world.run()

    approval = world.mission_control.approvals.all()[0]
    assert approval.state is ApprovalState.EXPIRED
    assert world.task().state is TaskState.FAILED
    assert doomed.exists(), "an expired request must never execute"
    assert world.mission_control.audit.of_type(EventType.APPROVAL_EXPIRED)


def test_no_timeout_means_it_waits_forever(work):
    """The safe default. A request that vanishes overnight is worse than
    one still on the screen in the morning."""
    (work / "Precious").mkdir()
    world = World(work, timeout=None)
    world.submit("Filesystem.DeleteFolder", {"path": "Precious"})
    world.run()
    world.run()

    assert len(world.mission_control.approvals.open()) == 1


# ---- the ledger ----------------------------------------------------------


def test_every_decision_writes_immutable_evidence(work):
    queue = ApprovalQueue()
    approval, _ = queue.request(
        PendingApproval(
            capability="Filesystem.DeleteFolder",
            local_capability="delete_folder",
            executive_id="filesystem",
            risk_tier="irreversible",
            reason="Delete Folder",
            task_id="t1",
            objective_id="obj-1",
        )
    )
    queue.approve(approval.approval_id, "onkar", "checked it")

    ledger = queue.ledger()
    assert len(ledger) == 1
    record = ledger[0]
    assert record.decided_by == "onkar"
    assert record.decision == "approved"
    assert record.capability == "Filesystem.DeleteFolder"
    assert record.task_id == "t1"
    assert record.objective_id == "obj-1"
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.decision = "rejected"


def test_the_ledger_cannot_be_edited_through_the_accessor(work):
    queue = ApprovalQueue()
    approval, _ = queue.request(
        PendingApproval(
            capability="X.Y",
            local_capability="y",
            executive_id="x",
            risk_tier="irreversible",
            reason="Y",
            task_id="t1",
        )
    )
    queue.approve(approval.approval_id, "onkar")

    queue.ledger().clear()

    assert len(queue.ledger()) == 1


def test_a_decided_approval_can_never_be_re_decided(work):
    queue = ApprovalQueue()
    approval, _ = queue.request(
        PendingApproval(
            capability="X.Y",
            local_capability="y",
            executive_id="x",
            risk_tier="irreversible",
            reason="Y",
            task_id="t1",
        )
    )
    queue.reject(approval.approval_id, "onkar")

    with pytest.raises(ApprovalAlreadyDecided):
        queue.approve(approval.approval_id, "onkar")


# ---- multiple pending (Deliverable 8) ------------------------------------


def test_five_pending_approvals_are_supported_and_ordered(work):
    queue = ApprovalQueue()
    for index in range(5):
        queue.request(
            PendingApproval(
                capability=f"Filesystem.Cap{index}",
                local_capability=f"cap{index}",
                executive_id="filesystem",
                risk_tier="irreversible",
                reason=f"Cap {index}",
                task_id=f"t{index}",
            )
        )

    assert len(queue.open()) == 5
    assert [a.capability for a in queue.open()] == [
        f"Filesystem.Cap{i}" for i in range(5)
    ]


def test_the_founder_may_decide_in_any_order(work):
    queue = ApprovalQueue()
    for index in range(5):
        queue.request(
            PendingApproval(
                capability=f"Filesystem.Cap{index}",
                local_capability=f"cap{index}",
                executive_id="filesystem",
                risk_tier="irreversible",
                reason=f"Cap {index}",
                task_id=f"t{index}",
            )
        )

    queue.approve(queue.by_index(4).approval_id, "onkar")
    queue.reject(queue.by_index(1).approval_id, "onkar")

    # index 4 was Cap3 and index 1 was Cap0, resolved against the queue
    # as it stood when each command was typed -- which is exactly how a
    # founder reads the panel.
    remaining = [a.capability for a in queue.open()]
    assert remaining == ["Filesystem.Cap1", "Filesystem.Cap2", "Filesystem.Cap4"]


def test_deferred_requests_sort_below_pending_ones(work):
    queue = ApprovalQueue()
    for index in range(3):
        queue.request(
            PendingApproval(
                capability=f"C{index}",
                local_capability=f"c{index}",
                executive_id="x",
                risk_tier="irreversible",
                reason="r",
                task_id=f"t{index}",
            )
        )
    queue.defer(queue.by_index(1).approval_id, "onkar")

    assert [a.capability for a in queue.open()] == ["C1", "C2", "C0"]


# ---- restart (Deliverable 5) ---------------------------------------------


def test_deferred_approvals_survive_a_restart(tmp_path, work):
    state = tmp_path / "state"
    store = JsonFileStateStore(state)

    world = World(work)
    service = PersistenceService(store, world.mission_control)
    service.start_recording()
    (work / "Precious").mkdir()
    world.submit("Filesystem.DeleteFolder", {"path": "Precious"})
    world.run()
    approval = world.mission_control.approvals.open()[0]
    world.mission_control.defer(approval.approval_id, "onkar", "tomorrow")
    service.save(world.mission_control)

    restored = MissionControl()
    PersistenceService(store, restored).restore_into(restored)

    assert len(restored.approvals.open()) == 1
    back = restored.approvals.open()[0]
    assert back.approval_id == approval.approval_id
    assert back.state is ApprovalState.DEFERRED
    assert back.capability == "Filesystem.DeleteFolder"
    assert back.impact == approval.impact
    assert back.note == "tomorrow"


def test_restart_restores_evidence_but_not_authority(tmp_path, work):
    """ADR-0019's rule, now with a queue in the picture: a restored
    APPROVED entry is a record that the founder said yes. It must not let
    the same work run again."""
    state = tmp_path / "state"
    store = JsonFileStateStore(state)
    doomed = work / "Precious"
    doomed.mkdir()

    world = World(work)
    service = PersistenceService(store, world.mission_control)
    service.start_recording()
    world.submit("Filesystem.DeleteFolder", {"path": "Precious"})
    world.run()
    world.mission_control.approve(
        world.mission_control.approvals.open()[0].approval_id, "onkar"
    )
    world.run()
    assert not doomed.exists()
    service.save(world.mission_control)

    # Restart: evidence comes back...
    restored = MissionControl()
    PersistenceService(store, restored).restore_into(restored)
    ledger = restored.approvals.ledger()
    assert len(ledger) == 1
    assert ledger[0].decided_by == "onkar"
    assert ledger[0].decision == "approved"

    # ...authority does not. A fresh world over the same work asks again.
    doomed.mkdir()
    second = World(work)
    second.submit("Filesystem.DeleteFolder", {"path": "Precious"})
    second.run()

    assert doomed.exists(), "a restored approval re-armed authority"
    assert len(second.mission_control.approvals.open()) == 1


# ---- the console (Deliverable 3) -----------------------------------------


def console_for(mission_control):
    dashboard = build_dashboard(
        mission_control=mission_control, writer=lambda _t: None
    )
    return FounderConsole(
        dashboard,
        mission_control,
        founder="onkar",
        reader=NullKeyReader(),
        writer=lambda _t: None,
        sleep=lambda _s: None,
    )


def seed(mission_control, count: int = 3):
    for index in range(count):
        mission_control.request_approval(
            PendingApproval(
                capability=f"Filesystem.Cap{index}",
                local_capability=f"cap{index}",
                executive_id="filesystem",
                risk_tier="irreversible",
                reason=f"Cap {index}",
                task_id=f"t{index}",
            )
        )


def test_approve_by_number():
    mc = MissionControl()
    seed(mc)
    console = console_for(mc)

    message = console.execute("approve 2")

    assert "Filesystem.Cap1" in message
    assert len(mc.approvals.open()) == 2
    assert mc.approvals.ledger()[0].decided_by == "onkar"


def test_reject_and_defer_by_number():
    mc = MissionControl()
    seed(mc)
    console = console_for(mc)

    console.execute("reject 1")
    console.execute("defer 1")

    states = {a.capability: a.state for a in mc.approvals.all()}
    assert states["Filesystem.Cap0"] is ApprovalState.REJECTED
    assert states["Filesystem.Cap1"] is ApprovalState.DEFERRED


def test_approve_all():
    mc = MissionControl()
    seed(mc, 5)
    console = console_for(mc)

    message = console.execute("approve all")

    assert "5 approval(s)" in message
    assert mc.approvals.open() == []
    assert len(mc.approvals.ledger()) == 5


def test_single_letter_shortcuts_match_the_panel_hints():
    mc = MissionControl()
    seed(mc)
    console = console_for(mc)

    console.execute("a 1")

    assert len(mc.approvals.open()) == 2


def test_a_bad_command_is_a_message_not_a_crash():
    mc = MissionControl()
    seed(mc)
    console = console_for(mc)

    assert "unknown command" in console.execute("aprove 1")
    assert "not an approval number" in console.execute("approve two")
    assert "no pending approval numbered 9" in console.execute("approve 9")
    assert "which?" in console.execute("approve")
    assert len(mc.approvals.open()) == 3, "no typo may decide anything"


def test_typing_builds_a_command_and_enter_runs_it():
    mc = MissionControl()
    seed(mc)
    console = console_for(mc)

    for char in "approve 1":
        console.feed(char)
    console.feed("\r")

    assert len(mc.approvals.open()) == 2


def test_backspace_edits_the_command_line():
    mc = MissionControl()
    seed(mc)
    console = console_for(mc)

    for char in "approve 12":
        console.feed(char)
    console.feed("\x7f")
    console.feed("\r")

    assert len(mc.approvals.open()) == 2


def test_quit_stops_the_console():
    mc = MissionControl()
    console = console_for(mc)

    console.execute("quit")

    assert console.stopped is True


def test_the_console_renders_the_queue_and_the_prompt():
    mc = MissionControl()
    seed(mc, 2)
    console = console_for(mc)

    frame = console.render_once()

    assert "FOUNDER DECISIONS (2)" in frame
    assert "approve N" in frame
    assert frame.rstrip().endswith(">")


def test_a_non_interactive_console_renders_without_blocking():
    """`kalpavriksha | tee log.txt` must not hang waiting for a keypress
    that can never arrive."""
    mc = MissionControl()
    seed(mc)
    console = console_for(mc)

    console.run(max_frames=2)

    assert console.stopped is False


# ---- live updates (Deliverable 9) ----------------------------------------


def test_the_panel_reflects_a_decision_with_no_restart(work):
    (work / "Precious").mkdir()
    world = World(work)
    world.submit("Filesystem.DeleteFolder", {"path": "Precious"})
    world.run()
    dashboard = build_dashboard(
        mission_control=world.mission_control, writer=lambda _t: None
    )

    assert "FOUNDER DECISIONS (1)" in dashboard.render()

    world.mission_control.approve(
        world.mission_control.approvals.open()[0].approval_id, "onkar"
    )

    assert "none pending" in dashboard.render()


def test_a_new_approval_marks_the_dashboard_dirty(work):
    """The Dashboard refreshes on events. A new question must be one."""
    world = World(work)
    dashboard = build_dashboard(
        mission_control=world.mission_control, writer=lambda _t: None
    )
    dashboard.render_once(clear=False)
    assert dashboard._dirty is False

    seed(world.mission_control, 1)

    assert dashboard._dirty is True


# ---- the boundary stays singular (Architecture Rules) --------------------


def test_no_executive_receives_approval_directly(work):
    """The gate still decides; the Executive is still told nothing. A
    gateway invoked outside the Runtime has no approval opinion at all,
    which is why the boundary had to live in the Runtime (ADR-0019)."""
    world = World(work)
    gateway = PluginGateway(world.plugin)

    assert not hasattr(gateway, "check")
    assert not hasattr(world.plugin, "approve")


def test_the_founder_gate_delegates_rather_than_replacing_the_permission_check(work):
    """ADR-0019 unweakened: the Permission System is still the only thing
    that says whether authority exists."""
    world = World(work)

    assert isinstance(world.gate._inner, PermissionSystemGate)
    assert world.gate._inner._permissions is world.permissions
