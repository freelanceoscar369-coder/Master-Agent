# KALPAVRIKSHA — PRODUCTION WIRING TRUTH & RECONCILIATION REPORT

**Date:** 2026-08-19 · **Base:** `dcb86e1` (the brief's `dcb86e7` was a transcription
error — that object does not exist in this repository)

Nothing was replaced. Every currently-integrated Executive runs exactly the code it ran
before; what changed is that three of them can now produce canonical `Evidence`.

---

## 1. Git Truth

| | |
|---|---|
| HEAD at start | `dcb86e1` == `origin/main`, ahead 0, behind 0, nothing staged |
| Protected worktree | 5 pre-existing modified files + 3 pre-existing untracked tests — untouched |

---

## 2. Classification of this session's changes — **UNRELATED = 0**

| Class | Files |
|---|---|
| Filesystem verification wiring | `plugins/filesystem_expectations.py` *(new)*, `filesystem_gateway.py`, `filesystem_observation.py`, `filesystem_verifier.py` |
| Browser verification wiring | `plugins/browser_expectations.py`, `browser_gateway.py`, `browser_session_verifier.py` *(all new)*, `browser_observation.py` |
| Desktop verification wiring | `desktop/gateway.py` *(new)* |
| Capability contract publication | `executor/actions/write_file.py` |
| Runtime lifecycle change | `runtime/engine.py` — **deferred, see §5** |
| Composition | `kalpavriksha_desktop.py` |
| Regression | `tests/test_production_gateway_wiring.py` *(new)*, `tests/test_filesystem_founder_path.py` |

---

## 3–4. Existing capabilities preserved

Verification is an **adapter around** each existing capability, never a replacement.

* `FilesystemGateway.invoke()` → `FilesystemWorker.run_step()` — unchanged.
* `BrowserGateway.invoke()` → `BrowserWorker.run_step()` on the **same**
  `BrowserSessionManager` the plugin drives. A second manager would have opened a second
  browser and verified a window nobody navigated; the composition passes the plugin's own.
* `DesktopGateway` **subclasses `PluginGateway` and overrides only `verify()`**.
  `invoke` is not in its `__dict__`, so the Desktop execution path is *provably* identical.

---

## 5. The global fail-closed gate — DEFERRED, and why

`evidence is None → cannot complete` was implemented earlier in this session. It is
**not shipped**. The Runtime is byte-identical to `dcb86e1` in behaviour — the diff is
21 insertions, 0 deletions, all comment.

The reason is sequencing, not doubt. Desktop reaches the Runtime through a gateway that
cannot verify 14 of its 19 capabilities, so switching the strict gate on today would stop
working Desktop capabilities from completing — disabling integrated production behaviour
to enforce an invariant, which is a worse failure than the one being fixed.

The implemented version is preserved for reference at
`scratchpad/engine_failclosed_reference.py`, and the deferral, its trigger condition and
its rationale are recorded in a comment at the gate itself.

---

## 6. Desktop wiring trace — current stack confirmed

`DesktopPlugin` registers **19** capabilities. The three named in the brief resolve to the
current interaction layer, not the intentionally incomplete older implementations:

| capability | implementing class | module |
|---|---|---|
| `launch_application` | `VerifiedLaunchApplicationAction` | `desktop.actions_interaction` |
| `focus_window` | `VerifiedFocusWindowAction` | `desktop.actions_interaction` |
| `bring_to_front` | `VerifiedBringToFrontAction` | `desktop.actions_interaction` |

The wider surface remains registered: `find_target`, `desktop_observe`, `desktop_click`,
`desktop_type_text`, `read_text`, `desktop_press_key`, `close_window` — all from
`actions_interaction`; `execute_command`, `open_file`, `open_folder`, `is_running`,
`is_installed`, `get_version`, `list_installed_software`, `list_running_processes`,
`close_application` from `desktop.actions`.

No capability was modified.

---

## 7–8. Desktop verification coverage matrix

Independent read-only observation sources already in the Desktop package:
`WindowManager.enumerate / locate / locate_by_process / active`,
`ProcessExecutive.is_running`, and `intelligence.evidence.capture_evidence()` (documented
"never types, clicks, submits, renames, or creates anything").

