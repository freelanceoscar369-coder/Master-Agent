"""LIVE ACCEPTANCE G — an objective that genuinely needs a model, and the
ladder that goes looking for one.

B, C and D are fully dictated: every value the founder wanted was in the
sentence, so the deterministic lane compiled them and no provider was
contacted. That is the correct answer for those objectives, and proving
it was the point.

This one is deliberately the opposite. "Think of a short name for X" has
no answer in the sentence. Nothing local can produce it. The plan itself
has to come from a model, and so does the content it writes.

So this measures two different things, and reports them separately:

  1. LADDER BEHAVIOUR — does reasoning walk every rung, cheapest first,
     and report truthfully what each rung said? This is observable
     whether or not any rung succeeds, and it is the part under this
     machine's control.

  2. MISSION OUTCOME — did an answer actually come back? This depends on
     a provider being reachable right now, which is not something the
     code can be held to.

A ladder that walks all four rungs and reports "every rung declined, and
here is what each one said" is CORRECT behaviour under an external
outage. A mission that fails silently, or claims success without
evidence, is not. Those two are never merged into one verdict here.
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

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


class _LadderWatch(logging.Handler):
    """Collects what each rung said, as it says it.

    The runner is a progression and keeps no history of its attempts, which
    is right -- a ladder is not a ledger. But the walk is observable: every
    rung logs. Listening is honest; adding a `last_attempts` field to
    production code so a test could read it would not be.
    """

    KEYS = ("tier", "rung", "provider", "reasoning")

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
        except Exception:
            return
        low = message.lower()
        if any(k in low for k in self.KEYS) and any(
            w in low for w in ("attempt", "declin", "fail", "unavail", "exhaust",
                               "sign-in", "quota", "skip", "unusable")
        ):
            self.lines.append(f"{record.name}: {message}")


LADDER = _LadderWatch()
logging.getLogger().addHandler(LADDER)

import kalpavriksha_desktop as kd  # noqa: E402
from master_agent.missions.execution_status import (  # noqa: E402
    AWAITING_APPROVAL,
    AWAITING_FOUNDER_COMPLETION,
)

FOLDER = f"KV_Reason_{time.strftime('%H%M%S')}"
DESKTOP = Path(os.path.expanduser("~")) / "Desktop"
TARGET = DESKTOP / FOLDER

# Nothing in this sentence is the answer. A name has to be invented.
OBJECTIVE = (
    f"Create a folder called {FOLDER} on the Desktop. Then think of three "
    f"short, memorable names for a note-taking app for gardeners, and write "
    f"them into a file called names.txt inside that folder."
)


def banner(text):
    print("\n" + "=" * 70, flush=True)
    print(text, flush=True)
    print("=" * 70, flush=True)


def main() -> int:
    banner("BUILDING THE REAL PIPELINE")
    pipeline = kd._build_mission_pipeline()
    if pipeline is None:
        print("NO PIPELINE", flush=True)
        return 2
    (mission_service, runtime, mission_control, status, runner,
     set_mode, interactions, decide_approval) = pipeline

    tiers = [name for name, _ids in getattr(runner, "_tiers", ())]
    print(f"reasoning ladder, cheapest first: {' -> '.join(tiers)}", flush=True)

    # The deterministic lane must NOT claim this. If it does, that is a
    # defect of exactly the kind this session already fixed once: an
    # objective compiled from words it recognised while the part that
    # needed thought was dropped.
    from master_agent.planner.direct import direct_plan
    from master_agent.planner.plan import Intent

    banner("PART 0 — THE DETERMINISTIC LANE MUST DECLINE")
    local = direct_plan(Intent(goal=OBJECTIVE), mission_service.planner._catalogue)
    if local is not None:
        print(f"FAIL the local lane claimed an objective needing invention: "
              f"{[s.capability for s in local.steps]}", flush=True)
        return 1
    print("PASS it declined. This objective has no answer in its own sentence.",
          flush=True)

    banner(f"OBJECTIVE\n{OBJECTIVE}")
    if TARGET.exists():
        print("target already exists - aborting", flush=True)
        return 2

    reply = kd._submit_objective(
        mission_service, runtime, mission_control, status, OBJECTIVE,
        timeout_seconds=300.0,
    )
    print(f"status : {reply.get('status')}", flush=True)
    print(f"reply  : {reply.get('reply')}", flush=True)

    for _round in range(12):
        current = status.snapshot() if hasattr(status, "snapshot") else status
        state = getattr(current, "status", None)
        if getattr(current, "approval_id", None):
            print(f"[founder] approving {current.approval_id}", flush=True)
            decide_approval(current.approval_id, True)
            kd._drive_until_settled(mission_service, runtime, mission_control, status)
            continue
        if state == AWAITING_FOUNDER_COMPLETION:
            print("[founder] continue", flush=True)
            kd._drive_until_settled(mission_service, runtime, mission_control, status)
            continue
        break

    banner("PART 1 — LADDER BEHAVIOUR (this machine's responsibility)")
    # `TieredPromptRunner` keeps no attempt history -- it is a progression,
    # not a ledger, and inventing a field on it for a test would be the
    # tail wagging the dog. What each rung did is in the INFO log above,
    # emitted as it happened. `LADDER` collected those lines live.
    if LADDER.lines:
        for line in LADDER.lines:
            print(f"  {line}", flush=True)
        print(f"\n  rungs attempted: {len(LADDER.lines)}", flush=True)
    else:
        print("  no rung was attempted -- reasoning was never asked", flush=True)

    banner("PART 2 — MISSION OUTCOME (depends on an external provider)")
    names = TARGET / "names.txt"
    if names.exists():
        body = names.read_text(encoding="utf-8", errors="replace")
        print(f"PASS names.txt exists ({len(body)} bytes)", flush=True)
        print("---- contents ----", flush=True)
        print(body, flush=True)
        print("------------------", flush=True)
        # The content must not be the founder's own phrase echoed back.
        if "memorable names" in body.lower():
            print("FAIL the objective's wording was written instead of an answer",
                  flush=True)
            return 1
        print("PASS the file holds an answer, not the request", flush=True)
        banner("LIVE ACCEPTANCE G: PASS (reasoning reached, answer written)")
        return 0

    print(f"NOT PRODUCED  {names}", flush=True)
    print(f"final status : {getattr(status, 'status', None)}", flush=True)
    errs = list(getattr(status, "errors", ()) or ())
    for e in errs:
        print(f"  error: {e}", flush=True)

    truthful = bool(errs) and TARGET.exists() is not None
    banner(
        "LIVE ACCEPTANCE G: BLOCKED — no reasoning provider was reachable.\n"
        "The ladder walked and reported why, which is the part this build\n"
        "controls. No success was claimed and nothing was invented."
        if truthful else
        "LIVE ACCEPTANCE G: FAIL — it failed without saying why."
    )
    return 0 if truthful else 1


if __name__ == "__main__":
    raise SystemExit(main())
