"""Questions about Kalpavriksha, answered from Kalpavriksha's own records.

## Why this exists

A founder asked *"What can you do right now?"* and the system tried to
answer it by asking a **provider** — with the last mission's contents
attached as grounding. `Reasoning.Transform` defaults to
`sensitive=True`, correctly, because its context is normally private
founder material; the Broker then found no PRIVATE-locality provider
available and the question failed outright.

Every layer behaved correctly. The mistake was upstream of all of them:
*none of these questions needed a provider.* What this machine can do,
which providers are usable, why a capability was chosen, whether the last
mission satisfied the request — all four are facts the system already
holds. ADR-0026 and the brief say so plainly: no mission is created to
read what Shared Infrastructure already knows.

Answering them here is not an optimisation. It removes three failure
modes at once — the sensitivity block, the latency, and the possibility
of a model inventing a reason that sounds right.

## What it will not do

It answers only what the records answer. A question the records cannot
settle returns `None`, and the ordinary reasoning path handles it with
its careful default intact. Nothing here lowers sensitivity, and nothing
here composes a fact.
"""
from __future__ import annotations

from typing import Any

#: What a founder question about this system can be about. Closed, like
#: every other vocabulary here: an open one drifts, and each member below
#: corresponds to records that actually exist.
CAPABILITIES = "capabilities"
PROVIDERS = "providers"
PLAN_RATIONALE = "plan_rationale"
OUTCOME = "outcome"
OTHER = "other"

QUESTION_SUBJECTS: tuple[str, ...] = (
    CAPABILITIES, PROVIDERS, PLAN_RATIONALE, OUTCOME, OTHER
)


def answer(subject: str, *, capabilities: Any = None, providers: Any = None,
           record: Any = None, conformance: Any = None) -> str:
    """The answer to a question of this subject, or `""`.

    Every caller passes facts it already has. Nothing is fetched here and
    nothing is judged: this turns records into a sentence a founder can
    read, and returns nothing when the records do not answer.
    """
    if subject == CAPABILITIES:
        return _capabilities(capabilities)
    if subject == PROVIDERS:
        return _providers(providers)
    if subject == PLAN_RATIONALE:
        return _rationale(record)
    if subject == OUTCOME:
        return _outcome(record, conformance)
    return ""


def _capabilities(rows: Any) -> str:
    """What this machine can do, by domain, from the live index.

    Domains rather than a dump of forty-eight primitive names: a founder
    asking what it can do wants to know the shape of its reach, and a
    list of `Filesystem.AppendFile`-style identifiers answers a different
    question than the one they asked. The count is included because it is
    the fact that makes the summary checkable.
    """
    by_domain: dict[str, list[str]] = {}
    for entry in rows or ():
        domain = str(getattr(entry, "domain", "") or "other")
        by_domain.setdefault(domain, []).append(str(getattr(entry, "canonical_id", "")))
    if not by_domain:
        return ""

    described = {
        "filesystem": "work with files and folders",
        "browser": "drive a browser — open pages, fill forms, read what is on them",
        "desktop": "operate applications on this machine",
        "document": "read and write documents",
        "reasoning": "think about something and produce text",
    }
    lines = [
        f"Right now I have {sum(len(v) for v in by_domain.values())} registered "
        f"capabilities across {len(by_domain)} areas:"
    ]
    for domain in sorted(by_domain):
        summary = described.get(domain, f"work in the {domain} area")
        lines.append(f"  • {domain} — {summary} ({len(by_domain[domain])} capabilities)")
    lines.append(
        "Ask me for any of it in your own words; I'll tell you if I can't."
    )
    return "\n".join(lines)


def _providers(rows: Any) -> str:
    """Which reasoning providers are actually usable.

    KNOWN is not USABLE, and the difference is the whole answer. A
    provider can be registered, configured and completely unable to run —
    no binary, no credential, an application that is not open. Naming one
    as available would be a promise this machine cannot keep.
    """
    usable, known = [], []
    for row in rows or ():
        name = str(getattr(row, "provider_id", "") or "")
        if not name:
            continue
        known.append(name)
        if getattr(row, "available", False):
            usable.append(name)
    if not known:
        return ""
    lines = [
        f"I know of {len(known)} reasoning providers, and {len(usable)} "
        f"can actually be used right now."
    ]
    if usable:
        lines.append("  usable now: " + ", ".join(sorted(usable)))
    unusable = sorted(set(known) - set(usable))
    if unusable:
        lines.append("  known but not usable now: " + ", ".join(unusable))
    lines.append(
        "I don't choose between them — the Broker does, on cost, locality "
        "and quality, and it records why."
    )
    return "\n".join(lines)


def _rationale(record: Any) -> str:
    """Why the capabilities in the last mission were chosen.

    Read from what was recorded at planning time. A model asked this
    afterwards would produce a plausible reason, and a plausible reason
    is indistinguishable from the real one exactly when it is wrong.
    """
    steps = list(getattr(record, "steps", ()) or ())
    reasons = [
        (str(getattr(s, "capability", "")), str(getattr(s, "selection_reason", "")))
        for s in steps
    ]
    reasons = [(cap, why) for cap, why in reasons if why]
    if not reasons:
        return ""
    objective = str(getattr(record, "objective", "") or "your last request")
    lines = [f'For "{objective}" I chose:']
    for capability, why in reasons:
        lines.append(f"  • {capability}")
        lines.append(f"    {why}")
    lines.append(
        "That reason was recorded when the plan was made, not composed now."
    )
    return "\n".join(lines)


def _outcome(record: Any, conformance: Any) -> str:
    """Whether the last mission satisfied what was asked.

    Grounded in the requirements, what covered them, and what
    Verification independently observed. `UNKNOWN` is never rounded up to
    done — a mission the machine cannot vouch for is one it says so
    about.
    """
    if conformance is None:
        return ""
    objective = str(getattr(record, "objective", "") or "your last request")
    state = str(getattr(conformance, "state", "") or "")
    rows = list(getattr(conformance, "requirements", ()) or ())

    opening = {
        "satisfied": f'Yes. "{objective}" did what you asked.',
        "not_satisfied": f'No. "{objective}" did not do everything you asked.',
        "unknown": (
            f'I can\'t say for certain. "{objective}" ran, but I don\'t have '
            f"enough independent evidence to confirm it."
        ),
    }.get(state)
    if opening is None:
        return ""

    lines = [opening, "", "What you asked for, and what was observed:"]
    for row in rows:
        mark = {"satisfied": "verified", "not_satisfied": "NOT met",
                "unknown": "not confirmed"}.get(row.state, row.state)
        lines.append(f"  • {row.description} — {mark}")
    lines.append("")
    lines.append(
        "Each of those was checked by looking at reality again, not by "
        "trusting what the step reported about itself."
    )
    return "\n".join(lines)
