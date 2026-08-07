"""Test support for Mission Brief 037.

Builds the real pipeline over a stubbed provider: real Planner, real
`objective_from_plan`, real `MissionControl`, real `PlanHistory`, real
`MemoryService`. Only the thing at the end of the socket is invented,
which is the same line MB033 and MB036 drew.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from master_agent.memory.knowledge_store import JsonKnowledgeStore
from master_agent.memory.memory_service import MemoryService
from master_agent.mission_control.capabilities import (
    CapabilityDescriptor,
    CapabilityRegistry,
)
from master_agent.mission_control.executives import ExecutiveHealth
from master_agent.mission_control.mission_control import MissionControl
from master_agent.missions.history import PlanHistory
from master_agent.missions.service import MissionService
from master_agent.planner.planner import Planner
from master_agent.brain import IntentLayer, Reporter
from tests.planner_test_support import CATALOGUE, StubRunner, plan_text, step

__all__ = [
    "CATALOGUE",
    "StubRunner",
    "capability_registry",
    "memory_for",
    "pipeline",
    "plan_text",
    "step",
]


def descriptors(*names: str) -> list[CapabilityDescriptor]:
    """Capability descriptors for the MB036 test catalogue by default.

    `local_capability` matters: the Runtime translates a qualified name
    into the Executive's own word through Mission Control (never by
    un-mangling the string), so `Filesystem.CreateFolder` has to carry
    `create_folder` or no gateway call can be made.
    """
    out = []
    for name in names or tuple(option.name for option in CATALOGUE):
        executive, capability = name.split(".", 1)
        local = _snake(capability)
        out.append(
            CapabilityDescriptor(
                qualified_name=name,
                executive_id=executive.lower(),
                capability=local,
                description=f"Does {local}.",
                risk_tier="reversible",
            )
        )
    return out


def _snake(pascal: str) -> str:
    letters = []
    for index, char in enumerate(pascal):
        if char.isupper() and index:
            letters.append("_")
        letters.append(char.lower())
    return "".join(letters)


def capability_registry(*names: str) -> CapabilityRegistry:
    """A standalone registry, for the tests that only need a catalogue."""
    registry = CapabilityRegistry()
    for descriptor in descriptors(*names):
        registry.register(descriptor)
    return registry


def memory_for(tmp_path: Path) -> MemoryService:
    memory = MemoryService(store=JsonKnowledgeStore(tmp_path / "knowledge"))
    memory.load()
    return memory


class Pipeline:
    """Everything MB037 wires, wired the way the launcher wires it."""

    def __init__(
        self,
        *replies: Any,
        tmp_path: Path | None = None,
        registry: CapabilityRegistry | None = None,
        with_memory: bool = True,
        with_history: bool = True,
    ) -> None:
        self.mission_control = MissionControl()
        # The Planner's catalogue *is* Mission Control's registry, exactly
        # as the launcher wires it. Two registries would let the Planner
        # name a capability the Dispatcher has never heard of -- which is
        # the first thing this brief has to make impossible.
        if registry is None:
            for executive_id in sorted({d.executive_id for d in descriptors()}):
                self.mission_control.register_executive(
                    executive_id,
                    version="test",
                    capabilities=[
                        d for d in descriptors() if d.executive_id == executive_id
                    ],
                    # READY is not enough: `available_provider_of()` also
                    # requires health, and an Executive registered as
                    # UNKNOWN is never offered work. The launcher's
                    # `discover_executives` sets it; a hand-wired test has
                    # to as well.
                    health=ExecutiveHealth.HEALTHY,
                )
                self.mission_control.mark_executive_ready(executive_id)
            self.registry = self.mission_control.capabilities
        else:
            self.registry = registry
        self.runner = StubRunner(*replies)
        self.planner = Planner(self.runner, self.registry)
        self.history = PlanHistory() if with_history else None
        self.memory = memory_for(tmp_path) if (with_memory and tmp_path) else None
        if self.history is not None:
            self.watching = self.history.attach_to(self.mission_control)
        else:
            self.watching = ()
        if self.memory is not None:
            self.memory.attach_to(self.mission_control)
        self.missions = MissionService(
            planner=self.planner,
            mission_control=self.mission_control,
            intent_layer=IntentLayer(),
            reporter=Reporter(),
            history=self.history,
            memory=self.memory,
        )

    # ---- convenience -----------------------------------------------------

    def start(self, objective: str = "Set up a demo project") -> Any:
        return self.missions.start(objective)

    def objective(self, objective_id: str) -> Any:
        return self.mission_control.dispatcher.objective(objective_id)

    def record(self, plan_id: str) -> Any:
        return self.history.get(plan_id)


def pipeline(*replies: Any, **kwargs: Any) -> Pipeline:
    return Pipeline(*replies, **kwargs)
