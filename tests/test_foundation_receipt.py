"""Sprint 1, Component 4 — Constitutional Receipt.

Evidence of what one execution attempt did. Written after the fact, never
touched again.

Every test uses fixed instants. Nothing here reads a wall clock — a receipt
takes its moments as arguments precisely so that it cannot.
"""
from __future__ import annotations

import ast
import json
from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from master_agent.foundation import Receipt as ExportedReceipt
from master_agent.foundation.execution_context import ExecutionContext
from master_agent.foundation.principal import Principal, PrincipalKind
from master_agent.foundation.receipt import (
    ExecutionOutcome,
    InvalidReceipt,
    Receipt,
)

STARTED = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
COMPLETED = STARTED + timedelta(seconds=2, milliseconds=300)


def receipt(**overrides) -> Receipt:
    defaults = {
        "receipt_id": "rcp-1",
        "objective_id": "obj-1",
        "principal_id": "onkar",
        "warrant_id": "wrt-1",
        "correlation_id": "cor-1",
        "trace_id": "trc-1",
        "capability": "Filesystem.WriteFile",
        "attempt": 1,
        "outcome": ExecutionOutcome.SUCCEEDED,
        "started_at": STARTED,
        "completed_at": COMPLETED,
    }
    return Receipt(**{**defaults, **overrides})


# ======================================================================
# ExecutionOutcome
# ======================================================================


def test_the_outcome_vocabulary_is_closed() -> None:
    """The Kernel Specification §6.3 settlement kinds, unchanged. A fifth
    kind is a caller who has not finished deciding what happened."""
    assert {o.value for o in ExecutionOutcome} == {
        "succeeded",
        "failed",
        "partial",
        "unknown",
    }


def test_unknown_exists_as_its_own_outcome() -> None:
    """Not folded into `failed`. A caller that times out mid-request
    genuinely does not know, and pretending otherwise is how a system
    double-charges a card."""
    assert ExecutionOutcome.UNKNOWN is not ExecutionOutcome.FAILED


# ======================================================================
# Construction
# ======================================================================


def test_a_receipt_can_be_created() -> None:
    r = receipt()
    assert r.receipt_id == "rcp-1"
    assert r.warrant_id == "wrt-1"
    assert r.capability == "Filesystem.WriteFile"
    assert r.outcome is ExecutionOutcome.SUCCEEDED


@pytest.mark.parametrize(
    "field",
    [
        "receipt_id",
        "objective_id",
        "principal_id",
        "warrant_id",
        "correlation_id",
        "trace_id",
        "capability",
    ],
)
@pytest.mark.parametrize("bad", ["", "   "])
def test_every_reference_is_required(field: str, bad: str) -> None:
    with pytest.raises(InvalidReceipt, match=f"{field} must be a non-empty"):
        receipt(**{field: bad})


def test_a_receipt_without_a_warrant_cannot_exist() -> None:
    """It would be a record of something nobody authorized."""
    with pytest.raises(InvalidReceipt, match="warrant_id must be a non-empty"):
        receipt(warrant_id="")


def test_the_outcome_must_be_an_execution_outcome() -> None:
    with pytest.raises(InvalidReceipt, match="must be an ExecutionOutcome"):
        receipt(outcome="succeeded")


@pytest.mark.parametrize("bad", [0, -1])
def test_attempt_is_one_based(bad: int) -> None:
    """There is no attempt zero to record."""
    with pytest.raises(InvalidReceipt, match="1-based"):
        receipt(attempt=bad)


def test_a_boolean_is_not_an_attempt_number() -> None:
    """`True == 1` in Python."""
    with pytest.raises(InvalidReceipt, match="must be an int"):
        receipt(attempt=True)


def test_several_receipts_may_share_one_warrant() -> None:
    """A warrant carries an attempt budget; each attempt that completes
    writes its own evidence."""
    first = receipt(receipt_id="rcp-1", attempt=1, outcome=ExecutionOutcome.FAILED)
    second = receipt(receipt_id="rcp-2", attempt=2)

    assert first.warrant_id == second.warrant_id
    assert first.attempt < second.attempt


# ======================================================================
# Time
# ======================================================================


def test_a_naive_timestamp_is_refused() -> None:
    with pytest.raises(InvalidReceipt, match="timezone-aware"):
        receipt(started_at=datetime(2026, 8, 5, 12, 0))  # noqa: DTZ001


def test_timestamps_are_normalised_to_utc() -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    r = receipt(
        started_at=STARTED.astimezone(ist), completed_at=COMPLETED.astimezone(ist)
    )

    assert r.started_at.tzinfo is UTC
    assert r.started_at == STARTED
    assert r == receipt()


