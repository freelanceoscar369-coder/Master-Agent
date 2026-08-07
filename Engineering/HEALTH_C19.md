# Health Report — Sprint 1, Component 19: Vigilance Attestation

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-06
**Status:** Complete. **Not committed, not tagged, no Rule 001.**
**Built on:** `kalpavriksha-s1-c18.0` — commit `01497c3`, treated as frozen. Every file below is new; nothing at or below that tag was touched.
**Ground:** VEDA 04 D7 · VEDA 04 §4, §5, §7, F7 · Roadmap v2 §2 C19 · Kernel Specification §3.4.

---

## 1 · Which C19 this is

**No brief accompanied the instruction**, so the component was grounded in
the only document that names C19: **Roadmap §2 — Vigilance Attestation**.

That entry is marked *Confirmed — buildable, dependencies verified* in
`ROADMAP_CONSISTENCY_STATUS.md` §0, depends on **C1 Clock alone**, and is
therefore buildable above a frozen `c18.0` without touching anything.

**The numbering divergence recorded as R54 continues.** C16, C17 and C18
were each briefed to a component other than their roadmap entry; C19 was
not briefed at all, and this one follows the roadmap. If a different C19
was intended, this is the wrong component and the correction costs one
message — nothing here is depended on by anything.

---

## 2 · What was built

| File | | |
|---|---|---|
| `src/master_agent/vigilance/vigilance.py` | new | 591 lines, **150 AST statements** |
| `src/master_agent/vigilance/__init__.py` | new | twelve exported names |
| `tests/test_vigilance.py` | new | **72 tests** |

```
DomainRegistry()
    register(Domain)        -> DomainRegistry     (never mutates)
    report(DomainReport)    -> DomainRegistry     (never mutates)

VigilanceAttestation(registry, clock)
    attest()                -> Coverage

CalmState(coverage)         unconstructable unless coverage.complete
```

The roadmap estimates ~200 source lines and ~45 tests. **150 executable
statements and 72 tests** — consistent with the calibration
`ROADMAP_CONSISTENCY_STATUS.md` §6 records, where test estimates run
1.3× to 3.1× because invariants are enforced at construction with
exhaustive coverage.

---

## 3 · The contract, taken verbatim

VEDA 04 §4 froze the shape:

```
   attest() → {complete: bool, domains[{name, lastChecked, healthy}], gaps[]}
```

Implemented exactly, **including the spelling**: the projection emits
`lastChecked`, not `last_checked`, because a frozen contract's key names
are part of the contract. `attest()` takes no argument, as the contract
shows it; the registry and the clock are held instead.

`Coverage` gains one field the contract does not list — `attested_at`,
the single moment every freshness comparison was made against. Without it
a reader cannot tell what "fresh" meant, and §5 makes freshness metadata
mandatory.

**The result is named `Coverage`, not `Attestation`.** C7 owns
`Attestation` for §7.3's eight questions, and D7's own phrase is *"a
**coverage check** across every monitored domain."* Three unqualified
attestations in one codebase is how a reader stops being able to tell
which one spoke — the reasoning C8 already applied to `KernelRefusal`.

---

## 4 · The calm state is unconstructable without proof

VEDA 04 §4: *"**Consider** enforcing at the type level — the calm-state
message should be unconstructable without a complete attestation."*
Roadmap §2 C19 turns the suggestion into a requirement: *"**must** be
unconstructable."*

```python
@dataclass(frozen=True)
class CalmState:
    coverage: Coverage        # the only field, and the only constructor
```

Construction refuses an incomplete `Coverage`, refuses anything that is
not a `Coverage`, and there is no second constructor, no flag and no
bypass. This is the Kernel's own pattern one layer out — §1.3 One:
*"Bypass is a type error, not a policy violation."*

**It holds the proof rather than a copy**, so an audit years later sees
exactly which domains were fresh when the claim was made.

**It carries no words.** Not the phrase, not a fragment of it. §3.4 gives
narration to D1 and Roadmap §2 C20 gives every outbound utterance to the
Voice Charter Validator; a component that composed the calm sentence
would be writing founder-facing prose inside the component whose job is
to decide whether prose is *permitted*. A test asserts the phrase appears
nowhere in the module body or in any projection.

---

## 5 · Three decisions worth naming

