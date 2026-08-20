"""How to plan work that takes more than one step.

`prompting.py`'s rules say what a plan must *be*: exact capability names,
exact argument spelling, stated expectations, bindings instead of guesses.
This says how to *arrive* at one when the objective has several phases.

The two are separate on purpose. A rule about JSON shape is true forever;
a heuristic about phases is judgement, and judgement that lives in the
same tuple as a syntax rule eventually gets edited like one.

Nothing here names a domain. These paragraphs were written after a
founder asked for documents to be read, compared, improved with
permission, and matched against live listings -- and if any of that
vocabulary appeared below, the guidance would only work for that one
request. A test asserts it does not.

`MEDIUM` and `COMPLEX` are descriptions, not a classifier. Nothing labels
an objective before planning it, and the Planner is told to respond to the
structure in front of it rather than decide which word applies.
"""
from __future__ import annotations

MEDIUM = (
    "Multi-step work:",
    (
        "A task that needs several capabilities is still one bounded plan. "
        "The usual movement is: acquire what you need, observe or read it, "
        "reason over what you found, decide, act, verify the effect, and "
        "deliver what was asked for. Use only the phases this objective "
        "actually requires -- most need three or four, and a phase added "
        "because the list mentions it is a redundant step."
    ),
)

COMPLEX = (
    "Longer work with phases:",
    (
        "When later work depends on what earlier work found, plan it as "
        "phases rather than as one flat list: discover what sources exist, "
        "collect evidence from them, compare the evidence, reason over it, "
        "identify the options or gaps, choose what to propose, get approval "
        "if the next step changes something, carry out the approved change, "
        "verify it, continue any research that depended on it, and "
        "synthesise the final answer."
    ),
    (
        "Plan a bounded amount of work, always. If an objective invites "
        "open-ended searching, plan a specific first batch big enough to "
        "answer it well and stop there. Do not plan a loop, and do not "
        "write a plan that assumes it will be revised while running -- "
        "steps run as written, in dependency order, and nothing replans "
        "mid-mission."
    ),
)

EVIDENCE = (
    "Evidence before judgement:",
    (
        "If a judgement depends on something the mission itself can find "
        "out, find it out first and reason over what was actually "
        "observed. Read the documents before comparing them; look at the "
        "real options before ranking them; read the page before "
        "summarising it. Never the other way round -- an answer produced "
        "first and checked against reality afterwards is a guess wearing "
        "a result's clothes."
    ),
    (
        "When several sources might hold what you need, discover them "
        "first, inspect the plausible ones, and compare them before "
        "choosing. Taking the first name that matched is not a choice; it "
        "is an accident that looks like one."
    ),
)

CHANGE = (
    "Before changing anything of the founder's:",
    (
        "Finding, reading, observing and reasoning change nothing, and "
        "need no permission -- do not plan an approval before them. "
        "Approval belongs immediately before the first step that actually "
        "changes something, and by then the founder should already be able "
        "to see what you found and what you propose to do about it."
    ),
    (
        "Never modify or overwrite something the founder already has. "
        "Write a new file alongside it. An original that still exists is "
        "the difference between a proposal and a fait accompli."
    ),
)

DELIVERY = (
    "Finishing:",
    (
        "Verify changes that matter in the real world by observing them, "
        "not by assuming the step that made them worked."
    ),
    (
        "Any claim about the world outside this machine must come from "
        "something the mission actually observed during this run. Do not "
        "state a fact about an external thing that no step looked at. If a "
        "detail the founder asked for is genuinely absent from what was "
        "observed, the answer says it was not stated -- it does not fill "
        "the space from general knowledge."
    ),
    (
        "Keep the thread traceable: each phase's inputs come from the "
        "outputs of the phase that produced them, through `input_bindings`, "
        "so the final answer can be followed back to the evidence it rests "
        "on."
    ),
    (
        "When the objective asks for something to be given to the founder "
        "-- a summary, a comparison, a set of recommendations -- the last "
        "step must put it somewhere they can actually open. A step that "
        "works the answer out and hands it to nobody has not delivered it: "
        "the founder is told the work finished and never sees what it "
        "found."
    ),
)


def playbook_lines() -> tuple[str, ...]:
    """The guidance, as lines to place in a planning prompt.

    A function rather than a constant so the composition is stated in one
    place: a caller adding a section edits this list, not a string that
    happens to be assembled somewhere else.
    """
    sections = (MEDIUM, COMPLEX, EVIDENCE, CHANGE, DELIVERY)
    lines: list[str] = ["Planning longer work:"]
    for section in sections:
        heading, *body = section
        lines.append(f"- {heading}")
        lines.extend(f"  {paragraph}" for paragraph in body)
    return tuple(lines)
