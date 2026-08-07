"""Sprint 1, Component 31 — Founder Conversation Engine.

| Requirement | Source |
|---|---|
| "Good morning Somesh" -> a natural greeting | C31 brief |
| "What are you doing?" -> a natural activity summary, never inventing calm | C31 brief |
| "How's the system?" -> four facts, no component names | C31 brief |
| "Continue" -> resumes without re-introduction | C31 brief |
| "Build a trading bot" -> never plans, delegates honestly | C31 brief |
| No desktop execution, no missions, no planning, no Runtime mutation | C31 brief |
| assistant role stays unreachable | C23, carried through C29/C31 |
| Never say "as an AI" / "language model" / "I cannot" | C31 brief |
| Never expose Runtime / Kernel / Operator / component names | C31 brief |

Boundary guards read imports by AST — the same discipline C23/C24/C29/C30
already use, because a promise in a docstring is not one a reader can
trust until a test can fail it.
"""
from __future__ import annotations

import ast
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from master_agent.conversation_engine import (
    FORBIDDEN_INTERNAL_TERMS,
    SOMESH,
    ContextAssembler,
    ConversationContext,
    ConversationEngine,
    ConversationTurn,
    DesktopStatus,
    ExposedInternals,
    Intent,
    IntentClassifier,
    ResponseComposer,
    ResponsePipeline,
)
from master_agent.founder_identity import FounderIdentity, FounderSession
from master_agent.founder_identity.greeting import FORBIDDEN_PHRASES
from master_agent.founder_runtime import FounderRuntime
from master_agent.memory.conversation import ConversationMemory
from master_agent.vigilance import Coverage, DomainStatus, Gap, GapKind

PACKAGE = (
    Path(__file__).resolve().parent.parent
    / "src" / "master_agent" / "conversation_engine"
)

T0 = datetime(2026, 8, 7, 8, 30, tzinfo=UTC)


# ───────────────────────────── fixtures ─────────────────────────────────


def identity(**kwargs) -> FounderIdentity:
    defaults = {"founder_name": "Onkar"}
    defaults.update(kwargs)
    return FounderIdentity(**defaults)


def rig(*, coverage: Coverage | None = None, environment_ready: bool = False):
    """A runtime/identity/session/conversation quartet, matching
    `founder_edition`'s own construction shape."""
    conversation = ConversationMemory()
    intelligence = None
    if environment_ready:
        from master_agent.desktop.inventory import MachineInventory
        from master_agent.environment_intelligence import derive_intelligence

        intelligence = derive_intelligence(MachineInventory(platform="win32"))
    runtime = FounderRuntime(
        intelligence=intelligence, coverage=coverage, conversation=conversation
    )
    ident = identity()
    session = FounderSession(conversation)
    return runtime, ident, session, conversation


def engine(**kwargs) -> ConversationEngine:
    runtime, ident, session, conversation = rig(**kwargs)
    return ConversationEngine(
        runtime=runtime, identity=ident, session=session, conversation=conversation
    )


def empty_coverage() -> Coverage:
    return Coverage(complete=False, domains=(), gaps=(
        Gap(domain="", kind=GapKind.NEVER_CHECKED, last_checked=None,
            detail="no domain is being watched, so coverage proves nothing"),
    ), attested_at=T0)


def complete_coverage() -> Coverage:
    status = DomainStatus(name="inbox", healthy=True, last_checked=T0)
    return Coverage(complete=True, domains=(status,), gaps=(), attested_at=T0)


def gapped_coverage() -> Coverage:
    status = DomainStatus(name="inbox", healthy=False, last_checked=T0)
    gap = Gap(domain="calendar", kind=GapKind.NEVER_CHECKED, last_checked=None,
              detail="calendar has never been checked")
    return Coverage(complete=False, domains=(status,), gaps=(gap,), attested_at=T0)


