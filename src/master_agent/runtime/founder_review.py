"""The pause a founder asked for, which is not a permission question.

Two different things need the same waiting machinery and must never be
confused for one another.

The **approval boundary** asks whether policy permits an action:
something destructive, something that costs money, private material
leaving the machine. Answering yes can create real Permission System
authority.

A **founder review** is not policy at all. The objective said *"show me
what you propose before you change it"*, so the founder is looking at what
the work produced. Answering Continue satisfies that request and nothing
else: no capability is authorised, no risk tier moves, and the Permission
System is neither consulted nor altered. A step that is also policy-gated
still meets the approval boundary separately, on its own terms.

The founder's words are `Continue` and `Stop`, not `Approve` and
`Reject`, because they are not being asked to permit anything. They are
being shown something they asked to see.

Named `founder_review` rather than `checkpoint`: `runtime/checkpoint.py`
has meant "saved runtime state for resume" since MB025, and one word for
two unrelated ideas in the same package is how a reader ends up restoring
a mission from a founder's question.

The exceptions mirror `runtime/approval.py`'s pair deliberately -- same
shape, same reason. Pending is an open question and the task waits;
stopped is a decision and the task does not run.
"""
from __future__ import annotations

from typing import Any


class ReviewPending(Exception):
    """The founder has been shown the proposal and has not answered yet.

    Not a failure. The task keeps its state and the gate is re-consulted
    next cycle, so Continue resumes the same work with no restart.
    """

    def __init__(self, task_id: str, approval_id: str, preview: str) -> None:
        super().__init__(f"awaiting founder review ({approval_id})")
        self.task_id = task_id
        self.approval_id = approval_id
        self.preview = preview


class ReviewStopped(Exception):
    """The founder looked and said Stop.

    A real decision, and the reviewed action does not happen. Not a fault
    in the work -- the mission did exactly what it was asked to do, which
    was to check first.
    """

    def __init__(self, task_id: str, approval_id: str, note: str = "") -> None:
        super().__init__("the founder chose to stop at the review they asked for")
        self.task_id = task_id
        self.approval_id = approval_id
        self.note = note


#: How much of a resolved value the founder is shown per argument. Long
#: enough to read a proposal, short enough that a chat bubble stays one.
MAX_VALUE_CHARS = 4_000

#: Arguments not worth showing. A preview exists so the founder can judge
#: the proposal, and plumbing does not help them judge anything.
_UNINTERESTING = frozenset({"session_id", "timeout_ms", "overwrite", "sensitive"})


def preview_of(payload: dict[str, Any] | None) -> str:
    """What the founder reads, built from the RESOLVED payload.

    From the values that will actually execute -- the same dict that goes
    on to `gateway.invoke` -- so the proposal reviewed is the proposal
    carried out. Never the Planner's literal, which for a bound argument
    does not exist at all.

    The step's own `founder_checkpoint` text is deliberately not used
    here: that says *why* the founder is being asked, and this is *what*
    they are being asked about.

    Bounded and plain. Not a JSON dump: a founder reading `{"content":
    "..."}` is reading our plumbing, and a payload can carry more than
    anyone wants pasted into a conversation.
    """
    if not payload:
        return ""
    parts: list[str] = []
    for name in sorted(payload):
        if name in _UNINTERESTING:
            continue
        value = payload[name]
        if value is None:
            continue
        text = value if isinstance(value, str) else str(value)
        if not text.strip():
            continue
        if len(text) > MAX_VALUE_CHARS:
            text = text[:MAX_VALUE_CHARS].rstrip() + "\n… (shortened)"
        parts.append(f"{name}:\n{text}" if "\n" in text else f"{name}: {text}")
    return "\n\n".join(parts)
