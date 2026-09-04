"""The trusted web-AI lane: which browser, which conversation, whose turn.

Every page state here is scripted. No real browser is driven, no founder
profile is touched, and no website is contacted -- which is the point:
the branches that matter (a browser that lies about being usable, focus
stolen mid-operation, two identically-named conversations) are rare live
and instant here.

The live facts these tests encode were measured on the founder's own
machine and are noted where they shaped an assertion.
"""
from __future__ import annotations

from master_agent.founder_interaction import (
    DeferredFounderInteraction,
    FounderChoiceResponse,
)
from master_agent.providers.trusted_web_ai import (
    GEMINI_WEB,
    TrustedWebAiProvider,
    WebAiSite,
)
from master_agent.trusted_browser import (
    BrowserCandidate,
    BrowserResolution,
    PageElement,
    PageObservation,
    TrustedBrowserResult,
)

PROMPT = "Give exactly three short names for a gardening notes app, one name per line."
ANSWER = "Sprout\nLeaflet\nFlora"
SECOND_PROMPT = "Give one more short gardening app name."
SECOND_ANSWER = "Trowel"
COMPOSER = GEMINI_WEB.composer_name
TITLE = "Kalpavriksha"


# =========================================================================
# A scripted browser
# =========================================================================


class Page:
    def __init__(self, title: str = "", texts=(), controls=(), usable: bool = True):
        self.title = title
        self.texts = list(texts)
        self.controls = list(controls)
        self.usable = usable


class FakeBrowser:
    """A `TrustedBrowserPort` whose whole world is a list of pages."""

    def __init__(self, candidates=(), pages=None, foreground=True, ambiguous=False,
                 pages_by_app=None):
        self._candidates = tuple(candidates)
        self._pages = list(pages or [Page("Google Gemini", controls=[COMPOSER])])
        #: Different browsers show different things -- including one that
        #: shows nothing readable at all, which is the case that matters.
        self._pages_by_app = {k: list(v) for k, v in (pages_by_app or {}).items()}
        self._ambiguous = ambiguous
        self.foreground = foreground
        self.used: list[str] = []
        self.typed: list[tuple[str, str]] = []
        self.keys: list[str] = []
        self.clicked: list[str] = []
        self.navigated: list[str] = []
        self.tabs_opened: list[str] = []
        self.launched = 0
        #: Control names that genuinely move the page on.
        self.advance_on: set[str] = set()
        self.application = self._candidates[0].application if self._candidates else "chrome"

    # -- resolution
    def resolve(self, page_markers):
        showing = [c for c in self._candidates if c.has_target_page]
        ordered = tuple(sorted(self._candidates,
                              key=lambda c: (not c.has_target_page, not c.is_foreground)))
        if self._ambiguous and len(showing) > 1:
            return BrowserResolution(None, "ambiguous", tuple(showing), ordered)
        if len(showing) == 1:
            return BrowserResolution(showing[0], "one showing", ordered=ordered)
        if len(showing) > 1:
            front = [c for c in showing if c.is_foreground]
            if len(front) == 1:
                return BrowserResolution(front[0], "foreground", ordered=ordered)
            return BrowserResolution(None, "ambiguous", tuple(showing), ordered)
        if ordered:
            return BrowserResolution(ordered[0], "reusing running", ordered=ordered)
        return BrowserResolution(None, "nothing running", (), ())

    def alternatives(self, exclude=()):
        """Configured environments that have not just been proven
        unreadable. The port gained this so a provider that found every
        RUNNING browser undrivable can open a fresh one instead of
        insisting on the broken one."""
        skip = {str(name).casefold() for name in exclude}
        return tuple(
            BrowserCandidate(application=c.application, has_target_page=False)
            for c in self._candidates
            if c.application.casefold() not in skip
        )

    def use(self, candidate):
        self.application = candidate.application
        self.used.append(candidate.application)
        if candidate.application in self._pages_by_app:
            self._pages = list(self._pages_by_app[candidate.application])
        return TrustedBrowserResult(True, candidate.application)

    def ensure_available(self):
        self.launched += 1
        return TrustedBrowserResult(True, "launched")

    def open_task_tab(self, url):
        self.tabs_opened.append(url)
        return TrustedBrowserResult(True, "tab")

    def navigate(self, url):
        self.navigated.append(url)
        return TrustedBrowserResult(True, "navigated")

    # -- observation
    @property
    def page(self) -> Page:
        return self._pages[0]

    def advance(self):
        if len(self._pages) > 1:
            self._pages.pop(0)

    def observe(self):
        page = self.page
        if not page.usable:
            return PageObservation(application=self.application, observed_at=1.0)
        elements = [
            PageElement(role="text_region", name=text, is_actionable=False)
            for text in page.texts
        ] + [
            PageElement(role="button", name=name, is_actionable=True, x=10, y=20)
            for name in page.controls
        ]
        return PageObservation(
            application=self.application,
            window_title=page.title,
            window_handle=1,
            foreground=self.foreground,
            elements=tuple(elements),
            observed_at=1.0,
        )

    def find(self, name_contains, control_type=None):
        if not self.page.usable:
            return None
        for name in self.page.controls:
            if name_contains in name:
                return PageElement(role="button", name=name, is_actionable=True, x=10, y=20)
        return None

    # -- acting
    def type_into(self, name_contains, text, control_type=None):
        if not self.foreground:
            return TrustedBrowserResult(False, "the window is not in front; nothing was typed")
        self.typed.append((name_contains, text))
        return TrustedBrowserResult(True, "typed")

    def press(self, key):
        self.keys.append(key)
        self.advance()
        return TrustedBrowserResult(True, key)

    def click(self, element):
        """A click records itself and changes nothing else.

        Deliberate: the provider must never treat a click as proof that
        the page changed, so the fake refuses to reward it with one.
        Pages move on only where a test says so.
        """
        self.clicked.append(element.name)
        if element.name in self.advance_on:
            self.advance()
        return TrustedBrowserResult(True, element.name)

    def close_task_tab(self):
        return TrustedBrowserResult(True, "closed")


