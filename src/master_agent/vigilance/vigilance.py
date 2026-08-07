"""Vigilance Attestation — the proof that makes *"Nothing needs you"* honest.

VEDA 04 D7, and it is the requirement that document says it *"would most
want on the record"*:

> *"The sentence **'Nothing needs you'** is the product's highest-value
> claim and its greatest liability. It is only safe if it is **provably
> complete** — backed by a coverage check across every monitored domain
> confirming each was actually checked, within its freshness window,
> without error."*
>
> **Invariant:** *"if any domain is stale, unreachable or errored, the
> system may not say 'nothing needs you.' It must say what it could not
> check. A silent gap converts the product's core promise into a lie by
> omission, and it is the single failure most likely to end a customer
> relationship permanently."*

## The contract, frozen

VEDA 04 §4 gives the shape verbatim:

```
   attest() → {complete: bool, domains[{name, lastChecked, healthy}], gaps[]}
```

> **Obligations:** *"the 'nothing needs you' surface **must** call this and
> **must** honour a false result. **Consider enforcing at the type level —
> the calm-state message should be unconstructable without a complete
> attestation.**"*

Roadmap §2 C19 turns that suggestion into a requirement: *"the calm-state
string **must** be unconstructable without a complete attestation."*

**`CalmState` is that enforcement.** Its only field is the `Coverage` it
was proved by, and construction refuses an incomplete one. A surface
cannot hold the permission without holding the proof, and cannot obtain
the proof by asserting it.

This is the Kernel's own pattern one layer out — §1.3 One: *"Bypass is a
type error, not a policy violation."*

## `CalmState` carries no words

Not one sentence, not one fragment, not the phrase itself. §3.4 of the
Kernel Specification gives narration to D1 and Roadmap §2 C20 gives every
outbound utterance to the Voice Charter Validator; a component that
composed the calm sentence would be writing founder-facing prose in the
component whose job is to decide whether prose is *permitted*.

**It is a permission, not a message.** D1 writes the words, C20 validates
them, and neither can begin without one of these.

## Why zero domains is not calm

A registry with nothing in it has no gaps, and that is exactly the lie D7
describes. *"Provably complete"* over an empty set proves nothing, and
VEDA 04 §7 warns that cost control *"must come from prioritising by
consequence, not from reducing coverage — because reducing coverage
silently breaks D7."*

**So completeness requires at least one registered domain and no gaps.**
An empty registry is incomplete, and its gap says so.

## The three gaps, and where D7's words went

D7 names *"stale, unreachable or errored"*. The frozen contract carries
`healthy` as a **boolean**, so *unreachable* and *errored* both arrive as
`healthy=False` and are told apart by the connector's own `detail` — its
words, carried verbatim, never composed here.

| Gap | Meaning |
|---|---|
| `never_checked` | Registered, and no connector has ever reported |
| `stale` | The last report is outside the domain's freshness window |
| `unhealthy` | The connector reported, and said it was not healthy |

**A report stamped after the attestation moment is `stale`**, not fresh.
A timestamp ahead of the canonical clock is not evidence that a check
happened; treating it as evidence would let a connector claim permanent
freshness by getting its clock wrong. The conservative direction is the
only safe one here, because the failure mode of the other is the lie D7
exists to prevent.

**Freshness is closed at the far end**: an age equal to the window is
`stale`, following C4's `is_expired`, which treats the moment of expiry as
expired. Both choices refuse calm slightly earlier rather than slightly
later.

## Immutable, like every other registry here

`register()` and `report()` return a **new** `DomainRegistry`, following
C12's Reversibility Registry — *"never mutates"* — and C14's
`OverrideSwitch`. A coverage answer that could change under a holder's
feet is not proof of anything, and threading the registry is what makes
`attest()` a pure function of the registry and one clock reading.

## Dependencies

**C1's `Clock`, and nothing else.** Roadmap §2 C19: *"Depends on. C1 Clock
(freshness windows)."* This module imports no Kernel, no ledger, no
surface and no capability — freshness is arithmetic on two moments, and
that is the whole of what it needs.

Placed in `master_agent/vigilance/` rather than `foundation/`: that
package's door admits a module only if *"every layer above it needs it"*,
and it aggregates its exports in an `__init__` that three shipped
milestones have left byte-identical.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from master_agent.foundation.clock import Clock


class InvalidDomain(ValueError):
    """Raised at construction for a domain that could not be watched.

    At construction, never at attestation time. A domain registered
    wrongly would be counted as covered while covering nothing, which is
    the silent gap D7 names as fatal.
    """


class UnknownDomain(LookupError):
    """A report arrived for a domain nobody registered.

    Refused rather than absorbed. A connector reporting on a domain the
    registry does not know is either a typo or a domain nobody decided to
    watch, and silently accepting it would make coverage look wider than
    it was decided to be.
    """

    def __init__(self, name: str) -> None:
        super().__init__(
            f"{name!r} is not a registered domain; a report cannot widen "
            "coverage that nobody chose"
        )
        self.name = name


class VigilanceIncomplete(ValueError):
    """The calm state was reached for without the proof it requires.

    VEDA 04 D7's invariant, as a type error: *"if any domain is stale,
    unreachable or errored, the system may not say 'nothing needs you.'"*
    """


class GapKind(str, Enum):
    """Why a domain is not covered. Closed.

    D7 names *"stale, unreachable or errored"*. The frozen contract
    carries `healthy` as a boolean, so the last two arrive together as
    `unhealthy` and are told apart by the connector's own words. A fourth
    kind is a change to what coverage means.
    """

    #: Registered, and never reported on.
    NEVER_CHECKED = "never_checked"

    #: The last report is outside the freshness window — or is stamped
    #: after the attestation moment, which is not evidence of a check.
    STALE = "stale"

    #: The connector reported, and said it was not healthy.
    UNHEALTHY = "unhealthy"


@dataclass(frozen=True)
class Domain:
    """One thing being watched, and how often it must be. Immutable."""

    #: What is watched, in the founder's own terms. VEDA 04 §7 makes
    #: per-domain health *"a first-class product concept surfaced in the
    #: founder's own language."*
    name: str

    #: How old a check may be and still count. §5 makes freshness
    #: metadata mandatory — *"D7 cannot function otherwise."*
    freshness_window: timedelta

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise InvalidDomain("a domain must have a non-empty name")
        if not isinstance(self.freshness_window, timedelta):
            raise InvalidDomain("freshness_window must be a timedelta")
        if self.freshness_window <= timedelta(0):
            raise InvalidDomain(
                "freshness_window must be positive; a window of zero means "
                "no check is ever fresh, and a negative one means every "
                "check is"
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "freshness_window_seconds": self.freshness_window.total_seconds(),
        }


@dataclass(frozen=True)
class DomainReport:
    """What a connector said, carried verbatim. Immutable."""

    name: str

    #: When the check happened. Supplied from the canonical clock; this
    #: module reads none.
    checked_at: datetime

    #: The frozen contract's boolean. `False` covers D7's *unreachable*
    #: and *errored* alike; `detail` says which.
    healthy: bool

    #: The connector's own words. **Never composed here** — C20 owns
    #: every outbound utterance, and this is carried, not written.
    detail: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise InvalidDomain("a report must name its domain")
        if not isinstance(self.healthy, bool):
            raise InvalidDomain(
                "healthy must be True or False; a domain is either checked "
                "and well or it is a gap"
            )
        object.__setattr__(
            self, "checked_at", _as_utc(self.checked_at, "checked_at")
        )
        if self.detail is not None and (
            not isinstance(self.detail, str) or not self.detail.strip()
        ):
            raise InvalidDomain("detail is absent or says something")

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "checked_at": self.checked_at.isoformat(),
            "healthy": self.healthy,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class Gap:
    """What could not be checked, and why.

    D7: *"It must say what it could not check."* This is that sentence's
    data, and it names one domain each — a gap that could not say which
    domain it was about would be the silent gap by another route.
    """

    domain: str
    kind: GapKind

    #: When the domain was last checked, or `None` if never.
    last_checked: datetime | None = None

    #: The connector's own words, where it gave any.
    detail: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "kind": self.kind.value,
            "last_checked": (
                None if self.last_checked is None
                else self.last_checked.isoformat()
            ),
            "detail": self.detail,
        }


@dataclass(frozen=True)
class DomainStatus:
    """One element of the frozen contract's `domains[]`.

    VEDA 04 §4: `domains[{name, lastChecked, healthy}]`. Three fields,
    and the projection uses the contract's own key names.
    """

    name: str
    last_checked: datetime | None
    healthy: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "lastChecked": (
                None if self.last_checked is None
                else self.last_checked.isoformat()
            ),
            "healthy": self.healthy,
        }


@dataclass(frozen=True)
class Coverage:
    """The answer `attest()` returns. Immutable.

    Named for VEDA 04 D7's own phrase — *"a **coverage check** across
    every monitored domain"* — rather than `Attestation`, which C7 owns
    for §7.3's eight questions. Three unqualified attestations in one
    codebase is how a reader stops being able to tell which one spoke.
    """

    #: Whether the calm state is available. **False whenever there is any
    #: gap, and false when nothing is watched at all.**
    complete: bool

    domains: tuple[DomainStatus, ...]
    gaps: tuple[Gap, ...]

    #: The single moment every freshness comparison was made against.
    attested_at: datetime

    @property
    def watched(self) -> int:
        """How many domains were considered. Zero is never complete."""
        return len(self.domains)

    def as_dict(self) -> dict[str, Any]:
        """A deterministic, JSON-ready projection. Fixed key order."""
        return {
            "complete": self.complete,
            "domains": [item.as_dict() for item in self.domains],
            "gaps": [item.as_dict() for item in self.gaps],
            "attested_at": self.attested_at.isoformat(),
        }


@dataclass(frozen=True)
class CalmState:
    """Permission to say that nothing needs the founder.

    **Unconstructable without a complete `Coverage`** — Roadmap §2 C19,
    and VEDA 04 §4's *"the calm-state message should be unconstructable
    without a complete attestation."* The check runs at construction, so
    there is no validation step a caller can forget and no flag one can
    pass.

    It holds the proof rather than a copy of it, so an audit years later
    can see exactly which domains were fresh at the moment the claim was
    made.

    **It carries no words.** D1 writes the sentence and C20 validates it;
    this only says the sentence is allowed.
    """

    coverage: Coverage

    def __post_init__(self) -> None:
        if not isinstance(self.coverage, Coverage):
            raise VigilanceIncomplete(
                "the calm state is constructed from a Coverage and from "
                "nothing else; there is no other way to obtain one"
            )
        if not self.coverage.complete:
            raise VigilanceIncomplete(
                "coverage is incomplete, so 'nothing needs you' is "
                "unavailable: "
                + ", ".join(
                    f"{gap.domain} is {gap.kind.value}"
                    for gap in self.coverage.gaps
                )
            )

    @property
    def domains(self) -> tuple[str, ...]:
        """The domains this calm was proved over."""
        return tuple(item.name for item in self.coverage.domains)

    @property
    def attested_at(self) -> datetime:
        return self.coverage.attested_at

    def as_dict(self) -> dict[str, Any]:
        return {
            "domains": list(self.domains),
            "attested_at": self.attested_at.isoformat(),
        }


class DomainRegistry:
    """What is watched, and what each connector last said. Immutable.

    `register()` and `report()` each return a **new** registry, following
    C12 — *"never mutates"* — and C14's `OverrideSwitch`. A coverage
    answer that could change under a holder's feet would not be proof of
    anything.
    """

    __slots__ = ("_domains", "_reports")

    def __init__(
        self,
        domains: tuple[Domain, ...] = (),
        reports: tuple[DomainReport, ...] = (),
    ) -> None:
        by_name: dict[str, Domain] = {}
        for domain in domains:
            if not isinstance(domain, Domain):
                raise InvalidDomain("domains must be Domain values")
            if domain.name in by_name:
                raise InvalidDomain(
                    f"{domain.name!r} is registered twice; one domain has "
                    "one freshness window, or coverage means two things"
                )
            by_name[domain.name] = domain

        latest: dict[str, DomainReport] = {}
        for report in reports:
            if not isinstance(report, DomainReport):
                raise InvalidDomain("reports must be DomainReport values")
            if report.name not in by_name:
                raise UnknownDomain(report.name)
            latest[report.name] = report

        self._domains: dict[str, Domain] = by_name
        self._reports: dict[str, DomainReport] = latest

    # ---- transitions, each returning a new registry --------------------

    def register(self, domain: Domain) -> DomainRegistry:
        """Begin watching something. Returns a **new** registry."""
        return DomainRegistry(
            domains=(*self._domains.values(), domain),
            reports=tuple(self._reports.values()),
        )

    def report(self, report: DomainReport) -> DomainRegistry:
        """Record what a connector said. Returns a **new** registry.

        The latest report for a domain replaces the previous one: the
        contract carries `lastChecked`, so what matters is the most recent
        check rather than the history of them. The history is the receipt
        ledger's, and this is not it.
        """
        if not isinstance(report, DomainReport):
            raise InvalidDomain("report expects a DomainReport")
        if report.name not in self._domains:
            raise UnknownDomain(report.name)
        return DomainRegistry(
            domains=tuple(self._domains.values()),
            reports=(*self._reports.values(), report),
        )

    # ---- reading -------------------------------------------------------

    def domains(self) -> tuple[Domain, ...]:
        """Every registered domain, in registration order."""
        return tuple(self._domains.values())

    def last_report(self, name: str) -> DomainReport | None:
        """What the connector last said, or `None` if it never has."""
        return self._reports.get(name)

    def __len__(self) -> int:
        return len(self._domains)

    def __contains__(self, name: object) -> bool:
        return name in self._domains


@dataclass(frozen=True)
class VigilanceAttestation:
    """The service. One operation, and it decides one thing.

    VEDA 04 §4's `attest()` takes no arguments, so the registry and the
    clock are held rather than passed. Both are cheap: the registry is an
    immutable value and this wrapper exists to inject the one clock
    reading every comparison is made against.
    """

    registry: DomainRegistry
    clock: Clock = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.registry, DomainRegistry):
            raise InvalidDomain("registry must be a DomainRegistry")
        if not isinstance(self.clock, Clock):
            raise InvalidDomain(
                "clock must satisfy the canonical Clock protocol; freshness "
                "is a comparison against one moment and nothing here reads "
                "an ambient one"
            )

    def attest(self) -> Coverage:
        """`{complete, domains[], gaps[]}`, per VEDA 04 §4.

        **The clock is read once**, and every freshness comparison is made
        against that one moment — so no two domains in a single answer can
        be judged against different nows.

        Completeness requires **at least one domain and no gaps**. An
        empty registry proves nothing, and *"provably complete"* over
        nothing is the silent gap D7 names as fatal.
        """
        now = self.clock.now()
        statuses: list[DomainStatus] = []
        gaps: list[Gap] = []

        for domain in self.registry.domains():
            report = self.registry.last_report(domain.name)
            gap = _gap_for(domain, report, now)
            if gap is not None:
                gaps.append(gap)
            statuses.append(
                DomainStatus(
                    name=domain.name,
                    last_checked=None if report is None else report.checked_at,
                    healthy=bool(report is not None and report.healthy),
                )
            )

        if not statuses:
            gaps.append(
                Gap(
                    domain="",
                    kind=GapKind.NEVER_CHECKED,
                    detail=(
                        "no domain is being watched, so coverage proves "
                        "nothing"
                    ),
                )
            )

        return Coverage(
            complete=bool(statuses) and not gaps,
            domains=tuple(statuses),
            gaps=tuple(gaps),
            attested_at=now,
        )


def _gap_for(
    domain: Domain, report: DomainReport | None, now: datetime
) -> Gap | None:
    """Why this domain is not covered, or `None` if it is.

    Order matters: a domain that was never checked is reported as never
    checked, not as stale, because *"I haven't checked"* and *"I checked
    and it is old"* are different sentences — VEDA 04 §5 makes that
    distinction *"a data property, not a phrasing choice."*
    """
    if report is None:
        return Gap(domain=domain.name, kind=GapKind.NEVER_CHECKED)

    if now - report.checked_at >= domain.freshness_window:
        return Gap(
            domain=domain.name,
            kind=GapKind.STALE,
            last_checked=report.checked_at,
            detail=report.detail,
        )

    if report.checked_at > now:
        return Gap(
            domain=domain.name,
            kind=GapKind.STALE,
            last_checked=report.checked_at,
            detail=(
                "the report is stamped after the attestation moment, which "
                "is not evidence that a check happened"
            ),
        )

    if not report.healthy:
        return Gap(
            domain=domain.name,
            kind=GapKind.UNHEALTHY,
            last_checked=report.checked_at,
            detail=report.detail,
        )

    return None


def _as_utc(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise InvalidDomain(f"{field_name} must be a datetime")
    if value.tzinfo is None:
        raise InvalidDomain(
            f"{field_name} must be timezone-aware; every moment in "
            "Kalpavriksha comes from the canonical clock and is aware"
        )
    return value.astimezone(UTC)
