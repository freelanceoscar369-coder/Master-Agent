# C9 Implementation Precheck — Execution Request

**Type:** Pre-implementation grounding pass. **No code, no commits, no tags, nothing implemented.**
**Date:** 2026-08-05
**Subject:** Sprint 1 Component 9 — Execution Request
**Predecessor:** `kalpavriksha-s1-c8.0`, GREEN under Rule 001
**Verdict:** **BLOCKED on one decision (M8).** Everything else is READY. See §6.

> Every dependency below was re-derived from the frozen documents and from the shipped source, not read from the roadmap. That discipline is what Amendment 001 exists to institutionalise, and it produced three findings here.

---

## 1 · Grounded dependency verification

### 1.1 What the roadmap declares

`SPRING_1_IMPLEMENTATION_ROADMAP_v2.md` §2 C9: *"Depends on. C2 Principal, C6 Consequence (optional, pending B1), C7 Attestation."*

### 1.2 What the amendment declares — and it disagrees with itself

| Location | Declares |
|---|---|
| Amendment §3 M8 (prose) | *"C9 does **not** depend on C2, only on C6 and **C7's enum**."* |
| Amendment §5 (dependency table) | `C9 · Execution Request · C6 Consequence, **C7 Attestation**, ~~C2~~ (pending M8)` |

**The table says the `Attestation` type; the prose says the enum only.** These are different dependencies. Resolved in §5.2 below.

### 1.3 Re-derived from the frozen documents

| Declared | Verified against | Verdict |
|---|---|---|
| **C2 `Principal`** | Shipped `Warrant.principal_id: str` (C4, frozen at `c3.0`). An `ExecutionRequest` becomes a `Warrant`. | ⚠ **Depends on the M8 decision.** If `principal_id: str`, C9 does not depend on C2 at all |
| **C6 `Consequence`** | Kernel Spec §4.3 lists `consequence` on the Intent; §14.1 governs its pending state | ✅ **Confirmed**, but see §5.3 — *"optional"* is the wrong word |
| **C7 `Attestation`** | Roadmap §2 C9's own public API lists `attestations`; Kernel Spec §7.3 requires the Kernel to verify *"presence, attestor identity, subject match, and freshness"* — properties of the **object**, not the question | ✅ **The type, not the enum.** The §5 table is right; the M8 prose is loose |
| **C8 `KernelRefusal`** | Not declared anywhere | ✅ **Correctly absent.** `authorize()` returns a refusal; the *request* never carries one |
| **C1 `Clock`** | Not declared | ✅ **Correctly absent.** A request carries no time. `issued_at`/`expires_at` are set by the Kernel at mint (§4.3) |

### 1.4 Terminology audit — measured against `src/` and `tests/` today

| Proposed name | Constitution §17 | Occurrences in code | Verdict |
|---|---|---|---|
| `ExecutionRequest` | absent | **0 classes.** 2 docstring mentions — `execution_context.py:21`, `refusal.py:14` | ✅ clean |
| `ActionClass` | absent | **0** | ✅ clean |
| `InvalidExecutionRequest` | absent | **0** | ✅ clean |
| `action_class` (field) | absent | **0** | ✅ clean |
| `payload_digest` (field) | absent | present on shipped `Warrant` | ✅ **reuse, not collision** — same meaning, same type |

**Zero collisions.**

> **Correction to Roadmap §5 R9, measured.** R9 states *"Five `Execution*` types will coexist after C9."* The actual count today is **seven**: `ExecutionReplay`, `ExecutionRecord`, `ExecutionRow`, `ExecutionResult`, `ExecutionLogEntry`, `ExecutionContext`, `ExecutionOutcome`. C9 makes **eight**. The mitigation is unchanged — the module documents its boundary, as C3 and C5 did — but the brief should state eight rather than five, because a reader who checks the number and finds it wrong stops trusting the rest.

---

## 2 · Frozen document references

