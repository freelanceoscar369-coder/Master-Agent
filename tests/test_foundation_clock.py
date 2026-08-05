"""Sprint 1, Component 1 — the Canonical Clock.

Two kinds of test here, and the second kind is the point.

The unit tests below prove the clock behaves: monotonic, ordered,
clamping, zone-correct, deterministic under test.

The **architecture tests** at the bottom prove nothing else reads a wall
clock. Prose in a design document drifts; a failing build does not. This
is the same posture `tests/test_mission_control_architecture.py` takes for
Mission Brief 023's "Mission Control never performs work" rule.
"""
from __future__ import annotations

import ast
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from master_agent.config import ClockConfig, MasterAgentConfig
from master_agent.foundation.clock import (
    Clock,
    Instant,
    InvalidTimezone,
    ManualClock,
    SystemClock,
)

#: Deliberately naive. Several tests below exist precisely to prove that a
#: naive datetime is refused, so constructing one is the point rather than
#: an oversight — hence one named constant with one suppression, instead of
#: four scattered `noqa`s a reader has to re-justify each time.
NAIVE = datetime(2026, 1, 1)  # noqa: DTZ001


# ======================================================================
# Instant
# ======================================================================


def test_instant_requires_an_aware_moment() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        Instant(moment=NAIVE, sequence=1)


def test_instants_sort_into_issue_order() -> None:
    """The receipt ledger reads this property: sorting a list of Instants
    must give the order they were issued in, including within one tick."""
    base = datetime(2026, 1, 1, tzinfo=UTC)
    later = base + timedelta(seconds=1)

    unordered = [
        Instant(later, 3),
        Instant(base, 2),
        Instant(base, 1),
    ]

    assert sorted(unordered) == [
        Instant(base, 1),
        Instant(base, 2),
        Instant(later, 3),
    ]


# ======================================================================
# now() and stamp()
# ======================================================================


def test_now_is_aware_and_utc() -> None:
    assert SystemClock().now().tzinfo is UTC


def test_now_never_decreases() -> None:
    clock = SystemClock()
    readings = [clock.now() for _ in range(1000)]
    assert readings == sorted(readings)


def test_stamp_sequence_is_strictly_increasing() -> None:
    clock = ManualClock()
    sequences = [clock.stamp().sequence for _ in range(1000)]
    assert sequences == list(range(1, 1001))


def test_stamp_orders_events_inside_one_tick() -> None:
    """The defect a bare `datetime.now()` cannot fix: two receipts written
    in the same millisecond have no defined order. A ManualClock that never
    advances is exactly that situation, held still."""
    clock = ManualClock()

    first = clock.stamp()
    second = clock.stamp()

    assert first.moment == second.moment
    assert first.sequence < second.sequence
    assert first < second


def test_now_does_not_consume_a_sequence_number() -> None:
    clock = ManualClock()
    clock.now()
    clock.now()
    assert clock.stamp().sequence == 1


# ======================================================================
# Clamping — the wall clock going backwards
# ======================================================================


def test_a_backwards_step_never_produces_a_decreasing_moment() -> None:
    """An NTP step, a DST bug, or a VM resuming from a snapshot can make the
    system clock read earlier than it did. For an append-only ledger that
    would place a new record before one already written."""
    clock = ManualClock(start=datetime(2026, 1, 1, 12, 0, tzinfo=UTC))
    before = clock.now()

    clock.set(datetime(2026, 1, 1, 11, 0, tzinfo=UTC))  # two hours backwards
    after = clock.now()

    assert after == before, "the clock moved backwards"


def test_a_backwards_step_is_counted_not_hidden() -> None:
    clock = ManualClock(start=datetime(2026, 1, 1, 12, 0, tzinfo=UTC))
    clock.now()

    assert clock.backward_steps == 0

    clock.set(datetime(2026, 1, 1, 11, 30, tzinfo=UTC))
    clock.now()

    assert clock.backward_steps == 1
    assert clock.largest_regression == timedelta(minutes=30)


def test_largest_regression_keeps_the_worst_not_the_latest() -> None:
    clock = ManualClock(start=datetime(2026, 1, 1, 12, 0, tzinfo=UTC))
    clock.now()

    clock.set(datetime(2026, 1, 1, 10, 0, tzinfo=UTC))  # 2h back
    clock.now()
    clock.set(datetime(2026, 1, 1, 11, 59, tzinfo=UTC))  # 1m back from the clamp
    clock.now()

    assert clock.backward_steps == 2
    assert clock.largest_regression == timedelta(hours=2)


def test_clamping_does_not_invent_forward_time() -> None:
    """Holding the line is correct. Skipping ahead to cover for a bad source
    would make the clock lie about the present."""
    start = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    clock = ManualClock(start=start)
    clock.now()

    clock.set(start - timedelta(hours=5))
    assert clock.now() == start


