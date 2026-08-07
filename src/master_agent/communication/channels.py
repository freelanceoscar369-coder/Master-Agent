"""Channel interfaces — the shape of a channel, never one that works. C32.

*"Provide abstract interfaces only... No implementation. No microphone.
No speakers. No pyttsx. No whisper. No Azure. No ElevenLabs."* Four
`ABC`s, each with exactly one abstract method and no body beyond `...` —
none of them can be instantiated, which is Python's own enforcement of
*"no implementation"* rather than a convention this module merely states.
`tests/test_communication.py::TestNoImplementationLeakage` reads every
method body in this file by AST and asserts none of them is anything but
`...`.

## Why there are four interfaces and not two

A channel that can both listen and speak (a future wearable, say) would
implement two of these, not one merged interface — `receive()` and
`emit()` are different capabilities with different failure modes, and a
text terminal that only displays has no business being asked to
`receive()`. This mirrors `master_agent.voice`'s own split
(`Transcriber`/`Speaker`) without importing it: that package is a
different, differently-scoped subsystem (its own docstrings cite
`ARCHITECTURE.md §4.8`, predating C1), and depending on it here would
blur this package's own boundary for no benefit — every fact this module
needs about "a channel" is expressible in `CommunicationRequest` and
`CommunicationResponse` alone.

## `OutputMode` lives here, not in `router.py`

*"Output Modes... Must be runtime selectable."* Three members, and the
brief names them twice with two different spellings — `OutputMode.BOTH`
once, `VOICE_AND_TEXT` once, in its own *"Output Modes"* list. The second
is followed: it is the section that actually enumerates the type's
members, so `VOICE_AND_TEXT` is the real value and `router.py`'s own
docstring records the reconciliation.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from master_agent.communication.request import CommunicationRequest
from master_agent.communication.response import CommunicationResponse


class OutputMode(str, Enum):
    """Which output channel(s) a response should reach. Closed at three
    — the brief's own list — and never derived from what a `Router`
    happens to have registered; `VOICE_AND_TEXT` is a founder's choice,
    checked against what is actually wired only when a response is about
    to be emitted (`engine.ChannelNotRegistered`)."""

    VOICE_ONLY = "voice_only"
    TEXT_ONLY = "text_only"
    VOICE_AND_TEXT = "voice_and_text"


class VoiceInput(ABC):
    """A channel that turns spoken founder input into one request. How
    the audio became text — which model, which vendor, whether there was
    audio at all — is entirely this interface's implementer's concern
    and none of this package's."""

    @abstractmethod
    def receive(self) -> CommunicationRequest: ...


class TextInput(ABC):
    """A channel that turns typed or dictated founder input into one
    request. Structurally identical to `VoiceInput` — the two are kept
    separate because *what produced the text* is a fact worth keeping,
    not because the contract differs."""

    @abstractmethod
    def receive(self) -> CommunicationRequest: ...


class VoiceOutput(ABC):
    """A channel that can say a response aloud. `emit()` takes the whole
    `CommunicationResponse`, not a bare string, so an implementer reads
    `response.spoken` — never `response.text` directly — and the
    text/spoken-text distinction stays honoured at the one place it
    matters."""

    @abstractmethod
    def emit(self, response: CommunicationResponse) -> None: ...


class TextOutput(ABC):
    """A channel that can display a response. Mirrors `VoiceOutput`; an
    implementer reads `response.display`."""

    @abstractmethod
    def emit(self, response: CommunicationResponse) -> None: ...
