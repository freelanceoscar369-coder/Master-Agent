"""Snapshot versioning, integrity, and migration (MB025 deliverable #10).

Corruption-detection and schema-version tests the brief requires.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from master_agent.persistence import schema as schema_module
from master_agent.persistence.schema import (
    CURRENT_SCHEMA_VERSION,
    RUNTIME_VERSION,
    CorruptSnapshot,
    PersistenceError,
    SnapshotEnvelope,
    UnsupportedSchemaVersion,
    canonical_json,
    compute_checksum,
    migrate,
)


def sealed(payload: dict | None = None, **kwargs) -> SnapshotEnvelope:
    return SnapshotEnvelope(payload=payload or {"a": 1}, **kwargs).sealed()


# ---- envelope shape -----------------------------------------------------


def test_envelope_carries_all_four_brief_required_fields():
    envelope = sealed()
    data = envelope.as_dict()
    for required in ("schema_version", "runtime_version", "created_at", "checksum"):
        assert required in data


def test_a_sealed_envelope_verifies():
    sealed().verify()  # must not raise


def test_envelope_defaults_to_the_current_schema_and_runtime_version():
    envelope = sealed()
    assert envelope.schema_version == CURRENT_SCHEMA_VERSION
    assert envelope.runtime_version == RUNTIME_VERSION


def test_envelope_round_trips_through_a_dict():
    original = sealed({"objectives": [{"id": "x"}]})
    restored = SnapshotEnvelope.from_dict(original.as_dict())
    assert restored.payload == original.payload
    assert restored.checksum == original.checksum
    restored.verify()


def test_created_at_is_timezone_aware():
    assert sealed().created_at.tzinfo is not None


# ---- checksums ----------------------------------------------------------


def test_canonical_json_is_order_independent():
    assert canonical_json({"b": 2, "a": 1}) == canonical_json({"a": 1, "b": 2})


def test_identical_payloads_hash_identically():
    assert compute_checksum({"a": 1, "b": [1, 2]}) == compute_checksum({"b": [1, 2], "a": 1})


def test_different_payloads_hash_differently():
    assert compute_checksum({"a": 1}) != compute_checksum({"a": 2})


def test_a_tampered_payload_fails_verification():
    envelope = sealed({"objectives": ["original"]})
    tampered = SnapshotEnvelope(
        payload={"objectives": ["tampered"]},
        schema_version=envelope.schema_version,
        runtime_version=envelope.runtime_version,
        created_at=envelope.created_at,
        checksum=envelope.checksum,
    )
    with pytest.raises(CorruptSnapshot):
        tampered.verify()


def test_a_missing_checksum_fails_verification_rather_than_being_trusted():
    unsealed = SnapshotEnvelope(payload={"a": 1})
    with pytest.raises(CorruptSnapshot):
        unsealed.verify()


def test_verify_raises_rather_than_returning_a_boolean():
    """A caller who forgets to check a boolean gets corrupted state; a
    caller who forgets to catch an exception gets a loud failure."""
    assert SnapshotEnvelope.verify.__annotations__.get("return") in (None, "None")


def test_corruption_errors_share_one_catchable_base():
    assert issubclass(CorruptSnapshot, PersistenceError)
    assert issubclass(UnsupportedSchemaVersion, PersistenceError)


# ---- malformed envelopes ------------------------------------------------


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"payload": {}},
        {"schema_version": 1},
        {"payload": {}, "schema_version": "not-a-number", "created_at": "2026-01-01T00:00:00"},
        {"payload": {}, "schema_version": 1, "created_at": "not-a-date"},
    ],
)
def test_a_malformed_envelope_is_reported_as_corrupt(data):
    with pytest.raises(CorruptSnapshot):
        SnapshotEnvelope.from_dict(data)


# ---- versioning and migration -------------------------------------------


def test_a_current_version_snapshot_passes_through_migration_unchanged():
    envelope = sealed()
    assert migrate(envelope) is envelope


def test_a_future_schema_version_is_refused_not_guessed_at():
    envelope = sealed(schema_version=CURRENT_SCHEMA_VERSION + 5)
    with pytest.raises(UnsupportedSchemaVersion):
        migrate(envelope)


def test_an_older_version_without_a_migration_is_refused_clearly():
    """The guarantee: a gap in the migration chain is refused rather than
    guessed at.

    This used `CURRENT_SCHEMA_VERSION - 1` as its example, which stopped
    being an unmigrated version the moment v1 -> v2 was registered for the
    provider slice. The property is unchanged; only the example needed to
    be a version that genuinely has no migration.
    """
    envelope = sealed(schema_version=0)
    with pytest.raises(UnsupportedSchemaVersion) as exc:
        migrate(envelope)
    assert "no migration registered" in str(exc.value)


def test_a_registered_migration_is_applied_and_the_result_is_resealed(monkeypatch):
    """Proves the migration seam works end to end, so v2 really is one
    registry entry rather than a rewrite."""
    monkeypatch.setattr(schema_module, "CURRENT_SCHEMA_VERSION", 2)
    monkeypatch.setitem(schema_module.MIGRATIONS, 1, lambda p: {**p, "migrated": True})

    old = SnapshotEnvelope(payload={"a": 1}, schema_version=1).sealed()
    migrated = schema_module.migrate(old)

    assert migrated.schema_version == 2
    assert migrated.payload["migrated"] is True
    migrated.verify()


def test_migrations_chain_across_multiple_versions(monkeypatch):
    monkeypatch.setattr(schema_module, "CURRENT_SCHEMA_VERSION", 3)
    monkeypatch.setitem(schema_module.MIGRATIONS, 1, lambda p: {**p, "v2": True})
    monkeypatch.setitem(schema_module.MIGRATIONS, 2, lambda p: {**p, "v3": True})

    migrated = schema_module.migrate(SnapshotEnvelope(payload={}, schema_version=1).sealed())

    assert migrated.schema_version == 3
    assert migrated.payload == {"v2": True, "v3": True}


def test_runtime_version_is_recorded_but_never_gates_readability():
    """Only schema_version decides whether a snapshot can be read --
    runtime_version is traceability, not a compatibility check."""
    envelope = sealed(runtime_version="0.0.1-ancient")
    migrate(envelope).verify()


def test_envelope_created_at_survives_a_round_trip_exactly():
    when = datetime(2026, 7, 26, 12, 30, tzinfo=UTC)
    restored = SnapshotEnvelope.from_dict(sealed(created_at=when).as_dict())
    assert restored.created_at == when
