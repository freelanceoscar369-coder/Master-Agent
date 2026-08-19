"""Intent Layer — turns raw input into structured Intent.

Constitution §3.1: The Intent Layer turns raw input into structured Intent
(goal, constraints, context, success criteria). Owns follow-up clarification
when ambiguous. Deliberately not "send raw string to a model" — real
parsing/clarification step so Planner never guesses.

This replaces the regex-based parse_intent() stand-in from cli.py.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from master_agent.brain.agency import roles
from master_agent.planner.plan import Intent


@dataclass
class ClarificationQuestion:
    """A question the Intent Layer needs answered before producing Intent."""
    question: str
    key: str
    options: tuple[str, ...] = ()
    required: bool = True


@dataclass
class IntentResult:
    """Result of intent parsing: either an Intent or a clarification request."""
    intent: Intent | None = None
    clarification: ClarificationQuestion | None = None
    raw_input: str = ""

    @property
    def needs_clarification(self) -> bool:
        return self.clarification is not None


#: Connectives with which a founder strings requirements together. Their
#: presence means the sentence carries more than one thing to do, whoever
#: ends up doing it.
_SEQUENCING_CONNECTIVES: tuple[str, ...] = (
    " then ", " and then ", " after that ", " followed by ",
)


def enumerates_multiple_requirements(text: str) -> bool:
    """Did the founder ask for more than one thing in this message?

    ## Why this exists

    Every specialised parser in this module is a COMPLETE-COMMAND
    recogniser: fifteen of their regexes are anchored to end-of-string and
    several to start-of-string, because each was written to recognise a
    sentence that *is* its command. None was written to extract a phrase
    out of a larger objective.

    The dispatcher, however, selected them with a substring test --
    `if pattern in text.lower()`. So a five-requirement objective that
    merely *mentioned* creating a folder was handed whole to
    `CreateFolderIntent`, whose end-anchored patterns then found no name
    mid-sentence and asked for one. Observed live:

        Onkar:  Open a browser and navigate to https://example.com.
                Observe the page's actual title and final URL. Create a
                folder called KV_MEDIUM_155505 on Desktop. Inside that
                folder create a text file called page_info.txt ... Then
                close the browser.
        Somesh: What should the folder be called?

    The browser, the observation, the file and the shutdown were discarded
    before a mission existed -- not because anything misunderstood them,
    but because a substring decided who owned the sentence. The same
    objective phrased "make a directory named ..." produced a correct
    generic Intent carrying the whole request, which proves the failure was
    routing rather than understanding.

    ## What is being detected

    Not *what* the founder wants -- that is the Planner's to work out.
    Only whether they enumerated more than one requirement, which is the
    boundary at which a single-command recogniser stops being the right
    reader. Two signals, both structural and both the founder's own
    punctuation and connectives:

      * more than one sentence carrying content;
      * an explicit sequencing connective ("then", "after that", ...).

    ## What this deliberately is not

    Not a classifier, not a decomposer, and not a second router. It answers
    one yes/no question and changes nothing about meaning. Decomposition
    stays with the Planner, which already receives the complete objective
    through the generic route and is the layer the Constitution gives that
    job to.

    STATED LIMIT: a genuine single command whose own words contain a
    connective -- `create a folder called then on Desktop` -- is treated as
    compound and travels the generic route. It is still planned and still
    executed; it simply is not fast-pathed. Deterministic and documented,
    and the safe direction to err: the generic route loses no requirement,
    while the fast path can lose four.
    """
    import re

    stripped = (text or "").strip()
    if not stripped:
        return False

    sentences = [s for s in re.split(r"[.!?]+(?:\s+|$)", stripped) if s.strip()]
    if len(sentences) > 1:
        return True

    lowered = f" {stripped.lower()} "
    return any(c in lowered for c in _SEQUENCING_CONNECTIVES)


class IntentLayer:
    """Parses raw input into structured Intent.

    Uses rule-based parsing with deterministic patterns. For ambiguous input
    that could map to multiple valid intents, requests clarification from
    the user rather than guessing. Never calls a model directly — the
    Planner handles model calls.
    """

    def __init__(self) -> None:
        # Patterns are tried in order; first match wins
        # More specific patterns first
        self._patterns: list[tuple[str, type]] = [
            # Folder patterns must all precede the generic ("create",
            # CreateProjectIntent) catch-all below -- first match wins.
            # Only "create a folder called" was listed, so "Create a
            # folder" (no name yet, which is exactly the case that needs
            # clarifying) fell through to the PROJECT parser and asked
            # "What should the project be called?" about a folder.
            ("create a folder called", CreateFolderIntent),
            ("create a folder named", CreateFolderIntent),
            ("create a folder", CreateFolderIntent),
            ("create folder", CreateFolderIntent),
            ("create a new folder", CreateFolderIntent),
            ("make a folder", CreateFolderIntent),
            ("set up a project called", SetUpProjectIntent),  # "set up a project called X"
            ("set up a project named", SetUpProjectIntent),  # "set up a project named X"
            ("set up a", SetUpProjectIntent),  # "set up a demo project" - specific first
            ("create", CreateProjectIntent),   # catches "create a project", "create a python project", etc.
            ("look at", LookAtIntent),         # "look at this machine" - scanning
            ("read", ReadFileIntent),
            ("rename", RenameFileIntent),
            ("copy", CopyFileIntent),
            ("move", MoveFileIntent),
            ("delete", DeleteIntent),
            ("list files", ListDirectoryIntent),
            ("search for", SearchFilesIntent),
        ]

    #: Phrases that mean *"tell me what you can do"* rather than *"do
    #: something"*. Deliberately the same rule-based, first-match-wins
    #: shape as `_patterns` above — this is the existing Intent Layer
    #: learning one more distinction, not a second classifier sitting
    #: beside it. A question about capabilities has no goal to plan
    #: toward, so routing it to the Planner can only ever produce a
    #: refusal (proven live: "the available capabilities cannot achieve
    #: this objective" for "what all you can do right now").
    _CAPABILITY_QUESTION_PATTERNS: tuple[str, ...] = (
        "what can you do",
        "what all can you do",
        "what all you can do",
        "what do you can do",
        "what are you capable of",
        "what are your capabilities",
        "what capabilities",
        "list your capabilities",
        "tell me your capabilities",
        "know your capabilities",
        "what can you help",
        "what else can you do",
        "what can i ask you",
        "what should i ask you",
    )

    def is_capability_question(self, text: str) -> bool:
        """Is this input asking *what* the system can do, rather than
        asking it to do something?

        A predicate rather than an `IntentResult` variant on purpose: the
        answer is not an Intent at all — there is nothing to plan — and
        the decision it feeds is a *routing* one, made by the Founder
        Surface before a mission is ever created. Keeping it here keeps
        the vocabulary in the one layer that already owns "what did the
        founder mean", instead of scattering phrase-matching into the
        surface.
        """
        lowered = (text or "").strip().lower()
        if not lowered:
            return False
        return any(pattern in lowered for pattern in self._CAPABILITY_QUESTION_PATTERNS)

    def parse(self, text: str, supplied: Mapping[str, str] | None = None) -> IntentResult:
        """Parse raw input into Intent or clarification request."""
        text = text.strip()
        if not text:
            # Pass empty input to planner - let it refuse
            return IntentResult(
                intent=Intent(
                    goal="",
                    constraints=[],
                    context={"raw_input": text},
                    success_criteria=[],
                ),
                raw_input=text,
            )

        # Try exact patterns first -- but only for a message that asks for
        # ONE thing. Every parser below is a complete-command recogniser
        # (see `enumerates_multiple_requirements`); offering one a compound
        # objective lets a substring match decide who owns a sentence, and
        # four of Onkar's five requirements were discarded that way.
        #
        # A compound objective is not refused and not decomposed here. It
        # travels the generic route below, which preserves it whole, and the
        # Planner -- the layer that owns decomposition -- plans it.
        if not enumerates_multiple_requirements(text):
            for pattern, handler in self._patterns:
                if pattern in text.lower():
                    return self._with_roles(handler().parse(text, supplied), text)

        # Fallback: generic intent for any input (allows Planner to handle
        # it). ADR-0024 Decision 3: lexical unfamiliarity is not semantic
        # ambiguity. That this layer holds no pattern for a sentence is a
        # fact about this layer's vocabulary, not about whether the founder
        # was clear -- so unmatched-but-clear input travels on rather than
        # becoming an interrogation.
        #
        # `success_criteria` is deliberately EMPTY here, where it used to
        # hold `f"Objective completed: {text}"`. That echoed the prompt back
        # as though it were a criterion: it named nothing checkable, and
        # Verification (§10) cannot compare observed reality against a
        # restatement of the request. ADR-0024 §8 -- preserve uncertainty
        # rather than invent a criterion. The typed parsers above, which
        # know what they parsed, still state real ones ("Folder 'Research'
        # exists at Desktop").
        return self._with_roles(
            IntentResult(
                intent=Intent(
                    goal=text,
                    constraints=[],
                    context={"raw_input": text},
                    success_criteria=[],
                ),
                raw_input=text,
            ),
            text,
        )

    @staticmethod
    def _with_roles(result: IntentResult, text: str) -> IntentResult:
        """Stamp derived agency onto whatever a parser produced.

        Applied HERE rather than inside each of the twelve parsers: agency
        is a property of the founder's sentence, not of which action the
        sentence happened to name, so deriving it once at the one entry
        point keeps a single implementation and makes it impossible for a
        new parser to be added without it.

        A clarification result carries no `Intent` to stamp and is returned
        untouched -- there is no agency to preserve on a question.
        """
        if result.intent is None:
            return result
        actor, beneficiary = roles(text)
        result.intent.actor = actor
        result.intent.beneficiary = beneficiary
        return result

    def clarify(
        self,
        original: str,
        answer: str,
        question: ClarificationQuestion | None = None,
        supplied: Mapping[str, str] | None = None,
    ) -> IntentResult:
        """Resolve a pending clarification with the founder's answer.

        ## The limitation this method used to carry, and how it is fixed

        The previous body was `self.parse(f"{original} {answer}")` --
        rejoin the two strings and parse the result -- with its own
        docstring stating the flaw:

            "It therefore only resolves cleanly when `original` ends where
            the missing value belongs. A general fix would fill
            `ClarificationQuestion.key` directly instead of re-parsing
            prose -- the field exists for that -- but nothing in
            production calls this method yet, so the resolution loop is
            not wired end-to-end and that change belongs with whoever
            wires it."

        It genuinely did not work for the ordinary case: `"Create a
        folder"` + `"Research"` rejoins to `"Create a folder Research"`,
        which has no `called`, so the parser found no name and asked the
        same question again -- an infinite loop the founder could not
        escape. `"Create a folder in Documents"` + `"Research"` failed the
        same way *and* would have dropped the location.

        This is that general fix. The answer is passed as **data**, keyed
        by `question.key`, and the original sentence is re-parsed
        unchanged -- so everything the founder already said (a location, a
        project type, a constraint) is re-derived from their own words
        rather than reconstructed from a rejoined string, and only the
        genuinely missing field comes from the answer.

        `question` is optional so the older two-argument form keeps
        working for callers that have no question to hand; without it the
        rejoin is all that can be done, and it is still better than
        nothing.
        """
        if question is not None and question.key:
            # Answers from EARLIER rounds first, then this one. An
            # objective that needs two fields cannot be resolved from the
            # original sentence plus a single reply: re-parsing "Create a
            # folder" with only `{"location": "Desktop"}` loses the name
            # given a turn earlier. `supplied` carries what is already
            # resolved so each round adds a field rather than replacing
            # the set. The founder's original sentence is still what gets
            # re-parsed, so anything they stated themselves continues to
            # win over anything reconstructed.
            answers: dict[str, str] = dict(supplied or {})
            answers[question.key] = answer
            result = self.parse(original, supplied=answers)
            if result.intent is not None:
                # Provenance, not contract. The founder's ORIGINAL sentence
                # stays the raw input -- overwriting it with "Research"
                # would lose what was actually asked for -- and the answer
                # is recorded beside it, keyed, so an audit can tell the
                # request from the reply to a question about it.
                result.intent.context.setdefault("raw_input", original)
                # Every answer that built this Intent, not only the last
                # one -- an audit reading `clarified` should see the whole
                # resolution, and on a two-round objective the last answer
                # alone explains neither the folder's name nor its place.
                result.intent.context["clarified"] = dict(answers)
            return result
        combined = f"{original} {answer}".strip()
        return self.parse(combined)


# --- Specific Intent Parsers ---

class BaseIntentParser:
    """Base class for specific intent parsers.

    `supplied` carries answers the founder has already given to this
    layer's own clarification questions, keyed by
    `ClarificationQuestion.key`. A parser consults it for exactly the
    field it was about to ask about, and for nothing else.

    This is what `clarify()`'s docstring said the general fix would be --
    *"fill `ClarificationQuestion.key` directly instead of re-parsing
    prose -- the field exists for that"* -- and it works because every
    parser already declares its own key. Nothing here maps a key to a
    phrase template or re-renders the founder's sentence: the parser that
    knows what it was missing is the one that fills it.
    """

    def parse(self, text: str, supplied: Mapping[str, str] | None = None) -> IntentResult:
        raise NotImplementedError

    @staticmethod
    def _answer(supplied: Mapping[str, str] | None, key: str) -> str | None:
        """The founder's answer for `key`, or `None` if they gave none.

        Empty and whitespace-only answers are `None` on purpose: a founder
        who pressed enter on a blank line has not named anything, and
        accepting `""` would invent a nameless folder rather than ask
        again (ADR-0024 Decision 3, and the standing rule that a missing
        parameter is not permission to invent one).
        """
        if not supplied:
            return None
        value = str(supplied.get(key, "") or "").strip()
        return value or None


class CreateFolderIntent(BaseIntentParser):
    r"""Parse 'create a folder called X [on/in Y]'.

    TWO PATTERNS, TRIED IN ORDER, rather than one pattern with an optional
    trailing group. The single-pattern form was
    `...called\s+([^"'.]+)(?:\s+(?:on|in)\s+...)?$`, whose name group is
    greedy and matches spaces, so the engine preferred letting the name
    consume the whole tail and skipping the optional location entirely:

        "create a folder called Research on my Desktop"
            -> name = "Research on my Desktop"
        "create a folder called Research in Documents"
            -> name = "Research in Documents", location silently "Desktop"

    The second case is the serious one: an explicit founder location was
    discarded and replaced by a default, so the folder would have been
    created somewhere the founder did not ask for.

    Anchoring the location clause in its own pattern removes the
    ambiguity: either the input ends with an "on/in <place>" clause and
    the name is what precedes it, or it does not and the whole tail is the
    name. Nothing is guessed either way.
    """

    #: The name runs to the end of the input. Used only after the
    #: with-location pattern has already failed.
    _NAME_ONLY = (
        r"create\s+(?:a\s+|an\s+|new\s+|a\s+new\s+)?folder\s+"
        r"(?:called|named)\s+[\"']?(?P<name>[^\"'.]+?)[\"']?\.?\s*$"
    )
    #: The location clause is anchored to the end, so the name group can no
    #: longer swallow it. `name` is lazy; `location` takes the last
    #: on/in clause.
    _NAME_AND_LOCATION = (
        r"create\s+(?:a\s+|an\s+|new\s+|a\s+new\s+)?folder\s+"
        r"(?:called|named)\s+[\"']?(?P<name>[^\"'.]+?)[\"']?"
        r"\s+(?:on|in)\s+(?:my\s+|the\s+)?(?P<location>[\w\s]+?)\.?\s*$"
    )
    #: A location with NO name -- "create a folder in Documents". Neither
    #: pattern above matches it, because both require `called`/`named`, so
    #: before clarification could resolve it the location was simply lost:
    #: the founder was asked for a name, answered it, and the folder was
    #: created wherever the action's default put it. The founder had
    #: already said where. This pattern is only consulted once the name
    #: arrives from a clarification answer, so it can never compete with
    #: the two above for an ordinary one-shot command.
    _LOCATION_ONLY = (
        r"create\s+(?:a\s+|an\s+|new\s+|a\s+new\s+)?folder\s+"
        r"(?:on|in)\s+(?:my\s+|the\s+)?(?P<location>[\w\s]+?)\.?\s*$"
    )

    def parse(self, text: str, supplied: Mapping[str, str] | None = None) -> IntentResult:
        import re

        location: str | None = None
        match = re.search(self._NAME_AND_LOCATION, text, re.IGNORECASE)
        if match:
            location = match.group("location").strip()
        else:
            match = re.search(self._NAME_ONLY, text, re.IGNORECASE)

        name = match.group("name").strip() if match else ""

        if not name:
            # The founder may already have answered this exact question.
            # Their answer fills the name and nothing else -- the location
            # below is still read from THEIR original sentence, so
            # "create a folder in Documents" keeps Documents rather than
            # falling back to whatever the action's default is.
            name = self._answer(supplied, "folder_name") or ""
            if name and location is None:
                located = re.search(self._LOCATION_ONLY, text, re.IGNORECASE)
                if located:
                    location = located.group("location").strip()

        if not name:
            return IntentResult(
                clarification=ClarificationQuestion(
                    question="What should the folder be called?",
                    key="folder_name",
                    required=True,
                ),
                raw_input=text,
            )

        # WHERE is Founder-owned information, exactly as WHAT-IT-IS-CALLED
        # is, and an unstated location is now a question rather than a
        # gap for something downstream to fill.
        #
        # It was not always. The Intent Layer correctly refused to write
        # `location or "Desktop"` -- product policy does not belong in the
        # Brain -- and left an unstated location unstated, on the reasoning
        # that `CreateFolderAction` publishes its own default and applies
        # it in `run()`. That reasoning is sound about DEFAULTS and wrong
        # about MEANING, and the difference showed up live:
        #
        #     Onkar:  Create a folder.
        #     Somesh: What should the folder be called?
        #     Onkar:  Research
        #     -> created on the Desktop
        #
        # Onkar never said Desktop. The action's default supplied a piece
        # of the founder's meaning that the founder had not given, and it
        # did so silently, because by then the Intent was already
        # "complete" and nothing was left to ask.
        #
        # An action default answers "what should this argument be when a
        # caller omits it" -- a question about an API. Founder intent asks
        # "what did Onkar mean" -- a question about a person. The action
        # keeps its default for its other callers (see
        # `optional_parameters`); it simply no longer gets to complete a
        # founder's sentence. Completeness is decided here, upstream, and
        # is deliberately NOT derived from the capability schema: changing
        # that default to Documents tomorrow must not change what Onkar is
        # asked today.
        if location is None:
            location = self._answer(supplied, "location")
        if location is None:
            return IntentResult(
                clarification=ClarificationQuestion(
                    # Uses what is already known. "Where should I create
                    # the Research folder?" reads as the same request
                    # continuing; a generic "Please provide a location"
                    # reads as a form. Deterministic string composition --
                    # no model is asked to phrase a question this layer
                    # already has all the words for.
                    question=f"Where should I create the {name} folder?",
                    key="location",
                    required=True,
                ),
                raw_input=text,
            )

        context: dict[str, Any] = {"folder_name": name, "location": location}
        constraints: list[str] = [f"Location: {location}"]

        where = f" at {location}"

        # The capability this sentence named, and its arguments under the
        # contract's OWN names (`name`, `location`) rather than this
        # parser's internal `folder_name`. `context` keeps the parser's
        # vocabulary for the prompt and for anything reading provenance;
        # `payload` is what a Step actually needs.
        #
        # Stating it costs nothing and saves a model call: the Planner can
        # see that "create a folder called Research in Documents" means
        # `Filesystem.CreateFolder(name="Research", location="Documents")`
        # without asking a provider to rediscover a mapping this parser
        # already performed. Whether that capability is registered, and
        # whether its contract is satisfied, remains the Planner's call.
        # Both fields, always. `location` is no longer conditional here:
        # execution is not reached until the founder has resolved it, so
        # the capability is always called with an explicit founder-owned
        # location and never falls through to its own default.
        payload: dict[str, Any] = {"name": name, "location": location}

        return IntentResult(
            intent=Intent(
                goal=f"Create folder '{name}'",
                constraints=constraints,
                context=context,
                success_criteria=[f"Folder '{name}' exists{where}"],
                capability="create_folder",
                payload=payload,
            ),
            raw_input=text,
        )


class CreateProjectIntent(BaseIntentParser):
    """Parse 'create a [type] project called X'."""

    def parse(self, text: str, supplied: Mapping[str, str] | None = None) -> IntentResult:
        import re
        match = re.search(
            r"create\s+(?:a\s+new\s+|a\s+|an\s+|new\s+)?(?:(?P<type>[A-Za-z][\w.+#-]*)\s+)?(?:project|application)\s+(?:called|named)\s+[\"']?([^\"'.]+)[\"']?\.?\s*$",
            text,
            re.IGNORECASE,
        )
        if not match:
            return IntentResult(
                clarification=ClarificationQuestion(
                    question="What should the project be called?",
                    key="project_name",
                    required=True,
                ),
                raw_input=text,
            )

        project_type = (match.group("type") or "generic").strip().lower()
        name = match.group(2).strip()

        if not name:
            return IntentResult(
                clarification=ClarificationQuestion(
                    question="What should the project be called?",
                    key="project_name",
                    required=True,
                ),
                raw_input=text,
            )

        return IntentResult(
            intent=Intent(
                goal=f"Create {project_type} project '{name}'",
                constraints=[f"Project type: {project_type}"],
                context={"project_name": name, "project_type": project_type},
                success_criteria=[
                    f"Project '{name}' created with standard structure",
                    f"Project type '{project_type}' template applied",
                ],
            ),
            raw_input=text,
        )


class ReadFileIntent(BaseIntentParser):
    """Parse 'read X'."""

    def parse(self, text: str, supplied: Mapping[str, str] | None = None) -> IntentResult:
        import re
        match = re.search(r"^read\s+(?:the\s+file\s+)?(?P<path>\S+?)\.?\s*$", text, re.IGNORECASE)
        if not match:
            return IntentResult(
                clarification=ClarificationQuestion(
                    question="Which file should I read?",
                    key="file_path",
                    required=True,
                ),
                raw_input=text,
            )

        path = match.group("path").strip()
        return IntentResult(
            intent=Intent(
                goal=f"Read file '{path}'",
                constraints=["Read-only operation"],
                context={"path": path, "location": "desktop"},
                success_criteria=[f"File '{path}' content returned"],
            ),
            raw_input=text,
        )


class RenameFileIntent(BaseIntentParser):
    """Parse 'rename X to Y'."""

    def parse(self, text: str, supplied: Mapping[str, str] | None = None) -> IntentResult:
        import re
        match = re.search(r"^rename\s+(?P<path>\S+?)\s+to\s+(?P<new_name>\S+?)\.?\s*$", text, re.IGNORECASE)
        if not match:
            return IntentResult(
                clarification=ClarificationQuestion(
                    question="What should I rename, and to what?",
                    key="rename_details",
                    required=True,
                ),
                raw_input=text,
            )

        path = match.group("path").strip()
        new_name = match.group("new_name").strip()
        return IntentResult(
            intent=Intent(
                goal=f"Rename '{path}' to '{new_name}'",
                constraints=["Modifies filesystem"],
                context={"path": path, "new_name": new_name, "location": "desktop"},
                success_criteria=[f"File renamed from '{path}' to '{new_name}'"],
            ),
            raw_input=text,
        )


class CopyFileIntent(BaseIntentParser):
    """Parse 'copy X to Y'."""

    def parse(self, text: str, supplied: Mapping[str, str] | None = None) -> IntentResult:
        import re
        match = re.search(r"^copy\s+(?P<path>\S+?)\s+to\s+(?P<destination>.+?)\.?\s*$", text, re.IGNORECASE)
        if not match:
            return IntentResult(
                clarification=ClarificationQuestion(
                    question="What should I copy, and where?",
                    key="copy_details",
                    required=True,
                ),
                raw_input=text,
            )

        path = match.group("path").strip()
        destination = match.group("destination").strip()
        return IntentResult(
            intent=Intent(
                goal=f"Copy '{path}' to '{destination}'",
                constraints=["Modifies filesystem"],
                context={"path": path, "destination": destination, "location": "desktop"},
                success_criteria=[f"File copied to '{destination}'"],
            ),
            raw_input=text,
        )


class MoveFileIntent(BaseIntentParser):
    """Parse 'move X to Y'."""

    def parse(self, text: str, supplied: Mapping[str, str] | None = None) -> IntentResult:
        import re
        match = re.search(r"^move\s+(?P<path>\S+?)\s+to\s+(?P<destination>.+?)\.?\s*$", text, re.IGNORECASE)
        if not match:
            return IntentResult(
                clarification=ClarificationQuestion(
                    question="What should I move, and where?",
                    key="move_details",
                    required=True,
                ),
                raw_input=text,
            )

        path = match.group("path").strip()
        destination = match.group("destination").strip()
        return IntentResult(
            intent=Intent(
                goal=f"Move '{path}' to '{destination}'",
                constraints=["Modifies filesystem"],
                context={"path": path, "destination": destination, "location": "desktop"},
                success_criteria=[f"File moved to '{destination}'"],
            ),
            raw_input=text,
        )


class DeleteIntent(BaseIntentParser):
    """Parse 'delete X [folder]'."""

    def parse(self, text: str, supplied: Mapping[str, str] | None = None) -> IntentResult:
        import re
        match = re.search(r"^delete\s+(?P<path>.+?)\.?\s*$", text, re.IGNORECASE)
        if not match:
            return IntentResult(
                clarification=ClarificationQuestion(
                    question="What should I delete?",
                    key="delete_path",
                    required=True,
                ),
                raw_input=text,
            )

        raw = match.group("path").strip()
        is_folder = raw.lower().endswith(" folder")
        path = raw[:-7].strip() if is_folder else raw

        return IntentResult(
            intent=Intent(
                goal=f"Delete {'folder' if is_folder else 'file'} '{path}'",
                constraints=["Irreversible operation", "Modifies filesystem"],
                context={"path": path, "is_folder": is_folder, "location": "desktop"},
                success_criteria=[f"{'Folder' if is_folder else 'File'} '{path}' deleted"],
            ),
            raw_input=text,
        )


class ListDirectoryIntent(BaseIntentParser):
    """Parse 'list files inside X'."""

    def parse(self, text: str, supplied: Mapping[str, str] | None = None) -> IntentResult:
        import re
        match = re.search(
            r"^list\s+(?:the\s+)?files\s+(?:inside|in|on)\s+(?:my\s+|the\s+)?(?P<location>[\w\s]+?)\.?\s*$",
            text,
            re.IGNORECASE,
        )
        if not match:
            return IntentResult(
                clarification=ClarificationQuestion(
                    question="Which folder should I list?",
                    key="location",
                    required=True,
                ),
                raw_input=text,
            )

        raw_location = match.group("location").strip()
        location_key = raw_location.lower()

        return IntentResult(
            intent=Intent(
                goal=f"List files in {raw_location}",
                constraints=["Read-only operation"],
                context={"path": ".", "location": location_key},
                success_criteria=[f"Files in {raw_location} listed"],
            ),
            raw_input=text,
        )


class SearchFilesIntent(BaseIntentParser):
    """Parse 'search for X'."""

    def parse(self, text: str, supplied: Mapping[str, str] | None = None) -> IntentResult:
        import re
        match = re.search(r"^search\s+for\s+(?P<pattern>\S+?)\.?\s*$", text, re.IGNORECASE)
        if not match:
            return IntentResult(
                clarification=ClarificationQuestion(
                    question="What should I search for?",
                    key="pattern",
                    required=True,
                ),
                raw_input=text,
            )

        pattern = match.group("pattern").strip()
        return IntentResult(
            intent=Intent(
                goal=f"Search for '{pattern}'",
                constraints=["Read-only operation"],
                context={"pattern": pattern, "location": "desktop"},
                success_criteria=[f"Files matching '{pattern}' returned"],
            ),
            raw_input=text,
        )


class SetUpProjectIntent(BaseIntentParser):
    """Parse 'set up a [type] project called X' or 'set up a demo project' or 'set up a project for X'."""

    def parse(self, text: str, supplied: Mapping[str, str] | None = None) -> IntentResult:
        import re
        # Match "set up a [type] project called X" or "set up a project named X"
        match = re.search(
            r"set\s+up\s+(?:a\s+)?(?:(?P<type>[A-Za-z][\w.+#-]*)\s+)?(?:project|application)\s+(?:called|named)\s+[\"']?(?P<name>[^\"'.]+?)[\"']?\.?\s*$",
            text,
            re.IGNORECASE,
        )
        if not match:
            # Try alternative: "set up a demo project" (no "called/named")
            alt_match = re.search(
                r"set\s+up\s+(?:a\s+)?(?P<name>[A-Za-z][\w.+#-]*)\s+(?:project|application)\.?\s*$",
                text,
                re.IGNORECASE,
            )
            if alt_match:
                name = alt_match.group("name").strip()
                project_type = "generic"
            else:
                # Try "set up a project for X"
                alt_match2 = re.search(
                    r"set\s+up\s+(?:a\s+)?(?:(?P<type>[A-Za-z][\w.+#-]*)\s+)?(?:project|application)\s+for\s+[\"']?(?P<name>[^\"'.]+?)[\"']?\.?\s*$",
                    text,
                    re.IGNORECASE,
                )
                if alt_match2:
                    project_type = (alt_match2.group("type") or "generic").strip().lower()
                    name = alt_match2.group("name").strip()
                else:
                    return IntentResult(
                        clarification=ClarificationQuestion(
                            question="What should the project be called?",
                            key="project_name",
                            required=True,
                        ),
                        raw_input=text,
                    )
        else:
            project_type = (match.group("type") or "generic").strip().lower()
            name = match.group("name").strip()

        if not name:
            return IntentResult(
                clarification=ClarificationQuestion(
                    question="What should the project be called?",
                    key="project_name",
                    required=True,
                ),
                raw_input=text,
            )

        return IntentResult(
            intent=Intent(
                goal=f"Create {project_type} project '{name}'",
                constraints=[f"Project type: {project_type}"],
                context={"project_name": name, "project_type": project_type},
                success_criteria=[
                    f"Project '{name}' created with standard structure",
                    f"Project type '{project_type}' template applied",
                ],
            ),
            raw_input=text,
        )


class LookAtIntent(BaseIntentParser):
    """Parse 'look at X' - for scanning/machine inspection."""

    def parse(self, text: str, supplied: Mapping[str, str] | None = None) -> IntentResult:
        import re
        match = re.search(r"^look\s+at\s+(?P<target>.+?)\.?\s*$", text, re.IGNORECASE)
        if not match:
            return IntentResult(
                clarification=ClarificationQuestion(
                    question="What should I look at?",
                    key="target",
                    required=True,
                ),
                raw_input=text,
            )

        target = match.group("target").strip()
        return IntentResult(
            intent=Intent(
                goal=f"Look at {target}",
                constraints=["Read-only operation"],
                context={"target": target},
                success_criteria=[f"{target} scanned and reported"],
            ),
            raw_input=text,
        )