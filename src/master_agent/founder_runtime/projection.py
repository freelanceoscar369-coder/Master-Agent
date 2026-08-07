"""Existing contracts, carried to the surface without being reshaped.

Two projections live here. Neither derives anything: one hands back C22's
own `as_dict()` unchanged, and the other maps conversation turns one-to-one
into the row shape the Founder Surface already renders.

## The environment projection is C22's, verbatim

`EnvironmentIntelligence.as_dict()` is already *"the data contract C20
Presence consumes"* by its own docstring. Re-keying it here — `summary` →
`environmentSummary`, `graph` → `capabilityGraph` — would create the one
thing C18 named as the reason it uses the Kernel API's own parameter names:
*"there is no translation table to drift."*

So the four contracts the C23 brief names arrive under C22's own section
names, and `CONTRACT_SECTIONS` records the correspondence **as a checked
fact rather than a transform**: a test asserts every named section is
present in a real projection, so a rename in C22 fails here loudly instead
of arriving at the surface as a missing panel.

## The conversation projection can never speak

`ConversationMemory` (Layer 1) holds turns whose speaker is `user` or
`system`. The Founder Surface's row shape admits a third role,
`assistant` — and **nothing in this path may ever produce one.**

C23's rule is *"do not invent responses"*, and C21's own suite already
enforces the mirror of it: `projectConversation` *"cannot construct an
assistant row that was not already in `entries`"*. If this projection could
mint an `assistant` role, the surface's non-synthesis guarantee would be
defeated one layer below where it is tested. So any speaker that is not
`user` maps to `system`, `assistant` is unreachable by construction, and a
test asserts it across every speaker string.

Every other field the surface accepts is reported **absent** rather than
guessed: a conversation turn is not an execution, has no execution id, is
not streaming, was superseded by nothing, and carries no mission card.
Filling any of them would be the invention this component exists to avoid.

## Purity

No clock, no I/O, no randomness. Entry identity is the turn's position —
`turn-1`, `turn-2` — which is addressing, not identity invention: it is
stable for a given transcript and needs nothing `ConversationMemory` does
not already have.
"""
from __future__ import annotations

from typing import Any

from master_agent.environment_intelligence import EnvironmentIntelligence
from master_agent.memory.conversation import ConversationMemory

#: The four contracts the C23 brief names, beside the C22 section each one
#: actually arrives under. **Documentation and a test fixture — never a
#: transform.** Nothing reads this to rename anything.
CONTRACT_SECTIONS: tuple[tuple[str, str], ...] = (
    ("EnvironmentSummary", "summary"),
    ("CapabilityGraph", "graph"),
    ("UserProfile", "profile"),
    ("PreferenceModel", "preferences"),
)

#: The roles a projected conversation row may carry. `assistant` is
#: deliberately absent: see the module docstring.
PROJECTED_ROLES: tuple[str, ...] = ("user", "system")


def environment_projection(
    intelligence: EnvironmentIntelligence,
) -> dict[str, Any]:
    """C22's own projection, unchanged.

    One line of work, and that is the point: the derivation, the key
    order and the evidence attached to every inference are C22's, and a
    second opinion about any of them would be a second Environment
    Intelligence.
    """
    if not isinstance(intelligence, EnvironmentIntelligence):
        raise TypeError(
            "environment_projection takes the EnvironmentIntelligence that "
            "derive_intelligence() returned; this layer derives none of its "
            "own"
        )
    return intelligence.as_dict()


def conversation_projection(
    conversation: ConversationMemory,
) -> dict[str, Any]:
    """Session turns, in the row shape the Founder Surface renders.

    Text is carried **verbatim and untrimmed** — C21's own test asserts
    strict, untrimmed equality against what it was given, and a
    projection that tidied whitespace here would fail it from below.
    """
    if not isinstance(conversation, ConversationMemory):
        raise TypeError(
            "conversation_projection takes the session's ConversationMemory"
        )

    entries = [
        {
            "id": f"turn-{position}",
            "role": "user" if turn.speaker == "user" else "system",
            "text": turn.text,
            "at": turn.at.isoformat(),
            "executionId": None,
            "streaming": False,
            "supersededBy": None,
            "missions": [],
        }
        for position, turn in enumerate(conversation.turns(), start=1)
    ]
    return {"entries": entries}
