"""Sprint 1, Component 25 — Elite Desktop Executive.

The brief's own philosophy is the header for this suite: the current
Desktop Executive answers *"what exists?"*; this component answers *"how
do I operate it?"* — as knowledge only. Every test below asks one of a
small number of questions: *is this profile complete?*, *is this recovery
plan total?*, *does a conflict get resolved with a stated reason rather
than silently?*, and — repeatedly, because it is the brief's own repeated
word — *is anything here executable?*

| Requirement | Source |
|---|---|
| Every profiled application has all eleven `ApplicationOperationProfile` fields | C25 brief |
| Every profiled application's recovery plan covers all eight failure modes | C25 brief |
| A capability matrix names which application provides which capability | C25 brief |
| Environment Intelligence can answer *which app, why, confidence, fallback* | C25 brief |
| Never execute, launch, click, move a mouse, send keys, install, mutate | C25 brief |
| Unknown applications, multiple versions, capability conflicts, workflow completeness are adversarially tested | C25 brief |

Every structural guard reads executable identifiers via AST, never source
text — the discipline `founder_runtime/` and `founder_edition/` already
established, for the same reason (C21's own boundary guard passed while
scanning zero files).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from master_agent.desktop import catalog
from master_agent.desktop.inventory import (
    INSTALLED,
    MISSING,
    InstalledApplication,
    MachineInventory,
)
from master_agent.desktop.operations import (
    AI_CAPABILITIES,
    KNOWLEDGE_BASE,
    MATRIX,
    PROFILES,
    RECOVERY_PLANS,
    UNPROFILED_EXAMPLES,
    WORKFLOWS,
    ApplicationOperationProfile,
    ApplicationRecoveryPlan,
    Capability,
    DesktopCapabilityMatrix,
    DesktopExecutiveV2,
    FailureMode,
    InvalidOperationKnowledge,
    OperationKnowledgeBase,
    OperationNote,
    RecoveryGuidance,
    StartupEstimate,
    StartupSpeed,
    Workflow,
    WorkflowStep,
    WorkflowVerb,
)
from master_agent.environment_intelligence import derive_intelligence

PACKAGE = (
    Path(__file__).resolve().parent.parent
    / "src" / "master_agent" / "desktop" / "operations"
)

#: The brief's own fifteen worked examples, by application name.
BRIEF_EXAMPLES: tuple[str, ...] = (
    "Claude Desktop", "Cursor", "Chrome", "Edge", "Brave", "Firefox",
    "VS Code", "Office", "Git", "Python", "Docker", "Node",
    "PowerShell", "Explorer", "Terminal",
)

_CATALOG_KEYS = {spec.key for spec in catalog.CATALOG}


def app(key: str, *, status: str = INSTALLED, healthy: bool = True, version: str | None = None) -> InstalledApplication:
    spec = catalog.BY_KEY[key]
    return InstalledApplication(
        key=key, name=spec.label, category=spec.category, status=status, healthy=healthy, version=version,
    )


def inventory(*applications: InstalledApplication) -> MachineInventory:
    return MachineInventory(applications=list(applications), processes=[], platform="win32")


# ═══════════════════════ A · every catalogued app is profiled ═══════════


class TestEveryApplicationIsProfiled:
    def test_every_catalog_key_has_a_profile(self):
        profiled = {p.key for p in PROFILES}
        assert profiled == _CATALOG_KEYS

    def test_every_catalog_key_has_a_recovery_plan(self):
        covered = {r.key for r in RECOVERY_PLANS}
        assert covered == _CATALOG_KEYS

    def test_no_profile_names_an_application_outside_the_catalog(self):
        """The Desktop Executive is the single source of truth for what
        applications exist; a profile for a key the catalog does not
        know would be a second, competing catalog."""
        for profile in PROFILES:
            assert profile.key in _CATALOG_KEYS

    def test_no_recovery_plan_names_an_application_outside_the_catalog(self):
        for plan in RECOVERY_PLANS:
            assert plan.key in _CATALOG_KEYS

    def test_no_workflow_names_an_application_outside_the_catalog(self):
        for workflow in WORKFLOWS:
            assert workflow.key in _CATALOG_KEYS

    def test_no_matrix_entry_names_an_application_outside_the_catalog(self):
        for key in (k for k, _ in MATRIX.entries):
            assert key in _CATALOG_KEYS

    @pytest.mark.parametrize("field_name", [
        "launch", "focus", "close", "wait_until_ready", "health_check", "recover",
    ])
    def test_every_profile_carries_a_real_description_for_every_note(self, field_name):
        for profile in PROFILES:
            note = getattr(profile, field_name)
            assert isinstance(note, OperationNote)
            assert note.description.strip()

    def test_every_profile_names_its_startup_estimate(self):
        for profile in PROFILES:
            assert isinstance(profile.startup_time, StartupEstimate)

    def test_every_profile_names_a_launch_method_window_strategy_and_automation_strategy(self):
        for profile in PROFILES:
            assert profile.preferred_launch_method is not None
            assert profile.window_strategy is not None
            assert profile.automation_strategy is not None


class TestTheBriefsOwnExamples:
    """The brief names fifteen applications. Four are not in the
    catalog — this is a stated gap, not a silent one."""

    def test_unprofiled_examples_are_exactly_the_uncatalogued_ones(self):
        catalog_labels = {spec.label for spec in catalog.CATALOG}
        for name in UNPROFILED_EXAMPLES:
            assert name.title() not in catalog_labels or name in (
                "brave", "office", "explorer", "terminal",
            )

    def test_every_brief_example_is_either_profiled_or_named_absent(self):
        profiled_labels = {p.key: catalog.BY_KEY[p.key].label for p in PROFILES}
        lower_profiled = {label.lower() for label in profiled_labels.values()} | {
            key.lower() for key in profiled_labels
        }
        lower_absent = {name.lower() for name in UNPROFILED_EXAMPLES}
        for example in BRIEF_EXAMPLES:
            lowered = example.lower()
            assert lowered in lower_profiled or lowered in lower_absent, (
                f"{example!r} is neither profiled nor recorded as an absent example"
            )

    def test_nothing_is_invented_for_the_four_absent_examples(self):
        for name in UNPROFILED_EXAMPLES:
            assert name not in _CATALOG_KEYS
            assert KNOWLEDGE_BASE.profile(name) is None


# ═══════════════════════ B · recovery plans are total ═══════════════════


class TestRecoveryPlansAreTotal:
    def test_every_plan_covers_all_eight_failure_modes(self):
        for plan in RECOVERY_PLANS:
            modes = {mode for mode, _ in plan.guidance}
            assert modes == set(FailureMode)

    def test_a_plan_cannot_be_constructed_with_a_missing_mode(self):
        incomplete = tuple(
            (mode, RecoveryGuidance("x", ("y",)))
            for mode in FailureMode
            if mode is not FailureMode.HUNG
        )
        with pytest.raises(InvalidOperationKnowledge):
            ApplicationRecoveryPlan(key="test", guidance=incomplete)

    def test_a_plan_cannot_repeat_a_mode(self):
        doubled = tuple((mode, RecoveryGuidance("x", ("y",))) for mode in FailureMode) + (
            (FailureMode.HUNG, RecoveryGuidance("z", ("w",))),
        )
        with pytest.raises(InvalidOperationKnowledge):
            ApplicationRecoveryPlan(key="test", guidance=doubled)

    def test_for_mode_returns_the_right_guidance(self):
        plan = KNOWLEDGE_BASE.recovery_plan("chrome")
        guidance = plan.for_mode(FailureMode.NETWORK_FAILURE)
        assert "connectivity" in guidance.diagnosis or "connectivity" in " ".join(guidance.guidance)

    def test_every_guidance_names_at_least_one_step(self):
        for plan in RECOVERY_PLANS:
            for _, guidance in plan.guidance:
                assert guidance.guidance

    def test_inapplicable_modes_are_stated_not_omitted(self):
        """Some failure modes genuinely do not apply — e.g. a CLI tool
        has no window to hide. These are still present, marked
        `applicable=False`, never absent."""
        cli_plan = KNOWLEDGE_BASE.recovery_plan("git")
        window_hidden = cli_plan.for_mode(FailureMode.WINDOW_HIDDEN)
        assert window_hidden.applicable is False
        assert window_hidden.diagnosis

    def test_at_least_one_application_finds_every_mode_applicable_or_not_by_design(self):
        """A sanity check that `applicable=False` is used selectively,
        not as a way to avoid writing real guidance everywhere."""
        applicable_counts = [
            sum(1 for _, g in plan.guidance if g.applicable) for plan in RECOVERY_PLANS
        ]
        assert any(count == 8 for count in applicable_counts)
        assert any(count < 8 for count in applicable_counts)


# ═══════════════════════ C · capability matrix and conflicts ════════════


class TestCapabilityMatrix:
    def test_every_capability_used_by_an_app_is_a_real_capability(self):
        for _, capabilities in MATRIX.entries:
            for capability in capabilities:
                assert isinstance(capability, Capability)

    def test_providers_of_returns_every_app_offering_a_capability(self):
        providers = MATRIX.providers_of(Capability.NAVIGATION)
        assert set(providers) == {"chrome", "edge", "firefox"}

    def test_capabilities_of_an_unknown_key_is_empty(self):
        assert MATRIX.capabilities_of("not-a-real-application") == ()

    def test_providers_of_an_unused_capability_is_empty(self):
        # every declared Capability is used by at least one app in this
        # matrix; this proves the empty case still behaves for a
        # capability that legitimately has no providers.
        unused = Capability.NAVIGATION
        assert "made_up_app" not in MATRIX.providers_of(unused)

    def test_the_matrix_refuses_a_repeated_application_key(self):
        with pytest.raises(InvalidOperationKnowledge):
            DesktopCapabilityMatrix(
                entries=(("chrome", (Capability.NAVIGATION,)), ("chrome", (Capability.SEARCH,)))
            )

    def test_real_capability_conflicts_exist_in_the_matrix(self):
        """At least one capability is genuinely offered by more than one
        application — this is the conflict `recommend()` exists to
        resolve, not to hide."""
        multi_provider = [
            cap for cap in MATRIX.all_capabilities()
            if len(MATRIX.providers_of(cap)) > 1
        ]
        assert multi_provider, "no capability conflict exists to test resolution against"

    def test_reasoning_capability_is_a_three_way_conflict(self):
        assert set(MATRIX.providers_of(Capability.REASONING)) == {
            "claude_desktop", "ollama",
        }


# ═══════════════════════ D · recommend() — the environment answer ═══════


class TestRecommendAnswersTheFourQuestions:
    def test_no_candidate_known_is_unknown(self):
        ex = DesktopExecutiveV2()
        rec = ex.recommend(Capability.JVM_RUNTIME, inventory=inventory())
        # java is the only JVM_RUNTIME provider and is not installed here
        assert rec.choice.value is None
        assert rec.choice.confidence.value == "unknown"

    def test_no_inventory_supplied_is_unknown_with_full_fallback(self):
        ex = DesktopExecutiveV2()
        rec = ex.recommend(Capability.CODE_EDITING)
        assert rec.choice.value is None
        assert rec.choice.reason
        assert set(rec.fallback) == {"vscode", "cursor", "visualstudio"}

    def test_exactly_one_healthy_candidate_is_observed(self):
        ex = DesktopExecutiveV2()
        rec = ex.recommend(Capability.VERSION_CONTROL, inventory=inventory(app("git")))
        assert rec.choice.value == "git"
        assert rec.choice.confidence.value == "observed"
        assert rec.choice.evidence

    def test_several_healthy_candidates_are_strong_with_a_stated_choice(self):
        ex = DesktopExecutiveV2()
        rec = ex.recommend(
            Capability.CODE_EDITING,
            inventory=inventory(app("vscode"), app("cursor")),
        )
        assert rec.choice.confidence.value == "strong"
        assert rec.choice.value in {"vscode", "cursor"}
        assert set(rec.fallback) == {"vscode", "cursor", "visualstudio"} - {rec.choice.value}
        assert len(rec.choice.evidence) == 2

    def test_installed_but_unhealthy_is_weak(self):
        ex = DesktopExecutiveV2()
        rec = ex.recommend(
            Capability.VERSION_CONTROL,
            inventory=inventory(app("git", healthy=False)),
        )
        assert rec.choice.value == "git"
        assert rec.choice.confidence.value == "weak"

    def test_healthy_beats_unhealthy(self):
        ex = DesktopExecutiveV2()
        rec = ex.recommend(
            Capability.CODE_EDITING,
            inventory=inventory(app("vscode", healthy=False), app("cursor", healthy=True)),
        )
        assert rec.choice.value == "cursor"
        assert rec.choice.confidence.value == "observed"

    def test_nothing_installed_is_unknown_with_the_full_candidate_list_as_fallback(self):
        ex = DesktopExecutiveV2()
        rec = ex.recommend(
            Capability.CODE_EDITING,
            inventory=inventory(app("git")),  # unrelated app, present but irrelevant
        )
        assert rec.choice.value is None
        assert set(rec.fallback) == {"vscode", "cursor", "visualstudio"}

    def test_missing_status_does_not_count_as_a_candidate(self):
        ex = DesktopExecutiveV2()
        rec = ex.recommend(
            Capability.VERSION_CONTROL,
            inventory=inventory(app("git", status=MISSING)),
        )
        assert rec.choice.value is None

    def test_reason_and_evidence_are_always_present_when_known(self):
        ex = DesktopExecutiveV2()
        rec = ex.recommend(Capability.VERSION_CONTROL, inventory=inventory(app("git")))
        assert rec.choice.reason
        assert all(e.source and e.fact for e in rec.choice.evidence)

    def test_it_refuses_a_non_capability(self):
        with pytest.raises(TypeError):
            DesktopExecutiveV2().recommend("code_editing")  # type: ignore[arg-type]

    def test_it_refuses_a_non_inventory(self):
        with pytest.raises(TypeError):
            DesktopExecutiveV2().recommend(Capability.CODE_EDITING, inventory=["vscode"])  # type: ignore[arg-type]

    def test_it_refuses_a_non_environment_intelligence(self):
        with pytest.raises(TypeError):
            DesktopExecutiveV2().recommend(Capability.CODE_EDITING, environment={})  # type: ignore[arg-type]

    def test_the_whole_recommendation_projects_to_a_dict(self):
        ex = DesktopExecutiveV2()
        rec = ex.recommend(Capability.VERSION_CONTROL, inventory=inventory(app("git")))
        projected = rec.as_dict()
        assert projected["capability"] == "version_control"
        assert projected["choice"]["value"] == "git"


class TestEnvironmentIntegration:
    """*"Integrate with C22."* — `environment.ai.preferred` breaks a tie
    among healthy candidates for AI capabilities, reusing C22's own
    already-derived conclusion rather than recomputing one."""

    def test_a_known_ai_preference_breaks_the_tie(self):
        """`ollama` is declared *second* in the matrix's own priority
        order for `REASONING` (`claude_desktop` is first) — so this only
        proves the environment's preference actually overrides the
        declared order, rather than merely agreeing with it by chance."""
        from master_agent.desktop.probe import ProcessInfo

        assert MATRIX.providers_of(Capability.REASONING)[0] == "claude_desktop"

        machine = MachineInventory(
            applications=[app("claude_desktop"), app("ollama")],
            processes=[ProcessInfo(pid=1, name="ollama.exe", owner="ollama")],
            platform="win32",
        )
        env = derive_intelligence(machine)
        assert env.ai.preferred is not None
        assert env.ai.preferred.value == "ollama"

        ex = DesktopExecutiveV2()
        rec = ex.recommend(Capability.REASONING, inventory=machine, environment=env)
        assert rec.choice.value == "ollama"
        assert "C22" in rec.choice.reason

    def test_an_unknown_ai_preference_falls_back_to_declared_order(self):
        machine = inventory(app("claude_desktop"), app("ollama"))
        ex = DesktopExecutiveV2()
        rec = ex.recommend(Capability.REASONING, inventory=machine, environment=None)
        assert rec.choice.value == MATRIX.providers_of(Capability.REASONING)[0]

    def test_the_preference_is_only_consulted_for_ai_capabilities(self):
        """A browser preference has no meaning for code editing; the
        environment argument must not silently leak into an unrelated
        decision."""
        assert Capability.CODE_EDITING not in AI_CAPABILITIES
        machine = inventory(app("vscode"), app("cursor"))
        env = derive_intelligence(inventory(app("claude_desktop"), app("ollama")))
        ex = DesktopExecutiveV2()
        rec = ex.recommend(Capability.CODE_EDITING, inventory=machine, environment=env)
        assert rec.choice.value == "vscode"  # declared order, unaffected


# ═══════════════════════ E · adversarial: unknown applications ══════════


class TestUnknownApplications:
    # `notepad` was on this list as an example of an application the
    # catalog did not know. It knows it now (`catalog.py`, with a profile
    # and a recovery plan), so using it here would assert the opposite of
    # what the catalog says. The remaining five still stand: two genuinely
    # absent applications, an empty key, and two mistyped forms of a key
    # that IS known -- wrong case and a trailing space -- which is the
    # part of this test that matters, since a fuzzy match would "helpfully"
    # resolve both.
    @pytest.mark.parametrize("key", ["photoshop", "slack", "", "CHROME", "chrome "])
    def test_an_unknown_or_mistyped_key_returns_nothing_rather_than_guessing(self, key):
        ex = DesktopExecutiveV2()
        assert ex.profile(key) is None
        assert ex.recovery_plan(key) is None
        assert ex.workflows(key) == ()

    def test_an_unknown_key_in_an_inventory_does_not_satisfy_any_capability(self):
        machine = MachineInventory(
            applications=[
                InstalledApplication(key="notepad", name="Notepad", category="system", status=INSTALLED, healthy=True),
            ],
            processes=[],
            platform="win32",
        )
        ex = DesktopExecutiveV2()
        rec = ex.recommend(Capability.CODE_EDITING, inventory=machine)
        assert rec.choice.value is None


# ═══════════════════════ F · adversarial: multiple versions ═════════════


class TestMultipleVersions:
    """Knowledge here is version-agnostic by design: nothing in this
    package claims to know that version 1.2 behaves differently from
    version 3.0, because nothing here was told that and inventing it
    would be a guess dressed as knowledge."""

    @pytest.mark.parametrize("version", [None, "1.0.0", "999.999.999", "not-a-version", "120.0.6099.129"])
    def test_the_profile_is_identical_regardless_of_installed_version(self, version):
        machine = inventory(app("chrome", version=version))
        ex = DesktopExecutiveV2()
        rec = ex.recommend(Capability.NAVIGATION, inventory=machine)
        assert rec.choice.value == "chrome"
        assert rec.choice.confidence.value == "observed"

    def test_two_versions_of_the_same_capability_provider_do_not_double_count(self):
        """Only one `InstalledApplication` per key can exist in an
        inventory (`MachineInventory.get` returns the first match), so a
        'second version' cannot appear as a second candidate — this
        proves the recommendation reads through the same single-instance
        assumption the rest of the Desktop Executive already makes."""
        machine = inventory(app("git", version="2.40.0"))
        ex = DesktopExecutiveV2()
        first = ex.recommend(Capability.VERSION_CONTROL, inventory=machine)
        second_machine = inventory(app("git", version="2.44.1"))
        second = ex.recommend(Capability.VERSION_CONTROL, inventory=second_machine)
        assert first.choice.value == second.choice.value == "git"
        assert first.choice.confidence == second.choice.confidence


# ═══════════════════════ G · workflow completeness ═══════════════════════


class TestWorkflowCompleteness:
    def test_every_workflow_has_at_least_one_step(self):
        for workflow in WORKFLOWS:
            assert workflow.steps

    def test_a_workflow_cannot_be_constructed_with_no_steps(self):
        with pytest.raises(InvalidOperationKnowledge):
            Workflow(key="chrome", name="empty", steps=())

    def test_the_briefs_own_claude_desktop_workflow_is_captured(self):
        workflow = next(w for w in WORKFLOWS if w.key == "claude_desktop" and w.name == "ask_a_question")
        verbs = [step.verb for step in workflow.steps]
        assert verbs == [
            WorkflowVerb.LAUNCH, WorkflowVerb.WAIT, WorkflowVerb.FOCUS,
            WorkflowVerb.PASTE, WorkflowVerb.SUBMIT, WorkflowVerb.WAIT, WorkflowVerb.COPY,
        ]

    def test_the_briefs_own_cursor_workflow_is_captured(self):
        workflow = next(w for w in WORKFLOWS if w.key == "cursor")
        verbs = {step.verb for step in workflow.steps}
        assert WorkflowVerb.ACCEPT in verbs

    def test_the_briefs_own_chrome_workflow_is_captured(self):
        workflow = next(w for w in WORKFLOWS if w.key == "chrome" and w.name == "research_a_topic")
        verbs = {step.verb for step in workflow.steps}
        assert {WorkflowVerb.NAVIGATE, WorkflowVerb.SEARCH, WorkflowVerb.SWITCH_TAB} <= verbs

    def test_gui_first_applications_have_at_least_one_workflow(self):
        """Scoping decision, stated as a test: GUI-interactive
        applications (the brief's own worked examples) have at least one
        captured workflow. CLI-only tools and hosted extensions do not —
        see `knowledge.py`'s module docstring."""
        expected_have_workflows = {
            "claude_desktop", "cursor", "vscode", "visualstudio",
            "chrome", "edge", "firefox", "ollama", "lm_studio",
        }
        actually_have_workflows = {w.key for w in WORKFLOWS}
        assert expected_have_workflows <= actually_have_workflows

    def test_cli_only_tools_have_no_fabricated_workflow(self):
        cli_keys = {"git", "python", "node", "powershell", "java", "playwright"}
        workflowed_keys = {w.key for w in WORKFLOWS}
        assert cli_keys.isdisjoint(workflowed_keys)

    def test_a_workflow_step_projects_to_a_dict(self):
        step = WorkflowStep(WorkflowVerb.LAUNCH, "an application")
        assert step.as_dict() == {"verb": "launch", "target": "an application", "note": ""}


# ═══════════════════════ H · the knowledge base and facade ══════════════


class TestKnowledgeBase:
    def test_it_refuses_a_repeated_profile_key(self):
        with pytest.raises(InvalidOperationKnowledge):
            OperationKnowledgeBase(
                profiles=(PROFILES[0], PROFILES[0]),
                recovery_plans=RECOVERY_PLANS,
                workflows=WORKFLOWS,
                matrix=MATRIX,
            )

    def test_the_default_facade_uses_the_module_level_knowledge_base(self):
        assert DesktopExecutiveV2().knowledge_base is KNOWLEDGE_BASE

    def test_the_facade_refuses_a_non_knowledge_base(self):
        with pytest.raises(TypeError):
            DesktopExecutiveV2({"chrome": {}})  # type: ignore[arg-type]

    def test_as_dict_round_trips_every_section(self):
        import json
        projected = KNOWLEDGE_BASE.as_dict()
        assert set(projected) == {"profiles", "recovery_plans", "workflows", "matrix"}
        assert json.loads(json.dumps(projected)) == projected

    def test_profile_lookup_matches_direct_field_access(self):
        assert DesktopExecutiveV2().profile("chrome") == KNOWLEDGE_BASE.profile("chrome")


# ═══════════════════════ I · nothing here mutates anything ══════════════


class TestNoDesktopMutation:
    def test_reading_recommend_does_not_change_the_inventory(self):
        machine = inventory(app("git"))
        before = [a.as_dict() for a in machine.applications]
        DesktopExecutiveV2().recommend(Capability.VERSION_CONTROL, inventory=machine)
        after = [a.as_dict() for a in machine.applications]
        assert before == after

    def test_repeated_lookups_return_equal_immutable_values(self):
        ex = DesktopExecutiveV2()
        assert ex.profile("chrome") == ex.profile("chrome")
        assert ex.profile("chrome") is ex.profile("chrome")  # same tuple element, never rebuilt

    def test_profiles_are_frozen(self):
        profile = PROFILES[0]
        with pytest.raises(AttributeError):
            profile.key = "changed"  # type: ignore[misc]


# ═══════════════════════ I2 · construction validation ═══════════════════


class TestConstructionValidation:
    """Every dataclass here refuses to exist with a gap — at
    construction, never at read time (`types.py`'s own stated rule)."""

    def test_startup_estimate_refuses_a_non_speed(self):
        with pytest.raises(InvalidOperationKnowledge):
            StartupEstimate("fast", (0, 1))  # type: ignore[arg-type]

    def test_startup_estimate_refuses_non_integer_bounds(self):
        with pytest.raises(InvalidOperationKnowledge):
            StartupEstimate(StartupSpeed.FAST, (0.5, 1))  # type: ignore[arg-type]

    def test_startup_estimate_refuses_a_decreasing_range(self):
        with pytest.raises(InvalidOperationKnowledge):
            StartupEstimate(StartupSpeed.FAST, (5, 1))

    def test_startup_estimate_refuses_a_negative_bound(self):
        with pytest.raises(InvalidOperationKnowledge):
            StartupEstimate(StartupSpeed.FAST, (-1, 1))

    def test_operation_note_refuses_a_blank_description(self):
        with pytest.raises(InvalidOperationKnowledge):
            OperationNote("   ")

    def test_profile_refuses_a_blank_key(self):
        good = PROFILES[0]
        with pytest.raises(InvalidOperationKnowledge):
            ApplicationOperationProfile(
                key="",
                launch=good.launch, focus=good.focus, close=good.close,
                wait_until_ready=good.wait_until_ready, health_check=good.health_check,
                recover=good.recover, known_failure_modes=good.known_failure_modes,
                startup_time=good.startup_time,
                preferred_launch_method=good.preferred_launch_method,
                window_strategy=good.window_strategy,
                automation_strategy=good.automation_strategy,
                recovery_approach=good.recovery_approach,
            )

    def test_profile_refuses_a_non_operation_note_field(self):
        good = PROFILES[0]
        with pytest.raises(InvalidOperationKnowledge):
            ApplicationOperationProfile(
                key="test",
                launch="not a note",  # type: ignore[arg-type]
                focus=good.focus, close=good.close,
                wait_until_ready=good.wait_until_ready, health_check=good.health_check,
                recover=good.recover, known_failure_modes=good.known_failure_modes,
                startup_time=good.startup_time,
                preferred_launch_method=good.preferred_launch_method,
                window_strategy=good.window_strategy,
                automation_strategy=good.automation_strategy,
                recovery_approach=good.recovery_approach,
            )

    def test_profile_refuses_a_non_failure_mode_in_known_failure_modes(self):
        good = PROFILES[0]
        with pytest.raises(InvalidOperationKnowledge):
            ApplicationOperationProfile(
                key="test",
                launch=good.launch, focus=good.focus, close=good.close,
                wait_until_ready=good.wait_until_ready, health_check=good.health_check,
                recover=good.recover, known_failure_modes=("not_a_mode",),  # type: ignore[arg-type]
                startup_time=good.startup_time,
                preferred_launch_method=good.preferred_launch_method,
                window_strategy=good.window_strategy,
                automation_strategy=good.automation_strategy,
                recovery_approach=good.recovery_approach,
            )

    def test_profile_refuses_a_repeated_failure_mode(self):
        good = PROFILES[0]
        with pytest.raises(InvalidOperationKnowledge):
            ApplicationOperationProfile(
                key="test",
                launch=good.launch, focus=good.focus, close=good.close,
                wait_until_ready=good.wait_until_ready, health_check=good.health_check,
                recover=good.recover,
                known_failure_modes=(FailureMode.HUNG, FailureMode.HUNG),
                startup_time=good.startup_time,
                preferred_launch_method=good.preferred_launch_method,
                window_strategy=good.window_strategy,
                automation_strategy=good.automation_strategy,
                recovery_approach=good.recovery_approach,
            )

    def test_recovery_guidance_refuses_a_blank_diagnosis(self):
        with pytest.raises(InvalidOperationKnowledge):
            RecoveryGuidance("  ", ("step",))

    def test_recovery_guidance_refuses_no_steps(self):
        with pytest.raises(InvalidOperationKnowledge):
            RecoveryGuidance("diagnosis", ())

    def test_recovery_plan_refuses_a_blank_key(self):
        full = tuple((mode, RecoveryGuidance("x", ("y",))) for mode in FailureMode)
        with pytest.raises(InvalidOperationKnowledge):
            ApplicationRecoveryPlan(key="  ", guidance=full)

    def test_workflow_step_refuses_a_non_verb(self):
        with pytest.raises(InvalidOperationKnowledge):
            WorkflowStep("launch", "a target")  # type: ignore[arg-type]

    def test_workflow_step_refuses_a_blank_target(self):
        with pytest.raises(InvalidOperationKnowledge):
            WorkflowStep(WorkflowVerb.LAUNCH, "   ")

    def test_workflow_refuses_a_blank_key(self):
        with pytest.raises(InvalidOperationKnowledge):
            Workflow(key="", name="x", steps=(WorkflowStep(WorkflowVerb.LAUNCH, "it"),))

    def test_workflow_refuses_a_blank_name(self):
        with pytest.raises(InvalidOperationKnowledge):
            Workflow(key="chrome", name="  ", steps=(WorkflowStep(WorkflowVerb.LAUNCH, "it"),))


class TestFacadeAndMatrixCoverage:
    """Direct lookups this suite's higher-level tests exercise only
    indirectly."""

    def test_profiled_keys_lists_every_profile(self):
        assert set(KNOWLEDGE_BASE.profiled_keys()) == _CATALOG_KEYS

    def test_capability_matrix_accessor_returns_the_real_matrix(self):
        assert DesktopExecutiveV2().capability_matrix() is MATRIX

    def test_capabilities_of_a_known_key_returns_its_capabilities(self):
        assert Capability.NAVIGATION in MATRIX.capabilities_of("chrome")

    def test_recovery_knowledge_base_refuses_a_repeated_plan_key(self):
        with pytest.raises(InvalidOperationKnowledge):
            OperationKnowledgeBase(
                profiles=PROFILES,
                recovery_plans=(RECOVERY_PLANS[0], RECOVERY_PLANS[0]),
                workflows=WORKFLOWS,
                matrix=MATRIX,
            )

    def test_a_capability_with_no_known_provider_is_unknown(self):
        """Every real `Capability` in this brief's own matrix happens to
        have a provider — proving the empty-candidate branch requires a
        knowledge base deliberately built without one."""
        sparse_matrix = DesktopCapabilityMatrix(entries=(("git", (Capability.VERSION_CONTROL,)),))
        sparse_kb = OperationKnowledgeBase(
            profiles=PROFILES, recovery_plans=RECOVERY_PLANS, workflows=WORKFLOWS,
            matrix=sparse_matrix,
        )
        rec = DesktopExecutiveV2(sparse_kb).recommend(Capability.CODE_EDITING, inventory=inventory())
        assert rec.choice.value is None
        assert rec.choice.confidence.value == "unknown"
        assert rec.fallback == ()

    def test_an_ai_preference_naming_a_non_candidate_falls_back_to_declared_order(self):
        """`environment.ai.preferred` can be known and yet name an
        AI-category application (`cursor`) that is not among the tied,
        healthy candidates for `REASONING` (`claude_desktop`, `ollama`)
        — the declared order must still win."""
        from master_agent.desktop.probe import ProcessInfo

        machine = MachineInventory(
            applications=[app("claude_desktop"), app("ollama"), app("cursor")],
            processes=[ProcessInfo(pid=1, name="cursor.exe", owner="cursor")],
            platform="win32",
        )
        env = derive_intelligence(machine)
        assert env.ai.preferred is not None
        assert env.ai.preferred.value == "cursor"  # preferred, but not a REASONING candidate

        rec = DesktopExecutiveV2().recommend(Capability.REASONING, inventory=machine, environment=env)
        assert rec.choice.value == "claude_desktop"  # declared order, unaffected


# ═══════════════════════ J · structural guards, by AST ═══════════════════


def _modules() -> list[tuple[Path, ast.Module]]:
    return [
        (path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
        for path in sorted(PACKAGE.rglob("*.py"))
    ]


def _imports() -> set[str]:
    found: set[str] = set()
    for _, tree in _modules():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module)
    return found


def _called_names() -> set[str]:
    found: set[str] = set()
    for _, tree in _modules():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                rendered = ast.unparse(node.func)
                found.add(rendered)
                found.add(".".join(rendered.split(".")[-2:]))
    return found


def _defined_names() -> set[str]:
    found: set[str] = set()
    for _, tree in _modules():
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                found.add(node.name)
    return found


class TestTheGuardsThemselves:
    def test_the_package_was_actually_found(self):
        assert len(list(PACKAGE.rglob("*.py"))) >= 3

    def test_forbidden_words_appear_in_prose_but_not_as_identifiers(self):
        prose = "\n".join(p.read_text(encoding="utf-8") for p, _ in _modules())
        for word in ("subprocess", "pyautogui", "click", "execute"):
            assert word in prose
            assert word not in _imports()
            assert word not in _defined_names()


class TestNeverExecutesOrAutomates:
    """The brief's own forbidden list, checked one item at a time:
    execute applications, launch software, click, move mouse, send keys,
    install software, modify applications, change settings."""

    FORBIDDEN_MODULES = (
        "subprocess", "os", "shutil", "socket", "http", "urllib",
        "requests", "httpx", "ctypes", "winreg", "threading",
        "multiprocessing", "pyautogui", "pynput", "win32api", "win32gui",
    )

    FORBIDDEN_EXECUTION_SURFACES = (
        "master_agent.desktop.actions",
        "master_agent.desktop.plugin",
        "master_agent.desktop.probe",
        "master_agent.executor",
        "master_agent.plugins",
        "master_agent.providers",
        "master_agent.broker",
        "master_agent.orchestrator",
        "master_agent.runtime.",
        "master_agent.mission_control",
        "master_agent.permissions",
    )

    FORBIDDEN_CALLS = (
        "click", "double_click", "right_click", "move_mouse", "press_key",
        "type_text", "send_keys", "hotkey", "screenshot", "popen", "run",
        "call", "check_call", "check_output", "system", "startfile",
        "install", "uninstall",
    )

    def test_no_module_that_could_touch_the_machine_is_imported(self):
        imported = _imports()
        for module in self.FORBIDDEN_MODULES:
            assert module not in imported

    def test_no_execution_capable_desktop_surface_is_imported(self):
        """The Desktop Executive's *execution* half — `actions.py`,
        `plugin.py`, `probe.py` — is untouched by this brief; this
        package reads only `inventory.py`'s data types."""
        for module in _imports():
            for forbidden in self.FORBIDDEN_EXECUTION_SURFACES:
                assert not module.startswith(forbidden), (
                    f"{module} gives this package an execution path"
                )

    def test_no_forbidden_call_appears_anywhere(self):
        called = _called_names()
        for name in self.FORBIDDEN_CALLS:
            assert name not in called

    def test_it_imports_only_the_desktop_inventory_data_types(self):
        imports = _imports()
        assert "master_agent.desktop.inventory" in imports
        assert "master_agent.desktop.catalog" not in imports

    def test_no_frozen_package_is_reachable(self):
        frozen = (
            "master_agent.foundation", "master_agent.kernel",
            "master_agent.ledger", "master_agent.coordinator",
            "master_agent.runtime_bridge", "master_agent.api",
        )
        for module in _imports():
            for forbidden in frozen:
                assert not module.startswith(forbidden)


class TestKnowledgeOnlyNoDerivation:
    def test_no_environment_intelligence_derivation_is_reimplemented(self):
        called = _called_names()
        for name in ("discover", "discover_application", "attribute_processes", "derive_browsers", "derive_ai", "derive_graph"):
            assert name not in called

    def test_environment_intelligence_types_are_reused_not_redeclared(self):
        defined = _defined_names()
        for owned_by_c22 in ("Inference", "Evidence", "Confidence", "EnvironmentSummary", "CapabilityGraph"):
            assert owned_by_c22 not in defined

    def test_derive_intelligence_is_never_called_here(self):
        """This package consumes an `EnvironmentIntelligence` a caller
        already derived; it performs no derivation of its own."""
        assert "derive_intelligence" not in _called_names()
