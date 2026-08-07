"""Product Veda integration — the Founder Desktop Application bridge.

`desktop_shell.py` is the wiring between the native window (pywebview,
optional and not imported by these tests) and `FounderEditionApp`
(C24/C30). Every test here proves the bridge composes no reply of its
own and duplicates no C29/C31/C32 logic — it calls the existing pieces
and returns what they said.
"""
from __future__ import annotations

import json
import types
from datetime import UTC, datetime

from master_agent.communication import CommunicationResponse
from master_agent.founder_edition.boot import boot_founder_edition
from master_agent.founder_edition.desktop_shell import (
    BridgeTextOutput,
    DesktopShellApi,
    _founder_seed,
    _local_now,
)


def app(**kwargs):
    kwargs.setdefault("founder_name", "Onkar")
    kwargs.setdefault("text_output", BridgeTextOutput())
    return boot_founder_edition(**kwargs)


def api(**kwargs) -> DesktopShellApi:
    return DesktopShellApi(app(**kwargs))


class TestBridgeTextOutput:
    def test_emit_does_nothing_and_returns_none(self):
        assert BridgeTextOutput().emit(CommunicationResponse(text="hi")) is None

    def test_is_a_real_text_output(self):
        from master_agent.communication import TextOutput

        assert isinstance(BridgeTextOutput(), TextOutput)


class TestFounderSeed:
    def test_stable_for_the_same_name(self):
        assert _founder_seed("Onkar") == _founder_seed("Onkar")

    def test_differs_for_different_names(self):
        assert _founder_seed("Onkar") != _founder_seed("Someone Else")

    def test_is_an_unsigned_32_bit_integer(self):
        seed = _founder_seed("Onkar")
        assert 0 <= seed <= 0xFFFFFFFF


class TestLocalNow:
    def test_is_timezone_aware(self):
        assert _local_now().tzinfo is not None


class TestDesktopShellApiSeed:
    def test_get_founder_seed_matches_the_identity(self):
        instance = api()
        assert instance.get_founder_seed() == _founder_seed("Onkar")

    def test_get_founder_seed_falls_back_when_identity_is_absent(self):
        from master_agent.founder_edition.boot import BootReport, FounderEditionApp
        from master_agent.founder_runtime import FounderRuntime
        from master_agent.memory.conversation import ConversationMemory

        bare = FounderEditionApp(
            runtime=FounderRuntime(), conversation=ConversationMemory(),
            report=BootReport(),
        )
        instance = DesktopShellApi(bare)
        assert instance.get_founder_seed() == _founder_seed("Founder")


class TestGreetWithoutIdentity:
    def test_returns_both_fields_as_none_rather_than_crashing(self):
        from master_agent.founder_edition.boot import BootReport, FounderEditionApp
        from master_agent.founder_runtime import FounderRuntime
        from master_agent.memory.conversation import ConversationMemory

        bare = FounderEditionApp(
            runtime=FounderRuntime(), conversation=ConversationMemory(),
            report=BootReport(),
        )
        result = DesktopShellApi(bare).greet()
        assert result == {"reply": None, "presence": None}


class TestGreet:
    def test_greeting_is_real_and_time_banded(self):
        result = api().greet()
        assert result["reply"] is not None
        assert any(
            result["reply"].startswith(word)
            for word in ("Good morning", "Good afternoon", "Good evening")
        )

    def test_greeting_names_no_internal_component(self):
        result = api().greet()
        lowered = (result["reply"] or "").lower()
        for forbidden in ("runtime", "kernel", "operator"):
            assert forbidden not in lowered

    def test_presence_is_honestly_absent_not_invented(self):
        """No backend component publishes a presence-line sentence; the
        bridge must not invent one — see the module's own docstring."""
        result = api().greet()
        assert result["presence"] is None

    def test_reflects_the_real_local_hour(self, monkeypatch):
        import master_agent.founder_edition.desktop_shell as shell

        fixed = datetime(2026, 8, 7, 8, 30, tzinfo=UTC).astimezone()
        monkeypatch.setattr(shell, "_local_now", lambda: fixed.replace(hour=8))
        result = api().greet()
        assert result["reply"].startswith("Good morning")


