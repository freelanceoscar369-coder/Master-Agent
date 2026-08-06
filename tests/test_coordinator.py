"""Sprint 1, Component 16 — the Execution Coordinator.

§6.1's exit protocol, composed once:

```
   intent = kernel.authorize(request)      # may refuse
   token  = kernel.attempt(intent.id)      # may refuse: expired, over budget
   result = <<the caller's own execution, entirely its own business>>
   kernel.settle(intent.id, outcome)       # mandatory
```

| Source | Requirement |
|---|---|
| §3.4 | *"Retry mechanics. The Runtime… it does not loop"* |
| §3.5 | The four operations this composes, and the absence of a fifth |
| §4.4 | An unsettled intent is *"a first-class defect"* |
| §4.5 | An unattempted warrant goes to EXPIRED, never to SETTLED |
| §6.1 | The order, and that the caller executes |
| §6.3 | Settlement is mandatory; the four kinds; `unknown` escalates |
| §8.1 | *"There was nothing for the loop to be bounded by"* |
| §8.4 | An irreversible action is never automatically retried. Ever |
| §8.5 | The budget is set at mint, never by the retry loop |
| §8.6 | `(warrant_id, attempt_seq)` is what the work receives |
| §11.5 | Fail closed **before** anything runs |
| ADR-0022 D2 | The caller is a courier for the class, never its author |

The Kernel is real in every test here — never a double. §14 R2:
*"tests obtain intents from a real Kernel over an in-memory ledger."*
"""
from __future__ import annotations

import ast
import inspect
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from master_agent.coordinator import (
    Execution,
    ExecutionCoordinator,
    InvalidCoordinator,
)
from master_agent.coordinator.coordinator import _may_retry
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
from master_agent.foundation.receipt import (
    ExecutionOutcome,
    InvalidReceipt,
    Receipt,
)
from master_agent.foundation.refusal import (
    KernelCheck,
    KernelRefusal,
    RefusalReason,
)
from master_agent.foundation.warrant import ReversibilityClass, Warrant
from master_agent.kernel import SCOPE_ALL, Kernel
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
    / "src" / "master_agent" / "coordinator" / "coordinator.py"
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


class Recorder:
    """A piece of work that remembers how it was called.

    Deliberately dumb: it answers with what the test told it to answer.
    Anything cleverer would start deciding outcomes, which is the whole
    of what §6.1 leaves to the caller.
    """

    def __init__(self, *answers: ExecutionOutcome, raises: Exception | None = None):
        self._answers = list(answers) or [ExecutionOutcome.SUCCEEDED]
        self._raises = raises
        self.tokens: list[AttemptToken] = []

    def __call__(self, token: AttemptToken) -> ExecutionOutcome:
        self.tokens.append(token)
        if self._raises is not None:
            raise self._raises
        index = min(len(self.tokens) - 1, len(self._answers) - 1)
        return self._answers[index]

    @property
    def calls(self) -> int:
        return len(self.tokens)


class AttemptRefusingLedger(ReceiptLedger):
    """Intents land; the attempt write does not. §11.3."""

    def record_attempt(self, record):  # type: ignore[override]
        raise LedgerUnavailable("the receipt ledger could not write: disk gone")


def build(
    tmp_path: Path,
    *,
    ledger: ReceiptLedger | None = None,
    deadline: datetime = DEADLINE,
) -> tuple[ExecutionCoordinator, Kernel, ReceiptLedger, ManualClock]:
    # An empty ReceiptLedger is falsy (`__len__` is 0), so this must be an
    # identity test rather than a truthiness one.
    store = ledger if ledger is not None else ReceiptLedger(
        JsonFileStateStore(tmp_path)
    )
    clock = ManualClock(T0)
    kernel = Kernel(
        clock=clock,
        ledger=store,
        admission=StubAdmissions(
            admission(
                consequence_ceiling=ReversibilityClass.IRREVERSIBLE,
                deadline=deadline,
            )
        ),
    )
    return ExecutionCoordinator(kernel), kernel, store, clock


def _run_source() -> ast.FunctionDef:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "run":
            return node
    raise AssertionError("coordinator.py has no run()")


def _module_imports() -> list[str]:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    return imported


# ======================================================================
# §6.1 · the sequence, in order
# ======================================================================


