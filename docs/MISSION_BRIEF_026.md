# Mission Brief 026 — Founder Dashboard (Founder Edition v1)

Status: Shipped — 2026-07-26

## Objective

The first operational window into a living autonomous system: a read-only
Dashboard consuming Runtime, Mission Control, Audit, Persistence, and
Founder State through their published contracts.

## Contract survey first, code second

MB026 required that a missing contract stop implementation and raise an
ADR. So the survey came before the UI
(`FOUNDER_DASHBOARD_ARCHITECTURE.md` §2): **every panel's data is
reachable through existing published surfaces. No gap was found, and no
blocking ADR was needed.**

The one item that *looked* like a gap turned out not to be: "Recovery
Status" is not discoverable by reading — the Dashboard must not call
`recover()`, since that is both a mutation and orchestration. It is handed
in by the launcher that already ran recovery (ADR-0016 Decision 5).

**No frozen component was modified. Not one line** — asserted by a test
that runs `git diff` against the MB025 tag over
`mission_control/`, `runtime/`, `persistence/`, `verification/`,
`plugins/`, and `executor/`.

## What was built

| Deliverable | Implementation |
|---|---|
| 1. Dashboard Shell | `dashboard/app.py` — `FounderDashboard`, `build_dashboard()` |
| 2. Runtime Status | `render_runtime` — all six named fields |
| 3. Current Mission | `render_mission` — objective, progress bar, executive, capability, ETA, status |
| 4. Executive Panel | `render_executives` — name, health, version, status, capability count |
| 5. Capability Panel | `render_capabilities` — registered names + pending/active/completed |
| 6. Audit Panel | `render_audit` — recent events with a scroll window |
| 7. Persistence Panel | `render_persistence` — checkpoint, schema version, log size, recovery |
| 8. System Health | `render_system_health` — five indicators |
| 9. Founder State | `render_founder_state` — published dict, verbatim |
| 10. Live Updates | bus subscription + clock tick, no manual refresh |

Supporting layers: `readmodel.py` (frozen snapshot), `sources.py`
(tolerant collectors), `health.py` (pure classification), `panels.py` +
`renderer.py` (pure rendering), `charset.py` (glyph fallback).

## The three decisions worth reading

**1. A frozen read model sits between contracts and rendering.** Panels
receive plain data and return strings; they never hold a live object. Two
consequences: rendering is testable without a Runtime or a browser (which
is why 182 tests were cheap rather than heroic), and a panel *physically
cannot* mutate anything, so read-only becomes a property of the data flow
rather than a rule someone must remember.

**2. Absence is a first-class value.** `0` and "unknown" are different
facts. A queue length of `0` means nothing is waiting; an unreadable queue
means we do not know. Every read is wrapped so a failure becomes absent
data *with a reason*, and a Dashboard wired to nothing still renders a
complete, honest frame — never a fabricated zero.

**3. Health classification is presentation, and is quarantined to prove
it.** Deliverable 8 sits closest to Rule 4 ("no business logic"), so the
boundary is stated and enforced: all classification lives in `health.py`
as pure functions of plain numbers, nothing in Kalpavriksha reads the
result, and every panel shows the raw counts beside the label. Deleting
the health labels would change what a founder sees and nothing about what
the system does.

## A real portability defect the first run caught

The very first smoke render crashed with `UnicodeEncodeError`: the
Windows console's default code page (cp1252) cannot encode the
box-drawing and block glyphs the frame is built from. **A dashboard that
cannot render on the founder's own terminal is not a dashboard.**

Fixed properly rather than by mangling output: rendering is parameterised
by a `Charset`, and the default is chosen by *asking the output stream
what it can encode* rather than guessing from the platform name — so a
Windows terminal running UTF-8 still gets the nice glyphs, and a cp1252
one gets clean ASCII instead of a traceback.

## An under-delivery the tests caught

The Definition-of-Done test failed on `assert "Filesystem." in frame`, and
the reason was not a test bug: the Capability panel showed only a *count*
of registered capabilities. Deliverable 5 says "Display: Registered
Capabilities" — the names. Now it names them, wrapped and bounded (eight,
then "... and N more"), so a system with two hundred capabilities cannot
push every other panel off the screen.

## Live verification

Killed, restarted, reconnected, resumed — the founder issuing no command
after startup:

```
=== AFTER RESTART, BEFORE RESUMING ===
MISSION
  Increase Founder Net Worth
  Progress          ##########......  67%
  Status            in progress
PERSISTENCE
  Snapshot Version  1
  Recovery          recovered (snapshot)

=== AFTER RESUMING TO COMPLETION ===
MISSION
  Increase Founder Net Worth
  Progress          ################  100%
  Status            completed
CAPABILITIES
  Registered        14
    Filesystem.AppendFile  Filesystem.CopyFile
    Filesystem.CreateFolder  Filesystem.DeleteFile
    ... and 6 more
  Completed         3
AUDIT  (112 events, 0 failures)
```

Acceptance criteria 8-10 (restart, reconnect, restored state displayed
correctly) are visible in that transcript and asserted in
`test_dashboard_live.py`.

## Testing

**182 new tests; 971 passing overall**, zero regressions, one skip
(a charset test that does not apply on this platform). `ruff check` clean
on every new file.

| Category | File |
|---|---|
| UI rendering | `test_dashboard_panels.py` (57) |
| Contract | `test_dashboard_sources.py` |
| Health rules | `test_dashboard_health.py` |
| Frame composition | `test_dashboard_renderer.py` |
| Live update + restart | `test_dashboard_live.py` |
| Architecture (Rules 1-4) | `test_dashboard_architecture.py` |

The strongest read-only test renders 25 frames against a live system and
asserts task states, audit length, and cycle counter are byte-identical
afterwards.

## Technical debt / known limitations

- **"Event Log Size" is O(log).** It comes from `read_events()`, which
  returns the entire persisted log. The right fix is a `count_events()`
  on the `StateStore` contract — a *persistence* change, deliberately not
  made because MB025 is frozen. Mitigated by the audit window and noted in
  `ROADMAP.md`.
- **Audit scrollback is bounded by the snapshot window** (default 20),
  not the full history. Full history remains available through the audit
  contract.
- **Terminal only.** A web front-end consumes the same
  `DashboardSnapshot` and discards `panels.py`; `ARCHITECTURE.md` §4.10
  keeps that path open and nothing here forecloses it.
- **No filtering, search, time-travel, or export**, and no mission
  submission — explicitly out of scope; this dashboard is observational.

## Recommendation for the next Mission Brief

Kalpavriksha now runs autonomously, survives restarts, and can be watched.
The conspicuous gap is what it can *do*: one real Executive (Browser) and
a Filesystem Executive that exists only as a capability family. The
highest-value next Miracle is a **second real Executive** — Terminal is
the natural choice, because it doubles as the test of whether
`BrowserSessionManager`'s shape genuinely generalises into a shared
`EnvironmentSessionManager` (the "second example" MB022 said was needed
before extracting one).

The alternative, if the founder wants reach before depth, is the **real
Planner** (`ROADMAP.md` item 1) — still unbuilt, and now the only thing
standing between "a founder writes task DAGs by hand" and "a founder
states an intent."
