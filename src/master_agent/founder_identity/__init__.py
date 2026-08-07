"""Founder Identity Layer — C29.

Somesh, not an assistant. This package owns exactly seven things the brief
names — a name, a session, a greeting, a continuation, a context, and
nothing else: `FounderIdentity`, `FounderSession`, `greet`/`is_greeting`,
`is_continuation_request`/`continuity_reply`, and `FounderContext`.

It never plans a mission, never executes on the desktop, never routes to a
model, and never decides strategy — those remain exactly where C1–C28 left
them. The only door this package reaches through is `FounderRuntime` (C23);
`tests/test_founder_identity.py` walks every module's imports by AST to
keep it that way.
"""
from __future__ import annotations

from master_agent.founder_identity.context import FounderContext, founder_context
from master_agent.founder_identity.continuity import (
    continuity_reply,
    is_continuation_request,
)
from master_agent.founder_identity.greeting import (
    ForbiddenWording,
    greet,
    is_greeting,
)
from master_agent.founder_identity.identity import (
    DEFAULT_TRAITS,
    GREETING_STYLES,
    FounderIdentity,
)
from master_agent.founder_identity.session import FounderSession

__all__ = [
    "DEFAULT_TRAITS",
    "GREETING_STYLES",
    "ForbiddenWording",
    "FounderContext",
    "FounderIdentity",
    "FounderSession",
    "continuity_reply",
    "founder_context",
    "greet",
    "is_continuation_request",
    "is_greeting",
]