def context(**overrides) -> ConversationContext:
    defaults = {
        "moment": T0,
        "founder_name": "Onkar",
        "assistant_name": "Somesh",
        "environment_ready": True,
        "conversation_ready": True,
        "presence_registered": True,
        "presence_complete": True,
        "attention_needed": (),
        "desktop_ready": True,
        "session_active": False,
        "last_founder_utterance": None,
    }
    defaults.update(overrides)
    return ConversationContext(**defaults)


# ══════════════════════════ IntentClassifier ═════════════════════════════


class TestIntentClassifier:
    c = IntentClassifier()

    @pytest.mark.parametrize(
        "text", ["Good morning Somesh", "Good evening", "hello", "hi"]
    )
    def test_greeting(self, text):
        assert self.c.classify(text) is Intent.GREETING

    @pytest.mark.parametrize("text", ["Continue", "continue.", "keep going", "resume"])
    def test_continuation(self, text):
        assert self.c.classify(text) is Intent.CONTINUATION

    @pytest.mark.parametrize(
        "text",
        ["How's the system?", "how is the system", "is everything ok",
         "is everything okay", "system status", "status check",
         "is everything working"],
    )
    def test_status_query(self, text):
        assert self.c.classify(text) is Intent.STATUS_QUERY

    @pytest.mark.parametrize(
        "text",
        ["What are you doing?", "what're you doing", "what's happening",
         "what is happening", "what's going on", "what is going on"],
    )
    def test_activity_query(self, text):
        assert self.c.classify(text) is Intent.ACTIVITY_QUERY

    @pytest.mark.parametrize(
        "text",
        ["What should I work on?", "what should i do", "what do i need to do",
         "what needs my attention", "what needs attention", "priorities",
         "what's my priority", "what is my priority"],
    )
    def test_priority_query(self, text):
        assert self.c.classify(text) is Intent.PRIORITY_QUERY

    @pytest.mark.parametrize(
        "text",
        ["Build a trading bot", "Create a dashboard", "Make me a report",
         "Set up a pipeline", "Automate my inbox", "Launch a new project",
         "Start building the system"],
    )
    def test_build_request(self, text):
        assert self.c.classify(text) is Intent.BUILD_REQUEST

    @pytest.mark.parametrize(
        "text", ["", "   ", "rebuild trust with the team", "asdkjalksdj", "42"]
    )
    def test_unknown(self, text):
        assert self.c.classify(text) is Intent.UNKNOWN

    def test_refuses_a_non_string(self):
        with pytest.raises(TypeError):
            self.c.classify(123)  # type: ignore[arg-type]

    def test_is_stateless_across_calls(self):
        self.c.classify("Good morning Somesh")
        assert self.c.classify("Continue") is Intent.CONTINUATION


# ══════════════════════════ ContextAssembler ═════════════════════════════


