"""C28 · Step Timeout Governor — every step carries a `timeout`; if
exceeded, `StepTimeoutFailure`. No infinite waits. No endless retries.
No polling loops.

**This module contains no loop of its own.** It is a single elapsed-time
check, called by the state machine once per step. The "no polling loops"
rule is honoured at the architecture level, not by adding a busy-wait
guard here: `state_machine.py`'s retry loop is *bounded* (at most
`tactical_recovery.MAX_RETRIES` iterations, checked as data, never a
`while True`), and the one action that waits for time to pass
(`WAIT`, in `operator.py`) sleeps exactly once per step rather than
looping internally — the *next* Observe is what re-checks the world, on
the next bounded iteration.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


class StepTimeoutFailure(Exception):
    """A step's own timeout elapsed before it could be verified. Carries
    enough for `ExecutionResult.reason` to state a specific fact, never a
    generic "something went wrong."""

    def __init__(self, step_index: int, elapsed_seconds: float, timeout_seconds: float) -> None:
        self.step_index = step_index
        self.elapsed_seconds = elapsed_seconds
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"step {step_index} exceeded its timeout: {elapsed_seconds:.2f}s "
            f"elapsed against a {timeout_seconds:.2f}s limit"
        )


@dataclass(frozen=True)
class TimeoutGovernor:
    """Stateless. `check()` is a pure function of three moments — it
    reads no clock of its own, the same purity rule every derivation in
    this project already holds to (C20's Presence Layer, C22's
    derivations, C27's observers)."""

    def check(self, *, step_index: int, started_at: datetime, now: datetime, timeout_seconds: float) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive; a step with no timeout is forbidden")
        elapsed = (now - started_at).total_seconds()
        if elapsed > timeout_seconds:
            raise StepTimeoutFailure(step_index, elapsed, timeout_seconds)

    def remaining(self, *, started_at: datetime, now: datetime, timeout_seconds: float) -> float:
        """Seconds left before this step times out. Never negative — a
        step already over its budget has zero remaining, not a negative
        number a caller might otherwise sleep against."""
        elapsed = (now - started_at).total_seconds()
        return max(0.0, timeout_seconds - elapsed)
