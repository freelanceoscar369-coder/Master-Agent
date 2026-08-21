"""What ROLE the founder's utterance plays — the Brain's answer to
"is this an answer, or something else entirely".

## The assumption this module exists to delete

The composition root used to read, in as many words:

    # A question was asked last turn, so this message is its answer.
    if pending is not None:
        intent_result = mission_service.intent_layer.clarify(...)

and carried a stated limit underneath it conceding that an unrelated
request typed while a question was open would be swallowed as the answer.
That is one assumption doing two jobs. A pending clarification is
**context** — it tells us a question is open. It does not own the next
thing the founder says.

The live consequence was not subtle. Asked *"Which file should I read?"*,
a founder answering *"nothing thanks"* had `nothing thanks` taken as a
filename, planned as a file-reading objective, and was asked the same
question again. Nothing in the loop could end.

## Why this is not a second classifier

`ConversationEngine` runs FIRST and answers the six conversational shapes
it owns (greeting, continuation, status, activity, priority, capability).
Only input it escalates — input it takes to be work — reaches here. So
this module deliberately holds **no** second definition of greeting or
continuation; `Intent.GREETING`/`Intent.CONTINUATION` remain that layer's,
via `founder_identity`'s own recognisers, and `ORDINARY_CONVERSATION`
exists in the vocabulary below without this function ever needing to
return it for recognised conversation.

## The one duplication here, named rather than hidden (Rule 10)

`clauses()` and `opens_an_instruction()` below are the same logic as the
private `_clauses`/`_opens_an_instruction` in `conversation_engine/intent
.py`. Sharing one definition was tried first and is **architecturally
forbidden**: `tests/test_conversation_engine.py::TestBoundaries` walks
that package's imports by AST and permits exactly four `master_agent`
roots — `conversation_engine`, `founder_identity`, `founder_runtime`,
`memory`. The Conversation Engine may not import the Brain, deliberately.

So this is a real duplication, kept because the alternative is breaking an
enforced isolation boundary to save a dozen lines. It is low-risk to hold:
both copies answer a narrow, stable question about English word order, and
neither is a place new phrases accumulate. If the two ever need to move
together, the honest fix is a shared primitive under a root BOTH sides may
import — a change to that boundary, decided deliberately, not an import
added quietly on one side.

## Why the decision is structural rather than a phrase list

Growing a phrase list is what the standing rule forbids, and it does not
work anyway: every list has a cliff edge one inserted word away. The
signals below are about sentence *shape* — does it end in a question mark,
does it open with an imperative verb, is the whole utterance an
abandonment — so an unseen phrasing is handled by the shape it shares with
seen ones, not by having been enumerated.
"""
from __future__ import annotations

import re

from collections.abc import Sequence
from enum import Enum


class UtteranceRole(str, Enum):
    """What the founder's message is DOING, relative to the conversation.

    Distinct from `Intent` (what they want) and from agency (who acts, see
    `brain/agency.py`). A message has exactly one role.
    """

    #: A fresh request. The default when nothing is pending.
    NEW_OBJECTIVE = "new_objective"
    #: Data supplying the field an open question asked for.
    ANSWER_TO_CLARIFICATION = "answer_to_clarification"
    #: A question back at us — about the question, or about something
    #: already said. Never field data.
    FOLLOW_UP = "follow_up"
    #: Abandon what is pending. Not a failure and not an answer.
    CANCEL_OR_STOP = "cancel_or_stop"
    #: A different or altered objective, stated while something else was
    #: open. The open thing yields; it does not swallow this.
    MODIFY_OR_REDIRECT = "modify_or_redirect"
    #: Conversation carrying no work. Owned by `ConversationEngine`, which
    #: runs before this and answers it; present here so the vocabulary is
    #: complete rather than because this module competes for it.
    ORDINARY_CONVERSATION = "ordinary_conversation"


# --- Sentence structure (moved from conversation_engine/intent.py) -------

#: Where one instruction ends and the next begins. Sentence enders, plus
#: the joins that introduce a second thing to do -- "and then", ", then",
#: a bare "and". Splitting here is what makes recognisers clause-local:
#: words in different clauses are not doing the same job, and treating
#: them as though they were is exactly how "show me what you propose ...
#: then use the revised profile" became a question about capabilities.
_CLAUSE_SPLIT = re.compile(r"[.!?;\n]+|,\s*(?:then|and)\b|\s+and\s+then\s+|\s+and\s+|,\s+")

