"""Trusted web-AI reasoning provider (Founder Edition policy).

Mission Brief 033's provider contract, executed inside the founder's own
ordinary browser through an injected `TrustedBrowserPort`.

**Why this provider exists rather than a fallback inside another one.**
Google refuses to sign in inside an automation-controlled browser --
*"This browser or app may not be secure"* -- so the Playwright-driven
`browser.free-ai` cannot authenticate a Google account, and no persistence
trick changes that. The wrong repair would have been to let that provider
notice it was signed out and quietly switch to driving the real browser.
That is a provider deciding, and MB033 Rule 4 forbids it: a provider
executes, and every attempt at a different execution path must be a fresh
decision the Broker makes and records. So this is a **separate provider**
with its own descriptor and its own availability. `browser.free-ai` keeps
failing truthfully; the Broker decides whether to try this one.

**Why one class and not one class per site.** The port knows nothing
about any website, and everything site-specific -- URL, what a sign-in
wall looks like, which element is the composer, how to tell this turn's
answer from the last one -- is a `WebAiSite` value handed in. A second web
AI service is a second value, not a second class, and needs no change to
this file, to the Desktop Executive, or to the Broker.

**What it still may not decide.** Not which provider should answer, not
whether another should be tried, and not which account to use when
several are offered -- that last one goes to the founder through the
`FounderInteraction` port, because it is theirs.
"""
from __future__ import annotations

import time
from typing import Any

from master_agent.providers.response import (
    MALFORMED,
    REJECTED,
    SUCCEEDED,
    TIMED_OUT,
    UNAVAILABLE,
    Availability,
    ProviderResponse,
    ProviderResult,
    failure,
)
from master_agent.trusted_browser import (
    ACCOUNT_CHOICE,
    FOUNDER_ACTION_REQUIRED,
    READY,
    SIGNED_OUT,
    UNKNOWN,
    PageObservation,
    TrustedBrowserUnavailable,
)

#: Founder Edition's web-AI rung. The id names the *lane*, not the site:
#: which service it drives is the `WebAiSite` it is constructed with, so a
#: deployment adding a second web AI registers a second instance with its
#: own id rather than editing this module.
TRUSTED_WEB_PROVIDER_ID = "trusted-founder-web"
PROVIDER_VERSION = "1.0.0"

BROWSER_UNAVAILABLE = "the founder's ordinary browser could not be made available"
NOT_REACHED = "the AI service page was not reached"
COMPOSER_NOT_FOUND = "the prompt composer could not be targeted"
SUBMIT_FAILED = "the prompt could not be submitted"
NO_RESPONSE = "no new response appeared within the bounded wait"
EMPTY_RESPONSE = "the service produced no substantive response text"
FOUNDER_ACTION_MESSAGE = (
    "Sign-in is needed and only you can complete it. Finish it in the "
    "browser window; Kalpavriksha will continue your request automatically "
    "once the page is usable."
)
ACCOUNT_CANCELLED = "the founder cancelled the account choice"
BROWSER_CANCELLED = "the founder cancelled the browser choice"
CANNOT_ASK = "an account must be chosen and this deployment has no way to ask the founder"

_UNSAFE_TO_ACT = "the browser window could not be confirmed, so nothing was typed"

_MAX_ACCOUNT_OPTIONS = 8


