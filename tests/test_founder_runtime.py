"""Sprint 1, Component 23 — Founder Runtime Wiring.

The brief is a wiring brief, so almost every test below asks one of two
questions: *did this carry the value it was given unchanged?* and *did it
refrain from producing a value nobody gave it?*

| Requirement | Source |
|---|---|
| The Founder UI can receive the five named contracts | C23 brief |
| Without duplicating logic | C23 brief |
| Never invent responses | C23 brief |
| Never execute tools | C23 brief |
| Never call AI | C23 brief |
| Never redesign the runtime or the dashboard | C23 brief |
| Frozen packages untouched and unimported | Project Brain |
| *I haven't checked* stays distinct from *I checked and it is old* | VEDA 04 §5 |
| Calm requires provable coverage | VEDA 04 D7 |

**Every guard reads executable identifiers via AST, never source text.**
These modules' docstrings name the things they refuse to do — `authorize`,
`assistant`, `PresenceSnapshot`, `execute` — and a text-matching guard would
fail on the explanation rather than on the code. That trap has been hit
twice in this project already (C15 Part 6, and the C20 audit's §11 note),
and once more in C21's boundary guard, which passed while scanning nothing.

Nothing here touches a real machine, a clock, a network or a Kernel.
"""
from __future__ import annotations

import ast
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from master_agent.desktop.inventory import (
    INSTALLED,
    MISSING,
    InstalledApplication,
    MachineInventory,
)
from master_agent.desktop.probe import ProcessInfo
from master_agent.environment_intelligence import derive_intelligence
from master_agent.foundation.clock import ManualClock
from master_agent.founder_runtime import (
    ARGUMENTS,
    AUTHORITY_UNREACHABLE,
    CONTRACT_SECTIONS,
    NOTHING_WATCHED,
    OPERATION,
    PRESENCE_OBSERVATION_TYPES,
    PROJECTED_ROLES,
    FounderOperation,
    FounderRuntime,
    InvalidFounderEnvelope,
    PresenceFeed,
    ResultKind,
    Source,
    conversation_projection,
    environment_projection,
    presence_feed,
)
from master_agent.memory.conversation import ConversationMemory
from master_agent.vigilance import (
    Domain,
    DomainRegistry,
    DomainReport,
    GapKind,
    VigilanceAttestation,
)

PACKAGE = (
    Path(__file__).resolve().parent.parent
    / "src" / "master_agent" / "founder_runtime"
)

T0 = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
WINDOW = timedelta(minutes=15)


# ───────────────────────────── fixtures ────────────────────────────────


def app(
    key: str,
    category: str,
    *,
    status: str = INSTALLED,
    healthy: bool = True,
) -> InstalledApplication:
    return InstalledApplication(
        key=key,
        name=key.replace("_", " ").title(),
        category=category,
        status=status,
        healthy=healthy,
    )


def machine(*applications: InstalledApplication, running: tuple[str, ...] = ()):
    return MachineInventory(
        applications=list(applications),
        processes=[
            ProcessInfo(pid=100 + i, name=f"{key}.exe", owner=key)
            for i, key in enumerate(running)
        ],
        platform="win32",
        captured_at=T0,
    )


def intelligence():
    """A real C22 derivation over a real inventory shape."""
    return derive_intelligence(
        machine(
            app("vscode", "editor"),
            app("chrome", "browser"),
            app("git", "development"),
            app("ollama", "ai"),
            app("firefox", "browser", status=MISSING, healthy=False),
            running=("chrome", "ollama"),
        )
    )


def registry(*names: str, window: timedelta = WINDOW) -> DomainRegistry:
    built = DomainRegistry()
    for name in names:
        built = built.register(Domain(name, window))
    return built


def attest(built: DomainRegistry, at: datetime = T0):
    return VigilanceAttestation(built, ManualClock(at)).attest()


def covered(*names: str):
    """Every domain fresh and healthy, so C19 reports complete."""
    built = registry(*names)
    for name in names:
        built = built.report(
            DomainReport(name=name, checked_at=T0, healthy=True)
        )
    return built, attest(built)


def conversation(*turns: tuple[str, str]) -> ConversationMemory:
    memory = ConversationMemory()
    for speaker, text in turns:
        memory.record(speaker, text)
    return memory


