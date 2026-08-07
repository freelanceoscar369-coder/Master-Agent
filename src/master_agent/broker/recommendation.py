"""Recommendation Engine (Mission Brief 031 Deliverable 8).

Recommends what would improve the AI ecosystem. Inert data — never
installs/downloads. ADR-0017 Decision 6: "Nothing in Kalpavriksha consumes a
recommendation to act. Deleting the entire engine would change what the
founder sees and nothing about what the system does."

Every recommendation must carry falsifiable evidence (decision IDs, sample
IDs, ledger references) or it is refused at generation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from master_agent.broker.benchmark import BenchmarkStore
from master_agent.broker.registry import ProviderRegistry
from master_agent.broker.profiles import ProviderProfile


class RecommendationType(str, Enum):
    """Types of recommendations the engine can make."""

    ADD_PROVIDER = "add_provider"
    UPGRADE_PROVIDER = "upgrade_provider"
    REMOVE_PROVIDER = "remove_provider"
    ADJUST_POLICY = "adjust_policy"
    ENABLE_CREDENTIALS = "enable_credentials"
    RUN_BENCHMARK = "run_benchmark"


class RecommendationPriority(str, Enum):
    """Priority of a recommendation."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class Recommendation:
    """One recommendation for improving the AI ecosystem.

    Must carry falsifiable evidence or it is refused at generation.
    """

    recommendation_id: str
    type: RecommendationType
    priority: RecommendationPriority

    # What it applies to
    provider_id: str | None = None
    ai_capability: str | None = None
    task_class: str | None = None

    # Human-readable
    title: str = ""
    rationale: str = ""

    # Falsifiable evidence (required)
    evidence: tuple[str, ...] = ()  # decision_ids, sample_ids, ledger_refs

    # What would change if accepted
    expected_impact: str = ""

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    policy_version: str = ""
    status: str = "pending"  # pending, accepted, rejected, superseded

    def as_dict(self) -> dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "type": self.type.value,
            "priority": self.priority.value,
            "provider_id": self.provider_id,
            "ai_capability": self.ai_capability,
            "task_class": self.task_class,
            "title": self.title,
            "rationale": self.rationale,
            "evidence": list(self.evidence),
            "expected_impact": self.expected_impact,
            "created_at": self.created_at.isoformat(),
            "policy_version": self.policy_version,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Recommendation:
        return cls(
            recommendation_id=data["recommendation_id"],
            type=RecommendationType(data["type"]),
            priority=RecommendationPriority(data["priority"]),
            provider_id=data.get("provider_id"),
            ai_capability=data.get("ai_capability"),
            task_class=data.get("task_class"),
            title=data.get("title", ""),
            rationale=data.get("rationale", ""),
            evidence=tuple(data.get("evidence", ())),
            expected_impact=data.get("expected_impact", ""),
            created_at=datetime.fromisoformat(data["created_at"]),
            policy_version=data.get("policy_version", ""),
            status=data.get("status", "pending"),
        )