def test_a_complete_run_settles(tmp_path: Path) -> None:
    coordinator, _, _, _ = build(tmp_path)
    result = coordinator.run(request(), Recorder())

    assert isinstance(result, Execution)
    assert result.authorized
    assert result.settled
    assert result.receipt.outcome is ExecutionOutcome.SUCCEEDED


def test_the_work_receives_the_attempt_token(tmp_path: Path) -> None:
    """§8.6 — *"the Kernel provides the key — `(intent_id, attempt_seq)`
    — and requires Workers to honour it."* Handing the work anything less
    would make that impossible."""
    coordinator, _, _, _ = build(tmp_path)
    work = Recorder()
    result = coordinator.run(request(), work)

    (token,) = work.tokens
    assert isinstance(token, AttemptToken)
    assert token.warrant_id == result.warrant.warrant_id
    assert token.idempotency_key == (result.warrant.warrant_id, 1)


def test_the_records_arrive_in_section_nine_ones_order(tmp_path: Path) -> None:
    """The proof that the sequence ran in order: the ledger's own tree."""
    coordinator, _, ledger, _ = build(tmp_path)
    result = coordinator.run(request(), Recorder())

    kinds = [type(r).__name__ for r in ledger.read(result.warrant.warrant_id)]
    assert kinds == ["IntentRecord", "AttemptRecord", "Receipt"]


def test_the_work_runs_after_the_intent_is_durable(tmp_path: Path) -> None:
    """§7.2 K3 — *"nothing executes without a durable intent."* Observed
    from inside the work, which is the only place that can see it."""
    coordinator, _, ledger, _ = build(tmp_path)
    seen: list[str] = []

    def work(token: AttemptToken) -> ExecutionOutcome:
        seen.extend(type(r).__name__ for r in ledger.read(token.warrant_id))
        return ExecutionOutcome.SUCCEEDED

    coordinator.run(request(), work)
    assert seen == ["IntentRecord", "AttemptRecord"]


def test_the_receipt_is_the_kernels_own(tmp_path: Path) -> None:
    """Nothing is composed here. The `Receipt` returned is the one
    `settle()` produced, unmodified."""
    coordinator, _, ledger, _ = build(tmp_path)
    result = coordinator.run(request(), Recorder())

    assert isinstance(result.receipt, Receipt)
    assert ledger.read(result.warrant.warrant_id)[-1] == result.receipt


# ======================================================================
# §11.5 · nothing runs before a warrant exists
# ======================================================================


def test_a_refusal_never_reaches_the_work(tmp_path: Path) -> None:
    """§11.5's reason for refusing before minting applies with more force
    to refusing before executing."""
    coordinator, _, _, _ = build(tmp_path)
    work = Recorder()
    result = coordinator.run(request(objective_id="obj-unknown"), work)

    assert work.calls == 0
    assert not result.authorized
    assert isinstance(result.refusal, KernelRefusal)
    assert result.refusal.reason is RefusalReason.OBJECTIVE_UNKNOWN


def test_a_refusal_is_data_and_not_an_exception(tmp_path: Path) -> None:
    """§7.5 — *"refusals are data, not exceptions… the founder is reading
    a stack trace from a provider SDK instead of a sentence about their
    own machine."*"""
    coordinator, _, _, _ = build(tmp_path)
    result = coordinator.run(request(objective_id="obj-unknown"), Recorder())

    assert isinstance(result, Execution)
    assert not result.settled
    assert result.attempts == 0


def test_a_suspended_kernel_runs_nothing(tmp_path: Path) -> None:
    """§7.2 K2 — the Override's meaning is that the Kernel stops minting,
    and nothing above it may route around that."""
    coordinator, kernel, ledger, _ = build(tmp_path)
    kernel.invalidate(SCOPE_ALL, "founder override")
    work = Recorder()

    result = coordinator.run(request(), work)
    assert work.calls == 0
    assert result.refusal.reason is RefusalReason.OVERRIDE_ACTIVE
    assert len(ledger) == 0


def test_an_unattested_request_runs_nothing(tmp_path: Path) -> None:
    """§7.3's eight attestations are the Kernel's, and the Coordinator
    neither supplies nor re-verifies one."""
    coordinator, _, _, _ = build(tmp_path)
    work = Recorder()
    thin = request(attestations=tuple(attest(q) for q in LOCAL_QUESTIONS[:3]))

    result = coordinator.run(thin, work)
    assert work.calls == 0
    assert result.refusal.reason is RefusalReason.ATTESTATION_ABSENT


