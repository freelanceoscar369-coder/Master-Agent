# 30 August 2026 — demo evidence pack

Every number here was read from a record: the Broker's decision ledger,
Mission Control's task Evidence, the disk, or the fixture's own server.
Nothing is estimated and nothing is reconstructed from a transcript.

The runner that produces all of it:

```
python scripts/live_acceptance/demo_30aug_battery.py
```

---

## Identity

```
source branch     claude/founder-browser-identity
source HEAD       f5f0a4b468f44c2d20e4110abc641e84102d6db4
package           dist/Kalpavriksha/Kalpavriksha.exe
built             2026-08-27T16:16:55
sha256            0cdb11d02d16861919a4caddcfc0efd715b1a6403d4f1ed0ce1264e802251cb8

self-check        RESULT: OK
  packaged        True
  capabilities    48
  executives      browser, desktop, document, filesystem, reasoning
                  all five runtime-reachable
  reasoning tiers local (empty) · desktop (4 apps) · gemini (gemini.api,
                  openrouter.api) · browser (trusted-founder-web)
  no-ollama       constructed=no, candidate=no
  browser.free-ai known=yes, executable=no        (Founder Edition AI-web lane)
  trusted-founder-web  known=yes, executable=yes, available=yes
  FMEA scope      UNSET — the full production ladder is shown
```

**How "AI planning calls" is counted.** Not by instrumentation. The
Broker records a `requester` for every selection it makes, so a planning
call is a ledger entry whose requester is the Planner. The number comes
from the same record an auditor would read.

---

## Golden path 1 — LOCAL

```
OBJECTIVE            Create a folder called KalpavrikshaDemoProof_<stamp> on the
                     Desktop. Then write it into proof.txt inside that folder.
                     The text should be: Kalpavriksha demo ready
PLANNING MODE        deterministic
AI PLANNING CALLS    0
CAPABILITIES         Filesystem.CreateFolder → Filesystem.WriteFile
EVIDENCE             CreateFolder: matched · WriteFile: matched
DURATION             0.3 s
INDEPENDENT READ     folder present on disk
                     proof.txt present, contents exactly "Kalpavriksha demo ready"
OUTCOME              PASS
```

Two steps, both consequential, both verified by re-reading the disk
rather than by trusting what the Executive reported.

---

## Golden path 2 — ORDINARY BROWSER (Playwright, deliberately)

```
OBJECTIVE            Open a browser session and navigate to
                     http://127.0.0.1:<port>/acceptance.html. Type the text
                     acceptance into the element matching #acceptance-box, click
                     the element matching #apply, observe the page and tell me
                     the current text shown by #state, then close the browser
                     session.
BROWSER ENVIRONMENT  Playwright — the ordinary Browser lane
FIXTURE              loopback only, 127.0.0.1, ephemeral port
                     page sha256 6519d75bfc0f6b22c770dce0c04ffa6ad332e404053a2ba9c97adc39d1a235b4
PLANNING MODE        deterministic
AI PLANNING CALLS    0
CAPABILITIES         Browser.OpenBrowserSession → Navigate → TypeText → Click
                     → ObserveBrowser(selectors=["#state"]) → CloseBrowserSession
EVIDENCE             OpenBrowserSession  matched
                     Navigate           matched
                     TypeText           none   ← delivery only, by design
                     Click              none   ← delivery only, by design
                     ObserveBrowser     matched
                     CloseBrowserSession matched
FINAL OBSERVATION    elements[0].selector == "#state"
                     elements[0].text     == "accepted"     (fresh re-read)
FOUNDER RESULT       "accepted" — then the verification summary
FIXTURE SERVER       {"state": "accepted", "typed": "acceptance", "applied": 1}
SESSION CLOSED       verified by absence, verdict matched
DURATION             2.5 s
OUTCOME              PASS
```

**On the two `none` verdicts.** `Browser.TypeText` and `Browser.Click`
are **delivery** actions. A page may accept typed input and then reject
it; a click may land and change nothing. No outcome verifier was
invented for them, because inventing one would make execution success
equal mission success. The observation that follows owns the page
effect — and it is that observation, re-read from scratch, which reports
`accepted`.

**On the independent read.** The fixture's server records the outcome, so
`GET /state` answers after every browser has exited. Reading the result
through the browser the mission drove would be the test agreeing with
itself.

---

## Golden path 3 — REASONING + REAL ACTION

```
OBJECTIVE            Think of exactly three short names for a gardening notes app
                     and write them one per line into demo_names_<stamp>.txt on
                     the Desktop.
PLANNING MODE        deterministic
AI PLANNING CALLS    0
AI REASONING CALLS   1, inside Reasoning.Transform
EXECUTION PROVIDER   gemini.api      (Broker's decision, recorded on the ledger)
CAPABILITIES         Reasoning.Transform → Filesystem.WriteFile
TEXT VERDICT         matched  (TextVerifier)
VERIFIED TEXT        Sprout / Leaflet / Bloom
BOUND EVIDENCE       WriteFile.content bound from the verified Evidence,
                     not predicted by the Planner
FILE                 ~/Desktop/demo_names_<stamp>.txt
FILE CONTENTS        Sprout / Leaflet / Bloom   (three lines)
FILE VERDICT         matched
DURATION             9.3 s
OUTCOME              PASS
```

The file holds **exactly** the text that passed verification. The Planner
never sees the names and never predicts them; the binding refuses a
source that carries no canonical Evidence, which is what makes that
guarantee structural rather than hoped for.

---

## Trusted Web lane

**Not re-run this sprint, and the reason is checkable.** Every file in
that lane is byte-identical to the previous closure:

```
git diff --name-only b4a9cfe HEAD -- \
    src/master_agent/providers/trusted_web_ai.py \
    src/master_agent/trusted_browser.py \
    src/master_agent/desktop/trusted_browser_adapter.py
→ (empty)
```

Its live two-turn proof — real authenticated browser, the `Kalpavriksha`
conversation reused, current-turn response ownership, TextVerifier
matched — stands in `DESKTOP_BROWSER_FINAL_CLOSURE.md`.

What this sprint adds is enforcement rather than repetition:
`tests/test_browser_lane_separation.py` now makes it structurally
impossible for that lane to reach Playwright, or for the ordinary lane to
reach it.

---

## Truthful external failure — a search engine's bot detection

Recorded because it is good behaviour, not because it is a defect.

