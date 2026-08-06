"""Sprint 1, Component 18 — the Runtime Integration Layer.

```
   Desktop UI · CLI · future services
        │
        ▼
   Runtime          ← serialization · transport · wiring
        │
        ▼
   Kernel API       ← projection (C17)
        │
        ▼
   Kernel           ← the authority (C15)
```

| Source | Requirement |
|---|---|
| §3.5 | Four operations. The bridge carries them and adds none |
| §4.5 | The warrant lifecycle the transport must carry end to end |
| §6.1 | The caller executes; a callable is *"entirely its own business"* |
| §6.3 | Settlement is mandatory, and the four kinds are closed |
| §7.5 | Refusals are data; a thousand are one state |
| §11.8 | No confirmation parameter, ever |
| §14 R2 | Determinism — no ambient randomness at any layer |
| ADR-0022 D2 | **The caller is a courier, not an author** — R53's resolution |
| C9 | A malformed request is not a constitutional refusal |

**No constitutional behaviour is mocked.** Every test runs a real Kernel
over a real ledger; the only doubles are the admission provider the Kernel
tests already ship and a piece of work that answers what it was told to.
"""
from __future__ import annotations

import ast
import inspect
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from master_agent.api import KernelApi, Operation, ResultKind
from master_agent.coordinator import Execution
from master_agent.foundation.attempt_token import AttemptToken
from master_agent.foundation.attestation import (
    Attestation,
    AttestationQuestion,
    AttestationVerdict,
)
from master_agent.foundation.clock import ManualClock
from master_agent.foundation.consequence import Consequence, Cost, CostBasis
from master_agent.foundation.execution_request import (
    PENDING_CONSEQUENCE_ENGINE,
    ActionClass,
    ExecutionRequest,
    InvalidExecutionRequest,
)
from master_agent.foundation.receipt import ExecutionOutcome
from master_agent.foundation.warrant import ReversibilityClass
from master_agent.kernel import SCOPE_ALL, Kernel
from master_agent.ledger.receipt_ledger import LedgerUnavailable, ReceiptLedger
from master_agent.persistence.store import JsonFileStateStore
from master_agent.runtime_bridge import (
    ARGUMENTS,
    OPERATION,
    InvalidEnvelope,
    InvalidRuntime,
    Runtime,
    decode_outcome,
    decode_request,
    encode_outcome,
    encode_request,
)
from tests.kernel_test_support import StubAdmissions, admission

SRC = Path(__file__).resolve().parent.parent / "src" / "master_agent"
PACKAGE = SRC / "runtime_bridge"
RUNTIME = PACKAGE / "runtime.py"
CODEC = PACKAGE / "codec.py"

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


def quartet() -> Consequence:
    """A real §14.1 quartet, so the marker is not the only path tested."""
    return Consequence(
        what_changes="one folder and everything under it stops existing",
        cost=Cost(
            description="the founder's evening if it was the wrong folder",
            basis=CostBasis.PRICED,
            amount=Decimal("12.50"),
            currency="GBP",
        ),
        if_nothing="the disk stays full and the backup keeps failing",
        reversibility=ReversibilityClass.REVERSIBLE,
    )


class Recorder:
    """A piece of work that answers what the test told it to answer."""

    def __init__(self, *answers: ExecutionOutcome):
        self._answers = list(answers) or [ExecutionOutcome.SUCCEEDED]
        self.tokens: list[AttemptToken] = []

    def __call__(self, token: AttemptToken) -> ExecutionOutcome:
        self.tokens.append(token)
        return self._answers[min(len(self.tokens) - 1, len(self._answers) - 1)]

    @property
    def calls(self) -> int:
        return len(self.tokens)


class OutcomeRefusingLedger(ReceiptLedger):
    """Intents and attempts land; the outcome write does not. §11.3."""

    def record_outcome(self, receipt):  # type: ignore[override]
        raise LedgerUnavailable("the receipt ledger could not write: disk gone")


def build(
    tmp_path: Path, *, ledger: ReceiptLedger | None = None
) -> tuple[Runtime, Kernel, ReceiptLedger, ManualClock]:
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
    return Runtime(kernel), kernel, store, clock


