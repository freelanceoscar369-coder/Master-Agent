"""Observation/Normalization unit tests. See BROWSER_WORKER_ARCHITECTURE.md
§7. All content is generated locally via page.set_content() -- no
navigation to a real website (Mission Brief 022's product-independence
rule).
"""
from __future__ import annotations

from master_agent.environment.browser_session import BrowserSessionManager
from master_agent.plugins.browser_observation import normalize_observation
from tests.browser_test_support import SAMPLE_HTML


def test_normalize_observation_reads_url_and_title():
    manager = BrowserSessionManager()
    manager.open_session("s1")
    try:
        page = manager.get("s1").page
        page.set_content(SAMPLE_HTML)
        observation = normalize_observation(page)
        assert observation.title == "Sample Test Page"
        assert observation.viewport_width is not None
        assert observation.viewport_height is not None
        assert observation.elements == []
    finally:
        manager.close_all()


def test_normalize_observation_reads_requested_elements():
    manager = BrowserSessionManager()
    manager.open_session("s1")
    try:
        page = manager.get("s1").page
        page.set_content(SAMPLE_HTML)
        observation = normalize_observation(page, ["#heading", "#btn"])
        by_selector = {element.selector: element for element in observation.elements}
        assert by_selector["#heading"].text == "Hello"
        assert by_selector["#heading"].is_visible is True
        assert by_selector["#heading"].tag_name == "H1"
        assert by_selector["#btn"].text == "Click me"
    finally:
        manager.close_all()


def test_normalize_observation_reports_hidden_element_as_not_visible():
    manager = BrowserSessionManager()
    manager.open_session("s1")
    try:
        page = manager.get("s1").page
        page.set_content(SAMPLE_HTML)
        observation = normalize_observation(page, ["#missing-link"])
        assert observation.elements[0].is_visible is False
    finally:
        manager.close_all()


def test_normalize_observation_reports_nonexistent_selector_without_raising():
    manager = BrowserSessionManager()
    manager.open_session("s1")
    try:
        page = manager.get("s1").page
        page.set_content(SAMPLE_HTML)
        observation = normalize_observation(page, ["#does-not-exist"])
        assert observation.elements[0].is_visible is False
        assert observation.elements[0].text is None
    finally:
        manager.close_all()


def test_accessibility_tree_is_off_by_default_and_captured_when_requested():
    """Mission Brief 022 names the accessibility tree as an observation
    source; it is opt-in per call because it is unbounded in page size --
    see BROWSER_WORKER_ARCHITECTURE.md §7."""
    manager = BrowserSessionManager()
    manager.open_session("s1")
    try:
        page = manager.get("s1").page
        page.set_content(SAMPLE_HTML)

        default_observation = normalize_observation(page)
        assert default_observation.accessibility_tree is None

        observation = normalize_observation(page, include_accessibility_tree=True)
        assert observation.accessibility_tree is not None
        # Generic ARIA vocabulary, not markup: the heading and button are
        # described by role, which is the whole point of this facet.
        assert "heading" in observation.accessibility_tree
        assert "button" in observation.accessibility_tree
        assert observation.accessibility_tree_truncated is False
    finally:
        manager.close_all()


def test_available_actions_is_off_by_default_and_captured_when_requested():
    manager = BrowserSessionManager()
    manager.open_session("s1")
    try:
        page = manager.get("s1").page
        page.set_content(SAMPLE_HTML)

        assert normalize_observation(page).available_actions == []

        observation = normalize_observation(page, include_available_actions=True)
        roles = {action.role for action in observation.available_actions}
        assert "button" in roles
        assert "a" in roles  # the visible link
        assert "input" in roles
        assert observation.available_actions_truncated is False
    finally:
        manager.close_all()


def test_available_actions_reports_enabled_state_and_skips_hidden_affordances():
    manager = BrowserSessionManager()
    manager.open_session("s1")
    try:
        page = manager.get("s1").page
        page.set_content(SAMPLE_HTML)
        observation = normalize_observation(page, include_available_actions=True)

        by_name = {action.name: action for action in observation.available_actions}
        assert by_name["Click me"].is_enabled is True
        assert by_name["Disabled"].is_enabled is False
        # The hidden link affords nothing right now, so it is not an
        # available action -- that absence is itself the observation.
        assert "Hidden" not in by_name
    finally:
        manager.close_all()


def test_accessibility_tree_is_capped_and_reports_truncation_honestly():
    """A cap that silently truncated would make Evidence quietly wrong --
    the flag says so out loud instead."""
    from master_agent.plugins import browser_observation

    manager = BrowserSessionManager()
    manager.open_session("s1")
    original_cap = browser_observation.MAX_ACCESSIBILITY_TREE_CHARS
    try:
        page = manager.get("s1").page
        page.set_content(SAMPLE_HTML)
        browser_observation.MAX_ACCESSIBILITY_TREE_CHARS = 10
        observation = browser_observation.normalize_observation(
            page, include_accessibility_tree=True
        )
        assert observation.accessibility_tree_truncated is True
        assert len(observation.accessibility_tree) == 10
    finally:
        browser_observation.MAX_ACCESSIBILITY_TREE_CHARS = original_cap
        manager.close_all()


def test_as_dict_is_a_plain_json_shape_with_no_playwright_types():
    manager = BrowserSessionManager()
    manager.open_session("s1")
    try:
        page = manager.get("s1").page
        page.set_content(SAMPLE_HTML)
        observation = normalize_observation(
            page,
            ["#heading"],
            include_accessibility_tree=True,
            include_available_actions=True,
        )
        data = observation.as_dict()
        import json

        json.dumps(data)  # must not raise, with every facet populated
        assert data["elements"][0]["selector"] == "#heading"
        assert data["elements"][0]["text"] == "Hello"
        assert isinstance(data["accessibility_tree"], str)
        assert isinstance(data["available_actions"], list)
        assert isinstance(data["available_actions"][0], dict)
    finally:
        manager.close_all()
