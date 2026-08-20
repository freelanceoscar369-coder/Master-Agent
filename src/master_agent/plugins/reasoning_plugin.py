"""The Reasoning Executive: judgement, exposed as a capability.

The Constitution already treats reasoning providers as Workers behind the
Capability Registry. This is the registration that finally makes that true
at *execution* time rather than only at planning time -- the same
composition `BrowserPlugin` uses, with the tiered runner injected exactly
as a session manager is.

One capability, deliberately. `Reasoning.Transform` covers comparing
documents, summarising a profile, deriving search criteria and ranking
observations, because all four are the same operation: evidence in,
reasoned text out. Splitting them would be inventing product vocabulary
for what is one primitive.
"""
from __future__ import annotations

from typing import Any

from master_agent.capabilities.extraction import contracts_from_actions
from master_agent.executor.action import Action
from master_agent.executor.actions.reasoning.transform import ReasoningTransformAction
from master_agent.executor.executor import LocalExecutor
from master_agent.permissions.permission_system import GrantScope
from master_agent.plugins.base import (
    CapabilityManifest,
    InvocationResult,
    Plugin,
    PluginManifest,
)


class ReasoningPlugin(Plugin):
    """Exposes the reasoning transform as a registered capability.

    `runner` is whatever the deployment already uses for reasoning -- in
    Founder Edition, the same `TieredPromptRunner` the Planner holds. It is
    injected rather than built here so this plugin owns no routing policy,
    no provider list and no fallback ladder.
    """

    def __init__(self, executor: LocalExecutor, runner: Any = None) -> None:
        self._executor = executor
        self._actions: dict[str, Action] = {}
        action = ReasoningTransformAction(runner)
        self._executor.register(action)
        self._actions[action.name] = action

    def bind_runner(self, runner: Any) -> None:
        """Give the reasoning capability its runner once one exists."""
        for action in self._actions.values():
            binder = getattr(action, "bind_runner", None)
            if binder is not None:
                binder(runner)

    @property
    def manifest(self) -> PluginManifest:
        def qualified_name(executive_id: str, capability: str) -> str:
            def _pascal(raw: str) -> str:
                return "".join(
                    part[:1].upper() + part[1:]
                    for part in raw.replace("-", "_").split("_")
                    if part
                )

            return f"{_pascal(executive_id)}.{_pascal(capability)}"

        contracts = {
            contract.metadata["local_name"]: contract
            for contract in contracts_from_actions(
                self._actions, "reasoning", qualified_name
            )
        }

        return PluginManifest(
            name="reasoning",
            version="0.1.0",
            capabilities=[
                CapabilityManifest(
                    name=action.name,
                    description=action.description,
                    risk_tier=action.risk_tier,
                    permission_category=action.permission_category,
                    input_schema=contracts[action.name].inputs.as_dict(),
                    output_schema=contracts[action.name].outputs.as_dict(),
                )
                for action in self._actions.values()
            ],
        )

    def invoke(self, capability: str, payload: dict[str, Any]) -> InvocationResult:
        if capability not in self._actions:
            return InvocationResult(
                success=False, error=f"unsupported capability: {capability}"
            )

        # ADR-0005's relay, unchanged.
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
