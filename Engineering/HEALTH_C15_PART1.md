# Health Report — Sprint 1 Component 15, Part 1: Kernel Skeleton

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-06
**Status:** Part 1 complete. **Not committed, not tagged, no Rule 001.**

> Structure only. No check runs, nothing is minted, nothing is written, nothing is published, and no state changes after construction.

---

## 1 · What was built

| File | | Lines |
|---|---|---|
| `src/master_agent/kernel/kernel.py` | new | 238 (**34 AST statements**) |
| `src/master_agent/kernel/__init__.py` | new — exports | 18 |
| `tests/test_kernel_skeleton.py` | new | 416 |

**Public surface**

```
Kernel          authorize · attempt · settle · invalidate
                override · outstanding_count
InvalidKernel   ValueError, raised at construction
SCOPE_ALL       "all" — §11.8's bulk scope
```

**Placement:** `master_agent/kernel/`, not `foundation/`. It depends on two packages — `foundation` and `ledger` — and `foundation/` admits a module only if it has no dependency on any other Kalpavriksha package. §3.6 places the Kernel in Shared Infrastructure.

---

## 2 · Dependency wiring — two, and why not more

```
Kernel(clock: Clock, ledger: ReceiptLedger)
```

§7.3 is the reason the list is short:

> *"The Kernel verifies each attestation's presence, attestor identity, subject match, and freshness. **It never re-derives the verdict.**"*

**The Kernel holds no attestor.** Not the Reversibility Registry, not the Permission System, not the Broker. Their answers arrive inside the `ExecutionRequest` as `Attestation` values and the Kernel checks them. Holding one would be the reimplementation §1.2 forbids, and §3.4's table names the real owner of every entry. A guard test asserts none is imported.

What remains is what §3.3 genuinely assigns:

| Dependency | Grounding |
|---|---|
| **`Clock`** | §4.3 sources `issued_at` and `expires_at` to the Kernel. Every value object in `foundation/` refuses to read ambient time precisely so that one component does — this is it |
| **`ReceiptLedger`** | §7.2 K3's obligation. *"The Kernel owns the obligation; A1 owns the storage."* Injected, never constructed, so the Kernel does not decide where the audit spine lives |

Both validated at construction against their protocols, not concrete classes — a `ManualClock` is as valid as a `SystemClock`.

### 2.1 Two dependencies deliberately absent

| Absent | Why |
|---|---|
| **The admission source for K1** | §7.2 K1 resolves an `objective_id` to an admitted objective, and §10.2 makes that an `AdmissionRecord` the Objective Engine publishes. **C17 does not exist**, and this brief requires every dependency to already exist. Inventing a lookup protocol would be a new concept with no owner. **K1's wiring belongs to the part that implements K1** |
| **The Event Bus** | §3.3 gives the Kernel *"what is published, when. Not the bus, which already exists."* Nothing is published in Part 1, and §10.3 records that *"zero subscribers is a valid, fully functional configuration"* — wiring an unused bus now would be a dependency with no use |

**Recorded rather than approximated.** Both are named in the module docstring and carried as risks in §7.

---

## 3 · Internal state — §3.3's two, immutable values in mutable slots

| Owned | Field | At construction |
|---|---|---|
| **The Override switch** | `_override: OverrideSwitch` | **Running.** A Kernel that started suspended would refuse every mint with nobody having asked for that |
| **The Intent lifecycle** | `_outstanding: dict[str, Warrant]` | **Empty.** §4.1 makes an Intent short-lived; warrants are minted, never restored |

Each *value* is immutable; the slot holding it changes. `__slots__` is exactly these four names plus the two dependencies, asserted by test — §3.4's budgets, occupancy, providers, capability resolution, verification and narration all have named owners and none is here.

`override` is handed out as the frozen `OverrideSwitch` itself, so a reader cannot suspend autonomy by touching what it was given. `outstanding_count` returns a count rather than the collection: handing out the collection would let a caller reach the Intent lifecycle §3.3 assigns the Kernel.

---

## 4 · The four operations, unimplemented

§3.5 verbatim, with two ratified renames — `Intent` → `Warrant` (Objective Engine Spec §13.1 Conflict A) and `Refusal` → `KernelRefusal` (Roadmap §2 C8):

```
authorize(request: ExecutionRequest) -> Warrant | KernelRefusal
attempt(warrant_id: str)             -> AttemptToken | KernelRefusal
settle(warrant_id: str, outcome: ExecutionOutcome) -> Receipt
invalidate(scope: str, reason: str)  -> int
```

