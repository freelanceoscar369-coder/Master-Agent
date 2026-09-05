"""A plan the Planner can write without asking a model.

## The defect this exists to remove

A founder typed *"create a folder called KalpavrikshaLiveTest3 in
Documents"*. `Filesystem.CreateFolder(name, location?)` was registered and
sufficient. The Planner nevertheless sent a planning prompt to its
reasoning ladder, which — Gemini being out of quota — fell through every
tier: Gemini, then each installed desktop AI application, then a browser
search. Windows opened. Nothing about the objective needed reasoning.

**Capability availability and reasoning necessity are different
questions.** A model that is asked *"which of these capabilities creates
a folder?"* is being paid to rediscover a mapping the Intent Layer has
already performed.

## What makes it deterministic rather than a guess

Two independent facts have to agree, and both are already published:

1. The Intent names a capability. Not inferred from prose here — the
   typed parser that recognised the sentence recorded it, the same
   `capability` + `payload` pair `cli.py`'s `ParsedActionIntent` has
   carried since MB005.
2. The registered catalogue confirms that capability exists, publishes
   `required_args`, and declares those arguments **complete**
   (`args_complete`) — MB039's index, not the thin registry.

If either is missing, this returns `None` and the Planner asks a provider
exactly as before. Nothing is downgraded on a maybe.

## Why matching on argument shape alone was rejected

The obvious alternative — find the capability whose `required_args` the
Intent's context happens to satisfy — is unsafe here, measured rather
than assumed: in the filesystem plugin alone `('path',)` is the required
signature of **six** capabilities, among them `Filesystem.ReadFile` and
`Filesystem.DeleteFile`. A shape match cannot tell reading from deleting,
and one of those is irreversible. So the capability is never inferred
from the arguments; it is only ever confirmed.

## What this module does not do

It does not decide whether to use a model — `Planner` owns that. It does
not execute anything. It does not reorder, retry, or approve. It produces
one `Step`, inside `planner/`, which is the only package permitted to
construct a `MissionPlan` at all (asserted by an AST test over `src/`).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from master_agent.planner.outcomes import SuccessSpec
from master_agent.planner.plan import (
    CONSTRAINT,
    DELIVERABLE,
    EFFECT,
    INFORMATION,
    Intent,
    MissionPlan,
    SemanticRequirement,
    Step,
)


def _normalised(name: str) -> str:
    """`create_folder`, `CreateFolder` and `Filesystem.CreateFolder` are
    the same capability written three ways -- the plugin constant, the
    contract class, and the qualified catalogue name. Comparing them
    without knowing plugin namespacing keeps the Brain from having to."""
    return name.rsplit(".", 1)[-1].replace("_", "").replace("-", "").lower()


def find_option(capability: str, options) -> Any | None:
    """The registered capability this intent names, or `None`.

    Exact match on the normalised name only. A near-miss is not a match:
    an intent naming something unregistered is a question for the Planner,
    not an invitation to pick the closest thing.
    """
    if not capability:
        return None
    wanted = _normalised(capability)
    for option in options:
        if _normalised(option.name) == wanted:
            return option
    return None



# ─────────────────────── semantic coverage ───────────────────────
#
# A deterministic plan does not need to be ASKED what it covers. It read
# the founder's sentence clause by clause to compile itself, so it knows
# which requirement each step exists for -- and coverage attached at
# construction is proven rather than claimed, which is the difference
# between this and an AI plan that has to be validated.


def _selection_reason(
    option: Any, requirements: Any, covered: tuple[str, ...]
) -> str:
    """Why this capability, for these requirements -- from facts only.

    Every clause is something already published: the requirement the
    Intent Layer extracted, the capability's own registered description,
    and the argument contract it declares. Nothing here is composed by a
    model, and nothing is inferred.

    That matters a day later. A founder asking *"why did you use that
    tool?"* must be answered from what was actually decided at planning
    time -- a model asked the same question afterwards would produce a
    plausible reason, and a plausible reason is indistinguishable from
    the real one exactly when it is wrong.
    """
    wanted = [r for r in (requirements or ()) if r.requirement_id in set(covered)]
    if not wanted:
        return ""
    described = "; ".join(f"{r.requirement_id} ({r.description})" for r in wanted)
    required_args = ", ".join(getattr(option, "required_args", ()) or ()) or "none"
    summary = (getattr(option, "description", "") or "").strip().rstrip(".")
    reason = f"{option.name} was selected for {described}"
    if summary:
        reason += f" because the registered capability {summary.lower()}"
    return f"{reason}. Its contract requires: {required_args}."


def _requirements_from(intent: Intent) -> tuple[SemanticRequirement, ...]:
    """What the founder required, as the Intent already recorded it."""
    return tuple(getattr(intent, "requirements", ()) or ())


def _dictated_requirements(
    intent: Intent, described: list[tuple[str, str]]
) -> tuple[SemanticRequirement, ...]:
    """Requirements for a workflow the founder dictated operation by
    operation.

    One requirement per operation THEY named, in the order they named it.
    That is faithful here in a way it would not be for prose: a dictated
    workflow's operations are not implementation detail the founder is
    indifferent to -- they are the request.

    Reuses whatever the Intent already carries. A typed intent arrives
    with requirements derived from its payload, and re-deriving them from
    the compiled steps would be a second reading of the same sentence.
    """
    existing = _requirements_from(intent)
    if existing:
        return existing
    return tuple(
        SemanticRequirement(
            requirement_id=f"req_{index}",
            kind=kind,
            description=description,
            provenance=intent.goal,
        )
        for index, (kind, description) in enumerate(described, start=1)
    )


def _single_capability_plan(intent: Intent, options) -> MissionPlan | None:
    """One step, or `None` when this objective genuinely needs planning.

    `None` is the safe answer and is returned for every uncertainty: no
    capability named, capability not registered, arguments the contract
    does not publish, a required argument missing, or an argument roster
    the catalogue itself flags as incomplete.
    """
    option = find_option(getattr(intent, "capability", ""), options)
    if option is None:
        return None

    payload = dict(getattr(intent, "payload", None) or {})
    if not payload:
        return None

    required = tuple(getattr(option, "required_args", ()) or ())
    optional = tuple(getattr(option, "optional_args", ()) or ())

    # MB039's own honesty flag. An index that does not know the full
    # argument roster cannot be used to certify a payload is complete --
    # that is exactly the "the Planner guesses argument names" failure
    # `args_complete` was added to expose, and guessing is what this
    # module exists to stop.
    if not getattr(option, "args_complete", False):
        return None

    known = set(required) | set(optional)
    if not known or not set(payload) <= known:
        # An argument the contract never published cannot be passed on. The
        # Planner will ask a provider, which at least gets to see the
        # capability description.
        return None
    if not set(required) <= set(payload):
        return None

    # The founder asked a question, and the Intent Layer said which output
    # field answers it. Checked against what the capability actually
    # publishes -- promising a field nobody declared is the same guess
    # `args_complete` exists to stop, pointed at outputs instead of
    # inputs.
    answers = str(getattr(intent, "answers_founder", "") or "").strip()
    if answers and answers.split(".")[0] not in set(
        getattr(option, "output_fields", ()) or ()
    ):
        return None

    # Stated before the step runs, from what the Intent Layer already said
    # success looks like -- never composed here, and never left empty:
    # `objective_from_plan()` rejects a step with no expectation, and
    # Verification would have nothing to check against.
    description = next(
        (c for c in (intent.success_criteria or []) if c and c.strip()),
        f"{option.name} completes for {intent.goal}".strip(),
    )
    covered = tuple(r.requirement_id for r in _requirements_from(intent))
    # The id must be unique across every mission this process runs, not
    # merely within this plan.
    #
    # It was `f"{option.name}-1"`, which is unique inside a one-step plan
    # and identical for every folder mission ever planned. `RuntimeEngine
    # ._objective_of()` finds a task's objective by scanning every
    # objective for a matching `task_id` and returning the FIRST hit -- so
    # the second folder mission's completion was applied to the first
    # mission's objective. The second objective then never completed, no
    # `OBJECTIVE_COMPLETED` fired, no completion question was asked, and
    # the founder surface span its full timeout and reported "that's
    # taking longer than expected" about a folder already sitting on disk.
    #
    # Every third-and-later mission compounded it. The founder saw this as
    # completed work blocking new work; the cause was two missions sharing
    # one identity.
    step = Step(
        step_id=f"{option.name}-{uuid4().hex[:8]}",
        capability=option.name,
        payload=payload,
        expected_outcome=SuccessSpec(description=description).to_expected_outcome(),
        answers_founder=answers,
        # One step doing the whole job covers every requirement there is,
        # including the constraints -- they are conditions ON this
        # effect, satisfied by the same call that performs it.
        covers=covered,
        selection_reason=_selection_reason(
            option, _requirements_from(intent), covered
        ),
    )
    # The plan carries the requirements its step covers.
    #
    # Without this the coverage is an orphaned reference: `covers` names
    # `req_1`, nothing records what `req_1` WAS, and conformance
    # correctly reports "no recorded founder requirements" for a mission
    # that had them all along. Caught by rehearsing the founder's own
    # question against real stored history.
    return MissionPlan(
        steps=[step], objective=intent.goal,
        requirements=_requirements_from(intent),
    )


# ---------------------------------------------------------------------
# The explicit local workflow
# ---------------------------------------------------------------------
#
# One step was the limit, not the philosophy. A founder who writes "open a
# browser, go to this address, see what the page says, write that into a
# file on my Desktop, close the browser" has not posed a planning problem
# -- they have dictated the steps. Sending that to a reasoning ladder buys
# nothing, and when every tier is out of quota or refuses, it loses the
# whole mission to a question nobody needed answered.
#
# So this recognises one narrow, explicitly-dictated shape and nothing
# else. It is deliberately not a workflow engine: no verb is inferred, no
# ordering is deduced, no capability is chosen by resemblance. Every
# signal below must be present in the founder's own sentence, and every
# capability must be registered with a contract that publishes the
# arguments used. Any doubt returns `None`, and the Planner reasons
# exactly as before.
#
# What this is NOT keyed on: the site. Matching a host would make it a
# rehearsal rather than a capability -- the same objective pointed at a
# different address has to plan identically, and a test asserts it does.

_URL = re.compile(r"https?://[^\s'\"<>)\]]+")
#: "folder called X", "folder named X" -- optionally quoted or back-ticked.
_FOLDER = re.compile(r"folder\s+(?:called|named)\s+[`'\"]?([^\s`'\"]+)", re.I)
#: "file called page_info.txt" -- a filename, so an extension is required.
_FILE = re.compile(r"file\s+(?:called|named)\s+[`'\"]?([^\s`'\"]+\.[A-Za-z0-9]+)", re.I)
#: Where the folder goes -- the founder's own word, never a default.
#: Writing to Desktop because nothing was said is exactly the guess the
#: create-folder completeness repair removed.
_PLACE = re.compile(
    r"\b(?:on|in|to)\s+(?:the\s+|my\s+)?(Desktop|Documents|Downloads)\b", re.I
)

_OPEN = "open_browser_session"
_NAVIGATE = "navigate"
_OBSERVE = "observe_browser"
_CREATE_FOLDER = "create_folder"
_WRITE_FILE = "write_file"
_CLOSE = "close_browser_session"
#: `Reasoning.Transform` -- the one capability that produces text by
#: thinking. Named here so `_generate_then_write` can confirm it is
#: registered rather than assume it.
_TRANSFORM = "transform"

#: The two page facts `Browser.ObserveBrowser` publishes. Confirmed
#: against the registered contract before use, never assumed here.
_TITLE = "title"
_URL_FIELD = "url"

#: The founder saying that the file holds what the browser saw.
#:
#: Two voices say the identical thing. As a modifier -- "a file called
#: page_info.txt CONTAINING the title and URL you observed" -- and in the
#: active voice -- "WRITE the observed title and final URL INTO a file
#: called page_info.txt". Only the first was recognised, so a founder who
#: phrased the same instruction the second way got no local plan and was
#: sent to a model to be told what they had already said.
#:
#: This widens how the relation may be phrased. It does not weaken what
#: must be present: the sentence must still name the page, the folder, the
#: place and the file, still ask for the page to be observed, and still
#: name both facts. A file whose content the founder never tied to the
#: browser remains unplannable here.
_CONTAINMENT = re.compile(
    r"contain(?:s|ing)\b|with\s+the\b|writ(?:e|es|ing)\b[^.]{0,80}?\b(?:in|into|to)\b",
    re.I,
)


@dataclass(frozen=True)
class _CaptureRequest:
    """What the founder's sentence explicitly said, and nothing more."""

    url: str
    folder: str
    place: str
    filename: str


