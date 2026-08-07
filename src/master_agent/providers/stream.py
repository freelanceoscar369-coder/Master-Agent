"""Measuring a stream (Mission Brief 038).

This module **measures and nothing else**. It records when the first token
arrived, how long the gaps between tokens were, and how many there were.
It holds no budget, makes no comparison against one, and cannot fail a
call. Enforcement is the adapter's, using a `CallBudget`.

The separation is deliberate and load-bearing: a measurement that also
decides is a measurement you cannot check against a different policy
later, and MB038's whole argument is that today's budgets are guesses that
must be corrected against what was actually observed.

## Unknown stays unknown

`ttft_ms` is `None` until a token actually arrives -- never `0.0`, which
would read as "instant". `max_gap_ms` is `None` until there are two
tokens, because one token produces no gap and reporting `0.0` would
claim a cadence nobody saw. `observed_itl_ms` is `None` until there is
enough to average.

## No wall clock

The clock is injected and read only through `self._clock`. Latency
measured across an NTP step or a laptop resuming from sleep is not
latency, and a monotonic source is the only one a deadline may be
compared against.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_MS = 1000.0


@dataclass(frozen=True)
class StreamObservation:
    """What a stream did, as facts a second reader could recompute.

    Everything here is measured. Nothing is judged: whether these numbers
    represent a healthy call is a question for whoever holds the budget.
    """

    #: Time from the request being issued to the first token. `None` when
    #: no token ever arrived -- which is the prefill-stall signature.
    ttft_ms: float | None = None
    #: Wall time of the whole stream, from issue to the last event.
    elapsed_ms: float = 0.0
    token_count: int = 0
    #: The largest silence between two consecutive tokens. `None` with
    #: fewer than two tokens, because there was no gap to measure.
    max_gap_ms: float | None = None
    #: Mean gap between tokens. `None` with fewer than two tokens.
    observed_itl_ms: float | None = None
    #: True once the producer signalled it was done, as opposed to the
    #: stream simply stopping.
    completed: bool = False

    @property
    def started(self) -> bool:
        """Did the provider ever produce anything at all?"""
        return self.ttft_ms is not None

    @property
    def decode_ms(self) -> float | None:
        """Time spent generating, as distinct from time spent thinking.

        `None` when nothing arrived: with no first token there is no
        boundary between prefill and decode, and inventing one would
        attribute the whole wait to the wrong phase.
        """
        if self.ttft_ms is None:
            return None
        return max(0.0, self.elapsed_ms - self.ttft_ms)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ttft_ms": self.ttft_ms,
            "elapsed_ms": self.elapsed_ms,
            "decode_ms": self.decode_ms,
            "token_count": self.token_count,
            "max_gap_ms": self.max_gap_ms,
            "observed_itl_ms": self.observed_itl_ms,
            "completed": self.completed,
        }


@dataclass
class StreamMonitor:
    """Records the timing of one stream.

    Constructed at the moment the request is issued, so `ttft_ms` measures
    the whole wait a caller experienced rather than only the part after
    some later bookkeeping.

    Mutable on purpose -- it accumulates during a call -- but it hands out
    a frozen `StreamObservation`, so nothing downstream can edit a
    measurement after the fact.
    """

    clock: Any
    started_at: float = field(default=0.0)
    _first_at: float | None = field(default=None, init=False)
    _last_at: float | None = field(default=None, init=False)
    _tokens: int = field(default=0, init=False)
    _max_gap: float | None = field(default=None, init=False)
    _completed: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not self.started_at:
            self.started_at = self.clock()

    # ---- recording -------------------------------------------------------

    def token(self, count: int = 1) -> float:
        """Record that content arrived. Returns the instant it happened.

        `count` allows one chunk carrying several tokens to be recorded
        honestly as several, while the *gap* is still measured between
        chunk arrivals -- which is what a stall actually looks like from
        outside.
        """
        now = self.clock()
        if self._first_at is None:
            self._first_at = now
        elif self._last_at is not None:
            gap = now - self._last_at
            if self._max_gap is None or gap > self._max_gap:
                self._max_gap = gap
        self._last_at = now
        self._tokens += max(1, count)
        return now

    def complete(self) -> None:
        """The producer said it was done, as opposed to going quiet."""
        self._completed = True
        self._last_at = self.clock()

    # ---- reading ---------------------------------------------------------

    def silence_ms(self, now: float) -> float:
        """How long since the last sign of life.

        Measured from the last token when there is one and from the start
        otherwise, so a provider that has produced nothing is still
        visibly silent rather than reporting zero.
        """
        reference = self._last_at if self._last_at is not None else self.started_at
        return (now - reference) * _MS

    def elapsed_ms(self, now: float) -> float:
        return (now - self.started_at) * _MS

    @property
    def started(self) -> bool:
        return self._first_at is not None

    @property
    def token_count(self) -> int:
        return self._tokens

    def observe(self, now: float | None = None) -> StreamObservation:
        """A frozen snapshot of what has happened so far."""
        at = self.clock() if now is None else now
        ttft = None if self._first_at is None else (self._first_at - self.started_at) * _MS
        elapsed = (at - self.started_at) * _MS

        gaps_seen = max(0, self._tokens - 1)
        mean_itl = None
        if gaps_seen and self._first_at is not None and self._last_at is not None:
            mean_itl = ((self._last_at - self._first_at) * _MS) / gaps_seen

        return StreamObservation(
            ttft_ms=ttft,
            elapsed_ms=elapsed,
            token_count=self._tokens,
            max_gap_ms=None if self._max_gap is None else self._max_gap * _MS,
            observed_itl_ms=mean_itl,
            completed=self._completed,
        )
