# Desktop Intelligence — Reasoning Provider Design

Status: design only. No production code written. No Planner, Broker,
provider registry, Founder Edition, Browser Executive, or Desktop Executor
file modified.

Constitution consulted directly, primary source (not summaries):
`docs/architecture/KALPAVRIKSHA_VISION_V2.md` §3 (Brain), §4 (Operator),
§5 (Shared Infrastructure, especially §5.7 AI Capability Broker and §5.8),
§6 (Brain/Shared Infrastructure/Operator Separation — the load-bearing
table), §7 (Environment Philosophy), §8 (Multi-Operator/Environment
Session), §9 (Knowledge Lifecycle), §10 (Verification), §11 (Recovery),
§12 (Worker and Plugin Runtime, by reference), §20 (Immutable Rules,
especially Rule 4); `AI_CAPABILITY_BROKER_ARCHITECTURE.md` §4 (provider
classes, `execution_binding`); `docs/adr/0017-ai-capability-broker.md`;
`FOUNDER_CONSTITUTION_FREEZE.md`; the current source of `providers/ollama.py`,
`ai_infrastructure/execution.py`, `ai_infrastructure/service.py`,
`planner/planner.py`; and this session's own prior evidence (Gate 3 audit,
reasoning-layer discovery run, Build 1's finding that no local API exists
for Claude Desktop).

**A genuine constitutional conflict was found and is reported below (§C),
per this mission's own instruction to stop and escalate rather than design
around it.** A second, narrower, architecturally clean use case survives
the conflict and is designed fully.

---

## Executive Conclusion

**For the use case this whole effort has been chasing — using Claude
Desktop as the reasoning provider for `Planner.plan()` — the answer is
Classification C: a real constitutional conflict, not a missing detail.**

The Constitution's own §6 table is unambiguous: for "Environment access,"
Brain = Never, Shared Infrastructure = Never, Operator = Only through a
Worker, via an Environment Session it owns. §5.7 states the Broker
"decides and never touches the machine." Driving Claude Desktop's UI
(typing a prompt, waiting, reading a reply) is unambiguously Environment
access — the paradigm case, not a borderline one. The code path that
calls a reasoning provider today (`Planner.plan()` → Model Router →
`PromptExecutor.run()` → `provider.complete()`) is Brain/Shared-
Infrastructure-layer code, by the Constitution's own classification. A
provider adapter that drives Claude Desktop's window from inside that
call is not a "smallest extension" — it is a direct violation of a FROZEN
section and a FROZEN Immutable Rule, regardless of how small the
implementation is.

The deeper reason this cannot be patched around: **planning happens
before any Mission, Task, or Operator Instance exists.** Environment
access is only ever granted to an already-running Operator Instance via
an Environment Session it already owns. There is no Environment Session
to drive Claude Desktop through until a Mission is already executing —
and a Mission cannot start executing until the Planner has already
produced a plan. Using a UI-driven desktop application to answer the
Planner's own reasoning request is circular by construction, not merely
unwired.

**A second, different use case is not circular, and the architecture
already designs the correct mechanism for it — RESEARCH-BACKED, not yet
implemented:** a Worker that is already executing, already holds an
Environment Session (already has legitimate Environment access), needing
a reasoning opinion as *part of* its own capability. There, the Operator
already exists and already owns Environment access — asking Claude
Desktop for help mid-task is just another Capability the Operator
dispatches "through the Operator like any other Capability" (§5.7),
exactly the way `execution_capability`/`execution_binding` was designed
to work. This case is designed fully below (§§ Proposed flows onward) and
is the legitimate way to realize "use Desktop Intelligence to avoid API
cost" without violating anything.

**These are not the same feature.** The Founder's stated goal (avoid
paid API cost by using an installed AI app) is realizable — but not by
making Claude Desktop *the Planner's* reasoning provider. It is realizable
as a mid-task reasoning aid a Worker can call on, through the mechanism
already named in frozen architecture.

---

## Existing Architecture

Traced end to end this session, with evidence:

