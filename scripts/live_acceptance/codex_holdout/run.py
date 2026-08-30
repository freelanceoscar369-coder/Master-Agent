"""Run the frozen Codex holdout against the real Founder Edition pipeline.

This is an evidence collector, not a golden-path assertion script.  It loads
``cases.json`` verbatim, substitutes only its declared tokens, drives the real
Founder surface (including clarification turns), and records independent
filesystem/browser state beside Mission, Evidence, conformance and Broker
records.  Product adjudication remains in ``CODEX_DEMO_CONVERGENCE.md``.

Usage::

    python scripts/live_acceptance/codex_holdout/run.py
    python scripts/live_acceptance/codex_holdout/run.py --ids H01,H04,H20
"""
from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import os
import re
import socket
import socketserver
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
sys.path[:0] = [str(REPO), str(REPO / "src")]

os.environ.setdefault("KALPAVRIKSHA_DISABLE_MIC", "1")

import kalpavriksha_desktop as kd
from scripts.live_acceptance.demo_30aug_battery import (
    Result,
    _ledger_rows,
    capabilities_run,
    conformance_of,
    evidence_of,
    run_objective,
)

DESKTOP = Path.home() / "Desktop"
DOCUMENTS = Path.home() / "Documents"
STATE_ROOT = REPO / ".codex-test-state" / "holdout"


PAGE = """<!doctype html><html><head><title>Codex Holdout</title></head>
<body><h1 id="heading">Holdout home</h1>
<input id="acceptance-box"><button id="apply">Apply</button>
<span id="state">pending</span>
<script>document.querySelector('#apply').onclick=()=>{
 const v=document.querySelector('#acceptance-box').value;
 document.querySelector('#state').textContent=v==='acceptance'?'accepted':'rejected';
 fetch('/state',{method:'POST',headers:{'Content-Type':'application/json'},
 body:JSON.stringify({typed:v,state:document.querySelector('#state').textContent})});
};</script></body></html>"""

CODE_PAGE = """<!doctype html><html><head><title>Runtime code</title></head>
<body><h1>Generated code</h1><code id="code">{code}</code></body></html>"""


