"""P0-2 — does autonomous reasoning actually use its own conversation?

The founder observed desktop AI applications being driven inside whatever
chat happened to be open. The architecture already has the right idea:
`ReasoningSessionManager.establish()` looks for a conversation named
exactly "Kalpavriksha Reasoning", opens it if found, and otherwise starts
a new one and tries to rename it.

The gap is what happens when that rename fails. `create_named_session()`
returns SUCCESS regardless -- so a failed rename means Kalpavriksha types
into an anonymous new conversation, which is precisely the outcome the
founder rejected.

This measures, per installed provider, exactly where the chain stops:

    app discovered
    window launched/focused
    Chat surface selected (where the app has one)
    "Kalpavriksha Reasoning" found  OR  created
    renamed so a FUTURE call can find it
    positively findable by exact name afterwards

Read-only about policy: it changes nothing and decides nothing. It exists
so the policy change is made against measured behaviour per application
rather than against an assumption about all of them.
"""
from __future__ import annotations

import logging
import os
import sys
import time

os.environ.setdefault("KALPAVRIKSHA_DISABLE_MIC", "1")
sys.path.insert(0, "D:/MasterAgent")
sys.path.insert(0, "D:/MasterAgent/src")

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

from master_agent.desktop.actions import DesktopContext  # noqa: E402
from master_agent.desktop.execution.keyboard import KeyboardController  # noqa: E402
from master_agent.desktop.probe import RealSystemProbe  # noqa: E402
from master_agent.providers.desktop_app import build_desktop_providers  # noqa: E402
from master_agent.providers.reasoning_session import (  # noqa: E402
    DEDICATED_SESSION_NAME,
)


def banner(text):
    print("\n" + "=" * 74, flush=True)
    print(text, flush=True)
    print("=" * 74, flush=True)


def main() -> int:
    # The real machine, scanned once -- `availability()` reads this cache
    # and answers "not installed" without it.
    context = DesktopContext(probe=RealSystemProbe())
    print("scanning the machine ...", flush=True)
    inventory = context.refresh(read_versions=False, deep=True)
    print(f"applications discovered: {len(list(getattr(inventory, 'applications', []) or []))}",
          flush=True)

    providers = build_desktop_providers(context)
    print(f"desktop reasoning providers in the catalogue: {len(providers)}", flush=True)

    rows = []
    for provider in providers:
        pid = getattr(provider, "provider_id", "?")
        banner(f"PROVIDER: {pid}")

        avail = provider.availability()
        available = bool(getattr(avail, "reachable", False))
        notes = str(getattr(avail, "detail", "") or "")
        print(f"  available : {available}", flush=True)
        print(f"  notes     : {notes[:150]}", flush=True)
        if not available:
            rows.append((pid, "not installed / not eligible", notes[:60], False, False))
            continue

        app = provider._resolve_app_record(context.cached)
        window = None
        try:
            window = provider._launch_or_focus(app)
        except Exception as exc:  # noqa: BLE001
            print(f"  launch/focus raised: {type(exc).__name__}: {exc}", flush=True)
        print(f"  window    : {window}", flush=True)
        if not window:
            rows.append((pid, "no window", "", False, False))
            continue

        time.sleep(2.0)
        manager = provider._sessions
        handle = window["handle"]

        found_before = manager.find_named_session(handle) is not None
        print(f"  {DEDICATED_SESSION_NAME!r} present beforehand: {found_before}", flush=True)

        established = None
        try:
            established = manager.establish(window, provider._spec.label, KeyboardController())
        except Exception as exc:  # noqa: BLE001
            print(f"  establish() raised: {type(exc).__name__}: {exc}", flush=True)

        if established is None:
            rows.append((pid, "establish raised", "", found_before, False))
            continue

        ok = bool(getattr(established, "ok", False))
        reused = bool(getattr(established, "reused", False))
        renamed = bool(getattr(established, "renamed", False))
        reason = getattr(established, "reason", "") or ""
        print(f"  establish : ok={ok} reused={reused} renamed={renamed}", flush=True)
        if reason:
            print(f"  reason    : {reason[:160]}", flush=True)

        # The question that matters: can a FUTURE call find it by name?
        time.sleep(1.5)
        findable = manager.find_named_session(handle) is not None
        print(f"  findable by exact name afterwards: {findable}", flush=True)

        # A fresh conversation carrying this call's own marker as its
        # first message is NOT anonymous -- an earlier version of this
        # probe called it a policy violation, which is what led to two
        # usable providers being refused. What it lacks is REUSE: without
        # an exact name, the next call creates another one.
        verdict = (
            "REUSES ITS NAMED SESSION" if (ok and findable)
            else "FRESH MARKED SESSION (no reuse next call)" if ok
            else "refused (fails closed)"
        )
        print(f"  VERDICT   : {verdict}", flush=True)
        rows.append((pid, verdict, reason[:50], reused, findable))

    banner("SUMMARY")
    print(f"{'provider':<24}{'reused':<9}{'findable':<11}verdict", flush=True)
    for pid, verdict, _reason, reused, findable in rows:
        print(f"{pid:<24}{str(reused):<9}{str(findable):<11}{verdict}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
