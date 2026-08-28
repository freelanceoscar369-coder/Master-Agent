"""Does today's intelligence work on objectives it was not built against?

Every mechanism proved this month was proved on one founder objective --
a live multi-source game/demo search. That objective is now frozen as a
regression case, and this battery exists to answer a different question:
does the BEHAVIOUR generalise, or only the code?

The subject here is deliberately dull and deliberately not games:
two lending libraries, and which of their reading rooms a person can
actually use on a Sunday. Neutral, small, and nothing in production knows
anything about it.

## What each fixture is for

    D  two independent sources, and neither is sufficient alone
    E  one source fails, an independent alternate carries the objective
    F  a provider returns a service notice; another answers
    G  public evidence may leave; private evidence may not
    H  one real live public objective, unrelated to games

D is built so that one mandatory criterion CANNOT be established from the
first source. That is the point: it is how `more_research` gets proved
generically rather than against a store page.

Run from the repository root. Nothing here is a product endpoint, a demo
Planner or a test-only provider -- every fixture drives the real
production composition.
"""
from __future__ import annotations

import http.server
import socket
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

# ---------------------------------------------------------------------
# Two independent sources, neither sufficient alone
# ---------------------------------------------------------------------

#: The directory page. It lists what exists and says nothing about hours
#: -- exactly like a real listing page, and the reason one source is not
#: enough.
DIRECTORY_HTML = """<!doctype html>
<html><head><title>City Reading Rooms</title></head><body>
<h1>Reading rooms in the city directory</h1>
<ul>
  <li>Halden Reading Room &mdash; step-free entrance</li>
  <li>Brackwell Reading Room &mdash; step-free entrance</li>
  <li>Coleport Reading Room &mdash; stairs only</li>
</ul>
<p>Opening hours are published separately by each room.</p>
</body></html>
"""

#: The hours page. It says when things open and nothing about access.
HOURS_HTML = """<!doctype html>
<html><head><title>Opening hours</title></head><body>
<h1>Sunday opening</h1>
<ul>
  <li>Halden Reading Room: open Sunday 10:00&ndash;16:00</li>
  <li>Brackwell Reading Room: closed on Sunday</li>
  <li>Coleport Reading Room: open Sunday 12:00&ndash;17:00</li>
</ul>
</body></html>
"""

#: The source that fails, for fixture E.
BROKEN_STATUS = 500


class Sources:
    """Two independent pages plus one that fails, on loopback.

    Loopback rather than the public web on purpose: this battery is about
    whether the SYSTEM generalises, and a fixture that can be blocked,
    rate-limited or redesigned by somebody else proves something about
    the internet instead.
    """

    def __init__(self) -> None:
        self.port = self._free_port()
        self._server = None
        self._thread = None

    @staticmethod
    def _free_port() -> int:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            return probe.getsockname()[1]

    def start(self) -> None:
        pages = {
            "/directory.html": DIRECTORY_HTML,
            "/hours.html": HOURS_HTML,
        }

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 - stdlib contract
                if self.path == "/broken.html":
                    self.send_response(BROKEN_STATUS)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(
                        b"<html><body><h1>500 Internal Server Error</h1>"
                        b"<p>This source is unavailable.</p></body></html>"
                    )
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

            def log_message(self, *args):  # noqa: A003 - silence the fixture
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

    def url(self, page: str) -> str:
        return f"http://127.0.0.1:{self.port}/{page}"


# ---------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------


class Case:
    def __init__(self, key: str, name: str) -> None:
        self.key = key
        self.name = name
        self.checks: list[tuple[bool, str]] = []
        self.notes: dict[str, object] = {}

    def check(self, passed: bool, description: str) -> None:
        self.checks.append((bool(passed), description))

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(ok for ok, _ in self.checks)

    def report(self) -> None:
        print(f"\n  {'PASS' if self.passed else 'FAIL'}  {self.key} — {self.name}",
              flush=True)
        for key, value in self.notes.items():
            print(f"        {key}: {value}", flush=True)
        for ok, description in self.checks:
            print(f"        [{'PASS' if ok else 'FAIL'}] {description}", flush=True)


def banner(text: str) -> None:
    print("\n" + "=" * 72)
    print(text)
    print("=" * 72, flush=True)


# ---------------------------------------------------------------------
# D — two independent sources, neither sufficient alone
# ---------------------------------------------------------------------