def envelope(operation: str, **arguments) -> dict:
    """An envelope built the way a surface would build one — through JSON,
    so nothing in these tests can pass a Python object by accident."""
    return json.loads(
        json.dumps({OPERATION: operation, ARGUMENTS: arguments})
    )


def _module_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    return imported


def _package_imports() -> list[str]:
    return [n for path in PACKAGE.rglob("*.py") for n in _module_imports(path)]


def _package_identifiers() -> set[str]:
    """Every executable name in the package.

    Checked instead of raw source because these modules' own docstrings
    name the things they do not do — a text-matching guard would fail on
    its own explanation.
    """
    names: set[str] = set()
    for path in PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.alias):
                names.add(node.asname or node.name.rsplit(".", 1)[-1])
    return names


# ======================================================================
# Serialization correctness
# ======================================================================


def test_encoding_is_the_values_own_projection() -> None:
    """Nothing is added, renamed or reordered — C9 already wrote the
    shape."""
    original = request()
    assert encode_request(original) == original.as_dict()
    assert encode_outcome(ExecutionOutcome.PARTIAL) == "partial"


def test_a_request_survives_the_round_trip() -> None:
    original = request()
    assert decode_request(encode_request(original)) == original


def test_the_round_trip_survives_json() -> None:
    """A boundary whose values cannot cross it is not a boundary."""
    original = request()
    wire = json.loads(json.dumps(encode_request(original)))
    assert decode_request(wire) == original


def test_a_real_quartet_survives_the_round_trip() -> None:
    """§14.1's marker is not the only consequence a request may carry, and
    the decimal must not become a float on the way."""
    original = request(consequence=quartet())
    restored = decode_request(json.loads(json.dumps(encode_request(original))))

    assert restored == original
    assert restored.consequence.cost.amount == Decimal("12.50")
    assert isinstance(restored.consequence.cost.amount, Decimal)


def test_the_pending_marker_survives_as_itself() -> None:
    """§14.1 — *"never null, never omitted, never a partial quartet."*"""
    restored = decode_request(encode_request(request()))
    assert restored.consequence is PENDING_CONSEQUENCE_ENGINE


def test_every_attestation_survives_with_its_attestor(
) -> None:
    """§7.3's subject match and attestor identity are checked by the
    Kernel, so both must arrive intact or an honest request is refused."""
    original = request()
    restored = decode_request(encode_request(original))

    assert restored.attestations == original.attestations
    assert len(restored.attestations) == len(LOCAL_QUESTIONS)
    for item in restored.attestations:
        assert item.attestor == item.question.canonical_attestor
        assert item.attested_at == T0


def test_an_optional_field_survives_being_absent() -> None:
    """`target_ref` and `attestations` are the two C9 gives defaults."""
    lean = {
        k: v
        for k, v in encode_request(request(attestations=())).items()
        if k not in {"target_ref", "attestations"}
    }
    restored = decode_request(lean)
    assert restored.target_ref is None
    assert restored.attestations == ()


def test_a_target_ref_survives_when_present() -> None:
    original = request(target_ref="/home/founder/scratch")
    assert decode_request(encode_request(original)).target_ref == (
        "/home/founder/scratch"
    )


@pytest.mark.parametrize("outcome", list(ExecutionOutcome))
def test_every_outcome_survives_the_round_trip(
    outcome: ExecutionOutcome,
) -> None:
    """§6.3's four kinds, closed by C5 and unaltered here."""
    assert decode_outcome(encode_outcome(outcome)) is outcome


@pytest.mark.parametrize("cls", list(ReversibilityClass))
def test_every_reversibility_class_survives(cls: ReversibilityClass) -> None:
    """ADR-0022 — the class the caller carried must arrive as the class
    the registry gave it, or the courier has changed the parcel."""
    original = request(reversibility_class=cls)
    assert decode_request(encode_request(original)).reversibility_class is cls


@pytest.mark.parametrize("action", list(ActionClass))
def test_every_action_class_survives(action: ActionClass) -> None:
    """§7.4 — the class selects the attestation set, so a wrong one is a
    wrong set of checks."""
    questions = (
        tuple(AttestationQuestion)
        if action is ActionClass.INTELLIGENCE
        else LOCAL_QUESTIONS
    )
    original = request(
        action_class=action,
        attestations=tuple(attest(q) for q in questions),
    )
    assert decode_request(encode_request(original)) == original


