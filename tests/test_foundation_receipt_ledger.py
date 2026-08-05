"""Sprint 1, Component 13 — Receipt Ledger.

**Every test below proves a specification invariant.** None exists to
raise coverage; each names the clause it defends, and each would fail if
that clause were violated.

The clauses under test:

| Source | Requirement |
|---|---|
| VEDA 04 A1 | *"if the intent write fails, the action does not occur.
  No exceptions, no buffering, no fire-and-forget."* |
| Kernel Spec §7.2 K3 | The intent write runs last; if it fails, nothing executes |
| Kernel Spec §9.1 | `IntentRecord ─┬─ AttemptRecord (0..n) └─ OutcomeRecord (0..1, terminal)` |
| Kernel Spec §9.2 | *"Every arrow is an identifier, never a copy."* |
| Kernel Spec §9.5 | Reconciliation — an orphaned record is a gap |
| Kernel Spec §11.3 | Ledger unavailable ⇒ **fail closed**, no buffering |
| Kernel Spec §8.6 | `(intent_id, attempt_seq)` is the idempotency key |
| Kernel Spec §14.1 | The consequence marker: never null, never omitted |
| Roadmap §2 C13 | *"No update. No delete. At any privilege level."* |

Nothing here reads a wall clock: every moment is fixed and passed in.
"""
from __future__ import annotations

import ast
import inspect
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest

from master_agent.foundation.consequence import Consequence, Cost, CostBasis
from master_agent.foundation.execution_request import PENDING_CONSEQUENCE_ENGINE
from master_agent.foundation.receipt import ExecutionOutcome, Receipt
from master_agent.foundation.warrant import ReversibilityClass
from master_agent.ledger.receipt_ledger import (
    AttemptRecord,
    IntentRecord,
    InvalidLedgerRecord,
    LedgerIntegrityError,
    LedgerUnavailable,
    ReceiptLedger,
    RecordKind,
)
from master_agent.persistence.store import JsonFileStateStore, StateStore

T0 = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)

QUARTET = Consequence(
    what_changes="one folder is removed",
    cost=Cost(description="none", basis=CostBasis.FREE),
    if_nothing="the folder stays",
    reversibility=ReversibilityClass.REVERSIBLE,
)


class SpyStore:
    """A `StateStore` that records how it was used and can fail on demand.

    Exists to prove *durability assumptions* and *failure behaviour*, both
    of which are statements about how the ledger talks to storage and are
    unobservable from the ledger's return values alone.
    """

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.append_calls: list[list[dict[str, Any]]] = []
        self.fail_next_append = False
        self.fail_read = False

    def append_events(self, events: list[dict[str, Any]]) -> None:
        self.append_calls.append(list(events))
        if self.fail_next_append:
            raise OSError("disk gone")
        # Round-trip through JSON so a test cannot pass on an object the
        # real store could not have persisted.
        self.events.extend(json.loads(json.dumps(e, default=str)) for e in events)

    def read_events(self) -> list[dict[str, Any]]:
        if self.fail_read:
            raise OSError("log unreadable")
        return list(self.events)

    def save_snapshot(self, envelope: Any) -> None: ...
    def load_snapshot(self) -> Any: return None
    def has_state(self) -> bool: return bool(self.events)
    def clear(self) -> None: self.events.clear()


def intent(warrant_id: str = "wrt-1", **overrides) -> IntentRecord:
    defaults = {
        "warrant_id": warrant_id,
        "objective_id": "obj-1",
        "principal_id": "founder",
        "capability": "Filesystem.DeleteFolder",
        "reversibility_class": ReversibilityClass.REVERSIBLE,
        "expected_effect": "the folder is gone",
        "consequence": PENDING_CONSEQUENCE_ENGINE,
        "recorded_at": T0,
    }
    return IntentRecord(**{**defaults, **overrides})


def attempt(warrant_id: str = "wrt-1", seq: int = 1, **overrides) -> AttemptRecord:
    defaults = {
        "warrant_id": warrant_id,
        "attempt_seq": seq,
        "recorded_at": T0,
    }
    return AttemptRecord(**{**defaults, **overrides})


