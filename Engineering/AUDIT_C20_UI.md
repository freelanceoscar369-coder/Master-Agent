# Engineering Audit — C20 Founder Presence Layer & UI Prototype

**Artefacts:** `VEDRA_PROJECT/01_Assets/UI-UX/`
— `kalpavriksha-C20-presence.zip` (the Presence Layer)
— `kalpavriksha-desktop-v0.1.zip` (the desktop prototype)
— four `UX_0*.html` static mockups (2026-08-03)
**Role:** Independent Architecture Auditor. The auditor did not implement C20.
**Audit Date:** 2026-08-06
**Repository:** `HEAD` = `01497c3`, tag `kalpavriksha-s1-c18.0`. Nothing modified.
**Method:** Both archives extracted to a scratchpad outside the repository. Tests and the purity guard were **executed independently**, and four probes were written to test claims the suite does not cover. The audited packages were never edited; guard-evasion tests ran against throwaway copies.

---

## Executive Verdict

> ## **FAIL**

**Not for craft.** The Presence Layer is disciplined work: 183 tests pass,
the purity guard is real and demonstrably catches breaches, there are zero
dependencies, and the grounding disclosure — twelve named assumptions,
locked open by a test — is the most honest artefact this project has
received from any agent.

**It fails on one thing, and it is the one thing that matters most.**

> **A Presence Layer that has been told nothing reports
> `calm: true` — "Nothing needs you."**

Verified by direct probe. `createPresenceLayer()` followed immediately by
`snapshot(now)` — zero observations, zero domains, nothing known about
anything — produces:

```
  observationCount  : 0
  vigilance.complete: true
  vigilance.domains : []
  calm.calm         : true
  calm.statement    : "Nothing needs you."
  meta.possiblyStale: false
```

VEDA 04 D7 names this exact condition and calls it fatal:

> *"'Nothing needs you' … is only safe if it is **provably complete** —
> backed by a coverage check across every monitored domain."*
>
> *"A silent gap converts the product's core promise into a lie by
> omission, and it is **the single failure most likely to end a customer
> relationship permanently.**"*

An empty coverage set is not a complete coverage check. It is the absence
of one. The layer has no gaps because it is watching nothing, and it
reports that as calm.

**This is also a direct contradiction of shipped C19**, which refuses the
identical case by construction (`test_an_empty_registry_cannot_reach_the_calm_state`).
Two components in the same system now answer the same constitutional
question differently.

**One further scope finding:** objective 5 cannot be discharged. **No
Founder Conversation surface exists in either archive** — see §8.

The verdict is narrow and the remedy is small. §12 states it.

---

## 1 · What was verified, and how

Every claim below was executed, not read.

| Check | Command | Result |
|---|---|---|
| Test suite | `node --test 'tests/**/*.test.ts'` | **183 pass · 0 fail · 40 suites** — health report accurate |
| Purity guard | `node tests/purity-guard.mjs` | **CONTAINED, 0 findings**, exit 0 — accurate |
| External dependencies | `package.json` | `dependencies: {}`, `devDependencies: {}` — **zero**, accurate |
| Guard actually enforces | 4 breaches injected into a **copy** | **5 findings, exit 1** — the guard is real |
| Guard limits | 4 evasions injected into a **copy** | **0 findings, exit 0** — see R67 |
| Runtime behaviour | 8 auditor probes | §4, §5, §6 |

Node v24.15.0, native TypeScript stripping. Nothing was installed.

---

## 2 · Constitutional Compliance

### 2.1 Ownership — what the Presence Layer owns

| Required to own | Verdict | Evidence |
|---|---|---|
| `PresenceSnapshot` production | ✅ | `presenceLayer.ts:build()`; all eight brief-mandated fields present, asserted with `Object.hasOwn` including when null |
| Runtime observation | ✅ | `observations.ts` — twelve observation types, structurally validated, push-only |
| Founder-facing state projection | ✅ | `derive.ts` — seven pure projections |

