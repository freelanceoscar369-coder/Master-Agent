# Plugin System Architecture

## Purpose
Documents the plugin architecture that makes every capability — filesystem, browser, model providers, and future Workers — a registered Plugin behind a single contract. The Plugin contract is the universal execution interface.

---

## Frozen Constitution

### Constitution §2.3 (Everything Is a Worker Behind a Capability — FROZEN)
> Reasoning Providers, capabilities, transport adapters — all are Workers behind the same Capability Registry and contract (§5, §12). The core engine is small; almost all capability lives in Workers.

### Constitution §5.1 (Capability Registry — FROZEN)
> **Belongs in Shared Infrastructure because:** queried by Brain's Model Router (Reasoning Provider resolution) and Operator's Orchestrator (execution capability resolution) — same lookup mechanism, two different callers. One registry, one answer, regardless of who asks.

> Today: one component with two indices (plugin identity, capability → plugin). Future capability-resolution policy is EVOLVABLE.

### Constitution §12 (Worker and Plugin Runtime — IMPLEMENTATION DETAIL)

**12.1 Why this is not a separate layer:**
> The prior revision's "Worker Architecture" section stated, in its own first line, that "there is no worker pool or agent swarm in the core" — i.e., it described Plugin Runtime (§4) under a different name. Keeping it as a peer section implied a fourth architectural concern that doesn't structurally exist.

**12.2 Workers are Capabilities' implementations:**
> Every Capability is implemented by a Worker (Action or Plugin, in current terminology) registered on the Operator's Worker Runtime. Adding Worker #N costs one new file; it never means editing the Capability Registry, the Permission System, or the Orchestrator (Rule 3).

**12.3 Composite Workers:**
> A Worker may orchestrate other Workers (e.g., project-bootstrap capability composed from folder-creation and file-write capabilities) — but only through the same Shared Infrastructure Capability Registry and Permission System every other caller uses, relaying its own already-obtained grant down to each sub-step (Rule 6). This is the **single** statement of that rule in this document.

**12.4 Worker Instance:**
> One live, invocable registration of a Worker inside a specific Operator Instance's Worker Runtime — distinguishing "the concept of a capability" from "the specific registered copy of it running inside Operator Instance #3" (§17).

### Constitution Rule 3 (FROZEN)
> **Capability Contract Is Sacred.** Every capability is a Worker behind the Capability Registry. Adding capability #N costs one new file, never an edit to the Registry, Orchestrator, Permission System, or Worker Runtime.

### Constitution Rule 4 (FROZEN)
> **Environment Access Has One Door.** No Brain module, no CLI code, touches an Environment directly. Everything goes through a Worker, via the Operator's Worker Runtime, via an Environment Session (§8.3) the Operator Instance owns.

---

## Plugin Philosophy

### From `FILESYSTEM_CAPABILITIES.md` §1 (Why Capabilities Are Individual Actions)
> Every filesystem operation — read a file, list a directory, rename something, delete something — is its own `Action` class: its own `name`, its own `validate()`, its own `run()`, registered individually on the `LocalExecutor`. Not one `FileManagerAction` with an `operation` parameter switching between `"read"`/`"write"`/`"delete"`/etc.

**Three reasons:**
1. **Risk tier per operation** — reading and deleting need different permission gates
2. **Validation per operation** — avoids "long if/else chain" moved from Plugin into Action
3. **Scalability** — adding capability #50 means writing a new file, not editing existing one to add 50th branch

### From `FILESYSTEM_CAPABILITIES.md` §4 (Future Capability Growth)
> Adding action #12 (or #200) never means:
> - Editing an existing Action
> - Editing `PermissionSystem` — every new Action declares from pre-existing `RiskTier` and `PermissionCategory` vocabularies
> - Editing `FilesystemPlugin`'s dispatch logic — registration is a loop over declared Action classes
> - Growing `FilesystemPlugin` into something it isn't — new capability category (shell, git) = new Plugin, new Action family

### From `BROWSER_WORKER_ARCHITECTURE.md` §1
> This Mission Brief proves the **Universal Executive Operator architecture** by implementing its first real Worker against a real Environment. Every decision made so that a future Desktop Worker, Terminal Worker, REST Worker, or MCP Worker can copy this file's shape and change only what's genuinely browser-specific.

---

## Plugin Contract

### Core Interface (`src/master_agent/plugins/base.py`)

```python
class Plugin(ABC):
    @property
    @abstractmethod
    def manifest(self) -> PluginManifest: ...

    @abstractmethod
    def invoke(self, capability: str, payload: dict[str, Any]) -> InvocationResult:
        """Execute one capability. Must not perform anything above READ_ONLY risk
        without having already been cleared by the Permission System."""
```

### Manifest Structure

