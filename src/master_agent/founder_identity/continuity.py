"""`ConversationContinuity` — "Continue" means continue. No re-introduction. C29.

*"Founder may say Continue. Somesh understands: continue previous
discussion. No explanation. No re-introduction."* This module recognises
that one class of founder utterance and answers it with an acknowledgement
short enough to carry no new information — it does not summarise the
prior discussion, does not repeat it, and does not ask what "continue"
refers to. Recognising *that* a request is a continuation is all it does;
resuming the discussion itself belongs to whatever produced the original
discussion, not to this module, which reaches no further than
`FounderSession`'s own tail.
"""
from __future__ import annotations

from master_agent.founder_identity.session import FounderSession

#: Utterances the brief's own example covers, plus its ordinary synonyms.
#: Closed rather than fuzzy-matched — a continuation is a specific,
#: recognisable request, and guessing at looser phrasing risks treating an
#: unrelated founder sentence as one.
_CONTINUATION_PHRASES: tuple[str, ...] = (
    "continue",
    "keep going",
    "carry on",
    "go on",
    "pick up where we left off",
    "resume",
)


def is_continuation_request(text: str) -> bool:
    """Whether this utterance asks Somesh to resume, not restate."""
    lowered = text.strip().lower().rstrip(".!")
    return lowered in _CONTINUATION_PHRASES


def continuity_reply(session: FounderSession) -> str:
    """The whole reply to a continuation request: an acknowledgement, and
    nothing that re-explains what came before.

    `session` is read for one fact only — whether there is anything to
    continue — never to compose a summary of it. A founder asking to
    continue with nothing yet said is told so honestly rather than met
    with an acknowledgement that implies a discussion that never happened.
    """
    if not isinstance(session, FounderSession):
        raise TypeError("continuity_reply takes a FounderSession")

    if not session.active:
        return "There's nothing to continue yet — we haven't started."
    return "Continuing."
