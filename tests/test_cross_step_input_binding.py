"""A value a later Step needs comes from the Step that produced it.

The proven failure, from a packaged Medium mission where every step
verified MATCHED:

    step_3 Browser.ObserveBrowser   observed  https://example.com/
    step_5 Filesystem.WriteFile     wrote     https://example.com

`step_5` declared `depends_on: ["step_3", "step_4"]`, so the ordering
dependency was understood. The data dependency had no way to be expressed,
so the Planner filled `content` at planning time from the founder's own
sentence -- a prediction, wrong by the one character that proves it.

`depends_on` says when. `input_bindings` says what flows. These tests hold
the second to a standard the first never needed: a bound value must come
from output the source Step's own Evidence corroborates.
"""
from __future__ import annotations

import json

import pytest

from master_agent.capabilities.input_bindings import (
    MalformedBinding,
    binding_from_dict,
    bindings_from_dict,
)
from master_agent.runtime.input_resolution import (
    BindingResolutionError,
    resolve_inputs,
)

OBSERVED_URL = "https://example.com/"
OBSERVED_TITLE = "Example Domain"


class FakeTask:
    """Stands in for a Mission Control Task."""

    def __init__(self, task_id, *, payload=None, bindings=None, depends_on=(),
                 state="completed", result=None, evidence=None):
        self.task_id = task_id
        self.payload = payload or {}
        self.input_bindings = bindings or {}
        self.depends_on = list(depends_on)
        self.state = state
        self.result = result
        self.evidence = evidence


def evidence(observation: dict, verdict: str = "matched") -> dict:
    return {
        "evidence_id": "ev-step3",
        "worker": "browser",
        "environment": "browser_environment",
        "captured_at": "2026-08-19T18:22:12.541630+00:00",
        "expected": {"description": "observed", "checks": []},
        "observation": observation,
        "verdict": verdict,
        "check_results": [],
        "errors": [],
    }


def source(**overrides) -> FakeTask:
    """A healthy `ObserveBrowser` source whose result and Evidence agree."""
    defaults = {
        "result": {"url": OBSERVED_URL, "title": OBSERVED_TITLE},
        "evidence": evidence({"url": OBSERVED_URL, "title": OBSERVED_TITLE}),
        "state": "completed",
    }
    defaults.update(overrides)
    return FakeTask("step_3", **defaults)


def consumer(bindings: dict, payload=None) -> FakeTask:
    return FakeTask(
        "step_5",
        payload=payload or {"path": "KV/page_info.txt", "location": "Desktop"},
        bindings=bindings_from_dict(bindings),
        depends_on=["step_3", "step_4"],
    )


MEDIUM_CONTENT_BINDING = {
    "content": {"concat": [
        {"literal": "Title: "},
        {"from_step": {"step_id": "step_3", "field": "title"}},
        {"literal": "\nURL: "},
        {"from_step": {"step_id": "step_3", "field": "url"}},
    ]}
}


class TestTheBindingContract:

    def test_a_direct_reference_round_trips(self):
        raw = {"from_step": {"step_id": "step_3", "field": "url"}}
        assert binding_from_dict(raw).as_dict() == raw

    def test_a_concat_round_trips(self):
        binding = binding_from_dict(MEDIUM_CONTENT_BINDING["content"])
        assert binding_from_dict(binding.as_dict()) == binding
        assert [(r.step_id, r.field) for r in binding.references] == [
            ("step_3", "title"), ("step_3", "url"),
        ]

    @pytest.mark.parametrize("malformed,why", [
        ({}, "neither form"),
        ({"from_step": {"step_id": "s", "field": "u"}, "concat": []}, "both forms"),
        ({"concat": []}, "empty concat"),
        ({"concat": [{"concat": []}]}, "nested concat"),
        ({"from_step": {"step_id": "", "field": "u"}}, "blank step id"),
        ({"concat": [{"literal": 42}]}, "non-string literal"),
    ])
    def test_a_malformed_binding_is_refused(self, malformed, why):
        with pytest.raises(MalformedBinding):
            binding_from_dict(malformed)


