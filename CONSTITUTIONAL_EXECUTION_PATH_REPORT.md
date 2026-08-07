# Constitutional Execution Path Integration Report v1.0

**Type:** Integration and execution governance. No component redesigned. No VEDA modified or reinterpreted.
**Date:** 2026-08-05
**Scope:** Every code path in `src/master_agent/` capable of initiating an effect outside the process.
**Method:** Direct source audit. Every claim below carries a `file:line`. Nothing is inferred from documentation.
**Constitutional inputs:** VEDA 01–04 (frozen) · KALPAVRIKSHA_VISION_V2 §§4, 5.2, 5.7, 10, 12, 15 · ADR-0005, 0011, 0019.
**Excluded:** VEDA 05 (under amendment). Nothing here depends on it.

---

## 1 · Executive Summary

### 1.1 The central finding

The brief anticipated "multiple execution surfaces." The audit found something structurally more significant.

> **Kalpavriksha does not have one execution path with leaks. It has two complete, parallel execution pipelines that share no gate, no ledger, and no approval surface.**

| | **Pipeline 1 — Capability** | **Pipeline 2 — Intelligence** |
|---|---|---|
| **Runs** | Actions that change the world | Provider calls that spend money and send data out |
| **Resolves** | capability → Worker | AI capability → Provider |
| **Path** | Objective → Dispatcher → Runtime → Gateway → Plugin → LocalExecutor → Action | Request → Broker decision → `ai_infrastructure/execution.py` → provider → `transport.py` → network |
| **Gate** | `PermissionSystem` via `PermissionSystemGate` | `ai_infrastructure/approval.py` + `admission.py` + `budgets.py` |
| **Ledger** | `ExecutionLogEntry` + `AuditStream` + `verification/AuditLog` | `ai_infrastructure/ledger.py` |
| **Refusal model** | `ApprovalDenied` | `refusal.py` |
| **Receipt before action** | **None** | **None** |

Both pipelines are individually well-built. Neither is a hack. **But VEDA 04 A1 requires one append-only ledger recording every action's intent before its effect, and there is no point in the system where both pipelines can be observed at once.**

An audit spine that covers one of two pipelines is the condition VEDA 04 R1 rates worse than no spine: it manufactures false confidence. Any future "prove nothing happened without approval" query today returns an answer that is true of half the system.

### 1.2 What is already correct, and must not be disturbed

The audit found substantially better discipline than the brief's premise assumed. These are load-bearing and the migration must preserve them intact:

- **MB028.0 closed the Runtime permission gap.** `RuntimeEngine._require_approval()` ([engine.py:430](src/master_agent/runtime/engine.py:430)) consults the gate before every task and **fails closed with no gate wired** — it refuses everything, not merely everything above `READ_ONLY` ([engine.py:450](src/master_agent/runtime/engine.py:450)). `PermissionSystemGate` also fails closed on an unresolvable risk tier ([approval.py:143](src/master_agent/runtime/approval.py:143)). This is correct and rare.
- **Raw OS access is already behind the contract.** Every `subprocess` call in the tree ([desktop/probe.py:100,125](src/master_agent/desktop/probe.py:100), [ai_infrastructure/executive/probes.py](src/master_agent/ai_infrastructure/executive/probes.py), [executive/actions.py](src/master_agent/ai_infrastructure/executive/actions.py)) sits behind an Action behind a registered `Plugin` with a manifest. There is no loose shell execution anywhere.
- **Execution and Verification are genuinely separate.** `PluginGateway.verify()` returns `None` rather than deriving a verdict from the invoke result ([gateway.py:113](src/master_agent/runtime/gateway.py:113)). ADR-0011 is honoured in code, not just in prose.
- **Mission Control cannot perform work.** `TaskDispatcher` assigns and never invokes ([dispatcher.py:7](src/master_agent/mission_control/dispatcher.py:7)); the coordination Capability Registry holds descriptors, never live objects.
- **The Broker never executes.** `ai_infrastructure/execution.py` is explicit that it decides nothing and never falls back, because a substituted provider would make the `DecisionRecord` a lie.

**None of the above is the problem. The problem is that these guarantees live in five places and no single place can assert them.**

### 1.3 The four structural defects

**D1 · The gate is in the caller, not on the path.** `PluginGateway.invoke()` ([gateway.py:96](src/master_agent/runtime/gateway.py:96)) calls `self._plugin.invoke()` with no permission check. It is safe *only because* `RuntimeEngine` checks first. Any future component that constructs a `PluginGateway` and calls `invoke()` executes with no gate, and nothing fails. The safety is a property of one caller's discipline, not of the path.

