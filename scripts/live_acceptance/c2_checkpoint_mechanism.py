"""LIVE ACCEPTANCE C (mechanism) - the founder checkpoint, on a FIXED plan.

## Why this exists alongside `c_founder_checkpoint.py`

That runner is the real thing: a founder sentence, planned by Gemini,
carrying its own "show me before you write it" into the plan. It is
blocked whenever the free tier is spent, because the Planner is the only
component that needs a provider.

This one substitutes a hand-authored MissionPlan and leaves EVERYTHING
downstream real -- Mission Control, the Runtime, the approval queue, the
permission boundary, the Filesystem executive, Verification. So it proves
the checkpoint MECHANISM without spending a single token.

**Stated honestly: the plan here is fixed, not reasoned.** It does not
prove the Planner marks a checkpoint when a founder asks for one -- rule
12b in `planner/prompting.py` is what does that, and only the Gemini
runner can demonstrate it end to end. What this proves is everything
after: that a step carrying `founder_checkpoint` holds, that it holds
*without executing*, that Continue resumes the SAME payload, and that Stop
does not perform the mutation.

Two runs, because the important half can only be shown by something not
happening.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("KALPAVRIKSHA_FMEA_REASONING_TIER", "gemini")
os.environ.setdefault("KALPAVRIKSHA_DISABLE_MIC", "1")

sys.path.insert(0, "D:/MasterAgent")
sys.path.insert(0, "D:/MasterAgent/src")

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

import kalpavriksha_desktop as kd  # noqa: E402
from master_agent.missions.execution_status import AWAITING_APPROVAL  # noqa: E402
from master_agent.planner.plan import Intent, MissionPlan, PlanOutcome, Step  # noqa: E402
from master_agent.verification.evidence import (  # noqa: E402
    ExpectedOutcome,
    ObservationCheck,
)

DESKTOP = Path(os.path.expanduser("~")) / "Desktop"
PAYLOAD = "Kalpavriksha checkpoint acceptance."


def banner(text):
    print("\n" + "=" * 70, flush=True)
    print(text, flush=True)
    print("=" * 70, flush=True)


class FixedPlanner:
    """Returns one hand-authored plan. Stands exactly where the real
    Planner stands, so nothing downstream can tell the difference."""

    def __init__(self, folder: str) -> None:
        self._folder = folder
        self.calls = 0

    def plan(self, intent, *, task_id="", objective_id=None):
        self.calls += 1
        return PlanOutcome(plan=MissionPlan(
            objective=getattr(intent, "goal", "") or "checkpoint acceptance",
            steps=[
                Step(
                    step_id="step_1",
                    capability="Filesystem.CreateFolder",
                    payload={"name": self._folder, "location": "desktop"},
                    # Mission Control REJECTS a step with no expectation
                    # ("step_1: no expected outcome") -- Constitution
                    # §3.2 enforcing itself, so Verification always has
                    # something concrete to compare an Observation to.
                    # A step whose ExpectedOutcome states no checks is
                    # rejected too: it would evaluate to ERROR under the
                    # frozen evaluator, putting a step into the Runtime
                    # that can never be verified. `filesystem_gateway`
                    # rebinds these text-shaped checks to disk-checkable
                    # ones at verify time -- the Planner is not expected
                    # to know what a disk observation looks like.
                    expected_outcome=ExpectedOutcome(
                        description=f"The folder {self._folder} exists on the Desktop.",
                        checks=[ObservationCheck(
                            field="exists", operator="equals", value=True,
                            description="the folder exists",
                        )],
                    ),
                ),
                Step(
                    step_id="step_2",
                    capability="Filesystem.WriteFile",
                    payload={
                        "location": "desktop",
                        "path": f"{self._folder}/notes.txt",
                        "content": PAYLOAD,
                    },
                    depends_on=["step_1"],
                    # The founder asked to see this before it happens.
                    expected_outcome=ExpectedOutcome(
                        description=(
                            f"notes.txt exists in {self._folder} containing: {PAYLOAD}"
                        ),
                        checks=[
                            ObservationCheck(
                                field="exists", operator="equals", value=True,
                                description="notes.txt exists",
                            ),
                            ObservationCheck(
                                field="content", operator="contains", value=PAYLOAD,
                                description="it contains the previewed text",
                            ),
                        ],
                    ),
                    founder_checkpoint=(
                        f"About to write this into {self._folder}/notes.txt: "
                        f"{PAYLOAD}"
                    ),
                ),
            ],
        ))


def run(label: str, continue_it: bool) -> bool:
    stamp = time.strftime("%H%M%S")
    folder_name = f"KV_C2_{label}_{stamp}"
    folder = DESKTOP / folder_name
    target = folder / "notes.txt"

    banner(f"RUN {label} - founder will {'CONTINUE' if continue_it else 'STOP'}")
    pipeline = kd._build_mission_pipeline()
    if pipeline is None:
        print("NO PIPELINE.", flush=True)
        return False
    (mission_service, runtime, mission_control, status, _runner,
     _set_mode, _interactions, decide_approval) = pipeline

    # The ONLY substitution. Everything else below is the shipped object.
    planner = FixedPlanner(folder_name)
    mission_service.planner = planner

    ok = True
    outcome = mission_service.start(Intent(
        goal=f"Create {folder_name} on the Desktop, then show me the text "
             f"before writing notes.txt",
        context={"raw_input": "fixed-plan checkpoint acceptance"},
    ))
    if not outcome.accepted:
        print(f"FAIL plan not accepted: status={getattr(outcome,'status',None)!r} "
              f"refusal={outcome.refusal} reasons={getattr(outcome,'reasons',None)}", flush=True)
        return False
    status.objective_id = outcome.objective_id
    print(f"objective_id: {outcome.objective_id}  (planner calls: {planner.calls})",
          flush=True)

    kd._drive_until_settled(runtime, mission_control, status,
                            outcome.objective_id, 120.0)

    print("\n-- did it hold at a checkpoint?", flush=True)
    if status.approval_id:
        print(f"   PASS held. kind={status.approval_kind!r}", flush=True)
        if status.approval_kind == "founder_checkpoint":
            print("   PASS it is a CHECKPOINT, not a permission decision", flush=True)
        else:
            print(f"   FAIL expected founder_checkpoint, got {status.approval_kind!r}",
                  flush=True)
            ok = False
        print(f"   preview: {status.approval_preview[:250]}", flush=True)
        if PAYLOAD in (status.approval_preview or ""):
            print("   PASS the preview is RESOLVED - it carries the real text", flush=True)
        else:
            print("   FAIL the preview does not carry the resolved payload", flush=True)
            ok = False
    else:
        print(f"   FAIL no checkpoint raised (status={status.status!r})", flush=True)
        ok = False

    print("\n-- was the prerequisite step done first?", flush=True)
    if folder.is_dir():
        print(f"   PASS folder exists: {folder}", flush=True)
    else:
        print(f"   FAIL prerequisite step did not run: {folder}", flush=True)
        ok = False

    print("\n-- has the held mutation happened yet? (must be NO)", flush=True)
    if target.exists():
        print("   FAIL notes.txt written before the founder answered", flush=True)
        ok = False
    else:
        print("   PASS nothing written while waiting", flush=True)

    if status.approval_id:
        banner(f"FOUNDER ANSWERS: {'Continue' if continue_it else 'Stop'}")
        decide_approval(status.approval_id, continue_it, f"acceptance C2 {label}")
        if status.requires_founder_completion and status.completion_id:
            mission_control.confirm_completion(status.completion_id)

    print(f"\nfinal status : {status.status}", flush=True)

    banner(f"RUN {label} - INDEPENDENT VERIFICATION (fresh look at disk)")
    if continue_it:
        if target.is_file():
            body = target.read_text(encoding="utf-8", errors="replace")
            print(f"   PASS notes.txt written: {body.strip()!r}", flush=True)
            if PAYLOAD in body:
                print("   PASS the SAME payload that was previewed", flush=True)
            else:
                print("   FAIL written text differs from the preview", flush=True)
                ok = False
        else:
            print("   FAIL Continue did not produce the file", flush=True)
            ok = False
    else:
        if target.exists():
            print("   FAIL Stop executed the mutation anyway", flush=True)
            ok = False
        else:
            print("   PASS Stop did not execute the mutation", flush=True)

    try:
        if target.exists():
            target.unlink()
        if folder.is_dir():
            folder.rmdir()
        print(f"   (cleaned up {folder})", flush=True)
    except OSError as exc:
        print(f"   (left {folder}: {exc})", flush=True)
    return ok


def main() -> int:
    a = run("CONT", continue_it=True)
    b = run("STOP", continue_it=False)
    banner(f"LIVE ACCEPTANCE C (mechanism): {'PASS' if (a and b) else 'FAIL'}"
           f"   continue={'PASS' if a else 'FAIL'}  stop={'PASS' if b else 'FAIL'}")
    return 0 if (a and b) else 1


if __name__ == "__main__":
    raise SystemExit(main())
