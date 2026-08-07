"""Layer 1 — Conversation Memory: the current session's turn history.

In-process only, never persisted — see MEMORY_ARCHITECTURE.md §3 ("What
should never be remembered"): raw conversation text is exactly the kind
of content that shouldn't outlive the process it happened in by default.
Nothing here writes to disk, the network, or Layer 3.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class ConversationTurn:
    speaker: str  # "user" | "system"
    text: str
    at: datetime = field(default_factory=lambda: datetime.now(UTC))


class ConversationMemory:
    """Holds the current session's turns in memory. Bounded so a very
    long-running session can't grow this without limit — the oldest turns
    fall off past `max_turns` rather than accumulating forever."""

    def __init__(self, max_turns: int = 200) -> None:
        self._max_turns = max_turns
        self._turns: list[ConversationTurn] = []

    def record(self, speaker: str, text: str) -> None:
        self._turns.append(ConversationTurn(speaker=speaker, text=text))
        if len(self._turns) > self._max_turns:
            self._turns = self._turns[-self._max_turns :]

    def turns(self) -> list[ConversationTurn]:
        return list(self._turns)

    def last_user_text(self) -> str | None:
        for turn in reversed(self._turns):
            if turn.speaker == "user":
                return turn.text
        return None
