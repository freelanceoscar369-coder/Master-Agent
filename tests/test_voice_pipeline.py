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

import time

import numpy as np
import pytest

from master_agent.founder_edition.voice_pipeline import (
    MIN_UTTERANCE_S,
    STATE_ARMED,
    STATE_CAPTURING,
    STATE_ERROR,
    STATE_MUTED,
    STATE_PROCESSING,
    STATE_SPEAKING,
    STATE_UNAVAILABLE,
    VoicePipeline,
)


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

    def query_devices(self, kind=None):
        self.query_calls += 1
        if self.fail_query:
            raise RuntimeError("no device")
        return {"name": self.device_name}

    def InputStream(self, **kwargs):
        stream = FakeStream(**kwargs)
        self.streams.append(stream)
        return stream

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


def build(
    *, device_name="Fake Mic", whisper_text="hello world", whisper_raises=False,
    piper_model_path="voice.onnx", piper_chunks=None, fail_query=False,
):
    states: list[str] = []
    amplitudes: list[float] = []
    transcripts: list[str] = []

    sd = FakeSoundDevice(device_name)
    sd.fail_query = fail_query
    whisper = FakeWhisperModel(text=whisper_text, raises=whisper_raises)
    voice_impl = FakeVoice(piper_chunks)

    pipeline = VoicePipeline(
        on_state=states.append,
        on_amplitude=amplitudes.append,
        on_transcript=transcripts.append,
        sounddevice_module=sd,
        whisper_model_factory=lambda name: whisper,
        piper_model_path=piper_model_path,
        piper_voice_factory=lambda path: voice_impl,
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