def test_a_refused_attempt_write_runs_nothing(tmp_path: Path) -> None:
    """§11.3 — no attempt record, no attempt. The work is not called on a
    token that was never issued."""
    coordinator, _, _, _ = build(
        tmp_path, ledger=AttemptRefusingLedger(JsonFileStateStore(tmp_path))
    )
    work = Recorder()

    result = coordinator.run(request(), work)
    assert work.calls == 0
    assert result.authorized
    assert result.refusal.reason is RefusalReason.LEDGER_UNAVAILABLE
    assert result.refusal.failed_check is KernelCheck.K3_RECEIPT_INTENT_WRITE
    assert not result.settled


# ======================================================================
# §3.4 · the retry loop lives here, and §8.5's budget bounds it
# ======================================================================


def test_a_failed_reversible_action_is_retried(tmp_path: Path) -> None:
    """§3.4 — *"Retry mechanics. The Runtime."* This is that Runtime."""
    coordinator, _, _, _ = build(tmp_path)
    work = Recorder(ExecutionOutcome.FAILED, ExecutionOutcome.SUCCEEDED)

    result = coordinator.run(request(), work)
    assert work.calls == 2
    assert result.attempts == 2
    assert result.receipt.outcome is ExecutionOutcome.SUCCEEDED


def test_the_loop_stops_at_the_warrants_budget(tmp_path: Path) -> None:
    """§8.1 — *"the root cause is not the loop. It is that there was
    nothing for the loop to be bounded by."* The bound is §8.5's budget,
    and the Kernel refusing a further attempt is what ends the loop."""
    coordinator, _, _, _ = build(tmp_path)
    work = Recorder(ExecutionOutcome.FAILED)

    result = coordinator.run(request(), work)
    assert work.calls == result.warrant.attempt_budget == 3
    assert result.receipt.attempt == 3
    assert result.receipt.outcome is ExecutionOutcome.FAILED


@pytest.mark.parametrize(
    "cls", [ReversibilityClass.READ_ONLY, ReversibilityClass.REVERSIBLE_UNTIL]
)
def test_every_class_is_bounded_by_its_own_budget(
    tmp_path: Path, cls: ReversibilityClass
) -> None:
    """§8.5's table, exercised through the loop rather than read."""
    coordinator, _, _, _ = build(tmp_path)
    work = Recorder(ExecutionOutcome.FAILED)

    result = coordinator.run(request(reversibility_class=cls), work)
    assert work.calls == result.warrant.attempt_budget


def test_the_coordinator_holds_no_counter_of_its_own() -> None:
    """§8.5 — the budget is *"set at mint from the capability's class,
    never by the retry loop."* A counter here would be a second opinion
    about a question the mint already answered."""
    assert set(ExecutionCoordinator.__slots__) == {"_kernel"}
    source = MODULE.read_text(encoding="utf-8")
    assert "attempt_budget" not in _run_source_text()
    assert "ATTEMPT_BUDGET" not in source


def _run_source_text() -> str:
    return ast.unparse(_run_source())


def test_a_success_is_not_retried(tmp_path: Path) -> None:
    coordinator, _, _, _ = build(tmp_path)
    work = Recorder(ExecutionOutcome.SUCCEEDED)

    coordinator.run(request(), work)
    assert work.calls == 1


def test_the_ledger_records_one_attempt_per_call(tmp_path: Path) -> None:
    """§9.1's `AttemptRecord (0..n)` — the loop must not open attempts the
    work never saw, nor run work on attempts nobody recorded."""
    coordinator, _, ledger, _ = build(tmp_path)
    work = Recorder(ExecutionOutcome.FAILED)

    result = coordinator.run(request(), work)
    records = [
        r for r in ledger.read(result.warrant.warrant_id)
        if isinstance(r, AttemptRecord)
    ]
    assert len(records) == work.calls
    assert [r.attempt_seq for r in records] == [1, 2, 3]


# ======================================================================
# §8.4 · the clause that is never negotiable
# ======================================================================


