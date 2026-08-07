# Design Validation — Sprint 1 Component 6

**Type:** Constitutional validation pass. No code, no commits, no tags, nothing implemented.
**Date:** 2026-08-05
**Verdict:** **STOP** — see §E. Not because of a constitutional conflict, but because **Component 6 is not determinable from the record.**

---

## 0 · The finding that blocks the audit

The brief asks me to validate "Component 6" without naming it. I cannot, because **the planned numbering and the shipped numbering diverged at Component 3**, and neither track determines what Component 6 is.

| # | `SPRING_1_IMPLEMENTATION_PLAN.md` §2 | Actually shipped | Match |
|---|---|---|---|
| C1 | Canonical Clock | Canonical Clock | ✅ |
| C2 | Principal | Principal **+ Execution Context** | superset |
| C3 | **Reversibility Registry** | **Constitutional Warrant** | ❌ |
| C4 | **Receipt Ledger** (append-only store) | **Constitutional Receipt** (value object) | ❌ |
| C5 | **Override** | **Consequence Quartet** | ❌ |
| C6 | **Constitutional Kernel** | — | **unspecified** |

The divergence is not an error. The shipped track built **immutable value objects in `foundation/`**; the plan's track scheduled **stateful services**. The value-object track is a coherent and defensible order — each object is a dependency of the Kernel and each was buildable with zero services in place. But it means "Component 6" now has two possible referents and no authority to choose between them.

**Guessing is the failure mode that produced the Component 2 and Component 5 conflict reports.** I am not repeating it.

---

## A · Dependency Audit

### A.1 What has shipped

| Component | Tag | Public surface |
|---|---|---|
| Clock | `c1.1` | `Clock`, `Instant`, `SystemClock`, `ManualClock` |
| Principal | `c2.0` | `Principal`, `PrincipalKind`, `PrincipalRegistry`, `UnknownPrincipal`, `InvalidPrincipalRegistry` |
| Execution Context | `c2.0` | `ExecutionContext` |
| Warrant | `c3.0` | `Warrant`, `ReversibilityClass`, `InvalidWarrant` |
| Receipt | `c4.0` | `Receipt`, `ExecutionOutcome`, `InvalidReceipt` |
| Consequence | `c5.0` | `Consequence`, `Cost`, `CostBasis`, `InvalidConsequence` |

All six are immutable value objects. **No service exists yet.**

### A.2 The plan's C6 (Constitutional Kernel) cannot begin

Its three declared dependencies are unbuilt:

| Dependency | Status |
|---|---|
| Reversibility Registry (A2 attestor) | **Not built.** Only the `ReversibilityClass` *vocabulary* shipped, inside `warrant.py`. The registry that classifies capabilities and fails closed does not exist. |
| Receipt Ledger (K3 write target) | **Not built.** Only the `Receipt` *value object* shipped. The append-only store does not exist. |
| Override (K2 switch) | **Not built at all.** |

Kernel Spec §7.2: K3 *"Receipt intent write… If the write fails, the Kernel refuses and nothing executes."* There is nothing to write to. **Building the Kernel next is not possible.**

### A.3 What the Kernel still needs — the eligible candidate set

From Kernel Spec §3.5's four operations and §7.3's eight attestations:

**Value objects (fit the shipped track):**

| Candidate | Required by | Depends on | Depth |
|---|---|---|---|
| **Attestation** | §7.3 (all eight), `Warrant.attestations[]` (§4.3) | Clock (freshness), Principal (attestor identity) | 1 |
| **Refusal** | `authorize()` **and** `attempt()` — two of four operations | nothing | 0 |
| **ExecutionRequest** | `authorize()` input | Principal, Attestation, Consequence | 2 |
| **AttemptToken** | `attempt()` output | Warrant | 1 |

**Services (do not fit the shipped track):**

Reversibility Registry (A2) · Receipt Ledger (A1) · Override (A3) · the Kernel itself.

### A.4 Future components depending on the candidate set

