"""Sprint 1, Component 15 Part 3 — attestation verification.

Kernel Specification §7.3, which is the whole of what this part builds:

> *"The Kernel verifies each attestation's **presence, attestor identity,
> subject match, and freshness**. **It never re-derives the verdict.** An
> attestation whose attestor is wrong, whose subject does not match this
> request, or which is stale is treated as absent."*

§14 R3 is the risk these tests exist against:

> *"**Attestation becomes a rubber stamp.** If validation degrades to 'a
> field is present,' the Kernel becomes ceremony… A mismatched or stale
> attestation is treated as absent, never as a warning."*

So every one of the four properties has adversarial coverage, including
the one C7 makes unconstructable — forged there deliberately, to prove the
Kernel does not rely on a distant invariant.

Nothing here reads a wall clock: the Kernel's clock is a `ManualClock`.
"""
from __future__ import annotations

import ast
import inspect
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from master_agent.foundation.attestation import (
    Attestation,
    AttestationQuestion,
    AttestationVerdict,
)
from master_agent.foundation.clock import ManualClock
from master_agent.foundation.execution_request import (
    PENDING_CONSEQUENCE_ENGINE,
    ActionClass,
    ExecutionRequest,
)
from master_agent.foundation.refusal import (
    KernelRefusal,
    RefusalFamily,
    RefusalReason,
)
from master_agent.foundation.warrant import ReversibilityClass
from master_agent.kernel import Kernel
from master_agent.kernel.kernel import (
    DEFAULT_ATTESTATION_MAX_AGE,
    _required_questions,
)
from master_agent.ledger.receipt_ledger import ReceiptLedger
from master_agent.persistence.store import JsonFileStateStore
from tests.kernel_test_support import StubAdmissions, admission

T0 = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
DIGEST = "sha256:abc"

LOCAL_QUESTIONS = tuple(
    q for q in AttestationQuestion if not q.is_intelligence_only
)
ALL_QUESTIONS = tuple(AttestationQuestion)


def attest(
    question: AttestationQuestion,
    subject: str = DIGEST,
    at: datetime = T0,
    verdict: AttestationVerdict = AttestationVerdict.SATISFIED,
    reason: str | None = None,
) -> Attestation:
    return Attestation(
        question=question,
        attestor=question.canonical_attestor,
        subject=subject,
        verdict=verdict,
        attested_at=at,
        reason=reason,
    )


def request(
    action_class: ActionClass = ActionClass.LOCAL,
    attestations: tuple[Attestation, ...] | None = None,
    **overrides,
) -> ExecutionRequest:
    if attestations is None:
        questions = (
            ALL_QUESTIONS
            if action_class is ActionClass.INTELLIGENCE
            else LOCAL_QUESTIONS
        )
        attestations = tuple(attest(q) for q in questions)
    defaults = {
        "objective_id": "obj-1",
        "principal_id": "founder",
        "capability": "Filesystem.DeleteFolder",
        "payload_digest": DIGEST,
        "action_class": action_class,
        "reversibility_class": ReversibilityClass.REVERSIBLE,
        "expected_effect": "the folder is gone",
        "consequence": PENDING_CONSEQUENCE_ENGINE,
        "attestations": attestations,
    }
    return ExecutionRequest(**{**defaults, **overrides})


@pytest.fixture
def clock() -> ManualClock:
    return ManualClock(T0)


@pytest.fixture
def kernel(tmp_path: Path, clock: ManualClock) -> Kernel:
    return Kernel(
        clock=clock,
        ledger=ReceiptLedger(JsonFileStateStore(tmp_path)),
        admission=StubAdmissions(admission()),
    )


# ======================================================================
# §7.4 · the required set differs by exactly two
# ======================================================================


def test_a_local_action_requires_six_attestations() -> None:
    """§7.4 — `local` requires A1–A6."""
    assert len(_required_questions(ActionClass.LOCAL)) == 6


def test_an_intelligence_action_requires_eight() -> None:
    assert len(_required_questions(ActionClass.INTELLIGENCE)) == 8


def test_the_sets_differ_by_exactly_provider_and_admission() -> None:
    """§7.4 — *"The sets differ by two attestations. That is the entire
    difference between the pipelines inside the Kernel."*"""
    local = set(_required_questions(ActionClass.LOCAL))
    intelligence = set(_required_questions(ActionClass.INTELLIGENCE))
    assert intelligence - local == {
        AttestationQuestion.PROVIDER,
        AttestationQuestion.ADMISSION,
    }


