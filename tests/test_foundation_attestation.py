"""Sprint 1, Component 7 — Attestation.

One component's signed answer to one of the Kernel's eight questions.

Kernel Specification §7.3: *"The Kernel verifies each attestation's
presence, attestor identity, subject match, and freshness. It never
re-derives the verdict."* The construction tests below make one of those
four — attestor identity — impossible to get wrong at all.

Every test uses fixed instants. Nothing here reads a wall clock.
"""
from __future__ import annotations

import ast
import json
from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from master_agent.foundation import Attestation as ExportedAttestation
from master_agent.foundation.attestation import (
    Attestation,
    AttestationQuestion,
    AttestationVerdict,
    InvalidAttestation,
)

ATTESTED = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)


def attestation(**overrides) -> Attestation:
    defaults = {
        "question": AttestationQuestion.REVERSIBILITY,
        "attestor": "reversibility_registry",
        "subject": "Filesystem.WriteFile",
        "verdict": AttestationVerdict.SATISFIED,
        "attested_at": ATTESTED,
    }
    return Attestation(**{**defaults, **overrides})


# ======================================================================
# AttestationQuestion — the eight
# ======================================================================


def test_there_are_exactly_eight_questions() -> None:
    """Kernel Specification §7.3. A ninth is a change to the Kernel's
    precondition set — a constitutional decision, not a code change."""
    assert len(AttestationQuestion) == 8


def test_the_question_vocabulary_is_closed() -> None:
    assert {q.value for q in AttestationQuestion} == {
        "task_ready",
        "reversibility",
        "permission",
        "rule",
        "principal",
        "payload_schema",
        "provider",
        "admission",
    }


def test_every_question_maps_to_the_attestor_veda_assigns_it() -> None:
    """§7.3's table, verbatim. All eight attestors are components."""
    assert {
        q: q.canonical_attestor for q in AttestationQuestion
    } == {
        AttestationQuestion.TASK_READY: "mission_control",
        AttestationQuestion.REVERSIBILITY: "reversibility_registry",
        AttestationQuestion.PERMISSION: "permission_system",
        AttestationQuestion.RULE: "standing_rule_engine",
        AttestationQuestion.PRINCIPAL: "principal_registry",
        AttestationQuestion.PAYLOAD_SCHEMA: "capability_contract",
        AttestationQuestion.PROVIDER: "broker",
        AttestationQuestion.ADMISSION: "broker",
    }


def test_exactly_two_questions_are_intelligence_only() -> None:
    """§7.4: *"The sets differ by two attestations. That is the entire
    difference between the pipelines inside the Kernel."*"""
    intelligence_only = {q for q in AttestationQuestion if q.is_intelligence_only}
    assert intelligence_only == {
        AttestationQuestion.PROVIDER,
        AttestationQuestion.ADMISSION,
    }


def test_the_local_attestation_set_is_the_other_six() -> None:
    local = {q for q in AttestationQuestion if not q.is_intelligence_only}
    assert len(local) == 6
    assert AttestationQuestion.PROVIDER not in local


# ======================================================================
# AttestationVerdict
# ======================================================================


def test_there_are_exactly_two_verdicts() -> None:
    """§7.3: an attestation that is missing, stale, wrongly attributed or
    subject-mismatched *"is treated as absent."* Absence is the lack of an
    attestation, never a value one can carry."""
    assert {v.value for v in AttestationVerdict} == {"satisfied", "refused"}


def test_there_is_no_unknown_verdict() -> None:
    """A third verdict would let a component record uncertainty where the
    Kernel expects an answer, and the Kernel would have to decide what that
    meant."""
    for absent in ("unknown", "absent", "pending", "partial"):
        with pytest.raises(ValueError):
            AttestationVerdict(absent)


# ======================================================================
# Construction
# ======================================================================


def test_a_satisfied_attestation_can_be_created() -> None:
    a = attestation()
    assert a.question is AttestationQuestion.REVERSIBILITY
    assert a.attestor == "reversibility_registry"
    assert a.subject == "Filesystem.WriteFile"
    assert a.is_satisfied
    assert a.reason is None


def test_a_refused_attestation_carries_its_reason() -> None:
    a = attestation(
        verdict=AttestationVerdict.REFUSED,
        reason="capability is unclassified",
    )
    assert not a.is_satisfied
    assert a.reason == "capability is unclassified"


@pytest.mark.parametrize("question", list(AttestationQuestion))
def test_every_question_can_be_attested(question: AttestationQuestion) -> None:
    assert attestation(
        question=question, attestor=question.canonical_attestor
    ).question is question