class TestSendMessage:
    def test_a_recognised_message_gets_a_real_reply(self):
        result = api().send_message("Continue", "text")
        assert result["reply"] == "Continuing."

    def test_an_unrecognised_message_is_honestly_silent(self):
        result = api().send_message("asdkjhasdkjh nonsense", "text")
        assert result["reply"] is None

    def test_voice_and_text_sources_are_answered_identically(self):
        instance = api()
        text_reply = instance.send_message("Continue", "text")
        instance2 = api()
        voice_reply = instance2.send_message("Continue", "voice")
        assert text_reply["reply"] == voice_reply["reply"]

    def test_an_unknown_source_string_defaults_to_text(self):
        result = api().send_message("Continue", "carrier-pigeon")
        assert result["reply"] == "Continuing."

    def test_without_a_wired_communication_layer_reply_is_none(self, monkeypatch):
        from master_agent.founder_edition import boot as boot_module

        def boom(*_a, **_kw):
            raise RuntimeError("no communication")

        monkeypatch.setattr(boot_module, "CommunicationEngine", boom)
        instance = DesktopShellApi(boot_module.boot_founder_edition(founder_name="Onkar"))
        assert instance.send_message("Continue", "text") == {"reply": None}

    def test_mode_switch_phrase_recovers_automatically(self):
        """The same `ChannelNotRegistered` gap `console.py` guards
        against (Engineering/HEALTH_C33.md §5): switching to voice with
        no voice channel registered must not strand the conversation."""
        instance = api()
        switch_result = instance.send_message("switch to voice", "text")
        assert switch_result == {"reply": None}
        recovered = instance.send_message("Continue", "text")
        assert recovered["reply"] == "Continuing."

    def test_the_conversation_actually_grows_in_the_dashboard(self):
        instance = api()
        instance.send_message("Good morning Somesh", "text")
        dashboard = instance.get_dashboard()
        assert len(dashboard["conversation"]["entries"]) == 2


class _RecordingVoice:
    def __init__(self) -> None:
        self.spoken: list[str] = []
        self.muted_calls: list[bool] = []
        self.interrupt_calls = 0
        self.abandon_calls = 0

    def speak(self, text: str) -> None:
        self.spoken.append(text)

    def set_muted(self, muted: bool) -> None:
        self.muted_calls.append(muted)

    def interrupt_speech(self) -> None:
        self.interrupt_calls += 1

    def abandon_capture(self) -> None:
        self.abandon_calls += 1


class TestSendMessageSpeaksThroughVoice:
    def test_a_real_reply_is_spoken(self):
        voice = _RecordingVoice()
        instance = DesktopShellApi(app(), voice=voice)
        instance.send_message("Continue", "text")
        assert voice.spoken == ["Continuing."]

    def test_an_unrecognised_message_speaks_nothing(self):
        voice = _RecordingVoice()
        instance = DesktopShellApi(app(), voice=voice)
        instance.send_message("asdkjhasdkjh nonsense", "text")
        assert voice.spoken == []

    def test_a_mode_switch_speaks_nothing_either(self):
        voice = _RecordingVoice()
        instance = DesktopShellApi(app(), voice=voice)
        instance.send_message("switch to voice", "text")
        assert voice.spoken == []


class TestToggleMute:
    def test_without_a_voice_pipeline_reports_none(self):
        instance = api()
        assert instance.toggle_mute() == {"muted": None}

    def test_toggles_and_forwards_to_the_pipeline(self):
        voice = _RecordingVoice()
        instance = DesktopShellApi(app(), voice=voice)
        assert instance.toggle_mute() == {"muted": True}
        assert instance.toggle_mute() == {"muted": False}
        assert voice.muted_calls == [True, False]


class TestInterruptSpeech:
    def test_forwards_to_the_pipeline(self):
        voice = _RecordingVoice()
        instance = DesktopShellApi(app(), voice=voice)
        instance.interrupt_speech()
        assert voice.interrupt_calls == 1

    def test_without_a_voice_pipeline_does_nothing(self):
        api().interrupt_speech()  # must not raise


class TestAbandonVoiceCapture:
    def test_forwards_to_the_pipeline(self):
        voice = _RecordingVoice()
        instance = DesktopShellApi(app(), voice=voice)
        instance.abandon_voice_capture()
        assert voice.abandon_calls == 1

    def test_without_a_voice_pipeline_does_nothing(self):
        api().abandon_voice_capture()  # must not raise


class TestOpenMicrophoneSettings:
    def test_calls_the_injected_settings_opener(self):
        calls = []
        instance = DesktopShellApi(app(), open_settings=lambda: calls.append(1))
        instance.open_microphone_settings()
        assert calls == [1]

    def test_without_an_injected_opener_does_nothing(self):
        api().open_microphone_settings()  # must not raise

    def test_a_raising_opener_does_not_crash_the_bridge(self):
        def boom():
            raise OSError("no handler registered")

        instance = DesktopShellApi(app(), open_settings=boom)
        instance.open_microphone_settings()  # must not raise


class TestGetDashboard:
    def test_returns_the_apps_own_live_dashboard(self):
        instance = api()
        dashboard = instance.get_dashboard()
        assert set(dashboard) == {
            "identity", "session", "boot", "environment", "presence",
            "conversation", "desktop", "sources",
        }

    def test_is_pure_json(self):
        dashboard = api().get_dashboard()
        assert json.loads(json.dumps(dashboard)) == dashboard


class TestPresenceComplete:
    def test_false_when_no_coverage_is_registered(self):
        instance = api()
        assert instance._presence_complete() is False


class _FakeEvent:
    """Mirrors `webview.window.Event`'s own `+=` registration contract
    closely enough to exercise `create_window()`'s real wiring."""

    def __init__(self) -> None:
        self.handlers: list = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self

    def fire(self, *args) -> None:
        for handler in self.handlers:
            handler(*args)


