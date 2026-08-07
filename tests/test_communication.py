"""Sprint 1, Component 32 — Unified Communication Layer.

| Requirement | Source |
|---|---|
| Somesh receives exactly one `CommunicationRequest`, whatever the channel | C32 brief |
| Conversation Engine never knows typed vs. spoken | C32 brief |
| Voice, text, or both simultaneously — Conversation Engine never knows which | C32 brief |
| `CommunicationResponse` packages strings; no TTS, no audio synthesis | C32 brief |
| Four abstract channel interfaces, no implementation | C32 brief |
| Router: channel -> request -> engine -> response -> channel | C32 brief |
| `OutputMode` runtime selectable; switching via founder speech | C32 brief |
| No speech recognition, no mic/TTS/audio libraries, no desktop, no Runtime mutation, no planning | C32 brief |
| Reuse Founder Identity, Conversation Engine, Founder Runtime, Conversation Memory — no duplication | C32 brief |

Boundary guards read imports and method bodies by AST — the same
discipline C23/C29/C30/C31 already use, because a promise in a docstring
is not one a reader can trust until a test can fail it.
"""
from __future__ import annotations

import ast
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from master_agent.communication import (
    ChannelNotRegistered,
    CommunicationEngine,
    CommunicationRequest,
    CommunicationResponse,
    CommunicationRouter,
    OutputMode,
    RoutedResponse,
    Source,
    TextInput,
    TextOutput,
    VoiceInput,
    VoiceOutput,
)
from master_agent.communication.router import (
    _CHANNELS_FOR_MODE,
    _normalize,
    _requested_mode,
)
from master_agent.conversation_engine import ConversationEngine
from master_agent.founder_identity import FounderIdentity, FounderSession
from master_agent.founder_runtime import FounderRuntime
from master_agent.memory.conversation import ConversationMemory

PACKAGE = (
    Path(__file__).resolve().parent.parent
    / "src" / "master_agent" / "communication"
)

T0 = datetime(2026, 8, 7, 8, 30, tzinfo=UTC)


# ───────────────────────────── fixtures ─────────────────────────────────


def request(content: str, source: Source = Source.TEXT, **overrides) -> CommunicationRequest:
    defaults = {
        "source": source,
        "content": content,
        "timestamp": T0,
        "conversation_id": "c1",
    }
    defaults.update(overrides)
    return CommunicationRequest(**defaults)


def conversation_engine(**kwargs):
    conversation = ConversationMemory()
    runtime = FounderRuntime(conversation=conversation)
    identity = FounderIdentity(founder_name="Onkar")
    session = FounderSession(conversation)
    ce = ConversationEngine(
        runtime=runtime, identity=identity, session=session, conversation=conversation
    )
    return ce, conversation


def router(**kwargs) -> CommunicationRouter:
    ce, _ = conversation_engine()
    return CommunicationRouter(conversation_engine=ce, **kwargs)


class SpyVoiceOutput(VoiceOutput):
    def __init__(self) -> None:
        self.received: list[CommunicationResponse] = []

    def emit(self, response: CommunicationResponse) -> None:
        self.received.append(response)


class SpyTextOutput(TextOutput):
    def __init__(self) -> None:
        self.received: list[CommunicationResponse] = []

    def emit(self, response: CommunicationResponse) -> None:
        self.received.append(response)


def engine(**kwargs) -> tuple[CommunicationEngine, SpyVoiceOutput, SpyTextOutput]:
    ce, conversation = conversation_engine()
    voice, text = SpyVoiceOutput(), SpyTextOutput()
    kwargs.setdefault("voice_output", voice)
    kwargs.setdefault("text_output", text)
    comm = CommunicationEngine(
        conversation_engine=ce, conversation=conversation, **kwargs
    )
    return comm, voice, text


# ══════════════════════════ CommunicationRequest ═════════════════════════


