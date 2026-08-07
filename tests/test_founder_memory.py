"""Mission Brief 034 — the record, the index, and the store.

Founder Memory is the first thing in Kalpavriksha whose *only* job is to
be true later. So most of this file is about the boring half: that a
record round-trips byte for byte, that an index is always derivable from
the records, that a corrupt file is preserved rather than replaced, and
that saying the same thing twice is one memory rather than two.
"""
from __future__ import annotations

import ast
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from master_agent.memory.knowledge_store import (
    CORRUPT_SUFFIX,
    INDEX_FILENAME,
    KNOWLEDGE_FILENAME,
    MEMORY_DIRNAME,
    InMemoryKnowledgeStore,
    JsonKnowledgeStore,
    KnowledgeStore,
    LoadReport,
)
from master_agent.memory.memory_index import INDEX_VERSION, MemoryIndex
from master_agent.memory.memory_models import (
    ARCHITECTURE_DECISIONS,
    BUSINESS_DECISIONS,
    CATEGORIES,
    CRITICAL,
    FAILURE_LIBRARY,
    FOUNDER,
    FOUNDER_PREFERENCES,
    HIGH,
    IMPORTANCE,
    LOW,
    NORMAL,
    OPEN_QUESTIONS,
    PROJECT_KNOWLEDGE,
    PROMPT_LIBRARY,
    SOURCES,
    SUCCESS_LIBRARY,
    InvalidMemory,
    MemoryRecord,
    build,
    derive_summary,
    normalise_tags,
    tokenise,
)
from master_agent.memory.memory_service import MemoryService

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "src" / "master_agent" / "memory"
NEW_MODULES = sorted(
    PACKAGE_DIR / name
    for name in (
        "knowledge_store.py",
        "memory_models.py",
        "memory_service.py",
        "memory_query.py",
        "memory_index.py",
    )
)
WHEN = datetime(2026, 7, 30, 15, 0, tzinfo=UTC)


def record(**kwargs) -> MemoryRecord:
    defaults = {
        "id": "mem-000001",
        "category": FOUNDER_PREFERENCES,
        "title": "Prefer the local model",
        "full_text": "Prefer the local model unless quality demands otherwise.",
        "tags": ("broker", "model"),
        "now": WHEN,
    }
    defaults.update(kwargs)
    return build(**defaults)


def service(**kwargs) -> MemoryService:
    memory = MemoryService(store=InMemoryKnowledgeStore(), **kwargs)
    memory.load()
    return memory


# =========================================================================
# The vocabulary MB034 fixes
# =========================================================================


def test_there_are_exactly_ten_categories():
    assert len(CATEGORIES) == 10


@pytest.mark.parametrize(
    "category",
    [
        FOUNDER_PREFERENCES,
        BUSINESS_DECISIONS,
        ARCHITECTURE_DECISIONS,
        PROJECT_KNOWLEDGE,
        "Mission Outcomes",
        PROMPT_LIBRARY,
        FAILURE_LIBRARY,
        SUCCESS_LIBRARY,
        "Recurring Lessons",
        OPEN_QUESTIONS,
    ],
)
def test_every_category_mb034_names_exists(category):
    assert category in CATEGORIES


def test_the_categories_are_closed():
    """"No others" is a rule, not a suggestion: a free-text category would
    make `find_by_category` a guessing game within a month."""
    with pytest.raises(InvalidMemory):
        record(category="Random Thoughts")


def test_there_are_exactly_four_importance_levels():
    assert IMPORTANCE == (LOW, NORMAL, HIGH, CRITICAL)


def test_importance_is_closed():
    with pytest.raises(InvalidMemory):
        record(importance="URGENT")


def test_there_are_exactly_six_sources():
    assert set(SOURCES) == {
        "Founder",
        "Mission",
        "Verification",
        "Executive",
        "Broker",
        "Recovery",
    }


def test_sources_are_closed():
    with pytest.raises(InvalidMemory):
        record(source="Somebody")


def test_importance_ranks_in_the_order_it_is_written():
    assert record(importance=LOW).rank < record(importance=NORMAL).rank
    assert record(importance=HIGH).rank < record(importance=CRITICAL).rank


