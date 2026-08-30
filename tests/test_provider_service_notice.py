"""An application talking about itself is not an answer.

## The failure

Asked to identify action RPGs from a page of store listings, a desktop AI
application returned:

    "High demand. Switched to K2.6 Instant for speed. Upgrade to use K2.6
     Thinking."

`SUCCEEDED` carried that onward as the reasoning result. Verification
later caught it -- correctly, as `partially_matched` -- but by then the
provider ladder was long gone, and the founder got a failed mission
instead of the next provider's answer.

## Why the adapter owns this

`gemini.py` already makes the same judgement about HTTP 503 ("this model
is currently experiencing high demand"): a transient service condition is
a provider failure, not a bad answer. A desktop application says the same
thing in text instead of a status code, and this adapter is the only
thing that knows what its own applications say.

It is `UNAVAILABLE`, not `MALFORMED`: nothing was wrong with the request
and rephrasing would not help. This provider cannot serve it right now,
which is exactly what the ladder's exclude-and-ask-again is for.

## What must NOT be thrown away

A genuine partial answer is still the founder's. Verification decides
whether it was enough; this does not. So a notice must be a BANNER --
short AND service-shaped -- and a real reply that happens to mention a
quota goes through untouched.
"""
from __future__ import annotations

import pytest

from master_agent.providers.desktop_app import (
    MAX_SERVICE_NOTICE_CHARS,
    _is_service_notice,
)


class TestAServiceNoticeIsRecognised:
    def test_the_exact_notice_that_broke_the_mission(self):
        assert _is_service_notice(
            "High demand. Switched to K2.6 Instant for speed. "
            "Upgrade to use K2.6 Thinking."
        ) is True

    @pytest.mark.parametrize("notice", [
        "We're at capacity right now. Please try again later.",
        "Rate limit reached. Try again in a few minutes.",
        "You have hit your usage limit for today.",
        "Please sign in to continue.",
        "This service is temporarily unavailable.",
        "Upgrade your plan to keep going.",
    ])
    def test_the_shapes_a_service_uses_about_itself(self, notice):
        assert _is_service_notice(notice) is True

    def test_it_matches_shapes_not_one_product(self):
        """Nothing here is a product's wording. A catalogue of one
        sentence would stop working the day that sentence changed."""
        import inspect

        from master_agent.providers import desktop_app

        source = inspect.getsource(desktop_app)
        for product in ("k2.6", "kimi instant", "gpt-4", "claude 3"):
            assert product not in source.lower().split("Measured live")[-1][:400]


class TestARealAnswerIsNeverThrownAway:
    def test_an_ordinary_answer_passes_through(self):
        assert _is_service_notice(
            "Three of the listed titles are action RPGs: Ashen Vale, "
            "Mirebound and Ghostlight."
        ) is False

    def test_a_long_answer_mentioning_a_quota_is_still_an_answer(self):
        """The discriminator is short AND service-shaped. A genuine reply
        that happens to discuss rate limits is the founder's, and
        Verification is what judges whether it was enough."""
        answer = (
            "The API documentation describes a rate limit of 100 requests "
            "per minute, and the quota resets hourly. "
        ) * 6
        assert len(answer) > MAX_SERVICE_NOTICE_CHARS
        assert _is_service_notice(answer) is False

    def test_empty_text_is_not_a_notice(self):
        """Empty has its own failure already; two names for one condition
        would make the reason a founder reads depend on which check ran
        first."""
        assert _is_service_notice("") is False
        assert _is_service_notice("   ") is False

    def test_a_short_genuine_answer_is_not_a_notice(self):
        assert _is_service_notice("Ashen Vale and Mirebound.") is False


class TestItReachesTheLadderAsAProviderFailure:
    def test_the_adapter_returns_unavailable_not_malformed(self):
        """`UNAVAILABLE` says "not this provider, right now" -- which is
        what makes the ladder exclude it and ask the Broker again.
        `MALFORMED` would say the request was wrong, and it was not."""
        import inspect

        from master_agent.providers import desktop_app

        source = inspect.getsource(desktop_app.DesktopAppReasoningProvider.complete)
        notice = source[source.index("_is_service_notice"):]
        assert "UNAVAILABLE" in notice[:400]
        assert "SERVICE_NOTICE" in notice[:400]

    def test_it_is_checked_after_the_empty_and_echo_guards(self):
        """Those are cheaper and more specific. Order matters only so the
        founder reads the most precise reason available."""
        import inspect

        from master_agent.providers import desktop_app

        source = inspect.getsource(desktop_app.DesktopAppReasoningProvider.complete)
        assert source.index("EMPTY_RESPONSE") < source.index("_is_service_notice")

    def test_the_notice_is_kept_for_diagnosis(self):
        """A founder asking why a provider was skipped deserves the
        sentence it actually said."""
        import inspect

        from master_agent.providers import desktop_app

        source = inspect.getsource(desktop_app.DesktopAppReasoningProvider.complete)
        assert "notice=" in source


