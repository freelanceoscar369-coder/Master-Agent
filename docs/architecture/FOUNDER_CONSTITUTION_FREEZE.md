# Founder Constitution Freeze

Status: **Frozen** — 2026-07-26
Produced by: Mission Brief 021, Revision 3 (design-only — no code, no tests, no packages)
Governs: `KALPAVRIKSHA_VISION_V2.md` (the Constitution itself)

This document is the freeze record: what was resolved, what remains
deliberately open, the single-page Section Status Registry, and the Final
Founder Review this Mission Brief was created to produce. It does not
restate the Constitution's content — see `KALPAVRIKSHA_VISION_V2.md` for
that. This document exists so a future session can answer "is the
Constitution frozen, and on what basis" without re-reading the full
document or re-deriving the audit trail.

---

## 1. How we got here

1. Mission Brief 021 (original) asked for a from-scratch "Executive Body"
   architecture, assuming Mission Briefs 006–020 existed as prior design
   input. They did not — confirmed absent from this repository, its git
   history, and every known backup (`D:\Backups\MasterAgent_PreRecovery_
   20260724_021917`, both delivery ZIPs in `Downloads`). That Mission
   Brief was paused rather than fabricating prior history.
2. `KALPAVRIKSHA_VISION_V2.md` v2 was produced instead, correctly grounding
   "Executive Brain / Universal Executive Operator" vocabulary in the real,
   verifiable Mission Briefs 001–005 and their supporting documents
   (`ARCHITECTURE.md`, `MEMORY_ARCHITECTURE.md`, `FILESYSTEM_CAPABILITIES.md`,
   ADRs 0001–0009) rather than the fictitious MB006–020.
3. An independent architecture audit reviewed v2 against internal
   consistency, completeness, separation of concerns, long-term
   scalability, product independence, knowledge/verification/recovery
   philosophy, future extensibility, and vision alignment. It returned a
   readiness score of 58/100 and five major findings, verified against
   source where possible (not just prose).
4. This Mission Brief (021, Revision 3) resolves every item the audit and
   the founder's own follow-on instructions raised. It is design-only —
   no source file under `src/` or `tests/` was touched.

---

## 2. The ten items, resolved (pointer, not restatement)

| # | Item | Resolved in |
|---|---|---|
| 1 | Introduce Shared Infrastructure layer | `KALPAVRIKSHA_VISION_V2.md` §5, ADR-0010 |
| 2 | Verification as first-class subsystem | `KALPAVRIKSHA_VISION_V2.md` §10, ADR-0011 |
| 3 | Formalize the Knowledge Lifecycle | `KALPAVRIKSHA_VISION_V2.md` §9.3–9.5, ADR-0012 |
| 4 | Remove product-specific terminology | `KALPAVRIKSHA_VISION_V2.md` §14, §21 (scrubbed throughout §1–§20) |
| 5 | Design for multiple Operators | `KALPAVRIKSHA_VISION_V2.md` §8, ADR-0013 |
| 6 | Clarify ownership, exactly once each | `KALPAVRIKSHA_VISION_V2.md` §16 |
| 7 | Reduce duplication, one source of truth | `KALPAVRIKSHA_VISION_V2.md` §20 (Rules 1/9 merged, Rules 5/14 merged, Rule 6 stated once) |
| 8 | Freeze terminology | `KALPAVRIKSHA_VISION_V2.md` §17 |
| 9 | Future-proof the Constitution | See §3 below |
| 10 | Section status labels | `KALPAVRIKSHA_VISION_V2.md` §18, and this document's §4 registry |

### Item 9 in detail — future-proofing review

