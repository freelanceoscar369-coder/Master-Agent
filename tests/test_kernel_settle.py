"""Sprint 1, Component 15 Part 7 — `settle()`.

The last of §3.5's four operations to be built before the Override:

```
  settle(intent_id, Outcome) → Receipt
      Record what happened. Terminal. Publishes. Never mutates the intent.
```

| Source | Requirement |
|---|---|
| §3.5 | The operation, and the one return type it has |
| §4.4 | *"Nothing mutates an Intent, ever, at any privilege level"* |
| §4.5 | SETTLED is terminal, and all six terminal states are recorded |
| §6.3 | Settlement is mandatory, and the four kinds |
| §9.1 | `OutcomeRecord (0..1, terminal)` — and it **is** the `Receipt` |
| §9.2 | *"Every arrow is an identifier, never a copy"* |
| §9.5 | Every settled intent has an outcome; orphans are gaps |
| §11.3 | Ledger unavailable ⇒ fail closed, no buffering |
| §13.3 | The outstanding set is what keeps the Kernel's memory bounded |
| ADR-0023 §6.3 | R29 — the Kernel owns all Receipt metadata |

The clock is a `ManualClock`, so every receipt here is deterministic —
that is the property most of these tests turn on.
"""
from __future__ import annotations

import ast
import inspect
import json
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
from master_agent.foundation.receipt import (
    ExecutionOutcome,
    InvalidReceipt,
    Receipt,
)
from master_agent.foundation.refusal import KernelRefusal
from master_agent.foundation.warrant import ReversibilityClass, Warrant
from master_agent.kernel import AttemptNotAuthorized, Kernel, NothingToSettle
from master_agent.ledger.receipt_ledger import (
    AttemptRecord,
    IntentRecord,
    LedgerIntegrityError,
    LedgerUnavailable,
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


class OutcomeRefusingLedger(ReceiptLedger):
    """A ledger whose store has gone by the time the outcome is written.

    Intents and attempts still land, so settlement can be reached with a
    live warrant that has really been attempted.
    """

    def record_outcome(self, receipt):  # type: ignore[override]
        raise LedgerUnavailable("the receipt ledger could not write: disk gone")


def build(
    tmp_path: Path,
    *,
    ceiling: ReversibilityClass = ReversibilityClass.IRREVERSIBLE,
    deadline: datetime = DEADLINE,
    ledger: ReceiptLedger | None = None,
) -> tuple[Kernel, ReceiptLedger, ManualClock, StubAdmissions]:
    # An empty ReceiptLedger is falsy (`__len__` is 0), so this must be an
    # identity test rather than a truthiness one.
    store = ledger if ledger is not None else ReceiptLedger(
        JsonFileStateStore(tmp_path)
    )
    clock = ManualClock(T0)
    admissions = StubAdmissions(
        admission(consequence_ceiling=ceiling, deadline=deadline)
    )
    kernel = Kernel(clock=clock, ledger=store, admission=admissions)
    return kernel, store, clock, admissions


def attempted(
    tmp_path: Path, *, attempts: int = 1, **kwargs
) -> tuple[Kernel, ReceiptLedger, ManualClock, Warrant]:
    """A Kernel with one warrant that has really been attempted — the
    state settlement is only reachable from."""
    reversibility_class = kwargs.pop(
        "reversibility_class", ReversibilityClass.REVERSIBLE
    )
    kernel, ledger, clock, _ = build(tmp_path, **kwargs)
    warrant = kernel.authorize(request(reversibility_class=reversibility_class))
    assert isinstance(warrant, Warrant), warrant
    for _ in range(attempts):
        assert not isinstance(kernel.attempt(warrant.warrant_id), KernelRefusal)
    return kernel, ledger, clock, warrant


def _settle_source() -> ast.FunctionDef:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "settle":
            return node
    raise AssertionError("kernel.py has no settle()")


def _attributes_touched_by_settle() -> set[str]:
    return {
        node.attr
        for node in ast.walk(_settle_source())
        if isinstance(node, ast.Attribute)
    }


# ======================================================================
# The successful settlement
# ======================================================================


def test_an_attempted_warrant_settles(tmp_path: Path) -> None:
    kernel, _, _, w = attempted(tmp_path)
    receipt = kernel.settle(w.warrant_id, ExecutionOutcome.SUCCEEDED)
    assert isinstance(receipt, Receipt)


def test_the_receipt_carries_the_outcome_it_was_given(tmp_path: Path) -> None:
    """§7.3's discipline applied to settlement: the Kernel records the
    caller's answer and never re-derives it."""
    kernel, _, _, w = attempted(tmp_path)
    receipt = kernel.settle(w.warrant_id, ExecutionOutcome.FAILED)
    assert receipt.outcome is ExecutionOutcome.FAILED


@pytest.mark.parametrize(
    "outcome",
    [
        ExecutionOutcome.SUCCEEDED,
        ExecutionOutcome.FAILED,
        ExecutionOutcome.UNKNOWN,
    ],
)
def test_three_of_the_four_settlement_kinds_are_reachable(
    tmp_path: Path, outcome: ExecutionOutcome
) -> None:
    """§6.3's kinds. `PARTIAL` is the fourth and is not reachable through
    this API — see R43 below, which is why it is excluded here rather than
    quietly omitted."""
    kernel, _, _, w = attempted(tmp_path)
    assert kernel.settle(w.warrant_id, outcome).outcome is outcome


def test_unknown_is_recorded_as_the_honest_answer(tmp_path: Path) -> None:
    """§6.3 — *"`unknown` exists because pretending otherwise is how a
    system double-charges a card."* C5 makes it the one outcome that
    always escalates."""
    kernel, _, _, w = attempted(tmp_path)
    receipt = kernel.settle(w.warrant_id, ExecutionOutcome.UNKNOWN)
    assert receipt.requires_escalation


# ======================================================================
# Every field comes from the warrant, the ledger, or the clock
# ======================================================================


def test_the_receipt_carries_the_warrants_identity(tmp_path: Path) -> None:
    """Nothing is taken from the caller but the outcome, so a settlement
    cannot describe an execution other than the authorized one."""
    kernel, _, _, w = attempted(tmp_path)
    receipt = kernel.settle(w.warrant_id, ExecutionOutcome.SUCCEEDED)

    assert receipt.warrant_id == w.warrant_id
    assert receipt.objective_id == w.objective_id
    assert receipt.principal_id == w.principal_id
    assert receipt.capability == w.capability


def test_the_attempt_count_is_the_warrants_own(tmp_path: Path) -> None:
    """§4.4 — *"One Intent, N attempts, N attempt records, **one outcome
    record**."* The count on the receipt is how many the warrant used."""
    kernel, _, _, w = attempted(tmp_path, attempts=3)
    assert kernel.settle(w.warrant_id, ExecutionOutcome.SUCCEEDED).attempt == 3


def test_started_at_is_the_first_attempts_moment_not_the_mints(
    tmp_path: Path,
) -> None:
    """C5 — *"When it ran."* Not when the warrant was minted: the gap
    between authorization and execution is not execution."""
    kernel, _, clock, _ = build(tmp_path)
    warrant = kernel.authorize(request())
    clock.advance(timedelta(seconds=4))
    kernel.attempt(warrant.warrant_id)

    started = kernel.settle(
        warrant.warrant_id, ExecutionOutcome.SUCCEEDED
    ).started_at
    assert started == T0 + timedelta(seconds=4)
    assert started != warrant.issued_at


def test_started_at_survives_several_attempts(tmp_path: Path) -> None:
    kernel, _, clock, w = attempted(tmp_path)
    clock.advance(timedelta(seconds=2))
    kernel.attempt(w.warrant_id)

    receipt = kernel.settle(w.warrant_id, ExecutionOutcome.SUCCEEDED)
    assert receipt.started_at == T0
    assert receipt.attempt == 2


def test_completed_at_is_the_moment_of_settlement(tmp_path: Path) -> None:
    kernel, _, clock, w = attempted(tmp_path)
    clock.advance(timedelta(seconds=7))
    receipt = kernel.settle(w.warrant_id, ExecutionOutcome.SUCCEEDED)

    assert receipt.completed_at == T0 + timedelta(seconds=7)
    assert receipt.duration == timedelta(seconds=7)


def test_the_receipt_carries_no_detail_and_no_compensation(
    tmp_path: Path,
) -> None:
    """**R44.** `detail` is *"in the caller's words"* and `settle()` has no
    parameter for words. Diagnostic only — C5 states it is *"never
    load-bearing and never read to make a decision"* — so nothing
    constitutional turns on its absence."""
    kernel, _, _, w = attempted(tmp_path)
    receipt = kernel.settle(w.warrant_id, ExecutionOutcome.SUCCEEDED)
    assert receipt.detail is None
    assert receipt.compensation_ref is None


# ======================================================================
# Deterministic receipt generation — ADR-0023 §6.3 / R29
# ======================================================================


def test_the_receipt_id_is_deterministic_and_never_random(
    tmp_path: Path,
) -> None:
    """ADR-0023 §6.4's constraint on `warrant_id`, applied to the receipt:
    no `uuid4()`, no ambient randomness, or the Kernel is unverifiable."""
    kernel, _, _, w = attempted(tmp_path)
    sequence = int(w.warrant_id.removeprefix("wrt-"))
    receipt = kernel.settle(w.warrant_id, ExecutionOutcome.SUCCEEDED)
    assert receipt.receipt_id == f"rcp-{sequence:012d}"


def test_two_kernels_settle_identically(tmp_path: Path) -> None:
    """The property that makes the Kernel verifiable at all."""
    first = attempted(tmp_path / "a")
    second = attempted(tmp_path / "b")

    a = first[0].settle(first[3].warrant_id, ExecutionOutcome.SUCCEEDED)
    b = second[0].settle(second[3].warrant_id, ExecutionOutcome.SUCCEEDED)
    assert a == b
    assert a.as_dict() == b.as_dict()


def test_the_identifiers_are_the_mints_own_derivations(
    tmp_path: Path,
) -> None:
    """The Part 5 health report's §3.1 resolution of **R29**: the receipt
    identifiers are pure functions of data already on the `Warrant`, so
    settlement re-derives them and the mint stores nothing."""
    kernel, _, _, w = attempted(tmp_path)
    sequence = int(w.warrant_id.removeprefix("wrt-"))
    receipt = kernel.settle(w.warrant_id, ExecutionOutcome.SUCCEEDED)

    assert receipt.correlation_id == f"cor-{w.objective_id}"
    assert receipt.trace_id == f"trc-{sequence:012d}"


def test_the_correlation_id_is_shared_across_an_objective(
    tmp_path: Path,
) -> None:
    """C5 — *"the logical unit of work this belonged to. Several
    executions share one."*"""
    kernel, _, _, first = attempted(tmp_path)
    second = kernel.authorize(request(payload_digest="sha256:other"))
    kernel.attempt(second.warrant_id)

    a = kernel.settle(first.warrant_id, ExecutionOutcome.SUCCEEDED)
    b = kernel.settle(second.warrant_id, ExecutionOutcome.SUCCEEDED)
    assert a.correlation_id == b.correlation_id
    assert a.trace_id != b.trace_id
    assert a.receipt_id != b.receipt_id


def test_settling_consumes_no_clock_sequence(tmp_path: Path) -> None:
    """`stamp()` *"consumes a sequence number; `now()` does not."* A
    settlement that spent one would silently shift the next mint's
    identity — the same reason `attempt()` reads `now()`."""
    kernel, _, _, first = attempted(tmp_path)
    kernel.settle(first.warrant_id, ExecutionOutcome.SUCCEEDED)
    second = kernel.authorize(request(payload_digest="sha256:other"))

    def seq(warrant: Warrant) -> int:
        return int(warrant.warrant_id.removeprefix("wrt-"))

    assert seq(second) == seq(first) + 1


def test_the_receipt_is_json_ready_and_stable(tmp_path: Path) -> None:
    kernel, _, _, w = attempted(tmp_path)
    receipt = kernel.settle(w.warrant_id, ExecutionOutcome.SUCCEEDED)
    encoded = json.dumps(receipt.as_dict(), sort_keys=False)
    assert json.loads(encoded)["receipt_id"] == receipt.receipt_id
    assert receipt.as_dict() == receipt.as_dict()


# ======================================================================
# §9.1 · the outcome record, and the ledger's ordering
# ======================================================================


def test_the_receipt_is_the_outcome_record(tmp_path: Path) -> None:
    """C13 — *"The outcome record **is** the shipped `Receipt`. There is no
    second outcome type."*"""
    kernel, ledger, _, w = attempted(tmp_path)
    receipt = kernel.settle(w.warrant_id, ExecutionOutcome.SUCCEEDED)

    assert ledger.is_settled(w.warrant_id)
    assert receipt in ledger.read(w.warrant_id)


def test_the_records_arrive_in_section_nine_ones_order(
    tmp_path: Path,
) -> None:
    """```
       IntentRecord ──┬── AttemptRecord (0..n)
                      └── OutcomeRecord (0..1, terminal)
    ```"""
    kernel, ledger, _, w = attempted(tmp_path, attempts=2)
    kernel.settle(w.warrant_id, ExecutionOutcome.SUCCEEDED)

    kinds = [type(r).__name__ for r in ledger.read(w.warrant_id)]
    assert kinds == ["IntentRecord", "AttemptRecord", "AttemptRecord", "Receipt"]


def test_the_outcome_is_the_last_record_of_its_tree(tmp_path: Path) -> None:
    """§9.1 marks it **terminal**, and terminal means last."""
    kernel, ledger, _, w = attempted(tmp_path, attempts=2)
    kernel.settle(w.warrant_id, ExecutionOutcome.SUCCEEDED)
    assert isinstance(ledger.read(w.warrant_id)[-1], Receipt)


def test_two_objectives_interleave_without_disturbing_each_others_order(
    tmp_path: Path,
) -> None:
    """§13.5 — the ledger needs a total order **per objective**, never
    globally. Two trees may interleave in the store and each still reads
    back in §9.1's order."""
    kernel, ledger, _, first = attempted(tmp_path)
    second = kernel.authorize(request(payload_digest="sha256:other"))
    kernel.attempt(second.warrant_id)
    kernel.settle(first.warrant_id, ExecutionOutcome.SUCCEEDED)
    kernel.settle(second.warrant_id, ExecutionOutcome.FAILED)

    for warrant_id in (first.warrant_id, second.warrant_id):
        kinds = [type(r).__name__ for r in ledger.read(warrant_id)]
        assert kinds == ["IntentRecord", "AttemptRecord", "Receipt"]


def test_the_outcome_survives_a_ledger_restart(tmp_path: Path) -> None:
    """Evidence, not session state."""
    kernel, _, _, w = attempted(tmp_path)
    receipt = kernel.settle(w.warrant_id, ExecutionOutcome.SUCCEEDED)

    reopened = ReceiptLedger(JsonFileStateStore(tmp_path))
    assert reopened.is_settled(w.warrant_id)
    assert reopened.read(w.warrant_id)[-1] == receipt


def test_the_earlier_records_are_untouched_by_settling(tmp_path: Path) -> None:
    """Append-only at every privilege level (§9.1)."""
    kernel, ledger, _, w = attempted(tmp_path, attempts=2)
    before = [
        r.as_dict() for r in ledger.read(w.warrant_id) if not isinstance(r, Receipt)
    ]
    kernel.settle(w.warrant_id, ExecutionOutcome.SUCCEEDED)
    after = [
        r.as_dict() for r in ledger.read(w.warrant_id) if not isinstance(r, Receipt)
    ]
    assert before == after


# ======================================================================
# §4.5 · the lifecycle transition
# ======================================================================


def test_a_settled_warrant_leaves_the_outstanding_set(tmp_path: Path) -> None:
    """§13.3 — the outstanding set is what keeps the Kernel's memory
    bounded, and §4.5 makes SETTLED terminal."""
    kernel, _, _, w = attempted(tmp_path)
    assert kernel.outstanding_count == 1

    kernel.settle(w.warrant_id, ExecutionOutcome.SUCCEEDED)
    assert kernel.outstanding_count == 0
    assert not kernel._is_outstanding(w.warrant_id)


def test_a_settled_warrant_opens_no_further_attempt(tmp_path: Path) -> None:
    """§3.5's *settled* condition, now the Kernel's own gate rather than
    the ledger's — this is what **R42** was recorded against in Part 6."""
    kernel, _, _, w = attempted(tmp_path)
    kernel.settle(w.warrant_id, ExecutionOutcome.SUCCEEDED)

    with pytest.raises(AttemptNotAuthorized):
        kernel.attempt(w.warrant_id)


def test_a_settled_warrant_leaves_no_attempt_count_behind(
    tmp_path: Path,
) -> None:
    """§13's bounded state: the count is lifecycle, and the lifecycle
    ended."""
    kernel, _, _, w = attempted(tmp_path, attempts=2)
    kernel.settle(w.warrant_id, ExecutionOutcome.SUCCEEDED)
    assert w.warrant_id not in kernel._attempts


def test_the_warrant_is_never_mutated_by_settling(tmp_path: Path) -> None:
    """§4.4 — *"Nothing mutates an Intent, ever, at any privilege level.
    State changes are separate append-only records referencing it."*"""
    kernel, _, _, w = attempted(tmp_path)
    before = w.as_dict()
    kernel.settle(w.warrant_id, ExecutionOutcome.SUCCEEDED)
    assert w.as_dict() == before


def test_settling_one_warrant_leaves_the_others_outstanding(
    tmp_path: Path,
) -> None:
    kernel, _, _, first = attempted(tmp_path)
    second = kernel.authorize(request(payload_digest="sha256:other"))
    kernel.attempt(second.warrant_id)

    kernel.settle(first.warrant_id, ExecutionOutcome.SUCCEEDED)
    assert kernel.outstanding_count == 1
    assert kernel._is_outstanding(second.warrant_id)


# ======================================================================
# Impossible states
# ======================================================================


def test_an_unknown_warrant_cannot_be_settled(tmp_path: Path) -> None:
    kernel, _, _, _ = attempted(tmp_path)
    with pytest.raises(NothingToSettle, match="not outstanding"):
        kernel.settle("wrt-000000000999", ExecutionOutcome.SUCCEEDED)


def test_a_warrant_cannot_be_settled_twice(tmp_path: Path) -> None:
    """§9.1 — `OutcomeRecord (0..1, **terminal**)`."""
    kernel, _, _, w = attempted(tmp_path)
    kernel.settle(w.warrant_id, ExecutionOutcome.SUCCEEDED)

    with pytest.raises(NothingToSettle, match="already settled"):
        kernel.settle(w.warrant_id, ExecutionOutcome.FAILED)


def test_a_second_settlement_changes_no_record(tmp_path: Path) -> None:
    """The refusal must not be a rewrite that happened to fail late."""
    kernel, ledger, _, w = attempted(tmp_path)
    kernel.settle(w.warrant_id, ExecutionOutcome.SUCCEEDED)
    before = [r.as_dict() for r in ledger.read(w.warrant_id)]

    with pytest.raises(NothingToSettle):
        kernel.settle(w.warrant_id, ExecutionOutcome.FAILED)
    assert [r.as_dict() for r in ledger.read(w.warrant_id)] == before


def test_an_unattempted_warrant_cannot_be_settled(tmp_path: Path) -> None:
    """`Receipt.attempt` is 1-based and C5 refuses attempt zero, so an
    outcome for a warrant that never ran is unconstructable. §4.5 sends an
    unattempted warrant to EXPIRED or CANCELLED, never to SETTLED."""
    kernel, _, _, _ = build(tmp_path)
    warrant = kernel.authorize(request())

    with pytest.raises(NothingToSettle, match="no attempt"):
        kernel.settle(warrant.warrant_id, ExecutionOutcome.SUCCEEDED)


def test_an_unattempted_warrant_stays_outstanding(tmp_path: Path) -> None:
    """A failed settlement is not a lifecycle transition."""
    kernel, _, _, _ = build(tmp_path)
    warrant = kernel.authorize(request())

    with pytest.raises(NothingToSettle):
        kernel.settle(warrant.warrant_id, ExecutionOutcome.SUCCEEDED)
    assert kernel._is_outstanding(warrant.warrant_id)


def test_a_partial_outcome_cannot_be_recorded_through_this_api(
    tmp_path: Path,
) -> None:
    """**R43.** §6.3 makes `compensation_ref` mandatory for `PARTIAL` —
    *"the most dangerous outcome"* — and `settle(warrant_id, outcome)` has
    no parameter for one. The Kernel cannot invent a compensating action,
    so C5 refuses construction and names what is missing.

    Recorded, not closed: closing it changes `settle()`'s API, which
    ADR-0023 §6.3 records as a ratified decision."""
    kernel, _, _, w = attempted(tmp_path)
    with pytest.raises(InvalidReceipt, match="compensating action"):
        kernel.settle(w.warrant_id, ExecutionOutcome.PARTIAL)


def test_a_refused_partial_writes_nothing_and_settles_nothing(
    tmp_path: Path,
) -> None:
    """R43 fails closed: the warrant is still live and still settleable
    under a kind the API can express."""
    kernel, ledger, _, w = attempted(tmp_path)
    with pytest.raises(InvalidReceipt):
        kernel.settle(w.warrant_id, ExecutionOutcome.PARTIAL)

    assert not ledger.is_settled(w.warrant_id)
    assert kernel._is_outstanding(w.warrant_id)
    assert kernel.settle(w.warrant_id, ExecutionOutcome.UNKNOWN)


@pytest.mark.parametrize("bogus", [None, "succeeded", 1, object()])
def test_an_outcome_that_is_not_one_of_the_four_is_refused(
    tmp_path: Path, bogus: object
) -> None:
    """C5's vocabulary is closed — *"an outcome that does not fit one of
    these is not a fifth kind, it is a caller who has not finished
    deciding what happened."*"""
    kernel, ledger, _, w = attempted(tmp_path)
    with pytest.raises(InvalidReceipt):
        kernel.settle(w.warrant_id, bogus)  # type: ignore[arg-type]
    assert not ledger.is_settled(w.warrant_id)


def test_a_ledger_failure_leaves_the_warrant_unsettled(tmp_path: Path) -> None:
    """§11.3 — fail closed, no buffering. The state stays honestly
    *unsettled* rather than becoming a settlement the ledger never heard
    of, which is §9.5's reconciliation gap."""
    kernel, _, _, w = attempted(
        tmp_path, ledger=OutcomeRefusingLedger(JsonFileStateStore(tmp_path))
    )
    with pytest.raises(LedgerUnavailable):
        kernel.settle(w.warrant_id, ExecutionOutcome.SUCCEEDED)

    assert kernel._is_outstanding(w.warrant_id)
    assert kernel.outstanding_count == 1


def test_a_ledger_failure_is_not_a_refusal(tmp_path: Path) -> None:
    """§3.5 gives `settle()` the return type `Receipt` and no refusal
    channel, so there is no `KernelRefusal` to return — and R40 therefore
    does not extend to this operation."""
    kernel, _, _, w = attempted(
        tmp_path, ledger=OutcomeRefusingLedger(JsonFileStateStore(tmp_path))
    )
    with pytest.raises(LedgerUnavailable) as caught:
        kernel.settle(w.warrant_id, ExecutionOutcome.SUCCEEDED)
    assert not isinstance(caught.value, KernelRefusal)


def test_an_outcome_written_outside_the_kernel_still_blocks_settlement(
    tmp_path: Path,
) -> None:
    """C13's referential integrity is the second line: even with the
    Kernel's own view intact, the ledger refuses a second outcome."""
    kernel, ledger, _, w = attempted(tmp_path)
    ledger.record_outcome(
        Receipt(
            receipt_id="rcp-external",
            objective_id=w.objective_id,
            principal_id=w.principal_id,
            warrant_id=w.warrant_id,
            correlation_id="cor-obj-1",
            trace_id="trc-1",
            capability=w.capability,
            attempt=1,
            outcome=ExecutionOutcome.SUCCEEDED,
            started_at=T0,
            completed_at=T0,
        )
    )
    with pytest.raises(LedgerIntegrityError):
        kernel.settle(w.warrant_id, ExecutionOutcome.FAILED)


# ======================================================================
# §9.2 · referential integrity
# ======================================================================


def test_every_receipt_has_an_intent_record(tmp_path: Path) -> None:
    """§9.5 — *"Every settled intent has an outcome"*, and the arrow runs
    both ways: an outcome with no intent is the gap C13 makes
    unwritable."""
    kernel, ledger, _, w = attempted(tmp_path)
    kernel.settle(w.warrant_id, ExecutionOutcome.SUCCEEDED)

    intents = [r for r in ledger.read(w.warrant_id) if isinstance(r, IntentRecord)]
    assert len(intents) == 1
    assert intents[0].warrant_id == w.warrant_id


def test_the_attempt_count_matches_the_attempt_records(
    tmp_path: Path,
) -> None:
    """The Kernel's lifecycle count and A1's records must agree, or
    §8.6's key means two things."""
    kernel, ledger, _, w = attempted(tmp_path, attempts=3)
    receipt = kernel.settle(w.warrant_id, ExecutionOutcome.SUCCEEDED)

    records = [
        r for r in ledger.read(w.warrant_id) if isinstance(r, AttemptRecord)
    ]
    assert receipt.attempt == len(records)
    assert [r.attempt_seq for r in records] == [1, 2, 3]


def test_the_whole_tree_shares_one_warrant_id(tmp_path: Path) -> None:
    """§9.2 — every arrow is an identifier."""
    kernel, ledger, _, w = attempted(tmp_path, attempts=2)
    kernel.settle(w.warrant_id, ExecutionOutcome.SUCCEEDED)
    assert {r.warrant_id for r in ledger.read(w.warrant_id)} == {w.warrant_id}


def test_the_objective_can_be_walked_from_the_receipt(tmp_path: Path) -> None:
    """§9.3's first query — *"everything done under objective X"*."""
    kernel, _, _, w = attempted(tmp_path)
    receipt = kernel.settle(w.warrant_id, ExecutionOutcome.SUCCEEDED)
    assert receipt.objective_id == w.objective_id


def test_no_settled_warrant_is_left_without_an_outcome(
    tmp_path: Path,
) -> None:
    """§9.5's reconciliation, asserted directly: the Kernel's outstanding
    set and the ledger's settled set never both claim the same warrant."""
    kernel, ledger, _, first = attempted(tmp_path)
    second = kernel.authorize(request(payload_digest="sha256:other"))
    kernel.attempt(second.warrant_id)
    kernel.settle(first.warrant_id, ExecutionOutcome.SUCCEEDED)

    assert ledger.is_settled(first.warrant_id)
    assert not kernel._is_outstanding(first.warrant_id)
    assert not ledger.is_settled(second.warrant_id)
    assert kernel._is_outstanding(second.warrant_id)


# ======================================================================
# What settlement deliberately does not do
# ======================================================================


def test_settling_reads_no_admission_record(tmp_path: Path) -> None:
    """The objective's state is not a settlement question. An effect that
    has already happened is recorded whatever the objective now says."""
    kernel, _, _, admissions = build(tmp_path)
    warrant = kernel.authorize(request())
    kernel.attempt(warrant.warrant_id)
    lookups = len(admissions.lookups)

    kernel.settle(warrant.warrant_id, ExecutionOutcome.SUCCEEDED)
    assert len(admissions.lookups) == lookups


def test_settling_touches_neither_the_override_nor_admission() -> None:
    """§11.8 — *"intents already ATTEMPTING run to settlement."* A
    suspension that blocked settlement would strand the ledger without the
    outcome of work that has already changed the world.

    Checked against the source, because the absence is the assertion."""
    touched = _attributes_touched_by_settle()
    assert not touched & {
        "_override",
        "_check_override_state",
        "_admission",
        "_admission_for",
        "is_suspended",
    }


def test_settling_mints_nothing(tmp_path: Path) -> None:
    kernel, ledger, _, w = attempted(tmp_path)
    kernel.settle(w.warrant_id, ExecutionOutcome.SUCCEEDED)

    intents = [r for r in ledger.read() if isinstance(r, IntentRecord)]
    assert len(intents) == 1
    assert kernel.outstanding_count == 0


def test_settling_re_verifies_no_attestation() -> None:
    """§7.3's attestations were verified once, at authorization."""
    touched = _attributes_touched_by_settle()
    assert "_verify_attestations" not in touched
    assert "attestations" not in touched


def test_settling_compensates_nothing() -> None:
    """§6.4 — *"Undoing is an action. It is classified, authorized,
    receipted, and minted like any other."* There is no privileged undo
    path, so settlement performs none."""
    touched = _attributes_touched_by_settle()
    assert not any("compensat" in name for name in touched)


def test_settlement_is_not_a_retry(tmp_path: Path) -> None:
    """§3.4 — *"Retry mechanics. The Runtime. The Kernel authorizes an
    attempt budget; it does not loop."* A failed settlement opens
    nothing."""
    kernel, ledger, _, w = attempted(tmp_path)
    kernel.settle(w.warrant_id, ExecutionOutcome.FAILED)

    records = [
        r for r in ledger.read(w.warrant_id) if isinstance(r, AttemptRecord)
    ]
    assert len(records) == 1


# ======================================================================
# CONSTITUTIONAL — nothing beyond Part 7
# ======================================================================


def test_settle_still_takes_an_identifier_and_an_outcome() -> None:
    """ADR-0023 §6.3 — *"`settle()` keeps its API."* R43 and R44 are the
    cost of that, and both are recorded rather than paid for with a
    signature change."""
    assert list(inspect.signature(Kernel.settle).parameters) == [
        "self", "warrant_id", "outcome",
    ]


def test_the_public_surface_is_unchanged() -> None:
    surface = {n for n in dir(Kernel) if not n.startswith("_")}
    assert surface == {
        "authorize", "attempt", "settle", "invalidate",
        "override", "outstanding_count",
    }


def test_the_kernel_holds_no_new_state() -> None:
    """Settlement removes state; it adds none. R29 is why — the receipt
    identifiers are derived, never stored at mint."""
    assert set(Kernel.__slots__) == {
        "_admission", "_attempts", "_clock", "_ledger", "_override",
        "_outstanding",
    }


def test_no_operation_remains_unimplemented(tmp_path: Path) -> None:
    """Part 8 built the last one."""
    kernel, _, _, _ = build(tmp_path)
    assert kernel.invalidate("all", "founder override") == 0
    assert MODULE.read_text(encoding="utf-8").count(
        "raise NotImplementedError"
    ) == 0


def test_part_7_publishes_nothing() -> None:
    """§3.5 says settlement *"Publishes"*, and it does not here: §3.3 gives
    the Kernel *"what is published, when. **Not the bus**"*, §3.6's
    dependency rule forbids importing it, and Roadmap §2 puts the
    subscriber at C18. §10.3 makes zero subscribers valid and §10.1's
    guarantee is coverage, never veto — which the durable outcome record
    already provides."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    imported = [
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    ]
    assert not any("events" in n for n in imported)
    assert not any(
        "publish" in n.lower() for n in dir(Kernel) if not n.startswith("__")
    )


def test_part_7_still_depends_only_on_foundation_and_the_ledger() -> None:
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


def test_part_7_reads_no_ambient_time() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    banned = {"datetime.now", "datetime.utcnow", "datetime.today", "time.time"}
    calls = [
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ".".join(ast.unparse(node.func).split(".")[-2:]) in banned
    ]
    assert not calls, f"kernel.py reads ambient time: {calls}"


def test_part_7_stays_within_the_six_hundred_statement_ceiling() -> None:
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


def test_the_gaps_are_marked_where_they_are_reached() -> None:
    """R43 and R44 are recorded at the site, not only in a report."""
    source = MODULE.read_text(encoding="utf-8")
    assert "R43" in source
    assert "R44" in source


def test_there_is_still_no_execute() -> None:
    """§3.5 — *"The Kernel is called; it never calls."*"""
    assert not hasattr(Kernel, "execute")
    assert not any(
        v in n.lower()
        for n in dir(Kernel)
        if not n.startswith("_")
        for v in ("execute", "run", "invoke", "dispatch", "perform")
    )
