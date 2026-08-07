"""`FounderSession` — the current conversation, and nothing before it. C29.

The brief draws this distinction directly: *"Represents current founder
conversation. Not memory. Not history. Only active session."* Layer 1
(`memory.conversation.ConversationMemory`) already holds turn history —
duplicating it here would be a second history with its own chance to
disagree with the first. So `FounderSession` holds **no turns of its
own**. It is handed the session's `ConversationMemory` at construction and
answers questions about *now* — is a conversation active, what did the
founder just say — by reading that memory's own tail, never by keeping a
second copy.
"""
from __future__ import annotations

from master_agent.memory.conversation import ConversationMemory


class FounderSession:
    """A thin lens onto the session's own `ConversationMemory`.

    Holds one reference, copies nothing, derives nothing `ConversationMemory`
    does not already expose. A session with no memory wired is a valid,
    inactive state — the same "absent is first-class" discipline
    `FounderRuntime` already uses for its own optional sources.
    """

    __slots__ = ("_conversation",)

    def __init__(self, conversation: ConversationMemory | None = None) -> None:
        if conversation is not None and not isinstance(
            conversation, ConversationMemory
        ):
            raise TypeError(
                "conversation must be a ConversationMemory, or be omitted"
            )
        self._conversation = conversation

    @property
    def active(self) -> bool:
        """True once at least one turn has been recorded this session."""
        if self._conversation is None:
            return False
        return bool(self._conversation.turns())

    def last_founder_utterance(self) -> str | None:
        """What the founder most recently said, or `None` if nothing has
        been said yet. `ConversationMemory.last_user_text()`, unchanged —
        this method exists so a caller reads it through the identity
        surface's own vocabulary rather than reaching past it."""
        if self._conversation is None:
            return None
        return self._conversation.last_user_text()

    def record(self, text: str) -> None:
        """One founder turn, recorded through Layer 1's own `record`.

        Raises if no `ConversationMemory` is wired — recording into a
        session that holds none would be inventing a place to put it.
        """
        if self._conversation is None:
            raise RuntimeError(
                "this session has no ConversationMemory wired; there is "
                "nowhere to record a turn"
            )
        self._conversation.record("user", text)

    def as_dict(self) -> dict[str, object]:
        return {
            "active": self.active,
            "last_founder_utterance": self.last_founder_utterance(),
        }