class RecommendationEngine:
    """Analyzes the AI ecosystem and produces recommendations.

    Inert data — never installs, downloads, or acts. A recommendation the
    founder accepts becomes a Self-Development Queue item (ADR-0017 Decision 6).
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        benchmark_store: BenchmarkStore,
        sink: Any = None,
    ) -> None:
        self._registry = registry
        self._benchmark_store = benchmark_store
        self._sink = sink
        self._recommendations: list[Recommendation] = []
        self._audit_log: list[dict[str, Any]] = []

    def analyze(self, policy_version: str = "") -> tuple[Recommendation, ...]:
        """Run full analysis and return new recommendations."""
        new_recommendations: list[Recommendation] = []

        # 1. Check for capabilities with no providers
        new_recommendations.extend(self._check_missing_capabilities(policy_version))

        # 2. Check for capabilities with only low-quality providers
        new_recommendations.extend(self._check_low_quality(policy_version))

        # 3. Check for capabilities with only paid providers
        new_recommendations.extend(self._check_paid_only(policy_version))

        # 4. Check for unbenchmarked providers
        new_recommendations.extend(self._check_unbenchmarked(policy_version))

        # 5. Check for stale benchmarks
        new_recommendations.extend(self._check_stale_benchmarks(policy_version))

        # 6. Check for disabled cloud providers
        new_recommendations.extend(self._check_disabled_cloud(policy_version))

        # 7. Check for quality floor too high (no providers clear it)
        new_recommendations.extend(self._check_quality_floor(policy_version))

        # Filter out duplicates and store
        for rec in new_recommendations:
            if not self._is_duplicate(rec):
                self._recommendations.append(rec)
                self._audit("generated", rec)

        return tuple(new_recommendations)

    def _check_missing_capabilities(self, policy_version: str) -> list[Recommendation]:
        """Find AI capabilities with zero registered providers."""
        # Capabilities are defined by what providers register; don't import catalog
        # to avoid broker depending on ai_infrastructure.
        known_capabilities = {"reasoning", "reasoning.planning", "coding", "vision.ocr", "speech.transcribe", "embedding"}
        recs = []

        for cap in known_capabilities:
            providers = self._registry.by_capability(cap)
            if not providers:
                recs.append(Recommendation(
                    recommendation_id=f"add_provider_{cap}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}",
                    type=RecommendationType.ADD_PROVIDER,
                    priority=RecommendationPriority.HIGH,
                    ai_capability=cap,
                    title=f"No provider for {cap}",
                    rationale=f"Zero providers registered for AI capability '{cap}'. Broker will refuse all requests for this capability.",
                    evidence=(),
                    expected_impact=f"Enable {cap} requests to be served",
                    policy_version=policy_version,
                ))
        return recs

    def _check_low_quality(self, policy_version: str) -> list[Recommendation]:
        """Find capabilities where all providers are below a reasonable floor."""
        # Capabilities are defined by what providers register; don't import catalog
        # to avoid broker depending on ai_infrastructure.
        known_capabilities = {"reasoning", "reasoning.planning", "coding"}
        recs = []

        for cap in known_capabilities:
            providers = self._registry.by_capability(cap)
            if not providers:
                continue

            # Check if all available providers have low effective quality
            low_quality = []
            for p in providers:
                if p.effective_quality < 0.6:
                    low_quality.append(p)

            if low_quality and len(low_quality) == len(providers):
                # All providers for this capability are low quality
                best = max(low_quality, key=lambda p: p.effective_quality)
                recs.append(Recommendation(
                    recommendation_id=f"low_quality_{cap}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}",
                    type=RecommendationType.UPGRADE_PROVIDER,
                    priority=RecommendationPriority.MEDIUM,
                    provider_id=best.provider_id,
                    ai_capability=cap,
                    title=f"All {cap} providers below quality floor",
                    rationale=f"All {len(providers)} providers for {cap} have effective_quality < 0.6. Best is {best.provider_id} at {best.effective_quality:.2f}.",
                    evidence=(best.provider_id,),
                    expected_impact="Higher quality provider would clear the floor for more tasks",
                    policy_version=policy_version,
                ))
        return recs

    def _check_paid_only(self, policy_version: str) -> list[Recommendation]:
        """Find capabilities where only paid providers are available."""
        # Capabilities are defined by what providers register; don't import catalog
        # to avoid broker depending on ai_infrastructure.
        known_capabilities = {"reasoning", "reasoning.planning", "coding"}
        recs = []

        for cap in known_capabilities:
            providers = [p for p in self._registry.by_capability(cap) if not p.is_free]
            free_providers = [p for p in self._registry.by_capability(cap) if p.is_free]

            if providers and not free_providers:
                cheapest = min(providers, key=lambda p: p.cost)
                recs.append(Recommendation(
                    recommendation_id=f"paid_only_{cap}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}",
                    type=RecommendationType.ADD_PROVIDER,
                    priority=RecommendationPriority.MEDIUM,
                    ai_capability=cap,
                    title=f"Only paid providers for {cap}",
                    rationale=f"All {len(providers)} available providers for {cap} are paid. Cheapest is {cheapest.provider_id} at ${cheapest.cost:.4f}/call. No free alternative exists.",
                    evidence=(cheapest.provider_id,),
                    expected_impact="Free provider would allow cost-free execution",
                    policy_version=policy_version,
                ))
        return recs

    def _check_unbenchmarked(self, policy_version: str) -> list[Recommendation]:
        """Find providers with declared quality but no benchmarks."""
        recs = []

        for provider in self._registry.all():
            if provider.benchmark is None and provider.declared_quality > 0:
                recs.append(Recommendation(
                    recommendation_id=f"benchmark_{provider.provider_id}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}",
                    type=RecommendationType.RUN_BENCHMARK,
                    priority=RecommendationPriority.LOW,
                    provider_id=provider.provider_id,
                    title=f"Provider {provider.provider_id} unbenchmarked",
                    rationale=f"Provider declares quality {provider.declared_quality:.2f} but has no benchmark data. Declared quality is used for ranking but cannot be verified.",
                    evidence=(provider.provider_id,),
                    expected_impact="Measured quality replaces declared quality in ranking (ADR-0017 Decision 5)",
                    policy_version=policy_version,
                ))
        return recs

    def _check_stale_benchmarks(self, policy_version: str) -> list[Recommendation]:
        """Find benchmarks older than 30 days."""
        from datetime import timedelta

        recs = []
        cutoff = datetime.now(UTC) - timedelta(days=30)

        for agg in self._benchmark_store.all_aggregates():
            if agg.last_sample_at and agg.last_sample_at < cutoff:
                recs.append(Recommendation(
                    recommendation_id=f"stale_benchmark_{agg.provider_id}_{agg.ai_capability}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}",
                    type=RecommendationType.RUN_BENCHMARK,
                    priority=RecommendationPriority.LOW,
                    provider_id=agg.provider_id,
                    ai_capability=agg.ai_capability,
                    task_class=agg.task_class,
                    title=f"Stale benchmark for {agg.provider_id}/{agg.ai_capability}/{agg.task_class}",
                    rationale=f"Last benchmark sample was {agg.last_sample_at.isoformat()} ({agg.total_samples} samples). Provider behavior may have changed.",
                    evidence=(agg.provider_id,),
                    expected_impact="Fresh benchmarks improve decision accuracy",
                    policy_version=policy_version,
                ))
        return recs

    def _check_disabled_cloud(self, policy_version: str) -> list[Recommendation]:
        """Find cloud providers that are disabled due to missing credentials."""
        recs = []

        for provider in self._registry.all():
            if provider.provenance.value == "declared" and provider.requires_network:
                # Check if it's a cloud provider that needs credentials
                if provider.locality == "cloud" and provider.health.value == "unverified":
                    recs.append(Recommendation(
                        recommendation_id=f"enable_creds_{provider.provider_id}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}",
                        type=RecommendationType.ENABLE_CREDENTIALS,
                        priority=RecommendationPriority.LOW,
                        provider_id=provider.provider_id,
                        title=f"Cloud provider {provider.provider_id} not enabled",
                        rationale=f"Cloud provider {provider.provider_id} is declared but not enabled (no credentials). Would add {provider.capabilities} at cost ${provider.cost_per_call:.4f}/call.",
                        evidence=(provider.provider_id,),
                        expected_impact="Additional cloud provider available for selection",
                        policy_version=policy_version,
                    ))
        return recs

    def _check_quality_floor(self, policy_version: str) -> list[Recommendation]:
        """Check if the policy's hard floor makes all providers ineligible."""
        # This is a placeholder - would need policy context
        return []

    def _is_duplicate(self, rec: Recommendation) -> bool:
        """Check if an equivalent recommendation already exists (pending)."""
        for existing in self._recommendations:
            if (
                existing.type == rec.type
                and existing.provider_id == rec.provider_id
                and existing.ai_capability == rec.ai_capability
                and existing.task_class == rec.task_class
                and existing.status == "pending"
            ):
                return True
        return False

    def all(self) -> tuple[Recommendation, ...]:
        """All recommendations, newest first."""
        return tuple(sorted(self._recommendations, key=lambda r: r.created_at, reverse=True))

    def pending(self) -> tuple[Recommendation, ...]:
        """Pending recommendations only."""
        return tuple(r for r in self.all() if r.status == "pending")

    def update_status(self, recommendation_id: str, status: str) -> bool:
        """Update recommendation status."""
        for i, rec in enumerate(self._recommendations):
            if rec.recommendation_id == recommendation_id:
                updated = rec.__class__(
                    recommendation_id=rec.recommendation_id,
                    type=rec.type,
                    priority=rec.priority,
                    provider_id=rec.provider_id,
                    ai_capability=rec.ai_capability,
                    task_class=rec.task_class,
                    title=rec.title,
                    rationale=rec.rationale,
                    evidence=rec.evidence,
                    expected_impact=rec.expected_impact,
                    created_at=rec.created_at,
                    policy_version=rec.policy_version,
                    status=status,
                )
                self._recommendations[i] = updated
                self._audit("status_changed", updated, rec)
                return True
        return False

    def audit_log(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._audit_log)

    def _audit(self, event_type: str, rec: Recommendation, previous: Recommendation | None = None) -> None:
        event = {
            "event_type": event_type,
            "recommendation_id": rec.recommendation_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "recommendation": rec.as_dict(),
            "previous": previous.as_dict() if previous else None,
        }
        self._audit_log.append(event)
        if self._sink is not None:
            try:
                self._sink(event)
            except Exception:
                pass