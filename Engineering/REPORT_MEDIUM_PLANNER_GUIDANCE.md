# KALPAVRIKSHA — MEDIUM PLANNER GUIDANCE REPORT

**Date:** 2026-08-20 · **Base:** `49e152f` == `origin/main`, ahead 0, behind 0

Intent was correct. **The observed CV failure was provider unavailability, not a Planner
guidance failure** — no plan ever came back, so the Planner's guidance was never exercised
on this objective. The guidance gap is real but **latent**, and this mission closes it as
such rather than claiming it caused what happened.

---

## 1. Git Truth

`HEAD == origin/main == 49e152f16691b302e5ffc7956b1890ea3c479edf`, ahead 0, behind 0.
Worktree 116 entries (5 modified, 111 untracked) — unchanged. No reset, no clean.

---

## 2. Exact Failed CV Founder Turn

**The request is not in the production state root.** `%LOCALAPPDATA%/Kalpavriksha/state`
ends on 2026-08-19 and contains no CV turn. A machine-wide search found it in
`Temp/kv_visible` — the isolated root belonging to the app instance left running after the
09:30 visible Medium success. **The Founder typed the request into that still-open window,
so it was audited there instead of in his own history.** Worth recording: a test-rooted
session outliving its test captured real Founder work.

| | |
|---|---|
| `interaction_id` | `d25640f92dc6` |
| `at` | `2026-08-20T04:05:57.225176+00:00` (**09:35:57 IST**) |
| `direction` | `founder` |
| `interaction_type` | **`unknown`** — *not* `mission_request` |
| reply | `f38765a18366`, `status='failed'`, *"I couldn't plan that just now. Please try again."* |

A second identical attempt followed: `fe48b1df5755` at 04:06:15 → `da40ba52c4d9` at
04:09:09, same failure text.

`interaction_type='unknown'` is **not** CV-specific: the browser objective that succeeded
minutes earlier is recorded the same way. It classifies the audit row, not the request.

---

## 3. Intent Audit Evidence

`MISSION_UNDERSTANDING_STARTED` and `MISSION_PLANNING_STARTED` were published for **both**
attempts (`plan-2`, `plan-3`). The planning payload objective is **311 characters,
byte-identical to the Founder's text**:

```
Check my CV stored in the D drive, understand my experience, skills and profile, then
search for current job opportunities that are suitable for me. Give me the best matching
opportunities with the company name, role, location, job link, why it suits my profile,
and any important skill gap I should know about.
```

All eleven material requirements survived — CV on D drive, experience, skills, profile,
search opportunities, company name, role, location, job link, why it suits, skill gaps.
**No tail lost, no collapse to "read CV" or "search jobs".**

**No clarification was asked.** No `clarification_question` row, `clarification_id` null.

---

## 4. Structured Intent Reconstruction

`IntentLayer.parse(exact_text)`, read-only, on the exact audited string:

| field | value |
|---|---|
| `goal` | byte-identical to the Founder's text |
| `constraints` | `[]` |
| `context` | `{'raw_input': <the same text>}` |
| `success_criteria` | `[]` |
| `actor` | `system` |
| `beneficiary` | `founder` |
| `needs_clarification` | `False` |
| `capability` | `''` |

`capability=''` is correct: no single typed capability names this objective, and the
multi-requirement guard properly declined single-capability dispatch. Empty
`constraints`/`success_criteria` is the rule-based layer not decomposing prose — the whole
request is carried in `goal`, so nothing was lost or distorted.

---

## 5. Intent Verdict

### **INTENT CORRECT**

The whole requested objective and both roles survived into the Planner intact.

---

## 6. Actual Planning Failure

| | attempt 1 (`plan-2`) | attempt 2 (`plan-3`) |
|---|---|---|
| planning started | 04:05:57.239 | 04:06:15.828 |
| Founder told | 04:05:57.245 | 04:09:09.739 |
| elapsed | **6 ms** | **173 s** |
| provider decisions | **none** | six |

**Attempt 1 reached no provider at all.** Six milliseconds, zero broker decisions: the
session was in LOCAL mode (set for the 09:30 visible mission and session-scoped), the
deterministic path did not recognise the objective, and LOCAL correctly refuses rather
than contacting a provider. Working as designed.

**Attempt 2 ran the whole ladder and every tier failed:**

