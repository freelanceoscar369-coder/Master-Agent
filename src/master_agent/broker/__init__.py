"""The AI Capability Broker (Mission Brief 031).

A Shared Infrastructure kernel service (Constitution Amendment 2 §5.7)
that answers one question: given these provider profiles and this task,
which provider should be used?

It decides. It never executes -- no model calls, no launching, no
downloads, no installation, no discovery. Those belong to the AI
Infrastructure Executive and the Operator.
"""
from master_agent.broker.broker import CapabilityBroker, replay_matches
from master_agent.broker.decision import (
    NO_PROVIDER_AVAILABLE,
    SELECTED,
    BrokerDecision,
    Candidate,
    DecisionRecord,
)
from master_agent.broker.policy import (
    BALANCED,
    BEST_QUALITY,
    CLOUD_ALLOWED,
    DEFAULT_POLICY,
    LOWEST_COST,
    OFFLINE_ONLY,
    POLICIES,
    PREFER_FREE,
    PREFER_LOCAL,
    PRIVACY_FIRST,
    SelectionPolicy,
    get_policy,
)
from master_agent.broker.profiles import ProviderProfile, TaskProfile
from master_agent.broker.registry import (
    ProviderRegistry,
    ProviderDescriptor,
    ProviderHealth,
    RegistrationProvenance,
)
from master_agent.broker.benchmark import (
    BenchmarkStore,
    BenchmarkSample,
    BenchmarkAggregate,
    VerificationVerdict,
)
from master_agent.broker.recommendation import (
    RecommendationEngine,
    Recommendation,
    RecommendationType,
    RecommendationPriority,
)
from master_agent.broker.learning import (
    VerificationLearningLoop,
    OutcomeReport,
    record_outcome,
)
from master_agent.broker.cost import (
    CostModel,
    CostModelConfig,
    BudgetCap,
    SpendEntry,
    BudgetStatus,
    BudgetPeriod,
)

__all__ = [
    "BALANCED",
    "BEST_QUALITY",
    "CLOUD_ALLOWED",
    "DEFAULT_POLICY",
    "LOWEST_COST",
    "NO_PROVIDER_AVAILABLE",
    "OFFLINE_ONLY",
    "POLICIES",
    "PREFER_FREE",
    "PREFER_LOCAL",
    "PRIVACY_FIRST",
    "SELECTED",
    "BrokerDecision",
    "Candidate",
    "CapabilityBroker",
    "DecisionRecord",
    "ProviderProfile",
    "SelectionPolicy",
    "TaskProfile",
    "get_policy",
    "replay_matches",
    # New components
    "ProviderRegistry",
    "ProviderDescriptor",
    "ProviderHealth",
    "RegistrationProvenance",
    "BenchmarkStore",
    "BenchmarkSample",
    "BenchmarkAggregate",
    "VerificationVerdict",
    "RecommendationEngine",
    "Recommendation",
    "RecommendationType",
    "RecommendationPriority",
    "VerificationLearningLoop",
    "OutcomeReport",
    "record_outcome",
    "CostModel",
    "CostModelConfig",
    "BudgetCap",
    "SpendEntry",
    "BudgetStatus",
    "BudgetPeriod",
]