```
MISSION              9f68a556-1931-46a9-b5ba-89a80b0d9c0a   (27 Aug, 09:10:37Z)
OBJECTIVE            find latest action rpg games and share free demo links
                     for download
PLANNED BY           the AI Planner — correctly: nothing about this was dictated
PLAN                 OpenBrowserSession → Navigate → ReadPageText →
                     Reasoning.Transform → CloseBrowserSession → WriteDocument
step_1               OpenBrowserSession   VERIFIED matched
step_2               Navigate             VERIFIED not_matched → mission failed

REQUESTED URL        …/search?q=latest+action+rpg+games+free+demo+download
OBSERVED URL         …/sorry/index?continue=…%3Fq%3Dlatest%2Baction%2Brpg…
                     (the site's anti-bot interstitial)

DOWNSTREAM WORK      none — the page was never read
FABRICATED RESEARCH  none
DOCUMENT WRITTEN     none
CAPTCHA              not solved, not attempted, not stored
LANE CHANGE          none — the founder's authenticated browser was not touched
```

**Verdict: TRUTHFUL FAILURE / EXTERNAL AUTOMATION LIMITATION.** Not a
Browser architecture failure. The mission asked to go somewhere, landed
somewhere else, and said so.

**One detail worth keeping.** The navigation check is `equals` on a
normalised URL rather than `contains`. The interstitial's URL carries the
*entire* intended search URL inside its `continue=` parameter, so a
substring test would have **passed on the challenge page** — and the
mission would have gone on to read it, reason over it, and write a
document about it. The stricter check was chosen for a different reason
than the one that saved it here, and
`tests/test_browser_lane_separation.py` now pins it.

---

## Known debt, stated rather than hidden

**Failed-mission browser session.** When a Browser mission fails before
`CloseBrowserSession`, the close step never runs and the Playwright
session survives until the process exits. Seen twice (26 and 27 Aug).
Not a demo blocker — each mission uses its own `kv-<hex>` session id and
the battery runs three missions in one process without interference.
Classified post-demo runtime environment-lifecycle debt.

**Absent-Evidence fall-open.** `runtime/engine.py` completes a task when
verification returns no Evidence, recording
`{"verdict": null, "evidence_id": null, "verifier": "none"}` honestly
before proceeding. Its own comment states the intended end state and why
it is not enabled yet. Every consequential outcome on the demo paths
terminates in canonical Verification; the two `none` verdicts in golden
path 2 are the deliberate delivery-only actions described above, not this
debt in disguise.


---

## Late defect, found by the founder during acceptance

The most basic interaction there is, and it failed.

```
10:36:38  founder   create a folder
          somesh    What should the folder be called?          clarification
10:36:50  founder   Abhishek
          somesh    Where should I create the Abhishek folder?  clarification
10:37:00  founder   on desktop
10:37:00  retry 1 of 3   unknown location 'on desktop'
                         (known: d_drive, desktop, documents, downloads)
10:37:01  retry 2 of 3   same
10:37:01  escalated      same
10:37:01  task_failed → objective_failed
          somesh    "That didn't complete. I've kept the details for review."
```

**Boundary.** `CreateFolderIntent.parse()` — `location = self._answer(
supplied, "location")`. Every inline pattern in that class strips
`(?:on|in)\s+(?:my\s+|the\s+)?`, which is why the dictated form has
always worked. A clarification answer never goes through a pattern, so
the founder's words reached the capability verbatim. Two paths into one
capability, two ideas of what a place is.

**Fixed** by normalising the grammar and only the grammar. The Brain does
not acquire the capability's vocabulary; an unknown place still travels
on and the capability answers for itself.

**Second defect, same failure.** The founder-facing sentence flattened an
actionable validation error to "That didn't complete". It now repeats the
capability's own list back, read out of the error rather than written
into the surface.

**Third finding, recorded not fixed.** A deterministic argument-validation
error was retried three times before escalating. Retrying something that
can never succeed is wasted work and delays the founder's answer.
Post-demo: retry policy should distinguish a transient failure from a
rejected argument.

**What worked in the same exchange.** The founder then asked *"whats the
challange?"* and was correctly answered as a FOLLOW_UP — because by then
a real mission stood behind the question. The morning's P0 fix, working
from the other side.


---

## Night session, 27 Aug — semantic spine, packaged

```
SOURCE HEAD    e240ec41251582e64f9ed555d59dcee2cba1e082
PACKAGE        dist/Kalpavriksha/Kalpavriksha.exe
BUILT          2026-08-27T23:36:56
SHA256         f6d850619cb95e1f5be219ca7d424843e88261213d366334500c80a8796da4df
SELF-CHECK     RESULT OK - 48 capabilities - 5 executives, all runtime-reachable
NO-OLLAMA      constructed=no, candidate=no
FMEA           UNSET (full production ladder shown)

FULL SUITE     75 failed - 8387 passed - 2 skipped
BASELINE       90 failed (b4a9cfe)
NEW REGRESSIONS ZERO, diffed by test ID
```

The two clipboard tests that failed last night pass now — confirming they
were environmental (the Windows clipboard was held by another process),
exactly as recorded.

### Golden paths, with conformance

All three now carry the semantic spine end to end:

```
GP1 LOCAL      PASS 0.4s   founder outcome: satisfied
GP2 BROWSER    PASS 3.1s   founder outcome: satisfied   (Playwright, deliberate)
GP3 REASONING  PASS 12.3s  founder outcome: satisfied
INTENT CONFORMANCE  PASS   10/10 against the production composition
```

### Grounded self-query — rehearsed before it was offered

Three questions were run against the real composition before being put in
front of the founder. Two failures were found and fixed that way:

**A provider was being asked what the records already knew.** *"What can
you do right now?"* built a `Reasoning.Transform` mission with the last
mission attached as grounding; that action defaults to `sensitive=True`,
correctly, so the Broker found no PRIVATE-locality provider and the
question failed. None of these questions needed a provider —
`brain/self_query.py` answers them from records.

**Coverage without requirements.** The one-step and capture lanes set
`Step.covers` but never published the requirements onto the plan, so
conformance reported "no recorded founder requirements" for missions that
had them. Caught only because the rehearsal read real stored history.

Answers now, from records:

```
what can you do right now?
  → 48 capabilities across 5 areas, by area, from the live index

why did you choose that capability?
  → the rationale recorded at PLANNING time, naming the requirement,
    the registered description and the argument contract

did the last mission satisfy what I asked for?
  → Yes/No/can't-say from requirements + coverage + Evidence,
    per requirement, with UNKNOWN never rounded up
```

"The last mission" excludes missions that were themselves questions —
by requirement marker, and for the hundred legacy records predating the
semantic trace, by shape.

---

# PACKAGE IDENTITY — 28 AUG 2026, 02:21

The build the semantic acceptance should be run against.

