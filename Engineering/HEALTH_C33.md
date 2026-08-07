# Health Report — Sprint 1, Component 33: Kalpavriksha Founder Edition Integration (Desktop Alpha)

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-07
**Status:** Complete, with two stated observations (§2, §5). **Not committed, not tagged, no Rule 001.**
**Ground:** C1–C32. **Zero new components built** — see §1 for exactly what changed and why each change is composition, not architecture.

---

## 0 · What this report is answering first

C33's own final constraint is explicit: *"If you encounter something that
seems to require redesign: Stop. Record it as an observation. Propose the
smallest integration fix. Do not introduce new architecture."* Two things
were found missing during this mission, and both are recorded before
anything else in this report, because they shape every decision below:

1. **No UI surface in this repository has a conversation area, a voice
   button, or a text box wired to Founder Runtime.** (§2)
2. **`CommunicationEngine` has no way to recover its own mode after a
   switch to an unregistered channel.** (§5)

Neither was fixed by building new architecture. Both were handled by the
smallest fix available at the integration layer, and both are argued in
full below.

---

## 1 · What actually changed, and why none of it is a new component

| File | What changed | Why it is composition, not a new layer |
|---|---|---|
| `founder_edition/boot.py` | Two new boot steps (`conversation_engine`, `communication`); three new `FounderEditionApp` properties (`conversation`, `conversation_engine`, `communication`); two new `boot_founder_edition()` parameters (`voice_output`, `text_output`) | Wires C31's `ConversationEngine` and C32's `CommunicationEngine` — both already built, neither redefined. `HEALTH_C30.md` §8 and `HEALTH_C31.md` §8 both named this exact next step in advance: *"wiring it into C30's boot sequence... is composition work for whichever future step extends `founder_edition/boot.py`"* |
| `founder_edition/console.py` (new file) | `ConsoleTextInput`/`ConsoleTextOutput` (concrete `TextInput`/`TextOutput`), `format_boot_report`/`format_dashboard` (string formatting of dicts C23/C24/C30 already produce), `process_line`/`run_repl`/`main` (a REPL loop) | The **one** concrete implementation C32 deliberately left unbuilt (*"Provide abstract interfaces only... No implementation"*) — the same relationship `desktop.probe.RealSystemProbe` already has to `desktop.probe.SystemProbe`. No new abstraction is declared; every type this file defines *implements* an existing C32 interface or *formats* an existing dict |
| `app.py` (new file, repo root) | Six lines: import `console.main`, call it | The brief's own literal instruction (*"python app.py... should produce a working Founder Edition"*). `TestAppPy::test_app_py_is_a_thin_shim` asserts by AST that this file defines no function and no class |

**No new package was created.** `founder_edition/console.py` is a new
*file* inside an *existing* package, the same relationship `launcher/
console.py` already has to `launcher/` for the older Mission Control
track. No new `Intent`, no new `ResponseComposer`, no new `FounderIdentity`,
no new `DesktopOperator` — `TestNoDuplicatedLogic` and
`TestConsoleBoundaries` check this by AST directly against the brief's
own forbidden list.

---

## 2 · Observation 1 — no wired UI surface exists, anywhere, for this conversation

Three UI surfaces were investigated before writing any code, per the
brief's own instruction to reuse *"kalpavriksha-desktop-v0.1, Founder
Surface, Founder Dashboard, HTML prototypes, Design Archive."*