def wired() -> FounderRuntime:
    built, coverage = covered("inbox", "calendar")
    return FounderRuntime(
        intelligence=intelligence(),
        coverage=coverage,
        registry=built,
        conversation=conversation(("user", "what is running?")),
    )


def by_type(feed: PresenceFeed, kind: str) -> list[dict]:
    return [obs for obs in feed.observations if obs["type"] == kind]


# ── C20 conformance check ───────────────────────────────────────────────
#
# A transcription of `isValidObservation` from C20's own `observations.ts`,
# restricted to the two types this component emits. It lives in the test
# suite deliberately: a copy in `src/` would be the second implementation
# of C20's contract that the brief forbids, but without a copy *somewhere*
# nothing in this repository can prove the feed is acceptable to the layer
# it is built for. This is the only place the two systems are compared.


def accepted_by_presence_layer(obs: dict) -> bool:
    if not isinstance(obs.get("type"), str):
        return False
    if obs["type"] not in PRESENCE_OBSERVATION_TYPES:
        return False
    if not isinstance(obs.get("at"), str) or not obs["at"]:
        return False
    if obs["type"] == "coverage.expected":
        domains = obs.get("domains")
        return isinstance(domains, list) and all(
            isinstance(name, str) for name in domains
        )
    freshness = obs.get("freshnessSeconds")
    return (
        isinstance(obs.get("domain"), str)
        and isinstance(obs.get("healthy"), bool)
        and (freshness is None or isinstance(freshness, (int, float)))
    )


# ═══════════════════ A · the presence feed transcribes ══════════════════


class TestPresenceFeedTranscribes:
    def test_emits_only_the_two_permitted_observation_types(self):
        _, coverage = covered("inbox", "calendar")
        feed = presence_feed(coverage)
        assert {obs["type"] for obs in feed.observations} <= set(
            PRESENCE_OBSERVATION_TYPES
        )

    def test_every_observation_is_acceptable_to_the_presence_layer(self):
        built = registry("inbox", "calendar", "billing")
        built = built.report(
            DomainReport(name="inbox", checked_at=T0, healthy=True)
        )
        built = built.report(
            DomainReport(name="calendar", checked_at=T0, healthy=False)
        )
        feed = presence_feed(built and attest(built), built)
        assert feed.observations
        assert all(accepted_by_presence_layer(o) for o in feed.observations)

    def test_expected_names_every_domain_in_coverage_order(self):
        _, coverage = covered("inbox", "calendar", "billing")
        feed = presence_feed(coverage)
        expected = by_type(feed, "coverage.expected")
        assert len(expected) == 1
        assert expected[0]["domains"] == ["inbox", "calendar", "billing"]

    def test_expected_is_stamped_with_the_attestation_moment(self):
        _, coverage = covered("inbox")
        feed = presence_feed(coverage)
        assert by_type(feed, "coverage.expected")[0]["at"] == (
            coverage.attested_at.isoformat()
        )

    def test_a_never_checked_domain_gets_no_report(self):
        """*I haven't checked* must not become *I checked and it is old*."""
        built = registry("inbox", "unreported")
        built = built.report(
            DomainReport(name="inbox", checked_at=T0, healthy=True)
        )
        feed = presence_feed(attest(built), built)

        reported = {o["domain"] for o in by_type(feed, "coverage.reported")}
        assert reported == {"inbox"}
        assert "unreported" in by_type(feed, "coverage.expected")[0]["domains"]

    def test_a_report_is_stamped_with_its_own_last_checked_moment(self):
        """C20 reads `lastCheckedAt` from the observation's own `at`."""
        checked = T0 - timedelta(minutes=5)
        built = registry("inbox")
        built = built.report(
            DomainReport(name="inbox", checked_at=checked, healthy=True)
        )
        coverage = attest(built)
        feed = presence_feed(coverage, built)

        report = by_type(feed, "coverage.reported")[0]
        assert report["at"] == checked.isoformat()
        assert report["at"] != coverage.attested_at.isoformat()

    def test_health_is_carried_not_reinterpreted(self):
        built = registry("inbox")
        built = built.report(
            DomainReport(
                name="inbox", checked_at=T0, healthy=False, detail="offline"
            )
        )
        feed = presence_feed(attest(built), built)
        assert by_type(feed, "coverage.reported")[0]["healthy"] is False

    def test_freshness_comes_from_the_registry_when_given(self):
        built = registry("inbox", window=timedelta(seconds=90))
        built = built.report(
            DomainReport(name="inbox", checked_at=T0, healthy=True)
        )
        feed = presence_feed(attest(built), built)
        assert by_type(feed, "coverage.reported")[0]["freshnessSeconds"] == 90

    def test_freshness_is_null_without_a_registry(self):
        """The default threshold is C20's presentation policy, not ours."""
        _, coverage = covered("inbox")
        feed = presence_feed(coverage)
        assert by_type(feed, "coverage.reported")[0]["freshnessSeconds"] is None

    def test_a_registry_domain_absent_from_the_coverage_is_ignored(self):
        built, coverage = covered("inbox")
        wider = built.register(Domain("elsewhere", WINDOW))
        feed = presence_feed(coverage, wider)

        domains = by_type(feed, "coverage.expected")[0]["domains"]
        assert domains == ["inbox"]
        assert all(
            o["domain"] != "elsewhere" for o in by_type(feed, "coverage.reported")
        )

    def test_the_feed_is_deterministic(self):
        built, coverage = covered("inbox", "calendar")
        assert presence_feed(coverage, built) == presence_feed(coverage, built)

    def test_it_refuses_anything_that_is_not_a_coverage(self):
        with pytest.raises(TypeError):
            presence_feed({"complete": True})  # type: ignore[arg-type]

    def test_it_refuses_a_registry_that_is_not_one(self):
        _, coverage = covered("inbox")
        with pytest.raises(TypeError):
            presence_feed(coverage, ["inbox"])  # type: ignore[arg-type]