def _read_capture_request(goal: str) -> _CaptureRequest | None:
    """The dictated workflow, or `None`.

    Every element must be stated. This does not complete a partial
    instruction: a sentence naming a page but no file, or a file but no
    folder, is an objective someone still has to think about.
    """
    text = (goal or "").strip()
    if not text:
        return None
    lowered = text.lower()

    url = _URL.search(text)
    folder = _FOLDER.search(text)
    filename = _FILE.search(text)
    place = _PLACE.search(text)
    if not (url and folder and filename and place):
        return None

    # The founder must have asked for the page to be observed, and for the
    # file to contain what was observed. Without both, that file's content
    # is not derivable from the browser and this shape does not apply.
    if "observ" not in lowered:
        return None
    if not _CONTAINMENT.search(text):
        return None
    if _TITLE not in lowered or _URL_FIELD not in lowered:
        return None
    if "close" not in lowered:
        return None

    return _CaptureRequest(
        url=url.group(0).rstrip(".,;"),
        folder=folder.group(1).rstrip(".,;"),
        place=place.group(1).capitalize(),
        filename=filename.group(1).rstrip(".,;"),
    )


def _usable(option: Any, payload: dict[str, Any], bound: tuple[str, ...] = ()) -> bool:
    """The one-step path's contract test, applied per step.

    An argument supplied by a binding counts as supplied: it is present at
    execution, just not yet at planning time. That is what a binding is
    for, and refusing it here would make cross-step data flow impossible
    to plan deterministically.
    """
    if option is None:
        return False
    required = set(getattr(option, "required_args", ()) or ())
    optional = set(getattr(option, "optional_args", ()) or ())
    supplied = set(payload) | set(bound)

    if not required or not required <= supplied:
        return False
    if supplied <= required:
        # Nothing but the capability's own published requirements. There is
        # no argument name to get wrong here, so `args_complete` -- which
        # exists to stop the Planner *inventing* argument names -- has
        # nothing to certify. `Browser.Navigate` publishes no optional
        # roster at all; refusing it on that basis would make a capability
        # unusable for being simple.
        return True
    # Beyond the requirements: `headless`, `location`, `content`. Now the
    # roster matters, because using an optional argument is a claim about
    # what the contract accepts.
    if not getattr(option, "args_complete", False):
        return False
    return supplied <= (required | optional)