- **Planner** (`planner/planner.py`, MB036): fully implemented, not a
  stub. `plan(intent)` builds a prompt, constructs a `RoutingContext`
  (`capability="reasoning"`), and calls its `runner` (a `PromptExecutor`).
- **AI Capability Broker** (`broker/broker.py`, MB031): pure decision
  function — filter, apply quality floor, rank, pick first. Takes
  `ProviderProfile`s as an argument; holds no live provider knowledge
  itself.
- **Provider estate** (`ai_infrastructure/profiles.py::ProviderSource`):
  rebuilds `ProviderProfile`s fresh on every request from the **Desktop
  Executive's own last machine scan** (`desktop.cached_inventory`) joined
  against a static, founder-editable `PROVIDER_CATALOG`
  (`ai_infrastructure/catalog.py`). This is the existing, correct join —
  reused unchanged.
- **Provider execution** (`ai_infrastructure/execution.py::PromptExecutor`):
  after the Broker picks a winner, looks up `providers.get(provider_id)`
  in a `PluginRegistry` and calls `provider.complete(prompt, context, ...)`.
  Only `providers/ollama.py::OllamaProvider` implements this today.
- **Constitution's own classification of `desktop_application`-class
  providers** (`AI_CAPABILITY_BROKER_ARCHITECTURE.md` §4.2): *"an
  installed AI application driven as an application"* — and its intended
  execution path (§5.7) is `execution_capability`/`execution_binding`: the
  Broker's decision *names* an already-registered Capability, and *the
  caller runs it through the Operator like any other Capability* — never
  through the Broker or the provider-execution layer directly.

---

## Proven Current Capabilities

Verified live, this session (`reasoning_layer_discovery.py`, read-only):

- Real machine scan (existing `DesktopPlugin.inventory(refresh=True)`,
  no new scanner) finds `claude_desktop` installed, healthy, version
  1.28929.0.0; `ollama` installed, healthy; `lm_studio` not installed.
- `ProviderSource` correctly reports `claude-desktop` as available, free,
  reasoning-capable.
- The Broker, using the existing `prefer_free` policy and the existing
  `TaskProfile.exclude_providers` field (no new mechanism), correctly
  selects `claude-desktop` (quality 0.90) once Ollama is excluded — proving
  the *decision* layer is completely sound.
- Mouse, keyboard, and window control are real and proven (P0 Gate 1) —
  so *if* a constitutionally correct dispatch path existed, the primitives
  to drive Claude Desktop's window already work.

---

## Missing Capability

Not a missing provider adapter (Build 1 already established that: no
local API exists for Claude Desktop). The actual missing piece, this
mission establishes, is a **constitutionally valid dispatch path** for
Environment-touching provider execution — and that path is only
well-formed for callers who already own an Environment Session. No such
path can be well-formed for the Planner itself, because the Planner runs
before any Environment Session exists.

---

## Proposed Request Flow (mid-task use case only — see Executive Conclusion)

```
Worker (already executing, already owns an Environment Session)
  │  e.g. Desktop Executive mid-Task, needs a reasoning opinion
  ▼
Worker asks the Broker: "which provider serves `reasoning` for this?"
  (same AiCapabilityService.decide() call every other caller uses)
  ▼
Broker selects among eligible profiles — INCLUDING desktop_application
  class providers now, because the CALLER already has Environment access
  ▼
Decision names execution_capability = e.g. "DesktopExecutive.AskDesktopAI"
  (a Capability already registered in the Capability Registry, per §5.7:
  "its output names an already-registered Capability plus parameters")
  ▼
The Worker (Operator-side, already holding the Environment Session) runs
  that Capability through its OWN Worker Runtime — no new execution path,
  no Broker involvement in the actual drive
  ▼
The named Capability's Action (new, small, Desktop-Executive-owned):
  focus/open the target app's window → type the prompt → wait → observe
  → extract the reply, using the SAME window/keyboard/observation
  primitives Gate 1/Gate 2 already proved
```

## Proposed Response Flow

