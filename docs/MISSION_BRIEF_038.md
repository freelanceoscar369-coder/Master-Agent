# Mission Brief 038 — Provider Deadline & Adaptive Timeout Architecture

**Status:** Architecture — canonical, implementation-ready.
**Date:** 2026-07-31
**Type:** Architecture only. No code, no implementation, no frozen edits,
no ADR ratified.
**Depends on:** ADR-0002, ADR-0011, ADR-0016, ADR-0017, ADR-0018, MB033,
MB036, MB037.

This document is the authoritative architectural specification for
timeout and deadline management in Kalpavriksha. Every future
implementation brief in this area follows it, and none should need to
reopen a question settled here.

---

## 1. The core architectural finding

### 1.1 What the system does today

Two facts, verified directly in the source:

1. **`Task` and `Objective` contain no deadline concept of any kind.** A
   search for `timeout|deadline` across `mission_control/tasks.py`
   returns nothing. The mission layer has no vocabulary for time.
2. **`OllamaProvider` holds a single `self._timeout`**, taken from
   `OllamaConfig.timeout_seconds` (default 120 s), and applies it
   unchanged to every call it makes — `/api/tags` health probes and
   `/api/generate` planning requests alike.

So the system has exactly one number where it needs a family of them, and
that number lives in the layer least equipped to know what the work is.
An adapter knows it holds a string and a socket. It cannot know whether
the string is a health probe or a twenty-six-capability planning prompt,
and there is no vocabulary in which it could be told.

### 1.2 The production evidence

| Brief | Workload | Budget | Result |
|---|---|---|---|
| MB033 | short execution prompt | 120 s | 22.8 s — correct |
| MB036 | 26-capability planning prompt | 120 s | `no answer within 120s` |
| MB036 | same prompt | 540 s | planned correctly |
| MB037 | larger planning objective | 540 s | `no answer within 540s` |

The provider was healthy in every row. `gemma4:latest` was doing exactly
what it had been asked to do. **A healthy provider was reported as failed,
twice, by a system with no means of telling the difference.**

### 1.3 Why raising the number is not the fix

Three arguments. Each is independently sufficient.

**A — The failure moves; it does not leave.** A timeout large enough for
planning is a timeout under which a *dead* daemon takes nine minutes to
report. Today Kalpavriksha answers `is Ollama running at
http://localhost:11434?` in about a second — a genuinely good failure,
built deliberately in MB033. A single large number destroys it.
Configuration can only choose which of the two failure modes to suffer;
it cannot escape the choice.

**B — One number cannot describe two different physical processes.**
Local inference latency is *prefill* (work proportional to input) plus
*decode* (work proportional to output). Planning is enormous-in,
moderate-out. Execution is small-in, small-out. These are not one
distribution with two means; they are two shapes. A scalar that fits both
constrains neither.

**C — A single wall-clock timeout cannot distinguish thinking from
hanging.** This is the root cause, and it is not a tuning problem. At
second 400 of a planning call, a healthy provider mid-prefill and a
wedged socket are byte-for-byte identical to the caller: connected, no
data. **No timeout value separates them, because the information required
is not being observed at all.** Fixing that means observing something
new — which is an architectural change by definition, not a
configuration one.

### 1.4 The three shifts

Everything in this document follows from three changes of *kind*, not of
degree:

1. **One deadline becomes three.** Total, TTFT, ITL. §4.
2. **A relative duration becomes an absolute instant.** §3.
3. **A constant becomes a derived, recorded value.** §5, §9, §10.

### 1.5 Freeze boundary and phase split

The entire provider-call path — Planner → `PromptExecutor` → Broker →
Provider Adapter → transport — lies **outside the frozen set**.
`planner/`, `missions/`, `ai_infrastructure/`, `providers/`, `dashboard/`
and `launcher/` are writable. `mission_control/` and `runtime/` are
frozen.

| Phase | Scope | Frozen edits | ADRs |
|---|---|---|---|
| **1** | The whole provider-call domain: classification, class bounds, adaptive budgets, three-deadline enforcement, streaming observability, telemetry, configuration precedence, replay reuse, orphan accounting | **none** | **none** |
| **2** | Mission SLA on `Objective`/`Task`, Runtime enforcement at the task boundary, founder cancellation | `mission_control/`, `runtime/` | ADR-0021/22/23 |

**Phase 1 resolves every failure observed to date and requires no
amendment to anything frozen.** Phase 2 adds a real guarantee that
nothing has yet demanded; it should be ratified on its own merits rather
than carried in on the back of a defect fix.

---

## 2. Timeout ownership hierarchy

