"""Boot sequence for the whole system (Mission Brief 027.5).

This module is the **composition root**: the one place permitted to know
about every layer at once, because its only job is to construct them and
wire them together. It holds no policy, executes no capability, decides
nothing, and adds no architecture — every component it touches shipped in
MB022–MB026 and is used through its published contract, unmodified.

Two rules keep that claim true, and both are enforced by
`tests/test_launcher.py` rather than by intention:

1. **Nothing in `src/` imports this package.** A composition root that
   something depends on has stopped being one.
2. **Every step reports its real status.** A step that could not run
   reports `unavailable` *with a reason* — never `ok`. `0` and "unknown"
   are different facts (ADR-0016), and a launcher that claims a subsystem
   started when it did not is worse than one that refuses to start.

Ordering rationale for each step is in `docs/MISSION_BRIEF_027_5.md`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from master_agent.config import MasterAgentConfig, load_config
from master_agent.dashboard.app import FounderDashboard, build_dashboard
from master_agent.executor.executor import LocalExecutor
from master_agent.mission_control.adapters import discover_executives
from master_agent.mission_control.mission_control import MissionControl
from master_agent.permissions.permission_system import PermissionSystem
from master_agent.persistence.recovery import RecoveryReport, recover
from master_agent.persistence.service import PersistenceService
from master_agent.persistence.store import JsonFileStateStore
from master_agent.plugins.base import Plugin
from master_agent.plugins.filesystem_plugin import FilesystemPlugin
from master_agent.plugins.registry import PluginRegistry
from master_agent.runtime.config import RuntimeConfig
from master_agent.runtime.engine import RuntimeEngine
from master_agent.runtime.gateway import PluginGateway

OK = "ok"
UNAVAILABLE = "unavailable"
WARNING = "warning"

# Why execution is opt-in, and why this constant is a paragraph rather
# than a flag name: on the Runtime path, **nothing consults the Permission
# System**. `FilesystemPlugin.invoke()` grants itself a ONCE permission on
# the Executor's key (the ADR-0005 relay) on the assumption that the
# Orchestrator already gated the call at the plugin/capability key — but
# the Runtime does not go through the Orchestrator. It calls the gateway,
# which calls `invoke()` directly. Verified by running it: an IRREVERSIBLE
# `delete_folder` completes with no approval anywhere.
#
# That gap predates this Mission Brief (MB024 built the path; MIT-001
# certified it) and closing it means changing frozen components, which is
# its own brief. What MB027.5 must not do is make it reachable by a
# founder typing one command *without saying so*. So execution is opt-in,
# and both postures are stated at every boot.
EXECUTION_DISABLED_DETAIL = (
    "observation only; no gateways registered, so dispatched tasks will not run"
)
EXECUTION_ENABLED_DETAIL = (
    "ENABLED and UNGATED - the Runtime path does not consult the Permission "
    "System, so any dispatched capability runs, including IRREVERSIBLE ones "
    "(see docs/MISSION_BRIEF_027_5.md)"
)

# Why the Broker step exists but cannot succeed: MB027 froze the AI
# Capability Broker's architecture and the founder ratified it, but no
# implementation exists yet (`ROADMAP.md`, Planned item 6). The launcher
# reports that honestly instead of omitting the step, so the gap is
# visible at every boot rather than discovered later by someone wondering
# why nothing selects a provider.
BROKER_UNAVAILABLE_REASON = (
    "architecture frozen (MB027, ADR-0017) but not implemented; "
    "no provider selection is available in this build"
)


@dataclass(frozen=True)
class BootStep:
    """One line of the boot report. Frozen because a report of what
    already happened should not be editable by whoever reads it."""

    name: str
    status: str
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status == OK

    def as_line(self) -> str:
        mark = {OK: "OK  ", UNAVAILABLE: "--  ", WARNING: "WARN"}.get(self.status, "??  ")
        suffix = f"  ({self.detail})" if self.detail else ""
        return f"[{mark}] {self.name}{suffix}"


@dataclass
class BootReport:
    steps: list[BootStep] = field(default_factory=list)
    recovery: RecoveryReport | None = None

    def add(self, name: str, status: str, detail: str = "") -> BootStep:
        step = BootStep(name=name, status=status, detail=detail)
        self.steps.append(step)
        return step

    def step(self, name: str) -> BootStep | None:
        for step in self.steps:
            if step.name == name:
                return step
        return None

    @property
    def needs_attention(self) -> list[BootStep]:
        """Every step a founder should actually read. Kept as a property
        rather than printed inline so a caller decides how loud to be."""
        return [step for step in self.steps if not step.ok]

    def as_lines(self) -> list[str]:
        return [step.as_line() for step in self.steps]


@dataclass
class KalpavrikshaSystem:
    """Everything the launcher built, held together so a caller can start
    it, stop it, and inspect it. A plain container — it delegates every
    operation to the component that owns it."""

    config: MasterAgentConfig
    state_dir: Path
    permissions: PermissionSystem
    executor: LocalExecutor
    registry: PluginRegistry
    mission_control: MissionControl
    store: JsonFileStateStore
    persistence: PersistenceService
    runtime: RuntimeEngine
    dashboard: FounderDashboard
    report: BootReport
    # Reserved seam, deliberately empty. When the AI Capability Broker is
    # implemented it is constructed in `build_system()` and lands here;
    # nothing else in this module changes. It is None rather than absent
    # so the gap is a value the system can report, not a hole.
    broker: Any = None

    def start(self) -> None:
        """Start the heartbeat. The Dashboard is *not* started here —
        whether it runs in the foreground or the background is the
        caller's decision, and the two have different lifetimes."""
        self.runtime.start_background()

    def stop(self, timeout: float = 5.0) -> list[str]:
        """Stop in reverse order of construction, then checkpoint.

        Two properties worth stating. **No failing step prevents the
        next** — a launcher that leaves a daemon thread running because an
        earlier stop raised is how a founder ends up with two Runtimes
        against one state directory. And **the snapshot is written last**,
        after both loops are quiet, so it describes a system at rest
        rather than one mid-cycle; `save()` flushes buffered events before
        writing it, so a crash between the two loses nothing the log
        cannot answer for.

        Returns whatever went wrong, rather than swallowing it: a failed
        shutdown step is exactly the kind of thing a founder needs told
        (a snapshot that did not get written is silent data loss at the
        next launch), and returning it keeps this method free of any
        opinion about how to report.
        """
        problems: list[str] = []
        for label, stop in (
            ("dashboard", lambda: self.dashboard.stop(timeout=timeout)),
            ("runtime", lambda: self.runtime.stop(timeout=timeout)),
            (
                "final snapshot",
                lambda: self.persistence.save(
                    self.mission_control, self.runtime.checkpoint()
                ),
            ),
        ):
            try:
                stop()
            except Exception as exc:  # noqa: BLE001 - shutdown must be total
                problems.append(f"{label}: {exc}")
        return problems


