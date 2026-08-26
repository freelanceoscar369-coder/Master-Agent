"""PersistenceService — the service that makes Mission Control and the
Runtime continuous (Mission Brief 025).

Rule 1: it never executes missions. It subscribes to the Event Bus,
serialises state on request, and restores it on startup. It holds no
gateway, no Executive, and no dispatch surface.

Two mechanisms, per PERSISTENCE_ARCHITECTURE.md §3:
  - the **event log**, appended as events happen (audit history, replay)
  - the **snapshot**, written on checkpoint (fast restart)
"""
from __future__ import annotations

from typing import Any

from master_agent.mission_control.events import Event
from master_agent.mission_control.mission_control import MissionControl
from master_agent.persistence.schema import (
    CURRENT_SCHEMA_VERSION,
    RUNTIME_VERSION,
    CorruptSnapshot,
    SnapshotEnvelope,
    migrate,
)
from master_agent.persistence.serialization import (
    audit_entry_to_event,
    capability_from_dict,
    capability_to_dict,
    event_from_dict,
    event_to_dict,
    executive_from_dict,
    executive_to_dict,
    objective_from_dict,
    objective_to_dict,
)
from master_agent.persistence.store import StateStore
from master_agent.runtime.checkpoint import RuntimeCheckpoint


class PersistenceService:
    """Attach with `PersistenceService(store, mission_control)`; call
    `start_recording()` to begin capturing events."""

    def __init__(
        self,
        store: StateStore,
        mission_control: MissionControl | None = None,
        flush_every: int = 1,
    ) -> None:
        self._store = store
        self._mc = mission_control
        self._flush_every = max(1, flush_every)
        self._buffer: list[dict[str, Any]] = []
        self._recording = False

    @property
    def store(self) -> StateStore:
        return self._store

    # ---- event capture (deliverable #6) ------------------------------

    def start_recording(self, mission_control: MissionControl | None = None) -> None:
        """Subscribe to every event type, including ones added later --
        `subscribe(handler)` with no type means all."""
        target = mission_control or self._mc
        if target is None:
            raise ValueError("no MissionControl to record from")
        self._mc = target
        target.bus.subscribe(self.record_event)
        self._recording = True

    def record_event(self, event: Event) -> None:
        """Buffered so a burst of events is one write rather than N. With
        the default `flush_every=1` there is no buffering at all, which is
        the safe default: an event that is only in memory is an event that
        does not survive a kill."""
        self._buffer.append(event_to_dict(event))
        if len(self._buffer) >= self._flush_every:
            self.flush()

    def flush(self) -> None:
        if not self._buffer:
            return
        pending, self._buffer = self._buffer, []
        self._store.append_events(pending)

    # ---- snapshots (deliverables #2-#5, #7) --------------------------

    def build_snapshot(
        self,
        mission_control: MissionControl | None = None,
        checkpoint: RuntimeCheckpoint | None = None,
        provider_registry: Any = None,
    ) -> SnapshotEnvelope:
        """Serialise live state into a sealed, versioned envelope. Reads
        only public surfaces (Rule 4)."""
        target = mission_control or self._mc
        if target is None:
            raise ValueError("no MissionControl to snapshot")

        payload: dict[str, Any] = {
            "executives": [executive_to_dict(r) for r in target.executives.all()],
            "capabilities": [capability_to_dict(d) for d in target.capabilities.all()],
            "objectives": [
                objective_to_dict(o) for o in target.dispatcher.objectives()
            ],
            "founder_state": target.founder_state().as_dict(),
            # MB028.1 Deliverable 5: a deferred approval is an unanswered
            # question, and a question the founder has not answered must
            # still be there after a restart. The ledger travels with it
            # so approval evidence survives too (ADR-0019).
            "approvals": target.approvals.as_dict(),
            "runtime": checkpoint.as_dict() if checkpoint else None,
            # The canonical provider record. Administrative facts only:
            # `ProviderDescriptor.as_dict()` has no field that can hold a
            # credential, and a guard asserts that rather than trusting it.
            #
            # Runtime facts are deliberately NOT preserved as truth here.
            # A provider that was healthy yesterday is not healthy today,
            # and `restore_providers()` starts every restored descriptor
            # UNVERIFIED so current reality has to say so again.
            "providers": (
                [d.as_dict() for d in provider_registry.all()]
                if provider_registry is not None else []
            ),
        }
        return SnapshotEnvelope(
            payload=payload,
            schema_version=CURRENT_SCHEMA_VERSION,
            runtime_version=RUNTIME_VERSION,
        ).sealed()

    def save(
        self,
        mission_control: MissionControl | None = None,
        checkpoint: RuntimeCheckpoint | None = None,
    ) -> SnapshotEnvelope:
        """Flush pending events, then write the snapshot. Events first, so
        a crash between the two loses nothing that the log could have
        answered for."""
        self.flush()
        envelope = self.build_snapshot(mission_control, checkpoint)
        self._store.save_snapshot(envelope)
        return envelope

    def load(self) -> SnapshotEnvelope | None:
        """Returns a verified, migrated snapshot, or None if there is
        none. Raises CorruptSnapshot / UnsupportedSchemaVersion rather
        than returning something untrustworthy."""
        envelope = self._store.load_snapshot()
        if envelope is None:
            return None
        envelope.verify()
        return migrate(envelope)

    def has_state(self) -> bool:
        return self._store.has_state()

    # ---- CheckpointSink (Rule 3 -- the Runtime's protocol) -----------

    def save_checkpoint(self, checkpoint: RuntimeCheckpoint) -> None:
        """Satisfies `runtime.checkpoint.CheckpointSink`. The Runtime calls
        this without knowing a file exists.

        A checkpoint updates the runtime slice of the snapshot; when a
        MissionControl is attached, the whole snapshot is rewritten so
        runtime counters and Mission Control state are always consistent
        with each other rather than describing two different moments.
        """
        if self._mc is not None:
            self.save(self._mc, checkpoint)
            return

        payload = {
            "executives": [],
            "capabilities": [],
            "objectives": [],
            "founder_state": None,
            "runtime": checkpoint.as_dict(),
        }
        self._store.save_snapshot(
            SnapshotEnvelope(payload=payload).sealed()
        )

    def load_checkpoint(self) -> RuntimeCheckpoint | None:
        """Satisfies `runtime.checkpoint.CheckpointSink`."""
        try:
            envelope = self.load()
        except CorruptSnapshot:
            return None
        if envelope is None:
            return None
        runtime_payload = envelope.payload.get("runtime")
        if not runtime_payload:
            return None
        return RuntimeCheckpoint.from_dict(runtime_payload)

    # ---- restore (deliverable #8) ------------------------------------

    def restore_into(
        self,
        mission_control: MissionControl,
        envelope: SnapshotEnvelope | None = None,
        restore_audit: bool = True,
        quarantine_interrupted: bool = True,
    ) -> dict[str, int]:
        """Rebuild Mission Control from a snapshot, using public contracts
        only (Rule 4). Returns counts of what was restored.

        Order matters: registries first (so capability resolution works),
        then objectives, then audit. Every one of these paths publishes
        nothing, so the restored audit contains exactly the history that
        actually happened -- not a second copy of it.
        """
        counts = {"executives": 0, "capabilities": 0, "objectives": 0, "audit_entries": 0}

        resolved = envelope if envelope is not None else self.load()
        if resolved is None:
            # No snapshot -- but the event log may still hold history, and
            # "audit history must survive restart" (deliverable #6) does
            # not depend on a snapshot existing. Restoring nothing here
            # would silently throw away a perfectly good log.
            if restore_audit:
                counts["audit_entries"] = self.restore_audit_into(mission_control)
            return counts

        payload = resolved.payload

        for data in payload.get("executives") or []:
            record = executive_from_dict(data)
            if not mission_control.executives.has(record.executive_id):
                mission_control.executives.register(record)
                counts["executives"] += 1

        for data in payload.get("capabilities") or []:
            descriptor = capability_from_dict(data)
            if not mission_control.capabilities.has(descriptor.qualified_name):
                mission_control.capabilities.register(descriptor)
                counts["capabilities"] += 1

        for data in payload.get("objectives") or []:
            objective = objective_from_dict(data, quarantine_interrupted)
            # The additive restore contract MB025 required -- see ADR-0015
            # Decision 3. Publishes nothing, so restoring does not claim
            # these objectives were submitted a second time, and it also
            # re-establishes the current objective so founder_state()
            # reports the recovered mission rather than an empty snapshot.
            mission_control.restore_objective(objective)
            counts["objectives"] += 1

        # MB028.1: restores questions and evidence, never authority. A
        # restored APPROVED entry records that the founder once said yes;
        # the grant it produced lived in the Permission System and is
        # deliberately gone (ADR-0019 Decision 3).
        approvals = payload.get("approvals")
        if approvals:
            mission_control.approvals.restore(approvals)
            counts["approvals"] = len(approvals.get("approvals", []))

        if restore_audit:
            counts["audit_entries"] = self.restore_audit_into(mission_control)

        return counts

    def restore_audit_into(self, mission_control: MissionControl) -> int:
        """Rebuild audit history from the event log.

        Uses `AuditStream.record()` -- the frozen component's own public,
        append-only API -- with Events reconstructed carrying their
        original `event_id` and `occurred_at`, so entries come back
        identical. No change to Mission Control was needed for this.
        """
        events = self._store.read_events()
        for data in events:
            try:
                mission_control.audit.record(event_from_dict(data))
            except (KeyError, ValueError):
                # A single unparseable line (a crash mid-append) must not
                # cost the rest of the history.
                continue
        return len(mission_control.audit)

    def archive_audit(self, mission_control: MissionControl) -> int:
        """Write a live audit stream into the event log -- used when
        persistence is attached to a system that has already been
        running, so its existing history is not lost."""
        events = [
            event_to_dict(audit_entry_to_event(entry))
            for entry in mission_control.audit.entries
        ]
        self._store.append_events(events)
        return len(events)


