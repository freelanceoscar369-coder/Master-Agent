"""Shared helpers for browser Actions. Not itself an Action — kept small
and private, the same way executor/action.py's module-level functions
(is_unsafe_relative_path, default_locations, ...) are shared without being
part of the Action contract. See BROWSER_WORKER_ARCHITECTURE.md §6, §8
(Error Handling — mechanical failures only, never strategic recovery).
"""
from __future__ import annotations

from playwright.sync_api import Error as PlaywrightError

DEFAULT_TIMEOUT_MS = 5_000

__all__ = ["DEFAULT_TIMEOUT_MS", "PlaywrightError", "describe_playwright_failure"]


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
