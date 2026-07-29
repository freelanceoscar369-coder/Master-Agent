"""Architecture compliance tests — mechanically verifies Mission Brief
023's central architectural rule, so it cannot quietly stop being true:

    "Mission Control never performs work. It coordinates work."

Prose in a design doc drifts. A failing test does not. This is the same
posture tests/test_browser_constitution_compliance.py takes for Mission
Brief 022's product-independence claim.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from master_agent.mission_control.audit import AuditStream
from master_agent.mission_control.capabilities import CapabilityRegistry
from master_agent.mission_control.executives import ExecutiveRegistry
from master_agent.mission_control.mission_control import MissionControl

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = REPO_ROOT / "src" / "master_agent" / "mission_control"
MODULES = sorted(PACKAGE_DIR.glob("*.py"))

# Mission Control coordinates; it must never reach an Environment, a model,
# or the execution machinery itself. Importing any of these would mean it
# could perform work.
FORBIDDEN_IMPORTS = {
    "playwright",
    "subprocess",
    "shutil",
    "socket",
    "requests",
    "httpx",
    "openai",
    "master_agent.executor.executor",
    "master_agent.plugins.browser_worker",
    "master_agent.plugins.browser_plugin",
    "master_agent.plugins.filesystem_plugin",
    "master_agent.plugins.model_router",
    "master_agent.environment.browser_session",
}


def _imported_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_mission_control_never_imports_anything_that_performs_work(path: Path):
    imported = _imported_names(path)
    for forbidden in FORBIDDEN_IMPORTS:
        offenders = {name for name in imported if name == forbidden or name.startswith(forbidden + ".")}
        assert not offenders, (
            f"{path.name} imports {offenders}, which would let Mission Control perform work "
            "-- see MISSION_CONTROL_ARCHITECTURE.md §1"
        )


def test_the_adapter_is_the_only_module_touching_the_plugin_contract():
    """adapters.py reads a Plugin's manifest to derive descriptors, which
    is a read, not an invocation. No other Mission Control module should
    know the Plugin contract exists at all."""
    for path in MODULES:
        if path.name == "adapters.py":
            continue
        imported = _imported_names(path)
        assert "master_agent.plugins.base" not in imported, (
            f"{path.name} should not depend on the Plugin contract; only adapters.py does"
        )


def test_registries_hold_descriptions_never_live_objects():
    """A registry holding a live plugin reference would let Mission Control
    invoke it -- the descriptors deliberately carry only data."""
    from master_agent.mission_control.capabilities import CapabilityDescriptor
    from master_agent.mission_control.executives import ExecutiveRecord

    for field_name, annotation in CapabilityDescriptor.__annotations__.items():
        assert "Plugin" not in str(annotation), f"CapabilityDescriptor.{field_name} holds a plugin"
    for field_name, annotation in ExecutiveRecord.__annotations__.items():
        assert "Plugin" not in str(annotation), f"ExecutiveRecord.{field_name} holds a plugin"


def test_mission_control_exposes_no_execute_or_invoke_surface():
    """The facade must offer no way to run anything. If a future change
    adds `execute()` or `invoke()` here, that is the architectural rule
    breaking, and this test is what says so."""
    public = {name for name in dir(MissionControl) if not name.startswith("_")}
    for forbidden in ("execute", "invoke", "run", "perform", "call_capability"):
        assert forbidden not in public, (
            f"MissionControl.{forbidden}() would make it perform work, not coordinate it"
        )


def test_dispatcher_returns_tasks_rather_than_running_them():
    """dispatch_ready() hands out assignments; an outside caller performs
    the work and reports back."""
    from master_agent.mission_control.dispatcher import TaskDispatcher

    public = {name for name in dir(TaskDispatcher) if not name.startswith("_")}
    for forbidden in ("execute", "invoke", "run"):
        assert forbidden not in public


def test_supporting_components_expose_no_execution_surface():
    for component in (CapabilityRegistry, ExecutiveRegistry, AuditStream):
        public = {name for name in dir(component) if not name.startswith("_")}
        for forbidden in ("execute", "invoke", "run"):
            assert forbidden not in public, f"{component.__name__}.{forbidden}() must not exist"


def test_mission_control_does_not_define_a_second_evidence_type():
    """Evidence is Mission Brief 022's, reused unchanged. A competing
    definition here would fragment the Evidence Hierarchy (Constitution
    §9.2)."""
    for path in MODULES:
        source = path.read_text(encoding="utf-8")
        assert "class Evidence" not in source, (
            f"{path.name} defines its own Evidence type; reuse master_agent.verification.evidence"
        )
