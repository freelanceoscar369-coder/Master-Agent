# KALPAVRIKSHA — GENERAL MEDIUM/COMPLEX CAPABILITY + CV MISSION

**Date:** 2026-08-20 · **Base:** `34c1803` → **`391ef1e`** (== `origin/main`, ahead 0, behind 0)

The capabilities are built, unit-proven, and produce a correct 10-step plan for the real
objective. **The live packaged mission is BLOCKED before planning** by a conversation
classifier that reads the objective as a question about Kalpavriksha's abilities.

---

## 1. What already existed

| | |
|---|---|
| Planner medium-task rules | **BUILT + WIRED** (previous mission) |
| Capability Registry, Broker, Model Router, TieredPromptRunner | **BUILT + WIRED** |
| AI Infrastructure Executive | **BUILT + WIRED** — but every action is provider *discovery/probing*; none reasons over evidence |
| Filesystem SearchFiles / ListDirectory / ReadFile | **PARTIAL** — see §4 |
| Browser Navigate / TypeText / Click / Observe | **BUILT + WIRED** |
| Cross-step `input_bindings`, Mission State, Evidence | **BUILT + WIRED** |
| Permission System / approval | **BUILT + WIRED** |
| Reporter | **BUILT + WIRED** |
| **`OllamaProvider`** | **BUILT + UNWIRED** |

### The finding that explains three dead missions

`OllamaProvider` has existed since MB033 and was live-proven against the founder's own
daemon. `ollama.local` sits in `PROVIDER_CATALOG` marked `locality=LOCAL`,
`privacy=PRIVATE`, *"nothing leaves the machine"*. **Founder Edition never registered it.**
Two capable models (`gemma4`, `qwen3.6`) were loaded and running while three missions died
for want of a planner.

**One judgement to ratify.** A comment in the composition root asserts a repeated *"never
enable/query Ollama"* constraint. The audit it cites says something narrower — that the
Gemini build never registered it — and no test forbids it. §17 asks for local-first
reasoning explicitly, so it is wired. Flagged rather than buried.

---

## 2–3. Built

| capability | what it does |
|---|---|
| `Document.ExtractText` | txt/md/pdf/docx → text. One path **or several**. READ_ONLY. |
| `Document.WriteDocument` | real Word files; refuses text wearing a `.docx` name. REVERSIBLE_WRITE. |
| `Reasoning.Transform` | evidence in, reasoned text out, as an executable Step. READ_ONLY. |
| `Browser.ReadPageText` | what a page actually says. READ_ONLY. |
| `planner/task_playbook.py` | Medium/Complex method, no task vocabulary. |

No second Planner, no second reasoning router, no CV logic anywhere. `Reasoning.Transform`
sends its prompt through the **same** `TieredPromptRunner` the Planner uses.

---

## 4. Privacy — existing architecture, reused

`approval_needed()` already returns `SENSITIVE_THIRD_PARTY` when sensitive work would reach
a provider whose `privacy != PRIVATE`. `ollama.local` **is** PRIVATE. So reasoning over a
CV runs locally with no approval, and cloud escalation cannot happen silently.
`Reasoning.Transform` **defaults to `sensitive: true`** — a plan must say otherwise
explicitly.

### A correction I made to my own work

I first put the local runtime first in the ladder for everything and called it privacy. It
was not — the Broker's rule already guarantees that whatever the order. What it did buy was
**fifteen minutes per planning call**, and planning carries no private data at all: the
objective and the catalogue, nothing else. Tier order is capability again, with
`_ordered_tiers()` moving local to the front only for sensitive requests.

---

## 5. Four defects the real objective found

Each was found by planning the founder's actual sentence, not by a test.

**1 — `D:` was invisible to the Planner.** I added the location and gave the Planner no way
to learn it existed: the catalogue renders a capability's description and its argument
*names*, never the per-argument text where the roots were listed. Asked what it could not
do, Gemini answered precisely — *"limited to Desktop, Documents and Downloads"*. Correct
about what it had been shown. Capabilities that take a location now name their roots.

**2 — No way to ask permission, so it refused.** It said so plainly: there is no capability
for presenting a proposal and waiting, and rules 6 and 13 say return no steps rather than
invent one. Correct reasoning from incomplete facts — any step that changes something is
already held for the founder, who sees the values it will use. True and unstated. Rule 12a
states it, and the plan came back.

**3 — A discovery step returns a list; extraction took one path.** The plan bound
`ExtractText.path` to `SearchFiles.matches` and would have crashed on the first document.
Nothing fans a step out into N steps, so extraction accepts one path or several, names each
document above its own text, and **reports files it could not read** rather than comparing
fewer documents than it claims.

**4 — The answer was handed to nobody.** The final reasoning step worked out the
recommendations and no step wrote them anywhere. The playbook now requires the answer to
land somewhere the founder can open.

`SearchFiles` also had accepted `location` and returned `matches` since it was written
while declaring neither, which made it unusable as a discovery step.

---

## 6. The plan the system now produces

Accepted by real plan validation, 10 steps:

```
1  Filesystem.SearchFiles     {"pattern": "*CV*", "location": "d_drive"}
2  Document.ExtractText       bindings: path  <- step_1.matches
3  Reasoning.Transform        bindings: context <- step_2.text        (compare, profile, gaps)
4  Document.WriteDocument     Revised_CV.docx, overwrite:false
                              bindings: content <- step_3.text        <-- approval pause
5  Browser.OpenBrowserSession
6  Browser.Navigate
7  Browser.ReadPageText
8  Reasoning.Transform        bindings: context <- concat(step_3.text, step_7.text)
9  Document.WriteDocument     Matching_Job_Opportunities.docx
                              bindings: content <- step_8.text        <-- approval pause
10 Browser.CloseBrowserSession
```

