"""Desktop AI application reasoning provider — Corrected Fallback Ladder,
Tier 2 (Gemini API → **installed desktop AI** → Browser free AI).

Mirrors `providers/gemini.py`'s own shape exactly, per that module's own
stated discipline: **it executes, it never decides.** Construction stores
only identity/configuration — no discovery, no launch, no window search,
no UIA probe happens until `complete()` is actually called, the same
contract `GeminiProvider.__init__` already holds (no network call at
construction) and `BrowserSessionManager.__init__` already holds (no
browser launch at construction). This is what keeps a desktop provider's
mere *registration* free of any boot/launch domino effect — confirmed by
this session's own dependency-impact audit
(`docs/audits/DESKTOP_REASONING_DEPENDENCY_IMPACT.md`).

**One provider per discovered desktop AI application, not one provider
that special-cases several.** `build_desktop_providers()` reads the
already-declarative `ai_infrastructure.catalog.PROVIDER_CATALOG` (the
same catalogue `claude-desktop` was already declared in) and constructs
one `DesktopAppReasoningProvider` per `locality == DESKTOP` entry — so
adding a fourth or fifth desktop AI application to the catalogue is
exactly the one-entry change `desktop/catalog.py`'s own docstring already
promises, never a new branch in this file.

**No second automation framework.** `complete()` composes the existing,
already-proven Desktop Executive primitives directly — the same
`DesktopContext`, `Win32WindowBackend`, `UiaAutomationBridge`, and
`KeyboardController` this session's prior missions already built and
verified live against Claude Desktop and ChatGPT Desktop — rather than
going through the `Action`/capability-dispatch layer (which requires a
`desktop/catalog.py` entry and a Planner-issued mission). A provider
calling the same underlying mechanism the Actions are themselves built
from is reuse, not a parallel implementation.
"""
from __future__ import annotations

import time
from typing import Any

from master_agent.ai_infrastructure.catalog import DESKTOP, PROVIDER_CATALOG, ProviderSpec, is_coding_agent
from master_agent.desktop.actions import DesktopContext
from master_agent.desktop.execution.keyboard import KeyboardController
from master_agent.desktop.execution.mouse import MouseController
from master_agent.desktop.execution.text_control import (
    ClassicControlResolver,
    ControlNotFound,
    Win32ChildEnumBackend,
    classify_window,
)
from master_agent.desktop.execution.uia_control import (
    ResponseTurn,
    UiaAutomationBridge,
    UiaTargetNotFound,
    UiaUnavailable,
    _normalize_whitespace,
)
from master_agent.desktop.execution.win32_backends import Win32WindowBackend
from master_agent.plugins.base import CapabilityManifest, ModelProvider, PluginManifest, RiskTier
from master_agent.providers.reasoning_session import ReasoningSessionManager
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

PROVIDER_VERSION = "1.0.0"

NOT_INSTALLED = "not installed on this machine"
NO_LAUNCH_TARGET = "installed but no usable launch target was discovered"
LAUNCH_FAILED = "the application did not report a real, visible window"
COMPOSER_NOT_FOUND = "no semantic composer target was found (classic control or UIA element)"
WRITE_UNVERIFIED = "typed into the composer but could not verify the text landed"
SUBMIT_UNVERIFIED = (
    "pressed Enter and tried a discoverable Send control, but neither "
    "produced any visible sign the prompt was actually submitted"
)
RESPONSE_TIMEOUT = "no response appeared within the bounded wait"
EMPTY_RESPONSE = "the application produced no meaningful response text"
SERVICE_NOTICE = "the application answered with a service notice, not an answer"

