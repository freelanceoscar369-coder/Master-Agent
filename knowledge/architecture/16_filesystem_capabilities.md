# Filesystem Capability Architecture

## Purpose
Documents the Filesystem capability family — the first and most mature capability implementation in Kalpavriksha, providing 14 distinct filesystem operations through the Action Contract pattern.

---

## Frozen Constitution

### Constitution Rule 3 (FROZEN)
> **Capability Contract Is Sacred.** Every capability is a Worker behind the Capability Registry. Adding capability #N costs one new file, never an edit to the Registry, Orchestrator, Permission System, or Worker Runtime.

### Constitution Rule 4 (FROZEN)
> **Environment Access Has One Door.** No Brain module, no CLI code, touches an Environment directly. Everything goes through a Worker, via the Operator's Worker Runtime, via an Environment Session the Operator Instance owns.

### Constitution §2.3 (Everything Is a Worker Behind a Capability — FROZEN)
> Reasoning Providers, capabilities, transport adapters — all are Workers behind the same Capability Registry and contract (§5, §12). The core engine is small; almost all capability lives in Workers.

### Constitution §12.2 (IMPLEMENTATION DETAIL)
> Every Capability is implemented by a Worker (Action or Plugin, in current terminology) registered on the Operator's Worker Runtime. Adding Worker #N costs one new file; it never means editing the Capability Registry, the Permission System, or the Orchestrator.

---

## Architecture Design

### From `FILESYSTEM_CAPABILITIES.md` §1 (Why Capabilities Are Individual Actions)
> Every filesystem operation — read a file, list a directory, rename something, delete something — is its own `Action` class: its own `name`, its own `validate()`, its own `run()`, registered individually on the `LocalExecutor`. Not one `FileManagerAction` with an `operation` parameter switching between `"read"`/`"write"`/`"delete"`/etc.

**Three reasons this isn't a style preference:**
1. **Risk tier per operation** — reading a file and deleting a folder would need the same permission gate (wrong — deleting needs strictly harder approval)
2. **Validation per operation** — avoids the exact "long if/else chain" moved from `FilesystemPlugin` into the Action
3. **Scalability** — adding capability #50 means writing a new file, not editing an existing one to add a 50th branch

### From `FILESYSTEM_CAPABILITIES.md` §2 (Why Actions Remain Atomic)
> Every Action does exactly one filesystem operation:
- `ReadFileAction` reads — it does not also check existence first and branch on the result
- `DeleteFileAction` deletes a file and refuses to touch a directory (`DeleteFolderAction` handles directories)
- `RenameFileAction` only renames within the same directory (`MoveFileAction` crosses directories)

**Atomicity means** "one Action, one clearly-scoped effect" — not database-transaction atomicity. The payoff: each Action's `validate()`/`run()` stays small enough to read completely, each Action's risk tier is unambiguous, and each Action can be tested/reused/reasoned about independently.

### From `FILESYSTEM_CAPABILITIES.md` §3 (Why Composition Over Large Actions)
> `WorkspaceBootstrapAction` (Mission Brief 003) is the model: a composite Action that orchestrates primitive Actions **through the real `LocalExecutor.execute()` path** — never by calling another Action's `run()` directly — so every sub-step stays independently validated, permission-gated, and logged.

**The alternative** — one large `Action` that does "bootstrap a project, but also handle deletion, but also handle renames" — fails the moment a mission needs a *different* combination of the same primitives. Small primitives compose into arbitrarily many future combinations; a large Action only ever does the combination it was written for.

### From `FILESYSTEM_CAPABILITIES.md` §4 (Future Capability Growth)
> Adding action #12 (or #200) never means:
- Editing an existing Action
- Editing `PermissionSystem` — every new Action declares from pre-existing `RiskTier` and `PermissionCategory` vocabularies
- Editing `FilesystemPlugin`'s dispatch logic — registration is a loop over declared Action classes
- Growing `FilesystemPlugin` into something it isn't — new capability category (shell, git) = new Plugin, new Action family

---

## Capability Inventory

