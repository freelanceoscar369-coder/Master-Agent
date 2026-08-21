"""Sprint 1, Component 30 — Founder Edition Assembly.

The brief is composition, so almost every test here asks one of two
questions: *does the founder experience actually work end to end?* and
*was anything built twice?*

| Requirement | Source |
|---|---|
| System boots automatically; no manual initialization | C30 brief |
| Founder says "Good morning Somesh"; Somesh replies naturally | C30 brief |
| Conversation continues | C30 brief |
| Dashboard / Environment / Presence / Desktop readiness update | C30 brief |
| No duplicated initialization, state, or Runtime | C30 brief |
| Only composition — no new Runtime, Identity, Executive, Operator, Perception | C30 brief |
| No Mission OS | C30 brief |

C24's own suite (`tests/test_founder_edition_boot.py`) still runs
unchanged against this same package and still passes — that is the
regression evidence for *"do not recreate anything"*, and it is not
duplicated here.
"""
from __future__ import annotations

import ast
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from master_agent.desktop.execution.executor import DesktopExecutor
from master_agent.desktop.operations import DesktopExecutiveV2
from master_agent.desktop.perception import DesktopObserver
from master_agent.desktop.probe import CommandResult, ProcessInfo
from master_agent.desktop_operator import DesktopOperator
from master_agent.foundation.clock import ManualClock
from master_agent.founder_edition import (
    DASHBOARD_SECTIONS,
    OK,
    STEP_NAMES,
    UNAVAILABLE,
    DesktopLayer,
    FounderEditionApp,
    boot_founder_edition,
)
from master_agent.founder_edition import boot as boot_module
from master_agent.founder_runtime import FounderRuntime
from master_agent.memory.conversation import ConversationMemory

PACKAGE = (
    Path(__file__).resolve().parent.parent
    / "src" / "master_agent" / "founder_edition"
)

T0 = datetime(2026, 8, 7, 8, 30, tzinfo=UTC)


# ───────────────────────────── fixtures ─────────────────────────────────


class FakeProbe:
    """Mirrors C24's own fixture — no second convention invented here."""

    def __init__(self, explode: bool = False) -> None:
        self.platform = "win32"
        self._explode = explode

    def which(self, executable: str) -> str | None:
        if self._explode:
            raise RuntimeError("the probe is unreachable")
        return {"git": "/usr/bin/git", "python": "/usr/bin/python"}.get(executable)

    def exists(self, path: str) -> bool:
        return False

    def run(self, command: list[str]) -> CommandResult:
        return CommandResult(ok=True, output="")

    def processes(self) -> list[ProcessInfo]:
        if self._explode:
            raise RuntimeError("the probe is unreachable")
        return []

    def get_store_apps(self) -> list[dict]:
        return []

    def get_uninstall_apps(self) -> list[dict]:
        return []

    def get_start_apps(self) -> list[dict]:
        return []


class StubState:
    """Something with an `as_dict()`. `DesktopLayer.readiness` asks a
    `DesktopState` for exactly that and nothing else."""

    def as_dict(self) -> dict[str, object]:
        return {"applications": {}, "windows": {}, "stub": True}


class StubObserver(DesktopObserver):
    """A real `DesktopObserver` subclass whose `observe` touches no
    machine, so a readiness assertion is deterministic.

    A subclass rather than a bare fake for the same reason C24's own
    `_raise_once` uses one: `DesktopLayer.__init__` runs `isinstance`
    against `DesktopObserver`, and a stand-in that is not one would be
    testing a construction path the real boot never takes.
    """

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple] = []

    def observe(self, now, **kwargs):  # type: ignore[override]
        self.calls.append((now, tuple(sorted(kwargs))))
        return StubState()


def booted(**kwargs) -> FounderEditionApp:
    kwargs.setdefault("probe", FakeProbe())
    kwargs.setdefault("clock", ManualClock(T0))
    kwargs.setdefault("founder_name", "Onkar")
    return boot_founder_edition(**kwargs)


def stub_layer(inventory=None) -> tuple[DesktopLayer, StubObserver]:
    executive = DesktopExecutiveV2()
    executor = DesktopExecutor(desktop_executive=executive)
    observer = StubObserver()
    return (
        DesktopLayer(
            executive=executive,
            executor=executor,
            observer=observer,
            operator=DesktopOperator(executor, observer),
            inventory=inventory,
        ),
        observer,
    )


