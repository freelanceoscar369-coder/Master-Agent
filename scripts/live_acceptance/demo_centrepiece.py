"""The demo centrepiece — one objective, the whole loop.

The impressive proof is not a search. It is a mission that decides it
does not know enough, works out what is missing, goes and gets it from
somewhere nobody named, loses a route on the way, carries on without
asking, and then tells the founder only what it can actually stand
behind.

    founder gives an objective naming ONE page
    -> read it
    -> Evidence
    -> a criterion nobody has established
    -> more research
    -> follow a link the founder never mentioned
    -> that route is dead
    -> no founder interruption
    -> the other link
    -> Evidence
    -> deliberate
    -> reject what does not conform, say why
    -> a verified answer

Controlled reality, deliberately. A demo must not depend on another
company's anti-bot policy -- the live Google mission that redirected
Playwright to `/sorry/` is recorded as a truthful failure in the evidence
pack and is exactly why this one is hermetic. What is being demonstrated
is the SYSTEM; the pages are a stage, not the act.

Nothing about repair workshops exists in production. The objective is
typed in fresh, the pages are served fresh, and the only thing that knows
what to do with either is the product.
"""
from __future__ import annotations

import http.server
import os
import pathlib
import socket
import socketserver
import sys
import threading
import time

os.environ.setdefault("KALPAVRIKSHA_DISABLE_MIC", "1")
_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "scripts" / "live_acceptance"))

from diversified_battery import Case, banner  # noqa: E402

#: The page the founder names. It knows what each workshop accepts and
#: says nothing whatever about Saturdays -- and it offers two ways
#: onward, one of which is dead.
DIRECTORY_HTML = """<!doctype html>
<html><head><title>Community repair workshops</title></head><body>
<h1>Community repair workshops in the city</h1>
<ul>
  <li>Ashcombe Repair Workshop &mdash; accepts laptops and phones</li>
  <li>Brindle Repair Workshop &mdash; accepts laptops and bicycles</li>
  <li>Calder Repair Workshop &mdash; bicycles only, no electronics</li>
</ul>
<p>Weekend opening is published separately:
<a href="/weekend-archive.html">weekend opening (archive)</a> or
<a href="/weekend.html">weekend opening hours</a>.</p>
</body></html>
"""

#: The page nobody named. Knows the hours and nothing about laptops.
WEEKEND_HTML = """<!doctype html>
<html><head><title>Weekend opening</title></head><body>
<h1>Weekend opening hours</h1>
<ul>
  <li>Ashcombe Repair Workshop &mdash; open Saturday 10:00&ndash;16:00</li>
  <li>Brindle Repair Workshop &mdash; closed at weekends</li>
  <li>Calder Repair Workshop &mdash; open Saturday 09:00&ndash;13:00</li>
</ul>
</body></html>
"""

#: Only Ashcombe accepts laptops AND opens on Saturday. Brindle takes
#: laptops and is shut; Calder is open and takes no electronics. Neither
#: page can answer the question on its own, and the archive route is
#: dead.

BROKEN_STATUS = 503


