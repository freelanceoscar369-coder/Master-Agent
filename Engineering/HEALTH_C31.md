# Health Report — Sprint 1, Component 31: Founder Conversation Engine

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-07
**Status:** Complete. **Not committed, not tagged, no Rule 001.**
**Ground:** C1–C30. No new Runtime, no new Identity, no desktop execution, no missions, no planning — none built.

---

## 1 · What was built

```
   Founder speech
        │
        ▼
   ConversationEngine.reply(text, moment, desktop)
        │
        ▼
   ResponsePipeline.handle()
        │
        ├─ 1  IntentClassifier.classify()   → Intent            (six shapes + UNKNOWN)
        ├─ 2  ContextAssembler.assemble()   → ConversationContext (FounderRuntime, read-only)
        ├─ 3  ConversationMemory.record("user", text)
        ├─ 4  ResponseComposer.<intent>()   → str | None          (translated, never a leak)
        └─ 5  ConversationMemory.record(SOMESH, reply)  — only if step 4 produced one
        │
        ▼
   ConversationTurn(intent, reply, context)
```

**Five files, exactly the brief's own list**, plus `__init__.py`:

| File | Role | Statements |
|---|---|---|
| `intent.py` | `Intent`, `IntentClassifier` — six recognised shapes, closed vocabulary | 35 |
| `context.py` | `DesktopStatus`, `ConversationContext`, `ContextAssembler` | 41 |
| `composer.py` | `ResponseComposer`, `ExposedInternals` — one sentence per intent, checked | 47 |
| `pipeline.py` | `ResponsePipeline`, `ConversationTurn`, `SOMESH` — the four-step orchestration | 57 |
| `engine.py` | `ConversationEngine` — the one public door | 13 |

**200 statements. 100% coverage. Ruff clean. 104 tests (minimum was 80).**

---

## 2 · The brief's own dialogue, run end to end

```
Founder: Good morning Somesh
Somesh : Good morning. I'm awake. Everything is ready.

Founder: What are you doing?
Somesh : I'm monitoring everything. Nothing currently needs your attention.
         (or, honestly, when nothing is registered yet:
          "I'm here and ready. Nothing is being watched yet, so nothing
          can need your attention.")

Founder: How's the system?
Somesh : Everything on the desktop is working normally. The environment
         looks healthy. I'm here and fully connected. Nothing is waiting
         on your approval.

Founder: Continue
Somesh : Continuing.

Founder: Build a trading bot
Somesh : I don't build things myself — that needs to go through
         planning, not through me.
```

Every one of these was produced by `ConversationEngine.reply()` against a
real `FounderRuntime`/`FounderIdentity`/`FounderSession` — not
hand-written for this report — and is asserted verbatim by
`tests/test_conversation_engine.py::TestConversationEngine`.

---

## 3 · Only answers — checked structurally, not promised

