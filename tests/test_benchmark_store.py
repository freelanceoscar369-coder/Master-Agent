"""Tests for the Benchmark Store (Mission Brief 031 Deliverable 6)."""
from __future__ import annotations

import pytest
from datetime import UTC, datetime

from master_agent.broker.benchmark import (
    BenchmarkStore,
    BenchmarkSample,
    BenchmarkAggregate,
    VerificationVerdict,
)


class TestVerificationVerdict:
    """Test the VerificationVerdict enum."""

    def test_verdict_values(self):
        assert VerificationVerdict.MATCHED.value == "matched"
        assert VerificationVerdict.DID_NOT_MATCH.value == "did_not_match"
        assert VerificationVerdict.PARTIALLY_MATCHED.value == "partially_matched"
        assert VerificationVerdict.INCONCLUSIVE.value == "inconclusive"


class TestBenchmarkSample:
    """Test the BenchmarkSample dataclass."""

    def test_sample_creation(self):
        """Test creating a benchmark sample."""
        sample = BenchmarkSample(
            provider_id="test-provider",
            ai_capability="reasoning",
            task_class="general",
            verdict=VerificationVerdict.MATCHED,
            latency_ms=100.0,
            tokens_per_second=50.0,
            cost=0.0,
            decision_id="dec-123",
        )
        assert sample.provider_id == "test-provider"
        assert sample.ai_capability == "reasoning"
        assert sample.task_class == "general"
        assert sample.verdict == VerificationVerdict.MATCHED

    def test_sample_is_success(self):
        """Test is_success property."""
        matched = BenchmarkSample(
            provider_id="p1", ai_capability="reasoning", task_class="general",
            verdict=VerificationVerdict.MATCHED,
        )
        partial = BenchmarkSample(
            provider_id="p1", ai_capability="reasoning", task_class="general",
            verdict=VerificationVerdict.PARTIALLY_MATCHED,
        )
        failed = BenchmarkSample(
            provider_id="p1", ai_capability="reasoning", task_class="general",
            verdict=VerificationVerdict.DID_NOT_MATCH,
        )
        inconclusive = BenchmarkSample(
            provider_id="p1", ai_capability="reasoning", task_class="general",
            verdict=VerificationVerdict.INCONCLUSIVE,
        )

        assert matched.is_success is True
        assert matched.is_failure is False
        assert matched.is_inconclusive is False

        assert partial.is_success is False
        assert partial.is_failure is False
        assert partial.is_inconclusive is False

        assert failed.is_success is False
        assert failed.is_failure is True
        assert failed.is_inconclusive is False

        assert inconclusive.is_success is False
        assert inconclusive.is_failure is False
        assert inconclusive.is_inconclusive is True

    def test_sample_serialization(self):
        """Test round-trip serialization."""
        sample = BenchmarkSample(
            provider_id="test-provider",
            ai_capability="reasoning",
            task_class="general",
            verdict=VerificationVerdict.MATCHED,
            latency_ms=100.0,
            tokens_per_second=50.0,
            cost=0.0,
            decided_at=datetime(2026, 1, 1, tzinfo=UTC),
            decision_id="dec-123",
        )
        data = sample.as_dict()
        restored = BenchmarkSample.from_dict(data)
        assert restored.provider_id == sample.provider_id
        assert restored.verdict == sample.verdict
        assert restored.decided_at == sample.decided_at
        assert restored.decision_id == sample.decision_id


class TestBenchmarkAggregate:
    """Test the BenchmarkAggregate dataclass."""

    def test_aggregate_creation(self):
        """Test creating a benchmark aggregate."""
        agg = BenchmarkAggregate(
            provider_id="test-provider",
            ai_capability="reasoning",
            task_class="general",
            total_samples=10,
            success_count=8,
            failure_count=1,
            inconclusive_count=1,
            quality=0.8,
            confidence=0.7,
        )
        assert agg.provider_id == "test-provider"
        assert agg.sample_count == 10

    def test_aggregate_serialization(self):
        """Test round-trip serialization."""
        agg = BenchmarkAggregate(
            provider_id="test-provider",
            ai_capability="reasoning",
            task_class="general",
            total_samples=10,
            success_count=8,
            failure_count=1,
            inconclusive_count=1,
            latency_ms_p50=100.0,
            latency_ms_p95=200.0,
            tokens_per_second_mean=50.0,
            cost_per_call_mean=0.0,
            quality=0.8,
            confidence=0.7,
            first_sample_at=datetime(2026, 1, 1, tzinfo=UTC),
            last_sample_at=datetime(2026, 1, 2, tzinfo=UTC),
            updated_at=datetime(2026, 1, 2, tzinfo=UTC),
        )
        data = agg.as_dict()
        restored = BenchmarkAggregate.from_dict(data)
        assert restored.provider_id == agg.provider_id
        assert restored.total_samples == agg.total_samples
        assert restored.quality == agg.quality
        assert restored.confidence == agg.confidence


