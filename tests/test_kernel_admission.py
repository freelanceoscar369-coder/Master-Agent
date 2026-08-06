"""Sprint 1, Component 15 Part 2 — K1, the admission gate.

**Founder Decision, 2026-08-06**, superseding ADR-0021 D5:

> K1 is an admission validation only. It refuses on **objective missing ·
> objective unknown · objective terminal**, and **shall not enforce
> `EXECUTING`**. `ObjectiveState == EXECUTING` is a *minting* prerequisite,
> not an admission prerequisite.

| Check | Question | Where |
|---|---|---|
| **K1** | Is this objective admitted and not finished? | structural |
| **Mint** | Is this objective running right now? | lifecycle — **not here** |

Every test names the clause it defends. Nothing here reads a wall clock.
"""
from __future__ import annotations

import ast
import inspect
from datetime import UTC, datetime
from pathlib import Path

import pytest

from master_agent.foundation.admission import ObjectiveState
from master_agent.foundation.clock import ManualClock
from master_agent.foundation.execution_request import (
    PENDING_CONSEQUENCE_ENGINE,
    ActionClass,
    ExecutionRequest,
    InvalidExecutionRequest,
)
from master_agent.foundation.refusal import (
    KernelCheck,
    KernelRefusal,
    RefusalFamily,
    RefusalReason,
)
from master_agent.foundation.warrant import ReversibilityClass, Warrant
from master_agent.kernel import AdmissionProvider, InvalidKernel, Kernel
from master_agent.ledger.receipt_ledger import ReceiptLedger
from master_agent.persistence.store import JsonFileStateStore
from tests.kernel_test_support import (
    FailingAdmissions,
    StubAdmissions,
    admission,
)

T0 = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)

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


def request(objective_id: str = "obj-1", **overrides) -> ExecutionRequest:
    defaults = {
        "objective_id": objective_id,
        "principal_id": "founder",
        "capability": "Filesystem.DeleteFolder",
        "payload_digest": "sha256:abc",
        "action_class": ActionClass.LOCAL,
        "reversibility_class": ReversibilityClass.REVERSIBLE,
        "expected_effect": "the folder is gone",
        "consequence": PENDING_CONSEQUENCE_ENGINE,
    }
    return ExecutionRequest(**{**defaults, **overrides})


def warrant(warrant_id: str = "wrt-1") -> Warrant:
    return Warrant(
        warrant_id=warrant_id,
        objective_id="obj-1",
        principal_id="founder",
        capability="Filesystem.DeleteFolder",
        payload_digest="sha256:abc",
        reversibility_class=ReversibilityClass.REVERSIBLE,
        consequence_ceiling=ReversibilityClass.REVERSIBLE,
        attempt_budget=3,
        issued_at=T0,
        expires_at=datetime(2026, 8, 6, 13, 0, tzinfo=UTC),
    )


@pytest.fixture
def ledger(tmp_path: Path) -> ReceiptLedger:
    return ReceiptLedger(JsonFileStateStore(tmp_path))


def build(ledger: ReceiptLedger, *records) -> tuple[Kernel, StubAdmissions]:
    admissions = StubAdmissions(*(records or (admission(),)))
    return (
        Kernel(clock=ManualClock(T0), ledger=ledger, admission=admissions),
        admissions,
    )


# ======================================================================
# The admission provider — R28's boundary
# ======================================================================


def test_admission_is_a_kernel_dependency_not_a_request_field() -> None:
    """Founder decision R28: admission stays **outside** the
    `ExecutionRequest` boundary. A request carrying its own admission
    would let a caller assert the very thing K1 exists to check."""
    fields = {f.name for f in ExecutionRequest.__dataclass_fields__.values()}
    assert not any(
        w in n for n in fields for w in ("admission", "objective_state", "state")
    )
    assert "admission" in inspect.signature(Kernel.__init__).parameters


def test_the_provider_is_validated_at_construction(ledger: ReceiptLedger) -> None:
    with pytest.raises(InvalidKernel, match="AdmissionProvider"):
        Kernel(clock=ManualClock(T0), ledger=ledger, admission=object())


def test_a_stub_satisfies_the_protocol() -> None:
    """Validated against the protocol, not a concrete class."""
    assert isinstance(StubAdmissions(), AdmissionProvider)