```
┌─────────────────────────────────────────────────────────────────────┐
│ MISSION CONTROL                                          Phase 2    │
│   OWNS: the mission SLA — one absolute instant, T_mission.          │
│   "This objective must be finished by T."                           │
│   Provides CEILINGS ONLY. Derives no budget. Enforces no call.      │
│   Knows nothing of prompts, tokens, providers or models.            │
├─────────────────────────────────────────────────────────────────────┤
│ DISPATCHER                                              unchanged   │
│   OWNS: NOTHING time-related.                                       │
│   Orders strictly by dependency. A deadline must never reorder      │
│   work — D-11.                                                      │
├─────────────────────────────────────────────────────────────────────┤
│ RUNTIME                                                  Phase 2    │
│   OWNS: enforcement at the TASK boundary, and task-level retry      │
│          with escalation (MB024, unchanged).                        │
│   Derives T_task = min(T_mission, now + task_ceiling).              │
│   Does NOT compute a call budget. Does not know what a prompt is.   │
├─────────────────────────────────────────────────────────────────────┤
│ BROKER                                                   Phase 1    │
│   OWNS: BUDGET DERIVATION — the single place in Kalpavriksha that   │
│          turns facts about work into milliseconds.                  │
│   Emits CallBudget{total, ttft, itl} on the Selection, with its     │
│          full derivation.                                           │
│   Does NOT enforce. Does NOT retry. Does NOT schedule.              │
├─────────────────────────────────────────────────────────────────────┤
│ PROVIDER ADAPTER                                         Phase 1    │
│   OWNS: ENFORCEMENT of the budget it was handed, transport-fault    │
│          retry, and honest reporting of what it observed.           │
│   Never invents, extends, re-derives or pads a budget.              │
│   Never retries a timeout.                                          │
├─────────────────────────────────────────────────────────────────────┤
│ TRANSPORT                                                Phase 1    │
│   OWNS: the socket deadline. Mechanism only, never policy.          │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.1 The non-overlap rule

> **Exactly one layer owns the SLA (Mission Control). Exactly one layer
> computes a budget (Broker). Exactly one layer enforces per call
> (Provider Adapter). Exactly one layer enforces per task (Runtime).**

Four verbs — *own*, *compute*, *enforce-per-call*, *enforce-per-task* —
each appearing exactly once. That is the property to test for.

It is also the property that decays first, and the decay has a
predictable shape: an adapter author debugging a flaky call adds "just a
little headroom". At that moment two layers compute, the recorded budget
stops describing the real one, and every downstream number becomes
fiction. **D-3 exists to make this impossible** — an adapter with no
budget refuses rather than defaults, so there is never a local constant
to nudge.

### 2.2 Why the Broker owns derivation

Budget derivation could plausibly sit in the Runtime, the executor, or
the adapter. It belongs to the Broker for four reasons no other layer
satisfies together:

1. **It already reasons about provider performance.**
   `ProviderProfile.latency_ms` is an existing input.
2. **It already receives the work's constraints.**
   `SelectionRequest.max_latency_ms` exists today and is already
   documented as *a fact about the work, never a preference about the
   provider* (MB032).
3. **It already produces a durable, replayable decision.** A budget
   recorded anywhere else would be a second record requiring its own
   replay story; on the `DecisionRecord` it inherits MB032's
   byte-identical replay guarantee unchanged.
4. **ADR-0018 forbids the alternative.** Its Consequences name *a ranking
   function growing outside the Broker* as the single failure mode that
   would invalidate the design. A budget is a judgement about provider
   performance. Computing it elsewhere is exactly that failure.

### 2.3 Mission Control's ownership, stated narrowly

**Mission Control owns the SLA and nothing else about time.** It answers
*"by when must this objective be done?"* It never answers *"how long may
this call take?"* — that question requires knowing what a prompt is, and
the mission layer deliberately does not.

---

## 3. Deadline propagation

### 3.1 D-1 — absolute instants, never relative durations

**A deadline propagates as an absolute instant on a monotonic clock.**

A relative duration is re-based at every hop. Five layers each faithfully
honouring "you have 60 seconds" honour *five* sixty-second windows. The
error is invisible in tests (one hop, no contention), compounds under
load, and grows with every layer added — so the architecture degrades
precisely as the system matures, which is the worst possible failure
curve.

An absolute instant is idempotent under propagation. Passing it through
any number of layers cannot extend it. A layer that forgets to subtract
its own overhead cannot cause a bug, because there is no subtraction to
forget.

**Clock discipline.** Monotonic for all arithmetic; wall clock for
records and display only. An NTP step, a DST transition or a manual clock
change must never extend or collapse a live deadline.

### 3.2 The propagation path

```
  Founder objective
        │
        │  T_mission = now + mission_sla                  [Mission Control, Ph2]
        ▼
  Objective(deadline = T_mission)                         ← CEILING ONLY
        │
        │  T_task = min(T_mission, now + task_ceiling)    [Runtime, Ph2]
        ▼
  Task(deadline = T_task)
        │
        │  the caller states FACTS about the work — never a timeout:
        │     request_class, prompt, expected output shape
        ▼
  SelectionRequest(request_class=…, deadline=T_task)  [Planner / ModelRouter]
        │
        │  BROKER DERIVES and RECORDS, before the call:
        │     ttft  = f(class, prompt_size, profile.prefill_rate)
        │     itl   = f(profile.decode_rate)           ← size-independent
        │     total = f(class, prefill + decode estimate)
        │     all three clamped to (T_task − now)
        ▼
  Selection(provider_id, CallBudget{
              total_deadline, ttft_deadline, itl_ms, derived_from })
        │
        ▼
  PromptExecutor   ── passes the CallBudget through UNCHANGED ──►
        │
        ▼
  Provider Adapter    enforces all three
        │
        ▼
  Transport           socket deadline = total_deadline
