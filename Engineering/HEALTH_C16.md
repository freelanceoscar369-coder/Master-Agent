# Health Report — Sprint 1, Component 16: The Execution Coordinator

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-06
**Status:** Complete. **Not committed, not tagged, no Rule 001.**
**Built on:** `kalpavriksha-s1-c15.0` — commit `c565244`, verified HEAD before any code was written.
**Ground:** Kernel Specification · ADR-0022 · ADR-0023 · Roadmap v2 (+ Amendments 001–003) · VEDA 01–04.

**Constraints honoured:** C1–C15 consumed exactly as shipped · no GREEN
component modified · no Foundation reopened · no new runtime dependency ·
no ADR decision changed · no constitutional vocabulary added · R34–R48 not
solved.

---

## 1 · A scope decision the founder should see first

**The Roadmap and this brief name two different halves of C16, and only
one of them is buildable under the brief's constraints.**

Roadmap §2 C16 · *Execution Path Unification*:

> *"One gate. `warrant_id` required by `LocalExecutor.run()`, no
> alternative route to a tool… **Modifies** `orchestrator/`, `executor/`,
> `runtime/gateway.py`, `runtime/engine.py`,
> `ai_infrastructure/execution.py`, `cli.py`."*

This brief · *Execution Coordinator*:

> *"Dependencies available: C1–C15 only… no new runtime dependencies…
> responsible for orchestration only. It must compose existing Kernel
> operations."*

The two cannot both hold. Migrating fifteen call sites in `runtime/`,
`executor/` and `orchestrator/` **is** a dependency on those packages.

**What was built is the brief's half:** a component depending on C1–C15
alone, which composes the Kernel's four operations into §6.1's sequence.
It is the thing the fifteen call sites will each be migrated *to*.

**What was not built, and is recorded rather than assumed away:** the
migration itself. Until it lands, an alternative route to a tool still
exists, and Roadmap §2's *"no alternative route"* is not yet true.
**Recorded as R51.** It needs a brief that permits touching those
packages; it is not an engineering blocker.

---

## 2 · What was built

| File | | |
|---|---|---|
| `src/master_agent/coordinator/coordinator.py` | new | 385 lines, **70 AST statements** |
| `src/master_agent/coordinator/__init__.py` | new | four exported names |
| `tests/test_coordinator.py` | new | **56 tests** |

```
ExecutionCoordinator(kernel)
    run(request, work) -> Execution

Work      = Callable[[AttemptToken], ExecutionOutcome]
Execution = warrant · receipt · refusal · attempts · error   (frozen)
```

**One public operation. One collaborator. No state.**
`__slots__ == {"_kernel"}`, asserted by test, and two Coordinators over
one Kernel are indistinguishable because everything that persists lives
below them.

---

## 3 · Why the component exists at all

§6.1 states the exit protocol in four lines. Four lines is not many, and
that is the problem:

> §6.3 — *"Every minted intent must be settled. Settlement is mandatory,
> and its absence is a defect rather than a shrug."*
>
> §4.4 — an unsettled intent is *"a first-class defect, never a silently
> discarded record."*

Both sentences describe something a caller can forget. This component
makes the sequence **structural rather than remembered**: the order, the
retry bound and the settlement are not the caller's business and cannot be
got wrong.

Tested directly — a work that raises still settles its intent, and the
records land in §9.1's order every time.

---

## 4 · Four decisions, each with its clause

### 4.1 The retry loop lives here, and it counts nothing

§3.4 assigns it by name:

> | Retry *mechanics* | **The Runtime.** The Kernel authorizes an attempt
> | budget; it does not loop. |

The loop **asks** `Kernel.attempt()` for another attempt and stops when
the Kernel refuses one. It holds no counter against §8.5's budget —
holding one would be the second opinion §1.2 forbids, and §8.1 is precise
that the defect was never the loop but *"that there was nothing for the
loop to be bounded by."*

Asserted three ways: `__slots__` has no counter, `attempt_budget` appears
nowhere in `run()`, and every reversibility class is exercised through the
loop to its own budget and no further.

### 4.2 §8.4 is decided here, and that is not duplication

> *"An action classified `irreversible` is never automatically retried.
> Ever. **Regardless of attempt budget**, error class, or how transient
> the failure appears."*

