# Permission & Security Architecture

## Purpose
Documents the human-approval gate, risk classification, and security boundaries that govern all capability execution in Kalpavriksha.

---

## Frozen Constitution

### Constitution §2.4 (Human Approval Before Important Actions — FROZEN)
> No Worker executes a step classified above `READ_ONLY` risk without a grant from the Permission System (§5). The Permission System has veto power over the Operator — it is not optional middleware, it is a gate.

### Constitution §5.2 (Permission System — FROZEN)
> **Belongs in Shared Infrastructure because:** it must remain a single, consistent grant ledger across every Operator Instance a Mission might touch. If each Operator Instance held its own grant table, a human approving a destructive capability once, for one Operator, could be silently re-satisfied — or silently re-asked — by a different Operator executing a different Step of the *same* Mission. Elevating Permission System to Shared Infrastructure is what makes "one approval per mission" (§15.3) a Mission-wide guarantee instead of an accidental, per-Operator-Instance one.

> **The relay pattern** (an outer approval explicitly carried down to an inner grant key, ADR-0005/0006) is unchanged by this move.

### Constitution §15 (Human Oversight Philosophy — FROZEN)

**15.1 Approval Is Not Optional**
> Every capability above `READ_ONLY` requires a Permission System grant (Shared Infrastructure, §5.2). Declining → `Mission.CANCELLED`, nothing executed, nothing persisted as a side effect.

**15.2 Approval UX Must Stay Simple**
> One clear decision point, regardless of how many Operator Instances (§8) or sub-steps a Mission touches.

**15.3 One Approval Per Mission (Canonical Statement)**
> A human is never asked twice for the same thing they already approved, no matter how many primitive Steps, Workers, or Operator Instances that thing decomposes into underneath. Achieved by relaying an already-obtained grant down through Shared Infrastructure's Permission System (§5.2, Rule 6) — **never by weakening what gets checked**.

**15.4 Transparency Over Trust**
> Every execution is logged. Every Mission is recorded. Evidence (§10) is available, not hidden. No Reasoning Provider call happens without a named Capability behind it.

### Constitution Rule 5 (FROZEN)
> **Permission System Has Veto Power, Now Mission-Wide.** Every capability declares a risk tier. The Permission System (Shared Infrastructure, §5.2) is consulted before any step above `READ_ONLY`, regardless of which Operator Instance executes it. An `ALWAYS_FOR_CAPABILITY` grant never satisfies an `IRREVERSIBLE` check.

### Constitution Rule 6 (FROZEN)
> **Composites and Nested Calls Relay, Never Bypass.** A Worker that orchestrates other Workers does so only through the Capability Registry and Permission System, relaying its own already-obtained grant down to each sub-step. No transactional rollback on partial failure — completed steps stay completed, and the result reports exactly what completed before failure.

### Constitution Rule 4 (FROZEN)
> **Environment Access Has One Door.** No Brain module, no CLI code, touches an Environment directly. Everything goes through a Worker, via the Operator's Worker Runtime, via an Environment Session (§8.3) the Operator Instance owns.

---

## Security Philosophy

### From `FILESYSTEM_CAPABILITIES.md` §6 (Security)

**Every Action validates four things using existing machinery (not inventing new checks per Action):**

1. **Path Traversal** — Every path-shaped parameter checked with `is_unsafe_relative_path()` (`executor/action.py`) — rejects absolute paths and any `..` segment. Checks both PurePosixPath and PureWindowsPath (MB023.1) — sandbox boundary identical on every platform.

2. **Invalid Paths** — Empty/whitespace-only names, non-string content, structurally malformed payloads rejected in `validate()` before filesystem or Permission System touched — `Action.validate()` "must never touch the filesystem or perform side effects."

3. **Overwrite Behaviour** — `RenameFileAction`/`CopyFileAction`/`MoveFileAction` refuse to clobber existing destination by default — fails with structured error unless payload explicitly sets `"overwrite": true`. Different from `WriteFileAction`/`CreateFolderAction` idempotency (identical content = no-op).