#: Verbs that open an instruction. Not a list of everything a founder
#: might say -- a clause starting with one of these is *telling the system
#: to do something*, which is the only fact needed here.
_OPERATIONAL_OPENERS = frozenset({
    "check", "read", "open", "create", "make", "write", "save", "search",
    "find", "use", "run", "build", "send", "delete", "move", "rename",
    "copy", "download", "upload", "install", "update", "compare",
    "identify", "summarise", "summarize", "highlight", "extract", "close",
    "navigate", "click", "type", "fill", "apply", "book", "schedule",
    "add", "remove", "organise", "organize", "sort", "rank", "list",
    "review", "analyse", "analyze", "draft", "revise", "improve", "fix",
    "complete", "finish", "start", "launch", "go", "take", "get", "put",
})

#: Words that sit in front of a verb without changing what it is:
#: "also create", "then read", "please open", "now check".
_LEAD = frozenset({
    "also", "then", "next", "and", "please", "now", "first",
    "finally", "afterwards", "after", "so", "just",
})

_STRIP = ".,!?;:'\"()"


def _tokens(clause: str) -> list[str]:
    return [word.strip(_STRIP) for word in clause.split()]


def clauses(lowered: str) -> list[str]:
    """The utterance's clauses, in order, empty ones dropped."""
    return [part.strip() for part in _CLAUSE_SPLIT.split(lowered) if part.strip()]


def opens_an_instruction(clause: str) -> bool:
    """Does this clause tell the system to do something?

    Read from the clause's FIRST word only. "check what you can improve"
    is an instruction; "what can you check" is a question. The difference
    is entirely word order, which is why this is structural rather than a
    membership test over the whole clause.
    """
    tokens = _tokens(clause)
    while tokens and tokens[0] in _LEAD:
        tokens = tokens[1:]
    if not tokens:
        return False
    return tokens[0] in _OPERATIONAL_OPENERS


# --- Role signals --------------------------------------------------------

#: Ways a founder closes something without answering it. Matched as the
#: WHOLE utterance (modulo the filler below), never as a substring: a
#: folder named "Stop That Nonsense" contains "stop" and is an answer.
_ABANDONMENT: tuple[str, ...] = (
    "nothing", "none", "never mind", "nevermind", "forget it",
    "forget about it", "forget that", "cancel", "cancel that", "stop",
    "stop it", "no thanks", "no thank you", "dont bother", "don't bother",
    "do not bother", "leave it", "skip it", "no need", "not now",
    "drop it", "let it go", "abandon", "nah", "nope", "no",
)

#: Words that carry no meaning of their own around an abandonment. What is
#: left of "nothing thanks" after "nothing" is removed must be only these,
#: or the utterance is saying something more than "stop".
_ABANDON_FILLER = frozenset({
    "", "thanks", "thank", "you", "please", "somesh", "actually", "just",
    "that", "it", "for", "now", "ok", "okay", "really", "then", "about",
    "the", "this", "im", "i", "m", "we", "lets", "let", "us", "s",
})

#: Question openers. Only decisive on their own when the utterance also
#: speaks TO the assistant -- see `_is_question`.
_INTERROGATIVES = frozenset({
    "why", "what", "how", "who", "when", "where", "which", "whose", "whom",
})

_ASSISTANT_WORDS = frozenset({"you", "your", "youre", "somesh"})


def _is_abandonment(lowered: str) -> bool:
    """Is this utterance, as a whole, a request to stop?"""
    for phrase in _ABANDONMENT:
        if phrase not in lowered:
            continue
        remainder = lowered.replace(phrase, " ", 1)
        if all(word.strip(_STRIP) in _ABANDON_FILLER for word in remainder.split()):
            return True
    return False


