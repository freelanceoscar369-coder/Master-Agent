"""Architecture compliance for the Runtime Engine (Mission Brief 024
Rules 1 and 2), enforced mechanically so it cannot quietly stop being
true. Same posture as tests/test_mission_control_architecture.py.

    Rule 1: The Runtime Engine never performs work.
    Rule 2: It communicates only through Mission Control. It never
            directly calls Browser Executive APIs.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from master_agent.runtime.engine import RuntimeEngine
from master_agent.runtime.gateway import ExecutiveGateway, PluginGateway

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = REPO_ROOT / "src" / "master_agent" / "runtime"
MODULES = sorted(PACKAGE_DIR.glob("*.py"))

# Importing any of these would mean the Runtime could perform work itself,
# or had learned about a specific Executive.
FORBIDDEN_IMPORTS = {
    "playwright",
    "subprocess",
    "shutil",
    "socket",
    "requests",
    "httpx",
    "openai",
    "master_agent.executor.executor",
    "master_agent.executor.action",
    "master_agent.plugins.browser_plugin",
    "master_agent.plugins.browser_worker",
    "master_agent.plugins.browser_verifier",
    "master_agent.plugins.browser_observation",
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
def test_runtime_never_imports_an_executive_or_anything_that_performs_work(path: Path):
    imported = _imported_names(path)
    for forbidden in FORBIDDEN_IMPORTS:
        offenders = {
            name for name in imported if name == forbidden or name.startswith(forbidden + ".")
        }
        assert not offenders, (
            f"{path.name} imports {offenders} -- Rule 2 forbids the Runtime from knowing any "
            "specific Executive. See RUNTIME_ENGINE_ARCHITECTURE.md §2.1"
        )


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_runtime_source_never_names_a_specific_executive(path: Path):
    """Not even in a string literal or a comment-driven special case: a
    `if executive_id == "browser"` branch would defeat the whole design."""
    source = path.read_text(encoding="utf-8").lower()
    for banned in ("browserplugin", "browserworker", "browsersession", "filesystemplugin"):
        assert banned not in source, f"{path.name} names a specific Executive: {banned}"


def test_the_runtime_holds_no_environment_or_execution_machinery():
    """Rule 1: it orchestrates. Its only route to work is a gateway,
    which is a protocol, not an implementation it owns."""
    public = {name for name in dir(RuntimeEngine) if not name.startswith("_")}
    for forbidden in ("execute", "perform", "navigate", "click", "invoke_capability"):
        assert forbidden not in public


def test_the_gateway_protocol_carries_no_executive_knowledge():
    """Two methods, both generic. If this grows a browser-shaped method,
    Rule 2 has been broken at the contract level."""
    protocol_members = {
        name for name in dir(ExecutiveGateway) if not name.startswith("_")
    }
    assert protocol_members == {"invoke", "verify"}


def test_the_shipped_generic_gateway_is_not_executive_specific():
    """PluginGateway must work for any Plugin -- if it ever imports or
    type-checks against a concrete plugin, it has stopped being generic."""
    source = (PACKAGE_DIR / "gateway.py").read_text(encoding="utf-8")
    assert "BrowserPlugin" not in source
    assert "FilesystemPlugin" not in source
    assert PluginGateway is not None


def test_runtime_talks_to_mission_control_and_nothing_else_stateful():
    """Rule 2 positively stated: the only collaborators the engine module
    imports from the rest of the system are Mission Control's own surface
    and the generic verification vocabulary."""
    imported = _imported_names(PACKAGE_DIR / "engine.py")
    master_agent_imports = {name for name in imported if name.startswith("master_agent.")}
    for name in master_agent_imports:
        assert name.startswith(("master_agent.mission_control", "master_agent.runtime")), (
            f"engine.py imports {name}; the Runtime may only depend on Mission Control "
            "and its own package"
        )


def test_runtime_defines_no_second_evidence_or_verdict_type():
    """Verification vocabulary is MB022's, reused unchanged."""
    for path in MODULES:
        source = path.read_text(encoding="utf-8")
        assert "class Evidence" not in source
        assert "class Verdict" not in source
