# ADR-0003: Everything is a plugin behind one contract

Status: Accepted (2026-07-23)

## Context
The founding principles call for "everything is a plugin" and "replaceable
modules." Without a firm boundary, it's easy for a fast-moving MVP to grow
special-cased branches in the Orchestrator for "the ChatGPT case," "the
calendar case," etc. — which is exactly the coupling this principle exists
to prevent.

## Decision
A single `Plugin` base contract (manifest + `invoke()`) in
`plugins/base.py` is implemented by every model provider, every capability
(filesystem, calendar, browser, ...), and every voice adapter. The
Orchestrator and Model Router only ever talk to plugins through this
interface and the Plugin Registry — never by importing a concrete plugin
class directly.

## Consequences
- Adding a capability is "write a plugin," never "add a branch in the
  Orchestrator." This is the mechanism that keeps the core engine small.
- The manifest must carry the risk tier (§4.4 in ARCHITECTURE.md) — the
  Permission System depends on every plugin declaring this honestly.
- Slightly more ceremony to add the first few plugins than a quick
  if/else would take. Worth it before the plugin count grows past ~5,
  which will happen fast once Mission Manager + Planner exist.
