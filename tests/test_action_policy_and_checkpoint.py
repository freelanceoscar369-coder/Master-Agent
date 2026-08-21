"""Ordinary work runs itself; only the real boundaries hold it.

The Planner was being told that "any step that changes something is held
automatically for the founder's approval". That is not Founder Edition's
policy and never was. Rule 5's pre-grant loop authorises each Executive's
reversible actions at boot, so writing a new file runs on its own; what is
held is destructive, financial, and private-material-to-a-third-party.

A test in this repository had pinned the wrong version, which is how the
drift survived. These are the barrier against that happening again: every
tier asserted together, so a change that quietly widens one has to argue
with the others.

Separately, and deliberately not merged with any of it: when the founder
ASKS to see something before a later action, that is part of the objective
rather than a policy matter, and the plan has to carry it.
"""
from __future__ import annotations

import pytest

from master_agent.permissions.permission_system import (
    ApprovalRequired,
    GrantScope,
    PermissionSystem,
)
from master_agent.plugins.base import RiskTier


def founder_edition_permissions(*executives: str) -> PermissionSystem:
    """Rule 5's pre-grant, reproduced: each Executive's own reversible
    actions are authorised at boot. Reproduced rather than imported
    because the composition root does a great deal else on import."""
    permissions = PermissionSystem()
    for executive in executives:
        for capability in ("write_file", "create_folder", "write_document",
                           "extract_text", "transform", "delete_folder"):
            permissions.grant(executive, capability,
                              GrantScope.ALWAYS_FOR_CAPABILITY)
    return permissions


class TestTheActionPolicy:
    """All five tiers, together."""

    def test_read_only_needs_no_approval(self):
        PermissionSystem().check("document", "extract_text", RiskTier.READ_ONLY)

    def test_a_reversible_write_runs_automatically_in_founder_edition(self):
        """The correction. A new file, a new folder, a revised copy: the
        founder already asked for the work, and Rule 5 authorised the
        tier."""
        permissions = founder_edition_permissions("filesystem", "document")
        permissions.check("filesystem", "create_folder", RiskTier.REVERSIBLE_WRITE)
        permissions.check("filesystem", "write_file", RiskTier.REVERSIBLE_WRITE)
        permissions.check("document", "write_document", RiskTier.REVERSIBLE_WRITE)

    def test_an_irreversible_action_is_still_held(self):
        """And the standing grant does not satisfy it -- asserted here so
        the line above can never be read as blanket authority."""
        permissions = founder_edition_permissions("filesystem")
        with pytest.raises(ApprovalRequired):
            permissions.check("filesystem", "delete_folder", RiskTier.IRREVERSIBLE)

    def test_a_paid_provider_is_held(self):
        from dataclasses import dataclass

        from master_agent.ai_infrastructure.approval import PAID, approval_needed

        @dataclass
        class Profile:
            cost: float
            privacy: str

        assert approval_needed(Profile(cost=0.02, privacy="private"),
                               "unrestricted") == PAID

    def test_sensitive_material_to_a_third_party_is_held(self):
        from dataclasses import dataclass

        from master_agent.ai_infrastructure.approval import (
            SENSITIVE_THIRD_PARTY,
            approval_needed,
        )

        @dataclass
        class Profile:
            cost: float
            privacy: str

        assert approval_needed(Profile(cost=0.0, privacy="cloud"),
                               "sensitive") == SENSITIVE_THIRD_PARTY

    def test_free_unrestricted_work_asks_nobody(self):
        from dataclasses import dataclass

        from master_agent.ai_infrastructure.approval import approval_needed

        @dataclass
        class Profile:
            cost: float
            privacy: str

        assert approval_needed(Profile(cost=0.0, privacy="cloud"),
                               "unrestricted") is None


