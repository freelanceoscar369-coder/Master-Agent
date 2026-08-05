"""Sprint 1, Component 5 — the Consequence Quartet.

The four questions every request for judgment answers before asking for a
verdict: *what changes, what it costs, what happens if you do nothing, and
whether it can be undone.*

VEDA 04 B1's invariant is a schema-level gate — *"a judgment request
missing any field cannot be emitted... enforce it where requests are
constructed, or it will be worked around."* The construction tests below
are that gate; the constitutional block at the bottom protects the
properties no ordinary unit test would notice going missing.
"""
from __future__ import annotations

import ast
import json
from dataclasses import FrozenInstanceError, fields
from decimal import Decimal
from pathlib import Path

import pytest

from master_agent.foundation import Consequence as ExportedConsequence
from master_agent.foundation.consequence import (
    Consequence,
    Cost,
    CostBasis,
    InvalidConsequence,
)
from master_agent.foundation.warrant import ReversibilityClass

PRICED = Cost(
    description="₹7,200 a year",
    basis=CostBasis.PRICED,
    amount=Decimal("7200.00"),
    currency="INR",
)
FREE = Cost(description="nothing", basis=CostBasis.FREE)
UNPRICEABLE = Cost(
    description="depends on how long the migration runs",
    basis=CostBasis.UNPRICEABLE,
)


def consequence(**overrides) -> Consequence:
    defaults = {
        "what_changes": "Sentry renews for another year",
        "cost": PRICED,
        "if_nothing": "it renews Friday 00:00",
        "reversibility": ReversibilityClass.REVERSIBLE_UNTIL,
    }
    return Consequence(**{**defaults, **overrides})


# ======================================================================
# CostBasis
# ======================================================================


def test_the_cost_basis_vocabulary_is_closed() -> None:
    assert {b.value for b in CostBasis} == {"priced", "free", "unpriceable"}


def test_free_and_unpriceable_are_distinguishable() -> None:
    """Ranking must treat *"this is free"* and *"I cannot price this"*
    differently — the first is a low-exposure fact, the second is
    uncertainty. Collapsing them into a missing amount hides the difference
    exactly where it matters."""
    assert FREE.basis is not UNPRICEABLE.basis
    assert FREE.amount is None and UNPRICEABLE.amount is None
    assert FREE != UNPRICEABLE


# ======================================================================
# Cost
# ======================================================================


def test_a_priced_cost_carries_an_amount_and_a_currency() -> None:
    assert PRICED.is_priced
    assert PRICED.amount == Decimal("7200.00")
    assert PRICED.currency == "INR"


@pytest.mark.parametrize("missing", [{"amount": None}, {"currency": None}])
def test_a_priced_cost_requires_both(missing: dict) -> None:
    with pytest.raises(InvalidConsequence, match="both an amount and a currency"):
        Cost(
            description="x",
            basis=CostBasis.PRICED,
            **{"amount": Decimal(1), "currency": "INR", **missing},
        )


def test_money_must_be_a_decimal_never_a_float() -> None:
    """VEDA 04 R3: *"treat as ledger arithmetic; never approximate."* Binary
    floating point cannot represent ₹0.10."""
    with pytest.raises(InvalidConsequence, match="must be a Decimal"):
        Cost(
            description="x",
            basis=CostBasis.PRICED,
            amount=7200.00,
            currency="INR",
        )


def test_priced_costs_sum_exactly() -> None:
    """VEDA 01 §5: swept approvals must show an aggregate — *"nine small
    approvals hide a total that one large one would not."* A total that
    drifts is a total the founder cannot rely on."""
    amounts = [Decimal("0.10"), Decimal("0.20")]
    assert sum(amounts) == Decimal("0.30")
    assert 0.1 + 0.2 != 0.3


def test_a_negative_amount_is_refused() -> None:
    with pytest.raises(InvalidConsequence, match="must not be negative"):
        Cost(
            description="x",
            basis=CostBasis.PRICED,
            amount=Decimal(-1),
            currency="INR",
        )


def test_a_zero_amount_is_allowed_when_priced() -> None:
    """Explicitly priced at zero is a different statement from `FREE`, and
    both are legitimate."""
    assert Cost(
        description="waived this year",
        basis=CostBasis.PRICED,
        amount=Decimal(0),
        currency="INR",
    ).is_priced


@pytest.mark.parametrize("basis", [CostBasis.FREE, CostBasis.UNPRICEABLE])
def test_an_unpriced_cost_carries_no_amount(basis: CostBasis) -> None:
    with pytest.raises(InvalidConsequence, match="carries no amount or currency"):
        Cost(
            description="x", basis=basis, amount=Decimal(1), currency="INR"
        )


