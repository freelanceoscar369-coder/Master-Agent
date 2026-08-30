"""Regression coverage for the pre-existing-folder false completion.

Observed in the frozen Codex holdout (H20): the Founder asked for a *new
empty* folder, the target already existed and contained ``OLD``, and the
product reported that all work was independently verified.  These tests
keep the Founder meaning, capability precondition, fresh observation, and
Founder-facing claim aligned without changing ordinary idempotent folder
creation.
"""
from __future__ import annotations

import pytest

from master_agent.brain.intent import IntentLayer
from master_agent.brain.reporter import Reporter
from master_agent.executor.actions.create_folder import CreateFolderAction
from master_agent.missions.history import COMPLETED, PlanRecord, StepRecord
from master_agent.permissions.permission_system import PermissionSystem
from master_agent.plugins.filesystem_expectations import bind_for_environment
from master_agent.plugins.filesystem_gateway import FilesystemGateway
from master_agent.verification.evidence import ExpectedOutcome, Verdict


class TestFounderMeaningSurvivesIntent:
    @pytest.mark.parametrize(
        "words",
        [
            "Create a new empty folder called Demo on my Desktop.",
            "Please make an empty new folder named Demo in Desktop!",
            "create new empty folder called Demo on the desktop",
        ],
    )
    def test_natural_modifier_order_is_structurally_parsed(self, words):
        result = IntentLayer().parse(words)

        assert not result.needs_clarification
        assert result.intent.capability == "create_folder"
        assert result.intent.payload["name"] == "Demo"
        assert result.intent.payload["location"].lower() == "desktop"
        assert result.intent.payload["must_be_new"] is True
        assert result.intent.payload["must_be_empty"] is True
        assert result.intent.requirements

    def test_empty_without_new_is_preserved_independently(self):
        result = IntentLayer().parse(
            "Create an empty folder called Demo in Documents"
        )

        assert result.intent.payload["must_be_empty"] is True
        assert "must_be_new" not in result.intent.payload

    def test_plain_create_keeps_the_existing_idempotent_contract(self):
        result = IntentLayer().parse("Create a folder called Demo on Desktop")

        assert result.intent.payload == {"name": "Demo", "location": "Desktop"}

    def test_modifiers_do_not_hide_a_missing_location(self):
        result = IntentLayer().parse("Create a new empty folder called Demo")

        assert result.needs_clarification
        assert result.clarification.key == "location"

    def test_an_unrelated_folder_sentence_is_not_claimed(self):
        result = IntentLayer().parse("Delete the folder after reading it")

        assert result.intent is not None
        assert result.intent.capability != "create_folder"

    def test_need_wording_and_leading_location_are_structural(self):
        result = IntentLayer().parse(
            "On Desktop, I need a folder named: Demo."
        )

        assert not result.needs_clarification
        assert result.intent.capability == "create_folder"
        assert result.intent.payload == {"name": "Demo", "location": "Desktop"}

    def test_need_wording_without_fields_asks_for_the_name(self):
        result = IntentLayer().parse("I need a new folder")

        assert result.needs_clarification
        assert result.clarification.key == "folder_name"

    def test_nounless_create_clarifies_instead_of_becoming_a_project(self):
        result = IntentLayer().parse("Create Demo on my Desktop.")

        assert result.needs_clarification
        assert result.clarification.key == "creation_kind"
        assert result.intent is None


class TestCapabilityEnforcesTheFounderConstraint:
    def test_contract_publishes_both_semantic_flags(self, tmp_path):
        optional = {
            item["name"]: item
            for item in CreateFolderAction({"desktop": tmp_path}).optional_parameters()
        }

        assert optional["must_be_new"]["type"] == "boolean"
        assert optional["must_be_empty"]["type"] == "boolean"

    def test_new_fails_when_any_directory_already_exists(self, tmp_path):
        target = tmp_path / "Demo"
        target.mkdir()

        result = CreateFolderAction({"desktop": tmp_path}).run({
            "name": "Demo",
            "location": "desktop",
            "must_be_new": True,
        })

        assert not result.success
        assert "already exists" in result.errors[0]

    def test_empty_fails_when_existing_directory_has_content(self, tmp_path):
        target = tmp_path / "Demo"
        target.mkdir()
        (target / "OLD").write_text("old", encoding="utf-8")

        result = CreateFolderAction({"desktop": tmp_path}).run({
            "name": "Demo",
            "location": "desktop",
            "must_be_empty": True,
        })

        assert not result.success
        assert "not empty" in result.errors[0]
        assert (target / "OLD").exists()

    def test_empty_allows_an_existing_empty_directory(self, tmp_path):
        (tmp_path / "Demo").mkdir()

        result = CreateFolderAction({"desktop": tmp_path}).run({
            "name": "Demo",
            "location": "desktop",
            "must_be_empty": True,
        })

        assert result.success
        assert "already existed" in result.warnings[0]

    def test_plain_create_remains_idempotent_even_when_nonempty(self, tmp_path):
        target = tmp_path / "Demo"
        target.mkdir()
        (target / "OLD").write_text("old", encoding="utf-8")

        result = CreateFolderAction({"desktop": tmp_path}).run({
            "name": "Demo", "location": "desktop"
        })

        assert result.success
        assert (target / "OLD").exists()


class _WorkerWithLocations:
    def __init__(self, locations):
        self._locations = locations


class TestIndependentEmptyVerification:
    def test_empty_contract_requires_a_complete_empty_listing(self):
        expected = bind_for_environment(
            "Filesystem.CreateFolder",
            {"name": "Demo", "location": "desktop", "must_be_empty": True},
            "A new empty folder exists",
        )

        checks = {check.field: check.value for check in expected.checks}
        assert checks["directory_listing"] == []
        assert checks["directory_listing_truncated"] is False

    def test_gateway_collects_the_listing_without_planner_opt_in(self, tmp_path):
        target = tmp_path / "Demo"
        target.mkdir()
        (target / "OLD").write_text("old", encoding="utf-8")
        gateway = FilesystemGateway(
            _WorkerWithLocations({"desktop": tmp_path}),
            PermissionSystem(),
            "filesystem",
        )
        expected = ExpectedOutcome(description="An empty folder exists", checks=[])

        evidence = gateway.verify(
            "Filesystem.CreateFolder",
            {"name": "Demo", "location": "desktop", "must_be_empty": True},
            expected,
        )

        assert evidence is not None
        assert evidence.verdict is not Verdict.MATCHED
        assert [row["name"] for row in evidence.observation["directory_listing"]] == ["OLD"]


class TestNoSemanticTraceNeverBecomesCompletion:
    def test_completed_steps_without_requirements_are_reported_as_unconfirmed(self):
        step = StepRecord(
            step_id="folder-1",
            capability="Filesystem.CreateFolder",
            payload={"name": "Demo"},
        )
        step.state = COMPLETED
        record = PlanRecord(
            plan_id="plan-1",
            objective="Create a new empty folder",
            steps=[step],
            state=COMPLETED,
            requirements=[],
        )

        report = Reporter().report_plan_record_outcome(record)
        founder_words = f"{report.title} {report.body}".lower()

        assert "can't confirm" in founder_words
        assert "work finished" not in founder_words
        assert "mission completed" not in founder_words
        assert report.metadata["founder_outcome_conformance"] == "unknown"