def test_only_critical_is_critical():
    assert record(importance=CRITICAL).is_critical is True
    assert record(importance=HIGH).is_critical is False


# =========================================================================
# The record
# =========================================================================


@pytest.mark.parametrize(
    "field",
    [
        "id",
        "category",
        "title",
        "summary",
        "full_text",
        "created_at",
        "updated_at",
        "tags",
        "source",
        "importance",
        "confidence",
        "related_items",
    ],
)
def test_a_record_carries_every_field_mb034_names(field):
    assert hasattr(record(), field)


def test_a_record_is_frozen():
    """A memory describes something that was true when it was written;
    editing one in place would make `updated_at` a lie."""
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        record().title = "something else"  # type: ignore[misc]


def test_a_memory_with_no_title_is_refused():
    """It could never be found again."""
    with pytest.raises(InvalidMemory):
        record(title="   ")


def test_a_title_is_collapsed_to_single_spaces():
    assert record(title="  too    many   spaces ").title == "too many spaces"


def test_full_text_falls_back_to_the_title():
    """A memory always has a body, so search never has to special-case
    one that does not."""
    assert record(title="Just this", full_text="").full_text == "Just this"


def test_a_summary_is_derived_when_none_is_given():
    written = record(full_text="First sentence here. Second one follows.", summary="")

    assert written.summary == "First sentence here."


def test_a_given_summary_is_kept():
    assert record(summary="my own words").summary == "my own words"


def test_a_decimal_point_is_not_a_sentence_ending():
    """The first version turned "exceeds 0.9" into "exceeds 0.9." -- a full
    stop the founder did not type."""
    assert derive_summary("Use Gemma unless quality exceeds 0.9") == (
        "Use Gemma unless quality exceeds 0.9"
    )


def test_a_long_body_is_cut_at_a_word_boundary():
    summary = derive_summary("word " * 100, limit=20)

    assert summary.endswith("...")
    assert len(summary) <= 23
    assert "wor..." not in summary


def test_nothing_summarises_to_nothing():
    assert derive_summary("") == ""
    assert derive_summary("   ") == ""


def test_a_short_body_is_its_own_summary():
    assert derive_summary("short") == "short"


def test_deriving_a_summary_never_asks_a_model():
    """MB034 forbids LLM summarisation. Truncating the founder's own
    opening words is the honest alternative, and the full text is always
    underneath."""
    body = "Docker was not running so verification failed"

    assert derive_summary(body) in body


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        (["B", "a"], ("a", "b")),
        (["dup", "DUP"], ("dup",)),
        (["  spaced  "], ("spaced",)),
        (["two words"], ("two-words",)),
        ([""], ()),
        (None, ()),
    ],
)
def test_tags_are_normalised(given, expected):
    """Sorted and de-duplicated, so two records tagged the same way in a
    different order are the same record."""
    assert normalise_tags(given) == expected


def test_confidence_is_clamped_to_a_probability():
    assert record(confidence=5.0).confidence == 1.0
    assert record(confidence=-1.0).confidence == 0.0


def test_confidence_defaults_to_certain():
    """Everything in this build is stated or observed. The field exists
    for inference, and nothing infers yet."""
    assert record().confidence == 1.0


def test_related_items_are_sorted_and_deduplicated():
    assert record(related_items=["b", "a", "b"]).related_items == ("a", "b")


def test_a_record_round_trips_through_plain_data():
    original = record(importance=HIGH, related_items=["mem-000002"], confidence=0.5)

    assert MemoryRecord.from_dict(original.as_dict()) == original


def test_a_record_read_back_is_never_re_validated():
    """History must not become unreadable because the vocabulary grew.
    Validation happens at `build()`; `from_dict` accepts what is on
    disk."""
    rebuilt = MemoryRecord.from_dict(
        {
            "id": "mem-000009",
            "category": "A Category From The Future",
            "title": "still readable",
            "created_at": WHEN.isoformat(),
            "updated_at": WHEN.isoformat(),
        }
    )

    assert rebuilt.category == "A Category From The Future"


