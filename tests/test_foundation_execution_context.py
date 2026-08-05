"""Sprint 1, Component 2 — Execution Context.

The identity one execution carries. It references an Objective, a
Principal and a Warrant, and owns none of them.

The architecture tests at the bottom encode the acceptance criteria that
prose cannot hold: that this thing **cannot execute work** and **cannot
authorize work**. Both are checked against the type's actual surface and
its actual imports, because a value object acquires methods one reasonable
pull request at a time.
"""
from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from master_agent.foundation import ExecutionContext as ExportedContext
from master_agent.foundation.execution_context import ExecutionContext
from master_agent.foundation.principal import Principal, PrincipalKind

FOUNDER = Principal("onkar", "Onkar", PrincipalKind.FOUNDER)
CFO = Principal("cfo", "Head of Finance", PrincipalKind.DELEGATE)


def context(**overrides) -> ExecutionContext:
    defaults = {
        "objective_id": "obj-1",
        "principal": FOUNDER,
        "warrant_id": "wrt-1",
        "correlation_id": "cor-1",
        "trace_id": "trc-1",
    }
    return ExecutionContext(**{**defaults, **overrides})


# ======================================================================
# Construction
# ======================================================================


def test_it_can_be_instantiated() -> None:
    ctx = context()
    assert ctx.objective_id == "obj-1"
    assert ctx.principal == FOUNDER
    assert ctx.warrant_id == "wrt-1"
    assert ctx.correlation_id == "cor-1"
    assert ctx.trace_id == "trc-1"


def test_metadata_defaults_to_empty() -> None:
    assert dict(context().metadata) == {}


def test_it_carries_a_delegates_authority_just_as_well() -> None:
    """Delegation costs a different Principal, nothing else."""
    assert context(principal=CFO).principal_id == "cfo"


def test_principal_id_is_available_without_a_lookup() -> None:
    """The receipt layer records the id; it should not have to reach
    through to get it."""
    assert context().principal_id == "onkar"


def test_contexts_compare_by_value() -> None:
    assert context() == context()
    assert context(trace_id="trc-2") != context()


# ======================================================================
# Validation — a context that cannot answer its question is refused
# ======================================================================


@pytest.mark.parametrize(
    "field", ["objective_id", "warrant_id", "correlation_id", "trace_id"]
)
@pytest.mark.parametrize("bad", ["", "   "])
def test_every_identifier_is_required(field: str, bad: str) -> None:
    with pytest.raises(ValueError, match=f"{field} must be a non-empty identifier"):
        context(**{field: bad})


def test_the_principal_must_be_a_principal() -> None:
    """Not a string, not an id, and above all not the system."""
    with pytest.raises(TypeError, match="Kalpavriksha is never a principal"):
        context(principal="onkar")


def test_a_warrant_is_required_because_execution_follows_authorization() -> None:
    """A context without a warrant describes work nobody permitted."""
    with pytest.raises(TypeError):
        ExecutionContext(  # type: ignore[call-arg]
            objective_id="obj-1",
            principal=FOUNDER,
            correlation_id="cor-1",
            trace_id="trc-1",
        )


# ======================================================================
# Immutability
# ======================================================================


@pytest.mark.parametrize(
    "field", ["objective_id", "principal", "warrant_id", "correlation_id", "trace_id"]
)
def test_identity_cannot_be_mutated(field: str) -> None:
    ctx = context()
    with pytest.raises(FrozenInstanceError):
        setattr(ctx, field, "tampered")


def test_metadata_cannot_be_mutated() -> None:
    ctx = context(metadata={"attempt": "1"})
    with pytest.raises(TypeError):
        ctx.metadata["attempt"] = "2"  # type: ignore[index]


def test_the_callers_dict_cannot_reach_back_in() -> None:
    """A dict passed by a caller stays mutable through *their* reference
    even inside a frozen dataclass. Copying on construction is what makes
    'immutable' true of the object rather than of the annotation."""
    supplied = {"attempt": "1"}
    ctx = context(metadata=supplied)

    supplied["attempt"] = "99"
    supplied["injected"] = "yes"

    assert dict(ctx.metadata) == {"attempt": "1"}


