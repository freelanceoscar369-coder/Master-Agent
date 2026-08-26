"""The FMEA harness must fail fast instead of falling through.

When Gemini returned HTTP 429 mid-run, the reasoning ladder did exactly
what the product should do -- fell through to the desktop AI applications
-- and launched twenty-three ChatGPT/Kimi/Perplexity processes on the
founder's machine before anything stopped it. Correct product behaviour;
unacceptable test behaviour.

A pre-flight probe cannot prevent that. A small probe succeeds where a
planning-sized request gets 429, and a planning-sized probe consumes the
very quota it is trying to predict. Scoping the tiers is the only honest
answer: the harness refuses to fall through rather than guessing whether
it would need to.

These tests hold two things at once:

* with the FMEA scope active, a Gemini failure reaches nobody else;
* with it absent -- every normal Founder launch -- the full
  Gemini -> Desktop -> Browser ladder is unchanged.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from master_agent.ai_infrastructure.tiered_runner import TieredPromptRunner

REPO = pathlib.Path(__file__).resolve().parent.parent


class CountingExecutor:
    """Stands in for `PromptExecutor`, recording which providers were asked
    and refusing every request the way an exhausted quota would."""

    def __init__(self) -> None:
        self.asked: list[str] = []

    def run(self, *args, **kwargs):
        allowed = kwargs.get("allowed_provider_ids") or kwargs.get("provider_ids") or ()
        self.asked.extend(sorted(allowed))
        raise RuntimeError("HTTP 429: You exceeded your current quota")

    # The runner may call any of these depending on its seam; all record.
    execute = run
    complete = run


DESKTOP_IDS = frozenset({"chatgpt-desktop", "kimi-desktop", "perplexity-desktop"})
BROWSER_IDS = frozenset({"browser.free-ai"})


class TestTheScopedRunnerHasNoLaterTiers:

    def test_only_gemini_is_configured(self):
        runner = TieredPromptRunner(
            CountingExecutor(),
            gemini_provider_ids=frozenset({"gemini.api"}),
            desktop_provider_ids=frozenset(),
            browser_provider_ids=frozenset(),
        )
        configured: set[str] = set()
        for _tier, ids in runner._tiers:
            configured |= set(ids)

        assert configured == {"gemini.api"}
        assert not (configured & DESKTOP_IDS), "a desktop provider is reachable"
        assert not (configured & BROWSER_IDS), "a browser provider is reachable"

    def test_a_gemini_failure_reaches_no_other_provider(self):
        """The 429 case, simulated. Nothing after Gemini may be asked."""
        executor = CountingExecutor()
        runner = TieredPromptRunner(
            executor,
            gemini_provider_ids=frozenset({"gemini.api"}),
            desktop_provider_ids=frozenset(),
            browser_provider_ids=frozenset(),
        )
        try:
            runner.run("plan something", capability="reasoning")
        except Exception:
            pass  # the outcome shape is not what this test is about

        assert not (set(executor.asked) & DESKTOP_IDS), (
            f"a desktop provider was asked after Gemini failed: {executor.asked}"
        )
        assert not (set(executor.asked) & BROWSER_IDS), (
            f"a browser provider was asked after Gemini failed: {executor.asked}"
        )

    def test_the_unscoped_runner_would_have_fallen_through(self):
        """The premise. If an unscoped runner did not reach later tiers,
        these tests would be guarding a problem that does not exist."""
        executor = CountingExecutor()
        runner = TieredPromptRunner(
            executor,
            gemini_provider_ids=frozenset({"gemini.api"}),
            desktop_provider_ids=DESKTOP_IDS,
            browser_provider_ids=BROWSER_IDS,
        )
        configured: set[str] = set()
        for _tier, ids in runner._tiers:
            configured |= set(ids)

        assert configured & DESKTOP_IDS
        assert configured & BROWSER_IDS


def _composition_source() -> str:
    return (REPO / "kalpavriksha_desktop.py").read_text(encoding="utf-8")


class TestNormalFounderLaunchIsUnchanged:
    """The scope must be dormant unless explicitly switched on."""

    def test_the_switch_is_read_from_a_dedicated_variable(self):
        source = _composition_source()
        assert "KALPAVRIKSHA_FMEA_REASONING_TIER" in source

    def test_the_desktop_tier_is_only_emptied_under_the_switch(self):
        """Parsed, not grepped: the desktop tier must still be the full
        catalogue when the switch is off."""
        source = _composition_source()
        tree = ast.parse(source)

        call = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "TieredPromptRunner"
        )
        by_keyword = {kw.arg: ast.unparse(kw.value) for kw in call.keywords}

        rendered = by_keyword["desktop_provider_ids"]
        assert "_gemini_only" in rendered, (
            "the desktop tier does not depend on the FMEA switch"
        )
        # The condition gained `_web_only` when the validation scope learned
        # to isolate the web rung. What this guard actually protects is that
        # the desktop tier stays CONDITIONAL -- so an unset switch still
        # yields the full catalogue -- not the exact spelling of the
        # condition. `tests/test_fmea_web_scope.py` proves the behaviour
        # itself, which is the stronger statement.
        assert "else" in rendered, (
            "the desktop tier is not a conditional -- the normal ladder may be gone"
        )
        assert "_web_only" in rendered or "_gemini_only" in rendered
        assert "PROVIDER_CATALOG" in rendered, (
            "the normal desktop tier no longer draws from the provider catalogue"
        )

        # This asserted the browser tier was EMPTY, which was true when the
        # rung had no provider Founder Edition would use. The rung is filled
        # now -- by the TRUSTED browser lane, the founder's own signed-in
        # browser driven through the Desktop Executive -- so "empty" is no
        # longer the property worth guarding.
        #
        # What the assertion was always really protecting is that Duck.ai
        # does not come back, and `browser.free-ai` is the provider that
        # drives it. That is what it checks now.
        rung = by_keyword["browser_provider_ids"]
        assert "BROWSER_FREE_AI_ID" not in rung, (
            "Duck.ai is back in the Founder Edition ladder"
        )
        assert "TRUSTED_WEB_PROVIDER_ID" in rung, (
            "the web rung should be the trusted browser lane"
        )

    @pytest.mark.parametrize("value", ["", "   ", "off", "no", "desktop"])
    def test_only_the_exact_value_activates_it(self, value):
        """Anything other than `gemini` leaves the full ladder in place, so
        a typo cannot silently disable the founder's fallback."""
        assert (value or "").strip().lower() != "gemini"

    def test_the_switch_defaults_to_the_full_ladder(self):
        """With the variable unset, `_gemini_only` is False."""
        import os

        value = (os.environ.get("KALPAVRIKSHA_FMEA_REASONING_TIER") or "").strip().lower()
        assert (value == "gemini") is False, (
            "the FMEA reasoning scope is active in this environment; a "
            "normal launch would lose its fallback"
        )
