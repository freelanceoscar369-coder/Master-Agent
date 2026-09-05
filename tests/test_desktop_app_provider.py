"""Regression coverage for `DesktopAppReasoningProvider` (Corrected
Fallback Ladder, Tier 2), covering real, live-found issues:

1. `_await_response()` must not mistake leftover, still-present prompt
   text for a genuine reply merely because a rich-text composer reflowed
   its whitespace on paste (blank lines collapsed, indentation moved) —
   found live pasting the real ~6KB planning prompt into Claude Desktop's
   composer. A fake success here would violate Section 5's own rule: no
   step reports success because text was typed or Enter was pressed.

2. Static safety exclusion (`TestStaticSafetyExclusion`): found live,
   this session, that a desktop AI application's discoverable window/
   composer can belong to an *existing, active* conversation rather than
   a fresh surface safe for an autonomous one-shot prompt — concretely,
   Claude Desktop hosting an active Claude Code project session as a tab
   within the same window the generic launch/focus path resolves to.
   `claude-desktop`'s own catalog entry is statically excluded from the
   autonomous tier pending a generic, provider-safe isolated-session
   mechanism proven for that specific application.

3. `complete()`'s integration with `ReasoningSessionManager`
   (`TestSessionEstablishmentIntegration`): the corrected architecture —
   `complete()` delegates isolation to a Kalpavriksha-owned session
   manager (its own behavior is covered in
   `tests/test_reasoning_session_manager.py`) and must never write a
   prompt into the composer until that manager reports success.
"""
from __future__ import annotations

import types

from master_agent.ai_infrastructure.catalog import PROVIDER_CATALOG
from master_agent.desktop.actions import DesktopContext
from master_agent.desktop.execution.backends import WindowInfo
from master_agent.desktop.probe import ProcessInfo
from master_agent.providers import desktop_app as mod
from master_agent.providers.desktop_app import DesktopAppReasoningProvider
from tests.test_desktop_execution import FakeWindowBackend


def _claude_spec():
    return next(spec for spec in PROVIDER_CATALOG if spec.provider_id == "claude-desktop")


def _chatgpt_spec():
    """A desktop provider spec with no static safety exclusion — used to
    test the *generic* runtime isolation gate, which must apply uniformly
    to every desktop provider, not just the one with a declarative flag."""
    return next(spec for spec in PROVIDER_CATALOG if spec.provider_id == "chatgpt-desktop")


class FakeUiaBridge:
    """Only the methods `_await_response` calls. `find_new_content()`
    returns each of `new_content_texts` in turn (as its own "element" —
    a plain string is enough since `read_text()` below just echoes it
    back), then `None` once exhausted, matching the real method's own
    "nothing changed yet" contract."""

    def __init__(self, new_content_texts: list[str] = ()):
        self._texts = list(new_content_texts)

    def find_new_content(self, handle, baseline, exclude_text=""):
        return self._texts.pop(0) if self._texts else None

    def find_new_response(self, handle, baseline, exclude_text="", min_height=8, turn=None):
        """`_await_response()` reconstructs the WHOLE reply now, so this
        fake answers the same question the real bridge does. Each entry in
        `new_content_texts` is one complete reading, exactly as before --
        these tests are about the settle rule, not about reconstruction,
        which `test_desktop_uia.py` owns."""
        return self._texts.pop(0) if self._texts else None

    def read_text(self, element):
        return element


def _provider(spec=None):
    return DesktopAppReasoningProvider(spec or _claude_spec(), context=DesktopContext(probe=None))