def test_the_empty_default_is_not_shared_mutable_state() -> None:
    first = context()
    second = context()
    with pytest.raises(TypeError):
        first.metadata["x"] = "1"  # type: ignore[index]
    assert dict(second.metadata) == {}


# ======================================================================
# Integration with Component 1
# ======================================================================


def test_it_is_exported_from_the_foundation_package() -> None:
    assert ExportedContext is ExecutionContext


def test_it_does_not_depend_on_the_clock() -> None:
    """Both are foundation primitives and neither needs the other. A
    context carries identity, not time — a timestamp belongs to the receipt
    the Kernel writes, which is where the Clock is already injected."""
    source = MODULE.read_text(encoding="utf-8")
    assert "clock" not in source.lower()


def test_component_one_is_untouched() -> None:
    """Component 2 adds; it does not modify. Guards against a quiet edit to
    a tagged, verified milestone."""
    from master_agent.foundation import clock

    assert hasattr(clock, "SystemClock")
    assert hasattr(clock, "ManualClock")
    assert hasattr(clock, "Instant")


# ======================================================================
# ARCHITECTURE — it owns nothing and does nothing
# ======================================================================

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE = REPO_ROOT / "src" / "master_agent" / "foundation" / "execution_context.py"

#: Verbs that would mean this value had started doing work or granting
#: authority. Checked against the public surface rather than trusted to
#: review, because a value object acquires methods one reasonable pull
#: request at a time.
FORBIDDEN_VERBS = (
    "execute", "run", "invoke", "perform", "dispatch", "call",
    "authorize", "authorise", "grant", "permit", "approve", "deny",
    "mint", "settle", "commit", "apply", "start", "stop",
)

#: Packages an identity value must never reach. Importing any of them
#: would mean it could act, decide, or hold state that belongs elsewhere.
FORBIDDEN_IMPORTS = (
    "master_agent.executor",
    "master_agent.orchestrator",
    "master_agent.permissions",
    "master_agent.runtime",
    "master_agent.plugins",
    "master_agent.broker",
    "master_agent.mission_control",
    "master_agent.persistence",
    "subprocess",
    "socket",
)


def _public_surface() -> list[str]:
    return [name for name in dir(ExecutionContext) if not name.startswith("_")]


def test_it_cannot_execute_work() -> None:
    """Acceptance criterion, enforced against the real surface."""
    offenders = [
        name
        for name in _public_surface()
        if any(verb in name.lower() for verb in FORBIDDEN_VERBS)
    ]
    assert not offenders, (
        f"ExecutionContext exposes {offenders}, which reads as doing work. "
        "It is identity, not intelligence: it records what is running and "
        "on whose authority, and it never acts."
    )


def test_it_cannot_authorize_work() -> None:
    """It references a Warrant; it never produces one. Authorization is the
    Kernel's, and permission is the Permission System's."""
    surface = {name.lower() for name in _public_surface()}
    assert not surface & {"authorize", "grant", "permit", "approve", "warrant"}


def test_it_owns_no_objective() -> None:
    """The Objective Engine is the single source of truth. This holds an
    id, never an Objective — which is what keeps K1 with one place to ask
    whether an objective is live."""
    ctx = context()
    assert isinstance(ctx.objective_id, str)
    assert not hasattr(ctx, "objective")


def test_it_holds_no_permissions() -> None:
    ctx = context()
    for attribute in ("permissions", "grants", "authority", "scopes", "roles"):
        assert not hasattr(ctx, attribute)


def test_it_has_no_lifecycle() -> None:
    """Created per execution, never managed. A lifecycle is how a value
    starts surviving its execution."""
    surface = {name.lower() for name in _public_surface()}
    assert not surface & {"close", "dispose", "release", "open", "enter", "exit"}


def test_it_imports_nothing_that_could_act() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    imported: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    offenders = [
        name
        for name in imported
        if any(name.startswith(forbidden) for forbidden in FORBIDDEN_IMPORTS)
    ]
    assert not offenders, (
        f"execution_context.py imports {offenders}. An identity value that "
        "can reach the execution machinery is no longer only an identity."
    )


def test_the_only_master_agent_import_is_the_principal() -> None:
    """Its one legitimate dependency. Anything else means it has started
    knowing about parts of the system it only names by id."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    internal = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module
        and node.module.startswith("master_agent")
    }
    assert internal == {"master_agent.foundation.principal"}
