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
    silently reintroduced it."""
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-construction-test")
    mission_service, _, _, _ = kd._build_mission_pipeline()
    provider_ids = {p.provider_id for p in mission_service.planner._runner._providers.all_plugins()}
    assert "ollama.local" not in provider_ids
    assert provider_ids == {"gemini.api"}


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

    result = kd._submit_objective(
        mission_service, runtime, mission_control, ExecutionStatus(), "do something"
    )

    assert "no eligible provider" in result["reply"]
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

    assert "selector not found" in result["reply"]


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
