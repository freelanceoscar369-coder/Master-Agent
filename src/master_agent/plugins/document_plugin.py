"""The Document Executive: turn documents into text, and text into documents.

A second Executive rather than two more filesystem capabilities, because
these are a different kind of work. `Filesystem` moves and names bytes;
`Document` understands formats. Keeping them apart means a founder reading
a plan can see which one a step belongs to, and means adding ODT or RTF
later touches one place.

Composed exactly like `FilesystemPlugin` -- same executor injection, same
`locations` pass-through, same manifest built from the actions themselves
so the contract and the code cannot drift. It is a smaller copy of an
existing shape, not a second architecture.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from master_agent.capabilities.extraction import contracts_from_actions
from master_agent.executor.action import Action
from master_agent.executor.actions.document.extract_text import ExtractTextAction
from master_agent.executor.actions.document.write_document import WriteDocumentAction
from master_agent.executor.executor import LocalExecutor
from master_agent.permissions.permission_system import GrantScope
from master_agent.plugins.base import (
    CapabilityManifest,
    InvocationResult,
    Plugin,
    PluginManifest,
)

_ACTION_CLASSES: tuple[type[Action], ...] = (
    ExtractTextAction,
    WriteDocumentAction,
)


class DocumentPlugin(Plugin):
    """Exposes every registered document Action as a same-named capability."""

    def __init__(
        self, executor: LocalExecutor, locations: dict[str, Path] | None = None
    ) -> None:
        self._executor = executor
        self._actions: dict[str, Action] = {}
        for action_cls in _ACTION_CLASSES:
            action = action_cls(locations)
            self._executor.register(action)
            self._actions[action.name] = action

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
                self._actions, "document", qualified_name
            )
        }

        return PluginManifest(
            name="document",
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

        # The same approval relay `FilesystemPlugin` performs, and for the
        # same reason (ADR-0005): the Orchestrator has already gated entry
        # on this plugin's own key, while the Executor checks its own. The
        # grant is relayed rather than the check skipped, and deliberately
        # not wrapped in a try/except -- an ApprovalRequired here must
        # propagate like any other, not be swallowed.
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
