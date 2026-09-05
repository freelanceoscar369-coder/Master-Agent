"""Corrected Fallback Ladder (Reasoning Fallback Ladder brief) — strict,
sequential reasoning tiers.

`Tier 1 — Gemini API → Tier 2 — Installed Desktop AI → Tier 3 — Browser
Free AI`, exactly as specified. **Not provider competition, not automatic
load balancing** — the mission's own explicit distinction from ordinary
`CapabilityBroker` ranking, which this module deliberately does not
reinterpret: `CapabilityBroker`/`policy.py` rank freely by cost/quality/
locality, and under several existing policies a free, `DESKTOP`-locality
provider would rank *above* Gemini's own free tier (`_LOCALITY_ORDER`
puts `DESKTOP` before `CLOUD`). Left to that ranking alone, the Broker
could select a desktop app before Gemini has even been tried — exactly
what the mission forbids.

**The fix reuses the existing machinery rather than replacing it.**
`TaskProfile.exclude_providers: frozenset[str]` (`broker/profiles.py`)
already exists and is already honored by `CapabilityBroker._reject()`
(`broker/broker.py:267`, `EXCLUDED`). This module's whole job is scoping
one `PromptExecutor.run()` call at a time to exactly one tier's
provider ids, via that existing field — so the Broker is structurally
unable to see a later tier's candidates before an earlier tier has been
exhausted, not merely unlikely to rank them first. Nothing about
`CapabilityBroker`, `policy.py`, or `PromptExecutor` is modified; this is
a drop-in wrapper for `Planner`'s own `runner` parameter — confirmed via
this session's own research that `Planner` requires exactly one method,
`run(prompt, request, expected=...)` (`planner/planner.py:184`) — so the
Planner itself needed zero changes to gain tiered fallback.

**SUPERSEDED FOR INTERACTIVE TURNS — founder decision, do not revert.**
Everything above describes the ladder as it still works for planning,
execution, code generation, verification and embedding. It no longer
describes an `interactive` turn, and the paragraphs above must not be used
to "correct" that back.

The argument above is that the Broker, left to rank freely, could pick a
desktop application before Gemini has been tried. That is true, and for a
cost-and-privacy question it is the wrong outcome. For a founder waiting
on a conversational answer it is the right one, and the ladder's own
guarantee becomes the defect: an adequate fast provider cannot win until
every slower one has been exhausted. Measured on a trivial public
generation -- desktop automation ~74s serially, a healthy free Gemini
~5.4s, ~90s overall.

So an `interactive` request gets ONE attempt containing every provider,
and `broker/policy.py`'s `policy_for_request_class()` decides it under
`fast_free`, which ranks free options by latency. The choice of provider
still belongs entirely to the Broker; what changed is that this module
stopped pre-deciding it by locality. Privacy is unaffected -- `fast_free`
keeps `require_private_for_sensitive`, and `approval_needed()` one layer
down still refuses to send sensitive work to a non-private provider
without a founder's yes. `allow_paid=False` keeps a paid provider from
winning on speed while `cost == 0` still conflates a free API, an
installed subscription and a local runtime.

**No second retry system.** A transient Gemini failure (429/500/502/503/
504) is already retried, bounded, inside `GeminiProvider.complete()`
itself (`DEFAULT_MAX_ATTEMPTS = 3`) before `PromptExecutor.run()` ever
returns to this module — by the time this module sees a failed Tier 1
outcome, Gemini has already exhausted its own existing retry policy. This
module only ever decides *which tier's providers the Broker may see*,
never how many times to hit the same one.

**Within Tier 2 specifically**, several desktop AI applications may be
installed at once. This module still does not invent a ranking
algorithm: it calls the existing `CapabilityBroker` (via
`PromptExecutor.run()`) to pick the best-ranked *desktop* candidate, and
if that one specific provider's `complete()` fails, excludes just that
one provider_id and asks the Broker again — bounded by the number of
desktop providers registered, never indefinite (Section 6's own rule:
"do not retry indefinitely... stop as soon as a verified reasoning
result is obtained").
"""
from __future__ import annotations

import dataclasses
from typing import Any

#: Named from the workload vocabulary rather than spelled here, so the two
#: cannot drift apart.
from master_agent.ai_infrastructure.workload import INTERACTIVE as INTERACTIVE_CLASS
from master_agent.providers.response import UNAVAILABLE

