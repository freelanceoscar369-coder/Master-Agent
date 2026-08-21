# CONVERGENCE HANDOFF — Kalpavriksha Founder Edition

**This file is a resumability ledger, not architecture and not a second source of
truth.** Canonical truth lives in `docs/architecture/KALPAVRIKSHA_VISION_V2.md`,
`docs/architecture/FOUNDER_CONSTITUTION_FREEZE.md`, and the accepted/ratified ADRs
under `docs/adr/`. Nothing here overrides those. When this file and canonical
sources disagree, canonical sources win and this file is stale.

Last updated: 2026-08-21 14:20 local.

---

## GIT

| Field | Value |
|---|---|
| CURRENT_BASELINE_SHA | `1743a53b585036cc872a409c2820bedf8cc4f316` |
| LATEST_VERIFIED_SHA | `1743a53b585036cc872a409c2820bedf8cc4f316` |
| REMOTE_SHA (origin/main) | `1743a53b585036cc872a409c2820bedf8cc4f316` |
| LOCAL_REMOTE_SYNC | IN SYNC — 0 ahead, 0 behind |
| Branch | `main` |

Baseline matches the SHA named in the convergence brief. No divergence to reconcile.

---

## MISSION_STATUS

Phase: **canonical read → conformance matrix**. No convergence implementation has
begun. No commits made this session yet.

---

## CONFORMANCE_MATRIX_STATUS

**NOT YET BUILT.** This is the first deliverable and blocks implementation.
Target location: `docs/audits/FOUNDER_EDITION_CONFORMANCE_MATRIX.md`.

---

## INHERITED UNCOMMITTED WORK — CLASSIFIED

All of the following was already in the working tree when this session began. It
was inspected, executed and classified before any new work started. **None of it
has been committed, reverted, or deleted.**

### Method

Compared the working tree against a clean worktree at `HEAD` (Engineering Rule
001 — the working directory is never evidence):

| Tree | Result on the 4 modified test files |
|---|---|
| Pristine `HEAD` (detached worktree) | **50 failed, 361 passed** |
| Working tree (inherited edits applied) | **16 failed, 417 passed** |

The inherited test edits therefore **repair 34 failures and add coverage**. They
are not noise.

### T1 — `tests/test_desktop_executive.py`, `test_desktop_shell.py`, `test_founder_edition_assembly.py`, `test_founder_edition_boot.py`

**Classification: coherent uncommitted current slice — PARTIALLY INCOMPLETE.**

These edits catch the *tests* up to source that is **already committed at HEAD**.
Every source API the new tests exercise already exists in the committed tree:

- `master_agent.desktop.inventory.discover(probe, deep=)`, `_claim_match`,
  `_is_raw_path`, `_start_app_launch_target`, `InstalledApplication.install_source`
  / `launch_target` / `discovery_sources`, `Inventory.get_unknown` /
  `unknown_applications` — all present in `src/master_agent/desktop/inventory.py`.
- `SystemProbe.get_start_apps` / `get_store_apps` / `get_uninstall_apps` — present
  in `src/master_agent/desktop/probe.py` (protocol + real + fake impls).
- `DesktopShellApi.get_startup_diagnostics`, `submit_objective=` injection —
  present in `src/master_agent/founder_edition/desktop_shell.py`.
- `VoicePipeline.mic_live` — present in `voice_pipeline.py:349`.

So the source landed in a commit and the test fixtures were left behind. The bulk
of the HEAD failures were a single stale fixture (`FakeProbe` missing
`get_start_apps`) cascading across four files.

**Two of the inherited edits are themselves wrong** (this is the incomplete part):

1. `TestStartupDiagnostics::test_all_true_when_everything_is_wired` asserts a
   6-key dict; the committed source also returns `mic_live`. The same diff *did*
   add `mic_live` to the `_RecordingVoice` fake but did not add it to the expected
   dict.
2. `test_exposes_exactly_the_nine_bridge_methods` (renamed from `..._eight_...`)
   expects 9 bridge methods; committed source exposes **15** — the extras being
   `decide_approval`, `get_execution_status`, `confirm_completion`, `get_mode`,
   `set_mode`, `debug_log`.

**Action taken: none. Left intact.** Do not commit T1 until items 1 and 2 are
corrected against source.

### T2 — `src/master_agent/providers/gemini.py`

**Classification: coherent completed implementation — UNPROVEN (no tests).**

Adds bounded retry on transient HTTP statuses (`429/500/502/503/504`), max 3
attempts, fixed short backoff `(0.6s, 1.4s)`, with `max_attempts` and `sleep`
injected for testability. Timeouts are deliberately *not* retried. Non-transient
outcomes return on the first pass, so the ordinary path is unchanged.

- Architecturally consistent with the brief: retry sits in the **provider**, which
  is its canonical owner. It does **not** put retry in the Broker (§9 forbids
  that). Cites MB033 Rule 4.
- `tests/test_gemini_provider.py` + `test_gemini_broker_integration.py`:
  **30 passed** with this change applied — non-regressive.
- **But there is no test for any of the new behaviour.** The author wrote the
  `sleep` injection seam with a comment saying a test "must not actually sleep",
  then was interrupted before writing that test.