```
04:06:15 gemini.api          rejected     HTTP 429, free-tier quota
04:06:26 chatgpt-desktop     unavailable  no real, visible window
04:06:59 perplexity-desktop  rejected     typed into the composer but could not verify it landed
04:07:43 kimi-desktop        unavailable  ISOLATION_UNVERIFIED
04:08:01 —                   no_provider_available
04:08:01 browser.free-ai     timed_out    Duck.ai
```

So: **was a plan returned? No. Was it rejected? There was none to reject. Did it return
`steps: []`? No.** Nothing came back at all.

**This is a provider availability failure.** The Planner's guidance was never tested
against this objective, and this report does not claim it produced a bad plan.

---

## 7. Existing Planner Guidance

Rules 1–6 already teach exact capability names, exact argument spelling, per-step success
expectations, `depends_on`, `input_bindings` with both forms, that cross-step values must
never be guessed, fewest sufficient steps, and `steps: []` when the catalogue cannot
achieve the goal. **All preserved verbatim**, asserted by test.

They teach the **shape** of a plan and say nothing about **method**. For a compound
objective the only two rules that spoke — "use the fewest steps" and "reply `steps: []` if
the catalogue cannot achieve the goal" — both point toward collapse. A model that asks *is
there one capability that does all of this?* answers no and stops.

---

## 8. Medium-Task Guidance Added

Seven rules appended to the same `_RULES` tuple. No second Planner, no new module.

| rule | what it establishes |
|---|---|
| 7 | A multi-capability goal is normal. Evaluate the catalogue **compositionally**. |
| 8 | **Discover before guessing** — plan the step that finds out. Not knowing is not a reason to stop, and not a reason to ask. |
| 8a | **Discoverable vs Founder-owned** unknowns. "Uncertainty you could have resolved is not impossibility." |
| 9 | **Acquire a fact before using it**; reference it through `input_bindings`. |
| 10 | **Observed reality outranks the objective's wording** — the trailing-slash lesson, generalised. |
| 11 / 11a | **Cover the whole request**, not its first executable action. Phase habit; local source before dependent external research. |
| 12 | `steps: []` is the **last** answer, not the first. |
| 13 | **Never invent a capability**, and planning-time reasoning "is not a capability the machine has at run time". |

Rule 5 was clarified in place: *"fewest" means no redundant steps — not dropping a phase
the objective requires to make the plan shorter.*

---

## 9–12. The four rules the brief asked for

**Requirement coverage (9).** Rule 11 requires checking each material requirement against
the step or output that satisfies it, and explicitly forbids writing that check out — a
reasoning trace in the reply would break the JSON contract of rule 1.

**Discover vs ask (10).** Rules 8/8a. The Planner does not own clarification and this does
not give it any; it forbids converting a *discoverable* unknown into a fake impossibility.

**Cross-step data (11–12).** Rules 9 and 10, pointing back at rule 4a's existing syntax.
Nothing about the binding mechanism changed.

**Capability composition (12).** Rules 7 and 12 together: *no single capability performs
the mission* is not the same statement as *the mission cannot be executed*.

---

## 13. CV Task Capability Coverage — the finding that matters

Against the live 42-capability catalogue (Browser, Desktop, Filesystem):

| phase | verdict | basis |
|---|---|---|
| locate CV | **SUPPORTED** | `Filesystem.SearchFiles`, `ListDirectory`, `FileExists` |
| read CV | **PARTIALLY SUPPORTED** | `Filesystem.ReadFile` is *"Read a **text** file's content"* — a PDF or DOCX CV is not covered |
| understand / profile CV | **NOT REPRESENTABLE** | no registered capability performs judgement |
| search current jobs | **SUPPORTED** | `Browser.Navigate` + `TypeText` + `Click` + `ObserveBrowser` |
| inspect job postings | **SUPPORTED** | `Browser.ObserveBrowser` |
| compare job to CV | **NOT REPRESENTABLE** | as above |
| compose ranked recommendations | **NOT REPRESENTABLE** | as above |

**There is no executable reasoning capability in the catalogue.** Three of the seven
phases cannot be expressed at all.

So even with perfect guidance this objective cannot complete today — and rule 13 is what
makes that failure *honest*: the Planner must answer `steps: []` rather than invent
`Reasoning.AnalyzeCV` or pretend `Desktop.ExecuteCommand` performs the judgement. **The
next blocker after this mission is a genuine capability gap, not Planner guidance.**
Nothing was implemented for it here.