class TestCommunicationRequest:
    def test_holds_the_four_named_fields(self):
        req = request("hello")
        assert req.source is Source.TEXT
        assert req.content == "hello"
        assert req.timestamp == T0
        assert req.conversation_id == "c1"

    @pytest.mark.parametrize("source", [Source.VOICE, Source.TEXT, Source.FUTURE])
    def test_every_named_source_is_accepted(self, source):
        assert request("hi", source=source).source is source

    def test_frozen(self):
        req = request("hello")
        with pytest.raises(AttributeError):
            req.content = "changed"  # type: ignore[misc]

    def test_refuses_a_non_source(self):
        with pytest.raises(TypeError):
            CommunicationRequest(
                source="voice", content="hi", timestamp=T0, conversation_id="c1"
            )

    def test_refuses_empty_content(self):
        with pytest.raises(ValueError):
            request("   ")

    def test_refuses_a_naive_timestamp(self):
        with pytest.raises(ValueError):
            CommunicationRequest(
                source=Source.TEXT, content="hi",
                timestamp=datetime(2026, 8, 7, 8, 30),  # noqa: DTZ001
                conversation_id="c1",
            )

    def test_refuses_empty_conversation_id(self):
        with pytest.raises(ValueError):
            request("hi", conversation_id="  ")

    def test_as_dict_is_json_ready(self):
        req = request("hi")
        assert json.loads(json.dumps(req.as_dict())) == req.as_dict()

    def test_as_dict_uses_the_sources_own_value(self):
        assert request("hi", source=Source.VOICE).as_dict()["source"] == "voice"


# ══════════════════════════ CommunicationResponse ════════════════════════


class TestCommunicationResponse:
    def test_text_alone_falls_back_for_both_spoken_and_display(self):
        response = CommunicationResponse(text="hello")
        assert response.spoken == "hello"
        assert response.display == "hello"

    def test_spoken_text_overrides_only_spoken(self):
        response = CommunicationResponse(text="hello", spoken_text="hi there")
        assert response.spoken == "hi there"
        assert response.display == "hello"

    def test_display_text_overrides_only_display(self):
        response = CommunicationResponse(text="hello", display_text="Hello!")
        assert response.spoken == "hello"
        assert response.display == "Hello!"

    def test_both_may_be_set_independently(self):
        response = CommunicationResponse(
            text="hello", spoken_text="hi", display_text="Hello!"
        )
        assert response.spoken == "hi"
        assert response.display == "Hello!"

    def test_may_be_identical(self):
        response = CommunicationResponse(
            text="hello", spoken_text="hello", display_text="hello"
        )
        assert response.spoken == response.display == "hello"

    def test_frozen(self):
        response = CommunicationResponse(text="hi")
        with pytest.raises(AttributeError):
            response.text = "changed"  # type: ignore[misc]

    def test_refuses_empty_text(self):
        with pytest.raises(ValueError):
            CommunicationResponse(text="")

    @pytest.mark.parametrize("field", ["spoken_text", "display_text"])
    def test_refuses_empty_optional_fields(self, field):
        with pytest.raises(ValueError):
            CommunicationResponse(text="hi", **{field: "   "})

    def test_none_is_accepted_for_optional_fields(self):
        response = CommunicationResponse(text="hi", spoken_text=None, display_text=None)
        assert response.spoken == response.display == "hi"

    def test_as_dict_is_json_ready(self):
        response = CommunicationResponse(text="hi")
        assert json.loads(json.dumps(response.as_dict())) == response.as_dict()

    def test_produces_no_audio_bytes_of_any_kind(self):
        """Structural: a response has exactly three string fields, and
        nothing this class returns is `bytes`."""
        response = CommunicationResponse(text="hi", spoken_text="hey", display_text="Hi!")
        for value in response.as_dict().values():
            assert not isinstance(value, bytes)


# ══════════════════════════ channels.py ══════════════════════════════════


