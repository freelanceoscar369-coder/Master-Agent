"""Sprint 1, Component 17 — the Kernel API.

§3.5's four operations, projected across one boundary, plus the two facts
§3.3 says the Kernel owns.

| Source | Requirement |
|---|---|
| §3.3 | The Kernel owns the Override switch and the Intent lifecycle |
| §3.5 | Four operations. A fifth is a change to what the Kernel is |
| §3.6 | Dependency direction is strictly downward |
| §7.5 | Refusals are data, not exceptions; a thousand are one state |
| §11.8 | No confirmation parameter, ever |
| §14 R2 | Determinism — no ambient randomness at any layer |
| ADR-0022 D2 | The caller is a courier, never an author |
| Roadmap §2 C21 | No objective count, no progress bar, no badge |

The Kernel is real in every test here — never a double. §14 R2: *"tests
obtain intents from a real Kernel over an in-memory ledger."*
"""
from __future__ import annotations

import ast
import inspect
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from master_agent.api import (
    ApiResponse,
    InvalidKernelApi,
    KernelApi,
    Operation,
    ResultKind,
)
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
from master_agent.foundation.receipt import ExecutionOutcome
from master_agent.foundation.refusal import RefusalReason
from master_agent.foundation.warrant import ReversibilityClass, Warrant
from master_agent.kernel import SCOPE_ALL, Kernel
from master_agent.ledger.receipt_ledger import (
    LedgerUnavailable,
    ReceiptLedger,
)
from master_agent.persistence.store import JsonFileStateStore
from tests.kernel_test_support import StubAdmissions, admission

SRC = Path(__file__).resolve().parent.parent / "src" / "master_agent"
MODULE = SRC / "api" / "kernel_api.py"

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
    """Intents land; the attempt write does not. §11.3."""

    def record_attempt(self, record):  # type: ignore[override]
        raise LedgerUnavailable("the receipt ledger could not write: disk gone")


class OutcomeRefusingLedger(ReceiptLedger):
    """Intents and attempts land; the outcome write does not."""

    def record_outcome(self, receipt):  # type: ignore[override]
        raise LedgerUnavailable("the receipt ledger could not write: disk gone")


def build(
    tmp_path: Path, *, ledger: ReceiptLedger | None = None
) -> tuple[KernelApi, Kernel, ReceiptLedger, ManualClock]:
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
                deadline=DEADLINE,
            )
        ),
    )
    return KernelApi(kernel), kernel, store, clock


def _module_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    return imported


# ======================================================================
# The authorize path
# ======================================================================


def test_authorize_projects_the_warrant(tmp_path: Path) -> None:
    api, _, _, _ = build(tmp_path)
    response = api.authorize(request())

    assert isinstance(response, ApiResponse)
    assert response.operation is Operation.AUTHORIZE
    assert response.kind is ResultKind.OK
    assert response.ok


def test_the_authorize_payload_is_the_warrants_own_projection(
    tmp_path: Path,
) -> None:
    """Nothing is renamed, reordered, flattened or enriched."""
    api, _, _, _ = build(tmp_path)
    direct = Kernel(
        clock=ManualClock(T0),
        ledger=ReceiptLedger(JsonFileStateStore(tmp_path / "b")),
        admission=StubAdmissions(
            admission(
                consequence_ceiling=ReversibilityClass.IRREVERSIBLE,
                deadline=DEADLINE,
            )
        ),
    ).authorize(request())
    assert isinstance(direct, Warrant)

    assert api.authorize(request()).payload == direct.as_dict()


def test_authorize_delegates_and_the_ledger_shows_it(tmp_path: Path) -> None:
    """§7.2 K3 — the intent write is the Kernel's, and the boundary
    neither performs nor duplicates it."""
    api, _, ledger, _ = build(tmp_path)
    assert len(ledger) == 0

    response = api.authorize(request())
    assert len(ledger) == 1
    assert ledger.has_intent(response.payload["warrant_id"])


def test_authorize_takes_the_foundation_value(tmp_path: Path) -> None:
    """ADR-0022 D2 — *"the caller is a courier, not an author."* A
    boundary that assembled the request from wire fields would become the
    author of the very field the courier discipline keeps honest."""
    assert list(inspect.signature(KernelApi.authorize).parameters) == [
        "self", "request",
    ]
    assert "ExecutionRequest(" not in MODULE.read_text(encoding="utf-8")


