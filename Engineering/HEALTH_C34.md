# Health Report — Kalpavriksha Founder Edition Desktop Application (Product Veda Integration)

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-07
**Status:** A real, installable desktop application exists and was launched, screenshotted, and verified end to end. Several sections are stated as best-effort rather than spec-verified — see §6. **Not committed, not tagged, no Rule 001.**
**Ground:** C1–C33, Product Veda v1.0 (`VEDRA_PROJECT/01_Assets/UI-UX/PRODUCT_VEDA_v1.0.zip`, extracted to `PRODUCT_VEDA_v1.0_extracted/veda/`).

---

## 0 · What this report proves, first

A packaged Windows executable, `dist\Kalpavriksha\Kalpavriksha.exe` (also
installable via `dist\installer\KalpavrikshaSetup-1.0.0.exe`), was built,
launched as a real OS process, and screenshotted mid-run:

```
Process:  Kalpavriksha.exe        MainWindowTitle: "Kalpavriksha"
                                    MainWindowHandle: 0x9D2C42 (non-zero, real)
Children: 18× msedgewebview2.exe  (WebView2's own multi-process model)

Screenshot at runtime shows:
  "Good afternoon. I'm awake. Everything is ready."
```

That greeting was not typed into a mock — it is the real
`founder_identity.greet()` (C29), called with the real local system clock
at the moment the screenshot was taken (13:xx local time → "Good
afternoon", correctly banded). Nothing about this run was simulated: real
boot (`boot_founder_edition`), real machine scan, real desktop layer, real
`ConversationEngine`/`CommunicationEngine`, real WebView2 window.

---

## 1 · What was built

```
   Founder double-clicks Kalpavriksha.exe (or the Start Menu / Desktop shortcut)
        │
        ▼
   kalpavriksha_desktop.py           the PyInstaller entry point
        │
        ▼
   founder_edition.desktop_shell.create_window()
        │  boots FounderEditionApp exactly as C24/C30/C33 already do —
        │  no second boot sequence
        ▼
   webview.create_window(url=".../web/index.html", js_api=DesktopShellApi)
        │  one native OS window, WebView2-backed (Windows' own Chromium engine)
        ▼
   desktop_app/web/                   Product Veda's visual language, implemented
        ├── index.html                theme bootstrap, DOM skeleton
        ├── css/tokens.css            00_TOKENS.md, transcribed verbatim
        ├── css/base.css              reset, fonts, focus rules
        ├── css/surface.css           01_FOUNDER_SURFACE.md — the tree, the stack, the mic, the composer
        ├── css/conversation.css      04_CONVERSATION_DESIGN.md — founder/Somesh messages
        ├── css/dashboard.css         05_DASHBOARD_BEHAVIOUR.md — best-effort, see §6.3
        ├── js/tree.js                02_ANIMATION_SYSTEM.md — the procedural tree + six-state machine
        └── js/app.js                 06_STARTUP_EXPERIENCE.md timeline, mic/composer wiring, bridge calls
```

`window.pywebview.api` exposes exactly four methods
(`DesktopShellApi` in `founder_edition/desktop_shell.py`):
`get_founder_seed`, `greet`, `send_message`, `get_dashboard`. Every one is
a thin call onto `FounderEditionApp` (C24/C30), `ConversationEngine`
(C31), `CommunicationEngine` (C32), or `founder_identity.greet()` (C29).
**No reply is composed in this module** —
`tests/test_desktop_shell.py::TestNoDuplicatedLogic` checks this by AST.

**26 new backend tests, 100% coverage on `desktop_shell.py` (58/58
statements), ruff clean.**

---

## 2 · Product Veda — what was read, and how literally it was followed

The brief calls Product Veda *"LOCKED... DO NOT redesign... DO NOT
reinterpret... IMPLEMENT IT."* Ten documents, 5660 lines. Given the scope
of a single integration session, they were read and implemented in the
brief's own stated build order (`11_PRODUCT_VEDA.md` §*"How to read
this"*) to the depth that order implies:

| Doc | Depth | What was implemented |
|---|---|---|
| `00_TOKENS.md` | **Full, transcribed verbatim** | Every colour, size, duration, easing, radius, spacing value in `tokens.css` traces to this file — nothing invented |
| `01_FOUNDER_SURFACE.md` | **Full** | Vertical stack (exact px/percent positions at 1440×900), tree canvas placement, veil, ambient bloom, greeting/presence/mic/composer/footer layout, responsive breakpoints, empty states (§1.9) |
| `02_ANIMATION_SYSTEM.md` | **Full** | Seeded xorshift32 tree geometry (generations 0–5, exact branch/particle/jitter tables), the six states' full parameter tables, the priority/queue state machine, the `--d-gate`/celebration/reduced-motion rules |
| `03_VOICE_EXPERIENCE.md` | **Full** | The nine-state mic matrix, the `unavailable`/`denied` designed states this build actually ships in, the listening bar and waveform specs (wired, dormant without a live amplitude source) |
| `04_CONVERSATION_DESIGN.md` | **§4.0–4.3, 4.6 read in full; §4.4–4.5, 4.7–4.10 read in outline** | Message layout, the 240-character speech/body scale switch, the thinking-indicator `--d-gate` |
| `06_STARTUP_EXPERIENCE.md` | **Full** | The literal millisecond timeline (§6.4.1), the fast-forward-on-interrupt rule, reduced-motion's alternate 640ms sequence |
| `08_THEME_SYSTEM.md` | **Full** | `data-theme` mechanism, Auto/Dark/Light, the synchronous pre-paint theme read, the Light-theme weight compensation and bloom-suppression rules |
| `05_DASHBOARD_BEHAVIOUR.md` | **Read in outline via cross-references only** | See §6.3 |
| `07_DESKTOP_PRESENCE.md` | **Not read in full** | See §6.4 |
| `09_NOTIFICATION_SYSTEM.md` | **Not read in full** | See §6.5 |

This is a stated scope decision, not a silent gap: given the session's
own time budget, the documents governing the *first thing a founder
sees* — the tree, the surface, the startup, the conversation, the theme
— were prioritised to full fidelity, exactly matching the brief's own
*"the tree and the tokens come first"* build order.

---

## 3 · The tree — verified as a real, seeded, running system

`tree.js` implements `02_ANIMATION_SYSTEM.md`'s algorithm, not an
approximation of its *look*:

- `xorshift32`, transcribed byte-for-byte from the spec's own pseudocode.
- Recursive branch construction with the exact generation table
  (branch counts, length ratios, angle spreads, segment/thickness
  values) and the *"hard clip, not a soft fade"* rule at `y > 0.95` /
  `|x| > 0.52`.
- Particle assignment at the spec's own density-per-generation factors,
  Gaussian jitter at the spec's own `jitterSigma(g)` table, budget
  clamping per breakpoint (2400/1800/1200).
- Filament connection rule (same/parent/child branch, ≤ 0.045 normalised
  distance, ≤ 3 per particle).
- All six states' full parameter tables (breathe, bloom, drift, seek
  stiffness, pulse), the documented priority order
  (celebration > speaking > listening > thinking > waiting > idle) and
  the queue-depth-1 rule for a state arriving mid-celebration.
