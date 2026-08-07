"""Mission Brief 034 — memory as the founder meets it.

The other two files test the parts. This one tests that Kalpavriksha
*accumulates*: that finishing a mission writes something down without
being asked, that `remember "..."` works from the console the founder
already has, that the Dashboard says what is known, and — the Definition
of Done — that all of it survives a restart without an LLM being involved
anywhere.
"""
from __future__ import annotations

import pytest

from master_agent.dashboard.charset import ASCII
from master_agent.dashboard.founder import as_dict as founder_as_dict
from master_agent.dashboard.founder import build_founder_view
from master_agent.dashboard.founder_panels import render_founder_frame, render_memory
from master_agent.dashboard.sources import DashboardSources
from master_agent.launcher.boot import build_system
from master_agent.launcher.console import FounderConsole
from master_agent.memory.knowledge_store import (
    KNOWLEDGE_FILENAME,
    MEMORY_DIRNAME,
    InMemoryKnowledgeStore,
    JsonKnowledgeStore,
)
from master_agent.memory.memory_models import (
    ARCHITECTURE_DECISIONS,
    BUSINESS_DECISIONS,
    CRITICAL,
    FAILURE_LIBRARY,
    FOUNDER,
    FOUNDER_PREFERENCES,
    HIGH,
    MISSION,
    MISSION_OUTCOMES,
    NORMAL,
    PROJECT_KNOWLEDGE,
    RECOVERY,
    SUCCESS_LIBRARY,
    VERIFICATION,
)
from master_agent.memory.memory_service import (
    RECENT_SHOWN,
    TOP_TAGS_SHOWN,
    MemoryService,
    MemorySummary,
)
from master_agent.mission_control.mission_control import MissionControl
from master_agent.mission_control.tasks import Objective, Task
from master_agent.runtime.config import RuntimeConfig


def service() -> MemoryService:
    memory = MemoryService(store=InMemoryKnowledgeStore())
    memory.load()
    return memory


def wired(with_capability: bool = True) -> tuple[MemoryService, MissionControl]:
    """A memory subscribed to a real Mission Control, exactly as the
    launcher wires it.

    The capability is registered because otherwise `dispatch_ready` fails
    the task on the spot — which is a real behaviour worth its own test
    (below), but not the setup for one about completion.
    """
    from master_agent.mission_control.capabilities import CapabilityDescriptor

    memory = service()
    mission_control = MissionControl()
    if with_capability:
        mission_control.register_executive(
            "filesystem",
            "1.0.0",
            capabilities=[
                CapabilityDescriptor(
                    qualified_name="Filesystem.CreateFolder",
                    executive_id="filesystem",
                    capability="create_folder",
                    risk_tier="reversible_write",
                )
            ],
        )
        mission_control.mark_executive_ready("filesystem")
    memory.attach_to(mission_control)
    return memory, mission_control


def objective_with(*tasks: Task, description: str = "Do the thing") -> Objective:
    return Objective(description=description, tasks=list(tasks))


# =========================================================================
# Manual memory — the founder's own words
# =========================================================================


def test_remembering_something_stores_it_verbatim():
    memory = service()

    write = memory.remember("Always use Gemma unless quality floor exceeds 0.9")

    assert write.created is True
    assert write.record.full_text == "Always use Gemma unless quality floor exceeds 0.9"


def test_a_remembered_sentence_becomes_its_own_title():
    """A founder searching for the words they typed should find them."""
    memory = service()

    write = memory.remember("Never delete logs automatically")

    assert write.record.title == "Never delete logs automatically"


def test_a_long_statement_is_trimmed_for_the_title_but_kept_in_full():
    memory = service()
    long_text = "Kalpavriksha should " + "keep going " * 20

    write = memory.remember(long_text)

    assert len(write.record.title) < len(write.record.full_text)
    assert write.record.full_text.strip().endswith("keep going")


def test_remembering_defaults_to_founder_preferences():
    """What a founder typing a bare sentence at a prompt is almost always
    stating — and the category is one word away on the same command."""
    memory = service()

    assert memory.remember("Project codename Ved").record.category == FOUNDER_PREFERENCES


def test_remembering_is_attributed_to_the_founder():
    assert service().remember("A thing").record.source == FOUNDER


def test_a_founder_can_choose_the_category_importance_and_tags():
    memory = service()

    write = memory.remember(
        "Browser Executive is not implemented yet",
        category=PROJECT_KNOWLEDGE,
        importance=CRITICAL,
        tags=["browser", "gap"],
    )

    assert write.record.category == PROJECT_KNOWLEDGE
    assert write.record.importance == CRITICAL
    assert write.record.tags == ("browser", "gap")


