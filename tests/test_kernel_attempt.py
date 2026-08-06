"""Sprint 1, Component 15 Part 6 — `attempt()`.

The third of §3.5's four operations:

```
  attempt(intent_id) → AttemptToken | Refusal
      Open one attempt against a live intent. Refuses when expired,
      cancelled, settled, or out of attempt budget. (§8)
```

| Source | Requirement |
|---|---|
| §3.5 | The operation, and its four refusal conditions |
| §4.4 | *"One Intent, N attempts, N attempt records, one outcome record"* |
| §4.5 | MINTED → ATTEMPTING, and what does not happen |
| §8.1 | The audited defect: a loop with nothing to be bounded by |
| §8.4 | An irreversible action is never automatically retried. Ever |
| §8.5 | The budget is set at mint, never by the retry loop |
| §8.6 | `(warrant_id, attempt_seq)` is the idempotency key |
| §9.1 | `AttemptRecord (0..n)` |
| §11.8 | Suspension fails closed on **minting**; `invalidate()` is its reach |

The clock is a `ManualClock`, so every expiry here is exercised by moving
time on purpose rather than by waiting.
"""
from __future__ import annotations

import ast
import inspect
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from master_agent.foundation.attempt_token import AttemptToken
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
from master_agent.foundation.receipt import ExecutionOutcome, Receipt
from master_agent.foundation.refusal import (
    KernelCheck,
    KernelRefusal,
    RefusalReason,
)
from master_agent.foundation.warrant import ReversibilityClass, Warrant
from master_agent.kernel import AttemptNotAuthorized, Kernel
from master_agent.kernel.kernel import ATTEMPT_BUDGET, VALIDITY_DEFAULT
from master_agent.ledger.receipt_ledger import (
    AttemptRecord,
    IntentRecord,
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


class AttemptRefusingLedger(ReceiptLedger):
    """A ledger whose store has gone by the time an attempt opens.

    `record_intent` still works, so a warrant can be minted and only then
    does the store fail — which is the only way to reach §9.1's attempt
    write with a live warrant in hand.
    """

    def record_attempt(self, record):  # type: ignore[override]
        raise LedgerUnavailable("the receipt ledger could not write: disk gone")


class TracingLedger(ReceiptLedger):
    """Records when the write completed, so ordering can be asserted.

    A subclass rather than a patched instance: `ReceiptLedger` is slotted
    and its methods are deliberately not replaceable on an instance.
    """

    def __init__(self, store: JsonFileStateStore) -> None:
        super().__init__(store)
        self.calls: list[str] = []

    def record_attempt(self, record):  # type: ignore[override]
        super().record_attempt(record)
        self.calls.append(f"wrote:{record.attempt_seq}")


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


def mint(
    tmp_path: Path, **kwargs
) -> tuple[Kernel, ReceiptLedger, ManualClock, StubAdmissions, Warrant]:
    """A Kernel with one live warrant — the state every test here starts in."""
    reversibility_class = kwargs.pop(
        "reversibility_class", ReversibilityClass.REVERSIBLE
    )
    kernel, ledger, clock, admissions = build(tmp_path, **kwargs)
    warrant = kernel.authorize(request(reversibility_class=reversibility_class))
    assert isinstance(warrant, Warrant), warrant
    return kernel, ledger, clock, admissions, warrant


def _attempt_records(ledger: ReceiptLedger, warrant_id: str) -> list[AttemptRecord]:
    return [
        r for r in ledger.read(warrant_id) if isinstance(r, AttemptRecord)
    ]


def _attempt_source() -> ast.FunctionDef:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "attempt":
            return node
    raise AssertionError("kernel.py has no attempt()")


def _attributes_touched_by_attempt() -> set[str]:
    return {
        node.attr
        for node in ast.walk(_attempt_source())
        if isinstance(node, ast.Attribute)
    }


# ======================================================================
# The successful attempt
# ======================================================================


def test_a_live_warrant_opens_an_attempt(tmp_path: Path) -> None:
    kernel, _, _, _, w = mint(tmp_path)
    token = kernel.attempt(w.warrant_id)
    assert isinstance(token, AttemptToken)
    assert not isinstance(token, KernelRefusal)


def test_the_token_names_the_warrant_it_runs_under(tmp_path: Path) -> None:
    kernel, _, _, _, w = mint(tmp_path)
    assert kernel.attempt(w.warrant_id).warrant_id == w.warrant_id


def test_the_first_attempt_is_numbered_one(tmp_path: Path) -> None:
    """§8.5 — *"a budget of 1 means one attempt and no second, which is
    unambiguous in a way '0 retries' is not."*"""
    kernel, _, _, _, w = mint(tmp_path)
    token = kernel.attempt(w.warrant_id)
    assert token.attempt_seq == 1
    assert token.is_first_attempt


def test_attempts_are_numbered_monotonically(tmp_path: Path) -> None:
    """§4.4 — *"One Intent, N attempts."*"""
    kernel, _, _, _, w = mint(tmp_path)
    seqs = [kernel.attempt(w.warrant_id).attempt_seq for _ in range(3)]
    assert seqs == [1, 2, 3]


def test_the_token_carries_the_idempotency_key(tmp_path: Path) -> None:
    """§8.6 — *"The Kernel provides the key — `(intent_id, attempt_seq)`."*"""
    kernel, _, _, _, w = mint(tmp_path)
    assert kernel.attempt(w.warrant_id).idempotency_key == (w.warrant_id, 1)
    assert kernel.attempt(w.warrant_id).idempotency_key == (w.warrant_id, 2)


def test_the_token_opens_at_the_canonical_clocks_moment(tmp_path: Path) -> None:
    kernel, _, clock, _, w = mint(tmp_path)
    clock.advance(timedelta(seconds=5))
    assert kernel.attempt(w.warrant_id).opened_at == T0 + timedelta(seconds=5)


def test_two_warrants_count_their_attempts_independently(
    tmp_path: Path,
) -> None:
    """One Intent authorizes one logical action (§4.4), and its budget is
    its own."""
    kernel, _, _, _, first = mint(tmp_path)
    second = kernel.authorize(request(payload_digest="sha256:other"))
    kernel.attempt(first.warrant_id)
    kernel.attempt(first.warrant_id)
    assert kernel.attempt(second.warrant_id).attempt_seq == 1


# ======================================================================
# §8.5 · the attempt budget — set at mint, never by the loop
# ======================================================================


@pytest.mark.parametrize("cls", list(ReversibilityClass))
def test_a_warrant_opens_exactly_its_budget_of_attempts(
    tmp_path: Path, cls: ReversibilityClass
) -> None:
    """§8.5's completed table, exercised end to end rather than read."""
    kernel, _, _, _, w = mint(tmp_path, reversibility_class=cls)
    budget = ATTEMPT_BUDGET[cls]
    assert w.attempt_budget == budget

    for expected in range(1, budget + 1):
        assert kernel.attempt(w.warrant_id).attempt_seq == expected

    with pytest.raises(AttemptNotAuthorized):
        kernel.attempt(w.warrant_id)


def test_an_exhausted_budget_names_itself(tmp_path: Path) -> None:
    """§8.1 — *"the root cause is not the loop. It is that there was
    nothing for the loop to be bounded by."*"""
    kernel, _, _, _, w = mint(tmp_path)
    for _ in range(w.attempt_budget):
        kernel.attempt(w.warrant_id)

    with pytest.raises(AttemptNotAuthorized, match="authorized attempts"):
        kernel.attempt(w.warrant_id)


def test_an_irreversible_action_gets_one_attempt_and_no_second(
    tmp_path: Path,
) -> None:
    """§8.4, the most important clause in §8 — *"never automatically
    retried. Ever. Regardless of attempt budget, error class, or how
    transient the failure appears."*

    There is no separate §8.4 branch in `attempt()` and there must not be:
    C4 refuses to construct an irreversible warrant whose budget is
    anything but 1, so the rule is **structural** rather than a check that
    could be edited out. This proves it holds through the budget.
    """
    kernel, _, _, _, w = mint(
        tmp_path, reversibility_class=ReversibilityClass.IRREVERSIBLE
    )
    assert w.attempt_budget == 1
    assert kernel.attempt(w.warrant_id).attempt_seq == 1

    with pytest.raises(AttemptNotAuthorized):
        kernel.attempt(w.warrant_id)


def test_a_spent_budget_is_never_refreshed_by_waiting(tmp_path: Path) -> None:
    """The budget is a count, not a rate. Nothing about the passage of
    time returns an attempt to a warrant."""
    kernel, _, clock, _, w = mint(tmp_path)
    for _ in range(w.attempt_budget):
        kernel.attempt(w.warrant_id)

    clock.advance(timedelta(seconds=1))
    with pytest.raises(AttemptNotAuthorized):
        kernel.attempt(w.warrant_id)


def test_no_caller_can_supply_a_budget(tmp_path: Path) -> None:
    """§8.5 — *"Set at mint from the capability's class, never by the
    retry loop."* There is no parameter for it, on either operation."""
    assert list(inspect.signature(Kernel.attempt).parameters) == [
        "self", "warrant_id",
    ]


# ======================================================================
# §4.4 · the validity window
# ======================================================================


def test_an_expired_warrant_opens_no_attempt(tmp_path: Path) -> None:
    kernel, _, clock, _, w = mint(tmp_path)
    clock.advance(VALIDITY_DEFAULT[ActionClass.LOCAL])

    assert w.is_expired(clock.now())
    with pytest.raises(AttemptNotAuthorized, match="expired"):
        kernel.attempt(w.warrant_id)


def test_a_warrant_expiring_mid_sequence_stops_at_that_moment(
    tmp_path: Path,
) -> None:
    """§4.4 — *"an intent minted before an approval and used hours later
    is authorized against a world that no longer exists."* The budget is
    not the only bound; both must hold.
    """
    kernel, _, clock, _, w = mint(tmp_path)
    assert kernel.attempt(w.warrant_id).attempt_seq == 1

    clock.advance(VALIDITY_DEFAULT[ActionClass.LOCAL])
    with pytest.raises(AttemptNotAuthorized):
        kernel.attempt(w.warrant_id)


def test_expiry_is_checked_before_the_budget(tmp_path: Path) -> None:
    """§7.1's ordering principle applied here: a warrant that is both
    expired and spent is reported as expired, because that is the more
    fundamental fact — the authorization ended, and a budget on an ended
    authorization is not the reason it cannot be used."""
    kernel, _, clock, _, w = mint(tmp_path)
    for _ in range(w.attempt_budget):
        kernel.attempt(w.warrant_id)
    clock.advance(VALIDITY_DEFAULT[ActionClass.LOCAL])

    with pytest.raises(AttemptNotAuthorized, match="expired"):
        kernel.attempt(w.warrant_id)


def test_the_last_moment_inside_the_window_still_opens_an_attempt(
    tmp_path: Path,
) -> None:
    """C4's `is_expired` is `>=`, so the boundary is closed at the end.
    Asserted here so the edge is a decision rather than an accident."""
    kernel, _, clock, _, w = mint(tmp_path)
    clock.advance(VALIDITY_DEFAULT[ActionClass.LOCAL] - timedelta(seconds=1))
    assert kernel.attempt(w.warrant_id).attempt_seq == 1


# ======================================================================
# The warrant must be one this Kernel minted and still holds
# ======================================================================


def test_an_unknown_warrant_id_opens_no_attempt(tmp_path: Path) -> None:
    """§4.2 — *"Only `Kernel.authorize()`. No other constructor exists at
    any privilege level."* An id from nowhere is an id from nowhere."""
    kernel, _, _, _, _ = mint(tmp_path)
    with pytest.raises(AttemptNotAuthorized, match="not outstanding"):
        kernel.attempt("wrt-000000000999")


def test_a_warrant_from_another_kernel_is_not_accepted(tmp_path: Path) -> None:
    """Minting authority is never federated (§15.2). Two Kernels mint
    identically, and that is precisely why one must not honour the
    other's token."""
    _, _, _, _, w = mint(tmp_path)
    second, _, _, _ = build(tmp_path / "other")

    assert second.outstanding_count == 0
    with pytest.raises(AttemptNotAuthorized):
        second.attempt(w.warrant_id)


@pytest.mark.parametrize("bogus", ["", "   ", "not-a-warrant"])
def test_a_malformed_identifier_opens_no_attempt(
    tmp_path: Path, bogus: str
) -> None:
    kernel, _, _, _, _ = mint(tmp_path)
    with pytest.raises(AttemptNotAuthorized):
        kernel.attempt(bogus)


def test_a_refused_authorization_leaves_nothing_to_attempt(
    tmp_path: Path,
) -> None:
    """No warrant, no attempt. There is no path from a refusal to a
    token."""
    kernel, _, _, _, _ = mint(tmp_path)
    refusal = kernel.authorize(request(objective_id="obj-unknown"))
    assert isinstance(refusal, KernelRefusal)
    with pytest.raises(AttemptNotAuthorized):
        kernel.attempt("obj-unknown")


# ======================================================================
# §9.1 · the attempt record is durable before the token exists
# ======================================================================


def test_every_attempt_is_recorded(tmp_path: Path) -> None:
    """§9.1 — `IntentRecord ──┬── AttemptRecord (0..n)`."""
    kernel, ledger, _, _, w = mint(tmp_path)
    kernel.attempt(w.warrant_id)
    kernel.attempt(w.warrant_id)

    records = _attempt_records(ledger, w.warrant_id)
    assert [r.attempt_seq for r in records] == [1, 2]


def test_the_record_carries_the_tokens_own_key_and_moment(
    tmp_path: Path,
) -> None:
    """§9.2 — *"every arrow is an identifier, never a copy."* The record
    and the token must agree, or the idempotency key means two things."""
    kernel, ledger, clock, _, w = mint(tmp_path)
    clock.advance(timedelta(seconds=3))
    token = kernel.attempt(w.warrant_id)

    (record,) = _attempt_records(ledger, w.warrant_id)
    assert (record.warrant_id, record.attempt_seq) == token.idempotency_key
    assert record.recorded_at == token.opened_at


def test_the_record_is_written_before_the_token_is_returned(
    tmp_path: Path,
) -> None:
    """A token is §8.6's idempotency key and a Worker *"treats it as
    settled fact."* One handed out before the write would authorize an
    attempt the ledger has never heard of."""
    kernel, ledger, _, _, w = mint(
        tmp_path, ledger=TracingLedger(JsonFileStateStore(tmp_path))
    )
    token = kernel.attempt(w.warrant_id)
    ledger.calls.append(f"token:{token.attempt_seq}")

    assert ledger.calls == ["wrote:1", "token:1"]


def test_a_ledger_failure_refuses_and_opens_nothing(tmp_path: Path) -> None:
    """§11.3 — fail closed, no buffering. This is the one condition C8 can
    name, so it is a real `KernelRefusal` rather than a raise."""
    kernel, _, _, _, w = mint(
        tmp_path, ledger=AttemptRefusingLedger(JsonFileStateStore(tmp_path))
    )
    refusal = kernel.attempt(w.warrant_id)

    assert isinstance(refusal, KernelRefusal)
    assert refusal.reason is RefusalReason.LEDGER_UNAVAILABLE
    assert refusal.failed_check is KernelCheck.K3_RECEIPT_INTENT_WRITE
    assert refusal.attestor is None
    assert refusal.remediable is True


def test_a_failed_write_consumes_no_attempt(tmp_path: Path) -> None:
    """The budget must not be spent by an attempt that never opened —
    otherwise a storage outage silently burns the founder's
    authorization."""
    kernel, _, _, _, w = mint(
        tmp_path, ledger=AttemptRefusingLedger(JsonFileStateStore(tmp_path))
    )
    for _ in range(w.attempt_budget + 2):
        assert isinstance(kernel.attempt(w.warrant_id), KernelRefusal)

    assert kernel._attempts.get(w.warrant_id, 0) == 0


def test_a_settled_warrant_opens_no_attempt(tmp_path: Path) -> None:
    """§9.1 marks the outcome record **terminal**.

    In Part 6 this is caught by C13's referential integrity rather than by
    a Kernel liveness gate, because `settle()` is Part 7 and nothing yet
    leaves the outstanding set. The condition is enforced either way, and
    the refusal is the ledger's honest report that the write could not be
    made.
    """
    kernel, ledger, _, _, w = mint(tmp_path)
    ledger.record_outcome(
        Receipt(
            receipt_id="rcp-1",
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

    refusal = kernel.attempt(w.warrant_id)
    assert isinstance(refusal, KernelRefusal)
    assert refusal.reason is RefusalReason.LEDGER_UNAVAILABLE
    assert _attempt_records(ledger, w.warrant_id) == []


def test_no_attempt_is_recorded_when_the_warrant_is_not_live(
    tmp_path: Path,
) -> None:
    """Nothing happened, so §9.1's tree gains nothing. An
    `AttemptNotAuthorized` is not an attempt."""
    kernel, ledger, clock, _, w = mint(tmp_path)
    clock.advance(VALIDITY_DEFAULT[ActionClass.LOCAL])

    with pytest.raises(AttemptNotAuthorized):
        kernel.attempt(w.warrant_id)
    assert _attempt_records(ledger, w.warrant_id) == []


def test_the_intent_record_is_untouched_by_attempting(tmp_path: Path) -> None:
    """Append-only at every privilege level (§9.1). The intent written at
    K3 is the same record afterwards."""
    kernel, ledger, _, _, w = mint(tmp_path)
    before = [
        r.as_dict() for r in ledger.read(w.warrant_id)
        if isinstance(r, IntentRecord)
    ]
    kernel.attempt(w.warrant_id)
    after = [
        r.as_dict() for r in ledger.read(w.warrant_id)
        if isinstance(r, IntentRecord)
    ]
    assert before == after


def test_the_records_survive_a_ledger_restart(tmp_path: Path) -> None:
    """The attempt tree is evidence, not session state."""
    kernel, _, _, _, w = mint(tmp_path)
    kernel.attempt(w.warrant_id)
    kernel.attempt(w.warrant_id)

    reopened = ReceiptLedger(JsonFileStateStore(tmp_path))
    assert [r.attempt_seq for r in _attempt_records(reopened, w.warrant_id)] == [
        1,
        2,
    ]


# ======================================================================
# Determinism, and what attempting must not disturb
# ======================================================================


def test_the_warrant_is_never_mutated(tmp_path: Path) -> None:
    """§4.4 — *"Nothing mutates an Intent, ever, at any privilege
    level."*"""
    kernel, _, _, _, w = mint(tmp_path)
    before = w.as_dict()
    kernel.attempt(w.warrant_id)
    assert kernel._outstanding[w.warrant_id] is w
    assert w.as_dict() == before


def test_attempting_does_not_settle(tmp_path: Path) -> None:
    """§4.5 — MINTED → ATTEMPTING, and ATTEMPTING is not terminal. The
    warrant leaves the outstanding set at settlement, which is Part 7."""
    kernel, _, _, _, w = mint(tmp_path)
    for _ in range(w.attempt_budget):
        kernel.attempt(w.warrant_id)
    assert kernel.outstanding_count == 1
    assert kernel._is_outstanding(w.warrant_id)


def test_attempting_consumes_no_clock_sequence(tmp_path: Path) -> None:
    """`stamp()` *"consumes a sequence number; `now()` does not."* The
    warrant id is derived from that sequence, so an attempt that spent one
    would silently shift the next mint's identity."""
    kernel, _, _, _, first = mint(tmp_path)
    kernel.attempt(first.warrant_id)
    second = kernel.authorize(request(payload_digest="sha256:other"))

    def seq(warrant: Warrant) -> int:
        return int(warrant.warrant_id.removeprefix("wrt-"))

    assert seq(second) == seq(first) + 1


def test_attempting_reads_no_admission_record(tmp_path: Path) -> None:
    """§3.5 lists four conditions and the objective's state is not among
    them. Re-reading admission would put a fifth gate on the path that no
    specification asks for."""
    kernel, _, _, admissions, w = mint(tmp_path)
    lookups = len(admissions.lookups)
    kernel.attempt(w.warrant_id)
    assert len(admissions.lookups) == lookups


def test_attempting_touches_neither_the_override_nor_admission() -> None:
    """§11.8 — suspension *"fails closed on **minting**"*, and its reach
    into work already authorized is `invalidate()`: *"invalidate every
    MINTED intent not yet attempted"*, while *"intents already ATTEMPTING
    run to settlement."* A K2 check here would contradict the second
    clause and duplicate the first.

    Checked against the source rather than prose, because the absence is
    the assertion."""
    touched = _attributes_touched_by_attempt()
    assert not touched & {
        "_override",
        "_check_override_state",
        "_admission",
        "_admission_for",
        "is_suspended",
    }


def test_attempting_mints_nothing(tmp_path: Path) -> None:
    """§3.5 — the Kernel's minting authority is `authorize()`'s alone."""
    kernel, ledger, _, _, w = mint(tmp_path)
    before = kernel.outstanding_count
    kernel.attempt(w.warrant_id)
    assert kernel.outstanding_count == before
    assert not any(
        isinstance(r, IntentRecord) and r.warrant_id != w.warrant_id
        for r in ledger.read()
    )


def test_attempting_re_verifies_no_attestation(tmp_path: Path) -> None:
    """§7.3's attestations are verified once, at authorization. Re-running
    them here would make the Kernel disagree with itself about a request
    it already admitted."""
    touched = _attributes_touched_by_attempt()
    assert "_verify_attestations" not in touched
    assert "attestations" not in touched


# ======================================================================
# R40 · the refusal vocabulary gap, recorded rather than closed
# ======================================================================


def test_no_refusal_reason_names_any_attempt_condition() -> None:
    """**R40.** §3.5 requires `attempt()` to *refuse* when a warrant is
    expired, cancelled, settled or out of budget, and C8 can name none of
    them. This asserts the gap so it cannot close by accident and go
    unnoticed — the same posture as the shipped R39.

    C8 is frozen at `c8.0` and this part does not reopen it.
    """
    names = {r.value for r in RefusalReason}
    for condition in ("expire", "budget", "settled", "cancel", "attempt"):
        assert not any(condition in n for n in names), condition


def test_the_gap_is_marked_where_it_is_reached() -> None:
    """The founder's standing instruction: a recorded issue is marked at
    the site, not only in a report."""
    source = MODULE.read_text(encoding="utf-8")
    assert "R40" in source
    assert "R41" in source


def test_an_unauthorized_attempt_is_not_a_refusal_in_disguise(
    tmp_path: Path,
) -> None:
    """C8's own reasoning for why this is the safer shape: a refusal
    *"that names the wrong check, or names no check at all, is worse than
    no record because it looks like evidence."*"""
    kernel, _, _, _, w = mint(tmp_path)
    for _ in range(w.attempt_budget):
        kernel.attempt(w.warrant_id)

    with pytest.raises(AttemptNotAuthorized) as caught:
        kernel.attempt(w.warrant_id)
    assert not isinstance(caught.value, KernelRefusal)


def test_it_is_not_a_value_error(tmp_path: Path) -> None:
    """Following `LedgerUnavailable`: a caller wrapping value construction
    in `except ValueError` must never absorb *"this warrant is spent."*"""
    assert issubclass(AttemptNotAuthorized, RuntimeError)
    assert not issubclass(AttemptNotAuthorized, ValueError)


def test_the_payload_digest_is_not_checked_here() -> None:
    """**R41.** §4.4 says the digest *"is checked at `attempt()`, not
    merely at mint"*, and §3.5 gives the operation an identifier and
    nothing else — so there is no capability and no payload to compare.

    Recorded, not closed: changing the signature would contradict §3.5 and
    Roadmap Amendment 001 M4.
    """
    assert list(inspect.signature(Kernel.attempt).parameters) == [
        "self", "warrant_id",
    ]
    assert "matches" not in _attributes_touched_by_attempt()


# ======================================================================
# CONSTITUTIONAL — nothing beyond Part 6
# ======================================================================


def test_the_public_surface_is_unchanged() -> None:
    """`attempt()` was already on the surface. Part 6 adds no operation
    and no reader — the attempt count is the Intent lifecycle's, and §3.3
    keeps that inside the Kernel."""
    surface = {n for n in dir(Kernel) if not n.startswith("_")}
    assert surface == {
        "authorize", "attempt", "settle", "invalidate",
        "override", "outstanding_count",
    }


def test_an_attempted_warrant_survives_an_override(tmp_path: Path) -> None:
    """The unbuilt-operation guard this replaces is spent: Part 8 built
    `invalidate()`. What matters here is §11.8 step 3 seen from the
    attempt side — *"intents already ATTEMPTING run to settlement."*"""
    kernel, _, _, _, w = mint(tmp_path)
    kernel.attempt(w.warrant_id)
    assert kernel.invalidate("all", "founder override") == 0
    assert kernel._is_outstanding(w.warrant_id)


def test_part_6_publishes_nothing() -> None:
    """§10.3 — zero subscribers is a valid configuration, and the Event
    Bus arrives with publication. `ATTEMPT_STARTED` is not emitted here."""
    source = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(MODULE))
    imported = [
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    ]
    assert not any("events" in n for n in imported)
    assert not any(
        "publish" in n.lower() for n in dir(Kernel) if not n.startswith("__")
    )


def test_part_6_holds_no_attestor() -> None:
    """§7.3 — still true. The attempt path consults no owner of anything."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    imported = " ".join(
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    for owner in ("reversibility", "permissions", "broker", "mission_control"):
        assert owner not in imported


def test_part_6_still_depends_only_on_foundation_and_the_ledger() -> None:
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


def test_part_6_reads_no_ambient_time() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    banned = {"datetime.now", "datetime.utcnow", "datetime.today", "time.time"}
    calls = [
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ".".join(ast.unparse(node.func).split(".")[-2:]) in banned
    ]
    assert not calls, f"kernel.py reads ambient time: {calls}"


def test_part_6_stays_within_the_six_hundred_statement_ceiling() -> None:
    """§14 R9 — *"if the Kernel exceeds roughly 600 lines, something in it
    belongs somewhere else."*"""
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
    """§3.5 — *"The Kernel is called; it never calls."* An operation that
    hands out a token is not an operation that runs anything."""
    assert not hasattr(Kernel, "execute")
    assert not any(
        v in n.lower()
        for n in dir(Kernel)
        if not n.startswith("_")
        for v in ("execute", "run", "invoke", "dispatch", "perform")
    )
