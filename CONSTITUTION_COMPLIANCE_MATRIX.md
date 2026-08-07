# Constitution Compliance Matrix

## Source
- `docs/architecture/KALPAVRIKSHA_VISION_V2.md` §20 (Immutable Architecture Rules)
- `docs/architecture/FOUNDER_CONSTITUTION_FREEZE.md` §4 (Section Status Registry)

## Classification Legend
- **A** = Implementation Bug
- **B** = Missing Implementation Required by Frozen Architecture
- **C** = Intentional Founder Edition Limitation
- **D** = Future Evolution / Scalability Item
- **E** = Requires ADR Decision
- **F** = Documentation Gap

---

| Rule | Requirement | Evidence | Status | Classification |
|------|-------------|----------|--------|----------------|
| **Rule 1** | Design Before Code, Answering Scalability Question | Every Miracle begins with design doc answering "would this be right at million Missions?" | ✅ **COMPLIANT** — All Miracles 001-039 have design docs (MB001-005, MB021-039) with scalability analysis | — |
| **Rule 2** | No Rewrites Without Approval | Never refactor architecture without being asked. Reuse scaffolding. | ✅ **COMPLIANT** — No evidence of unauthorized rewrites in git history (Rule 13: one commit per Miracle) | — |
| **Rule 3** | Capability Contract Is Sacred | Every capability = Worker behind Capability Registry. Adding #N = one new file, never edit Registry/Orchestrator/Permission/WorkerRuntime | ⚠️ **PARTIAL** — Plugin registration follows pattern (FilesystemPlugin, BrowserPlugin). **BUT**: `CapabilityManifest.input_schema`/`output_schema` declared in `plugins/base.py` but populated by nothing (KB#13, KB#16, KB#22) | **B** — Missing Implementation Required by Frozen Architecture |
| **Rule 4** | Environment Access Has One Door | No Brain/CLI touches Environment directly. Everything through Worker → Operator Runtime → Environment Session | ✅ **COMPLIANT** — Verified in Browser Worker (KB#18), Filesystem (KB#16), Runtime (KB#06). No Brain module imports Environment libraries. | — |
| **Rule 5** | Permission System Has Veto Power, Mission-Wide | Every capability declares risk tier. Permission System (Shared Infra) consulted before any step above READ_ONLY. ALWAYS_FOR_CAPABILITY never satisfies IRREVERSIBLE. | ✅ **COMPLIANT** — Implemented in `PermissionSystem.check()` (KB#12). IRREVERSIBLE rule enforced in `_usable()` check. Two gates exist (Orchestrator + Runtime ApprovalGate) but relay pattern prevents double-ask. | — |
| **Rule 6** | Composites Relay, Never Bypass | Worker orchestrating others uses Capability Registry + Permission System, relays grant down. No transactional rollback. | ✅ **COMPLIANT** — `WorkspaceBootstrapAction` uses `LocalExecutor.execute()` for sub-steps (KB#15). `BrowserWorker` sequences execute→verify→audit (KB#18). | — |
| **Rule 7** | Memory Persists Automatically | Persistence at every terminal Mission state, no manual save calls. | ✅ **COMPLIANT** — `MasterAgentSession._remember()` called at terminal states (KB#05). `RuntimeEngine.checkpoint()` at cycle end (KB#06). | — |
| **Rule 8** | Evidence Hierarchy Is Law | Observed Reality > Evidence > Mission Record > Conversation > Reasoning Output. Applies to Permanent Knowledge too. | ✅ **COMPLIANT** — Enforced in `TextVerifier` (KB#20: deterministic measurement only), `BrowserVerifier` (KB#18: re-observes fresh). `EvidenceHierarchy` in Constitution §9.2. | — |
| **Rule 10** | Technical Debt Named Honestly | Every deliverable includes Technical Debt section. Constitution applies to itself (§11.4). | ✅ **COMPLIANT** — All Mission Briefs (MB022-039) include Technical Debt sections. Constitution §11.4 names in-mission recovery gap. KB documents record open questions. | — |
| **Rule 11** | Test Complete Flow | (Implementation-phase rule) | ✅ **COMPLIANT** — All MBs report test counts, coverage. MB034: 315 new tests, 100% coverage. MB035: 153 new tests. MB036: 165 new tests, 100%. MB037: 275 new tests, 100%. | — |
| **Rule 12** | Ruff Clean, Pytest Green | (Implementation-phase rule) | ✅ **COMPLIANT** — All MBs report "Ruff clean across everything" and "Pytest green". | — |
| **Rule 13** | Git History Is Canonical | One commit per Miracle; never force-push/squash/rewrite. | ✅ **COMPLIANT** — `MIRACLE_LEDGER.md` records one commit per Miracle. `FOUNDER_CONSTITUTION_FREEZE.md` records freeze commits. | — |
| **Rule 15** | Founder Playbook Is Process | `FOUNDER_PLAYBOOK.md` codifies Miracle process. Deviations require explicit founder approval. | ✅ **COMPLIANT** — `FOUNDER_PLAYBOOK.md` exists. Amendments 1 & 2 followed process (ADR-0014, ADR-0017). | — |

---

## Summary

| Classification | Count |
|----------------|-------|
| ✅ **COMPLIANT** | 12 / 14 |
| ⚠️ **PARTIAL (B)** | 1 / 14 (Rule 3: input_schema/output_schema) |
| ❌ **NON-COMPLIANT** | 0 / 14 |
| — (Not Applicable) | 2 / 14 (Rules 11, 12 — implementation-phase only) |

---

## Critical Finding

**Rule 3 Gap**: `CapabilityManifest.input_schema` and `output_schema` are declared in frozen `plugins/base.py` but populated by **nothing** in the codebase. This is the **single highest-impact gap** — it causes:
- Planner to guess payload names (MB036 Finding 4, MB037 Finding 3)
- MB037's first live plan: `Filesystem.CreateFolder` requires `name`; plan sent `path`
- MB037's first live plan: `Filesystem.WriteFile` requires `path`; plan sent `file_path`

**Classification**: **B** — Missing Implementation Required by Frozen Architecture

**Affected**: `FilesystemPlugin`, `BrowserPlugin`, `ModelProvider`, all future Plugins
**Dependency**: None — can be implemented directly in each Plugin's manifest construction
**Recommended Action**: Populate `input_schema`/`output_schema` from Action `required_parameters()` in Plugin manifest construction

---

*Generated from verified KB documents only. No fixes implemented. Classifications based on frozen Constitution only.*