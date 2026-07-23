# Master Agent Handover Document

## Project Objective
Master Agent exists to take over the coordination layer between human intention and completed outcomes. It is not merely another chatbot but a system that plans, delegates, executes, verifies, learns, and reports back to the user. The core principle is the Kalpavriksha Principle: **Intent → Plan → Delegate → Execute → Verify → Learn → Report**.

## Current Architecture
The system is designed with a plugin-based architecture where each module is a separate Python package under `src/master_agent/`. Key modules include:

1. **Intent Layer**: Converts raw input (voice/text) into structured `Intent` objects.
2. **Planner**: Creates a `MissionPlan` (DAG of Steps) from an `Intent`.
3. **Mission Manager**: Owns the `Mission` entity and its state machine (draft → planned → awaiting_approval → executing → verifying → completed | failed | cancelled).
4. **Permission System**: Blocks any step above read-only risk until human approves.
5. **Orchestrator**: Resolves each Step to a Plugin via the Plugin Registry, invokes it, and collects results.
6. **Plugin Runtime**: Includes Model Providers (ChatGPT, Hermes-local), Capability Plugins (filesystem, calendar, browser, etc.), and Voice I/O Adapters (STT, TTS).
7. **Verifier**: Checks outcome against the Intent's success criteria.
8. **Reporter**: Returns voice + UI report to the human.
9. **Local Memory**: Records mission + outcome for future planning (Learn).

Guiding constraints:
- Intent over prompts
- Outcome over output
- Everything is a plugin
- Human approval before important actions
- Local-first, cloud-enhanced
- Replaceable modules

## Completed Work
- Architecture scaffold (all 9 modules stubbed) - Done
- Mission Brief 001 — first end-to-end mission (`create a folder`) - Done
- Mission Brief 001.5 — health check + workspace bootstrap - In progress (as of 2026-07-23)
- Permission System and Mission Manager state machine proven end-to-end for one hand-built plan (from Mission Brief 001)
- Local memory prototype (SQLite-based) in place
- Basic plugin registry and interfaces defined
- Initial VOICE I/O adapters (placeholder)
- Desktop UI shell concept (HTTP/WS based)
- Model Router capable of routing between local Hermes and ChatGPT providers

## Pending Work
- Finalize Mission Brief 001.5 (health check + workspace bootstrap)
- Begin Founder Edition milestones:
  1. Model Router + both providers answering a basic prompt.
  2. Planner + Mission Manager state machine, Permission System gate (make Planner generate the plan instead of hand-coding).
  3. Voice I/O wired to Intent Layer and Reporter.
  4. Desktop UI shell talking to the engine over HTTP/WS.
  5. Integration pass on one golden-path mission.
- Mission Brief 002: Memory that matters (persist Mission.outcome across restarts, recall last N missions)
- Mission Brief 003: A second capability (prove Orchestrator's capability resolution works with multiple plugins)
- A real Planner call through one model provider (Hermes first) to replace hand-built `build_plan()` for create-folder case

## Roadmap
See `ROADMAP.md` and `TIMELINE_RISK.md` for detailed pacing. As of 2026-07-23:

| Milestone | Status |
|-----------|--------|
| Architecture scaffold (all 9 modules stubbed) | Done |
| Mission Brief 001 — first end-to-end mission (`create a folder`) | Done |
| Mission Brief 001.5 — health check + workspace bootstrap | In progress |
| Founder Edition (voice, planner, both model providers, memory, desktop UI, permissions) | Not started — target 2026-08-05 |

Near-term post-001.5 suggestions:
1. Mission Brief 002 — Memory that matters.
2. Mission Brief 003 — A second capability.
3. A real Planner call through one model provider.

Explicitly not on roadmap yet: Plugin marketplace/installer, multi-device memory sync, non-Windows support, team/multi-user features.

## Important Decisions
- **Local-first, cloud-enhanced**: System must work fully offline with local model and memory; cloud providers are optional enhancements.
- **Human approval gate**: No plugin may execute a step above read-only risk without explicit human approval via Permission System.
- **Plugin-based architecture**: Core engine should be minimal; almost all capability lives in plugins behind a common registry and contract.
- **Replaceable modules**: Every module is swappable behind its interface without touching others (e.g., swap SQLite for Postgres, Piper for cloud TTS).
- **Intent over output**: System captures structured Intent (goal, constraints, context, success criteria) rather than raw prompts.
- **Outcome over output**: Mission is "done" only when Verifier confirms real-world state matches Intent's success criteria.

## Technical Debt
- Current implementation uses stubs for many modules; need to replace with functional implementations.
- Voice I/O adapters are placeholders.
- Plugin registry and discovery mechanisms need finalization.
- Permission System UI integration (voice/UI) not yet complete.
- Local memory schema may need evolution as mission complexity grows.
- Error handling and logging foundations are basic.
- No automated test coverage beyond Mission Brief 001 validation scripts.

## Next Milestones
1. Complete Mission Brief 001.5 (health check + workspace bootstrap).
2. Achieve Model Router + both providers responding to a basic prompt.
3. Implement Planner-generated Mission Plan (replacing hand-built plan) with Permission System gate.
4. Wire Voice I/O to Intent Layer and Reporter.
5. Build Desktop UI shell capable of sending/receiving messages over HTTP/WS.
6. Execute integration pass on a golden-path mission (e.g., create a folder, write a file, verify outcome).
7. Proceed to Mission Brief 002 and 003 as outlined in the roadmap.

---
*This document was generated to separate MasterAgent work from Arjun Options Bot work. No Arjun source code was modified during this process.*