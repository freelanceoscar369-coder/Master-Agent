"""Browser free-AI reasoning provider — Corrected Fallback Ladder,
Tier 3 (Gemini API → installed desktop AI → **Browser free AI**), the
final fallback, reached only once both prior tiers have failed.

Mirrors `providers/gemini.py`/`providers/desktop_app.py`'s own contract:
construction stores configuration only; every real action (opening
Chrome, navigating, typing, submitting, reading the response) happens
inside `complete()`, never at construction or registration.

**What this provider is, corrected.** It used to describe itself as
driving *"a free, no-login AI chat website"*, and for Founder Edition that
sentence was false in the way that matters: Gemini's web app shows a
sign-in wall, and a provider that believed otherwise read that wall as
terminal unavailability and gave up. What it actually does is **generate
text through an authenticated founder browser identity** -- the browser is
signed in as the founder, the way their own browser is, and staying signed
in between runs is the point rather than an accident.

**It does not own that identity.** Persistence belongs to the Browser
Environment (`environment/browser_identity.py`,
`environment/browser_session.py`): this provider names an identity and
asks for a session, exactly as it names a URL and asks for a navigation.
It knows Gemini's *page* -- which element is the composer, what a sign-in
wall looks like, where Google lists accounts -- and nothing about profile
directories.

**No second browser automation path.** This reuses the exact same
`BrowserSessionManager` and the exact same `Action` classes
(`OpenBrowserSessionAction`, `NavigateAction`, `WaitForSelectorAction`,
`TypeTextAction`, `PressKeyAction`, `ObserveBrowserAction`) the Browser
Executive and the Planner-driven Browser missions already use — the same
mechanism proven live, in this session's own Universal Autonomous Desktop
Executive mission, submitting a real prompt to `chatgpt.com` end to end.
`desktop_shell`'s own composition root already defaults every browser
session to `headless=False, channel="chrome"` for exactly this reason
(founder-visible browser use); this provider passes the same defaults
explicitly rather than relying on inherited configuration, so a visible
Chrome is this provider's own, unconditional contract — never headless,
per Section 8's explicit requirement.
"""
from __future__ import annotations

import time
from typing import Any

from master_agent.ai_infrastructure.catalog import CLOUD, REASONING, THIRD_PARTY, DECLARED, ProviderSpec
from master_agent.executor.action import Action, ExecutionResult
from master_agent.plugins.base import CapabilityManifest, ModelProvider, PluginManifest, RiskTier
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

PROVIDER_ID = "browser.free-ai"

#: Deliberately not part of the shared `ai_infrastructure.catalog.
#: PROVIDER_CATALOG` — see that module's own note on why. A composition
#: root that actually registers `BrowserFreeAiReasoningProvider` passes
#: `PROVIDER_CATALOG + (BROWSER_FREE_AI_SPEC,)` to its own `ProviderSource`
#: instead.
BROWSER_FREE_AI_SPEC = ProviderSpec(
    provider_id=PROVIDER_ID,
    label="Browser (visible Chrome, founder identity)",
    capabilities=frozenset({REASONING}),
    locality=CLOUD,
    privacy=THIRD_PARTY,
    # Deliberately the lowest declared quality in the catalogue: the
    # tier-3, last-resort fallback (Corrected Fallback Ladder mission) —
    # never meant to outrank Gemini or an installed desktop app on any
    # policy's ranking, only to be reached once both have failed.
    declared_quality=0.60,
    cost_per_call=0.0,
    latency_ms=8000.0,
    needs_credentials=False,
    # `requires_approval` stays False, matching the existing
    # `claude-desktop` entry's own precedent (also unset): the Broker's
    # `_reject()` treats `requires_approval=True` as an unconditional,
    # permanent exclusion (`broker.py:283-288`) — no granting path exists
    # in the current composition root (`AiCapabilityService(...,
    # approvals=None)`), so setting it here would make this tier
    # permanently unreachable, not merely gated. ADR-0017 Decision 7's
    # approval requirement for third-party data is real and worth
    # applying properly, but doing so needs the Permission System
    # actually wired to `approvals=` — a separate, out-of-scope
    # architectural change, not something to half-build here. Documented
    # as a known, deliberate gap.
    basis=DECLARED,
    # Corrected: this said "a free, no-login AI chat website". Gemini's web
    # app requires a signed-in Google account, so the old note was a false
    # claim about the deployment's own web rung -- and a claim the Broker
    # and the founder both read. It states the requirement now.
    #
    # What it deliberately does NOT state is whether that session is
    # authenticated *right now*: a descriptor is the canonical record of
    # what a provider IS, and "authenticated" is a fact about this minute
    # that a record written last week cannot hold. Only an observation of
    # the live page answers it (`complete()` below).
    notes=(
        "real, visible Chrome driven as an authenticated founder browser "
        "identity; requires a signed-in web session; final fallback tier only"
    ),
)
PROVIDER_VERSION = "1.1.0"
PROVIDER_LABEL = "Browser (authenticated founder identity)"