### Read Category (`READ_ONLY`, `PermissionCategory.READ`)
| Action | Capability Name | Description |
|--------|-----------------|-------------|
| `ReadFileAction` | `read_file` | Read file contents as text |
| `ListDirectoryAction` | `list_directory` | List directory contents |
| `SearchFilesAction` | `search_files` | Search for files matching pattern |
| `FileExistsAction` | `file_exists` | Check if file exists |
| `DirectoryExistsAction` | `directory_exists` | Check if directory exists |

**All `READ_ONLY`** — `PermissionSystem.check()` short-circuits unconditionally, never prompts for approval.

### Write Category (`REVERSIBLE_WRITE`, `PermissionCategory.WRITE`)
| Action | Capability Name | Description |
|--------|-----------------|-------------|
| `WriteFileAction` | `write_file` | Write text to file (create or overwrite) |
| `AppendFileAction` | `append_file` | Append text to existing file |

### Modify Category (`REVERSIBLE_WRITE`, `PermissionCategory.MODIFY`)
| Action | Capability Name | Description |
|--------|-----------------|-------------|
| `RenameFileAction` | `rename_file` | Rename file within same directory |
| `CopyFileAction` | `copy_file` | Copy file to new location |
| `MoveFileAction` | `move_file` | Move file to new location |

**Overwrite protection:** Refuse to clobber existing destination by default — fails with structured error unless `"overwrite": true` in payload.

### Delete Category (`IRREVERSIBLE`, `PermissionCategory.DELETE`)
| Action | Capability Name | Description |
|--------|-----------------|-------------|
| `DeleteFileAction` | `delete_file` | Delete a file |
| `DeleteFolderAction` | `delete_folder` | Delete a directory (recursive) |

**Critical rule (ADR-0009):** `ALWAYS_FOR_CAPABILITY` grant **never satisfies** an `IRREVERSIBLE` check — only `ONCE` or `THIS_SESSION` can. Destructive actions require fresh decision every time.

### Composite (`REVERSIBLE_WRITE`, varies)
| Action | Capability Name | Description |
|--------|-----------------|-------------|
| `CreateFolderAction` | `create_folder` | Create directory (idempotent: already exists = no-op) |
| `WorkspaceBootstrapAction` | `workspace_bootstrap` | Create folder + write files (composite via `LocalExecutor.execute()`) |

---

## Security Architecture (from `FILESYSTEM_CAPABILITIES.md` §6)

### 1. Path Traversal Protection
- Every path-shaped parameter checked with `is_unsafe_relative_path()` (`executor/action.py`)
- Rejects absolute paths and any `..` segment
- **Cross-platform (MB023.1):** Checks both `PurePosixPath` and `PureWindowsPath` — sandbox boundary identical on every platform

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
- All locations from developer-configured `locations: dict[str, Path]` map (`{"desktop": ..., "downloads": ..., "documents": ...}` by default)
- Combined with traversal check, no payload can name path outside roots
- `DeleteFolderAction` additionally refuses empty or `"."` path

### 5. Cross-Platform Path Safety (MB023.1)
- `is_unsafe_relative_path()` checks both POSIX and Windows path flavours
- `to_portable_relative_str()` emits forward slashes on every platform for stored history

---

## Plugin Integration

### FilesystemPlugin (from `src/master_agent/plugins/filesystem_plugin.py`)
```python
class FilesystemPlugin(Plugin):
    def __init__(self, executor: LocalExecutor, locations: dict[str, Path] | None = None):
        self._executor = executor
        self._actions: dict[str, Action] = {}

        for action_cls in _PRIMITIVE_ACTION_CLASSES:
            self._register(action_cls(locations))

        # Composite registered separately (needs Executor injected)
        self._register(WorkspaceBootstrapAction(executor, locations))

    def _register(self, action: Action):
        self._executor.register(action)
        self._actions[action.name] = action

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="filesystem",
            version="0.5.0",
            capabilities=[CapabilityManifest(
                name=action.name,
                description=action.description,
                risk_tier=action.risk_tier,
                permission_category=action.permission_category,
            ) for action in self._actions.values()],
        )

    def invoke(self, capability: str, payload: dict) -> InvocationResult:
        # Relay approval to Executor's grant key
        self._executor.permissions.grant(self._executor.name, capability, GrantScope.ONCE)
        result = self._executor.execute(capability, payload)
        # ... map ExecutionResult to InvocationResult
```

