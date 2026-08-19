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

import logging
import numpy as np

#: Whisper's own required input rate.
SAMPLE_RATE = 16000
#: One audio callback block, in samples — 30ms, a common VAD window size.
BLOCK_SIZE = int(SAMPLE_RATE * 0.030)
#: RMS above this is 'the founder is speaking'. 0.005 is calibrated to
#: catch normal conversational speech through Bluetooth headsets and
#: laptop internal mics — the previous 0.012 excluded quiet devices.
VAD_ENERGY_THRESHOLD = 0.005
#: How long a stretch of RMS-below-threshold ends an utterance.
SILENCE_HANGOVER_S = 0.8
#: An utterance shorter than this is treated as noise, not speech —
#: never sent to Whisper, never surfaced as "you said nothing".
MIN_UTTERANCE_S = 0.3
#: How long after Somesh stops speaking the microphone keeps ignoring
#: input, so the tail of the room's own reverb is not captured as the
#: founder. Short enough that answering immediately still works.
ECHO_GUARD_TAIL_S = 0.35
#: A transcript shorter than this many characters (after stripping)
#: is treated as noise — never surfaced as speech.
MIN_VALID_TRANSCRIPT_LENGTH = 2
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


def _avg_no_speech_prob(segments: list) -> float | None:
    """Extract average no-speech probability from faster-whisper segments.

    Returns None if the segment data is not available.
    """
    if not segments:
        return None
    probs = []
    for seg in segments:
        # faster-whisper segments have .no_speech_prob attribute
        nsp = getattr(seg, 'no_speech_prob', None)
        if nsp is not None:
            probs.append(nsp)
    if not probs:
        return None
    return sum(probs) / len(probs)


