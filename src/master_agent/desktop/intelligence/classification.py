"""Desktop Intelligence · semantic classification — turning one
`UiaElementSnapshot` into a `SemanticRole` judgment, evidence-based only.

**Two tiers of evidence, in priority order:**

1. **Structural matches against existing, proven heuristics.** An
   element that `UiaAutomationBridge.find_composer()` / `find_main_content()`
   / `find_new_content()` would themselves resolve is classified using
   *their* finding, not a second, independent guess — this module never
   re-derives composer/response geometry from scratch, per the mission's
   own "reuse existing primitives, no parallel automation framework" rule.
2. **Real UIA `ControlType` facts.** Buttons, menus, tabs, edits, and
   nested/modal windows carry a hard, Windows-reported `ControlType` —
   read directly, `OBSERVED` confidence, no inference involved.

Only when neither tier matches does this module fall back to a small set
of generic, geometry-based heuristics (sidebar detection) — always
`INFERRED`, always with a stated reason. **Nothing here branches on which
application is being observed.** Every signal used is either a UIA
standard (`ControlType`, pattern availability) or a generic geometric
shape (tall-and-narrow-and-edge-anchored) — the same discipline
`uia_control.py`'s own composer/content heuristics already hold to.
`AppKnowledgeProfile` is *not* consulted here for role classification
(see `app_knowledge_bridge.py` and `evidence.py` for where it *is* used) —
mixing a documented fact into a live structural judgment would blur
exactly the distinction Part E's own "preserve documented vs. observed vs.
inferred vs. unknown" requirement asks this layer to keep clean.
"""
from __future__ import annotations

from master_agent.app_knowledge.profile import KnowledgeType
from master_agent.desktop.execution.uia_control import (
    CONTROL_TYPE_BUTTON,
    CONTROL_TYPE_COMBO_BOX,
    CONTROL_TYPE_EDIT,
    CONTROL_TYPE_MENU,
    CONTROL_TYPE_MENU_BAR,
    CONTROL_TYPE_MENU_ITEM,
    CONTROL_TYPE_SPLIT_BUTTON,
    CONTROL_TYPE_TAB,
    CONTROL_TYPE_TAB_ITEM,
    CONTROL_TYPE_WINDOW,
    UiaElementSnapshot,
)
from master_agent.desktop.intelligence.models import SemanticRole

_BUTTON_TYPES = frozenset({CONTROL_TYPE_BUTTON, CONTROL_TYPE_SPLIT_BUTTON})
_MENU_TYPES = frozenset({CONTROL_TYPE_MENU, CONTROL_TYPE_MENU_BAR, CONTROL_TYPE_MENU_ITEM})
_TAB_TYPES = frozenset({CONTROL_TYPE_TAB, CONTROL_TYPE_TAB_ITEM})
_INPUT_TYPES = frozenset({CONTROL_TYPE_EDIT, CONTROL_TYPE_COMBO_BOX})

#: Generic sidebar geometry — a tall, narrow, window-edge-anchored region.
#: The same "structural inference over real geometry, never an invented
#: coordinate" discipline `uia_control.py`'s own `_COMPOSER_MAX_HEIGHT_FRACTION`
#: applies, tuned conservatively (a real navigation rail is reliably both
#: tall and narrow; a merely tallish content pane rarely is both at once).
_SIDEBAR_MIN_HEIGHT_FRACTION = 0.60
_SIDEBAR_MAX_WIDTH_FRACTION = 0.30
_SIDEBAR_EDGE_MARGIN_FRACTION = 0.05


def _looks_like_sidebar(bounds: tuple[int, int, int, int], window_bounds: tuple[int, int, int, int]) -> bool:
    left, top, right, bottom = bounds
    win_left, win_top, win_right, win_bottom = window_bounds
    win_width = win_right - win_left
    win_height = win_bottom - win_top
    if win_width <= 0 or win_height <= 0:
        return False
    height = bottom - top
    width = right - left
    if height <= 0 or width <= 0:
        return False
    if height < win_height * _SIDEBAR_MIN_HEIGHT_FRACTION:
        return False
    if width > win_width * _SIDEBAR_MAX_WIDTH_FRACTION:
        return False
    margin = win_width * _SIDEBAR_EDGE_MARGIN_FRACTION
    anchored_left = left <= win_left + margin
    anchored_right = right >= win_right - margin
    return anchored_left or anchored_right


