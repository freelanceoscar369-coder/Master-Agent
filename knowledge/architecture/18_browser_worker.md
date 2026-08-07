# Browser Worker Architecture

## Purpose
Documents the first concrete Worker implementation against the frozen Constitution — a Playwright-backed Browser Worker proving the Universal Executive Operator architecture in a real Environment.

---

## Frozen Constitution

### Constitution §4 (Universal Executive Operator — FROZEN)
> The **Universal Executive Operator** carries out what the Brain decided, with full accountability. It never decides, never plans, and never holds an opinion about *why* a Step exists — only *how* to run it safely and *whether it actually worked*.

### Constitution §7 (Universal Environment Philosophy — EVOLVABLE)
> **7.1 Local-First Is Not Optional** — System boots, plans, executes with purely local Reasoning Provider and local Memory.
> **7.2 Environment as an Abstract Category** — Desktop, Browser, Terminal, VPS, Robotics/IoT — never a specific product.
> **7.3 No Environment Assumptions in Core** — No hardcoded paths, no product-specific logic, no process lifetime assumptions.
> **7.4 Environment vs. Environment Instance** — "Environment" = category. "Environment Instance" = concrete live target.

### Constitution §8 (Multi-Operator Architecture — RESEARCH-BACKED)
> **8.2 Operator Instance** — One running instance bound to one (or tightly-coupled set of) Environment Instance(s). Tracked by Operator Registry.
> **8.3 Environment Instance and Environment Session** — Environment Instance = concrete target. Environment Session = live handle an Operator Instance holds. **Owned by exactly one Operator Instance; never Shared Infrastructure (§5.8).**

### Constitution §10 (Verification Philosophy — RESEARCH-BACKED)
> **Three-Part Boundary:**
> 1. **Execution produces effects** — Worker's Action runs, returns Execution Result. Says nothing about real-world outcome.
> 2. **Verification produces Evidence** — Verification Subsystem re-observes Environment Instance, compares Observation against Expected Outcome. Output = Verdict + Observation + Expected Outcome = **Evidence**.
> 3. **Evidence flows back to Brain** — routed via Shared Infrastructure as input to "is Mission complete?"

### Constitution §12 (Worker and Plugin Runtime — IMPLEMENTATION DETAIL)
> **12.2 Workers are Capabilities' implementations** — Every Capability implemented by a Worker registered on Operator's Worker Runtime. Adding Worker #N costs one new file; never edits Registry, Permission System, or Orchestrator (Rule 3).

---

## Architecture Design

### From `BROWSER_WORKER_ARCHITECTURE.md` §1
> **Not browser automation — Playwright already solves that.** This Mission Brief proves the **Universal Executive Operator architecture** by implementing its first real Worker against a real Environment. Every decision made so that a future Desktop Worker, Terminal Worker, REST Worker, or MCP Worker can copy this file's shape and change only what's genuinely browser-specific.

### From `BROWSER_WORKER_ARCHITECTURE.md` §2 (The Open Constitution Question)
> **Stateful Environment Sessions inside the Worker/Action contract** — today's Action contract is one-shot (`validate()` → `run()`); Browser, Terminal, and Robotics capabilities will eventually need a capability that holds a live handle across multiple `Step`s in one Mission.
>
> **Resolution:** Every Browser Action still implements the same six-member `Action` ABC unchanged; some Browser Actions additionally take a `session_id` parameter naming which already-open Environment Session to act against, resolved through a new **Environment Session Manager**, not through the Action contract growing a new method.

---

## Layer Map (Constitution → Implementation)

| Constitution Concept | Browser Worker Implementation |
|---------------------|------------------------------|
| Worker (§12) | 9 Browser Actions + `BrowserPlugin` |
| Environment Session (§8.3) | `BrowserSession` / `BrowserSessionManager` (`environment/browser_session.py`) |
| Observation (§10.2, §17) | `BrowserObservation` / `normalize_observation()` (`plugins/browser_observation.py`) |
| Verification (§10) | `Verifier` ABC (`verification/verifier.py`, generic) + `BrowserVerifier` (`plugins/browser_verifier.py`, ~10 lines) |
| Evidence (§9.2, §17) | `Evidence` / `ExpectedOutcome` / `ObservationCheck` / `Verdict` (`verification/evidence.py`, generic) |
| Audit (§5.6) | `AuditRecord` / `AuditLog` (`verification/audit.py`, generic) |
| Worker Lifecycle Facade | `BrowserWorker` (`plugins/browser_worker.py`) — sequences execute → verify → audit, decides nothing |

