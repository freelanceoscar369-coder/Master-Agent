# Health Report — Sprint 1, Component 22: Environment Intelligence

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-06
**Status:** Complete. **Not committed, not tagged, no Rule 001.**
**Built on:** `kalpavriksha-s1-c18.0` — commit `01497c3`, treated as frozen.
**Ground:** existing Desktop subsystem · existing Environment Scanner · AI Infrastructure · Provider Registry · C19 Vigilance · C20 Presence · C21 Surface.

**Constraints honoured:** no frozen component modified · no new scanner ·
no second catalog · no second inventory · no execution · no mutation ·
no privacy-sensitive inspection · no Sprint 2 · no Mission OS · no Runtime,
Kernel or Electron redesign.

---

## 1 · What was built

| File | | |
|---|---|---|
| `src/master_agent/environment_intelligence/evidence.py` | new | 198 lines, **51 AST statements** |
| `src/master_agent/environment_intelligence/models.py` | new | 471 lines, **131 AST statements** |
| `src/master_agent/environment_intelligence/derive.py` | new | 674 lines, **149 AST statements** |
| `src/master_agent/environment_intelligence/__init__.py` | new | 30 exported names |
| `tests/test_environment_intelligence.py` | new | **74 tests** |

**336 statements of implementation.** One entry point:

```python
derive_intelligence(inventory: MachineInventory) -> EnvironmentIntelligence
```

All six required contracts are produced: `BrowserProfile` · `AIToolProfile`
· `CapabilityGraph` · `UserProfile` · `PreferenceModel` ·
`EnvironmentSummary`.

**Placement:** `environment_intelligence/`, beside `environment/` rather
than inside it. That package is stateful browser-session management by its
own docstring; this is a pure derivation over a value someone else
captured, and putting it there would have meant editing its `__init__`.

---

## 2 · Reuse, proven rather than promised

The brief's hardest structural rule is *"no duplicate scanning logic, no
second catalog, no second inventory."*

| Guarantee | How it is enforced |
|---|---|
| Consumes the existing scanner | Imports `MachineInventory` and `desktop.catalog` — asserted by test |
| No second catalog | `ApplicationSpec` and `CATALOG` appear in **no expression** in this package |
| No second inventory | `discover`, `discover_application`, `attribute_processes` appear nowhere |
| Cannot reach the machine | No `subprocess`, `os`, `shutil`, `socket`, `http`, `urllib`, `requests`, `pathlib`, `winreg`, `ctypes` import — 10 names checked |
| Holds no probe | `SystemProbe`, `RealSystemProbe`, `CommandResult` appear nowhere |
| Executes nothing | `run`, `start`, `launch`, `execute`, `spawn`, `popen`, `system`, `install`, `write`, `delete`, `remove`, `mkdir` — 12 names, none present |
| Mutates no input | A test captures the inventory's projection before and after and asserts equality |

**Every check reads executable identifiers via AST, not source text.**
These modules' docstrings name the things they refuse to do, and a
text-matching guard would fail on its own explanation — a trap this
project has hit twice already (C15 Part 6, and the C20 audit).

**Dependency set: `master_agent.desktop.*` and this package only.** No
frozen component is imported — `foundation/`, `kernel/`, `ledger/`,
`coordinator/`, `runtime_bridge/` and `api/` are all asserted absent.

---

## 3 · Explainability — the reason nothing here is a black box

Every conclusion is an `Inference` carrying **value · confidence · reason ·
evidence**, and the type refuses to exist without them:

- A conclusion above `UNKNOWN` **must** carry evidence — enforced at
  construction.
- An `UNKNOWN` inference **must** carry `value=None` — naming a value
  would be a guess presented as a finding.
- Every `Evidence` names a `source` (a path into the inventory) and a
  `fact`, both non-empty.
- A blank reason is unconstructable.

A test walks the entire projected result and asserts all four properties
on **every** inference it finds, of which there are more than ten in a
typical reading.

### Confidence is a band, not a number

A float would let this layer emit `0.73` for a judgement made by counting
two facts — a black box wearing a lab coat. So confidence is an ordered
band: `OBSERVED` (the inventory says so) · `STRONG` (two independent facts)
· `WEAK` (one indirect fact) · `UNKNOWN` (no evidence).

