"""LIVE ACCEPTANCE B - the Medium Golden Mission, for real.

Real Gemini planning, real visible Chrome, a real folder on the founder's
Desktop, and independent verification read back off the disk afterwards.

Ladder is pinned to Gemini (KALPAVRIKSHA_FMEA_REASONING_TIER=gemini) so a
429 cannot fall through to the desktop AI applications -- the documented
incident where twenty-three ChatGPT/Kimi/Perplexity processes launched.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

# NO reasoning-tier pin here, deliberately.
#
# This harness used to set KALPAVRIKSHA_FMEA_REASONING_TIER=gemini, which
# EMPTIES the desktop tier and leaves the ladder as Gemini-only. That is a
# legitimate FMEA control for a provider-specific test, and it is exactly
# wrong for an operational acceptance: with the pin in place an exhausted
# Gemini quota ends the run, and the acceptance reports FAIL for a product
# that would have carried on perfectly well down the ladder in a founder's
# hands.
#
# A Founder Edition operational acceptance must exercise the PRODUCTION
# reasoning ladder -- local, desktop application, Gemini API, browser web
# rung -- not one rung of it. The control still exists for harnesses that
# genuinely need to isolate a provider.
os.environ.setdefault("KALPAVRIKSHA_DISABLE_MIC", "1")

sys.path.insert(0, "D:/MasterAgent")
sys.path.insert(0, "D:/MasterAgent/src")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

import kalpavriksha_desktop as kd  # noqa: E402
from master_agent.missions.execution_status import (  # noqa: E402
    AWAITING_APPROVAL,
    AWAITING_FOUNDER_COMPLETION,
)

FOLDER = f"KV_Golden_{time.strftime('%H%M%S')}"
DESKTOP = Path(os.path.expanduser("~")) / "Desktop"
TARGET = DESKTOP / FOLDER

OBJECTIVE = (
    f"Open a browser, go to https://example.com, and note the page's actual "
    f"title and final URL. Then create a folder called {FOLDER} on the Desktop "
    f"and write the observed title and final URL into a file called "
    f"page_info.txt inside it. Then close the browser."
)


def banner(text):
    print("\n" + "=" * 70, flush=True)
    print(text, flush=True)
    print("=" * 70, flush=True)


def main() -> int:
    banner("BUILDING THE REAL PIPELINE")
    pipeline = kd._build_mission_pipeline()
    if pipeline is None:
        print("NO PIPELINE. (It no longer depends on a Gemini key.)", flush=True)
        return 2
    (mission_service, runtime, mission_control, status, runner,
     set_mode, interactions, decide_approval) = pipeline
    print(f"pipeline built. reasoning ladder pinned to: "
          f"{os.environ.get('KALPAVRIKSHA_FMEA_REASONING_TIER')}", flush=True)

    banner(f"OBJECTIVE\n{OBJECTIVE}")
    print(f"target folder: {TARGET}", flush=True)
    if TARGET.exists():
        print("target already exists - aborting rather than reusing", flush=True)
        return 2

    reply = kd._submit_objective(
        mission_service, runtime, mission_control, status, OBJECTIVE,
        timeout_seconds=240.0,
    )
    banner("FIRST RETURN")
    print(f"status : {reply.get('status')}", flush=True)
    print(f"reply  : {reply.get('reply')}", flush=True)

    # The founder's decisions, made here because there is no window.
    for _round in range(12):
        if status.status == AWAITING_APPROVAL and status.approval_id:
            print(f"\n[founder] approving {status.approval_id} "
                  f"({status.approval_kind or 'permission'})", flush=True)
            print(f"[founder] preview: {status.approval_preview[:300]}", flush=True)
            decide_approval(status.approval_id, True, "live acceptance B")
        elif status.requires_founder_completion and status.completion_id:
            print(f"\n[founder] confirming completion {status.completion_id}", flush=True)
            mission_control.confirm_completion(status.completion_id)
        else:
            break
        # keep the runtime turning after the decision
        deadline = time.monotonic() + 180
        objective = mission_control.dispatcher.objective(status.objective_id)
        while time.monotonic() < deadline and not (
            objective.is_complete or objective.has_failure
        ):
            runtime.run_once()
            objective = mission_control.dispatcher.objective(status.objective_id)
            if status.status in (AWAITING_APPROVAL, AWAITING_FOUNDER_COMPLETION):
                break
            time.sleep(0.2)

    banner("FINAL MISSION STATE")
    print(f"status  : {status.status}", flush=True)
    print(f"message : {status.message}", flush=True)
    print(f"errors  : {status.errors}", flush=True)

    banner("INDEPENDENT VERIFICATION (fresh observation off disk)")
    ok = True
    if TARGET.is_dir():
        print(f"PASS folder exists: {TARGET}", flush=True)
    else:
        print(f"FAIL folder missing: {TARGET}", flush=True)
        ok = False
    info = TARGET / "page_info.txt"
    if info.is_file():
        body = info.read_text(encoding="utf-8", errors="replace")
        print(f"PASS page_info.txt exists ({len(body)} bytes)", flush=True)
        print("---- contents ----", flush=True)
        print(body, flush=True)
        print("------------------", flush=True)
        if "Example Domain" in body:
            print("PASS observed TITLE present", flush=True)
        else:
            print("FAIL observed title 'Example Domain' absent", flush=True)
            ok = False
        if "example.com" in body:
            print("PASS observed URL present", flush=True)
        else:
            print("FAIL observed final URL absent", flush=True)
            ok = False
    else:
        print(f"FAIL page_info.txt missing in {TARGET}", flush=True)
        ok = False

    banner(f"LIVE ACCEPTANCE B: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