# ═════════════════ A · startup: the founder launches, it boots ══════════


class TestStartup:
    def test_one_call_boots_the_whole_edition_with_no_manual_wiring(self):
        """*"System boots automatically. No manual initialization."*"""
        app = booted()
        assert app.ready is True
        assert app.identity is not None
        assert app.session is not None
        assert app.desktop is not None

    def test_every_step_in_the_assembly_appears_in_order(self):
        assert tuple(s.name for s in booted().report.steps) == STEP_NAMES

    def test_every_c30_layer_reports_a_step_of_its_own(self):
        report = booted().report
        for name in (
            "founder_identity",
            "desktop_executive",
            "desktop_perception",
            "desktop_operator",
            "dashboard",
        ):
            assert report.step(name) is not None, name
            assert report.step(name).status == OK, name

    def test_the_operator_is_built_after_what_it_is_built_from(self):
        """Dependency order, not the brief's layering order — see
        `STEP_NAMES` for the argument."""
        names = [s.name for s in booted().report.steps]
        assert names.index("desktop_executive") < names.index("desktop_operator")
        assert names.index("desktop_perception") < names.index("desktop_operator")

    def test_ready_is_still_the_last_step(self):
        assert booted().report.steps[-1].name == "ready"

    def test_a_scan_failure_still_boots_a_usable_edition(self):
        app = booted(probe=FakeProbe(explode=True))
        assert app.report.step("environment_intelligence").status == UNAVAILABLE
        assert app.report.step("ready").ok
        assert app.say("Good morning Somesh")["reply"] is not None


# ═════════════════ B · conversation: the founder talks to Somesh ════════


class TestConversation:
    def test_the_briefs_own_example_end_to_end(self):
        """Founder: *"Good morning Somesh"* → Somesh replies naturally.

        The expected sentence is the founder's own, quoted verbatim in the
        canonical convergence brief §12: *"Good morning, Onkar. Somesh
        here. Everything is ready."* This asserted an earlier wording --
        *"Good morning. I'm awake."* -- from before the Founder Identity
        layer gave Somesh a name and the founder one. Naming both is the
        whole point of C29, so the newer sentence is the correct one and
        this assertion was simply behind it.
        """
        app = booted()
        result = app.say("Good morning Somesh")
        assert result["reply"] == "Good morning, Onkar. Somesh here. Everything is ready."

    def test_somesh_never_says_it_is_an_ai(self):
        app = booted()
        rendered = json.dumps(app.say("Good morning Somesh")).lower()
        for phrase in ("as an ai", "language model", "i cannot", "assistant"):
            assert phrase not in rendered

    def test_continue_resumes_without_re_introduction(self):
        app = booted()
        app.say("let's talk about the Q3 roadmap")
        result = app.say("Continue")
        assert result["reply"] == "Continuing."
        assert "Q3" not in result["reply"]

    def test_conversation_continues_across_turns(self):
        app = booted()
        app.say("Good morning Somesh")
        app.say("Continue")
        texts = [e["text"] for e in app.snapshot()["conversation"]["entries"]]
        assert texts[0] == "Good morning Somesh"
        assert texts[-1] == "Continuing."

    def test_somesh_turns_are_never_the_assistant_role(self):
        """C23's guarantee, held one layer up: `SOMESH` projects to
        `system`, and `assistant` stays unreachable."""
        app = booted()
        app.say("Good morning Somesh")
        app.say("Continue")
        roles = {e["role"] for e in app.snapshot()["conversation"]["entries"]}
        assert roles == {"user", "system"}
        assert "assistant" not in roles

    def test_the_speaker_somesh_is_recorded_under_is_never_assistant(self):
        assert boot_module.SOMESH != "assistant"
        assert boot_module.SOMESH != "user"

    def test_open_ended_speech_gets_no_invented_reply(self):
        """Nothing in C1–C29 composes prose for arbitrary founder speech,
        so nothing here pretends to — but the turn still lands."""
        app = booted()
        result = app.say("book me a flight to Bangalore next Tuesday")
        assert result["reply"] is None
        entries = app.snapshot()["conversation"]["entries"]
        assert len(entries) == 1
        assert entries[0]["text"] == "book me a flight to Bangalore next Tuesday"

    def test_send_still_composes_nothing_at_all(self):
        """C24's door is left exactly as it was — one send, one entry."""
        app = booted()
        app.send("are you there?")
        assert len(app.snapshot()["conversation"]["entries"]) == 1

    def test_say_refuses_a_non_string(self):
        with pytest.raises(TypeError):
            booted().say(12345)  # type: ignore[arg-type]

    def test_a_fresh_boot_still_carries_no_synthetic_greeting(self):
        """C24's guarantee, unchanged: booting does not fabricate a
        greeting. One only exists once the founder asks for one."""
        rendered = json.dumps(booted().snapshot())
        assert "Good morning" not in rendered