**Propagation has exactly one operator:** `Confidence.weakest()`. A
conclusion is never stronger than its weakest input, there is no averaging
and **two weak facts cannot become a strong one** — asserted directly,
because that arithmetic is how a guess acquires authority it did not earn.

---

## 4 · Privacy — structural, not merely observed

The brief forbids inspecting passwords, conversations and personal
documents, and permits cookie knowledge only as far as session existence.

**This layer goes nowhere near any of them, and the reason is stronger
than compliance: a `MachineInventory` does not contain them.** It holds
application names, versions, install paths and a process list. There is no
cookie, no history, no document and no credential in it. The guarantee is
structural — this layer could not violate it without first acquiring a
capability it does not have.

Two deliberate refusals, both tested:

**`window_title` is never read.** `ProcessInfo` carries one, and a
browser's window title is the page the founder is looking at. Using it to
infer an "active browser" would be inspecting browsing by another route.
Activity comes from process *names* only, and a test asserts the
identifier appears nowhere in the package.

**Web AI is `UNKNOWN`, never `AVAILABLE`.** Determining whether a browser
holds a signed-in ChatGPT session requires reading that browser's profile
data. The inventory carries no such signal, and manufacturing one would
mean building the profile reader the brief forbids. So every service
reports `UNKNOWN` with a reason naming why — **except the one case real
evidence settles**: no usable browser installed means no web service is
reachable, which is `UNAVAILABLE` at `STRONG` confidence.

A test asserts that across three different environments, **no service is
ever reported `AVAILABLE`.** Nothing in a machine inventory can establish
a signed-in session, so nothing claims one.

Nine privacy-sensitive identifiers are asserted absent: `cookie`,
`cookies`, `password`, `credential`, `history`, `conversation`,
`document`, `profile_path`, `localstorage`.

---

## 5 · What the brief asked for that the evidence cannot support

**This is the most important section of this report.** The brief asks for
inference the current scanner cannot ground. Rather than fabricate, each
is returned as `UNKNOWN` carrying the reason — and the reason distinguishes
*"nothing found"* from *"finding out would require something forbidden"*,
which is VEDA 04 §5's distinction as a data property.

| Asked for | Answer | Why |
|---|---|---|
| **Default browser** | `UNKNOWN`, always | Needs a registry or `xdg-settings` read. The scanner performs neither, and adding one is scanner work |
| **Brave, Arc** | Not scanned | `desktop/catalog.py` has no entry, so nothing looked |
| **Office, Copilot** | Not scanned | As above |
| **Web AI sessions** | `UNKNOWN` | §4 |
| **Trader, Creator, Office, Research profiles** | Never claimed | No catalogued application evidences any of them |

**The four uncatalogued applications are surfaced by name** in
`EnvironmentIntelligence.uncatalogued`, so their absence reads as *"never
looked"* rather than *"not installed"*. Adding them is **one entry each in
the scanner's own catalog** — that file's documented extension point — and
C22 deliberately does not add them: the brief forbids a second catalog,
and editing the first is scanner work rather than enrichment. **Recorded
as R80** so the decision is the founder's rather than mine by default.

---

## 6 · The derivations, and the rules they follow

### Preference — one rule, stated so it is auditable

1. **Exactly one running** → that one, `OBSERVED`.
2. **Several running** → `UNKNOWN`, naming them. Two browsers open says
   nothing about preference, and picking one would be a coin toss wearing
   a confidence band.
3. **None running, one usable installed** → that one, `STRONG`.
4. **None running, several installed** → `UNKNOWN`, naming them.

An `UNAVAILABLE` (present but broken) application is never preferred —
recommending something that does not work is worse than saying nothing.

### User profile — never from one application

The brief's hard rule is enforced structurally: **at least two distinct
installed applications** must evidence a kind before it is named, and both
appear in the inference. One application returns `UNKNOWN` saying so.

With the current catalog only `DEVELOPER` is evidenceable, and `MIXED`
when developer tooling coexists with AI tooling — two distinct kinds of
use. The four unevidenceable profiles are named in `considered` rather
than silently omitted.

### Capability graph — stops where the evidence stops

The brief's illustrative chain is *Claude Desktop → MCP → Filesystem →
Trading Repository*. **Only the first hop is drawn.** The inventory
carries no MCP signal, no filesystem-tool signal and no repository signal,
so those three edges do not exist. A test asserts
`graph.node("mcp") is None` and that the repository is unreachable — a
graph showing them would be describing a machine nobody looked at.

