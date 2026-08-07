# Health Report — Sprint 1, Component 23: Founder Runtime Wiring

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-06
**Status:** Complete. **Not committed, not tagged, no Rule 001.**
**Built on:** `kalpavriksha-s1-c18.0` — commit `01497c3`, treated as frozen. Every file below is new; nothing at or below that tag was touched.
**Ground:** Project Brain · C1–C22 · C19 Vigilance (`vigilance/`) · C22 Environment Intelligence (`environment_intelligence/`) · C20 Presence Layer and C21 Founder Surface (TypeScript archives, read) · C18 Runtime Bridge (read, not imported) · `memory/conversation.py`.

**Constraints honoured:** no frozen component modified · no new architecture ·
no new intelligence · no UI redesign · no dashboard change · no execution ·
no AI call · no invented response · no Sprint 2.

---

## 1 · Read this first — the one judgment call

**This component does not produce a `PresenceSnapshot`, and that is the
central design decision.**

The brief requires the Founder UI to be able to receive `PresenceSnapshot`,
`EnvironmentSummary`, `CapabilityGraph`, `UserProfile` and `PreferenceModel`
**"without duplicating logic."** Four of those five are C22 contracts and
are carried verbatim. The fifth is not a stored value anywhere — it is
*derived*, by the Presence Layer, from observations it is fed. C20's own
`observations.ts` states the arrangement without hedging:

> *"This layer has no reach… Everything it knows, it was told.
> `Observation` is the complete vocabulary of what it can be told."*

and its terminology-reconciliation list asks the open question directly:
*"Is the Presence Layer fed by the Coordinator, or expected to pull? This
implementation only accepts being fed — it cannot call anything."*

**It is fed. C23 is the feed.** Writing a Python `PresenceSnapshot` would
have meant a second implementation of `deriveCalm`, `deriveVigilance`,
`deriveActivity` and `deriveExecution` — four derivations that already
exist, in the component that owns them. That is precisely the duplication
the brief forbids, and it would have produced two answers to *"may we say
'Nothing needs you'?"* in one system.

So the Founder UI receives its `PresenceSnapshot` from the Presence Layer it
already has. What changed is that the Presence Layer now has something real
to describe.

---

## 2 · What was built

| File | | |
|---|---|---|
| `src/master_agent/founder_runtime/presence_feed.py` | new | 203 lines, **40 AST statements** |
| `src/master_agent/founder_runtime/projection.py` | new | 115 lines, **18 AST statements** |
| `src/master_agent/founder_runtime/wiring.py` | new | 409 lines, **118 AST statements** |
| `src/master_agent/founder_runtime/__init__.py` | new | 15 exported names |
| `tests/test_founder_runtime.py` | new | 910 lines, **83 tests** |

**182 statements of implementation. 100% line coverage.**

```
   C22 Environment Intelligence      C19 Vigilance      Conversation Memory
              │                            │                     │
              └──────────────┬─────────────┴──────────┬──────────┘
                             ▼                        ▼
                    C23 Founder Runtime  ←  composition · projection
                             │
                             ▼   one JSON envelope
                    C20 Presence Layer  →  PresenceSnapshot
                             │
                             ▼
                    C21 Founder Surface
```

