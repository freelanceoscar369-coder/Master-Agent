"""Founder-authenticated browser identity — what the founder observed, as
tests.

The defect this file exists for: Founder Edition opened the founder's real
installed Chrome, navigated to Gemini, and Gemini said *Sign in*. Chrome
being installed and visible was never the same thing as the founder being
signed in -- the session was an isolated `BrowserContext` with no cookies
and no storage, so every run was a first run, and the provider read the
resulting wall as terminal unavailability.

Nothing here touches a real Google account, a real password, or the
founder's own Chrome profile. Page states are scripted, so every branch --
including the ones a live run would take months to produce -- is exercised
in milliseconds.
"""
from __future__ import annotations

import pytest

from master_agent.environment.browser_identity import (
    BrowserIdentityError,
    BrowserIdentityStore,
)
from master_agent.environment.browser_session import (
    BrowserSessionError,
    BrowserSessionManager,
)
from master_agent.executor.action import ExecutionResult
from master_agent.executor.actions.browser.open_session import OpenBrowserSessionAction
from master_agent.founder_interaction import (
    DeferredFounderInteraction,
    FounderChoiceRequest,
    FounderChoiceResponse,
)
from master_agent.providers.browser_free_ai import (
    AUTHENTICATED,
    AUTHENTICATION_IN_PROGRESS,
    AUTHENTICATION_REQUIRED,
    FOUNDER_ACTION_MESSAGE,
    SIGNED_OUT,
    BrowserFreeAiReasoningProvider,
    _Site,
)

PROMPT = "Give exactly three short names for a gardening notes app, one name per line."
ANSWER = "SproutLog\nGardenMemo\nPlotPad"

COMPOSER = "rich-textarea .ql-editor"
SIGN_IN = 'button:visible:has-text("Sign in")'
ACCOUNTS = "[data-identifier]"
IDENTIFIER = "#identifierId"

SITE = _Site(
    "Gemini (web)",
    "https://gemini.google.com/app",
    COMPOSER,
    sign_in_markers=("Sign in",),
    sign_in_control_selector=SIGN_IN,
    account_option_selector=ACCOUNTS,
    identifier_selector=IDENTIFIER,
    credential_markers=("password", "passkey", "2-step verification"),
)


# =========================================================================
# A scripted page, and the Actions that read it
# =========================================================================


class Page:
    """One page state: which selectors are visible, and the tree text.

    `tree` is what an accessibility observation would return, and it is
    where the sign-in marker and any credential prompt live -- the same
    two places the real provider reads them from.
    """

    def __init__(self, visible: dict[str, str] | None = None, tree: str = "") -> None:
        self.visible = dict(visible or {})
        self.tree = tree


def signed_in(extra_tree: str = "") -> Page:
    return Page({COMPOSER: ""}, tree=f"Conversation with Gemini{extra_tree}")


def signed_out() -> Page:
    # The composer is present here on purpose. Verified on the live page:
    # Gemini's signed-out landing carries the composer element, so any test
    # that omitted it would be testing a page Google does not serve.
    return Page({COMPOSER: ""}, tree="Sign in | Sign in to save activity")


def chooser(*labels: str) -> Page:
    visible = {f"{ACCOUNTS} >> nth={i}": label for i, label in enumerate(labels)}
    visible[ACCOUNTS] = labels[0] if labels else ""
    return Page(visible, tree="Choose an account")


def password_wall() -> Page:
    return Page({}, tree="Enter your password to continue")


def identifier_wall() -> Page:
    return Page({IDENTIFIER: ""}, tree="Sign in with your Google Account")


