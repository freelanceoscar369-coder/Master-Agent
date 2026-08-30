"""Reasoning Session Manager — one persistent, named, Kalpavriksha-owned
reasoning conversation per desktop AI application.

**Architectural history, in order — each correction found live, not
guessed:**

1. The original model asked "does whatever conversation is currently
   focused happen to look empty?" — and that model is exactly what let a
   real incident happen: the focused conversation was an *active* one
   (this project's own Claude Code session).
2. The correction: actively request a NEW conversation via a generic
   'start a new conversation' affordance (`NEW_SESSION_VOCABULARY`) and
   treat that verified action as the isolation guarantee, rather than
   inspecting whatever was already focused.
3. A second correction on top of that: requiring the resulting surface's
   *content* to look empty afterward conflated an unsent composer draft
   (safe to clear, never submitted) with real conversation history (must
   never be hijacked) — real applications leave draft text in a composer
   across many "new chat" actions, surviving even a machine restart,
   without that text ever having been part of an executed conversation.
4. **This correction**: creating a brand-new, anonymous conversation on
   *every single reasoning call* was itself the wrong end-state. The
   founder's own explicit requirement is one *persistent*, visibly named
   conversation — literally titled `"Kalpavriksha Reasoning"` — that is
   located and reused on every subsequent call, with creation happening
   only once, as an initialization step, not a per-request one.

**The name is the discovery mechanism, on purpose.** Exact-name matching
(`find(name_exact=...)`, never `name_contains`) is what keeps
`"Kalpavriksha Reasoning"` from ever being confused with
`"Kalpavriksha Reasoning — old test"`, `"My Kalpavriksha Reasoning
Notes"`, or any other conversation that merely contains the phrase — a
real, live-found risk: a substring search for this exact name matched an
unrelated historical conversation during this session's own knowledge-
acquisition work (see `docs/audits/APP_KNOWLEDGE_ACQUISITION_1.md`).
Because the name — not an in-memory identifier — is what makes the
session findable, it survives an application restart, a machine restart,
or this process itself restarting: whatever created it, a *later* call
locates the same conversation by title alone.

**No new automation mechanism, only new composition.** `find()`/`click()`
already exist; renaming a freshly created conversation reuses the exact
same vocabulary-search pattern (`RENAME_TRIGGER_VOCABULARY`/
`RENAME_ACTION_VOCABULARY`, structured identically to
`NEW_SESSION_VOCABULARY`) plus the already-proven `write_text()` and a
new, narrowly-scoped read primitive
(`UiaAutomationBridge.get_focused_element_in_window()`) to write into
whatever the OS moves real keyboard focus to after "Rename" is invoked —
the common UX pattern for an inline rename field, not a guess at any one
application's specific dialog shape. Renaming is explicitly best-effort:
a session that was genuinely, verifiably created but could not be renamed
is still a valid, isolated conversation for *this* call — only *reuse* on
a *future* call degrades, gracefully, back to creating a fresh one (the
prior architecture's own behavior, not a regression below it).
"""
from __future__ import annotations

import dataclasses
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from master_agent.desktop.execution.uia_control import UiaTargetNotFound, UiaUnavailable

#: The required, persistent, visibly-inspectable name for Kalpavriksha's
#: own reasoning conversation in every application — the founder's own
#: explicit requirement. Exact-match only; see this module's own
#: docstring for why a substring match is unacceptable here.
DEDICATED_SESSION_NAME = "Kalpavriksha Reasoning"

#: Generic vocabulary of "start a new conversation" affordances, common
#: across chat-style desktop AI applications — confirmed live, this
#: session, against two real, currently-installed applications (a "New
#: chat" button in one, a "New Task" button in another), found by this
#: exact vocabulary search. Not one application's own wording: a
#: case-insensitive substring match against each candidate element's
#: accessible name, the same matching rule `UiaAutomationBridge.find()`
#: already uses everywhere else in this codebase.
NEW_SESSION_VOCABULARY = (
    "new chat",
    "new conversation",
    "new session",
    "new thread",
    "new task",
    "start new chat",
    "start a new conversation",
    "clear chat",
    # Tried last, deliberately: a bare "new" is real (confirmed live
    # against Perplexity Desktop's own sidebar control, accessible name
    # exactly "New" — too terse to contain any of the more specific
    # phrases above as a substring), but also the phrase most likely to
    # false-positive match something unrelated in a busier window (a
    # "News" section, a "Renew subscription" control). Placed last so
    # every more specific, lower-risk phrase is tried first; only falls
    # back to this generic single word when nothing else matched at all.
    "new",
)

