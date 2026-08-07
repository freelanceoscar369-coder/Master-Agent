"""Elite Desktop Executive — operational knowledge (C25).

Upgrades the Desktop Executive from *"what exists?"* to *"how do I operate
it?"*, entirely as knowledge: `ApplicationOperationProfile` (launch, focus,
close, health, recovery, automation strategy), `ApplicationRecoveryPlan`
(all eight failure modes, for every profiled application), human
`Workflow`s, and a `DesktopCapabilityMatrix` naming which application
provides which capability. `DesktopExecutiveV2` is the read-only facade
over all of it, plus the one algorithm this package has —
`recommend(capability, inventory, environment)`, C22's own
`Inference`/`Confidence`/`Evidence` vocabulary answering *"which
application, why, how confident, what else could work."*

**No execution, anywhere in this package.** See `types.py` and
`knowledge.py` for the full argument; `tests/test_desktop_operations.py`
enforces it by AST, the same discipline `founder_runtime/` and
`founder_edition/` already established.
"""
from __future__ import annotations

from master_agent.desktop.operations.executive import (
    KNOWLEDGE_BASE,
    ApplicationRecommendation,
    DesktopExecutiveV2,
    OperationKnowledgeBase,
)
from master_agent.desktop.operations.knowledge import (
    MATRIX,
    PROFILES,
    RECOVERY_PLANS,
    UNPROFILED_EXAMPLES,
    WORKFLOWS,
)
from master_agent.desktop.operations.types import (
    AI_CAPABILITIES,
    ApplicationOperationProfile,
    ApplicationRecoveryPlan,
    AutomationStrategy,
    Capability,
    DesktopCapabilityMatrix,
    FailureMode,
    InvalidOperationKnowledge,
    LaunchMethod,
    OperationNote,
    RecoveryApproach,
    RecoveryGuidance,
    StartupEstimate,
    StartupSpeed,
    WindowStrategy,
    Workflow,
    WorkflowStep,
    WorkflowVerb,
)

__all__ = [
    "AI_CAPABILITIES",
    "KNOWLEDGE_BASE",
    "MATRIX",
    "PROFILES",
    "RECOVERY_PLANS",
    "UNPROFILED_EXAMPLES",
    "WORKFLOWS",
    "ApplicationOperationProfile",
    "ApplicationRecommendation",
    "ApplicationRecoveryPlan",
    "AutomationStrategy",
    "Capability",
    "DesktopCapabilityMatrix",
    "DesktopExecutiveV2",
    "FailureMode",
    "InvalidOperationKnowledge",
    "LaunchMethod",
    "OperationKnowledgeBase",
    "OperationNote",
    "RecoveryApproach",
    "RecoveryGuidance",
    "StartupEstimate",
    "StartupSpeed",
    "WindowStrategy",
    "Workflow",
    "WorkflowStep",
    "WorkflowVerb",
]
