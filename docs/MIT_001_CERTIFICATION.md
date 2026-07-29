# MIT-001 — Mission Control Integration Certification: Browser Executive

Status: **CERTIFIED** — 2026-07-26
Objective: *Can Mission Control orchestrate the Browser Executive without
modifying the Browser Executive?*

**Answer: yes.** All seven tests pass, verified two ways: 19 automated
tests (`tests/test_mit_001_browser_integration.py`) and one live run
against the real internet (transcript in §Live Verification below).

---

## Results at a glance

| Test | Result | Evidence |
|---|---|---|
| 1 — Executive Discovery | ✅ Pass | Auto-discovered from the Plugin Registry; nothing names a browser |
| 2 — Capability Registration | ✅ Pass, 2 notes | 9 capabilities derived from the manifest; see §Two deliberate differences |
| 3 — Task Dispatch | ✅ Pass | Real navigation reached `https://example.com`; Mission Control never navigated |
| 4 — Event Bus | ✅ Pass | Full expected sequence emitted in order |
| 5 — Audit Stream | ✅ Pass | Objective, timestamps, Executive, Capability, verdict all present |
| 6 — Founder State | ✅ Pass | JSON with the MIT-001 shape, including `result` |
| 7 — Zero Modification ⭐ | ✅ Pass | `git diff` against the MB022 tag is empty, asserted by a test |

Full suite after this work: **519 passing, 0 failing.** `ruff check`
clean on every changed file.

---

## What had to change to pass (and what did not)

The Browser Executive was **not** touched — that is the whole point of
Test 7. Four gaps were closed on the *Mission Control* side, plus one
read-only accessor on Shared Infrastructure:

1. **Auto-discovery did not exist.** MB023 shipped explicit registration;
   Test 1 asks Mission Control to *discover* the Executive. Added
   `discover_executives(mission_control, plugin_registry)`, which walks
   the Plugin Registry and registers whatever it finds. Nothing in it
   names a plugin, counts capabilities, or knows a browser exists.
2. **`TASK_DISPATCHED` → `TASK_ASSIGNED`.** MIT-001 specifies
   `TASK_ASSIGNED` in its expected sequence. Renamed rather than aliased —
   two names for one event is exactly the drift the Constitution's
   terminology freeze forbids.
3. **Founder State gained `result`.** Test 6 asks for a Result alongside
   Progress; MB023's ten fields did not include one.
4. **Verification events now carry the capability.** The first live run
   showed `verification_completed | cap: None`, so Test 5's "Capability
   used" was only answerable by joining back through `task_id`. Now
   stamped directly.
