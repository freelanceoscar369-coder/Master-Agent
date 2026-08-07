"""Desktop Perception Layer (C27).

```
   Desktop Executive (C26)     ↓ acts
   Desktop Perception (C27)    ↓ observes
   Desktop Operator (future)   ↓ decides
```

Transforms the Desktop Executive from *"I can execute"* to *"I know
whether execution succeeded."* **Perception only — this package never
executes, clicks, types, launches, terminates, restarts, moves the
mouse, presses a key, or modifies a window.** Every fact it reports was
read by a component that already exists (C22, C25, C26) or by the two
new, narrowly-scoped, read-only probes this brief adds
(`document.readyState`, `SendMessageTimeoutW` for responsiveness) —
`tests/test_desktop_perception.py` enforces the boundary by AST, the same
discipline every C22–C26 suite already established.

`DesktopObserver.observe(now, ...)` is the entry point: pass the moment,
the applications to check, and (optionally) a `MachineInventory`, and it
returns an immutable `DesktopState` — applications, windows, browser,
clipboard status, focus, foreground, time, and an aggregate confidence —
while recording it into a bounded `DesktopObservationHistory` a caller can
ask `changes_since()`, `latest()`, and `stable()` of, and `failures()`
detects the brief's six failure kinds by comparing the two most recent
observations.
"""
from __future__ import annotations

from master_agent.desktop.perception.browser import (
    BrowserObserver,
    BrowserPerception,
    BrowserUnavailable,
)
from master_agent.desktop.perception.clipboard import ClipboardObserver, ClipboardStatus
from master_agent.desktop.perception.engine import DesktopObserver, ObservationEngine
from master_agent.desktop.perception.evidence import (
    Confidence,
    InvalidObservation,
    Observation,
    unknown_observation,
)
from master_agent.desktop.perception.failures import (
    FailureDetector,
    FailureKind,
    FailureObservation,
)
from master_agent.desktop.perception.history import SECTIONS, DesktopObservationHistory
from master_agent.desktop.perception.readiness import ReadinessState, UIReadyDetector
from master_agent.desktop.perception.state import (
    ApplicationState,
    DesktopState,
    aggregate_confidence,
)
from master_agent.desktop.perception.win32_probe import (
    ResponsivenessBackend,
    ResponsivenessUnavailable,
)
from master_agent.desktop.perception.windows import WindowObservation, WindowObserver

__all__ = [
    "SECTIONS",
    "ApplicationState",
    "BrowserObserver",
    "BrowserPerception",
    "BrowserUnavailable",
    "ClipboardObserver",
    "ClipboardStatus",
    "Confidence",
    "DesktopObservationHistory",
    "DesktopObserver",
    "DesktopState",
    "FailureDetector",
    "FailureKind",
    "FailureObservation",
    "InvalidObservation",
    "Observation",
    "ObservationEngine",
    "ReadinessState",
    "ResponsivenessBackend",
    "ResponsivenessUnavailable",
    "UIReadyDetector",
    "WindowObservation",
    "WindowObserver",
    "aggregate_confidence",
    "unknown_observation",
]
