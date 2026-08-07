"""Mission Brief 036 — the claims about `planner/`, asserted rather than
promised.

MB031 established the pattern: a package that says what it is not should
be parsed to prove it, because a paragraph in a docstring is only true
until somebody adds an import. Four claims here.

1. It decides *what to do*, never *who does it*. No provider vocabulary,
   no ranking, no fallback.
2. It reaches nothing itself. No network, no subprocess, no filesystem.
   Constitution Rule 4: Environment access has exactly one door, and it
   is not this one.
3. It touches no frozen component.
4. Every Step it emits states what it expects. §3.2, mechanically.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from master_agent.planner.plan import Intent
from master_agent.planner.planner import Planner
from tests.planner_test_support import CATALOGUE, CREATE, WRITE, StubRunner, plan_text, step

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "master_agent" / "planner"
SOURCES = sorted(PACKAGE.glob("*.py"))


def trees():
    for path in SOURCES:
        yield path, ast.parse(path.read_text(encoding="utf-8"))


def imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def code_only(path: Path) -> str:
    """Source with docstrings and comments stripped.

    A vendor name in a docstring is documentation; the same name in a
    string literal being compared against is a hardcoded provider. Only
    the second is a defect, and a grep over raw source cannot tell them
    apart -- MB033 found a test that passed on a substring for want of
    this distinction.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def test_there_are_sources_to_check():
    """A glob that silently matches nothing would make every test below
    pass for the wrong reason."""
    assert len(SOURCES) >= 6, [p.name for p in SOURCES]


# =========================================================================
# 1. It decides what to do, never who does it
# =========================================================================

VENDORS = (
    "ollama",
    "gemma",
    "llama",
    "mistral",
    "openai",
    "gpt",
    "anthropic",
    "claude",
    "gemini",
    "copilot",
    "perplexity",
    "hermes",
    "kimi",
    "whisper",
)


@pytest.mark.parametrize("vendor", VENDORS)
def test_no_product_name_appears_anywhere_in_the_planner(vendor):
    """MB032 removed the last product names from Brain logic and turned
    "I need this done well" into a quality floor. A Planner that named a
    model would put them straight back."""
    for path in SOURCES:
        assert vendor not in code_only(path).lower(), f"{path.name} names {vendor}"


def test_the_planner_holds_no_ranking_and_no_fallback():
    """ADR-0018's Consequences name a ranking function growing outside the
    Broker as the single failure mode that would invalidate the design."""
    for path in SOURCES:
        source = code_only(path).lower()
        for word in ("fallback", "cheapest", "best_provider", "prefer_provider", "score"):
            assert word not in source, f"{path.name} contains `{word}`"


def test_nothing_in_the_planner_sorts_or_filters_providers():
    """The Planner names one AI Capability -- `reasoning` -- and the
    Broker answers. It never sees a candidate list, so it cannot have an
    opinion about one."""
    for _path, tree in trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                assert node.attr not in {
                    "profiles",
                    "candidates",
                    "provider_profiles",
                }, ast.dump(node)


# =========================================================================
# 2. It reaches nothing itself
# =========================================================================

FORBIDDEN_IMPORTS = {
    "socket",
    "http",
    "http.client",
    "urllib",
    "urllib.request",
    "requests",
    "httpx",
    "subprocess",
    "os",
    "shutil",
    "pathlib",
    "sqlite3",
}


def test_the_planner_imports_nothing_that_can_reach_the_machine():
    for path, tree in trees():
        for module in imported_modules(tree):
            root = module.split(".")[0]
            assert module not in FORBIDDEN_IMPORTS and root not in FORBIDDEN_IMPORTS, (
                f"{path.name} imports {module}"
            )


def test_the_planner_never_opens_a_file_or_starts_a_process():
    for path, tree in trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"open", "exec", "eval", "compile"}, (
                    f"{path.name} calls {node.func.id}()"
                )


def test_the_planner_depends_on_no_frozen_runtime_component():
    """`plugins/model_router` is the exception, and it is the *published*
    request vocabulary rather than a runtime: `RoutingContext` and
    `SelectionRequest` are the two frozen dataclasses MB032 made the way
    every caller asks the Broker for something."""
    allowed_frozen = {"master_agent.plugins.model_router"}
    for path, tree in trees():
        for module in imported_modules(tree):
            if not module.startswith("master_agent."):
                continue
            package = module.split(".")[1]
            if package in {"runtime", "persistence", "mission_control", "executor"}:
                pytest.fail(f"{path.name} imports the frozen {module}")
            if package == "plugins":
                assert module in allowed_frozen, f"{path.name} imports {module}"


def test_the_planner_uses_verification_only_through_its_published_contract():
    """ADR-0011 keeps Verification structurally independent. The Planner
    consumes `Evidence` and `ExpectedOutcome`; it never reaches into the
    evaluator or subclasses a Verifier."""
    for path, tree in trees():
        for module in imported_modules(tree):
            if module.startswith("master_agent.verification"):
                assert module == "master_agent.verification.evidence", (
                    f"{path.name} imports {module}"
                )


# =========================================================================
# 3. It touches no frozen component
# =========================================================================


def test_mb036_changed_nothing_outside_the_planner_package():
    """The guard in `test_dashboard_architecture.py` is the standing one.
    This is the brief-specific claim: MB036 needed no ratified exception,
    so `RATIFIED_EXCEPTIONS` gained no row."""
    from tests.test_dashboard_architecture import RATIFIED_EXCEPTIONS

    assert "src\\master_agent\\planner\\planner.py" not in RATIFIED_EXCEPTIONS
    assert len(RATIFIED_EXCEPTIONS) == 7, "MB036 added a frozen-file exception"


# =========================================================================
# 4. Every Step it emits states what it expects
# =========================================================================


@pytest.mark.parametrize(
    "steps",
    [
        [step("one")],
        [step("one"), step("two", WRITE.name)],
        [step("a"), step("b", depends_on=["a"]), step("c", depends_on=["b"])],
        [step(f"s{index}", CREATE.name) for index in range(12)],
    ],
)
def test_no_plan_the_planner_produces_has_a_step_without_an_expectation(steps):
    outcome = Planner(StubRunner(plan_text(*steps)), CATALOGUE).plan(Intent(goal="go"))

    assert outcome.planned, outcome.reason
    assert len(outcome.plan.steps) == len(steps)
    for planned in outcome.plan.steps:
        assert planned.expected_outcome is not None
        assert planned.expected_outcome.checks


def test_the_vocabulary_is_still_importable_from_where_it_always_was():
    """The Orchestrator, `cli.py` and two test modules import `MissionPlan`
    and `Step` from `planner.planner`. Moving the definitions to `plan.py`
    is only safe because that path still resolves."""
    from master_agent.planner.plan import Intent as PlanIntent
    from master_agent.planner.plan import MissionPlan as PlanMissionPlan
    from master_agent.planner.plan import Step as PlanStep
    from master_agent.planner.planner import Intent, MissionPlan, Step

    assert (Intent, MissionPlan, Step) == (PlanIntent, PlanMissionPlan, PlanStep)


def test_a_hand_built_step_without_an_expectation_is_still_legal():
    """§3.2 is a rule about planning, enforced where planning happens.
    Making the dataclass field required would have turned a vocabulary
    change into a rewrite of five earlier briefs."""
    from master_agent.planner.plan import Step as PlainStep

    hand_built = PlainStep(step_id="s", capability="Filesystem.CreateFolder", payload={})

    assert hand_built.expected_outcome is None
