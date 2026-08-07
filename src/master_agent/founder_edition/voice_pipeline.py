"""The local voice pipeline — C34.1's release blocker 6.

*"If the current Web Speech API cannot satisfy automatic device tracking
and reliability, replace it with a proper local speech pipeline... Do not
keep a partially working implementation."*

C34's own build used the browser's Web Speech API (real, but dependent on
whatever speech service the OS/browser vendor wired behind it, and with
no first-class way to react to a Bluetooth headset becoming the system's
new default device without recreating the recognizer). This module
replaces it entirely: **speech-to-text is `faster-whisper`, running
locally, on this machine, on CPU; text-to-speech is `piper`, running
locally, from a bundled voice model.** Neither calls a network service.
Both were already named as this project's own intended dependencies —
`pyproject.toml`'s `voice` extra has listed `faster-whisper` and
`piper-tts` since before this module existed; this is the first caller to
actually use them.

## Device tracking, and why it is polling rather than a WASAPI callback

*"Bluetooth headset changes must be detected automatically without
requiring restart or manual selection."* The most correct Windows
mechanism is a WASAPI `IMMNotificationClient` callback (COM, event-
driven). This module instead polls `sounddevice.query_devices(kind=
"input")` — which asks PortAudio for the OS's *current* default input
device — every 1.5 seconds on a background thread, and reopens the audio
stream the moment the reported device name changes. This satisfies the
literal requirement (automatic, no restart, no manual selection) with a
much smaller, more testable surface than a COM notification sink. The
worst-case latency between a founder putting on a headset and Somesh
hearing through it is a stated trade-off, not an oversight — see
`Engineering/HEALTH_C34_1.md` §3 for the argument and the event-driven
alternative for whoever wants to close that gap later. It is
`DEVICE_POLL_INTERVAL_S` (1.5s, detection) plus real `InputStream` open
mechanics — measured at ~0.77s on the dev machine, `Engineering/
HEALTH_C34_2.md` §9 — for a real total nearer 2.3s than the "2 seconds"
this comment used to claim from reasoning about the poll interval alone.

## Amplitude is real, not the fallback constant

`02_ANIMATION_SYSTEM.md §2.2.4` names a fallback: *"When the voice
pipeline does not provide `rawAmplitude`... the system uses a fixed
`voiceEnvelope = 0.55`."* This module always provides it — the RMS of
the actual microphone input while listening, and the RMS of the actual
synthesised audio while speaking — so the tree's pulse genuinely tracks
what Somesh is doing, not a constant standing in for it. The fallback
constant in `tree.js` is kept for the one case this module cannot help:
a machine with no working audio device at all.
"""
from __future__ import annotations

import threading
import time
from collections.abc import Callable

import numpy as np

#: Whisper's own required input rate.
SAMPLE_RATE = 16000
#: One audio callback block, in samples — 30ms, a common VAD window size.
BLOCK_SIZE = int(SAMPLE_RATE * 0.030)
#: RMS above this is "the founder is speaking". Calibrated for a typical
#: laptop/headset mic at conversational distance; not founder-adjustable
#: in this build (no settings surface exists for it yet).
VAD_ENERGY_THRESHOLD = 0.012
#: How long a stretch of RMS-below-threshold ends an utterance.
SILENCE_HANGOVER_S = 0.8
#: An utterance shorter than this is treated as noise, not speech —
#: never sent to Whisper, never surfaced as "you said nothing".
MIN_UTTERANCE_S = 0.3
#: Hard ceiling so a stuck-open mic cannot buffer forever.
MAX_UTTERANCE_S = 20.0
#: How often the default input device is re-queried.
DEVICE_POLL_INTERVAL_S = 1.5
#: How often amplitude pushes reach the page — throttled well below the
#: audio callback's own ~33Hz so `evaluate_js` stays cheap.
AMPLITUDE_PUSH_INTERVAL_S = 1 / 20

