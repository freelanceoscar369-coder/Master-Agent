# Knowledge Memory Architecture (Layer 4)

## Purpose
Documents the Persistent Founder Memory & Knowledge Repository — Layer 4 of the six-layer memory architecture — enabling Kalpavriksha to remember what the founder told it across restarts, with no LLM anywhere near the answer.

---

## Frozen Constitution

### Constitution §5.4 (Memory — FROZEN)
> **Belongs in Shared Infrastructure because:** every Operator Instance's Evidence must aggregate into one durable history, not fragment into per-Operator silos. All six Memory layers live here.

### Constitution §9 (Knowledge Philosophy — Mixed Status)

**§9.1 Permanent Knowledge and Temporary Observations (FROZEN)**
> **Permanent Knowledge (persisted, queryable):** Mission History + User Preferences.
> **Temporary Observations (in-process only):** Conversation Memory + Mission Memory.

**§9.2 Evidence Hierarchy (FROZEN)**
1. **Observed Reality** — what Environment actually shows
2. **Evidence** — structured record of Observation vs Expected Outcome
3. **Mission Record** — persisted record, survives restart
4. **Conversation Transcript** — debugging human intent only
5. **Reasoning Provider Output** — never treated as evidence of reality
> **When documentation and observed reality conflict, observed reality wins** (Rule 8). Extends to Permanent Knowledge.

**§9.3 Knowledge Lifecycle (RESEARCH-BACKED)**
```
Execution → Evidence → Knowledge Candidate → Promotion Review → Permanent Knowledge → Future Reasoning
```
**Stage Ownership:**
| Stage | Owner | What Happens |
|-------|-------|--------------|
| Execution | Operator (Worker) | Produces effects in Environment Instance |
| Evidence | Verification Subsystem | Observation + Expected Outcome + Verdict = durable record |
| Knowledge Candidate | Brain (Planner) | Recognizes recurring pattern, nominates it (reasoning judgment) |
| Promotion Review | Dedicated gate, human-confirmed (Founder Edition) | Checks: observed enough times, not contradicted, not superseded |
| Permanent Knowledge | Shared Infrastructure (Memory, Layer 4) | Durable, queryable, actively consulted |
| Future Reasoning | Brain (Planner) | Consumes Permanent Knowledge like recent Mission history |

**§9.4 Who Can Promote Knowledge (FROZEN)**
> Promoting Knowledge changes Brain's future reasoning permanently and silently — exactly the class of high-leverage action §15 exists to gate. **For Founder Edition, Promotion Review requires human confirmation.** Automating later = legitimate evolution (EVOLVABLE).

**§9.5 Temporary vs Permanent (FROZEN)**
> Dividing line = Promotion Review gate. Nothing crosses from "recorded" to "actively shapes future reasoning" without passing through it.

---

## Architecture Design

### From `MISSION_BRIEF_034.md` §1–§2
> **MB034 is Layer 4 arriving** — the "durable facts distinct from mission history" that `memory/future.py` reserved. MB004 shipped Layers 1–3 (Conversation, Mission, SQLite). The five new modules compose *beside* them; `cli.py`'s existing path untouched.

### Storage Location (Beside, Not Inside State)
```
.master_agent/
    state/                  <- MB025's snapshot + event log (operational state)
    memory/
        knowledge.json      <- the records. Authoritative.
        index.json          <- the index. Derived, disposable.
```
**Beside, not inside:** MB025's snapshot is operational state a recovery may legitimately discard; founder memory is not. Losing what the founder said because a mission crashed would be the worst reading of "recovery."

### Two Files, Two Attitudes to Corruption
| File | Role | Corruption Handling |
|------|------|---------------------|
| `knowledge.json` | Authoritative records | **Moved aside** with `.corrupt` suffix, never overwritten. Founder can open and copy notes out. Second corruption doesn't clobber first. |
| `index.json` | Derived index | **Rebuilt in silence**. Bad one costs nothing. Store checks index *equals* what records imply (not size) — index with right number of wrong entries is hardest failure to notice. |

### One Bad Record = Skipped, Not Fatal
- Single bad row skipped and counted (not fatal)
- Count reaches boot report — founder learns unreadable memories at moment it matters
- Same tolerance as event log's truncated final line

---

