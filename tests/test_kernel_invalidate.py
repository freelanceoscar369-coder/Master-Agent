"""Sprint 1, Component 15 Part 8 — `invalidate()`.

The last of §3.5's four operations:

```
  invalidate(scope, reason) → count
      Cancel outstanding unexecuted intents. The Override's mechanism,
      and the only bulk operation. (§11.8)
```

| Source | Requirement |
|---|---|
| §1.3 Five | Suspending autonomy **is** invalidate-every-unexecuted-intent plus refuse-to-mint |
| §3.3 | The Kernel owns the Override switch and the invalidation of outstanding intents |
| §3.5 | The operation, its two parameters, and its return type |
| §4.5 | `invalidate() ── Override ──► INVALIDATED`, a terminal state |
| §7.2 K2 | *"The Override's meaning **is** 'the Kernel stops minting'"* |
| §11.8 | The four steps, in order |
| §13.3 | The outstanding set is what keeps the Kernel's memory bounded |
| VEDA 01 §10 | One gesture, immediately, no confirmation and no persuasion |
| VEDA 04 A3 | Suspension of in-flight *evaluations*, not in-flight *executions* |
| Objective Engine Spec §10.5 | Termination is the same operation at a narrower scope |

Every test names the invariant it proves.
"""
from __future__ import annotations

import ast
import inspect
from datetime import UTC, datetime
from pathlib import Path

import pytest

from master_agent.foundation.admission import AdmissionRecord
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
from master_agent.foundation.override import InvalidOverride, OverrideSwitch
from master_agent.foundation.receipt import ExecutionOutcome, Receipt
from master_agent.foundation.refusal import (
    KernelCheck,
    KernelRefusal,
    RefusalReason,
)
from master_agent.foundation.warrant import ReversibilityClass, Warrant
from master_agent.kernel import (
    SCOPE_ALL,
    AttemptNotAuthorized,
    Kernel,
    NothingToSettle,
)
from master_agent.ledger.receipt_ledger import (
    AttemptRecord,
    IntentRecord,
    ReceiptLedger,
)
from master_agent.persistence.store import JsonFileStateStore
from tests.kernel_test_support import StubAdmissions, admission

MODULE = (
    Path(__file__).resolve().parent.parent
    / "src" / "master_agent" / "kernel" / "kernel.py"
)

T0 = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
DEADLINE = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)
DIGEST = "sha256:abc"
REASON = "founder override"

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
    digest = overrides.get("payload_digest", DIGEST)
    defaults = {
        "objective_id": "obj-1",
        "principal_id": "founder",
        "capability": "Filesystem.DeleteFolder",
        "payload_digest": DIGEST,
        "action_class": ActionClass.LOCAL,
        "reversibility_class": ReversibilityClass.REVERSIBLE,
        "expected_effect": "the folder is gone",
        "consequence": PENDING_CONSEQUENCE_ENGINE,
        "attestations": tuple(
            attest(q, subject=digest) for q in LOCAL_QUESTIONS
        ),
    }
    return ExecutionRequest(**{**defaults, **overrides})


def build(
    tmp_path: Path, *objectives: str
) -> tuple[Kernel, ReceiptLedger, ManualClock, StubAdmissions]:
    records: list[AdmissionRecord] = [
        admission(
            objective_id=objective_id,
            consequence_ceiling=ReversibilityClass.IRREVERSIBLE,
            deadline=DEADLINE,
        )
        for objective_id in (objectives or ("obj-1",))
    ]
    ledger = ReceiptLedger(JsonFileStateStore(tmp_path))
    clock = ManualClock(T0)
    admissions = StubAdmissions(*records)
    kernel = Kernel(clock=clock, ledger=ledger, admission=admissions)
    return kernel, ledger, clock, admissions


def mint(kernel: Kernel, objective_id: str = "obj-1", **overrides) -> Warrant:
    warrant = kernel.authorize(
        request(objective_id=objective_id, **overrides)
    )
    assert isinstance(warrant, Warrant), warrant
    return warrant


def _invalidate_source() -> ast.FunctionDef:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "invalidate":
            return node
    raise AssertionError("kernel.py has no invalidate()")


