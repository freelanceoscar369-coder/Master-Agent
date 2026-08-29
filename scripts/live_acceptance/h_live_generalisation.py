"""H — the same intelligence, against reality nobody controlled.

Every other fixture in this battery runs against pages this repository
serves to itself. That is the right way to prove a *discipline*: the
content is known, so a wrong answer is unambiguous. It is the wrong way
to prove *generalisation*, because a loopback page is exactly as
cooperative as the fixture author needed it to be.

H runs one real public research objective. Not a game, not the reading
rooms, and not a site this work has already been made to succeed against.

WHAT THIS JUDGES, AND WHAT IT DELIBERATELY DOES NOT

It does not assert which city is the answer. Encoding the answer would
make this a test of how well a model reads Wikipedia on the day it ran,
and a fixture whose verdict flips with the weather proves nothing.

It judges the contract that must hold whatever the page says:

    something real was actually read
    a decision was recorded
    nothing is claimed without Evidence that exists
    nothing clears the shortlist without clearing every criterion
    the founder is spoken to in their own language
    the ending is either a decision or an honest "I could not establish it"

A truthful insufficiency is a PASS. A confident answer with nothing
behind it is the only real failure -- and an unreachable site is neither:
it is an external limitation, recorded as one.
"""
from __future__ import annotations

import os
import pathlib
import re
import sys

os.environ.setdefault("KALPAVRIKSHA_DISABLE_MIC", "1")
_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

from diversified_battery import Case, banner  # noqa: E402

#: The objective, as a founder would type it.
#:
#: Two factual criteria that no single sentence anywhere answers together,
#: on a subject with nothing to do with games or reading rooms. A starting
#: page is named the way a founder naturally names one; everything after
#: it is the system's own problem.
OBJECTIVE = (
    "Which of these three cities has a metro system that opened before "
    "1930 and is also its country's capital: Barcelona, Madrid, Hamburg? "
    "Start from https://en.wikipedia.org/wiki/List_of_metro_systems"
)

#: Words that mean the outside world said no, rather than the system
#: getting something wrong. Checked against the founder-facing sentence
#: and the recorded errors, never used to excuse a wrong answer.
_EXTERNAL = (
    "timed out", "timeout", "could not reach", "net::", "err_",
    "navigation failed", "connection", "dns", "403", "429", "503",
    "captcha", "unusual traffic", "access denied", "blocked",
)

#: Things a founder must never be shown.
_UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
_INTERNAL_IDS = re.compile(r"\b(crit|req|task|obj)_[0-9a-z]+\b", re.I)


def _external_limitation(text: str) -> bool:
    lowered = (text or "").lower()
    return any(mark in lowered for mark in _EXTERNAL)