```

### 3.3 The clamp is load-bearing

Every layer above the mission **proposes**. The mission SLA **disposes**.
No derived budget, configured floor, or explicit override may exceed
`T_task − now`.

**D-12 — admission control.** If `T_task − now` is already below the
request class's floor, the correct behaviour is to **refuse before
calling**, not to issue a call that is arithmetically guaranteed to time
out. A doomed call wastes the remaining SLA, will orphan compute (§8.3),
and produces a timeout record that misattributes the failure to the
provider. This is *budget starvation* — F7 in §11.

When a clamp bites, the fact is recorded (§10). A budget silently reduced
by a ceiling, with no record, produces the most confusing failure this
architecture can generate: a timeout at a duration matching nothing in
any configuration file.

---

## 4. The three deadline model

### 4.1 Three questions, three physical phenomena

| Deadline | Question | Physical phenomenon | Scales with |
|---|---|---|---|
| **TTFT** | *Did it start?* | **prefill** — the forward pass over the input | **input size** |
| **ITL** | *Is it still alive?* | **decode cadence** — per-token generation | **nothing** — a provider/model constant |
| **Total** | *Is this still worth waiting for?* | **overall cost** — the whole call | expected output + mission SLA |

**No single number answers more than one of these questions.**

The decisive evidence is the last column. **The three quantities scale
with different variables.** TTFT must grow with prompt size — that is
precisely what MB036 and MB037 violated. ITL is roughly constant for a
given model on given hardware and must *not* grow with prompt size: a
model that has begun emitting tokens emits them at its own steady rate
regardless of how large the prompt was. Total depends on expected output
and the mission ceiling.

Three quantities that scale with different variables cannot be
represented by one variable. Collapsing them is not a simplification; it
is a category error, and it is the category error the system currently
ships.

### 4.2 What each deadline buys

**TTFT** fixes the observed defect. A planning prompt legitimately needs
a long prefill window; an execution prompt does not. Making this the
size-dependent deadline lets planning be slow to *start* without making
everything else slow to *fail*.

**ITL** recovers the fast failure that a large TTFT would otherwise cost.
Once tokens are flowing, a gap much larger than the observed inter-token
interval means the provider has stalled — detectable in **seconds**, not
minutes, even under a ten-minute total budget. **This is what makes a
generous total budget safe.** Without ITL, a decode stall is invisible
until Total expires, and every minute added to Total is a minute added to
the detection gap.

**Total** keeps a mission finite. A perfectly healthy stream that runs
forever is still a mission that never completes. Total is also the only
one of the three the mission SLA can bound directly.

### 4.3 Where each is undefined

Not every class has all three (§6.4). Embeddings are single-shot: there
is no stream, so **ITL is undefined rather than merely different**, and
TTFT collapses into Total. A class whose *set of applicable deadlines*
differs from another's is proof that the difference between classes is
structural, not numeric.

---

## 5. Adaptive budgeting

### 5.1 Division of authority

> **Mission Control provides ceilings. The Broker derives budgets. The
> Provider Adapter enforces them.**

### 5.2 Derivation inputs

| Input | Feeds | Phase |
|---|---|---|
| Request class | floors and ceilings on all three deadlines | 1 |
| Prompt size | TTFT | 1 |
| Expected output size | Total | 1 |
| Provider profile — prefill rate, decode rate | TTFT, ITL, Total | 1 declared / 2 measured |
| `supports_streaming` | whether ITL is enforceable at all | 1 |
| Mission SLA remaining | hard clamp on all three | 2 |
| **Host load** | **not a budget input — §10.2, R-2** | — |

### 5.3 Shape, not formula

Architecture fixes the shape and the clamp. Coefficients belong to an
implementation brief and **must be measured on the founder's hardware**,
never guessed:

```
  ttft_budget  = clamp( prompt_tokens / profile.prefill_rate × k_class,
                        class.ttft_floor, class.ttft_ceiling )

  itl_budget   = clamp( profile.expected_itl × k_stall,
                        class.itl_floor, class.itl_ceiling )

  total_budget = clamp( ttft_estimate + expected_tokens / profile.decode_rate,
                        class.total_floor, class.total_ceiling )

  every budget = min(budget, T_task − now)                         ← §3.3
