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

import re

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
    CAPABILITY_QUERY = "capability_query"
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


#: "What can you do?" — recognised HERE, in the Brain's own taxonomy,
#: because this is the layer that answers the founder.
#:
#: It previously lived as a list of exact phrases in `brain/intent.py`,
#: consulted by the desktop composition root *before* the Conversation
#: Engine was ever asked. Two problems followed: the routing decision sat
#: in the composition root rather than in the Brain, and the match was
#: contiguous-substring, so "what are your capabilities" was recognised
#: while "what are your *current* capabilities" was not — one inserted
#: word dropped the founder into the Planner, which cannot plan a
#: question and answered "I can't do that with what I'm currently able
#: to do."
#:
#: A longer phrase list does not fix that, it only moves the cliff edge
#: ("what can you *actually* do" breaks identically). Recognition is
#: therefore STRUCTURAL, over word tokens, so inserted adverbs,
#: qualifiers and trailing clauses are all irrelevant:
#:
#:   * the stem `capabilit` anywhere (capability / capabilities), or
#:   * an interrogative ABOUT THE ASSISTANT — a "what" question naming
#:     the assistant (you/your) together with an ability word.
#:
#: Naming the assistant is what keeps this narrow: "What happened to my
#: previous task?" is a "what" question with no "you", and stays out.
_CAPABILITY_STEM = "capabilit"
#: Naming this system. Kept from the previous recogniser, where it
#: was one of three loose conditions; here it only ever narrows a
#: clause that already mentions capability.
_ASSISTANT_WORDS = frozenset({"you", "your", "youre"})

#: Where one instruction ends and the next begins. Sentence enders, plus
#: the joins that introduce a second thing to do -- "and then", ", then",
#: a bare "and". Splitting here is what makes every recogniser below
#: clause-local: words in different clauses are not doing the same job,
#: and treating them as though they were is exactly how "show me what you
#: propose ... then use the revised profile" became a question about
#: Kalpavriksha's abilities.
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

#: Words that carry no instruction of their own. Whatever is left of a
#: clause after its conversational phrase is removed must be only these,
#: or the clause is about something more than the phrase.
_FILLER = frozenset({
    "", "please", "somesh", "hey", "hi", "hello", "ok", "okay", "so",
    "just", "actually", "really", "currently", "right", "now", "tell",
    "me", "us", "again", "the", "a", "an", "is", "it", "s", "you", "your",
    "what", "and", "about", "for", "to", "of", "quick", "question",
    "curious", "wondering", "im", "i", "m", "can", "could", "would",
    "do", "does", "did", "am", "are", "be", "with", "on", "in", "at",
    "my", "our", "this", "that", "there", "here", "much", "many",
})

_STRIP = ".,!?;:'\"()"


def _words(lowered: str) -> set[str]:
    """Word tokens with punctuation stripped, so "do?" matches "do"."""
    return {word.strip(_STRIP) for word in lowered.split()}


def _clauses(lowered: str) -> list[str]:
    """The utterance's clauses, in order, empty ones dropped."""
    return [part.strip() for part in _CLAUSE_SPLIT.split(lowered) if part.strip()]


def _opens_an_instruction(clause: str) -> bool:
    """Does this clause tell the system to do something?

    Read from the clause's FIRST word only. "check what you can improve"
    is an instruction; "what can you check" is a question. The difference
    is entirely word order, which is why this is structural rather than a
    membership test over the whole clause.
    """
    tokens = [word.strip(_STRIP) for word in clause.split()]
    # Words that sit in front of a verb without changing what it is:
    # "also create", "then read", "please open", "now check". Skipping
    # them is why the verb is found where a founder actually puts it.
    lead = {"also", "then", "next", "and", "please", "now", "first",
            "finally", "afterwards", "after", "so", "just"}
    while tokens and tokens[0] in lead:
        tokens = tokens[1:]
    if not tokens:
        return False
    return tokens[0] in _OPERATIONAL_OPENERS


def _phrase_is_the_clause(clause: str, phrase: str) -> bool:
    """Is this clause essentially just the phrase?

    A recogniser may claim an utterance only when its intent describes the
    utterance as a whole (see the module docstring). So the phrase has to
    BE the clause, not merely occur inside one: "what needs my attention"
    is a question, and "find what needs my attention in this report" is a
    job, and the difference is everything that surrounds the phrase.
    """
    if phrase not in clause:
        return False
    remainder = clause.replace(phrase, " ")
    return all(word.strip(_STRIP) in _FILLER for word in remainder.split())


