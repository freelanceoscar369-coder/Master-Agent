"""Sprint 1, Component 8 — Kernel Refusal.

Why the Kernel did not mint, in the three parts Kernel Specification §7.5
requires: *"a refusal names the check that failed, the attestor, and whether
it is remediable."*

The invariant tests below make three things unconstructable: a refusal that
names the wrong check for its reason, a K-check refusal that invents an
attestor, and an attestation refusal that attributes the failure to a
component §7.3 did not assign the question to.

Every test uses fixed values. Nothing here reads a wall clock — this value
carries no time at all.
"""
from __future__ import annotations

import ast
import json
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest

from master_agent.foundation import KernelRefusal as ExportedKernelRefusal
from master_agent.foundation.attestation import AttestationQuestion
from master_agent.foundation.refusal import (
    InvalidKernelRefusal,
    KernelCheck,
    KernelRefusal,
    RefusalFamily,
    RefusalReason,
)

KERNEL_CHECK_REASONS = (
    RefusalReason.OBJECTIVE_MISSING,
    RefusalReason.OBJECTIVE_UNKNOWN,
    RefusalReason.OBJECTIVE_TERMINAL,
    RefusalReason.OVERRIDE_ACTIVE,
    RefusalReason.LEDGER_UNAVAILABLE,
)

ATTESTATION_REASONS = (
    RefusalReason.ATTESTATION_ABSENT,
    RefusalReason.ATTESTATION_REFUSED,
)

INFRASTRUCTURE_REASONS = (
    RefusalReason.PERMISSION_SYSTEM_UNAVAILABLE,
    RefusalReason.TOOL_OR_WORKER_UNAVAILABLE,
    RefusalReason.PROVIDER_UNAVAILABLE,
    RefusalReason.KERNEL_UNAVAILABLE,
)


def refusal(**overrides) -> KernelRefusal:
    defaults = {
        "reason": RefusalReason.OVERRIDE_ACTIVE,
        "failed_check": KernelCheck.K2_OVERRIDE_STATE,
        "attestor": None,
        "remediable": True,
        "detail": "autonomy is suspended",
    }
    return KernelRefusal(**{**defaults, **overrides})


def attestation_refusal(question: AttestationQuestion, **overrides):
    defaults = {
        "reason": RefusalReason.ATTESTATION_ABSENT,
        "failed_check": question,
        "attestor": question.canonical_attestor,
        "remediable": True,
        "detail": "no attestation was supplied",
    }
    return KernelRefusal(**{**defaults, **overrides})


# ======================================================================
# KernelCheck — the three of §7.2
# ======================================================================


def test_there_are_exactly_three_kernel_checks() -> None:
    """Kernel Specification §7.2: *"exactly three."* A fourth Kernel-owned
    check is a change to what the Kernel is."""
    assert len(KernelCheck) == 3


def test_the_kernel_check_vocabulary_is_closed() -> None:
    assert {check.value for check in KernelCheck} == {
        "k1_objective_binding",
        "k2_override_state",
        "k3_receipt_intent_write",
    }


def test_the_kernel_checks_are_declared_in_ordering_order() -> None:
    """§7.1 — cheapest-and-most-fundamental first. K3 runs last, *"after
    every other check has passed."*"""
    assert list(KernelCheck) == [
        KernelCheck.K1_OBJECTIVE_BINDING,
        KernelCheck.K2_OVERRIDE_STATE,
        KernelCheck.K3_RECEIPT_INTENT_WRITE,
    ]


def test_a_kernel_check_is_not_an_attestation_question() -> None:
    """The two vocabularies never overlap: §7.2's checks are the Kernel's
    own, §7.3's questions belong to other components."""
    assert {c.value for c in KernelCheck} & {
        q.value for q in AttestationQuestion
    } == set()


# ======================================================================
# RefusalReason — three families
# ======================================================================


def test_the_reason_vocabulary_is_closed() -> None:
    assert {reason.value for reason in RefusalReason} == {
        "objective_missing",
        "objective_unknown",
        "objective_terminal",
        "override_active",
        "ledger_unavailable",
        "attestation_absent",
        "attestation_refused",
        "permission_system_unavailable",
        "tool_or_worker_unavailable",
        "provider_unavailable",
        "kernel_unavailable",
    }