def test_ids_are_sequential_and_readable():
    memory = service()

    assert [memory.remember(f"Thing {n}").id for n in range(1, 4)] == [
        "mem-000001",
        "mem-000002",
        "mem-000003",
    ]


def test_an_architecture_decision_has_its_own_door():
    """Nothing publishes "the architecture changed", and inferring it from
    a diff would be exactly the guessing MB034 forbids."""
    memory = service()

    write = memory.remember_architecture(
        "Broker completed in MB031", "The decision engine shipped and is wired."
    )

    assert write.record.category == ARCHITECTURE_DECISIONS
    assert "architecture" in write.record.tags
    assert write.record.importance == HIGH


def test_writing_an_empty_memory_is_refused():
    with pytest.raises(Exception, match="title"):
        service().remember("   ")


# =========================================================================
# Automatic memory — riding the existing event stream
# =========================================================================


def test_memory_subscribes_only_to_the_events_worth_remembering():
    """The Runtime publishes a heartbeat every cycle. A memory system that
    had to ignore most of what it saw would eventually stop ignoring
    one."""
    memory, _mission_control = wired()

    assert set(memory.attach_to(MissionControl())) == {
        "objective_submitted",
        "objective_completed",
        "objective_failed",
        "verification_completed",
        "approval_granted",
        "approval_denied",
    }
    assert len(memory) == 0


def test_a_runtime_heartbeat_is_not_remembered():
    memory, mission_control = wired()
    from master_agent.mission_control.events import Event, EventType

    for _ in range(20):
        mission_control.bus.publish(
            Event(event_type=EventType.RUNTIME_IDLE, source="runtime_engine")
        )

    assert len(memory) == 0


def test_a_completed_mission_is_remembered():
    memory, mission_control = wired()
    objective = mission_control.submit_objective(
        objective_with(Task(capability="Filesystem.CreateFolder", task_id="t1"))
    )
    mission_control.dispatch_ready(objective.objective_id)
    mission_control.task_started("t1", objective_id=objective.objective_id)

    mission_control.task_completed("t1", objective_id=objective.objective_id)

    written = memory.find_by_category(MISSION_OUTCOMES)
    assert len(written) == 1
    assert "Do the thing" in written[0].title
    assert written[0].source == MISSION


def test_a_mission_is_remembered_by_its_name_not_its_uuid():
    """`OBJECTIVE_COMPLETED` carries only an id, so the description is
    learned from the submission event. Without that, every mission memory
    was titled "Mission completed: a43de263-d959-46f7…" — a fact about a
    UUID rather than about the founder's work. Found by reading one."""
    memory, mission_control = wired()
    objective = mission_control.submit_objective(
        objective_with(
            Task(capability="Filesystem.CreateFolder", task_id="t1"),
            description="Write the quarterly summary",
        )
    )
    mission_control.dispatch_ready(objective.objective_id)
    mission_control.task_started("t1", objective_id=objective.objective_id)
    mission_control.task_completed("t1", objective_id=objective.objective_id)

    title = memory.find_by_category(MISSION_OUTCOMES)[0].title

    assert title == "Mission completed: Write the quarterly summary"
    assert objective.objective_id not in title


def test_submitting_a_mission_is_not_itself_a_memory():
    """A mission that was started is not an outcome. Remembering
    intentions alongside results would make Mission Outcomes
    untrustworthy."""
    memory, mission_control = wired()

    mission_control.submit_objective(
        objective_with(Task(capability="Filesystem.CreateFolder", task_id="t1"))
    )

    assert len(memory) == 0


def test_a_mission_recovered_from_a_previous_run_is_remembered_by_its_id():
    """No submission event on this bus, so there is no name to use — and
    an id is still something a founder can search for."""
    memory, mission_control = wired()
    objective = objective_with(
        Task(capability="Filesystem.CreateFolder", task_id="t1"),
        description="Restored work",
    )
    mission_control.restore_objective(objective)
    mission_control.dispatch_ready(objective.objective_id)
    mission_control.task_started("t1", objective_id=objective.objective_id)
    mission_control.task_completed("t1", objective_id=objective.objective_id)

    assert objective.objective_id in memory.find_by_category(MISSION_OUTCOMES)[0].title