class TestAwaitResponseFakeSuccessGuard:
    def test_reflowed_leftover_prompt_is_not_treated_as_a_real_response(self, monkeypatch):
        """The exact live-found case: a composer's own paste normalization
        (blank lines collapsed) makes the leftover prompt differ from the
        original string by whitespace alone. That must NOT be accepted as
        a genuine reply — a defense-in-depth guard inside `_await_response()`
        itself, in case `find_new_content()`'s own `exclude_text` filtering
        ever misses it."""
        monkeypatch.setattr(mod, "_RESPONSE_POLL_INTERVAL_SECONDS", 0)
        monkeypatch.setattr(mod, "_RESPONSE_POLL_TIMEOUT_SECONDS", 0.05)
        provider = _provider()
        prompt = "Objective: do the thing.\n\nContext:\n- raw_input: do the thing."
        reflowed_leftover = "Objective: do the thing.\nContext:\n- raw_input: do the thing."
        provider._uia = FakeUiaBridge([reflowed_leftover] * 10)

        result = provider._await_response({"handle": 123}, prompt, baseline={})

        assert result is None

    def test_a_genuinely_different_response_is_accepted_once_stable(self, monkeypatch):
        """Must read back identically across `_RESPONSE_STABILITY_POLLS`
        *consecutive* polls before being accepted — see
        `_await_response()`'s own docstring."""
        monkeypatch.setattr(mod, "_RESPONSE_POLL_INTERVAL_SECONDS", 0)
        monkeypatch.setattr(mod, "_RESPONSE_POLL_TIMEOUT_SECONDS", 1.0)
        provider = _provider()
        prompt = "Objective: do the thing."
        real_reply = "Sure — here is a plan for doing the thing: step one, step two."
        provider._uia = FakeUiaBridge([real_reply] * mod._RESPONSE_STABILITY_POLLS)

        result = provider._await_response({"handle": 123}, prompt, baseline={})

        assert result == real_reply

    def test_a_single_reading_is_not_enough_the_content_must_settle(self, monkeypatch):
        """The generic fix for a real, live-found false positive: a
        transient '...is responding'-style status string is itself new
        content (differs from the prompt, non-empty) and would satisfy a
        naive changed-since-baseline check while a reply is still
        streaming in. Confirmed live against ChatGPT Desktop: a poll
        landed mid-generation and captured exactly this. Only text that
        reads back unchanged across every required poll is accepted."""
        monkeypatch.setattr(mod, "_RESPONSE_POLL_INTERVAL_SECONDS", 0)
        monkeypatch.setattr(mod, "_RESPONSE_POLL_TIMEOUT_SECONDS", 1.0)
        provider = _provider()
        prompt = "Objective: do the thing."
        real_reply = "Sure — here is the real, finished answer."
        provider._uia = FakeUiaBridge([
            "...is responding",
            "...is responding a bit more",
            *([real_reply] * mod._RESPONSE_STABILITY_POLLS),
        ])

        result = provider._await_response({"handle": 123}, prompt, baseline={})

        assert result == real_reply

    def test_a_single_repeat_is_not_enough_a_truncated_mid_stream_read_is_rejected(self, monkeypatch):
        """Real, live-found bug in this mechanism's own first draft:
        requiring only *one* repeat (two consecutive identical polls)
        accepted a genuinely truncated mid-stream read, live, against
        ChatGPT Desktop — the real reply was
        "KALPAVRIKSHA_CHATGPT_FINAL_OK", but a poll happened to catch
        "KALPAVRIKSHA_" twice in a row (an LLM's own token cadence can
        pause for a full poll interval without having finished) and that
        was wrongly accepted as final. A truncated read that repeats only
        once, then changes again to the real, complete text, must not be
        accepted until the complete text itself has settled."""
        monkeypatch.setattr(mod, "_RESPONSE_POLL_INTERVAL_SECONDS", 0)
        monkeypatch.setattr(mod, "_RESPONSE_POLL_TIMEOUT_SECONDS", 1.0)
        provider = _provider()
        prompt = "Reply with exactly: KALPAVRIKSHA_CHATGPT_FINAL_OK"
        truncated = "KALPAVRIKSHA_"
        complete_reply = "KALPAVRIKSHA_CHATGPT_FINAL_OK"
        provider._uia = FakeUiaBridge([
            truncated,
            truncated,  # one repeat -- must NOT be enough on its own
            *([complete_reply] * mod._RESPONSE_STABILITY_POLLS),
        ])

        result = provider._await_response({"handle": 123}, prompt, baseline={})

        assert result == complete_reply

    def test_no_new_content_ever_appearing_times_out(self, monkeypatch):
        monkeypatch.setattr(mod, "_RESPONSE_POLL_INTERVAL_SECONDS", 0)
        monkeypatch.setattr(mod, "_RESPONSE_POLL_TIMEOUT_SECONDS", 0.05)
        provider = _provider()
        provider._uia = FakeUiaBridge([])  # find_new_content() always returns None

        result = provider._await_response({"handle": 123}, "Objective: do the thing.", baseline={})

        assert result is None