class TestNothingWatchedIsRefused:
    """An empty coverage must not be fed. C20 would derive calm from it."""

    def test_no_observations_are_emitted(self):
        feed = presence_feed(attest(DomainRegistry()))
        assert feed.observations == ()
        assert feed.fed is False

    def test_the_reason_is_c19s_own_words(self):
        feed = presence_feed(attest(DomainRegistry()))
        assert feed.absent_reason == NOTHING_WATCHED

        gap_details = [
            gap.detail for gap in attest(DomainRegistry()).gaps
        ]
        assert NOTHING_WATCHED in gap_details

    def test_no_placeholder_domain_is_invented(self):
        feed = presence_feed(attest(DomainRegistry()))
        assert not any("domains" in obs for obs in feed.observations)

    def test_a_feed_cannot_carry_both_observations_and_a_reason(self):
        with pytest.raises(ValueError):
            PresenceFeed(
                observations=({"type": "coverage.expected", "at": "x"},),
                absent_reason="also this",
            )


class TestFeedAgreesWithC19:
    """The feed carries the facts behind every gap C19 found.

    C20's `deriveVigilance` is not re-implemented here — that would be the
    duplication the brief forbids. What is asserted is that the *input* to
    each of C20's three gap reasons is present whenever C19 found the
    corresponding gap.
    """

    def test_never_checked_arrives_as_expected_but_unreported(self):
        built = registry("inbox")
        coverage = attest(built)
        feed = presence_feed(coverage, built)

        assert [g.kind for g in coverage.gaps] == [GapKind.NEVER_CHECKED]
        assert by_type(feed, "coverage.expected")[0]["domains"] == ["inbox"]
        assert by_type(feed, "coverage.reported") == []

    def test_unhealthy_arrives_as_a_report_saying_so(self):
        built = registry("inbox")
        built = built.report(
            DomainReport(name="inbox", checked_at=T0, healthy=False)
        )
        coverage = attest(built)
        feed = presence_feed(coverage, built)

        assert [g.kind for g in coverage.gaps] == [GapKind.UNHEALTHY]
        assert by_type(feed, "coverage.reported")[0]["healthy"] is False

    def test_stale_arrives_as_a_report_older_than_its_window(self):
        old = T0 - timedelta(hours=2)
        built = registry("inbox", window=WINDOW)
        built = built.report(
            DomainReport(name="inbox", checked_at=old, healthy=True)
        )
        coverage = attest(built)
        feed = presence_feed(coverage, built)

        assert [g.kind for g in coverage.gaps] == [GapKind.STALE]
        report = by_type(feed, "coverage.reported")[0]
        age = (T0 - datetime.fromisoformat(report["at"])).total_seconds()
        assert age > report["freshnessSeconds"]

    def test_a_complete_coverage_reports_every_domain_healthy(self):
        built, coverage = covered("inbox", "calendar")
        feed = presence_feed(coverage, built)

        assert coverage.complete is True
        reports = by_type(feed, "coverage.reported")
        assert len(reports) == 2
        assert all(r["healthy"] for r in reports)


