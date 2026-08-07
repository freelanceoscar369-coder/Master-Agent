# ADR-0023: The five remaining Kernel minting decisions

Status: Proposed (2026-08-06) — resolves every open specification gap between C15 Part 4 and a working mint.
Amends ADR-0021 D5 (second amendment, §7). Builds on ADR-0022.

## Context

C15's precondition path is complete: K1, K2 and §7.3's eight attestations are implemented and 188 tests pass. **K3 and the mint are blocked**, and five distinct gaps stand between here and a warrant.

| # | Gap | Recorded as |
|---|---|---|
| 1 | Kernel Spec §7.2 and Objective Engine Spec §10 disagree on the liveness gate | `CONFLICT_C15_PART2.md` |
| 2 | `IntentRecord.expected_effect` has no source | R35, predicted as R-A in `AUDIT_C9_CLAUDE.md` |
| 3 | §8.5 does not quantify `attempt_budget` for two classes | O1 |
| 4 | §4.4's `expires_at` formula has unreachable terms | O2 |
| 5 | The A2 attestation does not bind to the carried `reversibility_class` | R34, ADR-0022 §5.1 |

This ADR resolves all five, and §6 confirms they compose without circularity.

---

## Decision 1 · The liveness gate belongs to A1, not to K1 and not to the mint

### The contradiction

| Document | Says |
|---|---|
| **Kernel Spec §7.2 K1** | Refuses on *"no objective · unknown objective · objective already completed, failed, or cancelled"* — terminal only |
| **Objective Engine Spec §10.2/§10.3** | *"K1 keeps refusing while the objective is not `EXECUTING`"* · *"Non-`EXECUTING` ⇒ no mints"* |

The Founder Decision of 2026-08-06 removed the check from K1. It did **not** say where it goes, and ADR-0021 D5 as amended assigned it to *"the mint path"*. That relocation does not work:

**C8's `RefusalReason` has no member for "alive but not executing."** Its three objective reasons are `OBJECTIVE_MISSING`, `OBJECTIVE_UNKNOWN`, `OBJECTIVE_TERMINAL`. A `READY` objective is none of them. Putting the gate in the mint moves the vocabulary problem; it does not solve it. C8 is frozen at `c8.0` and this ADR does not reopen it.

### The decision

**§7.3 A1 already answers the question, and the component that owns dispatch owns it.**

> | **A1** | Is this task ready — dependencies satisfied, correctly assigned? | **Mission Control** | Refuses when: **Not dispatched, or dependencies unmet** |

An objective in `WAITING` is, by §8.2's definition, waiting on a judgment, a time, a dependency or a resource. A task under it is **not dispatched or has unmet dependencies**, so **A1 refuses** — with `ATTESTATION_REFUSED`, a reason C8 already has, from the attestor §7.3 already assigns.

An objective in `READY` has not started; no task is dispatched; A1 refuses on the same ground.

**§3.4's test settles it:** *"does another component already own this question, and would the Kernel have to reimplement or second-guess its answer?"* Mission Control owns dispatch readiness. A Kernel enforcing `EXECUTING` itself would be second-guessing Mission Control — the reimplementation §1.2 exists to prevent.

### What this yields

| | |
|---|---|
| **Contradiction removed** | Objective Engine Spec §10's requirement is *satisfied*, by A1 rather than by K1. Neither document is falsified |
| **No new `RefusalReason`** | C8 stays frozen |
| **No new Kernel check** | The mint gains nothing; §14 R9's budget is untouched |
| **K1 unchanged** | Structural admission only, exactly as the founder decided |

### Residual — R36

If Mission Control attests A1 `SATISFIED` for a task under a `WAITING` objective, the Kernel mints. The two components' views can disagree and the Kernel will not catch it.

**Accepted.** This is the same trust every one of the eight attestations rests on, and §7.3's design accepts it by construction: *"The Kernel requiring the attestation is stronger than the Kernel re-walking the graph, because it cannot disagree with the scheduler."* The alternative — the Kernel policing the Engine's state — is the coupling §3.4 forbids.

