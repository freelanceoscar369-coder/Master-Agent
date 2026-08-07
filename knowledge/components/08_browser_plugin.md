# Component: Browser Plugin

## Purpose
Playwright-wrapped Browser Worker with nine atomic Actions; registers on LocalExecutor; delegates session management to BrowserSessionManager.

## Scope
src/master_agent/plugins/browser_*.py
src/master_agent/executor/actions/browser/
src/master_agent/environment/browser_session.py

## Dependencies
- LocalExecutor (executor/)
- BrowserSessionManager (environment/browser_session.py)
- BrowserVerifier (verification/)
- MISSION_BRIEF_022.md
- BROWSER_WORKER_ARCHITECTURE.md

## Last Updated
2026-07-31

## References
- MISSION_BRIEF_022.md
- BROWSER_WORKER_ARCHITECTURE.md

## Status
Template