def test_a_mission_nothing_can_serve_is_remembered_as_a_failure():
    """Discovered while writing the test above: an objective naming an
    unregistered capability fails at dispatch, and that is a genuine
    mission failure worth remembering — it is usually a wiring gap the
    founder needs to know about."""
    memory, mission_control = wired(with_capability=False)
    objective = mission_control.submit_objective(
        objective_with(Task(capability="Filesystem.CreateFolder", task_id="t1"))
    )

    mission_control.dispatch_ready(objective.objective_id)

    failures = memory.find_by_category(FAILURE_LIBRARY)
    assert len(failures) == 1
    assert "Do the thing" in failures[0].title


def test_a_failed_mission_goes_to_the_failure_library():
    memory, mission_control = wired()
    objective = mission_control.submit_objective(
        objective_with(Task(capability="Filesystem.CreateFolder", task_id="t1"))
    )
    mission_control.dispatch_ready(objective.objective_id)
    mission_control.task_started("t1", objective_id=objective.objective_id)

    mission_control.task_failed("t1", "disk full", objective_id=objective.objective_id)

    written = memory.find_by_category(FAILURE_LIBRARY)
    assert len(written) == 1
    assert written[0].importance == HIGH


def test_a_matched_verification_goes_to_the_success_library():
    memory, mission_control = wired()

    mission_control.verification_completed(
        "t1", verdict="matched", evidence_id="ev-1", objective_id=None
    )

    written = memory.find_by_category(SUCCESS_LIBRARY)
    assert len(written) == 1
    assert written[0].source == VERIFICATION
    assert written[0].importance == NORMAL


def test_a_failed_verification_goes_to_the_failure_library_at_higher_importance():
    """The failures are what change behaviour."""
    memory, mission_control = wired()

    mission_control.verification_completed(
        "t1", verdict="not_matched", evidence_id="ev-1", objective_id=None
    )

    written = memory.find_by_category(FAILURE_LIBRARY)
    assert len(written) == 1
    assert written[0].importance == HIGH


def test_a_verification_memory_names_the_evidence():
    """ADR-0011's verdict is the strongest evidence this system produces,
    and a memory of it that could not be traced back would be a rumour."""
    memory, mission_control = wired()

    mission_control.verification_completed(
        "t1", verdict="matched", evidence_id="ev-42", objective_id=None
    )

    assert "ev-42" in memory.recent()[0].full_text


def test_an_approval_is_remembered_as_a_business_decision():
    memory, mission_control = wired()
    from master_agent.mission_control.approvals import PendingApproval

    approval, _ = mission_control.request_approval(
        PendingApproval(
            capability="Broker.UsePaidProvider[x]",
            local_capability="use_paid_provider",
            executive_id="x",
            risk_tier="irreversible",
            reason="Use A Paid Provider",
            task_id="t1",
        )
    )
    mission_control.approve(approval.approval_id, "founder")

    written = memory.find_by_category(BUSINESS_DECISIONS)
    assert len(written) == 1
    assert written[0].title.startswith("Approved")
    assert written[0].importance == HIGH


def test_a_rejection_is_remembered_too():
    memory, mission_control = wired()
    from master_agent.mission_control.approvals import PendingApproval

    approval, _ = mission_control.request_approval(
        PendingApproval(
            capability="Broker.UsePaidProvider[x]",
            local_capability="use_paid_provider",
            executive_id="x",
            risk_tier="irreversible",
            reason="Use A Paid Provider",
            task_id="t1",
        )
    )
    mission_control.reject(approval.approval_id, "founder")

    assert memory.find_by_category(BUSINESS_DECISIONS)[0].title.startswith("Rejected")


def test_an_approval_memory_records_who_decided():
    memory, mission_control = wired()
    from master_agent.mission_control.approvals import PendingApproval

    approval, _ = mission_control.request_approval(
        PendingApproval(
            capability="X.Y",
            local_capability="y",
            executive_id="x",
            risk_tier="irreversible",
            reason="r",
            task_id="t1",
        )
    )
    mission_control.approve(approval.approval_id, "onkar")

    assert "onkar" in memory.recent()[0].full_text


def test_a_recovery_is_remembered():
    """Recovery publishes nothing (MB025 runs it before recording starts),
    so the composition root hands the report in."""
    memory = service()

    class Report:
        recovered = True
        source = "snapshot"
        objectives = 2
        quarantined_tasks = 1

    write = memory.remember_recovery(Report())

    assert write is not None
    assert write.record.source == RECOVERY
    assert write.record.category == PROJECT_KNOWLEDGE
    assert "2 objective(s)" in write.record.title


def test_a_first_run_with_nothing_to_recover_writes_nothing():
    class Report:
        recovered = False

    assert service().remember_recovery(Report()) is None
    assert service().remember_recovery(None) is None


