"""Golden path — real visible Chrome, and capability-question routing.

Two launch-critical Founder requirements, each proven against the real
shipped classes:

1. "Open Chrome" must drive the founder's *installed, visible* Google
   Chrome — not a bundled headless renderer. A headless session must
   **fail** this acceptance, which is the assertion the previous (wrong)
   "browser mission PASS" never made.
2. "What can you do right now?" must be answered from the live capability
   registry and must never become an executable mission.

No real browser is launched here (the Playwright launcher is the injected
seam); the real-Chrome proof is the installed-runtime test.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kalpavriksha_desktop as kd  # noqa: E402

from master_agent.brain import IntentLayer  # noqa: E402
from master_agent.planner.plan import Intent  # noqa: E402
from master_agent.environment import browser_session as bs  # noqa: E402
from master_agent.environment.browser_session import BrowserSessionManager  # noqa: E402
from master_agent.executor.actions.browser.open_session import (  # noqa: E402
    OpenBrowserSessionAction,
)
from master_agent.missions.execution_status import COMPLETED, ExecutionStatus  # noqa: E402
from tests.test_kalpavriksha_desktop_mission_bridge import (  # noqa: E402
    _FakeFounderState,
    _FakeMissionControl,
    _FakeMissionService,
    _FakeObjective,
    _FakeOutcome,
    _FakeRuntime,
)


# ---- fakes for the Playwright seam ---------------------------------------


class FakePage:
    def __init__(self) -> None:
        self.url = "https://example.com/"

    def title(self) -> str:
        return "Example Domain"

    def close(self) -> None:
        pass


class FakeContext:
    def __init__(self) -> None:
        self.pages: list[FakePage] = []

    def new_page(self) -> FakePage:
        page = FakePage()
        self.pages.append(page)
        return page

    def close(self) -> None:
        pass


class FakeBrowser:
    def __init__(self, headless: bool, channel: str | None) -> None:
        self.headless = headless
        self.channel = channel

    def new_context(self) -> FakeContext:
        return FakeContext()

    def close(self) -> None:
        pass


class FakeChromium:
    def __init__(self) -> None:
        self.launches: list[dict] = []

    def launch(self, **kwargs):
        self.launches.append(dict(kwargs))
        return FakeBrowser(kwargs.get("headless", True), kwargs.get("channel"))


class FakePlaywright:
    def __init__(self) -> None:
        self.chromium = FakeChromium()
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


@pytest.fixture
def playwright(monkeypatch):
    fake = FakePlaywright()
    monkeypatch.setattr(bs, "sync_playwright", lambda: type("S", (), {"start": lambda _s: fake})())
    return fake


# ---- 1. visible Chrome ----------------------------------------------------


def test_the_founder_edition_default_is_the_installed_visible_chrome(playwright):
    """The composition root's own policy, proven at the session manager
    rather than by reading the composition root."""
    manager = BrowserSessionManager(default_headless=False, default_channel="chrome")
    handle = manager.open_session("s1")

    launch = playwright.chromium.launches[-1]
    assert launch["headless"] is False, "a founder-visible session must not be headless"
    assert launch["channel"] == "chrome", (
        "a founder-visible session must drive the installed Google Chrome, "
        "not the bundled Chromium build"
    )
    assert handle.headless is False
    assert handle.channel == "chrome"


def test_a_headless_session_fails_the_visible_chrome_acceptance(playwright):
    """The assertion the previous, invalidated 'PASS' never made: a
    headless run must be *detectably* not founder-visible."""
    manager = BrowserSessionManager()  # library defaults, unchanged
    handle = manager.open_session("s1")

    launch = playwright.chromium.launches[-1]
    assert launch["headless"] is True
    assert launch.get("channel") is None

    # The acceptance predicate itself:
    is_founder_visible = (handle.headless is False) and (handle.channel == "chrome")
    assert not is_founder_visible, "a headless bundled session must FAIL visible-Chrome acceptance"


def test_existing_library_defaults_are_unchanged(playwright):
    """Every non-Founder-Edition caller keeps the old behaviour, so this
    change cannot silently turn every other consumer headed."""
    manager = BrowserSessionManager()
    manager.open_session("s1")
    assert playwright.chromium.launches[-1] == {"headless": True}


def test_an_explicit_plan_value_still_wins_over_the_founder_default(playwright):
    """Defaults, not overrides — the Planner can still ask for an
    invisible session when an objective genuinely does not want a window."""
    manager = BrowserSessionManager(default_headless=False, default_channel="chrome")
    manager.open_session("s1", headless=True, channel=None)
    assert playwright.chromium.launches[-1]["headless"] is True


def test_the_action_publishes_both_visibility_parameters_to_the_planner():
    """Without publication the Planner cannot express the requirement at
    all — the original root cause."""
    action = OpenBrowserSessionAction(sessions=None)
    published = {item["name"] for item in action.optional_parameters() or []}
    assert {"headless", "channel"} <= published


def test_the_action_passes_channel_through_to_the_session(playwright):
    manager = BrowserSessionManager()
    action = OpenBrowserSessionAction(manager)

    result = action.run({"session_id": "s1", "headless": False, "channel": "chrome"})

    assert result.success
    assert result.output["channel"] == "chrome"
    assert result.output["headless"] is False
    assert playwright.chromium.launches[-1]["channel"] == "chrome"


def test_channel_is_validated_as_a_string():
    action = OpenBrowserSessionAction(sessions=None)
    assert action.validate({"session_id": "s1", "channel": 123})
    assert not action.validate({"session_id": "s1", "channel": "chrome"})


def test_dom_observation_still_works_on_a_visible_session(playwright):
    """Driving the installed Chrome must not cost DOM control — that is
    the whole reason this uses Playwright's channel rather than launching
    chrome.exe separately."""
    manager = BrowserSessionManager(default_headless=False, default_channel="chrome")
    manager.open_session("s1")
    page = manager.get("s1").page

    assert page.title() == "Example Domain"
    assert page.url == "https://example.com/"


# ---- 2. capability-question routing ---------------------------------------


@pytest.mark.parametrize(
    "question",
    [
        "What can you do right now?",
        "what all can you do",
        "I want to know what all you can do right now.",
        "what are your capabilities",
        "Tell me your capabilities",
        "What are you capable of?",
    ],
)
def test_capability_questions_are_recognised_by_the_existing_intent_layer(question):
    assert IntentLayer().is_capability_question(question)


@pytest.mark.parametrize(
    "objective",
    [
        "Open Chrome, navigate to https://example.com/, verify the page title.",
        "create a folder called demo",
        "Hello, are you there?",
        "what is two plus two",
    ],
)
def test_ordinary_input_is_not_mistaken_for_a_capability_question(objective):
    assert not IntentLayer().is_capability_question(objective)


def test_capability_questions_are_classified_by_the_brain():
    """UPDATED: capability routing moved out of the composition root.

    These three tests previously asserted a shortcut inside
    `_submit_objective` that recognised capability questions by phrase and
    answered them from `_describe_capabilities`. That shortcut was the
    defect: it put the routing decision in the composition root, matched
    by contiguous substring (so "what are your *current* capabilities"
    fell through to the Planner), and rendered the Operator's own verbs
    into the founder's answer. Capability questions are now
    `Intent.CAPABILITY_QUERY` in the Conversation Engine's taxonomy and
    never reach this module at all.
    """
    from master_agent.conversation_engine.intent import Intent, IntentClassifier

    classifier = IntentClassifier()
    for text in (
        "What can you do right now?",
        "What are your current capabilities?",
        "What can you actually do on this computer?",
    ):
        assert classifier.classify(text) is Intent.CAPABILITY_QUERY, text


def test_the_capability_domains_come_from_the_live_registry():
    """The registry is still the source of truth -- but it yields DOMAINS.

    This test used to assert `"navigate"` and `"create folder"` appeared
    in the founder's answer. Those are Operator execution primitives, and
    requiring them in founder-facing text is the leak the Brain/Operator
    separation exists to prevent, so the assertion is inverted here.
    """
    class _Caps:
        def all(self):
            return [
                type("D", (), {"executive_id": "browser", "capability": "navigate"})(),
                type("D", (), {"executive_id": "desktop", "capability": "focus_window"})(),
            ]

    mission_control = _FakeMissionControl([_FakeObjective()], _FakeFounderState())
    mission_control.capabilities = _Caps()

    domains = kd._capability_domains(mission_control)
    joined = " ".join(domains).lower()

    # Derived from the live registry, not a hardcoded list.
    assert any("browser" in d for d in domains)
    assert any("desktop" in d for d in domains)
    # ...and carrying none of the Operator's own vocabulary.
    for primitive in ("navigate", "focus_window", "focus window", "execute_command"):
        assert primitive not in joined, primitive


def test_an_empty_registry_is_reported_honestly():
    class _Caps:
        def all(self):
            return []

    mission_control = _FakeMissionControl([_FakeObjective()], _FakeFounderState())
    mission_control.capabilities = _Caps()

    assert kd._capability_domains(mission_control) == []


def test_an_executable_objective_still_reaches_mission_service():
    """The routing fix must not swallow real work."""
    mission_service = _FakeMissionService(_FakeOutcome(accepted=True, objective_id="obj-1"))
    mission_service.intent_layer = IntentLayer()
    runtime = _FakeRuntime()
    mission_control = _FakeMissionControl(
        [_FakeObjective(complete=True)],
        _FakeFounderState(progress=1.0, result="done"),
    )

    kd._submit_objective(
        mission_service, runtime, mission_control, ExecutionStatus(),
        "Open Chrome and go to https://example.com/",
    )

    # ADR-0024 Decision 1: what crosses this boundary is a canonical
    # `Intent`, not the raw sentence. The founder's wording survives as
    # provenance in `context["raw_input"]`, which is where anything that
    # wants the original words should read it from -- nothing downstream
    # derives *meaning* from it any more.
    handed_over = mission_service.started_with
    assert isinstance(handed_over, Intent), (
        f"MissionService received {type(handed_over).__name__}, not an Intent"
    )
    assert handed_over.goal == "Open Chrome and go to https://example.com/"
    assert handed_over.context["raw_input"] == "Open Chrome and go to https://example.com/"
