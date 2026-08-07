"""`ResponsePipeline` — classify, assemble, compose, record. One turn. C31.

The whole of *"only answers"* lives in this module's shape: four steps,
none of which touches a plugin, a broker, a provider, or `desktop/`. Step
four records the founder's turn and — only if a reply was composed — one
turn of Somesh's own, through Layer 1's `ConversationMemory.record()`
directly, never through `FounderSession.record()` (which C29 fixes to the
`"user"` speaker on purpose; see `founder_identity/session.py`).

## `assistant` stays unreachable one layer further out

C23's conversation projection maps every speaker that is not `"user"` to
the role `"system"` — `assistant` is unreachable by construction, and its
own suite asserts so across every speaker string. This module records
Somesh's turns under the speaker `SOMESH` (`"somesh"`), not `"user"` and
not `"assistant"`, so that guarantee holds through a third layer without
being restated or weakened. `tests/test_conversation_engine.py` asserts
the rendered role set is exactly `{"user", "system"}` after a real
pipeline turn.

## One turn in, at most two turns recorded

A pipeline run always records the founder's own turn — a reply is never a
precondition for "the founder was heard." It records a second turn only
when the composer actually produced one; `Intent.UNKNOWN` and a build
request answered with `None`... no such branch exists: every recognised
intent composes a sentence, and only `UNKNOWN` produces no reply and no
second turn, which is the honest state for speech this engine did not
recognise.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from master_agent.conversation_engine.composer import ResponseComposer
from master_agent.conversation_engine.context import (
    ContextAssembler,
    ConversationContext,
    DesktopStatus,
)
from master_agent.conversation_engine.intent import Intent, IntentClassifier
from master_agent.founder_identity import FounderIdentity, FounderSession
from master_agent.founder_runtime import FounderRuntime
from master_agent.memory.conversation import ConversationMemory

#: The speaker recorded for Somesh's own turns. Never `"user"` (C29's own
#: reservation) and never `"assistant"` (C23's own reservation) — a third
#: word, so neither guarantee has to bend to make room for this one.
SOMESH = "somesh"


@dataclass(frozen=True)
class ConversationTurn:
    """What one call to `ResponsePipeline.handle()` produced. `reply` is
    `None` exactly when `intent` is `Intent.UNKNOWN` — never in any other
    case, and a test asserts the correspondence directly."""

    intent: Intent
    reply: str | None
    context: ConversationContext


class ResponsePipeline:
    """Four collaborators, held and never re-constructed: an
    `IntentClassifier`, a `ContextAssembler`, a `ResponseComposer`, and
    the one `ConversationMemory` this engine was wired to. `handle()` is
    the only method that reads a wire-shaped input (a founder's raw
    text) and the only one that writes."""

    __slots__ = (
        "_assembler",
        "_classifier",
        "_composer",
        "_conversation",
        "_identity",
        "_runtime",
        "_session",
    )

    def __init__(
        self,
        *,
        runtime: FounderRuntime,
        identity: FounderIdentity,
        session: FounderSession,
        conversation: ConversationMemory,
        classifier: IntentClassifier | None = None,
        assembler: ContextAssembler | None = None,
        composer: ResponseComposer | None = None,
    ) -> None:
        if not isinstance(runtime, FounderRuntime):
            raise TypeError("runtime must be a FounderRuntime")
        if not isinstance(identity, FounderIdentity):
            raise TypeError("identity must be a FounderIdentity")
        if not isinstance(session, FounderSession):
            raise TypeError("session must be a FounderSession")
        if not isinstance(conversation, ConversationMemory):
            raise TypeError("conversation must be a ConversationMemory")

        self._runtime = runtime
        self._identity = identity
        self._session = session
        self._conversation = conversation
        self._classifier = classifier or IntentClassifier()
        self._assembler = assembler or ContextAssembler()
        self._composer = composer or ResponseComposer()

    def handle(
        self,
        text: str,
        *,
        moment: datetime,
        desktop: DesktopStatus | None = None,
    ) -> ConversationTurn:
        """Classify, assemble, compose, record. In that order, and no
        step is skipped for any intent — even `UNKNOWN` is classified and
        given a context, so a caller inspecting `ConversationTurn` never
        has to special-case the empty reply."""
        if not isinstance(text, str):
            raise TypeError("handle takes the founder's utterance as a string")

        intent = self._classifier.classify(text)
        context = self._assembler.assemble(
            runtime=self._runtime,
            founder_name=self._identity.founder_name,
            assistant_name=self._identity.assistant_name,
            session_active=self._session.active,
            last_founder_utterance=self._session.last_founder_utterance(),
            desktop=desktop,
            moment=moment,
        )

        self._conversation.record("user", text)
        reply = self._compose(intent, context)
        if reply is not None:
            self._conversation.record(SOMESH, reply)

        return ConversationTurn(intent=intent, reply=reply, context=context)

    def _compose(self, intent: Intent, context: ConversationContext) -> str | None:
        """One branch per recognised intent. `Intent.UNKNOWN` is the only
        one that returns `None` — nothing here fabricates a reply to
        speech it did not recognise."""
        if intent is Intent.GREETING:
            return self._composer.greeting(self._identity, context)
        if intent is Intent.CONTINUATION:
            return self._composer.continuation(self._session)
        if intent is Intent.STATUS_QUERY:
            return self._composer.status(context)
        if intent is Intent.ACTIVITY_QUERY:
            return self._composer.activity(context)
        if intent is Intent.PRIORITY_QUERY:
            return self._composer.priority(context)
        if intent is Intent.BUILD_REQUEST:
            return self._composer.build_request(context)
        return None
