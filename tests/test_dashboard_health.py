"""Health classification — the pure functions ADR-0016 Decision 3
quarantines so "presentation, not business logic" is structural.
"""
from __future__ import annotations

import pytest

from master_agent.dashboard.health import (
    HealthLevel,
    audit_health,
    persistence_health,
    queue_health,
    runtime_health,
)

# ---- runtime ------------------------------------------------------------


@pytest.mark.parametrize("state", ["idle", "dispatching", "waiting", "verifying"])
def test_a_cycling_runtime_is_healthy(state):
    assert runtime_health(state) is HealthLevel.HEALTHY


@pytest.mark.parametrize("state", ["recovering", "stopping", "initializing"])
def test_a_transitioning_runtime_is_a_warning(state):
    assert runtime_health(state) is HealthLevel.WARNING


def test_a_stopped_runtime_is_critical():
    assert runtime_health("stopped") is HealthLevel.CRITICAL


def test_no_runtime_is_unknown_not_healthy():
    """Absence must never read as wellness."""
    assert runtime_health(None) is HealthLevel.UNKNOWN


def test_an_unrecognised_runtime_state_is_unknown_not_guessed():
    assert runtime_health("teleporting") is HealthLevel.UNKNOWN


# ---- queue --------------------------------------------------------------


def test_a_clear_queue_is_healthy():
    assert queue_health(pending=3, blocked=0, failed=0) is HealthLevel.HEALTHY


def test_an_empty_queue_is_healthy():
    assert queue_health(pending=0, blocked=0, failed=0) is HealthLevel.HEALTHY


def test_blocked_work_is_a_warning():
    assert queue_health(pending=1, blocked=2, failed=0) is HealthLevel.WARNING


def test_failed_work_is_a_warning():
    assert queue_health(pending=1, blocked=0, failed=1) is HealthLevel.WARNING


def test_a_failure_that_has_blocked_dependents_is_critical():
    """A stalled objective, not an isolated problem."""
    assert queue_health(pending=0, blocked=1, failed=1) is HealthLevel.CRITICAL


def test_an_unreadable_queue_is_unknown():
    assert queue_health(None, None, None) is HealthLevel.UNKNOWN


def test_queue_health_treats_missing_counts_as_zero_not_as_failure():
    assert queue_health(pending=2, blocked=None, failed=None) is HealthLevel.HEALTHY


# ---- audit --------------------------------------------------------------


def test_an_audit_with_entries_is_healthy():
    assert audit_health(total_entries=10, failures=0) is HealthLevel.HEALTHY


def test_recorded_failures_do_not_make_the_audit_unhealthy():
    """A recorded failure is the audit *working*."""
    assert audit_health(total_entries=10, failures=5) is HealthLevel.HEALTHY


def test_an_empty_audit_is_unknown_not_healthy():
    """Nothing observed yet is not the same as all is well."""
    assert audit_health(total_entries=0, failures=0) is HealthLevel.UNKNOWN


def test_an_unreadable_audit_is_unknown():
    assert audit_health(None, None) is HealthLevel.UNKNOWN


# ---- persistence --------------------------------------------------------


def test_a_snapshot_and_a_log_together_are_healthy():
    assert (
        persistence_health(event_log_size=10, snapshot_schema_version=1)
        is HealthLevel.HEALTHY
    )


def test_a_log_with_no_snapshot_is_a_warning():
    assert (
        persistence_health(event_log_size=10, snapshot_schema_version=None)
        is HealthLevel.WARNING
    )


def test_a_snapshot_with_no_log_is_a_warning():
    assert (
        persistence_health(event_log_size=0, snapshot_schema_version=1)
        is HealthLevel.WARNING
    )


def test_quarantined_work_downgrades_persistence_to_a_warning():
    """A founder should look at work that was interrupted."""
    assert (
        persistence_health(event_log_size=10, snapshot_schema_version=1, quarantined_tasks=2)
        is HealthLevel.WARNING
    )


def test_persistence_not_wired_at_all_is_unknown():
    assert persistence_health(None, None) is HealthLevel.UNKNOWN


# ---- purity -------------------------------------------------------------


def test_every_health_function_is_pure_over_plain_numbers():
    """ADR-0016 Decision 3: no live objects, no I/O -- which is what makes
    "the Dashboard decides nothing" checkable rather than promised."""
    import inspect

    from master_agent.dashboard import health as health_module

    source = inspect.getsource(health_module)
    for forbidden in ("import os", "open(", "requests", "mission_control", "runtime."):
        assert forbidden not in source


def test_health_levels_are_a_closed_vocabulary():
    assert {level.value for level in HealthLevel} == {
        "healthy",
        "warning",
        "critical",
        "unknown",
    }
