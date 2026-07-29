"""Self-Development Queue (#6) and Knowledge Acquisition Queue (#7) tests.

The Knowledge tests carry the weight here: the Promotion Review gate is
Constitution ADR-0012 enforced in code, and these are what stop it from
quietly becoming a convention again.
"""
from __future__ import annotations

import pytest

from master_agent.mission_control.events import EventType
from master_agent.mission_control.knowledge_queue import (
    IllegalKnowledgeTransition,
    KnowledgeAcquisitionQueue,
    KnowledgeRequest,
    KnowledgeStage,
    PromotionRequiresHumanApproval,
)
from master_agent.mission_control.mission_control import MissionControl
from master_agent.mission_control.self_development import (
    IllegalSelfDevelopmentTransition,
    SelfDevelopmentItem,
    SelfDevelopmentQueue,
    SelfDevelopmentState,
    SelfDevelopmentType,
)

# ---- self-development queue --------------------------------------------


def test_all_five_brief_named_self_development_types_exist():
    expected = {
        "pending_capability",
        "learning_task",
        "architecture_improvement",
        "research_request",
        "implementation",
    }
    assert {member.value for member in SelfDevelopmentType} == expected


def test_items_move_through_their_state_machine():
    queue = SelfDevelopmentQueue()
    item = queue.add(
        SelfDevelopmentItem(
            item_type=SelfDevelopmentType.PENDING_CAPABILITY, title="Desktop.WindowDetect"
        )
    )
    queue.transition(item.item_id, SelfDevelopmentState.ACCEPTED)
    queue.transition(item.item_id, SelfDevelopmentState.IN_PROGRESS)
    queue.transition(item.item_id, SelfDevelopmentState.DONE)
    assert queue.get(item.item_id).state is SelfDevelopmentState.DONE


def test_illegal_self_development_transition_is_refused():
    queue = SelfDevelopmentQueue()
    item = queue.add(
        SelfDevelopmentItem(item_type=SelfDevelopmentType.LEARNING_TASK, title="x")
    )
    with pytest.raises(IllegalSelfDevelopmentTransition):
        queue.transition(item.item_id, SelfDevelopmentState.DONE)


def test_pending_is_ordered_by_priority_then_insertion_deterministically():
    queue = SelfDevelopmentQueue()
    queue.add(SelfDevelopmentItem(SelfDevelopmentType.LEARNING_TASK, "low", priority=200))
    queue.add(SelfDevelopmentItem(SelfDevelopmentType.LEARNING_TASK, "high", priority=1))
    queue.add(SelfDevelopmentItem(SelfDevelopmentType.LEARNING_TASK, "mid", priority=50))
    assert [item.title for item in queue.pending()] == ["high", "mid", "low"]


def test_done_and_rejected_items_leave_the_pending_list():
    queue = SelfDevelopmentQueue()
    item = queue.add(SelfDevelopmentItem(SelfDevelopmentType.IMPLEMENTATION, "x"))
    queue.transition(item.item_id, SelfDevelopmentState.REJECTED)
    assert queue.pending() == []


# ---- knowledge acquisition pipeline ------------------------------------


def test_all_seven_brief_named_pipeline_stages_exist():
    expected = {
        "need",
        "research",
        "source_collection",
        "comparison",
        "verification",
        "knowledge_storage",
        "capability_creation",
    }
    assert expected <= {member.value for member in KnowledgeStage}


def test_pipeline_advances_one_stage_at_a_time_up_to_the_gate():
    queue = KnowledgeAcquisitionQueue()
    request = queue.add(KnowledgeRequest(need="how to detect a window"))
    for expected in (
        KnowledgeStage.RESEARCH,
        KnowledgeStage.SOURCE_COLLECTION,
        KnowledgeStage.COMPARISON,
        KnowledgeStage.VERIFICATION,
    ):
        assert queue.advance(request.request_id).stage is expected


