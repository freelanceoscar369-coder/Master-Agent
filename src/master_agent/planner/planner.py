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
from master_agent.planner.modes import AI_MODE, BOTH, LOCAL, resolve_mode
from master_agent.planner.parsing import validate
from master_agent.planner.plan import (
    LOCAL_ONLY,
    BROKER_REFUSED,
    NO_CAPABILITIES,
    NO_STEPS,
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
        # Tried under EVERY mode, including AI. A founder who selected AI
        # is expressing a preference about reasoning, not forbidding their
        # own machine -- and an objective that needs Hands needs Hands
        # whatever the preference. So when a registered local capability
        # already settles it, that is what runs, and the mission's
        # effective mode is BOTH: the selected mode broadened by what the
        # objective actually requires (ADR-0024's separation of what the
        # founder means from what is executable, applied to resources).
        #
        # This is the AI -> BOTH transition, and it is a transition to
        # LOCAL EXECUTION, never "ask a provider how to create a folder".
        mode = self.mode()
        plan = direct_plan(intent, options)
        if plan is not None:
            return PlanOutcome(
                plan=plan,
                selected_mode=mode,
                effective_mode=BOTH if mode == AI_MODE else mode,
                mode_reason=(
                    f"local execution required: {plan.steps[0].capability}"
                    if mode == AI_MODE else ""
                ),
            )

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
                ),
                selected_mode=mode,
                effective_mode=LOCAL,
            )

        prompt = build_prompt(intent, options)
        context = self._context(intent, task_id=task_id, objective_id=objective_id)
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
        # Read straight off the runner rather than re-deriving: the ladder
        # is the only thing that knows which tiers it walked, and it has
        # always kept the record. Metadata only -- no prompt, no response.
        attempts = _attempt_trail(self._runner)

        refusal = self._rejected(outcome)
        if refusal is not None:
            return PlanOutcome(
                refusal=refusal,
                attempts=attempts,
                selected_mode=mode,
                effective_mode=mode,
                evidence=outcome.evidence,
                entry_id=outcome.entry_id,
                provider_id=outcome.provider_id,
                raw=outcome.text,
            )

        requirements = getattr(intent, "requirements", ()) or ()
        document = outcome.evidence.observation.get("json")
        plan, invalid = validate(
            document, options, objective=intent.goal,
            requirements=requirements,
        )

        # `no_steps` is not a malformed plan -- it is the model's honest
        # answer that the catalogue cannot reach this objective, and rule
        # 6 exists to give that answer a shape it can express. Re-asking
        # pressures it to invent one, which is exactly the fabrication
        # this Planner refuses; and for a blank objective there is
        # nothing to correct toward at all. A guard caught this: a blank
        # objective must cost exactly one provider call.
        repairable = (
            invalid is not None
            and plan is None
            and getattr(invalid, "code", "") != NO_STEPS
            and intent.goal.strip()
        )
        if repairable:
            # ONE correction attempt, with the errors we already have.
            #
            # `validate()` knows precisely what was wrong -- which step,
            # which argument, which missing dependency. Discarding that
            # and reporting "I couldn't plan that just now" spends a
            # provider call, teaches the model nothing, and makes the
            # founder the retry button for a defect the system already
            # diagnosed.
            #
            # Bounded at one, deliberately. A model that cannot produce a
            # valid plan given the exact error twice is not going to on
            # the third try, and each attempt is time a founder waits.
            # The same catalogue and the same objective are reused: the
            # capability set cannot change inside one `plan()` call, and
            # re-deriving it would invite a different plan for a
            # different reason.
            corrected = self._correct(
                intent, options, outcome, invalid, mode, attempts
            )
            if corrected is not None:
                return corrected

        return PlanOutcome(
            plan=plan,
            refusal=invalid,
            attempts=attempts,
            selected_mode=mode,
            effective_mode=mode,
            evidence=outcome.evidence,
            entry_id=outcome.entry_id,
            provider_id=outcome.provider_id,
            raw=outcome.text,
        )

    def _context(self, intent, *, task_id: str = "", objective_id=None):
        """The routing facts for one planning request.

        Factored so the correction pass asks under the SAME conditions as
        the first attempt -- most importantly the same sensitivity. A
        repair that quietly routed somewhere the original request was not
        allowed to go would be a privacy hole wearing the shape of a
        retry.
        """
        return RoutingContext(
            is_online=not self._offline,
            is_sensitive=intent.is_sensitive,
            requires_strong_reasoning=self._requires_strong_reasoning,
            capability=PLANNING_CAPABILITY,
            task_id=task_id,
            objective_id=objective_id,
            requester=self._requester,
        )

    def _correct(self, intent, options, first, invalid, mode, attempts):
        """One repair pass. `None` when it did not produce a valid plan,
        and the caller then reports the ORIGINAL refusal -- the first
        diagnosis is the honest one, and a second failure's wording would
        only describe a second symptom."""
        import logging

        from master_agent.planner.prompting import build_correction_prompt

        logging.info(
            "plan rejected (%s); attempting one correction: %s",
            getattr(invalid, "code", ""), getattr(invalid, "reason", ""),
        )
        try:
            prompt = build_correction_prompt(
                intent, options,
                rejected=str(getattr(first, "text", "") or ""),
                reason=str(getattr(invalid, "reason", "") or ""),
                detail=str(getattr(invalid, "detail", "") or ""),
            )
            request = BudgetedSelectionRequest(
                **vars(SelectionRequest.from_context(self._context(intent))),
                request_class=PLANNING_CLASS,
                prompt=prompt,
            )
            outcome = self._runner.run(
                prompt, request, expected=plan_expectation()
            )
        except Exception:  # noqa: BLE001 -- a failed repair is not a crash
            return None
        if self._rejected(outcome) is not None:
            return None

        plan, still_invalid = validate(
            outcome.evidence.observation.get("json"), options,
            objective=intent.goal,
            requirements=getattr(intent, "requirements", ()) or (),
        )
        if plan is None:
            logging.info(
                "correction did not produce a valid plan either: %s",
                getattr(still_invalid, "reason", ""),
            )
            return None
        logging.info("correction produced a valid plan")
        return PlanOutcome(
            plan=plan,
            refusal=None,
            attempts=attempts + _attempt_trail(self._runner),
            selected_mode=mode,
            effective_mode=mode,
            evidence=outcome.evidence,
            entry_id=outcome.entry_id,
            provider_id=outcome.provider_id,
            raw=outcome.text,
            corrected=True,
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


def _attempt_trail(runner: Any) -> tuple[dict[str, Any], ...]:
    """The ladder's attempt sequence as plain, serialisable metadata.

    Deliberately narrow: tier, whether it was tried, which providers were
    considered, which one answered, and whether it worked. No prompt and
    no response text -- an audit trail is for reconstructing routing, and
    persisting the content of every reasoning call would be a privacy
    decision nobody has made.
    """
    trail: list[dict[str, Any]] = []
    for order, attempt in enumerate(getattr(runner, "last_attempts", ()) or (), start=1):
        outcome = getattr(attempt, "outcome", None)
        trail.append({
            "order": order,
            "tier": getattr(attempt, "tier", ""),
            "attempted": bool(getattr(attempt, "attempted", False)),
            "considered": list(getattr(attempt, "provider_ids_considered", ()) or ()),
            "provider_id": getattr(outcome, "provider_id", None),
            "ok": bool(getattr(outcome, "ok", False)) if outcome is not None else None,
            "reason": (getattr(outcome, "reason", "") or "")[:200] if outcome is not None else "",
        })
    return tuple(trail)
