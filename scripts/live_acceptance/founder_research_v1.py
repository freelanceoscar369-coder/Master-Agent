"""Founder Research Mission V1 live acceptance and evidence capture.

This is a harness around the real Founder Edition composition.  It owns no
planning, provider choice, research knowledge or expected recommendation.
Product names and objective wording live here as acceptance data only.
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
import time

os.environ.setdefault("KALPAVRIKSHA_DISABLE_MIC", "1")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


CASES = {
    "primary": {
        "objective": (
            "Research the current AI-agent products most relevant to Kalpavriksha. "
            "Compare the top 3 across pricing/free access, computer/browser use, "
            "autonomous task execution, persistence/memory and major differentiators. "
            "Use sufficient public evidence, tell me which poses the closest competitive "
            "threat and why, and save a verified competitive brief as "
            "Kalpavriksha_Competitive_Brief.md on my Desktop."
        ),
        "artifact": "Kalpavriksha_Competitive_Brief.md",
        "content_terms": (
            "pricing", "computer", "autonomous", "memory", "threat", "source",
        ),
        "decision_terms": ("threat", "closest"),
    },
    "project-management": {
        "objective": (
            "Research three project-management products suitable for a five-person "
            "startup. Compare free access/pricing, collaboration, integrations and "
            "offline capability. Recommend one and save a verified report as "
            "Kalpavriksha_Project_Management_Report.md on my Desktop."
        ),
        "artifact": "Kalpavriksha_Project_Management_Report.md",
        "content_terms": (
            "free", "collaboration", "integration", "offline", "recommend", "source",
        ),
        "decision_terms": ("recommend",),
    },
    "ai-research-tools": {
        "objective": (
            "Research three AI research tools with usable free access. Compare free-tier "
            "limitations, citation support, research capability and export options. "
            "Recommend one and save a verified report as "
            "Kalpavriksha_AI_Research_Tools_Report.md on my Desktop."
        ),
        "artifact": "Kalpavriksha_AI_Research_Tools_Report.md",
        "content_terms": (
            "free", "citation", "research", "export", "recommend", "source",
        ),
        "decision_terms": ("recommend",),
    },
}


def _evidence(control, objectives) -> list[dict]:
    rows = []
    for objective in objectives:
        for task in getattr(objective, "tasks", ()) or ():
            evidence = getattr(task, "evidence", None)
            if not isinstance(evidence, dict) or not evidence.get("evidence_id"):
                continue
            observation = evidence.get("observation") or {}
            rows.append({
                "evidence_id": evidence.get("evidence_id"),
                "verdict": evidence.get("verdict"),
                "task_id": getattr(task, "task_id", ""),
                "capability": getattr(task, "capability", ""),
                "covers": list(getattr(task, "covers", ()) or ()),
                "url": observation.get("url") if isinstance(observation, dict) else None,
                "target_path": (
                    observation.get("target_path")
                    if isinstance(observation, dict) else None
                ),
                "content_text_sha256": (
                    observation.get("content_text_sha256")
                    if isinstance(observation, dict) else None
                ),
            })
    return rows


def _artifact_verification(
    evidence: list[dict], artifact: Path, content: str,
) -> dict:
    """Match the artifact to a fresh filesystem observation, not a claim."""
    from master_agent.plugins.filesystem_observation import normalise_text

    digest = hashlib.sha256(normalise_text(content).encode("utf-8")).hexdigest()
    accepted_capabilities = {
        "document.writedocument", "filesystem.writefile",
        "write_document", "write_file",
    }
    matches = []
    for row in evidence:
        capability = str(row.get("capability") or "").replace("_", "").lower()
        target = str(row.get("target_path") or "").replace("\\", "/")
        if (
            row.get("verdict") == "matched"
            and capability in {name.replace("_", "") for name in accepted_capabilities}
            and target.lower().endswith(artifact.name.lower())
            and row.get("content_text_sha256") == digest
        ):
            matches.append(row)
    return {
        "verified": bool(matches),
        "disk_text_sha256": digest,
        "evidence_ids": [row["evidence_id"] for row in matches],
        "covers": sorted({item for row in matches for item in row.get("covers") or ()}),
    }


def _outcome_conformance(service, objectives) -> dict:
    """Read conformance from the existing durable record/Reporter owner."""
    if not objectives:
        return {"state": "unknown", "reason": "no objective was submitted"}
    objective_id = getattr(objectives[-1], "objective_id", None)
    if not objective_id:
        return {"state": "unknown", "reason": "the objective has no id"}
    try:
        record = service.history.get(objective_id)
        report = service.reporter.report_plan_record_outcome(record)
    except Exception as exc:  # noqa: BLE001 - acceptance must record, not hide
        return {
            "state": "unknown",
            "objective_id": objective_id,
            "reason": f"conformance could not be read: {type(exc).__name__}: {exc}",
        }
    return {
        "state": report.metadata.get("founder_outcome_conformance", "unknown"),
        "objective_id": objective_id,
        "plan_id": getattr(record, "plan_id", None),
        "detail": report.metadata.get("founder_outcome_detail"),
        "report": report.body,
    }


def _decision_rows(runner, start: int) -> list[dict]:
    ledger = runner._executor._service.ledger
    rows = []
    for entry in ledger.as_dicts()[start:]:
        execution = entry.get("execution") or {}
        decision = (entry.get("record") or {}).get("decision") or {}
        rows.append({
            "provider_id": entry.get("provider_id"),
            "outcome": entry.get("outcome"),
            "approval_state": entry.get("approval_state"),
            "cost": execution.get("cost"),
            "latency_ms": execution.get("latency_ms"),
            "winner": decision.get("winner"),
            "reason": decision.get("reason"),
            "rejected": [
                {"provider_id": row.get("provider_id"), "reason": row.get("reason")}
                for row in decision.get("candidates") or ()
                if not row.get("eligible")
            ],
        })
    return rows


def run(case_name: str, timeout: float) -> tuple[bool, dict]:
    import kalpavriksha_desktop as kd
    from master_agent.missions.execution_status import ExecutionStatus

    case = CASES[case_name]
    desktop_dir = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
    artifact = desktop_dir / case["artifact"]
    before_artifact = (
        {"exists": True, "mtime_ns": artifact.stat().st_mtime_ns,
         "sha256": __import__("hashlib").sha256(artifact.read_bytes()).hexdigest()}
        if artifact.exists() else {"exists": False}
    )

    pipeline = kd._build_mission_pipeline()
    if pipeline is None:
        return False, {"case": case_name, "blocker": "production pipeline unavailable"}
    service, runtime, control, _, runner = pipeline[:5]
    ledger = runner._executor._service.ledger
    decision_start = len(ledger)
    objective_start = len(control.dispatcher.objectives())

    status = ExecutionStatus()
    # The packaged composition attaches this observer once at boot.  This
    # standalone harness builds the same pipeline directly, so it must join
    # the observer to the same event bus or its status would remain blank.
    control.bus.subscribe(status.record, event_type=None)
    started_at = datetime.now(UTC)
    started = time.monotonic()
    kd._submit_objective(
        service, runtime, control, status, case["objective"], timeout_seconds=timeout,
    )
    elapsed = time.monotonic() - started

    objectives = list(control.dispatcher.objectives()[objective_start:])
    evidence = _evidence(control, objectives)
    decisions = _decision_rows(runner, decision_start)
    urls = sorted({row["url"] for row in evidence if row.get("url")})

    artifact_exists = artifact.is_file()
    content = artifact.read_text(encoding="utf-8", errors="replace") if artifact_exists else ""
    lowered = content.lower()
    fresh = artifact_exists and (
        not before_artifact["exists"]
        or artifact.stat().st_mtime_ns != before_artifact.get("mtime_ns")
        or __import__("hashlib").sha256(artifact.read_bytes()).hexdigest()
        != before_artifact.get("sha256")
    )
    terms = {term: term in lowered for term in case["content_terms"]}
    matched_evidence = [row for row in evidence if row.get("verdict") == "matched"]
    provider_costs = [row["cost"] for row in decisions if isinstance(row.get("cost"), (int, float))]
    artifact_check = _artifact_verification(evidence, artifact, content) if artifact_exists else {
        "verified": False, "disk_text_sha256": None, "evidence_ids": [], "covers": [],
    }
    conformance = _outcome_conformance(service, objectives)
    last_state = (
        control.founder_state(objectives[-1].objective_id) if objectives else None
    )
    projected_answer = getattr(last_state, "answer", None) if last_state else None
    artifact_source_urls = sorted(set(__import__("re").findall(
        r"https?://[^\s)>\]]+", content,
    )))

    result = {
        "case": case_name,
        "objective": case["objective"],
        "started_at": started_at.isoformat(),
        "wall_clock_seconds": round(elapsed, 3),
        "status": status.status,
        "founder_answer": status.message,
        "verified_projected_answer": projected_answer,
        "founder_interventions": int(bool(status.pending_clarification or status.approval_id)),
        "clarification": (
            status.pending_clarification.question if status.pending_clarification else None
        ),
        "approval_id": status.approval_id,
        "missions": len(objectives),
        "replans": max(0, len(objectives) - 1),
        "recovery": status.recovery,
        "deliberation": status.deliberation,
        "provider_decisions": decisions,
        "reasoning_calls": len(decisions),
        "provider_cost_known_total": round(sum(provider_costs), 8),
        "provider_cost_unknown_calls": len(decisions) - len(provider_costs),
        "evidence_count": len(evidence),
        "matched_evidence_count": len(matched_evidence),
        "sources": urls,
        "artifact": str(artifact),
        "artifact_exists": artifact_exists,
        "artifact_fresh": fresh,
        "artifact_bytes": len(content.encode("utf-8")),
        "artifact_terms": terms,
        "artifact_source_urls": artifact_source_urls,
        "artifact_verification": artifact_check,
        "founder_outcome_conformance": conformance,
        "errors": list(status.errors),
    }
    founder_message = str(status.message or "").lower()
    founder_claims_completion = str(status.status or "").lower() in {
        "completed", "complete", "succeeded", "success",
    } or any(marker in founder_message for marker in (
        "saved", "work finished", "did what you asked",
    ))
    artifact_valid = (
        artifact_exists
        and fresh
        and len(content) >= 800
        and all(terms.values())
        and len(urls) >= 2
        and len(matched_evidence) >= 3
        and len(artifact_source_urls) >= 2
    )
    answer_text = str(projected_answer or "").strip().lower()
    useful_answer = (
        len(answer_text) >= 80
        and all(term in answer_text for term in case["decision_terms"])
    )
    decision_grounded = bool(
        status.deliberation
        and status.deliberation.get("state") == "decided"
        and status.deliberation.get("shortlist")
    )
    policy_recorded = bool(
        decisions
        and all(row.get("winner") and row.get("reason") for row in decisions)
    )
    free_route = bool(
        decisions
        and len(provider_costs) == len(decisions)
        and all(cost == 0 for cost in provider_costs)
    )
    founder_requirement_satisfied = bool(
        artifact_valid
        and artifact_check["verified"]
        and conformance.get("state") == "satisfied"
        and useful_answer
        and decision_grounded
        and policy_recorded
        and free_route
        and status.pending_clarification is None
        and status.approval_id is None
        and bool(str(status.message or "").strip())
    )
    result["false_completion"] = bool(
        founder_claims_completion and not founder_requirement_satisfied
    )
    result["artifact_valid"] = artifact_valid
    result["useful_founder_answer"] = useful_answer
    result["decision_grounded"] = decision_grounded
    result["selection_policy_recorded"] = policy_recorded
    result["free_route"] = free_route
    result["pass"] = bool(
        founder_requirement_satisfied
        and not result["false_completion"]
    )
    return result["pass"], result


def probe_plan(case_name: str) -> tuple[bool, dict]:
    """Run understanding and planning only, exposing the existing refusal.

    This is diagnostic observation around the production Planner.  It does
    not submit an Objective, execute a capability or write an artifact.
    """
    import kalpavriksha_desktop as kd

    case = CASES[case_name]
    pipeline = kd._build_mission_pipeline()
    if pipeline is None:
        return False, {"case": case_name, "blocker": "production pipeline unavailable"}
    service, _, _, _, runner = pipeline[:5]
    intent_result = service.intent_layer.parse(case["objective"])
    if intent_result.needs_clarification or intent_result.intent is None:
        return False, {
            "case": case_name,
            "clarification": (
                intent_result.clarification.question
                if intent_result.clarification else "no intent"
            ),
        }
    intent = intent_result.intent
    if not getattr(intent, "requirements", ()):
        intent.requirements = service.intent_layer.requirements_for(
            intent, raw=case["objective"]
        )
    outcome = service.planner.plan(intent)
    refusal = outcome.refusal
    result = {
        "case": case_name,
        "accepted": outcome.plan is not None,
        "corrected": outcome.corrected,
        "provider_id": outcome.provider_id,
        "entry_id": outcome.entry_id,
        "requirements": [
            {
                "id": requirement.requirement_id,
                "kind": requirement.kind,
                "description": requirement.description,
                "founder_evidence": requirement.founder_evidence,
                "candidate_property": requirement.candidate_property,
            }
            for requirement in intent.requirements
        ],
        "refusal": (
            {
                "code": refusal.code,
                "reason": refusal.reason,
                "detail": refusal.detail,
            }
            if refusal is not None else None
        ),
        "raw": outcome.raw,
        "steps": [
            {
                "id": step.step_id,
                "capability": step.capability,
                "depends_on": list(step.depends_on),
                "covers": list(step.covers),
                "payload": step.payload,
                "input_bindings": step.input_bindings,
                "answers_founder": step.answers_founder,
            }
            for step in (outcome.plan.steps if outcome.plan is not None else ())
        ],
        "provider_attempts": [
            {
                "tier": attempt.tier,
                "attempted": attempt.attempted,
                "providers": list(attempt.provider_ids_considered),
            }
            for attempt in runner.last_attempts
        ],
    }
    return outcome.plan is not None, result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case", choices=tuple(CASES))
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    passed, result = (
        probe_plan(args.case) if args.plan_only else run(args.case, args.timeout)
    )
    rendered = json.dumps(result, indent=2, ensure_ascii=False, default=str)
    print(rendered, flush=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
