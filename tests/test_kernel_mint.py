"""Sprint 1, Component 15 Part 5 — K3 and the mint.

`authorize()` completed: §7.4's order, §7.2 K3's receipt-intent write, and
the `Warrant`.

| Source | Requirement |
|---|---|
| §7.2 K3 | *"If the write fails, the Kernel refuses and **nothing executes**"* |
| §4.3 | Every Intent field, and where it comes from |
| §4.4 | `expires_at = min(…)` · non-transferability |
| §8.5 | Attempt budgets, completed by ADR-0023 D3 |
| §9.5 | An orphaned record is a reconciliation gap |
| §10.4 | The consequence ceiling bounds every warrant |
| ADR-0022 · ADR-0023 | The carried class, and every derivation |

The Kernel's clock is a `ManualClock`, so **every mint here is
deterministic** — that is the property most of these tests turn on.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
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
    KernelCheck,
    KernelRefusal,
    RefusalReason,
)
from master_agent.foundation.warrant import InvalidWarrant, ReversibilityClass, Warrant
from master_agent.kernel import InvalidKernel, Kernel
from master_agent.kernel.kernel import ATTEMPT_BUDGET, VALIDITY_DEFAULT
from master_agent.ledger.receipt_ledger import IntentRecord, ReceiptLedger
from master_agent.persistence.store import JsonFileStateStore
from tests.kernel_test_support import StubAdmissions, admission

MODULE = (
    Path(__file__).resolve().parent.parent
    / "src" / "master_agent" / "kernel" / "kernel.py"
)


def _kernel_imports() -> list[str]:
    import ast

    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    return [
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    ]


T0 = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
DEADLINE = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)
DIGEST = "sha256:abc"

LOCAL_QUESTIONS = tuple(
    q for q in AttestationQuestion if not q.is_intelligence_only
)
ALL_QUESTIONS = tuple(AttestationQuestion)


def attest(question: AttestationQuestion, **overrides) -> Attestation:
    defaults = {
        "question": question,
        "attestor": question.canonical_attestor,
        "subject": DIGEST,
        "verdict": AttestationVerdict.SATISFIED,
        "attested_at": T0,
    }
    return Attestation(**{**defaults, **overrides})


def request(
    action_class: ActionClass = ActionClass.LOCAL, **overrides
) -> ExecutionRequest:
    questions = (
        ALL_QUESTIONS
        if action_class is ActionClass.INTELLIGENCE
        else LOCAL_QUESTIONS
    )
    # The attestations must attest to *this* request's payload, or §7.3's
    # subject match refuses them -- which is the point of the check.
    digest = overrides.get("payload_digest", DIGEST)
    defaults = {
        "objective_id": "obj-1",
        "principal_id": "founder",
        "capability": "Filesystem.DeleteFolder",
        "payload_digest": DIGEST,
        "action_class": action_class,
        "reversibility_class": ReversibilityClass.REVERSIBLE,
        "expected_effect": "the folder is gone",
        "consequence": PENDING_CONSEQUENCE_ENGINE,
        "attestations": tuple(attest(q, subject=digest) for q in questions),
    }
    return ExecutionRequest(**{**defaults, **overrides})


class BrokenLedger(ReceiptLedger):
    """A ledger whose store has gone. §11.3's fail-closed condition."""

    def record_intent(self, record):  # type: ignore[override]
        from master_agent.ledger.receipt_ledger import LedgerUnavailable

        raise LedgerUnavailable("the receipt ledger could not write: disk gone")


def build(
    tmp_path: Path,
    *,
    ceiling: ReversibilityClass = ReversibilityClass.IRREVERSIBLE,
    deadline: datetime = DEADLINE,
    ledger: ReceiptLedger | None = None,
) -> tuple[Kernel, ReceiptLedger]:
    # An empty ReceiptLedger is falsy (`__len__` is 0), so this must be
    # an identity test rather than a truthiness one.
    store = ledger if ledger is not None else ReceiptLedger(
        JsonFileStateStore(tmp_path)
    )
    kernel = Kernel(
        clock=ManualClock(T0),
        ledger=store,
        admission=StubAdmissions(
            admission(consequence_ceiling=ceiling, deadline=deadline)
        ),
    )
    return kernel, store


