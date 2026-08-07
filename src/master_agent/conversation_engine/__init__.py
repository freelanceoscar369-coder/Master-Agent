"""Founder Conversation Engine — C31.

Turns Somesh from a greeting system into a real conversational entity, and
answers only. Five collaborators, exactly the brief's own list:
`IntentClassifier` (which of six things was asked), `ContextAssembler`
(what is true right now, never invented), `ResponseComposer` (one human
sentence, never a leaked internal name), `ResponsePipeline` (the four-step
orchestration), and `ConversationEngine` (the one public door).

It never executes a desktop action, never launches an application, never
creates a mission, never plans, and never mutates `FounderRuntime` — see
`engine.py`'s own docstring for the import-graph guarantee each of those
rests on, and `tests/test_conversation_engine.py` for the AST guard that
checks it.
"""
from __future__ import annotations

from master_agent.conversation_engine.composer import (
    FORBIDDEN_INTERNAL_TERMS,
    ExposedInternals,
    ResponseComposer,
)
from master_agent.conversation_engine.context import (
    ContextAssembler,
    ConversationContext,
    DesktopStatus,
)
from master_agent.conversation_engine.engine import ConversationEngine
from master_agent.conversation_engine.intent import Intent, IntentClassifier
from master_agent.conversation_engine.pipeline import (
    SOMESH,
    ConversationTurn,
    ResponsePipeline,
)

__all__ = [
    "FORBIDDEN_INTERNAL_TERMS",
    "SOMESH",
    "ContextAssembler",
    "ConversationContext",
    "ConversationEngine",
    "ConversationTurn",
    "DesktopStatus",
    "ExposedInternals",
    "Intent",
    "IntentClassifier",
    "ResponseComposer",
    "ResponsePipeline",
]
