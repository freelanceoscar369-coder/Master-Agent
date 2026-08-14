"""`advise` — the Brain's answer when a goal is understood but cannot be
carried out directly.

## The semantic error this module exists to correct

Three different things were being collapsed into one sentence at the
founder surface:

| the founder said            | goal understood | directly executable |
|-----------------------------|-----------------|---------------------|
| *"Open a website"*          | no — which one? | —                   |
| *"Learn trading"*           | **yes**         | **no**              |
| *"Open github.com"*         | yes             | yes                 |

The middle row is the one that had no home. `IntentLayer` resolved it
(it is not ambiguous — the founder said exactly what they want), the
`Planner` was then asked to plan it, correctly answered *"the available
capabilities cannot achieve this objective"* (`NO_STEPS`), and the
desktop surface flattened that into *"I can't do that with what I'm
currently able to do."*

That sentence is false. **Capability absence is not evidence that the
goal was not understood**, and it is not a reason to end the exchange.
A founder who says *"learn trading"* or *"buy a house for me"* has
issued a clear command; what they must hear back is that it is
understood and what the first real moves are — not a refusal.

## Who the command is about — a founder correction, recorded

The first version of this module got the *subject* wrong. Told *"learn
trading"*, it answered by coaching the founder: *"I'd start by settling
which market you actually care about, then get you reading a single
instrument daily…"*

**That is not what the instruction means.** The founder's correction,
verbatim in intent: *"Learn trading means Kalpavriksha itself must learn
trading. It does not mean 'teach the Founder trading' or 'give the
Founder advice about how to learn trading.'"*

The founder is not asking to be taught, advised, coached or given a
reading list. They are issuing an instruction **to this system about
this system**. *"Learn trading"* is a command to acquire a capability
it does not have. *"Buy a house for me"* is a command to pursue a goal
on the founder's behalf. In both, the actor is Kalpavriksha.

This generalises without a taxonomy of goal subjects, and the rule it
generalises to is a single one, enforced by `_prompt` and checked by
`_expectation`:

> **The answer says what *Kalpavriksha* will do. Never what the founder
> should do.**

An answer containing *"you should"*, *"you'll want to"* or *"I'd
recommend you"* has misread the instruction as a request for advice and
is rejected before the founder ever sees it — the same discipline the
refusal wording is held to. Advice is the failure mode here, not the
product.

## Why this reuses the Planner's own verdict rather than judging afresh

Nothing here decides whether a goal is executable. That question already
has exactly one owner in this architecture: the Planner, which asks a
provider against the full capability catalogue under a frozen rule
(`prompting.py` rule 6) — *"If the catalogue cannot achieve the goal,
reply with `{"steps": []}` rather than a step that only pretends to."*
`NO_STEPS` is that answer, and it is the only refusal code routed here.
Every other code (`PROVIDER_FAILED`, `MALFORMED`, `UNKNOWN_CAPABILITY`,
`NO_CAPABILITIES`, …) describes something that went *wrong*, not a goal
that is merely larger than one machine action, and none of them reach
this module.

So the two halves of the founder's distinction were both already in the
repository, decided by the components that own them. This module adds
neither — it only stops the third possibility being spoken as the first.

## Why this is not a second Brain, router, or provider door

`runner` is the *same* `TieredPromptRunner` instance the composition
root already builds and already hands to the `Planner`: the same Gemini
→ desktop-AI → free-AI ladder, the same Broker, the same
`DecisionRecord` trail. `RoutingContext.capability` stays `"reasoning"`
— the identical AI Capability `planner.PLANNING_CAPABILITY` names — so
this asks for no provider the Planner could not already have selected.
Only the *workload class* differs (`INTERACTIVE` rather than
`PLANNING`), because a founder is waiting on this one and the prompt is
a sentence rather than a whole catalogue. That is a fact about the work,
which is exactly what `workload` classes are for.

## Why `ResponseComposer` is not the home for this

`ResponseComposer` is documented as *"Stateless. Every method is a pure
function of what it is handed — no clock, no I/O, no randomness."* A
reasoning call is I/O and is not reproducible. Putting it there would
have broken that class's stated contract rather than extended it.

Its `FORBIDDEN_INTERNAL_TERMS` guard is likewise deliberately **not**
applied to what comes back here: that list bans words like `operator`,
`bridge` and `coordinator` because a *composed* sentence containing them
could only have come from architecture leaking. In generated prose about
the founder's own subject those are ordinary English words — a tour
operator, a bridge loan — and rejecting the answer for containing one
would be a false positive. The prompt below forbids naming this system's
internals directly, which is the honest form of the same rule here.
"""
from __future__ import annotations