# ======================================================================
# The successful mint
# ======================================================================


def test_a_complete_request_mints_a_warrant(tmp_path: Path) -> None:
    kernel, _ = build(tmp_path)
    warrant = kernel.authorize(request())
    assert isinstance(warrant, Warrant)
    assert not isinstance(warrant, KernelRefusal)


def test_the_warrant_carries_the_requests_identity(tmp_path: Path) -> None:
    """§8.2 — *"Same action ≡ identical (objective_id, actor, capability,
    payload_digest, target_ref)."*"""
    kernel, _ = build(tmp_path)
    w = kernel.authorize(request())
    assert w.objective_id == "obj-1"
    assert w.principal_id == "founder"
    assert w.capability == "Filesystem.DeleteFolder"
    assert w.payload_digest == DIGEST


def test_the_warrant_carries_the_class_the_request_supplied(
    tmp_path: Path,
) -> None:
    """ADR-0022 — the caller carries it from the Reversibility Registry."""
    kernel, _ = build(tmp_path)
    w = kernel.authorize(request(reversibility_class=ReversibilityClass.READ_ONLY))
    assert w.reversibility_class is ReversibilityClass.READ_ONLY


def test_the_ceiling_comes_from_the_admission_record(tmp_path: Path) -> None:
    """§10.4 — the envelope is the objective's, never the caller's."""
    kernel, _ = build(tmp_path, ceiling=ReversibilityClass.REVERSIBLE_UNTIL)
    assert kernel.authorize(request()).consequence_ceiling is (
        ReversibilityClass.REVERSIBLE_UNTIL
    )


def test_the_warrant_is_registered(tmp_path: Path) -> None:
    kernel, _ = build(tmp_path)
    w = kernel.authorize(request())
    assert kernel.outstanding_count == 1
    assert kernel._is_outstanding(w.warrant_id)


# ======================================================================
# Determinism
# ======================================================================


def test_two_kernels_mint_identically(tmp_path: Path) -> None:
    """The whole point of the Clock: same inputs, same warrant."""
    a, _ = build(tmp_path / "a")
    b, _ = build(tmp_path / "b")
    assert a.authorize(request()) == b.authorize(request())


def test_the_warrant_id_is_deterministic_and_never_random(
    tmp_path: Path,
) -> None:
    """§4.3 sources the token to the Kernel. `uuid4()` would make the
    Kernel unverifiable."""
    a, _ = build(tmp_path / "a")
    b, _ = build(tmp_path / "b")
    assert a.authorize(request()).warrant_id == b.authorize(request()).warrant_id


def test_warrant_ids_are_monotonic_within_one_kernel(tmp_path: Path) -> None:
    """The Clock's stamp *"consumes a sequence number."*"""
    kernel, _ = build(tmp_path)
    ids = [
        kernel.authorize(request(payload_digest=f"sha256:{i}")).warrant_id
        for i in range(3)
    ]
    assert ids == sorted(ids)
    assert len(set(ids)) == 3


def test_the_correlation_id_is_shared_across_an_objective(
    tmp_path: Path,
) -> None:
    """C5 — *"the logical unit of work this belonged to. Several
    executions share one."*"""
    kernel, _ = build(tmp_path)
    assert kernel._correlation_id("obj-1") == kernel._correlation_id("obj-1")
    assert kernel._correlation_id("obj-1") != kernel._correlation_id("obj-2")


def test_the_trace_id_is_unique_per_execution(tmp_path: Path) -> None:
    """C5 — *"**this** execution."*"""
    kernel, _ = build(tmp_path)
    assert kernel._trace_id(1) != kernel._trace_id(2)
    assert kernel._trace_id(7) == kernel._trace_id(7)


