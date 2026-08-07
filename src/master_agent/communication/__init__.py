"""Unified Communication Layer — C32.

The abstraction that lets Somesh be reached through any channel while
`conversation_engine.ConversationEngine` stays completely unaware of the
transport. Five files, exactly the brief's own list:
`request.CommunicationRequest` (one shape, however the founder spoke),
`response.CommunicationResponse` (a package of strings, never audio),
`channels` (four abstract interfaces plus `OutputMode`, no implementation),
`router.CommunicationRouter` (request → engine → response → channel
names), and `engine.CommunicationEngine` (the one public door, holding
whatever channels a caller actually registered).

It performs no speech recognition, no text-to-speech, and no desktop
automation, and it never mutates `FounderRuntime` — see `engine.py`'s own
docstring for the shape of that guarantee, and
`tests/test_communication.py` for the AST guard that checks it.
"""
from __future__ import annotations

from master_agent.communication.channels import (
    OutputMode,
    TextInput,
    TextOutput,
    VoiceInput,
    VoiceOutput,
)
from master_agent.communication.engine import ChannelNotRegistered, CommunicationEngine
from master_agent.communication.request import CommunicationRequest, Source
from master_agent.communication.response import CommunicationResponse
from master_agent.communication.router import CommunicationRouter, RoutedResponse

__all__ = [
    "ChannelNotRegistered",
    "CommunicationEngine",
    "CommunicationRequest",
    "CommunicationResponse",
    "CommunicationRouter",
    "OutputMode",
    "RoutedResponse",
    "Source",
    "TextInput",
    "TextOutput",
    "VoiceInput",
    "VoiceOutput",
]
