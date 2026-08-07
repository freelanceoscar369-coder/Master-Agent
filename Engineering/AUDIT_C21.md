# Engineering Audit — C21 Founder Conversation Surface

**Artefact:** `VEDRA_PROJECT/01_Assets/UI-UX/kalpavriksha-C21-surface.zip`
(cross-referenced against `kalpavriksha-C20-presence.zip` and
`kalpavriksha-C19A.zip` in the same folder, both consumed by C21 as
sibling packages)
**Role:** Independent Architecture Auditor. The auditor did not implement C21.
**Audit Date:** 2026-08-06
**Repository:** `HEAD` = `01497c3`, tag `kalpavriksha-s1-c18.0`. Nothing modified.
**Method:** All three archives extracted to a scratchpad outside the
repository, assembled as sibling packages (`surface/`, `presence/`,
`desktop/`) exactly as C21's own relative imports require. Tests and the
boundary guard were **executed independently** on this platform. No file
inside any archive was edited before or during execution; a breach-proof
copy was made separately to test the guard's behaviour under injected
violations.

---

## Executive Verdict

> ## **PASS WITH OBSERVATIONS**

The presentation logic is disciplined and its two hardest rules —
non-synthesis and inertness of the founder actions — are enforced
structurally and proven by test, independently re-run here with identical
results. **No constitutional violation was found inside `surface/`
itself.**

Two findings prevent an unqualified PASS, and one of them is severe enough
to name plainly: **the boundary guard this milestone cites as evidence
does not run on this platform.** It reports `RESULT: BOUNDED` after
scanning zero files, and continues to report `BOUNDED` when a `fetch()`
call and a literal `import ... from 'electron'` are injected into a copy.
The guard is not lying about what it found — it found nothing, because it
looked at nothing. Every "0 findings" claim in `HEALTH_C21.md` attributed
to this guard is currently **unverifiable, not verified,** on the
environment this audit was performed on.

The second finding is architectural rather than a defect in `surface/`:
**"consumes Runtime Bridge only" cannot be verified as true, because
nothing in the reachable stack consumes the Runtime Bridge at all** — not
C21, and not the C19A layer it will eventually be wired through. This is
recorded rather than treated as disqualifying, because C21's own design
correctly keeps the surface ignorant of transport (`onSend` is an
injected callback), and the absence of a real bridge is inherited from
C19A, not introduced here.

---

## 1 · What was verified, and how

| Check | Command | Result |
|---|---|---|
| Test suite | `node --test 'tests/**/*.test.ts'` (siblings assembled) | **127 pass · 0 fail · 30 suites** — health report accurate |
| Boundary guard | `node tests/boundary-guard.mjs` | **Reported BOUNDED, but scanned 0 modules** — see §6 |
| Guard under real breach | `fetch(`, `import 'electron'` injected into a copy | **Still BOUNDED, exit 0** — false pass reproduced |
| Module/import counts | manual `find` + `grep` | **12 `.ts`/`.tsx` files, 30 import lines** — matches the health report's claimed guard output, confirming the guard *would* have found the right surface if its path resolution worked |
| Runtime dependencies | `package.json` | `dependencies: {}`, only `react` as a peer — accurate |
| Frozen directories | `git diff kalpavriksha-s1-c18.0` | **Empty** — nothing in the Python repository touched |

Node v24.15.0, native TypeScript stripping.

---

## 2 · Constitutional Compliance

The brief names eight grounding sources. **HyperAgent had two** —
the UI prototype and their own C19A/C20 work — and disclosed the gap
explicitly rather than filling it by assumption (`HEALTH_C21.md` §1). This
auditor confirms the disclosure is accurate: nothing in `surface/`
references a VEDA concept, a Kernel Specification section, or an ADR
number, by name or by paraphrase.

**Consequence, stated plainly rather than assumed away:** this component's
compliance with the Kernel Specification, ADR-0022 and ADR-0023 cannot be
positively confirmed, because it was built without them and references
none of their vocabulary to check against. What *can* be confirmed —
and was — is that it introduces no vocabulary of its own that would
compete with theirs. §5 details this.

---

## 3 · Business Logic, Execution, Authorization, Mutation — searched, none found

