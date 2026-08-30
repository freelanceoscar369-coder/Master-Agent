# CODEX demo convergence ledger

**Mission opened:** 30 August 2026  
**Mode:** engineering convergence with evidence; not an architectural redesign  
**Working branch:** `codex/demo-convergence`  
**Starting source:** `6349eb169239c489b54e9832767c41046aafed53`
(`origin/main` when the branch was cut)  
**Repository:** `D:\MasterAgent`

This ledger is append-only for the duration of the convergence mission. Claims
below distinguish source, package, product surface, environment, and evaluator
evidence. Pre-existing untracked files are Founder-owned and are not part of
this work.

## Gate 0 — independently established starting truth

- The checkout initially named `main` at
  `60dbaa0147b81bc8fae10e684d0fd7e2b4fe84dc`; live `origin/main` was
  `6349eb169239c489b54e9832767c41046aafed53`, 59 commits ahead.
- The convergence branch was cut directly from live `origin/main`; no merge of
  the stale local branch was used.
- The only local packaged executable found at the start was
  `D:\MasterAgent\dist\Kalpavriksha\Kalpavriksha.exe`, timestamp
  26 August 2026 13:50, size 36,901,260 bytes, SHA-256
  `49B8480F4714D4749C2CBD821F946AC51FB2B776BDF1B7A5AE608CD2A8A7A336`.
- That executable self-checked `OK`, identified itself as packaged, advertised
  46 capabilities, reported Browser/Desktop/Document/Filesystem/Reasoning
  executives reachable, and showed no Ollama construction or candidacy.
- Current repository evidence describes a later 48-capability package built
  from `9234319` with a different hash. That artefact is not present locally.
  Therefore the executable above does **not** establish current-source product
  readiness and must not be treated as the release candidate.
- Ollama processes exist in the host environment. Founder Edition's self-check
  reported Ollama neither constructed nor eligible. This mission will not
  enable or select Ollama.

## First adversarial failure — observed product behaviour

Package under test: the stale 46-capability executable identified above. State
was isolated under a test-specific directory and microphone input disabled.

Founder said:

> make a folder called KVST_A1_0830 on my desktop

The product asked:

> What should the folder be called?

The Founder replied:

> Call it KVST_A1_0830 and put it on the Desktop.

Fresh state records establish:

1. `founder_interactions.jsonl` retained the opening, question, and reply.
2. `events.jsonl` recorded `mission_understanding_started` and
   `mission_planning_started` with the clarification reply alone as the
   objective, rather than the original Founder objective plus accumulated
   evidence.
3. The Broker ledger ranked `chatgpt-desktop` first while the same package's
   self-check had reported the desktop reasoning tier unavailable. This is a
   separate routing-truth question; it is not yet established as the cause of
   the semantic failure.
4. No terminal completion was observed before the interactive run was stopped.
   There is therefore no proved false-completion result from this reproduction.

**First incorrect boundary in that package:** Intent parsing failed to extract
two explicitly supplied CreateFolder fields. The next boundary also failed:
the clarification round trip promoted the answer into a replacement objective
instead of preserving the original objective and accumulated evidence.

**Current-source status:** unadjudicated at ledger creation. The present source
contains later Intent/clarification/correspondence changes. The exact sentence
must be traced through the current semantic spine before any repair is made.

## Frozen independent holdout

The 28 objectives in
`scripts/live_acceptance/codex_holdout/cases.json` were frozen before the
current-source run and before any production repair. They are not the three
rehearsed golden paths. They cover:

- equivalent wording, punctuation, capitalization, and courtesy;
- multi-turn and multi-field clarification, nested destination, and ambiguity;
- wrong-parser pressure and compound objectives;
- local multi-step execution and reasoning-to-action Evidence binding;
- browser state, redirect, missing selector, cross-step runtime Evidence, and
  unreachable-page failure;
- pre-existing artefact, wrong-path, and partial-content false-completion traps;
- grounded system questions, follow-up semantics, Broker/provider truth,
  sensitivity, recovery, and same-session continuity.

No production phrase table may be derived from this holdout. Token substitution
is limited to disposable names and controlled fixture values documented beside
the cases.

## Active defects and gates