# ═════════════════ C · identity ═════════════════════════════════════════


class TestIdentity:
    def test_the_founders_name_reaches_somesh(self):
        app = booted(founder_name="Onkar")
        assert app.identity.founder_name == "Onkar"
        assert app.identity.assistant_name == "Somesh"

    def test_the_edition_is_named_without_exposing_internals(self):
        app = booted()
        rendered = json.dumps(app.dashboard()["identity"])
        for internal in ("Runtime", "Kernel", "Coordinator", "Bridge"):
            assert internal not in rendered

    def test_the_session_reads_the_apps_own_conversation(self):
        app = booted()
        app.say("Good morning Somesh")
        assert app.session.last_founder_utterance() == "Good morning Somesh"


# ═════════════════ D · presence and environment ═════════════════════════


class TestPresenceAndEnvironment:
    def test_presence_stays_honestly_incomplete(self):
        """C19/C23's R80 discipline survives assembly: no domain is
        registered, so calm is never manufactured."""
        dashboard = booted().dashboard()
        assert dashboard["presence"]["coverage"]["complete"] is False
        assert dashboard["presence"]["feed"]["observations"] == []

    def test_environment_is_c22s_own_projection(self):
        app = booted()
        assert app.dashboard()["environment"] == app.runtime.environment()

    def test_environment_absence_is_reported_not_faked(self):
        app = booted(probe=FakeProbe(explode=True))
        assert app.dashboard()["environment"] is None


# ═════════════════ E · dashboard ════════════════════════════════════════


class TestDashboard:
    def test_it_carries_every_named_section_in_order(self):
        assert tuple(booted().dashboard()) == DASHBOARD_SECTIONS

    def test_it_is_pure_json(self):
        app = booted()
        app._desktop = stub_layer()[0]  # deterministic readiness
        dashboard = app.dashboard()
        assert json.loads(json.dumps(dashboard)) == dashboard

    def test_it_updates_rather_than_caching(self):
        """*"Dashboard updates. Conversation continues."* — the same app,
        read twice, reflects what happened in between."""
        app = booted()
        before = app.dashboard()
        app.say("Good morning Somesh")
        after = app.dashboard()
        assert before["session"]["active"] is False
        assert after["session"]["active"] is True
        assert len(after["conversation"]["entries"]) > len(
            before["conversation"]["entries"]
        )

    def test_desktop_readiness_names_all_four_layers(self):
        layer, _ = stub_layer()
        readiness = layer.readiness(T0)
        assert [entry["name"] for entry in readiness["layers"]] == [
            "desktop_executive",
            "desktop_execution",
            "desktop_perception",
            "desktop_operator",
        ]

    def test_readiness_reads_perception_once_per_call(self):
        layer, observer = stub_layer()
        layer.readiness(T0)
        layer.readiness(T0)
        assert len(observer.calls) == 2

    def test_readiness_refuses_a_naive_moment(self):
        layer, _ = stub_layer()
        with pytest.raises(ValueError):
            layer.readiness(datetime(2026, 8, 7, 8, 30))  # noqa: DTZ001

    def test_an_unscanned_machine_says_so_rather_than_reporting_zero(self):
        layer, _ = stub_layer(inventory=None)
        readiness = layer.readiness(T0)
        assert readiness["installed_count"] is None
        assert readiness["inventory_absent_reason"]
        assert readiness["watching"] == []

    def test_a_dashboard_without_an_identity_refuses_rather_than_guessing(self):
        app = FounderEditionApp(
            runtime=FounderRuntime(),
            conversation=ConversationMemory(),
            report=boot_module.BootReport(),
        )
        with pytest.raises(RuntimeError):
            app.dashboard()