def test_a_naive_timestamp_is_read_as_utc():
    rebuilt = MemoryRecord.from_dict(
        {"id": "x", "category": PROJECT_KNOWLEDGE, "title": "t",
         "created_at": "2026-07-30T15:00:00", "updated_at": "2026-07-30T15:00:00"}
    )

    assert rebuilt.created_at.tzinfo is not None


def test_a_missing_timestamp_is_stamped_rather_than_crashing():
    rebuilt = MemoryRecord.from_dict({"id": "x", "category": PROJECT_KNOWLEDGE, "title": "t"})

    assert rebuilt.created_at is not None


def test_updating_a_record_restamps_it_and_keeps_when_it_was_written():
    """`created_at` is when the founder said it; `updated_at` is when it
    last changed. Conflating them would lose the first fact, which is the
    one that orders the history."""
    original = record()

    updated = original.with_update(importance=CRITICAL)

    assert updated.importance == CRITICAL
    assert updated.created_at == original.created_at
    assert updated.updated_at != original.updated_at


def test_updating_normalises_what_it_is_given():
    updated = record().with_update(tags=["Z", "a"], related_items=["b", "a"])

    assert updated.tags == ("a", "z")
    assert updated.related_items == ("a", "b")


def test_the_searchable_text_is_title_summary_and_body():
    text = record(title="T", summary="S", full_text="F").text

    assert "T" in text and "S" in text and "F" in text


# ---- the digest, and duplicate suppression ------------------------------


def test_the_same_statement_digests_the_same_way():
    assert record().digest() == record(id="mem-000099").digest()


def test_the_digest_ignores_whitespace_and_case():
    assert record(title="Prefer THE local   model").digest() == record().digest()


@pytest.mark.parametrize("changed", [{"category": PROJECT_KNOWLEDGE}, {"title": "Other"}])
def test_a_different_statement_digests_differently(changed):
    assert record(**changed).digest() != record().digest()


def test_the_digest_ignores_tags_and_importance():
    """Saying the same thing again with a new tag is the same memory.
    Otherwise "how many things do I know" counts how often the founder
    repeated themselves."""
    assert record(tags=["new"], importance=CRITICAL).digest() == record().digest()


# ---- tokenising ---------------------------------------------------------


def test_tokenising_lowercases_and_splits_on_punctuation():
    assert tokenise("Broker, Verification!") == ("broker", "verification")


def test_single_characters_are_dropped():
    assert "a" not in tokenise("a broker")


def test_common_words_are_dropped():
    assert tokenise("the broker and the plan") == ("broker", "plan")


def test_tokens_keep_first_appearance_order_without_duplicates():
    assert tokenise("broker broker plan") == ("broker", "plan")


def test_numbers_are_searchable():
    """`memory mb031` has to find the brief it names."""
    assert "mb031" in tokenise("Broker architecture completed in MB031")


def test_tokenising_nothing_yields_nothing():
    assert tokenise("") == ()
    assert tokenise(None) == ()


# =========================================================================
# The index
# =========================================================================


def test_an_index_finds_a_record_by_every_axis():
    index = MemoryIndex.build([record()])

    assert index.tag("broker") == ("mem-000001",)
    assert index.category(FOUNDER_PREFERENCES) == ("mem-000001",)
    assert index.importance(NORMAL) == ("mem-000001",)
    assert index.source(FOUNDER) == ("mem-000001",)
    assert index.token("local") == ("mem-000001",)


def test_a_tag_lookup_is_case_insensitive():
    assert MemoryIndex.build([record()]).tag("BROKER") == ("mem-000001",)


def test_an_unknown_key_finds_nothing_rather_than_raising():
    index = MemoryIndex.build([record()])

    assert index.tag("nope") == ()
    assert index.category("Mission Outcomes") == ()
    assert index.token("nope") == ()
    assert index.links_to("nope") == ()


def test_ids_come_back_in_a_deterministic_order():
    index = MemoryIndex.build(
        [record(id="mem-000003"), record(id="mem-000001", title="A"), record(id="mem-000002", title="B")]
    )

    assert index.category(FOUNDER_PREFERENCES) == (
        "mem-000001",
        "mem-000002",
        "mem-000003",
    )


