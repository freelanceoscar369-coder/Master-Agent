# Constitutional Kernel Specification v1.0

**Type:** Implementation architecture. Not a VEDA. No VEDA modified, reinterpreted, or improved.
**Date:** 2026-08-05
**Governs:** every action, local or AI, performed by Kalpavriksha.
**Constitutional inputs:** VEDA 01–04 (frozen) · KALPAVRIKSHA_VISION_V2 §§2.5, 4, 5.1, 5.2, 5.7, 10, 12, 15 · ADR-0005, 0011, 0017, 0019.
**Excluded:** VEDA 05 (under amendment). Nothing here depends on it.
**Redesigns nothing:** Objective Engine, Broker, Permission System, Learning, Receipts, and both execution pipelines are governed, not altered.

---

## 0 · One correction to the prior report

The Constitutional Execution Path Report marked the Intelligence pipeline's authorization as satisfied by a *parallel* mechanism. Closer reading of [`ai_infrastructure/approval.py`](src/master_agent/ai_infrastructure/approval.py) shows that is not so: ADR-0017 Decision 7 already routes Broker selections into **the same Permission System and the same MB028.1 Approval Queue** — *"The Broker implements no approval machinery."*

**The two pipelines are already converged on authorization.** What diverges is the record: `ai_infrastructure/ledger.py` and the execution logs are separate stores, and nothing *requires* either pipeline to have consulted anything.

This makes the Kernel's job smaller and its design cleaner. It formalizes a discipline the Broker already volunteers, rather than imposing a new one.

---

## 1 · Executive Summary

### 1.1 The design question, and its answer

Everything about this specification follows from one decision:

> **Does the Kernel *perform* constitutional checks, or *require* them?**

If it performs them, it must contain a permission evaluator, a budget deriver, an admission controller, a rule engine, and a classifier. It becomes the largest component in the system, duplicates five things that already exist and work, and violates the instruction not to redesign any of them. It would also be wrong on its own terms: a kernel that reimplements what it governs is not a kernel, it is a monolith with a nice name.

**It requires them.**

> **The Constitutional Kernel performs three checks that belong to no one else, requires signed attestations from the components that own the other eight, and is the sole issuer of the token without which nothing can execute.**

This is the operating-system analogy done properly. A kernel does not implement ext4, TCP, or a GPU driver. It defines the contract each must satisfy and holds the one thing they cannot forge: **the file descriptor.** Its authority comes not from doing the work but from being the only source of the handle.

Kalpavriksha's file descriptor is the **Intent**.

### 1.2 What the Kernel is

```
   The Kernel is a gate that mints tokens, not a pipeline that moves work.
   It is called. It never calls execution.
   It knows capability names, classes, and digests.
   It has never heard of a file, a socket, a browser, or a robot arm.
```

Roughly 400 lines of logic that will not change in fifteen years, because everything it does is definitional rather than technological.

### 1.3 The five structural properties

**One · Sole minting authority.** Only the Kernel produces an `intent_id`. `LocalExecutor.run()` and the provider execution call require one. There is no default, no `Optional`, no test-only constructor. **Bypass is a type error, not a policy violation.**

**Two · Attestation, not reimplementation.** The Permission System still decides permission. The Broker still decides providers, budgets, and admission. The Kernel decides only whether every required attestation is present, current, and from the right attestor. It never second-guesses a verdict; it refuses when one is missing.

**Three · Convergence without merger.** Both pipelines call `authorize()` and both call `settle()`. Between those two calls, each executes through its own machinery, unchanged. The pipelines meet at the Kernel and nowhere else.

**Four · One-way learning.** The Kernel publishes to the Event Bus that already exists. Subscribers have **no return channel** — they cannot veto, delay, or modify. Eng. Law V made structural rather than aspirational.

**Five · The Override is a Kernel operation.** Suspending autonomy is precisely: invalidate every unexecuted intent, and refuse to mint. Work continues, queueing continues, **only deciding stops** — VEDA 01 §10's requirement expressed as a single mechanism with a testable meaning.

### 1.4 One genuine VEDA conflict found

VEDA 04 A1 requires the intent record to carry "the consequence quartet." VEDA 04 §9 places A1 in Phase 0 and B1 (the Consequence Engine that produces the quartet) in Phase 1. **A Phase-0 intent record cannot carry a field whose producer does not yet exist.**

This is a small internal sequencing tension, not a design flaw. §14.1 states it and recommends the smallest possible amendment. **No VEDA text is changed by this document.**

---

## 2 · Constitutional Philosophy

### 2.1 Why a kernel and not a framework

A framework is something capabilities are written *inside*. A kernel is something they must go *through*. The difference decides whether governance survives its authors.

A framework's guarantees hold while everyone uses the framework. The first capability written outside it works fine, ships, and creates the precedent. Five years later the framework governs sixty percent of the system and nobody can say which sixty.

**A kernel's guarantees hold because there is no other way to obtain what execution requires.** A developer in 2031 adding the four-thousandth skill will not read this document. They will write an Action, register it, declare its reversibility class, and discover their code does not run because it has no `intent_id` and nowhere to get one except the Kernel. They will comply without ever knowing they were governed.

That is the entire design goal. Everything below is in service of it.

### 2.2 The three constitutional sources, and what each contributes

**VEDA 04 A1 gives the Kernel its shape.** *Intent record → execute → outcome record*, with the invariant that a failed intent write aborts the action. That two-phase structure is not a logging pattern; it is the only arrangement in which "did this happen?" has an answer when the process dies mid-action.

**VEDA 01 §10 gives the Kernel its limits.** Autonomy is lent, never earned permanently. No rule, however broad, grants irreversible authority. One gesture stops all deciding. Each is a Kernel behaviour in §7, §8, and §11 respectively.

**Constitution §5 gives the Kernel its humility.** The Permission System, the Capability Registry, and the Broker are Shared Infrastructure with named owners. The Kernel depends on all three and owns none of them. **A kernel that absorbs its dependencies is how a trust boundary becomes a god object.**

### 2.3 Minimality as a safety property

The Kernel is on the path of every action forever. Every line in it is a line that runs a billion times and that no future engineer may safely modify without understanding the whole constitution.

**Minimality here is not aesthetics. It is the mechanism by which the component stays reviewable by one person.** A 400-line kernel can be read in an afternoon by someone deciding whether a change is safe. A 4,000-line kernel cannot, and will therefore accumulate changes nobody fully evaluated.

Every §7 check that could plausibly be attested rather than performed **is attested**, for this reason alone.

---

## 3 · Kernel Architecture

### 3.1 Purpose

> To be the single point at which the constitution is enforced, so that constitutional compliance is a property of the system's structure rather than of anyone's diligence.

### 3.2 Responsibilities — the complete list