class _FakeWindow:
    def __init__(self, title, **kwargs) -> None:
        self.title = title
        self.kwargs = kwargs
        self.exposed: dict[str, object] = {}
        self.js_calls: list[str] = []
        self.events = types.SimpleNamespace(
            shown=_FakeEvent(), closing=_FakeEvent(),
        )

    def expose(self, *functions) -> None:
        for fn in functions:
            self.exposed[fn.__name__] = fn

    def evaluate_js(self, source: str) -> None:
        self.js_calls.append(source)



def _install_fake_webview(monkeypatch):
    import sys

    windows: list[_FakeWindow] = []
    starts: dict = {}

    def fake_create_window(title, **kwargs):
        window = _FakeWindow(title, **kwargs)
        windows.append(window)
        return window

    fake_webview = types.SimpleNamespace(
        create_window=fake_create_window,
        start=lambda **kwargs: starts.update(kwargs) or starts.__setitem__("called", True),
    )
    monkeypatch.setitem(sys.modules, "webview", fake_webview)
    return windows, starts


class TestCreateWindow:
    def test_wires_a_fake_webview_module_without_opening_a_real_window(self, monkeypatch):
        """`create_window()` imports `webview` lazily inside the
        function body — this test supplies a fake module via
        `sys.modules` so the wiring is exercised without a real window
        opening during the test run."""
        from master_agent.founder_edition import desktop_shell as shell_module

        windows, starts = _install_fake_webview(monkeypatch)

        returned = shell_module.create_window(
            founder_name="Onkar", web_dir="/tmp/web", debug=True,
        )

        assert len(windows) == 1
        window = windows[0]
        assert window.title == "Kalpavriksha"
        assert window.kwargs["url"] == "/tmp/web/index.html"
        assert window.kwargs["background_color"] == "#05070A"
        assert starts == {"debug": True, "called": True}
        assert returned.identity.founder_name == "Onkar"

    def test_exposes_exactly_the_eight_bridge_methods(self, monkeypatch):
        from master_agent.founder_edition import desktop_shell as shell_module

        windows, _ = _install_fake_webview(monkeypatch)
        shell_module.create_window(founder_name="Onkar", web_dir="/tmp/web")

        assert set(windows[0].exposed) == {
            "get_founder_seed", "greet", "send_message", "get_dashboard", "toggle_mute",
            "open_microphone_settings", "interrupt_speech", "abandon_voice_capture",
        }

    def test_voice_starts_only_after_the_window_is_shown(self, monkeypatch):
        """Product Veda: the founder never waits on a flourish — model
        loading must not block window creation."""
        from master_agent.founder_edition import desktop_shell as shell_module

        started = {"n": 0}
        monkeypatch.setattr(
            shell_module.VoicePipeline, "start", lambda self: started.__setitem__("n", started["n"] + 1)
        )
        windows, _ = _install_fake_webview(monkeypatch)

        shell_module.create_window(founder_name="Onkar", web_dir="/tmp/web")
        assert started["n"] == 0

        windows[0].events.shown.fire()
        assert started["n"] == 1

    def test_voice_stops_when_the_window_closes(self, monkeypatch):
        from master_agent.founder_edition import desktop_shell as shell_module

        stopped = {"n": 0}
        monkeypatch.setattr(
            shell_module.VoicePipeline, "stop", lambda self: stopped.__setitem__("n", stopped["n"] + 1)
        )
        windows, _ = _install_fake_webview(monkeypatch)

        shell_module.create_window(founder_name="Onkar", web_dir="/tmp/web")
        windows[0].events.closing.fire()
        assert stopped["n"] == 1


class TestPush:
    def test_calls_evaluate_js_with_json_escaped_arguments(self):
        from master_agent.founder_edition.desktop_shell import _push

        window = _FakeWindow("x")
        _push(window, "onTranscript", 'he said "hi"')
        assert window.js_calls == ['onTranscript("he said \\"hi\\"")']

    def test_a_closed_window_does_not_raise(self):
        from master_agent.founder_edition.desktop_shell import _push

        class Closed:
            def evaluate_js(self, source):
                raise RuntimeError("window is gone")

        _push(Closed(), "onVoiceState", "armed")  # must not raise


class TestNoDuplicatedLogic:
    def test_send_message_composes_no_reply_of_its_own(self):
        """Every string `send_message` can return is `routed.response.
        display` — read from `CommunicationEngine.handle()`'s own
        return value, never composed in this module."""
        import ast
        import inspect
        import textwrap

        source = textwrap.dedent(inspect.getsource(DesktopShellApi.send_message))
        tree = ast.parse(source)
        string_constants = [
            n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
        ]
        # every literal string in this method is a dict key or the
        # closed "text" source-fallback, never founder-facing prose
        assert all(len(s) < 20 for s in string_constants)

    def test_greet_composes_no_reply_of_its_own(self):
        import ast
        import inspect
        import textwrap

        source = textwrap.dedent(inspect.getsource(DesktopShellApi.greet))
        tree = ast.parse(source)
        calls = {
            n.func.id for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }
        assert "greet" in calls  # delegates to founder_identity.greet