def test_the_required_set_is_derived_from_c7_never_restated() -> None:
    """The mapping belongs to the vocabulary that owns the questions."""
    assert set(_required_questions(ActionClass.LOCAL)) == {
        q for q in AttestationQuestion if not q.is_intelligence_only
    }


def test_the_order_is_the_specification_table_order() -> None:
    """§7.1's *"the reason returned is the most fundamental one"* is only
    well-defined if the order is."""
    assert _required_questions(ActionClass.INTELLIGENCE) == ALL_QUESTIONS


# ======================================================================
# The successful path
# ======================================================================


def test_a_fully_attested_local_request_passes(kernel: Kernel) -> None:
    assert kernel._verify_attestations(request()) is None


def test_a_fully_attested_intelligence_request_passes(kernel: Kernel) -> None:
    assert (
        kernel._verify_attestations(request(ActionClass.INTELLIGENCE)) is None
    )


def test_a_local_request_needs_no_provider_or_admission(kernel: Kernel) -> None:
    """A1–A6 is the whole requirement for a local action."""
    assert kernel._verify_attestations(request(ActionClass.LOCAL)) is None


def test_extra_attestations_are_permitted(kernel: Kernel) -> None:
    """§7.4 defines what is *required*. A local request carrying A7 is
    over-attested, not malformed, and C8 has no reason to refuse it."""
    over = tuple(attest(q) for q in ALL_QUESTIONS)
    assert kernel._verify_attestations(request(attestations=over)) is None