def test_every_reason_belongs_to_exactly_one_family() -> None:
    assert set(RefusalReason) == set(
        KERNEL_CHECK_REASONS + ATTESTATION_REASONS + INFRASTRUCTURE_REASONS
    )


def test_there_are_exactly_three_families() -> None:
    """Roadmap Amendment 001 M5. A reason set covering only attestations
    would leave "the ledger is down" unrepresentable."""
    assert len(RefusalFamily) == 3
    assert {f.value for f in RefusalFamily} == {
        "kernel_check",
        "attestation",
        "infrastructure",
    }


@pytest.mark.parametrize("reason", KERNEL_CHECK_REASONS)
def test_kernel_check_reasons_report_their_family(reason) -> None:
    assert reason.family is RefusalFamily.KERNEL_CHECK


@pytest.mark.parametrize("reason", ATTESTATION_REASONS)
def test_attestation_reasons_report_their_family(reason) -> None:
    assert reason.family is RefusalFamily.ATTESTATION


@pytest.mark.parametrize("reason", INFRASTRUCTURE_REASONS)
def test_infrastructure_reasons_report_their_family(reason) -> None:
    assert reason.family is RefusalFamily.INFRASTRUCTURE


def test_each_of_the_three_kernel_checks_is_representable() -> None:
    """§7.5 requires refusals to be recorded. A K-check with no reason would
    be an unrecordable refusal."""
    refused_at = {
        RefusalReason.OBJECTIVE_MISSING: KernelCheck.K1_OBJECTIVE_BINDING,
        RefusalReason.OVERRIDE_ACTIVE: KernelCheck.K2_OVERRIDE_STATE,
        RefusalReason.LEDGER_UNAVAILABLE: KernelCheck.K3_RECEIPT_INTENT_WRITE,
    }
    assert set(refused_at.values()) == set(KernelCheck)


def test_k1_refuses_the_three_conditions_seven_two_names() -> None:
    """§7.2 K1 *"Refuses: no objective · unknown objective · objective
    already completed, failed, or cancelled."* Three conditions, three
    remedies, three reasons."""
    k1 = {
        RefusalReason.OBJECTIVE_MISSING,
        RefusalReason.OBJECTIVE_UNKNOWN,
        RefusalReason.OBJECTIVE_TERMINAL,
    }
    for reason in k1:
        assert refusal(
            reason=reason,
            failed_check=KernelCheck.K1_OBJECTIVE_BINDING,
            detail="objective check failed",
        ).failed_check is KernelCheck.K1_OBJECTIVE_BINDING


def test_a_degraded_network_is_not_a_refusal_reason() -> None:
    """§11.7 — network unavailable is DEGRADED. *"The Kernel decides nothing
    here."* A reason for it would imply otherwise."""
    assert not any("network" in reason.value for reason in RefusalReason)
    assert not any("offline" in reason.value for reason in RefusalReason)


def test_learning_unavailable_is_not_a_refusal_reason() -> None:
    """§11.4 — the only "proceed" in the failure table. Execution does not
    know or care."""
    assert not any("learning" in reason.value for reason in RefusalReason)


# ======================================================================
# Construction — one per family
# ======================================================================


def test_a_kernel_check_refusal_can_be_created() -> None:
    r = refusal()
    assert r.reason is RefusalReason.OVERRIDE_ACTIVE
    assert r.failed_check is KernelCheck.K2_OVERRIDE_STATE
    assert r.attestor is None
    assert r.remediable is True
    assert r.family is RefusalFamily.KERNEL_CHECK


@pytest.mark.parametrize("question", list(AttestationQuestion))
def test_every_question_can_be_the_failed_check(question) -> None:
    r = attestation_refusal(question)
    assert r.failed_check is question
    assert r.attestor == question.canonical_attestor
    assert r.is_attestation_failure


def test_an_attestation_refusal_carries_the_attestors_verdict() -> None:
    """§7.3 — the Kernel *"never re-derives the verdict."* It carries this
    one through."""
    r = attestation_refusal(
        AttestationQuestion.REVERSIBILITY,
        reason=RefusalReason.ATTESTATION_REFUSED,
        remediable=True,
        detail="Filesystem.DeleteFile is unclassified",
    )
    assert r.reason is RefusalReason.ATTESTATION_REFUSED
    assert r.attestor == "reversibility_registry"