```
Action returns an ExecutionResult (the reply text, or a structured
  failure) — same shape every other Desktop Executive Action returns
  ▼
Caller (the Worker that asked) treats the reply as raw text — it is NOT
  automatically Evidence, NOT automatically a plan, NOT automatically
  trusted; the calling Worker's own logic decides what to do with an
  opinion, the same way a human's opinion would be treated: informative,
  not authoritative
  ▼
If the calling Worker uses the reply to inform its own Step's outcome,
  THAT Step still goes through Verification (§10) normally — the AI
  app's reply is Reasoning-Provider-Output, the *weakest* tier of the
  Evidence Hierarchy (§9.2, rung 5), never treated as Observed Reality
```

---

## Component Ownership

| Component | Owner | Why it belongs here | Why an existing component is insufficient |
|---|---|---|---|
| `DesktopApplicationAction` (new, small) | Desktop Executive (`desktop/actions.py`, already the Environment's one door for this Environment) | It is Environment access — Rule 4 gives it exactly one door, and this is that door | `DesktopExecutor`'s existing actions are app-launch/close/click/type primitives with no notion of "wait for an AI reply and extract it"; this is a genuinely new, small Action composed from existing primitives (window focus, type, wait, observe) — not a new authority |
| Capability registration for that Action | Same registration path every Desktop Executive Action already uses (manifest → Capability Registry) | Rule 3: "Adding capability #N costs one new file, never an edit to the Registry" | N/A — this is the existing mechanism, used as designed |
| `execution_capability` naming on the `claude-desktop` `ProviderDescriptor` | AI Capability Broker's Provider Registry (`broker/registry.py`), already has the field | §5.7's own design: a Provider's descriptor already carries `execution_capability`/`execution_parameters` | Already exists; needs a value filled in, not a new field |
| The decision to select `claude-desktop` for a mid-task reasoning need | `CapabilityBroker` (unchanged) | Same decision engine, same policy, same `exclude_providers` mechanism already proven this session | N/A |
| Deciding *whether* to trust/use the AI app's reply | The calling Worker (Operator-side), never the Broker, never a new component | The Broker only decides *which provider*, never *what to do with the answer* (§5.7's boundary) | N/A |

**No new top-level authority is proposed anywhere in this design.** The
only new code is one small Action inside the Desktop Executive — the same
shape as every other Desktop Executive Action — and one filled-in field
on an existing data structure.

---

## Provider Contract

**Do not extend `PluginRegistry.get(provider_id).complete()` to cover
`desktop_application` class.** That contract is correct for
`local_runtime`/`cloud_api` classes (Ollama, a future real Claude API key)
precisely because those calls do not touch the Environment — an HTTP call
to a local daemon or a remote host is not Environment access in the
Constitution's sense (§21's illustrative table scopes "Desktop
Environment" to "the host operating system's filesystem, shell, and
installed applications" — driving an app's window is squarely inside
that; calling an HTTP API is not).

Forcing `desktop_application` class into the same `.complete()` shape
would require the provider object itself to touch the Environment from
inside Shared-Infrastructure/Brain-layer code — the exact thing Rule 4
and the §6 table forbid. **The existing, correct contract for this class
is `execution_capability`/`execution_binding` (§5.7), not `.complete()`.**
This is not a new provider contract — it is the contract the Constitution
already specifies for exactly this provider class, currently unbuilt.

---

## Desktop Intelligence Binding

`ProviderDescriptor.execution_capability` (already a field,
`broker/registry.py:58`) should be set to the qualified name of the new
Desktop Executive Action (e.g. `DesktopExecutive.AskDesktopAI`) for the
`claude-desktop` catalog entry. `execution_parameters` carries whatever
fixed parameters identify *which* installed app to drive (so the same
binding shape generalizes — see below). This is data on an existing
descriptor, not a new mechanism.

---

## Claude Desktop — First Implementation Target

Scoped narrowly, for the mid-task use case only:

1. One new Desktop Executive Action, `AskDesktopAI` (or similarly named),
   parameterized by which installed AI app to drive (`claude-desktop`,
   later `chatgpt-desktop`, ...).
