"""Mission Brief 032 — the Broker as the founder meets it.

The other file tests the parts. This one tests that they are *connected*:
the launcher builds a Broker, the Dashboard shows what it decided, a
decision survives a restart and still replays against the policy that
produced it, and the Definition of Done's five-step flow

    Task -> Broker -> DecisionRecord -> Approval -> Execution

happens in that order, with nothing reaching a provider before the first
four have.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from master_agent.ai_infrastructure.ledger import (
    GRANTED,
    LEDGER_FILENAME,
    NOT_REQUIRED,
    PENDING,
    DecisionLedger,
    JsonFileDecisionStore,
)
from master_agent.ai_infrastructure.refusal import (
    NoProviderAvailable,
    ProviderApprovalDenied,
    ProviderApprovalPending,
)
from master_agent.ai_infrastructure.service import BrokerReport
from master_agent.broker.policy import BEST_QUALITY, PREFER_LOCAL
from master_agent.config import BrokerConfig, MasterAgentConfig
from master_agent.dashboard.app import FOUNDER_PAGE, TECHNICAL_PAGE
from master_agent.dashboard.charset import ASCII, UNICODE
from master_agent.dashboard.founder import as_dict as founder_as_dict
from master_agent.dashboard.founder import build_founder_view
from master_agent.dashboard.founder_panels import (
    render_founder_frame,
    render_intelligence,
)
from master_agent.dashboard.readmodel import DashboardSnapshot
from master_agent.dashboard.sources import DashboardSources
from master_agent.launcher.boot import build_system
from master_agent.plugins.model_router import ModelRouter, RoutingContext
from master_agent.runtime.config import RuntimeConfig
from tests.broker_test_support import Harness, RecordingProvider

# =========================================================================
# The launcher wires it (Deliverable 2)
# =========================================================================


def quiet_system(state_dir, **kwargs):
    kwargs.setdefault("runtime_config", RuntimeConfig(poll_interval_seconds=0))
    kwargs.setdefault("dashboard_kwargs", {"writer": lambda _text: None})
    return build_system(state_dir=state_dir, **kwargs)


class InstalledProbe:
    """A machine with exactly these executables on it.

    A real `SystemProbe`, not a mock of the Desktop Executive: the scan,
    the catalogue join, and the profile build all run for real, and only
    the machine underneath is invented. Shelling out once per known
    application to discover the developer's own laptop would put a
    multi-second probe in the middle of a unit suite, and would make the
    result depend on what happens to be installed.
    """

    platform = "test"

    def __init__(self, *executables: str) -> None:
        self._present = set(executables)

    def which(self, executable: str) -> str | None:
        return f"/usr/bin/{executable}" if executable in self._present else None

    def exists(self, path: str) -> bool:
        return False

    def run(self, command: list[str]):
        from master_agent.desktop.probe import CommandResult

        return CommandResult(ok=True, output="1.2.3")

    def start(self, command: list[str]):
        from master_agent.desktop.probe import CommandResult

        return CommandResult(ok=False, error="this probe launches nothing")

    def processes(self):
        return []

    def get_store_apps(self):
        return []

    def get_uninstall_apps(self):
        return []

    def get_start_apps(self):
        return []


def system_with(state_dir, *executables: str, **kwargs):
    """A launcher-built system whose machine has `executables` installed."""
    from master_agent.desktop.plugin import DesktopPlugin
    from master_agent.executor.executor import LocalExecutor
    from master_agent.permissions.permission_system import PermissionSystem
    from master_agent.plugins.filesystem_plugin import FilesystemPlugin

    executor = LocalExecutor(PermissionSystem())
    kwargs.setdefault(
        "plugins",
        [
            FilesystemPlugin(executor),
            DesktopPlugin(executor, probe=InstalledProbe(*executables)),
        ],
    )
    return quiet_system(state_dir, **kwargs)


def scan(system) -> None:
    """Run the machine scan through the Desktop Executive's own published
    read, exactly as the launcher's scan objective does."""
    desktop = next(
        p for p in system.registry.all_plugins() if p.manifest.name == "desktop"
    )
    desktop.inventory(refresh=True)


