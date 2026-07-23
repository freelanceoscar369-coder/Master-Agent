"""Local-first memory store. See ADR-0004.

Interface is storage-backend-agnostic on purpose: SQLite is the Founder
Edition backend, but nothing outside this file should know that. If a sync
provider plugin is added later, it talks to this interface too.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class MissionRecord:
    mission_id: str
    intent_summary: str
    status: str
    created_at: datetime
    updated_at: datetime
    outcome: dict[str, Any] | None = None


class MemoryStore(ABC):
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
    def remember_preference(self, key: str, value: Any) -> None:
        ...

    @abstractmethod
    def recall_preference(self, key: str, default: Any = None) -> Any:
        ...


class SQLiteMemoryStore(MemoryStore):
    """Founder Edition backend. Deliberately stubbed — schema + sqlmodel
    wiring is next, once the mission_manager module needs it end-to-end.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    def save_mission(self, record: MissionRecord) -> None:
        raise NotImplementedError

    def get_mission(self, mission_id: str) -> MissionRecord | None:
        raise NotImplementedError

    def recent_missions(self, limit: int = 20) -> list[MissionRecord]:
        raise NotImplementedError

    def remember_preference(self, key: str, value: Any) -> None:
        raise NotImplementedError

    def recall_preference(self, key: str, default: Any = None) -> Any:
        raise NotImplementedError