class Browser:
    """The scripted browser the provider drives, standing in for a
    `BrowserSessionManager` and recording everything asked of it."""

    def __init__(self, *pages: Page, on_click: dict[str, Page] | None = None) -> None:
        self._pages = list(pages)
        self._on_click = dict(on_click or {})
        self.clicks: list[str] = []
        self.typed: list[tuple[str, str]] = []
        self.keys: list[str] = []
        self.opened: list[dict] = []
        self.closed: list[str] = []

    @property
    def page(self) -> Page:
        return self._pages[0]

    def advance(self) -> None:
        if len(self._pages) > 1:
            self._pages.pop(0)

    def click(self, selector: str) -> None:
        """A click either turns the current page into a named one, or moves
        the script on by one. It never truncates what follows -- the page
        Gemini shows *after* the answer arrives is still queued behind it.
        """
        self.clicks.append(selector)
        replacement = self._on_click.get(selector)
        if replacement is not None:
            self._pages[0] = replacement
        else:
            self.advance()


def _action(run):
    """Build a fake Action class around one `run(browser, params)`."""

    class Fake:
        def __init__(self, sessions):
            self.sessions = sessions

        def validate(self, parameters):
            return []

        def run(self, parameters):
            return run(self.sessions, parameters)

    return Fake


def _observe(browser: Browser, parameters) -> ExecutionResult:
    page = browser.page
    elements = [
        {
            "selector": selector,
            "is_visible": selector in page.visible,
            "text": page.visible.get(selector, ""),
            "tag_name": "DIV",
        }
        for selector in parameters.get("selectors", [])
    ]
    return ExecutionResult(
        success=True,
        output={"elements": elements, "accessibility_tree": page.tree,
                "url": "https://gemini.google.com/app", "title": "Gemini"},
    )


def _type(browser: Browser, parameters) -> ExecutionResult:
    browser.typed.append((parameters["selector"], parameters["text"]))
    return ExecutionResult(success=True, output={})


def _press(browser: Browser, parameters) -> ExecutionResult:
    browser.keys.append(parameters["key"])
    browser.advance()
    return ExecutionResult(success=True, output={})


def _click(browser: Browser, parameters) -> ExecutionResult:
    browser.click(parameters["selector"])
    return ExecutionResult(success=True, output={})


def _open(browser: Browser, parameters) -> ExecutionResult:
    browser.opened.append(dict(parameters))
    return ExecutionResult(success=True, output=dict(parameters))


def _close(browser: Browser, parameters) -> ExecutionResult:
    browser.closed.append(parameters["session_id"])
    return ExecutionResult(success=True, output={})


class Provider(BrowserFreeAiReasoningProvider):
    """The real provider, with the browser replaced and the waiting removed.

    Every decision under test -- what the page state means, whether to
    click, whether to ask, whether to type the prompt -- is the shipped
    code's. Only the six Action classes and `time.sleep` are swapped.
    """

    def __init__(self, browser: Browser, **kwargs):
        kwargs.setdefault("sites", (SITE,))
        kwargs.setdefault("sessions", browser)
        kwargs.setdefault("auth_timeout_seconds", 6.0)
        super().__init__(**kwargs)
        self.browser = browser
        self.slept = 0.0

    def _sleep(self, seconds: float) -> None:
        """Time passing, without any of it actually passing.

        The clock advances so the bounded-wait logic is genuinely
        exercised rather than skipped, and the scripted page moves on --
        which is what a founder finishing a sign-in in the other window
        looks like from in here.
        """
        self.slept += seconds
        self.browser.advance()

    def _now(self) -> float:
        return self.slept

    @staticmethod
    def _observe_action():
        return _action(_observe)

    @staticmethod
    def _click_action():
        return _action(_click)

    @staticmethod
    def _type_text_action():
        return _action(_type)

    @staticmethod
    def _press_key_action():
        return _action(_press)

    @staticmethod
    def _open_session_action():
        return _action(_open)

    @staticmethod
    def _navigate_action():
        return _action(lambda b, p: ExecutionResult(success=True, output={}))

    @staticmethod
    def _wait_for_selector_action():
        return _action(lambda b, p: ExecutionResult(success=True, output={}))

    @staticmethod
    def _close_session_action():
        return _action(_close)