```
source        4e5b00e  (branch claude/founder-browser-identity)
artefact      dist/Kalpavriksha/Kalpavriksha.exe
sha256        b2bdadf05d1683a04a10f9fcf518d0d1c3a4f4e1d971fabbe0bcf8b76a211769
size          37,020,448 bytes
built         2026-08-28 02:21
supersedes    9d984a5bf02ae60d42d93ca91c45326759019027b5b8d768a110b31a39efede2 (01:39)
```

The hash is recorded because a PyInstaller build that fails on a locked
file **leaves the previous executable in place and still exits 0**. The
artefact is the evidence; the exit code is not. This one genuinely
changed.

## Packaged self-check

```
packaged: True
capabilities registered: 48
executives:              browser, desktop, document, filesystem, reasoning
runtime-reachable:       browser, desktop, document, filesystem, reasoning
approval wired:          True
no-ollama:               constructed=no, candidate=no
deterministic planning:  Filesystem.CreateFolder -> Filesystem.WriteFile
founder checkpoint:      True
RESULT: OK
```

Providers usable at build time: `gemini.api`, `openrouter.api`,
`trusted-founder-web`. Everything else is known and honestly reported as
not currently available — which is the distinction the grounded
self-query answers with, rather than naming a provider it cannot run.

## Full suite — clean run, settled tree

```
77 failed · 8431 passed · 2 skipped   (21m38s)
baseline   75 failed · 8415 passed · 2 skipped
```

Reconciled exactly:

```
8415 + 18 new tests - 2 environmental = 8431 passed
  75 +  2 environmental               =   77 failed
```

**New failure IDs attributable to this work: zero.**

The two new IDs are both `test_win32_clipboard_backend.py::
TestWin32ClipboardBackendLive`, failing with `BackendUnavailable: could
not open the clipboard` — another process on this machine is holding the
Windows clipboard lock. Not asserted, proved: a clean worktree at the
baseline commit `a50e5e2` fails **both, identically**. The only source
file changed across this work is `brain/intent.py`, which contains no
clipboard reference.

### A false regression, and why the run was repeated

An earlier full run reported 76 vs 75 and named
`TestThisIsNotAFolderPatch::test_all_three_families_share_one_implementation`
— an architecture guard that passes in isolation.

It failed because **I edited `intent.py` while that run was in flight**.
The guard reads source through `inspect.getsource`, which loads from disk
at test time; shifting line offsets under an already-imported module made
it read the wrong slice. A 27-minute failure-ID diff is only evidence if
the tree did not move during it, so the run was discarded and repeated on
a frozen tree rather than argued about.

Note it was again an architecture guard, not a unit test, that surfaced
the anomaly — the same class of test as in Engineering Rule 001, and for
a related reason: both read the filesystem rather than the imported
object.

## What this build was NOT proved against

Stated because a boundary left unstated reads as coverage:

- The packaged executable was exercised by `--self-check` (wiring,
  registry, provider facts, deterministic planning) and by nothing else.
  The semantic behaviour was proved against the same source the exe
  bundles, through the real pipeline, not through the frozen binary.
- The three live acceptances below ran from source.


---

# FINAL — 28 AUG 2026, 09:57

Re-adjudicated against source rather than against my own summary, which
changed two answers.

## Two gaps the re-audit found

**A stated invariant nothing enforced.** `SemanticRequirement` carried
the comment *"UNCERTAIN may never reach execution"*, and no code checked
it. Conformance refused to REPORT satisfaction for an uncertain
requirement — that closes the back door and leaves the front one open. A
plan carrying one would still have run, and the founder would have been
told about real work done on a reading the system did not stand behind.

Now enforced in `MissionService._admit`, which ADR-0024 Decision 1
already makes the single admission boundary to the Planner, so this is
one policy and not a second to drift from the first. The refusal quotes
the founder's own sentence back — nobody can resolve "something was
unclear".

**A contract that contradicted itself.** `CreateFolderAction.description`
— the line the Planner reads to fill arguments — said `name` is *"the
folder's own name only"*. The code says otherwise, deliberately.

## Nested destination — source classification

**ALREADY EXPRESSIBLE.** Exact contract evidence, at HEAD:

- `executor/action.py::is_unsafe_relative_path` docstring: shared by
  every action accepting *"a relative path/name meant to be joined onto
  a configured location's base directory (**CreateFolderAction's
  `name`**, WriteFileAction's `path`, …)"*. The argument is named, by
  the guard that defines its safety.
- `actions/create_folder.py::validate()` admits multi-segment values,
  with a comment recording that the guard was closed here for a *direct*
  caller too, not only composite ones.
- `actions/create_folder.py::run()`: `target = base / name` then
  `mkdir(parents=True)`. `parents=True` is a no-op unless `name` may
  carry more than one segment — it is positive evidence of intent, not
  an accident.
- Safety unchanged: `..`, absolute, and drive-anchored values are
  rejected identically on both path flavours.

So this is not an implementation accident being promoted to
architecture. The **description** was the thing out of step, and it was
telling the Planner the opposite of what the code accepts — refusing a
founder a target the capability can already reach safely. Corrected to
state the real rule, which was always about a LOCATION phrase; the
original defect it guarded (`name="Research on my Desktop"`) stays closed
and is pinned by test.

Idempotency untouched: `expected_result` still declares it.

## Full suite — clean run, frozen tree

```
75 failed · 8440 passed · 2 skipped   (24m39s)
baseline   75 failed · 8415 passed · 2 skipped
```

```
NEW FAILURE IDS: ZERO   (the ID sets are identical)
8415 + 25 new tests = 8440 passed
```

The two live-clipboard failures seen in the previous run are gone. They
were environmental, as reported — a stale `comtypes` generated typelib
was also blocking desktop-pipeline construction, and clearing that
regenerated cache resolved both. No product code was involved.

## Package

```
source        e7c1f04
sha256        fddf70b9535d9121889ddc442b9580d94ff3571faaaefcffcb3b5c7895481b91
size          37,021,681 bytes
built         2026-08-28 09:32
supersedes    b2bdadf0…
self-check    RESULT: OK · 48 capabilities · all five executives reachable
              approval wired · no-ollama constructed=no candidate=no
              deterministic planning: CreateFolder -> WriteFile
FMEA tier     unset
instances     none running
```


---

# DEMO ENGINEERING — AUTOMATED REHEARSAL, 28 AUG 2026

Founder acceptance is deliberately NOT part of this. Every class the
founder will exercise is proved first, by machine, against the real
production composition, so the founder's run is a demonstration and not
a debugging session.

## Feature branch

```
branch   claude/founder-browser-identity
HEAD     7779ae0
remote   pushed; origin HEAD == local HEAD
```

## The sixteen classes — INTENT CONFORMANCE: PASS

