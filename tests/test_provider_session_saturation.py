"""A provider's conversation can wear out while the provider is fine.

The founder watched this happen. Kimi Desktop was displaying

    Your conversation with Kimi is getting too long.
    Try starting a new session.

and Kalpavriksha kept sending requests into that same conversation. The
answers that came back were then read as evidence about the Brain --
fixtures D, D2 and E were failing and the failures looked like reasoning
variance. They were transport health.

The distinction this file exists to hold:

    PROVIDER HEALTH          is Kimi installed, launchable, answering
    PROVIDER SESSION HEALTH  is THIS conversation still fit to use

They are not the same, and only the second one was wrong. Nothing here
ever excludes Kimi as a provider; a saturated conversation is retired and
a fresh one is opened, because a provider conversation carries transport
continuity and never Founder meaning -- Intent, requirements, Evidence
and MissionProgress are the authoritative state, which is exactly why
starting over in the application is safe.
"""
from __future__ import annotations

import types

from master_agent.ai_infrastructure.catalog import PROVIDER_CATALOG
from master_agent.desktop.actions import DesktopContext
from master_agent.providers import desktop_app as mod
from master_agent.providers.desktop_app import DesktopAppReasoningProvider
from master_agent.providers.reasoning_session import (
    DEDICATED_SESSION_NAME,
    NEW_SESSION_VOCABULARY,
    SESSION_SATURATED,
    SESSION_SATURATION_VOCABULARY,
    ReasoningSessionManager,
    SessionHealth,
)
from master_agent.providers.response import SUCCEEDED, UNAVAILABLE
from tests.test_reasoning_session_manager import FakeKeyboard, FakeMouse, FakeUiaBridge

#: The founder's own observation, verbatim, as two separate lines --
#: because that is how a real window renders it, and matching it must not
#: depend on both sentences arriving in one element.
FOUNDER_WARNING = "Your conversation with Kimi is getting too long."
FOUNDER_ADVICE = "Try starting a new session."

WINDOW = {"handle": 7}


def _saturated_bridge(**kwargs):
    return FakeUiaBridge(
        existing_sessions={DEDICATED_SESSION_NAME: object()},
        window_text=("earlier turn", FOUNDER_WARNING, FOUNDER_ADVICE),
        **kwargs,
    )


class TestTheWarningIsObserved:
    def test_the_founders_own_warning_is_detected(self):
        manager = ReasoningSessionManager(_saturated_bridge(), FakeMouse())

        health = manager.inspect_session(handle=7)

        assert health.saturated is True
        assert health.warning == FOUNDER_WARNING
        assert health.usable is False

    def test_the_advice_sentence_alone_is_not_a_warning(self):
        """"Try starting a new session" is what the New-chat button says.

        If that half alone counted, every healthy window would be read as
        saturated -- which is why the vocabulary names the CONVERSATION'S
        OWN LENGTH and nothing else."""
        bridge = FakeUiaBridge(window_text=(FOUNDER_ADVICE, "New chat", "Start a new conversation"))
        manager = ReasoningSessionManager(bridge, FakeMouse())

        assert manager.inspect_session(handle=7).saturated is False

    def test_no_new_session_control_name_is_itself_a_saturation_phrase(self):
        """A structural guard, not a scenario: the two vocabularies must
        never overlap, or finding the button would mean condemning the
        conversation."""
        for control in NEW_SESSION_VOCABULARY:
            for phrase in SESSION_SATURATION_VOCABULARY:
                assert phrase not in control

    def test_an_unreadable_window_claims_nothing_either_way(self):
        """Not observed is not ill. The write/submit/read path verifies
        each of its own steps and does not need this to have succeeded --
        so an unreadable window must not become a refusal to work."""
        bridge = FakeUiaBridge(window_text=())
        manager = ReasoningSessionManager(bridge, FakeMouse())

        health = manager.inspect_session(handle=7)

        assert health.observed is False
        assert health.saturated is False
        assert health.usable is True

    def test_a_healthy_conversation_reads_as_healthy(self):
        bridge = FakeUiaBridge(window_text=("Hello.", "Here is the answer."))

        health = ReasoningSessionManager(bridge, FakeMouse()).inspect_session(handle=7)

        assert (health.saturated, health.stale_attachment, health.observed) == (False, False, True)