class TestOurOwnPromptHandedBackIsNotAnAnswer:
    """Reproduced live against Kimi Desktop.

    The scrape returned the composer placeholder, our marked prompt, and
    the surrounding UI labels -- with `ok=True`:

        "Ask me. Task me.
         [Kalpavriksha Reasoning - Kimi Desktop - ... - d477b9ad]
         Create or select a file to start
         Edit  Copy  Share ..."

    It propagated as a reasoning result, and every consumer behaved
    correctly on nonsense: the Planner could not build a plan from it and
    the candidate extractor found nothing. A whole acceptance battery
    failed while the ladder reported success at every rung.

    The existing guard catches an EXACT echo. The real shape is never
    exact, because the composer decorates.
    """

    SENT = ("[Kalpavriksha Reasoning - Kimi Desktop - 2026-08-28 - d477b9ad] "
            "Which reading rooms are step-free?")

    def test_the_live_shape_is_rejected(self):
        from master_agent.providers.desktop_app import _is_only_our_own_prompt

        chrome = (
            "Ask me. Task me.\n" + self.SENT +
            "\nCreate or select a file to start\nEdit\nCopy\nShare"
        )
        assert _is_only_our_own_prompt(chrome, self.SENT) is True

    def test_a_short_but_real_answer_survives(self):
        """The guard must not eat a terse reply. "Yes, both are
        step-free" is an answer."""
        from master_agent.providers.desktop_app import _is_only_our_own_prompt

        answer = self.SENT + "\nHalden and Brackwell both have step-free entrances."
        assert _is_only_our_own_prompt(answer, self.SENT) is False

    def test_an_answer_that_does_not_quote_us_survives(self):
        from master_agent.providers.desktop_app import _is_only_our_own_prompt

        assert _is_only_our_own_prompt(
            "Halden and Brackwell are step-free.", self.SENT
        ) is False

    def test_it_compares_on_words_not_characters(self):
        """A rich composer reflows whitespace on paste -- the same reason
        `_verify_readback` normalises before comparing."""
        from master_agent.providers.desktop_app import _is_only_our_own_prompt

        reflowed = "Ask me. Task me.\n\n   " + " ".join(self.SENT.split()) + "\n\nEdit Copy"
        assert _is_only_our_own_prompt(reflowed, self.SENT) is True

    def test_empty_inputs_are_not_treated_as_an_echo(self):
        from master_agent.providers.desktop_app import _is_only_our_own_prompt

        assert _is_only_our_own_prompt("", self.SENT) is False
        assert _is_only_our_own_prompt("something", "") is False

    def test_the_adapter_fails_closed_on_it(self):
        import inspect

        from master_agent.providers import desktop_app

        source = inspect.getsource(desktop_app.DesktopAppReasoningProvider.complete)
        assert "_is_only_our_own_prompt" in source
        assert "PROMPT_ECHOED" in source


class TestTheWindowDescribingItselfIsNotAnAnswer:
    """Measured live, this session, against Kimi Desktop.

    Asked to reply with one nonce token, the provider returned
    `SUCCEEDED` carrying eight lines of the window's own furniture:

        Copy / Share / Create or select a file to start / Your chats will
        appear here / Update / Instant / High / AI-generated, for
        reference only

    Our prompt was not in it, so the echo guard did not fire. It is not a
    service notice, so that guard did not fire. It was a reasoning result
    as far as everything downstream could tell.
    """

    FURNITURE = (
        "Copy\nShare\nCreate or select a file to start\n"
        "Your chats will appear here\nUpdate\nInstant\nHigh\n"
        "AI-generated, for reference only"
    )

    def test_the_live_capture_is_recognised(self):
        from master_agent.providers.desktop_app import _is_only_interface_text

        assert _is_only_interface_text(self.FURNITURE) is True

    def test_one_substantive_line_makes_it_an_answer(self):
        """Furniture usually arrives ATTACHED to a real reply -- `Copy`
        and `Share` sit under every message. The question is never
        whether furniture is present, only whether anything else is."""
        from master_agent.providers.desktop_app import _is_only_interface_text

        assert _is_only_interface_text(
            "Copy\nHalden Reading Room is step-free.\nShare") is False

    def test_a_terse_genuine_reply_survives(self):
        from master_agent.providers.desktop_app import _is_only_interface_text

        for reply in ("Yes, both are step-free.",
                      "KALPAVRIKSHA_KIMI_FRESH_ALPHA_5bd5b9c3",
                      "Halden."):
            assert _is_only_interface_text(reply) is False, reply

    def test_a_sentence_opening_with_a_label_word_is_not_a_label(self):
        """"Copy the following three names into your notes" begins with a
        control's name and is plainly prose. Length is what separates
        them, and it is checked before the vocabulary is consulted."""
        from master_agent.providers.desktop_app import _is_only_interface_text

        assert _is_only_interface_text(
            "Copy the following three names into your notes and share them") is False

    def test_nothing_at_all_is_left_to_the_empty_response_guard(self):
        from master_agent.providers.desktop_app import _is_only_interface_text

        assert _is_only_interface_text("") is False
        assert _is_only_interface_text("   \n  ") is False

    def test_the_acceptance_script_and_the_product_share_one_vocabulary(self):
        """This knowledge used to live only in
        `scripts/live_acceptance/p0_3_complete_response.py`, which meant
        the acceptance run was the only thing it protected."""
        import pathlib

        source = pathlib.Path(
            "scripts/live_acceptance/p0_3_complete_response.py"
        ).read_text(encoding="utf-8")
        assert "_INTERFACE_LABELS" in source
        assert '"your chats will appear here"' not in source
