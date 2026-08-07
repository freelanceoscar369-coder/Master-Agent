"""Founder Memory — the one door in and out (Mission Brief 034).

```
    founder: remember "..."  ─┐
    Mission Control events ───┼─> MemoryService ─> knowledge.json
    launcher: recovery ──────┘          │
                                        └─> MemoryQuery ─> memory <words>
```

Three things worth stating, because each one is a rule rather than an
implementation detail:

**Automatic memory rides the existing event stream.** The service
subscribes to the Event Bus Mission Control already publishes on — the
same door `PersistenceService` uses — so nothing new observes anything.
It subscribes *per event type* rather than to everything and filtering:
the Runtime publishes a heartbeat every cycle, and a memory system that
had to ignore most of what it saw would eventually stop ignoring one.

**Saying the same thing twice is one memory.** A write whose content
digest already exists updates that record instead of adding another —
otherwise "how many things do I know" becomes a count of how often the
founder repeated themselves, and the Dashboard's total stops meaning
anything.

**Nothing is inferred.** A record is what somebody stated or what the
system observed. There is no summarisation, no similarity, and no model
call anywhere in this package (a test asserts it), so a memory can be
wrong only if the fact it recorded was wrong.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from master_agent.memory.knowledge_store import LoadReport
from master_agent.memory.memory_index import MemoryIndex
from master_agent.memory.memory_models import (
    ARCHITECTURE_DECISIONS,
    BUSINESS_DECISIONS,
    CRITICAL,
    FAILURE_LIBRARY,
    FOUNDER,
    FOUNDER_PREFERENCES,
    HIGH,
    MISSION,
    MISSION_OUTCOMES,
    NORMAL,
    PROJECT_KNOWLEDGE,
    PROMPT_LIBRARY,
    RECOVERY,
    SUCCESS_LIBRARY,
    VERIFICATION,
    MemoryRecord,
    build,
    derive_summary,
    normalise_tags,
)
from master_agent.memory.memory_query import DEFAULT_LIMIT, MemoryQuery, SearchHit

ID_PREFIX = "mem-"
ID_WIDTH = 6

#: What `remember "..."` files things under when the founder does not say.
#: Preferences rather than Project Knowledge because that is what a founder
#: typing a bare sentence at a prompt is almost always stating -- and the
#: category is one word away on the same command.
DEFAULT_CATEGORY = FOUNDER_PREFERENCES

#: How many titles the Dashboard's "Recent Learnings" shows, and how many
#: tags "Top Tags" does. Small: a founder page is read at a glance.
RECENT_SHOWN = 3
TOP_TAGS_SHOWN = 5


@dataclass(frozen=True)
class MemoryWrite:
    """The result of remembering something. `created` is False when this
    updated an existing record rather than adding one — the caller usually
    wants to say which happened."""

    record: MemoryRecord
    created: bool = True

    @property
    def id(self) -> str:
        return self.record.id


@dataclass(frozen=True)
class MemorySummary:
    """What the Dashboard's MEMORY section shows (MB034). Plain counts and
    titles, resolved here so no renderer has to compute anything."""

    total: int = 0
    critical: int = 0
    recent: tuple[MemoryRecord, ...] = ()
    top_tags: tuple[tuple[str, int], ...] = ()
    last_written: MemoryRecord | None = None
    by_category: tuple[tuple[str, int], ...] = ()
    problems: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "critical": self.critical,
            "recent": [r.title for r in self.recent],
            "top_tags": [{"tag": tag, "count": count} for tag, count in self.top_tags],
            "last_written": self.last_written.title if self.last_written else None,
            "by_category": [
                {"category": name, "count": count} for name, count in self.by_category
            ],
            "problems": list(self.problems),
        }


class MemoryService:
    """Everything Kalpavriksha knows about the founder, and how to ask.

    `store` is optional only so a test can run without one; the launcher
    always gives it a `JsonKnowledgeStore`, because a memory that does not
    survive a restart is not a memory.
    """

    def __init__(self, store: Any = None, clock: Any = None) -> None:
        self._store = store
        self._clock = clock or (lambda: datetime.now(UTC))
        self._records: dict[str, MemoryRecord] = {}
        self._index = MemoryIndex()
        self._sequence = 0
        self._last_written: str | None = None
        #: objective id -> the description it was submitted with. Process-
        #: local and deliberately not persisted: it exists only to name a
        #: memory at the moment one is written, and a stale name from a
        #: previous run would be worse than an id.
        self._objective_names: dict[str, str] = {}
        self.duplicates_suppressed = 0
        self.write_failures: list[str] = []
        self.load_report: LoadReport | None = None

    # ---- lifecycle --------------------------------------------------------

    def load(self) -> LoadReport:
        """Read what is on disk. Safe to call on an empty machine."""
        if self._store is None:
            return LoadReport(index=MemoryIndex())
        report = self._store.load()
        self._records = {record.id: record for record in report.records}
        self._index = report.index or MemoryIndex.build(report.records)
        self._sequence = max((_number(i) for i in self._records), default=0)
        self._last_written = max(
            self._records.values(), key=lambda r: (r.updated_at, r.id), default=None
        )
        self._last_written = self._last_written.id if self._last_written else None
        self.load_report = report
        return report

    def save(self) -> None:
        """Never raises. A disk that will not take a memory is a recording
        problem; turning it into a failed mission would be the tail wagging
        the dog, the same posture the decision ledger takes."""
        if self._store is None:
            return
        try:
            self._store.save(self.all(), self._index)
        except Exception as exc:  # noqa: BLE001 - see docstring
            self.write_failures.append(str(exc))

    # ---- writing ----------------------------------------------------------

    def remember(
        self,
        text: str,
        category: str = DEFAULT_CATEGORY,
        tags: Any = (),
        importance: str = NORMAL,
        source: str = FOUNDER,
        title: str = "",
        related_items: Any = (),
        confidence: float = 1.0,
    ) -> MemoryWrite:
        """The founder's `remember "..."`: one sentence in, one record out.

        The title is the sentence itself (trimmed at a word boundary if it
        is long) and the full text is kept verbatim. Nothing rephrases it —
        a founder searching for the words they typed should find them.
        """
        body = " ".join((text or "").split())
        return self.write(
            category=category,
            title=title or derive_summary(body, limit=80),
            full_text=body,
            tags=tags,
            importance=importance,
            source=source,
            related_items=related_items,
            confidence=confidence,
        )

    def write(
        self,
        category: str,
        title: str,
        summary: str = "",
        full_text: str = "",
        tags: Any = (),
        importance: str = NORMAL,
        source: str = FOUNDER,
        related_items: Any = (),
        confidence: float = 1.0,
    ) -> MemoryWrite:
        """Store a record, or fold it into the one that already says this.

        The full-control door. `remember()` is the founder-shaped one.
        """
        candidate = build(
            id=self._peek_id(),
            category=category,
            title=title,
            summary=summary,
            full_text=full_text,
            tags=tags,
            source=source,
            importance=importance,
            confidence=confidence,
            related_items=related_items,
            now=self._clock(),
        )

        existing_id = self._index.duplicate_of(candidate.digest())
        if existing_id is not None and existing_id in self._records:
            return MemoryWrite(self._merge(existing_id, candidate), created=False)

        record = candidate.with_update(
            id=self._take_id(), updated_at=candidate.created_at
        )
        self._records[record.id] = record
        self._index.add(record)
        self._last_written = record.id
        self.save()
        return MemoryWrite(record, created=True)

    def _merge(self, existing_id: str, candidate: MemoryRecord) -> MemoryRecord:
        """Fold a repeat into the record it repeats.

        Tags and links are unioned and importance can only go *up*: saying
        something again never makes it matter less, and a founder repeating
        a fact is usually emphasising it.
        """
        self.duplicates_suppressed += 1
        existing = self._records[existing_id]
        merged = existing.with_update(
            tags=normalise_tags(set(existing.tags) | set(candidate.tags)),
            related_items=set(existing.related_items) | set(candidate.related_items),
            importance=(
                candidate.importance
                if candidate.rank > existing.rank
                else existing.importance
            ),
            updated_at=candidate.created_at,
        )
        self._index.replace(existing, merged)
        self._records[merged.id] = merged
        self._last_written = merged.id
        self.save()
        return merged

    def link(self, from_id: str, to_id: str) -> MemoryRecord | None:
        """Point one memory at another. Stored one way, walked both ways —
        `related()` reads the backlink index, so there is no second edge to
        keep in step."""
        record = self._records.get(from_id)
        if record is None or to_id not in self._records or to_id == from_id:
            return None
        linked = record.with_update(
            related_items=set(record.related_items) | {to_id},
            updated_at=self._clock(),
        )
        self._index.replace(record, linked)
        self._records[linked.id] = linked
        self.save()
        return linked

    # ---- automatic memory --------------------------------------------------

    def attach_to(self, mission_control: Any) -> tuple[str, ...]:
        """Subscribe to the events worth remembering, and only those.

        Returns the event types subscribed to, so the launcher can report
        what is being watched rather than claiming "memory is on".
        """
        from master_agent.mission_control.events import EventType

        wiring = (
            (EventType.OBJECTIVE_SUBMITTED, self._on_objective_submitted),
            (EventType.OBJECTIVE_COMPLETED, self._on_objective_completed),
            (EventType.OBJECTIVE_FAILED, self._on_objective_failed),
            (EventType.VERIFICATION_COMPLETED, self._on_verification),
            (EventType.APPROVAL_GRANTED, self._on_approval),
            (EventType.APPROVAL_DENIED, self._on_approval),
        )
        for event_type, handler in wiring:
            mission_control.bus.subscribe(handler, event_type)
        return tuple(event_type.value for event_type, _ in wiring)

    def _on_objective_submitted(self, event: Any) -> None:
        """Learns the mission's *name*, and writes nothing.

        `OBJECTIVE_COMPLETED` carries only an id — so without this, every
        mission memory would be titled "Mission completed:
        a43de263-d959-46f7…", which is a fact about a UUID rather than
        about the founder's work. Found by reading the first one.

        Submission itself is deliberately not a memory: a mission that was
        started is not an outcome, and remembering intentions alongside
        results would make the Mission Outcomes category untrustworthy.
        """
        description = (event.payload or {}).get("description")
        if event.objective_id and description:
            self._objective_names[event.objective_id] = str(description)

    def _name_of(self, event: Any) -> str:
        """The mission's description if this process saw it submitted, and
        the id if it did not — a mission recovered from a previous run has
        no submission event on this bus, and an id is still better than
        nothing to search for."""
        return self._objective_names.get(event.objective_id or "") or str(
            event.objective_id or "unknown objective"
        )

    def _on_objective_completed(self, event: Any) -> None:
        self.write(
            category=MISSION_OUTCOMES,
            title=f"Mission completed: {self._name_of(event)}",
            full_text=(
                f"Objective {event.objective_id} completed successfully "
                f"({(event.payload or {}).get('task_count', 'unknown')} task(s))."
            ),
            tags=("mission", "completed"),
            source=MISSION,
        )

    def _on_objective_failed(self, event: Any) -> None:
        self.write(
            category=FAILURE_LIBRARY,
            title=f"Mission failed: {self._name_of(event)}",
            full_text=event.error or f"Objective {event.objective_id} failed.",
            tags=("mission", "failed"),
            importance=HIGH,
            source=MISSION,
        )

    def _on_verification(self, event: Any) -> None:
        """A verdict is the strongest evidence this system produces
        (ADR-0011), so both halves are worth keeping: what worked goes to
        the Success Library, what did not goes to the Failure Library at a
        higher importance, because the failures are what change behaviour.
        """
        payload = event.payload or {}
        verdict = str(payload.get("verdict") or "unknown")
        capability = event.capability or "unknown capability"
        matched = verdict == "matched"
        self.write(
            category=SUCCESS_LIBRARY if matched else FAILURE_LIBRARY,
            title=f"Verification {verdict}: {capability}",
            full_text=(
                f"Capability {capability} verified with verdict '{verdict}'"
                + (f" (evidence {payload['evidence_id']})" if payload.get("evidence_id") else "")
                + (f". {event.error}" if event.error else ".")
            ),
            tags=("verification", verdict, capability.split(".")[0].lower()),
            importance=NORMAL if matched else HIGH,
            source=VERIFICATION,
        )

    def _on_approval(self, event: Any) -> None:
        """What the founder decided, and about what. Filed under Business
        Decisions because that is what an approval is — the founder
        choosing to spend something, or not."""
        from master_agent.mission_control.events import EventType

        payload = event.payload or {}
        granted = event.event_type is EventType.APPROVAL_GRANTED
        capability = event.capability or payload.get("capability") or "unknown"
        decided_by = payload.get("decided_by") or "founder"
        self.write(
            category=BUSINESS_DECISIONS,
            title=f"{'Approved' if granted else 'Rejected'}: {capability}",
            full_text=(
                f"{decided_by} {'approved' if granted else 'rejected'} {capability}. "
                f"{payload.get('reason') or payload.get('impact') or ''}".strip()
            ),
            tags=("approval", "granted" if granted else "rejected"),
            importance=HIGH,
            source=FOUNDER,
        )

    def remember_recovery(self, report: Any) -> MemoryWrite | None:
        """Called by the launcher, because recovery is not an event.

        `recover()` runs before recording starts (MB025 wires it that way
        deliberately), so there is nothing on the bus to subscribe to and
        the composition root hands the report in — the same shape the
        Dashboard gets it in.
        """
        if report is None or not getattr(report, "recovered", False):
            return None

        objectives = getattr(report, "objectives", 0) or 0
        quarantined = getattr(report, "quarantined_tasks", 0) or 0
        if not objectives and not quarantined:
            # A restart that recovered *nothing* is not a learning. Found
            # by reading a live founder page: an empty snapshot still
            # counts as `recovered`, so every launch wrote "Recovered 0
            # objective(s)" and that one line then owned Recent Learnings,
            # Top Tags and Last Written -- pushing everything the founder
            # actually said below it.
            return None

        return self.write(
            category=PROJECT_KNOWLEDGE,
            title=f"Recovered {getattr(report, 'objectives', 0)} objective(s) from {getattr(report, 'source', 'storage')}",
            full_text=(
                f"A restart recovered {getattr(report, 'objectives', 0)} objective(s); "
                f"{quarantined} task(s) were quarantined as interrupted."
            ),
            tags=("recovery", "restart"),
            importance=HIGH if quarantined else NORMAL,
            source=RECOVERY,
        )

    def remember_prompt(
        self,
        prompt: str,
        provider_id: str,
        verdict: str,
        expectation: str = "",
        evidence_id: str = "",
    ) -> MemoryWrite:
        """A prompt whose answer was *checked* (MB035).

        MB034 left the Prompt Library without an automatic writer because
        nothing could tell whether a prompt had worked. A verdict can, so
        this is the door it comes through — matched work goes to the
        Prompt Library, anything else to the Failure Library, and the
        evidence id travels with both so a claim can be traced back.

        Called through `PromptExecutor`'s memory sink rather than by
        importing anything: `memory/` reaches neither the Broker nor a
        provider, and a test asserts it.
        """
        worked = verdict == "matched"
        return self.write(
            category=PROMPT_LIBRARY if worked else FAILURE_LIBRARY,
            title=f"{'Prompt worked' if worked else 'Prompt failed'}: {derive_summary(prompt, limit=70)}",
            # Deliberately excludes the evidence id, because `full_text` is
            # what the content digest is taken over. Running the same
            # prompt twice produces two Evidence records and **one
            # lesson** -- putting a fresh uuid in here made every repeat a
            # new memory and quietly defeated MB034's duplicate
            # suppression, filling the Prompt Library with the same prompt.
            full_text=(
                f"{prompt}\n\nAnswered by {provider_id}; verification verdict "
                f"'{verdict}'"
                + (f" against: {expectation}" if expectation else "")
                + "."
            ),
            # The traceable half. A merge keeps the first one, which is
            # correct: it is the check that established the lesson.
            summary=(
                f"verdict '{verdict}' from {provider_id}"
                + (f" (evidence {evidence_id})" if evidence_id else "")
            ),
            tags=("prompt", verdict, provider_id),
            importance=NORMAL if worked else HIGH,
            source=VERIFICATION,
        )

    def remember_architecture(
        self, title: str, detail: str, tags: Any = (), importance: str = HIGH
    ) -> MemoryWrite:
        """An architectural decision, stated rather than detected.

        Nothing publishes "the architecture changed", and inferring it from
        a diff would be exactly the guessing MB034 forbids. So this is a
        door, used by whoever knows — today the founder, tomorrow a brief.
        """
        return self.write(
            category=ARCHITECTURE_DECISIONS,
            title=title,
            full_text=detail,
            tags=normalise_tags(set(normalise_tags(tags)) | {"architecture"}),
            importance=importance,
            source=FOUNDER,
        )

    # ---- reading ----------------------------------------------------------

    @property
    def query(self) -> MemoryQuery:
        """A fresh view over the current records. Cheap, and never stale."""
        return MemoryQuery(self._records, self._index)

    def get(self, record_id: str) -> MemoryRecord | None:
        return self._records.get(record_id)

    def all(self) -> tuple[MemoryRecord, ...]:
        """Every record, oldest first. Insertion order is id order, which
        is what makes the file on disk stable between saves."""
        return tuple(self._records[i] for i in sorted(self._records, key=_number))

    def find_by_tag(self, tag: str) -> tuple[MemoryRecord, ...]:
        return self.query.find_by_tag(tag)

    def find_by_category(self, category: str) -> tuple[MemoryRecord, ...]:
        return self.query.find_by_category(category)

    def recent(self, limit: int = DEFAULT_LIMIT) -> tuple[MemoryRecord, ...]:
        return self.query.recent(limit)

    def related(self, record_id: str, depth: int = 1) -> tuple[MemoryRecord, ...]:
        return self.query.related(record_id, depth)

    def search(self, query: str, limit: int = DEFAULT_LIMIT) -> tuple[MemoryRecord, ...]:
        return self.query.search(query, limit)

    def search_hits(self, query: str, limit: int = DEFAULT_LIMIT) -> tuple[SearchHit, ...]:
        return self.query.search_hits(query, limit)

    def critical(self) -> tuple[MemoryRecord, ...]:
        return self.query.critical()

    def tags(self) -> tuple[str, ...]:
        return self._index.known_tags()

    def __len__(self) -> int:
        return len(self._records)

    def summary(self) -> MemorySummary:
        """One read-only snapshot for the Dashboard."""
        counts: dict[str, int] = {}
        for record in self._records.values():
            counts[record.category] = counts.get(record.category, 0) + 1
        problems = list(self.write_failures)
        if self.load_report is not None:
            problems.extend(self.load_report.problems)

        return MemorySummary(
            total=len(self._records),
            critical=len(self._index.importance(CRITICAL)),
            recent=self.recent(RECENT_SHOWN),
            top_tags=self._index.tag_counts()[:TOP_TAGS_SHOWN],
            last_written=self._records.get(self._last_written or ""),
            by_category=tuple(sorted(counts.items(), key=lambda p: (-p[1], p[0]))),
            problems=tuple(problems),
        )

    # ---- ids ---------------------------------------------------------------

    def _peek_id(self) -> str:
        """The id a new record *would* get. Used to build a candidate for
        digest comparison before deciding whether it is new — so a
        suppressed duplicate never consumes a number and leaves a gap."""
        return _format_id(self._sequence + 1)

    def _take_id(self) -> str:
        self._sequence += 1
        return _format_id(self._sequence)


def _format_id(number: int) -> str:
    return f"{ID_PREFIX}{number:0{ID_WIDTH}d}"


def _number(record_id: str) -> int:
    """The numeric part of an id, for ordering. An id this build did not
    write sorts first rather than raising — a memory imported by hand is
    still a memory."""
    try:
        return int(str(record_id).removeprefix(ID_PREFIX))
    except ValueError:
        return 0