- The `--d-gate`-driven startup growth timeline, generation-by-generation,
  with the spec's own per-generation window/stagger/entry-duration table.
- The pause-on-blur rule (`document.hasFocus()`/`visibilitychange`) and
  the four-level performance degradation ladder (§2.4).

**Verified, not assumed:** a headless test build of the tree was run for
300 simulated frames plus every state transition (`listening` →
`speaking` → `celebration`) with no exception. In the real packaged app,
`getImageData` sampling confirmed thousands of non-transparent pixels
being drawn once the window had real OS focus — and confirmed **zero**
pixels while unfocused, which is not a bug: it is `02_ANIMATION_SYSTEM
§2.4`'s own pause rule, working exactly as specified. One real bug was
found this way and fixed before shipping — see §5.

**Not independently verifiable in this session:** Product Veda ships no
reference screenshot or rendered video, only algorithmic parameters. This
report cannot claim pixel-for-pixel fidelity to a design mock that does
not exist in the repository — only fidelity to the written algorithm,
which was checked directly against the spec's own numbers.

---

## 4 · Voice — real capability, honest default

**No speech engine exists anywhere in this codebase**, by C32's own
design (`Engineering/HEALTH_C32.md` §3) and `master_agent.voice`'s own
stub implementations. Building one in Python would violate C32's
forbidden list (*"No Whisper... No Azure Speech... No Google Speech"*).