def _is_question(lowered: str) -> bool:
    """Is the founder asking, rather than telling or answering?

    A question mark is decisive. A bare interrogative opener is NOT, on
    its own: while a question is open, "Where I keep my notes" is a
    perfectly good answer to "Where should I create it?", and reading it
    as a question would strand the founder in the same loop this module
    exists to end. An interrogative opener therefore counts only when the
    utterance also speaks to the assistant -- "what do you mean", "why are
    you asking" -- which an answer never does.
    """
    if lowered.rstrip().endswith("?"):
        return True
    tokens = _tokens(lowered)
    if tokens and tokens[0] in _INTERROGATIVES:
        return bool(set(tokens) & _ASSISTANT_WORDS)
    return False


#: How many words an answer can be before it stops looking like a value.
#: "Quarterly Report", "the second one", "C:/Users/Onkar/Desktop" are all
#: values; a sentence of eight words that is neither a question nor an
#: instruction is something else, and that is the one case structure
#: genuinely cannot settle on its own -- see `structural_role`.
_VALUE_WORD_LIMIT = 4


def structural_role(
    text: str,
    *,
    awaiting_answer: bool = False,
    options: Sequence[str] = (),
) -> tuple[UtteranceRole, bool]:
    """`(role, confident)` from sentence shape alone. No model call.

    `confident` is False for exactly one shape: a longer statement
    arriving while a question is open, which is neither a question, an
    instruction, an offered option, nor short enough to read as a value.
    That is the genuine ambiguity -- an odd multi-word folder name and a
    change of subject look identical to structure -- and it is where the
    Brain's reasoning door earns its keep (`IntentLayer.decide_role`).

    Everything else is settled here and costs nothing. This matters: the
    ordinary answer ("Research") must not acquire a model call's latency
    or price just because a harder case exists.
    """
    lowered = (text or "").strip().lower()
    if not lowered:
        return UtteranceRole.ORDINARY_CONVERSATION, True

    if awaiting_answer:
        offered = {str(option).strip().lower() for option in options if str(option).strip()}
        if lowered in offered:
            return UtteranceRole.ANSWER_TO_CLARIFICATION, True
        if _is_abandonment(lowered):
            return UtteranceRole.CANCEL_OR_STOP, True
        if _is_question(lowered):
            return UtteranceRole.FOLLOW_UP, True
        if any(opens_an_instruction(clause) for clause in clauses(lowered)):
            return UtteranceRole.MODIFY_OR_REDIRECT, True
        if len(_tokens(lowered)) <= _VALUE_WORD_LIMIT:
            return UtteranceRole.ANSWER_TO_CLARIFICATION, True
        # A long statement while a question is open. Structure is out of
        # evidence; the default stays what it was, and the flag says it
        # was a default rather than a finding.
        return UtteranceRole.ANSWER_TO_CLARIFICATION, False

    if _is_abandonment(lowered):
        return UtteranceRole.CANCEL_OR_STOP, True
    if any(opens_an_instruction(clause) for clause in clauses(lowered)):
        return UtteranceRole.NEW_OBJECTIVE, True
    if _is_question(lowered):
        return UtteranceRole.FOLLOW_UP, True
    return UtteranceRole.NEW_OBJECTIVE, True


def role_of(
    text: str,
    *,
    awaiting_answer: bool = False,
    options: Sequence[str] = (),
) -> UtteranceRole:
    """What role this utterance plays, from structure alone.

    The structural half of the decision, kept as its own callable so it
    can be read and tested without a provider anywhere near it.
    `IntentLayer.decide_role()` is what production calls -- it is this,
    plus the Brain's reasoning door for the one shape this cannot settle.

    `awaiting_answer` says only that a question is open — it is context,
    and it is deliberately not enough on its own to claim the utterance.
    `options`, when the open question offered choices, is checked first and
    wins outright: a founder picking an offered option is answering, even
    when the option happens to read like a refusal.

    ## Stated limit (Rule 10)

    A value that is genuinely indistinguishable from a refusal — a folder
    the founder really wants called `nothing` — is read as a refusal when
    no options were offered. That is a deliberate trade: the alternative,
    which shipped, made *every* refusal into a filename and left no way
    out of the question. Offering `options` removes the ambiguity wherever
    a producer can enumerate the choices.
    """
    role, _confident = structural_role(
        text, awaiting_answer=awaiting_answer, options=options,
    )
    return role
