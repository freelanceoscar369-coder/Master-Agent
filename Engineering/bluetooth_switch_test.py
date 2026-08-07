"""C34.3 — real device-switch validation. Runs the actual VoicePipeline
device-watch mechanism (real sounddevice, real 1.5s poll) against this
machine's real hardware and logs every device change it detects, with
timestamps, to a file a separate PowerShell command can be timed
against. Model loading is skipped (fake STT/TTS factories) — this test
is about device tracking, not transcription.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from master_agent.founder_edition.voice_pipeline import VoicePipeline

LOG_PATH = os.path.join(os.path.dirname(__file__), "bluetooth_switch_test.log")
log_file = open(LOG_PATH, "w", encoding="utf-8")


def log(msg):
    line = f"{time.time():.3f} {msg}"
    print(line)
    log_file.write(line + "\n")
    log_file.flush()


def on_state(state):
    log(f"state={state} device={pipeline._current_device_name!r}")


pipeline = VoicePipeline(
    on_state=on_state,
    on_amplitude=lambda a: None,
    on_transcript=lambda t: None,
    whisper_model_factory=lambda name: object(),  # skip real model load
    piper_model_path=None,
)

log("starting pipeline (real sounddevice, real 1.5s poll)")
pipeline.start()

# Run for 30 seconds, logging every device state and change. A separate
# PowerShell command flips the real default recording device partway
# through this window.
deadline = time.time() + 30
last_device = None
while time.time() < deadline:
    if pipeline._current_device_name != last_device:
        last_device = pipeline._current_device_name
        log(f"observed device change -> {last_device!r}")
    time.sleep(0.05)

log("test window complete")
pipeline.stop()
log_file.close()
