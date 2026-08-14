"""Founder Task 2 — the minimal Planner -> Broker -> Gemini -> MissionPlan
-> Mission Control -> Browser Executive composition root
`kalpavriksha_desktop.py` builds for `desktop_shell.py`'s injected
`submit_objective` callable.

Everything here runs against fakes — no real Gemini call, no real
browser. The real-API/real-browser proof is a founder-facing run
recorded separately, the same split every other provider test file in
this project already uses.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kalpavriksha_desktop as kd  # noqa: E402
from master_agent.missions.execution_status import ExecutionStatus  # noqa: E402


# ---- _build_mission_pipeline() -------------------------------------------


def test_returns_none_without_an_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert kd._build_mission_pipeline() is None


def test_builds_the_full_pipeline_with_a_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-construction-test")
    pipeline = kd._build_mission_pipeline()
    assert pipeline is not None
    mission_service, runtime, mission_control, status = pipeline
    assert type(mission_service).__name__ == "MissionService"
    assert type(runtime).__name__ == "RuntimeEngine"
    assert type(mission_control).__name__ == "MissionControl"
    assert type(status).__name__ == "ExecutionStatus"


def test_browser_capabilities_are_discovered(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-construction-test")
    _, _, mission_control, _ = kd._build_mission_pipeline()
    names = {c.qualified_name for c in mission_control.capabilities.all()}
    assert "Browser.Navigate" in names
    assert "Browser.ObserveBrowser" in names


def test_no_ollama_provider_is_ever_registered(monkeypatch):
    """Founder RAM constraint, repeated across every Gemini mission this
    session — proven here at the one new assembly point that could have
    silently reintroduced it.

    `planner._runner` is a `TieredPromptRunner` (Corrected Fallback
    Ladder) wrapping the real `PromptExecutor` as `._executor` — the same
    `PluginRegistry` this test always checked, reached through the one
    new, sanctioned layer between `Planner` and it."""
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-construction-test")
    mission_service, _, _, _ = kd._build_mission_pipeline()
    provider_ids = {p.provider_id for p in mission_service.planner._runner._executor._providers.all_plugins()}
    assert "ollama.local" not in provider_ids
    assert provider_ids == {
        "gemini.api", "claude-desktop", "chatgpt-desktop",
        "perplexity-desktop", "kimi-desktop", "browser.free-ai",
    }


# ---- _submit_objective() --------------------------------------------------


class _FakeRefusal:
    def __init__(self, reason):
        self.reason = reason


class _FakeOutcome:
    def __init__(self, accepted, objective_id=None, refusal=None, reasons=()):
        self.accepted = accepted
        self.objective_id = objective_id
        self.refusal = refusal
        self.reasons = reasons


class _FakeMissionService:
    def __init__(self, outcome):
        self._outcome = outcome
        self.started_with = None

    def start(self, text):
        self.started_with = text
        return self._outcome


class _FakeObjective:
    def __init__(self, complete=False, failed=False):
        self.is_complete = complete
        self.has_failure = failed


class _FakeDispatcher:
    def __init__(self, objectives_in_order):
        self._objectives = list(objectives_in_order)

    def objective(self, objective_id):
        if len(self._objectives) > 1:
            return self._objectives.pop(0)
        return self._objectives[0]


class _FakeFounderState:
    def __init__(self, progress=1.0, result="Done for real.", errors=()):
        self.progress = progress
        self.result = result
        self.errors = list(errors)


class _FakeMissionControl:
    def __init__(self, objectives_in_order, state):
        self.dispatcher = _FakeDispatcher(objectives_in_order)
        self._state = state

    def founder_state(self, objective_id):
        return self._state


class _FakeRuntime:
    def __init__(self):
        self.run_once_calls = 0

    def run_once(self):
        self.run_once_calls += 1


def test_a_refused_plan_never_touches_the_runtime():
    mission_service = _FakeMissionService(
        _FakeOutcome(accepted=False, refusal=_FakeRefusal("no eligible provider"))
    )
    runtime = _FakeRuntime()
    mission_control = _FakeMissionControl([_FakeObjective()], _FakeFounderState())

    status = ExecutionStatus()
    result = kd._submit_objective(
        mission_service, runtime, mission_control, status, "do something"
    )

    # The founder gets a clean sentence, never the provider's own words —
    # the developer diagnostic stays on `status.errors`. See
    # `test_launch_rescue_provider_hygiene.py` for the full hygiene rules.
    assert "no eligible provider" not in result["reply"]
    assert result["reply"]
    assert any("no eligible provider" in err for err in status.errors)
    assert runtime.run_once_calls == 0


def test_an_accepted_objective_runs_until_complete_and_reports_the_result():
    mission_service = _FakeMissionService(_FakeOutcome(accepted=True, objective_id="obj-1"))
    runtime = _FakeRuntime()
    mission_control = _FakeMissionControl(
        [_FakeObjective(complete=False), _FakeObjective(complete=True)],
        _FakeFounderState(progress=1.0, result="example.com loaded; title matched."),
    )

    result = kd._submit_objective(
        mission_service, runtime, mission_control, ExecutionStatus(), "open chrome"
    )

    assert result == {"reply": "example.com loaded; title matched."}
    assert runtime.run_once_calls >= 1


def test_a_failed_objective_reports_the_errors():
    mission_service = _FakeMissionService(_FakeOutcome(accepted=True, objective_id="obj-2"))
    runtime = _FakeRuntime()
    mission_control = _FakeMissionControl(
        [_FakeObjective(failed=True)],
        _FakeFounderState(progress=0.0, result=None, errors=["selector not found"]),
    )

    result = kd._submit_objective(
        mission_service, runtime, mission_control, ExecutionStatus(), "open chrome"
    )

    # Same hygiene rule as the refusal path: the founder is told the task
    # did not complete, not handed the executive's raw error string.
    assert "selector not found" not in result["reply"]
    assert "didn't complete" in result["reply"] or "review" in result["reply"]


def test_a_browser_observation_result_gets_a_readable_sentence():
    """The exact shape `Browser.ObserveBrowser` returns — a raw
    url/title dict must never reach the founder as a Python repr."""
    mission_service = _FakeMissionService(_FakeOutcome(accepted=True, objective_id="obj-4"))
    runtime = _FakeRuntime()
    mission_control = _FakeMissionControl(
        [_FakeObjective(complete=True)],
        _FakeFounderState(
            progress=1.0,
            result={"url": "https://example.com/", "title": "Example Domain"},
        ),
    )

    result = kd._submit_objective(
        mission_service, runtime, mission_control, ExecutionStatus(), "open chrome"
    )

    assert result["reply"] == (
        'Done — the page at https://example.com/ loaded with title "Example Domain".'
    )
    assert "{" not in result["reply"]


def test_a_non_browser_result_falls_back_to_its_own_string_form():
    mission_service = _FakeMissionService(_FakeOutcome(accepted=True, objective_id="obj-5"))
    runtime = _FakeRuntime()
    mission_control = _FakeMissionControl(
        [_FakeObjective(complete=True)],
        _FakeFounderState(progress=1.0, result=42),
    )

    result = kd._submit_objective(
        mission_service, runtime, mission_control, ExecutionStatus(), "count something"
    )

    assert result == {"reply": "42"}


def test_a_timeout_reports_honestly_rather_than_a_fabricated_success():
    mission_service = _FakeMissionService(_FakeOutcome(accepted=True, objective_id="obj-3"))
    runtime = _FakeRuntime()
    # Never reaches a terminal state within the loop.
    mission_control = _FakeMissionControl(
        [_FakeObjective(complete=False)],
        _FakeFounderState(progress=0.4, result=None, errors=[]),
    )

    result = kd._submit_objective(
        mission_service, runtime, mission_control, ExecutionStatus(), "open chrome",
        timeout_seconds=0.01,
    )

    assert "longer than expected" in result["reply"]


# ═════════ the Brain/Operator boundary at the Founder Surface ════════════
# This is the boundary the shipped app actually crossed. Asked "what can
# you do right now?", it answered with the Operator's own execution
# vocabulary — "browser.click, close browser session, navigate, press key,
# scroll, type text, execute command, find target, focus window, is
# installed, launch application" — because `_describe_capabilities` walked
# the capability registry and rendered every verb. The executor had become
# the conversational personality.
#
# Nothing caught it: this module is the composition root, and no test
# asserted anything about what a founder is *told*, only about what gets
# executed. That is the gap these tests close.
class _Descriptor:
    def __init__(self, executive_id: str, capability: str) -> None:
        self.executive_id = executive_id
        self.capability = capability


def _mission_control_with(*pairs):
    class _Caps:
        def all(self):
            return [_Descriptor(e, c) for e, c in pairs]

    class _MC:
        capabilities = _Caps()

    return _MC()


#: Verbatim fragments of the Operator's own vocabulary. None may ever
#: appear in a sentence shown to the founder.
_INTERNAL_VOCABULARY = (
    "browser.click", "click", "open_browser_session", "close_browser_session",
    "navigate", "press_key", "press key", "scroll", "type_text", "type text",
    "execute_command", "execute command", "find_target", "find target",
    "focus_window", "focus window", "is_installed", "is installed",
    "is_running", "is running", "launch_application", "launch application",
    "get_version", "get version", "observe_browser", "list_running_processes",
)


class TestCapabilityAnswerNeverLeaksOperatorVocabulary:
    def test_no_execution_primitive_reaches_the_founder(self):
        from kalpavriksha_desktop import _describe_capabilities

        reply = _describe_capabilities(_mission_control_with(
            ("browser", "click"), ("browser", "open_browser_session"),
            ("browser", "navigate"), ("browser", "type_text"),
            ("desktop", "launch_application"), ("desktop", "focus_window"),
            ("desktop", "execute_command"), ("desktop", "is_installed"),
        ))
        lowered = reply.lower()
        leaked = [v for v in _INTERNAL_VOCABULARY if v in lowered]
        assert leaked == [], f"operator vocabulary reached the founder: {leaked}"

    def test_it_still_describes_what_is_actually_registered(self):
        """Honest, not merely quiet: the answer must reflect the live
        registry rather than becoming a fixed marketing sentence."""
        from kalpavriksha_desktop import _describe_capabilities

        browser_only = _describe_capabilities(_mission_control_with(("browser", "click")))
        both = _describe_capabilities(
            _mission_control_with(("browser", "click"), ("desktop", "focus_window"))
        )
        assert "browser" in browser_only.lower()
        assert "desktop" not in browser_only.lower()
        assert "desktop" in both.lower()

    def test_an_unknown_executive_is_counted_not_described(self):
        """Adding an executive without a founder-facing description must
        degrade honestly rather than invent one for it."""
        from kalpavriksha_desktop import _describe_capabilities

        reply = _describe_capabilities(
            _mission_control_with(("browser", "click"), ("quantum", "entangle"))
        )
        assert "quantum" not in reply.lower()
        assert "entangle" not in reply.lower()
        assert "other area" in reply.lower()

    def test_an_empty_registry_admits_it_cannot_act(self):
        from kalpavriksha_desktop import _describe_capabilities

        reply = _describe_capabilities(_mission_control_with())
        assert "conversation" in reply.lower()
        assert "act" in reply.lower()