4. **Dangerous Destinations** — All locations from small, developer-configured `locations: dict[str, Path]` map (`{"desktop": ..., "downloads": ..., "documents": ...}` by default). Combined with traversal check, no payload can name path outside roots. `DeleteFolderAction` additionally refuses empty or `"."` path.

### From `BROWSER_WORKER_ARCHITECTURE.md` §5 (Product Independence)
- No product names in code — Environment Session contract does not expose engine choice
- Engine choice internal to single private function `_launch()` in `browser_session.py`
- Swapping Playwright for different browser-automation library touches exactly one function

---

## Permission Model

### Core Types (from `permission_system.py` and `plugins/base.py`)

**RiskTier (Enum):**
| Tier | Description | Permission Check |
|------|-------------|------------------|
| `READ_ONLY` | No side effects, read-only observation | Short-circuits unconditionally — never prompts |
| `REVERSIBLE_WRITE` | Can be undone (move back, delete copy, rename back) | Grants: `ONCE`, `THIS_SESSION`, `ALWAYS_FOR_CAPABILITY` apply |
| `IRREVERSIBLE` | Cannot be undone (delete file/folder) | **`ALWAYS_FOR_CAPABILITY` NEVER satisfies** — fresh decision every time |

**PermissionCategory (Enum — orthogonal to RiskTier):**
| Category | Description | Example Capabilities |
|----------|-------------|---------------------|
| `READ` | Read-only observation | `read_file`, `list_directory`, `wait_for_selector`, `observe_browser` |
| `WRITE` | Create new content | `write_file`, `append_file`, `type_text` |
| `MODIFY` | Change existing content | `rename_file`, `copy_file`, `move_file`, `navigate`, `click`, `press_key`, `scroll` |
| `DELETE` | Destroy content | `delete_file`, `delete_folder` |
| `SYSTEM` | Process/system operations | `open_browser_session`, `close_browser_session` |

**GrantScope (Enum):**
- `ONCE` — Covers exactly one invocation, consumed atomically with check
- `THIS_SESSION` — Covers all invocations in current session
- `ALWAYS_FOR_CAPABILITY` — Standing grant (BUT never satisfies `IRREVERSIBLE`)

### Permission Check Flow (`PermissionSystem.check()`)

```python
def check(plugin_name: str, capability: str, risk_tier: RiskTier) -> None:
    if risk_tier == RiskTier.READ_ONLY:
        return  # Short-circuits unconditionally

    # IRREVERSIBLE: ALWAYS_FOR_CAPABILITY never satisfies
    def _usable(grant):
        if risk_tier == RiskTier.IRREVERSIBLE and grant.scope == GrantScope.ALWAYS_FOR_CAPABILITY:
            return False
        return True

    match = find grant where plugin_name + capability match and _usable(grant)
    if match is None:
        raise ApprovalRequired(plugin_name, capability, risk_tier)
    if match.scope == GrantScope.ONCE:
        discard(match)  # Consumed atomically
```

### Relay Pattern (ADR-0005, ADR-0006)
- **Orchestrator → Executor:** Outer approval explicitly carried down to inner grant key
- **Composite → Sub-steps:** Already-obtained grant relayed to each sub-step
- **Plugin → Executor:** `grant_permission` callable in `PluginGateway` invoked before each `invoke()`

---

## Approval Boundaries

### 1. Orchestrator Boundary (Original)
- `Orchestrator.execute_capability()` calls `PermissionSystem.check()` before `plugin.invoke()`
- Returns `StepResult(blocked_on_approval=True)` if `ApprovalRequired` raised
- Used by `master-agent-demo` entry point

### 2. Runtime Boundary (MB028.0, ADR-019) — **Added Later**
**Problem:** Runtime calls `ExecutiveGateway` directly → Orchestrator's check never ran on this path. `IRREVERSIBLE` `delete_folder` completed with no approval.