class Recorder:
    """A `FounderInteraction` that answers however a test says."""

    can_ask = True

    def __init__(self, answer: FounderChoiceResponse | None = None) -> None:
        self.answer = answer or FounderChoiceResponse.cancel()
        self.asked: list[FounderChoiceRequest] = []
        self.told: list[str] = []

    def ask_choice(self, request: FounderChoiceRequest) -> FounderChoiceResponse:
        self.asked.append(request)
        return self.answer

    def notify(self, message: str) -> None:
        self.told.append(message)


def answered(browser: Browser) -> Page:
    """The page after Gemini has replied."""
    return Page({COMPOSER: ""}, tree=f"Conversation with Gemini {PROMPT} {ANSWER}")


# =========================================================================
# A. Already authenticated — nothing is asked, nothing is clicked
# =========================================================================


def test_an_authenticated_identity_submits_without_any_sign_in():
    browser = Browser(signed_in(), answered(None))
    founder = Recorder()
    result = Provider(browser, identity_id="founder", interaction=founder).complete(PROMPT)

    assert result.ok is True
    assert ANSWER.splitlines()[0] in result.text
    assert browser.clicks == [], "an authenticated session must not touch sign-in"
    assert founder.asked == [] and founder.told == []
    assert browser.typed == [(COMPOSER, PROMPT)]


def test_a_visible_composer_alone_is_not_proof_of_authentication():
    """The bug this whole mission turns on, as one assertion.

    Gemini's signed-out page carries the composer. Anything that reads a
    visible composer as "signed in" will type the founder's prompt into a
    page that can never answer it.
    """
    provider = Provider(Browser(signed_out()))
    assert provider._auth_state(provider._manager, SITE) == SIGNED_OUT

    provider = Provider(Browser(signed_in()))
    assert provider._auth_state(provider._manager, SITE) == AUTHENTICATED


# =========================================================================
# B. Signed out, exactly one account — continues on the founder's authority
# =========================================================================


def test_one_offered_account_is_selected_and_the_original_prompt_continues():
    browser = Browser(
        signed_out(),
        chooser("Onkar <onkar@example.com>"),
        on_click={f"{ACCOUNTS} >> nth=0": signed_in()},
    )
    founder = Recorder()
    provider = Provider(browser, identity_id="founder", interaction=founder)
    browser._pages.append(answered(None))

    result = provider.complete(PROMPT)

    assert founder.asked == [], "one account needs no question"
    assert f"{ACCOUNTS} >> nth=0" in browser.clicks
    assert result.ok is True
    # The point of the whole recovery: the founder never retyped anything.
    assert browser.typed == [(COMPOSER, PROMPT)]


# =========================================================================
# C. Signed out, several accounts — the founder chooses, and only that one
# =========================================================================


def test_several_accounts_ask_the_founder_and_click_only_the_chosen_one():
    browser = Browser(
        signed_out(),
        chooser("Onkar <a@example.com>", "Work <b@example.com>", "Old <c@example.com>"),
        on_click={f"{ACCOUNTS} >> nth=1": signed_in()},
    )
    founder = Recorder(FounderChoiceResponse.chose("1"))
    provider = Provider(browser, identity_id="founder", interaction=founder)
    browser._pages.append(answered(None))

    result = provider.complete(PROMPT)

    assert len(founder.asked) == 1
    request = founder.asked[0]
    assert [option.label for option in request.options] == [
        "Onkar <a@example.com>", "Work <b@example.com>", "Old <c@example.com>"
    ]
    account_clicks = [c for c in browser.clicks if c.startswith(ACCOUNTS)]
    assert account_clicks == [f"{ACCOUNTS} >> nth=1"], "only the chosen account"
    assert result.ok is True


