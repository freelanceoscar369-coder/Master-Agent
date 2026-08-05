"""Sprint 1, Component 11 — Admission Record.

The Objective Engine's published statement that an objective is admitted,
live, and bounded by an envelope. Objective Engine Specification §10.2.

`ObjectiveState` is the vocabulary ratified in **ADR-0021** — six values,
permanently separate from Constitution §17's frozen `Mission State`. The
adversarial tests below enforce that separation, the terminal partition,
and §10.3's liveness gate.

Every test uses fixed instants. Nothing here reads a wall clock.
"""
from __future__ import annotations

import ast
import json
from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from master_agent.foundation import AdmissionRecord as ExportedRecord
from master_agent.foundation.admission import (
    AdmissionRecord,
    InvalidAdmissionRecord,
    ObjectiveState,
)
from master_agent.foundation.warrant import ReversibilityClass

DEADLINE = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)

TERMINAL = (
    ObjectiveState.COMPLETED,
    ObjectiveState.FAILED,
    ObjectiveState.SUPERSEDED,
)
NON_TERMINAL = (
    ObjectiveState.WAITING,
    ObjectiveState.READY,
    ObjectiveState.EXECUTING,
)


def record(**overrides) -> AdmissionRecord:
    defaults = {
        "objective_id": "obj-001",
        "state": ObjectiveState.EXECUTING,
        "consequence_ceiling": ReversibilityClass.REVERSIBLE,
        "budget": Decimal("100.00"),
        "deadline": DEADLINE,
        "required_authority": "grant-77",
        "approval_ref": "appr-9",
    }
    return AdmissionRecord(**{**defaults, **overrides})


# ======================================================================
# ObjectiveState — the ratified vocabulary (ADR-0021)
# ======================================================================


def test_there_are_exactly_six_states() -> None:
    """ADR-0021. A seventh is a founder decision, not a code change."""
    assert len(ObjectiveState) == 6


def test_the_vocabulary_is_exactly_what_the_adr_ratified() -> None:
    assert {s.value for s in ObjectiveState} == {
        "waiting",
        "ready",
        "executing",
        "completed",
        "failed",
        "superseded",
    }


@pytest.mark.parametrize(
    "absent", ["draft", "planned", "awaiting_approval", "verifying", "cancelled"]
)
def test_the_mission_states_are_not_reused(absent) -> None:
    """ADR-0021 D1 — a distinct vocabulary, not an extension of the frozen
    Mission state machine. D4 — an unadmitted objective publishes no record
    at all, so there is no `DRAFT`."""
    assert absent not in {s.value for s in ObjectiveState}


def test_it_does_not_import_the_mission_vocabulary() -> None:
    """ADR-0021 D1 — the two vocabularies are permanently separate.

    Checked against the module's actual imports, not its prose: the
    docstring names `Mission State` precisely to record the separation."""
    assert not any(
        "mission" in name.lower() for name in _module_imports()
    )
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert "MissionStatus" not in imported_names


def test_the_two_vocabularies_are_distinct_types() -> None:
    """Sharing a spelling is not a collision: they are members of different
    enums in different modules."""
    from master_agent.mission_manager.mission import MissionStatus

    assert ObjectiveState is not MissionStatus
    assert ObjectiveState.EXECUTING is not MissionStatus.EXECUTING
    assert not isinstance(ObjectiveState.EXECUTING, MissionStatus)


@pytest.mark.parametrize("state", TERMINAL)
def test_terminal_states_report_themselves(state) -> None:
    assert state.is_terminal


@pytest.mark.parametrize("state", NON_TERMINAL)
def test_non_terminal_states_report_themselves(state) -> None:
    assert not state.is_terminal


def test_the_partition_is_complete() -> None:
    assert set(TERMINAL) | set(NON_TERMINAL) == set(ObjectiveState)
    assert not set(TERMINAL) & set(NON_TERMINAL)


def test_superseded_is_terminal() -> None:
    """ADR-0021 D3 — terminal and absolute."""
    assert ObjectiveState.SUPERSEDED.is_terminal


# ======================================================================
# §10.3's liveness gate — only EXECUTING mints
# ======================================================================


def test_only_executing_opens_the_liveness_gate() -> None:
    """§10.3 — *"Non-`EXECUTING` ⇒ no mints."*"""
    minting = {s for s in ObjectiveState if s.is_executing}
    assert minting == {ObjectiveState.EXECUTING}


