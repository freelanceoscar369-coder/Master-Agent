"""Founder Dashboard — backend contract only (Mission Brief 023
deliverable #9). No UI work: this is the shape a UI would eventually
render, and nothing more.

Exactly the ten fields the brief names: current objective, current
mission, current executive, current capability, progress, evidence,
errors, ETA, waiting approval, learning progress.

## ETA is honest or absent

`eta_seconds` is estimated from the mean duration of tasks already
completed in the current objective, times the number remaining, and is
`None` until at least one task has completed. A confidently-wrong ETA is
worse than no ETA — the same discipline that stops Verification from
letting execution success imply mission success.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FounderState:
    """One honest snapshot. Frozen: a snapshot describes a moment that has
    already passed, so it is read, never edited."""

    current_objective: str | None
    current_objective_id: str | None
    current_mission: str | None
    current_executive: str | None
    current_capability: str | None
    progress: float
    # `result` is the outcome of the most recently completed task, and is
    # None while nothing has completed yet. Added for MIT-001 Test 6,
    # which asks Founder State to expose a Result alongside Progress.
    # Deliberately the *last completed* result rather than an
    # objective-level summary: Mission Control coordinates and reports
    # what happened, it does not compute a judgment about what a whole
    # objective "means" -- that is the Brain's job (Constitution §3.4).
    result: Any = None
    # The value the founder actually ASKED FOR, when a Step designated one
    # and Verification independently observed it.
    #
    # Deliberately separate from `result` rather than replacing it.
    # `result` means "the last completed task's outcome" and other
    # consumers legitimately want exactly that; an answer is a different
    # fact, is present on almost no mission, and comes from Evidence
    # rather than from what an Executive reported. Collapsing the two
    # would make "what did the last step return" and "what did the
    # founder want to know" the same question, which they are not -- a
    # browser workflow's last step is closing the browser.
    answer: Any = None
    evidence: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    eta_seconds: float | None = None
    waiting_approval: list[dict[str, Any]] = field(default_factory=list)
    learning_progress: dict[str, Any] = field(default_factory=dict)
    # Task 2.5: an objective whose tasks all finished without failure is
    # *verified*, not yet founder-completed (mission_control/completion.py).
    # True only between that moment and the founder's own confirmation —
    # `completion_id` is the one thing a caller needs to answer it.
    requires_founder_completion: bool = False
    completion_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "current_objective": self.current_objective,
            "current_objective_id": self.current_objective_id,
            "current_mission": self.current_mission,
            "current_executive": self.current_executive,
            "current_capability": self.current_capability,
            "progress": self.progress,
            "result": self.result,
            "evidence": list(self.evidence),
            "errors": list(self.errors),
            "eta_seconds": self.eta_seconds,
            "waiting_approval": [dict(item) for item in self.waiting_approval],
            "learning_progress": dict(self.learning_progress),
            "requires_founder_completion": self.requires_founder_completion,
            "completion_id": self.completion_id,
        }


def estimate_eta_seconds(
    completed_durations: list[float], remaining_task_count: int
) -> float | None:
    """None when there is no basis for an estimate — see module docstring.
    Kept a pure function so the honesty rule is testable without building
    a whole Mission Control."""
    if not completed_durations or remaining_task_count <= 0:
        return None
    mean = sum(completed_durations) / len(completed_durations)
    return mean * remaining_task_count