def test_the_clock_resumes_normally_once_the_source_catches_up() -> None:
    start = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    clock = ManualClock(start=start)
    clock.now()

    clock.set(start - timedelta(minutes=10))
    assert clock.now() == start

    clock.set(start + timedelta(minutes=10))
    assert clock.now() == start + timedelta(minutes=10)


def test_a_naive_source_is_refused() -> None:
    clock = SystemClock(source=lambda: NAIVE)
    with pytest.raises(ValueError, match="naive"):
        clock.now()


# ======================================================================
# Founder-local
# ======================================================================


def test_to_founder_local_uses_the_configured_zone() -> None:
    clock = SystemClock(founder_timezone="Asia/Kolkata")
    moment = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)

    local = clock.to_founder_local(moment)

    assert local.hour == 17 and local.minute == 30  # UTC+05:30
    assert local == moment, "conversion must not change the instant"


def test_to_founder_local_returns_a_datetime_not_a_string() -> None:
    """Formatting belongs to Narration (D1) and its Voice Charter (D2). A
    clock that formatted would have to change every time the voice did."""
    local = SystemClock().to_founder_local(datetime(2026, 1, 1, tzinfo=UTC))
    assert isinstance(local, datetime)


def test_to_founder_local_refuses_a_naive_moment() -> None:
    with pytest.raises(ValueError, match="naive"):
        SystemClock().to_founder_local(NAIVE)


def test_an_unknown_timezone_fails_at_construction_not_at_first_render() -> None:
    """Discovering a config typo the first time you need to tell the founder
    when something renews is the worst available moment."""
    with pytest.raises(InvalidTimezone, match="not a known timezone"):
        SystemClock(founder_timezone="Mars/Olympus_Mons")


def test_the_default_founder_timezone_is_utc_not_system_local() -> None:
    """Wrong visibly and identically on every machine beats wrong invisibly
    and differently on each one."""
    assert ClockConfig().founder_timezone == "UTC"
    assert MasterAgentConfig().clock.founder_timezone == "UTC"


# ======================================================================
# ManualClock
# ======================================================================


def test_manual_clock_advances_only_when_told() -> None:
    clock = ManualClock(start=datetime(2026, 1, 1, tzinfo=UTC))
    first = clock.now()
    second = clock.now()
    assert first == second

    clock.advance(timedelta(days=30))
    assert clock.now() == first + timedelta(days=30)


def test_manual_clock_advance_refuses_to_go_backwards() -> None:
    """`advance` means forward. Moving backwards is a deliberate act with
    its own method, so it can never happen by a sign error."""
    with pytest.raises(ValueError, match="moves forward"):
        ManualClock().advance(timedelta(seconds=-1))


def test_manual_clock_set_refuses_a_naive_datetime() -> None:
    with pytest.raises(ValueError, match="aware"):
        ManualClock().set(NAIVE)


def test_thirty_days_passes_in_a_millisecond() -> None:
    """Sprint 3 must demonstrate a rule proposal that needs thirty days of
    decision history. This is why the clock is injectable: the miner is
    real, the decisions are real, and only the passage of time is not."""
    clock = ManualClock(start=datetime(2026, 8, 5, tzinfo=UTC))
    day_one = clock.now()

    clock.advance(timedelta(days=30))

    assert (clock.now() - day_one).days == 30


# ======================================================================
# Concurrency
# ======================================================================


def test_sequences_are_unique_under_concurrent_stamping() -> None:
    """The ledger is single-writer per objective, but the clock is
    process-wide. Two threads stamping at once must not receive the same
    ordering token."""
    clock = ManualClock()
    collected: list[int] = []
    lock = threading.Lock()

    def worker() -> None:
        local = [clock.stamp().sequence for _ in range(200)]
        with lock:
            collected.extend(local)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(collected) == 1600
    assert len(set(collected)) == 1600, "a sequence number was issued twice"
    assert sorted(collected) == list(range(1, 1601)), "the sequence has a gap"


# ======================================================================
# Protocol conformance
# ======================================================================


@pytest.mark.parametrize("clock", [SystemClock(), ManualClock()])
def test_both_clocks_satisfy_the_protocol(clock: Clock) -> None:
    assert isinstance(clock, Clock)


# ======================================================================
# ARCHITECTURE — no ambient time anywhere else
# ======================================================================

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = REPO_ROOT / "src" / "master_agent"

#: Wall-clock reads. Each one answers "what time is it now", which is a
#: decision-path question with a timezone, an ordering, and a founder-facing
#: meaning — so it must come from the one clock.
#:
#: `time.perf_counter` and `time.monotonic` are deliberately absent: they
#: measure *duration*, which has no zone, no ordering against other events,
#: and nothing to tell the founder. Prohibiting them would be cargo cult.
BANNED_TIME_CALLS = {
    "datetime.now",
    "datetime.utcnow",
    "datetime.today",
    "date.today",
    "time.time",
}