class FakeSubmitUiaBridge:
    """Only the methods `_submit()`/`_verify_submission()`/
    `_find_send_control()` call, plus `snapshot_text_regions()` — now
    called by `complete()` itself, between `_write_prompt()` and
    `_submit()`, for every provider whose composer write succeeds."""

    def __init__(self, composer_texts: list[str], send_control: object | None = None, click_result: bool = True):
        self._composer_texts = list(composer_texts)
        self._send_control = send_control
        self._click_result = click_result
        self.clicked_elements = []
        self.find_calls = []

    def find_composer(self, handle):
        return "composer-element"

    def read_text(self, element):
        return self._composer_texts.pop(0) if self._composer_texts else ""

    def snapshot_text_regions(self, handle):
        return {}

    def find(self, handle, *, name_contains=None, name_exact=None, visible_only=False, retries=0):
        self.find_calls.append(name_contains or name_exact)
        if self._send_control is not None:
            return self._send_control
        from master_agent.desktop.execution.uia_control import UiaTargetNotFound
        raise UiaTargetNotFound(f"no element matched {name_contains!r}")

    def click(self, element, mouse):
        self.clicked_elements.append(element)
        return self._click_result


class FakeSubmitKeyboard:
    def __init__(self):
        self.pressed: list[str] = []

    def press(self, key):
        self.pressed.append(key)


class TestSubmit:
    """`_submit()` — verified, not assumed. See the mission's own
    explicit instruction: 'do not immediately assume Enter is the
    universal submit mechanism.'"""

    def test_enter_confirmed_by_composer_content_changing(self, monkeypatch):
        monkeypatch.setattr(mod, "_SUBMIT_VERIFY_DELAY_SECONDS", 0)
        provider = _provider(_chatgpt_spec())
        # Composer held real content, then cleared after Enter -- the
        # generic "something happened" signal.
        provider._uia = FakeSubmitUiaBridge(composer_texts=["the submitted prompt", ""])
        keyboard = FakeSubmitKeyboard()

        submitted = provider._submit({"handle": 1}, keyboard)

        assert submitted is True
        assert keyboard.pressed == ["enter"]

    def test_enter_produces_no_change_falls_back_to_a_discovered_send_control(self, monkeypatch):
        monkeypatch.setattr(mod, "_SUBMIT_VERIFY_DELAY_SECONDS", 0)
        provider = _provider(_chatgpt_spec())
        # First round (after Enter): composer never changes, across every
        # verify poll. Second round (after Send is clicked): it does.
        composer_texts = ["stuck"] * (mod._SUBMIT_VERIFY_ATTEMPTS + 1) + ["stuck", ""]
        send_control = object()
        provider._uia = FakeSubmitUiaBridge(composer_texts=composer_texts, send_control=send_control)
        keyboard = FakeSubmitKeyboard()

        submitted = provider._submit({"handle": 1}, keyboard)

        assert submitted is True
        assert send_control in provider._uia.clicked_elements
        assert any(phrase in provider._uia.find_calls for phrase in mod.SEND_VOCABULARY)

    def test_neither_enter_nor_a_discoverable_send_control_verifies_fails_closed(self, monkeypatch):
        monkeypatch.setattr(mod, "_SUBMIT_VERIFY_DELAY_SECONDS", 0)
        provider = _provider(_chatgpt_spec())
        provider._uia = FakeSubmitUiaBridge(composer_texts=["stuck"] * 50, send_control=None)
        keyboard = FakeSubmitKeyboard()

        submitted = provider._submit({"handle": 1}, keyboard)

        assert submitted is False

    def test_complete_never_awaits_a_response_without_verified_submission_integration(self, monkeypatch):
        """End-to-end through the real `complete()` sequence (not a
        mocked `_submit`) — `_await_response` must not be reached when
        Enter and every discoverable Send attempt both fail to verify."""
        monkeypatch.setattr(mod, "_SUBMIT_VERIFY_DELAY_SECONDS", 0)
        provider = _provider(_chatgpt_spec())
        fake_app = types.SimpleNamespace(launchable=True, launch_target="fake.exe")
        provider._context.inventory = lambda deep: object()
        provider._resolve_app_record = lambda inventory: fake_app
        provider._launch_or_focus = lambda app: {"handle": 42}
        provider._sessions = FakeSessionManager(True)
        provider._write_prompt = lambda window, prompt, keyboard: True
        provider._uia = FakeSubmitUiaBridge(composer_texts=["stuck"] * 50, send_control=None)

        def _boom(*args, **kwargs):
            raise AssertionError("_await_response must not be called")

        provider._await_response = _boom

        result = provider.complete("some reasoning prompt")

        assert result.ok is False
        assert result.error == mod.SUBMIT_UNVERIFIED