def test_the_kernel_being_unavailable_names_no_check() -> None:
    """§11.9 — nothing executes. No check was reached, so none is named."""
    r = refusal(
        reason=RefusalReason.KERNEL_UNAVAILABLE,
        failed_check=None,
        attestor=None,
        remediable=True,
        detail="the Kernel is not running",
    )
    assert r.failed_check is None
    assert r.family is RefusalFamily.INFRASTRUCTURE


def test_a_refusal_may_be_irremediable() -> None:
    r = refusal(
        reason=RefusalReason.OBJECTIVE_TERMINAL,
        failed_check=KernelCheck.K1_OBJECTIVE_BINDING,
        remediable=False,
        detail="objective was cancelled on 2026-08-01",
    )
    assert r.remediable is False


# ======================================================================
# failed_check invariants
# ======================================================================


def test_the_reason_must_be_a_refusal_reason() -> None:
    with pytest.raises(InvalidKernelRefusal, match="RefusalReason"):
        refusal(reason="override_active")


@pytest.mark.parametrize(
    "bad", ["k2_override_state", 2, KernelCheck, object()]
)
def test_the_failed_check_must_be_a_check_or_a_question(bad) -> None:
    with pytest.raises(InvalidKernelRefusal, match="failed_check"):
        refusal(failed_check=bad)


def test_the_override_refusal_may_not_name_another_check() -> None:
    """§7.2 pairs each K-reason with exactly one check. A refusal that names
    the wrong one is a false record."""
    with pytest.raises(InvalidKernelRefusal, match="k2_override_state"):
        refusal(failed_check=KernelCheck.K1_OBJECTIVE_BINDING)


def test_the_ledger_refusal_names_k3() -> None:
    with pytest.raises(InvalidKernelRefusal, match="k3_receipt_intent_write"):
        refusal(
            reason=RefusalReason.LEDGER_UNAVAILABLE,
            failed_check=KernelCheck.K2_OVERRIDE_STATE,
            detail="the ledger did not accept the write",
        )


def test_a_kernel_check_reason_may_not_name_an_attestation_question() -> None:
    with pytest.raises(InvalidKernelRefusal):
        refusal(
            failed_check=AttestationQuestion.PERMISSION,
            attestor="permission_system",
        )


def test_an_attestation_reason_may_not_name_a_kernel_check() -> None:
    """§7.3's eight belong to other components; §7.2's three do not."""
    with pytest.raises(InvalidKernelRefusal):
        refusal(
            reason=RefusalReason.ATTESTATION_ABSENT,
            failed_check=KernelCheck.K1_OBJECTIVE_BINDING,
            detail="missing",
        )


def test_an_unavailable_permission_system_is_refused_at_a3() -> None:
    """§11.1 — the Permission System's answer is A3, so its unavailability
    is a refusal there and nowhere else."""
    r = refusal(
        reason=RefusalReason.PERMISSION_SYSTEM_UNAVAILABLE,
        failed_check=AttestationQuestion.PERMISSION,
        attestor="permission_system",
        remediable=True,
        detail="the permission system did not answer",
    )
    assert r.failed_check is AttestationQuestion.PERMISSION

    with pytest.raises(InvalidKernelRefusal, match="permission"):
        refusal(
            reason=RefusalReason.PERMISSION_SYSTEM_UNAVAILABLE,
            failed_check=AttestationQuestion.RULE,
            attestor="standing_rule_engine",
            detail="the permission system did not answer",
        )


def test_an_unavailable_provider_is_refused_at_a7() -> None:
    """§11.6 — *"No `DecisionRecord` ⇒ A7 attestation absent ⇒ refuse."*"""
    r = refusal(
        reason=RefusalReason.PROVIDER_UNAVAILABLE,
        failed_check=AttestationQuestion.PROVIDER,
        attestor="broker",
        remediable=True,
        detail="no provider on this machine serves reasoning",
    )
    assert r.attestor == "broker"

    with pytest.raises(InvalidKernelRefusal):
        refusal(
            reason=RefusalReason.PROVIDER_UNAVAILABLE,
            failed_check=AttestationQuestion.ADMISSION,
            attestor="broker",
            detail="no provider",
        )