#: What a desktop AI app says INSTEAD of answering.
#:
#: These apps put capacity, plan and sign-in messages in the same place
#: the reply appears, so a scraper reads them exactly as it reads an
#: answer. Measured live: asked to identify action RPGs from a page of
#: store listings, one returned
#:
#:     "High demand. Switched to K2.6 Instant for speed. Upgrade to use
#:      K2.6 Thinking."
#:
#: -- and `SUCCEEDED` carried it onward as the reasoning result.
#:
#: Kept here because this adapter is the only thing that knows what its
#: own applications say. The generic contract already has the right word
#: for it (`UNAVAILABLE`), and this file already refuses two other fake
#: successes -- an empty reply and an echoed prompt -- for the same
#: reason.
#:
#: SHAPES, not sentences. Nothing matches one product's wording; they
#: match the kinds of thing a service says about itself.
_SERVICE_NOTICE_MARKERS: tuple[str, ...] = (
    "high demand",
    "at capacity",
    "capacity limit",
    "rate limit",
    "too many requests",
    "try again later",
    "temporarily unavailable",
    "upgrade to",
    "upgrade your plan",
    "usage limit",
    "quota",
    "please sign in",
    "log in to continue",
)

#: A service notice is a BANNER. An answer to a real question is not
#: this short, and requiring both conditions is what stops a genuine
#: reply that happens to mention "quota" from being thrown away -- a
#: partial answer is still the founder's, and Verification is what
#: judges whether it was enough.
MAX_SERVICE_NOTICE_CHARS = 400


def _is_service_notice(text: str) -> bool:
    """Did the application talk about itself instead of answering?"""
    body = (text or "").strip()
    if not body or len(body) > MAX_SERVICE_NOTICE_CHARS:
        return False
    lowered = body.lower()
    return any(marker in lowered for marker in _SERVICE_NOTICE_MARKERS)
AUTONOMOUS_REASONING_UNSAFE = "AUTONOMOUS_REASONING_UNSAFE"
CODING_AGENT_NOT_A_REASONING_PROVIDER = (
    "CODING_AGENT_NOT_A_REASONING_PROVIDER: this identity is a coding tool, "
    "never a reasoning provider, regardless of installation state"
)

#: Bounded — Section 6's own rule: "do not retry indefinitely... stop as
#: soon as a verified reasoning result is obtained." This governs one
#: provider's own internal wait for one response, not cross-provider
#: fallback (that is `TieredPromptRunner`'s job, one layer up).
#:
#: `_await_response()` requires the same candidate's text to read
#: identically across `_RESPONSE_STABILITY_POLLS` *consecutive* polls
#: before accepting it — the generic fix for a real, live-found
#: false-positive: a transient "ChatGPT is responding"/"Reconnecting..."
#: status string is itself content that did not exist before submission,
#: so `find_new_content()` alone would happily return it mid-generation.
#: Requiring stability across one full poll interval is a structural way
#: to tell "a response is still streaming in" from "the response has
#: settled" without matching any application's specific wording.
#:
#: Two consecutive matches was tried first and found live, against
#: ChatGPT Desktop, to still accept a genuinely truncated mid-stream
#: read (`"KALPAVRIKSHA_"` instead of the real, complete
#: `"KALPAVRIKSHA_CHATGPT_FINAL_OK"`) — a real LLM's own token cadence
#: can pause for a full poll interval without having actually finished.
#: Three consecutive matches (roughly 3 poll intervals of true silence)
#: gives meaningfully more margin against that same coincidence without
#: turning this into an unbounded wait.
#: Raised from 3 once the reply became a RECONSTRUCTION rather than a
#: single region. Three polls is 4.5 seconds of no change, which is ample
#: for one region that either exists or does not, and too short for a
#: multi-line answer whose lines arrive as separate elements: measured
#: live on the founder's own acceptance prompt, a run settled at
#:
#:     GardenLog
#:     SproutNote
#:
#: and returned two names of three, because the pause before the third
#: line exceeded the window. Five polls is 7.5 seconds. It is still a
#: bounded settle rather than a guess about any application's wording,
#: and it is still the *whole* reconstruction being compared -- never one
#: child that happens to be stable.
_RESPONSE_STABILITY_POLLS = 5
_RESPONSE_POLL_TIMEOUT_SECONDS = 45.0
_RESPONSE_POLL_INTERVAL_SECONDS = 1.5
_LAUNCH_TIMEOUT_SECONDS = 30.0
#: See its own use, below, in `complete()`.
_POST_ESTABLISH_SETTLE_SECONDS = 0.6

