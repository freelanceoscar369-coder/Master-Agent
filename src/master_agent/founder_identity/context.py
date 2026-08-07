"""`FounderContext` — what Somesh is allowed to know, without saying how. C29.

*"Somesh talks to Founder Runtime. Founder Runtime delegates."* This module
is the one place in `founder_identity/` that reads anything beyond an
identity or a session, and it reads exactly one thing: the `FounderRuntime`
door C23 already built. It imports no Desktop Executive, no Environment
Intelligence, no Vigilance, no Kernel and no persistence — every fact
below is `FounderRuntime`'s own public method, read once and reported in
founder-facing words, never re-derived.

A time is included because a greeting needs one — *"Good morning"* is
wrong at 9pm — and this module takes it as a parameter rather than reading
a wall clock itself, the same injection discipline `foundation/clock.py`
already establishes for every other founder-facing time in this codebase.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from master_agent.founder_runtime import FounderRuntime


@dataclass(frozen=True)
class FounderContext:
    """Three readiness facts and a moment. Nothing this type holds can
    start work — it has no executor, no plugin, and no Kernel reference,
    the same absence `FounderRuntime` itself guarantees structurally."""

    moment: datetime
    environment_ready: bool
    conversation_ready: bool
    presence_ready: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "moment": self.moment.isoformat(),
            "environment_ready": self.environment_ready,
            "conversation_ready": self.conversation_ready,
            "presence_ready": self.presence_ready,
        }


def founder_context(runtime: FounderRuntime, moment: datetime) -> FounderContext:
    """Read `FounderRuntime`'s own sections and fold them into three
    readiness facts. The only derivation here is "is this section
    present" — the sections themselves are never re-interpreted.
    """
    if not isinstance(runtime, FounderRuntime):
        raise TypeError(
            "founder_context takes the FounderRuntime Founder Edition "
            "already connected; there is no other door to ask through"
        )
    if moment.tzinfo is None:
        raise ValueError("moment must be timezone-aware")

    presence = runtime.presence()
    coverage = presence.get("coverage")

    return FounderContext(
        moment=moment,
        environment_ready=runtime.environment() is not None,
        conversation_ready=runtime.conversation() is not None,
        presence_ready=bool(coverage and coverage.get("complete")),
    )