@pytest.mark.parametrize(
    "question",
    [AttestationQuestion.TASK_READY, AttestationQuestion.PAYLOAD_SCHEMA],
)
def test_a_missing_worker_is_refused_at_a1_or_a6(question) -> None:
    """§11.5 — *"Refused at A1/A6 attestation, before an intent exists."*"""
    r = refusal(
        reason=RefusalReason.TOOL_OR_WORKER_UNAVAILABLE,
        failed_check=question,
        attestor=question.canonical_attestor,
        remediable=True,
        detail="no worker offers Filesystem.WriteFile",
    )
    assert r.failed_check is question


def test_a_missing_worker_is_not_refused_at_a3() -> None:
    with pytest.raises(InvalidKernelRefusal):
        refusal(
            reason=RefusalReason.TOOL_OR_WORKER_UNAVAILABLE,
            failed_check=AttestationQuestion.PERMISSION,
            attestor="permission_system",
            detail="no worker",
        )


def test_only_the_unavailable_kernel_may_name_no_check() -> None:
    """Every other refusal happened somewhere, and §7.5 requires it to say
    where."""
    nameless = [
        reason
        for reason in RefusalReason
        if _accepts_no_check(reason)
    ]
    assert nameless == [RefusalReason.KERNEL_UNAVAILABLE]


def _accepts_no_check(reason: RefusalReason) -> bool:
    try:
        KernelRefusal(
            reason=reason,
            failed_check=None,
            attestor=None,
            remediable=True,
            detail="probe",
        )
    except InvalidKernelRefusal:
        return False
    return True


def test_an_unavailable_kernel_may_not_name_a_check() -> None:
    with pytest.raises(InvalidKernelRefusal):
        refusal(
            reason=RefusalReason.KERNEL_UNAVAILABLE,
            failed_check=KernelCheck.K1_OBJECTIVE_BINDING,
            detail="the Kernel is not running",
        )


# ======================================================================
# attestor invariants
# ======================================================================


def test_a_kernel_check_refusal_has_no_attestor() -> None:
    """Roadmap Amendment 001 M5: *"A refusal from K1 has no attestor, because
    no attestor was involved."*"""
    with pytest.raises(InvalidKernelRefusal, match="no attestor"):
        refusal(attestor="mission_control")


def test_a_refusal_naming_no_check_has_no_attestor() -> None:
    with pytest.raises(InvalidKernelRefusal, match="no attestor"):
        refusal(
            reason=RefusalReason.KERNEL_UNAVAILABLE,
            failed_check=None,
            attestor="broker",
            detail="the Kernel is not running",
        )


@pytest.mark.parametrize("question", list(AttestationQuestion))
def test_an_attestation_refusal_requires_the_canonical_attestor(question) -> None:
    """§7.3 assigns each question exactly one attestor. A refusal naming a
    different one attributes the failure to the wrong component."""
    with pytest.raises(InvalidKernelRefusal, match="attested by"):
        attestation_refusal(question, attestor="something_else")


@pytest.mark.parametrize("question", list(AttestationQuestion))
def test_an_attestation_refusal_may_not_omit_the_attestor(question) -> None:
    with pytest.raises(InvalidKernelRefusal, match="attested by"):
        attestation_refusal(question, attestor=None)


def test_both_broker_questions_name_the_broker() -> None:
    for question in (AttestationQuestion.PROVIDER, AttestationQuestion.ADMISSION):
        assert attestation_refusal(question).attestor == "broker"


def test_a_principal_is_never_the_attestor_of_a_refusal() -> None:
    """ED-018, carried forward. All eight attestors are components."""
    with pytest.raises(InvalidKernelRefusal):
        attestation_refusal(
            AttestationQuestion.PRINCIPAL, attestor="founder"
        )


# ======================================================================
# remediable and detail
# ======================================================================


@pytest.mark.parametrize("bad", [1, 0, "yes", None])
def test_remediable_must_be_a_boolean(bad) -> None:
    with pytest.raises(InvalidKernelRefusal, match="remediable"):
        refusal(remediable=bad)


def test_remediable_has_no_default() -> None:
    """The most consequential bit in a refusal must not be set by
    omission."""
    with pytest.raises(TypeError):
        KernelRefusal(
            reason=RefusalReason.OVERRIDE_ACTIVE,
            failed_check=KernelCheck.K2_OVERRIDE_STATE,
            attestor=None,
            detail="autonomy is suspended",
        )


