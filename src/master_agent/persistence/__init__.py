"""Persistence — Kalpavriksha's operational memory (Mission Brief 025).

Makes Mission Control and the Runtime *continuous*: state survives the
process exiting, and execution resumes where it stopped.

Persistence is a service. It never executes missions, never dispatches an
Executive, and holds no gateway — see PERSISTENCE_ARCHITECTURE.md §2 and
tests/test_persistence_architecture.py, which enforces that mechanically
rather than trusting this docstring.
"""
