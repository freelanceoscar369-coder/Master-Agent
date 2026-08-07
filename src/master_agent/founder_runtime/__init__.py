"""Founder Runtime Wiring — the completed Sprint 1 components, connected.

```
   Environment Intelligence (C22)
              ↓
       Presence Layer (C20)          ← fed, never re-implemented
              ↓
     Conversation Runtime            ← projected, never authored
              ↓
      Founder Surface (C21)
```

**Wiring only.** No new architecture, no new intelligence, no new UI. Every
value that leaves this package was produced by a component that already
existed and is carried in that component's own shape.

The one thing worth knowing before reading further: **this package does not
produce a `PresenceSnapshot`.** That type is derived by the Presence Layer
from observations, and a second implementation of that derivation is exactly
the duplication this component was told not to build. What is produced here
is the **feed** — the observations C20 folds in — so the Presence Layer that
already exists starts describing a real system instead of an empty one.

Consumes: `environment_intelligence` (C22) · `vigilance` (C19) ·
`memory.conversation`. Imports no frozen package.
"""
from __future__ import annotations

from master_agent.founder_runtime.presence_feed import (
    NOTHING_WATCHED,
    PRESENCE_OBSERVATION_TYPES,
    PresenceFeed,
    presence_feed,
)
from master_agent.founder_runtime.projection import (
    CONTRACT_SECTIONS,
    PROJECTED_ROLES,
    conversation_projection,
    environment_projection,
)
from master_agent.founder_runtime.wiring import (
    ARGUMENTS,
    AUTHORITY_UNREACHABLE,
    OPERATION,
    FounderOperation,
    FounderRuntime,
    InvalidFounderEnvelope,
    ResultKind,
    Source,
)

__all__ = [
    "ARGUMENTS",
    "AUTHORITY_UNREACHABLE",
    "CONTRACT_SECTIONS",
    "NOTHING_WATCHED",
    "OPERATION",
    "PRESENCE_OBSERVATION_TYPES",
    "PROJECTED_ROLES",
    "FounderOperation",
    "FounderRuntime",
    "InvalidFounderEnvelope",
    "PresenceFeed",
    "ResultKind",
    "Source",
    "conversation_projection",
    "environment_projection",
    "presence_feed",
]