@pytest.mark.parametrize("state", [ObjectiveState.READY, ObjectiveState.WAITING])
def test_a_live_objective_may_still_mint_nothing(state) -> None:
    """Alive and correctly doing nothing. §8.1 — waiting must not look like
    failure. This is why `is_executing` is not the inverse of
    `is_terminal`."""
    assert not state.is_terminal
    assert not state.is_executing


@pytest.mark.parametrize("state", TERMINAL)
def test_a_terminal_objective_never_mints(state) -> None:
    assert not state.is_executing


def test_the_two_questions_are_different() -> None:
    live = {s for s in ObjectiveState if not s.is_terminal}
    minting = {s for s in ObjectiveState if s.is_executing}
    assert minting < live


# ======================================================================
# Construction
# ======================================================================


def test_a_record_can_be_created() -> None:
    r = record()
    assert r.objective_id == "obj-001"
    assert r.state is ObjectiveState.EXECUTING
    assert r.consequence_ceiling is ReversibilityClass.REVERSIBLE
    assert r.budget == Decimal("100.00")
    assert r.deadline == DEADLINE
    assert r.required_authority == "grant-77"
    assert r.approval_ref == "appr-9"


@pytest.mark.parametrize("state", list(ObjectiveState))
def test_every_state_can_be_published(state) -> None:
    assert record(state=state).state is state


@pytest.mark.parametrize("ceiling", list(ReversibilityClass))
def test_every_ceiling_can_be_published(ceiling) -> None:
    """§10.4 — the ceiling is the highest class any warrant may carry."""
    assert record(consequence_ceiling=ceiling).consequence_ceiling is ceiling


def test_the_record_reports_its_states_questions() -> None:
    assert record(state=ObjectiveState.EXECUTING).is_executing
    assert not record(state=ObjectiveState.READY).is_executing
    assert record(state=ObjectiveState.SUPERSEDED).is_terminal
    assert not record(state=ObjectiveState.WAITING).is_terminal


def test_every_envelope_field_is_required() -> None:
    """§10.3 — the Kernel refuses a warrant exceeding any of the three. A
    record missing one describes an envelope with a side missing."""
    with pytest.raises(TypeError):
        AdmissionRecord(  # type: ignore[call-arg]
            objective_id="obj-001",
            state=ObjectiveState.READY,
            consequence_ceiling=ReversibilityClass.REVERSIBLE,
        )


# ======================================================================
# Adversarial — invalid ObjectiveState
# ======================================================================


@pytest.mark.parametrize(
    "bad", ["executing", "EXECUTING", None, 3, ReversibilityClass.REVERSIBLE]
)
def test_a_non_objective_state_is_refused(bad) -> None:
    with pytest.raises(InvalidAdmissionRecord, match="ObjectiveState"):
        record(state=bad)


def test_a_mission_status_is_refused_as_a_state() -> None:
    """ADR-0021 D1 enforced at construction: the Mission vocabulary cannot
    be published as an objective's state."""
    from master_agent.mission_manager.mission import MissionStatus

    with pytest.raises(InvalidAdmissionRecord, match="separate vocabulary"):
        record(state=MissionStatus.EXECUTING)


@pytest.mark.parametrize("retired", ["draft", "verifying", "cancelled"])
def test_a_retired_lifecycle_name_cannot_be_published(retired) -> None:
    """Passing a string that was a Mission state is refused — the record
    accepts only the ratified enum."""
    with pytest.raises(InvalidAdmissionRecord, match="ObjectiveState"):
        record(state=retired)


# ======================================================================
# Adversarial — identifiers, budget, deadline, ceiling
# ======================================================================


@pytest.mark.parametrize(
    "field", ["objective_id", "required_authority", "approval_ref"]
)
@pytest.mark.parametrize("bad", ["", "   ", "\n", None, 42])
def test_identifiers_are_required(field, bad) -> None:
    with pytest.raises(InvalidAdmissionRecord, match=field):
        record(**{field: bad})


@pytest.mark.parametrize("bad", ["reversible", None, 1])
def test_a_non_reversibility_class_ceiling_is_refused(bad) -> None:
    with pytest.raises(InvalidAdmissionRecord, match="ReversibilityClass"):
        record(consequence_ceiling=bad)


@pytest.mark.parametrize("bad", [100.0, "100.00", None, 100])
def test_a_non_decimal_budget_is_refused(bad) -> None:
    """A ceiling that drifts is not a ceiling."""
    with pytest.raises(InvalidAdmissionRecord, match="Decimal"):
        record(budget=bad)


