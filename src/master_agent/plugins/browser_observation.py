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

#: How much visible page text one observation may carry.
#:
#: Bounded for the same reason the tree is: an Evidence record is
#: persisted, replayed and sometimes handed to a reasoning step, and an
#: unbounded page would make all three expensive. Generous enough for a
#: listing or an article, which is what research actually reads.
MAX_PAGE_TEXT_CHARS = 20_000

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


#: How many links one page contributes.
#:
#: A directory page can carry hundreds. This is not a safety limit, it is
#: the same "what a later step can actually hold" limit `MAX_PAGE_TEXT_CHARS`
#: already states -- and it is declared in the observation when it bites,
#: never silently applied.
MAX_PAGE_LINKS = 60

#: Schemes that are not somewhere to go.
_NOT_A_DESTINATION = ("javascript:", "mailto:", "tel:", "about:", "data:")


@dataclass
class PageLink:
    """Somewhere this page says you can go next.

    Deterministic, from the page itself -- never a model's idea of where
    to look. It exists because a research mission that decides it needs
    more evidence had no way to act on that decision: the page's TEXT
    keeps the words "Sunday opening hours" and loses the `href` behind
    them, so a system that had already read the page holding the answer's
    address could only re-read the same page.
    """

    text: str
    url: str

    def as_dict(self) -> dict[str, Any]:
        return {"text": self.text, "url": self.url}


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
    #: What a person can actually SEE on the page.
    #:
    #: Opt-in like the tree, and for the same reason -- most steps do not
    #: need it and every Evidence record pays for what it carries.
    #:
    #: It exists because research had no way to reach reasoning.
    #: `Browser.ReadPageText` returned text as an Action RESULT, and an
    #: Action result is not Evidence: `input_bindings` refused it with
    #: "source has no canonical Evidence, so its output cannot be trusted
    #: as an input", and the Brain, which may only read canonical
    #: Evidence, saw nothing at all. A mission could visit three sites,
    #: verify all three, and have nothing to think about.
    text: str | None = None
    text_truncated: bool = False
    #: Where this page says you can go next. Gathered with the text, for
    #: the same reason and by the same opt-in: the read that wants to
    #: know what a page SAYS is the read that may need to know where it
    #: POINTS.
    links: list[PageLink] = field(default_factory=list)
    links_truncated: bool = False
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
            "text": self.text,
            "text_truncated": self.text_truncated,
            "links": [link.as_dict() for link in self.links],
            "links_truncated": self.links_truncated,
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


def destination_semantics(
    requested_url: str, actual_url: str, title: str = ""
) -> tuple[bool, str]:
    """Conservatively decide whether a redirect reached the requested place.

    Exact identity remains strongest.  Canonical redirects on the same
    site are accepted, and a cross-site redirect needs distinctive words
    from the requested path in the resulting URL/title.  Login, CAPTCHA
    and error destinations never satisfy navigation merely because they
    share a host.
    """
    import re
    from urllib.parse import urlsplit

    requested = normalise_url(requested_url)
    actual = normalise_url(actual_url)
    if requested == actual:
        return True, "exact_normalised_url"
    try:
        wanted = urlsplit(requested)
        reached = urlsplit(actual)
    except ValueError:
        return False, "invalid_url"
    if wanted.scheme not in {"http", "https"} or reached.scheme not in {"http", "https"}:
        return False, "unsupported_scheme"

    visible_destination = f"{reached.path} {reached.query} {title}".lower()
    blockers = ("login", "sign in", "signin", "captcha", "access denied",
                "not found", "error", "robot", "automated quer")
    if any(marker in visible_destination for marker in blockers):
        return False, "blocked_or_error_destination"

    def host(value: str) -> str:
        return value.lower().split(":", 1)[0].removeprefix("www.")

    generic = {"www", "com", "org", "net", "io", "co", "docs", "doc",
               "help", "support", "api", "en", "index", "html", "htm"}
    tokens = {
        token for token in re.findall(r"[a-z0-9]+", wanted.path.lower())
        if len(token) >= 4 and token not in generic
    }
    reached_words = set(re.findall(r"[a-z0-9]+", visible_destination))
    wanted_host, reached_host = host(wanted.netloc), host(reached.netloc)
    if wanted_host and wanted_host == reached_host:
        if wanted.path.rstrip("/") == reached.path.rstrip("/"):
            return True, "same_canonical_host_and_path"
        if not wanted.path.strip("/"):
            return True, "same_canonical_host"
        if tokens and tokens & reached_words:
            return True, "same_host_semantics_preserved"
        return False, "same_host_unrelated_path"

    if tokens and tokens & reached_words:
        return True, "requested_path_semantics_preserved"
    return False, "unrelated_destination"


