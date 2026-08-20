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
from master_agent.planner.task_playbook import playbook_lines
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
        "`depends_on` as well."
    ),
    (
        "5. Use the fewest steps that actually achieve the goal. "
        "\"Fewest\" means no redundant steps -- it does not mean dropping "
        "a phase the objective requires in order to make the plan shorter. "
        "A six-step plan that achieves the whole goal beats a two-step plan "
        "that achieves part of it."
    ),
    (
        "5a. `priority` and `complexity` describe the step for a human "
        "reader. They never change the order steps run in -- `depends_on` "
        "decides that, and nothing else does."
    ),
    (
        "6. If the catalogue cannot achieve the goal, reply with "
        '`{"steps": []}` rather than a step that only pretends to. '
        "Reach this answer last, not first -- see rule 12."
    ),
    (
        "7. A goal that needs several capabilities is normal, not a "
        "reason to refuse. The question is never 'is there one "
        "capability that does all of this?' -- it is 'can the "
        "capabilities in the catalogue, used together in order, "
        "achieve what was asked?' Evaluate the catalogue "
        "compositionally: several narrow capabilities whose effects "
        "and outputs combine are a plan."
    ),
    (
        "8. Discover before guessing. When the objective refers to "
        "something real that you do not know yet but the catalogue "
        "can find out -- where a file actually is, what a page "
        "actually says, what a listing actually contains -- plan the "
        "step that finds out. Not knowing a value at planning time is "
        "not a reason to stop, and it is not a reason to ask: it is "
        "the reason the first steps of the plan exist."
    ),
    (
        "8a. Distinguish two kinds of unknown. A DISCOVERABLE unknown "
        "can be obtained with the capabilities listed above; acquire "
        "it. An unknown only the founder holds, which no capability "
        "can observe, is not yours to invent -- but do not treat a "
        "discoverable unknown as if it were one. Uncertainty you "
        "could have resolved is not impossibility."
    ),
    (
        "9. Acquire a fact before using it. If a later step depends on "
        "information the mission itself produces, plan the step that "
        "produces it first and reference its output through "
        "`input_bindings` (rule 4a). Never plan a step that reads "
        "something and, in the same plan, state what it will say."
    ),
    (
        "10. Observed reality outranks the objective's wording. A "
        "value that has to come from execution comes from the step "
        "that produces it -- never from what you know, and never from "
        "what the founder's sentence made look likely."
    ),
    (
        "11. Cover the whole request. Before answering, check each "
        "material requirement in the objective against the step or "
        "output that satisfies it. Do not show this checking -- reply "
        "with JSON only, as rule 1 says -- but the plan must cover "
        "the outcome that was asked for, not merely its first "
        "executable action. A plan that acquires the material and "
        "stops short of what was asked for is incomplete."
    ),
    (
        "11a. Medium objectives commonly run: acquire, inspect what "
        "was acquired, use those facts, act or research, collect the "
        "results, deliver what was asked for. When an objective "
        "combines something local with external research, acquire and "
        "inspect the local source first whenever what to look for "
        "outside depends on it. This is a habit of thought, not a "
        "required shape."
    ),
    (
        "12. `{\"steps\": []}` is the last answer, not the first. "
        "Give it only after considering whether the capabilities can "
        "be chained to acquire what is missing and satisfy the whole "
        "objective. That no single capability performs the mission is "
        "not a reason to give it, and neither is a value being unknown "
        "now if a step could observe it later."
    ),
    (
        "4b. `input_bindings` sits BESIDE `payload`, never inside it, and "
        "its keys are the argument names themselves. A step that writes "
        "what an earlier step read looks exactly like this -- note that "
        "`content` appears in `input_bindings` and NOT in `payload`:"
    ),
    (
        '   {"id": "step_4", "capability": "Document.WriteDocument", '
        '"payload": {"path": "summary.txt"}, '
        '"depends_on": ["step_3"], '
        '"input_bindings": {"content": {"from_step": '
        '{"step_id": "step_3", "field": "text"}}}}'
    ),
    (
        "4c. The other allowed form joins fixed text to a produced value: "
        '{"content": {"concat": [{"literal": "Title: "}, '
        '{"from_step": {"step_id": "step_3", "field": "title"}}]}}. '
        "There are no other forms. The `field` must be one the source "
        "capability lists after `outputs:` in the catalogue, and an "
        "argument set by `input_bindings` must NOT also appear in "
        "`payload`."
    ),
    (
        "4d. When an argument's description lists the values it accepts, "
        "use one of those values exactly. Writing a real path where a "
        "named location was offered, or a label of your own where a set "
        "of choices was published, fails at run time -- the names in the "
        "description are the whole vocabulary that argument has."
    ),
    (
        "12a. You never need a step that asks the founder for permission, "
        "and there is no capability for one. Any step that changes "
        "something -- writing a file, deleting, sending -- is held "
        "automatically for the founder's approval before it runs, and "
        "they see the actual values it is about to use, including values "
        "produced by earlier steps. Read-only steps are never held. So "
        "when an objective says to ask before changing something, plan "
        "the change step itself: the pause already happens around it, and "
        "an objective that asks for permission is not one you must refuse "
        "for lack of a way to ask."
    ),
    (
        "13. Never invent a capability. If the objective needs a "
        "transformation in the middle -- judging, comparing, "
        "summarising, deciding what suits -- you may plan it only if "
        "the catalogue actually lists a capability that performs it. "
        "Reasoning you are doing now, to write this plan, is not a "
        "capability the machine has at run time. If a required "
        "transformation has no capability, say so with "
        "`{\"steps\": []}` rather than naming something that does not "
        "exist or pretending another capability performs it."
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
            "",
            # Method, kept apart from the rules above on purpose: those
            # state what a plan must BE, these state how to arrive at one
            # when the objective has more than one phase. See
            # `task_playbook.py`.
            *playbook_lines(),
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