@pytest.mark.parametrize("blank", ["", "   ", "\n"])
def test_a_refusal_without_detail_is_itself_refused(blank) -> None:
    """§7.5 — the founder reads a sentence about their own machine, not a
    stack trace. A refusal that cannot explain itself is the stack trace."""
    with pytest.raises(InvalidKernelRefusal, match="detail"):
        refusal(detail=blank)


def test_detail_must_be_a_string() -> None:
    with pytest.raises(InvalidKernelRefusal, match="detail"):
        refusal(detail=404)


def test_detail_has_no_default() -> None:
    with pytest.raises(TypeError):
        KernelRefusal(
            reason=RefusalReason.OVERRIDE_ACTIVE,
            failed_check=KernelCheck.K2_OVERRIDE_STATE,
            attestor=None,
            remediable=True,
        )


# ======================================================================
# Value semantics
# ======================================================================


@pytest.mark.parametrize(
    "field", ["reason", "failed_check", "attestor", "remediable", "detail"]
)
def test_a_refusal_cannot_be_mutated(field) -> None:
    r = refusal()
    with pytest.raises(FrozenInstanceError):
        setattr(r, field, None)


def test_equality_is_deterministic() -> None:
    assert refusal() == refusal()


def test_two_refusals_differing_in_detail_are_different() -> None:
    assert refusal() != refusal(detail="autonomy is suspended by the founder")


def test_a_refusal_is_hashable() -> None:
    """§7.5 — *"a thousand refusals are one state."* Collapsing them
    requires them to be usable in a set."""
    assert len({refusal(), refusal(), refusal()}) == 1


def test_a_thousand_identical_refusals_collapse_to_one() -> None:
    thousand = {
        refusal(detail="autonomy is suspended") for _ in range(1000)
    }
    assert len(thousand) == 1


# ======================================================================
# Serialisation
# ======================================================================


def test_serialisation_is_deterministic() -> None:
    assert refusal().as_dict() == refusal().as_dict()


def test_serialisation_is_json_ready() -> None:
    assert json.loads(json.dumps(refusal().as_dict()))


def test_serialisation_carries_every_field() -> None:
    r = attestation_refusal(
        AttestationQuestion.PERMISSION,
        reason=RefusalReason.ATTESTATION_REFUSED,
        remediable=False,
        detail="no grant exists for Filesystem.DeleteFile",
    )
    assert r.as_dict() == {
        "reason": "attestation_refused",
        "family": "attestation",
        "failed_check": "permission",
        "failed_check_kind": "attestation",
        "attestor": "permission_system",
        "remediable": False,
        "detail": "no grant exists for Filesystem.DeleteFile",
    }


def test_serialisation_distinguishes_a_kernel_check_from_a_question() -> None:
    """A reader fifteen years from now will not have these enum classes.
    `k2_override_state` should not have to be told apart from `permission`
    by inspection."""
    assert refusal().as_dict()["failed_check_kind"] == "kernel_check"
    assert (
        attestation_refusal(AttestationQuestion.RULE).as_dict()[
            "failed_check_kind"
        ]
        == "attestation"
    )


def test_serialisation_of_a_checkless_refusal() -> None:
    r = refusal(
        reason=RefusalReason.KERNEL_UNAVAILABLE,
        failed_check=None,
        attestor=None,
        remediable=True,
        detail="the Kernel is not running",
    )
    projected = r.as_dict()
    assert projected["failed_check"] is None
    assert projected["failed_check_kind"] is None
    assert projected["attestor"] is None


# ======================================================================
# CONSTITUTIONAL
# ======================================================================

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE = REPO_ROOT / "src" / "master_agent" / "foundation" / "refusal.py"

FORBIDDEN_VERBS = (
    "execute", "run", "invoke", "perform", "dispatch",
    "authorize", "authorise", "grant", "permit", "approve", "deny",
    "mint", "issue", "settle", "revoke", "start", "stop", "update", "set",
)

FORBIDDEN_IMPORTS = (
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


def _module_imports() -> list[str]:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    return imported


def _module_imported_names() -> set[str]:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
            "master_agent"
        ):
            names.update(alias.name for alias in node.names)
    return names


def _public_surface() -> list[str]:
    field_names = {f.name for f in fields(KernelRefusal)}
    return [
        name
        for name in dir(KernelRefusal)
        if not name.startswith("_") and name not in field_names
    ]


