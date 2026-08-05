"""Sprint 1, Component 3 — Constitutional Warrant.

The proof that one execution was authorized. Evidence *of* authorization,
never the act *of* authorizing.

Tests are grouped by what they protect. The constitutional block at the
bottom is the one that matters: three invariants that come straight from
frozen documents and that no ordinary unit test would notice going
missing.

Every test uses fixed instants. Nothing here reads a wall clock — a
warrant takes the moment as an argument precisely so that it can't.
"""
from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from master_agent.foundation import Warrant as ExportedWarrant
from master_agent.foundation.warrant import (
    InvalidWarrant,
    ReversibilityClass,
    Warrant,
)

ISSUED = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
EXPIRES = ISSUED + timedelta(minutes=5)


def warrant(**overrides) -> Warrant:
    defaults = {
        "warrant_id": "wrt-1",
        "objective_id": "obj-1",
        "principal_id": "onkar",
        "capability": "Filesystem.WriteFile",
        "payload_digest": "sha256:abc",
        "reversibility_class": ReversibilityClass.REVERSIBLE,
        "consequence_ceiling": ReversibilityClass.REVERSIBLE_UNTIL,
        "attempt_budget": 3,
        "issued_at": ISSUED,
        "expires_at": EXPIRES,
        "grant_ref": "grant-1",
    }
    return Warrant(**{**defaults, **overrides})


# ======================================================================
# ReversibilityClass — the consequence ordering
# ======================================================================


def test_the_vocabulary_is_closed() -> None:
    """An open enum is where `probably_reversible` eventually appears, and
    VEDA 04 A2 requires classification to fail closed."""
    assert {c.value for c in ReversibilityClass} == {
        "read_only",
        "reversible",
        "reversible_until",
        "irreversible",
    }


def test_classes_are_ordered_by_consequence() -> None:
    order = [
        ReversibilityClass.READ_ONLY,
        ReversibilityClass.REVERSIBLE,
        ReversibilityClass.REVERSIBLE_UNTIL,
        ReversibilityClass.IRREVERSIBLE,
    ]
    severities = [c.severity for c in order]
    assert severities == sorted(severities)
    assert len(set(severities)) == 4


def test_reversible_until_sits_between_reversible_and_irreversible() -> None:
    """It *becomes* irreversible when its window closes — reversible the way
    a recallable message is, which is to say temporarily."""
    assert ReversibilityClass.REVERSIBLE_UNTIL.exceeds(ReversibilityClass.REVERSIBLE)
    assert not ReversibilityClass.REVERSIBLE_UNTIL.exceeds(
        ReversibilityClass.IRREVERSIBLE
    )


def test_a_class_does_not_exceed_itself() -> None:
    for cls in ReversibilityClass:
        assert not cls.exceeds(cls)


# ======================================================================
# Construction
# ======================================================================


def test_a_warrant_can_be_created() -> None:
    w = warrant()
    assert w.warrant_id == "wrt-1"
    assert w.objective_id == "obj-1"
    assert w.principal_id == "onkar"
    assert w.capability == "Filesystem.WriteFile"
    assert w.attempt_budget == 3


def test_authority_refs_default_to_absent() -> None:
    w = Warrant(
        warrant_id="w",
        objective_id="o",
        principal_id="p",
        capability="C.Do",
        payload_digest="d",
        reversibility_class=ReversibilityClass.READ_ONLY,
        consequence_ceiling=ReversibilityClass.READ_ONLY,
        attempt_budget=1,
        issued_at=ISSUED,
        expires_at=EXPIRES,
    )
    assert w.grant_ref is None
    assert w.rule_ref is None


@pytest.mark.parametrize(
    "field",
    ["warrant_id", "objective_id", "principal_id", "capability", "payload_digest"],
)
@pytest.mark.parametrize("bad", ["", "   "])
def test_every_identifier_is_required(field: str, bad: str) -> None:
    with pytest.raises(InvalidWarrant, match=f"{field} must be a non-empty"):
        warrant(**{field: bad})


