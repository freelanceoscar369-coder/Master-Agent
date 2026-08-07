"""`CommunicationRouter` — the one place a channel and an intent meet. C32.

```
   CommunicationRequest
        │
        ├─ names a mode switch? ──yes──►  flip mode, acknowledge, stop
        │                                  (ConversationEngine never sees it)
        no
        │
        ▼
   ConversationEngine.reply(request.content, moment=request.timestamp)
        │
        ├─ no reply (Intent.UNKNOWN) ──►  RoutedResponse is None — silence
        │
        yes
        ▼
   CommunicationResponse(text=turn.reply)
        │
        ▼
   RoutedResponse(response, mode, channels)
```

*"Conversation Engine returns intent. Communication layer changes
routing. Nothing else changes."* Read literally, this asks C31's
`IntentClassifier` to grow a mode-switch intent — but C31 is a complete,
audited-pending component (`Engineering/HEALTH_C31.md`), and *"switch to
text"* is not conversational content in the first place: it is an
instruction about *how Somesh should answer*, which is precisely the
"transport" C31's own boundary says it must never know about
(`conversation_engine/engine.py`'s own docstring). Recognising the phrase
here — before `ConversationEngine` ever sees it — satisfies the
requirement's own intent more literally than editing C31 would: **the
routing decision is made by the layer that owns routing**, and
`ConversationEngine.reply()` is never called for a switch request at all,
so it stays exactly as unaware of channels as C31's own boundary
requires.

## `OutputMode.BOTH` vs `VOICE_AND_TEXT`

Recorded here rather than silently picked: the brief names the enum
`OutputMode.BOTH` once and lists its members as `VOICE_AND_TEXT` once.
`channels.OutputMode` uses `VOICE_AND_TEXT`, the value that actually
appears in the section enumerating the type's members. See
`channels.py`'s own docstring for the same note at the point a reader
would ask.

## Silence is a real outcome, not a bug

`route()` returns `None` when `ConversationEngine` recognised nothing —
`Intent.UNKNOWN`, C31's own honest non-reply. A router that manufactured
a filler sentence here (*"I didn't catch that"*) would be inventing
Somesh's own words, which is exactly what C29/C31 already refuse to do.
Whichever caller drives this router (`engine.py`, in this package)
decides what silence means for its own channels — most naturally,
nothing is emitted.
"""
from __future__ import annotations

from dataclasses import dataclass

from master_agent.communication.channels import OutputMode
from master_agent.communication.request import CommunicationRequest
from master_agent.communication.response import CommunicationResponse
from master_agent.conversation_engine import ConversationEngine

#: How a founder addresses Somesh before an instruction. Stripped before
#: phrase matching so "Somesh, switch to text." and "switch to text" are
#: recognised as the same instruction.
_ADDRESS_PREFIXES: tuple[str, ...] = ("somesh,", "somesh")

#: Closed vocabulary — the brief's own two examples plus their ordinary
#: phrasings. Not fuzzy-matched, the same discipline
#: `founder_identity.continuity.is_continuation_request` already uses:
#: guessing at looser phrasing risks treating unrelated founder speech as
#: a routing instruction.
_SWITCH_TO_TEXT_PHRASES: tuple[str, ...] = (
    "switch to text",
    "switch to text mode",
    "switch to text only",
    "go to text",
    "text mode",
)
_SWITCH_TO_VOICE_PHRASES: tuple[str, ...] = (
    "switch to voice",
    "switch back to voice",
    "switch to voice mode",
    "switch to voice only",
    "go to voice",
    "voice mode",
)
_SWITCH_TO_BOTH_PHRASES: tuple[str, ...] = (
    "switch to both",
    "switch to voice and text",
    "turn on both",
    "voice and text mode",
)

#: What the router says after a switch. Fixed, and keyed by the mode
#: switched *to* — never composed from free text, so there is nothing
#: here for a forbidden phrase to hide inside.
_ACKNOWLEDGEMENTS: dict[OutputMode, str] = {
    OutputMode.TEXT_ONLY: "Switched to text.",
    OutputMode.VOICE_ONLY: "Switched to voice.",
    OutputMode.VOICE_AND_TEXT: "Switched to voice and text.",
}

#: Which output channel names a mode reaches. A closed, total mapping —
#: every `OutputMode` member appears exactly once, checked by a test.
_CHANNELS_FOR_MODE: dict[OutputMode, tuple[str, ...]] = {
    OutputMode.VOICE_ONLY: ("voice",),
    OutputMode.TEXT_ONLY: ("text",),
    OutputMode.VOICE_AND_TEXT: ("voice", "text"),
}


@dataclass(frozen=True)
class RoutedResponse:
    """One `CommunicationResponse`, and which channel name(s) it should
    reach. `mode` is carried alongside `channels` — a derived, redundant
    field on purpose, so a caller can log *why* without recomputing it."""

    response: CommunicationResponse
    mode: OutputMode
    channels: tuple[str, ...]


def _normalize(text: str) -> str:
    lowered = text.strip().lower().rstrip(".!")
    for prefix in _ADDRESS_PREFIXES:
        if lowered.startswith(prefix):
            lowered = lowered[len(prefix):].strip()
            break
    return lowered


def _requested_mode(text: str) -> OutputMode | None:
    """Which mode this utterance asks for, or `None` if it asks for
    none. Checked as three closed sets, most specific first: "voice and
    text" would also satisfy a naive substring check against "voice", so
    the combined phrases are matched before either single-channel list."""
    normalized = _normalize(text)
    if normalized in _SWITCH_TO_BOTH_PHRASES:
        return OutputMode.VOICE_AND_TEXT
    if normalized in _SWITCH_TO_TEXT_PHRASES:
        return OutputMode.TEXT_ONLY
    if normalized in _SWITCH_TO_VOICE_PHRASES:
        return OutputMode.VOICE_ONLY
    return None


class CommunicationRouter:
    """Holds one `ConversationEngine` (never constructs one) and the
    current `OutputMode`. `route()` is the only method that reads a
    request or changes the mode."""

    __slots__ = ("_conversation_engine", "_mode")

    def __init__(
        self,
        *,
        conversation_engine: ConversationEngine,
        mode: OutputMode = OutputMode.TEXT_ONLY,
    ) -> None:
        if not isinstance(conversation_engine, ConversationEngine):
            raise TypeError("conversation_engine must be a ConversationEngine")
        if not isinstance(mode, OutputMode):
            raise TypeError("mode must be an OutputMode")
        self._conversation_engine = conversation_engine
        self._mode = mode

    @property
    def mode(self) -> OutputMode:
        return self._mode

    def route(self, request: CommunicationRequest) -> RoutedResponse | None:
        if not isinstance(request, CommunicationRequest):
            raise TypeError("route takes a CommunicationRequest")

        requested = _requested_mode(request.content)
        if requested is not None:
            self._mode = requested
            return RoutedResponse(
                response=CommunicationResponse(text=_ACKNOWLEDGEMENTS[requested]),
                mode=requested,
                channels=_CHANNELS_FOR_MODE[requested],
            )

        turn = self._conversation_engine.reply(
            request.content, moment=request.timestamp
        )
        if turn.reply is None:
            return None

        return RoutedResponse(
            response=CommunicationResponse(text=turn.reply),
            mode=self._mode,
            channels=_CHANNELS_FOR_MODE[self._mode],
        )