def run(pipeline) -> tuple[Case, bool]:
    """Returns the case and whether the outside world was the reason."""
    import kalpavriksha_desktop as kd
    from master_agent.missions.execution_status import ExecutionStatus

    case = Case("H", "one live public objective, against reality nobody controlled")
    service, runtime, control = pipeline[0], pipeline[1], pipeline[2]

    before = len(control.dispatcher.objectives())
    status = ExecutionStatus()
    kd._submit_objective(service, runtime, control, status, OBJECTIVE,
                         timeout_seconds=300.0)

    records = control.dispatcher.objectives()[before:]
    reached: list[str] = []
    evidence_ids: set[str] = set()
    for record in records:
        for task in record.tasks:
            evidence = getattr(task, "evidence", None) or {}
            if not isinstance(evidence, dict):
                continue
            found = str(evidence.get("evidence_id") or "").strip()
            if found:
                evidence_ids.add(found)
            observed = evidence.get("observation") or {}
            url = str(observed.get("url") or "") if isinstance(observed, dict) else ""
            if url:
                reached.append(url)

    decided = getattr(status, "deliberation", None) or {}
    reply = str(status.message or "")
    errors = "; ".join(getattr(status, "errors", None) or [])

    public = [u for u in reached if u.startswith("http") and "127.0.0.1" not in u]
    case.notes["missions run"] = len(records)
    case.notes["public pages read"] = sorted({u.split("?")[0] for u in public})[:6]
    case.notes["evidence records"] = len(evidence_ids)
    case.notes["decision"] = decided.get("state")
    case.notes["more research wanted"] = decided.get("more_research")
    case.notes["shortlist"] = [c.get("summary") for c in decided.get("shortlist") or ()]
    case.notes["rejected"] = [
        f"{r.get('summary')} ({r.get('reason')})"
        for r in (decided.get("rejected") or ())
    ][:4]
    case.notes["founder reply"] = reply[:200]
    if errors:
        case.notes["errors"] = errors[:200]

    outside = bool(public) is False and _external_limitation(f"{reply} {errors}")

    # --- 1. something real was actually read --------------------------
    case.check(bool(public), "a real public page was actually read")

    # --- 2. a decision was recorded -----------------------------------
    case.check(bool(decided), "the product recorded what it decided")

    # --- 3. nothing is claimed without Evidence that exists -----------
    #
    # The failure this exists to catch: a model naming a city it knows
    # the answer for, from its own memory, with no observation behind
    # it. On a subject this famous that is the likeliest way to be
    # confidently wrong.
    unsupported = [
        c.get("summary") for c in decided.get("shortlist") or ()
        if not (set(c.get("supporting") or ()) & evidence_ids)
    ]
    case.notes["unsupported claims"] = unsupported
    case.check(not unsupported,
               "every shortlisted answer rests on Evidence this mission actually holds")

    # --- 4. the shortlist means what it says --------------------------
    criteria = list((decided.get("criteria") or {}).keys())
    half_met = [
        c.get("summary") for c in decided.get("shortlist") or ()
        if criteria and not all(
            (c.get("criteria") or {}).get(cid) == "met" for cid in criteria)
    ]
    case.notes["shortlisted without clearing everything"] = half_met
    case.check(not half_met,
               "nothing reaches the shortlist without clearing every criterion")

    # --- 5. the founder is spoken to in their own language ------------
    case.check(not _UUID.search(reply), "no identifiers in the founder's reply")
    case.check(not _INTERNAL_IDS.search(reply),
               "no internal criterion or task ids in the founder's reply")
    case.check("{" not in reply and "```" not in reply,
               "no raw plan or JSON in the founder's reply")

    # --- 6. the ending is honest --------------------------------------
    #
    # Both endings are acceptable. What is not acceptable is claiming the
    # work finished while holding nothing, which is the exact shape of
    # the failure this whole session has been about.
    claims_done = "finished" in reply.lower() or "here is" in reply.lower()
    case.check(
        bool(decided.get("shortlist")) or not claims_done,
        "nothing is presented as finished on an empty result",
    )
    case.check(bool(reply.strip()), "the founder was told something")
    return case, outside


def main() -> int:
    import kalpavriksha_desktop as kd

    banner("H — LIVE GENERALISATION")
    print(f"objective: {OBJECTIVE}\n", flush=True)

    pipeline = kd._build_mission_pipeline()
    if pipeline is None:
        print("NO PIPELINE")
        return 2

    try:
        case, outside = run(pipeline)
    except Exception as exc:  # noqa: BLE001 - a broken fixture is a result
        import traceback
        case = Case("H", f"fixture raised: {type(exc).__name__}: {exc}")
        case.notes["traceback"] = "\n" + "".join(traceback.format_exception(exc))
        case.check(False, "the fixture itself failed")
        outside = False
    case.report()

    if case.passed:
        verdict = "H LIVE GENERALISATION: PASS"
    elif outside:
        verdict = ("H LIVE GENERALISATION: TRUTHFUL EXTERNAL FAILURE "
                   "(the site could not be reached; the system said so)")
    else:
        verdict = "H LIVE GENERALISATION: FAIL"
    banner(verdict)
    return 0 if case.passed else (2 if outside else 1)


if __name__ == "__main__":
    raise SystemExit(main())