class TestContextAssembler:
    a = ContextAssembler()

    def test_empty_runtime_reads_as_all_absent(self):
        runtime = FounderRuntime()
        ctx = self.a.assemble(
            runtime=runtime, founder_name="Onkar", assistant_name="Somesh",
            session_active=False, last_founder_utterance=None, desktop=None,
            moment=T0,
        )
        assert ctx.environment_ready is False
        assert ctx.conversation_ready is False
        assert ctx.presence_registered is False
        assert ctx.presence_complete is False
        assert ctx.attention_needed == ()
        assert ctx.desktop_ready is None

    def test_environment_ready_reflects_the_runtime(self):
        runtime, _, _, _ = rig(environment_ready=True)
        ctx = self.a.assemble(
            runtime=runtime, founder_name="Onkar", assistant_name="Somesh",
            session_active=False, last_founder_utterance=None, desktop=None,
            moment=T0,
        )
        assert ctx.environment_ready is True

    def test_conversation_ready_reflects_the_runtime(self):
        runtime, _, _, _ = rig()
        ctx = self.a.assemble(
            runtime=runtime, founder_name="Onkar", assistant_name="Somesh",
            session_active=False, last_founder_utterance=None, desktop=None,
            moment=T0,
        )
        assert ctx.conversation_ready is True

    def test_empty_coverage_is_unregistered_not_complete(self):
        runtime, _, _, _ = rig(coverage=empty_coverage())
        ctx = self.a.assemble(
            runtime=runtime, founder_name="Onkar", assistant_name="Somesh",
            session_active=False, last_founder_utterance=None, desktop=None,
            moment=T0,
        )
        assert ctx.presence_registered is False
        assert ctx.presence_complete is False
        assert ctx.attention_needed == ()

    def test_complete_coverage_carries_no_attention_items(self):
        runtime, _, _, _ = rig(coverage=complete_coverage())
        ctx = self.a.assemble(
            runtime=runtime, founder_name="Onkar", assistant_name="Somesh",
            session_active=False, last_founder_utterance=None, desktop=None,
            moment=T0,
        )
        assert ctx.presence_registered is True
        assert ctx.presence_complete is True
        assert ctx.attention_needed == ()

    def test_gapped_coverage_names_the_real_domain(self):
        runtime, _, _, _ = rig(coverage=gapped_coverage())
        ctx = self.a.assemble(
            runtime=runtime, founder_name="Onkar", assistant_name="Somesh",
            session_active=False, last_founder_utterance=None, desktop=None,
            moment=T0,
        )
        assert ctx.presence_registered is True
        assert ctx.presence_complete is False
        assert ctx.attention_needed == ("calendar",)

    def test_desktop_status_is_carried_through(self):
        runtime, _, _, _ = rig()
        ctx = self.a.assemble(
            runtime=runtime, founder_name="Onkar", assistant_name="Somesh",
            session_active=False, last_founder_utterance=None,
            desktop=DesktopStatus(ready=True), moment=T0,
        )
        assert ctx.desktop_ready is True

    def test_desktop_absent_is_none_not_false(self):
        runtime, _, _, _ = rig()
        ctx = self.a.assemble(
            runtime=runtime, founder_name="Onkar", assistant_name="Somesh",
            session_active=False, last_founder_utterance=None, desktop=None,
            moment=T0,
        )
        assert ctx.desktop_ready is None

    def test_session_fields_pass_through_verbatim(self):
        runtime, _, _, _ = rig()
        ctx = self.a.assemble(
            runtime=runtime, founder_name="Onkar", assistant_name="Somesh",
            session_active=True, last_founder_utterance="hello", desktop=None,
            moment=T0,
        )
        assert ctx.session_active is True
        assert ctx.last_founder_utterance == "hello"

    def test_refuses_a_non_runtime(self):
        with pytest.raises(TypeError):
            self.a.assemble(
                runtime=object(), founder_name="Onkar", assistant_name="Somesh",
                session_active=False, last_founder_utterance=None, desktop=None,
                moment=T0,
            )

    def test_refuses_a_non_desktop_status(self):
        runtime, _, _, _ = rig()
        with pytest.raises(TypeError):
            self.a.assemble(
                runtime=runtime, founder_name="Onkar", assistant_name="Somesh",
                session_active=False, last_founder_utterance=None,
                desktop=object(), moment=T0,
            )

    def test_refuses_a_naive_moment(self):
        runtime, _, _, _ = rig()
        with pytest.raises(ValueError):
            self.a.assemble(
                runtime=runtime, founder_name="Onkar", assistant_name="Somesh",
                session_active=False, last_founder_utterance=None, desktop=None,
                moment=datetime(2026, 8, 7, 8, 30),  # noqa: DTZ001
            )

    def test_as_dict_is_json_ready(self):
        ctx = context()
        assert json.loads(json.dumps(ctx.as_dict())) == ctx.as_dict()


# ══════════════════════════ ResponseComposer ═════════════════════════════


class TestResponseComposerGreetingAndContinuation:
    composer = ResponseComposer()

    def test_greeting_delegates_to_c29(self):
        reply = self.composer.greeting(identity(), context())
        assert reply.startswith("Good morning.")

    def test_continuation_delegates_to_c29(self):
        conversation = ConversationMemory()
        session = FounderSession(conversation)
        session.record("something")
        assert self.composer.continuation(session) == "Continuing."


