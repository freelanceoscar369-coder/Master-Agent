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
    (mission_service, runtime, mission_control, status, reasoning_runner,
     set_mode, interactions) = pipeline
    assert type(mission_service).__name__ == "MissionService"
    assert type(runtime).__name__ == "RuntimeEngine"
    assert type(mission_control).__name__ == "MissionControl"
    assert type(status).__name__ == "ExecutionStatus"
    # The Brain's one door to reasoning, returned as well as handed to the
    # Planner -- planning is only one of the things the Brain reasons
    # about, and `brain/advisory.py` must reuse this exact instance rather
    # than build a ladder of its own. See test_brain_non_execution_routing.
    assert type(reasoning_runner).__name__ == "TieredPromptRunner"
    # The founder's LOCAL / AI MODE / BOTH switch, returned so the
    # surface can set it and the Planner can read it -- one cell, not
    # a second copy of the mode on either side.
    assert callable(set_mode)
    # ADR-0025's interaction log, so the surface can record both sides.
    assert interactions is not None


def test_browser_capabilities_are_discovered(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-construction-test")
    _, _, mission_control, _, _, _, _ = kd._build_mission_pipeline()
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
    mission_service, _, _, _, _, _, _ = kd._build_mission_pipeline()
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
    """Stands in for `MissionService` at the admission boundary.

    Carries a REAL `IntentLayer`, because the production surface now
    resolves intent through `mission_service.intent_layer` before calling
    `start()` (ADR-0024 Decision 1). A double with a stubbed parser would
    let a test pass while the real boundary was broken, and `IntentLayer`
    is pure -- no clock, no I/O, no model -- so using the real one costs
    nothing and keeps the double honest.

    `started_with` records what `start()` received: `None` means it was
    never called, which is what ADR-0024 §10 requires for a
    clarification-required Intent.
    """

    def __init__(self, outcome, intent_layer=None):
        from master_agent.brain.intent import IntentLayer

        self._outcome = outcome
        self.started_with = None
        self.intent_layer = intent_layer if intent_layer is not None else IntentLayer()

    def start(self, objective, **kwargs):
        # `objective` is a canonical `Intent` on the production path now,
        # not raw text. Recorded verbatim so a test can assert exactly what
        # crossed the boundary.
        self.started_with = objective
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


class TestCapabilityDomainsAreFounderSafe:
    """The composition root's half of the Brain/Operator boundary.

    `_describe_capabilities` used to render every capability *verb* in
    the registry as the founder's answer. It is now
    `_capability_domains`, which returns founder-level DOMAINS and hands
    them to the Conversation Engine to compose -- the composition root no
    longer produces founder-facing prose at all.
    """

    def test_it_returns_domains_not_execution_verbs(self):
        from kalpavriksha_desktop import _capability_domains

        domains = _capability_domains(_mission_control_with(
            ("browser", "click"), ("browser", "open_browser_session"),
            ("browser", "navigate"), ("browser", "type_text"),
            ("desktop", "launch_application"), ("desktop", "focus_window"),
            ("desktop", "execute_command"), ("desktop", "is_installed"),
        ))
        joined = " ".join(domains).lower()
        leaked = [v for v in _INTERNAL_VOCABULARY if v in joined]
        assert leaked == [], f"operator vocabulary reached the founder: {leaked}"
        assert any("browser" in d for d in domains)
        assert any("desktop" in d for d in domains)

    def test_it_tracks_the_live_registry(self):
        from kalpavriksha_desktop import _capability_domains

        one = _capability_domains(_mission_control_with(("browser", "click")))
        two = _capability_domains(
            _mission_control_with(("browser", "click"), ("desktop", "focus_window"))
        )
        assert len(one) == 1
        assert len(two) == 2

    def test_an_unknown_executive_is_omitted_not_invented(self):
        from kalpavriksha_desktop import _capability_domains

        domains = _capability_domains(
            _mission_control_with(("browser", "click"), ("quantum", "entangle"))
        )
        joined = " ".join(domains).lower()
        assert "quantum" not in joined
        assert "entangle" not in joined
        assert len(domains) == 1

    def test_an_empty_registry_yields_no_domains(self):
        from kalpavriksha_desktop import _capability_domains

        assert _capability_domains(_mission_control_with()) == []

    def test_an_unreadable_registry_yields_no_domains(self):
        from kalpavriksha_desktop import _capability_domains

        class _Boom:
            @property
            def capabilities(self):
                raise RuntimeError("registry unavailable")

        assert _capability_domains(_Boom()) == []


class TestCompositionRootNoLongerRoutesConversation:
    """The capability shortcut is gone from the composition root.

    It was a phrase list consulted before the Conversation Engine, which
    put the routing decision in the wrong layer and matched by contiguous
    substring. Intent now belongs to the Brain.
    """

    def test_the_composition_root_holds_no_capability_phrase_list(self):
        import kalpavriksha_desktop as root

        assert not hasattr(root, "_describe_capabilities"), (
            "the composition root must not compose founder-facing capability prose"
        )

    def test_the_capability_shortcut_is_not_in_the_objective_path(self):
        import inspect

        from kalpavriksha_desktop import _submit_objective

        source = inspect.getsource(_submit_objective)
        assert "is_capability_question" not in source, (
            "capability routing belongs to the Conversation Engine, not here"
        )


class TestClarificationReachesTheFounder:
    """Defect C: a clarification question was destroyed before it was asked.

    The Intent Layer produces a real `ClarificationQuestion` for an
    ambiguous objective. That question used to travel to the founder
    wrapped in `PlanRefusal(code="CLARIFICATION_REQUIRED")` -- a question
    disguised as a planning failure -- and the composition root flattened
    every refusal through `_founder_refusal_sentence()`, which has no
    branch for that code, so the founder was told "I couldn't plan that
    just now. Please try again." -- ending the exchange instead of
    continuing it.

    ADR-0024 Decision 1 removed the disguise: intent is resolved BEFORE
    a mission exists, so an under-specified request never becomes one and
    the question is asked directly. These tests now drive the real
    `IntentLayer` rather than a fabricated refusal, which is a stronger
    check -- the question has to be genuinely produced, not stubbed.
    """

    class _Outcome:
        accepted = False
        refusal = None
        reasons = ()

    def _submit(self, outcome, text="create folder"):
        """Drive `_submit_objective` with a stubbed mission service that
        carries a real Intent Layer."""
        from master_agent.brain.intent import IntentLayer
        from master_agent.missions.execution_status import ExecutionStatus
        from kalpavriksha_desktop import _submit_objective

        class _MS:
            intent_layer = IntentLayer()
            started = False

            def start(self, objective, **kwargs):
                type(self).started = True
                return outcome

        service = _MS()
        status = ExecutionStatus()
        result = _submit_objective(service, None, _mission_control_with(), status, text)
        return result, service

    def test_the_actual_question_is_asked_verbatim(self):
        result, service = self._submit(self._Outcome())
        assert result["reply"] == "What should the folder be called?"
        assert not service.started, (
            "an under-specified request became a mission -- ADR-0024 §10 "
            "requires MissionService and Planner to be untouched"
        )

    def test_it_is_not_flattened_into_the_generic_refusal(self):
        reply = self._submit(self._Outcome())[0]["reply"]
        assert reply != "I couldn't plan that just now. Please try again."
        assert "couldn't plan" not in reply

    def test_an_ordinary_refusal_is_still_explained_as_a_refusal(self):
        """Clarification must not swallow genuine refusals. This objective
        IS understood, so it passes admission and the refusal it meets is
        a real planning refusal."""
        class _Plain:
            code = "NOT_EXECUTABLE"
            reason = "the available capabilities cannot achieve this objective"
            detail = None

        outcome = self._Outcome()
        outcome.refusal = _Plain()
        result, service = self._submit(outcome, text="Open github.com")
        assert service.started, "an understood objective never reached MissionService"
        assert result["reply"] == "I can't do that with what I'm currently able to do."