def test_the_launcher_builds_a_broker(tmp_path):
    system = quiet_system(tmp_path / "state")

    assert system.broker is not None
    assert system.intelligence is not None


def test_the_launcher_builds_one_model_router_with_the_broker_behind_it(tmp_path):
    """One router, wired once. Otherwise every caller builds its own and
    chooses whether to attach a Broker -- which is how the hardcoded
    ladder came back in a different file."""
    system = quiet_system(tmp_path / "state")

    assert isinstance(system.model_router, ModelRouter)
    assert system.model_router.has_broker is True
    assert system.model_router.selector is system.intelligence


def test_the_broker_uses_the_configured_policy(tmp_path):
    config = MasterAgentConfig(broker=BrokerConfig(policy="prefer_local"))
    system = quiet_system(tmp_path / "state", config=config)

    assert system.broker.policy is PREFER_LOCAL
    assert system.intelligence.policy_version == "prefer_local/1"


def test_the_broker_reads_the_estate_from_the_desktop_executive(tmp_path):
    """Deliverable 3: the *same* machine scan the Dashboard reads, not a
    second source of truth about what is installed.

    Asserted by making the Desktop Executive's cache the only thing that
    changes and watching the Broker's estate change with it -- rather than
    by triggering a real scan, which shells out once per known application
    and would put a multi-second probe of the developer's machine in the
    middle of the unit suite.
    """
    system = system_with(tmp_path / "state", "ollama")
    desktop = next(
        p for p in system.registry.all_plugins() if p.manifest.name == "desktop"
    )

    assert desktop.cached_inventory is None
    assert system.intelligence.providers.has_scan() is False

    scan(system)

    assert system.intelligence.providers.has_scan() is True
    assert [p.provider_id for p in system.intelligence.providers.available()] == [
        "ollama.local"
    ]


def test_no_provider_is_available_before_the_machine_has_been_scanned(tmp_path):
    system = quiet_system(tmp_path / "state")

    available, total = system.intelligence.providers.counts()

    assert available == 0
    assert total > 0


def test_cloud_providers_stay_off_until_the_founder_enables_them(tmp_path):
    """No credential, no availability. Absence of a key is a fact."""
    system = quiet_system(tmp_path / "state")

    enabled = system.intelligence.providers.enabled_cloud_providers

    assert enabled == frozenset()


def test_configuration_can_enable_a_cloud_provider(tmp_path):
    config = MasterAgentConfig(
        broker=BrokerConfig(enabled_cloud_providers=("openrouter.api",))
    )
    system = quiet_system(tmp_path / "state", config=config)

    profiles = {p.provider_id: p for p in system.intelligence.profiles()}

    assert profiles["openrouter.api"].available is True
    assert profiles["openai.api"].available is False


def test_the_strong_reasoning_floor_comes_from_configuration(tmp_path):
    config = MasterAgentConfig(
        broker=BrokerConfig(strong_reasoning_min_quality=0.99)
    )
    system = quiet_system(tmp_path / "state", config=config)

    task = system.intelligence.task_profile(
        _request(requires_strong_reasoning=True)
    )

    assert task.min_quality == 0.99


def test_the_boot_report_places_the_broker_before_the_dashboard(tmp_path):
    """Ordering is not cosmetic: the Dashboard is handed the Broker's
    report, so the Broker has to exist first."""
    system = quiet_system(tmp_path / "state")
    names = [step.name for step in system.report.steps]

    assert names.index("AI Capability Broker") < names.index("Founder Dashboard")


def test_the_boot_report_places_the_broker_after_the_executives(tmp_path):
    """And after Executives, because the estate it decides over is read
    from one of them."""
    system = quiet_system(tmp_path / "state")
    names = [step.name for step in system.report.steps]

    assert names.index("Executives") < names.index("AI Capability Broker")


def test_the_ledger_lives_in_the_state_directory(tmp_path):
    state = tmp_path / "state"
    system = quiet_system(state)

    system.intelligence.decide(_request(task_id="t1"))

    assert (state / LEDGER_FILENAME).exists()


