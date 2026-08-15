"""The Planner (Mission Brief 036).

An objective goes in; a `MissionPlan` whose every Step states what it
expects comes out, or a refusal explaining why there is none.

```
    Intent ─> catalogue ─> prompt ─┐
                                   v
             ExpectedOutcome ─> PromptExecutor ─> Broker ─> provider
                                   │
                        Evidence ──┴── observation["json"]
                                   │
                              validate() ─> MissionPlan
```

## What this closes

`ExpectedOutcome`'s docstring in the frozen `verification/` package has
said since ADR-0011 that a Planner is what attaches one to a Step. MB035
built the checker and inherited a Prompt Cache and a Prompt Library that
fill only for callers who state an expectation. This is the caller that
always states one -- Constitution §3.2 stops being a promise and becomes
a validation gate that refuses a plan without one.

## What it is not

It is not wired into `cli.py`. The regex `parse_intent()`/`build_plan()`
stand-in still runs the conversational path, and `test_cli_session.py` is
a hundred-assertion regression contract that deserves a brief of its own
-- the same MB031-then-MB032 rhythm the Broker got: build the engine,
prove it, wire it next.

## Five ways it fails, all closed

Nothing is registered; the Broker refused; the provider failed; the reply
was not a plan document; the plan was not a usable plan. Every one
returns a `PlanRefusal` with a code and a sentence, and **none of them
falls back to a plan of its own**. A fallback plan is a plan nobody
verified, produced at exactly the moment the system has just demonstrated
it cannot plan -- the same argument MB032 used to refuse a fallback
provider, for the same reason.
"""
from __future__ import annotations

from typing import Any

from master_agent.ai_infrastructure.budgeted_request import BudgetedSelectionRequest
from master_agent.ai_infrastructure.text_verifier import passed
from master_agent.ai_infrastructure.workload import PLANNING as PLANNING_CLASS
from master_agent.planner.catalogue import (
    CapabilityOption,
    catalogue_from,
    catalogue_from_index,
    names,
)
from master_agent.planner.direct import direct_plan
from master_agent.planner.modes import AI_MODE, LOCAL, resolve_mode
from master_agent.planner.parsing import validate
from master_agent.planner.plan import (
    LOCAL_ONLY,
    BROKER_REFUSED,
    NO_CAPABILITIES,
    NOT_JSON,
    PROVIDER_FAILED,
    UNVERIFIED,
    Intent,
    MissionPlan,
    PlanOutcome,
    PlanRefusal,
    Step,
)
from master_agent.planner.prompting import build_prompt, plan_expectation
from master_agent.plugins.model_router import RoutingContext, SelectionRequest

#: Re-exported so `from master_agent.planner.planner import MissionPlan,
#: Step` keeps working for the Orchestrator, `cli.py` and two test
#: modules. The definitions moved to `plan.py`; nothing that consumed them
#: changed.
__all__ = ["Intent", "MissionPlan", "Planner", "Step"]

#: The AI Capability a plan needs. Named here rather than passed in
#: because it is a fact about the work -- decomposing an objective is
#: reasoning -- and never a preference about who does it.
PLANNING_CAPABILITY = "reasoning"

REQUESTER = "planner"