def _attributes_touched_by_invalidate() -> set[str]:
    return {
        node.attr
        for node in ast.walk(_invalidate_source())
        if isinstance(node, ast.Attribute)
    }


# ======================================================================
# §11.8 step 2 · invalidation after authorize
# ======================================================================


def test_a_minted_unattempted_warrant_is_invalidated(tmp_path: Path) -> None:
    """§11.8 step 2 — *"invalidate every MINTED intent not yet
    attempted."*"""
    kernel, _, _, _ = build(tmp_path)
    warrant = mint(kernel)

    assert kernel.invalidate(SCOPE_ALL, REASON) == 1
    assert not kernel._is_outstanding(warrant.warrant_id)
    assert kernel.outstanding_count == 0


def test_the_count_is_what_was_invalidated(tmp_path: Path) -> None:
    """§3.5 — `invalidate(scope, reason) → count`."""
    kernel, _, _, _ = build(tmp_path)
    for i in range(4):
        mint(kernel, payload_digest=f"sha256:{i}")

    assert kernel.invalidate(SCOPE_ALL, REASON) == 4


def test_invalidating_nothing_returns_zero_and_does_not_object(
    tmp_path: Path,
) -> None:
    """VEDA 01 §10 — *"immediately, with no confirmation dialogue and no
    persuasion."* §3.5 gives this operation a count and no refusal, so an
    Override that reached nothing is still an Override."""
    kernel, _, _, _ = build(tmp_path)
    assert kernel.invalidate(SCOPE_ALL, REASON) == 0
    assert kernel.override.is_suspended


def test_an_invalidated_warrant_is_not_settleable(tmp_path: Path) -> None:
    """§4.5 — INVALIDATED and SETTLED are different terminal states, and
    a warrant reaches only one of them."""
    kernel, _, _, _ = build(tmp_path)
    warrant = mint(kernel)
    kernel.invalidate(SCOPE_ALL, REASON)

    with pytest.raises(NothingToSettle):
        kernel.settle(warrant.warrant_id, ExecutionOutcome.SUCCEEDED)


# ======================================================================
# §11.8 step 1 · suspension, and it is first
# ======================================================================


def test_a_global_invalidation_suspends_autonomy(tmp_path: Path) -> None:
    """§11.8 step 1 — *"Set suspension. K2 now refuses every mint."*"""
    kernel, _, _, _ = build(tmp_path)
    assert not kernel.override.is_suspended

    kernel.invalidate(SCOPE_ALL, REASON)
    assert kernel.override.is_suspended


def test_the_suspension_carries_the_founders_words(tmp_path: Path) -> None:
    """C14 — *"supplied by the caller and carried verbatim; nothing here
    argues, warns, or asks again."*"""
    kernel, _, _, _ = build(tmp_path)
    kernel.invalidate(SCOPE_ALL, "I need to think")
    assert kernel.override.reason == "I need to think"


def test_no_mint_survives_the_suspension(tmp_path: Path) -> None:
    """§7.2 K2 — *"the Override's meaning **is** 'the Kernel stops
    minting.'"* §1.3 Five makes the two halves one operation."""
    kernel, _, _, _ = build(tmp_path)
    kernel.invalidate(SCOPE_ALL, REASON)

    refusal = kernel.authorize(request())
    assert isinstance(refusal, KernelRefusal)
    assert refusal.reason is RefusalReason.OVERRIDE_ACTIVE
    assert refusal.failed_check is KernelCheck.K2_OVERRIDE_STATE
    assert refusal.detail == REASON


def test_suspension_is_set_before_the_sweep(tmp_path: Path) -> None:
    """§11.8's numbering is the guarantee, not a presentation order.

    A mint completing between the two steps would produce a warrant the
    sweep has already passed, surviving an Override meant to reach
    everything. Asserted structurally, because the window it closes is too
    small to observe from outside."""
    source = _invalidate_source()

    suspends = [
        node.lineno
        for node in ast.walk(source)
        if isinstance(node, ast.Attribute) and node.attr == "suspend"
    ]
    removals = [
        node.lineno
        for node in ast.walk(source)
        if isinstance(node, ast.Delete)
    ]
    assert suspends and removals
    assert max(suspends) < min(removals)