## Memory Models (from `memory_models.py`)

### MemoryRecord
```python
@dataclass
class MemoryRecord:
    id: str                    # mem-XXXXXX sequence
    category: Category         # enum: Mission Outcomes, Failure Library, Success Library, Business Decisions, Founder Preferences, Architecture Decisions, Recurring Lessons, Open Questions
    title: str
    body: str
    tags: tuple[str, ...]      # arbitrary tags
    importance: Importance     # enum: LOW, NORMAL, HIGH, CRITICAL
    source: Source             # enum: MANUAL, AUTOMATIC, ARCHITECTURE_DECISION, RECOVERY_REPORT, VERIFICATION_OUTCOME, APPROVAL_RECORD
    created_at: datetime
    updated_at: datetime
    importance_score: int      # computed: CRITICAL=1000, HIGH=100, NORMAL=10, LOW=1
    content_digest: str        # SHA256 of category+title+body (not tags/importance/timestamps)
    related_items: tuple[str, ...]  # bidirectional links by id
```

### Category & Importance (Closed Vocabularies Enforced at Write Time)
**10 Categories (Closed):**
1. Mission Outcomes
2. Failure Library
3. Success Library
4. Business Decisions
4. Founder Preferences
5. Architecture Decisions
6. Recurring Lessons
7. Open Questions
8. Architecture Decisions

**4 Importance Levels (Closed):**
- LOW, NORMAL, HIGH, CRITICAL

**6 Sources (Closed):**
- MANUAL, AUTOMATIC, ARCHITECTURE_DECISION, RECOVERY_REPORT, VERIFICATION_OUTCOME, APPROVAL_RECORD

---

## Retrieval & Ranking (Deterministic, Stated Not Tuned)

### From `MISSION_BRIEF_034.md` §3
> **No vector DB, no embeddings, no semantic search, no model call.** Ranking is **stated rather than tuned**:

| Match In | Weight | Why |
|----------|--------|-----|
| tag | 8 | somebody chose that word to file it under |
| title | 4 | somebody chose that word to name it |
| summary | 2 | the opening of what they wrote |
| full text | 1 | the word is in there somewhere |

**Tie-breaking:** importance → recency → id — same query returns same list forever, order never depends on insertion order.

**Matching is exact:** `fail` does not find `failure`. Deliberate: a surprise a founder can see and work around; a stemmer matching wrong thing is one they cannot.

### Lookup Methods (6 Named + `search_hits`)
| Method | Description |
|--------|-------------|
| `find_by_tag(tag)` | Records with tag |
| `find_by_category(category)` | Records in category |
| `recent(limit)` | Most recent records |
| `related(record_id)` | Bidirectional graph walk (own `related_items` + backlinks) |
| `search(query)` | Ranked text search |
| `critical()` | CRITICAL importance records |
| `search_hits` | Carries arithmetic so "why did that come first?" answerable without re-running |

### Related Graph (Bidirectional, Ids Only)
- `related()` walks both ways: record's own `related_items` + backlink index
- Ids only, no graph database
- Dangling id = skipped neighbour, not crash

---

## Automatic Memory (Rides Existing Event Bus)

### From `MISSION_BRIEF_034.md` §4
> **Six subscriptions on Event Bus Mission Control already publishes on** — same door `PersistenceService` uses. **Per event type, not to everything:** Runtime publishes heartbeat every cycle; memory system that ignores most would eventually stop ignoring one.

| Event | Category | Importance |
|-------|----------|------------|
| `objective_submitted` | (learns name; writes nothing) | — |
| `objective_completed` | Mission Outcomes | NORMAL |
| `objective_failed` | Failure Library | HIGH |
| `verification_completed` (matched) | Success Library | NORMAL |
| `verification_completed` (other) | Failure Library | HIGH |
| `approval_granted` / `approval_denied` | Business Decisions | HIGH |

**Submission deliberately not a memory:** a mission *started* is not an outcome.

**Recovery has no event** — MB025 runs `recover()` before recording starts; composition root hands report in.

**Architecture decisions have no event** — inferring from diff = guessing. `remember_architecture()` is a door used by whoever knows.

---

## Duplicate Suppression (from `MISSION_BRIEF_034.md` §5)