from typing import Any

from master_agent.ai_infrastructure.budgeted_request import BudgetedSelectionRequest
from master_agent.ai_infrastructure.text_verifier import expect
from master_agent.ai_infrastructure.workload import INTERACTIVE
from master_agent.plugins.model_router import RoutingContext, SelectionRequest

#: The same AI Capability `planner.PLANNING_CAPABILITY` asks for. Stated
#: as its own name so a reader can see it is deliberately identical, not
#: coincidentally so.
REASONING_CAPABILITY = "reasoning"

#: What the founder hears when the reasoning ladder itself is unreachable
#: (every tier down, no key, no quota). Still not a refusal of the goal —
#: the goal was understood, and saying so remains true even when nothing
#: can be worked out this second.
UNREACHABLE = (
    "I understand what you're asking me to take on. It isn't something I "
    "finish in one move — it's something I'd have to work my way up to. "
    "I can't map out my route to it this moment. Ask me again and I'll "
    "pick it up from there."
)


def _prompt(goal: str) -> str:
    """Written about *any* goal. There is no phrase list here and no
    subject-matter branch: the founder's own words are the only input,
    so a goal this codebase has never seen is handled exactly like one
    it has.

    The one thing this prompt is emphatic about is *who acts* — see the
    module docstring's recorded founder correction. Every instruction
    below is phrased to keep Kalpavriksha the subject of every verb.
    """
    return (
        "You are Somesh, the founder's executive partner. You speak to "
        "the founder directly, in first person.\n\n"
        "The founder has just given you this instruction:\n\n"
        f"    {goal.strip()}\n\n"
        "READ IT CORRECTLY. This is an instruction about what YOU are to "
        "do or to become. It is NOT a request for advice, coaching, "
        "teaching, or a reading list. If the instruction names a skill, "
        "the founder is telling YOU to acquire that skill — not asking "
        "you to explain how a person would acquire it. If it names an "
        "outcome, the founder is telling YOU to pursue that outcome on "
        "their behalf. In every case the one doing the work is you.\n\n"
        "You understand what they mean. You are NOT declining. The only "
        "thing that is true is that this is not finished in a single "
        "action — it is something you have to work your way up to over "
        "time.\n\n"
        "Reply in 90 words or fewer, and do all four of these:\n"
        "1. Show you understood what you are being asked to become able "
        "to do, or to bring about, without repeating their sentence "
        "back verbatim.\n"
        "2. Say in one clause that this is something you build up to "
        "rather than finish in one go.\n"
        "3. Name the first two or three concrete things YOU would do to "
        "get there — what you would go and read, watch, gather, track, "
        "practise or set up FOR YOURSELF. Real and particular to this "
        "instruction, never generic.\n"
        "4. End by offering to begin on the first of them now.\n\n"
        "Every one of those moves must have you as its subject. Never "
        "tell the founder to do anything. Never say 'you should', "
        "'you'll want to', 'you need to', 'I'd recommend you', or "
        "'start by' addressed to them. Never turn this into guidance "
        "for the founder — they did not ask to learn anything.\n\n"
        "Never say you cannot do it, are unable to, or lack the ability. "
        "Never list what you can and cannot do. Never mention plans, "
        "planners, steps, capabilities, systems, models, tools, or "
        "software of any kind. Plain spoken English. No headings, no "
        "bullet points, no markdown, no numbered list."
    )