# ======================================================================
# Deserialization correctness — and the line C9 draws
# ======================================================================


@pytest.mark.parametrize(
    "field",
    [
        "objective_id", "principal_id", "capability", "payload_digest",
        "action_class", "reversibility_class", "expected_effect",
        "consequence",
    ],
)
def test_a_missing_required_field_does_not_decode(field: str) -> None:
    """ADR-0022 D1 — `reversibility_class` is *"required, with no default:
    a default would be a guessed class."* No field here is guessed."""
    payload = encode_request(request())
    del payload[field]

    with pytest.raises(InvalidEnvelope, match=field):
        decode_request(payload)


def test_a_word_outside_a_closed_vocabulary_does_not_decode() -> None:
    """Every enum crossing this boundary is closed by a frozen component."""
    payload = encode_request(request())
    payload["reversibility_class"] = "probably_reversible"

    with pytest.raises(InvalidEnvelope, match="reversibility_class"):
        decode_request(payload)


def test_a_malformed_request_is_not_a_transport_failure() -> None:
    """C9 — *"a request that is merely malformed is not a constitutional
    refusal and must not become one."* The two errors stay apart, and the
    constitutional one is never wrapped."""
    payload = encode_request(request())
    payload["capability"] = "   "

    with pytest.raises(InvalidExecutionRequest):
        decode_request(payload)


def test_a_constitutional_error_is_never_relabelled() -> None:
    """The value's own verdict crosses untouched — `InvalidEnvelope` is
    not a superclass of it and must not become one."""
    payload = encode_request(request())
    payload["expected_effect"] = ""

    with pytest.raises(InvalidExecutionRequest) as caught:
        decode_request(payload)
    assert not isinstance(caught.value, InvalidEnvelope)


def test_a_null_consequence_does_not_decode() -> None:
    """§14.1 — *"never null, never omitted, never a partial quartet."*"""
    payload = encode_request(request())
    payload["consequence"] = None

    with pytest.raises(InvalidEnvelope, match="consequence"):
        decode_request(payload)


def test_a_partial_quartet_does_not_decode() -> None:
    payload = encode_request(request(consequence=quartet()))
    del payload["consequence"]["if_nothing"]

    with pytest.raises(InvalidEnvelope, match="if_nothing"):
        decode_request(payload)


def test_a_stale_attestation_is_decoded_and_then_refused(
    tmp_path: Path,
) -> None:
    """The decoder does not judge freshness — §7.3 does, at the Kernel.
    Proven end to end rather than asserted."""
    runtime, _, _, clock = build(tmp_path)
    payload = encode_request(request())
    clock.advance(__import__("datetime").timedelta(seconds=120))

    answer = runtime.handle(envelope("authorize", request=payload))
    assert answer["kind"] == "refused"
    assert answer["payload"]["reason"] == "attestation_absent"
    assert "no longer fresh" in answer["payload"]["detail"]


def test_the_decoder_validates_nothing_itself() -> None:
    """Every Foundation value validates at construction. A decoder that
    checked the same things would drift from them."""
    source = CODEC.read_text(encoding="utf-8")
    for restated in (
        "strip()", "canonical_attestor", "is_stale", "exceeds(",
        "is_intelligence_only",
    ):
        assert restated not in source


def test_a_non_mapping_payload_does_not_decode() -> None:
    for bogus in (None, [], "request", 7):
        with pytest.raises(InvalidEnvelope):
            decode_request(bogus)  # type: ignore[arg-type]


# ======================================================================
# Runtime request handling — the transport door
# ======================================================================


def test_authorize_crosses_the_bridge(tmp_path: Path) -> None:
    runtime, _, ledger, _ = build(tmp_path)
    answer = runtime.handle(
        envelope("authorize", request=encode_request(request()))
    )

    assert answer[OPERATION] == "authorize"
    assert answer["kind"] == "ok"
    assert ledger.has_intent(answer["payload"]["warrant_id"])