class TestResponseComposerStatus:
    composer = ResponseComposer()

    def test_the_briefs_own_four_facts_are_all_present(self):
        reply = self.composer.status(context(desktop_ready=True, environment_ready=True))
        assert "desktop" in reply.lower()
        assert "environment" in reply.lower()
        assert "connected" in reply.lower()
        assert "approval" in reply.lower()

    def test_no_component_name_appears(self):
        reply = self.composer.status(context())
        lowered = reply.lower()
        for term in FORBIDDEN_INTERNAL_TERMS:
            assert term not in lowered

    def test_desktop_not_ready_is_reported_honestly(self):
        reply = self.composer.status(context(desktop_ready=False))
        assert "needs a look" in reply

    def test_desktop_unknown_is_reported_honestly(self):
        reply = self.composer.status(context(desktop_ready=None))
        assert "don't have a desktop reading yet" in reply

    def test_environment_not_ready_is_reported_honestly(self):
        reply = self.composer.status(context(environment_ready=False))
        assert "haven't looked at the environment" in reply


class TestResponseComposerActivity:
    composer = ResponseComposer()

    def test_unregistered_presence_never_claims_full_monitoring(self):
        """R80: nothing watched must never read as calm."""
        reply = self.composer.activity(
            context(presence_registered=False, presence_complete=False)
        )
        assert "monitoring everything" not in reply
        assert "nothing is being watched yet" in reply.lower()

    def test_complete_presence_says_nothing_needs_attention(self):
        reply = self.composer.activity(
            context(presence_registered=True, presence_complete=True)
        )
        assert reply == (
            "I'm monitoring everything. Nothing currently needs your attention."
        )

    def test_incomplete_presence_names_the_real_count(self):
        reply = self.composer.activity(
            context(presence_registered=True, presence_complete=False,
                    attention_needed=("calendar",))
        )
        assert "1 thing could use your attention." in reply

    def test_pluralises_multiple_items_correctly(self):
        reply = self.composer.activity(
            context(presence_registered=True, presence_complete=False,
                    attention_needed=("calendar", "inbox"))
        )
        assert "2 things could use your attention." in reply


class TestResponseComposerPriority:
    composer = ResponseComposer()

    def test_names_the_first_real_gap_and_no_other(self):
        reply = self.composer.priority(
            context(attention_needed=("calendar", "inbox"))
        )
        assert reply == "The thing that needs you most right now is calendar."
        assert "inbox" not in reply

    def test_never_invents_a_priority_when_nothing_is_tracked(self):
        reply = self.composer.priority(
            context(presence_registered=False, attention_needed=())
        )
        assert "don't have a priority" in reply

    def test_nothing_needed_is_reported_as_a_good_moment(self):
        reply = self.composer.priority(
            context(presence_registered=True, presence_complete=True, attention_needed=())
        )
        assert "good moment to start something new" in reply


class TestResponseComposerBuildRequest:
    composer = ResponseComposer()

    def test_never_plans_and_never_claims_to_forward(self):
        reply = self.composer.build_request(context())
        assert "don't build things myself" in reply
        for word in ("mission", "plan it", "forwarded", "started"):
            assert word not in reply.lower()

    def test_is_identical_regardless_of_what_was_asked_for(self):
        """No branch reads free text — the same honest sentence every
        time, since nothing about *what* to build is ever known."""
        assert self.composer.build_request(context()) == self.composer.build_request(
            context(founder_name="Someone Else")
        )


class TestExposedInternalsIsStructural:
    def test_a_leaking_translation_is_caught_not_merely_avoided(self, monkeypatch):
        composer = ResponseComposer()
        monkeypatch.setattr(
            composer, "_desktop_line", lambda _ready: "The Runtime is healthy."
        )
        with pytest.raises(ExposedInternals):
            composer.status(context())

    def test_forbidden_terms_list_is_non_empty_and_lower_case(self):
        assert FORBIDDEN_INTERNAL_TERMS
        assert all(t == t.lower() for t in FORBIDDEN_INTERNAL_TERMS)


