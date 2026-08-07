# Mission Brief 034 — Persistent Founder Memory & Knowledge Repository

Status: **Shipped** — 2026-07-30

**No new ADR.** No frozen component changed, so none was needed.

## Objective

Kalpavriksha knew what it was *doing*. After MB034 it knows what the
founder *told it* — across restarts, without an LLM anywhere near the
answer.

Proved live: told to one process, asked of the next.

```
PROCESS 1
  > remember "Founder prefers Gemma by default"
    remembered [mem-000001] Founder prefers Gemma by default
  > remember "Founder prefers Gemma by default"
    already remembered [mem-000001] Founder prefers Gemma by default

PROCESS 2  (a fresh launch, 4 memory record(s) restored)
  > memory gemma
    1 match(es): [mem-000001] Founder prefers Gemma by default
  > memory docker
    1 match(es): [mem-000004] Last verification failed because Docker daemon was not running
  > memory blockchain
    nothing remembered about 'blockchain'
```

## 1. What changed, and what did not

**Zero frozen files modified.** `runtime/`, `mission_control/`,
`persistence/`, `executor/`, `verification/`, `plugins/` and `broker/` are
untouched — the `git diff` guard shows the same seven files MB032
accounted for, and MB034 added none.

`memory/` was **not** a new package: MB004 shipped Layers 1–3 there
(conversation, mission, SQLite mission history) with an empty
`__init__.py`. The five modules MB034 names are purely additive beside
them, and `cli.py`'s existing memory path is untouched — the brief's own
instruction to *compose rather than rewrite*.

This is Layer 4 arriving: the "durable facts distinct from mission
history" that `memory/future.py` reserved. That two-method sketch is left
in place rather than retrofitted — MB034 specifies a richer contract, and
two shapes for one idea is worse than one superseded stub.

Also changed, all additive: `dashboard/` (a MEMORY section),
`launcher/boot.py` (construct, load, subscribe), `launcher/console.py`
(two verbs), `launcher/main.py` (hand the console its memory).

## 2. Where it lives, and why beside the state

```
.master_agent/
    state/                  <- MB025's snapshot and event log
    memory/
        knowledge.json      <- the records. Authoritative.
        index.json          <- the index. Derived, and disposable.
```

Beside rather than inside, deliberately: MB025's snapshot is *operational*
state a recovery may legitimately discard, and founder memory is not.
Losing what the founder said because a mission crashed would be the worst
possible reading of "recovery".

Two files, two attitudes to corruption:

- **`knowledge.json` is authoritative**, so a file that will not parse is
  *moved aside* with a `.corrupt` suffix, never overwritten. A founder can
  open it and copy their notes out; they cannot recover a file this
  program replaced. A second corruption does not clobber the first.
- **`index.json` is derived**, so a bad one costs nothing. It is rebuilt
  in silence. The store checks the index *equals* what the records imply
  rather than checking its size — an index with the right number of wrong
  entries is the failure hardest to notice.

One bad record row is skipped and counted, not fatal — the same tolerance
the event log gives a truncated final line — and the count reaches the
boot report, so a founder learns three memories were unreadable at the
moment it matters.

## 3. Deterministic retrieval, and the ranking a founder can predict

No vector DB, no embeddings, no semantic search, no model call. The whole
of `memory/` imports nothing that could embed or call one, and a test
asserts it against twelve module names.

Which leaves ranking as the only interesting part, so it is stated rather
than tuned:

| Match in | Weight | Why |
|---|---|---|
| tag | 8 | somebody chose that word to file it under |
| title | 4 | somebody chose that word to name it |
| summary | 2 | the opening of what they wrote |
| full text | 1 | the word is in there somewhere |

Ties break on importance, then recency, then id — so the same query
returns the same list forever, and the order does not depend on insertion
order. Matching is exact: `fail` does not find `failure`. That is a
surprise a founder can see and work around; a stemmer matching the wrong
thing is one they cannot.

All six lookups MB034 names are there — `find_by_tag`,
`find_by_category`, `recent`, `related`, `search`, `critical` — plus
`search_hits`, which carries the arithmetic so *"why did that come
first?"* is answerable without re-running anything.

`related()` walks the graph **both ways**: a record's own `related_items`
and everything pointing at it, through a backlink index. Ids only, no
graph database, and a dangling id is a skipped neighbour rather than a
crash.

## 4. Automatic memory rides the existing bus

Six subscriptions on the Event Bus Mission Control already publishes on —
the same door `PersistenceService` uses. **Per event type, not to
everything**: the Runtime publishes a heartbeat every cycle, and a memory
system that had to ignore most of what it saw would eventually stop
ignoring one.

