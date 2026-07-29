"""The Founder Dashboard — the first operational window into a living
autonomous system (Mission Brief 026).

Read-only, by construction. It consumes published contracts, builds a
frozen read model, and renders it. It never dispatches work, never
executes a capability, never mutates Runtime or Mission Control state, and
never touches a file.

See FOUNDER_DASHBOARD_ARCHITECTURE.md for the contract survey and
ADR-0016 for the data contract. tests/test_dashboard_architecture.py
enforces the boundaries mechanically rather than trusting this docstring.
"""
