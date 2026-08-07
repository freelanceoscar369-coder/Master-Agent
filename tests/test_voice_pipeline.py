"""The local voice pipeline — C34.1's release blocker 6.

Every test here uses injected fakes for `sounddevice`, the Whisper model,
and the Piper voice (`VoicePipeline`'s own constructor seam) — no test
opens a real microphone or plays real audio, so this suite runs on any
machine, with or without audio hardware. Round-trip fidelity against real
`faster-whisper`/`piper` models was verified manually this session
(`Engineering/HEALTH_C34_1.md` §2) and is not re-asserted here, since
re-running full ML inference on every test run would make this suite
slow and machine-dependent.
"""
from __future__ import annotations

import threading
import time

import numpy as np
import pytest

from master_agent.founder_edition.voice_pipeline import (
    MIN_UTTERANCE_S,
    STATE_ARMED,
    STATE_CAPTURING,
    STATE_DENIED,
    STATE_ERROR,
    STATE_MUTED,
    STATE_PROCESSING,
    STATE_SPEAKING,
    STATE_TRANSITIONS,
    STATE_UNAVAILABLE,
    VoicePipeline,
)

ALL_STATES = {
    STATE_ARMED, STATE_CAPTURING, STATE_PROCESSING, STATE_MUTED, STATE_DENIED,
    STATE_UNAVAILABLE, STATE_ERROR, STATE_SPEAKING,
}


class TestStateTransitionTable:
    """C34.2 — the table is documentation, not runtime-enforced control
    flow (see its own module-level docstring for why), so what a test
    can actually hold it to is structural: every `to` is a state this
    module can really produce, no duplicate (from, event) pair claims
    two different destinations, and every state the module defines
    appears somewhere as a destination — the "no state may become
    unreachable" requirement, checked mechanically."""

    def test_every_destination_is_a_real_state(self):
        for _from, _event, to in STATE_TRANSITIONS:
            assert to in ALL_STATES

    def test_no_from_and_event_pair_claims_two_destinations(self):
        seen: dict[tuple[str | None, str], str] = {}
        for from_state, event, to in STATE_TRANSITIONS:
            key = (from_state, event)
            assert key not in seen, f"{key} already maps to {seen.get(key)}"
            seen[key] = to

    def test_every_state_is_reachable_as_a_destination(self):
        reached = {to for _from, _event, to in STATE_TRANSITIONS}
        assert reached == ALL_STATES


class FakeStream:
    def __init__(self, callback, **kwargs) -> None:
        self.callback = callback
        self.kwargs = kwargs
        self.started = False
        self.closed = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False

    def close(self) -> None:
        self.closed = True


class FakeSoundDevice:
    def __init__(self, device_name: str = "Fake Mic") -> None:
        self.device_name = device_name
        self.streams: list[FakeStream] = []
        self.play_calls: list[tuple[int, int]] = []
        self.query_calls = 0
        self.fail_query = False
        self.fail_open = False
        self.stop_calls = 0

    def query_devices(self, kind=None):
        self.query_calls += 1
        if self.fail_query:
            raise RuntimeError("no device")
        return {"name": self.device_name}

    def InputStream(self, **kwargs):
        if self.fail_open:
            raise RuntimeError("device busy")
        stream = FakeStream(**kwargs)
        self.streams.append(stream)
        return stream

    def stop(self):
        self.stop_calls += 1

    def play(self, audio, samplerate=None, blocking=None):
        self.play_calls.append((len(audio), samplerate))


class FakeSegment:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeWhisperModel:
    def __init__(self, text: str = "hello world", raises: bool = False) -> None:
        self.text = text
        self.raises = raises
        self.calls = 0

    def transcribe(self, audio, language=None):
        self.calls += 1
        if self.raises:
            raise RuntimeError("transcription failed")
        return [FakeSegment(self.text)], None


class FakeAudioChunk:
    def __init__(self, level: float, samples: int = 400, sample_rate: int = 22050) -> None:
        self.audio_float_array = np.full(samples, level, dtype="float32")
        self.sample_rate = sample_rate