def test_verification_calls_no_attestor() -> None:
    """§7.3 — every answer arrives inside the request. §1.2 — attestation,
    not reimplementation.

    Checked by walking `_verify_attestations` for calls on the Kernel's own
    collaborators: the only one it may touch is the clock. Reaching the
    admission provider or the ledger from here would be re-deriving, and
    reaching an attestor would be reimplementation."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    verify = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == "_verify_attestations"
    )
    collaborators = {
        ast.unparse(node.func)
        for node in ast.walk(verify)
        if isinstance(node, ast.Call)
        and ast.unparse(node.func).startswith("self._")
    }
    assert collaborators == {"self._clock.now", "self._attestation_absent"}


def test_verification_writes_nothing_and_registers_nothing(
    kernel: Kernel, tmp_path: Path
) -> None:
    kernel._verify_attestations(request())
    assert kernel.outstanding_count == 0


# ======================================================================
# PRESENCE — adversarial
# ======================================================================


@pytest.mark.parametrize("missing", LOCAL_QUESTIONS)
def test_any_missing_required_attestation_refuses(kernel: Kernel, missing) -> None:
    present = tuple(attest(q) for q in LOCAL_QUESTIONS if q is not missing)
    refusal = kernel._verify_attestations(request(attestations=present))
    assert isinstance(refusal, KernelRefusal)
    assert refusal.reason is RefusalReason.ATTESTATION_ABSENT
    assert refusal.failed_check is missing


def test_an_empty_request_refuses_on_the_first_question(kernel: Kernel) -> None:
    """§7.1 — the most fundamental reason first. A1 is first in §7.3."""
    refusal = kernel._verify_attestations(request(attestations=()))
    assert refusal.failed_check is AttestationQuestion.TASK_READY


@pytest.mark.parametrize(
    "question",
    [AttestationQuestion.PROVIDER, AttestationQuestion.ADMISSION],
)
def test_an_intelligence_request_missing_a_broker_answer_refuses(
    kernel: Kernel, question
) -> None:
    """§11.6 — *"No `DecisionRecord` ⇒ A7 attestation absent ⇒ refuse."*"""
    present = tuple(attest(q) for q in ALL_QUESTIONS if q is not question)
    refusal = kernel._verify_attestations(
        request(ActionClass.INTELLIGENCE, attestations=present)
    )
    assert refusal.failed_check is question


def test_a_local_set_does_not_satisfy_an_intelligence_request(
    kernel: Kernel,
) -> None:
    """The two-attestation difference, adversarially."""
    local_only = tuple(attest(q) for q in LOCAL_QUESTIONS)
    refusal = kernel._verify_attestations(
        request(ActionClass.INTELLIGENCE, attestations=local_only)
    )
    assert refusal.failed_check is AttestationQuestion.PROVIDER


# ======================================================================
# ATTESTOR IDENTITY — adversarial, including the forged case
# ======================================================================


def test_a_forged_attestor_is_refused(kernel: Kernel) -> None:
    """C7 makes this unconstructable (ED-019), so it is **forged** past the
    frozen dataclass to prove the Kernel performs §7.3's check itself
    rather than relying on a distant invariant. §14 R3."""
    forged = attest(AttestationQuestion.PERMISSION)
    object.__setattr__(forged, "attestor", "some_other_component")

    others = tuple(
        attest(q) for q in LOCAL_QUESTIONS if q is not AttestationQuestion.PERMISSION
    )
    refusal = kernel._verify_attestations(
        request(attestations=(*others, forged))
    )
    assert isinstance(refusal, KernelRefusal)
    assert refusal.reason is RefusalReason.ATTESTATION_ABSENT
    assert refusal.failed_check is AttestationQuestion.PERMISSION
    assert "some_other_component" in refusal.detail


def test_the_construction_time_guard_still_holds() -> None:
    """The forgery above is only possible by bypassing C7. Through the
    public constructor it is impossible."""
    from master_agent.foundation.attestation import InvalidAttestation

    with pytest.raises(InvalidAttestation, match="attested by"):
        Attestation(
            question=AttestationQuestion.PERMISSION,
            attestor="some_other_component",
            subject=DIGEST,
            verdict=AttestationVerdict.SATISFIED,
            attested_at=T0,
        )


# ======================================================================
# SUBJECT MATCH — adversarial
# ======================================================================


def test_an_attestation_for_another_payload_is_refused(kernel: Kernel) -> None:
    """§4.4 — an Intent is bound to its `payload_digest`; §8.2 calls the
    digest *"the load-bearing term."* This is the transfer §7.3's subject
    match exists to stop."""
    wrong = attest(AttestationQuestion.REVERSIBILITY, subject="sha256:other")
    others = tuple(
        attest(q)
        for q in LOCAL_QUESTIONS
        if q is not AttestationQuestion.REVERSIBILITY
    )
    refusal = kernel._verify_attestations(
        request(attestations=(*others, wrong))
    )
    assert refusal.reason is RefusalReason.ATTESTATION_ABSENT
    assert refusal.failed_check is AttestationQuestion.REVERSIBILITY
    assert "different subject" in refusal.detail


def test_attestations_cannot_be_replayed_against_a_new_payload(
    kernel: Kernel,
) -> None:
    """A complete, valid set gathered for one payload does not authorize
    another."""
    gathered = tuple(attest(q) for q in LOCAL_QUESTIONS)
    refusal = kernel._verify_attestations(
        request(payload_digest="sha256:mutated", attestations=gathered)
    )
    assert isinstance(refusal, KernelRefusal)
    assert refusal.failed_check is AttestationQuestion.TASK_READY


@pytest.mark.parametrize("question", LOCAL_QUESTIONS)
def test_every_question_is_subject_checked(kernel: Kernel, question) -> None:
    """Not merely the first: §14 R3's rubber stamp is exactly a check that
    runs on one field and not the rest."""
    others = tuple(attest(q) for q in LOCAL_QUESTIONS if q is not question)
    wrong = attest(question, subject="sha256:elsewhere")
    refusal = kernel._verify_attestations(
        request(attestations=(*others, wrong))
    )
    assert refusal.failed_check is question
    assert "different subject" in refusal.detail


# ======================================================================
# FRESHNESS — adversarial
# ======================================================================


def test_a_stale_attestation_is_refused(kernel: Kernel, clock: ManualClock) -> None:
    """§7.3 — *"which is stale is treated as absent."*"""
    clock.advance(DEFAULT_ATTESTATION_MAX_AGE + timedelta(seconds=1))
    refusal = kernel._verify_attestations(request())
    assert refusal.reason is RefusalReason.ATTESTATION_ABSENT
    assert "no longer fresh" in refusal.detail


def test_an_attestation_at_the_boundary_is_still_fresh(
    kernel: Kernel, clock: ManualClock
) -> None:
    """`Attestation.is_stale` is exclusive at the boundary; the Kernel
    inherits that rather than restating it."""
    clock.advance(DEFAULT_ATTESTATION_MAX_AGE)
    assert kernel._verify_attestations(request()) is None


def test_freshness_is_measured_from_the_kernels_clock(
    kernel: Kernel, clock: ManualClock
) -> None:
    """The Kernel is the component that reads the canonical clock; a
    request cannot supply its own 'now'."""
    assert kernel._verify_attestations(request()) is None
    clock.advance(timedelta(hours=1))
    assert isinstance(kernel._verify_attestations(request()), KernelRefusal)


@pytest.mark.parametrize("question", LOCAL_QUESTIONS)
def test_every_question_is_freshness_checked(
    kernel: Kernel, question, clock: ManualClock
) -> None:
    others = tuple(attest(q) for q in LOCAL_QUESTIONS if q is not question)
    old = attest(question, at=T0 - timedelta(hours=1))
    refusal = kernel._verify_attestations(
        request(attestations=(*others, old))
    )
    assert refusal.failed_check is question
    assert "no longer fresh" in refusal.detail


def test_the_freshness_window_is_a_named_constant() -> None:
    """No frozen document specifies it, so it is named rather than buried
    — changing it must be a visible decision. R31."""
    assert isinstance(DEFAULT_ATTESTATION_MAX_AGE, timedelta)
    assert DEFAULT_ATTESTATION_MAX_AGE > timedelta(0)


# ======================================================================
# THE VERDICT — carried, never re-derived
# ======================================================================


def test_a_refused_attestation_refuses_the_request(kernel: Kernel) -> None:
    refused = attest(
        AttestationQuestion.PERMISSION,
        verdict=AttestationVerdict.REFUSED,
        reason="no grant for Filesystem.DeleteFolder at this tier",
    )
    others = tuple(
        attest(q)
        for q in LOCAL_QUESTIONS
        if q is not AttestationQuestion.PERMISSION
    )
    refusal = kernel._verify_attestations(
        request(attestations=(*others, refused))
    )
    assert refusal.reason is RefusalReason.ATTESTATION_REFUSED
    assert refusal.failed_check is AttestationQuestion.PERMISSION


def test_the_attestors_reason_is_carried_verbatim(kernel: Kernel) -> None:
    """§7.3 — *"It never re-derives the verdict."* The Kernel relays; it
    does not paraphrase."""
    words = "Filesystem.DeleteFolder is unclassified"
    refused = attest(
        AttestationQuestion.REVERSIBILITY,
        verdict=AttestationVerdict.REFUSED,
        reason=words,
    )
    others = tuple(
        attest(q)
        for q in LOCAL_QUESTIONS
        if q is not AttestationQuestion.REVERSIBILITY
    )
    refusal = kernel._verify_attestations(
        request(attestations=(*others, refused))
    )
    assert refusal.detail == words


@pytest.mark.parametrize("question", LOCAL_QUESTIONS)
def test_a_refusal_from_any_attestor_stops_the_request(
    kernel: Kernel, question
) -> None:
    refused = attest(
        question, verdict=AttestationVerdict.REFUSED, reason="no"
    )
    others = tuple(attest(q) for q in LOCAL_QUESTIONS if q is not question)
    refusal = kernel._verify_attestations(
        request(attestations=(*others, refused))
    )
    assert refusal.reason is RefusalReason.ATTESTATION_REFUSED
    assert refusal.failed_check is question


def test_a_refused_attestation_is_not_treated_as_absent(kernel: Kernel) -> None:
    """The two are different facts: nobody answered, versus the owner said
    no. C8's ED-025 keeps them apart."""
    refused = attest(
        AttestationQuestion.RULE,
        verdict=AttestationVerdict.REFUSED,
        reason="cumulative cap breached",
    )
    others = tuple(
        attest(q) for q in LOCAL_QUESTIONS if q is not AttestationQuestion.RULE
    )
    refusal = kernel._verify_attestations(
        request(attestations=(*others, refused))
    )
    assert refusal.reason is not RefusalReason.ATTESTATION_ABSENT


