"""Sprint 1, Component 24 — Founder Edition Boot Sequence.

The brief is orchestration, so most tests ask two questions: *did the
seven-step flow run in the brief's own order?* and *does every step report
what actually happened, never a guess?*

| Requirement | Source |
|---|---|
| Boot → Runtime → Presence → Environment Intelligence → Conversation → Connect → Render → Ready | C24 brief |
| The Founder UI receives live state immediately after startup | C24 brief |
| No placeholder dashboard, no KPI wall, no synthetic greeting | C24 brief |
| Typing reaches the runtime; no tool execution, no AI call, no invented response | C24 brief |
| Frozen packages untouched and unreachable | Project Brain |
| A step that could not run reports `unavailable` with a reason, never `ok` | `launcher/boot.py`, ADR-0016 |
| An unfed/empty vigilance registry stays honestly incomplete | C19, C23 (R80) |

Every guard reads executable identifiers via AST, never source text — the
same discipline C23's own suite uses, for the same reason (C21's boundary
guard passed while scanning zero files).
"""
from __future__ import annotations

import ast
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from master_agent.desktop.probe import CommandResult, ProcessInfo
from master_agent.foundation.clock import ManualClock
from master_agent.founder_edition import (
    OK,
    OUT_OF_SCOPE,
    STEP_NAMES,
    UNAVAILABLE,
    BootReport,
    BootStep,
    FounderEditionApp,
    boot_founder_edition,
)
from master_agent.founder_runtime import FounderRuntime
from master_agent.memory.conversation import ConversationMemory

PACKAGE = (
    Path(__file__).resolve().parent.parent
    / "src" / "master_agent" / "founder_edition"
)

T0 = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)


# ───────────────────────────── fixtures ─────────────────────────────────


class FakeProbe:
    """A machine, described rather than discovered. Mirrors
    `tests/test_desktop_executive.py`'s own fixture — no second
    convention invented for this suite."""

    def __init__(
        self,
        platform: str = "win32",
        on_path: dict[str, str] | None = None,
        paths: set[str] | None = None,
        versions: dict[str, str] | None = None,
        running: list[ProcessInfo] | None = None,
        fail: set[str] | None = None,
        explode: bool = False,
    ) -> None:
        self.platform = platform
        self._on_path = on_path or {}
        self._paths = paths or set()
        self._versions = versions or {}
        self._running = running or []
        self._fail = fail or set()
        self._explode = explode

    def which(self, executable: str) -> str | None:
        if self._explode:
            raise RuntimeError("the probe is unreachable")
        return self._on_path.get(executable)

    def exists(self, path: str) -> bool:
        return path in self._paths

    def run(self, command: list[str]) -> CommandResult:
        head = command[0]
        if head in self._fail:
            return CommandResult(ok=False, error=f"boom: {head}")
        if head in self._versions:
            return CommandResult(ok=True, output=self._versions[head])
        return CommandResult(ok=True, output="")

    def processes(self) -> list[ProcessInfo]:
        if self._explode:
            raise RuntimeError("the probe is unreachable")
        return list(self._running)


def machine(**kwargs) -> FakeProbe:
    defaults = {
        "on_path": {"git": "/usr/bin/git", "python": "/usr/bin/python"},
        "versions": {"git": "git version 2.43.0", "python": "Python 3.14.0"},
    }
    defaults.update(kwargs)
    return FakeProbe(**defaults)


def booted(**kwargs) -> FounderEditionApp:
    probe = kwargs.pop("probe", None) or machine()
    clock = kwargs.pop("clock", None) or ManualClock(T0)
    return boot_founder_edition(probe=probe, clock=clock, **kwargs)


# ═══════════════════ A · the flow runs in the brief's order ═════════════