def test_the_kernel_never_imports_the_objective_engine() -> None:
    """§10.1 — the Engine publishes; the Kernel reads. This is why C15
    ships before C17."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    imported = [
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    ]
    assert not any("objective" in n.lower() for n in imported)


def test_the_lookup_asks_the_provider_for_the_requests_objective(
    ledger: ReceiptLedger,
) -> None:
    kernel, admissions = build(ledger)
    kernel._check_objective_binding(request("obj-1"))
    assert admissions.lookups == ["obj-1"]


def test_the_lookup_is_not_cached(ledger: ReceiptLedger) -> None:
    """A cached admission is an authority that outlives its source — the
    defect §11.1 names for permissions. §10.2's diagram has the state
    changing under the Kernel's feet."""
    kernel, admissions = build(ledger, admission(state=ObjectiveState.READY))
    first = kernel._check_objective_binding(request())
    assert not isinstance(first, KernelRefusal)

    admissions.publish(admission(state=ObjectiveState.COMPLETED))
    second = kernel._check_objective_binding(request())
    assert isinstance(second, KernelRefusal)
    assert second.reason is RefusalReason.OBJECTIVE_TERMINAL
    assert admissions.lookups == ["obj-1", "obj-1"]


def test_a_withdrawn_objective_stops_passing(ledger: ReceiptLedger) -> None:
    kernel, admissions = build(ledger)
    assert not isinstance(kernel._check_objective_binding(request()), KernelRefusal)
    admissions.withdraw("obj-1")
    refusal = kernel._check_objective_binding(request())
    assert refusal.reason is RefusalReason.OBJECTIVE_UNKNOWN


# ======================================================================
# K1 passes — every non-terminal state, including READY and WAITING
# ======================================================================


@pytest.mark.parametrize("state", NON_TERMINAL)
def test_every_non_terminal_state_passes_k1(state, ledger: ReceiptLedger) -> None:
    """**The founder decision, stated as a test.** `READY` and `WAITING`
    are non-terminal and pass. K1 does not enforce `EXECUTING`."""
    kernel, _ = build(ledger, admission(state=state))
    result = kernel._check_objective_binding(request())
    assert not isinstance(result, KernelRefusal)
    assert result.state is state


def test_a_ready_objective_is_not_refused(ledger: ReceiptLedger) -> None:
    """The case that superseded ADR-0021 D5. Refusing it would need a
    `RefusalReason` C8 does not have, and C8 is frozen."""
    kernel, _ = build(ledger, admission(state=ObjectiveState.READY))
    assert not isinstance(
        kernel._check_objective_binding(request()), KernelRefusal
    )


def test_a_waiting_objective_is_not_refused(ledger: ReceiptLedger) -> None:
    """§8.1 — waiting must not look like failure."""
    kernel, _ = build(ledger, admission(state=ObjectiveState.WAITING))
    assert not isinstance(
        kernel._check_objective_binding(request()), KernelRefusal
    )


def test_k1_never_consults_is_executing(ledger: ReceiptLedger) -> None:
    """Lifecycle admission belongs to the mint path. If K1 read
    `is_executing`, `READY` and `EXECUTING` would differ here — they must
    not."""
    ready, _ = build(ledger, admission(state=ObjectiveState.READY))
    executing, _ = build(ledger, admission(state=ObjectiveState.EXECUTING))
    a = ready._check_objective_binding(request())
    b = executing._check_objective_binding(request())
    assert not isinstance(a, KernelRefusal)
    assert not isinstance(b, KernelRefusal)


def test_the_source_never_reads_is_executing() -> None:
    """Structural: the property exists on `AdmissionRecord` and Part 2
    must not touch it. The mint path will."""
    assert "is_executing" not in MODULE.read_text(encoding="utf-8")


# ======================================================================
# K1 refuses — the three §7.2 conditions, and only those
# ======================================================================


def test_an_unknown_objective_is_refused(ledger: ReceiptLedger) -> None:
    kernel, _ = build(ledger)
    refusal = kernel._check_objective_binding(request("obj-missing"))
    assert isinstance(refusal, KernelRefusal)
    assert refusal.reason is RefusalReason.OBJECTIVE_UNKNOWN
    assert refusal.failed_check is KernelCheck.K1_OBJECTIVE_BINDING
    assert "obj-missing" in refusal.detail


@pytest.mark.parametrize("state", TERMINAL)
def test_every_terminal_state_is_refused(state, ledger: ReceiptLedger) -> None:
    """§7.2 — *"objective already completed, failed, or cancelled."*"""
    kernel, _ = build(ledger, admission(state=state))
    refusal = kernel._check_objective_binding(request())
    assert isinstance(refusal, KernelRefusal)
    assert refusal.reason is RefusalReason.OBJECTIVE_TERMINAL
    assert state.value in refusal.detail