#: The mic states this module can report — all nine of
#: `03_VOICE_EXPERIENCE §3.1`, including `denied`. This module never reads
#: the OS permission itself — `master_agent.founder_edition` is guarded
#: against importing `os`/`winreg` directly (see
#: `test_founder_edition_boot.py::TestNothingExecutesOrCallsAI`); the real
#: check (`kalpavriksha_desktop._windows_microphone_allowed`) is injected
#: through `mic_permission_checker`, the same seam `sounddevice_module`
#: and the model factories already use.
STATE_ARMED = "armed"
STATE_CAPTURING = "capturing-speech"
STATE_PROCESSING = "processing"
STATE_MUTED = "muted"
STATE_DENIED = "denied"
STATE_UNAVAILABLE = "unavailable"
STATE_ERROR = "error"
STATE_SPEAKING = "speaking"

#: C34.2's Voice Session Manager deliverable — the complete transition
#: table, in one place, rather than left implicit across the booleans
#: and `_on_state()` call sites below. `None` as `from` means "before
#: the first push has happened at all" (no state shown yet). Every
#: entry traces to a real call site; `tests/test_voice_pipeline.py::
#: TestStateTransitionTable` checks every listed `to` is one of the
#: constants above, so this table cannot silently drift from the states
#: this module can actually produce.
#:
#: Two things this table does NOT capture, because they are not
#: sequencing bugs: (1) `speaking` is pushed on the same channel as
#: every mic state but is conceptually orthogonal to it (the tree-only
#: state `desktop_app/web/js/app.js` reads it as) — a reply can arrive
#: to speak from `armed` or `muted` and always returns to whichever one
#: the founder's mute preference says, not to whatever the mic was
#: mid-utterance. (2) `_device_watch_loop` runs independently of
#: `_speak_sync` on its own thread, so a permission revocation or
#: device change can supersede `speaking` with `denied`/`unavailable`/
#: `error` at any moment — the same way it supersedes `armed`/`muted`.
STATE_TRANSITIONS: tuple[tuple[str | None, str, str], ...] = (
    # startup — _load_and_open -> _sync_stream_to_permission -> _open_stream
    (None, "models fail to load", STATE_ERROR),
    (None, "OS denies microphone permission", STATE_DENIED),
    (None, "permission granted, no input device found", STATE_UNAVAILABLE),
    (None, "permission granted, device open fails (busy/error)", STATE_ERROR),
    (None, "permission granted, device opens, founder pre-muted", STATE_MUTED),
    (None, "permission granted, device opens, not muted", STATE_ARMED),
    # listening / capture — _audio_callback, _end_utterance, _transcribe
    (STATE_ARMED, "VAD detects speech onset", STATE_CAPTURING),
    (STATE_CAPTURING, "utterance ends (silence hangover or max duration)", STATE_PROCESSING),
    (STATE_CAPTURING, "founder starts typing, abandoning the utterance, not muted", STATE_ARMED),
    (STATE_CAPTURING, "founder starts typing, abandoning the utterance, muted", STATE_MUTED),
    (STATE_PROCESSING, "transcription completes, not muted", STATE_ARMED),
    (STATE_PROCESSING, "transcription completes, muted meanwhile", STATE_MUTED),
    # founder-chosen mute — set_muted()
    (STATE_ARMED, "founder mutes", STATE_MUTED),
    (STATE_MUTED, "founder unmutes", STATE_ARMED),
    # permission changes mid-session — _device_watch_loop -> _sync_stream_to_permission
    (STATE_ARMED, "OS revokes microphone permission", STATE_DENIED),
    (STATE_MUTED, "OS revokes microphone permission", STATE_DENIED),
    (STATE_DENIED, "OS grants permission, device opens", STATE_ARMED),
    (STATE_DENIED, "OS grants permission, device opens, pre-muted", STATE_MUTED),
    (STATE_DENIED, "OS grants permission, no device found", STATE_UNAVAILABLE),
    (STATE_DENIED, "OS grants permission, device open fails", STATE_ERROR),
    # device changes and recovery — _device_watch_loop -> _open_stream
    (STATE_ARMED, "default input device changes (e.g. Bluetooth), reopen succeeds", STATE_ARMED),
    (STATE_MUTED, "default input device changes, reopen succeeds", STATE_MUTED),
    (STATE_UNAVAILABLE, "a device becomes available", STATE_ARMED),
    (STATE_ERROR, "the busy/erroring device becomes free, reopen succeeds", STATE_ARMED),
    (STATE_ERROR, "the busy/erroring device becomes free, reopen succeeds, pre-muted", STATE_MUTED),
    # speaking — speak() / _speak_sync() / interrupt_speech()
    (STATE_ARMED, "a reply arrives to speak", STATE_SPEAKING),
    (STATE_MUTED, "a reply arrives to speak", STATE_SPEAKING),
    (STATE_SPEAKING, "VAD detects the founder speaking over Somesh (barge-in)", STATE_CAPTURING),
    (STATE_SPEAKING, "speech ends (natural completion or any interrupt trigger), not muted", STATE_ARMED),
    (STATE_SPEAKING, "speech ends (natural completion or any interrupt trigger), muted", STATE_MUTED),
)


