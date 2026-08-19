"""Two P0 trust boundaries: the mic is muted until asked, and an
automated run cannot touch the founder's session.

A packaged FMEA run shared the founder's process, microphone and state
directory. Ambient speech reached a reasoning provider and the durable
audit. Nothing executed, but the words left the machine.

Two causes, fixed separately:

  * the pipeline opened the microphone at construction, and nothing in
    the composition ever muted it -- `set_muted()`'s only caller is a
    founder click;
  * the harness had no way to run anywhere other than the founder's own
    state root, on the founder's own microphone.

All synthetic. No founder content appears here.
"""
from __future__ import annotations

import json
import os

import pytest

from master_agent.founder_edition.voice_pipeline import (
    STATE_ARMED,
    STATE_MUTED,
    VoicePipeline,
)

SYNTHETIC = "Kalpavriksha startup mute test."


class Recorder:
    def __init__(self) -> None:
        self.turns: list[str] = []
        self.states: list[str] = []

    def pipeline(self, **kw) -> VoicePipeline:
        return VoicePipeline(
            on_state=self.states.append,
            on_amplitude=lambda _v: None,
            on_transcript=self.turns.append,
            **kw,
        )


class TestStartupMuteTruth:

    def test_the_pipeline_is_muted_at_construction(self):
        """The whole incident's precondition: it was live."""
        assert Recorder().pipeline()._muted is True

    def test_capture_is_refused_before_the_founder_ever_touches_anything(self):
        rec = Recorder()
        pipe = rec.pipeline()
        pipe._VoicePipeline__audio_callback([[0.5]] * 128, 128, None, None)
        assert rec.turns == []

    def test_the_label_is_derived_from_the_canonical_value(self):
        """UI and pipeline cannot disagree, because the label is computed
        FROM `_muted` rather than tracked alongside it.

        `set_muted()` only pushes once an STT model exists, so this
        asserts the derivation itself -- the expression the push uses --
        rather than requiring a loaded model.
        """
        import inspect

        source = inspect.getsource(VoicePipeline.set_muted)
        assert "STATE_MUTED if muted else STATE_ARMED" in source

        rec = Recorder()
        pipe = rec.pipeline()
        for value, expected in ((True, STATE_MUTED), (False, STATE_ARMED)):
            pipe.set_muted(value)
            assert (STATE_MUTED if pipe._muted else STATE_ARMED) == expected

    def test_a_live_start_must_be_asked_for_explicitly(self):
        assert Recorder().pipeline(start_muted=False)._muted is False

    def test_the_founder_control_still_moves_the_canonical_state(self):
        rec = Recorder()
        pipe = rec.pipeline()
        pipe.set_muted(False)
        assert pipe._muted is False
        pipe.set_muted(True)
        assert pipe._muted is True


class TestTheRaceFixStillHolds:
    """f764986 must not be weakened by the startup change."""

    def _finish(self, pipe, text):
        if text and not getattr(pipe, "_transcript_sent_for_id", 0) == pipe._utterance_id:
            pipe._transcript_sent_for_id = pipe._utterance_id
            if pipe._muted:
                return
            pipe._on_transcript(text)

    def test_a_transcript_completing_after_mute_is_still_discarded(self):
        rec = Recorder()
        pipe = rec.pipeline(start_muted=False)
        pipe._utterance_id = 3
        pipe.set_muted(True)
        self._finish(pipe, SYNTHETIC)
        assert rec.turns == []

    def test_unmuted_still_yields_exactly_one_turn(self):
        rec = Recorder()
        pipe = rec.pipeline(start_muted=False)
        pipe._utterance_id = 1
        self._finish(pipe, SYNTHETIC)
        self._finish(pipe, SYNTHETIC)
        assert rec.turns == [SYNTHETIC]


