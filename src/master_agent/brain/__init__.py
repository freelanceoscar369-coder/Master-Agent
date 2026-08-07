"""Brain Package — the cognitive layer.

Constitution §3: The Executive Brain is the cognitive layer. It decides *what*
to do, *how* to structure it, and *how to explain it back*. Owns Intent,
Planning, Reasoning-Provider selection, and Reporting. Never executes,
never touches Environment, never holds Permission grant.

Components:
- Intent Layer: Turns raw input into structured Intent
- Planner: Produces MissionPlan from Intent (in master_agent.planner)
- Model Router: Selects Reasoning Provider via AI Capability Broker (in master_agent.plugins.model_router)
- Reporter: Converts Mission outcome + Evidence into founder-facing reports
"""
from __future__ import annotations

# Intent Layer
from master_agent.brain.intent import (
    IntentLayer,
    IntentResult,
    ClarificationQuestion,
)

# Reporter
from master_agent.brain.reporter import (
    Reporter,
    Report,
    ReportContext,
    ReportFormat,
    ReportTone,
)

# Planner (re-exported from planner package)
from master_agent.planner import (
    Planner,
    Intent,
    MissionPlan,
    Step,
    PlanOutcome,
    PlanRefusal,
)

# Model Router (re-exported from plugins)
from master_agent.plugins.model_router import (
    ModelRouter,
    RoutingContext,
    SelectionRequest,
    ProviderSelector,
    BrokerUnavailable,
    ProviderNotWired,
    REASONING,
)

__all__ = [
    # Intent Layer
    "IntentLayer",
    "IntentResult",
    "ClarificationQuestion",
    # Reporter
    "Reporter",
    "Report",
    "ReportContext",
    "ReportFormat",
    "ReportTone",
    # Planner
    "Planner",
    "Intent",
    "MissionPlan",
    "Step",
    "PlanOutcome",
    "PlanRefusal",
    # Model Router
    "ModelRouter",
    "RoutingContext",
    "SelectionRequest",
    "ProviderSelector",
    "BrokerUnavailable",
    "ProviderNotWired",
    "REASONING",
]