def test_it_depends_on_component_seven_and_nothing_else() -> None:
    """Roadmap Amendment 001 M5 — *"C7's `AttestationQuestion` enum only."*"""
    internal = {
        name for name in _module_imports() if name.startswith("master_agent")
    }
    assert internal == {"master_agent.foundation.attestation"}


def test_it_imports_the_question_and_not_the_attestation() -> None:
    """*"A refusal names which question failed, never the attestation
    object."* Importing the type would invite carrying one."""
    assert _module_imported_names() == {"AttestationQuestion"}


def test_it_has_no_dependency_on_the_warrant() -> None:
    assert not any("warrant" in name for name in _module_imports())
    assert not any("warrant" in f.name for f in fields(KernelRefusal))


def test_it_has_no_dependency_on_the_principal() -> None:
    """ED-018. The attestor is a component, never a human authority."""
    assert not any("principal" in name for name in _module_imports())


def test_it_has_no_dependency_on_the_clock() -> None:
    """A refusal carries no time: the ledger records when it happened, and a
    second reading of the clock is a second answer to one question."""
    assert not any("clock" in name for name in _module_imports())


def test_it_imports_nothing_that_could_act() -> None:
    offenders = [
        name
        for name in _module_imports()
        if any(name.startswith(forbidden) for forbidden in FORBIDDEN_IMPORTS)
    ]
    assert not offenders, f"refusal.py imports {offenders}"


def test_it_cannot_execute_or_authorize_work() -> None:
    """It records that nothing happened. It makes nothing happen."""
    offenders = [
        name
        for name in _public_surface()
        if any(verb in name.lower() for verb in FORBIDDEN_VERBS)
    ]
    assert not offenders, f"KernelRefusal exposes {offenders}"


def test_it_holds_no_runtime_state() -> None:
    names = {f.name for f in fields(KernelRefusal)}
    forbidden = {"status", "state", "result", "outcome", "progress", "retries"}
    assert not names & forbidden


def test_it_reads_no_ambient_time() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    banned = {"datetime.now", "datetime.utcnow", "datetime.today", "time.time"}
    calls = [
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ".".join(ast.unparse(node.func).split(".")[-2:]) in banned
    ]
    assert not calls, f"refusal.py reads ambient time: {calls}"


def test_a_refusal_is_not_a_judgment_request() -> None:
    """§7.5: *"Under an active Override, a thousand refusals are one state —
    'autonomy is suspended; 1,000 actions are waiting' — not a thousand queue
    items."* Every field below would be the beginning of a queue."""
    names = {f.name for f in fields(KernelRefusal)}
    queue_shaped = {
        "id",
        "refusal_id",
        "assignee",
        "assigned_to",
        "priority",
        "severity",
        "count",
        "created_at",
        "requires_approval",
        "requires_decision",
        "acknowledged",
        "dismissed",
    }
    assert not names & queue_shaped


def test_it_composes_no_founder_facing_sentence() -> None:
    """C20's Voice Charter Validator owns every outbound utterance. A value
    object that phrases its own is one that reaches the founder
    un-validated."""
    offenders = [
        name
        for name in _public_surface()
        if any(word in name.lower() for word in ("message", "sentence", "text",
                                                 "narrate", "render", "speak",
                                                 "display", "headline"))
    ]
    assert not offenders, f"KernelRefusal exposes {offenders}"


def test_it_is_named_kernel_refusal_and_not_refusal() -> None:
    """`BrokerRefusal` and `PlanRefusal` already exist. A bare third would
    repeat the `Intent` collision."""
    import master_agent.foundation.refusal as module

    assert not hasattr(module, "Refusal")
    assert KernelRefusal.__name__ == "KernelRefusal"


def test_it_is_exported_from_the_foundation_package() -> None:
    assert ExportedKernelRefusal is KernelRefusal


def test_components_one_to_seven_are_untouched() -> None:
    from master_agent.foundation import (
        attestation,
        clock,
        consequence,
        execution_context,
        principal,
        receipt,
        warrant,
    )

    assert hasattr(clock, "SystemClock")
    assert hasattr(principal, "PrincipalRegistry")
    assert hasattr(execution_context, "ExecutionContext")
    assert hasattr(warrant, "Warrant")
    assert hasattr(receipt, "Receipt")
    assert hasattr(consequence, "Consequence")
    assert hasattr(attestation, "Attestation")