def test_a_restart_that_recovered_nothing_is_not_a_learning():
    """An empty snapshot still counts as `recovered`. Found by reading a
    live founder page: every launch wrote "Recovered 0 objective(s)", and
    that one line then owned Recent Learnings, Top Tags and Last Written —
    pushing everything the founder actually said below it."""

    class Empty:
        recovered = True
        source = "snapshot"
        objectives = 0
        quarantined_tasks = 0

    assert service().remember_recovery(Empty()) is None


def test_a_restart_that_only_quarantined_work_is_still_worth_remembering():
    """Interrupted work is exactly the thing a founder needs told about,
    even when no objective came back with it."""

    class Quarantined:
        recovered = True
        source = "snapshot"
        objectives = 0
        quarantined_tasks = 2

    write = service().remember_recovery(Quarantined())

    assert write is not None
    assert write.record.importance == HIGH


def test_a_recovery_that_quarantined_work_is_more_important():
    memory = service()

    class Clean:
        recovered = True
        source = "snapshot"
        objectives = 1
        quarantined_tasks = 0

    class Messy(Clean):
        quarantined_tasks = 3

    assert memory.remember_recovery(Clean()).record.importance == NORMAL
    assert service().remember_recovery(Messy()).record.importance == HIGH


def test_repeating_the_same_automatic_event_does_not_duplicate_the_memory():
    """The same verification verdict twice is one fact about the system,
    not two."""
    memory, mission_control = wired()

    for _ in range(3):
        mission_control.verification_completed(
            "t1", verdict="matched", evidence_id="ev-1", objective_id=None
        )

    assert len(memory) == 1
    assert memory.duplicates_suppressed == 2


def test_automatic_memory_never_blocks_the_event_that_caused_it():
    """A broken memory must not take down execution — the same isolation
    the Event Bus already gives every subscriber."""
    memory, mission_control = wired()
    memory._store = _ExplodingStore()

    mission_control.verification_completed(
        "t1", verdict="matched", evidence_id="ev", objective_id=None
    )

    assert memory.write_failures, "the failure was recorded rather than raised"


class _ExplodingStore:
    def load(self):  # pragma: no cover - never called in these tests
        raise OSError("no")

    def save(self, records, index):
        raise OSError("disk full")


# =========================================================================
# Persistence and restart
# =========================================================================


def test_a_memory_survives_a_restart(tmp_path):
    first = MemoryService(store=JsonKnowledgeStore(tmp_path))
    first.load()
    first.remember("Founder prefers Gemma by default", tags=["broker"])

    second = MemoryService(store=JsonKnowledgeStore(tmp_path))
    second.load()

    assert len(second) == 1
    assert second.search("gemma")[0].full_text == "Founder prefers Gemma by default"


def test_every_field_survives_a_restart(tmp_path):
    first = MemoryService(store=JsonKnowledgeStore(tmp_path))
    first.load()
    original = first.remember(
        "A detailed thing",
        category=ARCHITECTURE_DECISIONS,
        tags=["a", "b"],
        importance=CRITICAL,
        confidence=0.75,
    ).record

    second = MemoryService(store=JsonKnowledgeStore(tmp_path))
    second.load()

    assert second.get(original.id) == original


def test_ids_continue_after_a_restart(tmp_path):
    first = MemoryService(store=JsonKnowledgeStore(tmp_path))
    first.load()
    first.remember("One")
    first.remember("Two")

    second = MemoryService(store=JsonKnowledgeStore(tmp_path))
    second.load()

    assert second.remember("Three").id == "mem-000003"


def test_a_memory_is_written_the_moment_it_is_remembered(tmp_path):
    """Not at shutdown: a memory that only survives a graceful exit is not
    a memory."""
    memory = MemoryService(store=JsonKnowledgeStore(tmp_path))
    memory.load()

    memory.remember("Written immediately")

    assert (tmp_path / MEMORY_DIRNAME / KNOWLEDGE_FILENAME).exists()


def test_the_index_survives_and_is_not_rebuilt_on_a_clean_restart(tmp_path):
    first = MemoryService(store=JsonKnowledgeStore(tmp_path))
    first.load()
    first.remember("A thing", tags=["tag"])

    second = MemoryService(store=JsonKnowledgeStore(tmp_path))
    report = second.load()

    assert report.rebuilt_index is False
    assert len(second.find_by_tag("tag")) == 1


def test_search_still_works_after_the_index_is_rebuilt(tmp_path):
    first = MemoryService(store=JsonKnowledgeStore(tmp_path))
    first.load()
    first.remember("Broker architecture completed in MB031", tags=["broker"])
    (tmp_path / MEMORY_DIRNAME / "index.json").unlink()

    second = MemoryService(store=JsonKnowledgeStore(tmp_path))
    report = second.load()

    assert report.rebuilt_index is True
    assert len(second.search("mb031")) == 1
    assert len(second.find_by_tag("broker")) == 1