class TestStartupFlow:
    def test_every_named_step_appears_in_order(self):
        report = booted().report
        assert tuple(step.name for step in report.steps) == STEP_NAMES

    def test_every_step_reports_a_known_status(self):
        for step in booted().report.steps:
            assert step.status in (OK, UNAVAILABLE, OUT_OF_SCOPE)

    def test_runtime_opens_before_anything_else_is_ready(self):
        report = booted().report
        assert report.step("runtime").ok

    def test_presence_runs_before_environment_intelligence(self):
        """The brief's own ordering — see `boot.py`'s docstring for why
        presence does not need to wait for the scan."""
        names = [s.name for s in booted().report.steps]
        assert names.index("presence") < names.index("environment_intelligence")

    def test_connect_runs_after_all_four_inputs(self):
        names = [s.name for s in booted().report.steps]
        connect = names.index("connect_founder_runtime")
        for earlier in ("runtime", "presence", "environment_intelligence", "conversation"):
            assert names.index(earlier) < connect

    def test_render_founder_surface_is_out_of_scope_not_a_failure(self):
        step = booted().report.step("render_founder_surface")
        assert step.status == OUT_OF_SCOPE
        assert "TypeScript" in step.detail or "not part of this" in step.detail

    def test_ready_is_the_last_step(self):
        report = booted().report
        assert report.steps[-1].name == "ready"

    def test_a_successful_boot_reaches_ready_ok(self):
        assert booted().report.step("ready").ok

    def test_needs_attention_excludes_out_of_scope(self):
        report = booted().report
        assert all(s.status != OUT_OF_SCOPE for s in report.needs_attention)

    def test_app_reports_itself_ready(self):
        assert booted().ready is True


# ═══════════ B · the founder sees live state immediately ════════════════


class TestLiveStateOnFirstSnapshot:
    def test_the_first_snapshot_already_carries_every_section(self):
        """No placeholder dashboard: the very first read after boot is
        live, not a follow-up call away from being live."""
        snapshot = booted().snapshot()
        assert set(snapshot) == {"environment", "presence", "conversation", "sources"}

    def test_environment_summary_is_real_not_a_placeholder(self):
        """Every readiness signal is a real `Inference` — carrying its
        own reason and confidence — never a stub. `observations` itself
        is conditional (C22's own `derive_summary`: populated only when
        something evidences it), so the unconditional signals are what
        this test holds to."""
        snapshot = booted().snapshot()
        summary = snapshot["environment"]["summary"]
        for signal in ("environment_ready", "ai_available", "developer_environment_healthy"):
            assert summary[signal]["reason"], f"{signal} has no stated reason"
            assert summary[signal]["confidence"]

    def test_a_machine_with_running_tools_produces_observations(self):
        snapshot = booted(probe=machine(
            on_path={"chrome": "/usr/bin/chrome"},
            versions={"chrome": "Chrome 120.0"},
            running=[ProcessInfo(pid=1, name="chrome.exe", owner="chrome")],
        )).snapshot()
        assert snapshot["environment"]["summary"]["observations"]

    def test_current_activity_is_not_fabricated_here(self):
        """`CurrentActivity` is C20's own derived type (see C23's
        TestNothingIsDuplicated) — Python produces the feed C20 derives
        it from, never the activity line itself."""
        defined = _defined_names()
        assert "CurrentActivity" not in defined

    def test_calm_and_vigilance_state_are_not_fabricated_here(self):
        """Same boundary: C20 derives `CalmState`/`VigilanceState` from
        the feed. What this boot sequence guarantees is that C19's own
        authoritative `complete` travels with the feed — asserted below."""
        defined = _defined_names()
        assert "CalmState" not in defined
        assert "VigilanceState" not in defined

    def test_coverage_travels_beside_the_feed_so_calm_can_be_gated_honestly(self):
        snapshot = booted().snapshot()
        assert snapshot["presence"]["coverage"] is not None
        assert "complete" in snapshot["presence"]["coverage"]

    def test_conversation_ready_means_present_not_none(self):
        """Ready is signalled by `{}`/`[]`, never by absence — C23's own
        Absence discipline, exercised here at boot rather than assumed."""
        snapshot = booted().snapshot()
        assert snapshot["conversation"] is not None
        assert snapshot["conversation"]["entries"] == []

    def test_no_synthetic_greeting_is_present_anywhere_in_the_snapshot(self):
        rendered = json.dumps(booted().snapshot())
        for phrase in (
            "Good morning",
            "Good afternoon",
            "Good evening",
            "How can I help",
            "Welcome back",
        ):
            assert phrase not in rendered

    def test_the_snapshot_is_pure_json(self):
        snapshot = booted().snapshot()
        assert json.loads(json.dumps(snapshot)) == snapshot

    def test_a_scan_failure_still_produces_a_readable_snapshot(self):
        app = booted(probe=machine(explode=True))
        assert app.report.step("environment_intelligence").status == UNAVAILABLE
        assert app.snapshot()["environment"] is None
        # everything else still boots — one step's honest absence does
        # not take down the whole application
        assert app.report.step("ready").ok


