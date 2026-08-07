"""The Prompt Cache — foundation only (Mission Brief 033, Rule 2).

> Never ask a frontier model to solve something already solved.

The interface for that, and nothing more. MB033 asks for `lookup`,
`store`, `invalidate` and says future briefs implement the rest, so this
module defines the protocol and ships **one deliberately empty
implementation** (`NullPromptCache`) as the wired default. Out of the box,
every lookup is a MISS and the Dashboard says so — no invented hit rate,
no implied saving.

## Two rules that are not negotiable, written down before anything caches

1. **It never invents an answer.** A cache returns text a provider
   actually produced, for the same capability, the same provider, the same
   model and the same prompt — matched byte for byte through a digest.
   *Semantic* similarity is explicitly out of scope: "close enough" is a
   judgement, judgements belong to the Broker, and a cache that guessed
   would be the least auditable component in the system.
2. **It only stores verified work.** Rule 2 says *reuse previous verified
   results*, and there is no verifier for generated text yet (ADR-0011
   defines the subsystem; nothing in it judges prose). So
   `PromptExecutor` stores nothing unless a caller states the result was
   verified — which means the cache stays empty in this build, on purpose,
   and the metric that counts hits honestly reads zero.

`ExactPromptCache` exists as the reference implementation that proves the
protocol is implementable and gives the executor's hit path something real
to be tested against. It is **not wired by default**: shipping behaviour
is the always-miss one MB033 describes.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

# ---- what a lookup can say ----------------------------------------------

HIT = "hit"
MISS = "miss"
#: No cache was consulted at all — a decision was refused, or the caller
#: asked for a fresh answer. Distinct from MISS, because "we looked and
#: found nothing" and "we never looked" are different facts (ADR-0016).
NOT_CONSULTED = "not_consulted"
CACHE_STATES = (HIT, MISS, NOT_CONSULTED)


@dataclass(frozen=True)
class CachedResponse:
    """Work that was already done, and enough about it to count what
    reusing it saved. Frozen: a cached answer describes something that
    already happened."""

    text: str
    provider_id: str
    model: str = ""
    #: What the original execution cost. This is the *only* honest basis
    #: for "money saved" — an execution that actually occurred and was not
    #: repeated (MB033: no imaginary savings).
    cost: float = 0.0
    locality: str = ""
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    verified: bool = False
    stored_at: datetime = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.stored_at is None:
            object.__setattr__(self, "stored_at", datetime.now(UTC))

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "provider_id": self.provider_id,
            "model": self.model,
            "cost": self.cost,
            "locality": self.locality,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "verified": self.verified,
            "stored_at": self.stored_at.isoformat(),
        }


@dataclass(frozen=True)
class CacheLookup:
    """The answer to "have we done this before?" — always with the key, so
    a caller can store against the same one rather than recomputing it and
    risking a different answer."""

    state: str
    key: str
    entry: CachedResponse | None = None

    @property
    def hit(self) -> bool:
        return self.state == HIT


@runtime_checkable
class PromptCache(Protocol):
    """Three methods, exactly as MB033 specifies."""

    def lookup(self, key: str) -> CacheLookup: ...

    def store(self, key: str, response: CachedResponse) -> bool: ...

    def invalidate(self, key: str | None = None) -> int: ...


def cache_key(capability: str, provider_id: str, model: str, prompt: str) -> str:
    """A stable digest of everything that determines the answer.

    All four parts matter. The same prompt to a different model is a
    different answer; the same prompt for a different capability was asked
    for a different reason. Hashed rather than concatenated so a key never
    carries the founder's prompt text around the system in the clear.
    """
    payload = "\x00".join((capability or "", provider_id or "", model or "", prompt or ""))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


class NullPromptCache:
    """The wired default: looks nothing up, stores nothing, and says so.

    Not a stub standing in for missing work — it is the correct behaviour
    until something can verify generated text. A cache that stored
    unverified output would make Kalpavriksha repeat a wrong answer
    faster, which is worse than not caching at all.
    """

    def lookup(self, key: str) -> CacheLookup:
        return CacheLookup(state=MISS, key=key)

    def store(self, key: str, response: CachedResponse) -> bool:
        return False

    def invalidate(self, key: str | None = None) -> int:
        return 0

    def __len__(self) -> int:
        return 0


class ExactPromptCache:
    """Exact-match reuse, in memory. The reference implementation.

    **Not wired by default.** It exists so the protocol is proven by
    something rather than only described, and so the executor's hit path
    can be tested against a real cache. Exact match only: no similarity,
    no embeddings, no "close enough".

    `store()` refuses anything unverified unless explicitly allowed, which
    is Rule 2 enforced at the only door that can break it.
    """

    def __init__(self, allow_unverified: bool = False) -> None:
        self._entries: dict[str, CachedResponse] = {}
        self._allow_unverified = allow_unverified
        self.hits = 0
        self.misses = 0

    def lookup(self, key: str) -> CacheLookup:
        entry = self._entries.get(key)
        if entry is None:
            self.misses += 1
            return CacheLookup(state=MISS, key=key)
        self.hits += 1
        return CacheLookup(state=HIT, key=key, entry=entry)

    def store(self, key: str, response: CachedResponse) -> bool:
        """Returns whether it was stored. A refusal is not an error — it is
        the cache declining to remember something nobody checked."""
        if not response.verified and not self._allow_unverified:
            return False
        self._entries[key] = response
        return True

    def invalidate(self, key: str | None = None) -> int:
        """`None` clears everything. Returns how many entries went, so a
        caller can report it rather than guess."""
        if key is None:
            count = len(self._entries)
            self._entries.clear()
            return count
        return 1 if self._entries.pop(key, None) is not None else 0

    def __len__(self) -> int:
        return len(self._entries)
