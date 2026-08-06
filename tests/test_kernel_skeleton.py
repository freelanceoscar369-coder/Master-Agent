"""Sprint 1, Component 15 Part 1 — Kernel skeleton.

**Part 1 is structure only.** These tests prove two things: that the
structure the Kernel Specification requires is present, and — just as
important — that **no behaviour arrived early**.

The clauses under test:

| Source | Requirement |
|---|---|
| §3.1 | Compliance is a property of structure, not diligence |
| §3.3 | The Kernel owns the Intent lifecycle and the Override switch |
| §3.4 | The long list of what it must **not** own |
| §3.5 | Exactly four operations. **There is no `execute()`** |
| §3.6 | Dependency direction is strictly downward |
| §7.3 | It verifies attestations; it never re-derives a verdict |
| §11.8 | `invalidate()` has no confirmation parameter |
| §14 R9 | The 600-line ceiling |

Nothing here reads a wall clock.
"""
from __future__ import annotations

import ast
import inspect
from datetime import UTC, datetime
from pathlib import Path

import pytest

from master_agent.foundation.clock import Clock, ManualClock
from master_agent.foundation.override import OverrideSwitch
from master_agent.kernel import SCOPE_ALL, InvalidKernel, Kernel
from master_agent.ledger.receipt_ledger import ReceiptLedger
from master_agent.persistence.store import JsonFileStateStore
from tests.kernel_test_support import StubAdmissions, admission

T0 = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)


@pytest.fixture
def ledger(tmp_path: Path) -> ReceiptLedger:
    return ReceiptLedger(JsonFileStateStore(tmp_path))


@pytest.fixture
def clock() -> ManualClock:
    return ManualClock(T0)


@pytest.fixture
def admissions() -> StubAdmissions:
    return StubAdmissions(admission())


@pytest.fixture
def kernel(
    clock: ManualClock, ledger: ReceiptLedger, admissions: StubAdmissions
) -> Kernel:
    return Kernel(clock=clock, ledger=ledger, admission=admissions)


# ======================================================================
# Construction and dependency wiring
# ======================================================================


def test_a_kernel_can_be_constructed(kernel: Kernel) -> None:
    assert isinstance(kernel, Kernel)


def test_it_takes_exactly_the_three_collaborators_it_needs() -> None:
    """§7.3 is why there are not more: the Kernel verifies attestations
    and never re-derives a verdict, so it holds no attestor. `admission`
    is a read port, not an attestor -- it answers K1, which §7.2 assigns
    to the Kernel itself."""
    params = list(inspect.signature(Kernel.__init__).parameters)
    assert params == ["self", "clock", "ledger", "admission"]


def test_every_dependency_is_required(
    clock: ManualClock, ledger: ReceiptLedger, admissions: StubAdmissions
) -> None:
    with pytest.raises(TypeError):
        Kernel(clock=clock, ledger=ledger)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        Kernel(clock=clock, admission=admissions)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        Kernel(ledger=ledger, admission=admissions)  # type: ignore[call-arg]


@pytest.mark.parametrize("bad", [None, "clock", 42, object()])
def test_a_non_clock_is_refused(
    bad, ledger: ReceiptLedger, admissions: StubAdmissions
) -> None:
    """§4.3 sources `issued_at` and `expires_at` to the Kernel. Every value
    object refuses to read ambient time precisely so that one component
    does."""
    with pytest.raises(InvalidKernel, match="Clock protocol"):
        Kernel(clock=bad, ledger=ledger, admission=admissions)


@pytest.mark.parametrize("bad", [None, "ledger", 42, object()])
def test_a_non_ledger_is_refused(
    bad, clock: ManualClock, admissions: StubAdmissions
) -> None:
    """§7.2 K3 makes the intent write the Kernel's obligation; there is
    nothing to write to without one."""
    with pytest.raises(InvalidKernel, match="ReceiptLedger"):
        Kernel(clock=clock, ledger=bad, admission=admissions)


def test_the_ledger_is_injected_never_constructed() -> None:
    """*"The Kernel owns the obligation; A1 owns the storage."* A Kernel
    that built its own ledger would decide where the audit spine lives."""
    source = MODULE.read_text(encoding="utf-8")
    assert "ReceiptLedger(" not in source
    assert "JsonFileStateStore" not in source


def test_a_manual_clock_satisfies_the_protocol(clock: ManualClock) -> None:
    """The constructor validates against the protocol, not a concrete
    class, so a test clock is as valid as the system one."""
    assert isinstance(clock, Clock)


# ======================================================================
# §3.3 · owned state, at construction
# ======================================================================


def test_the_kernel_starts_unsuspended(kernel: Kernel) -> None:
    """A Kernel that started suspended would refuse every mint with nobody
    having asked for that."""
    assert isinstance(kernel.override, OverrideSwitch)
    assert not kernel.override.is_suspended
    assert kernel.override.reason is None