class Stage:
    def __init__(self) -> None:
        self.port = self._free_port()
        self._server = None
        self._thread = None

    @staticmethod
    def _free_port() -> int:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            return probe.getsockname()[1]

    def url(self, name: str) -> str:
        return f"http://127.0.0.1:{self.port}/{name}"

    def start(self) -> None:
        pages = {"/directory.html": DIRECTORY_HTML, "/weekend.html": WEEKEND_HTML}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 - stdlib contract
                if self.path == "/weekend-archive.html":
                    self.send_response(BROKEN_STATUS)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(
                        b"<html><body><h1>503 Service Unavailable</h1>"
                        b"<p>The archive is offline.</p></body></html>")
                    return
                body = pages.get(self.path)
                if body is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                encoded = body.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, *args):  # noqa: A003
                return

        class Server(http.server.HTTPServer):
            allow_reuse_address = True

        self._server = Server(("127.0.0.1", self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()


def run(stage: Stage, pipeline) -> Case:
    import kalpavriksha_desktop as kd
    from master_agent.missions.execution_status import ExecutionStatus

    case = Case("CENTREPIECE", "one objective, the whole loop")
    service, runtime, control = pipeline[0], pipeline[1], pipeline[2]

    before = len(control.dispatcher.objectives())
    objective = (
        "Which community repair workshops accept laptops and are also open "
        f"on Saturday? Start from {stage.url('directory.html')}"
    )
    print(f"\n  objective: {objective}\n", flush=True)

    started = time.monotonic()
    status = ExecutionStatus()
    kd._submit_objective(service, runtime, control, status, objective,
                         timeout_seconds=300.0)
    elapsed = time.monotonic() - started

    records = control.dispatcher.objectives()[before:]
    reached: list[str] = []
    for record in records:
        for task in record.tasks:
            evidence = getattr(task, "evidence", None) or {}
            observed = evidence.get("observation") if isinstance(evidence, dict) else None
            url = str((observed or {}).get("url") or "") if isinstance(observed, dict) else ""
            if url:
                reached.append(url.rsplit("/", 1)[-1])
    attempted = " ".join(
        str(getattr(task, "payload", None) or {})
        for record in records for task in record.tasks
    )

    decided = getattr(status, "deliberation", None) or {}
    reply = str(status.message or "")
    names = [c.get("summary") or "" for c in decided.get("shortlist") or ()]

    case.notes["seconds"] = f"{elapsed:.0f}"
    case.notes["missions run"] = len(records)
    case.notes["pages reached"] = sorted(set(reached))
    case.notes["decision"] = decided.get("state")
    case.notes["shortlist"] = names
    case.notes["rejected"] = [
        f"{r.get('summary')} ({r.get('reason')})" for r in decided.get("rejected") or ()
    ]
    case.notes["founder reply"] = reply[:300]

    # 1 - the page the founder named
    case.check("directory.html" in reached, "the source the founder named was read")

    # 2 - a page the founder never named, reached by the system's own
    #     decision that it needed evidence it did not have
    case.check("weekend.html" in reached,
               "the source holding the missing evidence was reached, and the "
               "founder never named it")

    # 3 - the dead route was genuinely tried, and cost nothing
    case.check("weekend-archive.html" in attempted or "archive" in attempted,
               "the dead route was genuinely attempted")
    case.check("try another" not in reply.lower() and "which source" not in reply.lower(),
               "the founder was not asked to pick another source")

    # 4 - the answer means what it says
    case.check(bool(names), "something was shortlisted")
    for name in names:
        case.check("brindle" not in name.lower(),
                   "the workshop that takes laptops and shuts at weekends is not offered")
        case.check("calder" not in name.lower(),
                   "the workshop that opens Saturday and takes no electronics is not offered")

    # 5 - the founder is spoken to, not debugged at
    import re
    case.check(not re.search(r"\b[0-9a-f]{8}-[0-9a-f]{4}-", reply),
               "no identifiers in the reply")
    case.check(not re.search(r"\b(crit|req|step|task)_[0-9a-z]+\b", reply),
               "no internal ids in the reply")
    case.check("{" not in reply, "no raw plan in the reply")
    return case


def main() -> int:
    import kalpavriksha_desktop as kd

    banner("DEMO CENTREPIECE — one objective, the whole loop")
    stage = Stage()
    stage.start()
    pipeline = kd._build_mission_pipeline()
    if pipeline is None:
        print("NO PIPELINE")
        return 2
    try:
        case = run(stage, pipeline)
    except Exception as exc:  # noqa: BLE001
        import traceback
        case = Case("CENTREPIECE", f"raised: {type(exc).__name__}: {exc}")
        case.notes["traceback"] = "\n" + "".join(traceback.format_exception(exc))
        case.check(False, "the fixture itself failed")
    finally:
        stage.stop()
    case.report()
    banner(f"DEMO CENTREPIECE: {'PASS' if case.passed else 'FAIL'}")
    return 0 if case.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
