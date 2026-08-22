"""LIVE ACCEPTANCE H — reasoning inside the step, not around it.

The Founder's objective:

    Think of three short names for a gardening notes app and write them
    into names.txt on the Desktop.

Nothing in that sentence says HOW. It does not need to: with
`Reasoning.Transform` and `Filesystem.WriteFile` both registered, the
shape is the only one they can form. Choosing it takes no judgement, and
the old behaviour paid a 20,869-character catalogue prompt to be told so
-- then lost the whole mission when every reasoning rung was out.

A model is still required. It is the only thing that can invent three
names. It is required INSIDE `Reasoning.Transform`, where the prompt is
the actual instruction.

    Planner provider calls           must be 0
    Reasoning.Transform executes     must be YES
    WriteFile receives PRODUCED text must be YES  (never predicted)
    names.txt on the Desktop         must be YES

The third is the one that is easy to fake and the whole point. The text
is bound out of the canonical Evidence that measured it -- if the
reasoning step produces nothing, or its Evidence does not match, the
binding fails and no file is written. That is the correct outcome, and
why a literal is never used.

Every provider call is counted at the one door reasoning goes through, so
"zero planning calls" is measured here, not asserted.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("KALPAVRIKSHA_DISABLE_MIC", "1")

sys.path.insert(0, "D:/MasterAgent")
sys.path.insert(0, "D:/MasterAgent/src")

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

import kalpavriksha_desktop as kd  # noqa: E402
from master_agent.ai_infrastructure.tiered_runner import TieredPromptRunner  # noqa: E402
from master_agent.missions.execution_status import (  # noqa: E402
    AWAITING_APPROVAL,
    AWAITING_FOUNDER_COMPLETION,
)

DESKTOP = Path(os.path.expanduser("~")) / "Desktop"
TARGET = DESKTOP / "names.txt"

OBJECTIVE = (
    "Think of three short names for a gardening notes app and write them "
    "into names.txt on the Desktop."
)

#: Every reasoning call, tagged with who asked. The Planner and
#: `Reasoning.Transform` use different requesters, so "did planning call a
#: provider?" is answerable by counting rather than by trusting.
CALLS: list[dict] = []


def _install_counter() -> None:
    original = TieredPromptRunner.run

    def counting(self, prompt, request, **kwargs):
        who = getattr(request, "requester", "") or "unknown"
        CALLS.append({"requester": who, "prompt_chars": len(prompt or "")})
        print(f"    [provider call] requester={who} prompt={len(prompt or '')} chars",
              flush=True)
        return original(self, prompt, request, **kwargs)

    TieredPromptRunner.run = counting


def banner(text):
    print("\n" + "=" * 70, flush=True)
    print(text, flush=True)
    print("=" * 70, flush=True)


def main() -> int:
    _install_counter()

    banner("BUILDING THE REAL PIPELINE")
    pipeline = kd._build_mission_pipeline()
    if pipeline is None:
        print("NO PIPELINE", flush=True)
        return 2
    (mission_service, runtime, mission_control, status, runner,
     set_mode, interactions, decide_approval) = pipeline

    if TARGET.exists():
        TARGET.unlink()
        print(f"removed a stale {TARGET} so its existence proves this run",
              flush=True)

    banner(f"OBJECTIVE\n{OBJECTIVE}")

    planning_before = len(CALLS)
    reply = kd._submit_objective(
        mission_service, runtime, mission_control, status, OBJECTIVE,
        timeout_seconds=420.0,
    )
    print(f"status : {reply.get('status')}", flush=True)
    print(f"reply  : {reply.get('reply')}", flush=True)

    for _round in range(12):
        if getattr(status, "approval_id", None):
            print(f"[founder] approving {status.approval_id}", flush=True)
            decide_approval(status.approval_id, True)
            kd._drive_until_settled(runtime, mission_control, status,
                                    status.objective_id, 120.0)
            continue
        if getattr(status, "status", None) == AWAITING_FOUNDER_COMPLETION:
            break
        break

    # ---- the measurements the Founder asked for --------------------
    planner_calls = [c for c in CALLS if "plan" in c["requester"].lower()]
    reasoning_calls = [c for c in CALLS if "transform" in c["requester"].lower()]
    other_calls = [c for c in CALLS if c not in planner_calls and c not in reasoning_calls]

    objective = None
    try:
        objective = mission_control.dispatcher.objective(status.objective_id)
    except Exception:  # noqa: BLE001
        pass

    steps, produced, evidence_note = [], "", ""
    if objective is not None:
        for task in getattr(objective, "tasks", ()) or ():
            steps.append(str(getattr(task, "capability", "?")))
            ev = getattr(task, "evidence", None)
            if isinstance(ev, dict) and "transform" in str(task.capability).lower():
                observed = (ev.get("observation") or {})
                produced = observed.get("text", "") or ""
                evidence_note = (
                    f"verdict={ev.get('verdict')} "
                    f"evidence_id={ev.get('evidence_id')} "
                    f"worker={ev.get('worker')} "
                    f"environment={ev.get('environment')}"
                )

    banner("MEASUREMENTS")
    print(f"Planner provider calls:   {len(planner_calls)}", flush=True)
    print(f"Reasoning provider calls: {len(reasoning_calls)}", flush=True)
    if other_calls:
        for c in other_calls:
            print(f"  other call: {c['requester']} ({c['prompt_chars']} chars)", flush=True)
    print(f"Planned steps:            {' -> '.join(steps) or '(none)'}", flush=True)
    print(f"Reasoning output:         {produced[:200]!r}", flush=True)
    print(f"Binding Evidence:         {evidence_note or '(none)'}", flush=True)
    print(f"names.txt exists:         {TARGET.exists()}", flush=True)
    contents = ""
    if TARGET.exists():
        contents = TARGET.read_text(encoding="utf-8", errors="replace")
        print("names.txt contents:", flush=True)
        print("---- contents ----", flush=True)
        print(contents, flush=True)
        print("------------------", flush=True)

    banner("VERDICT")
    checks = [
        ("Planner provider calls = 0", len(planner_calls) == 0),
        ("Reasoning.Transform actually executes", len(reasoning_calls) >= 1),
        ("final Desktop file", TARGET.exists() and bool(contents.strip())),
    ]
    # The one that matters: what was written must be what was PRODUCED,
    # not the objective's own words echoed into a literal.
    if produced and contents:
        checks.append((
            "WriteFile received produced text, not predicted text",
            produced.strip() in contents or contents.strip() in produced,
        ))
    else:
        checks.append(("WriteFile received produced text, not predicted text", False))

    for label, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'} {label}", flush=True)

    good = all(ok for _label, ok in checks)
    banner(f"LIVE ACCEPTANCE H: {'PASS' if good else 'FAIL'}")
    return 0 if good else 1


if __name__ == "__main__":
    raise SystemExit(main())