def receipt(warrant_id: str = "wrt-1", **overrides) -> Receipt:
    defaults = {
        "receipt_id": f"rcp-{warrant_id}",
        "objective_id": "obj-1",
        "principal_id": "founder",
        "warrant_id": warrant_id,
        "correlation_id": "corr-1",
        "trace_id": "trace-1",
        "capability": "Filesystem.DeleteFolder",
        "attempt": 1,
        "outcome": ExecutionOutcome.SUCCEEDED,
        "started_at": T0,
        "completed_at": T0 + timedelta(seconds=1),
    }
    return Receipt(**{**defaults, **overrides})


def ledger() -> tuple[ReceiptLedger, SpyStore]:
    store = SpyStore()
    return ReceiptLedger(store), store


# ======================================================================
# APPEND-ONLY — Roadmap §2 C13: "No update. No delete. At any privilege level."
# ======================================================================


def test_the_ledger_exposes_no_mutator_at_any_privilege_level() -> None:
    """*"No update. No delete. **At any privilege level**"* — so a private
    one is a violation too. This inspects every attribute, not just the
    public surface."""
    forbidden = ("update", "delete", "remove", "truncate", "pop", "clear",
                 "edit", "amend", "rewrite", "overwrite", "purge", "drop")
    offenders = [
        name
        for name in dir(ReceiptLedger)
        if not name.startswith("__")
        and any(word in name.lower() for word in forbidden)
    ]
    assert not offenders, f"ReceiptLedger exposes {offenders}"


def test_the_ledger_has_no_instance_dict() -> None:
    """`__slots__` — no caller can bolt a mutable cache onto a ledger and
    have it disagree with the store."""
    lg, _ = ledger()
    with pytest.raises(AttributeError):
        lg.anything = 1


def test_recording_only_ever_grows_the_history() -> None:
    """Append-only stated as an observable: length is monotonic and no
    prior entry ever changes."""
    lg, _ = ledger()
    seen: list[tuple] = []
    lg.record_intent(intent())
    seen.append(lg.read())
    lg.record_attempt(attempt())
    seen.append(lg.read())
    lg.record_outcome(receipt())
    seen.append(lg.read())

    assert [len(s) for s in seen] == [1, 2, 3]
    for earlier, later in pairwise(seen):
        assert later[: len(earlier)] == earlier


def test_read_returns_a_copy_the_caller_cannot_use_to_reach_history() -> None:
    lg, _ = ledger()
    lg.record_intent(intent())
    first = lg.read()
    lg.record_attempt(attempt())
    assert len(first) == 1
    assert len(lg.read()) == 2


def test_stored_records_are_immutable() -> None:
    """The entries handed back are frozen value objects, so a reader
    cannot edit history through a reference it was given."""
    from dataclasses import FrozenInstanceError

    lg, _ = ledger()
    lg.record_intent(intent())
    stored = lg.read()[0]
    with pytest.raises(FrozenInstanceError):
        stored.warrant_id = "other"


# ======================================================================
# ORDERING — §9.1's graph is only readable if order survives
# ======================================================================


def test_records_are_read_in_the_order_they_were_appended() -> None:
    lg, _ = ledger()
    lg.record_intent(intent())
    lg.record_attempt(attempt(seq=1))
    lg.record_attempt(attempt(seq=2))
    lg.record_outcome(receipt())
    kinds = [type(e).__name__ for e in lg.read()]
    assert kinds == ["IntentRecord", "AttemptRecord", "AttemptRecord", "Receipt"]
    assert [e.attempt_seq for e in lg.read() if isinstance(e, AttemptRecord)] == [1, 2]


def test_interleaved_warrants_keep_one_global_order() -> None:
    lg, _ = ledger()
    lg.record_intent(intent("wrt-1"))
    lg.record_intent(intent("wrt-2"))
    lg.record_attempt(attempt("wrt-1", 1))
    lg.record_attempt(attempt("wrt-2", 1))
    assert [e.warrant_id for e in lg.read()] == ["wrt-1", "wrt-2", "wrt-1", "wrt-2"]


