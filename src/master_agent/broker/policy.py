"""Founder policy, and the version stamped on every decision (MB031).

ADR-0018's central rule: **the decision procedure never learns; the
versioned policy it reads does.** So policy is data — a frozen object with
a version string — and the engine that reads it is fixed. A decision made
under `balanced/1` replays against `balanced/1` forever, whatever the
founder later prefers.

A policy can change the *order* candidates are ranked in. It can never
lower the quality floor below its own hard minimum, and it can never
authorise something the task's constraints forbid — MB031 Deliverable 8's
"never guess" is a property of the engine, not of any policy.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from master_agent.broker.profiles import CLOUD, DESKTOP, LOCAL

# ---- ranking keys -------------------------------------------------------
#
# What a policy sorts by *after* the hard filters and the quality floor
# have run. Named rather than numeric so a DecisionRecord says "ranked by
# cost", which a founder can read, instead of exposing weights nobody can
# audit (ADR-0017 Decision 3).

BY_COST = "cost"
BY_QUALITY = "quality"
BY_LATENCY = "latency"
BY_LOCALITY = "locality"
BY_PRIVACY = "privacy"
RANKING_KEYS = (BY_COST, BY_QUALITY, BY_LATENCY, BY_LOCALITY, BY_PRIVACY)

# There is deliberately NO blended "balanced" ranking key.
#
# The first draft had one -- quality divided by cost -- and a smoke run
# immediately showed why ADR-0017 Decision 3 rejected exactly that. Given
# a free local provider at quality 0.82 and a paid cloud one at 0.95, both
# clearing a 0.70 floor, the blend picked the paid one: at realistic
# per-call costs the denominator barely moves, so "balanced" quietly
# degenerated into "best quality" and overrode MB031 Deliverable 8's rule
# that the *lowest-cost* provider clearing the floor wins.
#
# What distinguishes the policies is therefore the FLOOR, not a secret
# weighting: `balanced` sets a higher bar than `lowest_cost` and then
# takes the cheapest that clears it. That is a sentence a founder can
# check against the record.

#: Locality order for `BY_LOCALITY`: on this machine first, then an
#: installed application, then someone else's computer.
_LOCALITY_ORDER = {LOCAL: 0, DESKTOP: 1, CLOUD: 2}


class UnknownRanking(Exception):
    pass


@dataclass(frozen=True)
class SelectionPolicy:
    """One founder policy. Frozen and versioned, so a decision made under
    it can always be reproduced.

    `hard_floor` is the floor beneath which this policy will not go even
    if a task asks it to. A task may raise the bar; nothing may lower it
    past here, which is what stops "just this once" from becoming the
    default (ADR-0018 Decision 5's cost-quality death spiral).
    """

    name: str
    version: str
    ranking: tuple[str, ...] = (BY_COST,)
    default_min_quality: float = 0.5
    hard_floor: float = 0.0
    allow_cloud: bool = True
    allow_paid: bool = True
    require_private_for_sensitive: bool = True
    description: str = ""

    @property
    def policy_version(self) -> str:
        """What lands on every DecisionRecord."""
        return f"{self.name}/{self.version}"

    def floor_for(self, requested: float | None) -> float:
        """The quality floor actually applied. A task may raise it; the
        policy's `hard_floor` is the bottom."""
        floor = self.default_min_quality if requested is None else requested
        return max(floor, self.hard_floor)

    def with_version(self, version: str) -> SelectionPolicy:
        return replace(self, version=version)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "policy_version": self.policy_version,
            "ranking": list(self.ranking),
            "default_min_quality": self.default_min_quality,
            "hard_floor": self.hard_floor,
            "allow_cloud": self.allow_cloud,
            "allow_paid": self.allow_paid,
            "require_private_for_sensitive": self.require_private_for_sensitive,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SelectionPolicy:
        return cls(
            name=data["name"],
            version=data["version"],
            ranking=tuple(data.get("ranking", (BY_COST,))),
            default_min_quality=data.get("default_min_quality", 0.5),
            hard_floor=data.get("hard_floor", 0.0),
            allow_cloud=data.get("allow_cloud", True),
            allow_paid=data.get("allow_paid", True),
            require_private_for_sensitive=data.get(
                "require_private_for_sensitive", True
            ),
            description=data.get("description", ""),
        )


# ---- the named policies MB031 asks for ----------------------------------

BALANCED = SelectionPolicy(
    name="balanced",
    version="1",
    ranking=(BY_COST, BY_QUALITY, BY_LATENCY),
    default_min_quality=0.6,
    description=(
        "a higher quality bar than lowest_cost, then the cheapest provider "
        "that clears it"
    ),
)

LOWEST_COST = SelectionPolicy(
    name="lowest_cost",
    version="1",
    ranking=(BY_COST, BY_QUALITY),
    default_min_quality=0.5,
    description="cheapest first, but still never below the quality floor",
)

BEST_QUALITY = SelectionPolicy(
    name="best_quality",
    version="1",
    ranking=(BY_QUALITY, BY_COST),
    default_min_quality=0.7,
    description="the best provider available, cost breaking ties",
)

PREFER_LOCAL = SelectionPolicy(
    name="prefer_local",
    version="1",
    ranking=(BY_LOCALITY, BY_COST, BY_QUALITY),
    default_min_quality=0.5,
    description="on this machine first, then installed applications, then cloud",
)

PREFER_FREE = SelectionPolicy(
    name="prefer_free",
    version="1",
    ranking=(BY_COST, BY_LOCALITY, BY_QUALITY),
    default_min_quality=0.5,
    allow_paid=False,
    description="free providers only",
)

OFFLINE_ONLY = SelectionPolicy(
    name="offline_only",
    version="1",
    ranking=(BY_LOCALITY, BY_QUALITY),
    default_min_quality=0.4,
    allow_cloud=False,
    description="nothing that needs the network",
)

CLOUD_ALLOWED = SelectionPolicy(
    name="cloud_allowed",
    version="1",
    ranking=(BY_COST, BY_QUALITY, BY_LATENCY),
    default_min_quality=0.6,
    description="the balanced policy, with cloud providers explicitly permitted",
)

PRIVACY_FIRST = SelectionPolicy(
    name="privacy_first",
    version="1",
    ranking=(BY_PRIVACY, BY_LOCALITY, BY_COST),
    default_min_quality=0.5,
    require_private_for_sensitive=True,
    description="private providers first; sensitive work never leaves the machine",
)

FAST_FREE = SelectionPolicy(
    name="fast_free",
    version="1",
    # Cost first, so nothing paid can win on speed. Then LATENCY, which is
    # the whole point of this policy and the one dimension `prefer_free`
    # never consults -- it ranks by locality, which is a proxy for cost
    # and privacy, not for how long the founder waits. Quality last, to
    # break ties among options that already clear the floor.
    ranking=(BY_COST, BY_LATENCY, BY_QUALITY),
    default_min_quality=0.6,
    allow_paid=False,
    require_private_for_sensitive=True,
    description=(
        "an interactive turn: the fastest free provider that clears an "
        "adequate quality bar, never a paid one"
    ),
)

POLICIES: dict[str, SelectionPolicy] = {
    policy.name: policy
    for policy in (
        BALANCED,
        LOWEST_COST,
        BEST_QUALITY,
        PREFER_LOCAL,
        PREFER_FREE,
        OFFLINE_ONLY,
        CLOUD_ALLOWED,
        PRIVACY_FIRST,
        FAST_FREE,
    )
}

DEFAULT_POLICY = BALANCED

#: Which policy an interactive turn is decided under.
#:
#: **This supersedes the strict locality ladder for simple work, on the
#: founder's explicit instruction, and it must not be "corrected" back.**
#:
#: `ai_infrastructure/tiered_runner.py` walked its locality tiers in a
#: fixed order and scoped the Broker to one of them at a time, so an
#: adequate fast provider could not win until every slower one had been
#: exhausted. Measured on a trivial public generation: desktop automation
#: ~74s serially, a healthy free cloud API ~5.4s, ~90s overall. That ordering
#: is right when the question is "what is cheapest and most private"; it
#: is wrong when the founder is waiting for three words.
#:
#: `interactive` therefore decides under FAST_FREE, which ranks free
#: options by latency. Every other class is unchanged and still decides
#: under whatever policy production configured -- planning included.
#:
#: Deliberately NOT an economics model: today `cost == 0` conflates a free
#: API, an installed subscription application and a local runtime, and
#: pretending otherwise here would be inventing measurements. `allow_paid`
#: is False so that conflation can never let a paid provider win on speed.
_POLICY_BY_REQUEST_CLASS: dict[str, SelectionPolicy] = {
    "interactive": FAST_FREE,
}


def policy_for_request_class(
    request_class: str | None, default: SelectionPolicy | None = None
) -> SelectionPolicy | None:
    """The policy an request of this workload class is decided under, or
    `default` when the class has no opinion.

    Lives here, with the policies, because it IS policy -- the mapping
    from "what kind of work is this" to "how do we choose" belongs beside
    the choices it names, never inside the runner that executes them.
    """
    if not request_class:
        return default
    return _POLICY_BY_REQUEST_CLASS.get(str(request_class).strip().lower(), default)


def get_policy(name: str) -> SelectionPolicy:
    policy = POLICIES.get((name or "").strip().lower())
    if policy is None:
        known = ", ".join(sorted(POLICIES))
        raise UnknownRanking(f"unknown policy '{name}' (known: {known})")
    return policy


def sort_key(ranking: str, provider: Any) -> tuple:
    """One ranking dimension as a sortable key, ascending.

    Every key is ascending-is-better so the caller can concatenate them
    without remembering which way each one runs — the sort direction being
    per-dimension is exactly the kind of detail that produces a subtly
    wrong ranking nobody notices.
    """
    quality = provider.effective_quality
    latency = provider.latency_ms if provider.latency_ms is not None else float("inf")

    if ranking == BY_COST:
        return (provider.cost,)
    if ranking == BY_QUALITY:
        return (-quality,)
    if ranking == BY_LATENCY:
        return (latency,)
    if ranking == BY_LOCALITY:
        return (_LOCALITY_ORDER.get(provider.locality, 99),)
    if ranking == BY_PRIVACY:
        return (0 if provider.privacy == "private" else 1,)
    raise UnknownRanking(f"unknown ranking '{ranking}' (known: {', '.join(RANKING_KEYS)})")


def ranking_key(policy: SelectionPolicy, provider: Any) -> tuple:
    """The full ordering for one provider under one policy.

    `provider_id` is always the final component. Without it, two providers
    that tie on every dimension would order by whatever the input list
    happened to be, and the same question would get different answers on
    different runs — which would make Deliverable 6 impossible.
    """
    key: tuple = ()
    for ranking in policy.ranking:
        key += sort_key(ranking, provider)
    return (*key, provider.provider_id)
