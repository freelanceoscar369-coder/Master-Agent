"""Sprint 1, Component 9 — Execution Request.

Everything `Kernel.authorize()` needs, assembled by the caller before the
Kernel is asked. Kernel Specification §3.5: `authorize(ExecutionRequest) →
Intent | Refusal`.

The construction tests below enforce that a request cannot be *ambiguous*
— no two answers to one question, no blank identifier, no null quartet —
while deliberately leaving it free to be **incomplete**, because verifying
presence is §7.3's job and a request that could not be incomplete would
make that check dead code.

Every test uses fixed values. Nothing here reads a wall clock; this value
carries no time at all.
"""
from __future__ import annotations

import ast
import json
from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from master_agent.foundation import ExecutionRequest as ExportedExecutionRequest
from master_agent.foundation.attestation import (
    Attestation,
    AttestationQuestion,
    AttestationVerdict,
)
from master_agent.foundation.consequence import Consequence, Cost, CostBasis
from master_agent.foundation.execution_request import (
    PENDING_CONSEQUENCE_ENGINE,
    ActionClass,
    ExecutionRequest,
    InvalidExecutionRequest,
    PendingConsequenceEngine,
)
from master_agent.foundation.warrant import ReversibilityClass

ATTESTED = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)

QUARTET = Consequence(
    what_changes="one folder is removed from the workspace",
    cost=Cost(
        description="no monetary cost",
        basis=CostBasis.FREE,
    ),
    if_nothing="the workspace keeps a folder the founder asked to clear",
    reversibility=ReversibilityClass.REVERSIBLE,
)

PRICED_QUARTET = Consequence(
    what_changes="one reasoning call is made",
    cost=Cost(
        description="one call at the published rate",
        basis=CostBasis.PRICED,
        amount=Decimal(1),
        currency="USD",
    ),
    if_nothing="the question goes unanswered",
    reversibility=ReversibilityClass.REVERSIBLE,
)


def attestation(question: AttestationQuestion, **overrides) -> Attestation:
    defaults = {
        "question": question,
        "attestor": question.canonical_attestor,
        "subject": "Filesystem.DeleteFolder",
        "verdict": AttestationVerdict.SATISFIED,
        "attested_at": ATTESTED,
    }
    return Attestation(**{**defaults, **overrides})


def request(**overrides) -> ExecutionRequest:
    defaults = {
        "objective_id": "obj-001",
        "principal_id": "founder",
        "capability": "Filesystem.DeleteFolder",
        "payload_digest": "sha256:abc123",
        "action_class": ActionClass.LOCAL,
        "reversibility_class": ReversibilityClass.REVERSIBLE,
        "expected_effect": "the folder is gone",
        "consequence": PENDING_CONSEQUENCE_ENGINE,
    }
    return ExecutionRequest(**{**defaults, **overrides})


# ======================================================================
# ActionClass — the two of §7.4
# ======================================================================


def test_there_are_exactly_two_action_classes() -> None:
    """§7.4 defines two attestation sets. A third class is a third
    pipeline, which is a constitutional decision."""
    assert len(ActionClass) == 2


def test_the_action_class_vocabulary_is_closed() -> None:
    assert {c.value for c in ActionClass} == {"local", "intelligence"}


def test_the_action_classes_match_the_attestation_split() -> None:
    """§7.4 — the sets differ by exactly A7 and A8, and C7 already knows
    which those are. C9 must not restate that mapping."""
    intelligence_only = {q for q in AttestationQuestion if q.is_intelligence_only}
    assert intelligence_only == {
        AttestationQuestion.PROVIDER,
        AttestationQuestion.ADMISSION,
    }


# ======================================================================
# PENDING_CONSEQUENCE_ENGINE — §14.1's marker
# ======================================================================


def test_the_marker_exists_and_is_not_none() -> None:
    """§14.1: *"never null, never omitted, and never a partial quartet."*"""
    assert PENDING_CONSEQUENCE_ENGINE is not None
    assert isinstance(PENDING_CONSEQUENCE_ENGINE, PendingConsequenceEngine)


