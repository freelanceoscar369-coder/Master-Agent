"""Mission Brief 027.5 — the Kalpavriksha Launcher.

Tests the complete flow (Constitution Rule 11): a real Permission System,
a real Mission Control, real persistence on a real temp directory, a real
Runtime, and a real Dashboard. Nothing here is a fake — the whole claim of
this Mission Brief is that the launcher wires *shipped* components through
their published contracts, and a fake shaped for the launcher would not
test that claim.
"""
from __future__ import annotations

import ast
from pathlib import Path

from master_agent.executor.executor import LocalExecutor
from master_agent.launcher.boot import (
    BROKER_UNAVAILABLE_REASON,
    OK,
    UNAVAILABLE,
    build_system,
)
from master_agent.launcher.main import build_parser, demo_objective, main
from master_agent.plugins.filesystem_plugin import FilesystemPlugin
from master_agent.runtime.config import RuntimeConfig

SRC = Path(__file__).resolve().parents[1] / "src" / "master_agent"


def quiet_system(state_dir: Path, **kwargs):
    """A system whose Dashboard writes nowhere and whose Runtime does not
    sleep — so tests are silent and fast without changing any wiring."""
    kwargs.setdefault("runtime_config", RuntimeConfig(poll_interval_seconds=0))
    kwargs.setdefault("dashboard_kwargs", {"writer": lambda _text: None})
    return build_system(state_dir=state_dir, **kwargs)


# ---- the system comes up whole -----------------------------------------


def test_one_call_produces_a_fully_wired_system(tmp_path):
    system = quiet_system(tmp_path / "state")

    assert system.mission_control is not None
    assert system.runtime is not None
    assert system.persistence is not None
    assert system.dashboard is not None
    assert system.registry.all_plugins(), "no Executive was registered"


def test_every_boot_step_is_reported(tmp_path):
    system = quiet_system(tmp_path / "state")
    names = [step.name for step in system.report.steps]

    assert names == [
        "Shared Infrastructure",
        "Mission Control",
        "Persistence",
        "Runtime",
        "Founder Memory",
        "Recovery",
        "Event recording",
        "Executives",
        "AI Capability Broker",
        "Provider execution",
        "Approval boundary",
        # MB037. After the boundary because a plan is only worth having if
        # the thing that executes it is gated, and before the Dashboard
        # because the Dashboard reads the plan history.
        "Intent Layer",
        "Reporter",
        "Planner",
        "Founder Dashboard",
    ]


def test_the_dashboard_is_attached_and_renders_a_real_frame(tmp_path):
    """MB029 made the founder page the default, so this asserts what a
    founder now sees; the technical page still carries the engineering
    detail it always did."""
    from master_agent.dashboard.app import TECHNICAL_PAGE

    system = quiet_system(tmp_path / "state")

    founder = system.dashboard.render()
    assert "KALPAVRIKSHA" in founder
    assert "Filesystem" in founder, "the discovered Executive should be visible"

    system.dashboard.show(TECHNICAL_PAGE)
    technical = system.dashboard.render()
    assert "RUNTIME" in technical
    assert "filesystem" in technical.lower()


def test_capabilities_reach_mission_control_from_the_plugin_manifest(tmp_path):
    system = quiet_system(tmp_path / "state")

    names = system.mission_control.capabilities.names()

    assert "Filesystem.CreateFolder" in names
    assert len(names) >= 14, "MB005 shipped fourteen filesystem capabilities"


# ---- the Broker is wired, and says what it wired ------------------------


def test_the_broker_step_reports_what_it_built(tmp_path):
    """MB027.5 reported this step as "frozen but not implemented"; MB031
    built the engine and MB032 wired it. The step now names the policy and
    the estate, because "OK" without a reason is the same non-answer as
    "unavailable" without one."""
    system = quiet_system(tmp_path / "state")
    step = system.report.step("AI Capability Broker")

    assert step is not None
    assert step.status == OK
    assert "balanced/1" in step.detail
    assert "provider(s) available" in step.detail
    assert system.broker is not None
    assert system.intelligence is not None