class FakeVoice:
    def __init__(self, chunks=None) -> None:
        self.chunks = chunks if chunks is not None else [FakeAudioChunk(0.4)]
        self.requests: list[str] = []

    def synthesize(self, text):
        self.requests.append(text)
        yield from self.chunks


class FakePermission:
    """Injected in place of the production `mic_permission_checker`
    (`kalpavriksha_desktop._windows_microphone_allowed`) — starts
    granted, like a machine where the founder has never touched the
    privacy toggle."""

    def __init__(self, granted: bool = True) -> None:
        self.granted = granted
        self.calls = 0

    def __call__(self) -> bool:
        self.calls += 1
        return self.granted


def build(
    *, device_name="Fake Mic", whisper_text="hello world", whisper_raises=False,
    piper_model_path="voice.onnx", piper_chunks=None, fail_query=False,
    permission_granted=True,
):
    states: list[str] = []
    amplitudes: list[float] = []
    transcripts: list[str] = []

    sd = FakeSoundDevice(device_name)
    sd.fail_query = fail_query
    whisper = FakeWhisperModel(text=whisper_text, raises=whisper_raises)
    voice_impl = FakeVoice(piper_chunks)
    permission = FakePermission(permission_granted)

    pipeline = VoicePipeline(
        on_state=states.append,
        on_amplitude=amplitudes.append,
        on_transcript=transcripts.append,
        sounddevice_module=sd,
        whisper_model_factory=lambda name: whisper,
        piper_model_path=piper_model_path,
        piper_voice_factory=lambda path: voice_impl,
        mic_permission_checker=permission,
    )
    return pipeline, sd, whisper, voice_impl, states, amplitudes, transcripts


def loud_block(level=0.5, n=480):
    return np.full((n, 1), level, dtype="float32")


def quiet_block(n=480):
    return np.zeros((n, 1), dtype="float32")


# ══════════════════════════ startup / device open ════════════════════════


class TestLoadAndOpen:
    def test_opens_a_stream_and_reports_armed(self):
        pipeline, sd, *_rest, states, _amp, _tx = build()
        pipeline._load_and_open()
        assert states == [STATE_ARMED]
        assert sd.streams[-1].started is True

    def test_reports_muted_if_muted_before_models_finished_loading(self):
        pipeline, *_rest, states, _amp, _tx = build()
        pipeline._muted = True
        pipeline._load_and_open()
        assert states[-1] == STATE_MUTED

    def test_reports_error_when_the_model_cannot_load(self):
        def boom(name):
            raise RuntimeError("model missing")

        states = []
        pipeline = VoicePipeline(
            on_state=states.append, on_amplitude=lambda a: None,
            on_transcript=lambda t: None,
            sounddevice_module=FakeSoundDevice(),
            whisper_model_factory=boom,
        )
        pipeline._load_and_open()
        assert states == [STATE_ERROR]

    def test_reports_unavailable_when_no_input_device_exists(self):
        pipeline, _sd, *_rest, states, _amp, _tx = build(fail_query=True)
        pipeline._load_and_open()
        assert states == [STATE_UNAVAILABLE]

    def test_skips_tts_loading_without_a_model_path(self):
        pipeline, *_rest, states, _amp, _tx = build(piper_model_path=None)
        pipeline._load_and_open()
        assert pipeline._tts_voice is None
        assert states == [STATE_ARMED]


# ══════════════════════════ device tracking ═══════════════════════════════


