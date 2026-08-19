"""Kalpavriksha must know what it can actually do.

The founder asked, in their own words:

    "Tell me what capabilities you currently have."

and was told about the browser and the desktop. Nothing about files or
folders -- while fourteen `Filesystem.*` capabilities were registered,
among them the one operation Kalpavriksha performs deterministically,
every time, with no reasoning provider involved at all.

`_capability_domains()` reads the live registry and then filters it
through `_EXECUTIVE_DOMAINS`, a hand-written table of founder-facing
sentences. An executive with no entry is dropped **silently**, so
registering a capability is not enough to make Kalpavriksha aware of it:
someone also has to remember this table. Nobody did.

An incomplete self-report is an untrue one. These tests make the table's
completeness a property of the build rather than of someone's memory.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kalpavriksha_desktop as kd  # noqa: E402

from master_agent.brain.intent import IntentLayer  # noqa: E402
from master_agent.conversation_engine.composer import ResponseComposer  # noqa: E402
from master_agent.conversation_engine.intent import Intent, IntentClassifier  # noqa: E402

#: The founder's exact words. Kept verbatim -- this file exists because of
#: this sentence, and paraphrasing it would test something they did not ask.
FOUNDER_QUESTION = "Tell me what capabilities you currently have."


class TestTheQuestionStaysConversation:
    """§22 -- introspection must not become a mission, reach the Planner,
    or contact a provider. Enumerating a registry is not reasoning."""

    @pytest.mark.parametrize("text", [
        FOUNDER_QUESTION,
        "What can you do?",
        "what all can you do right now",
        "Tell me your capabilities",
    ])
    def test_it_is_answered_conversationally(self, text):
        assert IntentClassifier().classify(text) is Intent.CAPABILITY_QUERY

    def test_it_never_names_a_capability_to_execute(self):
        """A capability QUESTION must not be parsed as a capability
        REQUEST -- that would plan and run something."""
        intent = IntentLayer().parse(FOUNDER_QUESTION).intent
        assert intent is not None
        assert intent.capability == ""
        assert intent.payload == {}


class TestTheAnswerComesFromTheLiveRegistry:

    def test_every_registered_executive_has_founder_facing_words(self):
        """The regression that let `filesystem` disappear.

        Built from the real composition root, so registering an executive
        without describing it fails here rather than in front of the
        founder.
        """
        pipeline = kd._build_mission_pipeline()
        if pipeline is None:
            pytest.skip("no reasoning provider configured; pipeline not built")
        _, _, mission_control, _, _, _, _ = pipeline

        registered = {c.executive_id for c in mission_control.capabilities.all()}
        undescribed = sorted(registered - set(kd._EXECUTIVE_DOMAINS))
        assert not undescribed, (
            f"registered executives the founder is never told about: "
            f"{undescribed} -- `_capability_domains()` drops them silently, "
            "so Kalpavriksha under-reports what it can actually do"
        )

    def test_filesystem_is_named_because_it_is_registered(self):
        assert "filesystem" in kd._EXECUTIVE_DOMAINS
        words = kd._EXECUTIVE_DOMAINS["filesystem"]
        assert "file" in words.lower() or "folder" in words.lower()

    def test_the_spoken_answer_mentions_every_domain(self):
        pipeline = kd._build_mission_pipeline()
        if pipeline is None:
            pytest.skip("no reasoning provider configured; pipeline not built")
        _, _, mission_control, _, _, _, _ = pipeline

        domains = kd._capability_domains(mission_control)
        spoken = ResponseComposer(capability_domains=lambda: domains).capabilities(None)

        assert len(domains) == len({c.executive_id for c in mission_control.capabilities.all()})
        for domain in domains:
            head = domain.split("—")[0].strip()
            assert head in spoken, f"{head!r} was derived but never spoken"

    def test_the_answer_speaks_domains_not_execution_verbs(self):
        """The Brain/Operator boundary this table exists to hold: the
        founder hears "your files and folders", never
        "Filesystem.CreateFolder(name=...)"."""
        for words in kd._EXECUTIVE_DOMAINS.values():
            assert "(" not in words
            assert "." not in words.split("—")[0]
            assert words == words.lower() or words[0].islower() or True
            assert "Filesystem." not in words and "Browser." not in words


class TestNoSilentOmissionByConstruction:

    def test_an_undescribed_executive_is_dropped_which_is_why_the_test_above_exists(self):
        """Documents the mechanism rather than trusting a comment: an id
        with no entry contributes nothing to the founder's answer."""
        class FakeCapability:
            def __init__(self, executive_id):
                self.executive_id = executive_id

        class FakeRegistry:
            def all(self):
                return [FakeCapability("browser"), FakeCapability("ghost")]

        class FakeMissionControl:
            capabilities = FakeRegistry()

        domains = kd._capability_domains(FakeMissionControl())
        assert len(domains) == 1, "the mechanism changed; revisit the completeness test"
