# What the UI needs from the Kernel

One row per `KernelClient` method. Nothing here is an instruction to change the
backend — it is a statement of what the UI consumes, so the mapping in
`httpKernel.ts` can be written without guesswork.

Where C15.0 already exposes something equivalent, only the mapping is needed.
Where it does not, the UI degrades honestly today (the method returns
`not-implemented` and the screen says so) rather than faking it.

| # | Method | Needs | Priority |
|---|---|---|---|
| 1 | `getBrief` | Since-timestamp, handled count, running count, open judgment requests, flagged receipts, disclosures, headline text | **P0 — Dashboard is empty without it** |
| 2 | `getAttestation` | Per-domain last-checked + healthy flag | **P0 — gates the calm state; see D7** |
| 3 | `listJudgmentRequests` | Open requests incl. the four consequence fields, confidence level, silence default, rank + justification | **P0** |
| 4 | `submitVerdict` | Returns receipt id + undo window seconds | **P0** |
| 5 | `subscribeEvents` | Event stream: type, timestamp, domain, one prose line, signal, refs | **P0 — everything live depends on it** |
| 6 | `queryLedger` | Cursor paging, filter by domain/actor/date/flagged, free text | P1 |
| 7 | `getBoundary` | Autonomy ratio + history series, active rule count, suspended flag | P1 |
| 8 | `listRules` / `listRuleProposals` | Five-part rule shape incl. **consumed vs limit** on the cumulative cap | P1 |
| 9 | `suspendAutonomy` / `resumeAutonomy` | Synchronous, unconditional | P1 |
| 10 | `listMissions` / `getMission` | State, progress, ETA, receipt ids, held-on request id, failure detail | P1 |
| 11 | `listCapabilities` | Reversibility classification per capability; `null` is meaningful (fail-closed) | P2 |
| 12 | `queryMemory` | Kind, freshness (`lastVerifiedAt`), provenance, supersedes/contradicts | P2 |
| 13 | `undo` | Reverse a batch within its window | P2 |
| 14 | `renderLedgerAsProse` | Server-rendered narrative of a ledger slice (Eng. Law III) | P2 |
| 15 | `getScope` | Two sentences: permitted, forbidden | P2 |
| 16 | `getDependencyAudit` | Four lists | P3 — annual |
| 17 | `requestMission` | Founder-initiated work | P3 — currently disabled in the UI with the reason shown |

## Three things the UI assumes and cannot verify

1. **Money is integer minor units.** `Money = { currency, minor }`. If the
   Kernel emits floats, the mapping must convert at the boundary — never let a
   float reach the UI, because sweep totals are summed.
2. **Timestamps are ISO 8601 with an offset.** Deadlines are legally
   consequential ("renews Friday 00:00"); a naive local time will be wrong.
3. **Receipts arrive as intent/outcome pairs sharing an `intentId`.** The
   Ledger Explorer renders them together. If the Kernel emits a single combined
   record, say so and the mapping will synthesise the pair.
