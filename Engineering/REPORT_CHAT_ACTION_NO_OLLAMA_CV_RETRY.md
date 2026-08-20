# KALPAVRIKSHA — CHAT/ACTION FINALIZATION + FOUNDER NO-OLLAMA + CV RETRY

**Date:** 2026-08-20 · **Base:** `c27e9f4` → **`889c687`** (== `origin/main`, ahead 0, behind 0)

Both blockers are closed. **The CV objective reached the Planner for the first time** —
routed as an instruction, byte-identical, `MISSION_PLANNING_STARTED` emitted, and no Ollama
touched. It then stopped on a new first blocker: the Planner returned an empty plan on this
run, and that answer is presented to the founder as a *completed* mission.

---

## Part A — chat vs action

`_is_capability_inquiry()` was a bag of words over the whole utterance: `what` anywhere,
plus `you`/`your`, plus one of `do/does/capable/able/help/handle/use/offer/support`. Your
hundred-word instruction supplied all three by accident — *"show me **what you** propose"*
and *"Then **use** the revised profile"*. One word decided it.

**The invariant, now implemented:** a recogniser may claim an utterance only when the
conversational intent describes the utterance **as a whole**. Structural, not a longer word
list:

* clauses split at sentence ends and at the joins that introduce a second thing to do;
* a clause opening with an operational verb means the utterance is a job, **wherever that
  clause sits** — leading adverbs (`also`, `then`, `please`) are stepped over to find it;
* a phrase must *be* its clause, not occur inside one. *"What needs my attention"* is a
  question; *"find what needs my attention in this report"* is work.

Word order carries it: `What can you check?` is a question, `Check what you can do.` is not,
and the words are identical.

`STATUS_QUERY`, `ACTIVITY_QUERY` and `PRIORITY_QUERY` had the same defect and got the same
rule — *"Check system status and save it to a file"* was being answered while the founder
waited for a file.

**Precision over recall**, by instruction: when it cannot show the utterance *is* the
question, it escalates. An objective wrongly answered here never reaches the Planner at all.

Architecture preserved: `Disposition.HANDLED` / `ESCALATE` / `UNAVAILABLE` untouched,
`BUILD_REQUEST` and `UNKNOWN` still escalate. This changed a recogniser, not the pipeline.

**All 27 routing-matrix cases pass**, and all 15 genuine capability phrasings still route as
questions — including your verbatim production phrasing. `use` → `take` now changes nothing.

---

## Part B — no Ollama on this machine

Removed from registration, from the ladder, and from the packaged bundle.
`providers/ollama.py` is untouched and still a good generic provider; what is gone is
Founder Edition *activating* it. Nothing constructs it, registers it, configures a local
tier, probes the daemon, loads a model or sends it a prompt.

`ollama.local` **stays in the catalogue on purpose** — that is what makes
`all_known_provider_ids` exclude it from every tier attempt, so it cannot win by ranking
even though it is known.

13 tests. Re-introducing the registration fails 3 of them. Removing it also **fixed 3
pre-existing failures** (11 → 8).

**RAM:** no model was resident to release — the daemon had already unloaded it by idle
timeout. 8.4 GB free before, 8.3 GB after. Your two `ollama` daemon processes (0.01 GB each)
predate this work and were left alone.

### The consequence, not bypassed

`Reasoning.Transform` still defaults to `sensitive`. With the local runtime gone that
default has teeth: private evidence has **no private provider to go to**, so
`approval_needed()` turns it into a founder question rather than a silent send to a cloud
model. §16 said not to relax privacy to compensate, and it is not relaxed.

---

## Part C — the live run

Normal Founder profile, not an isolated root (§20). The exact objective, unmodified.

### First acceptance gate — PASSED

| | |
|---|---|
| ConversationEngine | **ESCALATE** — reached the Mission pipeline |
| Objective preserved | **byte-identical, 712 chars** |
| `MISSION_PLANNING_STARTED` | **emitted**, 11:29:46 |
| Ollama in broker records | **0** |

