"""Sprint 1, Component 15 Part 4 — K2 and the ordered precondition set.

**K2 · Override state.** Kernel Specification §7.2:

> *"Global suspension is not active. **Why the Kernel:** the Override's
> meaning **is** 'the Kernel stops minting.' No other component can express
> that."*

**§7.4's order**, which §7.1 makes load-bearing rather than incidental:

```
  local        K1 · K2 · A1 A2 A3 A4 A5 A6 · K3
  intelligence K1 · K2 · A1 A2 A3 A4 A5 A6 A7 A8 · K3
```

> *"Checks run cheapest-and-most-fundamental first, so a refusal costs as
> little as possible and the reason returned is the most fundamental one.
> An action with no objective is refused for having no objective, never
> for a budget problem it also had."*

**K3 is not in this part.** `IntentRecord.expected_effect` has no source
the Kernel can reach — see the health report's R35.

Nothing here reads a wall clock.
"""
from __future__ import annotations

import ast
import inspect
from datetime import UTC, datetime
from pathlib import Path

import pytest

from master_agent.foundation.admission import AdmissionRecord, ObjectiveState
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
from master_agent.foundation.override import OverrideSwitch
from master_agent.foundation.refusal import (
    KernelCheck,
    KernelRefusal,
    RefusalFamily,
    RefusalReason,
)
from master_agent.foundation.warrant import ReversibilityClass
from master_agent.kernel import Kernel
from master_agent.ledger.receipt_ledger import ReceiptLedger
from master_agent.persistence.store import JsonFileStateStore
from tests.kernel_test_support import StubAdmissions, admission

T0 = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
DIGEST = "sha256:abc"

LOCAL_QUESTIONS = tuple(
    q for q in AttestationQuestion if not q.is_intelligence_only
)


def attest(question: AttestationQuestion, **overrides) -> Attestation:
    defaults = {
        "question": question,
        "attestor": question.canonical_attestor,
        "subject": DIGEST,
        "verdict": AttestationVerdict.SATISFIED,
        "attested_at": T0,
    }
    return Attestation(**{**defaults, **overrides})


def request(**overrides) -> ExecutionRequest:
    defaults = {
        "objective_id": "obj-1",
        "principal_id": "founder",
        "capability": "Filesystem.DeleteFolder",
        "payload_digest": DIGEST,
        "action_class": ActionClass.LOCAL,
        "reversibility_class": ReversibilityClass.REVERSIBLE,
        "expected_effect": "the folder is gone",
        "consequence": PENDING_CONSEQUENCE_ENGINE,
        "attestations": tuple(attest(q) for q in LOCAL_QUESTIONS),
    }
    return ExecutionRequest(**{**defaults, **overrides})


@pytest.fixture
def kernel(tmp_path: Path) -> Kernel:
    return Kernel(
        clock=ManualClock(T0),
        ledger=ReceiptLedger(JsonFileStateStore(tmp_path)),
        admission=StubAdmissions(admission()),
    )


def suspend(kernel: Kernel, reason: str = "founder override") -> None:
    """Force the Kernel's own switch.

    The Kernel has **no public writer** — suspension arrives through
    `invalidate()`, which is not implemented. Forcing the slot exercises
    K2's branch without inventing an API the specification does not give
    this part.
    """
    object.__setattr__(
        kernel, "_override", OverrideSwitch(suspended=True, reason=reason)
    )


# ======================================================================
# K2 · the check itself
# ======================================================================


def test_a_running_kernel_passes_k2(kernel: Kernel) -> None:
    assert kernel._check_override_state() is None


def test_a_suspended_kernel_refuses(kernel: Kernel) -> None:
    """§7.2 — the Override's meaning **is** *"the Kernel stops minting."*"""
    suspend(kernel)
    refusal = kernel._check_override_state()
    assert isinstance(refusal, KernelRefusal)
    assert refusal.reason is RefusalReason.OVERRIDE_ACTIVE


def test_the_refusal_names_k2(kernel: Kernel) -> None:
    suspend(kernel)
    assert kernel._check_override_state().failed_check is (
        KernelCheck.K2_OVERRIDE_STATE
    )


def test_the_refusal_names_no_attestor(kernel: Kernel) -> None:
    """Amendment 001 M5 — §7.2's three checks are the Kernel's own domain,
    so no attestor was involved."""
    suspend(kernel)
    assert kernel._check_override_state().attestor is None


def test_the_refusal_is_a_kernel_check(kernel: Kernel) -> None:
    suspend(kernel)
    assert kernel._check_override_state().family is RefusalFamily.KERNEL_CHECK