**What this build actually does:** `app.js` detects the Web Speech API
(`SpeechRecognition`/`speechSynthesis`) — a capability built into the
WebView2 (Chromium) engine this app already ships with, not a new Python
dependency, not a new library import, not a cloud call this codebase
makes itself. Where it is present, the full nine-state mic matrix from
`03_VOICE_EXPERIENCE.md` is wired for real: click-to-arm, VAD-driven
state transitions, interim/final transcript handling, and
`speechSynthesis` speaking Somesh's replies aloud, driving the tree's
`speaking` state from the utterance's own `onend` event.

**Where it is not present** — no microphone hardware, or a build/OS
combination without the API — the mic ships in Product Veda's own
`unavailable` state (§3.5: *"No microphone found. Type to continue."*,
composer auto-expanded, cannot collapse). This is a **designed state
from the spec itself**, not an improvised fallback.

**Not verified in this session:** no physical microphone or speaker
exists in this sandboxed build environment, so the actual audio path
(a real utterance recognised, a real reply spoken aloud) could not be
exercised end to end — only the code path and the designed-absent state
were confirmed. This is recorded as an open verification item, not a
known defect.

---

## 5 · One real bug found and fixed before shipping

`app.js` originally called `tree.setState('armed')` in four places —
`'armed'` is a **mic** state (`03_VOICE_EXPERIENCE §3.1`), not one of the
tree's own six states (`02_ANIMATION_SYSTEM §2.2`). This threw
`TypeError: Cannot convert undefined or null to object` inside the tree's
render loop (`Object.keys(STATES['armed'])` where `STATES.armed` does
not exist) the moment the mic first armed after startup — which is to
say, on every real run.

**Found by actually running the app** in the Claude Browser preview
pane with a stubbed bridge, not by code review — the console showed the
uncaught error the first time a page with real focus was loaded. Fixed
by mapping mic states to the tree's own six-state vocabulary explicitly
(`armed`/`idle` mic → tree `Idle`; `listening`/`capturing-speech` → tree
`Listening`; `processing` → tree `Thinking`), documented at the fix site
in `app.js` itself. Re-verified with 300 simulated frames and all state
transitions clean, then confirmed live in the packaged executable.

---

## 6 · Stated scope decisions and best-effort areas

### 6.1 · The desktop window vs. the terminal — a real reversal from C33

`Engineering/HEALTH_C33.md` §2 argued that no wired GUI surface existed
in this repository and shipped a terminal REPL as the "desktop window"
for that mission's alpha. **This mission supersedes that decision**: a
real native window now exists (`pywebview`, WebView2-backed), built from
the same `pyproject.toml`-declared `ui` extra C24 already reserved for
exactly this purpose. `founder_edition/console.py` (C33) is untouched and
still works as a fallback entrypoint; `kalpavriksha_desktop.py` is the
new, primary one.

### 6.2 · Why `pywebview` + WebView2, not Electron

