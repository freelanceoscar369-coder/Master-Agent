"""Text-to-speech, behind a Speaker interface. Default local engine: Piper.
See ARCHITECTURE.md §4.8.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class Speaker(ABC):
    @abstractmethod
    def speak(self, text: str) -> None:
        ...


class LocalPiperSpeaker(Speaker):
    def __init__(self, voice: str = "en_US-default") -> None:
        self._voice = voice

    def speak(self, text: str) -> None:
        raise NotImplementedError("Wire up Piper TTS here.")
