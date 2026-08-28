"""Shared helpers for browser Actions. Not itself an Action — kept small
and private, the same way executor/action.py's module-level functions
(is_unsafe_relative_path, default_locations, ...) are shared without being
part of the Action contract. See BROWSER_WORKER_ARCHITECTURE.md §6, §8
(Error Handling — mechanical failures only, never strategic recovery).
"""
from __future__ import annotations

from playwright.sync_api import Error as PlaywrightError

#: The budget for operating on a page that is ALREADY LOADED -- click,
#: type, press, wait for a selector. Five seconds is generous for those:
#: the document is in memory and the element either exists or does not.
DEFAULT_TIMEOUT_MS = 5_000

#: The budget for FETCHING a document over the network.
#:
#: Navigation shared the element budget above, and that conflated two
#: different things. Clicking asks an in-memory document a question;
#: `page.goto()` asks an arbitrary public host for a document, over the
#: founder's connection, and waits for it to load. Five seconds is a
#: reasonable answer to the first question and not to the second.
#:
#: Measured, live, twice: the founder's research objective reached
#: `Browser.Navigate` against a heavy commercial storefront and hit
#: `Page.goto: Timeout 5000ms exceeded` -- a mission failing not because
#: the site refused us but because we did not wait for it.
#:
#: 30 seconds because that is Playwright's own default navigation
#: timeout. Borrowed rather than invented: the library that owns
#: navigation semantics already made this judgement, and a number chosen
#: here would be a number nobody could defend later.
#:
#: Still bounded, and deliberately not applied to anything else -- a
#: genuinely hung navigation still fails, and no element interaction
#: waits any longer than it did.
DEFAULT_NAVIGATION_TIMEOUT_MS = 30_000

__all__ = [
    "DEFAULT_NAVIGATION_TIMEOUT_MS",
    "DEFAULT_TIMEOUT_MS",
    "PlaywrightError",
    "describe_playwright_failure",
]


def describe_playwright_failure(exc: Exception, operation: str) -> str:
    """Turn a Playwright exception into a mechanical, honest failure
    message. Distinguishing a timeout from other Playwright errors is
    still a mechanical classification (Playwright itself makes the same
    distinction) — never a strategic diagnosis of *why* it happened, which
    belongs to Executive Brain / Recovery, not this Worker."""
    message = str(exc)
    if "timeout" in type(exc).__name__.lower() or "timeout" in message.lower():
        return f"{operation} timed out: {message}"
    return f"{operation} failed: {message}"
