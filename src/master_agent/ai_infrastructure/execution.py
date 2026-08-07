"""Carrying out a Broker decision (Mission Brief 033).

MB032 wired the Broker so Kalpavriksha could decide who should answer.
Nobody answered. This is the step that runs the decision:

```
    request -> Broker decides -> locate provider -> cache? -> execute
                                                       |         |
                                                       +--> record on the ledger
```

**Nothing here decides.** It does not choose a provider, does not rank,
does not fall back, and does not retry an execution — the Broker chooses,
the provider executes, and this measures and records. MB033 Rule 4 for the
provider and Rule 5 for the caller amount to the same architectural fact
from two sides: *the only component allowed to name a provider is the one
holding a `DecisionRecord`.*

## What "never silently fall back" costs, and why it is worth it

When the chosen provider is missing or down, this returns a failure naming
it. It does not ask the Broker for a second opinion, even though it
trivially could, and even though that would make the system look more
robust. It would also make the stored `DecisionRecord` a lie about what
ran — and every future benchmark, cost total and policy proposal reads
those records. A system that quietly substitutes providers cannot learn
anything true about either one.

Re-asking after a failure is a real and reasonable thing to want. It
belongs to a caller holding the ranked runners-up the Broker already
returned (`decision.ranked`), making a *new* decision with its own record —
not to this function pretending the first one went differently.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from master_agent.ai_infrastructure.admission import admit
from master_agent.ai_infrastructure.cache import (
    HIT,
    MISS,
    NOT_CONSULTED,
    CachedResponse,
    NullPromptCache,
    cache_key,
)
from master_agent.ai_infrastructure.ledger import (
    ABANDONED,
    CACHE_HIT,
    COMPLETED,
    FAILED,
    REFUSED,
    DecisionEntry,
    ExecutionRecord,
)
from master_agent.ai_infrastructure.refusal import BrokerRefusal
from master_agent.ai_infrastructure.service import Selection
from master_agent.ai_infrastructure.text_verifier import passed, verify_text
from master_agent.ai_infrastructure.workload import DEFAULT_CLASS
from master_agent.providers.response import CANCELLED, UNAVAILABLE, ProviderResult

#: MB038. The outcome of a call that was refused *before* it was made.
#: Defined here rather than in `providers/response.py` because no provider
#: ever produces it -- admission happens above them, and putting it in
#: their vocabulary would imply one could.
NOT_ADMITTED = "not_admitted"

NO_PLUGIN = (
    "the Broker chose this provider and no plugin is registered to run it; "
    "refusing rather than choosing a different one"
)
NOT_EXECUTABLE = (
    "the registered plugin cannot execute a prompt (no complete() method); "
    "refusing rather than choosing a different one"
)


@dataclass(frozen=True)
class PromptOutcome:
    """What came back from asking Kalpavriksha to think.

    Three shapes, and the caller can tell them apart without parsing a
    string: a refusal (the Broker declined, nothing ran), a failed
    execution (something ran and did not work), and an answer.
    """

    ok: bool = False
    text: str = ""
    provider_id: str | None = None
    entry_id: int | None = None
    cache: str = NOT_CONSULTED
    execution: ExecutionRecord | None = None
    selection: Selection | None = None
    refusal: BrokerRefusal | None = None
    result: ProviderResult | None = None
    #: MB035. The Verification record for this answer, or None when
    #: nothing was asked of it.
    evidence: Any = None
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def verified(self) -> bool:
        """Checked against something stated in advance, and matched all of
        it. `False` when nothing was asked — unchecked is not verified."""
        return passed(self.evidence)

    @property
    def verdict(self) -> str:
        return self.evidence.verdict.value if self.evidence is not None else ""

    @property
    def refused(self) -> bool:
        """The Broker declined. Nothing was contacted, and there is no
        execution to explain."""
        return self.refusal is not None

    @property
    def from_cache(self) -> bool:
        return self.cache == HIT

    @property
    def latency_ms(self) -> float | None:
        return self.execution.latency_ms if self.execution else None

    @property
    def reason(self) -> str:
        """One sentence for a founder, whichever of the three shapes this
        is."""
        if self.refusal is not None:
            return self.refusal.reason
        if self.execution is not None and not self.ok:
            return self.execution.error
        return ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "provider_id": self.provider_id,
            "entry_id": self.entry_id,
            "cache": self.cache,
            "refused": self.refused,
            "reason": self.reason,
            "verdict": self.verdict,
            "verified": self.verified,
            "execution": self.execution.as_dict() if self.execution else None,
            "refusal": self.refusal.as_dict() if self.refusal else None,
        }


class PromptExecutor:
    """Runs what the Broker chose, and records what happened.

    `providers` needs one method — `get(provider_id)` — so a
    `PluginRegistry` satisfies it and nothing here depends on that class.
    `cache` defaults to `NullPromptCache`, which is the shipped behaviour:
    every lookup misses until something can verify generated text.
    """

    def __init__(
        self,
        service: Any,
        providers: Any,
        ledger: Any,
        cache: Any = None,
        clock: Any = None,
        store_unverified: bool = False,
        memory_sink: Any = None,
        occupancy: Any = None,
        monotonic: Any = None,
    ) -> None:
        self._service = service
        self._providers = providers
        self._ledger = ledger
        self._cache = cache if cache is not None else NullPromptCache()
        self._clock = clock or (lambda: datetime.now(UTC))
        # MB035's outbound port -- see `_remember`.
        self._memory_sink = memory_sink
        self.memory_failures: list[str] = []
        # Rule 2: the cache reuses *verified* work. Nothing verifies prose
        # yet, so the default stores nothing and the hit rate is honestly
        # zero rather than optimistically wrong.
        self._store_unverified = store_unverified
        # MB038. Both optional: a system with no occupancy tracking still
        # runs, and admits everything -- which is correct while nothing
        # runs concurrently, and honest about the fact that it is not
        # protecting anything.
        self._occupancy = occupancy
        self._monotonic = monotonic or time.monotonic

    @property
    def cache(self) -> Any:
        return self._cache

    # ---- running --------------------------------------------------------

    def run(
        self,
        prompt: str,
        request: Any,
        context: dict[str, Any] | None = None,
        verified: bool = False,
        use_cache: bool = True,
        expected: Any = None,
        cancellation: Any = None,
    ) -> PromptOutcome:
        """Decide, carry it out, and check the answer against what was
        asked for.

        `expected` is an `ExpectedOutcome` stated **before** the answer
        arrives (MB035). When one is given the verdict decides whether the
        result is verified, and the caller's `verified` flag is ignored —
        evidence beats assertion, which is the whole point of ADR-0011
        keeping Verification structurally independent of Execution.

        `verified` survives for callers with nothing to check against. It
        is still what MB033 made it: a promise, and never the default.
        """
        outcome = self._service.decide(request)
        if outcome.selection is None:
            # The Broker refused. The decision is already on the ledger
            # with its reason; there is nothing to execute and nothing to
            # add.
            return PromptOutcome(refusal=outcome.refusal, entry_id=_entry_id(outcome))

        selection = outcome.selection
        provider, problem = self._locate(selection.provider_id)
        if provider is None:
            return self._failed(selection, UNAVAILABLE, problem, cache=NOT_CONSULTED)

        # MB038. The last question before a socket opens: given this
        # budget and what the provider is already doing, is the call worth
        # making? A refusal here costs nothing; the call it prevents would
        # have cost the remaining budget and left an orphan behind.
        budget = getattr(selection, "budget", None)
        admission = admit(
            budget=budget,
            request_class=getattr(request, "request_class", DEFAULT_CLASS),
            now=self._monotonic(),
            occupancy=self._occupancy,
            provider_id=selection.provider_id,
            serialises=getattr(selection.profile, "serialises", False),
        )
        if not admission.ok:
            return self._failed(
                selection,
                NOT_ADMITTED,
                admission.reason,
                cache=NOT_CONSULTED,
                admission=admission,
                budget=budget,
            )

        model = str(getattr(provider, "model", "") or "")
        key = cache_key(
            selection.decision.task.capability, selection.provider_id, model, prompt
        )

        cache_state = NOT_CONSULTED
        if use_cache:
            cache_state = MISS
            lookup = self._cache.lookup(key)
            if lookup.hit and lookup.entry is not None:
                # A stored answer was verified against *the expectation it
                # was stored under*. This caller may be asking for
                # something else entirely, so it is checked again before
                # being served -- found by a live run that asked one
                # prompt with two different expectations and got the first
                # answer back marked "not checked".
                #
                # Re-checking is arithmetic; calling the provider again is
                # seconds. So a hit that still satisfies the new
                # expectation is served, and one that does not falls
                # through to a real call.
                reuse = (
                    verify_text(lookup.entry.text, expected)
                    if expected is not None
                    else None
                )
                if expected is None or passed(reuse):
                    return self._reused(selection, lookup.entry, key, reuse)

        # Occupancy is held for exactly as long as the provider is
        # believed busy. A call that returns releases it; a call that
        # raises does not get to skip the release, or the provider would
        # look permanently occupied after one bad call.
        occupant = (
            self._occupancy.begin(selection.provider_id)
            if self._occupancy is not None
            else None
        )
        try:
            # `budget` is passed only when there is one, so a provider
            # written before MB038 keeps its two-argument signature and
            # keeps working. Step 14 makes the parameter universal.
            result = (
                provider.complete(
                    prompt, context, budget=budget, cancellation=cancellation
                )
                if budget is not None
                else provider.complete(prompt, context)
            )
        except BaseException:
            # Released, not abandoned. `complete()` is contractually
            # forbidden from raising for an operational failure (MB033
            # Rule 5), so a raise here is a defect in *our* code -- and
            # wedging a provider in response to our own bug would turn one
            # broken call into a permanently unusable provider, with
            # nothing able to clear it because admission would refuse
            # every call that might.
            self._release(occupant)
            raise
        else:
            if result.outcome == CANCELLED:
                # Cancellation stops *us* waiting. It does not stop the
                # daemon generating, so the provider stays counted as
                # occupied until something establishes otherwise.
                self._abandon(occupant)
            else:
                self._release(occupant)

        # MB035: judge the answer before anything is allowed to remember
        # it. Only a successful call is worth checking -- a timeout has no
        # text, and running checks against "" would produce a confident
        # NOT_MATCHED that says nothing the outcome did not already say.
        evidence = None
        if result.ok and expected is not None:
            evidence = verify_text(result.text, expected)
        is_verified = passed(evidence) if expected is not None else verified

        entry = self._record(
            selection, result, cache_state, model, evidence, budget, admission
        )

        if result.ok and (is_verified or self._store_unverified):
            self._cache.store(
                key,
                CachedResponse(
                    text=result.text,
                    provider_id=selection.provider_id,
                    model=result.response.model if result.response else model,
                    cost=selection.entry.cost or 0.0,
                    locality=selection.entry.locality,
                    prompt_tokens=result.response.prompt_tokens if result.response else None,
                    completion_tokens=(
                        result.response.completion_tokens if result.response else None
                    ),
                    verified=is_verified,
                    stored_at=self._clock(),
                ),
            )

        outcome = PromptOutcome(
            ok=result.ok,
            text=result.text,
            provider_id=selection.provider_id,
            entry_id=entry.entry_id,
            cache=cache_state,
            execution=entry.execution,
            selection=selection,
            result=result,
            evidence=evidence,
            detail=dict(result.detail),
        )
        self._remember(prompt, outcome)
        return outcome

    # ---- occupancy, released exactly once --------------------------------

    def _release(self, occupant: Any) -> None:
        if occupant is not None and self._occupancy is not None:
            self._occupancy.end(occupant)

    def _abandon(self, occupant: Any) -> None:
        if occupant is not None and self._occupancy is not None:
            self._occupancy.abandon(occupant)

    def _remember(self, prompt: str, outcome: PromptOutcome) -> None:
        """Hand a verified outcome to whoever is writing things down.

        An outbound port, not an import: `ai_infrastructure` stays free of
        `memory/`, and `memory/` is already forbidden from reaching back
        here (MB034 asserts it). The same move MB025 made with
        `CheckpointSink` and MB031 with the Broker's own sink.

        Only ever called for a *checked* answer. An unverified one has
        nothing to teach — writing it down would fill the Prompt Library
        with prompts nobody established worked.
        """
        if self._memory_sink is None or outcome.evidence is None:
            return
        try:
            self._memory_sink(prompt, outcome)
        except Exception as exc:  # noqa: BLE001 - remembering never gates work
            self.memory_failures.append(str(exc))

    # ---- the pieces ------------------------------------------------------

    def _locate(self, provider_id: str) -> tuple[Any, str]:
        """Find the thing that can run this provider, or say why not.

        A missing plugin is a **wiring** problem, not a decision problem:
        the Broker chose correctly and this process cannot carry it out.
        Reported as such rather than resolved by picking something else.
        """
        try:
            provider = self._providers.get(provider_id)
        except Exception:  # noqa: BLE001 - any lookup failure is "not here"
            return None, NO_PLUGIN
        if provider is None:
            return None, NO_PLUGIN
        if not callable(getattr(provider, "complete", None)):
            return None, NOT_EXECUTABLE
        return provider, ""

    def _reused(
        self,
        selection: Selection,
        cached: CachedResponse,
        key: str,
        evidence: Any = None,
    ) -> PromptOutcome:
        """A cache hit. No provider is contacted, and the record says
        `cache_hit` rather than `succeeded` — an execution that did not
        happen must never be counted as one that did."""
        execution = ExecutionRecord(
            provider_id=cached.provider_id,
            outcome=CACHE_HIT,
            latency_ms=0.0,
            prompt_tokens=cached.prompt_tokens,
            completion_tokens=cached.completion_tokens,
            cost=cached.cost,
            quality_declared=selection.entry.quality,
            quality_basis=selection.entry.quality_basis,
            locality=cached.locality or selection.entry.locality,
            model=cached.model,
            retries=0,
            cache=HIT,
            executed_at=self._clock(),
            verdict=evidence.verdict.value if evidence is not None else "",
            evidence_id=evidence.evidence_id if evidence is not None else "",
        )
        entry = self._ledger.record_execution(selection.entry.entry_id, execution)
        return PromptOutcome(
            ok=True,
            text=cached.text,
            provider_id=cached.provider_id,
            entry_id=entry.entry_id,
            cache=HIT,
            execution=execution,
            selection=selection,
            evidence=evidence,
            detail={"cache_key": key},
        )

    def _record(
        self,
        selection: Selection,
        result: ProviderResult,
        cache: str,
        model: str,
        evidence: Any = None,
        budget: Any = None,
        admission: Any = None,
    ) -> DecisionEntry:
        """MB033 Rule 3, in one place: latency, tokens, cost, success,
        quality declaration and retry count, against the decision that
        chose this provider — plus, since MB035, the verdict on what came
        back."""
        response = result.response
        return self._ledger.record_execution(
            selection.entry.entry_id,
            ExecutionRecord(
                provider_id=selection.provider_id,
                outcome=result.outcome,
                latency_ms=result.latency_ms,
                prompt_tokens=response.prompt_tokens if response else None,
                completion_tokens=response.completion_tokens if response else None,
                cost=selection.entry.cost,
                quality_declared=selection.entry.quality,
                quality_basis=selection.entry.quality_basis,
                locality=selection.entry.locality,
                model=(response.model if response else "") or model,
                # `attempts` counts tries; `retries` counts the ones that
                # were not the first. Recording the wrong one of those two
                # would make every flakiness number off by one per call.
                retries=max(0, result.attempts - 1),
                cache=cache,
                error=result.error,
                executed_at=self._clock(),
                verdict=(
                    evidence.verdict.value if evidence is not None else ""
                ),
                evidence_id=evidence.evidence_id if evidence is not None else "",
                # MB038. Lifted out of the provider's own detail rather
                # than recomputed here: the adapter measured it, and a
                # second opinion about what it saw would be a second
                # source of truth.
                budget=budget.as_dict() if budget is not None else None,
                observation=result.detail.get("observation"),
                timeout=result.detail.get("timeout"),
                admission=admission.decision if admission is not None else "",
                admission_reason=admission.reason if admission is not None else "",
                lifecycle=_lifecycle_of(result),
            ),
        )

    def _failed(
        self,
        selection: Selection,
        outcome: str,
        error: str,
        cache: str,
        admission: Any = None,
        budget: Any = None,
    ) -> PromptOutcome:
        """A failure that never reached a provider — recorded anyway,
        because "we could not run what was chosen" is exactly the kind of
        thing that is invisible until someone asks why nothing works.

        An admission refusal comes through here too: it is a call that did
        not happen *on purpose*, and the record says which purpose."""
        execution = ExecutionRecord(
            provider_id=selection.provider_id,
            outcome=outcome,
            latency_ms=0.0,
            cost=selection.entry.cost,
            quality_declared=selection.entry.quality,
            quality_basis=selection.entry.quality_basis,
            locality=selection.entry.locality,
            retries=0,
            cache=cache,
            error=error,
            executed_at=self._clock(),
            budget=budget.as_dict() if budget is not None else None,
            admission=admission.decision if admission is not None else "",
            admission_reason=admission.reason if admission is not None else "",
            lifecycle=REFUSED if admission is not None else FAILED,
        )
        entry = self._ledger.record_execution(selection.entry.entry_id, execution)
        return PromptOutcome(
            ok=False,
            provider_id=selection.provider_id,
            entry_id=entry.entry_id,
            cache=cache,
            execution=execution,
            selection=selection,
        )


def _lifecycle_of(result: Any) -> str:
    """How the call ended, as distinct from what it produced.

    Cancellation is its own lifecycle rather than a kind of failure:
    the provider may still be working, so the call is neither completed
    nor cleanly failed, and the occupancy count reflects that.
    """
    if result.outcome == CANCELLED:
        return ABANDONED
    return COMPLETED if result.ok else FAILED


def _entry_id(outcome: Any) -> int | None:
    return outcome.refusal.entry_id if outcome.refusal is not None else None
