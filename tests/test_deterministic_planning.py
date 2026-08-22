"""Reasoning is used because reasoning is REQUIRED — not because an
objective has more than one step.

## The defect

A founder asked, in one sentence:

    Create a folder called X on the Desktop. Then show me the text before
    you write it into notes.txt inside that folder. The text should be:
    Kalpavriksha checkpoint acceptance.

Everything needed is already explicit: both operations, the folder name,
the location, the file, the literal content, the ordering ("then"), and
the checkpoint ("show me ... before"). Nothing needs judgement,
discovery, or outside knowledge. It should reach **zero** reasoning
providers.

It reached all of them. `direct_plan()` recognised exactly two shapes — a
single typed action, and one narrowly dictated browser-observe-write
workflow — so this fell through to the AI Planner, which sent the whole
46-capability catalogue to a model to ask which capability creates a
folder. With Gemini's quota spent, the ladder then walked ChatGPT
Desktop, Perplexity, Kimi and finally Gemini web, and the founder was
told *"I couldn't plan that just now."*

The architectural defect is not provider availability. It is that
**deterministic multi-step work was not covered by the deterministic
planning lane.**

## How these tests are built

Provider contact is made to fail *structurally*, not checked afterwards:
the Planner is given a runner whose `run()` raises. A deterministic
objective that touches a provider cannot pass by accident.
"""
from __future__ import annotations

import pytest

from master_agent.capabilities.extraction import contracts_from_actions
from master_agent.capabilities.index import build_index
from master_agent.environment.browser_session import BrowserSessionManager
from master_agent.executor.executor import LocalExecutor
from master_agent.mission_control.capabilities import qualified_name
from master_agent.permissions.permission_system import PermissionSystem
from master_agent.planner.catalogue import catalogue_from_index
from master_agent.planner.direct import direct_plan
from master_agent.planner.plan import Intent
from master_agent.plugins.browser_plugin import BrowserPlugin
from master_agent.plugins.filesystem_plugin import FilesystemPlugin


class ForbiddenRunner:
    """A reasoning runner that must never be reached.

    Asserting on `last_attempts` afterwards would let a passing test coexist
    with a real provider call. Raising makes the contact itself the failure.
    """

    def __init__(self) -> None:
        self.calls = 0

    def run(self, prompt, request, **kwargs):
        self.calls += 1
        raise AssertionError(
            "PROVIDER MUST NOT BE CONTACTED — this objective is fully "
            f"determined by the founder's own words. Prompt was {len(prompt)} chars."
        )


@pytest.fixture
def options():
    """The catalogue the packaged application actually builds."""
    executor = LocalExecutor(PermissionSystem())
    contracts = []
    for plugin in (
        BrowserPlugin(executor, BrowserSessionManager(default_headless=False)),
        FilesystemPlugin(executor),
    ):
        actions = getattr(plugin, "_actions", None)
        if isinstance(actions, dict):
            contracts.extend(
                contracts_from_actions(actions, plugin.manifest.name, qualified_name)
            )
    index = build_index(contracts, loader={c.canonical_id: c for c in contracts}.get)
    return catalogue_from_index(index)


def capabilities_of(plan):
    return [step.capability for step in plan.steps]


def step_named(plan, capability):
    for step in plan.steps:
        if step.capability == capability:
            return step
    raise AssertionError(f"{capability} not in plan: {capabilities_of(plan)}")


# =========================================================================
# J · the exact Acceptance C objective — the one that started this
# =========================================================================

ACCEPTANCE_C = (
    "Create a folder called KV_CheckC_STOP_093303 on the Desktop. Then show me "
    "the text before you write it into notes.txt inside that folder. The text "
    "should be: Kalpavriksha checkpoint acceptance."
)