`reaches()` returns `False` rather than assuming a link the evidence does
not draw.

### Summary — observations, never recommendations

`desktop/inventory.py` draws this line already — *"'Ollama not installed.'
is a fact. 'Install Ollama.' is advice"* — and this layer holds it. A test
scans every observation for ten advice markers (`should`, `recommend`,
`consider`, `install `, `better`, `best`, `instead`, …) and fails on any.

---

## 7 · Designed to be refreshable — structure only, no loop

Per the constraint issued mid-build: **the models are structured so
continuous refresh becomes possible later, and refresh is not
implemented.**

Three properties make the evolution cheap, all structural:

| Property | Why refresh needs it |
|---|---|
| **Immutable and self-dated** | Two readings coexist and are told apart. A consumer holding an older one cannot have it change underneath them |
| **Derived by a pure function** | Refreshing is calling `derive_intelligence()` again — no state to reset, no cache to invalidate, no warm-up |
| **Comparable** | `is_newer_than()` and `changes_from()` let a caller act on *what changed* instead of re-reading everything |

`changes_from()` returns which of the six sections differ, in fixed order.
`is_newer_than()` compares the two `captured_at` values — **the
inventories' own moments, never a clock read here** — and returns `False`
when either is undated, because *"unknown when"* cannot be ordered against
*"known when"*.

**No refresh machinery exists, and a test enforces it:** `refresh`,
`poll`, `schedule`, `subscribe`, `listener`, `cache`, `interval`, `sleep`,
`watch`, `thread` — ten identifiers, none present. Whoever owns the
cadence owns the loop; this only makes the loop cheap to write.

This is the same shape the Presence Layer already expects: it consumes
snapshots it did not produce and cannot reach back into.

---

## 8 · C20 Presence integration — the data contract, and its limit

The brief asks the Presence Layer to be able to expose *Environment
Ready · AI Available · Developer Environment Healthy*. All three are
produced on `EnvironmentSummary`, each a full `Inference`:

| Signal | Derived from |
|---|---|
| `environment_ready` | Capability nodes exist **and** the profile resolves. Confidence is `weakest(OBSERVED, profile.confidence)` — it can never exceed the profile's |
| `ai_available` | `OBSERVED` when an AI application is installed and usable; `UNKNOWN` otherwise, noting that web session state is not inspected |
| `developer_environment_healthy` | `STRONG` when a language runtime **and** version control are both present; `UNKNOWN` naming which is missing otherwise |

`EnvironmentIntelligence.as_dict()` is the JSON contract — deterministic,
fixed key order, whole-result serialisation tested.

**The limit, stated plainly.** C20 Presence is a **TypeScript package in a
zip** (`kalpavriksha-C20-presence.zip`), not in this repository and not
mine to modify. *"Wire the output into C20 Presence"* is therefore
delivered as **a data contract the Presence Layer can consume**, not as an
edit to that package. No TypeScript was written, and nothing consumes
these signals yet. **Recorded as R81.**

---

## 9 · Test coverage — 74 tests

| Area | Proves |
|---|---|
| **Explainability** | Every inference in a full result carries confidence, reason and evidence; `UNKNOWN` never carries a value; a known inference must carry evidence; blank reasons and sourceless evidence are unconstructable |
| **Confidence propagation** | The band ordering; weakest-input rule; **two weak facts do not become strong**; empty is `UNKNOWN`; readiness inherits the weakest input |
| **Browsers** | Single running → preferred and active; **conflicting browsers → `UNKNOWN`, not a coin toss**; only-installed → `STRONG`; several installed none running → `UNKNOWN` naming them; none installed; a broken browser is never preferred; default is always `UNKNOWN` and says why; two running produce no active guess |
| **AI ecosystem** | **Multiple AI tools running → `UNKNOWN`**; single running → preferred; local and running reported separately |
| **Privacy** | Only the three permitted values; `UNKNOWN` when a browser exists; `UNAVAILABLE` only when none does; **no service is ever `AVAILABLE`**; `window_title` never read; nine sensitive identifiers absent |
| **Read-only** | Ten machine-reaching imports absent; no probe; twelve execution identifiers absent; input never mutated |
| **No duplication** | No second catalog; no second inventory; dependency set is scanner + self; no frozen component imported; no Kernel vocabulary |
| **User profile** | **One application never names a profile**; none never does; two do; developer + AI is `MIXED`; unhealthy applications do not count; unevidenceable profiles are named as such |
| **Capability graph** | Node and edge from an installed application; missing and unusable produce nothing; **the brief's chain stops where evidence stops**; two applications share one capability node; every edge carries evidence; `reaches` returns `False` rather than assuming |
| **Preferences** | Running editor wins; every preference explainable; no candidates → `UNKNOWN` |
| **Partial environments** | Empty inventory produces a complete result with everything `UNKNOWN` and nothing raising; partial reports what it has; healthy developer environment named; uncatalogued surfaced by name |
| **Summary** | **Recommends nothing** (ten advice markers checked); reports web uncertainty rather than hiding it; three readiness signals present |
| **Refresh seam** | A reading is a moment not a live view; refreshing is deriving again; ordering uses the inventory's moment; undated is never newer; `changes_from` names which section moved and is empty when meaning holds; comparison mutates neither; **no refresh machinery exists** |
| **Determinism** | Same inventory → equal results; no clock read; whole result serialises; results immutable |

