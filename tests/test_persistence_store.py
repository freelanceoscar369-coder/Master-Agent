"""StateStore tests — the only component allowed to touch the filesystem.

Covers atomic writes, append-only event logging, and the corruption cases
the brief requires.
"""
from __future__ import annotations

import json

import pytest

from master_agent.persistence.schema import CorruptSnapshot, SnapshotEnvelope
from master_agent.persistence.store import (
    EVENT_LOG_FILENAME,
    SNAPSHOT_FILENAME,
    InMemoryStateStore,
    JsonFileStateStore,
    StateStore,
)


def sealed(payload=None) -> SnapshotEnvelope:
    return SnapshotEnvelope(payload=payload or {"a": 1}).sealed()


# ---- protocol conformance -----------------------------------------------


def test_both_shipped_stores_satisfy_the_protocol(tmp_path):
    assert isinstance(JsonFileStateStore(tmp_path), StateStore)
    assert isinstance(InMemoryStateStore(), StateStore)


def test_the_store_creates_its_root_directory(tmp_path):
    target = tmp_path / "nested" / "state"
    JsonFileStateStore(target)
    assert target.exists()


# ---- snapshots ----------------------------------------------------------


def test_snapshot_round_trips(tmp_path):
    store = JsonFileStateStore(tmp_path)
    store.save_snapshot(sealed({"objectives": [1, 2]}))
    loaded = store.load_snapshot()
    assert loaded is not None
    assert loaded.payload == {"objectives": [1, 2]}
    loaded.verify()


def test_loading_when_nothing_was_saved_returns_none(tmp_path):
    assert JsonFileStateStore(tmp_path).load_snapshot() is None


def test_saving_twice_replaces_rather_than_appends(tmp_path):
    store = JsonFileStateStore(tmp_path)
    store.save_snapshot(sealed({"n": 1}))
    store.save_snapshot(sealed({"n": 2}))
    assert store.load_snapshot().payload == {"n": 2}


def test_a_snapshot_file_of_invalid_json_is_reported_as_corrupt(tmp_path):
    store = JsonFileStateStore(tmp_path)
    (tmp_path / SNAPSHOT_FILENAME).write_text("{not json", encoding="utf-8")
    with pytest.raises(CorruptSnapshot):
        store.load_snapshot()


def test_a_snapshot_file_that_is_not_an_object_is_reported_as_corrupt(tmp_path):
    store = JsonFileStateStore(tmp_path)
    (tmp_path / SNAPSHOT_FILENAME).write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(CorruptSnapshot):
        store.load_snapshot()


