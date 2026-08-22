# CONVERGENCE HANDOFF — Kalpavriksha Founder Edition

**This file is a resumability ledger, not architecture and not a second source of
truth.** Canonical truth lives in `docs/architecture/KALPAVRIKSHA_VISION_V2.md`,
`docs/architecture/FOUNDER_CONSTITUTION_FREEZE.md`, and the accepted/ratified ADRs
under `docs/adr/`. Nothing here overrides those. When this file and canonical
sources disagree, canonical sources win and this file is stale.

Last updated: 2026-08-21, end of session.

---

## SUCCEEDED BY A LATER SWEEP — read that too

A follow-on mission (**`docs/audits/CAPABILITY_WIRING_AND_LIVE_PROOF.md`**) asked a
different question of the same system: not *"is it built"* but *"can the Runtime
actually reach it"*. It found and fixed one real defect this ledger did not:

**`Document` and `Reasoning` were registered, Planner-visible and
permission-granted — with no gateway.** The Runtime does not fall back; it fails the
task. Three capabilities could be planned and approved and could never run.

That lands directly on Slice 9 below. Slice 9 added `document` and `reasoning` to
the founder-facing capability answer, so Kalpavriksha began telling the founder it
could do two things that would have failed. **The answer was right; the wiring was
not.** Both are now wired and live-proven — a real 35 KB `.docx`, and a real model
reply through the Model Router.

That sweep also corrects two things recorded here: Reasoning's earlier refusal was
the **privacy boundary working**, not a provider defect, and the Desktop
verification surface is **four** capabilities, not the five a comment claimed.

**Evidence wording, stated precisely.** Document and Reasoning are **runtime-reachable
and live-execution-proven**. They are **not** independently verified: both run through
the generic `PluginGateway`, whose `verify()` returns `None`, so **no canonical
Verification Evidence is produced** for either. That is a fact about the current
wiring, recorded as a distinction — not a judgement that they need verifiers, and not
authorisation to build any.

**Live Acceptance C — attempted once at `da9f8f9`, NOT EXECUTED.** Both runs refused
at the Planner with HTTP 429 (`limit: 20, model: gemini-3.6-flash`; retry-after
33.3 s and 30.7 s). The checkpoint was never reached, so the run's own
*"nothing was written"* / *"Stop did not execute the mutation"* lines are **vacuous**
and are not evidence. Verdict: **EXTERNAL BLOCKER**, not FAIL — nothing about the
checkpoint was disproven, and its mechanism stays proven without quota by
`c2_checkpoint_mechanism.py`.

---

## READ THIS FIRST — what happened in one page

**Three real founder-facing defects were found and fixed. None was caught by the
test suite. All three surfaced by attempting live acceptance rather than by reading
code.**

1. **The founder could not approve anything.** `decide_approval` read `permissions`
   and `GrantScope` as module globals that do not exist — the first press of
   Approve raised `NameError`. Every approval test either injected a fake or
   asserted only that the bridge *received* one.
2. **Approving did not resume the work.** Nothing drove the Runtime after the
   founder decided, so an authorised task waited forever. Proven by approving and
   then simply waiting: the file the founder had just authorised deleting was still
   there.
3. **A pending clarification owned the founder's next utterance.** Asked *"Which
   file should I read?"*, a founder answering *"nothing thanks"* had that taken as
   a filename and was asked again, with no way out of the loop.

**Live acceptance: A, B, C(mechanism), D, E, F all pass.** The Medium Golden
Mission ran for real — Gemini planned it, a real browser observed
`https://example.com/`, six steps verified independently, and a real file landed on
the Desktop containing the observed title and final URL.

**One thing is genuinely blocked** (Gemini free tier, 20/day, spent on B and D) and
**two need the founder's decision** (FD1: what status follows Stop — already
ADR-0021's own open item; FD2: delete the untracked rogue provider client).

**Full suite: 119 → 95 failures, 7691 → 7715 passing.** And 63 of the 95 that
remain are classified as out-of-scope, superseded, or intentional — see THE FAILING
SUITE, CLASSIFIED before treating the raw number as debt. The four inherited test
files went from **50 failures to 0**.

---

## GIT

| Field | Value |
|---|---|
| CURRENT_BASELINE_SHA | `1743a53b585036cc872a409c2820bedf8cc4f316` |
| LATEST_VERIFIED_SHA | `3366eadb863a7b2b79f4cb00fa54e54e54e934ef` — **the parent of the commit that writes this line.** A file cannot record its own SHA; `git rev-parse HEAD` is authoritative. |
| REMOTE_SHA (origin/main) | equal to LOCAL, verified after every push |
| LOCAL_REMOTE_SYNC | **IN SYNC — 0 ahead, 0 behind**, verified after every one of the ~39 commits |
| Branch | `main` |
| Commits this session | **~39** (`git rev-list --count 1743a53..HEAD` is exact) |
| Tracked working tree | **clean** |

Baseline matched the SHA named in the convergence brief. No divergence at any point,
no force-push, no history rewritten, nothing discarded.

---

## MISSION_STATUS

Phase: **convergence implementation complete for this session.** Canonical read
done, matrix built and source-reconciled twice, eight slices landed, six live
acceptances run.

**Not finished, and honestly so:** Live Acceptance C end-to-end is blocked on
provider quota, two founder decisions are open, and one untracked file keeps an
architecture guard red. See NEXT_EXACT_ACTION.

---

## CONFORMANCE_MATRIX_STATUS

**BUILT and reconciled against source twice** —
`docs/audits/FOUNDER_EDITION_CONFORMANCE_MATRIX.md` (commit `01dda78`).

**31 responsibilities** classified, and the matrix was itself corrected once during
the session (Row 21 conflated persistence-recording with resume-after-restart).

Still open after this session: **1 IMPLEMENTATION_DRIFT** (Row 30 — the untracked
rogue provider client), **3 DELIBERATELY_FUTURE**, and **2 FOUNDER_DECISIONS**
(FD1, FD2 below). Everything else is COMPLIANT_AND_WIRED, including three rows that
were actively broken when the session began.

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

**RESOLVED (Slice 3, commit `a1a0a86`).** Both wrong assertions were corrected
against source, plus a third found afterwards (`create_window` asserted a bare page
URL while passing `debug=True`). 50 failures at HEAD → 13. `test_desktop_shell.py`
went fully green, and the rest followed in Slice 8. **Committed, not discarded.**

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

**RESOLVED (Slice 2, commit `fd707cc`).** 18 tests written using the author's own
`sleep` seam — every transient status retried and recovering, the cap holding at
three attempts total, the documented delays asserted as values, and the larger
negative half: no retry on a non-429 4xx, on a malformed body, or on a timeout.
**Committed.**

**Found while proving it:** an untracked companion test file
`tests/test_launch_rescue_provider_hygiene.py` (it imports `DEFAULT_MAX_ATTEMPTS`),
so T2 *did* have tests — just untracked. 22 of its 23 pass; the one failure was
verified to fail identically at pristine `1743a53`, so it is pre-existing and
concerns the Reporter path, not retry. Left untracked and uncommitted.

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

### Slice 6 — the founder approved and nothing happened

**The second real founder-facing defect, and Live Acceptance D is what found it.**

`_submit_objective` was the only thing in the process that ever called
`runtime.run_once()`, and it returns long before the founder decides. So:
founder asks for an irreversible action → gate holds → founder presses Approve →
grant recorded, approval marked approved → **nothing ever resumes the work.** The
mission sits at `awaiting_approval` forever.

Proven live before fixing: approve, then wait ten seconds with nobody turning the
crank — the file the founder had just authorised deleting was still there.
*"STUCK -- approval does not resume execution."*

- **Fix:** the runtime loop is extracted to `_drive_until_settled()` — one driver,
  not two — and `decide_approval` calls it after granting, then refreshes the
  founder-facing sentence through the existing Reporter.
- **A second bug inside the first:** the loop's break condition read
  `status.status in (AWAITING_APPROVAL, ...)`. That is a *label*, updated by a
  later event, and it still reads `awaiting_approval` immediately after a founder
  answers — so a resume loop would have broken on its first pass, before the
  newly-authorised work ran. It now reads `status.approval_id`, which is the
  authoritative "a question is open" fact and is cleared by `APPROVAL_GRANTED`.
- **Also fixed by this:** the founder used to be left with the stale sentence
  *"This needs your approval before I go ahead."* on a mission that had since
  completed. It now reads *"Work finished. All 1 executed step(s) were
  independently verified."*
- **Tests:** 5 added to `tests/test_founder_approval_path.py`. Zero regressions
  (11 = 11, with untracked test files synced into the baseline worktree — see
  the note below).

**Method note for future sessions:** comparing failure sets against a clean
worktree produces *spurious* "new failures" for **untracked** test files, which
simply do not exist in the worktree. `tests/test_fire_and_forget_contract.py`,
`tests/test_launch_rescue_provider_hygiene.py` and one other are untracked, and
the first contains four tests whose own docstrings say **"CHARACTERIZATION —
expected to FAIL today."** Always `cp` the untracked test files into the worktree
before trusting a comparison.

### Slice 7 — the founder-facing surface stops holding doors it should not

Three separate breaches of two architecture guards, closed:

- **`planner.modes` import removed** from `desktop_shell.py`. It put the
  founder-facing package inside the Mission OS namespace `TestOnlyComposition`
  forbids, to read two constants the composition root already owned. Mode is now
  injected and the root returns what it resolved, so there is one normalisation in
  the process.
- **`STEP_NAMES` corrected.** The package published a boot order that contradicted
  its own sequence — three tests across three files were right and the constant was
  wrong. Step 5 constructs `FounderRuntime(..., conversation=...)`, so conversation
  cannot follow it.
- **The vendored pywebview server moved to the composition root** (~170 lines,
  three classes). This is what made `os` and `socket` appear inside a package
  guarded against exactly those. Verified live afterwards by
  `scripts/live_acceptance/f_vendored_server.py` — it really serves `index.html` on
  `/`, which is the pywebview 6.x bug the class exists to fix, and which the unit
  tests could never have caught because they install a fake webview.

### Slice 8 — stale tests reconciled to decisions that had already been made

None of these were cosmetic; each was a test asserting a superseded architecture.

- **Desktop Executive (5).** MB030's Deliverable 7 held click/type/keyboard
  deliberately absent *and named its own successor*. That brief landed. Twelve
  capabilities became nineteen, and the automation ban now asserts both halves —
  interaction present, perception (OCR/vision/screenshot) still absent — because
  the old single loop could only be deleted wholesale, taking the perception ban
  with it.
- **The reasoning ladder (3).** Tests asserted cloud-before-desktop, which the
  baseline commit had already reconciled to ADR-0017's cheapest-first order. §9 says
  preserve that reconciliation, so the tests moved, not the source. The CRITICAL
  test is renamed for the property it protects rather than for Gemini.
- **Two clock-dependent console tests** that passed only before noon.
- **`Notepad` had no recovery plan** — a real source gap, not a stale test: the
  catalog knew an application the Executive could not recover. Written.
- Capability counts, `?debug=1`, greeting wording, boot-step positions.

### Slice 9 — the founder was never told about two of their own executives

Asking *"what can you do"* answered with **three** domains while **five** executives
were wired. `document` and `reasoning` were registered, planned against and
executable, but absent from `_EXECUTIVE_DOMAINS`, so they were silently dropped
from the answer.