class Planner:
    """Turns an `Intent` into a `MissionPlan`.

    `runner` needs one method -- `run(prompt, request, expected=...)` --
    so `PromptExecutor` satisfies it and this class depends on no
    concrete executor, the same port shape MB033 used for its providers.
    Going through the executor rather than a provider is not a
    convenience: it is what puts every plan through the Broker's decision,
    the Approval Queue, the ledger and the token economy, so a plan costs
    what it costs on the same record as everything else.

    `catalogue` is either a fixed tuple of `CapabilityOption` or anything
    with `.all()` (Mission Control's `CapabilityRegistry`), read on every
    call so a plan made after an Executive deregisters cannot name a
    capability that has just gone away.
    """

    def __init__(
        self,
        runner: Any,
        catalogue: Any = (),
        *,
        requester: str = REQUESTER,
        requires_strong_reasoning: bool = False,
        offline: bool = False,
        mode: Any = None,
    ) -> None:
        self._runner = runner
        self._catalogue = catalogue
        self._requester = requester
        # A knob, not a hardcoded `True`. Planning benefits from a
        # stronger model, but *how good a plan has to be* is a quality
        # floor, and ADR-0017 gives floors to the founder's policy rather
        # than to whichever component happens to be asking. Setting this
        # here would be the Planner deciding the founder should pay.
        self._requires_strong_reasoning = requires_strong_reasoning
        self._offline = offline
        # The founder's LOCAL / AI MODE / BOTH switch, read at plan time
        # rather than captured at construction -- the founder flips it
        # mid-session and this object is built once at boot. A callable or
        # a plain string; `None` means nobody wired the switch and the
        # historical default (BOTH) applies.
        self._mode = mode

    # ---- planning --------------------------------------------------------

    def mode(self) -> str:
        """The founder's current LOCAL / AI MODE / BOTH choice."""
        return resolve_mode(self._mode)

    def options(self) -> tuple[CapabilityOption, ...]:
        """What may appear in a plan right now."""
        catalogue = self._catalogue
        # MB039: an index publishes argument names, a registry publishes
        # only a sentence. Both are supported and the index is preferred
        # where one exists -- "needs one attribute", the same port shape
        # MB033 used for providers.
        if hasattr(catalogue, "entries"):
            return catalogue_from_index(catalogue)
        if hasattr(catalogue, "all"):
            return catalogue_from(catalogue)
        return tuple(catalogue)

    def plan(
        self, intent: Intent, *, task_id: str = "", objective_id: str | None = None
    ) -> PlanOutcome:
        """Plan, or say why not. Never raises, and never returns a partial
        plan: half a plan executed is worse than none."""
        options = self.options()
        if not options:
            return PlanOutcome(
                refusal=PlanRefusal(
                    code=NO_CAPABILITIES,
                    reason="no plan: nothing is registered to plan with",
                    detail=(
                        "The capability catalogue is empty. Asking a provider "
                        "to plan against an empty list would produce steps "
                        "naming capabilities that do not exist, so nothing is "
                        "asked."
                    ),
                )
            )

        # ---- deterministic first -------------------------------------
        #
        # BOTH is local-first, and LOCAL is local-only. Both start here,
        # and so does AI MODE's absence of a reason to: a capability the
        # Intent Layer already named and the catalogue already publishes
        # needs no provider to rediscover. A founder who explicitly chose
        # AI MODE is asking for reasoning, so that mode alone skips it.
        mode = self.mode()
        if mode != AI_MODE:
            plan = direct_plan(intent, options)
            if plan is not None:
                return PlanOutcome(plan=plan)

        if mode == LOCAL:
            # LOCAL means local capabilities only. Reaching a provider here
            # would be the one thing the founder switched the mode off to
            # prevent, so this refuses instead -- honestly, naming what is
            # registered, the same way NO_CAPABILITIES does.
            return PlanOutcome(
                refusal=PlanRefusal(
                    code=LOCAL_ONLY,
                    reason=(
                        "no plan: LOCAL mode uses only your computer's own "
                        "capabilities, and none of them completes this on its own"
                    ),
                    detail=(
                        "Switch to BOTH to let reasoning help when local "
                        "capabilities are not enough."
                    ),
                    known_capabilities=tuple(option.name for option in options),
                )
            )

        prompt = build_prompt(intent, options)
        context = RoutingContext(
            is_online=not self._offline,
            is_sensitive=intent.is_sensitive,
            requires_strong_reasoning=self._requires_strong_reasoning,
            capability=PLANNING_CAPABILITY,
            task_id=task_id,
            objective_id=objective_id,
            requester=self._requester,
        )
        # MB038. A planning prompt carries the whole capability catalogue,
        # so it is enormous-in and moderate-out -- a shape no single
        # timeout describes, and the one that reported a healthy provider
        # as failed twice (MB036, MB037). Saying so is all the Planner
        # does about it: the class and the prompt are *facts about the
        # work*, and the Broker derives the deadlines from them.
        request = BudgetedSelectionRequest(
            **vars(SelectionRequest.from_context(context)),
            request_class=PLANNING_CLASS,
            prompt=prompt,
        )

        # The expectation is stated here, before the request is sent, and
        # it is the executor that applies it -- so the same verdict that
        # decides whether this plan is usable also decides whether it is
        # worth caching. One judgement, one artefact.
        outcome = self._runner.run(prompt, request, expected=plan_expectation())

        refusal = self._rejected(outcome)
        if refusal is not None:
            return PlanOutcome(
                refusal=refusal,
                evidence=outcome.evidence,
                entry_id=outcome.entry_id,
                provider_id=outcome.provider_id,
                raw=outcome.text,
            )

        document = outcome.evidence.observation.get("json")
        plan, invalid = validate(document, options, objective=intent.goal)
        return PlanOutcome(
            plan=plan,
            refusal=invalid,
            evidence=outcome.evidence,
            entry_id=outcome.entry_id,
            provider_id=outcome.provider_id,
            raw=outcome.text,
        )

    # ---- the ways it stops -----------------------------------------------

    def _rejected(self, outcome: Any) -> PlanRefusal | None:
        """Everything that stops a reply from becoming a plan document.

        Ordered as the failures happen, so the reason a founder reads is
        the *first* thing that went wrong rather than a downstream symptom
        of it.
        """
        if outcome.refused:
            # The Broker declined and said why. Repeating its sentence in
            # planning vocabulary would be a second opinion about a
            # decision this class did not make.
            return PlanRefusal(
                code=BROKER_REFUSED,
                reason=f"no plan: {outcome.refusal.reason}",
                detail="The Broker declined before anything was asked to plan.",
            )

        if not outcome.ok:
            # The *why* goes in the sentence, not only in the detail. Found
            # by running MB037 live: a founder saw "the provider could not
            # answer" and had nowhere to go, while `no answer within 540s`
            # -- the one fact that tells them what to change -- sat in a
            # field the console does not render. MB033's discipline: a
            # missing model is reported *with* the models that are
            # installed, in the line the founder actually reads.
            because = outcome.reason
            return PlanRefusal(
                code=PROVIDER_FAILED,
                reason=(
                    f"no plan: the provider could not answer ({because})"
                    if because
                    else "no plan: the provider could not answer"
                ),
                detail=because,
            )

        if outcome.evidence is None:
            # Fail closed. An answer nobody checked is not a plan, and
            # accepting one here would quietly reintroduce the gap MB035
            # exists to close.
            return PlanRefusal(
                code=UNVERIFIED,
                reason="no plan: the reply arrived with no verification record",
                detail=(
                    "The Planner states an expectation on every request, so a "
                    "reply with no Evidence means the execution path did not "
                    "apply it."
                ),
            )

        if not passed(outcome.evidence):
            return PlanRefusal(
                code=NOT_JSON,
                reason="no plan: the reply was not a plan document",
                detail=(
                    f"Verification returned {outcome.evidence.verdict.value}; "
                    "a plan must be JSON with a `steps` list."
                ),
            )

        return None

    # ---- reporting -------------------------------------------------------

    def catalogue_names(self) -> tuple[str, ...]:
        """What a founder would see if they asked what it can plan with."""
        return names(self.options())
