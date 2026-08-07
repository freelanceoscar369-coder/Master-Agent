"""AI Infrastructure Executive — Plugin.

Registers the Executive with Mission Control and exposes discovery, probe,
and benchmark actions as capabilities. It produces facts for the Broker.
"""
from __future__ import annotations

from typing import Any

from master_agent.ai_infrastructure.executive.actions import get_all_discovery_actions
from master_agent.ai_infrastructure.executive.probes import get_all_probe_actions
from master_agent.executor.action import Action
from master_agent.executor.executor import LocalExecutor
from master_agent.permissions.permission_system import GrantScope
from master_agent.plugins.base import (
    CapabilityManifest,
    InvocationResult,
    Plugin,
    PluginManifest,
)

AI_INFRA_EXECUTIVE_ID = "ai_infrastructure"
AI_INFRA_VERSION = "1.0.0"


class AiInfrastructurePlugin(Plugin):
    """Exposes AI Infrastructure Executive actions as capabilities."""

    def __init__(self, executor: LocalExecutor) -> None:
        self._executor = executor
        self._actions: dict[str, Action] = {}

        # Register all discovery, probe, and benchmark actions
        for action_cls in get_all_discovery_actions():
            self._register(action_cls())
        for action_cls in get_all_probe_actions():
            self._register(action_cls())

    def _register(self, action: Action) -> None:
        self._actions[action.name] = action
        self._executor.register(action)

    # ---- the Plugin contract -----------------------------------------

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name=AI_INFRA_EXECUTIVE_ID,
            version=AI_INFRA_VERSION,
            capabilities=[
                CapabilityManifest(
                    name=action.name,
                    description=action.description,
                    risk_tier=action.risk_tier,
                    permission_category=action.permission_category,
                )
                for action in self._actions.values()
            ],
        )

    def invoke(self, capability: str, payload: dict[str, Any]) -> InvocationResult:
        if capability not in self._actions:
            return InvocationResult(
                success=False, error=f"unsupported capability: {capability}"
            )

        # ADR-0005 relay: carry the already-obtained approval down to the
        # Executor's own grant key.
        self._executor.permissions.grant(
            self._executor.name, capability, GrantScope.ONCE
        )
        result = self._executor.execute(capability, payload)

        if not result.success:
            return InvocationResult(
                success=False,
                error="; ".join(result.errors) or "unknown executor failure",
                execution_time_seconds=result.execution_time_seconds,
            )
        return InvocationResult(
            success=True,
            output=result.output,
            execution_time_seconds=result.execution_time_seconds,
        )