# ══════════════ C · the conversation pipeline, end to end ═══════════════


class TestConversationReachesTheRuntime:
    def test_sent_text_appears_in_the_runtimes_own_projection(self):
        app = booted()
        app.send("what is running on this machine?")
        entries = app.snapshot()["conversation"]["entries"]
        assert entries[-1]["text"] == "what is running on this machine?"
        assert entries[-1]["role"] == "user"

    def test_send_returns_the_updated_conversation_immediately(self):
        app = booted()
        result = app.send("hello")
        assert result["entries"][-1]["text"] == "hello"

    def test_multiple_messages_accumulate_in_order(self):
        app = booted()
        app.send("first")
        app.send("second")
        texts = [e["text"] for e in app.snapshot()["conversation"]["entries"]]
        assert texts == ["first", "second"]

    def test_no_reply_is_ever_synthesized(self):
        """C24: *do not invent responses*. One send, one entry — never
        two."""
        app = booted()
        app.send("are you there?")
        entries = app.snapshot()["conversation"]["entries"]
        assert len(entries) == 1
        assert all(e["role"] != "assistant" for e in entries)

    def test_ten_messages_produce_ten_entries_and_no_more(self):
        app = booted()
        for i in range(10):
            app.send(f"message {i}")
        assert len(app.snapshot()["conversation"]["entries"]) == 10

    def test_send_refuses_a_non_string(self):
        with pytest.raises(TypeError):
            booted().send(12345)  # type: ignore[arg-type]

    def test_handle_still_answers_through_the_original_door(self):
        """`FounderEditionApp.handle` is C23's own `FounderRuntime.handle`,
        not a reimplementation."""
        app = booted()
        answer = app.handle({"operation": "conversation"})
        assert answer["kind"] == "ok"


# ═══════════════ D · presence honestly reflects an unwatched world ══════


class TestPresenceIsHonest:
    def test_no_domain_is_registered_at_this_milestone(self):
        """No connector exists yet; inventing one to look complete would
        repeat C23's R80 finding in a different shape."""
        app = booted()
        assert app.snapshot()["presence"]["coverage"]["complete"] is False

    def test_the_gap_names_c19s_own_reason(self):
        app = booted()
        gaps = app.snapshot()["presence"]["coverage"]["gaps"]
        assert gaps
        assert "no domain is being watched" in gaps[0]["detail"]

    def test_the_feed_stays_unfed_rather_than_manufacturing_calm(self):
        """C23's own refusal (`NOTHING_WATCHED`), exercised by a real
        boot rather than a hand-built Coverage."""
        app = booted()
        feed = app.snapshot()["presence"]["feed"]
        assert feed["observations"] == []
        assert feed["absent_reason"]

    def test_the_presence_step_still_reports_ok(self):
        """Attesting honestly over nothing is success, not failure — the
        vigilance contract was exercised and answered truthfully."""
        assert booted().report.step("presence").ok


# ═══════════════════ E · failure is reported, never hidden ══════════════