def test_the_identifiers_are_derivable_without_stored_state(
    tmp_path: Path,
) -> None:
    """Because both are pure functions of data already on the `Warrant`,
    settlement re-derives them rather than the Kernel storing a map."""
    kernel, _ = build(tmp_path)
    w = kernel.authorize(request())
    sequence = int(w.warrant_id.removeprefix("wrt-"))
    assert kernel._correlation_id(w.objective_id) == "cor-obj-1"
    assert kernel._trace_id(sequence) == f"trc-{sequence:012d}"


# ======================================================================
# §8.5 · attempt_budget — ADR-0023 D3
# ======================================================================


def test_the_budget_table_is_complete() -> None:
    assert set(ATTEMPT_BUDGET) == set(ReversibilityClass)


def test_the_specified_budgets_are_verbatim() -> None:
    """§8.5 gives these two directly."""
    assert ATTEMPT_BUDGET[ReversibilityClass.IRREVERSIBLE] == 1
    assert ATTEMPT_BUDGET[ReversibilityClass.REVERSIBLE] == 3


def test_reversible_until_is_forced_between_one_and_three() -> None:
    """ADR-0023 D3 — the effect is undoable so it exceeds 1, and *"the
    undo window is not extended by retrying"* so it falls below 3. One
    integer satisfies both."""
    budget = ATTEMPT_BUDGET[ReversibilityClass.REVERSIBLE_UNTIL]
    assert 1 < budget < 3
    assert budget == 2


def test_read_only_is_bounded_and_above_reversible() -> None:
    """*"Liberal"* is not *"unlimited"*: an unbounded budget is a
    permission with no end."""
    budget = ATTEMPT_BUDGET[ReversibilityClass.READ_ONLY]
    assert budget > ATTEMPT_BUDGET[ReversibilityClass.REVERSIBLE]
    assert budget < 100


@pytest.mark.parametrize("cls", list(ReversibilityClass))
def test_the_budget_is_set_at_mint_from_the_class(tmp_path: Path, cls) -> None:
    """§8.5 — *"Set at mint from the capability's class, never by the retry
    loop."*"""
    kernel, _ = build(tmp_path)
    w = kernel.authorize(request(reversibility_class=cls))
    assert w.attempt_budget == ATTEMPT_BUDGET[cls]


def test_an_irreversible_action_gets_exactly_one_attempt(
    tmp_path: Path,
) -> None:
    """§8.4 — *"never automatically retried. Ever."*"""
    kernel, _ = build(tmp_path)
    w = kernel.authorize(
        request(reversibility_class=ReversibilityClass.IRREVERSIBLE)
    )
    assert w.attempt_budget == 1


# ======================================================================
# §4.4 · expires_at — ADR-0023 D4
# ======================================================================


def test_a_local_warrant_expires_on_the_class_default(tmp_path: Path) -> None:
    """§4.4 — *"seconds for a filesystem write."*"""
    kernel, _ = build(tmp_path)
    w = kernel.authorize(request(ActionClass.LOCAL))
    assert w.expires_at == T0 + VALIDITY_DEFAULT[ActionClass.LOCAL]


def test_an_intelligence_warrant_gets_the_longer_default(
    tmp_path: Path,
) -> None:
    """A provider call is not a filesystem write."""
    kernel, _ = build(tmp_path)
    w = kernel.authorize(request(ActionClass.INTELLIGENCE))
    assert w.expires_at == T0 + VALIDITY_DEFAULT[ActionClass.INTELLIGENCE]


def test_the_envelope_deadline_truncates_the_default(tmp_path: Path) -> None:
    """§10.4 — the objective's deadline bounds every warrant under it."""
    near = T0 + timedelta(seconds=5)
    kernel, _ = build(tmp_path, deadline=near)
    assert kernel.authorize(request()).expires_at == near


def test_the_shorter_of_the_two_always_wins(tmp_path: Path) -> None:
    for deadline, expected in (
        (T0 + timedelta(seconds=5), T0 + timedelta(seconds=5)),
        (T0 + timedelta(days=1), T0 + VALIDITY_DEFAULT[ActionClass.LOCAL]),
    ):
        kernel, _ = build(tmp_path / str(deadline.timestamp()), deadline=deadline)
        assert kernel.authorize(request()).expires_at == expected


