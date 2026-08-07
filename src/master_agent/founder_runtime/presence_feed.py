"""C19's coverage answer, in the vocabulary the Presence Layer already eats.

The Presence Layer (C20) is **push-fed**. Its own `observations.ts` says so
without hedging:

> *"This layer has no reach. It cannot call the Kernel, the Coordinator, the
> Runtime Bridge, a plugin or a tool... Everything it knows, it was told.
> `Observation` is the complete vocabulary of what it can be told."*

and its terminology-reconciliation list asks the question this module is the
answer to: *"Is the Presence Layer fed by the Coordinator, or expected to
pull? This implementation only accepts being fed — it cannot call anything."*

**It is fed. This is the feed.** Nothing here derives presence, calm,
vigilance state, activity or a snapshot — every one of those is C20's, and a
second implementation of any of them is the duplication C23 forbids.

## Transcription, not derivation

Two observation types are emitted and no others:

| Observation | Every field's source |
|---|---|
| `coverage.expected` | `Coverage.domains[].name`, stamped `Coverage.attested_at` |
| `coverage.reported` | one `DomainStatus`, stamped **its own** `lastChecked` |

No third type is emitted, because C19 has nothing to say about missions,
executions, approvals, actions, reasoning or failures. Emitting one of those
from a coverage answer would be inventing an observation, and an invented
observation is indistinguishable downstream from a real one.

## Why a never-checked domain gets no report

C20 sets `lastCheckedAt` from the observation's own `at` (`state.ts`,
`case 'coverage.reported'`). A domain C19 has never had a report for has no
such moment, so **no `coverage.reported` is emitted for it** — it appears in
`coverage.expected` alone, and C20's `deriveVigilance` turns that into a
`never-reported` gap.

That is the same sentence C19 already says, arriving by the route C20
already has: *"I haven't checked"* stays distinct from *"I checked and it is
old"*, which VEDA 04 §5 makes *"a data property, not a phrasing choice."*
Stamping a never-checked domain with the attestation moment would convert
the first sentence into the second, silently.

## Why the empty registry is refused rather than translated

C19 answers an empty registry with `complete=False` and one `Gap` whose
domain is `""` — *"no domain is being watched, so coverage proves nothing."*
That gap names no domain, because there is none to name.

Fed into C20 as `coverage.expected` with an empty list, the Presence Layer
would find no expected domains, no coverage records, **no gaps** — and
derive `complete: true`, from which `deriveCalm` produces *"Nothing needs
you."* over nothing at all. That is precisely the lie VEDA 04 D7 calls *"the
single failure most likely to end a customer relationship permanently."*

So this module emits **no observations** for a coverage with nothing
watched, and reports the absence with C19's own words instead. It does not
invent a placeholder domain to force a gap: a fabricated domain name would
reach a founder-facing line in `deriveVigilance`, and a lie told to prevent
a lie is still one.

**The underlying condition is not fixed here and cannot be** — an unfed
Presence Layer says *"Nothing needs you."* whether or not this module
exists. It is recorded as a finding in `Engineering/HEALTH_C23.md` and the
authoritative answer travels beside the feed: the envelope carries C19's own
`Coverage.as_dict()`, `complete` included, verbatim.

## Purity

No clock, no I/O, no randomness, no state. Every moment in every observation
was read from the `Coverage` it was given, and two calls with the same
`Coverage` return equal tuples.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from master_agent.vigilance import Coverage, DomainRegistry

#: The observation types this feed emits. A strict subset of C20's twelve,
#: because C19 is a coverage service and knows nothing else. Held as data so
#: a test can assert nothing outside it is ever produced.
PRESENCE_OBSERVATION_TYPES: tuple[str, ...] = (
    "coverage.expected",
    "coverage.reported",
)

#: C19's word for a coverage that proves nothing, carried rather than
#: composed. Matches `VigilanceAttestation.attest()`'s own gap detail.
NOTHING_WATCHED = (
    "no domain is being watched, so coverage proves nothing"
)


@dataclass(frozen=True)
class PresenceFeed:
    """Observations for the Presence Layer, or a stated reason there are none.

    Never both. An empty feed carrying no reason would be
    indistinguishable from a healthy system with nothing to report, and
    those are different facts.
    """

    #: In C20's own `Observation` shape, ready to hand to `observeAll`.
    observations: tuple[dict[str, Any], ...] = ()

    #: Why the feed is empty, in C19's words. `None` when it is not.
    absent_reason: str | None = None

    def __post_init__(self) -> None:
        if self.observations and self.absent_reason is not None:
            raise ValueError(
                "a feed either carries observations or says why it carries "
                "none; carrying both would let a consumer choose which to "
                "believe"
            )

    @property
    def fed(self) -> bool:
        return bool(self.observations)

    def as_dict(self) -> dict[str, Any]:
        """Deterministic, JSON-ready. Fixed key order."""
        return {
            "observations": [dict(obs) for obs in self.observations],
            "absent_reason": self.absent_reason,
        }


def presence_feed(
    coverage: Coverage, registry: DomainRegistry | None = None
) -> PresenceFeed:
    """Turn one `Coverage` into the observations C20 accepts.

    `registry` is optional and is read for one field only: a domain's
    `freshness_window`, which `Coverage` deliberately does not carry.
    Without it, `freshnessSeconds` is `null` and **C20 applies its own
    default** — that threshold is presentation policy and belongs to the
    layer that renders it, not to this one.

    A domain in the registry that the coverage does not name is ignored.
    The coverage is the answer; the registry is only asked to explain a
    window for a domain the answer already contains.
    """
    if not isinstance(coverage, Coverage):
        raise TypeError(
            "presence_feed takes the Coverage that VigilanceAttestation."
            "attest() returned; there is no other way to obtain one"
        )
    if registry is not None and not isinstance(registry, DomainRegistry):
        raise TypeError("registry must be a DomainRegistry, or omitted")

    if coverage.watched == 0:
        return PresenceFeed(absent_reason=NOTHING_WATCHED)

    at = coverage.attested_at.isoformat()
    windows = _freshness_windows(registry)

    observations: list[dict[str, Any]] = [
        {
            "type": "coverage.expected",
            "at": at,
            "domains": [status.name for status in coverage.domains],
        }
    ]

    for status in coverage.domains:
        if status.last_checked is None:
            # Never checked. It stays expected-but-unreported, which is the
            # `never-reported` gap C20 already draws and the `never_checked`
            # gap C19 already drew. Neither is invented here.
            continue
        observations.append(
            {
                "type": "coverage.reported",
                "at": status.last_checked.isoformat(),
                "domain": status.name,
                "healthy": status.healthy,
                "freshnessSeconds": windows.get(status.name),
            }
        )

    return PresenceFeed(observations=tuple(observations))


def _freshness_windows(
    registry: DomainRegistry | None,
) -> dict[str, float]:
    """Each registered domain's window, in whole-or-fractional seconds.

    C20's `freshnessSeconds` is a number; `timedelta.total_seconds()` is
    the value C19 already publishes in `Domain.as_dict()`, so the two
    agree without a conversion anyone has to remember.
    """
    if registry is None:
        return {}
    return {
        domain.name: domain.freshness_window.total_seconds()
        for domain in registry.domains()
    }