**D2 · Execution does not require an objective.** `Orchestrator.execute_capability(capability, payload, step_id="")` ([orchestrator.py:28](src/master_agent/orchestrator/orchestrator.py:28)) has a defaulted, unused-for-authorization `step_id` and no objective parameter at all. **An execution with no objective, no mission, and no plan is trivially constructible today.** The brief's first success criterion is currently unenforceable at the signature level.

**D3 · Retry multiplies one grant into N executions.** `_execute_with_retry()` ([engine.py:362](src/master_agent/runtime/engine.py:362)) loops `gateway.invoke()` up to `max_attempts` times, after exactly one `_require_approval()` call. `PermissionSystem` documents a `ONCE` grant as covering "exactly the one invocation it was given for" ([permission_system.py:68](src/master_agent/permissions/permission_system.py:68)). It does not. VEDA 04 §7 requires every action to be idempotent against its intent record; there is no intent record to be idempotent against.

**D4 · A second scheduler is live, not dead.** `Orchestrator.execute_plan()` documents itself as "**Not the mission path**" and warns that "a second scheduler would be a second orchestration authority" ([orchestrator.py:63](src/master_agent/orchestrator/orchestrator.py:63)) — yet [cli.py:807](src/master_agent/cli.py:807) calls it. The comment describes an intention; the call graph describes reality.

### 1.4 The recommendation in one sentence

> **Do not merge the two pipelines. Converge them at a single Constitutional Gate that both must call, and make the gate structurally impossible to skip — by making the thing an Action needs in order to run something only the gate can produce.**

This preserves the Broker, the Permission System, the Objective Engine, and the Learning loop exactly as designed. It is an integration, not a redesign, and §3 shows why merging the two pipelines would be the wrong answer.

---

## 2 · Current Execution Inventory

Complete. Every site in `src/master_agent/` capable of initiating an effect outside the process.

### 2.0 The scoping rule used

VEDA 04 defines an **Action** as *anything that changes state outside the system*. This audit applies that literally, which excludes the system's own durable state — a snapshot write ([persistence/store.py:132](src/master_agent/persistence/store.py:132)), a knowledge write ([memory/knowledge_store.py:215](src/master_agent/memory/knowledge_store.py:215)), a ledger write ([ai_infrastructure/ledger.py:754](src/master_agent/ai_infrastructure/ledger.py:754)), a mission history write ([missions/history.py:365](src/master_agent/missions/history.py:365)).

**These are named here so their exclusion is a decision rather than an oversight.** They are the system recording itself. A receipt for writing a receipt is an infinite regress. They are in scope for §7's integrity checks, not for the execution gate.

### 2.1 Pipeline 1 — Capability execution

| # | File | Class · Function | Purpose | Current caller | Bypass risk | Recommendation |
|---|---|---|---|---|---|---|
| **E1** | `orchestrator/orchestrator.py:28` | `Orchestrator.execute_capability()` | Resolve capability → check permission → invoke plugin | `execute_step()`, tests | **Medium.** Gated, but takes no objective (D2) and writes no receipt. Public and callable by anything holding a registry. | **Becomes the Constitutional Gate.** Signature gains a mandatory execution context. |
| **E2** | `orchestrator/orchestrator.py:60` | `Orchestrator.execute_step()` | Adapt a `Step` to E1 | `execute_plan()` | Low — pure delegation | Keep as a thin adapter |
| **E3** | `orchestrator/orchestrator.py:63` | `Orchestrator.execute_plan()` | Walk a plan in list order, stop at first problem | **[cli.py:807](src/master_agent/cli.py:807) — live** | **High.** A second orchestration authority, self-documented as such, still wired to the CLI (D4). Bypasses the dependency graph, Mission Control state, verification, and the event stream. | **Deprecate.** Relocate into the demo entry point or delete. Must not survive Phase 1. |
| **E4** | `runtime/gateway.py:96` | `PluginGateway.invoke()` | Perform one capability call | `RuntimeEngine._execute_with_retry()` | **Critical.** No internal permission check (D1). `grant_permission` *issues* a grant; it does not check one. Docstring concedes that with `None` it "relies on approval having been arranged some other way." | **Becomes a wrapper over the Gate.** It must not be able to reach a plugin directly. |
| **E5** | `runtime/engine.py:362` | `RuntimeEngine._execute_with_retry()` | Bounded mechanical retry | `_handle_task()` | **High.** N executions per grant (D3); no idempotency key. | Retry must carry the original intent id; each attempt writes its own outcome record against one intent. |
| **E6** | `runtime/engine.py:290` | `RuntimeEngine._handle_task()` | Gate → execute → verify → report | Runtime loop | Low — this is the compliant path | Keep. It becomes the reference implementation. |
| **E7** | `executor/executor.py:106` | `LocalExecutor` → `action.run()` | The innermost door: run one validated Action | Every plugin adapter | **Critical.** Public and reachable by any holder of an executor. Nothing here knows about objectives, permissions, or receipts. | **Becomes the enforcement point of last resort.** Refuses to run without a receipt intent id. |
| **E8** | `plugins/*.py`, `desktop/plugin.py`, `ai_infrastructure/executive/plugin.py` | `Plugin.invoke()` × 7 plugins | Adapt capability → Action, relay grant (ADR-0005) | Orchestrator, Gateway, tests | **High.** The `Plugin` contract is public. Any holder of a plugin object executes with no gate. | Left structurally unchanged; protected by E7's refusal. |
| **E9** | `desktop/probe.py:100,125` | `SystemProbe.run()` / `Popen` | Raw OS command execution | `desktop/actions.py:373,418`, `inventory.py:180` | **Medium.** Behind Actions behind `DesktopPlugin` — structurally compliant. Risk is that `probe.run()` is importable and reachable without an Action. | Mark internal; assert by import test that only `desktop/` reaches it |
| **E10** | `ai_infrastructure/executive/probes.py` (×6), `actions.py` (×4) | `subprocess.run` | Probe, benchmark, install providers | `AiInfrastructurePlugin` | **Medium.** Same shape as E9. Note `actions.py` performs **installation** — the highest-consequence local action in the system. | Same as E9. Verify installation is classified `IRREVERSIBLE`. |
| **E11** | `desktop/actions.py:373` | process kill via `_kill_command` | Terminate a process | `DesktopPlugin` | **Medium.** Irreversible, no compensating action exists. | Must be classified `IRREVERSIBLE` with no compensating action declared — fails closed rather than pretending |