def test_the_refusal_is_remediable(kernel: Kernel) -> None:
    """VEDA 01 §10 — the override is *"never discouraged"*, and resuming is
    one gesture. A suspension that read as irremediable would be a
    revocation of trust the founder cannot undo."""
    suspend(kernel)
    assert kernel._check_override_state().remediable is True


def test_the_founders_words_are_carried_verbatim(kernel: Kernel) -> None:
    """§7.5 — the founder reads a sentence about their own machine. The
    Kernel relays; C20 owns any composition."""
    words = "I don't trust the migration script"
    suspend(kernel, words)
    assert kernel._check_override_state().detail == words


def test_a_thousand_suspended_refusals_are_one_state(kernel: Kernel) -> None:
    """§7.5 — *"a thousand refusals are one state — 'autonomy is suspended;
    1,000 actions are waiting' — not a thousand queue items."*"""
    suspend(kernel)
    refusals = {kernel._check_override_state() for _ in range(1000)}
    assert len(refusals) == 1


def test_k2_reads_nothing_but_its_own_switch(kernel: Kernel) -> None:
    """No request, no admission, no ledger. §7.2 — *"No other component can
    express that."*"""
    assert list(inspect.signature(Kernel._check_override_state).parameters) == [
        "self"
    ]


def test_k2_does_not_mutate_the_switch(kernel: Kernel) -> None:
    """Only deciding stops; the switch itself is `invalidate()`'s."""
    suspend(kernel)
    before = kernel.override
    kernel._check_override_state()
    assert kernel.override is before
    assert kernel.override.is_suspended


def test_k2_writes_nothing_and_registers_nothing(
    kernel: Kernel, tmp_path: Path
) -> None:
    suspend(kernel)
    kernel._check_override_state()
    assert kernel.outstanding_count == 0


# ======================================================================
# §7.4 · the ordered precondition set
# ======================================================================


def test_a_complete_request_passes_every_precondition(kernel: Kernel) -> None:
    """K1 and K2 pass, all six local attestations verify."""
    result = kernel._check_preconditions(request())
    assert isinstance(result, AdmissionRecord)
    assert result.objective_id == "obj-1"


def test_the_admission_record_is_returned_for_the_envelope(
    kernel: Kernel,
) -> None:
    """§10.3 — budget, deadline and consequence_ceiling bound the warrant
    the mint will build. Reading them twice would invite disagreement."""
    result = kernel._check_preconditions(request())
    assert result.consequence_ceiling is not None
    assert result.budget is not None
    assert result.deadline is not None


@pytest.mark.parametrize("state", [ObjectiveState.READY, ObjectiveState.WAITING])
def test_a_non_terminal_objective_still_passes(
    tmp_path: Path, state
) -> None:
    """The Founder Decision superseding ADR-0021 D5: K1 is structural
    admission and does not enforce `EXECUTING`."""
    kernel = Kernel(
        clock=ManualClock(T0),
        ledger=ReceiptLedger(JsonFileStateStore(tmp_path)),
        admission=StubAdmissions(admission(state=state)),
    )
    assert isinstance(kernel._check_preconditions(request()), AdmissionRecord)


# ======================================================================
# §7.1 · ordering — the most fundamental reason wins
# ======================================================================


def test_k1_outranks_k2(kernel: Kernel) -> None:
    """*"An action with no objective is refused for having no objective,
    never for a budget problem it also had."* A suspended Kernel asked
    about an unknown objective refuses for the unknown objective."""
    suspend(kernel)
    refusal = kernel._check_preconditions(request(objective_id="obj-missing"))
    assert refusal.reason is RefusalReason.OBJECTIVE_UNKNOWN
    assert refusal.failed_check is KernelCheck.K1_OBJECTIVE_BINDING


def test_k1_outranks_the_attestations(kernel: Kernel) -> None:
    refusal = kernel._check_preconditions(
        request(objective_id="obj-missing", attestations=())
    )
    assert refusal.reason is RefusalReason.OBJECTIVE_UNKNOWN


def test_k2_outranks_the_attestations(kernel: Kernel) -> None:
    """§7.4 puts K2 before A1. A suspended Kernel does not spend effort
    verifying evidence for an action it will refuse anyway."""
    suspend(kernel)
    refusal = kernel._check_preconditions(request(attestations=()))
    assert refusal.reason is RefusalReason.OVERRIDE_ACTIVE
    assert refusal.failed_check is KernelCheck.K2_OVERRIDE_STATE


def test_every_failure_at_once_reports_k1(kernel: Kernel) -> None:
    """Three simultaneous failures; the most fundamental is reported."""
    suspend(kernel)
    refusal = kernel._check_preconditions(
        request(objective_id="gone", attestations=())
    )
    assert refusal.failed_check is KernelCheck.K1_OBJECTIVE_BINDING


