"""The deadline a provider is given (Mission Brief 038).

A pure dataclass module with no I/O, no HTTP client and no dependency on
anything above it -- so the wiring layer can *derive* a budget and the
adapter can *enforce* one without either importing the other. This is the
same shape MB033 used to let `ai_infrastructure` record an execution
without acquiring the ability to perform one.

## Absolute instants, never remaining durations

Every deadline here is a point on a **monotonic** clock, not a number of
seconds left. A relative duration is re-based at every hop, so five
layers each honouring "you have 60 seconds" honour five sixty-second
windows -- an error that is invisible in a one-hop test, compounds under
load, and grows as the system gains layers. An absolute instant is
idempotent under propagation: passing it through any number of layers
cannot extend it, and a layer that forgets to subtract its own overhead
cannot cause a bug, because there is no subtraction to forget.

Monotonic specifically, so an NTP step or a DST change cannot extend or
collapse a live deadline.

## Three deadlines, because they measure three things

`total` bounds the whole call. `ttft` bounds prefill -- the forward pass
over the input -- and is the only one that scales with prompt size.
`itl` bounds decode cadence and is a property of the model and the
hardware, independent of how large the prompt was.

Three quantities that scale with different variables cannot be
represented by one variable, which is why the single `timeout_seconds`
this replaces could not distinguish a provider that was thinking from one
that had hung.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: Which constraint produced the value. Recorded on every budget, because
#: without it "it timed out" does not say whether to raise the class floor
#: or the mission SLA -- and every timeout then gets "fixed" by raising
#: the planning floor until the system is back to one big number.
FROM_ESTIMATE = "estimate"
FROM_FLOOR = "class_floor"
FROM_CEILING = "class_ceiling"
FROM_MISSION = "mission_clamp"
FROM_OVERRIDE = "call_override"

BINDING_CONSTRAINTS = (
    FROM_ESTIMATE,
    FROM_FLOOR,
    FROM_CEILING,
    FROM_MISSION,
    FROM_OVERRIDE,
)


@dataclass(frozen=True)
class Derivation:
    """What the budget was computed from.

    Recorded so a wrong budget is diagnosable rather than mysterious, and
    so the estimate can later be corrected against what was actually
    observed. Every field is plain and JSON-shaped: this travels into the
    execution record and must survive being written to disk and read by a
    process that imports none of this.
    """

    request_class: str = ""
    prompt_tokens: int = 0
    expected_output_tokens: int = 0
    provider_id: str = ""
    prefill_rate: float = 0.0
    decode_rate: float = 0.0
    #: One of `BINDING_CONSTRAINTS`, per deadline.
    total_bound_by: str = FROM_ESTIMATE
    ttft_bound_by: str = FROM_ESTIMATE
    itl_bound_by: str = FROM_ESTIMATE

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_class": self.request_class,
            "prompt_tokens": self.prompt_tokens,
            "expected_output_tokens": self.expected_output_tokens,
            "provider_id": self.provider_id,
            "prefill_rate": self.prefill_rate,
            "decode_rate": self.decode_rate,
            "total_bound_by": self.total_bound_by,
            "ttft_bound_by": self.ttft_bound_by,
            "itl_bound_by": self.itl_bound_by,
        }


@dataclass(frozen=True)
class CallBudget:
    """Three deadlines and the reasoning behind them.

    `total_deadline` and `ttft_deadline` are absolute monotonic instants.
    `itl_ms` is a **duration**, and deliberately so: it bounds the gap
    between consecutive tokens, which is a rolling measurement with no
    fixed point to anchor to. It is the one quantity in this system that
    is legitimately relative, because it is re-based by design on every
    token.

    `enforce_itl` is False for single-shot work. An embedding has no
    tokens to pace, so ITL is undefined rather than merely different, and
    an adapter must not start a heartbeat it can never feed.
    """

    total_deadline: float
    ttft_deadline: float
    itl_ms: float
    enforce_itl: bool = True
    derivation: Derivation = field(default_factory=Derivation)
    #: The same two budgets as durations, captured when the budget was
    #: built. Carried so a record can report "we allowed 300s" without
    #: also having to carry the monotonic instant it was measured from --
    #: a monotonic value is meaningless in a later process.
    total_ms: float = 0.0
    ttft_ms: float = 0.0

    def __post_init__(self) -> None:
        if self.ttft_deadline > self.total_deadline:
            # A first token that may arrive after the call must already be
            # over is not a budget, it is a contradiction -- and it would
            # make TIMED_OUT_TOTAL unreachable, hiding the distinction the
            # three deadlines exist to draw.
            raise ValueError(
                "ttft_deadline must not exceed total_deadline "
                f"({self.ttft_deadline} > {self.total_deadline})"
            )
        if self.itl_ms <= 0:
            raise ValueError(f"itl_ms must be positive, got {self.itl_ms}")

    # ---- what the adapter asks ------------------------------------------

    def total_remaining_ms(self, now: float) -> float:
        """Milliseconds until the whole call must be over. May be <= 0."""
        return (self.total_deadline - now) * 1000.0

    def ttft_remaining_ms(self, now: float) -> float:
        return (self.ttft_deadline - now) * 1000.0

    def total_expired(self, now: float) -> bool:
        return now >= self.total_deadline

    def ttft_expired(self, now: float) -> bool:
        return now >= self.ttft_deadline

    def stalled(self, last_token_at: float, now: float) -> bool:
        """Has decode gone quiet for longer than the budget allows?"""
        if not self.enforce_itl:
            return False
        return (now - last_token_at) * 1000.0 > self.itl_ms

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_ms": self.total_ms,
            "ttft_ms": self.ttft_ms,
            "itl_ms": self.itl_ms,
            "enforce_itl": self.enforce_itl,
            "derivation": self.derivation.as_dict(),
        }
