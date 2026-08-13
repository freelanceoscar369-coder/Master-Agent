"""Desktop Intelligence — OBSERVE → UNDERSTAND.

The first bounded layer above `desktop/execution/` (raw UIA/Win32
primitives) and beside `desktop/perception/` (application/window-level
presence): a generic, evidence-based representation of what is currently
on screen — which application, which window, what elements are visible,
what they are (where determinable), what has focus, what can safely be
interacted with, and how confident this layer is about each of those.

Read-only, structurally: nothing in this package imports a keyboard or
mouse controller, or calls `write_text()`/`click()`/`press()`. See
`evidence.py`'s own module docstring for the full boundary, and
`tests/test_desktop_intelligence.py` for the AST-based guard that proves
it.

Public surface:

- `DesktopObservation` / `ElementObservation` / `ScreenshotEvidence` /
  `SemanticRole` / `WindowState` (`models.py`) — the data.
- `capture_evidence()` (`evidence.py`) — the primitive: one already-
  resolved window in, one `DesktopObservation` out.
- `DesktopIntelligence.observe_desktop()` (`observer.py`) — the stable,
  application-name-in, runtime-integrated API.
- `resolve_app_knowledge()` (`app_knowledge_bridge.py`) — the Part E join
  to `AppKnowledgeProfile`.
"""
from __future__ import annotations

from master_agent.desktop.intelligence.app_knowledge_bridge import resolve_app_knowledge
from master_agent.desktop.intelligence.classification import classify_element
from master_agent.desktop.intelligence.evidence import capture_evidence
from master_agent.desktop.intelligence.models import (
    ACTIONABLE_ROLES,
    DesktopObservation,
    ElementObservation,
    ScreenshotEvidence,
    SemanticRole,
    WindowState,
    unknown_observation,
)
from master_agent.desktop.intelligence.observer import DesktopIntelligence
from master_agent.desktop.intelligence.screenshot import (
    NullScreenshotBackend,
    ScreenshotBackend,
    ScreenshotUnavailable,
    Win32ScreenshotBackend,
    capture_screenshot,
    default_evidence_dir,
)

__all__ = [
    "ACTIONABLE_ROLES",
    "DesktopIntelligence",
    "DesktopObservation",
    "ElementObservation",
    "NullScreenshotBackend",
    "ScreenshotBackend",
    "ScreenshotEvidence",
    "ScreenshotUnavailable",
    "SemanticRole",
    "Win32ScreenshotBackend",
    "WindowState",
    "capture_evidence",
    "capture_screenshot",
    "classify_element",
    "default_evidence_dir",
    "resolve_app_knowledge",
    "unknown_observation",
]