1. Validate that an execution request is constitutionally admissible.
2. Collect and verify the attestations required for that request's class.
3. Perform the three checks that belong to no other component (§7.2).
4. Write the receipt intent, and refuse if that write fails.
5. Mint the Intent — the sole token permitting execution.
6. Accept outcome reports and write the outcome record.
7. Publish Kernel events, one-way, to subscribers who cannot answer back.
8. Enforce intent expiry, cancellation, and Override invalidation.

Eight responsibilities. Nothing else belongs here, and the test for any proposed ninth is §3.4.

### 3.3 What the Kernel owns

| Owns | Meaning |
|---|---|
| **The Intent** | Its structure, issuance, lifecycle, expiry, and invalidation. The only minting authority in the system. |
| **The attestation contract** | Which attestations each action class requires, and what a valid one looks like. Not the attestations' content. |
| **The precondition set** | The ordered list of checks in §7, and the refusal semantics when one fails. |
| **The receipt-write obligation** | That an intent record precedes every effect. **Not the ledger** — A1 owns storage; the Kernel owns the obligation. |
| **The Override switch** | Suspension state, and the invalidation of outstanding intents. |
| **Kernel event emission** | What is published, when. Not the bus, which already exists. |

### 3.4 What the Kernel explicitly does NOT own

**This list is longer than the previous one, deliberately.** Each entry names the real owner, so a future change proposing to move it into the Kernel can be answered by citation rather than by argument.

| Does not own | Real owner |
|---|---|
| Whether permission is granted | Permission System (Constitution §5.2) |
| Which provider serves a request | AI Capability Broker (§5.7) — *"No other component may decide"* |
| Budgets, deadlines, admission, occupancy | Broker's `budgets.py`, `admission.py`, `occupancy.py` (MB038) |
| What an objective is, or how it decomposes | Objective Engine |
| Task dependency order and assignment | Mission Control — which *cannot* perform work, and must stay that way |
| How a capability resolves to a Worker | Capability Registry (§5.1) |
| The execution itself | Worker Runtime, Actions, Providers |
| Verification and Evidence | Verification Subsystem (ADR-0011) |
| Receipt **storage** | A1 Receipt Ledger |
| What is learned, and from what | The learning loops |
| Rule definition and cumulative accounting | Standing Rule Engine (VEDA 04 C1) |
| Narration, ranking, the founder surface | D1, B2, VEDA 03 |
| Retry *mechanics* | The Runtime. The Kernel authorizes an attempt budget; it does not loop. |

**The test for any proposed Kernel responsibility:** *does another component already own this question, and would the Kernel have to reimplement or second-guess its answer?* If yes, it is an attestation, not a Kernel responsibility.

### 3.5 The Kernel's surface

Four operations. The smallness is the point.

```
  authorize(ExecutionRequest) → Intent | Refusal
      Perform the three checks. Verify attestations. Write receipt
      intent. Mint. Refuse on any failure, naming which.

  settle(intent_id, Outcome) → Receipt
      Record what happened. Terminal. Publishes. Never mutates the intent.

  attempt(intent_id) → AttemptToken | Refusal
      Open one attempt against a live intent. Refuses when expired,
      cancelled, settled, or out of attempt budget. (§8)

  invalidate(scope, reason) → count
      Cancel outstanding unexecuted intents. The Override's mechanism,
      and the only bulk operation. (§11.8)
```

**There is no `execute()`.** The Kernel is called; it never calls. This one absence is what keeps it independent of execution technology, and is why §6 can promise it survives robots.

### 3.6 Placement

```
                     ┌─────────────────────────────────┐
   BRAIN ───────────►│                                 │
   (Objective Engine,│    CONSTITUTIONAL KERNEL        │
    Planner)         │                                 │
                     │  the only minting authority     │
   SHARED INFRA ────►│                                 │◄──── OPERATOR
   (Permissions,     │  performs 3 checks              │      (Runtime,
    Broker, Registry,│  requires 8 attestations        │       Workers,
    Receipt Ledger)  │  owns 0 subsystems              │       Providers)
                     └─────────────────────────────────┘
```

**Constitutional placement: Shared Infrastructure.** Both the Brain (planning an action) and the Operator (executing one) depend on it; neither depends on the other. Its state — outstanding intents, override status — must be singular across every Operator Instance, for exactly the reason §5.2 gives for the Permission System. It decides and never touches a machine, exactly like the Broker (§5.7).

**Dependency direction is strictly downward.** The Kernel imports no Worker, no Provider, no Environment, and no concrete capability. An architecture test enforces this, in the pattern the codebase already uses.

---

## 4 · Intent Model

### 4.1 What an Intent is

> **A short-lived, immutable, non-transferable capability token authorizing one logical action, issued only by the Kernel, valid only within its window, and consumed by attempts rather than by use.**

It is not a request, a task, a plan step, or a job. Those describe *what should happen*. An Intent is the constitutional record that **it is permitted to happen now**, plus proof of why.

### 4.2 What creates one, and when

**Only `Kernel.authorize()`.** No other constructor exists at any privilege level, including in tests — tests obtain intents from a real Kernel over an in-memory ledger.

**Created at the last possible moment before the first effect**, and specifically:

- **After** the Objective Engine has admitted the objective
- **After** Mission Control has determined the task is ready
- **After** the Broker has decided the provider and derived the budget (intelligence actions)
- **After** the Permission System has been consulted
- **Before** any Worker is resolved to a live object, any socket opens, any byte is written

Late minting is deliberate. An intent minted early is an authorization aging against a world that keeps moving — the same defect VEDA 04 F5 identifies in firing a stale default.

### 4.3 Contents

Immutable. Every field set at mint.

| Field | Purpose | Source |
|---|---|---|
| `intent_id` | The token | Kernel |
| `objective_id` | Constitutional anchor. **No intent exists without one.** | Request |
| `task_ref` | The unit of work this serves | Mission Control |
| `actor` | Principal on whose authority this acts | Principal model |
| `capability` | Qualified name, e.g. `Filesystem.DeleteFolder` | Capability Registry |
| `action_class` | `local` \| `intelligence` — selects the attestation set | Kernel |
| `payload_digest` | Content hash of the payload. **The digest, never the payload** — payloads carry founder data and prompts; the ledger is permanent, and permanence plus sensitive content is a liability, not a feature. | Kernel |
| `target_ref` | What is acted upon (path, URL, provider id), where meaningful | Request |
| `reversibility_class` | `reversible` \| `reversible_until` \| `irreversible` | Reversibility Registry |
| `compensating_action` | How to undo, or explicitly `none` | Reversibility Registry |
| `undo_window` | Present only for `reversible_until` | Reversibility Registry |
| `grant_ref` | The permission satisfying this | Permission System |
| `rule_ref` | The standing rule fired under, or `none` — **opaque to the Kernel** (§2.1 of the prior report: A1 never resolves it) | Rule Engine |
| `expected_effect` | What the world should look like after | Planner |
| `consequence` | The quartet. **See §14.1** — pending until B1 exists | Consequence Engine |
| `attestations[]` | Attestor id, question, verdict, timestamp — one per §7 requirement | Various owners |
| `attempt_budget` | Maximum attempts authorized. Set at mint, never at retry. | Capability class |
| `deadline` | Wall-clock for intelligence actions | Broker `budgets.py` |
| `decision_ref` | The Broker's `DecisionRecord` — intelligence actions only | Broker |
| `issued_at` / `expires_at` | Validity window | Kernel |
| `sequence` | Monotonic, per objective | Kernel |

