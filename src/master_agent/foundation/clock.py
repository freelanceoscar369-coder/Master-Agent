"""The canonical Clock — the one source of time in Kalpavriksha.

VEDA 04 §7: *"Deadlines, defaults, greetings and expiries are all
founder-local and legally consequential ('renews Friday 00:00'). One
canonical timezone source; no ambient local time anywhere in the decision
path."*

## What this module is, and what it is not

It is **not** a new discipline. The injection pattern already exists and is
well established in this codebase — `ai_infrastructure/execution.py`,
`ai_infrastructure/occupancy.py` and `runtime/engine.py` all take an
injected clock, and MB038 states the rule outright: *"nothing here reads a
wall clock."* What was missing is a canonical implementation to inject.
This is that implementation, and nothing more.

## The three things a `datetime.now()` call cannot do

**1 · It cannot order two events in the same millisecond.** VEDA 04 A1
requires the receipt ledger to be append-only and *monotonic*. Two
receipts written inside one clock tick need a deterministic order, or
"what happened first" has no answer. `stamp()` returns an `Instant`
carrying a strictly increasing sequence alongside the moment.

**2 · It cannot survive the wall clock going backwards.** An NTP step, a
DST transition applied to a naive value, a VM resuming from a snapshot —
each can make the system clock read *earlier* than it did a moment ago.
For an append-only ledger that is not a cosmetic problem: it produces a
record that appears to precede one already written, and the ordering
guarantee the whole audit spine rests on is broken by an event nobody
logged. This clock clamps: it never returns a moment earlier than one it
has already issued, it never fabricates forward time, and it **counts the
regressions** so the anomaly is observable rather than silently absorbed.

**3 · It cannot be pinned by a test.** A deterministic system is one whose
tests do not depend on when they run. `ManualClock` advances only when
told, and the rule for every test in this repository from here on is that
no test reads a wall clock.

## Founder-local is a conversion, not a format

`to_founder_local()` returns a `datetime`, never a string. The zone is
configuration (`ClockConfig.founder_timezone`), never the machine's local
setting — an ambient local zone is exactly what §7 forbids, and a laptop
that travels would otherwise change what "Friday 00:00" means.

Turning an instant into *words* belongs to the Narration Service (D1) and
its Voice Charter (D2). A clock that formatted strings would have to
change every time the voice did.

## The prohibition

`tests/test_foundation_clock.py` fails the build if any module outside
this one reads ambient wall-clock time, with an explicit allowlist of the
modules that predate this component. **That list may only shrink** — a
test asserts that every file on it still needs to be, so it cannot decay
into an ignore-list.

Duration measurement (`time.perf_counter`, `time.monotonic`) is
deliberately *not* prohibited. Measuring how long something took is not a
decision-path time and has no timezone, no ordering, and no founder-facing
meaning.
"""
from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol, runtime_checkable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class InvalidTimezone(ValueError):
    """Raised at construction when the configured founder timezone is not a
    real zone.

    Deliberately at construction rather than at first render: a system that
    starts happily and fails the first time it needs to tell the founder
    when something renews has chosen the worst possible moment to discover
    a typo in a config file.
    """


@dataclass(frozen=True, order=True)
class Instant:
    """One moment, ordered.

    `moment` is always timezone-aware and always UTC. `sequence` breaks
    ties within a single clock tick and is strictly increasing for the life
    of the process.

    Ordering is by `(moment, sequence)`, which is the field order — so
    sorting a list of Instants gives issue order, and that is the property
    the receipt ledger reads.

    **Sequence is process-scoped**, not persisted. Across a restart,
    ordering falls back to `moment`, which is sufficient because a restart
    takes many orders of magnitude longer than the tick two events would
    have to share for the sequence to matter. Stated rather than assumed.
    """

    moment: datetime
    sequence: int

    def __post_init__(self) -> None:
        if self.moment.tzinfo is None:
            raise ValueError("Instant.moment must be timezone-aware")


@runtime_checkable
class Clock(Protocol):
    """What every other component depends on, and nothing more.

    Three methods. A component that needs a fourth is doing something the
    clock should not know about.
    """

    def now(self) -> datetime:
        """The current moment, aware and UTC. Never decreasing."""
        ...

    def stamp(self) -> Instant:
        """The current moment plus an ordering token. Consumes a sequence
        number; `now()` does not."""
        ...

    def to_founder_local(self, moment: datetime) -> datetime:
        """Convert to the founder's configured zone. A conversion, never a
        format."""
        ...