**Action taken: none. Left intact.** Needs a retry-policy test before commit.

### T3 — ~118 untracked paths at repo root and under `VEDRA_PROJECT/`, `docs/audits/`, `Engineering/`

**Classification: unrelated / generated artifacts + Hyperagent UI assets.**

Includes ~25 root-level status files (`TASK_DONE.txt`, `FINAL_SUMMARY.md`,
`TASK_COMPLETE_FINAL.txt`, `OUTPUT_FINAL.txt`, …), a stray pip artifact literally
named `=5.1`, ad-hoc scripts (`add_diagnostics.py`, `adjudicate.py`,
`capture_window.ps1`), Hyperagent UI deliverables under
`VEDRA_PROJECT/01_Assets/UI-UX/`, and audit documents under `docs/audits/` and
`Engineering/`.

Also present but untracked: `.bak` / `.backup` / `.backup2` / `.backup_diag` /
`.backup_before_diag` copies of `catalog.py`, `inventory.py`, `probe.py`,
`desktop_shell.py` inside `src/`. These are **not importable by Python** and do
not affect runtime or build behaviour.

**Action taken: none. Nothing deleted.** Per the brief these are not to be removed
for cleanliness. They do not block source analysis.

---

## COMPLETED_SLICES

None yet this session.

---

## CURRENT_SLICE

**Objective:** Read canonical sources in authority order, then build the
source-reconciled Founder Edition conformance matrix.

**Canonical source:** `docs/architecture/KALPAVRIKSHA_VISION_V2.md`,
`docs/architecture/FOUNDER_CONSTITUTION_FREEZE.md`, `docs/adr/*.md`.

**ADR ratification status recorded (matters — Proposed ADRs are design evidence
only, never binding):**

- Accepted/ratified: 0001–0022.
- **0023 kernel-minting-decisions — PROPOSED.**
- **0024 intent-resolution-clarification-and-planner-admission — PROPOSED**
  (2026-08-14). Directly governs the §11/§12 Intent work. Must be treated as
  design evidence, not as a binding contract.
- **0025 founder-interaction-audit-trail — PROPOSED** (2026-08-15).

**State:** Git truth established, inherited work classified, ledger created.
Canonical read not yet started.

---

## NEXT_EXACT_ACTION

Read `docs/architecture/KALPAVRIKSHA_VISION_V2.md` and
`docs/architecture/FOUNDER_CONSTITUTION_FREEZE.md` in full, then the accepted
ADRs, then reconcile against current source to produce
`docs/audits/FOUNDER_EDITION_CONFORMANCE_MATRIX.md`.

---

## KNOWN_BLOCKERS

None yet.

**Observation, not a blocker:** the backend suite is broadly red independent of
this mission. 16 failures remain on the four inherited test files even with the
inherited edits applied, and all 16 inspected so far are **stale tests lagging
committed source**, not source defects — e.g. `test_..._registers_twelve_capabilities`
asserts 12 where source registers 19; `test_no_automation_capability_exists`
forbids `click` where source now deliberately ships `desktop_click` /
`desktop_type_text` / `desktop_press_key`; `test_bringing_to_front_reports_that_it_is_not_built`
expects a "not built" stub where source now really implements it. One
(`test_launching_starts_the_resolved_path`) waits 30 real seconds on the live
machine. Treat old "missing" claims about the Desktop Executive with suspicion —
source is ahead of both its tests and the audit documents.

---

## FOUNDER_DECISIONS_REQUIRED

None yet.

---

## HYPERAGENT_UI_WORK_REQUIRED

None recorded yet.

---

## LIVE_ACCEPTANCE_STATUS

| Proof | Status |
|---|---|
| A. Intent / conversation regressions (§12) | NOT RUN |
| B. Medium golden mission | NOT RUN |
| C. Founder checkpoint | NOT RUN |
| D. Permission | NOT RUN |
| E. Persistence / recovery | NOT RUN |
| F. Real intelligence route | NOT RUN |

---

## UNCOMMITTED_WORK_STATUS

- `src/master_agent/providers/gemini.py` — T2 above. Coherent, non-regressive,
  untested. Intact.
- `tests/test_desktop_executive.py`, `tests/test_desktop_shell.py`,
  `tests/test_founder_edition_assembly.py`, `tests/test_founder_edition_boot.py` —
  T1 above. Net +34 repaired failures, two known-wrong assertions. Intact.
- ~118 untracked paths — T3 above. Untouched.
- `docs/CONVERGENCE_HANDOFF.md` — this file, new, uncommitted.

**Nothing has been discarded.**

---

## RUNNING PROCESSES / ENVIRONMENT NOTES

- A git worktree for baseline comparison exists at
  `C:\Users\DELL\AppData\Local\Temp\claude\D--MasterAgent\34a1e1b1-bd54-4720-9e2a-19b09325bb0f\scratchpad\wt-head`
  (detached at `1743a53`). Remove with `git worktree remove` when done; it is
  disposable and outside the repo.
- Tests require `PYTHONPATH=src`. There is no pytest config in `pyproject.toml`,
  so a bare `pytest` run will not resolve imports.
- Python 3.14.5.
- The four-file test run takes ~4 minutes; the full suite is slower. Prefer
  targeted `-k` runs during implementation.