### 4.4 The eight questions, answered

**Is it immutable?** **Yes, absolutely.** Nothing mutates an Intent, ever, at any privilege level. State changes are *separate append-only records* referencing it: `AttemptRecord`, `OutcomeRecord`, `CompensationRecord`. A mutable intent could be edited after the fact to describe an action other than the one authorized, which would make the entire ledger unfalsifiable and therefore worthless.

**When does it expire?** `expires_at = min(grant validity, budget deadline, class-specific default)`. Class defaults scale with the action's own timescale — seconds for a filesystem write, the Broker's derived deadline for a provider call.

**Why expire at all** — three reasons, each independently sufficient. An intent that never expires is a permission with no end date, which VEDA 04 C2 forbids. Facts move; an intent minted before an approval and used hours later is authorized against a world that no longer exists. And a bounded outstanding set is what keeps the Kernel's memory bounded at 500 concurrent objectives.

**Can retries reuse it?** **Yes — that is the point.** One Intent, N attempts, N attempt records, one outcome record. This is the precise fix for the audited defect where a `ONCE` grant authorized three executions: the grant is consumed once at mint, and the attempt budget — authorized at mint, not assumed by the loop — governs how many attempts that single authorization covers. **Subject to §8's irreversibility rule, which overrides this.**

**Can two executions share one?** **No.** One Intent authorizes one logical action. Two logical actions require two Intents even when identical. §8.2 defines "same action" precisely, because that definition is the entire boundary between a legitimate retry and an unauthorized second execution.

**Can it be cancelled?** **Yes, before its first attempt begins.** Cancellation writes a terminal outcome record of kind `cancelled` — never a deletion, because the ledger has no delete at any privilege level. Cancellation is also the Override's mechanism (§11.8).

**Is it transferable?** **No.** An Intent is bound to its `actor`, `capability`, and `payload_digest`. Presenting it for a different capability or a mutated payload is refused. This is what stops an intent minted for a harmless action being redirected to a harmful one — the digest is checked at `attempt()`, not merely at mint.

**What happens if it is never settled?** **An unsettled expired intent is a first-class defect, never a silently discarded record.** It means the system does not know whether the action occurred, which is worse than knowing it failed. It surfaces as a reconciliation gap (§9.5) and it is the exact condition the Broker's `occupancy.py` already worries about under the name *orphan*.

### 4.5 Lifecycle

```
   authorize() ──► MINTED ──┬──► attempt() ──► ATTEMPTING ──┬──► settle(ok)      ──► SETTLED ✓
                            │         ▲                     │
                            │         └── attempt() ────────┤ (within budget)
                            │                               │
                            │                               └──► settle(failed) ──► SETTLED ✗
                            │
                            ├──► cancel() ──────────────────────────────────────► CANCELLED
                            ├──► invalidate() ── Override ──────────────────────► INVALIDATED
                            └──► expires_at passes ─────────────────────────────► EXPIRED
                                                                                      │
                                        EXPIRED with attempts > 0 and no outcome ─────┴──► ORPHANED
                                        (a defect — surfaced, never swept)
```

All six terminal states are recorded. **None is a deletion.**

---

## 5 · Entry Model

### 5.1 The rule

Both pipelines enter by calling `Kernel.authorize()`. **Neither is modified. Neither is merged into the other.** They converge at one function call and diverge again immediately after.

### 5.2 Convergence

```
   ARM A · CAPABILITY                          ARM B · INTELLIGENCE
   ─────────────────────                       ────────────────────────
   Objective Engine                            Requester (Planner, Worker,
        ↓                                       launcher, any component
   Mission Control ── dependency order          needing intelligence)
        ↓                                            ↓
   Runtime ── picks up assigned task            AI Capability Broker
        ↓                                       ├─ decides Provider
   Capability Registry                          ├─ derives CallBudget
   capability → Worker (§5.1)                   ├─ admission: starved? occupied?
        ↓                                       └─ refusal if unavailable
   Permission System ── grant?                       ↓
        ↓                                       Permission System ── grant?
        │                                       (ADR-0017 Decision 7 — already
        │                                        the same ledger, same queue)
        │                                            ↓
        │        ┌──────────────────────────────────┘
        ▼        ▼
   ╔═══════════════════════════════════════════════════════════════════╗
   ║              Kernel.authorize(ExecutionRequest)                    ║
   ║                                                                    ║
   ║   Arm A supplies:  objective · task · actor · capability ·         ║
   ║                    payload · classification · grant ·             ║
   ║                    expected outcome                               ║
   ║                                                                    ║
   ║   Arm B supplies:  all of the above, PLUS decision_ref ·           ║
   ║                    budget · admission verdict                     ║
   ║                                                                    ║
   ║   The difference is the attestation set (§7.4), not the path.      ║
   ╚════════════════════════════════┬══════════════════════════════════╝
                                    │
                              Intent │ Refusal
              ┌─────────────────────┴─────────────────────┐
              ▼                                           ▼
   ARM A executes its own way                  ARM B executes its own way
   Gateway → Plugin → LocalExecutor            ai_infrastructure/execution
   → Action → Environment                      → provider → transport → network
              │                                           │
              └─────────────────► Kernel.settle() ◄───────┘
```

### 5.3 Why convergence and not merger

**Resolution is genuinely two different questions.** *"Which Worker provides `Filesystem.DeleteFolder`?"* is a registry lookup. *"Which Provider should serve this reasoning request, at what budget, and is it worth calling right now?"* is a ranked decision over cost, capability, privacy, occupancy, and policy. Constitution §5.1 and §5.7 give these to different owners on purpose.

**Merging them would force one component to answer both**, which means either the Broker absorbs capability dispatch or the Registry absorbs provider ranking. Both are redesigns of ratified components, and both are forbidden by this brief.

**Authorization is genuinely one question.** *"Is this permitted, classified, recorded, and traceable to an objective?"* has one right answer regardless of whether the effect is a file or a token. That is the seam, and it is exactly where the Kernel sits.

### 5.4 A third pipeline

