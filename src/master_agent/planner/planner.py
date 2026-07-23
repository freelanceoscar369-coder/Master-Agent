"""Planner — turns an Intent into a MissionPlan (a DAG of Steps, each
naming a Capability, not a concrete plugin). See ARCHITECTURE.md §4.2.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from master_agent.plugins.model_router import ModelRouter, RoutingContext


@dataclass
class Intent:
    """Structured intent — the output of the Intent Layer, the input to
    the Planner. Never a raw prompt string (see "Intent over prompts").
    """

    goal: str
    constraints: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    success_criteria: list[str] = field(default_factory=list)
    is_sensitive: bool = False


@dataclass
class Step:
    step_id: str
    capability: str
    payload: dict[str, Any]
    depends_on: list[str] = field(default_factory=list)


@dataclass
class MissionPlan:
    steps: list[Step]


class Planner:
    def __init__(self, model_router: ModelRouter) -> None:
        self._model_router = model_router

    def plan(self, intent: Intent) -> MissionPlan:
        """Founder Edition stub: planning itself is a model call — routed
        through the Model Router like any other generation, so it honors
        the same online/sensitivity/preference policy (see
        ARCHITECTURE.md §5). Real prompt construction + plan parsing is
        the next piece of work here, once the Model Router has a live
        provider behind it.
        """
        ctx = RoutingContext(is_sensitive=intent.is_sensitive)
        raise NotImplementedError(
            "Build the plan-generation prompt + response parser here, "
            f"routed via self._model_router.generate(..., ctx={ctx!r})."
        )