```

Two properties are architectural and non-negotiable:

- **Deterministic.** Identical inputs must yield an identical budget.
  This is what keeps MB032's byte-identical replay true (§9).
- **Recorded with its derivation.** Not just the number: the class, the
  size estimates, the profile, and which constraint bound it (§10).

### 5.4 Estimates will be wrong, by design

The adapter cannot see the provider's tokenizer, so `prompt_tokens` is an
approximation of an approximation. The architecture therefore never
*trusts* the estimate: the estimate sets the budget, and the **observed**
TTFT and ITL are recorded so the estimate can be corrected against
measured reality.

This is ADR-0017 Decision 5's posture toward quality — declaration is a
starting point, measurement replaces it where both exist — applied to
latency. It is also why §10's telemetry is load-bearing rather than
decoration: without it the budgets can never improve.

---

## 6. Request classification

### 6.1 Why timeout behaviour differs by workload

Workload classes differ **structurally**, not merely numerically:

- **Planning** — enormous input, moderate output. TTFT dominates; Total
  is mostly prefill. Long TTFT is *normal* and must not read as failure.
- **Code generation** — small input, long structured output. Decode
  dominates. A long TTFT here is a genuine symptom, not expected
  behaviour.
- **Interactive** — small in, small out, a human waiting. TTFT must be
  short and a slow start is itself the failure, because the value of the
  answer decays with latency.
- **Embeddings** — single-shot, no stream. ITL undefined (§4.3).
- **Verification** — see §6.4.

The same wall-clock number means "healthy" in one class and "broken" in
another. That is the definition of a classification problem.

### 6.2 D-4 — classification is a property of the request

**`request_class` is a field on `SelectionRequest`, set by the caller,
drawn from a closed vocabulary.**

It is a **fact about the work**, exactly like `sensitive` and
`requires_strong_reasoning` — MB032's rule that every field on a routing
request describes the work and never expresses a preference about the
provider. The Planner sets `planning`. It does not set a timeout, and
must not (D-11).

### 6.3 `request_class` is not `capability`

Two orthogonal axes. Conflating them is the obvious mistake:

| Axis | Answers | Consumed by | Examples |
|---|---|---|---|
| `capability` | *what kind of intelligence?* | **routing** | `reasoning`, `coding`, `vision.ocr` |
| `request_class` | *what shape is the interaction?* | **budgeting** | `planning`, `code_generation`, `embedding` |

Planning is `capability="reasoning"` **and**
`request_class="planning"` — two independent facts, two fields, two
consumers.

### 6.4 The taxonomy

| Class | TTFT | ITL | Total | Producer today | Notes |
|---|---|---|---|---|---|
| `planning` | long, size-driven | yes | long | ✅ MB036 Planner | The class the defect lives in |
| `execution` | short | yes | moderate | ✅ ModelRouter callers | Default class |
| `code_generation` | short | yes | long | ⚠️ not yet | `capability="coding"` exists; no caller emits it |
| `interactive` | **very short** | yes | short | ⚠️ not yet | Latency-sensitive; value decays with delay |
| `embedding` | n/a | **n/a** | short | ⚠️ not yet | Single-shot; Memory Layer 5 unimplemented |
| `verification` | short | yes | moderate | ⚠️ not yet | See below |

**On `verification`.** MB035's Generated Text Verifier is deterministic
and **never calls a provider** — it re-derives an observation from the
artefact by measurement. So no verification workload reaches the Broker
today. The class is defined because a *semantic* verification workload
would need one, and the vocabulary is more valuable frozen early than
grown ad hoc. It is worth recording that such a workload has not been
sanctioned: ADR-0017 Decision 5 declined model-judging-model, and
defining a budgeting class does not reverse that.

**Four of six classes have no producer.** That is not an argument against
defining the vocabulary — a closed vocabulary should be settled once. It
*is* an argument for a test asserting producer-less classes are never
emitted, so the taxonomy cannot quietly become a wish list.

---

## 7. Retry ownership

### 7.1 The rule

> **A retry belongs to the layer that owns the failure's meaning.**

| Layer | Retries | Never retries |
|---|---|---|
| **Provider Adapter** | Transport faults only — connection refused, DNS failure, socket reset. Nothing was computed; the retry is free. Bounded, **inside the budget**. | Timeouts. Model errors. 4xx. Anything where the provider did work. |
| **Runtime** | Task failures — mechanical retry with escalation (MB024, unchanged). | Provider calls directly; it does not know what one is. |
| **Broker** | Nothing. It **decides**. A retry that re-enters the Broker is a *new decision* with a *new record*. | — |
| **Mission Control** | Nothing at this level. Mission-level re-attempt is a founder decision. | — |
| **Dispatcher** | Nothing. | — |

This resolves a live ambiguity: `OllamaProvider.max_attempts` and the
Runtime's mechanical retry are two retry mechanisms with no written
boundary between them. The rule above is that boundary — a transport
fault means nothing above the adapter, so the adapter owns it; a failed
task means something to the mission, so the Runtime owns it.

### 7.2 D-5 — every retry happens inside the budget

**A retry never extends a deadline.** No sequence of retries at any layer
can exceed `T_task`, because every attempt shares one absolute instant
(D-1). This single property makes *retry storm* structurally impossible
rather than merely discouraged (F5, §11).

### 7.3 D-6 — a timeout is never retried under the same budget

MB033 established this for the adapter; it is promoted to architecture,
at every layer.

A timeout is **evidence that the budget was wrong**. Repeating the call
under the same budget is arithmetically guaranteed to fail again and
costs the founder the same wall-clock time twice. A retry after timeout
requires a **new Broker decision** with a new budget — visible,
attributable, and countable.

---

## 8. Cancellation propagation

### 8.1 D-7 — cancellation is a deadline set to now

One mechanism, four triggers:

| Trigger | Mechanism |
|---|---|
| Deadline expiry | the deadline is already now |
| Mission abort | `T_mission := now`, propagates down §3.2 unchanged |
| Founder cancellation | same, initiated from the console |
| Provider failure | that call is over; siblings cancel via mission abort |

Unifying these yields **one propagation path** to build, test and reason
about, rather than four that agree until the day they do not.

### 8.2 D-8 — cooperative, never preemptive

**No thread is killed.** Each layer checks its deadline at its own
boundary. A provider call that cannot be interrupted mid-flight is
**abandoned**: the caller stops waiting, the result is discarded, and the
abandonment is recorded as an outcome distinct from a timeout.

Preemption is rejected (R-4) because killing the caller's thread does
nothing about the daemon at the other end of the socket — which is the
half that actually matters.

### 8.3 Orphan compute and its prevention

**This is the most operationally dangerous element of the design.**

An abandoned call does not stop the provider. The daemon keeps
generating. For a local provider this is not merely wasted electricity:
**Ollama serialises work per model**, so an orphaned planning call
continues to occupy the model and **the next call queues behind work
nobody is waiting for**.

The compounding failure is the danger. A founder who cancels and
immediately retries experiences the retry as mysteriously slow — and the
budget derived for that retry assumed an *idle* provider, so it will very
likely time out too, producing a second orphan. That is self-sustaining
degradation, and nothing in the current architecture would even record
it.

Architectural requirements:

1. **Attempt real cancellation at the transport.** Closing the connection
   is the only lever available. *Whether a given provider actually halts
   generation on disconnect is a per-adapter fact that must be declared
   in the profile and verified by test, never assumed.*
2. **Record every abandonment** — instant, provider, believed occupancy.
   An orphan that is not recorded cannot be reasoned about.
3. **Track in-flight occupancy per local provider.** The Broker must be
   able to see that a serialising provider is busy, because selecting an
   occupied one is a decision made on false premises.
4. **Admission must account for occupancy.** Either wait, or derive a
   budget that includes the queue, or select elsewhere — but never derive
   a budget as though the provider were idle.
5. **Never issue a doomed call** (D-12). A call that cannot finish inside
   the remaining SLA is a guaranteed future orphan.

### 8.4 Propagation directions

- **Down (deadlines):** mission → task → selection → call → socket.
- **Up (facts):** provider outcome → execution record → task failure →
  Mission Control event → history, Dashboard, Memory. Unchanged from
  MB037 — cancellation produces evidence by the same route as any other
  outcome and needs no new path.

### 8.5 Founder cancellation requires Mission Control support

No verb exists today. This is **the same gap MB037 left open for
pause/resume** — see §16.1.

---

## 9. Replay architecture

### 9.1 D-9 — replay reuses recorded budgets; it never recomputes them

Three reasons, each independently sufficient:

1. **MB037's guarantee.** Replay never executes and never contacts a
   provider. A recomputed budget is a number that governed nothing —
   fiction presented as history.
2. **MB032's determinism.** A decision replays against the policy and
   profiles *of its time*, not today's. The budget is part of that
   decision; reconstituting it from current inputs breaks the guarantee.
3. **Silent rewriting.** A recomputed budget changes as the capability
   catalogue grows — the planning prompt lengthens with every new
   Executive. Last month's mission would replay with a budget it never
   had, and the record would quietly stop being true.

### 9.2 How a timeout decision becomes evidence

The `CallBudget` and its derivation are written to the `DecisionRecord`
**at the moment of decision, before the call is made** — never after it
returns.

This matters for the same reason MB035's expectations matter: a budget
recorded after the outcome is known is unfalsifiable. Recorded in
advance, it is a **prediction** that the observed TTFT and ITL either
vindicate or refute. Every provider call becomes a small self-scoring
experiment, and that is precisely what lets §10 distinguish *the budget
was too small* from *the provider was too slow*.

### 9.3 The Policy Simulator is the deliberate exception

The Policy Simulator (ROADMAP item 8) asks a different question: *what
would this budget policy have done?* It **should** recompute — and must
label the result an **estimate**, never a fact, exactly as the roadmap
already requires of it. Replay reports what happened; the simulator
reports what would have. Blurring them manufactures confidence at the
worst possible moment.

---

## 10. Telemetry

Architectural requirements only. These extend `ExecutionRecord`; **no new
record type is required**, and per R-10 no new event type either.

### 10.1 Required for every provider call

1. **The budget granted** — all three deadlines.
2. **Its derivation** — request class, prompt-size estimate,
   expected-output estimate, provider profile used, policy version.
3. **Which constraint bound it** — class floor, class ceiling, adaptive
   value, call override, or mission clamp.
4. **Observed TTFT.**
5. **Observed ITL** — at minimum token count and maximum inter-token gap.
6. **Outcome**, at §11 resolution: completed, `TIMED_OUT_PREFILL`,
   `STALLED_DECODE`, `TIMED_OUT_TOTAL`, abandoned, transport fault,
   refused-for-starvation.
7. **Retries**, and **which layer** performed them.
8. **Clock basis** — the monotonic start instant.
9. **Orphan state** — whether the call was abandoned, and whether the
   provider was believed still occupied.

### 10.2 Host state

**Record it as an observation; never feed it into budget derivation.**

Recording CPU pressure, memory pressure, whether another model was
loaded, and per-provider in-flight count is valuable — it is often the
difference between *the model is slow* and *the laptop was compiling*.
But it must remain observational, because a budget that varies with load
is non-deterministic and therefore non-replayable (R-2), which breaks
MB032.

The rule: **host state may explain a timeout; it may never determine a
deadline.** Load belongs to *admission* — whether to start now — never to
*budget* — how long to allow once started.

### 10.3 The two fields most easily omitted, and most needed

**Which constraint bound the budget (3).** Without it, "it timed out"
does not say whether to raise the class floor or the mission SLA. This
single field is the difference between a diagnosable system and one where
every fix is a guess. Its absence is what would let K-3 happen.

**Observed against estimated (4, 5 versus 2).** This is what separates
*budget too small* from *provider too slow* — different defects,
different owners, and today the same log line.

### 10.4 A timeout is a measurement

Every timeout is a **provider-performance fact**. ADR-0017 Decision 5's
future benchmark store should consume them: a provider that repeatedly
misses a well-derived budget is slower than it declares, and that is
exactly the declared-versus-observed gap the Broker exists to close.
ADR-0018's learning loop needs this data before it can propose anything.

---

## 11. Failure matrix

| # | Failure | Signature | Today | Detected by | Response | Key evidence |
|---|---|---|---|---|---|---|
| **F1** | **Silent stall (prefill)** | connected, zero bytes, healthy socket | **indistinguishable from healthy planning — the MB036/MB037 defect** | TTFT deadline | `TIMED_OUT_PREFILL` | ttft budget, observed wait, prompt size |
| **F2** | **Decode stall** | tokens flowed, then stopped | invisible until Total expires — minutes late | ITL deadline | `STALLED_DECODE` | last-token instant, itl budget, tokens so far |
| **F3** | **Dead daemon** | connection refused | ✅ already fast and correct (MB033) | transport | `UNAVAILABLE` | unchanged — must be preserved |
| **F4** | **Healthy but too slow** | completes, past budget | reported as failure, no distinction from F1 | Total deadline | `TIMED_OUT_TOTAL` | observed throughput vs estimate |
| **F5** | **Retry storm** | same call repeated, each failing | possible — two unbounded retry layers | D-5 + D-6 | structurally impossible | retry count, per layer |
| **F6** | **Orphan compute** | call abandoned, daemon still generating | invisible; silently degrades the *next* call | abandonment record + occupancy tracking | record, attempt transport cancel, account for occupancy | abandoned instant, occupancy belief |
| **F7** | **Budget starvation** | remaining SLA < class floor | issues a doomed call | admission check (D-12) | refuse before calling | which constraint bound |
| **F8** | **Wrong-budget cascade** | timeout → retry → identical timeout | plausible today | D-6 — retry needs a new Broker decision | new decision, or fail | both decisions, both budgets |
| **F9** | **Clock skew** | NTP step mid-call | would extend or collapse the deadline | monotonic arithmetic (D-1) | unaffected | clock basis |

**F1, F2, F6 and F7 are not detectable at all in the current
architecture.** F5 and F8 are not currently prevented. F3 is the one case
the system already handles well, and preserving it is an explicit
constraint on any change (§1.3 A).

---

## 12. Architectural decisions

| # | Decision |
|---|---|
| **D-1** | Deadlines propagate as absolute instants on a monotonic clock, never as relative durations. |
| **D-2** | The Provider Adapter contract must expose a progress signal. Streaming is the mechanism; observability is the requirement. Non-streaming providers are legal, declared, and degrade to `ttft == total` with ITL unenforceable. |
| **D-3** | An adapter that receives no budget refuses the call. It never invents, extends, pads or re-derives one. |
| **D-4** | `request_class` is a field on `SelectionRequest`, set by the caller, from a closed vocabulary. It is a fact about the work. |
| **D-5** | Every retry, at every layer, happens inside the budget. A retry never extends a deadline. |
| **D-6** | A timeout is never retried under the same budget. A retry after timeout requires a new, recorded Broker decision. |
| **D-7** | Cancellation is a deadline set to now. One mechanism, four triggers. |
| **D-8** | Cancellation is cooperative, never preemptive. An uninterruptible call is abandoned, and the abandonment recorded. |
| **D-9** | Replay reuses recorded budgets and never recomputes them. Only the Policy Simulator recomputes, and must label its output an estimate. |
| **D-10** | Configuration supplies bounds `(floor, ceiling)` at every level, never a single scalar. |
| **D-11** | A deadline must never influence dispatch order. Ordering is Mission Control's, resolved from `depends_on` alone. |
| **D-12** | Admission control: if the remaining SLA is below the class floor, refuse before calling rather than issue a doomed call. |

### 12.1 Streaming: the two hard constraints

**Streaming must never leak reasoning to the founder page.** MB037
forbids displaying internal LLM reasoning. The heartbeat monitor consumes
a **token count and a timestamp** — never text. It observes *that* tokens
arrive, never *what* they say.

**Streaming must never change verification.** MB035 verifies a complete
artefact against an expectation stated in advance. A partial response is
never verified, never cached, and never written to the Prompt Library. A
stream that ends early is a **failure**, not a short answer.

### 12.2 Provider timeout lifecycle

```
   t0  ADMITTED
       │  CallBudget received.
       │  no budget           → REFUSE (D-3)
       │  SLA < class floor   → REFUSE (D-12, starvation)
       ▼
   t1  CONNECTING ─── transport fault ──► bounded retry, inside budget
       │                                   exhausted ──► UNAVAILABLE
       ▼
   t2  AWAITING FIRST TOKEN
       │  ttft_deadline passed ──► TIMED_OUT_PREFILL      (F1)
       ▼
   t3  STREAMING
       │  no token for itl_ms   ──► STALLED_DECODE        (F2)
       │  total_deadline passed ──► TIMED_OUT_TOTAL       (F4)
       ▼
   t4  COMPLETE ──► full text ──► MB035 verification ──► cache / library