class TestAValueOnlyFlowsWhenItIsCorroborated:
    """The eight conditions. Rule 8 is the one that matters."""

    def test_agreeing_result_and_observation_resolve(self):
        resolved = resolve_inputs(
            consumer({"content": {"from_step": {"step_id": "step_3", "field": "url"}}}),
            {"step_3": source()},
        )
        assert resolved.payload["content"] == OBSERVED_URL

    def test_a_disagreement_is_never_silently_resolved(self):
        """The Action reports one thing, the independent Observation
        another. Picking a winner is how a system starts trusting itself;
        this refuses instead."""
        disagreeing = source(
            result={"url": "https://example.com", "title": OBSERVED_TITLE},   # no slash
            evidence=evidence({"url": OBSERVED_URL, "title": OBSERVED_TITLE}),
        )
        with pytest.raises(BindingResolutionError, match="refusing to choose"):
            resolve_inputs(
                consumer({"content": {"from_step": {"step_id": "step_3", "field": "url"}}}),
                {"step_3": disagreeing},
            )

    def test_no_evidence_means_the_value_cannot_flow(self):
        """Local fail-closed for data dependencies. A step may still
        COMPLETE elsewhere without Evidence while global fail-closed is
        deferred -- but a value may not FLOW on that basis."""
        with pytest.raises(BindingResolutionError, match="no canonical Evidence"):
            resolve_inputs(
                consumer({"content": {"from_step": {"step_id": "step_3", "field": "url"}}}),
                {"step_3": source(evidence=None)},
            )

    @pytest.mark.parametrize("verdict", ["not_matched", "partially_matched", "error"])
    def test_an_unmatched_verdict_cannot_flow(self, verdict):
        bad = source(evidence=evidence(
            {"url": OBSERVED_URL, "title": OBSERVED_TITLE}, verdict=verdict,
        ))
        with pytest.raises(BindingResolutionError, match="not matched"):
            resolve_inputs(
                consumer({"content": {"from_step": {"step_id": "step_3", "field": "url"}}}),
                {"step_3": bad},
            )

    def test_a_field_absent_from_the_result_fails(self):
        with pytest.raises(BindingResolutionError, match="absent from the source result"):
            resolve_inputs(
                consumer({"content": {"from_step": {"step_id": "step_3", "field": "nope"}}}),
                {"step_3": source()},
            )

    def test_a_field_absent_from_the_observation_fails(self):
        half = source(
            result={"url": OBSERVED_URL, "extra": "x"},
            evidence=evidence({"url": OBSERVED_URL}),
        )
        with pytest.raises(BindingResolutionError, match="absent from the source Evidence"):
            resolve_inputs(
                consumer({"content": {"from_step": {"step_id": "step_3", "field": "extra"}}}),
                {"step_3": half},
            )

    def test_an_incomplete_source_fails(self):
        with pytest.raises(BindingResolutionError, match="not completed"):
            resolve_inputs(
                consumer({"content": {"from_step": {"step_id": "step_3", "field": "url"}}}),
                {"step_3": source(state="running")},
            )

    def test_a_missing_source_fails(self):
        with pytest.raises(BindingResolutionError, match="no such step"):
            resolve_inputs(
                consumer({"content": {"from_step": {"step_id": "step_3", "field": "url"}}}),
                {},
            )

    def test_a_source_that_is_not_a_declared_dependency_fails(self):
        """A binding may READ a dependency; it may not create one.
        `depends_on` stays the single execution-order authority."""
        task = FakeTask(
            "step_5", payload={},
            bindings=bindings_from_dict(
                {"content": {"from_step": {"step_id": "step_3", "field": "url"}}}
            ),
            depends_on=["step_4"],          # step_3 deliberately absent
        )
        with pytest.raises(BindingResolutionError, match="not a declared dependency"):
            resolve_inputs(task, {"step_3": source()})


class TestTheMediumConcat:

    def test_it_produces_exactly_the_observed_values(self):
        resolved = resolve_inputs(consumer(MEDIUM_CONTENT_BINDING), {"step_3": source()})
        assert resolved.payload["content"] == (
            f"Title: {OBSERVED_TITLE}\nURL: {OBSERVED_URL}"
        )
        # The character the old prediction got wrong.
        assert resolved.payload["content"].endswith("/")

    def test_literal_arguments_survive_beside_bound_ones(self):
        resolved = resolve_inputs(consumer(MEDIUM_CONTENT_BINDING), {"step_3": source()})
        assert resolved.payload["path"] == "KV/page_info.txt"
        assert resolved.payload["location"] == "Desktop"

    def test_a_non_string_segment_is_refused(self):
        numeric = source(
            result={"title": 42, "url": OBSERVED_URL},
            evidence=evidence({"title": 42, "url": OBSERVED_URL}),
        )
        with pytest.raises(BindingResolutionError, match="not text"):
            resolve_inputs(consumer(MEDIUM_CONTENT_BINDING), {"step_3": numeric})

    def test_a_literal_and_a_binding_cannot_both_set_one_argument(self):
        task = consumer(MEDIUM_CONTENT_BINDING, payload={"content": "predicted"})
        with pytest.raises(BindingResolutionError, match="both by a literal"):
            resolve_inputs(task, {"step_3": source()})


