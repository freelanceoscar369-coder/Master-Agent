"""Diagnostic: WHY does reading order rebuild JSON in the wrong order?

Measured live: ChatGPT Desktop returned a correct obligation set and the
lane rebuilt it as invalid JSON, with two `depends_on` values moved to the
end, after the objects that should contain them. Prose survives that
reordering; JSON does not.

`_in_reading_order()` sorts by (top, left) off each element's rectangle.
Whether that is the wrong rule, or the right rule fed wrong rectangles,
cannot be settled by reading the code -- so this prints the rows it
actually sorts: rect, top, left, and the text.

Changes no product behaviour. It wraps `_in_reading_order`, prints what it
was handed and what it returned, and calls the real method through.

    python _reply_geometry_dump.py [provider_id]
"""
from __future__ import annotations

import logging
import os
import sys

logging.basicConfig(level=logging.WARNING, format="[%(levelname)s] %(message)s")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, "D:/MasterAgent")
sys.path.insert(0, "D:/MasterAgent/src")

PROVIDER = sys.argv[1] if len(sys.argv) > 1 else "chatgpt-desktop"

#: Small, but structured the same way the obligation set is: nested
#: objects, arrays, and a value that a wrap could separate from its key.
PROMPT = (
    "Return JSON only, no prose and no code fence:\n"
    '{"anchors": [{"anchor_id": "anchor_1", "meaning": "create the folder", '
    '"depends_on": []}, {"anchor_id": "anchor_2", "meaning": "write the file", '
    '"depends_on": ["anchor_1"]}, {"anchor_id": "anchor_3", '
    '"meaning": "verify both", "depends_on": ["anchor_1", "anchor_2"]}]}\n'
    "Reproduce exactly that object and nothing else."
)


def ascii_of(text):
    return (text or "").encode("ascii", "replace").decode("ascii")


def main() -> int:
    from master_agent.ai_infrastructure.catalog import PROVIDER_CATALOG
    from master_agent.desktop.actions import DesktopContext
    from master_agent.desktop.execution.uia_control import UiaAutomationBridge
    from master_agent.desktop.probe import RealSystemProbe
    from master_agent.providers.desktop_app import DesktopAppReasoningProvider

    spec = next(s for s in PROVIDER_CATALOG if s.provider_id == PROVIDER)
    ctx = DesktopContext(probe=RealSystemProbe())
    provider = DesktopAppReasoningProvider(spec, context=ctx)

    original = UiaAutomationBridge._in_reading_order

    def traced(kept):
        rows = list(kept)
        print(f"\n---- _in_reading_order got {len(rows)} row(s) ----", flush=True)
        # DOCUMENT order -- the order the tree walk produced. Printing this
        # sorted (as a first version did) hides the very thing in question:
        # whether the geometric sort is improving that order or destroying
        # it.
        print("  [as given: document order]", flush=True)
        for top, left, text in rows:
            flat = ascii_of(" ".join(text.split()))
            print(f"  top={top:>6} left={left:>6} len={len(text):>5} | {flat[:110]}",
                  flush=True)
        # What sorting by `top` alone, stably, would produce -- geometry
        # for the row, the document for the sequence within it.
        by_top = sorted(rows, key=lambda r: r[0])
        candidate = "\n".join(t for _a, _b, t in by_top)
        import json as _json
        try:
            _json.loads(candidate.strip())
            verdict = "VALID JSON"
        except Exception as exc:  # noqa: BLE001
            verdict = f"invalid -- {exc}"
        print(f"  [stable sort by top only] -> {verdict}", flush=True)
        return original(rows)

    UiaAutomationBridge._in_reading_order = staticmethod(traced)
    try:
        result = provider.complete(PROMPT)
        text = getattr(result, "text", "") or ""
        print("\n===== RESULT =====")
        print("  ok:", getattr(result, "ok", None), " outcome:",
              getattr(result, "outcome", None))
        print("  reply chars:", len(text))
        print("  ---- reply ----")
        print("  " + ascii_of(text).replace("\n", "\n  ")[:2000])
        import json
        try:
            json.loads(text.strip())
            print("  json.loads: OK")
        except Exception as exc:  # noqa: BLE001
            print(f"  json.loads: FAILED -- {exc}")
    finally:
        UiaAutomationBridge._in_reading_order = original
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
