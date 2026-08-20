"""The text a page is actually showing, so a later step can reason over it.

`Browser.ObserveBrowser` publishes `url` and `title` -- the two facts every
page has -- and that was enough to prove a value flowed from a browser
into a file. It is not enough to *judge* anything. A mission that has to
compare what several pages say needs what they say.

So this is the smallest capability that closes that: the visible text of
the current page, with its URL and title, from the live session. Nothing
is parsed for meaning here. There is no notion of an article, a listing,
a price or a posting, and no site is special -- a capability that knew how
to read one website would need rewriting for the next one, and would
quietly encode somebody's page structure as a promise.

READ_ONLY: it looks, and changes nothing.
"""
from __future__ import annotations

from typing import Any

from master_agent.environment.browser_session import (
    BrowserSessionError,
    BrowserSessionManager,
)
from master_agent.executor.action import Action, ExecutionResult
from master_agent.plugins.base import PermissionCategory, RiskTier

READ_PAGE_TEXT = "read_page_text"

#: A page's text goes on to become part of a prompt, so the cap is about
#: what a reasoning step can actually hold, not about safety. Declared in
#: the result when it bites.
MAX_TEXT_CHARS = 40_000


class ReadPageTextAction(Action):
    name = READ_PAGE_TEXT
    description = (
        "Read the visible text of the current page in an open browser session, "
        "with its URL and title, so a later step can read or reason over what "
        "the page actually says."
    )
    risk_tier = RiskTier.READ_ONLY
    permission_category = PermissionCategory.READ
    expected_result = (
        "The current page's visible text, URL and title are returned; "
        "nothing is changed."
    )

    def __init__(self, sessions: BrowserSessionManager) -> None:
        self._sessions = sessions

    def required_parameters(self) -> list[str]:
        return ["session_id"]

    def output_parameters(self) -> list[dict[str, Any]]:
        return [
            {"name": "url", "type": "string",
             "description": "The page's current URL as the browser reports it."},
            {"name": "title", "type": "string",
             "description": "The page's current title as the browser reports it."},
            {"name": "text", "type": "string",
             "description": "The visible text of the page as it currently stands."},
        ]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        if not (parameters.get("session_id") or "").strip():
            return ["missing required parameter: session_id"]
        return []

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        try:
            session = self._sessions.get(parameters["session_id"].strip())
        except BrowserSessionError as exc:
            return ExecutionResult(success=False, errors=[str(exc)])

        try:
            page = session.page
            url = page.url
            title = page.title()
            # `inner_text` rather than `text_content`: it returns what a
            # person can actually see, leaving out script bodies and
            # hidden nodes. A reasoning step given hidden markup would be
            # reasoning about something the founder never saw.
            text = page.inner_text("body")
        except Exception as exc:  # noqa: BLE001 - a page failure is data
            return ExecutionResult(
                success=False, errors=[f"could not read the page: {exc}"]
            )

        text = text or ""
        truncated = len(text) > MAX_TEXT_CHARS
        if truncated:
            text = text[:MAX_TEXT_CHARS]

        return ExecutionResult(
            success=True,
            output={
                "url": url,
                "title": title,
                "text": text,
                "truncated": truncated,
            },
        )