---

## Decision 2 · `expected_effect` travels in the `ExecutionRequest`

### The options, against the four criteria

| Source | Single truth | No duplication | Minimal coupling | Future-compatible |
|---|---|---|---|---|
| **`ExecutionRequest`** | ✅ the Step's Expected Outcome, carried | ✅ | ✅ no new dependency | ✅ |
| `AdmissionRecord` | ❌ wrong granularity — objective-level, but the effect is per-action | ❌ every action under one objective would share one effect | ✅ | ❌ |
| A Planner port on the Kernel | ✅ | ✅ | ❌ **rejected by ADR-0022's founder rationale** — no lookups beyond `AdmissionProvider`. Also §3.4: the Kernel does not own decomposition | ✅ |
| A new Foundation type | — | — | ❌ a type for one string | — |

### The decision

**`ExecutionRequest` gains `expected_effect: str`, required.**

The single source of truth is unchanged and is where §4.3 already puts it: **the Planner**, via Constitution §17's `Step` — *"One DAG node of a `MissionPlan`, naming a Capability and an **Expected Outcome**."* The Runtime executing that Step already holds it and carries it, exactly as ADR-0022 has it carry `reversibility_class`. The Kernel is a recipient, never a deriver.

**No duplication:** the string exists once, on the Step, and is copied into the permanent `IntentRecord` at K3 — which is a *record*, not a second source.

**Future compatibility:** ADR-0011's Verification Subsystem compares an Observation against the Expected Outcome, and §9.2's graph routes `OUTCOME ──► evidence_id ──► VERIFICATION`. The same string flows to both without a second path.

### Consequence

**C9.1 carries two new fields, not one** — `reversibility_class` (ADR-0022) and `expected_effect` (here). They ship in one reopening, one commit, one tag. §8 records the merged impact.

---

## Decision 3 · `attempt_budget` for `read_only` and `reversible_until`

§8.5 quantifies two of four: `irreversible` = **1**, `reversible` = **3**. The others read *"Liberal"* and *"Bounded."*

### `reversible_until` = **2** — derived, not chosen

Two constraints from §8.5 itself, and together they leave exactly one integer.

**Strictly greater than 1.** The effect *is* undoable, so it is not `irreversible`. A budget of 1 would collapse the two classes and erase the distinction VEDA 04 A2 requires.

**Strictly less than 3.** §8.5: *"the undo window is not extended by retrying — otherwise a long retry sequence silently consumes the founder's window to change their mind."* Every attempt burns the founder's window, so this class must retry **less** than a plain `reversible` action, never the same or more.

```
    1 < reversible_until < 3   ⇒   reversible_until = 2
```

The value is forced. Nothing here is a preference.

### `read_only` = **5** — bounded, and the least tightly derived of the four

**Bounded at all**, because *"liberal"* is not *"unlimited"*: an unbounded budget is a permission with no end, which VEDA 04 C2 forbids and §4.4's expiry reasoning rejects. §13's bounded outstanding set depends on it too.

**Greater than 3**, because §8.5 orders it above `reversible` — there is no effect to duplicate, so the only exposure is time and, for an intelligence read, spend. The bound protects resources, not consequence.

**5 rather than 4 or 6.** Four is indistinguishable from three in practice and buys nothing. Six is two times the reversible budget and reads as a number nobody thought about. Five gives one full extra round of transient-failure headroom — a lock, a slow disk, a blipped connection — while capping a runaway read at five times the cost of one.

> **Stated plainly: this is the only one of the four values not forced by the specification.** It is recorded as the value most open to revision once real read-failure rates exist.

### The four, complete

| Class | Budget | Basis |
|---|---|---|
| `read_only` | **5** | Bounded; above `reversible`; resource protection only |
| `reversible` | **3** | §8.5, verbatim |
| `reversible_until` | **2** | Forced: `1 < x < 3` |
| `irreversible` | **1** | §8.5, verbatim, and §8.4 |

