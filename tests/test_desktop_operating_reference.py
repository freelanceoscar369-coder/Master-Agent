"""Stable interaction reference: retrievable, provenanced, and powerless.

Powerless is the important half. This corpus explains techniques; it
selects no provider, no browser and no application, and it loses to
whatever the live control actually reports.
"""
from __future__ import annotations

import ast
from pathlib import Path

from master_agent.app_knowledge.profile import KnowledgeType
from master_agent.desktop.operations.reference import (
    CHROMIUM,
    REFERENCES,
    UIA,
    WINDOWS,
    confirmed_references,
    explain,
    reference_for,
    references_for_layer,
)

SOURCE = Path("src/master_agent/desktop/operations/reference.py")


# ---- A/B/C: locally retrievable, no network, no lookup service ----------


def test_windows_reference_is_locally_retrievable():
    topics = {r.topic for r in references_for_layer(WINDOWS)}
    assert {"select_all", "foreground_vs_visible", "clear_before_replace"} <= topics


def test_uia_pattern_reference_is_locally_retrievable():
    topics = {r.topic for r in references_for_layer(UIA)}
    assert {"value_pattern", "text_pattern", "control_type_identity"} <= topics


def test_chromium_reference_is_locally_retrievable():
    topics = {r.topic for r in references_for_layer(CHROMIUM)}
    assert {"triple_click", "chromium_accessibility_availability"} <= topics


# ---- D/E/F: provenance discipline ---------------------------------------


def test_every_entry_carries_a_non_empty_source():
    for reference in REFERENCES:
        assert reference.fact.source.strip(), reference.topic


def test_documented_entries_name_a_first_party_source():
    for reference in REFERENCES:
        if reference.fact.knowledge_type is KnowledgeType.DOCUMENTED:
            source = reference.fact.source.lower()
            assert ("microsoft" in source or "chromium" in source
                    or "google" in source), (
                f"{reference.topic}: a DOCUMENTED fact must cite first-party "
                f"material, got {reference.fact.source!r}"
            )


def test_observed_entries_are_distinct_from_documented_ones():
    """A machine observation and a vendor convention are different claims
    and must never be merged into one."""
    observed = {r.topic for r in REFERENCES
                if r.fact.knowledge_type is KnowledgeType.OBSERVED}
    documented = {r.topic for r in REFERENCES
                  if r.fact.knowledge_type is KnowledgeType.DOCUMENTED}
    assert observed and documented
    assert not (observed & documented)


def test_unknown_and_inferred_are_never_confirmed():
    for reference in REFERENCES:
        if reference.fact.knowledge_type in (KnowledgeType.UNKNOWN,
                                             KnowledgeType.INFERRED):
            assert reference.is_confirmed is False, reference.topic
    assert all(r.is_confirmed for r in confirmed_references())


# ---- G/H/I/J: the substance ---------------------------------------------


def test_triple_click_is_recorded_as_context_dependent_not_select_all():
    reference = reference_for("triple_click")
    assert reference is not None
    applicability = reference.applicability.lower()
    assert "context dependent" in applicability
    assert "not a universal select-all" in applicability
    # Untested here, so it must not read as confirmed technique.
    assert reference.is_confirmed is False


def test_select_all_is_recorded_with_applicability_not_as_a_universal_repair():
    reference = reference_for("select_all")
    assert reference is not None
    assert "not a universal repair" in reference.applicability.lower()
    assert reference.verification.strip()


def test_semantic_value_replacement_is_the_recorded_preferred_mechanism():
    """The lesson from the rename must be the right one.

    The defect was wrong-control identity. Semantic replacement was
    correct all along, and no gesture was needed.
    """
    value = reference_for("value_pattern")
    identity = reference_for("control_type_identity")
    assert value.is_confirmed and identity.is_confirmed
    assert "no gesture was required" in value.fact.value.lower()
    assert "50004" in str(identity.fact.value)


def test_live_reality_outranks_stored_reference():
    """Stated in the module itself, because a corpus that quietly claims
    authority over the live UI is worse than no corpus."""
    text = SOURCE.read_text(encoding="utf-8").lower()
    assert "outranked by whatever the live control actually reports" in text


# ---- K/L/M: it decides nothing ------------------------------------------


def test_reference_knowledge_can_never_select_a_provider_or_a_browser():
    """No provider id, no browser name, no selection verb anywhere in it."""
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            for forbidden in ("select", "rank", "choose", "prefer", "fallback"):
                assert forbidden not in node.name.lower(), node.name

    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef
                      | ast.AsyncFunctionDef):
            body = getattr(node, "body", None) or []
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                docstrings.add(id(body[0].value))
    literals = [n.value for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)
                and id(n) not in docstrings]

    for banned in ("chrome", "comet", "gemini", "chatgpt", "trusted-founder-web",
                   "browser.free-ai"):
        offenders = [t for t in literals if banned in t.lower()]
        assert not offenders, f"reference data names {banned}: {offenders[:2]}"


def test_no_duplicate_application_profile_was_created_for_the_browsers():
    from master_agent.app_knowledge.catalog import APP_KNOWLEDGE_CATALOG
    from master_agent.desktop.operations.knowledge import PROFILES

    operations = {p.key for p in PROFILES}
    assert {"chrome", "comet"} <= operations
    assert "chrome" not in APP_KNOWLEDGE_CATALOG
    assert "comet" not in APP_KNOWLEDGE_CATALOG


def test_a_technique_can_explain_itself_without_a_model():
    explanation = explain("control_type_identity")
    assert "control type" in explanation.lower()
    assert "observed" in explanation.lower()
    assert explain("nothing_recorded_here").startswith("no reference knowledge")


def test_the_generic_multi_click_primitive_exists_and_is_not_a_named_gesture():
    from master_agent.desktop.execution.mouse import MouseController

    assert hasattr(MouseController, "multi_click")
    assert not hasattr(MouseController, "triple_click"), (
        "the gesture is generic; a named triple_click invites treating it as "
        "select-all"
    )
    refused = MouseController().multi_click(1, 1, 0)
    assert refused.success is False