def test_the_partition_is_exactly_terminal_versus_not(
    ledger: ReceiptLedger,
) -> None:
    """No state falls between passing and refusing."""
    refused, passed = set(), set()
    for state in ObjectiveState:
        kernel, _ = build(ledger, admission(state=state))
        result = kernel._check_objective_binding(request())
        (refused if isinstance(result, KernelRefusal) else passed).add(state)
    assert refused == set(TERMINAL)
    assert passed == set(NON_TERMINAL)


def test_a_terminal_refusal_is_not_remediable(ledger: ReceiptLedger) -> None:
    """A finished objective does not become unfinished; the action needs a
    new one."""
    kernel, _ = build(ledger, admission(state=ObjectiveState.COMPLETED))
    assert kernel._check_objective_binding(request()).remediable is False


def test_an_unknown_refusal_is_remediable(ledger: ReceiptLedger) -> None:
    """Admitting the objective would let the same request succeed."""
    kernel, _ = build(ledger)
    assert kernel._check_objective_binding(request("nope")).remediable is True


def test_a_k1_refusal_names_no_attestor(ledger: ReceiptLedger) -> None:
    """§7.2 — the three checks are the Kernel's own domain. Amendment 001
    M5: *"a refusal from K1 has no attestor, because no attestor was
    involved."*"""
    kernel, _ = build(ledger)
    assert kernel._check_objective_binding(request("nope")).attestor is None


def test_a_k1_refusal_is_a_kernel_check(ledger: ReceiptLedger) -> None:
    kernel, _ = build(ledger)
    refusal = kernel._check_objective_binding(request("nope"))
    assert refusal.family is RefusalFamily.KERNEL_CHECK


def test_objective_missing_is_prevented_rather_than_detected() -> None:
    """§7.2's first refusal is unreachable from K1: `ExecutionRequest`
    refuses a blank `objective_id` at construction. C8 keeps the reason
    for callers C9 does not guard — C17's admission path among them."""
    with pytest.raises(InvalidExecutionRequest, match="objective_id"):
        request("")
    assert RefusalReason.OBJECTIVE_MISSING in set(RefusalReason)


def test_no_new_refusal_reason_was_added() -> None:
    """The founder decision turned on this: C8 stays frozen."""
    assert len(RefusalReason) == 11
    objective_reasons = {
        r for r in RefusalReason if r.value.startswith("objective_")
    }
    assert objective_reasons == {
        RefusalReason.OBJECTIVE_MISSING,
        RefusalReason.OBJECTIVE_UNKNOWN,
        RefusalReason.OBJECTIVE_TERMINAL,
    }


# ======================================================================
# The record is returned, not discarded
# ======================================================================


def test_a_passing_check_returns_the_admission_record(
    ledger: ReceiptLedger,
) -> None:
    """The mint path needs the envelope it carries; reading it twice would
    invite the two reads to disagree."""
    record = admission(state=ObjectiveState.EXECUTING)
    kernel, _ = build(ledger, record)
    assert kernel._check_objective_binding(request()) is record


def test_the_returned_record_carries_the_envelope(ledger: ReceiptLedger) -> None:
    """§10.3 — budget, deadline and consequence_ceiling bound every
    warrant minted under this objective."""
    kernel, _ = build(ledger)
    record = kernel._check_objective_binding(request())
    assert record.consequence_ceiling is ReversibilityClass.REVERSIBLE
    assert record.budget is not None
    assert record.deadline is not None


# ======================================================================
# Failure behaviour — fail closed, and never as a refusal
# ======================================================================


def test_a_provider_failure_propagates(ledger: ReceiptLedger) -> None:
    """Fail closed: nothing is minted. And **not** a `KernelRefusal` — a
    refusal is a decision the Kernel made and records (§7.5); an
    unreachable provider is not a decision, and recording it as one would
    put a falsehood in the ledger."""
    kernel = Kernel(
        clock=ManualClock(T0), ledger=ledger, admission=FailingAdmissions()
    )
    with pytest.raises(RuntimeError, match="unreachable"):
        kernel._check_objective_binding(request())


def test_a_provider_failure_registers_nothing(ledger: ReceiptLedger) -> None:
    kernel = Kernel(
        clock=ManualClock(T0), ledger=ledger, admission=FailingAdmissions()
    )
    with pytest.raises(RuntimeError):
        kernel._check_objective_binding(request())
    assert kernel.outstanding_count == 0


def test_k1_writes_nothing_to_the_ledger(ledger: ReceiptLedger) -> None:
    """K3 is the write, and it runs last. K1 is a read."""
    kernel, _ = build(ledger)
    kernel._check_objective_binding(request())
    kernel._check_objective_binding(request("nope"))
    assert len(ledger) == 0