def _local_capture_workflow(intent: Intent, options) -> MissionPlan | None:
    """Six steps for the dictated browser-observe-write workflow, or `None`."""
    request = _read_capture_request(getattr(intent, "goal", "") or "")
    if request is None:
        return None

    found = {
        name: find_option(name, options)
        for name in (_OPEN, _NAVIGATE, _OBSERVE, _CREATE_FOLDER, _WRITE_FILE, _CLOSE)
    }
    if any(option is None for option in found.values()):
        # Half of this workflow is not a smaller version of it. If the
        # machine cannot do all six, it cannot do the job.
        return None

    # The binding below promises `title` and `url` come from the
    # observation. That promise is only as good as the contract, so it is
    # checked against what the capability actually publishes rather than
    # against this module's expectations of it.
    published = set(getattr(found[_OBSERVE], "output_fields", ()) or ())
    if not {_TITLE, _URL_FIELD} <= published:
        return None

    session_id = f"kv-{uuid4().hex[:8]}"
    # One mark per mission, distinct per capability: unique across every
    # mission this process runs, for the identity reason recorded above.
    mark = uuid4().hex[:8]
    ids = {name: f"{name}-{mark}" for name in found}

    payloads: dict[str, dict[str, Any]] = {
        # Visible, because the founder said "open a browser" -- an
        # instruction about something they expect to watch happen. The
        # contract publishes `headless` precisely so this is a choice the
        # Planner may make rather than a default it inherits.
        _OPEN: {"session_id": session_id, "headless": False},
        _NAVIGATE: {"session_id": session_id, "url": request.url},
        _OBSERVE: {"session_id": session_id},
        _CREATE_FOLDER: {"name": request.folder, "location": request.place},
        # The path contract: `location` names the founder's place, `path`
        # is relative to it.
        _WRITE_FILE: {
            "path": f"{request.folder}/{request.filename}",
            "location": request.place,
        },
        _CLOSE: {"session_id": session_id},
    }
    if not _usable(found[_WRITE_FILE], payloads[_WRITE_FILE], bound=("content",)):
        return None
    if not all(
        _usable(found[name], payloads[name])
        for name in (_OPEN, _NAVIGATE, _OBSERVE, _CREATE_FOLDER, _CLOSE)
    ):
        return None

    expectations = {
        _OPEN: "A browser session is open and visible to the founder.",
        _NAVIGATE: f"The browser session's current page is {request.url}.",
        _OBSERVE: "The page's current title and URL are reported.",
        _CREATE_FOLDER: f"The folder {request.folder} exists in {request.place}.",
        _WRITE_FILE: (
            f"{request.filename} exists in {request.folder} and contains the "
            f"title and URL the browser reported."
        ),
        _CLOSE: "The browser session is closed.",
    }
    dependencies = {
        _OPEN: [],
        _NAVIGATE: [ids[_OPEN]],
        _OBSERVE: [ids[_NAVIGATE]],
        _CREATE_FOLDER: [ids[_OBSERVE]],
        # Both: the values come from the observation, the destination from
        # the folder. `depends_on` remains the single ordering authority,
        # so a binding may read this list but never extend it.
        _WRITE_FILE: [ids[_OBSERVE], ids[_CREATE_FOLDER]],
        _CLOSE: [ids[_WRITE_FILE]],
    }
    # Plain JSON: the wire form that survives translation, the event bus
    # and a restart. Emitting parsed objects here is what stalled an
    # earlier live mission on `'dict' object has no attribute 'ref'`.
    #
    # No literal `content` is written, and no title or URL is guessed --
    # at planning time nobody has looked at the page yet.
    bindings = {
        _WRITE_FILE: {
            "content": {
                "concat": [
                    {"literal": "Title: "},
                    {"from_step": {"step_id": ids[_OBSERVE], "field": _TITLE}},
                    {"literal": "\nURL: "},
                    {"from_step": {"step_id": ids[_OBSERVE], "field": _URL_FIELD}},
                ]
            }
        }
    }

    order = (_OPEN, _NAVIGATE, _OBSERVE, _CREATE_FOLDER, _WRITE_FILE, _CLOSE)
    # One requirement per operation the founder dictated, in their order
    # -- the same reading every other deterministic lane uses.
    requirements = _dictated_requirements(
        intent, [(EFFECT, expectations[name]) for name in order]
    )
    covered = {
        name: (requirement.requirement_id,)
        for name, requirement in zip(order, requirements)
    }

    steps = [
        Step(
            step_id=ids[name],
            capability=found[name].name,
            payload=payloads[name],
            depends_on=dependencies[name],
            input_bindings=bindings.get(name, {}),
            expected_outcome=SuccessSpec(
                description=expectations[name]
            ).to_expected_outcome(),
            covers=covered[name],
            selection_reason=_selection_reason(
                found[name], requirements, covered[name]
            ),
        )
        for name in order
    ]
    return MissionPlan(
        steps=steps, objective=intent.goal, requirements=requirements
    )


# ─────────────────── deterministic explicit workflows ───────────────────
#
# `_local_capture_workflow` above compiles ONE dictated workflow. That was
# the right size for the mission that produced it and the wrong size for
# the general case: a founder who says
#
#     Create a folder called X on the Desktop. Then show me the text
#     before you write it into notes.txt inside that folder. The text
#     should be: Kalpavriksha checkpoint acceptance.
#
# has supplied both operations, the name, the place, the file, the literal
# content, the ordering and the checkpoint. Nothing is left to judgement.
# It fell through to the AI Planner anyway, which sent the whole
# capability catalogue to a model to ask which capability creates a
# folder — and, with Gemini's quota spent, walked ChatGPT Desktop,
# Perplexity, Kimi and Gemini web before telling the founder it could not
# plan at all.
#
# Reasoning is for work that REQUIRES reasoning. Having more than one step
# is not that. What follows compiles an explicitly specified sequence when
# every part of it can be proven from the founder's own words and the
# registered contracts, and returns `None` the moment anything would have
# to be guessed — so uncertainty still falls through to the ladder, which
# is unchanged.

#: "show me ... before" / "before you write" — the founder asking to see a
#: payload before it is committed. `Step.founder_checkpoint` already exists
#: for exactly this; noticing a request the founder stated outright needs
#: no model.
_CHECKPOINT = re.compile(
    r"\b(?:show|check)\s+(?:me|with\s+me)\b[^.]*?\bbefore\b|\bbefore\s+you\s+write\b",
    re.I,
)

#: The literal the founder supplied for a file's contents, in the two
#: shapes they actually write.
_CONTENT_TRAILING = re.compile(
    r"\bthe\s+(?:text|content|contents)\s+(?:should\s+be|is)\s*:?\s*(.+)$",
    re.I | re.S,
)
_CONTENT_INLINE = re.compile(
    r"\bwrite\s+(.+?)\s+(?:in|into|to)\s+(?:a\s+file\s+called\s+)?"
    r"([^\s`'\"]+\.[A-Za-z0-9]+)",
    re.I,
)

#: The state-stated form of the same instruction. A founder who says what
#: must be TRUE rather than what to DO has still dictated the operation:
#: "ensure result.txt contains exactly: ..." names the file, the content
#: and the fact that it is to be written, as completely as "write ... into
#: result.txt" does.
#:
#: Measured live 2026-09-05: an objective in this form compiled to `None`
#: here and was therefore escalated to the reasoning ladder, which spent
#: eight external calls failing to establish requirements for a folder and
#: a text file. ADR-0027 names that exact case -- "creating a folder must
#: not deliberate."
#:
#: The filename must be the subject of the contains-clause. That is what
#: keeps this from being a bare "any token with a dot" rule, which would
#: read a version number or a domain as a destination.
_FILE_CONTAINS = re.compile(
    r"\b([^\s`'\"]+\.[A-Za-z0-9]+)\s+(?:should\s+)?contains?\b",
    re.I,
)

#: "...contains exactly: <text>" / "...contains: <text>". Stops at a
#: sentence boundary so a following instruction ("Verify ...", "Then
#: report.") is never swallowed into the founder's literal text.
_CONTENT_CONTAINS = re.compile(
    r"\bcontains?\s+(?:exactly\s*)?:\s*(.+?)(?=\s*\.(?:\s+[A-Z]|\s*$))",
    re.I | re.S,
)