def test_the_marker_is_not_falsy() -> None:
    """A marker that tested false would be indistinguishable from the
    absence it exists to replace."""
    assert PENDING_CONSEQUENCE_ENGINE


def test_the_marker_serialises_to_the_literal_the_spec_names() -> None:
    """§14.1 names the marker verbatim. It must be greppable in a record,
    not only in code."""
    assert PENDING_CONSEQUENCE_ENGINE.as_dict() == "pending_consequence_engine"


def test_the_marker_is_immutable() -> None:
    with pytest.raises(FrozenInstanceError):
        PENDING_CONSEQUENCE_ENGINE.frozen = True  # type: ignore[attr-defined]


def test_the_marker_is_hashable_and_equal_to_itself() -> None:
    assert hash(PENDING_CONSEQUENCE_ENGINE) == hash(PendingConsequenceEngine())
    assert PENDING_CONSEQUENCE_ENGINE == PendingConsequenceEngine()


def test_the_marker_is_not_a_consequence() -> None:
    """It stands in for one. It must never be mistaken for one."""
    assert not isinstance(PENDING_CONSEQUENCE_ENGINE, Consequence)


# ======================================================================
# Construction
# ======================================================================


def test_a_minimal_request_can_be_created() -> None:
    r = request()
    assert r.objective_id == "obj-001"
    assert r.principal_id == "founder"
    assert r.capability == "Filesystem.DeleteFolder"
    assert r.payload_digest == "sha256:abc123"
    assert r.action_class is ActionClass.LOCAL
    assert r.target_ref is None
    assert r.attestations == ()
    assert r.is_consequence_pending


def test_a_full_request_can_be_created() -> None:
    r = request(
        action_class=ActionClass.INTELLIGENCE,
        consequence=PRICED_QUARTET,
        target_ref="D:/workspace/old",
        attestations=(
            attestation(AttestationQuestion.TASK_READY),
            attestation(AttestationQuestion.REVERSIBILITY),
            attestation(AttestationQuestion.PROVIDER),
        ),
    )
    assert r.consequence is PRICED_QUARTET
    assert r.target_ref == "D:/workspace/old"
    assert len(r.attestations) == 3
    assert not r.is_consequence_pending


@pytest.mark.parametrize("action_class", list(ActionClass))
def test_both_action_classes_are_accepted(action_class) -> None:
    assert request(action_class=action_class).action_class is action_class


def test_a_real_quartet_is_accepted():
    assert request(consequence=QUARTET).consequence is QUARTET


# ======================================================================
# Identifier invariants
# ======================================================================


@pytest.mark.parametrize(
    "field", ["objective_id", "principal_id", "capability", "payload_digest"]
)
@pytest.mark.parametrize("bad", ["", "   ", "\n", None, 42])
def test_identifiers_are_required(field, bad) -> None:
    with pytest.raises(InvalidExecutionRequest, match=field):
        request(**{field: bad})


def test_the_objective_id_is_required_because_k1_anchors_on_it() -> None:
    """§7.2 K1 — *"No intent exists without one."*"""
    with pytest.raises(InvalidExecutionRequest, match="objective_id"):
        request(objective_id="")


def test_the_action_class_must_be_an_action_class() -> None:
    with pytest.raises(InvalidExecutionRequest, match="action_class"):
        request(action_class="local")


def test_every_identifier_field_has_no_default() -> None:
    """A request assembled by omission is a request nobody checked."""
    with pytest.raises(TypeError):
        ExecutionRequest(objective_id="obj-001")  # type: ignore[call-arg]


# ======================================================================
# consequence — §14.1
# ======================================================================


def test_the_consequence_is_required() -> None:
    """§14.1 — never omitted."""
    with pytest.raises(TypeError):
        ExecutionRequest(  # type: ignore[call-arg]
            objective_id="obj-001",
            principal_id="founder",
            capability="Filesystem.DeleteFolder",
            payload_digest="sha256:abc123",
            action_class=ActionClass.LOCAL,
        )


