"""A clarification is joinable by its own canonical identifier.

The previous report listed `clarification_id` as a remaining gap, on the
strength of a field-population count taken from the PRE-fix run and never
re-measured after. It was a measurement error: the canonical id reaches
the durable record. These tests exist so the claim is checked rather than
remembered, in both directions -- that the id is projected, and that it
is the *canonical* one rather than a second id minted at the surface.

`PendingClarification` owns the identity (ADR-0025: the audit records
identity, it never becomes the source of it).
"""
from __future__ import annotations

import inspect

import kalpavriksha_desktop as kd
from master_agent.missions.execution_status import (
    AWAITING_CLARIFICATION,
    ExecutionStatus,
    PendingClarification,
)


def envelope_for_clarification():
    status = ExecutionStatus()
    status.status = AWAITING_CLARIFICATION
    status.pending_clarification = PendingClarification(
        question="What should the folder be called?",
        key="folder_name", objective="Create a folder",
    )
    return status, kd._founder_reply(
        status, status.pending_clarification.question,
        interaction_type="clarification_question",
    )


class TestTheCanonicalIdIsProjected:

    def test_the_envelope_carries_the_owners_id_not_a_new_one(self):
        status, envelope = envelope_for_clarification()
        assert envelope["clarification_id"] == status.pending_clarification.clarification_id

    def test_the_surface_mints_no_identifier_of_its_own(self):
        """If the surface generated an id, two records of the same
        clarification would disagree."""
        source = inspect.getsource(kd._founder_reply)
        assert "uuid" not in source.lower()
        assert "clarification_id" in source

        _, first = envelope_for_clarification()
        status = ExecutionStatus()
        status.pending_clarification = PendingClarification(
            question="q", key="k", objective="o")
        second = kd._founder_reply(status, "q")
        assert first["clarification_id"] != second["clarification_id"], (
            "two different clarifications must not share an id"
        )

    def test_the_status_shown_travels_with_it(self):
        _, envelope = envelope_for_clarification()
        assert envelope["status"] == AWAITING_CLARIFICATION

    def test_no_clarification_means_no_id_rather_than_a_placeholder(self):
        envelope = kd._founder_reply(ExecutionStatus(), "nothing pending")
        assert envelope["clarification_id"] is None


class TestItSurvivesTheRecord:

    def test_the_durable_record_keeps_the_canonical_id(self, tmp_path):
        from master_agent.audit import FILENAME, InteractionLog, JsonlInteractionStore

        status, envelope = envelope_for_clarification()
        log = InteractionLog(JsonlInteractionStore(tmp_path / FILENAME))
        asked = log.founder_said("Create a folder").interaction_id
        log.founder_was_shown(
            envelope["reply"], interaction_type=envelope["interaction_type"],
            clarification_id=envelope["clarification_id"],
            status=envelope["status"], in_reply_to=asked,
        )

        reread = JsonlInteractionStore(tmp_path / FILENAME).read()
        answer = reread[1]
        assert answer.clarification_id == status.pending_clarification.clarification_id
        assert answer.in_reply_to == asked
        assert answer.status == AWAITING_CLARIFICATION

    def test_the_founder_turn_is_not_rewritten_to_carry_it(self, tmp_path):
        """Append-only: the question that caused the clarification was
        written before the clarification existed, and stays as written."""
        from master_agent.audit import FILENAME, InteractionLog, JsonlInteractionStore

        _, envelope = envelope_for_clarification()
        log = InteractionLog(JsonlInteractionStore(tmp_path / FILENAME))
        asked = log.founder_said("Create a folder").interaction_id
        log.founder_was_shown(envelope["reply"], clarification_id=envelope["clarification_id"],
                              in_reply_to=asked)

        founder_turn = JsonlInteractionStore(tmp_path / FILENAME).read()[0]
        assert founder_turn.clarification_id is None
        assert founder_turn.interaction_id == asked
