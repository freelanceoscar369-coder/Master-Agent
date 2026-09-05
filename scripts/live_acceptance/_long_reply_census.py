"""Diagnostic: a reply taller than the window -- what is actually there?

MODERATE fails at the obligation audit with "the audit was not a JSON
object". The recorded reason is that the reply's own head
(`{"regions":[...`) was absent from the reconstruction. Two very
different causes produce that, and they need opposite repairs:

  (a) the head IS in the accessibility tree and the candidate filter
      drops it -- offscreen flag, clipped height, or the prompt floor;
  (b) the head is NOT in the tree at all, because the application
      virtualises rows it has scrolled away.

Reading the code cannot tell them apart. This censuses EVERY
text-bearing descendant at the moment the reply settles, without any
filter, and prints why each one would have been kept or dropped. It also
counts the per-message `Copy` affordance, which an earlier note claims is
hover-dependent and therefore never present.

Changes no product behaviour: it wraps `_text_region_candidates`,
records, and calls the real method through.

    python _long_reply_census.py [provider_id]
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

#: Deliberately taller than any window: eight objects, each on its own
#: line, is what the real obligation audit returns for the MODERATE
#: request. The shape does not matter; the HEIGHT does.
PROMPT = (
    "Return JSON only -- no prose, no code fence, no commentary.\n"
    "An object with one key, \"regions\", whose value is an array of "
    "EIGHT objects. Each object has keys \"region_id\" (region_1 .. "
    "region_8), \"source_quote\" (a full sentence of at least 90 "
    "characters describing a distinct step of setting up a quarterly "
    "reporting folder), and \"meaning\" (a full sentence of at least 90 "
    "characters restating that step as a verifiable requirement).\n"
    "Print each object on its own line so the whole answer is tall."
)


def ascii_of(text):
    return (text or "").encode("ascii", "replace").decode("ascii")


def main() -> int:
    from master_agent.ai_infrastructure.catalog import PROVIDER_CATALOG
    from master_agent.desktop.actions import DesktopContext
    from master_agent.desktop.execution import uia_control as uc
    from master_agent.desktop.execution.uia_control import UiaAutomationBridge
    from master_agent.desktop.probe import RealSystemProbe
    from master_agent.providers.desktop_app import DesktopAppReasoningProvider

    spec = next(s for s in PROVIDER_CATALOG if s.provider_id == PROVIDER)
    ctx = DesktopContext(probe=RealSystemProbe())
    provider = DesktopAppReasoningProvider(spec, context=ctx)

    original = UiaAutomationBridge._text_region_candidates
    census: dict = {"rows": [], "win": None, "n": 0}

    def traced(self, root, win_rect, min_height):
        census["n"] += 1
        rows = []
        for element in self._descendants(root):
            try:
                focusable = bool(element.CurrentIsKeyboardFocusable)
                has_text = bool(element.GetCurrentPropertyValue(
                    uc._IS_TEXT_PATTERN_AVAILABLE_PROPERTY_ID))
                offscreen = bool(element.GetCurrentPropertyValue(
                    uc._IS_OFFSCREEN_PROPERTY_ID))
                rect = element.CurrentBoundingRectangle
                clipped = (min(rect.bottom, win_rect.bottom)
                           - max(rect.top, win_rect.top))
                text = self.read_text(element) if has_text else ""
            except Exception as exc:  # noqa: BLE001
                rows.append(("ERROR", 0, 0, 0, 0, 0, str(exc)[:80]))
                continue
            if not (text or "").strip():
                continue
            if focusable:
                why = "dropped: focusable"
            elif not has_text:
                why = "dropped: no text pattern"
            elif offscreen:
                why = "dropped: OFFSCREEN flag"
            elif clipped < min_height:
                why = f"dropped: clipped height {clipped}"
            else:
                why = "kept"
            rows.append((why, rect.left, rect.top, rect.right, rect.bottom,
                         clipped, text))
        census["rows"] = rows
        census["win"] = (win_rect.left, win_rect.top, win_rect.right,
                         win_rect.bottom)
        return original(self, root, win_rect, min_height)

    UiaAutomationBridge._text_region_candidates = traced
    try:
        result = provider.complete(PROMPT)
    finally:
        UiaAutomationBridge._text_region_candidates = original

    text = getattr(result, "text", "") or ""
    print("\n===== RESULT =====")
    print("  ok:", getattr(result, "ok", None),
          " outcome:", getattr(result, "outcome", None))
    print("  reason:", getattr(result, "reason", ""))
    print("  detail:", getattr(result, "detail", {}))
    print("  reply chars:", len(text))
    print("  starts:", ascii_of(text.strip()[:80]))
    print("  ends:  ", ascii_of(text.strip()[-80:]))
    import json
    try:
        json.loads(text.strip())
        print("  json.loads: OK")
    except Exception as exc:  # noqa: BLE001
        print(f"  json.loads: FAILED -- {exc}")

    print(f"\n===== LAST CENSUS (scan #{census['n']}) =====")
    print("  window rect:", census["win"])
    rows = census["rows"]
    print(f"  text-bearing elements with content: {len(rows)}")
    kept = sum(1 for r in rows if r[0] == "kept")
    print(f"  kept: {kept}   dropped: {len(rows) - kept}")
    counts: dict[str, int] = {}
    for row in rows:
        counts[row[0].split(" ")[0] + " " + " ".join(row[0].split(" ")[1:3])] = \
            counts.get(row[0].split(" ")[0] + " " + " ".join(row[0].split(" ")[1:3]), 0) + 1
    for why, n in sorted(counts.items()):
        print(f"    {why:<28} {n}")
    print("\n  ---- every row, document order ----")
    for why, left, top, right, bottom, clipped, body in rows:
        flat = ascii_of(" ".join((body or "").split()))
        print(f"  [{why:<26}] t={top:>6} b={bottom:>6} clip={clipped:>6} "
              f"len={len(body or ''):>6} | {flat[:100]}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