def test_nothing_is_written_until_something_asks_for_ai(tmp_path):
    state = tmp_path / "state"
    quiet_system(state)

    assert not (state / LEDGER_FILENAME).exists()


def test_a_failed_broker_leaves_the_router_refusing(tmp_path):
    """Deliverable 10, end to end: fail closed means the founder gets a
    system that says why, never one that quietly picks something."""
    config = MasterAgentConfig(broker=BrokerConfig(policy="nonsense"))
    system = quiet_system(tmp_path / "state", config=config)

    from master_agent.plugins.model_router import BrokerUnavailable

    with pytest.raises(BrokerUnavailable):
        system.model_router.select(RoutingContext())


def test_a_failed_broker_does_not_stop_the_rest_of_the_boot(tmp_path):
    """The Runtime, the Dashboard and the approval boundary are not the
    Broker's dependents. A system that cannot choose an AI can still do
    filesystem work, and should say which half is broken."""
    config = MasterAgentConfig(broker=BrokerConfig(policy="nonsense"))
    system = quiet_system(tmp_path / "state", config=config)

    assert system.runtime is not None
    assert system.dashboard.render()
    assert system.report.step("Founder Dashboard").ok is True


def test_the_approval_gate_uses_the_systems_own_queue_and_ledger(tmp_path):
    """Not a second permission system (ADR-0019 unweakened): the same
    Mission Control queue and the same grant ledger the Runtime uses."""
    system = quiet_system(tmp_path / "state")
    gate = system.intelligence._approvals

    assert gate._mc is system.mission_control
    assert gate._permissions is system.permissions


# =========================================================================
# Decisions survive a restart, and replay against their own policy
# =========================================================================


def test_a_decision_survives_a_restart(tmp_path):
    state = tmp_path / "state"
    first = quiet_system(state)
    first.intelligence.decide(_request(task_id="before-restart"))
    first.stop()

    second = quiet_system(state)

    assert len(second.intelligence.ledger) == 1
    assert second.intelligence.ledger.for_task("before-restart") is not None


def test_the_boot_report_says_how_much_history_it_restored(tmp_path):
    state = tmp_path / "state"
    first = quiet_system(state)
    first.intelligence.decide(_request(task_id="t1"))
    first.stop()

    second = quiet_system(state)

    assert "1 past decision(s) restored" in second.report.step(
        "AI Capability Broker"
    ).detail


def test_a_restored_decision_replays_against_the_policy_that_made_it(tmp_path):
    """Deliverable 8's load-bearing case: the founder changed policy
    between the two launches, and history did not change with them."""
    state = tmp_path / "state"
    first = system_with(state, "ollama")
    scan(first)
    first.intelligence.decide(_request(task_id="t1"))
    chosen = first.intelligence.ledger.get(1).provider_id
    first.stop()

    second = quiet_system(
        state, config=MasterAgentConfig(broker=BrokerConfig(policy="best_quality"))
    )

    assert second.broker.policy is BEST_QUALITY
    assert second.intelligence.ledger.replay(1).winner == chosen
    assert second.intelligence.ledger.replay_matches(1) is True


def test_replaying_after_a_restart_does_not_append_to_the_ledger(tmp_path):
    state = tmp_path / "state"
    first = quiet_system(state)
    first.intelligence.decide(_request(task_id="t1"))
    first.stop()

    second = quiet_system(state)
    second.intelligence.ledger.replay_all()

    assert len(second.intelligence.ledger) == 1


def test_a_ledger_file_written_by_one_process_is_readable_by_a_bare_ledger(tmp_path):
    """No launcher required to read the evidence -- a founder with the
    file and a Python prompt can replay their own history."""
    state = tmp_path / "state"
    system = quiet_system(state)
    system.intelligence.decide(_request(task_id="t1"))

    standalone = DecisionLedger(store=JsonFileDecisionStore(state / LEDGER_FILENAME))

    assert standalone.load() == 1
    assert standalone.replay_matches(1) is True