#: Generic vocabulary for a control that directly renames a conversation
#: (an inline pencil/edit icon, most commonly) — tried first, since it is
#: the more targeted, lower-risk match.
RENAME_ACTION_VOCABULARY = (
    "rename",
    "rename chat",
    "rename conversation",
    "edit name",
)

#: Generic vocabulary for a conversation's own "more options" trigger,
#: tried only when no direct rename control is found — opening it is
#: expected to reveal a menu that itself contains a `RENAME_ACTION_VOCABULARY`
#: match. Deliberately narrower than a bare "options"/"more"/"actions"
#: (all considered and rejected as *first*-priority entries) to reduce
#: the chance of matching an unrelated control elsewhere in the window
#: (e.g. an application-wide settings button) — every specific phrase
#: names the conversation directly. "options" and "actions" are both
#: represented: confirmed live, this session, that real applications use
#: either word interchangeably for the identical "more things you can do
#: with this item" concept — Perplexity Desktop's own per-session menu
#: trigger is named "Session actions" / "More actions", neither of which
#: contains "options" at all.
RENAME_TRIGGER_VOCABULARY = (
    "more options",
    "chat options",
    "conversation options",
    "message options",
    "session actions",
    "chat actions",
    "conversation actions",
    "message actions",
    "more actions",
)

#: Exact-match label for a general chat/reasoning section, distinct from a
#: coding-agent/work section — found live, this session, in two real,
#: independent applications, each exposing exactly this as one of two
#: top-level section tabs (the other being `"Work"`/`"Codex"`). Deliberately
#: exact-match (`name_exact`, not `name_contains`): "chat" as a *substring*
#: also matches `"New chat"`, `"Chats"`, `"Pin chat"`, `"Archive chat"` —
#: real sibling element names found live in the same window, any of which
#: a substring search could return first. Best-effort and non-fatal: an
#: application with no distinct chat/work sections (most of them, including
#: Perplexity Desktop's own single unified surface — confirmed live,
#: docs/audits/APP_KNOWLEDGE_ACQUISITION_1.md) simply has nothing to
#: navigate, and `ensure_named_session()` proceeds unchanged.
CHAT_SECTION_LABEL = "Chat"

#: What an application says when its own conversation has grown past
#: what it will keep serving well. Observed live by the founder, in Kimi
#: Desktop, while Kalpavriksha was still sending requests into it:
#:
#:     Your conversation with Kimi is getting too long.
#:     Try starting a new session.
#:
#: This is PROVIDER SESSION HEALTH, not model answer content. Nothing
#: about the reasoning was wrong; the transport this adapter had been
#: reusing was no longer suitable. Reading it as an answer, or ignoring
#: it and sending anyway, is how a whole battery of fixtures came to be
#: judged as intelligence variance.
#:
#: SHAPES, not one product's sentence -- the same discipline
#: `NEW_SESSION_VOCABULARY` above already holds. Every phrase names the
#: *conversation's own length*, which is what makes them safe to search
#: for across a whole window: a "New chat" button's accessible name
#: contains none of them, and neither does ordinary prose about anything
#: except a chat that has run on too long.
#:
#: Deliberately NOT paired with a "try starting a new session" half. That
#: conjunction would be more specific and would also miss the warning
#: whenever the two sentences render as two separate elements, which is
#: the common case. The asymmetry says to bias toward detection: a false
#: positive costs one extra new-conversation click, and the founder's own
#: architectural rule is that starting a fresh provider conversation must
#: always be safe.
SESSION_SATURATION_VOCABULARY = (
    "getting too long",
    "conversation is too long",
    "conversation too long",
    "chat is too long",
    "this chat is getting long",
    "maximum conversation length",
    "maximum length of this conversation",
    "conversation limit",
    "context limit reached",
    "reached the maximum length",
    "chat is full",
)

