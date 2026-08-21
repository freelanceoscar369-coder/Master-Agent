"""A pause the founder asked for, honoured with the machinery that exists.

The objective said "show me what you propose to improve and ask for my
permission before changing any CV". That is not a policy question -- the
write is reversible and Rule 5 already authorised it -- so no permission
gate would ever have stopped for it. It is part of what was asked for.

Two properties carry the weight here:

* **the founder sees what the mission actually produced.** The review
  happens after `input_bindings` resolve, so the preview is built from the
  payload that will execute, not from the Planner's guess about a document
  nobody had written yet;
* **Continue is not permission.** It satisfies the founder's own request
  and grants no capability authority whatsoever.
"""
from __future__ import annotations

import pytest

from master_agent.mission_control.approvals import (
    FOUNDER_CHECKPOINT,
    PERMISSION,
    ApprovalState,
)
from master_agent.mission_control.capabilities import (
    CapabilityDescriptor,
    qualified_name,
)
from master_agent.mission_control.executives import ExecutiveHealth
from master_agent.mission_control.mission_control import MissionControl
from master_agent.mission_control.tasks import Objective, Task, TaskState
from master_agent.runtime.engine import RuntimeEngine
from master_agent.runtime.gateway import GatewayResult
from master_agent.verification.evidence import ExpectedOutcome

PROPOSAL = "Add a measurable outcome to each role, and a summary at the top."


class Harness:
    """One mission: a step that produced a proposal, and a step that would
    write it -- which the founder asked to see first."""

    def __init__(self, checkpoint: str = "the proposed changes, before writing"):
        self.invocations: list[dict] = []
        self.approved_payloads: list[dict] = []
        self.mc = MissionControl()
        for executive, capability in (("reasoning", "transform"),
                                      ("document", "write_document")):
            self.mc.register_executive(
                executive_id=executive, version="0.1.0",
                capabilities=[CapabilityDescriptor(
                    qualified_name=qualified_name(executive, capability),
                    executive_id=executive, capability=capability,
                )],
                health=ExecutiveHealth.HEALTHY,
            )
            self.mc.mark_executive_ready(executive)

        harness = self

        class Gate:
            """Policy says yes -- a reversible write is pre-granted. If the
            mission still pauses, it is the founder's own checkpoint."""

            def check(self, request):
                harness.approved_payloads.append(dict(request.payload))

        class Gateway:
            def invoke(self, capability, payload):
                harness.invocations.append(dict(payload))
                return GatewayResult(success=True, output={"written": True})

            def verify(self, capability, payload, expected):
                return None

        self.engine = RuntimeEngine(self.mc, approval_gate=Gate())
        self.engine.register_gateway("reasoning", Gateway())
        self.engine.register_gateway("document", Gateway())

        write = Task(
            capability="Document.WriteDocument", task_id="step_2",
            payload={"path": "revised.docx"},
            depends_on=["step_1"],
            expected_outcome=ExpectedOutcome(description="written"),
        )
        write.input_bindings = {
            "content": {"from_step": {"step_id": "step_1", "field": "text"}}
        }
        write.founder_checkpoint = checkpoint

        self.objective = self.mc.submit_objective(Objective(
            description="improve the document",
            tasks=[Task(capability="Reasoning.Transform", task_id="step_1"), write],
        ))
        source = self.objective.task("step_1")
        source.state = TaskState.COMPLETED
        source.result = {"text": PROPOSAL}
        source.evidence = {
            "evidence_id": "ev-1", "worker": "reasoning",
            "environment": "reasoning", "captured_at": "2026-08-21T00:00:00+00:00",
            "expected": {"description": "reasoned", "checks": []},
            "observation": {"text": PROPOSAL}, "verdict": "matched",
            "check_results": [], "errors": [],
        }

    def run(self, cycles: int = 6) -> None:
        for _ in range(cycles):
            if not self.engine.run_once():
                break

    @property
    def open_review(self):
        return next(
            (a for a in self.mc.approvals.all() if a.kind == FOUNDER_CHECKPOINT),
            None,
        )


class TestItPausesWhereTheFounderAsked:

    def test_the_write_does_not_happen_yet(self):
        harness = Harness()
        harness.run()
        assert harness.invocations == [], "the step ran before the founder looked"

    def test_a_review_is_opened(self):
        harness = Harness()
        harness.run()
        review = harness.open_review
        assert review is not None
        assert review.state is ApprovalState.PENDING

    def test_it_is_not_a_permission_question(self):
        harness = Harness()
        harness.run()
        review = harness.open_review
        assert review.kind == FOUNDER_CHECKPOINT
        assert review.kind != PERMISSION
        assert review.requested_by == "founder_checkpoint"

    def test_no_risk_tier_is_claimed(self):
        """It is not a risk question, and saying one would invite a reader
        to treat Continue as permission for that tier."""
        harness = Harness()
        harness.run()
        assert harness.open_review.risk_tier == ""

    def test_a_task_without_one_never_pauses(self):
        """Ordinary work runs. Almost every step has no checkpoint, and
        pausing them would be ignoring an instruction already given."""
        harness = Harness(checkpoint="")
        harness.run()
        assert harness.invocations, "an ordinary reversible write did not run"
        assert harness.open_review is None


