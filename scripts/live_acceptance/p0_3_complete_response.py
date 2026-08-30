"""P0-3A — the whole reply, three clean times.

ChatGPT Desktop produced a valid three-line answer and the reader
returned one line of it. Not truncated mid-stream: `'GardenLog'` was
perfectly stable, and complete-looking, and two thirds missing. The
expectation then correctly rejected it and the mission fell through to
the next provider, which is the behaviour the founder saw as
"Kalpavriksha kept working while the app had already answered".

This runs the founder's own acceptance prompt through the real provider
path and checks the reconstruction against what the reply must contain:
three names, one per line, no missing line, no prompt echo.
"""
from __future__ import annotations

import logging
import os
import sys
import time

logging.basicConfig(level=logging.ERROR)
os.environ.setdefault("KALPAVRIKSHA_DISABLE_MIC", "1")
sys.path.insert(0, "D:/MasterAgent")
sys.path.insert(0, "D:/MasterAgent/src")

from master_agent.desktop.actions import DesktopContext  # noqa: E402
from master_agent.desktop.probe import RealSystemProbe  # noqa: E402
from master_agent.providers.desktop_app import build_desktop_providers  # noqa: E402

PROMPT = ("Give exactly three short names for a gardening notes app, "
          "one name per line.")


def ascii_of(text):
    return (text or "").encode("ascii", "replace").decode("ascii")


def judge(reply: str) -> tuple[bool, str]:
    """What the founder asked for, checked structurally: three non-empty
    lines, none of them the question."""
    lines = [line.strip() for line in (reply or "").splitlines() if line.strip()]
    if len(lines) < 3:
        return False, f"only {len(lines)} line(s) captured"
    if any(PROMPT[:30].lower() in line.lower() for line in lines):
        return False, "the founder's own prompt appears in the reply"
    if any("kalpavriksha reasoning" in line.lower() for line in lines):
        return False, "the session marker appears in the reply"
    # An earlier version of this judge passed eight lines of Kimi's own
    # chrome -- 'Copy', 'Share', 'Your chats will appear here' -- as a
    # three-name answer, because it only counted lines. Counting is not
    # judging. Chrome the founder never asked for is a failure however
    # many lines of it there are.
    # The vocabulary used to live here, in this script, which meant the
    # acceptance run was the only thing protected by it. It now lives in
    # the provider that does the classifying, and this imports it -- one
    # owner, and a real run is checked against the same knowledge the
    # product uses.
    from master_agent.providers.desktop_app import _INTERFACE_LABELS
    offenders = [line for line in lines if line.strip().lower() in _INTERFACE_LABELS]
    if offenders:
        return False, f"UI chrome captured as reply: {offenders[:3]}"
    if len(lines) > 6:
        return False, f"{len(lines)} lines for a three-name answer -- likely a window sweep"
    return True, f"{len(lines)} lines"


def main() -> int:
    provider_id = sys.argv[1] if len(sys.argv) > 1 else "chatgpt-desktop"
    runs = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    ctx = DesktopContext(probe=RealSystemProbe())
    ctx.refresh(read_versions=False, deep=True)
    providers = {p.provider_id: p for p in build_desktop_providers(ctx)}
    provider = providers.get(provider_id)
    if provider is None:
        print(f"no such provider: {provider_id}")
        return 2

    availability = provider.availability()
    if not getattr(availability, "reachable", False):
        print(f"{provider_id}: NOT ELIGIBLE — {getattr(availability, 'detail', '')}")
        return 0

    passed = 0
    for run in range(1, runs + 1):
        print("\n" + "=" * 66, flush=True)
        print(f"{provider_id}  RUN {run}", flush=True)
        print("=" * 66, flush=True)
        started = time.monotonic()
        try:
            result = provider.complete(PROMPT)
        except Exception as exc:  # noqa: BLE001
            print(f"  complete() raised: {type(exc).__name__}: {exc}", flush=True)
            continue
        elapsed = time.monotonic() - started

        text = ascii_of(getattr(getattr(result, "response", None), "text", "") or "")
        ok = bool(getattr(result, "ok", False))
        print(f"  ok={ok}  {elapsed:.1f}s", flush=True)
        print("  ---- reconstructed reply ----", flush=True)
        for line in (text.splitlines() or ["(empty)"]):
            print(f"  | {line}", flush=True)
        print("  -----------------------------", flush=True)

        good, why = judge(text)
        print(f"  VERDICT: {'PASS' if good else 'FAIL'} — {why}", flush=True)
        passed += 1 if good else 0
        time.sleep(3)

    print("\n" + "=" * 66, flush=True)
    print(f"{provider_id}: {passed}/{runs} clean", flush=True)
    return 0 if passed == runs else 1


if __name__ == "__main__":
    raise SystemExit(main())