#: Controls that only exist when something is already attached.
#:
#: Deliberately only the *removal* affordances. A bare "attach"/
#: "attachment" match would find the permanent "Attach file" button that
#: these applications show all the time, and would report a stale
#: attachment on a session that has none. A "remove" control is evidence
#: by its own existence: there is nothing to remove unless something is
#: attached.
#:
#: The founder observed this live: in Kimi, a previous prompt remained
#: visible as an attachment on the next turn. A clean text composer is
#: not the same thing as an isolated session.
STALE_ATTACHMENT_VOCABULARY = (
    "remove attachment",
    "remove file",
    "remove image",
    "remove upload",
    "delete attachment",
    "clear attachment",
)

#: A conversation observed saturated is never used again by this manager,
#: and this is the reason returned when a *freshly created* one cannot be
#: proven healthy either. `ok=False`, so the caller treats it exactly like
#: any other provider failure: exclude and ask the next ranked provider.
#: Never a permanent judgment about the provider itself.
SESSION_SATURATED = "SESSION_SATURATED"


#: Real UI settle time after invoking a "new chat"-style control, before
#: trusting the resulting surface's content — the same asynchronous-
#: rendering caution `_verify_readback()` already documents for Chromium/
#: Electron composers generally.
_POST_CREATE_SETTLE_SECONDS = 0.6

ISOLATION_UNVERIFIED = "ISOLATION_UNVERIFIED"


@dataclass(frozen=True)
class SessionHealth:
    """What one look at the application's own window says about the
    conversation currently open in it, *before* a prompt is written.

    Not a judgment about the provider. Kimi can be perfectly available
    while one accumulated conversation inside it is no longer suitable --
    the distinction the founder drew, and the reason nothing here ever
    reaches for a provider-wide exclusion.

    `composer_text` is recorded rather than gated on: an unsent draft is
    not conversation history (this module's own correction 3), and what
    actually guarantees a clean composer at send time is
    `_write_prompt()`'s already-verified clear-and-readback, which is
    proof rather than a glance.
    """

    saturated: bool = False
    stale_attachment: bool = False
    warning: str = ""
    composer_text: str = ""
    observed: bool = False

    @property
    def usable(self) -> bool:
        return not self.saturated and not self.stale_attachment

    def as_dict(self) -> dict:
        return {
            "saturated": self.saturated,
            "stale_attachment": self.stale_attachment,
            "warning": self.warning[:200],
            "composer_text": self.composer_text[:200],
            "observed": self.observed,
        }


@dataclass(frozen=True)
class SessionEstablishment:
    """The result of attempting to establish a Kalpavriksha-owned, named
    reasoning session. `ok=False` is `Provider = UNSAFE` in the mission's
    own vocabulary — the caller's job is to treat it exactly like any
    other provider failure (exclude, try the next ranked candidate),
    never to proceed anyway.

    `reused` distinguishes "found and opened the existing
    `DEDICATED_SESSION_NAME` conversation" from "created a new one this
    call" — surfaced in `ProviderResult.detail` so a live acceptance run
    can state, not merely assume, which one happened. `renamed` is only
    meaningful when `reused` is `False`: whether the freshly created
    conversation was successfully renamed to `DEDICATED_SESSION_NAME`
    (and will therefore be findable by exact name on a future call) —
    `False` here is not a call failure, only a note that *reuse* will not
    yet work next time."""

    ok: bool
    reason: str = ""
    session_marker: str = ""
    reused: bool = False
    renamed: bool = False
    #: What the window said about this conversation just before the
    #: prompt is written into it.
    health: SessionHealth = SessionHealth()
    #: True when a saturated conversation was retired and a fresh one was
    #: established in its place during this same call.
    rotated: bool = False


def build_session_marker(provider_label: str) -> str:
    """`"Kalpavriksha Reasoning — <session identifier>"` — the mission's
    own required inspectable identity, embedded directly in every
    submitted prompt's own text regardless of whether the conversation
    itself is a reused or freshly created `DEDICATED_SESSION_NAME`
    session. This is *per call*, not per conversation: the conversation
    persists and is reused, but each individual reasoning request still
    carries its own unique, timestamped identity in the visible prompt
    text, so the founder can tell separate requests inside the same
    persistent conversation apart. Generated locally, not threaded
    through the Broker/Planner (neither carries a mission/task id down to
    `ModelProvider.complete()` today, and this module does not add a new
    parameter to that frozen path to get one)."""
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    short_id = uuid.uuid4().hex[:8]
    return f"Kalpavriksha Reasoning — {provider_label} · {stamp} · {short_id}"


