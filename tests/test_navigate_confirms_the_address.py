"""Enter is the irreversible half, so it is the half that gets checked.

Measured live 2026-09-05: the founder's browser ended on

    gemini.google.com/ap        (asked for /app)

one character short, and a real 404. An address bar is not an ordinary
text field -- it autocompletes while you type, and a suggestion can
consume or replace the last keystroke. Pressing Enter without reading it
back commits to whatever the omnibox decided.
"""
from __future__ import annotations

from master_agent.desktop.trusted_browser_adapter import DesktopTrustedBrowser


class _Result:
    def __init__(self, success=True, output=None, ok=True, detail=""):
        self.success = success
        self.output = output or {}
        self.ok = ok
        self.detail = detail


class _Browser(DesktopTrustedBrowser):
    """Only the surface `navigate()` touches."""

    def __init__(self, shown):
        self._shown = shown
        self._application = "chrome"
        self.typed: list[str] = []
        self.pressed: list[str] = []

    def type_into(self, name_contains, text, control_type=None):
        self.typed.append(text)
        return _Result()

    def press(self, key):
        self.pressed.append(key)
        return _Result()

    def find(self, name_contains, control_type=None):
        return type("E", (), {"name": self._shown})()

    def _run(self, operation, **kwargs):
        if operation == "read_text":
            return _Result(output={"text": self._shown})
        return _Result()


class TestNavigateConfirmsTheAddress:

    def test_a_truncated_address_is_never_committed(self):
        """The live defect. One character short is a different page."""
        browser = _Browser("gemini.google.com/ap")
        result = browser.navigate("https://gemini.google.com/app")

        assert result.ok is False
        assert browser.pressed == [], "Enter was pressed on the wrong address"

    def test_the_asked_for_address_is_committed(self):
        browser = _Browser("gemini.google.com/app")
        result = browser.navigate("https://gemini.google.com/app")

        assert result.ok is True
        assert browser.pressed == ["enter"]

    def test_a_hidden_scheme_is_not_a_mismatch(self):
        """Chrome hides `https://`. That is presentation, not a different
        address, and refusing it would block every navigation."""
        browser = _Browser("gemini.google.com/app")
        assert browser.navigate("https://gemini.google.com/app").ok is True

    def test_a_trailing_slash_is_not_a_mismatch(self):
        browser = _Browser("gemini.google.com/app/")
        assert browser.navigate("https://gemini.google.com/app").ok is True

    def test_an_autocompleted_different_site_is_refused(self):
        """The omnibox offering a previous destination must not be able to
        redirect a reasoning call to somewhere the founder was working."""
        browser = _Browser("chatgpt.com/g/project")
        result = browser.navigate("https://gemini.google.com/app")

        assert result.ok is False
        assert browser.pressed == []

    def test_an_unreadable_address_bar_is_uncertain_and_refused(self):
        browser = _Browser("")
        assert browser.navigate("https://gemini.google.com/app").ok is False
        assert browser.pressed == []