def _is_valid_transcript(text: str, duration_s: float, rms: float) -> bool:
    """Reject hallucinated/noise transcripts that Whisper produces from silence.

    Returns True only if the transcript appears to be real speech.
    """
    if not text or not text.strip():
        return False
    t = text.strip()
    lower = t.lower()

    # Reject known Whisper hallucination phrases on noise/silence
    _HALLUCINATION_PHRASES = (
        "you", "thank you", "thanks", "i got you", "i get you",
        "got you", "you got it", "okay", "ok", "yeah", "yes",
        "no", "i see", "i know", "right", "sure", "fine",
        "good", "bye", "goodbye", "sorry", "please",
        "hmm", "huh", "um", "uh", "ah", "oh", "wow",
    )
    # Reject bare hallucination words
    if lower in _HALLUCINATION_PHRASES:
        return False
    # Reject very short hallucination-like phrases
    if len(t) <= 10 and lower in _HALLUCINATION_PHRASES:
        return False

    # Reject ultra-short noise artifacts
    if len(t) < MIN_VALID_TRANSCRIPT_LENGTH:
        return False

    # Reject single-punctuation or non-word transcripts
    alpha_chars = sum(1 for c in t if c.isalpha())
    if alpha_chars < 1:
        return False

    # For very short utterances (<1s), require at least a real word
    if duration_s < 1.0 and alpha_chars < 3:
        return False

    # Reject if RMS is extremely low (pure noise with hallucinated text)
    if rms < 0.0005:
        return False

    return True


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
        self._transcription_in_flight = False
        self._echo_guard_until = 0.0
        self._utterance_id = 0
        self._transcript_sent_for_id = 0
        # The one caller that can legitimately call speak() before Piper
        # has finished loading — the startup greeting, fired the instant
        # the page's own script runs, racing `_load_and_open()`'s model
        # load on its own thread. One slot, not a queue: nothing else
        # calls speak() this early, and a later real reply arriving before
        # the greeting flushes should simply replace it, not queue behind
        # it — a founder catching up mid-load hears the newest thing said
        # to them, not a backlog.
        self._pending_speech: str | None = None

    # ---- lifecycle -----------------------------------------------------

    def start(self) -> None:
        self._running = True
        threading.Thread(target=self._load_and_open, daemon=True).start()

    def stop(self) -> None:
        self._running = False
        self.interrupt_speech()
        self._close_stream()

    @property
    def stt_ready(self) -> bool:
        """For the startup diagnostics overlay — did Whisper load."""
        return self._stt_model is not None

    @property
    def tts_ready(self) -> bool:
        """For the startup diagnostics overlay — did Piper load."""
        return self._tts_voice is not None

    @property
    def mic_live(self) -> bool:
        """For the startup diagnostics overlay — is the physical
        microphone stream actually open right now. Distinct from
        `stt_ready`: that says a model was loaded into memory
        (INITIALIZED); this says a real `sd.InputStream` was opened and
        started against real hardware (LIVE DEVICE VERIFIED) — false
        while `denied`/`unavailable`/`error`, or before startup has
        reached `_open_stream()` at all."""
        return self._stream is not None

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
        applies here too, not just to a founder-triggered interrupt.

        Called before Piper has finished loading (`self._tts_voice is
        None`), this queues `text` instead of dropping it — see
        `_pending_speech`'s own docstring — and `_load_and_open()` flushes
        it the moment the model becomes ready."""
        if not text.strip():
            return
        if self._tts_voice is None:
            self._pending_speech = text
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
                logging.debug(f'Loading Whisper from: {self._whisper_model_name}')
                self._stt_model = WhisperModel(
                    self._whisper_model_name, device='cpu', compute_type='int8',
                )
                logging.debug('Whisper model loaded successfully')

            if self._piper_model_path:
                if self._piper_factory is not None:
                    self._tts_voice = self._piper_factory(self._piper_model_path)
                else:  # pragma: no cover — real model load; verified manually, see HEALTH_C34_1 §2
                    from piper import PiperVoice
                    logging.debug(f'Loading Piper from: {self._piper_model_path}')
                    self._tts_voice = PiperVoice.load(self._piper_model_path)
                    logging.debug('Piper voice loaded successfully')
        except Exception as exc:
            logging.error(f'Voice model load failed: {exc}', exc_info=True)
            self._on_state(STATE_ERROR)
            return

        # The startup greeting (or, in principle, any other early caller)
        # queued itself in `speak()` while `self._tts_voice` was still
        # `None` — flush it now that loading actually succeeded. Before
        # the mic stream, since TTS playback needs nothing from that path.
        if self._tts_voice is not None and self._pending_speech:
            pending, self._pending_speech = self._pending_speech, None
            self.speak(pending)

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

        logging.debug(f'[STT_DEVICE] opening: index={device_arg} name={device_info.get("name")} channels={device_info.get("max_input_channels")} sr={device_info.get("default_samplerate")} live_name={live_name}')

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
            try:
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
                except Exception:
                    continue
                if device_info.get("name") != self._current_device_name:
                    self._open_stream()
            except Exception:
                logging.exception("_device_watch_loop iteration failed — continuing")

    # ---- the audio callback: VAD, amplitude, buffering -------------------

    def _audio_callback(self, indata, _frames, _time_info, _status) -> None:
        try:
            self.__audio_callback(indata, _frames, _time_info, _status)
        except Exception:
            logging.exception("_audio_callback crashed — PortAudio thread survived")

    def __audio_callback(self, indata, _frames, _time_info, _status) -> None:
        if self._muted:
            return

        # HALF-DUPLEX WHILE SPEAKING. Without acoustic echo cancellation
        # this microphone cannot tell Somesh's own speaker output from the
        # founder, and on a laptop with no headset it always hears it. The
        # VAD below then read that echo as "the founder is speaking over
        # Somesh": it fired the barge-in interrupt (stamping "— interrupted"
        # into the conversation), captured the playback as an utterance,
        # transcribed it, and submitted it as a founder message -- which
        # produced a reply, which was spoken, which was heard again. That
        # feedback loop is what filled the surface with duplicated
        # messages and made the voice experience feel broken.
        #
        # Ignoring input while playing is the standard fix short of real
        # AEC, and it costs nothing this product needs: interrupting
        # Somesh is still one click on the microphone
        # (03_VOICE_EXPERIENCE §3.4 trigger 1, already wired in app.js).
        # Only VAD-triggered barge-in -- the trigger that cannot be made
        # reliable without AEC -- is what stops here.
        if self._speaking:
            self._echo_guard_until = time.monotonic() + ECHO_GUARD_TAIL_S
            return
        # The room keeps ringing briefly after playback stops; without this
        # tail the last word of Somesh's own sentence is still captured.
        if time.monotonic() < self._echo_guard_until:
            return

        chunk_raw = np.asarray(indata)[:, 0].astype("float32", copy=True)
        # Apply gain for low-sensitivity devices (Bluetooth headsets etc.)
        # The VAD threshold assumes normalised float32 [-1,1] but some
        # devices capture at -60 dBFS; 30× gain brings conversational
        # speech into the detectable range without excessive noise boost.
        chunk = chunk_raw * 15.0
        rms = self._rms(chunk)
        self._maybe_push_amplitude(rms)

        # Periodic RMS diagnostic — log every ~1s (50 chunks * 30ms = 1.5s)
        self._chunk_count = getattr(self, '_chunk_count', 0) + 1
        if self._chunk_count % 50 == 1:
            logging.debug(f'[STT_DIAG] chunk_rms={rms:.6f} peak={float(np.max(np.abs(chunk))):.6f} min={float(np.min(chunk)):.6f} max={float(np.max(chunk)):.6f}')

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
                self._speech_buffer.append(chunk_raw)
            elif self._in_speech:
                self._speech_buffer.append(chunk_raw)
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
        # Prevent duplicate transcriptions from the same utterance
        if self._transcription_in_flight:
            logging.debug("[STT_DIAG] _end_utterance: skipping — transcription already in flight")
            return
        buffer = list(self._speech_buffer)
        total_samples = sum(len(chunk) for chunk in buffer)
        logging.debug(f'[STT_DIAG] _end_utterance: chunks={len(buffer)} samples={total_samples} duration={total_samples/SAMPLE_RATE:.2f}s')
        self._in_speech = False
        self._speech_buffer = []
        self._silence_since = None
        self._utterance_started_at = None
        self._utterance_id = getattr(self, '_utterance_id', 0) + 1
        self._transcription_in_flight = True
        self._on_state(STATE_PROCESSING)
        threading.Thread(target=self._transcribe, args=(buffer,), daemon=True).start()

    def _transcribe(self, buffer: list[np.ndarray]) -> None:
        audio = np.concatenate(buffer) if buffer else np.zeros(0, dtype="float32")
        duration_s = len(audio) / SAMPLE_RATE
        audio_rms = self._rms(audio)
        logging.debug(f'[STT_DIAG] _transcribe: samples={len(audio)} duration={duration_s:.2f}s rms={audio_rms:.5f} peak={float(np.max(np.abs(audio))):.5f} stt_model={self._stt_model is not None}')
        text = ""
        try:
            if (len(audio) >= SAMPLE_RATE * MIN_UTTERANCE_S 
                and self._stt_model is not None):
                logging.debug(f'[STT_DIAG] calling Whisper.transcribe...')
                segments, info = self._stt_model.transcribe(audio, language="en")
                segs = list(segments)

                # --- extract no-speech probability from faster-whisper ---
                avg_nsp = _avg_no_speech_prob(segs)
                logging.debug(f'[STT_DIAG] segments={len(segs)} avg_no_speech_prob={avg_nsp}')

                # Reject if Whisper thinks it's mostly not speech
                if avg_nsp is not None and avg_nsp > 0.6:
                    logging.debug(f'[STT_DIAG] rejected: avg_no_speech_prob={avg_nsp} > 0.6')
                    text = ""
                else:
                    text = "".join(segment.text for segment in segs).strip()
                    logging.debug(f'[STT_DIAG] Whisper result: text="{text}" segments={len(segs)}')

                    # --- SPEECH QUALITY GATE ---
                    if not _is_valid_transcript(text, duration_s, audio_rms):
                        logging.debug(f'[STT_DIAG] transcript rejected by quality gate: "{text}"')
                        text = ""
            else:
                logging.debug(f'[STT_DIAG] skipping: len_ok={len(audio) >= SAMPLE_RATE * MIN_UTTERANCE_S} model_ok={self._stt_model is not None}')
        except Exception as exc:
            logging.error(f'[STT_DIAG] Whisper exception: {exc}', exc_info=True)
        self._transcription_in_flight = False
        self._on_state(STATE_MUTED if self._muted else STATE_ARMED)

        # MUTED means the founder's speech does not become a founder turn.
        #
        # `__audio_callback` already refuses to capture while muted, so the
        # obvious path was covered. This is the one that was not: an
        # utterance captured while live, transcribed on a worker thread
        # over the following seconds, and emitted here -- by which time the
        # founder may have muted. The line directly above reads `_muted` to
        # set the mic label, so the canonical value was known at this exact
        # point and simply not consulted; mute gated the display and
        # nothing else.
        #
        # A packaged session showed the cost: ambient speech reached the
        # conversation, an external reasoning provider, and the durable
        # audit while the microphone read MUTED. Nothing executed, but the
        # words left the machine.
        #
        # Checked HERE rather than in the callback that receives it,
        # because this is where the pipeline -- the canonical owner of
        # `_muted` -- decides whether an utterance is a founder turn. A
        # guard in the surface would be a second opinion about a state it
        # does not own.
        #
        # The utterance is still marked as sent, so un-muting cannot later
        # flush a transcript the founder muted through.
        if text:
            if not getattr(self, '_transcript_sent_for_id', 0) == self._utterance_id:
                self._transcript_sent_for_id = self._utterance_id
                if self._muted:
                    logging.debug(
                        "[STT_DIAG] transcript discarded: muted before transcription completed"
                    )
                else:
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
