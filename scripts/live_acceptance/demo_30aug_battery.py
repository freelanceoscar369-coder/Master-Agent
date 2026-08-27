"""LIVE ACCEPTANCE — the 30 August demo battery, all three golden paths.

Run it, read it, and it tells you whether the demo is green:

    python scripts/live_acceptance/demo_30aug_battery.py

Like every runner beside it this is **not a pytest test** and must never
be collected as one. It drives the real Founder Edition pipeline: real
files on the founder's Desktop, a real visible browser, real provider
quota for the one path that genuinely needs thinking.

## What each path proves, and why they are separate

1. **LOCAL** — fully dictated filesystem work. Zero AI planning calls.
2. **ORDINARY BROWSER** — a dictated browser workflow against a loopback
   fixture, through Playwright, ending in a fresh observation of the
   element the founder asked about. Zero AI planning calls.
3. **REASONING + FILE** — the only path where a model is used at all, and
   it is used *inside* `Reasoning.Transform`, never to plan. The written
   file must equal the verified answer, bound from canonical Evidence.

Path 2 deliberately uses a **loopback fixture, not a public website**. A
demo must not depend on another company's anti-bot policy: the live
Google mission that redirected Playwright to `/sorry/` is recorded as a
truthful failure in the evidence pack, and it is the reason this proof is
hermetic.

Path 2 is also, deliberately, Playwright. That is the ordinary Browser
lane and it stays that way. The Trusted Web lane -- a real authenticated
Chrome or Comet -- is a different proof for a different purpose and is
not exercised here.

## How "AI planning calls" is counted

Not by instrumentation. The Broker's own decision ledger records a
`requester` for every selection it makes, so a planning call is an entry
whose requester is the Planner. Counting the ledger means the number
comes from the same record an auditor would read, and a harness cannot
flatter itself by counting something else.

## Paths

Resolved from this file, never hardcoded. An earlier runner pinned
`D:/MasterAgent`, which silently imported the MAIN checkout while running
from a worktree -- the same class of mistake as trusting a working
directory for a milestone.
"""
from __future__ import annotations

import contextlib
import hashlib
import http.server
import json
import os
import socket
import socketserver
import sys
import threading
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

# A harness never listens to the room.
os.environ.setdefault("KALPAVRIKSHA_DISABLE_MIC", "1")
# NO reasoning-tier pin. An operational acceptance must exercise the
# PRODUCTION ladder; pinning one rung reports FAIL for a product that
# would have carried on perfectly well in a founder's hands.

import kalpavriksha_desktop as kd  # noqa: E402
from master_agent.missions.execution_status import (  # noqa: E402
    AWAITING_APPROVAL,
    AWAITING_FOUNDER_COMPLETION,
)

DESKTOP = Path(os.path.expanduser("~")) / "Desktop"
STAMP = time.strftime("%H%M%S")


# =====================================================================
# The loopback fixture
# =====================================================================

FIXTURE_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Kalpavriksha Acceptance</title></head>
<body style="font-family: system-ui, sans-serif; padding: 2rem">
  <h1>Acceptance fixture</h1>
  <input id="acceptance-box" style="font-size:1.2rem;padding:.4rem" />
  <button id="apply" style="font-size:1.2rem;padding:.4rem 1rem">Apply</button>
  <p>State: <span id="state" style="font-weight:700">pending</span></p>
  <script>
    document.getElementById('apply').addEventListener('click', function () {
      var typed = document.getElementById('acceptance-box').value;
      var next = (typed === 'acceptance') ? 'accepted' : 'rejected';
      document.getElementById('state').textContent = next;
      fetch('/state', {method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({state: next, typed: typed})});
    });
  </script>
