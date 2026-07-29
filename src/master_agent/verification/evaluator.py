"""Pure functions that turn an Observation dict + a list of ObservationChecks
into a Verdict. No I/O, no Environment access, no Worker-specific knowledge
— this is what makes it reusable by every future Verifier unchanged. See
BROWSER_WORKER_ARCHITECTURE.md §8.
"""
from __future__ import annotations

import re
from typing import Any

from master_agent.verification.evidence import CheckResult, ObservationCheck, Verdict

_MISSING = object()


def get_field(observation: dict[str, Any], field_path: str) -> tuple[bool, Any]:
    """Dot-path lookup into a nested dict/list structure, e.g. "url" or
    "elements.0.text". Returns (found, value) rather than raising — a
    missing path is a normal, expected outcome for a check to report, not
    a programming error."""
    current: Any = observation
    for part in field_path.split("."):
        if isinstance(current, dict):
            current = current.get(part, _MISSING)
        elif isinstance(current, list):
            try:
                index = int(part)
            except ValueError:
                return False, None
            current = current[index] if 0 <= index < len(current) else _MISSING
        else:
            return False, None
        if current is _MISSING:
            return False, None
    return True, current


def evaluate_check(observation: dict[str, Any], check: ObservationCheck) -> CheckResult:
    found, actual = get_field(observation, check.field)

    if check.operator == "exists":
        return CheckResult(check=check, passed=found, actual_value=actual if found else None)

    if not found:
        return CheckResult(
            check=check,
            passed=False,
            actual_value=None,
            error=f"field '{check.field}' not present in observation",
        )

    if check.operator == "equals":
        passed = actual == check.value
    elif check.operator == "contains":
        passed = check.value in actual if actual is not None else False
    elif check.operator == "not_contains":
        passed = check.value not in actual if actual is not None else True
    elif check.operator == "matches_regex":
        passed = bool(re.search(str(check.value), str(actual)))
    else:
        return CheckResult(
            check=check,
            passed=False,
            actual_value=actual,
            error=f"unknown operator: '{check.operator}'",
        )

    return CheckResult(check=check, passed=passed, actual_value=actual)


def evaluate_checks(
    observation: dict[str, Any], checks: list[ObservationCheck]
) -> tuple[Verdict, list[CheckResult]]:
    """An ExpectedOutcome with no checks at all can never be verified —
    treated as Verdict.ERROR (a design mistake in whoever built the Step),
    never as a silent pass. This mirrors ARCHITECTURE constitution §10.2's
    "do not allow execution success to imply mission success": an empty
    checks list must not default to MATCHED."""
    if not checks:
        return Verdict.ERROR, []

    results = [evaluate_check(observation, check) for check in checks]
    passed_count = sum(1 for result in results if result.passed)

    if passed_count == len(results):
        return Verdict.MATCHED, results
    if passed_count == 0:
        return Verdict.NOT_MATCHED, results
    return Verdict.PARTIALLY_MATCHED, results
