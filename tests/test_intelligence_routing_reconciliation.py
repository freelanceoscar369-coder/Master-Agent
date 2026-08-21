"""The ladder is ADR-0017's, and ownership stays where it was frozen.

ADR-0017 Decision 3 freezes a six-rung order — local, desktop app, free
cloud, free aggregator, existing subscription, paid API — walked from the
cheapest rung. Constitution §7.1 makes local-first not optional.

The implementation read `gemini -> desktop -> browser -> local`. That was
my drift, argued at the time as "order is capability, not privacy". The
argument addressed the wrong question: ADR-0017 does not order these by
capability. A frozen decision is not re-derivable because a local model is
slow, and a second routing policy inside the runner is how the ladder came
to disagree with the ADR in the first place.

These tests are the barrier. They read the ADR text itself, so a future
amendment has to change the document and the code together rather than one
of them quietly.
"""
from __future__ import annotations

import ast
import inspect
import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
ADR = REPO / "docs" / "adr" / "0017-ai-capability-broker.md"
COMPOSITION = REPO / "kalpavriksha_desktop.py"

#: The runner's tier names, in ADR order. `gemini` is the free-cloud rung
#: and `browser` the free-aggregator rung; the last two ADR rungs have no
#: tier yet because no subscription or paid provider is wired.
CANONICAL = ["local", "desktop", "gemini", "browser"]


class TestTheLadderMatchesTheAdr:

    def test_the_adr_still_says_what_we_think_it_says(self):
        """Read from the document, not from memory. If someone amends the
        ADR, this test is where the code finds out."""
        text = ADR.read_text(encoding="utf-8")
        ladder = re.search(
            r"local\s*→\s*desktop app\s*→\s*free cloud\s*→\s*free aggregator[^)]*",
            text,
        )
        assert ladder, "ADR-0017's ladder is no longer stated in the form this reads"
        assert "cheapest rung" in text

    def test_the_runner_walks_that_order(self):
        from master_agent.ai_infrastructure.tiered_runner import TieredPromptRunner

        runner = TieredPromptRunner(
            object(),
            local_provider_ids=frozenset({"a"}),
            desktop_provider_ids=frozenset({"b"}),
            gemini_provider_ids=frozenset({"c"}),
            browser_provider_ids=frozenset({"d"}),
        )
        assert [name for name, _ in runner._tiers] == CANONICAL

    def test_local_is_first(self):
        """Constitution §7.1 — not optional, and not a slogan."""
        from master_agent.ai_infrastructure.tiered_runner import TieredPromptRunner

        runner = TieredPromptRunner(
            object(),
            local_provider_ids=frozenset({"ollama.local"}),
            desktop_provider_ids=frozenset(),
            gemini_provider_ids=frozenset({"gemini.api"}),
            browser_provider_ids=frozenset(),
        )
        assert runner._tiers[0][0] == "local"

    def test_an_empty_rung_is_skipped_not_an_error(self):
        """Every rung exists in the ladder whether or not this deployment
        fills it. A rung nobody wired is not a missing tier."""
        from master_agent.ai_infrastructure.tiered_runner import TieredPromptRunner

        runner = TieredPromptRunner(
            object(),
            local_provider_ids=frozenset(),
            desktop_provider_ids=frozenset(),
            gemini_provider_ids=frozenset({"gemini.api"}),
            browser_provider_ids=frozenset(),
        )
        assert [name for name, _ in runner._tiers] == CANONICAL


class TestTheRunnerHoldsNoPolicy:
    """Ranking is the Broker's. The runner walks a fixed ladder."""

    def test_the_order_never_depends_on_the_request(self):
        from master_agent.ai_infrastructure.tiered_runner import TieredPromptRunner

        source = inspect.getsource(TieredPromptRunner.run)
        assert "for tier_name, tier_ids in self._tiers:" in source
        for policy in ("sensitive", "_ordered_tiers", "sort", "rank"):
            assert policy not in source, f"the runner decides order by {policy!r}"

    def test_no_second_ordering_function_exists(self):
        from master_agent.ai_infrastructure import tiered_runner

        assert not hasattr(tiered_runner.TieredPromptRunner, "_ordered_tiers")

    def test_the_runner_selects_no_provider_itself(self):
        """It scopes a tier and asks; the Broker chooses within it."""
        from master_agent.ai_infrastructure.tiered_runner import TieredPromptRunner

        source = inspect.getsource(TieredPromptRunner)
        assert "exclude_providers" in source, "the runner no longer scopes by exclusion"
        assert "def select" not in source


