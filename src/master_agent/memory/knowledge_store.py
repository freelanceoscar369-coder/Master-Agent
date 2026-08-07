"""Where founder memory lives on disk (Mission Brief 034).

```
    .master_agent/
        state/            <- MB025's snapshot and event log
        memory/
            knowledge.json    <- the records. Authoritative.
            index.json        <- the index. Derived, and disposable.
```

Beside the existing state rather than inside it, deliberately: MB025's
snapshot is *operational* state that a recovery may legitimately discard,
and founder memory is not. Losing what the founder told you because a
mission crashed would be the worst possible reading of "recovery".

Two files, two different attitudes to corruption:

- **`knowledge.json` is authoritative**, so a file that will not parse is
  *preserved*, never overwritten. It is moved aside with a `.corrupt`
  suffix and the store starts empty — because silently replacing the only
  copy of what a founder said is worse than starting from nothing and
  saying so.
- **`index.json` is derived**, so a bad one costs nothing. It is rebuilt
  from the records without comment.

Writes are atomic — serialise to a temporary file in the same directory,
then `os.replace()` — so a crash mid-write leaves the previous good file
rather than a truncated one. That is the third implementation of this
pattern in the codebase (`persistence/store.py`,
`ai_infrastructure/ledger.py`, here); the shared helper it wants would
have to live in a package frozen since MB025, so it is named in MB034's
debt list rather than smuggled in.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from master_agent.memory.memory_index import MemoryIndex
from master_agent.memory.memory_models import MemoryRecord

MEMORY_DIRNAME = "memory"
KNOWLEDGE_FILENAME = "knowledge.json"
INDEX_FILENAME = "index.json"
CORRUPT_SUFFIX = ".corrupt"

#: Bumped if the on-disk record shape changes.
KNOWLEDGE_VERSION = 1


@dataclass
class LoadReport:
    """What came back off the disk, and what went wrong doing it.

    Returned rather than logged: the launcher puts it in the boot report,
    so a founder finds out that three memories were unreadable at the
    moment it matters instead of the next time they search for one.
    """

    records: list[MemoryRecord] = field(default_factory=list)
    index: MemoryIndex | None = None
    skipped: int = 0
    rebuilt_index: bool = False
    corrupted: str = ""
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    @property
    def summary(self) -> str:
        parts = [f"{len(self.records)} memory record(s)"]
        if self.skipped:
            parts.append(f"{self.skipped} unreadable and skipped")
        if self.rebuilt_index:
            parts.append("index rebuilt")
        if self.corrupted:
            parts.append(f"previous file kept at {self.corrupted}")
        return "; ".join(parts)


@runtime_checkable
class KnowledgeStore(Protocol):
    """What the memory service needs from storage, and nothing more."""

    def load(self) -> LoadReport: ...

    def save(self, records: Any, index: MemoryIndex) -> None: ...


class JsonKnowledgeStore:
    """Two JSON documents under `<root>/memory/`, written atomically."""

    def __init__(self, root: Path) -> None:
        self._dir = Path(root) / MEMORY_DIRNAME

    @property
    def directory(self) -> Path:
        return self._dir

    @property
    def knowledge_path(self) -> Path:
        return self._dir / KNOWLEDGE_FILENAME

    @property
    def index_path(self) -> Path:
        return self._dir / INDEX_FILENAME

    # ---- reading ---------------------------------------------------------

    def load(self) -> LoadReport:
        report = LoadReport()
        if not self.knowledge_path.exists():
            report.index = MemoryIndex()
            return report

        raw = self._read_knowledge(report)
        if raw is None:
            report.index = MemoryIndex()
            return report

        for row in raw:
            try:
                report.records.append(MemoryRecord.from_dict(row))
            except (KeyError, TypeError, ValueError):
                # One bad row must not cost the rest of what the founder
                # knows -- the same tolerance the event log applies to a
                # truncated final line.
                report.skipped += 1

        if report.skipped:
            report.problems.append(f"{report.skipped} memory record(s) were unreadable")

        report.index = self._read_index(report)
        return report

    def _read_knowledge(self, report: LoadReport) -> list[dict[str, Any]] | None:
        try:
            payload = json.loads(self.knowledge_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
            report.problems.append(f"knowledge.json could not be read: {exc}")
            report.corrupted = self._preserve()
            return None

        rows = payload.get("records") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            report.problems.append("knowledge.json is not a list of records")
            report.corrupted = self._preserve()
            return None
        return [row for row in rows if isinstance(row, dict)]

    def _read_index(self, report: LoadReport) -> MemoryIndex:
        """Load the cache, and rebuild it if it does not describe exactly
        these records. An index with the right number of wrong entries is
        the failure hardest to notice, so equality is the test, not size."""
        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
            index = MemoryIndex.from_dict(payload)
        except (json.JSONDecodeError, OSError, UnicodeDecodeError, TypeError):
            index = MemoryIndex()

        if index.matches(report.records):
            return index
        report.rebuilt_index = True
        return MemoryIndex.build(report.records)

    def _preserve(self) -> str:
        """Move an unreadable knowledge file aside instead of replacing it.

        A founder can open a `.corrupt` file and copy their notes out. They
        cannot recover a file this program overwrote.
        """
        target = self.knowledge_path.with_suffix(
            self.knowledge_path.suffix + CORRUPT_SUFFIX
        )
        counter = 1
        while target.exists():
            counter += 1
            target = self.knowledge_path.with_suffix(
                f"{self.knowledge_path.suffix}{CORRUPT_SUFFIX}.{counter}"
            )
        try:
            os.replace(self.knowledge_path, target)
        except OSError:  # pragma: no cover - the read already failed
            return ""
        return target.name

    # ---- writing ---------------------------------------------------------

    def save(self, records: Any, index: MemoryIndex) -> None:
        """Records first, then the index.

        In that order because the records are authoritative: a crash
        between the two writes leaves a stale index, which is rebuilt on
        the next load. The reverse order would leave an index describing
        records that were never written.
        """
        self._dir.mkdir(parents=True, exist_ok=True)
        rows = [record.as_dict() for record in records]
        self._write(
            self.knowledge_path,
            {"version": KNOWLEDGE_VERSION, "records": rows},
        )
        self._write(self.index_path, index.as_dict())

    def _write(self, target: Path, payload: Any) -> None:
        handle, temp_name = tempfile.mkstemp(dir=str(self._dir), suffix=".tmp")
        temp_path = Path(temp_name)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, indent=2, default=str)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, target)
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise


class InMemoryKnowledgeStore:
    """A store that never touches disk — for tests, and proof that nothing
    above this class assumes a filesystem."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.index_payload: dict[str, Any] = {}
        self.saves = 0

    def load(self) -> LoadReport:
        report = LoadReport()
        for row in self.rows:
            try:
                report.records.append(MemoryRecord.from_dict(row))
            except (KeyError, TypeError, ValueError):
                report.skipped += 1
        index = MemoryIndex.from_dict(self.index_payload)
        if index.matches(report.records):
            report.index = index
        else:
            report.index = MemoryIndex.build(report.records)
            report.rebuilt_index = bool(self.index_payload)
        return report

    def save(self, records: Any, index: MemoryIndex) -> None:
        self.rows = [record.as_dict() for record in records]
        self.index_payload = index.as_dict()
        self.saves += 1