def restore_providers(envelope, registry) -> tuple[str, ...]:
    """Put a snapshot's canonical provider descriptors back, and refuse to
    pretend yesterday's runtime observations are today's.

    **Administrative facts survive; runtime facts do not.** A descriptor
    records what a provider IS -- its identity, locality, privacy,
    declared quality, economics and the provenance of those claims. That
    is stable and worth carrying across a restart. Whether it is
    *available*, *installed*, *healthy* or *within quota right now* is a
    fact about the world at the moment of asking, and restoring one as
    though it were still true is how a launcher selects a provider that
    has since gone away.

    `ProviderDescriptor.health` conflates the two, so the smallest
    truthful rule is applied here rather than by inventing a second health
    system: every restored descriptor comes back UNVERIFIED, whatever it
    was when saved, and the ordinary availability machinery re-establishes
    it from present reality.

    `verified_at` is deliberately NOT cleared, and that is worth stating
    because a first version of this tried. `ProviderRegistry.register()`
    stamps it on every write, so in that owner's model it records when the
    RECORD was last written, not when the provider was last confirmed
    working. Clearing it here would have been overwritten a line later
    anyway, and asserting otherwise would have been a comment describing
    behaviour the code does not have. Health is the runtime fact, and
    health is what resets.

    Returns the ids restored, so a caller can assert rather than trust.
    A row that cannot be read is refused loudly -- the same discipline the
    rest of this module applies to a payload it does not understand.
    """
    import dataclasses

    from master_agent.broker.registry import ProviderDescriptor, ProviderHealth

    rows = (envelope.payload or {}).get("providers") or []
    restored: list[str] = []
    for row in rows:
        descriptor = ProviderDescriptor.from_dict(row)
        registry.register(dataclasses.replace(
            descriptor, health=ProviderHealth.UNVERIFIED,
        ))
        restored.append(descriptor.provider_id)
    return tuple(restored)