Any future pipeline — a mobile agent, a cloud worker, a robot controller — enters the same way. It resolves however it resolves, then calls `authorize()`.

**The standing question, from the prior report, is a Kernel admission requirement:** *what does this pipeline need to do that the Kernel cannot authorize, classify, and receipt?* Every honest answer to date has been "nothing."

---

## 6 · Exit Model

### 6.1 The rule

The Kernel returns an Intent. **The caller executes. The Kernel does not.** Exit is the caller opening an attempt, doing its own work in its own way, and settling.

```
   intent = kernel.authorize(request)      # may refuse
   token  = kernel.attempt(intent.id)      # may refuse: expired, over budget
   result = <<the caller's own execution, entirely its own business>>
   kernel.settle(intent.id, outcome)       # mandatory
```

### 6.2 Why this survives every execution technology

The Kernel's vocabulary is: **capability name · action class · reversibility class · payload digest · target reference.** Five strings and an enum.

It has no concept of a file, a socket, a DOM node, a screen coordinate, a Bluetooth handle, or a joint angle.

| Execution technology | What the Kernel sees | Kernel change |
|---|---|---|
| Filesystem | `Filesystem.DeleteFolder`, irreversible, digest, path | **none** |
| AI provider | `Reasoning.Generate`, reversible, digest, provider id | **none** |
| Browser | `Browser.Click`, reversible, digest, selector | **none** |
| Desktop | `Desktop.KillProcess`, irreversible, digest, pid | **none** |
| Mobile (future) | `Mobile.SendSms`, irreversible, digest, recipient | **none** |
| Cloud (future) | `Cloud.TerminateInstance`, irreversible, digest, instance id | **none** |
| Robotics (future) | `Arm.Grip`, reversible-until, digest, coordinates | **none** |

A new technology supplies a Worker, a manifest, and a reversibility classification. **It does not touch the Kernel.** This is the fifteen-year property, and it is a consequence of the Kernel having no `execute()`.

### 6.3 The settle obligation

**Every minted intent must be settled.** Settlement is mandatory, and its absence is a defect rather than a shrug.

The four settlement kinds:

| Kind | Meaning |
|---|---|
| `succeeded` | The effect occurred as expected |
| `failed` | The effect did not occur, and this is known |
| `partial` | Some effect occurred. **Requires the compensating action reference.** The most dangerous outcome and the one most often modelled as failure — a half-written file is not a file that was not written. |
| `unknown` | The caller cannot determine whether the effect occurred. **Never auto-retried** (§8.4). Escalates. |

`unknown` exists because pretending otherwise is how a system double-charges a card. A caller that times out mid-request genuinely does not know, and the constitutionally honest response is to say so.

### 6.4 Compensation exits through the Kernel too

Undoing is an action. It is classified, authorized, receipted, and minted like any other — with `compensates: intent_id` linking it to what it reverses. **There is no privileged undo path**, because a path that can change the world without a receipt is a hole regardless of its good intentions.

---

## 7 · Constitutional Checks

### 7.1 The ordering principle

Checks run **cheapest-and-most-fundamental first**, so a refusal costs as little as possible and the reason returned is the most fundamental one. An action with no objective is refused for having no objective, never for a budget problem it also had.

### 7.2 Checks the Kernel performs itself — exactly three

Each is a question about the Kernel's own domain. No other component owns it.

**K1 · Objective binding.** `objective_id` present, resolves to an admitted objective in a non-terminal state.
*Refuses:* no objective · unknown objective · objective already completed, failed, or cancelled.
*Why the Kernel:* this is the constitutional anchor. Delegating it to an attestation would make *"no execution without an objective"* attestable-away, and it is the first guarantee in the brief.

**K2 · Override state.** Global suspension is not active.
*Why the Kernel:* the Override's meaning *is* "the Kernel stops minting." No other component can express that.

**K3 · Receipt intent write.** Runs last, after every other check has passed. If the write fails, the Kernel refuses and **nothing executes**.
*Why the Kernel:* VEDA 04 A1 verbatim — *"if the intent write fails, the action does not occur. No exceptions, no buffering, no fire-and-forget."* The Kernel owns the obligation; A1 owns the storage.

### 7.3 Checks the Kernel requires as attestations — eight

The Kernel verifies each attestation's **presence, attestor identity, subject match, and freshness**. It never re-derives the verdict. An attestation whose attestor is wrong, whose subject does not match this request, or which is stale is treated as absent.

| # | Question | Attestor | Refuses when |
|---|---|---|---|
| **A1** | Is this task ready — dependencies satisfied, correctly assigned? | Mission Control | Not dispatched, or dependencies unmet |
| **A2** | What is this action's reversibility class, and how is it undone? | Reversibility Registry | **Unclassified. Fails closed — no default classification exists.** |
| **A3** | Is there a valid grant for this capability at this tier? | Permission System | No grant · `IRREVERSIBLE` without contemporaneous approval |
| **A4** | If firing under a rule: headroom, exclusions, not expired? | Standing Rule Engine (C1, future) | Cumulative cap breached · excluded · rule expired |
| **A5** | Who is acting, and on whose authority? | Principal model | No principal resolved |
| **A6** | Does the payload conform to the capability's input schema? | Capability contract (MB039 schemas) | Schema violation |
| **A7** | *(intelligence only)* Provider, budget, deadline? | Broker — `decision.py`, `budgets.py` | No `DecisionRecord` · no budget |
| **A8** | *(intelligence only)* Should this call be made at all? | Broker — `admission.py`, `occupancy.py` | Starved · occupied |

**On the brief's "blast radius":** that is VEDA 03's own term for a rule's cumulative cap, and it is checked at **A4** by the component that owns cumulative accounting. Putting a second blast-radius calculation in the Kernel would create the divergent-accounting risk VEDA 04 R3 rates high severity.

**On the brief's "dependency satisfied":** checked at **A1** by Mission Control, which already refuses to dispatch a task whose dependencies are unmet. The Kernel requiring the attestation is stronger than the Kernel re-walking the graph, because it cannot disagree with the scheduler.

### 7.4 Attestation sets by action class

| Class | Required |
|---|---|
| `local` | K1 · K2 · A1 · A2 · A3 · A4 · A5 · A6 · K3 |
| `intelligence` | K1 · K2 · A1 · A2 · A3 · A4 · A5 · A6 · **A7 · A8** · K3 |

**The sets differ by two attestations. That is the entire difference between the pipelines inside the Kernel** — which is what "converge, do not merge" means in code.

### 7.5 The refusal contract

A refusal names the check that failed, the attestor, and whether it is remediable.

**Refusals are data, not exceptions** — the shape the Broker's `refusal.py` already established, and for the same stated reason: *"the founder is reading a stack trace from a provider SDK instead of a sentence about their own machine."*