# ══════════════════════════ ResponsePipeline ═════════════════════════════


class TestResponsePipeline:
    def test_takes_only_the_four_required_collaborators(self):
        runtime, ident, session, conversation = rig()
        pipeline = ResponsePipeline(
            runtime=runtime, identity=ident, session=session, conversation=conversation
        )
        assert isinstance(pipeline, ResponsePipeline)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"runtime": object()},
            {"identity": object()},
            {"session": object()},
            {"conversation": object()},
        ],
    )
    def test_refuses_a_substitute_for_any_collaborator(self, kwargs):
        runtime, ident, session, conversation = rig()
        base = {
            "runtime": runtime, "identity": ident, "session": session,
            "conversation": conversation,
        }
        base.update(kwargs)
        with pytest.raises(TypeError):
            ResponsePipeline(**base)

    def test_handle_refuses_a_non_string(self):
        runtime, ident, session, conversation = rig()
        pipeline = ResponsePipeline(
            runtime=runtime, identity=ident, session=session, conversation=conversation
        )
        with pytest.raises(TypeError):
            pipeline.handle(123, moment=T0)  # type: ignore[arg-type]

    def test_unknown_intent_records_the_turn_but_composes_no_reply(self):
        runtime, ident, session, conversation = rig()
        pipeline = ResponsePipeline(
            runtime=runtime, identity=ident, session=session, conversation=conversation
        )
        turn = pipeline.handle("asdkjhasdkjh nonsense", moment=T0)
        assert turn.intent is Intent.UNKNOWN
        assert turn.reply is None
        assert len(conversation.turns()) == 1

    def test_a_recognised_intent_records_two_turns(self):
        runtime, ident, session, conversation = rig()
        pipeline = ResponsePipeline(
            runtime=runtime, identity=ident, session=session, conversation=conversation
        )
        pipeline.handle("Good morning Somesh", moment=T0)
        assert len(conversation.turns()) == 2

    def test_somesh_turns_use_the_reserved_speaker(self):
        runtime, ident, session, conversation = rig()
        pipeline = ResponsePipeline(
            runtime=runtime, identity=ident, session=session, conversation=conversation
        )
        pipeline.handle("Good morning Somesh", moment=T0)
        assert conversation.turns()[-1].speaker == SOMESH

    def test_somesh_speaker_projects_to_system_never_assistant(self):
        runtime, ident, session, conversation = rig()
        pipeline = ResponsePipeline(
            runtime=runtime, identity=ident, session=session, conversation=conversation
        )
        pipeline.handle("Good morning Somesh", moment=T0)
        roles = {e["role"] for e in runtime.conversation()["entries"]}
        assert roles == {"user", "system"}
        assert "assistant" not in roles

    def test_every_recognised_intent_returns_a_conversation_turn(self):
        runtime, ident, session, conversation = rig()
        pipeline = ResponsePipeline(
            runtime=runtime, identity=ident, session=session, conversation=conversation
        )
        for text in (
            "Good morning Somesh", "Continue", "How's the system?",
            "What are you doing?", "What should I work on?", "Build a trading bot",
        ):
            turn = pipeline.handle(text, moment=T0)
            assert isinstance(turn, ConversationTurn)
            assert turn.reply is not None

    def test_context_reflects_the_moment_passed_in(self):
        runtime, ident, session, conversation = rig()
        pipeline = ResponsePipeline(
            runtime=runtime, identity=ident, session=session, conversation=conversation
        )
        turn = pipeline.handle("Continue", moment=T0)
        assert turn.context.moment == T0

    def test_desktop_status_reaches_the_context(self):
        runtime, ident, session, conversation = rig()
        pipeline = ResponsePipeline(
            runtime=runtime, identity=ident, session=session, conversation=conversation
        )
        turn = pipeline.handle(
            "How's the system?", moment=T0, desktop=DesktopStatus(ready=False)
        )
        assert turn.context.desktop_ready is False
        assert "needs a look" in turn.reply

    def test_default_collaborators_are_used_when_none_are_given(self):
        runtime, ident, session, conversation = rig()
        pipeline = ResponsePipeline(
            runtime=runtime, identity=ident, session=session, conversation=conversation
        )
        assert isinstance(pipeline._classifier, IntentClassifier)
        assert isinstance(pipeline._assembler, ContextAssembler)
        assert isinstance(pipeline._composer, ResponseComposer)


