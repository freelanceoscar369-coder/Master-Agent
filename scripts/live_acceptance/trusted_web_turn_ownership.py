"""Trusted-Web current-turn ownership — the live re-proof.

The repair is source-proven: 37 focused tests, including the adversarial
overlap cases. Source tests are not usability proof, so this drives the
real provider path against the real page and asks the only question that
matters live:

    does the extractor return GEMINI'S CURRENT TURN, and nothing else?

Two failure modes are checked in one session, because they fail
differently and a run that only tests one proves half of it:

  1. PROMPT ECHO. A 40-character anchor can only identify the FIRST
     fragment of a turn. A ~26K prompt is split across many page
     elements, every later one anchorless, and that is how the founder's
     own prompt came back as though Gemini had written it. So the prompt
     here is deliberately huge, and it carries a DECOY line that reads
     like an answer. If any prompt chunk is returned, the decoy shows up.

  2. CONVERSATION HISTORY. The second turn runs in the SAME conversation,
     with a different sentinel. Turn 2 must return turn 2's sentinel and
     must not return turn 1's -- yesterday's answer is not today's.

Nothing here pattern-matches Gemini's markup. It compares what came back
against what we sent, which is the same question the provider asks.

Live, adversarial, and it types a lot into the founder's own browser.
"""
from __future__ import annotations

import logging
import os
import secrets
import sys
import time

logging.basicConfig(level=logging.ERROR)
os.environ.setdefault("KALPAVRIKSHA_DISABLE_MIC", "1")
sys.path.insert(0, "D:/MasterAgent")
sys.path.insert(0, "D:/MasterAgent/src")

from master_agent.desktop.actions import DesktopContext  # noqa: E402
from master_agent.desktop.probe import RealSystemProbe  # noqa: E402
from master_agent.desktop.trusted_browser_adapter import (  # noqa: E402
    DesktopTrustedBrowser,
)
from master_agent.providers.trusted_web_ai import (  # noqa: E402
    GEMINI_WEB,
    TrustedWebAiProvider,
)

#: Never appears in a reply unless a chunk of the PROMPT was returned as
#: the answer. It is phrased as bait: it looks like a finished answer.
DECOY = "KALPAVRIKSHA_DECOY_LINE_THIS_IS_PROMPT_TEXT_NOT_A_MODEL_ANSWER"

#: The live failure was ~26K. Size IS the reproduction: below the point
#: where the page splits the turn, an anchor-only rule still looks right.
#: Sized TO that figure rather than past it -- a 100K prompt would prove
#: something the founder never hit, and may not survive the input limit.
TARGET_PROMPT_CHARS = 26_000


def _normalised(text: str) -> str:
    return " ".join((text or "").split())


def build_prompt(sentinel: str) -> str:
    """A planning-shaped prompt: enormous in, one short line out."""
    lines: list[str] = []
    size = 0
    i = 0
    while size < TARGET_PROMPT_CHARS:
        line = (
            f"constraint {i}: the plan must respect obligation {i}, and obligation "
            f"{i} is satisfied only when its evidence is observed rather than assumed."
        )
        lines.append(line)
        size += len(line) + 1
        i += 1
    bulk = "\n".join(lines)
    return (
        "You are being used as a reasoning provider by an automated system.\n"
        f"{DECOY}\n"
        "Below is a long list of constraints. Do not summarise them, do not "
        "repeat them, and do not explain anything.\n\n"
        f"{bulk}\n\n"
        "Reply with exactly one line containing only this token, and nothing "
        f"else at all:\n{sentinel}\n"
    )


def judge(reply: str, prompt: str, sentinel: str, stale: str | None) -> tuple[bool, list[str]]:
    """Ownership, checked against what we sent rather than against Gemini."""
    faults: list[str] = []
    text = reply or ""
    flat_reply = _normalised(text)
    flat_prompt = _normalised(prompt)

    if not flat_reply:
        return False, ["empty reply"]

    if sentinel not in text:
        faults.append(f"this turn's sentinel {sentinel} is missing from the reply")

    if DECOY in text:
        faults.append("THE DECOY CAME BACK — a prompt chunk was returned as the answer")

    if stale and stale in text:
        faults.append(f"the PREVIOUS turn's sentinel {stale} came back — history was returned")

    # The whole reply being inside what we sent is the original defect
    # exactly. Checked directly rather than inferred from the decoy.
    #
    # The sentinel is excluded first, and must be: we ASKED for it by
    # printing it in the prompt, so a perfect reply is trivially a
    # substring of what we sent. Without this the check would fail every
    # correct run and pass nothing -- a red light wired to the wrong
    # wire. What must never come back is the prompt's BULK.
    remainder = _normalised(text.replace(sentinel, " "))
    if len(remainder) >= 16 and remainder in flat_prompt:
        faults.append("the reply, sentinel aside, is contained in the submitted prompt")

    # And no substantial run of the prompt may appear inside the reply,
    # which catches a partial echo the decoy happened to miss.
    window = 120
    for start in range(0, max(1, len(flat_prompt) - window), window):
        chunk = flat_prompt[start:start + window]
        if chunk and chunk in flat_reply:
            faults.append(f"a {window}-char run of the prompt appears in the reply")
            break

    return not faults, faults