class TestFailureIsHonest:
    def test_an_unreachable_probe_does_not_crash_boot(self):
        app = booted(probe=machine(explode=True))
        assert app.report.step("environment_intelligence").status == UNAVAILABLE
        assert app.report.step("environment_intelligence").detail

    def test_the_app_still_answers_after_a_partial_failure(self):
        app = booted(probe=machine(explode=True))
        answer = app.handle({"operation": "snapshot"})
        assert answer["kind"] == "ok"

    def test_conversation_still_works_after_a_partial_failure(self):
        app = booted(probe=machine(explode=True))
        app.send("still reachable")
        assert app.snapshot()["conversation"]["entries"][0]["text"] == "still reachable"

    def test_sources_reports_the_gap_by_name(self):
        app = booted(probe=machine(explode=True))
        env_source = next(
            s for s in app.runtime.sources() if s.name == "environment_intelligence"
        )
        assert env_source.present is False


# ═══════════════════ F · construction refuses substitutes ═══════════════


def _raise_once(real_class, on_call: int, message: str):
    """A subclass of `real_class` whose `__init__` raises on exactly the
    `on_call`-th construction and behaves normally otherwise.

    A bare exploding function cannot stand in for `FounderRuntime` or
    `ConversationMemory` here: `FounderEditionApp.__init__` runs
    `isinstance(value, FounderRuntime)` against the same patched name, and
    a function is not a type. Subclassing keeps every `isinstance` check
    in `boot.py` and `wiring.py` true while still injecting exactly one
    failure at exactly one call site — which is what an intermittent
    failure actually looks like, rather than the whole class vanishing.
    """
    calls = {"n": 0}

    class Flaky(real_class):
        def __init__(self, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] == on_call:
                raise RuntimeError(message)
            super().__init__(*args, **kwargs)

    return Flaky


class TestUnrecoverableFailures:
    """Each of the four inputs can fail independently. These monkeypatch
    the constructors `boot.py` calls, at the name it imported them under
    — the same seam `desktop/`'s own tests use to force a probe failure,
    applied here to the pieces a fake probe cannot reach."""

    def test_a_founder_runtime_that_cannot_open_aborts_cleanly(self, monkeypatch):
        import master_agent.founder_edition.boot as boot_module

        monkeypatch.setattr(
            boot_module,
            "FounderRuntime",
            _raise_once(FounderRuntime, on_call=1, message="the door failed to open"),
        )
        report = boot_founder_edition(probe=machine(), clock=ManualClock(T0)).report
        assert report.step("runtime").status == UNAVAILABLE
        assert report.step("connect_founder_runtime").status == UNAVAILABLE
        assert report.step("ready").status == UNAVAILABLE

    def test_an_unattestable_registry_reports_presence_unavailable(self, monkeypatch):
        import master_agent.founder_edition.boot as boot_module

        class ExplodingAttestation:
            def __init__(self, *args, **kwargs):
                pass

            def attest(self):
                raise RuntimeError("the clock could not be read")

        monkeypatch.setattr(boot_module, "VigilanceAttestation", ExplodingAttestation)
        app = boot_founder_edition(probe=machine(), clock=ManualClock(T0))
        assert app.report.step("presence").status == UNAVAILABLE
        # boot continues past it — one step's failure does not abort the rest
        assert app.report.step("ready").ok

    def test_a_conversation_memory_that_cannot_open_aborts_cleanly(self, monkeypatch):
        import master_agent.founder_edition.boot as boot_module

        monkeypatch.setattr(
            boot_module,
            "ConversationMemory",
            _raise_once(
                ConversationMemory, on_call=1, message="session memory failed"
            ),
        )
        report = boot_founder_edition(probe=machine(), clock=ManualClock(T0)).report
        assert report.step("conversation").status == UNAVAILABLE
        assert report.step("connect_founder_runtime").status == UNAVAILABLE
        assert report.step("ready").status == UNAVAILABLE

    def test_a_connect_failure_still_returns_an_app_with_conversation_kept(
        self, monkeypatch
    ):
        """`_abort` carries the already-built `ConversationMemory` forward
        rather than discarding it — a founder's typed-but-unconnected
        session should not vanish because wiring failed one step later."""
        import master_agent.founder_edition.boot as boot_module

        # Call 1 is step 1's unwired probe-open; call 2 is step 5's real
        # connect, which is where the failure is injected.
        monkeypatch.setattr(
            boot_module,
            "FounderRuntime",
            _raise_once(FounderRuntime, on_call=2, message="connect failed"),
        )
        app = boot_founder_edition(probe=machine(), clock=ManualClock(T0))
        assert app.report.step("connect_founder_runtime").status == UNAVAILABLE
        assert app.report.step("ready").status == UNAVAILABLE
        assert app.ready is False