def build_system(
    state_dir: Path | None = None,
    config: MasterAgentConfig | None = None,
    runtime_config: RuntimeConfig | None = None,
    plugins: list[Plugin] | None = None,
    enable_execution: bool = False,
    dashboard_kwargs: dict[str, Any] | None = None,
) -> KalpavrikshaSystem:
    """Construct a complete, wired Kalpavriksha and report on the boot.

    Does **not** start anything — construction and starting are separate
    so a caller (or a test) can inspect a fully-built system before it
    begins moving.
    """
    config = config or load_config()
    state_dir = Path(state_dir) if state_dir is not None else config.app_dir / "state"
    report = BootReport()

    # 1. Shared Infrastructure. Permission System first: it is the gate
    #    every layer above it consults, so nothing should exist before it.
    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    registry = PluginRegistry()
    for plugin in plugins if plugins is not None else [FilesystemPlugin(executor)]:
        registry.register(plugin)
    report.add(
        "Shared Infrastructure",
        OK,
        f"{len(registry.all_plugins())} plugin(s), permission system armed",
    )

    # 2. Mission Control — the coordination layer everything else plugs
    #    into. Must exist before persistence, which subscribes to its bus.
    mission_control = MissionControl()
    report.add("Mission Control", OK, "event bus, registries, dispatcher")

    # 3. Persistence. Constructed before recovery for the obvious reason
    #    that recovery reads through it.
    store = JsonFileStateStore(state_dir)
    persistence = PersistenceService(store, mission_control)
    report.add("Persistence", OK, f"state at {state_dir}")

    # 4. Runtime. Built before recovery so `recover()` can restore the
    #    cycle counter into it (`RuntimeCheckpoint`) in the same pass —
    #    otherwise a restored system reports uptime and cycles it did not
    #    have, which MB025 found the hard way.
    runtime = RuntimeEngine(
        mission_control,
        runtime_config or RuntimeConfig(),
        checkpoint_sink=persistence,
    )
    report.add("Runtime", OK, "heartbeat constructed, not yet started")

    # 5. Recover *before* recording starts. Restoring republishes nothing
    #    (ADR-0015's non-publishing `restore_objective()`), but starting
    #    the recorder first would still risk appending recovered state
    #    back into the log it was recovered from. Recovery reads history;
    #    recording writes it; they must not overlap.
    recovery = recover(persistence, mission_control, runtime)
    report.recovery = recovery
    report.add(
        "Recovery",
        OK,
        f"{recovery.source}: {recovery.objectives} objective(s), "
        f"{recovery.quarantined_tasks} quarantined"
        if recovery.recovered
        else "no previous state; first run",
    )

    # 6. Now record. Everything from this instant forward is durable.
    persistence.start_recording()
    report.add("Event recording", OK, "subscribed to every event type")

    # 7. Discover Executives. After recovery on purpose: recovery restores
    #    the Executives that already existed, and discovery is idempotent
    #    (it skips anything already registered), so this adds only what is
    #    genuinely new since the last run — and does so *after* recording
    #    began, so the registration is in the log for the next replay.
    discovered = discover_executives(mission_control, registry)
    report.add(
        "Executives",
        OK,
        f"{len(discovered)} newly discovered, "
        f"{len(mission_control.executives.all())} registered, "
        f"{len(mission_control.capabilities.all())} capabilities",
    )

    # 8. AI Capability Broker — reported, not skipped. See
    #    BROKER_UNAVAILABLE_REASON.
    broker = None
    report.add("AI Capability Broker", UNAVAILABLE, BROKER_UNAVAILABLE_REASON)

    # 9. Execution posture. Registering a gateway is what makes a
    #    dispatched task actually run, so this single wiring choice is the
    #    difference between a system that watches and a system that acts.
    #    It is stated at every boot because a founder should never have to
    #    read source to find out what the thing they just launched can do
    #    without asking. See EXECUTION_ENABLED_DETAIL for why it is
    #    opt-in.
    if enable_execution:
        for plugin in registry.all_plugins():
            runtime.register_gateway(plugin.manifest.name, PluginGateway(plugin))
        report.add("Execution posture", WARNING, EXECUTION_ENABLED_DETAIL)
    else:
        report.add("Execution posture", UNAVAILABLE, EXECUTION_DISABLED_DETAIL)

    # 10. Dashboard last: it observes everything above, and per ADR-0016
    #     Decision 5 it is *handed* the recovery report rather than
    #     discovering one, because calling `recover()` would be both a
    #     mutation and orchestration.
    dashboard = build_dashboard(
        mission_control=mission_control,
        runtime=runtime,
        persistence=persistence,
        recovery_report=recovery,
        **(dashboard_kwargs or {}),
    )
    report.add("Founder Dashboard", OK, "attached to the event bus")

    return KalpavrikshaSystem(
        config=config,
        state_dir=state_dir,
        permissions=permissions,
        executor=executor,
        registry=registry,
        mission_control=mission_control,
        store=store,
        persistence=persistence,
        runtime=runtime,
        dashboard=dashboard,
        report=report,
        broker=broker,
    )
