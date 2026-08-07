"""The Token Economy (Mission Brief 033).

> Kalpavriksha must behave like an experienced engineer protecting the
> Founder's quota.

This module counts. It does not optimise, rank, or advise — those would be
decisions, and decisions belong to the Broker. What it produces is the
evidence a later brief needs in order to make the loop ADR-0018 designed
actually learn something.

## The rule that shapes every number here

> Do NOT estimate imaginary savings. Only count executions that actually
> occurred.

So there is no counterfactual anywhere in this file. In particular,
`money_saved` is **not** "what the frontier model would have cost if we
had used it" — that number is unfalsifiable, always flattering, and would
grow fastest on the days Kalpavriksha did the least. It is instead the
recorded cost of executions that genuinely happened once and were then
**reused from cache instead of repeated**. If nothing was reused, the
saving is zero and the panel says zero.

The same discipline applies to `avoided_cloud_executions`: a cache hit
whose original execution was on a cloud provider is one cloud call that
did not happen, and it is counted only because the first one is on the
record with its cost attached.

**Everything is zero in this build, and that is the correct answer.** The
Prompt Cache ships as `NullPromptCache` and nothing verifies generated
text, so nothing is ever stored and nothing is ever reused. `basis` says
so out loud rather than leaving a founder to infer it from a row of
zeroes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from master_agent.ai_infrastructure.ledger import CACHE_HIT, DecisionEntry

#: Localities that mean "this ran on someone else's computer". Mirrors
#: `broker.profiles`; a test asserts the two have not drifted.
CLOUD = "cloud"
LOCAL_LOCALITIES = ("local", "desktop")

NOTHING_YET = "no AI work has run yet"
#: MB035 built the verifier this used to blame, so the message now names
#: the condition that is actually outstanding: a cached answer needs an
#: `ExpectedOutcome` stated in advance, and a caller that asks for nothing
#: gets nothing remembered.
NO_CACHE = (
    "nothing has been reused yet: only an answer verified against an "
    "expected outcome is ever cached, so requests that ask for nothing "
    "specific are never stored"
)
COUNTED = "counted from executions that actually happened"


@dataclass(frozen=True)
class TokenEconomy:
    """What the founder's quota has actually been spent on.

    Every field is a count or a sum over recorded executions. There is no
    projection, no rate, and no estimate.
    """

    local_executions: int = 0
    cloud_executions: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    avoided_cloud_executions: int = 0
    money_saved: float = 0.0
    #: What was actually spent — the sum of recorded cost on executions
    #: that contacted a provider and succeeded.
    total_spend: float = 0.0
    failed_executions: int = 0
    #: `None`, not 0, when no provider reported token counts.
    total_tokens: int | None = None
    total_latency_ms: float = 0.0
    basis: str = NOTHING_YET

    @property
    def total_executions(self) -> int:
        return self.local_executions + self.cloud_executions

    @property
    def cache_hit_rate(self) -> float | None:
        """`None` when nothing has been looked up. A hit rate over zero
        lookups is 0/0, and rendering it as 0% would read as "the cache is
        useless" rather than "the cache has not been asked"."""
        looked_up = self.cache_hits + self.cache_misses
        if looked_up == 0:
            return None
        return self.cache_hits / looked_up

    @property
    def local_share(self) -> float | None:
        """The number this whole brief is about: how much of the thinking
        stayed free. `None` until something has run."""
        if self.total_executions == 0:
            return None
        return self.local_executions / self.total_executions

    def as_dict(self) -> dict[str, Any]:
        return {
            "local_executions": self.local_executions,
            "cloud_executions": self.cloud_executions,
            "total_executions": self.total_executions,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": self.cache_hit_rate,
            "avoided_cloud_executions": self.avoided_cloud_executions,
            "money_saved": self.money_saved,
            "total_spend": self.total_spend,
            "failed_executions": self.failed_executions,
            "total_tokens": self.total_tokens,
            "total_latency_ms": self.total_latency_ms,
            "local_share": self.local_share,
            "basis": self.basis,
        }


def summarise(entries: tuple[DecisionEntry, ...] | list[DecisionEntry]) -> TokenEconomy:
    """Total up a ledger. A pure function of what is on the record.

    Deliberately recomputed from the ledger rather than maintained as a
    running counter: a counter and a ledger eventually disagree, and when
    they do, the counter is the one that gets believed because it is the
    one on the screen.
    """
    local = cloud = hits = misses = failed = 0
    saved = spend = latency = 0.0
    tokens: int | None = None

    for entry in entries:
        execution = entry.execution
        if execution is None:
            continue

        if execution.cache == "hit":
            hits += 1
        elif execution.cache == "miss":
            misses += 1

        if execution.latency_ms:
            latency += execution.latency_ms
        if execution.total_tokens is not None:
            tokens = (tokens or 0) + execution.total_tokens

        if execution.outcome == CACHE_HIT:
            # Reuse is not an execution. It is the absence of one, which is
            # the entire point of counting it separately.
            if execution.locality == CLOUD:
                saved += execution.cost or 0.0
            continue

        if not execution.succeeded:
            failed += 1
            continue

        if execution.locality == CLOUD:
            cloud += 1
            spend += execution.cost or 0.0
        else:
            local += 1
            # A local execution's recorded cost is 0.0. Added anyway rather
            # than assumed, so a future non-free local provider is counted
            # without anyone having to remember this line exists.
            spend += execution.cost or 0.0

    avoided = sum(
        1
        for entry in entries
        if entry.execution is not None
        and entry.execution.outcome == CACHE_HIT
        and entry.execution.locality == CLOUD
    )

    return TokenEconomy(
        local_executions=local,
        cloud_executions=cloud,
        cache_hits=hits,
        cache_misses=misses,
        avoided_cloud_executions=avoided,
        money_saved=saved,
        total_spend=spend,
        failed_executions=failed,
        total_tokens=tokens,
        total_latency_ms=latency,
        basis=_basis(local + cloud + hits, hits),
    )


def _basis(anything: int, hits: int) -> str:
    """Say which of the three states these numbers are in, so a row of
    zeroes is never ambiguous between "nothing ran", "nothing was reused",
    and "this is real"."""
    if anything == 0:
        return NOTHING_YET
    if hits == 0:
        return NO_CACHE
    return COUNTED
