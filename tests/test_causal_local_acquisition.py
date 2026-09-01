"""One controlled reality update through the production causal seams.

No network provider is contacted.  A provider-shaped local stub supplies
only the semantic plan proposal; the production Planner compiles it, the
production MissionPlan->Task translation preserves it, and the real
headless Browser Executive reads a deterministic data URL.  Independent
Browser Evidence is then fed into the existing Brain state owner.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

from master_agent.brain.deliberation import (
    DISCOVERY,
    Observation,
    deliberate,
    frame_for,
    initial_evidence_need,
    next_evidence_need,
    progress_of,
)
from master_agent.environment.browser_session import BrowserSessionManager
from master_agent.executor.executor import LocalExecutor
from master_agent.mission_control.adapters import discover_executives
from master_agent.mission_control.mission_control import MissionControl
from master_agent.missions.translation import objective_from_plan
from master_agent.permissions.permission_system import PermissionSystem
from master_agent.planner.catalogue import CapabilityOption
from master_agent.planner.plan import INFORMATION, Intent, SemanticRequirement
from master_agent.planner.planner import Planner
from master_agent.plugins.browser_gateway import BrowserGateway
from master_agent.plugins.browser_plugin import BrowserPlugin
from master_agent.plugins.browser_worker import BrowserWorker
from master_agent.plugins.registry import PluginRegistry
from master_agent.runtime.config import RuntimeConfig
from master_agent.runtime.engine import RuntimeEngine
from tests.approval_test_support import ApprovingGate
from tests.planner_test_support import StubRunner

REQUIREMENTS = (
    SemanticRequirement(
        "req_discover", INFORMATION, "identify viable candidates",
        founder_evidence="identify viable candidates", candidate_property=False,
    ),
    SemanticRequirement(
        "req_select", INFORMATION, "establish the canonical comparison set",
        founder_evidence="establish the canonical comparison set",
        candidate_property=False,
    ),
    SemanticRequirement(
        "req_compare", INFORMATION, "compare the required candidate property",
        founder_evidence="compare the required candidate property",
        candidate_property=True,
    ),
)

OPTIONS = (
    CapabilityOption(
        "Browser.OpenBrowserSession", required_args=("session_id",),
        optional_args=("headless",), args_complete=True,
        output_fields=("session_id", "opened_at", "headless"),
    ),
    CapabilityOption(
        "Browser.Navigate", required_args=("session_id", "url"),
        args_complete=True, output_fields=("url", "title"),
    ),
    CapabilityOption(
        "Browser.ReadPageText", required_args=("session_id",),
        args_complete=True, output_fields=("url", "title", "text", "truncated"),
    ),
    CapabilityOption(
        "Browser.CloseBrowserSession", required_args=("session_id",),
        args_complete=True, output_fields=("session_id", "closed", "warnings"),
    ),
)


def _proposal(url: str) -> dict:
    def row(step_id, capability, payload, depends_on=()):
        return {
            "id": step_id,
            "capability": capability,
            "payload": payload,
            "depends_on": list(depends_on),
            "covers": ["req_discover"],
            "success": {"description": f"{step_id} is independently observable"},
        }

    return {"steps": [
        row("open", "Browser.OpenBrowserSession", {
            "session_id": "causal-local", "headless": True,
        }),
        row("navigate", "Browser.Navigate", {
            "session_id": "causal-local", "url": url,
        }, ("open",)),
        row("read", "Browser.ReadPageText", {
            "session_id": "causal-local",
        }, ("navigate",)),
        row("close", "Browser.CloseBrowserSession", {
            "session_id": "causal-local",
        }, ("read",)),
    ]}


def _planner(reply: dict) -> Planner:
    planner = Planner.__new__(Planner)
    planner._runner = StubRunner(json.dumps(reply))
    planner._offline = False
    planner._requires_strong_reasoning = False
    planner._requester = "causal-local-test"
    planner.options = lambda: OPTIONS
    planner.mode = lambda: "both"
    return planner


class CandidateReader:
    """Local deterministic extraction reply; never a provider call."""

    def run(self, _prompt, _request):
        return SimpleNamespace(ok=True, text=json.dumps({
            "candidates": [{
                "id": "atlas",
                "summary": "Atlas",
                "criteria": {
                    "crit_1": {
                        "state": "unverified",
                        "finding": "qualification property not stated",
                        "evidence_id": "",
                    },
                },
            }],
        }))


def _serve(html: str):
    body = html.encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}/candidates"


def test_real_local_observation_changes_the_brains_next_decision():
    objective = "Identify viable candidates, select a canonical set, and compare it."
    frame = frame_for(objective=objective, requirements=REQUIREMENTS)
    assert frame is not None
    first_need = initial_evidence_need(frame, REQUIREMENTS)
    assert first_need is not None
    assert first_need.target_requirements == ("req_discover",)

    html = (
        "<html><head><title>Candidate Directory</title></head>"
        "<body><h1>Atlas</h1><p>Atlas is a viable candidate for qualification.</p>"
        "</body></html>"
    )
    server, server_thread, url = _serve(html)
    intent = Intent(
        goal=objective,
        requirements=REQUIREMENTS,
        context={
            "decision_frame": frame.as_dict(),
            "evidence_needed": first_need.as_dict(),
        },
    )

    outcome = _planner(_proposal(url)).plan(intent)
    assert outcome.refusal is None
    assert outcome.plan is not None
    assert {cover for step in outcome.plan.steps for cover in step.covers} == {
        "req_discover"
    }

    mission = objective_from_plan(outcome.plan, description=objective)
    for step, task in zip(outcome.plan.steps, mission.tasks, strict=True):
        assert task.capability == step.capability
        assert task.payload == step.payload
        assert task.input_bindings == step.input_bindings
        assert task.depends_on == step.depends_on
        assert task.expected_outcome == step.expected_outcome
        assert task.covers == step.covers

    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    sessions = BrowserSessionManager()
    registry = PluginRegistry()
    registry.register(BrowserPlugin(executor, sessions))
    control = MissionControl()
    discover_executives(control, registry)
    worker = BrowserWorker(executor, sessions)
    gateway = BrowserGateway(worker, permissions, executor.name)
    runtime = RuntimeEngine(
        control,
        RuntimeConfig(
            poll_interval_seconds=0, max_attempts=1, retry_delay_seconds=0,
        ),
        sleep=lambda _seconds: None,
        approval_gate=ApprovingGate(),
    )
    runtime.register_gateway("browser", gateway)
    submitted = control.submit_objective(mission)
    try:
        for _ in range(8):
            runtime.run_once()
            if submitted.is_complete or submitted.has_failure:
                break
    finally:
        runtime.stop()
        sessions.close_all()
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)

    assert submitted.is_complete
    read_task = submitted.task("read")
    assert read_task is not None
    assert read_task.result["text"].endswith(
        "Atlas is a viable candidate for qualification."
    )
    assert read_task.evidence["verdict"] == "matched"
    assert read_task.evidence["observation"]["page_usable"] is True
    assert "Atlas" in read_task.evidence["observation"]["text"]

    record = read_task.evidence
    observed = record["observation"]
    evidence = Observation(
        evidence_id=record["evidence_id"],
        text=observed["text"],
        source_class=DISCOVERY,
        url=observed["url"],
        observed_at=record["captured_at"],
    )
    decision = deliberate(frame, (evidence,), reasoner=CandidateReader())
    after = progress_of(
        objective, REQUIREMENTS, submitted.tasks, deliberation=decision,
    )
    second_need = next_evidence_need(decision, after)

    assert decision.candidates[0].candidate_id == "atlas"
    assert after.satisfied == ("req_discover",)
    assert second_need is not None
    assert second_need.action == "qualify_candidates"
    assert second_need.target_requirements == ("req_select",)
    assert second_need.target_requirements != first_need.target_requirements
    assert read_task.evidence["evidence_id"] in after.evidence_ids