def test_an_irreversible_action_is_never_retried(tmp_path: Path) -> None:
    """§8.4 — *"An action classified `irreversible` is never automatically
    retried. Ever. Regardless of attempt budget, error class, or how
    transient the failure appears."*"""
    coordinator, _, _, _ = build(tmp_path)
    work = Recorder(ExecutionOutcome.FAILED)

    result = coordinator.run(
        request(reversibility_class=ReversibilityClass.IRREVERSIBLE), work
    )
    assert work.calls == 1
    assert result.receipt.outcome is ExecutionOutcome.FAILED


def test_the_irreversible_rule_is_checked_before_the_budget() -> None:
    """*"Regardless of attempt budget"* means the decision not to ask must
    not depend on the Kernel refusing. So the rule lives in the decision
    to ask, and reads the warrant's own class."""
    assert "_may_retry" in _run_source_text()
    decision = inspect.getsource(_may_retry)
    assert "is_irreversible" in decision
    assert "attempt_budget" not in decision


def test_an_irreversible_failure_escalates(tmp_path: Path) -> None:
    """§8.4 — *"an irreversible action failing produces `settle(failed)`
    or `settle(unknown)`, and either escalates as a judgment request."*"""
    coordinator, _, _, _ = build(tmp_path)
    result = coordinator.run(
        request(reversibility_class=ReversibilityClass.IRREVERSIBLE),
        Recorder(ExecutionOutcome.FAILED),
    )
    assert result.requires_escalation


def test_a_reversible_failure_does_not_escalate(tmp_path: Path) -> None:
    """The clause is about irreversibility, not about failure."""
    coordinator, _, _, _ = build(tmp_path)
    result = coordinator.run(request(), Recorder(ExecutionOutcome.FAILED))
    assert not result.requires_escalation


def test_unknown_is_never_retried(tmp_path: Path) -> None:
    """§6.3 — `unknown` is *"never auto-retried (§8.4). Escalates."*"""
    coordinator, _, _, _ = build(tmp_path)
    work = Recorder(ExecutionOutcome.UNKNOWN)

    result = coordinator.run(request(), work)
    assert work.calls == 1
    assert result.requires_escalation


def test_unknown_escalates_whatever_the_class(tmp_path: Path) -> None:
    """C5 already answers this as `Receipt.requires_escalation`; nothing
    is re-derived here."""
    coordinator, _, _, _ = build(tmp_path)
    result = coordinator.run(
        request(reversibility_class=ReversibilityClass.READ_ONLY),
        Recorder(ExecutionOutcome.UNKNOWN),
    )
    assert result.receipt.requires_escalation
    assert result.requires_escalation


def test_escalation_is_reported_and_never_raised(tmp_path: Path) -> None:
    """§3.4 gives narration and the founder surface to D1, B2 and VEDA 03.
    A component that manufactured judgment items would build the inbox
    VEDA 03 abolishes."""
    coordinator, _, _, _ = build(tmp_path)
    result = coordinator.run(
        request(reversibility_class=ReversibilityClass.IRREVERSIBLE),
        Recorder(ExecutionOutcome.UNKNOWN),
    )
    assert result.requires_escalation is True
    assert not any(
        w in n.lower()
        for n in dir(ExecutionCoordinator)
        if not n.startswith("_")
        for w in ("escalate", "notify", "judgment", "queue", "publish")
    )


# ======================================================================
# §6.3 · an exception is `unknown`, not `failed`
# ======================================================================


def test_work_that_raises_settles_unknown(tmp_path: Path) -> None:
    """§6.3 — `failed` is *"the effect did not occur, and this is
    known"*; `unknown` is *"the caller cannot determine whether the effect
    occurred."* An unexpected exception establishes the second."""
    coordinator, _, _, _ = build(tmp_path)
    result = coordinator.run(
        request(), Recorder(raises=RuntimeError("the disk went away"))
    )

    assert result.settled
    assert result.receipt.outcome is ExecutionOutcome.UNKNOWN


def test_work_that_raises_is_never_retried(tmp_path: Path) -> None:
    """It settles `unknown`, and §8.4 never auto-retries one."""
    coordinator, _, _, _ = build(tmp_path)
    work = Recorder(raises=RuntimeError("boom"))

    result = coordinator.run(request(), work)
    assert work.calls == 1
    assert result.attempts == 1