**Key Principle:** The **generic layer (`verification/`)** contains zero Playwright imports and zero browser vocabulary — written to be the Desktop/Terminal/REST Worker's verification layer too.

---

## Environment Session Design

### BrowserSessionManager (one per Operator Instance, per §8.2)
```
BrowserSessionManager
    session_id -> BrowserSession
                  BrowserSession owns: one Playwright instance,
                  one Browser, one BrowserContext, one Page.
                  Never exposed outside plugins/browser_*.py and
                  environment/browser_session.py.
```

### Methods
- `open_session(session_id) -> BrowserSessionHandle` — starts Playwright, launches browser, opens context and page, registers under `session_id`. **Deliberately NOT Shared Infrastructure (§5.8)** — live browser handle belongs to Operator Instance that opened it.
- `get(session_id) -> BrowserSession` — looks up live session; missing/closed = structured mechanical error
- `close_session(session_id)` — tears down page, context, browser, Playwright instance in order; swallows teardown errors into warnings list (closing must never fail loudly)
- Actions needing open page take `session_id` in payload, resolve through injected `BrowserSessionManager` — Action itself never stores session state between calls (stays stateless like all Actions)

### Why No Generic `EnvironmentSessionManager[T]` Yet?
> One concrete example (Browser) doesn't justify the abstraction yet — same judgment call ADR-0005/0006 made about Plugin→Executor relay pattern. Shape written so second Worker (Terminal) can copy the shape directly; extracting shared base is right call when second example exists, not before.

---

## Action Roster (9 Atomic Actions)

| Action | Capability | Risk Tier | Category | Wraps |
|--------|------------|-----------|----------|-------|
| `OpenBrowserSessionAction` | `open_browser_session` | `REVERSIBLE_WRITE` | `SYSTEM` | Playwright launch + new_context + new_page |
| `CloseBrowserSessionAction` | `close_browser_session` | `REVERSIBLE_WRITE` | `SYSTEM` | Playwright context/browser teardown |
| `NavigateAction` | `navigate` | `REVERSIBLE_WRITE` | `MODIFY` | `page.goto()` |
| `ClickAction` | `click` | `REVERSIBLE_WRITE` | `MODIFY` | `page.locator(selector).click()` |
| `TypeTextAction` | `type_text` | `REVERSIBLE_WRITE` | `WRITE` | `page.locator(selector).fill()` |
| `PressKeyAction` | `press_key` | `REVERSIBLE_WRITE` | `MODIFY` | `page.keyboard.press()` / locator `.press()` |
| `ScrollAction` | `scroll` | `REVERSIBLE_WRITE` | `MODIFY` | `page.locator(selector).scroll_into_view_if_needed()` / `mouse.wheel()` |
| `WaitForSelectorAction` | `wait_for_selector` | `READ_ONLY` | `READ` | `page.locator(selector).wait_for()` |
| `ObserveBrowserAction` | `observe_browser` | `READ_ONLY` | `READ` | `normalize_observation()` |

**Key Points:**
- `open_browser_session`/`close_browser_session` = `SYSTEM` category (first real use of `PermissionCategory.SYSTEM` reserved by ADR-0009)
- **None are `IRREVERSIBLE`** — every effect undone by closing session; mirrors Filesystem's honest tiering discipline
- **Deliberately not built:** hover, drag-and-drop, file upload, multi-tab management, network interception — adding any = one new Action file when concrete need exists

---

## Observation and Normalization

### Single Function: `normalize_observation()`
```python
normalize_observation(page, selectors=None, include_accessibility_tree=False,
                      include_available_actions=False) -> BrowserObservation
```
- **Only function besides Actions that touches Playwright `Page`**
- Called by both `ObserveBrowserAction.run()` and `BrowserVerifier.capture_observation_dict()`
- `BrowserObservation.as_dict()` = generic, Playwright-free view crossing into Evidence machinery

### Five Facets

| Facet | Source | Always On? |
|-------|--------|------------|
| Current page | `page.url`, `page.title()` | Yes |
| Viewport | `page.viewport_size` | Yes |
| DOM state / visible elements | Best-effort `BrowserElement` per caller-supplied selector | Yes (for asked selectors) |
| Accessibility tree | ARIA snapshot as generic role/name vocabulary | Opt-in |
| Available actions | Page's live interactive affordances (role, name, tag, enabled) | Opt-in |

**Why Last Two Opt-In:**
- Unbounded in page size; first three bounded by what caller asked about
- Verification re-observes on **every** verified step — unconditional capture would tax every Mission and inflate Evidence records
- Callers opt in per call; both capped (`MAX_ACCESSIBILITY_TREE_CHARS`, `MAX_AVAILABLE_ACTIONS`) with explicit `*_truncated` flag

