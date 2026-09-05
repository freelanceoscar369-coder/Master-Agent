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

import re

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


@pytest.fixture
def options_with_reasoning():
    """The same catalogue plus the Reasoning Executive.

    Kept separate from `options` deliberately: every other test in this
    module asserts what the deterministic lane does with the Browser and
    Filesystem catalogue, and silently widening that would change what
    those tests are measuring.
    """
    from master_agent.plugins.reasoning_plugin import ReasoningPlugin

    executor = LocalExecutor(PermissionSystem())
    contracts = []
    for plugin in (
        BrowserPlugin(executor, BrowserSessionManager(default_headless=False)),
        FilesystemPlugin(executor),
        ReasoningPlugin(executor),
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


class TestTheSameInstructionInEitherVoice:
    """"A file containing X" and "write X into a file" say one thing.

    Only the modifier form was recognised. A founder who phrased the
    identical instruction in the active voice got no local plan and was
    sent to a model to be told what they had already fully stated -- and
    when no model was reachable, the mission simply failed.
    """

    MODIFIER = (
        "Open a browser and navigate to https://example.com. Observe the page's "
        "actual title and final URL. Create a folder called KV_V on Desktop. "
        "Inside that folder create a text file called page_info.txt containing "
        "the title and URL you actually observed. Then close the browser."
    )
    ACTIVE = (
        "Open a browser, go to https://example.com, and note the page's actual "
        "title and final URL. Then create a folder called KV_V on the Desktop "
        "and write the observed title and final URL into a file called "
        "page_info.txt inside it. Then close the browser."
    )

    def test_both_voices_compile_to_the_same_plan(self, options):
        a = direct_plan(Intent(goal=self.MODIFIER), options)
        b = direct_plan(Intent(goal=self.ACTIVE), options)

        assert a is not None and b is not None
        assert [s.capability for s in a.steps] == [s.capability for s in b.steps]
        assert len(b.steps) == 6

    def test_the_active_voice_still_binds_rather_than_predicts(self, options):
        plan = direct_plan(Intent(goal=self.ACTIVE), options)
        write = step_named(plan, "Filesystem.WriteFile")

        assert write.input_bindings, "observed values must arrive by binding"
        assert "observed title" not in str(write.payload).lower(), (
            "the founder's phrase was written to disk instead of the page's values"
        )

    @pytest.mark.parametrize("goal", [
        # Observed, but the file's content was never tied to the page.
        "Open a browser, go to https://example.com and observe the title and url. "
        "Create a folder called A on Desktop with a file called n.txt. Close it.",
        # A containment phrase, but nothing observed.
        "Create a folder called A on the Desktop and write hello into a file "
        "called n.txt inside it. Then close the browser.",
    ])
    def test_widening_the_voice_did_not_widen_what_must_be_present(self, goal, options):
        from master_agent.planner.direct import _read_capture_request

        assert _read_capture_request(goal) is None, goal


class TestReasoningBelongsInTheStepNotTheChoiceOfSteps:
    """"Think of three short names for a gardening notes app and write
    them into names.txt on the Desktop."

    Nothing in that sentence says HOW. With `Reasoning.Transform` and
    `Filesystem.WriteFile` both registered, the shape is the only one they
    can form -- so choosing it needs no model. The old path paid a
    20,869-character catalogue prompt to be told the obvious, and lost the
    whole mission when every reasoning rung was out.

    A model is still needed. It is the only thing that can invent three
    names, and it is needed INSIDE the Transform.
    """

    GOAL = (
        "Think of three short names for a gardening notes app and write them "
        "into names.txt on the Desktop."
    )

    def test_it_compiles_to_transform_then_write(self, options_with_reasoning):
        plan = direct_plan(Intent(goal=self.GOAL), options_with_reasoning)

        assert plan is not None
        assert [s.capability for s in plan.steps] == [
            "Reasoning.Transform", "Filesystem.WriteFile",
        ]

    def test_the_model_is_asked_the_instruction_not_the_catalogue(self, options_with_reasoning):
        plan = direct_plan(Intent(goal=self.GOAL), options_with_reasoning)
        instruction = step_named(plan, "Reasoning.Transform").payload["instruction"]

        assert "gardening notes app" in instruction
        # The destination is not part of what to produce: Transform returns
        # text and must never be told to write a file.
        assert "names.txt" not in instruction
        assert "write them" not in instruction.lower()

    def test_the_content_is_bound_never_predicted(self, options_with_reasoning):
        plan = direct_plan(Intent(goal=self.GOAL), options_with_reasoning)
        write = step_named(plan, "Filesystem.WriteFile")

        assert write.payload.get("path") == "names.txt"
        assert "content" not in write.payload, "the answer was guessed at planning time"
        assert write.input_bindings["content"] == {
            "from_step": {"step_id": plan.steps[0].step_id, "field": "text"}
        }

    def test_this_step_declares_its_material_public(self, options_with_reasoning):
        """`Reasoning.Transform` defaults to `sensitive`, and rightly: its
        `context` is normally an earlier Step's output -- a document off
        the founder's disk. This lane builds a Transform with no `context`
        and no `depends_on`, so that material structurally cannot be
        present, and the contract requires a plan that knows this to say
        so.

        Measured before it was said: the Broker ruled every third-party
        provider NOT_PRIVATE, the only PRIVATE providers on this machine
        are disabled or absent, and selection refused before the founder
        could be offered the choice -- so the mission died with "none
        eligible" instead of with a question."""
        plan = direct_plan(Intent(goal=self.GOAL), options_with_reasoning)
        transform = step_named(plan, "Reasoning.Transform")

        assert transform.payload["sensitive"] is False
        assert "context" not in transform.payload
        assert transform.depends_on == []

    @pytest.mark.parametrize("goal", [
        # No verb of origination -- nothing is being invented.
        "Write hello into names.txt on the Desktop.",
        # A folder as well: another lane owns that shape.
        "Think of three names and create a folder called X on the Desktop.",
        # A page to open: not this lane's.
        "Think of three names for https://example.com and write them to n.txt on the Desktop.",
        # No destination the founder actually named.
        "Think of three short names for a gardening notes app.",
    ])
    def test_it_declines_everything_it_does_not_fully_recognise(self, goal, options):
        from master_agent.planner.direct import _read_generate_request

        assert _read_generate_request(goal) is None, goal


class TestNoStepIdIsEverReusedAcrossMissions:
    """A step id must be unique across every mission the process ever
    runs, not merely within its own plan.

    `RuntimeEngine._objective_of()` finds a task's objective by scanning
    every objective for a matching task id and returning the FIRST hit,
    so a reused id silently resolves to somebody else's mission.
    `_single_capability_plan` records this at length and obeys it; the
    multi-step lanes each carry a per-mission mark for the same reason.

    `_generate_then_write` shipped with "step_1"/"step_2" hard-coded, and
    the packaged application measured the cost: the plan was right, the
    reasoning ran, its Evidence came back matched -- and WriteFile was
    never dispatched, because its id collided with 26 earlier records in
    the founder's own plan history. Every source-path run had passed,
    because those had less history behind them.
    """

    GOALS = [
        "Think of three short names for a gardening notes app and write them "
        "into names.txt on the Desktop.",
        "Create a folder called KV_Ids on the Desktop. Then show me the text "
        "before you write it into notes.txt inside that folder. The text "
        "should be: hello.",
    ]

    def _ids(self, goal, options):
        plan = direct_plan(Intent(goal=goal), options)
        assert plan is not None, goal
        return [step.step_id for step in plan.steps]

    def test_two_runs_of_the_same_objective_share_no_step_id(
        self, options_with_reasoning
    ):
        for goal in self.GOALS:
            first = self._ids(goal, options_with_reasoning)
            second = self._ids(goal, options_with_reasoning)

            assert not (set(first) & set(second)), (
                f"a rerun reused {set(first) & set(second)} for: {goal}"
            )

    def test_no_plan_uses_a_bare_positional_id(self, options_with_reasoning):
        """"step_1" is the shape that collides. Nothing may emit it."""
        for goal in self.GOALS:
            for step_id in self._ids(goal, options_with_reasoning):
                assert not re.fullmatch(r"step_\d+", step_id), (
                    f"{step_id!r} is positional, so every mission emits it"
                )

    def test_dependencies_and_bindings_follow_the_unique_ids(
        self, options_with_reasoning
    ):
        """Making ids unique is only safe if everything pointing AT them
        moves too -- otherwise the step is unique and unreachable."""
        goal = self.GOALS[0]
        plan = direct_plan(Intent(goal=goal), options_with_reasoning)
        produced, consumer = plan.steps[0], plan.steps[1]

        assert consumer.depends_on == [produced.step_id]
        assert consumer.input_bindings["content"]["from_step"]["step_id"] == (
            produced.step_id
        )
class TestStateStatedInstructionsAreStillDictated:
    """A founder who says what must be TRUE has still dictated the work.

    Measured live 2026-09-05: an objective in this form compiled to None
    here, so it was escalated to model-backed requirement admission, which
    spent eight external calls failing to establish requirements for a
    folder and a text file. ADR-0027 names that exact case -- "creating a
    folder must not deliberate."

    "Ensure X exists" is the same instruction as "create X"; "ensure F
    contains exactly T" is the same instruction as "write T into F". The
    operations, arguments and ordering are all supplied either way.
    """

    def _plan(self, goal):
        from master_agent.planner.direct import _read_explicit_workflow
        return _read_explicit_workflow(goal)

    def test_ensure_exists_and_contains_compiles(self):
        ops = self._plan(
            "Ensure a folder Reports exists on my Desktop. Inside it ensure "
            "summary.txt contains exactly: quarter closed. Verify it, then report."
        )
        assert ops is not None
        assert [o.kind for o in ops] == ["create_folder", "write_file"]
        assert ops[0].payload == {"name": "Reports", "location": "desktop"}
        assert ops[1].payload["path"] == "Reports/summary.txt"
        assert ops[1].payload["content"] == "quarter closed"

    def test_a_trailing_instruction_is_not_swallowed_into_the_content(self):
        """The content stops at the sentence boundary. Writing "Verify it,
        then report." into the founder's file would be a wrong artifact
        that passes every existence check."""
        ops = self._plan(
            "Ensure a folder Notes exists in Documents. Inside it ensure "
            "log.md contains exactly: all clear. Then tell me it worked."
        )
        assert ops is not None
        assert ops[1].payload["content"] == "all clear"

    def test_the_older_imperative_phrasing_still_compiles(self):
        """The existing vocabulary must not regress."""
        ops = self._plan(
            "Create a folder called KV_Old on the Desktop. Then write hello "
            "into notes.txt inside that folder."
        )
        assert ops is not None
        assert [o.kind for o in ops] == ["create_folder", "write_file"]

    def test_a_filename_not_owning_a_contains_clause_is_not_a_destination(self):
        """`contains` is what makes the filename a destination. Without it
        a dotted token is just a token -- a version, a domain, a citation --
        and reading it as a file would invent a write nobody asked for."""
        assert self._plan(
            "Ensure a folder Reports exists on my Desktop. Mention v1.2 in "
            "the summary."
        ) is None

    def test_contains_without_a_stated_value_is_refused(self):
        """"Contains what the previous step produced" is not dictated."""
        assert self._plan(
            "Ensure a folder Reports exists on my Desktop. Inside it ensure "
            "summary.txt contains exactly: the title you found."
        ) is None

    def test_an_objective_naming_foreign_work_is_still_refused(self):
        """Compiling the recognised half would drop the rest, and a partial
        plan is worse than none because it runs."""
        assert self._plan(
            "Ensure a folder Reports exists on my Desktop. Research the "
            "market and ensure summary.txt contains exactly: done."
        ) is None