def test_a_truncated_snapshot_is_corrupt_not_silently_partial(tmp_path):
    store = JsonFileStateStore(tmp_path)
    store.save_snapshot(sealed({"objectives": list(range(50))}))
    text = (tmp_path / SNAPSHOT_FILENAME).read_text(encoding="utf-8")
    (tmp_path / SNAPSHOT_FILENAME).write_text(text[: len(text) // 2], encoding="utf-8")
    with pytest.raises(CorruptSnapshot):
        store.load_snapshot()


def test_no_temporary_files_are_left_behind_after_a_write(tmp_path):
    store = JsonFileStateStore(tmp_path)
    store.save_snapshot(sealed())
    assert [p.name for p in tmp_path.glob("*.tmp")] == []


def test_a_failed_write_leaves_the_previous_snapshot_intact(tmp_path, monkeypatch):
    """The failure mode that would make persistence worse than none."""
    store = JsonFileStateStore(tmp_path)
    store.save_snapshot(sealed({"good": True}))

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("master_agent.persistence.store.os.replace", boom)
    with pytest.raises(OSError):
        store.save_snapshot(sealed({"bad": True}))

    assert store.load_snapshot().payload == {"good": True}
    assert [p.name for p in tmp_path.glob("*.tmp")] == []


# ---- event log ----------------------------------------------------------


def test_events_append_rather_than_replace(tmp_path):
    store = JsonFileStateStore(tmp_path)
    store.append_events([{"n": 1}])
    store.append_events([{"n": 2}, {"n": 3}])
    assert [e["n"] for e in store.read_events()] == [1, 2, 3]


def test_appending_nothing_is_a_no_op(tmp_path):
    store = JsonFileStateStore(tmp_path)
    store.append_events([])
    assert store.read_events() == []
    assert not (tmp_path / EVENT_LOG_FILENAME).exists()


def test_reading_an_absent_log_returns_empty(tmp_path):
    assert JsonFileStateStore(tmp_path).read_events() == []


def test_one_event_per_line(tmp_path):
    store = JsonFileStateStore(tmp_path)
    store.append_events([{"n": 1}, {"n": 2}])
    lines = (tmp_path / EVENT_LOG_FILENAME).read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["n"] == 1


def test_a_truncated_final_line_costs_only_that_line(tmp_path):
    """A crash mid-append must not throw away the history before it."""
    store = JsonFileStateStore(tmp_path)
    store.append_events([{"n": 1}, {"n": 2}])
    with (tmp_path / EVENT_LOG_FILENAME).open("a", encoding="utf-8") as handle:
        handle.write('{"n": 3, "trunc')

    assert [e["n"] for e in store.read_events()] == [1, 2]


def test_blank_lines_in_the_log_are_skipped(tmp_path):
    store = JsonFileStateStore(tmp_path)
    store.append_events([{"n": 1}])
    with (tmp_path / EVENT_LOG_FILENAME).open("a", encoding="utf-8") as handle:
        handle.write("\n\n")
    store.append_events([{"n": 2}])
    assert [e["n"] for e in store.read_events()] == [1, 2]


def test_non_object_log_lines_are_skipped(tmp_path):
    store = JsonFileStateStore(tmp_path)
    with (tmp_path / EVENT_LOG_FILENAME).open("w", encoding="utf-8") as handle:
        handle.write('"a string"\n[1,2]\n{"n": 1}\n')
    assert [e["n"] for e in store.read_events()] == [1]


def test_unicode_survives_the_log(tmp_path):
    store = JsonFileStateStore(tmp_path)
    store.append_events([{"text": "café — 日本語"}])
    assert store.read_events()[0]["text"] == "café — 日本語"


# ---- lifecycle ----------------------------------------------------------


def test_has_state_is_false_before_anything_is_written(tmp_path):
    assert JsonFileStateStore(tmp_path).has_state() is False


def test_has_state_is_true_with_only_a_snapshot(tmp_path):
    store = JsonFileStateStore(tmp_path)
    store.save_snapshot(sealed())
    assert store.has_state() is True


def test_has_state_is_true_with_only_events(tmp_path):
    store = JsonFileStateStore(tmp_path)
    store.append_events([{"n": 1}])
    assert store.has_state() is True


def test_clear_removes_everything_and_is_safe_to_repeat(tmp_path):
    store = JsonFileStateStore(tmp_path)
    store.save_snapshot(sealed())
    store.append_events([{"n": 1}])
    store.clear()
    store.clear()
    assert store.has_state() is False
    assert store.load_snapshot() is None
    assert store.read_events() == []


# ---- in-memory store ----------------------------------------------------


def test_in_memory_store_behaves_like_the_file_store():
    store = InMemoryStateStore()
    assert store.has_state() is False
    store.save_snapshot(sealed({"n": 1}))
    store.append_events([{"e": 1}])
    assert store.has_state() is True
    assert store.load_snapshot().payload == {"n": 1}
    assert store.read_events() == [{"e": 1}]
    store.clear()
    assert store.has_state() is False


def test_in_memory_store_touches_no_filesystem(tmp_path):
    """Proof that nothing above store.py assumes a filesystem exists."""
    store = InMemoryStateStore()
    store.save_snapshot(sealed())
    store.append_events([{"e": 1}])
    assert list(tmp_path.iterdir()) == []