| Depends on | Attestation | Refusal | ExecutionRequest | AttemptToken |
|---|---|---|---|---|
| Constitutional Kernel | ✅ core check loop | ✅ every refusal path | ✅ the input | ✅ `attempt()` |
| Warrant (completing §4.3) | ✅ `attestations[]` | — | — | — |
| Receipt Ledger | ✅ records what was attested | ✅ refusals are recorded (§7.5) | — | — |
| Objective Engine | — | ✅ admission refusals (V1–V5) | — | — |
| Founder Dashboard | — | ✅ *"1,000 actions are waiting"* (§7.5) | — | — |
| Reversibility Registry | ✅ produces the A2 attestation | ✅ fails closed with one | — | — |
| Permission System adapter | ✅ produces the A3 attestation | ✅ | — | — |

---

## B · Terminology Audit

Checked against Constitution §17's 21 frozen terms and against the shipped codebase.

| Candidate | In §17? | In codebase? | Verdict |
|---|---|---|---|
| **Attestation** | No | **Zero occurrences** | ✅ **Clean.** No collision. |
| **Refusal** | No | `BrokerRefusal` (`ai_infrastructure/refusal.py`), `PlanRefusal` (`planner/plan.py`) | ⚠️ **Collision risk.** A bare `Refusal` would be the third refusal type. Must be qualified — `KernelRefusal` — or it repeats the `Intent` mistake. |
| **ExecutionRequest** | No | One mention, in an `execution_context.py` docstring. No class. | ✅ Clean, but adjacent to `ExecutionContext`, `ExecutionResult`, `ExecutionOutcome`, `ExecutionLogEntry` — five `Execution*` types. Boundary must be documented. |
| **AttemptToken** | No | Zero occurrences | ✅ Clean |

**None of the four redefines an existing concept**, provided `Refusal` is qualified.

**Standing terminology debt, unchanged and out of scope:** `Evidence` still carries two meanings (Constitution §17's, and VEDA 04 B5's Evidence Graph), recorded in Objective Engine Spec §13.1 and deferred by founder direction during Component 5. No candidate here touches it.

---

## C · Constitutional Audit

| Question | Answer |
|---|---|
| Would any candidate require **changing a VEDA**? | **No.** All four are named or implied by the Constitutional Kernel Specification, which was written against the frozen VEDAs. |
| Would any require **changing an existing component**? | **`Attestation`: yes, additively.** `Warrant` has no `attestations[]` field — Component 3 recorded it as *"additive: each arrives with the component that produces it."* Adding an optional field to a frozen component needs explicit authorization. The other three: no. |
| Would any require **changing a public API**? | **No**, if additive. `foundation/__init__.py` gains exports, as every component so far has. |

### C.1 The one item needing a decision before it can be built

`Warrant.attestations` does not exist. Two options, both additive:

- **(a)** Add an optional `attestations: tuple[Attestation, ...] = ()` field to `Warrant`. Changes a component tagged and verified at `c3.0`.
- **(b)** Leave `Warrant` untouched; the Kernel holds attestations alongside the warrant rather than inside it.

Kernel Spec §4.3 lists `attestations[]` as a warrant field, which favours (a). But Component 3's brief and this one both forbid modifying shipped components without authorization. **This is a decision, not a defect** — flagged so it is made deliberately.

---

## D · Final Public Contract — conditional

Produced for **Attestation**, the recommended candidate (§E.2). **This is a proposal, not a determination.** If Component 6 is something else, this section does not apply.

### Files — exactly three, per the established pattern

```
src/master_agent/foundation/attestation.py      new
src/master_agent/foundation/__init__.py         modified, exports only
tests/test_foundation_attestation.py            new
```

### Classes and immutable value objects

```
AttestationQuestion   Enum, closed — the eight questions of Kernel Spec §7.3
                      TASK_READY · REVERSIBILITY · PERMISSION · RULE ·
                      PRINCIPAL · PAYLOAD_SCHEMA · PROVIDER · ADMISSION

AttestationVerdict    Enum, closed — SATISFIED · REFUSED
                      Two values, not three. Kernel §7.3: an attestation
                      that is missing, stale, or subject-mismatched "is
                      treated as absent" — absence is not a third verdict.

Attestation           frozen dataclass
                      question · attestor · subject · verdict · attested_at
                      · reason (required on REFUSED, refused on SATISFIED)

InvalidAttestation    ValueError, raised at construction
```

### Interfaces