# =========================================================================
# The Dashboard shows live Broker decisions (Deliverable 9)
# =========================================================================


def snapshot_with(report) -> DashboardSnapshot:
    sources = DashboardSources(
        broker_provider=(lambda: report), clock=lambda: datetime.now(UTC)
    )
    return sources.collect()


def sample_report(**kwargs) -> BrokerReport:

    harness = Harness("alpha_runtime")
    harness.decide(task_id="t1")
    return harness.service.report(**kwargs)


def test_with_no_broker_attached_the_panel_says_so():
    """An empty list would read as "it has never chosen anything", which
    is a different and much more alarming fact."""
    panel = snapshot_with(None) and DashboardSources().collect().broker

    assert panel.status.available is False
    assert "no AI Capability Broker attached" in panel.status.reason


def test_a_broker_read_that_raises_becomes_absent_data():
    def explode():
        raise RuntimeError("broker unreachable")

    panel = DashboardSources(broker_provider=explode).collect().broker

    assert panel.status.available is False
    assert "broker unreachable" in panel.status.reason


def test_a_broker_that_reports_nothing_is_absent_rather_than_empty():
    panel = DashboardSources(broker_provider=lambda: None).collect().broker

    assert panel.status.available is False


def test_the_panel_carries_the_policy_and_the_estate():
    panel = snapshot_with(sample_report()).broker

    assert panel.policy_version == "balanced/1"
    assert panel.providers_total == 5
    assert panel.providers_available == 1


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("task_id", "t1"),
        ("capability", "reasoning"),
        ("provider_id", "alpha-local"),
        ("cost_tier", "free"),
        ("quality_tier", "good"),
        ("policy_version", "balanced/1"),
        ("approval_state", NOT_REQUIRED),
        ("locality", "local"),
    ],
)
def test_a_decision_row_carries_what_the_founder_asked(field, expected):
    row = snapshot_with(sample_report()).broker.decisions[0]

    assert getattr(row, field) == expected


def test_a_decision_row_carries_the_brokers_reason_verbatim():
    row = snapshot_with(sample_report()).broker.decisions[0]

    assert "clears the floor" in row.reason


def test_a_decision_row_states_the_cost_and_the_quality_in_words():
    row = snapshot_with(sample_report()).broker.decisions[0]

    assert row.cost_detail == "free"
    assert row.quality_detail == "good (0.75, declared)"


def test_the_panel_shows_a_bounded_window_of_decisions():

    harness = Harness("alpha_runtime")
    for index in range(6):
        harness.decide(task_id=f"t{index}")

    sources = DashboardSources(broker_provider=lambda: harness.service.report(limit=6))
    panel = sources.collect().broker

    assert len(panel.decisions) == 3, "the founder page shows a window, not a log"
    assert panel.total_decisions == 6


def test_the_panel_never_mutates_what_it_reads():

    harness = Harness("alpha_runtime")
    harness.decide()
    sources = DashboardSources(broker_provider=lambda: harness.service.report())

    for _ in range(5):
        sources.collect()

    assert len(harness.ledger) == 1, "rendering caused a decision"


# ---- the view model ------------------------------------------------------


def founder_view_with(report):
    return build_founder_view(snapshot_with(report))


def test_the_founder_view_reports_the_broker_as_available():
    view = founder_view_with(sample_report())

    assert view.intelligence.available is True
    assert view.intelligence.policy == "balanced/1"


def test_the_founder_view_reports_an_absent_broker_with_a_reason():
    view = build_founder_view(DashboardSources().collect())

    assert view.intelligence.available is False
    assert view.intelligence.reason


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("provider", "alpha-local"),
        ("cost", "free"),
        ("quality", "good (0.75, declared)"),
        ("capability", "reasoning"),
        ("approval", "not required"),
        ("selected", True),
    ],
)
def test_the_founder_view_answers_the_four_questions(field, expected):
    """Deliverable 9: which provider, why, cost tier, quality tier."""
    decision = founder_view_with(sample_report()).intelligence.decisions[0]

    assert getattr(decision, field) == expected