def read_visible_text(page: Page) -> tuple[str | None, bool]:
    """The visible text of a page, and whether it was cut.

    `inner_text` rather than `text_content`: it returns what a person can
    actually see, leaving out script bodies and hidden nodes. A reasoning
    step given hidden markup would be reasoning about something the
    founder never saw.

    **Public, and the only implementation, on purpose.** The Action that
    reads a page and the Observation that independently verifies it must
    produce the same string for the same page, because
    `_verified_value()` compares them for EQUALITY and -- correctly --
    refuses to pick a winner when they differ.

    They did not. `read_page_text` cut at 40,000 characters and this cut
    at 20,000, so every page longer than 20,000 characters produced a
    reported value and an observed value that could never match, and any
    binding from it failed with

        the step reported '...' but the independent observation recorded
        '...'; refusing to choose

    Found live on Wikipedia. Nothing in the controlled battery could have
    found it: those fixture pages are a few hundred characters, so the
    two limits never had anything to disagree about. Two truncations of
    one string, compared for equality, is a bug by construction -- and
    the fix is one reader, not two constants that happen to agree today.
    """
    try:
        text = page.inner_text("body") or ""
    except Exception:  # noqa: BLE001 -- an unreadable page observes nothing
        return None, False
    if len(text) > MAX_PAGE_TEXT_CHARS:
        return text[:MAX_PAGE_TEXT_CHARS], True
    return text, False


def _observe_links(page: Page) -> tuple[list[PageLink], bool]:
    """Every anchor with a destination, absolute and deduplicated.

    `el.href` rather than `getAttribute('href')`: the browser has already
    resolved it against the page's own base, so a relative
    `hours.html` arrives as somewhere a later step can actually navigate
    to. An unreadable page contributes no links, the same posture
    `read_visible_text` already takes.
    """
    try:
        rows = page.eval_on_selector_all(
            "a[href]",
            "els => els.map(el => ({text: (el.innerText || '').trim(), url: el.href}))",
        ) or []
    except Exception:  # noqa: BLE001 -- an unreadable page observes nothing
        return [], False

    links: list[PageLink] = []
    seen: set[str] = set()
    for row in rows:
        url = str((row or {}).get("url") or "").strip()
        if not url or url in seen:
            continue
        if any(url.lower().startswith(scheme) for scheme in _NOT_A_DESTINATION):
            continue
        seen.add(url)
        links.append(PageLink(text=str((row or {}).get("text") or "").strip()[:120], url=url))
        if len(links) >= MAX_PAGE_LINKS:
            return links, len(seen) < len(rows)
    return links, False


def normalize_observation(
    page: Page,
    selectors: list[str] | None = None,
    include_accessibility_tree: bool = False,
    include_available_actions: bool = False,
    include_text: bool = False,
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
    text, text_truncated = read_visible_text(page) if include_text else (None, False)
    links, links_truncated = _observe_links(page) if include_text else ([], False)

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
        text=text,
        text_truncated=text_truncated,
        links=links,
        links_truncated=links_truncated,
        captured_at=datetime.now(UTC),
    )