class TestChannelInterfaces:
    @pytest.mark.parametrize("cls", [VoiceInput, TextInput, VoiceOutput, TextOutput])
    def test_cannot_be_instantiated_directly(self, cls):
        with pytest.raises(TypeError):
            cls()

    def test_voice_input_requires_receive(self):
        class Incomplete(VoiceInput):
            pass

        with pytest.raises(TypeError):
            Incomplete()

    def test_text_input_requires_receive(self):
        class Incomplete(TextInput):
            pass

        with pytest.raises(TypeError):
            Incomplete()

    def test_voice_output_requires_emit(self):
        class Incomplete(VoiceOutput):
            pass

        with pytest.raises(TypeError):
            Incomplete()

    def test_text_output_requires_emit(self):
        class Incomplete(TextOutput):
            pass

        with pytest.raises(TypeError):
            Incomplete()

    def test_a_complete_voice_input_can_be_built_and_used(self):
        class FixedVoiceInput(VoiceInput):
            def receive(self) -> CommunicationRequest:
                return request("hello", source=Source.VOICE)

        received = FixedVoiceInput().receive()
        assert received.source is Source.VOICE

    def test_a_complete_text_input_can_be_built_and_used(self):
        class FixedTextInput(TextInput):
            def receive(self) -> CommunicationRequest:
                return request("hello", source=Source.TEXT)

        received = FixedTextInput().receive()
        assert received.source is Source.TEXT

    def test_output_mode_has_exactly_three_members(self):
        assert {m.name for m in OutputMode} == {
            "VOICE_ONLY", "TEXT_ONLY", "VOICE_AND_TEXT",
        }


# ══════════════════════════ router internals ═════════════════════════════


class TestNormalize:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Switch to text", "switch to text"),
            ("Somesh, switch to text.", "switch to text"),
            ("somesh switch to voice", "switch to voice"),
            ("SWITCH BACK TO VOICE!", "switch back to voice"),
        ],
    )
    def test_strips_address_and_punctuation(self, text, expected):
        assert _normalize(text) == expected


class TestRequestedMode:
    @pytest.mark.parametrize(
        "text",
        ["switch to text", "Somesh, switch to text.", "text mode", "go to text"],
    )
    def test_recognises_text_only(self, text):
        assert _requested_mode(text) is OutputMode.TEXT_ONLY

    @pytest.mark.parametrize(
        "text",
        ["switch to voice", "Switch back to voice.", "voice mode", "go to voice"],
    )
    def test_recognises_voice_only(self, text):
        assert _requested_mode(text) is OutputMode.VOICE_ONLY

    @pytest.mark.parametrize(
        "text",
        ["switch to both", "turn on both", "voice and text mode",
         "switch to voice and text"],
    )
    def test_recognises_both(self, text):
        assert _requested_mode(text) is OutputMode.VOICE_AND_TEXT

    @pytest.mark.parametrize(
        "text", ["Good morning Somesh", "How's the system?", "", "build a bot"]
    )
    def test_unrelated_speech_requests_no_mode(self, text):
        assert _requested_mode(text) is None

    def test_channels_for_mode_is_total_and_closed(self):
        assert set(_CHANNELS_FOR_MODE) == set(OutputMode)


# ══════════════════════════ CommunicationRouter ══════════════════════════


class TestCommunicationRouterConstruction:
    def test_default_mode_is_text_only(self):
        assert router().mode is OutputMode.TEXT_ONLY

    def test_a_starting_mode_can_be_given(self):
        assert router(mode=OutputMode.VOICE_ONLY).mode is OutputMode.VOICE_ONLY

    def test_refuses_a_non_conversation_engine(self):
        with pytest.raises(TypeError):
            CommunicationRouter(conversation_engine=object())

    def test_refuses_a_non_output_mode(self):
        ce, _ = conversation_engine()
        with pytest.raises(TypeError):
            CommunicationRouter(conversation_engine=ce, mode="text_only")


class TestCommunicationRouterRouting:
    def test_a_recognised_intent_is_routed_to_the_current_mode(self):
        r = router(mode=OutputMode.VOICE_ONLY)
        routed = r.route(request("Continue"))
        assert routed.channels == ("voice",)
        assert routed.mode is OutputMode.VOICE_ONLY

    def test_an_unrecognised_utterance_routes_to_nothing(self):
        r = router()
        assert r.route(request("asdkjhasdkjh nonsense")) is None

    def test_refuses_a_non_request(self):
        with pytest.raises(TypeError):
            router().route(object())

    def test_the_response_carries_the_conversation_engines_own_reply(self):
        r = router()
        routed = r.route(request("Continue"))
        assert routed.response.text == "Continuing."

    def test_the_conversation_engine_is_never_told_which_channel_asked(self):
        """Two requests differing only in `source` produce identical
        replies — nothing in `ConversationContext` or the composed
        sentence can vary with it, because `CommunicationRouter` never
        passes `source` through to `ConversationEngine.reply()`."""
        r = router()
        voice_reply = r.route(request("Continue", source=Source.VOICE))
        text_reply = r.route(request("Continue", source=Source.TEXT))
        assert voice_reply.response.text == text_reply.response.text