```

**Four distinct timeout outcomes replace today's single `TIMED_OUT`.**
*It never started*, *it stopped halfway* and *it was healthy but too
slow* have different causes, different owners and different fixes. Today
they are one log line.

### 12.3 Why the Planner never becomes a scheduler

MB037 established that `Step.priority` is descriptive, never directive,
and that Mission Control alone resolves order. A budget that could
reorder work would make the Planner a scheduler through the side door: it
would set a tight deadline, and tight-deadline work would *effectively*
run first. **Deadlines constrain duration; they never constrain
sequence.** The Dispatcher owning nothing time-related (§2) is what makes
this structural rather than a matter of discipline.

---

## 13. Configuration precedence

**D-10 — every level supplies bounds, never a scalar.** A single number
at any level re-creates the static timeout one layer up, which is the
defect wearing a different hat.

| # | Level | Supplies |
|---|---|---|
| 1 | Global default | floor/ceiling — safety net, never used directly |
| 2 | Provider profile | rates, `supports_streaming` — capability, not policy |
| 3 | **Request class** | floor/ceiling — **the planning-vs-execution fix** |
| 4 | Adaptive computation | a value within (3) |
| 5 | Call override | explicit; recorded *as* an override |
| 6 | **Mission SLA** | hard ceiling — **clamps all of 1–5** |

Levels 1–5 propose; level 6 disposes. An override exceeding the mission
ceiling is **clamped, not honoured**, and the clamp is recorded.

`OllamaConfig.timeout_seconds` becomes the **provider ceiling** (level 2)
and stops being the value planning actually uses. Today it is both, and
that conflation is the bug.

---

## 14. Rejected alternatives

| # | Rejected | Why |
|---|---|---|
| R-1 | Raise the global timeout | Trades a false failure for a nine-minute hang on a dead daemon. §1.3 A. |
| R-2 | Host load as a budget input | Non-deterministic → non-replayable → breaks MB032. Load belongs to admission, never budget. §10.2. |
| R-3 | Per-provider hardcoded timeouts in calling code | Reintroduces provider names into the Brain, which MB032 spent a whole brief deleting. |
| R-4 | Preemptive cancellation (kill the thread) | Unsafe in-process, and does nothing about the daemon — the half that matters. §8.3. |
| R-5 | Retry a timeout under the same budget | Arithmetically guaranteed to fail; burns the founder's wall clock twice. D-6. |
| R-6 | Let the Planner choose its own timeout | The Planner would own a lifecycle concern. MB037 forbids it. §12.3. |
| R-7 | A dedicated "planning provider" with its own config | Routing outside the Broker. ADR-0017. |
| R-8 | No timeout for planning | A hung daemon becomes indistinguishable from work — the defect, maximised. |
| R-9 | Deadlines as relative durations | Re-based at every hop; compounds under load. D-1. |
| R-10 | A new `TIMEOUT` event type | Edits a frozen file for reporting rather than for a guarantee. MB032's `BROKER_DECISION` precedent. |
| R-11 | Budget derivation in the Provider Adapter | Two layers computing — the drift §2.1 warns about. |
| R-12 | One deadline plus a generous margin | Cannot detect F2 at all; the margin *is* the detection gap. §4.2. |

---

## 15. Open reconciliation

Genuine architectural uncertainties. Each records the position taken, so
implementation is unblocked, and what would change it.

| # | Question | Position taken | Would change if… |
|---|---|---|---|
| **⚖1** | Does Mission Control own per-task deadlines, or only the SLA? | **SLA only.** The Runtime derives `T_task`. Keeps the mission layer free of execution vocabulary. | a future brief shows per-task deadlines are needed at submission time — e.g. for admission before dispatch. |
| **⚖2** | Should `T_task` exist at all, or should calls clamp directly to `T_mission`? | **Keep `T_task`.** More defensive; bounds a runaway task without consuming the whole mission. | it proves to be a number nobody can explain — then collapse it into `T_mission`. |
| **⚖3** | Does Ollama halt generation on client disconnect? | **Assume it does not.** Occupancy accounting is required either way. | measurement shows it reliably halts — §8.3 gets cheaper, accounting still stays. |
| **⚖4** | Do `code_generation` and `execution` need separate bounds? | **Defined separately, may share bounds initially.** Both are small-in; they differ in output length. | measurement shows the output distributions overlap — then merge, and keep one name. |
| **⚖5** | May a call override ever exceed the mission SLA? | **No.** A founder extending a deadline mid-mission is really changing the SLA and should be modelled as one. | a concrete workflow appears where per-call extension is meaningful without SLA change. |
| **⚖6** | How do budgets interact with the cost ledger? | **Unresolved.** A generous budget on a paid provider is a generous *spend*; ADR-0017 §9's ledger and these budgets are not yet connected. | the cost ledger ships — then budget and spend need a joint ceiling. |
| **⚖7** | Concurrency. | **Out of scope; single in-flight call assumed**, which is true today. | parallel provider calls are introduced — K-1 becomes sharply worse and needs its own treatment. |

---

## 16. Recommended ADRs — not ratified

| ADR | Subject | Frozen files | Phase |
|---|---|---|---|
| **ADR-0021** | `Objective` carries a mission SLA; `Task` carries a derived deadline | `mission_control/tasks.py` | 2 |
| **ADR-0022** | The Runtime enforces the task deadline at its single funnel | `runtime/engine.py` | 2 |
| **ADR-0023** | Mission lifecycle control: cancel, and a task state to express it | `mission_control/`, `dispatcher.py` | 2 |

**No ADR is required for Phase 1.**

### 16.1 ADR-0023 should absorb MB037's open question

MB037 could not build pause/resume/cancel: Mission Control publishes none
of them, adding them edits frozen files, and building them outside would
create a second orchestration authority. **That is the same decision as
ADR-0023.** Cancellation and pause/resume are one lifecycle amendment;
the founder should make one decision rather than two that must then be
kept consistent.

---

## 17. Architecture risks

**K-1 — Ollama serialises per model.** An abandoned call keeps the model
busy, so the next call queues behind work nobody wants — and its budget
was derived assuming an idle provider, so it likely times out too.
**Highest severity in this document**, because it is self-sustaining.
§8.3 is the mitigation; the measurement spike must precede any
coefficient work.

**K-2 — Prefill estimates depend on a tokenizer the adapter cannot see.**
Early budgets will be wrong. §5.4 mitigates by measuring rather than
trusting, but Phase 1 must ship with generous ceilings and tighten on
evidence.

**K-3 — Class floors become a dumping ground.** Without §10.1's *which
constraint bound it*, every timeout gets "fixed" by raising the planning
floor and the system drifts back to one big number. The telemetry
requirement is what prevents this, which is why it is not optional.

**K-4 — `providers/` grows.** MB033 deliberately kept it small, boring,
and re-exporting nothing. Streaming is more code in the package that most
benefits from being dull. Keep the monitor — count and timestamp — out of
the transport.

**K-5 — Budgeting coupled to verification vocabulary.** Deriving output
estimates from `ExpectedOutcome.min_words` links two independent
subsystems. Must stay strictly optional: a missing expectation falls back
to the class default, never to an error.

**K-6 — Phase 2 touches the most frozen files in the repository.** Three
ADRs against `mission_control/` and `runtime/` is the largest frozen
surface any brief has proposed. Sequencing Phase 1 first keeps that
decision unhurried.

---

## 18. Deferred work and backlog

Ordered. Phase 1 items are unblocked today.

1. **Measurement spike** — `gemma4:latest` prefill and decode rates on
   the founder's hardware; characterise K-1's serialisation and whether
   disconnect halts generation (⚖3). **Everything downstream needs real
   numbers.** Not code.
2. **`request_class`** on `SelectionRequest`, closed vocabulary, with a
   test that producer-less classes are never emitted (§6.4).
3. **Class bounds** in configuration (§13) — the smallest change that
   fixes the observed defect.
4. **`CallBudget`** — the three-deadline value object, emitted by the
   Broker on the Selection.
5. **Adaptive derivation** in the Broker (§5.3) — deterministic, recorded
   before the call.
6. **Streaming adapter contract** + `supports_streaming`; TTFT and ITL
   monitors (D-2).
7. **Admission control** (D-12) and **occupancy tracking** (§8.3).
8. **Telemetry** on `ExecutionRecord` (§10), including *which constraint
   bound the budget*.
9. **Dashboard** — a timeout must read as *budget exceeded, derived
   thus*, never as a bare failure.
10. **Replay reuse** (§9) — largely a "do not add recomputation"
    constraint; worth an explicit test.
11. **ADR-0021/0022/0023** — Phase 2, founder decision, ADR-0023 merged
    with MB037's pause/resume gap.
12. **Benchmark store consumes timeouts** (§10.4) — feeds ADR-0017 D5 and
    ADR-0018's learning loop.

---

## 19. Invariants check

| Invariant | Preserved by |
|---|---|
| Mission Control owns missions | §2.3 — it owns the SLA and nothing else about time |
| Runtime owns execution | §2 — task-boundary enforcement and task retry, unchanged |
| Planner produces plans only | §6.2 — it states facts; it sets no deadline |
| Planner never schedules | §12.3, D-11 |
| Dispatcher dispatches | §2 — owns nothing time-related; ordering untouched |
| Broker selects providers | §2.2 — budget derivation is a judgement about provider performance, already its remit |
| Provider adapters own transport | §2, D-3 — enforcement and honest reporting only |
| Replay deterministic | D-9, §5.3 — budgets recorded, never recomputed |
| Evidence complete | §10 — budget, derivation, binding constraint, observation, outcome, orphan state |
| No layer gains another's responsibility | §2.1 — four verbs, each appearing exactly once |
| No second orchestration authority | The Broker computes but never schedules |
| Constitution unchanged | No amendment proposed |
