"""What a browser Step's claim looks like when checked against a browser.

The same division of labour as `filesystem_expectations`: the Planner owns
*what the Step is for* and carries it in `description`, which travels
through here untouched; this module owns *how that claim is checked*,
because the browser package is what knows the shape of a browser
observation. The Runtime constructs no checks and the `MissionPlan` is
never rewritten.

Two different subjects are observed, so two different verifiers are used:

* a **page** -- url, title (Navigate, ObserveBrowser)
* a **session registry** -- is this session open (Open, Close)

Close is the reason that split exists. `BrowserVerifier` resolves the
session before reading the page, and a closed session cannot be resolved,
so verifying a successful close through it would report `ERROR` -- "the
observation could not be captured" -- for a session that closed exactly as
asked. Absence is the expected fact there, and something has to be able to
observe it as one.
"""
from __future__ import annotations

from typing import Any

from master_agent.verification.evidence import ExpectedOutcome, ObservationCheck

#: Which subject a capability's expectation is about. Named, not guessed
#: from the verb: "observe" and "open" would otherwise look alike.
PAGE = "page"
SESSION = "session"

_SESSION_PRESENT: frozenset[str] = frozenset({"open_browser_session"})
_SESSION_ABSENT: frozenset[str] = frozenset({"close_browser_session"})
_PAGE_DESTINATION: frozenset[str] = frozenset({"navigate"})
_PAGE_OBSERVABLE: frozenset[str] = frozenset({"observe_browser"})


def _local(capability: str) -> str:
    return capability.rsplit(".", 1)[-1].replace("_", "").replace("-", "").lower()


def _in(capability: str, names: frozenset[str]) -> bool:
    wanted = _local(capability)
    return any(_local(name) == wanted for name in names)


def subject(capability: str) -> str | None:
    """Which observation this capability's expectation is about, or `None`
    when this module cannot state one.

    `None` is neither a pass nor a failure: under the fail-closed runtime
    the Step cannot claim completion, which is the truthful answer while a
    capability has no domain verification yet. Click, TypeText, Scroll,
    PressKey and WaitForSelector are in that position -- their effects are
    page changes this module does not yet know how to state.
    """
    if _in(capability, _SESSION_PRESENT) or _in(capability, _SESSION_ABSENT):
        return SESSION
    if _in(capability, _PAGE_DESTINATION) or _in(capability, _PAGE_OBSERVABLE):
        return PAGE
    return None


def bind_for_environment(
    capability: str,
    payload: dict[str, Any],
    description: str,
) -> ExpectedOutcome | None:
    """The Planner's claim, expressed as checks a browser can answer."""
    from master_agent.plugins.browser_observation import normalise_url

    which = subject(capability)
    if which is None:
        return None

    session_id = str(payload.get("session_id") or "")

    if _in(capability, _SESSION_ABSENT):
        return ExpectedOutcome(
            description=description,
            checks=[ObservationCheck(
                field="session_exists", operator="equals", value=False,
                description=f"session '{session_id}' is no longer open",
            )],
        )

    if _in(capability, _SESSION_PRESENT):
        return ExpectedOutcome(
            description=description,
            checks=[ObservationCheck(
                field="session_exists", operator="equals", value=True,
                description=f"session '{session_id}' is open",
            )],
        )

    if _in(capability, _PAGE_DESTINATION):
        requested = payload.get("url")
        if not isinstance(requested, str) or not requested.strip():
            # Nothing to compare a destination against. Better to state no
            # expectation than to invent one that any page would satisfy.
            return None
        return ExpectedOutcome(
            description=description,
            checks=[ObservationCheck(
                field="url_normalised",
                operator="equals",
                value=normalise_url(requested),
                # EQUALITY on a normalised field, not `contains`. A
                # substring test for "example.com" would also be satisfied
                # by "example.com.attacker.test", which is a different
                # place entirely.
                description=f"the page is at {normalise_url(requested)}",
            )],
        )

    # ObserveBrowser: the claim is that the browser state can actually be
    # read. Checking that a url and a title were captured establishes
    # exactly that and nothing more -- this step promises an observation,
    # not a particular page.
    return ExpectedOutcome(
        description=description,
        checks=[
            ObservationCheck(
                field="url", operator="exists",
                description="a page URL could be observed",
            ),
            ObservationCheck(
                field="title", operator="exists",
                description="a page title could be observed",
            ),
        ],
    )
