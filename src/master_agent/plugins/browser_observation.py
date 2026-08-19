"""The Observation and Normalization layers for the Browser Worker. See
BROWSER_WORKER_ARCHITECTURE.md §7.

`normalize_observation()` is the only function, besides the Actions
themselves, that touches a Playwright `Page`. ObserveBrowserAction and
BrowserVerifier both call this one implementation — no duplicated "how do
we read the page" logic (ENGINEERING_PRINCIPLES.md #7). Everything past
`BrowserObservation.as_dict()` is a plain, JSON-shaped dict; no Playwright
type ever crosses that boundary.

Five observation facets, covering every source Mission Brief 022 named:
current page (url/title), viewport, DOM state and visible elements (the
caller's selectors), the accessibility tree, and available actions (the
page's interactive affordances). The last two are opt-in per call — see
§7 of the architecture doc for why: both are unbounded in the size of the
page rather than the size of what the caller asked about, and Verification
re-observes on every verified step, so paying for them unconditionally
would tax every Mission for data most steps never check against.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from playwright.sync_api import Page

# An accessibility tree is unbounded in page size; a very large one would
# bloat every Evidence record that captured it (and any Memory record a
# future Miracle persists Evidence into). Capped rather than truncated
# silently -- `accessibility_tree_truncated` says so out loud.
MAX_ACCESSIBILITY_TREE_CHARS = 20_000

# Same reasoning for interactive affordances: a large page can have
# hundreds. Capped, with `available_actions_truncated` reporting it.
MAX_AVAILABLE_ACTIONS = 100

# What counts as "an action is available here" -- deliberately expressed in
# generic web-platform vocabulary (element types and ARIA roles), never in
# terms of any particular site's markup.
_INTERACTIVE_SELECTOR = (
    "a[href], button, input:not([type=hidden]), select, textarea, "
    "[role=button], [role=link], [role=checkbox], [role=radio], [role=tab], "
    "[role=menuitem], [contenteditable=true]"
)


@dataclass
class BrowserElement:
    """A generic, Playwright-free description of one element a caller
    asked to observe — never a Playwright Locator/ElementHandle."""

    selector: str
    is_visible: bool
    text: str | None = None
    tag_name: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "selector": self.selector,
            "is_visible": self.is_visible,
            "text": self.text,
            "tag_name": self.tag_name,
        }


@dataclass
class AvailableAction:
    """One interaction the current page actually affords right now — an
    observation of browser state, not a claim about what the Worker can
    do. (What the *Worker* can do is its capability manifest, which is a
    Capability Registry concern, not an Observation one.)"""

    role: str
    name: str | None
    tag_name: str | None
    is_enabled: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "name": self.name,
            "tag_name": self.tag_name,
            "is_enabled": self.is_enabled,
        }


@dataclass
class BrowserObservation:
    url: str
    title: str
    viewport_width: int | None
    viewport_height: int | None
    #: `url` with the incidentals that do not change which page this is
    #: removed -- scheme and host lower-cased, a bare trailing slash
    #: dropped. Exists so Verification can compare destinations by
    #: EQUALITY: asking for "https://example.com" and landing on
    #: "https://example.com/" is the same page, and the alternative to a
    #: normalised field is a substring test, which would also accept
    #: "https://example.com.attacker.test".
    url_normalised: str = ""
    elements: list[BrowserElement] = field(default_factory=list)
    accessibility_tree: str | None = None
    accessibility_tree_truncated: bool = False
    available_actions: list[AvailableAction] = field(default_factory=list)
    available_actions_truncated: bool = False
    captured_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def as_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "url_normalised": self.url_normalised,
            "title": self.title,
            "viewport_width": self.viewport_width,
            "viewport_height": self.viewport_height,
            "elements": [element.as_dict() for element in self.elements],
            "accessibility_tree": self.accessibility_tree,
            "accessibility_tree_truncated": self.accessibility_tree_truncated,
            "available_actions": [action.as_dict() for action in self.available_actions],
            "available_actions_truncated": self.available_actions_truncated,
            "captured_at": self.captured_at.isoformat(),
        }


def _observe_elements(page: Page, selectors: list[str]) -> list[BrowserElement]:
    """A selector that matches nothing, or that errors during lookup, is
    reported as not visible rather than raising: Observation must never
    crash a Verification pass just because the page doesn't currently have
    what was expected — that absence IS the observation."""
    elements: list[BrowserElement] = []
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            is_visible = locator.is_visible()
        except Exception:  # noqa: BLE001 — a lookup failure means "not visible", not a crash
            is_visible = False
        try:
            text = locator.text_content()
        except Exception:  # noqa: BLE001
            text = None
        try:
            tag_name = locator.evaluate("el => el.tagName")
        except Exception:  # noqa: BLE001
            tag_name = None
        elements.append(
            BrowserElement(selector=selector, is_visible=is_visible, text=text, tag_name=tag_name)
        )
    return elements


def _observe_accessibility_tree(page: Page) -> tuple[str | None, bool]:
    """Returns (tree, truncated). A page whose accessibility tree can't be
    captured yields None rather than raising — same principle as
    _observe_elements: a failed observation is an observation."""
    try:
        tree = page.locator("body").aria_snapshot()
    except Exception:  # noqa: BLE001
        return None, False
    if tree is None:
        return None, False
    if len(tree) > MAX_ACCESSIBILITY_TREE_CHARS:
        return tree[:MAX_ACCESSIBILITY_TREE_CHARS], True
    return tree, False


def _is_observably_visible(item: Any) -> bool:
    """An affordance whose visibility can't be determined is treated as
    not available — the conservative reading, and the one consistent with
    every other facet: a failed observation reports absence, never a
    guess."""
    try:
        return bool(item.is_visible())
    except Exception:  # noqa: BLE001
        return False


def _observe_available_actions(page: Page) -> tuple[list[AvailableAction], bool]:
    """Enumerates the page's interactive affordances. Returns
    (actions, truncated)."""
    try:
        locator = page.locator(_INTERACTIVE_SELECTOR)
        total = locator.count()
    except Exception:  # noqa: BLE001
        return [], False

    truncated = total > MAX_AVAILABLE_ACTIONS
    actions: list[AvailableAction] = []
    for index in range(min(total, MAX_AVAILABLE_ACTIONS)):
        item = locator.nth(index)
        if not _is_observably_visible(item):
            continue
        try:
            tag_name = item.evaluate("el => el.tagName")
        except Exception:  # noqa: BLE001
            tag_name = None
        try:
            role = item.evaluate(
                "el => el.getAttribute('role') || el.tagName.toLowerCase()"
            )
        except Exception:  # noqa: BLE001
            role = tag_name.lower() if tag_name else "unknown"
        try:
            name = (item.text_content() or "").strip() or None
        except Exception:  # noqa: BLE001
            name = None
        try:
            is_enabled = item.is_enabled()
        except Exception:  # noqa: BLE001
            is_enabled = True
        actions.append(
            AvailableAction(role=role, name=name, tag_name=tag_name, is_enabled=is_enabled)
        )
    return actions, truncated


def normalise_url(url: str) -> str:
    """The one spelling of "the same destination".

    Both sides of a navigation check go through this, so a step that asked
    for `https://example.com` still matches a browser that reports
    `https://example.com/`. Deliberately conservative: only the scheme and
    host case and a bare trailing slash are touched. Query and fragment
    are left alone because they can select a different page.
    """
    from urllib.parse import urlsplit, urlunsplit

    try:
        parts = urlsplit((url or "").strip())
    except ValueError:
        return (url or "").strip()

    path = parts.path
    if path == "/":
        path = ""
    return urlunsplit((
        parts.scheme.lower(), parts.netloc.lower(), path, parts.query, parts.fragment
    ))


def normalize_observation(
    page: Page,
    selectors: list[str] | None = None,
    include_accessibility_tree: bool = False,
    include_available_actions: bool = False,
) -> BrowserObservation:
    """Reads generic, universal facts off a live Page. `selectors` names
    the specific elements a caller cares about; the two `include_*` flags
    opt into the page-sized facets (see module docstring for why they are
    opt-in rather than always-on)."""
    selectors = selectors or []
    viewport = page.viewport_size

    accessibility_tree, tree_truncated = (
        _observe_accessibility_tree(page) if include_accessibility_tree else (None, False)
    )
    available_actions, actions_truncated = (
        _observe_available_actions(page) if include_available_actions else ([], False)
    )

    return BrowserObservation(
        url=page.url,
        url_normalised=normalise_url(page.url),
        title=page.title(),
        viewport_width=viewport["width"] if viewport else None,
        viewport_height=viewport["height"] if viewport else None,
        elements=_observe_elements(page, selectors),
        accessibility_tree=accessibility_tree,
        accessibility_tree_truncated=tree_truncated,
        available_actions=available_actions,
        available_actions_truncated=actions_truncated,
        captured_at=datetime.now(UTC),
    )
