# Founder Edition Timeline Risk Assessment

Date of assessment: 2026-07-23
Target date: 2026-08-05
Runway: 13 days

## Honest read

Nine mandatory features (voice input, voice output, mission manager,
planner, ChatGPT integration, Hermes integration, local memory, desktop UI,
permission system) in 13 days is achievable as a **working, dogfoodable
v0.1** if scope is deliberately narrowed to one golden path — it is **not**
achievable as nine independently polished subsystems. Treating this list as
nine parallel deliverables is the most likely way to miss the date; treating
it as one coherent path with nine visible seams is how it gets hit.

## Where the real risk is

- **Voice I/O** is the feature most likely to eat unplanned time — STT/TTS
  quality tuning, latency, and mic/device handling on Windows are the kind
  of thing that looks done in a demo and then breaks on the founder's
  actual hardware. Budget this first, not last.
- **Permission System UX** is easy to under-scope. "Human approval before
  important actions" needs to actually interrupt a running mission
  cleanly and resume it — that's a real state-machine feature, not a
  confirm dialog bolted on afterward.
- **Two model providers on day one** (ChatGPT + Hermes) means the Model
  Router has to work correctly before either integration can be called
  "done" — there's no serial fallback where you ship ChatGPT-only and add
  Hermes later without revisiting the router.
- **Nine subsystems integrating for the first time** in the same window
  they're each being built is where schedule risk compounds — the last
  ~72 hours before Aug 5 should be integration and end-to-end testing, not
  new feature work. Reverse-plan from that.

## Recommendation

Define one golden-path mission end-to-end — e.g. *"say a command → Planner
produces a plan → Permission System asks for approval on the one
irreversible step → Orchestrator executes via 2–3 real plugins → Verifier
confirms → voice + UI report back"* — and get that path fully working
through both Hermes and ChatGPT before broadening plugin/capability
coverage. Everything in ARCHITECTURE.md is designed so that broadening
later is additive (new plugins), not architectural rework — so narrowing
now doesn't cost you later.

Suggested reverse-plan checkpoints (adjust once Hermes runtime and UI stack
are confirmed):

- Day 1–3: engine skeleton + Model Router + both providers answering a
  basic prompt.
- Day 4–6: Planner + Mission Manager state machine, Permission System gate.
- Day 7–9: Voice I/O in, wired to Intent Layer and Reporter.
- Day 10–11: Desktop UI shell talking to the engine over HTTP/WS.
- Day 12–13: End-to-end integration pass on the one golden path, fix what
  breaks. No new features in this window.

This isn't a commitment — it's a starting point to argue with once you've
seen how fast the first few days actually go.