@pytest.mark.parametrize("bad", ["", "   "])
def test_a_cost_description_is_always_required(bad: str) -> None:
    """A blank cost is indistinguishable from an unanswered one — including
    for an unpriceable cost, where the description is where the reason
    lives."""
    with pytest.raises(InvalidConsequence, match="cost description is required"):
        Cost(description=bad, basis=CostBasis.UNPRICEABLE)


def test_a_blank_currency_is_refused() -> None:
    with pytest.raises(InvalidConsequence, match="non-empty code"):
        Cost(
            description="x",
            basis=CostBasis.PRICED,
            amount=Decimal(1),
            currency="  ",
        )


def test_the_basis_must_be_a_cost_basis() -> None:
    with pytest.raises(InvalidConsequence, match="must be a CostBasis"):
        Cost(description="x", basis="free")


def test_cost_serialises_money_as_a_string() -> None:
    """JSON has only floats. Rendering `Decimal` as a string is what keeps
    the precision the ledger depends on."""
    assert PRICED.as_dict()["amount"] == "7200.00"
    assert FREE.as_dict()["amount"] is None


# ======================================================================
# Consequence — the gate
# ======================================================================


def test_a_complete_quartet_can_be_created() -> None:
    q = consequence()
    assert q.what_changes == "Sentry renews for another year"
    assert q.cost is PRICED
    assert q.if_nothing == "it renews Friday 00:00"
    assert q.reversibility is ReversibilityClass.REVERSIBLE_UNTIL


def test_no_field_has_a_default() -> None:
    """VEDA 04's contract: *"returns an error, never a partial."* A default
    is how a caller omits a field and discovers it at render time."""
    from dataclasses import MISSING

    for field in fields(Consequence):
        assert field.default is MISSING, f"{field.name} has a default"
        assert field.default_factory is MISSING, f"{field.name} has a default factory"


@pytest.mark.parametrize(
    "omit", ["what_changes", "cost", "if_nothing", "reversibility"]
)
def test_a_partial_quartet_is_not_constructible(omit: str) -> None:
    """VEDA 01 §5: *"A request missing any of the four is not a request; it
    is a guess dressed as one, and it does not ship."*"""
    args = {
        "what_changes": "x",
        "cost": FREE,
        "if_nothing": "y",
        "reversibility": ReversibilityClass.REVERSIBLE,
    }
    del args[omit]
    with pytest.raises(TypeError):
        Consequence(**args)


@pytest.mark.parametrize("field", ["what_changes", "if_nothing"])
@pytest.mark.parametrize("bad", ["", "   "])
def test_a_blank_answer_does_not_count_as_an_answer(field: str, bad: str) -> None:
    with pytest.raises(InvalidConsequence, match=f"{field} is required"):
        consequence(**{field: bad})


def test_the_cost_must_be_a_cost() -> None:
    with pytest.raises(InvalidConsequence, match="cost must be a Cost"):
        consequence(cost="₹7,200")


def test_the_reversibility_must_be_a_reversibility_class() -> None:
    with pytest.raises(InvalidConsequence, match="must be a ReversibilityClass"):
        consequence(reversibility="reversible")


def test_an_unpriceable_cost_still_makes_a_complete_quartet() -> None:
    """VEDA 01 §8 distinguishes *I don't know* from *I haven't checked*.
    Honest uncertainty is an answer; silence is not."""
    assert consequence(cost=UNPRICEABLE).cost.basis is CostBasis.UNPRICEABLE


# ======================================================================
# Immutability, equality, hashing, serialisation
# ======================================================================


@pytest.mark.parametrize(
    "field", ["what_changes", "cost", "if_nothing", "reversibility"]
)
def test_a_quartet_cannot_be_mutated(field: str) -> None:
    """A quartet is what the founder was shown when they decided. Editing it
    afterwards would restate the basis of a decision already made."""
    with pytest.raises(FrozenInstanceError):
        setattr(consequence(), field, "tampered")


def test_a_cost_cannot_be_mutated() -> None:
    with pytest.raises(FrozenInstanceError):
        PRICED.amount = Decimal(1)


def test_equality_is_deterministic() -> None:
    assert consequence() == consequence()
    assert consequence(if_nothing="nothing happens") != consequence()
    assert consequence(cost=FREE) != consequence()


def test_a_quartet_is_hashable() -> None:
    assert hash(consequence()) == hash(consequence())
    assert len({consequence(), consequence(), consequence(cost=FREE)}) == 2