# ======================================================================
# The attempt path
# ======================================================================


def test_attempt_projects_the_token(tmp_path: Path) -> None:
    api, _, _, _ = build(tmp_path)
    warrant_id = api.authorize(request()).payload["warrant_id"]

    response = api.attempt(warrant_id)
    assert response.operation is Operation.ATTEMPT
    assert response.ok
    assert response.payload == {
        "warrant_id": warrant_id,
        "attempt_seq": 1,
        "opened_at": T0.isoformat(),
    }


def test_attempt_carries_the_idempotency_key(tmp_path: Path) -> None:
    """§8.6 — the key is `(warrant_id, attempt_seq)`, and it must survive
    the boundary or a Worker cannot honour it."""
    api, _, _, _ = build(tmp_path)
    warrant_id = api.authorize(request()).payload["warrant_id"]

    first = api.attempt(warrant_id).payload
    second = api.attempt(warrant_id).payload
    assert (first["warrant_id"], first["attempt_seq"]) == (warrant_id, 1)
    assert (second["warrant_id"], second["attempt_seq"]) == (warrant_id, 2)


def test_attempt_takes_an_identifier_not_a_warrant() -> None:
    """§3.5 — `attempt(intent_id)`. The boundary changes no signature."""
    assert list(inspect.signature(KernelApi.attempt).parameters) == [
        "self", "warrant_id",
    ]


# ======================================================================
# The settle path
# ======================================================================


def test_settle_projects_the_receipt(tmp_path: Path) -> None:
    api, _, ledger, _ = build(tmp_path)
    warrant_id = api.authorize(request()).payload["warrant_id"]
    api.attempt(warrant_id)

    response = api.settle(warrant_id, ExecutionOutcome.SUCCEEDED)
    assert response.operation is Operation.SETTLE
    assert response.ok
    assert response.payload["outcome"] == "succeeded"
    assert response.payload["warrant_id"] == warrant_id
    assert ledger.is_settled(warrant_id)


def test_settle_never_refuses(tmp_path: Path) -> None:
    """§3.5 gives settlement the return type `Receipt` and no refusal
    channel, so this operation produces `OK` or `ERROR` and never
    `REFUSED`."""
    api, _, _, _ = build(tmp_path)
    warrant_id = api.authorize(request()).payload["warrant_id"]

    unattempted = api.settle(warrant_id, ExecutionOutcome.SUCCEEDED)
    assert unattempted.kind is ResultKind.ERROR
    assert unattempted.kind is not ResultKind.REFUSED


def test_settle_takes_the_outcome_vocabulary_unaltered() -> None:
    """§6.3's four kinds are C5's, and the boundary maps none of them to
    a name of its own."""
    assert list(inspect.signature(KernelApi.settle).parameters) == [
        "self", "warrant_id", "outcome",
    ]
    source = MODULE.read_text(encoding="utf-8")
    for kind in ("succeeded", "failed", "partial", "unknown"):
        assert f'"{kind}"' not in source


# ======================================================================
# The invalidate path
# ======================================================================


def test_invalidate_projects_the_count(tmp_path: Path) -> None:
    """§3.5 — `invalidate(scope, reason) → count`."""
    api, _, _, _ = build(tmp_path)
    api.authorize(request())
    api.authorize(request(payload_digest="sha256:other"))

    response = api.invalidate(SCOPE_ALL, "founder override")
    assert response.operation is Operation.INVALIDATE
    assert response.ok
    assert response.payload == {"count": 2}


def test_invalidate_suspends_through_the_boundary(tmp_path: Path) -> None:
    """§11.8 step 1 — the Override's meaning reaches the Kernel intact."""
    api, kernel, _, _ = build(tmp_path)
    api.invalidate(SCOPE_ALL, "I need to think")

    assert kernel.override.is_suspended
    assert kernel.override.reason == "I need to think"


def test_a_suspended_kernel_refuses_through_the_boundary(
    tmp_path: Path,
) -> None:
    """§7.2 K2 — nothing above the Kernel may route around a
    suspension."""
    api, _, ledger, _ = build(tmp_path)
    api.invalidate(SCOPE_ALL, "founder override")

    response = api.authorize(request())
    assert response.refused
    assert response.payload["reason"] == "override_active"
    assert len(ledger) == 0


