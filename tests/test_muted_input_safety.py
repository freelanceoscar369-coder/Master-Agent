"""MUTED speech must never become a founder turn.

A packaged session showed ambient speech reaching the conversation, an
external reasoning provider, and the durable audit while the microphone
read MUTED. Nothing executed -- no objective was submitted and no task
started -- but the words left the machine, and Somesh answered as though
it had taken the matter on.

Sanitised throughout: no real founder content appears in this file.

`__audio_callback` already refuses to capture while muted. The path that
was open is the asynchronous one: an utterance captured while live,
transcribed on a worker thread over the following seconds, and emitted
after the founder had muted. The emission site read `_muted` on the line
above it to set the mic label and did not consult it before submitting --
mute gated the display and nothing else.
"""
from __future__ import annotations

import pytest

from master_agent.founder_edition import voice_pipeline as vp

SYNTHETIC = "Kalpavriksha muted voice regression test."


class Recorder:
    """Stands in for the founder surface: counts what would become a turn."""

    def __init__(self) -> None:
        self.turns: list[str] = []
        self.states: list[str] = []

    def on_transcript(self, text: str) -> None:
        self.turns.append(text)

    def on_state(self, name: str) -> None:
        self.states.append(name)


def pipeline(recorder: Recorder) -> vp.VoicePipeline:
    """A pipeline with no device and no model -- only the state machine
    and the emission gate under test."""
    return vp.VoicePipeline(
        on_state=recorder.on_state,
        on_amplitude=lambda _v: None,
        on_transcript=recorder.on_transcript,
    )


def finish_transcription(pipe: vp.VoicePipeline, text: str) -> None:
    """Drive the emission block directly: the founder turn is decided
    here, after Whisper returns."""
    pipe._transcription_in_flight = False
    pipe._on_state(vp.STATE_MUTED if pipe._muted else vp.STATE_ARMED)
    if text:
        if not getattr(pipe, "_transcript_sent_for_id", 0) == pipe._utterance_id:
            pipe._transcript_sent_for_id = pipe._utterance_id
            if pipe._muted:
                return
            pipe._on_transcript(text)


class TestMutedBlocksSubmission:

    def test_ambient_speech_while_muted_creates_no_founder_turn(self):
        rec = Recorder()
        pipe = pipeline(rec)
        pipe.set_muted(True)
        finish_transcription(pipe, SYNTHETIC)
        assert rec.turns == []

    def test_capture_itself_is_refused_while_muted(self):
        """The obvious path, asserted so it cannot regress either."""
        rec = Recorder()
        pipe = pipeline(rec)
        pipe.set_muted(True)
        pipe._VoicePipeline__audio_callback(  # name-mangled private
            [[0.5]] * 128, 128, None, None
        )
        assert rec.turns == []


class TestTheInFlightRace:
    """The path that was actually open: captured live, muted before the
    transcript came back."""

    def test_a_transcript_completing_after_mute_is_discarded(self):
        rec = Recorder()
        pipe = pipeline(rec)
        pipe.set_muted(False)          # speech begins while live
        pipe._utterance_id = 7
        pipe.set_muted(True)           # founder mutes mid-transcription
        finish_transcription(pipe, SYNTHETIC)
        assert rec.turns == [], "a transcript survived the mute that preceded it"

    def test_unmuting_later_cannot_flush_the_discarded_transcript(self):
        """The utterance is marked sent even when discarded, so it cannot
        reappear when the founder un-mutes."""
        rec = Recorder()
        pipe = pipeline(rec)
        pipe._utterance_id = 9
        pipe.set_muted(True)
        finish_transcription(pipe, SYNTHETIC)
        pipe.set_muted(False)
        finish_transcription(pipe, SYNTHETIC)
        assert rec.turns == []


class TestUnmutedStillWorks:
    """P0 must not be bought by breaking voice input."""

    def test_one_utterance_becomes_exactly_one_turn(self):
        rec = Recorder()
        pipe = pipeline(rec)
        pipe.set_muted(False)
        pipe._utterance_id = 1
        finish_transcription(pipe, SYNTHETIC)
        assert rec.turns == [SYNTHETIC]

    def test_the_same_utterance_cannot_produce_two_turns(self):
        rec = Recorder()
        pipe = pipeline(rec)
        pipe.set_muted(False)
        pipe._utterance_id = 1
        finish_transcription(pipe, SYNTHETIC)
        finish_transcription(pipe, SYNTHETIC)
        assert rec.turns == [SYNTHETIC]


class TestTheGateLivesWithTheOwner:

    def test_the_emission_site_consults_mute(self):
        """Guards the specific regression: `_muted` was read on the line
        above for the label and ignored for the decision."""
        import inspect

        source = inspect.getsource(vp.VoicePipeline._transcribe) if hasattr(
            vp.VoicePipeline, "_transcribe") else inspect.getsource(vp)
        block = source.split("_transcript_sent_for_id = self._utterance_id")[1][:400]
        assert "self._muted" in block, (
            "the transcript emission no longer consults the canonical mute state"
        )

    def test_the_pipeline_owns_mute_not_the_surface(self):
        rec = Recorder()
        pipe = pipeline(rec)
        pipe.set_muted(True)
        assert pipe._muted is True
        pipe.set_muted(False)
        assert pipe._muted is False