class TestThePlannerNoLongerClaimsOtherwise:

    @pytest.fixture
    def prompt(self):
        from master_agent.planner.catalogue import CapabilityOption
        from master_agent.planner.plan import Intent
        from master_agent.planner.prompting import build_prompt

        return build_prompt(
            Intent(goal="do some multi-step work"),
            (CapabilityOption(name="Document.WriteDocument",
                              required_args=("path", "content"),
                              args_complete=True),),
        )

    def test_the_false_rule_is_gone(self, prompt):
        lowered = prompt.lower()
        assert "is held automatically for the founder's approval" not in lowered
        assert "read-only steps are never held" not in lowered

    def test_it_says_ordinary_work_runs_on_its_own(self, prompt):
        lowered = prompt.lower()
        assert "do not invent permission steps" in lowered
        assert "runs on its own and needs no approval step" in lowered

    def test_it_names_the_real_boundaries(self, prompt):
        lowered = prompt.lower()
        for boundary in ("destructive or irreversible", "spending money",
                         "sending private material"):
            assert boundary in lowered

    def test_the_boundaries_are_not_the_planners_job(self, prompt):
        assert "whether or not you mention them" in prompt.lower()


class TestTheFounderRequestedCheckpoint:
    """A different thing entirely, and it must stay different."""

    @pytest.fixture
    def prompt(self):
        from master_agent.planner.catalogue import CapabilityOption
        from master_agent.planner.plan import Intent
        from master_agent.planner.prompting import build_prompt

        return build_prompt(
            Intent(goal="anything"),
            (CapabilityOption(name="Document.WriteDocument",
                              required_args=("path", "content"),
                              args_complete=True),),
        )

    def test_the_planner_is_taught_to_mark_it(self, prompt):
        assert "founder_checkpoint" in prompt

    def test_it_is_taught_as_part_of_the_objective(self, prompt):
        lowered = prompt.lower()
        assert "that is part of what was asked for" in lowered

    def test_it_is_only_for_when_the_objective_asks(self, prompt):
        lowered = prompt.lower()
        assert "only when the objective asked for one" in lowered
        assert "improve this file and save a copy" in lowered

    def test_it_is_not_how_policy_gates_are_handled(self, prompt):
        """Marking a destructive step would ask the founder twice."""
        assert "would ask the founder twice" in prompt.lower()

    def test_the_example_carries_a_binding(self, prompt):
        """The founder must see what earlier steps actually produced, so
        the marked step is one whose content is bound, not predicted."""
        assert '"founder_checkpoint"' in prompt
        assert '"input_bindings": {"content": {"from_step"' in prompt


class TestTheStepCarriesIt:
    """The declaration has to survive into the plan object itself."""

    def test_a_step_can_declare_a_checkpoint(self):
        from master_agent.planner.plan import Step

        step = Step(step_id="s", capability="Document.WriteDocument", payload={})
        assert hasattr(step, "founder_checkpoint")
        assert step.founder_checkpoint == ""

    def test_it_defaults_to_absent(self):
        """Every mission that did not ask for one gets none."""
        from master_agent.planner.plan import Step

        assert not Step(step_id="s", capability="X", payload={}).founder_checkpoint