| Surface | Location | Finding |
|---|---|---|
| `kalpavriksha-desktop` (`kd`, React/Vite) | `VEDRA_PROJECT/02_Desktop/kd` | A **judgment/approval console** for an entirely different, unrelated "Kernel" (C15.0-era: missions, standing rules, ledger receipts). Every one of its ~40 HTTP methods (`httpKernel.ts`) literally `return Promise.resolve(notImplemented(...))`, marked *"UNVERIFIED — these paths are proposals, not observed API."* No component anywhere in it — `FounderConsole.tsx`, `Dashboard.tsx`, or any other — has a conversation area, a voice button, or a text box. It cannot be "connected" to Somesh; it was never built to talk to Somesh, or to anything this repository's Python side exposes. |
| HTML prototypes (`UX_01_First_Screen_v2.html`, `UX_03_Founder_Dashboard.html`, …) | `VEDRA_PROJECT/01_Assets/UI-UX/` | Static design mockups — markup and CSS, no live data binding of any kind. *"Embed the Founder Dashboard. Live. Not static HTML"* is the brief's own instruction to **not** use these as the live surface. |
| Design Archive | `VEDRA_PROJECT/01_Assets/Archive_Zips/KALPAVRIKSHA_DESIGN_ARCHIVE_v1.zip` | Reference imagery/specs, not a runnable artifact. |
| `master_agent.dashboard/` (ANSI terminal renderer, MB026/029) | `src/master_agent/dashboard/` | A live, working terminal dashboard — but it renders `dashboard.readmodel.DashboardSnapshot`, fed from Mission Control/the Runtime Engine (a *different* track than C22–C32's Founder Runtime), and has no method that accepts C30's `founder_dashboard()` dict shape. Reusing its renderer for C33's data would mean writing an adapter between two incompatible read models — itself a form of new plumbing, not reuse. |
| `pyproject.toml`'s `ui = ["pywebview>=5.1"]` | root | Declared as an optional dependency, never imported anywhere in `src/`. Reserved, evidently, for exactly this kind of desktop shell — but never wired. |

**Stopped, per the brief's own instruction, rather than building a fifth
UI surface.** Building a live bridge to the `kd` React app would mean
standing up a new HTTP server implementing an entirely different, frozen
Kernel API — *"new architectural layer,"* forbidden outright. Building a
`pywebview` shell around the HTML prototypes would mean inventing a
JS-Python bridge with its own message protocol — also new architecture,
and the brief says *"Do NOT redesign UI."* Adapting the ANSI dashboard
renderer to a second read model is the least-bad of the three, and it is
still non-trivial new glue rather than reuse.

### The smallest integration fix actually taken

**The terminal is the desktop window for this alpha.** It is the one UI
surface in this entire repository that is (a) already live, (b) already
wired to real backend state through a launcher pattern this same codebase
already established (`launcher/main.py`'s own `FounderConsole` terminal
loop, for the Mission Control track), and (c) reachable with **zero** new
architecture — `console.py` implements exactly the two interfaces C32
already declared and left unbuilt. `python app.py` opens a window (the
terminal session), the Founder Surface's *data* loads (`app.dashboard()`,
C30's own live projection), the dashboard is visible and live, a text box
is the prompt, and Somesh answers through C31/C32 exactly as specified.
**Voice as a UI affordance does not exist** — see the next paragraph for
why, which is the same root cause.

### Proposed follow-up, not built here

The smallest fix that would connect a graphical surface without new
architecture is a **read-only JSON adapter**: a thin function (not a
server — `fastapi`/`uvicorn` are already project dependencies, but adding
an HTTP server to `founder_edition/` would itself be new architecture)
that a `pywebview` window could call *in-process* — `pywebview` exposes
Python objects to JS directly without a network hop. This was not built
in C33 because it is still new surface area beyond what *"expose it"*
asks for; it is named here as the concrete next step, the same way this
report's own Observation 2 names its follow-up rather than building it.

---

## 3 · Voice — present in the abstraction, absent by design in the implementation

*"Voice is primary. Text is fallback."* No real speech engine exists
anywhere in this codebase to make voice primary with: `master_agent.voice
.Speaker`/`Transcriber` both `raise NotImplementedError` (predating C1),
and C32's own forbidden list bars building one during this mission in as
many words (*"No speech recognition... No TTS... No Whisper... No
ElevenLabs... No Azure Speech... No Google Speech"*).

`app.py` boots with `voice_output=None` and reports this honestly in two
places: the boot report (`communication` step's own detail —
`"channels registered: text"`, never claiming voice) and the console's
own banner (*"Voice is not wired in this build — no speech engine exists
in this codebase"*). This is the inverse of the brief's stated priority,
and it is stated as a deviation rather than silently accepted: **text is
primary and fully working; voice is the honestly-absent fallback**,
because building a working one would have meant violating C32's own
forbidden list to satisfy C33's UX preference — and C33's own list
repeats the same prohibition (*"No speech recognition... No microphone
APIs. No TTS"*). The two briefs agree with each other on what must not be
built; only the *priority* language differs, and the constraint wins.

What *is* real: `Source.VOICE` requests are answered identically to
`Source.TEXT` ones by the whole booted application (`TestVoiceAndTextParity`,
§6) — the architecture is voice-ready down to the wire; only a
microphone and a speaker are missing, and building either was explicitly
out of scope for both C32 and C33.

---

## 4 · The success-criteria dialogue, run for real

```
$ python app.py --founder-name Onkar

Kalpavriksha Founder Edition -- boot report
  [     ok     ] runtime ...
  [     ok     ] presence ...
  [     ok     ] environment_intelligence   19 applications scanned
  [     ok     ] conversation ...
  [     ok     ] connect_founder_runtime    3 of 3 sources wired
  [     ok     ] founder_identity           Somesh is awake for Onkar
  [     ok     ] conversation_engine        Somesh can answer greetings, ...
  [     ok     ] communication              channels registered: text
  [     ok     ] desktop_executive          19 application profiles available
  [     ok     ] desktop_perception         the desktop can be observed
  [     ok     ] desktop_operator           one executor and one observer, shared with perception
  [     ok     ] dashboard                  8 sections composed
  [out_of_scope] render_founder_surface     ...
  [     ok     ] ready ...

------------------------------------------------------------
 Somesh, for Onkar (Kalpavriksha Founder Edition)
------------------------------------------------------------
 ... (live dashboard) ...
------------------------------------------------------------
You: Good morning Somesh
Somesh: Good morning. I'm awake. Everything is ready.
... (dashboard reprints, conversation now 2 turns) ...
You: Continue
Somesh: Continuing.
You: How's the system?
Somesh: I don't have a desktop reading yet. The environment looks
        healthy. I'm here and fully connected. Nothing is waiting on
        your approval.
... (dashboard reprints, conversation now 6 turns) ...
You: switch to voice
[console] the current mode needs a voice output, but none was registered
-- switching back to text.
Somesh: Switched to text.
You: Continue
Somesh: Continuing.
You: quit
Stopping -- the founder runtime is a fresh session next launch.
```

Every arrow the brief draws is real for the text path: **Founder types →
Communication Layer → Conversation Engine → Somesh → Founder Runtime
[conversation] updated → Dashboard refreshed** — no mocks, one real boot,
real desktop scan, real `ConversationEngine`/`CommunicationEngine`
instances. `tests/test_founder_edition_console.py::TestRunReplAndMain::
test_run_repl_completes_the_success_criteria_dialogue` runs this exact
script through the real REPL loop and asserts on the captured output.

---

## 5 · Observation 2 — `ChannelNotRegistered` leaves the router's mode changed even though the switch failed

**Found while wiring the REPL, not anticipated.** `CommunicationRouter.
route()` flips its own `_mode` **before** returning a `RoutedResponse`;
`CommunicationEngine.handle()` then calls `_emit()`, which is where
`ChannelNotRegistered` is actually raised if the new mode needs a channel
nobody registered. The consequence: after `handle()` raises, the mode has
already changed, and *every subsequent* `handle()` call — including an
ordinary, previously-working reply — also raises, because it still
resolves to a mode that has no channel. A founder saying *"switch to
voice"* in a text-only build would otherwise strand the whole
conversation, permanently, with one typo.

**This was not fixed inside `communication/`.** C32 is a complete,
audited-pending component (`Engineering/HEALTH_C32.md`), and this
integration mission does not reopen it. The fix lives entirely in
`console.py`, the launcher layer this mission owns:
`process_line()` catches `ChannelNotRegistered`, tells the founder
honestly what happened, and immediately routes a synthetic, *real*
`"switch to text"` request through the same `CommunicationEngine` —
a recognised phrase, not a fabricated reply, restoring the mode the same
way any other founder-issued switch would. `TestProcessLine::
test_switching_to_voice_recovers_to_text_automatically` and
`test_the_app_stays_usable_after_a_voice_switch_recovery` both exercise
this directly; §4's own transcript shows it firing for real.

**Proposed follow-up, not built here:** the durable fix belongs to C32
itself — either `CommunicationRouter.route()` should not commit a mode
change until the channels it needs are confirmed registered, or
`ChannelNotRegistered` should roll the mode back atomically. Recorded for
whoever next audits or extends `communication/`.

---

## 6 · Test evidence — the brief's own eight "Prove" items

| Prove | Test |
|---|---|
| Voice → Somesh | `TestVoiceAndTextParity` — `Source.VOICE` requests reach `ConversationEngine` and produce identical replies to `Source.TEXT`, exercised through the fully booted app, not a bare router |
| Text → Somesh | `TestRunReplAndMain::test_run_repl_completes_the_success_criteria_dialogue` — the real REPL, real replies |
| Dashboard updates after every interaction | `TestDashboardUpdatesLive` — conversation count and session-active state both change after `communication.handle()`, unchanged after a bare mode switch |
| Runtime remains single source of truth | `TestRuntimeIsSingleSourceOfTruth` — `session`, `runtime.conversation()`, and `dashboard()["conversation"]` all read the identical turn after one interaction; `console.py` never calls `.handle()` on anything named `runtime` (AST-checked) |
| Desktop Operator remains reusable | `TestDesktopOperatorExposedNotExecuted` — `app.desktop.operator` is reachable; `.execute(` appears nowhere in `console.py` or `app.py` (AST-checked) |
| No duplicated conversation logic | `TestNoDuplicatedLogic` — none of C31/C32's classes are redeclared; none of Somesh's actual sentences (*"I'm awake"*, *"Continuing."*, …) appear as a literal string in `console.py`; the reply the REPL prints is read back from the real output channel, not composed separately |
| No duplicated identity logic | Same suite — `FounderIdentity` is not redeclared; `console.py` never calls `greet()`/`continuity_reply()` directly, only through `app.communication.handle()` |
| Existing C24–C32 tests still pass | See below |

```
python -m pytest tests/test_founder_edition_console.py -q
  56 passed

python -m pytest tests/test_founder_edition_console.py tests/test_founder_edition_boot.py \
                tests/test_founder_edition_assembly.py --cov=master_agent.founder_edition
  __init__.py         5 stmts   0 miss  100%
  boot.py           240 stmts   0 miss  100%
  console.py        111 stmts   1 miss   99%   (the `if __name__ == "__main__"` guard)
  dashboard.py       19 stmts   0 miss  100%
  desktop_layer.py   52 stmts   0 miss  100%
  TOTAL             427 stmts   1 miss   99%
  187 passed

python -m ruff check src/master_agent/founder_edition/ app.py tests/test_founder_edition_console.py
  All checks passed!

python -m pytest tests/test_founder_identity.py tests/test_founder_runtime.py \
                tests/test_conversation_engine.py tests/test_communication.py -q
  337 passed   # C23, C29, C31, C32 — every one unedited
```

**524 tests across the whole C23–C33 lineage, all green, none of C24–C32's
own test files touched.**

---

## 7 · Known limitations

1. **No graphical desktop window.** The terminal is the window for this
   alpha; §2 argues why and names the smallest real follow-up.
2. **No real voice channel.** §3 argues why building one would violate
   both C32's and C33's own forbidden lists.
3. **`ChannelNotRegistered` after a mode switch is a real C32 gap**,
   worked around at the launcher layer rather than fixed at its source.
   §5.
4. **cp1252 console encoding.** Some boot-step detail strings (carried
   verbatim from C23/C24, e.g. an em dash in *"attested; incomplete —
   ..."*) do not render on a plain Windows cp1252 terminal. `launcher.
   main`'s own MB026 finding already names this class of problem and its
   fix (ask the stream what it can encode); `console.py`'s own formatting
   functions are ASCII-only, but the underlying `BootStep.detail` strings
   are not, since editing C23/C24's own text is out of this mission's
   scope.
5. **`founder_context()` still hears nothing about desktop readiness in
   greetings.** Named already in `HEALTH_C30.md` §6.3 — unchanged here,
   since fixing it means editing C29, out of scope for an integration
   mission.
6. **No test drives the app against a second, different machine's real
   desktop mutation.** Every scenario here is real-boot but read-only on
   the desktop side (`DesktopOperator` is reachable, never executed, by
   design — §6).

---

## 8 · Frozen components and prior deliverables

```
git status --porcelain -- foundation kernel ledger coordinator runtime_bridge api
→ (empty)

git status --porcelain -- founder_runtime founder_identity conversation_engine
                          communication desktop desktop_operator
→ (only the untracked directories themselves; no tracked file modified)
```

Every source file this mission touched is `founder_edition/boot.py`
(extended, not rewritten — every C24/C30 line before this mission's edits
is still present and in its original relative order), `founder_edition/
console.py` (new file in an existing package), and `app.py` (new,
six-line shim at the repo root). Nothing else in `src/` was edited.

---

*End of report. Working-directory evidence only. No commits, no tags, no
Rule 001 milestone declared. Stop. Waiting for Hermes audit.*