**Refusals are recorded.** A refused action is a decision the system made and must be able to account for. A silently refused action is indistinguishable from one never attempted.

**Refusals are not automatically judgment requests.** Under an active Override, a thousand refusals are one state — *"autonomy is suspended; 1,000 actions are waiting"* — not a thousand queue items. VEDA 03 refuses counts and badges, and a Kernel that emitted one founder-facing item per refusal would manufacture exactly the inbox the product abolishes.

---

## 8 · Retry Model

### 8.1 The defect being fixed

`_execute_with_retry()` loops `gateway.invoke()` up to `max_attempts` times after **one** `_require_approval()`. `PermissionSystem` documents a `ONCE` grant as covering *"exactly the one invocation it was given for."* It does not.

**The root cause is not the loop. It is that there was nothing for the loop to be bounded by.** An attempt budget authorized at mint fixes it structurally: the retry policy becomes something granted rather than something assumed.

### 8.2 What counts as "the same action"

> **Same action ≡ identical `(objective_id, actor, capability, payload_digest, target_ref)`.**

Any difference in any component is a different action requiring a new Intent. The digest is the load-bearing term: a caller that "retries" with a corrected path is not retrying, it is doing something else, and the ledger must say so.

### 8.3 What survives a retry, and what does not

| Survives | Requires a new Intent |
|---|---|
| `intent_id`, grant, classification, attestations | Any payload or target change |
| The consumed permission — **one grant, one intent** | Expiry passing |
| `objective_id`, `actor`, `rule_ref` | Attempt budget exhausted |
| Budget and deadline (intelligence) | Reversibility class changing (world changed) |
| | Grant revoked or rule expired mid-flight |
| | **Any irreversible action — always (§8.4)** |

### 8.4 The irreversibility rule — the most important clause in this section

> **An action classified `irreversible` is never automatically retried. Ever. Regardless of attempt budget, error class, or how transient the failure appears.**

Three independent reasons, each sufficient:

**A failed irreversible action may not have failed.** A timeout on a payment, a message send, or a process kill means the caller does not know. Retrying is potentially doing it twice, and the second one has no compensating action either.

**VEDA 01 §10 Ethics 3 requires *contemporaneous* permission for irreversible action.** A retry three seconds later under a grant consumed three seconds ago is not contemporaneous; it is a second irreversible act under a first act's authority.

**`unknown` is the honest settlement, and it escalates.** The correct response to "I do not know whether I sent that email" is to ask, not to send it again.

So: an irreversible action failing produces `settle(failed)` or `settle(unknown)`, and either **escalates as a judgment request**. A human decides whether to try again, and that decision mints a new Intent under a fresh grant.

### 8.5 Attempt budgets

Set at mint from the capability's class, never by the retry loop:

| Class | Budget | Reasoning |
|---|---|---|
| `read_only` | Liberal | No effect to duplicate |
| `reversible` | Bounded, small (default 3) | A duplicate effect is undoable |
| `reversible_until` | Bounded, and **the undo window is not extended by retrying** | Otherwise a long retry sequence silently consumes the founder's window to change their mind |
| `irreversible` | **1** | §8.4 |

The `reversible_until` clause matters more than it looks: VEDA 03 grades undo windows by who was in the room, and a retry loop that quietly burns a 60-second window before the founder is even told is a loss of authority disguised as robustness.

### 8.6 Idempotency

VEDA 04 §7 requires every action to be idempotent against its intent record. The Kernel provides the key — `(intent_id, attempt_seq)` — and requires Workers to honour it where the underlying operation permits.

**Where it does not permit it, the reversibility class must say so.** A capability that cannot be made idempotent and is not classified irreversible is a misclassification, and §7.3 A2 fails closed on it.

---

## 9 · Receipt Architecture

### 9.1 Four record types, all append-only, none ever mutated

```
   IntentRecord ──┬── AttemptRecord (0..n)
                  ├── OutcomeRecord (0..1, terminal)
                  └── CompensationRecord (0..1, links a compensating intent)
```

### 9.2 The linkage graph

```
   FOUNDER
      │ approved acceptance criteria
      ▼
   OBJECTIVE ─────────────────────────────────► objective_id
      │                                              │
      ├── task ──► INTENT ◄── grant_ref ── PERMISSION SYSTEM
      │              │    ◄── rule_ref ──── RULE ENGINE (opaque to Kernel)
      │              │    ◄── decision_ref ─ BROKER (intelligence only)
      │              │    ◄── class ──────── REVERSIBILITY REGISTRY
      │              │
      │              ├──► ATTEMPT (1..n) ──► the Worker's own execution log
      │              │
      │              ├──► OUTCOME ─────────► evidence_id ──► VERIFICATION
      │              │
      │              └──► COMPENSATION ────► compensating intent_id
      │
      └──► narrated to the founder by D1, one line and a receipt (D6)
```

**Every arrow is an identifier, never a copy.** A receipt holds references; it never duplicates permission state, broker state, or evidence. Duplicated state is state that will eventually disagree.

### 9.3 What the graph answers

Six queries, each previously unanswerable or answerable only across two ledgers:

- *"Everything done under objective X"* → walk `objective_id`
- *"Everything fired under rule Y"* → walk `rule_ref` — this is what makes C5 self-audit and C7 dependency audit possible at all
- *"What did provider Z actually do, and what did it cost"* → walk `decision_ref`
- *"Every irreversible action last quarter, and whether each was individually approved"* → filter class + `grant_ref`
- *"Everything still undoable right now"* → live `reversible_until` intents inside their window
- *"Everything we don't know the outcome of"* → orphans (§9.5)

### 9.4 The AI ledger becomes a projection

`ai_infrastructure/ledger.py` keeps its shape, its consumers, and its cost model. It becomes a **projection keyed on `decision_ref`**, derived from the receipt store rather than written in parallel to it.

**Nothing about the Broker changes.** Its `DecisionRecord`, its byte-identical replay guarantee, and its no-fallback rule are untouched. One store gains a second index; it does not gain a second writer.

### 9.5 Reconciliation

Continuous, per VEDA 04 R3, which requires exactly this for cumulative accounting:

- Every settled intent has an outcome. **Every expired intent with attempts and no outcome is an orphan** — surfaced, never swept.
- Every AI-ledger entry has an intent; every intelligence intent has an AI-ledger entry.
- Every consumed grant has an intent; every intent has a grant or an explicit `read_only` marker.

**An orphan is the single most important signal the Kernel produces.** It means the system does not know whether it changed the world. Everything else is a known state.

---

## 10 · Learning Integration

### 10.1 Reading the brief's principle against Eng. Law V

The brief requires *"no execution without learning."* VEDA 04 Eng. Law V requires that inference generates proposals and only permission generates actions, and VEDA 04 §5 states plainly that **memory never acts**.

