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
    "I understand what you're after, and it's worth doing — it's just "
    "bigger than something I can carry out in one move. I can't work "
    "the approach out this moment. Ask me again and I'll take it apart "
    "with you."
)


def _prompt(goal: str) -> str:
    """Written about *any* goal. There is no phrase list here and no
    subject-matter branch: the founder's own words are the only input,
    so a goal this codebase has never seen is handled exactly like one
    it has."""
    return (
        "You are Somesh, the founder's executive partner. You speak to "
        "the founder directly, in first person.\n\n"
        "The founder has just told you to do this:\n\n"
        f"    {goal.strip()}\n\n"
        "You understand what they mean. This is a real instruction and "
        "you are NOT declining it. The only thing that is true is that "
        "it is not something finished in a single action on this "
        "machine — it is work that has to be broken down and worked "
        "through over time.\n\n"
        "Reply in 90 words or fewer, and do all four of these:\n"
        "1. Show you understood the goal, in their terms, without "
        "repeating their sentence back verbatim.\n"
        "2. Say in one clause that this is something you'd work through "
        "with them rather than finish in one go.\n"
        "3. Name the first two or three concrete moves that actually "
        "advance THIS goal specifically — real and particular to it, "
        "never generic advice that would fit any goal.\n"
        "4. End by offering to start on the first of them.\n\n"
        "Never say you cannot do it, are unable to, or lack the ability. "
        "Never list what you can and cannot do. Never mention plans, "
        "planners, steps, capabilities, systems, models, tools, or "
        "software of any kind. Plain spoken English. No headings, no "
        "bullet points, no markdown, no numbered list."
    )


def _expectation():
    """Stated before the answer arrives, like every other expectation in
    this codebase. It checks the answer is a real spoken paragraph and
    that the refusal wording the founder must never hear again is
    absent — the acceptance condition, enforced rather than hoped for."""
    return expect(
        description="a spoken answer to the founder about a goal too large to execute directly",
        excludes_all=("I can't do that", "I cannot do that", "I'm unable to"),
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
    return text or UNREACHABLE
