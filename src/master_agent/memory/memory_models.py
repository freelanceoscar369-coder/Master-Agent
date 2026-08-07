"""What a founder memory *is* (Mission Brief 034).

Kalpavriksha already remembers what it is doing. This is what it
remembers about *the founder* — preferences, decisions, what worked, what
did not — and it survives a restart.

**This is not an LLM memory.** Nothing here is summarised by a model,
embedded, or recalled by similarity. A record is a fact somebody stated or
something the system observed, stored verbatim and retrieved
deterministically. MB034 forbids the alternative in eight separate words,
and the reason is one sentence: a memory that can be *approximately*
recalled is a memory that can be confidently wrong, and a founder cannot
audit a vector.

`memory/` already held MB004's Layers 1-3 (conversation, mission,
persistent mission history). This is Layer 4 — the "durable facts distinct
from mission history" that `memory/future.py` reserved — arriving with a
richer contract than the two-method sketch there anticipated. That sketch
is left untouched rather than retrofitted; MB034 specifies the shape, and
two shapes for one idea is worse than one superseded stub.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any

# ---- categories: exactly the ten MB034 names, and no others -------------

FOUNDER_PREFERENCES = "Founder Preferences"
BUSINESS_DECISIONS = "Business Decisions"
ARCHITECTURE_DECISIONS = "Architecture Decisions"
PROJECT_KNOWLEDGE = "Project Knowledge"
MISSION_OUTCOMES = "Mission Outcomes"
PROMPT_LIBRARY = "Prompt Library"
FAILURE_LIBRARY = "Failure Library"
SUCCESS_LIBRARY = "Success Library"
RECURRING_LESSONS = "Recurring Lessons"
OPEN_QUESTIONS = "Open Questions"

CATEGORIES: tuple[str, ...] = (
    FOUNDER_PREFERENCES,
    BUSINESS_DECISIONS,
    ARCHITECTURE_DECISIONS,
    PROJECT_KNOWLEDGE,
    MISSION_OUTCOMES,
    PROMPT_LIBRARY,
    FAILURE_LIBRARY,
    SUCCESS_LIBRARY,
    RECURRING_LESSONS,
    OPEN_QUESTIONS,
)

# ---- importance ---------------------------------------------------------

LOW = "LOW"
NORMAL = "NORMAL"
HIGH = "HIGH"
CRITICAL = "CRITICAL"
IMPORTANCE: tuple[str, ...] = (LOW, NORMAL, HIGH, CRITICAL)

#: Rank, so "most important first" is one sort key rather than a lookup
#: every caller re-invents.
IMPORTANCE_RANK = {value: index for index, value in enumerate(IMPORTANCE)}

# ---- sources ------------------------------------------------------------

FOUNDER = "Founder"
MISSION = "Mission"
VERIFICATION = "Verification"
EXECUTIVE = "Executive"
BROKER = "Broker"
RECOVERY = "Recovery"
SOURCES: tuple[str, ...] = (FOUNDER, MISSION, VERIFICATION, EXECUTIVE, BROKER, RECOVERY)

#: How long a derived summary may be before it is cut at a word boundary.
SUMMARY_LIMIT = 160

_TOKEN = re.compile(r"[a-z0-9]+")

#: Words that match everything and therefore distinguish nothing. Kept
#: deliberately tiny: an aggressive stop list makes `memory "the broker"`
#: silently ignore half of what was typed.
STOPWORDS = frozenset(
    {"the", "a", "an", "and", "or", "of", "to", "in", "is", "it", "for", "on", "was"}
)


class InvalidMemory(Exception):
    """A record that could not be stored, and why. Raised at creation
    rather than discovered at retrieval: a memory with no title or an
    invented category is a bug in whoever wrote it, and storing it would
    put that bug beyond reach of the person who could fix it."""


def normalise_tags(tags: Any) -> tuple[str, ...]:
    """Lower-cased, de-duplicated, sorted.

    Sorted so two records tagged the same way in a different order are
    identical records — which is what makes duplicate suppression and
    deterministic ordering possible at all.
    """
    cleaned = {
        str(tag).strip().lower().replace(" ", "-")
        for tag in (tags or ())
        if str(tag).strip()
    }
    return tuple(sorted(cleaned))


def tokenise(text: str) -> tuple[str, ...]:
    """The words a search can match, in order of first appearance.

    Deterministic and dull on purpose: lower-case, split on anything that
    is not a letter or digit, drop single characters and a very short stop
    list. No stemming — "fail" not matching "failure" is a surprise a
    founder can see and work around; a stemmer matching the wrong thing is
    one they cannot.
    """
    seen: dict[str, None] = {}
    for match in _TOKEN.findall((text or "").lower()):
        if len(match) > 1 and match not in STOPWORDS:
            seen.setdefault(match, None)
    return tuple(seen)


def derive_summary(full_text: str, limit: int = SUMMARY_LIMIT) -> str:
    """A summary when none was given: the first sentence, or the first
    `limit` characters cut at a word boundary.

    **This is truncation, not summarisation.** Nothing is rephrased,
    nothing is inferred, and no model is asked. MB034 forbids LLM
    summarisation; taking the founder's own opening words is the honest
    alternative, and the full text is always there underneath.
    """
    text = " ".join((full_text or "").split())
    if not text:
        return ""
    # `". "` rather than `"."`: a decimal is not a sentence break, and the
    # first version of this turned "quality floor exceeds 0.9" into
    # "quality floor exceeds 0.9." -- a full stop the founder did not type.
    sentence, separator, _rest = text.partition(". ")
    if separator and len(sentence) <= limit:
        return f"{sentence}."
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return f"{cut}..."


@dataclass(frozen=True)
class MemoryRecord:
    """One thing Kalpavriksha knows. Frozen: a memory describes something
    that was true when it was written, and editing one in place would make
    `updated_at` a lie."""

    id: str
    category: str
    title: str
    summary: str = ""
    full_text: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    tags: tuple[str, ...] = ()
    source: str = FOUNDER
    importance: str = NORMAL
    #: How sure this is, 0..1. `1.0` for anything the founder stated or the
    #: system observed happening — which, in this build, is everything.
    #: The field exists for inferred records (a recurring lesson drawn from
    #: several failures), and nothing infers yet.
    confidence: float = 1.0
    #: Ids of other records. A graph, stored as ids and nothing else --
    #: MB034 is explicit that there is no graph database, and an id list
    #: needs no migration when the store changes shape.
    related_items: tuple[str, ...] = ()

    @property
    def rank(self) -> int:
        return IMPORTANCE_RANK.get(self.importance, 0)

    @property
    def is_critical(self) -> bool:
        return self.importance == CRITICAL

    @property
    def text(self) -> str:
        """Everything worth searching, as one string."""
        return " ".join(part for part in (self.title, self.summary, self.full_text) if part)

    def digest(self) -> str:
        """A fingerprint of *what this record says*, for duplicate
        suppression.

        Deliberately excludes tags, importance and timestamps: saying the
        same thing again with a new tag is the same memory, and storing it
        twice would make "how many things do I know" a count of how often
        the founder repeated themselves.
        """
        payload = "\x00".join(
            (
                self.category,
                " ".join(self.title.lower().split()),
                " ".join((self.full_text or self.summary).lower().split()),
            )
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def tokens(self) -> tuple[str, ...]:
        return tokenise(self.text)

    def with_update(self, **changes: Any) -> MemoryRecord:
        """A changed copy, stamped. The only way a record changes."""
        changes.setdefault("updated_at", datetime.now(UTC))
        if "tags" in changes:
            changes["tags"] = normalise_tags(changes["tags"])
        if "related_items" in changes:
            changes["related_items"] = _ids(changes["related_items"])
        return replace(self, **changes)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "title": self.title,
            "summary": self.summary,
            "full_text": self.full_text,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "tags": list(self.tags),
            "source": self.source,
            "importance": self.importance,
            "confidence": self.confidence,
            "related_items": list(self.related_items),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryRecord:
        return cls(
            id=str(data["id"]),
            category=data["category"],
            title=data["title"],
            summary=data.get("summary", ""),
            full_text=data.get("full_text", ""),
            created_at=_when(data.get("created_at")),
            updated_at=_when(data.get("updated_at")),
            tags=normalise_tags(data.get("tags")),
            source=data.get("source", FOUNDER),
            importance=data.get("importance", NORMAL),
            confidence=float(data.get("confidence", 1.0)),
            related_items=_ids(data.get("related_items")),
        )


def build(
    id: str,
    category: str,
    title: str,
    summary: str = "",
    full_text: str = "",
    tags: Any = (),
    source: str = FOUNDER,
    importance: str = NORMAL,
    confidence: float = 1.0,
    related_items: Any = (),
    now: datetime | None = None,
) -> MemoryRecord:
    """Build a valid record, or refuse.

    Validation lives here rather than in `MemoryRecord.__post_init__` so
    that a record read back from disk is never rejected by a rule added
    after it was written — history should not become unreadable because
    the vocabulary grew.
    """
    if category not in CATEGORIES:
        raise InvalidMemory(
            f"unknown category '{category}' (known: {', '.join(CATEGORIES)})"
        )
    if importance not in IMPORTANCE:
        raise InvalidMemory(
            f"unknown importance '{importance}' (known: {', '.join(IMPORTANCE)})"
        )
    if source not in SOURCES:
        raise InvalidMemory(f"unknown source '{source}' (known: {', '.join(SOURCES)})")

    clean_title = " ".join((title or "").split())
    if not clean_title:
        raise InvalidMemory("a memory with no title cannot be found again")

    body = (full_text or "").strip() or clean_title
    stamp = now or datetime.now(UTC)
    return MemoryRecord(
        id=id,
        category=category,
        title=clean_title,
        summary=" ".join((summary or "").split()) or derive_summary(body),
        full_text=body,
        created_at=stamp,
        updated_at=stamp,
        tags=normalise_tags(tags),
        source=source,
        importance=importance,
        confidence=min(1.0, max(0.0, float(confidence))),
        related_items=_ids(related_items),
    )


def _ids(values: Any) -> tuple[str, ...]:
    """Related ids, de-duplicated and sorted — a link is a fact, not an
    ordering."""
    return tuple(sorted({str(value) for value in (values or ()) if str(value).strip()}))


def _when(value: Any) -> datetime:
    if not value:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(str(value))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