class Founder:
    can_ask = True

    def __init__(self, answer=None):
        self.answer = answer or FounderChoiceResponse.cancel()
        self.asked = []
        self.told = []

    def ask_choice(self, request):
        self.asked.append(request)
        return self.answer

    def notify(self, message):
        self.told.append(message)


def chrome(title="Google Gemini", target=True, fg=False):
    return BrowserCandidate("chrome", 1, title, target, fg)


def comet(title="Comet", target=False, fg=True):
    return BrowserCandidate("comet", 2, title, target, fg)


def provider(browser, **kwargs):
    kwargs.setdefault("interaction", Founder())
    p = TrustedWebAiProvider(browser=browser, **kwargs)
    p._sleep = lambda seconds: None
    ticks = iter(range(100000))
    p._now = lambda: next(ticks) * 0.5
    return p


def answered(title=TITLE):
    return Page(title, texts=[PROMPT, ANSWER, "Gemini is AI and can make mistakes."],
                controls=[COMPOSER])


# =========================================================================
# 1-4. Which browser executes
# =========================================================================


def test_chrome_has_the_target_page_and_comet_does_not():
    browser = FakeBrowser([chrome(target=True), comet(target=False, fg=True)])
    provider(browser).complete(PROMPT)
    assert browser.used[0] == "chrome", "the browser showing the page wins, not the one in front"


def test_comet_has_the_target_page_and_chrome_does_not():
    browser = FakeBrowser([chrome("New Tab", target=False), comet("Google Gemini", target=True)])
    provider(browser).complete(PROMPT)
    assert browser.used[0] == "comet"
    assert browser.launched == 0, "a browser already holding the page must not launch another"


def test_both_suitable_and_one_in_front_reuses_the_foreground_one():
    browser = FakeBrowser([chrome("Google Gemini", True, False),
                           comet("Google Gemini", True, True)])
    provider(browser).complete(PROMPT)
    assert browser.used[0] == "comet"


def test_both_suitable_and_none_in_front_asks_the_founder():
    browser = FakeBrowser([chrome("Google Gemini", True, False),
                           comet("Google Gemini", True, False)], ambiguous=True)
    founder = Founder(FounderChoiceResponse.chose("1"))
    provider(browser, interaction=founder).complete(PROMPT)

    assert len(founder.asked) == 1, "genuine ambiguity is a question, not a tiebreak"
    # `used[-1]`, not `used[0]`: both candidates are probed for whether
    # they can actually be read before the founder is troubled, so the
    # last one used is the one that did the work.
    assert browser.used[-1] == "comet"