# ══════════════════════════ ConversationEngine ═══════════════════════════


class TestConversationEngine:
    def test_the_briefs_own_dialogue_end_to_end(self):
        eng = engine(coverage=complete_coverage(), environment_ready=True)
        assert eng.reply("Good morning Somesh", moment=T0).reply == (
            "Good morning. I'm awake. Everything is ready."
        )

    def test_activity_query_never_claims_calm_over_nothing_watched(self):
        eng = engine(coverage=empty_coverage())
        turn = eng.reply("What are you doing?", moment=T0)
        assert "monitoring everything" not in turn.reply

    def test_status_query_names_no_internal_component(self):
        eng = engine()
        turn = eng.reply("How's the system?", moment=T0, desktop=DesktopStatus(ready=True))
        lowered = turn.reply.lower()
        for term in FORBIDDEN_INTERNAL_TERMS:
            assert term not in lowered

    def test_continue_resumes_without_re_introduction(self):
        eng = engine()
        eng.reply("let's talk about the roadmap", moment=T0)
        turn = eng.reply("Continue", moment=T0)
        assert turn.reply == "Continuing."
        assert "roadmap" not in turn.reply

    def test_never_says_forbidden_ai_wording(self):
        eng = engine()
        for text in (
            "Good morning Somesh", "How's the system?", "What are you doing?",
            "What should I work on?", "Build a trading bot",
        ):
            turn = eng.reply(text, moment=T0, desktop=DesktopStatus(ready=True))
            lowered = (turn.reply or "").lower()
            for phrase in FORBIDDEN_PHRASES:
                assert phrase not in lowered

    def test_conversation_is_remembered_without_reintroduction(self):
        eng = engine()
        eng.reply("Good morning Somesh", moment=T0)
        second = eng.reply("Good afternoon Somesh", moment=T0.replace(hour=14))
        # no re-introduction: the second greeting is still just a greeting,
        # never a restated identity/edition disclosure
        for term in ("Kalpavriksha", "Founder Edition", "C29", "C31"):
            assert term not in (second.reply or "")

    def test_reply_signature_is_exactly_text_moment_desktop(self):
        import inspect

        sig = inspect.signature(ConversationEngine.reply)
        assert list(sig.parameters) == ["self", "text", "moment", "desktop"]

    def test_reply_returns_a_conversation_turn(self):
        eng = engine()
        assert isinstance(eng.reply("Continue", moment=T0), ConversationTurn)


# ══════════════════════════ Boundary guards (AST) ═════════════════════════

#: Everything this engine is forbidden from reaching, in the brief's own
#: words: never executes desktop actions, never launches applications,
#: never creates missions, never plans work, never mutates Founder Runtime.
_FORBIDDEN_ROOTS = (
    "master_agent.desktop",
    "master_agent.desktop_operator",
    "master_agent.founder_edition",
    "master_agent.kernel",
    "master_agent.runtime_bridge",
    "master_agent.coordinator",
    "master_agent.planner",
    "master_agent.mission_manager",
    "master_agent.mission_control",
    "master_agent.missions",
    "master_agent.orchestrator",
    "master_agent.brain",
    "master_agent.broker",
    "master_agent.plugins",
    "master_agent.providers",
    "master_agent.executor",
    "master_agent.ledger",
    "master_agent.foundation",
    "master_agent.api",
    "master_agent.dashboard",
    "master_agent.launcher",
    "master_agent.permissions",
)


