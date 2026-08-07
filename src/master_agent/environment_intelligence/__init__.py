"""Environment Intelligence — what the environment *means*.

The Desktop Executive's scanner answers *"what exists?"*. This package
answers *"what does this environment mean?"*, and it does so by consuming
the scanner's `MachineInventory` and adding nothing to it.

**Enrichment only.** No probe, no subprocess, no filesystem, no second
catalog, no second inventory. Every conclusion carries its confidence, its
reason and the evidence it rests on, and anything the evidence cannot
support is returned as `UNKNOWN` rather than guessed.

Placed beside `environment/` rather than inside it: that package is
stateful session management (its own docstring says so), and this is a
pure derivation over a value someone else captured.
"""
from __future__ import annotations

from master_agent.environment_intelligence.derive import (
    UNCATALOGUED,
    WEB_AI_SERVICES,
    derive_ai,
    derive_browsers,
    derive_graph,
    derive_intelligence,
    derive_preferences,
    derive_profile,
    derive_summary,
)
from master_agent.environment_intelligence.evidence import (
    Availability,
    Confidence,
    Evidence,
    Inference,
    InvalidEvidence,
    unknown,
)
from master_agent.environment_intelligence.models import (
    SECTIONS,
    AIToolProfile,
    BrowserProfile,
    CapabilityEdge,
    CapabilityGraph,
    CapabilityNode,
    EnvironmentIntelligence,
    EnvironmentSummary,
    PreferenceModel,
    ProfileKind,
    ToolObservation,
    ToolState,
    UserProfile,
    WebAIAccess,
)

__all__ = [
    "SECTIONS",
    "UNCATALOGUED",
    "WEB_AI_SERVICES",
    "AIToolProfile",
    "Availability",
    "BrowserProfile",
    "CapabilityEdge",
    "CapabilityGraph",
    "CapabilityNode",
    "Confidence",
    "EnvironmentIntelligence",
    "EnvironmentSummary",
    "Evidence",
    "Inference",
    "InvalidEvidence",
    "PreferenceModel",
    "ProfileKind",
    "ToolObservation",
    "ToolState",
    "UserProfile",
    "WebAIAccess",
    "derive_ai",
    "derive_browsers",
    "derive_graph",
    "derive_intelligence",
    "derive_preferences",
    "derive_profile",
    "derive_summary",
    "unknown",
]