def test_a_corrupt_knowledge_file_starts_empty_and_says_so(tmp_path):
    memory = MemoryService(store=JsonKnowledgeStore(tmp_path))
    memory.load()
    memory.remember("Something")
    (tmp_path / MEMORY_DIRNAME / KNOWLEDGE_FILENAME).write_text("{ broken", encoding="utf-8")

    second = MemoryService(store=JsonKnowledgeStore(tmp_path))
    report = second.load()

    assert len(second) == 0
    assert report.problems
    assert second.summary().problems


def test_a_service_with_no_store_still_works():
    memory = MemoryService()
    memory.load()

    assert memory.remember("A thing").created is True
    assert len(memory) == 1


def test_a_store_that_cannot_be_written_never_loses_the_memory_in_process():
    memory = MemoryService(store=_ExplodingStore())

    write = memory.remember("A thing")

    assert write.created is True
    assert len(memory) == 1
    assert memory.write_failures


def test_records_are_written_in_id_order(tmp_path):
    """So the file on disk is stable between saves and a diff of it is
    readable."""
    memory = MemoryService(store=JsonKnowledgeStore(tmp_path))
    memory.load()
    for n in range(1, 4):
        memory.remember(f"Thing {n}")

    assert [r.id for r in memory.all()] == ["mem-000001", "mem-000002", "mem-000003"]


# =========================================================================
# The summary the Dashboard reads
# =========================================================================


def test_an_empty_memory_summarises_as_empty():
    summary = service().summary()

    assert summary.total == 0
    assert summary.critical == 0
    assert summary.last_written is None


def test_the_summary_counts_what_is_known():
    memory = service()
    memory.remember("One", importance=CRITICAL)
    memory.remember("Two")

    summary = memory.summary()

    assert summary.total == 2
    assert summary.critical == 1


def test_the_summary_shows_the_most_recent_learnings():
    memory = service()
    for n in range(1, 6):
        memory.remember(f"Thing {n}")

    assert len(memory.summary().recent) == RECENT_SHOWN
    assert memory.summary().recent[0].title == "Thing 5"


def test_the_summary_shows_the_top_tags():
    memory = service()
    memory.remember("One", tags=["common", "rare"])
    memory.remember("Two", tags=["common"])

    assert memory.summary().top_tags[0] == ("common", 2)
    assert len(memory.summary().top_tags) <= TOP_TAGS_SHOWN


def test_the_summary_names_the_last_thing_written():
    memory = service()
    memory.remember("First")
    memory.remember("Last")

    assert memory.summary().last_written.title == "Last"


def test_repeating_a_memory_makes_it_the_last_written():
    """It is the most recently *touched* thing, which is what the founder
    just did."""
    memory = service()
    memory.remember("First")
    memory.remember("Second")
    memory.remember("First")

    assert memory.summary().last_written.title == "First"


def test_the_summary_counts_by_category():
    memory = service()
    memory.remember("A", category=PROJECT_KNOWLEDGE)
    memory.remember("B", category=PROJECT_KNOWLEDGE)
    memory.remember("C", category=FOUNDER_PREFERENCES)

    assert memory.summary().by_category[0] == (PROJECT_KNOWLEDGE, 2)


def test_the_summary_serialises_for_a_front_end():
    memory = service()
    memory.remember("A thing", tags=["t"], importance=CRITICAL)

    payload = memory.summary().as_dict()

    assert payload["total"] == 1
    assert payload["critical"] == 1
    assert payload["top_tags"] == [{"tag": "t", "count": 1}]


def test_the_last_written_survives_a_restart(tmp_path):
    first = MemoryService(store=JsonKnowledgeStore(tmp_path))
    first.load()
    first.remember("First")
    first.remember("Second")

    second = MemoryService(store=JsonKnowledgeStore(tmp_path))
    second.load()

    assert second.summary().last_written.title == "Second"


# =========================================================================
# The Dashboard section
# =========================================================================


def view_of(memory: MemoryService):
    sources = DashboardSources(memory_provider=memory.summary)
    return build_founder_view(sources.collect())


def test_with_no_memory_attached_the_panel_says_so():
    """An empty count would read as "you have told me nothing", which is a
    different and much more alarming fact."""
    view = build_founder_view(DashboardSources().collect())

    assert view.memory.available is False
    assert "no founder memory attached" in view.memory.reason


