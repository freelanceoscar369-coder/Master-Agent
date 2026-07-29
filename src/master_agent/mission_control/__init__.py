"""Mission Control — the runtime coordination layer (Mission Brief 023).

Registers who can do what, turns objectives into ordered capability calls,
receives every event through one schema, preserves an immutable audit
stream, tracks what the system still needs to learn, and exposes one
honest snapshot of state to the founder.

Mission Control never performs work. It holds no Environment access, no
model calls, no filesystem calls — it coordinates, and records what
happened. See MISSION_CONTROL_ARCHITECTURE.md §1, and
tests/test_mission_control_architecture.py for the mechanical enforcement
of that boundary.
"""