# ═════════════════ B · the environment is carried, not redone ═══════════


class TestEnvironmentProjection:
    def test_it_is_c22s_own_projection_unchanged(self):
        derived = intelligence()
        assert environment_projection(derived) == derived.as_dict()

    def test_the_four_named_contracts_are_all_reachable(self):
        """`EnvironmentSummary` · `CapabilityGraph` · `UserProfile` ·
        `PreferenceModel` — the brief's four, under C22's own section
        names. This fails loudly if C22 ever renames one."""
        projected = environment_projection(intelligence())
        for contract, section in CONTRACT_SECTIONS:
            assert section in projected, f"{contract} is unreachable"
            assert projected[section] is not None

    def test_no_section_is_renamed_or_added(self):
        derived = intelligence()
        assert set(environment_projection(derived)) == set(derived.as_dict())

    def test_the_projection_does_not_mutate_the_reading(self):
        derived = intelligence()
        before = derived.as_dict()
        environment_projection(derived)
        assert derived.as_dict() == before

    def test_it_refuses_anything_that_is_not_a_reading(self):
        with pytest.raises(TypeError):
            environment_projection({"summary": {}})  # type: ignore[arg-type]


# ═════════════════ C · the conversation cannot speak ════════════════════


class TestConversationProjection:
    def test_a_user_turn_stays_a_user_turn(self):
        projected = conversation_projection(conversation(("user", "hello")))
        assert projected["entries"][0]["role"] == "user"

    def test_a_system_turn_stays_a_system_turn(self):
        projected = conversation_projection(conversation(("system", "done")))
        assert projected["entries"][0]["role"] == "system"

    @pytest.mark.parametrize(
        "speaker",
        ["assistant", "ai", "model", "Assistant", "USER", "", "kalpavriksha"],
    )
    def test_no_speaker_can_ever_produce_an_assistant_row(self, speaker):
        """C23: *do not invent responses*. C21's non-synthesis guarantee
        must not be defeatable one layer below where it is tested."""
        projected = conversation_projection(conversation((speaker, "text")))
        role = projected["entries"][0]["role"]
        assert role != "assistant"
        assert role in PROJECTED_ROLES

    def test_text_is_carried_verbatim_and_untrimmed(self):
        raw = "  spaced  \n"
        projected = conversation_projection(conversation(("user", raw)))
        assert projected["entries"][0]["text"] == raw

    def test_absent_facts_are_reported_absent_never_guessed(self):
        entry = conversation_projection(
            conversation(("user", "hi"))
        )["entries"][0]
        assert entry["executionId"] is None
        assert entry["streaming"] is False
        assert entry["supersededBy"] is None
        assert entry["missions"] == []

    def test_entries_are_addressed_by_position_in_order(self):
        projected = conversation_projection(
            conversation(("user", "one"), ("system", "two"), ("user", "three"))
        )
        assert [e["id"] for e in projected["entries"]] == [
            "turn-1",
            "turn-2",
            "turn-3",
        ]
        assert [e["text"] for e in projected["entries"]] == [
            "one",
            "two",
            "three",
        ]

    def test_an_empty_memory_projects_no_entries(self):
        assert conversation_projection(ConversationMemory()) == {"entries": []}

    def test_it_refuses_anything_that_is_not_a_conversation_memory(self):
        with pytest.raises(TypeError):
            conversation_projection([("user", "hi")])  # type: ignore[arg-type]


# ═══════════════════════════ D · the door ═══════════════════════════════