| Class | Case | Proof |
|---|---|---|
| A | DIRECT / MULTI-TURN / MULTI-FIELD / CORRECTION | real reasoner, real vocabulary |
| A | CONTEXT — a place-word used as a NAME | "Desktop" as a name, not a place |
| A | ANOTHER FAMILY — list files / project name | not a folder patch |
| B | NESTED DESTINATION | `name=Onkar/KVNest_…`, `location=d_drive` |
| C | UNCERTAIN admission gate | real `MissionService`, refused |
| D | AI candidate legal-but-incomplete | `{"location":"d_drive"}` refused |
| E | Founder evidence survives | every requirement carries the words |
| F | Plan coverage | requirements covered, rationale recorded |
| G | false-SATISFIED regression | conformance cannot self-certify |
| H | fresh-state guard | precondition observed before the run |
| I | "What can you do right now?" | 48 capabilities across 5 areas |
| J | "Why did you choose that capability?" | rationale recorded at planning time |
| K | "Did verified reality satisfy it?" | per requirement, from Evidence |

Two boundaries stated rather than glossed:

- **B is resolution-only.** Executing it would create a real folder
  inside the founder's own `D:\Onkar`. Proving the system UNDERSTANDS
  the destination is the point; creating founder data to prove it is not
  mine to decide. The capability half is proved against the Action
  contract in `test_semantic_correspondence.py`.
- **D cannot use the real model**, because it requires a specific wrong
  answer on demand. The production layer keeps its own vocabulary and
  only the reasoning door is replaced — fed the exact answer the
  production model gave on the night it failed.

## Gates

```
GP1 — LOCAL                          PASS  0.6s
GP2 — ORDINARY BROWSER (Playwright)  PASS  4.6s
GP3 — REASONING + FILE               PASS  29.4s

FULL SUITE   75 failed · 8440 passed · 2 skipped   (34m08s)
BASELINE     75 failed · 8415 passed · 2 skipped
NEW FAILURE IDS: ZERO — the failure-ID sets are IDENTICAL
                 8415 + 25 new tests = 8440
```

## Known inherited failures (75, unchanged)

Pre-existing at the baseline commit and untouched by this work. The
largest clusters: `test_missions_console.py` (27 —
`FounderConsole.__init__()` signature drift), `test_ollama_provider.py`,
`test_brain_non_execution_routing.py`. None are semantic-spine.

## Known external limitations

- Steam `Navigate` 5s timeout — **browser policy finding**, not a defect.
- `ctreate` — **language robustness finding**. No fuzzy matching.
- Public search (Google) deliberately off the critical path: it serves an
  anti-bot interstitial to automation.
- Live Windows-clipboard tests depend on no other process holding the
  clipboard lock, and on a current `comtypes` generated typelib.

## Known post-demo debt

- Requirements extracted from a compound objective by reasoning carry the
  objective as provenance, not per-clause founder wording — a coarser
  audit trail than the folder family. Never a false SATISFIED.
- Legacy records predating the semantic trace carry no requirements;
  `assess()` returns UNKNOWN, which is correct and never rounded up.
- A browser left open after a failed mission must be closed by hand.


---

# CANONICAL MAIN AND THE FINAL ARTEFACT — 28 AUG 2026

## Convergence

```
before        origin/main 60dbaa0
merge base    60dbaa0  (origin/main was an ancestor of HEAD)
integration   fast-forward push, HEAD -> main
after         origin/main 9234319
```

No force, no rewrite, no reset, no discarded history.

## Canonical-main proof — from a CLEAN CHECKOUT of 9234319

Per Engineering Rule 001, run in a fresh worktree at the tag, not in the
working directory:

```
semantic spine · intent/parser · admission guard · false-SATISFIED
· grounded self-query · CreateFolder action contract
                                        282 passed

INTENT CONFORMANCE                      PASS  (16 classes)
GP1 — LOCAL                             PASS  0.6s
GP2 — ORDINARY BROWSER (Playwright)     PASS  4.4s
GP3 — REASONING + FILE                  PASS  19.3s
self-check (source path)                RESULT: OK
```

## Final package

```
built from    9234319   (worktree clean, HEAD == origin/main)
path          dist/Kalpavriksha/Kalpavriksha.exe
sha256        2612de996023b6988969f51695198de5c65c40e6d3a8812bfa266b1a2e6745b8
size          37,021,681 bytes
built         2026-08-28 10:51
```

`build/` and `dist/` were deleted first, so no stale artefact could
survive a locked-file failure — the trap that leaves the OLD executable
in place while still exiting 0.

### Source/package identity — PROVEN, not assumed

This machine has an editable install pointing `master_agent` at
`D:\MasterAgent\src`, which is the PRIMARY worktree and still sits at
the OLD main. Import resolution with no `PYTHONPATH` goes there. The
spec's `pathex` should win, but "should" is not evidence.

Proved by extracting the bundled `PYZ.pyz` from the executable and
reading the code constants of the modules that changed:

```
master_agent.planner.plan                    FOUND 'unsettled_interpretation'
master_agent.executor.actions.create_folder  FOUND 'may be a relative path under'
```

Neither string exists at old main `60dbaa0` (verified with `git show`).
The package therefore carries the canonical source and not the editable
install.

### Packaged smoke

```
packaged: True                RESULT: OK
capabilities registered: 48
executives / runtime-reachable: browser, desktop, document, filesystem, reasoning
approval wired: True          founder checkpoint: True
no-ollama: constructed=no, candidate=no
deterministic planning: Filesystem.CreateFolder -> Filesystem.WriteFile
FMEA tier: UNSET
providers available: gemini.api, openrouter.api, trusted-founder-web
                     (everything else honestly reported not available)
```

GP1/GP2/GP3 exercise the composition from source at this same SHA; the
packaged runtime is proved by `--self-check` and by the PYZ identity
above. The executable exposes no objective-run flag, so that is the
boundary — stated rather than blurred.

## Final machine state

One canonical Founder Edition instance running, PID 18632, from the
final package, window up and responding. A duplicate launched moments
earlier was stopped. No founder Chrome or Comet was touched (none were
open). Persistence, Evidence, founder memory and the Provider Registry
are untouched.

## A note on SHA ordering

The artefact was built from `9234319`. This ledger entry is committed
after it, so final main is one commit later. That delta is documentation
only:

```
git diff --stat 9234319..HEAD -- src/ kalpavriksha_desktop.py packaging/
  (empty)
```

The package's source identity is unchanged; only prose moved. Recorded
plainly rather than presented as exact SHA equality it does not have.

---

# FOUNDER ACCEPTANCE FAILURE — LIVE WEB RESEARCH / DECISION INTELLIGENCE