class TestOpenStreamRobustness:
    """C34.2 — a busy/erroring device on open used to raise uncaught out
    of `_open_stream()`, killing whichever daemon thread called it. On
    the startup thread that just stranded the mic with no state ever
    pushed; on `_device_watch_loop`'s own thread it was worse — the
    watch loop itself died, so no device change would ever be noticed
    again for the rest of the session."""

    def test_a_busy_device_reports_error_not_a_crash(self):
        pipeline, sd, *_rest, states, _amp, _tx = build()
        sd.fail_open = True
        pipeline._load_and_open()  # must not raise
        assert states == [STATE_ERROR]
        assert pipeline._stream is None

    def test_the_watch_loop_survives_repeated_busy_retries(self, monkeypatch):
        pipeline, sd, *_rest, states, _amp, _tx = build()
        sd.fail_open = True
        pipeline._load_and_open()
        assert states == [STATE_ERROR]

        pipeline._running = True
        calls = {"n": 0}

        def fake_sleep(_seconds):
            calls["n"] += 1
            if calls["n"] > 2:
                pipeline._running = False

        monkeypatch.setattr("time.sleep", fake_sleep)
        pipeline._device_watch_loop()  # must not raise across multiple failed retries
        assert states[-1] == STATE_ERROR

    def test_recovers_automatically_once_the_device_is_free(self, monkeypatch):
        pipeline, sd, *_rest, states, _amp, _tx = build()
        sd.fail_open = True
        pipeline._load_and_open()
        assert states == [STATE_ERROR]

        calls = {"n": 0}

        def fake_sleep(_seconds):
            calls["n"] += 1
            if calls["n"] == 1:
                sd.fail_open = False  # the device becomes free before the next retry
            if calls["n"] > 1:
                pipeline._running = False

        monkeypatch.setattr("time.sleep", fake_sleep)
        pipeline._running = True
        pipeline._device_watch_loop()

        assert states[-1] == STATE_ARMED
        assert sd.streams  # a real stream finally opened, no restart needed


class TestNoOverlappingPlayback:
    """C34.2 — `speak()` had no guard against a second reply arriving
    while the first was still playing; two `_speak_sync` threads could
    call `sd.play()` concurrently on the shared default output stream.
    `speak()` now interrupts and joins the previous thread first, so
    exactly one is ever alive."""

    def test_a_second_reply_never_overlaps_the_first(self):
        pipeline, sd, _whisper, voice, states, _amp, _tx = build(
            piper_chunks=[FakeAudioChunk(0.5, samples=800)],
        )
        pipeline._load_and_open()

        concurrency = {"active": 0, "max_seen": 0}
        lock = threading.Lock()
        original_play = sd.play

        def tracked_play(*a, **kw):
            with lock:
                concurrency["active"] += 1
                concurrency["max_seen"] = max(concurrency["max_seen"], concurrency["active"])
            time.sleep(0.15)  # held long enough that a real race would overlap
            original_play(*a, **kw)
            with lock:
                concurrency["active"] -= 1

        sd.play = tracked_play
        pipeline.speak("First reply.")
        time.sleep(0.03)  # let the first thread actually enter tracked_play
        pipeline.speak("Second reply.")  # speak() itself waits for the first to end
        time.sleep(0.3)

        assert concurrency["max_seen"] == 1
        assert voice.requests == ["First reply.", "Second reply."]
        assert states[-1] == STATE_ARMED

    def test_stop_interrupts_any_lingering_playback(self):
        pipeline, sd, _whisper, voice, states, _amp, _tx = build(
            piper_chunks=[FakeAudioChunk(0.5, samples=800), FakeAudioChunk(0.3, samples=800)],
        )
        pipeline._load_and_open()
        pipeline._speaking = True  # simulate mid-reply at window-close time

        pipeline.stop()

        assert sd.stop_calls == 1
        assert pipeline._speech_interrupted is True