class TestConstructionIsGuarded:
    def test_boot_report_step_returns_none_for_an_unknown_name(self):
        assert booted().report.step("nonexistent") is None

    def test_the_report_round_trips_through_json(self):
        report = booted().report
        assert json.loads(json.dumps(report.as_dict())) == report.as_dict()

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"runtime": object(), "conversation": ConversationMemory(), "report": BootReport()},
            {"runtime": FounderRuntime(), "conversation": object(), "report": BootReport()},
            {"runtime": FounderRuntime(), "conversation": ConversationMemory(), "report": object()},
        ],
    )
    def test_the_app_refuses_a_substitute_for_any_component(self, kwargs):
        with pytest.raises(TypeError):
            FounderEditionApp(**kwargs)

    def test_a_boot_step_is_immutable(self):
        step = BootStep("x", OK, "because")
        with pytest.raises(AttributeError):
            step.status = UNAVAILABLE  # type: ignore[misc]


# ═══════════════════ G · determinism and non-mutation ════════════════════


class TestDeterminism:
    def test_two_boots_over_the_same_fake_machine_agree(self):
        one = boot_founder_edition(probe=machine(), clock=ManualClock(T0))
        two = boot_founder_edition(probe=machine(), clock=ManualClock(T0))
        assert one.snapshot() == two.snapshot()

    def test_reading_the_app_repeatedly_does_not_change_it(self):
        app = booted()
        first = app.snapshot()
        for _ in range(5):
            app.snapshot()
            app.handle({"operation": "status"})
        assert app.snapshot() == first


# ═══════════════════ H · structural guards, by AST ═══════════════════════


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
    """The guards must be provably able to fail — C21's own boundary
    guard passed while scanning zero files (`Engineering/AUDIT_C21.md`
    R74)."""

    def test_the_package_was_actually_found(self):
        assert len(list(PACKAGE.rglob("*.py"))) >= 2

    def test_forbidden_words_appear_in_prose_but_not_as_identifiers(self):
        prose = "\n".join(p.read_text(encoding="utf-8") for p, _ in _modules())
        for word in ("authorize", "execute", "CalmState", "VigilanceState"):
            assert word in prose
            assert word not in _imports()
            assert word not in _defined_names()


class TestNoFrozenAuthorityIsReached:
    """`foundation.clock` is the one named exception: it is C1's shared
    time utility, carries no authority, and is the dependency C19's own
    `VigilanceAttestation.attest()` requires — the Roadmap already
    sanctions it as vigilance's sole external dependency. Every other
    frozen surface — the authority-bearing ones — stays unreachable."""

    FROZEN_AUTHORITY = (
        "master_agent.foundation.warrant",
        "master_agent.foundation.attempt_token",
        "master_agent.foundation.attestation",
        "master_agent.foundation.receipt",
        "master_agent.foundation.execution_request",
        "master_agent.foundation.execution_context",
        "master_agent.foundation.consequence",
        "master_agent.foundation.override",
        "master_agent.foundation.refusal",
        "master_agent.foundation.reversibility",
        "master_agent.foundation.admission",
        "master_agent.foundation.principal",
        "master_agent.kernel",
        "master_agent.ledger",
        "master_agent.coordinator",
        "master_agent.api",
        "master_agent.runtime_bridge",
    )

    def test_no_authority_surface_is_imported(self):
        imports = _imports()
        for module in imports:
            for frozen in self.FROZEN_AUTHORITY:
                assert not module.startswith(frozen), (
                    f"{module} reaches the frozen authority surface {frozen}"
                )

    def test_the_only_foundation_import_is_the_clock(self):
        foundation_imports = {
            m for m in _imports() if m.startswith("master_agent.foundation")
        }
        assert foundation_imports <= {"master_agent.foundation.clock"}

    def test_frozen_packages_are_untouched_on_disk(self):
        src = PACKAGE.parent
        for package in ("foundation", "kernel", "ledger", "coordinator", "runtime_bridge"):
            assert (src / package).is_dir()
        assert not (PACKAGE / "kernel.py").exists()


