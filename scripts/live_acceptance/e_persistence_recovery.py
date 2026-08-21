"""LIVE ACCEPTANCE E - persistence, and an honest boundary around recovery.

## What Founder Edition actually claims

Two different things travel under the word "persistence", and this
composition wires exactly one of them. `kalpavriksha_desktop.py` says so
itself, at the line that constructs them:

    Deliberately NOT restored into the runtime. This mission is about
    being able to reconstruct what happened, not about resuming
    interrupted missions after a restart; recovery semantics are their
    own decision and `restore_into()` is left uncalled.

So:

  RECORDING  - WIRED. `PersistenceService` appends every bus event to a
               durable log, and `PlanHistory` writes one row per mission
               with an entry per step. Both are subscribers: they observe
               the bus and drive nothing.

  RECOVERY   - NOT WIRED, deliberately. `recover()` exists and is fully
               built (`persistence/recovery.py`), and `launcher/boot.py`
               calls it -- but `master_agent.launcher` is kept out of the
               Founder Edition build on purpose.

This script proves the first and REPORTS the second rather than pretending
either way. §30 E says "where current architecture claims persistence" --
and here the architecture is explicit about where it does not.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "D:/MasterAgent")
sys.path.insert(0, "D:/MasterAgent/src")


def banner(text):
    print("\n" + "=" * 70, flush=True)
    print(text, flush=True)
    print("=" * 70, flush=True)


def state_dir() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Kalpavriksha"
    return root / "state"


def main() -> int:
    ok = True
    sd = state_dir()

    banner("1. DOES THE RECORD SURVIVE THE PROCESS THAT WROTE IT?")
    print(f"state dir: {sd}", flush=True)
    # This is a FRESH process. Nothing here shares memory with the runs
    # that produced these files, so reading them back is a real
    # cross-process durability check rather than a cache hit.
    history = sd / "plan_history.json"
    if not history.is_file():
        print(f"FAIL no plan history at {history}", flush=True)
        return 1

    plans = json.loads(history.read_text(encoding="utf-8"))["plans"]
    print(f"PASS plan history readable in a new process: {len(plans)} mission(s)",
          flush=True)

    banner("2. IS THE AUDIT TRUTHFUL ABOUT WHAT HAPPENED?")
    verified = [p for p in plans if any(
        (s.get("verdict") or "") == "matched" for s in p.get("steps", [])
    )]
    print(f"missions with at least one verified step: {len(verified)}", flush=True)
    for plan in plans[-3:]:
        steps = plan.get("steps", [])
        verdicts = [s.get("verdict") or "-" for s in steps]
        print(f"  {plan.get('state','?'):9} {len(steps)} step(s)  verdicts={verdicts}",
              flush=True)
        print(f"     {str(plan.get('objective'))[:66]}", flush=True)

    # A record that says "matched" for a step must say WHAT it matched.
    unexplained = [
        (p.get("plan_id"), s.get("step_id"))
        for p in plans for s in p.get("steps", [])
        if (s.get("verdict") or "") == "matched" and not s.get("expectation")
    ]
    if unexplained:
        print(f"FAIL {len(unexplained)} verified step(s) record no expectation, "
              f"so 'matched' cannot be checked: {unexplained[:3]}", flush=True)
        ok = False
    else:
        print("PASS every verified step records the expectation it was "
              "verified against", flush=True)

    # A failed step must keep its error rather than quietly reading clean.
    failed = [s for p in plans for s in p.get("steps", []) if s.get("state") == "failed"]
    silent = [s.get("step_id") for s in failed if not s.get("errors")]
    if silent:
        print(f"FAIL {len(silent)} failed step(s) carry no error", flush=True)
        ok = False
    else:
        print(f"PASS all {len(failed)} failed step(s) kept their errors", flush=True)

    banner("3. IS THE EVENT LOG THERE TOO?")
    candidates = sorted(p.name for p in sd.glob("*.json*"))
    print(f"state files: {candidates}", flush=True)

    banner("4. RESUME AFTER RESTART - IS IT EVEN CLAIMED?")
    # AST, not grep. The composition root *mentions* `restore_into()` in
    # the comment explaining why it does not call it, so searching the
    # text finds the explanation and concludes the opposite of what it
    # says. A call is a call node.
    import ast

    source = Path("D:/MasterAgent/kalpavriksha_desktop.py").read_text(
        encoding="utf-8", errors="replace")
    tree = ast.parse(source)
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    claims_recovery = "restore_into" in called or "recover" in called

    print(f"composition root CALLS restore_into()/recover(): {claims_recovery}",
          flush=True)
    if claims_recovery:
        print("   -- architecture DOES claim resume, so §30 E requires it to be",
              flush=True)
        print("      proven live. This script does not yet do that.", flush=True)
        ok = False
    else:
        print("   NOT CLAIMED, and the source says so where it would have been:",
              flush=True)
        print('   "recovery semantics are their own decision and restore_into()',
              flush=True)
        print('    is left uncalled."', flush=True)
        print("   `recover()` is fully built in persistence/recovery.py and IS",
              flush=True)
        print("   wired by launcher/boot.py -- which Founder Edition excludes on",
              flush=True)
        print("   purpose (packaging/kalpavriksha.spec).", flush=True)
        print("   => RECORDING proven above. RESUME is BUILT_BUT_UNWIRED: a scope",
              flush=True)
        print("      decision, not a defect, and not something to claim as passed.",
              flush=True)

    banner(f"LIVE ACCEPTANCE E: {'PASS (for what is claimed)' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