class TestOwnershipIsUnchanged:
    """ADR-0017's boundaries, asserted where they can actually break."""

    def test_the_broker_does_not_discover(self):
        from master_agent.broker import broker

        source = inspect.getsource(broker)
        for reaching_out in ("requests.", "urlopen", "subprocess", "Popen",
                             "os.path.exists", "shutil.which"):
            assert reaching_out not in source, f"the Broker discovers via {reaching_out}"

    def test_the_broker_does_not_execute(self):
        from master_agent.broker import broker

        source = inspect.getsource(broker)
        for executing in ("def complete", "provider.complete", ".run("):
            assert executing not in source, f"the Broker executes via {executing}"

    def test_the_broker_does_not_retry(self):
        from master_agent.broker import broker

        source = inspect.getsource(broker).lower()
        assert "retry" not in source and "attempt +" not in source

    def test_discovery_belongs_to_the_ai_infrastructure_executive(self):
        from master_agent.ai_infrastructure.executive import actions

        names = [n for n in dir(actions) if n.endswith("Action")]
        assert any("Discover" in n for n in names), (
            "the AI Infrastructure Executive no longer owns discovery"
        )

    def test_approval_belongs_to_the_permission_boundary(self):
        """Paid and privacy decisions are the Permission System's, reached
        through `approval_needed` -- never minted by the Broker."""
        from master_agent.ai_infrastructure.approval import approval_needed
        from master_agent.broker import broker

        assert callable(approval_needed)
        assert "approval_needed" not in inspect.getsource(broker)


class TestFounderEditionHasNoDuckAi:

    @staticmethod
    def _code_only() -> str:
        """Source with comments and docstrings dropped: the constraint is
        about what the program does, and explaining the decision naturally
        names the thing it excludes."""
        source = COMPOSITION.read_text(encoding="utf-8")
        tree = ast.parse(source)
        docs = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
                doc = ast.get_docstring(node, clean=False)
                if doc:
                    docs.add(doc)
        body = "\n".join(
            line for line in source.splitlines() if not line.strip().startswith("#")
        )
        for doc in docs:
            body = body.replace(doc, "")
        return body

    def test_the_provider_is_never_constructed(self):
        assert "BrowserFreeAiReasoningProvider" not in self._code_only()

    def test_no_browser_tier_is_configured(self):
        tree = ast.parse(COMPOSITION.read_text(encoding="utf-8"))
        call = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "TieredPromptRunner"
        )
        keywords = {kw.arg: ast.unparse(kw.value) for kw in call.keywords}
        assert keywords["browser_provider_ids"] == "frozenset()"

    def test_it_stays_excluded_from_every_tier_attempt(self):
        """Not configured AND explicitly excluded -- so the Broker cannot
        rank it into a tier it was never placed in."""
        assert "BROWSER_FREE_AI_ID" in self._code_only()

    def test_the_generic_provider_still_exists(self):
        """A founder decision about this product, not a deletion. ADR-0017
        keeps a free-aggregator rung and another deployment may fill it."""
        from master_agent.providers.browser_free_ai import (  # noqa: F401
            BrowserFreeAiReasoningProvider,
        )

        assert (REPO / "src" / "master_agent" / "providers"
                / "browser_free_ai.py").exists()


class TestBrowserPresentationIsComposed:
    """§ Browser presentation: visible or headless is a deployment choice,
    never something ranking logic knows about."""

    def test_the_broker_knows_nothing_about_editions(self):
        from master_agent.broker import broker

        source = inspect.getsource(broker).lower()
        for leak in ("founder edition", "founder_edition", "headless", "visible"):
            assert leak not in source, f"ranking logic mentions {leak!r}"

    def test_presentation_is_a_session_argument(self):
        from master_agent.environment.browser_session import BrowserSessionManager

        signature = inspect.signature(BrowserSessionManager.__init__)
        assert "default_headless" in signature.parameters