def test_a_memory_read_that_raises_becomes_absent_data():
    def explode():
        raise RuntimeError("memory unreadable")

    panel = DashboardSources(memory_provider=explode).collect().memory

    assert panel.status.available is False
    assert "memory unreadable" in panel.status.reason


def test_a_memory_that_reports_nothing_is_absent_rather_than_empty():
    panel = DashboardSources(memory_provider=lambda: None).collect().memory

    assert panel.status.available is False


@pytest.mark.parametrize(
    ("field", "expected"),
    [("total", 2), ("critical", 1)],
)
def test_the_panel_carries_the_counts(field, expected):
    memory = service()
    memory.remember("One", importance=CRITICAL)
    memory.remember("Two")

    assert getattr(view_of(memory).memory, field) == expected


def test_the_panel_lists_recent_titles():
    memory = service()
    memory.remember("Browser Executive is not implemented yet")

    assert view_of(memory).memory.recent == ["Browser Executive is not implemented yet"]


def test_the_panel_shows_tags_with_their_counts():
    memory = service()
    memory.remember("One", tags=["broker"])

    assert view_of(memory).memory.top_tags == ["broker (1)"]


def test_the_panel_names_the_last_memory_written_and_when():
    memory = service()
    memory.remember("The latest thing")

    assert "The latest thing" in view_of(memory).memory.last_written


def test_the_rendered_section_shows_the_five_things_mb034_names():
    memory = service()
    memory.remember("A remembered thing", tags=["broker"], importance=CRITICAL)

    text = "\n".join(render_memory(view_of(memory), ASCII))

    assert "MEMORY" in text
    assert "Total knowledge  1" in text
    assert "Critical facts   1" in text
    assert "Recent learnings" in text
    assert "Top tags" in text
    assert "Last written" in text


def test_the_section_is_visible_before_anything_is_remembered():
    """A section that vanishes when empty teaches a founder to stop
    looking for it."""
    text = "\n".join(render_memory(view_of(service()), ASCII))

    assert "MEMORY" in text
    assert "nothing remembered yet" in text


def test_the_section_says_when_memory_is_not_attached():
    text = "\n".join(render_memory(build_founder_view(DashboardSources().collect()), ASCII))

    assert "MEMORY" in text
    assert "no founder memory attached" in text


def test_the_section_surfaces_a_storage_problem():
    memory = MemoryService(store=_ExplodingStore())
    memory.remember("A thing")

    text = "\n".join(render_memory(view_of(memory), ASCII))

    assert "disk full" in text


def test_no_rendered_line_runs_past_the_frame():
    memory = service()
    memory.remember(
        "A really quite long thing that the founder typed in one go without stopping",
        tags=["one", "two", "three", "four", "five"],
    )

    lines = render_memory(view_of(memory), ASCII)

    assert all(len(line) <= 74 for line in lines), [
        line for line in lines if len(line) > 74
    ]


def test_the_section_encodes_on_a_cp1252_console():
    memory = service()
    memory.remember("A thing")

    "\n".join(render_memory(view_of(memory), ASCII)).encode("cp1252")


def test_the_section_appears_in_the_founder_frame():
    memory = service()
    memory.remember("A thing")

    frame = render_founder_frame(view_of(memory), ASCII)

    assert "MEMORY" in frame


def test_the_section_sits_after_what_the_system_has_and_before_what_is_next():
    memory = service()
    memory.remember("A thing")
    frame = render_founder_frame(view_of(memory), ASCII)

    assert frame.index("AI DECISIONS") < frame.index("MEMORY")
    assert frame.index("MEMORY") < frame.index("RECOMMENDATIONS")


def test_the_view_serialises_for_a_web_front_end():
    memory = service()
    memory.remember("A thing", importance=CRITICAL, tags=["t"])

    payload = founder_as_dict(view_of(memory))["memory"]

    assert payload["total"] == 1
    assert payload["critical"] == 1
    assert payload["recent"] == ["A thing"]


def test_rendering_never_writes_a_memory():
    """ADR-0016, extended to the new section: looking at the screen cannot
    change what Kalpavriksha knows."""
    memory = service()
    memory.remember("A thing")
    sources = DashboardSources(memory_provider=memory.summary)

    for _ in range(5):
        build_founder_view(sources.collect())

    assert len(memory) == 1


def test_the_panel_reads_a_summary_and_computes_nothing():
    """Handed in, never discovered — the same rule the machine inventory
    and the Broker report follow."""
    panel = DashboardSources(
        memory_provider=lambda: MemorySummary(total=7, critical=2)
    ).collect().memory

    assert panel.total == 7
    assert panel.critical == 2


