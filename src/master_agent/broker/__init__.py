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
]