def test_invalidate_carries_no_confirmation_parameter() -> None:
    """§11.8 and VEDA 04 A3 — *"no confirmation parameter in its
    signature."* A boundary is exactly where one would be added for a
    surface's convenience."""
    assert list(inspect.signature(KernelApi.invalidate).parameters) == [
        "self", "scope", "reason",
    ]
    forbidden = (
        "confirm", "confirmation", "sure", "acknowledge", "force", "yes",
        "consent", "delay", "cooldown", "grace", "throttle", "retry",
    )
    for name in ("authorize", "attempt", "settle", "invalidate", "status"):
        for param in inspect.signature(getattr(KernelApi, name)).parameters:
            assert not any(w in param.lower() for w in forbidden), name


# ======================================================================
# §7.5 · refusal mapping
# ======================================================================


def test_a_refusal_is_data_and_not_an_error(tmp_path: Path) -> None:
    """§7.5 — a refusal is a decision the Kernel made and must record. It
    is not a failure of the transport, and the two kinds keep it apart."""
    api, _, _, _ = build(tmp_path)
    response = api.authorize(request(objective_id="obj-unknown"))

    assert response.kind is ResultKind.REFUSED
    assert response.refused
    assert not response.ok


def test_the_refusal_payload_is_c8s_own(tmp_path: Path) -> None:
    """No reason is added and none is renamed."""
    api, _, _, _ = build(tmp_path)
    payload = api.authorize(request(objective_id="obj-unknown")).payload

    assert set(payload) == {
        "reason", "family", "failed_check", "failed_check_kind",
        "attestor", "remediable", "detail",
    }
    assert payload["reason"] == RefusalReason.OBJECTIVE_UNKNOWN.value
    assert payload["family"] == "kernel_check"
    assert payload["failed_check"] == "k1_objective_binding"
    assert payload["remediable"] is True


def test_an_attestation_refusal_names_its_attestor(tmp_path: Path) -> None:
    """§7.3's division of labour survives the boundary: the reason says
    what kind, `failed_check` says which question, `detail` says why."""
    api, _, _, _ = build(tmp_path)
    thin = request(attestations=tuple(attest(q) for q in LOCAL_QUESTIONS[:2]))
    payload = api.authorize(thin).payload

    assert payload["reason"] == "attestation_absent"
    assert payload["family"] == "attestation"
    assert payload["failed_check_kind"] == "attestation"
    assert payload["attestor"]


def test_the_boundary_invents_no_reason() -> None:
    """C8's vocabulary is closed. A transport that added one would open
    it from outside."""
    source = MODULE.read_text(encoding="utf-8")
    assert "RefusalReason." not in source
    assert "KernelCheck" not in source
    assert "RefusalFamily" not in source


def test_identical_refusals_are_identical_responses(tmp_path: Path) -> None:
    """§7.5 — *"a thousand refusals are one state."* They collapse only
    if they are equal, and the boundary must not make them differ."""
    api, _, _, _ = build(tmp_path)
    first = api.authorize(request(objective_id="obj-unknown"))
    second = api.authorize(request(objective_id="obj-unknown"))

    assert first == second
    assert first.as_dict() == second.as_dict()


# ======================================================================
# Transport failures — exceptions become responses
# ======================================================================


def test_an_unknown_warrant_becomes_an_error_response(tmp_path: Path) -> None:
    """`AttemptNotAuthorized` would otherwise cross as a traceback."""
    api, _, _, _ = build(tmp_path)
    response = api.attempt("wrt-000000000999")

    assert response.kind is ResultKind.ERROR
    assert response.payload["type"] == "AttemptNotAuthorized"
    assert "not outstanding" in response.payload["message"]


def test_a_settlement_with_nothing_to_settle_becomes_an_error(
    tmp_path: Path,
) -> None:
    api, _, _, _ = build(tmp_path)
    response = api.settle("wrt-000000000999", ExecutionOutcome.SUCCEEDED)

    assert response.kind is ResultKind.ERROR
    assert response.payload["type"] == "NothingToSettle"


def test_a_ledger_failure_at_settlement_becomes_an_error(
    tmp_path: Path,
) -> None:
    """§11.3 — fail closed. The boundary reports it; it does not retry
    it, buffer it, or soften it."""
    api, _, ledger, _ = build(
        tmp_path, ledger=OutcomeRefusingLedger(JsonFileStateStore(tmp_path))
    )
    warrant_id = api.authorize(request()).payload["warrant_id"]
    api.attempt(warrant_id)

    response = api.settle(warrant_id, ExecutionOutcome.SUCCEEDED)
    assert response.payload["type"] == "LedgerUnavailable"
    assert not ledger.is_settled(warrant_id)


