# ADR-0001: Core engine implemented in Python

Status: Accepted (2026-07-23)

## Context
The core engine (Orchestrator, Planner, Mission Manager, Permission System,
Plugin Runtime, Model Router) needs a language with fast iteration speed for
a solo founder on a 13-day runway to Founder Edition, strong local-AI
tooling (STT/TTS bindings, embedding libraries, Ollama/OpenAI SDKs), and an
easy plugin story (dynamic import).

Alternatives considered: TypeScript/Node (one language across engine + UI,
huge npm ecosystem), C#/.NET (native Windows integration, since the
founder's dev machine and initial target are Windows).

## Decision
Python for the core engine. TypeScript/Node was close — it wins on "one
language across the stack" — but Python wins on raw AI/ML ecosystem
maturity (local model tooling, STT/TTS libraries, embeddings) and lets us
move fastest for the mandatory Founder Edition feature set.

## Consequences
- The Desktop UI is a separate process/language from the engine by design
  (see ARCHITECTURE.md §4.9) — this was already the right call for
  replaceability, and it's *necessary* now since UI and engine aren't the
  same language.
- Plugin authors write Python. If we ever want third-party plugins in other
  languages, the Plugin contract will need a process-boundary (subprocess +
  JSON-RPC) variant — not needed for Founder Edition, worth a future ADR.
- Packaging a Python engine as a distributable Windows app (PyInstaller /
  similar) becomes a task on the critical path before ship.