def test_a_cancelled_browser_choice_submits_nothing():
    browser = FakeBrowser([chrome("Google Gemini", True), comet("Google Gemini", True)],
                          ambiguous=True)
    result = provider(browser, interaction=Founder(FounderChoiceResponse.cancel())).complete(PROMPT)

    assert result.ok is False
    assert browser.typed == []


# =========================================================================
# 5-6. Focus, and a browser that only looks usable
# =========================================================================


def test_nothing_is_typed_when_the_window_is_not_in_front():
    """The live failure, as an assertion.

    bring_to_front succeeding at one moment is not evidence about the
    next: measured on the founder's desktop, another application reclaimed
    the foreground about four seconds later, and the Desktop Executive
    refused to type three times running. Refusing is correct.
    """
    browser = FakeBrowser([chrome(target=True)], foreground=False)
    result = provider(browser).complete(PROMPT)

    assert result.ok is False
    assert browser.typed == [], "a stolen foreground must never produce a blind keystroke"


def test_only_one_drivable_candidate_is_not_an_ambiguity_worth_asking_about():
    """Two browsers held the page live and one threw on every read.

    That is a choice between a usable session and an unusable one, which
    is not something to interrupt the founder for -- asking is reserved
    for when they genuinely have something to decide.
    """
    browser = FakeBrowser(
        [chrome("Google Gemini", True, False), comet("Google Gemini", True, False)],
        ambiguous=True,
        pages_by_app={
            "chrome": [Page("Google Gemini", controls=[COMPOSER]), answered("Google Gemini")],
            "comet": [Page("Google Gemini", usable=False)],
        },
    )
    founder = Founder()
    result = provider(browser, interaction=founder).complete(PROMPT)

    assert founder.asked == [], "no question when only one candidate is drivable"
    assert browser.used[-1] == "chrome"
    assert result.ok is True


def test_a_browser_that_cannot_be_observed_is_not_treated_as_usable():
    """Measured live: a browser showed the target page in its title and
    threw on every accessibility read. Recognisable is not drivable."""
    browser = FakeBrowser(
        [comet("Google Gemini", True, True), chrome("Google Gemini", True, False)],
        pages_by_app={
            "comet": [Page("Google Gemini", usable=False)],
            "chrome": [Page("Google Gemini", controls=[COMPOSER]), answered("Google Gemini")],
        },
    )
    provider(browser).complete(PROMPT)
    assert "comet" in browser.used
    assert browser.used[-1] == "chrome", "an unusable candidate falls through to the next"


# =========================================================================
# 7. The page is already open
# =========================================================================


def test_an_already_open_page_is_not_navigated_again():
    browser = FakeBrowser([chrome("Google Gemini", target=True)])
    provider(browser).complete(PROMPT)

    assert browser.tabs_opened == [], "no duplicate tab"
    assert browser.navigated == [], "no duplicate navigation"


def test_no_running_browser_launches_one_and_opens_a_task_tab():
    browser = FakeBrowser([])
    provider(browser).complete(PROMPT)

    assert browser.launched == 1
    assert browser.tabs_opened == [GEMINI_WEB.url]


# =========================================================================
# 8-12. The dedicated conversation
# =========================================================================


def test_the_dedicated_conversation_already_on_screen_is_reused():
    browser = FakeBrowser([chrome(f"{TITLE} - Google Gemini", target=True)],
                          pages=[Page(f"{TITLE} - Google Gemini", controls=[COMPOSER])])
    state, title = provider(browser).open_dedicated_conversation()

    assert state == "reused_current"
    assert TITLE in title
    assert browser.clicked == [], "no search, no new chat"


