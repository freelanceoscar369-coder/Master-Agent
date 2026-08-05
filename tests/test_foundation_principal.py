"""Sprint 1, Component 2 — Principal.

`Principal` is VEDA 04's term, unchanged: *"the founder, delegates, their
authorities and their own decision histories"* (M5). Always a human
authority. Never Kalpavriksha.

The constitutional tests at the bottom are the ones that matter. A
`Principal` that could represent the system would let Kalpavriksha hold
authority nobody granted and nobody can withdraw, which VEDA 01 §10
forbids — and no unit test of a dataclass would ever notice.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from master_agent.foundation.principal import (
    InvalidPrincipalRegistry,
    Principal,
    PrincipalKind,
    PrincipalRegistry,
    UnknownPrincipal,
)

FOUNDER = Principal("onkar", "Onkar", PrincipalKind.FOUNDER)
CFO = Principal("cfo", "Head of Finance", PrincipalKind.DELEGATE)
ENG = Principal("eng", "Head of Engineering", PrincipalKind.DELEGATE)


# ======================================================================
# Principal — the value
# ======================================================================


def test_a_founder_can_be_created() -> None:
    assert FOUNDER.principal_id == "onkar"
    assert FOUNDER.display_name == "Onkar"
    assert FOUNDER.is_founder


def test_a_delegate_can_be_created() -> None:
    assert CFO.kind is PrincipalKind.DELEGATE
    assert not CFO.is_founder


def test_identity_cannot_be_mutated() -> None:
    """A founder who changes their display name is the same authority.
    Rewriting the record would silently restate who authorized every past
    action."""
    with pytest.raises(FrozenInstanceError):
        FOUNDER.display_name = "Someone Else"  # type: ignore[misc]


@pytest.mark.parametrize("bad", ["", "   "])
def test_an_empty_principal_id_is_refused(bad: str) -> None:
    with pytest.raises(ValueError, match="non-empty identifier"):
        Principal(bad, "Onkar", PrincipalKind.FOUNDER)


@pytest.mark.parametrize("bad", ["", "   "])
def test_an_unnamed_authority_is_refused(bad: str) -> None:
    """A receipt naming an unnamed authority is not answerable."""
    with pytest.raises(ValueError, match="non-empty"):
        Principal("onkar", bad, PrincipalKind.FOUNDER)


def test_principals_compare_by_value() -> None:
    assert Principal("onkar", "Onkar", PrincipalKind.FOUNDER) == FOUNDER


# ======================================================================
# PrincipalRegistry
# ======================================================================


def test_a_registry_always_has_a_founder() -> None:
    assert PrincipalRegistry(FOUNDER).founder() == FOUNDER


def test_a_registry_resolves_a_delegate() -> None:
    registry = PrincipalRegistry(FOUNDER, (CFO, ENG))
    assert registry.resolve("cfo") == CFO


def test_resolving_an_unknown_id_refuses_rather_than_returning_none() -> None:
    """Fails closed. A registry returning `None` would put the refusal in
    every caller, and one caller eventually forgets."""
    registry = PrincipalRegistry(FOUNDER)
    with pytest.raises(UnknownPrincipal, match="no principal with id 'ghost'"):
        registry.resolve("ghost")


def test_is_registered_answers_without_raising() -> None:
    registry = PrincipalRegistry(FOUNDER, (CFO,))
    assert registry.is_registered("cfo")
    assert not registry.is_registered("ghost")


def test_the_founder_slot_will_not_accept_a_delegate() -> None:
    with pytest.raises(InvalidPrincipalRegistry, match="must be of kind FOUNDER"):
        PrincipalRegistry(CFO)


def test_there_is_exactly_one_founder() -> None:
    """VEDA 01 §10 makes the founder's authority absolute and
    unconditional. Two of them is not a richer model but an ambiguous
    one."""
    second_founder = Principal("other", "Someone", PrincipalKind.FOUNDER)
    with pytest.raises(InvalidPrincipalRegistry, match="exactly one founder"):
        PrincipalRegistry(FOUNDER, (second_founder,))


def test_duplicate_ids_are_refused_at_construction() -> None:
    """At construction rather than at first lookup: discovering it the
    first time someone approves something is the worst available moment."""
    clash = Principal("onkar", "Impostor", PrincipalKind.DELEGATE)
    with pytest.raises(InvalidPrincipalRegistry, match="duplicate principal ids"):
        PrincipalRegistry(FOUNDER, (clash,))


def test_all_principals_lists_the_founder_first() -> None:
    registry = PrincipalRegistry(FOUNDER, (CFO, ENG))
    assert registry.all_principals() == (FOUNDER, CFO, ENG)


def test_a_registry_needs_no_delegates() -> None:
    """R10: model the principal as an entity now, even while only one
    exists."""
    assert PrincipalRegistry(FOUNDER).all_principals() == (FOUNDER,)


def test_adding_a_delegate_costs_a_row_not_a_migration() -> None:
    """The whole reason VEDA 04 R10 asks for this component now."""
    before = PrincipalRegistry(FOUNDER)
    after = PrincipalRegistry(FOUNDER, (CFO,))

    assert before.founder() == after.founder()
    assert after.resolve("cfo") == CFO


# ======================================================================
# CONSTITUTIONAL — a Principal is always a human authority
# ======================================================================


def test_there_are_exactly_two_kinds_of_principal() -> None:
    """VEDA 04 M5 names two: the founder, and delegates. An open enum is
    where a `system` principal quietly reappears."""
    assert {kind.value for kind in PrincipalKind} == {"founder", "delegate"}


def test_there_is_no_system_principal() -> None:
    """The one test this component exists to make impossible to break.

    `SPRING_1_IMPLEMENTATION_PLAN.md` §5 C2 sketched a `system` kind. It
    has no basis in VEDA 04 and it is the original conflict in miniature:
    a non-human principal is Kalpavriksha holding authority under another
    name, which VEDA 01 §10 forbids — *"every capability Kalpavriksha holds
    was granted... autonomy is lent, never earned in a way that makes it
    permanent."*

    If this test ever needs deleting, that is a constitutional amendment,
    not a refactor.
    """
    assert not hasattr(PrincipalKind, "SYSTEM")
    for forbidden in ("system", "kalpavriksha", "vedra", "agent", "service"):
        with pytest.raises(ValueError):
            PrincipalKind(forbidden)


def test_a_receipt_can_always_name_which_human_authorized_it() -> None:
    """The question the ledger exists to answer. Every principal resolves
    to a named human with a kind, so `"who authorized this?"` never
    degrades into `"which program ran?"`."""
    registry = PrincipalRegistry(FOUNDER, (CFO,))

    for principal in registry.all_principals():
        assert principal.display_name.strip()
        assert principal.kind in (PrincipalKind.FOUNDER, PrincipalKind.DELEGATE)
