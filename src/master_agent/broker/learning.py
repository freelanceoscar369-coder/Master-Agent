"""Verification Learning Loop (Mission Brief 031 Deliverable 9, ADR-0018).

Broker.record_outcome(decision_id, OutcomeReport) → BenchmarkSample aggregates by
(provider, ai_capability, task_class) → feeds next decision. Outcome successful
when Verification says so, not when the provider call returned.

ADR-0017 Decision 5: The sample feeds `observed` records the Verification Verdict
(ADR-0011), not an API status code. A model that returns a fluent, confident,
wrong answer scores as a failure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from master_agent.broker.benchmark import (
    BenchmarkSample,
    BenchmarkStore,
    VerificationVerdict,
)
from master_agent.broker.decision import BrokerDecision, DecisionRecord
from master_agent.broker.profiles import TaskProfile


@dataclass(frozen=True)
class OutcomeReport:
    """The outcome of an AI capability execution, as judged by Verification.

    This is NOT the provider's HTTP response — it is the Verification
    Subsystem's verdict on whether the actual outcome matched the expected
    outcome (ADR-0011).
    """

    decision_id: str
    task_id: str
    objective_id: str | None = None

    # Verification verdict
    verdict: VerificationVerdict = VerificationVerdict.INCONCLUSIVE

    # Observed metrics
    latency_ms: float | None = None
    tokens_per_second: float | None = None
    cost: float = 0.0

    # Quality signal
    expected_success: float | None = None  # What the Broker predicted
    confidence: float | None = None

    # Metadata
    verified_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    verifier: str = ""  # Which verifier produced this
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "task_id": self.task_id,
            "objective_id": self.objective_id,
            "verdict": self.verdict.value,
            "latency_ms": self.latency_ms,
            "tokens_per_second": self.tokens_per_second,
            "cost": self.cost,
            "expected_success": self.expected_success,
            "confidence": self.confidence,
            "verified_at": self.verified_at.isoformat(),
            "verifier": self.verifier,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutcomeReport:
        return cls(
            decision_id=data["decision_id"],
            task_id=data["task_id"],
            objective_id=data.get("objective_id"),
            verdict=VerificationVerdict(data["verdict"]),
            latency_ms=data.get("latency_ms"),
            tokens_per_second=data.get("tokens_per_second"),
            cost=data.get("cost", 0.0),
            expected_success=data.get("expected_success"),
            confidence=data.get("confidence"),
            verified_at=datetime.fromisoformat(data["verified_at"]),
            verifier=data.get("verifier", ""),
            notes=data.get("notes", ""),
        )


class VerificationLearningLoop:
    """Connects Broker decisions to Verification outcomes → Benchmark Store.

    This is the learning loop: every decision produces a record; when
    Verification completes, the outcome is recorded and feeds the Benchmark
    Store, which updates the provider's effective_quality for future decisions.

    ADR-0018: The Broker owns the data; the AI Infrastructure Executive
    analyses it and proposes policy changes. The decision procedure stays
    deterministic; only the versioned policy it reads evolves.
    """

    def __init__(
        self,
        benchmark_store: BenchmarkStore,
        ledger: Any = None,  # DecisionLedger
        sink: Any = None,
    ) -> None:
        self._benchmark_store = benchmark_store
        self._ledger = ledger
        self._sink = sink
        self._outcomes: list[OutcomeReport] = []
        self._audit_log: list[dict[str, Any]] = []

    def record_outcome(
        self,
        decision_id: str,
        outcome: OutcomeReport,
    ) -> BenchmarkSample:
        """Record a verification outcome and update benchmarks.

        This is the main entry point called by callers after Verification
        completes. It:
        1. Stores the outcome report
        2. Finds the original decision to extract provider/capability/task_class
        3. Creates a BenchmarkSample
        4. Records it in the BenchmarkStore (which updates aggregates)
        5. Updates the ledger entry if available
        """
        # Store outcome
        self._outcomes.append(outcome)

        # Find the decision record
        decision = None
        task = None
        provider_id = None

        if self._ledger is not None:
            # Find entry by decision_id (or task_id)
            entry = self._ledger.for_task(outcome.task_id)
            if entry and entry.record:
                decision = entry.record.decision
                task = decision.task
                provider_id = decision.winner

        if not provider_id:
            # Can't create benchmark sample without provider
            self._audit("outcome_recorded_no_provider", outcome)
            return None

        # Extract capability and task_class from task
        ai_capability = task.capability if task else "reasoning"
        task_class = self._infer_task_class(task, outcome)

        # Create benchmark sample
        sample = BenchmarkSample(
            provider_id=provider_id,
            ai_capability=ai_capability,
            task_class=task_class,
            verdict=outcome.verdict,
            latency_ms=outcome.latency_ms,
            tokens_per_second=outcome.tokens_per_second,
            cost=outcome.cost,
            decided_at=outcome.verified_at,
            decision_id=decision_id,
            notes=outcome.notes,
        )

        # Record in benchmark store (updates aggregates)
        aggregate = self._benchmark_store.record(sample)

        self._audit("outcome_recorded", outcome, sample, aggregate)
        return sample

    def _infer_task_class(self, task: TaskProfile | None, outcome: OutcomeReport) -> str:
        """Infer task class from task profile and outcome."""
        if task is None:
            return "general"

        # Use sensitivity and capability to infer class
        if task.sensitivity == "sensitive":
            return "sensitive"
        if task.offline:
            return "offline"
        if task.required_context_tokens and task.required_context_tokens > 8000:
            return "long_context"

        return "general"

    def outcome_for(self, decision_id: str) -> OutcomeReport | None:
        """Get outcome report for a decision."""
        for outcome in self._outcomes:
            if outcome.decision_id == decision_id:
                return outcome
        return None

    def all_outcomes(self) -> tuple[OutcomeReport, ...]:
        return tuple(self._outcomes)

    def audit_log(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._audit_log)

    def _audit(
        self,
        event_type: str,
        outcome: OutcomeReport,
        sample: BenchmarkSample | None = None,
        aggregate: Any = None,
    ) -> None:
        event = {
            "event_type": event_type,
            "decision_id": outcome.decision_id,
            "task_id": outcome.task_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "outcome": outcome.as_dict(),
            "sample": sample.as_dict() if sample else None,
            "aggregate": aggregate.as_dict() if aggregate else None,
        }
        self._audit_log.append(event)
        if self._sink is not None:
            try:
                self._sink(event)
            except Exception:
                pass


# Convenience function for callers
def record_outcome(
    loop: VerificationLearningLoop,
    decision: BrokerDecision,
    verdict: VerificationVerdict,
    latency_ms: float | None = None,
    tokens_per_second: float | None = None,
    cost: float = 0.0,
    verifier: str = "",
    notes: str = "",
) -> BenchmarkSample | None:
    """Record an outcome for a BrokerDecision.

    This is the simple interface for callers (ModelRouter, Workers, etc.)
    who have a decision and a verification verdict.
    """
    outcome = OutcomeReport(
        decision_id=decision.decision_id if hasattr(decision, 'decision_id') else decision.task.task_id,
        task_id=decision.task.task_id,
        objective_id=getattr(decision.task, 'objective_id', None),
        verdict=verdict,
        latency_ms=latency_ms,
        tokens_per_second=tokens_per_second,
        cost=cost,
        expected_success=decision.candidates[0].quality if decision.candidates else None,
        confidence=decision.candidates[0].quality if decision.candidates else None,
        verifier=verifier,
        notes=notes,
    )
    return loop.record_outcome(decision.task.task_id, outcome)