def test_the_window_is_deterministic(tmp_path: Path) -> None:
    a, _ = build(tmp_path / "a")
    b, _ = build(tmp_path / "b")
    assert a.authorize(request()).expires_at == b.authorize(request()).expires_at


def test_a_warrant_is_never_expired_at_birth(tmp_path: Path) -> None:
    """C4 refuses `expires_at <= issued_at`, so the algorithm must not
    produce one. ADR-0023 D4's C17 invariant is what keeps the deadline in
    the future when K1 passes."""
    kernel, _ = build(tmp_path)
    w = kernel.authorize(request())
    assert w.expires_at > w.issued_at
    assert not w.is_expired(w.issued_at)


def test_a_past_deadline_fails_closed_rather_than_minting(
    tmp_path: Path,
) -> None:
    """ADR-0023 D4: if C17 violates its invariant, `Warrant` refuses at
    construction and nothing is minted. Fail-closed, and **not** a
    `KernelRefusal` — an Engine defect is not a decision the Kernel made."""
    kernel, ledger = build(tmp_path, deadline=T0 - timedelta(seconds=1))
    with pytest.raises(InvalidWarrant, match="expired at birth"):
        kernel.authorize(request())
    assert kernel.outstanding_count == 0
    assert len(ledger) == 0


# ======================================================================
# §10.4 · the ceiling bounds the warrant
# ======================================================================


def test_a_class_within_the_ceiling_mints(tmp_path: Path) -> None:
    kernel, _ = build(tmp_path, ceiling=ReversibilityClass.REVERSIBLE)
    assert isinstance(
        kernel.authorize(
            request(reversibility_class=ReversibilityClass.READ_ONLY)
        ),
        Warrant,
    )


def test_a_class_exceeding_the_ceiling_cannot_mint(tmp_path: Path) -> None:
    """§10.4 — *"An objective admitted with `consequence_ceiling:
    reversible` **cannot mint an irreversible warrant**."* C4 enforces it
    at construction; the Kernel does not restate the check."""
    kernel, ledger = build(tmp_path, ceiling=ReversibilityClass.REVERSIBLE)
    with pytest.raises(InvalidWarrant, match="exceeds"):
        kernel.authorize(
            request(reversibility_class=ReversibilityClass.IRREVERSIBLE)
        )
    assert kernel.outstanding_count == 0
    assert len(ledger) == 0


# ======================================================================
# §7.2 K3 · the receipt-intent write
# ======================================================================


def test_the_intent_is_written_before_the_warrant_is_returned(
    tmp_path: Path,
) -> None:
    """§7.2 K3 — nothing executes without a durable intent."""
    kernel, ledger = build(tmp_path)
    w = kernel.authorize(request())
    assert len(ledger) == 1
    assert ledger.has_intent(w.warrant_id)


def test_the_intent_record_carries_a1s_field_list(tmp_path: Path) -> None:
    """VEDA 04 A1 — *"actor, rule (if any), reversibility class, expected
    effect, and the consequence quartet."*"""
    kernel, ledger = build(tmp_path)
    w = kernel.authorize(request())
    record = ledger.read(w.warrant_id)[0]
    assert isinstance(record, IntentRecord)
    assert record.principal_id == "founder"
    assert record.reversibility_class is ReversibilityClass.REVERSIBLE
    assert record.expected_effect == "the folder is gone"
    assert record.consequence is PENDING_CONSEQUENCE_ENGINE


def test_the_expected_effect_reaches_the_permanent_record(
    tmp_path: Path,
) -> None:
    """ADR-0023 D2's whole purpose."""
    kernel, ledger = build(tmp_path)
    w = kernel.authorize(request(expected_effect="the workspace is clear"))
    assert ledger.read(w.warrant_id)[0].expected_effect == "the workspace is clear"