**28 August 2026.** Founder acceptance of the frozen candidate FAILED.

```
SOURCE   6349eb169239c489b54e9832767c41046aafed53
PACKAGE  2612de996023b6988969f51695198de5c65c40e6d3a8812bfa266b1a2e6745b8
```

Founder's natural request:

> search for action rpg games released in 2026 and give me free demo
> download links

Founder-facing result:

> "That didn't complete."

Records preserved verbatim in
`docs/audits/evidence/founder_acceptance_20260828/failed_research_missions.json`
(four plan records of this objective class, including both acceptance
attempts). Nothing was deleted.

## Where correct evidence stopped

```
plan_id     e6c09799-4a9a-4cb8-93a1-8c3ce8aacc9c   (history entry 12)
planned_at  2026-08-28T05:37:42Z
finished    2026-08-28T05:37:43Z      <- 1.3 seconds
planned_by  openrouter.api            state: failed
```

**LAST CORRECT BOUNDARY** — Planning. The ladder walked local (skipped),
desktop (11 considered, none eligible), then `openrouter.api`, which
returned a coherent 10-step plan: open a browser session, navigate and
read three sources, reason over them, write a document, close the
session.

**FIRST BROKEN BOUNDARY** — `step_1: Browser.OpenBrowserSession`

```
failed to open browser session: cannot switch to a different thread
(which happens to have exited)
```

Every one of the nine downstream steps stayed `pending`. Then:

```
task_failed step_1 {'executive_id': 'browser'}
objective_failed
```

**This was not a website.** Not a Steam timeout, not a Google
interstitial, not a research-quality problem. It is a thread-affinity
failure opening the isolated Playwright session inside the packaged
desktop app — the sync API being driven from a thread other than the one
that owns it. The mission never reached the web at all.

The earlier attempt in the same class (entry 138) got one step further
and died the same way in shape: `step_2 Browser.Navigate` verified
`not_matched`, `task_failed`, `objective_failed`.

## Three findings, in order of what they cost

**1. One step failed and the objective failed.** No recovery, no
re-plan, no alternative source. `task_failed` is followed immediately by
`objective_failed` in both attempts. A method failure was treated as an
objective failure — the founder was told the request could not be done
when it had never been attempted.

**2. The semantic spine does not reach this lane.** The plan's
`requirements` list is **empty** and every step carries `covers=[]`.
Everything built for the folder family — founder evidence beside the
interpretation, coverage, outcome conformance — is absent on an
AI-planned research objective. Even had the browser worked, the mission
could only have reported UNKNOWN, because there was nothing to conform
against. This is a real limit of the previous milestone that its own
acceptance did not expose, and it is recorded here rather than softened:
the semantic guarantees proved in the last section hold for the
deterministic lanes, not for AI-planned research.

**3. Ordinary live-web research ran through the isolated automation
lane** rather than the trusted ordinary browser, which is the product
decision the founder has now made explicit.

## Why this is not being repaired narrowly

Fixing the thread affinity would have made this mission run. It would
not have made the answer intelligent, would not have produced
requirements to conform against, and would not have stopped the next
failed source from ending the objective. The founder's direction
supersedes the narrow repair.

Audit time-boxed to 20 minutes, as instructed.

---

# 29 August 2026 — final delivery strike

## Identity

```
branch              claude/brain-wisdom
final feature SHA   19ac803
origin/main         6349eb1   (untouched)
ahead / behind      42 ahead, 0 behind
status              clean

package             dist/Kalpavriksha/Kalpavriksha.exe
built from          19ac803
sha256              a1a6fa64c6d817d4b593208b3528ed02c4a423c2e613a0a5411b4f17500db5fb
size                37,079,471 bytes
built               2026-08-29 14:36:50 +0530
```

`build/` and `dist/` were deleted before building, and no Kalpavriksha
process was running — the trap that leaves the OLD executable in place
while still exiting 0.

## Source/package identity — proven, not assumed

This machine has an editable install pointing `master_agent` at
`D:\MasterAgent\src`, the PRIMARY worktree, still at old main. Import
resolution with no `PYTHONPATH` goes there. The spec's `pathex` should
win; "should" is not evidence.

The bundled archive was extracted and read:

```
master_agent.plugins.browser_observation    FOUND 'read_visible_text'
master_agent.brain.deliberation             FOUND 'OBSERVATIONS. Each has a label you must cite exactly:'
master_agent.providers.reasoning_session    FOUND 'SESSION_SATURATED'
master_agent.providers.desktop_app          FOUND 'ONLY_INTERFACE_TEXT'
master_agent.runtime.sensitivity            FOUND 'sensitive work may not go'
```

None of those strings exists at `6349eb1`. The package carries this
branch.

A note on the probe itself, because it was wrong first: it compared
whole code constants for membership, so `f"source_{index}"` — which
compiles to the fragment `"source_"` — was reported ABSENT for a module
that was plainly present. Substring matching over the fragments is the
correct question. A verification tool that can report a false negative
is worth recording, not quietly fixing.

## Packaged self-check

```
packaged: True                     RESULT: OK
capabilities registered: 48
executives / runtime-reachable: browser, desktop, document, filesystem, reasoning
reasoning tier local     (empty)
reasoning tier desktop   chatgpt-desktop, claude-desktop, kimi-desktop, perplexity-desktop
reasoning tier gemini    gemini.api, openrouter.api
reasoning tier browser   trusted-founder-web
approval wired: True               founder checkpoint: True
no-ollama: constructed=no, candidate=no
deterministic planning: Filesystem.CreateFolder -> Filesystem.WriteFile
FMEA tier: UNSET (no KALPAVRIKSHA* variable set in the environment)
providers available: gemini.api, openrouter.api, trusted-founder-web
                     (everything else honestly reported not available)
```

The executable exposes no objective-run flag. Objective-level proofs
therefore run against the composition from source at this same SHA, and
the packaged runtime is proved by `--self-check` and the archive
identity above. That is the boundary, stated rather than blurred.

## H — one live objective against reality nobody arranged

Not a game. Not the reading rooms. Not a site this work had already been
made to succeed against.

```
objective   Which of these three cities has a metro system that opened
            before 1930 and is also its country's capital: Barcelona,
            Madrid, Hamburg?  Start from
            https://en.wikipedia.org/wiki/List_of_metro_systems

missions    2
read        en.wikipedia.org/wiki/List_of_metro_systems
decision    decided
shortlist   Madrid
rejected    Barcelona (a mandatory criterion was not met)
            Hamburg   (a mandatory criterion was not met)

H LIVE GENERALISATION: PASS
```