def test_k1_registers_nothing(ledger: ReceiptLedger) -> None:
    """Passing K1 is not authorization; nothing is minted here."""
    kernel, _ = build(ledger)
    kernel._check_objective_binding(request())
    assert kernel.outstanding_count == 0


# ======================================================================
# Outstanding intent registration — §3.3's Intent lifecycle
# ======================================================================


def test_a_warrant_can_be_registered(ledger: ReceiptLedger) -> None:
    kernel, _ = build(ledger)
    kernel._register(warrant())
    assert kernel.outstanding_count == 1
    assert kernel._is_outstanding("wrt-1")


def test_registration_is_bookkeeping_not_minting(ledger: ReceiptLedger) -> None:
    """The caller has already decided; `_register` takes a warrant that
    exists. Nothing is created here."""
    assert list(inspect.signature(Kernel._register).parameters) == [
        "self", "warrant",
    ]


def test_a_warrant_is_registered_once(ledger: ReceiptLedger) -> None:
    """§4.4 — *"Can two executions share one? **No.**"* A second
    registration would silently replace the first."""
    kernel, _ = build(ledger)
    kernel._register(warrant())
    with pytest.raises(InvalidKernel, match="already outstanding"):
        kernel._register(warrant())
    assert kernel.outstanding_count == 1


def test_distinct_warrants_accumulate(ledger: ReceiptLedger) -> None:
    kernel, _ = build(ledger)
    kernel._register(warrant("wrt-1"))
    kernel._register(warrant("wrt-2"))
    assert kernel.outstanding_count == 2


def test_registration_refuses_a_non_warrant(ledger: ReceiptLedger) -> None:
    kernel, _ = build(ledger)
    with pytest.raises(InvalidKernel, match="Warrant"):
        kernel._register("wrt-1")
    assert kernel.outstanding_count == 0


def test_an_unregistered_warrant_is_not_outstanding(ledger: ReceiptLedger) -> None:
    kernel, _ = build(ledger)
    assert not kernel._is_outstanding("wrt-1")


def test_registration_writes_nothing_to_the_ledger(ledger: ReceiptLedger) -> None:
    """The receipt write is K3's, and it precedes the mint."""
    kernel, _ = build(ledger)
    kernel._register(warrant())
    assert len(ledger) == 0


# ======================================================================
# Override interaction is read-only
# ======================================================================


def test_the_override_is_readable(ledger: ReceiptLedger) -> None:
    kernel, _ = build(ledger)
    assert not kernel.override.is_suspended


def test_nothing_in_part_2_mutates_the_override(ledger: ReceiptLedger) -> None:
    """K2 is a separate check and belongs to a later part. Part 2 reads
    the switch and never writes it."""
    kernel, _ = build(ledger)
    before = kernel.override
    kernel._check_objective_binding(request())
    kernel._check_objective_binding(request("nope"))
    kernel._register(warrant())
    assert kernel.override is before
    assert not kernel.override.is_suspended


def test_k1_does_not_consult_the_override(ledger: ReceiptLedger) -> None:
    """§7.2 keeps K1 and K2 separate. A suspended Kernel must still refuse
    an unknown objective *for being unknown* — the most fundamental
    reason, per §7.1's ordering principle."""
    kernel, _ = build(ledger)
    object.__setattr__(
        kernel, "_override", kernel.override.suspend("founder override")
    )
    refusal = kernel._check_objective_binding(request("nope"))
    assert refusal.reason is RefusalReason.OBJECTIVE_UNKNOWN
    assert refusal.reason is not RefusalReason.OVERRIDE_ACTIVE


def test_no_override_writer_exists_on_the_public_surface() -> None:
    surface = {n for n in dir(Kernel) if not n.startswith("_")}
    assert not any(
        w in n.lower() for n in surface for w in ("suspend", "resume")
    )


# ======================================================================
# CONSTITUTIONAL
# ======================================================================

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE = REPO_ROOT / "src" / "master_agent" / "kernel" / "kernel.py"


def test_part_2_added_no_public_method() -> None:
    """The surface is still §3.5's four plus Part 1's two readers. K1,
    lookup and registration are internal — they are steps of `authorize`,
    not operations a caller invokes."""
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
    """§7.3 — the Kernel verifies attestations and never re-derives a
    verdict. `admission` is K1's own source, which §7.2 assigns to the
    Kernel; it is not one of §7.3's eight."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    imported = [
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    ]
    forbidden = ("reversibility", "permissions", "broker", "mission_control")
    assert not any(f in n for n in imported for f in forbidden)


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
