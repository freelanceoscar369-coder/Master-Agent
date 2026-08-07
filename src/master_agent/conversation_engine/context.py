"""`ContextAssembler` — everything the composer is allowed to know. C31.

*"He may summarize. He may prioritize. He may never invent."* This module
is where that line is drawn structurally: `ConversationContext` holds only
facts already published by `FounderRuntime` (C23), and `ContextAssembler`
adds no derivation beyond folding an optional gap into a boolean. Every
field a composer reads traces back to a real call on a real component —
never a guess, never a default standing in for an unknown.

## Desktop status arrives as a value, not a door

*"Desktop Status"* is one of the brief's own named inputs, and this module
takes it as a plain `DesktopStatus` value rather than importing anything
from `desktop/`, `desktop_operator/` or `founder_edition/`. Two reasons:

1. **Layering.** `founder_edition/` (C24/C30) is the composition root that
   will eventually hold both this package and the desktop layer together.
   A conversation engine that imported `founder_edition` would depend on
   its own future caller — the same inversion C23's own door avoids by
   holding no Kernel.
2. **The boundary itself.** *"Conversation Engine MUST NOT execute desktop
   actions [or] launch applications."* Not importing `desktop.execution`,
   `desktop_operator`, or `desktop.perception` at all is a stronger
   guarantee than importing them and merely not calling anything — a
   guarantee `tests/test_conversation_engine.py` checks by AST.

Whoever composes this engine (a future `founder_edition` wiring step, most
likely) is responsible for translating its own `DesktopLayer.readiness()`
into one `DesktopStatus` before calling in — a boolean and a short string,
never a live object.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from master_agent.founder_runtime import FounderRuntime


@dataclass(frozen=True)
class DesktopStatus:
    """The one desktop fact this engine is allowed to know: is it ready.
    `detail` is carried for logging only — no composer method reads it."""

    ready: bool
    detail: str = ""


@dataclass(frozen=True)
class ConversationContext:
    """Every fact a `ResponseComposer` may draw on for one reply. Frozen —
    a context that could be edited mid-composition would let one branch
    of a reply describe a different moment than another."""

    moment: datetime
    founder_name: str
    assistant_name: str
    environment_ready: bool
    conversation_ready: bool
    presence_registered: bool
    presence_complete: bool
    attention_needed: tuple[str, ...]
    desktop_ready: bool | None
    session_active: bool
    last_founder_utterance: str | None

    def as_dict(self) -> dict[str, object]:
        return {
            "moment": self.moment.isoformat(),
            "founder_name": self.founder_name,
            "assistant_name": self.assistant_name,
            "environment_ready": self.environment_ready,
            "conversation_ready": self.conversation_ready,
            "presence_registered": self.presence_registered,
            "presence_complete": self.presence_complete,
            "attention_needed": list(self.attention_needed),
            "desktop_ready": self.desktop_ready,
            "session_active": self.session_active,
            "last_founder_utterance": self.last_founder_utterance,
        }


class ContextAssembler:
    """Stateless. `assemble()` reads `FounderRuntime`'s own three
    projections once each and folds `Coverage`'s own gaps into a tuple of
    domain names — the one piece of interpretation this module performs,
    and it is a filter, not an invention."""

    def assemble(
        self,
        *,
        runtime: FounderRuntime,
        founder_name: str,
        assistant_name: str,
        session_active: bool,
        last_founder_utterance: str | None,
        desktop: DesktopStatus | None,
        moment: datetime,
    ) -> ConversationContext:
        if not isinstance(runtime, FounderRuntime):
            raise TypeError(
                "assemble takes the FounderRuntime this engine was wired to"
            )
        if desktop is not None and not isinstance(desktop, DesktopStatus):
            raise TypeError("desktop must be a DesktopStatus, or None")
        if moment.tzinfo is None:
            raise ValueError("moment must be timezone-aware")

        presence = runtime.presence()
        coverage = presence.get("coverage")

        if coverage is None:
            presence_registered = False
            presence_complete = False
            attention_needed: tuple[str, ...] = ()
        else:
            presence_registered = bool(coverage.get("domains"))
            presence_complete = bool(coverage.get("complete"))
            # A gap's `domain` is `""` only for the sentinel "nothing is
            # watched at all" gap (`vigilance.attest()`'s own reason) —
            # that fact is already carried by `presence_registered` being
            # `False`, so it is not repeated here as a named item.
            attention_needed = tuple(
                gap["domain"] for gap in coverage.get("gaps", []) if gap.get("domain")
            )

        return ConversationContext(
            moment=moment,
            founder_name=founder_name,
            assistant_name=assistant_name,
            environment_ready=runtime.environment() is not None,
            conversation_ready=runtime.conversation() is not None,
            presence_registered=presence_registered,
            presence_complete=presence_complete,
            attention_needed=attention_needed,
            desktop_ready=desktop.ready if desktop is not None else None,
            session_active=session_active,
            last_founder_utterance=last_founder_utterance,
        )
