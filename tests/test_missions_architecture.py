"""Mission Brief 037 — the hierarchy, asserted rather than promised.

```
Founder -> Mission Control -> Executives -> Workers -> Capabilities
        -> Broker -> Providers -> Verifier -> Evidence
```

Nothing in this brief may violate that. The way to keep a sentence like
that true a year from now is to make a test fail when it stops being
true, so this file parses the source rather than reading the docstrings.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "master_agent"
MISSIONS = sorted((SRC / "missions").glob("*.py"))


def tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def imports(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree(path)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def code_only(path: Path) -> str:
    """Source with docstrings stripped (MB036's helper, reused).

    A capability name in a docstring is an example; the same name in a
    string literal being compared against is hardcoded routing. Only the
    second is a defect, and a grep over raw source cannot tell them apart.
    """
    parsed = tree(path)
    for node in ast.walk(parsed):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                node.body = body[1:] or [ast.Pass()]
    return ast.unparse(parsed)


def calls(path: Path) -> set[str]:
    """Every attribute call name, e.g. `submit_objective` in
    `mc.submit_objective(...)`."""
    found: set[str] = set()
    for node in ast.walk(tree(path)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            found.add(node.func.attr)
    return found


def test_there_are_sources_to_check():
    assert len(MISSIONS) >= 4, [p.name for p in MISSIONS]


# =========================================================================
# The Planner is the only producer of a MissionPlan
# =========================================================================


def python_sources() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


#: Who may construct a `MissionPlan` or a `Step`.
#:
#: `planner/parsing.py` builds them from a reasoning provider's answer.
#: `planner/direct.py` builds them WITHOUT asking a model at all -- its
#: own docstring records the defect it exists to remove, where a founder
#: asking for a folder sent a planning prompt down the whole reasoning
#: ladder and opened browser windows for an objective that needed no
#: reasoning. Both are the Planner; the allowlist named only one because
#: `direct.py` did not exist when it was written. Admitting it is not a
#: widening of who may plan.
#:
#: `cli.py` is deliberately NOT here, though it does construct both and
#: therefore keeps these two tests red. It is the legacy demo entry point
#: (`master-agent-demo` in pyproject) and a genuine second planner -- the
#: exact duplication this guard exists against. MB037's cleanup of it
#: never landed, which is also why
#: `test_the_demo_cli_no_longer_imports_plan_vocabulary` and
#: `test_the_demo_cli_has_no_build_plan_left` fail beside these.
#:
#: Adding it here was tried and reverted: it would have made two guards
#: pass on a fact two other guards still correctly report, which is
#: papering over rather than fixing. Four tests reporting one real thing
#: is the honest state. `cli.py` is not shipped in Founder Edition -- it
#: appears nowhere in `packaging/kalpavriksha.spec` and nothing in the
#: composition root imports it -- so removing it is its own decision,
#: outside this convergence mission.
_ALLOWED_PLAN_BUILDERS = {
    "planner/parsing.py",
    "planner/direct.py",
}


def test_only_the_planner_constructs_a_mission_plan():
    """"Planner becomes the single producer of MissionPlans. No duplicate
    planning logic may exist." Before MB037 `cli.py` built one too."""
    builders = []
    for path in python_sources():
        for node in ast.walk(tree(path)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "MissionPlan"
            ):
                builders.append(path.relative_to(SRC).as_posix())

    assert set(builders) <= _ALLOWED_PLAN_BUILDERS, builders


def test_only_the_planner_constructs_a_step():
    steps = []
    for path in python_sources():
        for node in ast.walk(tree(path)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "Step"
            ):
                steps.append(path.relative_to(SRC).as_posix())

    assert set(steps) <= _ALLOWED_PLAN_BUILDERS, steps


def test_the_demo_cli_no_longer_imports_plan_vocabulary():
    assert "master_agent.planner.planner" not in imports(SRC / "cli.py")


def test_the_demo_cli_has_no_build_plan_left():
    source = (SRC / "cli.py").read_text(encoding="utf-8")

    assert "def build_plan" not in source


# =========================================================================
# The pipeline composes; it does not re-implement
# =========================================================================


def test_the_pipeline_never_dispatches_orders_or_retries():
    """Mission Control owns execution order, dependency resolution and
    retry. A second scheduler would be a second orchestration authority,
    which the brief forbids outright."""
    forbidden = {
        "dispatch_ready",
        "ready_tasks",
        "task_started",
        "task_completed",
        "task_failed",
        "run_once",
        "register_gateway",
    }
    for path in MISSIONS:
        assert not (calls(path) & forbidden), f"{path.name} drives execution"


def test_the_pipeline_holds_no_scheduler_of_its_own():
    """No topological sort, no ready-set, no queue. `depends_on` is copied
    across and Mission Control resolves it."""
    for path in MISSIONS:
        source = code_only(path).lower()
        for word in ("topolog", "kahn", "schedule", "queue", "priority_order"):
            assert word not in source, f"{path.name} contains `{word}`"


def test_the_pipeline_computes_no_verdict():
    """The Verifier owns correctness. Nothing here decides whether an
    answer was good; it records the verdict somebody else reached."""
    for path in MISSIONS:
        assert "verify" not in calls(path), f"{path.name} verifies"
        assert "master_agent.verification.evaluator" not in imports(path)


def test_the_pipeline_names_no_provider():
    vendors = ("ollama", "gemma", "claude", "gpt", "openai", "anthropic",
               "qwen", "deepseek", "mistral", "llama")
    for path in MISSIONS:
        source = code_only(path).lower()
        for vendor in vendors:
            assert vendor not in source, f"{path.name} names {vendor}"


def test_the_pipeline_holds_no_capability_name():
    """No hardcoded capability routing. The catalogue is Mission Control's
    registry and the Planner reads it; nothing here knows what a
    capability is called."""
    for path in MISSIONS:
        source = code_only(path)
        for name in ("Filesystem.", "Desktop.", "Browser.", "create_folder", "write_file"):
            assert name not in source, f"{path.name} names the capability {name}"


def test_the_pipeline_holds_no_regex():
    """No regex routing. An objective is decomposed by the Planner or not
    at all."""
    for path in MISSIONS:
        assert "re" not in imports(path)
        assert "regex" not in code_only(path).lower()


def test_history_never_writes_to_memory():
    """Memory owns persistence of lessons and MB034 already subscribes.
    A second writer would be a duplicate memory system."""
    history = SRC / "missions" / "history.py"

    assert "master_agent.memory" not in " ".join(imports(history))
    assert "remember" not in calls(history)


def test_replay_can_reach_no_provider_at_all():
    """The strongest form of "replay never invokes a provider": there is
    nothing in the module's imports that could."""
    history = SRC / "missions" / "history.py"
    reachable = imports(history)

    for module in ("master_agent.providers", "master_agent.ai_infrastructure",
                   "master_agent.plugins", "master_agent.broker", "httpx", "urllib",
                   "socket", "subprocess"):
        assert not any(m.startswith(module) for m in reachable), module


def test_the_pipeline_builds_no_second_event_bus():
    for path in MISSIONS:
        source = path.read_text(encoding="utf-8")
        assert "EventBus(" not in source, f"{path.name} builds a bus"


def test_the_pipeline_subscribes_per_event_type_never_to_everything():
    """MB034 learned what subscribing to all of it costs: the Runtime
    publishes a heartbeat every cycle."""
    history = (SRC / "missions" / "history.py").read_text(encoding="utf-8")

    assert "subscribe(handler, event_type)" in history
    assert "subscribe_all" not in history


# =========================================================================
# Frozen files
# =========================================================================


def test_mb037_needed_no_new_ratified_exception():
    """"Zero frozen files. No ADR." The standing guard in
    `test_dashboard_architecture.py` proves nothing frozen changed; this
    asserts the list it checks against did not grow to allow it."""
    from tests.test_dashboard_architecture import RATIFIED_EXCEPTIONS

    assert len(RATIFIED_EXCEPTIONS) == 7


def test_the_pipeline_imports_frozen_packages_only_for_their_vocabulary():
    """`mission_control.tasks` and `mission_control.events` are the
    published work vocabulary. Nothing reaches into the dispatcher or the
    runtime engine."""
    allowed = {
        "master_agent.mission_control.tasks",
        "master_agent.mission_control.events",
    }
    for path in MISSIONS:
        for module in imports(path):
            if module.startswith(("master_agent.mission_control", "master_agent.runtime",
                                  "master_agent.persistence", "master_agent.executor")):
                assert module in allowed, f"{path.name} imports {module}"


# =========================================================================
# Planner boundaries, restated for MB037
# =========================================================================


def test_the_planner_still_executes_nothing():
    planner = sorted((SRC / "planner").glob("*.py"))
    for path in planner:
        assert "invoke" not in calls(path), f"{path.name} invokes"
        assert "submit_objective" not in calls(path)


def test_the_planner_never_reaches_memory():
    """"Planner never updates memory." """
    for path in sorted((SRC / "planner").glob("*.py")):
        assert not any(m.startswith("master_agent.memory") for m in imports(path))


@pytest.mark.parametrize(
    "vocabulary", ["priority", "estimated_complexity"]
)
def test_the_planner_produces_the_fields_the_brief_asks_for(vocabulary):
    from master_agent.planner.plan import Step

    assert vocabulary in Step.__dataclass_fields__


def test_priority_and_complexity_are_closed_vocabularies():
    from master_agent.planner.plan import COMPLEXITIES, PRIORITIES

    assert PRIORITIES == ("low", "normal", "high", "critical")
    assert COMPLEXITIES == ("trivial", "small", "moderate", "large")