def test_reading_one_warrant_narrows_without_reordering() -> None:
    """§9.2 — one tree of the linkage graph, in its own order."""
    lg, _ = ledger()
    lg.record_intent(intent("wrt-1"))
    lg.record_intent(intent("wrt-2"))
    lg.record_attempt(attempt("wrt-1", 1))
    lg.record_outcome(receipt("wrt-1"))
    tree = lg.read("wrt-1")
    assert [type(e).__name__ for e in tree] == [
        "IntentRecord", "AttemptRecord", "Receipt",
    ]
    assert all(e.warrant_id == "wrt-1" for e in tree)


def test_reading_an_unknown_warrant_returns_nothing_rather_than_raising() -> None:
    lg, _ = ledger()
    assert lg.read("never-seen") == ()


def test_order_survives_a_restart() -> None:
    """A ledger that cannot reconstruct its own order after a crash is not
    an audit spine."""
    store = SpyStore()
    first = ReceiptLedger(store)
    first.record_intent(intent())
    first.record_attempt(attempt(seq=1))
    first.record_attempt(attempt(seq=2))
    first.record_outcome(receipt())

    restarted = ReceiptLedger(store)
    assert [type(e).__name__ for e in restarted.read()] == [
        "IntentRecord", "AttemptRecord", "AttemptRecord", "Receipt",
    ]


# ======================================================================
# DURABILITY ASSUMPTIONS — A1: "no buffering, no fire-and-forget"
# ======================================================================


def test_a_write_reaches_the_store_before_the_call_returns() -> None:
    """The whole of K3 depends on this: the Kernel checks that the write
    succeeded *before* anything executes."""
    lg, store = ledger()
    lg.record_intent(intent())
    assert len(store.read_events()) == 1


def test_each_write_is_one_append_of_one_event() -> None:
    """*"No buffering"* and no batching, stated as an observable about the
    calls made to storage."""
    lg, store = ledger()
    lg.record_intent(intent())
    lg.record_attempt(attempt())
    lg.record_outcome(receipt())
    assert len(store.append_calls) == 3
    assert all(len(call) == 1 for call in store.append_calls)


def test_nothing_is_ever_held_back() -> None:
    """Entries in memory and events in the store stay equal at every step
    — there is no moment at which the ledger knows more than the disk."""
    lg, store = ledger()
    lg.record_intent(intent())
    assert len(lg) == len(store.read_events()) == 1
    lg.record_attempt(attempt())
    assert len(lg) == len(store.read_events()) == 2


def test_a_write_is_visible_to_an_independent_reader(tmp_path: Path) -> None:
    """Against the real `JsonFileStateStore`: a second ledger built over
    the same root sees the record, which is only possible if it reached
    the filesystem rather than memory."""
    store = JsonFileStateStore(tmp_path)
    writer = ReceiptLedger(store)
    writer.record_intent(intent())

    reader = ReceiptLedger(JsonFileStateStore(tmp_path))
    assert len(reader.read()) == 1
    assert reader.has_intent("wrt-1")


def test_the_ledger_opens_no_file_itself(tmp_path: Path) -> None:
    """`persistence` is *"the only place in Kalpavriksha that reads or
    writes persistence files."* The ledger writes through the store."""
    source = MODULE.read_text(encoding="utf-8")
    assert "open(" not in source
    assert "Path(" not in source


# ======================================================================
# FAILURE BEHAVIOUR — §11.3 fail closed, fail loudly, never discard
# ======================================================================


def test_a_storage_failure_raises_rather_than_returning() -> None:
    """§11.3 — fail closed. A silent success here would mean an action
    executing with no record of its authorization."""
    lg, store = ledger()
    store.fail_next_append = True
    with pytest.raises(LedgerUnavailable, match="could not write"):
        lg.record_intent(intent())


def test_a_failed_write_leaves_no_trace_in_memory() -> None:
    """A ledger that remembered a write the store rejected would be lying
    to the next reader — and would let K3 pass on an action with no
    durable intent."""
    lg, store = ledger()
    store.fail_next_append = True
    with pytest.raises(LedgerUnavailable):
        lg.record_intent(intent())
    assert len(lg) == 0
    assert lg.read() == ()
    assert not lg.has_intent("wrt-1")


