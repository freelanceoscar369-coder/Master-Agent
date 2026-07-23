# Decisions Log

Running log of architecture and process decisions. Full ADR text lives in
`docs/adr/`; this is the quick-reference summary so a new session (or a
new machine) doesn't have to re-derive context by reading every ADR.

## ADR-0001: Core engine in Python
Chosen over TypeScript/Node and C#/.NET for AI/ML ecosystem maturity and
iteration speed. Consequence: the Desktop UI is necessarily a separate
process/language from the engine, talking over local HTTP/WS — already
the right call for replaceability.

## ADR-0002: "Hermes integration" = local LLM via Ollama
Confirmed by the founder: Hermes is the local-model counterpart to the
cloud ChatGPT integration, served locally via Ollama, behind the same
`ModelProvider` interface as ChatGPT. Still open: which specific Hermes
checkpoint/size to default to.

## ADR-0003: Everything is a plugin behind one contract
Single `Plugin` base contract (manifest + `invoke()`) implemented by
every model provider, capability, and voice adapter. Orchestrator and
Model Router only ever talk to plugins through the registry.

## ADR-0004: Local-first memory, no cloud sync in Founder Edition
SQLite + local embeddings. No multi-device sync in v0.1 — acceptable
under "build for one founder first."

## Mission Brief 001 (2026-07-23): First end-to-end mission
Implemented a real vertical slice — text in, real filesystem write out,
real Permission System gate — using only existing scaffold modules
(`Orchestrator`, `PermissionSystem`, `Mission`) plus one new plugin
(`FilesystemPlugin`) and one new entrypoint (`cli.py`). Found and fixed
two real bugs in code that had previously passed its own unit tests:
`PermissionSystem`'s `ONCE` grant was never consumed (one approval
silently authorized every future call), and the Mission state machine
illegally skipped `EXECUTING` when no approval was needed. Full writeup:
`docs/MISSION_BRIEF_001.md`.

## Mission Brief 001.5 (2026-07-23): Health check + workspace bootstrap
Confirmed all Mission Brief 001 assets intact, no drift from documented
structure. Found: no git repository existed despite two prior deliveries
of the codebase, and the project's canonical location (`D:\MasterAgent`)
could not be verified or written to from any session so far, because the
Claude desktop device bridge has not been connected. This bootstrap
initializes git in the cloud staging copy and adds the top-level runtime
folders, founder documentation set, and Obsidian vault requested in the
brief — all still pending a real transfer to `D:\MasterAgent`. See
`START_HERE.md` for the exact steps to complete that transfer, and
`docs/MISSION_BRIEF_001.md` §"What's production-ready vs. still a stub"
for what's real versus scaffolded in the code itself.

## Open decisions (not yet locked)
- Desktop UI stack: recommended pywebview + local FastAPI server for
  speed-to-ship; Tauri/Electron not ruled out, just not chosen yet.
- Exact Hermes checkpoint/quantization for the founder's hardware.
- Plugin distribution model beyond Founder Edition (marketplace/installer)
  — explicitly out of scope for v0.1; top-level `plugins/` folder exists
  as a placeholder for when this is designed.
- Commit message / tag naming: this bootstrap used "Miracle 001" verbatim
  as instructed for the initial commit and tag (`v0.1.0-miracle-001`).
  If that was meant to read "Mission 001," it's a one-line `git commit
  --amend` / re-tag away from being fixed — flagging here rather than
  silently changing wording you may have chosen deliberately (it does
  echo the Kalpavriksha "wish-granting" theme).