### 2.2 Ownership — what it must not own

Each was checked against the source and against the executed guard.

| Must NOT own | Verdict | Evidence |
|---|---|---|
| Authorization | ✅ absent | No verdict, permission or policy surface. Guard rejects `authorize(`/`authorise(` — proved by injection |
| Orchestration | ✅ absent | No scheduler, no queue, no dispatch. Subscribers notified synchronously inside `observe` |
| Execution | ✅ absent | No executor reference. Guard rejects `execute(`/`invoke(` — proved |
| Mutation (of anything outside itself) | ✅ absent | It holds nothing external. The fold copies; `state.test.ts` asserts inputs are never touched |
| Business logic | ⚠️ **partial** | Calm blockers are policy, not projection — see R66 |
| Planning | ✅ absent | No plan, step or decomposition concept |
| Plugin invocation | ✅ absent | Zero external imports, guard-enforced |
| Tool execution | ✅ absent | As above |
| Mission management | ✅ absent | Missions are observed and ranked for display; none is started, held or cleared by the layer |

**The one qualification is R66.** `deriveCalm` decides *when the product
may claim calm* — that is a constitutional rule, not a projection. It is
in a projection layer, and neither of its two most consequential branches
has a frozen source.

---

## 3 · Boundary Verification · Green Component Protection

| Protected path | Status |
|---|---|
| `src/master_agent/foundation/` | **Unmodified** |
| `src/master_agent/kernel/` | **Unmodified** |
| `src/master_agent/ledger/` | **Unmodified** |
| `src/master_agent/coordinator/` | **Unmodified** |
| `src/master_agent/runtime_bridge/` | **Unmodified** |
| Any tracked repository file | **Unmodified** — `git diff kalpavriksha-s1-c18.0` is empty for all tracked source |

**Zero architectural leakage into the Python repository.** Both artefacts
are self-contained archives in `VEDRA_PROJECT/01_Assets/UI-UX/` and import
nothing from `master_agent`. The Presence Layer's containment is
mechanically enforced: **18 imports, all package-internal, zero external.**

The health report's *"files touched outside `presence/`: none"* is accurate.

---

## 4 · Snapshot Contract Review

All eight brief-mandated fields are present on every snapshot, plus
`sequence`, `at` and `meta`.

| Field | Derived from | Invented? |
|---|---|---|
| `activeMission` | `mission.observed` fold, ranked held ▸ running ▸ queued ▸ other | No |
| `execution` | `execution.observed` fold | No |
| `calm` | computed from five blockers | **See R64, R66** |
| `vigilance` | `coverage.reported` / `coverage.expected` fold | **See R64, R65** |
| `pendingApprovals` | `approval.opened` / `.closed` fold | No |
| `lastAction` | `action.recorded` fold, carried verbatim | No |
| `reasoning` | `reasoning.supplied` fold, carried verbatim | No — **verified**, §6 |
| `activity` | fixed-template composition over the above | No — templates, §6 |

**Two derived numbers are computed, not carried** — `inPhaseSeconds`,
`waitingSeconds`, `agoSeconds`, `ageSeconds` — all from `secondsBetween`,
which is pure and clamps negatives to zero. Legitimate projection.

**One field is self-derived and disclosed as such:** `calmSince`. The
health report names it (§6 item 7). It is the only state the layer
originates, and it exists so calm can report duration. Accepted.

**Ordering is order-independent**, which matters for reproducibility:
missions sort by rank then `startedAt` then `ref`; approvals by
`requestedAt` then `approvalId`; domains lexically. All tie-breaks are
total. Verified in `derive.test.ts`.

---

## 5 · Calm Review — the failing section

### 5.1 R64 · A layer told nothing claims calm — **Critical**