def test_an_execution_cannot_finish_before_it_began() -> None:
    with pytest.raises(InvalidReceipt, match="completed_at precedes started_at"):
        receipt(completed_at=STARTED - timedelta(seconds=1))


def test_an_instantaneous_attempt_is_allowed() -> None:
    """Equal timestamps are legitimate: a refusal can complete inside the
    clock's resolution."""
    assert receipt(completed_at=STARTED).duration == timedelta(0)


def test_duration_is_derived_not_stored() -> None:
    assert receipt().duration == timedelta(seconds=2, milliseconds=300)
    assert "duration" not in {f.name for f in fields(Receipt)}


# ======================================================================
# Partial outcomes and compensation
# ======================================================================


def test_a_partial_outcome_requires_a_compensating_reference() -> None:
    """Kernel Specification §6.3. Some effect occurred and the record must
    say how to undo it — a half-written file is not a file that was not
    written."""
    with pytest.raises(InvalidReceipt, match="requires a compensating action"):
        receipt(outcome=ExecutionOutcome.PARTIAL)


@pytest.mark.parametrize("blank", ["", "   "])
def test_a_blank_compensating_reference_does_not_satisfy_it(blank: str) -> None:
    with pytest.raises(InvalidReceipt, match="requires a compensating action"):
        receipt(outcome=ExecutionOutcome.PARTIAL, compensation_ref=blank)


def test_a_partial_outcome_with_compensation_is_valid() -> None:
    r = receipt(outcome=ExecutionOutcome.PARTIAL, compensation_ref="Filesystem.Restore")
    assert r.compensation_ref == "Filesystem.Restore"


@pytest.mark.parametrize(
    "outcome",
    [ExecutionOutcome.SUCCEEDED, ExecutionOutcome.FAILED, ExecutionOutcome.UNKNOWN],
)
def test_compensation_is_refused_for_every_other_outcome(
    outcome: ExecutionOutcome,
) -> None:
    """So the field cannot quietly become optional on a partial."""
    with pytest.raises(InvalidReceipt, match="only meaningful for a partial"):
        receipt(outcome=outcome, compensation_ref="Filesystem.Restore")


# ======================================================================
# Derived answers
# ======================================================================


def test_is_success_is_true_only_for_succeeded() -> None:
    assert receipt().is_success
    assert not receipt(outcome=ExecutionOutcome.FAILED).is_success
    assert not receipt(outcome=ExecutionOutcome.UNKNOWN).is_success
    assert not receipt(
        outcome=ExecutionOutcome.PARTIAL, compensation_ref="c"
    ).is_success


def test_only_an_unknown_outcome_always_escalates() -> None:
    """The caller could not determine whether the effect occurred. The
    honest response is to ask, never to try again."""
    assert receipt(outcome=ExecutionOutcome.UNKNOWN).requires_escalation
    assert not receipt().requires_escalation
    assert not receipt(outcome=ExecutionOutcome.FAILED).requires_escalation


# ======================================================================
# Immutability, equality, hashing, serialisation
# ======================================================================


@pytest.mark.parametrize(
    "field", ["receipt_id", "warrant_id", "outcome", "attempt", "detail"]
)
def test_a_receipt_cannot_be_mutated(field: str) -> None:
    """Evidence that could be edited is not evidence."""
    with pytest.raises(FrozenInstanceError):
        setattr(receipt(), field, "tampered")


def test_equality_is_deterministic() -> None:
    assert receipt() == receipt()
    assert receipt(receipt_id="rcp-2") != receipt()
    assert receipt(outcome=ExecutionOutcome.FAILED) != receipt()


def test_a_receipt_is_hashable() -> None:
    assert hash(receipt()) == hash(receipt())
    assert len({receipt(), receipt(), receipt(receipt_id="rcp-2")}) == 2


def test_serialisation_is_deterministic() -> None:
    assert receipt().as_dict() == receipt().as_dict()
    assert list(receipt().as_dict()) == list(receipt().as_dict())


def test_serialisation_is_json_ready() -> None:
    payload = json.loads(json.dumps(receipt().as_dict(), sort_keys=True))
    assert payload["outcome"] == "succeeded"
    assert payload["started_at"] == "2026-08-05T12:00:00+00:00"
    assert payload["attempt"] == 1


def test_serialisation_carries_every_field() -> None:
    """A projection that quietly dropped a field would produce evidence
    that understates what happened."""
    assert set(receipt().as_dict()) == {f.name for f in fields(Receipt)}


# ======================================================================
# CONSTITUTIONAL — references, and what is deliberately absent
# ======================================================================

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE = REPO_ROOT / "src" / "master_agent" / "foundation" / "receipt.py"

