"""The data shapes Verification produces. See ARCHITECTURE constitution
§10 and §17 (Terminology Freeze) for the meaning of each term used here —
this module is the implementation of that vocabulary, not a new one.

Deliberately generic: nothing here references a browser, a filesystem, or
any other Environment. A Worker's concrete Verifier (see verifier.py)
produces these same shapes regardless of what it observed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Verdict(str, Enum):
    """The result of comparing an Observation against an ExpectedOutcome.
    Never conflated with an ExecutionResult's success flag — see
    verifier.py's module docstring for why the two must stay independent.
    """

    MATCHED = "matched"
    NOT_MATCHED = "not_matched"
    PARTIALLY_MATCHED = "partially_matched"
    ERROR = "error"  # observation itself could not be captured


@dataclass
class ObservationCheck:
    """One declarative assertion about an Observation's generic dict view.

    `field` is a dot-path into that dict (e.g. "url", or "elements.0.text"
    for the first entry of a list under the "elements" key) — see
    evaluator.py's `get_field()` for exactly how dots are walked. Kept
    intentionally small: five operators cover everything this Mission
    Brief needs; a bigger expression language is easy to grow into later
    and hard to walk back once something depends on it
    (ENGINEERING_PRINCIPLES.md #10).
    """

    field: str
    operator: str  # "equals" | "contains" | "not_contains" | "exists" | "matches_regex"
    value: Any = None
    description: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "operator": self.operator,
            "value": self.value,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ObservationCheck:
        return cls(
            field=data["field"],
            operator=data["operator"],
            value=data.get("value"),
            description=data.get("description", ""),
        )


@dataclass
class ExpectedOutcome:
    """What a Planner (or, until the real Planner exists, whatever
    hand-builds a Step — see docs/MISSION_BRIEF_022.md) attaches to a Step
    so Verification has something concrete to compare against. See
    KALPAVRIKSHA_VISION_V2.md §3.2."""

    description: str
    checks: list[ObservationCheck] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "checks": [check.as_dict() for check in self.checks],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExpectedOutcome:
        return cls(
            description=data.get("description", ""),
            checks=[ObservationCheck.from_dict(c) for c in data.get("checks", [])],
        )


@dataclass
class CheckResult:
    check: ObservationCheck
    passed: bool
    actual_value: Any = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "check": self.check.as_dict(),
            "passed": self.passed,
            "actual_value": self.actual_value,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CheckResult:
        return cls(
            check=ObservationCheck.from_dict(data["check"]),
            passed=bool(data["passed"]),
            actual_value=data.get("actual_value"),
            error=data.get("error"),
        )


@dataclass
class Evidence:
    """The durable record Verification produces and routes back to the
    Brain (KALPAVRIKSHA_VISION_V2.md §10.2). `observation` is always a
    plain, JSON-shaped dict — never a live object from whatever Environment
    produced it — so Evidence can be logged, persisted, or handed to a
    future Knowledge Candidate nomination (§9.3) without that consumer
    needing to know what kind of Worker produced it.
    """

    evidence_id: str
    worker: str
    environment: str
    captured_at: datetime
    expected: ExpectedOutcome
    observation: dict[str, Any]
    verdict: Verdict
    check_results: list[CheckResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """The canonical JSON-plain projection. **One** serializer, here,
        because the alternative is three that drift.

        Everything survives. Evidence answers *what was observed, when, by
        which Environment verifier, against what checks, and which of them
        passed*; a projection that kept only `evidence_id` and `verdict`
        would be a correlation key and a result code, and none of those
        questions could be answered from it after a restart. That is
        exactly what used to reach durable storage.

        `captured_at` is rendered ISO-8601 rather than dropped, because the
        one thing a historical observation must never acquire is a fresh
        timestamp: `datetime.now()` at read time would silently claim the
        observation happened when the report was generated.
        """
        return {
            "evidence_id": self.evidence_id,
            "worker": self.worker,
            "environment": self.environment,
            "captured_at": self.captured_at.isoformat(),
            "expected": self.expected.as_dict(),
            "observation": dict(self.observation),
            "verdict": self.verdict.value,
            "check_results": [result.as_dict() for result in self.check_results],
            "errors": list(self.errors),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Evidence:
        """Rebuild Evidence from its canonical projection.

        Reconstruction only. Nothing is invented for a field that is
        absent, and no value is recomputed -- in particular the Verdict is
        read, never re-derived from `check_results`, because Verification
        is the only thing permitted to decide one.
        """
        return cls(
            evidence_id=data["evidence_id"],
            worker=data["worker"],
            environment=data["environment"],
            captured_at=datetime.fromisoformat(data["captured_at"]),
            expected=ExpectedOutcome.from_dict(data.get("expected") or {}),
            observation=dict(data.get("observation") or {}),
            verdict=Verdict(data["verdict"]),
            check_results=[
                CheckResult.from_dict(r) for r in data.get("check_results", [])
            ],
            errors=list(data.get("errors", [])),
        )