| Future need | Already supported by | Still open |
|---|---|---|
| New Reasoning Providers (new AI models) | Capability Registry + Model Router extension model (§3.3, §5.1) — one new Worker, zero router edits | — |
| New Environment categories (new OSes, new hardware, robotics, IoT) | Environment / Environment Instance abstraction (§7, §8) generalizes cleanly — nothing in the category list is closed | Stateful, multi-Step sessions inside the Worker/Action contract (needed for Browser, Terminal, Robotics) — named, not solved, see §3 below |
| Future interfaces (voice, messaging, new transports) | Transport-agnostic Brain/Operator core, unchanged from v2 (§13) | — |
| Technologies not yet invented | Extension-by-new-implementation-of-existing-contracts philosophy (`ARCHITECTURE_PRINCIPLES.md`, unchanged) | — |
| Multiple simultaneous Operators | Operator Instance / Environment Instance / Operator Registry (§8, ADR-0013) | Concurrent DAG-branch dispatch across Operator Instances — explicitly scoped as a future, dedicated Mission Brief (§8.5) |

---

## 3. Named, deliberately open items (not blockers)

Per Rule 10 ("Technical Debt Is Named Honestly"), applied to this freeze
itself:

1. **In-mission recovery decision procedure** (`KALPAVRIKSHA_VISION_V2.md`
   §11.4). This revision connects a failed Verification Verdict to the
   Brain as a recovery trigger, but does not specify the exact rule for
   when the Orchestrator's own retry/failure-branching policy absorbs a
   failure versus when it must escalate to a full re-plan versus when it
   must surface to a human. Not a blocker: nothing on `ROADMAP.md` today
   (the real Planner, item 1) depends on this being resolved first.
2. **Stateful Environment Sessions inside the Worker/Action contract**
   (`KALPAVRIKSHA_VISION_V2.md` §8.3, §12, marked EVOLVABLE). Today's
   Action contract is one-shot (`validate()` → `run()`); Browser,
   Terminal, and Robotics capabilities will eventually need a capability
   that holds a live handle across multiple `Step`s in one Mission. Not a
   blocker: no current Worker needs this, and nothing on `ROADMAP.md`
   requires it before the real Planner work.
3. **Concurrent dispatch across Operator Instances** (`KALPAVRIKSHA_
   VISION_V2.md` §8.5). Deliberately left EVOLVABLE per this Mission
   Brief's explicit instruction not to design a distributed system. Not a
   blocker for the same reason.
4. **MB006–MB020 remain absent** from this repository and all known
   backups. The Constitution does not depend on their content — every
   claim in it traces to a document verified to exist. Noted here so a
   future session doesn't rediscover this as a surprise.

None of these four items block implementation of what is actually next on
`ROADMAP.md` (the real Planner). They are named so they are not forgotten,
each already carries the correct EVOLVABLE/RESEARCH-BACKED status in the
Constitution, and each becomes a blocker only for the *specific* future
work that depends on it (advanced recovery; Browser/Terminal/Robotics
capabilities; multi-Operator concurrency) — not for Founder Edition's
current roadmap.

---

## 4. Section Status Registry

Single-page copy of `KALPAVRIKSHA_VISION_V2.md` §18's per-section tags, for
quick reference without opening the full document.

| § | Section | Status |
|---|---|---|
| 1 | Project Vision | FROZEN |
| 2 | Core Principles | FROZEN |
| 3 | Executive Brain Responsibilities | FROZEN |
| 4 | Universal Executive Operator Responsibilities | FROZEN |
| 5 | Shared Infrastructure Layer | FROZEN |
| 6 | Brain / Shared Infrastructure / Operator Separation | FROZEN |
| 7 | Universal Environment Philosophy | EVOLVABLE |
| 8 | Multi-Operator Architecture | RESEARCH-BACKED |
| 9.1–9.2 | Permanent Knowledge, Temporary Observations, Evidence Hierarchy | FROZEN |
| 9.3–9.5 | Knowledge Lifecycle | RESEARCH-BACKED |
| 10 | Verification Philosophy | RESEARCH-BACKED |
| 11 | Recovery Philosophy | EVOLVABLE |
| 12 | Worker and Plugin Runtime | IMPLEMENTATION DETAIL |
| 13 | Environment Independence | FROZEN |
| 14 | Product Agnosticism | FROZEN |
| 15 | Human Oversight Philosophy | FROZEN |
| 16 | Ownership Registry | FROZEN |
| 17 | Terminology Freeze | FROZEN |
| 18 | Section Status Legend | FROZEN |
| 19 | Long-term Founder Edition Vision | EVOLVABLE |
| 20 | Immutable Architecture Rules | FROZEN |
| 21 | Illustrative Implementations | IMPLEMENTATION DETAIL |
| 22 | Appendix: Source Document Traceability | (index, not tagged) |