2. Uses existing window-focus, keyboard-type, and observation primitives
   already proven (Gate 1/Gate 2) — no new input backend.
3. Registered as a Capability the normal way (Rule 3).
4. `claude-desktop`'s `ProviderDescriptor.execution_capability` set to
   this Action's qualified name.
5. **Not wired to `Planner.plan()`.** The Planner's own reasoning request
   still requires a non-Environment-touching provider (a real Ollama
   call, or a real cloud API key) — this is the §7.1 "local-first" floor
   the Constitution already requires, and it is untouched by this design.

---

## Multi-Provider Generalization

Nothing here is Claude-specific beyond the one Action's parameters and
the one catalog entry's `execution_capability` value:

- A second `desktop_application` provider (ChatGPT Desktop) needs: one
  more `PROVIDER_CATALOG` entry (already how the catalog is designed to
  grow — "adding a provider is one entry and nothing else changes"), and
  either a shared parameterized Action (`AskDesktopAI(app="chatgpt-desktop")`)
  or, if the UI shape differs enough, one more small Action. Either way,
  zero changes to the Broker, the Planner, the registry mechanism, or the
  Capability Registry itself.

---

## Security Boundary

- The Action reads and types only the reasoning prompt supplied by its
  caller — never anything else on screen.
- No clipboard access to unrelated content; no credential/cookie/token
  extraction; no reading of unrelated conversation history in the AI
  app's own window.
- The Action never submits the caller's *task* to the AI app for
  execution — only a reasoning prompt. The Founder's "reasoning resource,
  not execution authority" boundary (§3 of this mission) is enforced
  structurally: the Action's contract is "prompt in, text out," nothing
  else, mirroring `provider.complete()`'s own shape even though it is
  reached through a different, Environment-legitimate door.
- Because it is a genuine Capability, it is gated by the existing
  Permission System (Rule 5) like every other above-`READ_ONLY` action —
  no bypass.

---

## Failure Handling (provider-level only, per this mission's scope)

| Failure | Handling |
|---|---|
| App not installed | `ProviderSource.availability()` already reports this (existing, unchanged) — Broker never selects it |
| App not running | Action's own first step: focus-or-launch, same pattern `DesktopExecutor` already uses for other apps |
| Launch failure | `ExecutionResult(success=False, ...)` — same shape every Action already returns; caller treats as a failed reasoning attempt, not a crash |
| Window/input-field not found | Same — a failure result, not an exception |
| Response timeout | Bounded wait, same timeout-governance pattern `desktop_operator/timeouts.py` already provides — reused, not reinvented |
| Response extraction failure | Failure result; never a guessed/partial answer |
| Unexpected UI state | Failure result — the Action never assumes prior state, always re-observes before acting (matches the existing Desktop Executive's own discipline) |

No new recovery engine. No objective-level recovery designed here — this
is exactly the provider-level scope this mission asks for.

---

## Verification

The AI app's reply is Reasoning-Provider-Output — Evidence Hierarchy
rung 5, the *weakest* tier (§9.2), explicitly *never* treated as evidence
of reality. If the calling Worker's Step uses the reply to decide
something about the real world, that Step's own Expected Outcome is still
checked by the existing Verification Subsystem exactly as any other Step
would be — the AI app's opinion is an input to reasoning, not a
substitute for Verification. No new verification mechanism is proposed.

---

## Cost Model

Zero marginal cost, matching the catalog's own accounting
(`cost_per_call=0.0`, "runs on an existing subscription"). No paid API
calls. No credential configuration. No Ollama involvement of any kind.

---

## Architectural Risks

1. **The temptation to "just make it work" for Planning by loosening
   Rule 4** is the single largest risk this design exists to name and
   refuse. Nothing in this document proposes that, and nothing should.
2. **UI automation is inherently more fragile than an API call** — window
   titles change, layouts change, a login prompt appears unexpectedly.
   This is a real, ongoing maintenance cost for whichever Action gets
   built, independent of the constitutional question. Timeout and
   failure-result discipline (above) contains it; it does not eliminate
   it.
3. **Scope creep toward "the Desktop Executive can now converse with AI
   apps generally"** — the Action's contract must stay narrow (prompt in,
   text out, one bounded interaction), or it starts to look like a second
   reasoning surface living inside the Operator, which would itself raise
   new boundary questions.

