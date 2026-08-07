"""`CommunicationRequest` — one shape, however the founder spoke. C32.

*"Somesh receives exactly one `ConversationRequest`."* (The brief's prose
names it `ConversationRequest`; the brief's own required-files list names
the module `request.py` and the type it must hold `CommunicationRequest`
— the second, more specific instruction is followed literally, and the
first is honoured in spirit: whichever channel the founder used, exactly
one object crosses into the rest of this package.)

Typed, spoken, dictated, or a channel that does not exist yet — every one
of them ends here, as the same four fields. `source` records *which*
channel produced this request, and nothing downstream branches on it: the
whole point of `Source.FUTURE` existing before a fourth channel does is
that adding one is a new `VoiceInput`/`TextInput` subclass and nothing
else, never a new case in this dataclass.

## No desktop. No runtime. No execution

Structural rather than promised: this module imports nothing beyond the
standard library. A `CommunicationRequest` cannot reach the desktop, the
Founder Runtime, or a Kernel, because it holds no reference to any of
them — it is four plain values, immutable the moment it is built.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Source(str, Enum):
    """Which channel produced a request. Closed at three members because
    that is what the brief names — `FUTURE` is not a placeholder for
    "unknown," it is the brief's own third example (*"future wearable...
    future mobile app"*), reserved for a channel that does not exist in
    this codebase yet but will not need a new `Source` member when it
    arrives."""

    VOICE = "voice"
    TEXT = "text"
    FUTURE = "future"


@dataclass(frozen=True)
class CommunicationRequest:
    """Four fields, and nothing a channel could not have supplied.

    Frozen — a request that could be edited after `VoiceInput.receive()`
    or `TextInput.receive()` produced it would let something downstream
    quietly rewrite what the founder actually said.
    """

    source: Source
    content: str
    timestamp: datetime
    conversation_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.source, Source):
            raise TypeError("source must be a Source")
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("content must be a non-empty string")
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        if not isinstance(self.conversation_id, str) or not self.conversation_id.strip():
            raise ValueError("conversation_id must be a non-empty string")

    def as_dict(self) -> dict[str, object]:
        return {
            "source": self.source.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "conversation_id": self.conversation_id,
        }
