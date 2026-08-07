"""Test support for Mission Brief 036.

The runner double returns a **real `PromptOutcome`** and builds its
`Evidence` by calling MB035's **real `verify_text`** with whatever
expectation the Planner passed in. Only the provider is invented. That
matters: it means these tests exercise the actual verification path, so a
test can only pass a plan the shipped verifier would also have passed.
"""
from __future__ import annotations

import json
from typing import Any

from master_agent.ai_infrastructure.execution import PromptOutcome
from master_agent.ai_infrastructure.refusal import NO_PROVIDER, BrokerRefusal
from master_agent.ai_infrastructure.text_verifier import verify_text
from master_agent.planner.catalogue import CapabilityOption

# ---- a small, real-shaped catalogue --------------------------------------

CREATE = CapabilityOption(
    "Filesystem.CreateFolder", "Create a folder at a path.", "reversible"
)
WRITE = CapabilityOption(
    "Filesystem.WriteFile", "Write text to a file.", "reversible"
)
DELETE = CapabilityOption(
    "Filesystem.DeleteFolder", "Delete a folder and its contents.", "irreversible"
)
CATALOGUE = (CREATE, WRITE, DELETE)


# ---- plan documents ------------------------------------------------------


def success(description: str = "the step reports what it did", **overrides: Any) -> dict:
    document: dict[str, Any] = {"description": description}
    document.update(overrides)
    return document


def step(
    step_id: str,
    capability: str = CREATE.name,
    payload: dict | None = None,
    depends_on: list | None = None,
    success_doc: Any = ...,
) -> dict:
    """One step document. `success_doc=None` omits the success object,
    which is how the missing-expectation path is exercised."""
    document: dict[str, Any] = {
        "id": step_id,
        "capability": capability,
        "payload": payload if payload is not None else {"path": f"/tmp/{step_id}"},
        "depends_on": depends_on if depends_on is not None else [],
    }
    if success_doc is ...:
        document["success"] = success()
    elif success_doc is not None:
        document["success"] = success_doc
    return document


def document(*steps: dict) -> dict:
    return {"steps": list(steps)}


def plan_text(*steps: dict) -> str:
    return json.dumps(document(*steps))


def fenced(text: str, info: str = "json") -> str:
    return f"```{info}\n{text}\n```"


# ---- the runner double ---------------------------------------------------


class StubRunner:
    """Satisfies the Planner's one-method `runner` port.

    A single reply repeats forever; several are consumed one per call.
    Every call is recorded, so a test can assert on the prompt the Planner
    actually sent and on the expectation it stated.
    """

    def __init__(self, *replies: Any, with_evidence: bool = True) -> None:
        self._replies = list(replies) or [plan_text(step("step_1"))]
        self.calls: list[dict[str, Any]] = []
        self._with_evidence = with_evidence

    def run(
        self,
        prompt: str,
        request: Any,
        context: dict | None = None,
        verified: bool = False,
        use_cache: bool = True,
        expected: Any = None,
    ) -> PromptOutcome:
        self.calls.append(
            {
                "prompt": prompt,
                "request": request,
                "context": context,
                "use_cache": use_cache,
                "expected": expected,
            }
        )
        reply = (
            self._replies.pop(0) if len(self._replies) > 1 else self._replies[0]
        )

        if isinstance(reply, BrokerRefusal):
            return PromptOutcome(refusal=reply, entry_id=7)
        if isinstance(reply, PromptOutcome):
            return reply

        evidence = None
        if expected is not None and self._with_evidence:
            evidence = verify_text(reply, expected, worker="planner")
        return PromptOutcome(
            ok=True,
            text=reply,
            provider_id="alpha-local",
            entry_id=7,
            evidence=evidence,
        )

    @property
    def prompt(self) -> str:
        return self.calls[-1]["prompt"]


def refused(reason: str = "nothing available clears the quality floor") -> BrokerRefusal:
    return BrokerRefusal(kind=NO_PROVIDER, reason=reason, capability="reasoning")
