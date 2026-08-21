# CONVERGENCE HANDOFF — Kalpavriksha Founder Edition

**This file is a resumability ledger, not architecture and not a second source of
truth.** Canonical truth lives in `docs/architecture/KALPAVRIKSHA_VISION_V2.md`,
`docs/architecture/FOUNDER_CONSTITUTION_FREEZE.md`, and the accepted/ratified ADRs
under `docs/adr/`. Nothing here overrides those. When this file and canonical
sources disagree, canonical sources win and this file is stale.

Last updated: 2026-08-21 17:05 local.

---

## GIT

| Field | Value |
|---|---|
| CURRENT_BASELINE_SHA | `1743a53b585036cc872a409c2820bedf8cc4f316` |
| LATEST_VERIFIED_SHA | see COMPLETED_SLICES — latest is Slice 1 |
| REMOTE_SHA (origin/main) | verified equal at each checkpoint |
| LOCAL_REMOTE_SYNC | IN SYNC after every checkpoint below |
| Branch | `main` |

Baseline matches the SHA named in the convergence brief. No divergence to reconcile.

---

## MISSION_STATUS

Phase: **convergence implementation, in dependency order.** Canonical read done,
matrix built and source-reconciled twice, Slice 1 landed.

---

## CONFORMANCE_MATRIX_STATUS

**BUILT and reconciled against source twice** —
`docs/audits/FOUNDER_EDITION_CONFORMANCE_MATRIX.md` (commit `01dda78`).

25 responsibilities classified. Not COMPLIANT_AND_WIRED: 1 SPECIFIED_BUT_MISSING
(utterance roles — now closed by Slice 1), 1 IMPLEMENTATION_DRIFT (Intent has no
reasoning door), 1 BUILT_BUT_UNWIRED (provider retry, uncommitted), 3
DELIBERATELY_FUTURE. **No FOUNDER_DECISION_REQUIRED rows.**

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

### Slice 0 — ledger + matrix (`c56b9d1`, `01dda78`)

Git truth, inherited-work classification, conformance matrix. No source touched.

### Slice 1 — utterance roles: a pending question is context, not ownership

- **Canonical requirement:** convergence brief §11 CRITICAL INVARIANT and the six
  §12 regressions; Constitution §3.1 (Intent Layer owns clarification).
- **Source changed:**
  - `src/master_agent/brain/utterance.py` — **new.** `UtteranceRole` (6 members),
    `role_of()`, plus `clauses()`/`opens_an_instruction()`.
  - `kalpavriksha_desktop.py` — `_submit_objective()` now asks the Brain for the
    utterance's role *before* acting, and handles `CANCEL_OR_STOP`, `FOLLOW_UP`
    and `MODIFY_OR_REDIRECT` instead of routing everything into `clarify()`.
  - `tests/test_clarification_round_trip.py` — one test inverted (see below).
- **Tests:** `tests/test_utterance_role.py` (44, new),
  `tests/test_founder_intent_regressions.py` (14, new).
- **Regression proof:** the failure set for
  `-k "intent or clarif or brain or conversation or founder_chief or capability_self"`
  is **byte-identical** to the same selection at clean HEAD (20 failures both
  sides, `comm` diff empty in both directions), with **+22 newly passing**. Zero
  regressions introduced.
- **Live proof status:** unit + composition-root proven. **Not yet live-proven in
  the running desktop app** (Live Acceptance A).

**One inherited test was deliberately inverted.**
`test_an_unrelated_escalated_message_IS_taken_as_the_answer` asserted the old
defect as intended behaviour and its own docstring nominated itself as the place
the decision would be revisited if it ever became wrong for the founder. §11
revisited it. It is now
`test_an_unrelated_escalated_question_is_NOT_taken_as_the_answer`.

**One thing tried and correctly abandoned:** sharing `opens_an_instruction`
between `brain/utterance.py` and `conversation_engine/intent.py`.
`tests/test_conversation_engine.py::TestBoundaries` walks that package's imports
by AST and allows only four `master_agent` roots — the Conversation Engine may not
import the Brain. The edit was reverted, the duplication kept, and it is named in
`brain/utterance.py`'s docstring rather than hidden.

---

### Slice 2 — provider retry proven (`fd707cc`)

Inherited `gemini.py` retry committed with 18 new tests using its author's own
`sleep` seam. Retry stays in the provider; the Broker still retries nothing.

**Found while proving it:** the inherited work also included an untracked test file
`tests/test_launch_rescue_provider_hygiene.py` (it imports `DEFAULT_MAX_ATTEMPTS`),
so T2 did have tests — just untracked. 22 of its 23 pass. The one failure
(`test_a_successful_mission_reply_is_unchanged_by_the_hygiene_layer`) was verified
to fail **identically at pristine `1743a53`**, so it is pre-existing and is about
the Reporter/`_mission_report` path, not retry. **Left untracked and uncommitted** —
committing someone else's untracked test with a known red is a separate decision.
It needs triage.

### Slice 3 — inherited test fixtures caught up (`a1a0a86`)

50 failures at HEAD → 13. `test_desktop_shell.py` fully green. Three inherited
assertions corrected against source (7-key diagnostics, 15 bridge methods,
`?debug=1`), plus the same stale "nine" in `desktop_shell.py`'s docstring.

### Slice 4 — the Intent Layer's reasoning door (matrix Row 4)

