"""Browser Worker's Action family — see BROWSER_WORKER_ARCHITECTURE.md §6.
Each module is one atomic Playwright-backed operation, following the exact
Action contract (executor/action.py) every filesystem Action already
implements. Nothing here is registered automatically; browser_plugin.py
does that declaratively, the same way filesystem_plugin.py does for its
own Actions.
"""
