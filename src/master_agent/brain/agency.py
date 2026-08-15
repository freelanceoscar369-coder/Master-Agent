"""Who acts, and who benefits — derived from grammar, never from subject.

ADR-0024 Decision 5 requires an `Intent` to preserve the agency and
beneficiary the founder expressed. This module derives them, and it is
the whole of that derivation: `IntentLayer.parse()` stamps the result
onto every `Intent` it produces, so all twelve typed parsers and the
generic fallback gain it in one place rather than twelve.

## What it looks at, and what it refuses to look at

Every rule below is about **pronouns and sentence structure**. Not one of
them mentions trading, houses, folders, or any other subject. That is the
point: ADR-0024 §6 forbids a phrase catalogue, and the founder's probes
are probes, not implementation. *"Get me fluent in Portuguese"* is
handled by the same rule as *"Teach me trading"* because they share a
grammatical shape, not a topic.

English marks the two roles this module cares about structurally:

| Construction | Example | Actor | Beneficiary |
|---|---|---|---|
| catenative *help* | *"Help me learn trading"* | both | founder |
| benefactive *for me* | *"Buy a house for me"* | system | founder |
| ditransitive V + me | *"Teach me trading"* | system | founder |
| bare imperative | *"Learn trading"* | system | **unknown** |

## Why the last row says `unknown` and not `system`

*"Learn trading"* means Kalpavriksha both acts and gains — the founder
said so explicitly, and ADR-0024's own table records the beneficiary as
Kalpavriksha. **This module cannot derive that half**, and says so
rather than guessing.

Knowing that *learn* leaves its competence with the actor, while *fetch*
leaves its result with someone else, is lexical semantics of the verb.
Deriving it would require a verb list — and a verb list is the phrase
catalogue ADR-0024 §6 rules out, differing from the founder's five probes
only in length. So the beneficiary of a bare imperative is honestly
`UNKNOWN_ROLE`.

That is sufficient for the correction this contract exists to protect.
What went wrong in `bb36c9f` was *"Learn trading"* being answered as
though the **founder** were the learner. `beneficiary=UNKNOWN_ROLE` does
not claim that, and it is now structurally distinct from
*"Teach me trading"* (`FOUNDER`) and *"Help me learn trading"*
(`actor=BOTH`) — which is the distinction the audit found missing. An
honest gap is not the same as the wrong answer.

## Why the actor of a bare imperative is `SYSTEM` and not `unknown`

This is derived from the channel, not guessed from the words. Text
arriving here was typed or spoken by the founder *to Kalpavriksha*.
An instruction addressed to the system has the system as its actor;
that is what makes it an instruction rather than a remark. The founder
naming themselves as an additional participant is what the rules above
detect.

## Stated limitation

These rules cover English imperatives carrying first-person pronouns.
They do not parse arbitrary language, and they are not a substitute for
one: passive voice, third-party beneficiaries (*"send it to John"*),
reported speech and conditionals are all outside them and correctly
yield `UNKNOWN_ROLE` rather than a confident wrong answer. Widening this
is a language-understanding problem, and ADR-0024 §6 is explicit that
until it is solved, unknown beats invented.
"""
from __future__ import annotations

from master_agent.planner.plan import BOTH, FOUNDER, SYSTEM, UNKNOWN_ROLE

#: First-person object pronouns. The founder naming themselves as a
#: participant is the one signal every rule below turns on.
_FIRST_PERSON_OBJECT = frozenset({"me", "us"})

#: Verbs that take a catenative complement meaning "the subject assists
#: while someone else also acts" — *"help me learn"*, *"assist me in
#: choosing"*. Two words, and they are here as a **grammatical
#: construction**, not a topic list: they change who the actor is, which
#: no other verb in the language does by itself. Everything downstream of
#: this set is structure, never subject matter.
_ASSISTANCE_VERBS = frozenset({"help", "assist"})

_STRIP = ".,!?;:'\"()"


def _tokens(text: str) -> list[str]:
    return [word.strip(_STRIP) for word in text.strip().lower().split()]


def roles(text: str) -> tuple[str, str]:
    """`(actor, beneficiary)` for one founder utterance.

    Never raises and never returns anything outside `ROLES`. Pure — the
    same text always produces the same pair, with no clock, no I/O and no
    model call, which is what keeps the Intent Layer the thing §3.1 says
    it is.
    """
    if not isinstance(text, str):
        return UNKNOWN_ROLE, UNKNOWN_ROLE

    words = _tokens(text)
    if not words:
        return UNKNOWN_ROLE, UNKNOWN_ROLE

    # 1. Catenative assistance: "help me <verb>". Checked first because it
    #    also matches rule 3's shape, and it is the only construction that
    #    makes the founder a co-actor rather than only a recipient.
    if words[0] in _ASSISTANCE_VERBS and len(words) > 1 and words[1] in _FIRST_PERSON_OBJECT:
        return BOTH, FOUNDER

    # 2. Benefactive prepositional phrase: "... for me". Position-free --
    #    "buy a house for me" and "for me, buy a house" mean the same
    #    thing about who benefits.
    for index, word in enumerate(words[:-1]):
        if word == "for" and words[index + 1] in _FIRST_PERSON_OBJECT:
            return SYSTEM, FOUNDER

    # 3. Ditransitive imperative: an opening verb whose immediate object
    #    is the founder -- "teach me trading", "tell me how to ...",
    #    "get me fluent in Portuguese". The founder is the recipient of
    #    whatever the verb delivers.
    #
    #    Deliberately positional rather than a search for "me" anywhere:
    #    "create a folder on my Desktop" names a possession, not a
    #    recipient, and must not be read as a benefactive.
    if len(words) > 1 and words[1] in _FIRST_PERSON_OBJECT:
        return SYSTEM, FOUNDER

    # 4. Bare imperative addressed to this system. The actor follows from
    #    the channel; the beneficiary does not follow from anything this
    #    module can see. See the module docstring.
    return SYSTEM, UNKNOWN_ROLE
