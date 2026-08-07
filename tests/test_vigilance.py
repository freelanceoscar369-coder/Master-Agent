"""Sprint 1, Component 19 — the Vigilance Attestation.

VEDA 04 D7 — the requirement that document says it *"would most want on
the record"*:

> *"'Nothing needs you' is the product's highest-value claim and its
> greatest liability. It is only safe if it is **provably complete**."*
>
> **Invariant:** *"if any domain is stale, unreachable or errored, the
> system may not say 'nothing needs you.' It must say what it could not
> check."*

| Source | Requirement |
|---|---|
| VEDA 04 D7 | The invariant, and *"it must say what it could not check"* |
| VEDA 04 §4 | `attest() → {complete, domains[{name, lastChecked, healthy}], gaps[]}` |
| VEDA 04 §4 | *"unconstructable without a complete attestation"* |
| VEDA 04 §5 | Freshness metadata is mandatory; *I don't know* ≠ *I haven't checked* |
| VEDA 04 §7 | *"The system says which domain it stopped watching"* |
| VEDA 04 F7 | *"Nothing needs you" is unavailable while coverage is incomplete* |
| Roadmap §2 C19 | `register / report` · `attest()`; depends on C1 only |
| Roadmap §2 C20 | Every outbound utterance is the Voice Charter Validator's |

The clock is a `ManualClock` in every test: freshness is a comparison
against a moment, and a test whose result depends on when it runs is not
a test.
"""
from __future__ import annotations

import ast
import inspect
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from master_agent.foundation.clock import Clock, ManualClock
from master_agent.vigilance import (
    CalmState,
    Coverage,
    Domain,
    DomainRegistry,
    DomainReport,
    DomainStatus,
    Gap,
    GapKind,
    InvalidDomain,
    UnknownDomain,
    VigilanceAttestation,
    VigilanceIncomplete,
)

SRC = Path(__file__).resolve().parent.parent / "src" / "master_agent"
MODULE = SRC / "vigilance" / "vigilance.py"

T0 = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
WINDOW = timedelta(minutes=15)


def registry(*names: str, window: timedelta = WINDOW) -> DomainRegistry:
    built = DomainRegistry()
    for name in names or ("inbox",):
        built = built.register(Domain(name, window))
    return built


def healthy(name: str = "inbox", at: datetime = T0) -> DomainReport:
    return DomainReport(name=name, checked_at=at, healthy=True)


def attest(
    built: DomainRegistry, clock: ManualClock | None = None
) -> Coverage:
    return VigilanceAttestation(built, clock or ManualClock(T0)).attest()


def covered(*names: str) -> Coverage:
    """A registry whose every domain is fresh and healthy."""
    built = registry(*names)
    for domain in built.domains():
        built = built.report(healthy(domain.name))
    return attest(built)


def _module_imports() -> list[str]:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    return imported


# ======================================================================
# The contract VEDA 04 §4 froze
# ======================================================================


def test_attest_returns_the_frozen_shape() -> None:
    """`{complete: bool, domains[{name, lastChecked, healthy}], gaps[]}`."""
    projection = covered().as_dict()

    assert set(projection) == {"complete", "domains", "gaps", "attested_at"}
    assert isinstance(projection["complete"], bool)
    assert set(projection["domains"][0]) == {"name", "lastChecked", "healthy"}


def test_the_domain_keys_are_the_contracts_own() -> None:
    """`lastChecked`, not `last_checked`. A frozen contract's spelling is
    part of the contract."""
    assert "lastChecked" in covered().as_dict()["domains"][0]


def test_attest_takes_no_argument() -> None:
    """VEDA 04 §4 — `attest()`. The registry and the clock are held."""
    assert list(inspect.signature(VigilanceAttestation.attest).parameters) == [
        "self"
    ]


def test_the_registry_surface_is_register_and_report() -> None:
    """Roadmap §2 C19 — `DomainRegistry.register / report`."""
    surface = {n for n in dir(DomainRegistry) if not n.startswith("_")}
    assert {"register", "report"} <= surface