def run_turn(provider, label: str, sentinel: str, stale: str | None) -> bool:
    prompt = build_prompt(sentinel)
    print("\n" + "=" * 68, flush=True)
    print(f"{label}   prompt {len(prompt):,} chars   sentinel {sentinel}", flush=True)
    print("=" * 68, flush=True)

    started = time.monotonic()
    try:
        result = provider.complete(prompt)
    except Exception as exc:  # noqa: BLE001
        print(f"  complete() raised: {type(exc).__name__}: {exc}", flush=True)
        return False
    elapsed = time.monotonic() - started

    ok = bool(getattr(result, "ok", False))
    response = getattr(result, "response", None)
    text = getattr(response, "text", "") or ""
    outcome = getattr(result, "outcome", "?")

    print(f"  ok={ok}  outcome={outcome}  {elapsed:.1f}s  reply {len(text):,} chars", flush=True)
    print("  ---- reply as extracted ----", flush=True)
    for line in (text.splitlines() or ["(empty)"])[:12]:
        print(f"  | {line[:160]}", flush=True)
    if len(text.splitlines()) > 12:
        print(f"  | ... {len(text.splitlines()) - 12} more line(s)", flush=True)
    print("  ----------------------------", flush=True)

    if not ok:
        # `failure()` puts the reason in `error`; `detail` is the extra
        # keyword bag and is empty here. Printing detail said "{}" and
        # taught us nothing about a 237-second failure.
        reason = getattr(result, "error", "") or getattr(result, "detail", "")
        print(f"  VERDICT: FAIL — provider did not succeed: {reason}", flush=True)
        return False

    good, faults = judge(text, prompt, sentinel, stale)
    if good:
        print("  VERDICT: PASS — the reply is Gemini's current turn and only that", flush=True)
    else:
        for fault in faults:
            print(f"  VERDICT: FAIL — {fault}", flush=True)
    return good


def main() -> int:
    nonce = secrets.token_hex(4).upper()
    first = f"KALPAVRIKSHA_TURN_ONE_OK_{nonce}"
    second = f"KALPAVRIKSHA_TURN_TWO_OK_{nonce}"

    print("Trusted-Web current-turn ownership — LIVE", flush=True)
    print("This drives the founder's own browser. It will take the keyboard.", flush=True)

    ctx = DesktopContext(probe=RealSystemProbe())
    ctx.refresh(read_versions=False, deep=True)

    # The identity and the deferred interaction come from the real
    # composition root. Re-deriving either here would mean this run proved
    # a provider the product does not actually build.
    import kalpavriksha_desktop as fe

    provider = TrustedWebAiProvider(
        browser=DesktopTrustedBrowser(ctx),
        site=GEMINI_WEB,
        interaction=fe.founder_interaction(),
        founder_identity=fe.FOUNDER_WEB_IDENTITY,
    )

    availability = provider.availability()
    reachable = getattr(availability, "reachable", None)
    print(f"availability: reachable={reachable} {getattr(availability, 'detail', '')}", flush=True)
    if reachable is False:
        print("NOT ELIGIBLE — no live proof produced.", flush=True)
        return 2

    turn_one = run_turn(provider, "TURN 1 — prompt-echo ownership", first, stale=None)
    time.sleep(4)
    turn_two = run_turn(provider, "TURN 2 — history ownership (same conversation)",
                        second, stale=first)

    print("\n" + "=" * 68, flush=True)
    passed = int(turn_one) + int(turn_two)
    print(f"TRUSTED-WEB CURRENT-TURN OWNERSHIP: {passed}/2 turns clean", flush=True)
    if passed == 2:
        print("LIVE-PROVEN = TRUE", flush=True)
    else:
        print("LIVE-PROVEN = FALSE — do not run any planner benchmark on this route",
              flush=True)
    return 0 if passed == 2 else 1


if __name__ == "__main__":
    raise SystemExit(main())