def test_an_existing_dedicated_conversation_is_opened_and_verified():
    browser = FakeBrowser(
        [chrome("Google Gemini", target=True)],
        pages=[
            Page("Google Gemini", controls=["Toggle Recents", TITLE, COMPOSER]),
            Page(f"{TITLE} - Google Gemini", controls=[COMPOSER]),
        ],
    )
    browser.advance_on = {TITLE}
    state, title = provider(browser).open_dedicated_conversation()

    assert state == "reused_existing"
    assert TITLE in title
    assert "New chat" not in browser.clicked, "an existing conversation is never duplicated"


def test_two_identically_named_conversations_are_not_guessed_between():
    browser = FakeBrowser([chrome("Google Gemini", target=True)])
    browser._pages = [Page("Google Gemini", controls=["Toggle Recents"])]
    browser.observe = lambda: PageObservation(
        application="chrome", window_title="Google Gemini", foreground=True,
        elements=(PageElement(role="button", name=TITLE, is_actionable=True, x=1, y=1),
                  PageElement(role="button", name=TITLE, is_actionable=True, x=2, y=2)),
    )
    state, _title = provider(browser).open_dedicated_conversation()

    assert state == "ambiguous", "two matches is a question for the founder, not a coin toss"


def test_no_dedicated_conversation_creates_exactly_one():
    browser = FakeBrowser(
        [chrome("Google Gemini", target=True)],
        pages=[Page("Google Gemini", controls=["Toggle Recents", "New chat", COMPOSER]),
               Page("Google Gemini", controls=[COMPOSER])],
    )
    browser.advance_on = {"New chat"}
    state, _title = provider(browser).open_dedicated_conversation()

    assert state == "created"
    assert browser.clicked.count("New chat") == 1, "exactly one, never one per request"


def test_rename_reports_the_title_the_site_actually_shows():
    """Confirmed live that Gemini offers Rename. Where it does not, this
    must report failure rather than claim a name it never set."""
    # Modelled on the real page: choosing Rename opens a modal carrying an
    # edit control named "Rename this chat" -- a different control from the
    # menu item, which is a MenuItem and cannot be typed into.
    browser = FakeBrowser(
        [chrome("Google Gemini", target=True)],
        pages=[Page("Google Gemini", controls=["Open menu for conversation actions",
                                               "Rename", COMPOSER]),
               Page("Google Gemini", controls=["Rename this chat"]),
               Page(f"{TITLE} - Google Gemini", controls=[COMPOSER])],
    )
    browser.advance_on = {"Rename"}
    renamed, title, stopped_at = provider(browser).rename_conversation()

    assert renamed is True
    assert TITLE in title
    assert stopped_at == "", "a successful rename stops nowhere"


def test_a_rename_that_fails_names_the_step_it_stopped_at():
    """A bare False is undebuggable.

    This returned only a boolean, reported False twice against a live page
    whose every control had already been observed, and left no way to tell
    a missing menu from a missing dialog from a refused keystroke.
    """
    browser = FakeBrowser(
        [chrome("Google Gemini", target=True)],
        pages=[Page("Google Gemini", controls=["Open menu for conversation actions",
                                               "Rename", COMPOSER])],
    )
    renamed, _title, stopped_at = provider(browser).rename_conversation()

    assert renamed is False
    assert "Rename this chat" in stopped_at, "it must say the dialog never appeared"


def test_a_site_without_rename_never_claims_it_renamed_anything():
    site = WebAiSite("Nameless AI", "https://example.invalid/", COMPOSER,
                     page_markers=("Nameless",))
    browser = FakeBrowser([chrome("Nameless AI", target=True)])
    renamed, _title, stopped_at = provider(browser, site=site).rename_conversation()

    assert renamed is False
    assert "no rename affordance" in stopped_at, "a failure must name its step"


# =========================================================================
# 13-14. Turn ownership
# =========================================================================


def test_the_answer_is_this_turn_and_not_the_disclaimer():
    """The live false positive, pinned.

    The first new text to appear after submitting was
    "Gemini is AI and can make mistakes." A rule that takes the first new
    text returns a disclaimer instead of the answer.
    """
    browser = FakeBrowser(
        [chrome("Google Gemini", target=True)],
        pages=[Page("Google Gemini", controls=[COMPOSER]), answered("Google Gemini")],
    )
    result = provider(browser).complete(PROMPT)

    assert result.ok is True
    assert result.text == ANSWER
    assert "make mistakes" not in result.text
    assert PROMPT not in result.text, "the prompt echo is not the answer"