class _MonotonicClock:
    """The single implementation. `SystemClock` and `ManualClock` differ
    only in where their source of raw time comes from, so they share this
    body — which is also what makes `ManualClock` a faithful test double
    rather than a second set of rules.
    """

    def __init__(
        self,
        source: Callable[[], datetime],
        founder_timezone: str = "UTC",
    ) -> None:
        try:
            self._zone = ZoneInfo(founder_timezone)
        except (ZoneInfoNotFoundError, ValueError, KeyError) as exc:
            raise InvalidTimezone(
                f"{founder_timezone!r} is not a known timezone"
            ) from exc

        self._source = source
        self._timezone_name = founder_timezone
        # One lock covers both the clamp and the sequence. They are read and
        # written together, so two locks would be two chances to interleave.
        self._lock = threading.Lock()
        self._last_moment: datetime | None = None
        self._sequence = 0
        # Observability rather than suppression: a clock that quietly
        # absorbed a backwards step would hide the one condition most likely
        # to corrupt an append-only ledger.
        self._backward_steps = 0
        self._largest_regression = timedelta(0)

    # ---- the Clock protocol -----------------------------------------

    def now(self) -> datetime:
        with self._lock:
            return self._read_locked()

    def stamp(self) -> Instant:
        with self._lock:
            moment = self._read_locked()
            self._sequence += 1
            return Instant(moment=moment, sequence=self._sequence)

    def to_founder_local(self, moment: datetime) -> datetime:
        if moment.tzinfo is None:
            raise ValueError(
                "cannot convert a naive datetime to founder-local time; "
                "every moment in Kalpavriksha is aware and UTC"
            )
        return moment.astimezone(self._zone)

    # ---- observability ----------------------------------------------

    @property
    def timezone_name(self) -> str:
        return self._timezone_name

    @property
    def backward_steps(self) -> int:
        """How many times the underlying source read earlier than a moment
        already issued. Non-zero is not an error, but it is a fact worth
        being able to state."""
        return self._backward_steps

    @property
    def largest_regression(self) -> timedelta:
        """The biggest single backwards step observed. A few milliseconds is
        ordinary NTP discipline; an hour is a DST bug upstream."""
        return self._largest_regression

    # ---- internals ---------------------------------------------------

    def _read_locked(self) -> datetime:
        """Read the source, normalise to UTC, and clamp. Caller holds the
        lock."""
        raw = self._source()
        if raw.tzinfo is None:
            raise ValueError(
                "clock source returned a naive datetime; the source must be "
                "timezone-aware so that 'now' is unambiguous"
            )
        moment = raw.astimezone(UTC)

        if self._last_moment is not None and moment < self._last_moment:
            regression = self._last_moment - moment
            self._backward_steps += 1
            self._largest_regression = max(self._largest_regression, regression)
            # Hold the line rather than move it. Returning the last issued
            # moment keeps the ledger ordered; inventing a *later* moment
            # would make the clock lie about the present to cover for the
            # source lying about the past.
            moment = self._last_moment

        self._last_moment = moment
        return moment


class SystemClock(_MonotonicClock):
    """Production. Reads the machine's wall clock, once, in one place.

    **This is the only line in `src/master_agent/` permitted to call
    `datetime.now()`**, and `tests/test_foundation_clock.py` enforces that.

    `source` is injectable so the clamping behaviour itself can be tested
    against a source that misbehaves. It is not a configuration knob and
    nothing in production passes it.
    """

    def __init__(
        self,
        founder_timezone: str = "UTC",
        source: Callable[[], datetime] | None = None,
    ) -> None:
        super().__init__(
            source=source or (lambda: datetime.now(UTC)),
            founder_timezone=founder_timezone,
        )


class ManualClock(_MonotonicClock):
    """Tests. Time advances only when told.

    Two reasons this is not a convenience:

    **Determinism.** A test whose result depends on when it runs is not a
    test. Every test in this repository from here on injects one of these.

    **Reachability.** Sprint 3 must demonstrate a rule proposal that
    requires thirty days of decision history. With an injectable clock that
    is a `advance(timedelta(days=30))` in a test that runs in
    milliseconds — against the real miner, on real recorded decisions, with
    nothing simulated except the passage of time.

    `set()` may move time *backwards*, deliberately: that is how the
    clamping in `_MonotonicClock` gets tested, and simulating an NTP step
    is the only honest way to prove the ledger survives one.
    """

    def __init__(
        self,
        start: datetime | None = None,
        founder_timezone: str = "UTC",
    ) -> None:
        self._current = (start or datetime(2026, 1, 1, tzinfo=UTC)).astimezone(UTC)
        super().__init__(source=lambda: self._current, founder_timezone=founder_timezone)

    def advance(self, delta: timedelta) -> None:
        """Move forward. The ordinary way a test moves time."""
        if delta < timedelta(0):
            raise ValueError("advance() moves forward; use set() to move backwards")
        self._current = self._current + delta

    def set(self, moment: datetime) -> None:
        """Set the underlying source, forwards or backwards.

        Backwards is allowed because the clock's job is to survive it — and
        a test double that could not misbehave could not prove that.
        """
        if moment.tzinfo is None:
            raise ValueError("ManualClock.set() requires an aware datetime")
        self._current = moment.astimezone(UTC)