def test_the_kernel_starts_with_no_outstanding_intents(kernel: Kernel) -> None:
    """§4.1 — an Intent is short-lived. Warrants are minted, never
    restored."""
    assert kernel.outstanding_count == 0


def test_two_kernels_do_not_share_state(
    clock: ManualClock, ledger: ReceiptLedger, admissions: StubAdmissions
) -> None:
    first = Kernel(clock=clock, ledger=ledger, admission=admissions)
    second = Kernel(clock=clock, ledger=ledger, admission=admissions)
    assert first.override == second.override
    assert first._outstanding is not second._outstanding


def test_the_override_is_handed_out_as_an_immutable_value(kernel: Kernel) -> None:
    """A reader cannot suspend autonomy by touching what it was handed."""
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        kernel.override.suspended = True


def test_the_outstanding_collection_is_not_handed_out(kernel: Kernel) -> None:
    """§3.3 assigns the Intent lifecycle to the Kernel. Handing out the
    collection would let a caller reach it."""
    surface = [n for n in dir(Kernel) if not n.startswith("_")]
    assert "outstanding_count" in surface
    assert not any(
        n in surface for n in ("outstanding", "warrants", "intents")
    )


def test_the_kernel_has_no_instance_dict(kernel: Kernel) -> None:
    """`__slots__` — no caller can attach state the Kernel does not own."""
    with pytest.raises(AttributeError):
        kernel.anything = 1


# ======================================================================
# §3.5 · exactly four operations
# ======================================================================

OPERATIONS = ("authorize", "attempt", "settle", "invalidate")


def test_the_four_operations_exist(kernel: Kernel) -> None:
    for name in OPERATIONS:
        assert callable(getattr(kernel, name))


def test_there_is_no_execute() -> None:
    """§3.5 — *"There is no `execute()`. The Kernel is called; it never
    calls."* This one absence is what keeps it independent of execution
    technology."""
    assert not hasattr(Kernel, "execute")
    surface = [n for n in dir(Kernel) if not n.startswith("_")]
    assert not any(
        v in n.lower()
        for n in surface
        for v in ("execute", "run", "invoke", "dispatch", "perform")
    )


def test_the_public_surface_is_exactly_the_four_plus_two_readers() -> None:
    """No speculative method arrived with the skeleton."""
    surface = {n for n in dir(Kernel) if not n.startswith("_")}
    assert surface == {*OPERATIONS, "override", "outstanding_count"}


def test_authorize_takes_an_execution_request() -> None:
    assert list(inspect.signature(Kernel.authorize).parameters) == [
        "self", "request",
    ]


def test_attempt_takes_an_identifier_not_a_warrant() -> None:
    """§3.5 — `attempt(intent_id)`. Amendment 001 M4 turns on this."""
    assert list(inspect.signature(Kernel.attempt).parameters) == [
        "self", "warrant_id",
    ]


def test_settle_takes_an_identifier_and_an_outcome() -> None:
    assert list(inspect.signature(Kernel.settle).parameters) == [
        "self", "warrant_id", "outcome",
    ]


def test_invalidate_takes_a_scope_and_a_reason() -> None:
    """§11.8 — *"`invalidate()` has no confirmation parameter in its
    signature, matching VEDA 04's requirement that none exist."*"""
    assert list(inspect.signature(Kernel.invalidate).parameters) == [
        "self", "scope", "reason",
    ]


def test_no_operation_carries_a_confirmation_or_friction_parameter() -> None:
    """VEDA 04 A3 and §11.8. Checked across all four, not just
    `invalidate`, because friction added anywhere on the path is friction."""
    forbidden = (
        "confirm", "confirmation", "sure", "acknowledge", "force", "yes",
        "consent", "delay", "cooldown", "grace", "throttle", "retry",
    )
    offenders = []
    for name in OPERATIONS:
        for param in inspect.signature(getattr(Kernel, name)).parameters:
            if any(w in param.lower() for w in forbidden):
                offenders.append(f"{name}({param})")
    assert not offenders, f"Kernel has forbidden parameters: {offenders}"


def test_the_scope_constant_names_the_bulk_case() -> None:
    """§11.8 — `invalidate(scope=all, ...)`; §10.5 — an `objective_id` in
    the same position."""
    assert SCOPE_ALL == "all"


# ======================================================================
# No behaviour arrived early
# ======================================================================


@pytest.mark.parametrize("name", OPERATIONS)
def test_every_operation_is_built(name: str) -> None:
    """Parts 5, 6, 7 and 8 completed `authorize`, `attempt`, `settle` and
    `invalidate`. Nothing on §3.5's surface is a placeholder."""
    assert "NotImplementedError" not in inspect.getsource(getattr(Kernel, name))