class TestCommunicationRouterSwitching:
    def test_switching_to_text_updates_mode_and_acknowledges(self):
        r = router(mode=OutputMode.VOICE_ONLY)
        routed = r.route(request("Somesh, switch to text."))
        assert r.mode is OutputMode.TEXT_ONLY
        assert routed.mode is OutputMode.TEXT_ONLY
        assert routed.response.text == "Switched to text."
        assert routed.channels == ("text",)

    def test_switching_to_voice_updates_mode_and_acknowledges(self):
        r = router(mode=OutputMode.TEXT_ONLY)
        routed = r.route(request("Switch back to voice."))
        assert r.mode is OutputMode.VOICE_ONLY
        assert routed.response.text == "Switched to voice."

    def test_switching_to_both_reaches_both_channel_names(self):
        r = router(mode=OutputMode.TEXT_ONLY)
        routed = r.route(request("switch to both"))
        assert r.mode is OutputMode.VOICE_AND_TEXT
        assert routed.channels == ("voice", "text")

    def test_a_switch_never_reaches_the_conversation_engine(self):
        """The brief's own boundary: Conversation Engine must never know
        about transport. A switch phrase must not even become a turn in
        the conversation history."""
        ce, conversation = conversation_engine()
        r = CommunicationRouter(conversation_engine=ce)
        r.route(request("switch to voice"))
        assert conversation.turns() == []

    def test_switching_back_and_forth_is_stable(self):
        r = router()
        r.route(request("switch to voice"))
        r.route(request("switch to text"))
        r.route(request("switch to voice"))
        assert r.mode is OutputMode.VOICE_ONLY

    def test_a_switch_takes_effect_for_the_very_next_route_call(self):
        r = router(mode=OutputMode.TEXT_ONLY)
        r.route(request("switch to voice"))
        routed = r.route(request("Continue"))
        assert routed.channels == ("voice",)


# ══════════════════════════ CommunicationEngine ══════════════════════════


class TestCommunicationEngineConstruction:
    def test_default_mode_is_text_only(self):
        comm, _, _ = engine()
        assert comm.mode is OutputMode.TEXT_ONLY

    def test_refuses_a_non_conversation_memory(self):
        ce, _ = conversation_engine()
        with pytest.raises(TypeError):
            CommunicationEngine(conversation_engine=ce, conversation=object())

    def test_refuses_a_non_voice_output(self):
        ce, conversation = conversation_engine()
        with pytest.raises(TypeError):
            CommunicationEngine(
                conversation_engine=ce, conversation=conversation, voice_output=object()
            )

    def test_refuses_a_non_text_output(self):
        ce, conversation = conversation_engine()
        with pytest.raises(TypeError):
            CommunicationEngine(
                conversation_engine=ce, conversation=conversation, text_output=object()
            )

    def test_channels_are_optional(self):
        ce, conversation = conversation_engine()
        comm = CommunicationEngine(conversation_engine=ce, conversation=conversation)
        assert comm.mode is OutputMode.TEXT_ONLY


