"""Deterministic retrieval (Mission Brief 034).

Six lookups: by tag, by category, recent, related, search, critical.

> No vector DB. No embeddings. No AI search. Pure deterministic retrieval.

Which makes the ranking the only interesting part, and it is deliberately
one a founder can predict: **where** a word appears decides how much it
counts, and every tie is broken by a stated rule rather than by whatever
order a dictionary happened to be in.

| Match in | Weight | Why |
|---|---|---|
| tag | 8 | somebody chose that word to file it under |
| title | 4 | somebody chose that word to name it |
| summary | 2 | the opening of what they wrote |
| full text | 1 | the word is in there somewhere |

Ties break on importance, then recency, then id — so the same query
returns the same list in the same order forever, which is what "no
hallucinated memory" means in practice.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from master_agent.memory.memory_index import MemoryIndex
from master_agent.memory.memory_models import (
    CRITICAL,
    MemoryRecord,
    tokenise,
)

TAG_WEIGHT = 8
TITLE_WEIGHT = 4
SUMMARY_WEIGHT = 2
TEXT_WEIGHT = 1

#: What `recent()` and `search()` return when nobody says otherwise. Small,
#: because these answers are read on a terminal by a person.
DEFAULT_LIMIT = 10


@dataclass(frozen=True)
class SearchHit:
    """One result, with the arithmetic that produced it.

    The score is carried rather than hidden so "why did that come first?"
    is answerable without re-running anything — the same reason a
    `BrokerDecision` carries its candidates.
    """

    record: MemoryRecord
    score: int
    matched: tuple[str, ...] = ()

    @property
    def id(self) -> str:
        return self.record.id


class MemoryQuery:
    """Read-only lookups over a record set and its index.

    Holds no state of its own and mutates nothing: given the same records
    it answers the same way, which is what makes every test in
    `test_memory_query.py` a statement about the query rather than about
    the order things were inserted.
    """

    def __init__(self, records: dict[str, MemoryRecord], index: MemoryIndex) -> None:
        self._records = records
        self._index = index

    # ---- the six MB034 names --------------------------------------------

    def find_by_tag(self, tag: str) -> tuple[MemoryRecord, ...]:
        return self._ordered(self._index.tag(tag))

    def find_by_category(self, category: str) -> tuple[MemoryRecord, ...]:
        return self._ordered(self._index.category(category))

    def recent(self, limit: int = DEFAULT_LIMIT) -> tuple[MemoryRecord, ...]:
        """Newest first. Ties break on id descending, so two memories
        written in the same millisecond still come back in a fixed
        order."""
        if limit <= 0:
            return ()
        ordered = sorted(
            self._records.values(), key=lambda r: (r.created_at, r.id), reverse=True
        )
        return tuple(ordered[:limit])

    def related(self, record_id: str, depth: int = 1) -> tuple[MemoryRecord, ...]:
        """Everything this record points at, and everything pointing at it.

        Both directions, because a one-way id list is only half a graph and
        the half a founder wants is usually the other one — *"what else
        mentions this decision?"*. `depth` walks further out; the starting
        record is never in its own results.
        """
        if record_id not in self._records or depth < 1:
            return ()
        seen = {record_id}
        frontier = {record_id}
        for _ in range(depth):
            nxt: set[str] = set()
            for current in frontier:
                record = self._records.get(current)
                if record is not None:
                    nxt.update(record.related_items)
                nxt.update(self._index.links_to(current))
            frontier = {i for i in nxt if i not in seen and i in self._records}
            seen.update(frontier)
            if not frontier:
                break
        return self._ordered(sorted(seen - {record_id}))

    def search(self, query: str, limit: int = DEFAULT_LIMIT) -> tuple[MemoryRecord, ...]:
        """The founder's `memory <words>` command. Ranked, deterministic,
        and never approximate."""
        return tuple(hit.record for hit in self.search_hits(query, limit))

    def critical(self) -> tuple[MemoryRecord, ...]:
        """Everything that must not be forgotten, newest first."""
        return self._ordered(self._index.importance(CRITICAL))

    # ---- the ranking ------------------------------------------------------

    def search_hits(self, query: str, limit: int = DEFAULT_LIMIT) -> tuple[SearchHit, ...]:
        """`search()` with the scores attached."""
        tokens = tokenise(query)
        if not tokens or limit <= 0:
            return ()

        hits: list[SearchHit] = []
        for record_id in self._candidates(tokens):
            record = self._records.get(record_id)
            if record is None:
                continue
            score, matched = self._score(record, tokens)
            if score > 0:
                hits.append(SearchHit(record=record, score=score, matched=matched))

        hits.sort(
            key=lambda hit: (
                -hit.score,
                -hit.record.rank,
                -hit.record.created_at.timestamp(),
                hit.record.id,
            )
        )
        return tuple(hits[:limit])

    def _candidates(self, tokens: tuple[str, ...]) -> tuple[str, ...]:
        """Anything containing any of the words. Narrowed by the index so
        the scoring loop is over matches rather than over everything."""
        found: set[str] = set()
        for token in tokens:
            found.update(self._index.token(token))
            found.update(self._index.tag(token))
        return tuple(sorted(found))

    def _score(
        self, record: MemoryRecord, tokens: tuple[str, ...]
    ) -> tuple[int, tuple[str, ...]]:
        """Where a word appears decides what it is worth. Summed over the
        words that appear, so a query matching two of them beats one
        matching a single word twice as prominently."""
        title = set(tokenise(record.title))
        summary = set(tokenise(record.summary))
        body = set(tokenise(record.full_text))
        tags = set(record.tags)

        score = 0
        matched: list[str] = []
        for token in tokens:
            weight = 0
            if token in tags:
                weight += TAG_WEIGHT
            if token in title:
                weight += TITLE_WEIGHT
            if token in summary:
                weight += SUMMARY_WEIGHT
            if token in body:
                weight += TEXT_WEIGHT
            if weight:
                score += weight
                matched.append(token)
        return score, tuple(matched)

    # ---- shared ordering ---------------------------------------------------

    def _ordered(self, ids: Any) -> tuple[MemoryRecord, ...]:
        """One ordering for every non-search lookup: most important first,
        then newest, then id.

        Shared so `find_by_tag` and `find_by_category` cannot drift into
        disagreeing about what "first" means.
        """
        records = [self._records[i] for i in ids if i in self._records]
        records.sort(key=lambda r: (-r.rank, -r.created_at.timestamp(), r.id))
        return tuple(records)
