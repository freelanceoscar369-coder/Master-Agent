"""Sprint 1, Component 14 — Override.

One gesture stops the deciding. VEDA 01 §10: *"All rules dormant, all
autonomy suspended, immediately, with no confirmation dialogue and no
persuasion."*

The constitutional tests below enforce the three prohibitions structurally
rather than by review: **no confirmation parameter in any signature**, **no
friction field**, and **no composed persuasion**. VEDA 01 §10's closing
line is the reason each one is a test — *"a product that makes it hard to
revoke trust has revealed what it thinks trust is for."*

Nothing here reads a wall clock; this value carries no time at all.
"""
from __future__ import annotations

import ast
import inspect
import json
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest

from master_agent.foundation import OverrideSwitch as ExportedSwitch
from master_agent.foundation.override import InvalidOverride, OverrideSwitch

RUNNING = OverrideSwitch(suspended=False)
SUSPENDED = OverrideSwitch(suspended=True, reason="founder override")


# ======================================================================
# Construction
# ======================================================================


def test_a_running_switch_can_be_created() -> None:
    assert RUNNING.suspended is False
    assert RUNNING.reason is None
    assert not RUNNING.is_suspended


def test_a_suspended_switch_can_be_created() -> None:
    assert SUSPENDED.suspended is True
    assert SUSPENDED.reason == "founder override"
    assert SUSPENDED.is_suspended


def test_suspended_is_required() -> None:
    """There is no default state. A switch nobody set is a switch nobody
    can rely on."""
    with pytest.raises(TypeError):
        OverrideSwitch()  # type: ignore[call-arg]


def test_the_reason_defaults_to_absent_for_a_running_switch() -> None:
    assert OverrideSwitch(suspended=False).reason is None


# ======================================================================
# Adversarial — the suspended flag
# ======================================================================


@pytest.mark.parametrize("bad", [1, 0, "yes", "", None, [], object()])
def test_a_non_boolean_suspension_is_refused(bad) -> None:
    """The type, not the truthiness. A switch built from `1` or `"yes"`
    would read as suspended without anyone having said so."""
    with pytest.raises(InvalidOverride, match="True or False"):
        OverrideSwitch(suspended=bad, reason="x")


# ======================================================================
# Adversarial — the reason symmetry
# ======================================================================


@pytest.mark.parametrize("blank", ["", "   ", "\n"])
def test_a_suspension_without_a_reason_is_refused(blank) -> None:
    """The founder is owed a sentence about their own machine, not a
    silent stop."""
    with pytest.raises(InvalidOverride, match="requires a reason"):
        OverrideSwitch(suspended=True, reason=blank)


def test_a_suspension_with_no_reason_at_all_is_refused() -> None:
    with pytest.raises(InvalidOverride, match="requires a reason"):
        OverrideSwitch(suspended=True)


@pytest.mark.parametrize("bad", [42, [], {"why": "x"}])
def test_a_non_string_reason_is_refused(bad) -> None:
    with pytest.raises(InvalidOverride, match="requires a reason"):
        OverrideSwitch(suspended=True, reason=bad)


def test_a_running_switch_may_not_carry_a_reason() -> None:
    """A reason that outlives its suspension is an explanation for a
    condition that no longer holds."""
    with pytest.raises(InvalidOverride, match="no reason"):
        OverrideSwitch(suspended=False, reason="founder override")


def test_the_reason_is_carried_verbatim() -> None:
    """Supplied, never composed. Nothing here rewrites the founder."""
    words = "  I don't trust the migration script  "
    assert OverrideSwitch(suspended=True, reason=words).reason == words


# ======================================================================
# suspend() — the one gesture
# ======================================================================


def test_suspend_returns_a_suspended_switch() -> None:
    suspended = RUNNING.suspend("founder override")
    assert suspended.is_suspended
    assert suspended.reason == "founder override"


def test_suspend_returns_a_new_switch() -> None:
    suspended = RUNNING.suspend("founder override")
    assert suspended is not RUNNING


def test_suspend_leaves_the_original_running() -> None:
    RUNNING.suspend("founder override")
    assert not RUNNING.is_suspended
    assert RUNNING.reason is None


def test_suspending_an_already_suspended_switch_is_allowed() -> None:
    """Refusing would be friction on the one gesture VEDA 01 §10 says must
    never be discouraged."""
    again = SUSPENDED.suspend("and again")
    assert again.is_suspended
    assert again.reason == "and again"


