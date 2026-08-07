"""Who is busy right now (Mission Brief 038).

A local runtime serialises work per model: a second call does not run
alongside the first, it queues behind it. That matters for budgets,
because a budget derived from measured throughput assumes the provider
starts working when asked. If it is already busy — or worse, still busy
with a call **nobody is waiting for** because it was abandoned — the
budget is wrong before the request is sent, and the call it produces will
very likely time out and orphan in turn.

This module is the bookkeeping that makes that visible. It is deliberately
small:

- It **counts**. It does not decide; `admission.py` does.
- It holds no budget and no timeout.
- It is **runtime state, not evidence**. The count is a fact about right
  now, so it is never persisted; what *is* recorded is the admission
  decision that consulted it, which is what a replay needs.

## Abandonment is tracked separately from completion

A call that finished released the provider. A call that was abandoned did
not — the daemon is still generating for a caller that stopped listening.
Counting them the same would make the provider look free while it is not,
which is exactly the mistake that produces a second orphan.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Occupant:
    """One call currently believed to be holding a provider."""

    provider_id: str
    started_at: float
    abandoned: bool = False


@dataclass
class ProviderOccupancy:
    """In-flight calls per provider.

    `clock` is injected like every other clock in MB038, so a test pins it
    and nothing here reads a wall clock.
    """

    clock: Any
    _live: dict[str, list[Occupant]] = field(default_factory=dict, init=False)

    # ---- recording -------------------------------------------------------

    def begin(self, provider_id: str) -> Occupant:
        occupant = Occupant(provider_id=provider_id, started_at=self.clock())
        self._live.setdefault(provider_id, []).append(occupant)
        return occupant

    def end(self, occupant: Occupant) -> None:
        """The call finished and the provider is free again."""
        self._release(occupant)

    def abandon(self, occupant: Occupant) -> Occupant:
        """The caller stopped waiting. The provider is **not** free.

        The occupant stays counted, flagged as abandoned, because the
        daemon is still working. Something has to say when it is done —
        see `release_abandoned`.
        """
        held = self._live.get(occupant.provider_id, [])
        for index, existing in enumerate(held):
            if existing is occupant:
                orphan = Occupant(
                    provider_id=occupant.provider_id,
                    started_at=occupant.started_at,
                    abandoned=True,
                )
                held[index] = orphan
                return orphan
        return occupant

    def release_abandoned(self, provider_id: str) -> int:
        """Forget the orphans for one provider. Returns how many.

        Called when something establishes the provider is idle again — a
        successful call, or a health probe. Kept explicit rather than
        timed out after N seconds, because guessing when an orphan
        finished is exactly the invented coefficient MB038 refuses.
        """
        held = self._live.get(provider_id, [])
        orphans = [occupant for occupant in held if occupant.abandoned]
        self._live[provider_id] = [
            occupant for occupant in held if not occupant.abandoned
        ]
        return len(orphans)

    def _release(self, occupant: Occupant) -> None:
        held = self._live.get(occupant.provider_id, [])
        for index, existing in enumerate(held):
            if existing is occupant:
                held.pop(index)
                return

    # ---- reading ---------------------------------------------------------

    def in_flight(self, provider_id: str) -> int:
        return len(self._live.get(provider_id, []))

    def abandoned(self, provider_id: str) -> int:
        return sum(
            1 for occupant in self._live.get(provider_id, []) if occupant.abandoned
        )

    def busy(self, provider_id: str) -> bool:
        return self.in_flight(provider_id) > 0

    def as_dict(self) -> dict[str, Any]:
        """A snapshot, for a founder-facing panel. Not evidence: this is
        what is true now, and now does not replay."""
        return {
            provider_id: {
                "in_flight": len(held),
                "abandoned": sum(1 for occupant in held if occupant.abandoned),
            }
            for provider_id, held in self._live.items()
            if held
        }
