"""Read-only: what does the Gemini page actually show right now?

The ownership probe timed out twice with an empty reply. A timeout tells
you nothing about WHY, and guessing is how the previous wrong conclusion
was reached. This observes the page and types nothing.

It answers exactly three questions:

  1. Did Gemini reply at all? (search for the run's sentinels)
  2. Is the 40-character ANCHOR present in any single element? The
     provider will not consider ANY text an answer until it sees the
     anchor, so if the page collapses a long user turn behind a
     "Show more", the anchor never appears and the wait can only time
     out -- an answer sitting in plain sight.
  3. How is the turn chunked, and how large are the elements?
"""
from __future__ import annotations

import logging
import os
import sys

logging.basicConfig(level=logging.ERROR)
os.environ.setdefault("KALPAVRIKSHA_DISABLE_MIC", "1")
sys.path.insert(0, "D:/MasterAgent")
sys.path.insert(0, "D:/MasterAgent/src")

from master_agent.desktop.actions import DesktopContext  # noqa: E402
from master_agent.desktop.probe import RealSystemProbe  # noqa: E402
from master_agent.desktop.trusted_browser_adapter import (  # noqa: E402
    DesktopTrustedBrowser,
)

NONCE = sys.argv[1] if len(sys.argv) > 1 else "75F6F7FD"
SENTINELS = (f"KALPAVRIKSHA_TURN_ONE_OK_{NONCE}", f"KALPAVRIKSHA_TURN_TWO_OK_{NONCE}")
DECOY = "KALPAVRIKSHA_DECOY_LINE_THIS_IS_PROMPT_TEXT_NOT_A_MODEL_ANSWER"
ANCHOR_SOURCE = (
    "You are being used as a reasoning provider by an automated system.\n"
    f"{DECOY}\n"
)
ANCHOR = ANCHOR_SOURCE.strip()[:40]


def ascii_of(text):
    return (text or "").encode("ascii", "replace").decode("ascii")


def main() -> int:
    ctx = DesktopContext(probe=RealSystemProbe())
    ctx.refresh(read_versions=False, deep=True)
    browser = DesktopTrustedBrowser(ctx)

    # Reach the window the same way the provider does. Observing without
    # this reads whatever happens to be in front -- which is how the first
    # attempt at this dump reported zero elements and proved nothing.
    from master_agent.providers.trusted_web_ai import GEMINI_WEB

    resolution = browser.resolve(GEMINI_WEB.page_markers)
    chosen = getattr(resolution, "chosen", None)
    print(f"resolve  : chosen={getattr(chosen, 'title', None)!r} "
          f"options={len(getattr(resolution, 'options', ()) or ())}")
    if chosen is None:
        print("no browser window shows Gemini — nothing to observe.")
        return 2
    used = browser.use(chosen)
    print(f"use      : ok={getattr(used, 'ok', None)} {getattr(used, 'detail', '')}")

    observation = browser.observe()
    texts = list(observation.texts())

    print(f"window   : {ascii_of(getattr(observation, 'window_title', ''))}")
    print(f"elements : {len(texts)} with a non-empty name")
    print(f"anchor   : {ascii_of(ANCHOR)!r}")
    print()

    anchored = [i for i, t in enumerate(texts) if ANCHOR in t]
    print(f"ANCHOR PRESENT IN {len(anchored)} element(s): {anchored[:5]}")
    if not anchored:
        print("  >>> the provider can never accept an answer in this state:")
        print("  >>> _await_answer() requires the anchor before it considers any text.")
    print()

    for sentinel in SENTINELS:
        hits = [i for i, t in enumerate(texts) if sentinel in t]
        print(f"{sentinel}: {'PRESENT in ' + str(hits[:5]) if hits else 'ABSENT'}")
    decoy_hits = [i for i, t in enumerate(texts) if DECOY in t]
    print(f"decoy line: {'present in ' + str(decoy_hits[:5]) if decoy_hits else 'absent'}")
    print()

    # What the PROVIDER sees is not what the window contains: it reads
    # only `response_role` elements. Deciding site vocabulary from the
    # full window would add noise entries for things it never receives.
    conversation = [
        e.name.strip()
        for e in observation.named(GEMINI_WEB.response_role)
        if (e.name or "").strip()
    ]
    print(f"---- {len(conversation)} element(s) of role "
          f"{GEMINI_WEB.response_role!r}: what the provider actually reads ----")
    for i, t in enumerate(conversation):
        flat = ascii_of(" ".join(t.split()))
        if len(flat) < 80 or any(s in t for s in SENTINELS):
            print(f"  <{i:>3}> ({len(t):>6}) {flat[:150]}")
    print("---- (long constraint chunks omitted above) ----")
    print()

    sizes = sorted(((len(t), i) for i, t in enumerate(texts)), reverse=True)[:8]
    print("largest elements (chars, index):", sizes)
    print()
    print("---- every element, truncated ----")
    for i, t in enumerate(texts):
        flat = ascii_of(" ".join(t.split()))
        print(f"[{i:>3}] ({len(t):>6}) {flat[:150]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