### 2.2 Pipeline 2 — Intelligence execution

| # | File | Class · Function | Purpose | Current caller | Bypass risk | Recommendation |
|---|---|---|---|---|---|---|
| **E12** | `ai_infrastructure/execution.py` | Broker-decision execution | Locate the chosen provider, execute, record to the AI ledger | Planner, launcher, workers needing intelligence | **Critical.** A complete second pipeline: own approval, own admission, own budgets, own ledger, own refusal model. Invisible to Pipeline 1's audit. | **Must call the same Constitutional Gate.** Its internal resolution logic stays exactly as designed. |
| **E13** | `providers/transport.py:133,168` | `urlopen` | HTTP egress | `providers/ollama.py:198,254,372` | **High.** The only network egress point in the tree. Local Ollama is `localhost`; the same transport serves any cloud provider — where a call spends money and sends founder data to a third party. | Classify provider calls as Actions. Route through the Gate. |
| **E14** | `planner/planner.py:184` | `self._runner.run(prompt, request, ...)` | The Brain asks a provider to plan | `Planner.plan()` | **Medium.** A Brain-side call to an external service, outside Pipeline 1 entirely. Correctly consults the Broker; produces no receipt. | Gate at E12, not here. The Planner should not change. |
| **E15** | `launcher/main.py:214` | `system.prompt_executor.run(...)` | Launcher-time provider call | Boot sequence | Medium. Same class as E14, earlier in the lifecycle — possibly before the Gate is wired. | Gate at E12. Boot ordering verified by §7 test L5. |

### 2.3 Coordination surfaces — audited and cleared

| Site | Finding |
|---|---|
| `mission_control/dispatcher.py:139` `dispatch_ready()` | Assigns and marks `DISPATCHED`. **Invokes nothing.** Correct as designed. |
| `mission_control/mission_control.py:184` | Delegates to the above. Correct. |
| `runtime/engine.py:287` | Calls `dispatch_ready`, receives assignments. Correct. |

**These are not execution entry points and must not be treated as such.** Mission Control being unable to perform work is a load-bearing property.

### 2.4 Inventory summary

| | Count |
|---|---|
| Execution entry points (Pipeline 1) | **11** |
| Execution entry points (Pipeline 2) | **4** |
| Registered plugins | 7 |
| Action implementations | ~32 |
| Risk-tier declarations | 48 (`READ_ONLY` 25 · `REVERSIBLE_WRITE` 17 · `IRREVERSIBLE` 6) |
| Compensating actions declared | **0** |
| Receipt-intent writes | **0** |
| Execution paths requiring an objective | **0** |

---

## 3 · Canonical Execution Pipeline

### 3.1 Two corrections to the proposed pipeline

The brief's chain is `Objective Engine → Permission Engine → Tool Broker → Execution → Receipt → Learning`. Two changes are required by what the codebase actually is. Both are stated so the deviation is deliberate.

**Correction 1 — The Broker is not on the path of every action.** In this codebase the Broker resolves *AI capability → Provider* ([broker/](src/master_agent/broker/), Constitution §5.7). `Filesystem.CreateFolder` needs no provider. Placing the Broker inline for every action would make a singular, spend-atomic component the hottest path in the system for no benefit, and would contradict §5.7's own boundary — it "must be consulted *before* dispatch, so cannot be a thing that is dispatched."