def test_promotion_without_human_approval_is_refused_in_code_not_convention():
    """Constitution ADR-0012: promoting knowledge silently reshapes all
    future reasoning, so it requires an explicit human decision."""
    queue = KnowledgeAcquisitionQueue()
    request = queue.add(KnowledgeRequest(need="x"))
    for _ in range(4):
        queue.advance(request.request_id)
    assert queue.get(request.request_id).stage is KnowledgeStage.VERIFICATION

    with pytest.raises(PromotionRequiresHumanApproval):
        queue.advance(request.request_id)

    assert queue.get(request.request_id).stage is KnowledgeStage.VERIFICATION, (
        "a refused promotion must not have advanced the request"
    )


def test_promotion_with_human_approval_records_who_approved_it():
    queue = KnowledgeAcquisitionQueue()
    request = queue.add(KnowledgeRequest(need="x"))
    for _ in range(4):
        queue.advance(request.request_id)

    promoted = queue.advance(request.request_id, human_approved=True, approved_by="founder")
    assert promoted.stage is KnowledgeStage.KNOWLEDGE_STORAGE
    assert promoted.promoted_by == "founder"
    assert promoted.is_promoted


def test_human_approval_is_only_consulted_at_the_promotion_gate():
    """Passing human_approved earlier is harmless and meaningless -- no
    other stage change makes anything durable."""
    queue = KnowledgeAcquisitionQueue()
    request = queue.add(KnowledgeRequest(need="x"))
    advanced = queue.advance(request.request_id, human_approved=True)
    assert advanced.stage is KnowledgeStage.RESEARCH
    assert advanced.promoted_by is None


def test_a_rejected_request_cannot_advance():
    queue = KnowledgeAcquisitionQueue()
    request = queue.add(KnowledgeRequest(need="x"))
    queue.reject(request.request_id, "the need was misconceived")
    with pytest.raises(IllegalKnowledgeTransition):
        queue.advance(request.request_id)


def test_advancing_past_the_final_stage_is_refused():
    queue = KnowledgeAcquisitionQueue()
    request = queue.add(KnowledgeRequest(need="x"))
    for _ in range(4):
        queue.advance(request.request_id)
    queue.advance(request.request_id, human_approved=True)
    queue.advance(request.request_id)  # -> CAPABILITY_CREATION
    with pytest.raises(IllegalKnowledgeTransition):
        queue.advance(request.request_id)


def test_awaiting_promotion_surfaces_exactly_what_needs_a_human():
    queue = KnowledgeAcquisitionQueue()
    waiting = queue.add(KnowledgeRequest(need="waiting"))
    early = queue.add(KnowledgeRequest(need="early"))
    for _ in range(4):
        queue.advance(waiting.request_id)
    queue.advance(early.request_id)

    assert [r.need for r in queue.awaiting_promotion()] == ["waiting"]


# ---- integration with Mission Control's event stream -------------------


def test_a_refused_auto_promotion_is_auditable_not_silent():
    mc = MissionControl()
    request = mc.request_knowledge("how to detect a window")
    for _ in range(4):
        mc.advance_knowledge(request.request_id)

    with pytest.raises(PromotionRequiresHumanApproval):
        mc.advance_knowledge(request.request_id)

    approval_events = mc.audit.of_type(EventType.APPROVAL_REQUIRED)
    assert len(approval_events) == 1
    assert approval_events[0].error is not None


def test_successful_promotion_emits_knowledge_acquired():
    mc = MissionControl()
    request = mc.request_knowledge("x")
    for _ in range(4):
        mc.advance_knowledge(request.request_id)
    mc.advance_knowledge(request.request_id, human_approved=True, approved_by="founder")

    assert len(mc.audit.of_type(EventType.KNOWLEDGE_ACQUIRED)) == 1


def test_self_development_lifecycle_emits_start_and_completion_events():
    mc = MissionControl()
    item = mc.propose_self_development(
        SelfDevelopmentType.PENDING_CAPABILITY, "Desktop.WindowDetect"
    )
    mc.self_development.transition(item.item_id, SelfDevelopmentState.ACCEPTED)
    mc.self_development.transition(item.item_id, SelfDevelopmentState.IN_PROGRESS)
    mc.complete_self_development(item.item_id)

    assert len(mc.audit.of_type(EventType.SELF_DEVELOPMENT_STARTED)) == 1
    assert len(mc.audit.of_type(EventType.SELF_DEVELOPMENT_COMPLETED)) == 1