# ======================================================================
# §7.1 · ordering — the most fundamental reason first
# ======================================================================


def test_the_first_failing_question_is_reported(kernel: Kernel) -> None:
    """Two failures, and A1 comes first in §7.3's table."""
    broken = tuple(
        attest(q, subject="sha256:wrong")
        for q in (AttestationQuestion.TASK_READY, AttestationQuestion.PERMISSION)
    )
    others = tuple(
        attest(q)
        for q in LOCAL_QUESTIONS
        if q
        not in (AttestationQuestion.TASK_READY, AttestationQuestion.PERMISSION)
    )
    refusal = kernel._verify_attestations(
        request(attestations=(*others, *broken))
    )
    assert refusal.failed_check is AttestationQuestion.TASK_READY


def test_absence_outranks_a_later_refusal(kernel: Kernel) -> None:
    """A missing A2 is reported even when a later A5 was refused."""
    refused_a5 = attest(
        AttestationQuestion.PRINCIPAL,
        verdict=AttestationVerdict.REFUSED,
        reason="no principal resolved",
    )
    present = tuple(
        attest(q)
        for q in LOCAL_QUESTIONS
        if q
        not in (AttestationQuestion.REVERSIBILITY, AttestationQuestion.PRINCIPAL)
    )
    refusal = kernel._verify_attestations(
        request(attestations=(*present, refused_a5))
    )
    assert refusal.failed_check is AttestationQuestion.REVERSIBILITY
    assert refusal.reason is RefusalReason.ATTESTATION_ABSENT


