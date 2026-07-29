"""The Verifier contract — see KALPAVRIKSHA_VISION_V2.md §10 and ADR-0011.

Execution produces effects. Verification produces Evidence. This class is
what keeps the two structurally independent: `verify()` never looks at an
ExecutionResult, never trusts a Worker's own claim that something
succeeded — it always re-observes reality fresh (via the subclass's
`capture_observation_dict()`) and compares that fresh observation against
an ExpectedOutcome the caller supplies. A Worker whose Action has a bug
that makes it silently no-op will still get an honest NOT_MATCHED Verdict,
because Verification never asks the Action whether it thinks it worked.

Concrete subclasses (BrowserVerifier is the first) implement exactly one
method. Everything else — building the Evidence record, handling an
observation that fails to capture at all, computing the Verdict — is
shared here, so a second Worker's Verifier is a handful of lines, not a
reimplementation.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from master_agent.verification.evaluator import evaluate_checks
from master_agent.verification.evidence import Evidence, ExpectedOutcome, Verdict


class Verifier(ABC):
    worker_name: str
    environment_name: str

    @abstractmethod
    def capture_observation_dict(self) -> dict[str, Any]:
        """Re-observe current real-world state fresh and return a generic,
        JSON-shaped dict view of it. Must never return a cached value from
        a prior Execution — that would silently reintroduce the
        Execution-implies-success coupling this class exists to prevent.
        """

    def verify(self, expected: ExpectedOutcome) -> Evidence:
        try:
            observation = self.capture_observation_dict()
        except Exception as exc:  # noqa: BLE001 — deliberate: a failed observation is
            # Evidence (Verdict.ERROR), never an exception escaping to the caller.
            return Evidence(
                evidence_id=str(uuid4()),
                worker=self.worker_name,
                environment=self.environment_name,
                captured_at=datetime.now(UTC),
                expected=expected,
                observation={},
                verdict=Verdict.ERROR,
                check_results=[],
                errors=[f"observation failed: {exc}"],
            )

        verdict, check_results = evaluate_checks(observation, expected.checks)
        return Evidence(
            evidence_id=str(uuid4()),
            worker=self.worker_name,
            environment=self.environment_name,
            captured_at=datetime.now(UTC),
            expected=expected,
            observation=observation,
            verdict=verdict,
            check_results=check_results,
        )
