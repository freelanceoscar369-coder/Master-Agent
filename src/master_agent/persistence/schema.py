"""Snapshot envelope, versioning, and integrity (Mission Brief 025
deliverable #10).

Every snapshot carries a schema version, a runtime version, a timestamp,
and a checksum. The rules around those four fields are what make a
snapshot safe to trust — or safe to refuse.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

# Bump when the persisted payload's shape changes, and add a migration.
CURRENT_SCHEMA_VERSION = 1

# Informational: which build wrote this snapshot. Never used to decide
# whether a snapshot is readable -- that is schema_version's job. Recorded
# so a confusing restore can be traced back to the code that wrote it.
RUNTIME_VERSION = "0.9.0"


class PersistenceError(Exception):
    """Base for every failure this package raises, so a caller can catch
    "persistence went wrong" without catching everything."""


class CorruptSnapshot(PersistenceError):
    """The payload does not match its checksum, or is not parseable. The
    snapshot is refused rather than partially loaded -- loading altered or
    truncated state is worse than starting without it, because the system
    would then act confidently on a lie."""


class UnsupportedSchemaVersion(PersistenceError):
    """The snapshot was written by a newer version than this code
    understands. Refused rather than guessed at."""


def canonical_json(payload: Any) -> str:
    """Deterministic serialisation: sorted keys, no incidental whitespace.
    A checksum is only meaningful if the same state always serialises to
    the same bytes."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def compute_checksum(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SnapshotEnvelope:
    """A payload plus everything needed to decide whether to trust it."""

    payload: dict[str, Any]
    schema_version: int = CURRENT_SCHEMA_VERSION
    runtime_version: str = RUNTIME_VERSION
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    checksum: str = ""

    def sealed(self) -> SnapshotEnvelope:
        """Return a copy with the checksum computed over the payload."""
        return SnapshotEnvelope(
            payload=self.payload,
            schema_version=self.schema_version,
            runtime_version=self.runtime_version,
            created_at=self.created_at,
            checksum=compute_checksum(self.payload),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "runtime_version": self.runtime_version,
            "created_at": self.created_at.isoformat(),
            "checksum": self.checksum,
            "payload": self.payload,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> SnapshotEnvelope:
        try:
            return SnapshotEnvelope(
                payload=data["payload"],
                schema_version=int(data["schema_version"]),
                runtime_version=str(data.get("runtime_version", "unknown")),
                created_at=datetime.fromisoformat(data["created_at"]),
                checksum=str(data.get("checksum", "")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise CorruptSnapshot(f"snapshot envelope is malformed: {exc}") from exc

    def verify(self) -> None:
        """Raises rather than returning a boolean: a caller that forgets to
        check a boolean gets corrupted state, whereas a caller that forgets
        to catch an exception gets a loud failure."""
        actual = compute_checksum(self.payload)
        if self.checksum != actual:
            raise CorruptSnapshot(
                f"checksum mismatch: snapshot claims {self.checksum or '<missing>'}, "
                f"payload hashes to {actual}"
            )


# Migration registry: from_version -> callable(payload) -> payload.
# Empty today because there is only one version. The seam exists so v2 is
# one entry here rather than a rewrite of the loader.
MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {}


def migrate(envelope: SnapshotEnvelope) -> SnapshotEnvelope:
    """Bring a snapshot up to CURRENT_SCHEMA_VERSION, or refuse.

    A *newer* schema than this code knows is refused outright: guessing at
    a format from the future is how state gets silently misread.
    """
    if envelope.schema_version > CURRENT_SCHEMA_VERSION:
        raise UnsupportedSchemaVersion(
            f"snapshot schema v{envelope.schema_version} is newer than this build "
            f"understands (v{CURRENT_SCHEMA_VERSION}); refusing to guess at its shape"
        )

    payload = envelope.payload
    version = envelope.schema_version
    while version < CURRENT_SCHEMA_VERSION:
        migration = MIGRATIONS.get(version)
        if migration is None:
            raise UnsupportedSchemaVersion(
                f"no migration registered from schema v{version} to v{version + 1}"
            )
        payload = migration(payload)
        version += 1

    if version == envelope.schema_version:
        return envelope
    return SnapshotEnvelope(
        payload=payload,
        schema_version=version,
        runtime_version=envelope.runtime_version,
        created_at=envelope.created_at,
    ).sealed()