def test_a_ledger_failure_at_attempt_is_a_refusal_not_an_error(
    tmp_path: Path,
) -> None:
    """The Kernel returns a `KernelRefusal` there and raises elsewhere.
    The boundary reports which happened rather than flattening both."""
    api, _, _, _ = build(
        tmp_path, ledger=AttemptRefusingLedger(JsonFileStateStore(tmp_path))
    )
    warrant_id = api.authorize(request()).payload["warrant_id"]

    response = api.attempt(warrant_id)
    assert response.kind is ResultKind.REFUSED
    assert response.payload["reason"] == "ledger_unavailable"


def test_a_partial_settlement_becomes_an_error(tmp_path: Path) -> None:
    """R43/R49, seen at the boundary. §6.3 requires a compensating action
    reference and `settle()` has no parameter for one, so C5 refuses
    construction. The boundary reports it and repairs nothing."""
    api, _, _, _ = build(tmp_path)
    warrant_id = api.authorize(request()).payload["warrant_id"]
    api.attempt(warrant_id)

    response = api.settle(warrant_id, ExecutionOutcome.PARTIAL)
    assert response.payload["type"] == "InvalidReceipt"
    assert "compensating action" in response.payload["message"]


def test_a_blank_override_reason_becomes_an_error(tmp_path: Path) -> None:
    """C14 owns the invariant and the boundary neither restates nor
    softens it."""
    api, kernel, _, _ = build(tmp_path)
    response = api.invalidate(SCOPE_ALL, "   ")

    assert response.payload["type"] == "InvalidOverride"
    assert not kernel.override.is_suspended


def test_every_error_keeps_its_own_class_name(tmp_path: Path) -> None:
    """Nothing is grouped into a transport error taxonomy. A boundary
    that renamed them would invent a vocabulary parallel to C8's."""
    api, _, _, _ = build(tmp_path)
    seen = {
        api.attempt("nope").payload["type"],
        api.settle("nope", ExecutionOutcome.SUCCEEDED).payload["type"],
        api.invalidate(SCOPE_ALL, "").payload["type"],
    }
    assert seen == {
        "AttemptNotAuthorized", "NothingToSettle", "InvalidOverride"
    }


def test_a_base_exception_is_not_swallowed(tmp_path: Path) -> None:
    """A `KeyboardInterrupt` is not a response."""

    class Interrupting(StubAdmissions):
        def admission_for(self, objective_id):  # type: ignore[override]
            raise KeyboardInterrupt

    kernel = Kernel(
        clock=ManualClock(T0),
        ledger=ReceiptLedger(JsonFileStateStore(tmp_path)),
        admission=Interrupting(),
    )
    with pytest.raises(KeyboardInterrupt):
        KernelApi(kernel).authorize(request())


def test_an_error_writes_nothing(tmp_path: Path) -> None:
    """A failed call is not a half-performed one."""
    api, _, ledger, _ = build(tmp_path)
    api.attempt("wrt-000000000999")
    api.settle("wrt-000000000999", ExecutionOutcome.SUCCEEDED)
    assert len(ledger) == 0


# ======================================================================
# §3.3 · status, and only the two facts
# ======================================================================


def test_status_projects_the_override_and_the_outstanding_count(
    tmp_path: Path,
) -> None:
    """§7.5 — *"autonomy is suspended; 1,000 actions are waiting."* That
    sentence needs exactly a switch and a count."""
    api, _, _, _ = build(tmp_path)
    api.authorize(request())

    response = api.status()
    assert response.operation is Operation.STATUS
    assert response.ok
    assert response.payload == {
        "override": {"suspended": False, "reason": None},
        "outstanding": 1,
    }


def test_status_follows_the_override(tmp_path: Path) -> None:
    api, _, _, _ = build(tmp_path)
    api.invalidate(SCOPE_ALL, "founder override")

    payload = api.status().payload
    assert payload["override"] == {
        "suspended": True, "reason": "founder override"
    }
    assert payload["outstanding"] == 0