### 5.1 Zero domains is not calm

An empty registry has no gaps, and that is precisely the lie D7 describes.
*"Provably complete"* over an empty set proves nothing, and §7 warns that
cost control *"must come from prioritising by consequence, not from
reducing coverage — because reducing coverage silently breaks D7."*

**Completeness requires at least one registered domain and no gaps.** An
empty registry is incomplete and its gap says so in the connector-facing
detail. Four tests cover it, including the adversarial one: watch
nothing, find no gaps, claim calm.

### 5.2 A report stamped in the future is stale

A timestamp ahead of the canonical clock is not evidence that a check
happened. Treating it as evidence would let a connector claim permanent
freshness by getting its clock wrong — and the failure mode of the
alternative is exactly the lie D7 exists to prevent.

The conservative direction is the only safe one here, and it is the same
direction the window boundary takes: an age **equal** to the freshness
window is stale, following C4's `is_expired`, which treats the moment of
expiry as expired. Both refuse calm slightly earlier rather than slightly
later.

### 5.3 Staleness is reported before unhealthiness

An old failure is first of all old. The freshest thing known about the
domain is outside its window, and calling it *unhealthy* would claim
knowledge the window says has expired. §5 makes the distinction between
*I don't know* and *I haven't checked* *"a data property, not a phrasing
choice"*, and this is that property.

Order: `never_checked` → `stale` → `unhealthy`. Each is tested at its own
boundary.

---

## 6 · Where D7's three words went

D7 names *"stale, unreachable or errored"*. The frozen contract carries
`healthy` as a **boolean**, so *unreachable* and *errored* both arrive as
`healthy=False` and are told apart by the connector's own `detail` —
carried verbatim, never composed here.

| Gap kind | Meaning |
|---|---|
| `never_checked` | Registered, and no connector has ever reported |
| `stale` | The last report is outside the window, or stamped after the attestation moment |
| `unhealthy` | The connector reported, and said it was not healthy |

Closed at three. A fourth kind is a change to what coverage means.

**Every gap names its domain.** D7: *"It must say what it could not
check."* A gap that could not say which domain it was about would be the
silent gap by another route, and the refusal message lists every one.

---

## 7 · Immutable, like every other registry here

`register()` and `report()` each return a **new** `DomainRegistry`,
following C12's Reversibility Registry — *"never mutates"* — and C14's
`OverrideSwitch`.

A coverage answer that could change under a holder's feet is not proof of
anything. A test holds a complete `Coverage`, reports a failure into the
registry afterwards, and asserts the held answer is unchanged.

`attest()` is therefore a pure function of the registry and **one** clock
reading — asserted by a counting clock, because no two domains in a single
answer may be judged against different nows.

---

## 8 · Placement, and why not `foundation/`

`master_agent/vigilance/`, a new package.

`foundation/`'s door admits a module only if *"every layer above it needs
it"* — vigilance is needed by C21 alone — and `foundation/__init__.py`
aggregates its exports, so adding there would **modify a file that three
shipped milestones have left byte-identical**. The roadmap also lists C19
as its own component with its own public API.

C12 is a registry inside `foundation/`, so the precedent exists; it is
not followed here because C12 has zero dependencies and this one has a
clock, and because the preservation guarantee is worth more than the
symmetry.

---

## 9 · Test coverage — 72 tests

| Area | Proves |
|---|---|
| **The frozen contract** | The exact shape; `lastChecked` spelling; `attest()` takes no argument; the registry's two operations; every answer serialises |
| **Complete coverage** | One fresh healthy domain; many; every covered domain is named with its check time |
| **The invariant** | Never checked, stale, and unhealthy each break completeness; one gap among many healthy domains is enough; every gap is named; the connector's own words are carried; the vocabulary is closed |
| **Zero domains** | Not complete; says why; cannot reach the calm state; dropping the last domain does not produce calm |
| **The calm state** | A complete coverage permits it; **all four ways coverage breaks refuse it**; the refusal names which domains broke it; it cannot be built from an assertion, from a forged coverage, or from anything but a `Coverage`; it holds its proof; it is immutable; **it carries no words** |
| **Freshness** | Inside the window; the boundary is closed at the far end; a future report is not fresh; each domain uses its own window; a fresh check replaces a stale one; an unhealthy check replaces a healthy one; staleness is reported before unhealthiness |
| **Determinism** | The clock is read once per attestation, asserted by a counting clock; two attestations over one registry agree; two registries built alike attest identically; no ambient time; no ambient randomness; the attested moment is the clock's |
| **Immutability** | `register` and `report` return new registries; an earlier attestation is unaffected by a later report; a domain cannot be registered twice; a report for an unregistered domain is refused and changes nothing |
| **Construction invariants** | A domain needs a name and a positive window; a report needs a boolean health, an aware timestamp normalised to UTC, and a detail that is absent or says something; the service needs a real clock and a real registry |
| **Boundaries** | Depends on `foundation.clock` and nothing else; imports no Kernel, ledger or surface; no runtime dependency; opens no file and writes nothing; exports no `Attestation`; decides nothing about execution |