# =========================================================================
# The founder's two commands
# =========================================================================


def console_with(memory: MemoryService) -> FounderConsole:
    return FounderConsole(
        dashboard=None,
        mission_control=MissionControl(),
        memory=memory,
        writer=lambda _text: None,
    )


def test_remember_stores_what_the_founder_typed():
    memory = service()

    message = console_with(memory).execute('remember "Never delete logs automatically"')

    assert "remembered" in message
    assert memory.search("logs")[0].full_text == "Never delete logs automatically"


def test_remember_works_without_quotes():
    """A founder typing at a prompt should not have to think about shell
    conventions that do not apply here."""
    memory = service()

    console_with(memory).execute("remember Project codename Ved")

    assert len(memory.search("codename")) == 1


@pytest.mark.parametrize("quoted", ["'single'", '"double"'])
def test_quotes_are_stripped_rather_than_stored(quoted):
    memory = service()

    console_with(memory).execute(f"remember {quoted}")

    assert '"' not in memory.recent()[0].full_text
    assert "'" not in memory.recent()[0].full_text


def test_remembering_preserves_the_founders_capitalisation():
    """Lower-casing "Project codename Ved" would store something they did
    not say."""
    memory = service()

    console_with(memory).execute("remember Project codename Ved")

    assert "Ved" in memory.recent()[0].full_text


def test_remembering_nothing_asks_what():
    assert "remember what?" in console_with(service()).execute("remember   ")


def test_remembering_the_same_thing_twice_says_so():
    memory = service()
    console = console_with(memory)
    console.execute("remember A thing")

    assert "already remembered" in console.execute("remember A thing")


def test_the_console_reports_a_refused_memory_rather_than_crashing():
    """A typo at 22:13 must not take down the console the founder is using
    to stop something irreversible."""

    class Refusing:
        def remember(self, text):
            raise ValueError("nope")

    console = FounderConsole(
        dashboard=None, mission_control=MissionControl(), memory=Refusing(),
        writer=lambda _t: None,
    )

    assert "could not remember" in console.execute("remember something")


def test_memory_search_finds_what_was_remembered():
    memory = service()
    memory.remember("Broker architecture completed in MB031", tags=["architecture"])

    message = console_with(memory).execute("memory architecture")

    assert "MB031" in message
    assert "mem-000001" in message


def test_memory_search_reports_finding_nothing():
    assert "nothing remembered about" in console_with(service()).execute("memory zebra")


def test_a_bare_memory_command_reports_how_much_is_known():
    memory = service()
    memory.remember("A thing")

    assert "1 memories" in console_with(memory).execute("memory")


def test_the_commands_report_honestly_when_memory_is_not_wired():
    console = FounderConsole(
        dashboard=None, mission_control=MissionControl(), writer=lambda _t: None
    )

    assert "not wired" in console.execute("remember a thing")
    assert "not wired" in console.execute("memory anything")


def test_the_memory_commands_are_offered_in_the_help():
    from master_agent.launcher.console import HELP

    assert "remember" in HELP
    assert "memory" in HELP


def test_the_approval_commands_still_work_alongside_them():
    """MB028.1's console is unchanged; MB034 added two verbs beside it."""
    console = console_with(service())

    assert "nothing pending" in console.execute("approve all")
    assert console.execute("quit") == "stopping"


def test_a_word_that_merely_starts_like_remember_is_not_a_memory_command():
    """`rememberish` must not reach `remember`. MB037 changed what happens
    to a line that matches no verb -- it becomes an objective now -- so
    this asserts the thing it was really guarding: verb matching is on
    whole words, and a near-miss never writes a memory."""
    memory = service()
    console = console_with(memory)

    before = memory.summary().total
    reply = console.execute("rememberish thing")

    assert "no planner is wired" in reply
    assert memory.summary().total == before, "a near-miss verb wrote a memory"


# =========================================================================
# The launcher, and the Definition of Done
# =========================================================================


def quiet_system(state_dir, **kwargs):
    kwargs.setdefault("runtime_config", RuntimeConfig(poll_interval_seconds=0))
    kwargs.setdefault("dashboard_kwargs", {"writer": lambda _text: None})
    return build_system(state_dir=state_dir, **kwargs)


def test_the_launcher_wires_founder_memory(tmp_path):
    system = quiet_system(tmp_path / "state")

    assert system.memory is not None
    assert isinstance(system.memory, MemoryService)


def test_memory_lives_beside_state_not_inside_it(tmp_path):
    system = quiet_system(tmp_path / "state")
    system.memory.remember("A thing")

    assert (tmp_path / MEMORY_DIRNAME / KNOWLEDGE_FILENAME).exists()
    assert not (tmp_path / "state" / MEMORY_DIRNAME).exists()