def test_the_consequence_is_never_recorded_as_null(tmp_path: Path) -> None:
    """§14.1 — the marker, never null."""
    kernel, ledger = build(tmp_path)
    w = kernel.authorize(request())
    projected = ledger.read(w.warrant_id)[0].as_dict()
    assert projected["consequence"] == "pending_consequence_engine"


def test_the_record_is_timestamped_from_the_kernels_clock(
    tmp_path: Path,
) -> None:
    kernel, ledger = build(tmp_path)
    w = kernel.authorize(request())
    assert ledger.read(w.warrant_id)[0].recorded_at == w.issued_at


def test_a_ledger_failure_refuses_and_mints_nothing(tmp_path: Path) -> None:
    """§7.2 K3 — *"If the write fails, the Kernel refuses and **nothing
    executes**."* §11.3 — fail closed, no buffering."""
    kernel, _ = build(tmp_path, ledger=BrokenLedger(JsonFileStateStore(tmp_path)))
    refusal = kernel.authorize(request())
    assert isinstance(refusal, KernelRefusal)
    assert refusal.reason is RefusalReason.LEDGER_UNAVAILABLE
    assert refusal.failed_check is KernelCheck.K3_RECEIPT_INTENT_WRITE
    assert refusal.attestor is None
    assert kernel.outstanding_count == 0


def test_a_refused_request_writes_nothing(tmp_path: Path) -> None:
    """K3 runs last: a request refused at K1 never reaches the ledger."""
    kernel, ledger = build(tmp_path)
    refusal = kernel.authorize(request(objective_id="obj-missing"))
    assert isinstance(refusal, KernelRefusal)
    assert len(ledger) == 0
    assert kernel.outstanding_count == 0


def test_an_unattested_request_writes_nothing(tmp_path: Path) -> None:
    kernel, ledger = build(tmp_path)
    assert isinstance(kernel.authorize(request(attestations=())), KernelRefusal)
    assert len(ledger) == 0


# ======================================================================
# Referential integrity and impossible states
# ======================================================================


def test_every_minted_warrant_has_an_intent_record(tmp_path: Path) -> None:
    """§9.2's graph, and §9.5's gap made unreachable."""
    kernel, ledger = build(tmp_path)
    for i in range(3):
        w = kernel.authorize(request(payload_digest=f"sha256:{i}"))
        assert ledger.has_intent(w.warrant_id)
    assert len(ledger) == kernel.outstanding_count == 3


def test_the_ledger_never_holds_an_orphan(tmp_path: Path) -> None:
    """A record with no warrant cannot arise: the `Warrant` is built
    before the write, so a construction failure writes nothing."""
    kernel, ledger = build(tmp_path, ceiling=ReversibilityClass.READ_ONLY)
    with pytest.raises(InvalidWarrant):
        kernel.authorize(
            request(reversibility_class=ReversibilityClass.IRREVERSIBLE)
        )
    assert len(ledger) == 0


def test_one_warrant_authorizes_one_action(tmp_path: Path) -> None:
    """§4.4 — *"Can two executions share one? **No.**"* Distinct requests
    mint distinct warrants."""
    kernel, _ = build(tmp_path)
    a = kernel.authorize(request(payload_digest="sha256:one"))
    b = kernel.authorize(request(payload_digest="sha256:two"))
    assert a.warrant_id != b.warrant_id
    assert kernel.outstanding_count == 2


def test_a_second_mint_never_reuses_an_id(tmp_path: Path) -> None:
    """A duplicate id would be refused by `_register` — and the sequence
    makes it unreachable."""
    kernel, _ = build(tmp_path)
    ids = {kernel.authorize(request(payload_digest=f"s:{i}")).warrant_id
           for i in range(5)}
    assert len(ids) == 5


def test_the_same_request_twice_mints_two_distinct_warrants(
    tmp_path: Path,
) -> None:
    """§8.2 — a repeat is a second action, not the same one. Each gets its
    own intent record."""
    kernel, ledger = build(tmp_path)
    a = kernel.authorize(request())
    b = kernel.authorize(request())
    assert a.warrant_id != b.warrant_id
    assert len(ledger) == 2