#: What an observation of the live page says about the session's
#: authentication. Five states, because collapsing any two of them loses
#: something a caller has to act on differently: "not signed in" is
#: recoverable and "Google is asking you for a password" is not something
#: Kalpavriksha may act on at all.
AUTHENTICATED = "authenticated"
SIGNED_OUT = "signed_out"
AUTHENTICATION_IN_PROGRESS = "authentication_in_progress"
AUTHENTICATION_REQUIRED = "authentication_required"
AUTHENTICATION_TIMEOUT = "authentication_timeout"

#: The founder is being asked for something only they can supply. Said
#: once, then Kalpavriksha goes back to watching.
FOUNDER_ACTION_MESSAGE = (
    "Google authentication requires your action. Complete sign-in in the "
    "Chrome window. Kalpavriksha will continue automatically once Gemini "
    "is ready."
)
NO_ACCOUNT_MESSAGE = (
    "Google is asking which account to sign in with, and none is offered "
    "yet. Complete Google sign-in in the Chrome window. Kalpavriksha will "
    "continue automatically once Gemini is ready."
)
#: Not one of the five observed page states: nothing about the page
#: changed, the founder declined. Kept distinct so the result says the
#: founder stopped this rather than that Google did.
AUTH_CANCELLED_STATE = "authentication_cancelled"
AUTH_CANCELLED = "the founder cancelled the Google account choice"
AUTH_TIMED_OUT = "Gemini was still not signed in within the bounded wait"
NO_INTERACTION_PORT = (
    "Gemini needs a Google account chosen and this deployment has no way "
    "to ask the founder"
)

#: How many account rows to look for in Google's chooser. A bound, not an
#: expectation: enumeration stops at the first row that is not there.
_MAX_ACCOUNT_OPTIONS = 8


class _Site:
    """One site's *page* knowledge -- and the only place any of it lives.

    Every selector below was read off the live page rather than guessed;
    the two that matter most are worth stating outright, because the old
    code got the second one wrong:

    `composer_selector` is present on Gemini's signed-out landing page
    too, verified live. So a visible composer is NOT proof of a signed-in
    session, and anything that treats it that way will happily type a
    founder's prompt into a page that will never answer it. Authentication
    is `composer present AND no sign-in marker`, never the composer alone.
    """

    __slots__ = (
        "account_option_selector",
        "composer_selector",
        "credential_markers",
        "identifier_selector",
        "label",
        "sign_in_control_selector",
        "sign_in_markers",
        "url",
    )

    def __init__(
        self,
        label: str,
        url: str,
        composer_selector: str,
        sign_in_markers: tuple[str, ...] = (),
        sign_in_control_selector: str = "",
        account_option_selector: str = "",
        identifier_selector: str = "",
        credential_markers: tuple[str, ...] = (),
    ):
        self.label = label
        self.url = url
        self.composer_selector = composer_selector
        self.sign_in_markers = sign_in_markers
        #: The visible control that begins sign-in. Verified live: the
        #: page also carries a *hidden* `a[aria-label="Sign in"]` that
        #: Playwright will never click, which is why this names the
        #: visible button specifically.
        self.sign_in_control_selector = sign_in_control_selector
        #: One row per already-known Google account in the chooser.
        #: Enumerated with `>> nth=`, so the same string serves both to
        #: observe a row and to click it.
        self.account_option_selector = account_option_selector
        #: Google's email field. Its presence means Google has no account
        #: to offer and is asking who the founder is -- which is founder
        #: work, never ours.
        self.identifier_selector = identifier_selector
        #: Text that means Google is asking for something Kalpavriksha
        #: must never supply. Matched case-insensitively against the
        #: accessibility tree.
        self.credential_markers = credential_markers


