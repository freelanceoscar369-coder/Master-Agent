"""`GreetingEngine` — one human sentence, never an AI disclaimer. C29.

*"Founder: Good morning Somesh. Somesh: Good morning. I'm awake.
Everything is ready."* Not `"As an AI..."`, not a re-introduction, not a
list of subsystems. This module composes that sentence from
`FounderIdentity` (who is speaking) and `FounderContext` (what is actually
ready), and nothing else — no model call, no template fetched from a
provider, no randomness. Two calls with the same identity, context and
time of day produce the same words.

## Why forbidden phrases are checked, not just avoided

`FORBIDDEN_PHRASES` names the wording C29 explicitly forbids —
`"as an ai"`, `"i cannot"`, `"language model"` — and every string this
module can return is checked against it before being returned. Avoiding
the phrasing by habit is how it reappears the first time this file is
edited by someone who has not read this docstring; checking it structurally
is what keeps it out.
"""
from __future__ import annotations

from master_agent.founder_identity.context import FounderContext
from master_agent.founder_identity.identity import FounderIdentity

#: Wording this module must never produce. Lower-cased substrings, checked
#: against every composed sentence before it is returned.
FORBIDDEN_PHRASES: tuple[str, ...] = (
    "as an ai",
    "i cannot",
    "i'm an ai",
    "i am an ai",
    "language model",
    "large language model",
)


class ForbiddenWording(RuntimeError):
    """A composed sentence contained wording this module may never say.
    Raised rather than silently rewritten — a caller should learn its
    template produced disclaimer language, not have it quietly patched."""


def _time_of_day_greeting(hour: int) -> str:
    if 5 <= hour < 12:
        return "Good morning"
    if 12 <= hour < 17:
        return "Good afternoon"
    if 17 <= hour < 22:
        return "Good evening"
    return "Good evening"


def _readiness_clause(context: FounderContext) -> str:
    if context.environment_ready and context.conversation_ready:
        return "Everything is ready."
    if not context.environment_ready and not context.conversation_ready:
        return "I'm still getting settled — give me a moment."
    return "Most things are ready; a couple of things are still coming online."


def greet(identity: FounderIdentity, context: FounderContext) -> str:
    """Compose the greeting reply. Three short sentences, in the brief's
    own cadence: a time-of-day greeting, a state-of-being, a readiness
    fact — never a subsystem name.
    """
    if not isinstance(identity, FounderIdentity):
        raise TypeError("greet takes a FounderIdentity")
    if not isinstance(context, FounderContext):
        raise TypeError("greet takes a FounderContext")

    opening = _time_of_day_greeting(context.moment.hour)
    sentence = f"{opening}. I'm awake. {_readiness_clause(context)}"

    lowered = sentence.lower()
    for phrase in FORBIDDEN_PHRASES:
        if phrase in lowered:
            raise ForbiddenWording(
                f"a composed greeting contained forbidden wording {phrase!r}"
            )
    return sentence


def is_greeting(text: str) -> bool:
    """Whether a founder utterance is a greeting addressed to Somesh.

    Deliberately narrow: it recognises the brief's own examples
    ("Good morning Somesh", "Morning Somesh") and does not attempt to
    classify open-ended founder speech, which would be the intent
    recognition this component is not.
    """
    lowered = text.strip().lower()
    if not lowered:
        return False
    openings = ("good morning", "good afternoon", "good evening", "morning", "hello", "hi")
    return any(lowered.startswith(opening) for opening in openings)