def test_the_whole_lifecycle_crosses_the_bridge(tmp_path: Path) -> None:
    """§4.5's lifecycle, end to end, through dictionaries only."""
    runtime, _, ledger, _ = build(tmp_path)

    minted = runtime.handle(
        envelope("authorize", request=encode_request(request()))
    )
    warrant_id = minted["payload"]["warrant_id"]

    opened = runtime.handle(envelope("attempt", warrant_id=warrant_id))
    assert opened["payload"]["attempt_seq"] == 1

    settled = runtime.handle(
        envelope("settle", warrant_id=warrant_id, outcome="succeeded")
    )
    assert settled["payload"]["outcome"] == "succeeded"

    kinds = [type(r).__name__ for r in ledger.read(warrant_id)]
    assert kinds == ["IntentRecord", "AttemptRecord", "Receipt"]


def test_invalidate_crosses_the_bridge(tmp_path: Path) -> None:
    runtime, kernel, _, _ = build(tmp_path)
    runtime.handle(envelope("authorize", request=encode_request(request())))

    answer = runtime.handle(
        envelope("invalidate", scope=SCOPE_ALL, reason="founder override")
    )
    assert answer["payload"] == {"count": 1}
    assert kernel.override.is_suspended


def test_status_crosses_the_bridge_with_no_arguments(tmp_path: Path) -> None:
    runtime, _, _, _ = build(tmp_path)
    runtime.handle(envelope("authorize", request=encode_request(request())))

    answer = runtime.handle({OPERATION: "status"})
    assert answer["payload"] == {
        "override": {"suspended": False, "reason": None},
        "outstanding": 1,
    }


def test_the_arguments_use_the_apis_own_parameter_names() -> None:
    """No translation table means nothing to drift."""
    for name in ("authorize", "attempt", "settle", "invalidate"):
        for param in inspect.signature(getattr(KernelApi, name)).parameters:
            if param == "self":
                continue
            assert f'"{param}"' in RUNTIME.read_text(encoding="utf-8"), param


# ======================================================================
# Runtime response handling
# ======================================================================


def test_a_refusal_crosses_as_a_refusal(tmp_path: Path) -> None:
    """§7.5 — a refusal is a decision the Kernel made, not a failure of
    the transport."""
    runtime, _, _, _ = build(tmp_path)
    payload = encode_request(request(objective_id="obj-unknown"))

    answer = runtime.handle(envelope("authorize", request=payload))
    assert answer["kind"] == "refused"
    assert answer["payload"]["reason"] == "objective_unknown"
    assert answer["payload"]["family"] == "kernel_check"


def test_the_refusal_payload_is_c8s_own(tmp_path: Path) -> None:
    runtime, _, _, _ = build(tmp_path)
    payload = encode_request(request(objective_id="obj-unknown"))

    answer = runtime.handle(envelope("authorize", request=payload))
    assert set(answer["payload"]) == {
        "reason", "family", "failed_check", "failed_check_kind",
        "attestor", "remediable", "detail",
    }


def test_every_answer_has_the_same_three_keys(tmp_path: Path) -> None:
    """One shape out, whatever happened. A caller parses once."""
    runtime, _, _, _ = build(tmp_path)
    minted = runtime.handle(
        envelope("authorize", request=encode_request(request()))
    )
    warrant_id = minted["payload"]["warrant_id"]

    for answer in (
        minted,
        runtime.handle(envelope("attempt", warrant_id=warrant_id)),
        runtime.handle(envelope("attempt", warrant_id="nope")),
        runtime.handle(
            envelope("settle", warrant_id=warrant_id, outcome="succeeded")
        ),
        runtime.handle(envelope("invalidate", scope="all", reason="stop")),
        runtime.handle({OPERATION: "status"}),
        runtime.handle({OPERATION: "not-an-operation"}),
        runtime.handle({}),
    ):
        assert set(answer) == {OPERATION, "kind", "payload"}
        assert answer["kind"] in {k.value for k in ResultKind}


def test_the_bridge_adds_no_wire_field(tmp_path: Path) -> None:
    """No status code, no envelope version, no request id, no timestamp.
    A field nobody reads is a field somebody will depend on."""
    runtime, _, _, _ = build(tmp_path)
    answer = runtime.handle(
        envelope("authorize", request=encode_request(request()))
    )
    assert set(answer) == {OPERATION, "kind", "payload"}
    # The payload is C4's own projection, key for key.
    assert set(answer["payload"]) == {
        "warrant_id", "objective_id", "principal_id", "capability",
        "payload_digest", "reversibility_class", "consequence_ceiling",
        "attempt_budget", "issued_at", "expires_at", "grant_ref", "rule_ref",
    }