**Resolution:** the pipeline forks at *resolution* and rejoins at the Gate. Capability resolution asks the Capability Registry; intelligence resolution asks the Broker. Both then pass the same gate.

**Correction 2 — Learning is downstream of the receipt, not inline.** VEDA 04 Eng. Law V: *inference generates proposals; only permission generates actions.* An inline learning call would put a component that must never act on the critical path of every action, and a learning failure would block execution. Learning **subscribes to the receipt stream**.

**Resolution:** Learning is fed by A1, asynchronously, and can never delay or block an action.

### 3.2 The canonical pipeline

```
   FOUNDER
      │
      ▼
   VEDRA ─ the only voice. Narration in, judgment out.
      │
      ▼
   OBJECTIVE ENGINE ─ admits, decomposes, holds the contract
      │                Every unit of work below carries its objective_id.
      ▼
   MISSION CONTROL ─ dependency order, assignment. Invokes nothing.
      │
      ▼
   RUNTIME ─ picks up an assigned task
      │
      │   ╔═══════════════════ RESOLUTION FORK ═══════════════════╗
      │   ║  The two arms answer different questions. Neither      ║
      │   ║  arm may execute. Both must call the Gate.             ║
      ├──►║                                                        ║
      │   ║  ARM A · CAPABILITY          ARM B · INTELLIGENCE      ║
      │   ║  Capability Registry         AI Capability Broker      ║
      │   ║  capability → Worker         ai capability → Provider  ║
      │   ║  (Constitution §5.1)         (Constitution §5.7)       ║
      │   ╚════════════════┬───────────────────┬═══════════════════╝
      │                    └─────────┬─────────┘
      ▼                              ▼
╔══════════════════════════════════════════════════════════════════════╗
║             THE CONSTITUTIONAL GATE — one, and only one              ║
║                                                                      ║
║   1. REQUIRE CONTEXT ── objective_id present, or refuse              ║
║                         (closes D2 at the signature)                 ║
║   2. CLASSIFY ───────── Reversibility Registry. Unclassified ⇒       ║
║                         non-executable. Fails closed.                ║
║   3. AUTHORIZE ──────── Permission System. Above READ_ONLY needs a   ║
║                         grant. IRREVERSIBLE needs a contemporaneous  ║
║                         one — no standing rule ever suffices.        ║
║   4. RECEIPT INTENT ─── written BEFORE any effect. If the write      ║
║                         fails, the action does not occur. No         ║
║                         exceptions, no buffering. Returns intent_id. ║
║                                                                      ║
║   ── nothing below this line runs without an intent_id ──            ║
║                                                                      ║
║   5. EXECUTE ────────── the Worker's Action, or the Provider call    ║
║   6. RECEIPT OUTCOME ── against the same intent_id. Retries reuse    ║
║                         it; they never mint a second. (closes D3)    ║
╚═════════════════════════════════┬════════════════════════════════════╝
                                  │
                                  ▼
                     VERIFICATION ─ re-observe, compare to
                     Expected Outcome, produce Evidence.
                     Never derived from the execution result.
                     (ADR-0011, unchanged)
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
            MISSION CONTROL              A1 RECEIPT LEDGER
            task_completed /             append-only, the single
            task_failed                  record of what happened
                    │                           │
                    ▼                           ▼ (subscribers, async)
            OBJECTIVE COMPLETION      ┌─────────────────────────┐
                    │                 │ LEARNING · BOUNDARY ·   │
                    ▼                 │ SELF-AUDIT · DASHBOARD  │
                 VEDRA                │ Read only. Never block. │
                 narrates             │ Never act. (Eng. Law V) │
                                      └─────────────────────────┘
```

### 3.3 The invariant that makes it enforceable rather than aspirational

A documented pipeline is a convention. A convention survives about two years of pressure. The following makes it structural:

> **`LocalExecutor.run()` and the provider execution call require an `intent_id`. Only the Gate can produce one. There is no other constructor, no default, and no test-only bypass.**

A future capability that tries to execute directly cannot — not because a reviewer catches it, but because it has nothing to pass. This is the difference between a rule and a type, and it is the only mechanism in this report that is still working in five years without anyone remembering why it is there.

**Corollary:** `PluginGateway` (E4) and `Plugin.invoke()` (E8) remain public and unchanged in shape. They no longer need their own gates, because the door they ultimately reach refuses to open.

---

## 4 · Compliance Matrix

Assessed against the five constitutional obligations. **Objective** — traceable to an admitted objective. **Permission** — gated above READ_ONLY. **Receipt** — intent before effect. **Audit** — recorded in a queryable history. **Learning** — feeds the loops.