def test_serialisation_is_deterministic() -> None:
    assert consequence().as_dict() == consequence().as_dict()
    assert list(consequence().as_dict()) == list(consequence().as_dict())


def test_serialisation_is_json_ready_and_carries_no_floats() -> None:
    payload = json.dumps(consequence().as_dict(), sort_keys=True)
    restored = json.loads(payload)

    assert restored["cost"]["amount"] == "7200.00"
    assert restored["reversibility"] == "reversible_until"
    assert not isinstance(restored["cost"]["amount"], float)


def test_serialisation_carries_every_field() -> None:
    assert set(consequence().as_dict()) == {f.name for f in fields(Consequence)}


def test_is_irreversible_reports_a_fact_not_a_policy() -> None:
    """What follows from it — never batched, never routed to a batchable
    tier — is the router's decision, not the quartet's."""
    assert consequence(reversibility=ReversibilityClass.IRREVERSIBLE).is_irreversible
    assert not consequence().is_irreversible


# ======================================================================
# CONSTITUTIONAL
# ======================================================================

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE = REPO_ROOT / "src" / "master_agent" / "foundation" / "consequence.py"

FORBIDDEN_VERBS = (
    "execute", "run", "invoke", "perform", "dispatch",
    "authorize", "authorise", "grant", "permit", "approve", "deny",
    "mint", "issue", "settle", "revoke", "start", "stop", "update", "set",
)

FORBIDDEN_IMPORTS = (
    "master_agent.verification",
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


def _module_imports() -> list[str]:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    return imported


def _public_surface() -> list[str]:
    field_names = {f.name for f in fields(Consequence)}
    return [
        name
        for name in dir(Consequence)
        if not name.startswith("_") and name not in field_names
    ]


def test_it_is_independent_of_evidence() -> None:
    """Evidence and Consequence are two different constitutional concepts.

    Evidence (Constitution §17) belongs to verification *after* execution:
    Observation + Expected Outcome + Verdict. Consequence (VEDA 04 B1)
    belongs to judgment *before* it: what changes, what it costs, what
    happens if you do nothing, whether it can be undone.

    Nothing here imports, subclasses, or reuses the shipped Evidence, and
    this test is what keeps the two from converging by accident.
    """
    assert not any("verification" in name for name in _module_imports())
    assert not any(
        term in name.lower()
        for name in {f.name for f in fields(Consequence)}
        for term in ("evidence", "observation", "verdict")
    )


def test_it_uses_one_reversibility_vocabulary_not_two() -> None:
    """The same enum the Warrant carries, so there is one ordering of
    consequence in the system rather than two that can disagree."""
    assert consequence().reversibility.__class__ is ReversibilityClass


def test_it_references_no_execution_object() -> None:
    """A consequence describes a *proposed* action. The thing that has one
    holds it; it knows nothing about what it describes, which is what keeps
    it free of any cycle."""
    names = {f.name for f in fields(Consequence)}
    for term in ("warrant", "receipt", "context", "objective", "principal"):
        assert not any(term in name for name in names)


def test_it_cannot_execute_or_authorize_work() -> None:
    offenders = [
        name
        for name in _public_surface()
        if any(verb in name.lower() for verb in FORBIDDEN_VERBS)
    ]
    assert not offenders, f"Consequence exposes {offenders}"


def test_it_reads_no_ambient_time() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    banned = {"datetime.now", "datetime.utcnow", "datetime.today", "time.time"}
    calls = [
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ".".join(ast.unparse(node.func).split(".")[-2:]) in banned
    ]
    assert not calls, f"consequence.py reads ambient time: {calls}"


def test_it_imports_nothing_that_could_act() -> None:
    offenders = [
        name
        for name in _module_imports()
        if any(name.startswith(forbidden) for forbidden in FORBIDDEN_IMPORTS)
    ]
    assert not offenders, f"consequence.py imports {offenders}"


def test_its_only_internal_import_is_the_reversibility_vocabulary() -> None:
    internal = {
        name for name in _module_imports() if name.startswith("master_agent")
    }
    assert internal == {"master_agent.foundation.warrant"}


def test_it_is_exported_from_the_foundation_package() -> None:
    assert ExportedConsequence is Consequence


def test_components_one_to_four_are_untouched() -> None:
    from master_agent.foundation import (
        clock,
        execution_context,
        principal,
        receipt,
        warrant,
    )

    assert hasattr(clock, "SystemClock")
    assert hasattr(principal, "PrincipalRegistry")
    assert hasattr(execution_context, "ExecutionContext")
    assert hasattr(warrant, "Warrant")
    assert hasattr(receipt, "Receipt")