**`PluginManifest`** — describes plugin as a whole:
- `name: str` — plugin identifier (e.g., `"filesystem"`, `"browser"`)
- `version: str` — semantic version
- `capabilities: list[CapabilityManifest]` — what this plugin exposes

**`CapabilityManifest`** — describes one capability:
- `name: str` — capability identifier (e.g., `"read_file"`, `"navigate"`)
- `description: str` — human-readable
- `risk_tier: RiskTier` — `READ_ONLY` | `REVERSIBLE_WRITE` | `IRREVERSIBLE`
- `input_schema: dict` — declared but **not populated** (see Open Questions)
- `output_schema: dict` — declared but **not populated**
- `permission_category: PermissionCategory | None` — `READ` | `WRITE` | `MODIFY` | `DELETE` | `SYSTEM`

**`InvocationResult`** — what `invoke()` returns:
- `success: bool`
- `output: Any`
- `error: str | None`
- `execution_time_seconds: float` — set by Plugin (forwarded from Executor)

### ModelProvider Specialization
```python
class ModelProvider(Plugin):
    CAPABILITY_NAME = "generate_text"

    @abstractmethod
    def generate(self, prompt: str, context: dict | None, **opts) -> str: ...

    def invoke(self, capability: str, payload: dict) -> InvocationResult:
        if capability != self.CAPABILITY_NAME:
            return InvocationResult(success=False, error=f"unknown capability: {capability}")
        text = self.generate(payload.get("prompt", ""), payload.get("context"))
        return InvocationResult(success=True, output=text)
```

---

## Capability Registration

### PluginRegistry (`src/master_agent/plugins/registry.py`)
```python
class PluginRegistry:
    def __init__(self):
        self._plugins: dict[str, Plugin] = {}                    # plugin_name -> Plugin
        self._capability_index: dict[str, list[str]] = {}        # capability -> [plugin_names]

    def register(self, plugin: Plugin) -> None:
        manifest = plugin.manifest
        self._plugins[manifest.name] = plugin
        for cap in manifest.capabilities:
            self._capability_index.setdefault(cap.name, []).append(manifest.name)

    def find_for_capability(self, capability: str) -> list[Plugin]:
        return [self._plugins[name] for name in self._capability_index.get(capability, [])]

    def risk_tier_for(self, plugin_name: str, capability: str) -> RiskTier:
        # Returns risk tier from manifest
```

**Key Properties:**
- Indexes by **capability**, not plugin name — Orchestrator resolves "who can do X" without caring which plugin
- `find_for_capability()` returns **list** — multiple plugins could expose same capability (Founder Edition: takes first)
- `risk_tier_for()` used by Orchestrator for permission check
- `all_plugins()` added for Mission Control discovery (read-only accessor, extends contract not routes around it)

### Declarative Registration Pattern (Mission Brief 005)

**FilesystemPlugin:**
```python
_PRIMITIVE_ACTION_CLASSES: tuple[type[Action], ...] = (
    CreateFolderAction, WriteFileAction, ReadFileAction, ...  # 11 primitives
)

def __init__(self, executor: LocalExecutor, locations: dict[str, Path] | None = None):
    for action_cls in _PRIMITIVE_ACTION_CLASSES:
        self._register(action_cls(locations))
    self._register(WorkspaceBootstrapAction(executor, locations))  # composite separate

def _register(self, action: Action):
    self._executor.register(action)           # Register on Executor
    self._actions[action.name] = action       # Keep reference for manifest

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
```

**BrowserPlugin** — identical pattern:
```python
_ACTION_CLASSES: tuple[type[Action], ...] = (
    OpenBrowserSessionAction, CloseBrowserSessionAction, NavigateAction, ...
)

def __init__(self, executor: LocalExecutor, sessions: BrowserSessionManager):
    for action_cls in _ACTION_CLASSES:
        self._register(action_cls(sessions))  # Actions need BrowserSessionManager
```

**Adding capability #N = one new Action class in tuple, never edit to Plugin logic.**

---

## Action / Worker / Verifier Relationship

### Layer Map (from `BROWSER_WORKER_ARCHITECTURE.md` §3)

| Constitution Concept | Implementation |
|---------------------|----------------|
| Worker (§12) | 9 Browser Actions + `BrowserPlugin` |
| Environment Session (§8.3) | `BrowserSession` / `BrowserSessionManager` |
| Observation (§10.2) | `BrowserObservation` / `normalize_observation()` |
| Verification (§10) | `Verifier` ABC (generic) + `BrowserVerifier` (~10 lines) |
| Evidence (§9.2) | `Evidence` / `ExpectedOutcome` / `ObservationCheck` / `Verdict` |
| Audit (§5.6) | `AuditRecord` / `AuditLog` (generic) |
| Worker Lifecycle Facade | `BrowserWorker` — sequences execute → verify → audit, decides nothing |