def test_the_exception_text_is_not_destroyed(tmp_path: Path) -> None:
    """**R50.** R44 leaves `detail` out of every receipt, so the sentence
    has no home in the permanent record. Carrying it here keeps it from
    being lost entirely. Diagnostic only."""
    coordinator, _, _, _ = build(tmp_path)
    result = coordinator.run(
        request(), Recorder(raises=ValueError("path escaped the workspace"))
    )
    assert result.error == "ValueError: path escaped the workspace"
    assert result.receipt.detail is None


def test_a_raising_work_still_settles_its_intent(tmp_path: Path) -> None:
    """§6.3 — *"settlement is mandatory, and its absence is a defect
    rather than a shrug."* An exception is not an exemption."""
    coordinator, _, ledger, _ = build(tmp_path)
    result = coordinator.run(request(), Recorder(raises=RuntimeError("boom")))
    assert ledger.is_settled(result.warrant.warrant_id)


def test_a_base_exception_is_not_swallowed(tmp_path: Path) -> None:
    """A `KeyboardInterrupt` is not an execution outcome."""
    coordinator, _, _, _ = build(tmp_path)

    def work(token: AttemptToken) -> ExecutionOutcome:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        coordinator.run(request(), work)


def test_an_interrupted_run_leaves_the_intent_outstanding(
    tmp_path: Path,
) -> None:
    """Honest rather than tidy: the intent is unsettled and the Kernel
    still knows it, which is exactly what §9.5 wants to be able to see."""
    coordinator, kernel, ledger, _ = build(tmp_path)

    def work(token: AttemptToken) -> ExecutionOutcome:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        coordinator.run(request(), work)

    assert kernel.outstanding_count == 1
    assert len(ledger) == 2  # intent + attempt, no outcome


# ======================================================================
# R49 · `partial` reaches a settlement C5 refuses to construct
# ======================================================================


def test_a_partial_outcome_cannot_be_settled(tmp_path: Path) -> None:
    """**R49**, which is the shipped **R43** seen from the caller's side.
    §6.3 requires a compensating action reference for `partial` and
    `settle(warrant_id, outcome)` has no parameter for one.

    Not caught here: swallowing it would turn a loud gap into a silent
    one, and the intent would be no more settled for it."""
    coordinator, _, _, _ = build(tmp_path)
    with pytest.raises(InvalidReceipt, match="compensating action"):
        coordinator.run(request(), Recorder(ExecutionOutcome.PARTIAL))


def test_a_partial_outcome_is_never_retried(tmp_path: Path) -> None:
    """*"Some effect occurred"* — doing it again is not a retry. The work
    is called once even though the settlement then fails."""
    coordinator, _, _, _ = build(tmp_path)
    work = Recorder(ExecutionOutcome.PARTIAL)

    with pytest.raises(InvalidReceipt):
        coordinator.run(request(), work)
    assert work.calls == 1


def test_a_partial_outcome_leaves_the_intent_unsettled(
    tmp_path: Path,
) -> None:
    """The consequence of R49, stated by test rather than by prose: the
    warrant is still outstanding and §6.3's mandatory settlement did not
    happen."""
    coordinator, kernel, ledger, _ = build(tmp_path)
    with pytest.raises(InvalidReceipt):
        coordinator.run(request(), Recorder(ExecutionOutcome.PARTIAL))

    assert kernel.outstanding_count == 1
    assert not ledger.is_settled(
        next(
            r.warrant_id for r in ledger.read() if isinstance(r, IntentRecord)
        )
    )


# ======================================================================
# §4.5 · an unattempted warrant is not settled
# ======================================================================


def test_a_window_that_closes_mid_loop_still_settles(tmp_path: Path) -> None:
    """§4.4's window and §8.5's budget are two separate bounds, and the
    loop must respect whichever arrives first.

    The important property is the second half: an expiry between attempts
    ends the loop **and the intent is still settled** with what the last
    attempt found. §6.3 makes that settlement mandatory, and an expiry is
    not an exemption from it."""
    coordinator, _, ledger, clock = build(tmp_path)
    calls: list[int] = []

    def work(token: AttemptToken) -> ExecutionOutcome:
        calls.append(token.attempt_seq)
        clock.advance(timedelta(seconds=31))  # past the LOCAL window
        return ExecutionOutcome.FAILED

    result = coordinator.run(request(), work)

    assert calls == [1]  # the budget was 3; the window ended it first
    assert result.settled
    assert result.receipt.outcome is ExecutionOutcome.FAILED
    assert result.receipt.attempt == 1
    assert ledger.is_settled(result.warrant.warrant_id)