5. **`PluginRegistry.all_plugins()`** — a read-only accessor, needed so
   discovery reads the registry through its contract instead of reaching
   into `_plugins` (`ENGINEERING_PRINCIPLES.md` #8). Additive; no existing
   caller changes. Worth naming plainly: this is a change to *Shared
   Infrastructure*, not to an Executive, so Test 7's principle is intact —
   but it is a change, and this document does not pretend otherwise.

---

## Two deliberate differences from the brief's expected output

Both are in Test 2's expected capability list. Neither is a defect, and
both are worth understanding before MB024.

### `Browser.Fill` is called `Browser.TypeText`

The capability exists and does exactly what "Fill" implies (it wraps
Playwright's `fill()`, setting an input's value). The name comes from the
Action shipped in MB022 (`type_text`), transformed by the one
deterministic rule `qualified_name()` applies to every capability. Renaming
it to match the brief would mean either renaming a shipped Action
(Constitution Rule 2) or special-casing one capability in the naming rule —
the latter reintroducing exactly the hand-maintained lookup table the rule
exists to avoid.

### There is no `Browser.Verify`, on purpose ⭐

This one is architectural, not cosmetic. **ADR-0011 makes Verification
structurally independent of Execution**: a Verifier is never invoked
through the Capability/`invoke()` path, because a component that can be
dispatched as ordinary work is not an independent check of that work.
Adding a `Browser.Verify` capability would mean a task could "verify
itself" through the same mechanism it executes with — collapsing the exact
distinction MB022 was built to establish (an Action can return
`success=True` while Verification independently returns `NOT_MATCHED`).

Verification is present in this system, and MIT-001 exercises it: as its
own subsystem (`BrowserVerifier`), as `VERIFICATION_STARTED` /
`VERIFICATION_COMPLETED` events (Test 4), and as a verdict + evidence ID
in the audit stream (Test 5). It is simply not a dispatchable capability,
and should not become one.

---

## Live Verification

Run against the real internet, not a fixture. Abridged transcript:

```
--- TEST 1: Executive Discovery ---
discovered: ['browser'] | status: ready | health: healthy | version: 0.1.0

--- TEST 2: Capability Registry ---
   Browser.Click
   Browser.CloseBrowserSession
   Browser.Navigate
   Browser.ObserveBrowser
   Browser.OpenBrowserSession
   Browser.PressKey
   Browser.Scroll
   Browser.TypeText
   Browser.WaitForSelector

--- TEST 3: Task Dispatch (real navigation to https://example.com) ---
assigned: [('open', 'browser')]
open ok: True
assigned: [('nav', 'browser')]
navigate ok: True | output: {'url': 'https://example.com/', 'title': 'Example Domain'}
VERDICT: matched | evidence: 5865aeb6

--- TEST 4: Event Bus sequence ---
   12 objective_submitted
   13 task_created
   14 task_created
   15 task_assigned
   16 task_started
   17 task_completed
   18 task_assigned
   19 task_started
   20 verification_started
   21 verification_completed
   22 task_completed
   23 objective_completed

--- TEST 6: Founder State ---
{
  "current_mission": "Navigate to https://example.com",
  "progress": 1.0,
  "result": { "url": "https://example.com/", "title": "Example Domain" },
  "evidence": ["5865aeb6-bf9b-481c-939e-673a6f715a05"],
  "errors": []
}
```

Note the `objective_completed` event at sequence 23: the objective closed
itself once both tasks completed. Note also that the automated suite uses
locally-generated pages rather than the network — the certification must
stay deterministic and offline-capable; this live run is the separate
proof that it works outside a sandbox, per `FOUNDER_PLAYBOOK.md`'s
"verify manually at least once against the real stack".

---

## Test 7 in detail — the Zero Modification Principle ⭐

Three independent proofs:

1. **`git diff v0.6.0-miracle-022 HEAD` over every Browser Executive path
   is empty** — and this is asserted by a test
   (`test_7_browser_executive_source_is_untouched_since_mission_brief_022`),
   so it cannot silently stop being true.
2. **Mission Control holds no reference to the Executive.** The registries
   store descriptors; a test walks every field of the Executive record and
   capability descriptor asserting none is a `BrowserPlugin`. Mission
   Control could not invoke the browser even if it tried.
3. **Mission Control opened no session of its own.** After a full dispatch
   cycle, `sessions.list_sessions()` is empty except where the *Executive*
   opened one on instruction.

**Open for Extension, Closed for Modification: proven.** The same
discovery call also picked up an unrelated `FilesystemPlugin` with no
Mission Control change
(`test_1_discovery_finds_whatever_is_installed_not_a_known_list`), which
is the extension half of the claim.

---

## Certification

> **Mission Control Integration Certified — Browser Executive**

- **MB022 (Browser Executive)** — Complete
- **MB023 (Mission Control)** — Complete
- **MB023 Integration (MIT-001)** — Complete

The backend is stable enough to visualize. MB024 (Founder Dashboard) is
unblocked; `MissionControl.founder_state().as_dict()` is the contract it
renders, and it is already JSON-serializable today.

## One honest caveat before MB024

Nothing yet *drives* the loop end to end. In every test and in the live
run above, an outside caller pulls `dispatch_ready()`, invokes through the
Worker, and reports back. That caller is the missing piece — a runner that
closes the loop automatically. MIT-001 proves every seam works; it does
not prove the system runs unattended, and a dashboard built now would be
visualizing a system a human is still hand-cranking. Worth deciding
deliberately whether the runner comes before or after MB024, rather than
discovering it mid-dashboard.