**Critical Distinction:** "Available actions" = page's affordances (enabled button, link, editable field) — **NOT** Worker's capabilities (which are Capability Registry concern).

---

## Verification Independence

### Generic Verification Package (`verification/`)
- **Zero Playwright imports, zero browser vocabulary** — written for Desktop/Terminal/REST Workers too
- **`Verifier` ABC** with `capture_observation_dict()` (abstract) + `verify(expected)` (concrete)
- **`evaluate_checks()`** — pure function, no I/O
- **`Evidence` / `ExpectedOutcome` / `ObservationCheck` / `Verdict`** — generic types
- **`AuditRecord` / `AuditLog`** — generic audit

### BrowserVerifier (~10 lines)
```python
class BrowserVerifier(Verifier):
    worker_name = "browser"
    environment_name = "browser"
    
    def capture_observation_dict(self) -> dict:
        return normalize_observation(self._page, ...)
```

### Key Principle (ADR-0011)
> **Execution produces effects. Verification produces Evidence.**
> `Verifier.verify()` **never reads `ExecutionResult`** — always re-observes reality fresh.
> Execution success ≠ verification success — `NOT_MATCHED` verdict = failed task.

---

## Worker Lifecycle Facade: `BrowserWorker`

### `run_step(capability, payload, requested_by, expected_outcome=None)`
Sequences exactly three mechanical steps, returns `BrowserStepReport`:
1. **Execute** — `LocalExecutor.execute(capability, payload)` (unmodified Executor)
2. **Verify** — if `expected_outcome` given, `BrowserVerifier.verify(...)` against session
3. **Audit** — `AuditRecord` capturing: requested_by, worker, environment, action, start/end time, Execution Result success, Verification Verdict, Evidence id, errors

**BrowserWorker performs NO reasoning:** no capability choice, no retry, no re-plan decision, no Memory/Knowledge touch.

---

## Two Integration Surfaces (Not One)

### 1. `BrowserPlugin` — Execution-Only Path
- Thin `Plugin` adapter for Orchestrator/Registry/Permission path
- Proves Capability Registry integration works for second capability family at zero risk to existing tests

### 2. `BrowserWorker` — Constitution-Complete Facade
- Execute → Verify → Audit sequence
- Called by demonstration and `test_browser_worker_lifecycle.py`
- Stands in for future Brain/Orchestrator integration

**Both paths execute through identical `LocalExecutor` + 9 `Action` classes** — single implementation, two callers.

### Critical: No Self-Granting Permission
- `BrowserPlugin.invoke()` relays `ONCE` grant to Executor's key (ADR-0005 pattern) — safe because Orchestrator's check already passed
- `BrowserWorker.run_step()` has **no upstream gate** — does not touch `permissions.grant()`; caller (approved Mission) responsible for granting Executor's key before calling

---

## Product Independence

### The One Gray Area: Playwright Engine Choice
- Playwright's launcher API namespaced by engine; one engine identifier = consumer browser product name
- **Resolution:** Environment Session contract does not expose engine choice at all
- `BrowserSession` takes only `headless: bool`; engine choice internal to single private function `_launch(playwright_instance)` in `environment/browser_session.py`
- **Only line in entire Browser Worker naming a specific engine**
- Swapping Playwright for different browser-automation library = touches exactly that one function

---

## Current Implementation Status

| Component | Architecture Status | Implementation Status | Notes |
|-----------|---------------------|----------------------|-------|
| **9 Browser Actions** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | `executor/actions/browser/` |
| **BrowserSessionManager** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | `environment/browser_session.py` |
| **normalize_observation()** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | `plugins/browser_observation.py` |
| **BrowserObservation** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | 5 facets, opt-in unbounded |
| **Verifier ABC** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | `verification/verifier.py` |
| **BrowserVerifier** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | ~10 lines, `plugins/browser_verifier.py` |
| **Evidence/Audit Types** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | `verification/evidence.py`, `verification/audit.py` |
| **BrowserWorker Facade** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | `plugins/browser_worker.py` |
| **BrowserPlugin** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | `plugins/browser_plugin.py` |
| **Generic Verification Package** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | Zero Playwright imports |
| **Product Independence** | FROZEN (§14, §21) | ✅ **IMPLEMENTED** | Engine choice internal to `_launch()` |
| **Compliance Tests** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | `test_browser_constitution_compliance.py` |

---

## Design vs Implementation Differences