def test_every_answer_serialises() -> None:
    """C21 will read these, and a projection that cannot cross JSON is
    not one."""
    for value in (covered(), attest(registry())):
        encoded = json.dumps(value.as_dict(), sort_keys=False)
        assert json.loads(encoded)["complete"] == value.complete


# ======================================================================
# Complete coverage
# ======================================================================


def test_one_fresh_healthy_domain_is_complete() -> None:
    coverage = covered()
    assert coverage.complete
    assert coverage.gaps == ()
    assert coverage.watched == 1


def test_many_fresh_healthy_domains_are_complete() -> None:
    coverage = covered("inbox", "calendar", "billing")
    assert coverage.complete
    assert [d.name for d in coverage.domains] == [
        "inbox", "calendar", "billing"
    ]


def test_a_complete_answer_names_every_domain_it_covered() -> None:
    """D7 — *"a coverage check across **every** monitored domain."*"""
    coverage = covered("inbox", "calendar")
    assert {d.name for d in coverage.domains} == {"inbox", "calendar"}
    assert all(d.healthy for d in coverage.domains)
    assert all(d.last_checked == T0 for d in coverage.domains)


# ======================================================================
# The invariant — every way coverage breaks
# ======================================================================


def test_a_never_checked_domain_is_a_gap() -> None:
    """VEDA 04 §5 — *I don't know* and *I haven't checked* are different
    sentences, and the distinction is *"a data property, not a phrasing
    choice."*"""
    coverage = attest(registry())

    assert not coverage.complete
    (gap,) = coverage.gaps
    assert gap.kind is GapKind.NEVER_CHECKED
    assert gap.domain == "inbox"
    assert gap.last_checked is None


def test_a_stale_domain_is_a_gap() -> None:
    clock = ManualClock(T0)
    built = registry().report(healthy())
    clock.advance(WINDOW + timedelta(seconds=1))

    coverage = attest(built, clock)
    assert not coverage.complete
    (gap,) = coverage.gaps
    assert gap.kind is GapKind.STALE
    assert gap.last_checked == T0


def test_an_unhealthy_domain_is_a_gap() -> None:
    """D7's *unreachable* and *errored* both arrive as `healthy=False`,
    because the frozen contract carries a boolean."""
    built = registry().report(
        DomainReport("inbox", T0, False, "the mail server refused the socket")
    )

    coverage = attest(built)
    assert not coverage.complete
    (gap,) = coverage.gaps
    assert gap.kind is GapKind.UNHEALTHY
    assert gap.detail == "the mail server refused the socket"


def test_one_gap_among_many_healthy_domains_breaks_completeness() -> None:
    """*"If **any** domain is stale, unreachable or errored."* One is
    enough, and that is the whole point."""
    built = registry("inbox", "calendar", "billing")
    built = built.report(healthy("inbox")).report(healthy("calendar"))

    coverage = attest(built)
    assert not coverage.complete
    assert [g.domain for g in coverage.gaps] == ["billing"]
    assert coverage.watched == 3


def test_every_gap_is_named() -> None:
    """D7 — *"It must say what it could not check."* A gap that could not
    say which domain it was about is the silent gap by another route."""
    clock = ManualClock(T0)
    built = registry("inbox", "calendar", "billing")
    built = built.report(healthy("inbox")).report(
        DomainReport("calendar", T0, False, "token expired")
    )
    clock.advance(WINDOW + timedelta(seconds=1))

    coverage = attest(built, clock)
    named = {(g.domain, g.kind) for g in coverage.gaps}
    assert named == {
        ("inbox", GapKind.STALE),
        ("calendar", GapKind.STALE),
        ("billing", GapKind.NEVER_CHECKED),
    }


def test_a_gap_carries_the_connectors_own_words() -> None:
    """Carried verbatim, never composed. C20 owns every utterance."""
    built = registry().report(
        DomainReport("inbox", T0, False, "OAuth token expired on Tuesday")
    )
    (gap,) = attest(built).gaps
    assert gap.detail == "OAuth token expired on Tuesday"


def test_the_gap_vocabulary_is_closed() -> None:
    """A fourth kind is a change to what coverage means."""
    assert {k.value for k in GapKind} == {
        "never_checked", "stale", "unhealthy"
    }


# ======================================================================
# Zero domains is not calm
# ======================================================================