def test_every_answer_serialises(tmp_path: Path) -> None:
    runtime, _, _, _ = build(tmp_path)
    for env in (
        envelope("authorize", request=encode_request(request())),
        envelope("attempt", warrant_id="nope"),
        {OPERATION: "status"},
        {OPERATION: "bogus"},
    ):
        answer = runtime.handle(env)
        assert json.loads(json.dumps(answer)) == answer


# ======================================================================
# Exception propagation
# ======================================================================


def test_an_unknown_operation_is_an_error_that_echoes_itself(
    tmp_path: Path,
) -> None:
    """`Operation` is closed. A word this system does not have must not be
    given one of its names."""
    runtime, _, _, _ = build(tmp_path)
    answer = runtime.handle({OPERATION: "execute"})

    assert answer[OPERATION] == "execute"
    assert answer["kind"] == "error"
    assert answer["payload"]["type"] == "InvalidEnvelope"


def test_a_missing_operation_is_an_error(tmp_path: Path) -> None:
    runtime, _, _, _ = build(tmp_path)
    answer = runtime.handle({ARGUMENTS: {}})

    assert answer[OPERATION] is None
    assert answer["payload"]["type"] == "InvalidEnvelope"


def test_a_missing_argument_is_an_error(tmp_path: Path) -> None:
    runtime, _, _, _ = build(tmp_path)
    answer = runtime.handle({OPERATION: "attempt", ARGUMENTS: {}})

    assert answer["kind"] == "error"
    assert "warrant_id" in answer["payload"]["message"]


def test_a_malformed_request_and_a_malformed_envelope_are_told_apart(
    tmp_path: Path,
) -> None:
    """C9's line, visible on the wire: each error keeps its own class
    name, so a caller can tell a shape problem from a value problem."""
    runtime, _, _, _ = build(tmp_path)

    shape = encode_request(request())
    del shape["capability"]
    value = encode_request(request())
    value["capability"] = "  "

    assert runtime.handle(
        envelope("authorize", request=shape)
    )["payload"]["type"] == "InvalidEnvelope"
    assert runtime.handle(
        envelope("authorize", request=value)
    )["payload"]["type"] == "InvalidExecutionRequest"


def test_a_kernel_exception_keeps_its_own_class_name(tmp_path: Path) -> None:
    """C17's convention, followed rather than restated."""
    runtime, _, _, _ = build(tmp_path)
    assert runtime.handle(
        envelope("attempt", warrant_id="wrt-000000000999")
    )["payload"]["type"] == "AttemptNotAuthorized"
    assert runtime.handle(
        envelope("settle", warrant_id="nope", outcome="failed")
    )["payload"]["type"] == "NothingToSettle"


def test_a_ledger_failure_crosses_as_an_error(tmp_path: Path) -> None:
    """§11.3 — fail closed. The bridge reports it; it does not retry it,
    buffer it, or soften it."""
    runtime, _, ledger, _ = build(
        tmp_path, ledger=OutcomeRefusingLedger(JsonFileStateStore(tmp_path))
    )
    minted = runtime.handle(
        envelope("authorize", request=encode_request(request()))
    )
    warrant_id = minted["payload"]["warrant_id"]
    runtime.handle(envelope("attempt", warrant_id=warrant_id))

    answer = runtime.handle(
        envelope("settle", warrant_id=warrant_id, outcome="succeeded")
    )
    assert answer["payload"]["type"] == "LedgerUnavailable"
    assert not ledger.is_settled(warrant_id)


def test_an_unknown_outcome_word_is_an_error(tmp_path: Path) -> None:
    runtime, _, _, _ = build(tmp_path)
    minted = runtime.handle(
        envelope("authorize", request=encode_request(request()))
    )
    warrant_id = minted["payload"]["warrant_id"]
    runtime.handle(envelope("attempt", warrant_id=warrant_id))

    answer = runtime.handle(
        envelope("settle", warrant_id=warrant_id, outcome="mostly_fine")
    )
    assert answer["payload"]["type"] == "InvalidEnvelope"


