# Kalpavriksha Architecture Constitution — Version 2

**Status:** Canonical Architecture Reference  
**Effective Date:** 2026-07-24  
**Scope:** All Mission Briefs from MB021 forward  
**Authority:** This document supersedes all prior Mission Briefs, ADRs, and design notes for architectural decisions. It is the single source of truth for Kalpavriksha Version 2.

---

## Table of Contents

1. [Project Vision](#1-project-vision)
2. [Core Principles](#2-core-principles)
3. [Executive Brain Responsibilities](#3-executive-brain-responsibilities)
4. [Universal Executive Operator Responsibilities](#4-universal-executive-operator-responsibilities)
5. [Brain vs Operator Separation](#5-brain-vs-operator-separation)
6. [Universal Environment Philosophy](#6-universal-environment-philosophy)
7. [Knowledge Philosophy](#7-knowledge-philosophy)
8. [Verification Philosophy](#8-verification-philosophy)
9. [Recovery Philosophy](#9-recovery-philosophy)
10. [Worker Architecture](#10-worker-architecture)
11. [Environment Independence](#11-environment-independence)
12. [Product Agnosticism](#12-product-agnosticism)
13. [Human Oversight Philosophy](#13-human-oversight-philosophy)
14. [Long-term Founder Edition Vision](#14-long-term-founder-edition-vision)
15. [Immutable Architecture Rules](#15-immutable-architecture-rules)

---

## 1. Project Vision

**Kalpavriksha** (the wish-fulfilling tree) is an AI orchestration platform that turns a stated human intention into a completed, verified outcome — not a chat response, not a suggestion, but a real-world result that the human can see, touch, and trust.

### The Kalpavriksha Loop

```
Intent → Plan → Delegate → Execute → Verify → Learn → Report
```

Every interaction follows this loop. No step is optional. No step is bypassed.

### What Kalpavriksha Is

- An **orchestration layer** between human intent and software execution
- A **plugin architecture** where every capability (filesystem, browser, shell, git, model provider, voice) is a plugin behind a single contract
- A **local-first, cloud-enhanced** system: fully functional offline with local models and local memory; cloud providers (ChatGPT, etc.) are opt-in enhancements
- A **permission-gated execution engine**: nothing above read-only risk executes without explicit human approval
- A **memory system** that survives process restarts and feeds future planning

### What Kalpavriksha Is Not

- A chatbot or LLM wrapper
- A replacement for the human's judgment
- A cloud-dependent service
- A monolith that must be rewritten to add capabilities

---

## 2. Core Principles

These are not slogans — they are design constraints the architecture is answerable to.

### 2.1 Intent Over Prompts
The system captures a structured `Intent` object (goal, constraints, context, success criteria), never passes raw strings to a model as the primary planning mechanism.

### 2.2 Outcome Over Output
A Mission is "done" only when the Verifier confirms real-world state matches the Intent's success criteria — not when a model produces text.

### 2.3 Everything Is a Plugin
Model providers, capabilities (filesystem, calendar, browser), voice adapters, UI transports — all are plugins behind the same registry and contract. The core engine is small; almost all capability lives in plugins.

### 2.4 Human Approval Before Important Actions
No plugin may execute a step classified above `READ_ONLY` risk without a Permission System grant. The Permission System has veto power over the Orchestrator — it is not optional middleware, it is a gate.

### 2.5 Local-First, Cloud-Enhanced
The system must be fully functional offline against a local model and local memory. Cloud providers are an enhancement the Model Router opts into, never a hard dependency.

### 2.6 Replaceable Modules
Every module (§4 of ARCHITECTURE.md) is swappable behind its interface without touching the others. This is what makes "build for one founder first, scale for millions later" possible — you don't rewrite the engine to swap SQLite for Postgres or Piper for a cloud TTS.

### 2.7 Minimum Manual Work, Maximum Agent Work
The recurring philosophy across every Mission Brief: the agent does the execution, the human approves and directs.

---

## 3. Executive Brain Responsibilities

The **Executive Brain** (Planner + Intent Layer + Model Router) is the cognitive layer. It decides *what* to do and *how* to structure it.

### 3.1 Intent Layer
- Turns raw input (voice transcript or typed text) into a structured `Intent` (goal, constraints, context, success criteria)
- Owns follow-up clarification questions when intent is ambiguous
- **Never** "send the raw string to an LLM" — this is a real parsing/clarification step so the Planner never has to guess

### 3.2 Planner
- Takes an `Intent`, produces a `MissionPlan`: a DAG of `Step` objects, each naming a required `Capability` (not a specific plugin — the Orchestrator resolves capability → plugin at execution time, so plans stay portable across whichever plugins are installed)
- Calls a Model Provider through the Model Router — planning is a capability like any other
- Reads `Memory.recent_missions()` / `Memory.successful_missions()` as context for "have I done something like this before"

### 3.3 Model Router
- Single `ModelProvider` interface (`generate(prompt, context, **opts) -> ModelResponse`)
- Picks a provider per-call based on:
  1. **Connectivity** — offline ⇒ local Hermes only
  2. **Privacy sensitivity** — anything tagged sensitive by the Intent Layer stays on local Hermes unless human explicitly overrides
  3. **Task profile** — planning/routine steps default to local Hermes (cheap, fast, private); steps declaring need for stronger reasoning or ChatGPT-specific capability escalate to ChatGPT
  4. **Explicit user preference** — always wins
- Router is a plugin-registry lookup, not a hardcoded if/else — adding a third provider (e.g., Claude via API) means writing one new `ModelProvider` plugin, not touching router logic

### 3.4 What the Brain Does NOT Do
- Does not execute filesystem operations
- Does not manage permissions
- Does not track mission state machine
- Does not persist memory
- Does not verify outcomes

---

## 4. Universal Executive Operator Responsibilities

The **Universal Executive Operator** (Orchestrator + Permission System + Local Executor + Plugin Runtime) is the execution layer. It carries out *what* the Brain decided, with full accountability.

### 4.1 Orchestrator
- Walks the `MissionPlan`, and for each `Step`:
  1. Resolves capability → plugin via the Plugin Registry
  2. Checks the Permission System
  3. Invokes the plugin, captures the result (or failure) back onto the Mission
- Retries and failure-branching policy lives here, not in individual plugins

### 4.2 Permission System
- Every plugin declares a `RiskTier` per capability: `READ_ONLY` | `REVERSIBLE_WRITE` | `IRREVERSIBLE`
- Consulted before the Orchestrator invokes anything above `READ_ONLY`
- Grants scoped: `ONCE` | `THIS_SESSION` | `ALWAYS_FOR_CAPABILITY`
- **Critical Rule:** An `ALWAYS_FOR_CAPABILITY` grant can **never** satisfy a check for an `IRREVERSIBLE`-tier capability — destructive actions (`delete_file`, `delete_folder`) require a fresh decision every time
- `PermissionCategory` (`READ` | `WRITE` | `MODIFY` | `DELETE` | `SYSTEM`) is a purely descriptive axis for human-facing grouping; it is never consulted by `check()`'s actual gating logic

### 4.3 Local Executor
- The **only** component allowed to perform local actions
- `Action` Contract (every local capability implements):
  - `name`, `description`, `risk_tier`, `permission_category`, `required_parameters()`
  - `validate(parameters)` — must never touch filesystem or perform side effects
  - `run(parameters)` — does the actual work, returns structured `ExecutionResult` (success, output, errors, warnings, execution_time)
- `LocalExecutor.execute(action_name, parameters)`:
  1. Looks up registered Action
  2. Validates parameters (fails fast, no permission check for malformed request)
  3. Checks Permission System
  4. Runs the action
  5. Catches anything that escapes (never a raw traceback)
  6. Logs every execution (action, start/end time, duration, status) in memory

### 4.4 Plugin Runtime
- `Plugin` contract: manifest (name, version, capabilities provided, risk tier per capability, input/output schema) + `invoke()` method
- `PluginRegistry` discovers and indexes installed plugins at startup
- Model providers are plugins like any other — ChatGPT and local Hermes both implement the same `ModelProvider` interface
- Plugins needing local machine access (filesystem, shell, git) **do not do that work themselves** — they delegate to the Local Executor
- `FilesystemPlugin` is the canonical example: a thin adapter that registers Actions and forwards `invoke()` calls to them

### 4.5 Composite Actions
- Not every capability is a primitive. `WorkspaceBootstrapAction` (create root folder + subfolders + seed files) is a composite Action
- Its `run()` **does not touch the filesystem directly** — it orchestrates other Actions through the same `LocalExecutor.execute()` path every direct caller uses
- Every sub-step is independently validated, permission-gated, and logged
- **No transactional rollback on partial failure** — completed steps stay completed; the result reports exactly what completed before failure (`completed_before_failure`). This is a deliberate, named limitation (see ADR-0006)

---

## 5. Brain vs Operator Separation

| Aspect | Executive Brain | Universal Executive Operator |
|--------|-----------------|------------------------------|
| **Role** | Decides *what* and *how to structure* | Carries out *what* was decided |
| **Modules** | Intent Layer, Planner, Model Router | Orchestrator, Permission System, Local Executor, Plugin Runtime |
| **Model Calls** | Yes (Planner, Intent Layer) | No |
| **Filesystem Access** | Never | Only via Local Executor |
| **Permission Checks** | Never | Every step above READ_ONLY |
| **State Machine** | Unaware | Owns Mission state machine |
| **Memory Persistence** | Reads only (context) | Writes (automatic at terminal states) |
| **Replaceability** | Swap Planner, swap Model Router | Swap Orchestrator policy, swap Executor backend |

**The boundary is absolute.** The Brain produces a `MissionPlan` (DAG of capability-named Steps). The Operator executes it. The Operator has no concept of "intent" — only "capability." The Brain has no concept of "filesystem" — only "capability."

---

## 6. Universal Environment Philosophy

### 6.1 Local-First Is Not Optional
- The system must boot, plan, and execute a meaningful mission with **zero network connectivity**
- Local model (Hermes via Ollama) + local memory (SQLite) + local executor = complete system
- Cloud providers are **plugins** that the Model Router may select when beneficial — never a prerequisite for core function

### 6.2 Environment as a Plugin Concern
- Desktop, server, headless CLI, mobile — the core engine doesn't care
- UI/transport is a plugin (local HTTP/WS API + thin client)
- Voice I/O is a plugin (STT/TTS adapters)
- The same `MasterAgentSession` class runs in all environments

### 6.3 No Environment Assumptions in Core
- No hardcoded paths (all locations injected via `locations: dict[str, Path]`)
- No OS-specific logic in core modules (executor actions handle path validation uniformly)
- No assumption about process lifetime (CLI exits after session; daemon would need bounded logs — flagged in ROADMAP.md)

---

## 7. Knowledge Philosophy

### 7.1 Permanent Knowledge (Persisted, Queryable)
**Mission History** — every mission's intent, plan, approval status, execution result, timing, artifacts created, errors. Stored in `SQLiteMemoryStore` (`~/.master_agent/memory.db`), survives process restarts, queryable by recency, status, ID.

**User Preferences** — small durable key/value facts the founder has explicitly told the system to remember (distinct from mission history).

### 7.2 Temporary Observations (In-Process Only)
**Conversation Memory** — current session's turns, in-process, never persisted. Used for immediate context within a single conversation.

**Mission Memory** — the `Mission` object currently executing; formalized as part of the existing Mission Manager architecture, not a new class.

### 7.3 Evidence Hierarchy (Strongest to Weakest)
1. **Observed Reality** — what the filesystem actually shows, what the shell actually returned, what the Verifier measured
2. **Executor Log** — structured, timestamped, per-action records (action, parameters, start/end, duration, status) — the ground truth of *what the system did*
3. **Mission Record** — the persisted `MissionRecord` (intent, plan, approval, outcome, artifacts) — derived from execution, survives restart
4. **Conversation Transcript** — what was said, in order — useful for debugging human intent, not for determining what happened
5. **Model Output** — what a model *said* it would do / *said* happened — never treated as evidence of reality

### 7.4 Documentation vs Observed Reality
- **Documentation** (Mission Briefs, ADRs, ARCHITECTURE.md) describes *intent* and *design rationale* — it is the map
- **Observed Reality** (tests passing, live verification transcripts, git history, memory.db contents) is the territory
- **When they conflict, observed reality wins.** Documentation is updated to match reality, never the reverse.
- Every Mission Brief ends with live verification against a real process, not a mocked one — this is the discipline that keeps documentation honest.

---

## 8. Verification Philosophy

### 8.1 Verification Is a Distinct Step
The Kalpavriksha Loop has **Verify** as an explicit phase between Execute and Learn. It is not merged into execution.

### 8.2 What Gets Verified
- **Real-world state** matches Intent's success criteria (file exists, folder created, content matches, process completed)
- **Executor log** shows every expected sub-step ran with `status=success`
- **Mission Record** persisted correctly and is queryable

### 8.3 How Verification Works
- `Verifier` (planned module, not yet built) checks outcome against Intent's success criteria
- Today, `cli.py`'s `_finish()` and completion messages serve as the manual verification surface — the human sees the result and confirms
- Future: automated Verifier plugin that the Orchestrator invokes as a final Step in every plan

### 8.4 No Trust Without Verification
- Model output is never trusted as truth
- Plugin `invoke()` return values are structured results, not free text — but they are still *claims* until verified
- The only thing trusted is **observed reality** (see Evidence Hierarchy)

---

## 9. Recovery Philosophy

### 9.1 Mission-Level Recovery
- `Mission` state machine (`draft → planned → awaiting_approval → executing → verifying → completed | failed | cancelled`) enables precise recovery
- If process dies during `executing`, the `MissionRecord` (persisted at terminal states) tells you what was attempted; the Executor log tells you what actually ran
- Idempotent Actions (`create_folder`, `write_file` with identical content) make re-running safe

### 9.2 System-Level Recovery
- **Memory survives restart** — `SQLiteMemoryStore` at `~/.master_agent/memory.db` is the durable anchor
- **No manual save calls** — `MasterAgentSession._remember()` persists automatically at every terminal mission state (`COMPLETED`, `FAILED`, `CANCELLED`)
- **Repository as source of truth** — git history + tags (`v0.x.0-miracle-NNN`) are the canonical architecture history; the ZIP delivery mechanism is a transport, not the source

### 9.3 No Silent Corruption
- Zero tolerance for silent data loss, drift, or gaps
- Every Mission Brief's live verification is a recovery test: "Does a fresh process see the prior process's history?"
- `LocalExecutor._log` (unbounded in-memory list) is a known gap for long-running daemons — flagged in ROADMAP.md, to be folded into Memory or bounded when Executor is next touched

---

## 10. Worker Architecture

### 10.1 Workers Are Plugins
Every capability is a plugin implementing the `Plugin` contract. There is no "worker pool" or "agent swarm" in the core — the Orchestrator invokes plugins sequentially (or with retry/branching policy) per the MissionPlan DAG.

### 10.2 Local-Action Workers
Plugins that touch the local machine (filesystem, shell, git, VS Code, Obsidian) are **thin adapters** over the Local Executor:
- They register `Action` classes on a `LocalExecutor` instance
- Their `invoke()` forwards to `LocalExecutor.execute()`
- They relay the Orchestrator's approval grant down to the Executor's grant key (ADR-0005 pattern) so the human is asked exactly once

### 10.3 Composite Workers
Composite Actions (e.g., `WorkspaceBootstrapAction`) are also plugins/adapters, but their `run()` orchestrates *other* Actions through `LocalExecutor.execute()` — never by calling `Action.run()` directly. This preserves validation, permission gating, and logging for every sub-step.

### 10.4 Model-Provider Workers
`HermesProvider` and `ChatGPTProvider` both implement `ModelProvider`. The Model Router selects between them per-call. They are workers like any other — the Planner calls them, the Orchestrator doesn't know they exist.

### 10.5 Adding a New Worker
1. Implement the `Plugin` contract (or `ModelProvider` / `Action` subclass)
2. Register it (declaratively for Actions; constructor injection for plugins)
3. **No changes to Orchestrator, Permission System, Local Executor, or Plugin Registry**
4. This is O(1) per capability — proven at scale in Miracle 005 (14 filesystem capabilities, zero core edits)

---

## 11. Environment Independence

### 11.1 No Hardcoded Environment Assumptions
- Paths: all locations injected via `locations: dict[str, Path]` (desktop, downloads, documents — default to `Path.home()` subdirectories, but fully overridable)
- OS: Actions use `pathlib` and stdlib only; path traversal guard (`is_unsafe_relative_path()`) rejects absolute paths and `..` segments uniformly
- Process lifetime: CLI process exits after session; daemon mode would need bounded logs (ROADMAP.md)

### 11.2 Transport-Agnostic Core
- `MasterAgentSession` has no stdin/stdout dependency — it takes a string, returns a string
- `cli.py` is a thin REPL wrapper; the same session class works for HTTP API, WebSocket, desktop UI, messaging gateway
- Voice I/O adapters (STT/TTS) are plugins, not core dependencies

### 11.3 Plugin Distribution
- For Founder Edition: plugins are local Python packages discovered by the registry at startup
- No plugin marketplace/installer needed yet — confirmed as acceptable for v0.1 (ARCHITECTURE.md §6)

---

## 12. Product Agnosticism

### 12.1 The Core Knows No Product
The architecture does not assume "this is a coding agent" or "this is a filesystem tool." It assumes:
- Human states intent
- System produces a plan of capabilities
- Capabilities execute with permission
- Outcomes are verified and remembered

### 12.2 Capabilities Define the Product
- Filesystem capabilities → it's a file manager
- Shell capabilities → it's a terminal agent
- Git capabilities → it's a version control assistant
- Browser capabilities → it's a web agent
- Calendar/email capabilities → it's a personal assistant
- **All of the above simultaneously** → it's Kalpavriksha

### 12.3 Adding a Product = Adding Capabilities
New product verticals don't require architecture changes — they require new plugins (and possibly new Action families for local operations). The core engine remains unchanged.

---

## 13. Human Oversight Philosophy

### 13.1 Approval Is Not Optional
- Every capability above `READ_ONLY` requires a Permission System grant
- The human is asked **once per mission** (grant relayed through Plugin → Executor for composites)
- Declining an approval → `Mission.CANCELLED`, nothing executed, nothing persisted as a side effect

### 13.2 Approval UX Must Stay Simple
- Current: CLI Yes/No prompt with a clear plan summary
- Future: voice, desktop UI, messaging platform — but always a single, clear decision point
- The tension named in `MANIFESTO.md`: security vs. friction — the architecture keeps the gate, the UX minimizes the friction

### 13.3 Human Directs, Agent Executes
- "Minimum Manual Work. Maximum Agent Work."
- The human provides intent, constraints, and approvals
- The agent handles parsing, planning, delegation, execution, verification, reporting, learning
- The human never manually manages multiple AI tools — that is the problem Kalpavriksha exists to solve

### 13.4 Transparency Over Trust
- Every execution is logged (action, parameters, time, status)
- Every mission is recorded (intent, plan, approval, outcome, artifacts)
- The human can always ask "What was my last mission?" / "Show my recent missions"
- No hidden state, no opaque model calls without a plan step naming the capability

---

## 14. Long-term Founder Edition Vision

### 14.1 What "Founder Edition" Means
- Built for **one founder first** — every design decision validated by "does this serve the founder's actual workflow today?"
- **Not** built for hypothetical millions of users — but **designed** so that scaling doesn't require rewriting (replaceable modules, plugin architecture, local-first)
- Documentation is the product — `ARCHITECTURE.md`, `MEMORY_ARCHITECTURE.md`, `FILESYSTEM_CAPABILITIES.md`, ADRs — so the founder (and future models) can understand the system without chat history

### 14.2 The 13-Day Runway Constraint (Historical Context)
- Original deadline: Aug 5, 2026
- Seven Miracles (MB001–MB005) delivered in that window
- Each Miracle: design doc first → implementation → tests → live verification → documentation
- No Miracle ever rewrote a prior Miracle's working code — only extended, composed, or fixed gaps

### 14.3 Post-Founder Edition Evolution
- Real Planner (model-driven, replaces `cli.py` regex stand-in)
- Mission Manager wired into live path
- Knowledge/Vector Memory
- Vector Memory (semantic recall over mission history)
- Cloud Sync (opt-in, plugin, never on by default)
- Desktop UI (FastAPI + pywebview recommended, Tauri acceptable alternative)
- Multi-Agent coordination (Kanban dispatcher, worker profiles)
- Voice I/O (local STT/TTS first, cloud as enhancement)

---

## 15. Immutable Architecture Rules

**All future Mission Briefs (MB021+) MUST follow these rules. No exceptions. No "just this once."**

### Rule 1: Design Before Code
Every Miracle begins with a design document (`*_CAPABILITIES.md`, `*_ARCHITECTURE.md`, or similar) written **before** any implementation. The design doc must answer the Scalability Question (§8 of `FILESYSTEM_CAPABILITIES.md`).

### Rule 2: No Rewrites Without Approval
Never refactor architecture without being asked. Reuse existing scaffolding. Check `DECISIONS.md` before assuming a module needs rebuilding.

### Rule 3: Plugin Contract Is Sacred
- Every capability is a plugin behind the `Plugin` contract (or `ModelProvider` / `Action` subclass)
- Adding capability #N costs **one new file**, never an edit to `PluginRegistry`, `Orchestrator`, `PermissionSystem`, or `LocalExecutor`
- Declarative registration (tuple + loop) over imperative if/else chains

### Rule 4: Local Executor Is the Only Local Touchpoint
No plugin, no Brain module, no CLI code touches the filesystem/shell/process directly. Everything goes through `LocalExecutor.execute(action_name, parameters)`.

### Rule 5: Permission System Has Veto Power
- Every capability declares a `RiskTier` (`READ_ONLY` | `REVERSIBLE_WRITE` | `IRREVERSIBLE`)
- `PermissionSystem.check()` is consulted before **any** step above `READ_ONLY`
- `ALWAYS_FOR_CAPABILITY` grants **never** satisfy `IRREVERSIBLE` checks
- `PermissionCategory` is descriptive only — never used for gating

### Rule 6: Composites Relay, Never Bypass
- Composite Actions orchestrate primitives **only through `LocalExecutor.execute()`**
- They relay their already-obtained approval down to each sub-step's grant key (ADR-0005/0006 pattern)
- Every sub-step is independently validated, permission-gated, and logged
- No transactional rollback — partial failure leaves completed steps completed; result reports `completed_before_failure`

### Rule 7: Memory Persists Automatically
- `MasterAgentSession._remember()` called at **every** terminal mission state (`COMPLETED`, `FAILED`, `CANCELLED`)
- No manual save calls anywhere in the CLI loop
- `SQLiteMemoryStore` at `~/.master_agent/memory.db` is the durable anchor

### Rule 8: Evidence Hierarchy Is Law
When documentation and observed reality conflict, **observed reality wins**. Documentation is updated to match reality. Live verification against a real process (not mocks) is mandatory for every Miracle.

### Rule 9: Scalability Question Answered Before Implementation
Before finalizing any design, answer explicitly: "Would this design still be right at a million missions, thousands of plugins, hundreds of capabilities, years of history?" Document the answer in the design doc (§8 of `FILESYSTEM_CAPABILITIES.md` is the template).

### Rule 10: Technical Debt Is Named Honestly
Every Miracle deliverable includes a "Technical Debt / Known Limitations / Remaining Stubs" section. Nothing is hidden. If a gap is out of scope, it is **named and flagged** (e.g., `LocalExecutor._log` unbounded list → ROADMAP.md), not silently accepted.

### Rule 11: Test the Complete Flow
Unit tests for modules are necessary but insufficient. Every Miracle adds **end-to-end integration tests** that exercise the complete Conversation → Intent → Plan → Permission → Executor → Action → Memory path. Regression suite must pass unchanged.

### Rule 12: Ruff Clean, Pytest Green
- `ruff check` → All checks passed (zero errors, zero warnings)
- `pytest` → All tests passing (count only goes up, never down)
- These are gates, not suggestions

### Rule 13: Git History Is Canonical
- One commit per Miracle (plus documentation commits if needed)
- Tags follow `vMAJOR.MINOR.PATCH-miracle-NNN` pattern
- Never force-push, never squash, never rewrite history
- The repository is the source of truth; ZIP delivery is transport only

### Rule 14: Human Approval UX Stays Simple
- One decision point per mission (grant relayed internally for composites)
- Clear plan summary shown before asking
- Declining = immediate cancellation, no side effects
- Future UX (voice, UI, messaging) must preserve this simplicity

### Rule 15: The Founder Playbook Is Process
`FOUNDER_PLAYBOOK.md` codifies how Miracles are built, reviewed, tested, shipped. It is not optional reading — it is the process. Deviations require explicit founder approval.

---

## Appendix: Source Document Traceability

This constitution consolidates decisions from the following canonical sources (all in repository):

| Document | Role |
|----------|------|
| `MISSION_BRIEF_001.md` – `MISSION_BRIEF_005.md` | Implementation records with honest accounting |
| `ARCHITECTURE.md` | System design (module boundaries, data flow, plugin contract) |
| `MEMORY_ARCHITECTURE.md` | Six-layer memory design, schema, privacy, tradeoffs |
| `FILESYSTEM_CAPABILITIES.md` | Filesystem capability design (atomic Actions, composition, security, scale) |
| `PROJECT_BRAIN.md` | Current-state index and orientation |
| `MIRACLE_LEDGER.md` | Chronological shipment record |
| `docs/adr/0005-executor-permission-relay.md` | Permission relay pattern (Plugin → Executor) |
| `docs/adr/0006-composite-action-relay.md` | Composite relay pattern (Action → Executor) |
| `docs/adr/0007-sqlite-memory-backend.md` | SQLite + JSON columns rationale |
| `docs/adr/0008-memory-scale-review.md` | Memory query contract & artifact schema generalization |
| `docs/adr/0009-permission-category-and-irreversible-grant-rule.md` | PermissionCategory + IRREVERSIBLE/ALWAYS rule |
| `ROADMAP.md` | Prioritized future work |
| `FOUNDER_PLAYBOOK.md` | Miracle build/review/test/ship process |
| `ENGINEERING_PRINCIPLES.md` / `PRODUCT_PRINCIPLES.md` / `ARCHITECTURE_PRINCIPLES.md` | Value-to-practice mappings |

---

**End of Kalpavriksha Architecture Constitution v2**

*This document is the single source of truth for Kalpavriksha Version 2. All future Mission Briefs (MB021+) reference this document for architectural authority. It is updated only when a new Miracle establishes a new immutable rule or modifies an existing one — and such updates are themselves documented in the Miracle's brief and the Miracle Ledger.*