class TestDeviceWatch:
    def test_reopens_the_stream_when_the_default_device_changes(self):
        pipeline, sd, *_rest = build()
        pipeline._load_and_open()
        first_stream = sd.streams[-1]

        sd.device_name = "New Bluetooth Headset"
        pipeline._running = True
        # one iteration of the watch loop's own body, without the sleep
        device_info = sd.query_devices(kind="input")
        assert device_info["name"] != pipeline._current_device_name
        pipeline._open_stream()

        assert first_stream.closed is True
        assert pipeline._current_device_name == "New Bluetooth Headset"
        assert sd.streams[-1] is not first_stream

    def test_does_not_reopen_when_the_device_is_unchanged(self):
        pipeline, sd, *_rest = build()
        pipeline._load_and_open()
        stream_count = len(sd.streams)

        device_info = sd.query_devices(kind="input")
        assert device_info["name"] == pipeline._current_device_name
        # no reopen call made — this is what the real watch loop does too

        assert len(sd.streams) == stream_count

    def test_watch_loop_tolerates_a_query_failure_without_crashing(self, monkeypatch):
        pipeline, sd, *_rest = build()
        pipeline._load_and_open()
        pipeline._running = True
        sd.fail_query = True

        monkeypatch.setattr("time.sleep", lambda _s: setattr(pipeline, "_running", False))
        pipeline._device_watch_loop()  # must return, not raise

    def test_watch_loop_reopens_on_a_real_device_change(self, monkeypatch):
        """One real iteration of `_device_watch_loop()`'s own body,
        including its reopen branch — not `_open_stream()` called
        directly, which the other tests already exercise in isolation."""
        pipeline, sd, *_rest = build()
        pipeline._load_and_open()
        first_stream = sd.streams[-1]
        sd.device_name = "New Bluetooth Headset"

        calls = {"n": 0}

        def fake_sleep(_seconds):
            calls["n"] += 1
            if calls["n"] > 1:
                pipeline._running = False

        monkeypatch.setattr("time.sleep", fake_sleep)
        pipeline._running = True
        pipeline._device_watch_loop()

        assert first_stream.closed is True
        assert pipeline._current_device_name == "New Bluetooth Headset"

    def test_reopen_tolerates_a_broken_old_stream(self):
        """The old stream fails to close cleanly (device already gone);
        the new one must still open."""
        pipeline, sd, *_rest = build()
        pipeline._load_and_open()
        pipeline._stream.stop = lambda: (_ for _ in ()).throw(RuntimeError("gone"))
        sd.device_name = "New Bluetooth Headset"
        pipeline._open_stream()
        assert pipeline._current_device_name == "New Bluetooth Headset"


# ══════════════════════════ mic permission (denied state) ═════════════════


class TestMicPermission:
    def test_reports_denied_instead_of_opening_a_stream(self):
        pipeline, sd, *_rest, states, _amp, _tx = build(permission_granted=False)
        pipeline._load_and_open()
        assert states == [STATE_DENIED]
        assert sd.streams == []

    def test_granted_permission_opens_normally_as_before(self):
        pipeline, sd, *_rest, states, _amp, _tx = build(permission_granted=True)
        pipeline._load_and_open()
        assert states == [STATE_ARMED]
        assert sd.streams[-1].started is True

    def test_watch_loop_recovers_automatically_once_permission_is_granted(self, monkeypatch):
        pipeline, sd, *_rest, states, _amp, _tx = build(permission_granted=False)
        pipeline._load_and_open()
        assert states == [STATE_DENIED]

        pipeline._permission_checker.granted = True
        pipeline._running = True
        calls = {"n": 0}

        def fake_sleep(_seconds):
            calls["n"] += 1
            if calls["n"] > 1:
                pipeline._running = False

        monkeypatch.setattr("time.sleep", fake_sleep)
        pipeline._device_watch_loop()

        assert states[-1] == STATE_ARMED
        assert sd.streams  # the stream was actually opened on recovery

    def test_watch_loop_revokes_and_closes_the_stream_when_permission_is_lost(self, monkeypatch):
        pipeline, sd, *_rest, states, _amp, _tx = build(permission_granted=True)
        pipeline._load_and_open()
        open_stream = sd.streams[-1]
        assert states == [STATE_ARMED]

        pipeline._permission_checker.granted = False
        pipeline._running = True
        calls = {"n": 0}

        def fake_sleep(_seconds):
            calls["n"] += 1
            if calls["n"] > 1:
                pipeline._running = False

        monkeypatch.setattr("time.sleep", fake_sleep)
        pipeline._device_watch_loop()

        assert states[-1] == STATE_DENIED
        assert open_stream.closed is True

    def test_watch_loop_does_not_poll_the_device_while_still_denied(self, monkeypatch):
        pipeline, sd, *_rest, states, _amp, _tx = build(permission_granted=False)
        pipeline._load_and_open()
        query_calls_before = sd.query_calls

        pipeline._running = True
        calls = {"n": 0}

        def fake_sleep(_seconds):
            calls["n"] += 1
            if calls["n"] > 1:
                pipeline._running = False

        monkeypatch.setattr("time.sleep", fake_sleep)
        pipeline._device_watch_loop()

        assert sd.query_calls == query_calls_before

    def test_an_unreadable_permission_source_fails_open_not_closed(self):
        def boom():
            raise OSError("registry unavailable")

        states = []
        pipeline = VoicePipeline(
            on_state=states.append, on_amplitude=lambda a: None,
            on_transcript=lambda t: None,
            sounddevice_module=FakeSoundDevice(),
            whisper_model_factory=lambda name: FakeWhisperModel(),
            mic_permission_checker=boom,
        )
        pipeline._load_and_open()
        assert states == [STATE_ARMED]

    def test_fails_open_when_no_checker_is_injected(self):
        """This module cannot read OS permission state itself (it is
        guarded against importing `os`/`winreg` — see the `STATE_DENIED`
        comment); an absent checker must mean "assume granted", not
        "assume denied"."""
        pipeline = VoicePipeline(
            on_state=lambda s: None, on_amplitude=lambda a: None, on_transcript=lambda t: None,
        )
        assert pipeline._resolve_permission_checker()() is True