def test_a_broker_that_cannot_be_built_fails_the_system_closed(tmp_path):
    """Deliverable 10. An unknown policy name is the cheapest way to make
    construction fail for real, rather than by patching a mock in."""
    from master_agent.config import BrokerConfig, MasterAgentConfig

    config = MasterAgentConfig(broker=BrokerConfig(policy="no-such-policy"))
    system = quiet_system(tmp_path / "state", config=config)
    step = system.report.step("AI Capability Broker")

    assert step.status == UNAVAILABLE
    assert BROKER_UNAVAILABLE_REASON in step.detail
    assert system.broker is None
    assert system.intelligence is None
    assert system.model_router.has_broker is False


def test_an_unavailable_step_is_never_reported_as_ok(tmp_path):
    """ADR-0016's discipline applied to boot: absence with a reason, never
    a plausible-looking success."""
    system = quiet_system(tmp_path / "state")

    for step in system.report.steps:
        if step.status != OK:
            assert step.detail, f"{step.name} is not OK without saying why"
    assert system.report.needs_attention == [], (
        "MB028.0 removed the execution-posture warning by removing the hazard, "
        "and MB032 removed the Broker warning by wiring the Broker"
    )


# ---- execution posture --------------------------------------------------


def test_gateways_are_wired_and_the_boundary_is_reported(tmp_path):
    """MB027.5 refused to register gateways because the Runtime path was
    ungated. MB028.0 gated it, so the gateways are wired unconditionally
    and the boot report states the boundary instead of a warning."""
    system = quiet_system(tmp_path / "state")

    assert "filesystem" in system.runtime._gateways
    step = system.report.step("Approval boundary")
    assert step.status == OK
    assert "waits for you in the Approval panel" in step.detail


def test_the_launcher_wires_a_real_approval_gate(tmp_path):
    """Fail-closed only helps if the founder command actually wires one."""
    from master_agent.runtime.approval import FounderApprovalGate

    system = quiet_system(tmp_path / "state")

    assert isinstance(system.runtime._approval_gate, FounderApprovalGate)


def test_the_runtime_path_is_no_longer_ungated(tmp_path):
    """MB027.5 shipped this test asserting the *defect*: a bare
    `PluginGateway` deleted a folder with no approval anywhere. It was
    written to fail when the gap closed. **MB028.0 closed it**, so the
    test now asserts the fix, and the boundary it asserts is the Runtime's
    -- a gateway on its own still has no opinion, which is exactly why the
    boundary could not live inside one (ADR-0019)."""
    from master_agent.mission_control.adapters import discover_executives
    from master_agent.mission_control.mission_control import MissionControl
    from master_agent.mission_control.tasks import Objective, Task, TaskState
    from master_agent.permissions.permission_system import PermissionSystem
    from master_agent.plugins.registry import PluginRegistry
    from master_agent.runtime.approval import PermissionSystemGate
    from master_agent.runtime.engine import RuntimeEngine
    from master_agent.runtime.gateway import PluginGateway

    sandbox = tmp_path / "desk"
    sandbox.mkdir()
    (sandbox / "Doomed").mkdir()

    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    plugin = FilesystemPlugin(executor, locations={"desktop": sandbox})
    registry = PluginRegistry()
    registry.register(plugin)
    mc = MissionControl()
    discover_executives(mc, registry)

    engine = RuntimeEngine(
        mc,
        RuntimeConfig(poll_interval_seconds=0, max_cycles=4),
        sleep=lambda _s: None,
        approval_gate=PermissionSystemGate(permissions, registry),
    )
    engine.register_gateway("filesystem", PluginGateway(plugin))
    mc.submit_objective(
        Objective(
            description="delete without approval",
            tasks=[
                Task(
                    capability="Filesystem.DeleteFolder",
                    payload={"path": "Doomed"},
                    task_id="t1",
                )
            ],
        )
    )

    engine.run_forever()

    assert mc.dispatcher.objectives()[0].task("t1").state is TaskState.FAILED
    assert (sandbox / "Doomed").exists(), "an IRREVERSIBLE delete ran unapproved"