class TestTheDoor:
    def test_every_operation_answers_ok(self):
        runtime = wired()
        for operation in FounderOperation:
            answer = runtime.handle({OPERATION: operation.value})
            assert answer["kind"] == ResultKind.OK.value
            assert answer[OPERATION] == operation.value

    def test_snapshot_carries_every_section(self):
        payload = wired().handle({OPERATION: "snapshot"})["payload"]
        assert set(payload) == {
            "environment",
            "presence",
            "conversation",
            "sources",
        }

    def test_each_section_matches_its_own_operation(self):
        runtime = wired()
        snapshot = runtime.handle({OPERATION: "snapshot"})["payload"]
        for name in ("environment", "presence", "conversation"):
            single = runtime.handle({OPERATION: name})["payload"]
            assert single == snapshot[name]

    def test_an_unknown_operation_is_an_error_naming_its_own_class(self):
        answer = wired().handle({OPERATION: "authorize"})
        assert answer["kind"] == ResultKind.ERROR.value
        assert answer["payload"]["type"] == InvalidFounderEnvelope.__name__

    def test_the_error_echoes_the_operation_it_was_given(self):
        answer = wired().handle({OPERATION: "authorize"})
        assert answer[OPERATION] == "authorize"

    def test_a_kernel_operation_is_not_reachable_through_this_door(self):
        """Observation and authority are different doors, deliberately."""
        for name in ("authorize", "attempt", "settle", "invalidate"):
            answer = wired().handle({OPERATION: name})
            assert answer["kind"] == ResultKind.ERROR.value

    def test_a_non_mapping_envelope_is_an_error(self):
        answer = wired().handle(["snapshot"])  # type: ignore[arg-type]
        assert answer["kind"] == ResultKind.ERROR.value
        assert answer[OPERATION] is None

    def test_an_envelope_naming_no_operation_is_an_error(self):
        answer = wired().handle({})
        assert answer["kind"] == ResultKind.ERROR.value

    def test_arguments_are_refused_rather_than_ignored(self):
        answer = wired().handle(
            {OPERATION: "snapshot", ARGUMENTS: {"since": "yesterday"}}
        )
        assert answer["kind"] == ResultKind.ERROR.value
        assert "since" in answer["payload"]["message"]

    @pytest.mark.parametrize("arguments", [None, {}])
    def test_empty_arguments_are_accepted(self, arguments):
        answer = wired().handle({OPERATION: "status", ARGUMENTS: arguments})
        assert answer["kind"] == ResultKind.OK.value

    def test_non_mapping_arguments_are_an_error(self):
        answer = wired().handle({OPERATION: "status", ARGUMENTS: ["a"]})
        assert answer["kind"] == ResultKind.ERROR.value

    def test_the_whole_envelope_is_json(self):
        answer = wired().handle({OPERATION: "snapshot"})
        assert json.loads(json.dumps(answer)) == answer

    def test_the_door_is_deterministic(self):
        runtime = wired()
        assert runtime.handle({OPERATION: "snapshot"}) == runtime.handle(
            {OPERATION: "snapshot"}
        )

    def test_the_envelope_carries_three_keys_and_no_more(self):
        """C18's reason, unchanged: no status code, no version, no id, no
        timestamp — a wire field nobody reads is one somebody will
        eventually depend on."""
        answer = wired().handle({OPERATION: "status"})
        assert set(answer) == {OPERATION, "kind", "payload"}


# ═══════════════════════ E · absence is stated ══════════════════════════


class TestAbsence:
    def test_an_unwired_runtime_still_opens(self):
        answer = FounderRuntime().handle({OPERATION: "snapshot"})
        assert answer["kind"] == ResultKind.OK.value

    def test_a_missing_section_is_null_never_empty(self):
        payload = FounderRuntime().handle({OPERATION: "snapshot"})["payload"]
        assert payload["environment"] is None
        assert payload["conversation"] is None

    def test_missing_coverage_says_so_rather_than_feeding_nothing(self):
        presence = FounderRuntime().presence()
        assert presence["coverage"] is None
        assert presence["feed"]["observations"] == []
        assert presence["feed"]["absent_reason"]

    def test_every_source_is_named_with_a_reason(self):
        for source in FounderRuntime().sources():
            assert source.name
            assert source.reason
            assert isinstance(source.present, bool)

    def test_the_wired_sources_report_present(self):
        present = {s.name for s in wired().sources() if s.present}
        assert present == {
            "environment_intelligence",
            "vigilance",
            "conversation",
        }

    def test_authority_is_always_reported_unreachable(self):
        for runtime in (FounderRuntime(), wired()):
            authority = next(
                s for s in runtime.sources() if s.name == "kernel_authority"
            )
            assert authority.present is False
            assert authority.reason == AUTHORITY_UNREACHABLE

    def test_status_reports_the_same_sources_as_the_snapshot(self):
        runtime = wired()
        assert runtime.status()["sources"] == runtime.snapshot()["sources"]

    def test_a_source_projects_to_three_keys(self):
        projected = Source("x", True, "because").as_dict()
        assert projected == {"name": "x", "present": True, "reason": "because"}

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"intelligence": {"summary": {}}},
            {"coverage": {"complete": True}},
            {"registry": ["inbox"]},
            {"conversation": [("user", "hi")]},
        ],
    )
    def test_it_refuses_a_substitute_for_any_component(self, kwargs):
        with pytest.raises(TypeError):
            FounderRuntime(**kwargs)


