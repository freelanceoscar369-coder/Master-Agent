"""Mission Brief 034 — deterministic retrieval.

> No vector DB. No embeddings. No AI search. Pure deterministic retrieval.

Which puts the whole burden on the ranking being *predictable*. A founder
who cannot guess why one result came first will stop trusting the second,
so almost every test here is about order: the same query returning the
same list, ties broken by a stated rule, and nothing matching that a
person would not expect to match.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from master_agent.memory.knowledge_store import InMemoryKnowledgeStore
from master_agent.memory.memory_index import MemoryIndex
from master_agent.memory.memory_models import (
    ARCHITECTURE_DECISIONS,
    CRITICAL,
    FAILURE_LIBRARY,
    HIGH,
    LOW,
    NORMAL,
    PROJECT_KNOWLEDGE,
    build,
)
from master_agent.memory.memory_query import (
    DEFAULT_LIMIT,
    SUMMARY_WEIGHT,
    TAG_WEIGHT,
    TEXT_WEIGHT,
    TITLE_WEIGHT,
    MemoryQuery,
    SearchHit,
)
from master_agent.memory.memory_service import MemoryService

BASE = datetime(2026, 7, 30, 9, 0, tzinfo=UTC)


def at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


def rec(number: int, **kwargs):
    defaults = {
        "id": f"mem-{number:06d}",
        "category": PROJECT_KNOWLEDGE,
        "title": f"Record {number}",
        "now": at(number),
    }
    defaults.update(kwargs)
    return build(**defaults)


def query_over(*records) -> MemoryQuery:
    by_id = {record.id: record for record in records}
    return MemoryQuery(by_id, MemoryIndex.build(records))


def service_with(*records) -> MemoryService:
    """A real service holding these records, for the delegation tests."""
    memory = MemoryService(store=InMemoryKnowledgeStore())
    memory.load()
    for record in records:
        memory.write(
            category=record.category,
            title=record.title,
            summary=record.summary,
            full_text=record.full_text,
            tags=record.tags,
            importance=record.importance,
            source=record.source,
        )
    return memory


# =========================================================================
# find_by_tag
# =========================================================================


def test_a_tag_finds_what_carries_it():
    found = query_over(rec(1, tags=["broker"]), rec(2, tags=["other"])).find_by_tag(
        "broker"
    )

    assert [r.id for r in found] == ["mem-000001"]


def test_a_tag_lookup_ignores_case_and_spacing():
    memory = query_over(rec(1, tags=["Two Words"]))

    assert memory.find_by_tag("two-words")
    assert memory.find_by_tag("TWO-WORDS")


def test_an_unknown_tag_finds_nothing():
    assert query_over(rec(1, tags=["broker"])).find_by_tag("nope") == ()


def test_a_tag_lookup_over_nothing_finds_nothing():
    assert query_over().find_by_tag("broker") == ()


def test_tag_results_are_most_important_first():
    found = query_over(
        rec(1, tags=["t"], importance=NORMAL),
        rec(2, tags=["t"], importance=CRITICAL),
        rec(3, tags=["t"], importance=LOW),
    ).find_by_tag("t")

    assert [r.importance for r in found] == [CRITICAL, NORMAL, LOW]


def test_equally_important_results_are_newest_first():
    found = query_over(rec(1, tags=["t"]), rec(2, tags=["t"])).find_by_tag("t")

    assert [r.id for r in found] == ["mem-000002", "mem-000001"]


def test_records_written_at_the_same_instant_still_have_a_fixed_order():
    """Two memories written in the same millisecond must not swap places
    between two runs of the same query."""
    found = query_over(
        rec(1, tags=["t"], now=BASE), rec(2, tags=["t"], now=BASE)
    ).find_by_tag("t")

    assert [r.id for r in found] == ["mem-000001", "mem-000002"]


# =========================================================================
# find_by_category
# =========================================================================


def test_a_category_finds_its_records():
    found = query_over(
        rec(1, category=ARCHITECTURE_DECISIONS), rec(2, category=FAILURE_LIBRARY)
    ).find_by_category(ARCHITECTURE_DECISIONS)

    assert [r.id for r in found] == ["mem-000001"]


def test_an_empty_category_finds_nothing():
    assert query_over(rec(1)).find_by_category(FAILURE_LIBRARY) == ()


def test_category_results_share_the_standard_ordering():
    """One ordering for every non-search lookup, so `find_by_tag` and
    `find_by_category` cannot drift into disagreeing about "first"."""
    found = query_over(
        rec(1, importance=NORMAL), rec(2, importance=CRITICAL)
    ).find_by_category(PROJECT_KNOWLEDGE)

    assert [r.id for r in found] == ["mem-000002", "mem-000001"]


# =========================================================================
# recent
# =========================================================================


def test_recent_is_newest_first():
    found = query_over(rec(1), rec(3), rec(2)).recent()

    assert [r.id for r in found] == ["mem-000003", "mem-000002", "mem-000001"]


def test_recent_respects_its_limit():
    assert len(query_over(rec(1), rec(2), rec(3)).recent(limit=2)) == 2


def test_recent_ignores_importance():
    """"What did I learn lately" is a question about time. Sorting it by
    importance would answer a different one."""
    found = query_over(rec(1, importance=CRITICAL), rec(2, importance=LOW)).recent()

    assert [r.id for r in found] == ["mem-000002", "mem-000001"]


@pytest.mark.parametrize("limit", [0, -1])
def test_asking_for_no_recent_records_returns_none(limit):
    assert query_over(rec(1)).recent(limit=limit) == ()


def test_recent_over_nothing_is_nothing():
    assert query_over().recent() == ()


def test_recent_has_a_sane_default_limit():
    assert DEFAULT_LIMIT > 0
    assert len(query_over(*[rec(n) for n in range(1, 30)]).recent()) == DEFAULT_LIMIT


# =========================================================================
# related — the graph, stored as ids
# =========================================================================


def test_a_record_finds_what_it_points_at():
    found = query_over(rec(1, related_items=["mem-000002"]), rec(2)).related("mem-000001")

    assert [r.id for r in found] == ["mem-000002"]


def test_a_record_finds_what_points_at_it():
    """The half a founder usually wants: *what else mentions this
    decision?* A one-way id list would only answer the other one."""
    found = query_over(rec(1), rec(2, related_items=["mem-000001"])).related("mem-000001")

    assert [r.id for r in found] == ["mem-000002"]


def test_a_record_is_never_in_its_own_results():
    found = query_over(rec(1, related_items=["mem-000001"])).related("mem-000001")

    assert found == ()


def test_an_unknown_record_has_no_relations():
    assert query_over(rec(1)).related("mem-999999") == ()


def test_a_link_to_a_record_that_does_not_exist_is_skipped():
    """A dangling id is a fact about a memory that was removed, not a
    crash."""
    assert query_over(rec(1, related_items=["mem-000404"])).related("mem-000001") == ()


def test_depth_one_stops_at_the_neighbours():
    found = query_over(
        rec(1, related_items=["mem-000002"]),
        rec(2, related_items=["mem-000003"]),
        rec(3),
    ).related("mem-000001")

    assert [r.id for r in found] == ["mem-000002"]


def test_depth_two_walks_one_hop_further():
    found = query_over(
        rec(1, related_items=["mem-000002"]),
        rec(2, related_items=["mem-000003"]),
        rec(3),
    ).related("mem-000001", depth=2)

    assert [r.id for r in found] == ["mem-000003", "mem-000002"]


def test_a_cycle_does_not_loop_forever():
    found = query_over(
        rec(1, related_items=["mem-000002"]), rec(2, related_items=["mem-000001"])
    ).related("mem-000001", depth=5)

    assert [r.id for r in found] == ["mem-000002"]


@pytest.mark.parametrize("depth", [0, -1])
def test_asking_for_no_depth_returns_nothing(depth):
    assert query_over(rec(1, related_items=["mem-000002"]), rec(2)).related(
        "mem-000001", depth=depth
    ) == ()


def test_relations_share_the_standard_ordering():
    found = query_over(
        rec(1, related_items=["mem-000002", "mem-000003"]),
        rec(2, importance=NORMAL),
        rec(3, importance=CRITICAL),
    ).related("mem-000001")

    assert [r.id for r in found] == ["mem-000003", "mem-000002"]


# =========================================================================
# critical
# =========================================================================


def test_critical_returns_only_what_must_not_be_forgotten():
    found = query_over(
        rec(1, importance=CRITICAL), rec(2, importance=HIGH), rec(3, importance=NORMAL)
    ).critical()

    assert [r.id for r in found] == ["mem-000001"]


def test_critical_over_nothing_is_nothing():
    assert query_over(rec(1)).critical() == ()


def test_critical_results_are_newest_first():
    found = query_over(
        rec(1, importance=CRITICAL), rec(2, importance=CRITICAL)
    ).critical()

    assert [r.id for r in found] == ["mem-000002", "mem-000001"]


# =========================================================================
# search — the ranking
# =========================================================================


def test_search_finds_a_word_in_the_title():
    found = query_over(rec(1, title="The broker decision"), rec(2)).search("broker")

    assert [r.id for r in found] == ["mem-000001"]


def test_search_finds_a_word_in_the_body():
    found = query_over(rec(1, title="Something", full_text="mentions docker")).search(
        "docker"
    )

    assert len(found) == 1


def test_search_finds_a_tag():
    assert len(query_over(rec(1, tags=["verification"])).search("verification")) == 1


def test_search_is_case_insensitive():
    assert len(query_over(rec(1, title="Broker")).search("BROKER")) == 1


def test_search_ignores_punctuation():
    assert len(query_over(rec(1, title="Broker, decided")).search("broker!")) == 1


def test_search_finds_nothing_for_a_word_nobody_wrote():
    assert query_over(rec(1, title="Broker")).search("elephant") == ()


def test_search_never_matches_approximately():
    """No stemming, no similarity. "fail" not matching "failure" is a
    surprise a founder can see and work around; a stemmer matching the
    wrong thing is one they cannot."""
    assert query_over(rec(1, title="A failure")).search("fail") == ()


@pytest.mark.parametrize("query", ["", "   ", "a", "the"])
def test_a_query_with_no_usable_words_finds_nothing(query):
    assert query_over(rec(1, title="Broker")).search(query) == ()


def test_search_respects_its_limit():
    records = [rec(n, title=f"Broker {n}") for n in range(1, 6)]

    assert len(query_over(*records).search("broker", limit=2)) == 2


@pytest.mark.parametrize("limit", [0, -1])
def test_asking_for_no_results_returns_none(limit):
    assert query_over(rec(1, title="Broker")).search("broker", limit=limit) == ()


def test_a_tag_match_outranks_a_title_match():
    """Somebody chose that word to file it under."""
    found = query_over(
        rec(1, title="broker mentioned"), rec(2, title="Unrelated", tags=["broker"])
    ).search("broker")

    assert [r.id for r in found] == ["mem-000002", "mem-000001"]


def test_a_title_match_outranks_a_body_match():
    found = query_over(
        rec(1, title="Nothing", full_text="the broker is mentioned here"),
        rec(2, title="The broker", full_text="nothing"),
    ).search("broker")

    assert [r.id for r in found] == ["mem-000002", "mem-000001"]


def test_the_weights_are_ordered_the_way_the_table_says():
    assert TAG_WEIGHT > TITLE_WEIGHT > SUMMARY_WEIGHT > TEXT_WEIGHT


def test_matching_two_words_beats_matching_one():
    found = query_over(
        rec(1, title="broker"), rec(2, title="broker verification")
    ).search("broker verification")

    assert [r.id for r in found] == ["mem-000002", "mem-000001"]


def test_an_equal_score_is_broken_by_importance():
    found = query_over(
        rec(1, title="Broker", importance=NORMAL),
        rec(2, title="Broker", importance=CRITICAL),
    ).search("broker")

    assert [r.id for r in found] == ["mem-000002", "mem-000001"]


def test_an_equal_score_and_importance_is_broken_by_recency():
    found = query_over(rec(1, title="Broker"), rec(2, title="Broker")).search("broker")

    assert [r.id for r in found] == ["mem-000002", "mem-000001"]


def test_everything_equal_is_broken_by_id():
    found = query_over(
        rec(1, title="Broker", now=BASE), rec(2, title="Broker", now=BASE)
    ).search("broker")

    assert [r.id for r in found] == ["mem-000001", "mem-000002"]


def test_the_same_query_returns_the_same_order_every_time():
    """The whole point of "deterministic retrieval"."""
    records = [rec(n, title=f"Broker note {n}", tags=["broker"]) for n in range(1, 8)]
    memory = query_over(*records)

    assert [r.id for r in memory.search("broker")] == [
        r.id for r in memory.search("broker")
    ]


def test_the_order_does_not_depend_on_insertion_order():
    forwards = query_over(rec(1, title="Broker"), rec(2, title="Broker"))
    backwards = query_over(rec(2, title="Broker"), rec(1, title="Broker"))

    assert [r.id for r in forwards.search("broker")] == [
        r.id for r in backwards.search("broker")
    ]


# ---- the scores, exposed ------------------------------------------------


def test_a_hit_carries_the_arithmetic_that_produced_it():
    """So "why did that come first?" is answerable without re-running
    anything — the same reason a `BrokerDecision` carries its
    candidates."""
    hit = query_over(
        rec(1, title="Broker", summary="a summary", full_text="a body", tags=["broker"])
    ).search_hits("broker")[0]

    assert isinstance(hit, SearchHit)
    assert hit.score == TAG_WEIGHT + TITLE_WEIGHT
    assert hit.matched == ("broker",)
    assert hit.id == "mem-000001"


def test_a_hit_reports_only_the_words_that_matched():
    hit = query_over(rec(1, title="Broker")).search_hits("broker elephant")[0]

    assert hit.matched == ("broker",)


def test_a_word_in_every_field_scores_every_weight():
    hit = query_over(
        rec(1, title="broker", summary="broker", full_text="broker", tags=["broker"])
    ).search_hits("broker")[0]

    assert hit.score == TAG_WEIGHT + TITLE_WEIGHT + SUMMARY_WEIGHT + TEXT_WEIGHT


def test_search_hits_and_search_agree():
    memory = query_over(rec(1, title="Broker"), rec(2, title="Broker note"))

    assert [hit.record for hit in memory.search_hits("broker")] == list(
        memory.search("broker")
    )


def test_search_hits_respect_the_limit():
    records = [rec(n, title="Broker") for n in range(1, 5)]

    assert len(query_over(*records).search_hits("broker", limit=1)) == 1


def test_a_query_with_no_words_produces_no_hits():
    assert query_over(rec(1, title="Broker")).search_hits("") == ()


def test_an_index_pointing_at_a_missing_record_is_skipped():
    """A stale index must degrade to "fewer results", never to a crash."""
    records = {"mem-000001": rec(1, title="Broker")}
    index = MemoryIndex.build([rec(1, title="Broker"), rec(2, title="Broker gone")])

    assert [r.id for r in MemoryQuery(records, index).search("broker")] == ["mem-000001"]


def test_a_stale_index_never_invents_a_result_for_the_other_lookups():
    records = {"mem-000001": rec(1, tags=["t"])}
    index = MemoryIndex.build([rec(1, tags=["t"]), rec(2, tags=["t"])])

    assert [r.id for r in MemoryQuery(records, index).find_by_tag("t")] == ["mem-000001"]


# =========================================================================
# The service delegates all six, unchanged
# =========================================================================


def test_the_service_offers_every_lookup_mb034_names():
    memory = MemoryService()

    for name in (
        "find_by_tag",
        "find_by_category",
        "recent",
        "related",
        "search",
        "critical",
    ):
        assert callable(getattr(memory, name)), name


def test_the_service_search_matches_the_query_object():
    memory = service_with(
        rec(1, title="Broker architecture", tags=["broker"]),
        rec(2, title="Unrelated"),
    )

    assert [r.title for r in memory.search("broker")] == ["Broker architecture"]


def test_the_service_finds_by_tag():
    memory = service_with(rec(1, tags=["broker"]))

    assert len(memory.find_by_tag("broker")) == 1


def test_the_service_finds_by_category():
    memory = service_with(rec(1, category=ARCHITECTURE_DECISIONS))

    assert len(memory.find_by_category(ARCHITECTURE_DECISIONS)) == 1


def test_the_service_lists_the_recent_ones():
    memory = service_with(rec(1), rec(2))

    assert len(memory.recent(1)) == 1


def test_the_service_returns_the_critical_ones():
    memory = service_with(rec(1, importance=CRITICAL), rec(2))

    assert len(memory.critical()) == 1


def test_the_service_walks_relations():
    memory = MemoryService(store=InMemoryKnowledgeStore())
    memory.load()
    first = memory.remember("First thing").id
    second = memory.remember("Second thing").id
    memory.link(second, first)

    assert [r.id for r in memory.related(first)] == [second]


def test_the_service_exposes_the_scores_too():
    memory = service_with(rec(1, title="Broker architecture", tags=["broker"]))

    hits = memory.search_hits("broker")

    assert hits[0].score > 0
    assert hits[0].matched == ("broker",)
    assert [hit.record for hit in hits] == list(memory.search("broker"))


def test_an_id_this_build_did_not_write_is_still_ordered():
    """A memory imported by hand is still a memory. It sorts first rather
    than raising."""
    from master_agent.memory.memory_service import _number

    assert _number("mem-000007") == 7
    assert _number("hand-written") == 0


def test_the_service_lists_its_tags():
    memory = service_with(rec(1, tags=["b", "a"]))

    assert memory.tags() == ("a", "b")


def test_the_query_view_is_never_stale():
    """`query` is a live view over the service's records, not a copy taken
    at the moment it was asked for — so a caller holding one cannot
    silently read yesterday's memory."""
    memory = MemoryService(store=InMemoryKnowledgeStore())
    memory.load()
    held = memory.query

    memory.remember("A new thing")

    assert len(held.recent()) == 1
    assert len(memory.query.recent()) == 1


