"""The Executive Registry (Mission Brief 023 deliverable #3).

"Executive" and the Constitution's "Worker" (§17) name the same
architectural role — one registered unit of execution capability. `Worker`
stays canonical in the Constitution and in Worker-side code
(`BrowserWorker` is untouched); `Executive` is the term Mission Control's
registration API uses, because that is the vocabulary Mission Brief 023
specified. See docs/adr/0014-executive-and-worker-terminology.md for the
reconciliation and MISSION_CONTROL_ARCHITECTURE.md §2.

Every Executive exposes exactly the seven fields the brief requires:
Executive ID, Version, Capabilities, Health, Status, Dependencies, and
Current Task.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from master_agent.mission_control.lifecycle import (
    WorkerState,
    assert_transition,
)


class ExecutiveHealth(str, Enum):
    """Distinct from lifecycle state on purpose: state answers "what is it
    doing", health answers "can it be trusted with work right now". A
    Worker can be READY but DEGRADED, and the dispatcher needs to be able
    to tell those apart."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ExecutiveAlreadyRegistered(Exception):
    pass


class UnknownExecutive(Exception):
    pass


@dataclass
class ExecutiveRecord:
    """Mission Control's description of one Executive. Deliberately holds
    no reference to the live object it describes — Mission Control
    coordinates and must not be able to invoke anything, even by accident
    (MISSION_CONTROL_ARCHITECTURE.md §1)."""

    executive_id: str
    version: str
    capabilities: list[str] = field(default_factory=list)
    health: ExecutiveHealth = ExecutiveHealth.UNKNOWN
    state: WorkerState = WorkerState.CREATED
    dependencies: list[str] = field(default_factory=list)
    current_task_id: str | None = None
    registered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_available(self) -> bool:
        """Available for new work: idle-but-alive, trusted, and not already
        holding a task.

        `current_task_id is None` is load-bearing, not belt-and-braces:
        Mission Control assigns a task without transitioning the Executive
        to RUNNING, because it cannot know when the Worker actually starts
        (that is the Worker's own report). Without this check, the state
        alone still reads READY immediately after an assignment, and the
        dispatcher would hand the same Executive a second task in the same
        pass. Found by
        test_a_ready_task_with_no_available_provider_stays_ready_not_failed.

        DEGRADED is deliberately excluded — a degraded Executive keeps
        whatever work it already has but is not handed more.
        """
        return (
            self.state in {WorkerState.READY, WorkerState.COMPLETED}
            and self.health is ExecutiveHealth.HEALTHY
            and self.current_task_id is None
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "executive_id": self.executive_id,
            "version": self.version,
            "capabilities": list(self.capabilities),
            "health": self.health.value,
            "status": self.state.value,
            "dependencies": list(self.dependencies),
            "current_task": self.current_task_id,
            "registered_at": self.registered_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class ExecutiveRegistry:
    def __init__(self) -> None:
        self._executives: dict[str, ExecutiveRecord] = {}

    def register(self, record: ExecutiveRecord) -> ExecutiveRecord:
        if record.executive_id in self._executives:
            raise ExecutiveAlreadyRegistered(
                f"executive already registered: {record.executive_id}"
            )
        self._executives[record.executive_id] = record
        return record

    def get(self, executive_id: str) -> ExecutiveRecord:
        record = self._executives.get(executive_id)
        if record is None:
            raise UnknownExecutive(f"unknown executive: {executive_id}")
        return record

    def has(self, executive_id: str) -> bool:
        return executive_id in self._executives

    def deregister(self, executive_id: str) -> ExecutiveRecord:
        record = self.get(executive_id)
        del self._executives[executive_id]
        return record

    def all(self) -> list[ExecutiveRecord]:
        return list(self._executives.values())

    def ids(self) -> list[str]:
        return sorted(self._executives)

    def transition(self, executive_id: str, new_state: WorkerState) -> ExecutiveRecord:
        """Consults the legal-transition table before mutating — an
        impossible state change raises rather than being silently
        accepted."""
        record = self.get(executive_id)
        assert_transition(record.state, new_state)
        record.state = new_state
        record.updated_at = datetime.now(UTC)
        return record

    def set_health(self, executive_id: str, health: ExecutiveHealth) -> ExecutiveRecord:
        record = self.get(executive_id)
        record.health = health
        record.updated_at = datetime.now(UTC)
        return record

    def set_current_task(self, executive_id: str, task_id: str | None) -> ExecutiveRecord:
        record = self.get(executive_id)
        record.current_task_id = task_id
        record.updated_at = datetime.now(UTC)
        return record

    def providers_of(self, qualified_capability: str) -> list[ExecutiveRecord]:
        return [
            record
            for record in self._executives.values()
            if qualified_capability in record.capabilities
        ]

    def available_provider_of(self, qualified_capability: str) -> ExecutiveRecord | None:
        """First healthy, idle provider — deterministic (registration
        order) rather than arbitrary, so dispatch is reproducible. A real
        selection policy (load, affinity, cost) is a scheduling concern
        this Mission Brief deliberately does not build ahead of need."""
        for record in self._executives.values():
            if qualified_capability in record.capabilities and record.is_available:
                return record
        return None

    def __len__(self) -> int:
        return len(self._executives)