def _claims_utterance(lowered: str, phrases: tuple[str, ...]) -> bool:
    """One of `phrases` describes this whole utterance.

    Two conditions, both structural: some clause is essentially just the
    phrase, and no clause anywhere is an instruction. The second is what
    stops "check system status and save it to a file" -- whose first
    clause does contain the phrase -- from being answered as a question
    while the founder waits for a file.
    """
    clauses = _clauses(lowered)
    if not clauses:
        return False
    if any(_opens_an_instruction(clause) for clause in clauses):
        return False
    return any(
        _phrase_is_the_clause(clause, phrase)
        for clause in clauses
        for phrase in phrases
    )


#: A question ABOUT this system, anchored at the start of its clause.
#:
#: Anchoring is the whole point. The previous recogniser asked whether
#: "what", an assistant word and an ability word appeared ANYWHERE in the
#: utterance, so a hundred-word instruction supplied all three by
#: accident -- "show me what you propose" and "then use the revised
#: profile" -- and a founder's real objective was answered with a list of
#: things Kalpavriksha can do. One word, `use`, was the difference.
_CAPABILITY_FORMS: tuple[re.Pattern[str], ...] = (
    # "what can you do", "what exactly can you do", "what are your
    # capabilities", "what are your current browser capabilities"
    re.compile(r"^what\b(?:\s+\w+){0,3}?\s+(?:can|could|do|does|are|is)\s+(?:you|your)\b"),
    # "can you use a browser", "could you handle this kind of thing"
    re.compile(r"^(?:can|could)\s+you\b(?:\s+\w+){0,3}?\s+(?:do|use|handle|help|manage|access|work)\b"),
    # "tell me what you can do", "tell me what capabilities you have"
    re.compile(r"^tell\s+me\s+(?:about\s+)?what\s+(?:you|your|capabilit)"),
    # "list your capabilities", "describe your capabilities"
    re.compile(r"^(?:list|describe|show\s+me)\s+(?:your\s+|the\s+)?capabilit"),
    # "what capabilities do you have"
    re.compile(r"^what\b(?:\s+\w+){0,3}?\s+capabilit"),
)


def _is_capability_inquiry(lowered: str) -> bool:
    """Does this utterance ask what Kalpavriksha can do?

    High precision on purpose (and by instruction): when this cannot show
    that the utterance itself is the question, it says no and the Mission
    pipeline decides. An objective wrongly answered here never reaches the
    Planner at all, which is a far worse failure than a question wrongly
    escalated -- the founder gets a paragraph about browsers instead of
    their work.
    """
    clauses = _clauses(lowered)
    if not clauses:
        return False
    # An instruction anywhere means this utterance is not a question about
    # abilities, whatever its first clause looks like.
    if any(_opens_an_instruction(clause) for clause in clauses):
        return False
    if any(form.match(clause) for clause in clauses for form in _CAPABILITY_FORMS):
        return True
    # The word itself, in a clause that is not an instruction and does name
    # this system: "how can I extend your capabilities", "I want to know
    # what are your current capabilities". Saying `capabilities` about
    # `you` is about as direct as the question gets, and the guard above
    # has already ruled out the utterance being a job.
    return any(
        _CAPABILITY_STEM in clause and _words(clause) & _ASSISTANT_WORDS
        for clause in clauses
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

        if _claims_utterance(lowered, _STATUS_PHRASES):
            return Intent.STATUS_QUERY
        if _claims_utterance(lowered, _ACTIVITY_PHRASES):
            return Intent.ACTIVITY_QUERY
        if _claims_utterance(lowered, _PRIORITY_PHRASES):
            return Intent.PRIORITY_QUERY
        # Before BUILD_REQUEST on purpose: "what can you do and how do we
        # add more capabilities" asks ABOUT capability, it does not
        # instruct anything to be built.
        if _is_capability_inquiry(lowered):
            return Intent.CAPABILITY_QUERY
        if any(lowered.startswith(opener) for opener in _BUILD_OPENERS):
            return Intent.BUILD_REQUEST

        return Intent.UNKNOWN