def test_a_failed_write_can_be_retried_by_the_caller() -> None:
    """The failure must not leave a phantom duplicate that blocks the
    caller's own retry. The *ledger* never retries; the caller may."""
    lg, store = ledger()
    store.fail_next_append = True
    with pytest.raises(LedgerUnavailable):
        lg.record_intent(intent())
    store.fail_next_append = False
    assert lg.record_intent(intent()) == "wrt-1"
    assert len(lg) == 1


def test_the_ledger_never_retries_on_its_own() -> None:
    """One call, one attempt at storage. A retry loop here would be the
    buffering A1 forbids, wearing a different name."""
    lg, store = ledger()
    store.fail_next_append = True
    with pytest.raises(LedgerUnavailable):
        lg.record_intent(intent())
    assert len(store.append_calls) == 1


def test_an_unreadable_log_fails_closed_at_construction() -> None:
    """A ledger that started empty after a read failure would silently
    lose duplicate protection and referential integrity."""
    store = SpyStore()
    store.fail_read = True
    with pytest.raises(LedgerUnavailable, match="could not be read"):
        ReceiptLedger(store)


def test_ledger_unavailable_cannot_be_swallowed_as_a_value_error() -> None:
    """A caller wrapping record construction in `except ValueError` must
    never absorb a storage failure by accident."""
    assert not issubclass(LedgerUnavailable, ValueError)
    assert issubclass(LedgerUnavailable, RuntimeError)


def test_one_except_catches_every_refusal_to_write() -> None:
    """Integrity refusals subclass `LedgerUnavailable` so a caller cannot
    handle "the disk is gone" and accidentally proceed past "this outcome
    has no intent"."""
    assert issubclass(LedgerIntegrityError, LedgerUnavailable)


@pytest.mark.parametrize(
    "call",
    [
        lambda lg: lg.record_intent("not a record"),
        lambda lg: lg.record_attempt("not a record"),
        lambda lg: lg.record_outcome("not a record"),
    ],
)
def test_a_malformed_call_is_refused_before_any_write(call) -> None:
    lg, store = ledger()
    with pytest.raises(InvalidLedgerRecord):
        call(lg)
    assert store.append_calls == []


# ======================================================================
# REFERENTIAL INTEGRITY — §9.2 linkage, §9.5 reconciliation
# ======================================================================


def test_an_attempt_without_an_intent_is_refused() -> None:
    """§7.2 K3 writes the intent before anything executes, so an attempt
    with no intent describes an execution that could not have happened."""
    lg, _ = ledger()
    with pytest.raises(LedgerIntegrityError, match="no intent record"):
        lg.record_attempt(attempt())


def test_an_outcome_without_an_intent_is_refused() -> None:
    """§9.5's reconciliation gap, made unwritable rather than detectable."""
    lg, _ = ledger()
    with pytest.raises(LedgerIntegrityError, match="no intent record"):
        lg.record_outcome(receipt())


def test_the_refusal_names_the_warrant() -> None:
    lg, _ = ledger()
    with pytest.raises(LedgerIntegrityError, match="wrt-99"):
        lg.record_outcome(receipt("wrt-99"))


def test_an_orphan_is_refused_before_it_reaches_storage() -> None:
    """Refused, not written-then-flagged: the log never contains the
    orphan at all."""
    lg, store = ledger()
    with pytest.raises(LedgerIntegrityError):
        lg.record_attempt(attempt())
    assert store.append_calls == []
    assert store.read_events() == []


def test_integrity_holds_for_a_sibling_warrant() -> None:
    """An intent for one warrant does not license records for another."""
    lg, _ = ledger()
    lg.record_intent(intent("wrt-1"))
    with pytest.raises(LedgerIntegrityError, match="wrt-2"):
        lg.record_attempt(attempt("wrt-2", 1))


# ======================================================================
# IMPOSSIBLE STATES — §9.1's shapes made unconstructable
# ======================================================================


