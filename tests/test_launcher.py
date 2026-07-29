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
    WARNING,
    build_system,
)
from master_agent.launcher.main import build_parser, demo_objective, main
from master_agent.plugins.base import RiskTier
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
        "Recovery",
        "Event recording",
        "Executives",
        "AI Capability Broker",
        "Execution posture",
        "Founder Dashboard",
    ]


def test_the_dashboard_is_attached_and_renders_a_real_frame(tmp_path):
    system = quiet_system(tmp_path / "state")

    frame = system.dashboard.render()

    assert "Runtime" in frame
    assert "filesystem" in frame.lower(), "the discovered Executive should be visible"


def test_capabilities_reach_mission_control_from_the_plugin_manifest(tmp_path):
    system = quiet_system(tmp_path / "state")

    names = system.mission_control.capabilities.names()

    assert "Filesystem.CreateFolder" in names
    assert len(names) >= 14, "MB005 shipped fourteen filesystem capabilities"


# ---- the Broker gap is reported, never claimed --------------------------


def test_the_broker_step_reports_unavailable_with_a_reason(tmp_path):
    system = quiet_system(tmp_path / "state")
    step = system.report.step("AI Capability Broker")

    assert step is not None
    assert step.status == UNAVAILABLE
    assert step.detail == BROKER_UNAVAILABLE_REASON
    assert system.broker is None


def test_an_unavailable_step_is_never_reported_as_ok(tmp_path):
    """ADR-0016's discipline applied to boot: absence with a reason, never
    a plausible-looking success."""
    system = quiet_system(tmp_path / "state")

    for step in system.report.steps:
        if step.status != OK:
            assert step.detail, f"{step.name} is not OK without saying why"
    assert [s.name for s in system.report.needs_attention] == [
        "AI Capability Broker",
        "Execution posture",
    ]


# ---- execution posture --------------------------------------------------


def test_execution_is_off_by_default(tmp_path):
    system = quiet_system(tmp_path / "state")

    assert system.runtime._gateways == {}, "a founder command must not act by default"
    step = system.report.step("Execution posture")
    assert step.status == UNAVAILABLE
    assert "observation only" in step.detail


def test_enabling_execution_is_reported_as_a_warning_not_a_success(tmp_path):
    """The founder is told, in the boot report, that the path they just
    switched on is ungated. See `test_the_runtime_path_is_ungated`."""
    system = quiet_system(tmp_path / "state", enable_execution=True)

    step = system.report.step("Execution posture")
    assert step.status == WARNING
    assert "does not consult the Permission System" in step.detail
    assert "filesystem" in system.runtime._gateways


def test_the_runtime_path_is_ungated(tmp_path):
    """**Characterises a known defect, deliberately.**

    On the Runtime path nothing consults the Permission System:
    `FilesystemPlugin.invoke()` self-grants a ONCE permission on the
    Executor's key (the ADR-0005 relay), on the assumption the
    Orchestrator already gated the call at the plugin/capability key — and
    the Runtime does not go through the Orchestrator. So an IRREVERSIBLE
    capability runs with no approval, which contradicts Constitution
    Rule 5.

    The gap predates MB027.5 (MB024 built the path, MIT-001 certified it)
    and closing it means changing frozen components. This test exists so
    that **when it is fixed, this fails** — forcing the boot report's
    wording and the Mission Brief's technical-debt section to be corrected
    at the same time, rather than the launcher quietly continuing to warn
    about a gap that no longer exists.
    """
    from master_agent.permissions.permission_system import PermissionSystem
    from master_agent.runtime.gateway import PluginGateway

    sandbox = tmp_path / "desk"
    sandbox.mkdir()
    # Built the way the launcher builds it -- PermissionSystem, executor,
    # plugin, bare PluginGateway -- with "desktop" pointed at a sandbox so
    # this test deletes only its own directory.
    executor = LocalExecutor(PermissionSystem())
    plugin = FilesystemPlugin(executor, locations={"desktop": sandbox})
    gateway = PluginGateway(plugin)

    assert gateway.invoke("create_folder", {"name": "Doomed"}).success
    assert (sandbox / "Doomed").exists()

    irreversible = [
        c.name
        for c in plugin.manifest.capabilities
        if c.risk_tier is RiskTier.IRREVERSIBLE
    ]
    assert "delete_folder" in irreversible

    result = gateway.invoke("delete_folder", {"path": "Doomed"})
    assert result.success, "if this now fails, the gap may be fixed — see docstring"
    assert not (sandbox / "Doomed").exists()


# ---- recovery across a real restart -------------------------------------


def test_a_second_launch_recovers_the_first_launchs_state(tmp_path):
    state = tmp_path / "state"

    first = quiet_system(state, enable_execution=True)
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
    from master_agent.permissions.permission_system import PermissionSystem

    desk = tmp_path / "desk"
    desk.mkdir()
    system = quiet_system(
        tmp_path / "state",
        enable_execution=True,
        plugins=[
            FilesystemPlugin(
                LocalExecutor(PermissionSystem()), locations={"desktop": desk}
            )
        ],
        runtime_config=RuntimeConfig(poll_interval_seconds=0, max_cycles=8),
    )
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
    assert "not implemented" in out


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

    assert args.enable_execution is False, "acting must be opt-in"
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
