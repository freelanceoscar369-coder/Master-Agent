"""What the Planner asks for, and what it expects back (Mission Brief 036).

Two functions and one constant, kept in a module of their own because
they are the only place in `planner/` where English is written. Both are
pure and deterministic: the same `Intent` and the same catalogue produce
byte-identical text, which is what lets the same objective be replayed
against a different policy version later (the MB032 guarantee) and what
makes the prompt cache able to hit at all.

The expectation is built **here**, beside the request, rather than at the
call site. That is not tidiness: MB035's argument is that a check is only
falsifiable if it was stated before the answer arrived, and the strongest
way to keep that true is for the sentence asking and the sentence
checking to be written in the same breath.
"""
from __future__ import annotations

from master_agent.ai_infrastructure.text_verifier import expect
from master_agent.planner.catalogue import CapabilityOption, render
from master_agent.planner.plan import Intent
from master_agent.verification.evidence import ExpectedOutcome

#: The shape a plan must have. Stated as an example rather than as a
#: JSON-Schema because the thing reading it is a small local model, and
#: MB033's provider is `gemma4` on the founder's own laptop, not a
#: frontier model with a structured-output mode.
PLAN_SHAPE = """{
  "steps": [
    {
      "id": "step_1",
      "capability": "<exactly one name from the catalogue above>",
      "payload": {"<argument>": "<value>"},
      "input_bindings": {},
      "depends_on": [],
      "priority": "low | normal | high | critical",
      "complexity": "trivial | small | moderate | large",
      "success": {
        "description": "what a good result for this step looks like",
        "must_contain": ["a phrase the result must contain"],
        "must_exclude": [],
        "must_be_json": false,
        "must_have_fields": [],
        "min_words": 0
      }
    }
  ]
}"""

_RULES = (
    "Rules:",
    "1. Reply with JSON only. No prose before or after it.",
    (
        "2. Every `capability` must be copied exactly from the catalogue. "
        "Never invent one, and never abbreviate one."
    ),
    (
        "2a. Each catalogue line reads `- Name | args: ... | description`. "
        "The `capability` you write is the **Name only**, never the args "
        "or the description. The names after `args:` are the keys your "
        "`payload` must use, spelled exactly that way -- do not infer "
        "argument names from the description."
    ),
    (
        "3. Every step must have a `success` object stating what a good "
        "result looks like *before* the step runs."
    ),
    (
        "4. `depends_on` lists the `id`s of steps that must finish first. "
        "Leave it empty if there are none."
    ),
    (
        "4a. When a step needs a value that an EARLIER step produces, do "
        "not guess it, copy it, predict it, or take it from the "
        "objective's wording. You do not know it yet -- it does not exist "
        "until that step runs. Declare it in `input_bindings` instead, "
        "referencing the step that produces it, and put that step in "
        "`depends_on` as well. Two forms are allowed: "
        '{"argument": {"from_step": {"step_id": "step_3", "field": "url"}}} '
        "or "
        '{"argument": {"concat": [{"literal": "Title: "}, '
        '{"from_step": {"step_id": "step_3", "field": "title"}}]}}. '
        "The `field` must be one the source capability lists after "
        "`outputs:` in the catalogue. An argument set by `input_bindings` "
        "must NOT also appear in `payload`."
    ),
    "5. Use the fewest steps that actually achieve the goal.",
    (
        "5a. `priority` and `complexity` describe the step for a human "
        "reader. They never change the order steps run in -- `depends_on` "
        "decides that, and nothing else does."
    ),
    (
        "6. If the catalogue cannot achieve the goal, reply with "
        '`{"steps": []}` rather than a step that only pretends to.'
    ),
)


def build_prompt(
    intent: Intent, options: tuple[CapabilityOption, ...] | list[CapabilityOption]
) -> str:
    """The planning request.

    Rule 6 is the load-bearing one. Without it the honest answer to an
    impossible objective is unavailable, so the provider invents a
    capability to fill the gap -- and the catalogue check downstream then
    refuses a plan the model was effectively forced into. Giving refusal a
    shape it can express is cheaper than detecting the alternative.
    """
    sections = [
        (
            "You are the Planner for an autonomous system. Turn the objective "
            "below into a plan the system can execute."
        ),
        "",
        f"Objective: {intent.goal}",
    ]

    if intent.constraints:
        sections.append("")
        sections.append("Constraints:")
        sections.extend(f"- {item}" for item in intent.constraints)

    if intent.success_criteria:
        sections.append("")
        sections.append("The founder will consider this done when:")
        sections.extend(f"- {item}" for item in intent.success_criteria)

    if intent.context:
        sections.append("")
        sections.append("Context:")
        # Sorted, because a dict's insertion order is not a fact about the
        # work and would otherwise change the prompt between two runs that
        # asked the same question.
        sections.extend(f"- {key}: {intent.context[key]}" for key in sorted(intent.context))

    sections.extend(
        [
            "",
            "Capabilities available (this list is exhaustive):",
            render(options),
            "",
            "Reply with exactly this JSON shape:",
            PLAN_SHAPE,
            "",
            *_RULES,
        ]
    )
    return "\n".join(sections)


def plan_expectation() -> ExpectedOutcome:
    """What a usable *plan document* looks like, stated before asking.

    Deliberately thin: it checks that something parseable with a `steps`
    key came back, and nothing about whether the plan is any good. The
    rest -- unknown capabilities, missing expectations, dependency cycles
    -- is decided by `parsing.validate()`, which can say *which step* and
    *why*. A verifier can only say matched or not, and "not matched" is a
    poor answer to "your third step names a capability that does not
    exist".
    """
    return expect(
        description="a plan document: JSON with a `steps` list",
        json_body=True,
        json_fields=("steps",),
    )