The surface showed *"Working out the steps"*. This is the first time this objective has ever
reached the Planner.

### Then it stopped

```
11:29:46  gemini.api  -> selected  exec=succeeded  requester=planner
11:30:00  gemini.api  -> selected  exec=succeeded  requester=brain_advisory
```

No plan record was written and no task ever ran. The Planner's reply was an empty plan, and
`kalpavriksha_desktop.py` routes exactly one refusal code — `NO_STEPS` — to
`brain/advisory.py::advise()`. What the founder was told:

> *"I understand completely. I am taking full responsibility for evaluating all your resume
> files… I am going to catalog your local resume files… Shall I start cataloging those files
> now?"* — recorded with **`status=completed`**.

**This is variance, not a capability gap.** Two attempts against the identical
packaged-shape prompt (46 capabilities, 19,677 chars):

```
attempt 1: 11 steps -> ACCEPTED
attempt 2: NO_STEPS
```

The same objective planned successfully minutes earlier, and planned successfully again on
retry. Nothing about the catalogue prevents it.

### The part that deserves attention beyond the retry

A `NO_STEPS` refusal is reported to the founder as a **completed mission containing a
promise**. Nothing was catalogued, nothing was read, no work exists — and the audit says
`completed`. The advisory route was built for *"understood, but larger than one action"*,
which is a fair reading of some objectives; here it made a failure look like an
acknowledgement, and asked a question ("Shall I start?") that nothing was waiting to act on.

That is a truthfulness regression of the same family as the ones already fixed in the
Reporter, and it is the reason this run *looked* like it worked.

---

## Verdicts

| | |
|---|---|
| CHAT/ACTION ARCHITECTURE PRESERVED | **YES** |
| WHOLE-UTTERANCE CLAIM RULE | **READY** |
| CAPABILITY QUERY HIGH-PRECISION | **READY** |
| REAL CV OBJECTIVE ROUTES AS ACTION | **YES** |
| REAL CV OBJECTIVE REACHES PLANNER | **YES** |
| INTENT TEXT PRESERVED | **YES** — byte-identical, 712 chars |
| OLLAMA GENERIC CODE RETAINED | **YES** |
| OLLAMA FOUNDER REGISTRATION | **ABSENT** |
| OLLAMA PROVIDER ELIGIBLE | **NO** |
| OLLAMA QUERIED DURING LIVE RUN | **NO** — 0 broker records |
| REASONING.TRANSFORM PRESERVED | **YES** |
| NORMAL PRIVACY POLICY PRESERVED | **YES** — sensitive default intact, not relaxed |
| CV MISSION | **BLOCKED** |

**FIRST BLOCKER:** the Planner returned `NO_STEPS` on this run, and that code is routed to
advisory — so the mission ended as a promise marked `completed` instead of as work. The same
prompt yields an accepted 11-step plan on retry, so this is provider variance, not a missing
capability.

**INTRODUCED TEST FAILURES: 0** (baseline 11 → 8 after; 3 pre-existing failures fixed).

Founder originals: **5 files, MD5 unchanged, nothing written.** The window was closed at
test end.

---

## The two questions

**1. Can Kalpavriksha now distinguish a genuine conversation from an operational instruction
without conversational words inside the instruction hijacking it?**

**Yes.** Twenty-seven matrix cases, including every example in the brief, and the real
objective proven live: it reached the Planner rather than being answered. The rule is
structural and clause-local, so the hijack cannot recur through a synonym — a longer word
list would only have moved the boundary.

**2. Did the exact CV mission reach and proceed through the Mission pipeline without
Ollama?**

**It reached it; it did not proceed through it.** Routing, preservation and planning start
are proven live with zero Ollama contact. Execution never began, because the Planner
answered with no steps on that attempt — and the founder was shown a completed mission with
a promise attached, which is the more troubling half of the finding.

Per §25: Part A and Part B are **INTEGRATED**. The routing repair is **LIVE-PROVEN** — it
was watched working in the packaged application. Nothing downstream of planning is.