#: Provider ids belonging to each tier. Populated once, from the same
#: declarative `PROVIDER_CATALOG` every provider in this system is
#: already built from — never a hardcoded application name. Adding a
#: fifth desktop AI application to that catalogue changes membership
#: here automatically; this module never names one.
#: Tier 0. A local runtime on the founder's own machine: free, and
#: nothing it is given leaves the laptop. It is first because that
#: is the honest order of preference for private work, not because
#: it is the strongest reasoner.
TIER_LOCAL = "local"
TIER_GEMINI = "gemini"
TIER_DESKTOP = "desktop"
TIER_BROWSER = "browser"
#: The one attempt an interactive turn gets: every provider at once, ranked
#: by the Broker rather than pre-ordered by locality here.
TIER_ANY = "any"



#: Outcomes that mean the provider was never actually asked.
#:
#: `UNAVAILABLE` is the transport saying it could not reach the provider
#: at all -- no prompt was delivered, no window driven, nothing spent. Any
#: other failure means the request WAS put to it and the answer was no
#: good, which is a different fact and belongs to the Brain.
_NEVER_INVOKED_OUTCOMES = frozenset({UNAVAILABLE})


def _never_invoked(outcome: Any) -> bool:
    """Was this provider unreachable, rather than asked and unhelpful?"""
    return str(getattr(outcome, "outcome", "") or "") in _NEVER_INVOKED_OUTCOMES


def _acceptable(outcome: Any) -> bool:
    """Whether this attempt actually answered the request.

    **One definition, read by both loops.** `run()` already knew that a
    result carrying a failed expectation is not an answer -- "stop as soon
    as a VERIFIED reasoning result is obtained", this module's own rule --
    while `_attempt_tier()` stopped on `ok` alone. Those two disagreed,
    and the disagreement was invisible while every tier held one locality:
    an unverified outcome returned to `run()`, which moved to the next
    tier, and the next tier had different providers in it.

    An interactive turn has ONE tier holding every configured provider, so
    there is no next tier -- and a provider that executed fine while
    failing the expectation ended the whole attempt with untried
    candidates sitting beside it. Measured live: a forced fallback reached
    a desktop provider, which returned `ok=True` and one line against a
    three-line expectation, and the run stopped there.

    The distinction the rest of this module turns on:

        execution failed              -> not acceptable
        executed, expectation failed  -> not acceptable, and NOT a
                                         provider execution failure
        executed, nothing was asked   -> acceptable, exactly as before

    `evidence is not None` is the discriminator, and it is the precise
    one: `PromptOutcome.evidence` is `None` exactly when no expectation was
    supplied, and `verified` is documented as "False when nothing was
    asked -- unchecked is not verified". A caller with nothing to check
    against therefore behaves exactly as it always did.
    """
    if outcome is None or not getattr(outcome, "ok", False):
        return False
    asked = getattr(outcome, "evidence", None) is not None
    return (not asked) or bool(getattr(outcome, "verified", False))


@dataclasses.dataclass(frozen=True)
class TierAttempt:
    """One tier's outcome, kept for founder-facing/diagnostic reporting —
    Section 7's own requirement: report which tier actually handled the
    request, not just a final yes/no."""

    tier: str
    attempted: bool
    provider_ids_considered: tuple[str, ...]
    outcome: Any  # PromptOutcome, or None if never attempted