def test_a_blank_reason_cannot_silently_suspend(tmp_path: Path) -> None:
    """C14 owns this invariant and the Kernel does not restate it — *"the
    founder is owed a sentence about their own machine, not a silent
    stop."*"""
    kernel, _, _, _ = build(tmp_path)
    mint(kernel)

    with pytest.raises(InvalidOverride):
        kernel.invalidate(SCOPE_ALL, "   ")
    assert not kernel.override.is_suspended
    assert kernel.outstanding_count == 1


# ======================================================================
# §11.8 step 3 · invalidation after attempt
# ======================================================================


def test_an_attempted_warrant_is_never_invalidated(tmp_path: Path) -> None:
    """§11.8 step 3 — *"intents already ATTEMPTING run to settlement — an
    in-flight write cannot be un-written."*"""
    kernel, _, _, _ = build(tmp_path)
    warrant = mint(kernel)
    kernel.attempt(warrant.warrant_id)

    assert kernel.invalidate(SCOPE_ALL, REASON) == 0
    assert kernel._is_outstanding(warrant.warrant_id)


def test_an_attempted_warrant_still_settles_under_an_override(
    tmp_path: Path,
) -> None:
    """*"Run to settlement"* means the settlement actually happens.
    VEDA 04 A3 requires suspension of in-flight **evaluations**, and does
    not require aborting in-flight **executions**."""
    kernel, ledger, _, _ = build(tmp_path)
    warrant = mint(kernel)
    kernel.attempt(warrant.warrant_id)
    kernel.invalidate(SCOPE_ALL, REASON)

    receipt = kernel.settle(warrant.warrant_id, ExecutionOutcome.SUCCEEDED)
    assert isinstance(receipt, Receipt)
    assert ledger.is_settled(warrant.warrant_id)


def test_the_sweep_separates_attempted_from_unattempted(
    tmp_path: Path,
) -> None:
    """The whole of step 2's *"not yet attempted"*, exercised on a mixed
    set rather than on one warrant at a time."""
    kernel, _, _, _ = build(tmp_path)
    untouched = [mint(kernel, payload_digest=f"sha256:cold-{i}") for i in range(3)]
    warm = [mint(kernel, payload_digest=f"sha256:warm-{i}") for i in range(2)]
    for w in warm:
        kernel.attempt(w.warrant_id)

    assert kernel.invalidate(SCOPE_ALL, REASON) == 3
    assert all(not kernel._is_outstanding(w.warrant_id) for w in untouched)
    assert all(kernel._is_outstanding(w.warrant_id) for w in warm)


def test_an_exhausted_warrant_is_still_attempted(tmp_path: Path) -> None:
    """*"Not yet attempted"* is about whether an attempt was opened, never
    about whether budget remains."""
    kernel, _, _, _ = build(tmp_path)
    warrant = mint(kernel)
    for _ in range(warrant.attempt_budget):
        kernel.attempt(warrant.warrant_id)

    assert kernel.invalidate(SCOPE_ALL, REASON) == 0
    assert kernel._is_outstanding(warrant.warrant_id)


# ======================================================================
# Invalidation after settle
# ======================================================================


def test_a_settled_warrant_is_not_invalidated_again(tmp_path: Path) -> None:
    """§4.5 — settlement is terminal, and a terminal warrant has already
    left the outstanding set."""
    kernel, _, _, _ = build(tmp_path)
    warrant = mint(kernel)
    kernel.attempt(warrant.warrant_id)
    kernel.settle(warrant.warrant_id, ExecutionOutcome.SUCCEEDED)

    assert kernel.invalidate(SCOPE_ALL, REASON) == 0


def test_settling_does_not_disturb_a_later_sweep(tmp_path: Path) -> None:
    """One warrant's terminal transition must not consume another's."""
    kernel, _, _, _ = build(tmp_path)
    done = mint(kernel, payload_digest="sha256:done")
    pending = mint(kernel, payload_digest="sha256:pending")
    kernel.attempt(done.warrant_id)
    kernel.settle(done.warrant_id, ExecutionOutcome.SUCCEEDED)

    assert kernel.invalidate(SCOPE_ALL, REASON) == 1
    assert not kernel._is_outstanding(pending.warrant_id)


