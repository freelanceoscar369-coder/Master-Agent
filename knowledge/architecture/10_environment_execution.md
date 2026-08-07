# Environment Execution

## Purpose
Documents the execution-layer patterns for Environment interaction — how Workers execute capabilities against concrete Environment Instances through Environment Sessions. Based on the reference Browser Worker implementation and Filesystem capabilities pattern.

---

## Frozen Constitution

### Constitution §4 (Universal Executive Operator — FROZEN)
> The **Universal Executive Operator** carries out what the Brain decided, with full accountability. It **never decides, never plans, and never holds an opinion about *why* a Step exists — only *how* to run it safely and *whether it actually worked*.**

### Constitution §4.3 (Verification Subsystem — FROZEN)
> See §10. Runs alongside the Operator (it needs Environment access, which only the Operator has) but through its own contract, never through a Worker's `invoke()`.

### Constitution §7 (Universal Environment Philosophy — EVOLVABLE)
> **7.1 Local-First Is Not Optional** — System boots, plans, executes with purely local Reasoning Provider and local Memory.
> **7.2 Environment as an Abstract Category** — Desktop, Browser, Terminal, VPS, Robotics/IoT — never a specific product.
> **7.3 No Environment Assumptions in Core** — No hardcoded paths (locations injected via configuration §5.5). No product-specific logic in core modules. No assumption about process lifetime.
> **7.4 Environment vs. Environment Instance** — "Environment" = category. "Environment Instance" = one concrete, live, addressable target.

### Constitution §8 (Multi-Operator Architecture — RESEARCH-BACKED)
> **8.2 Operator Instance** — One running instance of the Operator, bound to one (or tightly-coupled set of) Environment Instance(s). Tracked by Operator Registry (Shared Infrastructure §5.1).
> **8.3 Environment Instance and Environment Session** — Environment Instance = concrete target. Environment Session = live handle an Operator Instance holds to one Environment Instance. **Owned by exactly one Operator Instance; never Shared Infrastructure (§5.8).**

### Constitution §10 (Verification Philosophy — RESEARCH-BACKED)
> **10.2 Three-Part Boundary:**
> 1. **Execution produces effects** — Worker's Action runs, returns Execution Result. Says nothing about real-world outcome.
> 2. **Verification produces Evidence** — Verification Subsystem re-observes Environment Instance, compares Observation against Expected Outcome. Output = Verdict + Observation + Expected Outcome = **Evidence**.
> 3. **Evidence flows back to Brain** — routed via Shared Infrastructure as input to "is Mission complete?"

> **10.3 Why Verification stays physically near Operator but architecturally separate:** Only Operator has Environment access. Verification uses its own contract — "observe, then compare against Expected Outcome" — never reuses Worker's `validate()`/`run()`, never folds result into plain Execution Result.

### Constitution §12 (Worker and Plugin Runtime — IMPLEMENTATION DETAIL)
> **12.2 Workers are Capabilities' implementations** — Every Capability implemented by a Worker registered on Operator's Worker Runtime. Adding Worker #N costs one new file; never edits Registry, Permission System, Orchestrator.
> **12.3 Composite Workers** — May orchestrate other Workers through Capability Registry and Permission System, relaying already-obtained grant down to each sub-step (Rule 6).

---

## Architecture Design

### 1. Worker Contract Pattern (from `BROWSER_WORKER_ARCHITECTURE.md` §3, `FILESYSTEM_CAPABILITIES.md` §1)
Each Environment capability = **one Action class** implementing the Action Contract (`executor/action.py`):
- `name`, `description`, `risk_tier`, `permission_category`, `expected_result`
- `required_parameters()` → `list[str]`
- `validate(parameters)` → `list[str]` (pure, no side effects, no filesystem touch)
- `run(parameters)` → `ExecutionResult(success, output, errors, warnings, execution_time_seconds)`

**No god-class with `operation` switch** — each Action = one clearly-scoped effect.

### 2. Environment Session Pattern (from `BROWSER_WORKER_ARCHITECTURE.md` §4)
**Problem:** Action contract is one-shot (`validate()` → `run()`); Browser/Terminal/Robotics need live handle across multiple Steps.

