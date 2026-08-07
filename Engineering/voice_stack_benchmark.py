"""C34.2 — real performance measurements for the voice stack, against
the actual production code paths (real faster-whisper, real Piper, real
sounddevice), not fakes. Run standalone on the dev machine:

    python Engineering/voice_stack_benchmark.py

Writes nothing to the app itself; this is a throwaway measurement tool,
not a shipped module. Output is captured verbatim into HEALTH_C34_2.md.
No microphone is used — a WAV is synthesised via Piper and fed straight
to Whisper in memory, so this runs unattended without a live founder
speaking into it. TTS playback IS real audio through the default output
device (briefly, on purpose — it's the thing being measured).
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import psutil
import sounddevice as sd

ROOT = os.path.join(os.path.dirname(__file__), "..")
WHISPER_DIR = os.path.join(ROOT, "desktop_app", "voice_models", "whisper-base.en")
PIPER_PATH = os.path.join(ROOT, "desktop_app", "voice_models", "en_US-lessac-medium.onnx")

results: dict = {}
proc = psutil.Process()


def measure(label):
    class _Timer:
        def __enter__(self):
            self.t0 = time.perf_counter()
            return self

        def __exit__(self, *exc):
            results[label] = round((time.perf_counter() - self.t0) * 1000, 1)

    return _Timer()


def mem_mb():
    return round(proc.memory_info().rss / (1024 * 1024), 1)


print("=== C34.2 voice stack benchmark ===")
results["ram_at_start_mb"] = mem_mb()

# ---- 1. device discovery -------------------------------------------------
with measure("input_device_query_ms"):
    input_device = sd.query_devices(kind="input")
with measure("output_device_query_ms"):
    output_device = sd.query_devices(kind="output")
print(f"Input device:  {input_device.get('name')}")
print(f"Output device: {output_device.get('name')}")

# ---- 2. permission check --------------------------------------------------
sys.path.insert(0, ROOT)
import kalpavriksha_desktop as kd  # noqa: E402

with measure("permission_check_ms"):
    allowed = kd._windows_microphone_allowed()
print(f"Microphone permission allowed: {allowed}")

# ---- 3. model loads ---------------------------------------------------------
from faster_whisper import WhisperModel  # noqa: E402
from piper import PiperVoice  # noqa: E402

with measure("whisper_load_ms"):
    whisper_model = WhisperModel(WHISPER_DIR, device="cpu", compute_type="int8")
results["ram_after_whisper_mb"] = mem_mb()

with measure("piper_load_ms"):
    piper_voice = PiperVoice.load(PIPER_PATH)
results["ram_after_piper_mb"] = mem_mb()

# ---- 4. TTS synthesis + real playback latency -----------------------------
TEST_PHRASE = "Good evening. I am here, and I am listening."

with measure("tts_synthesis_first_chunk_ms"):
    chunk_iter = piper_voice.synthesize(TEST_PHRASE)
    first_chunk = next(chunk_iter)

chunks = [first_chunk]
t_synth_start = time.perf_counter()
for c in chunk_iter:
    chunks.append(c)
results["tts_synthesis_remaining_chunks_ms"] = round((time.perf_counter() - t_synth_start) * 1000, 1)

total_audio_samples = sum(len(c.audio_float_array) for c in chunks)
total_audio_s = total_audio_samples / chunks[0].sample_rate
results["tts_audio_duration_ms"] = round(total_audio_s * 1000, 1)

print(f"Playing synthesised phrase ({total_audio_s:.2f}s of audio) through the real output device...")
t_play_start = time.perf_counter()
for c in chunks:
    sd.play(c.audio_float_array, samplerate=c.sample_rate, blocking=True)
results["tts_playback_wall_ms"] = round((time.perf_counter() - t_play_start) * 1000, 1)

# ---- 5. interrupt latency ---------------------------------------------------
# A longer phrase, interrupted from a second thread partway through —
# measures real time from sd.stop() call to the blocked sd.play() call
# actually returning.
LONG_PHRASE = (
    "This is a longer sentence, spoken so there is enough audio in flight "
    "for an interruption to land clearly in the middle of it, rather than "
    "after it has already finished playing."
)
long_chunks = list(piper_voice.synthesize(LONG_PHRASE))
print(f"Measuring interrupt latency mid-playback of a {len(long_chunks)}-chunk reply...")

interrupt_fired_at = {}
play_returned_at = {}


def interrupt_after_delay():
    time.sleep(0.4)  # let real playback get underway
    interrupt_fired_at["t"] = time.perf_counter()
    sd.stop()


t = threading.Thread(target=interrupt_after_delay)
t.start()
t_play2_start = time.perf_counter()
try:
    for c in long_chunks:
        sd.play(c.audio_float_array, samplerate=c.sample_rate, blocking=True)
        if "t" in interrupt_fired_at:
            play_returned_at["t"] = time.perf_counter()
            break
finally:
    t.join()

if "t" in play_returned_at:
    results["interrupt_latency_ms"] = round((play_returned_at["t"] - interrupt_fired_at["t"]) * 1000, 1)
else:
    results["interrupt_latency_ms"] = None  # playback finished before the interrupt fired

# ---- 6. STT latency (no live mic — Piper's own output fed to Whisper) -----
stt_chunks = list(piper_voice.synthesize("Hi Somesh, can you hear me clearly?"))
stt_audio = np.concatenate([c.audio_float_array for c in stt_chunks]).astype("float32")
# Whisper wants 16kHz; Piper's voice model here is 22050Hz — resample by
# simple linear interpolation, adequate for a latency measurement (not
# a transcription-accuracy test).
src_rate = stt_chunks[0].sample_rate
dst_rate = 16000
duration_s = len(stt_audio) / src_rate
dst_len = int(duration_s * dst_rate)
stt_audio_16k = np.interp(
    np.linspace(0, len(stt_audio), dst_len, endpoint=False),
    np.arange(len(stt_audio)), stt_audio,
).astype("float32")

with measure("stt_transcription_ms"):
    segments, _info = whisper_model.transcribe(stt_audio_16k, language="en")
    transcript = "".join(s.text for s in segments).strip()
results["stt_input_audio_duration_ms"] = round(duration_s * 1000, 1)
print(f"Whisper heard (via Piper's own voice, resampled): {transcript!r}")

# ---- 7. device reopen mechanics --------------------------------------------
captured = {"n": 0}


def _cb(indata, frames, time_info, status):
    captured["n"] += 1


with measure("input_stream_open_ms"):
    stream = sd.InputStream(samplerate=16000, channels=1, dtype="float32", blocksize=480, callback=_cb)
    stream.start()
time.sleep(0.2)  # let a few real callbacks land
frames_during_200ms = captured["n"]
with measure("input_stream_close_ms"):
    stream.stop()
    stream.close()
results["input_callback_frames_in_200ms"] = frames_during_200ms

# ---- 8. CPU ------------------------------------------------------------------
proc.cpu_percent(interval=None)  # prime the counter
time.sleep(1.0)
results["cpu_percent_idle_1s_sample"] = proc.cpu_percent(interval=None)
results["ram_final_mb"] = mem_mb()

print()
print("=== RESULTS (JSON) ===")
print(json.dumps(results, indent=2))