**Fix:** `RuntimeEngine._handle_task()` consults `ApprovalGate` at single funnel `_handle_task()` before any gateway touched.

**ApprovalGate Protocol (defined in `runtime/approval.py`):**
```python
class ApprovalGate(Protocol):
    def check(self, request: ApprovalRequest) -> None: ...
```

**Three Outcomes:**
1. **Authorised** → execute
2. **ApprovalPending** → hold task, re-offer next cycle (task invisible to `_dispatch()`)
3. **ApprovalDenied** → fail, never retry

**Properties:**
- **One funnel** — `_handle_task()` only place reaching gateway; AST test fails if second `gateway.invoke()` site appears
- **No Runtime dependency** — `ApprovalGate` protocol inside `runtime/`; `PermissionSystemGate` adapter typed against protocols
- **Fail closed** — No gate ⇒ nothing runs (not even `READ_ONLY`)

### 3. FounderApprovalGate (MB028.1) — **Wraps PermissionSystemGate**
Adds third outcome: **ask the founder; the task waits** (instead of immediate deny).
- `ApprovalPending` deliberately not subclass of `ApprovalDenied`
- Expiry evaluated on each cycle re-check (no separate timer)
- Approval consumed once — never reused (ADR-0009)

---

## Risk Classification

### Filesystem Capabilities (`FILESYSTEM_CAPABILITIES.md` §5)

| Category | Risk Tier | Capabilities |
|----------|-----------|--------------|
| Read | `READ_ONLY` | `read_file`, `list_directory`, `search_files`, `file_exists`, `directory_exists` |
| Write | `REVERSIBLE_WRITE` | `write_file`, `append_file` |
| Modify | `REVERSIBLE_WRITE` | `rename_file`, `copy_file`, `move_file` |
| Delete | `IRREVERSIBLE` | `delete_file`, `delete_folder` |
| Composite | — | `create_folder`, `workspace_bootstrap` |

### Browser Capabilities (`BROWSER_WORKER_ARCHITECTURE.md` §6)

| Action | Capability | Risk Tier | Category |
|--------|------------|-----------|----------|
| `OpenBrowserSessionAction` | `open_browser_session` | `REVERSIBLE_WRITE` | `SYSTEM` |
| `CloseBrowserSessionAction` | `close_browser_session` | `REVERSIBLE_WRITE` | `SYSTEM` |
| `NavigateAction` | `navigate` | `REVERSIBLE_WRITE` | `MODIFY` |
| `ClickAction` | `click` | `REVERSIBLE_WRITE` | `MODIFY` |
| `TypeTextAction` | `type_text` | `REVERSIBLE_WRITE` | `WRITE` |
| `PressKeyAction` | `press_key` | `REVERSIBLE_WRITE` | `MODIFY` |
| `ScrollAction` | `scroll` | `REVERSIBLE_WRITE` | `MODIFY` |
| `WaitForSelectorAction` | `wait_for_selector` | `READ_ONLY` | `READ` |
| `ObserveBrowserAction` | `observe_browser` | `READ_ONLY` | `READ` |

**Key principle:** No Browser Action is `IRREVERSIBLE` — every effect undone by closing session. Mirrors Filesystem's honest tiering discipline.

---

## Current Implementation Status