**Reading this table:** FROZEN and RESEARCH-BACKED sections are both safe
to implement against — the difference is FROZEN has already held up under
audit and real usage (e.g., the Evidence Hierarchy), while RESEARCH-BACKED
is newly reasoned-through and expected to be refined once real usage
exists (e.g., Verification, Knowledge Lifecycle, Multi-Operator). EVOLVABLE
sections are meant to keep growing without a Constitution revision.
IMPLEMENTATION DETAIL sections live here for continuity but are not
architecture-constitution material.

---

## 5. Final Founder Review

**Question:** Can Founder Edition now be implemented without changing the
Constitution?

**Answer: YES, for everything currently on `ROADMAP.md` — with three named
exceptions that are not blockers, because nothing currently planned
depends on them.**

Reasoning:

- `ROADMAP.md`'s next planned item is the real Planner (replacing
  `cli.py`'s regex stand-in with a live Model Router call), followed by
  Planner-context-from-Memory, conversational phrasing for existing
  capabilities, a second project template, and a third Executor-relay
  instance. None of these five items require Verification's Expected
  Outcome/Observation mechanism to be built, require a second Operator
  Instance to exist, or require Promotion Review to be implemented — they
  need Shared Infrastructure's Capability Registry, Permission System, and
  Memory (§5) to keep behaving exactly as `ARCHITECTURE.md` already
  describes them, which this revision confirms rather than changes at the
  implementation level.
- The three items named in §3 above (in-mission recovery decision
  procedure, stateful Environment Sessions, concurrent multi-Operator
  dispatch) are real, honestly-named gaps — but each is a prerequisite for
  a *specific future* capability (respectively: complex failure recovery;
  Browser/Terminal/Robotics Workers; parallel execution across
  environments), none of which are scheduled before the real Planner.
  They do not block the next Mission Brief; they block whichever future
  Mission Brief is the first to actually need them, at which point that
  brief's design phase resolves them the same way this one resolved the
  five major audit findings — a normal, expected mode of Constitution
  evolution (§18's whole point in defining EVOLVABLE and RESEARCH-BACKED
  as distinct from FROZEN), not a sign the freeze is premature.
- Every major finding from the independent audit (the crossed Brain/
  Operator boundary, the self-contradicting product-name usage, the
  nominal-not-structural Verification, the unplaced `MasterAgentSession`/
  `MissionManager`/`Reporter`, the disclaimed multi-worker/multi-operator
  scaling) has a corresponding resolution in `KALPAVRIKSHA_VISION_V2.md`,
  each backed by an ADR with rejected alternatives recorded (ADR-0010
  through ADR-0013), matching this project's own standing bar for what
  makes a design decision reviewable (`FOUNDER_PLAYBOOK.md`'s "Design
  decisions with rejected alternatives get written down").

**Declaration: the Constitution is frozen.** `KALPAVRIKSHA_VISION_V2.md`,
Revision 3, is the authoritative architectural reference for all Mission
Briefs from MB021 forward. Amending it requires a new Mission Brief that
updates both the Constitution and this freeze record together.

This is the final architecture-only Mission Brief before implementation
resumes. The next Mission Brief should be `ROADMAP.md` item 1 (the real
Planner) — an implementation brief, not a design brief.