| Prohibition | Verdict | Evidence |
|---|---|---|
| Business logic | ✅ absent | Every field in `presenceView.ts` and `conversationView.ts` is either carried verbatim or drawn from a frozen 19-label allowlist. No branch decides anything about the world — only about which pre-computed field to show |
| Execution | ✅ absent | No executor, no dispatch, no queue. `Composer`'s `onSubmit` calls a prop; nothing runs |
| Authorization | ✅ absent | Grepped for `RefusalReason`, `Warrant`, `authorize`, `KernelRefusal`, `ApiResponse`, `ExecutionOutcome` across all twelve source files — **zero matches** |
| Runtime mutation | ✅ absent | `ConversationSurface.tsx`'s own comment states it explicitly: *"Does NOT append an entry itself — entries arrive from outside only."* `onSend` dispatches text upward; no local list is appended to |
| Network / storage side effects | ✅ absent | Grepped for `fetch(`, `localStorage`, `sessionStorage`, `indexedDB` — zero matches. The two `useEffect` hooks that exist (`Composer.tsx`, `ConversationArea.tsx`) are DOM-only: textarea auto-grow and scroll-to-bottom |

**This section passes cleanly and was the easiest to confirm** — the
absence is structural, not merely a claim.

---

## 4 · Consumes Presence Layer only — largely holds, with a naming caveat

C21 imports two things across a package boundary:

```
'../../../presence/src/index.ts'          — C20, PresenceSnapshot / CalmState / VigilanceState
'../../../desktop/src/types/execution.ts' — C19A, ConversationEntry / EntryRole
```

**The second import is not the Presence Layer, and it is not the real
Python Runtime Bridge either.** It is `desktop/src/types/execution.ts` —
a file inside the C19A prototype, which is a different artefact from
`src/master_agent/desktop/` in the actual repository (the machine-inventory
Executive audited separately this session) and different again from
`src/master_agent/runtime_bridge/` (C18, shipped). The name `desktop`
collides across three unrelated things in this project's total surface
area; none of the three is confused with another *inside* C21's own code,
but a reader assembling the full picture must not assume `desktop/` means
the same thing twice.

**`execution.ts` is declared types only — no logic, no runtime import,
verified by reading it.** Its own header carries the same grounding
disclosure discipline as C20's: *"I do not have access to
kalpavriksha-s1-c18.0, the Kernel API surface, the Runtime Bridge... every
identifier below is PROVISIONAL."* So C21 is one hop away from a type file
that is itself explicitly unreconciled against the real system.

**Net position:** C21 consumes exactly two things, both of which are
sibling front-end artefacts rather than the Python system, and one of
those two is types-only rather than the Presence Layer proper. This is
narrower than "consumes Presence Layer only" states but not a violation of
it — `ConversationEntry` is data the Presence Layer does not carry (C20's
`PresenceSnapshot` has no conversation transcript field), so a second type
source was unavoidable if a conversation is to render at all.

---

## 5 · Kernel vocabulary — none duplicated, because none is defined

Checked by direct search across every `.ts`/`.tsx` file in `surface/src/`
for `RefusalReason`, `Warrant`, `authorize`, `KernelRefusal`, `ApiResponse`,
`ExecutionOutcome` — **zero matches**, confirming `HEALTH_C21.md`'s claim
in §1: *"C21 introduces no new domain vocabulary at all."*

The only new types this package defines are view models
(`PresenceView`, `ViewField`, `ConversationRow`) and configuration
(`FounderModeConfig`), none of which name a Kernel concept. This is the
correct answer to the question the brief asks, and it holds.

---

## 6 · No Runtime Mutation, verified — and the boundary guard finding

### 6.1 What the guard is supposed to prove, and what it actually proved here

`tests/boundary-guard.mjs` scans `src/**/*.{ts,tsx}` for external imports
and a list of forbidden patterns (`fetch(`, `electron`, `ipcRenderer`,
`webContents`, `WebSocket`, greeting language, and others), and is the
mechanism `HEALTH_C21.md` cites as evidence for *"12 modules, 30 imports,
0 findings"* and for most of the *"✅ absent"* rows in its own §5 table.

**Independently executed on this platform, it reports:**

```
Modules scanned : 0
Import lines    : 0
Findings        : none
RESULT: BOUNDED
```

The repository genuinely contains **12** `.ts`/`.tsx` files and **30**
top-level import lines under `surface/src/` — confirmed by direct count,
and matching the health report's numbers exactly. **The guard scanned
none of them.**

### 6.2 Root cause, reproduced

```js
const srcDir = join(new URL('.', import.meta.url).pathname, '..', 'src');
```

On Windows, `import.meta.url`'s `.pathname` carries a leading slash before
the drive letter (`/C:/Users/...`). `path.join` does not correct this, and
the resulting string — reproduced directly —

```
"\\C:\\Users\\DELL\\...\\src"
```