class VoicePipeline:
    """Owns one microphone stream and one TTS voice. Constructed once by
    `desktop_shell.create_window()`, started after the native window
    exists (its callbacks push into that window), stopped when the
    window closes.

    Every callback (`on_state`, `on_amplitude`, `on_transcript`) is
    called from a background thread — the caller (`desktop_shell.py`) is
    responsible for marshalling onto the UI thread, which `pywebview`'s
    own `window.evaluate_js` already does safely from any thread.
    """

    def __init__(
        self,
        *,
        on_state: Callable[[str], None],
        on_amplitude: Callable[[float], None],
        on_transcript: Callable[[str], None],
        whisper_model: str = "base.en",
        piper_model_path: str | None = None,
        sounddevice_module=None,
        whisper_model_factory=None,
        piper_voice_factory=None,
        mic_permission_checker=None,
        input_device_resolver=None,
        output_device_resolver=None,
    ) -> None:
        self._on_state = on_state
        self._on_amplitude = on_amplitude
        self._on_transcript = on_transcript
        self._whisper_model_name = whisper_model
        self._piper_model_path = piper_model_path

        # Injected for testability — production callers omit all six
        # and get the real `sounddevice`/`faster_whisper`/`piper` modules
        # plus `_windows_microphone_allowed` and the C34.4 live-device
        # resolvers, imported/resolved lazily so this module stays
        # importable without them.
        self._sd = sounddevice_module
        self._whisper_factory = whisper_model_factory
        self._piper_factory = piper_voice_factory
        self._permission_checker = mic_permission_checker
        # C34.4 — the OS's actual live default device, bypassing
        # PortAudio's own cache (HEALTH_C34_3.md §3, HEALTH_C34_4.md).
        # `None` (no resolver injected) preserves the pre-C34.4 behavior
        # exactly: fall back to sounddevice's own (cache-prone) default
        # resolution, which is still correct for the very first device
        # the app opens on launch.
        self._input_device_resolver = input_device_resolver
        self._output_device_resolver = output_device_resolver

        self._stt_model = None
        self._tts_voice = None
        self._stream = None
        self._current_device_name: str | None = None
        self._permission_denied = False

        self._running = False
        self._muted = False
        self._speaking = False
        self._speech_interrupted = False
        self._speak_thread: threading.Thread | None = None
        self._in_speech = False
        self._silence_since: float | None = None
        self._speech_buffer: list[np.ndarray] = []
        self._utterance_started_at: float | None = None
        self._last_amplitude_push = 0.0
        self._lock = threading.Lock()

    # ---- lifecycle -----------------------------------------------------

    def start(self) -> None:
        self._running = True
        threading.Thread(target=self._load_and_open, daemon=True).start()

    def stop(self) -> None:
        self._running = False
        self.interrupt_speech()
        self._close_stream()

    # ---- founder-facing controls ----------------------------------------

    def set_muted(self, muted: bool) -> None:
        self._muted = muted
        if self._stt_model is not None:
            self._on_state(STATE_MUTED if muted else STATE_ARMED)

    def speak(self, text: str) -> None:
        """Synthesise and play `text`, pushing a real amplitude envelope
        and driving the mic state to `speaking` and back. Runs on its
        own thread — never blocks the caller for the full reply (
        `desktop_shell.send_message`, answering a bridge call the page
        is awaiting) — but if a previous reply is still speaking, this
        call first interrupts it and waits (briefly — `interrupt_speech`
        makes the block a currently-running `sd.play()` is in return
        almost immediately) for that thread to actually exit. C34.2:
        without this, a second `speak()` arriving before the first
        finishes started a second `_speak_sync` thread concurrently —
        two threads calling `sd.play()` on the shared default output
        stream at once, and racing on `_speaking`/`_speech_interrupted`.
        `03_VOICE_EXPERIENCE`'s own rule that interruption is instant
        applies here too, not just to a founder-triggered interrupt."""
        if self._tts_voice is None or not text.strip():
            return
        self.interrupt_speech()
        old_thread = self._speak_thread
        if old_thread is not None and old_thread.is_alive():
            old_thread.join(timeout=1.0)
        self._speak_thread = threading.Thread(target=self._speak_sync, args=(text,), daemon=True)
        self._speak_thread.start()

    def interrupt_speech(self) -> None:
        """`03_VOICE_EXPERIENCE §3.4`: "audio playback halts immediately
        — mid-word, mid-phoneme... No fade-out." Called from the bridge
        when the founder types, clicks the mic, or presses Escape while
        Somesh is speaking, and from `_audio_callback` itself when the
        VAD detects the founder speaking over Somesh — the fourth
        trigger, the one this class alone can see. A no-op when nothing
        is speaking, so every caller can invoke it unconditionally."""
        if not self._speaking:
            return
        self._speech_interrupted = True
        sd = self._resolve_sd()
        try:
            sd.stop()
        except Exception:  # noqa: BLE001 — the loop's own flag check ends playback either way
            pass

    def abandon_capture(self) -> None:
        """`03_VOICE_EXPERIENCE §3.7` "Founder starts typing mid-utterance
        (voice was `capturing-speech`)": *"Whatever was captured in the
        utterance up to the keystroke is discarded by the runtime. The
        UI does not show a partial transcript from an interrupted
        utterance."* This is the counterpart to `interrupt_speech()` for
        the founder's own in-flight voice rather than Somesh's — without
        it, an utterance abandoned by typing would still finish on its
        own (silence hangover or `MAX_UTTERANCE_S`) and surface as a
        stray, unwanted message moments after the founder had already
        moved on to text. A no-op when nothing is being captured, so
        every caller can invoke it unconditionally, same as
        `interrupt_speech()`."""
        with self._lock:
            if not self._in_speech:
                return
            self._in_speech = False
            self._speech_buffer = []
            self._silence_since = None
            self._utterance_started_at = None
        self._on_state(STATE_MUTED if self._muted else STATE_ARMED)

    # ---- model + stream setup --------------------------------------------

    def _resolve_sd(self):
        if self._sd is not None:
            return self._sd
        import sounddevice as sd
        return sd

    def _resolve_permission_checker(self):
        if self._permission_checker is not None:
            return self._permission_checker
        # No checker injected — this module cannot read OS permission
        # state itself (see the STATE_DENIED comment above), so an absent
        # checker means "unknown", which fails open exactly like an
        # injected checker that raises, just below.
        return lambda: True

    def _permission_granted(self) -> bool:
        try:
            return bool(self._resolve_permission_checker()())
        except Exception:  # noqa: BLE001 — an unreadable permission source must not block a working mic
            return True

    def _live_device_name(self, resolver) -> str | None:
        """C34.4 — the injected resolver's answer for "what does the OS
        actually say is default right now", or `None` if no resolver was
        injected or it failed. Never raises."""
        if resolver is None:
            return None
        try:
            return resolver()
        except Exception:  # noqa: BLE001 — an unreadable live source must not block a working mic
            return None

    def _resolve_input_device(self, sd):
        """Returns `(device_arg, device_name)` for opening the input
        stream. When the injected live resolver names a device that
        PortAudio's own (possibly stale, see the module docstring)
        device table still happens to list, that device's explicit
        index is returned — bypassing whichever device PortAudio itself
        would have picked as "default". Falls back to `(None, None)`
        (sounddevice's own default resolution, the pre-C34.4 behavior)
        whenever the live name is unavailable or not found in the
        table — a device PortAudio has never heard of cannot be opened
        by name no matter which source named it."""
        live_name = self._live_device_name(self._input_device_resolver)
        if not live_name:
            return None, None
        try:
            devices = sd.query_devices()
        except Exception:  # noqa: BLE001 — fall back to default resolution
            return None, None
        for idx, d in enumerate(devices):
            if self._names_match(live_name, d.get("name")) and d.get("max_input_channels", 0) > 0:
                return idx, live_name
        return None, None

    def _resolve_output_device(self, sd):
        """Same as `_resolve_input_device`, for playback — used fresh at
        the start of every `speak()` call so each reply follows whatever
        the OS's default output is at that moment."""
        live_name = self._live_device_name(self._output_device_resolver)
        if not live_name:
            return None
        try:
            devices = sd.query_devices()
        except Exception:  # noqa: BLE001 — fall back to default resolution
            return None
        for idx, d in enumerate(devices):
            if self._names_match(live_name, d.get("name")) and d.get("max_output_channels", 0) > 0:
                return idx
        return None

    @staticmethod
    def _names_match(live_name: str, table_name: str | None) -> bool:
        """A prefix match, not exact equality: PortAudio lists the same
        physical device once per host API (WDM, WASAPI, MME, DirectSound
        all show up separately in `sd.query_devices()`), and at least
        the classic MME entry truncates long names to a fixed buffer —
        confirmed on this dev machine, where WASAPI's entry for the
        default microphone reads `"Microphone Array (2- Realtek(R)
        Audio)"` (matching pycaw's live `FriendlyName` exactly) while the
        MME entry for the identical hardware reads `"Microphone Array
        (2- Realtek(R)"`, cut off mid-word. Exact equality would still
        find the untruncated WASAPI entry further down the table on this
        machine, but there is no guarantee every device has an
        untruncated entry at all — a prefix match in either direction
        catches a truncated table entry without needing one."""
        if table_name is None:
            return False
        shorter, longer = sorted((live_name, table_name), key=len)
        return longer.startswith(shorter)

    def _close_stream(self) -> None:
        if self._stream is None:
            return
        try:
            self._stream.stop()
            self._stream.close()
        except Exception:  # noqa: BLE001, S110 — the stream is being discarded anyway
            pass
        self._stream = None

    def _load_and_open(self) -> None:
        try:
            if self._whisper_factory is not None:
                self._stt_model = self._whisper_factory(self._whisper_model_name)
            else:  # pragma: no cover — real model load; verified manually, see HEALTH_C34_1 §2
                from faster_whisper import WhisperModel
                self._stt_model = WhisperModel(
                    self._whisper_model_name, device="cpu", compute_type="int8",
                )

            if self._piper_model_path:
                if self._piper_factory is not None:
                    self._tts_voice = self._piper_factory(self._piper_model_path)
                else:  # pragma: no cover — real model load; verified manually, see HEALTH_C34_1 §2
                    from piper import PiperVoice
                    self._tts_voice = PiperVoice.load(self._piper_model_path)
        except Exception:  # noqa: BLE001 — an unloadable model is an honest absence
            self._on_state(STATE_ERROR)
            return

        self._sync_stream_to_permission()
        threading.Thread(target=self._device_watch_loop, daemon=True).start()

    def _sync_stream_to_permission(self) -> None:
        """Opens the input stream if the OS grants microphone access,
        otherwise closes it and reports `denied` — the one state
        `_open_stream()` alone cannot produce, since PortAudio surfaces a
        mic blocked by OS privacy settings and a genuinely absent one as
        the same kind of failure."""
        if self._permission_granted():
            self._permission_denied = False
            self._open_stream()
        else:
            self._permission_denied = True
            self._close_stream()
            self._on_state(STATE_DENIED)

    def _open_stream(self) -> None:
        """Opens the input stream, or reports why it could not — and
        never raises. This method runs on both the startup thread and
        `_device_watch_loop`'s own thread; an uncaught exception here
        used to kill whichever one called it (silently, since both are
        daemon threads), which meant a busy/erroring device on open
        didn't just fail once — it permanently stopped all future
        reconnect attempts for the rest of the session. C34.2.

        C34.4: `device_arg` is an explicit PortAudio index when the live
        WASAPI resolver named a device the (possibly stale) device table
        still lists — bypassing whichever device `device=None` would
        have resolved to by asking PortAudio's own cached notion of
        "default". `device_info` still comes from `sd.query_devices()`
        for its metadata even when an explicit index is used; the index
        is what actually decides which physical device opens."""
        sd = self._resolve_sd()
        device_arg, live_name = self._resolve_input_device(sd)
        try:
            device_info = sd.query_devices(device_arg, kind="input") if device_arg is not None else sd.query_devices(kind="input")
        except Exception:  # noqa: BLE001 — no input device is an honest state
            self._on_state(STATE_UNAVAILABLE)
            return

        self._close_stream()

        try:
            stream = sd.InputStream(
                device=device_arg,
                samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                blocksize=BLOCK_SIZE, callback=self._audio_callback,
            )
            stream.start()
        except Exception:  # noqa: BLE001 — a busy/removed device on open is an honest error, not a crash
            self._on_state(STATE_ERROR)
            return

        self._current_device_name = live_name or device_info.get("name")
        self._stream = stream
        self._on_state(STATE_MUTED if self._muted else STATE_ARMED)

    def _device_watch_loop(self) -> None:
        """Polls both the default input device and the OS microphone
        permission every `DEVICE_POLL_INTERVAL_S` — the same cadence
        covers a headset swap and a founder granting/revoking access in
        Windows Settings while Kalpavriksha is running, so either kind of
        change is picked up automatically, without a restart.

        C34.4: the "did the device change" check itself prefers the live
        WASAPI resolver over `sd.query_devices()` — the latter is what
        `HEALTH_C34_3.md` §3 proved never changes within a running
        process no matter how long a founder waits. Falls back to the
        pre-C34.4 `sd.query_devices()` comparison when no resolver was
        injected, so a machine without it (or a unit test) behaves
        exactly as before."""
        sd = self._resolve_sd()
        while self._running:
            time.sleep(DEVICE_POLL_INTERVAL_S)
            currently_denied = not self._permission_granted()
            if currently_denied != self._permission_denied:
                self._sync_stream_to_permission()
                continue
            if currently_denied:
                continue
            live_name = self._live_device_name(self._input_device_resolver)
            if live_name is not None:
                if live_name != self._current_device_name:
                    self._open_stream()
                continue
            try:
                device_info = sd.query_devices(kind="input")
            except Exception:  # noqa: BLE001, S112 — a transient query failure just waits for the next poll
                continue
            if device_info.get("name") != self._current_device_name:
                self._open_stream()

    # ---- the audio callback: VAD, amplitude, buffering -------------------

    def _audio_callback(self, indata, _frames, _time_info, _status) -> None:
        if self._muted:
            return
        chunk = np.asarray(indata)[:, 0].astype("float32", copy=False)
        rms = self._rms(chunk)
        self._maybe_push_amplitude(rms)

        now = time.monotonic()
        speaking = rms > VAD_ENERGY_THRESHOLD

        with self._lock:
            if speaking:
                if not self._in_speech:
                    self._in_speech = True
                    self._speech_buffer = []
                    self._utterance_started_at = now
                    if self._speaking:
                        # 03_VOICE_EXPERIENCE §3.4 trigger 2 — the VAD
                        # confirmed the founder speaking over Somesh.
                        # `interrupt_speech()` calls `sd.stop()`, which
                        # this real-time audio callback must not do
                        # itself — moved to its own thread, same
                        # discipline `_end_utterance`'s transcription
                        # dispatch already uses.
                        threading.Thread(target=self.interrupt_speech, daemon=True).start()
                    self._on_state(STATE_CAPTURING)
                self._silence_since = None
                self._speech_buffer.append(chunk)
            elif self._in_speech:
                self._speech_buffer.append(chunk)
                if self._silence_since is None:
                    self._silence_since = now

            if self._in_speech:
                # MAX_UTTERANCE_S is checked unconditionally, not only
                # while silent — a founder who never pauses must still
                # be cut off, not buffered forever.
                over_silence = (
                    self._silence_since is not None
                    and (now - self._silence_since) >= SILENCE_HANGOVER_S
                )
                over_max = (now - (self._utterance_started_at or now)) >= MAX_UTTERANCE_S
                if over_silence or over_max:
                    self._end_utterance()

    @staticmethod
    def _rms(chunk: np.ndarray) -> float:
        if chunk.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(chunk))))

    def _maybe_push_amplitude(self, rms: float) -> None:
        now = time.monotonic()
        if now - self._last_amplitude_push < AMPLITUDE_PUSH_INTERVAL_S:
            return
        self._last_amplitude_push = now
        # A calibration gain so ordinary speech reaches useful amplitude
        # without clipping every plosive to 1.0 — presentation shaping,
        # the same role `03_VOICE_EXPERIENCE`'s own per-bar smoothing plays
        # on the JS side; this module hands the page a real, bounded value.
        self._on_amplitude(min(1.0, rms * 12.0))

    def _end_utterance(self) -> None:
        buffer = list(self._speech_buffer)
        self._in_speech = False
        self._speech_buffer = []
        self._silence_since = None
        self._utterance_started_at = None
        self._on_state(STATE_PROCESSING)
        threading.Thread(target=self._transcribe, args=(buffer,), daemon=True).start()

    def _transcribe(self, buffer: list[np.ndarray]) -> None:
        audio = np.concatenate(buffer) if buffer else np.zeros(0, dtype="float32")
        try:
            if len(audio) >= SAMPLE_RATE * MIN_UTTERANCE_S and self._stt_model is not None:
                segments, _info = self._stt_model.transcribe(audio, language="en")
                text = "".join(segment.text for segment in segments).strip()
            else:
                text = ""
        except Exception:  # noqa: BLE001 — a failed transcription is silence, not a crash
            text = ""
        self._on_state(STATE_MUTED if self._muted else STATE_ARMED)
        if text:
            self._on_transcript(text)

    # ---- speaking ---------------------------------------------------------

    def _speak_sync(self, text: str) -> None:
        sd = self._resolve_sd()
        # C34.4 — resolved once per reply, not once per chunk: the live
        # default output rarely changes mid-utterance, and re-querying
        # WASAPI on every chunk would add COM overhead to the playback
        # loop for no real benefit. `None` (no resolver, or the named
        # device isn't in PortAudio's table) means sd.play()'s own
        # default resolution, exactly the pre-C34.4 behavior.
        output_device = self._resolve_output_device(sd)
        self._speaking = True
        self._speech_interrupted = False
        self._on_state(STATE_SPEAKING)
        try:
            for chunk in self._tts_voice.synthesize(text):
                if self._speech_interrupted:
                    break
                audio = chunk.audio_float_array
                rms = self._rms(audio)
                self._on_amplitude(min(1.0, rms * 4.0))
                sd.play(audio, samplerate=chunk.sample_rate, blocking=True, device=output_device)
        except Exception:  # noqa: BLE001, S110 — playback failure ends speech, not the app
            pass
        self._speaking = False
        self._on_state(STATE_MUTED if self._muted else STATE_ARMED)
