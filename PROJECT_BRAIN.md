# Project Brain

**If you only read one file in this repo, read this one.** It's the
orientation index — where things stand, and where to go for detail. Meant
to be read cold by a new session, a new machine, or a future you who's
forgotten the details.

## What this is

Master Agent: an AI orchestration platform that turns a stated intention
into a completed, verified outcome, instead of the human manually
managing multiple AI tools. See `WHY.md` for the reasoning, `MANIFESTO.md`
for the values, `PRODUCT_PRINCIPLES.md` for the engineering rules those
values imply.

## Where things stand right now (2026-07-23)

- **The architecture is designed and documented**, not just implemented
  ad hoc: `ARCHITECTURE.md` is the system design; `docs/adr/` explains
  *why* each major choice was made.
- **Mission Brief 001 is real and working**: one full mission
  ("create a folder called Demo") runs end to end through the actual
  Orchestrator, Permission System, and Mission state machine — not a
  mock. 23 tests pass. Full detail and an honest "what's production-ready
  vs. still a stub" accounting: `docs/MISSION_BRIEF_001.md`.
- **This bootstrap (Mission Brief 001.5)** adds the founder-workspace
  scaffolding — top-level runtime folders, this documentation set, the
  Obsidian vault, git — around that working code, without touching the
  code itself.
- **What's still a stub, unchanged:** Planner (real model-driven
  planning), Mission Manager (persistence + multi-mission lifecycle),
  Model Router wiring to live providers, Memory persistence, Voice I/O,
  Desktop UI. See `ROADMAP.md` for what's next and in what order.

## Where to go for what

| Question | File |
|---|---|
| Why does this exist? | `WHY.md` |
| What do we value / what tradeoffs does that force? | `MANIFESTO.md`, `PRODUCT_PRINCIPLES.md` |
| How is the system designed? | `ARCHITECTURE.md` |
| Why was each design choice made? | `docs/adr/*.md`, summarized in `DECISIONS.md` |
| What's actually built and working right now? | `docs/MISSION_BRIEF_001.md` |
| What's next, and in what order? | `ROADMAP.md` |
| What's known/unknown about the founder and constraints? | `FOUNDER_CONTEXT.md` |
| How do I set this up on a new machine? | `START_HERE.md` |
| Is the deadline realistic? | `docs/TIMELINE_RISK.md` |
| Raw, unstructured notes / journal / research | `obsidian/` vault |

## Standing constraints worth repeating

- **Local-first architecture, cloud enhancement when beneficial.**
- **Human approval before important actions** — non-negotiable, and the
  approval UX itself has to stay simple (see the tension named in
  `MANIFESTO.md`).
- **Reuse existing scaffolding; don't refactor architecture without being
  asked; don't delete without approval.** Every mission brief so far has
  honored this — check `DECISIONS.md` before assuming a module needs
  rebuilding rather than reusing.
- **"Minimum Manual Work. Maximum Agent Work."** The recurring philosophy
  across every brief — the agent does the execution, the founder
  approves and directs.
