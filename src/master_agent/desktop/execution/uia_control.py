"""Universal Autonomous Desktop Executive — Windows UI Automation bridge.

`execution/text_control.py`'s own module docstring named this the
foundation's clearest remaining gap: classic Win32 messaging
(`WM_GETTEXT`/`WM_SETTEXT`) cannot see into anything Chromium (Electron)
or WinUI/XAML renders, because that content never becomes a classic child
window at all. Confirmed live against Claude Desktop: its window's only
direct children are `Chrome_RenderWidgetHostHWND` and a D3D composition
window — no classic control exists to target.

**What this module is.** A real, minimal bridge to `IUIAutomation` — the
one thing Windows guarantees is populated for accessible content
regardless of rendering technology, because it's the same tree a screen
reader consumes. Via `comtypes` (pure Python, zero native compilation,
already an installed transitive dependency of `pycaw`/the voice pipeline,
and already present in `packaging/kalpavriksha.spec`'s `hiddenimports`),
not hand-rolled `ctypes` COM vtables: `IUIAutomation` is a large,
many-method interface, and getting a vtable slot order wrong by hand is a
real, hard-to-debug risk this module avoids by generating the wrapper
from the real, system-registered `UIAutomationCore.dll` type library —
the exact method order Windows itself defines, not a guess.

**What this module is not.** Not `pywinauto`, not `FlaUI` — no .NET
runtime, no second object model imposed over this package's own
`ControlInfo`/`ExecutionResult` conventions. This is the marshaling layer
to Windows' own native accessibility API, nothing more, in the same spirit
`win32_backends.py` is the marshaling layer to raw Win32.

**Confirmed live, this session, against Claude Desktop's real composer**
(named "Prompt" in its own accessibility tree): element resolution by
name within one window, focus, real keystroke input, text read-back
verification *before* submitting, and reading the real response back
afterward — end to end, no fabricated success at any step.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from typing import Any

if sys.platform != "win32":  # pragma: no cover — this repository targets win32
    raise ImportError("uia_control is only available on Windows")

# `comtypes.client.gen_dir` must be set *before* the first `GetModule`/
# `comtypes.gen` import: comtypes' default generated-wrapper cache lives
# inside its own package directory, which an installed (or frozen) build
# has no guarantee of write access to. `UIAutomationCore.dll`'s type
# library is a Windows system component — nothing here ships it — so
# generation only ever needs a writable *cache* location, computed once
# per founder account.
_GEN_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA") or tempfile.gettempdir(),
    "Kalpavriksha", "comtypes_gen",
)
os.makedirs(_GEN_DIR, exist_ok=True)

import comtypes  # noqa: E402
import comtypes.client  # noqa: E402

comtypes.client.gen_dir = _GEN_DIR
comtypes.client.GetModule("UIAutomationCore.dll")
from comtypes.gen import UIAutomationClient as _UIA  # noqa: E402

# ---- UIA constants (from the real, generated type library — not guessed) --

_TREE_SCOPE_DESCENDANTS = 4
_CONTROL_TYPE_PROPERTY_ID = 30003
_IS_TEXT_PATTERN_AVAILABLE_PROPERTY_ID = 30040
_IS_VALUE_PATTERN_AVAILABLE_PROPERTY_ID = 30045
_IS_ENABLED_PROPERTY_ID = 30010
_IS_OFFSCREEN_PROPERTY_ID = 30022
_INVOKE_PATTERN_ID = 10000
_VALUE_PATTERN_ID = 10002
_TEXT_PATTERN_ID = 10014
#: `snapshot_elements()`'s own two bonus, best-effort facts — verified
#: against the real, installed `UIAutomationCore.dll` type library the same
#: way every constant above already was (never guessed): a "current
#: selected tab" is only ever knowable when an element both supports
#: `SelectionItemPattern` at all *and* reports itself selected.
_IS_SELECTION_ITEM_PATTERN_AVAILABLE_PROPERTY_ID = 30036
_SELECTION_ITEM_IS_SELECTED_PROPERTY_ID = 30079
#: `WindowPattern.IsModal` — the one generic, evidence-based signal this
#: module has for "this nested Window-typed element is a dialog, not just
#: another window" (Desktop Intelligence's own DIALOG classification).
_WINDOW_IS_MODAL_PROPERTY_ID = 30077

#: Real UIA ControlType IDs (from the same generated type library as every
#: property/pattern ID above) that Desktop Intelligence's semantic
#: classification layer (`desktop/intelligence/classification.py`) matches
#: directly — public (no leading underscore) because that higher layer
#: imports them rather than re-declaring its own copy of Windows' own
#: numbering.
CONTROL_TYPE_BUTTON = 50000
CONTROL_TYPE_COMBO_BOX = 50003
CONTROL_TYPE_EDIT = 50004
CONTROL_TYPE_MENU = 50009
CONTROL_TYPE_MENU_BAR = 50010
CONTROL_TYPE_MENU_ITEM = 50011
CONTROL_TYPE_TAB = 50018
CONTROL_TYPE_TAB_ITEM = 50019
CONTROL_TYPE_SPLIT_BUTTON = 50031
CONTROL_TYPE_WINDOW = 50032

#: A composer/input box is a small, focusable, text-bearing region docked
#: in roughly the bottom half of its window — real evidence from Claude
#: Desktop's own "Prompt" element, used as a *last-resort* heuristic only
#: when no `name`/`automation_id` hint narrows the search. This is a
#: structural inference over real, UIA-reported element geometry —
#: categorically different from inventing a screen coordinate, and
#: documented as approximate: a caller that knows the real name/
#: AutomationId should always pass it instead.
#:
#: Widened from the original (0.30 / 0.50), then again from (0.40 / 0.40),
#: with real, live evidence found this session: an auto-expanding composer
#: holding a genuinely long reasoning prompt (not the short strings the
#: heuristic was first tuned against) grew to 32% of Claude Desktop's
#: window height, and Kimi's own composer sits at 44% from the top — both
#: would have been wrongly rejected under the original bounds. Still tight
#: enough to reject unrelated large regions (a "Work with ChatGPT"
#: dropdown observed at 186% of window height) and top-anchored chrome (a
#: menu bar observed at 4% height, 0% top).
#:
#: Widened a second time, live, this session: a genuinely maximized
#: ChatGPT Desktop window (confirmed via real Win32 `is_maximized` state,
#: not assumed) still rejected its own composer at 0.40 — its accumulated
#: draft content put its *visible, on-window* height at 48.8% of the
#: window. A window this modestly sized (687px tall, even fully
#: maximized) leaves a multi-paragraph composer legitimately occupying
#: nearly half the screen; that is real geometry, not a defect to paper
#: over with an ever-larger number chasing one draft's exact length. 0.55
#: keeps meaningful headroom below that same window's own unrelated large
#: regions (a "Codex" panel observed at 98% of window height) while no
#: longer rejecting a real, maximized, ordinary composer.
_COMPOSER_MAX_HEIGHT_FRACTION = 0.55
_COMPOSER_MIN_TOP_FRACTION = 0.40

#: `write_text()`'s keystroke-vs-paste threshold. Below this, real
#: character-by-character `SendInput` keystrokes (the more faithful
#: "founder typed this" interaction). At/above it, `KeyboardController.
#: paste()` (clipboard write + Ctrl-V) — found live: a real ~6KB reasoning
#: prompt typed via `SendInput` failed read-back verification across every
#: desktop composer tried, where paste is a single, near-instant event.
_PASTE_THRESHOLD_CHARS = 200

#: `write_text()`'s clear-before-type step (`ctrl+a` + `delete`) previously
#: had no verification at all — found live, this session, reproducing the
#: real Kimi Desktop failure step by step: composer content stayed
#: byte-for-byte identical through `SetFocus()`, `ctrl+a`, `delete`, and
#: 800ms afterward. The clear action's own API calls "succeeding" (no
#: exception) was never evidence the composer was actually emptied. A
#: genuinely-cleared composer shows either nothing or a short placeholder
#: ("Ask me. Task me." / "Type / for commands" — real placeholder text
#: found live in two different applications, 17 and 20 characters) — real
#: leftover content that needs clearing runs far longer, matching the
#: exact same threshold philosophy `reasoning_session.py`'s own
#: `_MAX_FRESH_COMPOSER_CHARS` already uses for the identical judgment.
_MAX_CLEARED_CHARS = 80
#: How much rendered text must match the submitted prompt verbatim before
#: `find_new_content()` treats a region as part of that prompt's own echo
#: rather than as a reply. A genuine answer may well repeat a word, a
#: capability name or a short phrase from the question, and excluding it
#: for that would throw away real replies. A block this long appearing
#: verbatim inside the prompt is not a coincidence: it is the prompt,
#: rendered as one of the many blocks a chat UI splits a long message
#: into. Sits just above the two real placeholder lengths recorded above
#: (17 and 20 characters), so composer chrome cannot reach it either.
_PROMPT_FRAGMENT_MIN_CHARS = 24
#: A generation-in-progress notice is new content below this turn's own
#: prompt, so nothing structural distinguishes it from the reply -- and
#: once the reply is reconstructed from ALL such regions rather than one,
#: it lands inside the answer. Observed live, returned as an entire
#: three-name reply: `'ChatGPT is responding'`.
#:
#: These are STATUS phrasings, never answer content -- the same
#: distinction `app_knowledge.acquisition._LOADING_KEYWORDS` already
#: draws, extended with the generating-now wording that list did not
#: need. A short region that IS one of these, in full, is chrome; the
#: match is deliberately whole-string so a reply that happens to discuss
#: loading is untouched.
_TRANSIENT_STATUS = (
    "reconnecting", "getting ready", "loading", "connecting",
    "is responding", "thinking", "generating", "stop generating",
    "regenerate", "searching the web",
)


@dataclass
class ResponseTurn:
    """What one `_await_response()` call has established about its turn.

    Deliberately mutable, deliberately tiny, and deliberately owned by the
    caller for the duration of a single wait — not conversation state, not
    a subsystem, and never shared between two waits.

    It exists because a turn that has been positively anchored can stop
    being anchorable. Observed live: this call's prompt was located on
    polls 1-2, ChatGPT then scrolled the transcript, and from poll 3 the
    prompt was no longer anywhere in the accessibility tree. Each poll
    re-derived everything from scratch, so the wait forgot it had ever
    known where its own turn began and fell back to text uniqueness.

    Note what is NOT kept here: the numeric floor. A screen coordinate
    from a viewport that scrolls is not a durable boundary, and carrying
    one forward would be a worse answer than forgetting.
    """

    anchored: bool = False


def _is_transient_status(normalised: str) -> bool:
    """Whether this region is a generation/connection notice rather than
    words the model produced. Whole-string, case-insensitive, and bounded
    in length: a real answer is not one of these phrases."""
    text = (normalised or "").strip().lower().rstrip(".…")
    if not text or len(text) > 40:
        return False
    # Containment, because the application prefixes its own name:
    # 'ChatGPT is responding'. The length bound above is what keeps this
    # from reaching a real answer -- a reply discussing loading runs far
    # longer than a status line.
    return any(phrase in text for phrase in _TRANSIENT_STATUS)
_CLEAR_VERIFY_ATTEMPTS = 4
_CLEAR_VERIFY_DELAY_SECONDS = 0.25
#: Bounded — the clear *action* itself (`ctrl+a`+`delete`) is retried at
#: most this many times before failing closed, never indefinitely.
_CLEAR_ACTION_ATTEMPTS = 2

#: Best-effort focus verification (see `_verify_focus()`) — bounded, and
#: never a hard requirement on its own: some applications/controls do not
#: cleanly support `GetFocusedElement()`/`CompareElements()` for reasons
#: unrelated to whether the write will actually work, so an inconclusive
#: result proceeds rather than blocks. Retrying `SetFocus()` a couple of
#: times when focus is *positively confirmed* not to have landed is cheap
#: and catches a real, generic class of timing issue without inventing
#: any application-specific logic.
_FOCUS_VERIFY_ATTEMPTS = 3
_FOCUS_VERIFY_DELAY_SECONDS = 0.1

_WHITESPACE_RUN = re.compile(r"\s+")


def _normalize_whitespace(text: str) -> str:
    """Collapse every run of whitespace (spaces, tabs, blank lines) to a
    single space — see `_verify_readback`'s own docstring for the real,
    live-found paste behavior this absorbs. A rich-text `contenteditable`
    composer reflows plain text on paste: blank lines collapsed, JSON-style
    indentation moved or lost — legitimate rendering, not data loss, and
    not one fixed transformation worth chasing case by case. Comparing on
    words-and-order rather than exact whitespace still catches a genuine
    corruption (wrong, missing, or reordered text)."""
    return _WHITESPACE_RUN.sub(" ", text).strip()


_com_initialized_threads: set[int] = set()


def _ensure_com_initialized() -> None:
    """COM requires one `CoInitialize` per thread, and a redundant call is
    a harmless no-op (`S_FALSE`) — but `CoUninitialize` while COM objects
    from this thread are still alive is a real bug, so this process
    deliberately never calls it: COM stays initialized for a thread's
    natural lifetime, the same posture any long-running COM-using desktop
    application takes."""
    thread_id = threading.get_ident()
    if thread_id in _com_initialized_threads:
        return
    comtypes.CoInitialize()
    _com_initialized_threads.add(thread_id)


class UiaUnavailable(RuntimeError):
    """UIA could not be reached at all (COM/DLL failure) — distinct from
    `UiaTargetNotFound`, which means UIA works but nothing matched."""


class UiaTargetNotFound(RuntimeError):
    """UIA is working; no element matched the given, scoped search."""


@dataclass(frozen=True)
class UiaElementInfo:
    """One UIA element, resolved to enough identity to act on and to
    explain the match afterward — the same provenance discipline
    `text_control.py::ControlInfo` already established, extended with
    the bounding-rect center a caller can hand to a coordinate-based
    action (`ClickControlAction`'s own documented "a caller already
    resolved a specific point" contract)."""

    name: str
    automation_id: str
    control_type: int
    is_enabled: bool
    is_focusable: bool
    has_value_pattern: bool
    has_text_pattern: bool
    center_x: int
    center_y: int
    height: int


@dataclass(frozen=True)
class UiaElementSnapshot:
    """One UIA element's full, read-only observable state — the batch
    counterpart to `UiaElementInfo`/`describe()`: every descendant in a
    window, not just one caller-resolved target. `desktop/intelligence/`'s
    observation layer is this type's only consumer; nothing here carries
    or exposes any way to act on the element it describes.

    `is_selected`/`is_modal` are `None`, not `False`, when the underlying
    pattern/property could not be read at all — the same "silence is not
    evidence of absence" discipline `Observation`/`Fact` already hold
    elsewhere in this codebase, extended to a plain dataclass field here
    since this type carries no separate confidence wrapper of its own
    (that is `ElementObservation`'s job, one layer up)."""

    name: str
    automation_id: str
    control_type: int
    is_enabled: bool
    is_focusable: bool
    is_offscreen: bool
    is_selected: bool | None
    is_modal: bool | None
    has_value_pattern: bool
    has_text_pattern: bool
    bounds: tuple[int, int, int, int]
    text: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "automation_id": self.automation_id,
            "control_type": self.control_type, "is_enabled": self.is_enabled,
            "is_focusable": self.is_focusable, "is_offscreen": self.is_offscreen,
            "is_selected": self.is_selected, "is_modal": self.is_modal,
            "has_value_pattern": self.has_value_pattern, "has_text_pattern": self.has_text_pattern,
            "bounds": list(self.bounds), "text": self.text,
        }