# ══════════════════════════ VAD / capture / transcription ═════════════════


class TestAudioCallback:
    def test_ignores_audio_entirely_while_muted(self):
        pipeline, *_rest = build()
        pipeline._load_and_open()
        pipeline._muted = True
        pipeline._audio_callback(loud_block(), 480, None, None)
        assert pipeline._in_speech is False

    def test_loud_audio_enters_capturing_state(self):
        pipeline, _sd, _whisper, _voice, states, _amp, _tx = build()
        pipeline._load_and_open()
        pipeline._audio_callback(loud_block(), 480, None, None)
        assert states[-1] == STATE_CAPTURING
        assert pipeline._in_speech is True

    def test_amplitude_is_pushed_and_bounded_to_one(self):
        pipeline, *_rest, _states, amp, _tx = build()
        pipeline._load_and_open()
        pipeline._audio_callback(loud_block(level=10.0), 480, None, None)
        assert amp
        assert 0.0 <= amp[-1] <= 1.0

    def test_amplitude_pushes_are_throttled(self):
        pipeline, *_rest, _states, amp, _tx = build()
        pipeline._load_and_open()
        for _ in range(20):
            pipeline._audio_callback(loud_block(), 480, None, None)
        # throttled to ~20Hz; 20 back-to-back calls in the same instant
        # must not produce 20 pushes
        assert len(amp) < 20

    def test_a_short_utterance_below_the_minimum_produces_no_transcript(self):
        pipeline, _sd, whisper, _voice, _states, _amp, tx = build()
        pipeline._load_and_open()
        pipeline._audio_callback(loud_block(), 480, None, None)  # ~30ms, well under MIN_UTTERANCE_S
        pipeline._silence_since = time.monotonic() - 1.0
        pipeline._audio_callback(quiet_block(), 480, None, None)
        time.sleep(0.2)
        assert tx == []
        assert whisper.calls == 0

    def test_a_real_length_utterance_is_transcribed_and_pushed(self):
        pipeline, _sd, _whisper, _voice, states, _amp, tx = build(whisper_text="Good morning Somesh")
        pipeline._load_and_open()
        blocks_needed = int(MIN_UTTERANCE_S / 0.03) + 2
        for _ in range(blocks_needed):
            pipeline._audio_callback(loud_block(), 480, None, None)
        pipeline._silence_since = time.monotonic() - 1.0
        pipeline._audio_callback(quiet_block(), 480, None, None)
        time.sleep(0.3)
        assert tx == ["Good morning Somesh"]
        assert states[-1] == STATE_ARMED
        assert STATE_PROCESSING in states

    def test_a_transcription_failure_is_silence_not_a_crash(self):
        pipeline, _sd, _whisper, _voice, states, _amp, tx = build(whisper_raises=True)
        pipeline._load_and_open()
        blocks_needed = int(MIN_UTTERANCE_S / 0.03) + 2
        for _ in range(blocks_needed):
            pipeline._audio_callback(loud_block(), 480, None, None)
        pipeline._silence_since = time.monotonic() - 1.0
        pipeline._audio_callback(quiet_block(), 480, None, None)
        time.sleep(0.3)
        assert tx == []
        assert states[-1] == STATE_ARMED

    def test_silence_naturally_begins_tracking_without_manual_setup(self):
        """The ordinary path — no test manipulation of `_silence_since` —
        one loud block then one quiet block, which is not yet enough
        silence to end the utterance."""
        pipeline, *_rest = build()
        pipeline._load_and_open()
        pipeline._audio_callback(loud_block(), 480, None, None)
        pipeline._audio_callback(quiet_block(), 480, None, None)
        assert pipeline._in_speech is True
        assert pipeline._silence_since is not None

    def test_max_utterance_ceiling_ends_capture_even_without_silence(self):
        pipeline, _sd, _whisper, _voice, _states, _amp, _tx = build()
        pipeline._load_and_open()
        pipeline._audio_callback(loud_block(), 480, None, None)
        pipeline._utterance_started_at = time.monotonic() - 999.0
        pipeline._audio_callback(loud_block(), 480, None, None)
        time.sleep(0.2)
        assert pipeline._in_speech is False