#: The destination file when the founder names it plainly -- "write it
#: into notes.txt", "save that to report.md" -- rather than in the
#: "file called X" shape `_FILE` above already covers. An extension is
#: still required, so an ordinary noun is never mistaken for a filename.
_FILE_TARGET = re.compile(
    r"\b(?:in|into|to)\s+[`'\"]?([^\s`'\"]+\.[A-Za-z0-9]+)",
    re.I,
)

#: A folder named without "called"/"named" -- "inside the folder Research",
#: "in folder KV_Test". `_FOLDER` above covers the explicit form; this
#: covers the one founders write just as often.
#:
#: The name must look like a name: no spaces, and not one of the ordinary
#: words that follow "folder" in a sentence. Without that guard "inside the
#: folder on the Desktop" would yield a folder called "on".
_FOLDER_BARE = re.compile(r"\bfolder\s+[`'\"]?([A-Za-z0-9_\-.]+)", re.I)

#: A file named without "called"/"named" -- "the file delete_me.txt". An
#: extension is still required, so an ordinary noun after "file" is never
#: taken for a filename.
_FILE_BARE = re.compile(r"\bfile\s+[`'\"]?([^\s`'\"]+\.[A-Za-z0-9]+)", re.I)
_NOT_A_NAME = frozenset({
    "on", "in", "at", "to", "of", "the", "a", "an", "and", "or", "then",
    "inside", "into", "from", "with", "for", "is", "it", "that", "this",
})

#: The founder asking for something to be removed. Their own word, never
#: inferred from argument shape: "delete"/"remove" said outright is a
#: statement of intent, and the permission boundary still holds the action
#: at the irreversible tier regardless of how the plan was produced.
_DELETE = re.compile(r"\b(?:delete|remove)\b", re.I)
_DELETE_FILE = "delete_file"

#: Words that point at a value stated elsewhere rather than supplying one.
#: "write it into notes.txt" has named no content, and treating the
#: pronoun as the text is exactly the kind of guess this lane refuses.
_PRONOUNS = frozenset({"it", "that", "this", "them", "the text", "the content"})

#: A phrase that REFERS to a value some earlier step is supposed to
#: produce, rather than supplying one.
#:
#: Caught live and badly: "write the observed title and final URL into
#: page_info.txt" was compiled with the literal string "the observed title
#: and final URL" as the file's contents, and that sentence was duly
#: written to the founder's Desktop instead of what the browser actually
#: saw. A value another step produces must arrive by binding or not at
#: all -- predicting it is the one thing this lane must never do.
_REFERENCE = re.compile(
    r"\b(?:observed|actual|you\s+(?:saw|observed|found|read)|the\s+(?:title|url|"
    r"result|output|response|answer|contents?\s+of))\b",
    re.I,
)

#: Operations this lane knows how to compile. Anything else in the
#: objective means it is not ours to claim.
#:
#: The same live failure showed why: an objective that also said "open a
#: browser… navigate… note the title… close the browser" was compiled into
#: a two-step filesystem plan, silently dropping four steps the founder had
#: asked for. Recognising part of a sentence is not understanding it, and a
#: partial plan is worse than no plan -- it runs.
_FOREIGN_OPERATION = re.compile(
    r"\b(?:browser|browse|navigate|open\s+(?:a\s+)?(?:browser|chrome|page|url)|"
    r"observe|screenshot|search|download|upload|email|send|move|copy|rename|"
    r"launch|focus|click|type|scroll|read\s+(?:the\s+)?file|extract|summari[sz]e|"
    r"compare|research|recommend)\b",
    re.I,
)


@dataclass(frozen=True)
class _Operation:
    """One operation the founder dictated, already proven complete."""

    kind: str
    payload: dict[str, Any]
    checkpoint: str = ""


def _literal_content(goal: str) -> str | None:
    """The founder's own words for what to write, or `None`.

    Never a guess, and never a value an earlier step is supposed to
    produce: `_local_capture_workflow` binds an observed title because
    nobody has looked at the page yet, and that stays true. This only ever
    returns something the founder actually typed.
    """
    trailing = _CONTENT_TRAILING.search(goal)
    if trailing:
        text = trailing.group(1).strip().strip("`'\"")
        if not text or _REFERENCE.search(text):
            return None
        return text
    inline = _CONTENT_INLINE.search(goal)
    if inline:
        text = inline.group(1).strip().strip("`'\"")
        if text.lower() in _PRONOUNS or _REFERENCE.search(text):
            return None
        return text or None
    contains = _CONTENT_CONTAINS.search(goal)
    if contains:
        text = contains.group(1).strip().strip("`'\"")
        if not text or text.lower() in _PRONOUNS or _REFERENCE.search(text):
            return None
        return text
    return None


#: "...containing the heading H followed by the sentence S".
#:
#: Two founder-stated parts and, in a Markdown file, a determined way to
#: join them: a heading occupies its own line -- that is what MAKES it a
#: heading. The separator is therefore the format the founder named, not
#: a guess about their intent.
#:
#: In a plain text file the same sentence really is underspecified,
#: because nothing there defines what a heading is, so this is applied
#: only to Markdown targets and the objective otherwise falls through to
#: the ladder unchanged.
_CONTENT_HEADING_SENTENCE = re.compile(
    r"\bcontaining\s+the\s+heading\s+(.+?)\s+followed\s+by\s+the\s+sentence\s+"
    # A sentence keeps its full stop: the founder said "the sentence",
    # and dropping it would write something they did not say.
    r"(.+?\.)(?=\s+[A-Z]|\s*$)",
    re.I | re.S,
)

#: Formats in which a heading has defined line semantics.
_MARKDOWN_SUFFIXES = (".md", ".markdown")


def _composed_markdown_content(goal: str, filename: str) -> str | None:
    """A heading and a sentence, joined the way Markdown joins them."""
    if not filename.lower().endswith(_MARKDOWN_SUFFIXES):
        return None
    match = _CONTENT_HEADING_SENTENCE.search(goal)
    if match is None:
        return None
    heading = match.group(1).strip().strip("`'\"")
    sentence = match.group(2).strip().strip("`'\"")
    if not heading or not sentence:
        return None
    if _REFERENCE.search(heading) or _REFERENCE.search(sentence):
        return None
    return heading + chr(10) + sentence


def _read_explicit_workflow(goal: str) -> list[_Operation] | None:
    """The dictated operations, in order, or `None` if anything is unclear.

    Deliberately narrow. It recognises the two filesystem operations whose
    arguments a founder routinely states in full, and refuses everything
    else — anything needing discovery, comparison, judgement, or a value
    nobody supplied. Widening this means adding a recogniser here, never
    loosening the proof below.
    """
    text = (goal or "").strip()
    if not text:
        return None

    # An objective naming work this lane cannot compile is not this lane's
    # to claim. Compiling the part it recognises would drop the rest, and a
    # partial plan is worse than none because it runs.
    if _FOREIGN_OPERATION.search(text):
        return None

    folder = _FOLDER.search(text)
    if folder is None:
        bare = _FOLDER_BARE.search(text)
        if bare is not None and bare.group(1).lower() not in _NOT_A_NAME:
            folder = bare
    filename = (
        _FILE.search(text) or _FILE_BARE.search(text)
        or _FILE_TARGET.search(text) or _FILE_CONTAINS.search(text)
    )
    place = _PLACE.search(text)

    # A dictated deletion: the founder named the operation, the file, the
    # folder and the place. Nothing here is inferred from argument shape --
    # `delete` is their own word -- and the permission boundary still holds
    # it at the irreversible tier, which is what makes planning it locally
    # safe as well as correct.
    if _DELETE.search(text) and folder is not None and filename is not None and place is not None:
        return [_Operation(
            kind=_DELETE_FILE,
            payload={
                "path": f"{folder.group(1).strip()}/{filename.group(1)}",
                "location": place.group(1).strip().lower(),
            },
        )]

    if folder is None or place is None:
        # No named folder, or no founder-stated place. Choosing a location
        # because none was given is precisely the guess the create-folder
        # completeness repair removed.
        return None
    if filename is None:
        # A folder on its own is already the single-capability path's job;
        # there is no second operation to compile here.
        return None

    content = _literal_content(text) or _composed_markdown_content(
        text, filename.group(1),
    )
    if content is None:
        # A file was named but not its contents, or the sentence pointed at
        # a value something else produces. Either way the dictation is
        # incomplete, and the ladder is the honest next step.
        return None

    folder_name = folder.group(1).strip()
    location = place.group(1).strip().lower()
    target = f"{folder_name}/{filename.group(1)}"

    checkpoint = ""
    if _CHECKPOINT.search(text):
        checkpoint = f"About to write this into {target}:\n\n{content}"

    return [
        _Operation(kind=_CREATE_FOLDER,
                   payload={"name": folder_name, "location": location}),
        _Operation(kind=_WRITE_FILE,
                   payload={"path": target, "location": location, "content": content},
                   checkpoint=checkpoint),
    ]