**Placement:** `founder_runtime/`, deliberately not inside `runtime/`
(MB024's Runtime Engine), not `runtime_bridge/` (C18, frozen), and not
`dashboard/` (the terminal founder page, which this does not touch). The
C21 audit's R79 already recorded that `desktop/` names three unrelated
things in this project; a fourth collision on `runtime` was avoidable and
was avoided.

---

## 3 · The five contracts, and where each one comes from

| Contract the brief names | Where it arrives | Produced by |
|---|---|---|
| `EnvironmentSummary` | `payload.environment.summary` | C22, verbatim |
| `CapabilityGraph` | `payload.environment.graph` | C22, verbatim |
| `UserProfile` | `payload.environment.profile` | C22, verbatim |
| `PreferenceModel` | `payload.environment.preferences` | C22, verbatim |
| `PresenceSnapshot` | derived by C20 from `payload.presence.feed.observations` | C20, unchanged |

The four environment sections arrive under **C22's own section names**, not
renamed to match the brief's type names. C18 already recorded the reason it
uses the Kernel API's own parameter names — *"there is no translation table
to drift"* — and the same applies here. The correspondence is held as
`CONTRACT_SECTIONS`, a **test fixture rather than a transform**: a test
asserts each named section exists in a real projection, so a rename in C22
fails loudly here instead of arriving at the surface as an empty panel.

`environment_projection()` is one line — `intelligence.as_dict()` — and a
test asserts equality with it. There is no second opinion about any
inference, any confidence, or any piece of evidence.

---

## 4 · The presence feed — transcription, not derivation

Two observation types are emitted and no others, because C19 is a coverage
service and has nothing to say about missions, executions, approvals,
actions, reasoning or failures. A test asserts the emitted set is a subset
of `PRESENCE_OBSERVATION_TYPES`.

| Observation | Every field's source |
|---|---|
| `coverage.expected` | `Coverage.domains[].name`, stamped `Coverage.attested_at` |
| `coverage.reported` | one `DomainStatus`, stamped **its own** `lastChecked` |

### 4.1 The stamping rule is load-bearing

C20 sets `lastCheckedAt` from the observation's own `at`
(`state.ts`, `case 'coverage.reported'`). Three consequences follow, and all
three are tested:

**A never-checked domain gets no report.** It appears in
`coverage.expected` alone, and C20's `deriveVigilance` turns that into a
`never-reported` gap — the same sentence C19's `never_checked` gap already
says. Stamping it with the attestation moment would silently convert *"I
haven't checked"* into *"I checked and it is old"*, which VEDA 04 §5 makes
*"a data property, not a phrasing choice."*

**A reported domain is stamped with `lastChecked`, not with the attestation
moment.** A test asserts the two differ when the check was earlier, which is
the case where getting it wrong would make a stale domain look fresh.

**`freshnessSeconds` comes from the registry, or is `null`.** `Coverage`
does not carry a freshness window, so the optional `DomainRegistry` is read
for that one field. Absent it, `null` is emitted and **C20 applies its own
default** — that threshold is presentation policy owned by the layer that
renders it.

### 4.2 Agreement with C19, asserted without re-implementing C20

`deriveVigilance` is not reproduced in a test — that would have been the
duplication in another costume. What is asserted is that the *input* to each
of C20's three gap reasons is present whenever C19 found the corresponding
gap: `never_checked` → expected-but-unreported, `unhealthy` → a report
saying `healthy: false`, `stale` → a report whose age exceeds its window.

### 4.3 One transcription of C20's validator exists, and only in the tests

`accepted_by_presence_layer()` in `tests/test_founder_runtime.py` is a
restricted port of C20's `isValidObservation`, covering the two emitted
types. It lives in the suite deliberately: a copy in `src/` would be the
second implementation the brief forbids, but without a copy *somewhere*,
nothing in this repository can prove the feed is acceptable to the layer it
was built for. It is the only place the two systems are compared, and it is
named so a reader finds it.

---

## 5 · Finding — an unfed Presence Layer says *"Nothing needs you."*

**Severity: High. Recorded, not repaired — repairing it is C20's, not
C23's.**

C20's `deriveVigilance` over an empty `ObservedState` finds no expected
domains, no coverage records and therefore **no gaps**, and returns
`{complete: true}`. `deriveCalm` then finds no blockers and returns:

```ts
{ calm: true, since: …, statement: 'Nothing needs you.' }
```

A Presence Layer that has never been fed anything therefore makes the
product's highest-value claim over nothing at all. VEDA 04 D7 calls exactly
this *"the single failure most likely to end a customer relationship
permanently"*, and C19 exists to prevent it — its own answer for an empty
registry is `complete=False`, with the gap *"no domain is being watched, so
coverage proves nothing."*

**What C23 does about it, and what it deliberately does not.**

*Does:* refuses to feed an empty coverage at all. `presence_feed()` returns
no observations and carries C19's own sentence as `absent_reason`. Feeding
`coverage.expected` with an empty list would have walked the Presence Layer
straight into the defect while looking like wiring.

*Does not:* invent a placeholder domain to force a gap. A fabricated domain
name reaches a founder-facing line inside `deriveVigilance`
(`"${domain} is watched but has never reported"`), and a lie told to prevent
a lie is still one.

*Compensates:* **C19's authoritative answer travels beside the feed.**
`payload.presence.coverage` is `Coverage.as_dict()` verbatim, `complete`
included. A surface never has to take a re-derivation's word for whether the
sentence may be spoken.

**What is required of whoever wires the surface:** the calm sentence must be
gated on `presence.coverage.complete`, not on `snapshot.calm.calm` alone,
until C20 treats an unfed layer as incomplete. That is a UI wiring
requirement and belongs to HyperAgent; it is stated here so it is not
discovered later.

This continues the register from the C21 audit, which ended at R79.

| ID | Finding | Severity | Blocks Rule 001? |
|---|---|---|---|
| **R80** | An unfed C20 Presence Layer derives `complete: true` and states *"Nothing needs you."* — VEDA 04 D7's named failure. C23 refuses to feed an empty coverage and carries C19's `complete` beside the feed, but cannot fix the layer | **High** | **No** — the defect is in C20, which is not in this repository and not tagged |

---

## 6 · The conversation projection cannot speak

`ConversationMemory` (Layer 1) holds turns whose speaker is `user` or
`system`. C21's row shape admits a third role, `assistant`, and **nothing in
this path may ever produce one.**

C21's own suite already enforces the mirror of this — `projectConversation`
*"cannot construct an assistant row that was not already in `entries`"* —
and the C21 audit re-verified it independently. If this projection could
mint an `assistant` role, that guarantee would be defeated one layer below
where it is tested. So any speaker that is not `user` maps to `system`,
`assistant` is unreachable by construction, and a parametrised test asserts
it across seven speaker strings including `"assistant"` itself.

Every other field the surface accepts is reported **absent rather than
guessed**: a conversation turn is not an execution, has no execution id, is
not streaming, was superseded by nothing, and carries no mission card.
Entry identity is the turn's position (`turn-1`, `turn-2`) — addressing, not
identity invention, and stable for a given transcript.

Text is carried **verbatim and untrimmed**, because C21 asserts strict
untrimmed equality against what it was given and a projection that tidied
whitespace here would fail it from below.

---

## 7 · Why this door does not hold the Kernel

C18's Runtime Bridge is the door to **authority** — `authorize`, `attempt`,
`settle`, `invalidate`, `status`. This is the door to **observation**, and
they are kept apart structurally rather than by convention: a surface
holding a Kernel reference can authorize whatever its docstring says; one
holding none cannot.

`founder_runtime/` therefore **imports no frozen package** —
`foundation`, `kernel`, `ledger`, `coordinator`, `api`, `runtime_bridge` are
all asserted absent from its import graph by AST. (`vigilance` depends on
C1's `Clock` and reaches `foundation.clock` transitively; that is C19's
declared and ratified dependency, not one C23 introduces.)

The consequence is stated rather than hidden. `sources()` always reports a
fourth entry:

```
kernel_authority · present: false
  "authority travels the Runtime Bridge and is not reachable from this
   surface by construction; nothing sent here can start, approve or cancel
   work"
```

This is the honest answer to the C21 audit's **R75** — *"consumes Runtime
Bridge only cannot be verified as true anywhere in the reachable stack."*
It still cannot be verified, because C23 deliberately does not consume it;
the difference is that the surface can now say so from data instead of
inferring it from a call that quietly did nothing.

**Nothing the founder does on this surface can start work.** Send, approve,
cancel and retry are unimplemented here on purpose. They belong to a brief
that wires C18, and that brief has not been issued.

---

## 8 · The wire shape is C18's, not a new one

```
   in    {"operation": "snapshot"}
   out   {"operation": "snapshot", "kind": "ok",    "payload": {…}}
   out   {"operation": "snapshot", "kind": "error", "payload": {"type", "message"}}
```

Same three keys; an error carries **its own class name** rather than a
transport taxonomy, following C17's convention. **No status code, no
envelope version, no request id, no timestamp** — C18's reason holds
unchanged, and a test asserts the envelope has exactly three keys.

The operation set is this door's own and closed: `snapshot` · `environment`
· `presence` · `conversation` · `status`. `FounderOperation` is a separate
enum from C17's `Operation` precisely so that a founder envelope naming
`authorize` is an error — asserted by a test over all four Kernel
operations.

Every operation is nullary, so a non-empty `arguments` map is **refused
rather than ignored**: a caller passing one is asking for something
parameterised, and silently dropping it would answer a different question
than the one asked.

---

## 9 · Absence

Every section this runtime was not given arrives as `null`, and `sources`
says which and why, in the words of whichever component was missing. This
follows the discipline MB032 established for the same class of problem:
*"nothing has scanned yet"* is reported as absence rather than assumed
present.

An unwired `FounderRuntime()` still opens, still answers `snapshot`, and
still answers `status` — the founder surface has to be able to open before
an inventory has ever been scanned, and it has to be able to say so.

---

## 10 · Structural guarantees, and the guards that check them

| Guarantee | How it is enforced |
|---|---|
| Never executes | No `executor`, `plugins`, `providers`, `broker`, `ai_infrastructure`, `orchestrator`, `runtime`, `mission_control`, `permissions` import — 11 subsystems checked |
| Never calls AI | Same check; no provider, router or broker is reachable |
| Never authorizes | No frozen package imported — 6 checked |
| Cannot reach the machine | No `subprocess`, `os`, `shutil`, `socket`, `http`, `urllib`, `requests`, `httpx`, `threading`, `asyncio`, `multiprocessing`, `random`, `secrets`, `time`, `pathlib`, `sqlite3`, `winreg`, `ctypes` — 18 names |
| Reads no clock | `datetime.now`, `utcnow`, `time.time`, `time.monotonic`, `clock.now`, `random.random`, `uuid.uuid4` appear in no call expression |
| Duplicates no presence type | `PresenceSnapshot`, `CalmState`, `VigilanceState`, `CurrentActivity`, `ReasoningSummary`, `PendingApproval`, `LastAction`, `SnapshotMeta` declared nowhere |
| Duplicates no vigilance or environment type | `Coverage`, `Domain`, `DomainStatus`, `Gap`, `EnvironmentSummary`, `CapabilityGraph`, `UserProfile`, `PreferenceModel`, `Inference`, `Evidence` declared nowhere |
| Derives nothing itself | `derive_intelligence`, `discover`, `attest`, `createPresenceLayer` called nowhere; `desktop.inventory` and `desktop.catalog` unimported |
| Mutates nothing it was given | A test reads five snapshots and asserts the intelligence, the coverage, the transcript and the registry are unchanged |
| Deterministic | Two runtimes over the same inputs produce equal snapshots; the whole envelope round-trips through `json` |

**Every guard reads executable identifiers via AST, never source text.**
These modules' docstrings name the things they refuse to do — `authorize`,
`assistant`, `PresenceSnapshot`, `execute` — and a text-matching guard would
fail on the explanation rather than on the code.

### 10.1 The guards were proven able to fail

This is the point on which the C21 audit found a milestone's evidence
worthless (**R74**: a boundary guard reporting `BOUNDED` after scanning zero
files, and continuing to report it with an `electron` import and a `fetch()`
call injected). That failure mode was treated as the default assumption
here, not the exception.

Two things were done about it:

**A guard on the guards.** `test_the_package_was_actually_found` asserts at
least four modules were parsed, so a path-resolution defect fails the suite
instead of passing it silently.
`test_the_guards_read_identifiers_not_prose` asserts each forbidden word is
present in the package's prose *and* absent from its identifiers — so a
guard that regressed to text matching would fail immediately.

**A breach was injected and the guards caught it.** A throwaway module
containing `import subprocess`, `from master_agent.kernel import Kernel`,
`datetime.now()` and `class PresenceSnapshot` was added to the package and
the suite re-run:

```
FAILED TestTheGuardsThemselves::test_the_guards_read_identifiers_not_prose
FAILED TestNoFrozenComponentIsReached::test_no_frozen_package_is_imported
FAILED TestNothingExecutes::test_no_module_that_could_reach_the_machine_is_imported
FAILED TestNothingExecutes::test_no_clock_is_read
FAILED TestNothingIsDuplicated::test_no_presence_type_is_redeclared
5 failed, 6 passed
```

The file was then deleted and the suite returned to 83 passing. **The guards
on this platform can fail, and were observed failing for the right
reasons.**

---

## 11 · Test evidence

```
python -m pytest tests/test_founder_runtime.py -q
  83 passed in 0.34s

python -m pytest tests/test_founder_runtime.py --cov=master_agent.founder_runtime
  __init__.py         5 stmts   0 miss  100%
  presence_feed.py   37 stmts   0 miss  100%
  projection.py      15 stmts   0 miss  100%
  wiring.py         106 stmts   0 miss  100%
  TOTAL             163 stmts   0 miss  100%

python -m ruff check src/master_agent/founder_runtime/ tests/test_founder_runtime.py
  All checks passed!
```

**Full suite: 5393 passed, 49 failed, 1 skipped (148s).**

**All 49 failures are pre-existing and unrelated to C23**, verified by
moving both new files out of the tree and re-running the five affected
files: the same 49 fail without C23 present.

| File | Failures | Cause |
|---|---|---|
| `test_missions_console.py` | 27 | `FounderConsole.__init__() got an unexpected keyword argument 'memory'` |
| `test_memory_integration.py` | 16 | same constructor mismatch, plus `remember` unregistered in the console |
| `test_missions_architecture.py` | 4 | same area |
| `test_foundation_clock.py` | 1 | `launcher/boot.py:693` reads ambient `datetime.now()` |
| `test_founder_approval_workflow.py` | 1 | same area |

These sit in the uncommitted MB032–039 working-tree changes to
`launcher/console.py` and `memory/`. They are named rather than absorbed,
and are not C23's to fix under this brief.

---

## 12 · Frozen components

```
git diff --stat kalpavriksha-s1-c18.0 -- foundation kernel ledger coordinator
                                          runtime_bridge api
→ (empty)

git status --porcelain -- foundation kernel ledger coordinator runtime_bridge api
→ (empty)
```

**Byte-identical to the frozen tag, and clean in the working tree.** No
existing file anywhere in the repository was modified by this component; all
five deliverable files are new.

---

## 13 · What this does not do, stated so it is not assumed

1. **No `PresenceSnapshot` is produced in Python.** §1. The Presence Layer
   produces it, from this feed.
2. **No transport is started.** There is no HTTP server, no IPC channel, no
   socket and no process. `handle()` is a function call; wiring it to a
   process boundary is the next step and is not this brief's.
3. **No TypeScript was written or modified.** C20 and C21 live in archives
   under `VEDRA_PROJECT/01_Assets/UI-UX/`, are HyperAgent's artefacts, and
   are not in this repository. C23 reaches the boundary they consume — the
   observation vocabulary and a JSON envelope — and stops there.
4. **Nothing the founder does can start work.** §7.
5. **No mission, execution, approval, action, reasoning or failure
   observation is emitted**, because nothing wired here produces one. When
   Mission Control is wired to this surface, those six observation types are
   already in C20's vocabulary and will need a feed of their own — that is a
   brief, not a gap in this one.
6. **The dashboard is untouched.** `dashboard/founder.py` and its read model
   are unchanged; a `git status` on `dashboard/` shows only the pre-existing
   MB032–039 edits.

---

## 14 · Open questions for the founder

Neither is answered here, because answering either would be a decision this
brief did not grant.

1. **R80's gate.** Should the calm sentence be gated on
   `presence.coverage.complete` in the surface, or should C20 be changed to
   treat an unfed layer as incomplete? The first is a UI wiring rule; the
   second is a change to an artefact outside this repository. §5.
2. **Where the process boundary goes.** `handle()` answers envelopes
   in-process. Whether the Founder UI reaches it over IPC, over a local HTTP
   port, or by embedding Python, is a transport decision with security
   consequences and is not made here.

---

*End of report. Working-directory evidence only. No commits, no tags, no
Rule 001 milestone declared.*