| # | Path | Objective | Permission | Receipt | Audit | Learning | Verdict |
|---|---|---|---|---|---|---|---|
| E1 | `Orchestrator.execute_capability` | ✗ | ✓ | ✗ | ~ | ✗ | **Partial** |
| E2 | `Orchestrator.execute_step` | ~ | ✓ | ✗ | ~ | ✗ | **Partial** |
| E3 | `Orchestrator.execute_plan` | ✗ | ✓ | ✗ | ✗ | ✗ | **Non-compliant** |
| E4 | `PluginGateway.invoke` | ✗ | **✗** | ✗ | ✗ | ✗ | **Non-compliant** |
| E5 | `_execute_with_retry` | ✓ | **~** | ✗ | ✓ | ✗ | **Non-compliant** |
| E6 | `RuntimeEngine._handle_task` | ✓ | ✓ | ✗ | ✓ | ✗ | **Partial** — best in system |
| E7 | `LocalExecutor` → `action.run` | ✗ | ✗ | ✗ | ~ | ✗ | **Non-compliant** |
| E8 | `Plugin.invoke` ×7 | ✗ | ~ | ✗ | ✗ | ✗ | **Non-compliant** |
| E9 | `SystemProbe.run` | ✗ | ~ | ✗ | ~ | ✗ | **Partial** |
| E10 | AI-infra probes/actions | ✗ | ~ | ✗ | ~ | ✗ | **Partial** |
| E11 | process kill | ✗ | ~ | ✗ | ~ | ✗ | **Partial** |
| E12 | `ai_infrastructure/execution` | ~ | **≠** | ✗ | **≠** | ✓ | **Non-compliant** |
| E13 | `transport.urlopen` | ✗ | ✗ | ✗ | ~ | ~ | **Non-compliant** |
| E14 | `planner._runner.run` | ~ | **≠** | ✗ | **≠** | ✓ | **Partial** |
| E15 | `launcher prompt_executor` | ✗ | **≠** | ✗ | **≠** | ~ | **Non-compliant** |

`✓` satisfied · `~` partially or by the caller's discipline rather than the path's · `✗` absent · `≠` **satisfied by a parallel mechanism, not the constitutional one**

### 4.1 Reading the matrix

**Nothing is fully compliant, because the Receipt column is empty everywhere.** A1 does not exist. That is a known, scheduled gap, not a defect introduced by any of these paths.

**The `≠` column is the real finding.** E12, E14, and E15 *do* have approval and *do* have an audit ledger — just not the constitutional ones. They are governed, but by a second government. This is worse than being ungoverned in one specific way: it looks compliant from inside Pipeline 2 and looks absent from inside Pipeline 1, so neither view reveals it.

**Three paths where permission is satisfied by the caller, not the path** — E4, E8, E9/E10 — are the ones that will silently break. They are correct today because exactly one caller does the right thing. The first second caller is a regression that no test currently detects.

**E5 is the only path where the permission column is wrong under load rather than under refactoring.** Three retries against one `ONCE` grant is a live semantic breach, today, in shipped code.

---

## 5 · Refactoring Plan

No implementation code. Module-level disposition only.

### 5.1 Modules that must change

| Module | Change | Why | Blast radius |
|---|---|---|---|
| `orchestrator/orchestrator.py` | `execute_capability()` becomes the **Constitutional Gate**: mandatory execution context, classify → authorize → receipt intent → execute → receipt outcome | It is already the only place that resolves *and* gates. It is 83 lines. It is the correct home. | High — but the file is small and fully tested |
| `executor/executor.py` | `LocalExecutor.run()` requires an `intent_id` and refuses without one | The enforcement point of last resort (§3.3) | **Highest** — every Action reaches it. This is deliberate: one refusal covers all 32. |
| `runtime/gateway.py` | `PluginGateway` becomes a **wrapper over the Gate** rather than a direct caller of `plugin.invoke()` | Closes D1 permanently | Medium — one class, one method |
| `runtime/engine.py` | `_execute_with_retry()` carries the intent id through all attempts | Closes D3 | Low — one method |
| `ai_infrastructure/execution.py` | Calls the Gate for classification, authorization, and receipt. **Keeps all Broker, admission, budget, and refusal logic exactly as designed.** | Converges Pipeline 2 without redesigning it | Medium |
| `providers/transport.py` | Provider calls declared as Actions with a reversibility class | Network egress becomes visible to the spine | Low |
| `cli.py` | Stops calling `execute_plan()` | Closes D4 | Low — one call site |

### 5.2 Modules that stay untouched

**These are correct. Changing them is the failure mode of this kind of work.**

`mission_control/*` — cannot perform work; that property is load-bearing
`broker/*` — decides and never touches the machine; §5.7 boundary intact
`permissions/permission_system.py` — the grant ledger; C1 subsumes it later, not now
`verification/*` — ADR-0011 separation is honoured in code
`plugins/base.py`, all 7 plugin adapters — the contract is right; protection moves below them
`executor/actions/**` (32 Actions) — **not one Action changes.** They gain a class declaration in the registry, not a code edit.
`desktop/probe.py`, `ai_infrastructure/executive/*` — structurally compliant already
`memory/*`, `persistence/*`, `dashboard/*`, `planner/*`, `missions/*`