### Execution Paths (Two Surfaces, `BROWSER_WORKER_ARCHITECTURE.md` §11)

1. **`BrowserPlugin`** — thin `Plugin` adapter for Orchestrator/Registry/Permission path
2. **`BrowserWorker`** — Constitution-complete facade (execute → verify → audit)

**Both paths execute through identical `LocalExecutor` + 9 `Action` classes** — single implementation, two callers.

### Verifier Relationship
- **Generic `Verifier` ABC** (`verification/verifier.py`) — zero Environment imports
- **`BrowserVerifier`** (`plugins/browser_verifier.py`) — implements only `capture_observation_dict()`
- **Shared logic:** `verify()` (concrete), `evaluate_checks()` (pure), `Evidence` construction
- **Single observation function:** `normalize_observation()` called by both `ObserveBrowserAction` and `BrowserVerifier`

---

## Permission Integration

### Three-Layer Permission Check (from `FILESYSTEM_CAPABILITIES.md` §19, `permission_system.py`)

1. **Orchestrator** — `PermissionSystem.check(plugin_name, capability, risk_tier)` before `plugin.invoke()`
2. **Plugin Adapter** — Relays approval to Executor's grant key:
   ```python
   self._executor.permissions.grant(self._executor.name, capability, GrantScope.ONCE)
   ```
3. **LocalExecutor** — Own grant key check (ADR-0005 relay pattern)

### Relay Pattern (ADR-0005, ADR-0006)
- **Orchestrator → Executor:** Outer approval carried down to inner grant key
- **Composite → Sub-steps:** Already-obtained grant relayed to each sub-step
- **Plugin → Executor:** `grant_permission` callable in `PluginGateway` invoked before each `invoke()`

### Runtime ApprovalGate (MB028.0)
- Single funnel at `RuntimeEngine._handle_task()` before any gateway touched
- `ApprovalGate` protocol defined in `runtime/` — no Permission System dependency
- **Fail closed:** No gate ⇒ nothing runs (not even `READ_ONLY`)

---

## Current Implementation Status

| Component | Constitution/Architecture | Implementation Status | Notes |
|-----------|---------------------------|----------------------|-------|
| **Plugin Contract** | FROZEN (Rule 3) | ✅ **IMPLEMENTED** | `Plugin` ABC, `ModelProvider` specialization |
| **Manifest Types** | FROZEN | ✅ **IMPLEMENTED** | `PluginManifest`, `CapabilityManifest`, `InvocationResult` |
| **PluginRegistry** | FROZEN (§5.1) | ✅ **IMPLEMENTED** | Capability index, risk_tier lookup |
| **FilesystemPlugin** | FROZEN (MB005) | ✅ **IMPLEMENTED** | 14 capabilities, declarative registration |
| **BrowserPlugin** | FROZEN (MB022) | ✅ **IMPLEMENTED** | 9 capabilities, identical pattern |
| **ModelRouter** | FROZEN (MB032) | ✅ **IMPLEMENTED** | Uses `ProviderSelector` protocol, asks Broker |
| **Declarative Registration** | FROZEN (Rule 3) | ✅ **IMPLEMENTED** | Tuple of Action classes, loop-based |
| **Composite Actions** | FROZEN (Rule 6) | ✅ **IMPLEMENTED** | `WorkspaceBootstrapAction` separate from primitives |
| **Permission Relay** | FROZEN (ADR-0005) | ✅ **IMPLEMENTED** | Plugin → Executor grant relay |
| **Runtime ApprovalGate** | MB028.0 | ✅ **IMPLEMENTED** | Protocol in `runtime/`, fail-closed |
| **Plugin Discovery** | EVOLVABLE | ✅ **IMPLEMENTED** | `all_plugins()` for Mission Control |
| **Capability Selection Policy** | EVOLVABLE | ⏳ **RESERVED** | Founder Edition: takes first candidate |
| **input_schema/output_schema** | DECLARED | ❌ **NOT POPULATED** | Declared in `base.py`, populated by nothing |
| **Remote/Out-of-Process Plugins** | FUTURE | ❌ **NOT IMPLEMENTED** | Local Python objects only (ADR-0004) |

---

## Open Questions

1. **CapabilityManifest.input_schema/output_schema Empty** — Declared in frozen `plugins/base.py`, populated by nothing. Planner guesses payload names (MB036 Finding 4, MB037 Finding 3). Top backlog item.

2. **Capability Selection Policy** — `find_for_capability()` returns list; Founder Edition takes first. Multiple providers for same capability need selection policy (EVOLVABLE per Constitution).

3. **Remote/Out-of-Process Plugins** — Current architecture: local Python objects only. `register_executive()` in Mission Control accepts non-Plugin Executives, but Plugin system itself is local-only.