class TestCommunicationEngineHandling:
    def test_text_only_reaches_only_the_text_channel(self):
        comm, voice, text = engine(mode=OutputMode.TEXT_ONLY)
        comm.handle(request("Continue"))
        assert len(text.received) == 1
        assert len(voice.received) == 0

    def test_voice_only_reaches_only_the_voice_channel(self):
        comm, voice, text = engine(mode=OutputMode.VOICE_ONLY)
        comm.handle(request("Continue"))
        assert len(voice.received) == 1
        assert len(text.received) == 0

    def test_voice_and_text_reaches_both_simultaneously(self):
        """The brief's own reuse of the existing dual-output feature,
        exposed purely as routing: one response, both channels, one call."""
        comm, voice, text = engine(mode=OutputMode.VOICE_AND_TEXT)
        comm.handle(request("Continue"))
        assert len(voice.received) == 1
        assert len(text.received) == 1
        assert voice.received[0].text == text.received[0].text

    def test_both_channels_receive_the_identical_response_object(self):
        comm, voice, text = engine(mode=OutputMode.VOICE_AND_TEXT)
        comm.handle(request("Continue"))
        assert voice.received[0] is text.received[0]

    def test_unknown_speech_emits_to_nothing(self):
        comm, voice, text = engine(mode=OutputMode.VOICE_AND_TEXT)
        result = comm.handle(request("asdkjhasdkjh nonsense"))
        assert result is None
        assert voice.received == []
        assert text.received == []

    def test_a_voice_request_and_a_text_request_are_answered_identically(self):
        comm, _, _ = engine(mode=OutputMode.TEXT_ONLY)
        voice_result = comm.handle(request("Continue", source=Source.VOICE))
        text_result = comm.handle(request("Continue", source=Source.TEXT))
        assert voice_result.response.text == text_result.response.text

    def test_handle_returns_the_routed_response(self):
        comm, _, _ = engine()
        result = comm.handle(request("Continue"))
        assert isinstance(result, RoutedResponse)

    def test_switching_mid_conversation_changes_where_replies_land(self):
        comm, voice, text = engine(mode=OutputMode.TEXT_ONLY)
        comm.handle(request("Continue"))
        comm.handle(request("switch to voice"))
        comm.handle(request("Continue"))
        assert len(text.received) == 1
        # the switch acknowledgement plus the second "Continue" both land
        # on voice, since the switch took effect immediately
        assert len(voice.received) == 2

    def test_voice_only_without_a_registered_voice_output_raises(self):
        ce, conversation = conversation_engine()
        comm = CommunicationEngine(
            conversation_engine=ce, conversation=conversation,
            mode=OutputMode.VOICE_ONLY,
        )
        with pytest.raises(ChannelNotRegistered):
            comm.handle(request("Continue"))

    def test_text_only_without_a_registered_text_output_raises(self):
        ce, conversation = conversation_engine()
        comm = CommunicationEngine(
            conversation_engine=ce, conversation=conversation,
            mode=OutputMode.TEXT_ONLY,
        )
        with pytest.raises(ChannelNotRegistered):
            comm.handle(request("Continue"))

    def test_voice_and_text_with_only_text_registered_raises(self):
        ce, conversation = conversation_engine()
        comm = CommunicationEngine(
            conversation_engine=ce, conversation=conversation,
            mode=OutputMode.VOICE_AND_TEXT, text_output=SpyTextOutput(),
        )
        with pytest.raises(ChannelNotRegistered):
            comm.handle(request("Continue"))

    def test_a_switch_that_needs_an_unregistered_channel_still_raises(self):
        ce, conversation = conversation_engine()
        comm = CommunicationEngine(
            conversation_engine=ce, conversation=conversation,
            mode=OutputMode.TEXT_ONLY, text_output=SpyTextOutput(),
        )
        with pytest.raises(ChannelNotRegistered):
            comm.handle(request("switch to voice"))


class TestCommunicationEngineHistory:
    def test_history_reflects_recorded_turns(self):
        comm, _, _ = engine()
        comm.handle(request("Good morning Somesh"))
        assert len(comm.history()) == 2  # founder turn + Somesh's own

    def test_history_is_empty_before_anything_is_said(self):
        comm, _, _ = engine()
        assert comm.history() == ()

    def test_a_mode_switch_does_not_grow_history(self):
        comm, _, _ = engine()
        comm.handle(request("switch to voice"))
        assert comm.history() == ()

    def test_history_reads_the_same_memory_the_engine_uses_not_a_copy(self):
        ce, conversation = conversation_engine()
        comm = CommunicationEngine(
            conversation_engine=ce, conversation=conversation,
            text_output=SpyTextOutput(),
        )
        comm.handle(request("Good morning Somesh"))
        assert len(comm.history()) == len(conversation.turns())


# ══════════════════════════ end-to-end scenarios ═════════════════════════


