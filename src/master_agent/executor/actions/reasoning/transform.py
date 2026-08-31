"""Judgement as a Step the Runtime can actually execute.

Three kinds of reasoning already existed here, and none of them was this
one. The Planner reasons to *write* a plan. The Reporter reasons to talk
to the founder. Advisory reasons to answer a question. **Nothing could
reason over evidence a previous Step had just acquired** -- so a mission
could read two documents and could not compare them, could observe ten
pages and could not rank them.

That gap is why a founder's objective ended at `steps: []`: the catalogue
genuinely could not express "understand this", and the Planner is
forbidden to invent a capability it does not have.

## What this deliberately is not

It is not a second AI stack. The prompt goes to the same
`TieredPromptRunner` the Planner uses, through the same Broker, the same
provider records, the same budgets and the same privacy rules. Nothing
about routing is decided here.

It is not code execution, and it is not Hands. It reads what it is given
and returns text. It cannot write a file, open a browser, send anything,
or touch the environment -- those stay separate, explicit, individually
approved Steps. Brain decides; Hands act.

## Why the default is `sensitive`

`context` is normally the output of an earlier Step: a document off the
founder's own disk, a page from their session. Treating that as
unrestricted by default would mean the first mission over a private
document quietly posts it to whichever cloud provider ranked first.

So the default is the careful one. A sensitive request the Broker can
only satisfy with a non-PRIVATE provider becomes a founder approval by
existing rule (`ai_infrastructure/approval.py::approval_needed`), never a
silent send. A plan that knows its material is public may say
`"sensitive": false` and pay less for it -- but it has to say so.

READ_ONLY: nothing in the environment changes.
"""
from __future__ import annotations

from typing import Any

from master_agent.executor.action import Action, ExecutionResult
from master_agent.plugins.base import PermissionCategory, RiskTier

REASONING_TRANSFORM = "transform"

#: A prompt is not a place to discover a context-window limit. Capped
#: here, declared in the result, so a step reasoning over a shortened
#: brief can be seen to have done so.
MAX_CONTEXT_CHARS = 120_000