| ID | Severity | Boundary | Current evidence | Gate |
|---|---|---|---|---|
| CDX-001 | P0 candidate | Intent / clarification round trip in stale package | Explicit fields re-asked; reply became planning objective | Reproduce or falsify on current source |
| CDX-002 | P0 candidate | Release/package identity | Only local package predates current source and advertises 46 rather than 48 capabilities | Build and identify a fresh package after source gates pass |
| CDX-003 | P1 investigation | Broker availability truth | Stale package ranked a desktop provider that self-check called unavailable | Trace current eligibility and runtime availability evidence |
| CDX-004 | Known P1 | Browser lifecycle after failure | Existing repository evidence records a failed-mission session leak | Adversarially reproduce; repair only at lifecycle owner if current |
| CDX-005 | Known P1/P0 candidate | Verification absence handling | Existing repository evidence records an absent-Evidence fall-open path | Test false-completion family before release decision |

## Next evidence action

Drive the exact failed sentence and semantic variants through the current
production `IntentLayer`, record parsed fields, clarification state, semantic
requirements and planner admission, then run focused current tests. Only a
failure in current source authorizes a production repair.

## Gate 1 — current-source boundary proof and repair

### Before repair

The current production composition was built from source with all durable
mission state redirected to a disposable repository-local directory. The exact
Founder sentence was parsed as:

```text
text:           make a folder called KVST_A1_0830 on my desktop
clarification:  none
capability:     (generic)
payload:        {}
requirements:   []
```

Thus the later source no longer repeated the stale package's unnecessary
clarification, but it still failed at the canonical Intent boundary. An
end-to-end source mission then happened to produce the requested folder only
after **six** Broker decisions requested by the Planner. Fresh disk inspection
confirmed the right folder existed; that is a partial product success and an
Intent/efficiency defect, not a false completion.

Source trace found the exact mismatch:

- `IntentLayer._patterns` routes `"make a folder"` to
  `CreateFolderIntent`.
- All three structural expressions in `CreateFolderIntent` accepted only the
  verb `create`.
- `_may_claim()` therefore declined the typed result and the objective escaped
  as generic prose. The Planner and provider ladder were asked to rediscover a
  capability mapping that the Intent owner already claimed to know.

A red test family proved the boundary before production changed:

- fully specified `make` wording;
- polite prefix;
- case and terminal punctuation;
- missing name asks for the name;
- missing location asks for the location rather than inventing one.

The initial result was 4 failures and 82 passes in
`tests/test_intent_understanding.py`.

### Repair

`CreateFolderIntent` now owns one shared structural command grammar for the
existing `create` and `make` verbs. Its name-only, name-and-location and
location-only shapes derive from that grammar, preventing the registry/parser
drift that caused this defect. Ordinary `.`, `!`, and `?` terminal punctuation
is syntax rather than part of a Founder-supplied name or location.

No Planner, Broker, registry, MissionService, verification, or composition-root
logic changed. No holdout phrase table was added.

### After repair

- Focused Intent/clarification/correspondence family: **147 passed**.
- Broader semantic/surface/planner-admission/reporting family: **383 passed**
  after placing pytest temporary files in a sandbox-readable directory. The
  earlier eight setup errors were test-harness path errors, not product test
  failures; rerunning the affected files produced 27/27 passes.
- Exact end-to-end source mission with a new disposable name:
  - precondition: target absent;
  - capability: `Filesystem.CreateFolder`;
  - Planner model calls: **0** (previously 6);
  - fresh filesystem Evidence: all three path/existence/type checks matched;
  - independent disk inspection: target is a directory;
  - Founder report: all steps independently verified and Founder outcome
    conformance satisfied.

CDX-001 is closed for current source. It remains evidence that the pre-existing
local executable is stale and must not be demoed.

### Tooling notes

- An isolated `.venv-codex` was created for declared test/UI/browser/packaging
  dependencies. `numpy` and `tzdata` were needed to collect existing Windows
  Founder Edition tests; neither changes product configuration.
- Ruff reports three pre-existing findings in the two inspected files (import
  ordering, one duplicate set item, and one unused test unpack). None was
  introduced by this repair and none was changed opportunistically.
- The holdout checkpoint is committed locally as `7302f03`. Push was rejected
  by the host safety reviewer because the configured `origin` was not trusted
  for exporting the new holdout. No alternate export path was attempted.

## Next evidence action after Gate 1

Run the production Intent conformance acceptance, then exercise the frozen
holdout in risk order: false-completion traps, browser lifecycle/failure,
cross-step Evidence, Broker truth, and session continuity. Repair only a proved
current-source boundary; otherwise record a limitation.

## Gate 2 — frozen false-completion attack H20

The first risk-ordered holdout case exposed a current-source P0. A disposable
Desktop target named `KVH_FALSE_PREEXIST` was created before the mission and
contained a file named `OLD`. The Founder then said exactly:

> Create a new empty folder called KVH_FALSE_PREEXIST on my Desktop.