def test_a_null_consequence_is_refused() -> None:
    """§14.1 — *"never null."* This is the invariant the roadmap's
    "optional, pending B1" would have broken."""
    with pytest.raises(InvalidExecutionRequest, match="never null"):
        request(consequence=None)


@pytest.mark.parametrize("bad", ["pending", 0, {}, ReversibilityClass.REVERSIBLE])
def test_the_consequence_must_be_a_quartet_or_the_marker(bad) -> None:
    with pytest.raises(InvalidExecutionRequest, match="consequence"):
        request(consequence=bad)


def test_a_pending_consequence_is_reported_as_pending() -> None:
    assert request(consequence=PENDING_CONSEQUENCE_ENGINE).is_consequence_pending


def test_a_real_consequence_is_not_reported_as_pending() -> None:
    assert not request(consequence=QUARTET).is_consequence_pending


# ======================================================================
# target_ref — §4.3 "where meaningful"
# ======================================================================


def test_target_ref_may_be_absent() -> None:
    assert request(target_ref=None).target_ref is None


def test_target_ref_may_be_present() -> None:
    assert request(target_ref="https://example.test").target_ref == "https://example.test"


@pytest.mark.parametrize("blank", ["", "   ", "\n"])
def test_a_blank_target_ref_is_refused(blank) -> None:
    """Absent and blank are different. A blank string is an unanswered
    question wearing an answer."""
    with pytest.raises(InvalidExecutionRequest, match="target_ref"):
        request(target_ref=blank)


def test_a_non_string_target_ref_is_refused() -> None:
    with pytest.raises(InvalidExecutionRequest, match="target_ref"):
        request(target_ref=42)


# ======================================================================
# attestations — incomplete is legal, ambiguous is not
# ======================================================================


def test_a_request_with_no_attestations_is_legal() -> None:
    """§7.3 makes the Kernel verify presence. A request that could not be
    empty would make that check dead code, and §7.5's refusal
    unrecordable."""
    assert request(attestations=()).attestations == ()


def test_a_partially_attested_request_is_legal() -> None:
    """Completeness is the Kernel's judgment, never this value's
    invariant."""
    r = request(attestations=(attestation(AttestationQuestion.PERMISSION),))
    assert len(r.attestations) == 1


def test_a_fully_attested_local_request_is_legal() -> None:
    local = [q for q in AttestationQuestion if not q.is_intelligence_only]
    r = request(attestations=tuple(attestation(q) for q in local))
    assert len(r.attestations) == 6


def test_all_eight_attestations_are_legal() -> None:
    r = request(
        action_class=ActionClass.INTELLIGENCE,
        attestations=tuple(attestation(q) for q in AttestationQuestion),
    )
    assert len(r.attestations) == 8


@pytest.mark.parametrize("question", list(AttestationQuestion))
def test_every_question_may_appear_in_a_request(question) -> None:
    assert request(attestations=(attestation(question),)).attestations[0].question is question


def test_two_answers_to_one_question_are_refused() -> None:
    """§7.3 assigns each question exactly one attestor. The Kernel cannot
    choose between two answers, so two must be unconstructable."""
    with pytest.raises(InvalidExecutionRequest, match="two attestations"):
        request(
            attestations=(
                attestation(AttestationQuestion.PERMISSION),
                attestation(
                    AttestationQuestion.PERMISSION,
                    verdict=AttestationVerdict.REFUSED,
                    reason="no grant",
                ),
            )
        )


def test_two_identical_attestations_are_still_two_answers() -> None:
    a = attestation(AttestationQuestion.RULE)
    with pytest.raises(InvalidExecutionRequest, match="two attestations"):
        request(attestations=(a, a))


def test_a_refused_attestation_may_be_carried() -> None:
    """The Kernel refuses on it; it must be able to arrive. §7.3 — the
    Kernel *"never re-derives the verdict."*"""
    refused = attestation(
        AttestationQuestion.REVERSIBILITY,
        verdict=AttestationVerdict.REFUSED,
        reason="Filesystem.DeleteFolder is unclassified",
    )
    assert request(attestations=(refused,)).attestations[0].verdict is (
        AttestationVerdict.REFUSED
    )


