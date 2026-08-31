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

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from master_agent.ai_infrastructure.approval import ProviderApprovalGate
from master_agent.ai_infrastructure.cache import ExactPromptCache, NullPromptCache
from master_agent.ai_infrastructure.execution import PromptExecutor
from master_agent.ai_infrastructure.ledger import (
    LEDGER_FILENAME,
    DecisionLedger,
    JsonFileDecisionStore,
)
from master_agent.ai_infrastructure.occupancy import ProviderOccupancy
from master_agent.ai_infrastructure.profiles import ProviderSource
from master_agent.ai_infrastructure.service import AiCapabilityService
from master_agent.ai_infrastructure.executive import AiInfrastructurePlugin
from master_agent.broker.broker import CapabilityBroker
from master_agent.broker.policy import get_policy
from master_agent.capabilities.extraction import contracts_from_actions
from master_agent.capabilities.index import build_index
from master_agent.config import MasterAgentConfig, load_config
from master_agent.dashboard.app import FounderDashboard, build_dashboard
from master_agent.desktop.plugin import DesktopPlugin
from master_agent.executor.action import default_locations
from master_agent.executor.executor import LocalExecutor
from master_agent.memory.knowledge_store import JsonKnowledgeStore
from master_agent.memory.memory_service import MemoryService
from master_agent.mission_control.adapters import discover_executives
from master_agent.mission_control.capabilities import qualified_name
from master_agent.mission_control.mission_control import MissionControl
from master_agent.missions.history import (
    HISTORY_FILENAME,
    JsonFilePlanStore,
    PlanHistory,
)
from master_agent.missions.service import MissionService
from master_agent.permissions.permission_system import GrantScope, PermissionSystem
from master_agent.persistence.recovery import RecoveryReport, recover
from master_agent.persistence.service import PersistenceService
from master_agent.persistence.store import JsonFileStateStore
from master_agent.brain import IntentLayer, Reporter
from master_agent.planner.planner import Planner
from master_agent.plugins.base import Plugin
from master_agent.plugins.filesystem_plugin import FilesystemPlugin
from master_agent.plugins.model_router import ModelRouter
from master_agent.plugins.registry import PluginRegistry
from master_agent.providers.gemini import GeminiProvider
from master_agent.providers.ollama import OllamaProvider
from master_agent.runtime.approval import FounderApprovalGate, PermissionSystemGate
from master_agent.runtime.config import RuntimeConfig
from master_agent.runtime.engine import RuntimeEngine
from master_agent.runtime.gateway import PluginGateway
from master_agent.plugins.filesystem_gateway import FilesystemGateway
from master_agent.plugins.filesystem_worker import FilesystemWorker
from master_agent.verification.evidence import Evidence, ExpectedOutcome, Verdict
from datetime import UTC, datetime

OK = "ok"
UNAVAILABLE = "unavailable"
WARNING = "warning"

# MB027.5 shipped with execution opt-in behind `--enable-execution`,
# because the Runtime path consulted nothing: an IRREVERSIBLE
# `delete_folder` completed with no approval anywhere. **MB028.0 closed
# that** (ADR-0019): the Runtime now consults an `ApprovalGate` at its
# single funnel and fails closed without one. The flag is gone -- a safety
# flag that outlives its hazard teaches founders to ignore flags.
APPROVAL_BOUNDARY_DETAIL = (
    "every capability above READ_ONLY is checked before it runs; anything "
    "unapproved waits for you in the Approval panel"
)


def estimate_impact(request: Any) -> str:
    """A founder-readable estimate of what a capability would do
    (Deliverable 1). Lives in the composition root, not in `runtime/`,
    because interpreting a payload means knowing what a payload means --
    which is exactly the Executive knowledge the Runtime must not have.

    Deliberately best-effort: an estimate it cannot compute is reported as
    unknown, never guessed. A wrong number here is worse than no number,
    because a founder would approve against it.
    """
    payload = request.payload or {}
    target = payload.get("path") or payload.get("name")
    capability = request.local_capability

    if capability == "delete_folder" and target:
        for root in default_locations().values():
            candidate = root / str(target)
            if candidate.is_dir():
                files = sum(1 for item in candidate.rglob("*") if item.is_file())
                return f"Deletes {files} file(s) in '{target}'"
        return f"Deletes folder '{target}' (not found on disk; may already be gone)"
    if capability == "delete_file" and target:
        return f"Deletes file '{target}'"
    if target:
        return f"{capability.replace('_', ' ')} on '{target}'"
    return "unknown"

