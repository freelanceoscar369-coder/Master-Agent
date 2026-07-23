# Architecture Principles

Status: Frozen (2026-07-23) — Miracle 003.5, Foundation Freeze

`ARCHITECTURE.md` is the concrete system design — module boundaries,
data flow, the plugin contract, as they exist today. This document is
one layer up: the reasoning that produced that shape, stated generally
enough to survive `ARCHITECTURE.md` itself being revised. When a future
change to the system design is being considered, check it against this
document first — if it's compatible with these principles, updating
`ARCHITECTURE.md` is just describing the new state. If it isn't, that's
worth surfacing explicitly (an ADR, at minimum) before writing code.

## Why the architecture exists

Master Agent's architecture is not "how we happened to build it" — it's
a direct answer to a specific constraint from `VISION.md`: the system
has to remain fully extensible by a single founder (today) and,
eventually, many independent contributors (including AI agents), without
anyone needing to understand the whole system to safely change one part
of it. Every module boundary in `ARCHITECTURE.md` exists because the
alternative — one part of the system needing to understand another
part's internals to work correctly — doesn't scale past one person's
working memory, and this project is explicitly betting on outgrowing
that.

The four Miracles shipped so far are the evidence this bet is holding:
Miracle 002 added an entire new execution layer (`LocalExecutor` +
`Action`) underneath `FilesystemPlugin` without the Orchestrator,
PermissionSystem, or any existing test changing. Miracle 003 added
composite actions without the Plugin or Orchestrator contracts changing.
Miracle 003.1 connected a new kind of mission to real conversation
without the Executor, PermissionSystem, or composite-relay logic
changing. Each time, a real capability grew *underneath* a stable
contract instead of requiring the contract itself to be renegotiated.
That pattern repeating four times in a row is the actual argument for
this architecture, not the diagram in `ARCHITECTURE.md` §3 by itself.

## Module boundaries

Each module in `ARCHITECTURE.md` §4 is a separate package that talks to
its neighbors only through a narrow, explicit interface — never by
reaching into another module's internal state. The test for whether a
boundary is drawn correctly: **can this module be deleted and replaced
by a different implementation of the same interface, by someone who has
never read its source code?** If the answer requires reading the
replaced module's internals to write the replacement correctly, the
boundary is leaking.

This is why `Mission`, `Orchestrator`, and `PermissionSystem` have not
changed in four Miracles of real feature work underneath them — every
new capability was designed to fit through the interfaces those modules
already exposed (`Step.capability`, `Plugin.invoke()`,
`PermissionSystem.check()`/`grant()`), not to require those interfaces
to grow new cases.

## Dependency direction

Dependencies point inward, toward the core engine, never outward from it
toward a specific capability:

```
Conversation / UI  →  Intent Layer  →  Planner  →  Mission Manager
                                                        ↓
                                              Permission System (gate)
                                                        ↓
                                                  Orchestrator
                                                        ↓
                                                Plugin Runtime
                                             (plugins, incl. Executor
                                              + Actions underneath it)
```

The Orchestrator depends on the Plugin contract; no Plugin depends on
the Orchestrator's internals. `LocalExecutor` depends on the
`PermissionSystem`'s public `check()`/`grant()` surface; the
`PermissionSystem` has no idea `LocalExecutor` exists. This is what
makes it safe for a new Action, a new Plugin, or even a new
`ModelProvider` to be written by someone — or something — that has never
read the Orchestrator's source, only its contract. **A change to a
"lower" module (closer to conversation/UI) should never require a change
to a "higher" one (closer to the engine core) to keep working.** If it
does, the dependency arrow was drawn backwards somewhere.

## Extension strategy

The system grows by **adding new implementations of existing contracts**,
not by adding new contracts or widening old ones. Concretely, in order
of how a new capability should usually be built:

1. **First choice: a new `Action`**, registered on the existing
   `LocalExecutor`, exposed through an existing or new `Plugin`. This is
   the cheapest, most common extension — `write_file` (Miracle 003) is
   the reference example.
2. **Next: a composite `Action`**, when a capability is naturally a
   sequence of existing primitives. `WorkspaceBootstrapAction` (Miracle
   003) is the reference example — and critically, it required *no*
   change to the `Action` contract itself to exist.
3. **Rarely: a new module boundary**, when a genuinely new category of
   thing needs to exist (Voice I/O, Memory — both already scaffolded in
   `ARCHITECTURE.md` §4 as stubs, precisely so their eventual real
   implementation has a contract to fill rather than a decision to make
   about where they'd live).
4. **Almost never: a change to an existing contract's shape** (`Plugin`,
   `Action`, `Step`, `PermissionGrant`). Every one of these has stayed
   fixed across four Miracles of real functional growth. A change here
   should be treated as expensive and rare by default — it invalidates
   the "replaceable without reading internals" property for every
   existing implementation of that contract, not just the one being
   modified.

## Plugin philosophy

"Everything is a plugin" (ADR-0003) is not primarily about code reuse —
it's about making the Orchestrator's job possible to state simply:
resolve a capability name to a plugin, check permission, invoke, capture
the result. That statement has been true and unchanged since Miracle
001. A plugin's job, symmetrically, is to expose a manifest (what it
does, at what risk tier) and an `invoke()` — nothing about how it does
that work is the Orchestrator's concern, which is what let
`FilesystemPlugin` grow an entire Executor + Action layer underneath
itself (Miracle 002) without the plugin contract noticing.

The same philosophy repeats one layer down: `LocalExecutor` doesn't care
whether an `Action` is a five-line primitive or a composite orchestrating
five other Actions (Miracle 003) — it only cares that the `Action`
contract's six methods/attributes are implemented. **A contract's
consumer should never need to know which concrete implementation it's
talking to.** This is the property to protect above almost any other
architectural convenience.

## Future scalability

Two different kinds of "scale" apply to this project, and they're solved
differently, on purpose:

- **Scaling the number of capabilities** (more plugins, more actions,
  more model providers) is already solved by the extension strategy
  above — it's a registration problem, not a redesign problem. Nothing
  about adding the 50th Action should look different from adding the
  3rd.
- **Scaling from one founder to many users** is deliberately *not*
  solved yet, and that's correct for now (`PRODUCT_PRINCIPLES.md`'s
  "build for one founder first, scale for millions later"). The
  boundaries are drawn so that scaling later — multi-user Memory, a
  plugin marketplace, cloud sync — arrives as new modules behind
  existing contracts (Local Memory already has a defined interface in
  `ARCHITECTURE.md` §4.8, unimplemented), not as a rewrite of
  `Orchestrator`, `PermissionSystem`, or the `Plugin`/`Action` contracts.
  The test, again: when that work happens, will it require touching
  those four things? If the module boundaries above are being honored,
  the answer stays no.

## How to use this document

When designing a new Miracle: identify which of the four extension tiers
above it fits. If it's tier 4 (a contract change), that alone is reason
to slow down and write an ADR before code — not because contract changes
are forbidden, but because everything built on top of the old contract
shape is about to need re-verification, and that cost should be paid
deliberately, not discovered after the fact.
