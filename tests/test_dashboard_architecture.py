"""Architecture compliance for MB026's four rules, enforced mechanically.

    Rule 1: read-only -- never dispatches, executes, or mutates.
    Rule 2: published contracts only -- no private access, no filesystem.
    Rule 3: tolerate missing data; never fabricate.
    Rule 4: no business logic.

Same posture as MB023/024/025's architecture tests.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from master_agent.dashboard.app import FounderDashboard
from master_agent.dashboard.readmodel import DashboardSnapshot
from master_agent.dashboard.sources import DashboardSources

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE = REPO_ROOT / "src" / "master_agent" / "dashboard"
MODULES = sorted(PACKAGE.glob("*.py"))

FILESYSTEM_IMPORTS = {"pathlib", "os", "io", "json", "shutil", "tempfile", "sqlite3", "pickle"}

# Anything that performs work, or that would let the Dashboard cause it.
EXECUTION_IMPORTS = {
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
    "master_agent.persistence.recovery",
}


def imported_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


# ---- Rule 1: read-only --------------------------------------------------


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_the_dashboard_never_imports_anything_that_executes(path: Path):
    names = imported_names(path)
    offenders = {
        name
        for name in names
        for bad in EXECUTION_IMPORTS
        if name == bad or name.startswith(bad + ".")
    }
    assert not offenders, (
        f"{path.name} imports {offenders}; the Dashboard is read-only and must not be "
        "able to cause work. See FOUNDER_DASHBOARD_ARCHITECTURE.md §1"
    )


def test_the_dashboard_exposes_no_dispatch_or_mutation_surface():
    public = {name for name in dir(FounderDashboard) if not name.startswith("_")}
    for forbidden in (
        "dispatch",
        "dispatch_ready",
        "submit",
        "submit_objective",
        "invoke",
        "execute",
        "task_started",
        "task_completed",
        "task_failed",
        "recover",
        "save",
    ):
        assert forbidden not in public, f"FounderDashboard.{forbidden}() would break Rule 1"


def test_the_sources_layer_exposes_only_collection():
    public = {name for name in dir(DashboardSources) if not name.startswith("_")}
    assert public == {"collect"}


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_no_dashboard_module_calls_a_known_mutating_method(path: Path):
    """A textual guard against the obvious mistakes -- calling something
    that changes the system rather than reads it."""
    source = path.read_text(encoding="utf-8")
    for forbidden in (
        ".dispatch_ready(",
        ".submit_objective(",
        ".task_started(",
        ".task_completed(",
        ".task_failed(",
        ".run_once(",
        ".register_executive(",
        ".save_checkpoint(",
        ".restore_into(",
        ".recover(",
    ):
        # `self.`-prefixed calls are the Dashboard's own loop methods
        # (its own run_forever, its own render) -- those drive the view,
        # not the observed system. Only calls *onto another object* count.
        offending = [
            line
            for line in source.splitlines()
            if forbidden in line and f"self{forbidden}" not in line
        ]
        assert not offending, (
            f"{path.name} calls {forbidden} on another component -- Rule 1 violation:\n"
            + "\n".join(offending)
        )


def test_rendering_a_frame_changes_nothing_about_the_observed_system(tmp_path):
    """The strongest read-only statement available: render repeatedly and
    assert the system is byte-identical afterwards."""
    from master_agent.dashboard.app import build_dashboard
    from tests.dashboard_test_support import System

    work = tmp_path / "work"
    work.mkdir()
    system = System(tmp_path / "state", work)
    system.submit()
    system.run()

    before_states = [
        (task.task_id, task.state.value)
        for objective in system.mission_control.dispatcher.objectives()
        for task in objective.tasks
    ]
    before_audit = len(system.mission_control.audit)
    before_cycle = system.engine.health().active_cycle

    dashboard = build_dashboard(
        mission_control=system.mission_control,
        runtime=system.engine,
        persistence=system.service,
    )
    for _ in range(25):
        dashboard.render()

    after_states = [
        (task.task_id, task.state.value)
        for objective in system.mission_control.dispatcher.objectives()
        for task in objective.tasks
    ]
    assert after_states == before_states
    assert len(system.mission_control.audit) == before_audit
    assert system.engine.health().active_cycle == before_cycle


# ---- Rule 2: published contracts only -----------------------------------


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_the_dashboard_never_reads_the_filesystem(path: Path):
    """It asks persistence, which owns storage. It holds no path."""
    if path.name == "charset.py":
        pytest.skip("charset.py inspects sys.stdout's encoding, not the filesystem")
    offenders = imported_names(path) & FILESYSTEM_IMPORTS
    assert not offenders, f"{path.name} imports {offenders}; the Dashboard reads no files"


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_the_dashboard_never_touches_private_state_of_another_component(path: Path):
    """Rule 2, mechanically: no `something._private` on anything but self."""
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
            continue
        violations.append(f"{ast.unparse(target)}.{node.attr}")

    assert not violations, f"{path.name} reaches into private state: {violations}"


def test_the_dashboard_depends_on_narrow_protocols_not_concrete_engines():
    """Given a whole RuntimeEngine a careless panel could call run_once();
    given a one-method Protocol there is nothing to call but health()."""
    from master_agent.dashboard.sources import PersistenceReader, RuntimeReader

    assert set(dir(RuntimeReader)) & {"health"}
    assert {"load", "load_checkpoint", "store"} <= set(dir(PersistenceReader))


# ---- Rule 4: no business logic ------------------------------------------


def test_health_classification_is_isolated_to_one_module():
    """ADR-0016 Decision 3: quarantined so the boundary is visible."""
    for path in MODULES:
        if path.name in {"health.py", "sources.py"}:
            continue
        source = path.read_text(encoding="utf-8")
        assert "HealthLevel" not in source, (
            f"{path.name} classifies health; that belongs in health.py alone"
        )


def test_the_dashboard_defines_no_domain_types():
    """It renders Mission Control's and the Runtime's vocabulary; it must
    not invent a competing one."""
    for path in MODULES:
        source = path.read_text(encoding="utf-8")
        for forbidden in ("class Task", "class Objective", "class Evidence", "class Event"):
            assert forbidden not in source, f"{path.name} defines {forbidden}"


def test_the_read_model_is_frozen_so_a_panel_cannot_mutate_it():
    from dataclasses import FrozenInstanceError

    snapshot = DashboardSnapshot(captured_at=None)  # type: ignore[arg-type]
    with pytest.raises(FrozenInstanceError):
        snapshot.captured_at = "tampered"  # type: ignore[misc]


# Paths a *ratified* ADR permits to change, each with the ADR that
# permits it. This list is the amendment record: adding a row means an
# ADR was ratified, and a row without one is architectural drift.
#
# MB028.0 / ADR-0019 (ratified 2026-07-29) closed the Runtime approval
# boundary. It needed a new `runtime/approval.py`, a check at the
# Runtime's single funnel in `runtime/engine.py`, and two additive event
# types in `mission_control/events.py`. Those three are allowed here --
# and nothing else is, which is the point: the guard was **amended, with
# a reason**, not deleted or quietly narrowed.
RATIFIED_EXCEPTIONS = {
    "src/master_agent/runtime/approval.py": "ADR-0019",
    "src/master_agent/runtime/engine.py": "ADR-0019",
    "src/master_agent/mission_control/events.py": "ADR-0019",
}


def test_no_frozen_component_was_modified_without_a_ratified_adr():
    """MB026 changed nothing outside the dashboard package, and every
    change since has been permitted by a named, ratified ADR."""
    import subprocess

    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "v0.9.0-miracle-025",
            "HEAD",
            "--",
            "src/master_agent/mission_control/",
            "src/master_agent/runtime/",
            "src/master_agent/persistence/",
            "src/master_agent/verification/",
            "src/master_agent/plugins/",
            "src/master_agent/executor/",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip("git or the MB025 tag is unavailable")

    changed = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    unratified = [path for path in changed if path not in RATIFIED_EXCEPTIONS]

    assert unratified == [], (
        "a frozen component changed with no ratified ADR permitting it:\n"
        + "\n".join(unratified)
    )