def test_a_second_turn_excludes_the_first_turns_answer():
    browser = FakeBrowser(
        [chrome(f"{TITLE} - Google Gemini", target=True)],
        pages=[
            Page(f"{TITLE} - Google Gemini", texts=[PROMPT, ANSWER], controls=[COMPOSER]),
            Page(f"{TITLE} - Google Gemini",
                 texts=[PROMPT, ANSWER, SECOND_PROMPT, SECOND_ANSWER], controls=[COMPOSER]),
        ],
    )
    result = provider(browser).complete(SECOND_PROMPT)

    assert result.ok is True
    assert result.text == SECOND_ANSWER
    assert ANSWER not in result.text, "the previous turn is not this turn's answer"


#: A planning prompt is enormous-in, moderate-out. The live Stage 1 run
#: submitted ~26K and got the prompt back, so the size IS the
#: reproduction, not decoration.
HUGE_PROMPT = (
    "Plan the next move for the mission.\n"
    + "\n".join(f"constraint {i}: the plan must respect obligation {i}." for i in range(700))
)
HUGE_ANSWER = '{"steps": [{"capability": "search.web", "covers": ["o1"]}]}'


def _chunked(text: str, size: int = 900) -> list[str]:
    """The page's own chunking of one long turn.

    A UIA tree does not hand back a 26K string as a single element: the
    founder's turn arrives split. Only the FIRST chunk can contain the
    first 40 characters, which is exactly why a 40-character anchor
    cannot decide ownership of the rest.
    """
    return [text[i:i + size] for i in range(0, len(text), size)]


def test_a_huge_prompt_echo_is_never_returned_as_the_answer():
    """The live Stage 1 defect, pinned.

    Every chunk after the first is prompt text that does NOT contain the
    anchor, so an anchor-only rule calls it new, substantive and
    therefore an answer -- and the planner parses the founder's own
    prompt as if Gemini had written it.
    """
    echo = _chunked(HUGE_PROMPT)
    browser = FakeBrowser(
        [chrome("Google Gemini", target=True)],
        pages=[
            Page("Google Gemini", controls=[COMPOSER]),
            Page("Google Gemini", texts=[*echo, HUGE_ANSWER], controls=[COMPOSER]),
        ],
    )
    result = provider(browser).complete(HUGE_PROMPT)

    assert result.ok is True
    assert result.text == HUGE_ANSWER
    for chunk in echo:
        assert chunk not in result.text, "a chunk of the submitted prompt came back as the answer"


def test_prompt_size_does_not_change_who_owns_the_turn():
    """The same page shape at two sizes must answer the same way."""
    outcomes = []
    for prompt, answer in ((PROMPT, ANSWER), (HUGE_PROMPT, HUGE_ANSWER)):
        browser = FakeBrowser(
            [chrome("Google Gemini", target=True)],
            pages=[
                Page("Google Gemini", controls=[COMPOSER]),
                Page("Google Gemini", texts=[*_chunked(prompt), answer], controls=[COMPOSER]),
            ],
        )
        outcomes.append(provider(browser).complete(prompt).text)

    assert outcomes == [ANSWER, HUGE_ANSWER], "ownership changed with prompt size"


def test_a_huge_prompt_with_no_answer_times_out_rather_than_echoing():
    """No answer must stay no answer.

    The failure being closed is not only "wrong text" -- it is a provider
    reporting SUCCESS while handing back the founder's own words.
    """
    browser = FakeBrowser(
        [chrome("Google Gemini", target=True)],
        pages=[Page("Google Gemini", texts=_chunked(HUGE_PROMPT), controls=[COMPOSER])],
    )
    result = provider(browser, response_timeout_seconds=2.0).complete(HUGE_PROMPT)

    assert result.ok is False, "the prompt echo was returned as a successful answer"
    assert result.outcome == "timed_out"