# ---- recovery across a real restart -------------------------------------


def test_a_second_launch_recovers_the_first_launchs_state(tmp_path):
    state = tmp_path / "state"

    first = quiet_system(state)
    first.mission_control.submit_objective(demo_objective())
    first.stop()

    second = quiet_system(state)

    assert second.report.recovery.recovered is True
    assert second.report.recovery.objectives == 1
    assert second.report.recovery.source == "snapshot"
    assert "objective(s)" in second.report.step("Recovery").detail


def test_first_run_reports_no_previous_state_rather_than_a_failure(tmp_path):
    system = quiet_system(tmp_path / "state")

    assert system.report.recovery.recovered is False
    assert system.report.step("Recovery").status == OK
    assert "first run" in system.report.step("Recovery").detail


def test_discovery_after_recovery_does_not_duplicate_executives(tmp_path):
    """Recovery restores the Executives that existed; discovery then adds
    only what is new. If the ordering were wrong this raises
    ExecutiveAlreadyRegistered, so this test is the ordering's guard."""
    state = tmp_path / "state"

    first = quiet_system(state)
    first.stop()
    second = quiet_system(state)

    ids = second.mission_control.executives.ids()
    assert ids == sorted(set(ids)), f"duplicate executives after recovery: {ids}"
    assert "0 newly discovered" in second.report.step("Executives").detail


def test_a_new_plugin_is_discovered_on_the_next_launch(tmp_path):
    """The other half of the same ordering claim: idempotent discovery
    must still pick up something genuinely new."""
    from master_agent.permissions.permission_system import PermissionSystem
    from master_agent.plugins.base import PluginManifest

    state = tmp_path / "state"
    quiet_system(state).stop()

    class ExtraPlugin(FilesystemPlugin):
        @property
        def manifest(self) -> PluginManifest:
            base = super().manifest
            return PluginManifest(
                name="extra", version=base.version, capabilities=base.capabilities
            )

    # Each plugin needs its own executor: an executor registers each action
    # exactly once, by name.
    permissions = PermissionSystem()
    second = quiet_system(
        state,
        plugins=[
            FilesystemPlugin(LocalExecutor(permissions)),
            ExtraPlugin(LocalExecutor(permissions)),
        ],
    )

    assert "extra" in second.mission_control.executives.ids()
    assert "1 newly discovered" in second.report.step("Executives").detail


# ---- the loop actually runs ---------------------------------------------


def test_the_runtime_executes_a_submitted_objective_end_to_end(tmp_path):
    """Sandboxed deliberately. `build_system()`'s default plugin uses the
    real `default_locations()` — the founder's actual Desktop — which is
    correct for the shipped command and unacceptable in a test. Passing
    `plugins=` is the seam that keeps the wiring identical while the
    writes land in tmp_path."""
    from master_agent.permissions.permission_system import GrantScope, PermissionSystem

    desk = tmp_path / "desk"
    desk.mkdir()
    system = quiet_system(
        tmp_path / "state",
        plugins=[
            FilesystemPlugin(
                LocalExecutor(PermissionSystem()), locations={"desktop": desk}
            )
        ],
        runtime_config=RuntimeConfig(poll_interval_seconds=0, max_cycles=8),
    )
    for capability in ("create_folder", "write_file"):
        system.permissions.grant("filesystem", capability, GrantScope.THIS_SESSION)
    system.mission_control.submit_objective(demo_objective())

    system.runtime.run_forever()

    state = system.mission_control.founder_state()
    assert state.progress == 1.0, f"objective did not complete: {state.as_dict()}"
    assert (desk / "Kalpavriksha Demo" / "hello.txt").exists(), "no real file written"