# ═══════════════════ F · coverage travels beside the feed ═══════════════


class TestCoverageTravelsBesideTheFeed:
    """C19's `complete` is authoritative and is carried verbatim.

    A surface must never have to take a re-derivation's word for whether
    *"Nothing needs you."* may be said — VEDA 04 D7.
    """

    def test_the_coverage_projection_is_c19s_own(self):
        built, coverage = covered("inbox")
        runtime = FounderRuntime(coverage=coverage, registry=built)
        assert runtime.presence()["coverage"] == coverage.as_dict()

    def test_an_incomplete_coverage_says_incomplete(self):
        built = registry("inbox")
        runtime = FounderRuntime(coverage=attest(built), registry=built)
        assert runtime.presence()["coverage"]["complete"] is False

    def test_an_empty_registry_is_incomplete_and_unfed(self):
        runtime = FounderRuntime(coverage=attest(DomainRegistry()))
        presence = runtime.presence()
        assert presence["coverage"]["complete"] is False
        assert presence["feed"]["observations"] == []
        assert presence["feed"]["absent_reason"] == NOTHING_WATCHED


# ═══════════════════ G · nothing given is mutated ═══════════════════════


class TestNothingIsMutated:
    def test_reading_the_runtime_leaves_every_input_unchanged(self):
        built, coverage = covered("inbox", "calendar")
        derived = intelligence()
        memory = conversation(("user", "hi"))
        before = (
            derived.as_dict(),
            coverage.as_dict(),
            [t.text for t in memory.turns()],
            len(built),
        )

        runtime = FounderRuntime(
            intelligence=derived,
            coverage=coverage,
            registry=built,
            conversation=memory,
        )
        for _ in range(5):
            runtime.handle({OPERATION: "snapshot"})

        assert (
            derived.as_dict(),
            coverage.as_dict(),
            [t.text for t in memory.turns()],
            len(built),
        ) == before

    def test_two_runtimes_over_the_same_inputs_agree(self):
        built, coverage = covered("inbox")
        derived = intelligence()
        one = FounderRuntime(
            intelligence=derived, coverage=coverage, registry=built
        )
        two = FounderRuntime(
            intelligence=derived, coverage=coverage, registry=built
        )
        assert one.snapshot() == two.snapshot()


# ═══════════════════ H · structural guards, by AST ══════════════════════


def _modules() -> list[tuple[Path, ast.Module]]:
    return [
        (path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
        for path in sorted(PACKAGE.rglob("*.py"))
    ]


def _imports() -> set[str]:
    found: set[str] = set()
    for _, tree in _modules():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module)
    return found


def _called_names() -> set[str]:
    """Every callable expression, by its last two dotted segments."""
    found: set[str] = set()
    for _, tree in _modules():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                rendered = ast.unparse(node.func)
                found.add(rendered)
                found.add(".".join(rendered.split(".")[-2:]))
    return found


def _defined_names() -> set[str]:
    found: set[str] = set()
    for _, tree in _modules():
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                found.add(node.name)
    return found


class TestTheGuardsThemselves:
    """The guards must be able to fail. C21's could not, and passed."""

    def test_the_package_was_actually_found(self):
        paths = [path for path, _ in _modules()]
        assert len(paths) >= 4, f"scanned {len(paths)} modules under {PACKAGE}"

    def test_the_guards_read_identifiers_not_prose(self):
        """Every forbidden name below appears in a docstring in this
        package. A text-matching guard would fail on the explanation."""
        prose = "\n".join(
            path.read_text(encoding="utf-8") for path, _ in _modules()
        )
        for word in ("authorize", "assistant", "PresenceSnapshot", "execute"):
            assert word in prose
            assert word not in _imports()
            assert word not in _defined_names()