**None.** Like every foundation component so far, this is a value with no protocol. The Kernel *verifies* attestations; it does not call an attestor interface. Introducing one would invert the dependency the Kernel Specification §1.2 establishes — *"attestation, not reimplementation."*

### Invariants enforced at construction

| Invariant | Grounding |
|---|---|
| `attested_at` is timezone-aware, normalised to UTC | Clock discipline, C1–C5 |
| `attestor` and `subject` non-empty | §7.3 subject-match check needs both |
| `REFUSED` requires a `reason` | §7.5 — *"a refusal names the check that failed"* |
| `SATISFIED` refuses a `reason` | Symmetry with `Receipt.compensation_ref` (ED-007) |
| Deterministic `as_dict()`, hashable, frozen | Every component since C3 |

### The one behaviour it needs

```
is_stale(at, max_age) -> bool
```

Takes the moment as an argument, never reads a clock — the pattern established by `Warrant.is_expired()`. Kernel §7.3 validates **freshness**, and freshness is the one attestation property the Kernel cannot check without asking the attestation itself.

### Tests

| Group | Covers |
|---|---|
| Vocabulary | Both enums closed; eight questions exactly; two verdicts, not three |
| Construction | Every field required; blank attestor/subject refused; naive timestamp refused; UTC normalisation |
| Reason symmetry | `REFUSED` without reason refused; `SATISFIED` with reason refused |
| Freshness | Fresh, exactly-at-boundary, stale; naive moment refused |
| Value semantics | Immutable, hashable, deterministic equality, deterministic JSON-ready `as_dict()` |
| Constitutional | Cannot execute or authorize · no ambient time · imports nothing that could act · references no execution object · Components 1–5 untouched |

**Estimated 45–55 tests**, consistent with C3 (55), C4 (59), C5 (49).

---

## E · GO / STOP Decision

### **STOP**

Not a constitutional conflict. **An identification failure**: Component 6 is not named, and the two numbering tracks disagree about what it would be.

### E.1 What is blocked, and what is not

| | |
|---|---|
| **Blocked** | Implementation of anything called "Component 6" |
| **Not blocked** | Everything else. No VEDA conflict was found. No shipped component is at risk. All six tags remain green. |

### E.2 Recommendation — `Attestation` as Component 6

Grounded in three properties:

**It is the Kernel's core loop.** §7.3 — the Kernel *"verifies each attestation's presence, attestor identity, subject match, and freshness. It never re-derives the verdict."* That sentence is the entire design of the Kernel, and the type it operates on does not exist.

**It has the widest downstream reach.** Required by the Kernel, the Warrant's §4.3 field set, the Receipt Ledger, the Reversibility Registry, and the Permission System adapter — five consumers, more than any other candidate.

**Its terminology is clean.** Zero occurrences in the codebase, absent from §17. `Refusal`, by contrast, would be the third refusal type and needs qualifying first.

**Suggested order for the remainder of the value-object track**, each buildable with only what precedes it:

```
C6  Attestation      → Clock, Principal
C7  KernelRefusal    → Attestation
C8  ExecutionRequest → Principal, Attestation, Consequence
C9  AttemptToken     → Warrant
    ── value objects complete; services begin ──
C10 Reversibility Registry   C11 Receipt Ledger   C12 Override   C13 Kernel
```

### E.3 What unblocks implementation

One of:

1. **Confirm `Attestation`** — §D is then the implementation contract, and the only open question is §C.1 (whether `Warrant` gains an optional `attestations` field).
2. **Name a different component** — I will run this validation against it before any code is written.
3. **Reconcile the numbering** — declare whether the shipped track or the plan supersedes, so C6 through C13 have one meaning.

### E.4 A note on the plan

`SPRING_1_IMPLEMENTATION_PLAN.md` §2 now describes a numbering that shipped components do not follow. It is not wrong about *what* must be built — every component in it is still required — only about the order and the numbers. **Left untouched**, since amending it is not part of a validation pass, but it should be reconciled before it misleads someone.

---

## F · What was not done

No file created in `src/`. No test written. No commit. No tag. `foundation/` contains the same six modules it did at `kalpavriksha-s1-c5.0`.

---

*Constitutional validation pass. Every claim verified against the frozen documents, the Constitutional Kernel Specification, and the shipped source on 2026-08-05.*
