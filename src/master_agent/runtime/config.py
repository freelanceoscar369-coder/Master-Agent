"""Runtime Engine configuration (Mission Brief 024 deliverable #8).

Every default is a decision with a reason -- see
RUNTIME_ENGINE_ARCHITECTURE.md §6 for the table. Validated on
construction so a nonsensical configuration fails at startup rather than
producing a Runtime that misbehaves subtly hours later.
"""
from __future__ import annotations

from dataclasses import dataclass


class InvalidRuntimeConfig(Exception):
    pass


@dataclass(frozen=True)
class RuntimeConfig:
    # How long to rest between cycles that found nothing to do.
    poll_interval_seconds: float = 1.0

    # How many tasks the Runtime takes on in one cycle. Executed
    # sequentially within the cycle -- see architecture doc §5 for why
    # this is honestly bounded rather than pretending to parallelise.
    max_concurrent_tasks: int = 1

    # Mechanical retry only: same task, same payload, bounded attempts.
    # Strategic recovery (re-planning, substituting a capability) belongs
    # to the Brain, per Constitution §11.
    max_attempts: int = 3
    retry_delay_seconds: float = 0.5

    # Verification policy: verify whenever the task carries something to
    # check against. Setting this False makes the Runtime execute-only,
    # which is a real (if rarely wanted) mode for a Worker whose Verifier
    # is not yet built.
    verify_when_expected_outcome_present: bool = True

    # Bounds "finish current work where possible" during shutdown.
    shutdown_timeout_seconds: float = 10.0

    # Stop after N cycles. None means run until stopped. Exists so a
    # bounded run is a first-class, tested mode rather than something a
    # caller improvises with a timer.
    max_cycles: int | None = None

    def __post_init__(self) -> None:
        if self.poll_interval_seconds < 0:
            raise InvalidRuntimeConfig("poll_interval_seconds must not be negative")
        if self.max_concurrent_tasks < 1:
            raise InvalidRuntimeConfig("max_concurrent_tasks must be at least 1")
        if self.max_attempts < 1:
            raise InvalidRuntimeConfig("max_attempts must be at least 1")
        if self.retry_delay_seconds < 0:
            raise InvalidRuntimeConfig("retry_delay_seconds must not be negative")
        if self.shutdown_timeout_seconds < 0:
            raise InvalidRuntimeConfig("shutdown_timeout_seconds must not be negative")
        if self.max_cycles is not None and self.max_cycles < 1:
            raise InvalidRuntimeConfig("max_cycles must be at least 1 when set")
