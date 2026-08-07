"""What a provider execution *is* (Mission Brief 033).

The vocabulary every provider answers in, and the only module in this
package the AI Infrastructure layer is allowed to import. Pure data: no
transport, no client, no network — so recording an execution never drags a
network stack into the layer that records it.

**A provider never raises for an operational failure.** Ollama being down,
a model not being installed, a request timing out, a body that is not the
JSON it claimed to be — all of those are *answers*, returned as a
`ProviderResult` with a reason a founder can act on. MB033 Rule 5 states
the consequence that matters: a failure is returned, never silently
substituted, because **only the Broker may choose a different provider**.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---- outcomes -----------------------------------------------------------
#
# One value per thing a founder would do differently. "It didn't work" is
# not an outcome anybody can act on; "the model is not installed on this
# machine, and here are the ones that are" is.

SUCCEEDED = "succeeded"
#: Nothing is listening. The daemon is not running, or not at that address.
UNAVAILABLE = "unavailable"
#: It answered, eventually, but not inside the time allowed.
TIMED_OUT = "timed_out"
#: It answered with something that is not the shape it promised.
MALFORMED = "malformed_response"
#: It answered, and the answer was a refusal (an HTTP error, a missing
#: model). Distinct from `UNAVAILABLE`: the provider is *there*.
REJECTED = "rejected"

# MB038. `TIMED_OUT` said only "too slow", which is three different
# failures with three different fixes wearing one name. These say which:
#
#   TTFT  -- nothing ever arrived. The prompt was too big for the window,
#            or the daemon is wedged. Fix: measure, or raise the class
#            ceiling.
#   ITL   -- it was producing and went quiet. The provider stalled
#            mid-answer. Fix: look at the provider, not the budget.
#   TOTAL -- it produced steadily and did not finish in time. Genuinely
#            too slow for the work. Fix: a bigger budget, or less work.
#
# `TIMED_OUT` stays in the vocabulary: it is what a non-streaming provider
# produces, where the three cannot be told apart, and what pre-MB038
# records already contain.
TIMED_OUT_TTFT = "timed_out_ttft"
TIMED_OUT_ITL = "timed_out_itl"
TIMED_OUT_TOTAL = "timed_out_total"

#: MB038. The caller stopped waiting — a mission was aborted, or the
#: founder said stop. Distinct from every timeout above: a timeout means
#: the *budget* ran out, and this means somebody withdrew the question.
#: Recording them the same would make a founder's decision look like a
#: provider's failure in every future average.
CANCELLED = "cancelled"

TIMEOUTS = (TIMED_OUT, TIMED_OUT_TTFT, TIMED_OUT_ITL, TIMED_OUT_TOTAL)

OUTCOMES = (
    SUCCEEDED,
    UNAVAILABLE,
    TIMED_OUT,
    TIMED_OUT_TTFT,
    TIMED_OUT_ITL,
    TIMED_OUT_TOTAL,
    CANCELLED,
    MALFORMED,
    REJECTED,
)
FAILURES = tuple(outcome for outcome in OUTCOMES if outcome != SUCCEEDED)


@dataclass(frozen=True)
class ProviderResponse:
    """One completed generation, and what it cost in time and tokens.

    Token counts are `None` when the provider did not report them, never
    `0`. MB033 Rule 3 asks for "estimated tokens (if available)", and the
    parenthesis is load-bearing: a zero that means "unreported" would make
    every future average wrong, quietly (ADR-0016).
    """

    text: str
    model: str = ""
    latency_ms: float = 0.0
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    finish_reason: str = ""

    @property
    def total_tokens(self) -> int | None:
        """`None` unless both halves were reported. Adding an unreported
        half to a reported one would produce a number that looks like a
        measurement and is not."""
        if self.prompt_tokens is None or self.completion_tokens is None:
            return None
        return self.prompt_tokens + self.completion_tokens

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "finish_reason": self.finish_reason,
        }


@dataclass(frozen=True)
class ProviderResult:
    """The answer to "did this run, and what happened".

    `response` is set exactly when `outcome` is `SUCCEEDED`. There is no
    third state and no partial success — a caller that has to inspect a
    string to find out whether it has an answer will eventually forget to.
    """

    provider_id: str
    outcome: str
    response: ProviderResponse | None = None
    error: str = ""
    #: Transport attempts made. 1 means it worked first time.
    attempts: int = 1
    #: Wall-clock across every attempt, including the failed ones — which
    #: is what the founder actually waited.
    latency_ms: float = 0.0
    #: Anything a founder needs in order to fix it: the models that *are*
    #: installed, the address that was tried, the status code.
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.outcome == SUCCEEDED

    @property
    def text(self) -> str:
        return self.response.text if self.response is not None else ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "outcome": self.outcome,
            "ok": self.ok,
            "error": self.error,
            "attempts": self.attempts,
            "latency_ms": self.latency_ms,
            "detail": dict(self.detail),
            "response": self.response.as_dict() if self.response else None,
        }


@dataclass(frozen=True)
class Availability:
    """Whether a provider could serve a request *right now*, and what it
    has to serve it with.

    This is a **fact about the transport**, not a judgement: it reports
    what the daemon said it holds. Choosing among them is the Broker's,
    and nothing in this package ranks or prefers (MB033 Rule 4).
    """

    provider_id: str
    reachable: bool
    models: tuple[str, ...] = ()
    detail: str = ""

    def has(self, model: str) -> bool:
        """Exact name, or the same name without an explicit `:latest`,
        because a founder writing `gemma4` and a daemon reporting
        `gemma4:latest` mean the same thing."""
        wanted = (model or "").strip()
        if not wanted:
            return False
        candidates = {wanted, f"{wanted}:latest"}
        return any(
            held in candidates or held.split(":", 1)[0] == wanted.split(":", 1)[0]
            for held in self.models
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "reachable": self.reachable,
            "models": list(self.models),
            "detail": self.detail,
        }


def failure(
    provider_id: str,
    outcome: str,
    error: str,
    attempts: int = 1,
    latency_ms: float = 0.0,
    **detail: Any,
) -> ProviderResult:
    """A failed result, built in one line so no provider is tempted to
    invent its own failure shape."""
    return ProviderResult(
        provider_id=provider_id,
        outcome=outcome,
        error=error,
        attempts=attempts,
        latency_ms=latency_ms,
        detail=detail,
    )