class TestLaunchOrFocusMaximizes:
    """The 'Correct Session Creation and Screen-Proven E2E' mission's own
    requirement: 'Ensure the application window is maximized... Use the
    existing generic window-management capability' — never a reason to
    touch `find_composer()`'s own geometry thresholds. `maximize()` was
    already a generic `WindowManager` primitive (used nowhere in this
    provider before); this only wires it into the one place a window is
    confirmed focused and ready for interaction."""

    def test_launch_or_focus_maximizes_the_confirmed_foreground_window(self):
        provider = _provider(_chatgpt_spec())
        window_info = WindowInfo(
            handle=42, title="ChatGPT", process_id=99,
            is_visible=True, is_minimized=False, is_maximized=False,
        )
        backend = FakeWindowBackend(windows=(window_info,), active_handle=42)
        provider._windows = backend
        provider._context.refresh = lambda **_: types.SimpleNamespace(
            processes=[ProcessInfo(pid=99, name="chatgpt.exe", owner="chatgpt-desktop")],
        )
        app = types.SimpleNamespace(key="chatgpt-desktop", launchable=True, launch_target="fake.exe")

        window = provider._launch_or_focus(app)

        assert window is not None
        assert window["handle"] == 42
        assert ("maximize", 42) in backend.calls

    def test_a_window_that_refuses_to_maximize_is_not_fatal(self):
        """Best-effort: `find_composer()` already tolerates real window
        sizes below full screen — only launch/focus itself failing is
        fatal, never a maximize refusal."""
        provider = _provider(_chatgpt_spec())
        window_info = WindowInfo(
            handle=42, title="ChatGPT", process_id=99,
            is_visible=True, is_minimized=False, is_maximized=False,
        )
        backend = FakeWindowBackend(windows=(window_info,), active_handle=42)
        backend.fail_operations.add("maximize")
        provider._windows = backend
        provider._context.refresh = lambda **_: types.SimpleNamespace(
            processes=[ProcessInfo(pid=99, name="chatgpt.exe", owner="chatgpt-desktop")],
        )
        app = types.SimpleNamespace(key="chatgpt-desktop", launchable=True, launch_target="fake.exe")

        window = provider._launch_or_focus(app)

        assert window is not None
        assert window["handle"] == 42


