"""Intent Layer — turns raw input into structured Intent.

Constitution §3.1: The Intent Layer turns raw input into structured Intent
(goal, constraints, context, success criteria). Owns follow-up clarification
when ambiguous. Deliberately not "send raw string to a model" — real
parsing/clarification step so Planner never guesses.

This replaces the regex-based parse_intent() stand-in from cli.py.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from master_agent.brain.agency import roles
from master_agent.brain.utterance import UtteranceRole, structural_role
from master_agent.planner.direct import dictated_effects
from master_agent.planner.plan import (
    CONSTRAINT,
    EFFECT,
    INFORMATION,
    REQUIREMENT_KINDS,
    UNSETTLED_INTERPRETATION,
    Intent,
    SemanticRequirement,
)


@dataclass
class ClarificationQuestion:
    """A question the Intent Layer needs answered before producing Intent."""
    question: str
    key: str
    options: tuple[str, ...] = ()
    required: bool = True
    #: EVERY field this parser is gathering, not only the one being asked
    #: about right now.
    #:
    #: A founder answering "where?" with *"actually call it Finance and
    #: put it in Documents"* has settled two fields and revised one. The
    #: layer can only notice that if it knows which fields are in play --
    #: and only the parser knows, because only the parser knows what its
    #: capability needs. Empty means "just the one being asked", which is
    #: the historical behaviour.
    gathering: tuple[str, ...] = ()


@dataclass
class IntentResult:
    """Result of intent parsing: either an Intent or a clarification request."""
    intent: Intent | None = None
    clarification: ClarificationQuestion | None = None
    raw_input: str = ""
    #: The founder's own words for every field resolved so far.
    #:
    #: Carried beside `resolved` for the same reason `resolved` exists at
    #: all: without it, a value settled two turns ago arrives with
    #: nothing to audit it against, and a requirement built from it can
    #: only compare the interpretation with itself.
    evidence: dict[str, dict[str, str]] = field(default_factory=dict)
    #: Every field resolved so far, canonically, across all rounds.
    #:
    #: The caller carries this into the next round instead of
    #: accumulating raw replies. Without it the surface rebuilt
    #: `supplied` from what the founder typed -- so even once `clarify()`
    #: understood "on my desktop" as `desktop`, the NEXT round was handed
    #: the sentence again and the understanding was thrown away between
    #: turns. The same defect, one layer up.
    resolved: dict[str, str] = field(default_factory=dict)

    @property
    def needs_clarification(self) -> bool:
        return self.clarification is not None


@dataclass(frozen=True)
class RequirementAdmission:
    """The Intent owner's review of one proposed decomposition.

    This is not another Intent representation.  ``requirements`` is the
    existing canonical tuple; everything else is the bounded admission
    verdict that explains why that tuple was or was not allowed to become
    Intent.  It contains structured conclusions, never hidden reasoning.
    """

    requirements: tuple[SemanticRequirement, ...] = ()
    valid: bool = False
    semantic_verdict: str = "invalid"
    founder_obligation_anchors: tuple[dict[str, Any], ...] = ()
    coverage_mapping: tuple[dict[str, Any], ...] = ()
    unmapped_anchors: tuple[dict[str, Any], ...] = ()
    improper_merges: tuple[dict[str, Any], ...] = ()
    invented_requirements: tuple[dict[str, Any], ...] = ()
    founder_obligations_preserved: tuple[dict[str, Any], ...] = ()
    merged_obligations: tuple[dict[str, Any], ...] = ()
    lost_obligations: tuple[dict[str, Any], ...] = ()
    invented_obligations: tuple[dict[str, Any], ...] = ()
    independently_verifiable: bool = False
    structural_issues: tuple[str, ...] = ()
    detected_structural_issues: tuple[str, ...] = ()
    detected_merged_obligations: tuple[dict[str, Any], ...] = ()
    detected_lost_obligations: tuple[dict[str, Any], ...] = ()
    detected_invented_obligations: tuple[dict[str, Any], ...] = ()
    detected_founder_obligation_anchors: tuple[dict[str, Any], ...] = ()
    detected_coverage_mapping: tuple[dict[str, Any], ...] = ()
    correction_attempted: bool = False
    corrected: bool = False
    initial_provider_output: tuple[dict[str, Any], ...] = ()
    final_provider_output: tuple[dict[str, Any], ...] = ()
    #: Stage 1C. The Founder obligation set is itself a root of trust, so
    #: the evidence that established it is recorded beside the evidence
    #: that policed the decomposition below it. `source_regions` is
    #: deterministic; everything else is what the blind producer proposed
    #: and what the independent auditor said about it.
    source_regions: tuple[str, ...] = ()
    region_dispositions: tuple[dict[str, Any], ...] = ()
    anchor_entailment: tuple[dict[str, Any], ...] = ()
    obligation_issues: tuple[str, ...] = ()
    initial_obligation_anchors: tuple[dict[str, Any], ...] = ()
    obligation_correction_attempted: bool = False
    obligation_corrected: bool = False
    #: Stage 1D. The candidate state units the deterministic scaffold
    #: exposed, where the audit placed each one, and any anchor the
    #: placements showed holding more than one satisfaction state.
    state_candidates: tuple[dict[str, Any], ...] = ()
    state_placements: tuple[dict[str, Any], ...] = ()
    intra_anchor_fusion: tuple[dict[str, Any], ...] = ()
    #: Whether the semantic REVIEW itself needed one bounded repair --
    #: a translation fault, distinct from correcting the requirements.
    review_correction_attempted: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "semantic_verdict": self.semantic_verdict,
            "source_regions": list(self.source_regions),
            "region_dispositions": [
                dict(row) for row in self.region_dispositions
            ],
            "anchor_entailment": [dict(row) for row in self.anchor_entailment],
            "obligation_issues": list(self.obligation_issues),
            "initial_obligation_anchors": [
                dict(row) for row in self.initial_obligation_anchors
            ],
            "obligation_correction_attempted":
                self.obligation_correction_attempted,
            "obligation_corrected": self.obligation_corrected,
            "state_candidates": [dict(row) for row in self.state_candidates],
            "state_placements": [dict(row) for row in self.state_placements],
            "intra_anchor_fusion": [
                dict(row) for row in self.intra_anchor_fusion
            ],
            "review_correction_attempted": self.review_correction_attempted,
            "founder_obligation_anchors": [
                dict(row) for row in self.founder_obligation_anchors
            ],
            "coverage_mapping": [dict(row) for row in self.coverage_mapping],
            "unmapped_anchors": [dict(row) for row in self.unmapped_anchors],
            "improper_merges": [dict(row) for row in self.improper_merges],
            "invented_requirements": [
                dict(row) for row in self.invented_requirements
            ],
            "founder_obligations_preserved": [
                dict(row) for row in self.founder_obligations_preserved
            ],
            "merged_obligations": [dict(row) for row in self.merged_obligations],
            "lost_obligations": [dict(row) for row in self.lost_obligations],
            "invented_obligations": [
                dict(row) for row in self.invented_obligations
            ],
            "independently_verifiable": self.independently_verifiable,
            "structural_issues": list(self.structural_issues),
            "detected_structural_issues": list(self.detected_structural_issues),
            "detected_merged_obligations": [
                dict(row) for row in self.detected_merged_obligations
            ],
            "detected_lost_obligations": [
                dict(row) for row in self.detected_lost_obligations
            ],
            "detected_invented_obligations": [
                dict(row) for row in self.detected_invented_obligations
            ],
            "detected_founder_obligation_anchors": [
                dict(row) for row in self.detected_founder_obligation_anchors
            ],
            "detected_coverage_mapping": [
                dict(row) for row in self.detected_coverage_mapping
            ],
            "correction_attempted": self.correction_attempted,
            "corrected": self.corrected,
            "initial_provider_output": [
                dict(row) for row in self.initial_provider_output
            ],
            "final_provider_output": [
                dict(row) for row in self.final_provider_output
            ],
        }


#: Punctuation a founder wraps a value in without meaning it.
_VALUE_STRIP = " \t.,!?;:'\"()"

#: How long a reply can be and still read as a plain value rather than a
#: sentence. "Quarterly Report", "the second one", "C:/Users/Onkar" are
#: values; anything longer is doing something a value does not do, and
#: belongs to the stage that can read it.
_BARE_VALUE_WORDS = 4


#: Words that carry no fact of their own around a value.
#:
#: Grammar, not phrasings. Prepositions, determiners, politeness, the
#: copula, the generic verbs of putting and choosing, and the generic
#: nouns for a container. Nothing here names a PLACE or a THING; the
#: moment it did, this would be the phrase table that must not exist.
#:
#: It exists so that a vocabulary match can be checked for having
#: accounted for the whole utterance. Its failure direction is the safe
#: one: a word this list does not know makes the reply UNACCOUNTED FOR,
#: which escalates to reasoning or to a question -- never to a confident
#: wrong answer.
_GRAMMAR_WORDS: frozenset[str] = frozenset({
    # prepositions
    "on", "in", "at", "to", "into", "inside", "under", "within", "from",
    "for", "onto", "of",
    # determiners and pronouns
    "the", "a", "an", "my", "your", "our", "its", "it", "this", "that",
    "there", "i", "we", "you",
    # politeness and filler
    "please", "thanks", "thank", "ok", "okay", "just", "actually",
    "really", "maybe", "perhaps", "well",
    # copula and auxiliaries
    "is", "are", "be", "will", "would", "could", "can", "should",
    "lets", "let", "s", "d", "id", "ill",
    # generic verbs of placing or choosing
    "put", "place", "use", "using", "stick", "save", "keep", "make",
    "create", "go", "set", "like", "want", "prefer", "drop",
    # generic container nouns
    "folder", "directory", "dir", "location",
    # assent
    "fine", "good", "great", "right", "sure", "yes", "yeah", "instead",
    # conjunctions, and the verbs of NAMING -- "call it X" says nothing
    # about X beyond that it is the name
    "and", "then", "also", "plus", "with", "call", "called", "name",
    "named", "title", "titled",
})


def _unaccounted_by(text: str, values: Any) -> set[str]:
    """The founder's words that NOTHING resolved so far explains.

    The same accounting as `_unaccounted`, over every value settled
    rather than one -- because the question is not "did this match
    explain the sentence" but "does what we now believe explain it".
    """
    leftover = _tokens_of(text)
    for value in values:
        spelled = str(value).lower()
        # Both spellings. A capability value may use an underscore where
        # the founder said two words (`d_drive` for "d drive"), and a
        # founder's own value may contain one they typed (`KVIntent_C`).
        # Subtracting only the expanded form left `kvintent_c` looking
        # unexplained by its own name.
        leftover -= {spelled}
        leftover -= set(spelled.replace("_", " ").replace("/", " ").split())
    return leftover - _GRAMMAR_WORDS


def _tokens_of(text: str) -> set[str]:
    # Apostrophes are removed rather than listed: "let's" and "lets" are
    # one word wearing two spellings, and a grammar list that has to
    # carry both is a list that will miss the third.
    return {
        word.strip(_VALUE_STRIP).lower().replace("'", "").replace("’", "")
        for word in (text or "").split()
        if word.strip(_VALUE_STRIP)
    }


def _unaccounted(text: str, value: str) -> set[str]:
    """The founder's words this match did NOT explain.

    A vocabulary scan finds a value the capability accepts ANYWHERE in a
    reply. That is what makes "put it on my desktop please" work without
    any phrasing being enumerated -- and it is also what let

        d drive in Onkar folder

    resolve to `d_drive` while silently discarding "in Onkar folder".
    The folder was created in the wrong place and the founder was told
    "This did what you asked for."

    Matching part of a sentence is not understanding it. This returns
    what is left over once the matched value and pure grammar are taken
    out; anything remaining is a fact nobody has accounted for, and the
    caller must not settle the field on structure alone.
    """
    return _unaccounted_by(text, (value,))


#: What joins one clause to another. A reply built out of two clauses may
#: be saying two things, and is worth reading properly.
_CLAUSE_JOINS: tuple[str, ...] = (",", ";", " and ", " but ", " then ")


#: "call it X", "name it X", "called X" -- the founder NAMING something.
#:
#: Grammar, like the prepositions before it. The construction says only
#: that what follows is the name; it carries no opinion about what the
#: name is, which is why recognising it is not a phrase table.
#:
#: It earns its place by removing a model from the commonest multi-field
#: reply. Asked to extract from "call it Finance and put it in
#: Documents", the production reasoner returned the PLACE and not the
#: name -- the accounting then correctly refused the half-answer, and the
#: founder was asked something they had already answered. Structure can
#: settle this, so structure should.
#: A word boundary, spelled without an escape a heredoc can eat.
_WORD = chr(92) + "b"
_QUOTE = chr(91) + chr(34) + chr(39) + chr(93) + "?"
_NOT_BREAK = chr(91) + "^" + chr(34) + chr(39) + ",;" + chr(93) + "+?"
_NAME_ENDS = r"(?=\s+(?:and|then)\s|\s*[,;]|$)"

_NAMING = re.compile(
    _WORD + r"(?:call|name|title)\s+(?:it|them|this|that)?\s*"
    + _QUOTE + r"(?P<value>" + _NOT_BREAK + r")" + _QUOTE + _NAME_ENDS,
    re.IGNORECASE,
)
#: The same, said the other way round: "called X", "named X".
_NAMED = re.compile(
    _WORD + r"(?:called|named|titled)\s+"
    + _QUOTE + r"(?P<value>" + _NOT_BREAK + r")" + _QUOTE + _NAME_ENDS,
    re.IGNORECASE,
)


def _named_value(text: str) -> str:
    """What the founder said to call it, or `""`."""
    for pattern in (_NAMED, _NAMING):
        found = pattern.search(text or "")
        if found:
            value = found.group("value").strip().strip("\"'")
            if value:
                return value
    return ""


def _said_for(recorded: Mapping[str, Any], field_name: str, value: Any) -> str:
    """The founder's own words behind one resolved argument.

    Matched by field name first, and by VALUE second, because the two
    vocabularies legitimately differ: the parser gathers `folder_name`
    and the capability's argument is `name`. A lookup that only tried the
    argument name silently returned nothing for the one field a founder
    always supplies -- so the requirement carried the interpretation with
    nothing to audit it against, which is the circularity being removed.
    """
    row = recorded.get(field_name)
    if isinstance(row, Mapping) and row.get("evidence"):
        return str(row["evidence"])
    wanted = str(value)
    for candidate in recorded.values():
        if isinstance(candidate, Mapping) and str(candidate.get("value")) == wanted:
            return str(candidate.get("evidence") or "")

    # A COMPOSED argument, whose parts were each evidenced separately.
    #
    # `CreateFolder` takes one `name`, and a nested destination makes it
    # "Onkar/Rudra" out of two fields the founder supplied in two
    # different turns. Neither lookup above can see that: the argument
    # is not called `parent` and its value equals nothing recorded.
    #
    # Measured, and it is the worst possible field to lose. The audit of
    # "where does founder evidence become only the resolved value" found
    # its FIRST and only point here -- on the requirement encoding the
    # nested destination, which is precisely what both failed
    # acceptances got wrong. A requirement carrying "name = Onkar/Rudra"
    # and nothing else can only be checked against the reading that
    # produced it.
    segments = [part for part in wanted.replace(chr(92), "/").split("/") if part]
    if len(segments) > 1:
        spoken: list[str] = []
        for candidate in recorded.values():
            if not isinstance(candidate, Mapping):
                continue
            if str(candidate.get("value")) not in segments:
                continue
            said = str(candidate.get("evidence") or "")
            if said and said not in spoken:
                spoken.append(said)
        if spoken:
            return "; ".join(spoken)
    return ""


def _is_single_clause(text: str) -> bool:
    """Does this reply say one thing?

    Not a judgement about meaning -- a judgement about shape, used only
    to decide whether a second reading could find anything the first one
    missed. Being wrong costs a provider call, never a wrong answer.
    """
    lowered = f" {(text or '').strip().lower()} "
    return not any(join in lowered for join in _CLAUSE_JOINS)


def _is_bare_value(text: str) -> bool:
    """Is this reply a value, rather than a sentence about one?

    Short, and not built out of clauses. Deliberately crude, because it
    is only ever a FAST PATH: everything it declines goes to the stage
    that can actually read a sentence, so being wrong here costs a
    provider call rather than a wrong answer.
    """
    stripped = (text or "").strip()
    if not stripped or len(stripped.split()) > _BARE_VALUE_WORDS:
        return False
    return not any(mark in stripped for mark in (",", ";", " and ", " but "))


def _parsed_json(text: str) -> dict[str, Any] | None:
    """The JSON object in a reply, or `None`.

    Tolerates a fenced block and surrounding prose, because a model
    routinely wraps JSON in both. Refuses everything else: output that
    cannot be parsed is output that never becomes Intent.
    """
    import json as _json

    body = (text or "").strip()
    if "```" in body:
        parts = body.split("```")
        body = max(parts, key=len)
        if body.lstrip().lower().startswith("json"):
            body = body.lstrip()[4:]
    start, end = body.find("{"), body.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        document = _json.loads(body[start:end + 1])
    except Exception:  # noqa: BLE001 -- unparseable output is not a crash
        return None
    return document if isinstance(document, dict) else None


def _semantic_span(text: str) -> str:
    """Comparable founder language without changing the retained quote."""
    return " ".join((text or "").casefold().split()).strip()


def _grounded_in(objective: str, quote: str) -> bool:
    grounded = _semantic_span(quote)
    return bool(grounded and grounded in _semantic_span(objective))


def requirement_structure_issues(objective: str, offered: Any) -> list[str]:
    """Deterministic defects in a proposed semantic requirement set.

    This deliberately does not pretend grammar can decide atomicity.  It
    establishes the facts that *can* be proved without semantic judgement:
    every row is readable, uses the closed kind vocabulary, identifies its
    candidate scope, names a separately verifiable success state, and points
    to Founder language that actually exists.  Atomicity, coverage and
    invention are reviewed separately after this gate.
    """
    if not isinstance(offered, list) or not offered:
        return ["the provider returned no non-empty requirements list"]

    issues: list[str] = []
    descriptions: set[str] = set()
    for index, item in enumerate(offered, start=1):
        if not isinstance(item, dict):
            issues.append(f"item {index} is not a requirement object")
            continue
        kind = str(item.get("kind", "") or "").strip().lower()
        description = str(item.get("description", "") or "").strip()
        source_quote = str(item.get("source_quote", "") or "").strip()
        success_meaning = str(item.get("success_meaning", "") or "").strip()
        if kind not in REQUIREMENT_KINDS:
            issues.append(
                f"item {index} has kind {kind!r}, not one of "
                f"{', '.join(REQUIREMENT_KINDS)}"
            )
        if not description:
            issues.append(f"item {index} has no canonical description")
        elif _semantic_span(description) in descriptions:
            issues.append(f"item {index} duplicates another requirement")
        else:
            descriptions.add(_semantic_span(description))
        if not source_quote:
            issues.append(f"item {index} has no Founder source_quote")
        elif not _grounded_in(objective, source_quote):
            issues.append(
                f"item {index} source_quote {source_quote!r} is not in the "
                "Founder input"
            )
        if not success_meaning:
            issues.append(
                f"item {index} has no independently checkable success_meaning"
            )
        if not isinstance(item.get("candidate_property"), bool):
            issues.append(
                f"item {index} must state candidate_property as true or false"
            )
    return issues


def _audit_structure_issues(
    objective: str, offered: list[dict[str, Any]], audit: Any,
) -> list[str]:
    """Whether an obligation-level semantic projection is inspectable."""
    if not isinstance(audit, dict):
        return ["the semantic-integrity review was not a JSON object"]
    if not isinstance(audit.get("valid"), bool):
        return ["the semantic-integrity review did not state valid true/false"]
    if not isinstance(audit.get("independently_verifiable"), bool):
        return ["the semantic-integrity review did not settle verifiability"]

    issues: list[str] = []
    for name in ("anchors", "coverage", "invented"):
        if not isinstance(audit.get(name), list):
            issues.append(f"the semantic-integrity review field {name!r} is not a list")
    if issues:
        return issues

    anchors = audit["anchors"]
    anchor_ids: set[str] = set()
    anchor_semantics: set[tuple[str, str]] = set()
    for position, anchor in enumerate(anchors, start=1):
        if not isinstance(anchor, dict):
            issues.append(f"anchor {position} is not an object")
            continue
        anchor_id = str(anchor.get("anchor_id", "") or "").strip()
        source_quote = str(anchor.get("source_quote", "") or "").strip()
        meaning = str(anchor.get("meaning", "") or "").strip()
        depends_on = anchor.get("depends_on")
        if not anchor_id:
            issues.append(f"anchor {position} has no anchor_id")
        elif anchor_id in anchor_ids:
            issues.append(f"anchor {position} duplicates anchor_id {anchor_id!r}")
        else:
            anchor_ids.add(anchor_id)
        if not source_quote or not _grounded_in(objective, source_quote):
            issues.append(f"anchor {anchor_id or position!r} is not Founder-grounded")
        if not meaning:
            issues.append(f"anchor {anchor_id or position!r} has no semantic meaning")
        semantic_key = (_semantic_span(source_quote), _semantic_span(meaning))
        if all(semantic_key) and semantic_key in anchor_semantics:
            issues.append(
                f"anchor {anchor_id or position!r} duplicates an obligation under "
                "a new id"
            )
        anchor_semantics.add(semantic_key)
        if not isinstance(depends_on, list) or not all(
            isinstance(item, str) and item.strip() for item in depends_on or ()
        ):
            issues.append(
                f"anchor {anchor_id or position!r} must state depends_on as a list "
                "of anchor ids"
            )

    for anchor in anchors:
        if not isinstance(anchor, dict):
            continue
        anchor_id = str(anchor.get("anchor_id", "") or "").strip()
        for dependency in anchor.get("depends_on") or ():
            if dependency == anchor_id:
                issues.append(f"anchor {anchor_id!r} depends on itself")
            elif dependency not in anchor_ids:
                issues.append(
                    f"anchor {anchor_id!r} depends on unknown anchor {dependency!r}"
                )

    limit = len(offered)
    covered_anchor_ids: list[str] = []
    for position, row in enumerate(audit["coverage"], start=1):
        if not isinstance(row, dict):
            issues.append(f"coverage item {position} is not an object")
            continue
        anchor_id = str(row.get("anchor_id", "") or "").strip()
        indices = row.get("requirement_indices")
        if anchor_id not in anchor_ids:
            issues.append(
                f"coverage item {position} names unknown anchor {anchor_id!r}"
            )
        else:
            covered_anchor_ids.append(anchor_id)
        if not isinstance(indices, list):
            issues.append(
                f"coverage item {position} requirement_indices is not a list"
            )
        else:
            for index in indices:
                if not isinstance(index, int) or not 1 <= index <= limit:
                    issues.append(
                        f"coverage item {position} has invalid requirement index "
                        f"{index!r}"
                    )
        if not isinstance(row.get("independently_trackable"), bool):
            issues.append(
                f"coverage item {position} must state independently_trackable"
            )

    if len(covered_anchor_ids) != len(set(covered_anchor_ids)):
        issues.append("an obligation anchor has more than one coverage row")
    missing_coverage = sorted(anchor_ids - set(covered_anchor_ids))
    if missing_coverage:
        issues.append(
            "the coverage projection omits obligation anchors: "
            + ", ".join(missing_coverage)
        )

    for position, row in enumerate(audit["invented"], start=1):
        if not isinstance(row, dict):
            issues.append(f"invented item {position} is not an object")
            continue
        index = row.get("requirement_index")
        if not isinstance(index, int) or not 1 <= index <= limit:
            issues.append(
                f"invented item {position} has no valid requirement_index"
            )
        if not str(row.get("reason", "") or "").strip():
            issues.append(f"invented item {position} has no reason")

    # Sentence-scale regions prove that an entire Founder statement was not
    # omitted. They are source coverage, not obligation boundaries: commas,
    # verbs and `and` are deliberately untouched.
    for region in _founder_source_regions(objective):
        region_span = _semantic_span(region)
        if not any(
            _semantic_span(str(anchor.get("source_quote", "") or "")) in region_span
            or region_span in _semantic_span(
                str(anchor.get("source_quote", "") or "")
            )
            for anchor in anchors if isinstance(anchor, dict)
        ):
            issues.append(
                "no Founder obligation anchor accounts for source region "
                f"{region!r}"
            )
    return issues


def _founder_source_regions(objective: str) -> tuple[str, ...]:
    """Sentence-scale source coverage, never an obligation splitter."""
    import re

    flattened = " ".join((objective or "").split())
    if not flattened:
        return ()
    return tuple(
        part.strip()
        for part in re.split(r"(?<=[.!?;])\s+(?=[A-Z])", flattened)
        if part.strip()
    )


#: A coordinated predicate becomes its own candidate region only when both
#: sides carry enough language to stand as an obligation. "Save and verify
#: report.md" stays one region -- its left side is a bare verb -- while
#: "Research the products ... and give me the top 3" becomes two. This is
#: VISIBILITY, not atomicity: the scaffold never decides what is one
#: obligation, only that a phrase may not disappear unexplained.
_MIN_REGION_WORDS = 2

#: How a Founder source region may be accounted for. Closed, because an
#: open vocabulary is how "we looked at it" becomes indistinguishable from
#: "we explained it".
REPRESENTED_BY_ANCHOR = "represented_by_anchor"
MODIFIER_OF_ANCHOR = "modifier_of_anchor"
CONSTRAINT_ON_ANCHOR = "constraint_on_anchor"
SUCCESS_CONDITION_OF_ANCHOR = "success_condition_of_anchor"
NON_OBLIGATIONAL_CONTEXT = "non_obligational_context"
OMITTED_OBLIGATION = "omitted"

REGION_DISPOSITIONS: tuple[str, ...] = (
    REPRESENTED_BY_ANCHOR, MODIFIER_OF_ANCHOR, CONSTRAINT_ON_ANCHOR,
    SUCCESS_CONDITION_OF_ANCHOR, NON_OBLIGATIONAL_CONTEXT, OMITTED_OBLIGATION,
)

#: Dispositions that claim some anchor carries this region's meaning.
_ANCHOR_BEARING_DISPOSITIONS = frozenset({
    REPRESENTED_BY_ANCHOR, MODIFIER_OF_ANCHOR, CONSTRAINT_ON_ANCHOR,
    SUCCESS_CONDITION_OF_ANCHOR,
})

# ---------------------------------------------------------------------
# Stage 1D -- state atomicity inside one anchor
# ---------------------------------------------------------------------

#: How a candidate semantic unit inside a region relates to an anchor.
#: Closed, for the same reason the region vocabulary is closed.
INDEPENDENT_OUTCOME = "independent_outcome"
PREREQUISITE_STATE = "prerequisite_state"
EVALUATION_CRITERION = "evaluation_criterion"
CONSTRAINT_UNIT = "constraint_unit"
SUCCESS_CONDITION_UNIT = "success_condition"
RATIONALE_UNIT = "rationale"
MODIFIER_UNIT = "modifier"
CONTEXT_UNIT = "context"

STATE_RELATIONSHIPS: tuple[str, ...] = (
    INDEPENDENT_OUTCOME, PREREQUISITE_STATE, EVALUATION_CRITERION,
    CONSTRAINT_UNIT, SUCCESS_CONDITION_UNIT, RATIONALE_UNIT, MODIFIER_UNIT,
    CONTEXT_UNIT,
)

#: Relationships that name a SEPARATELY TRACKABLE mission state. Two of
#: these inside one anchor is intra-anchor fusion: one anchor exposes one
#: satisfaction state, so the second meaning has nowhere to live.
#:
#: The test is statefulness, never the type label. Live Probe #3 fused
#: "Use sufficient public evidence" with the threat decision and this set
#: could not see it, because a constraint was assumed to be a property of
#: whatever it sat beside. That assumption is false: a recommendation can
#: exist while the evidence behind it remains insufficient, a purchase can
#: complete while a budget constraint is breached, and an action can
#: succeed while a privacy constraint fails. Each of those is a DIFFERENT
#: truthful status for two units, which is the whole definition.
#:
#: What genuinely cannot hold its own status is a unit whose truth is
#: already part of another unit's completion: the verification that
#: DEFINES a deliverable being done, the rationale that DEFINES an answer
#: being complete, a modifier, or plain context. Those may share an
#: anchor -- which is why "save AND verify report.md" and "which option
#: is best AND why" stay whole.
_SEPARATELY_STATEFUL = frozenset({
    INDEPENDENT_OUTCOME, PREREQUISITE_STATE, EVALUATION_CRITERION,
    CONSTRAINT_UNIT,
})

#: Units whose truth is a property of the state they accompany.
_SHARES_A_STATE = frozenset({
    SUCCESS_CONDITION_UNIT, RATIONALE_UNIT, MODIFIER_UNIT, CONTEXT_UNIT,
})

#: Prepositions that introduce the criteria an evaluation is made ON.
#: Structure, not vocabulary: no domain word appears here.
_CRITERIA_PREPOSITIONS = (
    "across", "on", "by", "against", "in terms of", "with respect to",
)

#: A bare interrogative trailing an outcome is the RATIONALE the founder
#: asked for with it, not another item in a list. Interrogative form, not
#: domain vocabulary.
_RATIONALE_TOKENS = frozenset({"why", "how", "when", "where", "who", "what"})


def _state_candidates_in(region: str) -> tuple[str, ...]:
    """Candidate state-bearing units inside one source region.

    Probe #2 proved the region scaffold too coarse: one region carried a
    selection AND five requested comparison dimensions, one anchor
    swallowed all six, and nothing downstream could see it because a
    single anchor has a single satisfaction state.

    These are CANDIDATES and nothing more. Exposing one costs nothing --
    the audit may call it context with a reason -- while failing to
    expose one is exactly how six Founder meanings became one opaque
    obligation. Over-exposure is therefore the safe direction, and no
    canonical requirement is created here.
    """
    text = " ".join((region or "").split()).strip()
    if not text:
        return ()
    parts = [part.strip(" ,;") for part in text.split(",") if part.strip(" ,;")]
    if len(parts) < 2 or sum(
        1 for part in parts if len(part.split()) >= _MIN_REGION_WORDS
    ) < 2:
        return (text,)

    # The head often carries an evaluation and the first criterion at
    # once ("Compare the top 3 across pricing/free access"). Splitting on
    # the criteria preposition separates WHAT is evaluated from the FIRST
    # THING it is evaluated on; the remaining commas already separate the
    # rest.
    head = parts[0]
    lowered = head.casefold()
    for preposition in _CRITERIA_PREPOSITIONS:
        marker = f" {preposition} "
        position = lowered.find(marker)
        if position == -1:
            continue
        subject = head[:position].strip(" ,;")
        criterion = head[position + len(marker):].strip(" ,;")
        if (len(subject.split()) >= _MIN_REGION_WORDS
                and len(criterion.split()) >= 1):
            parts = [subject, criterion, *parts[1:]]
        break

    # Inside an established list, a trailing "x and y" is the last two
    # items of that list. Scoped to list context on purpose: with no comma
    # there is no list, so "Save and verify report.md" never reaches this
    # branch at all. And a bare interrogative is a RATIONALE, not a list
    # item -- "...the closest competitive threat and why" is one requested
    # outcome, and splitting it is the mechanical fragmentation this
    # scaffold exists to avoid.
    widened: list[str] = []
    for part in parts:
        halves = [half.strip(" ,;")
                  for half in re.split(r"\s+and\s+", part) if half.strip(" ,;")]
        if len(halves) > 1 and not any(
            half.casefold().rstrip(".?!") in _RATIONALE_TOKENS
            for half in halves
        ):
            widened.extend(halves)
        else:
            widened.append(part)
    return tuple(
        # A list item inherits the conjunction that introduced it.
        re.sub(r"^and\s+", "", item).strip(" ,;") or item
        for item in widened
    )


def _source_state_candidates(objective: str) -> tuple[dict[str, Any], ...]:
    """Every candidate state unit, numbered, with its region."""
    candidates: list[dict[str, Any]] = []
    for region_index, region in enumerate(
        _source_coverage_regions(objective), start=1,
    ):
        for text in _state_candidates_in(region):
            candidates.append({
                "candidate_index": len(candidates) + 1,
                "region_index": region_index,
                "text": text,
            })
    return tuple(candidates)


def _coordinated_regions(sentence: str) -> tuple[str, ...]:
    """Candidate regions inside one sentence."""
    parts = [
        part.strip(" ,;")
        for part in re.split(r",?\s+and then\s+|,?\s+and\s+|;\s*", sentence)
        if part.strip(" ,;")
    ]
    if len(parts) < 2:
        return (sentence,)
    if any(len(part.split()) < _MIN_REGION_WORDS for part in parts):
        # One side is a bare verb or a dangling "why": one cohesive
        # statement, not two coordinated obligations.
        return (sentence,)
    return tuple(parts)


def _source_coverage_regions(objective: str) -> tuple[str, ...]:
    """Deterministic candidate regions of raw Founder language.

    Stage 1B polices a truthful anchor set correctly. It could not see an
    anchor set that quietly covered two obligations with one anchor,
    because its only source check was sentence-scale and any anchor inside
    the sentence satisfied it.

    This is the smallest scaffold that makes such a phrase VISIBLE. It
    never decides a region is a requirement -- the semantic layer does --
    but every region it names must afterwards be accounted for explicitly,
    so meaning cannot vanish in silence.
    """
    regions: list[str] = []
    for sentence in _founder_source_regions(objective):
        regions.extend(_coordinated_regions(sentence))
    return tuple(regions)


def _obligation_audit_issues(
    objective: str,
    regions: Sequence[str],
    anchors: Sequence[Mapping[str, Any]],
    audit: Any,
    candidates: Sequence[Mapping[str, Any]] = (),
) -> list[str]:
    """Whether an independent obligation audit is inspectable at all.

    An unusable audit is refused rather than read generously: the point of
    this boundary is that silence must not become consent.
    """
    if not isinstance(audit, dict):
        return ["the obligation audit was not a JSON object"]

    issues: list[str] = []
    for name in ("regions", "anchors", "omissions", "collapses", "invented"):
        if not isinstance(audit.get(name), list):
            issues.append(f"the obligation audit field {name!r} is not a list")
    if issues:
        return issues

    anchor_ids = {
        str(anchor.get("anchor_id", "") or "").strip() for anchor in anchors
    }
    anchor_ids.discard("")
    if not anchor_ids:
        issues.append("no Founder obligation anchor was proposed")

    for anchor in anchors:
        anchor_id = str(anchor.get("anchor_id", "") or "").strip()
        quote = str(anchor.get("source_quote", "") or "")
        if not _grounded_in(objective, quote):
            issues.append(
                f"anchor {anchor_id or '?'!r} does not quote Founder language"
            )
        if not str(anchor.get("meaning", "") or "").strip():
            issues.append(f"anchor {anchor_id or '?'!r} states no meaning")

    seen_regions: list[int] = []
    for position, row in enumerate(audit["regions"], start=1):
        if not isinstance(row, dict):
            issues.append(f"region disposition {position} is not an object")
            continue
        index = row.get("region_index")
        if not isinstance(index, int) or not 1 <= index <= len(regions):
            issues.append(
                f"region disposition {position} names no valid region_index"
            )
            continue
        seen_regions.append(index)
        disposition = str(row.get("disposition", "") or "").strip()
        if disposition not in REGION_DISPOSITIONS:
            issues.append(
                f"region {index} has an unusable disposition {disposition!r}"
            )
        elif disposition in _ANCHOR_BEARING_DISPOSITIONS:
            named = str(row.get("anchor_id", "") or "").strip()
            if named not in anchor_ids:
                issues.append(f"region {index} claims unknown anchor {named!r}")
        elif disposition == NON_OBLIGATIONAL_CONTEXT and not str(
            row.get("reason", "") or ""
        ).strip():
            issues.append(
                f"region {index} was called non-obligational with no reason"
            )

    duplicated = {i for i in seen_regions if seen_regions.count(i) > 1}
    if duplicated:
        issues.append(
            "more than one disposition for region(s) "
            + ", ".join(str(index) for index in sorted(duplicated))
        )

    for position, row in enumerate(audit["anchors"], start=1):
        if not isinstance(row, dict):
            issues.append(f"anchor verdict {position} is not an object")
            continue
        if str(row.get("anchor_id", "") or "").strip() not in anchor_ids:
            issues.append(f"anchor verdict {position} names an unknown anchor")
        if not isinstance(row.get("entailed"), bool):
            issues.append(f"anchor verdict {position} does not settle entailment")

    # Stage 1D. A region-level answer is too coarse: Probe #2's auditor
    # said "region 2 -> anchor_2, represented" and six Founder meanings
    # went into one satisfaction state. Each candidate state unit must
    # now be placed individually.
    if candidates:
        if not isinstance(audit.get("state_candidates"), list):
            issues.append(
                "the obligation audit field 'state_candidates' is not a list"
            )
            return issues
        seen_candidates: list[int] = []
        for position, row in enumerate(audit["state_candidates"], start=1):
            if not isinstance(row, dict):
                issues.append(f"state candidate {position} is not an object")
                continue
            index = row.get("candidate_index")
            if not isinstance(index, int) or not 1 <= index <= len(candidates):
                issues.append(
                    f"state candidate {position} names no valid candidate_index"
                )
                continue
            seen_candidates.append(index)
            relationship = str(row.get("relationship", "") or "").strip()
            if relationship not in STATE_RELATIONSHIPS:
                issues.append(
                    f"state candidate {index} has an unusable relationship "
                    f"{relationship!r}"
                )
                continue
            if relationship == CONTEXT_UNIT:
                if not str(row.get("reason", "") or "").strip():
                    issues.append(
                        f"state candidate {index} was called context with no "
                        "reason"
                    )
                continue
            named = str(row.get("anchor_id", "") or "").strip()
            if named not in anchor_ids:
                issues.append(
                    f"state candidate {index} claims unknown anchor {named!r}"
                )
        missing = sorted(
            set(range(1, len(candidates) + 1)) - set(seen_candidates)
        )
        if missing:
            issues.append(
                "the audit never placed Founder state candidate(s) "
                + ", ".join(str(index) for index in missing)
            )
        duplicated = {
            index for index in seen_candidates if seen_candidates.count(index) > 1
        }
        if duplicated:
            issues.append(
                "more than one placement for state candidate(s) "
                + ", ".join(str(index) for index in sorted(duplicated))
            )
    return issues


def _intra_anchor_fusion(
    candidates: Sequence[Mapping[str, Any]],
    anchors: Sequence[Mapping[str, Any]],
    audit: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Anchors asked to hold more than one separately satisfiable state.

    One anchor exposes ONE satisfaction state. If the audit's own
    placements put two independently stateful Founder meanings inside it,
    the second has nowhere to live -- which is exactly how, live, a
    top-three SELECTION and five requested COMPARISONS became a single
    obligation that could only ever be wholly done or wholly not.

    Derived from the audit's structured placements, never from its
    opinion: the same discipline by which `_coverage_decision` reads two
    anchors on one requirement as an improper merge, applied one level
    up. A success condition, rationale, constraint or context is not
    separately satisfiable and may share an anchor, so "save AND verify"
    and "which is best AND why" remain whole.
    """
    by_text = {
        int(row["candidate_index"]): row.get("text", "")
        for row in candidates if isinstance(row, Mapping)
        and isinstance(row.get("candidate_index"), int)
    }
    held: dict[str, list[dict[str, Any]]] = {}
    for row in audit.get("state_candidates", ()) or ():
        if not isinstance(row, Mapping):
            continue
        relationship = str(row.get("relationship", "") or "").strip()
        if relationship not in _SEPARATELY_STATEFUL:
            continue
        anchor_id = str(row.get("anchor_id", "") or "").strip()
        index = row.get("candidate_index")
        if not anchor_id or not isinstance(index, int):
            continue
        held.setdefault(anchor_id, []).append({
            "candidate_index": index,
            "text": by_text.get(index, ""),
            "relationship": relationship,
        })

    fused: list[dict[str, Any]] = []
    for anchor in anchors:
        anchor_id = str(anchor.get("anchor_id", "") or "").strip()
        states = held.get(anchor_id, [])
        if len(states) <= 1:
            # The auditor may SAY this anchor holds several states. Its own
            # placements say otherwise, and a declaration with no structured
            # support is the mirror image of `valid=true`: an opinion, not
            # evidence. It is recorded, and it does not decide.
            continue
        fused.append({
            "anchor_id": anchor_id,
            "source_quote": anchor.get("source_quote", ""),
            "meaning": anchor.get("meaning", ""),
            "states": states,
            "auditor_declared_multiple": audit_declares_multiple(
                audit, anchor_id,
            ),
            "reason": (
                "one anchor exposes one satisfaction state but was asked "
                "to hold several independently trackable Founder meanings"
            ),
        })
    return fused


