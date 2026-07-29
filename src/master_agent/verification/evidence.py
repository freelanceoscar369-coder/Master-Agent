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


@dataclass
class ExpectedOutcome:
    """What a Planner (or, until the real Planner exists, whatever
    hand-builds a Step — see docs/MISSION_BRIEF_022.md) attaches to a Step
    so Verification has something concrete to compare against. See
    KALPAVRIKSHA_VISION_V2.md §3.2."""

    description: str
    checks: list[ObservationCheck] = field(default_factory=list)


@dataclass
class CheckResult:
    check: ObservationCheck
    passed: bool
    actual_value: Any = None
    error: str | None = None


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
