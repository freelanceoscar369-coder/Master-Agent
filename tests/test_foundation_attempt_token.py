"""Sprint 1, Component 10 — Attempt Token.

Permission to open one attempt against a live warrant. Kernel
Specification §3.5: `attempt(intent_id) → AttemptToken | Refusal`.

§8.6 states what this value is for: *"The Kernel provides the key —
`(intent_id, attempt_seq)`."* The tests below enforce that it carries
exactly that key and the moment it opened — and that it carries nothing
which would let a holder re-derive a decision the Kernel already made.

Every test uses fixed instants. Nothing here reads a wall clock.
"""
from __future__ import annotations

import ast
import json
from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from master_agent.foundation import AttemptToken as ExportedAttemptToken
from master_agent.foundation.attempt_token import (
    FIRST_ATTEMPT,
    AttemptToken,
    InvalidAttemptToken,
)

OPENED = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)


def token(**overrides) -> AttemptToken:
    defaults = {
        "warrant_id": "wrt-001",
        "attempt_seq": 1,
        "opened_at": OPENED,
    }
    return AttemptToken(**{**defaults, **overrides})


# ======================================================================
# Construction
# ======================================================================


def test_a_token_can_be_created() -> None:
    t = token()
    assert t.warrant_id == "wrt-001"
    assert t.attempt_seq == 1
    assert t.opened_at == OPENED


def test_the_first_attempt_is_numbered_one() -> None:
    """§8.5 — an `irreversible` budget of 1 means one attempt and no
    second. That is unambiguous only if counting starts at 1."""
    assert FIRST_ATTEMPT == 1


@pytest.mark.parametrize("seq", [1, 2, 3, 10, 1000])
def test_any_positive_sequence_is_accepted(seq) -> None:
    """The upper bound is the warrant's `attempt_budget`, which this value
    does not carry and must not enforce."""
    assert token(attempt_seq=seq).attempt_seq == seq


def test_every_field_is_required() -> None:
    with pytest.raises(TypeError):
        AttemptToken(warrant_id="wrt-001")  # type: ignore[call-arg]


# ======================================================================
# warrant_id
# ======================================================================


@pytest.mark.parametrize("bad", ["", "   ", "\n"])
def test_a_blank_warrant_id_is_refused(bad) -> None:
    with pytest.raises(InvalidAttemptToken, match="warrant_id"):
        token(warrant_id=bad)


@pytest.mark.parametrize("bad", [None, 42, b"wrt-001", ["wrt-001"]])
def test_a_non_string_warrant_id_is_refused(bad) -> None:
    with pytest.raises(InvalidAttemptToken, match="warrant_id"):
        token(warrant_id=bad)


# ======================================================================
# attempt_seq
# ======================================================================


def test_attempt_zero_is_refused() -> None:
    """There is no attempt zero. §8.5."""
    with pytest.raises(InvalidAttemptToken, match="no attempt zero"):
        token(attempt_seq=0)


@pytest.mark.parametrize("seq", [-1, -5, -1000])
def test_a_negative_sequence_is_refused(seq) -> None:
    with pytest.raises(InvalidAttemptToken, match="attempt_seq"):
        token(attempt_seq=seq)


@pytest.mark.parametrize("bad", ["1", 1.0, None, [1]])
def test_a_non_integer_sequence_is_refused(bad) -> None:
    with pytest.raises(InvalidAttemptToken, match="integer"):
        token(attempt_seq=bad)


@pytest.mark.parametrize("bad", [True, False])
def test_a_boolean_sequence_is_refused(bad) -> None:
    """`bool` subclasses `int`, so `True` would otherwise pass as attempt
    1. An attempt numbered `True` is a caller error, not a first
    attempt."""
    with pytest.raises(InvalidAttemptToken, match="integer"):
        token(attempt_seq=bad)


# ======================================================================
# opened_at
# ======================================================================


def test_a_naive_timestamp_is_refused() -> None:
    with pytest.raises(InvalidAttemptToken, match="timezone-aware"):
        token(opened_at=datetime(2026, 8, 5, 12, 0))  # noqa: DTZ001


