"""Health classification — presentation only (ADR-0016 Decision 3).

Every function here is **pure, over plain numbers**. No live objects, no
I/O, no decisions that anything in Kalpavriksha consumes. Deleting this
module would change what a founder *sees* and nothing about what the
system *does* -- which is exactly the boundary MB026 Rule 4 draws, made
structural instead of promised.

Each rule is documented at its function, and every panel renders the raw
counts beside the label, so a founder can always check the judgement
against the numbers that produced it.
"""
from __future__ import annotations

from enum import Enum


class HealthLevel(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


# Runtime states that mean "alive and doing its job". A runtime that is
# STOPPED is not unhealthy -- it is stopped, which is a different fact and
# is reported as such.
_LIVE_RUNTIME_STATES = {"idle", "dispatching", "waiting", "verifying"}


def runtime_health(state: str | None) -> HealthLevel:
    """HEALTHY while the loop is alive and cycling; WARNING while it is
    recovering or shutting down; CRITICAL only when it has stopped with
    work presumably outstanding; UNKNOWN when there is no runtime to ask.
    """
    if state is None:
        return HealthLevel.UNKNOWN
    if state in _LIVE_RUNTIME_STATES:
        return HealthLevel.HEALTHY
    if state in {"recovering", "stopping", "initializing"}:
        return HealthLevel.WARNING
    if state == "stopped":
        return HealthLevel.CRITICAL
    return HealthLevel.UNKNOWN


def queue_health(
    pending: int | None, blocked: int | None, failed: int | None
) -> HealthLevel:
    """A queue is HEALTHY when nothing is stuck. Blocked or failed work is
    a WARNING -- it is visible and waiting on a decision, not a system
    fault. Both at once is CRITICAL, because a failure that has already
    blocked dependents is a stalled objective rather than an isolated
    problem.
    """
    if pending is None and blocked is None and failed is None:
        return HealthLevel.UNKNOWN
    blocked = blocked or 0
    failed = failed or 0
    if blocked and failed:
        return HealthLevel.CRITICAL
    if blocked or failed:
        return HealthLevel.WARNING
    return HealthLevel.HEALTHY


def audit_health(total_entries: int | None, failures: int | None) -> HealthLevel:
    """An audit stream with entries is HEALTHY -- recorded failures are
    the audit *working*, not the audit being unwell, so failures alone
    never downgrade it. An empty stream is UNKNOWN rather than healthy:
    nothing has been observed yet, which is not the same as "all is
    well".
    """
    if total_entries is None:
        return HealthLevel.UNKNOWN
    if total_entries == 0:
        return HealthLevel.UNKNOWN
    return HealthLevel.HEALTHY


def persistence_health(
    event_log_size: int | None,
    snapshot_schema_version: int | None,
    quarantined_tasks: int | None = None,
) -> HealthLevel:
    """HEALTHY when both a snapshot and a log exist. WARNING when only one
    does -- the system would still recover, but from a weaker position --
    or when a recovery quarantined work, which a founder should look at.
    UNKNOWN when persistence is not wired at all.
    """
    if event_log_size is None and snapshot_schema_version is None:
        return HealthLevel.UNKNOWN
    if quarantined_tasks:
        return HealthLevel.WARNING
    if snapshot_schema_version is None or not event_log_size:
        return HealthLevel.WARNING
    return HealthLevel.HEALTHY