### Declarative Registration
- `_PRIMITIVE_ACTION_CLASSES`: tuple of 11 Action classes
- Loop registers each on Executor and builds manifest
- Composite (`WorkspaceBootstrapAction`) registered separately (needs Executor for sub-step relay)
- Adding capability #N = one new class in tuple, never edit to Plugin logic

---

## Permission Strategy (from `FILESYSTEM_CAPABILITIES.md` §5)

### Two Axes (Kept Separate)

**RiskTier** (gating mechanism):
- `READ_ONLY` — never prompts, short-circuits
- `REVERSIBLE_WRITE` — grants: `ONCE`, `THIS_SESSION`, `ALWAYS_FOR_CAPABILITY`
- `IRREVERSIBLE` — **`ALWAYS_FOR_CAPABILITY` never satisfies** (ADR-0009)

**PermissionCategory** (human-facing classification):
- `READ` | `WRITE` | `MODIFY` | `DELETE` | `SYSTEM`
- Answers "what kind of thing is this" for human approving
- Never consulted by `check()`'s gating logic (driven by `RiskTier` alone)

### Mapping
| Category | Risk Tier | Actions |
|----------|-----------|---------|
| Read | `READ_ONLY` | `read_file`, `list_directory`, `search_files`, `file_exists`, `directory_exists` |
| Write | `REVERSIBLE_WRITE` | `write_file`, `append_file` |
| Modify | `REVERSIBLE_WRITE` | `rename_file`, `copy_file`, `move_file` |
| Delete | `IRREVERSIBLE` | `delete_file`, `delete_folder` |

---

## Conversation Reachability (from `FILESYSTEM_CAPABILITIES.md` §9)

`cli.py`'s intent parser reaches 9 of 14 capabilities:
- `read_file`, `list_directory`, `search_files`
- `rename_file`, `copy_file`, `move_file`
- `delete_file`, `delete_folder`
- Pre-existing: `create_folder`, `workspace_bootstrap`

**Not yet reachable:** `file_exists`, `directory_exists`, `append_file` — real, tested Actions with no `cli.py` phrasing yet (brief's examples didn't call for them).

All 9 reachable capabilities represented by single generic `ParsedActionIntent` dataclass rather than 9 hand-written ones — same "avoid long if/else chains, design for many" principle applied to intent parsing.

---

## Current Implementation Status

| Component | Architecture Status | Implementation Status | Notes |
|-----------|---------------------|----------------------|-------|
| **11 Primitive Actions** | MB005 | ✅ **IMPLEMENTED** | Read (5), Write (2), Modify (3), Delete (2) |
| **2 Composite Actions** | MB003, MB005 | ✅ **IMPLEMENTED** | `create_folder`, `workspace_bootstrap` |
| **FilesystemPlugin** | MB005 | ✅ **IMPLEMENTED** | Declarative registration, 14 capabilities |
| **Permission Strategy** | MB005 | ✅ **IMPLEMENTED** | Two axes, IRREVERSIBLE rule |
| **Security Helpers** | MB005, MB023.1 | ✅ **IMPLEMENTED** | Traversal, overwrite, sandboxing |
| **Cross-Platform Path Safety** | MB023.1 | ✅ **IMPLEMENTED** | Dual path flavour checks |
| **Conversation Reachability** | MB005 | ⚠️ **PARTIAL** | 9/14 capabilities reachable |
| **CapabilityManifest.input_schema** | Declared | ❌ **NOT POPULATED** | Populated by nothing (top backlog) |

---

## Design vs Implementation Differences