@pytest.mark.parametrize("field", ["attestor", "subject"])
@pytest.mark.parametrize("bad", ["", "   "])
def test_identifiers_are_required(field: str, bad: str) -> None:
    with pytest.raises(InvalidAttestation, match=f"{field} must be a non-empty"):
        attestation(**{field: bad})


def test_the_question_must_be_an_attestation_question() -> None:
    with pytest.raises(InvalidAttestation, match="must be an AttestationQuestion"):
        attestation(question="reversibility")


def test_the_verdict_must_be_an_attestation_verdict() -> None:
    with pytest.raises(InvalidAttestation, match="must be an AttestationVerdict"):
        attestation(verdict="satisfied")


# ======================================================================
# Attestor identity — §7.3, enforced at construction
# ======================================================================


def test_an_attestation_attributed_to_the_wrong_component_is_refused() -> None:
    """§7.3: *"an attestation whose attestor is wrong... is treated as
    absent."* Making it unconstructable means it can never be verified
    incorrectly, because it can never exist."""
    with pytest.raises(InvalidAttestation, match="is attested by"):
        attestation(
            question=AttestationQuestion.PERMISSION,
            attestor="reversibility_registry",
        )


@pytest.mark.parametrize("question", list(AttestationQuestion))
def test_no_question_accepts_a_foreign_attestor(
    question: AttestationQuestion,
) -> None:
    with pytest.raises(InvalidAttestation, match="not 'impostor'"):
        attestation(question=question, attestor="impostor")


def test_both_broker_questions_accept_the_broker() -> None:
    """A7 and A8 share an attestor. The mapping is one-to-one from question
    to attestor, not the reverse."""
    for question in (AttestationQuestion.PROVIDER, AttestationQuestion.ADMISSION):
        assert attestation(question=question, attestor="broker").attestor == "broker"


def test_a_principal_is_never_an_attestor() -> None:
    """**ED-018.** All eight attestors in §7.3 are components: Mission
    Control, the Reversibility Registry, the Permission System, the
    Standing Rule Engine, the Principal registry, the capability contract,
    and the Broker twice.

    A `Principal` is a human authority — founder or delegate — and is never
    one of them. The `PRINCIPAL` question is attested by the *registry*
    that resolves principals, not by a principal.

    This test exists because the roadmap declared a dependency on
    Component 2 that does not exist, and because conflating component
    identity with human authority is precisely the error Component 2's
    conflict report was written about.
    """
    assert AttestationQuestion.PRINCIPAL.canonical_attestor == "principal_registry"

    for question in AttestationQuestion:
        assert "founder" not in question.canonical_attestor
        assert "delegate" not in question.canonical_attestor


# ======================================================================
# Reason symmetry
# ======================================================================


@pytest.mark.parametrize("blank", [None, "", "   "])
def test_a_refusal_without_a_reason_is_itself_refused(blank) -> None:
    """A refusal that cannot say what failed is not answerable."""
    with pytest.raises(InvalidAttestation, match="requires a reason"):
        attestation(verdict=AttestationVerdict.REFUSED, reason=blank)


def test_a_satisfied_attestation_may_not_carry_a_reason() -> None:
    """So the field cannot drift into a general-purpose note."""
    with pytest.raises(InvalidAttestation, match="only meaningful on a refused"):
        attestation(reason="everything was fine")


# ======================================================================
# Time and freshness
# ======================================================================


def test_a_naive_timestamp_is_refused() -> None:
    with pytest.raises(InvalidAttestation, match="timezone-aware"):
        attestation(attested_at=datetime(2026, 8, 5, 12, 0))  # noqa: DTZ001


def test_timestamps_are_normalised_to_utc() -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    a = attestation(attested_at=ATTESTED.astimezone(ist))

    assert a.attested_at.tzinfo is UTC
    assert a.attested_at == ATTESTED
    assert a == attestation()


def test_a_fresh_attestation_is_not_stale() -> None:
    assert not attestation().is_stale(ATTESTED, timedelta(minutes=5))
    assert not attestation().is_stale(
        ATTESTED + timedelta(minutes=4), timedelta(minutes=5)
    )


def test_an_attestation_exactly_at_the_boundary_is_not_yet_stale() -> None:
    """Staleness begins after the window, not at it — the same boundary
    convention the rest of the foundation uses."""
    assert not attestation().is_stale(
        ATTESTED + timedelta(minutes=5), timedelta(minutes=5)
    )


def test_an_attestation_past_its_window_is_stale() -> None:
    assert attestation().is_stale(
        ATTESTED + timedelta(minutes=5, seconds=1), timedelta(minutes=5)
    )


def test_freshness_takes_the_moment_rather_than_reading_a_clock() -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    assert attestation().is_stale(
        (ATTESTED + timedelta(hours=1)).astimezone(ist), timedelta(minutes=5)
    )


