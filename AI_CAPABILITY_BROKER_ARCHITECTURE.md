# AI Capability Broker Architecture

Status: **Frozen (architecture only)** — 2026-07-29 — Mission Brief 027

Design document required before any code, per Constitution Rule 1. This
Mission Brief is architecture-only: no implementation, no provider
integration, no provider-specific code. Nothing under `src/` or `tests/`
was touched.

Siblings: `MISSION_CONTROL_ARCHITECTURE.md`, `RUNTIME_ENGINE_ARCHITECTURE.md`,
`PERSISTENCE_ARCHITECTURE.md`, `FOUNDER_DASHBOARD_ARCHITECTURE.md`.
Governed by `docs/architecture/KALPAVRIKSHA_VISION_V2.md` (the Constitution).
Decision record: `docs/adr/0017-ai-capability-broker.md`.

---

## 0. The one-paragraph version

Every Executive that will ever need intelligence — Desktop, Research,
Knowledge, Filesystem, Terminal, Git — asks one question: *"I need this
kind of thinking done; which intelligence should do it?"* The **AI
Capability Broker** is the only component permitted to answer. It holds
the registry of what intelligence exists, the matrix of what each one can
do, the ledger of what each one costs, the history of how well each one
has actually performed, and the policy for what the founder must approve.
It returns a **decision**, never a result. It never executes anything, it
never touches a provider, and it never spends money without an approval it
did not itself grant.

---

## 1. Two terminology collisions, resolved before anything else

Both of these would have poisoned every section below if left implicit.
Constitution §17 freezes each term to exactly one meaning, and MB023's
precedent (ADR-0014) is that a collision surfaced during design gets
resolved explicitly, in writing, rather than left ambiguous.

### 1.1 "Capability" already means something else

| Term | Meaning | Example | Dispatchable? |
|---|---|---|---|
| **Capability** (Constitution §17, unchanged) | A named unit of *what can be done*, resolved to a Worker at execution time via the Capability Registry (§5.1) | `Browser.Navigate`, `Filesystem.WriteFile` | Yes — this is the thing a `Step` names |
| **AI Capability** (new, this document) | A *kind of intelligence* a Provider can supply | `reasoning`, `vision.ocr`, `speech.transcribe` | **No** — never dispatchable on its own |

An AI Capability is an *input to selection*. A Capability is a *unit of
execution*. The Broker maps the first onto the second: you ask it for
`vision.ocr`, and part of what it hands back is the Constitution-flavoured
Capability that will actually run (`LocalModel.Generate`, say) plus the
provider to run it against.

**Naming rule, chosen so the two are distinguishable on sight and by a
regex:**

- Constitution Capabilities are `PascalCase.PascalCase` — the deterministic
  qualified-name rule Mission Control already implements
  (`mission_control/capabilities.py::qualified_name`).
- AI Capabilities are `lowercase.dotted.path`.

A document, a log line, or a test can tell them apart mechanically. This
is deliberately not a convention to remember.

### 1.2 "Provider" generalizes "Reasoning Provider", it does not replace it

Constitution §17 and §3.3 use **Reasoning Provider**. §17 also forbids
giving any frozen term a third synonym. So:

> A **Provider** is any registered source of AI capability. A **Reasoning
> Provider** (§3.3, unchanged) is a Provider that offers the `reasoning`
> AI Capability.

Nothing is renamed. Nothing shipped changes name. "Reasoning Provider"
stays exactly as valid and exactly as meaningful as it was; it is now
understood as one row of a larger table that also has vision, speech,
image, and embedding rows.

---

## 2. The Required Analysis: Kernel Service or Executive?

MB027 requires this question be answered, not deferred.

### 2.1 The case for making it an Executive

Real, and worth stating properly:

- Constitution §2.3 says *"Everything Is a Worker Behind a Capability."*
  Rule 3 says adding capability #N costs one new file. An Executive is the
  cheapest possible thing to add and the most consistent with how
  everything else in this system has been built.
- Discovery, scanning, probing, and benchmarking all need to touch the
  real machine — and Rule 4 says Environment access has exactly one door:
  a Worker, via the Operator's Worker Runtime.
- Mission Control could then dispatch broker work like any other task, and
  the Broker would inherit lifecycle, health, and audit for free.

### 2.2 Why it fails as an Executive

Four independent reasons, any one of which is disqualifying:

1. **Both sides need the same answer.** The Brain's Model Router (§3.3)
   needs it to route a planning call. An Executive mid-task needs it to
   pick an OCR engine. That is *precisely* the condition ADR-0010 defined
   Shared Infrastructure to handle: a thing both columns legitimately
   depend on. Putting the Broker in the Operator's column recreates,
   exactly, the contradiction the independent audit found in Revision 2 —
   the Brain reaching across the boundary into an Operator component. Put
   one copy on each side instead and they drift, which is the failure mode
   §5.1 exists to prevent.
2. **It arrives too late in the sequence.** An Executive is selected and
   dispatched *by* Mission Control and the Runtime. The Broker's answer is
   needed *before* dispatch, to decide what the dispatch should even
   contain. A component that must be consulted before dispatch cannot be
   a thing that is dispatched.
3. **The state it owns must be singular.** Monthly spend, standing founder
   approvals, and benchmark history are ledgers. Two Operator Instances
   holding two copies of "how much have we spent this month" is the same
   class of bug §5.2 elevated the Permission System to Shared
   Infrastructure to eliminate — an approval satisfied twice, or asked
   twice, because two components disagreed about what was already true.
4. **Executive-to-Executive calling would become the norm.** Every future
   Executive needing intelligence would have to invoke the Broker
   Executive, and Rule 6 requires that to be a permission-relaying
   composite call. Making the single most-called component in the system
   reachable only through the heaviest calling convention in the system is
   backwards.

### 2.3 Decision

> **The AI Capability Broker is a Kernel Service — a Shared Infrastructure
> component (Constitution §5).** It is not an Executive, and it is not
> Brain-side or Operator-side.

The part of §2.1's argument that is genuinely right is preserved rather
than discarded: **everything that requires touching the machine is an
Executive.** Scanning the host, listing installed applications, probing a
provider, running a benchmark — all of it belongs to the **AI
Infrastructure Executive** (§11), which is an ordinary Worker behind
ordinary Capabilities, gated by the ordinary Permission System.

The split is exact:

| | AI Capability Broker (kernel service) | AI Infrastructure Executive (Worker) |
|---|---|---|
| Touches the machine | **Never** | Always — that is its whole job |
| Decides which Provider | Always — nothing else may | Never |
| Holds registry, matrix, ledger, benchmarks | Yes | No — it *produces inputs* to them |
| Invoked by | Direct call, as Shared Infrastructure | Dispatch, as any Executive |
| Import of a provider SDK | Forbidden, mechanically | Permitted, in its own adapter |

This mirrors, deliberately, how Mission Control relates to the Executives
it coordinates: the coordinator holds descriptors and decides ordering;
the Worker holds live handles and does the work. It is the same shape
applied one layer down.

### 2.4 Cost of this decision, stated honestly

It requires a Constitution amendment: §5 gains a component, §6's module
table gains an entry, §16's Ownership Registry gains two rows, §17 gains
two terms. §5 and §16 are FROZEN. Per the freeze process
(`FOUNDER_CONSTITUTION_FREEZE.md` §4a, precedent ADR-0014), that is
permitted — through an ADR, in a Mission Brief, updating the Constitution
and the freeze record together.

**The Mission Brief proposed that amendment and did not make it** —
MB027's own acceptance criteria say "no existing architecture modified,"
and MB025 set the precedent: an ADR marked *Proposed*, awaiting founder
ratification, rather than a unilateral edit to frozen text.

**Ratified by the founder on 2026-07-29**, and applied in one pass as
**Amendment 2** (`FOUNDER_CONSTITUTION_FREEZE.md` §4a). §5.7 is the
Broker; the prior §5.7 renumbered to §5.8 and now states that machine
scanning, probing, benchmarking, inventory, and installation are
deliberately *not* Shared Infrastructure. §5.7 carries the status
**RESEARCH-BACKED** — frozen in shape, not yet proven by implementation.

The sequence is the precedent, now recorded in the freeze record: a
structural amendment is proposed by a Mission Brief and applied only after
founder ratification; a terminology reconciliation forced by shipping code
(Amendment 1, ADR-0014) may move in the same commit.

---

## 3. Deliverable 1 — The architecture

### 3.1 Position in the system

```
                    Executive Brain
        (Intent Layer, Planner, Model Router, Reporter)
                          │  asks
                          ▼
 ┌─────────────────── Shared Infrastructure ───────────────────┐
 │  Capability Registry   Permission System   Mission State    │
 │  Memory   Configuration   Telemetry/Evidence                │
 │                                                             │
 │  ┌──────────────  AI Capability Broker  ─────────────────┐  │
 │  │  Provider Registry ─ Capability Matrix ─ Cost Model   │  │
 │  │  Decision Engine ─ Benchmark Store ─ Approval Policy  │  │
 │  │  AI Asset Inventory ─ Recommendation Engine           │  │
 │  └───────────────────────────────────────────────────────┘  │
 └──────────────────────────────▲──────────────────────────────┘
                          │ asks │ feeds inventory,
                          ▼      │ benchmarks, outcomes
              Universal Executive Operator
        (Orchestrator, Verification, Worker Runtime)
                          │
        ┌─────────────────┴──────────────────┐
        ▼                                    ▼
  Desktop / Browser / Terminal /      AI Infrastructure
  Research / Git Executives             Executive
```