class TestTheFounderSeesWhatWasActuallyProduced:

    def test_the_preview_holds_the_resolved_value(self):
        harness = Harness()
        harness.run()
        assert PROPOSAL in harness.open_review.reason

    def test_the_preview_is_not_the_checkpoint_description(self):
        """`founder_checkpoint` says WHY they are being asked; the preview
        is WHAT they are being asked about."""
        harness = Harness()
        harness.run()
        review = harness.open_review
        assert review.reason != review.objective
        assert review.objective == "the proposed changes, before writing"

    def test_the_review_happens_after_binding_resolution(self):
        """If it happened earlier, `content` would not exist yet -- the
        Planner never wrote a literal for it."""
        harness = Harness()
        harness.run()
        assert "content" not in harness.objective.task("step_2").payload
        assert PROPOSAL in harness.open_review.reason

    def test_plumbing_is_left_out(self):
        from master_agent.runtime.founder_review import preview_of

        text = preview_of({
            "path": "revised.docx", "content": PROPOSAL,
            "session_id": "kv-1", "overwrite": False,
        })
        assert "revised.docx" in text and PROPOSAL in text
        assert "session_id" not in text and "overwrite" not in text

    def test_a_very_long_value_is_shortened_and_says_so(self):
        from master_agent.runtime.founder_review import MAX_VALUE_CHARS, preview_of

        text = preview_of({"content": "x" * (MAX_VALUE_CHARS + 5_000)})
        assert len(text) < MAX_VALUE_CHARS + 200
        assert "shortened" in text


class TestContinue:

    def test_the_same_task_resumes(self):
        harness = Harness()
        harness.run()
        review_id = harness.open_review.approval_id

        harness.mc.approve(review_id, founder="onkar")
        harness.run()

        assert harness.invocations, "Continue did not resume the work"
        assert harness.objective.task("step_2").state is TaskState.COMPLETED

    def test_the_reviewed_payload_is_the_one_that_executes(self):
        """The whole point. What was shown is what runs."""
        harness = Harness()
        harness.run()
        shown = harness.open_review.reason
        harness.mc.approve(harness.open_review.approval_id, founder="onkar")
        harness.run()

        executed = harness.invocations[-1]
        assert executed["content"] == PROPOSAL
        assert PROPOSAL in shown

    def test_no_second_mission_is_created(self):
        harness = Harness()
        harness.run()
        harness.mc.approve(harness.open_review.approval_id, founder="onkar")
        harness.run()

        assert len(harness.mc.dispatcher.objectives()) == 1

    def test_continue_grants_no_permission_authority(self):
        """The invariant that keeps the two concepts apart: satisfying a
        founder's review must never authorise a capability."""
        harness = Harness()
        harness.run()
        harness.mc.approve(harness.open_review.approval_id, founder="onkar")
        harness.run()

        permissions = getattr(harness.engine, "_permissions", None)
        assert permissions is None, "the runtime should hold no permission system"
        # And nothing recorded a permission-kind decision.
        assert all(a.kind == FOUNDER_CHECKPOINT for a in harness.mc.approvals.all())


class TestStop:

    def test_the_action_does_not_happen(self):
        harness = Harness()
        harness.run()
        harness.mc.reject(harness.open_review.approval_id, founder="onkar",
                          note="not yet")
        harness.run()

        assert harness.invocations == [], "the step ran after the founder said Stop"

    def test_the_task_does_not_stay_waiting_forever(self):
        harness = Harness()
        harness.run()
        harness.mc.reject(harness.open_review.approval_id, founder="onkar")
        harness.run()

        assert harness.objective.task("step_2").state is not TaskState.DISPATCHED

    def test_the_reason_says_the_founder_decided(self):
        """Read later, this must not look like the work went wrong."""
        harness = Harness()
        harness.run()
        harness.mc.reject(harness.open_review.approval_id, founder="onkar",
                          note="I want to reword it myself")
        harness.run()

        task = harness.objective.task("step_2")
        errors = " ".join(getattr(task, "errors", ()) or ()) + str(
            getattr(task, "error", "") or ""
        )
        assert "founder" in errors.lower()


class TestIdempotence:
    """The Runtime re-consults this every cycle while a task waits."""

    def test_asking_repeatedly_opens_one_question(self):
        harness = Harness()
        harness.run(cycles=8)
        reviews = [a for a in harness.mc.approvals.all()
                   if a.kind == FOUNDER_CHECKPOINT]
        assert len(reviews) == 1