def test_a_settled_warrants_receipt_survives_an_override(
    tmp_path: Path,
) -> None:
    """§9.1 is append-only at every privilege level. Invalidation is not a
    privilege that reaches evidence."""
    kernel, ledger, _, _ = build(tmp_path)
    warrant = mint(kernel)
    kernel.attempt(warrant.warrant_id)
    receipt = kernel.settle(warrant.warrant_id, ExecutionOutcome.SUCCEEDED)

    kernel.invalidate(SCOPE_ALL, REASON)
    assert ledger.read(warrant.warrant_id)[-1] == receipt


# ======================================================================
# Scope — Objective Engine Specification §10.5
# ======================================================================


def test_an_objective_scope_reaches_only_that_objective(
    tmp_path: Path,
) -> None:
    """§10.5 — *"the same operation the founder's global Override uses, at
    a narrower scope."*"""
    kernel, _, _, _ = build(tmp_path, "obj-1", "obj-2")
    doomed = mint(kernel, "obj-1")
    spared = mint(kernel, "obj-2")

    assert kernel.invalidate("obj-1", "objective cancelled") == 1
    assert not kernel._is_outstanding(doomed.warrant_id)
    assert kernel._is_outstanding(spared.warrant_id)


def test_an_objective_scope_does_not_suspend_the_machine(
    tmp_path: Path,
) -> None:
    """§11.8 attributes suspension to the founder's **global** Override,
    and §10.2 gets *"no new mints"* for a terminated objective from K1
    instead. A cancelled objective must not stop all autonomy."""
    kernel, _, _, _ = build(tmp_path, "obj-1", "obj-2")
    mint(kernel, "obj-1")

    kernel.invalidate("obj-1", "objective cancelled")
    assert not kernel.override.is_suspended
    assert isinstance(kernel.authorize(request(objective_id="obj-2")), Warrant)


def test_an_objective_scope_still_spares_attempted_warrants(
    tmp_path: Path,
) -> None:
    """The narrower scope changes which intents are reached, never step
    3's rule about which are exempt."""
    kernel, _, _, _ = build(tmp_path)
    warrant = mint(kernel)
    kernel.attempt(warrant.warrant_id)

    assert kernel.invalidate("obj-1", "objective cancelled") == 0
    assert kernel._is_outstanding(warrant.warrant_id)


def test_an_unknown_scope_reaches_nothing(tmp_path: Path) -> None:
    """A scope that matches no objective invalidates no intent, and says
    so with a count of zero rather than by guessing at intent."""
    kernel, _, _, _ = build(tmp_path)
    warrant = mint(kernel)

    assert kernel.invalidate("obj-does-not-exist", "typo") == 0
    assert kernel._is_outstanding(warrant.warrant_id)
    assert not kernel.override.is_suspended


def test_the_scope_constant_is_the_only_reserved_value(
    tmp_path: Path,
) -> None:
    """§11.8 shows `scope=all`; §10.5 shows an `objective_id` in the same
    position. Nothing else is special."""
    assert SCOPE_ALL == "all"
    kernel, _, _, _ = build(tmp_path, "all")
    mint(kernel, "all")
    # An objective literally named "all" is unreachable as a narrow scope.
    # Recorded rather than defended against: the collision is in the
    # specification's own vocabulary, not introduced here.
    assert kernel.invalidate("all", REASON) == 1
    assert kernel.override.is_suspended


# ======================================================================
# Duplicate invalidation
# ======================================================================


def test_a_second_invalidation_reaches_nothing(tmp_path: Path) -> None:
    """Idempotent by consequence: the first call emptied the set."""
    kernel, _, _, _ = build(tmp_path)
    mint(kernel)

    assert kernel.invalidate(SCOPE_ALL, REASON) == 1
    assert kernel.invalidate(SCOPE_ALL, REASON) == 0


def test_a_second_invalidation_is_never_refused(tmp_path: Path) -> None:
    """C14 — *"refusing it would be friction on the one gesture VEDA 01
    §10 says must never be discouraged."*"""
    kernel, _, _, _ = build(tmp_path)
    kernel.invalidate(SCOPE_ALL, REASON)

    assert kernel.invalidate(SCOPE_ALL, "and again") == 0
    assert kernel.override.is_suspended