class TestTheSaturatedSessionIsNotReused:
    def test_a_healthy_named_session_is_reused_with_no_rotation(self):
        bridge = FakeUiaBridge(existing_sessions={DEDICATED_SESSION_NAME: object()})
        manager = ReasoningSessionManager(bridge, FakeMouse())

        result = manager.establish(WINDOW, "Kimi Desktop", FakeKeyboard())

        assert (result.ok, result.reused, result.rotated) == (True, True, False)
        assert bridge.new_session_element not in bridge.clicked_elements

    def test_the_warning_retires_the_conversation_and_opens_a_fresh_one(self):
        bridge = _saturated_bridge()
        manager = ReasoningSessionManager(bridge, FakeMouse())

        # The fresh conversation the application creates shows no warning.
        real_click = bridge.click

        def click(element, mouse):
            if element is bridge.new_session_element:
                bridge.window_text[:] = []
            return real_click(element, mouse)

        bridge.click = click

        result = manager.establish(WINDOW, "Kimi Desktop", FakeKeyboard())

        assert result.ok is True
        assert result.rotated is True
        assert result.reused is False
        assert result.health.saturated is False
        assert bridge.new_session_element in bridge.clicked_elements
        assert manager.is_retired("Kimi Desktop") is True

    def test_the_retired_conversation_is_never_looked_up_again(self):
        """Otherwise the next call finds the same saturated conversation
        by name and walks straight back into it."""
        bridge = _saturated_bridge()
        manager = ReasoningSessionManager(bridge, FakeMouse())
        manager.retire("Kimi Desktop")
        bridge.find_calls.clear()

        manager.establish(WINDOW, "Kimi Desktop", FakeKeyboard())

        assert DEDICATED_SESSION_NAME not in bridge.find_calls

    def test_retirement_is_about_one_application_not_all_of_them(self):
        manager = ReasoningSessionManager(FakeUiaBridge(), FakeMouse())
        manager.retire("Kimi Desktop")

        assert manager.is_retired("Kimi Desktop") is True
        assert manager.is_retired("ChatGPT Desktop") is False

    def test_a_rotation_does_not_leave_two_conversations_with_one_name(self):
        """`find_named_session()` matches an exact name. Naming the
        replacement the same thing as the conversation just retired would
        make that match ambiguous -- the single failure the exact-match
        rule exists to prevent."""
        bridge = _saturated_bridge(rename_action_available=True)
        manager = ReasoningSessionManager(bridge, FakeMouse())
        real_click = bridge.click

        def click(element, mouse):
            if element is bridge.new_session_element:
                bridge.window_text[:] = []
            return real_click(element, mouse)

        bridge.click = click

        result = manager.establish(WINDOW, "Kimi Desktop", FakeKeyboard())

        assert result.rotated is True
        assert result.renamed is False
        assert [name for _, name in bridge.written] == []


class TestRotationIsBounded:
    def test_a_fresh_conversation_that_is_still_saturated_fails_closed(self):
        """One governed establishment, then the ladder's problem. Clicking
        New chat until something looks right is how an adapter fills a
        founder's sidebar."""
        bridge = _saturated_bridge()
        manager = ReasoningSessionManager(bridge, FakeMouse())

        result = manager.establish(WINDOW, "Kimi Desktop", FakeKeyboard())

        assert result.ok is False
        assert result.reason.startswith(SESSION_SATURATED)
        assert bridge.clicked_elements.count(bridge.new_session_element) == 1

    def test_a_brand_new_conversation_that_is_unusable_is_not_replaced_again(self):
        """Nothing was reused, so there is nothing to rotate away from --
        a second new conversation would prove exactly what the first one
        already did."""
        bridge = FakeUiaBridge(
            existing_sessions={},
            window_text=(FOUNDER_WARNING,),
        )
        manager = ReasoningSessionManager(bridge, FakeMouse())

        result = manager.establish(WINDOW, "Kimi Desktop", FakeKeyboard())

        assert result.ok is False
        assert result.reason.startswith(SESSION_SATURATED)
        assert bridge.clicked_elements.count(bridge.new_session_element) == 1