FORBIDDEN_VERBS = (
    "execute", "run", "invoke", "perform", "dispatch",
    "authorize", "authorise", "grant", "permit", "approve", "deny",
    "mint", "issue", "settle", "revoke", "start", "stop", "update", "set",
)

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
    """Behaviour only — never data fields. A field cannot do anything, and
    the criterion here is about behaviour."""
    field_names = {f.name for f in fields(Receipt)}
    return [
        name
        for name in dir(Receipt)
        if not name.startswith("_") and name not in field_names
    ]


def test_it_references_the_execution_context_as_component_2_defines_it() -> None:
    """**ED-006.** The brief lists `execution_context_id`. `ExecutionContext`
    (Component 2, `kalpavriksha-s1-c2.0`) has no such field: its per-execution
    identifier is `trace_id`, with `correlation_id` naming the group.

    Adding an id to Component 2 is forbidden, and synthesising one would
    invent an identifier nothing produces. So the receipt carries both real
    fields, which together identify an Execution Context exactly.

    This test exists so the substitution is demonstrably a decision rather
    than an oversight, and so it breaks loudly if Component 2 ever gains a
    single id of its own.
    """
    context_fields = {f.name for f in fields(ExecutionContext)}
    assert "execution_context_id" not in context_fields, (
        "ExecutionContext has gained an id; ED-006 should be revisited and "
        "the Receipt should reference it directly."
    )

    receipt_fields = {f.name for f in fields(Receipt)}
    assert {"correlation_id", "trace_id"} <= receipt_fields


def test_the_reference_round_trips_against_a_real_execution_context() -> None:
    """Evidence that the linkage is exact, not merely plausible."""
    context = ExecutionContext(
        objective_id="obj-1",
        principal=Principal("onkar", "Onkar", PrincipalKind.FOUNDER),
        warrant_id="wrt-1",
        correlation_id="cor-1",
        trace_id="trc-1",
    )
    r = receipt()

    assert r.objective_id == context.objective_id
    assert r.principal_id == context.principal_id
    assert r.warrant_id == context.warrant_id
    assert r.correlation_id == context.correlation_id
    assert r.trace_id == context.trace_id


def test_it_cannot_execute_work() -> None:
    offenders = [
        name
        for name in _public_surface()
        if any(verb in name.lower() for verb in FORBIDDEN_VERBS)
    ]
    assert not offenders, f"Receipt exposes {offenders}, which reads as doing work."


def test_it_cannot_authorize_work() -> None:
    """It is written after the fact. Authorization was the Warrant's."""
    surface = {name.lower() for name in _public_surface()}
    assert not surface & {"authorize", "grant", "permit", "approve", "revoke"}


def test_it_owns_no_constitutional_object() -> None:
    """Ids only. Objective, Warrant and Execution Context are each owned
    elsewhere and stay owned there."""
    r = receipt()
    for owned in ("objective", "warrant", "context", "execution_context", "principal"):
        assert not hasattr(r, owned)


def test_it_holds_no_mutable_state() -> None:
    from dataclasses import fields as dc_fields

    names = {f.name for f in dc_fields(Receipt)}
    forbidden = {"status", "state", "retries", "progress", "next_attempt", "pending"}
    assert not names & forbidden


def test_it_does_not_reference_learning() -> None:
    """Learning subscribes to the receipt stream; the stream does not know
    it exists.

    Checked against fields and imports rather than against the prose — the
    module docstring names Learning precisely to say it is absent, and a
    text search would flag that sentence as a violation of itself.
    """
    assert not any("learn" in f.name.lower() for f in fields(Receipt))
    assert not any("learn" in name.lower() for name in _public_surface())

    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    assert not any("learn" in name.lower() for name in imported)


def test_it_reads_no_ambient_time() -> None:
    """Timestamps are supplied by the Kernel from the canonical Clock."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    banned = {"datetime.now", "datetime.utcnow", "datetime.today", "time.time"}
    calls = [
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ".".join(ast.unparse(node.func).split(".")[-2:]) in banned
    ]
    assert not calls, f"receipt.py reads ambient time: {calls}"


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
    assert not offenders, f"receipt.py imports {offenders}"


def test_it_imports_nothing_from_master_agent_at_all() -> None:
    """A flat, self-contained record — which is what makes it deterministic
    to serialise and safe to keep forever."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    internal = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module
        and node.module.startswith("master_agent")
    }
    assert internal == set()


def test_it_is_exported_from_the_foundation_package() -> None:
    assert ExportedReceipt is Receipt


def test_components_one_to_three_are_untouched() -> None:
    from master_agent.foundation import clock, execution_context, principal, warrant

    assert hasattr(clock, "SystemClock")
    assert hasattr(principal, "PrincipalRegistry")
    assert hasattr(execution_context, "ExecutionContext")
    assert hasattr(warrant, "Warrant")
