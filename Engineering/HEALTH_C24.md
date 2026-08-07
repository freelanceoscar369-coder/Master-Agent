# Health Report — Sprint 1, Component 24: Founder Edition Boot Sequence

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-06
**Status:** Complete. **Not committed, not tagged, no Rule 001.**
**Built on:** `kalpavriksha-s1-c18.0` — commit `01497c3`, treated as frozen. Every file below is new; nothing at or below that tag was touched.
**Ground:** Project Brain · C1–C23 · Founder Runtime (`founder_runtime/`, C23) · C19 Vigilance · C22 Environment Intelligence · Presence Layer and Founder Conversation Surface (C20/C21, TypeScript, read) · Existing Desktop Application (`desktop/inventory.py`, `desktop/probe.py`) · `memory/conversation.py`.

**Constraints honoured:** no new architecture · no new intelligence · no
new UI · boot orchestration only · no execution · no AI call · no invented
response · no browser automation · no Sprint 2.

---

## 1 · What was built

| File | | |
|---|---|---|
| `src/master_agent/founder_edition/boot.py` | new | 420 lines, **118 AST statements** |
| `src/master_agent/founder_edition/__init__.py` | new | 8 exported names |
| `tests/test_founder_edition_boot.py` | new | 692 lines, **61 tests** |

**122 statements of implementation. 100% line coverage.**

```python
boot_founder_edition(probe=None, clock=None) -> FounderEditionApp
```

One function. Given nothing, it scans the real machine with the real
clock; given a fake probe and a `ManualClock` (the same injection seam
`desktop/` and `vigilance/` already expose for their own tests), it is
fully deterministic.

**Placement:** a new package, `founder_edition/`, deliberately **not**
inside `founder_runtime/` (C23). Two reasons: C23's own guard suite
(`tests/test_founder_runtime.py::TestNoFrozenComponentIsReached`) scans
every `.py` file under that package and asserts none of them imports
`master_agent.foundation` at all — but this component's Initialize
Presence step must call `VigilanceAttestation.attest()`, which requires a
concrete `Clock`, which lives in `foundation.clock`. Putting the boot
sequence in C23's own directory would have forced editing C23's delivered
test file to carve out an exception, which is not what this brief asked
for and not a decision this brief grants. A sibling package keeps C23
exactly as it shipped and gives this component's own guard suite the room
to state the one exception precisely (§6).

---

## 2 · The seven steps, and what each one actually does

```
   Boot
     │
     ▼
   Initialize Runtime            ← FounderRuntime() opens unwired
     │
     ▼
   Initialize Presence           ← VigilanceAttestation.attest() over the current registry
     │
     ▼
   Initialize Environment Intelligence   ← desktop.inventory.discover() then derive_intelligence()
     │
     ▼
   Initialize Conversation       ← a fresh ConversationMemory
     │
     ▼
   Connect Founder Runtime       ← FounderRuntime(intelligence, coverage, registry, conversation)
     │
     ▼
   Render Founder Surface        ← out of scope: HyperAgent's TypeScript
     │
     ▼
   Ready
```

Every arrow is the brief's own diagram, unmodified, and `STEP_NAMES` holds
it as data so a test can assert the report never has a different shape.
**No step derives anything new.** `discover()`, `derive_intelligence()`,
`VigilanceAttestation.attest()` and `ConversationMemory()` are C19's, C22's
and Layer 1's own entry points, called once each, and a test
(`test_no_derivation_is_reimplemented`) asserts no internal helper of any
of those three components — `discover_application`, `attribute_processes`,
`_gap_for` — is called from this package, which would be the tell that a
piece of logic had been pulled out and pasted rather than reused.