**Solution:** **Environment Session Manager** (per Operator Instance) + **Environment Session** (live handle).
- `BrowserSessionManager` (one per Operator Instance, per §8.2)
  - `session_id` → `BrowserSession`
  - `BrowserSession` owns: Playwright instance, Browser, BrowserContext, Page
  - Never exposed outside Worker's own modules
- Actions needing open page take `session_id` in payload, resolve through injected Manager
- Action itself **never stores session state** between calls — stays stateless like all Actions

**Deliberately NO generic `EnvironmentSessionManager[T]` base class yet** — one concrete example doesn't justify abstraction (same as ADR-0005/0006 relay pattern). Shape written so second Worker (Terminal) can copy directly.

### 3. Verification Independence (from `BROWSER_WORKER_ARCHITECTURE.md` §8, §10)
**Generic Verification Package** (`verification/`) — zero Environment imports:
- `Verifier` ABC with `capture_observation_dict()` (abstract) + `verify(expected)` (concrete)
- `ExpectedOutcome`, `ObservationCheck`, `Verdict`, `Evidence`, `AuditRecord`, `AuditLog`
- `evaluate_checks()` — pure function, no I/O

**BrowserVerifier** implements only `capture_observation_dict()` using `normalize_observation()`.

**Key principle:** `Verifier.verify()` **never reads `ExecutionResult`** — always re-observes reality fresh. Execution success ≠ verification success.

### 4. Observation Normalization (from `BROWSER_WORKER_ARCHITECTURE.md` §7)
Single function `normalize_observation(page, selectors, include_accessibility_tree, include_available_actions)` → `BrowserObservation`:
- Only function besides Actions touching Playwright `Page`
- Called by both `ObserveBrowserAction.run()` and `BrowserVerifier.capture_observation_dict()`
- `BrowserObservation.as_dict()` = generic, Playwright-free view crossing into Evidence machinery

**Five facets:**
| Facet | Source | Always on? |
|-------|--------|------------|
| Current page | `page.url`, `page.title()` | Yes |
| Viewport | `page.viewport_size` | Yes |
| DOM state / visible elements | Best-effort `BrowserElement` per selector | Yes (for asked selectors) |
| Accessibility tree | ARIA snapshot as generic role/name | Opt-in |
| Available actions | Page's live interactive affordances | Opt-in |

**Opt-in for unbounded facets** — capped with explicit `*_truncated` flags. "Available actions" = page's affordances, NOT Worker's capabilities.

### 5. Worker Lifecycle Facade (from `BROWSER_WORKER_ARCHITECTURE.md` §10)
`BrowserWorker.run_step(capability, payload, requested_by, expected_outcome)` sequences three mechanical steps:
1. **Execute** — `LocalExecutor.execute(capability, payload)` (unmodified Executor)
2. **Verify** — if `expected_outcome` given, `BrowserVerifier.verify(...)` against session
3. **Audit** — `AuditRecord` capturing: requested_by, worker, environment, action, start/end time, Execution Result success, Verification Verdict, Evidence id, errors

**BrowserWorker performs NO reasoning:** no capability choice, no retry, no re-plan decision, no Memory/Knowledge touch.

---

## Current Implementation Status

### Filesystem Capabilities (Implemented — `FILESYSTEM_CAPABILITIES.md`, MB005)
| Category | Risk Tier | Capabilities |
|----------|-----------|--------------|
| Read | `READ_ONLY` | `read_file`, `list_directory`, `search_files`, `file_exists`, `directory_exists` |
| Write | `REVERSIBLE_WRITE` | `write_file`, `append_file` |
| Modify | `REVERSIBLE_WRITE` | `rename_file`, `copy_file`, `move_file` |
| Delete | `IRREVERSIBLE` | `delete_file`, `delete_folder` |
| Composite | — | `create_folder`, `workspace_bootstrap` |

**14 capabilities** via declarative registration (tuple of Action classes). Adding capability #N = one new Action file, no edit to Plugin/Executor/PermissionSystem.