def test_a_naive_timestamp_is_refused() -> None:
    """Every moment in Kalpavriksha comes from the canonical clock and is
    aware. A naive one has no defined instant."""
    with pytest.raises(InvalidWarrant, match="timezone-aware"):
        warrant(issued_at=datetime(2026, 8, 5, 12, 0))  # noqa: DTZ001


def test_timestamps_are_normalised_to_utc() -> None:
    """So equality and serialisation do not depend on the caller's zone."""
    ist = timezone(timedelta(hours=5, minutes=30))
    w = warrant(issued_at=ISSUED.astimezone(ist), expires_at=EXPIRES.astimezone(ist))

    assert w.issued_at.tzinfo is UTC
    assert w.issued_at == ISSUED
    assert w == warrant()


def test_a_warrant_expired_at_birth_is_refused() -> None:
    with pytest.raises(InvalidWarrant, match="expires_at must be after issued_at"):
        warrant(expires_at=ISSUED)


@pytest.mark.parametrize("bad", [0, -1])
def test_an_attempt_budget_below_one_is_refused(bad: int) -> None:
    """A warrant permitting no attempt is not an authorization."""
    with pytest.raises(InvalidWarrant, match="at least 1"):
        warrant(attempt_budget=bad)


def test_a_boolean_is_not_an_attempt_budget() -> None:
    """`True == 1` in Python. Accepting it would let `attempt_budget=True`
    silently mean one attempt."""
    with pytest.raises(InvalidWarrant, match="must be an int"):
        warrant(attempt_budget=True)


def test_the_class_must_be_a_reversibility_class() -> None:
    with pytest.raises(InvalidWarrant, match="must be a ReversibilityClass"):
        warrant(reversibility_class="reversible")


# ======================================================================
# Immutability, equality, hashing, serialisation
# ======================================================================


@pytest.mark.parametrize(
    "field", ["warrant_id", "objective_id", "capability", "attempt_budget", "grant_ref"]
)
def test_a_warrant_cannot_be_mutated(field: str) -> None:
    """An authorization editable after the fact would make every receipt
    anchored to it unfalsifiable."""
    with pytest.raises(FrozenInstanceError):
        setattr(warrant(), field, "tampered")


def test_equality_is_deterministic() -> None:
    assert warrant() == warrant()
    assert warrant(warrant_id="wrt-2") != warrant()
    assert warrant(payload_digest="sha256:other") != warrant()


def test_a_warrant_is_hashable() -> None:
    """Frozen and all-hashable, so it can key a lookup or join a set."""
    assert hash(warrant()) == hash(warrant())
    assert len({warrant(), warrant(), warrant(warrant_id="wrt-2")}) == 2


def test_serialisation_is_deterministic() -> None:
    """The same warrant produces an identical dictionary every time, and
    equal warrants produce identical dictionaries — which is what lets a
    receipt written today be compared to one written in five years."""
    assert warrant().as_dict() == warrant().as_dict()
    assert list(warrant().as_dict()) == list(warrant().as_dict())


def test_serialisation_is_json_ready() -> None:
    import json

    payload = json.dumps(warrant().as_dict(), sort_keys=True)
    assert json.loads(payload)["reversibility_class"] == "reversible"
    assert json.loads(payload)["issued_at"] == "2026-08-05T12:00:00+00:00"


def test_serialisation_carries_every_field() -> None:
    """A projection that quietly dropped a field would produce a receipt
    that understates what was authorized."""
    from dataclasses import fields

    assert set(warrant().as_dict()) == {f.name for f in fields(Warrant)}


def test_the_payload_itself_is_never_carried() -> None:
    """The digest, never the payload. A warrant is permanent and payloads
    carry founder data."""
    from dataclasses import fields

    names = {f.name for f in fields(Warrant)}
    assert "payload" not in names
    assert "payload_digest" in names