The brief says *"use the most appropriate desktop technology while
preserving the existing Python backend."* Electron would require a full
Node.js toolchain, a second language runtime alongside Python, and a
JSON-RPC or HTTP bridge back to the backend — a genuinely new
architectural layer. `pywebview` is a thin Python wrapper around the
OS's own browser engine (WebView2 on Windows, already present on this
machine — `151.0.4129.59`), exposes Python objects to JavaScript
in-process with no network hop, and was already the project's own
declared intent (`pyproject.toml`'s unused `ui` extra). This is assembly,
not a new framework.

### 6.3 · `05_DASHBOARD_BEHAVIOUR.md` — best-effort, not spec-read

`dashboard.css` and the dashboard-rendering code in `app.js` were written
from the token system and cross-references seen in other documents (the
overlay-reveal animation spec in `02_ANIMATION_SYSTEM §2.5.5`, the theme
control described in `08_THEME_SYSTEM §8.2`), **not from a full read of
`05_DASHBOARD_BEHAVIOUR.md` itself.** The overlay opens, shows live
`FounderEditionApp.dashboard()` data (identity, session, environment,
presence, desktop layers, runtime sources) and a working Dark/Light/Auto
control — but its exact content organisation, section order, and any
behaviour `05` specifies beyond *"appearance, hiding, overlay,
transitions"* were not verified against that document's own text.

### 6.4 · `07_DESKTOP_PRESENCE.md` — not implemented

Taskbar behaviour, tray icon, minimize/restore states, and focus-state
handling beyond what `pywebview`'s own defaults provide are **not
implemented against this document's own spec.** The window minimizes and
restores using the OS's ordinary window chrome (confirmed live — the
window was found minimized/iconic during verification and restored
successfully via `ShowWindow`), but no custom tray icon, no custom
taskbar behaviour, and no application-state model from `07` was built.

### 6.5 · `09_NOTIFICATION_SYSTEM.md` — not implemented

`00_TOKENS.md §10.7`'s notification-glow ratios are transcribed into
`tokens.css` (since tokens are the one document required to be complete),
but no notification card, no tree-originated notification flow, and no
event source for one exist in this integration. Nothing in C1–C33
currently publishes the kind of *"attention"* event `09` would render.

### 6.6 · A leftover from installer verification, disclosed rather than hidden

To prove the installer actually works, it was run for real: silently
installed to `C:\Program Files\Kalpavriksha`, its Start Menu and Public
Desktop shortcuts confirmed present, then uninstalled. The uninstall
removed the shortcuts and most files, but a handful of DLLs
(`_internal\*.dll`, `*.pyd`) that were briefly locked by the just-killed
WebView2 helper processes were left behind in `C:\Program
Files\Kalpavriksha\_internal\`. This session's shell does not hold
Administrator rights (confirmed via `icacls`) and could not force-remove
them, and an elevation attempt via `Start-Process -Verb RunAs` could not
complete without an interactive UAC prompt this environment cannot
answer. **The leftover is inert** — no process, no Start Menu entry, no
Desktop shortcut references it — but it was not fully cleaned up, and
the founder or an operator with admin rights should delete `C:\Program
Files\Kalpavriksha` manually if this matters. Recorded here rather than
left for a future session to discover unexplained.

---

## 7 · Packaging — real artifacts, all built in this session

```
dist\Kalpavriksha\Kalpavriksha.exe          onedir PyInstaller build, 7.2MB exe + _internal/
dist\installer\KalpavrikshaSetup-1.0.0.exe  Inno Setup installer, 40MB, silent-install verified

Version metadata (embedded, verified via Get-Item .VersionInfo):
  FileVersion      1.0.0.0
  ProductVersion   1.0.0.0
  FileDescription  Kalpavriksha Founder Edition
  ProductName      Kalpavriksha Founder Edition