| Area | Design (Architecture/Constitution) | Implementation | Status |
|------|-----------------------------------|----------------|--------|
| **Worker = Capability Implementation** | 9 Actions + Plugin | ✅ 9 Actions + BrowserPlugin | ✅ MATCH |
| **Environment Session** | Per Operator Instance, not Shared Infra | ✅ `BrowserSessionManager` per Operator Instance | ✅ MATCH |
| **Action Contract Unchanged** | Adds `session_id` param, no new methods | ✅ Stateless Actions, resolve via Manager | ✅ MATCH |
| **Verification Independent** | Re-observes fresh, never reads ExecutionResult | ✅ `Verifier.verify()` calls `capture_observation_dict()` | ✅ MATCH |
| **Generic Verification Package** | Zero Environment imports | ✅ `verification/` zero Playwright imports | ✅ MATCH |
| **Single Observation Function** | `normalize_observation()` only Playwright touchpoint | ✅ Used by Action + Verifier | ✅ MATCH |
| **Product Independence** | No product names; engine choice internal | ✅ Single `_launch()` line names engine | ✅ MATCH |
| **No God-Class Actions** | One Action per effect | ✅ 9 atomic Browser Actions | ✅ MATCH |
| **Declarative Registration** | Tuple of Action classes | ✅ `_ACTION_CLASSES` tuple | ✅ MATCH |
| **Thread Affinity Documented** | Browser Session thread-affine | ✅ Named in Runtime §5.1 | ✅ MATCH |
| **Orchestrator Verification** | Not yet generic | ⚠️ Two surfaces side by side | 📝 DOCUMENTED |
| **Generic Session Manager** | Not built — awaits second Worker | ⏳ RESERVED | ⏳ RESERVED |
| **Expression Language** | 5 operators, deliberately small | ✅ `evaluate_checks()` with 5 operators | ✅ MATCH |

---

## Open Questions

1. **Stateful Environment Sessions in Action Contract** (§8.3, §12, `FOUNDER_CONSTITUTION_FREEZE.md` §3.2) — today's Action is one-shot (`validate()` → `run()`); Browser/Terminal/Robotics need live handle across multiple Steps. Resolved for Browser via `session_id` + Manager; not a blocker.

2. **Generic `EnvironmentSessionManager[T]` Base Class** — deliberately not built; awaits second Worker (Terminal).

3. **Orchestrator-Level Automatic Verification Dispatch** — two surfaces side by side (`BrowserPlugin` + `BrowserWorker`); awaits second Verifier-backed Worker.

4. **Multi-Engine Configuration Surface** — engine choice internal to `_launch()`; not exposed.

5. **Expression Language for `ObservationCheck`** — 5 operators (`equals`, `contains`, `not_contains`, `matches_regex`, `exists`); deliberately flat/small.

6. **Thread Affinity for Environment Sessions** (`RUNTIME_ENGINE_ARCHITECTURE.md` §5.1) — Browser Session must be used from thread that created it (Playwright sync API binds to per-thread event loop). Objectives must open/close session as tasks.

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
- `[[BROWSER_WORKER_ARCHITECTURE.md]]` — Primary source document
- `[[FILESYSTEM_CAPABILITIES.md]]` — Action Contract pattern
- `[[ARCHITECTURE.md]]` — Implementation map §4.7
- `[[RUNTIME_ENGINE_ARCHITECTURE.md]]` — Thread affinity, Runtime loop
- `[[03_universal_executive_operator.md]]` — Operator responsibilities
- `[[04_shared_infrastructure.md]]` — Shared Infrastructure (Capability Registry, Permission)
- `[[06_runtime_engine.md]]` — Runtime Engine (thread affinity, loop)
- `[[07_mission_control.md]]` — Mission Control (dispatcher, registries)
- `[[10_environment_execution.md]]` — Environment execution patterns
- `[[11_verification_system.md]]` — Verification system
- `[[12_permission_security.md]]` — Permission integration
- `[[13_plugin_system.md]]` — Plugin system (BrowserPlugin)
- `[[15_action_contract.md]]` — Action Contract
- `[[16_filesystem_capabilities.md]]` — Filesystem reference
- `[[system_overview.md]]` — System overview
- `[[docs/adr/0005]]`–`[[docs/adr/0006]]` — Relay pattern precedent
- `[[docs/adr/0009]]` — PermissionCategory + IRREVERSIBLE rule
- `[[docs/adr/0011]]` — Verification independent subsystem

---

*Document created from verified sources only. No Browser Worker architecture redesigned. Terminology preserved exactly. Constitution/Architecture/Implementation/Open Questions separated. Design/implementation differences recorded without reconciliation.*