`createObservedState()` initialises `expectedDomains: []` and an empty
`coverage` map. `deriveVigilance` builds its `expected` set from those two,
finds it empty, iterates zero times, produces zero gaps, and returns
`{ complete: true, domains: [] }`. `deriveCalm` then finds no blockers.

**Probe 1, verbatim output:**

```
  vigilance.complete: true
  calm.calm         : true
  calm.statement    : "Nothing needs you."
  meta.possiblyStale: false
```

Two aggravating factors:

**The staleness flag does not fire either.** `possiblyStale` requires
`state.lastObservedAt !== null`. A layer that has never been fed has
`lastObservedAt === null`, so the one signal that might have qualified the
claim is **false** in exactly the case it is most needed. A layer that is
disconnected at birth is indistinguishable from a calm one.

**`meta` is explicitly not founder-facing.** `types.ts` documents
`SnapshotMeta` as *"Diagnostics; never founder-facing prose."* So even if
`possiblyStale` did fire, `calm.statement` would still read *"Nothing
needs you."* The claim carries no qualification.

The layer's own defence — the discriminated union, and `calm: true` being
constructible at exactly one place — is well designed and **works exactly
as intended.** It is not the gate that failed. The gate simply has nothing
to check when the domain set is empty.

### 5.2 R65 · Three measurable disagreements with shipped C19 — **High**

C19 (`src/master_agent/vigilance/vigilance.py`, delivered, awaiting audit)
implements the same D7 gate. The two disagree:

| Case | C19 | C20 | Probe |
|---|---|---|---|
| **Zero domains** | `complete = bool(statuses) and not gaps` → **incomplete** | **complete** | 1 |
| **Age exactly equals the window** | `age >= window` → **stale** | `age > freshness` → **fresh** | 3 |
| **Report stamped in the future** | future stamp → **stale** | negative age clamps to 0 → **fresh** | 4 |

**Probe 4 is the sharpest.** A coverage report stamped 24 hours in the
future is accepted as fresh, permanently. A connector with a wrong clock
can hold the system in a false calm indefinitely, and `secondsBetween`'s
negative clamp — correct as a display rule — is what makes it possible.

The two components also spell the same vocabulary differently:
`never_checked` vs `never-reported`, `GapKind` vs `VigilanceGapReason`.

**Neither implementation is wrong on its own terms.** The finding is that
**two exist**, and D7 is a single constitutional gate.

### 5.3 R66 · The calm blockers have no frozen source — **Medium**

The auditor searched the Kernel Specification, VEDA 01–05, ADR-0022,
ADR-0023 and the Roadmap. **Only one of the five blockers is grounded.**

| Blocker | Grounded? |
|---|---|
| `coverage-incomplete` | ✅ **VEDA 04 D7 and F7**, verbatim |
| `approval-pending` | ✗ Not stated. Consistent with the sentence's plain meaning; not written anywhere |
| `execution-active` | ✗ Not stated — **and see below** |
| `mission-held` | ✗ Not stated |
| `failure-unacknowledged` | ✗ Not stated |

**`execution-active` contradicts the layer's own stated rationale.**
`HEALTH_C20.md` §4 argues:

> *"Calm means nothing needs **you**, not nothing is happening. A mission
> running unattended is the product working, not a reason to alarm the
> founder."*

But `deriveCalm` blocks on `execution.phase ∈ {dispatching, running,
streaming, awaiting-approval, cancelling}`. Probes 5 and 6:

```
  mission running, execution idle    → calm: true   "Nothing needs you."
  mission running, execution running → calm: false  "An execution is running."
```

So *"nothing is happening"* **is** required after all — measured on the
execution stream instead of the mission stream. The same underlying
situation produces opposite claims depending on which of two independent
observation streams the feeder happens to populate.

This is recorded in the auditor's earlier `AUDIT_C20.md` as **R62** and is
unchanged: the proposition *"running missions do not block calm"* is
**unsupported and uncontradicted** by any frozen document. It needs an ADR,
not a code change — and the implementation does not currently match its
own stated version of it.