def test_an_empty_registry_is_not_complete() -> None:
    """*"Provably complete"* over nothing proves nothing, and an empty
    registry has no gaps to notice."""
    coverage = attest(DomainRegistry())

    assert not coverage.complete
    assert coverage.watched == 0
    assert coverage.gaps


def test_an_empty_registry_says_why() -> None:
    (gap,) = attest(DomainRegistry()).gaps
    assert "no domain is being watched" in gap.detail


def test_an_empty_registry_cannot_reach_the_calm_state() -> None:
    """The adversarial case: watch nothing, find no gaps, claim calm."""
    with pytest.raises(VigilanceIncomplete):
        CalmState(attest(DomainRegistry()))


def test_dropping_the_last_domain_does_not_produce_calm() -> None:
    """VEDA 04 §7 — *"reducing coverage silently breaks D7."*"""
    assert covered().complete
    assert not attest(DomainRegistry()).complete


# ======================================================================
# The calm state is unconstructable without proof
# ======================================================================


def test_a_complete_coverage_permits_the_calm_state() -> None:
    calm = CalmState(covered())
    assert calm.domains == ("inbox",)
    assert calm.attested_at == T0


@pytest.mark.parametrize(
    "broken",
    [
        "never_checked",
        "stale",
        "unhealthy",
        "empty",
    ],
)
def test_no_incomplete_coverage_permits_the_calm_state(broken: str) -> None:
    """VEDA 04 F7 — *"'Nothing needs you' is unavailable while coverage is
    incomplete."* Every way coverage breaks, checked."""
    clock = ManualClock(T0)
    if broken == "empty":
        coverage = attest(DomainRegistry())
    elif broken == "never_checked":
        coverage = attest(registry())
    elif broken == "unhealthy":
        coverage = attest(
            registry().report(DomainReport("inbox", T0, False, "down"))
        )
    else:
        built = registry().report(healthy())
        clock.advance(WINDOW + timedelta(seconds=1))
        coverage = attest(built, clock)

    with pytest.raises(VigilanceIncomplete):
        CalmState(coverage)


def test_the_refusal_says_which_domains_broke_it() -> None:
    """A refusal that could not say what was missing would leave the
    founder exactly as uninformed as a silent gap."""
    built = registry("inbox", "calendar")
    built = built.report(DomainReport("calendar", T0, False, "down"))

    with pytest.raises(VigilanceIncomplete) as caught:
        CalmState(attest(built))
    assert "inbox is never_checked" in str(caught.value)
    assert "calendar is unhealthy" in str(caught.value)


def test_the_calm_state_cannot_be_built_from_an_assertion() -> None:
    """There is no second constructor, no flag, and no way to hand it
    anything but a `Coverage`."""
    for bogus in (None, True, "complete", {"complete": True}, object()):
        with pytest.raises(VigilanceIncomplete):
            CalmState(bogus)  # type: ignore[arg-type]

    assert list(inspect.signature(CalmState).parameters) == ["coverage"]


def test_the_calm_state_cannot_be_built_from_a_forged_coverage() -> None:
    """A caller can construct a `Coverage` — it is a value — but not one
    that says complete while carrying gaps, because the gate reads
    `complete` and the attestation is what sets it."""
    forged = Coverage(
        complete=False,
        domains=(DomainStatus("inbox", T0, True),),
        gaps=(Gap("inbox", GapKind.STALE),),
        attested_at=T0,
    )
    with pytest.raises(VigilanceIncomplete):
        CalmState(forged)


def test_the_calm_state_holds_its_proof() -> None:
    """It carries the `Coverage` rather than a copy, so an audit years
    later sees exactly which domains were fresh when the claim was
    made."""
    coverage = covered("inbox", "calendar")
    calm = CalmState(coverage)

    assert calm.coverage is coverage
    assert calm.domains == ("inbox", "calendar")


def test_the_calm_state_is_immutable() -> None:
    from dataclasses import FrozenInstanceError

    calm = CalmState(covered())
    with pytest.raises(FrozenInstanceError):
        calm.coverage = None