| Document | Sections bearing on C9 |
|---|---|
| **Constitutional Kernel Specification** | §3.5 (`authorize(ExecutionRequest) → Intent \| Refusal`) · §4.3 (Intent contents and each field's source) · §4.4 (non-transferability; the digest is checked at `attempt()`) · §5.2 (convergence, not merger) · §7.3 (the eight attestations) · §7.4 (attestation sets by action class) · **§14.1** (`pending_consequence_engine`) |
| **VEDA 04** | A1 (intent record contents) · §9 (phase gates) |
| **VEDA 01 / VEDA 03** | No direct bearing. C9 is not founder-facing |
| **Roadmap v2** | §2 C9 · §4 order · §5 R9 |
| **Amendment 001** | **M8** (the open decision) · §5 table · §6 terminology |
| **Objective Engine Spec** | §10.2 only indirectly — `objective_id` is the K1 anchor; C9 carries the id, never the record |
| **Shipped source** | `foundation/warrant.py` (the output shape) · `foundation/attestation.py` · `foundation/consequence.py` |

**First Founder Journey Specification:** reviewed; C9 is infrastructure beneath the slice and the specification places no constraint on it.

---

## 3 · Required inputs — what must exist before C9 starts

### 3.1 Shipped and available

| Input | From | Tag | Status |
|---|---|---|---|
| `Attestation`, `AttestationQuestion`, `AttestationVerdict` | C7 | `c7.0` | ✅ available |
| `Consequence`, `Cost`, `CostBasis` | C6 | `c5.0` | ✅ available |
| `Principal`, `PrincipalKind` | C2 | `c2.0` | ✅ available — **needed only if M8 resolves to the object** |
| `Warrant` field shape (the target of the transformation) | C4 | `c3.0` | ✅ available |

**No unshipped component is required.** C9 has no dependency on C10–C21.

### 3.2 Decisions required before the brief is written

| # | Decision | Recommendation | Authority |
|---|---|---|---|
| **M8** | `principal: Principal` or `principal_id: str`? | **`principal_id: str`** — see §5.1 | **Founder.** Amendment §3 says *"Decide before C9's brief"* |
| **P2** | Does `attestations` carry `Attestation` objects or only questions? | **Objects** — the §5 table, corroborated by §7.3 | Determinable from frozen documents; see §5.2 |
| **P3** | Is `consequence` optional, or does it carry §14.1's marker? | **Marker, never null** — see §5.3 | Determinable from Kernel Spec §14.1 |

---

## 4 · Required outputs — what C9 must produce

### 4.1 Files, per the established three-file pattern

```
src/master_agent/foundation/execution_request.py   new
src/master_agent/foundation/__init__.py            modified, exports only
tests/test_foundation_execution_request.py         new
```

### 4.2 Public surface, per Roadmap §2 C9

```
ActionClass                closed enum, 2 — local · intelligence  (§7.4)
ExecutionRequest           frozen dataclass
InvalidExecutionRequest    ValueError, raised at construction
```

### 4.3 The transformation C9 exists to serve

An `ExecutionRequest` is the input half of §3.5's contract; the shipped `Warrant` is the output half. Every request field must therefore be traceable to a warrant field or to something the Kernel needs in order to mint one.

| `ExecutionRequest` field | Becomes / feeds | Source per §4.3 |
|---|---|---|
| `objective_id` | `Warrant.objective_id` — the K1 anchor | **Request** |
| `principal` **or** `principal_id` | `Warrant.principal_id` | Principal model |
| `capability` | `Warrant.capability` | Capability Registry |
| `payload_digest` | `Warrant.payload_digest` | Kernel — see §5.4 |
| `action_class` | selects the §7.4 attestation set | Kernel — see §5.4 |
| `target_ref` | Intent `target_ref` | **Request** |
| `attestations` | verified by §7.3; held by the Kernel alongside the warrant | Various owners |
| `consequence` | Intent `consequence` | Consequence Engine (B1, Sprint 2) |

**Fields C9 must NOT carry**, because §4.3 sources them elsewhere and the Kernel or an attestor supplies them at mint: `warrant_id` · `reversibility_class` · `compensating_action` · `undo_window` · `consequence_ceiling` · `grant_ref` · `rule_ref` · `attempt_budget` · `issued_at` · `expires_at` · `sequence` · `decision_ref` · `expected_effect` · `task_ref`.

A request that carried any of these would be the caller authorizing itself — the request would arrive pre-decided and the Kernel would have nothing left to decide.

### 4.4 Invariants the brief should require

Derived from the frozen documents, stated so C9's brief needs no clarification:

| Invariant | Grounding |
|---|---|
| `objective_id` non-empty | §7.2 K1 — *"No intent exists without one"* |
| `capability` and `payload_digest` non-empty | shipped `Warrant.__post_init__` requires both non-empty |
| `action_class` is an `ActionClass` | §7.4 selects the attestation set by it |
| Attestations are a tuple, deduplicated by question | §7.3 assigns one attestor per question; two answers to one question is an unresolvable state |
| **No** `payload` field, ever | §4.3 — *"The digest, never the payload… permanence plus sensitive content is a liability"* |
| Frozen, hashable, deterministic `as_dict()` | every component since C3 |
| Carries no clock reading | C7, C8 precedent |

> **The brief must NOT require the request to be complete.** §7.3 makes the Kernel verify attestation presence; if `ExecutionRequest` refused construction without all eight, the Kernel's presence check would be dead code and a caller could never build the object that produces the refusal §7.5 requires to be recorded. **Completeness is the Kernel's judgment, not the request's invariant.** This is the single most likely way C9 is built wrong.

---

## 5 · Potential conflicts

### 5.1 M8 — `Principal` object or `principal_id`? **OPEN. Founder decision.**

The amendment states the tension and defers the choice:

| Shipped precedent | Carries | Stated reason |
|---|---|---|
| `ExecutionContext` (C3) | `principal: Principal` | runtime identity, *"so a receipt can name them without a lookup"* |
| `Warrant` (C4) | `principal_id: str` | *"a flat, self-contained record… deterministic to serialise"* |

**New evidence, measured from the shipped source rather than recalled:** `Warrant.principal_id` is typed `str` and validated non-empty alongside `objective_id`, `capability` and `payload_digest`. An `ExecutionRequest` becomes a `Warrant`. Carrying a `Principal` object would mean C9 holds a richer type than the thing it turns into, and the Kernel would discard the extra at mint.

**Recommendation: `principal_id: str`.** Consequences if adopted: C9 does **not** depend on C2, and its dependency set reduces to C6 and C7.

**This is a decision, not a defect, and it is not mine to make.** Amendment §3 assigns it to brief time.

### 5.2 P2 — the amendment contradicts itself on the C7 dependency. **Determinable.**

§3 M8's prose says *"only on C6 and C7's enum"*; §5's table says *"C7 Attestation"*.

**The table is correct.** Roadmap §2 C9's own public API lists `attestations` as a field, and Kernel Spec §7.3 requires the Kernel to verify each attestation's *presence, attestor identity, subject match, and freshness* — `attestor`, `subject` and `attested_at` are fields of the **object**. An enum cannot carry them.

The prose sentence sits directly beneath M5's C8 entry, which legitimately reduces to the enum. **The most likely explanation is a carry-over, not a considered narrowing.** Recorded rather than assumed: if the intent really was the enum, C9's public API in the same document is wrong instead, and that is a larger correction than a precheck may make.

**Severity: low.** Both sources agree C9 depends on C7; only the granularity differs, and the frozen specification settles it.

### 5.3 P3 — *"optional, pending B1"* contradicts Kernel Spec §14.1. **Determinable.**

Roadmap §2 C9 declares *"C6 Consequence (**optional**, pending B1)."* Kernel Spec §14.1 says the opposite, verbatim:

> *"Until then the field carries the explicit marker `pending_consequence_engine` — **never null, never omitted**, and never a partial quartet."*

An optional field is a null. **This is the same finding Amendment M1 made for C13**, where the note reads: *"an intent record written in Sprint 1 carries the explicit marker `pending_consequence_engine`, never null. C13's brief must state this or it will be discovered at implementation time."*

**C9's brief needs the identical sentence.** The open sub-question — whether the request carries the marker or the Kernel substitutes it at mint — is genuinely undecided by the frozen documents and should be settled at brief time.

**Severity: medium.** It changes a field's type and its invariant, and it is exactly the class of thing that gets discovered mid-implementation.

### 5.4 P4 — §4.3 sources `payload_digest` and `action_class` to the Kernel, not the Request. **Low.**

§4.3's Source column marks `objective_id` and `target_ref` as *"Request"* but `payload_digest` and `action_class` as *"Kernel"*. Roadmap §2 C9 puts all four on the request.

**The roadmap is almost certainly right, on three pieces of evidence:** the shipped `Warrant.payload_digest: str` is passed in, not computed; §4.4 says the digest *"is checked at `attempt()`"* — the Kernel compares digests rather than deriving them; and a Kernel that computed the digest would need the payload, which §3.4's minimality and §4.3's own *"the digest, never the payload"* both argue against.

**Read as §4.3 describing where a value's authority originates rather than which component assigns it.** Flagged so the brief states the reading explicitly instead of inheriting an unexamined assumption.

### 5.5 Not conflicts — checked and clear

| Checked | Result |
|---|---|
| Constitution §17 frozen terms | No proposed name appears. Clean |
| Kernel Spec §3.4 ownership table | C9 claims nothing the Kernel assigns elsewhere. It is a value; it owns no responsibility |
| Objective/Mission ADR (R1) | **Does not touch C9.** C9 carries `objective_id` as an opaque string and never the state vocabulary the ADR governs. This is why C9 is buildable while C11 is not |
| MB032–039 collision (R3) | **Does not touch C9.** C9 adds one file to `foundation/`; the uncommitted work modifies `orchestrator/`, `executor/`, `runtime/`, `missions/`. Zero overlap |
| Five `Execution*` types (R9) | Real but mitigated; the count is eight, not five — §1.4 |

---

## 6 · Verdict — READY or BLOCKED

### **BLOCKED — on exactly one decision.**

| Dimension | Status |
|---|---|
| Dependencies shipped | ✅ **READY.** C6 and C7 are green; nothing unshipped is required |
| Terminology | ✅ **READY.** Zero collisions, measured |
| Ownership | ✅ **READY.** Claims nothing §3.4 assigns elsewhere |
| Frozen documents | ✅ **READY.** §3.5, §4.3, §7.3, §7.4 fully specify the field set |
| Output shape | ✅ **READY.** The shipped `Warrant` fixes what the request must become |
| Not blocked by R1 | ✅ **READY.** No Objective/Mission vocabulary |
| Not blocked by R3 | ✅ **READY.** No file overlap |
| **M8 — `principal_id` or `Principal`?** | ⛔ **BLOCKED.** Founder decision, assigned by Amendment §3 to brief time |

### 6.1 What unblocks it

**One sentence: ratify M8.** The amendment carries a recommendation, and §5.1 above adds shipped-source evidence for it. If M8 resolves to `principal_id: str`, C9's dependency set is C6 and C7, and the brief can be written immediately.

P2, P3 and P4 do **not** block. All three are determinable from the frozen documents, all three have a stated resolution above, and each needs one sentence in C9's brief rather than a decision.

### 6.2 Founder Edition critical-path note (Rule 002)

> *Does C9 increase the probability that Founder Edition succeeds before 12 Aug?*

**Yes.** `authorize(ExecutionRequest)` is the Kernel's primary operation; C15 cannot be written without its input type. C9 is also one of the components entirely unaffected by R1, so it is progress that the unratified ADR cannot stall.

**But R1 remains the binding constraint, and C9 does not change that.** After C9, the Kernel's remaining prerequisites are C10, C12, C13, C14 — all unblocked — and **C11, which Amendment M6 rates critical and blocked on the `Objective`/`Mission` ADR.** C15 depends on C11.

Sequencing C9 now is correct and buys time. It does not buy a Kernel. **M6 §10's recommendation — ratify the ADR — is still the single decision standing between the sprint and continuous progress**, and the number of components that can be built around it is now four.

---

## 7 · What was not done

No file created in `src/`. No test written. No commit. No tag. No roadmap or amendment file edited. `foundation/` contains the same eight modules it did at `kalpavriksha-s1-c8.0`.

**C9 was not started.**

---

*Pre-implementation grounding pass. Every dependency re-derived from VEDA 01/03/04, the Constitutional Kernel Specification, the Objective Engine Specification, Roadmap v2, Amendment 001 and the shipped source at tag `kalpavriksha-s1-c8.0` on 2026-08-05. All occurrence counts measured, not estimated.*