# ======================================================================
# Expiry
# ======================================================================


def test_a_warrant_is_live_before_it_expires() -> None:
    assert not warrant().is_expired(ISSUED)
    assert not warrant().is_expired(EXPIRES - timedelta(seconds=1))


def test_a_warrant_is_expired_at_and_after_its_deadline() -> None:
    """Expiry is inclusive at the boundary: at `expires_at` the window is
    over, not closing."""
    assert warrant().is_expired(EXPIRES)
    assert warrant().is_expired(EXPIRES + timedelta(seconds=1))


def test_expiry_takes_the_moment_rather_than_reading_a_clock() -> None:
    """A warrant stays a pure value with no dependencies. The caller reads
    the canonical clock once and passes what it said."""
    ist = timezone(timedelta(hours=5, minutes=30))
    assert warrant().is_expired(EXPIRES.astimezone(ist))


def test_expiry_refuses_a_naive_moment() -> None:
    with pytest.raises(InvalidWarrant, match="timezone-aware"):
        warrant().is_expired(datetime(2026, 8, 5, 13, 0))  # noqa: DTZ001


# ======================================================================
# Binding
# ======================================================================


def test_a_warrant_matches_only_what_it_authorized() -> None:
    w = warrant()
    assert w.matches("Filesystem.WriteFile", "sha256:abc")
    assert not w.matches("Filesystem.DeleteFolder", "sha256:abc")
    assert not w.matches("Filesystem.WriteFile", "sha256:tampered")


def test_fired_under_rule_reports_how_authority_arrived() -> None:
    assert not warrant().fired_under_rule
    assert warrant(rule_ref="rule-7").fired_under_rule


# ======================================================================
# CONSTITUTIONAL — three invariants from frozen documents
# ======================================================================


def test_an_action_may_not_exceed_its_objectives_ceiling() -> None:
    """The founder approved a limit at admission. A warrant past it is the
    envelope check failing, and it must be unconstructable rather than
    merely refused somewhere downstream."""
    with pytest.raises(InvalidWarrant, match="exceeds this objective"):
        warrant(
            reversibility_class=ReversibilityClass.IRREVERSIBLE,
            consequence_ceiling=ReversibilityClass.REVERSIBLE,
            attempt_budget=1,
            rule_ref=None,
        )


def test_an_action_at_exactly_the_ceiling_is_allowed() -> None:
    """The ceiling is a limit, not an exclusive bound."""
    assert warrant(
        reversibility_class=ReversibilityClass.REVERSIBLE_UNTIL,
        consequence_ceiling=ReversibilityClass.REVERSIBLE_UNTIL,
    )


def test_an_irreversible_action_gets_exactly_one_attempt() -> None:
    """Kernel Specification §8.4 — *"never automatically retried. Ever."* A
    timed-out payment may have succeeded; retrying is potentially doing it
    twice."""
    with pytest.raises(InvalidWarrant, match="never automatically retried"):
        warrant(
            reversibility_class=ReversibilityClass.IRREVERSIBLE,
            consequence_ceiling=ReversibilityClass.IRREVERSIBLE,
            attempt_budget=2,
        )


def test_no_rule_ever_grants_irreversible_authority() -> None:
    """VEDA 01 §10 Ethics 3 — *"No rule, however broad, ever grants
    irreversible authority."* An irreversible warrant carries a grant and
    no rule."""
    with pytest.raises(InvalidWarrant, match="contemporaneous permission"):
        warrant(
            reversibility_class=ReversibilityClass.IRREVERSIBLE,
            consequence_ceiling=ReversibilityClass.IRREVERSIBLE,
            attempt_budget=1,
            rule_ref="rule-7",
            grant_ref="grant-1",
        )


def test_an_irreversible_warrant_is_valid_when_contemporaneously_granted() -> None:
    w = warrant(
        reversibility_class=ReversibilityClass.IRREVERSIBLE,
        consequence_ceiling=ReversibilityClass.IRREVERSIBLE,
        attempt_budget=1,
        grant_ref="grant-1",
        rule_ref=None,
    )
    assert w.is_irreversible
    assert not w.fired_under_rule


