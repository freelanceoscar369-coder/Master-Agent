# Capability Contract & Index Architecture

## Purpose
Documents the machine-readable capability contract system (Mission Brief 039) that enables the Planner to know exactly what arguments a capability takes, what it returns, and what calling it does to the world — solving the "Planner guesses payload names" problem (MB036 Finding 4).

---

## Frozen Constitution

### Constitution Rule 3 (FROZEN)
> **Capability Contract Is Sacred.** Every capability is a Worker behind the Capability Registry. Adding capability #N costs one new file, never an edit to the Registry, Orchestrator, Permission System, or Worker Runtime.

### Constitution §12.2 (IMPLEMENTATION DETAIL)
> **Workers are Capabilities' implementations** — Every Capability is implemented by a Worker registered on the Operator's Worker Runtime. Adding Worker #N costs one new file; never means editing the Capability Registry, the Permission System, or the Orchestrator.

### Constitution Rule 4 (FROZEN)
> **Environment Access Has One Door.** No Brain module, no CLI code, touches an Environment directly. Everything goes through a Worker, via the Operator's Worker Runtime, via an Environment Session the Operator Instance owns.

### Constitution §5.1 (Capability Registry — FROZEN)
> Queried by the Brain's Model Router and the Operator's Orchestrator — same lookup mechanism, two different callers. One registry, one answer.

---

## Architecture Design

### From `capabilities/contract.py` Module Docstring
> **MB036 and MB037 built a Planner that names the right capability and then gets its arguments wrong, because the only thing published about a capability is a sentence of prose.** `Filesystem.CreateFolder` requires `name`; the Planner wrote `path`. The plan read perfectly and could not run.

> **A contract is the machine-readable answer to *"what does this capability actually take, and what does calling it do to the world?"***

### Key Design Principles

**1. Metadata Only — No Execution**
> Nothing in this package executes anything, imports an executor, or holds a reference to a plugin instance. A contract describes; something else performs. Separation asserted by test — a registry that could invoke would become a second execution path (Rule 4).

**2. Unknown Stays UNKNOWN**
> Latency class, retryability, idempotency default to `UNKNOWN` and are **never inferred from something else**. A capability that has not declared its idempotency is not "probably idempotent"; it is unknown, and a caller that needs to know must find out rather than be told a guess.

**2a. Side Effects Exception**
> Side effects are the one exception — derived from `RiskTier` because `RiskTier` already *is* a statement about what calling something does to the world, declared by the Action author and gated by the Permission System.

---

## Two-Tier Architecture (from `capabilities/index.py`)

### The Latency Problem
> A planning prompt carries the whole catalogue — MB038 measured: 1,095 prompt tokens and 78s prefill for 26 capabilities. Putting every field of every full contract into that prompt would multiply the number that already dominates planning latency.

### Two Tiers
| Tier | Purpose | When Loaded |
|------|---------|-------------|
| **IndexEntry** | Always loaded, one line each, goes in the prompt | Startup |
| **CapabilityContract** | Loaded on demand, for the one capability being checked | On demand |

> **So the index carries what the Planner needs to *choose* and to *fill in arguments*, and the full contract is fetched only when something asks a question the summary cannot answer.**

**Immutable Once Built:** Entries are a frozen mapping; loader consulted at most once per capability. A registry that could change underneath a plan would make the plan's premises unreproducible (MB032's replay guarantee depends on the opposite).

---

## Core Types (from `capabilities/contract.py`)

### Vocabulary Constants
```python
UNKNOWN = "unknown"

# Side Effects (derived from RiskTier)
NO_EFFECT = "none"
REVERSIBLE = "reversible"
IRREVERSIBLE = "irreversible"
SIDE_EFFECT_BY_RISK = {
    "read_only": NO_EFFECT,
    "reversible_write": REVERSIBLE,
    "irreversible": IRREVERSIBLE,
}

# Latency Classes (coarse buckets, not milliseconds)
INSTANT = "instant"
FAST = "fast"
SLOW = "slow"
VERY_SLOW = "very_slow"

# Retryability
RETRY_SAFE = "safe"
RETRY_UNSAFE = "unsafe"
RETRY_CONDITIONAL = "conditional"

# Idempotency
IDEMPOTENT = "idempotent"
NOT_IDEMPOTENT = "not_idempotent"

# Field Types (closed, small set)
STRING = "string"
INTEGER = "integer"
NUMBER = "number"
BOOLEAN = "boolean"
OBJECT = "object"
ARRAY = "array"
```

### Core Data Structures

#### `FieldSpec` — One Argument
```python
@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: str = STRING
    required: bool = False
    description: str = ""
    choices: tuple[str, ...] = ()  # empty = unconstrained
    default: Any = None            # None = no default, field absent
```

