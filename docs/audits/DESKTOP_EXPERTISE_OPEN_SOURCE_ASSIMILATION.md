# Desktop expertise: what to take from UFO and OpenAdapt, and what not to

**Status:** source inspection complete. No code ported yet — this document
is the gate that decides what may be.

## Provenance

Every claim below was read from source at these exact commits, cloned to a
temporary location outside the repository. Nothing was installed, and no
dependency was added.

| Project | Commit | Licence | Role here |
|---|---|---|---|
| `microsoft/UFO` | `cd9bfdd6caacee7b8c5894605f42207ec84b6e47` | MIT | knowledge sources, retrieval, experience summarisation |
| `OpenAdaptAI/OpenAdapt` | `753f3d28ca4e5c2e18761be097fd57e75753a23a` | MIT | demonstration capture lineage |
| `OpenAdaptAI/openadapt-flow` | `80dc49b7296e5e6999b04124f26a647047a14b95` | MIT | demonstration → program compilation, deterministic replay, verification |

---

## 1. What UFO actually does

UFO's knowledge substrate names **four sources**: offline help documents,
online (Bing) search, self-experience from its own successful runs, and
user demonstrations. Each has a `Retriever` subclass over a FAISS vector
store with HuggingFace embeddings (`ufo/rag/retriever.py`), and
`AppAgent.context_provision()` builds whichever indexers are configured and
injects retrieved text into the agent's prompt.

`ufo/experience/summarizer.py` takes execution logs, asks a model to
summarise them into JSON, and writes that into an experience database.

**The four-source taxonomy is the valuable part. The delivery mechanism is
not what Kalpavriksha wants.** UFO's knowledge reaches execution as *text
in a prompt*: the model reads retrieved prose and decides what to do.
Kalpavriksha's knowledge reaches execution as *structured data a
deterministic path consults* — `AppKnowledgeProfile`, `Fact`,
`KnowledgeType`. Those are different architectures, and adopting UFO's
would mean routing every desktop step back through a model. That is the
opposite of the direction this codebase has been moving.

UFO also has no epistemology. A retrieved chunk is a chunk; there is no
`DOCUMENTED` / `OBSERVED` / `INFERRED` / `UNKNOWN` distinction and no
requirement that a fact cite how it was learned. Kalpavriksha's `Fact`
refuses to exist without a source. That discipline must survive contact
with anything imported here.

**Steps Recorder is excluded on the founder's instruction and on the
merits.** UFO's demonstration capture shells out to `psr.exe`, which
Microsoft has deprecated. The *record → summarise → store → retrieve →
apply* shape is worth having; that particular capture binding is not.

---

## 2. What openadapt-flow actually does

This is the closer match, and the more useful of the two.

A recording is compiled into a **workflow program IR**: states, guarded
transitions, an action leaf per action state, typed parameters, loops,
branches, `wait_until` predicates, and exception handlers. Its own design
document states the governing idea plainly — *treat a demonstration as
evidence, not as a specification, and compile it toward a program*.

Four properties are directly relevant to us:

**Zero model calls on the healthy path.** All model use is confined to
compile time. A validated program replays deterministically. This is
exactly the property the founder asked for: do not invoke a model to
rediscover "what should I click next" for an operation already learned.

**Guards halt by default.** A `Guard` is a precondition evaluated on the
step's entry frame; when it does not hold, `on_unmet` decides, and `halt`
is the default — described in-source as *"the safe direction for an unmet
precondition."* Timeouts halt rather than proceed. Bounded worklists halt
rather than run unbounded. A placeholder is treated as fail-safe. This is
the same instinct the Desktop Executive already shows when it refuses to
type into a window it cannot confirm is in front.

**A pre-act identity gate.** The action leaf is described as *resolve
target, pre-click identity gate, act, verify postconditions* — the identity
check sits immediately before the act, not earlier. Independently, that is
the correction the live desktop already forced on this codebase: focus
confirmed at the moment of action, because a check made seconds earlier is
worthless on a contended desktop.

**Action success and effect verification are different questions — and
this one matters beyond desktop work.** openadapt-flow reports a fault-model
study finding that **5 of 7 transactional fault classes are silently
mishandled by screen verification**: a partial save, a phantom optimistic-UI
success, a duplicate submission, a lost update, and a double-delivered
click all leave the screen reading "saved" while the record is wrong or
missing. Their `EffectVerifier` therefore reads the *system of record*,
never the screen.

That finding lands on Kalpavriksha directly. The trusted web-AI lane
currently verifies a *screen text region*. For "did Gemini answer" that is
the right substrate — the screen genuinely is the system of record for a
chat reply. But the moment this lane is pointed at anything that writes a
record, screen verification stops being sufficient, and the existing
`Evidence`/`Verification` architecture should be told so before that
happens rather than after.

**Capture is a separate, optional package.** `desktop_record.py` lazily
imports `openadapt_capture` behind an extra, and declares only the slice of
its interface it uses as a `Protocol` so the module type-checks without it.
That is a well-behaved seam: it makes `openadapt-capture` a candidate small
library dependency rather than a framework adoption.