#: Read off the live signed-out page this session (headed Chrome, a fresh
#: dedicated identity): the composer exists while signed out, three
#: visible "Sign in" controls exist alongside one hidden anchor, and
#: clicking the visible button lands on
#: `accounts.google.com/v3/signin/identifier` carrying `#identifierId`.
_GEMINI_AUTH = {
    "sign_in_control_selector": 'button:visible:has-text("Sign in")',
    "account_option_selector": "[data-identifier]",
    "identifier_selector": "#identifierId",
    "credential_markers": (
        "enter your password",
        "password",
        "passkey",
        "2-step verification",
        "verify it",
        "authenticator",
        "security key",
        "recovery",
    ),
}


#: Tried in order — Gemini's own website first, per the founder's explicit
#: preference, falling through to a confirmed-anonymous, no-login site
#: only if Gemini's is unusable (a real sign-in wall, confirmed live:
#: gemini.google.com shows "Sign in" for an unauthenticated Playwright
#: session, so an anonymous submission there is not reliably usable).
#: `rich-textarea .ql-editor` (Gemini) and
#: `textarea[name="user-prompt"]` (Duck.ai, DuckDuckGo AI Chat) are both
#: real, stable, semantic selectors confirmed live this session — neither
#: is an auto-generated CSS-module class name, which a redeploy would
#: silently break.
CANDIDATE_SITES: tuple[_Site, ...] = (
    _Site(
        "Gemini (web)",
        "https://gemini.google.com/app",
        "rich-textarea .ql-editor",
        sign_in_markers=("Sign in",),
        **_GEMINI_AUTH,
    ),
    _Site("Duck.ai", "https://duck.ai/chat", 'textarea[name="user-prompt"]'),
)

#: Founder Edition's web rung, and the reason this provider takes a `sites`
#: argument at all.
#:
#: Duck.ai is excluded from this product by an explicit founder decision,
#: and the exclusion has to survive *enabling* the provider — otherwise
#: wiring the web tier on would quietly switch Duck.ai back on as the
#: fall-through, which is exactly what the decision forbids. Selecting the
#: site list is configuration, so it is passed in rather than cloned: one
#: provider, two deployments, no `GeminiWebProvider2`.
FOUNDER_EDITION_SITES: tuple[_Site, ...] = (
    _Site(
        "Gemini (web)",
        "https://gemini.google.com/app",
        "rich-textarea .ql-editor",
        sign_in_markers=("Sign in",),
        **_GEMINI_AUTH,
    ),
)

BROWSER_UNAVAILABLE = "the Browser Worker's dependency (Playwright) is not available"
NAVIGATE_FAILED = "could not reach the free AI chat site"
COMPOSER_NOT_FOUND = "the composer input did not appear"
SUBMIT_FAILED = "could not submit the prompt"
RESPONSE_TIMEOUT = "no response appeared within the bounded wait"
EMPTY_RESPONSE = "the site produced no meaningful response text"

_LOAD_TIMEOUT_MS = 15_000
#: How long the founder has to finish a Google sign-in before this gives
#: up and says so. Generous on purpose -- a real sign-in involves a
#: password manager, possibly a phone, and possibly a person walking back
#: to their desk -- and bounded on purpose, because a provider that waits
#: forever is a hung founder request with no explanation.
_AUTH_TIMEOUT_SECONDS = 300.0
_AUTH_POLL_INTERVAL_SECONDS = 2.0
_RESPONSE_POLL_TIMEOUT_SECONDS = 45.0
_RESPONSE_POLL_INTERVAL_SECONDS = 1.5


def _run(action_cls: type[Action], sessions: Any, **parameters: Any) -> ExecutionResult:
    action = action_cls(sessions)
    errors = action.validate(parameters)
    if errors:
        return ExecutionResult(success=False, errors=errors)
    return action.run(parameters)