class TestThePlanIsNotRewritten:

    def test_the_original_payload_is_untouched(self):
        task = consumer(MEDIUM_CONTENT_BINDING)
        before = json.dumps(task.payload, sort_keys=True)

        resolved = resolve_inputs(task, {"step_3": source()})

        assert json.dumps(task.payload, sort_keys=True) == before
        assert "content" not in task.payload
        assert "content" in resolved.payload


class TestProvenance:

    def test_it_names_the_step_field_and_evidence(self):
        resolved = resolve_inputs(consumer(MEDIUM_CONTENT_BINDING), {"step_3": source()})

        assert len(resolved.provenance) == 1
        record = resolved.provenance[0]
        assert record["target"] == "content"
        assert [(s["step_id"], s["field"]) for s in record["sources"]] == [
            ("step_3", "title"), ("step_3", "url"),
        ]
        assert all(s["evidence_id"] == "ev-step3" for s in record["sources"])

    def test_it_is_json_plain(self):
        resolved = resolve_inputs(consumer(MEDIUM_CONTENT_BINDING), {"step_3": source()})
        assert json.loads(json.dumps(resolved.provenance)) == resolved.provenance

    def test_a_task_with_no_bindings_records_none(self):
        plain = FakeTask("step_4", payload={"name": "KV", "location": "Desktop"})
        resolved = resolve_inputs(plain, {})
        assert resolved.provenance == []
        assert resolved.payload == {"name": "KV", "location": "Desktop"}


class TestTheResolverStaysDomainAgnostic:
    """The Runtime must not learn what a browser is."""

    @pytest.mark.parametrize("forbidden", [
        "browser", "filesystem", "desktop", "title", "url",
        "page_info", "example.com", "playwright",
    ])
    def test_it_names_no_domain(self, forbidden):
        import inspect

        from master_agent.runtime import input_resolution

        code = "".join(
            line for line in inspect.getsource(input_resolution).splitlines(True)
            if not line.lstrip().startswith("#")
        )
        # Docstrings explain the defect and legitimately name it; executable
        # code may not branch on any of these.
        body = code.split('"""')
        executable = "".join(body[i] for i in range(0, len(body), 2))
        assert forbidden not in executable.lower()

    def test_it_imports_no_domain_package(self):
        import ast
        import inspect

        from master_agent.runtime import input_resolution

        tree = ast.parse(inspect.getsource(input_resolution))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
            elif isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
        for module in imported:
            assert "plugins" not in module
            assert "desktop" not in module
            assert "executor" not in module


class TestFieldPathParityWithVerification:
    """The resolver reimplements the dot-path walk because `runtime/` may
    not import the verification package. Parity is asserted rather than
    obtained by coupling."""

    @pytest.mark.parametrize("path,document,expected", [
        ("url", {"url": "u"}, "u"),
        ("elements.0.text", {"elements": [{"text": "hello"}]}, "hello"),
        ("a.b", {"a": {"b": 1}}, 1),
    ])
    def test_the_same_paths_resolve_the_same_way(self, path, document, expected):
        from master_agent.runtime.input_resolution import _walk
        from master_agent.verification.evaluator import get_field

        assert _walk(document, path) == (True, expected)
        assert get_field(document, path) == (True, expected)

    @pytest.mark.parametrize("path,document", [
        ("missing", {"url": "u"}),
        ("elements.9.text", {"elements": []}),
        ("a.b", {"a": "not a dict"}),
    ])
    def test_absences_agree_too(self, path, document):
        from master_agent.runtime.input_resolution import _walk
        from master_agent.verification.evaluator import get_field

        assert _walk(document, path)[0] is False
        assert get_field(document, path)[0] is False