Every arrow points *downward into* Shared Infrastructure or *upward out
of* it as data. The Broker has **no upward dependency on anything** — not
on the Brain, not on the Operator, not on Mission Control, not on the
Runtime. This is what makes it safe to be called from everywhere.

### 3.2 Responsibilities

The Broker owns, and is the only owner of:

1. **The Provider Registry** — what intelligence exists (§4).
2. **The Capability Matrix** — what each Provider can do, declared and
   observed (§5).
3. **The Decision Engine** — which Provider serves a given request (§6).
4. **The AI Asset Inventory** — the machine's AI ecosystem as last
   observed (§7).
5. **The Recommendation Engine** — what would improve the ecosystem (§8).
6. **The Cost Model** — what has been spent, what will be (§9).
7. **The Benchmark Store** — how well each Provider actually performs (§10).
8. **The Approval Policy** — what the founder must sign off (§12).
9. **The audit trail of every decision** — emitted, never kept private.

### 3.3 The eight things the Broker must never do

Stated as prohibitions because that is how MB023, MB024, and MB025 each
kept their boundaries honest — and because each of these is mechanically
testable at implementation time, the way `test_mission_control_purity` and
`test_runtime_architecture` already are.

1. **Never executes.** It has no Environment access, opens no network
   connection, and imports no provider SDK. It returns decisions.
2. **Never decides *what* to do.** That is the Brain's. The Broker
   answers only "with which intelligence," given a request it did not
   author.
3. **Never discovers.** Scanning the machine is Environment access, and
   Rule 4 gives that exactly one door. The Broker *consumes* an inventory
   handed to it; it never produces one.
4. **Never grants permission.** It *requires* permission, through the
   existing Permission System (§5.2). It implements no parallel approval
   mechanism (§12).
5. **Never spends.** It estimates cost and records reported spend. Money
   leaves only through an execution path the Operator ran with a grant.
6. **Never retries.** Retry is the Runtime's (bounded, mechanical) and the
   Brain's (strategic) — the split MB024 resolved. A caller whose provider
   failed re-asks the Broker with an exclusion; the Broker does not loop.
7. **Never names a product in its own logic.** Zero provider-specific
   branches. Product names appear only in registry *data* and in
   explicitly non-binding illustrative tables, exactly as Constitution §21
   requires.
8. **Never installs, downloads, or removes anything.** Recommendations are
   inert data (§8).

### 3.4 Inputs

One request shape, frozen:

```
CapabilityRequest(
    request_id,                 # caller-generated, for correlation
    ai_capability,              # "vision.ocr" — lowercase.dotted (§1.1)
    task_class,                 # coarse bucket for benchmarking, e.g. "plan"
    requester,                  # executive_id | "brain.planner" | "brain.model_router"
    objective_id, task_id,      # Mission Control correlation, optional
    constraints: RequestConstraints,
    hints: RequestHints,
)

RequestConstraints(            # hard — a Provider failing any of these is filtered out
    privacy,                    # unrestricted | local_only | no_third_party
    connectivity,               # online_permitted | offline_only
    max_latency_ms,             # None = unconstrained
    min_quality,                # floor on expected success probability
    required_context_tokens,
    required_modalities,        # e.g. ["image"] for a vision request
    licensing_use,              # personal | commercial — matched against Provider licence
    exclude_providers,          # re-ask after a failure, never a Broker-side loop
    max_cost,                   # per-request ceiling; None = policy default
)

RequestHints(                  # soft — influences ranking, never filters
    prefer_provider,            # explicit founder preference (§6.5)
    prefer_speed_over_quality,
    expected_output_tokens,     # improves the cost estimate
)
```

The split between `constraints` (filter) and `hints` (rank) is
load-bearing: it is what stops a preference from silently overriding a
privacy rule, and it is why §6's algorithm can be described in two clean
phases instead of one weighted blob nobody can audit.

### 3.5 Outputs

```
BrokerDecision(
    decision_id,                # the join key for cost, benchmark, and audit
    request_id,
    outcome,                    # SELECTED | APPROVAL_REQUIRED | NO_CAPABLE_PROVIDER
    selection,                  # ProviderSelection | None
    alternatives,               # ranked, with reasons — never just the winner
    rejected,                   # [(provider_id, filter_reason)] — the full audit trail
    cost_estimate,              # CostEstimate | None
    approval,                   # ApprovalRequirement | None
    inventory_age_seconds,      # freshness of the facts this rested on
    policy_version,             # which policy produced this
    inputs_digest,              # replay key — see §6.6
    decided_at,
)

ProviderSelection(
    provider_id,
    tier,                       # which rung of the ladder it came from (§6.2)
    execution_capability,       # PascalCase.PascalCase — what the Operator dispatches
    execution_parameters,       # plain dict: model name, endpoint id, etc.
    expected_success,           # 0..1, with `confidence`
    confidence,                 # low when benchmark samples are scarce (§10.4)
    rationale,                  # human-readable, founder-facing
)
```

Three properties of this shape matter more than the fields:

- **`execution_capability` is the bridge.** The Broker's output is not a
  connection or a client — it is the name of an existing Constitution
  Capability plus the parameters to invoke it with. The caller resolves it
  through the Capability Registry (§5.1) and runs it through the Operator,
  exactly as it would any other Capability. **The Broker creates no new
  execution path**, which is what stops it becoming a second, unaudited
  way to reach the outside world.
- **`rejected` is not debug output.** MB027 Rule 15 requires every
  provider decision be auditable. A decision that records only its winner
  is not auditable — the question a founder asks six weeks later is *"why
  didn't it use the local one?"*, and the answer has to be in the record.
- **`alternatives` is what makes re-asking cheap.** A caller whose
  selection failed already holds the ranked runners-up.

### 3.6 Failure handling

