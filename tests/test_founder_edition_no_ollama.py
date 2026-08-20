"""Founder Edition must not touch Ollama on this machine.

A founder decision, not a technical one. The laptop has 16 GB and the
smaller of the two installed models occupies 9 GB resident -- that is the
founder's working memory, not spare capacity. It supersedes any
local-first preference, including the privacy argument that briefly put
the local runtime at the front of the reasoning ladder.

`providers/ollama.py` is untouched and remains a perfectly good generic
provider. What must not happen is Founder Edition *activating* it:
constructing it, registering it, ranking it, probing the daemon, loading a
model, or sending it a prompt.

A future developer who adds it back should fail these tests rather than
discover the constraint from a founder whose machine has stalled.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
COMPOSITION = REPO / "kalpavriksha_desktop.py"
SPEC = REPO / "packaging" / "kalpavriksha.spec"


def _code_only(source: str) -> str:
    """The source with comments and docstrings removed.

    The constraint is about what the program *does*. Comments explaining
    why Ollama is absent naturally mention it, and a test that could not
    tell those apart would forbid documenting the decision.
    """
    tree = ast.parse(source)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc:
                docstrings.add(doc)
    lines = []
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        lines.append(line.split("  #")[0])
    text = "\n".join(lines)
    for doc in docstrings:
        text = text.replace(doc, "")
    return text


@pytest.fixture(scope="module")
def composition_code():
    return _code_only(COMPOSITION.read_text(encoding="utf-8"))


class TestFounderEditionNeverActivatesOllama:

    def test_the_provider_is_never_constructed(self, composition_code):
        assert "OllamaProvider" not in composition_code, (
            "Founder Edition constructs an Ollama provider"
        )

    def test_it_is_never_imported(self, composition_code):
        assert "providers.ollama" not in composition_code
        assert "OLLAMA_PROVIDER_ID" not in composition_code

    def test_it_is_never_registered(self, composition_code):
        lowered = composition_code.lower()
        for line in lowered.splitlines():
            if "register" in line:
                assert "ollama" not in line, f"registers ollama: {line.strip()}"

    def test_no_local_tier_is_configured(self, composition_code):
        """The ladder still *supports* a local tier -- that is generic and
        reusable -- but this deployment passes none."""
        assert "local_provider_ids" not in composition_code

    def test_it_is_not_packaged(self):
        spec = _code_only(SPEC.read_text(encoding="utf-8"))
        assert "ollama" not in spec.lower(), (
            "the packaged build bundles the Ollama provider"
        )


class TestItCannotBeSelected:
    """Belt and braces: absent from the ladder AND excluded from every
    Broker call the ladder makes."""

    def test_the_catalogue_still_describes_it(self):
        """The generic entry stays -- another machine may use it. Its
        presence here is exactly why exclusion below matters."""
        from master_agent.ai_infrastructure.catalog import PROVIDER_CATALOG

        assert any(s.provider_id == "ollama.local" for s in PROVIDER_CATALOG)

    def test_every_tier_attempt_excludes_it(self):
        """`all_known_provider_ids` minus the configured tiers is the
        exclusion set, and `ollama.local` is in the catalogue that feeds
        it, so no tier's scoped request can rank it."""
        from master_agent.ai_infrastructure.catalog import PROVIDER_CATALOG
        from master_agent.ai_infrastructure.tiered_runner import TieredPromptRunner

        known = frozenset(s.provider_id for s in PROVIDER_CATALOG)
        runner = TieredPromptRunner(
            object(),
            gemini_provider_ids=frozenset({"gemini.api"}),
            desktop_provider_ids=frozenset({"chatgpt-desktop"}),
            browser_provider_ids=frozenset({"browser.free-ai"}),
            all_known_provider_ids=known,
        )
        configured = frozenset().union(*(ids for _name, ids in runner._tiers))
        assert "ollama.local" not in configured

        excluded = getattr(runner, "_all_ids", known) - configured
        assert "ollama.local" in excluded, (
            "ollama.local is neither configured nor excluded, so a Broker "
            "ranking could still select it"
        )


class TestTheGenericProviderSurvives:
    """§14/§15: disable the deployment's use, do not destroy the code."""

    def test_the_module_is_still_present(self):
        assert (REPO / "src" / "master_agent" / "providers" / "ollama.py").exists()

    def test_it_is_still_importable_and_whole(self):
        from master_agent.providers.ollama import (  # noqa: F401
            OLLAMA_PROVIDER_ID,
            OllamaProvider,
        )

        assert OLLAMA_PROVIDER_ID == "ollama.local"

    def test_importing_it_starts_nothing(self):
        """Construction performs no I/O -- the constraint is about
        Founder Edition never doing it, not about the class being unsafe."""
        import inspect

        from master_agent.providers.ollama import OllamaProvider

        source = inspect.getsource(OllamaProvider.__init__)
        for reaching_out in ("requests.", "urlopen", "post(", "get("):
            assert reaching_out not in source


class TestReasoningSurvivesWithoutIt:
    """§16: the capability stays, and privacy is not quietly relaxed to
    make up for the missing local provider."""

    def test_the_capability_is_still_registered(self):
        from master_agent.executor.executor import LocalExecutor
        from master_agent.permissions.permission_system import PermissionSystem
        from master_agent.plugins.reasoning_plugin import ReasoningPlugin

        plugin = ReasoningPlugin(LocalExecutor(PermissionSystem()))
        assert [c.name for c in plugin.manifest.capabilities] == ["transform"]

    def test_evidence_is_still_private_by_default(self):
        from master_agent.executor.executor import LocalExecutor
        from master_agent.permissions.permission_system import PermissionSystem
        from master_agent.plugins.reasoning_plugin import ReasoningPlugin

        seen = []

        class Runner:
            def run(self, prompt, request, **kwargs):
                seen.append(request)

                class Outcome:
                    ok = True
                    text = "an answer"

                return Outcome()

        ReasoningPlugin(LocalExecutor(PermissionSystem()), Runner()).invoke(
            "transform", {"instruction": "Summarise.", "context": "a document"}
        )
        assert seen[0].sensitive is True

    def test_private_work_still_needs_a_yes_for_a_public_provider(self):
        """With the local runtime gone, this is the rule that decides what
        happens to a private document: it becomes a founder question, not
        a silent send."""
        from dataclasses import dataclass

        from master_agent.ai_infrastructure.approval import (
            SENSITIVE_THIRD_PARTY,
            approval_needed,
        )
        from master_agent.ai_infrastructure.catalog import PROVIDER_CATALOG

        @dataclass
        class Profile:
            cost: float
            privacy: str

        gemini = next(s for s in PROVIDER_CATALOG if s.provider_id == "gemini.api")
        assert approval_needed(
            Profile(cost=gemini.cost_per_call, privacy=gemini.privacy), "sensitive"
        ) == SENSITIVE_THIRD_PARTY