def test_the_calm_state_carries_no_words() -> None:
    """Roadmap §2 C20 gives every outbound utterance to the Voice Charter
    Validator, and §3.4 gives narration to D1. A component that composed
    the calm sentence would be writing prose in the component whose job
    is to decide whether prose is permitted."""
    calm = CalmState(covered())
    rendered = json.dumps(calm.as_dict())

    for phrase in ("nothing needs you", "Nothing needs you", "all clear"):
        assert phrase not in rendered
    source = MODULE.read_text(encoding="utf-8")
    body = source.split('"""', 2)[2]
    assert "Nothing needs you" not in body


# ======================================================================
# Freshness — the boundary, and the directions it fails in
# ======================================================================


def test_a_check_inside_the_window_is_fresh() -> None:
    clock = ManualClock(T0)
    built = registry().report(healthy())
    clock.advance(WINDOW - timedelta(seconds=1))

    assert attest(built, clock).complete


def test_the_window_is_closed_at_the_far_end() -> None:
    """An age exactly equal to the window is stale, following C4's
    `is_expired`, which treats the moment of expiry as expired. Both
    refuse calm slightly earlier rather than slightly later."""
    clock = ManualClock(T0)
    built = registry().report(healthy())
    clock.advance(WINDOW)

    coverage = attest(built, clock)
    assert not coverage.complete
    assert coverage.gaps[0].kind is GapKind.STALE


def test_a_report_from_the_future_is_not_fresh() -> None:
    """A timestamp ahead of the canonical clock is not evidence that a
    check happened. Treating it as evidence would let a connector claim
    permanent freshness by getting its clock wrong."""
    built = registry().report(healthy(at=T0 + timedelta(hours=1)))

    coverage = attest(built)
    assert not coverage.complete
    assert coverage.gaps[0].kind is GapKind.STALE
    assert "after the attestation moment" in coverage.gaps[0].detail


def test_each_domain_is_judged_against_its_own_window() -> None:
    clock = ManualClock(T0)
    built = DomainRegistry()
    built = built.register(Domain("inbox", timedelta(minutes=5)))
    built = built.register(Domain("billing", timedelta(days=1)))
    built = built.report(healthy("inbox")).report(healthy("billing"))
    clock.advance(timedelta(minutes=10))

    coverage = attest(built, clock)
    assert [g.domain for g in coverage.gaps] == ["inbox"]


def test_a_fresh_check_replaces_a_stale_one() -> None:
    """The contract carries `lastChecked`, so what matters is the most
    recent check rather than the history of them."""
    clock = ManualClock(T0)
    built = registry().report(healthy())
    clock.advance(WINDOW + timedelta(seconds=1))
    assert not attest(built, clock).complete

    built = built.report(healthy(at=clock.now()))
    assert attest(built, clock).complete


def test_an_unhealthy_check_replaces_a_healthy_one() -> None:
    built = registry().report(healthy())
    assert attest(built).complete

    built = built.report(DomainReport("inbox", T0, False, "went down"))
    assert not attest(built).complete


def test_staleness_is_reported_before_unhealthiness() -> None:
    """An old failure is first of all old: the freshest thing known about
    the domain is outside its window, and saying it is unhealthy would
    claim knowledge the window says is expired."""
    clock = ManualClock(T0)
    built = registry().report(DomainReport("inbox", T0, False, "was down"))
    clock.advance(WINDOW + timedelta(seconds=1))

    (gap,) = attest(built, clock).gaps
    assert gap.kind is GapKind.STALE


# ======================================================================
# Determinism
# ======================================================================


def test_the_clock_is_read_once_per_attestation() -> None:
    """No two domains in one answer may be judged against different
    nows."""
    reads: list[datetime] = []

    class CountingClock(ManualClock):
        def now(self) -> datetime:
            reads.append(super().now())
            return reads[-1]

    built = registry("inbox", "calendar", "billing")
    for domain in built.domains():
        built = built.report(healthy(domain.name))

    VigilanceAttestation(built, CountingClock(T0)).attest()
    assert len(reads) == 1


def test_two_attestations_over_one_registry_agree() -> None:
    built = registry("inbox", "calendar").report(healthy("inbox"))
    clock = ManualClock(T0)

    assert VigilanceAttestation(built, clock).attest() == (
        VigilanceAttestation(built, clock).attest()
    )


