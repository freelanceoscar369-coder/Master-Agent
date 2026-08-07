# Action Contract Architecture

## Purpose
Documents the foundational Action Contract that every local capability (filesystem, browser, shell, git, VS Code, Obsidian, etc.) implements. This is the universal execution interface that makes "adding capability #N = one new file" a reality.

---

## Frozen Constitution

### Constitution Rule 3 (FROZEN)
> **Capability Contract Is Sacred.** Every capability is a Worker behind the Capability Registry. Adding capability #N costs one new file, never an edit to the Registry, Orchestrator, Permission System, or Worker Runtime.

### Constitution Rule 4 (FROZEN)
> **Environment Access Has One Door.** No Brain module, no CLI code, touches an Environment directly. Everything goes through a Worker, via the Operator's Worker Runtime, via an Environment Session (§8.3) the Operator Instance owns.

### Constitution §12.2 (IMPLEMENTATION DETAIL)
> **Workers are Capabilities' implementations** — Every Capability is implemented by a Worker (Action or Plugin, in current terminology) registered on the Operator's Worker Runtime. Adding Worker #N costs one new file; it never means editing the Capability Registry, the Permission System, or the Orchestrator.

### Constitution §12.3 (IMPLEMENTATION DETAIL)
> **Composite Workers** — A Worker may orchestrate other Workers (e.g., a project-bootstrap capability composed from folder-creation and file-write capabilities) — but only through the same Shared Infrastructure Capability Registry and Permission System every other caller uses, relaying its own already-obtained grant down to each sub-step (Rule 6).

### Constitution Rule 6 (FROZEN)
> **Composites and Nested Calls Relay, Never Bypass.** A Worker that orchestrates other Workers does so only through the Capability Registry and Permission System, relaying its own already-obtained grant down to each sub-step. No transactional rollback on partial failure — completed steps stay completed, and the result reports exactly what completed before failure.

### Constitution §5.2 (Permission System — FROZEN)
> The Permission System (Shared Infrastructure) is consulted before any step above `READ_ONLY`, regardless of which Operator Instance executes it. The relay pattern (an outer approval explicitly carried down to an inner grant key, ADR-0005/0006) is unchanged by this move.

---

## Architecture Design

### From `executor/action.py` Module Docstring
> **The Action Contract — the foundation every future local capability (create/read/rename/delete/copy/move file, run PowerShell/CMD, git, VS Code, Obsidian, ...) plugs into.**
>
> Deliberately small: name, description, risk tier, required parameters, a validation step, and a run step. Anything more here makes writing a new action expensive, which defeats the point of having a contract at all.

