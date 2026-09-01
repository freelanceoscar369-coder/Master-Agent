"""The Founder Research V1 gate must reject cosmetic completion."""
from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

from master_agent.plugins.filesystem_observation import normalise_text
from scripts.live_acceptance.founder_research_v1 import (
    AUTHORIZED_REASONING_PROVIDERS,
    _activate_authorized_provider_scope,
    _artifact_verification,
    _capture_planner_translations,
)


def _digest(text: str) -> str:
    return hashlib.sha256(normalise_text(text).encode("utf-8")).hexdigest()


def test_artifact_gate_accepts_only_matched_fresh_write_evidence(tmp_path):
    artifact = tmp_path / "report.md"
    content = "# Report\n\nEvidence-backed conclusion."
    artifact.write_text(content, encoding="utf-8")
    evidence = [{
        "evidence_id": "ev-write",
        "verdict": "matched",
        "capability": "Document.WriteDocument",
        "target_path": "report.md",
        "content_text_sha256": _digest(content),
        "covers": ["req_1", "req_2"],
    }]

    result = _artifact_verification(evidence, artifact, content)

    assert result == {
        "verified": True,
        "disk_text_sha256": _digest(content),
        "evidence_ids": ["ev-write"],
        "covers": ["req_1", "req_2"],
    }


def test_artifact_gate_rejects_a_successful_write_with_wrong_disk_content(tmp_path):
    artifact = tmp_path / "report.md"
    artifact.write_text("changed", encoding="utf-8")
    evidence = [{
        "evidence_id": "ev-old",
        "verdict": "matched",
        "capability": "Filesystem.WriteFile",
        "target_path": "report.md",
        "content_text_sha256": _digest("old content"),
        "covers": ["req_1"],
    }]

    assert _artifact_verification(evidence, artifact, "changed")["verified"] is False


def test_artifact_gate_rejects_non_write_evidence_even_with_same_digest(tmp_path):
    artifact = tmp_path / "report.md"
    content = "report"
    artifact.write_text(content, encoding="utf-8")
    evidence = [{
        "evidence_id": "ev-read",
        "verdict": "matched",
        "capability": "Filesystem.ReadFile",
        "target_path": "report.md",
        "content_text_sha256": _digest(content),
        "covers": ["req_1"],
    }]

    assert _artifact_verification(evidence, artifact, content)["verified"] is False


def test_live_acceptance_disclosure_scope_names_only_the_authorized_apis():
    assert AUTHORIZED_REASONING_PROVIDERS == {"gemini.api", "openrouter.api"}


def test_activating_acceptance_scope_is_explicit_not_an_import_side_effect(monkeypatch):
    # `setenv` registers teardown even when the variable started absent;
    # the helper writes through os.environ deliberately because it runs
    # outside pytest in acceptance.
    monkeypatch.setenv("KALPAVRIKSHA_FMEA_REASONING_TIER", "not-scoped")

    _activate_authorized_provider_scope()

    assert __import__("os").environ["KALPAVRIKSHA_FMEA_REASONING_TIER"] == "gemini"


def test_acceptance_uses_the_existing_disposable_state_override(monkeypatch, tmp_path):
    monkeypatch.delenv("KALPAVRIKSHA_STATE_DIR", raising=False)

    _activate_authorized_provider_scope(tmp_path / "isolated-state")

    assert __import__("os").environ["KALPAVRIKSHA_STATE_DIR"] == str(
        tmp_path / "isolated-state"
    )


def test_planner_translation_capture_preserves_exact_local_replay_material(tmp_path):
    class Runner:
        def run(self, prompt, request, **kwargs):
            return SimpleNamespace(
                provider_id="provider.test",
                entry_id=8,
                text='{"plan":{"steps":[]}}',
                ok=True,
                verified=True,
                evidence=SimpleNamespace(
                    verdict=SimpleNamespace(value="matched"),
                    observation={"json": {"plan": {"steps": []}}},
                ),
            )

    runner = Runner()
    trace_path = tmp_path / "planner_translation_trace.json"
    traces = _capture_planner_translations(runner, trace_path=trace_path)

    runner.run(
        "exact prompt",
        SimpleNamespace(requester="planner"),
        expected=SimpleNamespace(),
    )

    assert traces[0]["prompt"] == "exact prompt"
    assert traces[0]["response"] == '{"plan":{"steps":[]}}'
    assert traces[0]["parsed_json"] == {"plan": {"steps": []}}
    assert traces[0]["provider_id"] == "provider.test"
    assert json.loads(trace_path.read_text(encoding="utf-8")) == traces
