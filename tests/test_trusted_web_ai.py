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
        ranked = tuple(sorted(self._candidates,
                              key=lambda c: (not c.has_target_page, not c.is_foreground)))
        if self._ambiguous and len(showing) > 1:
            return BrowserResolution(None, "ambiguous", tuple(showing), ranked)
        if len(showing) == 1:
            return BrowserResolution(showing[0], "one showing", ranked=ranked)
        if len(showing) > 1:
            front = [c for c in showing if c.is_foreground]
            if len(front) == 1:
                return BrowserResolution(front[0], "foreground", ranked=ranked)
            return BrowserResolution(None, "ambiguous", tuple(showing), ranked)
        if ranked:
            return BrowserResolution(ranked[0], "reusing running", ranked=ranked)
        return BrowserResolution(None, "nothing running", (), ())

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

    def find(self, name_contains):
        if not self.page.usable:
            return None
        for name in self.page.controls:
            if name_contains in name:
                return PageElement(role="button", name=name, is_actionable=True, x=10, y=20)
        return None

    # -- acting
    def type_into(self, name_contains, text):
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
    assert browser.used[0] == "comet"


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
    browser = FakeBrowser(
        [chrome("Google Gemini", target=True)],
        pages=[Page("Google Gemini", controls=["Open menu for conversation actions",
                                               "Rename", COMPOSER]),
               Page(f"{TITLE} - Google Gemini", controls=[COMPOSER])],
    )
    renamed, title = provider(browser).rename_conversation()

    assert renamed is True
    assert TITLE in title


def test_a_site_without_rename_never_claims_it_renamed_anything():
    site = WebAiSite("Nameless AI", "https://example.invalid/", COMPOSER,
                     page_markers=("Nameless",))
    browser = FakeBrowser([chrome("Nameless AI", target=True)])
    renamed, _title = provider(browser, site=site).rename_conversation()

    assert renamed is False


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