C4 already forces `attempt_budget == 1` for an irreversible warrant, so
the Kernel would refuse a second attempt anyway. The rule is still decided
here because §8.4 says *"regardless of attempt budget"*, and this is the
only place in the system that decides whether to **ask**. That is a
different question from whether one would be granted, and the Kernel does
not answer it — the Kernel does not loop.

`_may_retry()` reads `warrant.is_irreversible` and never reads the budget,
asserted by source.

### 4.3 An exception from the work settles `unknown`, not `failed`

§6.3 defines the two words and they are not interchangeable:

| `failed` | *"The effect did not occur, and this is known"* |
| `unknown` | *"The caller cannot determine whether the effect occurred"* |

An unexpected exception establishes the second. §6.3: *"`unknown` exists
because pretending otherwise is how a system double-charges a card."* So
the intent settles `unknown`, which never auto-retries and which
escalates — the honest reading, and the safe direction in every case.

`BaseException` is deliberately not caught: a `KeyboardInterrupt` is not
an execution outcome. Tested, including that an interrupted run leaves the
intent outstanding and unsettled rather than tidily disposed of — which is
exactly the state §9.5 needs to be able to see.

### 4.4 Escalation is reported, never performed

§8.4: an irreversible action settled `failed` or `unknown` *"escalates as
a judgment request."*

`Execution.requires_escalation` says one **is required**. It does not
raise one — §3.4 gives narration and the founder surface to D1, B2 and
VEDA 03, and a component that manufactured judgment items would build the
inbox VEDA 03 abolishes. The property is derived from values that already
exist: C5's own `Receipt.requires_escalation` for `unknown`, and the
warrant's class for the irreversible-failure clause. **No vocabulary is
added.**

---

## 5 · What it does not do, proven rather than promised

| Never | Owner | Asserted by |
|---|---|---|
| Mint anything | Kernel §3.3 | No `Warrant(`, `Receipt(`, `AttemptToken(` or `IntentRecord` in source |
| Write to the ledger | K3, and A1 owns storage | No `ledger` import; no `record_*` call |
| Perform a Kernel check or re-verify an attestation | §7.2, §7.3 | No `_check_*`, `_verify_attestations`, `is_suspended`, `is_terminal`, `consequence_ceiling` or `exceeds(` in source |
| Read a clock | The Kernel holds the canonical one | No clock import; no ambient-time call |
| Build an `ExecutionRequest` | **The caller** — ADR-0022 D2 | No `ExecutionRequest(` in source; `run()` takes one |
| Hold an attestor | §7.3 | No import of reversibility, permissions, broker, mission control, attestation or admission |
| Invalidate | §11.8 — the founder's and C17's | The word appears nowhere in the module |
| Compensate | §6.4 — *"no privileged undo path"* | No compensation call in `run()`; no such name on the surface |
| Bypass the Kernel | §12.3 | `run()`'s AST calls `authorize`, `attempt` **and** `settle` |
| Import a Worker, Provider or Environment | §6.2 | No `runtime`, `executor`, `orchestrator`, `plugins`, `planner`, `providers`, `ai_infrastructure`, `persistence`, `subprocess`, `socket`, `threading`, `asyncio` |

**Dependency set: `master_agent.foundation.*` and `master_agent.kernel`
only.** Asserted by test — the brief's C1–C15 constraint, enforced rather
than stated.

---

## 6 · Test coverage — 56 tests

The Kernel is **real in every test**, never a double, per §14 R2:
*"tests obtain intents from a real Kernel over an in-memory ledger."*

| Area | Proves |
|---|---|
| **§6.1 sequence** | A complete run settles; the work receives §8.6's token; the ledger reads back intent → attempt → outcome; the work runs only after the intent is durable, observed from inside the work; the receipt returned is the Kernel's own |
| **§11.5 fail closed** | The work is never called on an unknown objective, a suspended Kernel, an unattested request, or a refused attempt write; a refusal is data, not an exception |
| **§3.4 retry loop** | A failed reversible action retries; the loop stops at the warrant's budget; every class is bounded by its own; no counter is held; a success is not retried; one `AttemptRecord` per call, sequenced 1..n |
| **§8.4** | An irreversible action is attempted exactly once; the rule is decided without reading the budget; an irreversible failure escalates; a reversible failure does not; `unknown` is never retried and always escalates; escalation is reported, never raised |
| **§6.3 exceptions** | A raising work settles `unknown`; is never retried; its text is preserved; its intent is still settled; `BaseException` is not swallowed; an interrupted run leaves the intent outstanding |
| **R49 `partial`** | Cannot be settled; is never retried; leaves the intent unsettled — each asserted, none repaired |
| **§4.5 window** | A window closing mid-loop still settles what the last attempt found; a warrant expiring before any attempt settles nothing, which is correct |
| **Boundaries** | The eleven rows of §5 |
| **Structure** | One collaborator, no state; two Coordinators agree; construction refuses a non-Kernel and a non-callable; the surface is one operation; the result is immutable and serialises deterministically, including on the refusal path |