def test_an_answer_that_quotes_the_prompt_is_still_the_answer():
    """The adversarial direction: overlap must not become ownership.

    Containment suppresses a fragment that is ENTIRELY our own words. A
    real answer routinely restates the obligation it is answering, so it
    overlaps the prompt heavily while still being the model's own turn.
    If quoting were enough to be disowned, the repair would have traded
    one silent falsehood for another.
    """
    quoting_answer = (
        "constraint 5: the plan must respect obligation 5. "
        "This is satisfied by search.web, so the plan admits one step."
    )
    echo = _chunked(HUGE_PROMPT)
    browser = FakeBrowser(
        [chrome("Google Gemini", target=True)],
        pages=[
            Page("Google Gemini", controls=[COMPOSER]),
            Page("Google Gemini", texts=[*echo, quoting_answer], controls=[COMPOSER]),
        ],
    )
    result = provider(browser).complete(HUGE_PROMPT)

    assert result.ok is True
    assert result.text == quoting_answer


def test_a_short_answer_that_appears_inside_the_prompt_is_still_the_answer():
    """Why `_MIN_ECHO_CHARS` exists, pinned as behaviour.

    A brief reply -- "obligation 3." -- is inside almost any long prompt
    by coincidence. Disowning it on containment alone would lose real
    answers, so below the threshold containment says nothing.
    """
    short_answer = "obligation 3."
    assert TrustedWebAiProvider._normalised(short_answer) in TrustedWebAiProvider._normalised(
        HUGE_PROMPT
    ), "the fixture must actually overlap, or it proves nothing"

    browser = FakeBrowser(
        [chrome("Google Gemini", target=True)],
        pages=[
            Page("Google Gemini", controls=[COMPOSER]),
            Page(
                "Google Gemini",
                texts=[*_chunked(HUGE_PROMPT), short_answer],
                controls=[COMPOSER],
            ),
        ],
    )
    result = provider(browser).complete(HUGE_PROMPT)

    assert result.ok is True
    assert result.text == short_answer

#: Measured live on 2026-09-04, from the real UIA tree. The founder's own
#: closing line and Gemini's reply were byte-identical and adjacent:
#:
#:   <190> KALPAVRIKSHA_TURN_ONE_OK_75F6F7FD   <- our echo
#:   <191> KALPAVRIKSHA_TURN_ONE_OK_75F6F7FD   <- Gemini's answer
#:
#: No text tells them apart, because there is no difference in the text.
TOKEN = "KALPAVRIKSHA_TURN_ONE_OK_75F6F7FD"


def _quoting_prompt() -> str:
    """A prompt that names, verbatim, the answer it wants back."""
    body = "\n".join(f"constraint {i}: respect obligation {i}." for i in range(400))
    return (
        "You are being used as a reasoning provider.\n"
        f"{body}\n"
        f"Reply with exactly one line containing only this token:\n{TOKEN}\n"
    )


def test_an_answer_the_prompt_asked_for_verbatim_is_still_the_answer():
    """The live regression, pinned.

    Containment against our own outgoing text closes the echo defect and,
    alone, overshoots: we PUT the token in the prompt, so the correct
    reply is a substring of what we sent. Gemini answered perfectly and
    the provider disowned it and timed out, with the answer on screen.

    Suppressing the founder's answer is the same falsehood as returning
    their prompt, pointing the other way. Order is what separates them --
    we sent the prompt once, so it echoes once.
    """
    prompt = _quoting_prompt()
    echo = [line for line in prompt.splitlines() if line.strip()]
    browser = FakeBrowser(
        [chrome("Google Gemini", target=True)],
        pages=[
            Page("Google Gemini", controls=[COMPOSER]),
            # ...our whole turn, then Gemini's reply: the same characters.
            Page("Google Gemini", texts=[*echo, TOKEN], controls=[COMPOSER]),
        ],
    )
    result = provider(browser).complete(prompt)

    assert result.ok is True, "a perfect reply was disowned as our own words"
    assert result.text == TOKEN


