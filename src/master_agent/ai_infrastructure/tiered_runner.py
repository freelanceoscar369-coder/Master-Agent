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

#: Provider ids belonging to each tier. Populated once, from the same
#: declarative `PROVIDER_CATALOG` every provider in this system is
#: already built from — never a hardcoded application name. Adding a
#: fifth desktop AI application to that catalogue changes membership
#: here automatically; this module never names one.
TIER_GEMINI = "gemini"
TIER_DESKTOP = "desktop"
TIER_BROWSER = "browser"


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
    ) -> None:
        self._executor = prompt_executor
        self._tiers: tuple[tuple[str, frozenset[str]], ...] = (
            (TIER_GEMINI, frozenset(gemini_provider_ids)),
            (TIER_DESKTOP, frozenset(desktop_provider_ids)),
            (TIER_BROWSER, frozenset(browser_provider_ids)),
        )
        tiered_ids = frozenset().union(gemini_provider_ids, desktop_provider_ids, browser_provider_ids)
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

        for tier_name, tier_ids in self._tiers:
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
            if tier_name == TIER_DESKTOP and self._desktop_context is not None:
                self._desktop_context.inventory(deep=True)

            outcome, considered = self._attempt_tier(prompt, request, tier_ids, kwargs)
            self.last_attempts.append(TierAttempt(tier_name, True, tuple(considered), outcome))
            last_outcome = outcome
            if outcome is not None and getattr(outcome, "ok", False):
                return outcome

        return last_outcome

    def _attempt_tier(
        self, prompt: str, request: Any, tier_ids: frozenset[str], kwargs: dict,
    ) -> tuple[Any, list[str]]:
        """Bounded loop *within* one tier: ask the Broker (scoped to this
        tier only) for its best candidate; if that specific provider's
        `complete()` fails, exclude just it and ask again — never more
        than `len(tier_ids)` attempts, and stop the instant a result
        succeeds."""
        remaining = set(tier_ids)
        considered: list[str] = []
        outcome = None
        while remaining:
            scoped_request = self._scope(request, remaining)
            outcome = self._executor.run(prompt, scoped_request, **kwargs)
            provider_id = getattr(outcome, "provider_id", None)
            if provider_id:
                considered.append(provider_id)
            if outcome is not None and getattr(outcome, "ok", False):
                return outcome, considered
            if not provider_id or provider_id not in remaining:
                # A refusal before any provider was even selected (e.g.
                # `NO_PROVIDER_AVAILABLE`) — nothing left to exclude and
                # retry within this tier.
                break
            remaining.discard(provider_id)
        return outcome, considered

    def _scope(self, request: Any, allowed_ids: set[str]):
        excluded_elsewhere = self._all_ids - allowed_ids
        current = frozenset(getattr(request, "exclude_providers", ()) or ())
        return dataclasses.replace(request, exclude_providers=current | frozenset(excluded_elsewhere))
