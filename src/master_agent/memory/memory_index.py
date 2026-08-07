"""The index — what makes retrieval fast, and what makes it derived
(Mission Brief 034).

Six maps over the record set: tag, category, importance, source, search
token, and content digest. Plus backlinks, so a graph stored as one-way id
lists can be walked both ways.

**Everything here is derivable from the records.** That is the load-bearing
property: `index.json` is a cache, so a missing, stale or corrupt index is
never a data loss — it is rebuilt. The alternative (an index that holds
something the records do not) would mean two sources of truth for what
Kalpavriksha knows, and the one on disk would win by accident.

Every lookup returns ids in a deterministic order, because MB034 asks for
deterministic retrieval and "the order the dict happened to be in" is not
one.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from master_agent.memory.memory_models import MemoryRecord

#: Bumped if the index's shape changes. A version this build does not
#: understand is a rebuild, not an error -- the records are authoritative.
INDEX_VERSION = 1


@dataclass
class MemoryIndex:
    """Lookups over a record set. Mutable, because it is a cache that gets
    updated; never authoritative, because it is a cache."""

    by_tag: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    by_category: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    by_importance: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    by_source: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    by_token: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    #: digest -> id. One entry per distinct thing known, which is what
    #: makes duplicate suppression a lookup rather than a scan.
    by_digest: dict[str, str] = field(default_factory=dict)
    #: id -> ids that point *at* it. The other half of the graph.
    backlinks: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))

    # ---- building -------------------------------------------------------

    def add(self, record: MemoryRecord) -> None:
        self.by_category[record.category].add(record.id)
        self.by_importance[record.importance].add(record.id)
        self.by_source[record.source].add(record.id)
        for tag in record.tags:
            self.by_tag[tag].add(record.id)
        for token in record.tokens():
            self.by_token[token].add(record.id)
        self.by_digest.setdefault(record.digest(), record.id)
        for related in record.related_items:
            self.backlinks[related].add(record.id)

    def remove(self, record: MemoryRecord) -> None:
        """Take a record out of every map. Needed because an *update* is a
        remove and an add: a record whose tags changed would otherwise
        stay findable under the old ones forever."""
        for mapping, key in (
            (self.by_category, record.category),
            (self.by_importance, record.importance),
            (self.by_source, record.source),
        ):
            mapping.get(key, set()).discard(record.id)
        for tag in record.tags:
            self.by_tag.get(tag, set()).discard(record.id)
        for token in record.tokens():
            self.by_token.get(token, set()).discard(record.id)
        if self.by_digest.get(record.digest()) == record.id:
            self.by_digest.pop(record.digest(), None)
        for related in record.related_items:
            self.backlinks.get(related, set()).discard(record.id)

    def replace(self, old: MemoryRecord, new: MemoryRecord) -> None:
        self.remove(old)
        self.add(new)

    @classmethod
    def build(cls, records: Any) -> MemoryIndex:
        """Rebuild from the records. The repair path, and the only thing
        that needs to be correct for a corrupt index to cost nothing."""
        index = cls()
        for record in records:
            index.add(record)
        return index

    # ---- reading --------------------------------------------------------

    def tag(self, tag: str) -> tuple[str, ...]:
        return _sorted(self.by_tag.get((tag or "").strip().lower(), ()))

    def category(self, category: str) -> tuple[str, ...]:
        return _sorted(self.by_category.get(category, ()))

    def importance(self, importance: str) -> tuple[str, ...]:
        return _sorted(self.by_importance.get(importance, ()))

    def source(self, source: str) -> tuple[str, ...]:
        return _sorted(self.by_source.get(source, ()))

    def token(self, token: str) -> tuple[str, ...]:
        return _sorted(self.by_token.get((token or "").strip().lower(), ()))

    def links_to(self, record_id: str) -> tuple[str, ...]:
        return _sorted(self.backlinks.get(record_id, ()))

    def duplicate_of(self, digest: str) -> str | None:
        return self.by_digest.get(digest)

    def tag_counts(self) -> tuple[tuple[str, int], ...]:
        """Every tag with how many records carry it, most used first.

        Ties break alphabetically rather than by insertion, so "Top Tags"
        on the Dashboard is the same list every time it is drawn.
        """
        counts = [(tag, len(ids)) for tag, ids in self.by_tag.items() if ids]
        return tuple(sorted(counts, key=lambda pair: (-pair[1], pair[0])))

    def known_tags(self) -> tuple[str, ...]:
        return tuple(sorted(tag for tag, ids in self.by_tag.items() if ids))

    # ---- persistence ----------------------------------------------------

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": INDEX_VERSION,
            "by_tag": _dump(self.by_tag),
            "by_category": _dump(self.by_category),
            "by_importance": _dump(self.by_importance),
            "by_source": _dump(self.by_source),
            "by_token": _dump(self.by_token),
            "by_digest": dict(sorted(self.by_digest.items())),
            "backlinks": _dump(self.backlinks),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryIndex:
        """Load an index, or return an empty one for anything unexpected.

        Never raises. An index is a cache; the caller's fallback is to
        rebuild, and making that path depend on the cache being well-formed
        would defeat the point of having it.
        """
        index = cls()
        if not isinstance(data, dict) or data.get("version") != INDEX_VERSION:
            return index
        index.by_tag = _load(data.get("by_tag"))
        index.by_category = _load(data.get("by_category"))
        index.by_importance = _load(data.get("by_importance"))
        index.by_source = _load(data.get("by_source"))
        index.by_token = _load(data.get("by_token"))
        index.backlinks = _load(data.get("backlinks"))
        digests = data.get("by_digest")
        index.by_digest = (
            {str(k): str(v) for k, v in digests.items()}
            if isinstance(digests, dict)
            else {}
        )
        return index

    def matches(self, records: Any) -> bool:
        """Does this index describe exactly these records?

        Used at load time to decide whether the cache on disk can be
        trusted or has to be rebuilt. Compares the whole thing rather than
        a count, because an index with the right number of wrong entries is
        the failure that would be hardest to notice.
        """
        return self.as_dict() == MemoryIndex.build(records).as_dict()


def _sorted(ids: Any) -> tuple[str, ...]:
    return tuple(sorted(ids))


def _dump(mapping: dict[str, set[str]]) -> dict[str, list[str]]:
    return {
        key: sorted(values)
        for key, values in sorted(mapping.items())
        if values
    }


def _load(raw: Any) -> dict[str, set[str]]:
    loaded: dict[str, set[str]] = defaultdict(set)
    if isinstance(raw, dict):
        for key, values in raw.items():
            if isinstance(values, list):
                loaded[str(key)] = {str(value) for value in values}
    return loaded
