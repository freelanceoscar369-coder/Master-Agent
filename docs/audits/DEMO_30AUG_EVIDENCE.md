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