class TestStaleAttachment:
    def test_a_clean_composer_is_not_an_isolated_session(self):
        """The founder saw a previous prompt survive as an attachment on
        the next turn. Text and attachments are separate state."""
        bridge = FakeUiaBridge(
            existing_sessions={DEDICATED_SESSION_NAME: object()},
            window_text=("Hello.",),
            attachment_present=True,
        )
        manager = ReasoningSessionManager(bridge, FakeMouse())

        health = manager.inspect_session(handle=7)

        assert health.saturated is False
        assert health.stale_attachment is True
        assert health.usable is False

    def test_an_attachment_that_survives_a_fresh_conversation_fails_closed(self):
        bridge = FakeUiaBridge(
            existing_sessions={DEDICATED_SESSION_NAME: object()},
            window_text=("Hello.",),
            attachment_present=True,
        )
        manager = ReasoningSessionManager(bridge, FakeMouse())

        result = manager.establish(WINDOW, "Kimi Desktop", FakeKeyboard())

        assert result.ok is False
        assert result.reason.startswith(SESSION_SATURATED)
        assert "attachment" in result.reason

    def test_only_removal_controls_count_as_evidence(self):
        """A permanent "Attach file" button exists on every one of these
        applications all the time. A "Remove attachment" control exists
        only when there is something attached -- which is why the
        vocabulary is removal-only."""
        from master_agent.providers.reasoning_session import STALE_ATTACHMENT_VOCABULARY

        for phrase in STALE_ATTACHMENT_VOCABULARY:
            assert phrase.split()[0] in ("remove", "delete", "clear")


# ----------------------------------------------------------------------
# The provider side
# ----------------------------------------------------------------------


def _kimi_spec():
    return next(spec for spec in PROVIDER_CATALOG if spec.provider_id == "kimi-desktop")


def _provider(spec):
    return DesktopAppReasoningProvider(spec, context=DesktopContext(probe=None))


class _Sessions:
    """A `ReasoningSessionManager`-shaped stand-in for the provider tests
    below, whose own behaviour is covered above."""

    def __init__(self, health_after: SessionHealth):
        from master_agent.providers.reasoning_session import SessionEstablishment
        self._establishment = SessionEstablishment(
            True, "", "Kalpavriksha Reasoning - test", health=SessionHealth(observed=True),
        )
        self._after = health_after
        self.retired: list[str] = []

    def establish(self, window, provider_label, keyboard):
        return self._establishment

    def inspect_session(self, handle):
        return self._after

    def retire(self, provider_label):
        self.retired.append(provider_label)


def _wired(provider, sessions, response):
    provider._context.inventory = lambda deep: object()
    provider._resolve_app_record = lambda inventory: types.SimpleNamespace(
        launchable=True, launch_target="fake.exe")
    provider._launch_or_focus = lambda app: {"handle": 42}
    provider._sessions = sessions
    provider._write_prompt = lambda window, prompt, keyboard: True
    provider._submit = lambda window, keyboard: True
    provider._await_response = lambda window, prompt, baseline: response
    provider._uia = types.SimpleNamespace(
        snapshot_text_regions=lambda handle: {})
    return provider