def test_several_accounts_are_never_guessed_when_nobody_can_be_asked():
    """No interaction port is a reason to stop, not a licence to pick."""
    browser = Browser(signed_out(), chooser("A <a@example.com>", "B <b@example.com>"))
    result = Provider(browser, identity_id="founder", interaction=None).complete(PROMPT)

    assert result.ok is False
    assert [c for c in browser.clicks if c.startswith(ACCOUNTS)] == []
    assert browser.typed == []


def test_an_unattached_interaction_port_cancels_rather_than_choosing():
    port = DeferredFounderInteraction()
    response = port.ask_choice(
        FounderChoiceRequest(question="which account?", options=())
    )
    assert response.cancelled is True
    assert port.attached is False
    assert port.can_ask is False


def test_a_port_that_cannot_ask_is_not_reported_as_a_founder_cancelling():
    """"Nobody asked you" and "you said no" are different facts.

    The composition root builds the port before there is a window to ask
    in. An unattached port cancels -- correctly, since guessing is
    forbidden -- but telling the founder they cancelled a choice they were
    never offered is a lie about their own actions.
    """
    browser = Browser(signed_out(), chooser("A <a@example.com>", "B <b@example.com>"))
    port = DeferredFounderInteraction()

    result = Provider(browser, identity_id="founder", interaction=port).complete(PROMPT)

    assert result.ok is False
    assert "cancel" not in result.error.lower()
    assert FOUNDER_ACTION_MESSAGE in result.error or "action" in result.error.lower()
    assert browser.typed == []
    assert [c for c in browser.clicks if c.startswith(ACCOUNTS)] == []


# =========================================================================
# D. Several accounts, founder cancels — nothing is submitted
# =========================================================================


def test_a_cancelled_account_choice_submits_nothing_and_says_so():
    browser = Browser(signed_out(), chooser("A <a@example.com>", "B <b@example.com>"))
    founder = Recorder(FounderChoiceResponse.cancel())

    result = Provider(browser, identity_id="founder", interaction=founder).complete(PROMPT)

    assert result.ok is False
    assert "cancel" in result.error.lower()
    assert browser.typed == [], "a cancelled sign-in must not send the prompt"
    assert [c for c in browser.clicks if c.startswith(ACCOUNTS)] == []


# =========================================================================
# E. Password / MFA — the founder's alone
# =========================================================================


def test_a_password_wall_is_never_typed_into_and_the_founder_is_told_once():
    browser = Browser(password_wall(), password_wall(), password_wall(), signed_in())
    founder = Recorder()
    provider = Provider(browser, identity_id="founder", interaction=founder)
    browser._pages.append(answered(None))

    result = provider.complete(PROMPT)

    assert founder.told.count(FOUNDER_ACTION_MESSAGE) == 1, "said once, not every poll"
    # Nothing was typed until the page was genuinely usable, and then it was
    # the founder's own prompt -- never a credential.
    assert browser.typed == [(COMPOSER, PROMPT)]
    assert result.ok is True


def test_a_credential_prompt_is_reported_as_founder_action_required():
    provider = Provider(Browser(password_wall()))
    assert provider._auth_state(provider._manager, SITE) == AUTHENTICATION_REQUIRED

    provider = Provider(Browser(identifier_wall()))
    assert provider._auth_state(provider._manager, SITE) == AUTHENTICATION_REQUIRED


def test_an_account_chooser_is_authentication_in_progress():
    provider = Provider(Browser(chooser("A <a@example.com>")))
    assert provider._auth_state(provider._manager, SITE) == AUTHENTICATION_IN_PROGRESS


# =========================================================================
# F. Timeout — bounded, and truthful about it
# =========================================================================


def test_an_unfinished_sign_in_times_out_without_submitting_the_prompt():
    browser = Browser(password_wall())  # never becomes usable
    founder = Recorder()

    result = Provider(
        browser, identity_id="founder", interaction=founder, auth_timeout_seconds=0.01
    ).complete(PROMPT)

    assert result.ok is False
    assert result.outcome == "timed_out"
    assert browser.typed == [], "a timed-out sign-in must not send the prompt"