---

## Decision 4 · The `expires_at` algorithm

### The formula, and which terms are reachable

§4.4: `expires_at = min(grant validity, budget deadline, class-specific default)`

| Term | Reachable | Why |
|---|---|---|
| grant validity | ❌ | The A3 attestation carries no `grant_ref` and no expiry |
| budget deadline | ✅ | `AdmissionRecord.deadline` |
| class-specific default | ⚠️ | Defined below |

### The class-specific default is keyed by `ActionClass`

§4.4's own examples are *"seconds for a filesystem write, the Broker's derived deadline for a provider call"* — a **local** action versus an **intelligence** one.

| `ActionClass` | Default | Basis |
|---|---|---|
| `LOCAL` | **30 seconds** | §4.4's *"seconds for a filesystem write."* Thirty is the order of magnitude the specification names, with headroom for a slow disk |
| `INTELLIGENCE` | **300 seconds** | A provider call is not a filesystem write. Measured evidence: the Hermes diagnostic recorded **67–92 s** single-call latency on a free-tier endpoint. Five minutes covers that with margin without becoming an authorization that outlives its world |

### The algorithm

```
    issued_at  = clock.now()
    ceiling    = issued_at + CLASS_DEFAULT[request.action_class]
    expires_at = min(ceiling, admission.deadline)
```

**Deterministic.** Both terms are pure functions of `issued_at`, the request's action class, and the published record. No wall clock is read twice — `issued_at` is taken once and reused, so the two terms cannot drift apart.

### The non-positive window

`Warrant` refuses `expires_at <= issued_at` at construction — *"a warrant that is expired at birth authorizes nothing."* So the algorithm must not produce one.

**It cannot, if C17 keeps one invariant this ADR states:**

> **An objective whose `deadline` has passed must not be published `EXECUTING`.** It has failed a criterion it cannot now meet, and §3.8 makes that `FAILED`.

With that invariant, `admission.deadline > issued_at` whenever K1 passes, and the `min()` is always positive.

**If it is violated**, `Warrant` raises `InvalidWarrant` and the mint fails closed — nothing is minted, and the failure is **not** a `KernelRefusal`, because a Kernel refusal is a decision the Kernel made and records (§7.5), while this is an Engine defect. The same posture as R30's unreachable provider.

### The dropped term

Omitting grant validity narrows a `min()`, which can only **lengthen** the window — the unsafe direction. It is bounded by two real terms, and the residual is recorded as **R37**: when the A3 attestation can carry a grant expiry, it joins the `min()` and the window can only tighten.

---

## Decision 5 · `reversibility_class` becomes part of the A2 attestation's subject — **yes**

### The gap

ADR-0022 R34: a caller can present a genuine, fresh, correctly-attributed A2 attestation together with a **different** class than the Reversibility Registry gave it. The Kernel cannot detect the substitution, because it cannot read the registry.

**Understatement is the dangerous direction.** Claiming `reversible` for an `irreversible` action yields budget 3 instead of 1 and evades §8.4 — *"never automatically retried. Ever."* ADR-0022 D4's ceiling check bounds the class **upward only** and does not touch this.

### The decision

**A2's subject binds the class:**

```
    A2.subject = sha256( payload_digest + "\x1f" + reversibility_class.value )
```

Every other question's subject stays the request's `payload_digest`.

**Deterministic** — a pure function of two strings with an unambiguous separator. `\x1f` (ASCII unit separator) cannot occur in either operand, so no two distinct pairs collide by concatenation.

### Why this, and why the asymmetry is correct

**It reopens nothing frozen.** `ReversibilityRegistry.attest(capability, subject, attested_at)` already takes its subject from the caller, so C12 is unchanged. The Kernel's subject convention is C15's own, set in Part 3, not a frozen contract.

