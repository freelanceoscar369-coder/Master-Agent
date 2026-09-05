"""Diagnostic: what does the Planner actually get back?

Understanding now passes and the mission reaches the Planner, which
refuses with "`steps` is missing or is not a list". That says the shape
was wrong; it does not say what arrived. This prints the raw reply for
the real objective, through the real composition, changing no product
behaviour.

Wraps the tiered runner the Planner calls, observes, and calls through.

    python _planner_reply_dump.py
"""
from __future__ import annotations

import logging
import os
import sys

logging.basicConfig(level=logging.WARNING, format="[%(levelname)s] %(message)s")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, "D:/MasterAgent")
sys.path.insert(0, "D:/MasterAgent/src")

OBJECTIVE = (
    "Ensure a folder Kalpavriksha_Usability_Simple exists on my Desktop. "
    "Inside it ensure result.txt contains exactly: Kalpavriksha simple "
    "usability test passed. Verify folder/file/content, then report."
)


def ascii_of(text):
    return (text or "").encode("ascii", "replace").decode("ascii")


def main() -> int:
    import kalpavriksha_desktop as fe

    pipeline = fe._build_mission_pipeline()
    if pipeline is None:
        print("could not assemble the pipeline")
        return 2
    mission_service, _runtime, _mc, _status, runner, *_rest = pipeline

    original = type(runner).run
    calls = {"n": 0}

    def traced(self, prompt, request=None, expected=None, **kw):
        calls["n"] += 1
        n = calls["n"]
        requester = getattr(request, "requester", None) or getattr(
            getattr(request, "context", None), "requester", None
        )
        outcome = original(self, prompt, request, expected=expected, **kw) \
            if expected is not None else original(self, prompt, request, **kw)
        text = getattr(outcome, "text", "") or ""
        ok = getattr(outcome, "ok", None)
        print(f"\n===== runner call {n} =====", flush=True)
        print(f"  requester   : {requester}", flush=True)
        print(f"  prompt chars: {len(prompt)}", flush=True)
        print(f"  ok={ok}  provider={getattr(outcome, 'provider_id', None)}"
              f"  reply chars={len(text)}", flush=True)
        # Only the planner's own replies are worth printing whole.
        if len(text) < 4000:
            print("  ---- reply ----", flush=True)
            print("  " + ascii_of(text).replace("\n", "\n  ")[:3500], flush=True)
        else:
            print("  ---- reply head ----", flush=True)
            print("  " + ascii_of(text[:1500]).replace("\n", "\n  "), flush=True)
            print("  ---- reply tail ----", flush=True)
            print("  " + ascii_of(text[-600:]).replace("\n", "\n  "), flush=True)
        import json
        try:
            document = json.loads(text.strip())
            print(f"  json: OK, top-level keys = {list(document)[:8]}", flush=True)
            if isinstance(document, dict) and "steps" in document:
                print(f"  steps: {type(document['steps']).__name__}, "
                      f"len={len(document['steps']) if isinstance(document['steps'], list) else 'n/a'}",
                      flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  json: FAILED -- {exc}", flush=True)
        return outcome

    type(runner).run = traced
    try:
        outcome = mission_service.start(OBJECTIVE)
        print("\n===== OUTCOME =====")
        print("  accepted:", getattr(outcome, "accepted", None))
        refusal = getattr(outcome, "refusal", None)
        if refusal is not None:
            print("  code   :", getattr(refusal, "code", None))
            print("  reason :", ascii_of(getattr(refusal, "reason", "")))
            print("  detail :", ascii_of(getattr(refusal, "detail", "")))
        print("  runner calls:", calls["n"])
    finally:
        type(runner).run = original
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