def test_a_boolean_budget_is_refused() -> None:
    """`bool` subclasses `int`, and `int` is already refused — but the
    check is explicit so `True` can never read as a budget."""
    with pytest.raises(InvalidAdmissionRecord, match="Decimal"):
        record(budget=True)


def test_a_negative_budget_is_refused() -> None:
    with pytest.raises(InvalidAdmissionRecord, match="negative"):
        record(budget=Decimal(-1))


def test_a_zero_budget_is_permitted() -> None:
    """Explicitly nothing is a legitimate ceiling; it is not the same as
    unbounded, which is unrepresentable here."""
    assert record(budget=Decimal(0)).budget == Decimal(0)


def test_budget_precision_survives() -> None:
    assert record(budget=Decimal("0.01")).budget == Decimal("0.01")


def test_a_naive_deadline_is_refused() -> None:
    with pytest.raises(InvalidAdmissionRecord, match="timezone-aware"):
        record(deadline=datetime(2026, 8, 12, 9, 0))  # noqa: DTZ001


@pytest.mark.parametrize("bad", [None, "2026-08-12T09:00:00Z", 1785000000])
def test_a_non_datetime_deadline_is_refused(bad) -> None:
    with pytest.raises(InvalidAdmissionRecord, match="datetime"):
        record(deadline=bad)


def test_the_deadline_is_normalised_to_utc() -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    r = record(deadline=datetime(2026, 8, 12, 14, 30, tzinfo=ist))
    assert r.deadline.tzinfo is UTC
    assert r.deadline == DEADLINE


# ======================================================================
# Immutability, equality, hashing
# ======================================================================


@pytest.mark.parametrize("field", [f.name for f in fields(AdmissionRecord)])
def test_a_record_cannot_be_mutated(field) -> None:
    r = record()
    with pytest.raises(FrozenInstanceError):
        setattr(r, field, None)


def test_the_ceiling_cannot_be_raised_in_place() -> None:
    """§10.4 — raising the ceiling *"requires a new founder approval, never
    a re-derivation."*"""
    r = record(consequence_ceiling=ReversibilityClass.REVERSIBLE)
    with pytest.raises(FrozenInstanceError):
        r.consequence_ceiling = ReversibilityClass.IRREVERSIBLE


def test_the_state_cannot_be_advanced_in_place() -> None:
    """A state change is a new published record, never an edit."""
    r = record(state=ObjectiveState.SUPERSEDED)
    with pytest.raises(FrozenInstanceError):
        r.state = ObjectiveState.EXECUTING


def test_equality_is_deterministic() -> None:
    assert record() == record()


def test_two_records_differing_in_state_are_different() -> None:
    assert record(state=ObjectiveState.READY) != record(
        state=ObjectiveState.EXECUTING
    )


def test_two_records_differing_in_budget_are_different() -> None:
    assert record() != record(budget=Decimal("100.01"))


def test_a_record_is_hashable() -> None:
    assert len({record(), record()}) == 1


def test_records_for_distinct_states_do_not_collapse() -> None:
    assert len({record(state=s) for s in ObjectiveState}) == 6


def test_zone_does_not_affect_equality_or_hash() -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    other = record(deadline=datetime(2026, 8, 12, 14, 30, tzinfo=ist))
    assert record() == other
    assert hash(record()) == hash(other)


# ======================================================================
# Serialization
# ======================================================================


def test_serialisation_is_deterministic() -> None:
    assert record().as_dict() == record().as_dict()


def test_serialisation_is_json_ready() -> None:
    assert json.loads(json.dumps(record().as_dict()))


def test_serialisation_carries_every_field() -> None:
    assert record().as_dict() == {
        "objective_id": "obj-001",
        "state": "executing",
        "consequence_ceiling": "reversible",
        "budget": "100.00",
        "deadline": "2026-08-12T09:00:00+00:00",
        "required_authority": "grant-77",
        "approval_ref": "appr-9",
    }


def test_the_budget_survives_json_as_a_string() -> None:
    """Every JSON number is a float. A budget crossing as a float is a
    budget that drifts."""
    projected = json.loads(json.dumps(record(budget=Decimal("0.10")).as_dict()))
    assert projected["budget"] == "0.10"
    assert Decimal(projected["budget"]) == Decimal("0.10")


def test_serialisation_normalises_the_zone() -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    r = record(deadline=datetime(2026, 8, 12, 14, 30, tzinfo=ist))
    assert r.as_dict()["deadline"] == "2026-08-12T09:00:00+00:00"