class TestStaticSafetyExclusion:
    """`claude-desktop`'s declarative `autonomous_reasoning_unsafe_reason`
    must stop `complete()` before ANY machine interaction — no inventory
    read, no launch, no focus. 'Never open or interact with an unsafe
    desktop application merely because it is installed' (the mission's
    own words) is a statement about not touching the machine at all, not
    merely about refusing to type once it's already open."""

    def test_complete_refuses_immediately_without_touching_the_machine(self):
        spec = _claude_spec()
        assert spec.autonomous_reasoning_unsafe_reason is not None  # sanity: the fixture assumption holds
        provider = _provider(spec)

        def _boom(*args, **kwargs):
            raise AssertionError("must not be called for a statically unsafe provider")

        provider._context.inventory = _boom
        provider._launch_or_focus = _boom
        provider._write_prompt = _boom

        result = provider.complete("some reasoning prompt")

        assert result.ok is False
        assert "AUTONOMOUS_REASONING_UNSAFE" in result.error

    def test_availability_reports_the_static_exclusion(self):
        provider = _provider(_claude_spec())

        availability = provider.availability()

        assert availability.reachable is False
        assert "AUTONOMOUS_REASONING_UNSAFE" in availability.detail

    def test_a_provider_without_the_flag_is_not_statically_excluded(self):
        spec = _chatgpt_spec()
        assert spec.autonomous_reasoning_unsafe_reason is None  # sanity

        provider = _provider(spec)

        # complete() must proceed past the static gate (it will fail later,
        # for the mundane reason that DesktopContext(probe=None) can't
        # really scan a machine — proving the static gate specifically did
        # NOT short-circuit it is the point, not a full success).
        result = provider.complete("some reasoning prompt")

        assert "AUTONOMOUS_REASONING_UNSAFE" not in result.error


class FakeSessionManager:
    """A `ReasoningSessionManager`-shaped fake — the session manager's own
    behavior is covered in `tests/test_reasoning_session_manager.py`; here
    the point is only whether `complete()` correctly gates `_write_prompt`
    on its result."""

    def __init__(self, ok: bool, reason: str = "", session_marker: str = "Kalpavriksha Reasoning — test"):
        from master_agent.providers.reasoning_session import SessionEstablishment
        from master_agent.providers.reasoning_session import SessionHealth
        self._result = SessionEstablishment(ok, reason, session_marker if ok else "")
        self.establish_calls = 0
        #: What the window says AFTER the answer arrives. Healthy by
        #: default; a test that cares sets it.
        self.health = SessionHealth(observed=True)
        self.retired: list[str] = []

    def establish(self, window, provider_label, keyboard):
        self.establish_calls += 1
        return self._result

    def inspect_session(self, handle):
        from master_agent.providers.reasoning_session import SessionHealth
        return self.health

    def retire(self, provider_label):
        self.retired.append(provider_label)


