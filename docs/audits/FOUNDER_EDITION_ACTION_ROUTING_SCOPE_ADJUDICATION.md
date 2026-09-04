# Founder Edition Action Routing — Scope Adjudication

Status: read-only evidence gathering. No source modified, deleted, reverted,
or committed. No Mission Brief created. No feature formalized, expanded, or
fixed. Performed per explicit instruction — this document exists only to
give the Founder/CTO the evidence needed to decide; it makes no decision.

---

## 1. Exact capability investigated

The uncommitted code in `src/master_agent/founder_edition/desktop_shell.py`:

- `_try_action(text, runtime)` — prefix-matches founder text
  (`if t.startswith("open ") or t.startswith("launch ")`), resolves it
  against `master_agent.desktop.catalog.resolve()`, and calls
  `runtime._desktop.executor.execute(spec.key)` directly, with fallbacks to
  `os.startfile()` for URLs/files/raw targets.
- `_handle_local_query(text, runtime)` — answers environment/desktop
  queries locally (installed apps, running processes, AI tool inventory,
  Desktop directory listing via `os.listdir`).
- Mode switching (`LOCAL` / `AI_MODE` / `BOTH`) stored on
  `self._mode`, changing how `send_message()` routes unresolved intents.

Both functions are called from `DesktopShellApi.send_message()` — the one
bridge method the Founder Edition UI actually invokes for every founder
utterance — ahead of the committed `CommunicationEngine.handle()` call.

## 2. All authorizing/restricting documents found

Searched: every `docs/MISSION_BRIEF_*.md`, all ADRs (`docs/adr/0001`–`0023`),
`docs/architecture/KALPAVRIKSHA_VISION_V2.md`,
`docs/architecture/FOUNDER_CONSTITUTION_FREEZE.md`, `ROADMAP.md`, every
`Engineering/AUDIT_*.md` and `Engineering/HEALTH_*.md` for C24–C34, and the
committed source of `founder_edition/boot.py` and
`tests/test_founder_edition_boot.py`.

**No Mission Brief, ADR, roadmap item, or founder-approved scope statement
names `_try_action`, `_handle_local_query`, desktop action routing from
Founder Edition, or LOCAL/AI/BOTH execution modes.** `grep` for these terms
and their synonyms across `docs/`, `knowledge/`, and `Engineering/` returns
no hits outside this session's own audit documents.