def test_a_second_invalidation_carries_the_newer_reason(
    tmp_path: Path,
) -> None:
    """C14 — *"calling `suspend()` on an already-suspended switch is
    allowed and returns a switch carrying the new reason."*"""
    kernel, _, _, _ = build(tmp_path)
    kernel.invalidate(SCOPE_ALL, "first")
    kernel.invalidate(SCOPE_ALL, "second")
    assert kernel.override.reason == "second"


def test_a_scoped_invalidation_after_a_global_one_changes_nothing(
    tmp_path: Path,
) -> None:
    """Nothing about a narrower scope lifts a suspension."""
    kernel, _, _, _ = build(tmp_path)
    kernel.invalidate(SCOPE_ALL, REASON)
    kernel.invalidate("obj-1", "objective cancelled")
    assert kernel.override.is_suspended


# ======================================================================
# Replay protection
# ======================================================================


def test_an_invalidated_warrant_opens_no_attempt(tmp_path: Path) -> None:
    """§12.1's twelfth guarantee — *"a live, unexpired, **uninvalidated**
    Intent — `attempt()` refuses otherwise."*"""
    kernel, _, _, _ = build(tmp_path)
    warrant = mint(kernel)
    kernel.invalidate(SCOPE_ALL, REASON)

    with pytest.raises(AttemptNotAuthorized, match="not outstanding"):
        kernel.attempt(warrant.warrant_id)


def test_an_invalidated_warrant_cannot_be_replayed_after_a_second_sweep(
    tmp_path: Path,
) -> None:
    """A warrant does not come back because the sweep ran again."""
    kernel, _, _, _ = build(tmp_path)
    warrant = mint(kernel)
    kernel.invalidate(SCOPE_ALL, REASON)
    kernel.invalidate(SCOPE_ALL, REASON)

    with pytest.raises(AttemptNotAuthorized):
        kernel.attempt(warrant.warrant_id)


def test_no_warrant_id_is_ever_reissued(tmp_path: Path) -> None:
    """§4.2 — only `authorize()` mints, and the id comes from a strictly
    increasing clock sequence. An invalidated id cannot be minted again,
    so a replayed token has nothing to match."""
    kernel, _, _, _ = build(tmp_path)
    first = mint(kernel)
    kernel.invalidate("obj-1", "objective cancelled")
    second = mint(kernel, payload_digest="sha256:other")

    assert second.warrant_id != first.warrant_id
    assert not kernel._is_outstanding(first.warrant_id)


def test_the_intent_record_cannot_be_rewritten_after_invalidation(
    tmp_path: Path,
) -> None:
    """C13 — *"an intent is written once and never rewritten."* Nothing
    about invalidation reopens the tree."""
    from master_agent.ledger.receipt_ledger import LedgerIntegrityError

    kernel, ledger, _, _ = build(tmp_path)
    warrant = mint(kernel)
    kernel.invalidate(SCOPE_ALL, REASON)

    with pytest.raises(LedgerIntegrityError):
        ledger.record_intent(
            IntentRecord(
                warrant_id=warrant.warrant_id,
                objective_id=warrant.objective_id,
                principal_id=warrant.principal_id,
                capability=warrant.capability,
                reversibility_class=warrant.reversibility_class,
                expected_effect="a second story about the same intent",
                consequence=PENDING_CONSEQUENCE_ENGINE,
                recorded_at=T0,
            )
        )


# ======================================================================
# Ledger durability — nothing is deleted, and R46 is what is missing
# ======================================================================


def test_invalidation_deletes_no_record(tmp_path: Path) -> None:
    """§4.5 — *"None is a deletion."* The outstanding set is working
    memory; the ledger is evidence, and the two are not the same thing."""
    kernel, ledger, _, _ = build(tmp_path)
    warrant = mint(kernel)
    before = [r.as_dict() for r in ledger.read()]

    kernel.invalidate(SCOPE_ALL, REASON)
    assert [r.as_dict() for r in ledger.read()] == before
    assert ledger.has_intent(warrant.warrant_id)


