"""LocalExecutor unit tests -- the core new coverage for Mission Brief 002.
Uses a minimal fake Action (not CreateFolderAction) so these tests are
about the Executor's own contract (validation ordering, permission
gating, structured failures, logging, never crashing) independent of any
one action's business logic.
"""
from __future__ import annotations

import pytest

from master_agent.executor.action import Action, ExecutionResult
from master_agent.executor.executor import LocalExecutor
from master_agent.permissions.permission_system import (
    ApprovalRequired,
    GrantScope,
    PermissionSystem,
)
from master_agent.plugins.base import RiskTier


class EchoAction(Action):
    """Succeeds and echoes its `value` parameter back."""

    name = "echo"
    description = "Echo a value back (test fixture)."
    risk_tier = RiskTier.REVERSIBLE_WRITE
    expected_result = "output equals the given value"

    def required_parameters(self) -> list[str]:
        return ["value"]

    def validate(self, parameters):
        return [] if "value" in parameters else ["missing required parameter: value"]

    def run(self, parameters):
        return ExecutionResult(success=True, output=parameters["value"])


class ReadOnlyAction(Action):
    """Never needs approval -- exercises the READ_ONLY short-circuit."""

    name = "peek"
    description = "Read-only action (test fixture)."
    risk_tier = RiskTier.READ_ONLY
    expected_result = "output is 'peeked'"

    def required_parameters(self) -> list[str]:
        return []

    def validate(self, parameters):
        return []

    def run(self, parameters):
        return ExecutionResult(success=True, output="peeked")


class ExplodingAction(Action):
    """Raises an unexpected exception from run() -- proves the Executor
    never lets an action's internal crash escape as a raw traceback."""

    name = "explode"
    description = "Always raises (test fixture)."
    risk_tier = RiskTier.READ_ONLY
    expected_result = "never returns normally"

    def required_parameters(self) -> list[str]:
        return []

    def validate(self, parameters):
        return []

    def run(self, parameters):
        raise RuntimeError("boom: simulated internal action failure")


def make_executor():
    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    executor.register(EchoAction())
    executor.register(ReadOnlyAction())
    executor.register(ExplodingAction())
    return executor, permissions


# ---- successful execution -----------------------------------------------

def test_successful_execution_read_only_needs_no_grant():
    executor, _permissions = make_executor()
    result = executor.execute("peek", {})

    assert result.success
    assert result.output == "peeked"
    assert result.execution_time_seconds >= 0.0


def test_successful_execution_reversible_write_with_grant():
    executor, permissions = make_executor()
    permissions.grant(executor.name, "echo", GrantScope.ONCE)

    result = executor.execute("echo", {"value": "hello"})

    assert result.success
    assert result.output == "hello"


# ---- permission denied ---------------------------------------------------

def test_permission_denied_raises_approval_required_without_a_grant():
    executor, _permissions = make_executor()

    with pytest.raises(ApprovalRequired):
        executor.execute("echo", {"value": "hello"})


def test_permission_denied_is_logged_as_blocked_on_approval():
    executor, _permissions = make_executor()

    with pytest.raises(ApprovalRequired):
        executor.execute("echo", {"value": "hello"})

    assert executor.log[-1].status == "blocked_on_approval"
    assert executor.log[-1].action_name == "echo"


def test_once_grant_is_consumed_by_the_executor():
    executor, permissions = make_executor()
    permissions.grant(executor.name, "echo", GrantScope.ONCE)

    first = executor.execute("echo", {"value": "one"})
    assert first.success

    with pytest.raises(ApprovalRequired):
        executor.execute("echo", {"value": "two"})


# ---- invalid parameters ---------------------------------------------------

def test_invalid_parameters_returns_structured_failure_without_touching_permissions():
    executor, _permissions = make_executor()
    # No grant issued at all -- if validation ran after the permission
    # check, this would raise ApprovalRequired instead of returning a
    # structured validation failure. It must not.
    result = executor.execute("echo", {})

    assert not result.success
    assert any("value" in e for e in result.errors)
    assert executor.log[-1].status == "invalid_parameters"
    # No grant was ever issued and none was consumed -- confirmed by the
    # next line: a subsequent valid call still requires its own grant.
    with pytest.raises(ApprovalRequired):
        executor.execute("echo", {"value": "now valid"})


# ---- unknown action ---------------------------------------------------

def test_unknown_action_returns_structured_failure_not_an_exception():
    executor, _permissions = make_executor()
    result = executor.execute("does_not_exist", {})

    assert not result.success
    assert "unknown action" in result.errors[0]
    assert executor.log[-1].status == "unknown_action"


# ---- executor failure propagation ---------------------------------------

def test_action_internal_crash_becomes_a_structured_failure():
    executor, _permissions = make_executor()
    result = executor.execute("explode", {})

    assert not result.success
    assert "executor failure" in result.errors[0]
    assert "boom" in result.errors[0]
    # Never a raw traceback -- just the exception's message.
    assert "Traceback" not in result.errors[0]
    assert executor.log[-1].status == "failed"


# ---- logging ---------------------------------------------------------------

def test_every_execution_is_logged_with_required_fields():
    executor, permissions = make_executor()
    permissions.grant(executor.name, "echo", GrantScope.ONCE)

    executor.execute("echo", {"value": "hi"})

    entry = executor.log[-1]
    assert entry.action_name == "echo"
    assert entry.status == "success"
    assert entry.started_at <= entry.ended_at
    assert entry.duration_seconds >= 0.0


def test_log_accumulates_across_multiple_executions():
    executor, _permissions = make_executor()
    executor.execute("peek", {})
    executor.execute("peek", {})
    executor.execute("does_not_exist", {})

    assert len(executor.log) == 3
    assert [e.action_name for e in executor.log] == ["peek", "peek", "does_not_exist"]


def test_log_property_returns_a_copy_not_the_live_list():
    executor, _permissions = make_executor()
    executor.execute("peek", {})

    snapshot = executor.log
    snapshot.append("tampered")

    assert len(executor.log) == 1


# ---- action registry -------------------------------------------------------

def test_registering_the_same_action_name_twice_raises():
    executor, _permissions = make_executor()
    with pytest.raises(ValueError):
        executor.register(EchoAction())