# ══════════════════════════ mute ═══════════════════════════════════════════


class TestRms:
    def test_an_empty_chunk_is_zero_rather_than_nan(self):
        assert VoicePipeline._rms(np.zeros(0, dtype="float32")) == 0.0


class TestSetMuted:
    def test_reports_muted_when_models_are_already_loaded(self):
        pipeline, *_rest, states, _amp, _tx = build()
        pipeline._load_and_open()
        pipeline.set_muted(True)
        assert states[-1] == STATE_MUTED

    def test_reports_armed_on_unmute(self):
        pipeline, *_rest, states, _amp, _tx = build()
        pipeline._load_and_open()
        pipeline.set_muted(True)
        pipeline.set_muted(False)
        assert states[-1] == STATE_ARMED

    def test_before_models_load_it_only_records_the_preference(self):
        pipeline = VoicePipeline(
            on_state=lambda s: pytest.fail(f"unexpected push: {s}"),
            on_amplitude=lambda a: None, on_transcript=lambda t: None,
        )
        pipeline.set_muted(True)
        assert pipeline._muted is True


# ══════════════════════════ speaking ═══════════════════════════════════════


class TestSpeak:
    def test_synthesises_plays_and_returns_to_armed(self):
        pipeline, sd, _whisper, voice, states, _amp, _tx = build(
            piper_chunks=[FakeAudioChunk(0.5, samples=800), FakeAudioChunk(0.2, samples=400)],
        )
        pipeline._load_and_open()
        pipeline.speak("Good afternoon.")
        time.sleep(0.3)
        assert voice.requests == ["Good afternoon."]
        assert sd.play_calls == [(800, 22050), (400, 22050)]
        assert STATE_SPEAKING in states
        assert states[-1] == STATE_ARMED

    def test_does_nothing_without_a_loaded_voice(self):
        pipeline, sd, *_rest = build(piper_model_path=None)
        pipeline._load_and_open()
        pipeline.speak("hello")
        time.sleep(0.1)
        assert sd.play_calls == []

    def test_does_nothing_for_blank_text(self):
        pipeline, _sd, _whisper, voice, *_rest = build()
        pipeline._load_and_open()
        pipeline.speak("   ")
        time.sleep(0.1)
        assert voice.requests == []

    def test_returns_to_muted_if_the_founder_muted_while_speaking(self):
        pipeline, _sd, _whisper, _voice, states, _amp, _tx = build()
        pipeline._load_and_open()
        pipeline._muted = True
        pipeline.speak("hello")
        time.sleep(0.2)
        assert states[-1] == STATE_MUTED

    def test_playback_failure_still_returns_to_armed(self):
        pipeline, sd, _whisper, _voice, states, _amp, _tx = build()
        pipeline._load_and_open()

        def boom(*a, **kw):
            raise RuntimeError("device error")

        sd.play = boom
        pipeline.speak("hello")
        time.sleep(0.2)
        assert states[-1] == STATE_ARMED


# ══════════════════════════ interrupt (03_VOICE_EXPERIENCE §3.4) ══════════