def test_status_derives_nothing(tmp_path: Path) -> None:
    """Both values are the Kernel's own read-only properties, projected.
    Roadmap §2 C21 refuses *"no objective count, no progress bar, no
    badge"* — what a surface may say about these is C20's and C21's
    question, not this one's."""
    api, kernel, _, _ = build(tmp_path)
    for _ in range(3):
        api.authorize(request(payload_digest=f"sha256:{_}"))

    assert api.status().payload["outstanding"] == kernel.outstanding_count
    assert api.status().payload["override"] == kernel.override.as_dict()


def test_status_takes_no_argument() -> None:
    assert list(inspect.signature(KernelApi.status).parameters) == ["self"]


def test_status_changes_nothing(tmp_path: Path) -> None:
    """A reader that mutated would be a writer with a modest name."""
    api, kernel, ledger, _ = build(tmp_path)
    api.authorize(request())
    before = (kernel.outstanding_count, len(ledger), kernel.override.as_dict())

    api.status()
    api.status()
    assert (
        kernel.outstanding_count, len(ledger), kernel.override.as_dict()
    ) == before


# ======================================================================
# Deterministic responses
# ======================================================================


def test_two_apis_over_two_kernels_answer_identically(
    tmp_path: Path,
) -> None:
    """§14 R2's determinism survives the boundary only if the boundary
    adds nothing that varies."""
    a, _, _, _ = build(tmp_path / "a")
    b, _, _, _ = build(tmp_path / "b")

    assert a.authorize(request()) == b.authorize(request())
    assert a.status() == b.status()


def test_a_response_carries_no_id_and_no_timestamp(tmp_path: Path) -> None:
    """No `uuid4()`, no clock, no request id, no correlation of its own."""
    api, _, _, _ = build(tmp_path)
    response = api.authorize(request())

    assert set(response.as_dict()) == {"operation", "kind", "payload"}

    # Checked against executable identifiers, not against prose: this
    # module's own docstring names what it does not do.
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    identifiers = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    } | {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    } | set(_module_imports(MODULE))
    for banned in ("uuid", "uuid4", "random", "monotonic", "perf_counter"):
        assert not any(banned in name.lower() for name in identifiers), banned


def test_the_boundary_reads_no_clock() -> None:
    """Every moment on the record comes from the Kernel's canonical
    clock. A second reader would be a second timeline."""
    assert not any("clock" in n.lower() for n in _module_imports(MODULE))
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    banned = {"datetime.now", "datetime.utcnow", "datetime.today", "time.time"}
    assert not [
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ".".join(ast.unparse(node.func).split(".")[-2:]) in banned
    ]


def test_the_response_is_immutable(tmp_path: Path) -> None:
    from dataclasses import FrozenInstanceError

    api, _, _, _ = build(tmp_path)
    response = api.authorize(request())
    with pytest.raises(FrozenInstanceError):
        response.kind = ResultKind.ERROR


def test_every_response_serialises(tmp_path: Path) -> None:
    """A boundary whose answers cannot cross it is not a boundary."""
    api, _, _, _ = build(tmp_path)
    warrant_id = api.authorize(request()).payload["warrant_id"]
    api.attempt(warrant_id)

    for response in (
        api.authorize(request(objective_id="obj-unknown")),
        api.attempt("nope"),
        api.settle(warrant_id, ExecutionOutcome.SUCCEEDED),
        api.invalidate(SCOPE_ALL, "founder override"),
        api.status(),
    ):
        encoded = json.dumps(response.as_dict(), sort_keys=False)
        assert json.loads(encoded)["operation"] == response.operation.value


def test_the_same_call_twice_differs_only_by_kernel_state(
    tmp_path: Path,
) -> None:
    """Nothing in the response varies for a reason the Kernel did not
    supply."""
    api, _, _, _ = build(tmp_path)
    assert api.status() == api.status()

    first = api.authorize(request())
    second = api.authorize(request())
    assert first.operation == second.operation and first.kind == second.kind
    assert first.payload["warrant_id"] != second.payload["warrant_id"]


# ======================================================================
# API isolation — one door, and it is this one
# ======================================================================


def test_the_boundary_depends_only_on_foundation_and_the_kernel() -> None:
    """§3.6 — dependency direction is strictly downward. C1–C16 is the
    brief's bound, and this uses less than that."""
    internal = {
        n for n in _module_imports(MODULE) if n.startswith("master_agent")
    }
    assert all(
        n.startswith(("master_agent.foundation.", "master_agent.kernel"))
        for n in internal
    ), internal