class TestAValidAnswerSurvivesTheWarning:
    """The warning can be caused by the very turn that just succeeded.

    Discarding a genuine answer for it would throw away work the founder
    already waited for. What changes is only what happens NEXT."""

    def test_the_answer_is_kept_and_the_conversation_is_retired(self):
        sessions = _Sessions(SessionHealth(saturated=True, warning=FOUNDER_WARNING, observed=True))
        provider = _wired(_provider(_kimi_spec()), sessions,
                          "Halden Reading Room is step-free and opens on Sunday.")

        result = provider.complete("which rooms are step-free?")

        assert result.outcome == SUCCEEDED
        assert "Halden" in result.response.text
        assert result.detail["session_reusable"] is False
        assert sessions.retired == ["Kimi Desktop"]

    def test_a_healthy_conversation_stays_reusable(self):
        sessions = _Sessions(SessionHealth(observed=True))
        provider = _wired(_provider(_kimi_spec()), sessions, "Halden Reading Room.")

        result = provider.complete("which rooms are step-free?")

        assert result.detail["session_reusable"] is True
        assert sessions.retired == []


class TestPromptLongerThanTheComposerWillCarry:
    """Two different provider constraints, never conflated:

        SESSION TOO LONG        rotate the conversation
        THIS PROMPT TOO LONG    this provider cannot serve this request

    Neither is ever answered by sending less of the question."""

    def test_a_prompt_past_the_declared_limit_is_refused_not_shortened(self):
        sessions = _Sessions(SessionHealth(observed=True))
        provider = _wired(_provider(_kimi_spec()), sessions, "an answer")
        written: list[str] = []
        provider._write_prompt = lambda w, prompt, k: written.append(prompt) or True

        result = provider.complete("x" * 5000)

        assert result.outcome != SUCCEEDED
        assert result.error == mod.PROMPT_TOO_LONG
        assert result.detail["prompt_chars"] == 5000
        assert written == [], "nothing may reach the composer"

    def test_the_refusal_happens_before_the_application_is_touched(self):
        """A provider that cannot serve this request should cost the
        question and nothing else -- no launch, no focus, no window."""
        provider = _provider(_kimi_spec())
        provider._context.inventory = lambda deep: (_ for _ in ()).throw(
            AssertionError("discovery must not run"))

        assert provider.complete("x" * 5000).error == mod.PROMPT_TOO_LONG

    def test_a_prompt_within_the_limit_is_sent_whole(self):
        sessions = _Sessions(SessionHealth(observed=True))
        provider = _wired(_provider(_kimi_spec()), sessions, "an answer")
        written: list[str] = []
        provider._write_prompt = lambda w, prompt, k: written.append(prompt) or True
        question = "y" * 3000

        provider.complete(question)

        assert written and written[0].endswith(question)

    def test_a_provider_with_no_declared_limit_is_unaffected(self):
        spec = next(s for s in PROVIDER_CATALOG if s.provider_id == "chatgpt-desktop")
        assert spec.max_prompt_chars is None
        sessions = _Sessions(SessionHealth(observed=True))
        provider = _wired(_provider(spec), sessions, "an answer")

        assert provider.complete("x" * 50_000).outcome == SUCCEEDED


class TestNothingTruncatesAPrompt:
    def test_no_slice_of_a_prompt_is_taken_anywhere_on_the_send_path(self):
        """The founder's own prohibition, checked against the source
        rather than trusted. `prompt[:4000]` and every relative of it is
        a different question answered confidently."""
        import inspect
        import io
        import re
        import tokenize

        from master_agent.providers import desktop_app, reasoning_session

        def executable_code(module) -> str:
            """Comments and docstrings discuss `prompt[:limit]` at length
            precisely because it is forbidden. Only what actually RUNS is
            evidence about what the code does."""
            kept = []
            for token in tokenize.generate_tokens(
                io.StringIO(inspect.getsource(module)).readline
            ):
                if token.type not in (tokenize.COMMENT, tokenize.STRING):
                    kept.append(token.string)
            return " ".join(kept)

        for module in (desktop_app, reasoning_session):
            # A slice of anything named like the request being sent.
            offenders = re.findall(
                r"\b\w*prompt\w*\s*\[\s*[^\]]*:", executable_code(module)
            )
            assert offenders == [], f"{module.__name__}: {offenders}"