def test_attestations_must_be_a_tuple() -> None:
    with pytest.raises(InvalidExecutionRequest, match="tuple"):
        request(attestations=[attestation(AttestationQuestion.RULE)])


def test_every_attestation_must_be_an_attestation() -> None:
    with pytest.raises(InvalidExecutionRequest, match="Attestation"):
        request(attestations=("permission",))


def test_the_request_does_not_check_the_attestation_set_for_this_class() -> None:
    """§7.4's set selection is the Kernel's. An intelligence request with
    no A7/A8 is malformed to the *Kernel*, not to this value — and the
    Kernel must be free to refuse it and record the refusal."""
    r = request(
        action_class=ActionClass.INTELLIGENCE,
        attestations=(attestation(AttestationQuestion.TASK_READY),),
    )
    assert len(r.attestations) == 1


# ======================================================================
# Value semantics
# ======================================================================


@pytest.mark.parametrize(
    "field",
    [
        "objective_id",
        "principal_id",
        "capability",
        "payload_digest",
        "action_class",
        "consequence",
        "target_ref",
        "attestations",
    ],
)
def test_a_request_cannot_be_mutated(field) -> None:
    r = request()
    with pytest.raises(FrozenInstanceError):
        setattr(r, field, None)


def test_equality_is_deterministic() -> None:
    assert request() == request()


def test_two_requests_differing_in_digest_are_different() -> None:
    """§4.4 — an intent is bound to its `payload_digest`, and the digest is
    checked at `attempt()`. Two payloads are never one request."""
    assert request() != request(payload_digest="sha256:def456")


def test_a_request_is_hashable() -> None:
    assert len({request(), request()}) == 1


def test_a_request_carrying_attestations_is_hashable() -> None:
    r = request(attestations=(attestation(AttestationQuestion.PERMISSION),))
    assert hash(r) == hash(
        request(attestations=(attestation(AttestationQuestion.PERMISSION),))
    )


# ======================================================================
# Serialisation
# ======================================================================


def test_serialisation_is_deterministic() -> None:
    assert request().as_dict() == request().as_dict()


def test_serialisation_is_json_ready() -> None:
    assert json.loads(json.dumps(request().as_dict()))


def test_serialisation_of_a_full_request_is_json_ready() -> None:
    r = request(
        consequence=PRICED_QUARTET,
        target_ref="D:/workspace/old",
        attestations=tuple(attestation(q) for q in AttestationQuestion),
    )
    assert json.loads(json.dumps(r.as_dict()))


def test_serialisation_carries_every_field() -> None:
    r = request(
        target_ref="D:/workspace/old",
        attestations=(attestation(AttestationQuestion.PERMISSION),),
    )
    assert r.as_dict() == {
        "objective_id": "obj-001",
        "principal_id": "founder",
        "capability": "Filesystem.DeleteFolder",
        "payload_digest": "sha256:abc123",
        "action_class": "local",
        "reversibility_class": "reversible",
        "expected_effect": "the folder is gone",
        "consequence": "pending_consequence_engine",
        "target_ref": "D:/workspace/old",
        "attestations": [attestation(AttestationQuestion.PERMISSION).as_dict()],
    }


def test_a_pending_consequence_serialises_to_the_marker() -> None:
    assert request().as_dict()["consequence"] == "pending_consequence_engine"


def test_a_real_consequence_serialises_to_the_quartet() -> None:
    assert request(consequence=QUARTET).as_dict()["consequence"] == QUARTET.as_dict()


def test_serialisation_never_emits_a_null_consequence() -> None:
    """§14.1's whole point: the gap is explicit, never an absence."""
    for consequence in (PENDING_CONSEQUENCE_ENGINE, QUARTET, PRICED_QUARTET):
        assert request(consequence=consequence).as_dict()["consequence"] is not None


# ======================================================================
# reversibility_class and expected_effect — ADR-0022 and ADR-0023 D2
# ======================================================================