# ═════════════════ F · nothing was built twice ══════════════════════════


class TestNothingIsDuplicated:
    def test_the_machine_is_scanned_exactly_once(self, monkeypatch):
        """*"No duplicated initialization."* C24 scanned and discarded the
        inventory; C30 needs it for the desktop layer. A second
        `discover()` would be both wasteful and *wrong* — the two reads
        could disagree about a machine that changed in between."""
        calls = {"n": 0}
        real = boot_module.discover

        def counting(*args, **kwargs):
            calls["n"] += 1
            return real(*args, **kwargs)

        monkeypatch.setattr(boot_module, "discover", counting)
        booted()
        assert calls["n"] == 1

    def test_exactly_one_founder_runtime_is_constructed_and_connected(self):
        """*"No duplicated Runtime."* `boot.py` constructs a throwaway
        `FounderRuntime()` in step 1 to prove the door opens, then the
        connected one in step 5. Only the second is ever held, and the
        app hands back that one object every time."""
        app = booted()
        assert app.runtime is app.runtime
        assert app.dashboard()["sources"] == [
            s.as_dict() for s in app.runtime.sources()
        ]

    def test_the_operator_shares_the_one_executor_and_the_one_observer(self):
        """`DesktopOperator()` builds its own executor and observer when
        handed neither. If boot let it, the founder's dashboard would read
        one observation history while the operator's own Verify wrote to
        another."""
        desktop = booted().desktop
        assert desktop.operator._executor is desktop.executor
        assert desktop.operator._observer is desktop.observer

    def test_the_executor_shares_the_one_desktop_executive(self):
        desktop = booted().desktop
        assert desktop.executor._executive is desktop.executive

    def test_there_is_one_conversation_memory_and_the_session_reads_it(self):
        """*"No duplicated state."* `FounderSession` holds a reference,
        never a copy — so a turn recorded through `say()` is visible to
        the session, the runtime projection and the dashboard at once."""
        app = booted()
        app.say("Good morning Somesh")
        assert app.session.active is True
        assert app.session.last_founder_utterance() == "Good morning Somesh"
        assert app.runtime.conversation()["entries"][0]["text"] == (
            "Good morning Somesh"
        )

    def test_the_inventory_the_desktop_holds_is_the_one_boot_scanned(self):
        app = booted()
        assert app.desktop.inventory is not None
        assert app.desktop.inventory.platform == "win32"

    def test_the_desktop_layer_constructs_none_of_the_four_itself(self):
        """Every one is required at construction, so there is exactly one
        construction site for each and it is the boot sequence."""
        executive = DesktopExecutiveV2()
        executor = DesktopExecutor(desktop_executive=executive)
        observer = StubObserver()
        for kwargs in (
            {"executive": object()},
            {"executor": object()},
            {"observer": object()},
            {"operator": object()},
        ):
            base = {
                "executive": executive,
                "executor": executor,
                "observer": observer,
                "operator": DesktopOperator(executor, observer),
            }
            base.update(kwargs)
            with pytest.raises(TypeError):
                DesktopLayer(**base)


# ═════════════ F2 · every new layer fails honestly, never silently ══════


def _exploding(message: str):
    def boom(*args, **kwargs):
        raise RuntimeError(message)

    return boom


