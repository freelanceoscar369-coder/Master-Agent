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
import uuid
from typing import Any

from master_agent.ai_infrastructure.catalog import DESKTOP, PROVIDER_CATALOG, ProviderSpec, is_coding_agent
from master_agent.desktop.actions import DesktopContext
from master_agent.desktop.execution.clipboard import ClipboardExecutive
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
    _PROMPT_FRAGMENT_MIN_CHARS,
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
PROMPT_TOO_LONG = (
    "this request is longer than the application's own composer will "
    "carry, and a shortened request is a different request"
)

#: Room for the `[Kalpavriksha Reasoning - ... ]` identity line that every
#: submitted prompt carries. Counted against the composer's own limit
#: because it is genuinely typed into the composer alongside the request.
_MARKER_RESERVE_CHARS = 128
PROMPT_ECHOED = (
    "the application returned the request back with interface text around "
    "it, not an answer"
)

#: How much genuinely new text a real answer must carry once our own
#: request is removed from it.
#:
#: Small deliberately -- a terse but real reply ("Yes, both are
#: step-free.") must survive, while a composer echoing the prompt beside
#: its own buttons must not.
MIN_ANSWER_CHARS = 40


def _is_only_our_own_prompt(response: str, marked_prompt: str) -> bool:
    """Is this our request wearing the application's furniture?

    Compares on words rather than characters, because a rich composer
    reflows whitespace on paste -- the same reason `_verify_readback`
    already normalises before comparing.
    """
    body = _normalize_whitespace(response or "")
    sent = _normalize_whitespace(marked_prompt or "")
    if not body or not sent:
        return False
    if sent not in body:
        # It did not hand our request back at all, so whatever this is,
        # it is the application's own words. A test caught this: a short
        # genuine reply that never quotes us was being rejected purely
        # for being short, which would have thrown away real answers.
        return False
    remainder = body.replace(sent, " ")
    # Whatever is left after removing what we sent, minus the short
    # generic labels a chat surface puts around a message.
    for label in ("Edit", "Copy", "Share", "Retry", "Regenerate", "New chat",
                  "Send", "Stop", "Ask me. Task me."):
        remainder = remainder.replace(label, " ")
    return len(_normalize_whitespace(remainder)) < MIN_ANSWER_CHARS

ONLY_INTERFACE_TEXT = (
    "the application returned its own interface labels, not an answer"
)

#: The labels a chat surface paints around a conversation.
#:
#: Measured live, this session, against Kimi Desktop. Asked to reply with
#: one nonce token, the provider returned `SUCCEEDED` carrying:
#:
#:     Copy
#:     Share
#:     Create or select a file to start
#:     Your chats will appear here
#:     Update
#:     Instant
#:     High
#:     AI-generated, for reference only
#:
#: Not our prompt handed back, so `_is_only_our_own_prompt` did not fire.
#: Not a service notice, so `_is_service_notice` did not fire. Eight
#: lines of a window describing itself, propagating as a reasoning
#: result -- and every consumer downstream then behaved correctly on
#: furniture, which is how a battery of Brain fixtures came to be read as
#: intelligence variance.
#:
#: This exact knowledge already existed in
#: `scripts/live_acceptance/p0_3_complete_response.py`, where a hand-
#: written judge rejected the same eight lines. A guard that lives only
#: in an acceptance script protects the acceptance run and nothing else.
#: It belongs where the classification happens, beside the two guards
#: that already refuse the other kinds of fake success -- and there is
#: now one owner of it, which that script imports.
_INTERFACE_LABELS: frozenset[str] = frozenset({
    # affordances on a message
    "copy", "share", "edit", "delete", "retry", "regenerate", "rerun",
    "like", "dislike", "good response", "bad response", "read aloud",
    # affordances on the conversation
    "send", "stop", "new chat", "new task", "new conversation", "rename",
    "export", "attach", "attach file", "upload", "search", "voice",
    # model / mode pickers
    "update", "instant", "high", "auto", "thinking", "fast", "pro",
    "model", "settings",
    # empty-state and disclaimer copy
    "your chats will appear here", "create or select a file to start",
    "ai-generated, for reference only", "ask me. task me.",
    "how can i help", "how can i help?", "what can i help with",
    "what can i help with?", "start a new chat to begin",
})