— does not exist. `walk()`'s own `try { readdirSync(dir) } catch { return
[] }` swallows the resulting `ENOENT` **silently**, so the script does not
crash; it reports success having examined nothing.

**This is not a hypothetical.** C20's `purity-guard.mjs`, audited
separately this session, resolves the identical kind of path using
`fileURLToPath(import.meta.url)` and works correctly on this same
platform — 6 modules scanned, real findings when breaches were injected.
C21's guard uses the raw `.pathname` instead, which is the one substitution
that breaks.

### 6.3 The practical consequence, proven rather than inferred

A copy of `surface/` was made and a literal `import ... from 'electron'`
plus a `fetch()` call were appended to `Composer.tsx` — exactly the class
of violation §5 of the health report claims the guard prevents. The guard
was re-run:

```
Modules scanned : 0
Findings        : none
RESULT: BOUNDED
```

**It did not catch either.** The guard currently cannot fail on this
platform, regardless of what the source contains.

### 6.4 What this does and does not mean

**It does not mean a violation exists.** Every prohibited pattern the
guard is meant to catch was independently searched for by this auditor
using direct grep across the real source (§3, §5), and none was found.
**The absence of network calls, Electron APIs and forbidden imports in
`surface/` is confirmed by this audit through other means.**

**It does mean the specific claim "the guard verified this" is false on
this platform**, for every one of the eleven rows in `HEALTH_C21.md` §5
that cites the guard as evidence. The health report's own numbers (12
modules, 30 imports) suggest the guard *was* run somewhere it produced a
real scan — but not here, and this is the platform Rule 001 verification
runs on for this project.

---

## 7 · No Synthetic AI Text, No Fabricated Founder Messages

**Independently re-verified, not merely re-read.**

`tests/noSynthesis.test.ts` walks a projected view across nine snapshot
variants and asserts every emitted string is traceable to either (a)
verbatim snapshot content or (b) the frozen `STATIC_LABELS` allowlist,
plus three explicit negative assertions:

```
/good (morning|afternoon|evening)/i    — no greeting
/probably|likely|seems|appears|might|should be|I think/i  — no hedging
/thinking|working on it|please wait/i  — no invented activity
```

All 127 tests, including these, passed on independent execution.

**The empty-conversation state was checked by hand as well as by test**:
`EMPTY_CONVERSATION` renders *"No conversation yet."* / *"Anything said
here will appear in this column, in order."* — not a greeting. The health
report's own framing of this (§4: *"the honest version is quieter than
the synthesized version"*) is accurate to what the code does.

`conversationView.ts`'s `projectConversation` **cannot construct an
assistant row that was not already in `entries`** — it maps one-to-one
over its input array and invents no new element. Confirmed by reading
the function: there is no code path that appends.

---

## 8 · No Dashboard Regression

**Cannot regress what it does not touch.** `surface/` contains no
`Dashboard` component, and the extracted archive modifies no file inside
`desktop/src/features/dashboard/` (the actual Dashboard implementation,
present in the separate C19A archive). `git diff kalpavriksha-s1-c18.0`
confirms nothing in the Python repository was touched either.

`MissionStrip.tsx` and `surface.css` both carry explicit, load-bearing
comments forbidding a change toward card/tile/grid rendering — *"CARD/TILE
RENDERING IS FORBIDDEN BY THE BRIEF'S 'NO KPI WALL' RULE… Violating this
constraint is an explicit brief failure."* Read directly: the component is
a single horizontal row of `label / value` pairs with hairline separators,
which is what the comment promises.

---

## 9 · No Sprint 2 Leakage

Searched for `Sprint 2`, `sprint2`, `v2`, `phase 2` — no matches in
`surface/src`. The only forward references found are to **C22**, and each
is a scope boundary rather than an implementation: `founderMode.ts`
explicitly declines to implement alias matching, stating *"answering that
is C22's or later"*; `FounderActions.tsx` explicitly declines to wire any
button, stating connecting them *"belongs to a future cycle, not C21."*
Both are enforced by tests (`ALL_ACTIONS_INERT`, the no-matching-capability
assertion in `founderMode.test.ts`) rather than left as comments alone.

**No Sprint 2 or later work is present in executable form.**

---

## 10 · Independent Test Verification

**127 assertions across 30 suites, executed on this platform with
sibling packages assembled exactly as the imports require, identical
result to the health report.**

| File | What was independently confirmed |
|---|---|
| `presenceView.test.ts` | Totality across 9 snapshot variants; every label from the allowlist; verbatim carriage of title/statement/activity line/reasoning text; all null paths; `absentPresence`; fixed strip order; purity (no snapshot mutation) |
| `noSynthesis.test.ts` | The traceability walk and all three forbidden-language regexes |
| `conversationView.test.ts` | Role→author mapping; strict, untrimmed verbatim text equality; streaming/superseded flags; no fabricated assistant row; empty state has no greeting |
| `founderMode.test.ts` | All five validation codes; the length boundary at exactly `MAX_NAME_LENGTH`; case-insensitive duplicate detection; `readFounderMode` against malformed input without throwing; lossless round-trip; **no matching capability exported** |
| `founderActions.test.ts` | Exactly four actions, correct keys/order, non-empty labels/reasons; **no function-valued properties on any action object** |

**Tests build real C20 snapshots via `createPresenceLayer()`** rather than
hand-constructed fixtures, which means the projection was exercised
against genuine layer output — the same discipline this auditor credited
in the C20 audit, and it holds here too.

**One honest limitation, disclosed by HyperAgent and confirmed by this
auditor rather than repeated on trust:** the seven `.tsx` components have
never been rendered, mounted, or type-checked. `npm test` exercises
`src/presentation` and `src/config` in full; it does not execute JSX.
`tsc` was unavailable in this environment as well, so type correctness —
as opposed to the runtime behaviour of the non-component logic — remains
unverified by anyone to date.

---

## 11 · Findings

| ID | Finding | Severity | Blocks Rule 001? |
|---|---|---|
| **R74** | The boundary guard does not scan any file on this platform, due to a Windows path-resolution defect (`.pathname` used instead of `fileURLToPath`), and reports a false `BOUNDED` result even with an `electron` import and a `fetch()` call present | **High** | **Yes, for the guard's evidentiary value.** Does not indicate an actual violation — none was found by direct search — but the milestone's own automated check cannot currently be trusted to catch a future one |
| **R75** | "Consumes Runtime Bridge only" cannot be verified as true anywhere in the reachable stack. C21 imports C20 (Presence) and a C19A type-only file; the one module that would eventually reach the real Runtime Bridge (`desktop/src/services/runtimeClient.ts`, C19A) is an explicit stub returning `not-wired` and performing no I/O by design | **Medium** | **No.** This is inherited scope, not a defect introduced by C21, and the stub's honesty is itself correct design — recorded so the chain's actual reach is not assumed from the diagram in `HEALTH_C21.md` §8 |
| **R76** | Six of eight grounding sources were unavailable to the implementer, disclosed accurately in `HEALTH_C21.md` §1. Compliance with the Kernel Specification, ADR-0022 and ADR-0023 specifically therefore cannot be positively confirmed — only the absence of competing vocabulary can be, and was | Medium | No — this is a disclosed gap, not a violation, and matches the same pattern already recorded for C20 |
| **R77** | The `.tsx` components are untested — never rendered, mounted, or type-checked in any environment to date, by the implementer's own account and unchanged by this audit | Medium | No — the non-component logic (100% of the constitutional surface: projection, validation, inertness) is tested; the JSX is presentation wiring only |
| **R78** | No `tsc` run exists anywhere for this package; 127 passing tests prove runtime behaviour of stripped `.ts`, not type correctness, and say nothing about `.tsx` at all | Low | No |
| **R79** | The name `desktop/` refers to three unrelated things across the project's total surface area at this point — the real Python Executive (`src/master_agent/desktop/`), C18's Runtime Bridge target, and the C19A TypeScript prototype C21 actually imports from. Not a collision *inside* C21, but a hazard for whoever integrates these next | Low | No |

**R74 is the finding that matters most.** It does not indicate C21 is
unsafe — every property the guard exists to enforce was independently
confirmed true by direct inspection in §3, §5 and §7 of this audit. It
means the specific instrument cited as proof does not currently produce
proof on this platform, and should not be relied on again until fixed.

---

## 12 · Credit

The non-synthesis discipline is the strongest part of this delivery and
was verified rather than taken on trust: every string in the view layer
traces to either verbatim snapshot content or one of nineteen frozen
labels, checked by a test that walks nine snapshot shapes and by three
explicit bans on greeting, hedging, and invented-activity language. The
reasoning in `HEALTH_C21.md` §4 — that the honest quiet opening is correct
even though it is less immediately impressive than a synthesized greeting
— is sound, and the code delivers exactly what it argues for.

The founder-actions inertness is enforced the same way: data-driven
buttons with no `onClick` anywhere in the file, backed by a test that
inspects the action objects themselves for function-valued properties
rather than trusting the JSX not to have one.

Both are the kind of guarantee this project has learned, component by
component this Sprint, to make structural rather than aspirational. C21
continues that pattern correctly in the two places that mattered most.

---

*End of Audit — Read-Only. No files modified, no refactoring, no repairs,
no commits, no tags. Archives were extracted to a scratchpad outside the
repository; the guard-breach test ran against a throwaway copy and never
touched the audited package.*