#: The one module allowed to read the machine's wall clock.
CLOCK_MODULE = PACKAGE_DIR / "foundation" / "clock.py"

#: Modules that predate this component and still read ambient time.
#:
#: **This list may only shrink.** `test_the_legacy_allowlist_only_shrinks`
#: fails if an entry no longer needs to be here, which forces its removal
#: rather than letting the list decay into a permanent ignore-list. Each
#: entry is migrated as the sprint that touches that module reaches it —
#: not in one heroic commit, which is how a 40-file change becomes a 40-file
#: risk.
LEGACY_AMBIENT_TIME = {
    "ai_infrastructure/cache.py",
    "ai_infrastructure/execution.py",
    "ai_infrastructure/executive/actions.py",
    "ai_infrastructure/executive/models.py",
    "ai_infrastructure/executive/probes.py",
    "broker/benchmark.py",
    "broker/broker.py",
    "broker/cost.py",
    "broker/decision.py",
    "broker/learning.py",
    "broker/recommendation.py",
    "broker/registry.py",
    "cli.py",
    "dashboard/app.py",
    "dashboard/sources.py",
    "desktop/inventory.py",
    "environment/browser_session.py",
    "executor/executor.py",
    "launcher/boot.py",
    "memory/conversation.py",
    "memory/memory_models.py",
    "memory/memory_service.py",
    "mission_control/approvals.py",
    "mission_control/dispatcher.py",
    "mission_control/events.py",
    "mission_control/executives.py",
    "mission_control/knowledge_queue.py",
    "mission_control/self_development.py",
    "mission_control/tasks.py",
    "mission_manager/mission.py",
    "missions/history.py",
    "persistence/schema.py",
    "persistence/serialization.py",
    "plugins/browser_observation.py",
    "plugins/browser_worker.py",
    "plugins/filesystem_observation.py",
    "plugins/filesystem_worker.py",
    "runtime/checkpoint.py",
    "runtime/engine.py",
    "verification/verifier.py",
}


def _source_files() -> list[Path]:
    return sorted(
        path
        for path in PACKAGE_DIR.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _relative(path: Path) -> str:
    return path.relative_to(PACKAGE_DIR).as_posix()


def _ambient_time_calls(path: Path) -> list[str]:
    """Every wall-clock read in one module, as `line: expression`."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        rendered = ast.unparse(node.func)
        # `datetime.datetime.now` and `datetime.now` are the same call; the
        # last two components identify it either way.
        tail = ".".join(rendered.split(".")[-2:])
        if tail in BANNED_TIME_CALLS:
            found.append(f"{node.lineno}: {rendered}()")

    return found


def test_only_the_clock_module_reads_the_machines_wall_clock() -> None:
    """VEDA 04 §7: one canonical timezone source, no ambient local time
    anywhere in the decision path.

    A module reading `datetime.now()` directly cannot be pinned by a test,
    cannot order two events in one tick, and cannot survive the wall clock
    stepping backwards. Take an injected `Clock` instead.
    """
    offenders: dict[str, list[str]] = {}

    for path in _source_files():
        if path == CLOCK_MODULE:
            continue
        relative = _relative(path)
        if relative in LEGACY_AMBIENT_TIME:
            continue
        calls = _ambient_time_calls(path)
        if calls:
            offenders[relative] = calls

    assert not offenders, (
        "these modules read ambient wall-clock time:\n"
        + "\n".join(f"  {name}\n    " + "\n    ".join(calls) for name, calls in offenders.items())
        + "\n\nTake a `Clock` in the constructor instead (see "
        "master_agent.foundation.clock). If this module genuinely predates "
        "the clock and cannot be migrated in this change, add it to "
        "LEGACY_AMBIENT_TIME with the sprint that will remove it."
    )


def test_the_legacy_allowlist_only_shrinks() -> None:
    """An allowlist nobody prunes becomes an ignore-list, and an ignore-list
    is how a prohibition quietly stops being one.

    If a listed module no longer reads ambient time, this fails until the
    entry is deleted — so the debt burns down monotonically and the list
    always states the real remaining work.
    """
    stale = []
    missing = []

    for relative in sorted(LEGACY_AMBIENT_TIME):
        path = PACKAGE_DIR / relative
        if not path.exists():
            missing.append(relative)
            continue
        if not _ambient_time_calls(path):
            stale.append(relative)

    assert not missing, (
        f"LEGACY_AMBIENT_TIME names modules that no longer exist: {missing}. "
        "Remove them."
    )
    assert not stale, (
        f"these modules no longer read ambient time: {stale}. "
        "Remove them from LEGACY_AMBIENT_TIME — the list may only shrink."
    )


def test_the_clock_module_reads_the_wall_clock_exactly_once() -> None:
    """The whole design rests on there being one place. If this number grows,
    the single source has quietly become two."""
    calls = _ambient_time_calls(CLOCK_MODULE)
    assert len(calls) == 1, f"expected exactly one wall-clock read, found: {calls}"