The fixture asserts the contract, never the answer: a real public page
was read; every shortlisted answer rests on Evidence the mission holds;
nothing clears the shortlist without clearing every criterion; no
identifiers, internal ids or JSON reach the founder; nothing is
presented as finished on an empty result.

### What H found that no fixture could

H failed its first live run:

```
step_4: binding on step 'step_3' field 'text': the step reported
'Jump to content\nMain menu\nSearch\n...' but the independent
observation recorded 'Jump to content\nMain menu\nSearch\n...';
refusing to choose
```

`ReadPageText` cut at 40,000 characters; the independent Observation cut
at 20,000. Every page longer than 20,000 characters was unusable as
reasoning input, deterministically. Verification was doing its job; one
page had two readers. There is now one — `read_visible_text` — owned
where Evidence is produced.

Every controlled fixture page is a few hundred characters, so below both
limits the two readers agree perfectly. No fixture written by the author
of the fixtures could have found this.

## The demo centrepiece — one objective, the whole loop

```
objective   Which community repair workshops accept laptops and are
            also open on Saturday?  Start from <directory page>

missions    3
reached     directory.html, weekend-archive.html (dead), weekend.html
decision    decided
shortlist   Ashcombe Repair Workshop
rejected    Brindle Repair Workshop (a mandatory criterion was not met)
            Calder Repair Workshop  (a mandatory criterion was not met)

DEMO CENTREPIECE: PASS
```

The founder sees:

> 1 of what I found meets everything you asked for:
>   - Ashcombe Repair Workshop
> I ruled out 2: Brindle Repair Workshop (a mandatory criterion was not
> met); Calder Repair Workshop (a mandatory criterion was not met)

Neither page can answer the question alone. `weekend.html` is never
named in the objective — it was reached because the system decided it
needed evidence it did not have and knew where that evidence was. The
archive route is dead, was genuinely attempted, and the founder was not
asked to pick another source.

Controlled reality on purpose: a demo must not depend on another
company's anti-bot policy. The live Google mission that redirected
Playwright to `/sorry/` remains recorded as a truthful external failure,
and it is why this proof is hermetic.

### Three defects it exposed, in order

**A replan threw away what the last attempt established.** A replan
starts a new mission record and the deliberation read only the newest
one, so a mission that read the directory on its first pass and the
opening hours on its third could never decide anything — no single
record held both. It reported "mandatory criteria remain unestablished"
while holding, between its records, every fact it needed. The exact
opposite of the rule recovery is built on.

**A model was asked to prove a citation by transcribing a UUID.** The
guard requiring every `met` to cite a supplied observation is right and
is unchanged. H, with one observation, decided cleanly. The centrepiece,
with two, correctly rejected the two candidates needing one citation
each and lost the correct answer — the one whose two criteria come from
two different sources. Observations now carry `source_1`, `source_2`
labels. A citation naming no supplied source is still refused.

**A question that was answered was reported as a failure.** The
centrepiece ended with a decided shortlist and then said "That didn't
complete", because a route it had already recovered from failed earlier.
Both halves are facts; only one is the outcome. The failure is still
reported, in a sentence that does not contradict the answer above it.

## Batteries, at the final SHA

```
GOLDEN PATH 1 — LOCAL                              PASS
GOLDEN PATH 2 — ORDINARY BROWSER (Playwright)      PASS
GOLDEN PATH 3 — REASONING + FILE                   FAIL  (see below)

D   two independent sources, neither sufficient alone      PASS
D2  more_research is consumed, and acquires what is missing PASS
E   a failed source does not end the objective             PASS
F   provider fallback on a service notice                  PASS
G   privacy asymmetry                                      PASS
I   unanswerable research stops truthfully                 PASS
H   live generalisation                                    PASS
CENTREPIECE                                                PASS
```

## GOLDEN PATH 3 — the open P0

```
TextVerifier    matched
verified text   SproutLog / GreenGrove / PlantPad
file contents   Sprout / BloomNote / GrowLog
FIRST BROKEN BOUNDARY: the file holds EXACTLY the verified answer,
                       bound from Evidence
```

The file on the founder's Desktop does not hold the text that was
verified. Every other check on that path passed — three names, one per
line, both steps independently verified, zero AI planning calls — and
the one that matters did not.

What is known:

- One mission, one `Reasoning.Transform`, one `Filesystem.WriteFile`.
  No replan (no recovery attempt was logged).
- Twelve provider calls for that one step — `gemini.api, openrouter.api`
  six times over. The ladder retried six rounds, and a model generates
  different names each time.
- Nothing on this branch touches that value path. `git diff origin/main`
  over `executor/actions/reasoning/`, `ai_infrastructure/tiered_runner.py`
  and the reasoning Verifier is empty; the only change under
  `runtime/input_resolution.py` is the sensitivity derivation added in an
  earlier session, which does not alter what `content` resolves to.
- The 28 August ledger records this same path passing at `9234319`.

So it is intermittent, it is not a regression from this branch, and it
is on the boundary that matters most: **what a founder is told was
verified must be what is on their disk.** A re-run to characterise it
did not return within ten minutes, with providers under heavy load after
a day of live calls.

It is recorded here rather than retried until green. A boundary that
passes on the second attempt has not been fixed.

## Kimi — available provider, unhealthy session, fail-closed

```
KIMI PROVIDER          AVAILABLE
KIMI CURRENT SESSION   HEALTHY (not saturated on this estate today)
CURRENT ATTEMPT        may be UNAVAILABLE — capacity
BEHAVIOUR              detect -> reject -> Broker fallback -> continue
```

Live, all day: `High demand. Switched to K2.6 Instant for speed. Upgrade
to use K2.6 Thinking.` — classified `UNAVAILABLE`, excluded for the
attempt, ladder falls through. Never permanently blacklisted. Full
detail in `docs/audits/PROVIDER_SESSION_HEALTH.md`.

## Regression

```
75 failed  8713 passed  2 skipped
NEW FAILURE IDS: ZERO — set identical to the recorded 75 baseline
```

---

# 29 August 2026 — GP3 closed, and a correction

## Identity

```
final feature SHA     692ee09
origin/main           6349eb1   (untouched)
package               dist/Kalpavriksha/Kalpavriksha.exe
built from            692ee09
sha256                9a8232dabb4d4fe373e56f7fdd0cdcfd52172f27169a0e72dfa7e97c985dbc2b
size                  37,081,137 bytes
built                 2026-08-29 19:10:40 +0530
FMEA tier             UNSET
self-check            RESULT: OK, 48 capabilities, no-ollama constructed=no candidate=no
archive identity      5 of 5 modules FOUND -- the package carries this branch
```

## A correction I owe the record

