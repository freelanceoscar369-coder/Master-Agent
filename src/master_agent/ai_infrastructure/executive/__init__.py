"""AI Infrastructure Executive package.

The machine-touching Worker that discovers, probes, benchmarks, and inventories
AI providers. It produces facts; the Broker consumes them.
"""
from master_agent.ai_infrastructure.executive.models import (
    ProviderClass,
    DiscoverySource,
    ProviderIdentity,
    ProviderCapabilities,
    ProviderHealth,
    ProviderInventoryEntry,
    ProviderInventory,
    BenchmarkRequest,
    BenchmarkResult,
    BenchmarkStatus,
)
from master_agent.ai_infrastructure.executive.actions import (
    get_all_discovery_actions,
    DISCOVERY_ACTION_CLASSES,
)
from master_agent.ai_infrastructure.executive.probes import (
    get_all_probe_actions,
)
from master_agent.ai_infrastructure.executive.plugin import (
    AiInfrastructurePlugin,
    AI_INFRA_EXECUTIVE_ID,
    AI_INFRA_VERSION,
)

__all__ = [
    # Models
    "ProviderClass",
    "DiscoverySource",
    "ProviderIdentity",
    "ProviderCapabilities",
    "ProviderHealth",
    "ProviderInventoryEntry",
    "ProviderInventory",
    "BenchmarkRequest",
    "BenchmarkResult",
    "BenchmarkStatus",
    # Actions
    "get_all_discovery_actions",
    "DISCOVERY_ACTION_CLASSES",
    "get_all_probe_actions",
    # Plugin
    "AiInfrastructurePlugin",
    "AI_INFRA_EXECUTIVE_ID",
    "AI_INFRA_VERSION",
]