#: What a dictated operation asserts once it has run, in the founder's
#: own terms. Shared so recognition and planning cannot drift apart.
_EFFECT_DESCRIPTIONS = {
    _CREATE_FOLDER: lambda p: f"The folder {p['name']} exists in {p['location']}.",
    _WRITE_FILE: lambda p: (
        f"{p['path']} exists in {p['location']} and contains "
        f"the text the founder supplied."
    ),
    _DELETE_FILE: lambda p: f"{p['path']} no longer exists in {p['location']}.",
}


def dictated_effects(goal: str) -> tuple[str, ...]:
    """The effects a FULLY dictated objective states, or `()`.

    Recognition only. No catalogue is consulted, no capability is
    resolved, no plan is built and nothing is executed -- this answers
    one question, "has the founder already supplied every operation,
    argument and ordering", and it answers `()` on any doubt because
    `_read_explicit_workflow` does.

    It exists so the Intent Layer can establish requirements for such an
    objective WITHOUT a model. Compound is not the same as ambiguous: a
    three-sentence objective naming a folder, a file and its exact text
    has nothing left to interpret, and ADR-0027 is explicit that "creating
    a folder must not deliberate". Measured live 2026-09-05, that exact
    objective cost eight external calls and still failed.

    The Planner remains the only thing that turns this into steps. This
    is the Brain asking what the founder said, not the Brain planning.
    """
    operations = _read_explicit_workflow(goal)
    if not operations:
        return ()
    return tuple(
        _EFFECT_DESCRIPTIONS[op.kind](op.payload) for op in operations
    )


def _explicit_workflow(intent: Intent, options) -> MissionPlan | None:
    """A dictated multi-step plan compiled from the founder's own words."""
    operations = _read_explicit_workflow(getattr(intent, "goal", "") or "")
    if operations is None:
        return None

    found = {op.kind: find_option(op.kind, options) for op in operations}
    if any(option is None for option in found.values()):
        return None

    # Every payload key checked against what the capability actually
    # publishes, exactly as the one-step path does. A key the contract does
    # not name is a planning error, not something to send anyway.
    if any(not _usable(found[op.kind], op.payload) for op in operations):
        return None

    mark = uuid4().hex[:8]
    ids = [f"{op.kind}-{mark}" for op in operations]

    descriptions = {
        _CREATE_FOLDER: lambda op: (
            f"The folder {op.payload['name']} exists in {op.payload['location']}."
        ),
        _WRITE_FILE: lambda op: (
            f"{op.payload['path']} exists in {op.payload['location']} and contains "
            f"the text the founder supplied."
        ),
        _DELETE_FILE: lambda op: (
            f"{op.payload['path']} no longer exists in {op.payload['location']}."
        ),
    }

    # One requirement per operation the founder dictated -- the same
    # reading the browser lane uses, and faithful for the same reason:
    # in a dictated workflow the operations ARE the request, not
    # implementation detail the founder is indifferent to.
    requirements = _dictated_requirements(
        intent, [(EFFECT, descriptions[op.kind](op)) for op in operations]
    )
    requirement_ids = [r.requirement_id for r in requirements]

    return MissionPlan(
        steps=[
            Step(
                step_id=ids[position],
                capability=found[op.kind].name,
                payload=op.payload,
                # The founder's own "then". Each step waits for the one
                # before it, and `depends_on` stays the single ordering
                # authority.
                depends_on=ids[:position][-1:],
                expected_outcome=SuccessSpec(
                    description=descriptions[op.kind](op)
                ).to_expected_outcome(),
                founder_checkpoint=op.checkpoint,
                covers=(requirement_ids[position],),
                selection_reason=_selection_reason(
                    found[op.kind], requirements, (requirement_ids[position],)
                ),
            )
            for position, op in enumerate(operations)
        ],
        objective=intent.goal,
        requirements=requirements,
    )


# ──────────────────── generate-then-write, deterministically ────────────
#
# "Think of three short names for a gardening notes app and write them
# into names.txt on the Desktop."
#
# Nothing in that sentence says HOW. It does not need to: with
# `Reasoning.Transform` and `Filesystem.WriteFile` both registered, the
# shape is the only one they can form -- produce text, then write that
# text. Choosing it requires no judgement, and asking a model to choose
# it costs a 20,000-character catalogue prompt to be told the obvious.
#
# The founder's own measurement of the old behaviour, which is what this
# lane exists to end:
#
#     AI calls for PLANNING:              0   (required)
#     AI calls for Reasoning.Transform:   required
#
# The model is still needed -- it is the only thing that can invent three
# names. It is needed INSIDE the Transform, where the prompt is the
# actual instruction, and not in the choice of two capabilities.
#
# The content is never predicted here. `Reasoning.Transform` produces the
# text at run time, `TextVerifier` measures it into canonical Evidence,
# and `WriteFile.content` binds to that Evidence's `text` field. If the
# reasoning step produces nothing, or its Evidence does not match, the
# binding fails and no file is written -- which is the correct outcome,
# and the reason a literal is not used.

#: The founder asking for something to be invented. A verb of
#: origination, not of retrieval: "think of", "come up with",
#: "generate", "invent", "suggest", "brainstorm", "write me". These are
#: the openings that mean the answer is not in the sentence.
# --------------- dictated browser interaction workflows ---------------
#
# The failure this compiles away, in full. A founder typed:
#
#     Open a browser session and navigate to <url>. Type the text
#     acceptance into the element matching #acceptance-box, click the
#     element matching #apply, observe the page and tell me the current
#     text shown by #state, then close the browser session.
#
# Every material fact is in that sentence: the URL, both selectors, the
# text to type, which element to read, and the close. Nothing needs
# judgement. It nevertheless reached the AI Planner, because
# `_read_explicit_workflow` above refuses anything matching
# `_FOREIGN_OPERATION` -- and "Open a browser" matches it at offset 0.
#
# That refusal was right for THAT lane, which compiles filesystem work and
# would have dropped four browser clauses on the floor. It was never a
# statement that browser work is unplannable; it was a statement that the
# filesystem compiler must not pretend to understand it. So the answer is
# a lane that does, not a loosened guard on the one that does not.
#
# What it cost, measured from the ledger rather than guessed. Three
# desktop reasoning providers were walked -- one returned a plan the text
# verifier only PARTIALLY matched, one could not confirm its own prompt
# had landed in the composer, one could not establish conversation
# isolation -- before a cloud model produced a seven-step plan that read
# the page with `ReadPageText`, piped it into `Reasoning.Transform`, and
# failed on a binding because `ReadPageText` publishes no verified output
# to bind to. Roughly two minutes, four providers, and a browser window
# left open because the closing step never ran -- to answer a question the
# machine had already been told the answer to.
#
# ## Why clause-by-clause, rather than a pattern for the whole sentence
#
# `_local_capture_workflow` recognises one dictated workflow by matching
# its parts anywhere in the text. That works while there is one shape. It
# does not generalise, because "matched somewhere" cannot tell you what
# was NOT matched -- and the danger with a dictated sequence is never the
# clause you understood, it is the clause you silently ignored.
#
# So this splits the objective into clauses and requires EVERY clause to
# be claimed, in full, by exactly one recogniser. An unclaimed clause
# returns `None` and the ladder handles the objective exactly as before.
# The partial-plan guard is then structural rather than a list of things
# somebody has to remember to check when adding the next operation.

