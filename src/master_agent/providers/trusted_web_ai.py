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

from master_agent.ai_infrastructure.catalog import (
    CLOUD,
    DECLARED,
    REASONING,
    THIRD_PARTY,
    ProviderSpec,
)
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
        "credential_markers",
        "label",
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
    response_noise=(
        "ask gemini",
        "gemini is ai and can make mistakes",
        "open menu for conversation actions",
        "show thinking",
        "just a sec",
        "thinking",
        "loading",
    ),
)

#: The provider's canonical record. It states that an authenticated
#: browser session is required and states NO verdict about whether one
#: exists -- that is a fact about this minute, and a record written last
#: week cannot hold it.
TRUSTED_WEB_SPEC = ProviderSpec(
    provider_id=TRUSTED_WEB_PROVIDER_ID,
    label="Web AI in the founder's own browser",
    capabilities=frozenset({REASONING}),
    locality=CLOUD,
    privacy=THIRD_PARTY,
    declared_quality=0.72,
    cost_per_call=0.0,
    latency_ms=12000.0,
    needs_credentials=False,
    basis=DECLARED,
    notes=(
        "drives the founder's ordinary installed browser through the Desktop "
        "Executive; uses the session they are already signed into; requires a "
        "usable authenticated page, verified at use"
    ),
)


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
        auth_timeout_seconds: float = 300.0,
        response_timeout_seconds: float = 90.0,
        poll_seconds: float = 3.0,
    ) -> None:
        self._browser = browser
        self._site = site
        self._provider_id = provider_id
        self._interaction = interaction
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

        try:
            available = self._browser.ensure_available()
        except TrustedBrowserUnavailable as exc:
            return self._fail(UNAVAILABLE, f"{BROWSER_UNAVAILABLE}: {exc}", started)
        if not available.ok:
            return self._fail(UNAVAILABLE, f"{BROWSER_UNAVAILABLE}: {available.detail}", started)

        opened = self._browser.open_task_tab(self._site.url)
        if not opened.ok:
            return self._fail(UNAVAILABLE, f"{NOT_REACHED}: {opened.detail}", started)

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
        """Right application, right window in front, expected page.

        All three, every time, from a fresh observation. Anything less is
        typing hopefully into whatever happens to be on screen -- which on
        a real desktop is another person's window.
        """
        if not observation.foreground:
            return False
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