@pytest.mark.parametrize("bad", [None, "2026-08-05T12:00:00Z", 1785000000])
def test_a_non_datetime_is_refused(bad) -> None:
    with pytest.raises(InvalidAttemptToken, match="datetime"):
        token(opened_at=bad)


def test_timestamps_are_normalised_to_utc() -> None:
    """Equality and serialisation must not depend on the caller's zone."""
    ist = timezone(timedelta(hours=5, minutes=30))
    t = token(opened_at=datetime(2026, 8, 5, 17, 30, tzinfo=ist))
    assert t.opened_at.tzinfo is UTC
    assert t.opened_at == OPENED


def test_two_tokens_from_different_zones_are_equal() -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    assert token() == token(opened_at=datetime(2026, 8, 5, 17, 30, tzinfo=ist))


# ======================================================================
# The idempotency key — §8.6
# ======================================================================


def test_the_idempotency_key_is_the_pair_the_spec_names() -> None:
    """§8.6 — *"The Kernel provides the key — `(intent_id,
    attempt_seq)`."*"""
    assert token().idempotency_key == ("wrt-001", 1)


def test_the_key_excludes_the_moment() -> None:
    """Two attempts opened at different instants under the same warrant and
    sequence are one attempt seen twice, not two attempts."""
    later = token(opened_at=OPENED + timedelta(minutes=5))
    assert token().idempotency_key == later.idempotency_key


def test_different_attempts_have_different_keys() -> None:
    assert token(attempt_seq=1).idempotency_key != token(attempt_seq=2).idempotency_key


def test_different_warrants_have_different_keys() -> None:
    assert token().idempotency_key != token(warrant_id="wrt-002").idempotency_key


def test_the_key_is_hashable() -> None:
    """A Worker deduplicates on it, so it must be usable in a set."""
    assert len({token().idempotency_key, token().idempotency_key}) == 1


# ======================================================================
# is_first_attempt
# ======================================================================


def test_the_first_attempt_reports_itself() -> None:
    assert token(attempt_seq=1).is_first_attempt


@pytest.mark.parametrize("seq", [2, 3, 99])
def test_a_later_attempt_is_not_the_first(seq) -> None:
    assert not token(attempt_seq=seq).is_first_attempt


# ======================================================================
# Value semantics
# ======================================================================


@pytest.mark.parametrize("field", ["warrant_id", "attempt_seq", "opened_at"])
def test_a_token_cannot_be_mutated(field) -> None:
    t = token()
    with pytest.raises(FrozenInstanceError):
        setattr(t, field, None)


def test_equality_is_deterministic() -> None:
    assert token() == token()


def test_two_attempts_against_one_warrant_are_different() -> None:
    assert token(attempt_seq=1) != token(attempt_seq=2)


def test_a_token_is_hashable() -> None:
    assert len({token(), token()}) == 1


def test_tokens_for_distinct_attempts_do_not_collapse() -> None:
    assert len({token(attempt_seq=1), token(attempt_seq=2)}) == 2


# ======================================================================
# Serialisation
# ======================================================================


def test_serialisation_is_deterministic() -> None:
    assert token().as_dict() == token().as_dict()


def test_serialisation_is_json_ready() -> None:
    assert json.loads(json.dumps(token().as_dict()))


def test_serialisation_carries_every_field() -> None:
    assert token().as_dict() == {
        "warrant_id": "wrt-001",
        "attempt_seq": 1,
        "opened_at": "2026-08-05T12:00:00+00:00",
    }


def test_serialisation_normalises_the_zone() -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    t = token(opened_at=datetime(2026, 8, 5, 17, 30, tzinfo=ist))
    assert t.as_dict()["opened_at"] == "2026-08-05T12:00:00+00:00"


def test_serialisation_returns_a_dict() -> None:
    """Every `as_dict()` in `foundation/` returns a mapping."""
    assert isinstance(token().as_dict(), dict)


# ======================================================================
# CONSTITUTIONAL
# ======================================================================

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE = REPO_ROOT / "src" / "master_agent" / "foundation" / "attempt_token.py"