@pytest.mark.parametrize("state", list(ObjectiveState))
def test_every_state_serialises_to_its_ratified_spelling(state) -> None:
    assert record(state=state).as_dict()["state"] == state.value


# ======================================================================
# CONSTITUTIONAL
# ======================================================================

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE = REPO_ROOT / "src" / "master_agent" / "foundation" / "admission.py"

FORBIDDEN_VERBS = (
    "execute", "run", "invoke", "perform", "dispatch",
    "authorize", "authorise", "grant", "permit", "approve", "deny",
    "mint", "issue", "settle", "revoke", "start", "stop", "update", "set",
    "admit", "terminate", "supersede",
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
    field_names = {f.name for f in fields(AdmissionRecord)}
    return [
        n
        for n in dir(AdmissionRecord)
        if not n.startswith("_") and n not in field_names
    ]


def test_it_depends_only_on_component_four() -> None:
    """Roadmap §2 C11 and Amendment 001 §5: C4 `ReversibilityClass`."""
    internal = {n for n in _module_imports() if n.startswith("master_agent")}
    assert internal == {"master_agent.foundation.warrant"}


def test_it_has_no_dependency_on_the_clock() -> None:
    assert not any("clock" in n for n in _module_imports())


def test_it_does_not_import_the_objective_engine_or_the_kernel() -> None:
    """§10.1 — the record exists so the Kernel need not import the Engine."""
    assert not any(
        w in n for n in _module_imports() for w in ("objective", "kernel")
    )


def test_it_imports_nothing_that_could_act() -> None:
    forbidden = (
        "master_agent.executor",
        "master_agent.orchestrator",
        "master_agent.permissions",
        "master_agent.runtime",
        "master_agent.plugins",
        "master_agent.broker",
        "master_agent.mission_control",
        "master_agent.mission_manager",
        "master_agent.persistence",
        "master_agent.verification",
        "master_agent.planner",
        "subprocess",
        "socket",
    )
    offenders = [
        n for n in _module_imports() if any(n.startswith(f) for f in forbidden)
    ]
    assert not offenders, f"admission.py imports {offenders}"


def test_it_cannot_execute_admit_or_terminate() -> None:
    """It records that admission happened. It performs none of it — no
    Engine, no service, no workflow."""
    offenders = [
        n for n in _public_surface()
        if any(v in n.lower() for v in FORBIDDEN_VERBS)
    ]
    assert not offenders, f"AdmissionRecord exposes {offenders}"


def test_it_carries_none_of_the_objectives_internals() -> None:
    """§10.1 — the Engine keeps the objective. A Kernel that could read
    these could second-guess admission."""
    names = {f.name for f in fields(AdmissionRecord)}
    assert not names & {
        "statement",
        "outcome_statement",
        "criteria",
        "plan_ref",
        "waiting",
        "supersedes",
        "superseded_by",
        "depends_on",
        "set_id",
        "creator",
    }


def test_it_carries_none_of_the_deliberately_absent_fields() -> None:
    """§5.2 — *"The absences are as load-bearing as the fields."*"""
    names = {f.name for f in fields(AdmissionRecord)}
    assert not names & {
        "progress_percent",
        "priority",
        "assignee",
        "owner",
        "task_count",
        "completed_count",
        "estimated_effort",
        "status_note",
    }


def test_it_has_exactly_the_seven_published_fields() -> None:
    """§10.2 and Roadmap §2 C11, verbatim and in order."""
    assert [f.name for f in fields(AdmissionRecord)] == [
        "objective_id",
        "state",
        "consequence_ceiling",
        "budget",
        "deadline",
        "required_authority",
        "approval_ref",
    ]


def test_it_holds_no_runtime_state() -> None:
    names = {f.name for f in fields(AdmissionRecord)}
    assert not names & {"status", "result", "outcome", "progress", "retries"}


def test_it_does_not_restate_the_reversibility_vocabulary() -> None:
    assert "class ReversibilityClass" not in MODULE.read_text(encoding="utf-8")


def test_it_reads_no_ambient_time() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    banned = {"datetime.now", "datetime.utcnow", "datetime.today", "time.time"}
    calls = [
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ".".join(ast.unparse(node.func).split(".")[-2:]) in banned
    ]
    assert not calls, f"admission.py reads ambient time: {calls}"


def test_it_is_exported_from_the_foundation_package() -> None:
    assert ExportedRecord is AdmissionRecord