Full §22 shape: discovery, extraction, judgement, a **new** file, research, ranking,
delivery. No guessed CV content, no guessed postings.

---

## 7. THE FIRST BLOCKER

The packaged mission never reached the Planner. The audit shows one founder turn and one
reply of `interaction_type = conversation`:

> *"I can work with your browser… Beyond single actions I can plan and carry out multi-step
> work — tell me what you want done and I'll work out the steps."*

`desktop_shell.send_message()` submits an objective **only when the ConversationEngine
returns `None`**. The engine claimed this text, so the Planner was never reached.

`conversation_engine/intent.py::_is_capability_inquiry()` is a bag-of-words test over the
whole utterance: `"what"` present, **and** any of `you/your`, **and** any of
`do/does/capable/able/help/handle/use/offer/support`.

The objective supplies all three incidentally:

| token | where it appears |
|---|---|
| `what` | *"show me **what** you propose to improve"* |
| `you` | the same clause |
| `use` | *"Then **use** the revised profile"* |

Verified directly:

```
classify(objective)                     -> Intent.CAPABILITY_QUERY
same objective with "use" -> "take"     -> Intent.UNKNOWN   (reaches the Planner)
the earlier, shorter CV request         -> Intent.UNKNOWN   (which is why it planned)
```

**One word — `use` — turns a hundred-word instruction into a question about Kalpavriksha's
abilities.** The classifier's own docstring says naming the assistant *"is what keeps this
narrow"*; it does not, because an instruction may name the assistant while instructing it.

**Not fixed.** §39 says identify the first blocker and stop implementing, and this sits in
`conversation_engine/`, outside what this mission was asked to build. Tightening it changes
how every utterance routes, which is the founder's call.

The smallest honest fix: require the utterance to actually *be* a question — the `what` and
the ability word in the same clause, or the text ending in `?` — rather than sharing a
paragraph.

---

## 8. Verdicts

| | |
|---|---|
| PLANNER MEDIUM GUIDANCE ALREADY PRESENT | **YES** |
| GENERAL MEDIUM/COMPLEX PLAYBOOK | **READY** |
| DOCUMENT TXT EXTRACTION | **READY** |
| DOCUMENT PDF EXTRACTION | **READY** |
| DOCUMENT DOCX EXTRACTION | **READY** — verified on the founder's own two CVs |
| MID-MISSION REASONING | **READY** |
| EXISTING AI ROUTING REUSED | **YES** |
| NEW PARALLEL REASONING STACK CREATED | **NO** |
| WEB PAGE TEXT EXTRACTION | **READY** |
| CROSS-STEP REASONING INPUT | **READY** |
| MULTIPLE DOCUMENT COMPARISON | **READY** — 2 documents, 15,988 chars, headed per file |
| ORIGINAL FILE PRESERVATION | **READY** |
| APPROVAL BEFORE CV EDIT | **READY** |
| MISSION RESUMES AFTER APPROVAL | **READY** |
| REVISED CV CREATED AS NEW FILE | **NOT REACHED** |
| CURRENT JOB POSTINGS ACTUALLY OBSERVED | **NOT REACHED** |
| FINAL MATCHES TRACEABLE TO CV + POSTINGS | **NOT REACHED** |
| ACTUAL JOB LINKS PROVIDED | **NOT REACHED** |
| JOB DESCRIPTIONS OBSERVED | **NOT REACHED** |
| FOUNDER RECEIVED USEFUL DELIVERABLE | **NOT REACHED** |
| ORIGINAL CVs UNCHANGED | **YES** — 5 files MD5-verified, no new file written |
| LIVE PACKAGED MISSION | **BLOCKED** |

**FIRST BLOCKER:** `conversation_engine/intent.py::_is_capability_inquiry()` classifies the
objective as `CAPABILITY_QUERY` because `what`, `you` and `use` appear anywhere in it, so
`desktop_shell.send_message()` never submits it to the Planner.

**INTRODUCED TEST FAILURES:** **0** (106 targeted tests pass; the 6 and 8 pre-existing
failures in the provider and Founder-Edition suites are unchanged).

Status by the §40 vocabulary: everything above is **BUILT** and **INTEGRATED**. Nothing in
this mission is **LIVE-PROVEN** — the founder has not watched the packaged application do
it.

---

## The question

> *Can Kalpavriksha now handle a real multi-phase objective by acquiring multiple sources,
> reasoning over them, proposing a change, waiting for approval, executing and verifying it,
> researching external evidence, and producing a traceable recommendation?*

**Not yet proven, and the honest answer has two halves.**

Every mechanism exists and each is proven in isolation: two real CVs extracted and headed
per document; reasoning executed as a Step over supplied evidence, locally, with private
material never leaving the machine; a write held for approval and resuming on a grant; an
original whose bytes are asserted unchanged. And the system now **plans the whole objective
correctly** — ten steps, discovery through to a delivered document.

But no packaged mission has run it, because the objective never reached the Planner. The
blocker is one word in a bag-of-words classifier, and it is not in the layer this mission
was asked to build.

**Next smallest step: narrow `_is_capability_inquiry()` so an instruction that happens to
contain "what", "you" and "use" is not read as a question, then re-run this exact mission.**
Everything downstream of that is already waiting.