#### `Schema` — Payload Shape (In or Out)
```python
@dataclass(frozen=True)
class Schema:
    fields: tuple[FieldSpec, ...] = ()
    known: bool = True      # False = nobody has published this shape
    closed: bool = True     # True = exhaustive list; unexpected key = caller error
    
    @staticmethod
    def unknown() -> Schema:
        return Schema(fields=(), known=False, closed=False)
    
    def problems(self, payload: dict) -> tuple[str, ...]:
        """Structural problems only — names, presence, types.
        Never checks whether a path exists, a name is safe, or a folder exists.
        Those are the Action's own validate(), which runs against the real world."""
```

#### `Permissions` — What Calling Needs from Founder
```python
@dataclass(frozen=True)
class Permissions:
    risk_tier: str = UNKNOWN
    category: str = UNKNOWN
    approval_required: bool = False  # Derived from risk_tier by same rule Permission System applies
```

#### `CapabilityContract` — Everything Published About One Capability
```python
@dataclass(frozen=True)
class CapabilityContract:
    canonical_id: str              # e.g., "Filesystem.CreateFolder"
    version: Version               # Semantic version for contract (distinct from plugin version)
    domain: str                    # e.g., "Filesystem"
    category: str                  # e.g., "modify"
    inputs: Schema = Schema.unknown()
    outputs: Schema = Schema.unknown()
    permissions: Permissions = Permissions()
    side_effect: str = UNKNOWN
    latency_class: str = UNKNOWN
    retryability: str = UNKNOWN
    idempotency: str = UNKNOWN
    summary: str = ""
    metadata: dict[str, Any] = {}
    
    def accepts(self, payload: dict) -> tuple[str, ...]:
        """Structural problems with payload, or nothing. See Schema.problems()."""
    
    @property
    def fully_specified(self) -> bool:
        """Is every field actually known? Most are not today — honest starting point."""
    
    @property
    def unknowns(self) -> tuple[str, ...]:
        """Which fields nobody has declared. The work list for making a capability fully contracted."""
```

#### `Version` — Semantic Version for Contract
```python
@dataclass(frozen=True, order=True)
class Version:
    major: int
    minor: int
    patch: int
    
    def compatible_with(self, other: Version) -> bool:
        """Same major, and at least the minor it was written against. Ordinary semver."""
        return self.major == other.major and self >= other
```

#### `IndexEntry` — One Line of Always-Loaded Index
```python
@dataclass(frozen=True)
class IndexEntry:
    canonical_id: str
    domain: str
    summary: str = ""
    risk_tier: str = UNKNOWN
    required_args: tuple[str, ...] = ()      # Arguments a call MUST carry
    args_complete: bool = False              # False = optional args exist that nobody published
    approval_required: bool = False
    side_effect: str = UNKNOWN
    
    @property
    def signature(self) -> str:
        """e.g., 'Filesystem.CreateFolder(name)' — the one line a prompt needs."""
```

---

## Capability Index (`capabilities/index.py`)

### `CapabilityIndex` — Two-Tier Registry
```python
@dataclass
class CapabilityIndex:
    entries: tuple[IndexEntry, ...] = ()
    loader: Any = None  # callable canonical_id -> CapabilityContract | None
    
    # Always-loaded tier
    def __contains__(self, canonical_id: str) -> bool
    def names(self) -> tuple[str, ...]
    def entry(self, canonical_id: str) -> IndexEntry | None
    def in_domain(self, domain: str) -> tuple[IndexEntry, ...]
    def domains(self) -> tuple[str, ...]
    def search(self, text: str) -> tuple[IndexEntry, ...]  # substring, case-insensitive
    
    # Lazy tier
    def contract(self, canonical_id: str) -> CapabilityContract | None:
        """Full contract, loaded on first ask and memoised."""
    
    @property
    def loaded(self) -> tuple[str, ...]:
        """Which full contracts have actually been fetched."""
    
    def unspecified(self) -> tuple[str, ...]:
        """Capabilities whose index entry publishes no required args and no completeness — the honest work list."""
```

### `build_index(contracts, loader) -> CapabilityIndex`
- Sorted by canonical_id (determinism: same objective = same plan on different boot)
- Loader consulted lazily, memoised

### `entry_for(contract) -> IndexEntry`
Projects full contract down to index line:
- `required_args` = `contract.inputs.required_names` (if known)
- `args_complete` = `contract.inputs.known and contract.inputs.closed`
- `approval_required` = `contract.permissions.approval_required`

---

## Current Implementation Status

| Component | Architecture Status | Implementation Status | Notes |
|-----------|---------------------|----------------------|-------|
| **`Version`** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | Semver with `compatible_with()` |
| **`FieldSpec`** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | 5 field types + choices + default |
| **`Schema`** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | `known` + `closed` flags, `problems()` |
| **`Permissions`** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | Mirrors Action declaration |
| **`CapabilityContract`** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | Full contract with `fully_specified` + `unknowns` |
| **`Version`** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | Semver + `compatible_with()` |
| **`IndexEntry`** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | `signature()` for prompts |
| **`CapabilityIndex`** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | Two-tier, memoised loader |
| **`entry_for()`** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | Contract → IndexEntry projection |
| **`build_index()`** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | Sorted, deterministic |
| **`Schema.unknown()`** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | Distinguishes "unknown" from "empty" |
| **`_schema_from()`** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | Missing schema = unknown, not empty |
| **`FieldSpec` choices** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | Closed value sets |
| **`FieldSpec` default** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | `None` = no default |
| **`Schema.closed`** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | False = open to unknown keys |
| **`CapabilityContract.fully_specified`** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | Honest "is everything known?" |
| **`CapabilityContract.unknowns`** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | Work list for full contract |

