"""PermissionSystem unit tests — first dedicated test module for this
class (previously only exercised indirectly through executor/plugin
tests). Mission Brief 005 added one new rule to check(): an
ALWAYS_FOR_CAPABILITY grant can never satisfy an IRREVERSIBLE check, no
matter how it was created (see permission_system.py's check() docstring
and FILESYSTEM_CAPABILITIES.md §5). This file covers that new rule plus
regression coverage of the pre-existing behavior: the READ_ONLY
short-circuit and ONCE-grant consumption.
"""
from __future__ import annotations

import pytest

from master_agent.permissions.permission_system import (
    ApprovalRequired,
    GrantScope,
    PermissionSystem,
)
from master_agent.plugins.base import RiskTier

# ---- READ_ONLY short-circuit (pre-existing, regression) -------------------------

def test_read_only_never_requires_a_grant():
    permissions = PermissionSystem()
    # No grant() call at all -- should not raise.
    permissions.check("filesystem", "read_file", RiskTier.READ_ONLY)


# ---- REVERSIBLE_WRITE: ONCE grant consumption (pre-existing, regression) --------

def test_reversible_write_without_a_grant_raises_approval_required():
    permissions = PermissionSystem()
    with pytest.raises(ApprovalRequired):
        permissions.check("filesystem", "write_file", RiskTier.REVERSIBLE_WRITE)


def test_reversible_write_once_grant_is_consumed_after_one_check():
    permissions = PermissionSystem()
    permissions.grant("filesystem", "write_file", GrantScope.ONCE)

    permissions.check("filesystem", "write_file", RiskTier.REVERSIBLE_WRITE)  # covered
    with pytest.raises(ApprovalRequired):
        permissions.check("filesystem", "write_file", RiskTier.REVERSIBLE_WRITE)  # consumed


def test_reversible_write_always_for_capability_grant_is_reusable():
    permissions = PermissionSystem()
    permissions.grant("filesystem", "write_file", GrantScope.ALWAYS_FOR_CAPABILITY)

    permissions.check("filesystem", "write_file", RiskTier.REVERSIBLE_WRITE)
    permissions.check("filesystem", "write_file", RiskTier.REVERSIBLE_WRITE)  # still covered


def test_reversible_write_this_session_grant_is_reusable_until_revoked():
    permissions = PermissionSystem()
    permissions.grant("filesystem", "write_file", GrantScope.THIS_SESSION)

    permissions.check("filesystem", "write_file", RiskTier.REVERSIBLE_WRITE)
    permissions.revoke_session_grants()
    with pytest.raises(ApprovalRequired):
        permissions.check("filesystem", "write_file", RiskTier.REVERSIBLE_WRITE)


# ---- IRREVERSIBLE: the new Mission Brief 005 rule --------------------------------

def test_irreversible_without_a_grant_raises_approval_required():
    permissions = PermissionSystem()
    with pytest.raises(ApprovalRequired):
        permissions.check("filesystem", "delete_file", RiskTier.IRREVERSIBLE)


def test_irreversible_once_grant_satisfies_a_single_check():
    permissions = PermissionSystem()
    permissions.grant("filesystem", "delete_file", GrantScope.ONCE)

    permissions.check("filesystem", "delete_file", RiskTier.IRREVERSIBLE)  # covered, consumed
    with pytest.raises(ApprovalRequired):
        permissions.check("filesystem", "delete_file", RiskTier.IRREVERSIBLE)


def test_irreversible_this_session_grant_is_reusable_until_revoked():
    permissions = PermissionSystem()
    permissions.grant("filesystem", "delete_file", GrantScope.THIS_SESSION)

    permissions.check("filesystem", "delete_file", RiskTier.IRREVERSIBLE)
    permissions.revoke_session_grants()
    with pytest.raises(ApprovalRequired):
        permissions.check("filesystem", "delete_file", RiskTier.IRREVERSIBLE)


def test_irreversible_always_for_capability_grant_never_satisfies_the_check():
    """The core new rule: even a standing blanket grant cannot pre-approve
    a destructive action. Distinguishes this from REVERSIBLE_WRITE, where
    the same grant scope is reusable indefinitely (see
    test_reversible_write_always_for_capability_grant_is_reusable above)."""
    permissions = PermissionSystem()
    permissions.grant("filesystem", "delete_folder", GrantScope.ALWAYS_FOR_CAPABILITY)

    with pytest.raises(ApprovalRequired):
        permissions.check("filesystem", "delete_folder", RiskTier.IRREVERSIBLE)


def test_irreversible_always_for_capability_grant_does_not_block_a_fresh_once_grant():
    """An unusable ALWAYS_FOR_CAPABILITY grant sitting in the grant set
    must not prevent a subsequent real (ONCE) grant from working -- the
    two coexist; check() must find the usable one."""
    permissions = PermissionSystem()
    permissions.grant("filesystem", "delete_folder", GrantScope.ALWAYS_FOR_CAPABILITY)
    permissions.grant("filesystem", "delete_folder", GrantScope.ONCE)

    permissions.check("filesystem", "delete_folder", RiskTier.IRREVERSIBLE)  # satisfied by ONCE
    with pytest.raises(ApprovalRequired):
        permissions.check("filesystem", "delete_folder", RiskTier.IRREVERSIBLE)  # ONCE consumed


def test_grants_are_scoped_per_plugin_and_capability():
    permissions = PermissionSystem()
    permissions.grant("filesystem", "delete_file", GrantScope.THIS_SESSION)

    with pytest.raises(ApprovalRequired):
        permissions.check("filesystem", "delete_folder", RiskTier.IRREVERSIBLE)
    with pytest.raises(ApprovalRequired):
        permissions.check("other_plugin", "delete_file", RiskTier.IRREVERSIBLE)