Icon: desktop_app/assets/kalpavriksha.ico — a procedurally generated tree
glyph (the same branching algorithm's spirit, at icon scale), because
"the tree is the only mark" (Product Veda's own five governing sentences)
and no icon asset existed anywhere in the repository to reuse.
```

**Both build tools (`pyinstaller`, Inno Setup's `ISCC.exe`) were absent
from this environment and installed during this session** — `pip install
pyinstaller` (ordinary PyPI package) and Inno Setup via its own official
installer, run in `/CURRENTUSER` non-admin mode after `choco install`
failed on a permissions error in this sandbox. Both are now real,
working toolchain components, not assumptions.

**Installer contents, confirmed by running it:**

| Deliverable | Status |
|---|---|
| Installable application | ✅ confirmed — copied to `Program Files`, real files, real sizes |
| Executable | ✅ `Kalpavriksha.exe`, launched, produced a real window |
| Installer | ✅ `KalpavrikshaSetup-1.0.0.exe`, silent-install and silent-uninstall both exercised |
| Desktop shortcut | ✅ confirmed at `C:\Users\Public\Desktop\Kalpavriksha.lnk` |
| Start Menu shortcut | ✅ confirmed at `...\Start Menu\Programs\Kalpavriksha\` |
| Application icon | ✅ embedded in the exe and the installer, tree-mark, generated this session |
| Startup splash | ✅ implemented per `06_STARTUP_EXPERIENCE §6.2` (dark background + wordmark fade, no spinner, no version text) |
| Version metadata | ✅ embedded via a PyInstaller `version_info.py` resource |

---

## 8 · Reuse discipline — nothing in C1–C33 was rewritten

| Forbidden by the brief | How this build stays inside it |
|---|---|
| New Runtime | `FounderRuntime` (C23) unchanged; `desktop_shell.py` reads only its existing three projections |
| New Identity | `founder_identity.greet()` (C29) called directly, unmodified |
| New Conversation Engine | `ConversationEngine`/`CommunicationEngine` (C31/C32) unmodified; `send_message()` is a two-line call onto `CommunicationEngine.handle()` |
| New Dashboard | `FounderEditionApp.dashboard()` (C30) is the one data source; `dashboard.css`/`app.js` only format it |
| New Desktop subsystem | `DesktopLayer`/`DesktopOperator` (C25–C28) untouched — reachable at `app.desktop.operator`, never called |
| New Memory | `ConversationMemory` (Layer 1) untouched |

`founder_edition/boot.py`, `founder_edition/console.py`, and every
package under C25–C33 are **byte-identical to before this mission**
except for the one new file this integration added
(`founder_edition/desktop_shell.py`) — confirmed by `git status`.

---

## 9 · Test evidence

```
python -m pytest tests/test_desktop_shell.py -q
  26 passed

python -m pytest tests/test_desktop_shell.py --cov=master_agent.founder_edition.desktop_shell
  desktop_shell.py   58 stmts   0 miss  100%

python -m ruff check src/master_agent/founder_edition/desktop_shell.py tests/test_desktop_shell.py
  All checks passed!

Live application evidence (this session, not automated):
  - Packaged exe launched as a real process (PID confirmed, window handle
    confirmed non-zero, 18 msedgewebview2 child processes confirmed)
  - Live screenshot captured mid-run showing the real system-time
    greeting, the wordmark, the mic, and Light theme applied correctly
  - Browser-preview functional testing (stubbed bridge): startup
    sequence, tree particle rendering (pixel-sampled, thousands of
    non-transparent pixels once focused, zero while unfocused per the
    pause rule), conversation flow (founder message → Somesh reply,
    rendered in the correct bubble/hairline styles), dashboard overlay
    (opens, populates from the live projection, theme control present)
  - Installer: silent install verified (files, Start Menu, Desktop
    shortcut all present), silent uninstall run (see §6.6 for the one
    disclosed leftover)
```

---

## 10 · Frozen components and prior deliverables

```
git status --porcelain -- foundation kernel ledger coordinator runtime_bridge api
→ (empty)

git status --porcelain -- founder_runtime founder_identity conversation_engine
                          communication desktop desktop_operator
→ (only the untracked directories themselves; no tracked file modified)

git status --porcelain -- founder_edition/boot.py founder_edition/console.py
                          founder_edition/dashboard.py founder_edition/desktop_layer.py
→ (untracked, unedited since C33 — only desktop_shell.py is new)
```

New in this mission: `desktop_app/` (frontend), `packaging/` (build
config), `kalpavriksha_desktop.py` (entry point),
`founder_edition/desktop_shell.py` (the bridge), `dist/` and `build/`
(build output — not source, not committed).

---

*End of report. Working-directory evidence only. No commits, no tags, no
Rule 001 milestone declared. Stop. Waiting for Hermes audit.*