def test_a_refusal_is_marked_as_one_in_the_view():
    """The first live run rendered a refusal with a tick beside it and
    "Approval  not required" underneath, which reads as "we chose nothing
    and that was fine"."""

    harness = Harness(scanned=False)
    harness.decide(task_id="t1")

    decision = founder_view_with(harness.service.report()).intelligence.decisions[0]

    assert decision.selected is False
    assert decision.provider == "no provider available"


def test_the_view_serialises_for_a_web_front_end():
    """MB029 Deliverable 10 -- a front-end consumes the view model and
    writes its own renderer. A panel it cannot serialise is a panel only
    the terminal can show."""
    payload = founder_as_dict(founder_view_with(sample_report()))

    assert payload["intelligence"]["policy"] == "balanced/1"
    assert payload["intelligence"]["decisions"][0]["provider"] == "alpha-local"
    assert payload["intelligence"]["decisions"][0]["cost"] == "free"


# ---- the rendered panel --------------------------------------------------


def test_the_panel_names_the_provider_and_why():
    lines = render_intelligence(founder_view_with(sample_report()), ASCII)
    text = "\n".join(lines)

    assert "alpha-local" in text
    assert "Why" in text
    assert "clears the floor" in text


def test_the_panel_states_the_cost_and_quality_tiers():
    text = "\n".join(render_intelligence(founder_view_with(sample_report()), ASCII))

    assert "Cost      free" in text
    assert "good (0.75, declared)" in text


def test_the_panel_wraps_a_long_reason_rather_than_truncating_it():
    """A live run cut the Broker's reason off at "quality 0.72 clears the
    qual", losing the number the whole panel exists to show."""
    text = "\n".join(render_intelligence(founder_view_with(sample_report()), ASCII))

    assert "0.75 clears the floor 0.60" in text


def test_no_rendered_line_runs_past_the_frame():
    lines = render_intelligence(founder_view_with(sample_report()), ASCII)

    assert all(len(line) <= 74 for line in lines), [
        line for line in lines if len(line) > 74
    ]


def test_the_panel_is_visible_even_with_nothing_to_show():
    """A panel that disappears when empty trains a founder to stop looking
    for it -- the same rule the Decisions panel follows."""

    text = "\n".join(
        render_intelligence(founder_view_with(Harness().service.report()), ASCII)
    )

    assert "AI DECISIONS" in text
    assert "nothing has asked for AI yet" in text


def test_the_panel_says_when_no_machine_scan_has_run():

    view = founder_view_with(Harness(scanned=False).service.report())
    text = "\n".join(render_intelligence(view, ASCII))

    assert "no machine scan yet" in text


def test_the_panel_says_when_the_broker_is_not_attached():
    view = build_founder_view(DashboardSources().collect())
    text = "\n".join(render_intelligence(view, ASCII))

    assert "AI DECISIONS" in text
    assert "no AI Capability Broker attached" in text


def test_a_decision_waiting_on_the_founder_is_not_drawn_as_a_finished_one():
    """It was chosen, so it is not a refusal -- but it has not run, and a
    founder skimming glyphs must not read it as done."""
    harness = Harness(enabled=("delta-cloud", "epsilon-cloud"))
    harness.decide(task_id="paid")

    view = founder_view_with(harness.service.report())
    decision = view.intelligence.decisions[0]
    line = render_intelligence(view, ASCII)[2]

    assert decision.selected is True
    assert decision.waiting is True
    assert line.strip().startswith(ASCII.pending)


def test_a_decision_that_needed_no_approval_is_drawn_as_finished():
    view = founder_view_with(sample_report())
    decision = view.intelligence.decisions[0]

    assert decision.waiting is False
    assert render_intelligence(view, ASCII)[1].strip().startswith(ASCII.ok)


def test_the_panel_flags_work_waiting_on_the_founder():

    harness = Harness(enabled=("delta-cloud", "epsilon-cloud"))
    harness.decide(task_id="paid")

    text = "\n".join(render_intelligence(founder_view_with(harness.service.report()), ASCII))

    assert "1 waiting on your approval" in text