### Browser Worker (Implemented — `BROWSER_WORKER_ARCHITECTURE.md`, MB022)
**9 Atomic Actions:**
| Action | Capability | Risk Tier | Category | Wraps |
|--------|------------|-----------|----------|-------|
| `OpenBrowserSessionAction` | `open_browser_session` | `REVERSIBLE_WRITE` | `SYSTEM` | Playwright launch + context + page |
| `CloseBrowserSessionAction` | `close_browser_session` | `REVERSIBLE_WRITE` | `SYSTEM` | Playwright teardown |
| `NavigateAction` | `navigate` | `REVERSIBLE_WRITE` | `MODIFY` | `page.goto()` |
| `ClickAction` | `click` | `REVERSIBLE_WRITE` | `MODIFY` | `page.locator().click()` |
| `TypeTextAction` | `type_text` | `REVERSIBLE_WRITE` | `WRITE` | `page.locator().fill()` |
| `PressKeyAction` | `press_key` | `REVERSIBLE_WRITE` | `MODIFY` | `page.keyboard.press()` |
| `ScrollAction` | `scroll` | `REVERSIBLE_WRITE` | `MODIFY` | `page.mouse.wheel()` |
| `WaitForSelectorAction` | `wait_for_selector` | `READ_ONLY` | `READ` | `page.locator().wait_for()` |
| `ObserveBrowserAction` | `observe_browser` | `READ_ONLY` | `READ` | `normalize_observation()` |

**Environment Session Manager:** `BrowserSessionManager` (per Operator Instance) → `BrowserSession` (Playwright instance, Browser, Context, Page). **NOT Shared Infrastructure** (§5.8).

**Generic Verification Package** (`verification/`) — zero Playwright imports, reusable by Desktop/Terminal/REST Workers.

**Product Independence:** No product names in code. Engine choice internal to `_launch()` in `browser_session.py` — single line names specific engine.

### Integration Points
| Surface | Purpose | Status |
|---------|---------|--------|
| `BrowserPlugin` | Thin `Plugin` adapter for Orchestrator/Registry/Permission path | ✅ Implemented |
| `BrowserWorker` | Constitution-complete facade (execute→verify→audit) | ✅ Implemented |
| Both paths → identical `LocalExecutor` + 9 `Action` classes | Single implementation, two callers | ✅ Verified |

---

## Open Questions

1. **Stateful Environment Sessions in Action Contract** (Constitution §8.3, §12, `FOUNDER_CONSTITUTION_FREEZE.md` §3.2)
   - Today's Action = one-shot (`validate()` → `run()`); Browser/Terminal/Robotics need live handle across multiple Steps
   - Resolved for Browser via `session_id` parameter + `BrowserSessionManager` (not Action contract change)
   - **Not a blocker** — no current Worker needs this beyond Browser

2. **Generic `EnvironmentSessionManager[T]` Base Class**
   - Deliberately not built — one concrete example (Browser) doesn't justify abstraction
   - Right call when second stateful Worker (Terminal) exists, not before

3. **Orchestrator-Level Automatic Verification Dispatch**
   - `BROWSER_WORKER_ARCHITECTURE.md` §11: two integration surfaces side by side (`BrowserPlugin` + `BrowserWorker`)
   - Verification not yet wired generically into `Orchestrator` — awaits second Verifier-backed Worker

4. **Multi-Engine Configuration Surface**
   - Engine choice internal to `_launch()`; not exposed in Environment Session contract
   - Deliberately not built — becomes right thing when second concrete example demands it

5. **Expression Language for `ObservationCheck`**
   - Currently 5 operators: `equals`, `contains`, `not_contains`, `matches_regex`, `exists`
   - Deliberately flat/small — bigger DSL easy to add, hard to remove

6. **Thread Affinity for Environment Sessions** (`RUNTIME_ENGINE_ARCHITECTURE.md` §5.1)
   - Browser Session must be used from thread that created it (Playwright sync API binds to per-thread event loop)
   - Every interaction must happen inside a task on Runtime's thread
   - Objective must open session, do work, close session as tasks

---

## Design vs Implementation Differences