- **Canonical requirement:** Vision §3.3 — the Model Router is *"the Brain's single
  door to reasoning"*; ADR-0024 D7 states normatively that this covers every Brain
  reasoning call, not only the Planner's.
- **Source changed:** `brain/utterance.py` gains `structural_role()` returning
  `(role, confident)`; `brain/intent.py` gains `IntentLayer(reasoner=...)` and
  `decide_role()`; `kalpavriksha_desktop.py` passes the **same `tiered_runner` the
  Planner uses** and calls `mission_service.intent_layer.decide_role(...)`.
- **The door opens for exactly one shape:** a longer statement arriving while a
  question is open — neither question, instruction, offered option, nor short
  enough (≤4 words) to read as a value. Everything else is settled by structure at
  no cost, so the ordinary answer ("Research") pays nothing.
- **Tests:** `tests/test_intent_reasoning_door.py` (26). Zero new failures vs
  `5fd8abd` (21 both sides, `comm` empty both directions).
- **Live proof status:** the routed seam is proven with a spy. **A real provider
  call through this door has NOT been made** — it fires only on the ambiguous
  shape, and firing it deliberately would be a synthetic probe (§32).

---

### Slice 5 — the founder could not approve anything

**A real, live, founder-facing crash, found while preparing Live Acceptance D.**

`decide_approval` was a closure defined inside `main()`. `permissions` and
`GrantScope` are **not in scope there** — both are local to
`_build_mission_pipeline()`. Python compiled them as global lookups; neither name
exists at module level. **The first time a founder pressed Approve in the packaged
app, the bridge raised `NameError` instead of granting anything.**

Confirmed three ways before touching it: AST scope analysis, `dis` on the compiled
closure (`co_names` carries `permissions`/`GrantScope` as globals, `co_freevars`
carries only `mission_control`), and the new guard failing on the pre-fix commit
with exactly `decide_approval() -> GrantScope, decide_approval() -> permissions`.

Nothing caught it because every approval test either injected a fake
`decide_approval` or asserted only that `create_window` *received* one. The closure
was unreachable without running `main()`, which opens a real window.

- **Fix:** `decide_approval` moved into `_build_mission_pipeline()`, beside the
  `PermissionSystem` it grants through — the same shape as `_set_mode`, which was
  already defined and returned there. Returned as the tuple's 8th element.
- **Tests:** `tests/test_founder_approval_path.py` — a specific test that calls the
  **real** `decide_approval`, and a general guard that walks every code object in
  the module and asserts every `LOAD_GLOBAL` resolves. **The guard was verified to
  fail on the pre-fix commit**, which is the only thing that makes it worth having.
- Five test unpackings updated for the 8-tuple. Zero new failures (20 = 20).

**This is why §30 says unit tests are not enough.** Everything about approval was
green; the one path a founder actually takes was a crash.

---

## CURRENT_SLICE

**Objective:** none in flight. Next candidate is the stale
`test_intent_layer_boundary.py::TestClarificationResolution::test_the_resolution_loop_has_no_production_caller_yet`,
which asserts by `git grep` that `IntentLayer.clarify()` has no production caller.
It has had one since before this session (`kalpavriksha_desktop.py`), so the test
now asserts an absence that has been closed — the same staleness ADR-0024 Gap 1
carries. Pre-existing failure, not caused by this session.

**Canonical source:** Vision §3.3 (Model Router is the Brain's single reasoning
door) and ADR-0024 Decision 7, which is normative on exactly this point: *every*
reasoning call the Brain makes goes through the Model Router, whatever it is
reasoning about — not only the Planner's. ADR-0024 is **PROPOSED**, so it is design
evidence; the binding requirement is Vision §3.3, which says the same thing.

**ADR ratification status recorded (matters — Proposed ADRs are design evidence
only, never binding):**

- Accepted/ratified: 0001–0022.
- **0023 kernel-minting-decisions — PROPOSED.**
- **0024 intent-resolution-clarification-and-planner-admission — PROPOSED**
  (2026-08-14). Directly governs the §11/§12 Intent work. Must be treated as
  design evidence, not as a binding contract.
- **0025 founder-interaction-audit-trail — PROPOSED** (2026-08-15).

**State:** not started. Slice 1 established the seam it will use — `role_of()` is
the first place a Brain-side reasoning call becomes worth making, because it is
where a wrong answer currently costs the founder most.

---

## NEXT_EXACT_ACTION

Give `IntentLayer` a Model-Router-backed path for the residual case where
`role_of()`'s structural signals cannot decide, keeping deterministic parsing in
front of it so the ordinary path neither slows down nor starts costing tokens.
`brain/advisory.py` already shows the in-repo shape of a Brain component making a
routed call (`RoutingContext`, `SelectionRequest`, `BudgetedSelectionRequest`,
workload `INTERACTIVE`) — reuse that seam, do not invent a second one.

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
| A. Intent / conversation regressions (§12) | **LIVE_PROVEN through the real assembled surface** — `tests/test_live_acceptance_intent.py`, 9 passed. Enters at `DesktopShellApi.send_message()` on an app built by the real `boot_founder_edition()` (real Identity, ConversationEngine, CommunicationEngine, `IntentLayer`). **Planner deliberately spied** — `GEMINI_API_KEY` is set on this machine and a real call would spend founder quota and launch a browser on a synthetic probe (§32). For five of the six exchanges the required behaviour *is* that the Planner is never reached, which a spy proves better than a live call. Not yet clicked through the packaged .exe. |
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
