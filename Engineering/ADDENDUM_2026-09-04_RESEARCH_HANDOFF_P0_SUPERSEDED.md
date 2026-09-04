# ADDENDUM — 2026-09-04 Research handoff, P0 statement superseded

**Status:** superseding addendum. Nothing in the 4 Sep Research handoff is
edited or deleted by this document. That handoff remains the record of what was
believed when it was written; this records what later evidence established.

**Authoritative commit:** `deafb50ed72fba302bebacc55ecaed568107f7d7`
(`codex/founder-research-v1`) — verified present as HEAD on the migrated
laptop, `fsck` clean.

---

## 1. The statement being superseded

The 4 Sep Research handoff carries this P0:

> continuation-plan admission appeared provider/model-sensitive

That reading was reasonable on the evidence available at the time. It is
**stale**, and it must not be used to direct further work.

## 2. Why it is stale

At `deafb50` the universal tool-use slice is **proven**:

- the Gemini trusted-web route was reached;
- the **Onkar** profile was selected autonomously, without asking the Founder;
- the frozen Stage 1 prompt was delivered.

The run nevertheless produced no usable provider answer, because:

- **current-turn extraction captured the ~26K USER prompt echo instead of
  Gemini's provider response.**

The planner therefore never saw a Gemini answer. It saw the prompt again.

## 3. What follows

A measurement that never received the provider's response cannot be evidence
about that provider's planning ability. Accordingly:

```
GEMINI PLANNER SUITABILITY = UNMEASURED
```

Not "poor", not "provider-sensitive" — **unmeasured**. The earlier
provider/model-sensitivity reading was an artifact of reading the echoed user
prompt as if it were a model answer.

## 4. The current first causal defect

```
TRUSTED-WEB CURRENT-TURN RESPONSE OWNERSHIP
```

This is the first thing in the causal chain that is actually broken. Until it
is closed, every downstream provider comparison is measuring the harness, not
the provider.

### Invariants the repair must satisfy

- prompt size must not alter ownership;
- user turn ≠ provider turn;
- conversation history ≠ current provider turn.

### What the repair must prove

- the provider answer is returned;
- the submitted prompt is **never** returned as a fallback answer;
- same conversation, no duplicate, bounded waiting.

No Gemini-specific text hacks: a fix that pattern-matches Gemini's markup would
re-break on the next surface and would not be evidence of ownership.

## 5. Consequence for sequencing

Any Gemini Web planner benchmark run **before** current-turn ownership is
closed is void by construction. Only a correctly-owned provider response may
enter the Planner parser.

## 6. What this addendum does not reopen

Unchanged and not reopened: Stage 1 trusted obligation work, the Universal Tool
architecture, Broker architecture, Founder identity semantics, and the
free-model economic doctrine. This addendum narrows one stale P0; it does not
disturb those.
