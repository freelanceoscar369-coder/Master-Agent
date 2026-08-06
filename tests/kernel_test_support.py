"""Shared doubles for the Kernel's tests.

The `AdmissionProvider` double is deliberately dumb: it returns what it
was given and records what it was asked. Anything cleverer would start
making admission decisions, which is the Objective Engine's job and
exactly what these tests must not simulate.
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from master_agent.foundation.admission import AdmissionRecord, ObjectiveState
from master_agent.foundation.warrant import ReversibilityClass

DEADLINE = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)


def admission(
    objective_id: str = "obj-1",
    state: ObjectiveState = ObjectiveState.EXECUTING,
    **overrides,
) -> AdmissionRecord:
    defaults = {
        "objective_id": objective_id,
        "state": state,
        "consequence_ceiling": ReversibilityClass.REVERSIBLE,
        "budget": Decimal("100.00"),
        "deadline": DEADLINE,
        "required_authority": "grant-77",
        "approval_ref": "appr-9",
    }
    return AdmissionRecord(**{**defaults, **overrides})


class StubAdmissions:
    """An `AdmissionProvider` holding whatever the test put in it."""

    def __init__(self, *records: AdmissionRecord) -> None:
        self._records = {r.objective_id: r for r in records}
        self.lookups: list[str] = []

    def admission_for(self, objective_id: str) -> AdmissionRecord | None:
        self.lookups.append(objective_id)
        return self._records.get(objective_id)

    def publish(self, record: AdmissionRecord) -> None:
        """Change what the Engine publishes, as §10.2's diagram allows."""
        self._records[record.objective_id] = record

    def withdraw(self, objective_id: str) -> None:
        self._records.pop(objective_id, None)


class FailingAdmissions:
    """An `AdmissionProvider` that cannot answer."""

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error or RuntimeError("objective engine unreachable")
        self.lookups: list[str] = []

    def admission_for(self, objective_id: str) -> AdmissionRecord | None:
        self.lookups.append(objective_id)
        raise self._error