def test_the_intent_survives_a_ledger_restart_after_invalidation(
    tmp_path: Path,
) -> None:
    """What was authorized stays on the record even though the
    authorization was withdrawn."""
    kernel, _, _, _ = build(tmp_path)
    warrant = mint(kernel)
    kernel.invalidate(SCOPE_ALL, REASON)

    reopened = ReceiptLedger(JsonFileStateStore(tmp_path))
    assert reopened.has_intent(warrant.warrant_id)
    assert not reopened.is_settled(warrant.warrant_id)


def test_invalidation_writes_nothing_at_all(tmp_path: Path) -> None:
    """**R46.** §4.5 requires all six terminal states to be recorded and
    §4.4 names cancellation's as *"a terminal outcome record of kind
    `cancelled`."* No such record exists to write: C13's `RecordKind` is
    closed to intent/attempt/outcome, and the outcome record is C5's
    `Receipt`, which requires an attempt of at least 1 and one of §6.3's
    four execution outcomes.

    Asserted so the gap cannot close by accident and go unnoticed."""
    kernel, ledger, _, _ = build(tmp_path)
    mint(kernel)
    length = len(ledger)

    kernel.invalidate(SCOPE_ALL, REASON)
    assert len(ledger) == length


def test_no_record_type_can_express_an_invalidation() -> None:
    """**R46**, measured against the vocabulary rather than asserted in
    prose. Closing it needs a fourth `RecordKind` or a widened outcome
    vocabulary — both GREEN components this part does not open."""
    from master_agent.ledger.receipt_ledger import RecordKind

    assert {k.value for k in RecordKind} == {"intent", "attempt", "outcome"}
    assert not any(
        "cancel" in o.value or "invalid" in o.value for o in ExecutionOutcome
    )


def test_an_invalidated_warrant_is_not_an_orphan(tmp_path: Path) -> None:
    """§9.5's orphan is *"every expired intent **with attempts** and no
    outcome."* An invalidated warrant has no attempts, so it is not one —
    which is why R46 is a missing record and not a false alarm."""
    kernel, ledger, _, _ = build(tmp_path)
    warrant = mint(kernel)
    kernel.invalidate(SCOPE_ALL, REASON)

    records = ledger.read(warrant.warrant_id)
    assert not any(isinstance(r, AttemptRecord) for r in records)
    assert not any(isinstance(r, Receipt) for r in records)


# ======================================================================
# Outstanding state integrity
# ======================================================================


def test_the_outstanding_count_matches_what_was_left(tmp_path: Path) -> None:
    """§13.3 — the outstanding set is what keeps the Kernel's memory
    bounded, so the sweep must actually empty it."""
    kernel, _, _, _ = build(tmp_path, "obj-1", "obj-2")
    for i in range(3):
        mint(kernel, "obj-1", payload_digest=f"sha256:a{i}")
    for i in range(2):
        mint(kernel, "obj-2", payload_digest=f"sha256:b{i}")

    assert kernel.outstanding_count == 5
    assert kernel.invalidate("obj-1", "objective cancelled") == 3
    assert kernel.outstanding_count == 2


def test_the_attempt_counts_of_survivors_are_untouched(
    tmp_path: Path,
) -> None:
    """A sweep must not spend another warrant's budget."""
    kernel, _, _, _ = build(tmp_path)
    survivor = mint(kernel, payload_digest="sha256:warm")
    mint(kernel, payload_digest="sha256:cold")
    kernel.attempt(survivor.warrant_id)
    kernel.attempt(survivor.warrant_id)

    kernel.invalidate(SCOPE_ALL, REASON)
    assert kernel._attempts[survivor.warrant_id] == 2
    assert kernel.attempt(survivor.warrant_id).attempt_seq == 3


def test_the_surviving_warrant_object_is_unchanged(tmp_path: Path) -> None:
    """§4.4 — *"Nothing mutates an Intent, ever, at any privilege
    level."*"""
    kernel, _, _, _ = build(tmp_path)
    survivor = mint(kernel, payload_digest="sha256:warm")
    kernel.attempt(survivor.warrant_id)
    before = survivor.as_dict()

    kernel.invalidate(SCOPE_ALL, REASON)
    assert kernel._outstanding[survivor.warrant_id] is survivor
    assert survivor.as_dict() == before