#: A line long enough to be prose is not a label, whatever it says --
#: which keeps a genuine sentence that happens to open with one of these
#: words from ever being counted as furniture.
_MAX_INTERFACE_LABEL_CHARS = 48


def _is_only_interface_text(text: str) -> bool:
    """Is every line of this the window describing itself?

    ONE substantive line is enough to make it an answer. The question is
    not whether furniture is present -- a real reply often arrives with
    `Copy` and `Share` attached to it -- but whether there is anything
    else at all.
    """
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if not lines:
        return False
    for line in lines:
        if len(line) > _MAX_INTERFACE_LABEL_CHARS:
            return False
        if line.lower().strip(" .:-—") not in _INTERFACE_LABELS:
            return False
    return True


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
        #: Reading a reply back the way the application offers it.
        #: The lane already spends the clipboard to paste prompts.
        self._clipboard = ClipboardExecutive()
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

        # 0.5. Will this application's own composer even carry the
        # request? Asked here, before discovery, launch or focus, so a
        # provider that cannot serve this prompt costs nothing but the
        # question -- and so the answer is never "send a shorter one".
        #
        # `prompt[:limit]` is the whole failure mode this branch exists
        # to make unreachable. Truncating turns "what are the Sunday
        # hours for these three rooms" into "what are the Sunday" and
        # gets a fluent answer to the wrong question, with nothing
        # downstream able to tell that anything was lost. Failing here
        # hands the request to the next provider intact.
        limit = getattr(self._spec, "max_prompt_chars", None)
        if limit is not None and len(prompt) + _MARKER_RESERVE_CHARS > limit:
            return failure(
                self._spec.provider_id, REJECTED, PROMPT_TOO_LONG,
                latency_ms=self._elapsed_ms(started),
                prompt_chars=len(prompt), max_prompt_chars=limit,
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

        # What was established, carried onto every result from here on --
        # success AND failure. The first live run of
        # `scripts/live_acceptance/kimi_session_health.py` could not say
        # whether a fresh conversation had been created, because the run
        # ended in a provider failure and the failure carried nothing
        # about the session. A diagnosis is most needed exactly when
        # something went wrong.
        session_detail = {
            "session_marker": session.session_marker,
            "session_reused": session.reused,
            "session_renamed": session.renamed,
            "session_rotated": session.rotated,
            "session_health": session.health.as_dict(),
        }

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
                            latency_ms=self._elapsed_ms(started), **session_detail)

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
                            latency_ms=self._elapsed_ms(started), **session_detail)

        # 5. Bounded observation + verification — never treated as done
        # merely because Enter was pressed.
        response_text = self._await_response(
            window, marked_prompt, response_baseline, budget,
        )
        if response_text is None:
            return failure(self._spec.provider_id, TIMED_OUT, RESPONSE_TIMEOUT,
                            latency_ms=self._elapsed_ms(started), **session_detail)

        # The application will hand over its own reply, exactly, if asked.
        #
        # Reconstruction can only ever see what is RENDERED. Measured live
        # on 2026-09-05, a Stage 1 audit reply came back with rows at
        # top=-121 -- scrolled above the viewport -- and its leading
        # `{"regions":[...]` was absent from the accessibility tree
        # altogether. No ordering or exclusion rule recovers text the
        # window never drew, and the reply parsed as prose rather than as
        # the JSON the Brain asked for.
        #
        # A per-message `Copy` button is the application's own answer to
        # "give me that text", which is what a founder would click. It
        # costs the clipboard, and this lane already spends it: `paste()`
        # replaces the clipboard to submit every long prompt.
        #
        # Strictly an improvement or nothing -- the settled reconstruction
        # stands unless copying produced something real.
        copied = self._reply_via_copy(window)
        if (
            copied
            and self._copy_is_this_turn(copied, response_text)
            and len(copied.strip()) >= len(response_text.strip())
        ):
            response_text = copied
        # Whitespace-normalized comparison, not raw `.strip()`: a rich-text
        # composer reflows pasted whitespace (blank lines collapsed,
        # indentation moved — see `uia_control.py`'s own finding). Leftover
        # prompt text that never actually got replaced by a real reply
        # would otherwise differ from `marked_prompt` by whitespace alone
        # and be mistaken for a genuine response — a fake success this
        # guards against, found live in this session's own testing.
        if not response_text.strip() or _normalize_whitespace(response_text) == _normalize_whitespace(marked_prompt):
            return failure(self._spec.provider_id, MALFORMED, EMPTY_RESPONSE,
                            latency_ms=self._elapsed_ms(started), **session_detail)

        # Our own prompt handed back with the furniture around it.
        #
        # The check above catches an EXACT echo. Reproduced live against
        # Kimi Desktop, the real shape is not exact: the scrape returned
        # the composer placeholder, our marked prompt, and the surrounding
        # UI labels --
        #
        #     "Ask me. Task me.
        #      [Kalpavriksha Reasoning - Kimi Desktop - ... - d477b9ad]
        #      Create or select a file to start
        #      Edit  Copy  Share ..."
        #
        # -- with `ok=True`. It propagated as a reasoning result, and
        # every consumer behaved correctly on nonsense: the Planner could
        # not build a plan from it and the candidate extractor found
        # nothing, so a whole battery failed while the ladder reported
        # success at every rung.
        #
        # Generic, not app-specific: "the reply is our own request plus
        # decoration" is a fake success in any application. Removing the
        # prompt we sent and asking whether anything substantial remains
        # is the same question `EMPTY_RESPONSE` already asks, made to
        # survive a composer that decorates.
        if _is_only_our_own_prompt(response_text, marked_prompt):
            return failure(
                self._spec.provider_id, MALFORMED, PROMPT_ECHOED,
                latency_ms=self._elapsed_ms(started),
                observed=response_text.strip()[:200], **session_detail,
            )

        # The window describing itself is not an answer either.
        #
        # `MALFORMED`, alongside the echoed prompt: nothing is wrong with
        # the request, and nothing here says the application cannot serve
        # it -- the read came back with the surface instead of the reply.
        # Measured live against Kimi Desktop; see `_INTERFACE_LABELS`.
        if _is_only_interface_text(response_text):
            return failure(
                self._spec.provider_id, MALFORMED, ONLY_INTERFACE_TEXT,
                latency_ms=self._elapsed_ms(started),
                observed=response_text.strip()[:200], **session_detail,
            )

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
                notice=response_text.strip()[:200], **session_detail,
            )

        # The warning can appear because of the very turn that just
        # succeeded. A real answer is not thrown away for it -- the
        # request was owned, the response is genuine, and Verification
        # judges it on its own merits. What changes is only that this
        # conversation is not used again: retired now, so the NEXT call
        # rotates instead of walking back into it.
        after = self._sessions.inspect_session(window["handle"])
        saturated_after = after.saturated
        if saturated_after:
            self._sessions.retire(self._spec.label)

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
                **session_detail,
                # PROVIDER SESSION health, never provider health. False
                # here says one accumulated conversation is finished; it
                # says nothing at all about whether this application can
                # answer the next question, which is why the Broker sees
                # a `SUCCEEDED` result and no exclusion.
                "session_reusable": not saturated_after,
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

    #: How long to wait for the clipboard to show the copy actually
    #: happened. A button click is instant; the write behind it is not
    #: always synchronous, and reading too eagerly returns the sentinel.
    _COPY_SETTLE_SECONDS = 2.5
    _COPY_POLL_SECONDS = 0.15

    @staticmethod
    def _copy_is_this_turn(copied: str, settled: str) -> bool:
        """Is the copied text THIS turn's reply, or an older message?

        The sentinel proves the clipboard changed. It cannot prove what it
        changed TO. `find_last` takes the last `Copy` in the transcript,
        and if this turn's affordance has not rendered yet that is the
        PREVIOUS message's button -- so a stale reply arrives complete,
        well-formed, and answering the question before last.

        Measured live on 2026-09-05: two different prompts came back with
        byte-identical 3,251-character replies, and the obligation AUDIT
        returned the proposal shape -- `source_quote`/`meaning` where
        `regions`/`omissions`/`collapses` were required. Parsed cleanly,
        and wrong, which is worse than unparseable.

        The reconstruction is this turn's by construction: it is anchored
        below this turn's own prompt floor. It may be partial, but every
        run in it came from this reply, so the longest of them must appear
        in any text claiming to BE this reply.
        """
        runs = [
            run.strip() for run in (settled or "").split("\n")
            if len(run.strip()) >= _PROMPT_FRAGMENT_MIN_CHARS
        ]
        if not runs:
            # Nothing distinctive to check against. The size comparison in
            # the caller is then the only guard, which is where it was
            # before copying existed.
            return True
        # Whitespace is dropped entirely rather than normalised. The two
        # texts came from different places -- one rebuilt from rendered
        # runs, one copied as the application stores it -- and they wrap
        # differently, so a newline in one is a space, or nothing, in the
        # other. Normalising still leaves those apart; ignoring the
        # whitespace compares what was actually said.
        def _bare(text: str) -> str:
            return "".join((text or "").split())

        return _bare(max(runs, key=len)) in _bare(copied)


    def _reply_via_copy(self, window: dict) -> str | None:
        """The reply as the application itself would give it, or `None`.

        Never raises and never partially succeeds: either the clipboard
        provably changed to something non-empty because of our click, or
        this answers `None` and the caller keeps what it already had.

        The sentinel is what makes that provable. Reading the clipboard
        after a click and trusting whatever is there would return the
        founder's own previous clipboard whenever the click missed --
        silently, and looking exactly like a reply.
        """
        try:
            handle = window["handle"]
            button = self._uia.find_last(handle, name_exact="Copy", control_type=50000)
            if button is None:
                return None

            sentinel = f"__kalpavriksha_copy_{uuid.uuid4().hex}__"
            written = self._clipboard.write(sentinel)
            if not getattr(written, "success", False):
                return None

            if not self._uia.click(button, self._mouse):
                return None

            deadline = time.monotonic() + self._COPY_SETTLE_SECONDS
            while time.monotonic() < deadline:
                time.sleep(self._COPY_POLL_SECONDS)
                read = self._clipboard.read()
                if not read.success:
                    continue
                text = (read.output or {}).get("text") or ""
                if text and text != sentinel:
                    return text
            return None
        except Exception:  # noqa: BLE001 -- an optional improvement never fails a turn
            return None


    @staticmethod
    def _reply_window_seconds(budget: Any) -> float:
        """How long this call may wait, from the budget it was given.

        MB038 derives a deadline per request and `complete()` has taken a
        `budget` since Step 14 -- but nothing here ever read it, so every
        prompt got the same 45 seconds. That constant was tuned against
        the founder's three-name acceptance prompt, and a Stage 1
        obligation audit is a different size of question entirely.

        Measured live on 4 Sep: ChatGPT Desktop answered that audit in
        95.1s standalone and was cut off at 45s inside the mission, so the
        Brain was told the lane had timed out. Every reasoning lane failed
        in turn, the ladder exhausted, and the founder was told "I
        couldn't plan that just now" about a request to make a folder.
        A working provider reported as broken is the expensive kind of
        wrong: it looks like an unreachable provider, not like a clock.

        The budget is authoritative when present -- it is derived from the
        workload class and the prompt, which is exactly the thing the
        constant could not know. The constant stays as the floor for
        callers that pass no budget at all.
        """
        total_ms = getattr(budget, "total_ms", None)
        if not isinstance(total_ms, (int, float)) or total_ms <= 0:
            return _RESPONSE_POLL_TIMEOUT_SECONDS
        return max(_RESPONSE_POLL_TIMEOUT_SECONDS, float(total_ms) / 1000.0)

    def _await_response(
        self, window: dict, prompt: str, baseline: dict, budget: Any = None,
    ) -> str | None:
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
        deadline = time.monotonic() + self._reply_window_seconds(budget)
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
