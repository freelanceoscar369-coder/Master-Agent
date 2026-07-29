"""Mission Brief 028.0 — the Runtime approval boundary (ADR-0019).

The claim under test is the Definition of Done:

    "Nothing irreversible can happen inside Kalpavriksha unless I
     explicitly approved it."

Enforced by architecture, so these tests attack the architecture: they try
to bypass the boundary, they construct a Runtime without one, and they
replay history to see whether authority comes back with it.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from master_agent.executor.executor import LocalExecutor
from master_agent.mission_control.adapters import discover_executives
from master_agent.mission_control.events import EventType
from master_agent.mission_control.mission_control import MissionControl
from master_agent.mission_control.tasks import Objective, Task, TaskState
from master_agent.permissions.permission_system import GrantScope, PermissionSystem
from master_agent.persistence.replay import replay_events_into
from master_agent.persistence.service import PersistenceService
from master_agent.persistence.store import JsonFileStateStore
from master_agent.plugins.base import RiskTier
from master_agent.plugins.filesystem_plugin import FilesystemPlugin
from master_agent.plugins.registry import PluginRegistry
from master_agent.runtime.approval import (
    ApprovalDenied,
    ApprovalRequest,
    PermissionSystemGate,
)
from master_agent.runtime.config import RuntimeConfig
from master_agent.runtime.engine import RuntimeEngine
from master_agent.runtime.gateway import PluginGateway

RUNTIME_DIR = Path(__file__).resolve().parents[1] / "src" / "master_agent" / "runtime"


class World:
    """A real system, wired exactly as the launcher wires one."""

    def __init__(self, work_dir: Path, gate=..., decisions: list | None = None):
        self.permissions = PermissionSystem()
        self.executor = LocalExecutor(self.permissions)
        self.plugin = FilesystemPlugin(self.executor, locations={"desktop": work_dir})
        self.registry = PluginRegistry()
        self.registry.register(self.plugin)
        self.mission_control = MissionControl()
        discover_executives(self.mission_control, self.registry)
        self.decisions = decisions if decisions is not None else []

        if gate is ...:
            # Exactly the launcher's wiring: the shipped publishing
            # reporter, plus a tap so tests can assert on decisions.
            gate = PermissionSystemGate(self.permissions, self.registry)
            publish = gate.publishing_reporter(self.mission_control.bus)

            def report(req, granted, reason):
                self.decisions.append((req.local_capability, granted, reason))
                publish(req, granted, reason)

            gate._on_decision = report
        self.engine = RuntimeEngine(
            self.mission_control,
            RuntimeConfig(poll_interval_seconds=0, max_cycles=6),
            sleep=lambda _s: None,
            approval_gate=gate,
        )
        self.engine.register_gateway("filesystem", PluginGateway(self.plugin))

    def approve(self, capability: str, scope: GrantScope = GrantScope.THIS_SESSION):
        self.permissions.grant("filesystem", capability, scope)

    def submit(self, capability: str, payload: dict) -> Objective:
        return self.mission_control.submit_objective(
            Objective(
                description="boundary test",
                tasks=[Task(capability=capability, payload=payload, task_id="t1")],
            )
        )

    def run(self) -> TaskState:
        self.engine.run_forever()
        return self.mission_control.dispatcher.objectives()[0].task("t1").state


# ---- missing gate blocks execution --------------------------------------


def test_a_runtime_with_no_gate_executes_nothing(tmp_path):
    """Fail closed. Forgetting to wire the boundary must yield a system
    that does nothing, never one that does everything."""
    world = World(tmp_path, gate=None)
    world.approve("create_folder")  # even WITH a grant, no gate means no run
    world.submit("Filesystem.CreateFolder", {"name": "NeverMade"})

    assert world.run() is TaskState.FAILED
    assert not (tmp_path / "NeverMade").exists()


def test_a_missing_gate_says_why(tmp_path):
    world = World(tmp_path, gate=None)
    world.submit("Filesystem.CreateFolder", {"name": "X"})
    world.run()

    required = world.mission_control.audit.of_type(EventType.APPROVAL_REQUIRED)
    assert required, "a refusal must be auditable"
    assert "no approval gate" in required[-1].error


# ---- missing approval blocks execution ----------------------------------


def test_an_unapproved_reversible_capability_is_refused(tmp_path):
    world = World(tmp_path)
    world.submit("Filesystem.CreateFolder", {"name": "Unapproved"})

    assert world.run() is TaskState.FAILED
    assert not (tmp_path / "Unapproved").exists()


def test_an_unapproved_irreversible_capability_is_refused(tmp_path):
    """The headline case. Before MB028.0 this deleted the folder."""
    doomed = tmp_path / "Doomed"
    doomed.mkdir()
    world = World(tmp_path)
    world.submit("Filesystem.DeleteFolder", {"path": "Doomed"})

    assert world.run() is TaskState.FAILED
    assert doomed.exists(), "an IRREVERSIBLE capability ran without approval"


def test_a_standing_grant_can_never_authorise_an_irreversible_capability(tmp_path):
    """ADR-0009, inherited rather than rebuilt: ALWAYS_FOR_CAPABILITY
    cannot satisfy an IRREVERSIBLE check, no matter how it was created."""
    doomed = tmp_path / "Doomed"
    doomed.mkdir()
    world = World(tmp_path)
    world.approve("delete_folder", GrantScope.ALWAYS_FOR_CAPABILITY)
    world.submit("Filesystem.DeleteFolder", {"path": "Doomed"})

    assert world.run() is TaskState.FAILED
    assert doomed.exists()


# ---- granted approval allows execution ----------------------------------


def test_an_approved_capability_executes(tmp_path):
    world = World(tmp_path)
    world.approve("create_folder")
    world.submit("Filesystem.CreateFolder", {"name": "Approved"})

    assert world.run() is TaskState.COMPLETED
    assert (tmp_path / "Approved").exists()


def test_an_approved_irreversible_capability_executes(tmp_path):
    """A fresh ONCE decision is what an irreversible capability requires,
    and it is enough."""
    doomed = tmp_path / "Doomed"
    doomed.mkdir()
    world = World(tmp_path)
    world.approve("delete_folder", GrantScope.ONCE)
    world.submit("Filesystem.DeleteFolder", {"path": "Doomed"})

    assert world.run() is TaskState.COMPLETED
    assert not doomed.exists()


def test_read_only_capabilities_need_no_approval(tmp_path):
    """Rule 5 gates what is *above* READ_ONLY. Requiring approval below it
    would be a stricter rule than the Constitution states, invented here."""
    (tmp_path / "Readable").mkdir()
    world = World(tmp_path)
    world.submit("Filesystem.DirectoryExists", {"path": "Readable"})

    assert world.run() is TaskState.COMPLETED
    assert world.decisions == [], "READ_ONLY must not be recorded as an approval"


# ---- the audit holds the evidence ---------------------------------------


def test_a_granted_decision_is_reported_with_its_reason(tmp_path):
    world = World(tmp_path)
    world.approve("create_folder")
    world.submit("Filesystem.CreateFolder", {"name": "Audited"})
    world.run()

    granted = [d for d in world.decisions if d[1]]
    assert granted, "a granted approval must be reported"
    assert granted[0][0] == "create_folder"


def test_a_refusal_is_reported_and_is_auditable(tmp_path):
    world = World(tmp_path)
    world.submit("Filesystem.CreateFolder", {"name": "Refused"})
    world.run()

    assert [d for d in world.decisions if not d[1]], "a refusal must be reported"
    assert world.mission_control.audit.of_type(EventType.APPROVAL_REQUIRED)


def test_a_refusal_is_never_retried(tmp_path):
    """Retrying a refusal is asking the same question repeatedly and
    hoping for a different answer."""
    world = World(tmp_path)
    world.submit("Filesystem.CreateFolder", {"name": "Refused"})
    world.run()

    refusals = [d for d in world.decisions if not d[1]]
    assert len(refusals) == 1, f"the boundary was consulted {len(refusals)} times"
    assert not world.mission_control.audit.of_type(EventType.TASK_RETRY_SCHEDULED)


# ---- evidence survives restart, authority does not ----------------------


def test_approval_evidence_survives_a_restart_but_authority_does_not(tmp_path):
    """Deliverables 8 and 9 together, which is the only way they make
    sense: the audit remembers you approved; the system still asks again."""
    state = tmp_path / "state"
    work = tmp_path / "work"
    work.mkdir()
    store = JsonFileStateStore(state)

    first = World(work)
    service = PersistenceService(store, first.mission_control)
    service.start_recording()
    first.approve("create_folder")
    first.submit("Filesystem.CreateFolder", {"name": "Durable"})
    assert first.run() is TaskState.COMPLETED
    service.flush()

    # --- restart: a brand new process-equivalent, replaying history ---
    second = MissionControl()
    replay_events_into(second, store.read_events())
    PersistenceService(store, second).restore_audit_into(second)

    approvals = second.audit.of_type(EventType.APPROVAL_GRANTED)
    assert approvals, "approval evidence did not survive the restart"
    evidence = approvals[-1].payload
    assert evidence["capability"] == "Filesystem.CreateFolder"  # which capability
    assert evidence["decided_by"] == "founder"  # who approved
    assert approvals[-1].occurred_at is not None  # when

    # ...and the authority is gone. A fresh world over the same history
    # starts with an empty ledger.
    third = World(work)
    third.submit("Filesystem.CreateFolder", {"name": "SecondTime"})
    assert third.run() is TaskState.FAILED, "replay re-armed an approval"
    assert not (work / "SecondTime").exists()


def test_replay_executes_nothing(tmp_path):
    """Replay reconstructs history. It must never perform work — least of
    all irreversible work it is reading a record of."""
    state = tmp_path / "state"
    work = tmp_path / "work"
    work.mkdir()
    (work / "Doomed").mkdir()
    store = JsonFileStateStore(state)

    world = World(work)
    service = PersistenceService(store, world.mission_control)
    service.start_recording()
    world.approve("delete_folder", GrantScope.ONCE)
    world.submit("Filesystem.DeleteFolder", {"path": "Doomed"})
    assert world.run() is TaskState.COMPLETED
    assert not (work / "Doomed").exists()
    service.flush()

    (work / "Doomed").mkdir()  # recreate: replay must not delete it again
    replay_events_into(MissionControl(), store.read_events())

    assert (work / "Doomed").exists(), "replay re-executed an irreversible action"


# ---- one funnel, no alternate path --------------------------------------


def test_the_runtime_reaches_a_gateway_from_exactly_one_place():
    """Requirement 6: one and only one execution funnel. If a second
    `gateway.invoke(...)` site ever appears in `runtime/`, it is an
    alternate execution path and this fails."""
    sites = []
    for path in RUNTIME_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "invoke"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "gateway"
            ):
                sites.append(f"{path.name}:{node.lineno}")

    assert len(sites) == 1, f"more than one execution funnel: {sites}"
    assert sites[0].startswith("engine.py:"), sites


def test_the_approval_check_precedes_the_only_dispatch_path():
    """`_handle_task` must consult the boundary before it calls
    `_execute_with_retry`. Asserted on the AST, because a reordering that
    put execution first would still pass every behavioural test that
    happens to grant approval."""
    tree = ast.parse((RUNTIME_DIR / "engine.py").read_text(encoding="utf-8"))
    handler = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_handle_task"
    )
    lines = {
        node.func.attr: node.lineno
        for node in ast.walk(handler)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert "_require_approval" in lines, "the boundary is not consulted at the funnel"
    assert lines["_require_approval"] < lines["_execute_with_retry"], (
        "execution is reached before the approval boundary"
    )


def test_the_runtime_imports_no_permission_system():
    """The boundary is a protocol defined inside `runtime/` (ADR-0019), so
    the Runtime consults it without depending on Shared Infrastructure's
    Permission System — the same property `CheckpointSink` gives it for
    storage."""
    offenders = []
    for path in RUNTIME_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and "permissions" in (node.module or ""):
                offenders.append(f"{path.name}: {node.module}")

    assert offenders == [], f"runtime/ imports the Permission System: {offenders}"


# ---- the gate itself ----------------------------------------------------


def test_the_gate_fails_closed_on_an_unclassifiable_capability(tmp_path):
    """A capability whose risk cannot be established is not thereby safe."""
    world = World(tmp_path)
    gate = PermissionSystemGate(world.permissions, world.registry)

    with pytest.raises(ApprovalDenied) as denied:
        gate.check(
            ApprovalRequest(
                executive_id="filesystem",
                qualified_capability="Filesystem.Nonexistent",
                local_capability="nonexistent",
                task_id="t1",
            )
        )

    assert "risk tier unresolvable" in denied.value.reason


def test_a_broken_reporter_never_changes_whether_work_is_authorised(tmp_path):
    world = World(tmp_path)
    world.approve("create_folder")

    def explode(*_args):
        raise RuntimeError("reporter down")

    gate = PermissionSystemGate(world.permissions, world.registry, on_decision=explode)
    gate.check(
        ApprovalRequest(
            executive_id="filesystem",
            qualified_capability="Filesystem.CreateFolder",
            local_capability="create_folder",
            task_id="t1",
        )
    )

    assert gate.reporting_failures, "the reporting failure was swallowed silently"


def test_every_irreversible_capability_is_covered_without_naming_one(tmp_path):
    """Deliverable 4 is a *classification*, not a list. The Runtime must
    never know which capabilities exist (MB024 Rule 2), so the guarantee
    has to hold for every capability declaring IRREVERSIBLE — including
    ones that do not exist yet."""
    world = World(tmp_path)
    gate = PermissionSystemGate(world.permissions, world.registry)

    irreversible = [
        c.name
        for c in world.plugin.manifest.capabilities
        if c.risk_tier is RiskTier.IRREVERSIBLE
    ]
    assert irreversible, "this test is meaningless if nothing is irreversible"

    for capability in irreversible:
        world.approve(capability, GrantScope.ALWAYS_FOR_CAPABILITY)
        with pytest.raises(ApprovalDenied):
            gate.check(
                ApprovalRequest(
                    executive_id="filesystem",
                    qualified_capability=f"Filesystem.{capability}",
                    local_capability=capability,
                    task_id="t1",
                )
            )
