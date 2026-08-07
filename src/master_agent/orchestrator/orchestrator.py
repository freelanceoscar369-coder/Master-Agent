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

    def execute_capability(
        self, capability: str, payload: dict, step_id: str = ""
    ) -> StepResult:
        """Resolve, gate, invoke — one capability call.

        Split out of `execute_step()` by MB037 so a caller with a single
        capability to run does not have to manufacture a `Step` to do it.
        That is not a convenience: `Step` belongs to a `MissionPlan`, the
        Planner is the only thing permitted to produce one, and a caller
        that builds a Step in order to reach this code is producing plan
        vocabulary without having planned.
        """
        candidates = self._registry.find_for_capability(capability)
        if not candidates:
            return StepResult(
                step_id=step_id or capability,
                result=InvocationResult(success=False, error=f"no plugin for capability {capability}"),
            )
        # Founder Edition: take the first candidate. A capability with
        # multiple providers (e.g. two calendar plugins) needs a
        # selection policy eventually — not required for the golden path.
        plugin = candidates[0]
        risk_tier = self._registry.risk_tier_for(plugin.manifest.name, capability)

        try:
            self._permissions.check(plugin.manifest.name, capability, risk_tier)
        except ApprovalRequired:
            return StepResult(step_id=step_id or capability, result=None, blocked_on_approval=True)

        result = plugin.invoke(capability, payload)
        return StepResult(step_id=step_id or capability, result=result)

    def execute_step(self, step: Step) -> StepResult:
        return self.execute_capability(step.capability, step.payload, step_id=step.step_id)

    def execute_plan(self, plan: MissionPlan) -> list[StepResult]:
        """Sequential execution in declared order.

        **Not the mission path.** Since MB037 a founder objective is
        planned and submitted to Mission Control, whose Dispatcher orders
        by dependency and whose Runtime executes and verifies. This walks
        a plan in list order and stops at the first problem, which is all
        the `master-agent-demo` entry point ever needed. Dependency-graph
        scheduling is deliberately *not* built here: Mission Control owns
        execution order, and a second scheduler would be a second
        orchestration authority.
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
