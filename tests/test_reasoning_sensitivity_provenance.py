"""Public material stays public. Private material stays private.

## Both directions, and the dangerous one is second

A research mission that read three public web pages was refused:

    11 provider(s) considered, none eligible: excluded by the request;
    sensitive work may not go to a third party

`Reasoning.Transform` defaults to `sensitive=True` -- correctly, because
its context is normally an earlier Step's output and a founder's own
document must not go to whichever cloud provider ranked first. But the
default described the CAPABILITY rather than the MATERIAL, and public
information does not become private because reasoning touched it.

The half that matters more is the reverse. `sensitive` arrives in the
plan PAYLOAD, so a model could write `"sensitive": false` over a
founder's private file and the request would go out. Model-generated
output may never lower sensitivity; only provenance may.
"""
from __future__ import annotations

import pytest

from master_agent.runtime.sensitivity import (
    PRIVATE,
    PUBLIC,
    UNKNOWN,
    apply_to,
    classify,
    derive,
)


class TestWhatKindOfMaterialIsThis:
    @pytest.mark.parametrize("capability", [
        "Browser.ReadPageText", "Browser.Navigate", "Browser.ObserveBrowser",
    ])
    def test_the_ordinary_browser_lane_is_public(self, capability):
        """Anonymous by construction -- a fresh automated context with
        none of the founder's sessions."""
        assert classify(capability) == PUBLIC

    @pytest.mark.parametrize("capability", [
        "Filesystem.ReadFile", "Document.ReadDocument", "Desktop.Screenshot",
        "Clipboard.Read", "Memory.Recall",
    ])
    def test_the_founders_own_material_is_private(self, capability):
        assert classify(capability) == PRIVATE

    def test_the_trusted_browser_is_private_however_ordinary_the_page_looks(self):
        """It carries the founder's signed-in identity. What it sees is
        theirs even when the URL is public."""
        assert classify("Browser.TrustedNavigate") == PRIVATE

    def test_an_unrecognised_capability_is_unknown_not_public(self):
        """The safe direction. A capability nobody classified must not
        become a way to launder material."""
        assert classify("Something.New") == UNKNOWN
        assert classify("") == UNKNOWN


class TestTheJoinRule:
    def test_public_and_public_is_public(self):
        assert derive(["Browser.ReadPageText", "Browser.Navigate"]) is False

    def test_public_and_private_is_private(self):
        """One private input makes the whole invocation private."""
        assert derive(["Browser.ReadPageText", "Filesystem.ReadFile"]) is True

    def test_private_alone_is_private(self):
        assert derive(["Filesystem.ReadFile"]) is True

    def test_anything_unknown_leaves_the_default_alone(self):
        """`None` means "say nothing", so the conservative default
        stands. That is the right failure."""
        assert derive(["Browser.ReadPageText", "Something.New"]) is None

    def test_no_sources_says_nothing(self):
        assert derive([]) is None


class TestAModelCannotLowerSensitivity:
    """The line this module exists to draw."""

    def test_a_declared_false_over_private_provenance_is_overridden(self):
        payload = {"sensitive": False, "instruction": "summarise"}
        apply_to(payload, ["Filesystem.ReadFile"])
        assert payload["sensitive"] is True, (
            "a model wrote sensitive=false over a founder's private file "
            "and it survived"
        )

    def test_a_declared_false_over_mixed_provenance_is_overridden(self):
        payload = {"sensitive": False}
        apply_to(payload, ["Browser.ReadPageText", "Desktop.Screenshot"])
        assert payload["sensitive"] is True

    def test_a_declared_true_is_never_relaxed_by_public_provenance(self):
        """Raising is always allowed. A plan may be more careful than
        provenance requires, and nothing here second-guesses that."""
        payload = {"sensitive": True}
        apply_to(payload, ["Browser.ReadPageText"])
        assert payload["sensitive"] is True

    def test_authoritative_public_intent_can_relax_model_caution_for_public_evidence(self):
        """The model is not the sensitivity authority in either direction.

        Keeping its conservative guess blocked the live public-research
        mission after six anonymous public pages had been verified.
        """
        payload = {"sensitive": True}
        apply_to(
            payload,
            ["Browser.ReadPageText", "Browser.ReadPageText"],
            intent_sensitive=False,
        )
        assert payload["sensitive"] is False

    def test_sensitive_intent_cannot_be_lowered_by_public_provenance(self):
        payload = {"sensitive": False}
        apply_to(
            payload,
            ["Browser.ReadPageText"],
            intent_sensitive=True,
        )
        assert payload["sensitive"] is True

    def test_a_declared_false_over_unknown_provenance_becomes_conservative(self):
        """Unknown provenance cannot license a downgrade."""
        payload = {"sensitive": False}
        apply_to(payload, ["Something.New"])
        assert payload["sensitive"] is True
        assert derive(["Something.New"], False) is True