def test_the_boot_report_says_what_it_remembered_and_what_it_watches(tmp_path):
    system = quiet_system(tmp_path / "state")
    step = system.report.step("Founder Memory")

    assert step.ok is True
    assert "0 memory record(s)" in step.detail
    assert "watching 6 event type(s)" in step.detail


def test_the_boot_report_warns_when_memory_could_not_be_read(tmp_path):
    (tmp_path / MEMORY_DIRNAME).mkdir(parents=True)
    (tmp_path / MEMORY_DIRNAME / KNOWLEDGE_FILENAME).write_text("{ broken", encoding="utf-8")

    system = quiet_system(tmp_path / "state")
    step = system.report.step("Founder Memory")

    assert step.ok is False
    assert step.detail


def test_memory_is_built_before_recovery_so_the_recovery_can_be_remembered(tmp_path):
    system = quiet_system(tmp_path / "state")
    names = [step.name for step in system.report.steps]

    assert names.index("Founder Memory") < names.index("Recovery")


def test_the_dashboard_shows_the_launchers_own_memory(tmp_path):
    system = quiet_system(tmp_path / "state")
    system.memory.remember("Founder prefers Gemma by default")

    frame = system.dashboard.render()

    assert "MEMORY" in frame
    assert "Total knowledge  1" in frame


def test_a_restart_remembers_the_recovery_that_happened(tmp_path):
    """The launcher hands the report in, because recovery publishes
    nothing."""
    state = tmp_path / "state"
    first = quiet_system(state)
    first.mission_control.submit_objective(
        objective_with(Task(capability="Filesystem.CreateFolder", task_id="t1"))
    )
    first.stop()

    second = quiet_system(state)

    recovered = [r for r in second.memory.all() if r.source == RECOVERY]
    assert len(recovered) == 1
    assert "objective(s)" in recovered[0].title


def test_kalpavriksha_survives_a_restart_and_still_knows_things(tmp_path):
    """MB034's Definition of Done, in one test and with no LLM anywhere.

    The four facts the brief names, told to one process and asked of the
    next.
    """
    state = tmp_path / "state"
    first = quiet_system(state)
    first.memory.remember(
        "Founder prefers Gemma by default", category=FOUNDER_PREFERENCES,
        tags=["broker", "model"], importance=CRITICAL,
    )
    first.memory.remember(
        "Browser Executive not yet implemented", category=PROJECT_KNOWLEDGE,
        tags=["browser"],
    )
    first.memory.remember_architecture(
        "Broker architecture completed in MB031",
        "The AI Capability Broker decision engine shipped in Mission Brief 031.",
    )
    first.memory.remember(
        "Last verification failed because the Docker daemon was not running",
        category=FAILURE_LIBRARY, tags=["verification", "docker"], importance=HIGH,
    )
    first.stop()

    second = quiet_system(state)

    assert "Gemma" in second.memory.search("gemma")[0].full_text
    assert "Browser Executive" in second.memory.search("browser executive")[0].title
    assert "MB031" in second.memory.search("mb031")[0].title
    assert "Docker" in second.memory.search("docker")[0].full_text
    assert [r.title for r in second.memory.critical()] == [
        "Founder prefers Gemma by default"
    ]


def test_the_founder_can_ask_the_next_process_what_it_knows(tmp_path):
    """The same four facts, through the console the founder actually
    types into."""
    state = tmp_path / "state"
    first = quiet_system(state)
    console_with(first.memory).execute(
        "remember Last verification failed because Docker was not running"
    )
    first.stop()

    second = quiet_system(state)
    message = FounderConsole(
        dashboard=None, mission_control=second.mission_control,
        memory=second.memory, writer=lambda _t: None,
    ).execute("memory docker")

    assert "Docker" in message


def test_nothing_in_the_memory_path_ever_calls_a_model(tmp_path):
    """The Definition of Done says "without asking an LLM". Asserted by
    giving the system a provider whose transport would record any call,
    then exercising the whole memory path."""
    from master_agent.providers.ollama import OLLAMA_PROVIDER_ID
    from tests.broker_test_support import FakeTransport

    system = quiet_system(tmp_path / "state")
    transport = FakeTransport()
    system.providers.get(OLLAMA_PROVIDER_ID)._transport = transport

    system.memory.remember("A thing worth knowing", tags=["t"])
    system.memory.search("thing")
    system.memory.summary()
    system.dashboard.render()

    assert transport.posts == []
    assert transport.gets == []
