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
#: Capabilities whose whole point is to observe the page they are on.
#:
#: `read_page_text` was absent, so `subject()` returned None, no Verifier
#: ran, and the capability that gathers research produced no canonical
#: Evidence at all. Everything downstream then behaved correctly and
#: uselessly: `input_bindings` refused its output as untrusted, and the
#: Brain -- which may read only Evidence -- had nothing to reason about.
_PAGE_OBSERVABLE: frozenset[str] = frozenset(
    {"observe_browser", "read_page_text"}
)


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
                field="destination_matches",
                operator="equals",
                value=True,
                description=f"the page reached the requested destination {requested}",
            )],
        )

    # ObserveBrowser: the claim is that the browser state can actually be
    # read. Checking that a url and a title were captured establishes
    # exactly that and nothing more -- this step promises an observation,
    # not a particular page.
    checks = [
        ObservationCheck(
            field="url", operator="exists",
            description="a page URL could be observed",
        ),
        ObservationCheck(
            field="title", operator="exists",
            description="a page title could be observed",
        ),
    ]

    if _in(capability, frozenset({"read_page_text"})):
        checks.extend([
            ObservationCheck(
                field="text", operator="exists",
                description="visible page text could be observed",
            ),
            ObservationCheck(
                field="page_usable", operator="equals", value=True,
                description="the observed page is not an explicit error surface",
            ),
        ])

    # When the step named selectors, the promise is larger by exactly one
    # thing: those selectors were the ones looked at. The verifier
    # re-observes the page from scratch and passes the same selectors, so
    # position `i` answers request `i` -- asserting that identity is what
    # stops a fresh observation of the WRONG element from reading as
    # proof about the right one.
    #
    # What is deliberately NOT asserted here is that the element was
    # found. `_observe_elements()` reports a selector that matches
    # nothing as `is_visible=False` with null text, on the stated
    # principle that an absence IS an observation -- and a step whose
    # whole purpose may be to confirm something is gone must not be
    # failed for succeeding. Whether a particular element should be
    # present, and what it should say, is a claim about a particular
    # page; this module states what a browser observation means, and
    # inventing a page-specific postcondition here is how fixture
    # semantics leak into product code.
    requested = payload.get("selectors")
    if isinstance(requested, list):
        for index, selector in enumerate(requested):
            if not isinstance(selector, str) or not selector.strip():
                continue
            checks.append(ObservationCheck(
                field=f"elements.{index}.selector",
                operator="equals",
                value=selector,
                description=f"'{selector}' is the element that was observed",
            ))

    return ExpectedOutcome(description=description, checks=checks)