def test_a_warrant_expiring_before_any_attempt_settles_nothing(
    tmp_path: Path,
) -> None:
    """§4.5 sends an unattempted warrant to EXPIRED, never to SETTLED, and
    `settle()` would refuse it. The absence of a settlement is correct
    here, not a defect.

    Reached through the Kernel directly, because `run()` deliberately
    leaves no window between authorization and the first attempt."""
    _, kernel, ledger, clock = build(tmp_path)
    warrant = kernel.authorize(request())
    assert isinstance(warrant, Warrant)

    clock.advance(timedelta(seconds=31))
    assert warrant.is_expired(clock.now())
    assert not ledger.is_settled(warrant.warrant_id)


def test_a_run_that_opened_no_attempt_reports_zero(tmp_path: Path) -> None:
    coordinator, _, _, _ = build(
        tmp_path, ledger=AttemptRefusingLedger(JsonFileStateStore(tmp_path))
    )
    result = coordinator.run(request(), Recorder())
    assert result.attempts == 0
    assert result.receipt is None
    assert not result.settled


# ======================================================================
# It coordinates. It decides nothing.
# ======================================================================


def test_it_mints_nothing(tmp_path: Path) -> None:
    """§3.3 — the Kernel is *"the only minting authority in the
    system."*"""
    source = MODULE.read_text(encoding="utf-8")
    assert "Warrant(" not in source
    assert "IntentRecord" not in source
    assert "AttemptToken(" not in source
    assert "Receipt(" not in source


def test_it_never_writes_to_the_ledger() -> None:
    """§3.4 — receipt storage is A1's, and the obligation to write is the
    Kernel's K3. Neither is this component's."""
    assert not any("ledger" in n.lower() for n in _module_imports())
    source = MODULE.read_text(encoding="utf-8")
    for writer in ("record_intent", "record_attempt", "record_outcome"):
        assert writer not in source


def test_it_reads_no_clock() -> None:
    """Every moment on the record comes from the Kernel's canonical clock.
    A second reader would be a second timeline."""
    assert not any("clock" in n.lower() for n in _module_imports())
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    banned = {"datetime.now", "datetime.utcnow", "datetime.today", "time.time"}
    assert not [
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ".".join(ast.unparse(node.func).split(".")[-2:]) in banned
    ]


def test_it_builds_no_execution_request() -> None:
    """ADR-0022 D2 — *"the caller is a courier, not an author."* A
    Coordinator that built the request would be authoring the very field
    the courier discipline exists to keep honest."""
    source = MODULE.read_text(encoding="utf-8")
    assert "ExecutionRequest(" not in source
    assert list(inspect.signature(ExecutionCoordinator.run).parameters) == [
        "self", "request", "work",
    ]


def test_it_holds_no_attestor() -> None:
    """§7.3 — the answers arrive inside the request and the Kernel checks
    them. Nothing here gathers or verifies one."""
    imported = " ".join(_module_imports())
    for owner in (
        "reversibility", "permissions", "broker", "mission_control",
        "attestation", "admission",
    ):
        assert owner not in imported


def test_it_performs_no_kernel_check() -> None:
    """§7.2's three checks and §7.3's eight attestations are the Kernel's
    alone. Restating one here would be the second opinion §1.2 forbids."""
    source = MODULE.read_text(encoding="utf-8")
    for name in (
        "_check_objective_binding", "_check_override_state",
        "_verify_attestations", "is_suspended", "is_terminal",
        "consequence_ceiling", "exceeds(",
    ):
        assert name not in source