#: Generic vocabulary for a visible Send/submit control — searched only
#: when Enter does not visibly submit anything, per the mission's own
#: explicit instruction: "do not immediately assume Enter is the
#: universal submit mechanism." Not one application's own wording, the
#: same discipline `reasoning_session.py`'s own `NEW_SESSION_VOCABULARY`
#: already established for the identical kind of judgment call.
SEND_VOCABULARY = ("send", "submit", "send message")
#: Bounded retry/backoff for confirming a submit action actually did
#: something — the same shape `_verify_readback()`/`_verify_cleared()`
#: already use. A genuine submit either clears the composer or starts
#: replacing its content; the composer's own state is the fastest signal
#: available, well before a full response has arrived.
_SUBMIT_VERIFY_ATTEMPTS = 4
_SUBMIT_VERIFY_DELAY_SECONDS = 0.5


class DesktopAppReasoningProvider(ModelProvider):
    """A `ModelProvider` whose `complete()` operates one real, installed
    desktop AI application via the Desktop Executive.

    `spec.inventory_key` is the join back to `desktop/catalog.py` — the
    exact mechanism `ai_infrastructure/profiles.py` already documents
    ("the join to `desktop/catalog.py`"), reused, not reinvented.
    """

    CAPABILITY_NAME = "generate_text"

    def __init__(
        self,
        spec: ProviderSpec,
        context: DesktopContext,
        composer_name_hint: str | None = None,
    ) -> None:
        self._spec = spec
        self._context = context
        self._composer_hint = composer_name_hint
        self._uia = UiaAutomationBridge()
        self._windows = Win32WindowBackend()
        self._mouse = MouseController()
        self._sessions = ReasoningSessionManager(self._uia, self._mouse)

    # ---- identity ---------------------------------------------------------

    @property
    def provider_id(self) -> str:
        return self._spec.provider_id

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name=self._spec.provider_id,
            version=PROVIDER_VERSION,
            capabilities=[
                CapabilityManifest(
                    name=self.CAPABILITY_NAME,
                    description=f"Generate text with {self._spec.label} (installed desktop application).",
                    risk_tier=RiskTier.REVERSIBLE_WRITE,
                )
            ],
        )

    # ---- availability -------------------------------------------------
    #
    # Not consulted by the real selection path today (`ProviderSource`
    # computes `ProviderProfile.available` itself, from the cached
    # inventory — confirmed the same is already true of
    # `GeminiProvider.availability()`), implemented anyway for interface
    # completeness and so a caller that *does* ask gets a real, honest
    # answer rather than a stub. Reads the **cached** inventory only —
    # never triggers a scan, matching `ai_infrastructure/profiles.py`'s
    # own "handed facts, never goes looking" discipline.

    def availability(self) -> Availability:
        if is_coding_agent(self._spec):
            return Availability(
                self._spec.provider_id, False, detail=CODING_AGENT_NOT_A_REASONING_PROVIDER,
            )
        if self._spec.autonomous_reasoning_unsafe_reason is not None:
            return Availability(
                self._spec.provider_id, False,
                detail=f"{AUTONOMOUS_REASONING_UNSAFE}: {self._spec.autonomous_reasoning_unsafe_reason}",
            )
        inventory = self._context.cached
        if inventory is None:
            return Availability(self._spec.provider_id, False, detail="no machine scan has run yet")
        app = self._resolve_app_record(inventory)
        if app is None or not app.launchable:
            return Availability(self._spec.provider_id, False, detail=NOT_INSTALLED)
        return Availability(self._spec.provider_id, True, detail=app.install_source)

    def _resolve_app_record(self, inventory):
        if self._spec.inventory_key:
            app = inventory.get(self._spec.inventory_key)
            if app is not None:
                return app
        matches = inventory.get_unknown(self._spec.label)
        return matches[0] if matches else None

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
        """Run one prompt against the real, installed desktop application.
        Never raises for an operational failure — every branch below
        returns a structured `ProviderResult`, the same contract
        `GeminiProvider.complete()` holds.

        No step here reports success because a launch happened, a window
        exists, text was typed, or Enter was pressed — Section 5's own
        rule. `SUCCEEDED` is returned only after a real response has been
        read back through the Desktop Executive and found non-empty and
        different from the submitted prompt.
        """
        started = time.monotonic()

        # -1. Role separation — checked before anything else, including the
        # static safety gate below. "Coding agents are for coding only...
        # they must not be selected by Kalpavriksha for... reasoning" (the
        # mission's own words), enforced structurally rather than by
        # convention: `is_coding_agent()` checks the spec's own declared
        # `role` AND a closed identity set, independent of each other, so
        # neither a missing role declaration nor a missing identity-list
        # entry alone can let a coding tool through. This check is also why
        # `build_desktop_providers()` never *constructs* a provider for a
        # coding-agent spec in the first place — this is defense in depth,
        # not the only gate.
        if is_coding_agent(self._spec):
            return failure(
                self._spec.provider_id, UNAVAILABLE, CODING_AGENT_NOT_A_REASONING_PROVIDER,
                latency_ms=self._elapsed_ms(started),
            )

        # 0. Static safety gate — checked before any discovery, launch, or
        # focus call. "Never open or interact with an unsafe desktop
        # application merely because it is installed" (the mission's own
        # words): a provider declared unsafe never even reaches the
        # machine, not just never reaches the composer. This is a
        # deliberately stronger guarantee than the generic runtime check
        # below provides on its own — see `claude-desktop`'s own catalog
        # entry for why one specific application needs it.
        if self._spec.autonomous_reasoning_unsafe_reason is not None:
            return failure(
                self._spec.provider_id, UNAVAILABLE,
                f"{AUTONOMOUS_REASONING_UNSAFE}: {self._spec.autonomous_reasoning_unsafe_reason}",
                latency_ms=self._elapsed_ms(started),
            )

        # 1. Real discovery evidence, not an assumption.
        inventory = self._context.inventory(deep=True)  # cache-first; see module docstring
        app = self._resolve_app_record(inventory)
        if app is None or not app.launchable or not app.launch_target:
            return failure(self._spec.provider_id, UNAVAILABLE, NOT_INSTALLED,
                            latency_ms=self._elapsed_ms(started))

        # 2. Launch or reuse (Model A — lifecycle owned by this call only).
        window = self._launch_or_focus(app)
        if window is None:
            return failure(self._spec.provider_id, UNAVAILABLE, LAUNCH_FAILED,
                            latency_ms=self._elapsed_ms(started))

        # 2.5. Find-or-create the one persistent, named
        # "Kalpavriksha Reasoning" reasoning conversation — the founder's
        # own explicit requirement: reuse the same, visibly-named
        # conversation across calls rather than creating a new, anonymous
        # one every time. `ReasoningSessionManager.establish()` first
        # searches for that exact name (never a substring match — a real,
        # live-found risk this guards against, see
        # `reasoning_session.py`'s own docstring); if found, it is opened
        # and reused. If not, a new conversation is created via the same
        # generic 'start a new conversation' control this architecture has
        # always used (a verified click through the application's own
        # genuine mechanism *is* the isolation guarantee — see that
        # module's own history for why), then best-effort renamed to the
        # required name so a future call can find and reuse it. Any
        # leftover composer draft the resulting surface shows either way
        # is not inspected here — an unsent draft is not conversation
        # history, and `_write_prompt()`'s own already-verified clear step
        # is what safely removes it before the real prompt is written. No
        # generic new-session control discoverable, and no existing named
        # session found, means isolation cannot be established at all:
        # fail closed, skip this provider.
        keyboard = KeyboardController()
        session = self._sessions.establish(window, self._spec.label, keyboard)
        if not session.ok:
            return failure(self._spec.provider_id, UNAVAILABLE, session.reason,
                            latency_ms=self._elapsed_ms(started))

        # Found live, this session: writing immediately after a
        # successfully-verified establishment can still fail — the
        # composer's *text content* settling (what establishment's own
        # freshness check reads) is not the same as its *focus/input*
        # state settling. A short, bounded, generic buffer here — not
        # inside `ReasoningSessionManager` itself, since this is about the
        # transition into writing, not about establishment's own
        # correctness — gives the same class of asynchronous UI update
        # `_verify_readback()`/`_verify_cleared()` already tolerate
        # elsewhere room to finish before the next real interaction
        # begins.
        time.sleep(_POST_ESTABLISH_SETTLE_SECONDS)

        # Every submitted prompt carries its own inspectable identity —
        # "Kalpavriksha Reasoning — <session identifier>" — directly in the
        # visible text, on top of the conversation itself now being
        # persistently named "Kalpavriksha Reasoning" (see step 2.5 above).
        # The founder can open the application and see, in the transcript
        # itself, what was asked and which individual request produced
        # the answer, inside the one persistent, reused conversation.
        marked_prompt = f"[{session.session_marker}]\n\n{prompt}"

        # 3. Semantic composer targeting — classic control first (cheap),
        # UIA fallback (the mechanism proven live against Claude Desktop
        # and ChatGPT Desktop this session). `keyboard` was already
        # constructed at step 2.5 (session establishment may itself need
        # to type a rename) — reused here, not recreated.
        written = self._write_prompt(window, marked_prompt, keyboard)
        if not written:
            return failure(self._spec.provider_id, REJECTED, WRITE_UNVERIFIED,
                            latency_ms=self._elapsed_ms(started))

        # 3.5. Baseline the window's text content *before* submitting —
        # `_await_response()`'s own generic response-discovery mechanism
        # (`find_new_content()`) needs a "before" snapshot to recognize
        # what genuinely changed once a real reply arrives, rather than
        # guessing from region size alone (see that method's own docstring
        # for the live-found sidebar/chrome false-positive this replaces).
        # Best-effort: an unreachable window here is not fatal on its
        # own — `_write_prompt()` already proved the window was reachable
        # moments ago — it just means `find_new_content()` has nothing to
        # diff against and treats everything as new, no worse than the
        # size-only heuristic it replaces.
        try:
            response_baseline = self._uia.snapshot_text_regions(window["handle"])
        except (UiaUnavailable, UiaTargetNotFound):
            response_baseline = {}

        # 4. Submit — verified, not assumed. Prefers Enter (the common,
        # fastest case); if that produces no visible sign of submission
        # within a bounded wait, Enter is not assumed to be this
        # application's universal submit mechanism — a generically-
        # discovered Send control is tried instead, via the same
        # find()/click() primitives every other interaction in this
        # provider already uses. No application-specific selector.
        submitted = self._submit(window, keyboard)
        if not submitted:
            return failure(self._spec.provider_id, REJECTED, SUBMIT_UNVERIFIED,
                            latency_ms=self._elapsed_ms(started))

        # 5. Bounded observation + verification — never treated as done
        # merely because Enter was pressed.
        response_text = self._await_response(window, marked_prompt, response_baseline)
        if response_text is None:
            return failure(self._spec.provider_id, TIMED_OUT, RESPONSE_TIMEOUT,
                            latency_ms=self._elapsed_ms(started))
        # Whitespace-normalized comparison, not raw `.strip()`: a rich-text
        # composer reflows pasted whitespace (blank lines collapsed,
        # indentation moved — see `uia_control.py`'s own finding). Leftover
        # prompt text that never actually got replaced by a real reply
        # would otherwise differ from `marked_prompt` by whitespace alone
        # and be mistaken for a genuine response — a fake success this
        # guards against, found live in this session's own testing.
        if not response_text.strip() or _normalize_whitespace(response_text) == _normalize_whitespace(marked_prompt):
            return failure(self._spec.provider_id, MALFORMED, EMPTY_RESPONSE,
                            latency_ms=self._elapsed_ms(started))

        # The application talking about itself is not an answer.
        #
        # `UNAVAILABLE` rather than `MALFORMED`: nothing was wrong with
        # the request and there is nothing to fix by rephrasing it --
        # this provider simply cannot serve it right now, which is
        # exactly what the ladder's exclude-and-ask-again is for. The
        # same class of judgement `gemini.py` makes about a 503, made
        # where the signal happens to be text instead of a status code.
        if _is_service_notice(response_text):
            return failure(
                self._spec.provider_id, UNAVAILABLE, SERVICE_NOTICE,
                latency_ms=self._elapsed_ms(started),
                notice=response_text.strip()[:200],
            )

        return ProviderResult(
            provider_id=self._spec.provider_id,
            outcome=SUCCEEDED,
            response=ProviderResponse(
                text=response_text, model=self._spec.label,
                latency_ms=self._elapsed_ms(started),
            ),
            latency_ms=self._elapsed_ms(started),
            detail={
                "application": self._spec.label,
                "window_handle": window["handle"],
                "session_marker": session.session_marker,
                "session_reused": session.reused,
                "session_renamed": session.renamed,
            },
        )

    # ---- steps ------------------------------------------------------------

    def _launch_or_focus(self, app) -> dict | None:
        deadline = time.monotonic() + _LAUNCH_TIMEOUT_SECONDS

        def _start() -> bool:
            """Invoke the launch target discovery already resolved (§7's
            own precedence: AppUserModel/MSIX > verified path). Never
            guessed here."""
            target = app.launch_target
            if target.lower().startswith("shell:appsfolder"):
                result = self._context.probe.start(["explorer.exe", target])
            else:
                result = self._context.probe.start([target])
            return bool(result.ok)

        from master_agent.desktop.execution.window import WindowManager
        manager = WindowManager(self._windows)

        def _visible_windows() -> list:
            inv = self._context.refresh(read_versions=False, deep=False)
            running = {p.pid for p in inv.processes
                       if p.owner and p.owner == getattr(app, "key", None)}
            if not running:
                return []
            located = manager.locate_by_process(frozenset(running))
            if not located.success:
                return []
            return list(located.output["windows"] or ())

        # **A running process is not an open window.**
        #
        # This used to launch only when no process existed, on the
        # reasonable-sounding assumption that a running application has a
        # window to focus. These applications do not work that way: closing
        # the window leaves the app alive in the tray, and it then has
        # processes and no window at all.
        #
        # Measured live, and it is the whole of the "empty run" the founder
        # saw one time in three: ChatGPT Desktop with NINE running processes
        # and ZERO visible windows. Because processes existed, nothing was
        # launched; the loop below then polled for thirty seconds for a
        # window that was never going to appear, and the mission failed with
        # "the application did not report a real, visible window" without a
        # single prompt being submitted. Nothing was wrong with response
        # capture; nothing had been asked.
        #
        # So the decision to launch follows the WINDOW, not the process.
        # Invoking the launch target of an already-running application is
        # how a founder reopens it from the Start menu, and for the
        # single-instance applications here that restores the existing
        # window rather than starting a second copy. Done once, before the
        # poll, so the bounded wait is spent waiting for a window that has
        # actually been asked to appear.
        if not _visible_windows():
            if not _start():
                return None
            time.sleep(1.0)

        # Find the real, visible window — polled, bounded, never assumed
        # from "the launch call returned".
        pids = {p.pid for p in self._context.refresh(read_versions=False, deep=False).processes
                if p.owner and p.owner == getattr(app, "key", None)}
        while time.monotonic() < deadline:
            inv = self._context.refresh(read_versions=False, deep=False)
            running_pids = {p.pid for p in inv.processes
                             if p.owner == getattr(app, "key", None)} or pids
            if running_pids:
                located = manager.locate_by_process(frozenset(running_pids))
                if located.success and located.output["windows"]:
                    window = located.output["windows"][0]
                    manager.bring_to_front(window["handle"])
                    time.sleep(0.3)
                    active = manager.active()
                    if active.success and active.output.get("handle") == window["handle"]:
                        # A non-maximized window can leave the composer
                        # heuristic reasoning about the wrong proportions
                        # (`find_composer()`'s own height-fraction math
                        # assumes a normally-sized window) — maximize is
                        # the correct, generic fix for that, never a
                        # reason to touch the composer geometry thresholds
                        # themselves. Best-effort: a window that refuses to
                        # maximize is not fatal here, since `find_composer()`
                        # already tolerates real window sizes below full
                        # screen; only launch/focus failing is fatal.
                        manager.maximize(window["handle"])
                        time.sleep(0.3)
                        return window
                    # Foreground not confirmed — do NOT type, paste, or
                    # press Enter into whatever window actually holds real
                    # OS keyboard focus right now. Found live, this
                    # session: proceeding on an unconfirmed ("racy")
                    # foreground state let a real ~6KB prompt and a
                    # submitting Enter land in a completely different
                    # application's window instead of the intended one —
                    # a real cross-application keystroke leak, not a
                    # theoretical risk. Retry bring_to_front within the
                    # same bounded deadline instead of ever proceeding
                    # unconfirmed.
            time.sleep(0.5)
        return None

    def _write_prompt(self, window: dict, prompt: str, keyboard: KeyboardController) -> bool:
        handle = window["handle"]
        interface = classify_window(handle, Win32ChildEnumBackend())
        if interface == "classic":
            resolver = ClassicControlResolver(Win32ChildEnumBackend())
            try:
                control = resolver.find(handle, text_contains=self._composer_hint)
                if resolver.write_text(control, prompt):
                    return prompt in resolver.read_text(control)
            except ControlNotFound:
                pass  # fall through to UIA

        try:
            if self._composer_hint:
                element = self._uia.find(handle, name_contains=self._composer_hint)
            else:
                element = self._uia.find_composer(handle)
        except (UiaUnavailable, UiaTargetNotFound):
            return False
        return self._uia.write_text(element, prompt, keyboard, append=False, mouse=self._mouse)

    def _submit(self, window: dict, keyboard: KeyboardController) -> bool:
        """Submit the composer's current content, verified — never
        treated as done merely because Enter was pressed or a Send
        control was clicked.

        Prefers Enter first (the common case, and the one every desktop
        AI application tried this session has actually accepted). If the
        composer's own content does not change within a bounded wait,
        Enter is not assumed to be this application's submit mechanism —
        a generically-discovered Send/submit control (see
        `SEND_VOCABULARY`) is searched for and invoked instead, using the
        same `find()`/`click()` primitives every other interaction in
        this provider already uses. No application-specific selector, no
        coordinate.
        """
        handle = window["handle"]
        composer_before = self._read_composer_safely(handle)

        keyboard.press("enter")
        if self._verify_submission(handle, composer_before):
            return True

        control = self._find_send_control(handle)
        if control is not None:
            try:
                clicked = self._uia.click(control, self._mouse)
            except (UiaUnavailable, UiaTargetNotFound):
                clicked = False
            if clicked and self._verify_submission(handle, composer_before):
                return True

        return False

    def _read_composer_safely(self, handle: int) -> str | None:
        try:
            element = self._uia.find_composer(handle)
            return _normalize_whitespace(self._uia.read_text(element))
        except (UiaUnavailable, UiaTargetNotFound):
            return None

    def _verify_submission(self, handle: int, composer_before: str | None) -> bool:
        """Bounded retry/backoff: submission is confirmed once the
        composer's own content differs from what it held right before
        the submit attempt — a genuine submit either clears the composer
        or starts replacing it, well before a full response has arrived.
        Fails closed on an unreadable composer (`None`) that stays
        unreadable throughout — never assumed to have submitted.

        Reads `_SUBMIT_VERIFY_ATTEMPTS`/`_SUBMIT_VERIFY_DELAY_SECONDS` as
        bare module globals rather than default parameter values — the
        same pattern `_await_response()` already uses — so a test can
        monkeypatch either constant and actually affect behavior; a
        default parameter value is bound once at import time and would
        not be reachable that way.
        """
        for _ in range(_SUBMIT_VERIFY_ATTEMPTS):
            time.sleep(_SUBMIT_VERIFY_DELAY_SECONDS)
            current = self._read_composer_safely(handle)
            if current != composer_before:
                return True
        return False

    def _find_send_control(self, handle: int):
        for phrase in SEND_VOCABULARY:
            try:
                return self._uia.find(handle, name_contains=phrase, visible_only=True, retries=0)
            except (UiaTargetNotFound, UiaUnavailable):
                continue
        return None

    def _await_response(self, window: dict, prompt: str, baseline: dict) -> str | None:
        """Poll for a genuinely new, settled response — not merely
        `find_main_content()`'s "biggest text region," which was
        confirmed live, against both ChatGPT Desktop and Kimi Desktop, to
        select navigation/sidebar chrome instead of the real reply (a
        chat list or workspace nav panel can be taller than a short
        answer). `find_new_content()` instead asks what changed since
        `baseline` (captured before submission) — the structural signal
        that actually distinguishes a new response from persistent UI.

        A single "it changed" reading is still not enough on its own: a
        transient "…is responding" / "Reconnecting…" status string is
        also new content that did not exist before submission, and was
        directly observed live, mid-generation, satisfying a naive
        changed-since-baseline check. Nor is even one repeat enough —
        confirmed live, against ChatGPT Desktop, accepting a genuinely
        truncated mid-stream read after only one repeat (see
        `_RESPONSE_STABILITY_POLLS`'s own docstring). This only accepts a
        candidate once the *same* text reads back identically across
        `_RESPONSE_STABILITY_POLLS` consecutive polls — a generic
        settle/stability check, not a match against any application's
        specific wording, distinguishing "still streaming in" from
        "finished" the same way a founder watching the screen would: it
        stopped moving.
        """
        handle = window["handle"]
        deadline = time.monotonic() + _RESPONSE_POLL_TIMEOUT_SECONDS
        prompt_norm = _normalize_whitespace(prompt)
        # One turn, owned by this wait and discarded with it. Once this
        # call has positively located its own prompt, that fact survives
        # the application scrolling the prompt out of the tree -- which it
        # does, mid-wait, and which used to make every later poll behave
        # as though the turn had never been anchored at all.
        turn = ResponseTurn()
        previous_text: str | None = None
        stable_count = 0
        while time.monotonic() < deadline:
            time.sleep(_RESPONSE_POLL_INTERVAL_SECONDS)
            try:
                # The whole reply, reconstructed from its rendered leaves in
                # reading order. `find_new_content()` answers "which single
                # region", and in a transcript exposed as flat sibling leaves
                # -- ChatGPT Desktop's is 2196 of them under one parent --
                # that question has no answer: it returned 'GardenLog', one
                # line of a three-line reply, perfectly stable and two thirds
                # missing. The stability check below now compares the whole
                # reconstruction, so a streaming answer settles only once
                # every line has arrived.
                text = self._uia.find_new_response(
                    handle, baseline, exclude_text=prompt, turn=turn
                )
            except (UiaUnavailable, UiaTargetNotFound):
                text = None
            if not text or not text.strip() or _normalize_whitespace(text) == prompt_norm:
                previous_text = None
                stable_count = 0
                continue
            if previous_text is not None and _normalize_whitespace(text) == _normalize_whitespace(previous_text):
                stable_count += 1
                if stable_count >= _RESPONSE_STABILITY_POLLS - 1:
                    return text  # stable across every required poll -- generation has settled
            else:
                stable_count = 0
            previous_text = text
        return None

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return (time.monotonic() - started) * 1000.0


def build_desktop_providers(
    context: DesktopContext,
    composer_hints: dict[str, str] | None = None,
) -> list[DesktopAppReasoningProvider]:
    """One provider per `locality == DESKTOP` entry already declared in
    `PROVIDER_CATALOG` — adding a new desktop AI application to that
    catalogue is the only change needed to add it here; nothing in this
    function names an application.

    A coding-agent spec (`is_coding_agent()`) is never even constructed as
    a provider — "coding-agent providers cannot enter the reasoning-provider
    catalogue" holds at this, the earliest possible point, not merely at
    `complete()`'s own redundant check.
    """
    hints = composer_hints or {}
    return [
        DesktopAppReasoningProvider(spec, context, composer_name_hint=hints.get(spec.provider_id))
        for spec in PROVIDER_CATALOG
        if spec.locality == DESKTOP and not is_coding_agent(spec)
    ]