class TestSessionEstablishmentIntegration:
    """Session establishment must sit inside `complete()`'s own real
    sequence, between launch/focus and composer writing — proven by
    showing `_write_prompt` (and therefore any keyboard/paste action) is
    never reached when establishment fails, using a provider spec with no
    static exclusion so only the session-manager integration is under
    test."""

    def _wired_provider(self, session_ok: bool, session_reason: str = ""):
        provider = _provider(_chatgpt_spec())
        fake_app = types.SimpleNamespace(launchable=True, launch_target="fake.exe")
        provider._context.inventory = lambda deep: object()
        provider._resolve_app_record = lambda inventory: fake_app
        provider._launch_or_focus = lambda app: {"handle": 42}
        provider._sessions = FakeSessionManager(session_ok, session_reason)
        return provider

    def test_composer_is_never_written_when_session_establishment_fails(self):
        provider = self._wired_provider(session_ok=False, session_reason="ISOLATION_UNVERIFIED: no control found")

        def _boom(*args, **kwargs):
            raise AssertionError("_write_prompt must not be called when session establishment fails")

        provider._write_prompt = _boom

        result = provider.complete("some reasoning prompt")

        assert result.ok is False
        assert "ISOLATION_UNVERIFIED" in result.error
        assert provider._sessions.establish_calls == 1

    def test_write_prompt_is_reached_once_the_session_is_established(self):
        provider = self._wired_provider(session_ok=True)
        provider._write_prompt = lambda window, prompt, keyboard: False  # fail here, deliberately, to prove reachability

        result = provider.complete("some reasoning prompt")

        assert result.ok is False
        # Proves session establishment passed and execution continued past
        # it: the failure is the *next* real step's own honest reason
        # (`WRITE_UNVERIFIED`'s own message), not a session rejection.
        assert result.error == mod.WRITE_UNVERIFIED

    def test_the_prompt_actually_written_carries_the_session_marker(self):
        """Inspectability: the marker must be part of what's actually
        submitted, not merely returned and discarded."""
        provider = self._wired_provider(session_ok=True)
        captured = {}

        def _capture_write(window, prompt, keyboard):
            captured["prompt"] = prompt
            return False  # fail here deliberately -- only the captured text matters

        provider._write_prompt = _capture_write

        provider.complete("the real reasoning request")

        assert "Kalpavriksha Reasoning" in captured["prompt"]
        assert "the real reasoning request" in captured["prompt"]

    def test_successful_completion_surfaces_the_session_marker_in_result_detail(self):
        provider = self._wired_provider(session_ok=True)
        provider._write_prompt = lambda window, prompt, keyboard: True
        provider._submit = lambda window, keyboard: True
        provider._await_response = (
            lambda window, prompt, baseline, budget=None:
            "a genuine reply from the application"
        )

        result = provider.complete("some reasoning prompt")

        assert result.ok is True
        assert "session_marker" in result.detail
        assert "Kalpavriksha Reasoning" in result.detail["session_marker"]

    def test_response_is_never_awaited_when_submission_is_not_verified(self):
        """Section 4's own rule, extended to submission: never treated as
        done merely because Enter was pressed. `_await_response()` must
        not even be called until `_submit()` has positively verified
        something happened."""
        provider = self._wired_provider(session_ok=True)
        provider._write_prompt = lambda window, prompt, keyboard: True
        provider._submit = lambda window, keyboard: False

        def _boom(*args, **kwargs):
            raise AssertionError("_await_response must not be called when submission is unverified")

        provider._await_response = _boom

        result = provider.complete("some reasoning prompt")

        assert result.ok is False
        assert result.error == mod.SUBMIT_UNVERIFIED


