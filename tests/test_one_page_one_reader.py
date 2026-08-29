"""A long page must still be usable.

## What happened

H, the one live objective against a site nobody controls, read a real
Wikipedia article and then failed on this:

    step_4: binding on step 'step_3' field 'text': the step reported
    'Jump to content\\nMain menu\\nSearch\\n...' but the independent
    observation recorded 'Jump to content\\nMain menu\\nSearch\\n...';
    refusing to choose

Two strings that begin identically and are not equal. `ReadPageText` cut
its result at 40,000 characters; the independent Observation cut its own
at 20,000. `_verified_value()` compares them for EQUALITY -- correctly,
and it must keep doing so, because an Action and an Observation
disagreeing is exactly what Verification exists to surface.

So **every page longer than 20,000 characters was unusable as reasoning
input**, deterministically, and the failure looked like a disagreement
about the page rather than what it was: two truncations of one string.

## Why no fixture caught it

Every controlled page in the diversified battery is a few hundred
characters. Below both limits, the two readers agree perfectly, which is
precisely why a battery of fixtures the author wrote cannot substitute
for one objective against reality nobody arranged.

## The fix, and what it is not

Not "make the two constants match" -- that is the same bug waiting for
someone to change one of them. There is now one reader,
`read_visible_text`, and the Action calls it.
"""
from __future__ import annotations

import types

from master_agent.executor.actions.browser.read_page_text import (
    MAX_TEXT_CHARS,
    ReadPageTextAction,
)
from master_agent.plugins.browser_observation import (
    MAX_PAGE_TEXT_CHARS,
    normalize_observation,
    read_visible_text,
)

#: Longer than the Observation's limit and shorter than what the Action
#: used to allow -- the band in which the two answers could never match.
LONG_PAGE = "Jump to content\nMain menu\n" + ("metro system opened 1919. " * 1200)


def _page(text: str, url: str = "https://en.wikipedia.org/wiki/List_of_metro_systems"):
    return types.SimpleNamespace(
        url=url,
        title=lambda: "List of metro systems",
        inner_text=lambda selector: text,
        viewport_size={"width": 1280, "height": 800},
        eval_on_selector_all=lambda selector, script: [],
        locator=lambda selector: None,
    )


class _Sessions:
    def __init__(self, page):
        self._page = page

    def get(self, session_id):
        return types.SimpleNamespace(page=self._page)


class TestTheActionAndTheObservationReadTheSamePage:
    def test_the_long_page_is_long_enough_to_have_shown_the_bug(self):
        assert len(LONG_PAGE) > MAX_PAGE_TEXT_CHARS, (
            "this fixture only means something above the Observation's limit")

    def test_they_return_the_identical_string(self):
        """The whole defect, in one assertion. Not "both are truncated"
        -- byte-for-byte identical, because that is what the binding
        compares."""
        page = _page(LONG_PAGE)

        reported = ReadPageTextAction(_Sessions(page)).run(
            {"session_id": "s"}).output["text"]
        observed = normalize_observation(page, include_text=True).text

        assert reported == observed

    def test_a_short_page_is_untouched_by_either(self):
        page = _page("Halden Reading Room is step-free.")

        reported = ReadPageTextAction(_Sessions(page)).run(
            {"session_id": "s"}).output["text"]
        observed = normalize_observation(page, include_text=True).text

        assert reported == observed == "Halden Reading Room is step-free."

    def test_truncation_is_declared_by_both_when_it_bites(self):
        """Silence about a cut is the thing that turns a shortened page
        into a confidently wrong answer."""
        page = _page(LONG_PAGE)

        result = ReadPageTextAction(_Sessions(page)).run({"session_id": "s"})
        observation = normalize_observation(page, include_text=True)

        assert result.output["truncated"] is True
        assert observation.text_truncated is True

    def test_there_is_one_limit_and_the_action_does_not_own_it(self):
        """A structural guard. Two constants that happen to be equal
        today is the same bug with a longer fuse."""
        assert MAX_TEXT_CHARS is MAX_PAGE_TEXT_CHARS

    def test_the_action_uses_the_observation_s_own_reader(self):
        import inspect

        source = inspect.getsource(ReadPageTextAction.run)
        assert "read_visible_text" in source
        assert "inner_text" not in source, (
            "a second implementation is how the two answers drifted apart")


class TestTheBindingStillRefusesARealDisagreement:
    """The equality check is not what was wrong and must not be relaxed.

    An Action and an independent Observation genuinely disagreeing about
    a page is the condition Verification exists to surface, and silently
    preferring either one would make the Evidence decorative.
    """

    def test_a_genuine_mismatch_is_still_refused(self):
        from master_agent.runtime.input_resolution import (
            BindingResolutionError,
            resolve_inputs,
        )

        source = types.SimpleNamespace(
            step_id="step_3",
            capability="Browser.ReadPageText",
            state="completed",
            result={"text": "the page said one thing"},
            evidence={"evidence_id": "ev-1", "verdict": "matched",
                      "observation": {"text": "the page said another"}},
        )
        task = types.SimpleNamespace(
            task_id="t-1",
            payload={"instruction": "summarise"},
            depends_on=["step_3"],
            input_bindings={"context": {"from_step": {"step_id": "step_3",
                                                      "field": "text"}}},
        )

        try:
            resolve_inputs(task, {"step_3": source})
        except BindingResolutionError as exc:
            assert "refusing to choose" in str(exc)
        else:  # pragma: no cover - the guard would be gone
            raise AssertionError("a real disagreement must still be refused")

    def test_agreement_flows_and_public_provenance_is_derived(self):
        """The other half of the same path: once the two readers agree,
        the value flows AND public browser provenance is what decides how
        it may be handled."""
        from master_agent.runtime.input_resolution import resolve_inputs

        page_text = "Madrid Metro opened in 1919."
        source = types.SimpleNamespace(
            step_id="step_3",
            capability="Browser.ReadPageText",
            state="completed",
            result={"text": page_text},
            evidence={"evidence_id": "ev-1", "verdict": "matched",
                      "observation": {"text": page_text}},
        )
        task = types.SimpleNamespace(
            task_id="t-1",
            payload={"instruction": "which city?"},
            depends_on=["step_3"],
            input_bindings={"context": {"from_step": {"step_id": "step_3",
                                                      "field": "text"}}},
        )

        resolved = resolve_inputs(task, {"step_3": source})

        assert resolved.payload["context"] == page_text
        assert resolved.payload["sensitive"] is False
