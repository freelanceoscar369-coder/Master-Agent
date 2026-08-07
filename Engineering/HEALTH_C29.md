# Health Report — Sprint 1, Component 29: Founder Identity Layer

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-07
**Status:** Complete. **Not committed, not tagged, no Rule 001.**
**Ground:** C1–C28 · Founder Vision · Founder Conversation · Founder Runtime (C23) · Desktop Executive · Desktop Operator (C28) · Environment Intelligence (C22) · Desktop Perception (C27).
**Out of scope, by the brief's own words:** Sprint 2, Mission OS, Consumer Edition, Kernel redesign. None touched.

---

## 1 · What Somesh is

*"Not an assistant. Not an LLM. Not a chatbot."* `founder_identity/` is five
small modules that hold exactly what the brief lists — a name, a session,
a greeting, a continuation, and a context — and reach exactly one door:
`FounderRuntime` (C23).

```
   Founder: "Good morning Somesh"
        │
        ▼
   FounderIdentity  +  FounderContext ──── founder_context() ──── FounderRuntime (C23)
        │                                                              │
        ▼                                                              ▼
   greet()                                              environment() / conversation() / presence()
        │
        ▼
   "Good morning. I'm awake. Everything is ready."
```

| File | Role | Statements |
|---|---|---|
| `identity.py` | `FounderIdentity` — the fixed, frozen shape of who Somesh is | 34 |
| `session.py` | `FounderSession` — a lens on the session's own `ConversationMemory`, never a second history | 23 |
| `context.py` | `FounderContext` / `founder_context()` — three readiness facts read from `FounderRuntime`, and nothing re-derived | 20 |
| `greeting.py` | `greet()` / `is_greeting()` — the composed reply, checked against forbidden AI wording | 37 |
| `continuity.py` | `is_continuation_request()` / `continuity_reply()` — "Continue" means continue | 12 |

**133 statements. 98% coverage (3 uncovered defensive branches — see §6). Ruff clean.**

---

## 2 · Somesh Responsibilities, exactly the brief's own list

| Somesh owns | Where |
|---|---|
| Founder personality | `FounderIdentity` |
| Conversation continuity | `continuity.py` |
| Greeting | `greeting.py` |
| Acknowledgement | `continuity_reply()` |
| Memory recall | `FounderSession.last_founder_utterance()` — read, never duplicated |
| Environment awareness | `FounderContext.environment_ready` |
| Execution acknowledgement | Out of scope for this layer — Somesh reports readiness, never an execution outcome; there is no field here for one |

## 3 · Somesh NEVER — checked structurally, not promised

| Never | Enforced by |
|---|---|
| Plans a mission | No `planner`, `mission_manager`, `mission_control`, `missions` import anywhere in the package |
| Executes on the desktop | No `desktop` or `desktop_operator` import; `TestBoundaries::test_no_forbidden_module_is_imported_anywhere_in_the_package` |
| Routes to a model | No `broker`, `plugins`, `providers` import; `greet()` and `continuity_reply()` are pure functions of their arguments — no network call is reachable from either |
| Decides strategy | No `orchestrator`, `brain`, `coordinator` import |
| Calls the Kernel | No `kernel`, `runtime_bridge`, `ledger` import; the only `master_agent.*` roots this package may import are `founder_identity` itself, `founder_runtime`, and `memory` — `TestBoundaries::test_the_only_master_agent_door_is_founder_runtime_or_memory` checks the closed set by AST across every file |
| Calls Desktop Executive directly | Same guard — `desktop.*` is in the forbidden root list, and `FounderContext` reads only `FounderRuntime`'s own three methods (`environment()`, `conversation()`, `presence()`), never `environment_intelligence` or `desktop` themselves |
| Mutates the Runtime | `FounderContext` and `founder_context()` call no method on `FounderRuntime` beyond the three read-only projections already named; nothing in the package holds a `FounderRuntime` reference longer than one function call |

