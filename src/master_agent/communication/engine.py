"""`CommunicationEngine` — the one public door into C32.

```
   VoiceInput.receive() ──┐
                          ├──►  CommunicationRequest  ──►  CommunicationEngine.handle()
   TextInput.receive() ───┘                                     │
                                                                  ▼
                                                          CommunicationRouter.route()
                                                                  │
                                                     RoutedResponse | None
                                                                  │
                                        ┌─────────────────────────┴──────────────────────┐
                                        ▼                                                  ▼
                              VoiceOutput.emit(response)                       TextOutput.emit(response)
                          (only if "voice" ∈ channels)                    (only if "text" ∈ channels)
```

Everything this class does was already built by `CommunicationRouter`
(routing) and `ConversationEngine` (answering) — its own job is holding
the channels a caller actually registered and refusing to pretend one
exists that was not. *"Somesh can answer through voice, text, [or] both
simultaneously... without Conversation Engine knowing which"* is true
here structurally: `_emit()` reads `RoutedResponse.channels`, which the
router derived from `OutputMode` alone, and calls whichever registered
output objects match — `ConversationEngine.reply()` was already called,
and returned, before this method runs.

## Registered channels, not constructed ones

*"No implementation"* means this package builds no `VoiceOutput` or
`TextOutput` of its own — `voice_output`/`text_output` are constructor
parameters, and both default to `None`. A mode that needs a channel that
was not registered raises `ChannelNotRegistered` rather than silently
skipping half a `VOICE_AND_TEXT` response: an honest failure, in the same
spirit as every other absence in this codebase being stated rather than
assumed.
"""
from __future__ import annotations

from master_agent.communication.channels import TextOutput, VoiceOutput
from master_agent.communication.request import CommunicationRequest
from master_agent.communication.router import (
    CommunicationRouter,
    OutputMode,
    RoutedResponse,
)
from master_agent.conversation_engine import ConversationEngine
from master_agent.memory.conversation import ConversationMemory


class ChannelNotRegistered(RuntimeError):
    """The current `OutputMode` needs an output channel this engine was
    never given. Raised rather than silently dropped — a founder who
    switched to `VOICE_AND_TEXT` with no voice channel wired should learn
    that, not lose half of every reply without being told."""


class CommunicationEngine:
    """One `CommunicationRouter`, and up to two registered output
    channels. Reuses the `ConversationMemory` its `ConversationEngine`
    already holds — `history()` reads that same instance, never a
    second one, so "reuse Conversation Memory, do not duplicate" is a
    structural fact rather than an intention."""

    __slots__ = ("_conversation", "_router", "_text_output", "_voice_output")

    def __init__(
        self,
        *,
        conversation_engine: ConversationEngine,
        conversation: ConversationMemory,
        mode: OutputMode = OutputMode.TEXT_ONLY,
        voice_output: VoiceOutput | None = None,
        text_output: TextOutput | None = None,
    ) -> None:
        if not isinstance(conversation, ConversationMemory):
            raise TypeError("conversation must be a ConversationMemory")
        if voice_output is not None and not isinstance(voice_output, VoiceOutput):
            raise TypeError("voice_output must be a VoiceOutput, or None")
        if text_output is not None and not isinstance(text_output, TextOutput):
            raise TypeError("text_output must be a TextOutput, or None")

        self._router = CommunicationRouter(
            conversation_engine=conversation_engine, mode=mode
        )
        self._conversation = conversation
        self._voice_output = voice_output
        self._text_output = text_output

    @property
    def mode(self) -> OutputMode:
        return self._router.mode

    def handle(self, request: CommunicationRequest) -> RoutedResponse | None:
        """Route one request, emit through whatever it names, return
        what was routed. `None` means silence — nothing was emitted,
        because there was nothing to say."""
        routed = self._router.route(request)
        if routed is None:
            return None
        self._emit(routed)
        return routed

    def history(self) -> tuple[object, ...]:
        """The session's own turns, read through the one
        `ConversationMemory` this engine and its `ConversationEngine`
        both point to — never a second history."""
        return tuple(self._conversation.turns())

    def _emit(self, routed: RoutedResponse) -> None:
        for channel in routed.channels:
            if channel == "voice":
                if self._voice_output is None:
                    raise ChannelNotRegistered(
                        "the current mode needs a voice output, but none "
                        "was registered"
                    )
                self._voice_output.emit(routed.response)
            elif channel == "text":
                if self._text_output is None:
                    raise ChannelNotRegistered(
                        "the current mode needs a text output, but none "
                        "was registered"
                    )
                self._text_output.emit(routed.response)
