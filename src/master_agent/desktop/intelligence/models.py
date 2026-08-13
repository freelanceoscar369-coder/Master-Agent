"""Desktop Intelligence · `DesktopObservation` — a generic, evidence-based
snapshot of what is currently on screen: which application, which window,
what elements are visible, what they are (where determinable), what has
focus, what can safely be interacted with, and how confident this layer is
about each of those.

**Confidence vocabulary — reused, not reinvented.** Every fact in this
module is one `KnowledgeType` (`app_knowledge.profile`):

- `DOCUMENTED` — this fact came from an `AppKnowledgeProfile`, not from
  the live UIA tree this call actually read. Carried through unchanged
  from the profile, never collapsed into `OBSERVED` — a documented claim
  and a live reading are not the same kind of evidence, and this layer
  never pretends otherwise (the mission's own "preserve the distinction"
  requirement).
- `OBSERVED` — a real, hard UIA fact this call read directly (a
  `ControlType`, an `IsEnabled`/`IsOffscreen` property, a resolved
  element's own bounding rectangle).
- `INFERRED` — a generic, evidence-based heuristic matched (the same
  heuristics `uia_control.py` already uses for `find_composer()`/
  `find_main_content()`/`find_new_content()`), not a hard property read.
- `UNKNOWN` — nothing above cleared the bar. **Never fabricated as a
  guess presented as a finding** — the whole reason this module exists
  is to say `UNKNOWN` honestly instead.

This is one level below `desktop.perception.state.DesktopState` (which
observes *application/window/browser/clipboard presence*, never an
element) and composes with it rather than replacing it — see this
package's own `README`-equivalent, `evidence.py`'s module docstring, for
how the two relate.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from master_agent.app_knowledge.profile import AppKnowledgeProfile, KnowledgeType


class SemanticRole(str, Enum):
    """The mission's own closed vocabulary. `UNKNOWN` is the honest
    default — classification never guesses one of the others without a
    named, evidence-based reason (see `classification.py`)."""

    WINDOW = "window"
    TAB = "tab"
    BUTTON = "button"
    MENU = "menu"
    COMPOSER = "composer"
    TEXT_REGION = "text_region"
    RESPONSE_REGION = "response_region"
    SIDEBAR = "sidebar"
    DIALOG = "dialog"
    INPUT = "input"
    UNKNOWN = "unknown"


#: Roles a caller could plausibly act on directly — the vocabulary
#: `DesktopObservation.actionable_controls` filters against. `TEXT_REGION`/
#: `RESPONSE_REGION`/`SIDEBAR`/`WINDOW`/`DIALOG`/`UNKNOWN` are deliberately
#: excluded: reading them is safe, but this layer makes no claim they are
#: meant to be clicked or typed into.
ACTIONABLE_ROLES: frozenset[SemanticRole] = frozenset(
    {SemanticRole.BUTTON, SemanticRole.COMPOSER, SemanticRole.INPUT, SemanticRole.TAB, SemanticRole.MENU}
)


class WindowState(str, Enum):
    """The window's own real, Win32-reported presentation state — always
    `OBSERVED`-confidence when a window was found at all (it comes
    straight from `WindowInfo`, not a derivation), so this type carries no
    separate confidence wrapper of its own."""

    MAXIMIZED = "maximized"
    MINIMIZED = "minimized"
    NORMAL = "normal"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ElementObservation:
    """One visible-or-not UI element, its real UIA-reported facts, and
    this layer's own best classification of what it is — never
    conflating the two: `is_enabled`/`is_offscreen`/`bounds`/`text` are
    hard reads (`OBSERVED`, structurally, by construction — see
    `evidence.py`); `role`/`role_confidence`/`role_reason` are this
    layer's own generic, evidence-based judgment, which may honestly be
    `UNKNOWN`."""

    name: str
    automation_id: str
    control_type: int
    role: SemanticRole
    role_confidence: KnowledgeType
    role_reason: str
    is_enabled: bool
    is_focusable: bool
    is_focused: bool
    is_offscreen: bool
    is_selected: bool | None
    bounds: tuple[int, int, int, int]
    text: str | None
    source: str
    timestamp: datetime

    @property
    def is_actionable(self) -> bool:
        """Enabled, on-screen, and a role this layer's own closed
        vocabulary considers something a caller could plausibly act on —
        computed, never stored twice, the same "one source of truth"
        discipline `WindowObservation.is_foreground()` already applies."""
        return self.is_enabled and not self.is_offscreen and self.role in ACTIONABLE_ROLES

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "automation_id": self.automation_id,
            "control_type": self.control_type,
            "role": self.role.value, "role_confidence": self.role_confidence.value,
            "role_reason": self.role_reason,
            "is_enabled": self.is_enabled, "is_focusable": self.is_focusable,
            "is_focused": self.is_focused, "is_offscreen": self.is_offscreen,
            "is_selected": self.is_selected, "is_actionable": self.is_actionable,
            "bounds": list(self.bounds), "text": self.text,
            "source": self.source, "timestamp": self.timestamp.isoformat(),
        }


@dataclass(frozen=True)
class ScreenshotEvidence:
    """One screenshot attempt's outcome — always produced, even on
    failure (`captured=False`), so a caller never has to distinguish "no
    screenshot was attempted" from "a screenshot was attempted and safely
    failed" by checking for `None` in two different places. See
    `screenshot.py` for the capture mechanism itself."""

    captured: bool
    path: str | None
    width: int | None
    height: int | None
    window_handle: int
    application: str
    reason: str
    source: str
    timestamp: datetime

    def as_dict(self) -> dict[str, Any]:
        return {
            "captured": self.captured, "path": self.path,
            "width": self.width, "height": self.height,
            "window_handle": self.window_handle, "application": self.application,
            "reason": self.reason, "source": self.source,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass(frozen=True)
class DesktopObservation:
    """One structured, read-only snapshot of the current desktop —
    Desktop Intelligence's own `Observe` output. Always constructed, even
    when the target application or window could not be found — an
    unobservable desktop is itself a fact this layer reports honestly
    (`confidence=UNKNOWN`, `window_handle=0`, `elements=()`), never an
    exception a caller has to catch to learn nothing happened.

    Immutable, like every other evidence-carrying value in this codebase
    (`Observation`, `Fact`, `Inference`) — a snapshot a consumer could
    edit is not a snapshot."""

    application: str
    application_confidence: KnowledgeType
    application_reason: str

    window_handle: int
    window_title: str
    window_state: WindowState

    elements: tuple[ElementObservation, ...]
    focused_element: ElementObservation | None
    selected_tab: ElementObservation | None

    screenshot: ScreenshotEvidence | None
    app_knowledge: AppKnowledgeProfile | None

    confidence: KnowledgeType
    reason: str
    source: str
    timestamp: datetime

    @property
    def composer_candidates(self) -> tuple[ElementObservation, ...]:
        """Every focusable, text-bearing, on-screen element — not just
        the single element this layer's own classification elevated to
        `SemanticRole.COMPOSER` (`find_composer()`'s own "smallest,
        bottom-anchored" pick). A future Plan layer choosing among real
        alternatives needs the *candidates*, not only the winner."""
        return tuple(
            e for e in self.elements
            if e.is_focusable and not e.is_offscreen and (e.text is not None or e.role == SemanticRole.COMPOSER)
        )

    @property
    def actionable_controls(self) -> tuple[ElementObservation, ...]:
        return tuple(e for e in self.elements if e.is_actionable)

    def elements_by_role(self, role: SemanticRole) -> tuple[ElementObservation, ...]:
        return tuple(e for e in self.elements if e.role is role)

    def as_dict(self) -> dict[str, Any]:
        return {
            "application": self.application,
            "application_confidence": self.application_confidence.value,
            "application_reason": self.application_reason,
            "window_handle": self.window_handle, "window_title": self.window_title,
            "window_state": self.window_state.value,
            "elements": [e.as_dict() for e in self.elements],
            "focused_element": self.focused_element.as_dict() if self.focused_element else None,
            "selected_tab": self.selected_tab.as_dict() if self.selected_tab else None,
            "screenshot": self.screenshot.as_dict() if self.screenshot else None,
            "app_knowledge_provider_id": self.app_knowledge.provider_id if self.app_knowledge else None,
            "confidence": self.confidence.value, "reason": self.reason,
            "source": self.source, "timestamp": self.timestamp.isoformat(),
        }


def unknown_observation(reason: str, source: str, timestamp: datetime, *, application: str = "") -> DesktopObservation:
    """The honest answer when nothing could be observed at all (no
    window, no application resolved) — the same role
    `perception.evidence.unknown_observation()` plays for one fact,
    applied here to a whole snapshot."""
    return DesktopObservation(
        application=application, application_confidence=KnowledgeType.UNKNOWN,
        application_reason=reason,
        window_handle=0, window_title="", window_state=WindowState.UNKNOWN,
        elements=(), focused_element=None, selected_tab=None,
        screenshot=None, app_knowledge=None,
        confidence=KnowledgeType.UNKNOWN, reason=reason, source=source, timestamp=timestamp,
    )