def test_a_warrant_has_exactly_one_intent() -> None:
    """§9.1 roots each tree at one intent; two would make the tree
    ambiguous and the audit unanswerable."""
    lg, _ = ledger()
    lg.record_intent(intent())
    with pytest.raises(LedgerIntegrityError, match="already has an intent"):
        lg.record_intent(intent())


def test_a_warrant_has_at_most_one_outcome() -> None:
    """§9.1 — `OutcomeRecord (0..1, terminal)`."""
    lg, _ = ledger()
    lg.record_intent(intent())
    lg.record_outcome(receipt())
    with pytest.raises(LedgerIntegrityError, match="already has an outcome"):
        lg.record_outcome(receipt())


def test_nothing_follows_the_outcome() -> None:
    """*"Terminal"* is the load-bearing word: an attempt recorded after
    settlement would describe execution continuing past its own receipt."""
    lg, _ = ledger()
    lg.record_intent(intent())
    lg.record_outcome(receipt())
    with pytest.raises(LedgerIntegrityError, match="already settled"):
        lg.record_attempt(attempt(seq=2))


def test_settlement_is_reported() -> None:
    lg, _ = ledger()
    lg.record_intent(intent())
    assert not lg.is_settled("wrt-1")
    lg.record_outcome(receipt())
    assert lg.is_settled("wrt-1")


def test_the_impossible_states_stay_impossible_after_a_restart() -> None:
    """The indexes are rebuilt from the log, so a restart cannot be used
    to write a second intent or a post-settlement attempt."""
    store = SpyStore()
    first = ReceiptLedger(store)
    first.record_intent(intent())
    first.record_attempt(attempt(seq=1))
    first.record_outcome(receipt())

    restarted = ReceiptLedger(store)
    with pytest.raises(LedgerIntegrityError, match="already has an intent"):
        restarted.record_intent(intent())
    with pytest.raises(LedgerIntegrityError, match="already settled"):
        restarted.record_attempt(attempt(seq=2))
    with pytest.raises(LedgerIntegrityError, match="already has an outcome"):
        restarted.record_outcome(receipt())


# ======================================================================
# DUPLICATE PROTECTION — §8.6's idempotency key
# ======================================================================


def test_an_attempt_sequence_is_recorded_once() -> None:
    """§8.6 — *"The Kernel provides the key — `(intent_id, attempt_seq)`."*
    Recording it twice would make one attempt look like two."""
    lg, _ = ledger()
    lg.record_intent(intent())
    lg.record_attempt(attempt(seq=1))
    with pytest.raises(LedgerIntegrityError, match="already recorded"):
        lg.record_attempt(attempt(seq=1))


def test_distinct_sequences_are_both_recorded() -> None:
    lg, _ = ledger()
    lg.record_intent(intent())
    lg.record_attempt(attempt(seq=1))
    lg.record_attempt(attempt(seq=2))
    assert len(lg.read("wrt-1")) == 3


def test_the_key_is_scoped_to_the_warrant() -> None:
    """The key is the *pair*. Attempt 1 of two different warrants is two
    different attempts."""
    lg, _ = ledger()
    lg.record_intent(intent("wrt-1"))
    lg.record_intent(intent("wrt-2"))
    lg.record_attempt(attempt("wrt-1", 1))
    lg.record_attempt(attempt("wrt-2", 1))
    assert len(lg) == 4


def test_duplicate_protection_survives_a_restart() -> None:
    store = SpyStore()
    first = ReceiptLedger(store)
    first.record_intent(intent())
    first.record_attempt(attempt(seq=1))

    restarted = ReceiptLedger(store)
    with pytest.raises(LedgerIntegrityError, match="already recorded"):
        restarted.record_attempt(attempt(seq=1))


# ======================================================================
# DETERMINISTIC SERIALIZATION
# ======================================================================


def test_intent_serialisation_is_deterministic_and_json_ready() -> None:
    assert intent().as_dict() == intent().as_dict()
    assert json.loads(json.dumps(intent().as_dict()))