def test_the_panel_surfaces_a_recording_problem():

    class Broken:
        def read(self):
            return []

        def write(self, _rows):
            raise OSError("disk full")

    harness = Harness("alpha_runtime", store=Broken())
    harness.decide()

    text = "\n".join(render_intelligence(founder_view_with(harness.service.report()), ASCII))

    assert "recording problem" in text


@pytest.mark.parametrize("charset", [ASCII, UNICODE], ids=["ascii", "unicode"])
def test_the_panel_encodes_on_both_terminals(charset):
    """MB026's lesson: a cp1252 Windows console cannot encode the
    punctuation this project writes everywhere else."""
    text = "\n".join(render_intelligence(founder_view_with(sample_report()), charset))

    if charset is ASCII:
        text.encode("cp1252")
    text.encode("utf-8")


def test_the_founder_frame_includes_the_panel():
    frame = render_founder_frame(founder_view_with(sample_report()), ASCII)

    assert "AI DECISIONS" in frame


def test_the_panel_sits_with_the_machine_rather_than_above_the_mission():
    """Which provider was chosen is a question about what the system
    *has*. A founder only asks it once they know nothing is wrong."""
    frame = render_founder_frame(founder_view_with(sample_report()), ASCII)

    assert frame.index("STATUS") < frame.index("AI DECISIONS")
    assert frame.index("MACHINE READINESS") < frame.index("AI DECISIONS")
    assert frame.index("AI DECISIONS") < frame.index("RECOMMENDATIONS")


def test_a_broker_that_is_absent_never_changes_the_headline_status():
    """A build with no Broker is not "needs attention": nothing is broken
    and nothing is waiting on the founder. Saying otherwise would train
    them to ignore the status line."""
    view = build_founder_view(DashboardSources().collect())

    assert view.status_reason == "" or "Broker" not in view.status_reason


def test_the_launcher_dashboard_shows_the_brokers_decisions(tmp_path):
    """End to end: the launcher's own Dashboard, reading the launcher's
    own Broker."""
    system = quiet_system(tmp_path / "state")
    system.intelligence.decide(_request(task_id="t1"))

    frame = system.dashboard.render()

    assert "AI DECISIONS" in frame
    assert "policy balanced/1" in frame


def test_the_technical_page_is_unchanged_by_all_of_this(tmp_path):
    """MB026's nine engineering panels are not this brief's business."""
    system = quiet_system(tmp_path / "state")
    system.dashboard.show(TECHNICAL_PAGE)

    frame = system.dashboard.render()

    assert "RUNTIME" in frame
    assert "AI DECISIONS" not in frame
    assert system.dashboard.show(FOUNDER_PAGE) == FOUNDER_PAGE


# =========================================================================
# Definition of Done — Task -> Broker -> DecisionRecord -> Approval -> Execution
# =========================================================================


def _request(**kwargs):
    from master_agent.plugins.model_router import SelectionRequest

    return SelectionRequest(**kwargs)


def test_the_whole_flow_runs_for_a_free_provider(tmp_path):
    """Free, local, unrestricted: decided, recorded, and executable with
    nobody interrupted (Deliverable 6)."""
    from master_agent.plugins.registry import PluginRegistry

    harness = Harness("alpha_runtime")
    provider = RecordingProvider("alpha-local", reply="the answer")
    registry = PluginRegistry()
    registry.register(provider)
    router = ModelRouter(registry, selector=harness.service)

    answer = router.generate("summarise", RoutingContext(task_id="t1"))

    assert answer == "the answer"
    assert harness.ledger.for_task("t1").approval_state == NOT_REQUIRED
    assert harness.mission_control.approvals.open() == []