4. **Two Plugin Integration Surfaces** — `BrowserPlugin` (Orchestrator path) + `BrowserWorker` (Constitution-complete facade). Not yet unified into single generic Verification dispatch in Orchestrator.

5. **Plugin Versioning** — `PluginManifest.version` exists but no version negotiation or compatibility checking implemented.

6. **ModelProvider as Plugin** — `ModelProvider` extends `Plugin` with `generate()` specialization. `invoke()` delegates to `generate()`. Is this the right long-term pattern for all Provider types?

---

## Design vs Implementation Differences

| Area | Design (Architecture/Constitution) | Implementation | Status |
|------|-----------------------------------|----------------|--------|
| **One Plugin = One Capability Family** | Each Plugin exposes related capabilities | ✅ Filesystem (14), Browser (9) | ✅ MATCH |
| **Declarative Registration** | Tuple of Action classes, loop-based | ✅ Both Plugins use identical pattern | ✅ MATCH |
| **Capability Index by Capability** | Registry indexes by capability name | ✅ `_capability_index[capability] = [plugin_names]` | ✅ MATCH |
| **Manifest from Actions** | `manifest` property builds from `_actions` | ✅ Both Plugins | ✅ MATCH |
| **Permission Relay** | Plugin → Executor grant relay | ✅ `grant_permission` in `invoke()` | ✅ MATCH |
| **Composite Separate from Primitives** | WorkspaceBootstrapAction registered separately | ✅ FilesystemPlugin | ✅ MATCH |
| **ModelProvider as Plugin** | Specialization with `generate()` | ✅ `invoke()` delegates to `generate()` | ✅ MATCH |
| **Plugin Discovery for MC** | `all_plugins()` read-only accessor | ✅ Added for MIT-001 | ✅ MATCH |
| **Capability Selection Policy** | Multiple providers → selection policy | ⏳ Founder Edition: first only | ⏳ RESERVED |
| **input_schema/output_schema** | Declared in CapabilityManifest | ❌ Populated by nothing | ❌ MISSING |
| **Remote Plugins** | Architecture allows | ❌ Local-only (ADR-0004) | ❌ MISSING |
| **Two Integration Surfaces** | BrowserPlugin + BrowserWorker | ⚠️ Two surfaces side by side | 📝 DOCUMENTED |
| **Plugin Versioning** | version field in manifest | ⚠️ No negotiation/checking | 📝 DOCUMENTED |

---

## Future Extraction Targets

1. `src/master_agent/plugins/base.py` — Plugin ABC, ModelProvider, RiskTier, PermissionCategory, manifests
2. `src/master_agent/plugins/registry.py` — PluginRegistry, capability index
3. `src/master_agent/plugins/filesystem_plugin.py` — FilesystemPlugin, 14 capabilities
3. `src/master_agent/plugins/browser_plugin.py` — BrowserPlugin, 9 capabilities
4. `src/master_agent/plugins/model_router.py` — ModelRouter, ProviderSelector protocol
5. `src/master_agent/plugins/providers/` — Provider implementations (when added)
6. `src/master_agent/plugins/browser_worker.py` — BrowserWorker facade
7. `src/master_agent/plugins/browser_verifier.py` — BrowserVerifier
8. `tests/test_plugin_registry.py` — Registry tests
9. `tests/test_filesystem_plugin.py` / `test_browser_plugin.py` — Plugin integration tests
10. `docs/adr/0003` — Plugin contract decision
11. `docs/adr/0004` — Local-first plugin discovery

---

## Wiki Links Added

- `[[KALPAVRIKSHA_VISION_V2.md]]` — Constitution §2.3, §5.1, §12, Rule 3, Rule 4
- `[[FOUNDER_CONSTITUTION_FREEZE.md]]` — Freeze record
- `[[FILESYSTEM_CAPABILITIES.md]]` — Action Contract, registration pattern
- `[[BROWSER_WORKER_ARCHITECTURE.md]]` — Worker/Environment Session/Verification mapping
- `[[ARCHITECTURE.md]]` — Implementation map §4.6, §4.7
- `[[03_universal_executive_operator.md]]` — Operator responsibilities
- `[[04_shared_infrastructure.md]]` — Shared Infrastructure (Capability Registry)
- `[[10_environment_execution.md]]` — Environment execution patterns
- `[[11_verification_system.md]]` — Verification system
- `[[12_permission_security.md]]` — Permission integration
- `[[system_overview.md]]` — System overview
- `[[docs/adr/0003]]` — Plugin contract
- `[[docs/adr/0004]]` — Local-first plugin discovery
- `[[docs/adr/0005]]`–`[[docs/adr/0006]]` — Relay pattern

---

*Document created from verified sources only. No plugin architecture redesigned. Terminology preserved exactly. Constitution/Architecture/Implementation/Open Questions separated. Design/implementation differences recorded without reconciliation.*