---

## Design vs Implementation Differences

| Area | Design (Architecture) | Implementation | Status |
|------|----------------------|----------------|--------|
| **Two-Tier Index/Contract** | Always-loaded + lazy | ✅ `IndexEntry` + `CapabilityContract` | ✅ MATCH |
| **Unknown ≠ Empty** | `Schema.known` flag | ✅ `Schema.unknown()` + `Schema.known` | ✅ MATCH |
| **Contract Versioning** | Semver, distinct from plugin | ✅ `Version` with `compatible_with()` | ✅ MATCH |
| **Unknown Stays Unknown** | Never inferred | ✅ `UNKNOWN` defaults, `SIDE_EFFECT_BY_RISK` only derivation | ✅ MATCH |
| **Structural Validation Only** | `Schema.problems()` | ✅ Names, presence, types only | ✅ MATCH |
| **Immutable Index** | Frozen, memoised loader | ✅ `frozen=True`, memoised `contract()` | ✅ MATCH |
| **Deterministic Ordering** | Sorted by canonical_id | ✅ `sorted()` in `build_index()` | ✅ MATCH |
| **Side Effect from RiskTier** | One derivation only | ✅ `SIDE_EFFECT_BY_RISK` map | ✅ MATCH |
| **Permissions Mirror Action** | Not re-decided | ✅ Mirrors Action declaration | ✅ MATCH |
| **Lazy Contract Loading** | Memoised, at most once | ✅ `contract()` with `_contracts` cache | ✅ MATCH |
| **Deterministic Search** | Substring, case-insensitive | ✅ `search()` in `CapabilityIndex` | ✅ MATCH |
| **Contract Serialization** | `as_dict()` / `from_dict()` | ✅ Round-trip support | ✅ MATCH |

---

## Open Questions

1. **CapabilityManifest.input_schema/output_schema Still Empty** — Declared in frozen `plugins/base.py`, populated by nothing. This contract system is the intended replacement, but not yet wired to Plugin manifests.

2. **No Capability Registry Integration** — `CapabilityIndex` exists but not yet wired as the source of truth for `PluginRegistry` or Mission Control's Capability Registry.

3. **Contract Discovery/Extraction** — How are `CapabilityContract`s created from existing Actions/Plugins? Not yet automated.

4. **Contract Evolution/Versioning** — `Version.compatible_with()` exists but no migration path or deprecation policy for contract changes.

5. **Output Schemas** — `outputs` Schema exists but not populated by any Action/Plugin yet.

6. **Latency/Retry/Idempotency** — All `UNKNOWN` by default. No mechanism to measure/declare them yet.

7. **Contract Testing** — No contract test suite that validates a capability against its contract.

8. **Cross-Plugin Contract Conflicts** — What if two plugins expose same `canonical_id` with different contracts?

---

## Future Extraction Targets

1. `src/master_agent/capabilities/contract.py` — Full contract definitions
2. `src/master_agent/capabilities/index.py` — Index, two-tier loading
3. `src/master_agent/capabilities/extraction.py` — Contract extraction from Actions/Plugins
4. `src/master_agent/plugins/base.py` — `CapabilityManifest` with `input_schema`/`output_schema`
5. `src/master_agent/plugins/registry.py` — Integration with CapabilityIndex
6. `tests/test_capability_contract.py` — Contract validation tests
7. `docs/MISSION_BRIEF_039.md` — Full Mission Brief with findings
8. `docs/adr/0013` — Multi-Operator / Environment Instance architecture (referenced)

---

## Wiki Links Added

- `[[KALPAVRIKSHA_VISION_V2.md]]` — Constitution Rule 3, Rule 4, §5.1, §12.2
- `[[FOUNDER_CONSTITUTION_FREEZE.md]]` — Freeze record
- `[[ARCHITECTURE.md]]` — Implementation map
- `[[03_universal_executive_operator.md]]` — Operator responsibilities
- `[[04_shared_infrastructure.md]]` — Shared Infrastructure (Capability Registry)
- `[[13_plugin_system.md]]` — Plugin system (Plugin contract)
- `[[15_action_contract.md]]` — Action Contract (LocalExecutor)
- `[[16_filesystem_capabilities.md]]` — Filesystem capabilities reference
- `[[17_orchestrator.md]]` — Orchestrator (uses Registry)
- `[[18_browser_worker.md]]` — Browser Worker (capability example)
- `[[system_overview.md]]` — System overview
- `[[docs/adr/0013]]` — Multi-Operator architecture

---

*Document created from verified sources only. No Capability Contract architecture redesigned. Terminology preserved exactly. Constitution/Architecture/Implementation/Open Questions separated. Design/implementation differences recorded without reconciliation.*