class TestPublicResearchIsNotRefused:
    def test_public_browser_evidence_makes_the_invocation_non_sensitive(self):
        """The founder's failed mission, in one assertion."""
        payload = {"instruction": "which of these are action RPGs?"}
        apply_to(payload, ["Browser.ReadPageText", "Browser.ReadPageText"])
        assert payload["sensitive"] is False

    def test_a_payload_with_no_bindings_is_left_untouched(self):
        payload = {"instruction": "think about something"}
        apply_to(payload, [])
        assert "sensitive" not in payload


class TestItIsWiredIntoResolution:
    def test_public_intent_and_verified_public_binding_reach_execution_as_public(self):
        from types import SimpleNamespace

        from master_agent.runtime.input_resolution import resolve_inputs

        source = SimpleNamespace(
            capability="Browser.ReadPageText",
            state="completed",
            result={"text": "public page"},
            evidence={
                "evidence_id": "ev-public",
                "verdict": "matched",
                "observation": {"text": "public page"},
            },
        )
        task = SimpleNamespace(
            task_id="synthesise",
            payload={"instruction": "compare", "sensitive": True},
            input_bindings={
                "context": {
                    "from_step": {"step_id": "read", "field": "text"}
                }
            },
            depends_on=["read"],
            intent_sensitive=False,
        )

        resolved = resolve_inputs(task, {"read": source})

        assert resolved.payload["context"] == "public page"
        assert resolved.payload["sensitive"] is False

    @pytest.mark.parametrize(
        ("observed_sensitivity", "expected"),
        [("public", False), ("private", True)],
    )
    def test_reasoning_output_inherits_its_verified_material_classification(
        self, observed_sensitivity, expected
    ):
        from types import SimpleNamespace

        from master_agent.runtime.input_resolution import resolve_inputs

        source = SimpleNamespace(
            capability="Reasoning.Transform",
            state="completed",
            result={"text": "derived report", "sensitivity": observed_sensitivity},
            evidence={
                "evidence_id": "ev-reasoning",
                "verdict": "matched",
                "observation": {
                    "text": "derived report",
                    "sensitivity": observed_sensitivity,
                },
            },
        )
        task = SimpleNamespace(
            task_id="format",
            payload={"instruction": "format"},
            input_bindings={
                "context": {
                    "from_step": {"step_id": "compare", "field": "text"}
                }
            },
            depends_on=["compare"],
            intent_sensitive=False,
        )

        resolved = resolve_inputs(task, {"compare": source})

        assert resolved.payload["sensitive"] is expected

    def test_the_resolver_derives_sensitivity_from_its_own_provenance(self):
        import inspect

        from master_agent.runtime import input_resolution

        source = inspect.getsource(input_resolution.resolve_inputs)
        assert "apply_to" in source
        assert "provenance" in source

    def test_it_depends_on_nothing_in_the_planner(self):
        """Not a planning concern. Sensitivity is decided at execution
        time from what the material actually is, and a module that
        imported the Planner could be influenced by what a plan said --
        which is the thing being guarded against."""
        import inspect

        from master_agent.runtime import sensitivity

        source = inspect.getsource(sensitivity)
        for forbidden in ("from master_agent.planner", "import planner"):
            assert forbidden not in source, forbidden