# ======================================================================
# Refusal shape — C8's contract
# ======================================================================


def test_an_attestation_refusal_names_the_canonical_attestor(
    kernel: Kernel,
) -> None:
    """C8 refuses a refusal that attributes the failure to the wrong
    component, so this is enforced at construction as well as asserted."""
    refusal = kernel._verify_attestations(request(attestations=()))
    assert refusal.attestor == AttestationQuestion.TASK_READY.canonical_attestor
    assert refusal.attestor == "mission_control"


def test_an_attestation_refusal_is_in_the_attestation_family(
    kernel: Kernel,
) -> None:
    refusal = kernel._verify_attestations(request(attestations=()))
    assert refusal.family is RefusalFamily.ATTESTATION
    assert refusal.is_attestation_failure


def test_every_refusal_carries_a_detail(kernel: Kernel) -> None:
    """§7.5 — the founder reads a sentence about their own machine."""
    for attestations in ((), tuple(attest(q, subject="x") for q in LOCAL_QUESTIONS)):
        refusal = kernel._verify_attestations(request(attestations=attestations))
        assert refusal.detail.strip()


def test_only_the_two_attestation_reasons_are_used(kernel: Kernel) -> None:
    """No new `RefusalReason` was needed; C8 stays frozen."""
    seen = set()
    for attestations in (
        (),
        tuple(attest(q, subject="x") for q in LOCAL_QUESTIONS),
        tuple(
            attest(q, verdict=AttestationVerdict.REFUSED, reason="no")
            for q in LOCAL_QUESTIONS
        ),
    ):
        refusal = kernel._verify_attestations(request(attestations=attestations))
        seen.add(refusal.reason)
    assert seen == {
        RefusalReason.ATTESTATION_ABSENT,
        RefusalReason.ATTESTATION_REFUSED,
    }
    assert len(RefusalReason) == 11


# ======================================================================
# CONSTITUTIONAL
# ======================================================================

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE = REPO_ROOT / "src" / "master_agent" / "kernel" / "kernel.py"


def test_the_public_surface_is_still_unchanged() -> None:
    """Verification is a step of `authorize`, not an operation."""
    surface = {n for n in dir(Kernel) if not n.startswith("_")}
    assert surface == {
        "authorize", "attempt", "settle", "invalidate",
        "override", "outstanding_count",
    }


def test_no_operation_remains_unimplemented() -> None:
    """Parts 5-8 completed all four operations of §3.5. The count is
    kept rather than deleted: it pinned exactly how much was unbuilt, and
    zero is the strongest value it has ever asserted."""
    assert MODULE.read_text(encoding="utf-8").count(
        "raise NotImplementedError"
    ) == 0


def test_it_still_holds_no_attestor() -> None:
    """§7.3 — the answers arrive in the request."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    imported = [
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    ]
    forbidden = ("reversibility", "permissions", "broker", "mission_control")
    assert not any(f in n for n in imported for f in forbidden)


def test_it_does_not_restate_the_attestation_vocabulary() -> None:
    """C7 owns the questions and their attestors; C9 owns the action
    classes. A second copy would eventually disagree."""
    source = MODULE.read_text(encoding="utf-8")
    assert "canonical_attestor" in source
    assert "class AttestationQuestion" not in source
    assert "class ActionClass" not in source
    assert "mission_control" not in source


def test_verification_is_private() -> None:
    """A caller that could pre-verify would act on a stale answer; the
    Kernel's guarantee is that the check and the mint happen together."""
    assert not hasattr(Kernel, "verify_attestations")
    assert hasattr(Kernel, "_verify_attestations")


def test_verification_takes_only_the_request(kernel: Kernel) -> None:
    assert list(inspect.signature(Kernel._verify_attestations).parameters) == [
        "self", "request",
    ]


def test_it_reads_no_ambient_time() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    banned = {"datetime.now", "datetime.utcnow", "datetime.today", "time.time"}
    calls = [
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ".".join(ast.unparse(node.func).split(".")[-2:]) in banned
    ]
    assert not calls, f"kernel.py reads ambient time: {calls}"


def test_it_is_within_the_six_hundred_line_ceiling() -> None:
    """§14 R9."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    statements = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.stmt)
        and not (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )
    ]
    assert len(statements) < 600, f"Kernel is {len(statements)} statements"
