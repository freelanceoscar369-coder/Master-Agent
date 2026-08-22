"""Browser free-AI reasoning provider — Corrected Fallback Ladder,
Tier 3 (Gemini API → installed desktop AI → **Browser free AI**), the
final fallback, reached only once both prior tiers have failed.

Mirrors `providers/gemini.py`/`providers/desktop_app.py`'s own contract:
construction stores configuration only; every real action (opening
Chrome, navigating, typing, submitting, reading the response) happens
inside `complete()`, never at construction or registration.

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
    label="Browser (free AI chat, visible Chrome)",
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
    notes="real, visible Chrome; a free, no-login AI chat website; final fallback tier only",
)
PROVIDER_VERSION = "1.0.0"
PROVIDER_LABEL = "Browser (free AI chat)"


class _Site:
    __slots__ = ("label", "url", "composer_selector", "sign_in_markers")

    def __init__(self, label: str, url: str, composer_selector: str, sign_in_markers: tuple[str, ...] = ()):
        self.label = label
        self.url = url
        self.composer_selector = composer_selector
        self.sign_in_markers = sign_in_markers


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
    _Site("Gemini (web)", "https://gemini.google.com/app", "rich-textarea .ql-editor", sign_in_markers=("Sign in",)),
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
    _Site("Gemini (web)", "https://gemini.google.com/app", "rich-textarea .ql-editor", sign_in_markers=("Sign in",)),
)

BROWSER_UNAVAILABLE = "the Browser Worker's dependency (Playwright) is not available"
NAVIGATE_FAILED = "could not reach the free AI chat site"
COMPOSER_NOT_FOUND = "the composer input did not appear"
SUBMIT_FAILED = "could not submit the prompt"
RESPONSE_TIMEOUT = "no response appeared within the bounded wait"
EMPTY_RESPONSE = "the site produced no meaningful response text"

_LOAD_TIMEOUT_MS = 15_000
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
    ) -> None:
        self._provider_id = provider_id
        self._session_id = session_id
        #: Which sites this deployment may drive, in order. Defaults to the
        #: full generic list so existing callers are unchanged; Founder
        #: Edition passes `FOUNDER_EDITION_SITES` to keep Duck.ai out.
        self._sites = tuple(sites)
        self._manager = None  # never constructed until complete() — see module docstring

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
        try:
            import master_agent.environment.browser_session  # noqa: F401
        except ImportError:
            return Availability(self._provider_id, False, detail=BROWSER_UNAVAILABLE)
        return Availability(self._provider_id, True, detail="Playwright available")

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

        waited = _run(
            self._wait_for_selector_action(), manager,
            session_id=self._session_id, selector=site.composer_selector,
            state="visible", timeout_ms=_LOAD_TIMEOUT_MS,
        )
        if not waited.success:
            return f"{site.label}: {COMPOSER_NOT_FOUND}"

        if site.sign_in_markers and self._looks_signed_out(manager, site):
            return f"{site.label}: sign-in required for this session, not usable anonymously"

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

    def _looks_signed_out(self, manager: Any, site: "_Site") -> bool:
        observed = _run(
            self._observe_action(), manager,
            session_id=self._session_id, selectors=[], include_accessibility_tree=True,
        )
        if not observed.success or not observed.output:
            return False
        tree_text = observed.output.get("accessibility_tree") or ""
        return any(marker in tree_text for marker in site.sign_in_markers)

    # ---- steps --------------------------------------------------------

    def _await_response(self, manager: Any, prompt: str) -> str | None:
        observe_action = self._observe_action()
        deadline = time.monotonic() + _RESPONSE_POLL_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            time.sleep(_RESPONSE_POLL_INTERVAL_SECONDS)
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
            self._manager = BrowserSessionManager(default_headless=False, default_channel="chrome")
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
