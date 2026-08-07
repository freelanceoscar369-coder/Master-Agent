"""Benchmark Store (Mission Brief 031 Deliverable 6).

Aggregates BenchmarkSample(provider_id, ai_capability, task_class, success_count,
total_count, latency_ms_p50/p95, tokens_per_second) by (provider, ai_capability,
task_class). Observed beats declared — Verification Verdict determines success.

ADR-0017 Decision 5: The sample feeds `observed` records the Verification Verdict
(ADR-0011), not an API status code. A model that returns a fluent, confident,
wrong answer scores as a failure.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import Enum
from statistics import median, quantiles
from typing import Any

from master_agent.broker.profiles import ProviderProfile


class VerificationVerdict(str, Enum):
    """Verification verdict per ADR-0011."""

    MATCHED = "matched"
    DID_NOT_MATCH = "did_not_match"
    PARTIALLY_MATCHED = "partially_matched"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class BenchmarkSample:
    """One observed outcome from a real execution + Verification.

    This is the atomic unit of learning. It is NOT the provider's HTTP status
    code — it is the Verification subsystem's verdict on whether the actual
    outcome matched the expected outcome.
    """

    provider_id: str
    ai_capability: str
    task_class: str
    verdict: VerificationVerdict
    latency_ms: float | None = None
    tokens_per_second: float | None = None
    cost: float = 0.0
    decided_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    decision_id: str = ""
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "ai_capability": self.ai_capability,
            "task_class": self.task_class,
            "verdict": self.verdict.value,
            "latency_ms": self.latency_ms,
            "tokens_per_second": self.tokens_per_second,
            "cost": self.cost,
            "decided_at": self.decided_at.isoformat(),
            "decision_id": self.decision_id,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BenchmarkSample:
        return cls(
            provider_id=data["provider_id"],
            ai_capability=data["ai_capability"],
            task_class=data["task_class"],
            verdict=VerificationVerdict(data["verdict"]),
            latency_ms=data.get("latency_ms"),
            tokens_per_second=data.get("tokens_per_second"),
            cost=data.get("cost", 0.0),
            decided_at=datetime.fromisoformat(data["decided_at"]),
            decision_id=data.get("decision_id", ""),
            notes=data.get("notes", ""),
        )

    @property
    def is_success(self) -> bool:
        """ADR-0017 Decision 5: success = Verification says MATCHED."""
        return self.verdict == VerificationVerdict.MATCHED

    @property
    def is_failure(self) -> bool:
        return self.verdict == VerificationVerdict.DID_NOT_MATCH

    @property
    def is_inconclusive(self) -> bool:
        return self.verdict == VerificationVerdict.INCONCLUSIVE


@dataclass(frozen=True)
class BenchmarkAggregate:
    """Aggregated benchmark for (provider, ai_capability, task_class).

    This is what the Broker reads for `effective_quality`. The aggregation
    is incremental — new samples update the aggregate without re-reading
    history.
    """

    provider_id: str
    ai_capability: str
    task_class: str

    # Core counts
    total_samples: int = 0
    success_count: int = 0
    failure_count: int = 0
    inconclusive_count: int = 0

    # Latency percentiles (updated incrementally via reservoir or stored samples)
    latency_ms_p50: float | None = None
    latency_ms_p95: float | None = None

    # Throughput
    tokens_per_second_mean: float | None = None

    # Cost
    cost_per_call_mean: float = 0.0

    # Quality (success rate)
    quality: float = 0.0
    confidence: float = 0.0

    # Metadata
    first_sample_at: datetime | None = None
    last_sample_at: datetime | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def sample_count(self) -> int:
        return self.total_samples

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "ai_capability": self.ai_capability,
            "task_class": self.task_class,
            "total_samples": self.total_samples,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "inconclusive_count": self.inconclusive_count,
            "latency_ms_p50": self.latency_ms_p50,
            "latency_ms_p95": self.latency_ms_p95,
            "tokens_per_second_mean": self.tokens_per_second_mean,
            "cost_per_call_mean": self.cost_per_call_mean,
            "quality": self.quality,
            "confidence": self.confidence,
            "first_sample_at": self.first_sample_at.isoformat() if self.first_sample_at else None,
            "last_sample_at": self.last_sample_at.isoformat() if self.last_sample_at else None,
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BenchmarkAggregate:
        return cls(
            provider_id=data["provider_id"],
            ai_capability=data["ai_capability"],
            task_class=data["task_class"],
            total_samples=data["total_samples"],
            success_count=data["success_count"],
            failure_count=data["failure_count"],
            inconclusive_count=data["inconclusive_count"],
            latency_ms_p50=data.get("latency_ms_p50"),
            latency_ms_p95=data.get("latency_ms_p95"),
            tokens_per_second_mean=data.get("tokens_per_second_mean"),
            cost_per_call_mean=data.get("cost_per_call_mean", 0.0),
            quality=data["quality"],
            confidence=data["confidence"],
            first_sample_at=datetime.fromisoformat(data["first_sample_at"]) if data.get("first_sample_at") else None,
            last_sample_at=datetime.fromisoformat(data["last_sample_at"]) if data.get("last_sample_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


class BenchmarkStore:
    """The Benchmark Store — aggregates by (provider, ai_capability, task_class).

    Stores raw samples (for audit/replay) and maintains incrementally-updated
    aggregates for the Broker's decision engine.

    ADR-0018: The Broker owns the data; the AI Infrastructure Executive
    analyses it and proposes policy changes.
    """

    def __init__(self, sink: Any = None, max_samples_per_key: int = 1000) -> None:
        self._samples: dict[tuple[str, str, str], list[BenchmarkSample]] = {}
        self._aggregates: dict[tuple[str, str, str], BenchmarkAggregate] = {}
        self._sink = sink
        self._max_samples_per_key = max_samples_per_key
        self._audit_log: list[dict[str, Any]] = []

    def record(self, sample: BenchmarkSample) -> BenchmarkAggregate:
        """Record a benchmark sample, update the aggregate, return new aggregate."""
        key = (sample.provider_id, sample.ai_capability, sample.task_class)

        # Store sample (with bounded retention)
        if key not in self._samples:
            self._samples[key] = []
        self._samples[key].append(sample)
        if len(self._samples[key]) > self._max_samples_per_key:
            # Keep most recent
            self._samples[key] = self._samples[key][-self._max_samples_per_key :]

        # Update aggregate incrementally
        aggregate = self._aggregates.get(key)
        new_aggregate = self._update_aggregate(aggregate, sample)
        self._aggregates[key] = new_aggregate

        self._audit("recorded", sample, new_aggregate)
        return new_aggregate

    def _update_aggregate(
        self,
        existing: BenchmarkAggregate | None,
        sample: BenchmarkSample,
    ) -> BenchmarkAggregate:
        if existing is None:
            # First sample for this key
            return BenchmarkAggregate(
                provider_id=sample.provider_id,
                ai_capability=sample.ai_capability,
                task_class=sample.task_class,
                total_samples=1,
                success_count=1 if sample.is_success else 0,
                failure_count=1 if sample.is_failure else 0,
                inconclusive_count=1 if sample.is_inconclusive else 0,
                latency_ms_p50=sample.latency_ms,
                latency_ms_p95=sample.latency_ms,
                tokens_per_second_mean=sample.tokens_per_second,
                cost_per_call_mean=sample.cost,
                quality=1.0 if sample.is_success else 0.0,
                confidence=0.1,  # Low confidence with 1 sample
                first_sample_at=sample.decided_at,
                last_sample_at=sample.decided_at,
                updated_at=datetime.now(UTC),
            )

        # Incremental update
        total = existing.total_samples + 1
        success = existing.success_count + (1 if sample.is_success else 0)
        failure = existing.failure_count + (1 if sample.is_failure else 0)
        inconclusive = existing.inconclusive_count + (1 if sample.is_inconclusive else 0)

        # Recompute percentiles from stored samples (simple approach)
        sample_key = (sample.provider_id, sample.ai_capability, sample.task_class)
        latencies = [s.latency_ms for s in self._samples[sample_key] if s.latency_ms is not None]
        tps_values = [s.tokens_per_second for s in self._samples[sample_key] if s.tokens_per_second is not None]
        costs = [s.cost for s in self._samples[sample_key]]

        latency_p50 = median(latencies) if latencies else None
        latency_p95 = quantiles(latencies, n=20)[18] if len(latencies) >= 20 else (max(latencies) if latencies else None)
        tps_mean = sum(tps_values) / len(tps_values) if tps_values else None
        cost_mean = sum(costs) / len(costs) if costs else 0.0

        quality = success / total if total > 0 else 0.0

        # Confidence grows with sample count (Wilson score interval lower bound approximation)
        # Simplified: confidence = min(1.0, total / 30) * quality
        confidence = min(1.0, total / 30.0) * quality

        return BenchmarkAggregate(
            provider_id=existing.provider_id,
            ai_capability=existing.ai_capability,
            task_class=existing.task_class,
            total_samples=total,
            success_count=success,
            failure_count=failure,
            inconclusive_count=inconclusive,
            latency_ms_p50=latency_p50,
            latency_ms_p95=latency_p95,
            tokens_per_second_mean=tps_mean,
            cost_per_call_mean=cost_mean,
            quality=quality,
            confidence=confidence,
            first_sample_at=existing.first_sample_at,
            last_sample_at=sample.decided_at,
            updated_at=datetime.now(UTC),
        )

    def get_aggregate(
        self, provider_id: str, ai_capability: str, task_class: str
    ) -> BenchmarkAggregate | None:
        """Get the aggregate for a provider/capability/task_class."""
        return self._aggregates.get((provider_id, ai_capability, task_class))

    def get_effective_quality(
        self, provider_id: str, ai_capability: str, task_class: str
    ) -> tuple[float, float]:
        """Get (quality, confidence) for a provider/capability/task_class.

        Returns (0.0, 0.0) if no benchmark data exists.
        """
        aggregate = self.get_aggregate(provider_id, ai_capability, task_class)
        if aggregate is None:
            return 0.0, 0.0
        return aggregate.quality, aggregate.confidence

    def all_aggregates(self) -> tuple[BenchmarkAggregate, ...]:
        """All aggregates, sorted for determinism."""
        return tuple(
            sorted(self._aggregates.values(), key=lambda a: (a.provider_id, a.ai_capability, a.task_class))
        )

    def samples_for(
        self, provider_id: str, ai_capability: str, task_class: str
    ) -> tuple[BenchmarkSample, ...]:
        """Raw samples for a key (for audit/replay)."""
        key = (provider_id, ai_capability, task_class)
        return tuple(self._samples.get(key, []))

    def audit_log(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._audit_log)

    def _audit(self, event_type: str, sample: BenchmarkSample, aggregate: BenchmarkAggregate) -> None:
        event = {
            "event_type": event_type,
            "provider_id": sample.provider_id,
            "ai_capability": sample.ai_capability,
            "task_class": sample.task_class,
            "verdict": sample.verdict.value,
            "timestamp": datetime.now(UTC).isoformat(),
            "sample": sample.as_dict(),
            "aggregate": aggregate.as_dict(),
        }
        self._audit_log.append(event)
        if self._sink is not None:
            try:
                self._sink(event)
            except Exception:
                pass