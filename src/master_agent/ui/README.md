# Desktop UI

The UI is deliberately a separate process from the engine, talking over a
local HTTP/WS API — not a Python package imported by the engine. See
ARCHITECTURE.md §4.9 for the reasoning and the pywebview recommendation.

Nothing lives in this package yet: the API server (FastAPI, exposing
Mission Manager state + a way to submit Intents + an approval endpoint for
the Permission System) is the next piece of work, once Mission Manager and
Planner have something real to expose.
