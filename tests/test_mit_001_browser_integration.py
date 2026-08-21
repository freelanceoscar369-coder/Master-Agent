"""MIT-001 — Mission Control Integration Test, Browser Executive.

The objective: **can Mission Control orchestrate the Browser Executive
without modifying the Browser Executive?**

Each of the seven MIT-001 tests has a section below. Nothing here imports
or touches a private member of the Browser Executive; everything goes
through Mission Control's public surface and the long-standing `Plugin`
contract. See docs/MIT_001_CERTIFICATION.md for the results and the two
places where the brief's expected output and the shipped architecture
differ on purpose.

Pages are generated locally via `set_content()` rather than fetched from
the network, for the same reason every Mission Brief 022 test does: the
certification must be deterministic and must not depend on the internet
being up. A real navigation against a live URL was run separately as
live verification -- transcript in the certification document.
"""
from __future__ import annotations

import pytest

from master_agent.environment.browser_session import BrowserSessionManager
from master_agent.executor.executor import LocalExecutor
from master_agent.mission_control.adapters import discover_executives
from master_agent.mission_control.events import EventType
from master_agent.mission_control.lifecycle import WorkerState
from master_agent.mission_control.mission_control import MissionControl
from master_agent.mission_control.tasks import Objective, Task
from master_agent.permissions.permission_system import GrantScope, PermissionSystem
from master_agent.plugins.browser_plugin import BrowserPlugin
from master_agent.plugins.browser_worker import BrowserWorker
from master_agent.plugins.registry import PluginRegistry
from master_agent.verification.evidence import ExpectedOutcome, ObservationCheck, Verdict

DEMO_PAGE = """
<html><head><title>Integration Demo</title></head>
<body>
  <h1 id="heading">Mission Control Demo</h1>
  <button id="go">Go</button>
  <input id="field" />
</body></html>
"""


class Harness:
    """Wires a real system exactly the way a founder would: plugins into
    the Plugin Registry, then Mission Control discovers whatever is there.

    Mission Control is given no knowledge of what a browser is. The only
    browser-specific thing this harness does is *construct* the plugin --
    which is installation, not orchestration.
    """

    def __init__(self) -> None:
        self.permissions = PermissionSystem()
        self.executor = LocalExecutor(self.permissions)
        self.sessions = BrowserSessionManager()

        self.registry = PluginRegistry()
        self.registry.register(BrowserPlugin(self.executor, self.sessions))

        self.mission_control = MissionControl()
        self.discovered = discover_executives(self.mission_control, self.registry)

        # The Worker-side runner. Mission Control never calls this; the
        # test acts as the outside caller that pulls ready tasks and
        # performs them, exactly as MISSION_CONTROL_ARCHITECTURE.md §1
        # describes.
        self.worker = BrowserWorker(self.executor, self.sessions)

    def approve(self, capability: str) -> None:
        """Stands in for a human approving a step of this mission."""
        self.permissions.grant(self.executor.name, capability, GrantScope.ONCE)

    def close(self) -> None:
        self.sessions.close_all()


@pytest.fixture
def harness():
    h = Harness()
    yield h
    h.close()


# =====================================================================
# Test 1 — Executive Discovery
# =====================================================================


def test_1_mission_control_automatically_discovers_the_browser_executive(harness):
    """Mission Control starts, and finds the Browser Executive without
    being told it exists."""
    assert "browser" in harness.discovered
    assert harness.mission_control.executives.has("browser")


def test_1_discovered_executive_is_registered_ready_with_its_capabilities(harness):
    record = harness.mission_control.executives.get("browser")
    assert record.state is WorkerState.READY
    assert record.version == "0.1.0"
    # Ten since `read_page_text` joined the Browser Executive; nine was
    # right at MB022. See MIT-001 Test 7 below, which is the guard that
    # actually cares whether that addition was sanctioned.
    assert len(record.capabilities) == 10


def test_1_discovery_names_no_specific_plugin_and_is_idempotent(harness):
    """Calling discovery again registers nothing new -- proving it reads
    the registry rather than replaying a hardcoded list."""
    again = discover_executives(harness.mission_control, harness.registry)
    assert again == []
    assert len(harness.mission_control.executives) == 1


def test_1_discovery_finds_whatever_is_installed_not_a_known_list(harness):
    """A second, unrelated Executive appearing in the registry is
    discovered by the same call, with no Mission Control change."""
    from master_agent.plugins.filesystem_plugin import FilesystemPlugin

    harness.registry.register(FilesystemPlugin(harness.executor, locations={}))
    newly = discover_executives(harness.mission_control, harness.registry)

    assert newly == ["filesystem"]
    assert len(harness.mission_control.executives) == 2