_CLICK = "click"
_TYPE_TEXT = "type_text"

#: How a founder separates dictated steps: sentence and list punctuation,
#: or the words "then" / "and".
#:
#: Punctuation only counts when whitespace follows it, which is what keeps
#: `http://127.0.0.1:8731/acceptance.html` in one piece -- its dots and
#: colons are internal. The final clause's trailing period is stripped
#: separately.
_CLAUSE_BREAK = re.compile(r"[.;,]\s+|\s+then\s+|\s+and\s+", re.I)

#: A CSS selector as founders actually write one: an id, a class, or an
#: attribute selector. Deliberately narrow. A bare word is never accepted
#: as a selector, because "click the button" names an intention while
#: `#submit` names an element, and only one of those is a fact the founder
#: supplied.
_SELECTOR = re.compile(r"^(?:[#.][A-Za-z_][A-Za-z0-9_-]*|\[[^\]]+\])$")

#: One recogniser per operation, every one applied with `fullmatch`, so a
#: clause is claimed only when it is understood END TO END. A clause that
#: is half-recognised is not recognised -- that is the whole point.
#: A word that only says "the next thing" -- it carries no material fact.
#:
#: Needed because the separators overlap: in ", then close the browser
#: session" the comma splits first, so the clause still begins with the
#: connective the other alternative would have consumed. Left in place it
#: made a perfectly ordinary close clause unclaimable, and the whole
#: objective was refused for a comma.
#:
#: Stripping is safe in a way inferring never is: removing "then" cannot
#: invent a URL, a selector or a value. If what remains still matches no
#: recogniser, the objective is refused exactly as before.
_LEADING_CONNECTIVE = re.compile(r"^(?:and|then|after\s+that|finally)\s+", re.I)

_C_OPEN = re.compile(r"open\s+(?:a|the)\s+browser(?:\s+session|\s+window|\s+tab)?", re.I)
_C_CLOSE = re.compile(r"close\s+(?:the\s+)?browser(?:\s+session|\s+window|\s+tab)?", re.I)
_C_NAVIGATE = re.compile(r"(?:navigate|go|browse)\s+to\s+(\S+)", re.I)
_C_TYPE = re.compile(
    r"type\s+(?:the\s+(?:text|value)\s+)?(.+?)\s+(?:in|into)\s+(?:the\s+)?"
    r"(?:element\s+(?:matching\s+|with\s+selector\s+)?)?(\S+)",
    re.I,
)
_C_CLICK = re.compile(
    r"click\s+(?:on\s+)?(?:the\s+)?"
    r"(?:element\s+(?:matching\s+|with\s+selector\s+)?)?(\S+)",
    re.I,
)
_C_OBSERVE = re.compile(r"(?:observe|look\s+at|examine)\s+(?:the\s+)?page", re.I)
#: The founder asking to be TOLD a value the page is showing. This clause
#: designates the mission's answer -- see `Step.answers_founder`.
_C_TELL = re.compile(
    r"(?:tell|show)\s+me\s+(?:the\s+)?(?:current\s+)?(?:text|value|contents?)\s+"
    r"(?:(?:shown|displayed|held|contained)\s+)?(?:by|in|of|at|on)\s+(\S+)",
    re.I,
)

#: Entry 0 of `elements` is the first selector this step asked for: the
#: observation contract guarantees one entry per requested selector, in
#: the order requested. Built as a path, never parsed out of prose.
_ELEMENT_TEXT = "elements.0.text"
_ELEMENTS = "elements"


def _clauses(goal: str) -> list[str]:
    """The founder's sentence as the separate instructions they wrote.

    Empty fragments are dropped and nothing else is: a clause that
    survives here must be claimed by a recogniser or the whole objective
    is refused, so discarding anything with content would defeat the very
    guard this exists to provide.
    """
    text = (goal or "").strip()
    if not text:
        return []
    parts = (
        _LEADING_CONNECTIVE.sub("", part.strip().strip(".;,").strip()).strip()
        for part in _CLAUSE_BREAK.split(text)
    )
    return [part for part in parts if part]


def _clean(value: str) -> str:
    return value.strip().strip("`'\"").rstrip(".,;?")


def _read_browser_workflow(goal: str) -> list[_Operation] | None:
    """The dictated browser sequence in the founder's own order, or `None`.

    Every clause must be claimed and every value must be theirs.
    """
    clauses = _clauses(goal)
    if not clauses:
        return None

    operations: list[_Operation] = []
    opens = closes = answers = 0

    for clause in clauses:
        if _C_OPEN.fullmatch(clause):
            opens += 1
            operations.append(_Operation(kind=_OPEN, payload={}))
            continue

        if _C_CLOSE.fullmatch(clause):
            closes += 1
            operations.append(_Operation(kind=_CLOSE, payload={}))
            continue

        match = _C_NAVIGATE.fullmatch(clause)
        if match:
            url = _clean(match.group(1))
            if not _URL.fullmatch(url):
                # "go to the settings page" names a destination nobody
                # stated as an address. Inventing one is the guess this
                # lane exists to refuse.
                return None
            operations.append(_Operation(kind=_NAVIGATE, payload={"url": url}))
            continue

        match = _C_TYPE.fullmatch(clause)
        if match:
            text = match.group(1).strip().strip("`'\"")
            selector = _clean(match.group(2))
            if not text or text.lower() in _PRONOUNS or _REFERENCE.search(text):
                # No literal was supplied, or the sentence points at a
                # value another step produces. Either way there is nothing
                # here to type, and predicting it is forbidden.
                return None
            if not _SELECTOR.fullmatch(selector):
                return None
            operations.append(_Operation(
                kind=_TYPE_TEXT, payload={"selector": selector, "text": text}
            ))
            continue

        match = _C_CLICK.fullmatch(clause)
        if match:
            selector = _clean(match.group(1))
            if not _SELECTOR.fullmatch(selector):
                return None
            operations.append(_Operation(kind=_CLICK, payload={"selector": selector}))
            continue

        if _C_OBSERVE.fullmatch(clause):
            operations.append(_Operation(kind=_OBSERVE, payload={"selectors": []}))
            continue

        match = _C_TELL.fullmatch(clause)
        if match:
            selector = _clean(match.group(1))
            if not _SELECTOR.fullmatch(selector):
                # "tell me what happened" asks for a summary, not for a
                # named element's text. Summarising is reasoning, and
                # reasoning is the ladder's job.
                return None
            answers += 1
            if answers > 1:
                # Two values requested, one place to report an answer.
                # Rather than choose which the founder meant, refuse.
                return None
            last = operations[-1] if operations else None
            if last is not None and last.kind == _OBSERVE and not last.payload["selectors"]:
                # "observe the page and tell me the text in #state" is one
                # instruction said twice. Attach the selector rather than
                # read the same page twice in a row.
                last.payload["selectors"].append(selector)
            else:
                operations.append(_Operation(
                    kind=_OBSERVE, payload={"selectors": [selector]}
                ))
            continue

        # Unclaimed. The founder said something this lane does not
        # understand, and compiling the rest would drop it.
        return None

    # ---- shape rules, every one of them about what was actually said ---
    if opens != 1 or closes > 1:
        return None
    if operations[0].kind != _OPEN:
        # Nothing can act on a session that is not open yet, and this lane
        # does not reorder the founder's sequence to make it work.
        return None
    if closes and operations[-1].kind != _CLOSE:
        return None
    if not [op for op in operations if op.kind not in (_OPEN, _CLOSE)]:
        # "Open a browser and close it" is not work. There is nothing here
        # worth a mission, so there is nothing to claim.
        return None
    return operations