def audit_declares_multiple(audit: Mapping[str, Any], anchor_id: str) -> bool:
    """The auditor's own claim that an anchor holds several states.

    Supporting evidence only. It is recorded beside a structurally proven
    fusion and can neither create one nor excuse one: placements showing
    two trackable states are fusion even when this says ``false``, and
    this saying ``true`` over a single trackable state is not.
    """
    for row in audit.get("anchors", ()) or ():
        if not isinstance(row, Mapping):
            continue
        if str(row.get("anchor_id", "") or "").strip() != anchor_id:
            continue
        if row.get("contains_multiple_states") is True:
            return True
        if row.get("independently_satisfiable_together") is False:
            return True
    return False


def _obligation_trust_decision(
    regions: Sequence[str],
    anchors: Sequence[Mapping[str, Any]],
    audit: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Decide deterministically whether the Founder obligation set may be
    trusted as the root the rest of Stage 1 stands on.

    The auditor's own ``valid`` value is ignored, exactly as
    ``_coverage_decision`` ignores the reviewer's. A model may report
    evidence; it may not award itself the verdict.

    What this proves: every deterministic source region carries an explicit
    disposition, every anchor quotes real Founder language and carries an
    affirmative entailment verdict, and no reported omission, collapse or
    invention is outstanding.

    What it does NOT prove, and does not claim: that a region called
    ``non_obligational_context`` truly is one. That judgement is semantic.
    This layer forces it to be stated, attributed and recorded rather than
    made in silence.
    """
    dispositions = {
        row.get("region_index"): row
        for row in audit.get("regions", ()) or ()
        if isinstance(row, dict)
    }
    entailment = {
        str(row.get("anchor_id", "") or "").strip(): row
        for row in audit.get("anchors", ()) or ()
        if isinstance(row, dict)
    }

    issues: list[str] = []
    unexplained: list[dict[str, Any]] = []
    for index, region in enumerate(regions, start=1):
        row = dispositions.get(index)
        if row is None:
            unexplained.append({"region_index": index, "region": region})
            issues.append(
                f"Founder source region {index} was never accounted for: "
                f"{region!r}"
            )
            continue
        if str(row.get("disposition", "") or "") == OMITTED_OBLIGATION:
            unexplained.append({
                "region_index": index,
                "region": region,
                "reason": str(row.get("reason", "") or ""),
            })
            issues.append(
                f"Founder source region {index} was reported omitted: {region!r}"
            )

    unentailed: list[dict[str, Any]] = []
    for anchor in anchors:
        anchor_id = str(anchor.get("anchor_id", "") or "").strip()
        verdict = entailment.get(anchor_id)
        if verdict is None:
            unentailed.append({
                "anchor_id": anchor_id,
                "source_quote": anchor.get("source_quote", ""),
                "meaning": anchor.get("meaning", ""),
                "reason": "no independent entailment verdict was returned",
            })
            issues.append(f"anchor {anchor_id!r} carries no entailment verdict")
        elif verdict.get("entailed") is not True:
            unentailed.append({
                "anchor_id": anchor_id,
                "source_quote": anchor.get("source_quote", ""),
                "meaning": anchor.get("meaning", ""),
                "reason": str(verdict.get("reason", "") or ""),
            })
            issues.append(
                f"anchor {anchor_id!r} asserts a meaning its own Founder quote "
                "does not entail"
            )

    omissions = [dict(r) for r in audit.get("omissions", ()) or ()
                 if isinstance(r, dict)]
    collapses = [dict(r) for r in audit.get("collapses", ()) or ()
                 if isinstance(r, dict)]
    invented = [dict(r) for r in audit.get("invented", ()) or ()
                if isinstance(r, dict)]
    for row in omissions:
        issues.append(
            "the independent audit found Founder meaning with no anchor: "
            + str(row.get("meaning", "") or row.get("source_quote", ""))
        )
    for row in invented:
        issues.append(
            "the independent audit found an anchor the Founder did not ask "
            "for: " + str(row.get("reason", "") or row.get("anchor_id", ""))
        )

    # Fusion is decided by the placements, not by the report. A collapse
    # the auditor names is recorded and, where the placements corroborate
    # it, its own words are carried into the correction; a collapse it
    # names over a single trackable state is an opinion and does not
    # refuse on its own.
    fused = _intra_anchor_fusion(candidates, anchors, audit)
    reported = {
        str(row.get("anchor_id", "") or "").strip(): str(row.get("reason", "") or "")
        for row in collapses
    }
    for row in fused:
        held = ", ".join(
            f"{state['text']!r}" for state in row.get("states", ())
        ) or "several Founder meanings"
        row["auditor_reason"] = reported.get(row["anchor_id"], "")
        issues.append(
            f"anchor {row['anchor_id']!r} fuses independently trackable "
            f"Founder states: {held}"
        )

    return {
        "trusted": not issues,
        "issues": issues,
        "intra_anchor_fusion": fused,
        "state_candidates": [dict(row) for row in candidates],
        "state_placements": [
            dict(row) for row in audit.get("state_candidates", ()) or ()
            if isinstance(row, Mapping)
        ],
        "unexplained_regions": unexplained,
        "unentailed_anchors": unentailed,
        "omissions": omissions,
        "collapses": collapses,
        "invented": invented,
        "regions": list(regions),
        "region_dispositions": [
            dict(r) for r in audit.get("regions", ()) or () if isinstance(r, dict)
        ],
        "anchor_entailment": [
            dict(r) for r in audit.get("anchors", ()) or () if isinstance(r, dict)
        ],
    }


def _coverage_decision(
    offered: list[dict[str, Any]], audit: Mapping[str, Any],
) -> dict[str, Any]:
    """Deterministically decide whether the obligation mapping is lossless.

    The model's global ``valid`` value is intentionally ignored. One
    ``SemanticRequirement`` exposes one mission state, so two distinct
    obligation anchors mapped to it are an improper merge. One anchor may
    map to several requirements because structure may become more precise.
    """
    anchors = [dict(row) for row in audit.get("anchors", ())]
    coverage = [dict(row) for row in audit.get("coverage", ())]
    by_id = {
        str(row.get("anchor_id", "") or "").strip(): row for row in anchors
    }
    requirement_to_anchors: dict[int, list[dict[str, Any]]] = {}
    unmapped: list[dict[str, Any]] = []
    preserved: list[dict[str, Any]] = []

    for mapping in coverage:
        anchor_id = str(mapping.get("anchor_id", "") or "").strip()
        anchor = by_id[anchor_id]
        indices = list(mapping.get("requirement_indices") or ())
        if not indices or not mapping.get("independently_trackable", False):
            unmapped.append({
                **anchor,
                "reason": (
                    "no canonical requirement mapping" if not indices
                    else "the mapping does not expose an independent state"
                ),
            })
            continue
        preserved.append({
            "anchor_id": anchor_id,
            "source_quote": anchor.get("source_quote", ""),
            "meaning": anchor.get("meaning", ""),
            "requirement_indices": indices,
        })
        for index in indices:
            requirement_to_anchors.setdefault(index, []).append(anchor)

    improper_merges: list[dict[str, Any]] = []
    for index, mapped in sorted(requirement_to_anchors.items()):
        unique = {
            str(anchor.get("anchor_id", "") or ""): anchor for anchor in mapped
        }
        if len(unique) > 1:
            improper_merges.append({
                "requirement_index": index,
                "obligations": [dict(anchor) for anchor in unique.values()],
                "reason": (
                    "one canonical requirement has one mission state but was "
                    "asked to represent multiple independently stateful Founder "
                    "obligations"
                ),
            })

    invented_by_index: dict[int, dict[str, Any]] = {}
    for row in audit.get("invented", ()) or ():
        invented_by_index[int(row["requirement_index"])] = dict(row)
    for index in range(1, len(offered) + 1):
        if index not in requirement_to_anchors:
            invented_by_index.setdefault(index, {
                "requirement_index": index,
                "reason": "no Founder obligation anchor maps to this requirement",
            })

    invented = list(invented_by_index.values())
    valid = not unmapped and not improper_merges and not invented
    return {
        "valid": valid,
        "independently_verifiable": valid,
        "anchors": anchors,
        "coverage": coverage,
        "preserved": preserved,
        "merged": improper_merges,
        "lost": unmapped,
        "invented": invented,
    }


def _semantic_violation_messages(audit: Mapping[str, Any]) -> list[str]:
    """Grounded correction instructions from a structured verdict."""
    issues: list[str] = []
    for row in audit.get("merged", ()) or ():
        if not isinstance(row, Mapping):
            continue
        parts = [
            (
                str(item.get("source_quote", "") or "")
                + " => "
                + str(item.get("meaning", "") or "")
            ).strip(" =>")
            for item in row.get("obligations", ()) or ()
            if isinstance(item, Mapping)
        ]
        issues.append(
            "independent Founder obligations were merged in requirement "
            f"{row.get('requirement_index')}: " + " | ".join(parts)
        )
    for row in audit.get("lost", ()) or ():
        if isinstance(row, Mapping):
            issues.append(
                "a Founder obligation was lost: "
                + str(row.get("source_quote", "") or row.get("meaning", ""))
            )
    for row in audit.get("invented", ()) or ():
        if isinstance(row, Mapping):
            issues.append(
                "an unstated obligation was invented in requirement "
                f"{row.get('requirement_index')}: {row.get('reason', '')}"
            )
    if not audit.get("independently_verifiable", False):
        issues.append(
            "the proposed requirements cannot all change state and be verified "
            "independently"
        )
    return issues


#: How a field's value came to be established.
STATED = "stated"
REASONED = "reasoned"


@dataclass(frozen=True)
class FieldEvidence:
    """One field the founder supplied, and how it came to be known.

    Provenance rather than decoration. A canonical Intent assembled over
    several turns has to stay explainable: which utterance supplied this,
    was it read structurally or reasoned about, and did it replace
    something said earlier. Without that, a corrected value and an
    original one are indistinguishable in the record.
    """

    value: str
    #: The founder's own words this was read out of.
    evidence: str
    source: str
    #: The value this superseded, when the founder changed their mind.
    replaced: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "value": self.value,
            "evidence": self.evidence,
            "source": self.source,
            "replaced": self.replaced,
        }


@dataclass(frozen=True)
class Understanding:
    """What one utterance told us, against what we were trying to learn.

    Deliberately allows **zero or many** fields from a single answer. The
    assumption that an answer resolves exactly the field that was asked
    is what made *"actually call it Finance and put it in Documents"*
    impossible to express.
    """

    fields: dict[str, FieldEvidence] = field(default_factory=dict)
    #: True when the utterance carries meaning this layer could not pin
    #: down -- two candidate places, a referent with nothing to refer to.
    #: Uncertainty is a reason to ASK, never a reason to pick.
    uncertain: bool = False
    reason: str = ""

    @property
    def resolved(self) -> dict[str, str]:
        return {name: found.value for name, found in self.fields.items()}


#: Connectives with which a founder strings requirements together. Their
#: presence means the sentence carries more than one thing to do, whoever
#: ends up doing it.
_SEQUENCING_CONNECTIVES: tuple[str, ...] = (
    " then ", " and then ", " after that ", " followed by ",
)


#: A creation command that supplies a name and a supported place but omits
#: what kind of object is to be created.  This is deliberately a structural
#: shape, not a list of holdout sentences.  The location is the anchor: plain
#: ``create a report`` remains ordinary generic prose, while ``create Budget
#: on Desktop`` has supplied two fields and demonstrably omitted a third.
_NOUNLESS_CREATE = re.compile(
    r"\b(?:create|make)\s+"
    r"(?P<name>[\w][\w ._'-]*?)\s+"
    r"(?:on|in)\s+(?:my\s+|the\s+)?"
    r"(?P<location>desktop|documents|downloads|d(?:[_ ]+)drive)\b",
    re.IGNORECASE,
)

#: Words that already state what is being created.  Their exact action may
#: still belong to a typed parser or to Planning, but it is not the
#: ``creation_kind`` ambiguity handled here.  Exact tokens avoid treating a
#: proper name such as ``ProjectFolder`` as an object declaration.
_EXPLICIT_CREATE_KINDS = frozenset({
    "folder", "directory", "file", "document", "project", "application",
    "app", "report",
})
_CREATE_REFERENTS = frozenset({"it", "this", "that", "one", "them", "something"})
_CREATION_KIND = "creation_kind"
_CREATION_KIND_OPTIONS = ("folder", "file")


#: How much a sentence may say beyond a parser's trigger phrase and still
#: be that parser's sentence with a field missing.
#:
#: A size gate, not a semantic judgement, and its failure mode is the
#: safe one: a sentence this declines travels to the Planner, which holds
#: the whole capability catalogue and owns decomposition. "create a
#: folder on the Desktop" says three words beyond its trigger; "search
#: for new 2026 action rpg games and give me demo version download links"
#: says eleven, and is not a file search.
_TRIGGER_SLACK_WORDS = 4


def _may_claim(text: str, trigger: str, result: Any, supplied: Any) -> bool:
    """May this parser own this sentence?

    ## The defect

    Parsers are selected by substring: `if pattern in text.lower()`. A
    founder asked

        search for new 2026 action rpg games and give me demo version
        download links

    and the FILESYSTEM search parser claimed it, because "search for"
    appears in it. Unable to read the sentence, it asked *"What should I
    search for?"* -- about a sentence that says exactly what to search
    for, and means the web rather than their files.

    Two things went wrong at once: a request was routed to the wrong
    capability family, and having been routed there it asked for
    something the founder had already given.

    ## The rule

    A parser may claim a sentence when it can READ it, or when the
    sentence is essentially its trigger with a field missing -- which is
    the case clarification exists for. It may not claim a sentence it
    cannot read that plainly says much more than its trigger phrase.

    Mid-conversation is always claimed: once a founder is answering this
    parser's questions, the sentence being re-parsed is their original
    one and the answers are arriving separately.
    """
    if not getattr(result, "needs_clarification", False):
        return True

    asked_again = getattr(getattr(result, "clarification", None), "key", "")
    # A key present with an EMPTY value is not an answer. A founder who
    # pressed enter on a blank line has said nothing, and the question
    # must be asked again -- treating that as "already answered" made a
    # folder request fall through to the project parser and be asked
    # about a project it never mentioned.
    if supplied and asked_again and str(supplied.get(asked_again, "") or "").strip():
        # The founder has ALREADY answered this exact question and the
        # parser still cannot read the sentence. Asking a third time is
        # the loop a founder can only escape by giving up -- and one did,
        # by typing "stop", after answering the same question twice.
        #
        # Declining is the honest move: this parser has had its answer
        # and cannot use it, so the request travels on to the layer that
        # owns decomposition instead of going round again.
        return False
    if supplied:
        return True
    if getattr(result, "resolved", None):
        # The parser read at least one field and is explicitly asking for
        # another.  This is a partial understanding, not a broad lexical
        # match that should fall through to generic planning.
        return True
    beyond = len(text.split()) - len(trigger.split())
    return beyond <= _TRIGGER_SLACK_WORDS


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


#: The same AI Capability the Planner and `brain/advisory.py` ask for,
#: named explicitly so a reader can see it is deliberately identical.
#: One ladder, one Broker, one decision trail (VISION_V2 §3.3).
REASONING_CAPABILITY = "reasoning"

#: What the reasoner is allowed to answer. Anything else is treated as no
#: answer at all and the structural default stands -- a provider inventing
#: a seventh role must not be able to invent behaviour with it.
_ROLE_BY_WORD = {
    "answer": UtteranceRole.ANSWER_TO_CLARIFICATION,
    "redirect": UtteranceRole.MODIFY_OR_REDIRECT,
    "cancel": UtteranceRole.CANCEL_OR_STOP,
    "question": UtteranceRole.FOLLOW_UP,
}


#: `Reasoning.Transform`, named the way every other intent names a
#: capability -- unqualified, since `find_option` normalises. The Planner
#: still confirms it is registered before planning anything.
#: A question about this system, with this system's own facts attached.
#:
#: The rules matter more than the framing. A provider that answers from
#: memory about "Kalpavriksha" is answering about a product, not about
#: this installation on this machine at this moment -- and the two differ
#: in exactly the way a founder would care about: a capability that is
#: registered but not executable is not something to offer them.
_GROUNDED_QUESTION = """Answer the founder's question about this system.

These are its CURRENT facts, read from its own registries a moment ago:

{facts}

The founder asks: {question}

Answer only from the facts above. If they do not settle the question, say
what is missing rather than filling the gap -- do not rely on anything you
remember about a system with this name, because these facts are about this
installation right now. Do not offer anything the facts do not show as
usable. Speak plainly to the founder; do not quote internal identifiers at
them unless one is genuinely the answer."""

#: How a question's own requirement is described.
#:
#: Named rather than spelled out twice, because something has to be able
#: to recognise it: a mission whose whole purpose was to ANSWER a
#: question is not work the founder commissioned, and "did the last
#: mission satisfy what I asked?" means the last thing they asked FOR,
#: not the last thing they asked ABOUT.
QUESTION_REQUIREMENT = "answer the founder's question:"

_TRANSFORM_CAPABILITY = "transform"
#: The output field it publishes, and the one an answer is read from.
_TRANSFORM_ANSWER_FIELD = "text"


class IntentLayer:
    """Parses raw input into structured Intent.

    Deterministic parsing first, for everything it can settle. For
    ambiguous input that could map to multiple valid intents, it asks the
    founder rather than guessing.

    ## What this layer reasons about, and what it never does

    `reasoner` is the Brain's Model Router door (`VISION_V2` §3.3 — *"the
    Brain's single door to reasoning"*, which ADR-0024 Decision 7 states
    normatively is not the Planner's alone). It is optional: omitted, this
    layer still resolves everything structure can settle, and asks rather
    than guesses for the rest.

    It is consulted for exactly two narrow judgements, both of them about
    MEANING and neither about what to do:

    * `decide_role()` — what an utterance is DOING, when structure was
      falling back to a default rather than reading a signal.
    * `understand()` — which of the fields we are gathering an utterance
      supplies, when the capability's own vocabulary and sentence shape
      could not settle it.

    Both are structured extractions with validated output. Neither is
    asked what to do, which capability to use, or which provider to ask —
    those belong to the Planner and the Broker respectively.

    Never on the ordinary path. A founder answering "Research", or
    naming a place the capability publishes, pays no latency and no
    tokens for a harder case existing elsewhere.

    **This docstring said "one decision, and not for parsing or
    clarification" until `understand()` was added.** It is corrected here
    rather than left to mislead the next reader: a comment describing
    behaviour the code no longer has is worse than no comment.
    """

    def __init__(
        self,
        reasoner: Any = None,
        vocabularies: Mapping[str, Sequence[str]] | None = None,
        grounding: Any = None,
    ) -> None:
        #: Injected, never constructed here: a second provider path is
        #: exactly what ADR-0024 Decision 7 forbids. The composition root
        #: hands in the SAME `TieredPromptRunner` the Planner uses.
        self._reasoner = reasoner
        #: Field -> the canonical values that field can actually take, for
        #: the fields whose vocabulary is closed. `{"location":
        #: ("d_drive", "desktop", "documents", "downloads")}`.
        #:
        #: Injected for the same reason the reasoner is. The capability
        #: owns this list -- the composition root widens it with the
        #: founder's D: drive at runtime -- and a second copy here would
        #: be a copy that drifts. What the Intent Layer does with it is
        #: its own business: mapping the founder's meaning onto the values
        #: the machine can act on is precisely this layer's job, and it is
        #: why `Filesystem` never has to understand "on my desktop
        #: please".
        self._vocabularies: dict[str, tuple[str, ...]] = {
            name: tuple(str(value) for value in values)
            for name, values in (vocabularies or {}).items()
        }
        #: A callable returning CURRENT authoritative facts about this
        #: system: what it can do, which providers are usable, what the
        #: last mission did. Injected, never gathered here -- the Brain
        #: may not read the environment, and these facts belong to Shared
        #: Infrastructure.
        #:
        #: Why it exists. A founder asking "what can you do right now?"
        #: was previously answered by a provider reasoning from whatever
        #: it remembered about a product called Kalpavriksha, which is
        #: not a source of truth about THIS machine at THIS moment. A
        #: capability that is known but not executable is not something
        #: to promise, and only the registry knows which is which.
        self._grounding = grounding
        # Patterns are tried in order; first match wins
        # More specific patterns first
        self._patterns: list[tuple[str, type]] = [
            # Folder patterns must all precede the generic ("create",
            # CreateProjectIntent) catch-all below -- first match wins.
            # Only "create a folder called" was listed, so "Create a
            # folder" (no name yet, which is exactly the case that needs
            # clarifying) fell through to the PROJECT parser and asked
            # "What should the project be called?" about a folder.
            # The parser owns the structural create/make grammar.  The
            # registry only needs the noun that makes the parser relevant;
            # a parser-level ``recognizes`` guard below prevents unrelated
            # folder sentences from being claimed.  Keeping six exact
            # command fragments here previously made valid adjective order
            # ("a new empty folder") fall off the typed path.
            ("folder", CreateFolderIntent),
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

    def decide_role(
        self,
        text: str,
        *,
        awaiting_answer: bool = False,
        options: Sequence[str] = (),
        question: str = "",
        objective: str = "",
        task_id: str = "",
        objective_id: str | None = None,
        has_referent: bool = False,
    ) -> UtteranceRole:
        """What role the founder's utterance plays.

        Structure decides first and decides most things, at no cost. The
        reasoner is asked only when structure reports it was falling back
        to a default rather than reading a signal — a longer statement
        arriving while a question is open, which is the one shape where an
        odd multi-word answer and a change of subject are genuinely
        indistinguishable by shape.

        Never raises. A dead ladder, a refused request, or an answer
        outside the four permitted words all leave the structural default
        standing, which is the behaviour that shipped before this door
        existed. Reasoning here can only *improve* on structure; it can
        never leave the founder worse off than no reasoning at all.
        """
        role, confident = structural_role(
            text, awaiting_answer=awaiting_answer, options=options,
            has_referent=has_referent,
        )
        if confident or self._reasoner is None:
            return role
        reasoned = self._reasoned_role(
            text, question=question, objective=objective,
            task_id=task_id, objective_id=objective_id,
        )
        return reasoned if reasoned is not None else role

    def _reasoned_role(
        self,
        text: str,
        *,
        question: str,
        objective: str,
        task_id: str,
        objective_id: str | None,
    ) -> UtteranceRole | None:
        """Ask the Brain's one reasoning door. `None` means "no usable
        answer" — never an exception, and never a guess."""
        from master_agent.ai_infrastructure.budgeted_request import (
            BudgetedSelectionRequest,
        )
        from master_agent.ai_infrastructure.workload import INTERACTIVE
        from master_agent.plugins.model_router import RoutingContext, SelectionRequest

        prompt = (
            "A founder is using an assistant. The assistant asked them a "
            "question and is waiting for the answer.\n\n"
            f"    The assistant is working on: {objective.strip()}\n"
            f"    The assistant asked: {question.strip()}\n"
            f"    The founder replied: {text.strip()}\n\n"
            "Decide what the founder's reply is DOING. Answer with exactly "
            "one of these four words and nothing else:\n\n"
            "answer    - it supplies what the question asked for, even if "
            "it is worded oddly\n"
            "redirect  - it asks for something different instead\n"
            "cancel    - it abandons the request without answering\n"
            "question  - it asks the assistant something back\n\n"
            "Reply with one word only. No punctuation, no explanation."
        )
        context = RoutingContext(
            is_online=True,
            # Deciding what a sentence is doing is a small judgement, not
            # a hard one. Asking for strong reasoning here would push a
            # cheap, latency-sensitive call up the ladder for no gain.
            requires_strong_reasoning=False,
            capability=REASONING_CAPABILITY,
            task_id=task_id,
            objective_id=objective_id,
            requester="brain_intent_role",
        )
        request = BudgetedSelectionRequest(
            **vars(SelectionRequest.from_context(context)),
            request_class=INTERACTIVE,
            prompt=prompt,
        )
        try:
            outcome = self._reasoner.run(prompt, request)
        except Exception:  # noqa: BLE001 -- a dead ladder is a default, not a crash
            return None
        if outcome is None or not getattr(outcome, "ok", False):
            return None
        answer = (getattr(outcome, "text", "") or "").strip().lower()
        # First permitted word wins, so "answer." or "answer - it supplies"
        # still resolve. An answer naming none of them returns None.
        for word in answer.replace(".", " ").replace(",", " ").split():
            if word in _ROLE_BY_WORD:
                return _ROLE_BY_WORD[word]
        return None


    # ---- understanding an utterance against what we need to learn ----

    def understand(
        self,
        utterance: str,
        *,
        gathering: Sequence[str],
        asked: str = "",
        known: Mapping[str, str] | None = None,
        objective: str = "",
        question: str = "",
    ) -> Understanding:
        """What this utterance tells us about the fields we still need.

        ## The defect this replaces

        A clarification answer used to become the field value directly:

            answers[question.key] = answer

        so the founder's words travelled, untouched, into a capability
        argument. Measured live, on the simplest interaction the product
        has:

            Somesh: Where should I create the Abhishek folder?
            Onkar:  on desktop
            -> unknown location 'on desktop'

        The founder had answered the question correctly. Nothing had
        *understood* the answer, because nothing was asked to -- the
        layer whose constitutional job is turning language into structure
        was copying a string.

        The repair is not a bigger phrase list. It is to treat an answer
        as what it is: **new natural-language evidence**, from which the
        Intent Layer updates its understanding of every field in play.

        ## Two stages, cheapest first

        **Stated.** For a field whose vocabulary is closed, the founder's
        words are matched against *the values the machine can actually
        act on* -- not against a table of English phrasings. "put it on
        the desktop please" mentions `desktop`; so does "Desktop"; so does
        "let's use my Desktop". None of those is enumerated anywhere,
        because what is enumerated is the capability's own vocabulary,
        which it has to publish regardless. Two candidates mentioned is
        ambiguity, and ambiguity is a question rather than a coin toss.

        For an open field -- a folder's name -- a short reply carrying no
        clause structure is the value, which is what "Research" has always
        been.

        **Reasoned.** When structure cannot settle it, the Brain's
        existing reasoning door interprets the utterance against the
        objective, the question asked, what is already known, and what
        remains. It returns a narrow structured extraction that is
        validated before it is believed. It may fill fields. It may not
        invent them.

        Neither stage guesses. An utterance this layer cannot pin down
        returns `uncertain`, and the caller asks.
        """
        text = (utterance or "").strip()
        wanted = tuple(dict.fromkeys([name for name in gathering if name]))
        if not text or not wanted:
            return Understanding()

        stated = self._stated_fields(text, wanted=wanted, asked=asked)
        if stated.uncertain:
            # Structure found genuine ambiguity -- two places named, say.
            # Reasoning cannot resolve what the founder has not decided.
            return stated

        outstanding = [name for name in wanted if name not in stated.fields]
        answered_the_question = bool(asked) and asked in stated.fields
        if not outstanding:
            return stated
        if answered_the_question and not _unaccounted_by(
            text, [field.value for field in stated.fields.values()]
        ):
            # Every word the founder used is already explained by the
            # fields structure settled or by grammar.  An outstanding
            # optional field (the parent folder, for example) is not a
            # reason to ask a provider whether the founder said something
            # they demonstrably did not say.  Parsing below will still ask
            # for any required field that remains missing.
            return stated
        if answered_the_question and _is_single_clause(text):
            # One clause, and it settled what was asked. A sentence that
            # says one thing cannot also be saying a second, so paying a
            # provider to confirm that is the unnecessary-AI cost this
            # ladder exists to avoid. "put it on my desktop please" ends
            # here; "call it Finance and put it in Documents" does not.
            return stated

        reasoned = self._reasoned_fields(
            text,
            wanted=tuple(outstanding),
            known={**dict(known or {}), **stated.resolved},
            objective=objective,
            question=question,
        )
        if reasoned is None:
            # No usable interpretation -- a dead ladder, a refusal, or
            # output that failed validation.
            if answered_the_question:
                # The question that was asked HAS been answered. Whatever
                # else the sentence may have carried is unread, and the
                # remaining fields get asked for in the ordinary way --
                # which is a worse conversation than understanding it in
                # one go, and a truthful one.
                return stated
            return Understanding(
                fields=dict(stated.fields),
                uncertain=True,
                reason="the answer could not be interpreted",
            )
        merged = dict(stated.fields)
        merged.update(reasoned.fields)

        # Does what we now believe explain what the founder SAID?
        #
        # The prompt asks a model not to pick the closest value when the
        # reply names something narrower. Asked "d drive in onkar
        # folder", the production model returned `d_drive` anyway -- and
        # because `d_drive` is a legitimate value, the vocabulary check
        # accepted it and a folder was created in the wrong place for the
        # second time.
        #
        # An instruction to a model is not a constraint. This is: every
        # word the founder used must be explained by a value we resolved
        # or by grammar, whoever resolved it. A leftover word is a fact
        # nobody has accounted for, and acting on a partial reading is
        # how the founder gets told "This did what you asked for" about
        # work that did not.
        leftover = _unaccounted_by(text, [f.value for f in merged.values()])
        if leftover:
            return Understanding(
                fields={}, uncertain=True,
                reason=f"{' '.join(sorted(leftover))} was not understood",
            )
        return Understanding(
            fields=merged, uncertain=reasoned.uncertain, reason=reasoned.reason
        )

    def _stated_fields(
        self, text: str, *, wanted: Sequence[str], asked: str
    ) -> Understanding:
        """What structure alone can settle, at no cost."""
        found: dict[str, FieldEvidence] = {}

        # The question that was asked is part of the meaning.
        #
        # "Desktop" answering *"What should the folder be called?"* is a
        # NAME. The identical word answering *"Where should I create
        # it?"* is a PLACE. A vocabulary scan that ran regardless would
        # read both out of one word and quietly file the founder's chosen
        # name as a location -- so a plain reply to an open-vocabulary
        # question settles that question and is not mined for anything
        # else.
        if (
            asked
            and asked in wanted
            and asked not in self._vocabularies
            and _is_bare_value(text)
        ):
            return Understanding(
                fields={asked: FieldEvidence(
                    value=text.strip(), evidence=text, source=STATED
                )}
            )

        # "call it X" -- the founder naming the thing, inside a longer
        # sentence that also says something else. Read structurally so
        # the commonest multi-field reply needs no provider at all.
        if asked and asked in wanted and asked not in self._vocabularies:
            named = _named_value(text)
            if named:
                found[asked] = FieldEvidence(
                    value=named, evidence=text, source=STATED
                )

        tokens = {word.strip(_VALUE_STRIP).lower() for word in text.split()}
        joined = " ".join(
            word.strip(_VALUE_STRIP).lower() for word in text.split()
        )

        for name in wanted:
            vocabulary = self._vocabularies.get(name)
            if not vocabulary:
                continue
            # Which of the values this capability actually accepts did the
            # founder mention? Multi-word values ("d drive" for `d_drive`)
            # are matched on the phrase, single words on the token, so a
            # folder called "Desktop Backup" cannot be read as a place by
            # accident when the place is not what was asked.
            mentioned = [
                value for value in vocabulary
                if (value.replace("_", " ") in joined
                    if "_" in value else value.lower() in tokens)
            ]
            if len(mentioned) == 1:
                # Everything settled in this pass, not just the
                # candidate. The name read a moment ago already accounts
                # for its own words, and checking the place against the
                # candidate alone made "call it X and put it in
                # Documents" look unexplained by X's own name.
                if _unaccounted_by(
                    text, [f.value for f in found.values()] + [mentioned[0]]
                ):
                    # The reply names something this match did not
                    # explain. Settling the field here would DISCARD it,
                    # which is exactly how a folder ended up on the wrong
                    # drive with the founder told it went well.
                    #
                    # Left outstanding rather than refused: leftover words
                    # are the signal that a sentence needs reading, not
                    # that it cannot be read. Reasoning gets it next, and
                    # only if that cannot settle it does the founder get
                    # asked -- so "call it Finance and put it in
                    # Documents" resolves while "d drive in Onkar folder"
                    # asks.
                    continue
                found[name] = FieldEvidence(
                    value=mentioned[0], evidence=text, source=STATED
                )
            elif len(mentioned) > 1:
                return Understanding(
                    fields=found,
                    uncertain=True,
                    reason=f"more than one {name} was named: "
                           f"{', '.join(sorted(mentioned))}",
                )

        return Understanding(fields=found)

    def _reasoned_fields(
        self,
        text: str,
        *,
        wanted: Sequence[str],
        known: Mapping[str, str],
        objective: str,
        question: str,
    ) -> Understanding | None:
        """The Brain's existing door, asked for a narrow extraction.

        Not "what should we do?" -- that question invites a model to
        propose actions, which is the failure `_submit_objective` records
        at length. This asks only: *which of these named fields does this
        sentence supply, and with what value.*

        `None` means no usable answer: a dead ladder, a refusal, output
        that is not JSON, or values that fail validation. It is never an
        exception and never a guess.
        """
        if self._reasoner is None:
            return None

        from master_agent.ai_infrastructure.budgeted_request import (
            BudgetedSelectionRequest,
        )
        from master_agent.ai_infrastructure.workload import INTERACTIVE
        from master_agent.plugins.model_router import RoutingContext, SelectionRequest

        lines = []
        for name in wanted:
            vocabulary = self._vocabularies.get(name)
            if vocabulary:
                lines.append(
                    f'    "{name}": exactly one of '
                    f'{", ".join(sorted(vocabulary))} -- or omit it'
                )
            elif name == PARENT:
                lines.append(
                    '    "parent": if they named a folder INSIDE one of '
                    "those places to put it in, its name -- otherwise omit it"
                )
            else:
                lines.append(f'    "{name}": the founder\'s own words for it')
        already = (
            "\n".join(f"    {name} = {value}" for name, value in known.items())
            or "    (nothing yet)"
        )
        prompt = (
            "A founder is talking to an assistant that is collecting a few "
            "specific pieces of information.\n\n"
            f"    What they originally asked for: {objective.strip()}\n"
            f"    Already established:\n{already}\n"
            f"    The assistant just asked: {question.strip()}\n"
            f"    The founder replied: {text.strip()}\n\n"
            "Read ONLY what the founder actually said. Report which of "
            "these fields their reply supplies:\n\n"
            + "\n".join(lines)
            + "\n\nReply with JSON and nothing else:\n"
            '    {"fields": {...}, "ambiguous": false}\n\n'
            "Rules. Include a field ONLY if the founder's words establish "
            "it -- never because it would be convenient or likely. Omit "
            "anything they did not say. If their reply points at something "
            "with no clear referent (\"put it there\", \"the usual place\") "
            'set "ambiguous": true and return no fields. If a field has a '
            "listed set of values and their reply names something NARROWER "
            "or DIFFERENT -- a folder inside one of them, a path, somewhere "
            "not on the list -- that is not one of those values: set "
            '"ambiguous": true rather than picking the closest one. If they '
            "corrected something they said earlier, report the NEW value."
        )
        context = RoutingContext(
            is_online=True,
            # Reading a sentence for named fields is a small judgement.
            # Asking for strong reasoning would push a cheap,
            # latency-sensitive call up the ladder for no gain.
            requires_strong_reasoning=False,
            capability=REASONING_CAPABILITY,
            requester="brain_intent_fields",
        )
        request = BudgetedSelectionRequest(
            **vars(SelectionRequest.from_context(context)),
            request_class=INTERACTIVE,
            prompt=prompt,
        )
        try:
            outcome = self._reasoner.run(prompt, request)
        except Exception:  # noqa: BLE001 -- a dead ladder is a default, not a crash
            return None
        if outcome is None or not getattr(outcome, "ok", False):
            return None

        document = _parsed_json(getattr(outcome, "text", "") or "")
        if document is None:
            # Unverified output never becomes Intent.
            return None
        if document.get("ambiguous") is True:
            return Understanding(
                uncertain=True, reason="the reply did not name a clear value"
            )

        offered = document.get("fields")
        if not isinstance(offered, dict):
            return None
        accepted: dict[str, FieldEvidence] = {}
        for name in wanted:
            value = offered.get(name)
            if not isinstance(value, str) or not value.strip():
                continue
            value = value.strip()
            vocabulary = self._vocabularies.get(name)
            if vocabulary:
                # A closed field may only take a value the capability
                # accepts. A model naming somewhere plausible but
                # non-existent is exactly what validation is for.
                match = {v.lower(): v for v in vocabulary}.get(value.lower())
                if match is None:
                    continue
                value = match
            accepted[name] = FieldEvidence(
                value=value, evidence=text, source=REASONED
            )
        return Understanding(fields=accepted)

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

        # A name plus a place does not answer WHAT is being created.
        #
        # This check must precede both the single-command parsers and the
        # compound-objective bypass.  Without it, ``create Budget on
        # Desktop`` becomes generic prose and a Planner/provider is invited
        # to choose file versus folder.  In a compound sentence the same
        # guess can mutate the environment before the safe Reporter says it
        # cannot confirm conformance.  Capability availability is not a
        # source of Founder meaning; the missing object kind is therefore a
        # clarification owned here.
        ambiguous_create = self._parse_nounless_create(text, supplied)
        if ambiguous_create is not None:
            return self._with_roles(ambiguous_create, text)

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
                if pattern not in text.lower():
                    continue
                recognizes = getattr(handler, "recognizes", None)
                if recognizes is not None and not recognizes(text):
                    continue
                claim_trigger = pattern
                structural_trigger = getattr(handler, "claim_trigger", None)
                if structural_trigger is not None:
                    claim_trigger = structural_trigger(text) or pattern
                claimed = handler().parse(text, supplied)
                if _may_claim(text, claim_trigger, claimed, supplied):
                    return self._with_roles(claimed, text)
                # This parser recognised a phrase, could not read the
                # sentence, and the sentence says much more than the
                # phrase. Not its to claim -- try the next one, and
                # otherwise travel on to the layer that owns
                # decomposition.

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

    def _parse_nounless_create(
        self,
        text: str,
        supplied: Mapping[str, str] | None,
    ) -> IntentResult | None:
        """Clarify a structurally omitted file/folder kind.

        ``None`` means this is not the semantic class.  A result means the
        class was recognised and must not escape to generic Planning until
        the Founder supplies the missing meaning.
        """
        match = _NOUNLESS_CREATE.search(text)
        if match is None:
            return None

        name = match.group("name").strip(_VALUE_STRIP)
        tokens = {
            token.strip(_VALUE_STRIP).lower()
            for token in name.split()
            if token.strip(_VALUE_STRIP)
        }
        if not name or tokens & _EXPLICIT_CREATE_KINDS:
            return None
        if name.lower() in _CREATE_REFERENTS:
            # A missing referent is a different ambiguity.  Do not pretend
            # this rule knows what ``it`` points to.
            return None

        location_words = match.group("location").lower().replace("_", " ")
        location = location_words.replace(" ", "_") if location_words == "d drive" else location_words
        for candidate in self._vocabularies.get("location", ()):
            if candidate.lower().replace("_", " ") == location_words:
                location = candidate
                break

        raw_kind = str((supplied or {}).get(_CREATION_KIND, "") or "").strip()
        kind_tokens = {
            token.strip(_VALUE_STRIP).lower()
            for token in raw_kind.split()
            if token.strip(_VALUE_STRIP)
        }
        kind = ""
        if kind_tokens & {"folder", "directory"}:
            kind = "folder"
        elif kind_tokens & {"file", "document"}:
            kind = "file"

        base_resolved = {
            "creation_name": name,
            "location": location,
        }
        base_evidence = {
            key: FieldEvidence(value=value, evidence=text, source=STATED).as_dict()
            for key, value in base_resolved.items()
        }
        if not kind:
            return IntentResult(
                clarification=ClarificationQuestion(
                    question=(
                        f"Should I create a folder or a file named {name}?"
                    ),
                    key=_CREATION_KIND,
                    options=_CREATION_KIND_OPTIONS,
                    required=True,
                    gathering=(_CREATION_KIND,),
                ),
                raw_input=text,
                resolved=base_resolved,
                evidence=base_evidence,
            )

        # One folder command can reuse the existing typed parser and its
        # capability contract.  No second folder interpretation is authored
        # here; this method only supplies the fields the Founder just made
        # unambiguous.
        if kind == "folder" and not enumerates_multiple_requirements(text):
            result = CreateFolderIntent().parse(
                "create a folder",
                supplied={"folder_name": name, "location": location},
            )
            result.raw_input = text
            return result

        # A compound objective still belongs to Planning.  Preserve every
        # original word and attach the Founder clarification as additional
        # evidence; do not collapse the sentence into its creation clause.
        clarified_goal = (
            f"{text}\nFounder clarification: the named item {name!r} is a {kind}."
        )
        return IntentResult(
            intent=Intent(
                goal=clarified_goal,
                constraints=[],
                context={
                    "raw_input": text,
                    "clarified": {_CREATION_KIND: kind},
                },
                success_criteria=[],
            ),
            raw_input=text,
        )


    # ---- what the founder requires -----------------------------------

    def requirements_for(self, intent: Any, *, raw: str = "") -> tuple:
        """The founder's requirements, as facts rather than prose.

        ## Why this lives here

        Meaning is understood here, so meaning is extracted here. The
        alternative -- letting the Planner or the Reporter re-derive it
        from the sentence later -- is what let three separate defects
        share one shape: the founder's meaning was never a first-class
        object, so every layer had its own private reading of it.

        ## Deterministic first, and usually only

        A typed intent has already been parsed. Its goal IS the effect,
        its payload entries ARE the constraints, and a question's answer
        IS the information required. Nothing about that needs a model,
        and asking one would be paying to rediscover what the parser
        already knows.

        Reasoning is reached only for a generic objective -- prose no
        parser claimed -- and even then it is asked what the founder
        REQUIRES, never which capability should run.
        """
        evidence = (raw or getattr(intent, "goal", "") or "").strip()

        answers = str(getattr(intent, "answers_founder", "") or "")
        capability = str(getattr(intent, "capability", "") or "")
        payload = dict(getattr(intent, "payload", None) or {})

        if answers:
            # A question. The requirement is that the founder be TOLD
            # something -- not that anything change.
            requirements = (SemanticRequirement(
                requirement_id="req_1",
                kind=INFORMATION,
                description=f"{QUESTION_REQUIREMENT} {evidence}",
                provenance=evidence,
                founder_evidence=evidence,
            ),)
            self._record_requirement_admission(
                intent, self._deterministic_admission(requirements),
            )
            return requirements

        if capability:
            found = [SemanticRequirement(
                requirement_id="req_1",
                kind=EFFECT,
                description=evidence or f"perform {capability}",
                provenance=evidence,
                # The objective IS the founder's words here. Leaving the
                # field empty made the effect requirement the one place
                # an audit had only the interpretation to look at.
                founder_evidence=evidence,
            )]
            # Every argument the founder supplied is a condition on that
            # effect. Ordered by the payload's own key order so the ids
            # are deterministic for the same Intent.
            #
            # Each carries the founder's OWN WORDS for that field beside
            # the resolved value. Without both, conformance compares the
            # execution against the interpretation and calls agreement
            # with itself success -- which it did, twice, about a folder
            # on the wrong drive.
            recorded = dict(
                (getattr(intent, "context", None) or {}).get("field_evidence") or {}
            )
            for index, (name, value) in enumerate(payload.items(), start=2):
                found.append(SemanticRequirement(
                    requirement_id=f"req_{index}",
                    kind=CONSTRAINT,
                    description=f"{name} = {value}",
                    provenance=evidence,
                    # Per-field words when the conversation recorded
                    # them; otherwise the founder's sentence.
                    #
                    # A ONE-SENTENCE request records no per-field
                    # evidence -- nothing asked, so nothing was
                    # answered -- and this returned "" for every
                    # constraint on the commonest path a founder uses.
                    # The multi-turn path carried evidence and the
                    # direct path did not, so the acceptance that
                    # proved this contract proved it on the narrower
                    # of the two.
                    #
                    # The sentence is coarser than the field but it is
                    # the founder's own words and it is never empty,
                    # which is what an audit needs to compare an
                    # interpretation against.
                    founder_evidence=_said_for(recorded, name, value) or evidence,
                ))
            requirements = tuple(found)
            self._record_requirement_admission(
                intent, self._deterministic_admission(requirements),
            )
            return requirements

        # **Compound is not the same as ambiguous.**
        #
        # A three-sentence objective naming a folder, a file and its
        # exact text has enumerated several requirements and left
        # nothing to interpret. `enumerates_multiple_requirements` is
        # right to keep it away from the single-command parsers -- that
        # guard exists because a compound sentence once lost four
        # requirements to one -- but being unfit for a COMMAND
        # recogniser is not the same as needing a model.
        #
        # Measured live 2026-09-05: exactly such an objective spent
        # eight external calls here and still refused, for a folder and
        # a text file. ADR-0027 names that case in as many words --
        # "creating a folder must not deliberate".
        #
        # So ask the deterministic recogniser first. It answers `()` on
        # any doubt, and on doubt nothing below changes.
        dictated = dictated_effects(evidence)
        if dictated:
            requirements = tuple(
                SemanticRequirement(
                    requirement_id=f"req_{index}",
                    kind=EFFECT,
                    description=description,
                    provenance=evidence,
                    founder_evidence=evidence,
                )
                for index, description in enumerate(dictated, start=1)
            )
            self._record_requirement_admission(
                intent, self._deterministic_admission(requirements),
            )
            return requirements

        # Preserve the established no-reasoner composition used by offline
        # deterministic/test pipelines: there was no provider proposal to
        # admit or reject. Production compound-intent admission wires a
        # reasoner and therefore always receives the verdict below.
        if not evidence or self._reasoner is None:
            return ()
        admission = self._reasoned_requirement_admission(evidence)
        self._record_requirement_admission(intent, admission)
        return admission.requirements

    @staticmethod
    def _record_requirement_admission(
        intent: Any, admission: RequirementAdmission,
    ) -> None:
        context = getattr(intent, "context", None)
        if isinstance(context, dict):
            context["requirement_admission"] = admission.as_dict()

    @staticmethod
    def _deterministic_admission(
        requirements: tuple[SemanticRequirement, ...],
    ) -> RequirementAdmission:
        anchors = tuple({
            "anchor_id": f"anchor_{index}",
            "source_quote": requirement.founder_evidence,
            "meaning": requirement.description,
            "depends_on": [],
        } for index, requirement in enumerate(requirements, start=1))
        coverage = tuple({
            "anchor_id": f"anchor_{index}",
            "requirement_indices": [index],
            "independently_trackable": True,
        } for index, _requirement in enumerate(requirements, start=1))
        preserved = tuple({
            "anchor_id": f"anchor_{index}",
            "requirement_index": index,
            "requirement_id": requirement.requirement_id,
            "source_quote": requirement.founder_evidence,
        } for index, requirement in enumerate(requirements, start=1))
        return RequirementAdmission(
            requirements=requirements,
            valid=True,
            semantic_verdict="valid_deterministic",
            founder_obligation_anchors=anchors,
            coverage_mapping=coverage,
            founder_obligations_preserved=preserved,
            independently_verifiable=True,
        )

    def _reasoned_requirements(self, objective: str) -> tuple:
        """Compatibility surface for callers that only need the tuple."""
        return self._reasoned_requirement_admission(objective).requirements

    def _reasoned_requirement_admission(
        self, objective: str,
    ) -> RequirementAdmission:
        """Derive, validate, correct once, and admit canonical semantics.

        Stage 1C runs first and separately: the Founder obligation set is
        established and independently audited BEFORE any decomposition
        exists, so the anchors that police the decomposition below cannot
        have been shaped by it. Only a trusted obligation set reaches the
        Stage 1B machinery, which is otherwise unchanged.
        """
        if not objective or self._reasoner is None:
            return RequirementAdmission(
                valid=False,
                semantic_verdict="unavailable",
                structural_issues=("semantic requirement reasoning is unavailable",),
            )

        trust = self._trusted_founder_obligations(objective)
        if not trust["trusted"]:
            return RequirementAdmission(
                valid=False,
                semantic_verdict=trust["verdict"],
                structural_issues=tuple(trust["issues"]),
                obligation_issues=tuple(trust["issues"]),
                source_regions=tuple(trust["regions"]),
                founder_obligation_anchors=tuple(trust["anchors"]),
                initial_obligation_anchors=tuple(trust["initial_anchors"]),
                region_dispositions=tuple(trust["region_dispositions"]),
                anchor_entailment=tuple(trust["anchor_entailment"]),
                lost_obligations=tuple(trust["omissions"]),
                merged_obligations=tuple(trust["collapses"]),
                obligation_correction_attempted=trust["correction_attempted"],
                state_candidates=tuple(trust.get("state_candidates", ())),
                state_placements=tuple(trust.get("state_placements", ())),
                intra_anchor_fusion=tuple(trust.get("intra_anchor_fusion", ())),
            )

        trusted_anchors = list(trust["anchors"])
        prompt = self._requirement_decomposition_prompt(objective, trusted_anchors)
        initial_document = self._reasoned_json(
            prompt, requester="brain_semantic_requirements",
        )
        initial = (
            initial_document.get("requirements")
            if isinstance(initial_document, dict) else None
        )
        initial_rows = self._requirement_rows(initial)
        offered = initial
        correction_attempted = False
        corrected = False
        issues = requirement_structure_issues(objective, offered)
        detected_structural_issues = tuple(issues)
        detected_merged: tuple[dict[str, Any], ...] = ()
        detected_lost: tuple[dict[str, Any], ...] = ()
        detected_invented: tuple[dict[str, Any], ...] = ()
        detected_anchors: tuple[dict[str, Any], ...] = ()
        detected_coverage: tuple[dict[str, Any], ...] = ()

        if issues:
            correction_attempted = True
            offered = self._correct_requirement_decomposition(
                objective, prompt, offered, issues,
            )
            issues = requirement_structure_issues(objective, offered)
            if issues:
                return RequirementAdmission(
                    valid=False,
                    semantic_verdict="invalid_structure_after_correction",
                    structural_issues=tuple(issues),
                    detected_structural_issues=detected_structural_issues,
                    correction_attempted=True,
                    initial_provider_output=initial_rows,
                    final_provider_output=self._requirement_rows(offered),
                )
            corrected = True

        rows = [dict(row) for row in offered]
        audit = self._semantic_integrity_review(objective, rows, trusted_anchors)
        audit_issues = _audit_structure_issues(objective, rows, audit)
        review_correction_attempted = False
        if audit_issues:
            # A review that cannot be read is a TRANSLATION fault, not a
            # semantic one: live Probe #2 lost a whole mission because the
            # reviewer answered in 0-based indices. Every other Stage-1
            # failure gets one grounded repair; this one had none, so a
            # formatting slip was fatal where a genuine semantic violation
            # was not. It gets the same single bounded correction -- of the
            # REVIEW only. The Founder's obligations are already trusted
            # and the requirements already stand; neither is regenerated.
            review_correction_attempted = True
            audit = self._correct_semantic_review(
                objective, rows, trusted_anchors, audit, audit_issues,
            )
            audit_issues = _audit_structure_issues(objective, rows, audit)
        if audit_issues:
            return RequirementAdmission(
                valid=False,
                semantic_verdict="semantic_review_unusable",
                structural_issues=tuple(audit_issues),
                detected_structural_issues=detected_structural_issues,
                correction_attempted=correction_attempted,
                corrected=corrected,
                initial_provider_output=initial_rows,
                final_provider_output=tuple(rows),
                # The obligation boundary already passed. Refusing the
                # review must not erase that truth from the record.
                founder_obligation_anchors=tuple(trusted_anchors),
                source_regions=tuple(trust["regions"]),
                region_dispositions=tuple(trust["region_dispositions"]),
                anchor_entailment=tuple(trust["anchor_entailment"]),
                state_candidates=tuple(trust.get("state_candidates", ())),
                state_placements=tuple(trust.get("state_placements", ())),
                obligation_correction_attempted=trust["correction_attempted"],
                review_correction_attempted=review_correction_attempted,
            )

        semantic = _coverage_decision(rows, audit)
        if not semantic["valid"]:
            detected_anchors = tuple(
                dict(row) for row in semantic.get("anchors", ())
            )
            detected_coverage = tuple(
                dict(row) for row in semantic.get("coverage", ())
            )
            detected_merged = tuple(
                dict(row) for row in semantic.get("merged", ())
            )
            detected_lost = tuple(
                dict(row) for row in semantic.get("lost", ())
            )
            detected_invented = tuple(
                dict(row) for row in semantic.get("invented", ())
            )
            semantic_issues = _semantic_violation_messages(semantic)
            if correction_attempted:
                return self._invalid_semantic_admission(
                    initial_rows, rows, semantic, semantic_issues,
                    detected_merged=detected_merged,
                    detected_lost=detected_lost,
                    detected_invented=detected_invented,
                    detected_anchors=detected_anchors,
                    detected_coverage=detected_coverage,
                )
            correction_attempted = True
            corrected_rows = self._correct_requirement_decomposition(
                objective, prompt, rows, semantic_issues,
            )
            issues = requirement_structure_issues(objective, corrected_rows)
            if issues:
                return RequirementAdmission(
                    valid=False,
                    semantic_verdict="invalid_structure_after_correction",
                    structural_issues=tuple(issues),
                    detected_structural_issues=detected_structural_issues,
                    detected_merged_obligations=detected_merged,
                    detected_lost_obligations=detected_lost,
                    detected_invented_obligations=detected_invented,
                    detected_founder_obligation_anchors=detected_anchors,
                    detected_coverage_mapping=detected_coverage,
                    correction_attempted=True,
                    initial_provider_output=initial_rows,
                    final_provider_output=self._requirement_rows(corrected_rows),
                    merged_obligations=tuple(
                        dict(row) for row in semantic.get("merged", ())
                    ),
                    lost_obligations=tuple(
                        dict(row) for row in semantic.get("lost", ())
                    ),
                    invented_obligations=tuple(
                        dict(row) for row in semantic.get("invented", ())
                    ),
                    founder_obligation_anchors=tuple(
                        dict(row) for row in semantic.get("anchors", ())
                    ),
                    coverage_mapping=tuple(
                        dict(row) for row in semantic.get("coverage", ())
                    ),
                    unmapped_anchors=tuple(
                        dict(row) for row in semantic.get("lost", ())
                    ),
                    improper_merges=tuple(
                        dict(row) for row in semantic.get("merged", ())
                    ),
                    invented_requirements=tuple(
                        dict(row) for row in semantic.get("invented", ())
                    ),
                )
            rows = [dict(row) for row in corrected_rows]
            audit = self._semantic_integrity_review(objective, rows, trusted_anchors)
            audit_issues = _audit_structure_issues(objective, rows, audit)
            if audit_issues:
                return RequirementAdmission(
                    valid=False,
                    semantic_verdict="semantic_review_unusable_after_correction",
                    structural_issues=tuple(audit_issues),
                    detected_structural_issues=detected_structural_issues,
                    detected_merged_obligations=detected_merged,
                    detected_lost_obligations=detected_lost,
                    detected_invented_obligations=detected_invented,
                    detected_founder_obligation_anchors=detected_anchors,
                    detected_coverage_mapping=detected_coverage,
                    correction_attempted=True,
                    initial_provider_output=initial_rows,
                    final_provider_output=tuple(rows),
                )
            semantic = _coverage_decision(rows, audit)
            if not semantic["valid"]:
                return self._invalid_semantic_admission(
                    initial_rows,
                    rows,
                    semantic,
                    _semantic_violation_messages(semantic),
                    detected_merged=detected_merged,
                    detected_lost=detected_lost,
                    detected_invented=detected_invented,
                    detected_anchors=detected_anchors,
                    detected_coverage=detected_coverage,
                )
            corrected = True

        requirements = tuple(
            SemanticRequirement(
                requirement_id=f"req_{index}",
                kind=str(item["kind"]).strip().lower(),
                description=str(item["description"]).strip(),
                provenance=objective,
                founder_evidence=str(item["source_quote"]).strip(),
                candidate_property=bool(item["candidate_property"]),
            )
            for index, item in enumerate(rows, start=1)
        )
        return RequirementAdmission(
            requirements=requirements,
            valid=True,
            semantic_verdict="valid_after_correction" if corrected else "valid",
            founder_obligation_anchors=tuple(
                dict(row) for row in semantic.get("anchors", ())
            ),
            coverage_mapping=tuple(
                dict(row) for row in semantic.get("coverage", ())
            ),
            founder_obligations_preserved=tuple(
                dict(row) for row in semantic.get("preserved", ())
            ),
            independently_verifiable=True,
            detected_structural_issues=detected_structural_issues,
            detected_merged_obligations=detected_merged,
            detected_lost_obligations=detected_lost,
            detected_invented_obligations=detected_invented,
            detected_founder_obligation_anchors=detected_anchors,
            detected_coverage_mapping=detected_coverage,
            correction_attempted=correction_attempted,
            corrected=corrected,
            review_correction_attempted=review_correction_attempted,
            source_regions=tuple(trust["regions"]),
            region_dispositions=tuple(trust["region_dispositions"]),
            anchor_entailment=tuple(trust["anchor_entailment"]),
            state_candidates=tuple(trust.get("state_candidates", ())),
            state_placements=tuple(trust.get("state_placements", ())),
            obligation_correction_attempted=trust["correction_attempted"],
            initial_obligation_anchors=tuple(trust["initial_anchors"]),
            initial_provider_output=initial_rows,
            final_provider_output=tuple(rows),
        )

    @staticmethod
    def _requirement_rows(offered: Any) -> tuple[dict[str, Any], ...]:
        if not isinstance(offered, list):
            return ()
        return tuple(dict(row) for row in offered if isinstance(row, dict))

    @staticmethod
    def _invalid_semantic_admission(
        initial: tuple[dict[str, Any], ...],
        final: list[dict[str, Any]],
        audit: Mapping[str, Any],
        issues: list[str],
        *,
        detected_merged: tuple[dict[str, Any], ...] = (),
        detected_lost: tuple[dict[str, Any], ...] = (),
        detected_invented: tuple[dict[str, Any], ...] = (),
        detected_anchors: tuple[dict[str, Any], ...] = (),
        detected_coverage: tuple[dict[str, Any], ...] = (),
    ) -> RequirementAdmission:
        return RequirementAdmission(
            valid=False,
            semantic_verdict="invalid_semantics_after_correction",
            founder_obligation_anchors=tuple(
                dict(row) for row in audit.get("anchors", ())
            ),
            coverage_mapping=tuple(
                dict(row) for row in audit.get("coverage", ())
            ),
            unmapped_anchors=tuple(
                dict(row) for row in audit.get("lost", ())
            ),
            improper_merges=tuple(
                dict(row) for row in audit.get("merged", ())
            ),
            invented_requirements=tuple(
                dict(row) for row in audit.get("invented", ())
            ),
            founder_obligations_preserved=tuple(
                dict(row) for row in audit.get("preserved", ())
            ),
            merged_obligations=tuple(
                dict(row) for row in audit.get("merged", ())
            ),
            lost_obligations=tuple(dict(row) for row in audit.get("lost", ())),
            invented_obligations=tuple(
                dict(row) for row in audit.get("invented", ())
            ),
            independently_verifiable=bool(audit.get("independently_verifiable")),
            structural_issues=tuple(issues),
            detected_merged_obligations=detected_merged or tuple(
                dict(row) for row in audit.get("merged", ())
            ),
            detected_lost_obligations=detected_lost or tuple(
                dict(row) for row in audit.get("lost", ())
            ),
            detected_invented_obligations=detected_invented or tuple(
                dict(row) for row in audit.get("invented", ())
            ),
            detected_founder_obligation_anchors=detected_anchors or tuple(
                dict(row) for row in audit.get("anchors", ())
            ),
            detected_coverage_mapping=detected_coverage or tuple(
                dict(row) for row in audit.get("coverage", ())
            ),
            correction_attempted=True,
            initial_provider_output=initial,
            final_provider_output=tuple(final),
        )

    @staticmethod
    def _requirement_decomposition_prompt(
        objective: str, anchors: Sequence[Mapping[str, Any]] = (),
    ) -> str:
        """Refine an already-trusted obligation set into requirements.

        Live Probe #4 established ten independently stateful Founder
        obligations and then handed this layer the raw sentence alone. It
        did what anyone would with only a sentence: it read the sentence
        again, and re-fused the top-three selection with all five
        comparison dimensions that Stage 1 had just spent four reasoning
        passes separating.

        Once meaning is trusted upstream, downstream refines it -- it does
        not re-derive it. The objective stays for provenance and wording;
        the obligations are the semantic input.
        """
        import json

        trusted = ""
        if anchors:
            trusted = (
                "\nTRUSTED FOUNDER OBLIGATIONS. These have already passed "
                "Founder-meaning integrity review: each one is grounded in "
                "the Founder's own words and is independently trackable, "
                "meaning it can be SATISFIED while another remains "
                "UNRESOLVED.\n"
                + json.dumps(
                    [{"anchor_id": row.get("anchor_id"),
                      "state": row.get("meaning"),
                      "founder_source": row.get("source_quote"),
                      "depends_on": list(row.get("depends_on") or ())}
                     for row in anchors],
                    indent=2, ensure_ascii=False,
                )
                + "\n\nDo not merge them. Do not omit them. Do not invent "
                "replacements. Do not reinterpret the original request into "
                "a smaller obligation set. Produce canonical requirements "
                "that preserve these trusted obligation states. One "
                "obligation may become several MORE PRECISE requirements "
                "where that genuinely helps tracking; it may never become "
                "part of a requirement that also carries another "
                "obligation's state. The Founder's sentence below is "
                "provenance and wording -- where the two appear to differ, "
                "the trusted obligations are what was established.\n"
            )
        return (
            "A founder has asked an assistant to do something. Break their "
            "request into the separate things they REQUIRE.\n\n"
            f"    The founder said: {objective}\n\n"
            + trusted
            + "\nReport each requirement with a kind:\n"
            "    effect      - something in the world must change\n"
            "    information - the founder must be TOLD something\n"
            "    deliverable - an artefact must be produced for them\n"
            "    constraint  - a condition another requirement must meet\n\n"
            "For each requirement state candidate_property. It is true only "
            "when EACH candidate can possess or fail that property. It is "
            "false for mission work such as establishing a candidate set, "
            "recommending one, or producing a deliverable.\n\n"
            "Reply with JSON and nothing else:\n"
            '    {"requirements": [{"kind": "...", "description": "...", '
            '"candidate_property": true, "source_quote": "...", '
            '"success_meaning": "..."}]}\n\n'
            "Rules. Describe WHAT is required, never HOW. source_quote must "
            "be copied from the Founder input and identify the language that "
            "establishes this obligation. success_meaning must state the "
            "independently observable semantic state that would make it true. "
            "Do not add sensible execution steps. Do not split one inseparable "
            "outcome merely because execution may use several capabilities. "
            "Do not merge obligations when one can legitimately be satisfied, "
            "blocked or unresolved independently of the other, or when one "
            "produces the subject/state consumed by the other. Establishing a "
            "candidate set is independently stateful from evaluating properties "
            "of that set. An outcome and its verification condition may remain "
            "one requirement."
        )

    def _reasoned_json(self, prompt: str, *, requester: str) -> dict[str, Any] | None:
        from master_agent.ai_infrastructure.budgeted_request import (
            BudgetedSelectionRequest,
        )
        from master_agent.ai_infrastructure.workload import INTERACTIVE
        from master_agent.plugins.model_router import RoutingContext, SelectionRequest

        context = RoutingContext(
            is_online=True,
            requires_strong_reasoning=False,
            capability=REASONING_CAPABILITY,
            requester=requester,
        )
        request = BudgetedSelectionRequest(
            **vars(SelectionRequest.from_context(context)),
            request_class=INTERACTIVE,
            prompt=prompt,
        )
        try:
            outcome = self._reasoner.run(prompt, request)
        except Exception:  # noqa: BLE001 -- unavailable reasoning is not a crash
            return None
        if outcome is None or not getattr(outcome, "ok", False):
            return None
        return _parsed_json(getattr(outcome, "text", "") or "")

    # ---- Stage 1C: the Founder obligation set as a root of trust -------

    def _trusted_founder_obligations(self, objective: str) -> dict[str, Any]:
        """Establish, independently audit and deterministically admit the
        Founder's obligation set BEFORE any decomposition exists.

        Producer and verifier are separated on purpose. The producer sees
        only raw Founder language; the auditor sees that language, the
        deterministic source regions and the proposed anchors -- never the
        requirements those anchors will later police. Nothing downstream
        can therefore shape the obligation set that judges it.
        """
        regions = _source_coverage_regions(objective)
        candidates = _source_state_candidates(objective)
        initial_anchors = self._propose_founder_obligations(objective, regions)
        anchors = initial_anchors
        correction_attempted = False
        decision: dict[str, Any] = {}
        verdict = "obligation_set_untrusted"

        for attempt in (1, 2):
            audit = self._audit_founder_obligations(
                objective, regions, anchors, candidates,
            )
            structural = _obligation_audit_issues(
                objective, regions, anchors, audit, candidates,
            )
            if structural:
                decision = {
                    "trusted": False, "issues": structural,
                    "unexplained_regions": [], "unentailed_anchors": [],
                    "omissions": [], "collapses": [], "invented": [],
                    "regions": list(regions), "region_dispositions": [],
                    "anchor_entailment": [], "intra_anchor_fusion": [],
                    "state_candidates": [dict(row) for row in candidates],
                    "state_placements": [],
                }
                verdict = "obligation_audit_unusable"
            else:
                decision = _obligation_trust_decision(
                    regions, anchors, audit, candidates,
                )
                verdict = "obligation_set_untrusted"

            if decision["trusted"]:
                return {
                    "trusted": True,
                    "verdict": "founder_obligations_trusted",
                    "regions": list(regions),
                    "anchors": [dict(row) for row in anchors],
                    "initial_anchors": [dict(row) for row in initial_anchors],
                    "region_dispositions": decision["region_dispositions"],
                    "anchor_entailment": decision["anchor_entailment"],
                    "state_candidates": decision.get("state_candidates", []),
                    "state_placements": decision.get("state_placements", []),
                    "intra_anchor_fusion": [],
                    "issues": [], "omissions": [], "collapses": [],
                    "correction_attempted": correction_attempted,
                }

            if attempt == 2:
                break
            # One bounded correction of the OBLIGATION SET -- a different
            # boundary from the requirement correction below it. Letting a
            # requirement correction quietly repair an untrusted anchor set
            # is exactly the confusion Stage 1C exists to end.
            correction_attempted = True
            anchors = self._correct_founder_obligations(
                objective, regions, anchors, decision["issues"],
                decision.get("intra_anchor_fusion", ()),
            )

        return {
            "trusted": False,
            # After a bounded correction the meaning is not settled, and
            # saying so is the contract MissionService already refuses on.
            "verdict": (
                UNSETTLED_INTERPRETATION if correction_attempted else verdict
            ),
            "regions": list(regions),
            "anchors": [dict(row) for row in anchors],
            "initial_anchors": [dict(row) for row in initial_anchors],
            "region_dispositions": decision.get("region_dispositions", []),
            "anchor_entailment": decision.get("anchor_entailment", []),
            "state_candidates": decision.get("state_candidates", []),
            "state_placements": decision.get("state_placements", []),
            "intra_anchor_fusion": decision.get("intra_anchor_fusion", []),
            "issues": decision.get("issues", []),
            "omissions": decision.get("omissions", []),
            "collapses": decision.get("collapses", []),
            "correction_attempted": correction_attempted,
        }

    def _propose_founder_obligations(
        self, objective: str, regions: Sequence[str],
    ) -> tuple[dict[str, Any], ...]:
        """The blind producer. Raw Founder language in, anchors out."""
        import json

        prompt = (
            "A founder stated an objective. Enumerate the separate "
            "OBLIGATIONS their words place on an assistant.\n\n"
            f"FOUNDER INPUT:\n{objective}\n\n"
            "SOURCE REGIONS (deterministic coverage only; candidate spans, "
            "NOT pre-decided obligations, and several regions may belong to "
            "one obligation):\n"
            + json.dumps(list(regions), indent=2, ensure_ascii=False)
            + "\n\nAn obligation anchor is a span copied from the Founder "
            "input plus ONE independently stateful meaning that must survive "
            "every later transformation. If one state can be SATISFIED while "
            "another remains UNRESOLVED or BLOCKED, they are separate "
            "anchors. If one state produces the entity another consumes, name "
            "that prerequisite in depends_on. Establishing a candidate set is "
            "independently stateful from evaluating properties of that set, "
            "and a condition on the work is its own state whenever it can be "
            "unmet while the outcome it governs already exists -- an "
            "evidence-sufficiency, budget or privacy condition is a separate "
            "anchor, not a decoration on the anchor beside it.\n\n"
            "Do not create anchors from sentence count, verbs, commas or the "
            "word 'and'. An inseparable outcome and its completion condition "
            "are ONE anchor: saving and verifying one artifact is one "
            "deliverable, and a decision with its requested rationale is one "
            "informational outcome.\n\n"
            "Describe WHAT is obliged, never HOW. Do not add sensible extra "
            "work the Founder did not ask for.\n\n"
            "Reply with JSON and nothing else:\n"
            '{"anchors": [{"anchor_id": "anchor_1", "source_quote": "...", '
            '"meaning": "...", "depends_on": []}]}'
        )
        document = self._reasoned_json(
            prompt, requester="brain_founder_obligations",
        )
        proposed = document.get("anchors") if isinstance(document, dict) else None
        if not isinstance(proposed, list):
            return ()
        return tuple(dict(row) for row in proposed if isinstance(row, dict))

    def _audit_founder_obligations(
        self,
        objective: str,
        regions: Sequence[str],
        anchors: Sequence[Mapping[str, Any]],
        candidates: Sequence[Mapping[str, Any]] = (),
    ) -> dict[str, Any] | None:
        """The independent auditor. It never sees the decomposition."""
        import json

        prompt = (
            "Audit whether a proposed set of Founder obligations preserves "
            "the Founder's meaning. You did not author this set; do not "
            "improve the objective and do not plan any execution.\n\n"
            f"FOUNDER INPUT:\n{objective}\n\n"
            "DETERMINISTIC SOURCE REGIONS (every one must be accounted for "
            "explicitly):\n"
            + json.dumps(
                [{"region_index": index, "text": text}
                 for index, text in enumerate(regions, start=1)],
                indent=2, ensure_ascii=False,
            )
            + "\n\nCANDIDATE STATE UNITS inside those regions "
            "(deterministic; candidates only, NOT decided "
            "obligations -- several may belong to one):\n"
            + json.dumps(
                [{"candidate_index": row.get("candidate_index"),
                  "region_index": row.get("region_index"),
                  "text": row.get("text")} for row in candidates],
                indent=2, ensure_ascii=False,
            )
            + "\n\nPROPOSED OBLIGATION ANCHORS:\n"
            + json.dumps(list(anchors), indent=2, ensure_ascii=False)
            + "\n\nAnswer four questions with evidence, not opinion.\n\n"
            "1. COVERAGE. Give every region exactly one disposition from: "
            + ", ".join(REGION_DISPOSITIONS)
            + ". Name the anchor_id whenever the disposition refers to one. "
            "Use 'omitted' when a region carries Founder meaning that NO "
            "anchor represents. Use 'non_obligational_context' only with a "
            "reason.\n\n"
            "2. ENTAILMENT. For each anchor say whether its meaning actually "
            "FOLLOWS from its own source_quote. A quote that genuinely "
            "appears in the Founder input does not make an unrelated meaning "
            "true: 'Save a verified brief on my Desktop' does not entail "
            "'Email the brief to the team'. Answer entailed true or false, "
            "with a reason when false.\n\n"
            "3. STATE ATOMICITY. Place EVERY candidate state unit "
            "individually. Saying a whole region is represented by "
            "an anchor is NOT enough. Give each candidate one "
            "relationship from: " + ", ".join(STATE_RELATIONSHIPS) + ". "
            "Name the anchor_id for every relationship except "
            "context, which needs a reason instead. Use "
            "independent_outcome or prerequisite_state when the unit "
            "is a mission state that could be SATISFIED while another "
            "remains UNRESOLVED, and evaluation_criterion for a "
            "requested property that could be established for one "
            "candidate while another stays unknown. Use "
            "constraint_unit for a condition on the work that can itself "
            "be met or unmet independently -- an evidence-sufficiency, "
            "budget or privacy condition can fail while the outcome it "
            "governs already exists, so it is its own state. Use "
            "success_condition, rationale, modifier or context ONLY when "
            "the unit has no status of its own because its truth is "
            "already part of another unit being complete -- verifying the "
            "artifact you just saved, or the reason for the decision you "
            "just made. The test is always: can these two units hold "
            "DIFFERENT truthful statuses at the same moment? State per "
            "anchor whether it contains_multiple_states.\n\n"
            "4. INTEGRITY. Report Founder-stated obligations no anchor "
            "carries (omissions), independently stateful obligations "
            "collapsed into one anchor (collapses), and anchors asserting "
            "work the Founder never asked for (invented).\n\n"
            "Return JSON only:\n"
            '{"regions": [{"region_index": 1, "disposition": "...", '
            '"anchor_id": "...", "reason": "..."}], '
            '"state_candidates": [{"candidate_index": 1, '
            '"relationship": "...", "anchor_id": "...", '
            '"reason": "..."}], '
            '"anchors": [{"anchor_id": "...", "entailed": true, '
            '"contains_multiple_states": false, '
            '"reason": "..."}], '
            '"omissions": [{"source_quote": "...", "meaning": "..."}], '
            '"collapses": [{"anchor_id": "...", "reason": "..."}], '
            '"invented": [{"anchor_id": "...", "reason": "..."}], '
            '"valid": true}\n\n'
            "Return structured evidence only, never a reasoning transcript. "
            "The caller decides admission deterministically; your global "
            "valid value is recorded but is not authoritative."
        )
        return self._reasoned_json(
            prompt, requester="brain_founder_obligation_audit",
        )

    def _correct_founder_obligations(
        self,
        objective: str,
        regions: Sequence[str],
        rejected: Sequence[Mapping[str, Any]],
        issues: Sequence[str],
        fused: Sequence[Mapping[str, Any]] = (),
    ) -> tuple[dict[str, Any], ...]:
        """One bounded, grounded repair of the obligation set itself."""
        import json

        try:
            shown = json.dumps(
                {"anchors": list(rejected)}, indent=2, ensure_ascii=False,
            )[:12000]
        except Exception:  # noqa: BLE001
            shown = repr(rejected)[:12000]
        prompt = (
            "A proposed set of Founder obligations was refused by "
            "deterministic admission.\n\n"
            f"FOUNDER INPUT:\n{objective}\n\n"
            "SOURCE REGIONS:\n"
            + json.dumps(list(regions), indent=2, ensure_ascii=False)
            + "\n\nYOUR PREVIOUS OBLIGATION SET:\n" + shown
            + "\n\nIt was refused for these exact reasons:\n"
            + "\n".join(f"    - {issue}" for issue in issues)
            + (
                "\n\nThese anchors each hold SEVERAL independently "
                "satisfiable Founder states. One anchor exposes one "
                "satisfaction state, so split each of them into anchors "
                "that preserve those states separately, changing no other "
                "Founder meaning:\n"
                + "\n".join(
                    "    - {id}: {states}".format(
                        id=row.get("anchor_id", ""),
                        states=", ".join(
                            str(state.get("text", ""))
                            for state in row.get("states", ()) or ()
                        ) or str(row.get("meaning", "")),
                    )
                    for row in fused
                )
                if fused else ""
            )
            + "\n\nCorrect only those violations. Every anchor's source_quote "
            "must be copied from the Founder input and its meaning must "
            "actually follow from that quote. Do not invent work the Founder "
            "did not state. Do not fragment one inseparable outcome: an "
            "outcome and its verification condition remain one anchor, and a "
            "decision and its requested rationale remain one anchor.\n\n"
            "Reply with JSON and nothing else:\n"
            '{"anchors": [{"anchor_id": "anchor_1", "source_quote": "...", '
            '"meaning": "...", "depends_on": []}]}'
        )
        document = self._reasoned_json(
            prompt, requester="brain_founder_obligation_correction",
        )
        proposed = document.get("anchors") if isinstance(document, dict) else None
        if not isinstance(proposed, list):
            return tuple(dict(row) for row in rejected)
        return tuple(dict(row) for row in proposed if isinstance(row, dict))

    def _correct_semantic_review(
        self,
        objective: str,
        offered: list[dict[str, Any]],
        anchors: Sequence[Mapping[str, Any]],
        rejected: Any,
        issues: Sequence[str],
    ) -> dict[str, Any] | None:
        """One bounded repair of the REVIEW's own representation.

        Nothing semantic is reconsidered here. The Founder obligations are
        trusted, the requirements stand as proposed, and the reviewer is
        asked only to restate its mapping in a form the caller can read --
        the fault live Probe #2 hit when it answered in 0-based indices.
        """
        import json

        try:
            shown = json.dumps(rejected, indent=2, ensure_ascii=False)[:12000]
        except Exception:  # noqa: BLE001
            shown = repr(rejected)[:12000]
        prompt = (
            "Your previous semantic-review response could not be read by "
            "the caller. Do not reconsider the Founder's meaning, the "
            "obligation anchors or the proposed requirements -- only "
            "restate your mapping so it is machine-readable.\n\n"
            "THE REQUIREMENTS, WITH THE ONLY INDICES YOU MAY USE:\n"
            + json.dumps(
                [{"requirement_index": index, "description": row.get("description")}
                 for index, row in enumerate(offered, start=1)],
                indent=2, ensure_ascii=False,
            )
            + "\n\nTRUSTED FOUNDER OBLIGATION ANCHORS:\n"
            + json.dumps(
                [{"anchor_id": a.get("anchor_id"), "meaning": a.get("meaning")}
                 for a in anchors], indent=2, ensure_ascii=False,
            )
            + "\n\nYOUR PREVIOUS RESPONSE:\n" + shown
            + "\n\nIt was rejected for these exact reasons:\n"
            + "\n".join(f"    - {issue}" for issue in issues)
            + "\n\nrequirement_indices are 1-BASED and must be drawn from "
            "the requirement_index values listed above. There is no index "
            "0. Every anchor_id must be copied exactly from the trusted "
            "anchors above.\n\n"
            "Return JSON only with this exact shape:\n"
            '{"valid": true, "independently_verifiable": true, '
            '"coverage": [{"anchor_id": "...", '
            '"requirement_indices": [1], "independently_trackable": true}], '
            '"invented": [{"requirement_index": 1, "reason": "..."}]}'
        )
        document = self._reasoned_json(
            prompt, requester="brain_semantic_review_correction",
        )
        if isinstance(document, dict) and anchors:
            document = dict(document)
            document["anchors"] = [dict(anchor) for anchor in anchors]
        return document

    def _semantic_integrity_review(
        self,
        objective: str,
        offered: list[dict[str, Any]],
        anchors: Sequence[Mapping[str, Any]] = (),
    ) -> dict[str, Any] | None:
        """Map an ALREADY TRUSTED obligation set onto a decomposition.

        Stage 1C establishes the anchors upstream, blind to this
        decomposition, so this reviewer is no longer asked to invent them.
        It answers one question: which proposed requirements expose each
        obligation's state. The trusted anchors are re-attached to the
        response afterwards, so the Stage 1B deterministic decision reads
        the Founder's obligation set and not a re-derived one.
        """
        import json

        source_regions = _source_coverage_regions(objective)
        prompt = (
            "Act as the semantic admission reviewer inside an Intent Layer. "
            "Project the Founder's obligations onto a proposed canonical "
            "decomposition. Do not plan execution or improve the objective.\n\n"
            f"FOUNDER INPUT:\n{objective}\n\n"
            "SOURCE REGIONS (coverage only; they are not pre-decided "
            "obligations):\n"
            + json.dumps(source_regions, indent=2, ensure_ascii=False)
            + "\n\nTRUSTED FOUNDER OBLIGATION ANCHORS (already established "
            "and independently audited upstream; use them as given, do not "
            "add, remove or restate them):\n"
            + json.dumps(list(anchors), indent=2, ensure_ascii=False)
            # Each row carries the ONLY index that may refer to it. The
            # convention is machine-readable rather than described in
            # prose, because a reviewer that answered 0-based cost a live
            # mission and prose had not prevented it.
            + "\n\nPROPOSED REQUIREMENTS (refer to these by "
            "requirement_index; the numbering is 1-based and there is no "
            "index 0):\n"
            + json.dumps(
                [{"requirement_index": index, **row}
                 for index, row in enumerate(offered, start=1)],
                indent=2, ensure_ascii=False,
            )
            + "\n\nUse the anchors exactly as given. For reference, an "
            "Founder input. An anchor is a grounded source span plus one "
            "independently stateful meaning that must survive transformation. "
            "If one state can be SATISFIED while another remains UNRESOLVED or "
            "BLOCKED, they are separate anchors. If one state produces the "
            "entity consumed by another, name that prerequisite in depends_on. "
            "Do not create anchors from implementation steps, sentence count, "
            "verbs, commas or the word 'and'. An inseparable outcome and its "
            "completion condition may be one anchor: saving and verifying one "
            "artifact may remain one deliverable, and a decision with its "
            "requested rationale may remain one informational outcome.\n\n"
            "Then map every anchor to the one-or-more proposed requirement "
            "indices that independently expose its mission state. One anchor "
            "may map to several more-precise requirements. If two anchors map "
            "to the same single-state requirement, independently_trackable must "
            "be false. A proposed requirement grounded in no anchor is invented.\n\n"
            "Return JSON only with this exact shape:\n"
            '{"valid": true, "independently_verifiable": true, '
            '"coverage": [{"anchor_id": "anchor_1", '
            '"requirement_indices": [1], "independently_trackable": true}], '
            '"invented": [{"requirement_index": 1, "reason": "..."}]}\n\n'
            "Return structured mapping only, never a reasoning transcript. "
            "The caller decides admission deterministically from the trusted "
            "anchors and your coverage; your global valid value is recorded "
            "but is not authoritative."
        )
        document = self._reasoned_json(
            prompt, requester="brain_semantic_requirement_validation",
        )
        if isinstance(document, dict) and anchors:
            # The obligation set was settled upstream. Re-attaching it here
            # means the Stage 1B decision reads the Founder's audited
            # anchors, never a set this reviewer could have reshaped to fit
            # the decomposition it is grading.
            document = dict(document)
            document["anchors"] = [dict(anchor) for anchor in anchors]
        return document

    def _correct_requirement_decomposition(
        self,
        objective: str,
        original_prompt: str,
        rejected: Any,
        issues: Sequence[str],
    ) -> Any:
        import json

        try:
            shown = json.dumps(
                {"requirements": rejected}, indent=2, ensure_ascii=False,
            )[:12000]
        except Exception:  # noqa: BLE001
            shown = repr(rejected)[:12000]
        correction = (
            f"{original_prompt}\n\nYour previous proposed decomposition was:\n"
            f"{shown}\n\nIt cannot become canonical Intent for these exact "
            "reasons:\n"
            + "\n".join(f"    - {issue}" for issue in issues)
            + "\n\nCorrect only those semantic-admission violations. Preserve "
            "the original Founder input, every unaffected obligation and its "
            "source provenance. Do not reinterpret the mission from scratch "
            "and do not add execution steps. Reply once with the original JSON "
            "shape."
        )
        document = self._reasoned_json(
            correction, requester="brain_semantic_requirements_correction",
        )
        return document.get("requirements") if isinstance(document, dict) else None


    def question_subject(self, text: str) -> str:
        """What a founder's question about this system is ABOUT.

        A closed vocabulary (`brain/self_query.QUESTION_SUBJECTS`), so the
        answer can only be one of the things this machine actually keeps
        records of.

        Asked of the Brain's existing door rather than matched against a
        phrase list, because a phrase list has a cliff edge one word away
        and a founder does not know where it is. Only the question text
        is sent -- no mission content, no file paths, no evidence -- so
        this carries none of the founder's private material.

        `OTHER` on anything unusable: no reasoner, a refusal, an
        unrecognised word. `OTHER` means "the records do not answer this",
        and the ordinary reasoning path handles it with its careful
        sensitivity default intact.
        """
        from master_agent.brain.self_query import OTHER, QUESTION_SUBJECTS

        question = (text or "").strip()
        if not question or self._reasoner is None:
            return OTHER

        from master_agent.ai_infrastructure.budgeted_request import (
            BudgetedSelectionRequest,
        )
        from master_agent.ai_infrastructure.workload import INTERACTIVE
        from master_agent.plugins.model_router import RoutingContext, SelectionRequest

        prompt = (
            "A founder is asking an assistant a question about the "
            "assistant itself.\n\n"
            f"    They asked: {question}\n\n"
            "Which ONE of these is the question about?\n\n"
            "    capabilities    - what it is able to do\n"
            "    providers       - which AI providers it can use\n"
            "    plan_rationale  - why it chose a particular tool or "
            "capability for work it did\n"
            "    outcome         - whether work it did actually satisfied "
            "what was asked\n"
            "    other           - anything else at all\n\n"
            "Reply with exactly one of those five words and nothing else."
        )
        context = RoutingContext(
            is_online=True,
            requires_strong_reasoning=False,
            capability=REASONING_CAPABILITY,
            requester="brain_question_subject",
        )
        request = BudgetedSelectionRequest(
            **vars(SelectionRequest.from_context(context)),
            request_class=INTERACTIVE,
            prompt=prompt,
        )
        try:
            outcome = self._reasoner.run(prompt, request)
        except Exception:  # noqa: BLE001 -- a dead ladder is a default, not a crash
            return OTHER
        if outcome is None or not getattr(outcome, "ok", False):
            return OTHER
        answer = (getattr(outcome, "text", "") or "").strip().lower()
        for word in answer.replace(".", " ").replace(",", " ").split():
            if word in QUESTION_SUBJECTS:
                return word
        return OTHER

    def answer_question(self, text: str) -> IntentResult:
        """A question the founder wants ANSWERED, as an Intent.

        Thinking is work, and this codebase already has a capability for
        it: `Reasoning.Transform(instruction) -> text`. So an
        informational question needs no new subsystem, no advisory layer
        and no second brain -- it is one registered capability, chosen by
        the Broker, verified by `TextVerifier`, reported like anything
        else. The Planner's ordinary one-step path plans it without a
        model, because the capability is NAMED here rather than guessed
        there.

        `answers_founder` is what makes the answer reach the founder
        instead of stopping at a Task result. It is `"text"` because that
        is the field `Reasoning.Transform` publishes; the Planner still
        checks the contract says so before promising it.

        Deliberately not routed through `parse()`. The typed parsers
        there recognise ACTIONS -- create a folder, read a file -- and a
        question is not one; adding it to that ladder would put "is this
        a question?" in a place that has no idea what came before.
        `_submit_objective` asks the Brain for the utterance's role first,
        and calls this only for the role that means it.
        """
        goal = (text or "").strip()
        facts, sources = self._grounded_facts()
        # The founder's question, with this machine's own current facts
        # attached. Not a system prompt and not a persona -- evidence,
        # so the answer is about what is true here now rather than what
        # a provider remembers about a product with this name.
        instruction = (
            f"{_GROUNDED_QUESTION.format(facts=facts, question=goal)}"
            if facts else goal
        )
        context: dict[str, Any] = {"raw_input": goal}
        if sources:
            # Kept for the audit trail, not shown to the founder: which
            # internal fact sources this answer was allowed to rely on.
            context["grounding_sources"] = list(sources)
        return self._with_roles(
            IntentResult(
                intent=Intent(
                    goal=goal,
                    constraints=[],
                    context=context,
                    # Stated, and checkable: the founder asked something
                    # and an answer either exists or it does not.
                    success_criteria=["A reasoned answer to the question is produced."],
                    capability=_TRANSFORM_CAPABILITY,
                    payload={"instruction": instruction},
                    answers_founder=_TRANSFORM_ANSWER_FIELD,
                ),
                raw_input=goal,
            ),
            goal,
        )

    def _grounded_facts(self) -> tuple[str, tuple[str, ...]]:
        """This machine's current facts, and which sources supplied them.

        `("", ())` when nothing is wired, which is every test that does
        not care and the honest state of a layer with no grounding
        source: the question still travels, ungrounded, exactly as before
        this existed.
        """
        if self._grounding is None:
            return "", ()
        try:
            facts = self._grounding()
        except Exception:  # noqa: BLE001 -- grounding is evidence, not control flow
            return "", ()
        if not isinstance(facts, Mapping) or not facts:
            return "", ()
        rendered = "\n\n".join(
            f"{name}:\n{value}" for name, value in facts.items() if value
        )
        return rendered, tuple(facts)

    def _with_roles(self, result: IntentResult, text: str) -> IntentResult:
        """Stamp derived agency and semantic requirements onto whatever a
        parser produced.

        Applied HERE rather than inside each of the twelve parsers: agency
        is a property of the founder's sentence, not of which action the
        sentence happened to name, so deriving it once at the one entry
        point keeps a single implementation and makes it impossible for a
        new parser to be added without it. Requirements are stamped in the
        same place, for the same reason.

        **Only what is free.** A typed intent already knows its effect and
        its constraints, and a question already knows what must be
        answered; both are derived from what the parser produced, with no
        provider involved. Generic prose is left with no requirements
        here: extracting them would cost a call on every objective, and
        the deterministic planner is about to read the same sentence
        clause by clause anyway. It attaches them from what it compiled.

        A clarification result carries no `Intent` to stamp and is returned
        untouched -- there is no agency to preserve on a question.
        """
        if result.intent is None:
            return result
        if not getattr(result.intent, "requirements", ()) and (
            getattr(result.intent, "capability", "")
            or getattr(result.intent, "answers_founder", "")
        ):
            # Only what costs nothing HERE.
            #
            # A capability-bearing intent derives its requirements
            # deterministically, so it is free and belongs at parse
            # time. A compound objective needs the reasoning door, and
            # `parse()` must never reach a provider -- it is a
            # structural operation on every path, including the ones a
            # founder never sees. `MissionService._admit` derives the
            # rest, once per mission, at the admission boundary that
            # already owns the semantic gate.
            #
            # This was gated on the intent carrying a `capability` or
            # `answers_founder`, which excluded exactly the objectives
            # that most need requirements: the compound natural ones the
            # AI Planner handles. `_reasoned_requirements` was written
            # for that case and was unreachable for it.
            #
            # Measured on the failed founder acceptance -- "search for
            # action rpg games released in 2026 and give me free demo
            # download links" produced a ten-step plan whose
            # `requirements` list was EMPTY and whose every step carried
            # `covers=[]`. Outcome conformance over an empty requirement
            # set can only ever answer UNKNOWN, so a research mission
            # could not be judged against founder intent even when it
            # worked.
            #
            result.intent.requirements = self.requirements_for(
                result.intent, raw=text
            )
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
        evidence: Mapping[str, Mapping[str, str]] | None = None,
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
            # What the founder said for each field ALREADY settled. The
            # turns before this one are part of the record too.
            said: dict[str, dict[str, str]] = {
                name: dict(row) for name, row in (evidence or {}).items()
            }

            # The answer is EVIDENCE, not a value.
            #
            # This line used to read `answers[question.key] = answer`, and
            # that assignment was the defect: the founder's words became a
            # capability argument without anything understanding them.
            # "on desktop" reached `Filesystem.CreateFolder` verbatim and
            # was refused, for a question the founder had answered
            # correctly.
            #
            # `understand()` reads the reply against every field this
            # parser is gathering, so one answer may settle several, and a
            # correction may revise one already given. It resolves closed
            # fields against the capability's own vocabulary, reaches the
            # Brain's reasoning door only when structure cannot, and
            # returns uncertainty rather than a guess.
            understood = self.understand(
                answer,
                gathering=question.gathering or (question.key,),
                asked=question.key,
                known=answers,
                objective=original,
                question=question.question,
            )
            if understood.uncertain:
                # Nothing was established. Ask again rather than proceed
                # on something nobody said -- accuracy over completion.
                #
                # And ask BETTER. Repeating the same words at a founder
                # who has already answered once is how a clarification
                # becomes a loop they can only escape by giving up. When
                # the field has a known set of values, saying what they
                # are turns an unanswerable question into a choice.
                asked = question.question
                vocabulary = self._vocabularies.get(question.key)
                if vocabulary:
                    places = ", ".join(
                        value.replace("_", " ") for value in sorted(vocabulary)
                    )
                    asked = (
                        f"{question.question} I can use: {places} -- "
                        f"or a folder inside one of those."
                    )
                return IntentResult(
                    clarification=ClarificationQuestion(
                        question=asked,
                        key=question.key,
                        options=question.options,
                        required=question.required,
                        gathering=question.gathering,
                    ),
                    raw_input=original,
                    resolved=dict(answers),
                    evidence=dict(said),
                )
            if question.key not in understood.fields:
                if question.key in self._vocabularies:
                    # A field whose values the capability fixes, and the
                    # founder named none of them. Passing the words
                    # through anyway is exactly the defect this replaces:
                    # it is how "on desktop" reached the capability and
                    # was refused. Ask instead.
                    return IntentResult(
                        clarification=ClarificationQuestion(
                            question=question.question,
                            key=question.key,
                            options=question.options,
                            required=question.required,
                            gathering=question.gathering,
                        ),
                        raw_input=original,
                        resolved=dict(answers),
                        evidence=dict(said),
                    )
                # An open field -- a name -- that this layer has no
                # vocabulary to check. The founder's own words are the
                # value, which is what "Research" has always been.
                answers[question.key] = answer
            for name, found in understood.fields.items():
                previous = answers.get(name, "")
                answers[name] = found.value
                said[name] = FieldEvidence(
                    value=found.value,
                    evidence=found.evidence,
                    source=found.source,
                    # A founder who changes their mind must not leave a
                    # stale value behind, and the record must show which
                    # value moved.
                    replaced=previous if previous and previous != found.value else "",
                ).as_dict()

            result = self.parse(original, supplied=answers)
            # Canonical, and carried whether this round finished the job
            # or asked another question.
            result.resolved = dict(answers)
            result.evidence = dict(said)
            if result.intent is not None:
                if said:
                    # Provenance for every field this turn established:
                    # the words it came from, whether structure or
                    # reasoning read it, and what it replaced.
                    carried = dict(result.intent.context.get("field_evidence") or {})
                    carried.update(said)
                    result.intent.context["field_evidence"] = carried
                    # Re-derive the requirements now that the founder's
                    # own words are on the Intent.
                    #
                    # `parse()` stamped them a moment ago, before this
                    # turn's evidence existed -- so they carried the
                    # resolved value and nothing else, which is exactly
                    # the circularity being removed. Derived again here,
                    # each requirement keeps what was SAID beside what it
                    # was read as.
                    result.intent.requirements = self.requirements_for(
                        result.intent, raw=original
                    )
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


#: Everything `CreateFolderIntent` needs before it can produce an Intent.
#: Declared once, and carried on every question it asks, so a founder who
#: answers "where?" with "actually call it Finance and put it in
#: Documents" has both fields read rather than one.
_FOLDER_FIELDS: tuple[str, ...] = ("folder_name", "location", "parent")

#: A folder INSIDE the named location -- "d drive in onkar folder".
#:
#: Not a new capability and not an overloaded field by accident. Source,
#: at `executor/action.py::is_unsafe_relative_path`, names
#: `CreateFolderAction`'s `name` among the arguments that are "a relative
#: path/name meant to be joined onto a configured location's base
#: directory"; `run()` does `base / name` and then
#: `mkdir(parents=True)`; and `validate()`'s own comment contemplates
#: multi-segment values like "MyProject/src" from
#: `WorkspaceBootstrapAction`. A parent folder is therefore something the
#: existing contract already expresses safely -- `..` and anchored paths
#: are rejected by the same guard.
#:
#: The parser composes it, not the Intent Layer: only the parser knows
#: what its capability's arguments mean.
PARENT = "parent"


class CreateFolderIntent(BaseIntentParser):
    r"""Parse 'create/make a folder called X [on/in Y]'.

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

    #: One structural command grammar shared by every shape below.
    #:
    #: The Intent registry deliberately routes both "create a folder" and
    #: "make a folder" here.  Keeping the verb in three separate regexes
    #: let the registry and parser disagree: the latter accepted only
    #: ``create``, so a fully specified ``make`` objective escaped as
    #: generic prose and made the Planner rediscover this typed mapping.
    #: This is grammar, not a sentence table -- verb, optional article and
    #: noun remain independent of the name and location the Founder gives.
    _COMMAND = (
        r"\b(?:(?:create|make)\s+|(?:i\s+)?need\s+)"
        r"(?:(?:a|an)\s+)?"
        r"(?:(?:new|empty)\s+)*folder"
    )

    #: The name runs to the end of the input. Used only after the
    #: with-location pattern has already failed.
    _NAME_ONLY = (
        _COMMAND
        + r"\s+(?:called|named)\s*:?\s*[\"']?(?P<name>[^\"'.!?]+?)[\"']?[.!?]?\s*$"
    )
    #: The location clause is anchored to the end, so the name group can no
    #: longer swallow it. `name` is lazy; `location` takes the last
    #: on/in clause.
    _NAME_AND_LOCATION = (
        _COMMAND
        + r"\s+(?:called|named)\s*:?\s*[\"']?(?P<name>[^\"'.!?]+?)[\"']?"
        + r"\s+(?:on|in)\s+(?:my\s+|the\s+)?(?P<location>[\w\s]+?)[.!?]?\s*$"
    )
    #: A name followed by a location reference that only the founder can
    #: resolve: ``called Notes where I normally keep these``.  The clause is
    #: evidence that location is still unknown, never a long suffix of the
    #: folder name and never permission for a Planner/model to choose a place.
    _NAME_AND_UNRESOLVED_LOCATION = (
        _COMMAND
        + r"\s+(?:called|named)\s*:?\s*[\"']?"
        r"(?P<name>[^\"'.!?]+?)[\"']?\s+where\b.+$"
    )
    #: The same complete command with the location stated first:
    #: "On Desktop, I need a folder named: Research."  Word order is
    #: language, not ambiguity; the two fields remain structurally clear.
    _LEADING_NAME_AND_LOCATION = (
        r"^\s*(?:on|in)\s+(?:my\s+|the\s+)?"
        r"(?P<location>[\w\s]+?)\s*,\s*"
        + _COMMAND
        + r"\s+(?:called|named)\s*:?\s*[\"']?"
        r"(?P<name>[^\"'.!?]+?)[\"']?[.!?]?\s*$"
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
        _COMMAND
        + r"\s+(?:on|in)\s+(?:my\s+|the\s+)?(?P<location>[\w\s]+?)[.!?]?\s*$"
    )

    @classmethod
    def recognizes(cls, text: str) -> bool:
        """Whether this sentence contains this parser's command grammar.

        The Intent registry uses broad lexical relevance while the parser
        owns meaning.  This guard is what lets the registry say merely
        ``folder`` without allowing "delete the folder" to become a create
        request.
        """
        import re

        return re.search(cls._COMMAND, text or "", re.IGNORECASE) is not None

    @classmethod
    def claim_trigger(cls, text: str) -> str:
        """The structural trigger text used by the generic claim guard."""
        import re

        found = re.search(cls._COMMAND, text or "", re.IGNORECASE)
        return found.group(0) if found else ""

    def parse(self, text: str, supplied: Mapping[str, str] | None = None) -> IntentResult:
        import re

        command = re.search(self._COMMAND, text, re.IGNORECASE)
        command_words = command.group(0) if command else ""
        must_be_new = bool(re.search(r"\bnew\b", command_words, re.IGNORECASE))
        must_be_empty = bool(re.search(r"\bempty\b", command_words, re.IGNORECASE))

        location: str | None = None
        unresolved_location = False
        match = re.search(self._LEADING_NAME_AND_LOCATION, text, re.IGNORECASE)
        if match:
            location = match.group("location").strip()
        else:
            match = re.search(self._NAME_AND_LOCATION, text, re.IGNORECASE)
        if match:
            location = location or match.group("location").strip()
        else:
            match = re.search(
                self._NAME_AND_UNRESOLVED_LOCATION, text, re.IGNORECASE
            )
            unresolved_location = match is not None
            if match is None:
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
                    gathering=_FOLDER_FIELDS,
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
            # Already canonical. `IntentLayer.understand()` resolved the
            # founder's words against this capability's own vocabulary
            # before `supplied` was built, so what arrives here is a value
            # the capability accepts -- not a phrase to be de-grammared.
            location = self._answer(supplied, "location")
        elif location.lower().endswith(" directory"):
            location = location[:-len(" directory")].rstrip()

        # A folder inside that place, when the founder named one.
        #
        # "d drive in onkar folder" means D:\Onkar\<name>, and the
        # capability expresses that today: `name` is a relative path
        # joined onto the location. Composing it here rather than in the
        # Intent Layer keeps capability knowledge with the parser that
        # owns the capability.
        parent = self._answer(supplied, PARENT)
        if parent and name:
            leaf = name.strip().strip("/\\")
            branch = parent.strip().strip("/\\").replace("\\", "/")
            if branch and leaf:
                name = f"{branch}/{leaf}"
        if location is None:
            resolved = {"folder_name": name} if unresolved_location else {}
            evidence = (
                {
                    "folder_name": FieldEvidence(
                        value=name, evidence=text, source=STATED
                    ).as_dict()
                }
                if unresolved_location else {}
            )
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
                    gathering=_FOLDER_FIELDS,
                ),
                raw_input=text,
                resolved=resolved,
                evidence=evidence,
            )

        context: dict[str, Any] = {
            "folder_name": name,
            "location": location,
            "field_evidence": {
                "folder_name": FieldEvidence(
                    value=name, evidence=text, source=STATED
                ).as_dict(),
                "location": FieldEvidence(
                    value=location, evidence=text, source=STATED
                ).as_dict(),
            },
        }
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
        if must_be_new:
            payload["must_be_new"] = True
            context["field_evidence"]["must_be_new"] = FieldEvidence(
                value=True, evidence=text, source=STATED
            ).as_dict()
        if must_be_empty:
            payload["must_be_empty"] = True
            context["field_evidence"]["must_be_empty"] = FieldEvidence(
                value=True, evidence=text, source=STATED
            ).as_dict()

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


#: Everything `CreateProjectIntent` gathers. One field today; declared
#: the same way so a second one costs a constant rather than a rewrite.
_PROJECT_FIELDS: tuple[str, ...] = ("project_name",)


class CreateProjectIntent(BaseIntentParser):
    """Parse 'create a [type] project called X'."""

    @staticmethod
    def recognizes(text: str) -> bool:
        """Only project/application language belongs to this parser."""
        import re

        return re.search(r"\b(?:project|application)\b", text or "", re.IGNORECASE) is not None

    def parse(self, text: str, supplied: Mapping[str, str] | None = None) -> IntentResult:
        import re
        match = re.search(
            r"create\s+(?:a\s+new\s+|a\s+|an\s+|new\s+)?(?:(?P<type>[A-Za-z][\w.+#-]*)\s+)?(?:project|application)\s+(?:called|named)\s+[\"']?([^\"'.]+)[\"']?\.?\s*$",
            text,
            re.IGNORECASE,
        )
        if not match:
            # No project pattern at all -- but a name may have arrived
            # from an earlier round, and re-asking for something the
            # founder already gave is the loop this whole correction
            # exists to end.
            answered = self._answer(supplied, "project_name")
            if answered:
                return self.parse(
                    f"create a project called {answered}", supplied=supplied
                )
            return IntentResult(
                clarification=ClarificationQuestion(
                    question="What should the project be called?",
                    key="project_name",
                    required=True,
                    gathering=_PROJECT_FIELDS,
                ),
                raw_input=text,
            )

        project_type = (match.group("type") or "generic").strip().lower()
        name = match.group(2).strip()

        if not name:
            # The founder may already have answered this exact question.
            # Read like every other resolved field -- this parser asked
            # for it, so this parser reads it.
            name = self._answer(supplied, "project_name") or ""

        if not name:
            return IntentResult(
                clarification=ClarificationQuestion(
                    question="What should the project be called?",
                    key="project_name",
                    required=True,
                    gathering=_PROJECT_FIELDS,
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
        answered = self._answer(supplied, "file_path")
        if not match and not answered:
            return IntentResult(
                clarification=ClarificationQuestion(
                    question="Which file should I read?",
                    key="file_path",
                    required=True,
                    gathering=("file_path",),
                ),
                raw_input=text,
            )

        path = answered or match.group("path").strip()
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


#: Everything `ListDirectoryIntent` gathers -- one field, and it shares
#: the closed vocabulary `CreateFolderIntent` uses, which is what makes
#: this a proof that the correction is shared rather than folder-shaped.
_LIST_FIELDS: tuple[str, ...] = ("location",)


class ListDirectoryIntent(BaseIntentParser):
    """Parse 'list files inside X'."""

    def parse(self, text: str, supplied: Mapping[str, str] | None = None) -> IntentResult:
        import re
        match = re.search(
            r"^list\s+(?:the\s+)?files\s+(?:inside|in|on)\s+(?:my\s+|the\s+)?(?P<location>[\w\s]+?)\.?\s*$",
            text,
            re.IGNORECASE,
        )
        answered = self._answer(supplied, "location")
        if not match and not answered:
            return IntentResult(
                clarification=ClarificationQuestion(
                    question="Which folder should I list?",
                    key="location",
                    required=True,
                    gathering=_LIST_FIELDS,
                ),
                raw_input=text,
            )

        # An answer resolved against the capability's vocabulary beats a
        # phrase scraped out of the original sentence: it is already the
        # value the capability accepts, and it is the more recent thing
        # the founder said.
        raw_location = answered or match.group("location").strip()
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
        # The founder may already have answered this exact question. Taken
        # as the value rather than round-tripped through the pattern
        # above: an answer is not a command, and re-parsing it as one is
        # how a parser asks the same question forever.
        answered = self._answer(supplied, "pattern")
        if not match and not answered:
            return IntentResult(
                clarification=ClarificationQuestion(
                    question="What should I search for?",
                    key="pattern",
                    required=True,
                    gathering=("pattern",),
                ),
                raw_input=text,
            )

        pattern = answered or match.group("pattern").strip()
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