def test_removing_a_record_takes_it_out_of_every_map():
    one = record()
    index = MemoryIndex.build([one])

    index.remove(one)

    assert index.tag("broker") == ()
    assert index.category(FOUNDER_PREFERENCES) == ()
    assert index.duplicate_of(one.digest()) is None


def test_replacing_a_record_stops_the_old_tags_finding_it():
    """An update is a remove and an add. Without that, a record whose tags
    changed stays findable under the old ones forever."""
    one = record()
    index = MemoryIndex.build([one])
    two = one.with_update(tags=["renamed"])

    index.replace(one, two)

    assert index.tag("broker") == ()
    assert index.tag("renamed") == ("mem-000001",)


def test_backlinks_make_the_graph_walkable_both_ways():
    index = MemoryIndex.build([record(id="mem-000002", related_items=["mem-000001"])])

    assert index.links_to("mem-000001") == ("mem-000002",)


def test_a_digest_maps_to_the_first_record_that_said_it():
    one = record()
    index = MemoryIndex.build([one, record(id="mem-000002")])

    assert index.duplicate_of(one.digest()) == "mem-000001"


def test_tag_counts_are_most_used_first_then_alphabetical():
    index = MemoryIndex.build(
        [
            record(id="mem-000001", tags=["common", "zebra"]),
            record(id="mem-000002", title="Other", tags=["common", "alpha"]),
        ]
    )

    assert index.tag_counts() == (("common", 2), ("alpha", 1), ("zebra", 1))


def test_known_tags_are_sorted():
    index = MemoryIndex.build([record(tags=["z", "a"])])

    assert index.known_tags() == ("a", "z")


def test_an_emptied_tag_disappears_from_the_counts():
    one = record()
    index = MemoryIndex.build([one])
    index.remove(one)

    assert index.tag_counts() == ()
    assert index.known_tags() == ()


def test_an_index_round_trips_through_plain_data():
    index = MemoryIndex.build([record(related_items=["mem-000002"])])

    assert MemoryIndex.from_dict(index.as_dict()).as_dict() == index.as_dict()


def test_an_index_from_a_future_version_is_discarded_rather_than_guessed():
    payload = MemoryIndex.build([record()]).as_dict()
    payload["version"] = INDEX_VERSION + 1

    assert MemoryIndex.from_dict(payload).tag("broker") == ()


@pytest.mark.parametrize("junk", [None, "not a dict", [], {"version": None}])
def test_a_junk_index_loads_as_an_empty_one_rather_than_raising(junk):
    """An index is a cache; the caller's fallback is to rebuild, and that
    path must not depend on the cache being well-formed."""
    assert MemoryIndex.from_dict(junk).known_tags() == ()


def test_an_index_knows_whether_it_describes_a_record_set():
    records = [record()]
    index = MemoryIndex.build(records)

    assert index.matches(records) is True
    assert index.matches([*records, record(id="mem-000002", title="New")]) is False


def test_an_index_with_the_right_size_but_wrong_contents_does_not_match():
    """The failure hardest to notice, which is why equality is the test
    rather than a count."""
    index = MemoryIndex.build([record(id="mem-000001")])

    assert index.matches([record(id="mem-000002")]) is False


# =========================================================================
# The store
# =========================================================================


def test_both_stores_satisfy_the_protocol():
    assert isinstance(InMemoryKnowledgeStore(), KnowledgeStore)
    assert isinstance(JsonKnowledgeStore(Path(".")), KnowledgeStore)


def test_memory_lives_beside_state_not_inside_it(tmp_path):
    """A recovery may legitimately discard operational state. Losing what
    the founder said because a mission crashed would be the worst possible
    reading of "recovery"."""
    store = JsonKnowledgeStore(tmp_path)

    assert store.directory == tmp_path / MEMORY_DIRNAME
    assert store.knowledge_path.name == KNOWLEDGE_FILENAME
    assert store.index_path.name == INDEX_FILENAME


def test_an_empty_machine_loads_as_an_empty_memory(tmp_path):
    report = JsonKnowledgeStore(tmp_path).load()

    assert report.records == []
    assert report.ok is True
    assert report.index is not None