The current source selected `Filesystem.CreateFolder`. Execution returned
success because that action treated every existing directory as an idempotent
success. Fresh independent disk inspection after the mission showed the same
`OLD` file still present. Nevertheless Verification matched existence, path,
and directory type, and the Founder-facing report said:

> Work finished. All 1 executed step(s) were independently verified.

The durable plan record preserved “new empty” only in the prose description.
Its payload contained only `name` and `location`; its semantic requirements
were absent; its Evidence did not request a directory listing; and Founder
outcome conformance was `not_evaluated`. This is a proved **FALSE COMPLETION**,
not merely an unsupported feature.

### First divergence trace

1. The generic Intent preserved the complete Founder objective, so no words
   had yet been discarded.
2. `CreateFolderIntent` could not structurally recognise modifiers between the
   article and `folder`, and the substring trigger did not claim the sentence.
3. The AI Planner retained “new empty” only in an expected-outcome sentence,
   but emitted neither machine-readable semantic requirements nor capability
   inputs representing those constraints.
4. `CreateFolderAction` declared and implemented unconditional idempotent
   success for an existing directory.
5. Filesystem expectation binding checked only existence, exact relative path,
   and directory type. Directory listing was opt-in and the payload did not opt
   in, so the recorded observation's empty default was not an observation of
   emptiness.
6. `Reporter` treated a completed record with no semantic requirements as
   “Work finished” and added no warning that Founder outcome conformance had
   never been evaluated.

### Regression proof before repair

`tests/test_create_folder_new_empty_truth.py` was added before production
changes. It covers natural modifier order, nearby ordinary idempotency,
clarification, parser non-claim, published capability inputs, existing-target
preconditions, independent empty-directory observation, and the global
no-semantic-trace reporting rule. Initial result: **11 failed, 4 passed**.

| ID | Severity | Boundary | Current evidence | Gate |
|---|---|---|---|---|
| CDX-006 | P0 | Intent → capability → Verification → Reporter | Existing non-empty target survived; product claimed verified completion of a new empty folder | Repair at the four existing owners; rerun H20 and semantic/regression suites |

No holdout wording will be copied into a sentence table. The repair target is
the existing structural grammar and capability contract, plus truthful
verification/reporting defaults.

### Repair and end-to-end result

The repair stayed with existing owners:

- `CreateFolderIntent` now recognises structural `create|make` commands with
  ordinary `new`/`empty` modifier order and records those constraints in the
  typed payload and semantic requirements. A parser-owned recognition guard
  prevents unrelated folder sentences from being claimed.
- `CreateFolderAction` publishes `must_be_new` and `must_be_empty` as optional
  boolean contract inputs. The former refuses any pre-existing target; the
  latter refuses a non-empty existing directory. Plain creation remains
  idempotent for existing callers.
- Filesystem expectation binding adds complete-directory-listing checks when
  emptiness is required, and the gateway gathers that fresh observation
  automatically rather than depending on a Planner opt-in.
- `Reporter` now sends every record through the existing conservative
  conformance owner. Missing semantic trace is `UNKNOWN`, with an unconfirmed
  outcome title and explicit “can't confirm” language rather than “Work
  finished.”

Focused result after repair: **210 passed**. Neighboring Planner, Mission,
Founder runtime, structured-admission, gateway and architecture tests:
**487 passed**.

Fresh production-composition rerun of H20:

- precondition: target existed with listing `[OLD]`;
- capability selected: `Filesystem.CreateFolder`;
- action result: failed — target already exists and a new folder was required;
- Founder reply: “That didn't complete. I've kept the details for review.”;
- postcondition: target still existed with listing `[OLD]`;
- false completion: **none**.

The complementary absent-target case created a directory with a fresh observed
listing of `[]`, produced matched Evidence, assessed all five recorded
requirements as satisfied, and only then reported verified completion.

CDX-006 is closed for the proven path. Full holdout and regression remain
release gates.

## Gate 3 — neighboring semantic pressure and core-path regression

Frozen H21 began with a same-named directory in Documents and no Desktop
target. The Founder said `Create KVH_<stamp>_M on my Desktop.` The existing
generic `("create", CreateProjectIntent)` route claimed it and asked “What
should the project be called?” even though the name was already present and no
project had been requested. This was a semantic/wrong-parser defect, not a
false completion.

The local repair gives `CreateProjectIntent` a structural project/application
recognition guard. Unrelated create language now remains intact on the generic
planning route. The same existing CreateFolder structural parser was widened
for two ordinary grammatical forms already frozen before repair: “I need a
new folder” and a leading location (“On Desktop, I need a folder named: X”).
No exact objective or test-name table was introduced.