# ---- links ---------------------------------------------------------------


def test_linking_two_memories_makes_a_graph():
    memory = MemoryService(store=InMemoryKnowledgeStore())
    memory.load()
    a = memory.remember("Decision A").id
    b = memory.remember("Decision B").id

    memory.link(a, b)

    assert memory.get(a).related_items == (b,)
    assert [r.id for r in memory.related(b)] == [a], "walkable both ways"


def test_linking_the_same_pair_twice_adds_one_edge():
    memory = MemoryService(store=InMemoryKnowledgeStore())
    memory.load()
    a = memory.remember("A").id
    b = memory.remember("B").id

    memory.link(a, b)
    memory.link(a, b)

    assert memory.get(a).related_items == (b,)


def test_a_memory_cannot_be_linked_to_itself():
    memory = MemoryService(store=InMemoryKnowledgeStore())
    memory.load()
    a = memory.remember("A").id

    assert memory.link(a, a) is None


@pytest.mark.parametrize(
    ("source", "target"), [("mem-999999", "real"), ("real", "mem-999999")]
)
def test_linking_something_that_does_not_exist_does_nothing(source, target):
    memory = MemoryService(store=InMemoryKnowledgeStore())
    memory.load()
    real = memory.remember("A").id
    resolved = {"real": real}

    assert memory.link(resolved.get(source, source), resolved.get(target, target)) is None


def test_a_link_is_persisted():
    store = InMemoryKnowledgeStore()
    first = MemoryService(store=store)
    first.load()
    a = first.remember("A").id
    b = first.remember("B").id
    first.link(a, b)

    second = MemoryService(store=store)
    second.load()

    assert second.get(a).related_items == (b,)


def test_a_link_can_be_declared_when_the_memory_is_written():
    memory = MemoryService(store=InMemoryKnowledgeStore())
    memory.load()
    a = memory.remember("A").id

    b = memory.remember("B", related_items=[a])

    assert b.record.related_items == (a,)
    assert [r.id for r in memory.related(a)] == [b.id]


def test_relations_survive_a_reload_and_are_still_walkable_both_ways():
    store = InMemoryKnowledgeStore()
    first = MemoryService(store=store)
    first.load()
    a = first.remember("A").id
    first.remember("B", related_items=[a])

    second = MemoryService(store=store)
    second.load()

    assert [r.title for r in second.related(a)] == ["B"]