**It closes R34 completely.** The registry computes the subject over the class it actually assigned. A caller carrying a different class produces a subject the Kernel's recomputation will not match, and §7.3 already treats a subject mismatch as **absent** — the existing refusal, no new reason.

**It closes R32 too.** Part 3's residual — that a bare `payload_digest` could transfer between requests sharing a payload — is narrowed for the one attestation whose answer travels outside it.

**The asymmetry is justified, not incidental.** A2 is the **only** attestation whose *value* leaves the attestation and travels separately in the request. The other seven carry their whole answer in the verdict. Binding all eight to a composite would impose a cost on seven attestors to solve a problem only one has.

### Alternative rejected

Widening `Attestation` to carry the classification would be the most faithful to *"attestation, not reimplementation"* — the owner's answer travelling under the owner's signature. **Rejected**: it modifies C7, on which C9, C12 and the Kernel all depend, for a result the subject binding achieves with no frozen change.

---

## Decision 6 · The five together

### 6.1 No circular dependencies

```
   D1  liveness → A1                    depends on: nothing new
   D2  expected_effect → request        depends on: C9.1
   D3  budget values                    depends on: reversibility_class (C9.1)
   D4  expires_at                       depends on: ActionClass, AdmissionRecord.deadline, issued_at
   D5  A2 subject binding               depends on: reversibility_class (C9.1)
```

**One shared prerequisite — C9.1 — and it depends on none of the five.** D4 is keyed by `ActionClass`, not by `ReversibilityClass`, so it does not wait on D3; D3 is keyed by `ReversibilityClass` and does not wait on D4. **No cycle exists.**

The dependency graph is a tree rooted at C9.1, which carries **both** new fields (D2's and ADR-0022's) in one reopening.

### 6.2 Are Parts 5–8 implementable?

| Part | Needs | Status |
|---|---|---|
| **5 · K3 + mint** | `expected_effect` (D2) · `reversibility_class` (ADR-0022) · budgets (D3) · expiry (D4) · A2 binding (D5) | ✅ **Fully unblocked** once C9.1 ships |
| **6 · `attempt()`** | The warrant's `attempt_budget` and `reversibility_class` — both on the minted `Warrant`; §8.4's rule reads the class | ✅ **Unblocked** |
| **7 · `settle()`** | `Receipt` needs `receipt_id`, `correlation_id`, `trace_id` | ⚠️ **One residual — see 6.3** |
| **8 · `invalidate()`** | The outstanding set and the Override switch, both owned since Parts 1 and 4 | ✅ **Unblocked** |

### 6.3 The one residual, and it is not a minting gap

**R29 — `settle()`'s Receipt identity fields.** The founder ruled that `settle()` keeps its API and *"the Kernel owns all Receipt metadata; Receipt construction occurs internally using Kernel state."*

That ruling is sufficient in principle: the Kernel generates `receipt_id`, `correlation_id` and `trace_id` **at mint** and holds them beside the outstanding warrant, so `settle(warrant_id, outcome)` has everything it needs from state it already owns.

**This ADR does not specify that mechanism**, because it is settlement, not minting, and the brief scopes this document to the mint. **Part 7's brief must confirm it** — and if the Kernel is to generate identifiers at mint, Part 5 must store them, so the two briefs are coupled and should be written together.

### 6.4 One item Part 5 must fix that no specification gives

**`warrant_id` generation.** §4.3 sources it to the Kernel and says nothing more. Constraints, stated so Part 5 does not invent them under pressure:

- **Deterministic under test** — no `uuid4()`, no ambient randomness, or the Kernel becomes unverifiable.
- **Derived from `Clock.stamp()`**, which C1 documents as *"the current moment plus an ordering token; consumes a sequence number."* That is the only monotonic source the Kernel holds.
- **Unique per Kernel instance**, which the sequence number guarantees.

The exact encoding is Part 5's, within those three constraints.

---

## 7 · Amendment to ADR-0021