**Each raises `NotImplementedError` naming the part that will build it.**

That is not a TODO placeholder. It is the loudest available statement that behaviour is absent, and it is deliberately **not** a `KernelRefusal`: a refusal is a constitutional decision the Kernel made and must record (§7.5), while an unbuilt operation is not a decision. Conflating them would put a lie in the ledger. A test asserts the raised error is not a `KernelRefusal`.

**There is no `execute()`** — §3.5, *"The Kernel is called; it never calls."* Asserted, along with `run`, `invoke`, `dispatch` and `perform`.

**The public surface is exactly these four plus the two readers**, asserted as a set equality so no speculative method can arrive unnoticed.

---

## 5 · Quality gates

| Gate | Result |
|---|---|
| Part 1 tests | **45 passed, 0 failed** (0.15 s) |
| Ruff — `kernel/` + tests | **All checks passed** |
| Line length | 88 / 74 / 88 (limit 100) |
| Architecture guards (Rule 001 set, 6 modules) | **215 passed, 1 skipped, 0 failed** |
| §14 R9 ceiling | **34 of 600 executable statements** — 6% consumed |

Architecture guards were run because Part 1 introduces a new package that could have crossed a boundary another component's guard defends. It had not.

### 5.1 Test coverage — structure present, and no behaviour early

The suite proves both directions, which is what makes it a Part 1 suite rather than a coverage exercise:

| Proves present | Proves absent |
|---|---|
| Both dependencies required and protocol-validated | No attestor imported (§7.3, §1.2) |
| Override starts running; outstanding starts empty | No `execute()`, `run`, `invoke`, `dispatch` |
| Exactly four operations, with §3.5's signatures | No speculative method — surface asserted as a set |
| `SCOPE_ALL` names §11.8's bulk case | No confirmation or friction parameter on **any** of the four |
| `__slots__` is exactly the six owned names | Nothing §3.4 assigns elsewhere |
| Exported from its package | No Objective Engine import; no Worker, Provider or capability; no `persistence`; no ambient time |
| | **Construction writes nothing to the ledger and reads no clock** |

The last one is measurable because `ManualClock` only advances when told — so a construction-time clock read would be observable, and is asserted not to happen.

---

## 6 · One naming note

`Kernel` was clean: the only prior `class Kernel*` hits were C8's `KernelCheck` and `KernelRefusal`. `InvalidKernel` and `SCOPE_ALL` are new and collide with nothing.

---

## 7 · New risks

| # | Risk | Severity | Note |
|---|---|---|---|
| **R28** | **K1 has no admission source, and cannot have one until C17.** The Kernel's first constitutional check has no wiring | **Medium** | Deliberate — inventing a lookup protocol would create a concept with no owner. **The part implementing K1 must decide** whether the Kernel is injected with an admission lookup or an `AdmissionRecord` is supplied per request. The latter would keep the Kernel free of C17 entirely and is worth weighing first |
| **R29** | **`settle(warrant_id, outcome)` cannot construct a full `Receipt` from its declared arguments.** §3.5 specifies `settle(intent_id, Outcome) → Receipt`, but `Receipt` also requires `correlation_id`, `trace_id`, `started_at`, `completed_at` and `receipt_id` | **Medium** | **New, and it is a specification gap, not an implementation choice.** The signature here is §3.5's literal shape. The part implementing `settle` must either widen the signature or establish where those fields come from — surfaced now rather than discovered mid-build |
| **R25** | The ledger is not thread-safe; the single-writer assumption is unstated | Medium | Carried from C13. **The part implementing the operations must state that Kernel operations are serialised** |
| **R24** | §11.8's four-step override mechanism is unimplemented | Low | Carried from C14. Lands on the part implementing `invalidate()` |
| **R6** | §14 R9's 600-line ceiling | High | **6% consumed.** Recorded so the budget is visible from the start rather than discovered at the end |

---

## 8 · Blockers

**None for Part 1.**

R28 and R29 both land on later parts and are recorded so they are decided rather than discovered.

---

## 9 · Preservation

C1–C14 untouched — no file outside `src/master_agent/kernel/` and `tests/test_kernel_skeleton.py` was modified. `foundation/__init__.py` not touched: the Kernel is not a foundation component and exports through its own package. No specification, roadmap, amendment or ADR modified. No commit, no tag.

**STOP.** Part 2 not started.
