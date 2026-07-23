"""Orchestrator — walks a MissionPlan, resolves each Step's capability to a
plugin via the registry, checks the Permission System, invokes the plugin.
See ARCHITECTURE.md §4.5. Retry/failure-branching policy lives here, not
in individual plugins.
"""
from __future__ import annotations

from dataclasses import dataclass

from master_agent.permissions.permission_system import ApprovalRequired, PermissionSystem
from master_agent.planner.planner import MissionPlan, Step
from master_agent.plugins.base import InvocationResult
from master_agent.plugins.registry import PluginRegistry


@dataclass
class StepResult:
    step_id: str
    result: InvocationResult | None
    blocked_on_approval: bool = False


class Orchestrator:
    def __init__(self, registry: PluginRegistry, permissions: PermissionSystem) -> None:
        self._registry = registry
        self._permissions = permissions

    def execute_step(self, step: Step) -> StepResult:
        candidates = self._registry.find_for_capability(step.capability)
        if not candidates:
            return StepResult(
                step_id=step.step_id,
                result=InvocationResult(success=False, error=f"no plugin for capability {step.capability}"),
            )
        # Founder Edition: take the first candidate. A capability with
        # multiple providers (e.g. two calendar plugins) needs a
        # selection policy eventually — not required for the golden path.
        plugin = candidates[0]
        risk_tier = self._registry.risk_tier_for(plugin.manifest.name, step.capability)

        try:
            self._permissions.check(plugin.manifest.name, step.capability, risk_tier)
        except ApprovalRequired:
            return StepResult(step_id=step.step_id, result=None, blocked_on_approval=True)

        result = plugin.invoke(step.capability, step.payload)
        return StepResult(step_id=step.step_id, result=result)

    def execute_plan(self, plan: MissionPlan) -> list[StepResult]:
        """Founder Edition stub: sequential execution in declared order.
        Real dependency-graph scheduling (respecting Step.depends_on, and
        stopping the whole mission cleanly on the first blocked_on_approval
        so Mission Manager can surface it) is the next piece of work here.
        """
        results: list[StepResult] = []
        for step in plan.steps:
            step_result = self.execute_step(step)
            results.append(step_result)
            if step_result.blocked_on_approval or (
                step_result.result and not step_result.result.success
            ):
                break
        return results
