"""Memory — the single seam the rest of the system depends on for
anything memory-related. See MEMORY_ARCHITECTURE.md.

Composes Layer 1 (ConversationMemory, in-process) and Layer 3 (a
MemoryStore implementation — SQLite today, anything storage-agnostic
tomorrow) behind one surface. Layer 2 (the mission currently executing)
is deliberately not wrapped here — it already lives on the Mission object
itself (mission_manager/mission.py) and MasterAgentSession.last_mission;
this class's job starts once a mission reaches a terminal state and needs
to survive past this process (see MEMORY_ARCHITECTURE.md §4b). Layers 4-6
are reserved (memory/future.py) and are not referenced by this facade.

MasterAgentSession depends on this class, injected through its
constructor — never on a concrete MemoryStore directly, and never as a
singleton.
"""
from __future__ import annotations

from typing import Any

from master_agent.memory.conversation import ConversationMemory, ConversationTurn
from master_agent.memory.store import MemoryStore, MissionQuery, MissionRecord


class Memory:
    def __init__(self, store: MemoryStore, conversation: ConversationMemory | None = None) -> None:
        self._store = store
        self._conversation = conversation or ConversationMemory()

    # ---- Layer 1: Conversation Memory --------------------------------------

    def record_turn(self, speaker: str, text: str) -> None:
        self._conversation.record(speaker, text)

    def conversation_turns(self) -> list[ConversationTurn]:
        return self._conversation.turns()

    # ---- Layer 3: Persistent Memory ----------------------------------------

    def persist_mission(self, record: MissionRecord) -> None:
        self._store.save_mission(record)

    def mission_by_id(self, mission_id: str) -> MissionRecord | None:
        return self._store.get_mission(mission_id)

    def last_mission(self) -> MissionRecord | None:
        recents = self._store.query_missions(MissionQuery(limit=1))
        return recents[0] if recents else None

    def recent_missions(self, limit: int = 10) -> list[MissionRecord]:
        return self._store.query_missions(MissionQuery(limit=limit))

    def successful_missions(self, limit: int = 20) -> list[MissionRecord]:
        return self._store.query_missions(MissionQuery(status="completed", limit=limit))

    def failed_missions(self, limit: int = 20) -> list[MissionRecord]:
        return self._store.query_missions(MissionQuery(status="failed", limit=limit))

    # ---- Preferences (carried over from ADR-0004's original interface) ----

    def remember_preference(self, key: str, value: Any) -> None:
        self._store.remember_preference(key, value)

    def recall_preference(self, key: str, default: Any = None) -> Any:
        return self._store.recall_preference(key, default)
