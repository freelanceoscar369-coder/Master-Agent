"""Architecture compliance for MB025's four rules, enforced mechanically.

    Rule 1: Persistence is a service. It never executes missions.
    Rule 2: Mission Control requests persistence; never writes files.
    Rule 3: Runtime requests checkpoints; never performs storage.
    Rule 4: Contracts only -- no reaching into private state.

Same posture as the MB023 and MB024 architecture tests: prose drifts, a
failing test does not.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from master_agent.persistence.recovery import recover
from master_agent.persistence.service import PersistenceService
from master_agent.persistence.store import JsonFileStateStore
from master_agent.runtime.checkpoint import CheckpointSink

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src" / "master_agent"
PERSISTENCE_DIR = SRC / "persistence"
PERSISTENCE_MODULES = sorted(PERSISTENCE_DIR.glob("*.py"))
MISSION_CONTROL_MODULES = sorted((SRC / "mission_control").glob("*.py"))
RUNTIME_MODULES = sorted((SRC / "runtime").glob("*.py"))

# Filesystem and storage APIs Mission Control must never reach for.
# MB025's constraint: "Mission Control cannot access filesystem APIs."
STORAGE_IMPORTS = {"json", "pathlib", "sqlite3", "os", "io", "shutil", "tempfile", "pickle"}


def imported_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


# ---- Rule 2: Mission Control cannot access filesystem APIs --------------


@pytest.mark.parametrize("path", MISSION_CONTROL_MODULES, ids=lambda p: p.name)
def test_mission_control_never_imports_storage_or_filesystem_apis(path: Path):
    offenders = imported_names(path) & STORAGE_IMPORTS
    assert not offenders, (
        f"{path.name} imports {offenders}; MB025 requires Mission Control to have no "
        "filesystem access. Persistence reads it through public contracts instead."
    )


@pytest.mark.parametrize("path", MISSION_CONTROL_MODULES, ids=lambda p: p.name)
def test_mission_control_never_imports_the_persistence_package(path: Path):
    """It is persisted; it does not persist. The dependency points one
    way, which is what keeps Mission Control testable with no storage."""
    assert not any(
        name.startswith("master_agent.persistence") for name in imported_names(path)
    )


# ---- Rule 3: the Runtime performs no storage ----------------------------


@pytest.mark.parametrize("path", RUNTIME_MODULES, ids=lambda p: p.name)
def test_runtime_never_imports_storage_or_the_persistence_package(path: Path):
    """The CheckpointSink protocol lives inside runtime/ precisely so this
    stays true -- dependency inversion, not a storage dependency."""
    names = imported_names(path)
    assert not (names & STORAGE_IMPORTS), f"{path.name} reaches for storage APIs"
    assert not any(name.startswith("master_agent.persistence") for name in names)


def test_the_checkpoint_protocol_is_defined_inside_the_runtime_package():
    assert (REPO_ROOT / "src/master_agent/runtime/checkpoint.py").exists()
    assert CheckpointSink.__module__ == "master_agent.runtime.checkpoint"


def test_the_persistence_service_satisfies_the_runtime_owned_protocol():
    """Persistence conforms to the Runtime's contract, not the reverse."""
    from master_agent.persistence.store import InMemoryStateStore

    assert isinstance(PersistenceService(InMemoryStateStore()), CheckpointSink)


# ---- Rule 1: persistence never executes ---------------------------------


@pytest.mark.parametrize("path", PERSISTENCE_MODULES, ids=lambda p: p.name)
def test_persistence_never_imports_anything_that_executes_work(path: Path):
    forbidden = {
        "playwright",
        "subprocess",
        "socket",
        "requests",
        "httpx",
        "openai",
        "master_agent.executor.executor",
        "master_agent.plugins.browser_plugin",
        "master_agent.plugins.browser_worker",
        "master_agent.plugins.filesystem_plugin",
        "master_agent.environment.browser_session",
        "master_agent.runtime.engine",
        "master_agent.runtime.gateway",
    }
    names = imported_names(path)
    offenders = {
        name
        for name in names
        for bad in forbidden
        if name == bad or name.startswith(bad + ".")
    }
    assert not offenders, f"{path.name} imports {offenders}; persistence must never execute"


