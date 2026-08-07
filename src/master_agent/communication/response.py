"""`CommunicationResponse` — a package of strings, never an audio signal. C32.

*"Do not synthesize audio. Do not perform TTS. Only package responses."*
This module holds three optional strings and produces no sound, no
phoneme, no audio buffer, and no file. `spoken_text` and `display_text`
default to `None`, meaning *"identical to `text`"* — a response that
never distinguished the two is not a smaller response, it is the ordinary
one, and `spoken`/`display` below make that fallback explicit rather than
leaving every caller to remember it.

## Why this module imports nothing

Not even `master_agent.conversation_engine` — a `CommunicationResponse`
is built from whatever text a caller hands it (in this package,
`router.py`, from a `ConversationEngine`'s own reply). Holding no
dependency on where that text came from is what lets a future channel
construct one directly, in a test or otherwise, without pulling in the
whole Conversation Engine to do it.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommunicationResponse:
    """`text` is the canonical content. `spoken_text` and `display_text`
    exist only to let voice and text diverge when a caller has a reason
    to — abbreviating what is spoken versus what is shown, say — and
    default to `None`, meaning *"use `text`."*"""

    text: str
    spoken_text: str | None = None
    display_text: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("text must be a non-empty string")
        for name, value in (
            ("spoken_text", self.spoken_text),
            ("display_text", self.display_text),
        ):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{name} must be a non-empty string, or None")

    @property
    def spoken(self) -> str:
        """What a `VoiceOutput` should say. `spoken_text` if this
        response set one, `text` otherwise — never `None`, so a voice
        channel never has to fall back on its own."""
        return self.spoken_text if self.spoken_text is not None else self.text

    @property
    def display(self) -> str:
        """What a `TextOutput` should show. Same fallback as `spoken`,
        mirrored for the other channel."""
        return self.display_text if self.display_text is not None else self.text

    def as_dict(self) -> dict[str, object]:
        return {
            "text": self.text,
            "spoken_text": self.spoken_text,
            "display_text": self.display_text,
        }