class Fixture:
    def __init__(self, code: str) -> None:
        self.code = code
        self.state = {"typed": None, "state": "pending", "posts": 0}
        self._lock = threading.Lock()
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        fixture = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def send(self, status: int, body: str, kind: str = "text/html") -> None:
                raw = body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", f"{kind}; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self):
                if self.path == "/redirect":
                    self.send_response(302)
                    self.send_header("Location", "/final")
                    self.end_headers()
                elif self.path == "/final":
                    self.send(200, "<html><head><title>Final</title></head>"
                              "<body><h1>Redirect landed</h1></body></html>")
                elif self.path == "/code":
                    self.send(200, CODE_PAGE.format(code=fixture.code))
                elif self.path == "/state":
                    with fixture._lock:
                        self.send(200, json.dumps(fixture.state), "application/json")
                elif self.path in ("/", "/fixture"):
                    self.send(200, PAGE)
                else:
                    self.send(404, "not found", "text/plain")

            def do_POST(self):
                if self.path != "/state":
                    self.send(404, "not found", "text/plain")
                    return
                size = int(self.headers.get("Content-Length") or 0)
                document = json.loads(self.rfile.read(size) or b"{}")
                with fixture._lock:
                    fixture.state.update(document)
                    fixture.state["posts"] += 1
                    self.send(200, json.dumps(fixture.state), "application/json")

            def log_message(self, _format, *_args):
                pass

        class Server(socketserver.ThreadingTCPServer):
            allow_reuse_address = True
            daemon_threads = True

        self._server = Server(("127.0.0.1", self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        # The frozen cases append ``/redirect`` and ``/code`` themselves,
        # so this token is the origin, not one page path.
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()


def _path_fact(path: Path) -> dict[str, Any]:
    fact: dict[str, Any] = {"path": str(path), "exists": path.exists()}
    if not path.exists():
        return fact
    fact["is_dir"] = path.is_dir()
    if path.is_dir():
        try:
            fact["listing"] = sorted(p.name for p in path.iterdir())
        except OSError as exc:
            fact["error"] = str(exc)
    else:
        try:
            raw = path.read_bytes()
            fact["sha256"] = hashlib.sha256(raw).hexdigest()
            fact["text"] = raw.decode("utf-8")[:10_000]
        except (OSError, UnicodeDecodeError) as exc:
            fact["error"] = str(exc)
    return fact


def _case_names(words: list[str]) -> list[str]:
    joined = " ".join(words)
    return sorted(set(re.findall(r"KVH_[A-Za-z0-9_.-]+", joined)))


def _world(words: list[str]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for name in _case_names(words):
        for root in (DESKTOP, DOCUMENTS):
            facts.append(_path_fact(root / name))
    return facts


def _sessions(runtime: Any) -> list[str]:
    for gateway in (getattr(runtime, "_gateways", {}) or {}).values():
        worker = getattr(gateway, "_worker", None)
        manager = getattr(worker, "_sessions", None)
        if manager is not None and hasattr(manager, "list_sessions"):
            return [row.session_id for row in manager.list_sessions()]
    return []


def _close_sessions(runtime: Any) -> None:
    for gateway in (getattr(runtime, "_gateways", {}) or {}).values():
        worker = getattr(gateway, "_worker", None)
        manager = getattr(worker, "_sessions", None)
        if manager is not None and hasattr(manager, "close_all"):
            manager.close_all()


def _setup(case_id: str, stamp: str) -> list[dict[str, Any]]:
    made: list[Path] = []
    if case_id == "H06":
        parent = Path("D:/") / f"KVH_PARENT_{stamp}"
        parent.mkdir(parents=True, exist_ok=False)
        made.append(parent)
    elif case_id == "H10":
        target = DESKTOP / f"KVH_{stamp}_companies.txt"
        target.write_text("OpenAI\nAnthropic\n", encoding="utf-8")
        made.append(target)
    elif case_id == "H20":
        target = DESKTOP / f"KVH_{stamp}_L"
        target.mkdir(parents=True, exist_ok=False)
        (target / "OLD").write_text("old", encoding="utf-8")
        made.append(target)
    elif case_id == "H21":
        target = DOCUMENTS / f"KVH_{stamp}_M"
        target.mkdir(parents=True, exist_ok=False)
        made.append(target)
    elif case_id == "H22":
        target = DESKTOP / f"KVH_{stamp}_N.txt"
        target.write_text("alpha wrong omega", encoding="utf-8")
        made.append(target)
    return [_path_fact(path) for path in made]


def _record_for(pipeline: tuple, objective_id: str | None) -> dict[str, Any] | None:
    if not objective_id:
        return None
    history = getattr(pipeline[0], "history", None)
    record = history.get(objective_id) if history is not None else None
    return record.as_dict() if record is not None else None


def run_case(pipeline: tuple, case: dict[str, Any], words: list[str], stamp: str):
    setup = _setup(case["id"], stamp)
    pre = _world(words)
    runner = pipeline[4]
    ledger_before = len(_ledger_rows(runner))
    exchanges: list[dict[str, Any]] = []
    result = Result(case["id"])
    started = time.monotonic()

    for utterance in words:
        reply, status, _rows = run_objective(
            pipeline, utterance, result, timeout=120.0
        )
        exchanges.append({"founder": utterance, "surface": reply})

    duration = time.monotonic() - started
    objective_id = getattr(status, "objective_id", None)
    caps = capabilities_run(pipeline[2], objective_id) if objective_id else []
    evidence = evidence_of(pipeline[2], objective_id) if objective_id else []
    conformance = conformance_of(pipeline[0], objective_id) if objective_id else (None, None)
    decisions = [
        row.as_dict() for row in _ledger_rows(runner)[ledger_before:]
    ]
    sessions = _sessions(pipeline[1])
    # Preserve the leak as evidence, then keep cases independent. Product
    # cleanup is still judged by ``sessions`` above; harness teardown is not
    # allowed to turn a leak into a pass or contaminate the next mission.
    _close_sessions(pipeline[1])

    return {
        "id": case["id"],
        "class": case["class"],
        "required_outcome": case["required_outcome"],
        "words": words,
        "setup": setup,
        "pre_world": pre,
        "exchanges": exchanges,
        "duration_seconds": round(duration, 3),
        "objective_id": objective_id,
        "status": getattr(status, "status", ""),
        "status_message": getattr(status, "message", ""),
        "capabilities": caps,
        "evidence": evidence,
        "conformance": {"state": conformance[0], "detail": conformance[1]},
        "plan_record": _record_for(pipeline, objective_id),
        "broker_decisions": decisions,
        "post_world": _world(words),
        "browser_sessions_after": sessions,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", default="", help="comma-separated frozen ids")
    args = parser.parse_args()
    wanted = {item.strip() for item in args.ids.split(",") if item.strip()}

    frozen = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    cases = [case for case in frozen["cases"] if not wanted or case["id"] in wanted]
    stamp = time.strftime("%H%M%S")
    code = f"RUNTIME-{stamp}-{os.getpid()}"
    fixture = Fixture(code)
    fixture.start()
    state = STATE_ROOT / stamp
    state.mkdir(parents=True, exist_ok=False)
    os.environ["KALPAVRIKSHA_STATE_DIR"] = str(state)
    pipeline = kd._build_mission_pipeline()
    if pipeline is None:
        print("NO PRODUCTION PIPELINE", flush=True)
        return 2

    results: list[dict[str, Any]] = []
    try:
        for case in cases:
            words = [
                word.replace("{STAMP}", stamp)
                .replace("{FIXTURE_URL}", fixture.url)
                .replace("{RUNTIME_CODE}", code)
                for word in case["founder_words"]
            ]
            print(f"\n[{case['id']}] {words[0]}", flush=True)
            try:
                result = run_case(pipeline, case, words, stamp)
            except Exception as exc:  # noqa: BLE001 -- collector must continue
                result = {
                    "id": case["id"], "class": case["class"],
                    "required_outcome": case["required_outcome"],
                    "words": words, "harness_error": repr(exc),
                }
            results.append(result)
            print(json.dumps({
                "status": result.get("status"),
                "conformance": (result.get("conformance") or {}).get("state"),
                "capabilities": result.get("capabilities"),
                "seconds": result.get("duration_seconds"),
                "sessions": result.get("browser_sessions_after"),
                "error": result.get("harness_error"),
            }, ensure_ascii=False), flush=True)
    finally:
        leaked_before_cleanup = _sessions(pipeline[1])
        _close_sessions(pipeline[1])
        fixture_state = dict(fixture.state)
        fixture.stop()

    output = {
        "source_head": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "frozen_source_head": frozen["source_head"],
        "stamp": stamp,
        "fixture_url": fixture.url,
        "runtime_code": code,
        "fixture_state": fixture_state,
        "browser_sessions_before_final_cleanup": leaked_before_cleanup,
        "results": results,
    }
    destination = state / "holdout-results.json"
    destination.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"\nRESULTS {destination}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
