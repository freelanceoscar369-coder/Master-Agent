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
2-second worst case latency between a founder putting on a headset and
Somesh hearing through it is a stated trade-off, not an oversight — see
`Engineering/HEALTH_C34_1.md` §3 for the argument and the event-driven
alternative for whoever wants to close that gap later.

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
    ) -> None:
        self._on_state = on_state
        self._on_amplitude = on_amplitude
        self._on_transcript = on_transcript
        self._whisper_model_name = whisper_model
        self._piper_model_path = piper_model_path

        # Injected for testability — production callers omit all four
        # and get the real `sounddevice`/`faster_whisper`/`piper` modules
        # plus `_windows_microphone_allowed`, imported/resolved lazily so
        # this module stays importable without them.
        self._sd = sounddevice_module
        self._whisper_factory = whisper_model_factory
        self._piper_factory = piper_voice_factory
        self._permission_checker = mic_permission_checker

        self._stt_model = None
        self._tts_voice = None
        self._stream = None
        self._current_device_name: str | None = None
        self._permission_denied = False

        self._running = False
        self._muted = False
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
        self._close_stream()

    # ---- founder-facing controls ----------------------------------------

    def set_muted(self, muted: bool) -> None:
        self._muted = muted
        if self._stt_model is not None:
            self._on_state(STATE_MUTED if muted else STATE_ARMED)

    def speak(self, text: str) -> None:
        """Synthesise and play `text`, pushing a real amplitude envelope
        and driving the mic state to `speaking` and back. Runs on its
        own thread — never blocks the caller (`desktop_shell.send_
        message`, answering a bridge call the page is awaiting)."""
        if self._tts_voice is None or not text.strip():
            return
        threading.Thread(target=self._speak_sync, args=(text,), daemon=True).start()

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
        sd = self._resolve_sd()
        try:
            device_info = sd.query_devices(kind="input")
        except Exception:  # noqa: BLE001 — no input device is an honest state
            self._on_state(STATE_UNAVAILABLE)
            return

        self._close_stream()

        self._current_device_name = device_info.get("name")
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="float32",
            blocksize=BLOCK_SIZE, callback=self._audio_callback,
        )
        self._stream.start()
        self._on_state(STATE_MUTED if self._muted else STATE_ARMED)

    def _device_watch_loop(self) -> None:
        """Polls both the default input device and the OS microphone
        permission every `DEVICE_POLL_INTERVAL_S` — the same cadence
        covers a headset swap and a founder granting/revoking access in
        Windows Settings while Kalpavriksha is running, so either kind of
        change is picked up automatically, without a restart."""
        sd = self._resolve_sd()
        while self._running:
            time.sleep(DEVICE_POLL_INTERVAL_S)
            currently_denied = not self._permission_granted()
            if currently_denied != self._permission_denied:
                self._sync_stream_to_permission()
                continue
            if currently_denied:
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
        self._on_state(STATE_SPEAKING)
        try:
            for chunk in self._tts_voice.synthesize(text):
                audio = chunk.audio_float_array
                rms = self._rms(audio)
                self._on_amplitude(min(1.0, rms * 4.0))
                sd.play(audio, samplerate=chunk.sample_rate, blocking=True)
        except Exception:  # noqa: BLE001, S110 — playback failure ends speech, not the app
            pass
        self._on_state(STATE_MUTED if self._muted else STATE_ARMED)
