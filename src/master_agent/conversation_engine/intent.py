"""`IntentClassifier` — which of six things the founder is asking. C31.

A closed, narrow vocabulary — the same discipline `founder_identity.greeting
.is_greeting` and `.continuity.is_continuation_request` already use, and
this module reuses both rather than re-classifying either. There is no
model call here and no fuzzy matching: an utterance that names none of the
six recognised shapes is `Intent.UNKNOWN`, honestly, rather than forced
into the closest guess.

## Why `BUILD_REQUEST` is recognised at all

The Conversation Engine "must never plan" — but recognising that a founder
*asked* for something to be built is not planning it. `Intent.BUILD_REQUEST`
exists so `ResponseComposer` can answer honestly (*"that's not something I
start myself"*) instead of falling through to `UNKNOWN` and staying
silent, which would read as Somesh simply not having heard the founder.
"""
from __future__ import annotations

from enum import Enum

from master_agent.founder_identity import is_continuation_request, is_greeting


class Intent(str, Enum):
    """The six shapes this engine answers, plus the honest seventh:
    nothing recognised. Closed — a component that needs a new member here
    is doing more than answering."""

    GREETING = "greeting"
    CONTINUATION = "continuation"
    STATUS_QUERY = "status_query"
    ACTIVITY_QUERY = "activity_query"
    PRIORITY_QUERY = "priority_query"
    BUILD_REQUEST = "build_request"
    UNKNOWN = "unknown"


#: Phrases recognised as "how is the system doing". Closed rather than
#: fuzzy — the brief's own example ("How's the system?") plus its ordinary
#: phrasings.
_STATUS_PHRASES: tuple[str, ...] = (
    "how's the system",
    "how is the system",
    "system status",
    "status check",
    "is everything ok",
    "is everything okay",
    "is everything working",
)

#: Phrases recognised as "what are you doing right now".
_ACTIVITY_PHRASES: tuple[str, ...] = (
    "what are you doing",
    "what're you doing",
    "what's happening",
    "what is happening",
    "what's going on",
    "what is going on",
)

#: Phrases recognised as "what should I focus on".
_PRIORITY_PHRASES: tuple[str, ...] = (
    "what should i work on",
    "what should i do",
    "what do i need to do",
    "what needs my attention",
    "what needs attention",
    "priorities",
    "what's my priority",
    "what is my priority",
)

#: Verbs that open a request to build, make, or start something new. A
#: prefix match, not a substring match — "rebuild trust" does not open
#: with "build " and is correctly left `UNKNOWN` rather than misread as a
#: construction request.
_BUILD_OPENERS: tuple[str, ...] = (
    "build ",
    "create ",
    "make me ",
    "set up ",
    "automate ",
    "launch a ",
    "start building",
)


class IntentClassifier:
    """Stateless. `classify()` is a pure function of the text it is given
    — no memory, no context, no model, and the same input always returns
    the same `Intent`."""

    def classify(self, text: str) -> Intent:
        if not isinstance(text, str):
            raise TypeError("classify takes the founder's utterance as a string")

        lowered = text.strip().lower()
        if not lowered:
            return Intent.UNKNOWN

        # Continuation and greeting are checked first and via C29's own
        # recognisers — this module holds no second definition of either.
        if is_continuation_request(text):
            return Intent.CONTINUATION
        if is_greeting(text):
            return Intent.GREETING

        if any(phrase in lowered for phrase in _STATUS_PHRASES):
            return Intent.STATUS_QUERY
        if any(phrase in lowered for phrase in _ACTIVITY_PHRASES):
            return Intent.ACTIVITY_QUERY
        if any(phrase in lowered for phrase in _PRIORITY_PHRASES):
            return Intent.PRIORITY_QUERY
        if any(lowered.startswith(opener) for opener in _BUILD_OPENERS):
            return Intent.BUILD_REQUEST

        return Intent.UNKNOWN