@pytest.mark.parametrize("cls", list(ReversibilityClass))
def test_every_reversibility_class_is_accepted(cls) -> None:
    """C4's vocabulary is reused, not restated."""
    assert request(reversibility_class=cls).reversibility_class is cls


@pytest.mark.parametrize("bad", ["reversible", None, 1, ActionClass.LOCAL])
def test_a_non_reversibility_class_is_refused(bad) -> None:
    """There is no default: A2 fails closed on anything unclassified, and a
    defaulted class would be the guess VEDA 04 A2 forbids."""
    with pytest.raises(InvalidExecutionRequest, match="ReversibilityClass"):
        request(reversibility_class=bad)


def test_the_reversibility_class_has_no_default() -> None:
    with pytest.raises(TypeError):
        ExecutionRequest(  # type: ignore[call-arg]
            objective_id="obj-001",
            principal_id="founder",
            capability="Filesystem.DeleteFolder",
            payload_digest="sha256:abc123",
            action_class=ActionClass.LOCAL,
            expected_effect="the folder is gone",
            consequence=PENDING_CONSEQUENCE_ENGINE,
        )


@pytest.mark.parametrize("blank", ["", "   ", "\n"])
def test_a_blank_expected_effect_is_refused(blank) -> None:
    """A step whose completion cannot be checked is the defect Objective
    Engine Spec V2 exists against."""
    with pytest.raises(InvalidExecutionRequest, match="expected_effect"):
        request(expected_effect=blank)


@pytest.mark.parametrize("bad", [None, 42, ["gone"]])
def test_a_non_string_expected_effect_is_refused(bad) -> None:
    with pytest.raises(InvalidExecutionRequest, match="expected_effect"):
        request(expected_effect=bad)


def test_the_expected_effect_is_carried_verbatim() -> None:
    """The founder's words survive into the permanent IntentRecord."""
    words = "  the old workspace folder no longer exists  "
    assert request(expected_effect=words).expected_effect == words


def test_the_two_carried_fields_are_distinct_from_the_ceiling() -> None:
    """ADR-0022: `consequence_ceiling` is the objective's upper bound and
    belongs to the AdmissionRecord. The request carries the action's own
    class, and never the ceiling."""
    names = {f.name for f in fields(ExecutionRequest)}
    assert "reversibility_class" in names
    assert "consequence_ceiling" not in names


# ======================================================================
# CONSTITUTIONAL
# ======================================================================

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE = REPO_ROOT / "src" / "master_agent" / "foundation" / "execution_request.py"

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


def _module_imported_names() -> set[str]:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    return {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and (node.module or "").startswith("master_agent")
        for alias in node.names
    }


def _public_surface() -> list[str]:
    field_names = {f.name for f in fields(ExecutionRequest)}
    return [
        name
        for name in dir(ExecutionRequest)
        if not name.startswith("_") and name not in field_names
    ]


def test_it_has_no_dependency_on_the_principal() -> None:
    """Frozen decision M8: `principal_id: str`, matching the `Warrant` this
    becomes. C9 does not depend on C2."""
    assert not any("principal" in name for name in _module_imports())
    assert "principal_id" in {f.name for f in fields(ExecutionRequest)}
    assert "principal" not in {f.name for f in fields(ExecutionRequest)}


def test_it_carries_no_warrant() -> None:
    """A request becomes a warrant; it does not carry one.

    **ADR-0022 superseded the stricter form of this guard.** It formerly
    asserted no import from `warrant` at all, on the reasoning that
    `ReversibilityClass` is *"attested (A2) rather than the caller
    asserting."* The founder ruled that the request carries the class so
    the Kernel needs no second lookup. The vocabulary is imported; the
    `Warrant` type still is not."""
    assert "Warrant" not in _module_imported_names()
    assert not any("warrant_id" in f.name for f in fields(ExecutionRequest))


def test_it_has_no_dependency_on_the_clock() -> None:
    """`issued_at` and `expires_at` are set by the Kernel at mint (§4.3)."""
    assert not any("clock" in name for name in _module_imports())