class TestOneFieldOneMeaningEndToEnd:
    """`founder_checkpoint` must be the same field everywhere it appears.

    The canonical JSON shape omitted it while the prose taught it, which
    left the Planner with two instructions and no way to reconcile them.
    """

    def test_the_canonical_shape_declares_it(self):
        from master_agent.planner.prompting import PLAN_SHAPE

        assert '"founder_checkpoint": ""' in PLAN_SHAPE

    def test_the_shape_and_the_step_agree(self):
        import json

        from master_agent.planner.plan import Step
        from master_agent.planner.prompting import PLAN_SHAPE

        # The shape is an example, not schema, so its placeholders are
        # prose; the keys are what must line up.
        shape_keys = set(
            json.loads(
                PLAN_SHAPE.replace(
                    '"<exactly one name from the catalogue above>"', '"X"'
                ).replace('{"<argument>": "<value>"}', "{}")
                .replace('"low | normal | high | critical"', '"normal"')
                .replace('"trivial | small | moderate | large"', '"moderate"')
            )["steps"][0]
        )
        assert "founder_checkpoint" in shape_keys
        assert hasattr(Step(step_id="s", capability="X", payload={}),
                       "founder_checkpoint")

    def test_parsing_reads_the_same_field(self):
        from master_agent.planner.catalogue import CapabilityOption
        from master_agent.planner.parsing import validate

        catalogue = (CapabilityOption(name="Document.WriteDocument",
                                      required_args=("path", "content"),
                                      args_complete=True),)
        plan, refusal = validate({"steps": [{
            "id": "s", "capability": "Document.WriteDocument",
            "payload": {"path": "a.txt", "content": "x"}, "depends_on": [],
            "founder_checkpoint": "the changes, before writing",
            "success": {"description": "written"},
        }]}, catalogue)

        assert refusal is None
        assert plan.steps[0].founder_checkpoint == "the changes, before writing"

    def test_empty_means_no_checkpoint_everywhere(self):
        from master_agent.planner.catalogue import CapabilityOption
        from master_agent.planner.parsing import validate
        from master_agent.planner.plan import Step
        from master_agent.planner.prompting import PLAN_SHAPE

        assert '"founder_checkpoint": ""' in PLAN_SHAPE
        assert Step(step_id="s", capability="X", payload={}).founder_checkpoint == ""

        catalogue = (CapabilityOption(name="Document.WriteDocument",
                                      required_args=("path", "content"),
                                      args_complete=True),)
        plan, _ = validate({"steps": [{
            "id": "s", "capability": "Document.WriteDocument",
            "payload": {"path": "a.txt", "content": "x"}, "depends_on": [],
            "founder_checkpoint": "",
            "success": {"description": "written"},
        }]}, catalogue)
        assert plan.steps[0].founder_checkpoint == ""

    def test_there_is_no_second_representation(self):
        """One field, one meaning. A parallel spelling would let two parts
        of the system disagree about whether a founder is waiting."""
        import pathlib

        planner = pathlib.Path("src/master_agent/planner")
        for rival in ("checkpoint_required", "needs_review", "pause_before",
                      "founder_review", "requires_checkpoint"):
            for module in planner.glob("*.py"):
                assert rival not in module.read_text(encoding="utf-8"), (
                    f"{module.name} introduces a second spelling: {rival}"
                )


class TestMutationFollowsTheObjective:
    """The "never overwrite" rule came from one objective and must not
    become a universal law. Kalpavriksha follows what was asked."""

    @staticmethod
    def _text():
        from master_agent.planner.task_playbook import playbook_lines

        return " ".join(playbook_lines()).lower()

    def test_the_universal_prohibition_is_gone(self):
        assert "never modify or overwrite something the founder already has"             not in self._text()

    def test_a_requested_new_copy_preserves_the_original(self):
        text = self._text()
        assert "asked for a new or revised copy, leave the original where it is"             in text

    def test_a_requested_replacement_is_not_forbidden(self):
        """"Edit this and replace the current version" is a legitimate
        instruction, not something to refuse or quietly reinterpret."""
        text = self._text()
        assert "asked to edit or replace what is there, plan that" in text
        assert "it was requested" in text

    def test_silence_is_not_permission_to_replace(self):
        text = self._text()
        assert "said nothing either way, write something new" in text
        assert "not a detail to infer" in text

    def test_the_guidance_names_no_document_type(self):
        """Generic: it must read the same for a CV, a contract or a
        spreadsheet."""
        import re

        text = self._text()
        for word in ("cv", "resume", "curriculum", "docx"):
            assert not re.search(rf"(?<![a-z]){word}(?![a-z])", text)

    def test_summarising_implies_no_write_rule_at_all(self):
        """A read-only objective is untouched by any of this -- the
        guidance is about what to do WHEN writing, not an instruction to
        write."""
        text = self._text()
        assert "ordinary work runs on its own" in text