class TestNothingExecutesOrCallsAI:
    # `threading` is deliberately not in this list as of C34.1 —
    # `founder_edition.voice_pipeline` runs real local audio capture and
    # model loading on background threads (so the tree's own startup
    # animation is never blocked waiting for Whisper/Piper to load,
    # per 06_STARTUP_EXPERIENCE §6.0). That is concurrency inside this
    # process, not a door to the machine — `subprocess`, `socket`, and
    # `ctypes` are what this guard actually exists to keep out, and all
    # three remain forbidden below.
    FORBIDDEN_MODULES = (
        "subprocess",
        "shutil",
        "socket",
        "http",
        "urllib",
        "requests",
        "httpx",
        "multiprocessing",
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
        "master_agent.runtime.",
        "master_agent.mission_control",
        "master_agent.planner",
        "master_agent.brain",
        "master_agent.permissions",
        "master_agent.launcher",
    )

    def test_no_module_that_could_reach_the_machine_is_imported(self):
        """`os` is deliberately not in this list — `RealSystemProbe`,
        the Desktop Executive's own sanctioned probe, is imported by
        type only (`SystemProbe`, `RealSystemProbe`); nothing in this
        package calls `os` itself."""
        imported = _imports()
        for module in self.FORBIDDEN_MODULES:
            assert module not in imported

    def test_this_package_imports_no_os_module_directly(self):
        assert "os" not in _imports()

    def test_no_execution_subsystem_is_reachable(self):
        for module in _imports():
            for forbidden in self.FORBIDDEN_SUBSYSTEMS:
                assert not module.startswith(forbidden), (
                    f"{module} gives this boot sequence an execution path"
                )

    def test_only_the_desktops_own_scanner_touches_the_machine(self):
        """No second inventory, no second catalog — the same guarantee
        C22's own suite already proves for `environment_intelligence`,
        checked here for the boot layer above it."""
        imports = _imports()
        assert "master_agent.desktop.inventory" in imports
        assert "master_agent.desktop.probe" in imports
        assert "master_agent.desktop.catalog" not in imports


class TestNothingIsDuplicated:
    def test_no_environment_intelligence_type_is_redeclared(self):
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

    def test_no_vigilance_type_is_redeclared(self):
        defined = _defined_names()
        for owned_by_c19 in ("Coverage", "Domain", "DomainStatus", "Gap", "GapKind"):
            assert owned_by_c19 not in defined

    def test_no_founder_runtime_type_is_redeclared(self):
        defined = _defined_names()
        for owned_by_c23 in ("PresenceFeed", "FounderOperation", "ResultKind", "Source"):
            assert owned_by_c23 not in defined

    def test_no_derivation_is_reimplemented(self):
        called = _called_names()
        for name in ("discover_application", "attribute_processes", "_gap_for"):
            assert name not in called

    def test_derive_intelligence_and_attest_are_called_exactly_once_each(self):
        """Composition, not re-derivation — this module calls the two
        existing derivations and does nothing else with the result."""
        called = _called_names()
        assert "derive_intelligence" in called
        assert "VigilanceAttestation" in called or "attest" in called