def test_it_depends_only_on_components_four_six_and_seven() -> None:
    """C4's `ReversibilityClass` joined the set under ADR-0022."""
    internal = {
        name for name in _module_imports() if name.startswith("master_agent")
    }
    assert internal == {
        "master_agent.foundation.attestation",
        "master_agent.foundation.consequence",
        "master_agent.foundation.warrant",
    }


def test_it_imports_nothing_that_could_act() -> None:
    offenders = [
        name
        for name in _module_imports()
        if any(name.startswith(forbidden) for forbidden in FORBIDDEN_IMPORTS)
    ]
    assert not offenders, f"execution_request.py imports {offenders}"


def test_it_cannot_execute_or_authorize_work() -> None:
    """It is a question. It answers nothing and permits nothing."""
    offenders = [
        name
        for name in _public_surface()
        if any(verb in name.lower() for verb in FORBIDDEN_VERBS)
    ]
    assert not offenders, f"ExecutionRequest exposes {offenders}"


def test_it_never_carries_the_payload() -> None:
    """§4.3 — *"The digest, never the payload."* Payloads carry founder
    data; the ledger is permanent."""
    names = {f.name for f in fields(ExecutionRequest)}
    assert "payload" not in names
    assert "payload_digest" in names
    assert not any(n for n in names if n.endswith("_payload"))


def test_it_holds_no_field_the_kernel_owns() -> None:
    """§4.3 sources these to the Kernel or an attestor at mint. A request
    carrying one would be the caller authorizing itself."""
    names = {f.name for f in fields(ExecutionRequest)}
    kernel_owned = {
        "warrant_id",
        "intent_id",
        "compensating_action",
        "undo_window",
        "consequence_ceiling",
        "grant_ref",
        "rule_ref",
        "attempt_budget",
        "issued_at",
        "expires_at",
        "sequence",
        "decision_ref",
        "task_ref",
    }
    assert not names & kernel_owned


def test_it_holds_no_runtime_state() -> None:
    names = {f.name for f in fields(ExecutionRequest)}
    forbidden = {"status", "state", "result", "outcome", "progress", "retries"}
    assert not names & forbidden


def test_it_owns_no_objective_and_no_mission() -> None:
    """`objective_id` is opaque here. C9 carries the id and never the
    record, which is why it is buildable while C11 is blocked."""
    assert not any("objective" in name for name in _module_imports())
    assert not any("mission" in name for name in _module_imports())
    names = {f.name for f in fields(ExecutionRequest)}
    assert "objective" not in names
    assert not any("mission" in n for n in names)


def test_it_reads_no_ambient_time() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    banned = {"datetime.now", "datetime.utcnow", "datetime.today", "time.time"}
    calls = [
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ".".join(ast.unparse(node.func).split(".")[-2:]) in banned
    ]
    assert not calls, f"execution_request.py reads ambient time: {calls}"


def test_it_learns_nothing() -> None:
    """Kernel Spec §10.3 — learning has no return channel. A request is
    not a place to record anything."""
    assert not any("learning" in name for name in _module_imports())
    offenders = [
        name
        for name in _public_surface()
        if any(w in name.lower() for w in ("learn", "record", "publish", "emit"))
    ]
    assert not offenders, f"ExecutionRequest exposes {offenders}"


def test_it_is_exported_from_the_foundation_package() -> None:
    assert ExportedExecutionRequest is ExecutionRequest


def test_components_one_to_eight_are_untouched() -> None:
    from master_agent.foundation import (
        attestation,
        clock,
        consequence,
        execution_context,
        principal,
        receipt,
        refusal,
        warrant,
    )

    assert hasattr(clock, "SystemClock")
    assert hasattr(principal, "PrincipalRegistry")
    assert hasattr(execution_context, "ExecutionContext")
    assert hasattr(warrant, "Warrant")
    assert hasattr(receipt, "Receipt")
    assert hasattr(consequence, "Consequence")
    assert hasattr(attestation, "Attestation")
    assert hasattr(refusal, "KernelRefusal")