Red family: 3 failures, 15 passes. After repair: 140 focused Intent tests
passed. Rerunning H21 then created the exact absent Desktop target while the
similar Documents target remained; matched filesystem Evidence established the
exact path. Because the AI-planned generic mission still carried no semantic
requirements, the repaired Reporter correctly labeled Founder outcome
`UNKNOWN` and said it could not confirm satisfaction. This is safe but remains
a semantic-trace/autonomy limitation, not a release-quality success.

Frozen H22 replaced a disposable file's actual contents from `alpha wrong
omega` to exactly `alpha beta omega`. `Filesystem.WriteFile` produced matched
full-content digest Evidence; the surrounding FileExists/ReadFile query steps
have no domain Evidence, so the mission again reported outcome unconfirmed.
Actual state was correct and no false completion occurred.

Core-path regression after these changes:

- Golden local: **PASS**, 0.3 seconds, zero planning-provider calls, exact file
  contents and satisfied conformance.
- Golden ordinary Browser: **PASS**, 8.5 seconds, six dictated steps, fresh
  `#state == accepted`, fixture independently recorded the exact interaction,
  and session close was verified.
- Golden reasoning → file: **PASS**, 28.1 seconds, Gemini reasoning Evidence
  bound unchanged into an exactly verified three-line file, zero AI planning
  calls, satisfied conformance.
- Production Intent/clarification/grounded-question conformance: **16/16 PASS**
  with 48 registered capabilities.

No architecture was added. Active non-P0 limitation: AI-planned generic
missions do not yet carry the Intent owner's semantic requirements and Planner
coverage projection, so the safe Reporter returns `UNKNOWN` even when step
Evidence happens to match.

## Gate 4 — browser resource lifecycle expansion decision (before code)

Frozen H09 reproduced CDX-004 on the current source. A six-step Browser →
Reasoning → Filesystem plan failed when a downstream binding correctly refused
to trust a source with no canonical Evidence. Because the explicit
`CloseBrowserSession` step depended on the failed chain, it never became
runnable. `BrowserSessionManager.list_sessions()` then reported the live
`search_session`; the very next holdout mission would have inherited that
environment. This is a demonstrated same-process resource leak and a controlled
demo risk.

**Problem:** An Objective can own an external resource whose normal close step
becomes unreachable after failure. No current boundary tells its Executive that
the Objective is terminal and its remaining owned resources must be released.

**Existing owners inspected:** `MissionControl.Dispatcher` owns terminal state
but must not operate environments; `RuntimeEngine` observes execution terminal
transitions but must not know browsers; `BrowserSessionManager` owns browser
resources but does not know Objectives; `BrowserGateway` is the existing
Executive-specific seam between Runtime and the Browser environment.

**Why an existing owner cannot absorb it alone:** Mission Control/Runtime cannot
call browser APIs without violating Executive independence. The Browser manager
cannot infer mission termination. An explicit close Step cannot run once a
dependency fails. The responsibility therefore spans the already-existing
Runtime/Gateway seam.

**New responsibility:** When an Objective becomes terminal, Runtime offers its
assigned tasks to any gateway that implements optional objective finalization;
that gateway releases only resources identifiable as owned by those tasks.

**Canonical owner:** Runtime owns *when an Objective is terminal*;
`BrowserGateway` owns *how Browser resources for those tasks are released*.
There is no second lifecycle authority.

**Inputs:** Terminal Objective's existing task records (assigned Executive,
payload, and execution result).
**Outputs:** Best-effort release of matching live session IDs; no fabricated
task success or Evidence.
**State ownership:** Browser sessions remain solely in
`BrowserSessionManager`; Objective/task state remains solely in Mission Control.
**Authority:** Cleanup can only reverse resources the same Objective opened. It
cannot authenticate, navigate, execute a new capability, or close sessions
owned only by another Objective.

**Consumers:** `RuntimeEngine` calls the narrow optional gateway hook;
`BrowserGateway` consumes it. Gateways without mission-scoped resources remain
unchanged.

**Overlap analysis:** This does not add an orchestrator or cleanup service.
`CloseBrowserSession` remains the planned normal path; terminal finalization is
the failure-safe lifecycle path for the same manager-owned resource.

**Domino analysis:** Expected changes are limited to the generic gateway
lifecycle protocol, Runtime terminal handling, BrowserGateway finalization,
focused runtime/browser tests, and the holdout evidence runner. Planner, Brain,
Mission Control state machines, Broker, permissions and Verification do not
change.

