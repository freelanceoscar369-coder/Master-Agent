"""C28 · `ExecutionResult` — the entire Founder Runtime boundary.

*"Founder Runtime sends `DesktopTask`. Desktop Operator returns
`ExecutionResult`. Nothing more."* This is that return value.

## A deliberate name collision, documented rather than hidden

`master_agent.executor.action.ExecutionResult` already exists and is used
throughout `desktop/execution/` and `desktop/perception/` — every `Act`
this package performs returns one. **This is a different type at a
different altitude.** The Action-level `ExecutionResult` answers *"did
this one click succeed?"*; this module's `ExecutionResult` answers *"did
the whole mission succeed, and what does Founder Runtime need to know?"*
Nothing in this package imports both under the same bare name — every
reference to the Action-level type elsewhere in this package is written
as `action_result.ExecutionResult` or received as an already-typed value,
never aliased to this name.

## What Founder Runtime receives, and what it does not

`ExecutionResult` states facts: how the mission ended, how many of its
steps completed, and — when it did not finish — an `EscalationRequest`
naming exactly what a human or Founder Runtime needs to decide next.
**It never recommends a next step.** Deciding what to do about an
escalation is Founder Runtime's job, per the brief's own boundary: the
Operator "NEVER decides strategy."
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from master_agent.desktop.perception import Confidence


class MissionOutcome(str, Enum):
    """How the mission ended. Closed."""

    #: Every step verified successfully.
    SUCCESS = "success"

    #: A step failed, tactical recovery was exhausted, and the mission
    #: was escalated to Founder Runtime rather than continuing blind.
    ESCALATED = "escalated"

    #: A step's own timeout elapsed before it could be verified.
    TIMED_OUT = "timed_out"


@dataclass(frozen=True)
class EscalationRequest:
    """What Founder Runtime needs to decide next. States the facts;
    recommends nothing — recommending a strategy would itself be the
    strategic decision the Operator is forbidden to make."""

    step_index: int
    reason: str
    retries_exhausted: int
    last_observation_confidence: Confidence
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "reason": self.reason,
            "retries_exhausted": self.retries_exhausted,
            "last_observation_confidence": self.last_observation_confidence.value,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class ExecutionResult:
    """The entire Founder Runtime boundary. Immutable — a result a
    consumer could edit after the fact is not a record of what
    happened."""

    mission_id: str
    outcome: MissionOutcome
    steps_completed: int
    steps_total: int
    reason: str
    started_at: datetime
    finished_at: datetime
    escalation: EscalationRequest | None = None
    step_results: tuple[str, ...] = field(default_factory=tuple)
    """One short line per completed step, in order — a readable trail,
    never a re-derivable log; nothing here is replayed from it."""

    def __post_init__(self) -> None:
        if self.outcome is not MissionOutcome.ESCALATED and self.escalation is not None:
            raise ValueError(
                "escalation is only carried when outcome is ESCALATED; "
                "a successful or timed-out result has nothing to escalate"
            )
        if self.outcome is MissionOutcome.ESCALATED and self.escalation is None:
            raise ValueError("an ESCALATED result must carry an EscalationRequest")
        if self.steps_completed > self.steps_total:
            raise ValueError("steps_completed cannot exceed steps_total")

    @property
    def succeeded(self) -> bool:
        return self.outcome is MissionOutcome.SUCCESS

    def as_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "outcome": self.outcome.value,
            "steps_completed": self.steps_completed,
            "steps_total": self.steps_total,
            "reason": self.reason,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "escalation": self.escalation.as_dict() if self.escalation else None,
            "step_results": list(self.step_results),
        }