class ReasoningSessionManager:
    """Finds or creates the one persistent, named, Kalpavriksha-owned
    `DEDICATED_SESSION_NAME` reasoning conversation inside one
    already-focused desktop application window, before any reasoning
    provider ever writes a prompt into it.

    Composes existing `UiaAutomationBridge`/`MouseController`/
    `KeyboardController` primitives — no new automation layer.
    Constructed with the same objects a `DesktopAppReasoningProvider`
    already holds, so no additional Desktop Executive surface is
    introduced.
    """

    def __init__(self, uia: Any, mouse: Any) -> None:
        self._uia = uia
        self._mouse = mouse
        #: Provider labels whose `DEDICATED_SESSION_NAME` conversation has
        #: been observed saturated. Never looked up by name again while
        #: this manager lives -- otherwise the very next call would find
        #: and reopen the conversation we just decided was unusable.
        #:
        #: In-process, deliberately. The named conversation is discovered
        #: by its visible title, and nothing here writes a marker into the
        #: application to say "retired". A later process therefore finds
        #: the same saturated conversation once, observes the same
        #: warning, and rotates again -- one wasted click, self-correcting,
        #: and far cheaper than teaching this manager to rename or delete
        #: conversations in the founder's own window.
        self._retired: set[str] = set()

    def establish(self, window: dict, provider_label: str, keyboard: Any) -> SessionEstablishment:
        """The public entry point — kept named `establish()` for
        `DesktopAppReasoningProvider.complete()`'s own existing call
        site. Implemented as `find_named_session()` →
        `open_named_session()` on a hit, or `create_named_session()` on
        a miss — see each method's own docstring."""
        handle = window["handle"]
        marker = build_session_marker(provider_label)

        # Best-effort, generic, and idempotent: if this application exposes
        # a distinct "Chat" section separate from a coding-agent/work one,
        # switch to it before doing anything else. Coding agents are for
        # coding only — this is what keeps every step below from ever
        # operating inside a coding-agent section merely because that
        # section happened to be showing when the window was focused.
        # Absence of any such section is not an error: most applications
        # (including Perplexity Desktop's own single unified surface) have
        # only one, and this call is then a no-op.
        self._navigate_to_chat_section(handle)

        opened = self._open_or_create(handle, provider_label, keyboard, marker)
        if not opened.ok:
            return opened

        # PRE-FLIGHT. Before a single character is written, ask the
        # application what state the conversation we are about to use is
        # actually in. The founder watched Kalpavriksha keep sending into
        # a conversation that was visibly telling it to stop.
        health = self.inspect_session(handle)
        if health.usable:
            return dataclasses.replace(opened, health=health)

        # Not usable. This conversation is finished as a transport, and
        # saying so costs nothing that matters: the mission's meaning
        # lives in Founder Intent, requirements, Evidence and
        # MissionProgress, never in a provider's chat history.
        self.retire(provider_label)

        if not opened.reused:
            # It was already brand new and still is not usable -- an
            # attachment that survived a new conversation, most likely.
            # Creating a second one would prove nothing the first did not.
            return SessionEstablishment(
                False, f"{SESSION_SATURATED}: {self._unusable_reason(health)}", health=health,
            )

        # ONE governed rotation. Not a loop: if the fresh conversation
        # cannot be proven healthy either, this provider is unusable for
        # this attempt and the ladder asks the next one. Clicking "New
        # chat" until something looks right is how an adapter ends up
        # filling a founder's sidebar.
        fresh = self.create_named_session(handle, keyboard, marker, rename=False)
        if not fresh.ok:
            return fresh
        after = self.inspect_session(handle)
        if not after.usable:
            return SessionEstablishment(
                False,
                f"{SESSION_SATURATED}: a fresh conversation was created and is "
                f"still not usable ({self._unusable_reason(after)})",
                health=after,
            )
        return dataclasses.replace(fresh, health=after, rotated=True)

    def _open_or_create(
        self, handle: int, provider_label: str, keyboard: Any, marker: str,
    ) -> SessionEstablishment:
        """Find-and-open the named conversation, or create one -- unchanged
        behaviour, lifted out so `establish()` reads as what it now is:
        get a conversation, then check it is fit to use."""
        if provider_label not in self._retired:
            existing = self.find_named_session(handle)
            if existing is not None:
                if not self.open_named_session(handle, existing):
                    return SessionEstablishment(
                        False,
                        f"{ISOLATION_UNVERIFIED}: found the existing {DEDICATED_SESSION_NAME!r} "
                        "conversation but could not open it",
                    )
                time.sleep(_POST_CREATE_SETTLE_SECONDS)
                return SessionEstablishment(True, "", marker, reused=True, renamed=True)

        return self.create_named_session(handle, keyboard, marker)

    # ---- provider SESSION health (never provider health) ---------------

    def retire(self, provider_label: str) -> None:
        """This application's named conversation must not be used again."""
        self._retired.add(provider_label)

    def is_retired(self, provider_label: str) -> bool:
        return provider_label in self._retired

    def inspect_session(self, handle: int) -> SessionHealth:
        """One look at the window before writing into it.

        Never raises. An unreadable window returns `observed=False` with
        nothing claimed either way -- which is the honest answer, and is
        not treated as ill health: the write/submit/read path downstream
        verifies every one of its own steps and does not depend on this
        succeeding. What this exists to catch is the case where the
        application *is* readable and is plainly saying the conversation
        is spent.
        """
        try:
            return self._inspect(handle)
        except Exception:  # noqa: BLE001
            # "Never raises" has to be true, not stated. The automation
            # stack below raises `_ctypes.COMError` for a window that
            # closed or an element that went stale mid-read, and that is
            # outside this module's declared vocabulary -- a health check
            # that can kill the call it was meant to protect is worse
            # than no health check.
            logging.debug("session inspection failed", exc_info=True)
            return SessionHealth()

    def _inspect(self, handle: int) -> SessionHealth:
        regions = self._text_regions(handle)
        warning = ""
        for text in regions:
            lowered = text.lower()
            if any(phrase in lowered for phrase in SESSION_SATURATION_VOCABULARY):
                warning = text.strip()
                break
        attachment = self._find_by_vocabulary(handle, STALE_ATTACHMENT_VOCABULARY) is not None
        return SessionHealth(
            saturated=bool(warning),
            stale_attachment=attachment,
            warning=warning,
            composer_text=self._read_composer(handle),
            observed=bool(regions),
        )

    @staticmethod
    def _unusable_reason(health: SessionHealth) -> str:
        if health.saturated and health.stale_attachment:
            return f"saturated, and a stale attachment is still on it: {health.warning!r}"
        if health.saturated:
            return f"the application says this conversation is spent: {health.warning!r}"
        return "a previous request's attachment is still on this conversation"

    def _text_regions(self, handle: int) -> tuple[str, ...]:
        try:
            snapshot = self._uia.snapshot_text_regions(handle)
        except (UiaUnavailable, UiaTargetNotFound, OSError):
            return ()
        return tuple(str(text) for text in snapshot.values() if text)

    def _read_composer(self, handle: int) -> str:
        try:
            return str(self._uia.read_text(self._uia.find_composer(handle)) or "")
        except (UiaUnavailable, UiaTargetNotFound, OSError):
            return ""

    def find_named_session(self, handle: int):
        """Exact-name search for `DEDICATED_SESSION_NAME` — never a
        substring match. Real, live-found risk this guards against: a
        substring search for this exact phrase matched an unrelated
        historical conversation during this session's own knowledge-
        acquisition work (`Kalpavriksha Reasoning — ChatGPT Desktop ·
        ...`-style prior identities, and any future `"...Kalpavriksha
        Reasoning..."`-titled conversation, would all wrongly match a
        substring search). Returns `None`, never raises, when nothing
        matches — a miss here is the normal, expected case on the very
        first call for any application."""
        try:
            return self._uia.find(handle, name_exact=DEDICATED_SESSION_NAME, visible_only=True, retries=0)
        except (UiaTargetNotFound, UiaUnavailable):
            return None

    def open_named_session(self, handle: int, element) -> bool:
        """Invoke the already-resolved, exact-name-matched
        `DEDICATED_SESSION_NAME` element via the existing generic
        `click()` primitive — no new mechanism, and no re-verification
        of the name here (the caller already resolved it exactly)."""
        try:
            return self._uia.click(element, self._mouse)
        except (UiaUnavailable, UiaTargetNotFound):
            return False

    def create_named_session(
        self, handle: int, keyboard: Any, marker: str, rename: bool = True,
    ) -> SessionEstablishment:
        """No existing `DEDICATED_SESSION_NAME` conversation was found —
        create one via the existing generic 'start a new conversation'
        vocabulary search (unchanged from the prior architecture: the
        verified click *is* the isolation guarantee, regardless of
        whatever draft content the resulting composer happens to show —
        see this module's own docstring, correction 3), then make a
        best-effort attempt to rename it to `DEDICATED_SESSION_NAME` so a
        *future* call's `find_named_session()` can reuse it.

        Renaming is best-effort and its failure is **not** fatal to this
        call. That statement was briefly reversed, and reversing it was a
        mistake worth recording so it is not repeated.

        The reasoning was: rename failed on perplexity-desktop and
        kimi-desktop, so those providers must be refused rather than
        allowed to type into an "anonymous" chat. The measurement was
        real; the inference was not. It conflated *not named exactly
        `DEDICATED_SESSION_NAME`* with *unidentified*, and turned
        `can_rename_chat: UNKNOWN` — a question nobody has answered for
        those applications — into a settled "unsupported".

        What the live observation actually shows, in Kimi Desktop's own
        conversation list:

            'Short Gardening App Names'        <- Kalpavriksha's own run
            'KALPAVRIKSHA_KIMI_FINAL_OK'       <- Kalpavriksha's own run
            'Bank Nifty Scalping Checklist'    <- the founder's
            'Python vs Rust'                   <- the founder's

        The application auto-titles a conversation from its first
        message. A conversation this manager created, carrying this
        call's `[Kalpavriksha Reasoning — ...]` marker as its first
        message, is therefore neither anonymous nor the founder's — which
        is exactly the strategy `app_knowledge.catalog` already records
        for both ChatGPT and Kimi: *identity is embedded in the submitted
        prompt rather than by renaming the session*.

        So the fail-closed rule that matters is kept, and it is the one
        above: no new-session control means no verified-fresh
        conversation, and an already-active conversation is never reused.
        That is what protects the founder's own chats. A missing rename
        affordance only costs reuse on the next call.

        What remains genuinely open is per-application knowledge: Kimi
        exposes a `More` control on each conversation row whose menu the
        generic `RENAME_TRIGGER_VOCABULARY` does not match. Whether that
        is the supported rename path is UNKNOWN until observed, and it
        stays UNKNOWN — it belongs in `app_knowledge`, as data, not as a
        provider branch in here.
        """
        control = self._find_new_session_control(handle)
        if control is None:
            return SessionEstablishment(
                False,
                f"{ISOLATION_UNVERIFIED}: no generic 'start a new conversation' "
                "control was found in this application's window — isolation "
                "cannot be positively established, and an already-active "
                "conversation is never reused",
            )

        try:
            clicked = self._uia.click(control, self._mouse)
        except (UiaUnavailable, UiaTargetNotFound) as exc:
            return SessionEstablishment(
                False, f"{ISOLATION_UNVERIFIED}: could not invoke the new-session control ({exc})",
            )
        if not clicked:
            return SessionEstablishment(
                False, f"{ISOLATION_UNVERIFIED}: found a new-session control but could not invoke it",
            )

        time.sleep(_POST_CREATE_SETTLE_SECONDS)

        # `rename=False` is how a rotation avoids leaving two
        # conversations wearing the same name. The conversation just
        # retired may still hold `DEDICATED_SESSION_NAME`; giving the
        # replacement that name too would make `find_named_session()`'s
        # exact match ambiguous, which is the one thing this module's
        # exact-match discipline exists to prevent. Unnamed is not
        # unidentified: the marker in the first message still says whose
        # conversation this is, the strategy `app_knowledge.catalog`
        # already records for these applications.
        renamed = (
            self._rename_current_session(handle, keyboard, DEDICATED_SESSION_NAME)
            if rename else False
        )
        return SessionEstablishment(True, "", marker, reused=False, renamed=renamed)

    def _navigate_to_chat_section(self, handle: int) -> bool:
        """Best-effort: click an exact-match `"Chat"` section tab if one
        exists. Returns whether a click happened — callers should not treat
        `False` as a failure; it just means no such section was found,
        which is the normal case for a single-purpose chat application."""
        try:
            return self._navigate(handle)
        except Exception:  # noqa: BLE001
            logging.debug("chat-section navigation was not possible", exc_info=True)
            return False

    def _navigate(self, handle: int) -> bool:
        try:
            control = self._uia.find(handle, name_exact=CHAT_SECTION_LABEL, visible_only=True, retries=0)
        except (UiaTargetNotFound, UiaUnavailable):
            return False
        try:
            clicked = self._uia.click(control, self._mouse)
        except (UiaUnavailable, UiaTargetNotFound):
            return False
        if clicked:
            time.sleep(_POST_CREATE_SETTLE_SECONDS)
        return clicked

    def _find_new_session_control(self, handle: int):
        return self._find_by_vocabulary(handle, NEW_SESSION_VOCABULARY)

    def _find_by_vocabulary(self, handle: int, vocabulary: tuple[str, ...]):
        for phrase in vocabulary:
            try:
                return self._uia.find(handle, name_contains=phrase, visible_only=True, retries=0)
            except (UiaTargetNotFound, UiaUnavailable):
                continue
        return None

    def _rename_current_session(self, handle: int, keyboard: Any, new_name: str) -> bool:
        """Best-effort rename of the currently-open conversation — see
        this module's own docstring for the full design. Tries a direct
        rename control first (`RENAME_ACTION_VOCABULARY`); if none is
        visible, tries a 'more options'-style trigger
        (`RENAME_TRIGGER_VOCABULARY`) and re-searches for the rename
        action inside whatever it reveals. Once invoked, writes
        `new_name` into whatever element real OS keyboard focus lands on
        (`get_focused_element_in_window()` — safety-checked to belong to
        this window, never assumed) and confirms with Enter. Returns
        whether `new_name` is positively confirmed findable by exact
        name afterward — never raises; a failure at any step simply
        returns `False`.

        That last sentence was a claim rather than a fact until a live
        run proved otherwise: `SetFocus()` on a rename field that had
        already closed raised `_ctypes.COMError` out of this best-effort
        step, through `complete()`, and ended the mission. Losing the
        rename costs reuse on a future call. Losing the mission costs the
        founder the work.
        """
        try:
            return self._rename(handle, keyboard, new_name)
        except Exception:  # noqa: BLE001
            logging.debug("rename was not possible", exc_info=True)
            return False

    def _rename(self, handle: int, keyboard: Any, new_name: str) -> bool:
        action = self._find_by_vocabulary(handle, RENAME_ACTION_VOCABULARY)
        if action is None:
            trigger = self._find_by_vocabulary(handle, RENAME_TRIGGER_VOCABULARY)
            if trigger is None:
                return False
            try:
                if not self._uia.click(trigger, self._mouse):
                    return False
            except (UiaUnavailable, UiaTargetNotFound):
                return False
            time.sleep(_POST_CREATE_SETTLE_SECONDS)
            action = self._find_by_vocabulary(handle, RENAME_ACTION_VOCABULARY)
            if action is None:
                return False

        try:
            if not self._uia.click(action, self._mouse):
                return False
        except (UiaUnavailable, UiaTargetNotFound):
            return False
        time.sleep(_POST_CREATE_SETTLE_SECONDS)

        try:
            focused = self._uia.get_focused_element_in_window(handle)
        except (UiaUnavailable, UiaTargetNotFound):
            return False

        try:
            written = self._uia.write_text(focused, new_name, keyboard, append=False, mouse=self._mouse)
        except (UiaUnavailable, UiaTargetNotFound):
            written = False
        if not written:
            return False

        keyboard.press("enter")
        time.sleep(_POST_CREATE_SETTLE_SECONDS)

        return self.find_named_session(handle) is not None