**Rollback boundary:** Revert the optional hook and its two call sites; explicit
Browser close behavior remains exactly as before.

**Tests proving ownership:** A generic Runtime test must prove finalization is
called once with only the terminal Objective's tasks after success and failure;
a BrowserGateway test must prove it closes matching session IDs and preserves
an unrelated live session; H09 must leave zero sessions before H10 begins.

### Gate 4 result

The red test failed three assertions before the hook existed: Runtime never
offered terminal work for finalization after either success or failure, and the
Browser gateway had no mission-scoped release operation. After the repair:

- 69 Runtime/finalization/architecture tests pass in the restricted runner.
- 24 browser-dependent Runtime, Worker, lifecycle, and session tests pass when
  allowed to launch the repository's local Playwright Chromium. Their initial
  restricted-run failures were uniformly `BrowserType.launch: spawn EPERM`, not
  changed product verdicts.
- Frozen H09 still fails its requested web outcome truthfully at the Browser
  verification boundary, but `browser_sessions_after` is now `[]` before the
  evidence harness performs its own cleanup.
- An unrelated live Browser session is preserved by the focused gateway test.

CDX-004 is therefore closed on the reproduced same-process failure path. The
normal explicit `CloseBrowserSession` plan step remains unchanged; terminal
finalization is only its failure-safe resource lifecycle boundary.

## Gate 5 — combined clarification semantic handoff

Frozen H04 and H06 failed before this repair even though a direct
`IntentLayer.clarify()` could understand the same replies. The first incorrect
boundary was the Founder surface handoff:

1. `brain.utterance.structural_role()` classified referential continuations
   such as `call it ... and put it ...` as `MODIFY_OR_REDIRECT` merely because
   one clause opened with an operational verb.
2. `_submit_objective()` therefore abandoned the pending original objective
   and parsed the answer as a new objective.
3. Even on the answer branch, `PendingClarification` dropped
   `ClarificationQuestion.gathering`, so the existing multi-field extractor was
   reconstructed with only the currently asked key.

Eight focused regressions failed before code changed: four role/surface cases,
three complete-answer round trips, and the missing transport contract. The
repair stays with the existing owners: utterance grammar now distinguishes a
referential continuation (`put it`) from a new named object (`create a folder`),
and `PendingClarification` carries the Intent parser's existing `gathering`
tuple unchanged. No surface parser and no second semantic owner were added.

The Intent layer's existing whole-utterance accounting also now avoids a model
call when every founder word is already explained. It still invokes reasoning
for H06's narrower nested place because `KVH_PARENT_*` remains an unexplained
fact until extracted; it does not guess or discard it.

### Gate 5 result

- 226 role, clarification, correlation, provenance, and understanding tests
  pass.
- H04 now completes in 0.063 seconds with zero model/Broker calls, one
  `Filesystem.CreateFolder` step, matched Evidence, and `SATISFIED` outcome
  conformance. Independent state: Documents target exists and the Desktop
  namesake does not.
- H06 completes through the same typed capability with payload
  `{"name": "KVH_PARENT_132831/KVH_132831_F", "location": "d_drive"}`,
  matched Evidence and `SATISFIED` conformance. Independent state confirms the
  exact empty directory at `D:\KVH_PARENT_132831\KVH_132831_F`.

CDX-005 (combined clarification discarded as redirect) is closed on both the
ordinary and nested-location frozen paths.

## Gate 6 — unresolved Founder-owned location

Frozen H08 exposed a dangerous admission path. The folder parser recognised
the command but treated `where I normally keep these` as part of an unreadable
long tail, so its conservative claim guard sent the whole sentence to generic
planning. The resulting AI plan attempted to use reasoning to choose a place
only the Founder could know. Execution happened to be blocked by provider
eligibility, but a successful model response could have turned missing Founder
meaning into an environmental action.

The Intent owner now recognises the grammatical boundary `named <name> where
...` as partial understanding: the folder name is known, location is not. Its
existing claim guard accepts that explicitly resolved field and the ordinary
clarification path asks for location. It does not interpret the personal
reference, select a location, or consult the Planner.

### Gate 6 result

- Two regressions failed before the repair and 228 neighboring Intent and
  clarification tests pass afterward.
- Frozen H08 returns `AWAITING_CLARIFICATION` immediately with `Where should I
  create the KVH_174028_G folder?`.
- Zero Planner steps, zero Broker/model decisions, zero browser sessions, and
  neither Desktop nor Documents target exists.

CDX-006 (generic planning invited to guess an unresolved location) is closed.