---

## 10 · Quality gates

| Gate | Result |
|---|---|
| C22 tests | **74 passed, 0 failed** |
| C22 + C15–C21 + foundation suites | **1,683 passed, 1 pre-existing failure** |
| Architecture guards (6 modules) | **215 passed, 1 skipped, 0 failed** |
| Ruff — C22 source and tests | **All checks passed** |
| Line length | 86 source / 87 tests (limit 100) |
| Size | **336 AST statements** across four modules |
| Frozen components untouched | **0 modified files** in `foundation/`, `kernel/`, `ledger/`, `coordinator/`, `runtime_bridge/` |
| Scanner untouched | **0 modified files** in `desktop/` |

The single failure is
`test_foundation_clock.py::test_only_the_clock_module_reads_the_machines_wall_clock`,
caused by `launcher/boot.py` reading ambient time **in the working copy**.
It is the pre-existing failure recorded at C15.0 and C18.0 and proven
absent at both tags. The guard's report names only `boot.py`; **C22 adds
no ambient-time read** and holds no clock at all.

---

## 11 · New findings

### R80 — four named applications have no catalog entry · **Medium**

Brave, Arc, Microsoft Office and GitHub Copilot are named in the brief and
absent from `desktop/catalog.py`, so the scanner never looks for them.
This layer surfaces them by name in `uncatalogued` rather than letting
their absence read as *"not installed"*.

**Not fixed here, deliberately.** Each is one entry in the scanner's own
catalog — that file's documented extension point — but the brief forbids a
second catalog and editing the first is scanner work, not enrichment.
Adding them is a small, safe change to `desktop/catalog.py` whenever the
founder wants it; making that call unilaterally would have been the
scanner redesign the brief excludes.

### R81 — the C20 wiring is a contract, not a connection · **Medium**

C20 Presence is a TypeScript package inside
`VEDRA_PROJECT/01_Assets/UI-UX/kalpavriksha-C20-presence.zip`. It is not
in this repository, and modifying it was not in scope.

The three readiness signals and the full JSON projection exist and are
tested. **Nothing consumes them yet.** Whoever integrates will need either
a Python-side presence consumer or a TypeScript-side decoder for this
contract — the same shape as R53 before C18 resolved it, and the same kind
of decision: where the value is assembled.

### R82 — only one user profile is currently evidenceable · **Low**

Of the brief's six kinds, `DEVELOPER` and `MIXED` are derivable from the
current catalog. Creator, Office User, Trader and Research User have **no
catalogued application** that would evidence them, so none is ever claimed
and `considered` says why.

This is a consequence of R80 and of the catalog's scope (developer tooling,
browsers, AI), not a defect in the derivation. Widening it means widening
the catalog first — the evidence has to exist before it can be weighed.

---

## 12 · Preservation

Frozen components untouched — zero modified files in `foundation/`,
`kernel/`, `ledger/`, `coordinator/` or `runtime_bridge/`. **The scanner
is untouched too**: `desktop/` has zero modified files, and this layer
consumes `MachineInventory` and `desktop.catalog` through their public
surfaces only.

No specification, roadmap, amendment or ADR modified. **No new scanner, no
second catalog, no second inventory, no new runtime dependency, no
execution, no mutation, no refresh loop.** No commit, no tag, no Rule 001.

**STOP.** Awaiting Hermes audit.