| Component | Constitution/Architecture | Implementation Status | Notes |
|-----------|---------------------------|----------------------|-------|
| **PermissionSystem** | FROZEN (§5.2) | ✅ **IMPLEMENTED** | `permissions/permission_system.py` — grants, check(), IRREVERSIBLE rule |
| **RiskTier Enum** | FROZEN | ✅ **IMPLEMENTED** | `plugins/base.py` — READ_ONLY, REVERSIBLE_WRITE, IRREVERSIBLE |
| **PermissionCategory Enum** | FROZEN (ADR-0009) | ✅ **IMPLEMENTED** | `plugins/base.py` — READ, WRITE, MODIFY, DELETE, SYSTEM |
| **GrantScope Enum** | FROZEN | ✅ **IMPLEMENTED** | `permissions/permission_system.py` — ONCE, THIS_SESSION, ALWAYS_FOR_CAPABILITY |
| **Orchestrator Check** | FROZEN (§4.1) | ✅ **IMPLEMENTED** | `orchestrator/orchestrator.py` — check() before invoke() |
| **Executor Relay** | FROZEN (ADR-0005) | ✅ **IMPLEMENTED** | `executor/executor.py` — own grant key, relayed from Plugin |
| **PluginGateway Relay** | FROZEN (ADR-0005) | ✅ **IMPLEMENTED** | `runtime/gateway.py` — `grant_permission` callable |
| **Runtime ApprovalGate** | MB028.0/ADR-019 | ✅ **IMPLEMENTED** | `runtime/approval.py` — Protocol + PermissionSystemGate |
| **FounderApprovalGate** | MB028.1/ADR-020 | ✅ **IMPLEMENTED** | `runtime/approval.py` — wraps PermissionSystemGate |
| **Fail-Closed Runtime** | MB028.0 | ✅ **IMPLEMENTED** | No gate ⇒ nothing runs |
| **Approval Evidence** | MB028.1 | ✅ **IMPLEMENTED** | `APPROVAL_GRANTED`/`DENIED` events with `decided_by` |
| **Filesystem Security** | `FILESYSTEM_CAPABILITIES.md` §6 | ✅ **IMPLEMENTED** | Traversal, invalid paths, overwrite, sandboxing |
| **Browser Product Independence** | `BROWSER_WORKER_ARCHITECTURE.md` §5 | ✅ **IMPLEMENTED** | Engine choice internal to `_launch()` |
| **Cross-Platform Path Safety** | MB023.1 | ✅ **IMPLEMENTED** | `is_unsafe_relative_path()` checks both PurePosixPath/PureWindowsPath |

---

## Open Questions

1. **Two Approval Gates** — Orchestrator checks PermissionSystem; Runtime has separate ApprovalGate. Both paths exist. Relay pattern (ADR-0005) connects them but adds complexity. Is this the right long-term architecture?

2. **Filesystem Verifier Missing** — No independent Verification for Filesystem capabilities. ExecutionResult trusted without re-observation. Constitution §10 requires Verification for all.

3. **Grant Scope UI Not Implemented** — Nothing currently offers human option to create `THIS_SESSION` or `ALWAYS_FOR_CAPABILITY` grants (every live flow only grants `ONCE`). IRREVERSIBLE rule defensive ahead of UI.

4. **CapabilityManifest.input_schema/output_schema Empty** — Declared in frozen `plugins/base.py`, populated by nothing. Planner guesses payload names (MB036 Finding 4). Security validation limited to what Action.validate() checks.

5. **Multi-Operator Permission Consistency** — Shared Infrastructure owns single grant ledger (§5.2). Implementation uses in-memory `set[PermissionGrant]`. Multi-process deployment would need shared store.

6. **Standing Grant for READ_ONLY** — `READ_ONLY` short-circuits unconditionally. No grant recorded. Is this auditable enough? Constitution §15.4 says "No Reasoning Provider call happens without a named Capability behind it" — but READ_ONLY capability executions not logged in grant ledger.

---

## Design vs Implementation Differences