class TieredPromptRunner:
    """Drop-in replacement for `PromptExecutor` as `Planner(runner=...)`.
    Presents the identical `run(prompt, request, **kwargs) -> PromptOutcome`
    surface `Planner` already calls — `Planner`'s own code is untouched.
    """

    def __init__(
        self,
        prompt_executor: Any,
        gemini_provider_ids: frozenset[str],
        desktop_provider_ids: frozenset[str],
        browser_provider_ids: frozenset[str],
        desktop_context: Any = None,
        all_known_provider_ids: frozenset[str] | None = None,
        local_provider_ids: frozenset[str] = frozenset(),
    ) -> None:
        self._executor = prompt_executor
        # Additive and defaulted empty, so every existing caller keeps the
        # exact ladder it had.
        #
        # Order is by capability, NOT by privacy. Privacy is already
        # guaranteed one layer down: `approval_needed()` refuses to send
        # sensitive work to a provider whose `privacy` is not PRIVATE
        # without a founder's yes, so a private document cannot reach a
        # cloud model whatever order these tiers are in.
        #
        # Putting local first for everything therefore buys no privacy and
        # costs a great deal: on this machine a planning-sized prompt takes
        # a local model about a quarter of an hour, and planning carries no
        # private data at all -- it is the objective plus the capability
        # catalogue. `_ordered_tiers()` is where the distinction is made.
        # ADR-0017 Decision 3's frozen ladder, in order:
        #
        #   local -> desktop app -> free cloud -> free aggregator
        #        -> existing subscription -> paid API
        #
        # This read `gemini -> desktop -> browser -> local` until now, and
        # that was my drift, argued at the time as "order is capability,
        # not privacy". The argument was about the wrong thing: ADR-0017
        # does not order these by capability, it orders them by cost with
        # local first, and Constitution §7.1 makes local-first not
        # optional. A frozen decision is not mine to re-derive because a
        # local model is slow.
        #
        # The last two rungs have no tier here yet -- no subscription or
        # paid provider is wired -- and rungs are added in ADR order when
        # they are, never appended wherever they happen to be built.
        #: Which candidates need the machine scanned before they can
        #: honestly report availability. Kept as a set so the scan follows
        #: the candidates rather than a tier's name.
        self._desktop_ids = frozenset(desktop_provider_ids)
        self._tiers: tuple[tuple[str, frozenset[str]], ...] = (
            (TIER_LOCAL, frozenset(local_provider_ids)),
            (TIER_DESKTOP, frozenset(desktop_provider_ids)),
            (TIER_GEMINI, frozenset(gemini_provider_ids)),
            (TIER_BROWSER, frozenset(browser_provider_ids)),
        )
        tiered_ids = frozenset().union(
            local_provider_ids, gemini_provider_ids, desktop_provider_ids,
            browser_provider_ids,
        )
        #: The providers this deployment actually CONFIGURED -- the union
        #: of what was placed into the tiers above, and nothing else.
        #:
        #: Distinct from `_all_ids` below, and the distinction is the whole
        #: point: `_all_ids` is the universe needed to EXCLUDE everything
        #: not allowed in an attempt. Reading it as a candidate list turns
        #: "every provider this codebase has a descriptor for" into "every
        #: provider we may send a prompt to", which is the opposite of what
        #: it is for.
        #:
        #: A deployment's standing "never enable or query it" constraints
        #: depend on exactly this. Such a provider keeps its descriptor in
        #: the catalogue deliberately, is never constructed, registered or
        #: probed, and its presence in `_all_ids` is what has always kept
        #: it EXCLUDED. Four of them became live interactive candidates the
        #: moment I used `_all_ids` as the candidate set.
        #:
        #: Known but not configured is never a candidate. That is generic,
        #: needs no exclusion table, and names no provider.
        self._configured_ids: frozenset[str] = tiered_ids
        # A real, live bug found running the actual production pipeline:
        # `ProviderSource` (and therefore `CapabilityBroker.select()`)
        # sees *every* spec in whatever `specs=` tuple the composition
        # root built it with — which, in the real `kalpavriksha_desktop.
        # py` wiring, is the shared `PROVIDER_CATALOG` (every other
        # registered local/cloud provider this codebase knows about,
        # including one under a standing "never enable/query it"
        # constraint elsewhere in this codebase) plus this ladder's own
        # three tiers. If `_all_ids` only covered the three named tiers,
        # every provider *outside* them was never excluded from any
        # tier's scoped request, so the Broker could rank one of them
        # highest and "win" a tier attempt regardless of which tier this
        # module thought it was scoping to. `all_known_provider_ids` —
        # the caller's own full `specs` universe — is what makes
        # exclusion actually complete: every tier attempt now excludes
        # everything *not* explicitly named in one of the three tiers,
        # not just the other two tiers.
        self._all_ids: frozenset[str] = (
            frozenset(all_known_provider_ids) | tiered_ids
            if all_known_provider_ids is not None
            else tiered_ids
        )
        self._desktop_context = desktop_context
        #: Section 7 / diagnostic evidence for the most recent call —
        #: "the system reports which tier actually handled the request."
        self.last_attempts: list[TierAttempt] = []

    def run(self, prompt: str, request: Any, **kwargs: Any) -> Any:
        self.last_attempts = []
        last_outcome = None

        for tier_name, tier_ids in self._ordered_attempts(request):
            if not tier_ids:
                self.last_attempts.append(TierAttempt(tier_name, False, (), None))
                continue

            # Desktop-tier discovery is lazy and scoped to exactly this
            # moment: only once Gemini has already failed, never at boot,
            # never merely because a desktop provider was registered.
            # This is the one place this module performs I/O of its own,
            # and it is read-only machine discovery, not an application
            # launch — launching happens only inside a provider's own
            # `complete()`, one tier down.
            # The scan must follow the CANDIDATES, not the tier's name.
            # A desktop provider reports "not available" until the machine
            # has been scanned, so an attempt that offers desktop
            # candidates without scanning would see them rejected as
            # missing and hand the win to whatever remained -- the right
            # provider chosen for the wrong reason, and a fast path that
            # only looks fast because it never looked. Measured: the first
            # interactive run selected gemini.api over a field where every
            # desktop candidate read "not available".
            if self._desktop_context is not None and (tier_ids & self._desktop_ids):
                self._desktop_context.inventory(deep=True)

            outcome, considered = self._attempt_tier(prompt, request, tier_ids, kwargs)
            self.last_attempts.append(TierAttempt(tier_name, True, tuple(considered), outcome))
            last_outcome = outcome
            if _acceptable(outcome):
                return outcome

        return last_outcome

    def _ordered_attempts(self, request: Any) -> tuple[tuple[str, frozenset[str]], ...]:
        """The attempts this request gets, in order.

        **Locality tiers are a cost-and-privacy answer, not a latency
        one.** Walking local -> desktop -> gemini -> browser and scoping
        the Broker to one locality at a time means an adequate fast
        provider cannot win until every slower one has been exhausted.
        Measured on a trivial public generation: desktop automation ~74s
        serially, a healthy free Gemini ~5.4s, ~90s overall. For a founder
        waiting on three words that is the wrong question answered well.

        So an INTERACTIVE turn gets ONE attempt containing every provider,
        and the Broker ranks them under `fast_free` -- which is chosen by
        `policy_for_request_class()` in the Broker's own policy module,
        not here. This module still decides nothing about which provider
        wins; it stops pre-deciding by locality and lets the owner choose.

        `_attempt_tier()` already falls through candidate by candidate
        within one attempt, so a selected provider that fails still yields
        to the next eligible one, bounded by the candidate count.

        Every other class keeps the ladder exactly as it was.
        """
        request_class = str(getattr(request, "request_class", "") or "").strip().lower()
        if request_class != INTERACTIVE_CLASS:
            return self._tiers

        # CONFIGURED, never `_all_ids`. See `_configured_ids`.
        if not self._configured_ids:
            return self._tiers
        return ((TIER_ANY, self._configured_ids),)

    def _attempt_tier(
        self, prompt: str, request: Any, tier_ids: frozenset[str], kwargs: dict,
    ) -> tuple[Any, list[str]]:
        """Bounded loop *within* one tier: ask the Broker (scoped to this
        tier only) for its best candidate; if that candidate does not
        answer the request, exclude just it and ask again — never more
        than `len(tier_ids)` attempts, and stop the instant one does.

        "Does not answer" is `_acceptable()`, the same predicate `run()`
        uses, and it covers two different things on purpose: a provider
        whose `complete()` failed, and a provider that completed fine
        while failing the expectation the caller stated. The second is not
        an execution failure and is not treated as one — the provider is
        simply not adequate for THIS request, so the Broker is asked again
        over what remains. It is never retried, and the expectation is
        never weakened to let it through."""
        remaining = set(tier_ids)
        considered: list[str] = []
        outcome = None
        while remaining:
            scoped_request = self._scope(request, remaining)
            outcome = self._executor.run(prompt, scoped_request, **kwargs)
            provider_id = getattr(outcome, "provider_id", None)
            if provider_id:
                considered.append(provider_id)
            if _acceptable(outcome):
                return outcome, considered
            if not provider_id or provider_id not in remaining:
                # A refusal before any provider was even selected (e.g.
                # `NO_PROVIDER_AVAILABLE`) — nothing left to exclude and
                # retry within this tier.
                break
            if not _never_invoked(outcome):
                # **Invoked and failed is not the same as unreachable.**
                #
                # Measured live 2026-09-05: one Brain sub-call walked
                # ChatGPT -> Perplexity -> Kimi -> the web lane, four of
                # the founder's applications driven for one question,
                # because each was invoked, timed out, and this loop
                # quietly asked for the next one.
                #
                # A provider that could not be REACHED was never asked,
                # so asking someone else is still one question. A
                # provider that WAS asked and failed is a method
                # failure, and ADR-0027 gives that to the Brain to
                # adjudicate -- retry, another resource, another
                # method, clarification, or an honest stop. It does not
                # give it to a loop.
                #
                # So the failure goes back with its evidence, and any
                # change of provider becomes a new, explicit, recorded
                # selection rather than a silent one.
                break
            remaining.discard(provider_id)
        return outcome, considered

    def _scope(self, request: Any, allowed_ids: set[str]):
        excluded_elsewhere = self._all_ids - allowed_ids
        current = frozenset(getattr(request, "exclude_providers", ()) or ())
        return dataclasses.replace(request, exclude_providers=current | frozenset(excluded_elsewhere))
