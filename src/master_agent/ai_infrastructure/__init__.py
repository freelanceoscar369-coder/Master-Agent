"""AI infrastructure — the seam between the machine, the Broker, and the
founder (Mission Brief 032).

MB031 shipped the AI Capability Broker as a kernel service that depends on
nothing: it is handed provider profiles and a task, and it hands back a
`DecisionRecord`. That independence is the property worth protecting
(ADR-0017), and it is exactly why something else has to do the supplying
and the consuming. This package is that something.

```
    Desktop Executive inventory ─┐
    founder configuration ───────┤
                                 ├─> ProviderSource ─> profiles ─┐
                                                                 v
                              ModelRouter ─ request ───────> CapabilityBroker
                                                                 │
                                    DecisionLedger <── record ───┤
                                                                 v
                              Approval Queue <── paid? ── ProviderApprovalGate
                                                                 │
                                                            Selection
```

**What this package is not.** It is not the AI Infrastructure Executive
(ADR-0018 Decision 2). It performs no discovery, no probing, no
benchmarking, and no installation — it *reads* the scan the Desktop
Executive already published, the way the Dashboard does. Environment
access still has exactly one door (Constitution Rule 4).

**And it holds no ranking.** ADR-0018's Consequences name a ranking
function growing outside the Broker as the single failure mode that would
invalidate the whole design. Nothing here sorts providers, scores them, or
prefers one over another; it supplies facts and records answers.
`tests/test_broker_integration.py` asserts that mechanically rather than
trusting this paragraph.
"""
from master_agent.ai_infrastructure.approval import (
    PAID,
    SENSITIVE_THIRD_PARTY,
    ProviderApprovalGate,
    approval_needed,
)
from master_agent.ai_infrastructure.cache import (
    HIT,
    MISS,
    NOT_CONSULTED,
    CachedResponse,
    CacheLookup,
    ExactPromptCache,
    NullPromptCache,
    PromptCache,
    cache_key,
)
from master_agent.ai_infrastructure.catalog import (
    PROVIDER_CATALOG,
    REASONING,
    ProviderSpec,
)
from master_agent.ai_infrastructure.economy import TokenEconomy, summarise
from master_agent.ai_infrastructure.execution import PromptExecutor, PromptOutcome
from master_agent.ai_infrastructure.ledger import (
    CACHE_HIT,
    DENIED,
    GRANTED,
    LEDGER_FILENAME,
    NOT_REQUIRED,
    PENDING,
    DecisionEntry,
    DecisionLedger,
    ExecutionRecord,
    InMemoryDecisionStore,
    JsonFileDecisionStore,
)
from master_agent.ai_infrastructure.profiles import ProviderSource, profile_for
from master_agent.ai_infrastructure.refusal import (
    APPROVAL_DENIED,
    APPROVAL_PENDING,
    NO_PROVIDER,
    BrokerRefusal,
    BrokerRefused,
    NoProviderAvailable,
    ProviderApprovalDenied,
    ProviderApprovalPending,
)
from master_agent.ai_infrastructure.service import (
    AiCapabilityService,
    BrokerReport,
    Selection,
    SelectionOutcome,
)
from master_agent.ai_infrastructure.tiers import cost_tier, quality_tier
from master_agent.ai_infrastructure.executive import (
    AiInfrastructurePlugin,
    AI_INFRA_EXECUTIVE_ID,
    AI_INFRA_VERSION,
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
    get_all_discovery_actions,
    get_all_probe_actions,
)

__all__ = [
    "APPROVAL_DENIED",
    "APPROVAL_PENDING",
    "CACHE_HIT",
    "DENIED",
    "GRANTED",
    "HIT",
    "LEDGER_FILENAME",
    "MISS",
    "NOT_CONSULTED",
    "NOT_REQUIRED",
    "NO_PROVIDER",
    "PAID",
    "PENDING",
    "PROVIDER_CATALOG",
    "REASONING",
    "SENSITIVE_THIRD_PARTY",
    "AiCapabilityService",
    "BrokerRefusal",
    "BrokerRefused",
    "BrokerReport",
    "CacheLookup",
    "CachedResponse",
    "DecisionEntry",
    "DecisionLedger",
    "ExactPromptCache",
    "ExecutionRecord",
    "InMemoryDecisionStore",
    "JsonFileDecisionStore",
    "NoProviderAvailable",
    "NullPromptCache",
    "PromptCache",
    "PromptExecutor",
    "PromptOutcome",
    "ProviderApprovalDenied",
    "ProviderApprovalGate",
    "ProviderApprovalPending",
    "ProviderSource",
    "ProviderSpec",
    "Selection",
    "SelectionOutcome",
    "TokenEconomy",
    "approval_needed",
    "cache_key",
    "cost_tier",
    "profile_for",
    "quality_tier",
    "summarise",
    # Executive
    "AiInfrastructurePlugin",
    "AI_INFRA_EXECUTIVE_ID",
    "AI_INFRA_VERSION",
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
    "get_all_discovery_actions",
    "get_all_probe_actions",
]
