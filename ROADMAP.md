# Roadmap

Living document — update it as briefs complete or plans change. This is
the founder-facing view; `docs/TIMELINE_RISK.md` has the detailed
reasoning behind the Founder Edition pacing below.

## Status as of 2026-07-23

| Milestone | Status |
|---|---|
| Architecture scaffold (all 9 modules stubbed) | Done |
| Mission Brief 001 — first end-to-end mission (`create a folder`) | Done |
| Mission Brief 001.5 — health check + workspace bootstrap | In progress (this brief) |
| Founder Edition (voice, planner, both model providers, memory, desktop UI, permissions) | Not started — target 2026-08-05 |

## Founder Edition — reverse-plan checkpoints

From `docs/TIMELINE_RISK.md`, reproduced here so it's visible without
opening a second file. Treat these as a starting point to argue with, not
a locked commitment:

1. **Model Router + both providers** answering a basic prompt.
2. **Planner + Mission Manager** state machine, Permission System gate
   (Mission Brief 001 already proved the Permission System + Mission
   state machine work end to end for one hand-built plan — this step is
   about making the Planner generate that plan instead of hand-coding it).
3. **Voice I/O**, wired to the Intent Layer and Reporter.
4. **Desktop UI shell** talking to the engine over HTTP/WS.
5. **Integration pass** on one golden-path mission, no new features in
   the final ~72 hours before the deadline.

## Near-term (post-001.5)

Suggestions from `docs/MISSION_BRIEF_001.md`, in recommended order:

1. **Mission Brief 002 — Memory that matters.** Wire `SQLiteMemoryStore`
   for real; persist `Mission.outcome` across restarts; recall the last N
   missions.
2. **Mission Brief 003 — A second capability.** Prove the Orchestrator's
   capability resolution works with more than one plugin/capability in
   the registry (Mission Brief 001 only ever exercised a single plugin).
3. **A real Planner call** through one model provider (Hermes first — no
   API key needed, keeps testing fast), replacing the hand-built
   `build_plan()` for the create-folder case specifically, verified
   against Mission Brief 001's existing test suite before intent parsing
   generalizes further.

## Explicitly not on this roadmap yet

Plugin marketplace/installer, multi-device memory sync, non-Windows
support, team/multi-user features — all deliberately deferred per "build
for one founder first" (`PRODUCT_PRINCIPLES.md`). Don't schedule work
against these without a concrete trigger for why they're needed now.