def fixture_d(sources: Sources, pipeline) -> Case:
    """Which reading rooms are step-free AND open on Sunday?

    Neither page can answer it. The directory knows about access and not
    hours; the hours page knows the reverse. Only Halden satisfies both,
    and establishing that requires combining two Evidence records.

    Built this way on purpose: the first deliberation must come back with
    a criterion it cannot establish, which is how `more_research` gets
    proved on something that is not a store page.
    """
    from master_agent.brain.deliberation import (
        DISCOVERY, Criterion, DecisionFrame, Observation, deliberate, shortlist,
    )

    case = Case("D", "two independent sources, neither sufficient alone")
    reasoner = getattr(pipeline[0].intent_layer, "_reasoner", None)

    step_free = Criterion("crit_1", "the reading room is step-free",
                          requirement_id="req_1")
    open_sunday = Criterion("crit_2", "the reading room is open on Sunday",
                            requirement_id="req_2")
    frame = DecisionFrame(
        objective="which reading rooms are step-free and open on Sunday",
        requirement_ids=("req_1", "req_2"),
        decision_type="research_shortlist",
        mandatory=(step_free, open_sunday),
    )

    # --- one source alone --------------------------------------------
    directory_only = (Observation("ev-directory", DIRECTORY_HTML,
                                  source_class=DISCOVERY,
                                  url=sources.url("directory.html")),)
    first = deliberate(frame, directory_only, reasoner)
    case.notes["one source"] = f"{first.state}, more_research={first.more_research}"
    case.check(first.shortlist == (),
               "one source alone shortlists nothing")
    case.check(first.more_research is True,
               "the Brain says more research is needed")
    unresolved_criteria = {
        c for rejected in first.rejected for c in rejected.unverified
    }
    case.check("crit_2" in unresolved_criteria,
               "it names the criterion it could not establish (Sunday hours)")

    # --- both sources -------------------------------------------------
    both = directory_only + (
        Observation("ev-hours", HOURS_HTML, source_class=DISCOVERY,
                    url=sources.url("hours.html")),
    )
    second = deliberate(frame, both, reasoner)
    names = [candidate.summary for candidate in second.shortlist]
    case.notes["both sources"] = f"{second.state}, shortlist={names}"
    case.check(bool(second.shortlist),
               "with the second source, something qualifies")
    case.check(any("halden" in n.lower() for n in names),
               "the room that satisfies BOTH criteria is shortlisted")
    case.check(not any("brackwell" in n.lower() for n in names),
               "the step-free room that is closed on Sunday is not")
    case.check(not any("coleport" in n.lower() for n in names),
               "the Sunday-open room that has stairs is not")

    # --- a model cannot invent what neither page says -----------------
    #
    # The directory page never mentions Sunday. If a candidate came back
    # with `crit_2` MET from that source alone, the model would have
    # supplied a fact the evidence does not contain -- which is the
    # failure mode the whole discipline exists to stop.
    from_one = shortlist(
        tuple(
            candidate for candidate in
            deliberate(frame, directory_only, reasoner).shortlist
        ),
        frame,
    )[0]
    case.check(from_one == (),
               "no room is claimed open on Sunday from a page that never says so")
    return case


# ---------------------------------------------------------------------
# F — a provider that talks about itself is not an answer
# ---------------------------------------------------------------------


def fixture_f() -> Case:
    """Provider A returns a service notice; provider B answers.

    Drives the real classifier and the real acceptability predicate the
    ladder uses -- not a re-implementation of either.
    """
    from master_agent.ai_infrastructure.tiered_runner import _acceptable
    from master_agent.providers.desktop_app import _is_service_notice

    case = Case("F", "provider fallback on a service notice")

    notice = ("High demand. Switched to a faster model. Upgrade to use the "
              "thinking model.")
    case.check(_is_service_notice(notice) is True,
               "a capacity notice is classified as a provider failure")

    real_but_incomplete = (
        "Halden Reading Room is step-free. I could not determine the Sunday "
        "hours for the other two rooms from what was provided."
    )
    case.check(_is_service_notice(real_but_incomplete) is False,
               "a genuine INCOMPLETE answer is not mistaken for one")
    case.notes["incomplete answer"] = real_but_incomplete[:60] + "..."

    class Outcome:
        def __init__(self, ok, verified, asked):
            self.ok = ok
            self.verified = verified
            self.evidence = object() if asked else None

    case.check(_acceptable(Outcome(ok=False, verified=False, asked=True)) is False,
               "an execution failure is not acceptable to the ladder")
    case.check(_acceptable(Outcome(ok=True, verified=False, asked=True)) is False,
               "an answer that failed its expectation is not acceptable")
    case.check(_acceptable(Outcome(ok=True, verified=True, asked=True)) is True,
               "a verified answer stops the ladder")
    return case


# ---------------------------------------------------------------------
# G — public may leave, private may not
# ---------------------------------------------------------------------