class TestARunningProcessIsNotAnOpenWindow:
    """Closing one of these applications leaves it alive in the tray, so
    it has processes and no window at all.

    `_launch_or_focus()` launched only when NO process existed, on the
    reasonable-sounding assumption that a running application has a window
    to focus. Measured live, and it is the whole of the founder's
    intermittent "empty run": ChatGPT Desktop with NINE running processes
    and ZERO visible windows. Nothing was launched, the bounded poll spent
    thirty seconds waiting for a window that was never going to appear,
    and the mission failed with "the application did not report a real,
    visible window" — without a single prompt being submitted.
    """

    def _app(self):
        return types.SimpleNamespace(
            key="chatgpt-desktop", launchable=True, launch_target="fake.exe",
        )

    def test_processes_but_no_window_still_launches(self):
        provider = _provider(_chatgpt_spec())
        window_info = WindowInfo(
            handle=42, title="ChatGPT", process_id=99,
            is_visible=True, is_minimized=False, is_maximized=False,
        )
        # No window at first; the launch is what makes one appear.
        backend = FakeWindowBackend(windows=(), active_handle=42)
        provider._windows = backend
        provider._context.refresh = lambda **_: types.SimpleNamespace(
            processes=[ProcessInfo(pid=99, name="chatgpt.exe", owner="chatgpt-desktop")],
        )
        started: list = []

        def start(argv):
            started.append(argv)
            backend._windows[window_info.handle] = window_info   # the window opens
            return types.SimpleNamespace(ok=True)

        provider._context.probe = types.SimpleNamespace(start=start)

        window = provider._launch_or_focus(self._app())

        assert started, "a running-but-windowless application was never launched"
        assert window is not None and window["handle"] == 42

    def test_an_already_open_window_is_not_relaunched(self):
        """The launch follows the WINDOW. One that is already open must
        be focused, never started again."""
        provider = _provider(_chatgpt_spec())
        window_info = WindowInfo(
            handle=42, title="ChatGPT", process_id=99,
            is_visible=True, is_minimized=False, is_maximized=False,
        )
        backend = FakeWindowBackend(windows=(window_info,), active_handle=42)
        provider._windows = backend
        provider._context.refresh = lambda **_: types.SimpleNamespace(
            processes=[ProcessInfo(pid=99, name="chatgpt.exe", owner="chatgpt-desktop")],
        )
        started: list = []
        provider._context.probe = types.SimpleNamespace(
            start=lambda argv: (started.append(argv), types.SimpleNamespace(ok=True))[1]
        )

        window = provider._launch_or_focus(self._app())

        assert window is not None and window["handle"] == 42
        assert started == [], "an application with an open window was relaunched"
class TestReplyWindowHonoursTheBudget:
    """The clock, not the lane, decided the founder could not have a folder.

    Measured live on 2026-09-04. Every reasoning provider was reported
    unusable and the founder was told "I couldn't plan that just now" --
    about a request to create a folder and a text file. The broker record:

        chatgpt-desktop      timed_out    77.1s
        perplexity-desktop   unavailable  31.2s
        kimi-desktop         rejected      0.0s
        trusted-founder-web  rejected      9.1s
        -> no_provider_available

    ChatGPT Desktop answered the same Stage 1 obligation prompt in 95.1s
    when probed on its own. It was not broken; it was cut off at a
    constant tuned against a three-name prompt, while MB038 had already
    derived a real deadline that `complete()` was being handed and this
    provider never read.
    """

    def test_a_budget_widens_the_wait_beyond_the_tuned_constant(self):
        budget = types.SimpleNamespace(total_ms=120_000.0)
        assert DesktopAppReasoningProvider._reply_window_seconds(budget) == 120.0

    def test_the_constant_is_a_floor_not_a_ceiling(self):
        """A budget must never make the wait SHORTER than it already was.

        A derived deadline can come back small for a short prompt, and
        letting that shrink the window would turn one fix into a new
        truncation -- the failure this exists to end, in miniature.
        """
        tiny = types.SimpleNamespace(total_ms=5_000.0)
        assert (
            DesktopAppReasoningProvider._reply_window_seconds(tiny)
            == mod._RESPONSE_POLL_TIMEOUT_SECONDS
        )

    def test_no_budget_keeps_the_original_behaviour_exactly(self):
        """Callers that pass nothing are pre-MB038 and must not change."""
        for absent in (None, types.SimpleNamespace(), types.SimpleNamespace(total_ms=None),
                       types.SimpleNamespace(total_ms=0)):
            assert (
                DesktopAppReasoningProvider._reply_window_seconds(absent)
                == mod._RESPONSE_POLL_TIMEOUT_SECONDS
            )

    def test_the_budget_actually_reaches_the_wait(self):
        """Wiring, not arithmetic.

        `_reply_window_seconds` being right is worth nothing if
        `complete()` still drops the budget on the floor, which is
        precisely the defect: the parameter was accepted and ignored.
        """
        import inspect
        source = inspect.getsource(DesktopAppReasoningProvider.complete)
        assert "budget" in source.split("def complete")[-1], (
            "complete() must pass its budget onward, not merely accept it"
        )
        signature = inspect.signature(DesktopAppReasoningProvider._await_response)
        assert "budget" in signature.parameters

