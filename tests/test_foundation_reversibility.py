"""Sprint 1, Component 12 — Reversibility Registry.

VEDA 04 A2: *"A declared classification for every action type in the
system… Unclassified action types are non-executable by default — the
registry fails closed."*

**Invariant:** *"'probably reversible' cannot be represented."* The
construction tests below make that literally true: a reversible
classification that cannot name how it is undone does not exist.

Every test uses fixed instants. Nothing here reads a wall clock.
"""
from __future__ import annotations

import ast
import json
from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from master_agent.foundation import (
    ReversibilityRegistry as ExportedRegistry,
)
from master_agent.foundation.attestation import (
    AttestationQuestion,
    AttestationVerdict,
)
from master_agent.foundation.reversibility import (
    Classification,
    InvalidClassification,
    ReversibilityRegistry,
    Unclassified,
)
from master_agent.foundation.warrant import ReversibilityClass

ATTESTED = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
WINDOW = timedelta(minutes=60)

READ = Classification(
    capability="Filesystem.ReadFile",
    cls=ReversibilityClass.READ_ONLY,
)
REVERSIBLE = Classification(
    capability="Filesystem.CreateFolder",
    cls=ReversibilityClass.REVERSIBLE,
    compensating_capability="Filesystem.DeleteFolder",
)
TIMED = Classification(
    capability="Email.Send",
    cls=ReversibilityClass.REVERSIBLE_UNTIL,
    compensating_capability="Email.Recall",
    undo_window=WINDOW,
)
IRREVERSIBLE = Classification(
    capability="Payment.Transfer",
    cls=ReversibilityClass.IRREVERSIBLE,
)

ALL_FOUR = (READ, REVERSIBLE, TIMED, IRREVERSIBLE)


# ======================================================================
# Classification — the four classes
# ======================================================================


def test_every_shipped_class_can_be_classified() -> None:
    """C4's vocabulary is reused, not restated. All four must be usable."""
    assert {c.cls for c in ALL_FOUR} == set(ReversibilityClass)


def test_a_read_only_classification_needs_nothing_to_undo() -> None:
    assert READ.compensating_capability is None
    assert READ.undo_window is None


def test_a_reversible_classification_names_its_compensating_capability() -> None:
    assert REVERSIBLE.compensating_capability == "Filesystem.DeleteFolder"


def test_a_timed_classification_names_both() -> None:
    assert TIMED.compensating_capability == "Email.Recall"
    assert TIMED.undo_window == WINDOW


def test_an_irreversible_classification_reports_itself() -> None:
    assert IRREVERSIBLE.is_irreversible
    assert not REVERSIBLE.is_irreversible


# ======================================================================
# "probably reversible" cannot be represented
# ======================================================================


@pytest.mark.parametrize(
    "cls", [ReversibilityClass.REVERSIBLE, ReversibilityClass.REVERSIBLE_UNTIL]
)
def test_a_compensated_class_without_a_compensating_capability_is_refused(cls) -> None:
    """VEDA 04 A2's invariant, enforced structurally."""
    with pytest.raises(InvalidClassification, match="probably reversible"):
        Classification(capability="X.Y", cls=cls, undo_window=WINDOW)


@pytest.mark.parametrize("blank", ["", "   ", "\n"])
def test_a_blank_compensating_capability_is_refused(blank) -> None:
    with pytest.raises(InvalidClassification, match="probably reversible"):
        Classification(
            capability="X.Y",
            cls=ReversibilityClass.REVERSIBLE,
            compensating_capability=blank,
        )


@pytest.mark.parametrize(
    "cls", [ReversibilityClass.READ_ONLY, ReversibilityClass.IRREVERSIBLE]
)
def test_an_uncompensated_class_may_not_name_one(cls) -> None:
    """§8.4 — an irreversible action has no undo. Naming one would be a
    promise nothing can keep."""
    with pytest.raises(InvalidClassification, match="no compensating"):
        Classification(
            capability="X.Y", cls=cls, compensating_capability="X.Undo"
        )


def test_reversible_until_requires_a_window() -> None:
    """Without one it is indistinguishable from `reversible`."""
    with pytest.raises(InvalidClassification, match="window"):
        Classification(
            capability="Email.Send",
            cls=ReversibilityClass.REVERSIBLE_UNTIL,
            compensating_capability="Email.Recall",
        )


@pytest.mark.parametrize("bad", [timedelta(0), timedelta(seconds=-1)])
def test_a_non_positive_window_is_refused(bad) -> None:
    """A window of zero is an irreversible action wearing a reversible
    name."""
    with pytest.raises(InvalidClassification, match="positive"):
        Classification(
            capability="Email.Send",
            cls=ReversibilityClass.REVERSIBLE_UNTIL,
            compensating_capability="Email.Recall",
            undo_window=bad,
        )