def test_an_invalidated_warrant_leaves_no_attempt_count_behind(
    tmp_path: Path,
) -> None:
    """An unattempted warrant has no entry to leave, and the sweep must
    not create one."""
    kernel, _, _, _ = build(tmp_path)
    warrant = mint(kernel)
    kernel.invalidate(SCOPE_ALL, REASON)
    assert warrant.warrant_id not in kernel._attempts


def test_the_kernel_holds_no_new_state() -> None:
    """Invalidation removes state; it adds none. §3.4's table is
    unchanged by Part 8."""
    assert set(Kernel.__slots__) == {
        "_admission", "_attempts", "_clock", "_ledger", "_override",
        "_outstanding",
    }


# ======================================================================
# Deterministic behaviour
# ======================================================================


def test_two_kernels_invalidate_identically(tmp_path: Path) -> None:
    """The property that makes the Kernel verifiable at all, applied to
    the Override."""
    counts = []
    states = []
    for name in ("a", "b"):
        kernel, _, _, _ = build(tmp_path / name)
        for i in range(3):
            mint(kernel, payload_digest=f"sha256:{i}")
        kernel.attempt(mint(kernel, payload_digest="sha256:warm").warrant_id)
        counts.append(kernel.invalidate(SCOPE_ALL, REASON))
        states.append((kernel.override.as_dict(), kernel.outstanding_count))

    assert counts[0] == counts[1] == 3
    assert states[0] == states[1]


def test_invalidation_reads_no_clock(tmp_path: Path) -> None:
    """Nothing is timestamped because nothing is written. A clock read
    here would also consume a sequence and shift the next warrant's
    identity."""
    kernel, _, clock, _ = build(tmp_path)
    mint(kernel)
    before = clock.now()

    kernel.invalidate(SCOPE_ALL, REASON)
    assert clock.now() == before
    assert "_clock" not in _attributes_touched_by_invalidate()


def test_invalidation_reads_no_admission_record(tmp_path: Path) -> None:
    """The scope is matched against the warrant's own `objective_id`.
    Asking the Engine whether an objective is terminal would be K1's
    question, asked at the wrong moment by the wrong operation."""
    kernel, _, _, admissions = build(tmp_path)
    mint(kernel)
    lookups = len(admissions.lookups)

    kernel.invalidate(SCOPE_ALL, REASON)
    assert len(admissions.lookups) == lookups
    assert not _attributes_touched_by_invalidate() & {
        "_admission", "_admission_for"
    }


def test_the_sweep_order_does_not_change_the_result(tmp_path: Path) -> None:
    """The outcome is a set membership question, so the order warrants
    were minted in cannot change which survive."""
    kernel, _, _, _ = build(tmp_path)
    warm = mint(kernel, payload_digest="sha256:warm")
    kernel.attempt(warm.warrant_id)
    cold = mint(kernel, payload_digest="sha256:cold")

    assert kernel.invalidate(SCOPE_ALL, REASON) == 1
    assert kernel._is_outstanding(warm.warrant_id)
    assert not kernel._is_outstanding(cold.warrant_id)


# ======================================================================
# §11.8 step 4 · what invalidation must NOT do
# ======================================================================


def test_invalidation_settles_nothing(tmp_path: Path) -> None:
    """§4.5 gives INVALIDATED and SETTLED different arrows. Writing an
    outcome would claim an attempt that never happened."""
    kernel, ledger, _, _ = build(tmp_path)
    warrant = mint(kernel)
    kernel.invalidate(SCOPE_ALL, REASON)
    assert not ledger.is_settled(warrant.warrant_id)


def test_invalidation_compensates_nothing() -> None:
    """§6.4 — *"Undoing is an action. It is classified, authorized,
    receipted, and minted like any other."* There is no privileged undo
    path, and the Override is not one."""
    touched = _attributes_touched_by_invalidate()
    assert not any("compensat" in name for name in touched)


def test_invalidation_neither_admits_nor_assigns_nor_queues() -> None:
    """§11.8 step 4 — *"Objective Engine keeps admitting. Mission Control
    keeps assigning. Work queues at the Kernel boundary."* All three are
    absences here, and §3.4 names their owners."""
    touched = _attributes_touched_by_invalidate()
    assert not any(
        word in name.lower()
        for name in touched
        for word in ("admit", "assign", "queue", "notify", "publish")
    )


