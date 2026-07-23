"""Speech-to-text, behind a Transcriber interface so the default local
engine (faster-whisper) can be swapped for a cloud STT later without the
Intent Layer noticing. See ARCHITECTURE.md §4.8.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class Transcriber(ABC):
    @abstractmethod
    def transcribe(self, audio_bytes: bytes) -> str:
        ...


class LocalWhisperTranscriber(Transcriber):
    """Default: faster-whisper running locally. Stubbed until the voice
    dependency group is installed and a model size is chosen for the
    founder's hardware.
    """

    def __init__(self, model_size: str = "base") -> None:
        self._model_size = model_size

    def transcribe(self, audio_bytes: bytes) -> str:
        raise NotImplementedError("Wire up faster-whisper here.")