def test_records_survive_a_save_and_load(tmp_path):
    store = JsonKnowledgeStore(tmp_path)
    one = record(related_items=["mem-000002"], importance=HIGH)
    store.save([one], MemoryIndex.build([one]))

    report = JsonKnowledgeStore(tmp_path).load()

    assert report.records == [one]
    assert report.ok is True


def test_the_index_survives_too_and_is_not_rebuilt(tmp_path):
    store = JsonKnowledgeStore(tmp_path)
    one = record()
    store.save([one], MemoryIndex.build([one]))

    report = JsonKnowledgeStore(tmp_path).load()

    assert report.rebuilt_index is False
    assert report.index.tag("broker") == ("mem-000001",)


def test_a_missing_index_is_rebuilt_from_the_records(tmp_path):
    store = JsonKnowledgeStore(tmp_path)
    one = record()
    store.save([one], MemoryIndex.build([one]))
    store.index_path.unlink()

    report = JsonKnowledgeStore(tmp_path).load()

    assert report.rebuilt_index is True
    assert report.index.tag("broker") == ("mem-000001",)


@pytest.mark.parametrize("junk", ["not json", "[]", '{"version": 99}'])
def test_a_corrupt_index_costs_nothing(junk, tmp_path):
    store = JsonKnowledgeStore(tmp_path)
    one = record()
    store.save([one], MemoryIndex.build([one]))
    store.index_path.write_text(junk, encoding="utf-8")

    report = JsonKnowledgeStore(tmp_path).load()

    assert report.records == [one]
    assert report.rebuilt_index is True
    assert report.ok is True, "a rebuilt cache is not a problem worth reporting"


def test_a_stale_index_is_rebuilt(tmp_path):
    """An index describing yesterday's records is worse than none."""
    store = JsonKnowledgeStore(tmp_path)
    store.save([record()], MemoryIndex.build([record(id="mem-000009", title="Other")]))

    report = JsonKnowledgeStore(tmp_path).load()

    assert report.rebuilt_index is True
    assert report.index.matches(report.records)


def test_a_corrupt_knowledge_file_is_preserved_never_overwritten(tmp_path):
    """A founder can open a `.corrupt` file and copy their notes out. They
    cannot recover a file this program replaced."""
    store = JsonKnowledgeStore(tmp_path)
    store.save([record()], MemoryIndex())
    store.knowledge_path.write_text("{ broken", encoding="utf-8")

    report = JsonKnowledgeStore(tmp_path).load()

    assert report.records == []
    assert report.ok is False
    assert CORRUPT_SUFFIX in report.corrupted
    assert (store.directory / report.corrupted).read_text(encoding="utf-8") == "{ broken"


def test_a_second_corruption_does_not_overwrite_the_first(tmp_path):
    store = JsonKnowledgeStore(tmp_path)
    store.knowledge_path.parent.mkdir(parents=True, exist_ok=True)
    store.knowledge_path.write_text("first breakage", encoding="utf-8")
    JsonKnowledgeStore(tmp_path).load()
    store.knowledge_path.write_text("second breakage", encoding="utf-8")

    second = JsonKnowledgeStore(tmp_path).load()

    assert "first breakage" in (store.directory / f"{KNOWLEDGE_FILENAME}{CORRUPT_SUFFIX}").read_text()
    assert "second breakage" in (store.directory / second.corrupted).read_text()


def test_a_knowledge_file_that_is_not_a_list_is_treated_as_corrupt(tmp_path):
    store = JsonKnowledgeStore(tmp_path)
    store.knowledge_path.parent.mkdir(parents=True, exist_ok=True)
    store.knowledge_path.write_text('{"records": "nope"}', encoding="utf-8")

    report = JsonKnowledgeStore(tmp_path).load()

    assert report.ok is False
    assert report.corrupted


def test_a_bare_list_of_records_is_still_readable(tmp_path):
    """Forward tolerance in the other direction: a hand-written file
    without the envelope still loads."""
    store = JsonKnowledgeStore(tmp_path)
    store.knowledge_path.parent.mkdir(parents=True, exist_ok=True)
    store.knowledge_path.write_text(
        json.dumps([record().as_dict()]), encoding="utf-8"
    )

    assert len(JsonKnowledgeStore(tmp_path).load().records) == 1