class TestEveryC30LayerReportsItsOwnFailure:
    """C24's rule, extended to the five steps C30 adds: *"a step that
    could not run reports `unavailable` with a reason, never `ok`"* — and
    the rest of the application still boots."""

    def test_an_identity_that_cannot_be_built_is_reported(self, monkeypatch):
        monkeypatch.setattr(
            boot_module, "FounderIdentity", _exploding("no founder")
        )
        app = booted()
        step = app.report.step("founder_identity")
        assert step.status == UNAVAILABLE
        assert "no founder" in step.detail
        assert app.identity is None
        # and the dashboard step reports the consequence rather than crashing
        assert app.report.step("dashboard").status == UNAVAILABLE

    def test_an_unbuildable_executive_takes_the_operator_with_it_honestly(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            boot_module, "DesktopExecutiveV2", _exploding("no knowledge base")
        )
        app = booted()
        assert app.report.step("desktop_executive").status == UNAVAILABLE
        operator_step = app.report.step("desktop_operator")
        assert operator_step.status == UNAVAILABLE
        assert "construct its own" in operator_step.detail
        assert app.desktop is None
        # the founder can still talk to Somesh
        assert app.say("Good morning Somesh")["reply"] is not None

    def test_perception_that_cannot_open_is_reported(self, monkeypatch):
        monkeypatch.setattr(
            boot_module, "DesktopObserver", _exploding("no perception")
        )
        app = booted()
        assert app.report.step("desktop_perception").status == UNAVAILABLE
        assert app.report.step("desktop_operator").status == UNAVAILABLE

    def test_a_desktop_layer_that_cannot_compose_is_reported(self, monkeypatch):
        monkeypatch.setattr(
            boot_module, "DesktopLayer", _exploding("cannot compose")
        )
        app = booted()
        step = app.report.step("desktop_operator")
        assert step.status == UNAVAILABLE
        assert "cannot compose" in step.detail
        assert app.desktop is None

    def test_a_dashboard_that_cannot_be_composed_is_reported(self, monkeypatch):
        monkeypatch.setattr(
            boot_module, "founder_dashboard", _exploding("cannot draw")
        )
        app = booted()
        step = app.report.step("dashboard")
        assert step.status == UNAVAILABLE
        assert "cannot draw" in step.detail
        assert app.report.step("ready").ok

    def test_an_abort_still_names_every_c30_layer(self, monkeypatch):
        """A boot that dies early must not silently omit the layers it
        never reached — the report would read as though they were never
        part of this assembly.

        The failure is injected on exactly the **first** construction,
        which is C24's own `_raise_once` model and its own reasoning:
        *"which is what an intermittent failure actually looks like,
        rather than the whole class vanishing."* `_abort()` builds a
        replacement `ConversationMemory` for the unwired app it returns,
        and a permanently-broken class would take that path down too —
        recorded as a finding in `Engineering/HEALTH_C30.md` §7 rather
        than fixed here, since repairing C24's abort path is not
        composition.
        """
        calls = {"n": 0}

        class FlakyMemory(ConversationMemory):
            def __init__(self, *args, **kwargs):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise RuntimeError("no memory")
                super().__init__(*args, **kwargs)

        monkeypatch.setattr(boot_module, "ConversationMemory", FlakyMemory)
        report = booted().report

        # The property that matters, and the one the docstring above
        # states: nothing is silently OMITTED. Every layer is named
        # whether or not the boot got to it.
        for name in (
            "founder_identity",
            "desktop_executive",
            "desktop_perception",
            "desktop_operator",
            "dashboard",
        ):
            assert report.step(name) is not None, f"{name} vanished from the report"

        # The three desktop layers now run BEFORE `conversation`, so a
        # boot that dies at conversation has genuinely already wired them
        # and reporting them as unavailable would be a lie. `boot.py`'s
        # own docstring carries both the old claim ("C30's five are
        # inserted after connect_founder_runtime") and the correction
        # underneath it ("C30 inserts desktop layer before
        # connect_founder_runtime, because the FounderRuntime now requires
        # the desktop layer"). This assertion was written against the
        # first and is now read against the second.
        for reached in ("desktop_executive", "desktop_perception", "desktop_operator"):
            assert report.step(reached).ok, f"{reached} runs before the failure"

        # What the abort never reached still says so.
        for unreached in ("founder_identity", "dashboard"):
            assert report.step(unreached).status == UNAVAILABLE, unreached
        assert report.steps[-1].name == "ready"