</body></html>
"""


class _Fixture:
    """A page, and a server that remembers what happened to it.

    The server holding the state is the point. If the outcome lived only
    in the DOM, the only way to read it would be through the very browser
    session the mission is asked to close -- reading the result through
    the thing under test. `GET /state` answers after every browser has
    exited.
    """

    def __init__(self) -> None:
        self.record = {"state": "pending", "typed": None, "applied": 0}
        self._lock = threading.Lock()
        self.port = self._free_port()
        fixture = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def _send(self, code, body, content_type):
                payload = body.encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self):
                if self.path.startswith("/state"):
                    with fixture._lock:
                        self._send(200, json.dumps(fixture.record), "application/json")
                elif self.path in ("/", "/acceptance.html"):
                    self._send(200, FIXTURE_PAGE, "text/html; charset=utf-8")
                else:
                    self._send(404, "not found", "text/plain")

            def do_POST(self):
                if not self.path.startswith("/state"):
                    self._send(404, "not found", "text/plain")
                    return
                length = int(self.headers.get("Content-Length") or 0)
                document = json.loads(self.rfile.read(length) or b"{}")
                with fixture._lock:
                    fixture.record["state"] = str(document.get("state") or "")
                    fixture.record["typed"] = document.get("typed")
                    fixture.record["applied"] += 1
                    self._send(200, json.dumps(fixture.record), "application/json")

            def log_message(self, fmt, *args):
                pass

        class Server(socketserver.ThreadingTCPServer):
            allow_reuse_address = True
            daemon_threads = True

        # Loopback only. An acceptance fixture is not a service.
        self._server = Server(("127.0.0.1", self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @staticmethod
    def _free_port() -> int:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            return probe.getsockname()[1]

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/acceptance.html"

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    def observed_state(self) -> dict:
        """Read the outcome from the server, not from any browser."""
        with urllib.request.urlopen(
            f"http://127.0.0.1:{self.port}/state", timeout=5
        ) as response:
            return json.loads(response.read())

    @property
    def page_sha256(self) -> str:
        return hashlib.sha256(FIXTURE_PAGE.encode("utf-8")).hexdigest()


# =====================================================================
# Running one golden path
# =====================================================================


def banner(text: str) -> None:
    print("\n" + "=" * 72, flush=True)
    print(text, flush=True)
    print("=" * 72, flush=True)


def _ledger_rows(runner) -> list:
    executor = getattr(runner, "_executor", None)
    ledger = getattr(executor, "_ledger", None)
    if ledger is None:
        return []
    try:
        return list(ledger.entries())
    except Exception:  # noqa: BLE001 -- the ledger is evidence, not control flow
        return []


def _requester_of(entry) -> str:
    record = getattr(entry, "record", None)
    decision = getattr(record, "decision", None)
    task = getattr(decision, "task", None)
    return str(getattr(task, "requester", "") or "")


class Result:
    def __init__(self, name: str) -> None:
        self.name = name
        self.checks: list[tuple[bool, str]] = []
        self.facts: dict[str, object] = {}
        self.seconds = 0.0

    def check(self, passed: bool, description: str) -> bool:
        self.checks.append((bool(passed), description))
        return bool(passed)

    def fact(self, key: str, value: object) -> None:
        self.facts[key] = value

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(ok for ok, _ in self.checks)

    @property
    def first_broken(self) -> str:
        for ok, description in self.checks:
            if not ok:
                return description
        return ""

    def report(self) -> None:
        banner(f"{self.name}: {'PASS' if self.passed else 'FAIL'}")
        for key, value in self.facts.items():
            print(f"  {key:<24}: {value}", flush=True)
        print(f"  {'duration':<24}: {self.seconds:.1f}s", flush=True)
        for ok, description in self.checks:
            print(f"  [{'PASS' if ok else 'FAIL'}] {description}", flush=True)
        if not self.passed:
            print(f"  FIRST BROKEN BOUNDARY: {self.first_broken}", flush=True)


def run_objective(pipeline, objective: str, result: Result, timeout: float = 300.0):
    """One founder objective through the real surface entry point."""
    (mission_service, runtime, mission_control, status, runner,
     _set_mode, _interactions, decide_approval) = pipeline

    before = len(_ledger_rows(runner))
    started = time.monotonic()
    reply = kd._submit_objective(
        mission_service, runtime, mission_control, status, objective,
        timeout_seconds=timeout,
    )

    # The founder's decisions, made here because there is no window.
    #
    # Each decision is made ONCE. `status` is not re-derived after a
    # confirmation, so re-reading the same id and acting on it again is
    # how this loop span for twelve rounds of three minutes on a mission
    # that had already finished -- the harness hanging, not the product.
    decided: set[str] = set()
    for _round in range(12):
        if (status.status == AWAITING_APPROVAL and status.approval_id
                and status.approval_id not in decided):
            decided.add(status.approval_id)
            print(f"  [founder] approving {status.approval_id}", flush=True)
            decide_approval(status.approval_id, True, "demo battery")
        elif (status.requires_founder_completion and status.completion_id
                and status.completion_id not in decided):
            decided.add(status.completion_id)
            print(f"  [founder] confirming completion {status.completion_id}", flush=True)
            mission_control.confirm_completion(status.completion_id)
        else:
            break
        deadline = time.monotonic() + 90
        objective_record = mission_control.dispatcher.objective(status.objective_id)
        while time.monotonic() < deadline and not (
            objective_record.is_complete or objective_record.has_failure
        ):
            runtime.run_once()
            objective_record = mission_control.dispatcher.objective(status.objective_id)
            if status.status in (AWAITING_APPROVAL, AWAITING_FOUNDER_COMPLETION):
                break
            time.sleep(0.2)

    result.seconds = time.monotonic() - started
    new_rows = _ledger_rows(runner)[before:]

    result.fact("mission id", status.objective_id)
    result.fact("status", status.status)
    result.fact("founder result", (status.message or "").replace("\n", " ")[:160])
    planning = [row for row in new_rows if _requester_of(row) == "planner"]
    result.fact("AI planning calls", len(planning))
    other = [row for row in new_rows if _requester_of(row) != "planner"]
    if other:
        result.fact("reasoning provider(s)", [
            getattr(row, "provider_id", None) for row in other
        ])
    return reply, status, new_rows


def capabilities_run(mission_control, objective_id) -> list[str]:
    record = mission_control.dispatcher.objective(objective_id)
    return [task.capability for task in record.tasks]


def evidence_of(mission_control, objective_id) -> list[tuple[str, str]]:
    record = mission_control.dispatcher.objective(objective_id)
    return [
        (task.capability, (task.evidence or {}).get("verdict") or "none")
        for task in record.tasks
    ]


# =====================================================================
# Golden path 1 — LOCAL
# =====================================================================


def golden_local(pipeline) -> Result:
    result = Result("GOLDEN PATH 1 — LOCAL")
    folder = f"KalpavrikshaDemoProof_{STAMP}"
    target = DESKTOP / folder
    proof = target / "proof.txt"
    body = "Kalpavriksha demo ready"

    objective = (
        f"Create a folder called {folder} on the Desktop. Then write it into "
        f"proof.txt inside that folder. The text should be: {body}"
    )
    result.fact("objective", objective)
    banner(result.name)
    print(f"  {objective}", flush=True)

    _reply, status, _rows = run_objective(pipeline, objective, result)
    mission_control = pipeline[2]

    result.check(status.objective_id is not None, "a mission was created")
    if status.objective_id:
        result.fact("capabilities", capabilities_run(mission_control, status.objective_id))
        result.fact("evidence", evidence_of(mission_control, status.objective_id))
    result.check(
        result.facts.get("AI planning calls") == 0,
        "planned deterministically — no provider was asked how to create a folder",
    )
    # Independent verification: read the disk, not the report.
    result.check(target.is_dir(), f"folder exists on disk: {target}")
    result.check(proof.is_file(), f"file exists on disk: {proof}")
    if proof.is_file():
        found = proof.read_text(encoding="utf-8", errors="replace").strip()
        result.fact("file contents", found)
        result.check(found == body, f"contents are exactly {body!r}")
    return result


# =====================================================================
# Golden path 2 — ORDINARY BROWSER (Playwright, deliberately)
# =====================================================================


def golden_browser(pipeline, fixture: _Fixture) -> Result:
    result = Result("GOLDEN PATH 2 — ORDINARY BROWSER (Playwright)")
    objective = (
        f"Open a browser session and navigate to {fixture.url}. "
        f"Type the text acceptance into the element matching #acceptance-box, "
        f"click the element matching #apply, observe the page and tell me the "
        f"current text shown by #state, then close the browser session."
    )
    result.fact("objective", objective)
    result.fact("fixture sha256", fixture.page_sha256)
    result.fact("browser environment", "Playwright — the ordinary Browser lane")
    banner(result.name)
    print(f"  {objective}", flush=True)

    baseline = fixture.observed_state()
    result.check(baseline["state"] == "pending", "fixture starts at 'pending'")

    _reply, status, _rows = run_objective(pipeline, objective, result)
    mission_control = pipeline[2]

    result.check(status.objective_id is not None, "a mission was created")
    if status.objective_id:
        capabilities = capabilities_run(mission_control, status.objective_id)
        result.fact("capabilities", capabilities)
        result.fact("evidence", evidence_of(mission_control, status.objective_id))
        result.check(
            capabilities == [
                "Browser.OpenBrowserSession", "Browser.Navigate", "Browser.TypeText",
                "Browser.Click", "Browser.ObserveBrowser", "Browser.CloseBrowserSession",
            ],
            "the six dictated steps, in the founder's order",
        )
        record = mission_control.dispatcher.objective(status.objective_id)
        observation = next(
            ((task.evidence or {}).get("observation") for task in record.tasks
             if task.capability == "Browser.ObserveBrowser"),
            None,
        )
        result.check(
            isinstance(observation, dict),
            "the final observation produced canonical Evidence",
        )
        if isinstance(observation, dict):
            elements = observation.get("elements") or [{}]
            result.fact("observed #state", elements[0].get("text"))
            result.check(
                elements[0].get("selector") == "#state",
                "the element observed is the one the founder named",
            )
            result.check(
                elements[0].get("text") == "accepted",
                "a FRESH observation reads #state == 'accepted'",
            )
        closed = next(
            ((task.evidence or {}).get("verdict") for task in record.tasks
             if task.capability == "Browser.CloseBrowserSession"),
            None,
        )
        result.check(closed == "matched", "the browser session is verifiably closed")

    result.check(
        result.facts.get("AI planning calls") == 0,
        "planned deterministically — no provider was asked how to click a button",
    )
    result.check(
        "accepted" in (status.message or ""),
        "the founder is told the value they asked for",
    )
    # Independent verification: the server, not the browser that drove it.
    final = fixture.observed_state()
    result.fact("fixture server says", final)
    result.check(final["state"] == "accepted", "the fixture itself records 'accepted'")
    result.check(final["typed"] == "acceptance", "the fixture received the exact text")
    return result


# =====================================================================
# Golden path 3 — REASONING + REAL ACTION
# =====================================================================


def golden_reasoning(pipeline) -> Result:
    result = Result("GOLDEN PATH 3 — REASONING + FILE")
    filename = f"demo_names_{STAMP}.txt"
    target = DESKTOP / filename
    objective = (
        f"Think of exactly three short names for a gardening notes app and "
        f"write them one per line into {filename} on the Desktop."
    )
    result.fact("objective", objective)
    banner(result.name)
    print(f"  {objective}", flush=True)

    _reply, status, _rows = run_objective(pipeline, objective, result)
    mission_control = pipeline[2]

    result.check(status.objective_id is not None, "a mission was created")
    if status.objective_id:
        capabilities = capabilities_run(mission_control, status.objective_id)
        result.fact("capabilities", capabilities)
        result.fact("evidence", evidence_of(mission_control, status.objective_id))
        result.check(
            capabilities == ["Reasoning.Transform", "Filesystem.WriteFile"],
            "reasoning produces the text, the filesystem writes it",
        )
        record = mission_control.dispatcher.objective(status.objective_id)
        reasoning = next(
            (task for task in record.tasks if task.capability == "Reasoning.Transform"),
            None,
        )
        if reasoning is not None:
            verdict = (reasoning.evidence or {}).get("verdict")
            result.fact("TextVerifier", verdict)
            result.check(verdict == "matched", "the generated answer was verified")
            generated = ((reasoning.evidence or {}).get("observation") or {}).get("text")
            result.fact("verified text", (generated or "").replace("\n", " / ")[:120])
            if target.is_file():
                written = target.read_text(encoding="utf-8", errors="replace")
                result.check(
                    written.strip() == (generated or "").strip(),
                    "the file holds EXACTLY the verified answer, bound from Evidence",
                )
        written_verdict = next(
            ((task.evidence or {}).get("verdict") for task in record.tasks
             if task.capability == "Filesystem.WriteFile"),
            None,
        )
        result.check(written_verdict == "matched", "the write was independently verified")

    result.check(
        result.facts.get("AI planning calls") == 0,
        "planned deterministically — AI is used to THINK, never to plan",
    )
    result.check(target.is_file(), f"file exists on disk: {target}")
    if target.is_file():
        lines = [ln for ln in target.read_text(encoding="utf-8").splitlines() if ln.strip()]
        result.fact("file contents", " / ".join(lines))
        result.check(len(lines) == 3, "three names, one per line")
    return result


# =====================================================================


def main() -> int:
    banner("BUILDING THE REAL PIPELINE")
    print(f"  repo         : {REPO}", flush=True)
    print(f"  FMEA scope   : {os.environ.get('KALPAVRIKSHA_FMEA_REASONING_TIER') or '(unset — production ladder)'}",
          flush=True)
    pipeline = kd._build_mission_pipeline()
    if pipeline is None:
        print("NO PIPELINE.", flush=True)
        return 2

    wanted = set(sys.argv[1:]) or {"local", "browser", "reasoning"}
    fixture = _Fixture()
    results: list[Result] = []
    try:
        if "local" in wanted:
            results.append(golden_local(pipeline))
        if "browser" in wanted:
            fixture.start()
            print(f"\n  fixture serving {fixture.url}", flush=True)
            results.append(golden_browser(pipeline, fixture))
        if "reasoning" in wanted:
            results.append(golden_reasoning(pipeline))
    finally:
        with contextlib.suppress(Exception):
            fixture.stop()

    for result in results:
        result.report()

    banner("BATTERY SUMMARY")
    for result in results:
        print(f"  {'PASS' if result.passed else 'FAIL'}  {result.name}"
              f"   ({result.seconds:.1f}s)", flush=True)
        if not result.passed:
            print(f"        first broken boundary: {result.first_broken}", flush=True)
    everything = all(result.passed for result in results)
    banner(f"DEMO BATTERY: {'PASS' if everything else 'FAIL'}")
    return 0 if everything else 1


if __name__ == "__main__":
    raise SystemExit(main())