---

## Rejected Alternatives

- **A. `DesktopApplicationProvider` implementing `.complete()` directly,
  calling mouse/keyboard from inside the provider-execution layer** —
  rejected: unambiguous Rule 4 / §6 violation, evidenced above. This was
  the shape Build 1 was implicitly asked to build; this mission's own
  Constitution-first reading is what surfaced why it cannot be built as
  specified.
- **B. A "bootstrap" Environment Session stood up before any Mission
  exists, purely to service Planner-time reasoning calls** — considered
  for the Planning use case specifically. Rejected as out of this
  mission's scope: it is not a small extension, it is a new architectural
  concept (an Environment Session with no owning Mission/Task), and
  Section 4 of this mission explicitly forbids inventing new execution
  authorities. Named here so it is not silently forgotten, per Rule 10.
- **C. Clipboard-based response extraction** — considered as the response-
  extraction mechanism for the mid-task Action. Not rejected outright
  (it is one legitimate option among the existing observation
  mechanisms), but not selected as *the* mechanism here since Section 9
  of this mission restricts it to cases explicitly allowed by
  architecture, and window/accessibility-based reading (the same
  observation approach already proven for Gate 2's browser work) is the
  more consistent choice — left as an implementation-time decision for
  the build mission, not decided here.
- **D. OCR** — rejected for this design, per Section 9's explicit
  instruction; not shown to be necessary since the target apps expose
  real windows with real text content, not images.

---

## Smallest Correct Implementation

For the **mid-task use case** (the only one this design finds
constitutionally sound):

1. One new, narrow Desktop Executive Action (Environment access stays
   inside the one existing door).
2. One filled-in field (`execution_capability`) on the existing
   `claude-desktop` `ProviderDescriptor`.
3. Zero changes to the Broker, the Planner, the Capability Registry
   mechanism, the provider-execution contract for `local_runtime`/
   `cloud_api` classes, or Mission Control.

For the **Planning use case** (the one every prior mission in this
thread has actually been chasing): **no implementation is smaller than
"do not build this,"** because the request itself is constitutionally
unsatisfiable as currently framed. The Founder's underlying goal (avoid
paid API cost) is still reachable — through a real local reasoning
provider for Planning (Ollama, currently disabled by Founder choice; or a
future genuinely local model), with Claude Desktop available as a
mid-task reasoning aid once §"Claude Desktop — First Implementation
Target" is built.

---

## Implementation Decision

**Classification: C — CONSTITUTIONAL / ARCHITECTURAL CONFLICT**, for the
Planning use case. STOP and escalate — this is not a mission a Founder/CTO
"accepts a small extension" into; it is a request that conflicts with two
FROZEN sections (§6, Rule 4) as currently framed, and resolving it would
require either changing the Founder's own "Ollama stays disabled"
constraint (making a real local/cloud provider available for Planning) or
formally amending the Constitution to invent a new "pre-Mission Environment
Session" concept — a decision only the Founder can ratify, per this
project's own amendment process (`FOUNDER_CONSTITUTION_FREEZE.md` §4a).

**For the mid-task use case, separately: Classification A — the design
already exists** (`AI_CAPABILITY_BROKER_ARCHITECTURE.md` §5.7's
`execution_capability`/`execution_binding` mechanism, RESEARCH-BACKED,
frozen in shape). Implementation is missing. A future, separately-scoped
build mission could implement exactly the "Smallest Correct
Implementation" above, once the Founder decides whether that narrower
capability (Desktop Executive can consult an installed AI app mid-task)
is worth building on its own — it does not solve "avoid API cost for
Planning," and should not be sold to the Founder as doing so.

STOP.