---

## 3. The matrix

`PORT` = adapt the mechanism into an existing Kalpavriksha owner.
`REJECT` = do not take it, with the reason stated.
`REFERENCE` = the idea informs design; no code moves.

| External mechanism | Kalpavriksha owner | Already built? | Decision | Why |
|---|---|---|---|---|
| UFO help documents as a knowledge source | `app_knowledge` (`Fact`, `DOCUMENTED`) | Yes — `DOCUMENTED` facts require a citation already | **REFERENCE** | The concept is already ours and stricter. Nothing to import. |
| UFO online/Bing retrieval | none | No | **REJECT (this tranche)** | Adds a network dependency and an un-sourced trust path. A retrieved page is not `DOCUMENTED` unless it is first-party and cited. |
| UFO self-experience learning | `Mission` + `Evidence` + `Verification` + Promotion Review | Partly — evidence exists, promotion exists; "successful run becomes reusable procedure" does not | **PORT (adapted)** | Take the idea, bind it to *verified* evidence. `ExecutionResult.success` alone must never promote. |
| UFO user demonstrations | none | No | **PORT (adapted)** | Valuable, but not via Steps Recorder. |
| UFO `Retriever` (FAISS + embeddings) | none | No | **REJECT** | Deterministic keys (`site` + `operation`) cover the current need. A vector store is unjustified complexity at one procedure. |
| UFO `ExperienceSummarizer` (LLM → JSON) | none | No | **REJECT (as implemented)** | Summarising logs with a model invents detail. Our procedure should be compiled from observed evidence, not narrated by a model. |
| UFO `context_provision` (knowledge → prompt) | — | — | **REJECT** | Routes every step back through a model. Kalpavriksha consults data deterministically. |
| UFO HostAgent / AppAgent orchestration | Planner, Broker, Mission Control | Yes | **REJECT** | We have these owners. The founder's rule: port the mechanism, not the architecture. |
| OpenAdapt recording | Desktop Executive | No | **PORT or small LIBRARY** | `openadapt-capture` is optional and lazily imported; decide by size once a demonstration is actually needed. |
| openadapt-flow Workflow IR | `app_knowledge` (new `OperationalProcedure`) | No | **PORT (heavily reduced)** | Take steps + preconditions + expected observations + success condition. Do **not** take loops, subflows, typed parameters, exception handlers — no demonstrated need. |
| openadapt-flow compiler / induction | — | No | **REJECT (this tranche)** | 1351 lines of induction exists to generalise across multiple traces. We have one operation and one trace. |
| Deterministic replay, zero model calls on the healthy path | Desktop Executive + provider | No | **PORT** | This is the founder's Phase 6 requirement, and the single most valuable idea in either project. |
| Guards halting on unmet precondition | Desktop Executive | **Yes, already** | **REFERENCE** | `TypeIntoWindowAction` already refuses when the window is not confirmed foreground. Independently arrived at; worth recording that a mature project chose the same default. |
| Pre-act identity gate | Desktop Executive | **Yes, already** | **REFERENCE** | Live evidence forced the same ordering here. Confirms the correction was right. |
| Drift → halt with evidence, never improvise | new procedure replay | No | **PORT** | Report expected vs actual and where it stopped; mark the procedure for revalidation. Never rewrite it from one failure. |
| Effect verification against a system of record | `Verification` / `Evidence` | No — current verification reads the screen | **REFERENCE now, ESCALATE** | Their fault-model evidence says screen verification silently mishandles 5 of 7 transactional fault classes. Not a blocker for chat replies; a real one before this lane touches anything that writes a record. Recorded as a finding for founder decision, not silently patched. |
| OpenAdapt control plane / runner / planner | Runtime, Mission Control | Yes | **REJECT** | Second runtime. Forbidden. |

---

## 4. What this means for the immediate blocker

The Gemini rename is the right first integration precisely because it is
small and already half-learned. The acquisition cycle already produced the
observed facts a procedure needs:

```
conversation menu   ctl=50011 MenuItem  "Open menu for conversation actions"
Rename              ctl=50011 MenuItem  "Rename"
dialog              ctl=50032 Window    "Rename this chat"
edit field          ctl=50004 Edit      "Rename this chat"
cancel              ctl=50000 Button    "Cancel"
```

The remaining unknown is not *what the controls are* but *which step of the
sequence fails* — `rename_conversation()` returns a bare boolean, so a
failure is indistinguishable from any other failure. Under the ported
model that is precisely what a procedure fixes: each step carries its own
expected observation, so a failure names the step it stopped at.

**That is the smallest honest next increment**, and it is worth more than
importing anything: step-level failure reporting first, then the procedure
record, then replay.

---

## 5. Attribution

If and when code is adapted from either project, the adapted files must
carry the upstream repository, the commit inspected, the MIT licence, and
what was changed. Nothing in this document has moved code yet, so nothing
carries attribution yet.

Neither project's name may appear in product control flow. Once a
mechanism is assimilated, Kalpavriksha owns it.