class TestEndToEnd:
    def test_typed_spoken_and_dictated_all_arrive_as_one_shape(self):
        """*"typed or spoken or dictated... Somesh receives exactly one
        ConversationRequest."* Three different sources, same downstream
        handling."""
        comm, _, _ = engine(mode=OutputMode.TEXT_ONLY)
        for source in (Source.TEXT, Source.VOICE, Source.FUTURE):
            result = comm.handle(request("Continue", source=source))
            assert result.response.text == "Continuing."

    def test_the_briefs_own_switching_dialogue(self):
        comm, voice, text = engine(mode=OutputMode.VOICE_ONLY)
        comm.handle(request("Good morning Somesh"))
        assert len(voice.received) == 1 and len(text.received) == 0

        comm.handle(request("Somesh, switch to text."))
        comm.handle(request("Continue"))
        assert len(text.received) == 2  # switch ack + "Continuing."
        assert len(voice.received) == 1  # unchanged

        comm.handle(request("Switch back to voice."))
        comm.handle(request("Continue"))
        assert len(voice.received) == 3


# ══════════════════════════ Boundary guards (AST) ═════════════════════════

#: Everything this package is forbidden from reaching, in the brief's own
#: words: no desktop, no Runtime mutation, no planning, no audio/speech.
_FORBIDDEN_MASTER_AGENT_ROOTS = (
    "master_agent.desktop",
    "master_agent.desktop_operator",
    "master_agent.founder_edition",
    "master_agent.founder_runtime",
    "master_agent.founder_identity",
    "master_agent.voice",
    "master_agent.kernel",
    "master_agent.runtime_bridge",
    "master_agent.coordinator",
    "master_agent.planner",
    "master_agent.mission_manager",
    "master_agent.mission_control",
    "master_agent.missions",
    "master_agent.orchestrator",
    "master_agent.brain",
    "master_agent.broker",
    "master_agent.plugins",
    "master_agent.providers",
    "master_agent.executor",
    "master_agent.ledger",
    "master_agent.foundation",
    "master_agent.api",
    "master_agent.dashboard",
    "master_agent.launcher",
    "master_agent.permissions",
)

#: Third-party/stdlib modules that would mean real audio, real speech
#: recognition, real microphones, or real machine access. None of these
#: is imported by a package that is only supposed to package strings.
_FORBIDDEN_EXTERNAL_MODULES = (
    "pyaudio",
    "sounddevice",
    "wave",
    "speech_recognition",
    "whisper",
    "elevenlabs",
    "azure",
    "pyttsx3",
    "keyboard",
    "pynput",
    "subprocess",
    "socket",
    "threading",
    "multiprocessing",
    "sqlite3",
    "winreg",
    "ctypes",
    "http",
    "urllib",
    "requests",
    "httpx",
)


