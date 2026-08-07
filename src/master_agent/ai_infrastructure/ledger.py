"""The decision ledger — a `DecisionRecord` for every AI task (Mission
Brief 032 Deliverables 7 and 8).

The Broker already produces the evidence; MB031 built `DecisionRecord` to
carry *everything needed to reproduce an answer*, including the policy and
the provider profiles exactly as they were. What was missing was somewhere
durable to put it, keyed by the task it belongs to.

This is that place, and it is wired as the Broker's `sink` — the outbound
port MB031 defined for precisely this (the same move MB025 made with
`CheckpointSink` and MB028.0 with `ApprovalGate`). The Broker gains no
dependency on storage; storage gains every decision the Broker makes,
including the refusals.

## Replay uses the record, never today's policy

`replay()` reconstructs a decision from the record's **own** policy and
**own** provider profiles. Replaying against the current estate would not
be reproducing history — it would be making a new decision and calling it
history (MB031 §5, Deliverable 8). That holds across a restart too: the
record is serialised whole, so a decision made under `balanced/1` last
Tuesday still replays under `balanced/1` after the founder has switched to
`prefer_local`.

## What is appended and what is not

Decisions are append-only: nothing rewrites a `DecisionRecord`, and
`record()` refuses to. The one field that changes after the fact is the
*approval state*, because "the founder was asked" and "the founder
answered" are two moments in the life of one decision, and splitting them
into two entries would make the ledger read as though the Broker decided
twice.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from master_agent.ai_infrastructure.tiers import (
    cost_tier,
    describe_cost,
    describe_quality,
    quality_basis,
    quality_tier,
)
from master_agent.broker.broker import CapabilityBroker
from master_agent.broker.decision import BrokerDecision, DecisionRecord

# ---- approval states ----------------------------------------------------
#
# The life of one decision, from the Approval Queue's point of view. A free
# provider under a permitting policy never leaves `not_required`, which is
# MB032 Deliverable 6 stated as data.

NOT_REQUIRED = "not_required"
PENDING = "pending"
GRANTED = "granted"
DENIED = "denied"
APPROVAL_STATES = (NOT_REQUIRED, PENDING, GRANTED, DENIED)

LEDGER_FILENAME = "broker_decisions.json"

#: What `ExecutionRecord.outcome` says when the answer came out of the
#: Prompt Cache and no provider was contacted (MB033 Rule 2). Its own
#: value rather than a flag on a success, because an execution that did
#: not happen must never be counted as one that did.
CACHE_HIT = "cache_hit"


#: MB038 lifecycle vocabulary. How a call ended, as distinct from what
#: it produced. Closed, and deliberately small.
COMPLETED = "completed"
FAILED = "failed"
#: The caller stopped waiting; the provider did not stop working.
ABANDONED = "abandoned"
#: Refused before the call was made -- admission control.
REFUSED = "refused"

LIFECYCLES = (COMPLETED, FAILED, ABANDONED, REFUSED)


@dataclass(frozen=True)
class ExecutionReplay:
    """One call, re-read rather than re-run (MB038 Step 12).

    Every field is lifted verbatim from the stored record. Nothing here is
    derived, defaulted or inferred: an execution that carried no budget
    replays as `budget=None`, which is the truth about it, and a record
    written before MB038 replays with every new field absent rather than
    with a fabricated one.
    """

    entry_id: int
    #: False when the decision was never executed -- refused by the Broker,
    #: or still pending approval. Distinct from an execution that happened
    #: and went badly.
    recorded: bool = False
    provider_id: str = ""
    outcome: str = ""
    lifecycle: str = ""
    admission: str = ""
    admission_reason: str = ""
    budget: dict[str, Any] | None = None
    observation: dict[str, Any] | None = None
    timeout: dict[str, Any] | None = None

    @property
    def timeout_reason(self) -> str:
        """Which of the three deadlines ended this call, if one did."""
        return (self.timeout or {}).get("reason", "")

    @property
    def bound_by(self) -> str:
        """Which constraint produced the total budget. The single most
        useful field when asking why something timed out."""
        return ((self.budget or {}).get("derivation") or {}).get("total_bound_by", "")

    @property
    def abandoned(self) -> bool:
        return self.lifecycle == ABANDONED

    def as_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "recorded": self.recorded,
            "provider_id": self.provider_id,
            "outcome": self.outcome,
            "lifecycle": self.lifecycle,
            "admission": self.admission,
            "admission_reason": self.admission_reason,
            "budget": self.budget,
            "observation": self.observation,
            "timeout": self.timeout,
            "timeout_reason": self.timeout_reason,
            "bound_by": self.bound_by,
        }


@dataclass(frozen=True)
class ExecutionRecord:
    """What actually happened when a decision was carried out (MB033
    Rule 3).

    Every field here exists because a later brief needs it: latency and
    tokens to know what a provider really costs, `cost` and `locality` to
    total the token economy, `quality_declared` to compare what a provider
    claimed against what it delivered once a verifier exists, `retries` to
    tell a flaky transport from a slow model, and `cache` to count reuse.

    **It is measurement, not judgement.** Nothing here scores a provider,
    and the fields a future benchmark store will read are recorded rather
    than interpreted (ADR-0017 Decision 5, ADR-0018 Decision 2).
    """

    provider_id: str
    outcome: str
    #: Wall clock the founder actually waited, including failed attempts.
    latency_ms: float | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost: float | None = None
    #: The quality the provider's profile *declared* at decision time, and
    #: what that claim was based on. Recorded so a future benchmark can be
    #: compared against the claim it is replacing.
    quality_declared: float | None = None
    quality_basis: str = ""
    locality: str = ""
    model: str = ""
    retries: int = 0
    cache: str = "not_consulted"
    error: str = ""
    executed_at: datetime | None = None
    #: MB035. The Verification verdict for the generated text, and the
    #: Evidence it came from. Empty when nothing was asked of the answer —
    #: which is a different fact from "it was checked and failed", and the
    #: Dashboard says which.
    verdict: str = ""
    evidence_id: str = ""
    # ---- MB038 timeout evidence ------------------------------------------
    #
    # Recorded so a timeout is diagnosable rather than merely annoying.
    # The pair that matters most is `budget` (what was granted, and what it
    # was derived from) beside `observation` (what actually happened):
    # together they separate *the budget was too small* from *the provider
    # was too slow*, which are different defects with different owners and
    # were one log line until this brief.
    #
    # `None` throughout means "this call had none", never zero. A
    # pre-MB038 record and an unbudgeted call both read as absent, which
    # is the truth about both.
    budget: dict[str, Any] | None = None
    observation: dict[str, Any] | None = None
    #: The `TimeoutEvent` that ended the call, when one did.
    timeout: dict[str, Any] | None = None
    #: The admission decision that let this call be made, or refused it.
    #: Empty when nothing was asked -- the pre-MB038 path.
    admission: str = ""
    admission_reason: str = ""
    #: MB038. How the call *ended*, as distinct from what it produced.
    #: `abandoned` is the one that matters: the caller stopped waiting but
    #: the provider did not stop working, so the call is neither completed
    #: nor cleanly failed and the machine may still be busy because of it.
    #: Empty for records written before MB038.
    lifecycle: str = ""

    @property
    def succeeded(self) -> bool:
        return self.outcome in ("succeeded", CACHE_HIT)

    @property
    def verified(self) -> bool:
        """The answer was checked against something stated in advance and
        matched all of it. `partially_matched` is not verified: half of
        what was asked for is not what was asked for."""
        return self.verdict == "matched"

    @property
    def from_cache(self) -> bool:
        return self.outcome == CACHE_HIT

    @property
    def total_tokens(self) -> int | None:
        """`None` unless both halves were reported — see
        `ProviderResponse.total_tokens` for why a sum over an unreported
        half is worse than no number."""
        if self.prompt_tokens is None or self.completion_tokens is None:
            return None
        return self.prompt_tokens + self.completion_tokens

    @property
    def latency_seconds(self) -> float | None:
        return None if self.latency_ms is None else self.latency_ms / 1000.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "outcome": self.outcome,
            "latency_ms": self.latency_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost": self.cost,
            "quality_declared": self.quality_declared,
            "quality_basis": self.quality_basis,
            "locality": self.locality,
            "model": self.model,
            "retries": self.retries,
            "cache": self.cache,
            "error": self.error,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "verdict": self.verdict,
            "evidence_id": self.evidence_id,
            "budget": self.budget,
            "observation": self.observation,
            "timeout": self.timeout,
            "admission": self.admission,
            "admission_reason": self.admission_reason,
            "lifecycle": self.lifecycle,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionRecord:
        executed = data.get("executed_at")
        return cls(
            provider_id=data.get("provider_id", ""),
            outcome=data.get("outcome", ""),
            latency_ms=data.get("latency_ms"),
            prompt_tokens=data.get("prompt_tokens"),
            completion_tokens=data.get("completion_tokens"),
            cost=data.get("cost"),
            quality_declared=data.get("quality_declared"),
            quality_basis=data.get("quality_basis", ""),
            locality=data.get("locality", ""),
            model=data.get("model", ""),
            retries=data.get("retries", 0),
            cache=data.get("cache", "not_consulted"),
            error=data.get("error", ""),
            executed_at=datetime.fromisoformat(executed) if executed else None,
            # Absent in every ledger written before MB035. Missing means
            # "nothing was asked of the answer", which is what those
            # executions were.
            verdict=data.get("verdict", ""),
            evidence_id=data.get("evidence_id", ""),
            # Absent in every ledger written before MB038. Missing means
            # the call had no budget and nothing timed it -- which is what
            # those executions were, and is a different fact from a budget
            # of zero.
            budget=data.get("budget"),
            observation=data.get("observation"),
            timeout=data.get("timeout"),
            admission=data.get("admission", ""),
            admission_reason=data.get("admission_reason", ""),
            lifecycle=data.get("lifecycle", ""),
        )


@dataclass(frozen=True)
class DecisionEntry:
    """One decision, as the rest of the system reads it.

    Everything a founder-facing surface needs is precomputed here — the
    tiers especially — so that no renderer has to classify anything
    (ADR-0016). `record` is the evidence underneath, kept whole so the
    entry is replayable rather than merely descriptive.
    """

    entry_id: int
    task_id: str
    capability: str
    outcome: str
    provider_id: str | None
    reason: str
    policy_version: str
    quality_floor: float
    cost: float | None
    quality: float | None
    cost_tier: str
    quality_tier: str
    quality_basis: str
    cost_detail: str
    quality_detail: str
    locality: str
    decided_at: datetime
    inputs_digest: str
    requester: str = ""
    approval_state: str = NOT_REQUIRED
    approval_id: str | None = None
    record: DecisionRecord | None = None
    #: What happened when the decision was carried out, or None while it
    #: has not been (MB033). A decision and its execution are two moments
    #: in the life of one task; two entries would read as two decisions.
    execution: ExecutionRecord | None = None

    @property
    def selected(self) -> bool:
        return self.provider_id is not None

    @property
    def executed(self) -> bool:
        return self.execution is not None

    @property
    def executable(self) -> bool:
        """Ready to run right now: something was chosen, and nothing is
        waiting on the founder."""
        return self.selected and self.approval_state in (NOT_REQUIRED, GRANTED)

    def as_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "task_id": self.task_id,
            "capability": self.capability,
            "outcome": self.outcome,
            "provider_id": self.provider_id,
            "reason": self.reason,
            "policy_version": self.policy_version,
            "quality_floor": self.quality_floor,
            "cost": self.cost,
            "quality": self.quality,
            "cost_tier": self.cost_tier,
            "quality_tier": self.quality_tier,
            "quality_basis": self.quality_basis,
            "cost_detail": self.cost_detail,
            "quality_detail": self.quality_detail,
            "locality": self.locality,
            "decided_at": self.decided_at.isoformat(),
            "inputs_digest": self.inputs_digest,
            "requester": self.requester,
            "approval_state": self.approval_state,
            "approval_id": self.approval_id,
            "record": self.record.as_dict() if self.record is not None else None,
            "execution": self.execution.as_dict() if self.execution is not None else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DecisionEntry:
        raw_record = data.get("record")
        # Absent in every ledger written before MB033. Missing means "not
        # executed", which is exactly what those entries were.
        raw_execution = data.get("execution")
        return cls(
            entry_id=int(data["entry_id"]),
            task_id=data.get("task_id", ""),
            capability=data.get("capability", ""),
            outcome=data.get("outcome", ""),
            provider_id=data.get("provider_id"),
            reason=data.get("reason", ""),
            policy_version=data.get("policy_version", ""),
            quality_floor=data.get("quality_floor", 0.0),
            cost=data.get("cost"),
            quality=data.get("quality"),
            cost_tier=data.get("cost_tier", ""),
            quality_tier=data.get("quality_tier", ""),
            quality_basis=data.get("quality_basis", ""),
            cost_detail=data.get("cost_detail", ""),
            quality_detail=data.get("quality_detail", ""),
            locality=data.get("locality", ""),
            decided_at=datetime.fromisoformat(data["decided_at"]),
            inputs_digest=data.get("inputs_digest", ""),
            requester=data.get("requester", ""),
            approval_state=data.get("approval_state", NOT_REQUIRED),
            approval_id=data.get("approval_id"),
            record=DecisionRecord.from_dict(raw_record) if raw_record else None,
            execution=(
                ExecutionRecord.from_dict(raw_execution) if raw_execution else None
            ),
        )


def entry_from_record(record: DecisionRecord, entry_id: int) -> DecisionEntry:
    """Read one record into the shape the rest of the system consumes.

    The winner's cost and quality are read off the *candidate* rather than
    re-derived from the current estate: the candidate is what the decision
    was actually made against, and re-reading a provider now would let a
    later change quietly rewrite what the founder was shown.
    """
    decision = record.decision
    winner = next(
        (c for c in decision.candidates if c.provider_id == decision.winner), None
    )
    profile = next(
        (p for p in record.providers if p.provider_id == decision.winner), None
    )
    benchmark = profile.benchmark if profile is not None else None
    cost = winner.cost if winner is not None else None
    quality = winner.quality if winner is not None else None

    return DecisionEntry(
        entry_id=entry_id,
        task_id=decision.task.task_id,
        capability=decision.task.capability,
        outcome=decision.outcome,
        provider_id=decision.winner,
        reason=decision.reason,
        policy_version=decision.policy_version,
        quality_floor=decision.quality_floor,
        cost=cost,
        quality=quality,
        cost_tier=cost_tier(cost),
        quality_tier=quality_tier(quality),
        quality_basis=quality_basis(benchmark),
        cost_detail=describe_cost(cost),
        quality_detail=describe_quality(quality, benchmark),
        locality=winner.locality if winner is not None else "",
        decided_at=decision.decided_at,
        inputs_digest=decision.inputs_digest,
        requester=decision.task.requester,
        record=record,
    )


class LedgerError(Exception):
    pass


class UnknownDecision(LedgerError):
    pass


class DecisionLedger:
    """Every decision the Broker made, oldest first.

    `store` is optional: a ledger with none decides and remembers
    identically and simply does not survive the process, which is the right
    behaviour for a test and the wrong one for a founder — so the launcher
    always gives it one.
    """

    def __init__(self, store: Any = None) -> None:
        self._entries: list[DecisionEntry] = []
        self._store = store
        self.write_failures: list[str] = []

    # ---- writing -------------------------------------------------------

    def record(self, record: DecisionRecord) -> DecisionEntry:
        """The Broker's sink. Appends, persists, and hands back the entry.

        Never raises on a storage failure: a broken disk is a recording
        problem, and turning it into a refused AI task would be the tail
        wagging the dog. Failures are collected so a caller can surface
        them (the same posture `CapabilityBroker._record` takes).
        """
        entry = entry_from_record(record, self._next_id())
        self._entries.append(entry)
        self._flush()
        return entry

    def set_approval(
        self, entry_id: int, state: str, approval_id: str | None = None
    ) -> DecisionEntry:
        """Annotate one decision with what the founder said.

        The `DecisionRecord` is carried over untouched — this changes what
        happened *to* a decision, never the decision itself.
        """
        if state not in APPROVAL_STATES:
            raise LedgerError(
                f"unknown approval state '{state}' (known: {', '.join(APPROVAL_STATES)})"
            )
        index = self._index_of(entry_id)
        current = self._entries[index]
        updated = replace(
            current,
            approval_state=state,
            approval_id=approval_id if approval_id is not None else current.approval_id,
        )
        self._entries[index] = updated
        self._flush()
        return updated

    def record_execution(self, entry_id: int, execution: ExecutionRecord) -> DecisionEntry:
        """Attach what happened when a decision was carried out (MB033
        Rule 3).

        Annotates rather than appends, for the reason `set_approval` does:
        the decision and its execution are two moments in the life of one
        task. The `DecisionRecord` underneath is carried over untouched, so
        a decision stays replayable no matter how its execution went — and
        an execution that failed is recorded just as carefully as one that
        worked, because a provider's failures are the more interesting half
        of what a future benchmark needs.
        """
        index = self._index_of(entry_id)
        updated = replace(self._entries[index], execution=execution)
        self._entries[index] = updated
        self._flush()
        return updated

    # ---- reading -------------------------------------------------------

    def executions(self) -> tuple[DecisionEntry, ...]:
        """Every decision that was actually carried out, oldest first."""
        return tuple(entry for entry in self._entries if entry.execution is not None)

    def last_execution(self) -> DecisionEntry | None:
        """The most recent decision that ran. What the founder page means
        by "thinking with"."""
        for entry in reversed(self._entries):
            if entry.execution is not None:
                return entry
        return None

    def entries(self) -> tuple[DecisionEntry, ...]:
        """Copies of the list, not the list. Evidence a caller can edit is
        not evidence."""
        return tuple(self._entries)

    def last(self) -> DecisionEntry | None:
        return self._entries[-1] if self._entries else None

    def get(self, entry_id: int) -> DecisionEntry:
        return self._entries[self._index_of(entry_id)]

    def for_task(self, task_id: str) -> DecisionEntry | None:
        """The most recent decision for this task. Most recent rather than
        first: a task re-asked after an approval is the same task, and the
        answer that matters is the latest one."""
        for entry in reversed(self._entries):
            if entry.task_id == task_id:
                return entry
        return None

    def all_for_task(self, task_id: str) -> tuple[DecisionEntry, ...]:
        return tuple(entry for entry in self._entries if entry.task_id == task_id)

    def entry_for_decision(self, decision: BrokerDecision) -> DecisionEntry | None:
        """The entry holding *this exact* decision object.

        Identity, not equality: two identical decisions are two decisions,
        and a caller reconciling what it just received with what the sink
        just wrote must not match the wrong one.
        """
        for entry in reversed(self._entries):
            if entry.record is not None and entry.record.decision is decision:
                return entry
        return None

    def recent(self, limit: int = 5) -> tuple[DecisionEntry, ...]:
        """Newest first — a founder reads the top of a list."""
        if limit <= 0:
            return ()
        return tuple(reversed(self._entries[-limit:]))

    def awaiting_approval(self) -> tuple[DecisionEntry, ...]:
        return tuple(e for e in self._entries if e.approval_state == PENDING)

    def __len__(self) -> int:
        return len(self._entries)

    # ---- replay (Deliverable 8) ----------------------------------------

    def replay(self, entry_id: int) -> BrokerDecision:
        """Re-derive a historical decision from its own stored record.

        Builds a throwaway engine on the record's policy, with a clock
        pinned to the original timestamp, and no sink — a replay is not a
        new decision and must not append to the ledger it is reading.
        """
        record = self._record_of(entry_id)
        engine = CapabilityBroker(
            policy=record.policy, clock=lambda: record.decision.decided_at
        )
        return engine.replay(record)

    def replay_matches(self, entry_id: int) -> bool:
        """Did the replay reproduce the stored answer, in full?

        Delegates to the Broker's own comparison, which checks outcome,
        winner, floor, digest **and** the whole ranking — two policies can
        agree on first place and disagree on everything after it.
        """
        from master_agent.broker.broker import replay_matches as broker_replay_matches

        return broker_replay_matches(self._record_of(entry_id))

    def replay_all(self) -> dict[int, bool]:
        """Every stored decision, re-derived. The evidence behind "replay
        is deterministic" being a property rather than a claim."""
        return {entry.entry_id: self.replay_matches(entry.entry_id) for entry in self._entries}

    # ---- replaying an execution (MB038 Step 12) --------------------------

    def replay_execution(self, entry_id: int) -> ExecutionReplay:
        """Reconstruct how one call went, from the record and nothing else.

        **It recomputes nothing.** MB038 D-9: replay reuses the recorded
        budget rather than re-deriving one. A re-derived budget would be a
        number that governed nothing — and it would drift, because the
        planning prompt grows with every Executive added, so last month's
        mission would replay under a budget it never had.

        No provider is contacted, no clock is read, and no current
        provider state is consulted. Reading an entry twice gives the same
        answer forever.
        """
        execution = self.get(entry_id).execution
        if execution is None:
            return ExecutionReplay(entry_id=entry_id, recorded=False)
        return ExecutionReplay(
            entry_id=entry_id,
            recorded=True,
            provider_id=execution.provider_id,
            outcome=execution.outcome,
            lifecycle=execution.lifecycle,
            admission=execution.admission,
            admission_reason=execution.admission_reason,
            budget=execution.budget,
            observation=execution.observation,
            timeout=execution.timeout,
        )

    def _record_of(self, entry_id: int) -> DecisionRecord:
        entry = self.get(entry_id)
        if entry.record is None:
            raise UnknownDecision(
                f"decision {entry_id} was stored without its record and cannot be replayed"
            )
        return entry.record

    # ---- durability ----------------------------------------------------

    def as_dicts(self) -> list[dict[str, Any]]:
        return [entry.as_dict() for entry in self._entries]

    def restore(self, rows: list[dict[str, Any]]) -> int:
        """Rebuild from plain data. A row that cannot be parsed is skipped
        rather than fatal — one bad entry must not cost the rest of the
        history, exactly as a truncated line does not cost the event log."""
        restored = 0
        for row in rows:
            try:
                entry = DecisionEntry.from_dict(row)
            except (KeyError, TypeError, ValueError):
                continue
            if any(existing.entry_id == entry.entry_id for existing in self._entries):
                continue
            self._entries.append(entry)
            restored += 1
        self._entries.sort(key=lambda entry: entry.entry_id)
        return restored

    def load(self) -> int:
        if self._store is None:
            return 0
        try:
            rows = self._store.read()
        except Exception as exc:  # noqa: BLE001 - unreadable history is no history
            self.write_failures.append(f"load: {exc}")
            return 0
        return self.restore(rows)

    def _flush(self) -> None:
        if self._store is None:
            return
        try:
            self._store.write(self.as_dicts())
        except Exception as exc:  # noqa: BLE001 - see `record`
            self.write_failures.append(str(exc))

    # ---- internals -----------------------------------------------------

    def _next_id(self) -> int:
        return (self._entries[-1].entry_id + 1) if self._entries else 1

    def _index_of(self, entry_id: int) -> int:
        for index, entry in enumerate(self._entries):
            if entry.entry_id == entry_id:
                return index
        raise UnknownDecision(f"unknown decision: {entry_id}")


class JsonFileDecisionStore:
    """One JSON document, rewritten atomically.

    Atomic for the reason `JsonFileStateStore` is: a crash mid-write leaves
    the previous good ledger rather than a truncated one. Rewritten whole
    rather than appended because an approval annotation edits an existing
    entry, and an append-only file would need two record types and a
    reducer to read one decision — complexity a founder-edition volume
    does not earn.

    **Named cost:** the file grows with every AI decision and is rewritten
    each time. That is the same unbounded-growth item already on the
    roadmap for the event log, and it should be solved once for both.
    """

    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def read(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return []
        return [row for row in raw if isinstance(row, dict)]

    def write(self, rows: list[dict[str, Any]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp_name = tempfile.mkstemp(dir=str(self._path.parent), suffix=".tmp")
        temp_path = Path(temp_name)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(rows, stream, indent=2, default=str)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, self._path)
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise


class InMemoryDecisionStore:
    """A store that never touches disk — for tests, and proof that nothing
    above this class assumes a filesystem."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def read(self) -> list[dict[str, Any]]:
        return list(self.rows)

    def write(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)