> **A write whose content digest already exists updates that record instead of adding one.**
> - Digest covers: category, title, body (deliberately NOT tags, importance, timestamps)
> - Re-stating a fact with a new tag = same fact
> - Merging unions tags and links
> - Importance can only go **UP** — repeating emphasises it
> - Suppressed duplicate does not consume an id (no unexplainable gaps)

> Without this, "how many things do I know" would count how often founder repeated themselves.

---

## Implementation Modules (from `MISSION_BRIEF_034.md` §6)

| Module | Stmts | Coverage | Purpose |
|--------|-------|----------|---------|
| `memory/knowledge_store.py` | 138 | 100% | Atomic JSON writes, corruption handling |
| `memory/memory_index.py` | 94 | 100% | Index, backlinks, search ranking |
| `memory/memory_models.py` | 114 | 100% | Data models, enums, validation |
| `memory/memory_query.py` | 97 | 100% | Search, ranking, graph links |
| `memory/memory_service.py` | 174 | 100% | High-level service, Event Bus subscriptions |

**Total: 617 statements, 100% coverage, 315 new tests, zero regressions**

---

## Current Implementation Status

| Component | Architecture Status | Implementation Status | Notes |
|-----------|---------------------|----------------------|-------|
| **Layer 1: Conversation Memory** | FROZEN | ✅ **IMPLEMENTED** | `memory/conversation.py` |
| **Layer 2: Mission Memory** | FROZEN | ✅ **IMPLEMENTED** | `Mission` object + `MasterAgentSession` |
| **Layer 3: Persistent Memory (SQLite)** | FROZEN | ✅ **IMPLEMENTED** | `memory/store.py` — mission history |
| **Layer 4: Knowledge Memory** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | 5 new modules, `knowledge.json` + `index.json` |
| **Layer 5: Vector Memory** | FUTURE | ⏳ **INTERFACE ONLY** | `memory/future.py` — `VectorMemory` ABC |
| **Layer 6: Cloud Sync** | OPTIONAL FUTURE | ⏳ **INTERFACE ONLY** | `memory/future.py` — `CloudSyncMemory` ABC |
| **Duplicate Suppression** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | Content digest (SHA256), importance only goes up |
| **Automatic Memory (Event Bus)** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | 6 subscriptions, per-event-type |
| **Related Graph** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | Bidirectional, backlink index |
| **Corruption Handling** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | `.corrupt` suffix, index rebuild |
| **Duplicate Suppression** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | Content digest (SHA256), importance only up |
| **Closed Vocabularies** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | 10 categories, 4 importance, 6 sources |

---

## Design vs Implementation Differences

| Area | Design (Architecture/Constitution) | Implementation | Status |
|------|-----------------------------------|----------------|--------|
| **Layer 4 Separate from State** | Beside `state/`, not inside | ✅ `.master_agent/memory/` beside `.master_agent/state/` | ✅ MATCH |
| **Authoritative + Derived Files** | `knowledge.json` + `index.json` | ✅ `.corrupt` suffix, index rebuild | ✅ MATCH |
| **Corruption Handling** | Authoritative moved aside, index rebuilt | ✅ `.corrupt` suffix, index equals check | ✅ MATCH |
| **Deterministic Ranking** | Stated weights, no model | ✅ tag=8, title=4, summary=2, body=1 | ✅ MATCH |
| **Exact Matching** | No stemming | ✅ `fail` ≠ `failure` | ✅ MATCH |
| **Event Bus Subscriptions** | Per event type | ✅ 6 subscriptions, not heartbeat | ✅ MATCH |
| **Duplicate Suppression** | Content digest, importance up only | ✅ SHA256 digest, importance only up | ✅ MATCH |
| **Automatic Memory Sources** | 6 event types | ✅ 6 subscriptions, per-type | ✅ MATCH |
| **Related Graph** | Bidirectional, backlinks | ✅ `related_items` + backlink index | ✅ MATCH |
| **Vector Memory (Layer 5)** | Interface only | ⏳ `VectorMemory` ABC in `future.py` | ⏳ RESERVED |
| **Cloud Sync (Layer 6)** | Optional plugin | ⏳ `CloudSyncMemory` ABC in `future.py` | ⏳ RESERVED |
| **Atomic JSON Writing** | Three implementations | 📝 3× (`persistence`, `ledger`, `knowledge_store`) | 📝 DOCUMENTED |
| **Whole File Rewrite** | On every write | 📝 Same as event log | 📝 DOCUMENTED |
| **Confidence Always 1.0** | No inference yet | 📝 Field exists for inferred records | 📝 DOCUMENTED |
| **Recurring Lessons/Open Questions** | No automatic writer | 📝 Manual only | 📝 DOCUMENTED |
| **Prompt Library Auto-Writer** | Needs verifier | 📝 Blocked on verifier gap | 📝 DOCUMENTED |
| **Search Unstemmed** | Exact match | ✅ `fail` ≠ `failure` | ✅ MATCH |
| **No Forget/Delete** | Manual only | ✅ No `forget()` method | ✅ MATCH |
| **Objective-Name Map** | Process-local, not persisted | 📝 Mission outliving restart = id only | 📝 DOCUMENTED |