def test_the_boundary_imports_no_surface() -> None:
    """A door that knew who was on the other side would not be a door."""
    forbidden = (
        "master_agent.ui", "master_agent.desktop", "master_agent.dashboard",
        "master_agent.cli", "master_agent.launcher", "master_agent.voice",
    )
    assert not [
        n for n in _module_imports(MODULE)
        if any(n.startswith(f) for f in forbidden)
    ]


def test_the_boundary_introduces_no_runtime_dependency() -> None:
    """No web framework, no server, no socket, no thread, no background
    worker. The transport is a function call."""
    forbidden = (
        "http", "socket", "threading", "asyncio", "multiprocessing",
        "concurrent", "queue", "subprocess", "flask", "fastapi", "starlette",
        "uvicorn", "requests", "aiohttp", "pydantic",
    )
    imported = _module_imports(MODULE)
    assert not [
        n for n in imported
        if any(n == f or n.startswith(f + ".") for f in forbidden)
    ], imported


def test_no_surface_imports_the_kernel() -> None:
    """**The reason this component exists.** The assertion means something
    only because there is a door to use instead."""
    offenders: dict[str, list[str]] = {}
    for package in ("ui", "desktop", "dashboard", "voice"):
        directory = SRC / package
        if not directory.is_dir():
            continue
        for path in directory.rglob("*.py"):
            reaching = [
                n for n in _module_imports(path)
                if n == "master_agent.kernel"
                or n.startswith("master_agent.kernel.")
            ]
            if reaching:
                offenders[str(path.relative_to(SRC))] = reaching
    assert not offenders, offenders


def test_the_public_surface_is_the_four_operations_plus_status() -> None:
    """§3.5 fixes the surface at four. `status()` projects §3.3's two
    owned facts and is not a fifth operation on the Kernel."""
    surface = {n for n in dir(KernelApi) if not n.startswith("_")}
    assert surface == {
        "authorize", "attempt", "settle", "invalidate", "status"
    }


def test_the_operation_vocabulary_is_closed() -> None:
    assert {o.value for o in Operation} == {
        "authorize", "attempt", "settle", "invalidate", "status"
    }
    assert {k.value for k in ResultKind} == {"ok", "refused", "error"}


def test_there_is_no_execute_and_no_run() -> None:
    """§3.5 — *"There is no `execute()`."* And C16's `run()` is not
    exposed here: a fifth operation on this boundary would be a second
    way to execute, which is the thing one door exists to prevent."""
    surface = {n for n in dir(KernelApi) if not n.startswith("_")}
    assert not any(
        v in n.lower()
        for n in surface
        for v in ("execute", "run", "invoke", "dispatch", "perform", "coordinate")
    )
    assert "coordinator" not in " ".join(_module_imports(MODULE))


def test_the_boundary_performs_no_kernel_check() -> None:
    """§7.2's three checks and §7.3's eight attestations are the Kernel's
    alone. Restating one here would give the system two answers."""
    source = MODULE.read_text(encoding="utf-8")
    for name in (
        "_check_objective_binding", "_check_override_state",
        "_verify_attestations", "is_suspended", "is_terminal",
        "consequence_ceiling", "exceeds(", "attempt_budget", "is_expired",
        "record_intent", "record_attempt", "record_outcome",
    ):
        assert name not in source


def test_the_boundary_holds_one_collaborator_and_no_state() -> None:
    assert set(KernelApi.__slots__) == {"_kernel"}


def test_two_apis_over_one_kernel_agree(tmp_path: Path) -> None:
    """The consequence of holding no state."""
    _, kernel, _, _ = build(tmp_path)
    first, second = KernelApi(kernel), KernelApi(kernel)

    first.authorize(request())
    assert second.status().payload["outstanding"] == 1


def test_it_refuses_a_kernel_that_is_not_one() -> None:
    for bogus in (None, object(), "kernel"):
        with pytest.raises(InvalidKernelApi):
            KernelApi(bogus)  # type: ignore[arg-type]


def test_it_is_exported_from_its_package() -> None:
    from master_agent.api import KernelApi as Exported

    assert Exported is KernelApi


def test_the_boundary_is_small() -> None:
    """A transport with business logic in it is not a transport. The
    whole of the mapping is one method and one function."""
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
    assert len(statements) < 120, f"{len(statements)} statements"