If "no execution without learning" meant learning gates execution, a component forbidden from acting would sit on the critical path of every action, and a learning outage would stop the system.

**The reading this specification adopts:**

> **No execution escapes being learnable. Every action, without exception, enters the receipt stream that learning consumes. Learning is guaranteed *complete coverage*, never *veto*.**

That satisfies the brief's intent — nothing happens invisibly to learning — while preserving Eng. Law V exactly. It is stated here rather than assumed, so a future reader knows it was a decision.

### 10.2 The mechanism

**Use the Event Bus that already exists.** `mission_control/events.py` is documented as *the only reporting shape in the system* — *"An Executive that needs to say something says it as an Event... or it isn't heard."* Building a second bus for Kernel events would create precisely the parallel-mechanism problem this Kernel exists to end.

New event types, following the existing schema:

`INTENT_MINTED` · `INTENT_REFUSED` · `ATTEMPT_STARTED` · `ATTEMPT_FAILED` · `INTENT_SETTLED` · `INTENT_EXPIRED` · `INTENT_ORPHANED` · `INTENT_INVALIDATED` · `COMPENSATION_APPLIED`

### 10.3 The four invariants that make learning safe

**Publication is after the durable write, never before.** An event describing an action whose receipt failed would teach the system about something that did not happen.

**Subscribers have no return channel.** The subscription signature returns nothing. There is no veto, no delay, no modification, no "learning says wait." Eng. Law V is enforced by the shape of the callback rather than by a rule someone must remember.

**Subscriber failure is isolated and invisible to execution.** A subscriber that raises is logged and skipped. The Kernel never learns whether anyone listened.

**No subscriber is required.** Zero subscribers is a valid, fully functional configuration. This is how "learning unavailable" is a non-event (§11.4).

### 10.4 The three loops, and the boundary between them

| Loop | Learns from | Owner | May enact? |
|---|---|---|---|
| **Provider performance** | `INTENT_SETTLED` on intelligence actions | Broker `learning.py` (ADR-0018, ratified) | Yes — within its ratified decision authority |
| **Execution reliability** | `ATTEMPT_FAILED`, orphan rate, retry patterns | Runtime policy | Yes — retry tuning only, never authority |
| **Boundary** | Founder decisions, refusals, escalations | Rule Proposal Miner (VEDA 04 C3) | **Never.** Proposes only. |

**The invariant that holds for fifteen years:** the first two loops make the system better at what it is *already permitted* to do. Only the third touches what it is *permitted* to do, and it cannot enact.

> **No component may convert competence into authority. That conversion is a founder act, always, one rule at a time, each with a cumulative cap and an expiry date.**

---

## 11 · Failure Behaviour

Eight conditions. Each states the mode and the reasoning, because a failure policy without reasoning gets "optimized" by someone under deadline pressure.

### 11.1 Permission System unavailable → **FAIL CLOSED**

Cannot verify authority ⇒ no authority. No cache, no grace period, no "it was granted a minute ago."

A permission cache is an authority that outlives its source, which is the same defect as a grant without an expiry. `PermissionSystemGate` already fails closed on an unresolvable risk tier ([approval.py:143](src/master_agent/runtime/approval.py:143)); the Kernel extends the same posture to the system being unreachable.

### 11.2 Objective missing → **FAIL CLOSED**

Refuse at K1, before anything else runs. Not delayed, not queued: an action with no objective is not a delayed action, it is an unauthorized one, and queueing it implies it might later become legitimate without anything changing.

### 11.3 Receipt Ledger unavailable → **FAIL CLOSED**

VEDA 04 A1, verbatim: *"if the intent write fails, the action does not occur. No exceptions, no buffering, no fire-and-forget."*

**"No buffering" forecloses the tempting mitigation.** An in-memory queue of pending receipts "until the ledger recovers" is exactly the fire-and-forget A1 forbids, and it fails precisely when it matters — a crash loses the queue and the actions already happened.

**Consequence, stated plainly:** the ledger is a hard dependency of all execution. Local-first (Constitution §2.5) therefore requires a **local** ledger. A remote-only ledger would make the product non-functional offline and would contradict a frozen principle.

### 11.4 Learning unavailable → **PROCEED, UNAFFECTED**

Execution does not know or care. Zero subscribers is a valid configuration (§10.3). This is the only "proceed" in this section, and it is the direct consequence of §10.1's reading.

### 11.5 Tool / Worker unavailable → **FAIL CLOSED, BEFORE MINTING**

Refused at A1/A6 attestation, before an intent exists. Minting first and discovering the Worker is missing afterwards produces an intent that can only ever be settled `failed` — a real authorization for an impossible action, which pollutes the ledger and the learning stream.

### 11.6 Provider unavailable → **REFUSE, per the Broker's existing model**

The Broker already returns a structured `BrokerRefusal` and explicitly never falls back, because a substituted provider would make the `DecisionRecord` a lie. **The Kernel does not override this and does not add a second opinion.** No `DecisionRecord` ⇒ A7 attestation absent ⇒ refuse. The refusal is recorded and, if it blocks an objective, escalates.

### 11.7 Network unavailable → **DEGRADED, by policy that already exists**

Constitution §2.5: fully functional offline against a local Reasoning Provider. §3.3: offline ⇒ local providers only.

**The Kernel decides nothing here.** Offline routing is the Broker's; a local action is unaffected. The Kernel's contribution is that an offline refusal is *recorded and named* — the founder learns which capability is unavailable and why, rather than reading a connection error.

### 11.8 Override active → **FAIL CLOSED ON MINTING; EVERYTHING ELSE CONTINUES**

The precise mechanism, and the reason the Override belongs in the Kernel:

```
   invalidate(scope=all, reason="founder override")
      1. Set suspension. K2 now refuses every mint.        ← milliseconds
      2. Invalidate every MINTED intent not yet attempted.
      3. Intents already ATTEMPTING run to settlement —
         an in-flight write cannot be un-written.
      4. Objective Engine keeps admitting. Mission Control
         keeps assigning. Work queues at the Kernel boundary.
```

VEDA 01 §10: *"Kalpavriksha continues working and continues queueing — it simply stops deciding."* Step 4 is that sentence in code.

VEDA 04 A3 requires suspension of *in-flight evaluations* — step 2 — and does not require aborting in-flight *executions*, which is fortunate, because step 3 is a physical limit rather than a design choice. A half-written file cannot be recalled by a switch. **Naming that limit is more honest than a specification that implies otherwise.**

**No confirmation, no persuasion, no friction.** `invalidate()` has no confirmation parameter in its signature, matching VEDA 04's requirement that none exist.

### 11.9 The Kernel itself unavailable → **NOTHING EXECUTES**

Stated rather than mitigated. The Kernel is a single point of failure by design.

