"""Sprint 1, Component 29 — Founder Identity Layer.

| Requirement | Source |
|---|---|
| Greeting: "Good morning Somesh" -> a human reply, never AI wording | C29 brief |
| "Continue" resumes without re-introduction | C29 brief |
| No planning, no execution, no AI routing, no strategy | C29 brief |
| No desktop calls; Somesh talks only to Founder Runtime | C29 brief |
| No Runtime mutation, no Kernel access | C29 brief |
| Founder continuity across turns | C29 brief |

Boundary guards read imports by AST, the same discipline C23/C24's own
suites use — a promise in a docstring is not a promise a reader can trust
until a test can fail it.
"""
from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest

from master_agent.founder_identity import (
    FounderIdentity,
    DEFAULT_TRAITS,
    ForbiddenWording,
    FounderContext,
    FounderIdentity,
    FounderSession,
    continuity_reply,
    founder_context,
    greet,
    is_continuation_request,
    is_greeting,
)
from master_agent.founder_identity import greeting as greeting_module
from master_agent.founder_identity.greeting import FORBIDDEN_PHRASES
from master_agent.founder_runtime import FounderRuntime
from master_agent.memory.conversation import ConversationMemory

PACKAGE = (
    Path(__file__).resolve().parent.parent
    / "src" / "master_agent" / "founder_identity"
)

T_MORNING = datetime(2026, 8, 7, 8, 30, tzinfo=UTC)
T_EVENING = datetime(2026, 8, 7, 20, 0, tzinfo=UTC)


def identity(**kwargs) -> FounderIdentity:
    defaults = {"founder_name": "Onkar"}
    defaults.update(kwargs)
    return FounderIdentity(**defaults)


def ready_context(moment: datetime = T_MORNING) -> FounderContext:
    return FounderContext(
        moment=moment,
        environment_ready=True,
        conversation_ready=True,
        presence_ready=False,
    )


# ══════════════════════════ FounderIdentity ══════════════════════════════


class TestFounderIdentity:
    def test_defaults_match_the_brief(self):
        ident = identity()
        assert ident.assistant_name == "Somesh"
        assert ident.greeting_style == "calm"
        assert ident.personality_traits == DEFAULT_TRAITS

    def test_empty_founder_name_is_refused(self):
        with pytest.raises(ValueError):
            FounderIdentity(founder_name="  ")

    def test_invalid_greeting_style_is_refused(self):
        with pytest.raises(ValueError):
            identity(greeting_style="excited")

    def test_empty_personality_traits_is_refused(self):
        with pytest.raises(ValueError):
            identity(personality_traits=())

    @pytest.mark.parametrize("word", ["Runtime", "Kernel", "Engine", "Bridge"])
    def test_internal_architecture_words_are_refused(self, word):
        with pytest.raises(ValueError):
            identity(assistant_name=f"Founder {word}")

    def test_frozen(self):
        ident = identity()
        with pytest.raises(AttributeError):
            ident.founder_name = "Someone Else"

    def test_as_dict_round_trips_fields(self):
        ident = identity()
        d = ident.as_dict()
        assert d["assistant_name"] == "Somesh"
        assert d["personality_traits"] == list(DEFAULT_TRAITS)


# ══════════════════════════ FounderSession ═══════════════════════════════


class TestFounderSession:
    def test_inactive_with_no_conversation_wired(self):
        session = FounderSession()
        assert session.active is False
        assert session.last_founder_utterance() is None

    def test_becomes_active_after_a_recorded_turn(self):
        conversation = ConversationMemory()
        session = FounderSession(conversation)
        assert session.active is False
        session.record("Good morning Somesh")
        assert session.active is True
        assert session.last_founder_utterance() == "Good morning Somesh"

    def test_recording_without_wired_memory_raises(self):
        session = FounderSession()
        with pytest.raises(RuntimeError):
            session.record("hello")

    def test_wrong_conversation_type_is_refused(self):
        with pytest.raises(TypeError):
            FounderSession(conversation=object())

    def test_holds_no_second_copy_of_history(self):
        """FounderSession stores nothing beyond the ConversationMemory
        reference itself — no list, no dict of turns."""
        conversation = ConversationMemory()
        session = FounderSession(conversation)
        session.record("one")
        session.record("two")
        assert session.__slots__ == ("_conversation",)


# ══════════════════════════ GreetingEngine ═══════════════════════════════