def test_no_test_in_this_module_writes_outside_tmp_path():
    """Guard for the mistake this suite actually made once: a test that
    used the default plugin created a folder on the real Desktop. Any test
    enabling execution must pass its own sandboxed `plugins=`."""
    source = Path(__file__).read_text(encoding="utf-8")
    enabling = source.count("enable_execution=True")
    sandboxed = source.count('locations={"desktop"')

    assert enabling <= sandboxed + 2, (
        "a test enables execution without sandboxing the filesystem plugin; "
        "the two exceptions are the tests that register no gateway writes"
    )


def test_shutdown_writes_a_snapshot_a_later_launch_can_read(tmp_path):
    state = tmp_path / "state"
    system = quiet_system(state)

    problems = system.stop()

    assert problems == []
    assert system.persistence.has_state()
    assert system.persistence.load() is not None


def test_shutdown_reports_problems_instead_of_swallowing_them(tmp_path):
    """A snapshot that silently failed to write is data loss discovered at
    the *next* launch. Shutdown continues through a failure, and says so."""
    system = quiet_system(tmp_path / "state")

    def explode(*_args, **_kwargs):
        raise OSError("disk full")

    system.persistence.save = explode

    problems = system.stop()

    assert len(problems) == 1
    assert "final snapshot" in problems[0]
    assert "disk full" in problems[0]


# ---- the CLI surface ----------------------------------------------------


def test_boot_only_prints_the_report_and_starts_nothing(tmp_path, capsys):
    code = main(["--state-dir", str(tmp_path / "state"), "--boot-only"])

    out = capsys.readouterr().out
    assert code == 0
    assert "boot report" in out
    assert "AI Capability Broker" in out
    assert "balanced/1" in out, "the boot report should name the policy in force"


def test_launcher_output_is_ascii_only(tmp_path, capsys):
    """MB026 found that a cp1252 Windows console cannot encode this
    project's usual punctuation. The Dashboard solved it by asking the
    stream; the launcher's own twelve lines simply avoid it. Asserted, not
    trusted, because it is invisible on a UTF-8 terminal."""
    main(["--state-dir", str(tmp_path / "state"), "--boot-only"])

    out = capsys.readouterr().out
    offenders = sorted({c for c in out if ord(c) > 127})
    assert offenders == [], f"non-ASCII in launcher output: {offenders}"
    out.encode("cp1252")  # raises if a real Windows console could not print it


def test_the_parser_exposes_the_documented_flags():
    args = build_parser().parse_args([])

    assert args.approval_timeout is None, "waiting forever is the safe default"
    assert args.demo is False
    assert args.boot_only is False
    assert args.state_dir is None


# ---- the composition-root rule, enforced mechanically -------------------


def test_nothing_in_src_imports_the_launcher():
    """A composition root that something depends on has stopped being one.
    Parses imports rather than grepping, so a re-exported or aliased
    import cannot slip past."""
    offenders = []
    for path in SRC.rglob("*.py"):
        if path.parts[-2] == "launcher":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "master_agent.launcher"
            ):
                offenders.append(f"{path.name}: from {node.module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("master_agent.launcher"):
                        offenders.append(f"{path.name}: import {alias.name}")

    assert offenders == [], f"the launcher must be depended on by nothing: {offenders}"


def test_the_launcher_holds_no_business_logic_of_its_own():
    """It may construct and wire. It must not decide, execute, or verify —
    so it defines no class that implements a subsystem's contract."""
    tree = ast.parse((SRC / "launcher" / "boot.py").read_text(encoding="utf-8"))
    classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]

    assert classes == ["BootStep", "BootReport", "KalpavrikshaSystem"], (
        f"boot.py should define only report/container types, found {classes}"
    )