def test_the_persistence_service_exposes_no_dispatch_surface():
    """MB025: "Persistence Service cannot dispatch Executives."""
    public = {name for name in dir(PersistenceService) if not name.startswith("_")}
    for forbidden in ("dispatch", "invoke", "execute", "run", "run_once", "register_gateway"):
        assert forbidden not in public


def test_persistence_holds_no_gateway_or_executive_reference():
    from master_agent.persistence.store import InMemoryStateStore

    service = PersistenceService(InMemoryStateStore())
    for value in vars(service).values():
        assert not hasattr(value, "invoke"), "persistence must hold nothing invocable"


def test_only_the_store_module_touches_the_filesystem():
    """Every read/write is funnelled through one module, so "who can write
    to disk" has exactly one answer."""
    for path in PERSISTENCE_MODULES:
        if path.name == "store.py":
            continue
        names = imported_names(path)
        assert not (names & {"pathlib", "tempfile", "shutil", "io"}), (
            f"{path.name} reaches for filesystem APIs; only store.py may"
        )


def test_only_store_and_schema_use_json():
    """schema.py needs it for canonical serialisation and checksums;
    store.py needs it to read and write. Nothing else should."""
    for path in PERSISTENCE_MODULES:
        if path.name in {"store.py", "schema.py"}:
            continue
        assert "json" not in imported_names(path), f"{path.name} should not serialise directly"


# ---- Rule 4: contracts only ---------------------------------------------


@pytest.mark.parametrize("path", PERSISTENCE_MODULES, ids=lambda p: p.name)
def test_persistence_never_touches_a_private_attribute_of_another_component(path: Path):
    """Scans for `something._private` access on anything that is not
    `self`. Rule 4, mechanically."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        if not node.attr.startswith("_") or node.attr.startswith("__"):
            continue
        target = node.value
        if isinstance(target, ast.Name) and target.id == "self":
            continue
        if isinstance(target, ast.Attribute) and target.attr.startswith("_"):
            # self._store._something -- still our own object graph
            continue
        violations.append(f"{ast.unparse(target)}.{node.attr}")

    assert not violations, f"{path.name} reaches into private state: {violations}"


def test_restore_uses_only_public_mission_control_surfaces():
    """The additive contract (ADR-0015) exists so this can be true."""
    source = (PERSISTENCE_DIR / "service.py").read_text(encoding="utf-8")
    assert "_objectives" not in source
    assert "_current_objective_id" not in source
    assert "restore_objective" in source


def test_the_additive_restore_contract_is_public_and_documented():
    """If this method is ever removed, ADR-0015 must be revisited rather
    than the removal silently breaking recovery."""
    from master_agent.mission_control.dispatcher import TaskDispatcher
    from master_agent.mission_control.mission_control import MissionControl

    assert hasattr(TaskDispatcher, "restore_objective")
    assert hasattr(MissionControl, "restore_objective")
    assert "ADR-0015" in (MissionControl.restore_objective.__doc__ or "")


def test_recovery_takes_the_runtime_as_an_opaque_collaborator():
    """recover() must not require a concrete RuntimeEngine -- anything
    with restore_from() will do, which is what keeps persistence free of
    a runtime dependency."""
    import inspect

    signature = inspect.signature(recover)
    assert signature.parameters["runtime"].default is None


def test_the_state_store_contract_is_satisfiable_without_a_filesystem():
    """Proof the layers above storage assume nothing about disk."""
    from master_agent.persistence.store import InMemoryStateStore, StateStore

    assert isinstance(InMemoryStateStore(), StateStore)
    assert isinstance(JsonFileStateStore(REPO_ROOT / ".pytest_cache"), StateStore)