---

## 14. Files Changed

```
src/master_agent/planner/prompting.py      (prompt text only)
tests/test_medium_planner_guidance.py      (new)
Engineering/REPORT_MEDIUM_PLANNER_GUIDANCE.md
```

`planner.py`, `parsing.py`, `catalogue.py` and `direct.py` were **not** modified. Nothing
outside `planner/` was touched — verified by diff against `49e152f`.

The production audit is **MD5-verified unchanged** across all four files. It was read only.

---

## 15. Planner Tests

45 tests, all ten required properties, plus two guards of my own:

* the guidance is **generic** — a word-boundary check asserts the rules never name `cv`,
  `resume`, `curriculum`, `job`, `vacancy`, `career`, `d drive`, `d:`, `linkedin`,
  `naukri`, `indeed`, `recruit`, and the rules hold for objectives of any subject;
* the **original contract survives** — rules 1–6 phrasing, the binding syntax example, and
  the no-double-set rule are each asserted intact.

That first guard caught a real slip: rule 7 originally read *"one capability that does this
whole job"*. Generic English, but in a rule set written after a job-search failure it reads
as leakage, so it now says *"does all of this"*.

No packaged run, no FMEA, no live search, no D-drive access.

---

## 16. Regression

**409 passed with the change** (364 baseline + 45 new), **364 passed at `49e152f`**,
**0 failures either side, 0 introduced** — across 13 planner, routing, binding, direct-plan
and mission-pipeline suites. File list verified present before the run counted as a
baseline. The live-proven visible browser→file behaviour is still asserted at Planner level
by `test_local_capture_workflow.py`.

---

## 17. Git End State

`HEAD == origin/main`, ahead 0, behind 0, worktree 116 entries.

---

## Verdicts

| | |
|---|---|
| INTENT PRESERVED FULL REQUEST | **YES** — byte-identical, 311 chars |
| INTENT REQUIRED CLARIFICATION | **NO** |
| INTENT VERDICT | **CORRECT** |
| PLANNER REACHED | **YES** — both attempts |
| PLANNER MEDIUM GUIDELINES ADDED | **YES** |
| COMPOUND TASKS TREATED AS NORMAL | **YES** |
| DISCOVERABLE UNKNOWNS ACQUIRED | **YES** |
| FUTURE VALUES MUST USE BINDINGS | **YES** |
| FULL REQUIREMENT COVERAGE REQUIRED | **YES** |
| CAPABILITIES EVALUATED COMPOSITIONALLY | **YES** |
| UNAVAILABLE CAPABILITIES MAY BE INVENTED | **NO** |
| CV-SPECIFIC LOGIC ADDED | **NO** |
| INTENT LAYER MODIFIED | **NO** |
| RUNTIME MODIFIED | **NO** |
| MISSION CONTROL MODIFIED | **NO** |
| EXECUTIVES MODIFIED | **NO** |
| PACKAGED INTEGRATION RUN | **NO** |
| INTRODUCED TEST FAILURES | **0** |

---

## The two questions

**1. Was the CV request correctly understood before it reached Planner?**

**Yes.** The audit shows the objective reaching `MISSION_PLANNING_STARTED` byte-identical
at 311 characters with all eleven requirements intact, no clarification asked, actor
`system`, beneficiary `founder`. Intent is not the blocker, and no repair belongs there.

**2. After this Planner-only improvement, does the Planner have clear generic guidance for
decomposing and sequencing Medium objectives without guessing, dropping requirements, or
assuming one capability must solve the whole task?**

**Yes — with one honest boundary.** The prompt now states that compound goals are normal,
that the catalogue is to be read compositionally, that discoverable facts are acquired
rather than guessed or asked about, that acquired facts flow through `input_bindings`, that
observation outranks the objective's wording, that the whole request must be covered, and
that refusal comes last.

The boundary: **a prompt is an instruction, not a guarantee.** These tests prove the
guidance is present, load-bearing and free of task-specific vocabulary. They cannot prove a
model obeys it, and no provider was available to try. The first real test of this guidance
will be the first successful planning call on a compound objective.

And when that call happens, the CV objective will still not complete — because three of its
seven phases have no executable capability. Rule 13 ensures the Planner says so plainly
instead of inventing one.