# =========================================================================
# G / H. Persistence across restart, and its expiry
# =========================================================================


def test_the_same_identity_resolves_to_the_same_directory_across_managers(tmp_path):
    store = BrowserIdentityStore(tmp_path, known={"founder": "Onkar"})

    first = store.path_for("founder")
    (first / "Local State").write_text("{}", encoding="utf-8")

    # A second run, a second store object, the same declared identity.
    again = BrowserIdentityStore(tmp_path, known={"founder": "Onkar"})
    assert again.path_for("founder") == first
    assert again.exists("founder") is True, "the profile survives the process"


def test_an_identity_that_has_never_signed_in_is_not_reported_as_known(tmp_path):
    store = BrowserIdentityStore(tmp_path, known={"founder": "Onkar"})
    assert store.exists("founder") is False
    store.path_for("founder")
    assert store.exists("founder") is False, "an empty directory is not a session"


def test_forgetting_an_identity_removes_everything_it_persisted(tmp_path):
    store = BrowserIdentityStore(tmp_path, known={"founder": "Onkar"})
    (store.path_for("founder") / "Cookies").write_text("x", encoding="utf-8")
    assert store.exists("founder") is True

    assert store.forget("founder") is True
    assert store.exists("founder") is False


def test_an_expired_session_is_observed_signed_out_rather_than_trusted(tmp_path):
    """Persisted state is not eternal authentication truth.

    The identity has a profile from a previous run -- `exists()` is True --
    and Gemini still says Sign in. The live observation wins, and the
    recovery path starts again.
    """
    store = BrowserIdentityStore(tmp_path, known={"founder": "Onkar"})
    (store.path_for("founder") / "Cookies").write_text("stale", encoding="utf-8")

    browser = Browser(
        signed_out(),
        chooser("Onkar <a@example.com>"),
        on_click={f"{ACCOUNTS} >> nth=0": signed_in()},
    )
    provider = Provider(
        browser, identity_id="founder", identities=store, interaction=Recorder()
    )
    assert store.exists("founder") is True
    assert provider._auth_state(provider._manager, SITE) == SIGNED_OUT

    browser._pages.append(answered(None))
    assert provider.complete(PROMPT).ok is True


def test_availability_never_claims_the_identity_is_authenticated(tmp_path):
    store = BrowserIdentityStore(tmp_path, known={"founder": "Onkar"})
    (store.path_for("founder") / "Cookies").write_text("x", encoding="utf-8")

    detail = BrowserFreeAiReasoningProvider(
        identity_id="founder", identities=store
    ).availability().detail

    assert "verified at use" in detail
    # A profile directory is not a session. The word that would make this a
    # standing claim must not appear.
    assert "signed-in state" not in detail
    assert "authenticated" not in detail.replace("authentication_required", "")


# =========================================================================
# I. Anonymous sessions — unchanged
# =========================================================================


def test_an_anonymous_session_is_unchanged_and_names_no_identity():
    sessions = BrowserSessionManager()
    handle = sessions.open_session("anon")
    try:
        assert handle.identity_id is None
        assert sessions.get("anon").owns_browser is False
    finally:
        sessions.close_all()


def test_naming_an_identity_without_a_configured_store_is_refused():
    sessions = BrowserSessionManager()
    with pytest.raises(BrowserSessionError, match="no browser identities"):
        sessions.open_session("s", identity_id="founder")


def test_the_provider_stays_anonymous_unless_a_deployment_names_an_identity():
    browser = Browser(signed_in(), answered(None))
    Provider(browser).complete(PROMPT)

    assert browser.opened[0]["identity_id"] is None


# =========================================================================
# J. Identity ids cannot name a directory
# =========================================================================


