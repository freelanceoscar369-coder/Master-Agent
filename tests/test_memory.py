"""Mission Brief 004 — Memory System tests.

Covers: SQLiteMemoryStore persistence + retrieval, the Memory facade's
query surface, ConversationMemory's bounded in-process behavior, and
failure recovery (a store re-opened at the same path sees what was
written before it was closed — i.e. mission history survives a
"restart"). See MEMORY_ARCHITECTURE.md.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from master_agent.memory.conversation import ConversationMemory
from master_agent.memory.future import CloudSyncMemory, KnowledgeMemory, VectorMemory
from master_agent.memory.memory import Memory
from master_agent.memory.store import MissionQuery, MissionRecord, SQLiteMemoryStore


def _record(mission_id: str, status: str = "completed", **overrides) -> MissionRecord:
    now = datetime.now(timezone.utc)
    defaults = dict(
        mission_id=mission_id,
        title=f'Create Folder "{mission_id}"',
        intent_summary=f"Create a folder called {mission_id}",
        status=status,
        approval_status="approved",
        created_at=now,
        completed_at=now,
        execution_plan=[{"step_id": "s1", "capability": "create_folder", "payload": {"name": mission_id}}],
        execution_result=f"/tmp/{mission_id}",
        execution_time_seconds=0.01,
        artifacts=[{"type": "folder", "path": f"/tmp/{mission_id}"}],
        errors=[],
        outcome={"created_path": f"/tmp/{mission_id}"},
    )
    defaults.update(overrides)
    return MissionRecord(**defaults)


# ---- SQLiteMemoryStore: persistence + retrieval ----------------------------

def test_save_and_get_mission_round_trips_all_fields():
    store = SQLiteMemoryStore(":memory:")
    record = _record("Demo")

    store.save_mission(record)
    fetched = store.get_mission("Demo")

    assert fetched is not None
    assert fetched.mission_id == "Demo"
    assert fetched.title == record.title
    assert fetched.intent_summary == record.intent_summary
    assert fetched.status == "completed"
    assert fetched.approval_status == "approved"
    assert fetched.execution_plan == record.execution_plan
    assert fetched.execution_result == record.execution_result
    assert fetched.execution_time_seconds == pytest.approx(0.01)
    assert fetched.folders_created == ["/tmp/Demo"]
    assert fetched.files_created == []
    assert fetched.errors == []
    assert fetched.outcome == {"created_path": "/tmp/Demo"}


def test_get_mission_returns_none_for_unknown_id():
    store = SQLiteMemoryStore(":memory:")
    assert store.get_mission("does-not-exist") is None


def test_save_mission_is_idempotent_upsert():
    """Saving the same mission_id twice updates the row instead of
    raising a duplicate-key error -- MEMORY_ARCHITECTURE.md §5."""
    store = SQLiteMemoryStore(":memory:")
    store.save_mission(_record("Demo", status="failed", errors=["boom"]))
    store.save_mission(_record("Demo", status="completed", errors=[]))

    fetched = store.get_mission("Demo")
    assert fetched.status == "completed"
    assert fetched.errors == []


def test_query_missions_orders_newest_first():
    store = SQLiteMemoryStore(":memory:")
    base = datetime.now(timezone.utc)
    store.save_mission(_record("Oldest", completed_at=base - timedelta(minutes=10)))
    store.save_mission(_record("Newest", completed_at=base))
    store.save_mission(_record("Middle", completed_at=base - timedelta(minutes=5)))

    recent = store.query_missions(MissionQuery(limit=10))

    assert [r.mission_id for r in recent] == ["Newest", "Middle", "Oldest"]


def test_query_missions_respects_limit():
    store = SQLiteMemoryStore(":memory:")
    for i in range(15):
        store.save_mission(_record(f"m{i}"))

    assert len(store.query_missions(MissionQuery(limit=10))) == 10
    assert len(store.query_missions(MissionQuery(limit=3))) == 3


def test_query_missions_filters_by_status():
    store = SQLiteMemoryStore(":memory:")
    store.save_mission(_record("Good1", status="completed"))
    store.save_mission(_record("Good2", status="completed"))
    store.save_mission(_record("Bad1", status="failed", errors=["disk full"]))
    store.save_mission(_record("Gone", status="cancelled"))

    successful = store.query_missions(MissionQuery(status="completed"))
    failed = store.query_missions(MissionQuery(status="failed"))
    cancelled = store.query_missions(MissionQuery(status="cancelled"))

    assert {r.mission_id for r in successful} == {"Good1", "Good2"}
    assert [r.mission_id for r in failed] == ["Bad1"]
    assert failed[0].errors == ["disk full"]
    assert [r.mission_id for r in cancelled] == ["Gone"]


def test_query_missions_offset_pages_through_results():
    """The `offset` field exists for a future bulk consumer (Layer 5's
    indexer, MEMORY_ARCHITECTURE.md §12) that needs to walk the whole
    table, not just the most recent N -- added ahead of that consumer
    existing because it's a one-field, zero-complexity addition to
    MissionQuery, not new infrastructure."""
    store = SQLiteMemoryStore(":memory:")
    base = datetime.now(timezone.utc)
    for i in range(5):
        store.save_mission(_record(f"m{i}", completed_at=base - timedelta(minutes=i)))

    page1 = store.query_missions(MissionQuery(limit=2, offset=0))
    page2 = store.query_missions(MissionQuery(limit=2, offset=2))

    assert [r.mission_id for r in page1] == ["m0", "m1"]
    assert [r.mission_id for r in page2] == ["m2", "m3"]


def test_mission_record_folders_and_files_created_derive_from_artifacts():
    record = _record(
        "Demo",
        artifacts=[
            {"type": "folder", "path": "/tmp/Demo"},
            {"type": "folder", "path": "/tmp/Demo/src"},
            {"type": "file", "path": "/tmp/Demo/README.md"},
        ],
    )

    assert record.folders_created == ["/tmp/Demo", "/tmp/Demo/src"]
    assert record.files_created == ["/tmp/Demo/README.md"]


def test_preferences_round_trip():
    store = SQLiteMemoryStore(":memory:")
    assert store.recall_preference("theme", default="light") == "light"

    store.remember_preference("theme", "dark")
    assert store.recall_preference("theme") == "dark"

    # Overwriting an existing key updates it, not duplicates it.
    store.remember_preference("theme", "system")
    assert store.recall_preference("theme") == "system"


def test_preferences_support_structured_values():
    store = SQLiteMemoryStore(":memory:")
    store.remember_preference("recent_types", ["python", "generic"])
    assert store.recall_preference("recent_types") == ["python", "generic"]


# ---- Failure recovery: history survives a "restart" ------------------------

def test_mission_history_survives_reopening_the_store(tmp_path):
    """Not :memory: on purpose -- a file-backed store closed and reopened
    at the same path is the closest this test suite gets to simulating a
    process restart, which is exactly the guarantee Memory exists to
    provide (see MEMORY_ARCHITECTURE.md §1)."""
    db_path = str(tmp_path / "memory.db")

    store = SQLiteMemoryStore(db_path)
    store.save_mission(_record("Survivor"))
    store.close()

    reopened = SQLiteMemoryStore(db_path)
    fetched = reopened.get_mission("Survivor")

    assert fetched is not None
    assert fetched.mission_id == "Survivor"


# ---- Memory facade -----------------------------------------------------------

def test_memory_last_mission_returns_most_recent():
    memory = Memory(SQLiteMemoryStore(":memory:"))
    base = datetime.now(timezone.utc)
    memory.persist_mission(_record("First", completed_at=base - timedelta(minutes=1)))
    memory.persist_mission(_record("Second", completed_at=base))

    last = memory.last_mission()

    assert last.mission_id == "Second"


def test_memory_last_mission_is_none_when_empty():
    memory = Memory(SQLiteMemoryStore(":memory:"))
    assert memory.last_mission() is None


def test_memory_mission_by_id():
    memory = Memory(SQLiteMemoryStore(":memory:"))
    memory.persist_mission(_record("Findable"))

    assert memory.mission_by_id("Findable").mission_id == "Findable"
    assert memory.mission_by_id("missing") is None


def test_memory_recent_missions_default_limit_is_ten():
    memory = Memory(SQLiteMemoryStore(":memory:"))
    for i in range(12):
        memory.persist_mission(_record(f"m{i}"))

    assert len(memory.recent_missions()) == 10


def test_memory_successful_and_failed_missions():
    memory = Memory(SQLiteMemoryStore(":memory:"))
    memory.persist_mission(_record("Good", status="completed"))
    memory.persist_mission(_record("Bad", status="failed", errors=["nope"]))
    memory.persist_mission(_record("Skipped", status="cancelled"))

    assert [r.mission_id for r in memory.successful_missions()] == ["Good"]
    assert [r.mission_id for r in memory.failed_missions()] == ["Bad"]


def test_memory_preferences_delegate_to_store():
    memory = Memory(SQLiteMemoryStore(":memory:"))
    memory.remember_preference("default_project_type", "python")
    assert memory.recall_preference("default_project_type") == "python"
    assert memory.recall_preference("unset_key", default="fallback") == "fallback"


# ---- Layer 1: Conversation Memory -------------------------------------------

def test_conversation_memory_records_turns_in_order():
    convo = ConversationMemory()
    convo.record("user", "hello")
    convo.record("system", "hi there")

    turns = convo.turns()

    assert [(t.speaker, t.text) for t in turns] == [("user", "hello"), ("system", "hi there")]


def test_conversation_memory_last_user_text():
    convo = ConversationMemory()
    convo.record("user", "first")
    convo.record("system", "reply")
    convo.record("user", "second")

    assert convo.last_user_text() == "second"


def test_conversation_memory_last_user_text_is_none_when_no_user_turns():
    convo = ConversationMemory()
    assert convo.last_user_text() is None


def test_conversation_memory_is_bounded():
    convo = ConversationMemory(max_turns=5)
    for i in range(10):
        convo.record("user", f"turn {i}")

    turns = convo.turns()

    assert len(turns) == 5
    # Oldest turns fall off -- the most recent 5 survive.
    assert [t.text for t in turns] == [f"turn {i}" for i in range(5, 10)]


def test_memory_facade_exposes_conversation_layer():
    memory = Memory(SQLiteMemoryStore(":memory:"))
    memory.record_turn("user", "Master Agent")
    memory.record_turn("system", "Hello! I'm awake.")

    turns = memory.conversation_turns()

    assert [t.speaker for t in turns] == ["user", "system"]


# ---- Layers 4-6: interfaces exist, are not implemented, are not wired ------

def test_future_layers_are_abstract_and_unimplemented():
    """These exist as agreed shapes only -- MEMORY_ARCHITECTURE.md §4d.
    Confirms they can't be instantiated directly (no concrete
    implementation exists yet), which is the point."""
    for cls in (KnowledgeMemory, VectorMemory, CloudSyncMemory):
        with pytest.raises(TypeError):
            cls()
