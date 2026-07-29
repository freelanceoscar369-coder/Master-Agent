"""Capability Registry (#2) and Executive Registry (#3) tests.
See MISSION_CONTROL_ARCHITECTURE.md §4.
"""
from __future__ import annotations

import pytest

from master_agent.mission_control.capabilities import (
    CapabilityAlreadyRegistered,
    CapabilityDescriptor,
    CapabilityRegistry,
    UnknownCapability,
    qualified_name,
)
from master_agent.mission_control.executives import (
    ExecutiveAlreadyRegistered,
    ExecutiveHealth,
    ExecutiveRecord,
    ExecutiveRegistry,
    UnknownExecutive,
)
from master_agent.mission_control.lifecycle import WorkerState

# ---- qualified names ---------------------------------------------------


def test_qualified_name_builds_the_brief_style_dotted_name():
    assert qualified_name("browser", "navigate") == "Browser.Navigate"
    assert qualified_name("filesystem", "read_file") == "Filesystem.ReadFile"
    assert qualified_name("git", "commit") == "Git.Commit"


def test_qualified_name_is_deterministic_not_a_lookup_table():
    """A capability that does not exist yet still gets a correct name --
    that is the point of a rule over a table."""
    assert qualified_name("desktop", "window_detect") == "Desktop.WindowDetect"
    assert qualified_name("research", "extract") == "Research.Extract"
    assert qualified_name("knowledge", "store") == "Knowledge.Store"


def test_qualified_name_rejects_unusable_input():
    with pytest.raises(ValueError):
        qualified_name("", "navigate")
    with pytest.raises(ValueError):
        qualified_name("browser", "")


# ---- capability registry -----------------------------------------------


def descriptor(executive: str, capability: str) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        qualified_name=qualified_name(executive, capability),
        executive_id=executive,
        capability=capability,
    )


def test_register_and_look_up_a_capability():
    registry = CapabilityRegistry()
    registry.register(descriptor("browser", "navigate"))
    assert registry.has("Browser.Navigate")
    assert registry.get("Browser.Navigate").executive_id == "browser"
    assert len(registry) == 1


def test_duplicate_capability_registration_is_refused():
    registry = CapabilityRegistry()
    registry.register(descriptor("browser", "navigate"))
    with pytest.raises(CapabilityAlreadyRegistered):
        registry.register(descriptor("browser", "navigate"))


def test_unknown_capability_lookup_raises_a_named_error():
    with pytest.raises(UnknownCapability):
        CapabilityRegistry().get("Nope.Nothing")


def test_capabilities_can_be_listed_per_executive():
    registry = CapabilityRegistry()
    registry.register(descriptor("browser", "navigate"))
    registry.register(descriptor("browser", "click"))
    registry.register(descriptor("filesystem", "read_file"))
    assert len(registry.for_executive("browser")) == 2
    assert len(registry.for_executive("filesystem")) == 1


def test_removing_an_executive_reports_exactly_what_the_system_lost():
    registry = CapabilityRegistry()
    registry.register(descriptor("browser", "navigate"))
    registry.register(descriptor("browser", "click"))
    removed = registry.remove_executive("browser")
    assert sorted(removed) == ["Browser.Click", "Browser.Navigate"]
    assert len(registry) == 0


# ---- executive registry ------------------------------------------------


def make_record(executive_id: str = "browser") -> ExecutiveRecord:
    return ExecutiveRecord(
        executive_id=executive_id,
        version="0.1.0",
        capabilities=[qualified_name(executive_id, "navigate")],
        health=ExecutiveHealth.HEALTHY,
    )


def test_executive_exposes_all_seven_brief_required_fields():
    record = make_record()
    data = record.as_dict()
    for required in (
        "executive_id",
        "version",
        "capabilities",
        "health",
        "status",
        "dependencies",
        "current_task",
    ):
        assert required in data, f"missing brief-required field: {required}"


def test_duplicate_executive_registration_is_refused():
    registry = ExecutiveRegistry()
    registry.register(make_record())
    with pytest.raises(ExecutiveAlreadyRegistered):
        registry.register(make_record())


def test_unknown_executive_lookup_raises_a_named_error():
    with pytest.raises(UnknownExecutive):
        ExecutiveRegistry().get("nobody")


def test_executive_transitions_consult_the_lifecycle_table():
    from master_agent.mission_control.lifecycle import IllegalWorkerTransition

    registry = ExecutiveRegistry()
    registry.register(make_record())
    registry.transition("browser", WorkerState.INITIALIZED)
    registry.transition("browser", WorkerState.READY)
    assert registry.get("browser").state is WorkerState.READY

    with pytest.raises(IllegalWorkerTransition):
        registry.transition("browser", WorkerState.COMPLETED)


def test_only_healthy_idle_executives_are_available_for_new_work():
    registry = ExecutiveRegistry()
    registry.register(make_record())
    registry.transition("browser", WorkerState.INITIALIZED)
    registry.transition("browser", WorkerState.READY)
    assert registry.available_provider_of("Browser.Navigate") is not None

    registry.set_health("browser", ExecutiveHealth.DEGRADED)
    assert registry.available_provider_of("Browser.Navigate") is None, (
        "a degraded executive keeps its current work but must not be handed more"
    )


def test_a_running_executive_is_not_available_for_more_work():
    registry = ExecutiveRegistry()
    registry.register(make_record())
    registry.transition("browser", WorkerState.INITIALIZED)
    registry.transition("browser", WorkerState.READY)
    registry.transition("browser", WorkerState.RUNNING)
    assert registry.available_provider_of("Browser.Navigate") is None


def test_providers_of_finds_every_executive_offering_a_capability():
    registry = ExecutiveRegistry()
    registry.register(make_record("browser"))
    second = ExecutiveRecord(
        executive_id="browser_backup", version="0.1.0", capabilities=["Browser.Navigate"]
    )
    registry.register(second)
    assert len(registry.providers_of("Browser.Navigate")) == 2


def test_current_task_is_tracked_and_cleared():
    registry = ExecutiveRegistry()
    registry.register(make_record())
    registry.set_current_task("browser", "t1")
    assert registry.get("browser").current_task_id == "t1"
    registry.set_current_task("browser", None)
    assert registry.get("browser").current_task_id is None
