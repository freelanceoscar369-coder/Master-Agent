"""Local-first memory store. See ADR-0004 (why SQLite, why local-first)
and ADR-0007 (why stdlib sqlite3, why JSON columns over normalization).

Interface is storage-backend-agnostic on purpose: SQLite is the Founder
Edition backend, but nothing outside this file should know that. If a
sync provider plugin (Layer 6, memory/future.py) is added later, it talks
to this interface too. See MEMORY_ARCHITECTURE.md for the full design.
"""
from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class MissionRecord:
    """One completed/failed/cancelled mission, in the shape Layer 3
    persists and Layer 3 queries return. See MEMORY_ARCHITECTURE.md §5
    for what each field means and why the structured-but-unqueried
    fields are plain JSON rather than normalized columns/tables.
    """

    mission_id: str
    title: str
    intent_summary: str
    status: str  # MissionStatus value at the terminal transition: "completed" | "failed" | "cancelled"
    approval_status: str  # "not_required" | "approved" | "denied"
    created_at: datetime
    completed_at: datetime
    execution_plan: list[dict[str, Any]] = field(default_factory=list)
    execution_result: Any = None
    execution_time_seconds: float = 0.0
    folders_created: list[str] = field(default_factory=list)
    files_created: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    outcome: dict[str, Any] | None = None


class MemoryStore(ABC):
    """The storage contract. The rest of the system depends on this (via
    the `Memory` facade in memory/memory.py), never on a concrete
    backend — swapping SQLite for JSON/Postgres/a future sync-aware store
    means writing one new class here, nothing above it changes."""

    @abstractmethod
    def save_mission(self, record: MissionRecord) -> None:
        ...

    @abstractmethod
    def get_mission(self, mission_id: str) -> MissionRecord | None:
        ...

    @abstractmethod
    def recent_missions(self, limit: int = 20) -> list[MissionRecord]:
        ...

    @abstractmethod
    def missions_by_status(self, status: str, limit: int = 20) -> list[MissionRecord]:
        ...

    @abstractmethod
    def remember_preference(self, key: str, value: Any) -> None:
        ...

    @abstractmethod
    def recall_preference(self, key: str, default: Any = None) -> Any:
        ...


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS missions (
    mission_id             TEXT PRIMARY KEY,
    title                   TEXT NOT NULL,
    intent_summary          TEXT NOT NULL,
    status                  TEXT NOT NULL,
    approval_status         TEXT NOT NULL,
    created_at              TEXT NOT NULL,
    completed_at            TEXT NOT NULL,
    execution_plan          TEXT NOT NULL,
    execution_result        TEXT,
    execution_time_seconds  REAL NOT NULL DEFAULT 0.0,
    folders_created         TEXT NOT NULL,
    files_created           TEXT NOT NULL,
    errors                  TEXT NOT NULL,
    outcome                 TEXT
);
CREATE INDEX IF NOT EXISTS idx_missions_status ON missions(status);
CREATE INDEX IF NOT EXISTS idx_missions_completed_at ON missions(completed_at);

CREATE TABLE IF NOT EXISTS preferences (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class SQLiteMemoryStore(MemoryStore):
    """Founder Edition backend — see ADR-0007 for why this is stdlib
    `sqlite3` rather than an ORM, and MEMORY_ARCHITECTURE.md §5 for the
    schema this creates on first use.

    `db_path` is injected, never hardcoded or looked up globally — pass
    ":memory:" for tests, a tmp_path-scoped file for isolated integration
    tests, or a real path (cli.py's `_default_memory_db_path()`) for
    production use. This class is never a singleton: each caller
    constructs its own instance and owns its own connection.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA_SQL)
        self._conn.commit()

    def save_mission(self, record: MissionRecord) -> None:
        # Upsert, not insert-only: a MissionRecord is built once a mission
        # reaches a terminal state, so in practice each mission_id is
        # written exactly once — but making this idempotent costs nothing
        # and means a retried save (e.g. after a caller-side error) can
        # never raise a duplicate-key error.
        self._conn.execute(
            """
            INSERT INTO missions (
                mission_id, title, intent_summary, status, approval_status,
                created_at, completed_at, execution_plan, execution_result,
                execution_time_seconds, folders_created, files_created, errors, outcome
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(mission_id) DO UPDATE SET
                title = excluded.title,
                intent_summary = excluded.intent_summary,
                status = excluded.status,
                approval_status = excluded.approval_status,
                completed_at = excluded.completed_at,
                execution_plan = excluded.execution_plan,
                execution_result = excluded.execution_result,
                execution_time_seconds = excluded.execution_time_seconds,
                folders_created = excluded.folders_created,
                files_created = excluded.files_created,
                errors = excluded.errors,
                outcome = excluded.outcome
            """,
            (
                record.mission_id,
                record.title,
                record.intent_summary,
                record.status,
                record.approval_status,
                record.created_at.isoformat(),
                record.completed_at.isoformat(),
                json.dumps(record.execution_plan),
                json.dumps(record.execution_result) if record.execution_result is not None else None,
                record.execution_time_seconds,
                json.dumps(record.folders_created),
                json.dumps(record.files_created),
                json.dumps(record.errors),
                json.dumps(record.outcome) if record.outcome is not None else None,
            ),
        )
        self._conn.commit()

    def get_mission(self, mission_id: str) -> MissionRecord | None:
        row = self._conn.execute(
            "SELECT * FROM missions WHERE mission_id = ?", (mission_id,)
        ).fetchone()
        return self._row_to_record(row) if row else None

    def recent_missions(self, limit: int = 20) -> list[MissionRecord]:
        rows = self._conn.execute(
            "SELECT * FROM missions ORDER BY completed_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def missions_by_status(self, status: str, limit: int = 20) -> list[MissionRecord]:
        rows = self._conn.execute(
            "SELECT * FROM missions WHERE status = ? ORDER BY completed_at DESC LIMIT ?",
            (status, limit),
        ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def remember_preference(self, key: str, value: Any) -> None:
        self._conn.execute(
            "INSERT INTO preferences (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value)),
        )
        self._conn.commit()

    def recall_preference(self, key: str, default: Any = None) -> Any:
        row = self._conn.execute(
            "SELECT value FROM preferences WHERE key = ?", (key,)
        ).fetchone()
        return json.loads(row["value"]) if row else default

    def close(self) -> None:
        self._conn.close()

    def _row_to_record(self, row: sqlite3.Row) -> MissionRecord:
        return MissionRecord(
            mission_id=row["mission_id"],
            title=row["title"],
            intent_summary=row["intent_summary"],
            status=row["status"],
            approval_status=row["approval_status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"]),
            execution_plan=json.loads(row["execution_plan"]),
            execution_result=(
                json.loads(row["execution_result"]) if row["execution_result"] is not None else None
            ),
            execution_time_seconds=row["execution_time_seconds"],
            folders_created=json.loads(row["folders_created"]),
            files_created=json.loads(row["files_created"]),
            errors=json.loads(row["errors"]),
            outcome=json.loads(row["outcome"]) if row["outcome"] is not None else None,
        )