| Event | Category | Importance |
|---|---|---|
| `objective_submitted` | *(learns the name; writes nothing)* | — |
| `objective_completed` | Mission Outcomes | NORMAL |
| `objective_failed` | Failure Library | HIGH |
| `verification_completed` (matched) | Success Library | NORMAL |
| `verification_completed` (other) | Failure Library | HIGH |
| `approval_granted` / `approval_denied` | Business Decisions | HIGH |

Submission is deliberately not a memory: a mission that was *started* is
not an outcome, and remembering intentions alongside results would make
Mission Outcomes untrustworthy.

Recovery has no event — MB025 runs `recover()` before recording starts —
so the composition root hands the report in, the same shape the Dashboard
gets it. Architecture decisions have no event either, and inferring one
from a diff would be exactly the guessing this brief forbids, so
`remember_architecture()` is a door used by whoever knows.

## 5. Saying the same thing twice is one memory

A write whose content digest already exists updates that record instead of
adding one. The digest covers category, title and body — deliberately not
tags, importance or timestamps, so re-stating a fact with a new tag is the
same fact.

Merging unions tags and links, and importance can only go **up**: a
founder repeating something is usually emphasising it. A suppressed
duplicate does not consume an id, so the sequence has no unexplainable
gaps.

Without this, "how many things do I know" would count how often the
founder repeated themselves — and the automatic path would have written
one record per identical verification verdict.

## 6. Verification

**315 new tests, 2610 passing, 1 skipped, zero regressions** (2295
before). **100% statement coverage** of all five new modules:

```
src/master_agent/memory/knowledge_store.py    138 stmts  100%
src/master_agent/memory/memory_index.py        94 stmts  100%
src/master_agent/memory/memory_models.py      114 stmts  100%
src/master_agent/memory/memory_query.py        97 stmts  100%
src/master_agent/memory/memory_service.py     174 stmts  100%
TOTAL                                         617 stmts  100%
```

Every item on the brief's list has tests: persistence, restart recovery,
manual memory, automatic memory, search, indexing, graph links, corruption
recovery, duplicate suppression, and deterministic ordering.

## 7. Three defects, each found by running it

1. **A full stop the founder did not type.** `derive_summary` split
   sentences on `"."`, so *"quality floor exceeds 0.9"* became *"…exceeds
   0.9."*. A decimal is not a sentence break; it splits on `". "` now.
2. **Missions remembered by UUID.** `OBJECTIVE_COMPLETED` carries only an
   id, so every mission memory was titled *"Mission completed:
   a43de263-d959-46f7…"* — a fact about a UUID rather than about the
   founder's work. The description is now learned from the submission
   event and held process-locally; a mission recovered from a previous run
   has no submission event on this bus and falls back to the id, which is
   still something to search for.
3. **Every restart wrote "Recovered 0 objective(s)".** An empty snapshot
   still counts as `recovered`, so a launch that restored nothing wrote a
   memory saying so — and that one line then owned Recent Learnings, Top
   Tags and Last Written, pushing everything the founder actually said
   below it. Found by reading a live founder page. A recovery is now
   remembered only when objectives or quarantined tasks actually came
   back.

A fourth thing worth recording, which was a *test* defect rather than a
code one: a mission naming an unregistered capability fails at dispatch,
so my first "completed mission" test was writing both a failure and a
completion. Mission Control was right. The fixture now registers the
capability, and the behaviour it exposed — a mission nothing can serve is
a real failure worth remembering — became its own test.

## 8. Debt and known limitations (Rule 10)

1. **Atomic JSON writing is now implemented three times**
   (`persistence/store.py`, `ai_infrastructure/ledger.py`,
   `memory/knowledge_store.py`). The shared helper it wants would have to
   live in a package frozen since MB025, so it is named here rather than
   smuggled in.
2. **The whole file is rewritten on every write**, like the decision
   ledger. Fine at founder-edition volumes; it joins the same unbounded-
   growth item already on the roadmap for the event log.
3. **`confidence` is always 1.0.** Everything stored is stated or
   observed. The field exists for inferred records — a Recurring Lesson
   drawn from several failures — and nothing infers yet, which is also why
   **Recurring Lessons and Open Questions have no automatic writer**.
   Both are reachable manually.
4. **`Prompt Library` has no automatic writer either.** MB033 records
   every execution in the decision ledger; promoting a *successful prompt*
   into memory needs a verifier to know it succeeded, which is the same
   gap that keeps MB033's Prompt Cache empty.
5. **Search is whole-word and unstemmed.** `memory fail` does not find
   *failure*. Deliberate (see §3), and a founder-facing surprise
   nonetheless.
6. **No editing or forgetting.** A record can be updated by re-stating it
   and linked to others, but there is no `forget()`. Deleting founder
   memory is a decision that deserves its own thinking about approval and
   evidence rather than a method added in passing.
7. **The objective-name map is process-local** and not persisted, so a
   mission that outlives a restart is remembered by id. Persisting it
   would mean a second store for something that is only ever used at the
   moment a memory is written.
