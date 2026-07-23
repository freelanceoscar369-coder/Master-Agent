# Founder Context

Working notes on the founder and constraints this project is built
around — kept factual and sourced from what's actually been established
in project conversations. Sections marked **TBD** are genuinely unknown,
not omitted on purpose; fill them in rather than treating their absence
as an answer.

## Confirmed

- **Primary machine / project root:** Windows, with the project's
  permanent home specified as `D:\MasterAgent` (never Drive C).
- **Target date:** Founder Edition — 2026-08-05.
- **Mandatory Founder Edition features:** voice input, voice output,
  Mission Manager, Planner, ChatGPT integration, Hermes integration
  (confirmed: a local model served via Ollama, not a separate product —
  see `docs/adr/0002-hermes-local-llm.md`), local memory, desktop UI,
  permission system.
- **Working philosophy, stated repeatedly across mission briefs:**
  "Minimum Manual Work. Maximum Agent Work." — the founder wants Claude
  doing the execution, not just advising on it.
- **Engineering style preference:** modular, plugin-first, reuse existing
  scaffolding rather than rewriting, verify before creating, don't
  refactor architecture without being asked, don't delete without
  approval. Each Mission Brief so far has been deliberately scoped
  narrower than "implement everything" — vertical slices over broad
  parallel work.
- **Session environment:** work happens through Claude sessions running
  in a cloud sandbox; the founder's own machine is reached only when the
  Claude desktop app's device bridge is connected, which has not been
  connected in any session so far as of this writing — see the Mission
  Brief 001.5 entry in `DECISIONS.md` and `START_HERE.md` for what that
  means in practice.

## Inferred, not confirmed

- **Solo founder.** "Build for one founder first, scale for millions
  later" strongly implies a single founder rather than a team, but this
  hasn't been stated outright — worth confirming rather than assuming
  permanently, since it affects things like whether Local Memory ever
  needs multi-user awareness.

## TBD

- Funding / company stage.
- Target users beyond the founder (who is "millions later," specifically?).
- Non-Windows environments in scope, if any.
- Budget or preference constraints on cloud API usage (ChatGPT costs
  money per call — no stated ceiling yet).
- Whether "Hermes" checkpoint choice has been made (`ARCHITECTURE.md` §6
  still lists this as open).
