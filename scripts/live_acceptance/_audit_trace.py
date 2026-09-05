"""Run the real Founder Edition app with the reply reconstruction traced.

MODERATE keeps refusing with "the obligation audit was not a JSON
object". Everything up to that point reports success: one committed
provider, chat mode verified, the reasoning conversation reused, the
call returning `succeeded`. So the question is narrow -- what text did
reconstruction actually hand back, and where did it stop reading?

This changes no product behaviour. It wraps `find_new_response()`,
writes what went in and what came out to a file, and calls the real
method through. The app runs exactly as it does for the founder.

    python _audit_trace.py            # then type the objective as usual

Trace file: %TEMP%/kalpavriksha_reply_trace.txt
"""
from __future__ import annotations

import os
import sys
import tempfile
import time

sys.path.insert(0, "D:/MasterAgent")
sys.path.insert(0, "D:/MasterAgent/src")
os.environ.setdefault("KALPAVRIKSHA_DISABLE_MIC", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

TRACE = os.path.join(tempfile.gettempdir(), "kalpavriksha_reply_trace.txt")


def _ascii(text):
    return (text or "").encode("ascii", "replace").decode("ascii")


def main() -> int:
    from master_agent.desktop.execution.uia_control import UiaAutomationBridge

    open(TRACE, "w", encoding="utf-8").close()
    original = UiaAutomationBridge.find_new_response
    # Only the LAST reading of each turn matters -- the settled one --
    # so each call overwrites its own turn's entry rather than appending
    # twenty polls of a half-drawn answer.
    turns: dict[str, dict] = {}

    def traced(self, window_handle, baseline, exclude_text="", min_height=8,
               turn=None, turn_marker=""):
        result = original(self, window_handle, baseline, exclude_text,
                          min_height, turn, turn_marker)
        if result:
            turns[turn_marker or "?"] = {
                "at": time.strftime("%H:%M:%S"),
                "marker": turn_marker,
                "prompt_chars": len(exclude_text or ""),
                "prompt_tail": (exclude_text or "")[-200:],
                "reply_chars": len(result),
                "reply": result,
            }
            with open(TRACE, "w", encoding="utf-8") as fh:
                for entry in turns.values():
                    fh.write("=" * 70 + "\n")
                    fh.write(f"{entry['at']}  {_ascii(entry['marker'])}\n")
                    fh.write(f"prompt {entry['prompt_chars']} chars, "
                             f"tail: {_ascii(entry['prompt_tail'])}\n")
                    fh.write(f"reply  {entry['reply_chars']} chars\n")
                    fh.write("-" * 70 + "\n")
                    fh.write(_ascii(entry["reply"]) + "\n")
        return result

    UiaAutomationBridge.find_new_response = traced

    # And the boundary itself. `:[]` came back for a 6,471-character
    # audit prompt, which is either "the answer was never in the tree" or
    # "the answer was in the tree and read as our own question". Those
    # need opposite repairs and only the item list tells them apart.
    inner = UiaAutomationBridge._lines_after_the_prompt
    detail = os.path.join(tempfile.gettempdir(), "kalpavriksha_boundary.txt")
    open(detail, "w", encoding="utf-8").close()

    @staticmethod
    def traced_boundary(regions, exclude_norm, on_the_composer):
        lines = inner(regions, exclude_norm, on_the_composer)
        if len(exclude_norm or "") < 5000:
            return lines          # only the big audit turn is in question
        items = [text for _key, (_e, text) in regions.items()
                 if text and text.strip()]
        with open(detail, "w", encoding="utf-8") as fh:
            fh.write(f"prompt {len(exclude_norm)} chars, "
                     f"{len(items)} items, {len(lines)} line(s) kept\n")
            spent = 0
            for index, text in enumerate(items):
                from master_agent.desktop.execution.uia_control import (
                    _normalize_whitespace)
                norm = _normalize_whitespace(text)
                echoed = exclude_norm.find(norm, spent)
                mark = "ECHO " if echoed >= 0 else "reply"
                if echoed >= 0:
                    spent = echoed + len(norm)
                fh.write(f"{index:4d} {mark} spent={spent:6d} "
                         f"len={len(text):5d} | {_ascii(' '.join(text.split()))[:120]}\n")
        return lines

    UiaAutomationBridge._lines_after_the_prompt = traced_boundary

    import kalpavriksha_desktop
    return kalpavriksha_desktop.main([])


if __name__ == "__main__":
    raise SystemExit(main())
