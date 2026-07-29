"""The Runtime Engine — Kalpavriksha's heartbeat (Mission Brief 024).

Mission Control is the nervous system; the Executives are the organs;
this is the loop that makes them beat without a human driving each cycle.

It performs no work and knows nothing about any specific Executive: it
observes Mission Control, routes assigned tasks to an Executive-agnostic
gateway, forwards verification results back, and repeats. See
RUNTIME_ENGINE_ARCHITECTURE.md §2 for why that boundary is drawn where it
is, and tests/test_runtime_architecture.py for its mechanical enforcement.
"""