def test_two_registries_built_the_same_way_attest_identically() -> None:
    """§14 R2's property, applied here: a test whose result depends on
    when it runs is not a test."""
    first = registry("inbox").report(healthy())
    second = registry("inbox").report(healthy())

    assert attest(first).as_dict() == attest(second).as_dict()


def test_it_reads_no_ambient_time() -> None:
    """It holds the canonical Clock; it never bypasses it."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    banned = {"datetime.now", "datetime.utcnow", "datetime.today", "time.time"}
    assert not [
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ".".join(ast.unparse(node.func).split(".")[-2:]) in banned
    ]


def test_the_attested_moment_is_the_clocks() -> None:
    clock = ManualClock(T0)
    clock.advance(timedelta(hours=3))
    assert attest(registry(), clock).attested_at == T0 + timedelta(hours=3)


def test_it_has_no_ambient_randomness() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
        n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
    } | set(_module_imports())
    for banned in ("uuid", "random", "monotonic", "perf_counter"):
        assert not any(banned in n.lower() for n in names), banned


# ======================================================================
# The registry never mutates
# ======================================================================


def test_register_returns_a_new_registry() -> None:
    """C12 — *"never mutates."* A coverage answer that could change under
    a holder's feet is not proof of anything."""
    empty = DomainRegistry()
    grown = empty.register(Domain("inbox", WINDOW))

    assert grown is not empty
    assert len(empty) == 0
    assert len(grown) == 1


def test_report_returns_a_new_registry() -> None:
    before = registry()
    after = before.report(healthy())

    assert after is not before
    assert before.last_report("inbox") is None
    assert after.last_report("inbox") is not None


def test_an_earlier_attestation_is_unaffected_by_a_later_report() -> None:
    """The answer a surface is holding cannot become a different answer
    while it holds it."""
    built = registry().report(healthy())
    coverage = attest(built)
    assert coverage.complete

    built.report(DomainReport("inbox", T0, False, "went down"))
    assert coverage.complete


def test_a_domain_cannot_be_registered_twice() -> None:
    """One domain has one freshness window, or coverage means two
    things."""
    with pytest.raises(InvalidDomain, match="twice"):
        registry().register(Domain("inbox", timedelta(days=1)))


def test_a_report_for_an_unregistered_domain_is_refused() -> None:
    """A connector reporting on a domain nobody chose to watch would make
    coverage look wider than it was decided to be."""
    with pytest.raises(UnknownDomain, match="calendar"):
        registry().report(healthy("calendar"))


def test_a_refused_report_changes_nothing() -> None:
    built = registry()
    with pytest.raises(UnknownDomain):
        built.report(healthy("calendar"))
    assert built.last_report("inbox") is None


# ======================================================================
# Values refuse to exist in states they should not
# ======================================================================


@pytest.mark.parametrize("name", ["", "   ", None, 7])
def test_a_domain_needs_a_name(name: object) -> None:
    with pytest.raises(InvalidDomain):
        Domain(name, WINDOW)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "window", [timedelta(0), timedelta(seconds=-1), None, 15]
)
def test_a_domain_needs_a_positive_window(window: object) -> None:
    """A window of zero means no check is ever fresh; a negative one
    means every check is."""
    with pytest.raises(InvalidDomain):
        Domain("inbox", window)  # type: ignore[arg-type]


def test_a_report_needs_a_boolean_health() -> None:
    """A domain is either checked and well, or it is a gap."""
    for bogus in ("yes", 1, None):
        with pytest.raises(InvalidDomain):
            DomainReport("inbox", T0, bogus)  # type: ignore[arg-type]


def test_a_report_needs_an_aware_timestamp() -> None:
    """VEDA 04 §5 — freshness metadata is mandatory, and an ambient local
    moment is what §7 forbids everywhere else."""
    with pytest.raises(InvalidDomain, match="timezone-aware"):
        DomainReport("inbox", datetime(2026, 8, 6, 12, 0), True)  # noqa: DTZ001