def test_the_echo_is_spent_once_and_not_twice():
    """No reply must stay no reply, even now that duplicates are allowed.

    Loosening ownership is how a lane starts inventing answers, so the
    other direction is pinned in the same shape: with the trailing line
    present exactly once -- as our echo -- nothing may come back.

    This does NOT discriminate order from plain containment; both pass it,
    and `..._asked_for_verbatim_...` above is the one that does. It is
    here as the U1 guard for this lane: a truthful timeout beats a
    confident echo.
    """
    prompt = _quoting_prompt()
    echo = [line for line in prompt.splitlines() if line.strip()]
    browser = FakeBrowser(
        [chrome("Google Gemini", target=True)],
        pages=[Page("Google Gemini", texts=echo, controls=[COMPOSER])],
    )
    result = provider(browser, response_timeout_seconds=2.0).complete(prompt)

    assert result.ok is False, "our own closing line came back as the answer"
    assert result.outcome == "timed_out"

def test_no_new_response_within_the_wait_is_a_truthful_timeout():
    browser = FakeBrowser(
        [chrome("Google Gemini", target=True)],
        pages=[Page("Google Gemini", texts=[PROMPT], controls=[COMPOSER])],
    )
    result = provider(browser, response_timeout_seconds=2.0).complete(PROMPT)

    assert result.ok is False
    assert result.outcome == "timed_out"


# =========================================================================
# 15. The architecture did not move
# =========================================================================


def test_the_provider_never_reaches_the_layer_that_decides():
    """MB033 Rule 4, structurally, for the new provider."""
    import ast
    from pathlib import Path

    source = Path("src/master_agent/providers/trusted_web_ai.py").read_text(encoding="utf-8")
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    for forbidden in ("master_agent.broker", "master_agent.mission_control",
                      "master_agent.runtime", "master_agent.planner"):
        assert not any(name.startswith(forbidden) for name in imported), forbidden


