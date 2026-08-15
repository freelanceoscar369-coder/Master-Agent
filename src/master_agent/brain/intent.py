"""Intent Layer — turns raw input into structured Intent.

Constitution §3.1: The Intent Layer turns raw input into structured Intent
(goal, constraints, context, success criteria). Owns follow-up clarification
when ambiguous. Deliberately not "send raw string to a model" — real
parsing/clarification step so Planner never guesses.

This replaces the regex-based parse_intent() stand-in from cli.py.
"""
from __future__ import annotations

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

    def parse(self, text: str) -> IntentResult:
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

        # Try exact patterns first
        for pattern, handler in self._patterns:
            if pattern in text.lower():
                return self._with_roles(handler().parse(text), text)

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

    def clarify(self, original: str, answer: str) -> IntentResult:
        """Process a clarification answer and re-parse.

        The separator used to be an em-dash, which the parsers then read
        as part of the value: answering "Research" to "create a folder
        called" produced a folder literally named "— Research". A plain
        space keeps the rejoined sentence in the same shape the parsers
        already expect.

        KNOWN LIMITATION, stated rather than papered over: this rejoins
        two strings and re-parses. It therefore only resolves cleanly when
        `original` ends where the missing value belongs. A general fix
        would fill `ClarificationQuestion.key` directly instead of
        re-parsing prose -- the field exists for that -- but nothing in
        production calls this method yet, so the resolution loop is not
        wired end-to-end and that change belongs with whoever wires it.
        """
        combined = f"{original} {answer}".strip()
        return self.parse(combined)


# --- Specific Intent Parsers ---

class BaseIntentParser:
    """Base class for specific intent parsers."""

    def parse(self, text: str) -> IntentResult:
        raise NotImplementedError


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

    def parse(self, text: str) -> IntentResult:
        import re

        location: str | None = None
        match = re.search(self._NAME_AND_LOCATION, text, re.IGNORECASE)
        if match:
            location = match.group("location").strip()
        else:
            match = re.search(self._NAME_ONLY, text, re.IGNORECASE)

        if not match:
            return IntentResult(
                clarification=ClarificationQuestion(
                    question="What should the folder be called?",
                    key="folder_name",
                    required=True,
                ),
                raw_input=text,
            )

        name = match.group("name").strip()

        if not name:
            return IntentResult(
                clarification=ClarificationQuestion(
                    question="What should the folder be called?",
                    key="folder_name",
                    required=True,
                ),
                raw_input=text,
            )

        # No location is NOT the same as location "Desktop". The Intent
        # Layer used to write `location = match.group(2) or "Desktop"`,
        # which is product policy living in the Brain -- and it is policy
        # the action already owns: `CreateFolderAction` publishes
        # `location` as optional with its own default, and its `run()`
        # falls back to that default when the argument is absent. So an
        # unstated location is simply left unstated here, and the action
        # contract applies its own default downstream. Nothing is invented,
        # and the default lives in exactly one place.
        context: dict[str, Any] = {"folder_name": name}
        constraints: list[str] = []
        if location is not None:
            context["location"] = location
            constraints.append(f"Location: {location}")

        where = f" at {location}" if location is not None else ""
        return IntentResult(
            intent=Intent(
                goal=f"Create folder '{name}'",
                constraints=constraints,
                context=context,
                success_criteria=[f"Folder '{name}' exists{where}"],
            ),
            raw_input=text,
        )


class CreateProjectIntent(BaseIntentParser):
    """Parse 'create a [type] project called X'."""

    def parse(self, text: str) -> IntentResult:
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

    def parse(self, text: str) -> IntentResult:
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

    def parse(self, text: str) -> IntentResult:
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

    def parse(self, text: str) -> IntentResult:
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

    def parse(self, text: str) -> IntentResult:
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

    def parse(self, text: str) -> IntentResult:
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

    def parse(self, text: str) -> IntentResult:
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

    def parse(self, text: str) -> IntentResult:
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

    def parse(self, text: str) -> IntentResult:
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

    def parse(self, text: str) -> IntentResult:
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