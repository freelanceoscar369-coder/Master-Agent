"""C30 · The founder dashboard — six existing projections, one dict.

```
   C29 FounderIdentity ─┐
   C29 FounderSession ──┤
   C24 BootReport ──────┤
   C22 environment ─────┼──►  founder_dashboard()  ──►  one JSON dict
   C19/C20 presence ────┤          (composes)
   C21 conversation ────┤
   C25–C28 desktop ─────┘
```

**Every section is some other component's own `as_dict()`, unchanged.**
This module has no branch that reshapes a value, no key it renames, and no
number it computes. It is the C23 discipline applied one layer up:

> *"Re-keying it here — `summary` → `environmentSummary` … would create
> the one thing C18 named as the reason it uses the Kernel API's own
> parameter names: there is no translation table to drift."*

## Which dashboard this is, and which it is not

`master_agent/dashboard/` (MB026, MB029) is a **different surface at a
different altitude**: it renders the Runtime Engine, Mission Control,
approvals, the audit spine, persistence and the broker, and it is fed by
`DashboardSources`, which reads those subsystems' own contracts. Wiring
*that* dashboard into this assembly would reach straight into Mission
Control — which this brief forbids in as many words (*"No Mission OS"*),
and which C29 already forbids Somesh from touching at all.

So the dashboard C30 assembles is the founder-facing one: the state a
Founder Surface (C21) renders through the Presence Layer (C20), which is
HyperAgent's TypeScript and stays out of this repository exactly as C24's
own `render_founder_surface` step already records. What this module
produces is the **data** that surface consumes, in one round trip, for the
same reason C23's `snapshot()` exists: a surface that has to make six
calls to draw one screen will eventually draw five of them from one moment
and one from another.

## Purity

No clock, no I/O, no randomness, no state. `moment` arrives as a
parameter. Two calls against the same components return equal
dictionaries, which is what lets a test assert the whole dashboard
byte-for-byte.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from master_agent.founder_edition.desktop_layer import DesktopLayer
from master_agent.founder_identity import FounderIdentity, FounderSession
from master_agent.founder_runtime import FounderRuntime

#: The sections a founder dashboard carries, in fixed order. Held as data
#: so a test can assert the shape never silently grows or loses one.
DASHBOARD_SECTIONS: tuple[str, ...] = (
    "identity",
    "session",
    "boot",
    "environment",
    "presence",
    "conversation",
    "desktop",
    "sources",
)


def founder_dashboard(
    *,
    runtime: FounderRuntime,
    identity: FounderIdentity,
    session: FounderSession,
    boot: dict[str, Any],
    desktop: DesktopLayer | None,
    moment: datetime,
) -> dict[str, Any]:
    """Every section a founder surface draws, composed from what already
    exists. One line per section, and no line between them.

    `desktop` is optional because a boot whose desktop layer could not be
    wired must still produce a readable dashboard — C24's own rule that
    *"one step's honest absence does not take down the whole
    application"*, applied to the layer C30 adds.
    """
    if not isinstance(runtime, FounderRuntime):
        raise TypeError("runtime must be the FounderRuntime this boot connected")
    if not isinstance(identity, FounderIdentity):
        raise TypeError("identity must be the FounderIdentity this boot built")
    if not isinstance(session, FounderSession):
        raise TypeError("session must be the FounderSession this boot built")
    if desktop is not None and not isinstance(desktop, DesktopLayer):
        raise TypeError("desktop must be the DesktopLayer this boot built, or None")
    if moment.tzinfo is None:
        raise ValueError("moment must be timezone-aware")

    return {
        "identity": identity.as_dict(),
        "session": session.as_dict(),
        "boot": boot,
        "environment": runtime.environment(),
        "presence": runtime.presence(),
        "conversation": runtime.conversation(),
        "desktop": desktop.readiness(moment) if desktop is not None else None,
        "sources": [source.as_dict() for source in runtime.sources()],
    }