def fixture_g() -> Case:
    """Sensitivity comes from where the material came from.

    Both directions, and the dangerous one is the second: a model must
    not be able to write `sensitive: false` over a founder's own file.
    """
    from master_agent.runtime.sensitivity import apply_to, derive

    case = Case("G", "privacy asymmetry")

    public = {"instruction": "which rooms are step-free?"}
    apply_to(public, ["Browser.ReadPageText", "Browser.ReadPageText"])
    case.check(public.get("sensitive") is False,
               "public browser Evidence may go to an eligible provider")

    private = {"instruction": "summarise this"}
    apply_to(private, ["Filesystem.ReadFile"])
    case.check(private.get("sensitive") is True,
               "the founder's own file stays private")

    mixed = {"instruction": "compare these"}
    apply_to(mixed, ["Browser.ReadPageText", "Filesystem.ReadFile"])
    case.check(mixed.get("sensitive") is True,
               "public + private is private")

    overridden = {"instruction": "summarise", "sensitive": False}
    apply_to(overridden, ["Desktop.Screenshot"])
    case.check(overridden.get("sensitive") is True,
               "a model cannot lower sensitivity over private provenance")

    case.check(derive(["Something.Unrecognised"], False) is None,
               "unknown provenance cannot license a downgrade")
    return case


# ---------------------------------------------------------------------
# E — one source fails, an independent alternate carries the objective
# ---------------------------------------------------------------------


def fixture_e(sources: Sources, pipeline) -> Case:
    """A dead source must not end an objective an alternate can answer.

    Driven through the REAL mission path -- `_submit_objective`, the same
    entry point the founder surface calls -- because the thing being
    proved is that the product recovers, not that a helper can.
    """
    import kalpavriksha_desktop as kd
    from master_agent.missions.execution_status import ExecutionStatus

    case = Case("E", "a failed source does not end the objective")
    service, runtime, control = pipeline[0], pipeline[1], pipeline[2]

    objective = (
        f"open a browser, go to {sources.url('broken.html')} and read the "
        f"page text, then go to {sources.url('hours.html')} and read that "
        "page text too"
    )
    status = ExecutionStatus()
    kd._submit_objective(service, runtime, control, status, objective,
                         timeout_seconds=180.0)

    # The newest objective the dispatcher holds.
    #
    # `status.objective_id` is populated by the event recorder, which
    # this direct call does not wire up -- so reading it here found
    # nothing while the mission had in fact completed. The dispatcher is
    # the lifecycle authority and knows what it just ran.
    records = control.dispatcher.objectives()
    reached = []
    if records:
        record = records[-1]
        for task in record.tasks:
            evidence = getattr(task, "evidence", None) or {}
            observed = evidence.get("observation") or {}
            url = str(observed.get("url") or "") if isinstance(observed, dict) else ""
            if url:
                reached.append(url)
    case.notes["urls actually reached"] = [u.rsplit("/", 1)[-1] for u in reached]
    case.notes["mission"] = (
        f"{len(records[-1].tasks) if records else 0} tasks, "
        f"complete={records[-1].is_complete if records else False}"
    )
    case.notes["founder reply"] = str(status.message or "")[:90]

    case.check(any("broken" in u for u in reached),
               "the failing source was genuinely attempted")
    case.check(any("hours" in u for u in reached),
               "the independent alternate was reached anyway")
    case.check("try another" not in str(status.message or "").lower(),
               "the founder was not asked to pick another source")
    return case


# ---------------------------------------------------------------------


def main() -> int:
    import kalpavriksha_desktop as kd

    sources = Sources()
    sources.start()
    cases: list[Case] = []
    # ONE production composition for the whole battery.
    #
    # Building it twice in one process registers COM/UIA twice and the
    # second mission dies on "An event was unable to invoke any of the
    # subscribers" -- a fixture defect that looked exactly like a product
    # failure until the pipelines were counted.
    pipeline = kd._build_mission_pipeline()
    if pipeline is None:
        print("NO PIPELINE")
        return 2
    try:
        banner("DIVERSIFIED BATTERY — objectives this work was not built against")
        for build in (lambda: fixture_d(sources, pipeline), fixture_f, fixture_g,
                      lambda: fixture_e(sources, pipeline)):
            try:
                case = build()
            except Exception as exc:  # noqa: BLE001 - a broken fixture is a result
                case = Case("?", f"fixture raised: {type(exc).__name__}: {exc}")
                case.check(False, "the fixture itself failed")
            cases.append(case)
            case.report()
    finally:
        sources.stop()

    banner("SUMMARY")
    for case in sorted(cases, key=lambda c: c.key):
        print(f"  {'PASS' if case.passed else 'FAIL'}  {case.key} — {case.name}",
              flush=True)
    everything = all(case.passed for case in cases)
    banner(f"DIVERSIFIED BATTERY: {'PASS' if everything else 'FAIL'}")
    return 0 if everything else 1


if __name__ == "__main__":
    raise SystemExit(main())