# ======================================================================
# ARCHITECTURE — it proves authorization, it does not perform it
# ======================================================================

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE = REPO_ROOT / "src" / "master_agent" / "foundation" / "warrant.py"

#: Verbs that would mean this record had started acting or deciding.
FORBIDDEN_VERBS = (
    "execute", "run", "invoke", "perform", "dispatch",
    "authorize", "authorise", "grant", "permit", "approve", "deny", "check",
    "mint", "issue", "settle", "revoke", "consume", "start", "stop",
)

#: Packages an authorization record must never reach.
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
    """Behaviour only — methods and properties, never data fields.

    A field cannot do anything, and the criterion here is about behaviour:
    `grant_ref` *references* a grant the Permission System issued, which is
    the opposite of granting one. Checking names without that distinction
    would forbid a warrant from recording what authorized it.
    """
    from dataclasses import fields

    field_names = {f.name for f in fields(Warrant)}
    return [
        name
        for name in dir(Warrant)
        if not name.startswith("_") and name not in field_names
    ]


def test_it_cannot_execute_work() -> None:
    offenders = [
        name
        for name in _public_surface()
        if any(verb in name.lower() for verb in FORBIDDEN_VERBS)
    ]
    assert not offenders, (
        f"Warrant exposes {offenders}, which reads as doing work. It is "
        "evidence of authorization, never the act of authorizing."
    )


def test_it_cannot_authorize_work() -> None:
    """It records a decision the Permission System already made. Nothing
    here evaluates, grants, or revokes."""
    surface = {name.lower() for name in _public_surface()}
    assert not surface & {"authorize", "grant", "permit", "approve", "revoke", "check"}


def test_it_owns_no_objective_state() -> None:
    """The Objective Engine is the single source of truth."""
    w = warrant()
    assert isinstance(w.objective_id, str)
    assert not hasattr(w, "objective")


def test_it_holds_no_runtime_state() -> None:
    """No attempt counter, no status, no result, no progress. Those belong
    to the receipt records the Kernel writes."""
    from dataclasses import fields

    names = {f.name for f in fields(Warrant)}
    forbidden = {
        "attempts_used", "attempt_count", "status", "state", "result",
        "outcome", "progress", "completed", "succeeded", "receipt",
    }
    assert not names & forbidden


def test_it_does_not_reference_an_execution_context() -> None:
    """The dependency runs one way. `ExecutionContext` carries a
    `warrant_id` because execution follows authorization; a warrant
    pointing back would be circular and would name something that does not
    exist when the warrant is minted.

    The Component 3 brief listed `execution_context_id` as a candidate
    field. It cannot exist, and this test is why it is absent rather than
    forgotten.
    """
    from dataclasses import fields

    names = {f.name for f in fields(Warrant)}
    assert not any("context" in name for name in names)


def test_it_reads_no_ambient_time() -> None:
    """Clock injection only. A warrant takes the moment as an argument, so
    it never needs to ask what time it is."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    banned = {"datetime.now", "datetime.utcnow", "datetime.today", "time.time"}
    calls = [
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ".".join(ast.unparse(node.func).split(".")[-2:]) in banned
    ]
    assert not calls, f"warrant.py reads ambient time: {calls}"


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
    assert not offenders, f"warrant.py imports {offenders}"


def test_it_imports_nothing_from_master_agent_at_all() -> None:
    """A warrant is a flat, self-contained record. That is what makes it
    deterministic to serialise and safe to keep forever."""
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
    assert ExportedWarrant is Warrant


def test_components_one_and_two_are_untouched() -> None:
    from master_agent.foundation import clock, execution_context, principal

    assert hasattr(clock, "SystemClock")
    assert hasattr(principal, "PrincipalRegistry")
    assert hasattr(execution_context, "ExecutionContext")