class TestAcceptanceCNeedsNoModel:

    def test_it_plans_without_contacting_any_provider(self, options):
        plan = direct_plan(Intent(goal=ACCEPTANCE_C), options)

        assert plan is not None, (
            "the founder's own fully-specified objective still needs a model"
        )

    def test_the_plan_is_create_folder_then_write_file(self, options):
        plan = direct_plan(Intent(goal=ACCEPTANCE_C), options)

        assert capabilities_of(plan) == [
            "Filesystem.CreateFolder",
            "Filesystem.WriteFile",
        ]

    def test_the_founders_literal_text_is_used_verbatim(self, options):
        """The content was supplied by the founder. It is not produced by
        an earlier step, so it needs no binding and certainly no model."""
        write = step_named(direct_plan(Intent(goal=ACCEPTANCE_C), options),
                           "Filesystem.WriteFile")

        assert write.payload["content"] == "Kalpavriksha checkpoint acceptance."

    def test_the_file_lands_inside_the_folder_that_was_just_created(self, options):
        plan = direct_plan(Intent(goal=ACCEPTANCE_C), options)
        create = step_named(plan, "Filesystem.CreateFolder")
        write = step_named(plan, "Filesystem.WriteFile")

        assert create.payload["name"] == "KV_CheckC_STOP_093303"
        assert create.payload["location"] == "desktop"
        assert write.payload["path"] == "KV_CheckC_STOP_093303/notes.txt"
        assert write.payload["location"] == "desktop"

    def test_the_write_waits_for_the_folder(self, options):
        """Ordering is the founder's own "then", and `depends_on` is the
        single authority for it. Step ids follow the existing per-mission
        unique-mark convention rather than positional names."""
        plan = direct_plan(Intent(goal=ACCEPTANCE_C), options)
        create = step_named(plan, "Filesystem.CreateFolder")
        write = step_named(plan, "Filesystem.WriteFile")

        assert write.depends_on == [create.step_id]
        assert create.depends_on == []
        assert create.step_id != write.step_id

    def test_show_me_before_you_write_becomes_a_founder_checkpoint(self, options):
        """"show me the text before you write it" is not something to
        reason about. It is the founder asking to see the payload, and
        `Step.founder_checkpoint` already exists to carry exactly that."""
        plan = direct_plan(Intent(goal=ACCEPTANCE_C), options)

        write = step_named(plan, "Filesystem.WriteFile")
        create = step_named(plan, "Filesystem.CreateFolder")

        assert write.founder_checkpoint, "the founder's own request was dropped"
        assert "Kalpavriksha checkpoint acceptance." in write.founder_checkpoint, (
            "the checkpoint must show the RESOLVED text, not describe it"
        )
        assert not create.founder_checkpoint, "only the held mutation waits"

    def test_no_extra_read_back_step_is_invented(self, options):
        """A model tends to append a ReadFile to 'verify' the write.
        Verification is the Runtime's own concern and the Filesystem
        gateway already re-observes the disk; planning must not simulate
        it with more execution work."""
        assert capabilities_of(direct_plan(Intent(goal=ACCEPTANCE_C), options)).count(
            "Filesystem.ReadFile"
        ) == 0

    def test_every_step_carries_a_checkable_expectation(self, options):
        """Mission Control refuses a step with no expectation, or an
        expectation stating no checks. A deterministic plan has to satisfy
        the same contract an AI plan does."""
        for step in direct_plan(Intent(goal=ACCEPTANCE_C), options).steps:
            assert step.expected_outcome is not None, step.capability
            assert step.expected_outcome.checks, step.capability


# =========================================================================
# A–E · deterministic cases that must never reach a provider
# =========================================================================