@pytest.mark.parametrize(
    "bad",
    [
        "../../../Google/Chrome/User Data",
        "..",
        "../founder",
        "C:/Users/DELL/AppData/Local/Google/Chrome/User Data",
        "/etc/passwd",
        "founder/Default",
        "founder\\Default",
        "Founder",   # uppercase is not a spelling of the declared id
        "",
        "a" * 33,
    ],
)
def test_a_traversal_or_absolute_path_is_never_an_identity(tmp_path, bad):
    store = BrowserIdentityStore(tmp_path)
    with pytest.raises(BrowserIdentityError):
        store.path_for(bad)


def test_an_undeclared_identity_is_refused_even_when_well_formed(tmp_path):
    store = BrowserIdentityStore(tmp_path, known={"founder": "Onkar"})
    with pytest.raises(BrowserIdentityError, match="unknown browser identity"):
        store.path_for("someone_else")


def test_the_action_refuses_a_traversal_before_it_reaches_the_filesystem():
    action = OpenBrowserSessionAction(BrowserSessionManager())
    errors = action.validate(
        {"session_id": "s", "identity_id": "../../Google/Chrome/User Data"}
    )
    assert errors and "identity_id" in errors[0]


# =========================================================================
# K. The capability schema tells the truth about the new argument
# =========================================================================


def test_the_open_session_capability_declares_the_identity_argument():
    from master_agent.capabilities.extraction import contracts_from_actions

    contract = contracts_from_actions(
        {"open_browser_session": OpenBrowserSessionAction(BrowserSessionManager())},
        "browser",
        lambda executive, local: f"{executive}.{local}",
    )[0]

    fields = {field.name: field for field in contract.inputs.fields}
    assert "identity_id" in fields
    assert fields["identity_id"].required is False
    assert fields["identity_id"].description, "an undescribed argument teaches nothing"
    assert contract.inputs.closed is True, "P0-4: no '(others may exist)' regression"


# =========================================================================
# L. Nothing about authentication is ever written down
# =========================================================================


def test_the_session_handle_carries_the_identity_id_and_nothing_from_inside_it():
    sessions = BrowserSessionManager()
    handle = sessions.open_session("anon")
    try:
        recorded = {
            "session_id": handle.session_id,
            "headless": handle.headless,
            "channel": handle.channel,
            "identity_id": handle.identity_id,
        }
    finally:
        sessions.close_all()

    assert set(recorded) == {"session_id", "headless", "channel", "identity_id"}
    assert "path" not in recorded and "cookies" not in recorded


def test_the_provider_descriptor_states_the_requirement_and_no_authentication_verdict():
    from master_agent.providers.browser_free_ai import BROWSER_FREE_AI_SPEC

    notes = BROWSER_FREE_AI_SPEC.notes
    assert "no-login" not in notes, "the corrected claim must not come back"
    assert "authenticated founder browser identity" in notes
    # A record of what the provider IS, never a claim about this minute.
    assert "authenticated forever" not in notes
    assert BROWSER_FREE_AI_SPEC.needs_credentials is False


def test_duck_ai_is_not_in_founder_edition():
    from master_agent.providers.browser_free_ai import FOUNDER_EDITION_SITES

    labels = [site.label for site in FOUNDER_EDITION_SITES]
    assert labels == ["Gemini (web)"]
    assert not any("duck" in label.lower() for label in labels)


def test_an_account_label_is_asked_about_and_not_kept(tmp_path):
    """A discovered address reaches the question and stops there."""
    browser = Browser(
        signed_out(),
        chooser("Onkar <private@example.com>", "Work <work@example.com>"),
        on_click={f"{ACCOUNTS} >> nth=0": signed_in()},
    )
    founder = Recorder(FounderChoiceResponse.chose("0"))
    store = BrowserIdentityStore(tmp_path, known={"founder": "Onkar"})
    provider = Provider(
        browser, identity_id="founder", identities=store, interaction=founder
    )
    browser._pages.append(answered(None))

    result = provider.complete(PROMPT)

    assert "private@example.com" not in str(result.as_dict())
    assert "private@example.com" not in str(result.detail)