> **A system that can still act when its trust authority is down does not have a trust authority. It has a suggestion.**

The mitigations are the ordinary ones for a critical local component — small surface, no network dependency, no external calls, heavily tested, minimal logic. §14 R1 treats it as the risk it is.

### 11.10 Summary

| Condition | Mode |
|---|---|
| Permission System unavailable | **Fail closed** |
| Objective missing | **Fail closed** |
| Receipt Ledger unavailable | **Fail closed** — no buffering |
| Tool / Worker unavailable | **Fail closed**, pre-mint |
| Provider unavailable | **Refuse**, per Broker |
| Override active | **Fail closed on minting**; queueing continues |
| Kernel unavailable | **Nothing executes** |
| Network unavailable | **Degraded** — local-first, already constitutional |
| Learning unavailable | **Proceed** — the only one |

**Eight fail-closed, one proceed.** The one that proceeds is the one forbidden from acting.

---

## 12 · Guarantees

After the Kernel ships and `intent_id` is mandatory:

### 12.1 It is impossible for any capability to execute without…

1. …**an objective** — K1 refuses, and there is no execution path that does not begin at `authorize()`
2. …**a resolved reversibility classification** — A2 fails closed; no default exists
3. …**a valid permission grant above `READ_ONLY`** — A3
4. …**contemporaneous founder approval, if irreversible** — A3; no standing rule ever satisfies it
5. …**a receipt intent written first** — K3; failure aborts the action
6. …**an identified principal** — A5
7. …**a payload conforming to the declared schema** — A6
8. …**cumulative-cap headroom, if firing under a rule** — A4
9. …**a Broker decision and budget, if it needs intelligence** — A7
10. …**passing admission, if it needs intelligence** — A8
11. …**entering the receipt stream learning consumes** — publication follows every settlement
12. …**a live, unexpired, uninvalidated Intent** — `attempt()` refuses otherwise
13. …**the founder's authority not being suspended** — K2

### 12.2 It is impossible to…

14. …**execute more times than authorized** — attempt budget set at mint, not by the loop
15. …**automatically retry an irreversible action** — §8.4, unconditional
16. …**reuse an Intent for a different action** — digest, capability, and actor bound at mint and checked at attempt
17. …**mutate or delete a receipt** — append-only at every privilege level
18. …**convert competence into authority** — only C3 touches the line, and C3 cannot enact
19. …**have an action invisible to audit** — one store, both pipelines, reconciled continuously
20. …**silently lose an action's outcome** — orphans surface as defects

### 12.3 The guarantee about the guarantees

21. **A future capability inherits all twenty automatically, by writing an Action and obtaining an `intent_id`.** There is nothing to remember, no base class to extend correctly, and no review checklist to follow. The guarantees are inherited because the alternative does not compile.

---

## 13 · Scalability

### 13.1 The honest position

**The Kernel is on the path of every action. It is the hottest path in the system.** Claiming otherwise would repeat the error of declaring a component bottleneck-free while making it universal.

It survives because it does almost nothing.

| Work | Cost |
|---|---|
| K1 objective lookup | O(1) local |
| K2 override check | O(1), a boolean |
| 6–8 attestation validations | O(1) each — presence, attestor identity, subject match, freshness. **No verdict is recomputed.** |
| Digest computation | O(payload), typically microseconds |
| K3 receipt intent write | **Durable append — the floor of every action's latency** |
| Mint + publish | O(1) + async |

**Every expensive decision happens in its owner, before the Kernel is called, exactly as it does today.** The Kernel adds one durable append and a handful of field comparisons. No new expensive work is introduced anywhere.

### 13.2 The one real cost

The durable append is on the critical path of every action, and A1 forbids buffering it away. VEDA 04 §7 names this: *"Slow ledger = slow product, everywhere."*

**This is a storage engineering problem with a known shape** — append-only, sequential, local, single-writer per objective — and it must be measured from the first vertical-slice run rather than discovered. It is not an architecture problem, and it must never be solved by making the write optional.

### 13.3 At the stated scale

| Dimension | Effect on the Kernel |
|---|---|
| **1,000+ skills** | **None.** The Kernel holds no capability list. A skill is a string with a class. 1,000 costs exactly what 30 costs. |
| **500 concurrent objectives** | Bounded. State is the outstanding-intent set, kept small by expiry. Ledger writes partition cleanly by `objective_id`. |
| **Local + cloud AI** | **None.** Both are `action_class: intelligence` with the same two extra attestations. The Broker absorbs the difference, as designed. |
| **Hundreds of providers** | **None.** The Kernel never enumerates providers; it holds an opaque `decision_ref`. |
| **Multiple devices** | Partition key is `objective_id`. A device may mint only for objectives whose ledger segment it can append to. |
| **Multi-agent** | A remote agent receives Intents or does not execute. **Minting authority is never federated.** |

### 13.4 Multi-device partition — and why it fails closed here

Minting requires a successful durable append. Under partition, a device that cannot append **cannot mint**, and therefore cannot execute.

This is genuinely fail-closed rather than nominally so: it is not a check that could be skipped but a write that cannot succeed. The failure mode is *unavailability*, not *unauthorized action* — and for a trust authority, that is the correct trade. The Kernel does not have the class of bug where a stale local view lets something proceed, because there is no local view to be stale.

### 13.5 Why sharding does not break it

Cross-objective ordering is never required — the ledger needs a total order **per objective**, not globally. Two objectives are causally independent by construction, because the Objective Engine admits them independently.

**This is the property that makes horizontal scaling possible without redesign**, and it holds because objectives are the unit of admission. If a future change made objectives share mutable state, this property would be lost — which is itself a reason not to make that change.

### 13.6 The fifteen-year test

| Change | Kernel change |
|---|---|
| New execution technology (mobile, cloud, robotics) | **None** — §6.2 |
| New provider, new model, new AI vendor | **None** — opaque `decision_ref` |
| 30 → 4,000 capabilities | **None** — holds no list |
| Departments, or any new organizational layer | **None** — it sees objectives and capabilities |
| New rule types, new approval UX | **None** — attestation, not implementation |
| Storage engine replacement | **None** — A1 owns storage |
| A second founder, delegation | **A5's principal set widens.** The only anticipated change, and it is a data change. |

**One anticipated change in fifteen years, and it is additive.** That is the design target, and it is a consequence of the Kernel owning definitions rather than technologies.

---

## 14 · Risks

### 14.1 The VEDA conflict found — and the smallest amendment

**Conflict.** VEDA 04 A1 states the intent record carries *"actor, rule (if any), reversibility class, expected effect, and the consequence quartet."* VEDA 04 §9 places A1 in **Phase 0** and B1, the Consequence Engine that produces the quartet, in **Phase 1**.