class WebAiSite:
    """One web AI service's own knowledge, and the only place it lives.

    Every field was read off the live page rather than guessed. The two
    worth calling out:

    `composer_name` is the *editable* element's accessible name. On Gemini
    that is `Enter a prompt for Gemini` (an Edit control); the visible
    words `Ask Gemini` beside it are a static label that cannot be typed
    into. Targeting the label is a silent failure that looks like success
    right up until nothing is submitted.

    `response_noise` is what must never be mistaken for an answer. Live,
    the first "new" text to appear after submitting was
    `Gemini is AI and can make mistakes.` -- a disclaimer that arrives
    with the conversation view. A response rule that accepts the first new
    text returns that instead of the answer.
    """

    __slots__ = (
        "account_option_role",
        "composer_name",
        "conversation_menu",
        "credential_markers",
        "history_toggle",
        "label",
        "new_chat",
        "page_markers",
        "rename_field",
        "rename_field_control_type",
        "rename_item",
        "response_noise",
        "response_role",
        "signed_out_markers",
        "url",
    )

    def __init__(
        self,
        label: str,
        url: str,
        composer_name: str,
        response_role: str = "text_region",
        signed_out_markers: tuple[str, ...] = (),
        credential_markers: tuple[str, ...] = (),
        account_option_role: str = "",
        response_noise: tuple[str, ...] = (),
        page_markers: tuple[str, ...] = (),
        history_toggle: str = "",
        conversation_menu: str = "",
        rename_item: str = "",
        rename_field: str = "",
        rename_field_control_type: int | None = None,
        new_chat: str = "",
    ) -> None:
        self.label = label
        self.url = url
        self.composer_name = composer_name
        #: Which observed role carries conversation text.
        self.response_role = response_role
        self.signed_out_markers = signed_out_markers
        self.credential_markers = credential_markers
        self.account_option_role = account_option_role
        self.response_noise = response_noise
        #: How a *window title* betrays that this site is already open.
        #: Cheap evidence used only to pick which browser to drive -- no
        #: accessibility read, because deciding which browser to drive
        #: must not itself require driving one.
        self.page_markers = page_markers or (label,)
        #: The conversation controls, all read off the live page. The
        #: menu's contents were confirmed rather than assumed: it offers
        #: Share, Pin, Rename, Download PDF, Export to Docs, Delete -- so
        #: rename is genuinely available here and this provider is allowed
        #: to claim a dedicated conversation was named.
        self.history_toggle = history_toggle
        self.conversation_menu = conversation_menu
        self.rename_item = rename_item
        #: The dialog's own edit control, which is NOT the menu item.
        #: Acquired read-only rather than guessed, and the distinction is
        #: the whole reason the first attempt failed: choosing Rename
        #: opens a modal named "Rename this chat" carrying an edit control
        #: of the same name, while "Rename" on its own also matches the
        #: menu item -- a MenuItem, which cannot be typed into. Targeting
        #: the shorter name is a silent no-op that looks like a rename.
        self.rename_field = rename_field
        #: 50004 is UIA's Edit. Named because the dialog, its heading and
        #: its edit box all answer to "Rename this chat", and the name
        #: alone resolves the dialog -- observed live, and the reason four
        #: rename attempts reported an unverifiable write.
        self.rename_field_control_type = rename_field_control_type
        self.new_chat = new_chat


#: Gemini, as observed live in the founder's own browser this session.
GEMINI_WEB = WebAiSite(
    label="Gemini (web)",
    url="https://gemini.google.com/app",
    composer_name="Enter a prompt for Gemini",
    response_role="text_region",
    signed_out_markers=("Sign in", "Sign in to Gemini"),
    credential_markers=(
        "enter your password", "password", "passkey", "2-step verification",
        "verify it", "authenticator", "security key", "recovery",
    ),
    account_option_role="button",
    page_markers=("Google Gemini",),
    history_toggle="Toggle Recents",
    conversation_menu="Open menu for conversation actions",
    rename_item="Rename",
    rename_field="Rename this chat",
    rename_field_control_type=50004,
    new_chat="New chat",
    response_noise=(
        "ask gemini",
        "gemini is ai and can make mistakes",
        "open menu for conversation actions",
        "show thinking",
        "just a sec",
        "thinking",
        "loading",
        # Observed live and not anticipated: Gemini sometimes answers with
        # an A/B comparison and asks which reply was better. The scaffolding
        # around that question is chrome, not an answer, and returning it
        # would hand the founder a survey instead of the names they asked
        # for.
        "which response is more helpful",
        "your choice will help",
        "choice a",
        "choice b",
        # An aria status announcement, not the reply it announces.
        "gemini replied",
    ),
)