def test_registration_refuses_a_duplicate_warrant(tmp_path: Path) -> None:
    kernel, _ = build(tmp_path)
    w = kernel.authorize(request())
    with pytest.raises(InvalidKernel, match="already outstanding"):
        kernel._register(w)


# ======================================================================
# Serialization
# ======================================================================


def test_the_warrant_serialises_deterministically(tmp_path: Path) -> None:
    a, _ = build(tmp_path / "a")
    b, _ = build(tmp_path / "b")
    assert a.authorize(request()).as_dict() == b.authorize(request()).as_dict()


def test_the_warrant_serialisation_is_json_ready(tmp_path: Path) -> None:
    kernel, _ = build(tmp_path)
    assert json.loads(json.dumps(kernel.authorize(request()).as_dict()))


def test_the_intent_record_survives_a_ledger_restart(tmp_path: Path) -> None:
    """The audit spine outlives the process."""
    kernel, _ = build(tmp_path)
    w = kernel.authorize(request())
    reread = ReceiptLedger(JsonFileStateStore(tmp_path))
    assert reread.has_intent(w.warrant_id)
    assert reread.read(w.warrant_id)[0].expected_effect == "the folder is gone"


def test_the_budget_survives_serialisation(tmp_path: Path) -> None:
    kernel, _ = build(tmp_path)
    w = kernel.authorize(
        request(reversibility_class=ReversibilityClass.IRREVERSIBLE)
    )
    assert w.as_dict()["attempt_budget"] == 1


# ======================================================================
# CONSTITUTIONAL — nothing beyond Part 5
# ======================================================================


def test_no_operation_remains_unimplemented(
    tmp_path: Path,
) -> None:
    """`invalidate()` left this set in Part 8, and it was the last."""
    kernel, _ = build(tmp_path)
    kernel.authorize(request())
    assert kernel.invalidate("all", "founder override") == 1


def test_the_public_surface_is_unchanged(tmp_path: Path) -> None:
    surface = {n for n in dir(Kernel) if not n.startswith("_")}
    assert surface == {
        "authorize", "attempt", "settle", "invalidate",
        "override", "outstanding_count",
    }


def test_the_mint_publishes_nothing() -> None:
    """The Event Bus is not wired; §10.3 makes zero subscribers valid.

    Checked against imports and the public surface, not prose."""
    assert "events" not in " ".join(_kernel_imports())
    assert not any(
        "publish" in n.lower() for n in dir(Kernel) if not n.startswith("__")
    )


def test_the_mint_holds_no_attestor() -> None:
    """§7.3 — still true after the mint. The class came from the request,
    so the Kernel still consults no attestor."""
    imported = " ".join(_kernel_imports())
    for owner in ("reversibility", "permissions", "broker", "mission_control"):
        assert owner not in imported


def test_the_budget_is_never_overridden_by_a_caller(tmp_path: Path) -> None:
    """§8.5 — *"never by the retry loop."* There is no parameter for it."""
    import inspect

    assert list(inspect.signature(Kernel.authorize).parameters) == [
        "self", "request",
    ]


def test_an_intelligence_mint_requires_all_eight_attestations(
    tmp_path: Path,
) -> None:
    """§7.4's two-attestation difference, at the mint."""
    kernel, ledger = build(tmp_path)
    local_only = tuple(attest(q) for q in LOCAL_QUESTIONS)
    refusal = kernel.authorize(
        request(ActionClass.INTELLIGENCE, attestations=local_only)
    )
    assert isinstance(refusal, KernelRefusal)
    assert refusal.failed_check is AttestationQuestion.PROVIDER
    assert len(ledger) == 0


def test_the_budget_amount_is_untouched_by_the_mint(tmp_path: Path) -> None:
    """§3.4 — budgets belong to the Broker. The Kernel reads the
    objective's envelope and never spends against it."""
    kernel, _ = build(tmp_path)
    kernel.authorize(request())
    record = kernel._admission_for("obj-1")
    assert record.budget == Decimal("100.00")