def _provider_for_copy():
    return DesktopAppReasoningProvider(_chatgpt_spec(), context=DesktopContext(probe=None))


class _FakeClipboard:
    """The real `ClipboardExecutive` shape: output={"text": ...}."""

    def __init__(self, on_copy=None):
        self.text = "the founder's own clipboard, untouched"
        self._on_copy = on_copy
        self.writes = []

    def write(self, text):
        self.writes.append(text)
        self.text = text
        return types.SimpleNamespace(success=True, output={"written_characters": len(text)})

    def read(self):
        return types.SimpleNamespace(success=True, output={"text": self.text})

    def copy_happened(self, text):
        self.text = text


class _CopyBridge:
    """Only what `_reply_via_copy` touches."""

    def __init__(self, button=object(), clicks_land=True, clipboard=None):
        self._button = button
        self._clicks_land = clicks_land
        self._clipboard = clipboard
        self.clicked = 0

    def find_last(self, handle, *, name_exact, control_type=None):
        return self._button

    def click(self, element, mouse):
        self.clicked += 1
        if self._clicks_land and self._clipboard is not None:
            self._clipboard.copy_happened('{"regions":[],"anchors":[],"valid":true}')
        return self._clicks_land


class TestTheApplicationHandsOverItsOwnReply:
    """Reconstruction can only see what is RENDERED.

    Measured live on 2026-09-05: a Stage 1 audit reply carried rows at
    top=-121 -- scrolled above the viewport -- and its leading
    `{"regions":[...]` was not in the accessibility tree at all. No
    ordering or exclusion rule recovers text the window never drew.
    """

    def _provider(self, bridge, clipboard):
        provider = _provider_for_copy()
        provider._uia = bridge
        provider._clipboard = clipboard
        provider._COPY_SETTLE_SECONDS = 0.4
        provider._COPY_POLL_SECONDS = 0.01
        return provider

    def test_the_copied_reply_is_returned(self):
        clipboard = _FakeClipboard()
        bridge = _CopyBridge(clipboard=clipboard)
        provider = self._provider(bridge, clipboard)

        assert provider._reply_via_copy({"handle": 1}) == (
            '{"regions":[],"anchors":[],"valid":true}'
        )
        assert bridge.clicked == 1

    def test_a_click_that_did_not_land_returns_nothing(self):
        """The failure this must never turn into a reply.

        Without the sentinel, reading the clipboard after a missed click
        hands back whatever the founder had copied earlier -- silently,
        and shaped exactly like an answer.
        """
        clipboard = _FakeClipboard()
        before = clipboard.text
        provider = self._provider(_CopyBridge(clicks_land=False, clipboard=clipboard),
                                  clipboard)

        assert provider._reply_via_copy({"handle": 1}) is None
        assert before not in (provider._reply_via_copy({"handle": 1}) or "")

    def test_no_copy_affordance_is_an_ordinary_no(self):
        """Applications without the button must keep working."""
        clipboard = _FakeClipboard()
        provider = self._provider(_CopyBridge(button=None, clipboard=clipboard), clipboard)

        assert provider._reply_via_copy({"handle": 1}) is None

    def test_the_sentinel_is_never_mistaken_for_the_reply(self):
        """A click that lands but copies nothing leaves our own marker
        on the clipboard. Returning that would be a fake success wearing
        a hex string."""
        clipboard = _FakeClipboard()

        class _EmptyCopy(_CopyBridge):
            def click(self, element, mouse):
                self.clicked += 1
                return True  # landed, but the app wrote nothing

        provider = self._provider(_EmptyCopy(clipboard=clipboard), clipboard)
        result = provider._reply_via_copy({"handle": 1})

        assert result is None
        assert clipboard.writes, "the sentinel must actually have been written"
        assert not (result or "").startswith("__kalpavriksha_copy_")