A Phase-0 intent record therefore cannot carry a required field. Building A1 without the quartet violates A1's field list; deferring A1 to Phase 1 violates §9's gate that *no execution path can reach a tool without a receipt intent* before anything autonomous ships.

**This is internal to VEDA 04 and small. No VEDA text is changed by this document.**

**Recommended smallest amendment** — one sentence added to A1, changing no other clause, no gate, and no phase:

> *"The consequence quartet is required on every intent record from the moment B1 exists. Until then the field carries the explicit marker `pending_consequence_engine` — never null, never omitted, and never a partial quartet."*

**Why this is the smallest:** it preserves A1's Phase-0 position, preserves B1's Phase-1 position, preserves both gates, changes no invariant, and makes the temporary gap **explicit and greppable** rather than an absence someone later mistakes for an oversight. It also honours B1's own invariant that a partial quartet is never constructed — a marker is not a partial.

**Related tension, not a conflict.** The brief's *"no execution without learning"* would contradict Eng. Law V if read as a gate. §10.1 states the reading adopted — complete coverage, never veto — and no amendment is needed.

### 14.2 The other risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| **R1** | **The Kernel is a single point of failure.** By design (§11.9), but the consequence is total. | **Critical** | Minimal surface, no network, no external calls, no I/O beyond one append. Its test suite is the most valuable in the codebase and should be treated that way. |
| **R2** | **`intent_id` acquires a default "for testing."** The single most likely cause of this specification being obsolete in three years. | **Critical** | No default at any privilege level. Tests obtain intents from a real Kernel over an in-memory ledger. **A test-only bypass is a production bypass with a comment on it.** |
| **R3** | **Attestation becomes a rubber stamp.** If validation degrades to "a field is present," the Kernel becomes ceremony. | **High** | Validate attestor identity, subject match, and freshness — not merely presence. A mismatched or stale attestation is treated as absent, never as a warning. |
| **R4** | **The receipt write becomes the latency floor and someone makes it async.** The most reasonable-sounding fatal change available. | **High** | A1's "no buffering" is quoted in the code at the write site. Measure from the first slice; if it cannot meet budget, that is a storage decision. **Never a correctness one.** |
| **R5** | **Attestation forgery.** A compromised component could attest falsely; the Kernel verifies the attestor, not the reasoning. | **High** | Outside the current threat model — a compromised Permission System is already fatal regardless of the Kernel. **Named so it is a known limit rather than an assumed guarantee.** Signed attestations become worthwhile the moment any component is remote. |
| **R6** | **Intent expiry mistuned.** Too short: spurious refusals mid-approval. Too long: authorization outlives its facts. | Medium | Derive from the action's own timescale, never a global constant. A global timeout is the defect MB038 already removed one layer up; do not reintroduce it here. |
| **R7** | **Orphans are treated as noise.** They will be rare, look like flakes, and be the first thing suppressed. | Medium | An orphan is the only signal meaning *we do not know whether we changed the world*. It surfaces to the founder as an unknown, not as an error, and it is never rate-limited. |
| **R8** | **A fourth pipeline arrives with a reason to bypass.** | Medium | §5.4's standing question, answered in writing, in the ADR that would create it. |
| **R9** | **The Kernel accretes.** Every §3.4 exclusion will eventually be proposed as an inclusion by someone with a good local reason. | Medium | §3.4's test cited in review. A line-count budget is crude but works: **if the Kernel exceeds roughly 600 lines, something in it belongs somewhere else.** |
| **R10** | **The A4 attestation has no attestor until C1 ships.** | Medium | Until the Standing Rule Engine exists, A4 is attested by the Permission System as `no_rule_fired`. **Explicitly attested, never skipped** — the same discipline as §14.1's marker, and for the same reason. |

---

## 15 · Final Recommendation

### 15.1 Adopt

The Constitutional Kernel as specified: **three checks performed, eight attested, four operations, one minting authority, zero subsystems owned.**

Nothing in this specification redesigns the Objective Engine, the Broker, the Permission System, Learning, Receipts, or either execution pipeline. Every one of them is governed by a component that depends on it and reimplements none of it.

### 15.2 The three decisions that must not be revisited

**One · Attestation, not reimplementation.** The moment the Kernel computes a permission verdict, derives a budget, or re-walks a dependency graph, it acquires a second opinion about a question that already has an owner — and two opinions about authorization is the failure the entire Trust Spine exists to prevent. It is also how a 400-line kernel becomes a 4,000-line one that no single person can safely review.

**Two · Minting authority is never federated.** Not to a department, not to a remote agent, not to a second Kernel instance, not for performance. A federated participant receives Intents or does not execute. **The single sentence that keeps this true in 2040 is that there is exactly one place an `intent_id` comes from.**

**Three · Convergence, never merger.** The two pipelines answer different resolution questions and both answers are correct. They meet at authorization because authorization has one right answer regardless of whether the effect is a file or a token. Merging them would redesign ratified components and would make the Kernel technology-aware, which is precisely what §6.2's fifteen-year property depends on it not being.

### 15.3 Build order

The Kernel cannot ship before A1 and A2, and should ship with them:

1. **Foundation** — Clock, Principal, Timers, the unified execution path, the reversibility classification audit at ~30 capabilities
2. **A2 Reversibility Registry** — fails closed. The Kernel's A2 attestation has no attestor without it.
3. **A1 Receipt Ledger** — the Kernel's K3 has nothing to write to without it
4. **The Kernel** — three checks, six attestations initially (A4 stubbed per R10, A7/A8 as the Broker already provides them)
5. **`intent_id` mandatory** — the door closes behind us
6. **A4's real attestor** when C1 ships; the quartet field when B1 ships

Steps 4 and 5 are deliberately separate. Between them, the Kernel is live and every path already supplies an intent id — and step 5 is what proves it.

### 15.4 What this is, in one sentence

> **The Constitutional Kernel is the answer to "how do you make a constitution enforceable by a machine": you do not write more rules, you make the one thing every action needs obtainable from exactly one place, and you put the rules there.**

### 15.5 The test that matters

In 2038, someone will add the six-thousandth capability to Kalpavriksha. They will not have read this document. They will not know what a VEDA is. They will write an Action, register a manifest, declare a reversibility class, and find that their code does not run.

They will look for what is missing, discover it needs an `intent_id`, find there is exactly one place to get one, and call it.

**In that moment they will have complied with every clause of a constitution they have never read — not because they were careful, but because there was no other way to make their code work.**

That is the only form of governance that outlives the people who wrote it, and it is the entire purpose of this specification.

---

*Implementation architecture specification. No VEDA created, modified, or reinterpreted. One genuine conflict internal to VEDA 04 is documented in §14.1 with the smallest possible amendment recommended; the amendment is not applied here. All claims about current system behaviour verified directly against `src/master_agent/` as of 2026-08-05.*