| Area | Design (Architecture/Constitution) | Implementation | Status |
|------|-----------------------------------|----------------|--------|
| **One Action = One Effect** | Atomic primitives | ✅ 11 primitives + 2 composites | ✅ MATCH |
| **Declarative Registration** | Tuple of Action classes | ✅ `_PRIMITIVE_ACTION_CLASSES` tuple | ✅ MATCH |
| **Composite Separate** | Needs Executor for relay | ✅ `WorkspaceBootstrapAction` separate | ✅ MATCH |
| **Permission Two Axes** | RiskTier + PermissionCategory | ✅ Both implemented, orthogonal | ✅ MATCH |
| **IRREVERSIBLE Rule** | ALWAYS_FOR_CAPABILITY never satisfies | ✅ Enforced in `PermissionSystem.check()` | ✅ MATCH |
| **Overwrite Protection** | Refuse clobber unless overwrite=true | ✅ Implemented in Modify actions | ✅ MATCH |
| **Sandboxing** | Configured location roots | ✅ `default_locations()` + traversal check | ✅ MATCH |
| **Cross-Platform Paths** | MB023.1 dual flavour check | ✅ Both PurePosixPath/PureWindowsPath | ✅ MATCH |
| **Conversation Reachability** | 9/14 capabilities | ⚠️ 3 not yet reachable | ⚠️ PARTIAL |
| **input_schema/output_schema** | Declared in CapabilityManifest | ❌ Populated by nothing | ❌ MISSING |

---

## Open Questions

1. **CapabilityManifest.input_schema/output_schema Empty** — Declared in frozen `plugins/base.py`, populated by nothing. Planner guesses payload names (MB036 Finding 4, MB037 Finding 3). Top backlog item.

2. **Filesystem Verifier Missing** — No independent Verification for Filesystem capabilities. ExecutionResult trusted without re-observation. Constitution §10 requires Verification for all.

3. **No Transactional Rollback for Composites** — `WorkspaceBootstrapAction` partial failure leaves completed steps completed (ADR-0006 deliberate). Named in `FILESYSTEM_CAPABILITIES.md` §7 as "still not solved, named honestly."

4. **Deep Recursive Operations** — Deleting very large folder tree = one `IRREVERSIBLE` action same as small one. No "extra confirmation for big deletion" tier. Named in `FILESYSTEM_CAPABILITIES.md` §7.

5. **SearchFilesAction Cap** — Caps results at 200 matches, reports if capped. Named as real limit, not silently truncated (`FILESYSTEM_CAPABILITIES.md` §7).

6. **Executor Log Unbounded** — `LocalExecutor._log` unbounded in-memory list, not part of Memory. Would leak in long-running daemon. Flagged in `MEMORY_ARCHITECTURE.md` §11.

7. **Filesystem Verifier Not Implemented** — Constitution §10 requires Verification for all capabilities. No `FilesystemVerifier` exists.

---

## Future Extraction Targets

1. `src/master_agent/executor/actions/` — All 13 Filesystem Action implementations
2. `src/master_agent/executor/actions/workspace_bootstrap.py` — Composite pattern
3. `src/master_agent/plugins/filesystem_plugin.py` — Plugin adapter
4. `src/master_agent/cli.py` — Intent parser (`ParsedActionIntent`, `_INTENT_PATTERNS`)
5. `tests/test_read_actions.py`, `test_write_actions.py` — Action tests
6. `docs/adr/0006` — Composite action relay
7. `docs/adr/0009` — PermissionCategory + IRREVERSIBLE grant rule

---

## Wiki Links Added

- `[[KALPAVRIKSHA_VISION_V2.md]]` — Constitution Rule 3, Rule 4, §12.2
- `[[FOUNDER_CONSTITUTION_FREEZE.md]]` — Freeze record
- `[[FILESYSTEM_CAPABILITIES.md]]` — Primary source document
- `[[ARCHITECTURE.md]]` — Implementation map §4.7
- `[[03_universal_executive_operator.md]]` — Operator responsibilities
- `[[04_shared_infrastructure.md]]` — Shared Infrastructure (Permission System)
- `[[10_environment_execution.md]]` — Environment execution patterns
- `[[12_permission_security.md]]` — Permission strategy
- `[[13_plugin_system.md]]` — Plugin system (FilesystemPlugin)
- `[[15_action_contract.md]]` — Action Contract
- `[[system_overview.md]]` — System overview
- `[[docs/adr/0006]]` — Composite action relay
- `[[docs/adr/0009]]` — PermissionCategory + IRREVERSIBLE grant rule

---

*Document created from verified sources only. No Filesystem capability architecture redesigned. Terminology preserved exactly. Constitution/Architecture/Implementation/Open Questions separated. Design/implementation differences recorded without reconciliation.*