class TestInterruptSpeech:
    def test_a_noop_when_nothing_is_speaking(self):
        pipeline, sd, *_rest = build()
        pipeline._load_and_open()
        pipeline.interrupt_speech()  # must not raise
        assert sd.stop_calls == 0

    def test_stops_before_the_next_chunk_and_returns_to_armed(self):
        pipeline, sd, _whisper, voice, states, _amp, _tx = build(
            piper_chunks=[
                FakeAudioChunk(0.5, samples=800), FakeAudioChunk(0.3, samples=800),
                FakeAudioChunk(0.1, samples=800),
            ],
        )
        pipeline._load_and_open()

        original_play = sd.play

        def play_then_interrupt(*a, **kw):
            original_play(*a, **kw)
            pipeline.interrupt_speech()

        sd.play = play_then_interrupt
        pipeline.speak("A longer reply than the founder wants to hear.")
        time.sleep(0.3)

        assert len(sd.play_calls) == 1  # cut mid-reply, never reached chunk 2 or 3
        assert sd.stop_calls == 1
        assert states[-1] == STATE_ARMED
        assert pipeline._speaking is False

    def test_a_stop_failure_still_ends_the_loop_via_the_flag(self):
        pipeline, sd, _whisper, voice, states, _amp, _tx = build(
            piper_chunks=[FakeAudioChunk(0.5, samples=800), FakeAudioChunk(0.3, samples=800)],
        )
        pipeline._load_and_open()

        def boom():
            raise RuntimeError("stop failed")

        sd.stop = boom
        original_play = sd.play

        def play_then_interrupt(*a, **kw):
            original_play(*a, **kw)
            pipeline.interrupt_speech()

        sd.play = play_then_interrupt
        pipeline.speak("hello")
        time.sleep(0.2)
        assert states[-1] == STATE_ARMED

    def test_founder_speech_onset_interrupts_active_speech(self):
        """03_VOICE_EXPERIENCE §3.4 trigger 2 — the VAD, not a bridge
        call, detects the founder speaking over Somesh."""
        pipeline, sd, *_rest = build()
        pipeline._load_and_open()
        pipeline._speaking = True

        pipeline._audio_callback(loud_block(), 480, None, None)
        time.sleep(0.2)

        assert pipeline._speech_interrupted is True
        assert sd.stop_calls == 1

    def test_no_interrupt_fires_when_somesh_is_not_speaking(self):
        pipeline, sd, *_rest = build()
        pipeline._load_and_open()
        pipeline._audio_callback(loud_block(), 480, None, None)
        time.sleep(0.1)
        assert sd.stop_calls == 0


# ══════════════════════════ lifecycle ══════════════════════════════════════


class TestLifecycle:
    def test_stop_closes_the_open_stream(self):
        pipeline, sd, *_rest = build()
        pipeline._load_and_open()
        pipeline._running = True
        pipeline.stop()
        assert pipeline._running is False
        assert sd.streams[-1].closed is True

    def test_stop_before_any_stream_opened_does_not_raise(self):
        pipeline = VoicePipeline(
            on_state=lambda s: None, on_amplitude=lambda a: None, on_transcript=lambda t: None,
        )
        pipeline.stop()  # must not raise

    def test_stop_tolerates_a_stream_that_raises_on_close(self):
        pipeline, _sd, *_rest = build()
        pipeline._load_and_open()

        def boom():
            raise RuntimeError("already gone")

        pipeline._stream.stop = boom
        pipeline.stop()  # must not raise
        assert pipeline._stream is None

    def test_start_launches_a_background_thread(self):
        pipeline, sd, *_rest = build()
        pipeline.start()
        time.sleep(0.3)
        assert pipeline._running is True
        assert sd.streams  # the loader thread reached _open_stream
        pipeline.stop()

    def test_resolve_sd_returns_the_real_module_when_none_was_injected(self):
        pipeline = VoicePipeline(
            on_state=lambda s: None, on_amplitude=lambda a: None, on_transcript=lambda t: None,
        )
        import sounddevice as real_sd

        assert pipeline._resolve_sd() is real_sd