Omission is the correct default there and the docstring says why — inventing words
for an executive is worse than leaving it out. These two were not missing
descriptions, only missing entries. Added at founder level (*"reading what is inside
a PDF or Word file"*), never as execution verbs, which is the whole reason that map
exists. Both `test_capability_self_knowledge` failures were right and now pass.

### Remaining unclassified failures — ~9, triaged by area

After the classification above, these are what is left. None is in the canonical
loop; several point at the excluded launcher.

| Test | What it says | Note |
|---|---|---|
| `test_broker_wiring.py` (2) | cloud providers on before enabling; providers available before scan | Same area as the Broker lead. **Not env-driven** — verified with `GEMINI_API_KEY` cleared |
| `test_broker_integration.py` (1) | the Desktop Executive still decides nothing | Broker area; triage with the above |
| `test_provider_execution.py` (2) | a real answer vs a model's prose; `rejected` vs `succeeded` | Provider execution |
| `test_founder_dashboard_v2.py` (1) | *"browser is not wired by the launcher yet"* | **launcher** — excluded component |
| `test_founder_approval_workflow.py` (1) | *"no planner is wired"* vs `unknown command 'aprove'` | **launcher** console |
| `test_capability_registry.py` (1) | the prompt shows the signature, not only the description | Planner prompt shape |
| `test_filesystem_plugin.py` (1) | manifest capabilities carry output schema from contracts | Contract plumbing |

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

In priority order. The first two need no quota; the third needs the daily Gemini
free tier to have reset.

1. **Move `FixedBottleServer` out of `founder_edition/desktop_shell.py` into
   `kalpavriksha_desktop.py`** (blocker B0b). This is the clearest remaining piece
   of tracked drift: it is what makes `os` and `socket` appear inside a package
   architecture-guarded against exactly those, and the guard's own comment names
   `socket` as one of the three things it exists to keep out. The seam already
   exists — `create_window()` passes the class to `webview.start(server=...)`, and
   a test already asserts that. **Verify by launching the app in dev mode**
   (`python kalpavriksha_desktop.py`) and confirming the window renders, not by
   unit tests alone: they use a fake webview and would not catch a real pywebview
   integration break. Deliberately not attempted at the end of a session because a
   packaged rebuild could not be safely verified.
2. **Decide on `founder_edition/ai_client.py`** (blocker B0a) — recommended
   deletion. Founder's call; it is untracked, so git holds no copy.
3. **Run `scripts/live_acceptance/c_founder_checkpoint.py`** once the Gemini free
   tier resets, to close the one Live Acceptance still blocked (C end-to-end, the
   Planner actually marking a checkpoint from the founder's own sentence). The
   mechanism below it is already proven by `c2_checkpoint_mechanism.py`.

**Do not** treat the 43 `FounderConsole` failures as convergence work — see THE
FAILING SUITE, CLASSIFIED. They belong to a component this product excludes.

---

## THE FAILING SUITE, CLASSIFIED

A bare failure count is not information. The pre-existing red was triaged by cause,
because "119 failures" and "43 of them are one unbuilt feature in a component
Founder Edition does not ship" are very different facts.

**Final measurement: 95 failed, 7715 passed, 2 skipped** (complete list captured, not
a truncated tail — see the method note). Session start was **119 failed, 7691
passed**.

| Cause | Files | Count | Verdict |
|---|---|---|---|
| `FounderConsole` has no `memory=` parameter and no `replay`/`remember` commands | `test_missions_console.py`, `test_memory_integration.py` | **43** | Unbuilt feature in an **excluded** component |
| `_submit_objective()` no longer takes `reasoning_runner` | `test_brain_non_execution_routing.py` | **15** | Tests for a **deliberately removed** path |
| `cli.py` still constructs `MissionPlan`/`Step` | `test_missions_architecture.py` | **5** | Real: MB037's cleanup never landed. Out of Founder Edition scope |
| Broker selects cloud over an installed local provider | `test_verified_execution.py` | **4** | **Lead — see above** |
| Ollama provider | `test_ollama_provider.py` | **4** | Policy-banned component |
| Untracked `ai_client.py` keeps `os` in the package | `test_founder_edition_boot.py` | **1** | **Blocker B0a — one decision away** |
| Characterization tests, docstrings say *expected to FAIL today* | `test_fire_and_forget_contract.py` | **3** | Intentional |
| Everything else | assorted | 23 | Untriaged |

**63 of 98 (64%) are explained above as out-of-scope, superseded, or intentional.**
That is the number worth carrying forward, not the raw 95.

### The 15 — tests for a path that was deliberately removed

Every one fails with `_submit_objective() got an unexpected keyword argument
'reasoning_runner'`. That parameter existed to pass a runner to
`brain/advisory.py::advise()`, and the composition root records why it went, in
detail:

> *"This used to ask `brain/advisory.py::advise()` what to say and then record the
> turn as COMPLETED. Both halves were wrong, and the live CV mission showed exactly
> how wrong: the founder was told 'I am taking full responsibility for evaluating
> all your resume files… Shall I start cataloging those files now?' over a mission
> that had no plan, no tasks, and nothing waiting on an answer."*

So this is a deliberate quality fix, and 15 tests still assert the behaviour it
removed. **Not touched here:** deleting or rewriting 15 tests is a decision about
whether the advisory path should return in some form, which belongs to whoever
owns that call — not to a convergence pass.

### A fifth — the ladder's tier is named after a product, not after its rung

`test_broker_integration.py::test_only_the_catalogue_names_a_provider[gemini]` fails
with *"'gemini' appears in tiered_runner.py"*, and it is right.

`ai_infrastructure/tiered_runner.py:62` declares `TIER_GEMINI = "gemini"`, with a
matching `gemini_provider_ids` constructor argument threaded through the
composition root. **ADR-0017 Decision 3 has no rung called "gemini".** Its six are
`local · desktop app · free cloud · free aggregator · existing subscription · paid
API`. The rung this tier implements is **free cloud**; Gemini is merely who
currently fills it.

The baseline commit reconciled the ladder's **order** to ADR-0017 and said so at
`tiered_runner.py:115` — *"This read `gemini -> desktop -> browser -> local` until
now"* — but left the tier **named** after the product that happened to occupy it.
So the ordering drift was fixed and the naming drift was not, and a guard that
exists to keep provider names in the catalogue has been reporting it since.

This matters beyond tidiness: a tier named for its occupant invites the next
provider swap to be a rename across three files instead of a catalogue entry, which
is the coupling §14 and Rule 3 exist to prevent.

**Fix, not applied:** rename `TIER_GEMINI` → `TIER_FREE_CLOUD` and
`gemini_provider_ids` → `free_cloud_provider_ids`, in `tiered_runner.py` and at its
one call site in `kalpavriksha_desktop.py`. Mechanical, and it touches the reasoning
ladder — the component that decides where every founder request goes — so it wants a
deliberate run of the ladder suite plus Acceptance B behind it, not an end-of-session
rename. Two of the remaining `test_broker_wiring.py` failures sit in the same area
and should be triaged with it.

**Not this session's doing:** `git diff 1743a53..HEAD` touches neither
`tiered_runner.py`, `broker/`, nor `ai_infrastructure/`.

### A third and fourth, from the last 18 — both Constitution-level, both pre-existing

Neither file involved was touched this session (`git diff 1743a53..HEAD` confirms).

#### `chrome` in Browser source vs MB022's categorical product-name ban

`test_browser_constitution_compliance.py` fails on two files. Its own docstring
cites *"Mission Brief 022's explicit 'if a product name appears anywhere… treat it
as an architectural violation' rule"*, and the matches are real:
`environment/browser_session.py` and `executor/actions/browser/open_session.py`.

**But look at what the matches are.** Both are Playwright's own `channel`
parameter — its first-class API value meaning *"drive a browser already installed
on this machine rather than the bundled build"* — plus the founder-facing
description of that argument. The source already confines it deliberately:
*"It stays confined to this one function for exactly the reason above."*

**And a later Founder requirement makes it necessary.** *"Open Chrome"* must drive
the founder's installed, **visible** Chrome rather than a bundled headless
renderer — recorded in tracked source at
`Engineering/REPORT_FIRST_VISIBLE_MEDIUM_SUCCESS.md` and
`docs/audits/DESKTOP_EXECUTIVE_FOUNDATION_1.md`. Playwright's `channel="chrome"`
is the mechanism that satisfies it. Remove the string and the requirement breaks.

**Convergence brief §2 resolves this on its face:** explicit later Founder
decisions rank *above* Mission Briefs. So the later visible-Chrome requirement
supersedes MB022's categorical ban for this one parameter value, and the guard's
regex — which cannot tell a branded product in core prose from an API argument in a
Worker — is what has drifted.

**Not changed here, deliberately.** Editing a Constitution-compliance guard is
exactly the kind of change that should be made in daylight with the reasoning
visible, not at the end of a session. The argument is written out above so the
decision takes a minute rather than a re-investigation. **Recommended:** exempt
Playwright's `channel` value specifically — not the whole file, and not the whole
name list.

#### `datetime.now()` read outside the clock module

`test_foundation_clock.py::test_only_the_clock_module_reads_the_machines_wall_clock`
names several `ai_infrastructure/` modules reading ambient wall-clock time directly
(`cache.py:71`, `execution.py:178`, `executive/actions.py:162`, and more).

That guard exists so time is injectable and therefore testable — the same seam
`clock`, `sleep` and `transport` already are elsewhere in this codebase, and the
same discipline that let the provider-retry tests run without waiting. Pre-existing
drift; genuine; not in the canonical loop; recorded for triage.

### A second lead, and this one touches Rule 2 — frozen components edited without an ADR

`test_dashboard_architecture.py::test_no_frozen_component_was_modified_without_a_ratified_adr`
fails, naming seven files:

```
src/master_agent/executor/action.py
src/master_agent/executor/actions/browser/observe.py
src/master_agent/executor/actions/browser/open_session.py
src/master_agent/executor/actions/browser/read_page_text.py
src/master_agent/executor/actions/create_folder.py
src/master_agent/executor/actions/document/__init__.py
src/master_agent/executor/actions/document/extract_text.py
```

**None of them was touched this session** — verified against
`git diff --name-only 1743a53..HEAD`, which has zero overlap with that list. This
is pre-existing.

It matters because it is not a stale-count or renamed-symbol failure; it is a guard
reporting that **frozen components changed without the ratified ADR the amendment
process requires** (Constitution Rule 2, and §4a's *"a structural amendment is
proposed by a Mission Brief and applied only after founder ratification"*).

**A second guard reports the same thing independently:**
`test_mit_001_browser_integration.py::test_7_browser_executive_source_is_untouched_since_mission_brief_022`
— *"the Browser Executive was modified since MB022"*. Two guards, written for
different missions, both saying frozen source moved. That agreement is what makes
this worth a human rather than a shrug.

Everything else in both files is now green: the surrounding failures were the
`read_page_text` capability arriving (nine → ten), which is *itself* one of the
modifications the guards are objecting to. **The count was updated; the question of
whether the capability should have been added without an ADR is left open, because
that is the actual question.**

Either those edits were legitimate and an ADR was never written, or the guards'
notion of "frozen" has drifted from what the Constitution freezes. **Both readings
need a human**, and neither is a convergence action — writing an ADR to retrofit
approval for edits already made would be exactly the silent amendment §4a exists to
prevent.

### A lead worth someone's attention — `test_verified_execution.py` (4)

Not chased, because it is Broker-internal and could not be validated live with the
quota spent. **Pre-existing** — nothing this session touched `broker/` or `policy.py`.

The harness builds a system with an installed local provider (`InstalledProbe
("ollama")`) and fakes *that* provider's transport. The Broker nevertheless selects
**`gemini.api`**, so the fake is never reached and the test fails.

Two things about that are worth a look, and they are separable:

1. **Cloud selected over an installed local provider.** ADR-0017 Decision 3 walks
   local first. If the harness's policy legitimately differs, the tests are stale;
   if it does not, this is the same drift class the baseline commit fixed in the
   runner, one layer down in the Broker.
2. **A provider with no credentials was still selected.** With `GEMINI_API_KEY`
   cleared the same selection happens and fails with *"no GEMINI_API_KEY
   configured"*. Vision §3.3 Amendment 2 is explicit that a preference *"can never
   select a Provider that is unavailable, licence-barred, privacy-barred, or
   paid-without-approval"* — an unconfigured provider surviving the hard-constraint
   filter is worth confirming against `broker/decision.py`.

Neither is a Founder Edition blocker: the shipped composition pins its own ladder
and B/D/F all passed live through it. Recorded so it is triaged rather than
rediscovered.

### The 43 — one unbuilt feature, in an excluded component

`master_agent.launcher.console.FounderConsole.__init__()` takes no `memory`
argument, and the module contains no `replay` or `remember` command. `git log -S`
shows **`replay` was never there** — these are tests written against a feature that
was never built, not a regression that removed one.

And the component is **explicitly excluded from the Founder Edition build**:

```
packaging/kalpavriksha.spec:128
excludes=['master_agent.launcher', 'master_agent.dashboard'],
```

So this whole cluster is **SPECIFIED_BUT_MISSING for the CLI launcher and out of
scope for this mission**. Building it would be building the future (§20) on the
strength of tests that describe an intention. Recorded here so the next session
does not spend an afternoon rediscovering that 36% of the red belongs to something
Founder Edition does not ship.

**Recommended:** these tests should be marked `xfail` with the reason, or the
feature should get its own brief. Either is a founder/Hermes decision, not a
convergence action.

---

## KNOWN_BLOCKERS

### B0 · Two findings recorded rather than acted on — both need a decision

#### B0a · `src/master_agent/founder_edition/ai_client.py` — an **untracked** second provider path

A 90-line module inside the shipped package directory that:

- calls **OpenRouter/DeepSeek directly over `urllib.request`**, bypassing Model
  Router and Broker entirely — the "second provider path or client that bypasses
  the Broker" ADR-0024 Decision 7 names as forbidden, and against Vision §5.7's
  "no other component may decide";
- carries **its own `SYSTEM_PROMPT` defining Somesh** — a second persona;
- reads `OPENROUTER_API_KEY`, **which is set on this machine**, so anything that
  imported it would spend the founder's money with no approval gate (§10: *"Do not
  silently spend money"*);
- is the reason `urllib` and `os` appear in the `founder_edition` import set that
  `TestNothingExecutesOrCallsAI` guards.

**It is untracked** (`git ls-files` does not know it) and has **zero references**
anywhere — source, tests, packaging spec, JS. It is *not* in
`packaging/kalpavriksha.spec`'s `hiddenimports` and nothing imports it, so **it
does not ship today**. It is a loaded trap, not a live wound.

**Not deleted, deliberately.** Untracked means git holds no copy, so deletion is
unrecoverable — and the founder's standing instruction is to classify inherited
untracked work, not remove it.

**Recommendation: delete it.** OpenRouter is already a legitimate provider *through
the Broker* (`ai_infrastructure/catalog.py:404`, `provider_id="openrouter.api"`),
so nothing is lost. If it is wanted, it belongs behind the Broker like every other
provider. **Founder's call.**

#### B0b · **CLOSED** — the vendored server moved to the composition root

**Done.** `FixedBottleServer`, `ThreadedAdapter` and `SSLWSGIRefServer` (~170 lines
of vendored pywebview server) moved out of `founder_edition/desktop_shell.py` into
`kalpavriksha_desktop.py`, and `create_window()` now takes `server=` instead of
importing one. `socket`, `bottle`, `wsgiref` and `socketserver` are gone from the
guarded package.

**The remaining `os` import in `founder_edition` is `ai_client.py` and nothing
else** — verified by search, and then proven: parking that one untracked file makes
**all four** `TestNothingExecutesOrCallsAI` guards pass. It was restored
immediately. So the tracked source is now fully compliant with the guard, and B0a
is the only thing keeping it red.

Packaging is unaffected: PyInstaller's `Analysis` entry script *is*
`kalpavriksha_desktop.py`, so the imports are statically found exactly as they were
when they lived in a `hiddenimports` module.

Two things worth recording from doing it. The first extraction swept
`CONVERSATION_ID` and `_SOURCE_BY_NAME` out with the server classes because they
sit between them and `BridgeTextOutput` — caught immediately on import and put
back. The second: the moved code reads `random` and `threading`, which the root did
not import, and **the `LOAD_GLOBAL` guard added in Slice 5 caught both** before any
test exercised those branches. That is twice in one session it has caught a live
`NameError` in code that was about to be committed.

#### B0b (original text) · `founder_edition` imports `os` and `socket`

`tests/test_founder_edition_boot.py::TestNothingExecutesOrCallsAI` fails on two
assertions, and **these are not stale tests**. The guard's own comment states its
purpose: *"`subprocess`, `socket`, and `ctypes` are what this guard actually exists
to keep out."*

The cause is `desktop_shell.py`'s embedded `FixedBottleServer` (~120 lines) — a
genuine workaround for a pywebview 6.x bug where `@app.route('/')` and
`@app.route('/<file:path>')` both call `asset(file)`. Serving the local UI needs a
socket and filesystem paths, so the class cannot avoid them.

**Canonical fix, not applied:** move `FixedBottleServer` into
`kalpavriksha_desktop.py`. The composition root is the layer that *is* allowed to
own the environment — the same rule already stated for `record_interaction`, mode,
and machine scanning — and `create_window` already receives it as
`server=FixedBottleServer`, so the seam exists.

**Why it was not done today:** it changes what PyInstaller packages and how the
native window starts, and a packaged rebuild cannot be safely verified at this hour
(a locked-file build failure silently leaves the OLD exe). Breaking the founder's
desktop shell to satisfy a guard test is the wrong trade. **This is the single
clearest remaining piece of tracked implementation drift.**

### B1 · Gemini free-tier daily quota exhausted (external)

```
HTTP 429: Quota exceeded for metric:
generativelanguage.googleapis.com/generate_content_free_tier_requests,
limit: 20, model: gemini-3.6-flash
```

Spent legitimately on Live Acceptance B and D, which both passed. **No new
objective can be planned today** — the Planner is the only component that needs a
provider, so anything requiring a fresh MissionPlan is blocked until the quota
resets.

**The system behaved correctly under exhaustion, which is worth recording as its
own evidence:** it refused honestly, told the founder *"My reasoning service is
temporarily busy. Please try again in a moment."*, created nothing on disk, and
manufactured no success. Two independent runs, identical behaviour.

**Why the ladder did not fall through to the desktop AI applications.** The
acceptance runners pin `KALPAVRIKSHA_FMEA_REASONING_TIER=gemini` deliberately. In
a real founder launch the ladder is unpinned and a 429 *would* fall through to
ChatGPT/Kimi/Perplexity desktop — which is ADR-0017's ladder working as designed
and §10's free-first philosophy.

**A deliberate decision not to force that fall-through today.** Both ChatGPT and
Claude are currently running on this machine, and driving a desktop provider means
UI automation typing into the founder's live windows — several of the running
`claude` processes are plausibly Claude Code sessions, including the one doing
this work. Hijacking an unattended desktop to close out a test is not a trade
worth making. **The desktop-provider rung is therefore NOT live-proven.**

**To finish C:** rerun `scripts/live_acceptance/c_founder_checkpoint.py` after the
quota resets, or run it with the ladder unpinned while the founder is watching
their screen.

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

### FD1 · What status does a mission carry after the founder presses **Stop**?

**Observed live** (`c2_checkpoint_mechanism.py`, STOP run): the founder declines a
`founder_checkpoint`, the mutation is correctly **not** executed — and
`status.status` remains `awaiting_approval`. Nothing further will ever happen, but
the surface still reads as though it were waiting for the founder who has already
answered.

This is the same *shape* as the stale-message bug fixed in Slice 6, but it is **not
mine to fix**, because there is no truthful state to move it to:

- `FAILED` is untrue — nothing failed, the founder chose.
- `COMPLETED` is untrue — the work did not happen.
- `SUPERSEDED` implies a replacement that does not exist.

This is **exactly ADR-0021 Open Item O1**, already recorded and already the
founder's: *"§3.8 names four terminations; the ratified vocabulary has three
terminal states. There is no `CANCELLED`. … The founder should decide before C17's
brief whether cancellation is a seventh state, or whether §3.8's four ways collapse
to three."*

**Minimum decision needed:** does a founder-declined checkpoint (and a
founder-declined permission) terminate in a new `CANCELLED`/`DECLINED` state, or
project onto an existing one?

**What remains unblocked:** everything. The refusal itself is correct and proven —
only the label the surface shows afterwards is unsettled. Inventing a seventh state
here would pre-empt a decision ADR-0021 deliberately left open, so it is recorded
rather than guessed.

**Note:** the same stale label appears after a declined *permission*. One decision
covers both.

---

## HYPERAGENT_UI_WORK_REQUIRED

§19 inspected rather than assumed. Three of the five named areas are **already
built and wired**; two are genuinely absent and are recorded here without
inventing a design.

### Already built — no work required

| Area | Status | Evidence |
|---|---|---|
| Founder/Somesh text select & copy | **BUILT + WIRED** | `desktop_app/web/css/base.css:52-71` applies Hyperagent's `SELECTION_CONTRACT` in full — `user-select: text`, plus `-webkit-app-region: no-drag` (a drag region swallows mousedown so a selection never begins), `pointer-events: auto`, and `cursor: text`. Controls inside a message keep `cursor: pointer`. Founder should confirm on the packaged build. |
| Safe HTTP/HTTPS link click | **BUILT + WIRED** | `desktop_app/web/js/messageRender.js` — `http:`/`https:` only; `javascript:`, `data:`, `vbscript:`, `file:` rejected. Emits `target="_blank" rel="noopener noreferrer"`. Loaded by `index.html:117` as a module. |
| Attachments never inferred from prose | **CORRECT BY CONSTRUCTION** | `app.js:678` — *"A bare path stays prose; only an explicit Mission deliverable may ever become a file card."* This is exactly what §19 forbids inferring, and the UI does not. |

### UI-1 · Mission deliverable / artifact contract — **ABSENT, both sides**

There is no file-card component (no CSS class, no JS) and **no backend contract
publishing what a mission produced**. Verified by search across
`desktop_app/web/` and `src/master_agent/missions|mission_control`; the
"Deliverable N" hits in source are Mission Brief numbering, unrelated.

**Not blocking.** Live Acceptance B produced a real file and the founder was told
where it is, in prose, by the Reporter. The canonical loop closes without this.

**The backend data already exists** — this is a contract to expose, not a
capability to build:

- `PlanRecord.steps[]` carries `capability`, `payload`, `state`, `verdict`,
  `evidence_id` (`missions/history.py`). A verified `Filesystem.WriteFile` step's
  payload holds `location` (a named root: `desktop`/`documents`/`downloads`) and
  `path` (relative to it) — exactly enough to name a produced file.
- `verdict == "matched"` is what distinguishes a file that *exists* from one a plan
  merely intended.
- Named locations resolve through `executor/action.default_locations()`.

**Exact backend contract that would need adding** (Claude can build this once the
shape is agreed):

```
deliverables(objective_id) -> [
    { "location": "desktop",              # named root, never an absolute path
      "path": "KV_Golden_153713/page_info.txt",
      "capability": "Filesystem.WriteFile",
      "verdict": "matched",               # only verified steps qualify
      "step_id": "step_5" }
]
```

**What remains a Hyperagent UI decision:** whether a deliverable renders as a card
or a line; where it sits relative to Somesh's message; what a founder sees for a
folder versus a file; and whether an unverified step ever appears at all
(recommendation: no).

### UI-2 · Open / Save As — **ABSENT**

No opener and no save affordance in the page or the bridge. The bridge exposes 15
methods; none of them opens or saves a file.

**Backend capability already exists** — `Desktop.OpenFile` and `Desktop.OpenFolder`
are registered capabilities at `reversible_write` tier, so "Open" is a bridge
method away rather than new machinery. **Save As has no equivalent** and would need
a real decision: the sandbox resolves *named locations plus relative paths* and
refuses absolute ones, so a native Save-As dialog returning an arbitrary path does
not fit the current filesystem contract without widening it.

**Founder decision embedded here, flagged not answered:** whether Save As is worth
widening the filesystem sandbox for. **Not blocking Founder Edition.**

---

## LIVE_ACCEPTANCE_STATUS

| Proof | Status |
|---|---|
| A. Intent / conversation regressions (§12) | **LIVE_PROVEN through the real assembled surface** — `tests/test_live_acceptance_intent.py`, 9 passed. Enters at `DesktopShellApi.send_message()` on an app built by the real `boot_founder_edition()` (real Identity, ConversationEngine, CommunicationEngine, `IntentLayer`). **Planner deliberately spied** — `GEMINI_API_KEY` is set on this machine and a real call would spend founder quota and launch a browser on a synthetic probe (§32). For five of the six exchanges the required behaviour *is* that the Planner is never reached, which a spy proves better than a live call. Not yet clicked through the packaged .exe. |
| B. Medium golden mission | **LIVE_PROVEN — PASS, 2026-08-21 15:38.** Real Gemini planning, real visible Chrome, real folder on the founder's Desktop. Runner: `scripts/live_acceptance/b_medium_golden_mission.py`. See below. |
| C. Founder checkpoint (mechanism) | **LIVE_PROVEN — PASS, 2026-08-21 16:00.** `scripts/live_acceptance/c2_checkpoint_mechanism.py`. Hand-authored plan, **everything downstream real**. Both halves pass: Continue writes the previewed payload, Stop does not execute the mutation. See below. |
| C. Founder checkpoint (end-to-end, Gemini-planned) | **BLOCKED — external.** Gemini free tier exhausted (20 requests/day, `generate_content_free_tier_requests`) by acceptances B and D. Runner written and ready: `scripts/live_acceptance/c_founder_checkpoint.py`. See KNOWN_BLOCKERS. |
| D. Permission | **LIVE_PROVEN — PASS, 2026-08-21 15:48**, after fixing two real defects it exposed. Runner: `scripts/live_acceptance/d_permission_gate.py`. See Slice 6. |
| E. Persistence / recovery | **PASS for what Founder Edition claims** — `scripts/live_acceptance/e_persistence_recovery.py`. **Recording is wired and proven**: 9 missions readable from `plan_history.json` in a fresh process; every verified step records the expectation it was verified against; every failed step kept its errors; `events.jsonl`, `founder_interactions.jsonl`, `broker_decisions.json` all present. **Resume-after-restart is BUILT_BUT_UNWIRED, deliberately** — `restore_into()` is left uncalled and the source says so. Matrix Row 21 was wrong and is corrected. |
| F. Real intelligence route | **LIVE_PROVEN as a side effect of B** — B's plan was produced by a real Gemini call through Planner → Model Router → Broker → provider, with the ladder pinned to Gemini. `broker_decisions.json` holds the decision trail. **No Duck.ai** (`browser_free_ai` is never registered in this composition). Not separately scripted. |

### Live Acceptance B — the record

Objective given verbatim to the pipeline:

> Open a browser, go to https://example.com, and note the page's actual title and
> final URL. Then create a folder called `KV_Golden_153713` on the Desktop and write
> the observed title and final URL into a file called `page_info.txt` inside it.
> Then close the browser.

**Plan record — 6 steps, every one independently verified:**

| Step | Capability | Verdict |
|---|---|---|
| 1 | `Browser.OpenBrowserSession` | matched |
| 2 | `Filesystem.CreateFolder` | matched |
| 3 | `Browser.Navigate` | matched |
| 4 | `Browser.ObserveBrowser` | matched |
| 5 | `Filesystem.WriteFile` | matched |
| 6 | `Browser.CloseBrowserSession` | matched |

**Independent verification, read off disk after the mission claimed to be done:**

```
Title: Example Domain
URL: https://example.com/
```

**The observation is genuinely observed, not guessed.** The objective said
`https://example.com`; the file says `https://example.com/`. The trailing slash
exists only because a real browser resolved a real navigation — a Planner echoing
the objective could not have produced it. Step 4's observation bound into step 5's
write through canonical bindings.

**Mission truth held.** The first return was `awaiting_founder_completion`, not
`completed` — *"Work finished. All 6 executed step(s) were independently
verified."* Six verified steps did **not** self-promote to a verified Founder
outcome; it took an explicit `confirm_completion` to reach `completed`. That is
`STEP VERIFIED != FOUNDER OUTCOME VERIFIED` observed live rather than asserted.

**Artifact left in place as evidence:** `C:\Users\DELL\Desktop\KV_Golden_153713\`.
Founder can delete it once seen.

**What B did NOT exercise:** no `AWAITING_APPROVAL` gate was reached, so Live
Acceptance D (permission) is still unproven — see below.

---

## UNCOMMITTED_WORK_STATUS

**All inherited tracked work from T1 and T2 has been proven and committed.** The
working tree carries no uncommitted source or test changes from this session.

What remains uncommitted is untracked and was untracked before this session began:

- **~118 untracked paths** (T3) — root-level status files, `.bak`/`.backup` copies
  under `src/`, Hyperagent UI assets, audit documents. **Untouched. Nothing
  deleted.** 17 of the 18 under `src/` are `.bak`-style copies that Python cannot
  import and that therefore cannot affect runtime.
- **`src/master_agent/founder_edition/ai_client.py`** — the exception, and the one
  that matters. Untracked but a real `.py` inside the shipped package. See blocker
  B0a. **Left in place deliberately: untracked means git holds no copy.**
- **3 untracked test files** — `test_fire_and_forget_contract.py` (four of whose
  tests say **"CHARACTERIZATION — expected to FAIL today"** in their own
  docstrings), `test_launch_rescue_provider_hygiene.py`, and
  `test_golden_path_visible_chrome.py`. They run and mostly pass; they distort
  worktree comparisons, which is why the method note above exists.

**Nothing has been discarded at any point in this session.**

---

## RUNNING PROCESSES / ENVIRONMENT NOTES

- **The comparison worktree this session created has been removed** and pruned.
- **Three worktrees from EARLIER sessions remain and were left alone** — under
  `%TEMP%\kv_arch`, `kv_b2`, `kv_ship2`, all detached. Not this session's, not
  touched. `git worktree list` shows them.
- **No background processes are left running.** Every test run, acceptance runner
  and suite completed before this was written.
- **Desktop artifacts.** `Desktop\KV_Golden_153713\page_info.txt` is left on
  purpose — it is Live Acceptance B's evidence, holding the title and final URL a
  real browser observed. Delete it once seen. This session's own throwaway
  (`KV_PermD_154144`, from the first D run that failed on an absolute path) has
  been removed. `KV_VISIBLE_MEDIUM_093017` is dated **20 August** and is not this
  session's — left untouched.
- Tests require `PYTHONPATH=src`. There is no pytest config in `pyproject.toml`,
  so a bare `pytest` run will not resolve imports.
- Python 3.14.5.
- The four-file test run takes ~4 minutes; the full suite is slower. Prefer
  targeted `-k` runs during implementation.

---

# PAUSE CHECKPOINT — 2026-08-22 (laptop shutdown)

HEAD:        58c41fdcbbbb3ea6c2f9910c0a44f2153f60d9fd
BRANCH:      main
REMOTE SYNC: origin/main == HEAD, 0 ahead / 0 behind (verified by
             `git rev-list --left-right --count origin/main...HEAD` -> `0  0`)

Written at the Founder's pause instruction. Work stopped mid-repair on
purpose. Everything below is separated into **PROVEN**, **IN PROGRESS**
and **UNPROVEN**, and nothing is concluded that was not observed.

## CURRENT OPERATIONALIZATION STATE

The deterministic planning lane and the live acceptances are green and
committed. An active repair — giving `Reasoning.Transform` output a way
to reach `Filesystem.WriteFile` — is **written but never executed**. It
sits uncommitted in the working tree.

## COMPLETED AND CLOSED — PROVEN

Each of these was observed live, not inferred.

- **Deterministic local planning repair.** A fully dictated objective
  compiles with zero provider calls.
- **Acceptance C (founder checkpoint), Continue and Stop.** Both paths
  PASS. The preview is resolved, the payload written is the payload
  previewed, and Stop executes nothing.
- **Acceptance C2 (checkpoint mechanism).** PASS, both paths.
- **Acceptance D (permission gate).** PASS. The gate holds, the file
  survives until approval, and is really gone afterwards. Required
  repairs: a `_DELETE` recogniser, and `delete_file.py` publishing its
  `location` optional parameter (it always accepted it, never advertised
  it). Commit `d681fa6`.
- **Acceptance E (persistence/recovery).** PASS for what it claims.
- **Acceptance F (vendored server).** PASS.
- **Acceptance B (medium golden mission).** PASS — six steps executed,
  all six independently verified, `page_info.txt` holding
  `Title: Example Domain` / `URL: https://example.com/`. The trailing
  slash is the proof: that is the final URL as the browser resolved it,
  not the string in the objective.
- **Two planner guards, from a defect I introduced and then found.**
  `_explicit_workflow` had claimed the golden objective and compiled a
  TWO-step plan for a SIX-step instruction, writing the literal phrase
  "the observed title and final URL" to the Desktop. Now: an objective
  naming an operation this lane cannot compile is refused outright, and
  a phrase referring to a produced value is never treated as a literal.
  Commit `c86a6f0`.
- **Either voice, one instruction.** "a file containing X" and
  "write X into a file" state the same relation; only the first was
  recognised, so the golden objective got no local plan and died when no
  model was reachable. Commit `58c41fd`.
- **Packaged self-check.** `--self-check` runs inside the frozen process
  and reports 46 capabilities, five executives all runtime-reachable, the
  four-rung ladder, and deterministic planning. Commit `81b342b`.

### PROVEN this session, not previously recorded

- **Reasoning is alive on this machine.** ChatGPT Desktop answered a
  short prompt in ~35s through the `desktop` rung. The ladder is
  `local(0) -> desktop(4) -> gemini(1) -> browser(1)`; `local` is empty
  by deliberate policy (Ollama, 16GB RAM). So a reasoning failure is NOT
  "no provider is reachable" — that diagnosis is wrong and should not be
  repeated.
- **`gemini.api` is out of quota:** HTTP 429, "You exceeded your current
  quota". **`browser.free-ai` (Gemini web)** returns "sign-in required
  for this session, not usable anonymously". Both observed directly.

## CURRENT ACTIVE PROBLEM

The Founder objective:

    Think of three short names for a gardening notes app and write them
    into names.txt on the Desktop.

### The finding to preserve

    The mission appears structurally to require:

    Reasoning.Transform
    -> produced text
    -> Filesystem.WriteFile

    The Founder objective requires reasoning for generating the names,
    but should not automatically require an external AI Planner to
    rediscover the two-step capability composition.

### The unresolved constraint to preserve

    Cross-step bindings currently require canonical matched Evidence.
    Reasoning.Transform currently needs its existing verification/
    generated-text architecture inspected before changing this path.

## EXACT SYMPTOM — PROVEN

Before any of today's uncommitted work, the objective failed with:

    no plan: the provider could not answer
    (Gemini (web): sign-in required for this session, not usable anonymously)

The Planner sent a **20,869-character** prompt (the whole 46-capability
catalogue) to the reasoning ladder purely to be told that producing text
then writing it is `Transform -> WriteFile`.

## ROOT CAUSE PROVEN SO FAR

Two separate causes, both observed, neither previously known.

**1. The planning prompt should never have been sent.** Nothing in that
objective needs a model to choose the composition. Required, per the
Founder: `Planner provider calls = 0`, with AI used *inside*
`Reasoning.Transform` only.

**2. `PluginGateway.verify()` returns `None` by contract**, and the
Reasoning Executive was registered through it.
`runtime/input_resolution.py` resolves a bound value only from a source
carrying canonical Evidence whose verdict is `matched` and whose
*observation* holds the field. So **no binding out of
`Reasoning.Transform` could ever resolve.** The two halves were never
joined; nothing was broken.

Classification, using the Founder's own categories:
**2 — EXISTING CONTRACT SUPPORTS IT BUT CURRENT COMPOSITION MISSES THE
SEAM.** Evidence for that classification, all read from current source:

- `ai_infrastructure/text_verifier.py` (MB035) already exists and
  produces canonical `Evidence`.
- Its `observe()` already publishes a **`text`** field — exactly what
  `Filesystem.WriteFile.content` needs to bind to.
- `planner/outcomes.py::SuccessSpec` already emits text-shaped checks
  built from `text_verifier.expect`, so a Reasoning step's
  `ExpectedOutcome` is already the right shape.
- `ai_infrastructure/execution.py:330` already calls
  `verify_text(result.text, expected)`.
- `PluginGateway`'s own docstring names the sanctioned join: *"an
  Executive with a Verifier supplies a gateway that pairs the two"* —
  which is exactly what `FilesystemGateway` already does.

No second verifier is needed. No second Reasoning capability is needed.

### A third defect, found on the way — PROVEN, and worth keeping

While diagnosing, the desktop rung was caught **fabricating answers**.
Twice, with different causes:

1. It returned the composer's own placeholder, "Message ChatGPT", as
   the model's reply — `ok=True`, fifteen words, to a twenty-thousand
   character question.
2. After that was fixed, it returned " Browser.OpenBrowserSession |
   args: session_id" — a fragment of **the founder's own prompt**,
   echoed back in the transcript.

Cause of (2): `find_new_content()` anchored its floor by finding a region
whose text *equals* the submitted prompt. A long prompt is never one
region — a chat UI splits it into one block per line — so nothing
matched, the floor collapsed to the window top, and the prompt's own
rendered lines became candidates.

Both reached no one only because a downstream expectation happened to
reject them. **A wrong answer caught by luck downstream is still a wrong
answer**, and this is the reason the strict Evidence rule above must not
be weakened to get the objective passing.

## SOURCE FILES CURRENTLY INVOLVED

Dirty tracked (3), all intentionally uncommitted:

- `kalpavriksha_desktop.py` — registers `ReasoningGateway` in place of
  `PluginGateway` for the reasoning plugin, plus its import.
- `src/master_agent/desktop/execution/uia_control.py` — the two
  fabrication fixes above.
- `src/master_agent/planner/direct.py` — the `_generate_then_write` lane.

Untracked new source (3):

- `src/master_agent/plugins/reasoning_gateway.py` — **new file**, the seam.
- `scripts/live_acceptance/g_reasoning_required.py` — probe: an objective
  that genuinely needs a model; separates ladder behaviour from mission
  outcome so an external outage is never reported as a code failure.
- `scripts/live_acceptance/h_generate_then_write.py` — **the acceptance
  for this repair. Written, never run.** It counts provider calls by
  requester, so "Planner provider calls = 0" is measured, not asserted.

## CHANGES ALREADY MADE — IN PROGRESS, NOT PROVEN

Note for the record: the Founder's pause message said *"Do not implement
that repair now."* That message arrived after the code below had already
been written. It is left in place, uncommitted and unproven, exactly as
the pause instruction requires for mid-repair work — not committed, not
reverted, not tidied.

1. **`ReasoningGateway`** (new). Pairs the reasoning plugin with
   `TextVerifier`. `invoke()` keeps the produced text keyed by the call
   that produced it; `verify()` measures **that artefact** with
   `verify_text(text, expected)` and returns canonical `Evidence`, or
   `None` when the artefact cannot be identified with certainty.

   Why measuring the produced text is not "verifying from the result":
   `text_verifier.py`'s own docstring already settled this for this
   medium — for a disk you stat the path, for a page you re-read the DOM,
   and for generated text **the answer is the artefact**. The observation
   is re-derived deterministically every time and the provider is never
   asked to grade itself.

2. **`_generate_then_write` lane in `direct.py`.** Recognises a verb of
   origination ("think of", "come up with", "generate", ...) plus a named
   file and a named place, and refuses on any doubt — including
   `_FOREIGN_OPERATION`, and any sentence also naming a folder, a URL or
   a deletion, since other lanes own those.

3. **Two `uia_control.py` fixes** for the fabrications described above.

## TESTS ALREADY RUN — with results

- `tests/test_deterministic_planning.py` — **38 passed** (28 before this
  session's additions).
- UIA/desktop subset (`-k "uia or desktop_exec or find_new"`) — **454
  passed, 2 failed**. Both failures are
  `test_the_desktop_executive_still_decides_nothing` and
  `test_the_broker_reads_the_estate_from_the_desktop_executive`, which
  assert the estate is `['ollama.local']` and got
  `['ollama.local', 'gemini.api']`. **Environment-dependent** — a
  `GEMINI_API_KEY` is present in that shell — and unrelated to any change
  here. Not yet triaged.
- **Full suite: 95 failed, 7769 passed, 2 skipped** (15m36s). Previous
  recorded baseline: 93 failed / 7722 passed. The +47 passing are this
  session's new tests; the +2 failures are the two environment-dependent
  broker tests above. **No test that passed before this session fails
  now.** The full list is in the session scratchpad, not the repo.

  This suite ran **before** the three dirty files reached their current
  state, so it does not cover the uncommitted repair.

## LIVE EVIDENCE

- `Desktop\KV_Golden_102901\page_info.txt` — Acceptance B's evidence.
  Left on purpose.
- Acceptance D and C2 folders (`KV_PermD_102935`, `KV_C2_STOP_102934`)
  and the C/G run folders are left as run evidence.
- `Desktop\names.txt` — **does not exist.** The objective has never
  completed. Acceptance H deletes any stale copy first, so its existence
  will always prove the run that created it.

## UNCOMMITTED WORK — and why it is uncommitted

All six files listed above. They are coherent and they compile — the
two-step plan was verified to build with the correct binding:

    step_1 Reasoning.Transform   payload={'instruction': 'Think of three
                                 short names for a gardening notes app...'}
    step_2 Filesystem.WriteFile  bindings={'content': {'from_step':
                                 {'step_id': 'step_1', 'field': 'text'}}}

**But not one line of it has ever executed against the live pipeline.**
The gateway has never produced Evidence, no binding has ever resolved
through it, and `names.txt` has never been written. Committing this as
though it were finished would be a claim I have not earned, so it stays
dirty, per the Founder's instruction.

## UNPROVEN — explicitly

- That `ReasoningGateway` produces Evidence the Runtime accepts.
- That `input_resolution` resolves `content` from that Evidence.
- That the whole objective completes end to end.
- That planner provider calls are actually zero at runtime (compiling the
  plan locally strongly implies it, but implication is not measurement —
  that is what acceptance H exists to settle).
- That the two `uia_control.py` fixes hold under a live desktop run; the
  second has no dedicated regression test yet.
- Whether the desktop rung can return a **whole** structured reply. Last
  observed, it returned real plan JSON missing its opening `{"steps"` —
  the reply renders as sibling regions and no container was eligible.
  **Unresolved, and now lower priority**: with planning done locally, a
  20k-char planning prompt should never be sent at all.

## IMPORTANT ARCHITECTURAL CONSTRAINTS

- Do not send deterministic planning work to external AI.
- Local deterministic work => zero provider calls.
- A deterministic workflow containing `Reasoning.Transform` => AI belongs
  in the execution step, not automatically in the Planner.
- Do not weaken verified input-binding trust.
- Do not trust raw `ExecutionResult` for cross-step bindings.
- Inspect/reuse the existing generated-text/`TextVerifier` work before
  designing any Reasoning verification. **(Done — see the classification
  above. It already supplies what is needed.)**
- Ollama remains disabled (16GB RAM).
- Duck.ai remains excluded from Founder Edition.
- No second Planner / Browser / Desktop / Reasoning architecture.

## EXACT NEXT INVESTIGATION

Run the repair that is already written, and find out whether the Evidence
it produces actually satisfies `input_resolution`. Specifically: does
`verify_text` return verdict `matched` for a `SuccessSpec(min_words=1)`
expectation over the produced text, and does `_verified_value()` find
`text` in that Evidence's observation.

## EXACT NEXT FILES TO INSPECT

1. `src/master_agent/plugins/reasoning_gateway.py` (new, unexecuted)
2. `src/master_agent/runtime/input_resolution.py` — `_verified_value()`,
   the seven conditions at the top of the module docstring
3. `src/master_agent/runtime/engine.py:577` — `_verify()`, how Evidence
   reaches Mission Control
4. `src/master_agent/ai_infrastructure/text_verifier.py` — `observe()`
   and `verify_text()`
5. `src/master_agent/planner/direct.py` — `_generate_then_write`

## EXACT NEXT TEST TO RUN

    python scripts/live_acceptance/h_generate_then_write.py

It prints exactly the record the Founder asked for: Planner provider
calls, Reasoning provider calls, planned steps, reasoning output, binding
Evidence, `names.txt` exists, `names.txt` contents. Required:

    Planner provider calls = 0
    Reasoning.Transform actually executes = YES
    WriteFile receives produced text, not predicted text = YES
    final Desktop file = YES

Then, before anything is committed:

    PYTHONPATH=src python -m pytest tests/test_deterministic_planning.py -q
    PYTHONPATH=src python -m pytest tests/ -q -p no:randomly --tb=no

and add regression tests for the two `uia_control.py` fixes and the
`_generate_then_write` lane, which have none yet.

## DO NOT REOPEN

- Acceptance C, unless a later packaged regression proves failure.
- The completed provider-web wiring.
- The completed deterministic local-planning repair.
- "No reasoning provider is reachable" as a diagnosis — disproven above.

## FINAL RELEASE GOAL

Build and prove the packaged Founder Edition from final HEAD, perform the
restart smoke test, then launch the final production application and
leave it open and running for the Founder. **Not done — the package must
be rebuilt from final HEAD, because production source has changed since
the last build.**

## PROCESS STATE AT PAUSE

- **No Kalpavriksha instance is running.** The packaged instance launched
  earlier this session (PID 7972) had already exited before the pause.
- **No test, build or acceptance process of mine is running.** All
  completed; both background suite runs exited.
- **No browser session survived.** Acceptance B's own final verified step
  closes the browser.
- **Two `python.exe` processes belong to Hermes**
  (`hermes_cli.main gateway run`) and were deliberately left alone.
- `msedgewebview2` processes remain from earlier in the day with no
  parent Kalpavriksha process; not started by this session's tooling and
  not touched.
- Nothing was killed, and no evidence or log was deleted.

---

# RESUMED AND CLOSED — 2026-08-22 (same day, after the shutdown pause)

HEAD:        003be1c9ebbaa16c3fb22f78afb1d5158dad7c4b
BRANCH:      main
REMOTE SYNC: origin/main == HEAD, 0 ahead / 0 behind
TRACKED TREE: clean

The repair the pause checkpoint left **written but never executed** has
now been executed, proven live, tested, committed and packaged. This
section supersedes that checkpoint's UNPROVEN list.

## Acceptance H — PASS

The Founder objective, through the production pipeline:

    Think of three short names for a gardening notes app and write them
    into names.txt on the Desktop.

    Planner provider calls:   0
    Reasoning provider calls: 2
    Planned steps:            Reasoning.Transform -> Filesystem.WriteFile
    Reasoning output:         'Sprout, Flora, Bud'
    Binding Evidence:         verdict=matched
                              evidence_id=bf7a2ac1-3600-4929-9baa-79a1f89776d9
                              worker=text  environment=generated_text
    names.txt exists:         True
    names.txt contents:       Sprout, Flora, Bud

Every required condition met. The chain is live-proven end to end:
deterministic plan -> Reasoning.Transform -> real produced text ->
canonical Evidence from `TextVerifier` -> `input_resolution` binding ->
`Filesystem.WriteFile` -> a real file holding the produced names.

## Four defects, none of them new architecture

The pause checkpoint had established the seam. Running it exposed three
more, in front of and behind it. All four are fixed in `7ae49cf` and
`003be1c`.

1. **Planning was still being sent to a model.** Now compiled locally by
   `_generate_then_write`. Planner provider calls = 0, counted at the
   door by requester rather than asserted. The Transform prompt is 390
   characters of the founder's actual instruction, not 20,869 characters
   of capability catalogue.

2. **The seam itself.** `ReasoningGateway` pairs the Reasoning Executive
   with MB035's `TextVerifier`, in the shape `PluginGateway`'s own
   docstring prescribes and `FilesystemGateway` already follows. No
   second verifier, no second capability, `input_resolution` untouched.
   It fails closed: no Evidence at all when the artefact under test
   cannot be identified with certainty.

3. **Sensitivity was never declared.** `Reasoning.Transform` defaults to
   `sensitive` -- correctly, since its `context` is normally a document
   off the founder's disk. That cannot reach a step built with no
   `context` and no `depends_on`. Unsaid, the Broker ruled every
   third-party provider `NOT_PRIVATE`; the only PRIVATE providers here
   are Ollama (disabled by the RAM policy) and LM Studio (not installed);
   so selection refused before `approval_needed()` could offer the
   founder the choice, and the mission died with "none eligible" rather
   than with a question. The contract already provided for a plan that
   knows its material is public to say so. It now says so, for that step
   only.

4. **The question itself was malformed.** Every Transform prompt opened
   with "you are reasoning over evidence gathered by earlier steps" and
   closed with "if the evidence does not contain something you were asked
   about, say so rather than supplying it from general knowledge" --
   whether or not any evidence existed. With none, the model obeyed
   perfectly and returned "The evidence provided does not contain names
   for a gardening notes app", which was then verified, bound and written
   to the Desktop. The machinery was flawless; the question was wrong.
   The evidence framing is now stated when there is evidence and not when
   there is none. A Transform carrying context is held to the same rule,
   word for word.

## The two desktop fabrications — fixed and pinned (`7ae49cf`)

Both had been recorded by the runner as SUCCESSFUL answers, and both
reached no one only because a downstream expectation happened to reject
the text.

- The composer's own placeholder, "Message ChatGPT", returned as the
  reply to a 20,869-character prompt. Focusable elements were already
  excluded for exactly this reason and it was not enough: the app draws
  the placeholder as a separate NON-focusable label over the input. The
  rule that holds is ownership, not focusability.
- A block of the founder's own prompt, echoed in the transcript. The
  floor meant to bury the prompt was anchored on a region whose text
  EQUALS the whole prompt; a long prompt is never one region.

Three regression tests now pin these, including one proving a genuine
reply below the echoed prompt is still found -- the guard must not
starve the reader. Both changes only ever ADD exclusions, so the reader
can return `None` more often and never accept more: **fail-closed by
construction**. Submission, provider availability, the Claude Desktop
`AUTONOMOUS_REASONING_UNSAFE` gate and session isolation are untouched.

## Tests

- Focused: `test_deterministic_planning.py` 46, `test_desktop_uia.py` 67,
  `test_reasoning_gateway.py` 10 (new), plus text-verification,
  cross-step binding, binding plan/runtime and reasoning role separation
  -- all passing.
- **Full suite: 94 failed, 7791 passed, 2 skipped.** Baseline was 95 /
  7769. Failure lists were diffed rather than counted:
  **zero new failures**, and one pre-existing failure now passes --
  `test_verified_execution.py::test_a_verified_answer_reaches_the_founders_memory_end_to_end`,
  which is precisely about a verified answer reaching the founder.
- The 94 remaining are the inherited baseline, untouched by this work and
  not chased.

## Packaging and the running application

- `packaging/kalpavriksha.spec` gained
  `master_agent.plugins.reasoning_gateway` as a hidden import. It is
  imported inside `_build_mission_pipeline()` like every other entry
  there, so static analysis cannot see it; without the declaration a
  packaged run would have lost the Evidence the whole path depends on.
- Package **rebuilt from final HEAD**. Artifact verified by timestamp,
  not by exit code: `dist/Kalpavriksha/Kalpavriksha.exe`, 13:10, 36.9 MB
  (the stale 10:15 build is gone).
- **Packaged self-check: RESULT OK** -- `packaged: True`, 46
  capabilities, five executives all runtime-reachable, four-rung ladder,
  deterministic planning and founder checkpoint both working inside the
  frozen process. This is also the proof that `reasoning_gateway` was
  collected: the pipeline imports and registers it, so a missing module
  could not have assembled.
- **Restart smoke: PASS.** Launched, verified, closed, confirmed gone,
  relaunched cold. Window "Kalpavriksha" visible and responding, UI
  serving HTTP 200 (5,197 bytes) on 127.0.0.1, exactly one instance.
- **The packaged Founder Edition is running now and was left open** --
  PID 8708.

## Stated precisely: packaged vs source

The frozen process is proven to assemble the identical composition and to
plan deterministically (self-check, above). The mission acceptances --
B, C, C2, D, E, F, H -- were executed through the real production path
(`_build_mission_pipeline` + `_submit_objective`) at this same HEAD,
launched from source rather than from the exe, because the packaged app
speaks to its UI over pywebview's internal `js_api` bridge and has no
external mission endpoint to drive. Driving the GUI by automation was not
attempted, so **"the frozen exe executed a full mission" is not claimed
here**; what is claimed is that it assembles the same 46 capabilities,
the same five reachable executives, the same ladder and the same
deterministic planner, and that it launches, serves and restarts.

## Observed and NOT acted on

While recovering repository truth, `args_complete=False` was found on 15
of the 19 Desktop capabilities -- including `DesktopClick`,
`DesktopPressKey` and `FindTarget` -- because those actions never
declare `optional_parameters()`, leaving their schemas open. The
consequence is measured, not inferred: `direct_plan` refuses them, so
those capabilities cannot be planned without a model, and only
`LaunchApplication`, `DesktopObserve`, `DesktopTypeText` and `ReadText`
can. It is the same contract-incompleteness class as `delete_file.py`'s
unpublished `location`, fixed earlier in `d681fa6`, and the four actions
checked read only their required parameters -- so the truthful
declaration is an empty list, not a new argument.

**Deliberately left alone.** No Desktop blocker appeared in operational
acceptance, and the instruction was not to open a P0 Desktop campaign
tonight. Recorded here so the next session does not rediscover it.

Also still true and unchanged: the desktop rung's handling of a long
STRUCTURED reply (a JSON plan arrived missing its opening `{"steps"`,
rendered as sibling regions with no eligible container). Now largely
moot -- with planning done locally, a 20k-character planning prompt
should never be sent at all.

---

# PACKAGED FOUNDER ACCEPTANCE — 2026-08-22

Driven through the **real packaged UI**: the founder window, its own
pywebview/WebView2 bridge, real mouse and real keyboard via the project's
own Win32/UIA mechanisms. No HTTP endpoint, no Runtime bypass, no
`_submit_objective()` call, no import into the frozen process, no second
bridge, no synthetic test interface.

FINAL HEAD:  5f097218cfc1eff15ac667721427c282c9cb6383
PACKAGE:     dist/Kalpavriksha/Kalpavriksha.exe, built 15:10 from that
             production source (every production file predates the build;
             only docs and tests changed after it)

## Results

| mission | through the packaged UI | outcome |
|---|---|---|
| A — deterministic local | "Create a folder called KV_PACKAGED_LIVE on the Desktop." | **PASS** — folder on disk, UI: "Work finished. All 1 executed step(s) were independently verified." |
| B — reasoning to action | "Think of three short names for a gardening notes app and write them into packaged_names.txt on the Desktop." | **PASS** — `Sprout / Leaflet / Flora`, 105s |
| C — cross-Executive golden | browser → observe → folder → file → close | **PASS** — 6 steps, all independently verified, 24s |
| cold restart | closed, confirmed gone, cold launch, "Create a folder called KV_AFTER_RESTART on the Desktop." | **PASS** — folder on disk, UI reported verified completion, 14s |

Mission C's file, off disk:

    Title: Example Domain
    URL: https://example.com/

The founder's sentence said `https://example.com` **without** the
trailing slash. The slash is therefore material evidence that the final
URL flowed out of the page the browser actually resolved, rather than
being copied from the instruction.

Mission B's file holds three invented names -- not the founder's own
prompt echoed back, not `Message ChatGPT`, not an error explanation, and
not anything a planner could have predicted.

## The defect this found, which source acceptance could not

**`_drive_until_settled` abandoned a mission between its steps.**

Mission B, first packaged run: the plan was right, `Reasoning.Transform`
ran, produced real text, and its Evidence came back `matched` with the
text in the observation -- and `Filesystem.WriteFile` was never
dispatched at all. The runtime went idle holding a completed, verified
dependency. The founder watched "that's taking longer than expected" for
seven minutes about work that had already stopped.

The loop bounded the mission by **elapsed time**, and `run_once()` blocks
for the whole of the step it runs. A step that asks a desktop AI for an
answer takes minutes; the packaged UI passes the 45-second default. So
the deadline had *always* expired by the time control returned, and the
loop exited between step one and step two. Nothing else drives the
Runtime, so the mission stayed abandoned forever.

Classification: **WIRED BUT RUNTIME/CONFIG BROKEN.** The architecture was
right; the bound was measuring the wrong thing.

Repair: the deadline now bounds **silence, not work**. Every observable
step forward returns the full budget. The bound is still real -- a
runtime reporting no progress is still cut off after one budget -- but it
measures how long a mission has been silent rather than how long it has
been running. Progress is read from Mission Control's own
`founder_state()`, best-effort, so a Mission Control without it still
drives. Both tests use real time rather than a stubbed clock, because the
loop reads `time.monotonic()` itself, and the slow-step test was
confirmed to fail with the fix reverted.

Why source acceptance missed it: every source runner passed an explicit
generous `timeout_seconds`. Only the packaged UI uses the default.

### Also fixed, and honestly NOT the cause

`_generate_then_write` emitted hard-coded `"step_1"`/`"step_2"`. Every
other lane carries a per-mission mark, for the reason
`_single_capability_plan` documents: a step id must be unique across
every mission the process ever runs, because
`RuntimeEngine._objective_of()` returns the FIRST objective holding a
matching id, and the founder's own plan history already had **26**
records colliding on those two names. This was my first hypothesis and it
was **wrong** -- the mission stalled identically once ids were unique.
It is a real latent defect that would eventually bind a live step to a
long-finished mission, so it is fixed and pinned for every lane, but it
did not cause this failure.

## Founder UI behaviour, observed

- Accepts typed input through the composer (`.composer-input`,
  contenteditable); the window was confirmed to hold the text before
  Enter was ever sent.
- Progresses truthfully: `Working` → `Step 1 of 2` → `Checking the
  result` → the verified terminal sentence.
- Does **not** report completion before verification supports it -- every
  completion sentence counted independently verified steps.
- Shows the founder-completion state correctly, with the real path.
- Remains responsive after a mission: B, C and the restart mission were
  each submitted while a previous completion prompt was still pending,
  and all three ran.
- Greets with real temporal awareness ("Good afternoon, Onkar. Somesh
  here. Everything is ready.").

## Open observations — NOT acted on

1. **"Mark complete" does not respond to synthetic clicks.** The button
   is not exposed as its own UIA element (only its label is), and clicks
   at its rendered position produce no `founder_completion_confirmed`
   event, while composer clicks at the same scale work. The backend
   genuinely holds a pending completion (`completion_id 19d0f661`), so
   this is *not* stale UI. Whether a physical human click behaves
   differently could not be determined from here. It does not block: three
   missions ran with a completion pending. Left for the founder to try.

2. **The window restores off-screen.** After a minimise/restore it was
   placed at (190,190)-(2136,1296) on a 1920x1080 screen, putting the
   composer below the visible area. Maximising fixed it. Worth a look
   before release.

3. **Driving the UI needs DPI awareness.** UIA reports logical
   coordinates in a DPI-unaware process while SendInput uses physical
   ones; on this 150% display that puts every click at two thirds of its
   intended position. Recorded because the product's own
   `Desktop.DesktopClick` takes coordinates and could meet the same trap.

4. `15/19` Desktop capabilities still carry `args_complete=False`. No
   packaged mission was blocked by it. Still post-release.

## Tests

Focused, all passing: `test_deterministic_planning.py` 49,
`test_founder_approval_path.py` 12, `test_reasoning_gateway.py` 10,
`test_desktop_uia.py` 67.

Targeted regression across every area these two fixes could touch --
deterministic planning, the founder/approval drive path, the reasoning
gateway, text verification, cross-step binding, binding isolation,
reasoning role separation and fallback, filesystem, executive
reachability, verified execution:

    429 passed, 3 failed, 1 skipped

All three failures are in the inherited baseline -- each appears in both
the 95-failure and 94-failure lists recorded earlier today. **Zero new
failures.**

### The full suite could not complete in this environment

`tests/test_desktop_shell.py` **hangs**, at
`TestGreet::test_greeting_names_no_internal_component`. Verified in a
clean worktree that it hangs **identically at `f756685`, before either of
today's fixes** -- `timeout` exit 124 both times, same eleven dots. It is
pre-existing and environmental, not a regression. I said the opposite
before checking; the worktree comparison corrected it.

It sits in the greeting/temporal-awareness path, which the packaged
application performs correctly ("Good afternoon, Onkar. Somesh here.
Everything is ready."), so nothing founder-facing is blocked. Per the
instruction not to open environment work that no packaged mission proves
is blocking, it was left alone and is recorded here instead.

With that file deselected the suite progresses past it but runs at
roughly one test per 45 seconds -- real browser and UIA tests against a
machine carrying ~25 provider windows left open by this session's own
reasoning attempts, plus the packaged app. That is an environment cost,
not a code one, and it is why the targeted regression above is what was
run to completion.
