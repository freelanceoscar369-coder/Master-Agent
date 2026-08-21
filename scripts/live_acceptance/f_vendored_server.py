"""The vendored pywebview server, actually serving the founder's page.

## Why this is a runner and not a unit test

It binds a real TCP port. That is exactly why it is worth running — and
exactly why it does not belong in the suite, where a bound port is a
flake waiting for a busy machine.

## What it protects

`FixedBottleServer` and its two adapters were moved out of
`founder_edition/desktop_shell.py` into the composition root, because
serving a page needs a socket and filesystem paths and that package is
architecture-guarded against both. The move is behaviour-preserving by
construction — same classes, different module — but "by construction" is
not evidence, and the unit tests around `create_window()` install a FAKE
webview, so they would not notice if the real server stopped working.

This runs the real one. It checks the specific thing the class exists to
fix: pywebview 6.x routes both `/` and `/<file:path>` to `asset(file)`,
and `/` supplies no `file`, so the founder's window opens on a
`TypeError` instead of the page.

No window is opened. Nothing is installed. It starts a server, fetches
two URLs, and stops.
"""
from __future__ import annotations

import sys
import urllib.request

sys.path.insert(0, "D:/MasterAgent")
sys.path.insert(0, "D:/MasterAgent/src")

import kalpavriksha_desktop as kd  # noqa: E402


def banner(text):
    print("\n" + "=" * 70, flush=True)
    print(text, flush=True)
    print("=" * 70, flush=True)


def main() -> int:
    banner("THE RELOCATED SERVER, SERVING THE REAL PAGE")
    page = kd._bundled_dir("web") + "/index.html"
    print(f"web root: {page}", flush=True)

    ok = True
    url, _key, server = kd.FixedBottleServer.start_server([page])
    print(f"listening: {url}", flush=True)
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            body = response.read().decode("utf-8", "replace")
        if response.status == 200 and ("<html" in body.lower() or "<!doctype" in body.lower()):
            print(f"PASS  GET /            -> {response.status}, {len(body)} bytes of HTML",
                  flush=True)
            print("      (this is the pywebview 6.x bug the class exists to fix:",
                  flush=True)
            print("       unpatched, '/' reaches asset(file) with no file and raises)",
                  flush=True)
        else:
            print(f"FAIL  GET / returned {response.status} and no HTML", flush=True)
            ok = False

        asset = url.rstrip("/") + "/js/app.js"
        with urllib.request.urlopen(asset, timeout=10) as response:
            payload = response.read()
        if response.status == 200 and payload:
            print(f"PASS  GET /js/app.js   -> {response.status}, {len(payload)} bytes",
                  flush=True)
        else:
            print(f"FAIL  asset route returned {response.status}", flush=True)
            ok = False
    except Exception as exc:  # noqa: BLE001 — the whole point is to see it
        print(f"FAIL  the server did not serve: {exc!r}", flush=True)
        ok = False
    finally:
        try:
            server.running = False
        except Exception:  # noqa: BLE001
            pass

    banner(f"VENDORED SERVER: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