---

## Open Questions

1. **Atomic JSON Writing Duplicated 3×** — `persistence/store.py`, `ai_infrastructure/ledger.py`, `memory/knowledge_store.py`. Shared helper would live in frozen package (MB025). Named, not smuggled.

2. **Whole File Rewrite on Every Write** — Fine at founder-edition volumes; joins unbounded-growth roadmap item for event log.

3. **`confidence` Always 1.0** — Everything stored is stated/observed. Field exists for inferred records (Recurring Lessons from multiple failures). Nothing infers yet → Recurring Lessons/Open Questions have no automatic writer.

4. **Prompt Library No Automatic Writer** — MB033 records every execution in decision ledger; promoting successful prompt needs verifier (same gap as MB033's Prompt Cache).

5. **Search Unstemmed** — `memory fail` ≠ `failure`. Deliberate, but founder-facing surprise.

6. **No Editing or Forgetting** — Record can be updated by re-stating, linked to others, but no `forget()`. Deleting founder memory deserves own approval/evidence thinking.

7. **Objective-Name Map Process-Local** — Mission outliving restart remembered by id. Persisting would mean second store for something only used when memory written.

8. **Vector Memory (Layer 5)** — Interface only; natural shape reads Layer 3 via `MissionQuery.offset` for background indexing.

9. **Cloud Sync (Layer 6)** — Optional plugin via `MemoryStore` interface; off by default forever unless founder decision.

---

## Future Extraction Targets

1. `src/master_agent/memory/knowledge_store.py` — Atomic JSON, corruption handling
2. `src/master_agent/memory/memory_index.py` — Index, backlinks, search ranking
3. `src/master_agent/memory/memory_models.py` — Data models, enums, validation
4. `src/master_agent/memory/memory_query.py` — Search, ranking, graph links
5. `src/master_agent/memory/memory_service.py` — High-level service, Event Bus subscriptions
6. `src/master_agent/memory/future.py` — Layer 4–6 interfaces (`KnowledgeMemory`, `VectorMemory`, `CloudSyncMemory`)
7. `src/master_agent/memory/store.py` — Layer 3 SQLite implementation
8. `src/master_agent/memory/conversation.py` — Layer 1
9. `src/master_agent/memory/memory.py` — Facade
10. `docs/adr/0008` — Memory scale review
11. `docs/adr/0012` — Knowledge Lifecycle

---

## Wiki Links Added

- `[[KALPAVRIKSHA_VISION_V2.md]]` — Constitution §5.4, §9, Rule 8
- `[[FOUNDER_CONSTITUTION_FREEZE.md]]` — Freeze record
- `[[MEMORY_ARCHITECTURE.md]]` — Six-layer design
- `[[MISSION_BRIEF_034.md]]` — Primary source
- `[[05_memory_system.md]]` — Memory system overview
- `[[08_persistence_architecture.md]]` — Persistence (separate concern)
- `[[04_shared_infrastructure.md]]` — Shared Infrastructure (Memory home)
- `[[system_overview.md]]` — System overview
- `[[docs/adr/0008]]` — Memory scale review
- `[[docs/adr/0012]]` — Knowledge Lifecycle

---

*Document created from verified sources only. No Knowledge Memory architecture redesigned. Terminology preserved exactly. Constitution/Architecture/Implementation/Open Questions separated. Design/implementation differences recorded without reconciliation.*