# =====================================================================
# Test 2 — Capability Registration
# =====================================================================


def test_2_capabilities_are_registered_automatically_from_the_manifest(harness):
    """No manual registration, no hardcoding: every capability name comes
    from the plugin's own manifest, transformed by one deterministic
    rule."""
    names = harness.mission_control.capabilities.names()
    assert "Browser.Navigate" in names
    assert "Browser.Click" in names
    assert "Browser.ObserveBrowser" in names
    assert "Browser.TypeText" in names  # MIT-001 calls this "Fill"
    assert len(names) == 10


def test_2_every_registered_capability_points_back_at_its_executive(harness):
    for name in harness.mission_control.capabilities.names():
        assert harness.mission_control.capabilities.get(name).executive_id == "browser"


def test_2_risk_metadata_survives_registration_without_being_regated(harness):
    """Mission Control describes risk; the Permission System remains the
    only thing that gates on it."""
    descriptor = harness.mission_control.capabilities.get("Browser.OpenBrowserSession")
    assert descriptor.risk_tier == "reversible_write"
    assert descriptor.permission_category == "system"


def test_2_there_is_no_browser_verify_capability_and_that_is_deliberate(harness):
    """MIT-001's expected list includes `Browser.Verify`. There is no such
    capability, on purpose: ADR-0011 makes Verification structurally
    independent of Execution -- a Verifier is never invoked through the
    Capability/`invoke()` path, because a component that can be dispatched
    as ordinary work is not an independent check. Verification appears in
    this system as its own subsystem and as VERIFICATION_* events (Test 4),
    not as a dispatchable capability. See docs/MIT_001_CERTIFICATION.md."""
    assert "Browser.Verify" not in harness.mission_control.capabilities.names()


# =====================================================================
# Test 3 — Task Dispatch
# =====================================================================


def test_3_a_navigation_objective_flows_founder_to_executive_and_back(harness):
    mc = harness.mission_control

    objective = mc.submit_objective(
        Objective(
            description="Open a browser session and navigate",
            tasks=[
                Task(
                    capability="Browser.OpenBrowserSession",
                    payload={"session_id": "mit"},
                    task_id="open",
                ),
                Task(
                    capability="Browser.Navigate",
                    payload={"session_id": "mit", "url": "about:blank"},
                    task_id="nav",
                    depends_on=["open"],
                ),
            ],
        )
    )

    # --- step 1: Mission Control assigns; it does not navigate ---
    assigned = mc.dispatch_ready()
    assert [t.task_id for t in assigned] == ["open"]
    assert assigned[0].assigned_executive == "browser"

    # --- the outside caller performs the work through the Executive ---
    harness.approve("open_browser_session")
    mc.task_started("open")
    report = harness.worker.run_step(
        "open_browser_session", {"session_id": "mit"}, requested_by="founder"
    )
    assert report.execution.success
    mc.task_completed("open", result=report.execution.output)

    # --- step 2 becomes ready only now ---
    assigned = mc.dispatch_ready()
    assert [t.task_id for t in assigned] == ["nav"]

    harness.approve("navigate")
    mc.task_started("nav")
    report = harness.worker.run_step(
        "navigate", {"session_id": "mit", "url": "about:blank"}, requested_by="founder"
    )
    assert report.execution.success
    mc.task_completed("nav", result=report.execution.output)

    assert mc.dispatcher.objective(objective.objective_id).is_complete


def test_3_mission_control_never_performs_the_navigation_itself(harness):
    """The architectural claim, asserted directly: Mission Control has no
    surface that could navigate, and no browser session of its own."""
    mc = harness.mission_control
    public = {name for name in dir(mc) if not name.startswith("_")}
    for forbidden in ("execute", "invoke", "run", "navigate", "perform"):
        assert forbidden not in public

    assert harness.sessions.list_sessions() == [], (
        "Mission Control must not have opened a browser session on its own"
    )


# =====================================================================
# Test 4 — Event Bus
# =====================================================================


