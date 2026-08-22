"""ReasoningGateway -- pairs the Reasoning Executive with `TextVerifier`.

## The seam this closes

`Reasoning.Transform` produces text. Another Step then wants to use it:

    Reasoning.Transform.text  ->  Filesystem.WriteFile.content

`runtime/input_resolution.py` will only resolve that binding from a
source that carries canonical Evidence whose verdict is `matched` and
whose *observation* holds the field. That rule is the whole reason a
produced value cannot be quietly replaced by a predicted one, and it is
not being relaxed here.

The Reasoning Executive was registered through the generic
`PluginGateway`, whose `verify()` returns `None` by contract -- honest,
because the `Plugin` protocol has no verification surface. The
consequence, measured live: a Reasoning step executed, produced real
text, and no Evidence existed for it, so every binding out of it failed
and the objective could not run. Nothing was broken; the two halves were
simply never joined.

`PluginGateway`'s own docstring names the sanctioned join: *an Executive
with a Verifier supplies a gateway that pairs the two*. That is all this
is, and it is the same shape `FilesystemGateway` already has.

## Why measuring the produced text is not "verifying from the result"

`ExecutiveGateway.verify()` says Evidence must come from re-observing
reality, never from the `invoke()` return -- that distinction is what
ADR-0011 exists to keep.

For a disk you stat the path again. For a page you read the DOM again.
For generated text there is no such elsewhere, and MB035 already faced
this and wrote down its reading in `text_verifier.py`: *the answer is the
artefact*. The observation is re-derived from that artefact by
deterministic measurement -- length, word count, line count, whether it
parses as JSON -- every time it is asked for, and the provider is never
consulted about whether it did well.

So what is refused is intact. This never reads the plugin's own success
flag, never trusts a claim, and never lets the producer grade itself. The
verdict is arithmetic over an `ExpectedOutcome` the Planner stated before
the Step ran, which is the only kind of verdict that can fail.

What it does need is the artefact, and `verify()` is not handed it -- the
Runtime passes the *payload*, since for a disk or a page the payload is
where the target is named. So the text is carried from `invoke()` to the
`verify()` that follows it, keyed by the payload it came from, and a
mismatch produces no Evidence rather than Evidence about the wrong
answer.
"""
from __future__ import annotations

import json
from typing import Any

from master_agent.runtime.gateway import GatewayResult
from master_agent.verification.evidence import Evidence, ExpectedOutcome

#: The observation field a bound value is read from. `observe()` in
#: `text_verifier` publishes it; `Filesystem.WriteFile.content` binds to
#: it. Named once here so the two ends cannot drift apart silently.
TEXT_FIELD = "text"


def _payload_key(capability: str, payload: dict[str, Any]) -> str:
    """A stable identity for "the call that produced this text".

    Ties one `verify()` to the `invoke()` it belongs to. Sorted keys, so
    two dicts that differ only in insertion order are the same call.
    """
    try:
        body = json.dumps(payload, sort_keys=True, default=str)
    except Exception:  # noqa: BLE001 - identity is best-effort, never fatal
        body = repr(sorted(payload.items(), key=lambda kv: str(kv[0])))
    return f"{capability}|{body}"


class ReasoningGateway:
    """Pairs the Reasoning plugin with `TextVerifier`."""

    def __init__(self, plugin: Any, grant_permission: Any = None) -> None:
        self._plugin = plugin
        self._grant_permission = grant_permission
        #: The artefact produced by the most recent invocation, and the
        #: call it belongs to. One entry: the Runtime verifies a Step
        #: immediately after executing it.
        self._produced: tuple[str, str] | None = None

    # ---- execution ---------------------------------------------------

    def invoke(self, capability: str, payload: dict[str, Any]) -> GatewayResult:
        if self._grant_permission is not None:
            self._grant_permission(capability)

        self._produced = None
        result = self._plugin.invoke(capability, payload)
        if not result.success:
            return GatewayResult(
                success=False, errors=[result.error or "unknown plugin failure"]
            )

        output = result.output
        text = output.get(TEXT_FIELD) if isinstance(output, dict) else None
        if isinstance(text, str):
            self._produced = (_payload_key(capability, payload), text)

        return GatewayResult(success=True, output=output)

    # ---- verification ------------------------------------------------

    def verify(
        self,
        capability: str,
        payload: dict[str, Any],
        expected: ExpectedOutcome,
    ) -> Evidence | None:
        """Evidence about the text this capability just produced, or None.

        None whenever the artefact under test cannot be identified with
        certainty -- a capability that produced no text, or a `verify()`
        that does not belong to the `invoke()` still held here. The
        Runtime records "no Evidence" for that, which is the truthful
        outcome; Evidence about some *other* answer would not be.
        """
        if self._produced is None:
            return None
        key, text = self._produced
        if key != _payload_key(capability, payload):
            return None

        from master_agent.ai_infrastructure.text_verifier import verify_text

        return verify_text(text, expected)
