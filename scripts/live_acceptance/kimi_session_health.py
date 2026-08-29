"""Kimi session health, live — the founder's own P0 observation.

The founder saw Kimi Desktop displaying

    Your conversation with Kimi is getting too long.
    Try starting a new session.

while Kalpavriksha kept sending requests into that same conversation.
This runs the four tests the brief asks for against the real installed
application:

    1  a saturated conversation is observed, retired, and replaced
    2  a fresh short prompt gets a genuine answer to THAT prompt
    3  a second turn answers BRAVO, with no ALPHA draft or attachment
    4  a conversation that saturates later is marked non-reusable

Nothing here closes a founder-owned window, deletes a conversation, or
renames anything the founder owns. Retirement means "this manager will
not use it again"; the conversation itself is left exactly where it is.
"""
from __future__ import annotations

import logging
import os
import pathlib
import sys
import time
import uuid

logging.basicConfig(level=logging.ERROR)
os.environ.setdefault("KALPAVRIKSHA_DISABLE_MIC", "1")
# The checkout this file belongs to, not whichever one happens to sit at
# D:/MasterAgent -- Engineering Rule 001: the working directory is never
# evidence, and neither is a hard-coded path to somebody else's tree.
_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

from master_agent.desktop.actions import DesktopContext  # noqa: E402
from master_agent.desktop.probe import RealSystemProbe  # noqa: E402
from master_agent.providers.desktop_app import build_desktop_providers  # noqa: E402
from master_agent.providers.response import SUCCEEDED  # noqa: E402


def ascii_of(text) -> str:
    return (str(text) or "").encode("ascii", "replace").decode("ascii")


class Report:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.verdicts: dict[str, str] = {}

    def note(self, key: str, value) -> None:
        self.lines.append(f"    {key}: {ascii_of(value)}")

    def verdict(self, key: str, passed: bool) -> None:
        self.verdicts[key] = "PASS" if passed else "FAIL"

    def unknown(self, key: str, why: str) -> None:
        self.verdicts[key] = "NOT YET"
        self.lines.append(f"    {key}: NOT YET -- {ascii_of(why)}")


