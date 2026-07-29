"""Integration tests — the acceptance criteria of Mission Brief 023.

The central claim under test: Mission Control can register Executives,
register Capabilities, dispatch Tasks, receive Events, maintain the Audit
Stream, maintain the Self-Development Queue, and expose Founder State
**without requiring modifications to existing Executives**.

That last clause is why these tests use the real, untouched
`FilesystemPlugin` (Mission Brief 005) and `BrowserPlugin` (Mission Brief
022) rather than fakes: a fake would prove the adapter works against a
fixture shaped for it, which is not the claim being made.
"""
from __future__ import annotations

from master_agent.executor.executor import LocalExecutor
from master_agent.mission_control.adapters import (
    describe_plugin_capabilities,
    register_plugin_as_executive,
)
from master_agent.mission_control.events import EventType
from master_agent.mission_control.executives import ExecutiveHealth
from master_agent.mission_control.lifecycle import WorkerState
from master_agent.mission_control.mission_control import MissionControl
from master_agent.mission_control.self_development import SelfDevelopmentType
from master_agent.mission_control.tasks import Objective, Task
from master_agent.permissions.permission_system import PermissionSystem
from master_agent.plugins.filesystem_plugin import FilesystemPlugin


def make_filesystem_plugin() -> FilesystemPlugin:
    return FilesystemPlugin(LocalExecutor(PermissionSystem()), locations={})


# ---- registration without modifying existing Executives ----------------


def test_the_real_unmodified_filesystem_plugin_registers_as_an_executive():
    mc = MissionControl()
    executive_id = register_plugin_as_executive(mc, make_filesystem_plugin())

    assert executive_id == "filesystem"
    record = mc.executives.get("filesystem")
    assert record.state is WorkerState.READY
    assert record.health is ExecutiveHealth.HEALTHY
    # Mission Brief 005 shipped fourteen filesystem capabilities.
    assert len(record.capabilities) == 14


def test_registration_derives_qualified_names_from_the_plugins_own_manifest():
    mc = MissionControl()
    register_plugin_as_executive(mc, make_filesystem_plugin())
    names = mc.capabilities.names()
    assert "Filesystem.CreateFolder" in names
    assert "Filesystem.ReadFile" in names
    assert "Filesystem.DeleteFolder" in names


def test_registration_carries_risk_tier_and_category_through_without_regating():
    """Mission Control *describes* risk; it never gates on it -- the
    Permission System remains the only thing that does."""
    mc = MissionControl()
    register_plugin_as_executive(mc, make_filesystem_plugin())
    delete = mc.capabilities.get("Filesystem.DeleteFolder")
    assert delete.risk_tier == "irreversible"
    assert delete.permission_category == "delete"


def test_the_real_unmodified_browser_plugin_registers_the_same_way():
    """Proves the adapter is not shaped around one plugin: a second,
    unrelated capability family registers with no Mission Control change."""
    from master_agent.environment.browser_session import BrowserSessionManager
    from master_agent.plugins.browser_plugin import BrowserPlugin

    mc = MissionControl()
    executor = LocalExecutor(PermissionSystem())
    plugin = BrowserPlugin(executor, BrowserSessionManager())
    register_plugin_as_executive(mc, plugin)

    record = mc.executives.get("browser")
    assert len(record.capabilities) == 9
    assert "Browser.Navigate" in mc.capabilities.names()
    assert "Browser.ObserveBrowser" in mc.capabilities.names()


def test_two_executives_coexist_without_capability_collisions():
    from master_agent.environment.browser_session import BrowserSessionManager
    from master_agent.plugins.browser_plugin import BrowserPlugin

    mc = MissionControl()
    executor = LocalExecutor(PermissionSystem())
    register_plugin_as_executive(mc, FilesystemPlugin(executor, locations={}))
    register_plugin_as_executive(mc, BrowserPlugin(executor, BrowserSessionManager()))

    assert len(mc.executives) == 2
    assert len(mc.capabilities) == 23  # 14 filesystem + 9 browser


def test_describe_plugin_capabilities_reads_only_the_public_plugin_contract():
    """The adapter must work for plugins that do not exist yet, which
    requires depending on nothing but `Plugin.manifest`."""
    descriptors = describe_plugin_capabilities(make_filesystem_plugin())
    assert len(descriptors) == 14
    assert all(d.executive_id == "filesystem" for d in descriptors)


# ---- the seven acceptance criteria, end to end -------------------------