# The provider's canonical record used to live here, and was moved to the
# composition root deliberately.
#
# A `ProviderSpec` comes from `ai_infrastructure`, and MB033 Rule 4 keeps a
# provider from importing that package at all: a provider able to see the
# layer that decides will eventually consult it, and the guard that
# enforces this caught exactly that import here. The descriptor is
# administrative data about a provider rather than part of executing one,
# so it belongs where the deployment registers it -- see
# `kalpavriksha_desktop.py`. `providers/browser_free_ai.py` keeps its own
# spec inline and is precisely why that module fails the same guard.


class TrustedWebAiProvider:
    """A `ModelProvider` whose execution environment is the founder's own
    browser, driven through an injected `TrustedBrowserPort`."""

    CAPABILITY_NAME = "generate_text"

    def __init__(
        self,
        browser: Any,
        site: WebAiSite = GEMINI_WEB,
        provider_id: str = TRUSTED_WEB_PROVIDER_ID,
        interaction: Any = None,
        conversation_title: str = "Kalpavriksha",
        auth_timeout_seconds: float = 300.0,
        response_timeout_seconds: float = 90.0,
        poll_seconds: float = 3.0,
    ) -> None:
        self._browser = browser
        self._site = site
        self._provider_id = provider_id
        self._interaction = interaction
        #: The one conversation this deployment keeps for its own work, so
        #: a founder can find what Kalpavriksha asked, and so Kalpavriksha
        #: does not litter their history with a new chat per request.
        self._conversation_title = conversation_title
        self._auth_timeout_seconds = auth_timeout_seconds
        self._response_timeout_seconds = response_timeout_seconds
        self._poll_seconds = poll_seconds

    # ---- identity -------------------------------------------------------

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def manifest(self):
        from master_agent.plugins.base import (
            CapabilityManifest,
            PluginManifest,
            RiskTier,
        )

        return PluginManifest(
            name=self._provider_id,
            version=PROVIDER_VERSION,
            capabilities=[
                CapabilityManifest(
                    name=self.CAPABILITY_NAME,
                    description=(
                        "Generate text through a web AI service in the founder's "
                        "own signed-in browser."
                    ),
                    risk_tier=RiskTier.REVERSIBLE_WRITE,
                )
            ],
        )

    def availability(self) -> Availability:
        """Executable, and honest about what it may still need.

        It never claims the session is authenticated: only an observation
        of the live page can say that, and making one means driving a
        browser, which is a call rather than an availability check.
        Equally it does not report *unavailable* merely because nobody has
        signed in -- that would be a deadlock, refusing to select the
        provider inside which signing in happens.
        """
        if self._browser is None:
            return Availability(self._provider_id, False, detail=BROWSER_UNAVAILABLE)
        return Availability(
            self._provider_id,
            True,
            detail=(
                f"drives {self._site.label} in the founder's own browser; "
                "authentication verified at use"
            ),
        )

    # ---- execution ------------------------------------------------------

    def generate(self, prompt: str, context: dict[str, Any] | None = None, **opts: Any) -> str:
        result = self.complete(prompt, context=context)
        if not result.ok:
            raise RuntimeError(result.error)
        return result.text

    def complete(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
        budget: Any = None,
        cancellation: Any = None,
    ) -> ProviderResult:
        started = time.monotonic()

        reached = self._reach_site(started)
        if isinstance(reached, ProviderResult):
            return reached

        state = self._page_state(self._browser.observe())
        if state != READY:
            state = self._reach_ready(state)
        if state == TIMED_OUT:
            return self._fail(TIMED_OUT, f"{self._site.label}: sign-in did not complete in time", started)
        if state == REJECTED:
            return self._fail(REJECTED, f"{self._site.label}: {ACCOUNT_CANCELLED}", started)
        if state != READY:
            return self._fail(UNAVAILABLE, f"{self._site.label}: {self._why(state)}", started)

        # The turn is anchored on what was on the page BEFORE this prompt.
        # Everything the response rules do is a comparison against this.
        before = self._browser.observe()
        if not self._safe_to_act(before):
            return self._fail(UNAVAILABLE, f"{self._site.label}: {_UNSAFE_TO_ACT}", started)

        typed = self._browser.type_into(self._site.composer_name, prompt)
        if not typed.ok:
            return self._fail(UNAVAILABLE, f"{self._site.label}: {COMPOSER_NOT_FOUND}: {typed.detail}", started)

        submitted = self._browser.press("enter")
        if not submitted.ok:
            return self._fail(REJECTED, f"{self._site.label}: {SUBMIT_FAILED}: {submitted.detail}", started)

        answer = self._await_answer(prompt, before)
        if answer is None:
            return self._fail(TIMED_OUT, f"{self._site.label}: {NO_RESPONSE}", started)
        if not answer.strip():
            return self._fail(MALFORMED, f"{self._site.label}: {EMPTY_RESPONSE}", started)

        return ProviderResult(
            provider_id=self._provider_id,
            outcome=SUCCEEDED,
            response=ProviderResponse(
                text=answer,
                model=f"{self._site.label} (founder browser)",
                latency_ms=self._elapsed(started),
            ),
            latency_ms=self._elapsed(started),
            detail={"site": self._site.label, "url": self._site.url},
        )

    # ---- getting to the right browser, page and conversation -------------

    def _reach_site(self, started: float) -> Any:
        """Choose a browser, get to the site, and land in this
        deployment's own conversation, reusing whatever already exists.

        Every step here is *preparation for the founder's request*, never a
        substitute for it. The prompt stays in hand throughout and is
        submitted the moment the page is usable.
        """
        resolution = self._browser.resolve(self._site.page_markers)

        if resolution.ambiguous:
            # Before asking, find out how many of them can actually be
            # driven. Live, two browsers held the page and one threw on
            # every accessibility read -- so the "ambiguity" was between a
            # usable session and an unusable one, which is not a choice
            # worth interrupting the founder for. Asking is reserved for
            # when the founder genuinely has something to decide.
            usable = [option for option in resolution.options if self._is_usable(option)]
            if len(usable) == 1:
                candidates = (usable[0],)
            else:
                chosen = self._ask_which_browser(tuple(usable) or resolution.options)
                if chosen is None:
                    return self._fail(REJECTED, BROWSER_CANCELLED, started)
                candidates = (chosen,)
        elif resolution.ordered:
            candidates = resolution.ordered
        elif resolution.chosen is not None:
            candidates = (resolution.chosen,)
        else:
            candidates = ()

        # A title match is cheap evidence; being drivable is the real test.
        # Measured live: a browser was showing the target page and threw on
        # every accessibility read, so it could be recognised and not
        # driven. Each candidate is therefore proven by observation before
        # anything is typed into it.
        for candidate in candidates:
            self._browser.use(candidate)
            if candidate.has_target_page and self._browser.observe().elements:
                return None
        if candidates:
            self._browser.use(candidates[0])

        try:
            available = self._browser.ensure_available()
        except TrustedBrowserUnavailable as exc:
            return self._fail(UNAVAILABLE, f"{BROWSER_UNAVAILABLE}: {exc}", started)
        if not available.ok:
            return self._fail(UNAVAILABLE, f"{BROWSER_UNAVAILABLE}: {available.detail}", started)

        opened = self._browser.open_task_tab(self._site.url)
        if not opened.ok:
            return self._fail(UNAVAILABLE, f"{NOT_REACHED}: {opened.detail}", started)
        return None

    def _is_usable(self, candidate: Any) -> bool:
        """Can this browser actually be read? A title is not an answer."""
        self._browser.use(candidate)
        return bool(self._browser.observe().elements)

    def _ask_which_browser(self, options: tuple[Any, ...]) -> Any:
        """Several browsers hold the page and none is in front. Which
        session the founder means is not something to infer."""
        if not self._can_ask():
            return options[0] if len(options) == 1 else None
        from master_agent.founder_interaction import ChoiceOption, FounderChoiceRequest

        response = self._interaction.ask_choice(
            FounderChoiceRequest(
                question=f"Which browser should Kalpavriksha use for {self._site.label}?",
                options=tuple(
                    ChoiceOption(
                        option_id=str(index),
                        label=f"{option.application}: {option.window_title}",
                    )
                    for index, option in enumerate(options)
                ),
                context="More than one browser already has this page open.",
                asked_by=self._provider_id,
            )
        )
        if response is None or response.cancelled:
            return None
        try:
            return options[int(response.option_id)]
        except (TypeError, ValueError, IndexError):
            return None

    def conversation_state(self) -> tuple[str, str]:
        """Is this deployment's own conversation the one on screen?

        Returns `(state, visible_title)`. The visible title is the
        authority, because it is what the site itself is displaying --
        clicking something and assuming it worked is exactly the trust
        this lane refuses to extend.
        """
        observation = self._browser.observe()
        title = observation.window_title or ""
        if self._conversation_title and self._conversation_title in title:
            return ("current", title)
        return ("absent", title)

    def open_dedicated_conversation(self) -> tuple[str, str]:
        """Reuse this deployment's conversation, or say truthfully that it
        had to be created.

        The order is the founder's and it matters: confirm what is already
        on screen, then search the visible history, and only then create --
        so a new chat is not spawned on every single request.
        """
        state, title = self.conversation_state()
        if state == "current":
            return ("reused_current", title)

        if self._site.history_toggle:
            toggle = self._browser.find(self._site.history_toggle)
            if toggle is not None:
                self._browser.click(toggle)

        matches = [
            element
            for element in self._browser.observe().elements
            if (element.name or "").strip() == self._conversation_title
        ]
        if len(matches) == 1:
            self._browser.click(matches[0])
            state, title = self.conversation_state()
            # The click proves nothing. The title after it does.
            return ("reused_existing", title) if state == "current" else ("open_failed", title)
        if len(matches) > 1:
            return ("ambiguous", title)

        if self._site.new_chat:
            fresh = self._browser.find(self._site.new_chat)
            if fresh is not None:
                self._browser.click(fresh)
        return ("created", self._browser.observe().window_title or "")

    def rename_conversation(self) -> tuple[bool, str, str]:
        """Name this deployment's conversation, and report WHICH STEP
        stopped it when it does not work.

        Returns `(renamed, visible_title, stopped_at)`.

        The third value is the point of this signature. This returned a
        bare boolean before, and it reported False twice in a row against
        a live page whose every control had already been observed -- which
        left no way to tell a missing menu from a missing dialog from a
        refused keystroke. A step that cannot say where it stopped cannot
        be debugged without guessing, and guessing at this page is the
        habit that produced three wrong answers already.

        Each step below therefore states what it expects to observe, and
        names itself when that expectation is not met. That is the same
        shape a stored procedure needs, arrived at from the debugging need
        rather than imported for its own sake.
        """
        def title() -> str:
            return self._browser.observe().window_title or ""

        if not (self._site.conversation_menu and self._site.rename_item):
            return (False, title(), "site declares no rename affordance")

        menu = self._browser.find(self._site.conversation_menu)
        if menu is None:
            return (False, title(), "conversation menu not found")
        if not self._browser.click(menu).ok:
            return (False, title(), "conversation menu would not open")

        item = self._browser.find(self._site.rename_item)
        if item is None:
            self._browser.press("escape")
            return (False, title(), "no rename item in the opened menu")
        if not self._browser.click(item).ok:
            self._browser.press("escape")
            return (False, title(), "rename item would not activate")

        # The dialog's edit control, NOT the menu item -- acquired
        # read-only rather than guessed, because "Rename" matches both and
        # only one of them can be typed into.
        target = self._site.rename_field or self._site.rename_item
        kind = self._site.rename_field_control_type
        if self._browser.find(target, kind) is None:
            self._browser.press("escape")
            return (False, title(), f"rename dialog never showed {target!r}")

        typed = self._browser.type_into(target, self._conversation_title, kind)
        if not typed.ok:
            self._browser.press("escape")
            return (False, title(), f"could not type the new name: {typed.detail}")

        if not self._browser.press("enter").ok:
            return (False, title(), "could not commit the new name")

        visible = title()
        if self._conversation_title in visible:
            return (True, visible, "")
        # The site is the authority on whether it renamed anything. It says
        # no, so this says no -- and says what it is showing instead.
        return (False, visible, "the site still shows a different title")

    # ---- page state -----------------------------------------------------

    def _page_state(self, observation: PageObservation) -> str:
        """What the live page says. Never inferred from the browser having
        opened, and never from a composer merely existing -- proven live
        on the Playwright lane, where a signed-out landing page carried the
        composer element too."""
        texts = observation.texts()
        if not texts:
            return UNKNOWN
        lowered = " | ".join(texts).lower()

        if any(marker.lower() in lowered for marker in self._site.credential_markers):
            return FOUNDER_ACTION_REQUIRED
        if self._account_options(observation):
            return ACCOUNT_CHOICE
        if any(marker in text for text in texts for marker in self._site.signed_out_markers):
            return SIGNED_OUT
        if self._browser.find(self._site.composer_name) is not None:
            return READY
        return UNKNOWN

    def _why(self, state: str) -> str:
        return {
            SIGNED_OUT: "the service is signed out and sign-in did not complete",
            FOUNDER_ACTION_REQUIRED: FOUNDER_ACTION_MESSAGE,
            ACCOUNT_CHOICE: CANNOT_ASK,
            UNKNOWN: "the page could not be confirmed as usable",
        }.get(state, f"the page is not usable: {state}")

    def _safe_to_act(self, observation: PageObservation) -> bool:
        """Right application, expected page -- checked here; right window
        in front -- checked by the act itself.

        The split is not laziness, it is what the live desktop forced.
        Requiring foreground from *this* observation made acting
        impossible: another application reclaims the foreground within
        seconds, so by the time the check passed and the type began it was
        false again, and the run died having never typed anything on a
        page that was perfectly usable.

        The invariant is not weakened, it is moved to where it can hold.
        `type_into` takes the foreground and types as one operation and the
        Desktop Executive refuses the keystroke unless the window is
        confirmed in front at that instant -- which is a stronger guarantee
        than any check made beforehand could give.
        """
        if not observation.application:
            return False
        return self._browser.find(self._site.composer_name) is not None

    # ---- accounts, which are the founder's call --------------------------

    def _account_options(self, observation: PageObservation) -> list[Any]:
        if not self._site.account_option_role:
            return []
        return [
            element
            for element in observation.named(self._site.account_option_role)
            if element.is_actionable and self._looks_like_account(element.name)
        ][:_MAX_ACCOUNT_OPTIONS]

    @staticmethod
    def _looks_like_account(name: str) -> bool:
        lowered = (name or "").lower()
        return lowered.startswith("open ") and "profile" in lowered

    def _resolve_account(self, observation: PageObservation) -> str:
        """One offered account continues; several go to the founder.

        Never first, never list order, never name similarity -- observed
        live, this browser offered three profiles and *two carried the same
        person's name*, so every one of those heuristics would have picked
        wrong with full confidence.
        """
        options = self._account_options(observation)
        if not options:
            self._notify(FOUNDER_ACTION_MESSAGE)
            return FOUNDER_ACTION_REQUIRED

        if len(options) == 1:
            self._browser.click(options[0])
            return UNKNOWN  # observe again; the click proves nothing by itself

        if not self._can_ask():
            self._notify(FOUNDER_ACTION_MESSAGE)
            return FOUNDER_ACTION_REQUIRED

        from master_agent.founder_interaction import ChoiceOption, FounderChoiceRequest

        response = self._interaction.ask_choice(
            FounderChoiceRequest(
                question=f"Which account should Kalpavriksha use for {self._site.label}?",
                options=tuple(
                    ChoiceOption(option_id=str(index), label=option.name)
                    for index, option in enumerate(options)
                ),
                context="More than one account is being offered.",
                asked_by=self._provider_id,
            )
        )
        if response is None or response.cancelled:
            return REJECTED
        try:
            chosen = options[int(response.option_id)]
        except (TypeError, ValueError, IndexError):
            return REJECTED
        self._browser.click(chosen)
        return UNKNOWN

    # ---- getting to a usable page ---------------------------------------

    def _reach_ready(self, state: str) -> str:
        """Watch, and help only where helping is ours to do.

        Kalpavriksha never types a password, a code or a passkey. When the
        service asks for one it says so once and goes back to watching,
        because the founder finishing a sign-in in their own browser is
        exactly the recovery -- and the original request is still in hand
        for when they do.
        """
        told = False
        deadline = self._now() + self._auth_timeout_seconds
        while self._now() < deadline:
            if state == ACCOUNT_CHOICE:
                outcome = self._resolve_account(self._browser.observe())
                if outcome in (REJECTED,):
                    return REJECTED
            elif state == FOUNDER_ACTION_REQUIRED and not told:
                self._notify(FOUNDER_ACTION_MESSAGE)
                told = True

            self._sleep(self._poll_seconds)
            state = self._page_state(self._browser.observe())
            if state == READY:
                return READY
        return TIMED_OUT

    # ---- the answer, and proving it belongs to this turn -----------------

    def _await_answer(self, prompt: str, before: PageObservation) -> str | None:
        """Return only text that belongs to THIS turn.

        Three things must hold before anything is returned: the prompt is
        visible on the page (which anchors the turn), the text was not
        there beforehand, and it is not the service's own furniture. Each
        was earned live -- the first "new" text to appear after submitting
        was a disclaimer, and the page also carries the founder's entire
        conversation history, none of which is this turn's answer.
        """
        seen = set(before.texts())
        anchor = prompt.strip()[:40]
        deadline = self._now() + self._response_timeout_seconds

        while self._now() < deadline:
            self._sleep(self._poll_seconds)
            observation = self._browser.observe()
            texts = [
                text for text in self._conversation_texts(observation)
                if text not in seen
            ]
            if not any(anchor in text for text in self._conversation_texts(observation)):
                continue  # our own prompt is not on the page yet
            answers = [text for text in texts if self._is_answer(text, anchor)]
            if answers:
                return "\n".join(answers).strip()
        return None

    def _conversation_texts(self, observation: PageObservation) -> list[str]:
        return [
            element.name.strip()
            for element in observation.named(self._site.response_role)
            if (element.name or "").strip()
        ]

    def _is_answer(self, text: str, anchor: str) -> bool:
        if anchor and anchor in text:
            return False  # the prompt echo is not the answer
        lowered = text.strip().lower()
        return not any(lowered.startswith(noise) for noise in self._site.response_noise)

    # ---- small helpers ---------------------------------------------------

    def _can_ask(self) -> bool:
        if self._interaction is None:
            return False
        return bool(getattr(self._interaction, "can_ask", True))

    def _notify(self, message: str) -> None:
        if self._interaction is None:
            return
        try:
            self._interaction.notify(message)
        except Exception as exc:  # noqa: BLE001 - see below
            # Swallowed deliberately and without logging: this runs while
            # the founder is mid sign-in, and a surface that fails to
            # display a courtesy message must not turn their working
            # authentication into a failed reasoning request.
            _ = exc

    def _fail(self, outcome: str, message: str, started: float) -> ProviderResult:
        return failure(self._provider_id, outcome, message, latency_ms=self._elapsed(started))

    def _sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def _now(self) -> float:
        return time.monotonic()

    @staticmethod
    def _elapsed(started: float) -> float:
        return (time.monotonic() - started) * 1000.0