class TestConstructionRefusesSubstitutes:
    @pytest.mark.parametrize(
        "extra",
        [
            {"identity": object()},
            {"session": object()},
            {"desktop": object()},
        ],
    )
    def test_the_app_refuses_a_substitute_for_any_c30_component(self, extra):
        base = {
            "runtime": FounderRuntime(),
            "conversation": ConversationMemory(),
            "report": boot_module.BootReport(),
        }
        base.update(extra)
        with pytest.raises(TypeError):
            FounderEditionApp(**base)

    def test_say_without_an_identity_records_the_turn_and_composes_nothing(self):
        app = FounderEditionApp(
            runtime=FounderRuntime(conversation=(memory := ConversationMemory())),
            conversation=memory,
            report=boot_module.BootReport(),
        )
        result = app.say("Good morning Somesh")
        assert result["reply"] is None
        assert result["conversation"]["entries"][0]["text"] == "Good morning Somesh"

    @pytest.mark.parametrize(
        "broken",
        [
            {"runtime": object()},
            {"identity": object()},
            {"session": object()},
            {"desktop": object()},
        ],
    )
    def test_the_dashboard_refuses_a_substitute_for_any_section_source(
        self, broken
    ):
        memory = ConversationMemory()
        base = {
            "runtime": FounderRuntime(conversation=memory),
            "identity": boot_module.FounderIdentity(founder_name="Onkar"),
            "session": boot_module.FounderSession(memory),
            "boot": {},
            "desktop": None,
            "moment": T0,
        }
        base.update(broken)
        with pytest.raises(TypeError):
            boot_module.founder_dashboard(**base)

    def test_the_dashboard_refuses_a_naive_moment(self):
        memory = ConversationMemory()
        with pytest.raises(ValueError):
            boot_module.founder_dashboard(
                runtime=FounderRuntime(conversation=memory),
                identity=boot_module.FounderIdentity(founder_name="Onkar"),
                session=boot_module.FounderSession(memory),
                boot={},
                desktop=None,
                moment=datetime(2026, 8, 7, 8, 30),  # noqa: DTZ001
            )

    def test_the_desktop_layer_refuses_a_substitute_inventory(self):
        executive = DesktopExecutiveV2()
        executor = DesktopExecutor(desktop_executive=executive)
        observer = StubObserver()
        with pytest.raises(TypeError):
            DesktopLayer(
                executive=executive,
                executor=executor,
                observer=observer,
                operator=DesktopOperator(executor, observer),
                inventory=object(),
            )


# ═════════════════ G · only composition ═════════════════════════════════


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


def _defined_names() -> set[str]:
    found: set[str] = set()
    for _, tree in _modules():
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                found.add(node.name)
    return found


class TestOnlyComposition:
    def test_the_guard_actually_scanned_the_package(self):
        assert len(list(PACKAGE.rglob("*.py"))) >= 4

    @pytest.mark.parametrize(
        "owned_elsewhere",
        [
            "FounderRuntime",       # C23
            "FounderIdentity",      # C29
            "FounderSession",       # C29
            "DesktopExecutiveV2",   # C25
            "DesktopExecutor",      # C26
            "DesktopObserver",      # C27
            "DesktopOperator",      # C28
            "ConversationMemory",   # Layer 1
            "GreetingEngine",
            "ConversationContinuity",
        ],
    )
    def test_no_component_is_redeclared_here(self, owned_elsewhere):
        """*"No new Runtime. No new Identity. No new Executive. No new
        Operator. No new Perception. Only composition."*"""
        assert owned_elsewhere not in _defined_names()

    def test_no_greeting_or_continuation_prose_is_composed_here(self):
        """Every sentence Somesh says was written in `founder_identity/`.
        This package dispatches; it never authors."""
        prose = "\n".join(
            p.read_text(encoding="utf-8")
            for p, _ in _modules()
            if p.name != "boot.py"
        )
        assert "I'm awake" not in prose
        boot_source = (PACKAGE / "boot.py").read_text(encoding="utf-8")
        # boot.py may name C29's functions, but must not contain the
        # sentences they return.
        assert "I'm awake" not in boot_source
        assert "Continuing." not in boot_source

    def test_no_mission_os_surface_is_reachable(self):
        """*"No Mission OS."* Including the MB026/MB029 dashboard, which
        is fed by Mission Control's own contracts — see `dashboard.py`'s
        docstring for why this assembly does not consume it."""
        forbidden = (
            "master_agent.dashboard",
            "master_agent.mission_control",
            "master_agent.mission_manager",
            "master_agent.missions",
            "master_agent.planner",
            "master_agent.orchestrator",
            "master_agent.brain",
        )
        for module in _imports():
            for root in forbidden:
                assert not module.startswith(root), f"{module} reaches {root}"

    def test_no_founder_facing_door_starts_desktop_work(self):
        """C23: *"nothing the founder does on this surface can start,
        approve or cancel work."* The Operator is wired and idle, and this
        package exposes no method that hands it a mission."""
        public = {
            name for name in dir(FounderEditionApp) if not name.startswith("_")
        }
        for verb in ("execute", "run", "act", "perform", "dispatch", "operate"):
            assert verb not in public