def test_suspend_still_requires_a_reason() -> None:
    with pytest.raises(InvalidOverride, match="requires a reason"):
        RUNNING.suspend("")


def test_suspend_takes_exactly_one_argument() -> None:
    """One gesture, one reason. A second parameter is a second gate."""
    params = list(inspect.signature(OverrideSwitch.suspend).parameters)
    assert params == ["self", "reason"]


# ======================================================================
# resume()
# ======================================================================


def test_resume_returns_a_running_switch() -> None:
    resumed = SUSPENDED.resume()
    assert not resumed.is_suspended
    assert resumed.reason is None


def test_resume_returns_a_new_switch() -> None:
    assert SUSPENDED.resume() is not SUSPENDED


def test_resume_leaves_the_original_suspended() -> None:
    SUSPENDED.resume()
    assert SUSPENDED.is_suspended
    assert SUSPENDED.reason == "founder override"


def test_resuming_an_already_running_switch_is_allowed() -> None:
    assert not RUNNING.resume().is_suspended


def test_resume_takes_no_argument() -> None:
    """Nothing gates resumption."""
    assert list(inspect.signature(OverrideSwitch.resume).parameters) == ["self"]


def test_resume_drops_the_reason() -> None:
    """The suspension is over; its reason does not survive it."""
    assert SUSPENDED.resume().reason is None


def test_a_round_trip_returns_to_the_starting_state() -> None:
    assert RUNNING.suspend("x").resume() == RUNNING


# ======================================================================
# CONSTITUTIONAL — no confirmation, no friction, no persuasion
# ======================================================================

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE = REPO_ROOT / "src" / "master_agent" / "foundation" / "override.py"

CONFIRMATION_WORDS = (
    "confirm",
    "confirmation",
    "are_you_sure",
    "sure",
    "acknowledge",
    "ack",
    "verify",
    "double_check",
    "force",
    "yes",
    "accept",
    "consent",
)

FRICTION_WORDS = (
    "delay",
    "cooldown",
    "grace",
    "timeout",
    "expires",
    "expiry",
    "retry",
    "attempts",
    "throttle",
    "debounce",
    "min_duration",
)

PERSUASION_WORDS = (
    "warning",
    "warn",
    "message",
    "prompt",
    "copy",
    "explain",
    "persuade",
    "discourage",
    "banner",
)


def _public_methods() -> list[tuple[str, object]]:
    return [
        (name, getattr(OverrideSwitch, name))
        for name in dir(OverrideSwitch)
        if not name.startswith("_") and callable(getattr(OverrideSwitch, name))
    ]


def _module_imports() -> list[str]:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    return imported


def test_no_signature_carries_a_confirmation_parameter() -> None:
    """Kernel Specification §11.8 — *"no confirmation parameter in its
    signature, matching VEDA 04's requirement that none exist."*"""
    offenders = []
    for name, method in _public_methods():
        for param in inspect.signature(method).parameters:
            if any(w in param.lower() for w in CONFIRMATION_WORDS):
                offenders.append(f"{name}({param})")
    assert not offenders, f"OverrideSwitch has confirmation parameters: {offenders}"


def test_no_field_is_a_confirmation() -> None:
    names = {f.name for f in fields(OverrideSwitch)}
    assert not any(w in n.lower() for n in names for w in CONFIRMATION_WORDS)


def test_no_field_introduces_friction() -> None:
    """VEDA 04 A3 — *"suspension latency measured in milliseconds, not in a
    job cycle."* Every one of these is a job cycle wearing a
    safety-feature name."""
    names = {f.name for f in fields(OverrideSwitch)}
    offenders = [n for n in names if any(w in n.lower() for w in FRICTION_WORDS)]
    assert not offenders, f"OverrideSwitch has friction fields: {offenders}"


def test_no_method_introduces_friction() -> None:
    offenders = []
    for name, method in _public_methods():
        for param in inspect.signature(method).parameters:
            if any(w in param.lower() for w in FRICTION_WORDS):
                offenders.append(f"{name}({param})")
    assert not offenders, f"OverrideSwitch has friction parameters: {offenders}"