| capability | execution impl | independent observation | canonical verification without changing execution? |
|---|---|---|---|
| `launch_application` | `VerifiedLaunchApplicationAction` | `ProcessExecutive.is_running` | **YES** |
| `close_application` | `CloseApplicationAction` | `ProcessExecutive.is_running` | **YES** (absence) |
| `focus_window` | `VerifiedFocusWindowAction` | `WindowManager.active` | **YES** |
| `bring_to_front` | `VerifiedBringToFrontAction` | `WindowManager.active` | **YES** |
| `close_window` | `CloseWindowAction` | `WindowManager.locate` | **YES** (absence) |
| `desktop_observe` | `ObserveDesktopAction` | `capture_evidence` | NO — the effect *is* the observation; no separate postcondition |
| `find_target` | `FindTargetAction` | `capture_evidence` | NO — returns a locator; nothing changes |
| `read_text` | `ReadWindowTextAction` | UIA text read | NO — query |
| `desktop_click` | `ClickControlAction` | none generic | **NO** — a click's postcondition is application-specific |
| `desktop_type_text` | `TypeIntoWindowAction` | UIA control read | NO — only where the app echoes into an identifiable control |
| `desktop_press_key` | `PressKeyAction` | none generic | **NO** |
| `execute_command` | `ExecuteCommandAction` | none generic | **NO** — arbitrary shell |
| `open_file` / `open_folder` | `desktop.actions` | `WindowManager` | NO — which window is app-specific |
| `is_running`, `is_installed`, `get_version`, `list_*` | `desktop.actions` | n/a | NO — queries |

**5 of 19 verifiable.** The rest return `None` — not a fabricated `MATCHED`, and never a
fallback to the Planner's text-shaped checks.

---

## 9–10. Domain verification support, all three Executives

| domain | supported | not yet supported |
|---|---|---|
| **Filesystem** (14) | `create_folder`, `write_file`, `append_file`, `copy_file`, `move_file`, `rename_file`, `delete_file`, `delete_folder`, `workspace_bootstrap` — **9** | `read_file`, `list_directory`, `search_files`, `file_exists`, `directory_exists` — **5 queries** |
| **Browser** (9) | `open_browser_session`, `navigate`, `observe_browser`, `close_browser_session` — **4** | `click`, `type_text`, `scroll`, `press_key`, `wait_for_selector` — **5** |
| **Desktop** (19) | `launch_application`, `close_application`, `focus_window`, `bring_to_front`, `close_window` — **5** | 14 |

Exact **content** verification exists only for `write_file`. `append_file` is deliberately
excluded: the finished file is prior content plus this step's, and this layer never saw
the prior content, so a payload-derived digest would fail a correct append.

Query capabilities are excluded on purpose. An existence check would be actively wrong:
`file_exists` reporting `False` about a genuinely absent file is a **correct** execution,
and an exists-check would mark it failed.

So the honest statement is **not** "filesystem verification complete" — it is: the
world-changing filesystem capabilities are verified; the five query capabilities are not.

---

## 11. Global fail-closed decision

**ALL CURRENTLY COMPLETING PRODUCTION EXECUTIVES HAVE A CANONICAL VERIFICATION PATH = NO.**

Filesystem and Browser now do for their world-changing capabilities. Desktop covers 5 of
19. Until the remaining gaps are either verified or explicitly exempted, the strict gate
stays off. This is sequencing, not abandonment.

---

## 12. Composition-root drift test

`tests/test_production_gateway_wiring.py` — **12 tests**. A domain with a real production
verification gateway may not be wired with the generic `PluginGateway` in *either* root.
Read over the parsed AST, not source text.

Validated by reintroducing the historical drift (filesystem wired generically in the
Founder Edition): **2 tests fail**; restored, all 12 pass.

The two roots are *not* required to become the same application — only to not silently
lose a verification adapter.

---

## 13–14. Browser and Desktop unchanged

Asserted structurally, not by inspection: `BrowserGateway.invoke` and
`FilesystemGateway.invoke` both go through their existing Worker's `run_step`;
`DesktopGateway` does not define `invoke` at all. No second registry, no second executor,
no second Worker, no resurrection of the old `DesktopObserver` as a primary path.

---

## 15. Wiring truth matrix

