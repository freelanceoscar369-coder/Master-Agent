"""ObserveBrowserAction — the Observation layer's entry point as a
capability a Brain/caller can request directly. Calls the exact same
normalize_observation() function BrowserVerifier uses internally (see
plugins/browser_observation.py) — one shared implementation, two callers,
per ENGINEERING_PRINCIPLES.md #7.
"""
from __future__ import annotations

from typing import Any

from master_agent.environment.browser_session import BrowserSessionError, BrowserSessionManager
from master_agent.executor.action import Action, ExecutionResult
from master_agent.plugins.base import PermissionCategory, RiskTier
from master_agent.plugins.browser_observation import normalize_observation

OBSERVE_BROWSER = "observe_browser"


class ObserveBrowserAction(Action):
    name = OBSERVE_BROWSER
    description = "Capture a generic observation of an open browser session's current state."
    risk_tier = RiskTier.READ_ONLY
    permission_category = PermissionCategory.READ
    expected_result = "A BrowserObservation describing the current page is returned."

    def __init__(self, sessions: BrowserSessionManager) -> None:
        self._sessions = sessions

    def required_parameters(self) -> list[str]:
        return ["session_id"]

    def optional_parameters(self) -> list[dict[str, Any]]:
        """The three arguments `run()` already reads beyond `session_id`.

        Nothing new is accepted here. `validate()` has checked
        `selectors`, `include_accessibility_tree` and
        `include_available_actions` since this Action was written, and
        `run()` forwards all three to `normalize_observation()`. They were
        simply never *published*, so the Planner's catalogue rendered this
        capability as `Browser.ObserveBrowser(session_id, ...)` -- required
        names plus an "others may exist" hedge -- and a planner that cannot
        see the whole roster correctly refuses to use an argument it would
        be guessing at.

        The cost of that silence was measured. A founder asked, in full
        detail, for a page element's text to be observed and reported; the
        deterministic lane could not name the argument that asks for it, so
        the objective went to a model, which planned `ReadPageText` into
        `Reasoning.Transform` and failed on a binding. The capability that
        answers the question directly was registered the whole time.

        Returning a list -- rather than `None` -- is this Action stating
        that its argument roster is now complete, which is what lets
        `args_complete` be true and what makes `selectors` plannable.
        """
        return [
            {
                "name": "selectors",
                "type": "array",
                "description": (
                    "CSS selectors to observe individually. Each one produces "
                    "an entry in `elements`, in the order given, reporting "
                    "whether it is visible and what text it holds. A selector "
                    "that matches nothing is reported as not visible rather "
                    "than failing -- that absence is itself the observation."
                ),
                "default": [],
            },
            {
                "name": "include_accessibility_tree",
                "type": "boolean",
                "description": (
                    "Capture the page's accessibility tree as well. Large, so "
                    "off unless something actually needs it."
                ),
                "default": False,
            },
            {
                "name": "include_available_actions",
                "type": "boolean",
                "description": (
                    "Capture the interactive affordances the page currently "
                    "offers. Off by default for the same size reason."
                ),
                "default": False,
            },
        ]

    def output_parameters(self) -> list[dict[str, Any]] | None:
        """The observation fields a later step may bind to.

        `run()` returns `observation.as_dict()`, which carries more than
        this -- viewport, an optional accessibility tree, the affordance
        list. Publishing a field is a promise that a plan may depend on
        it, so only what is structurally guaranteed appears here.

        `url` and `title` are what a browser always has.

        `elements` is guaranteed too, which is why it is published now and
        was not before. The earlier reading -- "elements depends on
        selectors the caller passed" -- confused the list's CONTENTS with
        its PRESENCE. `BrowserObservation.as_dict()` always emits the key,
        `_observe_elements()` appends exactly one entry per requested
        selector in the order requested and skips none, and a selector
        matching nothing still yields an entry saying so. So a plan that
        asks for one selector may depend on `elements.0` existing; what it
        must not assume is that the element was found.

        Still *known* rather than *closed*: this does not claim to
        enumerate the whole output, only that these fields are real.
        """
        return [
            {
                "name": "url",
                "type": "string",
                "description": "The page's current URL as the browser reports it.",
            },
            {
                "name": "title",
                "type": "string",
                "description": "The page's current title as the browser reports it.",
            },
            {
                "name": "elements",
                "type": "array",
                "description": (
                    "One entry per requested selector, in the order requested: "
                    "`selector` (the selector as asked for), `is_visible`, "
                    "`text` (the element's text, or null), and `tag_name`. "
                    "Empty when no selectors were requested."
                ),
            },
        ]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not (parameters.get("session_id") or "").strip():
            errors.append("missing required parameter: session_id")

        selectors = parameters.get("selectors", [])
        if not isinstance(selectors, list) or not all(isinstance(s, str) for s in selectors):
            errors.append("'selectors' must be a list of strings if provided")

        for flag in ("include_accessibility_tree", "include_available_actions"):
            if not isinstance(parameters.get(flag, False), bool):
                errors.append(f"'{flag}' must be a boolean if provided")

        return errors

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        try:
            session = self._sessions.get(parameters["session_id"].strip())
        except BrowserSessionError as exc:
            return ExecutionResult(success=False, errors=[str(exc)])

        try:
            observation = normalize_observation(
                session.page,
                parameters.get("selectors", []),
                include_accessibility_tree=parameters.get("include_accessibility_tree", False),
                include_available_actions=parameters.get("include_available_actions", False),
            )
        except Exception as exc:  # noqa: BLE001 — mechanical failure, e.g. session closed mid-call
            return ExecutionResult(success=False, errors=[f"observation failed: {exc}"])

        return ExecutionResult(success=True, output=observation.as_dict())