def test_intent_serialisation_carries_a1s_field_list() -> None:
    """VEDA 04 A1: *"Intent carries actor, rule (if any), reversibility
    class, expected effect, and the consequence quartet."*"""
    assert intent().as_dict() == {
        "kind": "intent",
        "warrant_id": "wrt-1",
        "objective_id": "obj-1",
        "principal_id": "founder",
        "capability": "Filesystem.DeleteFolder",
        "reversibility_class": "reversible",
        "expected_effect": "the folder is gone",
        "consequence": "pending_consequence_engine",
        "recorded_at": "2026-08-05T12:00:00+00:00",
        "rule_ref": None,
    }


def test_attempt_serialisation_is_deterministic_and_json_ready() -> None:
    assert attempt().as_dict() == attempt().as_dict()
    assert attempt().as_dict() == {
        "kind": "attempt",
        "warrant_id": "wrt-1",
        "attempt_seq": 1,
        "recorded_at": "2026-08-05T12:00:00+00:00",
    }


def test_the_consequence_is_never_serialised_as_null() -> None:
    """§14.1 — *"never null, never omitted, and never a partial quartet."*
    This is the invariant M1's note for C13 requires."""
    for consequence in (PENDING_CONSEQUENCE_ENGINE, QUARTET):
        projected = intent(consequence=consequence).as_dict()["consequence"]
        assert projected is not None


def test_the_pending_marker_serialises_to_the_literal_the_spec_names() -> None:
    assert intent().as_dict()["consequence"] == "pending_consequence_engine"


def test_every_record_kind_is_tagged_on_the_wire() -> None:
    """Replay depends on the discriminator; an untagged record is one the
    ledger could not reconstruct after a restart."""
    lg, store = ledger()
    lg.record_intent(intent())
    lg.record_attempt(attempt())
    lg.record_outcome(receipt())
    kinds = [e["kind"] for e in store.read_events()]
    assert kinds == ["intent", "attempt", "outcome"]
    assert set(kinds) == {k.value for k in RecordKind}


def test_records_round_trip_through_storage_unchanged() -> None:
    """Equality after replay is the proof that serialisation lost
    nothing — the property an audit fifteen years out depends on."""
    store = SpyStore()
    first = ReceiptLedger(store)
    original_intent = intent(consequence=QUARTET, rule_ref="rule-3")
    original_attempt = attempt(seq=4)
    original_receipt = receipt()
    first.record_intent(original_intent)
    first.record_attempt(original_attempt)
    first.record_outcome(original_receipt)

    replayed = ReceiptLedger(store).read()
    assert replayed[0] == original_intent
    assert replayed[1] == original_attempt
    assert replayed[2] == original_receipt


def test_decimal_precision_survives_the_round_trip() -> None:
    """A cost that drifts is a cost the founder cannot rely on."""
    priced = Consequence(
        what_changes="one reasoning call",
        cost=Cost(
            description="published rate",
            basis=CostBasis.PRICED,
            amount=Decimal("0.07"),
            currency="USD",
        ),
        if_nothing="unanswered",
        reversibility=ReversibilityClass.REVERSIBLE,
    )
    store = SpyStore()
    ReceiptLedger(store).record_intent(intent(consequence=priced))
    replayed = ReceiptLedger(store).read()[0]
    assert replayed.consequence.cost.amount == Decimal("0.07")


def test_timezone_normalisation_survives_the_round_trip() -> None:
    from datetime import timezone

    ist = timezone(timedelta(hours=5, minutes=30))
    store = SpyStore()
    ReceiptLedger(store).record_intent(
        intent(recorded_at=datetime(2026, 8, 5, 17, 30, tzinfo=ist))
    )
    assert ReceiptLedger(store).read()[0].recorded_at == T0


# ======================================================================
# RECORD INVARIANTS — enforced at construction
# ======================================================================


@pytest.mark.parametrize(
    "field",
    ["warrant_id", "objective_id", "principal_id", "capability", "expected_effect"],
)
@pytest.mark.parametrize("bad", ["", "   ", None, 42])
def test_intent_identifiers_are_required(field, bad) -> None:
    with pytest.raises(InvalidLedgerRecord, match=field):
        intent(**{field: bad})