### 5.3 Modules that become deprecated

| Module | Disposition | Timing |
|---|---|---|
| `Orchestrator.execute_plan()` | **Delete or relocate to the demo entry point.** A second orchestration authority its own docstring warns against. | Phase 1 |
| `PluginGateway.grant_permission` parameter | **Remove.** It *issues* a grant immediately before invoking — the inverse of a gate. Once the Gate authorizes, relaying a grant downward is ADR-0005's job, not a constructor parameter's. | Phase 2 |
| `mission_manager/` (86 lines, unwired) | Pending the `Objective`/`Mission` ADR. **Write no new consumer.** | Blocked on ADR |

### 5.4 Modules that become wrappers

| Module | Wraps | Keeps |
|---|---|---|
| `PluginGateway` | The Gate | Its `Protocol` shape, its verify/invoke split, its Executive-agnosticism |
| `Plugin.invoke()` ×7 | Unchanged shape; protected from below | ADR-0005 grant relay |
| `ai_infrastructure/execution.py` | The Gate for authorize + receipt | Broker resolution, admission, budgets, cache, ledger, no-fallback rule |

### 5.5 Dependency impact

| Module | New dependency | Risk | Required validation |
|---|---|---|---|
| `orchestrator/` | Reversibility Registry, Receipt Ledger | **Central chokepoint.** A slow ledger makes the whole product slow (VEDA 04 §7). | Latency budget test on the gate path |
| `executor/` | `intent_id` in its signature | Touches all 32 Actions' call sites — though not their bodies | Full existing suite green with zero Action edits |
| `runtime/` | Nothing new — it already consults a gate protocol | Low. Retry semantics change. | Retry test: N attempts, one intent, N outcome records |
| `ai_infrastructure/` | The Gate | **Highest coupling risk** — two governance models meeting. | Assert the AI ledger and the receipt ledger agree on every call |
| `providers/` | Action classification | Low | Egress test: no `urlopen` without a preceding intent |
| `cli.py` | Mission Control path instead of `execute_plan` | Medium — user-visible behaviour | Miracle 001 and 003.1 regression |
| `plugins/`, `desktop/`, `verification/`, `mission_control/`, `broker/` | **None** | — | Existing suites unchanged |

---

## 6 · Migration Plan

Five phases. Constraints: **no Miracle breaks, no test breaks, no duplicate implementation exists at any point.**

### Phase 0 · Census — prove the inventory is complete

No production code changes.

- Add `test_execution_paths.py`: assert the set of modules importing `Plugin`, `LocalExecutor`, or `ExecutiveGateway` equals an explicit allowlist. **Any new importer fails the build.**
- Assert no `subprocess`, `urlopen`, or `shutil` import exists outside the allowlisted modules.
- Record the current call graph as a committed fixture.

**Gate:** the allowlist matches §2 exactly. If it does not, §2 was incomplete and this report is amended before proceeding.
**Miracle risk:** zero. Tests only.

### Phase 1 · Close the two open doors

- `cli.py` stops calling `execute_plan()`; the CLI routes through Mission Control as MB037 already intended.
- `execute_plan()` relocated to the demo entry point or deleted.
- Reversibility classification audit across all ~30 capabilities: every one declares a class; every reversible one declares a **compensating action**; unclassified is non-executable.

**Gate:** one orchestration authority. Every capability classified. Registry fails closed.
**Miracle risk:** Miracles 001, 003.1, 005 exercise the CLI path. Run them explicitly before and after.
**No duplication:** `execute_plan` is removed in the same commit that re-points `cli.py`.

### Phase 2 · Erect the Gate, keep both doors open

The only phase with a temporary parallel path, so it is the shortest.

- `Orchestrator.execute_capability()` gains the mandatory execution context and the four gate steps.
- `LocalExecutor.run()` accepts an `intent_id` **as optional**, and logs a loud warning when absent.
- `PluginGateway` re-pointed at the Gate.
- `_execute_with_retry()` threads the intent id.

**Gate:** every Pipeline 1 execution produces a receipt pair. The warning count for absent `intent_id` is zero in a full test run.
**Miracle risk:** medium — this is the invasive commit. Mitigated by `intent_id` being optional for exactly one phase.
**No duplication:** the old ungated route still exists but is unused, and is measured — the warning count is the proof.

### Phase 3 · Converge Pipeline 2

- `ai_infrastructure/execution.py` calls the Gate for classification, authorization, and receipt. Broker resolution, admission, budgets, cache, and the no-fallback rule are untouched.
- Provider calls classified as Actions.
- The AI ledger becomes a **projection of, or a feeder into, the receipt ledger** — never a peer.