FORBIDDEN_VERBS = (
    "execute", "run", "invoke", "perform", "dispatch",
    "authorize", "authorise", "grant", "permit", "approve", "deny",
    "mint", "issue", "settle", "revoke", "start", "stop", "update", "set",
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


def _public_surface() -> list[str]:
    field_names = {f.name for f in fields(AttemptToken)}
    return [
        name
        for name in dir(AttemptToken)
        if not name.startswith("_") and name not in field_names
    ]


def test_it_imports_nothing_from_master_agent_at_all() -> None:
    """Roadmap Amendment 001 M4: C10 depends on **nothing**. Not the
    Warrant, not even the Clock."""
    internal = {n for n in _module_imports() if n.startswith("master_agent")}
    assert internal == set()


def test_it_has_no_dependency_on_the_warrant() -> None:
    """§3.5's operation takes an id, not a warrant. M4."""
    assert not any("warrant" in n for n in _module_imports())


def test_it_has_no_dependency_on_the_clock() -> None:
    """`opened_at` is passed in, as `Warrant.issued_at` is."""
    assert not any("clock" in n for n in _module_imports())


def test_it_imports_nothing_that_could_act() -> None:
    forbidden = (
        "master_agent",
        "subprocess",
        "socket",
        "threading",
        "asyncio",
    )
    offenders = [
        n for n in _module_imports() if any(n.startswith(f) for f in forbidden)
    ]
    assert not offenders, f"attempt_token.py imports {offenders}"


def test_it_cannot_execute_or_authorize_work() -> None:
    """The Kernel decided before this existed. It permits nothing itself."""
    offenders = [
        name
        for name in _public_surface()
        if any(verb in name.lower() for verb in FORBIDDEN_VERBS)
    ]
    assert not offenders, f"AttemptToken exposes {offenders}"


def test_it_carries_no_budget() -> None:
    """§8.5 — the budget is *"set at mint from the capability's class,
    never by the retry loop."* A token that knew its own budget is a retry
    loop one field away from enforcing its own policy."""
    names = {f.name for f in fields(AttemptToken)}
    assert not names & {
        "attempt_budget",
        "budget",
        "max_attempts",
        "remaining",
        "attempts_left",
        "ceiling",
    }


def test_it_carries_no_retry_policy() -> None:
    """§8.4 is the most important clause in §8 and it belongs to the Kernel
    and the Reversibility Registry, never to the thing being retried."""
    names = {f.name for f in fields(AttemptToken)} | set(_public_surface())
    assert not any(
        w in n.lower() for n in names for w in ("retry", "reversib", "policy")
    )


def test_it_carries_no_expiry() -> None:
    """The validity window belongs to the Warrant. A token is opened inside
    one that the Kernel has already confirmed is live."""
    names = {f.name for f in fields(AttemptToken)} | set(_public_surface())
    assert not any(w in n.lower() for n in names for w in ("expire", "expiry", "deadline"))


def test_it_holds_no_runtime_state() -> None:
    names = {f.name for f in fields(AttemptToken)}
    assert not names & {"status", "state", "result", "outcome", "progress", "error"}


def test_it_carries_no_payload() -> None:
    names = {f.name for f in fields(AttemptToken)}
    assert not any("payload" in n for n in names)


def test_it_reads_no_ambient_time() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    banned = {"datetime.now", "datetime.utcnow", "datetime.today", "time.time"}
    calls = [
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ".".join(ast.unparse(node.func).split(".")[-2:]) in banned
    ]
    assert not calls, f"attempt_token.py reads ambient time: {calls}"


def test_it_has_exactly_three_fields() -> None:
    """Roadmap v2 §2 C10: `AttemptToken (frozen: warrant_id, attempt_seq,
    opened_at)`."""
    assert [f.name for f in fields(AttemptToken)] == [
        "warrant_id",
        "attempt_seq",
        "opened_at",
    ]


def test_it_is_exported_from_the_foundation_package() -> None:
    assert ExportedAttemptToken is AttemptToken