I previously reported the golden-path-3 failure as *"intermittent, and
not a regression from this branch"*, on the strength of a `git diff` over
the reasoning action, the tiered runner and the reasoning verifier -- all
empty.

**That was wrong, and the method was wrong.** I diffed the value path and
concluded the value path was innocent, without asking what else could
change a value. The defect was mine, it was deterministic, and it was in
the recovery loop I had written the same day.

## What it actually was

`Reasoning.Transform`'s Evidence -- a deterministic measurement of the
text a model produced -- was being fed into deliberation as if it were an
observation of the world. So "think of three names and write them into a
file", an objective that poses no decision at all, produced a
deliberation, which found no candidates it could establish, which this
branch's own rule reads as *every criterion is still open*, which asked
for more research.

The mission ran **three times**:

```
attempt 1 (insufficient evidence):
    satisfied=['req_1','req_2','req_3','req_4'] unresolved=[] failed=[]
```

Every requirement satisfied, nothing unresolved, nothing failed -- and it
replanned twice anyway. Each pass generated different names and rewrote
the file, so:

```
verified text   SproutLog / GreenGrove / PlantPad     (mission 1)
file contents   Sprout / BloomNote / GrowLog          (mission 3)
```

The founder was told one thing was verified and handed another. That is
the boundary golden path 3 exists to guard.

## The fix, and one that was taken back out

**Kept.** A decision weighs the world; what the system itself said is not
something it saw. Reasoning-capability Evidence no longer enters a
deliberation. Matched on the executive prefix, so a second reasoning
capability is excluded the day it is written.

**Tried first, and wrong.** Requiring an unresolved *requirement* before
more research. D2 caught it immediately: that suppresses exactly the case
research exists for -- a mission whose steps all ran and whose objective
is still unanswered. Reverted.

**Tried, measured, taken back out.** Splitting extraction into one call
per observation, so the cross-source join would be arithmetic rather than
a model's judgement. The reasoning is right; the result was worse. Given
one page and criteria mentioning things that page says nothing about, the
model turns cautious and reports `unverified` for facts it can plainly
see -- the centrepiece went from correctly rejecting a workshop as CLOSED
at weekends to "could not be established", from the page listing its
hours. Zero provider failures in that run. Reverted, with the account
kept in the docstring.

**Kept from that attempt.** The extraction prompt was cutting every
observation at **1,500 characters**, silently. A Wikipedia list article
runs to two hundred thousand: the Brain was deciding about real research
pages from their table of contents and telling nobody. Now 12,000, and
when it bites the prompt says the source was cut and that nothing further
down may be claimed.

## Verified after the fix

```
GOLDEN PATH 1 -- LOCAL                        PASS   22.3s
GOLDEN PATH 2 -- ORDINARY BROWSER             PASS   15.4s
GOLDEN PATH 3 -- REASONING + FILE             PASS   11.8s
DEMO BATTERY: PASS

verified text   Growly / Sprout / Bedlog
file contents   Growly / Sprout / Bedlog
```

One mission. Confirmed three separate times: an instrumented probe
(`result.text` == `observation.text` == disk), and two full battery runs.

```
D   two independent sources, neither sufficient alone       PASS
D2  more_research is consumed, and acquires what is missing  PASS
E   a failed source does not end the objective              PASS
F   provider fallback on a service notice                   PASS
G   privacy asymmetry                                       PASS
I   unanswerable research stops truthfully                  PASS
DIVERSIFIED BATTERY: PASS

H   live generalisation                                     PASS
```

## Regression

```
75 failed  8720 passed  2 skipped   (42m24s, frozen tree, 692ee09)
NEW FAILURE IDS: ZERO -- set identical to the recorded 75 baseline
```

## The one open P0 -- the centrepiece verdict

The centrepiece **loop** passes on every run:

```
[PASS] the source the founder named was read
[PASS] the source holding the missing evidence was reached, and the
       founder never named it
[PASS] the dead route was genuinely attempted
[PASS] the founder was not asked to pick another source
[PASS] no identifiers / no internal ids / no raw plan in the reply
```

The **verdict** does not. Shortlisting the one candidate whose two
criteria come from two different sources has succeeded once and failed
four times on identical pages:

```
rejected: Ashcombe Repair Workshop (a mandatory criterion could not be
                                    established)      <- the right answer
          Brindle Repair Workshop  (a mandatory criterion was not met)
          Calder Repair Workshop   (a mandatory criterion was not met)
```

The two candidates that need **one** citation each are rejected correctly
every single time. Only the cross-source confirmation is unreliable --
the model is being asked to notice that the workshop named on one page is
the workshop whose hours are on another, and to cite a different source
for each criterion of the same candidate.

Two remedies are already spent: short citable labels instead of UUIDs
(kept, helped) and per-source extraction (measured worse, reverted). The
next one is not a five-minute change, and it is not being attempted
against a demo deadline.

## An intermittent worth recording

Twice, a golden-path-3 run completed the mission -- the file correct on
disk -- and then sat idle on I/O for seventeen minutes after the
completion confirmation, with flat CPU. A third run of the identical code
finished in 21.5 seconds. It is an unbounded wait somewhere past
completion when a provider stops responding rather than failing. Not
reproduced since, not isolated, and recorded rather than forgotten.

---

# 29 August 2026 -- the centrepiece verdict, diagnosed

## Classification: A -- input assembly

Not extraction. Not parsing. Not adjudication. The decision frame that
reaches the Brain does not reliably contain the founder's questions.

## What was captured

The real centrepiece objective was run with the frame printed and the
recovery loop's exits made explicit. Across three missions of one run,
every frame was:

```
FRAME: [('crit_1', 'Which community repair workshops accept laptops'),
        ('crit_2', 'Start from the directory page at the given URL')]
```

The **Saturday question is absent**, and a statement about method is a
mandatory per-candidate criterion. No workshop can BE a source. The loop
was not idle -- it spent its whole budget trying:

```
no further attempt: errors=False decided=insufficient_evidence
                    more_research=True question=True attempts=2/2
```

An earlier capture of a different run showed a different frame again:

```
crit_1  List of community repair workshops that accept laptops and
        are also open on Saturday
crit_2  Workshop must accept laptops
crit_3  Workshop must be open on Saturday
crit_4  Source must be http://127.0.0.1:.../directory.html
```

Four criteria that time, including the answer SET restated. Replaying
extraction against that exact frame and Evidence, six times, gave both
outcomes: one replay marked `crit_4` unverified and shortlisted the
right workshop; the next marked `crit_1` unverified and shortlisted
nothing. Same frame, same Evidence, same code.

