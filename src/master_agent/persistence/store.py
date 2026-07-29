"""The storage contract and its local-filesystem implementation.

This module is the **only** place in Kalpavriksha that reads or writes
persistence files. Mission Control cannot (MB025 constraint, enforced by
its own architecture test); the Runtime cannot (it talks to a Protocol
defined in `runtime/`); the rest of this package talks to `StateStore`.

Writes are atomic: serialise to a temporary file in the same directory,
then `os.replace()` onto the target. A crash mid-write therefore leaves
the *previous good* snapshot rather than a truncated one -- the failure
mode that would make a persistence layer worse than having none.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from master_agent.persistence.schema import CorruptSnapshot, SnapshotEnvelope

SNAPSHOT_FILENAME = "snapshot.json"
EVENT_LOG_FILENAME = "events.jsonl"


@runtime_checkable
class StateStore(Protocol):
    """What persistence needs from storage, and nothing more. An
    in-memory, SQLite, or remote implementation satisfies this without
    anything above it changing."""

    def save_snapshot(self, envelope: SnapshotEnvelope) -> None: ...

    def load_snapshot(self) -> SnapshotEnvelope | None: ...

    def append_events(self, events: list[dict[str, Any]]) -> None: ...

    def read_events(self) -> list[dict[str, Any]]: ...

    def has_state(self) -> bool: ...

    def clear(self) -> None: ...


class JsonFileStateStore:
    """Snapshot as one JSON document, events as append-only JSONL."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    @property
    def snapshot_path(self) -> Path:
        return self._root / SNAPSHOT_FILENAME

    @property
    def event_log_path(self) -> Path:
        return self._root / EVENT_LOG_FILENAME

    # ---- snapshot ----------------------------------------------------

    def save_snapshot(self, envelope: SnapshotEnvelope) -> None:
        self._atomic_write(self.snapshot_path, json.dumps(envelope.as_dict(), indent=2))

    def load_snapshot(self) -> SnapshotEnvelope | None:
        if not self.snapshot_path.exists():
            return None
        try:
            raw = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CorruptSnapshot(f"snapshot is not valid JSON: {exc}") from exc
        if not isinstance(raw, dict):
            raise CorruptSnapshot("snapshot is not a JSON object")
        return SnapshotEnvelope.from_dict(raw)

    # ---- event log ---------------------------------------------------

    def append_events(self, events: list[dict[str, Any]]) -> None:
        """Append-only, one JSON document per line. Appending rather than
        rewriting is what keeps the log's cost proportional to what is
        new, and what makes a partial write lose at most the final line
        rather than the whole history."""
        if not events:
            return
        lines = "".join(json.dumps(event, default=str) + "\n" for event in events)
        with self.event_log_path.open("a", encoding="utf-8") as handle:
            handle.write(lines)
            handle.flush()
            os.fsync(handle.fileno())

    def read_events(self) -> list[dict[str, Any]]:
        """A truncated final line (a crash mid-append) is skipped rather
        than fatal: the rest of the history is still perfectly good, and
        refusing all of it because of one bad tail would throw away
        exactly what the founder needs after a crash."""
        if not self.event_log_path.exists():
            return []

        events: list[dict[str, Any]] = []
        for line in self.event_log_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                events.append(parsed)
        return events

    # ---- lifecycle ---------------------------------------------------

    def has_state(self) -> bool:
        return self.snapshot_path.exists() or self.event_log_path.exists()

    def clear(self) -> None:
        self.snapshot_path.unlink(missing_ok=True)
        self.event_log_path.unlink(missing_ok=True)

    # ---- internals ---------------------------------------------------

    def _atomic_write(self, target: Path, content: str) -> None:
        handle, temp_name = tempfile.mkstemp(dir=str(self._root), suffix=".tmp")
        temp_path = Path(temp_name)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, target)
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise


class InMemoryStateStore:
    """A StateStore that never touches disk -- for tests, and proof that
    nothing above this module assumes a filesystem."""

    def __init__(self) -> None:
        self._snapshot: SnapshotEnvelope | None = None
        self._events: list[dict[str, Any]] = []

    def save_snapshot(self, envelope: SnapshotEnvelope) -> None:
        self._snapshot = envelope

    def load_snapshot(self) -> SnapshotEnvelope | None:
        return self._snapshot

    def append_events(self, events: list[dict[str, Any]]) -> None:
        self._events.extend(events)

    def read_events(self) -> list[dict[str, Any]]:
        return list(self._events)

    def has_state(self) -> bool:
        return self._snapshot is not None or bool(self._events)

    def clear(self) -> None:
        self._snapshot = None
        self._events = []