@pytest.mark.parametrize(
    "cls",
    [
        ReversibilityClass.READ_ONLY,
        ReversibilityClass.REVERSIBLE,
        ReversibilityClass.IRREVERSIBLE,
    ],
)
def test_only_reversible_until_may_carry_a_window(cls) -> None:
    """Kernel Specification §4.3 — *"Present only for `reversible_until`."*"""
    compensating = (
        "X.Undo" if cls is ReversibilityClass.REVERSIBLE else None
    )
    with pytest.raises(InvalidClassification, match="reversible_until"):
        Classification(
            capability="X.Y",
            cls=cls,
            compensating_capability=compensating,
            undo_window=WINDOW,
        )


@pytest.mark.parametrize("bad", ["", "   ", None, 42])
def test_the_capability_name_is_required(bad) -> None:
    with pytest.raises(InvalidClassification, match="capability"):
        Classification(capability=bad, cls=ReversibilityClass.READ_ONLY)


def test_the_class_must_be_a_reversibility_class() -> None:
    with pytest.raises(InvalidClassification, match="ReversibilityClass"):
        Classification(capability="X.Y", cls="reversible")


def test_a_non_timedelta_window_is_refused() -> None:
    with pytest.raises(InvalidClassification, match="window"):
        Classification(
            capability="Email.Send",
            cls=ReversibilityClass.REVERSIBLE_UNTIL,
            compensating_capability="Email.Recall",
            undo_window=3600,
        )


# ======================================================================
# Classification value semantics
# ======================================================================


@pytest.mark.parametrize(
    "field", ["capability", "cls", "compensating_capability", "undo_window"]
)
def test_a_classification_cannot_be_mutated(field) -> None:
    with pytest.raises(FrozenInstanceError):
        setattr(READ, field, None)


def test_classification_equality_is_deterministic() -> None:
    assert READ == Classification(
        capability="Filesystem.ReadFile", cls=ReversibilityClass.READ_ONLY
    )


def test_a_classification_is_hashable() -> None:
    assert len({READ, READ}) == 1


def test_classification_serialisation_is_deterministic() -> None:
    assert TIMED.as_dict() == TIMED.as_dict()


def test_classification_serialisation_is_json_ready() -> None:
    assert json.loads(json.dumps(TIMED.as_dict()))


def test_classification_serialisation_carries_every_field() -> None:
    assert TIMED.as_dict() == {
        "capability": "Email.Send",
        "cls": "reversible_until",
        "compensating_capability": "Email.Recall",
        "undo_window_seconds": 3600,
    }


def test_serialisation_of_an_unwindowed_class() -> None:
    assert READ.as_dict()["undo_window_seconds"] is None


# ======================================================================
# The registry — fails closed
# ======================================================================


def test_an_empty_registry_classifies_nothing() -> None:
    """The correct starting state, not a defect: every capability is
    non-executable until declared."""
    registry = ReversibilityRegistry()
    assert len(registry) == 0
    assert registry.capabilities == ()


def test_an_unclassified_capability_raises() -> None:
    """VEDA 04 A2 — *"Unclassified action types are non-executable by
    default."*"""
    with pytest.raises(Unclassified, match="no reversibility classification"):
        ReversibilityRegistry().classify("Filesystem.DeleteFolder")


def test_the_raise_names_the_capability() -> None:
    with pytest.raises(Unclassified) as caught:
        ReversibilityRegistry().classify("Payment.Transfer")
    assert caught.value.capability == "Payment.Transfer"


def test_there_is_no_default_classification() -> None:
    """A method that returned a default would put the decision in the
    caller's hands, and some caller would read it as permission."""
    registry = ReversibilityRegistry()
    for capability in ("A.B", "C.D", "Filesystem.DeleteFolder"):
        assert not registry.is_classified(capability)
        with pytest.raises(Unclassified):
            registry.classify(capability)


def test_classify_returns_the_declared_classification() -> None:
    registry = ReversibilityRegistry(ALL_FOUR)
    assert registry.classify("Email.Send") is TIMED


def test_is_classified_answers_without_raising() -> None:
    registry = ReversibilityRegistry((READ,))
    assert registry.is_classified("Filesystem.ReadFile")
    assert not registry.is_classified("Filesystem.DeleteFolder")


def test_membership_reads_naturally() -> None:
    registry = ReversibilityRegistry((READ,))
    assert "Filesystem.ReadFile" in registry
    assert "Payment.Transfer" not in registry