#: What each step promises, stated before it runs.
#:
#: Type and click say DELIVERY and nothing more, deliberately. A page may
#: accept typed input and then reject it; a click may land and change
#: nothing. Writing "the text is in the field" here would be asserting an
#: outcome from the act of acting -- the same conflation the desktop mouse
#: closure removed. The observation that follows owns the page effect.
#: What the FOUNDER required, per dictated operation -- kind, and a
#: description in their terms. Distinct from `_BROWSER_EXPECTATION`
#: below, which says what a STEP promises: one is the request, the other
#: is the machine's claim about a call.
_BROWSER_REQUIREMENT = {
    _OPEN: (EFFECT, lambda p: "a browser session is open"),
    _NAVIGATE: (EFFECT, lambda p: f"the browser is at {p['url']}"),
    _TYPE_TEXT: (EFFECT, lambda p: f"{p['text']!r} is entered into {p['selector']}"),
    _CLICK: (EFFECT, lambda p: f"{p['selector']} is clicked"),
    _OBSERVE: (
        INFORMATION,
        lambda p: (f"the founder is told what {p['selectors'][0]} shows"
                   if p.get("selectors") else "the page is read"),
    ),
    _CLOSE: (EFFECT, lambda p: "the browser session is closed"),
}

_BROWSER_EXPECTATION = {
    _OPEN: lambda p: "A browser session is open and visible to the founder.",
    _NAVIGATE: lambda p: f"The browser session's current page is {p['url']}.",
    _TYPE_TEXT: lambda p: (
        f"The text was typed into {p['selector']}. Whether the page kept it "
        f"is a later observation's question, not this step's claim."
    ),
    _CLICK: lambda p: (
        f"The click was delivered to {p['selector']}. What it changed is a "
        f"later observation's question, not this step's claim."
    ),
    _OBSERVE: lambda p: (
        f"The page was read and {p['selectors'][0]} was observed."
        if p.get("selectors")
        else "The page's current title and URL are reported."
    ),
    _CLOSE: lambda p: "The browser session is closed.",
}


def _browser_workflow(intent: Intent, options) -> MissionPlan | None:
    """A dictated browser interaction sequence, compiled locally."""
    operations = _read_browser_workflow(getattr(intent, "goal", "") or "")
    if operations is None:
        return None

    found = {op.kind: find_option(op.kind, options) for op in operations}
    if any(option is None for option in found.values()):
        # A capability this objective needs is not registered. Half a
        # dictated sequence is not a smaller version of it.
        return None

    # The session is environment identity, not a founder fact -- nobody
    # types a session id -- and `_local_capture_workflow` has generated one
    # exactly this way since it was written.
    session_id = f"kv-{uuid4().hex[:8]}"
    mark = uuid4().hex[:8]

    # `headless` is False because the founder said "open a browser": an
    # instruction about something they expect to watch happen. The
    # contract publishes the argument precisely so this is a choice the
    # Planner makes rather than a default it inherits.
    extras: dict[str, dict[str, Any]] = {_OPEN: {"headless": False}}

    # What the founder required, one entry per operation they dictated.
    # `TYPE_TEXT` and `CLICK` are effects they asked for; they are also
    # the two this architecture cannot verify directly, which is why the
    # observation below is made to cover them as well.
    described = [(_BROWSER_REQUIREMENT[op.kind][0],
                  _BROWSER_REQUIREMENT[op.kind][1](op.payload))
                 for op in operations]
    requirements = _dictated_requirements(intent, described)
    ids = [r.requirement_id for r in requirements]
    # Every delivery-only operation before the observation that reads the
    # page. Its Evidence is what shows they took effect -- the same
    # delivery/outcome split the expectations below state, expressed as
    # coverage so conformance can use it.
    delivered_before_observation: list[str] = []
    for index, op in enumerate(operations):
        if op.kind in (_TYPE_TEXT, _CLICK) and index < len(ids):
            delivered_before_observation.append(ids[index])

    steps: list[Step] = []
    previous: str = ""

    for index, op in enumerate(operations):
        option = found[op.kind]
        payload: dict[str, Any] = {
            "session_id": session_id, **extras.get(op.kind, {}), **op.payload
        }
        reports = bool(op.kind == _OBSERVE and op.payload.get("selectors"))
        if op.kind == _OBSERVE and not payload["selectors"]:
            # An observation of the page as a whole. Passing an empty list
            # would be supplying an argument in order to say nothing.
            payload.pop("selectors")
        if not _usable(option, payload):
            # The contract does not publish an argument this step needs to
            # pass, so passing it would be guessing at the contract -- the
            # exact failure this module exists to prevent.
            return None
        if reports and _ELEMENTS not in set(getattr(option, "output_fields", ()) or ()):
            # The founder's answer would be read out of a field the
            # capability never promised. Refuse rather than depend on one.
            return None

        step_id = f"{op.kind}-{mark}-{index}"
        covered_by_this_step = (
            # The observation answers for itself AND for everything
            # delivered before it: a click's effect on the page is
            # exactly what this step re-reads.
            tuple([ids[index]] + delivered_before_observation)
            if op.kind == _OBSERVE and index < len(ids)
            else (ids[index],) if index < len(ids) else ()
        )
        steps.append(Step(
            step_id=step_id,
            capability=option.name,
            payload=payload,
            # The founder dictated one sequence, so each step waits for the
            # one before it. `depends_on` stays the sole ordering
            # authority, exactly as it is everywhere else.
            depends_on=[previous] if previous else [],
            expected_outcome=SuccessSpec(
                description=_BROWSER_EXPECTATION[op.kind](payload)
            ).to_expected_outcome(),
            answers_founder=_ELEMENT_TEXT if reports else "",
            covers=covered_by_this_step,
            selection_reason=_selection_reason(
                option, requirements, covered_by_this_step
            ),
        ))
        previous = step_id

    return MissionPlan(
        steps=steps, objective=intent.goal, requirements=requirements
    )


_GENERATE = re.compile(
    r"\b(?:think(?:\s+up|\s+of)?|come\s+up\s+with|generate|invent|"
    r"make\s+up|suggest|brainstorm|draft|compose)\b",
    re.I,
)

#: Where the produced text is to be put. Deliberately narrow: a file the
#: founder named, in a place the founder named. Anything vaguer is not a
#: dictated destination and belongs to a model.
_INTO_FILE = re.compile(
    r"\b(?:in|into|to)\s+(?:a\s+|the\s+)?(?:new\s+)?(?:text\s+)?file\s+"
    r"(?:called\s+|named\s+)?[`'\"]?([^\s`'\"]+\.[A-Za-z0-9]+)|"
    r"\b(?:in|into|to)\s+[`'\"]?([A-Za-z0-9_\-]+\.[A-Za-z0-9]+)",
    re.I,
)


#: The tail of the sentence that names the destination rather than the
#: work: "... and write them", "... then save it". Removed from the
#: instruction the model is given.
_TRAILING_WRITE = re.compile(
    r"[,;]?\s*(?:and\s+|then\s+)*(?:write|save|put|store|record|place)\s*"
    r"(?:them|it|those|these|that|the\s+(?:names|list|text|result|results))?\s*$",
    re.I,
)


