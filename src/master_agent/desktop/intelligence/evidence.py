"""Desktop Intelligence · Part B — `capture_evidence()`, the read-only
observation primitive.

**How this relates to the rest of the perception stack.**
`desktop.perception.engine.ObservationEngine` (C27) answers "is this
application running, what window does it have, is it ready" —
application/window-level presence. This module answers one level deeper:
"given one already-resolved window, what elements are on it, what are
they, what has focus, what can be acted on" — element-level structure.
Neither replaces the other; a future caller composes both the same way
`ObservationEngine` already composes `WindowObserver`/`BrowserObserver`/
`ClipboardObserver`.

**Strictly read-only — enforced structurally, not by convention.** This
module never imports `KeyboardController`, `MouseController`, or any
`write_text`/`click`/`press` method. Every `UiaAutomationBridge` call this
module makes is one of: `snapshot_elements()`, `window_bounds()`,
`find_composer()`, `find_main_content()`, `find_new_content()`,
`get_focused_element_in_window()` — all read-only by their own contract.
`tests/test_desktop_intelligence.py` carries an AST-based structural guard
for exactly this, the same discipline `app_knowledge/acquisition.py` and
`desktop/perception/*` already hold their own suites to.

**Composes, does not replace.** No new UIA traversal mechanism is
introduced here — `snapshot_elements()` (added to `uia_control.py` this
same mission, for exactly this caller) is the one new read primitive;
everything else this module calls already existed before this mission.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from master_agent.app_knowledge.profile import AppKnowledgeProfile, KnowledgeType
from master_agent.desktop.execution.backends import WindowInfo
from master_agent.desktop.execution.uia_control import (
    UiaAutomationBridge,
    UiaTargetNotFound,
    UiaUnavailable,
)
from master_agent.desktop.intelligence.classification import classify_element
from master_agent.desktop.intelligence.models import (
    DesktopObservation,
    ElementObservation,
    ScreenshotEvidence,
    SemanticRole,
    WindowState,
    unknown_observation,
)
from master_agent.desktop.intelligence.screenshot import (
    ScreenshotBackend,
    capture_screenshot,
    default_evidence_dir,
)

SOURCE = "desktop.intelligence.evidence.capture_evidence()"

#: Top-level confidence combination — deliberately smaller than
#: `environment_intelligence.evidence.Confidence.weakest()` (this layer
#: only ever combines two facts: "is this really the window/app we think
#: it is" and "was a window found at all") but the same
#: never-stronger-than-the-weakest-input rule.
_RANK: dict[KnowledgeType, int] = {
    KnowledgeType.OBSERVED: 0,
    KnowledgeType.DOCUMENTED: 0,
    KnowledgeType.INFERRED: 1,
    KnowledgeType.UNKNOWN: 2,
}


def _weakest(*types: KnowledgeType) -> KnowledgeType:
    return max(types, key=lambda t: _RANK[t])


def _window_state(window: WindowInfo) -> WindowState:
    if window.is_maximized:
        return WindowState.MAXIMIZED
    if window.is_minimized:
        return WindowState.MINIMIZED
    return WindowState.NORMAL


def _bounds_of(element: Any) -> tuple[int, int, int, int] | None:
    """Best-effort: the real UIA-reported bounding rectangle of one
    already-resolved element, used only to correlate it against
    `snapshot_elements()`'s own results (the same bounding-rect-as-key
    technique `uia_control._text_region_candidates()` already documents
    and relies on) — never to act on it."""
    try:
        rect = element.CurrentBoundingRectangle
        return (rect.left, rect.top, rect.right, rect.bottom)
    except Exception:  # noqa: BLE001 — an unreadable rect just means "no match", not a failure
        return None


def capture_evidence(
    *,
    uia: UiaAutomationBridge,
    window: WindowInfo,
    application: str,
    application_confidence: KnowledgeType,
    application_reason: str,
    app_knowledge: AppKnowledgeProfile | None = None,
    baseline: dict[tuple[int, int, int, int], str] | None = None,
    screenshot_backend: ScreenshotBackend | None = None,
    screenshot_dir: Path | None = None,
    now: datetime,
) -> DesktopObservation:
    """The Part B primitive: one already-resolved, real window in, one
    `DesktopObservation` out. Never types, clicks, submits, renames, or
    creates anything — every call this function makes is read-only (see
    module docstring). Never raises for an ordinary observation failure
    (an unreadable element, an unresolvable composer/content heuristic, a
    failed screenshot) — each degrades the relevant field's own
    confidence/reason rather than aborting the whole call; only a truly
    unusable `window` (no bounding rectangle at all) falls back to
    `unknown_observation()`.
    """
    try:
        window_bounds = uia.window_bounds(window.handle)
    except (UiaUnavailable, UiaTargetNotFound) as exc:
        return unknown_observation(
            reason=f"window {window.handle} has no readable bounding rectangle: {exc}",
            source=SOURCE, timestamp=now, application=application,
        )

    try:
        snapshots = uia.snapshot_elements(window.handle)
    except (UiaUnavailable, UiaTargetNotFound):
        snapshots = ()

    composer_bounds = _resolve_bounds(lambda: uia.find_composer(window.handle))
    main_content_bounds = _resolve_bounds(lambda: uia.find_main_content(window.handle))
    response_bounds = (
        _resolve_bounds(lambda: uia.find_new_content(window.handle, baseline))
        if baseline is not None else None
    )

    focused_bounds: tuple[int, int, int, int] | None = None
    try:
        focused_raw = uia.get_focused_element_in_window(window.handle)
        focused_bounds = _bounds_of(focused_raw)
    except (UiaUnavailable, UiaTargetNotFound):
        focused_bounds = None

    elements: list[ElementObservation] = []
    for snapshot in snapshots:
        role, role_confidence, role_reason, role_source = classify_element(
            snapshot,
            window_bounds=window_bounds,
            is_composer_match=(composer_bounds is not None and snapshot.bounds == composer_bounds),
            is_response_match=(response_bounds is not None and snapshot.bounds == response_bounds),
            is_main_content_match=(main_content_bounds is not None and snapshot.bounds == main_content_bounds),
        )
        elements.append(
            ElementObservation(
                name=snapshot.name, automation_id=snapshot.automation_id,
                control_type=snapshot.control_type,
                role=role, role_confidence=role_confidence, role_reason=role_reason,
                is_enabled=snapshot.is_enabled, is_focusable=snapshot.is_focusable,
                is_focused=(focused_bounds is not None and snapshot.bounds == focused_bounds),
                is_offscreen=snapshot.is_offscreen, is_selected=snapshot.is_selected,
                bounds=snapshot.bounds, text=snapshot.text,
                source=role_source, timestamp=now,
            )
        )

    focused_element = next((e for e in elements if e.is_focused), None)
    selected_tab = next(
        (e for e in elements if e.role is SemanticRole.TAB and e.is_selected is True), None,
    )

    screenshot: ScreenshotEvidence | None = None
    if screenshot_backend is not None:
        screenshot = capture_screenshot(
            screenshot_backend,
            window_handle=window.handle, application=application,
            bounds=window_bounds, dest_dir=screenshot_dir or default_evidence_dir(),
            now=now,
        )

    overall_confidence = _weakest(application_confidence, KnowledgeType.OBSERVED)

    return DesktopObservation(
        application=application, application_confidence=application_confidence,
        application_reason=application_reason,
        window_handle=window.handle, window_title=window.title,
        window_state=_window_state(window),
        elements=tuple(elements), focused_element=focused_element, selected_tab=selected_tab,
        screenshot=screenshot, app_knowledge=app_knowledge,
        confidence=overall_confidence,
        reason=(
            f"window {window.handle!r} ({window.title!r}) observed; "
            f"{len(elements)} element(s) enumerated via UiaAutomationBridge.snapshot_elements()"
        ),
        source=SOURCE, timestamp=now,
    )


def _resolve_bounds(finder) -> tuple[int, int, int, int] | None:
    """Best-effort: call one of the existing `find_*()` heuristics and
    return the resolved element's own bounds, or `None` on any of its
    documented failure modes (`UiaUnavailable`/`UiaTargetNotFound`, or a
    genuine "nothing new" `None` from `find_new_content()`) — never
    raised past this point, since none of these are failures of
    *observation*, only "this particular heuristic found nothing this
    time"."""
    try:
        element = finder()
    except (UiaUnavailable, UiaTargetNotFound):
        return None
    if element is None:
        return None
    return _bounds_of(element)