def test_every_registered_capability_is_classified() -> None:
    """The roadmap's required coverage test: nothing can be registered
    without a classification, so the registry cannot hold a gap."""
    registry = ReversibilityRegistry(ALL_FOUR)
    assert len(registry) == len(ALL_FOUR)
    for capability in registry.capabilities:
        assert registry.is_classified(capability)
        assert isinstance(registry.classify(capability), Classification)


# ======================================================================
# The registry is immutable
# ======================================================================


def test_register_returns_a_new_registry() -> None:
    original = ReversibilityRegistry()
    extended = original.register(READ)
    assert extended is not original


def test_register_leaves_the_original_untouched() -> None:
    """§8.3 — a reversibility class changing requires a new Intent, not a
    silent substitution."""
    original = ReversibilityRegistry()
    original.register(READ)
    assert len(original) == 0
    assert not original.is_classified("Filesystem.ReadFile")


def test_registering_accumulates() -> None:
    registry = ReversibilityRegistry()
    for item in ALL_FOUR:
        registry = registry.register(item)
    assert len(registry) == 4
    assert set(registry.capabilities) == {c.capability for c in ALL_FOUR}


def test_a_capability_may_not_be_classified_twice() -> None:
    """Overwriting is how a reversible action becomes irreversible with
    nobody noticing."""
    registry = ReversibilityRegistry((REVERSIBLE,))
    replacement = Classification(
        capability="Filesystem.CreateFolder",
        cls=ReversibilityClass.IRREVERSIBLE,
    )
    with pytest.raises(InvalidClassification, match="already classified"):
        registry.register(replacement)


def test_re_registering_an_identical_classification_is_also_refused() -> None:
    registry = ReversibilityRegistry((READ,))
    with pytest.raises(InvalidClassification, match="already classified"):
        registry.register(READ)


def test_construction_refuses_a_duplicate_capability() -> None:
    duplicate = Classification(
        capability="Filesystem.ReadFile", cls=ReversibilityClass.IRREVERSIBLE
    )
    with pytest.raises(InvalidClassification, match="classified twice"):
        ReversibilityRegistry((READ, duplicate))


def test_construction_refuses_a_non_classification() -> None:
    with pytest.raises(InvalidClassification, match="Classification"):
        ReversibilityRegistry(("Filesystem.ReadFile",))


def test_register_refuses_a_non_classification() -> None:
    with pytest.raises(InvalidClassification, match="Classification"):
        ReversibilityRegistry().register("Filesystem.ReadFile")


def test_the_registry_exposes_no_mutator() -> None:
    """`PrincipalRegistry` (C2) precedent: entries at construction, no
    mutator."""
    surface = [n for n in dir(ReversibilityRegistry) if not n.startswith("_")]
    assert not any(
        w in n.lower()
        for n in surface
        for w in ("add", "remove", "delete", "clear", "pop", "update", "set")
    )


def test_the_registry_has_no_instance_dict() -> None:
    """`__slots__` — a caller cannot bolt state onto a registry."""
    with pytest.raises(AttributeError):
        ReversibilityRegistry().anything = 1


# ======================================================================
# attest — the A2 attestation (Amendment 001 M7)
# ======================================================================


def test_a_classified_capability_is_attested_satisfied() -> None:
    registry = ReversibilityRegistry((REVERSIBLE,))
    a = registry.attest("Filesystem.CreateFolder", "req-1", ATTESTED)
    assert a.question is AttestationQuestion.REVERSIBILITY
    assert a.verdict is AttestationVerdict.SATISFIED
    assert a.subject == "req-1"
    assert a.attested_at == ATTESTED


def test_the_attestor_is_the_registry_c7_assigns() -> None:
    """§7.3 assigns A2 to the Reversibility Registry, one to one."""
    a = ReversibilityRegistry((READ,)).attest("Filesystem.ReadFile", "s", ATTESTED)
    assert a.attestor == AttestationQuestion.REVERSIBILITY.canonical_attestor
    assert a.attestor == "reversibility_registry"


def test_an_unclassified_capability_is_attested_refused() -> None:
    """§7.5 requires refusals to be recorded, so this refuses rather than
    raising."""
    a = ReversibilityRegistry().attest("Payment.Transfer", "req-9", ATTESTED)
    assert a.verdict is AttestationVerdict.REFUSED
    assert "no reversibility classification" in a.reason


def test_the_refusal_names_the_registry_failing_closed() -> None:
    a = ReversibilityRegistry().attest("X.Y", "s", ATTESTED)
    assert "fails closed" in a.reason