def test_invalidation_never_reaches_the_ledger() -> None:
    """R46 stated structurally: there is no write here to be reviewed
    later as if it were one."""
    assert "_ledger" not in _attributes_touched_by_invalidate()


# ======================================================================
# CONSTITUTIONAL — the surface, and no friction
# ======================================================================


def test_invalidate_takes_a_scope_and_a_reason_and_nothing_else() -> None:
    """§11.8 — *"`invalidate()` has no confirmation parameter in its
    signature, matching VEDA 04's requirement that none exist."*"""
    assert list(inspect.signature(Kernel.invalidate).parameters) == [
        "self", "scope", "reason",
    ]


def test_no_friction_parameter_was_added() -> None:
    """VEDA 04 A3 — no delay, cooldown, grace period or confirmation. Every
    one of those is a job cycle wearing a safety-feature name."""
    forbidden = (
        "confirm", "confirmation", "sure", "acknowledge", "force", "yes",
        "consent", "delay", "cooldown", "grace", "throttle", "retry",
    )
    for param in inspect.signature(Kernel.invalidate).parameters:
        assert not any(word in param.lower() for word in forbidden), param


def test_no_override_writer_sits_beside_the_operation() -> None:
    """§11.8's mechanism is `invalidate()`'s. C14's `suspend()` returns a
    new value; the Kernel holds it and exposes no way to write it."""
    names = [n for n in dir(Kernel) if not n.startswith("__")]
    assert not any(
        word in name.lower() for name in names for word in ("suspend", "resume")
    )


def test_there_is_no_way_to_resume(tmp_path: Path) -> None:
    """**R47.** §3.5's surface is four operations and none of them
    resumes. C14's `OverrideSwitch.resume()` exists and the Kernel reaches
    it from nowhere, so a suspended Kernel stays suspended for the life of
    the process.

    Recorded, not closed: a fifth operation would be a speculative API."""
    kernel, _, _, _ = build(tmp_path)
    kernel.invalidate(SCOPE_ALL, REASON)

    assert "resume" not in inspect.getsource(Kernel)
    assert kernel.override.is_suspended
    assert isinstance(kernel.authorize(request()), KernelRefusal)


def test_the_override_is_still_handed_out_immutable(tmp_path: Path) -> None:
    """A reader cannot lift a suspension by touching what it was
    handed."""
    from dataclasses import FrozenInstanceError

    kernel, _, _, _ = build(tmp_path)
    kernel.invalidate(SCOPE_ALL, REASON)

    assert isinstance(kernel.override, OverrideSwitch)
    with pytest.raises(FrozenInstanceError):
        kernel.override.suspended = False


def test_the_outstanding_collection_is_still_not_handed_out() -> None:
    """§3.3 assigns the Intent lifecycle to the Kernel. The only bulk
    operation must not be joined by a bulk reader."""
    surface = {n for n in dir(Kernel) if not n.startswith("_")}
    assert surface == {
        "authorize", "attempt", "settle", "invalidate",
        "override", "outstanding_count",
    }


def test_the_gaps_are_marked_where_they_are_reached() -> None:
    """R46 and R47 are recorded at the site, not only in a report."""
    source = MODULE.read_text(encoding="utf-8")
    assert "R46" in source
    assert "R47" in source


def test_part_8_still_depends_only_on_foundation_and_the_ledger() -> None:
    """§3.6 — dependency direction is strictly downward."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    internal = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module
        and node.module.startswith("master_agent")
    }
    assert all(
        n.startswith(("master_agent.foundation.", "master_agent.ledger."))
        for n in internal
    ), internal


def test_part_8_stays_within_the_six_hundred_statement_ceiling() -> None:
    """§14 R9 — the budget for the complete Kernel, now that it is
    complete."""
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


def test_there_is_still_no_execute() -> None:
    """§3.5 — *"The Kernel is called; it never calls."* True of all four
    operations, now that all four exist."""
    assert not hasattr(Kernel, "execute")
    assert not any(
        v in n.lower()
        for n in dir(Kernel)
        if not n.startswith("_")
        for v in ("execute", "run", "invoke", "dispatch", "perform")
    )