| Situation | Behaviour | Why this and not the alternative |
|---|---|---|
| No Provider offers the AI Capability | `NO_CAPABLE_PROVIDER`, with the full `rejected` list | An explicit, auditable refusal. Silently falling back to "the best thing we have" is how a request for OCR gets served by a text model that hallucinates the answer. |
| Candidates exist, all below `min_quality` | `NO_CAPABLE_PROVIDER`, reason `quality_floor` | Same rule. A confident wrong answer is worse than a refusal, and this is the Evidence discipline (Rule 8) applied to selection. |
| Only paid candidates remain | `APPROVAL_REQUIRED` — never `SELECTED` | MB027's central rule. The decision names the cost, the best free alternative, and what the founder is being asked to permit. |
| Selected Provider fails at execution | Caller reports the outcome, then re-asks with `exclude_providers` | The Broker does not retry (§3.3 #6). Failure also degrades that Provider's observed reliability (§10), so the *next* decision is better without anyone editing policy. |
| Inventory is stale beyond the configured bound | Decision still returned; local/desktop candidates marked `unverified`, and `inventory_age_seconds` is on the record | Absence and unknown are different facts (ADR-0016). A stale inventory must not silently become "you have no GPU." |
| Budget exhausted for the period | Paid tiers filtered out entirely; free tiers still selectable | A budget cap that merely warns is not a cap. |
| Broker itself unavailable | The caller **fails the step**. It does not choose a Provider | Falling back to a caller-local default is precisely the architecture this document exists to prevent, and it would be undetectable in the audit trail. |

### 3.7 Verification flow — how we learn whether the Broker chose well

```
CapabilityRequest ──▶ BrokerDecision(decision_id) ──▶ caller executes
                                                          │
                        Verification Subsystem (ADR-0011) ─┤
                                                          ▼
              Broker.record_outcome(decision_id, OutcomeReport)
                                                          │
                          BenchmarkSample ────────────────┘
                                   │
                                   ▼
              aggregates by (provider, ai_capability, task_class)
                                   │
                                   ▼
                     input to the next decision (§6.3)
```

The single most important rule in this loop:

> **An outcome is successful when Verification says so, not when the
> provider call returned.**

`OutcomeReport.verdict` is the Verification Verdict (ADR-0011), not an
HTTP status. A model that returns a fluent, confident, wrong answer must
score as a failure, or the Benchmark Engine will systematically prefer
providers that fail *articulately*. This is the same distinction that
stops execution success from implying mission success everywhere else in
Kalpavriksha, applied to provider quality.

Callers report outcomes; the Broker never observes execution itself.

---

## 4. Deliverable 2 — Provider Registry

### 4.1 The descriptor

```
ProviderDescriptor(
    provider_id,                # stable, unique, founder-readable
    display_name,
    provider_class,             # open vocabulary — see §4.2
    offers,                     # [CapabilityOffer] — the matrix rows (§5)
    execution_binding,          # PascalCase.PascalCase Capability + fixed parameters
    cost_profile,               # §9
    licensing,                  # LicenceTerms — see §4.4
    rate_limits,                # RateLimitPolicy
    requirements,               # HardwareRequirement — GPU/VRAM/RAM/disk/runtime
    availability,               # how presence is determined (§4.5)
    version,
    provenance,                 # declared | discovered | self_registered (§4.3)
    registered_at, verified_at,
    health,                     # healthy | degraded | unreachable | unverified
)
```

Registry rules, frozen:

1. **Descriptors only, never live objects.** The registry holds
   descriptions. It cannot invoke what it describes, which is what makes
   §3.3 #1 structural rather than promised. This is the same choice
   Mission Control's coordination catalogue made, for the same reason
   (`MISSION_CONTROL_ARCHITECTURE.md` §4).
2. **No provider is known to the Broker's code.** There is no enum of
   providers, no `if provider_id == ...` anywhere, no module named after a
   vendor. Adding provider #200 costs one registration call and zero edits
   — Rule 3, applied to intelligence instead of execution.
3. **`provider_class` is an open vocabulary string, not an enum.** An enum
   is closed for modification; the class of thing an AI provider *is* has
   changed three times in as many years. The Broker never branches on
   class — it is a descriptive and grouping axis only, and the tier ladder
   (§6.2) is derived from cost and locality, not from class.
4. **`execution_binding` must name an already-registered Capability.**
   Registration is refused otherwise. A Provider nobody can invoke is a
   configuration error and should fail loudly at registration rather than
   quietly at 3am.
5. **Registration is idempotent by `provider_id`,** and re-registration
   with a changed descriptor is an update *with an audit event*, never a
   silent overwrite.

### 4.2 Provider classes — illustrative, explicitly non-binding

Constitution §21 forbids architecture from depending on any named
product. This table exists so a reader can picture the design, and MB027's
named products land in it as **data, not architecture**. Nothing in §3–§13
depends on any row.

| `provider_class` | What it means | Illustrative examples from MB027 (non-binding) |
|---|---|---|
| `local_runtime` | A model served by an inference runtime on this host | Ollama, LM Studio, llama.cpp |
| `desktop_application` | An installed AI application driven as an application | Claude Desktop, ChatGPT Desktop, ComfyUI, Stable Diffusion, Whisper, VS Code AI |
| `cloud_api` | A hosted API reached over the network | Anthropic, OpenAI, Gemini |
| `cloud_aggregator` | A hosted API that itself routes to many models | OpenRouter |
| `remote_self_hosted` | A runtime the founder operates on other hardware | a VPS-hosted inference server |
| `embedded` | Intelligence bundled inside another tool | an editor's built-in completion |

A class not on this list needs no code change — it is a string.

### 4.3 Three registration paths, one shape

| Provenance | Who writes it | Trust | Example |
|---|---|---|---|
| `declared` | The founder, via Configuration (§5.5) | Highest — an explicit statement of intent | "I have an OpenRouter key, free tier only" |
| `discovered` | The AI Infrastructure Executive (§11), from a real scan | Evidence-backed | "Ollama is installed, with these four models" |
| `self_registered` | An Executive that itself provides intelligence | Manifest-backed | a Local Model Executive registering what it serves |

All three produce a `ProviderDescriptor`. Provenance is recorded and is a
tie-breaker, never a filter — a discovered provider is not second-class,
but when a declared descriptor and a discovered one disagree, **observed
reality wins** (Rule 8), and the disagreement is published as an event
rather than silently reconciled.

### 4.4 Licensing is a first-class filter, not a note

`LicenceTerms(licence_id, permits_commercial_use, permits_redistribution,
requires_attribution, requires_paid_activation, source_url)`.

A Provider whose licence does not permit the request's `licensing_use` is
**filtered out in Phase 1** (§6.1), not warned about. This is deliberate:
a local model with a non-commercial licence is genuinely unavailable for
commercial work, and a system that quietly used it anyway would be
creating a legal exposure that no audit trail would surface until much
later.

### 4.5 Availability

`availability` records *how presence is determined*, because the answer
differs per class and pretending otherwise is how "is it there?" becomes
unreliable:

- `local_runtime` — the runtime process/endpoint responds, **and** the
  named model is present in the inventory.
- `desktop_application` — the application is installed at a known path,
  at a compatible version.
- `cloud_api` / `cloud_aggregator` — a credential is present in
  Configuration (presence only — see §7.3) **and** connectivity exists
  **and** rate-limit headroom remains.

Availability is never assumed from the descriptor existing. An unverified
Provider is `unverified`, not `healthy` — distinct states, and the
Decision Engine treats them differently (§6.3).

---

## 5. Deliverable 3 — Capability Matrix

### 5.1 Two axes, deliberately separated

MB027's Deliverable 3 lists "Reasoning, Coding, Browser, Vision, OCR,
Speech, Video, Image, Embeddings, Tool Use, Long Context, Offline Support,
Latency, Quality, Cost, Availability, Licensing, Rate Limits" as one list.
Freezing it as one list would be a mistake, and this is the one place this
document deliberately restructures what the brief asked for:

- The first group answers ***what can this Provider do*** — they are AI
  Capabilities, and a Provider either offers one or does not.
- The second group answers ***how well, at what price, under what
  terms*** — they are attributes that qualify *every* offer, vary per
  capability, and change over time.

Merging them means "cost" becomes something a Provider "can do," and the
Decision Engine's filter phase can no longer be written cleanly. Split,
each axis has exactly one job.

### 5.2 Axis 1 — AI Capabilities (what)

An open, dotted, lowercase vocabulary (§1.1). Seeded from MB027:

```
reasoning            reasoning.planning      reasoning.long_context
coding               coding.completion       coding.review
vision               vision.ocr              vision.describe
speech.transcribe    speech.synthesize
image.generate       image.edit
video.generate       video.understand
embeddings
tool_use             tool_use.structured_output
browser.understand
```

Frozen rules:

- Matching is **exact or prefix**: a request for `vision` is served by a
  Provider offering `vision.ocr`; a request for `vision.ocr` is *not*
  served by one offering only `vision`. Specific requests never get
  generic answers; generic requests accept specific ones.
- The vocabulary is **open**. A new AI Capability costs a string. There is
  no enum to edit and no registry to migrate, for the same reason
  `provider_class` is open (§4.1 rule 3).
- `browser.understand` is intelligence *about* a page — reasoning over an
  accessibility tree or screenshot. It is emphatically **not** the Browser
  Executive's `Browser.Navigate` and friends, which are execution and are
  not brokered. MB027's Deliverable 3 lists "Browser" among AI
  capabilities; this is the reading that keeps §1.1's line intact.

### 5.3 Axis 2 — Attributes, declared *and* observed

Every offer carries both:

```
CapabilityOffer(
    ai_capability,
    declared: AttributeSet,     # from manifest, config, or vendor documentation
    observed: AttributeSet,     # from the Benchmark Store (§10) — may be empty
    max_context_tokens,
    supports_offline,
    supports_tool_use,
    supports_streaming,
    modalities_in, modalities_out,
)

AttributeSet(
    quality,          # 0..1, per task_class where known
    latency_p50_ms, latency_p95_ms,
    reliability,      # 1 - error rate
    sample_count,     # 0 for declared; drives `confidence` (§10.4)
    measured_at,
)
```

> **The rule that makes this matrix trustworthy: where `observed` exists,
> it wins over `declared`.**

This is Constitution Rule 8 (Evidence Hierarchy — observed reality beats
documentation) applied to provider selection. Vendor benchmark claims and
model cards are `declared`. What actually happened on this founder's
missions, on this founder's hardware, is `observed`. A Provider cannot
market its way up the ranking.

`declared` is not discarded — it is what makes cold start possible (§10.4)
— but it is always visibly labelled as the weaker evidence, and it carries
a confidence penalty that a proven Provider does not.

### 5.4 What the matrix is not

It is not a leaderboard, and it is not global. It is a record of how
Providers have performed **on this system, for this founder's task
classes**. A provider that is excellent in general and poor at the three
things this founder actually does should rank poorly here. That is the
design working, not a flaw in it.

---

## 6. Deliverable 4 — Decision Engine

### 6.1 Phase 1 — Filter on hard constraints

Every Provider offering the requested AI Capability is tested against the
request's `constraints`. Each rejection is recorded with a reason and
lands in `BrokerDecision.rejected`.

| Filter | Rejects when |
|---|---|
| Capability match | The offer does not match by exact-or-prefix (§5.2) |
| Availability | Provider is `unreachable`, or the underlying asset is absent from the inventory |
| Privacy | `local_only` and the Provider is not local; `no_third_party` and it is an aggregator |
| Connectivity | `offline_only` and the Provider requires the network |
| Hardware | The host cannot satisfy `requirements` (VRAM, RAM, disk, runtime) |
| Licensing | The licence does not permit `licensing_use` (§4.4) |
| Context / modality | `required_context_tokens` exceeds `max_context_tokens`, or a modality is unsupported |
| Rate limits | No headroom remains in the current window |
| Budget | The tier costs money and the period budget is exhausted (§9.4) |
| Explicit exclusion | `provider_id` is in `exclude_providers` |

Filters are **absolute**. Nothing in Phase 2 or 3 can revive a filtered
Provider, and no hint can override a constraint. That asymmetry is the
whole reason §3.4 splits the two.

### 6.2 Phase 2 — The tier ladder, with a quality floor

MB027 freezes this priority order:

| Tier | Class | Founder approval |
|---|---|---|
| 1 | Local models | Never required |
| 2 | Installed desktop AI applications | Never required |
| 3 | Free cloud models | Never required (but see §12.3 on privacy) |
| 4 | Free aggregator models | Never required (but see §12.3) |
| 5 | Existing paid subscriptions (already bought) | Not required to *use*; required to *acquire* |
| 6 | Paid metered APIs | **Always required** |

Selection walks the ladder from tier 1 and stops at **the first tier
containing at least one *viable* candidate**, where viable means it
survived Phase 1 *and* its expected success probability meets the
request's `min_quality` floor.

That floor is the part that makes this algorithm correct rather than
merely cheap. MB027 asks the Broker to answer:

> *"Which available intelligence gives the highest probability of success
> for this task while minimizing cost?"*

Read as pure cost-minimisation, a 1B local model would be handed every
mission and most would fail — cheaply, repeatedly, and then be retried
somewhere more expensive anyway, which is the *worst* of both. Read as
pure success-maximisation, everything routes to the most expensive
frontier API and the local-first principle is decoration. The floor
resolves it exactly:

> **Cheapest tier that clears the bar — and if no tier clears it, refuse
> rather than guess.**

Where the bar comes from, in priority order: the request's explicit
`min_quality`; else the configured default for the `task_class`; else the
global policy default. It is configuration, not a constant in the code,
because the right floor for "summarise this file" and "plan a mission" are
genuinely different numbers and always will be.

### 6.3 Phase 3 — Rank within the winning tier

Deterministic, in this order:

1. **Expected success probability** — `observed.quality` for
   `(provider, ai_capability, task_class)` where samples exist; otherwise
   `declared.quality × cold_start_penalty` (§10.4). An `unverified`
   Provider (§4.5) carries a further penalty — not a filter, because an
   unverified Provider may be the only one, but never a free pass.
2. **Latency** — `observed.latency_p95_ms` against `max_latency_ms`, then
   as a preference; `prefer_speed_over_quality` swaps 1 and 2.
3. **Cost within the tier** — tiers 1–4 are usually equal here; tiers 5–6
   are not.
4. **Provenance** — `declared` over `discovered` over `self_registered` on
   an exact tie.
5. **`provider_id`, lexicographically** — never a random or
   insertion-order tie-break, so the same inputs always produce the same
   answer (§6.6).

### 6.4 Phase 4 — The approval gate

If the winner sits in a tier requiring approval, the Broker returns
`APPROVAL_REQUIRED` — **never** `SELECTED`. The decision carries:

- what is being requested and why the free tiers did not clear the floor,
- the cost estimate for this request and its effect on the period budget,
- the best free alternative *and its expected success probability*, so the
  founder is choosing between two named outcomes rather than being asked
  to approve a number in isolation.

The Broker then stops. It does not queue, does not wait, does not proceed
on timeout. The caller receives a decision that does not authorise
execution, and the requirement is published for the founder (§12).

### 6.5 Where Constitution §3.3 lands

§3.3 already gives the Model Router four selection criteria. They are not
superseded — every one of them maps onto this engine, which is the
evidence that the Broker is the generalisation of an existing frozen
design rather than a competing one:

| §3.3 criterion | Where it lives here |
|---|---|
| 1. Connectivity — offline ⇒ local only | Phase 1 filter, `constraints.connectivity` |
| 2. Privacy — sensitive stays local unless overridden | Phase 1 filter, `constraints.privacy` |
| 3. Task profile — routine local, strong reasoning escalates | Phase 2: the quality floor per `task_class` is exactly this, made explicit and configurable instead of implicit |
| 4. Explicit user preference — always wins | Phase 3, via `hints.prefer_provider` — see below |

**One deliberate narrowing of §3.3 criterion 4, stated plainly rather than
smuggled.** "Always wins" is honoured *among candidates that survived
Phase 1*. A preference cannot select a Provider that is unavailable, is
forbidden by the request's privacy constraint, is licence-barred, or is
paid-without-approval. Preference is a hint, not a constraint (§3.4).

This is not a weakening of founder control — it is the mechanism by which
founder control is expressed *once*, in policy and approval, instead of
being re-litigated per call. And a founder who genuinely wants the paid
provider expresses that by approving it (§12), which is a stronger and
more auditable act than a hint that silently bypasses a privacy rule.

### 6.6 Determinism and replay

> Same request + same registry state + same inventory + same benchmark
> aggregates + same policy version ⇒ **same decision, always**.

`inputs_digest` is a hash over exactly those five things. It is what turns
"every provider decision must be auditable" (MB027 Rule 15) from a claim
into a property: given a past decision, its inputs can be reconstructed
and the decision re-derived. A ranking that broke ties by dict ordering,
wall-clock, or randomness would make that impossible — hence §6.3 rule 5.

No model call is made to *make* a decision. The Decision Engine is
deterministic policy over data. A Broker that asked an AI which AI to use
would need an AI to make that choice, and something would have to break
the recursion; this design never starts it.

---

## 7. Deliverable 5 — AI Asset Inventory

### 7.1 Shape

```
AiAssetInventory(
    inventory_id, host_id, captured_at, captured_by,   # an executive_id
    applications,     # [InstalledApplication]  name, version, path, vendor, ai_features
    models,           # [LocalModel]  name, family, parameters, quantisation, runtime,
                      #               path, size_bytes, licence_id, last_used
    checkpoints,      # [Checkpoint]  kind, path, size_bytes, licence_id  (image/audio weights)
    credentials,      # [CredentialPresence]  provider_id, present, scope, tier  — NEVER a value
    runtimes,         # [Runtime]  name, version, endpoint, healthy
    hardware,         # HardwareProfile
    storage,          # StorageUsage  per-root totals, free space
    scan_coverage,    # what was and was not scanned, and why (§7.4)
)

HardwareProfile(
    cpu_model, cpu_cores, ram_bytes,
    gpus,             # [Gpu]  model, vram_bytes, driver, compute_capability
    accelerators,     # non-GPU accelerators
    disk_free_bytes,
)
```

### 7.2 The inventory is a snapshot, produced elsewhere

It is captured by the AI Infrastructure Executive (§11) and handed to the
Broker through one entry point, `ingest_inventory(AiAssetInventory)`. The
Broker never calls the Executive — that would be orchestration, which
Shared Infrastructure does not do, and would give a kernel service an
upward dependency (§3.1).

Every inventory is timestamped and retained; `inventory_age_seconds`
appears on every decision (§3.5). The Broker holds the current one plus
history, because "when did that GPU disappear?" is a question the
Recommendation Engine needs to answer.

### 7.3 The inventory never stores a secret

`CredentialPresence` records **that** a credential exists, its scope, and
its tier. Never its value, never a prefix, never a hash that could be
confirmed against a guess. The value stays in Configuration (§5.5), and
only the execution path ever reads it.

This is stated as a frozen rule rather than left to implementation care,
because the Broker is otherwise the single most attractive place in the
architecture to keep API keys — it knows every provider, and it is
consulted before every call — and because Broker state is persisted (§13),
which would put keys in a snapshot file on disk. It must never be that
place.

### 7.4 Missing is not zero

`scan_coverage` records what could not be scanned and why. A host where
GPU enumeration failed reports `gpus: unknown`, not `gpus: []`. The
Decision Engine treats unknown hardware as *unverified* — candidates
needing it are ranked down, not filtered out — because filtering on an
unknown would silently make every local provider disappear on a machine
where one probe failed.

Same discipline as ADR-0016's read model, for the same reason: `0` and
"we do not know" are different facts, and conflating them fabricates.

---

## 8. Deliverable 6 — Recommendation Engine

### 8.1 Shape

```
Recommendation(
    recommendation_id, kind, target, rationale,
    evidence,             # decision_ids, benchmark sample ids, ledger references
    estimated_impact,     # monthly_cost_delta, latency_delta_ms, storage_delta_bytes,
                          # success_rate_delta — each optional, each with a basis
    confidence,
    founder_action,       # the single concrete thing the founder would do
    generated_at, policy_version,
)
```

`kind` is an open vocabulary. MB027's list seeds it: `install`, `remove`,
`upgrade`, `replace`, `reclaim_storage`, `reconfigure`, `rebalance_local_cloud`.

### 8.2 Recommendations are inert, by construction

> **Nothing in Kalpavriksha consumes a recommendation to act.** Deleting
> the entire Recommendation Engine would change what the founder *sees*
> and nothing about what the system *does*.

This is exactly the boundary ADR-0016 drew around Dashboard health
classification, and it is drawn the same way — structurally, not by
intention. The Decision Engine does not read recommendations. The Broker
does not download, install, or remove anything (§3.3 #8). A recommendation
is a row of data with a founder-facing sentence attached.

### 8.3 How a recommendation becomes action — through machinery that exists

Mission Control already has the right component: the **Self-Development
Queue** (MB023, deliverable #6) — the published path for "the system
lacks something." So:

```
Recommendation ──▶ Founder Dashboard (visible)
                     │
                     │  founder accepts
                     ▼
              Self-Development Queue item ──▶ normal Mission Control flow
                                                (planned, approved, executed)
```

The Broker publishes recommendations as events; whether one is *enqueued*
is a founder decision made through existing surfaces. This keeps the
Broker on the correct side of "never performs work" and adds no new
approval path (§12.4).

### 8.4 Every recommendation must carry falsifiable evidence

A recommendation with an empty `evidence` list is refused at generation.
"Consider upgrading your model" is noise; *"`vision.ocr` has failed 6 of
the last 9 verifications on this provider, and provider X, already
installed, has succeeded 14 of 15 on the same task class — decisions
`d-8821`, `d-8834`, …"* is a decision a founder can check and reject.

Savings figures follow the same rule and are labelled as **estimates
against a named counterfactual** (§9.5), never presented as realised
money.

---

## 9. Deliverable 7 — Cost Model

### 9.1 Three separate things, deliberately not merged

| Concept | Answers | Source |
|---|---|---|
| `CostProfile` | What *would* this cost? | The Provider descriptor — rates, quotas, subscription terms |
| `CostEstimate` | What will *this request* cost? | Profile × expected usage, computed pre-decision |
| `CostLedger` | What *did* it cost? | Reported by the caller after execution, keyed by `decision_id` |

Estimates and actuals are never written to the same field. The gap between
them is itself a signal worth surfacing — a consistently under-estimating
profile is a stale profile.

### 9.2 Shapes

```
CostProfile(
    pricing_model,       # free | metered | subscription | local
    currency,
    rates,               # [CostComponent]  unit ("input_token"|"image"|"minute"|...),
                         #                  amount_per_unit
    free_quota,          # units per period, if any
    subscription,        # SubscriptionTerms  period cost, renewal, included quota
    local_cost,          # LocalCostModel — see §9.3
)

CostLedgerEntry(
    decision_id, provider_id, ai_capability, objective_id,
    units_consumed, monetary_cost, currency,
    period,              # the accounting period it lands in
    recorded_at, reported_by,
)
```

`rates` is a list of components rather than named fields, because "what
you are billed per" is the fastest-changing thing in this entire
architecture. A new billing unit is a new `CostComponent`, never a schema
migration.

### 9.3 Local is not free, and the model says so

`LocalCostModel` carries an explicit, configurable non-monetary cost:
compute time, energy, and the opportunity cost of occupying the GPU. It
defaults to **zero monetary, non-zero latency/opportunity**.

Without this, the tier ladder would treat a 40-second local generation and
a 2-second free-cloud one as equally free, and the founder would sit
waiting for something a free cloud tier would have returned instantly.
Local-first is a *priority*, not a claim that local costs nothing.

### 9.4 Budgets are enforced, not reported

Configuration (§5.5) holds `monthly_cap`, `per_mission_cap`, and
`per_request_cap`. When a cap would be exceeded, the affected tiers are
**filtered out in Phase 1** (§6.1) — the Broker will refuse or route free
before it will exceed a cap. A budget that only produced a warning would
not be a budget.

Caps are per accounting period, and the period boundary is Configuration's
call, not the Broker's.

### 9.5 "Savings" is an estimate against a named counterfactual

A savings figure must always state *versus what*: "£38 this month versus
serving the same 412 decisions on the cheapest paid alternative that
clears their quality floors." Never a bare number.

The honest limitation, named: the counterfactual is itself an estimate,
because the paid provider might have succeeded on a task the local one
failed — in which case some of the "saving" is really a deferred cost.
Savings are therefore always reported next to the success rate for the
same period, so the two numbers are read together.

---

## 10. Deliverable 8 — Benchmark Engine

### 10.1 Shape

```
BenchmarkSample(
    sample_id, decision_id,           # joins to the decision that caused it
    provider_id, ai_capability, task_class,
    source,                           # passive | active
    verdict,                          # from Verification (ADR-0011) — matched | mismatched
                                      #                                 | inconclusive
    latency_ms, units_consumed, monetary_cost,
    error_kind,                       # None | timeout | rate_limited | refused | malformed
    host_id, provider_version,
    occurred_at,
)
```

### 10.2 Two sources, different properties, both needed

| | Passive | Active |
|---|---|---|
| Where from | Every real decision's reported outcome | A deliberate benchmark run |
| Cost | Free — work we were doing anyway | Real (compute, sometimes money) |
| Bias | Only covers what we actually run, on providers we actually chose | Unbiased, covers what we never pick |
| Approval | None | Required if it costs money (§12) |

Passive is the default and does the heavy lifting. Active exists to break
the feedback loop that passive alone creates: a provider ranked low is
never selected, so it never generates samples, so it stays ranked low
forever — including after an upgrade that fixed it. Active benchmarking is
the only way a Provider climbs back, and the Recommendation Engine is what
proposes running one.

### 10.3 Aggregates, not scans

The Decision Engine reads pre-computed aggregates keyed by
`(provider_id, ai_capability, task_class)`: success rate, latency
percentiles, reliability, sample count, and `last_sample_at`, each over a
configured recency window. Aggregates update incrementally as samples
arrive. Selection never scans raw history — see §14.

Recency-weighting is not optional: a provider's quality genuinely changes
under it when a vendor swaps the model behind an endpoint, and an
unweighted lifetime average would take months to notice.

### 10.4 Cold start — how an unknown Provider gets a fair first chance

A Provider with zero samples for a `(capability, task_class)` uses
`declared.quality × cold_start_penalty`, with `confidence: low`.

The penalty is what stops vendor claims from outranking measured
performance; the fact that it is a penalty and not a filter is what lets a
genuinely better new Provider get selected, generate samples, and earn its
place. Both halves matter — a pure filter means nothing new is ever tried,
and no penalty means every new arrival immediately displaces a proven one
on the strength of its own marketing.

`confidence` is carried on every selection (§3.5) and shown to the
founder, so "we picked this and we are not sure" is visible rather than
hidden behind a single number.

### 10.5 Verification-backed, always

Restating §3.7 because it is the load-bearing rule of this subsystem:
`verdict` is the Verification Verdict, not an API status code. `inconclusive`
is a distinct third value and is not counted as either success or failure
— treating "we could not tell" as success is how a benchmark store slowly
fills with fiction.

---

## 11. Deliverable 10 — AI Infrastructure Executive (contract only)

An ordinary Executive. Registered like any other, dispatched like any
other, permission-gated like any other. **Interface frozen here;
implementation is a future Mission Brief.**

| Capability | Risk tier | Returns |
|---|---|---|
| `AiInfrastructure.ScanHost` | `READ_ONLY` | A complete `AiAssetInventory` |
| `AiInfrastructure.ListApplications` | `READ_ONLY` | `[InstalledApplication]` |
| `AiInfrastructure.ListLocalModels` | `READ_ONLY` | `[LocalModel]` + `[Checkpoint]` |
| `AiInfrastructure.ProbeProvider` | `READ_ONLY` | reachability, version, health for one Provider |
| `AiInfrastructure.MeasureStorage` | `READ_ONLY` | `StorageUsage` |
| `AiInfrastructure.RunBenchmark` | `REVERSIBLE_WRITE` | `[BenchmarkSample]` — spends compute, sometimes money |
| `AiInfrastructure.AnalyseUsage` | `READ_ONLY` | `UsageAnalytics` + `[PolicyProposal]` — the learning loop (§19) |
| `AiInfrastructure.InstallProvider` | `IRREVERSIBLE` | Installed asset record — **Founder-approved only** (§11.1) |
| `AiInfrastructure.RemoveProvider` | `IRREVERSIBLE` | Reclaimed storage record — **Founder-approved only** (§11.1) |
| `AiInfrastructure.UpgradeProvider` | `IRREVERSIBLE` | Version change record — **Founder-approved only** (§11.1) |

Boundaries, frozen:

- It **proposes** `ProviderDescriptor`s; the Broker validates and admits
  them. It never writes the registry directly — the same reason Mission
  Control's adapter *reads* a plugin manifest rather than letting plugins
  mutate the catalogue.
- It **never selects a Provider.** It has no Decision Engine, no cost
  policy, and no ranking logic. If it ever grows one, that is the
  architecture failing.
- It **proposes policy changes; it never applies them** (§19.4).
- `RunBenchmark` and `AnalyseUsage` are the loop's two engines: one
  produces evidence, the other turns evidence into proposals.

### 11.1 Ecosystem mutation — added by founder ratification, 2026-07-29

MB027 as written froze this contract with **no install, download, or
removal capability**, deferring ecosystem mutation to a separate future
Executive. The founder's ratification assigns **discovery, installation,
benchmarking, and inventory** to this Executive, so the three
`IRREVERSIBLE` rows above are now part of its contract. That is a
deliberate expansion of scope, recorded here rather than absorbed
silently, and it comes with the gating that expansion requires:

1. **`IRREVERSIBLE` risk tier, always.** Per ADR-0009, an
   `ALWAYS_FOR_CAPABILITY` grant can *never* satisfy an `IRREVERSIBLE`
   check — so no standing approval can ever authorise an install, a
   removal, or an upgrade. **Every single one is a fresh founder
   decision.** This guarantee is mechanical and already shipped; the
   contract inherits it by choosing the tier honestly.
2. **MB027's "no automatic downloads" rule is unchanged and now
   structural.** Nothing in the system can *trigger* these capabilities.
   The Broker cannot — it executes nothing (§3.3). The Recommendation
   Engine cannot — recommendations are inert data (§8.2). The only path
   is: recommendation → founder accepts → Self-Development Queue item →
   normal Mission Control planning and approval → dispatched task. The
   capability exists; nothing but a founder starts it.
3. **Removal requires an impact statement.** A `RemoveProvider` proposal
   names every AI Capability that would become unserved or drop a tier if
   it went, checked against the current registry. "Reclaim 40 GB" without
   "and lose your only offline OCR" is not a decision a founder can
   actually make.
4. **Every mutation re-runs discovery.** An install, removal, or upgrade
   is followed by a `ScanHost`, so the inventory can never silently
   disagree with the machine — the state the Decision Engine's
   availability filter depends on (§6.1).

---

## 12. Deliverable 9 — Founder Approval Policy

### 12.1 Always requires approval

1. Any use of a metered paid API (tier 6).
2. Acquiring a new paid subscription, or upgrading an existing tier.
3. Activating a commercial licence, or any use whose licence terms require
   paid activation.
4. Any active benchmark that spends money.
5. Any single request whose estimated cost exceeds `per_request_cap`, and
   any decision that would cross `monthly_cap`.
6. **Sending data tagged sensitive to any third-party Provider — including
   a free one.**

Item 6 is not in MB027's list, and it is added deliberately. MB027's
approval policy is organised entirely around *money*, but a free cloud
model is a third party receiving the founder's data, and Constitution §3.3
criterion 2 already treats privacy as a first-class routing constraint. A
policy that gates a £0.002 paid call and waves through a free upload of
the same content would be protecting the wrong thing. Free is not the same
as private, and the policy now says so.

### 12.2 Never requires approval

- Local models already installed, used within their licence.
- Desktop AI applications already installed, used within their licence.
- Free cloud and aggregator tiers, for data not tagged sensitive.
- Open-source tools.
- Reading the inventory; generating recommendations; passive benchmarking;
  every read-only capability in §11.

### 12.3 Mechanism — the existing Permission System, not a new one

The Broker implements **no approval machinery**. An approval requirement
is expressed through Shared Infrastructure's Permission System (§5.2),
which already holds the grant ledger, already has veto power, and is
already Mission-wide.

Two properties fall out of that reuse, both of which would have had to be
rebuilt (and probably rebuilt wrong) in a bespoke mechanism:

- **A subscription purchase is `IRREVERSIBLE`.** Per ADR-0009, an
  `ALWAYS_FOR_CAPABILITY` grant can *never* satisfy an `IRREVERSIBLE`
  check. So a standing "yes, use paid AI" approval can never
  auto-authorise buying a new subscription. That guarantee is mechanical
  and already shipped — the Broker inherits it by not reinventing it.
- **One approval per mission** (§15.3) applies unchanged. A founder who
  approves paid reasoning for a mission is not asked again at every step.

The approval requirement is published as an `APPROVAL_REQUIRED` event —
the event type Mission Control already defines — so it reaches the Founder
Dashboard through the surface it already reads. No new channel.

### 12.4 The default is refusal, not escalation

If an approval is not granted, the Broker's decision stands as
`APPROVAL_REQUIRED` and the caller does not proceed. There is no timeout
that becomes a yes, no "proceed if the founder is away," and no fallback
to a cheaper provider that failed the quality floor. Absence of approval
is a stop.

---

## 13. Deliverables 11 & 12 — Executive and Capability Package interfaces

### 13.1 Deliverable 11 — the Desktop Executive contract (and every Executive after it)

Frozen, and stated generally because it must hold for Desktop, Research,
Knowledge, Filesystem, Terminal, Git, and everything not yet imagined:

```
Executive needs intelligence
        │
        ├──▶ builds CapabilityRequest(ai_capability, constraints, hints)
        │
        ├──▶ Broker.select(request) ──▶ BrokerDecision
        │
        ├──▶ if APPROVAL_REQUIRED or NO_CAPABLE_PROVIDER: report and stop
        │
        ├──▶ else invoke decision.selection.execution_capability
        │        through the Capability Registry, relaying its own grant
        │        (Rule 6), through the Operator's Worker Runtime (Rule 4)
        │
        └──▶ Broker.record_outcome(decision_id, OutcomeReport)
```

The five prohibitions, each mechanically testable at implementation time
by the import-parsing pattern MB023/MB024/MB025 already use:

1. **No Executive imports a provider SDK.** Only a Provider-adapter
   Executive does, and only for the Provider it adapts.
2. **No Executive reads the Provider Registry.** It asks; it does not
   browse.
3. **No Executive branches on `provider_id`.** It passes it through.
4. **No Executive holds a fallback provider** for when the Broker says no.
5. **No Executive caches a decision across missions.** Inventory, budget,
   and benchmarks move; a stale selection is a wrong selection.

The Desktop Executive therefore says *"I need `vision.ocr` on this
screenshot, local-only, quality floor 0.8"* — and has no idea, ever, which
engine ran.

### 13.2 Deliverable 12 — Capability Packages

A Capability Package is a future declarative bundle: capabilities it
provides, intelligence it needs, policy it assumes. The integration point
is frozen now so packages can be designed against it later.

```
Capability Package
        │  declares  requires_ai: [CapabilityNeed(ai_capability,
        │                          min_quality, privacy, modalities)]
        ▼
Registration ──▶ Broker.validate_needs(package)
        │            └─▶ satisfiable | unsatisfiable(reason, missing_needs)
        ▼
Runtime ──▶ package step issues CapabilityRequest ──▶ Broker ──▶ decision
        ▼
Operator executes the selected execution_capability
```

Three frozen rules:

1. **A package declares needs, never providers.** A package naming a
   specific Provider is **rejected at registration.** This is the
   mechanical guarantee that packages stay provider-agnostic — the same
   move as refusing to register a Provider whose `execution_binding` does
   not exist (§4.1 rule 4). A convention would be ignored; a rejection
   cannot be.
2. **Validation happens at registration, not first use.** A package whose
   needs cannot be met on this host says so at install time, with the
   missing needs named — and that unsatisfiable report is exactly the
   input the Recommendation Engine turns into *"install this to unlock
   that"* (§8).
3. **A package never gets a private Broker or a private policy.** One
   Broker, one policy, one ledger, one audit trail — for the same reason
   there is one Permission System (§5.2).

---

## 14. Compatibility with everything already frozen

MB027 Rules 10–14 require this. Each row states the integration surface
and what changes in the existing component: **nothing, in every row.**

| System | How the Broker integrates | Changes required there |
|---|---|---|
| **Constitution** | New Shared Infrastructure component; §3.3's four criteria map onto §6.5 unchanged; §17 terms preserved and extended (§1) | **One amendment, proposed not made** (§2.4) |
| **Mission Control** | Decisions, approvals, and recommendations are published as `Event`s on the existing bus, through an outbound port (§14.1). Recommendations reach the existing Self-Development Queue | None |
| **Runtime** | No interaction. The Runtime dispatches tasks and stays Executive-agnostic; it never selects intelligence | None |
| **Persistence** | Broker state is snapshot + event log, exactly MB025's shape (§14.2) | None (a new state kind, not a changed contract) |
| **Founder Dashboard** | A tenth panel over a new read-model slice, following ADR-0016 exactly: plain frozen data, tolerant reads, absence distinct from zero | None |
| **Permission System** | Reused verbatim for every approval (§12.3) | None |
| **Capability Registry (§5.1)** | The Broker's `execution_capability` is resolved through it, as any Capability is | None |
| **Capability Packages** | Frozen integration point (§13.2) | N/A — not yet built |
| **Existing Executives** | Browser, Filesystem: untouched. They do not use AI today and are not required to change | None |

### 14.1 How the Broker publishes without depending on Mission Control

The Broker is Shared Infrastructure; Mission Control sits above it. A
direct import would give a kernel service an upward dependency and break
§3.1.

Same solution MB025 used for the Runtime's `CheckpointSink`: **an outbound
port defined inside the Broker.**

```
broker/ports.py:  class DecisionSink(Protocol):
                      def emit(self, record: BrokerAuditRecord) -> None: ...

composition root: broker = AiCapabilityBroker(sink=EventBusDecisionSink(mc.bus))
```

The Broker knows a sink exists. It does not know what a bus is. A Broker
with no sink still decides correctly and simply records nothing — which is
also what makes it testable without a running system.

Proposed event types (additive, existing schema): `PROVIDER_SELECTED`,
`PROVIDER_SELECTION_REFUSED`, `PROVIDER_REGISTERED`, `INVENTORY_UPDATED`,
`BENCHMARK_RECORDED`, `RECOMMENDATION_GENERATED`, `COST_RECORDED`.
Approval reuses the existing `APPROVAL_REQUIRED`.

### 14.2 Why Broker state must persist, specifically

Not persisting it is a correctness bug, not a missing nicety:

- **The cost ledger.** A restart resetting monthly spend to zero means
  budget caps stop being caps after the first crash.
- **Standing approvals.** Re-asking after every restart trains a founder
  to approve reflexively, which destroys the value of asking.
- **Benchmark aggregates.** Losing them means every Provider returns to
  cold start, and the system permanently forgets what it learned.
- **The inventory.** Losing it makes every local Provider unavailable
  until a rescan — turning a restart into a silent, temporary downgrade to
  cloud providers, which is both a cost and a privacy event.

The registry itself is reconstructible (declared from Configuration,
discovered by rescan). The four items above are not.

---

## 15. The Scalability Question (Constitution Rule 1)

*Would this still be right at a million Missions, thousands of Workers,
hundreds of Capabilities, years of history, many Operator Instances?*

**Adding things — the costs that must stay flat, and do:**

| Adding | Cost |
|---|---|
| A Provider | One registration. Zero Broker edits. |
| An AI Capability | One string. No enum, no migration. |
| A provider class | One string. |
| A selection criterion | One rule appended to the ordered chain (§6.1/§6.3), not an edit to a scoring function. |
| A cost dimension | One `CostComponent`. |
| A recommendation kind | One recommender. |
| An Executive that needs AI | Zero Broker changes. It asks. |

**Where the real limits are, named now rather than discovered later:**

1. **Benchmark history is the first thing that grows without bound.**
   Mitigated by design — selection reads incrementally-maintained
   aggregates, never raw samples (§10.3), so decision latency is
   independent of history size. The raw samples still accumulate, and
   compaction is deliberately not designed here: a correct compaction
   policy needs a retention policy, which does not exist yet. This is the
   *same* open item already on `ROADMAP.md` for the event log, and it
   should be solved once, for both.
2. **Decision cost is O(candidates for one AI Capability)**, with the tier
   ladder short-circuiting at the first viable tier — so it is usually
   O(local providers). At thousands of Providers this holds only with an
   index by AI Capability; that index is part of the frozen design, not an
   optimisation to add later.
3. **The cost ledger must roll up.** Period totals maintained
   incrementally; a full ledger scan per decision would make the budget
   filter the slowest part of the system.
4. **Decision caching is deliberately NOT designed.** It looks free and is
   not: a cached decision must be invalidated by inventory changes, budget
   consumption, benchmark updates, and policy edits — four independent
   sources — and a stale hit spends money the budget filter would have
   refused. Determinism (§6.6) means it can be added safely later, with
   explicit invalidation, when a measured need exists.
5. **The Capability Matrix's declared half is hand-maintained** and will
   rot at scale. Mitigated structurally by observed-beats-declared (§5.3)
   — the matrix self-corrects for Providers actually used. Providers never
   used stay stale, which is exactly what active benchmarking (§10.2) and
   the Recommendation Engine exist to surface.
6. **Many Operator Instances / many hosts.** `host_id` is on the
   inventory, on benchmark samples, and on hardware — so per-host facts
   are already distinguishable. But *one Broker serving several hosts* is
   designed-for, not solved: which host's inventory applies to a decision
   is a routing question this document does not answer. Consistent with
   ADR-0013's posture — the data model does not have to be rebuilt, and
   the dispatch rule is a future brief's problem.

---

## 16. Technical Debt and Known Limitations (Constitution Rule 10)

1. ~~A Constitution amendment is required and has not been made.~~
   **Resolved 2026-07-29** — ratified by the founder and applied as
   Amendment 2 (§2.4). The Broker's placement is now Constitution text,
   at status RESEARCH-BACKED.
2. **`ModelRouter.select_provider()` is a live contradiction of this
   design and of Constitution §14.** `plugins/model_router.py` currently
   hardcodes the strings `"hermes"` and `"chatgpt"` in its routing
   branches — product names in Brain logic, which §14/§21 forbid. The
   Broker supersedes that method entirely: the Model Router keeps its
   `generate()` interface and its role as the Brain's single door to
   reasoning, and resolves *which* provider by asking the Broker. **This
   Mission Brief changes no code**; the migration is named here and on
   `ROADMAP.md` as a future implementation brief.
3. **Success-probability estimation for a novel task class is the weakest
   part of this design.** Cold start (§10.4) is defined and reasonable,
   but genuinely unproven — the first real workload will likely force a
   revision of the penalty and the floor defaults. Configuration, not
   constants, is the hedge.
4. **Rate-limit headroom is estimated from our own accounting.** If
   another process shares a credential, the estimate drifts and the filter
   under-rejects. Correct fix is provider-reported headroom, which is
   provider-specific and therefore out of scope here.
5. **Desktop applications are the least verifiable Providers.** A GUI
   application publishes no manifest and no capability list; what it can
   do must be declared by the founder or inferred. `unverified` (§4.5)
   exists for exactly this, but it is a mitigation, not a solution.
6. **Active benchmarking policy is minimal on purpose.** *What* to
   benchmark, how often, and against which reference tasks is a real
   design problem this document does not solve — it freezes the shape
   (`source: active`, approval-gated) and defers the scheduling policy.
7. **Multi-host brokering is designed-for, not solved** (§15 item 6).
8. **Local cost coefficients are guesses** until measured (§9.3). They are
   configuration and should be treated as such — a default, not a fact.
9. **The learning loop's guards are reasoned, not calibrated** (§19).
   Exploration budget, minimum sample counts, review windows, and rollback
   thresholds are all configuration with no empirical basis yet — the
   right values are unknowable before real usage. The *shape* is frozen;
   every number in it should be treated as a first guess.
10. **Rollback reverts policy, never effects.** A policy version can be
    reverted mechanically (§19.5). An install, a removal, or a month of
    spend made under it cannot. This is why ecosystem mutation is
    `IRREVERSIBLE`-tier and separately founder-approved (§11.1) rather
    than covered by the loop's rollback guarantee — the two mechanisms
    protect different things and neither substitutes for the other.

---

## 17. The Final Architectural Question

> *"Does this architecture increase Kalpavriksha's ability to build
> Kalpavriksha?"*

**Yes — unambiguously.** Four specific mechanisms, not a general feeling:

1. **It removes the last per-Executive decision that would have had to be
   made N times.** Every future Executive — Desktop, Research, Knowledge,
   Terminal, Git — would otherwise each pick its own provider, hold its
   own key, and encode its own fallback. That is N copies of the same
   policy drifting apart, and the single biggest tax on building
   Executives quickly. With the Broker, an Executive that needs
   intelligence writes one `CapabilityRequest` and is done. **The cost of
   building the next Executive goes down because this exists.**
2. **It makes self-improvement measurable.** The Benchmark Store plus the
   cost ledger mean Kalpavriksha can answer "am I getting better at this,
   and at what price?" with evidence rather than impression. Self-
   development without measurement is just change.
3. **It makes the system's own growth affordable.** A system that builds
   itself makes an enormous number of AI calls. Routing them local-first
   with a quality floor is the difference between an autonomous system the
   founder can afford to run continuously and one that is rationed — and
   the runtime is already continuous (MB024) and already survives restarts
   (MB025).
4. **It closes the last open loop in the Kalpavriksha Loop.** MB023 gave
   the system coordination, MB024 a heartbeat, MB025 memory across
   restarts, MB026 a window. All four assumed intelligence was simply
   available. This is the layer that decides where intelligence comes
   from — and it is the dependency every remaining Executive on the
   roadmap is blocked behind.

The honest counter-argument, stated rather than avoided: this adds a
component every future Executive depends on, and a bug in it degrades
every mission at once. That is real. It is mitigated by the Broker being
deterministic policy over data with no I/O (§6.6) — the most testable
shape in this codebase — and by the refusal-over-guessing rule, which
makes its worst realistic failure mode "the system stops and says why"
rather than "the system quietly used the wrong thing."

---

## 18. What this Mission Brief did not do

Named explicitly, because "architecture only" is a promise that should be
checkable:

- No code. `src/` and `tests/` are byte-identical to the MB026 tag.
- No provider integration, no SDK, no API key handling, no network call.
- No Desktop automation.
- No change to Mission Control, the Runtime, Persistence, the Dashboard,
  or any Executive.
- No installation, download, or removal of anything.
- **Constitution edit:** none by the Mission Brief itself — the amendment
  was written out and *proposed* in ADR-0017 (§2.4). **The founder
  ratified it on 2026-07-29**, and it was then applied as **Amendment 2**
  (`FOUNDER_CONSTITUTION_FREEZE.md` §4a). The sequence matters and is the
  precedent: proposed by the brief, applied only after ratification.

---

## 19. The Learning Loop

Status: **Frozen in shape, EVOLVABLE in policy** — added 2026-07-29 by
founder directive at ratification. Decision record:
`docs/adr/0018-broker-learning-loop.md`.

> *"The Broker must become self-improving through long-term usage
> analytics, benchmark history, cost optimization, privacy awareness, and
> Founder-approved AI ecosystem evolution. This learning loop should
> become a first-class architectural objective for the AI Infrastructure
> Executive."*

### 19.1 The constraint this has to satisfy

A self-improving Broker sits directly against §6.6, which freezes
determinism and replay as the mechanism that makes every provider decision
auditable. A component that quietly changes how it decides is a component
whose past decisions can no longer be explained.

Both are non-negotiable, so the resolution is not a compromise between
them — it is a separation:

> **The decision *procedure* never learns. The *policy* it reads does —
> versioned, evidence-backed, and Founder-promoted.**

Every decision already carries `policy_version` (§3.5). A decision made
under policy v7 is replayed against policy v7 forever. Learning produces
policy v8, as a discrete, reviewable, reversible artifact — not a drift in
behaviour that nobody can point at.

### 19.2 Three owners, and why the split is exactly here

| Stage | Owner | Why |
|---|---|---|
| **Data** — decisions, outcomes, costs, benchmark aggregates | The Broker | It already owns them, and owning data is not learning |
| **Analysis** — turning that data into proposals | The **AI Infrastructure Executive** | Analysis is work; work happens in an Executive. This is the founder's directive, and it is also the only placement that keeps the Broker deterministic |
| **Promotion** — deciding a proposal becomes policy | The Founder, via Promotion Review | §9.4, §15.5 — unchanged |

The Broker must not analyse itself. If it did, the kernel service that
every mission depends on would acquire a periodic, expensive, model-driven
workload — and the component that must be replayable would be the one
rewriting its own rules. Analysis is an *ordinary mission*, dispatched by
the Runtime like any other (MB024), which also means it is bounded,
observable, interruptible, and free to be expensive.

### 19.3 The loop is the Knowledge Lifecycle, not a new mechanism

This is the point that keeps the design small. ADR-0012 already defines:

```
Execution → Evidence → Knowledge Candidate → Promotion Review
          → Permanent Knowledge → Future Reasoning
```

The learning loop is that lifecycle, applied to intelligence selection:

```
BrokerDecision → OutcomeReport (Verification-backed)
      → BenchmarkSample + CostLedgerEntry          [Evidence]
      → UsageAnalytics + PolicyProposal            [Knowledge Candidate]
      → Founder Promotion Review                   [ADR-0012, human-gated]
      → policy vN+1                                [Permanent Knowledge]
      → every subsequent decision                  [Future Reasoning]
```

Nothing new is built for promotion. MB023 already ships the **Knowledge
Acquisition Queue** with the gate enforced *in code* — advancing past
verification requires `human_approved=True`, and the refusal is published
as an auditable event. A policy proposal is a Knowledge Candidate and
rides that machinery unchanged.

Ecosystem proposals (install / remove / upgrade) ride the **Self-
Development Queue** the same way (§8.3, §11.1). Two existing queues, two
existing gates, zero new approval paths.

### 19.4 The five learning inputs, each with an owner and a guard

| Input (founder's words) | Produced from | Proposes | Hard guard |
|---|---|---|---|
| **Long-term usage analytics** | The decision record: capability mix, tier distribution, refusal rate, approval friction, re-ask rate | Floor tuning, tier-order exceptions, capability coverage gaps | Minimum sample counts before any proposal; a proposal citing fewer is refused at generation |
| **Benchmark history** | `BenchmarkSample` aggregates, recency-weighted (§10.3) | Ranking adjustments, re-benchmark targets, provider retirement | Verification-backed samples only (§10.5); `inconclusive` is never evidence |
| **Cost optimization** | `CostLedger` vs. counterfactuals (§9.5) | Local/cloud rebalancing, budget re-allocation, subscription value review | A proposal that lowers a quality floor must show the *verified* success rate holds; floors have configured hard minimums the loop cannot propose below |
| **Privacy awareness** | Which capabilities carry sensitive data, and where those requests were served | **Tightening only** | **One-way ratchet: the loop may propose tightening a privacy constraint and may never propose loosening one.** Loosening is a founder-initiated act, never a system-initiated proposal |
| **AI ecosystem evolution** | Inventory + coverage gaps + benchmark + cost | Install / remove / upgrade (§11.1) | `IRREVERSIBLE` tier — no standing grant can ever satisfy it (ADR-0009). Removal requires an impact statement |

### 19.5 The pathologies this loop would otherwise develop

Named, because a learning loop that nobody has argued against is a
learning loop nobody has understood:

1. **Selection bias.** A Provider ranked low is never chosen, so it never
   generates samples, so it stays low — permanently, including after an
   upgrade that fixed it. Countered by active benchmarking (§10.2) and by
   a small **exploration budget**: a configured fraction of low-stakes
   requests deliberately go to a viable non-winner, and the resulting
   samples are what let a Provider climb back. Without this, the loop
   converges on whatever it happened to try first.
2. **The cost–quality death spiral.** Lower the floor → save money → more
   failures → more re-asks and retries → *higher* total cost and worse
   outcomes, while the cost report still shows a saving because it counts
   spend and not failure. Countered by the guard in §19.4 and by the rule
   that every cost proposal reports success rate beside spend (§9.5).
3. **Overfitting to a fortnight.** Recency-weighting is necessary (vendors
   swap models behind endpoints) and dangerous (a bad week rewrites
   policy). Countered by bounded windows, minimum sample counts, and the
   fact that proposals are *proposed* — a human sees the sample size.
4. **Self-serving measurement.** The loop must not be the sole judge of
   its own changes. **Every promoted policy change carries a review window
   and an automatic rollback trigger**: if the observed verified success
   rate for the affected capabilities degrades beyond a configured
   threshold during the window, the policy reverts to the prior version
   and the reversion is published as an event. Rollback is mechanical
   because `policy_version` is already first-class — this costs nothing
   extra to build.
5. **Quiet scope creep into decisions.** The single failure that would
   invalidate this whole design: the Executive growing a ranking function
   of its own. Countered structurally — it emits `PolicyProposal`s and has
   no path to apply one (§11 boundaries), the same way the Broker has no
   path to execute.

### 19.6 What a proposal looks like

```
PolicyProposal(
    proposal_id, kind,          # floor_adjust | rank_weight | tier_exception
                                # | budget_reallocate | privacy_tighten
                                # | provider_retire | rebenchmark
    target,                     # the policy element it would change
    current_value, proposed_value,
    evidence,                   # decision_ids, sample_ids, ledger refs — required
    sample_count, window,
    expected_effect,            # success-rate delta, cost delta, latency delta
    rollback_condition,         # required — the metric and threshold that reverts it
    review_window,
    requires_approval,          # always true for anything that spends or loosens
    generated_at, analyst,      # the executive_id and its own policy version
)
```

A proposal without `evidence` or without a `rollback_condition` is refused
at generation. Both are non-optional for the same reason: a change that
cannot be justified and a change that cannot be undone are the two kinds
this system should never accept from itself.

### 19.7 What the founder sees

One surface, not a new one: the Founder Dashboard's intelligence panel
(§14) gains proposals alongside recommendations — each with its evidence,
its sample size, its expected effect, its rollback condition, and a single
accept/reject. The standing discipline applies: **the raw numbers are
shown beside the judgement**, so a founder can always check the proposal
against what produced it (ADR-0016).

### 19.8 The Policy Simulator — scheduled, not designed here

Status: **Scheduled future enhancement** — founder directive, 2026-07-29.
Named now so the loop is not built in a way that forecloses it. Not
designed in this document, and deliberately not implemented.

> Validate a proposed policy version against historical missions **before**
> it is presented for Founder approval.

**Why this is possible at all, and why it is nearly free:** §6.6 already
freezes every decision as deterministic and replayable, with an
`inputs_digest` over the five things that produced it. Replaying history
under a *different* policy is the same mechanism pointed at a different
version. The simulator is not a new capability the architecture has to
grow — it is a consequence of a decision already made, which is the
clearest possible sign that decision was the right one.

Shape, to the depth needed to reserve the space:

- A `READ_ONLY` capability of the AI Infrastructure Executive
  (`AiInfrastructure.SimulatePolicy`). It decides nothing, executes
  nothing, spends nothing, and calls no Provider.
- Input: a candidate policy version plus a historical window. Output: a
  `PolicySimulation` — which past decisions would have changed, how tier
  distribution shifts, estimated cost delta, and concrete examples.
- It becomes a **required attachment to a `PolicyProposal`** (§19.6), so
  the founder approves against "this would have changed 34 of 1,206
  decisions, here are five of them" rather than against a claim.

**The limit that has to be built in from the start, or the simulator
becomes actively harmful:** replay can say what would have been
*selected*. It cannot say whether the alternative would have *succeeded* —
there is no outcome on record for a Provider that was never called. So a
simulation reports selection changes and cost deltas as **fact**, and
success-rate effects only as an **estimate from benchmark aggregates,
labelled as such**. A simulator that blurred the two would manufacture
confidence at precisely the moment a founder is deciding whether to trust
the system's judgement about itself — worse than having no simulator at
all.

Two guards, reserved with the space:

1. **A simulation informs the founder; it never promotes.** No threshold
   on a simulation result may auto-approve a proposal. The human gate
   (§19.3) is unchanged by better evidence arriving in front of it.
2. **A simulation is evidence, and is recorded like any other** — attached
   to the proposal, replayable, and reviewable after the fact against what
   actually happened once the policy was live.

### 19.9 Why this belongs to the AI Infrastructure Executive

The founder's directive places it there, and the architecture agrees for a
reason worth recording: the Executive is already the component that
*observes the world outside the Broker's ledgers* — what is installed,
what the hardware can do, what a provider actually returns when probed.
Usage analytics without that context produces proposals that are correct
about the data and wrong about the machine ("switch to the 70B local
model" on a host that cannot load it). One Executive holding both the
measurements and the machine is the only placement where a proposal can be
checked for feasibility before a founder ever sees it.
