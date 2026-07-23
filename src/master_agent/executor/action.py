"""The Action Contract — the foundation every future local capability
(create/read/rename/delete/copy/move file, run PowerShell/CMD, git,
VS Code, Obsidian, ...) plugs into. See docs/MISSION_BRIEF_002.md for why
this exists and docs/adr/0005-executor-permission-relay.md for how it
interacts with the Permission System.

Deliberately small: name, description, risk tier, required parameters,
a validation step, and a run step. Anything more here makes writing a
new action expensive, which defeats the point of having a contract at
all.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from master_agent.plugins.base import RiskTier


@dataclass
class ExecutionResult:
    """What every action run — and every executor.execute() call —
    returns. `execution_time_seconds` is set by the Executor, not the
    Action itself (the Action doesn't know how long it took; timing is
    the Executor's job, not the action's)."""

    success: bool
    output: Any = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    execution_time_seconds: float = 0.0


class Action(ABC):
    """One executable local action. Implementations declare the contract
    fields as class attributes and implement validate()/run().

    validate() must never touch the filesystem or perform side effects —
    it's a pure check, called before permission is even consulted, so a
    malformed request fails fast without ever bothering the human or the
    Permission System.

    run() performs the actual work. It should not raise for ordinary
    failures — return `ExecutionResult(success=False, errors=[...])`
    instead. The Executor catches anything that escapes anyway (see
    executor.py), but a well-behaved action returns structured failures
    on its own.
    """

    name: str
    description: str
    risk_tier: RiskTier
    expected_result: str

    @abstractmethod
    def required_parameters(self) -> list[str]:
        """Names of parameters this action requires in its payload —
        documentation as much as contract; validate() is what's actually
        enforced."""

    @abstractmethod
    def validate(self, parameters: dict[str, Any]) -> list[str]:
        """Return validation error messages; empty list means valid."""

    @abstractmethod
    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        """Perform the work. Only ever called after validate() passed and
        permission (if the risk tier requires it) was granted."""