def test_a_report_timestamp_is_normalised_to_utc() -> None:
    from datetime import timezone

    elsewhere = datetime(
        2026, 8, 6, 14, 0, tzinfo=timezone(timedelta(hours=2))
    )
    assert DomainReport("inbox", elsewhere, True).checked_at == T0


def test_a_detail_is_absent_or_says_something() -> None:
    with pytest.raises(InvalidDomain):
        DomainReport("inbox", T0, False, "   ")


def test_the_service_needs_a_real_clock() -> None:
    for bogus in (None, object(), T0):
        with pytest.raises(InvalidDomain):
            VigilanceAttestation(registry(), bogus)  # type: ignore[arg-type]


def test_the_service_needs_a_real_registry() -> None:
    for bogus in (None, object(), ()):
        with pytest.raises(InvalidDomain):
            VigilanceAttestation(bogus, ManualClock(T0))  # type: ignore[arg-type]


# ======================================================================
# CONSTITUTIONAL — the boundaries this component keeps
# ======================================================================


def test_it_depends_on_the_clock_and_nothing_else() -> None:
    """Roadmap §2 C19 — *"Depends on. C1 Clock (freshness windows)."*"""
    internal = {n for n in _module_imports() if n.startswith("master_agent")}
    assert internal == {"master_agent.foundation.clock"}


def test_it_imports_no_kernel_no_ledger_and_no_surface() -> None:
    """Coverage is arithmetic on two moments. It authorizes nothing,
    records nothing, and says nothing."""
    forbidden = (
        "master_agent.kernel", "master_agent.ledger", "master_agent.api",
        "master_agent.coordinator", "master_agent.runtime",
        "master_agent.ui", "master_agent.desktop", "master_agent.dashboard",
        "master_agent.voice", "master_agent.cli", "master_agent.persistence",
        "master_agent.mission_control", "master_agent.broker",
    )
    assert not [
        n for n in _module_imports()
        if any(n.startswith(f) for f in forbidden)
    ]


def test_it_introduces_no_runtime_dependency() -> None:
    forbidden = (
        "http", "socket", "threading", "asyncio", "subprocess", "requests",
        "queue", "concurrent", "multiprocessing",
    )
    imported = _module_imports()
    assert not [
        n for n in imported
        if any(n == f or n.startswith(f + ".") for f in forbidden)
    ]


def test_it_opens_no_file_and_writes_nothing() -> None:
    """Coverage is computed, never stored. The receipt ledger is A1's and
    this is not it."""
    source = MODULE.read_text(encoding="utf-8")
    assert "open(" not in source
    for writer in ("record_intent", "record_attempt", "record_outcome"):
        assert writer not in source


def test_it_holds_no_attestation_of_the_kernels_kind() -> None:
    """C7 owns `Attestation` for §7.3's eight questions. Three
    unqualified attestations in one codebase is how a reader stops being
    able to tell which one spoke — which is why the result here is
    `Coverage`, D7's own word."""
    exported = {n for n in dir(__import__(
        "master_agent.vigilance", fromlist=["_"]
    )) if not n.startswith("_")}
    assert "Attestation" not in exported
    assert "Coverage" in exported


def test_it_decides_nothing_about_execution() -> None:
    """It is a gate on a sentence, not on an action. Nothing here refuses
    a warrant, and nothing here can."""
    source = MODULE.read_text(encoding="utf-8")
    for name in (
        "warrant", "Warrant", "authorize", "settle", "invalidate",
        "KernelRefusal", "attempt_budget",
    ):
        assert name not in source, name


def test_the_clock_is_the_canonical_protocol() -> None:
    """C1's, injected — not a datetime, not a callable, not a default."""
    assert isinstance(ManualClock(T0), Clock)
    parameters = list(inspect.signature(VigilanceAttestation).parameters)
    assert parameters == ["registry", "clock"]


def test_it_is_exported_from_its_package() -> None:
    from master_agent.vigilance import VigilanceAttestation as Exported

    assert Exported is VigilanceAttestation


def test_it_is_within_its_size_budget() -> None:
    """Roadmap §2 C19 — ~200 source lines. Read as executable lines,
    since documentation is not what the estimate is about."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    statements = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.stmt)
        and not (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )
    ]
    assert len(statements) < 300, f"{len(statements)} statements"