def test_a_paid_provider_is_not_executed_before_the_founder_answers(tmp_path):
    """Deliverable 5, and the property that makes it worth having: the
    provider proves it was not called."""
    from master_agent.plugins.registry import PluginRegistry

    harness = Harness(enabled=("delta-cloud", "epsilon-cloud"))
    provider = RecordingProvider("delta-cloud")
    registry = PluginRegistry()
    registry.register(provider)
    router = ModelRouter(registry, selector=harness.service)

    with pytest.raises(ProviderApprovalPending):
        router.generate("summarise", RoutingContext(task_id="t1"))

    assert provider.calls == []
    assert harness.ledger.for_task("t1").approval_state == PENDING


def test_the_same_task_runs_once_the_founder_approves(tmp_path):
    from master_agent.plugins.registry import PluginRegistry

    harness = Harness(enabled=("delta-cloud", "epsilon-cloud"))
    provider = RecordingProvider("delta-cloud", reply="paid answer")
    registry = PluginRegistry()
    registry.register(provider)
    router = ModelRouter(registry, selector=harness.service)

    with pytest.raises(ProviderApprovalPending):
        router.generate("summarise", RoutingContext(task_id="t1"))
    harness.approve_everything()
    answer = router.generate("summarise", RoutingContext(task_id="t1"))

    assert answer == "paid answer"
    assert provider.calls == [("summarise", None)]
    assert harness.ledger.for_task("t1").approval_state == GRANTED


def test_a_rejected_provider_never_runs(tmp_path):
    from master_agent.plugins.registry import PluginRegistry

    harness = Harness(enabled=("delta-cloud", "epsilon-cloud"))
    provider = RecordingProvider("delta-cloud")
    registry = PluginRegistry()
    registry.register(provider)
    router = ModelRouter(registry, selector=harness.service)

    with pytest.raises(ProviderApprovalPending):
        router.generate("summarise", RoutingContext(task_id="t1"))
    harness.reject_everything()

    with pytest.raises(ProviderApprovalDenied):
        router.generate("summarise", RoutingContext(task_id="t1"))
    assert provider.calls == []


def test_a_refusal_never_reaches_a_provider(tmp_path):
    from master_agent.plugins.registry import PluginRegistry

    harness = Harness(scanned=False)
    provider = RecordingProvider("alpha-local")
    registry = PluginRegistry()
    registry.register(provider)
    router = ModelRouter(registry, selector=harness.service)

    with pytest.raises(NoProviderAvailable):
        router.generate("summarise", RoutingContext(task_id="t1"))

    assert provider.calls == []


def test_every_step_of_the_flow_leaves_a_record(tmp_path):
    """Three attempts at one task -- refused, pending, granted -- and a
    replayable record of each."""

    harness = Harness(enabled=("delta-cloud", "epsilon-cloud"))
    harness.decide(task_id="t1")
    harness.approve_everything()
    harness.decide(task_id="t1")

    assert len(harness.ledger.all_for_task("t1")) == 2
    assert set(harness.ledger.replay_all().values()) == {True}


def test_the_founder_answers_in_the_console_they_already_use(tmp_path):
    """Zero new approval paths (ADR-0018 Decision 3): `approve 1` in the
    existing Founder Console decides a provider question exactly as it
    decides a filesystem one."""
    from master_agent.launcher.console import FounderConsole

    harness = Harness(enabled=("delta-cloud", "epsilon-cloud"))
    harness.decide(task_id="t1")
    console = FounderConsole(
        dashboard=None, mission_control=harness.mission_control, writer=lambda _t: None
    )

    message = console.execute("approve 1")

    assert "approved" in message.lower() or "approved" in message
    assert harness.decide(task_id="t1").ok is True


def test_kalpavriksha_no_longer_names_a_provider_to_route(tmp_path):
    """The Definition of Done, stated as a property of the running system:
    the only place a provider name enters is a DecisionRecord."""
    system = system_with(tmp_path / "state", "ollama")
    scan(system)

    outcome = system.intelligence.decide(_request(task_id="t1"))

    assert outcome.ok is True
    assert outcome.selection.provider_id in {
        spec.provider_id
        for spec in __import__(
            "master_agent.ai_infrastructure.catalog", fromlist=["PROVIDER_CATALOG"]
        ).PROVIDER_CATALOG
    }
    assert system.intelligence.ledger.for_task("t1").record is not None
