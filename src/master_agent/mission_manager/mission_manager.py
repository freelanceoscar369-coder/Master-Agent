"""Mission Manager — owns Mission lifecycle end to end. Every other module
that needs "what is happening right now" reads it from here.
"""
from __future__ import annotations

from master_agent.memory.store import MemoryStore
from master_agent.mission_manager.mission import Mission, MissionStatus


class MissionManager:
    def __init__(self, memory: MemoryStore) -> None:
        self._memory = memory
        self._active: dict[str, Mission] = {}

    def create(self, intent_summary: str) -> Mission:
        mission = Mission(intent_summary=intent_summary)
        self._active[mission.mission_id] = mission
        return mission

    def get(self, mission_id: str) -> Mission | None:
        return self._active.get(mission_id)

    def transition(self, mission_id: str, new_status: MissionStatus) -> Mission:
        mission = self._active[mission_id]
        mission.transition(new_status)
        # Persisting on every transition (rather than only at terminal
        # states) is what lets a mission survive a restart mid-execution —
        # important once this is a long-running desktop app, not just a
        # script.
        return mission