def test_a_base_exception_is_not_swallowed(tmp_path: Path) -> None:
    """A `KeyboardInterrupt` is not a response."""

    class Interrupting(StubAdmissions):
        def admission_for(self, objective_id):  # type: ignore[override]
            raise KeyboardInterrupt

    runtime = Runtime(
        Kernel(
            clock=ManualClock(T0),
            ledger=ReceiptLedger(JsonFileStateStore(tmp_path)),
            admission=Interrupting(),
        )
    )
    with pytest.raises(KeyboardInterrupt):
        runtime.handle(envelope("authorize", request=encode_request(request())))


def test_an_error_writes_nothing(tmp_path: Path) -> None:
    runtime, _, ledger, _ = build(tmp_path)
    runtime.handle({OPERATION: "bogus"})
    runtime.handle(envelope("attempt", warrant_id="nope"))
    assert len(ledger) == 0


# ======================================================================
# Coordinator interaction — the in-process door
# ======================================================================


def test_execute_runs_the_composed_sequence(tmp_path: Path) -> None:
    """§6.1, composed by C16 and delegated to whole."""
    runtime, _, ledger, _ = build(tmp_path)
    work = Recorder()

    result = runtime.execute(request(), work)
    assert isinstance(result, Execution)
    assert result.settled
    assert work.calls == 1
    kinds = [type(r).__name__ for r in ledger.read(result.warrant.warrant_id)]
    assert kinds == ["IntentRecord", "AttemptRecord", "Receipt"]


def test_execute_honours_the_retry_bound(tmp_path: Path) -> None:
    """§8.5's budget is the Coordinator's to respect and the bridge's to
    leave alone."""
    runtime, _, _, _ = build(tmp_path)
    work = Recorder(ExecutionOutcome.FAILED)

    result = runtime.execute(request(), work)
    assert work.calls == result.warrant.attempt_budget == 3


def test_execute_honours_the_irreversible_rule(tmp_path: Path) -> None:
    """§8.4 — *"never automatically retried. Ever."* The bridge adds no
    loop of its own that could get this wrong."""
    runtime, _, _, _ = build(tmp_path)
    work = Recorder(ExecutionOutcome.FAILED)

    result = runtime.execute(
        request(reversibility_class=ReversibilityClass.IRREVERSIBLE), work
    )
    assert work.calls == 1
    assert result.requires_escalation


def test_execute_is_a_pure_delegation() -> None:
    """The order, the retry bound and the mandatory settlement are C16's.
    Duplicating any would give the system two answers about §6.3."""
    tree = ast.parse(RUNTIME.read_text(encoding="utf-8"), filename=str(RUNTIME))
    body = next(
        node.body
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "execute"
    )
    statements = [n for n in body if not isinstance(n, ast.Expr)]
    assert len(statements) == 1
    assert isinstance(statements[0], ast.Return)
    assert "run" in ast.unparse(statements[0])


def test_execute_is_not_reachable_over_the_transport(tmp_path: Path) -> None:
    """A callable has no wire representation, and inventing one would be
    the speculative API the brief forbids."""
    runtime, _, _, _ = build(tmp_path)
    answer = runtime.handle({OPERATION: "execute"})
    assert answer["kind"] == "error"
    assert "execute" not in {o.value for o in Operation}


def test_a_refused_execution_never_reaches_the_work(tmp_path: Path) -> None:
    """§11.5 — fail closed before anything runs, through the bridge as
    through the Coordinator."""
    runtime, kernel, _, _ = build(tmp_path)
    kernel.invalidate(SCOPE_ALL, "founder override")
    work = Recorder()

    result = runtime.execute(request(), work)
    assert work.calls == 0
    assert result.refusal.reason.value == "override_active"


# ======================================================================
# Kernel interaction — the bridge decides nothing
# ======================================================================


def test_the_bridge_creates_no_kernel_state() -> None:
    """It constructs no `Warrant`, `AttemptToken`, `Receipt` or ledger
    record, and mints nothing."""
    names = _package_identifiers()
    for constructor in (
        "Warrant", "AttemptToken", "Receipt", "IntentRecord",
        "AttemptRecord", "KernelRefusal",
    ):
        assert constructor not in names, constructor