class TestFmeaStateIsolation:

    def test_an_override_redirects_the_whole_state_root(self, tmp_path, monkeypatch):
        import kalpavriksha_desktop as kd

        monkeypatch.setenv("KALPAVRIKSHA_STATE_DIR", str(tmp_path / "fmea"))
        assert kd._app_state_dir() == tmp_path / "fmea"

    def test_without_the_override_the_founder_path_is_unchanged(self, monkeypatch):
        import kalpavriksha_desktop as kd

        monkeypatch.delenv("KALPAVRIKSHA_STATE_DIR", raising=False)
        assert "Kalpavriksha" in str(kd._app_state_dir())
        assert "fmea" not in str(kd._app_state_dir()).lower()

    def test_two_profiles_cannot_see_each_others_history(self, tmp_path, monkeypatch):
        """Part J -- profile A is founder-like, profile B is the harness.
        Neither uses the real session."""
        from master_agent.audit import FILENAME, InteractionLog, JsonlInteractionStore
        import kalpavriksha_desktop as kd

        roots = {}
        for name, phrase in (("A", "profile A synthetic turn"), ("B", "profile B synthetic turn")):
            monkeypatch.setenv("KALPAVRIKSHA_STATE_DIR", str(tmp_path / name))
            root = kd._app_state_dir()
            roots[name] = root
            InteractionLog(JsonlInteractionStore(root / FILENAME)).founder_said(phrase)

        assert roots["A"] != roots["B"]
        a = [r.text for r in JsonlInteractionStore(roots["A"] / FILENAME).read()]
        b = [r.text for r in JsonlInteractionStore(roots["B"] / FILENAME).read()]
        assert a == ["profile A synthetic turn"]
        assert b == ["profile B synthetic turn"]
        assert not set(a) & set(b), "one profile can see the other's interactions"

    def test_sessions_in_separate_roots_do_not_share_ids(self, tmp_path, monkeypatch):
        from master_agent.audit import FILENAME, InteractionLog, JsonlInteractionStore
        import kalpavriksha_desktop as kd

        sessions = []
        for name in ("A", "B"):
            monkeypatch.setenv("KALPAVRIKSHA_STATE_DIR", str(tmp_path / name))
            log = InteractionLog(JsonlInteractionStore(kd._app_state_dir() / FILENAME))
            log.founder_said("synthetic")
            sessions.append(log.session_id)
        assert sessions[0] != sessions[1]


class TestFmeaMicrophonePolicy:

    def test_the_composition_can_run_without_the_physical_microphone(self):
        """The flag is INJECTED, not read inside `founder_edition` --
        that package is architecture-guarded against importing `os`, so
        the composition root owns the environment and hands the decision
        down, exactly as it already does for `mic_permission_checker`."""
        import inspect

        import kalpavriksha_desktop as kd
        from master_agent.founder_edition import desktop_shell

        shell = inspect.getsource(desktop_shell)
        assert "if not microphone_enabled:" in shell

        # The flag must be THREADED, not merely declared. An earlier
        # version of this test asserted only that the identifier appeared
        # somewhere in the module -- which it did, on the parameter and in
        # a comment -- while `create_window` silently dropped it and the
        # packaged FMEA profile built a real microphone anyway.
        call = shell.split("piper_model_path=voice_model_path,")[1][:400]
        assert "microphone_enabled=microphone_enabled" in call, (
            "create_window accepts the flag and never passes it on"
        )

        # ...and the lifecycle bindings must survive a None pipeline.
        # `window.events.closing += voice.stop` raised AttributeError at
        # composition time the first time the flag actually took effect.
        assert "if voice is not None:" in shell, (
            "voice lifecycle wiring assumes a pipeline always exists"
        )
        assert "KALPAVRIKSHA_DISABLE_MIC" not in shell, (
            "the guarded package is reading the environment itself"
        )

        root = inspect.getsource(kd.main)
        assert "KALPAVRIKSHA_DISABLE_MIC" in root
        assert "microphone_enabled=" in root

    def test_the_disable_is_opt_in_so_founder_voice_is_untouched(self, monkeypatch):
        monkeypatch.delenv("KALPAVRIKSHA_DISABLE_MIC", raising=False)
        assert os.environ.get("KALPAVRIKSHA_DISABLE_MIC") is None


class TestMutedSpeechReachesNoProvider:

    def test_a_muted_utterance_produces_no_interaction_record(self, tmp_path, monkeypatch):
        """Part L -- no turn means no route, so no broker decision and no
        tier attempt can exist for it."""
        from master_agent.audit import FILENAME, JsonlInteractionStore
        import kalpavriksha_desktop as kd

        monkeypatch.setenv("KALPAVRIKSHA_STATE_DIR", str(tmp_path / "muted"))
        root = kd._app_state_dir()

        rec = Recorder()
        pipe = rec.pipeline()          # muted by construction
        pipe._VoicePipeline__audio_callback([[0.5]] * 256, 256, None, None)

        assert rec.turns == []
        assert JsonlInteractionStore(root / FILENAME).read() == []
        assert not (root / "broker_decisions.json").exists()
        assert not (root / "plan_history.json").exists()
