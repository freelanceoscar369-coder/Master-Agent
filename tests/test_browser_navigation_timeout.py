"""Navigation gets a network budget; element interaction does not.

## The failure

The founder's research objective reached the web and died here, twice:

    Browser.Navigate -> Page.goto: Timeout 5000ms exceeded

Not a refusal. Not a block. The mission failed because it did not wait
for a heavy commercial storefront to load.

Every browser Action shared one `DEFAULT_TIMEOUT_MS = 5_000`, and that
conflated two different things. Clicking asks an in-memory document a
question; `page.goto()` asks an arbitrary public host for a document over
the founder's connection. Five seconds is a fair answer to the first and
not to the second.

## What must NOT change

A longer wait must never turn a real block into a success. Navigation
reports the URL it actually landed on, so an interstitial or a redirect
still produces different observed reality and still fails Verification.
The timeout was never what protected that, and this change does not
touch it.
"""
from __future__ import annotations

import pytest

from master_agent.executor.actions.browser._common import (
    DEFAULT_NAVIGATION_TIMEOUT_MS,
    DEFAULT_TIMEOUT_MS,
)


class TestTheTwoBudgetsAreDifferentThings:
    def test_navigation_gets_longer_than_element_interaction(self):
        assert DEFAULT_NAVIGATION_TIMEOUT_MS > DEFAULT_TIMEOUT_MS

    def test_element_interaction_was_not_broadened(self):
        """The fix must not become "everything waits longer". A founder
        pays for every one of these in latency they can feel."""
        assert DEFAULT_TIMEOUT_MS == 5_000

    def test_navigation_is_still_bounded(self):
        """A genuinely hung navigation must still fail. Unbounded is not
        patience, it is a mission that never returns."""
        assert 0 < DEFAULT_NAVIGATION_TIMEOUT_MS <= 60_000

    def test_the_value_is_playwrights_own_default_not_an_invented_one(self):
        """Borrowed on purpose: the library that owns navigation
        semantics already made this judgement, and a number chosen here
        would be one nobody could defend later."""
        assert DEFAULT_NAVIGATION_TIMEOUT_MS == 30_000


class TestOnlyNavigationChanged:
    def actions(self):
        from master_agent.executor.actions.browser import (
            click, navigate, press_key, type_text, wait_for_selector,
        )

        return click, navigate, press_key, type_text, wait_for_selector

    def test_navigate_uses_the_navigation_budget(self):
        import inspect

        from master_agent.executor.actions.browser import navigate

        source = inspect.getsource(navigate)
        assert "DEFAULT_NAVIGATION_TIMEOUT_MS" in source
        # Not merely imported alongside the old one.
        assert "DEFAULT_TIMEOUT_MS," not in source

    @pytest.mark.parametrize("module_name", [
        "click", "press_key", "type_text", "wait_for_selector",
    ])
    def test_element_actions_still_use_the_element_budget(self, module_name):
        import importlib
        import inspect

        module = importlib.import_module(
            f"master_agent.executor.actions.browser.{module_name}"
        )
        source = inspect.getsource(module)
        assert "DEFAULT_TIMEOUT_MS" in source
        assert "DEFAULT_NAVIGATION_TIMEOUT_MS" not in source, (
            f"{module_name} silently inherited the navigation budget; a click "
            "on a loaded page has no reason to wait that long"
        )


class TestAnExplicitTimeoutStillWins:
    """A plan that states its own budget keeps it. The default is a
    default, not a floor."""

    def action(self):
        from master_agent.executor.actions.browser.navigate import NavigateAction

        class Page:
            url = "https://example.invalid/"
            def goto(self, url, timeout=None):
                self.seen = timeout
            def title(self):
                return "t"

        class Session:
            def __init__(self):
                self.page = Page()

        class Sessions:
            def __init__(self, session):
                self._session = session
            def get(self, session_id):
                return self._session

        session = Session()
        return NavigateAction(Sessions(session)), session

    def test_an_explicit_timeout_is_honoured(self):
        action, session = self.action()
        action.run({"session_id": "s1", "url": "https://example.invalid/",
                    "timeout_ms": 1234})
        assert session.page.seen == 1234

    def test_the_default_is_the_navigation_budget(self):
        action, session = self.action()
        action.run({"session_id": "s1", "url": "https://example.invalid/"})
        assert session.page.seen == DEFAULT_NAVIGATION_TIMEOUT_MS


class TestATimeoutIsNotASiteBlock:
    """These are different failures and must stay different.

    A longer wait may rescue a slow page. It must never make an
    interstitial, a redirect, or an outright rejection look like success.
    """

    def test_navigation_reports_the_url_it_actually_landed_on(self):
        """The observed URL, not the requested one -- which is what lets
        Verification catch a redirect to a bot wall. This is what
        protects truthfulness, not the timeout, and it is unchanged."""
        import inspect

        from master_agent.executor.actions.browser import navigate

        source = inspect.getsource(navigate.NavigateAction.run)
        assert "session.page.url" in source
        assert '"url": url' not in source, (
            "navigation reported the REQUESTED url; a redirect to an "
            "interstitial would then look like the page we asked for"
        )

    def test_a_playwright_failure_is_still_reported_as_a_failure(self):
        from master_agent.executor.actions.browser._common import PlaywrightError
        from master_agent.executor.actions.browser.navigate import NavigateAction

        class Page:
            url = ""
            def goto(self, url, timeout=None):
                raise PlaywrightError("Timeout 30000ms exceeded")
            def title(self):
                return ""

        class Sessions:
            def get(self, session_id):
                return type("S", (), {"page": Page()})()

        result = NavigateAction(Sessions()).run(
            {"session_id": "s1", "url": "https://example.invalid/"}
        )
        assert result.success is False
        assert result.errors