def _modules() -> list[tuple[Path, ast.Module]]:
    return [
        (path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
        for path in sorted(PACKAGE.glob("*.py"))
    ]


def _imported_modules() -> set[str]:
    modules: set[str] = set()
    for _, tree in _modules():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
    return modules


class TestBoundaries:
    def test_the_guard_actually_found_the_package(self):
        assert len(list(PACKAGE.glob("*.py"))) >= 5

    def test_no_forbidden_master_agent_module_is_imported(self):
        offenders = []
        imports = _imported_modules()
        for module in imports:
            for root in _FORBIDDEN_MASTER_AGENT_ROOTS:
                if module == root or module.startswith(root + "."):
                    offenders.append(module)
        assert offenders == []

    def test_no_forbidden_external_module_is_imported(self):
        imports = _imported_modules()
        offenders = [m for m in _FORBIDDEN_EXTERNAL_MODULES if m in imports]
        assert offenders == []

    def test_the_only_master_agent_door_is_communication_or_conversation_engine_or_memory(self):
        allowed_roots = (
            "master_agent.communication",
            "master_agent.conversation_engine",
            "master_agent.memory",
        )
        offenders = []
        for module in _imported_modules():
            if not module.startswith("master_agent"):
                continue
            if not any(
                module == root or module.startswith(root + ".")
                for root in allowed_roots
            ):
                offenders.append(module)
        assert offenders == []

    def test_no_ambient_clock_is_read(self):
        offenders = []
        for path, _ in _modules():
            text = path.read_text(encoding="utf-8")
            if "datetime.now(" in text or "date.today(" in text:
                offenders.append(path.name)
        assert offenders == []

    def test_runtime_is_never_imported_at_all(self):
        """A stronger guarantee than "not mutated" — this package cannot
        even construct or hold a `FounderRuntime` reference, so it
        literally cannot mutate one."""
        assert "master_agent.founder_runtime" not in _imported_modules()

    def test_the_guards_can_actually_fail(self):
        """Proven able to fail, the same discipline C28/C30/C31 already
        use: a throwaway forbidden import is added, confirmed to trip,
        then discarded."""
        probe = PACKAGE / "_leak_probe.py"
        probe.write_text(
            "import subprocess\n"
            "from master_agent.desktop.inventory import discover\n"
            "import pyttsx3\n",
            encoding="utf-8",
        )
        try:
            imports = _imported_modules()
            master_agent_tripped = any(
                m == root or m.startswith(root + ".")
                for m in imports
                for root in _FORBIDDEN_MASTER_AGENT_ROOTS
            )
            external_tripped = any(m in imports for m in _FORBIDDEN_EXTERNAL_MODULES)
            assert master_agent_tripped is True
            assert external_tripped is True
        finally:
            probe.unlink()
        assert not any(
            m == root or m.startswith(root + ".")
            for m in _imported_modules()
            for root in _FORBIDDEN_MASTER_AGENT_ROOTS
        )


class TestNoImplementationLeakage:
    """*"Provide abstract interfaces only... No implementation."* Every
    abstract method body in `channels.py` must be exactly `...` — nothing
    that could be mistaken for a real microphone, speaker, or network
    call."""

    def _abstract_method_bodies(self) -> dict[str, list[ast.stmt]]:
        path = PACKAGE / "channels.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        bodies: dict[str, list[ast.stmt]] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name in (
                "VoiceInput", "TextInput", "VoiceOutput", "TextOutput",
            ):
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        bodies[f"{node.name}.{item.name}"] = item.body
        return bodies

    def test_every_channel_class_is_found(self):
        bodies = self._abstract_method_bodies()
        assert set(bodies) == {
            "VoiceInput.receive", "TextInput.receive",
            "VoiceOutput.emit", "TextOutput.emit",
        }

    def test_every_method_body_is_exactly_ellipsis(self):
        for name, body in self._abstract_method_bodies().items():
            assert len(body) == 1, name
            statement = body[0]
            assert isinstance(statement, ast.Expr), name
            assert isinstance(statement.value, ast.Constant), name
            assert statement.value.value is Ellipsis, name

    def test_no_audio_related_identifier_appears_anywhere_in_the_package(self):
        """Prose may say *"no microphone"* — that is the point of this
        package. What must never appear is one of these words used as an
        actual identifier: a parameter, a variable, a function, or a
        class."""
        forbidden_identifiers = (
            "microphone", "speaker", "audio_bytes", "sample_rate",
            "wav", "mp3", "pcm",
        )
        names: set[str] = set()
        for _, tree in _modules():
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    names.add(node.name.lower())
                elif isinstance(node, ast.arg):
                    names.add(node.arg.lower())
                elif isinstance(node, ast.Name):
                    names.add(node.id.lower())
        offenders = [w for w in forbidden_identifiers if w in names]
        assert offenders == []


class TestDoesNotDuplicateExistingComponents:
    def test_no_component_type_from_earlier_components_is_redeclared(self):
        defined: set[str] = set()
        for _, tree in _modules():
            for node in ast.walk(tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                    defined.add(node.name)
        for owned_elsewhere in (
            "FounderRuntime", "FounderIdentity", "FounderSession",
            "ConversationMemory", "ConversationEngine", "ResponsePipeline",
            "ResponseComposer", "IntentClassifier", "ContextAssembler",
            "Speaker", "Transcriber",
        ):
            assert owned_elsewhere not in defined

    def test_communication_response_holds_no_conversation_engine_dependency(self):
        """`response.py` must import nothing beyond the standard library
        — see its own docstring for why."""
        path = PACKAGE / "response.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
            elif isinstance(node, ast.Import):
                imports.update(a.name for a in node.names)
        assert not any(m.startswith("master_agent") for m in imports)

    def test_communication_request_holds_no_master_agent_dependency(self):
        path = PACKAGE / "request.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
            elif isinstance(node, ast.Import):
                imports.update(a.name for a in node.names)
        assert not any(m.startswith("master_agent") for m in imports)