def test_4_the_expected_event_sequence_is_emitted_in_order(harness):
    mc = harness.mission_control
    mc.submit_objective(
        Objective(
            description="navigate",
            tasks=[
                Task(
                    capability="Browser.OpenBrowserSession",
                    payload={"session_id": "mit"},
                    task_id="open",
                )
            ],
        )
    )
    mc.dispatch_ready()
    harness.approve("open_browser_session")
    mc.task_started("open")
    harness.worker.run_step("open_browser_session", {"session_id": "mit"}, requested_by="founder")

    mc.verification_started("open")
    mc.verification_completed("open", verdict="matched", evidence_id="ev-1")
    mc.task_completed("open", evidence_id="ev-1")

    emitted = [entry.event_type for entry in mc.audit.entries]
    expected_order = [
        EventType.TASK_CREATED,
        EventType.TASK_ASSIGNED,
        EventType.TASK_STARTED,
        EventType.VERIFICATION_STARTED,
        EventType.VERIFICATION_COMPLETED,
        EventType.TASK_COMPLETED,
    ]
    positions = [emitted.index(event) for event in expected_order]
    assert positions == sorted(positions), (
        f"events out of order: {[e.value for e in emitted]}"
    )


def test_4_every_mit_001_named_event_type_exists(harness):
    for name in (
        "TASK_CREATED",
        "TASK_ASSIGNED",
        "TASK_STARTED",
        "TASK_COMPLETED",
        "VERIFICATION_STARTED",
        "VERIFICATION_COMPLETED",
    ):
        assert hasattr(EventType, name), f"MIT-001 expects event type {name}"


# =====================================================================
# Test 5 — Audit Stream
# =====================================================================


def test_5_audit_contains_objective_timestamps_executive_capability_and_verdict(harness):
    mc = harness.mission_control
    objective = mc.submit_objective(
        Objective(
            description="Audit demo",
            tasks=[
                Task(
                    capability="Browser.OpenBrowserSession",
                    payload={"session_id": "mit"},
                    task_id="open",
                )
            ],
        )
    )
    mc.dispatch_ready()
    harness.approve("open_browser_session")
    mc.task_started("open")
    harness.worker.run_step("open_browser_session", {"session_id": "mit"}, requested_by="founder")
    mc.verification_completed("open", verdict="matched", evidence_id="ev-1")
    mc.task_completed("open", evidence_id="ev-1")

    entries = mc.audit.for_objective(objective.objective_id)
    assert entries

    # objective
    assert all(entry.objective_id == objective.objective_id for entry in entries)
    # timestamps
    assert all(entry.occurred_at is not None for entry in entries)
    # executive used
    assigned = mc.audit.of_type(EventType.TASK_ASSIGNED)[0]
    assert assigned.payload["executive_id"] == "browser"
    # capability used
    assert assigned.capability == "Browser.OpenBrowserSession"
    # verification result -- and the capability it verified, so an audit
    # entry answers "which capability" without a join back through task_id
    verification = mc.audit.of_type(EventType.VERIFICATION_COMPLETED)[0]
    assert verification.payload["verdict"] == "matched"
    assert verification.payload["evidence_id"] == "ev-1"
    assert verification.capability == "Browser.OpenBrowserSession"


def test_5_audit_history_is_immutable(harness):
    from dataclasses import FrozenInstanceError

    mc = harness.mission_control
    mc.submit_objective(
        Objective(description="x", tasks=[Task(capability="Browser.Navigate", task_id="t1")])
    )
    entry = mc.audit.entries[0]
    with pytest.raises(FrozenInstanceError):
        entry.source = "tampered"  # type: ignore[misc]


# =====================================================================
# Test 6 — Founder State
# =====================================================================


def test_6_founder_state_exposes_the_mit_001_shape_as_json(harness):
    mc = harness.mission_control
    mc.submit_objective(
        Objective(
            description="Founder state demo",
            tasks=[
                Task(
                    capability="Browser.OpenBrowserSession",
                    payload={"session_id": "mit"},
                    task_id="open",
                ),
                Task(
                    capability="Browser.Navigate",
                    payload={"session_id": "mit", "url": "about:blank"},
                    task_id="nav",
                    depends_on=["open"],
                ),
            ],
        )
    )
    mc.dispatch_ready()
    harness.approve("open_browser_session")
    mc.task_started("open")
    report = harness.worker.run_step(
        "open_browser_session", {"session_id": "mit"}, requested_by="founder"
    )
    mc.task_completed("open", result=report.execution.output, evidence_id="ev-1")

    state = mc.founder_state().as_dict()

    assert state["current_mission"] == "Founder state demo"
    assert state["current_executive"] is None or isinstance(state["current_executive"], str)
    assert state["current_capability"] == "Browser.Navigate"  # the next one up
    assert state["progress"] == 0.5
    assert state["result"] is not None
    assert state["evidence"] == ["ev-1"]

    import json

    json.dumps(state)  # "even if it's just JSON today"


