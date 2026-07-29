"""Approval gates for tests (not a test module) — MB028.0.

The Runtime fails closed: with no `ApprovalGate` wired it executes
nothing. That is the point of MB028.0, and it means every test that
drives the Runtime must now say, explicitly, whether the founder approved.
Saying so out loud in each test is the fix being visible — before
MB028.0, none of these tests could tell you whether approval had happened,
because nothing asked.

`ApprovingGate` stands in for a founder who said yes. It is deliberately
**not** shipped in `runtime/`: an "allow everything" gate in production
code is a footgun that would eventually get wired by accident, which is
precisely the class of mistake MB028.0 exists to make impossible.
"""
from __future__ import annotations

from master_agent.runtime.approval import ApprovalDenied, ApprovalRequest


class ApprovingGate:
    """A founder who approved. Records what it was asked, so a test can
    assert the boundary was consulted rather than merely not-blocking."""

    def __init__(self) -> None:
        self.requests: list[ApprovalRequest] = []

    def check(self, request: ApprovalRequest) -> None:
        self.requests.append(request)

    @property
    def capabilities(self) -> list[str]:
        return [request.qualified_capability for request in self.requests]


class RefusingGate:
    """A founder who has not approved, or said no."""

    def __init__(self, reason: str = "founder approval required") -> None:
        self.requests: list[ApprovalRequest] = []
        self._reason = reason

    def check(self, request: ApprovalRequest) -> None:
        self.requests.append(request)
        raise ApprovalDenied(request, self._reason)