def test_no_operation_remains_unimplemented(kernel: Kernel) -> None:
    """A `KernelRefusal` is a constitutional decision the Kernel made and
    must record (§7.5). An unbuilt operation is not a decision, and
    returning one would have put a lie in the ledger — Part 8 removes the
    question by removing the last unbuilt operation."""
    assert MODULE.read_text(encoding="utf-8").count(
        "raise NotImplementedError"
    ) == 0
    assert kernel.invalidate(SCOPE_ALL, "founder override") == 0


def test_construction_changes_no_state(kernel: Kernel) -> None:
    """*"No state transitions beyond construction."*"""
    assert kernel.outstanding_count == 0
    assert not kernel.override.is_suspended


def test_construction_writes_nothing_to_the_ledger(
    clock: ManualClock, ledger: ReceiptLedger, admissions: StubAdmissions
) -> None:
    """K3's write happens at authorize, never at construction."""
    Kernel(clock=clock, ledger=ledger, admission=admissions)
    assert len(ledger) == 0
    assert ledger.read() == ()


def test_construction_reads_no_clock(
    clock: ManualClock, ledger: ReceiptLedger, admissions: StubAdmissions
) -> None:
    """A moment read at construction would be a moment nothing asked for.
    `ManualClock` only advances when told, so its reading is observable."""
    before = clock.now()
    Kernel(clock=clock, ledger=ledger, admission=admissions)
    assert clock.now() == before


# ======================================================================
# CONSTITUTIONAL — §3.4 and §3.6
# ======================================================================

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE = REPO_ROOT / "src" / "master_agent" / "kernel" / "kernel.py"


def _module_imports() -> list[str]:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    return imported


def test_it_holds_no_attestor() -> None:
    """§7.3 — *"It never re-derives the verdict."* §1.2 — attestation, not
    reimplementation. Holding any of these would be the reimplementation
    §3.4's table names the real owner of."""
    forbidden = (
        "reversibility",
        "permissions",
        "broker",
        "mission_control",
        "capabilities",
    )
    offenders = [
        n for n in _module_imports() if any(f in n for f in forbidden)
    ]
    assert not offenders, f"kernel.py imports an attestor: {offenders}"


def test_it_imports_no_worker_provider_or_capability() -> None:
    """§3.6 — *"The Kernel imports no Worker, no Provider, no Environment,
    and no concrete capability."*"""
    forbidden = (
        "master_agent.executor",
        "master_agent.orchestrator",
        "master_agent.runtime",
        "master_agent.plugins",
        "master_agent.planner",
        "master_agent.verification",
        "master_agent.providers",
        "master_agent.missions",
        "subprocess",
        "socket",
    )
    offenders = [
        n for n in _module_imports() if any(n.startswith(f) for f in forbidden)
    ]
    assert not offenders, f"kernel.py imports {offenders}"


def test_it_does_not_import_the_objective_engine() -> None:
    """§10.1 — the Objective Engine publishes an AdmissionRecord; the
    Kernel reads the record, never the Engine. This is why C15 can ship
    before C17."""
    assert not any("objective" in n.lower() for n in _module_imports())


def test_it_depends_only_on_foundation_and_the_ledger() -> None:
    """Dependency direction is strictly downward (§3.6)."""
    internal = {n for n in _module_imports() if n.startswith("master_agent")}
    assert all(
        n.startswith(("master_agent.foundation.", "master_agent.ledger."))
        for n in internal
    ), internal


def test_it_reads_no_ambient_time() -> None:
    """It holds the canonical Clock; it never bypasses it."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    banned = {"datetime.now", "datetime.utcnow", "datetime.today", "time.time"}
    calls = [
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ".".join(ast.unparse(node.func).split(".")[-2:]) in banned
    ]
    assert not calls, f"kernel.py reads ambient time: {calls}"


def test_it_opens_no_file_and_touches_no_store() -> None:
    """§3.4 — receipt **storage** belongs to A1."""
    assert "master_agent.persistence" not in _module_imports()
    source = MODULE.read_text(encoding="utf-8")
    assert "open(" not in source


def test_it_holds_nothing_section_3_4_assigns_elsewhere() -> None:
    """Budgets, occupancy, providers, capability resolution, verification,
    narration — every one has a named owner.

    `_attempts` arrived with Part 6 and is **not** one of them: §3.3
    assigns the Intent's *lifecycle* to the Kernel, and §4.4's *"one
    Intent, N attempts"* is that lifecycle. It is a count, never a record
    — §3.4's receipt storage stays A1's, and the `AttemptRecord` goes to
    the ledger."""
    slots = set(Kernel.__slots__)
    assert slots == {
        "_admission", "_attempts", "_clock", "_ledger", "_override",
        "_outstanding",
    }


def test_it_is_within_the_six_hundred_line_ceiling() -> None:
    """§14 R9 — *"if the Kernel exceeds roughly 600 lines, something in it
    belongs somewhere else."* Read as executable lines: documentation is
    not what the ceiling is about."""
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


def test_it_is_exported_from_its_package() -> None:
    from master_agent.kernel import Kernel as Exported

    assert Exported is Kernel