| Forbidden (brief's own words) | Enforced by |
|---|---|
| Execute desktop actions | No `desktop.execution`/`desktop_operator` import anywhere in the package |
| Launch applications | Same guard — no process-capable module reachable |
| Create missions | No `mission_manager`/`mission_control`/`missions` import |
| Plan work | No `planner`/`brain`/`orchestrator` import |
| Mutate Founder Runtime | Only `environment()`, `conversation()`, `presence()` are called on `FounderRuntime` — `handle()`, C23's one door with a mutable shape, is never called; `TestBoundaries::test_runtime_handle_is_never_called_here` checks this by AST, narrowed so `ResponsePipeline`'s own same-named method does not trip it |

The only `master_agent.*` roots this package may import are itself,
`founder_identity`, `founder_runtime`, and `memory` —
`TestBoundaries::test_the_only_master_agent_door_is_founder_identity_
runtime_or_memory` checks the closed set across every file. **`desktop.*`
and `founder_edition` are both in the forbidden root list** — the second
one deliberately, to keep this package from depending on the composition
root that will eventually depend on it (see `context.py`'s own docstring
§2).

**The guard was proven able to fail.** A throwaway file importing
`master_agent.desktop.inventory.discover` and `master_agent.planner.planner`
was added to the package, confirmed to trip the boundary check, then
removed — `TestBoundaries::test_the_guards_can_actually_fail` does this
inline, on every run, rather than as a one-off manual step.

---

## 4 · Never says, never exposes — both checked at runtime, not just avoided

`composer._checked()` lower-cases every composed sentence and scans it
against two closed lists before returning it:

- `founder_identity.greeting.FORBIDDEN_PHRASES` — *"as an AI," "language
  model," "I cannot"* — C29's own list, reused rather than duplicated.
- `conversation_engine.composer.FORBIDDEN_INTERNAL_TERMS` — `runtime`,
  `kernel`, `operator`, `mission id`, and every component class name this
  package or its neighbours define (`DesktopExecutiveV2`,
  `DesktopOperator`, `DesktopObserver`, `DesktopExecutor`,
  `FounderRuntime`), plus `coordinator`, `orchestrator`, `bridge`.

Either list matching raises rather than returning the leaked string —
`ExposedInternals` for architecture, `ForbiddenWording` (C29's own, raised
from inside `greet()`) for AI wording. `TestExposedInternalsIsStructural
::test_a_leaking_translation_is_caught_not_merely_avoided` monkeypatches
one composer method to leak the word *"Runtime"* and confirms the whole
`status()` call raises — proving the check fires, not merely that current
wording happens to avoid it.

---

## 5 · One stated conflict in the brief, and how it was resolved

The brief's worked status dialogue reads four lines that are themselves
component names:

```
Desktop Executive healthy.
Environment Intelligence healthy.
Founder Runtime healthy.
No warrants pending.
```

— while the same brief's Speaking Rules say, two sections earlier,
*"Never expose Runtime … Component names,"* and give the opposite-
direction worked example: `DesktopExecutiveV2 healthy` → *"Everything on
the desktop is working normally."*

**The structural rule was followed.** `ResponseComposer.status()` states
the same four facts without a single forbidden name:

```
Everything on the desktop is working normally.
The environment looks healthy.
I'm here and fully connected.
Nothing is waiting on your approval.
```

Argued in full in `composer.py`'s own module docstring, at the point a
reader would ask the question — the same discipline C30 already used for
its own two brief reconciliations (dashboard identity, boot ordering)
rather than resolving a conflict silently.

---

## 6 · Never invents

Every composer method reads one or more fields of `ConversationContext`
and states them; none composes a number, a name, or a recommendation the
context did not already carry.

- **`activity()`** distinguishes *"nothing is registered"* from
  *"registered and complete"* from *"registered with N gaps"* — three
  honest states, never collapsed into one. The first branch exists
  specifically so *"I'm monitoring everything"* is never said over a
  `Coverage` with nothing watched, which would repeat C23's own R80
  finding (*"Nothing needs you," said over nothing at all*) one layer up.
  `TestResponseComposerActivity::test_unregistered_presence_never_
  claims_full_monitoring` asserts the literal phrase never appears in
  that branch.
- **`priority()`** names the first *real* domain from `Coverage.gaps`
  (already C19's own order, never re-sorted) or says honestly that
  nothing is tracked — it never fabricates a priority when none exists.
- **`build_request()`** is content-blind by design:
  `test_is_identical_regardless_of_what_was_asked_for` asserts the same
  sentence for *"Build a trading bot"* as for any other request, because
  nothing about *what* to build is ever known to this engine and
  inventing an opinion about it would be exactly the invention the brief
  forbids.

---

## 7 · `assistant` stays unreachable a third layer out

C23's conversation projection maps every speaker that is not `"user"` to
`"system"`; C29 records Somesh's own turns under a speaker that is
neither `"user"` nor `"assistant"`. C31 does the same at its own layer —
`pipeline.SOMESH = "somesh"`, recorded directly through
`ConversationMemory.record()` (not through `FounderSession.record()`,
which C29 fixes to `"user"` by design). Three independent modules, three
independent tests
(`test_conversation.py`/`test_founder_identity.py`/
`test_conversation_engine.py`), the same guarantee held at every layer it
passes through: `TestResponsePipeline::test_somesh_speaker_projects_to_
system_never_assistant` asserts the rendered role set after a real
pipeline turn is exactly `{"user", "system"}`.

---

## 8 · Not wired into `founder_edition` yet

`ConversationEngine` is complete and independently testable but **is not
constructed by `boot_founder_edition()`.** This brief is scoped to the
package itself (*"Create `conversation_engine/`"*); wiring it into C30's
boot sequence — deciding where in `STEP_NAMES` it belongs, and how a
`DesktopLayer.readiness()` reading becomes the `DesktopStatus` this
package expects — is composition work for whichever future step extends
`founder_edition/boot.py`, the same way C29's `FounderIdentity` sat
unwired until C30 connected it. `founder_edition`'s own `say()` (C30)
therefore still answers only greetings and continuations; `How's the
system?` and the rest of C31's vocabulary are reachable only through
`ConversationEngine` directly today.

---

## 9 · Known limitations

1. **Six intents, not open conversation.** *"Turn Somesh from a greeting
   system into a real conversational entity"* is met for the six shapes
   the brief itself names and worked examples for; free-form founder
   speech outside those six still returns no reply
   (`Intent.UNKNOWN`), the same honest silence C29's greeting/continuity
   pair already chose over inventing a response.
2. **`priority()` reasons only from `Coverage.gaps`.** No backlog, task
   list, or mission queue is reachable from this package (by design —
   see §3), so *"what should I work on"* can only ever point at a
   vigilance gap or say nothing is tracked. A founder with real pending
   work tracked elsewhere (Mission Control, the dashboard's own approval
   queue) will not hear about it from this engine.
3. **`DesktopStatus` is a value the caller must translate.** This package
   never reads `DesktopLayer` itself (§3/§8), so whichever component
   eventually wires `ConversationEngine` into `founder_edition` is
   responsible for turning a `DesktopLayer.readiness()` reading into one
   `DesktopStatus(ready, detail)` before each call — an honest coupling
   point rather than a hidden one.
4. **No test exercises this engine against a live desktop.** Every test
   here is deterministic and fixture-backed; the earlier live smoke run
   used a real `FounderRuntime` against this machine (§2) but not a real
   `DesktopStatus` reading, since the desktop layer is not wired in.

---

## 10 · Test evidence

```
python -m pytest tests/test_conversation_engine.py -q
  104 passed

python -m pytest tests/test_conversation_engine.py --cov=master_agent.conversation_engine
  __init__.py     7 stmts   0 miss  100%
  composer.py    47 stmts   0 miss  100%
  context.py     41 stmts   0 miss  100%
  engine.py      13 stmts   0 miss  100%
  intent.py      35 stmts   0 miss  100%
  pipeline.py    57 stmts   0 miss  100%
  TOTAL         200 stmts   0 miss  100%

python -m ruff check src/master_agent/conversation_engine/ tests/test_conversation_engine.py
  All checks passed!

python -m pytest tests/test_conversation_engine.py tests/test_founder_identity.py \
                tests/test_founder_runtime.py tests/test_founder_edition_boot.py \
                tests/test_founder_edition_assembly.py -q
  359 passed
```

**Frozen packages and prior deliverables:**

```
git status --porcelain -- foundation kernel ledger coordinator runtime_bridge api
→ (empty)

git status --porcelain -- founder_runtime founder_identity founder_edition desktop
→ (only the untracked directories themselves; no tracked file modified)
```

Every source package C31 touched is `conversation_engine/`, new and
untracked.

---

*End of report. Working-directory evidence only. No commits, no tags, no
Rule 001 milestone declared. Stop. Waiting for Hermes audit.*