class TestGreetingEngine:
    def test_it_greets_the_founder_by_name_as_the_chief_of_staff(self):
        """A founder decision supersedes C29's own example here.

        The brief's greeting was "Good morning. I'm awake." -- correct in
        cadence and addressed to nobody. `greet()` has always been handed
        a `FounderIdentity` carrying both names and never read either, so
        the founder was greeted by no one, by name, in their own product.

        Two different people are named, and they are not interchangeable:
        Onkar is the founder being addressed, Somesh is the chief of staff
        speaking. "Good morning, Somesh" would greet the assistant as
        though it were the founder.
        """
        assert is_greeting("Good morning Somesh") is True
        reply = greet(identity(), ready_context(T_MORNING))
        assert reply.startswith("Good morning, ")
        assert identity().founder_name in reply
        assert f"{identity().assistant_name} here." in reply
        assert "Everything is ready." in reply

    def test_a_generic_founder_name_is_not_spoken_aloud(self):
        """"Good morning, Founder." is worse than no name. When identity is
        unconfigured the greeting simply omits the address."""
        anonymous = FounderIdentity(founder_name="Founder")
        reply = greet(anonymous, ready_context(T_MORNING))
        assert reply.startswith("Good morning.")
        assert "Founder." not in reply.replace("Good morning.", "", 1)
        assert "Somesh here." in reply

    def test_afternoon_and_evening_vary_the_opening(self):
        afternoon = greet(identity(), ready_context(T_EVENING.replace(hour=14)))
        assert afternoon.startswith("Good afternoon, ")
        evening = greet(identity(), ready_context(T_EVENING))
        assert evening.startswith("Good evening, ")

    def test_partial_readiness_is_reported_between_the_two_extremes(self):
        half_ready = FounderContext(
            moment=T_MORNING,
            environment_ready=True,
            conversation_ready=False,
            presence_ready=False,
        )
        reply = greet(identity(), half_ready)
        assert "still coming online" in reply

    def test_greet_requires_a_founder_identity_and_context(self):
        with pytest.raises(TypeError):
            greet(object(), ready_context())
        with pytest.raises(TypeError):
            greet(identity(), object())

    def test_not_ready_context_says_so_without_naming_a_subsystem(self):
        not_ready = FounderContext(
            moment=T_MORNING,
            environment_ready=False,
            conversation_ready=False,
            presence_ready=False,
        )
        reply = greet(identity(), not_ready)
        for banned in ("Environment Intelligence", "Vigilance", "FounderRuntime"):
            assert banned not in reply

    @pytest.mark.parametrize("phrase", FORBIDDEN_PHRASES)
    def test_forbidden_phrases_never_survive(self, phrase):
        assert phrase not in greet(identity(), ready_context()).lower()

    def test_is_greeting_rejects_unrelated_text(self):
        assert is_greeting("please open my inbox") is False
        assert is_greeting("") is False

    def test_forbidden_wording_is_raised_if_a_template_ever_leaks_one(self, monkeypatch):
        """Proves the check is structural: force a forbidden phrase into
        the composed sentence and confirm it is caught, not merely
        avoided by the current wording."""
        monkeypatch.setattr(
            greeting_module, "_readiness_clause", lambda _ctx: "As an AI, I'm ready."
        )
        with pytest.raises(ForbiddenWording):
            greet(identity(), ready_context())


# ══════════════════════════ ConversationContinuity ═══════════════════════


class TestConversationContinuity:
    @pytest.mark.parametrize(
        "text", ["Continue", "continue.", "Keep going", "carry on", "resume"]
    )
    def test_recognises_the_brief_words(self, text):
        assert is_continuation_request(text) is True

    def test_rejects_unrelated_text(self):
        assert is_continuation_request("what's my schedule today") is False

    def test_reply_requires_a_founder_session(self):
        with pytest.raises(TypeError):
            continuity_reply(object())

    def test_reply_carries_no_re_introduction(self):
        conversation = ConversationMemory()
        session = FounderSession(conversation)
        session.record("let's talk about the Q3 roadmap")
        reply = continuity_reply(session)
        assert reply == "Continuing."
        # No re-explanation: the prior text is not echoed back.
        assert "Q3" not in reply

    def test_nothing_to_continue_is_stated_honestly(self):
        session = FounderSession()
        reply = continuity_reply(session)
        assert "nothing to continue" in reply.lower()


# ══════════════════════════ FounderContext ═══════════════════════════════


class TestFounderContext:
    def test_reads_only_founder_runtime_sections(self):
        runtime = FounderRuntime(conversation=ConversationMemory())
        ctx = founder_context(runtime, T_MORNING)
        assert ctx.conversation_ready is True
        assert ctx.environment_ready is False
        assert ctx.presence_ready is False

    def test_naive_moment_is_refused(self):
        runtime = FounderRuntime()
        with pytest.raises(ValueError):
            founder_context(runtime, datetime(2026, 8, 7, 8, 0))  # noqa: DTZ001

    def test_takes_only_a_founder_runtime(self):
        with pytest.raises(TypeError):
            founder_context(object(), T_MORNING)

    def test_as_dict_reports_an_iso_moment(self):
        ctx = ready_context(T_MORNING)
        d = ctx.as_dict()
        assert d["moment"] == T_MORNING.isoformat()
        assert d["environment_ready"] is True


# ══════════════════════════ Boundary guards (AST) ═════════════════════════

#: Everything Somesh is forbidden from reaching, in the brief's own words:
#: never plans, never executes desktop, never routes AI, never decides
#: strategy, never touches the Kernel.
_FORBIDDEN_ROOTS = (
    "master_agent.desktop",
    "master_agent.desktop_operator",
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
)


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


class TestBoundaries:
    def test_no_forbidden_module_is_imported_anywhere_in_the_package(self):
        offenders = []
        for path in PACKAGE.glob("*.py"):
            for module in _imported_modules(path):
                for root in _FORBIDDEN_ROOTS:
                    if module == root or module.startswith(root + "."):
                        offenders.append((path.name, module))
        assert offenders == []

    def test_the_only_master_agent_door_is_founder_runtime_or_memory(self):
        """Every `master_agent.*` import in this package resolves to one
        of: founder_identity itself, founder_runtime (the one door), or
        memory.conversation (the session's own substrate) — nothing else."""
        allowed_roots = (
            "master_agent.founder_identity",
            "master_agent.founder_runtime",
            "master_agent.memory",
        )
        offenders = []
        for path in PACKAGE.glob("*.py"):
            for module in _imported_modules(path):
                if not module.startswith("master_agent"):
                    continue
                if not any(
                    module == root or module.startswith(root + ".")
                    for root in allowed_roots
                ):
                    offenders.append((path.name, module))
        assert offenders == []

    def test_no_ambient_clock_is_read(self):
        """Every moment this package uses arrives as a parameter — no
        `datetime.now`, no `date.today`, anywhere in the package."""
        offenders = []
        for path in PACKAGE.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "datetime.now(" in text or "date.today(" in text:
                offenders.append(path.name)
        assert offenders == []