def _read_generate_request(goal: str) -> tuple[str, str, str] | None:
    """`(instruction, filename, place)` for the generate-then-write shape.

    `None` on any doubt, as everywhere in this module. In particular this
    refuses anything naming work neither capability can do -- the same
    `_FOREIGN_OPERATION` guard that stops a partial plan being compiled
    from a sentence that was only partly understood.
    """
    text = (goal or "").strip()
    if not text or not _GENERATE.search(text):
        return None
    if _FOREIGN_OPERATION.search(text):
        return None
    # A folder to create, a file to delete, a page to open: other lanes
    # own those shapes, and a sentence carrying one is not this one.
    if _FOLDER.search(text) or _URL.search(text) or _DELETE.search(text):
        return None

    match = _INTO_FILE.search(text)
    place_match = _PLACE.search(text)
    if not match or not place_match:
        return None
    filename = (match.group(1) or match.group(2) or "").rstrip(".,;")
    if not filename:
        return None

    # The instruction is the founder's own words, up to the point where
    # they stop describing what to produce and start describing where to
    # put it. Never paraphrased: this is what the model will be asked,
    # and rewording a founder's request is not this module's business.
    instruction = text[: match.start()].strip().rstrip(",;").strip()
    # "...and write them" is the founder describing the destination, not
    # the thing to produce. It is cut, because this instruction becomes
    # the model's entire prompt and telling it to write a file is the one
    # thing `Reasoning.Transform` must never do -- it returns text and
    # touches nothing.
    instruction = _TRAILING_WRITE.sub("", instruction).strip().rstrip(",;").strip()
    if not instruction:
        return None
    return instruction, filename, place_match.group(1).capitalize()


def _generate_then_write(intent: Intent, options) -> MissionPlan | None:
    """`Reasoning.Transform` -> `Filesystem.WriteFile`, with a binding."""
    request = _read_generate_request(intent.goal)
    if request is None:
        return None
    instruction, filename, place = request

    found = {name: find_option(name, options) for name in (_TRANSFORM, _WRITE_FILE)}
    if any(option is None for option in found.values()):
        return None

    payloads = {
        # The prompt the model actually receives is this instruction --
        # not the capability catalogue. Stated plainly, and with the
        # shape of the answer named, because a file is about to be
        # written from it verbatim.
        _TRANSFORM: {
            "instruction": (
                f"{instruction}\n\n"
                "Return only the result itself, with nothing else -- no "
                "preamble, no numbering, no commentary, no quotes around it. "
                "It is going to be written into a file exactly as you return it."
            ),
            # Said out loud, because the contract requires it to be said.
            #
            # `Reasoning.Transform` defaults to `sensitive`, and it is right
            # to: its `context` is normally an earlier Step's output -- a
            # document off the founder's disk, a page from their session --
            # and treating that as public by default would quietly post it
            # to whichever provider ranked first.
            #
            # That reasoning cannot reach this step. This lane builds a
            # Transform with **no `context` and no `depends_on`**: nothing
            # from disk, from a session, or from any earlier Step can be in
            # it. What is sent is the founder's own sentence and nothing
            # else. So the careful default is guarding material that
            # structurally does not exist here, and the contract's own
            # provision applies -- "a plan that knows its material is
            # public may say so, but it has to say so."
            #
            # Measured, before this was said: `sensitive` reached the
            # Broker, `prefer_free` inherits `require_private_for_sensitive`,
            # every third-party provider was ruled NOT_PRIVATE, and the
            # only PRIVATE providers on this machine are Ollama (disabled
            # by the RAM policy) and LM Studio (not installed). Nothing was
            # eligible, so selection refused before `approval_needed()`
            # could offer the founder the choice, and the mission died with
            # "none eligible" rather than with a question.
            #
            # This is a statement about THIS step only. A lane that ever
            # binds a produced value into `context` is carrying the
            # founder's material and must leave the default alone.
            "sensitive": False,
        },
        _WRITE_FILE: {"path": filename, "location": place.lower()},
    }
    if not _usable(found[_TRANSFORM], payloads[_TRANSFORM]):
        return None
    if not _usable(found[_WRITE_FILE], payloads[_WRITE_FILE], bound=("content",)):
        return None

    # One mark per mission, exactly as the two lanes above do, and for the
    # identity reason `_single_capability_plan` records at length: a step
    # id must be unique across every mission this process EVER runs, not
    # merely within its own plan. `RuntimeEngine._objective_of()` finds a
    # task's objective by scanning every objective for a matching task id
    # and returning the FIRST hit.
    #
    # This lane shipped with `"step_1"`/`"step_2"` hard-coded, and the
    # consequence was measured in the packaged application rather than
    # reasoned about. The mission planned correctly, `Reasoning.Transform`
    # ran and produced "Sprout, Flora, Bud", and its Evidence came back
    # `matched` with the text in the observation -- and then
    # `Filesystem.WriteFile` was never dispatched at all. Its id collided
    # with 26 earlier records in the founder's own plan history, so it
    # resolved to a long-completed objective, and the founder watched
    # "that's taking longer than expected" about a step nothing would ever
    # run.
    #
    # It passed every source-path run because those had less history
    # behind them. That is the worst kind of defect: one that works until
    # the founder has used the application for a while.
    mark = uuid4().hex[:8]
    ids = {_TRANSFORM: f"{_TRANSFORM}-{mark}", _WRITE_FILE: f"{_WRITE_FILE}-{mark}"}
    steps = [
        Step(
            step_id=ids[_TRANSFORM],
            capability=found[_TRANSFORM].name,
            payload=payloads[_TRANSFORM],
            depends_on=[],
            input_bindings={},
            expected_outcome=SuccessSpec(
                description=f"Text is produced for: {instruction}",
                min_words=1,
            ).to_expected_outcome(),
        ),
        Step(
            step_id=ids[_WRITE_FILE],
            capability=found[_WRITE_FILE].name,
            payload=payloads[_WRITE_FILE],
            depends_on=[ids[_TRANSFORM]],
            # The produced text, read from the Evidence that measured it.
            # Never a literal: at planning time the answer does not exist.
            input_bindings={
                "content": {
                    "from_step": {"step_id": ids[_TRANSFORM], "field": "text"}
                }
            },
            expected_outcome=SuccessSpec(
                description=f"{filename} exists on the {place} holding the produced text",
            ).to_expected_outcome(),
        ),
    ]
    # Two requirements, and they are genuinely different kinds. The
    # founder wants text THOUGHT OF -- that is information they did not
    # have -- and they want it HANDED OVER as a file. A plan that
    # produced the text and failed to write it has met one and not the
    # other, and conformance should be able to say so.
    requirements = _dictated_requirements(intent, [
        (INFORMATION, f"text is produced for: {instruction}"),
        (DELIVERABLE, f"{filename} on the {place} holds that text"),
    ])
    steps[0].covers = (requirements[0].requirement_id,)
    steps[0].selection_reason = _selection_reason(
        found[_TRANSFORM], requirements, steps[0].covers
    )
    # The write answers for BOTH: it is the only step that can show the
    # produced text actually reached the founder, and its content is
    # bound from the reasoning step's verified Evidence.
    steps[1].covers = tuple(r.requirement_id for r in requirements)
    steps[1].selection_reason = _selection_reason(
        found[_WRITE_FILE], requirements, steps[1].covers
    )
    return MissionPlan(
        steps=steps, objective=intent.goal, requirements=requirements
    )


def direct_plan(intent: Intent, options) -> MissionPlan | None:
    """A plan written without a model, or `None` when one is genuinely needed.

    Four shapes qualify: a single capability the Intent Layer already
    named, the dictated browser-observe-write workflow, a dictated browser
    interaction sequence, and any explicitly dictated filesystem sequence
    whose operations, arguments and ordering the founder has already
    supplied in full. All four answer `None` on any doubt, and the Planner
    then asks a provider exactly as before.
    """
    plan = _single_capability_plan(intent, options)
    if plan is not None:
        return plan
    plan = _local_capture_workflow(intent, options)
    if plan is not None:
        return plan
    plan = _browser_workflow(intent, options)
    if plan is not None:
        return plan
    plan = _generate_then_write(intent, options)
    if plan is not None:
        return plan
    return _explicit_workflow(intent, options)