def test_it_does_not_bypass_the_kernel() -> None:
    """Every path to an effect goes through `authorize` → `attempt` →
    `settle`, and there is no other way to reach the work."""
    called = {
        node.func.attr
        for node in ast.walk(_run_source())
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert {"authorize", "attempt", "settle"} <= called


def test_it_never_invalidates(tmp_path: Path) -> None:
    """§11.8's operation is the founder's and the Objective Engine's.
    Orchestration is not a reason to suspend autonomy."""
    assert "invalidate" not in MODULE.read_text(encoding="utf-8")


def test_it_compensates_nothing() -> None:
    """§6.4 — *"Undoing is an action… There is no privileged undo
    path."* A compensation would be a second `run()`, minted like any
    other, and that is the caller's decision to make."""
    called = {
        node.func.attr
        for node in ast.walk(_run_source())
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not any("compensat" in name.lower() for name in called)
    assert not any(
        "compensat" in n.lower() for n in dir(ExecutionCoordinator)
    )


# ======================================================================
# Structure and dependencies
# ======================================================================


def test_it_depends_only_on_foundation_and_the_kernel() -> None:
    """The brief's constraint, and §3.6's dependency direction: strictly
    downward, C1–C15 only."""
    internal = {n for n in _module_imports() if n.startswith("master_agent")}
    assert all(
        n.startswith(("master_agent.foundation.", "master_agent.kernel"))
        for n in internal
    ), internal


def test_it_imports_no_worker_provider_or_environment() -> None:
    """§6.2's fifteen-year property depends on the layers above execution
    knowing nothing about how execution happens. A callable is how this
    one keeps knowing nothing."""
    forbidden = (
        "master_agent.executor", "master_agent.orchestrator",
        "master_agent.runtime", "master_agent.plugins",
        "master_agent.planner", "master_agent.providers",
        "master_agent.ai_infrastructure", "master_agent.missions",
        "master_agent.verification", "master_agent.persistence",
        "subprocess", "socket", "threading", "asyncio",
    )
    assert not [
        n for n in _module_imports() if any(n.startswith(f) for f in forbidden)
    ]


def test_it_holds_one_collaborator_and_no_state() -> None:
    """Two Coordinators over one Kernel are indistinguishable, because
    everything that persists lives below them."""
    assert set(ExecutionCoordinator.__slots__) == {"_kernel"}


def test_two_coordinators_over_one_kernel_agree(tmp_path: Path) -> None:
    """The consequence of holding no state, exercised rather than
    asserted."""
    _, kernel, _, _ = build(tmp_path)
    first = ExecutionCoordinator(kernel)
    second = ExecutionCoordinator(kernel)

    a = first.run(request(), Recorder())
    b = second.run(request(payload_digest="sha256:other"), Recorder())
    assert a.settled and b.settled
    assert a.receipt.correlation_id == b.receipt.correlation_id


def test_it_refuses_a_kernel_that_is_not_one() -> None:
    """At construction, never later — `InvalidKernel`'s own discipline."""
    for bogus in (None, object(), "kernel"):
        with pytest.raises(InvalidCoordinator):
            ExecutionCoordinator(bogus)  # type: ignore[arg-type]


def test_it_refuses_work_that_is_not_callable(tmp_path: Path) -> None:
    coordinator, _, ledger, _ = build(tmp_path)
    with pytest.raises(InvalidCoordinator):
        coordinator.run(request(), "not callable")  # type: ignore[arg-type]
    assert len(ledger) == 0


def test_the_public_surface_is_one_operation() -> None:
    """No speculative API. `run()` and nothing beside it."""
    surface = {n for n in dir(ExecutionCoordinator) if not n.startswith("_")}
    assert surface == {"run"}


def test_the_result_is_immutable(tmp_path: Path) -> None:
    """A report that could be edited after the fact is not a report."""
    from dataclasses import FrozenInstanceError

    coordinator, _, _, _ = build(tmp_path)
    result = coordinator.run(request(), Recorder())
    with pytest.raises(FrozenInstanceError):
        result.attempts = 99


def test_the_result_serialises_deterministically(tmp_path: Path) -> None:
    import json

    coordinator, _, _, _ = build(tmp_path)
    result = coordinator.run(request(), Recorder())
    encoded = json.dumps(result.as_dict(), sort_keys=False)

    assert json.loads(encoded)["attempts"] == 1
    assert result.as_dict() == result.as_dict()


def test_an_empty_result_serialises(tmp_path: Path) -> None:
    """The refusal path must be recordable too."""
    coordinator, _, _, _ = build(tmp_path)
    result = coordinator.run(request(objective_id="obj-unknown"), Recorder())

    projection = result.as_dict()
    assert projection["warrant"] is None
    assert projection["receipt"] is None
    assert projection["refusal"]["reason"] == "objective_unknown"


def test_it_is_exported_from_its_package() -> None:
    from master_agent.coordinator import ExecutionCoordinator as Exported

    assert Exported is ExecutionCoordinator