A `BootStep` never says `ok` for a step that did not run: every branch is
either `OK` with a real detail (*"19 applications scanned"*, *"3 of 3
sources wired"*), `UNAVAILABLE` with the caught exception's own message, or
`OUT_OF_SCOPE` for the one step this component cannot perform. This is
`launcher/boot.py`'s own convention (*"a step that could not run reports
`unavailable` with a reason — never `ok`"*), reused rather than
reinvented, and checked by a parametrized test over four independent
failure injections (§5).

---

## 3 · Why Presence runs before Environment Intelligence

The brief's own ordering, followed literally rather than reordered for
convenience — a test (`test_presence_runs_before_environment_intelligence`)
asserts the two steps appear in that order in every boot report.

The design temptation was to seed a vigilance domain from the environment
scan's own success — *"was the machine scan able to run"* — folded into
presence as a fact about presence. **This was rejected.** VEDA 04 §7 makes
per-domain health *"a first-class product concept surfaced in the
founder's own language"* — inbox, calendar, billing, the things a founder
decided matter. The environment scan is infrastructure this boot sequence
depends on, not something a founder asked to be watched. Inventing a
domain to make `Coverage.complete` look better than the truth would have
been C23's own R80 finding, recurring in a different shape.

**So Initialize Presence attests over whatever `DomainRegistry` it is
given — empty, at this milestone, because no connector has registered
anything yet — and reports the honest answer.** `Coverage.complete` is
`False`; the gap names C19's own reason
(*"no domain is being watched, so coverage proves nothing"*); C23's
`presence_feed()` refuses to feed it to the Presence Layer rather than
manufacturing calm from nothing. Four tests in `TestPresenceIsHonest`
exercise this against a real boot rather than a hand-built `Coverage`, and
`test_the_presence_step_still_reports_ok` records the finding precisely:
**attesting honestly over nothing is success**, not failure — the contract
was exercised and answered truthfully, which is what the step promises.

The brief's ordering turns out to be exactly right for this reason:
Presence *can* run before Environment Intelligence, because it genuinely
does not depend on it.

---

## 4 · The Founder UI receives live state immediately — proven, not asserted

`TestLiveStateOnFirstSnapshot` calls `snapshot()` **once**, immediately
after `boot_founder_edition()` returns, with no warm-up call and no second
round trip:

- All four sections (`environment`, `presence`, `conversation`, `sources`)
  are present in that first call.
- `environment.summary`'s three readiness signals
  (`environment_ready`, `ai_available`, `developer_environment_healthy`)
  are always real `Inference` values — each carrying its own `reason` and
  `confidence` — never a placeholder. `observations` itself is left
  conditional, because C22's own `derive_summary` only populates it when
  something evidences it (a running browser, a preferred tool); a second
  test drives a fake machine with a running Chrome to confirm the list
  populates for real when there is something to observe.
- `presence.coverage` travels beside the feed and always carries
  `complete`, so a surface can gate the calm sentence on C19's
  authoritative answer rather than a re-derivation (C23's own remedy for
  R80, exercised here for the first time against a real boot sequence).
- `conversation.entries` is `[]`, not `None` — present-but-empty is the
  *"conversation ready"* signal the brief asks for, distinguished from
  *"conversation not wired"* the same way C23's Absence discipline already
  distinguishes every other section.
- The whole snapshot round-trips through `json.dumps`/`json.loads`
  unchanged, and a text search across the serialized snapshot for five
  synthetic-greeting phrases (*"Good morning"*, *"How can I help"*,
  *"Welcome back"*, …) finds none.
- `CurrentActivity`, `CalmState` and `VigilanceState` are asserted absent
  from this package's own defined names — they are C20's derived types,
  produced from the feed this component hands it, never duplicated here.

---

## 5 · Failure is reported, never hidden — all four inputs, independently

Every one of the four steps that can fail was actually made to fail, not
just reasoned about:

| Step | Forced failure | What the report says |
|---|---|---|
| Initialize Runtime | `FounderRuntime.__init__` raises on its first call | `runtime: unavailable`, boot aborts, `ready: unavailable` |
| Initialize Presence | `VigilanceAttestation.attest()` raises | `presence: unavailable`, **boot continues**, `ready: ok` |
| Initialize Environment Intelligence | a probe whose `which`/`processes` raise | `environment_intelligence: unavailable` with the real exception text, boot continues, `ready: ok` |
| Initialize Conversation | `ConversationMemory.__init__` raises on its first call | `conversation: unavailable`, boot aborts, `ready: unavailable` |
| Connect Founder Runtime | `FounderRuntime.__init__` raises on its second call (the connect call, not the open call) | `connect_founder_runtime: unavailable`, `ready: unavailable`, `app.ready is False` |

Presence and Environment Intelligence are **non-fatal**: a founder who
cannot reach vigilance domains or whose machine scan fails still gets a
working conversation pipeline and a running application, with the gap
named rather than papered over (`test_the_app_still_answers_after_a_
partial_failure`, `test_conversation_still_works_after_a_partial_failure`).
Runtime and Conversation failures are **fatal**, because nothing downstream
can be trusted without them — `_abort()` still returns a working
`FounderEditionApp` holding an unwired `FounderRuntime()` (C23's own
supported empty state) rather than raising, so a founder sees *why*
instead of a crash.

**Injecting these failures required a real design decision, recorded so it
is not mistaken for hand-waving.** A bare function cannot stand in for
`FounderRuntime` or `ConversationMemory` in these tests:
`FounderEditionApp.__init__` runs `isinstance(value, FounderRuntime)`
against the same patched name, and a function is not a type. `_raise_once()`
constructs a **subclass** of the real class whose `__init__` raises on
exactly the Nth call and behaves normally otherwise — keeping every
`isinstance` check in `boot.py` and `wiring.py` true while injecting one
failure at one call site, which is closer to what an intermittent failure
actually looks like than replacing the whole class.

---

## 6 · Frozen boundary, and the one stated exception

The brief's frozen list is `foundation/`, `kernel/`, `ledger/`,
`coordinator/`, `runtime_bridge/`. C24's guard is narrower than "no
`foundation` import at all" for one reason, argued rather than assumed:

**`foundation.clock` is not an authority surface.** It is `Clock`,
`SystemClock` and `ManualClock` — a time source with three methods and no
`Warrant`, `Receipt`, `AttemptToken` or ledger record anywhere in it. C19's
own `VigilanceAttestation` already depends on it — the Roadmap states
plainly that vigilance's *"Depends on. C1 Clock alone"* — and C24 calls
`VigilanceAttestation.attest()` directly, per the brief's instruction to
*"wire them together using existing contracts."* There is no way to call
that contract without a `Clock` instance, and the only place one is
defined is `foundation.clock`.

So `TestNoFrozenAuthorityIsReached` states the boundary precisely rather
than broadly:

- `test_the_only_foundation_import_is_the_clock` asserts the package's
  entire `foundation` import surface is exactly `{"master_agent.foundation
  .clock"}` — not a subset check, an equality check.
- `test_no_authority_surface_is_imported` separately forbids every
  authority-bearing `foundation` submodule by name —
  `warrant`, `attempt_token`, `attestation`, `receipt`,
  `execution_request`, `execution_context`, `consequence`, `override`,
  `refusal`, `reversibility`, `admission`, `principal` — plus `kernel`,
  `ledger`, `coordinator`, `api`, `runtime_bridge` in full.

`git diff --stat kalpavriksha-s1-c18.0` against all five frozen packages,
and `git status --porcelain` against the same five, are both empty — byte-
identical to the tag, clean in the working tree.

---

## 7 · Nothing executes, nothing calls AI, nothing is duplicated

Same discipline as C23, over this package specifically, and re-proven by
breach injection rather than assumed to still hold:

| Guarantee | How it is enforced |
|---|---|
| No execution subsystem reachable | `executor`, `plugins`, `providers`, `broker`, `ai_infrastructure`, `orchestrator`, `runtime.*` (the Engine), `mission_control`, `planner`, `brain`, `permissions`, `launcher` — none importable, checked by prefix |
| Cannot reach the machine except through the Desktop Executive's own scanner | `subprocess`, `shutil`, `socket`, `http`, `urllib`, `requests`, `httpx`, `threading`, `multiprocessing`, `sqlite3`, `winreg`, `ctypes`, and bare `os` — none imported; `desktop.inventory` and `desktop.probe` **are**, and `desktop.catalog` is not (no second catalog) |
| No presence, vigilance or environment type redeclared | `PresenceFeed`, `FounderOperation`, `ResultKind`, `Source` (C23); `Coverage`, `Domain`, `DomainStatus`, `Gap`, `GapKind` (C19); `EnvironmentSummary`, `CapabilityGraph`, `UserProfile`, `PreferenceModel`, `Inference`, `Evidence` (C22) — none declared here |
| `authorize` / `execute` / `CalmState` / `VigilanceState` unreachable | named in prose, absent from every import and every defined identifier — the same AST-over-source-text discipline C23 established |

**The guards were proven able to fail**, the same way C23's were and for
the reason C21's audit (R74) makes mandatory: a throwaway module
containing `import subprocess`, `from master_agent.kernel import Kernel`,
`from master_agent.foundation.attestation import Attestation`,
`datetime.now()` and `class CalmState` was added to the package and the
suite re-run:

```
FAILED TestTheGuardsThemselves::test_forbidden_words_appear_in_prose_but_not_as_identifiers
FAILED TestNoFrozenAuthorityIsReached::test_no_authority_surface_is_imported
FAILED TestNoFrozenAuthorityIsReached::test_the_only_foundation_import_is_the_clock
FAILED TestNothingExecutesOrCallsAI::test_no_module_that_could_reach_the_machine_is_imported
4 failed, 10 passed, 47 deselected
```

The file was deleted and the suite returned to 61 passing.

---

## 8 · The conversation pipeline, end to end

The brief's exact request — *"prove the conversation pipeline works
end-to-end"* — without executing a tool, calling AI, or inventing a
response.

`FounderEditionApp.send(text)` does exactly one thing: records `text` as a
`user` turn on the same `ConversationMemory` instance the connected
`FounderRuntime` already holds, and returns that runtime's own
`conversation()` projection immediately afterward. It performs no
derivation `ConversationMemory.record()` and `conversation_projection()`
(C23) did not already perform — it is composition, one call each, in that
order.

Tested directly:

- Sent text appears, verbatim, in the *runtime's own* projection —
  not a copy this module kept, the actual value `FounderRuntime.handle()`
  would return over the wire.
- Ten sequential messages produce exactly ten entries, in order, and
  **never an eleventh** — `test_no_reply_is_ever_synthesized` asserts one
  `send()` call yields exactly one entry, and every entry's `role` is
  checked to never be `assistant` (C23's own unreachable role, exercised
  here through the boot-assembled path rather than the unit-constructed
  one C23's own suite already covered).
- `send()` still works after Environment Intelligence or Presence has
  failed — the conversation pipeline does not depend on either.
- `send()` refuses a non-string, the same defensiveness `FounderRuntime`
  and every C22/C19 constructor already apply at their own boundaries.

---

## 9 · Determinism

`test_two_boots_over_the_same_fake_machine_agree` constructs two
independent `FounderEditionApp`s from two separately-constructed fake
probes and two separately-constructed `ManualClock(T0)`s, and asserts
their snapshots are equal — not merely similar.

This required one real fix, recorded because it is the kind of thing that
would otherwise surface as a flaky test months later: `discover()` takes
its own `clock` parameter as a **zero-argument callable**, not the
`foundation.clock.Clock` protocol `VigilanceAttestation` takes. `boot.py`
resolves one `Clock` (the injected one, or `SystemClock()`) and passes
`resolved_clock.now` — the bound method — into `discover()`, so the same
moment stamps both the vigilance attestation and the machine inventory's
`captured_at`. Without this, `captured_at` read the real wall clock on
every boot regardless of the injected `Clock`, and two "identical" test
boots produced different environment sections by construction.

---

## 10 · Test evidence

```
python -m pytest tests/test_founder_edition_boot.py -q
  61 passed in 0.39s

python -m pytest tests/test_founder_edition_boot.py --cov=master_agent.founder_edition
  __init__.py    3 stmts   0 miss  100%
  boot.py      118 stmts   0 miss  100%
  TOTAL        121 stmts   0 miss  100%

python -m ruff check src/master_agent/founder_edition/ tests/test_founder_edition_boot.py
  All checks passed!
```

**Full suite: 5454 passed, 49 failed, 1 skipped (176s)** — up from C23's
5393 passed with the same 49 failures, confirming all 61 new tests landed
clean and nothing existing regressed.

**All 49 failures are the same ones named in `Engineering/HEALTH_C23.md`
§11** — `FounderConsole.__init__()` rejecting a `memory` keyword argument,
and `launcher/boot.py:693` reading ambient `datetime.now()` — sitting in
the uncommitted MB032–039 working-tree changes, unrelated to and
unmodified by this component. Not re-verified by moving files this time
since C23 already established the isolation method and nothing in this
component touches `launcher/`, `missions/` or `memory/` beyond importing
`ConversationMemory`, which is used read/record-only and unmodified.

---

## 11 · What this does not do, stated so it is not assumed

1. **No transport is started.** `boot_founder_edition()` returns a
   `FounderEditionApp` in-process. There is no HTTP server, no IPC
   channel, no socket. Wiring this to a real Founder Surface process is a
   transport decision C23's own §14 already deferred, and C24 does not
   resolve it either.
2. **No TypeScript was written or modified.** Render Founder Surface is
   reported `out_of_scope`, not implemented in a stub. C20 and C21 remain
   HyperAgent's artefacts, untouched.
3. **No vigilance domain is registered.** §3. This is not a gap to close
   in this brief — a founder connecting a real domain (inbox, calendar) is
   future work, and doing it here would be adding intelligence this brief
   forbids.
4. **The dashboard is untouched.** `dashboard/` shows only the pre-existing
   MB032–039 edits; nothing in this component imports it.
5. **`FounderEditionApp.send()` is the only write path**, and it performs
   exactly one operation: recording a `user` turn. There is no `retry`,
   no `cancel`, no `approve` — those travel the Runtime Bridge (C18) via a
   door C23 already established this surface cannot reach
   (`AUTHORITY_UNREACHABLE`), and C24 does not add a second one.

---

## 12 · Open question carried forward from C23, still open

**R80's gate** (`Engineering/HEALTH_C23.md` §5) is unchanged by this
component: whether the calm sentence should be gated on
`presence.coverage.complete` in the surface, or whether C20 should be
changed to treat an unfed layer as incomplete. C24 exercised the honest
path against a real boot (§3) and confirms the remedy holds under it, but
does not resolve the underlying question — that decision is still the
founder's, per C23 §14.

---

*End of report. Working-directory evidence only. No commits, no tags, no
Rule 001 milestone declared.*