---

## 10 · Quality gates

| Gate | Result |
|---|---|
| C19 tests | **72 passed, 0 failed** |
| C19 + C18 + C17 + C16 + C15 + C9.1 + all foundation suites | **1,609 passed, 1 pre-existing failure** |
| Architecture guards (7 modules) | **243 passed, 1 skipped, 0 failed** |
| Ruff — C19 source and tests | **All checks passed** |
| Line length | 79 source / 87 tests (limit 100) |
| Size | **150 AST statements** against the roadmap's ~200 source lines |
| C1–C18 untouched | **0 modified files** in `foundation/`, `ledger/`, `kernel/`, `coordinator/`, `api/` or `runtime_bridge/` |

The single failure is
`test_foundation_clock.py::test_only_the_clock_module_reads_the_machines_wall_clock`,
caused by `launcher/boot.py` reading ambient time **in the working copy**.
It is the pre-existing failure recorded at C15.0 and C18.0 and proven
absent at both tags. The guard's report names only `boot.py`; C19 adds no
ambient-time read.

---

## 11 · New findings

### R59 — the registry has no way to stop watching · **Low**

`register()` and `report()` exist; nothing removes a domain.

VEDA 04 §7 requires that *"if work must be shed, the system **says which
domain it stopped watching**"* — which implies a domain can leave
coverage, and that its departure is narrated. Neither half is built: the
roadmap's declared surface for C19 is `register / report` and nothing
else, and adding an unbriefed third operation would be speculative.

**The safe direction holds meanwhile:** a domain that stops being
reported goes stale and breaks completeness, so nothing can quietly
disappear from coverage without the calm state becoming unavailable.
What is missing is the deliberate, narrated removal, not the protection.

### R60 — a connector's `detail` is untrusted text on a founder-facing path · **Low**

`DomainReport.detail` is carried verbatim into `Gap.detail` and into the
`VigilanceIncomplete` message, both of which a surface may render. The
words come from a connector, not from this system.

Carrying them is correct — they are the only description of *why* a
domain failed, and composing a replacement here would be writing prose
C20 owns. But whatever renders them must treat them as untrusted input
and validate them as an utterance. **This is the same shape as R56** and
lands in the same place: C20 and C21.

### R61 — a healthy report is trusted, not verified · **Low**

The component checks that a domain *was reported*, *within its window*,
*as healthy*. It cannot check whether the connector actually looked.

VEDA 04 §2 names this exact risk — *"a connector that fails quietly makes
'Nothing needs you' a lie"* — and its stated mitigation is the one built
here: *"D7 as a hard gate on the calm state."* The gate catches silence
and staleness; it cannot catch a connector that reports success without
checking.

Recorded as a known limit rather than an assumed guarantee, in the same
spirit as the Kernel's R5 on attestation forgery.

---

## 12 · Preservation

C1–C18 untouched — zero modified files in `foundation/`, `ledger/`,
`kernel/`, `coordinator/`, `api/` or `runtime_bridge/`, measured against
the working tree at `kalpavriksha-s1-c18.0`. `foundation/__init__.py` in
particular is unchanged, which is why the package is its own.

The only C1 surface consumed is `Clock`, injected and never constructed.

No specification, roadmap, amendment or ADR modified. **No new ADR, no new
runtime dependency, no speculative API, no outbound utterance.** C20 and
C21 not begun. No commit, no tag, no Rule 001.

**STOP.** Awaiting Hermes audit.