class TestSaturationIsNotAProviderVerdict:
    def test_the_reason_is_about_the_session_not_the_application(self):
        bridge = _saturated_bridge()
        manager = ReasoningSessionManager(bridge, FakeMouse())

        reason = manager.establish(WINDOW, "Kimi Desktop", FakeKeyboard()).reason

        assert SESSION_SATURATED in reason
        assert "conversation" in reason

    def test_a_retired_conversation_leaves_the_provider_catalog_untouched(self):
        """Nothing here may reach for a provider-wide exclusion. One
        accumulated conversation being spent says nothing about whether
        the application can answer the next question."""
        before = _kimi_spec()
        manager = ReasoningSessionManager(FakeUiaBridge(), FakeMouse())
        manager.retire("Kimi Desktop")

        assert _kimi_spec() == before
        assert before.autonomous_reasoning_unsafe_reason is None


class TestBestEffortMeansBestEffort:
    """A step whose failure costs nothing must not be able to cost
    everything.

    Found live, in the diversified battery: `SetFocus()` on an inline
    rename field that had already closed raised `_ctypes.COMError` out of
    `_rename_current_session` -- a step documented as "never raises; a
    failure at any step simply returns False" -- through the reasoning
    provider, out of `mission_service.start()`, and ended the mission.

    Losing a rename costs reuse on a future call. Losing the mission
    costs the founder the work. The automation stack raises COM errors
    that are not in this module's declared vocabulary, so "never raises"
    has to be enforced, not stated.
    """

    class _Exploding:
        """A bridge whose every automation call fails the way the real
        one did: an OSError subclass, which `_ctypes.COMError` is."""

        def __init__(self, sessions=None):
            self.sessions = dict(sessions or {})

        def find(self, handle, **kwargs):
            name = kwargs.get("name_exact")
            if name is not None and name in self.sessions:
                return self.sessions[name]
            raise OSError("the window went away")

        def click(self, element, mouse):
            raise OSError("the window went away")

        def snapshot_text_regions(self, handle, min_height=8):
            raise OSError("the window went away")

        def find_composer(self, handle, retries=2, retry_delay_seconds=0.6):
            raise OSError("the window went away")

        def read_text(self, element):
            raise OSError("the window went away")

        def get_focused_element_in_window(self, handle):
            raise OSError("the window went away")

        def write_text(self, element, text, keyboard, append=False, mouse=None):
            raise OSError("the window went away")

    def test_inspecting_a_window_that_went_away_claims_nothing(self):
        manager = ReasoningSessionManager(self._Exploding(), FakeMouse())

        health = manager.inspect_session(handle=7)

        assert health.observed is False
        assert health.usable is True

    def test_a_rename_that_explodes_is_still_only_a_rename(self):
        manager = ReasoningSessionManager(self._Exploding(), FakeMouse())

        assert manager._rename_current_session(7, FakeKeyboard(), "x") is False

    def test_chat_section_navigation_that_explodes_is_not_fatal(self):
        manager = ReasoningSessionManager(self._Exploding(), FakeMouse())

        assert manager._navigate_to_chat_section(7) is False

    def test_a_write_that_cannot_take_focus_is_a_failed_write(self):
        """The exact frame the live traceback named. `write_text` is the
        primitive every caller already reads as "did it land?"."""
        from master_agent.desktop.execution.uia_control import UiaAutomationBridge

        class Detached:
            def SetFocus(self):
                raise OSError("An event was unable to invoke any of the subscribers")

            def GetCurrentPattern(self, *_):
                raise OSError("no pattern")

        assert UiaAutomationBridge().write_text(
            Detached(), "anything", FakeKeyboard()) is False