| Area | Design (Architecture/Constitution) | Implementation | Status |
|------|-----------------------------------|----------------|--------|
| **Worker = Capability Implementation** | Each capability = one Action class (Rule 3) | ✅ Filesystem 14, Browser 9 | ✅ MATCH |
| **Environment Session per Operator Instance** | Owned by Operator Instance, never Shared Infra (§8.3) | ✅ `BrowserSessionManager` per Operator Instance | ✅ MATCH |
| **Action Contract Unchanged** | Browser adds `session_id` param, no new methods | ✅ Actions stateless, resolve session via Manager | ✅ MATCH |
| **Verification Independent** | Re-observes fresh, never reads ExecutionResult | ✅ `Verifier.verify()` calls `capture_observation_dict()` | ✅ MATCH |
| **Generic Verification Package** | Zero Environment imports, reusable | ✅ `verification/` package, `BrowserVerifier` ~10 lines | ✅ MATCH |
| **Single Observation Function** | `normalize_observation()` only Playwright touchpoint | ✅ Used by Action + Verifier | ✅ MATCH |
| **Product Independence** | No product names in code; engine choice internal | ✅ Single `_launch()` line names engine | ✅ MATCH |
| **No God-Class Actions** | One Action per clearly-scoped effect | ✅ 9 atomic Browser Actions | ✅ MATCH |
| **Declarative Registration** | Tuple of Action classes, no Plugin edit | ✅ Filesystem + Browser both | ✅ MATCH |
| **Thread Affinity Documented** | Browser Session thread-affine constraint | ✅ Named in Runtime §5.1 | ✅ MATCH |
| **Orchestrator Verification** | Not yet generic — two surfaces side by side | ⚠️ `BrowserPlugin` + `BrowserWorker` | 📝 DOCUMENTED |
| **Generic Session Manager** | Not built — awaits second Worker | ⏳ RESERVED | ⏳ RESERVED |
| **Expression Language** | 5 operators, deliberately small | ✅ `evaluate_checks()` with 5 operators | ✅ MATCH |

---

## Future Extraction Targets

1. `src/master_agent/executor/actions/browser/` — 9 Browser Action implementations
2. `src/master_agent/environment/browser_session.py` — `BrowserSessionManager`, `BrowserSession`
3. `src/master_agent/plugins/browser_observation.py` — `normalize_observation()`, `BrowserObservation`
4. `src/master_agent/plugins/browser_verifier.py` — `BrowserVerifier` (~10 lines)
5. `src/master_agent/plugins/browser_worker.py` — `BrowserWorker.run_step()`
6. `src/master_agent/plugins/browser_plugin.py` — `BrowserPlugin` adapter
7. `src/master_agent/verification/` — `Verifier` ABC, `evaluate_checks()`, `Evidence`, `AuditLog`
8. `tests/test_browser_constitution_compliance.py` — Mechanically checks no Playwright imports in generic layer
9. `tests/test_browser_worker_lifecycle.py` — Worker lifecycle facade tests
10. `docs/adr/0011` — Verification as independent subsystem

---

## Wiki Links Added

- `[[KALPAVRIKSHA_VISION_V2.md]]` — Constitution §4, §7, §8, §10, §12
- `[[FOUNDER_CONSTITUTION_FREEZE.md]]` — Open items, terminology
- `[[BROWSER_WORKER_ARCHITECTURE.md]]` — Primary source
- `[[FILESYSTEM_CAPABILITIES.md]]` — Action Contract pattern
- `[[ARCHITECTURE.md]]` — Implementation map §4.7
- `[[RUNTIME_ENGINE_ARCHITECTURE.md]]` — Thread affinity, Runtime loop
- `[[03_universal_executive_operator.md]]` — Operator responsibilities
- `[[04_shared_infrastructure.md]]` — Shared Infrastructure (Capability Registry, Permission)
- `[[06_runtime_engine.md]]` — Runtime Engine (thread affinity, loop)
- `[[07_mission_control.md]]` — Mission Control (dispatcher, registries)
- `[[system_overview.md]]` — System overview
- `[[docs/adr/0005]]`–`[[docs/adr/0006]]` — Relay pattern precedent
- `[[docs/adr/0009]]` — PermissionCategory + IRREVERSIBLE rule
- `[[docs/adr/0011]]` — Verification independent subsystem

---

*Document created from verified sources only. No environment execution capabilities redesigned. Terminology preserved exactly. Constitution/Architecture/Implementation/Open Questions separated. Design/implementation differences recorded without reconciliation.*