#: Second-person guidance markers. Their presence means the instruction
#: was read as a request for advice — the founder correction recorded in
#: the module docstring — and the answer is rejected on the way back
#: rather than shown. Deliberately only phrases that put the FOUNDER in
#: the actor position; "you" alone is ordinary and stays allowed ("you
#: asked me to", "I'll show you").
COACHING_MARKERS: tuple[str, ...] = (
    "you should",
    "you'll want to",
    "you will want to",
    "you need to",
    "you could start",
    "I'd recommend you",
    "I would recommend you",
    "I'd suggest you",
    "I would suggest you",
    "I recommend that you",
    "you might want",
    "for you to learn",
    "help you learn",
    "teach you",
)

#: The refusal wording the founder must never hear about a goal that was
#: understood.
REFUSAL_MARKERS: tuple[str, ...] = (
    "I can't do that",
    "I cannot do that",
    "I'm unable to",
    "I am unable to",
)


def _expectation():
    """Stated before the answer arrives, like every other expectation in
    this codebase. Two acceptance conditions, both enforced rather than
    hoped for: the founder is never refused a goal that was understood,
    and the founder is never coached about a goal they instructed *this
    system* to take on.

    A provider that ignores the prompt and answers with advice fails
    here, and `advise()` falls back to `UNREACHABLE` — which is honest
    ("I couldn't work out my route") rather than wrong ("here is how you
    should learn to trade").
    """
    return expect(
        description=(
            "a first-person answer in which Kalpavriksha says what IT will do "
            "about an instruction too large to carry out in one action"
        ),
        excludes_all=REFUSAL_MARKERS + COACHING_MARKERS,
        min_words=15,
    )


def advise(
    goal: str,
    runner: Any,
    *,
    task_id: str = "",
    objective_id: str | None = None,
    offline: bool = False,
) -> str:
    """The founder's answer for a clear-but-not-directly-executable goal.

    Never raises and never returns empty: a dead reasoning ladder still
    produces `UNREACHABLE`, because the one thing that must not happen
    is the founder being told their goal was not understood.
    """
    if not isinstance(goal, str) or not goal.strip():
        return UNREACHABLE

    prompt = _prompt(goal)
    context = RoutingContext(
        is_online=not offline,
        # A goal the founder states out loud carries no more sensitivity
        # than the same goal stated to the Planner, which is where this
        # request would otherwise have gone.
        requires_strong_reasoning=True,
        capability=REASONING_CAPABILITY,
        task_id=task_id,
        objective_id=objective_id,
        requester="brain_advisory",
    )
    request = BudgetedSelectionRequest(
        **vars(SelectionRequest.from_context(context)),
        request_class=INTERACTIVE,
        prompt=prompt,
    )

    try:
        outcome = runner.run(prompt, request, expected=_expectation())
    except Exception:  # noqa: BLE001 — a broken ladder is an honest silence, not a crash
        return UNREACHABLE

    if outcome is None or not getattr(outcome, "ok", False):
        return UNREACHABLE

    text = (getattr(outcome, "text", "") or "").strip()
    if not text:
        return UNREACHABLE

    # The expectation above is stated to the executor, which is the right
    # place for it. This second check is not a duplicate of that: it makes
    # the guarantee hold for ANY runner, including one whose executor
    # ignores `expected=`, and it is what a test can assert without
    # standing up a real verifier. A provider that answered with advice
    # despite being told not to is not shown to the founder -- honest
    # silence beats confidently answering the wrong question.
    lowered = text.lower()
    for marker in COACHING_MARKERS + REFUSAL_MARKERS:
        if marker.lower() in lowered:
            return UNREACHABLE
    return text
