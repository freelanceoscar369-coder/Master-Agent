"""Diagnostic: what does the obligation audit actually get back?

A live refusal said `the obligation audit was not a JSON object`, while
the broker recorded the reasoning call as SUCCEEDED. So a reply arrived
and it was not parseable. This prints the real replies for the real
objective, through the real composition, changing no product behaviour.

It wraps `_reasoned_json` to observe its input and output and then calls
the same method through. Nothing here decides anything, and the wrapper
is removed before exit.

    python _obligation_audit_reply_dump.py
"""
from __future__ import annotations

import logging
import os
import sys

logging.basicConfig(level=logging.WARNING, format="[%(levelname)s] %(message)s")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, "D:/MasterAgent")
sys.path.insert(0, "D:/MasterAgent/src")

OBJECTIVE = (
    "Ensure a folder Kalpavriksha_Usability_Simple exists on my Desktop. "
    "Inside it ensure result.txt contains exactly: Kalpavriksha simple "
    "usability test passed. Verify folder/file/content, then report."
)


def ascii_of(text):
    return (text or "").encode("ascii", "replace").decode("ascii")


def main() -> int:
    import kalpavriksha_desktop as fe
    from master_agent.brain import intent as intent_mod

    pipeline = fe._build_mission_pipeline()
    if pipeline is None:
        print("could not assemble the pipeline on this machine")
        return 2
    mission_service = pipeline[0]
    layer = mission_service.intent_layer

    # Also trace the reconstruction itself: a reply that arrives as a
    # fragment is either a fragment on the page or a fragment we made.
    # Only the rows the sorter was handed can tell those apart.
    from master_agent.desktop.execution.uia_control import UiaAutomationBridge

    order_original = UiaAutomationBridge._in_reading_order

    def order_traced(kept):
        rows = list(kept)
        if rows:
            print(f"  [reading order: {len(rows)} row(s), document order]", flush=True)
            for top, left, text in rows:
                flat = ascii_of(" ".join(text.split()))
                print(f"    top={top:>6} left={left:>6} len={len(text):>5} | {flat[:90]}",
                      flush=True)
        else:
            print("  [reading order: 0 rows -- falling back to single region]",
                  flush=True)
        return order_original(rows)

    UiaAutomationBridge._in_reading_order = staticmethod(order_traced)

    original = type(layer)._reasoned_json
    calls = {"n": 0}

    def traced(self, prompt: str, *, requester: str):
        calls["n"] += 1
        n = calls["n"]
        print(f"\n===== call {n}: {requester} =====", flush=True)
        print(f"  prompt chars : {len(prompt)}", flush=True)
        # Reproduce exactly what the product does, then look at it.
        from master_agent.ai_infrastructure.budgeted_request import (
            BudgetedSelectionRequest,
        )
        from master_agent.ai_infrastructure.workload import INTERACTIVE
        from master_agent.plugins.model_router import RoutingContext, SelectionRequest

        context = RoutingContext(
            is_online=True, requires_strong_reasoning=False,
            capability=intent_mod.REASONING_CAPABILITY, requester=requester,
        )
        request = BudgetedSelectionRequest(
            **vars(SelectionRequest.from_context(context)),
            request_class=INTERACTIVE, prompt=prompt,
        )
        try:
            outcome = self._reasoner.run(prompt, request)
        except Exception as exc:  # noqa: BLE001
            print(f"  RAISED: {type(exc).__name__}: {exc}", flush=True)
            return None
        ok = getattr(outcome, "ok", False)
        text = getattr(outcome, "text", "") or ""
        print(f"  ok={ok}  reply chars={len(text)}", flush=True)
        print(f"  provider={getattr(outcome, 'provider_id', None)}", flush=True)
        print("  ---- reply, first 1200 chars ----", flush=True)
        print("  " + ascii_of(text)[:1200].replace("\n", "\n  "), flush=True)
        print("  ---- reply, last 400 chars ----", flush=True)
        print("  " + ascii_of(text)[-400:].replace("\n", "\n  "), flush=True)
        parsed = intent_mod._parsed_json(text)
        print(f"  _parsed_json -> {type(parsed).__name__ if parsed is not None else 'None'}",
              flush=True)
        if parsed is None and text:
            body = text.strip()
            print(f"  has open brace: {'{' in body}   has close brace: {'}' in body}",
                  flush=True)
            print(f"  fenced: {'```' in body}", flush=True)
        return parsed

    type(layer)._reasoned_json = traced
    try:
        print("submitting the real objective through the real Intent Layer...")
        outcome = mission_service.start(OBJECTIVE)
        print("\n===== OUTCOME =====")
        print("  accepted:", getattr(outcome, "accepted", None))
        refusal = getattr(outcome, "refusal", None)
        if refusal is not None:
            print("  code   :", getattr(refusal, "code", None))
            print("  reason :", ascii_of(getattr(refusal, "reason", "")))
            print("  detail :", ascii_of(getattr(refusal, "detail", "")))
        print(f"  reasoning calls made: {calls['n']}")
    finally:
        type(layer)._reasoned_json = original
        UiaAutomationBridge._in_reading_order = order_original
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