def _modules() -> list[tuple[Path, ast.Module]]:
    return [
        (path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
        for path in sorted(PACKAGE.glob("*.py"))
    ]


def _imported_modules() -> set[str]:
    modules: set[str] = set()
    for _, tree in _modules():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
    return modules


class TestBoundaries:
    def test_the_guard_actually_found_the_package(self):
        assert len(list(PACKAGE.glob("*.py"))) >= 5

    def test_no_forbidden_module_is_imported_anywhere_in_the_package(self):
        offenders = []
        imports = _imported_modules()
        for module in imports:
            for root in _FORBIDDEN_ROOTS:
                if module == root or module.startswith(root + "."):
                    offenders.append(module)
        assert offenders == []

    def test_the_only_master_agent_door_is_founder_identity_runtime_or_memory(self):
        allowed_roots = (
            "master_agent.conversation_engine",
            "master_agent.founder_identity",
            "master_agent.founder_runtime",
            "master_agent.memory",
        )
        offenders = []
        for module in _imported_modules():
            if not module.startswith("master_agent"):
                continue
            if not any(
                module == root or module.startswith(root + ".")
                for root in allowed_roots
            ):
                offenders.append(module)
        assert offenders == []

    def test_no_ambient_clock_is_read(self):
        offenders = []
        for path, _ in _modules():
            text = path.read_text(encoding="utf-8")
            if "datetime.now(" in text or "date.today(" in text:
                offenders.append(path.name)
        assert offenders == []

    def test_runtime_handle_is_never_called_here(self):
        """`FounderRuntime.handle()` is C23's one mutable-shaped door — see
        `engine.py`'s docstring for why it stays unreachable even though
        this package holds a live `FounderRuntime`.

        `ResponsePipeline.handle()` is this package's own method of the
        same name and must not trip the guard — so the check is narrowed
        to attribute chains whose *receiver* names a runtime
        (`self._runtime.handle(...)`, `runtime.handle(...)`), not every
        `.handle` access in the package.
        """
        offenders = []
        for path, tree in _modules():
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Attribute) and node.attr == "handle"):
                    continue
                receiver = node.value
                receiver_name = (
                    receiver.attr if isinstance(receiver, ast.Attribute)
                    else receiver.id if isinstance(receiver, ast.Name)
                    else ""
                )
                if "runtime" in receiver_name.lower():
                    offenders.append(path.name)
        assert offenders == []

    def test_the_guards_can_actually_fail(self, tmp_path, monkeypatch):
        """Proven able to fail, the same discipline C28's own audit and
        C30's own suite use: a throwaway forbidden import is added, the
        guard is re-run against a package copy that includes it, and it
        is confirmed to trip — then discarded, never left behind."""
        probe = PACKAGE / "_leak_probe.py"
        probe.write_text(
            "from master_agent.desktop.inventory import discover\n"
            "from master_agent.planner import planner\n",
            encoding="utf-8",
        )
        try:
            imports = _imported_modules()
            tripped = any(
                m == root or m.startswith(root + ".")
                for m in imports
                for root in _FORBIDDEN_ROOTS
            )
            assert tripped is True
        finally:
            probe.unlink()
        # and the guard is clean again afterward
        assert not any(
            m == root or m.startswith(root + ".")
            for m in _imported_modules()
            for root in _FORBIDDEN_ROOTS
        )


class TestDoesNotDuplicateC29OrC23:
    def test_no_greeting_or_continuation_prose_is_authored_here(self):
        """Every greeting/continuation sentence is C29's; this package
        only dispatches to it."""
        prose = "\n".join(
            p.read_text(encoding="utf-8")
            for p in PACKAGE.glob("*.py")
            if p.name not in ("composer.py",)
        )
        assert "I'm awake" not in prose
        assert "Continuing." not in prose

    def test_no_component_type_from_c23_or_c29_is_redeclared(self):
        defined: set[str] = set()
        for _, tree in _modules():
            for node in ast.walk(tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                    defined.add(node.name)
        for owned_elsewhere in ("FounderRuntime", "FounderIdentity", "FounderSession"):
            assert owned_elsewhere not in defined