**Gate:** every provider call appears in the receipt ledger. The two ledgers reconcile exactly, asserted by test.
**Miracle risk:** Miracles 027, 031, 032, 033 are all Broker work. Their suites must stay green untouched — that is the proof that convergence is not redesign.
**No duplication:** this phase *removes* the second governance model; it adds nothing.

### Phase 4 · Close the door behind us

- `LocalExecutor.run()` makes `intent_id` **mandatory**. No default, no test bypass.
- Remove `PluginGateway.grant_permission`.
- Phase 0's allowlist test is upgraded: any module reaching an Action other than through the Gate fails the build.

**Gate:** §7's full verification suite passes. Bypass is not merely absent — it is unconstructable.
**Miracle risk:** low. By this point every path already supplies an intent id; making it required proves it.
**No duplication:** the last alternative route is deleted in the same commit that makes the parameter mandatory.

### 6.1 Order rationale

Phase 1 before Phase 2 because closing a known door is cheaper than gating it. Phase 2 before Phase 3 because Pipeline 1 is the reference implementation Pipeline 2 converges onto — building the Gate against the harder pipeline first would design it around the exception. Phase 4 last because a mandatory parameter is only safe once every caller supplies it, and Phase 3's reconciliation test is what proves they do.

---

## 7 · Verification Plan

Five layers. Each proves something the others cannot. **Layers 1–3 are static and cheap; layer 4 is the one that holds for five years.**

### L1 · Import boundary — *no new door can be opened*

Assert the exact set of modules importing `Plugin`, `LocalExecutor`, `ExecutiveGateway`, `subprocess`, `urlopen`, or `shutil`. Build-breaking on change.
**Proves:** no new execution surface appears without a deliberate allowlist edit that a reviewer must see.
**Does not prove:** that allowlisted modules behave.

### L2 · Signature enforcement — *the door cannot open without a key*

`LocalExecutor.run()` and provider execution require an `intent_id` that only the Gate produces. No default, no `Optional`, no test-only constructor.
**Proves:** bypass is a type error, not a policy violation.
**This is the load-bearing layer.** If only one layer survives the next five years of refactoring, it must be this one.

### L3 · Classification coverage — *fails closed*

Every registered capability resolves to a reversibility class; every reversible one names a compensating action; an unclassified capability is non-executable. Enumerated from the registry, not from a hand-maintained list.
**Proves:** the surface cannot grow past its own governance.

### L4 · Adversarial bypass suite — *every known route is tested as a refusal*

One test per entry point in §2, each attempting the bypass and asserting refusal:

- construct a `PluginGateway` with no gate → invoke → must refuse
- hold a `FilesystemPlugin` → `invoke()` directly → must refuse
- call `LocalExecutor.run()` with a fabricated intent id → must refuse
- execute with no `objective_id` → must refuse
- retry three times → assert **one** intent record and **three** outcome records
- provider call outside the Gate → must refuse
- `IRREVERSIBLE` capability with an `ALWAYS_FOR_CAPABILITY` grant → must refuse

**Proves:** the specific historical routes are closed, and stay closed. **This suite grows by one test per entry point discovered forever** — it is the institutional memory of this audit.

### L5 · Reconciliation — *the two ledgers agree*

For any window: every AI-ledger entry has a receipt; every receipt for a provider capability has an AI-ledger entry; counts and costs match. Asserted continuously, not on demand — VEDA 04 R3 requires exactly this for cumulative accounting.
**Proves:** Pipeline 2 did not quietly re-diverge.

### 7.1 The standing question

Any future component claiming it needs its own execution path must answer:

> **What does it need to do that the Gate cannot authorize, classify, and receipt?**

Every honest answer to date has been "nothing" — the two pipelines diverged because they were built at different times for different reasons, not because the Gate could not serve both. **Recording that question here is the mechanism by which the third pipeline does not get built.**

---