class TestDeterministicObjectivesNeverReachAProvider:

    @pytest.mark.parametrize("goal", [
        # B · explicit two-step workflow
        "Create a folder called Test on Desktop then write hello into a.txt inside it.",
        # C · the same, with a founder checkpoint
        "Create a folder called Test on Desktop then show me the text before you "
        "write hello into a.txt inside it.",
    ])
    def test_it_is_planned_locally(self, goal, options):
        assert direct_plan(Intent(goal=goal), options) is not None, goal

    def test_a_single_action_is_planned_locally_through_the_real_intent_layer(self, options):
        """A · the case that already worked. It goes through `IntentLayer`
        because that is what production does and what fills
        `Intent.capability` -- the single-capability path reads the pair the
        typed parser already knew rather than re-deriving it."""
        from master_agent.brain.intent import IntentLayer

        parsed = IntentLayer().parse("Create a folder called Test on Desktop")

        assert parsed.intent is not None, "the Intent Layer asked for clarification"
        assert direct_plan(parsed.intent, options) is not None

    def test_the_checkpoint_case_marks_only_the_write(self, options):
        plan = direct_plan(Intent(
            goal="Create a folder called Test on Desktop then show me the text "
                 "before you write hello into a.txt inside it."), options)

        write = step_named(plan, "Filesystem.WriteFile")
        assert write.founder_checkpoint
        assert "hello" in write.founder_checkpoint

    def test_a_dictated_browser_workflow_still_plans_locally(self, options):
        """E · the pre-existing capture workflow, which already used the
        real input-binding mechanism for a value an earlier step produces.
        This must keep working exactly as it did."""
        goal = (
            "Open a browser and navigate to https://example.com. Observe the page's "
            "actual title and final URL. Create a folder called KV_X on Desktop. "
            "Inside that folder create a text file called page_info.txt containing "
            "the title and URL you actually observed. Then close the browser."
        )
        plan = direct_plan(Intent(goal=goal), options)

        assert plan is not None
        write = step_named(plan, "Filesystem.WriteFile")
        assert write.input_bindings, (
            "an observed value must arrive by binding, never be predicted"
        )


# =========================================================================
# F–I · where reasoning is genuinely required, or nothing is
# =========================================================================


class TestJudgementStillGoesToTheReasoningLadder:
    """The goal is not "never use AI". It is "AI only when the plan cannot
    be certified deterministically"."""

    @pytest.mark.parametrize("goal", [
        "Compare these two documents and tell me which is stronger.",
        "Research current alternatives and recommend the best.",
        "Learn trading.",
        "Look at my resume files and improve the strongest one.",
    ])
    def test_real_judgement_is_not_planned_locally(self, goal, options):
        assert direct_plan(Intent(goal=goal), options) is None, (
            f"deterministic lane claimed an objective needing judgement: {goal}"
        )

    @pytest.mark.parametrize("goal", [
        # H · a dangerous action whose target is not certain
        "Delete the old stuff.",
        # I · a founder-owned value that was never supplied
        "Create a folder on the Desktop.",
        "Write hello into a file inside that folder.",
    ])
    def test_uncertainty_is_never_guessed(self, goal, options):
        assert direct_plan(Intent(goal=goal), options) is None, (
            f"deterministic lane guessed at: {goal}"
        )


# =========================================================================
# §13 · the token/cost guard
# =========================================================================


class TestNoPlanningPromptIsBuiltForADeterministicObjective:
    """Asking a model "which registered capability creates a folder?" costs
    the whole 46-capability catalogue in prompt tokens, every time, for an
    answer the Planner can already prove. Provider availability must never
    change that."""

    def test_the_planner_never_reaches_the_runner(self, options):
        from master_agent.planner.planner import Planner

        runner = ForbiddenRunner()
        planner = Planner(runner=runner, catalogue=options)

        outcome = planner.plan(Intent(goal=ACCEPTANCE_C), task_id="t", objective_id="o")

        assert runner.calls == 0, "a fully-specified objective was sent to a provider"
        assert outcome.planned, "the deterministic lane produced no plan"

    def test_it_holds_with_no_provider_configured_at_all(self, options):
        """The decisive operational property: this objective needs no
        Gemini key, no quota, no desktop application and no browser."""
        from master_agent.planner.planner import Planner

        planner = Planner(runner=ForbiddenRunner(), catalogue=options)
        outcome = planner.plan(Intent(goal=ACCEPTANCE_C), task_id="t", objective_id="o")

        assert outcome.planned
        assert [s.capability for s in outcome.plan.steps] == [
            "Filesystem.CreateFolder", "Filesystem.WriteFile",
        ]