| Area | Design (Architecture/Constitution) | Implementation | Status |
|------|-----------------------------------|----------------|--------|
| **Single Grant Ledger** | Shared Infrastructure (§5.2) | ✅ In-memory `set[PermissionGrant]` | ✅ MATCH |
| **IRREVERSIBLE Rule** | ALWAYS_FOR_CAPABILITY never satisfies | ✅ Enforced in `_usable()` check | ✅ MATCH |
| **READ_ONLY Short-Circuit** | Never prompts, unconditional | ✅ First check in `check()` | ✅ MATCH |
| **ONCE Grant Consumption** | Consumed atomically with check | ✅ `discard(match)` in check() | ✅ MATCH |
| **Relay Pattern** | Outer → inner grant key | ✅ PluginGateway.grant_permission + Executor | ✅ MATCH |
| **Runtime ApprovalGate** | Single funnel, fail-closed | ✅ Protocol in `runtime/`, AST test enforces | ✅ MATCH |
| **FounderApprovalGate** | Three outcomes (auth/pending/deny) | ✅ Wraps PermissionSystemGate | ✅ MATCH |
| **Filesystem Security** | 4 validation layers | ✅ Traversal, invalid, overwrite, sandbox | ✅ MATCH |
| **Cross-Platform Paths** | Both PurePosixPath/PureWindowsPath | ✅ MB023.1 implemented | ✅ MATCH |
| **Two Approval Gates** | One boundary | ⚠️ Orchestrator + Runtime (both exist) | 📝 DOCUMENTED |
| **Filesystem Verifier** | Mandatory per Constitution §10 | ❌ Not implemented | ❌ MISSING |
| **Grant UI** | THIS_SESSION/ALWAYS offered | ❌ Only ONCE ever granted live | ⚠️ DEFERRED |
| **Capability Schemas** | input_schema/output_schema declared | ❌ Populated by nothing | ❌ MISSING |
| **Multi-Process Grants** | Single ledger across instances | ⚠️ In-memory set only | 📝 DOCUMENTED |

---

## Future Extraction Targets

1. `src/master_agent/permissions/permission_system.py` — PermissionSystem, GrantScope, ApprovalRequired
2. `src/master_agent/plugins/base.py` — RiskTier, PermissionCategory, CapabilityManifest
3. `src/master_agent/executor/action.py` — `is_unsafe_relative_path()`, `default_locations()`, security helpers
4. `src/master_agent/orchestrator/orchestrator.py` — Orchestrator check() before invoke
5. `src/master_agent/runtime/approval.py` — ApprovalGate, PermissionSystemGate, FounderApprovalGate
6. `src/master_agent/runtime/gateway.py` — PluginGateway grant_permission relay
7. `src/master_agent/executor/executor.py` — LocalExecutor permission relay
8. `tests/test_permission_system.py` — Permission system tests
8. `docs/adr/0005` — Executor permission relay
9. `docs/adr/0006` — Composite action relay
10. `docs/adr/0009` — PermissionCategory + IRREVERSIBLE grant rule
11. `docs/adr/0019` — Runtime approval boundary
12. `docs/adr/0020` — Founder approval workflow (Proposed)

---

## Wiki Links Added

- `[[KALPAVRIKSHA_VISION_V2.md]]` — Constitution §2.4, §5.2, §15, Rule 4, Rule 5, Rule 6
- `[[FOUNDER_CONSTITUTION_FREEZE.md]]` — Freeze record, amendments
- `[[FILESYSTEM_CAPABILITIES.md]]` — Security §5, §6
- `[[BROWSER_WORKER_ARCHITECTURE.md]]` — Browser capabilities, product independence
- `[[RUNTIME_ENGINE_ARCHITECTURE.md]]` — ApprovalGate, thread affinity
- `[[ARCHITECTURE.md]]` — Implementation map §4.4
- `[[03_universal_executive_operator.md]]` — Operator responsibilities
- `[[04_shared_infrastructure.md]]` — Shared Infrastructure (Permission System)
- `[[06_runtime_engine.md]]` — Runtime Engine (ApprovalGate, loop)
- `[[10_environment_execution.md]]` — Environment execution patterns
- `[[system_overview.md]]` — System overview
- `[[docs/adr/0005]]`–`[[docs/adr/0006]]` — Relay pattern
- `[[docs/adr/0009]]` — PermissionCategory + IRREVERSIBLE rule
- `[[docs/adr/0019]]` — Runtime approval boundary
- `[[docs/adr/0020]]` — Founder approval workflow (Proposed)

---

*Document created from verified sources only. No security capabilities redesigned. Terminology preserved exactly. Constitution/Architecture/Implementation/Open Questions separated. Design/implementation differences recorded without reconciliation.*