## 8 · Risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| **1** | **Phase 2 breaks a Miracle.** The Gate change touches the path every shipped capability uses. | **Critical** | `intent_id` optional for exactly one phase. Miracles 001, 002, 003, 003.1, 005 re-run explicitly as acceptance, not just as suite membership. |
| **2** | **The Gate becomes a latency bottleneck.** Every action now writes a durable record before executing — VEDA 04 §7 warns a slow ledger makes the product slow everywhere. | **High** | Latency budget measured from Phase 2, not discovered. The ledger write is append-only and local; if it cannot meet budget, that is a storage decision, never a reason to make the write optional. |
| **3** | **Pipeline 2 convergence is mistaken for Broker redesign.** The Broker is ratified (ADR-0017/0018) and its boundary is precise. Touching `ai_infrastructure/execution.py` invites scope creep into decision logic. | **High** | Explicit: only classification, authorization, and receipt are added. **The Broker suites must stay green untouched — that is the acceptance criterion for "not a redesign."** |
| **4** | **A third pipeline appears.** Nothing structural prevented the second one; the same forces persist. | **High** | L1 + L4 + the §7.1 standing question. |
| **5** | **The `intent_id` gets a default "for testing."** The most likely single cause of this entire report being obsolete in three years. | **High** | No default at any privilege level. Tests obtain intent ids from a real Gate against an in-memory ledger. **A test-only bypass is a production bypass with a comment on it.** |
| **6** | **Receipt volume.** Every action, both pipelines, forever, append-only and permanent (VEDA 04 M1 — retention is a trust obligation, not a cost decision). | Medium | Declare the store's lifetime now. Design for append-only growth from the first write; retrofitting compaction onto an immutable ledger is a rewrite. |
| **7** | **The classification audit is rushed.** ~30 capabilities including process-kill and provider-install. Every misclassification is a potential irreversible action taken automatically. | Medium | Classify pessimistically. `IRREVERSIBLE` with no compensating action is a valid and expected outcome — E11 process-kill is exactly that. Upgrade a class only on evidence of a *working* compensating action. |
| **8** | **Retry semantics are subtly wrong.** One intent, N outcomes is the correct shape; N intents or one outcome are both wrong and both plausible. | Medium | L4's explicit retry test, written before the change. |
| **9** | **Boot-order gap.** `launcher/main.py:214` executes during boot, possibly before the Gate is wired. | Medium | L5 boot test: no execution occurs before the Gate exists; a Runtime with no gate already refuses everything, and the launcher must adopt the same posture. |
| **10** | **The report is read as permission to refactor `mission_control/` or `verification/`.** Both are correct and both are adjacent to the work. | Medium | §5.2 is explicit. A diff touching them is out of scope by definition. |

---

## 9 · Final Recommendation

### 9.1 Approve, and start with Phase 0

The census costs nothing, changes no production code, and either confirms this inventory or reveals that it is incomplete. **Every later phase depends on §2 being exhaustive, and only a machine-checked allowlist proves that.** Beginning anywhere else means building a gate without knowing how many doors exist.

### 9.2 The three decisions that outlive the migration

**One · Converge, do not merge.** The two pipelines answer different resolution questions and both answers are correct. Merging them would redesign the Broker, which is ratified and out of scope. Converging them at classification, authorization, and receipt makes them one governed system while leaving both designs intact.

**Two · Enforce with a type, not a rule.** `LocalExecutor.run()` requiring an `intent_id` only the Gate can produce is the single mechanism in this report that still works when everyone who wrote it has forgotten why. Documentation decays, reviews miss things, conventions bend under deadline. **A missing required argument does none of those.**

**Three · Keep the bypass suite forever.** L4 grows by one test per entry point discovered, permanently. It is the only artifact that remembers this audit happened. In five years, when someone proposes a direct execution path for a good reason, that suite is what makes the cost visible before the commit rather than after the incident.

### 9.3 What this guarantees, and what it does not

**Guaranteed after Phase 4:**

| Success criterion | Mechanism |
|---|---|
| Cannot execute without an objective | Mandatory execution context on the Gate signature (L2) |
| Cannot execute without permission | Gate step 3; unreachable except through the Gate (L1 + L2) |
| Cannot execute without a receipt | Gate step 4; `intent_id` required by `LocalExecutor` (L2) |
| Cannot bypass auditing | One ledger, both pipelines, reconciled continuously (L5) |
| Cannot bypass learning | Learning subscribes to the receipt stream; a receipt cannot be skipped, so learning cannot be starved |

**Not guaranteed, and stated plainly:**

The receipt ledger (A1) does not exist yet. This report establishes the **path** through which every action must flow and the **point** at which the receipt is written. It does not build the ledger — that is Phase 0 of the Implementation Blueprint. **Until A1 ships, the Gate can classify and authorize but writes its intent to a stub.**

That is the correct order. A gate with a stub ledger is a gate with one unimplemented step. A ledger with no gate is a ledger with holes, and VEDA 04 R1 is unambiguous about which of those is worse.

### 9.4 The five-year test

> **In 2031, with hundreds of capabilities and components nobody currently imagines, a developer adding a new capability will not need to know this document exists. They will write an Action, register it, declare its reversibility class — and discover that it cannot run without an `intent_id` they can only obtain from the Gate.**

They will not read about the constitutional path. They will be unable to avoid it. That is the only form of architectural governance that survives its authors, and it is the entire purpose of this report.

---

*Integration report. No component redesigned, no VEDA modified. Every execution site cited by `file:line` and verified against `src/master_agent/` as of 2026-08-05. Where an existing mechanism is already correct, it is named as correct and placed out of scope rather than absorbed into the change.*