def test_6_result_reflects_what_the_executive_returned_not_a_reinterpretation(harness):
    mc = harness.mission_control
    mc.submit_objective(
        Objective(
            description="result demo",
            tasks=[
                Task(
                    capability="Browser.OpenBrowserSession",
                    payload={"session_id": "mit"},
                    task_id="open",
                )
            ],
        )
    )
    mc.dispatch_ready()
    harness.approve("open_browser_session")
    mc.task_started("open")
    report = harness.worker.run_step(
        "open_browser_session", {"session_id": "mit"}, requested_by="founder"
    )
    mc.task_completed("open", result=report.execution.output)

    assert mc.founder_state().result == report.execution.output


# =====================================================================
# Test 7 — Zero Modification Principle
# =====================================================================


def test_7_the_full_loop_runs_with_verification_against_an_unmodified_executive(harness):
    """The whole point, end to end: discover, dispatch, execute, verify,
    audit -- with a Browser Executive that this test never modifies,
    subclasses, monkeypatches, or reaches into."""
    mc = harness.mission_control

    mc.submit_objective(
        Objective(
            description="Open, load a page, and verify what is on it",
            tasks=[
                Task(
                    capability="Browser.OpenBrowserSession",
                    payload={"session_id": "mit"},
                    task_id="open",
                ),
                Task(
                    capability="Browser.ObserveBrowser",
                    payload={"session_id": "mit", "selectors": ["#heading"]},
                    task_id="observe",
                    depends_on=["open"],
                ),
            ],
        )
    )

    mc.dispatch_ready()
    harness.approve("open_browser_session")
    mc.task_started("open")
    harness.worker.run_step("open_browser_session", {"session_id": "mit"}, requested_by="founder")
    mc.task_completed("open")

    harness.sessions.get("mit").page.set_content(DEMO_PAGE)

    mc.dispatch_ready()
    harness.approve("observe_browser")
    mc.task_started("observe")
    mc.verification_started("observe")

    report = harness.worker.run_step(
        "observe_browser",
        {"session_id": "mit", "selectors": ["#heading"]},
        requested_by="founder",
        expected_outcome=ExpectedOutcome(
            description="the page heading reads 'Mission Control Demo'",
            checks=[
                ObservationCheck(
                    field="elements.0.text", operator="equals", value="Mission Control Demo"
                )
            ],
        ),
        verify_selectors=["#heading"],
    )

    assert report.execution.success
    assert report.evidence.verdict is Verdict.MATCHED

    mc.verification_completed(
        "observe", verdict=report.evidence.verdict.value, evidence_id=report.evidence.evidence_id
    )
    mc.task_completed(
        "observe", result=report.execution.output, evidence_id=report.evidence.evidence_id
    )

    state = mc.founder_state()
    assert state.progress == 1.0
    assert report.evidence.evidence_id in state.evidence
    assert mc.audit.of_type(EventType.VERIFICATION_COMPLETED)


def test_7_mission_control_holds_no_reference_to_the_browser_executive(harness):
    """"Closed for modification" also means Mission Control never acquired
    a handle it could call. The registries hold descriptors only."""
    record = harness.mission_control.executives.get("browser")
    for value in vars(record).values():
        assert not isinstance(value, BrowserPlugin)

    descriptor = harness.mission_control.capabilities.get("Browser.Navigate")
    for value in vars(descriptor).values():
        assert not isinstance(value, BrowserPlugin)


def test_7_browser_executive_source_is_untouched_since_mission_brief_022():
    """Objective proof rather than assertion-by-inspection: every Browser
    Executive file is byte-identical to the MB022 tag."""
    import subprocess
    from pathlib import Path

    repo = Path(__file__).resolve().parent.parent
    browser_paths = [
        "src/master_agent/plugins/browser_plugin.py",
        "src/master_agent/plugins/browser_worker.py",
        "src/master_agent/plugins/browser_verifier.py",
        "src/master_agent/plugins/browser_observation.py",
        "src/master_agent/executor/actions/browser/",
        "src/master_agent/environment/",
    ]
    result = subprocess.run(
        ["git", "diff", "--stat", "v0.6.0-miracle-022", "HEAD", "--", *browser_paths],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:  # pragma: no cover - only when git/tag is unavailable
        pytest.skip(f"git unavailable or tag missing: {result.stderr.strip()}")

    assert result.stdout.strip() == "", (
        "the Browser Executive was modified since MB022, which breaks MIT-001 Test 7:\n"
        + result.stdout
    )
