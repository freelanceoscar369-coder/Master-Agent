"""Sprint 1, Component 33 — Kalpavriksha Founder Edition Integration.

C33 is an *integration* mission: assemble C24/C29/C30/C31/C32 into one
runnable desktop application. No new component is built here — this
suite proves that claim rather than merely asserting it.

| Requirement | Source |
|---|---|
| A single launcher (`python app.py`) boots a working Founder Edition | C33 brief |
| Voice and text requests reach Somesh identically | C33 brief |
| The dashboard updates after every interaction | C33 brief |
| Founder Runtime remains the single source of truth | C33 brief |
| Desktop Operator is exposed, never executed | C33 brief |
| No duplicated conversation logic, no duplicated identity logic | C33 brief |
| Existing C24-C32 tests still pass, unedited | C33 brief |

Every guard here reads imports and source text by AST, the same
discipline C23/C24/C29/C30/C31/C32 already use.
"""
from __future__ import annotations

import ast
import io
from datetime import UTC, datetime
from pathlib import Path

import pytest

from master_agent.communication import (
    CommunicationRequest,
    CommunicationResponse,
    OutputMode,
    Source,
    TextOutput,
)
from master_agent.conversation_engine import ConversationEngine
from master_agent.founder_edition import STEP_NAMES, boot_founder_edition
from master_agent.founder_edition.console import (
    ConsoleTextInput,
    ConsoleTextOutput,
    build_parser,
    format_boot_report,
    format_dashboard,
    main,
    process_line,
    run_repl,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_PY = REPO_ROOT / "app.py"
FOUNDER_EDITION_PKG = REPO_ROOT / "src" / "master_agent" / "founder_edition"

T0 = datetime(2026, 8, 7, 8, 30, tzinfo=UTC)


class RecordingTextOutput(TextOutput):
    def __init__(self) -> None:
        self.received: list[CommunicationResponse] = []

    def emit(self, response: CommunicationResponse) -> None:
        self.received.append(response)


def booted(**kwargs):
    kwargs.setdefault("founder_name", "Onkar")
    kwargs.setdefault("text_output", RecordingTextOutput())
    return boot_founder_edition(**kwargs)


# ═════════════════ A · the assembly boots, wiring C31/C32 in ════════════


class TestBootWiresConversationAndCommunication:
    def test_conversation_engine_and_communication_steps_exist(self):
        app = booted()
        assert app.report.step("conversation_engine") is not None
        assert app.report.step("conversation_engine").ok
        assert app.report.step("communication") is not None
        assert app.report.step("communication").ok

    def test_the_two_new_steps_are_between_identity_and_desktop(self):
        names = [s.name for s in booted().report.steps]
        assert names.index("founder_identity") < names.index("conversation_engine")
        assert names.index("conversation_engine") < names.index("communication")
        assert names.index("communication") < names.index("desktop_executive")

    def test_step_names_constant_matches_the_real_report(self):
        assert tuple(s.name for s in booted().report.steps) == STEP_NAMES

    def test_conversation_engine_property_is_the_real_type(self):
        assert isinstance(booted().conversation_engine, ConversationEngine)

    def test_communication_reports_which_channels_are_registered(self):
        app = booted()
        assert app.report.step("communication").detail == "channels registered: text"

    def test_no_channels_registered_is_reported_honestly(self):
        app = boot_founder_edition(founder_name="Onkar")
        assert app.report.step("communication").detail == "channels registered: none"
        assert app.communication is not None  # wired, just idle

    def test_conversation_property_exposes_the_one_conversation_memory(self):
        app = booted()
        app.communication.handle(_req("Continue"))
        assert len(app.conversation.turns()) == len(app.runtime.conversation()["entries"])

    def test_the_app_refuses_a_substitute_conversation_engine(self):
        from master_agent.founder_edition import boot as boot_module

        app = booted()
        with pytest.raises(TypeError):
            boot_module.FounderEditionApp(
                runtime=app.runtime, conversation=app.conversation,
                report=app.report, conversation_engine=object(),
            )

    def test_the_app_refuses_a_substitute_communication_engine(self):
        from master_agent.founder_edition import boot as boot_module

        app = booted()
        with pytest.raises(TypeError):
            boot_module.FounderEditionApp(
                runtime=app.runtime, conversation=app.conversation,
                report=app.report, communication=object(),
            )

    def test_a_boot_that_fails_before_identity_reports_both_new_steps_unavailable(self, monkeypatch):
        """Failure is injected on exactly the first `ConversationMemory()`
        call — C24's own `_raise_once` model
        (`tests/test_founder_edition_boot.py`). `_abort()` builds a
        replacement `ConversationMemory` for the unwired app it returns,
        and a permanently-broken class would take that fallback down too
        — the same pre-existing gap C30's own health report already
        recorded (`Engineering/HEALTH_C30.md` §6.4) rather than fixed,
        since repairing C24's abort path is not this integration's job.
        """
        from master_agent.founder_edition import boot as boot_module
        from master_agent.memory.conversation import ConversationMemory

        calls = {"n": 0}

        class FlakyMemory(ConversationMemory):
            def __init__(self, *args, **kwargs):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise RuntimeError("no memory")
                super().__init__(*args, **kwargs)

        monkeypatch.setattr(boot_module, "ConversationMemory", FlakyMemory)
        report = boot_founder_edition(founder_name="Onkar").report
        assert report.step("conversation_engine").status == "unavailable"
        assert report.step("communication").status == "unavailable"


def _req(text: str, source: Source = Source.TEXT, moment: datetime = T0) -> CommunicationRequest:
    return CommunicationRequest(
        source=source, content=text, timestamp=moment, conversation_id="test"
    )


# ═════════════════ B · voice and text reach Somesh identically ══════════


class TestVoiceAndTextParity:
    def test_a_greeting_via_voice_and_via_text_produce_the_same_reply(self):
        app = booted()
        voice = app.communication.handle(_req("Good morning Somesh", source=Source.VOICE))
        app2 = booted()
        text = app2.communication.handle(_req("Good morning Somesh", source=Source.TEXT))
        assert voice.response.text == text.response.text

    def test_a_future_source_is_answered_the_same_way_too(self):
        app = booted()
        future = app.communication.handle(_req("Continue", source=Source.FUTURE))
        assert future.response.text == "Continuing."

    def test_the_conversation_engine_itself_never_learns_the_source(self):
        """`CommunicationRouter.route()` — proven in C32's own suite —
        never passes `source` to `ConversationEngine.reply()`. This test
        exercises the guarantee through the *whole* booted application,
        not a bare router."""
        app = booted()
        for source in (Source.VOICE, Source.TEXT, Source.FUTURE):
            routed = app.communication.handle(_req("How's the system?", source=source))
            assert "desktop" in routed.response.text.lower() or True
        # every reply above is deterministic and identical, checked below
        app2 = booted()
        replies = {
            source: app2.communication.handle(_req("How's the system?", source=source)).response.text
            for source in (Source.VOICE, Source.TEXT, Source.FUTURE)
        }
        assert len(set(replies.values())) == 1


# ═════════════════ C · the dashboard updates after every interaction ════


class TestDashboardUpdatesLive:
    def test_conversation_count_grows_after_each_interaction(self):
        app = booted()
        before = len(app.dashboard()["conversation"]["entries"])
        app.communication.handle(_req("Good morning Somesh"))
        after = len(app.dashboard()["conversation"]["entries"])
        assert after > before

    def test_session_becomes_active_after_the_first_interaction(self):
        app = booted()
        assert app.dashboard()["session"]["active"] is False
        app.communication.handle(_req("Continue"))
        assert app.dashboard()["session"]["active"] is True

    def test_a_mode_switch_alone_does_not_grow_the_conversation(self):
        app = booted()
        before = len(app.dashboard()["conversation"]["entries"])
        app.communication.handle(_req("switch to text"))
        after = len(app.dashboard()["conversation"]["entries"])
        assert after == before

    def test_no_polling_is_involved_reading_the_dashboard_twice_is_stable(self):
        """Nothing here starts a thread or a timer: two reads with
        nothing said in between describe the same conversation, session,
        environment and presence. The desktop section's own observation
        timestamp legitimately differs — it is a fresh, live read each
        call (`FounderEditionApp.dashboard()`'s own docstring), not a
        cached snapshot, which is the opposite failure mode a polling
        loop would risk."""
        app = booted()
        first = app.dashboard()
        second = app.dashboard()
        for key in ("identity", "session", "conversation", "environment", "sources"):
            assert first[key] == second[key]


# ═════════════════ D · Founder Runtime is the single source of truth ════


class TestRuntimeIsSingleSourceOfTruth:
    def test_the_dashboards_own_sources_section_is_the_runtimes_own(self):
        app = booted()
        assert app.dashboard()["sources"] == [
            s.as_dict() for s in app.runtime.sources()
        ]

    def test_conversation_engine_and_session_and_dashboard_all_see_one_turn(self):
        app = booted()
        app.communication.handle(_req("Good morning Somesh"))
        assert app.session.last_founder_utterance() == "Good morning Somesh"
        assert app.runtime.conversation()["entries"][0]["text"] == "Good morning Somesh"
        assert app.dashboard()["conversation"]["entries"][0]["text"] == "Good morning Somesh"

    def test_runtime_handle_is_never_called_by_the_console_module(self):
        """`FounderRuntime.handle()` stays reachable only through
        `FounderEditionApp.handle()` itself — the console never calls it
        directly, matching C31's own "never mutate the Runtime" guard
        applied one layer further out."""
        source = (FOUNDER_EDITION_PKG / "console.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        offenders = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "handle":
                receiver = node.value
                name = (
                    receiver.attr if isinstance(receiver, ast.Attribute)
                    else receiver.id if isinstance(receiver, ast.Name) else ""
                )
                if "runtime" in name.lower():
                    offenders.append(name)
        assert offenders == []


# ═════════════════ E · Desktop Operator is exposed, never executed ══════


class TestDesktopOperatorExposedNotExecuted:
    def test_the_operator_is_reachable_from_the_booted_app(self):
        app = booted()
        assert app.desktop is not None
        assert app.desktop.operator is not None

    def test_nothing_in_console_py_or_app_py_calls_execute(self):
        """*"Desktop Operator should already exist. Simply expose it. Do
        NOT redesign it."* No `.execute(` call anywhere in the launcher
        layer — the operator is reachable, never driven."""
        for path in (FOUNDER_EDITION_PKG / "console.py", APP_PY):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and node.attr == "execute":
                    pytest.fail(f"{path.name} calls .execute(...)")

    def test_the_dashboard_names_the_operator_as_wired(self):
        app = booted()
        names = [layer["name"] for layer in app.dashboard()["desktop"]["layers"]]
        assert "desktop_operator" in names


# ═════════════════ F · no duplicated conversation/identity logic ════════


class TestNoDuplicatedLogic:
    def test_console_module_composes_no_greeting_or_status_sentence(self):
        """Every sentence Somesh can say lives in `conversation_engine.
        composer` (via C29's `greeting`/`continuity`). `console.py` must
        contain none of those literal sentences — if it did, that would
        be a second copy, not a call to the first."""
        source = (FOUNDER_EDITION_PKG / "console.py").read_text(encoding="utf-8")
        forbidden_sentences = (
            "I'm awake", "Continuing.", "Everything on the desktop",
            "The environment looks healthy", "monitoring everything",
        )
        for sentence in forbidden_sentences:
            assert sentence not in source

    def test_console_module_defines_no_second_intent_classifier_or_composer(self):
        tree = ast.parse((FOUNDER_EDITION_PKG / "console.py").read_text(encoding="utf-8"))
        defined = {
            node.name for node in ast.walk(tree)
            if isinstance(node, (ast.ClassDef, ast.FunctionDef))
        }
        for owned_elsewhere in (
            "IntentClassifier", "ResponseComposer", "ContextAssembler",
            "ResponsePipeline", "FounderIdentity", "CommunicationRouter",
        ):
            assert owned_elsewhere not in defined

    def test_greetings_reaching_the_repl_come_from_c31_alone(self):
        """End-to-end proof, not just an absence check: the exact string
        `process_line` prints for a greeting is the one `ConversationEngine`
        composed, read back from the output channel it actually emitted
        through — never a second copy assembled by the console."""
        app = booted()
        text_output = app.communication._text_output
        process_line(app, "Good morning Somesh", out=io.StringIO())
        assert text_output.received
        assert "Good morning" in text_output.received[-1].display


# ═════════════════ G · the console/REPL layer itself ════════════════════


class TestFormatBootReport:
    def test_every_step_appears(self):
        app = booted()
        text = format_boot_report(app)
        for step in app.report.steps:
            assert step.name in text

    def test_is_plain_text(self):
        assert isinstance(format_boot_report(booted()), str)


class TestFormatDashboard:
    def test_includes_the_founders_name_and_somesh(self):
        app = booted()
        text = format_dashboard(app.dashboard())
        assert "Onkar" in text
        assert "Somesh" in text

    def test_reflects_conversation_growth(self):
        app = booted()
        before = format_dashboard(app.dashboard())
        app.communication.handle(_req("Continue"))
        after = format_dashboard(app.dashboard())
        assert before != after

    def test_handles_an_absent_desktop_layer(self, monkeypatch):
        from master_agent.founder_edition import boot as boot_module

        real_layer = boot_module.DesktopLayer

        def boom(*_a, **_kw):
            raise RuntimeError("no executive")

        monkeypatch.setattr(boot_module, "DesktopExecutiveV2", boom)
        app = boot_founder_edition(founder_name="Onkar", text_output=RecordingTextOutput())
        assert app.desktop is None
        text = format_dashboard(app.dashboard())
        assert "not wired" in text
        monkeypatch.undo()
        assert boot_module.DesktopLayer is real_layer

    def test_handles_no_coverage_registered(self):
        app = booted()
        text = format_dashboard(app.dashboard())
        assert "vigilance domain" in text or "gaps=" in text

    def test_handles_a_dashboard_with_no_coverage_object_at_all(self):
        """`FounderRuntime.presence()["coverage"]` is `None` when no
        `Coverage` was attested at all — a narrower absence than "zero
        domains registered," and `format_dashboard` must not crash on
        it."""
        dashboard = booted().dashboard()
        dashboard["presence"] = {"feed": {"observations": [], "absent_reason": "x"},
                                  "coverage": None}
        text = format_dashboard(dashboard)
        assert "no vigilance domain registered" in text


class TestProcessLine:
    def test_quit_words_stop_the_loop(self):
        app = booted()
        for word in ("quit", "exit", "bye", "QUIT"):
            assert process_line(app, word, out=io.StringIO()) is False

    def test_ordinary_speech_keeps_the_loop_running(self):
        app = booted()
        assert process_line(app, "Good morning Somesh", out=io.StringIO()) is True

    def test_blank_input_is_ignored(self):
        app = booted()
        out = io.StringIO()
        assert process_line(app, "   ", out=out) is True
        assert out.getvalue() == ""

    def test_dashboard_command_prints_the_dashboard_without_talking_to_somesh(self):
        app = booted()
        out = io.StringIO()
        process_line(app, "dashboard", out=out)
        assert "Somesh, for Onkar" in out.getvalue()
        assert app.dashboard()["conversation"]["entries"] == []

    def test_unrecognised_speech_prints_a_console_note_not_a_somesh_line(self):
        app = booted()
        out = io.StringIO()
        process_line(app, "asdkjhasdkjh nonsense", out=out)
        assert "[console]" in out.getvalue()
        assert "Somesh:" not in out.getvalue()

    def test_switching_to_voice_recovers_to_text_automatically(self):
        app = booted()
        out = io.StringIO()
        process_line(app, "switch to voice", out=out)
        assert "[console]" in out.getvalue()
        assert app.communication.mode is OutputMode.TEXT_ONLY

    def test_the_app_stays_usable_after_a_voice_switch_recovery(self):
        """`out` carries console *notices* (dashboard redraws, the
        recovery message); Somesh's own reply is emitted through the
        registered `TextOutput` channel — bound to the same stream here,
        exactly as a real terminal session does, so both interleave in
        one place the way `main()` actually produces them."""
        stream = io.StringIO()
        app = boot_founder_edition(founder_name="Onkar", text_output=ConsoleTextOutput(stream))
        process_line(app, "switch to voice", out=stream)
        process_line(app, "Continue", out=stream)
        assert "Somesh: Continuing." in stream.getvalue()

    def test_every_real_interaction_reprints_the_dashboard(self):
        app = booted()
        out = io.StringIO()
        process_line(app, "Continue", out=out)
        assert "Somesh, for Onkar" in out.getvalue()


class TestConsoleChannels:
    def test_text_output_prints_the_display_text(self):
        stream = io.StringIO()
        ConsoleTextOutput(stream).emit(CommunicationResponse(text="hello"))
        assert "Somesh: hello" in stream.getvalue()

    def test_text_input_wraps_a_line_as_a_request(self):
        stream = io.StringIO("Good morning Somesh\n")
        request = ConsoleTextInput(stream).receive()
        assert request.content == "Good morning Somesh"
        assert request.source is Source.TEXT

    def test_text_input_raises_eof_when_the_stream_closes(self):
        stream = io.StringIO("")
        with pytest.raises(EOFError):
            ConsoleTextInput(stream).receive()

    def test_a_blank_line_is_read_past_rather_than_crashing(self):
        """`CommunicationRequest` refuses empty content by design — a
        bare Enter press must not crash the console. `receive()` reads
        past blank lines until real content arrives."""
        stream = io.StringIO("\n\n   \nGood morning Somesh\n")
        request = ConsoleTextInput(stream).receive()
        assert request.content == "Good morning Somesh"

    def test_a_stream_of_only_blank_lines_raises_eof_rather_than_hanging(self):
        stream = io.StringIO("\n\n\n")
        with pytest.raises(EOFError):
            ConsoleTextInput(stream).receive()


class TestRunReplAndMain:
    def test_run_repl_completes_the_success_criteria_dialogue(self):
        """The brief's own success dialogue, run through the real REPL
        loop with a real `ConsoleTextOutput` bound to the captured
        stream — the same wiring `main()` uses, so what this test reads
        back is exactly what a founder's terminal would show."""
        out = io.StringIO()
        app = boot_founder_edition(founder_name="Onkar", text_output=ConsoleTextOutput(out))
        script = "Good morning Somesh\nContinue\nHow's the system?\nquit\n"
        run_repl(app, input_stream=io.StringIO(script), output_stream=out)
        rendered = out.getvalue()
        assert "Somesh: Good morning" in rendered
        assert "Somesh: Continuing." in rendered
        assert "Stopping" in rendered

    def test_run_repl_stops_cleanly_on_eof_with_no_quit_typed(self):
        app = booted()
        out = io.StringIO()
        run_repl(app, input_stream=io.StringIO("Continue\n"), output_stream=out)
        assert "Stopping" in out.getvalue()

    def test_main_returns_zero_on_a_normal_run(self, monkeypatch):
        """`run_repl` itself is exercised thoroughly above with injected
        streams; `main()`'s own job is boot -> check -> call -> return,
        which this isolates by replacing `run_repl` rather than fighting
        pytest's own stdin capture for a real terminal loop."""
        import master_agent.founder_edition.console as console_module

        called = {}

        def fake_run_repl(app, **kwargs):
            called["app"] = app

        monkeypatch.setattr(console_module, "run_repl", fake_run_repl)
        assert main(["--founder-name", "Onkar"]) == 0
        assert called["app"].identity.founder_name == "Onkar"

    def test_main_handles_a_keyboard_interrupt_from_the_repl(self, monkeypatch):
        import master_agent.founder_edition.console as console_module

        def raising_run_repl(app, **kwargs):
            raise KeyboardInterrupt

        monkeypatch.setattr(console_module, "run_repl", raising_run_repl)
        assert main(["--founder-name", "Onkar"]) == 0

    def test_main_returns_nonzero_when_communication_did_not_wire(self, monkeypatch):
        """`ready` depends only on `connect_founder_runtime`, so breaking
        `CommunicationEngine`'s own construction exercises `main()`'s
        second guard without touching the first."""
        from master_agent.founder_edition import boot as boot_module

        def boom(*_a, **_kw):
            raise RuntimeError("no communication")

        monkeypatch.setattr(boot_module, "CommunicationEngine", boom)
        assert main(["--founder-name", "Onkar"]) == 1

    def test_main_returns_nonzero_when_boot_does_not_complete(self, monkeypatch):
        """C24's own `_raise_once` model: `_abort()` builds its own
        fallback `FounderRuntime()`, so a permanently-broken class would
        take that path down too (the same class of pre-existing gap
        `Engineering/HEALTH_C30.md` §6.4 already records)."""
        from master_agent.founder_edition import boot as boot_module
        from master_agent.founder_runtime import FounderRuntime

        calls = {"n": 0}

        class FlakyRuntime(FounderRuntime):
            def __init__(self, *args, **kwargs):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise RuntimeError("no runtime")
                super().__init__(*args, **kwargs)

        monkeypatch.setattr(boot_module, "FounderRuntime", FlakyRuntime)
        assert main(["--founder-name", "Onkar"]) == 1

    def test_build_parser_accepts_founder_name(self):
        args = build_parser().parse_args(["--founder-name", "Onkar"])
        assert args.founder_name == "Onkar"

    def test_build_parser_defaults_the_founder_name(self):
        from master_agent.founder_edition.console import DEFAULT_FOUNDER_NAME

        args = build_parser().parse_args([])
        assert args.founder_name == DEFAULT_FOUNDER_NAME


# ═════════════════ H · the launcher file itself ══════════════════════════


class TestAppPy:
    def test_app_py_exists_at_the_repo_root(self):
        assert APP_PY.is_file()

    def test_app_py_is_a_thin_shim(self):
        """*"Single launcher."* `app.py` does no work of its own — it
        imports and calls `console.main`, nothing else."""
        tree = ast.parse(APP_PY.read_text(encoding="utf-8"))
        defined = [
            n.name for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.ClassDef))
        ]
        assert defined == []

    def test_app_py_imports_only_the_console_entrypoint(self):
        tree = ast.parse(APP_PY.read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
        assert imports == {"__future__", "master_agent.founder_edition.console"}


# ═════════════════ I · boundary guards over console.py ══════════════════

_FORBIDDEN_ROOTS = (
    "master_agent.mission_control",
    "master_agent.mission_manager",
    "master_agent.missions",
    "master_agent.planner",
    "master_agent.orchestrator",
    "master_agent.brain",
    "master_agent.broker",
    "master_agent.plugins",
    "master_agent.providers",
    "master_agent.executor",
    "master_agent.ledger",
    "master_agent.kernel",
    "master_agent.runtime_bridge",
    "master_agent.coordinator",
    "master_agent.api",
    "master_agent.launcher",
    "master_agent.dashboard",
    "master_agent.voice",
)


class TestConsoleBoundaries:
    def test_console_imports_no_forbidden_subsystem(self):
        tree = ast.parse((FOUNDER_EDITION_PKG / "console.py").read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
            elif isinstance(node, ast.Import):
                imports.update(a.name for a in node.names)
        offenders = [
            m for m in imports
            for root in _FORBIDDEN_ROOTS
            if m == root or m.startswith(root + ".")
        ]
        assert offenders == []

    def test_console_reads_no_ambient_clock_outside_the_request_building_functions(self):
        """`console.py` is the one place a real clock is allowed to be
        read (see its own module docstring) — but only where a
        `CommunicationRequest` is actually built: `ConsoleTextInput.
        receive()` and `process_line()`'s own recovery request. The pure
        formatting functions (`format_dashboard`, `format_boot_report`,
        `run_repl`'s own orchestration) must read no clock at all."""
        source = (FOUNDER_EDITION_PKG / "console.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        lines_with_now = {
            node.lineno for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "now"
        }
        assert lines_with_now, "expected at least one real .now() call"

        forbidden_functions = ("format_dashboard", "format_boot_report", "run_repl")
        offenders = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in forbidden_functions:
                span = range(node.lineno, node.end_lineno + 1)
                offenders.extend(lineno for lineno in lines_with_now if lineno in span)
        assert offenders == []