def classify_element(
    snapshot: UiaElementSnapshot,
    *,
    window_bounds: tuple[int, int, int, int],
    is_composer_match: bool,
    is_response_match: bool,
    is_main_content_match: bool,
) -> tuple[SemanticRole, KnowledgeType, str, str]:
    """Returns `(role, confidence, reason, source)`. Never raises; the
    honest default is `(UNKNOWN, KnowledgeType.UNKNOWN, ..., ...)` — Part
    D's own explicit rule: "if the system cannot confidently determine a
    role, return UNKNOWN rather than guessing."
    """
    if is_composer_match:
        return (
            SemanticRole.COMPOSER, KnowledgeType.INFERRED,
            "matched UiaAutomationBridge.find_composer()'s own heuristic "
            "(smallest, bottom-anchored, focusable, text-bearing element)",
            "UiaAutomationBridge.find_composer()",
        )

    if is_response_match:
        return (
            SemanticRole.RESPONSE_REGION, KnowledgeType.INFERRED,
            "matched UiaAutomationBridge.find_new_content()'s baseline-diff "
            "(text that did not exist anywhere in the pre-submission baseline)",
            "UiaAutomationBridge.find_new_content()",
        )

    control_type = snapshot.control_type

    if control_type == CONTROL_TYPE_WINDOW:
        if snapshot.is_modal is True:
            return (
                SemanticRole.DIALOG, KnowledgeType.OBSERVED,
                "UIA-reported ControlType is Window and WindowPattern.IsModal is True",
                "UiaAutomationBridge.snapshot_elements()",
            )
        return (
            SemanticRole.WINDOW, KnowledgeType.OBSERVED,
            "UIA-reported ControlType is Window (nested, not the root window itself)",
            "UiaAutomationBridge.snapshot_elements()",
        )

    if control_type in _TAB_TYPES:
        return (
            SemanticRole.TAB, KnowledgeType.OBSERVED,
            "UIA-reported ControlType is Tab or TabItem",
            "UiaAutomationBridge.snapshot_elements()",
        )

    if control_type in _MENU_TYPES:
        return (
            SemanticRole.MENU, KnowledgeType.OBSERVED,
            "UIA-reported ControlType is Menu, MenuBar, or MenuItem",
            "UiaAutomationBridge.snapshot_elements()",
        )

    if control_type in _BUTTON_TYPES:
        return (
            SemanticRole.BUTTON, KnowledgeType.OBSERVED,
            "UIA-reported ControlType is Button or SplitButton",
            "UiaAutomationBridge.snapshot_elements()",
        )

    if control_type in _INPUT_TYPES:
        return (
            SemanticRole.INPUT, KnowledgeType.OBSERVED,
            "UIA-reported ControlType is Edit or ComboBox",
            "UiaAutomationBridge.snapshot_elements()",
        )

    if is_main_content_match and not snapshot.is_focusable:
        return (
            SemanticRole.RESPONSE_REGION, KnowledgeType.INFERRED,
            "matched UiaAutomationBridge.find_main_content()'s own heuristic "
            "(largest text-bearing region) and is not itself focusable",
            "UiaAutomationBridge.find_main_content()",
        )

    if _looks_like_sidebar(snapshot.bounds, window_bounds):
        return (
            SemanticRole.SIDEBAR, KnowledgeType.INFERRED,
            "tall (>=60% window height), narrow (<=30% window width), "
            "window-edge-anchored region — generic sidebar geometry",
            "desktop.intelligence.classification (geometry heuristic)",
        )

    if snapshot.has_text_pattern and not snapshot.is_focusable:
        return (
            SemanticRole.TEXT_REGION, KnowledgeType.OBSERVED,
            "UIA reports a TextPattern and the element is not keyboard-focusable",
            "UiaAutomationBridge.snapshot_elements()",
        )

    return (
        SemanticRole.UNKNOWN, KnowledgeType.UNKNOWN,
        "no generic, evidence-based signal matched a known semantic category",
        "desktop.intelligence.classification",
    )