def test_all_seven_acceptance_criteria_in_one_flow():
    mc = MissionControl()

    # 1. Register Executives.  2. Register Capabilities.
    register_plugin_as_executive(mc, make_filesystem_plugin())
    assert len(mc.executives) == 1
    assert len(mc.capabilities) == 14

    # 3. Dispatch Tasks.
    objective = mc.submit_objective(
        Objective(
            description="Set up a workspace",
            tasks=[
                Task(capability="Filesystem.CreateFolder", payload={"name": "Demo"}, task_id="t1"),
                Task(
                    capability="Filesystem.WriteFile",
                    payload={"path": "Demo/README.md"},
                    task_id="t2",
                    depends_on=["t1"],
                ),
            ],
        )
    )
    dispatched = mc.dispatch_ready()
    assert [task.task_id for task in dispatched] == ["t1"]

    # 4. Receive Events -- an Executive reports through the one schema.
    reporter = mc.reporter_for("filesystem")
    mc.task_started("t1")
    reporter.report(
        EventType.VERIFICATION_STARTED, task_id="t1", capability="Filesystem.CreateFolder"
    )
    mc.verification_completed("t1", verdict="matched", evidence_id="ev-1")
    mc.task_completed("t1", evidence_id="ev-1")

    # 5. Maintain Audit Stream.
    assert len(mc.audit) > 0
    assert mc.audit.of_type(EventType.VERIFICATION_COMPLETED)

    # 6. Maintain Self-Development Queue.
    mc.propose_self_development(
        SelfDevelopmentType.PENDING_CAPABILITY, "Desktop.WindowDetect"
    )
    assert len(mc.self_development.pending()) == 1

    # 7. Expose Founder State.
    state = mc.founder_state()
    assert state.current_objective == "Set up a workspace"
    assert state.current_objective_id == objective.objective_id
    assert state.progress == 0.5
    assert state.evidence == ["ev-1"]
    assert state.learning_progress["self_development_open"] == 1


def test_founder_state_exposes_exactly_the_ten_brief_named_fields():
    mc = MissionControl()
    data = mc.founder_state().as_dict()
    for required in (
        "current_objective",
        "current_mission",
        "current_executive",
        "current_capability",
        "progress",
        "evidence",
        "errors",
        "eta_seconds",
        "waiting_approval",
        "learning_progress",
    ):
        assert required in data, f"missing brief-required founder field: {required}"


def test_founder_state_is_well_formed_before_anything_has_happened():
    """A consumer must never have to special-case "no objective yet"."""
    state = MissionControl().founder_state()
    assert state.current_objective is None
    assert state.progress == 0.0
    assert state.eta_seconds is None
    assert state.errors == []


def test_founder_state_surfaces_a_failure_rather_than_absorbing_it():
    mc = MissionControl()
    register_plugin_as_executive(mc, make_filesystem_plugin())
    mc.submit_objective(
        Objective(
            description="will fail",
            tasks=[Task(capability="Filesystem.CreateFolder", task_id="t1")],
        )
    )
    mc.dispatch_ready()
    mc.task_started("t1")
    mc.task_failed("t1", "disk on fire")

    state = mc.founder_state()
    assert "disk on fire" in state.errors


def test_founder_state_surfaces_knowledge_waiting_on_a_human():
    mc = MissionControl()
    request = mc.request_knowledge("how to detect a window")
    for _ in range(4):
        mc.advance_knowledge(request.request_id)

    waiting = mc.founder_state().waiting_approval
    assert len(waiting) == 1
    assert waiting[0]["kind"] == "knowledge_promotion"


def test_eta_is_absent_until_there_is_a_basis_for_one():
    mc = MissionControl()
    register_plugin_as_executive(mc, make_filesystem_plugin())
    mc.submit_objective(
        Objective(
            description="two",
            tasks=[
                Task(capability="Filesystem.CreateFolder", task_id="t1"),
                Task(capability="Filesystem.WriteFile", task_id="t2"),
            ],
        )
    )
    assert mc.founder_state().eta_seconds is None

    mc.dispatch_ready()
    mc.task_started("t1")
    mc.task_completed("t1")
    assert mc.founder_state().eta_seconds is not None


# ---- future Executives plug in without architectural changes -----------


def test_an_executive_that_is_not_a_plugin_registers_through_the_primitive():
    """A future out-of-process or remote Executive has no Plugin object --
    the adapter is a convenience over register_executive(), never the only
    door (MISSION_CONTROL_ARCHITECTURE.md §9)."""
    from master_agent.mission_control.capabilities import CapabilityDescriptor, qualified_name

    mc = MissionControl()
    mc.register_executive(
        executive_id="desktop",
        version="0.1.0",
        capabilities=[
            CapabilityDescriptor(
                qualified_name=qualified_name("desktop", "window_detect"),
                executive_id="desktop",
                capability="window_detect",
            )
        ],
        dependencies=["filesystem"],
        health=ExecutiveHealth.HEALTHY,
    )
    mc.mark_executive_ready("desktop")

    assert "Desktop.WindowDetect" in mc.capabilities.names()
    assert mc.executives.get("desktop").dependencies == ["filesystem"]

    mc.submit_objective(
        Objective(
            description="detect",
            tasks=[Task(capability="Desktop.WindowDetect", task_id="t1")],
        )
    )
    assert [t.task_id for t in mc.dispatch_ready()] == ["t1"]


def test_registering_a_new_executive_requires_no_mission_control_change():
    """The 'every future Executive can plug in without architectural
    changes' criterion, stated as a property: registering N executives
    touches only data, never Mission Control's own code paths."""
    mc = MissionControl()
    from master_agent.mission_control.capabilities import CapabilityDescriptor, qualified_name

    for name in ("git", "research", "knowledge", "mobile", "robot"):
        mc.register_executive(
            executive_id=name,
            version="0.1.0",
            capabilities=[
                CapabilityDescriptor(
                    qualified_name=qualified_name(name, "do_thing"),
                    executive_id=name,
                    capability="do_thing",
                )
            ],
        )
        mc.mark_executive_ready(name)

    assert len(mc.executives) == 5
    assert len(mc.capabilities) == 5