| Component | State |
|---|---|
| Founder Surface | **WIRED** |
| IntentLayer | **WIRED** |
| MissionService | **WIRED** |
| Planner | **WIRED** |
| Capability Index | **WIRED** |
| MissionControl | **WIRED** |
| Runtime | **WIRED** |
| Permission Gate | **WIRED** |
| Filesystem Execution | **WIRED** |
| Filesystem Verification | **PARTIAL** — 9/14 (queries excluded by design) |
| Browser Execution | **WIRED** |
| Browser Verification | **PARTIAL** — 4/9 (the Medium set) |
| Desktop Execution | **WIRED** |
| Desktop V2 Knowledge | **WIRED** — `intelligence/`, `app_knowledge_bridge`, `capture_evidence` |
| Desktop Interaction Layer | **WIRED** — `actions_interaction` backs the interaction capabilities |
| Desktop Verification | **PARTIAL** — 5/19 |
| Evidence → Mission State | **WIRED** — `dispatcher.task_completed` sets `task.evidence_id` |
| Evidence → Persistence | **WIRED** — `PlanRecord.verdict` / `.evidence_id`, `verified` = verdict is matched |
| Evidence → Reporter | **NOT WIRED** — the Founder sentence is composed from `state.result`; the code already says so: *"Naming the artifact a multi-step mission produced needs evidence the surface is not currently given"* |
| Mission → Persistence | **WIRED** |

---

## 16. Built-but-unwired vs actually-not-built

### BUILT BUT NOT FULLY WIRED

* **Fail-closed lifecycle** — implemented, deliberately deferred (§5, §11).
* **Evidence → Reporter** — Evidence reaches mission state and disk; the Founder-facing
  sentence does not read it.
* **Verification for the unsupported capability sets** — the *observation* primitives
  exist (`capture_evidence`, UIA reads); the expectation bindings do not.

### ACTUALLY NOT BUILT

* **Cross-step execution data provenance.** No contract exists for a later Step to consume
  an earlier Step's observed output. `Step.payload` is fixed at plan time; `depends_on`
  expresses order only; no reference, resolver or interpolation mechanism exists; and
  `ObserveBrowser`'s result is not retained anywhere. This is **not** a wiring gap — there
  is nothing to wire.
* **Outcome conformance (semantic QC)** — nothing compares the finished collection of
  Steps against the Founder's objective.

---

## 18. Regression — named sets against `dcb86e1`

**20 failures at baseline, 20 after, INTRODUCED = 0.**

One failure appeared mid-work and was corrected rather than accepted:
`test_filesystem_founder_path::test_it_is_wired_through_every_seam_the_runtime_needs`
asserted the literal source spelling `"register_gateway(filesystem_plugin"`. Reformatting
the call across lines to pass a *verifying* gateway broke it — the test failed on a change
that made the wiring strictly better. It now reads the parsed AST and asserts the real
property: filesystem is registered, with something that can verify.

The 20 pre-existing failures are the known set (`test_desktop_executive` ×5,
`test_desktop_shell` ×3, `test_founder_edition_assembly` ×4, `_boot` ×4,
`test_verified_execution` ×4 — the last being the known order-dependent suite).

---

## Required conclusions

| | |
|---|---|
| CURRENT DESKTOPPLUGIN PRESERVED | **YES** |
| CURRENT DESKTOPEXECUTOR PRESERVED | **YES** |
| CURRENT DESKTOPEXECUTIVEV2 PRESERVED | **YES** |
| CURRENT DESKTOP INTERACTION ACTIONS PRESERVED | **YES** |
| OLD DESKTOPLAYER/OBSERVER USED AS REPLACEMENT | **NO** *(required NO)* |
| CURRENT BROWSERPLUGIN PRESERVED | **YES** |
| CURRENT BROWSER EXECUTION PATH PRESERVED | **YES** |
| FILESYSTEM EXECUTION PATH PRESERVED | **YES** |
| FILESYSTEM CANONICAL VERIFICATION | **PARTIAL** — 9/14 |
| BROWSER CANONICAL VERIFICATION | **PARTIAL** — 4/9 |
| DESKTOP CANONICAL VERIFICATION | **PARTIAL** — 5/19 |
| GLOBAL FAIL-CLOSED SAFE TO ENABLE | **NO** |
| ALL BUILT PRODUCTION COMPONENTS WIRED INTO CANONICAL PATH | **NO** — Evidence → Reporter remains unwired |

### TRUE MISSING ARCHITECTURE AFTER WIRING

1. **Cross-step data provenance** — no contract for an observed value to reach a later
   Step. Nothing to wire; it does not exist.
2. **Outcome conformance** — no comparison of the finished mission against the objective.
3. **Evidence → Reporter** — built either side, not connected.
4. **Verification bindings** for the unsupported capability sets (queries, generic input).

---

**STOP.** Medium FMEA not started, per §17.