class TestNoFrozenComponentIsReached:
    FROZEN = (
        "master_agent.foundation",
        "master_agent.kernel",
        "master_agent.ledger",
        "master_agent.coordinator",
        "master_agent.api",
        "master_agent.runtime_bridge",
    )

    def test_no_frozen_package_is_imported(self):
        for module in _imports():
            for frozen in self.FROZEN:
                assert not module.startswith(frozen), (
                    f"{module} reaches the frozen {frozen}"
                )

    def test_frozen_source_is_untouched_by_this_component(self):
        src = PACKAGE.parent
        for package in (
            "foundation",
            "kernel",
            "ledger",
            "coordinator",
            "api",
            "runtime_bridge",
        ):
            assert (src / package).is_dir()
        assert not (PACKAGE / "kernel.py").exists()


class TestNothingExecutes:
    FORBIDDEN_MODULES = (
        "subprocess",
        "os",
        "shutil",
        "socket",
        "http",
        "urllib",
        "requests",
        "httpx",
        "threading",
        "asyncio",
        "multiprocessing",
        "random",
        "secrets",
        "time",
        "pathlib",
        "sqlite3",
        "winreg",
        "ctypes",
    )

    FORBIDDEN_SUBSYSTEMS = (
        "master_agent.executor",
        "master_agent.plugins",
        "master_agent.providers",
        "master_agent.broker",
        "master_agent.ai_infrastructure",
        "master_agent.orchestrator",
        "master_agent.runtime",
        "master_agent.mission_control",
        "master_agent.planner",
        "master_agent.brain",
        "master_agent.permissions",
    )

    def test_no_module_that_could_reach_the_machine_is_imported(self):
        imported = _imports()
        for module in self.FORBIDDEN_MODULES:
            assert module not in imported
            assert not any(
                name.startswith(f"{module}.") for name in imported
            )

    def test_no_execution_subsystem_is_imported(self):
        """Never execute tools · never call AI — structurally, not by
        promise."""
        for module in _imports():
            for forbidden in self.FORBIDDEN_SUBSYSTEMS:
                assert not module.startswith(forbidden), (
                    f"{module} gives this surface an execution path"
                )

    def test_no_clock_is_read(self):
        """Every moment is carried from the value it came with."""
        called = _called_names()
        for reader in (
            "datetime.now",
            "datetime.utcnow",
            "time.time",
            "time.monotonic",
            "clock.now",
            "random.random",
            "uuid.uuid4",
        ):
            assert reader not in called


class TestNothingIsDuplicated:
    def test_no_presence_type_is_redeclared(self):
        """The Presence Layer's contract stays the Presence Layer's."""
        defined = _defined_names()
        for owned_by_c20 in (
            "PresenceSnapshot",
            "CalmState",
            "VigilanceState",
            "CurrentActivity",
            "ReasoningSummary",
            "PendingApproval",
            "LastAction",
            "SnapshotMeta",
        ):
            assert owned_by_c20 not in defined

    def test_no_vigilance_type_is_redeclared(self):
        defined = _defined_names()
        for owned_by_c19 in ("Coverage", "Domain", "DomainStatus", "Gap"):
            assert owned_by_c19 not in defined

    def test_no_environment_type_is_redeclared(self):
        defined = _defined_names()
        for owned_by_c22 in (
            "EnvironmentSummary",
            "CapabilityGraph",
            "UserProfile",
            "PreferenceModel",
            "Inference",
            "Evidence",
        ):
            assert owned_by_c22 not in defined

    def test_no_scanning_or_deriving_is_performed_here(self):
        """C22 derives; this carries. C19 attests; this transcribes."""
        imported = _imports()
        called = _called_names()
        assert "master_agent.desktop.inventory" not in imported
        assert "master_agent.desktop.catalog" not in imported
        for name in (
            "derive_intelligence",
            "discover",
            "attest",
            "createPresenceLayer",
        ):
            assert name not in called