def test_one_unreadable_record_does_not_cost_the_others(tmp_path):
    """The same tolerance the event log applies to a truncated final
    line."""
    store = JsonKnowledgeStore(tmp_path)
    store.knowledge_path.parent.mkdir(parents=True, exist_ok=True)
    store.knowledge_path.write_text(
        json.dumps({"version": 1, "records": [{"no": "id"}, record().as_dict()]}),
        encoding="utf-8",
    )

    report = JsonKnowledgeStore(tmp_path).load()

    assert len(report.records) == 1
    assert report.skipped == 1
    assert report.ok is False, "silently dropping a memory is worth reporting"


def test_non_object_rows_are_ignored(tmp_path):
    store = JsonKnowledgeStore(tmp_path)
    store.knowledge_path.parent.mkdir(parents=True, exist_ok=True)
    store.knowledge_path.write_text(
        json.dumps({"version": 1, "records": ["junk", 7, record().as_dict()]}),
        encoding="utf-8",
    )

    assert len(JsonKnowledgeStore(tmp_path).load().records) == 1


def test_a_write_leaves_no_temporary_file_behind(tmp_path):
    store = JsonKnowledgeStore(tmp_path)
    store.save([record()], MemoryIndex())

    assert list(store.directory.glob("*.tmp")) == []


def test_a_failed_write_leaves_no_temporary_file_behind(tmp_path):
    """Atomic means atomic: the previous good file survives and the
    directory is not littered with attempts."""
    store = JsonKnowledgeStore(tmp_path)
    store.directory.mkdir(parents=True, exist_ok=True)
    (store.directory / KNOWLEDGE_FILENAME).mkdir()

    with pytest.raises(OSError):
        store.save([record()], MemoryIndex())

    assert list(store.directory.glob("*.tmp")) == []


def test_the_store_creates_its_directory_on_first_write(tmp_path):
    store = JsonKnowledgeStore(tmp_path / "nested" / "deeper")
    store.save([record()], MemoryIndex())

    assert store.knowledge_path.exists()


def test_the_load_report_says_what_happened(tmp_path):
    store = JsonKnowledgeStore(tmp_path)
    store.save([record()], MemoryIndex.build([record()]))

    report = JsonKnowledgeStore(tmp_path).load()

    assert "1 memory record(s)" in report.summary


def test_the_load_report_mentions_skipped_records(tmp_path):
    report = LoadReport(skipped=2, rebuilt_index=True, corrupted="knowledge.json.corrupt")

    assert "2 unreadable" in report.summary
    assert "index rebuilt" in report.summary
    assert "knowledge.json.corrupt" in report.summary


def test_the_in_memory_store_round_trips():
    store = InMemoryKnowledgeStore()
    one = record()
    store.save([one], MemoryIndex.build([one]))

    assert store.load().records == [one]


def test_the_in_memory_store_rebuilds_a_mismatched_index():
    store = InMemoryKnowledgeStore()
    store.save([record()], MemoryIndex.build([record(id="mem-000009", title="Other")]))

    assert store.load().rebuilt_index is True


def test_the_in_memory_store_skips_a_bad_row():
    store = InMemoryKnowledgeStore()
    store.rows = [{"no": "id"}]

    assert store.load().skipped == 1


# =========================================================================
# Duplicate suppression, through the service
# =========================================================================


def test_saying_the_same_thing_twice_is_one_memory():
    memory = service()
    memory.remember("Never delete logs automatically")

    second = memory.remember("Never delete logs automatically")

    assert second.created is False
    assert len(memory) == 1
    assert memory.duplicates_suppressed == 1


def test_a_suppressed_duplicate_does_not_consume_an_id():
    """Otherwise the ids grow with every repetition and the gaps are
    unexplainable."""
    memory = service()
    memory.remember("A thing")
    memory.remember("A thing")

    assert memory.remember("Another thing").id == "mem-000002"


def test_repeating_something_merges_its_tags():
    memory = service()
    memory.remember("A thing", tags=["first"])

    merged = memory.remember("A thing", tags=["second"])

    assert merged.record.tags == ("first", "second")