class TestADictatedDeletionIsAlsoDeterministic:
    """Acceptance D's objective. The founder named the operation, the file,
    the folder and the place; nothing is inferred from argument shape, and
    the permission boundary still holds it at the irreversible tier — which
    is what makes planning it locally safe as well as correct.

    It was going to the reasoning ladder, so with quota spent the founder
    was told "I couldn't plan that just now" about deleting a file they had
    named exactly.
    """

    OBJECTIVE = ("Delete the file delete_me.txt inside the folder "
                 "KV_PermD_101648 on the Desktop")

    def test_it_plans_without_a_model(self, options):
        plan = direct_plan(Intent(goal=self.OBJECTIVE), options)

        assert plan is not None
        assert capabilities_of(plan) == ["Filesystem.DeleteFile"]

    def test_the_target_is_the_founders_own_file(self, options):
        step = step_named(direct_plan(Intent(goal=self.OBJECTIVE), options),
                          "Filesystem.DeleteFile")

        assert step.payload["path"] == "KV_PermD_101648/delete_me.txt"
        assert step.payload["location"] == "desktop"

    @pytest.mark.parametrize("goal", [
        "Delete the old stuff.",
        "Remove everything in the folder on the Desktop",
        "Delete that file.",
    ])
    def test_a_vague_deletion_is_never_compiled(self, goal, options):
        """The irreversible tier is exactly where a guess is least
        acceptable. Without a named file, a named folder and a named place,
        this refuses and the objective goes where uncertainty belongs."""
        assert direct_plan(Intent(goal=goal), options) is None, goal

    def test_the_planner_reaches_no_provider_for_it(self, options):
        from master_agent.planner.planner import Planner

        runner = ForbiddenRunner()
        outcome = Planner(runner=runner, catalogue=options).plan(
            Intent(goal=self.OBJECTIVE), task_id="t", objective_id="o")

        assert runner.calls == 0
        assert outcome.planned


class TestTheLaneRefusesWhatItCannotFullyCompile:
    """Two guards, both from one live failure.

    The golden mission's objective — open a browser, note the page's actual
    title and final URL, create a folder, write the observed values into a
    file, close the browser — was claimed by this lane and compiled into a
    TWO-step filesystem plan. Four steps the founder asked for were
    silently dropped, and the literal sentence "the observed title and
    final URL" was written to their Desktop instead of what the browser
    saw.

    Recognising part of a sentence is not understanding it, and a partial
    plan is worse than no plan because it runs.
    """

    GOLDEN = (
        "Open a browser, go to https://example.com, and note the page's actual "
        "title and final URL. Then create a folder called KV_G on the Desktop "
        "and write the observed title and final URL into a file called "
        "page_info.txt inside it. Then close the browser."
    )

    def test_an_objective_naming_foreign_work_is_not_claimed(self, options):
        from master_agent.planner.direct import _read_explicit_workflow

        assert _read_explicit_workflow(self.GOLDEN) is None, (
            "the lane claimed an objective containing operations it cannot compile"
        )

    def test_a_value_another_step_produces_is_never_treated_as_a_literal(self, options):
        from master_agent.planner.direct import _literal_content

        for referring in (
            "the observed title and final URL",
            "the title you actually observed",
            "the result",
            "the contents of that file",
        ):
            assert _literal_content(f"write {referring} into out.txt") is None, referring

    @pytest.mark.parametrize("goal", [
        "Create a folder called X on Desktop then read the file a.txt inside it.",
        "Create a folder called X on Desktop then summarise report.pdf into out.txt.",
        "Create a folder called X on Desktop then email me the results.",
    ])
    def test_mixed_objectives_fall_through_to_the_planner(self, goal, options):
        assert direct_plan(Intent(goal=goal), options) is None, goal

    def test_the_dictated_capture_workflow_is_still_reached(self, options):
        """The guard must not starve the lane that DOES compile browser
        work. `_local_capture_workflow` runs before this one and still
        claims its own shape."""
        goal = (
            "Open a browser and navigate to https://example.com. Observe the page's "
            "actual title and final URL. Create a folder called KV_X on Desktop. "
            "Inside that folder create a text file called page_info.txt containing "
            "the title and URL you actually observed. Then close the browser."
        )
        plan = direct_plan(Intent(goal=goal), options)

        assert plan is not None
        assert len(plan.steps) == 6
        assert step_named(plan, "Filesystem.WriteFile").input_bindings, (
            "the observed values must arrive by binding"
        )