Three documents speak directly to the underlying question (may Founder
Edition's conversational surface execute desktop actions) — all three
restrict it:

### a) `founder_edition/boot.py` (committed, unchanged, `51cdf44`)

> *"C28, handed the executor and observer built above rather than
> constructing its own. **Wired and idle: nothing in C1–C29 turns founder
> speech into a DesktopTask, so no door here hands it one.**"*

Directly on point: the desktop layer is wired into `FounderRuntime` but the
project's own accepted state, as of the last commit, is that no mechanism
exists to turn founder speech into desktop execution.

### b) `Engineering/AUDIT_C31_CONVERSATION_ENGINE.md`

> *"C31 correctly implements the Founder Conversation Engine as a pure
> answer layer... **The engine answers only — it never plans, executes,
> launches, mutates Runtime, or reaches desktop/perception/execution
> layers.**"*

And its verification table:

| Prohibited Action | Verified Absent |
|---|---|
| Launches software | ✅ — no `LaunchApplicationAction`, `SystemProbe.start()` |
| Calls Desktop Operator | ✅ — no `desktop_operator` import |
| Calls Desktop Executive | ✅ — no `desktop.execution` import |

And explicitly: *"This is the correct architecture for C31 (answer layer),
but the **Desktop Operator (C30+) must handle proactive behavior**."* — i.e.
if founder-speech-triggered desktop action is ever built, the project's own
audit trail says it belongs in the Desktop Operator, not in the
conversational/bridge surface `send_message()` sits on.

This audit governs the `conversation_engine/` package specifically, not
`founder_edition/` — but it establishes the project's own consistently
applied design rule (answer layers do not execute), the same rule
`desktop_shell.py`'s committed `send_message()` already followed until this
uncommitted addition.

### c) `tests/test_founder_edition_boot.py::TestNothingExecutesOrCallsAI` (committed, unchanged, `51cdf44` — confirmed via `git diff --stat`, zero output)

This is not an audit opinion — it is a committed, ship-verified,
mechanically-enforced test suite. Run against the current working tree
(read-only — no source touched to produce this):

```
tests/test_founder_edition_boot.py::TestNothingExecutesOrCallsAI::test_no_module_that_could_reach_the_machine_is_imported FAILED
tests/test_founder_edition_boot.py::TestNothingExecutesOrCallsAI::test_this_package_imports_no_os_module_directly FAILED
tests/test_founder_edition_boot.py::TestNothingExecutesOrCallsAI::test_only_the_desktops_own_scanner_touches_the_machine FAILED

AssertionError: assert 'subprocess' not in {...}
AssertionError: assert 'os' not in {...}
AssertionError: assert 'master_agent.desktop.catalog' not in {...}
```

The test file itself is untouched (`git status --short` on it: empty). It
was passing against the committed baseline and is failing **only** because
of the uncommitted `_try_action()`/`_handle_local_query()` additions:
`import os`, `import subprocess`, and
`from master_agent.desktop.catalog import resolve` are exactly what these
three tests were written to forbid. The third test's own docstring states
the rule directly: *"No second inventory, no second catalog — the same
guarantee C22's own suite already proves for `environment_intelligence`."*
`desktop_shell.py` now imports a second catalog resolution path
(`desktop.catalog.resolve`) parallel to the one `DesktopExecutiveV2`
already owns.

## 3. Does the uncommitted implementation match any approved scope?

No. There is no approved scope for it to match — searched exhaustively, none
found — and where the committed architecture speaks to the underlying
question at all, it speaks against this shape of implementation
specifically: conversational/answer surfaces do not execute, and the
package guard tests that enforce that for `founder_edition` are currently
red because of this code.

## 4. Final classification

**B — EXPLICITLY NOT AUTHORIZED / PROHIBITED**

Not merely silence (which would be C). Three independent, committed,
project-governing sources restrict this specific pattern:
1. `boot.py`'s own docstring records the deliberate absence of any
   speech-to-DesktopTask door.
2. `AUDIT_C31_CONVERSATION_ENGINE.md` states the project's own rule that
   answer layers must never reach desktop/execution layers, and names
   Desktop Operator (not the conversational bridge) as the correct future
   home for proactive desktop behavior.
3. `tests/test_founder_edition_boot.py::TestNothingExecutesOrCallsAI` — a
   committed, unmodified, mechanically-enforced test suite — is currently
   **failing**, specifically and only, because of this code.

## 5. Recommended next governance action

This is not a recommendation to build, fix, or formalize anything — it is
the decision surface for the Founder/CTO:

- **Option 1 — Revert.** Remove `_try_action()`/`_handle_local_query()`/mode
  switching from the working tree, restoring the committed, test-passing,
  audit-compliant `send_message()`. Zero governance cost; three currently-red
  tests return to green immediately.
- **Option 2 — Formalize.** If founder-speech-triggered desktop action is
  wanted on this surface, it requires a new Mission Brief and, per
  `AUDIT_C31_CONVERSATION_ENGINE.md`'s own finding, should route through the
  Desktop Operator (C30+) as proactive behavior rather than synchronously
  inside `send_message()` — and the `TestNothingExecutesOrCallsAI` guard
  would need an explicit, ratified amendment (the same process
  `FOUNDER_CONSTITUTION_FREEZE.md` §4a documents for Amendment 1/2), not a
  silent weakening.
- Either way, the decision is the Founder's/CTO's — not Claude's, per this
  mission's own instruction.

STOP.