class ReasoningTransformAction(Action):
    name = REASONING_TRANSFORM
    description = (
        "Reason over supplied evidence and return the result as text: compare "
        "documents, summarise findings, identify gaps, derive search criteria, "
        "or rank observations against a profile. Returns text only -- it never "
        "writes files, opens applications, or changes anything."
    )
    risk_tier = RiskTier.READ_ONLY
    permission_category = PermissionCategory.READ
    expected_result = (
        "A reasoned textual answer to the instruction, derived from the "
        "supplied evidence; nothing in the environment changes."
    )

    def __init__(self, runner: Any = None) -> None:
        #: The same object the Planner is given. Injected, never
        #: constructed here: this Action owns no routing, no provider
        #: list, and no fallback policy.
        self._runner = runner

    def bind_runner(self, runner: Any) -> None:
        """Attach the reasoning runner after construction.

        A composition root builds the ladder *after* it registers its
        Executives -- the ladder needs providers the plugins themselves
        supply. Rather than reach into this object from outside, or invent
        a lazy proxy, the binding is a stated part of the contract.
        """
        self._runner = runner

    def required_parameters(self) -> list[str]:
        return ["instruction"]

    def optional_parameters(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "context",
                "type": "string",
                "description": (
                    "The evidence to reason over. Normally bound from an "
                    "earlier step's output rather than written by hand."
                ),
                "default": "",
            },
            {
                "name": "must_contain",
                "type": "array",
                "description": (
                    "Sections the answer must include, e.g. "
                    "['strengths', 'gaps']. Stated to the reasoner as part "
                    "of the instruction, and checkable afterwards."
                ),
                "default": None,
            },
            {
                "name": "sensitive",
                "type": "boolean",
                "description": (
                    "Whether this evidence is private. True by default. "
                    "Set false only for material that is already public."
                ),
                "default": True,
            },
        ]

    def output_parameters(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "text",
                "type": "string",
                "description": "The reasoned answer, as text a later step may use.",
            },
            {
                "name": "sensitivity",
                "type": "string",
                "description": (
                    "The material classification this transform actually "
                    "ran under: public or private."
                ),
            },
        ]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not (parameters.get("instruction") or "").strip():
            errors.append("missing required parameter: instruction")

        must_contain = parameters.get("must_contain")
        if must_contain is not None and not isinstance(must_contain, (list, tuple)):
            errors.append("'must_contain' must be a list of strings if provided")

        sensitive = parameters.get("sensitive")
        if sensitive is not None and not isinstance(sensitive, bool):
            errors.append("'sensitive' must be a boolean if provided")
        return errors

    def _prompt(self, instruction: str, context: str, must_contain) -> str:
        """The framing follows the evidence, because the discipline does.

        Every prompt used to open with "you are reasoning over evidence
        gathered by earlier steps" and close with "if the evidence does
        not contain something you were asked about, say so plainly rather
        than supplying it from general knowledge" -- whether or not any
        evidence had been supplied.

        That is exactly right when there IS evidence, and it is the whole
        anti-fabrication discipline, so it is preserved below unchanged.

        With no `context` it inverts. Measured live, on the founder
        objective "think of three short names for a gardening notes app":
        the model obeyed, correctly, and returned

            The evidence provided does not contain names for a gardening
            notes app.

        which was then verified, bound and written to their Desktop. The
        machinery was flawless; the question was malformed. Nothing had
        been gathered, nothing was being reasoned over, and the founder
        had asked for something to be originated -- so the model was told
        to refuse the only thing it had been asked to do.

        So the evidence framing is stated when evidence exists and not
        when it does not. This weakens nothing: a Transform carrying
        context is held to the same rule it always was, word for word.
        """
        grounded = bool(context)
        parts = [
            "You are reasoning over evidence that was gathered by earlier "
            "steps of a task. Use only what the evidence actually says."
            if grounded else
            "You are carrying out one step of a task. No evidence was "
            "gathered for it: answer from your own general knowledge.",
            "",
            f"Instruction:\n{instruction}",
        ]
        if must_contain:
            wanted = ", ".join(str(item) for item in must_contain)
            parts += ["", f"Your answer must cover: {wanted}."]
        if grounded:
            parts += ["", "Evidence:", context]
        parts += [
            "",
            # The same discipline the Planner is held to, stated where the
            # reasoning happens: an answer that invents a fact is worse
            # than one that reports the absence.
            "If the evidence does not contain something you were asked "
            "about, say so plainly rather than supplying it from general "
            "knowledge. Answer with the result only."
            if grounded else
            "Answer with the result only.",
        ]
        return "\n".join(parts)

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        if self._runner is None:
            return ExecutionResult(
                success=False,
                errors=[
                    "no reasoning runner is wired: this capability cannot run "
                    "without the AI infrastructure it delegates to"
                ],
            )

        instruction = parameters["instruction"].strip()
        context = parameters.get("context") or ""
        if not isinstance(context, str):
            context = str(context)
        truncated = len(context) > MAX_CONTEXT_CHARS
        if truncated:
            context = context[:MAX_CONTEXT_CHARS]

        must_contain = parameters.get("must_contain") or ()
        sensitive = parameters.get("sensitive")
        if sensitive is None:
            sensitive = True

        # Built here rather than imported from the Planner: this is the
        # public request vocabulary, and reusing the *type* is the reuse
        # that matters, not reusing the Planner's own call site.
        from master_agent.ai_infrastructure.budgeted_request import (
            BudgetedSelectionRequest,
        )
        from master_agent.ai_infrastructure.workload import (
            DEFAULT_CLASS,
            INTERACTIVE,
        )
        from master_agent.plugins.model_router import REASONING

        prompt = self._prompt(instruction, context, must_contain)
        request = BudgetedSelectionRequest(
            capability=REASONING,
            sensitive=bool(sensitive),
            requester="reasoning_transform",
            # **What kind of work this actually is.**
            #
            # `context` is an earlier Step's output -- a document off the
            # founder's disk, a page from their session. A Transform that
            # has one is analysis: it may be long, and the founder is not
            # sitting watching it. A Transform WITHOUT one is a
            # conversational turn, which is what `interactive` means in
            # `workload.py` ("a conversational turn is short"), and the
            # founder is waiting on it.
            #
            # The distinction matters because the workload class is what
            # `broker/policy.py::policy_for_request_class()` reads to
            # decide an interactive turn under `fast_free` -- ranking free
            # providers by latency instead of walking locality tiers.
            # Declared from the same structural fact the sensitivity
            # decision already uses, never from the wording of the
            # instruction and never from which provider is installed.
            request_class=INTERACTIVE if not context else DEFAULT_CLASS,
            prompt=prompt,
        )

        try:
            outcome = self._runner.run(prompt, request)
        except Exception as exc:  # noqa: BLE001 - a provider failure is data
            return ExecutionResult(
                success=False, errors=[f"reasoning failed: {exc}"]
            )

        if outcome is None or not getattr(outcome, "ok", False):
            detail = (
                getattr(outcome, "error", None)
                or getattr(outcome, "reason", None)
                or "no reasoning provider produced an answer"
            )
            return ExecutionResult(success=False, errors=[str(detail)])

        text = (
            getattr(outcome, "text", None)
            or getattr(outcome, "output", None)
            or ""
        )
        if not isinstance(text, str):
            text = str(text)
        if not text.strip():
            # An empty answer is a failure, not a result. A later step
            # binding to it would carry the emptiness forward silently.
            return ExecutionResult(
                success=False,
                errors=["the reasoning provider returned an empty answer"],
            )

        missing = [
            str(item)
            for item in must_contain
            if str(item).lower() not in text.lower()
        ]

        return ExecutionResult(
            success=True,
            output={
                "text": text,
                # Action-owned metadata, never model output. A later
                # reasoning step reads it only through matched Evidence,
                # so public research remains public through synthesis and
                # private material can never be laundered by the model.
                "sensitivity": "private" if bool(sensitive) else "public",
                # Mechanical facts about the answer -- what Verification
                # can honestly check. None of this says the judgement is
                # correct, and nothing here should be read as saying so.
                "missing_sections": missing,
                "context_truncated": truncated,
            },
        )