**So the requirement derivation for one unchanged objective varies run
to run in count, wording and kind.** Measured directly on the Intent
Layer, the source line came back `effect`, then `constraint`, then --
live -- `information`. `shortlist()` requires every mandatory criterion
MET, so whatever lands in the frame decides the answer.

## Two fixes attempted, both taken back out

**Filter the frame to INFORMATION requirements.** A candidate is an
answer to a question about the world; an EFFECT is something to do, a
DELIVERABLE is what to hand over about the winners, a CONSTRAINT is a
condition on how. Three isolated measurements supported it. The live
path then labelled the source line `information` and dropped the
Saturday question, and a frame missing one of the founder's questions
produces a confident answer to half the request. Reverted.

**Read each source separately and join by counting.** The cross-source
join is a judgement, and this module's rule is that a model reads prose
into structure while `shortlist()` decides. Measured worse: given one
page and criteria mentioning things that page says nothing about, the
model turns cautious and reports `unverified` for facts it can plainly
see -- a workshop went from correctly "closed at weekends" to "could not
be established", from the page listing its hours. Zero provider failures
in that run. Reverted.

Both accounts are kept in `frame_for` and `candidates_from`, because the
reasoning behind each is still right and the next person to have the
same idea should find out what happened when it was tried.

## What is kept

**`tests/test_cross_source_qualification.py`** -- deterministic, no
model, twenty runs. One criterion from E1, another from E2, same
candidate; rivals rejected for their own reasons; a citation naming no
supplied source still refused. It passed on the first run, which is
itself the proof that adjudication, sufficiency and the shortlist were
never the defect.

**`tests/test_no_demo_specific_production_code.py`** -- fifteen deciding
modules, executable code only (comments and docstrings excluded, because
that is where this codebase keeps its reasoning). None of them names a
workshop, a reading room, a game or a city.

**The recovery loop's three silent exits now say why they stopped.** A
mission that ran once instead of three times used to be something to
reconstruct from outside.

**A 12,000-character observation budget**, declared when it bites. It
was 1,500, silently.

## State

```
D            PASS      D2           PASS      E            PASS
F            PASS      G            PASS      I            PASS
GOLDEN 1     PASS      GOLDEN 2     PASS      GOLDEN 3     PASS
DEMO BATTERY: PASS     DIVERSIFIED BATTERY: PASS

CENTREPIECE loop        PASS on every run
CENTREPIECE verdict     NOT STABLE -- 5/5 not attempted, root cause upstream
```

## The remaining work, named

Requirement derivation must produce the founder's questions
deterministically for an unchanged objective. That is a change to the
Intent Layer with its own regression surface, and it is not a change to
make against a demo deadline after two measured-wrong attempts in one
evening. It is written down here so it starts from evidence rather than
from a fresh guess.

---

# 29 August 2026 -- the Intent/requirement boundary, traced

## What was asked, and what was found

The brief's prescribed correction was: derive the founder's requirements
once per canonical objective, and have every replan reuse them.

**That is already implemented.** `missions/service.py::_admit` derives
only when the Intent carries none:

```python
if not getattr(intent, "requirements", ()) and self.intent_layer is not None:
    intent.requirements = self.intent_layer.requirements_for(intent, raw=text)
```

`_submit_objective` passes the same canonical Intent object through every
replan, so the second and third admissions skip derivation entirely.
Nothing is keyed by raw text.

It had no regression. It has one now --
`tests/test_requirement_stability_across_replans.py`, nine tests, with a
stub Intent Layer whose reading of the same sentence CHANGES between
calls, so a constant mock cannot make it pass:

```
requirements_for calls for one objective        1
ids / descriptions / kinds / provenance         stable across two replans
the second, incompatible reading                never consumed
two separate objectives with identical text     derive independently
a founder modification                          may change meaning, by
                                                being a new canonical Intent
```

The live capture agrees: three missions of one centrepiece run all framed
the identical two criteria. **Requirements do not move during a
mission.**

## Where the variance actually is

Not in reuse. In the FIRST derivation, run to run, for the same sentence.

`_reasoned_requirements` was measured five times on the centrepiece
objective, with the model's raw output printed beside what the parser
kept:

```
run 1   3 offered, 3 kept   Saturday=information   source=constraint
run 2   3 offered, 3 kept   Saturday=information   source=constraint
run 3   4 offered, 4 kept   Saturday=information   source=constraint
                            + a synthesised "combined list of workshops
                              that meet both criteria"
run 4   3 offered, 3 kept   Saturday=information   source=constraint
run 5   3 offered, 3 kept   Saturday=CONSTRAINT    source=INFORMATION
```

A correction to my own earlier reasoning: I expected the parser's closed
kind vocabulary to be silently dropping requirements, since
`_reasoned_requirements` discards any item whose `kind` falls outside
`REQUIREMENT_KINDS` and then renumbers the survivors by position. **It
was not.** Every item the model offered survived in all five runs. The
drop path exists and is a real hazard, but it is not what happened here,
and saying so is worth more than a fix aimed at the wrong thing.

What varies is the reading itself: the count (three or four), the
wording, and which of the two labels lands on which sentence. Run 5
labelled the Saturday question `constraint` and the navigation
instruction `information` -- exactly inverted.

And an earlier live admission produced only TWO requirements, losing the
Saturday question altogether:

```
crit_1  Which community repair workshops accept laptops
crit_2  Start from the directory page at the given URL
```

Every downstream component then reasoned correctly about a question the
founder did not ask.

## Why this is not fixed tonight

The remaining lever is the derivation prompt, and the brief rules out
prompt experimentation for good reason. Two corrections were attempted
earlier this evening on the same defect -- filtering the frame to
INFORMATION requirements, and splitting extraction per source -- and both
were measured worse and reverted. A third speculative change to the one
boundary that decides what the founder asked for, made at the end of a
long day against a demo deadline, is how the third one goes wrong too.

What the next attempt should start from, rather than a fresh guess:

- The reuse invariant holds and is now pinned; do not re-solve it.
- The parser drops nothing here; do not harden the wrong path first,
  though the silent-drop-and-renumber branch is worth closing on its own
  merits.
- The variance is in `_reasoned_requirements`' single call. The two
  failure shapes are a MISSING question and a SWAPPED kind, and both
  are visible in the raw output, which means a coverage check against
  the founder's own sentence is possible without a second model.

## State

```
D PASS   D2 PASS   E PASS   F PASS   G PASS   I PASS
GOLDEN PATH 1/2/3 PASS      DEMO BATTERY PASS
cross-source deterministic fixture PASS (20 runs, no model)
requirement stability regression   PASS (9 tests)
task-specific production code      NO

CENTREPIECE loop      PASS on every run
CENTREPIECE verdict   NOT STABLE -- 5/5 gate not met
```
