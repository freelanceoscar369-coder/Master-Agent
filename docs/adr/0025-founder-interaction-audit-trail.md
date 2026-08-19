# ADR-0025: The Founder Interaction Audit Trail

Status: Proposed (2026-08-15) — the deliberate, separately-scoped decision `MEMORY_ARCHITECTURE.md` §3 requires before any conversation text is written to disk.

Relates to ADR-0012 (Knowledge Lifecycle) and ADR-0007 (SQLite Memory backend) by staying **outside** both. Builds on the mission-audit wiring in `cbf5b2a`.

---

## Context

A founder used Kalpavriksha for a real session and asked afterwards what had gone wrong. Nothing could be answered. The desktop composition persisted no conversation, and the process that held it had exited.

`cbf5b2a` fixed half of that by wiring the existing `PersistenceService` event log and `PlanHistory`, so *missions* are now durable. But a founder's session is not only missions. Two of the three things they actually did that day — saying good morning, and asking what Kalpavriksha could do — created no mission at all, and therefore left no trace whatsoever.

The other half is blocked by an explicit prohibition. `MEMORY_ARCHITECTURE.md` §3, "What should never be remembered":

> **Raw conversation text, persisted indefinitely.** Layer 1 (Conversation Memory) exists in-process only and is discarded when the session ends. A user's typed text can contain anything — there's no reason for it to outlive the process by default… If a future Miracle wants that, it's a deliberate, separately-scoped decision, not a side effect of building mission memory.

That paragraph is correct and this ADR does not overturn it. It does exactly what the paragraph asks for: makes the decision deliberately, scopes it narrowly, and says what the resulting data is **not** allowed to become.

## Decision

**Kalpavriksha keeps a local, durable Founder Interaction Audit Trail: an append-only record of what the founder said and what they were shown.**

Its purpose is diagnosis and accountability. Nothing else.

### What this authorises

- Persisting the founder's message text and the exact response handed to the founder surface.
- Correlating those to `mission_id`, `clarification_id`, `approval_id`, `completion_id` and `session_id` where known.
- Reading it back after the process exits, to reconstruct a session.

### What this explicitly does NOT authorise

This is the load-bearing half of the decision:

| Forbidden | Why |
|---|---|
| Interaction records becoming **semantic Memory** | Memory is what Kalpavriksha *knows*. A transcript is what was *said*. ADR-0012's lifecycle starts at Evidence, not at chat. |
| Interaction records becoming **Permanent Knowledge** | "Onkar said X" is not "X is true". |
| Interaction records feeding a **founder profile** | Preference inference from transcripts is a separate product decision nobody has made. |
| Interaction records leaving the machine | `MEMORY_ARCHITECTURE.md` §3's second prohibition stands unchanged: no telemetry, no sync, no network. |
| Interaction records being **searched by the Brain** during reasoning | That would make the transcript an input to decisions, which is Memory by another name. |

The audit trail is written by the surface and read by an investigator. **No component of the Brain, Planner, or Operator reads it.** That is what keeps it an audit trail rather than a memory system, and it is enforceable: a test asserts nothing in `brain/`, `planner/` or the runtime imports it.

### Four separate systems

| System | Question it answers | Where |
|---|---|---|
| **Founder Interaction Audit** | What did Onkar and Somesh say? | this ADR |
| **Mission Audit** | What did Kalpavriksha decide? | `PlanHistory`, `cbf5b2a` |
| **Execution Evidence** | What did it do, and did it verify? | event log + `verification/` |
| **Knowledge** | What has it learned? | ADR-0012 |

They stay separate stores with separate lifecycles. A record moves between them only by a deliberate, reviewed mechanism — which for Knowledge is ADR-0012's promotion gate, and for the other two is nothing at all.

### Identity, not roles

Records name a **direction**, not a generic user/system pair: the founder (Onkar) and the chief of staff (Somesh). Those are two different people and an audit trail that flattened them into `user`/`assistant` would lose the distinction the product is built on.

### Storage and secrecy

`%LOCALAPPDATA%/Kalpavriksha/state`, alongside the mission audit — the convention already established. Append-only JSONL: a corrected record is a new record, never an overwrite, because an audit trail that can be silently rewritten is not evidence.

Infrastructure secrets are never written. The founder's own typed text is recorded verbatim, which is the point — but that is *their* content, kept locally, and never sent anywhere.

## Consequences

**Good.** A founder can use Kalpavriksha for days and then ask what happened, and be answered from evidence. The specific class of defect that motivated this — *"backend verified success, founder saw 'still working'"* — becomes provable rather than arguable, because both sides are recorded.

**Costs accepted.**

- **A local file now contains everything the founder typed.** That is a real privacy surface, deliberately taken, mitigated by staying local, never leaving the machine, and never becoming an input to reasoning. A founder who wants it gone deletes the file; there is no server copy.
- **Unbounded growth.** No retention policy is defined here. Recorded as an open question rather than solved badly — a wrong retention rule silently destroys the evidence this exists to keep.
- **It records what was *shown*, not what was *meant*.** Deliberate: the whole diagnostic value is in capturing the gap between them.