# MB027.5 shipped this step reporting "frozen but not implemented", because
# the Broker was architecture and nothing more. MB031 built the engine and
# **MB032 wired it**, so the step now constructs it and reports what it
# actually built.
#
# The reason survives for the case that still matters: a Broker that could
# not be constructed. The system then **fails closed** -- the Model Router
# is left with no selector and refuses every AI request (MB032 Deliverable
# 10). A launcher that silently continued would hand the founder a system
# that looks fine and quietly cannot think.
BROKER_UNAVAILABLE_REASON = (
    "the AI Capability Broker could not be constructed; no provider "
    "selection is available and every AI request will be refused"
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
    # MB027.5 reserved this seam and left it empty; MB032 fills it. Still
    # `None`-able, because a Broker that failed to construct must be a
    # value the system can report rather than a hole -- and because
    # `intelligence` being None is what makes the Model Router refuse
    # (`ModelRouter.has_broker`).
    broker: Any = None
    #: The Broker, wired: profiles in, decisions recorded, paid selections
    #: routed to the Approval Queue (`ai_infrastructure.AiCapabilityService`).
    intelligence: Any = None
    #: The Brain's door to reasoning. Constructed here so that *one* router
    #: exists with the Broker behind it, rather than each caller building
    #: its own and choosing whether to wire one.
    model_router: Any = None
    #: MB033. A **second** `PluginRegistry`, holding model providers only.
    #: Deliberately not the Executive registry: ADR-0017 Decision 8 rules
    #: that an AI Capability is not a Constitution Capability, so a
    #: provider is not a dispatchable Executive and must not appear in
    #: Mission Control's registry, the Runtime's gateway map, or the
    #: Dashboard's Executive list. Same class, different instance, no
    #: change to any of the three.
    providers: Any = None
    #: Runs what the Broker chose, and records what happened.
    prompt_executor: Any = None
    #: MB034. What the founder has told Kalpavriksha, and what it observed
    #: about its own work, across restarts.
    memory: Any = None
    #: The Intent Layer — turns raw input into structured Intent.
    intent_layer: Any = None
    #: The Reporter — converts Mission outcome + Evidence into founder-facing reports.
    reporter: Any = None
    #: MB037. The Planner, the durable record of what it planned, and the
    #: one path from a founder objective to submitted work. `None` when
    #: nothing can execute a prompt -- an objective that cannot be planned
    #: is reported as absent, never planned by something else.
    planner: Any = None
    plan_history: Any = None
    missions: Any = None
    #: MB039. The contract index the Planner plans against.
    capability_index: Any = None

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
    decided_by: str = "founder",
    approval_timeout_seconds: float | None = None,
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
    from master_agent.environment.browser_session import BrowserSessionManager
    from master_agent.plugins.browser_plugin import BrowserPlugin
    sessions = BrowserSessionManager()
    default_plugins = [FilesystemPlugin(executor), DesktopPlugin(executor), AiInfrastructurePlugin(executor), BrowserPlugin(executor, sessions)]
    for plugin in plugins if plugins is not None else default_plugins:
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
    # 4a. The approval boundary (MB028.0, ADR-0019), wired before the
    #     Runtime because the Runtime refuses to execute without it. The
    #     gate delegates to the same Permission System the Orchestrator
    #     uses -- one ledger, one policy, two paths.
    inner_gate = PermissionSystemGate(permissions, registry).report_to(
        mission_control.bus, decided_by
    )
    # MB028.1: when authority is missing, ask instead of refusing. The
    # inner gate is unchanged and still the only thing that consults the
    # Permission System -- the boundary stays singular (ADR-0019).
    approval_gate = FounderApprovalGate(
        inner=inner_gate,
        mission_control=mission_control,
        grant_on_approval=lambda request: permissions.grant(
            request.executive_id, request.local_capability, GrantScope.ONCE
        ),
        timeout_seconds=approval_timeout_seconds,
        describe_impact=estimate_impact,
    )
    runtime = RuntimeEngine(
        mission_control,
        runtime_config or RuntimeConfig(),
        checkpoint_sink=persistence,
        approval_gate=approval_gate,
    )
    report.add("Runtime", OK, "heartbeat constructed, not yet started")

    # 4b. Founder memory (MB034). Before recovery, so the recovery itself
    #     can be remembered; beside the state directory rather than inside
    #     it, because a recovery may legitimately discard operational state
    #     and must never discard what the founder said.
    memory = MemoryService(store=JsonKnowledgeStore(state_dir.parent))
    memory_load = memory.load()
    watching = memory.attach_to(mission_control)
    report.add(
        "Founder Memory",
        WARNING if memory_load.problems else OK,
        f"{memory_load.summary}; watching {len(watching)} event type(s)",
    )

    # 5. Recover *before* recording starts. Restoring republishes nothing
    #    (ADR-0015's non-publishing `restore_objective()`), but starting
    #    the recorder first would still risk appending recovered state
    #    back into the log it was recovered from. Recovery reads history;
    #    recording writes it; they must not overlap.
    recovery = recover(persistence, mission_control, runtime)
    report.recovery = recovery
    # Recovery publishes nothing (ADR-0015's non-publishing restore), so
    # there is no event to subscribe to and the composition root hands the
    # report in -- the same shape the Dashboard receives it.
    memory.remember_recovery(recovery)
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

    # 8. AI Capability Broker (MB032) — constructed, not merely reported.
    #    After Executives, because the estate it decides over is read from
    #    the Desktop Executive's machine scan; before the Dashboard,
    #    because the Dashboard displays its decisions.
    #
    #    The whole step is guarded: a Broker that cannot be built leaves
    #    `intelligence` None, which leaves the Model Router without a
    #    selector, which makes it refuse every request with a reason.
    #    Failing closed is the design, not the error path.
    desktop = next(
        (p for p in registry.all_plugins() if p.manifest.name == "desktop"), None
    )
    inventory_provider = (
        (lambda: desktop.cached_inventory) if desktop is not None else None
    )
    broker: Any = None
    intelligence: Any = None
    try:
        policy = get_policy(config.broker.policy)
        ledger = DecisionLedger(
            store=JsonFileDecisionStore(state_dir / LEDGER_FILENAME)
        )
        restored = ledger.load()
        # The ledger is the Broker's `sink` (MB031's outbound port), so
        # every decision it makes is recorded before any caller can act on
        # it -- including decisions made by a caller that is not the
        # service below.
        broker = CapabilityBroker(policy=policy, sink=ledger.record)
        providers = ProviderSource(
            inventory_provider=inventory_provider,
            enabled_cloud_providers=config.broker.enabled_cloud_providers,
        )
        intelligence = AiCapabilityService(
            broker=broker,
            providers=providers,
            ledger=ledger,
            approvals=ProviderApprovalGate(
                mission_control=mission_control,
                permissions=permissions,
                timeout_seconds=approval_timeout_seconds,
            ),
            strong_reasoning_min_quality=config.broker.strong_reasoning_min_quality,
        )
        available, total = providers.counts()
        report.add(
            "AI Capability Broker",
            OK,
            f"policy {policy.policy_version}; {available}/{total} provider(s) "
            f"available, {restored} past decision(s) restored",
        )
    except Exception as exc:  # noqa: BLE001 - a broken Broker must not stop the boot
        broker = None
        intelligence = None
        report.add(
            "AI Capability Broker", UNAVAILABLE, f"{BROKER_UNAVAILABLE_REASON}: {exc}"
        )

    # 8a. Provider execution (MB033). A separate registry, for the reason
    #     given on `KalpavrikshaSystem.providers`: a provider is not an
    #     Executive, and putting one in the Executive registry would add it
    #     to Mission Control, the Runtime and the Dashboard -- three of the
    #     subsystems this brief must not touch.
    #
    #     The provider is constructed whether or not Ollama is running.
    #     Reachability is a question for the moment of use, not for boot:
    #     a daemon started five minutes after launch should work, and a
    #     provider that probed at boot would have decided otherwise.
    providers = PluginRegistry()
    provider_detail = "no provider is enabled; nothing can execute a prompt"
    provider_details: list[str] = []
    if config.ollama.enabled:
        providers.register(
            OllamaProvider(
                model=config.ollama.model,
                base_url=config.ollama.base_url,
                timeout_seconds=config.ollama.timeout_seconds,
            )
        )
        provider_details.append(f"model '{config.ollama.model}' at {config.ollama.base_url}")
    # Founder decision: provider search closed, Gemini API selected as the
    # first genuinely programmatic reasoning provider. Registered whether
    # or not a key is configured — the same "construct regardless,
    # reachability is a question for the moment of use" posture the
    # Ollama registration above already takes. A missing key is reported
    # honestly by GeminiProvider.availability()/complete(), never assumed.
    if config.gemini.enabled:
        providers.register(
            GeminiProvider(
                api_key=config.gemini.api_key,
                model=config.gemini.model,
                base_url=config.gemini.base_url,
                timeout_seconds=config.gemini.timeout_seconds,
            )
        )
        provider_details.append(f"model '{config.gemini.model}' at {config.gemini.base_url}")
    if providers.all_plugins():
        provider_detail = (
            f"{len(providers.all_plugins())} provider(s) executable; "
            + "; ".join(provider_details)
        )

    # 8b. The Brain's door to reasoning, with the Broker behind it. Given
    #     `intelligence=None` it refuses every request rather than falling
    #     back to a provider nobody chose (MB032 Deliverable 10).
    model_router = ModelRouter(providers, selector=intelligence)

    # 8c. The thing that carries a decision out. The cache is
    #     `NullPromptCache` unless the founder turns one on -- shipped
    #     behaviour is every lookup missing, because nothing verifies
    #     generated text yet (MB033 Rule 2).
    prompt_executor = None
    if intelligence is not None:
        # MB038. One occupancy register per system, so admission can see
        # that a serialising local provider is already busy -- and so an
        # abandoned call stays counted until something establishes the
        # provider is idle again.
        occupancy = ProviderOccupancy(clock=time.monotonic)
        prompt_executor = PromptExecutor(
            service=intelligence,
            providers=providers,
            ledger=intelligence.ledger,
            cache=(
                ExactPromptCache(allow_unverified=config.prompt_cache.store_unverified)
                if config.prompt_cache.enabled
                else NullPromptCache()
            ),
            store_unverified=config.prompt_cache.store_unverified,
            occupancy=occupancy,
            # MB035: a checked answer teaches the founder's memory
            # something. An outbound port rather than an import, so
            # `ai_infrastructure` stays free of `memory/` and `memory/`
            # stays free of the Broker (MB034 asserts the second).
            memory_sink=lambda prompt, outcome: memory.remember_prompt(
                prompt=prompt,
                provider_id=outcome.provider_id or "unknown",
                verdict=outcome.verdict,
                expectation=(
                    outcome.evidence.expected.description
                    if outcome.evidence is not None
                    else ""
                ),
                evidence_id=(
                    outcome.evidence.evidence_id if outcome.evidence is not None else ""
                ),
            ),
        )
    report.add(
        "Provider execution",
        OK if prompt_executor is not None else UNAVAILABLE,
        provider_detail
        if prompt_executor is not None
        else "no Broker, so nothing can be executed",
    )

    # 9. Gateways. Registered unconditionally now: the boundary is in the
    #    Runtime (step 4a), not in whether a gateway exists, so refusing
    #    to wire one would no longer be a safety measure -- just a system
    #    that cannot work.
    from master_agent.plugins.document_gateway import DocumentGateway

    for plugin in registry.all_plugins():
        if plugin.manifest.name == "filesystem":
            # Wire FilesystemGateway with real verification (same pattern as BrowserGateway in tests)
            # Use the plugin's executor (which has the correct permissions) and extract locations
            plugin_executor = getattr(plugin, "_executor", executor)
            plugin_permissions = getattr(plugin_executor, "permissions", permissions)
            actions = getattr(plugin, "_actions", {})
            locations = None
            for action in actions.values():
                if hasattr(action, "_locations"):
                    locations = action._locations
                    break
            worker = FilesystemWorker(plugin_executor, locations=locations)
            runtime.register_gateway(plugin.manifest.name, FilesystemGateway(worker, plugin_permissions, plugin_executor.name))
        elif plugin.manifest.name == "document":
            actions = getattr(plugin, "_actions", {})
            locations = None
            for action in actions.values():
                if hasattr(action, "_locations"):
                    locations = action._locations
                    break
            runtime.register_gateway(
                plugin.manifest.name,
                DocumentGateway(plugin, locations=locations),
            )
        else:
            runtime.register_gateway(plugin.manifest.name, PluginGateway(plugin))
    report.add(
        "Approval boundary",
        OK,
        APPROVAL_BOUNDARY_DETAIL,
    )

    # 9a. The Planner and the mission pipeline (MB037). Built after the
    #     prompt executor, because planning is a Broker decision like any
    #     other and there is nothing to plan with until one exists; and
    #     before the Dashboard, which reads the plan history.
    #
    #     The catalogue handed to the Planner is Mission Control's own
    #     capability registry -- so the Planner can only ever name a
    #     capability that is really registered, and nothing here holds a
    #     capability name of its own.
    
    # Intent Layer (Constitution §3.1) - turns raw input into structured Intent
    intent_layer = IntentLayer()
    report.add("Intent Layer", OK, "rule-based parsing with clarification support")

    # Reporter (Constitution §3.4) - converts internal state into founder-facing responses
    reporter = Reporter()
    report.add("Reporter", OK, "templates for mission/step outcomes, approvals, clarifications")

    planner = None
    plan_history = None
    missions = None
    # MB039. `None` rather than an empty index: a system with no Broker
    # never built one, which is a different fact from a system whose
    # capabilities publish nothing. An empty index would read as the
    # second.
    capability_index = None
    if prompt_executor is None:
        report.add(
            "Planner",
            UNAVAILABLE,
            "no provider execution, so an objective cannot be planned",
        )
    else:
        # MB039. The Planner reads the **contract index**, not the
        # capability registry: the registry publishes a sentence about a
        # capability and the index publishes its argument names. MB037's
        # first live plan named the right two capabilities and got both
        # payloads wrong because a sentence was all there was.
        #
        # Contracts are derived from the Action objects the plugins
        # already hold, so adding a capability adds a contract and the two
        # cannot drift.
        contracts: list[Any] = []
        for plugin in registry.all_plugins():
            actions = getattr(plugin, "_actions", None)
            if isinstance(actions, dict):
                contracts.extend(
                    contracts_from_actions(
                        actions, plugin.manifest.name, qualified_name
                    )
                )
        capability_index = build_index(
            contracts, loader={c.canonical_id: c for c in contracts}.get
        )
        planner = Planner(prompt_executor, capability_index)
        plan_history = PlanHistory(
            store=JsonFilePlanStore(state_dir / HISTORY_FILENAME)
        )
        watched = plan_history.attach_to(mission_control)
        missions = MissionService(
            planner=planner,
            mission_control=mission_control,
            intent_layer=intent_layer,
            reporter=reporter,
            history=plan_history,
            memory=memory,
        )
        report.add(
            "Planner",
            OK,
            f"{len(capability_index)} capability contract(s) to plan with, "
            f"{len(capability_index.unspecified())} with no published "
            f"arguments; history watching {len(watched)} event type(s)",
        )

    # 10. Dashboard last: it observes everything above, and per ADR-0016
    #     Decision 5 it is *handed* the recovery report rather than
    #     discovering one, because calling `recover()` would be both a
    #     mutation and orchestration.
    # MB030: the Dashboard reads the last machine scan; it never triggers
    # one (ADR-0016 Decision 5 -- handed in, never discovered). MB032 hands
    # in Broker decisions through the same kind of read-only callable: the
    # Dashboard displays what was decided and can no more cause a decision
    # than it can cause a scan.
    dashboard = build_dashboard(
        mission_control=mission_control,
        runtime=runtime,
        persistence=persistence,
        recovery_report=recovery,
        inventory_provider=inventory_provider,
        broker_provider=(
            (lambda: intelligence.report()) if intelligence is not None else None
        ),
        memory_provider=memory.summary,
        plan_provider=(lambda: plan_history) if plan_history is not None else None,
        **(dashboard_kwargs or {}),
    )
    report.add("Founder Dashboard", OK, "attached to the event bus")

    # REMOVED: two callbacks that manufactured Evidence.
    #
    # They rebuilt an `Evidence` object per step from nothing but an
    # `evidence_id` and a verdict, filling the rest in:
    #
    #     worker="filesystem"                 # for EVERY step
    #     environment="filesystem_environment"
    #     captured_at=datetime.now(UTC)       # report time, not observation time
    #     observation={}
    #     check_results=[]
    #
    # A Browser step came back claiming a filesystem worker, and a
    # historical observation acquired the timestamp of the moment the
    # report was generated. That is not Evidence; it is fabricated
    # metadata wearing the Evidence type, and an `evidence_id` is a
    # correlation key rather than a record of what was observed.
    #
    # Both callbacks discarded the `Report` they built, and
    # `report_mission_outcome()` is pure -- it persists nothing -- so
    # this was dead code whose only effect was to make fabrication look
    # supported. Real Evidence now travels on VERIFICATION_COMPLETED and
    # is retained on `StepRecord.evidence`; a future Reporter wiring
    # consumes that, and is a separate mission.

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
        intelligence=intelligence,
        model_router=model_router,
        providers=providers,
        prompt_executor=prompt_executor,
        memory=memory,
        intent_layer=intent_layer,
        reporter=reporter,
        planner=planner,
        capability_index=capability_index,
        plan_history=plan_history,
        missions=missions,
    )