def test_the_provider_defines_no_decision_making_function():
    import ast
    from pathlib import Path

    tree = ast.parse(Path("src/master_agent/providers/trusted_web_ai.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            for forbidden in ("select", "rank", "score", "choose", "prefer", "fallback"):
                assert forbidden not in node.name.lower(), f"{node.name}()"


def test_the_port_carries_no_website_knowledge():
    """No site name may be a *value* the port acts on.

    Checked over string literals rather than the whole file, because both
    modules discuss Gemini at length in their docstrings -- explaining what
    they deliberately do not know is not the same as knowing it, and a
    grep-based guard would have forced the explanation out of the code
    that most needs it.
    """
    import ast
    from pathlib import Path

    for path in ("src/master_agent/trusted_browser.py",
                 "src/master_agent/desktop/trusted_browser_adapter.py"):
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        # Identify docstrings structurally -- the first statement of a
        # module, class or function -- rather than by comparing text:
        # `ast.get_docstring` cleandoc-normalises, so the raw constant
        # never matches it and every docstring would look like a value.
        docstring_nodes = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef
                          | ast.AsyncFunctionDef):
                body = getattr(node, "body", None) or []
                if (body and isinstance(body[0], ast.Expr)
                        and isinstance(body[0].value, ast.Constant)
                        and isinstance(body[0].value.value, str)):
                    docstring_nodes.add(id(body[0].value))
        literals = [
            node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            and id(node) not in docstring_nodes
        ]
        for site in ("gemini", "chatgpt", "perplexity", "deepseek", "kimi"):
            offenders = [text for text in literals if site in text.lower()]
            assert not offenders, f"{path} carries {site} as a value: {offenders}"


def test_a_second_web_ai_service_needs_no_new_class():
    """The genericity claim, as a test rather than an assertion in prose."""
    other = WebAiSite(
        label="Example AI",
        url="https://example.invalid/chat",
        composer_name="Type your message",
        page_markers=("Example AI",),
        signed_out_markers=("Log in",),
        response_noise=("example ai can be wrong",),
    )
    browser = FakeBrowser(
        [chrome("Example AI", target=True)],
        pages=[Page("Example AI", controls=["Type your message"]),
               Page("Example AI", texts=[PROMPT, ANSWER, "Example AI can be wrong"],
                    controls=["Type your message"])],
    )
    result = provider(browser, site=other, provider_id="web.example").complete(PROMPT)

    assert result.ok is True
    assert result.text == ANSWER
    assert result.provider_id == "web.example"


def test_an_unattached_founder_port_never_guesses_a_browser():
    browser = FakeBrowser([chrome("Google Gemini", True), comet("Google Gemini", True)],
                          ambiguous=True)
    result = provider(browser, interaction=DeferredFounderInteraction()).complete(PROMPT)

    assert result.ok is False
    assert browser.typed == []


# =========================================================================
# No hidden browser preference
# =========================================================================


def _adapter(running, foreground=None, candidates=("chrome", "comet")):
    """The real adapter over a scripted window list -- no machine."""
    from master_agent.desktop.trusted_browser_adapter import DesktopTrustedBrowser

    class Windows:
        def locate_by_process(self, pids):
            app = next(iter(pids))
            wins = [{"handle": h, "title": t} for h, t in running.get(app, [])]
            return type("R", (), {"success": bool(wins),
                                  "output": {"windows": wins}, "errors": []})()

        def active(self):
            return type("R", (), {"success": foreground is not None,
                                  "output": {"handle": foreground}, "errors": []})()

    class Context:
        def refresh(self, **_kw):
            return type("Inv", (), {
                "running": staticmethod(
                    lambda app: [type("P", (), {"pid": app})()] if app in running else []
                )
            })()

    return DesktopTrustedBrowser(Context(), actions={}, windows=Windows(),
                                 candidates=candidates)


def test_neither_browser_holds_the_page_and_both_run_is_the_founders_tie():
    """The hidden default, as an assertion.

    Resolution used to fall through to the first entry of a tuple, so
    `("chrome", "comet")` silently chose Chrome with nothing observed
    justifying it. A deployment preference has no business living inside
    execution ordering.
    """
    resolution = _adapter(
        {"chrome": [(1, "New Tab - Google Chrome")], "comet": [(2, "Comet")]}
    ).resolve(("Google Gemini",))

    assert resolution.chosen is None, "a genuine tie must not be broken by tuple order"
    assert resolution.ambiguous is True
    assert {c.application for c in resolution.options} == {"chrome", "comet"}


def test_one_running_browser_is_an_observation_not_a_preference():
    resolution = _adapter({"comet": [(2, "Comet")]}).resolve(("Google Gemini",))

    assert resolution.chosen is not None
    assert resolution.chosen.application == "comet"
    assert "only one running" in resolution.reason


def test_nothing_running_and_several_configured_is_also_the_founders_tie():
    resolution = _adapter({}).resolve(("Google Gemini",))

    assert resolution.chosen is None
    assert {c.application for c in resolution.options} == {"chrome", "comet"}


def test_nothing_running_and_one_configured_needs_no_question():
    resolution = _adapter({}, candidates=("comet",)).resolve(("Google Gemini",))

    assert resolution.chosen is not None
    assert resolution.chosen.application == "comet"


def test_the_browser_showing_the_page_still_wins_over_the_one_in_front():
    resolution = _adapter(
        {"chrome": [(1, "Kalpavriksha - Google Gemini - Google Chrome")],
         "comet": [(2, "Comet")]},
        foreground=2,
    ).resolve(("Google Gemini",))

    assert resolution.chosen.application == "chrome", (
        "showing the target page outranks merely being in front"
    )


def test_no_browser_is_opened_before_one_has_been_resolved():
    browser = _adapter({})
    assert browser.ensure_available().ok is False, (
        "an unresolved browser must not be launched on a hidden default"
    )


def test_an_unreadable_browser_is_not_the_one_we_then_drive():
    """Measured live. A browser held the target page and threw on every
    accessibility read, so it was recognised and could not be driven. The
    provider proved that, and then pinned it anyway -- `candidates[0]` --
    and the attempt died on "no new-tab control was offered".

    An environment that cannot be perceived is not a usable environment.
    Nothing here prefers one browser over another: the excluded one is an
    observation made a moment earlier.
    """
    browser = FakeBrowser(
        candidates=(comet("Google Gemini", target=True),
                    chrome("New Tab", target=False)),
        # The one showing the page reads as nothing at all.
        pages_by_app={"comet": [Page("Google Gemini", controls=[])],
                      "chrome": [Page("Google Gemini", controls=[COMPOSER])]},
    )

    provider(browser).complete("plan something")

    assert browser.used, "no environment was selected at all"
    assert browser.used[-1] != "comet", (
        "the provider drove the environment it had just proven unreadable")