def test_the_bridge_duplicates_no_authorization() -> None:
    """§7.2's three checks and §7.3's eight attestations are the Kernel's
    alone."""
    names = _package_identifiers()
    for name in (
        "_check_objective_binding", "_check_override_state",
        "_verify_attestations", "is_suspended", "is_terminal",
        "consequence_ceiling", "attempt_budget", "is_expired",
        "RefusalReason", "KernelCheck", "authorize_request",
    ):
        assert name not in names, name


def test_the_bridge_duplicates_no_settlement() -> None:
    """No outcome is derived, defaulted or inferred. The caller says which
    of §6.3's four kinds happened, and the bridge carries the word."""
    names = _package_identifiers()
    for kind in ("SUCCEEDED", "FAILED", "PARTIAL", "UNKNOWN"):
        assert kind not in names, kind
    for writer in ("record_intent", "record_attempt", "record_outcome"):
        assert writer not in names, writer


def test_the_bridge_writes_to_no_ledger() -> None:
    assert not any("ledger" in n.lower() for n in _package_imports())


def test_the_bridge_never_bypasses_the_kernel_api(tmp_path: Path) -> None:
    """Every transport path goes through C17, and there is no second
    route to the Kernel."""
    tree = ast.parse(RUNTIME.read_text(encoding="utf-8"), filename=str(RUNTIME))
    invoke = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_invoke"
    )
    receivers = {
        ast.unparse(node.func)
        for node in ast.walk(invoke)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert all(
        r.startswith(("self._api.", "_"))
        for r in receivers
    ), receivers


def test_the_bridge_holds_no_kernel_of_its_own() -> None:
    """It is handed one and wires two collaborators over it."""
    assert set(Runtime.__slots__) == {"_api", "_coordinator"}


def test_two_runtimes_over_one_kernel_agree(tmp_path: Path) -> None:
    """The consequence of holding no state."""
    _, kernel, _, _ = build(tmp_path)
    first, second = Runtime(kernel), Runtime(kernel)

    first.handle(envelope("authorize", request=encode_request(request())))
    assert second.handle({OPERATION: "status"})["payload"]["outstanding"] == 1


def test_it_refuses_a_kernel_that_is_not_one() -> None:
    for bogus in (None, object(), "kernel"):
        with pytest.raises(InvalidRuntime):
            Runtime(bogus)  # type: ignore[arg-type]


# ======================================================================
# Deterministic execution
# ======================================================================


def test_two_runtimes_over_two_kernels_answer_identically(
    tmp_path: Path,
) -> None:
    """§14 R2's determinism survives two boundaries only if neither adds
    anything that varies."""
    a, _, _, _ = build(tmp_path / "a")
    b, _, _, _ = build(tmp_path / "b")
    payload = encode_request(request())

    assert a.handle(envelope("authorize", request=payload)) == b.handle(
        envelope("authorize", request=payload)
    )
    assert a.handle({OPERATION: "status"}) == b.handle({OPERATION: "status"})


def test_identical_refusals_are_identical_envelopes(tmp_path: Path) -> None:
    """§7.5 — *"a thousand refusals are one state."* They collapse only if
    they are equal."""
    runtime, _, _, _ = build(tmp_path)
    payload = encode_request(request(objective_id="obj-unknown"))
    env = envelope("authorize", request=payload)

    assert runtime.handle(env) == runtime.handle(env)


def test_encoding_is_stable() -> None:
    original = request()
    assert encode_request(original) == encode_request(original)


def test_the_bridge_reads_no_clock() -> None:
    """Every moment on the record comes from the Kernel's canonical clock.
    A second reader would be a second timeline."""
    assert not any("clock" in n.lower() for n in _package_imports())
    for path in PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        banned = {
            "datetime.now", "datetime.utcnow", "datetime.today", "time.time"
        }
        assert not [
            ast.unparse(node.func)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and ".".join(ast.unparse(node.func).split(".")[-2:]) in banned
        ], path.name


def test_the_bridge_has_no_ambient_randomness() -> None:
    """Checked against executable identifiers, not prose."""
    identifiers: set[str] = set()
    for path in PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        identifiers |= {
            node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
        }
        identifiers |= {
            node.attr for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
        }
    identifiers |= set(_package_imports())
    for banned in ("uuid", "random", "monotonic", "perf_counter"):
        assert not any(banned in n.lower() for n in identifiers), banned


# ======================================================================
# Transport independence · hidden dependency audit
# ======================================================================


def test_the_bridge_introduces_no_runtime_dependency() -> None:
    """No web framework, no server, no socket, no thread, no background
    worker. The transport is a function call, and the Roadmap requires no
    HTTP server in Sprint 1."""
    forbidden = (
        "http", "socket", "threading", "asyncio", "multiprocessing",
        "concurrent", "queue", "subprocess", "flask", "fastapi",
        "starlette", "uvicorn", "requests", "aiohttp", "pydantic",
        "websockets", "grpc",
    )
    imported = _package_imports()
    assert not [
        n for n in imported
        if any(n == f or n.startswith(f + ".") for f in forbidden)
    ], imported


def test_the_bridge_depends_only_on_c1_to_c17() -> None:
    """The brief's bound, enforced rather than stated."""
    internal = {n for n in _package_imports() if n.startswith("master_agent")}
    assert all(
        n.startswith((
            "master_agent.foundation.",
            "master_agent.kernel",
            "master_agent.coordinator",
            "master_agent.api",
            "master_agent.runtime_bridge",
        ))
        for n in internal
    ), internal


def test_the_bridge_does_not_reach_the_shipped_runtime_engine() -> None:
    """`master_agent/runtime/` is MB024's Runtime Engine. Importing
    through its `__init__` would give this layer a dependency the brief
    forbids — which is why the package is named `runtime_bridge`."""
    assert not [
        n for n in _package_imports()
        if n == "master_agent.runtime" or n.startswith("master_agent.runtime.")
    ]


def test_the_bridge_imports_no_surface() -> None:
    """A bridge that knew who was on the other side would not be one."""
    forbidden = (
        "master_agent.ui", "master_agent.desktop", "master_agent.dashboard",
        "master_agent.cli", "master_agent.launcher", "master_agent.voice",
        "master_agent.orchestrator", "master_agent.executor",
        "master_agent.planner", "master_agent.missions",
        "master_agent.mission_control", "master_agent.broker",
        "master_agent.ai_infrastructure", "master_agent.permissions",
        "master_agent.plugins", "master_agent.providers",
        "master_agent.verification", "master_agent.memory",
    )
    assert not [
        n for n in _package_imports()
        if any(n.startswith(f) for f in forbidden)
    ]


def test_the_transport_accepts_any_mapping(tmp_path: Path) -> None:
    """Transport independence: the envelope is a mapping, not a type this
    layer invented, so any carrier that can produce one can call it."""
    from types import MappingProxyType

    runtime, _, _, _ = build(tmp_path)
    frozen = MappingProxyType({OPERATION: "status"})
    assert runtime.handle(frozen)["kind"] == "ok"


def test_the_transport_needs_no_framework(tmp_path: Path) -> None:
    """A round trip through nothing but `json` and a dict."""
    runtime, _, _, _ = build(tmp_path)
    wire_in = json.dumps(
        {OPERATION: "authorize", ARGUMENTS: {"request": encode_request(request())}}
    )
    wire_out = json.dumps(runtime.handle(json.loads(wire_in)))
    assert json.loads(wire_out)["kind"] == "ok"


def test_the_public_surface_is_two_doors() -> None:
    """No speculative API. `handle()` and `execute()`, and nothing
    beside them."""
    surface = {n for n in dir(Runtime) if not n.startswith("_")}
    assert surface == {"handle", "execute"}


def test_no_confirmation_parameter_exists_anywhere() -> None:
    """§11.8 and VEDA 04 A3 — a bridge is exactly where one would be added
    for a surface's convenience."""
    forbidden = (
        "confirm", "confirmation", "sure", "acknowledge", "force", "yes",
        "consent", "delay", "cooldown", "grace", "throttle", "retry",
    )
    for name in ("handle", "execute"):
        for param in inspect.signature(getattr(Runtime, name)).parameters:
            assert not any(w in param.lower() for w in forbidden), name
    source = "".join(p.read_text(encoding="utf-8") for p in PACKAGE.rglob("*.py"))
    assert '"confirm"' not in source


def test_it_is_exported_from_its_package() -> None:
    from master_agent.runtime_bridge import Runtime as Exported

    assert Exported is Runtime