def test_repeating_something_can_raise_its_importance_but_never_lower_it():
    """A founder repeating a fact is usually emphasising it."""
    memory = service()
    memory.remember("A thing", importance=NORMAL)

    raised = memory.remember("A thing", importance=CRITICAL)
    assert raised.record.importance == CRITICAL

    again = memory.remember("A thing", importance=LOW)
    assert again.record.importance == CRITICAL


def test_repeating_something_stamps_it_as_updated():
    memory = service()
    first = memory.remember("A thing").record

    merged = memory.remember("A thing").record

    assert merged.created_at == first.created_at
    assert merged.updated_at >= first.updated_at


def test_the_same_words_in_a_different_category_are_two_memories():
    """The same sentence can be a preference and an architecture decision,
    and they are not the same fact."""
    memory = service()
    memory.remember("Use the local model", category=FOUNDER_PREFERENCES)
    memory.remember("Use the local model", category=ARCHITECTURE_DECISIONS)

    assert len(memory) == 2


def test_duplicate_suppression_survives_a_reload():
    store = InMemoryKnowledgeStore()
    first = MemoryService(store=store)
    first.load()
    first.remember("Never delete logs")

    second = MemoryService(store=store)
    second.load()
    again = second.remember("Never delete logs")

    assert again.created is False
    assert len(second) == 1


# =========================================================================
# Architecture purity
# =========================================================================

FORBIDDEN = (
    "openai",
    "anthropic",
    "httpx",
    "requests",
    "urllib",
    "socket",
    "subprocess",
    "numpy",
    "faiss",
    "chromadb",
    "pinecone",
    "sentence_transformers",
)


def _imported(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


@pytest.mark.parametrize("forbidden", FORBIDDEN)
def test_memory_imports_nothing_that_could_embed_or_call_a_model(forbidden):
    """MB034 forbids embeddings, vector search and LLM summarisation in
    eight separate words. A package that cannot import a client or a maths
    library cannot quietly grow one."""
    for path in NEW_MODULES:
        for name in _imported(path):
            assert not name.startswith(forbidden), f"{path.name} imports {name}"


@pytest.mark.parametrize(
    "forbidden", ["embed", "vector", "semantic", "similarity", "summarise_with"]
)
def test_memory_defines_no_approximate_retrieval(forbidden):
    """Checked on function names by AST, so the docstrings explaining the
    prohibition do not trip it."""
    for path in NEW_MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                assert forbidden not in node.name.lower(), f"{path.name}: {node.name}"


def test_memory_never_reaches_the_broker_or_a_provider():
    """It records what happened; it does not participate."""
    for path in NEW_MODULES:
        for name in _imported(path):
            assert not name.startswith("master_agent.broker")
            assert not name.startswith("master_agent.providers")
            assert not name.startswith("master_agent.ai_infrastructure")
            assert not name.startswith("master_agent.runtime")


def test_memory_touches_mission_control_only_through_its_event_types():
    """Automatic memory rides the existing bus. Importing anything else
    from Mission Control would make this a second coordination layer."""
    for path in NEW_MODULES:
        for name in _imported(path):
            if name.startswith("master_agent.mission_control"):
                assert name == "master_agent.mission_control.events", name


def test_only_the_store_touches_the_filesystem():
    """One door, the same discipline `persistence/store.py` and
    `desktop/probe.py` have."""
    for path in NEW_MODULES:
        if path.name == "knowledge_store.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id != "open", f"{path.name} opens a file"


def test_the_five_modules_mb034_names_all_exist():
    assert [path.name for path in NEW_MODULES] == [
        "knowledge_store.py",
        "memory_index.py",
        "memory_models.py",
        "memory_query.py",
        "memory_service.py",
    ]


def test_mb004s_memory_layers_were_left_alone():
    """MB034 composes beside MB004's mission memory rather than rewriting
    it — the brief's own instruction, and the reason `cli.py` still
    works."""
    for name in ("memory.py", "store.py", "conversation.py", "future.py"):
        assert (PACKAGE_DIR / name).exists()


def test_every_new_module_says_which_brief_it_serves():
    for path in NEW_MODULES:
        head = " ".join(path.read_text(encoding="utf-8")[:600].split())
        assert "Mission Brief 034" in head, path.name