def test_it_composes_no_persuasion() -> None:
    """VEDA 01 §10 — *"no persuasion."* C20's Voice Charter owns every
    outbound utterance; `reason` is carried, never authored."""
    surface = {f.name for f in fields(OverrideSwitch)} | {
        n for n, _ in _public_methods()
    }
    offenders = [
        n for n in surface if any(w in n.lower() for w in PERSUASION_WORDS)
    ]
    assert not offenders, f"OverrideSwitch exposes {offenders}"


def test_the_switch_has_exactly_two_fields() -> None:
    """Roadmap §2 C14's whole state: suspended, and why."""
    assert [f.name for f in fields(OverrideSwitch)] == ["suspended", "reason"]


def test_it_carries_nothing_about_work_or_queues() -> None:
    """§11.8 — work and queueing continue; only deciding stops. §7.5 — a
    thousand refusals are one state, not a thousand queue items."""
    names = {f.name for f in fields(OverrideSwitch)}
    assert not names & {
        "queue",
        "queued",
        "pending",
        "count",
        "waiting",
        "in_flight",
        "outstanding",
        "warrants",
    }


def test_it_imports_nothing_at_all_from_master_agent() -> None:
    """VEDA 04 A3 — *"must be reachable when the rest of the system is
    degraded."* Roadmap §2 C14 — deliberately outside the main path."""
    internal = {n for n in _module_imports() if n.startswith("master_agent")}
    assert internal == set()


def test_it_has_no_dependency_on_the_clock() -> None:
    """A record of when suspension began belongs to the ledger that records
    it, not to the switch."""
    assert not any("clock" in n for n in _module_imports())


def test_it_reads_no_ambient_time() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    banned = {"datetime.now", "datetime.utcnow", "datetime.today", "time.time"}
    calls = [
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ".".join(ast.unparse(node.func).split(".")[-2:]) in banned
    ]
    assert not calls, f"override.py reads ambient time: {calls}"


def test_it_cannot_mint_execute_or_invalidate() -> None:
    """§11.8's mechanism — invalidating outstanding warrants — is the
    Kernel's. This value only records the state."""
    surface = {n for n, _ in _public_methods()}
    forbidden = (
        "mint",
        "invalidate",
        "execute",
        "run",
        "authorize",
        "cancel",
        "revoke",
    )
    offenders = [n for n in surface if any(v in n.lower() for v in forbidden)]
    assert not offenders, f"OverrideSwitch exposes {offenders}"


# ======================================================================
# Value semantics
# ======================================================================


@pytest.mark.parametrize("field", ["suspended", "reason"])
def test_a_switch_cannot_be_mutated(field) -> None:
    with pytest.raises(FrozenInstanceError):
        setattr(RUNNING, field, None)


def test_a_suspension_cannot_be_lifted_in_place() -> None:
    """Resuming produces a new switch; it never edits a suspension away."""
    with pytest.raises(FrozenInstanceError):
        SUSPENDED.suspended = False


def test_equality_is_deterministic() -> None:
    assert OverrideSwitch(suspended=False) == RUNNING
    assert OverrideSwitch(suspended=True, reason="founder override") == SUSPENDED


def test_running_and_suspended_are_different() -> None:
    assert RUNNING != SUSPENDED


def test_two_suspensions_with_different_reasons_are_different() -> None:
    assert SUSPENDED != OverrideSwitch(suspended=True, reason="something else")


def test_a_switch_is_hashable() -> None:
    assert len({RUNNING, RUNNING}) == 1


def test_a_thousand_identical_suspensions_are_one_state() -> None:
    """§7.5 — *"a thousand refusals are one state."*"""
    assert len({OverrideSwitch(suspended=True, reason="x") for _ in range(1000)}) == 1


# ======================================================================
# Serialization
# ======================================================================


def test_serialisation_is_deterministic() -> None:
    assert SUSPENDED.as_dict() == SUSPENDED.as_dict()


def test_serialisation_is_json_ready() -> None:
    assert json.loads(json.dumps(SUSPENDED.as_dict()))


def test_serialisation_carries_every_field() -> None:
    assert SUSPENDED.as_dict() == {
        "suspended": True,
        "reason": "founder override",
    }


def test_serialisation_of_a_running_switch() -> None:
    assert RUNNING.as_dict() == {"suspended": False, "reason": None}


def test_serialisation_returns_a_dict() -> None:
    assert isinstance(RUNNING.as_dict(), dict)


def test_it_is_exported_from_the_foundation_package() -> None:
    assert ExportedSwitch is OverrideSwitch
