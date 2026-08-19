"""What Onkar said, and what Somesh showed him (ADR-0025).

A founder used Kalpavriksha for a real session and asked afterwards what
went wrong. Nothing could be answered: the process that held the
conversation had exited and nothing was written down. `cbf5b2a` made
*missions* durable, but two of the three things the founder actually did
that day -- saying good morning, and asking what Kalpavriksha could do --
created no mission and left no trace at all.

## What this is not

It is not Memory and it is not Knowledge, and ADR-0025 is explicit that
it must never become either. "Onkar said X" is not "X is true", and a
transcript is not something Kalpavriksha *knows*.

The rule that keeps that honest is structural rather than stated: this
module is written by the founder surface and read by an investigator.
**Nothing in `brain/`, `planner/` or the runtime imports it.** A
transcript the Brain could consult during reasoning would be a memory
system wearing an audit trail's name, so the boundary is a test, not a
promise (`test_founder_interaction_audit.py`).

## Append-only

A correction is a new record, never an overwrite. An audit trail that can
be silently rewritten is not evidence -- and the specific defect this
exists to catch (*backend verified success, founder saw "still working"*)
is only provable if both sides were recorded as they actually happened.

## Two people, not two roles

`direction` names the founder and the chief of staff, not a generic
`user`/`assistant` pair. Those are different people -- Onkar delegates,
Somesh operates Kalpavriksha -- and flattening them would discard the
distinction the whole product is built on.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

#: Who spoke. Deliberately not "user"/"assistant".
FOUNDER = "founder"
CHIEF_OF_STAFF = "chief_of_staff"

#: What kind of turn this was. Open on purpose: `UNKNOWN` is preferable to
#: a fabricated classification, and a wrong label in an audit trail is
#: worse than an absent one.
CONVERSATION = "conversation"
CAPABILITY_QUERY = "capability_query"
MISSION_REQUEST = "mission_request"
CLARIFICATION_QUESTION = "clarification_question"
CLARIFICATION_ANSWER = "clarification_answer"
MISSION_RESULT = "mission_result"
ERROR = "error"
UNKNOWN = "unknown"

FILENAME = "founder_interactions.jsonl"


@dataclass
class InteractionRecord:
    """One thing said, by one of two people, at one moment."""

    direction: str
    text: str
    interaction_type: str = UNKNOWN
    interaction_id: str = field(default_factory=lambda: uuid4().hex[:12])
    session_id: str = ""
    at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    #: Correlation, so a later investigation never has to rely on
    #: chronological proximity to tie a turn to the work it caused.
    mission_id: str | None = None
    clarification_id: str | None = None
    approval_id: str | None = None
    completion_id: str | None = None
    #: What the founder was actually SHOWN, when that differs from
    #: anything the Reporter believed internally.
    status: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class JsonlInteractionStore:
    """Append-only JSONL. One record per line, flushed per write.

    Per-write flushing is deliberate: this file's whole purpose is to
    survive a process that did not exit cleanly, and a buffered record is
    exactly the one an investigation would want.
    """

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def append(self, record: InteractionRecord) -> None:
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.as_dict(), ensure_ascii=False) + "\n")
            handle.flush()

    def read(self) -> list[InteractionRecord]:
        if not self._path.is_file():
            return []
        out: list[InteractionRecord] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                out.append(InteractionRecord(**json.loads(line)))
            except (json.JSONDecodeError, TypeError):
                # One unreadable line must not hide the rest of the
                # session. A partial audit beats no audit.
                continue
        return out


class InteractionLog:
    """The surface's one door to the audit trail.

    Never raises. A founder's request must not fail because a log write
    failed -- an audit trail that can break the product it observes is a
    liability, and a missing record is recoverable while a broken session
    is not.
    """

    def __init__(self, store: JsonlInteractionStore, session_id: str = "") -> None:
        self._store = store
        self._session_id = session_id or uuid4().hex[:12]

    @property
    def session_id(self) -> str:
        return self._session_id

    def record(self, direction: str, text: str, **fields: Any) -> InteractionRecord | None:
        record = InteractionRecord(
            direction=direction, text=text, session_id=self._session_id, **fields
        )
        try:
            self._store.append(record)
        except Exception:  # noqa: BLE001 — see the class docstring
            return None
        return record

    def founder_said(self, text: str, **fields: Any) -> InteractionRecord | None:
        return self.record(FOUNDER, text, **fields)

    def founder_was_shown(self, text: str, **fields: Any) -> InteractionRecord | None:
        return self.record(CHIEF_OF_STAFF, text, **fields)