---

## 7 · Quality gates

| Gate | Result |
|---|---|
| C16 tests | **56 passed, 0 failed** |
| C16 + C15 + C9.1 + all foundation suites | **1,404 passed, 1 pre-existing failure** |
| Architecture guards (7 modules run) | **243 passed, 1 skipped, 0 failed** |
| Ruff — C16 source and tests | **All checks passed** |
| Line length | 81 source / 84 tests (limit 100) |
| Size | **70 AST statements** — the Kernel it coordinates is 163 |
| C1–C15 untouched | **0 modified files** in `foundation/`, `ledger/` or `kernel/` |

The single failure is `test_foundation_clock.py::test_only_the_clock_module_reads_the_machines_wall_clock`,
caused by `launcher/boot.py` reading ambient time **in the working copy**.
It is the same pre-existing failure recorded at C15.0, where it was proven
absent at the tag. C16 adds no ambient-time read; the guard's report names
only `boot.py`.

**Adding the package disturbed no guard.** The architecture suites pass
unchanged with `coordinator/` present.

---

## 8 · New findings

### R49 — `partial` reaches a settlement C5 refuses to construct · **Medium**

This is the shipped **R43** seen from the caller's side, and C16 is where
it becomes reachable in ordinary use.

Work that returns `PARTIAL` — §6.3's *"most dangerous outcome"* — reaches
`settle()`, which has no parameter for the compensating action reference
C5 requires. `InvalidReceipt` propagates, and **the warrant stays
outstanding and unsettled**, which §6.3 calls a defect.

**Not caught here.** Swallowing it would turn a loud gap into a silent
one, and the intent would be no more settled for it. Three tests pin the
behaviour and its consequence.

Closing it requires `settle()`'s ratified signature to change — a founder
decision, not engineering work.

### R50 — a raised exception's text has no home in the record · **Low**

**R44** leaves `detail` `None` on every receipt. When work raises, the
sentence describing why has nowhere to go in the permanent record.

It is carried on `Execution.error` so it is not destroyed, but that is an
in-memory value that ends with the call. The ledger holds the outcome
without the sentence.

Diagnostic only — C5 states `detail` is *"never load-bearing and never
read to make a decision"* — so nothing constitutional turns on it.

### R51 — the execution path is not yet unified · **High**

Roadmap §2 C16's other half. Fifteen inventoried entry points across
`orchestrator/`, `executor/`, `runtime/gateway.py`, `runtime/engine.py`,
`ai_infrastructure/execution.py` and `cli.py` still reach tools without a
`warrant_id`, and `LocalExecutor.run()` does not require one.

**Until that migration lands, an alternative route to a tool exists**, and
VEDA 04 R1's *"holes in an audit spine are worse than no spine"* still
applies to those fifteen. §12.3's guarantee — that a future capability
inherits the twenty because *"the alternative does not compile"* — is not
yet true of the existing ones.

C16 as built is the destination, not the migration. §1 states why the
migration was out of scope; it needs a brief that permits touching those
packages.

---

## 9 · Carried, untouched

R34 · R37 · R38 · R39 · R40 · R41 · R43 · R44 · R45 · R46 · R47 · R48 —
unchanged by this component and not solved, per the brief. R43 and R44 are
reached by C16 and their consequences recorded above as R49 and R50; the
underlying gaps are unmodified.

---

## 10 · Preservation

C1–C15 untouched — zero modified files in `foundation/`, `ledger/` or
`kernel/`, measured against the working tree at `kalpavriksha-s1-c15.0`.
The Kernel is consumed exactly as shipped: `authorize`, `attempt`,
`settle` and its two exception types, through their public surface only.

No specification, roadmap, amendment or ADR modified. **No new ADR, no new
constitutional vocabulary, no new runtime dependency, no speculative
API.** C17 not begun. No commit, no tag, no Rule 001.

**STOP.** Awaiting Hermes audit.