def test_freshness_refuses_a_naive_moment() -> None:
    with pytest.raises(InvalidAttestation, match="timezone-aware"):
        attestation().is_stale(datetime(2026, 8, 5, 13, 0), timedelta(minutes=5))  # noqa: DTZ001


def test_a_negative_max_age_is_refused() -> None:
    """It would make every attestation stale, including one just written —
    a configuration error, not a very strict policy."""
    with pytest.raises(InvalidAttestation, match="must not be negative"):
        attestation().is_stale(ATTESTED, timedelta(seconds=-1))


def test_a_zero_max_age_makes_anything_older_stale() -> None:
    assert not attestation().is_stale(ATTESTED, timedelta(0))
    assert attestation().is_stale(ATTESTED + timedelta(microseconds=1), timedelta(0))


# ======================================================================
# Immutability, equality, hashing, serialisation
# ======================================================================


@pytest.mark.parametrize(
    "field", ["question", "attestor", "subject", "verdict", "attested_at"]
)
def test_an_attestation_cannot_be_mutated(field: str) -> None:
    with pytest.raises(FrozenInstanceError):
        setattr(attestation(), field, "tampered")


def test_equality_is_deterministic() -> None:
    assert attestation() == attestation()
    assert attestation(subject="Filesystem.DeleteFolder") != attestation()


def test_an_attestation_is_hashable() -> None:
    assert hash(attestation()) == hash(attestation())
    assert len({attestation(), attestation(), attestation(subject="other")}) == 2


def test_serialisation_is_deterministic() -> None:
    assert attestation().as_dict() == attestation().as_dict()
    assert list(attestation().as_dict()) == list(attestation().as_dict())


def test_serialisation_is_json_ready() -> None:
    payload = json.loads(json.dumps(attestation().as_dict(), sort_keys=True))
    assert payload["question"] == "reversibility"
    assert payload["verdict"] == "satisfied"
    assert payload["attested_at"] == "2026-08-05T12:00:00+00:00"


def test_serialisation_carries_every_field() -> None:
    assert set(attestation().as_dict()) == {f.name for f in fields(Attestation)}


# ======================================================================
# CONSTITUTIONAL
# ======================================================================

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE = REPO_ROOT / "src" / "master_agent" / "foundation" / "attestation.py"

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
    "master_agent.verification",
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
    field_names = {f.name for f in fields(Attestation)}
    return [
        name
        for name in dir(Attestation)
        if not name.startswith("_") and name not in field_names
    ]


def test_it_has_no_dependency_on_the_warrant() -> None:
    """Frozen integration decision for Component 7: `Warrant` stays
    byte-compatible with `kalpavriksha-s1-c3.0`. The Kernel aggregates
    attestations during authorization; an attestation knows nothing about
    warrants."""
    assert not any("warrant" in name for name in _module_imports())
    assert not any("warrant" in f.name for f in fields(Attestation))


def test_it_has_no_dependency_on_the_principal() -> None:
    """ED-018. The attestor is a component, never a human authority."""
    assert not any("principal" in name for name in _module_imports())


def test_it_imports_nothing_from_master_agent_at_all() -> None:
    """A flat, self-contained record — deterministic to serialise and safe
    to keep forever."""
    internal = {
        name for name in _module_imports() if name.startswith("master_agent")
    }
    assert internal == set()


def test_it_imports_nothing_that_could_act() -> None:
    offenders = [
        name
        for name in _module_imports()
        if any(name.startswith(forbidden) for forbidden in FORBIDDEN_IMPORTS)
    ]
    assert not offenders, f"attestation.py imports {offenders}"


def test_it_cannot_execute_or_authorize_work() -> None:
    """It is evidence that a check was performed. It performs none."""
    offenders = [
        name
        for name in _public_surface()
        if any(verb in name.lower() for verb in FORBIDDEN_VERBS)
    ]
    assert not offenders, f"Attestation exposes {offenders}"


def test_it_holds_no_runtime_state() -> None:
    names = {f.name for f in fields(Attestation)}
    forbidden = {"status", "state", "result", "outcome", "progress", "retries"}
    assert not names & forbidden


def test_it_reads_no_ambient_time() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    banned = {"datetime.now", "datetime.utcnow", "datetime.today", "time.time"}
    calls = [
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ".".join(ast.unparse(node.func).split(".")[-2:]) in banned
    ]
    assert not calls, f"attestation.py reads ambient time: {calls}"


def test_it_is_exported_from_the_foundation_package() -> None:
    assert ExportedAttestation is Attestation


def test_components_one_to_six_are_untouched() -> None:
    from master_agent.foundation import (
        clock,
        consequence,
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
    assert hasattr(consequence, "Consequence")