class BrowserFreeAiReasoningProvider(ModelProvider):
    """A `ModelProvider` whose `complete()` operates a real, visible
    Chrome browser session against a free, no-login AI chat website."""

    CAPABILITY_NAME = "generate_text"

    def __init__(
        self,
        provider_id: str = PROVIDER_ID,
        session_id: str = "reasoning_fallback",
        sites: tuple[_Site, ...] = CANDIDATE_SITES,
        identity_id: str | None = None,
        interaction: Any = None,
        sessions: Any = None,
        identities: Any = None,
        auth_timeout_seconds: float = _AUTH_TIMEOUT_SECONDS,
    ) -> None:
        self._provider_id = provider_id
        self._session_id = session_id
        #: Which sites this deployment may drive, in order. Defaults to the
        #: full generic list so existing callers are unchanged; Founder
        #: Edition passes `FOUNDER_EDITION_SITES` to keep Duck.ai out.
        self._sites = tuple(sites)
        #: Which browser identity to sign in as, or None to stay
        #: anonymous. None is the default so that nothing that already
        #: constructs this provider silently acquires the founder's
        #: signed-in browser; a deployment opts in by naming one.
        self._identity_id = identity_id
        #: The `FounderInteraction` port. None means this deployment has
        #: no way to ask -- which is a reason to stop and say so, never a
        #: licence to pick an account on the founder's behalf.
        self._interaction = interaction
        #: An existing `BrowserSessionManager`, so a deployment that
        #: already has one does not end up with two Chromes.
        self._manager = sessions
        self._identities = identities
        self._auth_timeout_seconds = auth_timeout_seconds

    # ---- identity ---------------------------------------------------------

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name=self._provider_id,
            version=PROVIDER_VERSION,
            capabilities=[
                CapabilityManifest(
                    name=self.CAPABILITY_NAME,
                    description="Generate text via a real, visible Chrome session against a free AI chat site.",
                    risk_tier=RiskTier.REVERSIBLE_WRITE,
                )
            ],
        )

    # ---- availability -------------------------------------------------
    #
    # Not consulted by the real selection path today (see
    # `providers/desktop_app.py`'s identical note re: `GeminiProvider`'s
    # own `availability()`), implemented for completeness. Reports
    # available whenever Playwright can be imported — the actual
    # reachability of the free AI site is only known at `complete()` time,
    # the same "ask, don't probe" posture every other provider here takes.

    def availability(self) -> Availability:
        """Whether a call could be attempted right now, and what the
        founder may have to do during it.

        Three things this deliberately does NOT do.

        It does not claim the session is authenticated. Nothing here can
        know that: only an observation of the live Gemini page can, and
        making that observation means opening a browser, which is a call,
        not an availability check. `AUTHENTICATION_REQUIRED` in the detail
        is a statement about what *may* be needed, never a verdict already
        reached.

        It does not report *unavailable* when no identity has signed in
        yet. That would be the deadlock the brief names: the Broker would
        refuse to select the provider because it is unauthenticated, and
        authentication can only begin once it is selected. The honest
        shape is "executable, and able to become ready through founder
        interaction" -- so this stays reachable and says what it will ask
        for.

        It does not write anything down. A descriptor persisted last week
        saying `authenticated=true` would be exactly the eternal-truth
        claim the canonical record must never hold.
        """
        try:
            import master_agent.environment.browser_session  # noqa: F401
        except ImportError:
            return Availability(self._provider_id, False, detail=BROWSER_UNAVAILABLE)

        if self._identity_id is None:
            return Availability(
                self._provider_id, True, detail="Playwright available; anonymous session"
            )

        known = self._identity_seen_before()
        detail = (
            f"Playwright available; browser identity '{self._identity_id}' "
            + (
                # Carefully not "has signed-in state". A browser writes a
                # profile directory the moment it launches, signed in or
                # not -- observed live: a first run that never signed in
                # still left 20 entries behind. All this knows is that the
                # identity has been used before.
                "has a profile from a previous run; "
                "whether it is still signed in is verified at use"
                if known
                else f"has no profile yet ({AUTHENTICATION_REQUIRED} on first use)"
            )
        )
        return Availability(self._provider_id, True, detail=detail)

    def _identity_seen_before(self) -> bool:
        """Whether anything was ever persisted for this identity.

        A fact about the past and nothing more -- see the docstring above
        for why it is never allowed to become a claim about now.
        """
        if self._identities is None or self._identity_id is None:
            return False
        try:
            return bool(self._identities.exists(self._identity_id))
        except Exception:  # noqa: BLE001 - an unreadable store is simply "nothing known"
            return False

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
            manager = self._ensure_manager()
        except ImportError:
            return failure(self._provider_id, UNAVAILABLE, BROWSER_UNAVAILABLE,
                            latency_ms=self._elapsed_ms(started))

        opened = _run(
            self._open_session_action(), manager,
            session_id=self._session_id, headless=False, channel="chrome",
            identity_id=self._identity_id,
        )
        if not opened.success:
            return failure(self._provider_id, UNAVAILABLE, "; ".join(opened.errors) or "could not open a browser session",
                            latency_ms=self._elapsed_ms(started))

        last_error = NAVIGATE_FAILED
        for site in self._sites:
            outcome = self._try_site(manager, site, prompt, started)
            if isinstance(outcome, ProviderResult):
                self._cleanup(manager)
                return outcome
            last_error = outcome  # a site-level reason to try the next candidate

        self._cleanup(manager)
        return failure(self._provider_id, UNAVAILABLE, last_error, latency_ms=self._elapsed_ms(started))

    def _try_site(self, manager: Any, site: "_Site", prompt: str, started: float) -> "ProviderResult | str":
        """One candidate site, start to finish. Returns a `ProviderResult`
        the moment the site is genuinely unusable/succeeds/fails at
        submission — a plain string means "try the next site", never a
        final answer on its own."""
        navigated = _run(
            self._navigate_action(), manager,
            session_id=self._session_id, url=site.url, timeout_ms=_LOAD_TIMEOUT_MS,
        )
        if not navigated.success:
            return f"{site.label}: {NAVIGATE_FAILED}"

        # Authentication comes BEFORE the composer wait, for a reason found
        # against the live site: a never-signed-in profile is redirected
        # straight to Google's sign-in page, where there is no composer at
        # all. Waiting for one first meant the run died with "the composer
        # input did not appear" while the real answer was "you are not
        # signed in yet, and here is how to fix that".
        #
        # Only sites that declare what a sign-in wall looks like take this
        # path; a genuinely no-login site keeps the original order exactly.
        if site.sign_in_markers:
            state = self._auth_state(manager, site)
            if state != AUTHENTICATED:
                # The old code stopped here, calling a sign-in wall
                # terminal unavailability. It is not terminal -- it is the
                # ordinary first-run state of a browser identity nobody
                # has signed in yet, and the recovery is a sign-in.
                state = self._authenticate(manager, site)
            if state == AUTHENTICATION_TIMEOUT:
                return failure(self._provider_id, TIMED_OUT, f"{site.label}: {AUTH_TIMED_OUT}",
                                latency_ms=self._elapsed_ms(started))
            if state == AUTH_CANCELLED_STATE:
                return failure(self._provider_id, REJECTED, f"{site.label}: {AUTH_CANCELLED}",
                                latency_ms=self._elapsed_ms(started))
            if state != AUTHENTICATED:
                return failure(self._provider_id, UNAVAILABLE,
                                f"{site.label}: {self._auth_reason(state)}",
                                latency_ms=self._elapsed_ms(started))

        waited = _run(
            self._wait_for_selector_action(), manager,
            session_id=self._session_id, selector=site.composer_selector,
            state="visible", timeout_ms=_LOAD_TIMEOUT_MS,
        )
        if not waited.success:
            return f"{site.label}: {COMPOSER_NOT_FOUND}"

        # Authentication was RECOVERY for this request, not a new errand:
        # `prompt` is the founder's original text, still in hand, and it is
        # submitted below without anyone being asked to type it again.

        typed = _run(
            self._type_text_action(), manager,
            session_id=self._session_id, selector=site.composer_selector, text=prompt,
        )
        if not typed.success:
            return failure(self._provider_id, REJECTED,
                            f"{site.label}: " + ("; ".join(typed.errors) or "could not type the prompt"),
                            latency_ms=self._elapsed_ms(started))

        submitted = _run(
            self._press_key_action(), manager,
            session_id=self._session_id, key="Enter", selector=site.composer_selector,
        )
        if not submitted.success:
            return failure(self._provider_id, REJECTED, f"{site.label}: {SUBMIT_FAILED}",
                            latency_ms=self._elapsed_ms(started))

        response_text = self._await_response(manager, prompt)
        if response_text is None:
            return failure(self._provider_id, TIMED_OUT, f"{site.label}: {RESPONSE_TIMEOUT}",
                            latency_ms=self._elapsed_ms(started))
        if not response_text.strip() or response_text.strip() == prompt.strip():
            return failure(self._provider_id, MALFORMED, f"{site.label}: {EMPTY_RESPONSE}",
                            latency_ms=self._elapsed_ms(started))

        return ProviderResult(
            provider_id=self._provider_id,
            outcome=SUCCEEDED,
            response=ProviderResponse(text=response_text, model=f"{PROVIDER_LABEL}: {site.label}",
                                       latency_ms=self._elapsed_ms(started)),
            latency_ms=self._elapsed_ms(started),
            detail={"url": site.url, "site": site.label},
        )

    # ---- authentication, observed rather than assumed ------------------

    def _auth_state(self, manager: Any, site: _Site) -> str:
        """What the *live page* says right now.

        Never derived from the browser having launched, from the identity
        directory existing, or from a cookie being present -- all three can
        be true of a session Google revoked an hour ago. Positive proof is
        a genuinely usable composer with no sign-in wall around it, which
        is stricter than it sounds: Gemini's signed-out landing page
        carries the composer element too (verified live this session), so
        the marker check is what does the real work.
        """
        selectors = [site.composer_selector]
        if site.identifier_selector:
            selectors.append(site.identifier_selector)
        if site.account_option_selector:
            selectors.append(site.account_option_selector)

        observed = _run(
            self._observe_action(), manager,
            session_id=self._session_id, selectors=selectors,
            include_accessibility_tree=True,
        )
        if not observed.success or not observed.output:
            return SIGNED_OUT

        elements = {
            item.get("selector"): item
            for item in (observed.output.get("elements") or [])
        }
        tree_text = observed.output.get("accessibility_tree") or ""
        lowered = tree_text.lower()

        def visible(selector: str) -> bool:
            item = elements.get(selector)
            return bool(item and item.get("is_visible"))

        if any(marker.lower() in lowered for marker in site.credential_markers):
            # Google is asking for a password, a code or a passkey. This is
            # the one state Kalpavriksha may observe and must never act on.
            return AUTHENTICATION_REQUIRED
        if site.identifier_selector and visible(site.identifier_selector):
            return AUTHENTICATION_REQUIRED
        if site.account_option_selector and visible(site.account_option_selector):
            return AUTHENTICATION_IN_PROGRESS
        if any(marker in tree_text for marker in site.sign_in_markers):
            return SIGNED_OUT
        if visible(site.composer_selector):
            return AUTHENTICATED
        return SIGNED_OUT

    def _auth_reason(self, state: str) -> str:
        return {
            SIGNED_OUT: "Gemini is signed out and sign-in did not complete",
            AUTHENTICATION_REQUIRED: FOUNDER_ACTION_MESSAGE,
            AUTHENTICATION_IN_PROGRESS: "Google sign-in did not finish",
        }.get(state, f"Gemini is not usable: {state}")

    def _authenticate(self, manager: Any, site: _Site) -> str:
        """Sign in through the same visible Chrome, using the same Actions.

        Returns the state the page ended in. Everything a human must do
        stays a human's: this clicks Google's own controls and then
        watches.
        """
        # Clicking the site's own sign-in control is an *assist*, not the
        # authority on what happened. Two things found live on the real
        # page make that distinction load-bearing:
        #
        #   1. The composer is in the DOM well before the sign-in button
        #      renders, so the composer wait that precedes this is no
        #      evidence the button exists yet.
        #   2. Gemini redirects a never-signed-in profile to Google's
        #      sign-in page on its own. The button we were waiting for
        #      then disappears *because the site already did the thing we
        #      were about to ask for* -- and the old code read that
        #      timeout as failure and gave up one step short of the
        #      surface the founder needed to see.
        #
        # So: try the control if it shows up, ignore it if it does not,
        # and let the next observation decide. The page is the authority.
        if site.sign_in_control_selector:
            appeared = _run(
                self._wait_for_selector_action(), manager,
                session_id=self._session_id,
                selector=site.sign_in_control_selector,
                state="visible", timeout_ms=_LOAD_TIMEOUT_MS,
            )
            if appeared.success:
                self._run_click(manager, site.sign_in_control_selector)

        state = self._auth_state(manager, site)
        if state == AUTHENTICATION_IN_PROGRESS:
            chosen = self._choose_account(manager, site)
            if chosen is not None:
                return chosen
        elif state == SIGNED_OUT:
            # Nothing moved: no control, no redirect, still the signed-out
            # landing page. Waiting would only burn the founder's timeout
            # watching a page that is not going to change by itself.
            return SIGNED_OUT

        return self._wait_for_authenticated(manager, site)

    def _choose_account(self, manager: Any, site: _Site) -> str | None:
        """Google is offering accounts. Decide which -- or rather, don't.

        Returns a terminal state, or None meaning "an account was clicked,
        carry on watching".
        """
        accounts = self._discover_accounts(manager, site)
        if not accounts:
            self._notify(NO_ACCOUNT_MESSAGE)
            return None

        if len(accounts) == 1:
            # One account, and the founder authorised continuing on it.
            # Note this is *not* "pick the first of several" -- that is the
            # guess this whole path exists to refuse.
            selector, _label = accounts[0]
            self._run_click(manager, selector)
            return None

        if self._interaction is None:
            return AUTHENTICATION_REQUIRED

        from master_agent.mission_control.founder_choice import (
            ChoiceOption,
            FounderChoiceRequest,
        )

        request = FounderChoiceRequest(
            question="Which Google account should Kalpavriksha use for Gemini?",
            options=tuple(
                # The option id is the row's position, never the address:
                # the label is the only thing carrying what Google showed,
                # and it goes no further than the question itself.
                ChoiceOption(option_id=str(index), label=label or f"Account {index + 1}")
                for index, (_selector, label) in enumerate(accounts)
            ),
            context="Google is offering more than one account for this browser identity.",
            asked_by=self._provider_id,
        )
        response = self._interaction.ask_choice(request)
        if response is None or response.cancelled:
            return AUTH_CANCELLED_STATE

        try:
            index = int(response.option_id)
            selector, _label = accounts[index]
        except (TypeError, ValueError, IndexError):
            return AUTH_CANCELLED_STATE

        self._run_click(manager, selector)
        return None

    def _discover_accounts(self, manager: Any, site: _Site) -> list[tuple[str, str]]:
        """The account rows Google is *visibly* showing, in page order.

        Enumerated through the ordinary observation path -- `>> nth=` makes
        one selector string both the thing observed and the thing later
        clicked. Nothing hidden is read, no credential field is touched,
        and the labels are used for this one question and then dropped.
        """
        if not site.account_option_selector:
            return []
        found: list[tuple[str, str]] = []
        for index in range(_MAX_ACCOUNT_OPTIONS):
            selector = f"{site.account_option_selector} >> nth={index}"
            observed = _run(
                self._observe_action(), manager,
                session_id=self._session_id, selectors=[selector],
            )
            if not observed.success or not observed.output:
                break
            elements = observed.output.get("elements") or []
            if not elements or not elements[0].get("is_visible"):
                break
            found.append((selector, (elements[0].get("text") or "").strip()))
        return found

    def _wait_for_authenticated(self, manager: Any, site: _Site) -> str:
        """Watch until Gemini is usable, or the bounded wait runs out.

        The founder may be typing a password or approving a phone prompt
        while this runs. Kalpavriksha observes and says nothing further
        after the one message that told them it was their turn.
        """
        told = False
        deadline = self._now() + self._auth_timeout_seconds
        while self._now() < deadline:
            state = self._auth_state(manager, site)
            if state == AUTHENTICATED:
                return AUTHENTICATED
            if state == AUTHENTICATION_REQUIRED and not told:
                self._notify(FOUNDER_ACTION_MESSAGE)
                told = True
            self._sleep(_AUTH_POLL_INTERVAL_SECONDS)
        return AUTHENTICATION_TIMEOUT

    def _run_click(self, manager: Any, selector: str) -> bool:
        clicked = _run(
            self._click_action(), manager,
            session_id=self._session_id, selector=selector,
            timeout_ms=_LOAD_TIMEOUT_MS,
        )
        return bool(clicked.success)

    def _notify(self, message: str) -> None:
        if self._interaction is None:
            return
        try:
            self._interaction.notify(message)
        except Exception:  # noqa: BLE001 - telling the founder must never break the run
            pass

    def _sleep(self, seconds: float) -> None:
        """Overridden in tests so a bounded wait is not an actual wait."""
        time.sleep(seconds)

    def _now(self) -> float:
        """The clock the two polling loops measure their deadlines against.

        A seam for the same reason `providers/gemini.py` takes a `clock`:
        a bounded wait is a real behaviour worth testing, and testing it
        against the wall clock means either a slow suite or an untested
        branch. Deliberately not used for `complete()`'s own latency
        figure, which must stay the founder's real elapsed time.
        """
        return time.monotonic()

    # ---- steps --------------------------------------------------------

    def _await_response(self, manager: Any, prompt: str) -> str | None:
        observe_action = self._observe_action()
        deadline = self._now() + _RESPONSE_POLL_TIMEOUT_SECONDS
        while self._now() < deadline:
            self._sleep(_RESPONSE_POLL_INTERVAL_SECONDS)
            observed = _run(
                observe_action, manager,
                session_id=self._session_id, selectors=[], include_accessibility_tree=True,
            )
            if not observed.success or not observed.output:
                continue
            tree_text = observed.output.get("accessibility_tree") or ""
            if not tree_text:
                continue
            candidate = tree_text.strip()
            if candidate and prompt.strip() in candidate and len(candidate) > len(prompt) + 20:
                # The page contains our prompt plus real additional
                # content — a response has rendered. Return everything
                # after the prompt, the actual new content.
                idx = candidate.find(prompt.strip())
                after = candidate[idx + len(prompt.strip()):].strip()
                if after:
                    return after
        return None

    def _cleanup(self, manager: Any) -> None:
        try:
            _run(self._close_session_action(), manager, session_id=self._session_id)
        except Exception:  # noqa: BLE001 — cleanup is best-effort, never masks the real result
            pass

    def _ensure_manager(self):
        if self._manager is None:
            from master_agent.environment.browser_session import BrowserSessionManager
            self._manager = BrowserSessionManager(
                default_headless=False,
                default_channel="chrome",
                identities=self._identities,
            )
        return self._manager

    @staticmethod
    def _open_session_action():
        from master_agent.executor.actions.browser.open_session import OpenBrowserSessionAction
        return OpenBrowserSessionAction

    @staticmethod
    def _navigate_action():
        from master_agent.executor.actions.browser.navigate import NavigateAction
        return NavigateAction

    @staticmethod
    def _wait_for_selector_action():
        from master_agent.executor.actions.browser.wait_for_selector import WaitForSelectorAction
        return WaitForSelectorAction

    @staticmethod
    def _type_text_action():
        from master_agent.executor.actions.browser.type_text import TypeTextAction
        return TypeTextAction

    @staticmethod
    def _press_key_action():
        from master_agent.executor.actions.browser.press_key import PressKeyAction
        return PressKeyAction

    @staticmethod
    def _click_action():
        from master_agent.executor.actions.browser.click import ClickAction
        return ClickAction

    @staticmethod
    def _observe_action():
        from master_agent.executor.actions.browser.observe import ObserveBrowserAction
        return ObserveBrowserAction

    @staticmethod
    def _close_session_action():
        from master_agent.executor.actions.browser.close_session import CloseBrowserSessionAction
        return CloseBrowserSessionAction

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return (time.monotonic() - started) * 1000.0
