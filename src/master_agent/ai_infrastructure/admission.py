"""Whether a call should be made at all (Mission Brief 038).

The Broker has already chosen a provider and derived a budget. This asks
the last question before the socket opens: *given that budget and what
this provider is currently doing, is this call worth making?*

Two ways the answer is no, and both are refusals **before** the call
rather than failures after it:

- **Starved.** The time left is below the workload class's floor, so the
  call cannot finish. Issuing it would burn the remaining budget, produce
  a timeout that blames the provider for arithmetic, and — because the
  daemon keeps working after we stop waiting — leave an orphan behind.
- **Occupied.** The provider serialises, and something is already running
  on it. The budget was derived assuming the provider starts when asked;
  behind a queue that assumption is false.

## Deterministic by construction

Same budget, same occupancy, same clock reading -> same decision, same
reason string. Nothing here reads a clock, samples load, or consults
anything that varies between two identical calls. That is what lets an
admission refusal be recorded as evidence and mean the same thing when it
is read back.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from master_agent.ai_infrastructure.workload import profile_for

#: Closed vocabulary. A caller branches on the code; a founder reads the
#: reason. Neither has to parse the other's.
ADMITTED = "admitted"
STARVED = "starved"
OCCUPIED = "occupied"

DECISIONS = (ADMITTED, STARVED, OCCUPIED)


@dataclass(frozen=True)
class Admission:
    """The answer, and why."""

    decision: str = ADMITTED
    reason: str = ""
    #: The floor or count that was not met, and what was actually
    #: available -- so a refusal is diagnosable rather than merely
    #: discouraging.
    required: float | None = None
    available: float | None = None

    @property
    def ok(self) -> bool:
        return self.decision == ADMITTED

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "required": self.required,
            "available": self.available,
        }


def admit(
    *,
    budget: Any,
    request_class: str,
    now: float,
    occupancy: Any = None,
    provider_id: str = "",
    serialises: bool = False,
) -> Admission:
    """Should this call be made?

    `budget` of `None` is admitted: that is the pre-MB038 path, which has
    no budget to be starved against and no deadline to protect. Step 14
    removes it, and the adapter is what refuses an unbudgeted call once
    budgets are mandatory.
    """
    if budget is None:
        return Admission()

    if serialises and occupancy is not None and occupancy.busy(provider_id):
        in_flight = occupancy.in_flight(provider_id)
        orphans = occupancy.abandoned(provider_id)
        detail = f"{in_flight} call(s) already running"
        if orphans:
            # Worth naming separately: an orphan is work nobody is waiting
            # for, and a founder seeing "1 abandoned" knows the queue is
            # not their doing.
            detail += f", {orphans} of them abandoned"
        return Admission(
            decision=OCCUPIED,
            reason=(
                f"{provider_id} runs one call at a time and is busy "
                f"({detail}); a budget derived for an idle provider would "
                "be wrong behind a queue"
            ),
            required=0.0,
            available=float(in_flight),
        )

    floor_ms = profile_for(request_class).total.floor_ms
    remaining_ms = budget.total_remaining_ms(now)
    if remaining_ms < floor_ms:
        return Admission(
            decision=STARVED,
            reason=(
                f"{remaining_ms / 1000:.1f}s left is below the "
                f"{request_class} floor of {floor_ms / 1000:.1f}s; the call "
                "cannot finish, so it is not started"
            ),
            required=floor_ms,
            available=remaining_ms,
        )

    return Admission()