The guard was proven able to fail the same way C28's own audit proved its
import guards able to fail: a throwaway `import master_agent.desktop` line
added to `context.py` was confirmed to trip
`test_no_forbidden_module_is_imported_anywhere_in_the_package`, then
removed.

---

## 4 · No AI wording — checked, not just avoided

`greeting.FORBIDDEN_PHRASES` names the brief's own forbidden sentences —
*"As an AI," "I cannot," "language model"* — and `greet()` lower-cases and
scans its own composed sentence against that list before returning it,
raising `ForbiddenWording` rather than emitting the phrase. §1 of C29's
test file, `test_forbidden_wording_is_raised_if_a_template_ever_leaks_one`,
monkeypatches the readiness clause to inject a forbidden phrase and
confirms the check actually fires — the same "prove the guard can fail"
discipline C28's audit used for its own import guards, applied here to a
wording guard instead of an import guard.

## 5 · Conversation continuity — "Continue" means continue

`is_continuation_request()` recognises the brief's own example
(`"Continue"`) plus its ordinary synonyms (`"keep going"`, `"carry on"`,
`"resume"`). `continuity_reply()` reads exactly one fact from
`FounderSession` — whether any turn has been recorded — and never echoes,
summarises, or re-explains what came before: `test_reply_carries_no_re_
introduction` records a turn mentioning "Q3" and asserts the word never
appears in the reply.

`FounderSession` itself holds no history of its own — `__slots__ =
("_conversation",)`, checked directly by
`test_holds_no_second_copy_of_history` — because the brief's own
distinction is *"Not memory. Not history. Only active session,"* and a
session that kept a second list of turns would be exactly the duplicate
history the brief rules out.

---

## 6 · What is not exercised

1. **No real `FounderRuntime` wired with all four sources at once was
   exercised against `founder_context()`** — only the empty and
   conversation-only constructions. The three uncovered branches (§0) are
   `greeting.py:50`'s dead `"Good evening"` fallback for an hour outside
   `range(24)` (unreachable from a real `datetime`, kept only because the
   brief's three time bands do not partition the day exhaustively without
   it), `identity.py:70` (the `assistant_name` empty-string branch, which
   `founder_name`'s sibling check already proves the pattern for), and
   `session.py:68` (`FounderSession.as_dict()`, never called by a test —
   present for parity with every other frozen/near-frozen type in this
   layer, unused by anything that currently reads a session).
2. **`FounderEditionApp` (C24) is not wired to construct a
   `FounderIdentity`/`FounderSession` yet.** This component builds the
   layer the brief asks for; connecting `boot_founder_edition()` to
   actually hand a founder's name into it is composition work the brief
   places outside C29's own scope (*"No Sprint 2. No Mission OS."*), and
   is left as the natural next step for whichever component does that
   wiring.
3. **Time-of-day banding is UTC, not founder-local.** `FounderContext.moment`
   is whatever the caller passes; nothing in this package converts it
   through `foundation.clock.Clock.to_founder_local()`, because doing so
   would require importing `foundation`, which is outside the two-root
   allow-list this layer polices. The caller that constructs
   `FounderContext` is responsible for handing it an already-founder-local
   moment.

---

## 7 · Test evidence

```
python -m pytest tests/test_founder_identity.py -q
  44 passed in ~0.2s

python -m pytest tests/test_founder_identity.py --cov=master_agent.founder_identity
  __init__.py       7 stmts   0 miss  100%
  context.py       20 stmts   0 miss  100%
  continuity.py     12 stmts   0 miss  100%
  greeting.py       37 stmts   1 miss   97%
  identity.py       34 stmts   1 miss   97%
  session.py        23 stmts   1 miss   96%
  TOTAL            133 stmts   3 miss   98%

python -m ruff check src/master_agent/founder_identity/ tests/test_founder_identity.py
  All checks passed!
```

---

*End of report. Working-directory evidence only. No commits, no tags, no
Rule 001 milestone declared. Stop. Waiting for Hermes audit.*