def test_an_intent_consequence_is_never_null() -> None:
    """§14.1, enforced structurally rather than by convention."""
    with pytest.raises(InvalidLedgerRecord, match="never null"):
        intent(consequence=None)


def test_a_blank_rule_ref_is_refused() -> None:
    """Absent or a reference; a blank string is an unanswered question
    wearing an answer."""
    with pytest.raises(InvalidLedgerRecord, match="rule_ref"):
        intent(rule_ref="  ")


def test_a_naive_recorded_at_is_refused() -> None:
    with pytest.raises(InvalidLedgerRecord, match="timezone-aware"):
        intent(recorded_at=datetime(2026, 8, 5, 12, 0))  # noqa: DTZ001


@pytest.mark.parametrize("bad", [0, -1])
def test_an_attempt_sequence_is_one_based(bad) -> None:
    with pytest.raises(InvalidLedgerRecord, match="attempt zero"):
        attempt(seq=bad)


@pytest.mark.parametrize("bad", [True, "1", 1.0])
def test_a_non_integer_attempt_sequence_is_refused(bad) -> None:
    with pytest.raises(InvalidLedgerRecord, match="integer"):
        attempt(seq=bad)


# ======================================================================
# CONSTITUTIONAL — the ledger records; it never decides
# ======================================================================

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE = REPO_ROOT / "src" / "master_agent" / "ledger" / "receipt_ledger.py"


def _module_imports() -> list[str]:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    return imported


def test_it_never_decides_evaluates_or_authorizes() -> None:
    """The ledger records events. Every one of these verbs belongs to the
    Kernel."""
    forbidden = ("authorize", "authorise", "decide", "evaluate", "approve",
                 "deny", "mint", "execute", "invoke", "retry", "settle_action")
    offenders = [
        name
        for name in dir(ReceiptLedger)
        if not name.startswith("__")
        and any(word in name.lower() for word in forbidden)
    ]
    assert not offenders, f"ReceiptLedger exposes {offenders}"


def test_it_reads_no_ambient_time() -> None:
    """Every moment is supplied by the caller from the canonical clock."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    banned = {"datetime.now", "datetime.utcnow", "datetime.today", "time.time"}
    calls = [
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ".".join(ast.unparse(node.func).split(".")[-2:]) in banned
    ]
    assert not calls, f"receipt_ledger.py reads ambient time: {calls}"


def test_it_imports_nothing_that_could_act() -> None:
    forbidden = (
        "master_agent.executor",
        "master_agent.orchestrator",
        "master_agent.runtime",
        "master_agent.plugins",
        "master_agent.broker",
        "master_agent.planner",
        "master_agent.verification",
        "subprocess",
        "socket",
        "threading",
        "asyncio",
    )
    offenders = [
        n for n in _module_imports() if any(n.startswith(f) for f in forbidden)
    ]
    assert not offenders, f"receipt_ledger.py imports {offenders}"


def test_it_depends_on_persistence_only_through_the_protocol() -> None:
    """M1 declares `persistence.StateStore` as the dependency — the
    contract, not an implementation."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    from_persistence = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and (node.module or "").startswith("master_agent.persistence")
        for alias in node.names
    }
    assert from_persistence == {"StateStore"}


def test_the_store_is_injected_never_constructed() -> None:
    """A ledger that built its own store would decide where the audit
    spine lives."""
    params = list(inspect.signature(ReceiptLedger.__init__).parameters)
    assert params == ["self", "store"]


def test_the_write_surface_is_exactly_what_the_roadmap_declares() -> None:
    """Roadmap §2 C13: `record_intent / record_attempt / record_outcome /
    read`. A fourth writer would exceed the declared surface."""
    writers = {
        name
        for name in dir(ReceiptLedger)
        if not name.startswith("_") and name.startswith("record")
    }
    assert writers == {"record_intent", "record_attempt", "record_outcome"}


def test_the_spy_store_satisfies_the_shipped_protocol() -> None:
    """If the double diverged from `StateStore`, every durability and
    failure test above would be proving something about a fiction."""
    assert isinstance(SpyStore(), StateStore)