def test_a_terminal_objective_outranks_a_suspension(kernel: Kernel) -> None:
    """K1's refusal is reported even when K2 would also refuse."""
    suspend(kernel)
    kernel._admission._records["obj-1"] = admission(
        state=ObjectiveState.COMPLETED
    )
    refusal = kernel._check_preconditions(request())
    assert refusal.reason is RefusalReason.OBJECTIVE_TERMINAL


def test_the_attestations_are_reached_when_k1_and_k2_pass(
    kernel: Kernel,
) -> None:
    refusal = kernel._check_preconditions(request(attestations=()))
    assert refusal.reason is RefusalReason.ATTESTATION_ABSENT
    assert refusal.failed_check is AttestationQuestion.TASK_READY


def test_a_refused_attestation_is_reached_last(kernel: Kernel) -> None:
    refused = attest(
        AttestationQuestion.PERMISSION,
        verdict=AttestationVerdict.REFUSED,
        reason="no grant at this tier",
    )
    others = tuple(
        attest(q)
        for q in LOCAL_QUESTIONS
        if q is not AttestationQuestion.PERMISSION
    )
    refusal = kernel._check_preconditions(
        request(attestations=(*others, refused))
    )
    assert refusal.reason is RefusalReason.ATTESTATION_REFUSED


def test_the_order_is_k1_then_k2_then_attestations() -> None:
    """Structural: §7.4's order read out of the source, so a reordering
    that passed the behavioural tests by coincidence still fails."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    fn = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == "_check_preconditions"
    )
    calls = [
        ast.unparse(node.func)
        for node in ast.walk(fn)
        if isinstance(node, ast.Call)
        and ast.unparse(node.func).startswith("self._")
    ]
    assert calls == [
        "self._check_objective_binding",
        "self._check_override_state",
        "self._verify_attestations",
    ]


# ======================================================================
# K3 and the mint are deliberately absent
# ======================================================================


def test_the_preconditions_write_nothing_to_the_ledger(
    kernel: Kernel, tmp_path: Path
) -> None:
    """§7.2 K3 *"runs last, after every other check has passed"* — and it
    is not in this part."""
    ledger = kernel._ledger
    kernel._check_preconditions(request())
    kernel._check_preconditions(request(objective_id="gone"))
    assert len(ledger) == 0


def test_the_preconditions_mint_nothing(kernel: Kernel) -> None:
    kernel._check_preconditions(request())
    assert kernel.outstanding_count == 0


def test_no_operation_remains_unimplemented() -> None:
    """Parts 5-8 completed all four operations of §3.5. The count is
    kept rather than deleted: it pinned exactly how much was unbuilt, and
    zero is the strongest value it has ever asserted."""
    assert MODULE.read_text(encoding="utf-8").count(
        "raise NotImplementedError"
    ) == 0


def test_no_k3_check_exists_yet() -> None:
    """Recorded so its absence is deliberate rather than overlooked."""
    assert not hasattr(Kernel, "_check_receipt_intent_write")


# ======================================================================
# CONSTITUTIONAL
# ======================================================================

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE = REPO_ROOT / "src" / "master_agent" / "kernel" / "kernel.py"


def test_the_public_surface_is_still_unchanged() -> None:
    surface = {n for n in dir(Kernel) if not n.startswith("_")}
    assert surface == {
        "authorize", "attempt", "settle", "invalidate",
        "override", "outstanding_count",
    }


def test_no_override_writer_was_added() -> None:
    """§11.8's mechanism is `invalidate()`'s, and stays `invalidate()`'s.

    Part 8 built it and this assertion is unchanged: suspension is reached
    through the one operation §3.5 names, never through a setter beside
    it. C14's `OverrideSwitch.suspend()` returns a new value; the Kernel
    holds it, and exposes no way to write it directly."""
    names = [n for n in dir(Kernel) if not n.startswith("__")]
    assert not any(
        w in n.lower() for n in names for w in ("suspend", "resume")
    )


def test_the_adr_0022_forward_references_are_recorded() -> None:
    """The founder asked for the binding gap to be marked where it will be
    closed, not only in a report."""
    source = MODULE.read_text(encoding="utf-8")
    assert source.count("TODO(ADR-0022)") == 2
    assert "R34" in source


def test_it_reads_no_ambient_time() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    banned = {"datetime.now", "datetime.utcnow", "datetime.today", "time.time"}
    calls = [
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ".".join(ast.unparse(node.func).split(".")[-2:]) in banned
    ]
    assert not calls


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
