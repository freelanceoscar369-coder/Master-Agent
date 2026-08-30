"""Nounless creation is missing Founder-owned meaning, not Planner freedom.

The adversarial holdout exposed the same class twice::

    Could you please CREATE KVH_B in the Desktop directory?
    ... create KVH_P on my Desktop, then tell me why ...

In both sentences the Founder names a thing and a place but never says what
kind of thing to create.  The generic Planner chose a file.  That is a guess
about Intent even when the Reporter later labels conformance UNKNOWN.

These tests describe the semantic class rather than either frozen sentence.
Explicit object nouns remain untouched; nounless creation asks once, preserves
the whole objective, and resumes only from a Founder-owned answer.
"""
from __future__ import annotations

import pytest

from master_agent.brain.intent import IntentLayer


@pytest.fixture
def layer() -> IntentLayer:
    return IntentLayer(vocabularies={
        "location": ("desktop", "documents", "downloads", "d_drive"),
    })


@pytest.mark.parametrize("objective", [
    "Create Budget on my Desktop.",
    "Could you please make Quarterly_Notes in the Documents directory?",
    "CREATE Launch-Plan in Desktop!",
    "Please create Archive42 on the Desktop",
])
def test_nounless_creation_asks_what_kind_of_thing(layer, objective):
    result = layer.parse(objective)

    assert result.needs_clarification
    assert result.clarification.key == "creation_kind"
    assert set(result.clarification.options) == {"folder", "file"}
    assert result.raw_input == objective


def test_folder_answer_resumes_as_the_existing_typed_folder_intent(layer):
    original = "Could you please create Budget on the Desktop?"
    pending = layer.parse(original)

    resolved = layer.clarify(original, "a folder", pending.clarification)

    assert not resolved.needs_clarification
    assert resolved.intent.capability == "create_folder"
    assert resolved.intent.payload == {"name": "Budget", "location": "desktop"}
    assert resolved.raw_input == original


def test_directory_is_a_valid_folder_answer(layer):
    original = "Make Research in Documents."
    pending = layer.parse(original)

    resolved = layer.clarify(original, "directory", pending.clarification)

    assert resolved.intent.capability == "create_folder"
    assert resolved.intent.payload == {"name": "Research", "location": "documents"}


def test_invalid_kind_is_not_passed_to_planning(layer):
    original = "Create Budget on Desktop."
    pending = layer.parse(original)

    unresolved = layer.clarify(original, "something useful", pending.clarification)

    assert unresolved.needs_clarification
    assert unresolved.clarification.key == "creation_kind"
    assert unresolved.intent is None


def test_compound_objective_is_preserved_while_kind_is_unresolved(layer):
    objective = (
        "After the failed browser mission, create Budget on my Desktop, "
        "then explain why the browser mission failed."
    )

    result = layer.parse(objective)

    assert result.needs_clarification
    assert result.raw_input == objective
    assert result.intent is None


def test_compound_folder_answer_preserves_both_requirements_for_planning(layer):
    original = (
        "After the failed browser mission, create Budget on my Desktop, "
        "then explain why the browser mission failed."
    )
    pending = layer.parse(original)

    resolved = layer.clarify(original, "folder", pending.clarification)

    assert not resolved.needs_clarification
    assert resolved.intent.capability == ""
    assert original in resolved.intent.goal
    assert "folder" in resolved.intent.goal.lower()
    assert "why the browser mission failed" in resolved.intent.goal.lower()


@pytest.mark.parametrize("explicit", [
    "Create a folder called Budget on Desktop.",
    "Create a file called Budget.txt on Desktop.",
    "Create a project called Budget.",
    "Create a report comparing the two files.",
])
def test_explicit_object_kind_does_not_get_this_clarification(layer, explicit):
    result = layer.parse(explicit)

    assert not (
        result.needs_clarification
        and result.clarification.key == "creation_kind"
    )


def test_referential_create_is_not_mistaken_for_a_named_object(layer):
    result = layer.parse("Create it on Desktop.")

    assert not (
        result.needs_clarification
        and result.clarification.key == "creation_kind"
    )