class TestBenchmarkStore:
    """Test the BenchmarkStore."""

    def test_record_first_sample(self):
        """Test recording the first sample for a key."""
        store = BenchmarkStore()
        sample = BenchmarkSample(
            provider_id="test-provider",
            ai_capability="reasoning",
            task_class="general",
            verdict=VerificationVerdict.MATCHED,
            latency_ms=100.0,
            tokens_per_second=50.0,
            cost=0.0,
        )
        aggregate = store.record(sample)

        assert aggregate.provider_id == "test-provider"
        assert aggregate.ai_capability == "reasoning"
        assert aggregate.task_class == "general"
        assert aggregate.total_samples == 1
        assert aggregate.success_count == 1
        assert aggregate.failure_count == 0
        assert aggregate.inconclusive_count == 0
        assert aggregate.quality == 1.0
        assert aggregate.confidence == 0.1  # Low confidence with 1 sample

    def test_record_multiple_samples(self):
        """Test recording multiple samples updates aggregate."""
        store = BenchmarkStore()
        # Success
        store.record(BenchmarkSample(
            provider_id="p1", ai_capability="reasoning", task_class="general",
            verdict=VerificationVerdict.MATCHED, latency_ms=100.0, tokens_per_second=50.0,
        ))
        # Success
        store.record(BenchmarkSample(
            provider_id="p1", ai_capability="reasoning", task_class="general",
            verdict=VerificationVerdict.MATCHED, latency_ms=120.0, tokens_per_second=45.0,
        ))
        # Failure
        store.record(BenchmarkSample(
            provider_id="p1", ai_capability="reasoning", task_class="general",
            verdict=VerificationVerdict.DID_NOT_MATCH, latency_ms=200.0, tokens_per_second=30.0,
        ))

        agg = store.get_aggregate("p1", "reasoning", "general")
        assert agg.total_samples == 3
        assert agg.success_count == 2
        assert agg.failure_count == 1
        assert agg.inconclusive_count == 0
        assert agg.quality == 2/3

    def test_get_effective_quality(self):
        """Test getting effective quality and confidence."""
        store = BenchmarkStore()
        store.record(BenchmarkSample(
            provider_id="p1", ai_capability="reasoning", task_class="general",
            verdict=VerificationVerdict.MATCHED,
        ))
        store.record(BenchmarkSample(
            provider_id="p1", ai_capability="reasoning", task_class="general",
            verdict=VerificationVerdict.MATCHED,
        ))
        store.record(BenchmarkSample(
            provider_id="p1", ai_capability="reasoning", task_class="general",
            verdict=VerificationVerdict.DID_NOT_MATCH,
        ))

        quality, confidence = store.get_effective_quality("p1", "reasoning", "general")
        assert quality == 2/3
        assert confidence > 0

    def test_get_effective_quality_no_data(self):
        """Test getting quality for non-existent data returns zeros."""
        store = BenchmarkStore()
        quality, confidence = store.get_effective_quality("nonexistent", "reasoning", "general")
        assert quality == 0.0
        assert confidence == 0.0

    def test_separate_keys_independent(self):
        """Test different (provider, capability, task_class) keys are independent."""
        store = BenchmarkStore()
        store.record(BenchmarkSample(
            provider_id="p1", ai_capability="reasoning", task_class="general",
            verdict=VerificationVerdict.MATCHED,
        ))
        store.record(BenchmarkSample(
            provider_id="p1", ai_capability="coding", task_class="general",
            verdict=VerificationVerdict.DID_NOT_MATCH,
        ))
        store.record(BenchmarkSample(
            provider_id="p2", ai_capability="reasoning", task_class="general",
            verdict=VerificationVerdict.MATCHED,
        ))

        # Each key has its own aggregate
        r1 = store.get_aggregate("p1", "reasoning", "general")
        c1 = store.get_aggregate("p1", "coding", "general")
        r2 = store.get_aggregate("p2", "reasoning", "general")

        assert r1.quality == 1.0
        assert c1.quality == 0.0
        assert r2.quality == 1.0

    def test_all_aggregates_sorted(self):
        """Test all_aggregates returns sorted results."""
        store = BenchmarkStore()
        store.record(BenchmarkSample(
            provider_id="zebra", ai_capability="reasoning", task_class="general",
            verdict=VerificationVerdict.MATCHED,
        ))
        store.record(BenchmarkSample(
            provider_id="alpha", ai_capability="reasoning", task_class="general",
            verdict=VerificationVerdict.MATCHED,
        ))
        store.record(BenchmarkSample(
            provider_id="beta", ai_capability="coding", task_class="general",
            verdict=VerificationVerdict.MATCHED,
        ))

        all_aggs = store.all_aggregates()
        keys = [(a.provider_id, a.ai_capability, a.task_class) for a in all_aggs]
        assert keys == [
            ("alpha", "reasoning", "general"),
            ("beta", "coding", "general"),
            ("zebra", "reasoning", "general"),
        ]

    def test_samples_for_key(self):
        """Test retrieving raw samples for a key."""
        store = BenchmarkStore()
        sample1 = BenchmarkSample(
            provider_id="p1", ai_capability="reasoning", task_class="general",
            verdict=VerificationVerdict.MATCHED, decision_id="dec1",
        )
        sample2 = BenchmarkSample(
            provider_id="p1", ai_capability="reasoning", task_class="general",
            verdict=VerificationVerdict.DID_NOT_MATCH, decision_id="dec2",
        )
        store.record(sample1)
        store.record(sample2)

        samples = store.samples_for("p1", "reasoning", "general")
        assert len(samples) == 2
        assert samples[0].decision_id == "dec1"
        assert samples[1].decision_id == "dec2"

    def test_sample_retention_limit(self):
        """Test that sample retention is bounded."""
        store = BenchmarkStore(max_samples_per_key=3)
        for i in range(5):
            store.record(BenchmarkSample(
                provider_id="p1", ai_capability="reasoning", task_class="general",
                verdict=VerificationVerdict.MATCHED, decision_id=f"dec{i}",
            ))

        samples = store.samples_for("p1", "reasoning", "general")
        assert len(samples) == 3
        # Should keep most recent
        assert samples[0].decision_id == "dec2"
        assert samples[2].decision_id == "dec4"

    def test_audit_log(self):
        """Test audit log records events."""
        events = []
        store = BenchmarkStore(sink=lambda e: events.append(e))
        store.record(BenchmarkSample(
            provider_id="p1", ai_capability="reasoning", task_class="general",
            verdict=VerificationVerdict.MATCHED,
        ))
        assert len(events) == 1
        assert events[0]["event_type"] == "recorded"
        assert events[0]["verdict"] == "matched"

    def test_latency_percentiles(self):
        """Test latency percentiles are computed."""
        store = BenchmarkStore()
        latencies = [100, 120, 130, 140, 150, 160, 170, 180, 190, 200,
                     210, 220, 230, 240, 250, 260, 270, 280, 290, 300]
        for lat in latencies:
            store.record(BenchmarkSample(
                provider_id="p1", ai_capability="reasoning", task_class="general",
                verdict=VerificationVerdict.MATCHED, latency_ms=float(lat),
            ))

        agg = store.get_aggregate("p1", "reasoning", "general")
        assert agg.latency_ms_p50 is not None
        assert agg.latency_ms_p95 is not None
        # P50 (median) should be around 155 for this range (statistics.median uses average of middle two for even n)
        # With 20 values sorted: median is average of 10th and 11th = (200+210)/2 = 205
        assert agg.latency_ms_p50 == 205.0
        # P95 - quantiles with n=20, index 18 = 95th percentile
        # For 20 values, quantiles with n=20 gives 19 cut points, index 18 is the 95th percentile
        assert 290 <= agg.latency_ms_p95 <= 300