class UiaAutomationBridge:
    """One `IUIAutomation` instance, reused across calls (creating it is
    real COM overhead not worth paying per action). Every search is
    scoped to one already-resolved window handle — never desktop-wide,
    the same discipline `ClassicControlResolver` already holds."""

    def __init__(self) -> None:
        self._automation = None

    def _instance(self):
        if self._automation is None:
            _ensure_com_initialized()
            self._automation = comtypes.client.CreateObject(
                _UIA.CUIAutomation, interface=_UIA.IUIAutomation
            )
        return self._automation

    def _root(self, window_handle: int):
        try:
            return self._instance().ElementFromHandle(window_handle)
        except Exception as exc:  # noqa: BLE001
            raise UiaUnavailable(f"could not reach UIA for window {window_handle}: {exc}") from exc

    def _descendants(self, root) -> list:
        automation = self._instance()
        condition = automation.CreateTrueCondition()
        found = root.FindAll(_TREE_SCOPE_DESCENDANTS, condition)
        return [found.GetElement(i) for i in range(found.Length)]

    def _info(self, element) -> UiaElementInfo | None:
        try:
            rect = element.CurrentBoundingRectangle
            height = rect.bottom - rect.top
            if height <= 0:
                return None
            has_value = bool(element.GetCurrentPropertyValue(_IS_VALUE_PATTERN_AVAILABLE_PROPERTY_ID))
            has_text = bool(element.GetCurrentPropertyValue(_IS_TEXT_PATTERN_AVAILABLE_PROPERTY_ID))
            return UiaElementInfo(
                name=element.CurrentName or "",
                automation_id=element.CurrentAutomationId or "",
                control_type=element.CurrentControlType,
                is_enabled=bool(element.GetCurrentPropertyValue(_IS_ENABLED_PROPERTY_ID)),
                is_focusable=bool(element.CurrentIsKeyboardFocusable),
                has_value_pattern=has_value,
                has_text_pattern=has_text,
                center_x=(rect.left + rect.right) // 2,
                center_y=(rect.top + rect.bottom) // 2,
                height=height,
            )
        except Exception:  # noqa: BLE001 — a single unreadable element is skipped, not fatal
            return None

    # ---- resolution ------------------------------------------------------

    def find(
        self,
        window_handle: int,
        *,
        name_contains: str | None = None,
        name_exact: str | None = None,
        automation_id: str | None = None,
        visible_only: bool = False,
        retries: int = 2,
        retry_delay_seconds: float = 0.4,
    ):
        """Resolve one element, retried a bounded number of times
        (Section 7's "target not found / target changed" recovery mode —
        a UIA tree can genuinely still be settling right after a window
        gains focus). Returns the raw COM element (for `read`/`write`/
        `click`/`verify`) — callers needing only its identity should use
        `describe()` instead.

        `name_exact` (case-insensitive whole-name match) exists alongside
        `name_contains` (substring) for exactly the ambiguity substring
        matching can hit: a short, generic tab label like `"Chat"` is also
        a substring of `"New chat"`, `"Chats"`, `"Pin chat"`, and similar —
        real names found live, this session, in real applications' own
        UIA trees. A caller that knows the target's name precisely should
        ask for it precisely rather than accept whichever same-substring
        match a tree happens to list first.

        `visible_only` (default `False`, preserving every existing
        caller's behavior) skips any candidate UIA reports as off-screen
        (`IsOffscreen`) before matching it. Found live, this session: a
        Chromium/Electron app can keep an *inactive* tab's own elements
        (a different tab's own "New chat" button, sharing the same name as
        the active tab's) mounted in the accessibility tree, merely
        hidden — `FindAll()` returns both, and a name match alone cannot
        tell which one is actually on screen. Opt-in, not the default: a
        caller resolving a real target the founder can see on screen
        should ask for exactly that.
        """
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                root = self._root(window_handle)
                candidates = self._descendants(root)
            except UiaUnavailable as exc:
                last_error = exc
                time.sleep(retry_delay_seconds)
                continue

            for element in candidates:
                try:
                    el_name = element.CurrentName or ""
                    el_aid = element.CurrentAutomationId or ""
                except Exception:  # noqa: BLE001
                    continue
                if automation_id and el_aid != automation_id:
                    continue
                if name_contains and name_contains.lower() not in el_name.lower():
                    continue
                if name_exact and el_name.lower() != name_exact.lower():
                    continue
                if not automation_id and not name_contains and not name_exact:
                    continue
                if visible_only:
                    try:
                        if bool(element.GetCurrentPropertyValue(_IS_OFFSCREEN_PROPERTY_ID)):
                            continue
                    except Exception:  # noqa: BLE001
                        continue  # cannot confirm on-screen -- do not guess it is
                return element

            if attempt < retries:
                time.sleep(retry_delay_seconds)

        if last_error is not None:
            raise UiaUnavailable(str(last_error))
        raise UiaTargetNotFound(
            f"no element in window {window_handle} matched "
            f"name_contains={name_contains!r} name_exact={name_exact!r} "
            f"automation_id={automation_id!r}"
        )

    def find_composer(self, window_handle: int, retries: int = 2, retry_delay_seconds: float = 0.6):
        """Last-resort heuristic (see module docstring) for when a
        caller has no name/AutomationId hint: the smallest focusable,
        text-bearing element anchored in the bottom half of the window —
        confirmed live against Claude Desktop's own "Prompt" element.

        Retried the same bounded way `find()` already is (Section 7's
        "target not found / target changed" recovery mode). Found live
        against a genuinely cold-launched ChatGPT Desktop window, in an
        autonomous Planner-driven mission (not a manually-warmed-up test
        session): Chromium's accessibility tree can still be near-empty
        on the very first probe against a freshly-created window — the
        same lazy-activation behavior already documented for
        `ElementFromHandle` generally, previously only guarded for
        `find()`, not for this heuristic path. Without this, a fresh
        launch immediately followed by a type (exactly what an
        autonomous mission does, with no human pause in between) could
        fall through to the unverified keyboard fallback for no reason
        other than probing one moment too early.
        """
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                root = self._root(window_handle)
                win_rect = root.CurrentBoundingRectangle
                win_height = win_rect.bottom - win_rect.top
                if win_height <= 0:
                    raise UiaTargetNotFound(f"window {window_handle} has no usable bounding rectangle")

                candidates: list[tuple[Any, int]] = []
                for element in self._descendants(root):
                    try:
                        if not element.CurrentIsKeyboardFocusable:
                            continue
                        has_text = bool(element.GetCurrentPropertyValue(_IS_TEXT_PATTERN_AVAILABLE_PROPERTY_ID))
                        if not has_text:
                            continue
                        # Same class of bug `find()`'s own `visible_only`
                        # guards against, applied here unconditionally —
                        # there is no legitimate reason to ever resolve an
                        # off-screen element as "the composer": a
                        # Chromium/Electron app can keep an *inactive*
                        # tab's own composer mounted in the accessibility
                        # tree, merely hidden, and geometry alone cannot
                        # tell it apart from the one actually on screen.
                        if bool(element.GetCurrentPropertyValue(_IS_OFFSCREEN_PROPERTY_ID)):
                            continue
                        rect = element.CurrentBoundingRectangle
                        # Real, live-found measurement bug this clip
                        # guards against: a scrollable rich-text composer
                        # holding more content than fits on screen can
                        # report `CurrentBoundingRectangle` as its full
                        # *scrollable content* extent, not the clipped,
                        # on-window viewport a founder actually sees —
                        # confirmed live against ChatGPT Desktop's real
                        # composer, whose raw rect extended nearly 2x past
                        # its own maximized window's bottom edge. Clipping
                        # to the window's own bounds before measuring
                        # height is what makes this heuristic reason about
                        # what is actually visible, the same thing a
                        # founder looking at the screen would judge by.
                        height = min(rect.bottom, win_rect.bottom) - max(rect.top, win_rect.top)
                        if height <= 0 or height > win_height * _COMPOSER_MAX_HEIGHT_FRACTION:
                            continue
                        if rect.top < win_rect.top + win_height * _COMPOSER_MIN_TOP_FRACTION:
                            continue
                        candidates.append((element, height))
                    except Exception:  # noqa: BLE001
                        continue

                if candidates:
                    candidates.sort(key=lambda pair: pair[1])
                    return candidates[0][0]
            except UiaUnavailable as exc:
                last_error = exc

            if attempt < retries:
                time.sleep(retry_delay_seconds)

        if last_error is not None:
            raise UiaUnavailable(str(last_error))
        raise UiaTargetNotFound(
            f"no composer-shaped element found in window {window_handle} "
            "(smallest focusable, text-bearing, bottom-anchored region)"
        )

    def find_main_content(self, window_handle: int, retries: int = 2, retry_delay_seconds: float = 0.6):
        """The read-side counterpart to `find_composer()`: the largest
        text-bearing region in the window — a chat application's message/
        response area is reliably the biggest such region, confirmed
        live reading Claude Desktop's own response back after a real
        submitted prompt this session. Approximate for the same reason
        `find_composer()` is — a caller that knows the real name/
        AutomationId should pass it instead of relying on this. Retried
        for the same reason `find_composer()` now is.

        Live-found limitation this method still carries, not fixed here:
        "largest" is not the same as "the newly produced response" — a
        navigation sidebar can legitimately be the largest text-bearing
        region in a window, confirmed live against both ChatGPT Desktop
        and Kimi Desktop. `DesktopAppReasoningProvider._await_response()`
        no longer relies on this method for exactly that reason — see
        `snapshot_text_regions()`/`find_new_content()`, which distinguish
        "changed since the prompt was submitted" from "big." This method
        is kept, unchanged in its own behavior, for its other existing
        caller (`ReadWindowContentAction`), which wants "the biggest
        readable region" as a one-shot content read with no baseline to
        diff against."""
        for attempt in range(retries + 1):
            root = self._root(window_handle)
            best: tuple[Any, int] | None = None
            for element in self._descendants(root):
                try:
                    has_text = bool(element.GetCurrentPropertyValue(_IS_TEXT_PATTERN_AVAILABLE_PROPERTY_ID))
                    if not has_text:
                        continue
                    if bool(element.GetCurrentPropertyValue(_IS_OFFSCREEN_PROPERTY_ID)):
                        continue
                    rect = element.CurrentBoundingRectangle
                    height = rect.bottom - rect.top
                    if height < 200:  # smaller than any realistic content pane
                        continue
                    if best is None or height > best[1]:
                        best = (element, height)
                except Exception:  # noqa: BLE001
                    continue
            if best is not None:
                return best[0]
            if attempt < retries:
                time.sleep(retry_delay_seconds)
        raise UiaTargetNotFound(f"no text-bearing content region found in window {window_handle}")

    def _text_region_candidates(self, root, win_rect, min_height: int):
        """Shared scan behind `snapshot_text_regions()`/`find_new_content()`:
        every visible, text-bearing descendant at least `min_height` tall
        (clipped to the window's own bounds — see `find_composer()`'s own
        finding on why a raw, unclipped rect can lie about what is
        actually on screen), keyed by its own bounding rectangle. A
        bounding rect is not a stable, persistent identity the way an
        AutomationId would be, but real chat UIs were found live to keep
        a region's screen position fixed across a poll a few seconds
        apart even as its *content* changes underneath — good enough to
        correlate "the same region" between two snapshots without needing
        a live COM reference to survive that long.

        Excludes any keyboard-focusable element — real, live-found false
        positive this guards against: a composer's own empty-state
        placeholder text (e.g. "Message ChatGPT") reads as "changed" the
        moment a submitted prompt is cleared out, is short enough to win
        as the smallest changed region, and — being static placeholder
        text — trivially passes a stability check too, all before any
        real response has even appeared. `find_composer()` itself only
        ever matches focusable elements (that is what makes something a
        composer, not content); a genuine response region is a static
        text/document element, never an editable control. Excluding
        focusable candidates here is the structural mirror of that same
        distinction, not a guess specific to any one application."""
        regions: dict[tuple[int, int, int, int], tuple[Any, str]] = {}
        for element in self._descendants(root):
            try:
                if bool(element.CurrentIsKeyboardFocusable):
                    continue
                has_text = bool(element.GetCurrentPropertyValue(_IS_TEXT_PATTERN_AVAILABLE_PROPERTY_ID))
                if not has_text:
                    continue
                if bool(element.GetCurrentPropertyValue(_IS_OFFSCREEN_PROPERTY_ID)):
                    continue
                rect = element.CurrentBoundingRectangle
                height = min(rect.bottom, win_rect.bottom) - max(rect.top, win_rect.top)
                if height < min_height:
                    continue
                key = (rect.left, rect.top, rect.right, rect.bottom)
                regions[key] = (element, self.read_text(element))
            except Exception:  # noqa: BLE001
                continue
        return regions

    def snapshot_text_regions(self, window_handle: int, min_height: int = 8) -> dict[tuple[int, int, int, int], str]:
        """Read-only baseline: every visible, text-bearing region's
        current text, keyed by its own bounding rectangle. Call this
        right before submitting a prompt; hand the result to
        `find_new_content()` afterward to identify what actually changed —
        the generic signal for "a new assistant response appeared" that
        does not depend on a region merely being the largest one in the
        window (see `find_new_content()`'s own docstring for the live
        finding this replaces).

        `min_height` defaults low (8px) on real, live evidence: a short,
        genuine reply — confirmed live against ChatGPT Desktop, a
        single-line answer reading exactly "KALPAVRIKSHA_CHATGPT_FINAL_OK" —
        clipped to 19px tall, narrowly missing an earlier, untested 20px
        default and silently excluding the real response from
        consideration at all. This filter's job now is only to drop
        zero/negative-height or truly negligible elements; unlike
        `find_main_content()`'s old "must be the biggest pane" role, a
        small, precise region is exactly what this mechanism wants to be
        able to prefer (see `find_new_content()`'s own "smallest wins"
        rule)."""
        root = self._root(window_handle)
        win_rect = root.CurrentBoundingRectangle
        return {key: text for key, (_, text) in self._text_region_candidates(root, win_rect, min_height).items()}

    def find_new_content(
        self,
        window_handle: int,
        baseline: dict[tuple[int, int, int, int], str],
        exclude_text: str = "",
        min_height: int = 8,
    ):
        """The generic fix for a real, live-found response-discovery bug:
        `find_main_content()`'s "largest text-bearing region" heuristic
        picked a navigation sidebar (chat list, workspace nav, connection
        status) instead of the real, newly-produced assistant reply —
        confirmed live against both ChatGPT Desktop and Kimi Desktop,
        where a sidebar's accumulated list of prior chats is taller than
        a short new answer. Size was never the right signal; *change* is —
        persistent chrome (sidebars, toolbars, status text) reads the same
        before and after a response arrives, while the real response is,
        by definition, content that did not exist (or did not read this
        way) a moment ago.

        Compares every current visible, text-bearing region's *text*
        against the full set of text baseline (from
        `snapshot_text_regions()`, taken before submission) — not
        against baseline by *position*. A region is a candidate only if
        its text is non-empty, does not equal `exclude_text` (the
        submitted prompt — composers often stay visible with
        residual/echoed text), and did not read this way *anywhere* in
        the baseline snapshot. Among candidates, the *smallest* wins —
        the same "most specific match, not the broadest one" preference
        `find_composer()` already applies, so a small, precise new-reply
        element is preferred over a large enclosing scrollable pane that
        also happens to contain it. Returns `None` when nothing has
        genuinely changed yet — the caller's own bounded poll loop is
        what turns that into a timeout, not this method.

        **Content-set comparison, not position comparison — the first
        fix for a real, live-found bug specific to a *persistent,
        reused, multi-turn* conversation.** An earlier version of this
        method compared each region against `baseline` *by its own
        bounding rectangle* (`baseline.get(key)`): confirmed live against
        ChatGPT Desktop's own reused `"Kalpavriksha Reasoning"`
        conversation, once several exchanges had accumulated, a much
        *older* reply's on-screen position shifted between the baseline
        snapshot and the after-submission poll — its rectangle key no
        longer matched its own baseline entry, so it was wrongly treated
        as "not in baseline." Comparing against the *set* of all
        baseline text, regardless of position, absorbs that.

        **Prompt-anchored floor — a second, separate fix, needed even
        with the content-set comparison above.** Confirmed live, again
        against a growing `"Kalpavriksha Reasoning"` conversation: an
        even *older* reply — one that had scrolled entirely off-screen
        at the moment `baseline` was captured, and therefore was never
        recorded in it at all — scrolled back into view partway through
        a *later* poll and was accepted as new, since content-set
        membership alone cannot exclude something baseline never saw in
        the first place. The structural fix: locate this call's own
        just-submitted prompt (`exclude_text`) by its rendered text
        anywhere in the window, and only ever consider a candidate whose
        own top position is at or below that prompt's own bottom edge.
        In every chat UI this architecture targets, a response can only
        ever render *after* — meaning visually below — the request that
        produced it; nothing above the current prompt's own position can
        ever be this call's own answer, however baseline-membership or
        content-change comparisons might be confused by scrolling.
        Best-effort: if the prompt's own echo cannot be located (e.g.
        `exclude_text` is empty, or the composer has not yet visibly
        cleared into the transcript), the floor defaults to the window's
        own top edge and every candidate remains eligible — the same
        content-set comparison above is still in force either way.
        """
        root = self._root(window_handle)
        win_rect = root.CurrentBoundingRectangle
        exclude_norm = _normalize_whitespace(exclude_text)
        baseline_texts = {_normalize_whitespace(t) for t in baseline.values() if t and t.strip()}
        all_regions = self._text_region_candidates(root, win_rect, min_height)

        # **A long prompt is not one region -- a fourth fix, for a real,
        # live-found fabrication.**
        #
        # The floor below was anchored by finding a region whose text
        # EQUALS the submitted prompt. That holds for a one-line question.
        # It fails completely for a long one: a chat UI renders a large
        # message as many separate blocks -- one per line, per paragraph,
        # per table row -- and not one of them equals the whole.
        #
        # Confirmed live against ChatGPT Desktop with a 20,869-character
        # planning prompt, which carries the whole capability catalogue.
        # Every catalogue line came back as its own region. None equalled
        # `exclude_text`, so the floor fell back to the window top; none
        # was in `baseline`, because the prompt had only just been sent;
        # so the founder's own question became the candidate set, and the
        # shortest line of it -- `" Browser.OpenBrowserSession | args:
        # session_id"` -- was returned as the model's reply.
        #
        # The runner recorded that as a successful answer. It reached no
        # one only because a downstream expectation rejected it, and a
        # wrong answer caught by luck downstream is still a wrong answer.
        #
        # The rule that holds for any length: nothing that is literally a
        # piece of the question can be the answer to it. A region whose
        # text appears verbatim inside the submitted prompt is part of
        # this call's own echo -- it anchors the floor, and it can never
        # be a candidate. Short matches are ignored (a real reply may
        # legitimately repeat a word or a capability name); a fragment
        # long enough to be a rendered block of the prompt is not a
        # coincidence.
        prompt_floor = win_rect.top
        prompt_echo: set[str] = set()
        if exclude_norm:
            for key, (_element, text) in all_regions.items():
                if not text or not text.strip():
                    continue
                norm = _normalize_whitespace(text)
                if norm == exclude_norm or (
                    len(norm) >= _PROMPT_FRAGMENT_MIN_CHARS and norm in exclude_norm
                ):
                    prompt_floor = max(prompt_floor, key[3])
                    prompt_echo.add(norm)

        # **Nothing drawn on the composer is ever an answer -- a fourth
        # fix, for a real, live-found fabrication.**
        #
        # `_text_region_candidates()` already drops keyboard-focusable
        # elements precisely to keep a composer's empty-state placeholder
        # out of this set. That is necessary and it is not sufficient: a
        # real app draws that placeholder as a SEPARATE, non-focusable
        # label sitting on top of the focusable input, so it survives the
        # filter. The prompt-anchored floor normally buries it anyway --
        # the composer sits below the transcript, but so does the reply.
        #
        # Confirmed live against ChatGPT Desktop with a 20,869-character
        # planning prompt: a prompt that large never renders as one
        # locatable region in the transcript, so `exclude_norm` matched
        # nothing, the floor fell back to the window top, and the
        # placeholder "Message ChatGPT" -- newly visible the instant the
        # composer cleared, therefore absent from baseline, and the
        # smallest changed region in the window -- was returned as the
        # model's reply. The runner recorded ok=True and a fifteen-word
        # answer to a twenty-thousand-character question.
        #
        # It reached no one only because a downstream expectation happened
        # to reject it, and a guess that is caught by luck downstream is
        # still a guess. The structural rule is that the composer is the
        # place the FOUNDER's words go: nothing rendered inside its
        # rectangle is ever the model's. Best-effort by design -- if the
        # composer cannot be located, every check above still stands.
        composer_rect = None
        try:
            composer = self.find_composer(window_handle, retries=0)
            if composer is not None:
                box = composer.CurrentBoundingRectangle
                composer_rect = (box.left, box.top, box.right, box.bottom)
        except Exception:  # noqa: BLE001
            composer_rect = None

        def _on_the_composer(key: tuple[int, int, int, int]) -> bool:
            if composer_rect is None:
                return False
            left, top, right, bottom = key
            return (
                left >= composer_rect[0] - 2
                and top >= composer_rect[1] - 2
                and right <= composer_rect[2] + 2
                and bottom <= composer_rect[3] + 2
            )

        candidates: list[tuple[Any, int]] = []
        for key, (element, text) in all_regions.items():
            if key[1] < prompt_floor:
                continue  # positioned at/above this call's own prompt -- cannot be its response
            if _on_the_composer(key):
                continue  # chrome drawn on the input box, not the model's words
            if not text or not text.strip():
                continue
            text_norm = _normalize_whitespace(text)
            if text_norm == exclude_norm or text_norm in prompt_echo:
                continue  # a rendered block of this call's own question
            if text_norm in baseline_texts:
                continue  # this exact text already existed somewhere in the window before submission
            if _is_transient_status(text_norm):
                # **One status rule, not two.** `_reply_lines()` excluded
                # generation notices and this path did not, so whenever
                # reconstruction declined and fell back here, the fallback
                # could return what the other path had just refused --
                # observed live returning 'ChatGPT is responding' as a
                # reply. A notice that the model is still working is never
                # the model's answer, whichever path is asking.
                continue
            height = key[3] - key[1]
            candidates.append((element, height, text_norm, key))
        if not candidates:
            return None

        # **Whole reply before smallest region -- a third fix, for a real,
        # live-found truncation.** "Smallest wins" is right when the choice
        # is a short answer versus a big enclosing scrollable pane, and
        # wrong when the reply is STRUCTURED: a JSON block, a numbered
        # list or a table is exposed by UIA as one region per line *plus*
        # an enclosing region holding all of them, and every one of those
        # is new. Smallest then returns the first line.
        #
        # Confirmed live against ChatGPT Desktop asked for a MissionPlan:
        # this method returned `{"steps"` -- eight characters, the opening
        # line of a pretty-printed JSON reply -- and the Planner refused
        # the founder's whole objective as "not a plan document". The text
        # was perfectly stable, so no amount of settle-polling could have
        # helped; it was complete-looking and incomplete.
        #
        # The structural signal is containment, not size: if one candidate
        # holds every other candidate's text inside its own, it IS the
        # whole reply and the others are its fragments. Nothing else
        # changes -- persistent chrome is still excluded by the baseline
        # content-set, an older reply is still excluded by the
        # prompt-anchored floor, and when no candidate contains the rest
        # (the ordinary single-region answer, or two genuinely unrelated
        # new regions) the original smallest-wins choice still stands.
        # The discriminator is *how many* fragments a candidate holds, not
        # merely that it holds one. An enclosing conversation pane also
        # contains the new reply -- together with prior transcript -- and
        # for that case the smallest region is still the right answer, as
        # `test_find_new_content_prefers_the_smallest_changed_region`
        # requires. A structured reply is different in kind: its container
        # holds SEVERAL new sibling regions, one per line, and nothing
        # else that is new. Requiring two or more contained candidates
        # separates the two without a size ratio or any guess about
        # wording.
        candidates.sort(key=lambda item: item[1])
        texts = [text for _element, _height, text, _key in candidates]
        for element, _height, text, _key in sorted(candidates, key=lambda c: -len(c[2])):
            contained = [other for other in texts if other != text and other in text]
            if len(contained) >= 2:
                return element
        return candidates[0][0]

    def find_new_response(
        self,
        window_handle: int,
        baseline: dict[tuple[int, int, int, int], str],
        exclude_text: str = "",
        min_height: int = 8,
        turn: "ResponseTurn | None" = None,
    ) -> str | None:
        """The whole assistant reply as TEXT, or `None`.

        **Why this exists rather than another element-returning finder.**

        `find_new_content()` answers "which single region is the reply",
        and for this application that question has no answer. Observed
        live in ChatGPT Desktop's own accessibility tree, immediately
        after a complete three-line answer:

            y=431  '[Kalpavriksha Reasoning - ChatGPT Desktop - ...]'
            y=497  'Give exactly three short names...'
            y=604  'GardenLog'
            y=637  'SproutNote'
            y=670  'PlotPad'
            y=861  'Message ChatGPT'   (the composer, ControlType 50004)

        Every one of those is a **flat sibling** `Text` leaf at the same
        depth, under a single parent holding 2196 children. There is no
        per-response container to descend into: the transcript is one
        long list of leaves. So a method that must return one element can
        only ever return one line of a three-line answer, and it did --
        `'GardenLog'`, stable, complete-looking and two thirds missing.

        The structure that IS present is reading order relative to this
        turn. The reply is every new leaf below this call's own prompt and
        above the composer, top to bottom. That is what a founder reads,
        and it is what this reconstructs.

        Every exclusion `find_new_content()` already enforces is enforced
        here, because this is built on the same candidate set: the
        prompt-anchored floor drops the previous exchange (the earlier
        identical answer at y=248-314 sits above it), `prompt_echo` drops
        this turn's own question however many blocks it renders as, the
        composer rectangle drops the input box and its placeholder, and
        the baseline content-set drops sidebar and navigation chrome.

        Where a genuine container DOES exist -- a JSON block or table
        exposed as one region holding its own lines -- `find_new_content()`
        finds it by containment and this returns that container's text
        unchanged, so nothing regresses for the applications that have one.

        **Completeness belongs to the whole.** The caller's settle check
        compares what this returns across polls, so a streaming reply is
        only accepted once every line has arrived and the reconstruction
        stops changing -- never because one child happened to be stable.
        """
        lines = self._reply_lines(
            window_handle, baseline, exclude_text, min_height, turn
        )
        if not lines:
            # Nothing below this turn's prompt. Fall back to the
            # single-region finder, which still answers for applications
            # whose transcript this method's floor cannot anchor in.
            element = self.find_new_content(
                window_handle, baseline, exclude_text, min_height
            )
            if element is None:
                return None
            return self.read_text(element) or None

        # A genuine container -- a JSON block or table exposed as one
        # region that already holds its own lines -- is the whole reply by
        # itself, and returning it alongside its children would repeat
        # every line twice. Containment decides, exactly as
        # `find_new_content()` decides it: two or more held fragments.
        normalised = [_normalize_whitespace(line) for line in lines]
        for index, candidate in enumerate(normalised):
            held = [other for j, other in enumerate(normalised)
                    if j != index and other and other in candidate]
            if len(held) >= 2:
                return lines[index]

        return "\n".join(lines)

    def _reply_lines(
        self,
        window_handle: int,
        baseline: dict[tuple[int, int, int, int], str],
        exclude_text: str,
        min_height: int,
        turn: "ResponseTurn | None" = None,
    ) -> list[str]:
        """This turn's reply, one entry per rendered leaf, in reading
        order — top to bottom, then left to right for anything sharing a
        row. Consecutive duplicates are collapsed: a line rendered by both
        a wrapper and its own leaf must not appear twice."""
        root = self._root(window_handle)
        win_rect = root.CurrentBoundingRectangle
        exclude_norm = _normalize_whitespace(exclude_text)
        baseline_texts = {
            _normalize_whitespace(t) for t in baseline.values() if t and t.strip()
        }
        all_regions = self._text_region_candidates(root, win_rect, min_height)

        prompt_floor = win_rect.top
        prompt_echo: set[str] = set()
        if exclude_norm:
            for key, (_element, text) in all_regions.items():
                if not text or not text.strip():
                    continue
                norm = _normalize_whitespace(text)
                if norm == exclude_norm or (
                    len(norm) >= _PROMPT_FRAGMENT_MIN_CHARS and norm in exclude_norm
                ):
                    prompt_floor = max(prompt_floor, key[3])
                    prompt_echo.add(norm)

        composer_rect = None
        try:
            composer = self.find_composer(window_handle, retries=0)
            if composer is not None:
                box = composer.CurrentBoundingRectangle
                composer_rect = (box.left, box.top, box.right, box.bottom)
        except Exception:  # noqa: BLE001
            composer_rect = None

        def _on_the_composer(key: tuple[int, int, int, int]) -> bool:
            if composer_rect is None:
                return False
            left, top, right, bottom = key
            return (
                left >= composer_rect[0] - 2 and top >= composer_rect[1] - 2
                and right <= composer_rect[2] + 2 and bottom <= composer_rect[3] + 2
            )

        # **Below this turn's prompt, "seen before" means nothing.**
        #
        # The baseline content-set exists to drop persistent chrome -- a
        # sidebar, a nav list -- which lives outside and above the
        # transcript. It cannot also be used to drop transcript content,
        # because a founder who asks the same question twice gets the same
        # answer twice, and the second one is then filtered out as "not
        # new". Measured: three consecutive runs of the founder's own
        # acceptance prompt all returned empty, because each run's
        # baseline held the previous run's identical three names.
        #
        # When a prompt floor was actually established, it is the stronger
        # signal and it is sufficient: everything above it is the previous
        # exchange, everything below it was produced by this turn. With no
        # floor located, the content-set stays in force, which is the
        # conservative answer.
        floor_established = prompt_floor > win_rect.top
        if floor_established and turn is not None:
            turn.anchored = True

        if not floor_established and turn is not None and turn.anchored:
            # **The turn was anchored; the viewport moved.**
            #
            # This call located its own prompt on an earlier poll, so the
            # boundary between "before this turn" and "this turn" is a
            # settled fact. Then ChatGPT scrolled the transcript and the
            # prompt left the accessibility tree entirely -- observed
            # live, polls 1-2 anchored at floor=179, polls 3-20 with the
            # prompt nowhere in the tree.
            #
            # Re-deriving from scratch each poll made the wait forget it
            # had ever known, and fall back to text uniqueness. Because
            # the founder's acceptance asks the same question repeatedly,
            # the new answer is byte-identical to the previous one, and
            # the three names sat in the tree being discarded as "already
            # existed" until the poll budget ran out.
            #
            # The distinction that survives a scroll is not the text and
            # not the coordinate: it is the OBSERVATION. `baseline` is
            # `rectangle -> text`, and collapsing it to a set of strings
            # is what threw that away. A region is excluded here only when
            # it is the SAME observation the baseline recorded -- same
            # rectangle, same text. Persistent chrome does not move, so it
            # stays excluded; a freshly rendered answer occupies a
            # rectangle the baseline never held, so it stays eligible
            # however familiar its words.
            return self._lines_by_observation(
                all_regions, baseline, exclude_norm, prompt_echo, _on_the_composer
            )

        if not floor_established:
            # **No floor, no reconstruction.**
            #
            # Everything this method does rests on one structural claim:
            # what lies below this turn's own prompt was produced by this
            # turn. Without having located that prompt there is no such
            # claim, and joining every new region is not a reply -- it is
            # a sweep of the window.
            #
            # Measured live against Kimi Desktop, whose prompt echo was
            # not located, this returned:
            #
            #     Copy / Share / Create or select a file to start /
            #     Your chats will appear here / Update / Instant / High /
            #     AI-generated, for reference only
            #
            # Eight confident lines of copy-and-share control labels,
            # empty-state chrome and a disclaimer, offered as the model's
            # answer. That is worse than the single fragment it replaced,
            # because it looks like a whole reply.
            #
            # So this declines, and `find_new_response()` falls back to
            # the single-region finder, whose own baseline content-set and
            # smallest-region rule are what that situation still has.
            return []

        kept: list[tuple[int, int, str]] = []
        for key, (_element, text) in all_regions.items():
            if key[1] < prompt_floor or _on_the_composer(key):
                continue
            if not text or not text.strip():
                continue
            norm = _normalize_whitespace(text)
            if norm == exclude_norm or norm in prompt_echo:
                continue
            if not floor_established and norm in baseline_texts:
                continue
            if _is_transient_status(norm):
                continue
            kept.append((key[1], key[0], text.strip()))

        return self._in_reading_order(kept)

    @staticmethod
    def _in_reading_order(kept: list[tuple[int, int, str]]) -> list[str]:
        """Top to bottom, then left to right for anything sharing a row.
        Consecutive duplicates collapse: a line rendered by both a wrapper
        and its own leaf must not appear twice."""
        kept.sort(key=lambda row: (row[0], row[1]))
        lines: list[str] = []
        for _top, _left, text in kept:
            if lines and _normalize_whitespace(lines[-1]) == _normalize_whitespace(text):
                continue
            lines.append(text)
        return lines

    def _lines_by_observation(
        self,
        all_regions: dict,
        baseline: dict[tuple[int, int, int, int], str],
        exclude_norm: str,
        prompt_echo: set[str],
        on_the_composer,
    ) -> list[str]:
        """This turn's reply for an anchored turn whose prompt has
        scrolled away — selected by OBSERVATION rather than by text.

        A region is the baseline's own if the baseline holds that same
        rectangle with that same text. Anything else is something the
        window is rendering now that it was not rendering then, which is
        what "new" has to mean once identical wording is legitimate.
        """
        kept: list[tuple[int, int, str]] = []
        for key, (_element, text) in all_regions.items():
            if not text or not text.strip() or on_the_composer(key):
                continue
            norm = _normalize_whitespace(text)
            if norm == exclude_norm or norm in prompt_echo:
                continue
            if _is_transient_status(norm):
                continue
            previously = baseline.get(key)
            if previously is not None and _normalize_whitespace(previously) == norm:
                continue  # the same observation, unchanged -- chrome
            kept.append((key[1], key[0], text.strip()))
        return self._in_reading_order(kept)

    def describe(self, element) -> UiaElementInfo:
        info = self._info(element)
        if info is None:
            raise UiaTargetNotFound("element could not be described (unreadable properties)")
        return info

    def window_bounds(self, window_handle: int) -> tuple[int, int, int, int]:
        """Read-only: this window's own top-level bounding rectangle
        (left, top, right, bottom) — the same `CurrentBoundingRectangle`
        every geometry heuristic in this module already reads from the
        window root (`find_composer()`, `find_main_content()`,
        `find_new_content()`), reused here so Desktop Intelligence's
        evidence capture has one source of window geometry truth rather
        than a second, Win32-based measurement of the same thing."""
        root = self._root(window_handle)
        rect = root.CurrentBoundingRectangle
        return (rect.left, rect.top, rect.right, rect.bottom)

    def snapshot_elements(self, window_handle: int) -> tuple[UiaElementSnapshot, ...]:
        """Read-only: every descendant element in this window, resolved
        to enough identity for Desktop Intelligence's observation layer
        to reason about the whole visible surface at once — the batch
        counterpart to `find()`/`describe()`'s single-target resolution.
        Composes the exact same `_root()`/`_descendants()` primitives
        every other method in this class already uses; adds no new
        traversal mechanism of its own.

        Deliberately unfiltered by height or offscreen state, unlike
        `find_composer()`/`_text_region_candidates()` — this method's own
        job is to report what is there, including hidden/offscreen
        elements (`is_offscreen`, carried per-element), not to pre-judge
        which of them a caller will find useful. Never clicks, types,
        focuses, or otherwise acts on anything it finds.

        An element that raises while being read is skipped, not fatal to
        the whole snapshot — the same "a single unreadable element is
        skipped" discipline `_info()` already holds for one-element
        resolution, extended here so one bad element cannot blank out
        every other element in the window."""
        root = self._root(window_handle)
        results: list[UiaElementSnapshot] = []
        for element in self._descendants(root):
            snapshot = self._snapshot_one(element)
            if snapshot is not None:
                results.append(snapshot)
        return tuple(results)

    def _snapshot_one(self, element) -> UiaElementSnapshot | None:
        try:
            rect = element.CurrentBoundingRectangle
            has_value = bool(element.GetCurrentPropertyValue(_IS_VALUE_PATTERN_AVAILABLE_PROPERTY_ID))
            has_text = bool(element.GetCurrentPropertyValue(_IS_TEXT_PATTERN_AVAILABLE_PROPERTY_ID))
            is_offscreen = bool(element.GetCurrentPropertyValue(_IS_OFFSCREEN_PROPERTY_ID))

            is_selected: bool | None = None
            try:
                selectable = bool(
                    element.GetCurrentPropertyValue(_IS_SELECTION_ITEM_PATTERN_AVAILABLE_PROPERTY_ID)
                )
                if selectable:
                    is_selected = bool(
                        element.GetCurrentPropertyValue(_SELECTION_ITEM_IS_SELECTED_PROPERTY_ID)
                    )
            except Exception:  # noqa: BLE001 — selection state is a bonus fact, never required
                is_selected = None

            is_modal: bool | None = None
            if element.CurrentControlType == CONTROL_TYPE_WINDOW:
                try:
                    is_modal = bool(element.GetCurrentPropertyValue(_WINDOW_IS_MODAL_PROPERTY_ID))
                except Exception:  # noqa: BLE001 — same bonus-fact posture as is_selected
                    is_modal = None

            text: str | None = None
            if has_text or has_value:
                try:
                    text = self.read_text(element)
                except (UiaUnavailable, UiaTargetNotFound):
                    text = None

            return UiaElementSnapshot(
                name=element.CurrentName or "", automation_id=element.CurrentAutomationId or "",
                control_type=element.CurrentControlType,
                is_enabled=bool(element.GetCurrentPropertyValue(_IS_ENABLED_PROPERTY_ID)),
                is_focusable=bool(element.CurrentIsKeyboardFocusable),
                is_offscreen=is_offscreen, is_selected=is_selected, is_modal=is_modal,
                has_value_pattern=has_value, has_text_pattern=has_text,
                bounds=(rect.left, rect.top, rect.right, rect.bottom), text=text,
            )
        except Exception:  # noqa: BLE001 — a single unreadable element is skipped, not fatal
            return None

    # ---- action ------------------------------------------------------

    def read_text(self, element) -> str:
        try:
            pattern = element.GetCurrentPattern(_TEXT_PATTERN_ID)
            text_pattern = pattern.QueryInterface(_UIA.IUIAutomationTextPattern)
            return text_pattern.DocumentRange.GetText(-1)
        except Exception:  # noqa: BLE001
            try:
                pattern = element.GetCurrentPattern(_VALUE_PATTERN_ID)
                value_pattern = pattern.QueryInterface(_UIA.IUIAutomationValuePattern)
                return value_pattern.CurrentValue
            except Exception as exc:  # noqa: BLE001
                raise UiaTargetNotFound(f"element exposes neither TextPattern nor ValuePattern: {exc}") from exc

    def _verify_readback(self, element, expected: str, attempts: int = 4, delay_seconds: float = 0.25) -> bool:
        """Re-read up to `attempts` times before declaring a mismatch.
        Found live, against ChatGPT Desktop's real composer (an `Edit`-
        typed element, distinct from Claude Desktop's `Group`-typed one):
        a `ValuePattern.SetValue()` that demonstrably succeeded (confirmed
        by a *later* read in the same session) still failed verification
        on the *first* immediate read-back — Chromium's DOM-to-
        accessibility-tree sync is asynchronous, and different composer
        implementations settle at different speeds. This is a generic
        timing-robustness fix, not an app-specific one: every UIA-backed
        write goes through this same bounded retry, regardless of which
        application it targets.

        `_normalize_whitespace()` handles a second, separate real finding:
        a rich-text composer's own Ctrl-V paste handler reflows plain-text
        whitespace — blank lines collapsed, JSON-style indentation moved —
        confirmed live pasting the real ~6KB planning prompt into Claude
        Desktop's composer. Comparing both sides on words-and-order rather
        than exact whitespace absorbs that expected reflow without
        loosening the check that matters: a genuine corruption (wrong,
        missing, or reordered text) still fails.

        A third, separate real finding — confirmed live against Kimi
        Desktop's own composer — is why this always compares by
        *containment*, not exact equality, even for a full overwrite
        (`append=False`): that composer's own `TextPattern.DocumentRange`
        reports a fixed, non-editable label ("Ask me. Task me.") as part
        of the *same* text range as the real, editable content — a write
        that genuinely landed correctly then failed exact-match
        verification because the readback carried this extra, legitimate
        chrome the write itself never put there and can't remove.
        Containment still catches the failure mode that matters (missing,
        wrong, or reordered text — the expected string no longer appears
        as a contiguous run) while tolerating fixed decoration a
        composer's own accessibility tree bakes in around the value."""
        expected_norm = _normalize_whitespace(expected)
        for attempt in range(attempts):
            readback = _normalize_whitespace(self.read_text(element))
            if expected_norm in readback:
                return True
            if attempt < attempts - 1:
                time.sleep(delay_seconds)
        return False

    def get_focused_element_in_window(self, window_handle: int):
        """The element with real UIA-level keyboard focus right now —
        but only if it actually belongs to `window_handle`. Confirmed by
        checking it against that window's own descendants, not merely
        trusted from `GetFocusedElement()`'s own result, because that
        call is desktop-wide — there is no per-window overload. Real,
        live-found risk this guards against: a *different* application's
        window can hold real OS keyboard focus at the exact moment this
        is called (this session's own development environment, running
        a concurrent coding-agent GUI, reproduced exactly this) — acting
        on whatever that unrelated focus happens to be would be a real
        cross-application keystroke leak, not a theoretical risk, the
        same class of risk `_launch_or_focus()`'s own foreground
        confirmation already guards against for launch/focus.

        Raises `UiaTargetNotFound` if nothing is currently focused, or if
        the focused element does not belong to this window — callers
        must never fall back to guessing in either case."""
        try:
            automation = self._instance()
            focused = automation.GetFocusedElement()
        except Exception as exc:  # noqa: BLE001
            raise UiaUnavailable(f"could not read the focused element: {exc}") from exc
        if focused is None:
            raise UiaTargetNotFound("no element currently has focus")
        root = self._root(window_handle)
        for candidate in self._descendants(root):
            try:
                if bool(automation.CompareElements(focused, candidate)):
                    return focused
            except Exception:  # noqa: BLE001
                continue
        raise UiaTargetNotFound(f"the focused element does not belong to window {window_handle}")

    def _verify_focus(self, element, keyboard=None, mouse=None) -> None:
        """Best-effort, generic focus confirmation — never a hard blocker
        on its own (see the module-level constant's own docstring for
        why). Retries `element.SetFocus()` when focus is *positively*
        confirmed elsewhere via `GetFocusedElement()`/`CompareElements()`
        — generic `IUIAutomation` methods, not anything application-
        specific. Does nothing further when the comparison mechanism
        itself is unavailable, since that is inconclusive, not a failure.

        Found live, this session: UIA's own notion of "focused" (what
        `SetFocus()`/`GetFocusedElement()` operate on) and the real Win32
        keyboard input focus `SendInput`-based typing actually follows can
        diverge — reproduced against Kimi Desktop's real composer,
        immediately after a session-establishment sequence that performed
        its own real mouse clicks elsewhere in the window. If a `mouse`
        controller is given and UIA-level focus could not be positively
        confirmed within the bounded retries, one real, coordinate-based
        click at the element's own UIA-reported bounding-rect center is
        attempted as a last resort — the exact same geometry-derived
        fallback `click()` itself already uses for invokable elements
        that lack a working `InvokePattern`, not an invented screen
        coordinate and not application-specific.
        """
        try:
            automation = self._instance()
        except Exception:  # noqa: BLE001
            automation = None
        if automation is not None:
            for attempt in range(_FOCUS_VERIFY_ATTEMPTS):
                try:
                    focused = automation.GetFocusedElement()
                    already_focused = bool(automation.CompareElements(focused, element))
                except Exception:  # noqa: BLE001
                    return  # cannot compare -- inconclusive, not a failure
                if already_focused:
                    return
                if attempt < _FOCUS_VERIFY_ATTEMPTS - 1:
                    try:
                        element.SetFocus()
                    except Exception:  # noqa: BLE001
                        return
                    time.sleep(_FOCUS_VERIFY_DELAY_SECONDS)
            # Positively confirmed, every retry, that UIA-level focus
            # never landed. A real click is the generic, last-resort way
            # to force real OS keyboard focus onto this exact element.
            if mouse is not None:
                info = self._info(element)
                if info is not None:
                    mouse.click(info.center_x, info.center_y)
                    time.sleep(_FOCUS_VERIFY_DELAY_SECONDS)

    def _verify_cleared(self, element, pre_clear_text: str,
                         attempts: int = _CLEAR_VERIFY_ATTEMPTS,
                         delay_seconds: float = _CLEAR_VERIFY_DELAY_SECONDS,
                         max_chars: int = _MAX_CLEARED_CHARS) -> bool:
        """Bounded retry/backoff, read-back-based — the exact same shape
        `_verify_readback()` already uses for the write side, applied to
        the clear side, which previously had no verification at all.

        A genuinely-cleared composer shows either nothing or a short
        placeholder; real leftover content that needs clearing runs far
        longer — but short is not, on its own, proof of *cleared*: found
        live, this session, real leftover content from an earlier attempt
        can itself happen to be short, and a `ctrl+a`+`delete` that
        silently does nothing would pass a length-only check by pure
        coincidence. `pre_clear_text` — captured once, before the first
        clear attempt in `write_text()` — is compared against: short
        content that is *identical* to what was already there and was not
        already empty is treated as unverified, since nothing has actually
        been shown to change.
        """
        pre_was_empty = not pre_clear_text
        for attempt in range(attempts):
            try:
                current = _normalize_whitespace(self.read_text(element))
            except (UiaUnavailable, UiaTargetNotFound):
                current = None
            if current is not None and len(current) <= max_chars:
                if pre_was_empty or current != pre_clear_text:
                    return True
            if attempt < attempts - 1:
                time.sleep(delay_seconds)
        return False

    def write_text(self, element, text: str, keyboard, append: bool = False, mouse=None) -> bool:
        """Write `text`, then read the element back and confirm an exact
        match *before* the caller does anything else (Phase 5's own
        standard: never treat "the write call returned" as "the value is
        there"). Tries `ValuePattern.SetValue` first (the direct,
        no-keystroke path some controls support, and one that replaces
        the whole value on its own — matches `append=False`'s contract
        without extra work). Most modern rich-text composers only expose
        `TextPattern` for *reading*, not writing — for those, this
        focuses the element via UIA's own `SetFocus` (confirmed by UIA
        identity, not a blind click) and sends real keystrokes through
        the existing `KeyboardController`, exactly the path proven live
        against Claude Desktop's composer. Real, found-live bug this
        guards against: typing without clearing first *inserts* at
        whatever the cursor position already is — leftover text from an
        earlier action silently doubles up rather than being replaced.
        `append=False` (the default, matching `TypeIntoWindowAction`'s
        own contract) selects-all and deletes before typing; `append=True`
        types at the current cursor position instead.

        Real, live-found bug this method now also guards against, on top
        of the one above: the clear step's own `ctrl+a`+`delete` API calls
        "succeeding" (no exception) was never evidence the composer was
        actually emptied. Reproduced live, this session, against Kimi
        Desktop's real composer: content stayed byte-for-byte identical
        through `SetFocus()`, `ctrl+a`, `delete`, and 800ms afterward — a
        generic timing/commit issue, not one this application invented.
        `append=False` now verifies the clear the same bounded,
        read-back-based way `_verify_readback()` already verifies the
        write (see `_verify_cleared()`), retries the clear action itself
        within a bounded ceiling, and fails closed — returns `False`
        without ever typing — if the composer cannot be positively
        confirmed empty. Never types into content that might still be
        stale.

        `mouse`, when given, lets `_verify_focus()` fall back to one real,
        geometry-derived click on this element if UIA-level focus was
        never positively confirmed — see that method's own docstring for
        the real, live-found divergence between UIA focus and actual
        Win32 keyboard input focus this guards against. Optional and
        `None`-safe: every existing caller that does not pass it keeps
        today's behavior exactly.
        """
        try:
            pattern = element.GetCurrentPattern(_VALUE_PATTERN_ID)
            value_pattern = pattern.QueryInterface(_UIA.IUIAutomationValuePattern)
            if not value_pattern.CurrentIsReadOnly:
                new_value = (self.read_text(element) + text) if append else text
                value_pattern.SetValue(new_value)
                if self._verify_readback(element, new_value):
                    return True
                # Real, live-found bug this guards against: `SetValue()`
                # can raise nothing at all and still not write anything —
                # reproduced against Kimi Desktop's real composer, whose
                # `ValuePattern.CurrentIsReadOnly` reports `False` (a
                # genuinely writable pattern, not a stub that raises), yet
                # `SetValue()` left the composer's content completely
                # unchanged. Trusting "no exception" as "it worked" here
                # silently gave up before ever trying the keystroke path
                # below — which was independently confirmed, live, this
                # same session, to work reliably on this exact composer.
                # Fall through instead of returning a false failure.
        except Exception:  # noqa: BLE001
            pass  # no writable ValuePattern — fall through to keystrokes

        element.SetFocus()
        time.sleep(0.15)
        self._verify_focus(element, keyboard, mouse)

        if not append:
            try:
                pre_clear_text = _normalize_whitespace(self.read_text(element))
            except (UiaUnavailable, UiaTargetNotFound):
                pre_clear_text = ""
            cleared = False
            for clear_attempt in range(_CLEAR_ACTION_ATTEMPTS):
                keyboard.hotkey("ctrl", "a")
                time.sleep(0.05)
                keyboard.press("delete")
                time.sleep(0.1)
                if self._verify_cleared(element, pre_clear_text):
                    cleared = True
                    break
            if not cleared:
                return False  # fail closed — never type into unverified stale content

        # Real reasoning-provider prompts (the Planner's own system prompt,
        # capability catalogue included) run to several thousand characters
        # — confirmed live at 6081 chars, not the short test strings this
        # path was first proven against. Character-by-character `SendInput`
        # (`keyboard.type`) sends one real OS keystroke event per character;
        # at that length it is both slow and, found live, unreliable enough
        # that read-back verification failed across every desktop composer
        # tried. `keyboard.paste()` already exists for exactly this
        # (`ClipboardExecutive.write()` + Ctrl-V) and moves arbitrarily long
        # text in one event, the same way a founder pasting a long prompt
        # would. Short text keeps typing — real keystrokes remain the more
        # faithful "founder typed this" interaction where length doesn't
        # make it unreliable.
        #
        # A literal newline is a second, separate reason to prefer paste
        # regardless of length: found live, this session, typing a short
        # (well under the length threshold) prompt containing a blank line
        # into Kimi Desktop's real composer — the "\n\n" did not merely
        # collapse the way pasted whitespace already does elsewhere
        # (`_normalize_whitespace()`'s own finding); it vanished entirely,
        # with no separator left at all. A raw `\n` sent as a synthetic
        # keystroke is genuinely ambiguous across composers — some insert
        # a line break, some treat it as submit, this one appears to
        # simply drop it — where a real Enter keypress remains this
        # method's own separate, correctly-treated submit action.
        # Clipboard content carries no such ambiguity; only its own,
        # already-tolerated reflow behavior applies.
        if len(text) > _PASTE_THRESHOLD_CHARS or "\n" in text:
            keyboard.paste(text)
        else:
            keyboard.type(text)
        time.sleep(0.15)
        return self._verify_readback(element, text)

    def click(self, element, mouse) -> bool:
        """`InvokePattern.Invoke()` where the target supports it (the
        semantically correct action for a button-like element — no
        coordinate involved at all); otherwise a real click at this
        element's *own, UIA-reported* bounding-rect center — a
        structural inference from a resolved element's real geometry,
        not an invented screen coordinate."""
        try:
            pattern = element.GetCurrentPattern(_INVOKE_PATTERN_ID)
            invoke_pattern = pattern.QueryInterface(_UIA.IUIAutomationInvokePattern)
            invoke_pattern.Invoke()
            return True
        except Exception:  # noqa: BLE001
            pass

        info = self._info(element)
        if info is None:
            return False
        result = mouse.click(info.center_x, info.center_y)
        return bool(getattr(result, "success", result))