**D5 is amended a second time**, and only in where the liveness gate lives.

ADR-0021 D5 as amended on 2026-08-06 reads that *"the `EXECUTING` requirement is a minting prerequisite… and belongs to the mint decision path."*

**It becomes:**

> The `EXECUTING` requirement is **satisfied by attestation A1**, which Mission Control answers and §7.3 already requires. It belongs neither to K1 nor to the mint. An objective that is not `EXECUTING` has no dispatched task with satisfied dependencies, so A1 refuses — with `ATTESTATION_REFUSED`, a reason C8 already carries.

**Unchanged:** D5's core ruling that **K1 is structural admission only** and does not enforce `EXECUTING`. D1–D4, A1–A3, and the terminology audit all stand. The table in D5 becomes:

| Check | Question | Where |
|---|---|---|
| **K1** | Is this objective admitted and not finished? | structural admission |
| **A1** | Is this task dispatched and are its dependencies met? | **Mission Control's attestation** |

**Objective Engine Specification §10.2 and §10.3 are unchanged and are no longer contradicted** — their requirement that a non-`EXECUTING` objective mints nothing holds, satisfied by A1.

---

## 8 · Migration impact

### 8.1 C9 → `kalpavriksha-s1-c9.1` — one reopening, two fields

| Field | From |
|---|---|
| `reversibility_class: ReversibilityClass` | ADR-0022 |
| `expected_effect: str` | ADR-0023 D2 |

Both required, no defaults. Position: after `action_class`, before `consequence`. All shipped C9 tests use keyword arguments, so measured positional breakage is **zero**. Three C9 guards are reversed by ADR-0022 §5.2; D2 adds no further reversal, because no shipped guard forbids `expected_effect`.

### 8.2 Everything else

| Component | Effect |
|---|---|
| **C7 `Attestation`** | Unchanged. D5 was chosen partly to avoid touching it |
| **C8 `RefusalReason`** | Unchanged. D1 and D5 were both chosen so that no new member is needed |
| **C12 `ReversibilityRegistry`** | Unchanged. Its callers compute D5's subject; `attest()` already takes one |
| **C4 · C11 · C13 · C14** | Unchanged |
| **C15 Parts 1–4** | Unchanged. 188 tests unaffected |
| **C16** | Callers must supply **both** new fields and compute D5's A2 subject. C16's brief must state it |
| **C17** | Gains D4's invariant: **do not publish `EXECUTING` past the deadline** |
| **Constitution · VEDAs** | Unchanged. No frozen constitutional document is amended |

---

## 9 · Risks

| # | Risk | Severity |
|---|---|---|
| **R36** | Mission Control and the Objective Engine can disagree about liveness, and the Kernel will not catch it (D1) | Low — accepted; the trust every attestation rests on |
| **R37** | `expires_at` omits grant validity, which can only lengthen the window (D4) | Low — bounded by two real terms; tightens when A3 carries an expiry |
| **R38** | `read_only = 5` is the one budget value not forced by the specification (D3) | Low — revisit once real read-failure rates exist |
| **R29** | `settle()`'s Receipt identity fields (6.3) | Medium — Parts 5 and 7 must be briefed together |
| **R34 · R32** | **Closed** by D5 |
| **R35 · O1 · O2** | **Closed** by D2, D3, D4 |

---

## References

- `Engineering/CONFLICT_C15_PART2.md` · `CONFLICT_C15_PART4.md` · `HEALTH_C15_PART4.md`
- `AUDIT_C9_CLAUDE.md` §4 — R-A, which predicted D2's gap
- ADR-0021 (amended here, §7) · ADR-0022
- Kernel Specification §1.2, §3.4, §4.3, §4.4, §7.2, §7.3, §8.4, §8.5, §10.4, §14 R9
- Objective Engine Specification §3.8, §8.2, §10.2, §10.3
- Constitution §17 — `Step`, and its Expected Outcome
