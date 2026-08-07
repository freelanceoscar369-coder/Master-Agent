"""Enforcing the three deadlines (Mission Brief 038).

This module is **policy**. It holds a `CallBudget`, reads a
`StreamMonitor`, and decides whether the call may continue. It measures
nothing itself and touches no socket -- the two things either side of it
are deliberately incapable of the other's job:

```
  transport.py   mechanism    yields bytes, knows no budget
  stream.py      measurement  times them, cannot fail a call
  deadline.py    policy       compares the two, decides       <-- here
```

## Why a blocked read needs the budget too

A stall is silence, and silence cannot be observed by code that is
blocked waiting for the next chunk. So enforcement has two halves, and
both live here: `read_timeout_seconds()` bounds how long a single read
may block, and `check()` classifies what happened once control returns.
Without the first, an ITL breach would not surface until the socket's own
timeout -- which is exactly the "one number for everything" failure.

## Boundary semantics, stated because they differ

A **deadline** is an instant you must not pass, so `now >= deadline`
fails: at the instant itself, the budget is gone. A **gap budget** is a
duration you are allowed to use, so a silence of exactly `itl_ms` is
still within it and only `> itl_ms` fails. Both are tested at the
boundary rather than left to be discovered.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

from master_agent.providers.response import (
    CANCELLED,
    TIMED_OUT_ITL,
    TIMED_OUT_TOTAL,
    TIMED_OUT_TTFT,
)

_MS = 1000.0


@dataclass(frozen=True)
class TimeoutEvent:
    """A deadline breach, with everything needed to explain it.

    Carries the *budget that was granted* beside the *value observed*, so
    a reader can tell "the budget was too small" from "the provider was
    too slow" -- different defects, different owners, and one log line
    until MB038.
    """

    reason: str
    #: The limit that was passed, in milliseconds.
    limit_ms: float
    #: What was actually observed against that limit.
    observed_ms: float
    provider_id: str = ""
    capability: str = ""
    #: The full `CallBudget.as_dict()`, including its derivation, so the
    #: binding constraint travels with the failure.
    budget: dict[str, Any] | None = None
    #: The full `StreamObservation.as_dict()`.
    observation: dict[str, Any] | None = None
    #: Free text from whoever cancelled. Empty for a deadline breach,
    #: which needs no explanation beyond its own reason code.
    detail: str = ""

    @property
    def overran_by_ms(self) -> float:
        return self.observed_ms - self.limit_ms

    @property
    def summary(self) -> str:
        """One sentence a founder can act on."""
        return (
            f"{_SENTENCES[self.reason]} after {self.observed_ms / _MS:.1f}s "
            f"(budget {self.limit_ms / _MS:.1f}s)"
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason,
            "limit_ms": self.limit_ms,
            "observed_ms": self.observed_ms,
            "overran_by_ms": self.overran_by_ms,
            "provider_id": self.provider_id,
            "capability": self.capability,
            "budget": self.budget,
            "observation": self.observation,
            "detail": self.detail,
        }


_SENTENCES = {
    TIMED_OUT_TTFT: "no first token",
    TIMED_OUT_ITL: "stopped producing",
    TIMED_OUT_TOTAL: "did not finish",
    CANCELLED: "cancelled",
}


@dataclass
class Cancellation:
    """Somebody stopped waiting.

    MB038 makes cancellation *a deadline set to now*: one mechanism, four
    triggers (expiry, mission abort, founder cancellation, provider
    failure). This is the signal for the three that come from outside —
    the effect is identical to a deadline passing, and `check()` treats it
    that way, so there is still exactly one place a call is refused.

    Mutable, unlike everything else in this layer, because that is the
    whole point: it is set by one actor while another is blocked reading a
    socket. It carries no timer and no window. Nothing here expires on its
    own; something has to decide.
    """

    reason: str = ""
    #: The instant it was requested, on the same monotonic clock as the
    #: budget. `None` until cancelled -- never `0.0`, which would read as
    #: "cancelled at the start of time".
    at: float | None = None

    @property
    def cancelled(self) -> bool:
        return self.at is not None

    def cancel(self, now: float, reason: str = "") -> None:
        """Idempotent: the first cancellation is the one that counts, so a
        second caller cannot rewrite why the work stopped."""
        if self.at is None:
            self.at = now
            self.reason = reason


class DeadlineExceeded(Exception):
    """Raised out of `supervise()` when a budget is passed.

    An exception rather than a sentinel because it must unwind a
    generator: there is no value to return from a stream that has already
    stopped being valid.
    """

    def __init__(self, event: TimeoutEvent) -> None:
        self.event = event
        super().__init__(event.summary)


def check(
    budget: Any, monitor: Any, now: float, cancellation: Any = None
) -> TimeoutEvent | None:
    """Has any deadline been passed? Returns the breach, or None.

    Ordered most-specific first. Cancellation outranks every deadline: if
    somebody withdrew the question, *why the budget would also have run
    out* is no longer the interesting fact, and recording a timeout there
    would blame the provider for a founder's decision.

    After that, before a first token, TTFT is the explanation even if
    total has also gone -- and it will have gone first, because the budget
    guarantees `ttft <= total`. After a first token, a stall is the
    explanation even if total has also expired, because a provider that
    went quiet at second 30 of a 600-second budget did not "run out of
    time"; it stopped.
    """
    if cancellation is not None and cancellation.cancelled:
        return TimeoutEvent(
            reason=CANCELLED,
            limit_ms=budget.total_ms,
            observed_ms=monitor.elapsed_ms(now),
            detail=cancellation.reason,
        )

    if not monitor.started:
        if budget.ttft_expired(now):
            return TimeoutEvent(
                reason=TIMED_OUT_TTFT,
                limit_ms=budget.ttft_ms,
                observed_ms=monitor.elapsed_ms(now),
            )
        if budget.total_expired(now):
            return TimeoutEvent(
                reason=TIMED_OUT_TOTAL,
                limit_ms=budget.total_ms,
                observed_ms=monitor.elapsed_ms(now),
            )
        return None

    silence = monitor.silence_ms(now)
    if budget.enforce_itl and silence > budget.itl_ms:
        return TimeoutEvent(
            reason=TIMED_OUT_ITL,
            limit_ms=budget.itl_ms,
            observed_ms=silence,
        )
    if budget.total_expired(now):
        return TimeoutEvent(
            reason=TIMED_OUT_TOTAL,
            limit_ms=budget.total_ms,
            observed_ms=monitor.elapsed_ms(now),
        )
    return None


def read_timeout_seconds(budget: Any, monitor: Any, now: float) -> float:
    """How long the next read may block, in seconds.

    The tightest deadline that could plausibly fire while we are waiting:
    the remaining prefill window before a first token, the stall budget
    after one, and never longer than the whole call has left.

    Never negative -- a caller past its deadline should get an immediate
    read rather than an exception from the socket layer about a nonsense
    timeout. `check()` is what refuses it, one line later.
    """
    if monitor.started:
        window = budget.itl_ms if budget.enforce_itl else budget.total_remaining_ms(now)
    else:
        window = budget.ttft_remaining_ms(now)
    bounded = min(window, budget.total_remaining_ms(now))
    return max(0.0, bounded) / _MS


def supervise(
    chunks: Iterable[Any],
    budget: Any,
    monitor: Any,
    clock: Any,
    is_token: Any = bool,
    provider_id: str = "",
    capability: str = "",
    cancellation: Any = None,
) -> Iterator[Any]:
    """Yield a stream's chunks, refusing it the moment a budget is passed.

    `is_token` decides which chunks count as content. It is supplied by
    the adapter because deciding that means parsing the provider's
    format, and this module parses nothing -- an Ollama `done` frame
    carries no text and must not reset the stall clock.
    """

    def fail(event: TimeoutEvent) -> DeadlineExceeded:
        return DeadlineExceeded(
            TimeoutEvent(
                reason=event.reason,
                limit_ms=event.limit_ms,
                observed_ms=event.observed_ms,
                provider_id=provider_id,
                capability=capability,
                budget=budget.as_dict(),
                observation=monitor.observe(now=clock()).as_dict(),
                detail=event.detail,
            )
        )

    for chunk in chunks:
        now = clock()
        # Checked *before* the arrival is recorded: a token that shows up
        # after the stall budget has already gone is a late token, and
        # recording it first would reset the very clock that failed.
        breach = check(budget, monitor, now, cancellation)
        if breach is not None:
            raise fail(breach)

        if is_token(chunk):
            monitor.token()
        yield chunk

    # The stream ended on its own. It can still have ended too late.
    final = check(budget, monitor, clock(), cancellation)
    if final is not None:
        raise fail(final)