**HyperAgent flagged the semantic decision themselves** (§4, *"flagging it
because it is a semantic judgement I made without a grounding document"*).
That disclosure is correct and creditable. What was not noticed is the
internal inconsistency, and R64.

---

## 6 · Reasoning Review — **passes cleanly**

| Requirement | Verdict | Evidence |
|---|---|---|
| Projected | ✅ | `deriveReasoning` reads `state.reasoning`, set only by `reasoning.supplied` |
| Never generated | ✅ | **Probe 7**: with nothing supplied, `{"text":null,"suppliedAt":null,"ageSeconds":null,"stale":false}` |
| Never hallucinated | ✅ | No model, no inference, no template for `reasoning.text`. The silence is reported as silence |
| Never synthesised | ✅ | `contract.test.ts` folds a long sequence with no `reasoning.supplied` and asserts null throughout |

**Activity lines are templates, and this was checked rather than
accepted.** `deriveActivity` is five branches with fixed precedence —
degraded ▸ waiting-on-founder ▸ blocked ▸ working ▸ idle — interpolating
only counts and a runtime-supplied `title`. No branch composes novel
prose. `PendingApproval.prompt` and `LastAction.description` are carried
verbatim.

**Presence has not become an LLM.** This is the cleanest section of the
audit.

One consequence worth stating: because `text` is carried and never
generated, **it is untrusted runtime input on a founder-facing path.**
Whatever renders it must validate it as an utterance. Same shape as the
auditor's R56/R60 and it lands in the same place.

---

## 7 · Purity Review

### 7.1 What holds

| Prohibition | Verdict | Evidence |
|---|---|---|
| No network | ✅ | Guard rejects `fetch(`, `XMLHttpRequest`, `WebSocket`, `EventSource` — injection proved |
| No filesystem | ✅ | Guard rejects `node:fs/net/http/https/child_process/worker_threads/dgram/tls` — proved |
| No timers | ✅ | Guard rejects `setTimeout`/`setInterval`. Subscribers notified synchronously |
| No threads / background execution | ✅ | No worker, no async surface, no scheduling. **Inert between observations** |
| No randomness | ✅ | Guard rejects `Math.random()` |
| No hidden state | ✅ | `calmSince` is the only self-derived state and is disclosed |
| No hidden clock | ✅ | Guard rejects `Date.now()` and `new Date()`. **Every instant is a parameter** |
| Held snapshots immutable | ✅ | **Probe 8**: a snapshot held across a later fold is unchanged |
| Deterministic | ✅ | `deepStrictEqual` + JSON round-trip in `presenceLayer.test.ts` |

**The no-clock decision is the strongest design choice in the package.**
`snapshot(now)` describes the moment the caller names. That is what makes
every test exact, every snapshot reproducible, and — as the health report
observes — leaves the layer with no notion of *"later"* it could act on.

### 7.2 R67 · The guard is textual, not capability-based — **Medium**

The guard genuinely works against honest error. Four breaches were
injected into a throwaway copy and **all five findings were reported, exit
1.** That is real enforcement and deserves credit.

It does not hold against a determined author. Four evasions were injected
into a second copy; **all four passed, 0 findings, exit 0:**

| Evasion | Why it passes |
|---|---|
| `const f = fetch; f('http://x')` | The pattern is `fetch\s*\(`; the aliased call is `f(` |
| `process.hrtime.bigint()` | Only `process.(env\|exit\|argv)` is listed. A clock, unbanned |
| `new Date(2026, 1, 1)` | The pattern is `new\s+Date\s*\(\s*\)` — empty parentheses only |
| `src/sneaky.mjs` | The walker collects `extname === '.ts'`. **A non-`.ts` file in `src/` is never scanned at all** |

The fourth is the most significant: a `.mjs` inside `src/`, imported by a
relative specifier, is invisible to every check the guard performs, and
the relative import itself resolves inside `SRC` so it is permitted.

**This is a defence against drift, not against an adversary** — which is
the correct thing for it to be, and worth stating so nobody mistakes
`RESULT: CONTAINED` for a stronger claim than it is.

---

## 8 · Founder Conversation Surface — **cannot be verified**

Objective 5 asks whether the Founder Conversation surface aligns with the
approved Sprint 1 execution plan.

**No Founder Conversation surface exists in either archive.** A search
across the whole desktop prototype for `conversation`, `chat`, `message
input` and `composer` returns **zero files**.

What exists is `features/founder/FounderConsole.tsx` (43 KB), whose own
header reads *"the autonomy and judgment surface"*, with four tabs:
**Judgment · Rules · Proposals · Scope & Audit.** That is a governance and
approval surface. It is not a conversation.

No claim is made about whether a conversation surface *should* exist. The
factual position is that the named artefact is absent and objective 5 is
therefore undischarged.

---

## 9 · Hidden Dependency Audit

### 9.1 The Presence Layer — clean

18 imports, all package-internal. Zero dependencies. No implicit coupling,
no duplicated Kernel state, no parallel architecture. **It cannot reach
anything**, which is the whole of its design and it holds.

### 9.2 The desktop prototype — a parallel architecture

The second archive is a different matter, and the findings below concern
it alone.

#### R68 · `kd/src/kernel/` re-declares Kernel vocabulary and behaviour — **High**

| File | Size | What it is |
|---|---|---|
| `kernel/types.ts` | 16 KB | Client-side re-declaration of `Attestation`, `Receipt`, `Principal`, `Capability`, `Verdict`, `StandingRule`, `Mission`, … |
| `kernel/client.ts` | 6 KB | A ~40-method `KernelClient` interface |
| `kernel/mock/mockKernel.ts` | 34 KB | A **working simulated backend** |
| `kernel/mock/fixtures.ts` | 61 KB | Its data |
| `kernel/http/httpKernel.ts` | 22 KB | HTTP mapping |

**A frozen name is redefined.** `kd/src/kernel/types.ts:257` declares:

```ts
export type Attestation =
  | { complete: true;  domains: DomainCoverage[]; at: Iso8601 }
  | { complete: false; domains: DomainCoverage[]; gaps: DomainCoverage[]; at: Iso8601 };
```

C7's shipped `Attestation` is one of §7.3's **eight questions** —
`question · attestor · subject · verdict · attested_at · reason`. These are
different types with the same name. C19 deliberately avoided this collision
by naming its result `Coverage`, citing D7's own phrase and C8's precedent
about three unqualified refusals. The UI reintroduces it.

**In mock mode the UI is the backend.** `mockKernel.ts` implements
`submitVerdict`, `submitBatchVerdict`, `undo`, `grantRule`,
`setRuleStatus`, `suspendAutonomy` and `resumeAutonomy` locally. Every one
of those is a mutation the Kernel owns. Whether that constitutes *leakage*
depends on whether the mock can ever be reached in a real build — a
question this audit cannot answer from static artefacts, and does not
guess at.

#### R69 · A third D7 gate, with a fourth semantics — **High**

`kd/src/lib/vigilance.ts` implements `canClaimCalm()`. There are now three
independent implementations of one constitutional gate:

| | Zero domains | Boundary | Future stamp | Unhealthy + complete |
|---|---|---|---|---|
| **C19** (Python, shipped) | incomplete | `>=` stale | stale | unconstructable |
| **C20 presence** | **complete** | `>` fresh | **fresh** | unconstructable |
| **kd `lib/vigilance.ts`** | not computed — consumes the Kernel's answer | n/a | n/a | **possible, and re-checked in the UI** |

The third is architecturally the *best* of the three — it consumes an
attestation rather than computing one. But its comment reads *"unhealthy
domains prevent the calm claim even when structural completeness is
satisfied"*, which means it assumes a backend `Attestation` where
`complete: true` can coexist with unhealthy domains. **Neither C19 nor C20
can produce that value.** Three components, three models.

#### R70 · The two deliverables do not connect — **Medium**

Both archives sit in one folder and neither consumes the other.

- C20 defines `PresenceSnapshot` — eight rich fields.
- `kd/src/kernel/types.ts:263` defines `PresenceState = 'idle' | 'thinking' | 'speaking' | 'awaiting'` — a four-value enum for the presence sigil animation.

Nothing in the desktop prototype imports the presence package. The health
report's §6 item 6 states it plainly — *"nothing consumes this layer yet"*
— and that is accurate. The observation is that a **second, unrelated
presence contract already exists** in the adjacent deliverable.

#### R71 · The UI is specified against components Sprint 1 does not have — **Medium**

`KernelClient` declares methods for the **Standing Rule Engine**
(`listRuleProposals`, `grantRule`, `setRuleStatus`, `renewRule`,
`getBoundary`), **Memory M1–M5** (`queryMemory`), **Dependency Audit**,
and **Disclosures**. None exists in Sprint 1. The Kernel Specification
§14 R10 records that §7.3's A4 *"has no attestor until C1 ships"* — the
Rule Engine is explicitly future work.

The prototype degrades honestly (`not-implemented` with the reason shown),
which is the right behaviour and is documented in
`BACKEND_CONTRACT_REQUESTS.md`. The finding is one of scope: **the UI is
built against a system substantially larger than the approved Sprint 1
plan**, and `BACKEND_CONTRACT_REQUESTS.md` reads as a set of requirements
on the Kernel that no ratified document has agreed to.

#### R72 · VEDA 04 E2 divergence — **Low**

VEDA 04 E2 requires the demo tenant be *"Fixed outcomes over real data
shape, labelled as such. **A first-class runtime mode, not a fixtures
file.**"* The prototype ships a 61 KB `fixtures.ts`. Labelling is
satisfied (`kind: 'mock'`); the *"not a fixtures file"* clause is not.

---

## 10 · Test Quality Review

**183 assertions across 40 suites, executed twice by the auditor with
identical results.** No mocked constitutional behaviour; no real clock; no
I/O; no timers.

| Strength | Evidence |
|---|---|
| Adversarial input coverage | null, undefined, primitives, arrays, `{}`, unknown type, empty `at`, per-type wrong-field-type — all rejected |
| Order-independence proven, not assumed | Active-mission precedence tested via two insertion orders |
| Boundary conditions tested | `secondsBetween` negative clamp, reasoning staleness at the exact threshold, `possiblyStale` boundary |
| Purity proven behaviourally | Fold input never mutated; new identity every time; held snapshots stable across later folds |
| Disclosure locked open | A test asserts `TERMINOLOGY_RECONCILIATION` stays non-empty — the disclosure cannot be quietly deleted |
| Negative surface assertion | `contract.test.ts` asserts the public surface exports nothing matching `/execute\|invoke\|authorize\|mutate\|write\|commit\|dispatch/i` |

### The gaps

**The suite does not test the empty layer.** Every calm test seeds
coverage first. R64 is reachable in three lines and no test reaches it —
this is the single most valuable test the suite is missing, and its
absence is why a strong suite coexists with a critical defect.

**No test asserts the future-timestamp case** (R65, probe 4).

**No typecheck has run**, and HyperAgent discloses this (§6 item 2). Node
strips types; it does not check them. **183 passing tests prove runtime
behaviour, not type correctness.** The auditor confirms the disclosure and
could not run `tsc` either — the toolchain is unavailable here. Recorded
as **R73 (Medium)**.

---

## 11 · New Risks

| ID | Risk | Severity | Blocks Rule 001? |
|---|---|---|---|
| **R64** | A Presence Layer told nothing reports `calm: true` | **Critical** | **Yes** |
| **R65** | C20 and C19 disagree on the D7 gate in three measurable ways | **High** | **Yes** |
| **R66** | Four of five calm blockers have no frozen source; `execution-active` contradicts the layer's own rationale | Medium | No |
| **R67** | The purity guard is textual; four evasions proved | Medium | No |
| **R68** | `kd/src/kernel/` re-declares Kernel vocabulary; `Attestation` collides with frozen C7 | **High** | No |
| **R69** | A third D7 gate with a fourth semantics | **High** | No |
| **R70** | Two unrelated presence contracts in adjacent deliverables | Medium | No |
| **R71** | The UI is specified against components Sprint 1 does not have | Medium | No |
| **R72** | VEDA 04 E2 — *"not a fixtures file"* not satisfied | Low | No |
| **R73** | No typecheck has run | Medium | No |

### R64 — **Critical · blocks**

**Why it matters.** The layer emits the product's highest-liability
sentence in the state where it has the least evidence for it. VEDA 04 D7
calls the silent gap *"the single failure most likely to end a customer
relationship permanently."* It is reachable in three lines, from the
default constructor, with no configuration. `possiblyStale` does not fire,
and `meta` is not founder-facing.

**Blocks Rule 001:** yes. A milestone cannot be declared on a component
that makes the calm claim without coverage.

### R65 — **High · blocks**

**Why it matters.** D7 is one gate. Two implementations answering
differently means the honest answer depends on which one a surface asks —
and the divergences are all in the unsafe direction for C20 (empty set
calm, boundary fresh, future stamps fresh). §1.2's *"two opinions about
authorization is the failure the entire Trust Spine exists to prevent"*
applies with equal force to the calm gate.

**Blocks Rule 001:** yes, until one owner is named. This is a founder
decision about which implementation is canonical, not an engineering fix.

### R66 · R67 · R68 · R69 · R70 · R71 · R72 · R73 — do not block

Each is recorded above with its evidence. R66 needs an ADR. R68–R72 concern
the desktop prototype, which is a prototype and is not on any Rule 001
path. R73 needs a toolchain, not a decision.

---

## 12 · What the verdict turns on

**Two changes, both small, would move this to PASS WITH OBSERVATIONS:**

1. **R64** — completeness must require at least one accounted-for domain.
   C19 already expresses the rule: `complete = bool(statuses) and not gaps`.
2. **R65** — one owner named for the D7 gate, and the other aligned to it.

Neither is a redesign. The union type, the containment, the no-clock
discipline, the carried-never-generated reasoning and the grounding
disclosure are all sound and should survive unchanged.

**No implementation change is recommended or made here.** The auditor did
not modify the artefacts, and §12 states what the verdict turns on because
the brief asks what would make the work correct — not because a repair was
attempted.

---

## 13 · Credit where it is due

Recorded because an audit that reports only defects misrepresents the work.

**The grounding disclosure is exemplary.** `types.ts` opens by stating
that none of the six grounding documents was provided and that every
identifier is provisional; `TERMINOLOGY_RECONCILIATION` lists twelve
assumptions each with the question to put to the specification; and a test
keeps it from being deleted. **The first question it asks is whether
ADR-0022/0023 already own this contract, with the instruction to stop if
so.** That is exactly how an agent should behave when it is building
without ground, and it is why this audit could be precise rather than
speculative.

**The union-over-boolean decision is right**, and for the stated reason: a
boolean can be set from anywhere; a union member must be constructed. It
is the same discipline C19 applies to `CalmState` and the Kernel applies to
`intent_id`. **R64 is not a failure of that design — it is a gap in what
the gate has to check.**

---

*End of Audit — Read-Only. No files modified, no refactoring, no commits,
no tags. Archives were extracted to a scratchpad outside the repository;
guard-evasion tests ran against throwaway copies and never touched the
audited packages.*