def test_a_satisfied_attestation_carries_no_reason() -> None:
    """C7's symmetry, inherited."""
    a = ReversibilityRegistry((READ,)).attest("Filesystem.ReadFile", "s", ATTESTED)
    assert a.reason is None


def test_attest_never_reads_a_clock() -> None:
    """The moment is supplied, exactly as C7, C9 and C10 do."""
    earlier = datetime(2020, 1, 1, tzinfo=UTC)
    a = ReversibilityRegistry((READ,)).attest("Filesystem.ReadFile", "s", earlier)
    assert a.attested_at == earlier


@pytest.mark.parametrize("item", ALL_FOUR)
def test_every_class_can_be_attested(item) -> None:
    a = ReversibilityRegistry((item,)).attest(item.capability, "s", ATTESTED)
    assert a.verdict is AttestationVerdict.SATISFIED


def test_attesting_does_not_classify() -> None:
    """Asking the question must not answer it."""
    registry = ReversibilityRegistry()
    registry.attest("Payment.Transfer", "s", ATTESTED)
    assert not registry.is_classified("Payment.Transfer")


# ======================================================================
# CONSTITUTIONAL
# ======================================================================

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE = REPO_ROOT / "src" / "master_agent" / "foundation" / "reversibility.py"

FORBIDDEN_VERBS = (
    "execute", "run", "invoke", "perform", "dispatch",
    "authorize", "authorise", "grant", "permit", "approve", "deny",
    "mint", "issue", "settle", "revoke", "start", "stop",
)


def _module_imports() -> list[str]:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    return imported


def test_it_depends_only_on_components_four_and_seven() -> None:
    """Roadmap §2 C12: C4 `ReversibilityClass`, C7 Attestation."""
    internal = {n for n in _module_imports() if n.startswith("master_agent")}
    assert internal == {
        "master_agent.foundation.attestation",
        "master_agent.foundation.warrant",
    }


def test_it_has_no_dependency_on_the_clock() -> None:
    assert not any("clock" in n for n in _module_imports())


def test_it_imports_nothing_that_could_act() -> None:
    forbidden = (
        "master_agent.executor",
        "master_agent.orchestrator",
        "master_agent.permissions",
        "master_agent.runtime",
        "master_agent.plugins",
        "master_agent.broker",
        "master_agent.mission_control",
        "master_agent.persistence",
        "master_agent.verification",
        "subprocess",
        "socket",
    )
    offenders = [
        n for n in _module_imports() if any(n.startswith(f) for f in forbidden)
    ]
    assert not offenders, f"reversibility.py imports {offenders}"


def test_it_cannot_execute_or_authorize_work() -> None:
    """It says what an action does to the world. It does none of it, and it
    decides nothing about permission."""
    surface = [
        n
        for n in dir(ReversibilityRegistry) + dir(Classification)
        if not n.startswith("_")
    ]
    offenders = [
        n for n in surface if any(v in n.lower() for v in FORBIDDEN_VERBS)
    ]
    assert not offenders, f"C12 exposes {offenders}"


def test_it_decides_nothing_about_permission() -> None:
    """§3.4 assigns permission to the Permission System (A3). A registry
    field about tiers or approval would be a second opinion."""
    names = {f.name for f in fields(Classification)}
    assert not any(
        w in n.lower()
        for n in names
        for w in ("permission", "grant", "tier", "risk", "approval")
    )


def test_it_holds_no_callable() -> None:
    """The registry knows *what* undoes an action, never *how* to run it.
    A callable here would put execution in `foundation/`."""
    for item in ALL_FOUR:
        for f in fields(Classification):
            assert not callable(getattr(item, f.name))


def test_it_reads_no_ambient_time() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    banned = {"datetime.now", "datetime.utcnow", "datetime.today", "time.time"}
    calls = [
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ".".join(ast.unparse(node.func).split(".")[-2:]) in banned
    ]
    assert not calls, f"reversibility.py reads ambient time: {calls}"


def test_it_does_not_restate_the_reversibility_vocabulary() -> None:
    """C4 owns it. A second enum would be two orderings of reversibility."""
    source = MODULE.read_text(encoding="utf-8")
    assert "class ReversibilityClass" not in source


def test_unclassified_is_not_silently_catchable_as_a_value_error() -> None:
    """It is a `LookupError`. A caller writing `except ValueError` around a
    construction must not accidentally swallow a fail-closed refusal."""
    assert issubclass(Unclassified, LookupError)
    assert not issubclass(Unclassified, ValueError)


def test_it_is_exported_from_the_foundation_package() -> None:
    assert ExportedRegistry is ReversibilityRegistry