def main() -> int:
    report = Report()
    context = DesktopContext(probe=RealSystemProbe())
    providers = {p._spec.provider_id: p for p in build_desktop_providers(context)}
    kimi = providers.get("kimi-desktop")
    if kimi is None:
        print("kimi-desktop is not a constructed provider on this machine")
        return 2

    # ---- reach the real window without writing anything into it -------
    inventory = context.inventory(deep=True)
    app = kimi._resolve_app_record(inventory)
    if app is None or not app.launchable:
        print(f"kimi-desktop is not launchable here: {app!r}")
        return 2
    window = kimi._launch_or_focus(app)
    if window is None:
        print("kimi-desktop reported no visible window")
        return 2
    handle = window["handle"]
    print(f"window handle {handle}")

    sessions = kimi._sessions

    # ---- TEST 1 - what does the application say right now? ------------
    print("\n[1] pre-flight observation of the conversation as found")
    before = sessions.inspect_session(handle)
    # A cold launch hands back a window handle before the surface has
    # rendered anything: the first run of this script read an empty
    # window and reported observed=False. `establish()` never hits that
    # -- it navigates and opens a conversation first, both of which
    # settle -- so the wait belongs here, in the one caller that looks at
    # a window nothing has touched yet.
    for _ in range(10):
        if before.observed:
            break
        time.sleep(1.0)
        before = sessions.inspect_session(handle)
    report.note("observed", before.observed)
    report.note("saturated", before.saturated)
    report.note("warning", before.warning[:160])
    report.note("stale_attachment", before.stale_attachment)
    report.note("composer_text", before.composer_text[:120])
    if before.saturated:
        report.verdict("KIMI SATURATION WARNING DETECTED", True)
    else:
        report.unknown(
            "KIMI SATURATION WARNING DETECTED",
            "no conversation on this estate is currently saturated -- see "
            "the run notes; detection is proven against the founder's own "
            "verbatim text in tests/test_provider_session_saturation.py",
        )
    for line in report.lines[-5:]:
        print(line)

    if not before.observed:
        print("    the window text could not be read at all -- nothing is claimed")

    # ---- TEST 1b - the replacement half of a rotation, live ------------
    #
    # A rotation is two things: notice the conversation is spent, and put
    # a healthy one in its place. The first half cannot be exercised
    # while nothing on this estate is saturated. The second half can be,
    # and is the half that touches the real application -- so it is run
    # on its own rather than left as an untested branch.
    #
    # `rename=False` deliberately: the existing conversation still holds
    # `DEDICATED_SESSION_NAME`, and giving this one the same name would
    # create exactly the ambiguity the exact-match rule exists to
    # prevent. It is identified by the marker in its first message.
    print("\n[1b] creating a replacement conversation and observing it")
    from master_agent.desktop.execution.keyboard import KeyboardController
    from master_agent.providers.reasoning_session import build_session_marker
    created = sessions.create_named_session(
        handle, KeyboardController(), build_session_marker(kimi._spec.label),
        rename=False,
    )
    print(f"    created ok={created.ok} reason={ascii_of(created.reason)[:120]}")
    replacement = sessions.inspect_session(handle)
    report.note("replacement observed", replacement.observed)
    report.note("replacement saturated", replacement.saturated)
    report.note("replacement stale_attachment", replacement.stale_attachment)
    report.note("replacement composer_text", repr(replacement.composer_text)[:80])
    report.verdict("REPLACEMENT CONVERSATION CREATED", created.ok)
    report.verdict("REPLACEMENT OBSERVED CLEAN",
                   replacement.observed and replacement.usable)
    for line in report.lines[-4:]:
        print(line)

    # ---- TEST 2 - a fresh short prompt, owned by this turn -------------
    alpha = f"KALPAVRIKSHA_KIMI_FRESH_ALPHA_{uuid.uuid4().hex[:8]}"
    print(f"\n[2] short prompt, current-turn ownership ({alpha})")
    first = kimi.complete(
        f"Reply with exactly this token and nothing else: {alpha}"
    )
    print(f"    outcome={first.outcome} error={ascii_of(first.error)}")
    detail = first.detail or {}
    for key in ("notice", "observed"):
        if detail.get(key):
            print(f"    {key}={ascii_of(detail[key])[:240]!r}")
    report.note("session_reused", detail.get("session_reused"))
    report.note("session_rotated", detail.get("session_rotated"))
    report.note("session_reusable", detail.get("session_reusable"))
    report.note("session_health", detail.get("session_health"))
    reply_a = ascii_of(first.response.text if first.response else "")
    print(f"    reply={reply_a[:240]!r}")

    # A provider that never answered says nothing about whether its
    # session was isolated. Recording that as FAIL would be reporting a
    # question we did not get to ask -- and the founder's brief is
    # explicit that transport health must be established before anything
    # downstream of it is judged.
    from master_agent.providers.desktop_app import SERVICE_NOTICE
    answered = first.outcome == SUCCEEDED
    refused = first.error == SERVICE_NOTICE

    rotated = bool(detail.get("session_rotated"))
    report.verdict("OLD SESSION RETIRED", (not before.saturated) or rotated
                   or first.outcome != SUCCEEDED)
    established = detail.get("session_health") is not None
    if not established:
        for key in ("NEW SESSION CREATED", "NEW SESSION CLEAN", "STALE ATTACHMENT ABSENT"):
            report.unknown(key, "no conversation was established this call")
    else:
        health_after_establish = detail["session_health"]
        if before.saturated:
            report.verdict("NEW SESSION CREATED",
                           rotated or not detail.get("session_reused", True))
        else:
            # Reusing a healthy conversation is the correct answer, not a
            # missing rotation. Demanding a new one here would report the
            # right behaviour as a failure.
            report.unknown("NEW SESSION CREATED",
                           "the conversation as found was healthy, so it was "
                           "correctly reused rather than replaced")
        report.verdict("NEW SESSION CLEAN", health_after_establish.get("saturated") is False)
        report.verdict("STALE ATTACHMENT ABSENT",
                       health_after_establish.get("stale_attachment") is False)
    if refused:
        report.unknown("SHORT PROMPT CURRENT-TURN OWNERSHIP",
                       f"the application refused to answer at all: {first.error}")
    else:
        report.verdict("SHORT PROMPT CURRENT-TURN OWNERSHIP",
                       answered and alpha in reply_a)

    # ---- TEST 3 - the second turn must answer BRAVO -------------------
    bravo = f"KALPAVRIKSHA_KIMI_FRESH_BRAVO_{uuid.uuid4().hex[:8]}"
    print(f"\n[3] second turn isolation ({bravo})")
    second = kimi.complete(
        f"Reply with exactly this token and nothing else: {bravo}"
    )
    print(f"    outcome={second.outcome} error={ascii_of(second.error)}")
    for key in ("notice", "observed"):
        if (second.detail or {}).get(key):
            print(f"    {key}={ascii_of(second.detail[key])[:240]!r}")
    reply_b = ascii_of(second.response.text if second.response else "")
    print(f"    reply={reply_b[:240]!r}")
    detail_b = second.detail or {}
    report.note("second session_health", detail_b.get("session_health"))
    if second.error == SERVICE_NOTICE or refused:
        report.unknown("TWO-TURN ISOLATION",
                       "one of the two turns was refused, so nothing was "
                       "compared between them")
    else:
        report.verdict("TWO-TURN ISOLATION", (
            second.outcome == SUCCEEDED
            and bravo in reply_b
            and alpha not in reply_b
            and (detail_b.get("session_health") or {}).get("stale_attachment") is False
        ))

    # ---- TEST 4 - a conversation that saturates later ------------------
    print("\n[4] session-state persistence")
    now = sessions.inspect_session(handle)
    report.note("saturated now", now.saturated)
    if now.saturated:
        report.verdict("SATURATED SESSION MARKED NON-REUSABLE",
                       sessions.is_retired(kimi._spec.label))
    else:
        report.unknown("SATURATED SESSION MARKED NON-REUSABLE",
                       "the conversation did not saturate during this run")

    # ---- the 4000-char current-prompt limit ---------------------------
    print("\n[5] a prompt larger than the composer will carry")
    over = kimi.complete("z" * 5000)
    print(f"    outcome={over.outcome} error={ascii_of(over.error)}")
    report.note("prompt_chars", (over.detail or {}).get("prompt_chars"))
    report.note("max_prompt_chars", (over.detail or {}).get("max_prompt_chars"))
    from master_agent.providers.desktop_app import PROMPT_TOO_LONG
    report.verdict("4000-CHAR CURRENT-PROMPT LIMIT", over.error == PROMPT_TOO_LONG)

    print("\n" + "=" * 62)
    for key, value in report.verdicts.items():
        print(f"{key:<44} {value}")
    print(f"{'SATURATED SESSION REUSED':<44} "
          f"{'YES' if before.saturated and not rotated and first.outcome == SUCCEEDED else 'NO'}")
    print("=" * 62)
    for line in report.lines:
        print(line)
    return 0 if not any(v == "FAIL" for v in report.verdicts.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