### From `FILESYSTEM_CAPABILITIES.md` §1–§2
**Why Actions Are Individual:**
- Every operation is its own `Action` class: own `name`, `validate()`, `run()`, registered individually
- Not one `FileManagerAction` with `operation` parameter switching between `"read"`/`"write"`/`"delete"`
- Reasons: risk tier per operation, validation per operation, scalability (adding #50 = new file, not 50th branch)

**Why Actions Remain Atomic:**
- One Action = one clearly-scoped effect
- `ReadFileAction` reads, doesn't check existence first and branch
- `DeleteFileAction` deletes file, refuses directory (`DeleteFolderAction` handles directories)
- `RenameFileAction` only renames within directory (`MoveFileAction` crosses directories)
- Atomicity = "one Action, one clearly-scoped effect" — not database-transaction atomicity

**Why Composition Over Large Actions:**
- `WorkspaceBootstrapAction` = composite orchestrating primitives through real `LocalExecutor.execute()`
- Every sub-step independently validated, permission-gated, logged
- No rollback on partial failure (deliberate, ADR-0006)
- Small primitives compose into arbitrarily many combinations; large Action only does one combination

---

## Action Contract Interface

### Class Attributes (Declared, Not Instantiated)
```python
class Action(ABC):
    name: str                           # Unique identifier (e.g., "read_file")
    description: str                    # Human-readable description
    risk_tier: RiskTier                 # READ_ONLY | REVERSIBLE_WRITE | IRREVERSIBLE
    permission_category: PermissionCategory  # READ | WRITE | MODIFY | DELETE | SYSTEM
    expected_result: str                # Description of successful outcome
```

### Abstract Methods

**`required_parameters() -> list[str]`**
- Names of parameters this action requires in its payload
- Documentation as much as contract; `validate()` is what's actually enforced

**`validate(parameters: dict[str, Any]) -> list[str]`**
- Returns validation error messages; empty list = valid
- **Must never touch filesystem or perform side effects** — pure check
- Called before permission consulted, so malformed request fails fast

**`run(parameters: dict[str, Any]) -> ExecutionResult`**
- Performs the actual work
- Should not raise for ordinary failures — return `ExecutionResult(success=False, errors=[...])`
- Executor catches anything that escapes anyway

### ExecutionResult
```python
@dataclass
class ExecutionResult:
    success: bool
    output: Any = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    execution_time_seconds: float = 0.0  # Set by Executor, not Action
```

---

## Security Architecture (from `FILESYSTEM_CAPABILITIES.md` §6)

### 1. Path Traversal Protection
- Every path-shaped parameter checked with `is_unsafe_relative_path()` (`executor/action.py`)
- Rejects absolute paths and any `..` segment
- **Cross-platform (MB023.1):** Checks both `PurePosixPath` and `PureWindowsPath` — sandbox boundary identical on every platform
- `anchor` catches drive-relative (`"D:config"`) and root-relative (`"/etc/passwd"`) forms that `is_absolute()` misses on Windows

### 2. Invalid Path Rejection
- Empty/whitespace-only names rejected
- Non-string content where string required rejected
- Structurally malformed payloads rejected (e.g., `folders`/`files` not being lists)
- All in `validate()` before filesystem or Permission System touched

### 3. Overwrite Protection
- `RenameFileAction`/`CopyFileAction`/`MoveFileAction` refuse to clobber existing destination by default
- Fails with structured error unless payload explicitly sets `"overwrite": true`
- Different from `WriteFileAction`/`CreateFolderAction` idempotency (identical content = no-op)

### 4. Dangerous Destination Prevention
- All locations from developer-configured `locations: dict[str, Path]` map (`{"desktop": ..., "downloads": ..., "documents": ...}`)
- Combined with traversal check, no payload can name path outside roots
- `DeleteFolderAction` additionally refuses empty or `"."` path

### 5. Cross-Platform Path Safety (MB023.1)
- `is_unsafe_relative_path()` checks both POSIX and Windows path flavours
- Separator handling: `PurePosixPath("..\\escape").parts` = one opaque segment on POSIX host
- `to_portable_relative_str()` emits forward slashes on every platform for stored history

---

## LocalExecutor (from `executor/executor.py`)

### Purpose
> **LocalExecutor — the only component allowed to perform local actions.**
> Every future local capability registers an Action here and runs through `execute()`. Nothing else in the codebase should touch the filesystem, a shell, or any other local resource directly.

### Key Responsibilities
1. **Action Registry** — `register(action)` maps `action.name` → `Action`
2. **Permission Check** — Own grant key (`self.name`, `action.name`) distinct from Plugin's (ADR-0005 relay pattern)
3. **Validation** — Calls `action.validate(parameters)` before permission check
4. **Execution** — Calls `action.run(parameters)`, catches exceptions, never crashes
4. **Logging** — `ExecutionLogEntry` per invocation (action, start/end, duration, status)
5. **Relay Surface** — `permissions` property exposed so Plugin adapters can relay approval

### Permission Relay (ADR-0005)
- Orchestrator checks Permission System on `(plugin_name, capability)` — consumes grant
- LocalExecutor checks on `(self.name, action.name)` — different key
- Plugin adapter relays approval: `self._executor.permissions.grant(self._executor.name, capability, GrantScope.ONCE)`
- Human never asked twice; Executor's gate stays real for direct callers

---

## Composite Actions (from `FILESYSTEM_CAPABILITIES.md` §3, ADR-0006)

### WorkspaceBootstrapAction Pattern
- Composite Action that orchestrates primitive Actions **through the real `LocalExecutor.execute()` path**
- Never calls another Action's `run()` directly
- Every sub-step independently validated, permission-gated, logged
- No rollback on partial failure — completed steps stay completed (deliberate, ADR-0006)

### Registration Separation
- Primitives: registered in loop over `_PRIMITIVE_ACTION_CLASSES` tuple
- Composites: registered separately (need `LocalExecutor` injected for sub-step relay)
- See `FilesystemPlugin.__init__()` for pattern

---

## Current Implementation Status

| Component | Constitution/Architecture | Implementation Status | Notes |
|-----------|---------------------------|----------------------|-------|
| **Action ABC** | Rule 3, §12.2 | ✅ **IMPLEMENTED** | `executor/action.py` — 6 abstract members |
| **ExecutionResult** | Rule 3 | ✅ **IMPLEMENTED** | `executor/action.py` — success, output, errors, warnings, time |
| **LocalExecutor** | Rule 4, ADR-0005 | ✅ **IMPLEMENTED** | `executor/executor.py` — registry, permission, logging |
| **Action Registration** | Rule 3 | ✅ **IMPLEMENTED** | `register(action)` with duplicate detection |
| **Permission Check (Executor)** | ADR-0005 | ✅ **IMPLEMENTED** | Own grant key (`executor_name`, `action_name`) |
| **Validation Before Permission** | Contract | ✅ **IMPLEMENTED** | `validate()` called before `_permissions.check()` |
| **Structured Failure** | Contract | ✅ **IMPLEMENTED** | `ExecutionResult(success=False, errors=[...])` |
| **Exception Safety** | Contract | ✅ **IMPLEMENTED** | Catches all exceptions, returns structured failure |
| **Execution Logging** | Transparency | ✅ **IMPLEMENTED** | `ExecutionLogEntry` per invocation |
| **Permission Relay Surface** | ADR-0005 | ✅ **IMPLEMENTED** | `permissions` property exposed |
| **Composite Action Pattern** | Rule 6, ADR-0006 | ✅ **IMPLEMENTED** | `WorkspaceBootstrapAction` via `LocalExecutor.execute()` |
| **Cross-Platform Path Safety** | MB023.1 | ✅ **IMPLEMENTED** | `is_unsafe_relative_path()` checks both path flavours |
| **Portable Path Output** | MB023.1 | ✅ **IMPLEMENTED** | `to_portable_relative_str()` emits forward slashes |
| **Filesystem Primitives (11)** | MB005 | ✅ **IMPLEMENTED** | Read/Write/Modify/Delete categories |
| **Filesystem Composite (1)** | MB003 | ✅ **IMPLEMENTED** | `WorkspaceBootstrapAction` |
| **Browser Primitives (9)** | MB022 | ✅ **IMPLEMENTED** | Open/Close/Navigate/Click/Type/Press/Scroll/Wait/Observe |

---

## Design vs Implementation Differences

| Area | Design (Architecture/Constitution) | Implementation | Status |
|------|-----------------------------------|----------------|--------|
| **One Action = One Effect** | Atomic, no god-class | ✅ 11 FS + 9 Browser primitives | ✅ MATCH |
| **Action Contract Minimal** | Name, risk, validate, run | ✅ 6 abstract members | ✅ MATCH |
| **Validation Before Permission** | Contract requirement | ✅ `validate()` before `check()` | ✅ MATCH |
| **Executor Own Permission Key** | ADR-0005 relay pattern | ✅ `(executor_name, action_name)` | ✅ MATCH |
| **Structured Failures** | Never raise ordinary failures | ✅ `ExecutionResult(success=False)` | ✅ MATCH |
| **Executor Catches Exceptions** | Never crash, never leak traceback | ✅ `except Exception` in `execute()` | ✅ MATCH |
| **Execution Logging** | Every invocation logged | ✅ `ExecutionLogEntry` per call | ✅ MATCH |
| **Permission Relay Surface** | Plugin adapter relays approval | ✅ `permissions` property exposed | ✅ MATCH |
| **Composite via Executor** | Rule 6, ADR-0006 | ✅ `WorkspaceBootstrapAction` uses `execute()` | ✅ MATCH |
| **No Rollback on Partial Failure** | Deliberate, ADR-0006 | ✅ Completed steps stay completed | ✅ MATCH |
| **Cross-Platform Path Safety** | MB023.1 | ✅ Checks both PurePosixPath/PureWindowsPath | ✅ MATCH |
| **Portable Path Storage** | Forward slashes always | ✅ `to_portable_relative_str()` | ✅ MATCH |
| **Action Registration Loop** | Declarative, tuple of classes | ✅ `_PRIMITIVE_ACTION_CLASSES` tuple | ✅ MATCH |
| **Composite Separate Registration** | Needs Executor injected | ✅ `WorkspaceBootstrapAction` registered separately | ✅ MATCH |

---

## Open Questions

1. **Action Contract Extensibility** — Current contract has 6 abstract members. Future capability categories (shell, git, VS Code, Obsidian) may need additional contract members (e.g., `timeout`, `retry_policy`, `resource_limits`).

2. **Composite Action Rollback** — Currently no rollback (ADR-0006 deliberate). Future safety-critical composites may need transactional semantics. Named in `FILESYSTEM_CAPABILITIES.md` §7 as "still not solved, named honestly."

3. **Deep Recursive Operations** — Deleting very large folder tree = one `IRREVERSIBLE` action same as small one. No "extra confirmation for big deletion" tier. Named in `FILESYSTEM_CAPABILITIES.md` §7.

4. **SearchFilesAction Cap** — Caps results at 200 matches, reports if capped. Named as real limit, not silently truncated (`FILESYSTEM_CAPABILITIES.md` §7).

5. **Executor Log Unbounded** — `LocalExecutor._log` is unbounded in-memory list, not part of Memory. Would leak in long-running daemon. Flagged in `MEMORY_ARCHITECTURE.md` §11 and `ROADMAP.md`.

6. **CapabilityManifest.input_schema/output_schema Empty** — Declared in frozen `plugins/base.py`, populated by nothing. Planner guesses payload names (MB036 Finding 4, MB037 Finding 3). Top backlog item.

7. **Action Timeout** — No timeout mechanism in Action contract or Executor. Long-running actions (git clone, large copy) could block indefinitely.

8. **Resource Limits** — No CPU/memory/disk limits enforced per Action. Future shell/git actions may need resource governance.

---

## Future Extraction Targets

1. `src/master_agent/executor/action.py` — Action ABC, `ExecutionResult`, `is_unsafe_relative_path()`, `default_locations()`, security helpers
2. `src/master_agent/executor/executor.py` — `LocalExecutor`, `ExecutionLogEntry`, permission relay
3. `src/master_agent/executor/actions/` — All 20+ Action implementations
4. `src/master_agent/executor/actions/browser/` — 9 Browser Action implementations
5. `src/master_agent/executor/actions/workspace_bootstrap.py` — Composite pattern
6. `src/master_agent/plugins/base.py` — `RiskTier`, `PermissionCategory`, `CapabilityManifest`
7. `src/master_agent/permissions/permission_system.py` — `RiskTier` usage in `check()`
8. `docs/adr/0005` — Executor permission relay
9. `docs/adr/0006` — Composite action relay
10. `docs/adr/0009` — PermissionCategory + IRREVERSIBLE grant rule
11. `docs/MISSION_BRIEF_002.md` — Local Executor brief
12. `docs/MISSION_BRIEF_005.md` — Filesystem expansion brief

---

## Wiki Links Added

- `[[KALPAVRIKSHA_VISION_V2.md]]` — Constitution Rule 3, Rule 4, Rule 6, §12.2, §12.3, §5.2
- `[[FOUNDER_CONSTITUTION_FREEZE.md]]` — Freeze record
- `[[FILESYSTEM_CAPABILITIES.md]]` — Action Contract pattern, security, composition
- `[[BROWSER_WORKER_ARCHITECTURE.md]]` — Browser Actions reference
- `[[ARCHITECTURE.md]]` — Implementation map §4.7
- `[[03_universal_executive_operator.md]]` — Operator responsibilities
- `[[04_shared_infrastructure.md]]` — Shared Infrastructure (Permission System)
- `[[10_environment_execution.md]]` — Environment execution patterns
- `[[12_permission_security.md]]` — Permission relay pattern
- `[[13_plugin_system.md]]` — Plugin system (FilesystemPlugin, BrowserPlugin)
- `[[system_overview.md]]` — System overview
- `[[docs/adr/0005]]` — Executor permission relay
- `[[docs/adr/0006]]` — Composite action relay
- `[[docs/adr/0009]]` — PermissionCategory + IRREVERSIBLE grant rule

---

*Document created from verified sources only. No Action Contract redesigned. Terminology preserved exactly. Constitution/Architecture/Implementation/Open Questions separated. Design/implementation differences recorded without reconciliation.*