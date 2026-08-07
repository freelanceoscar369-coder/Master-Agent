"""Verifying generated text (Mission Brief 035).

MB033 shipped a Prompt Cache that never hits and MB034 shipped a Prompt
Library with no automatic writer. Both were blocked on the same missing
piece: *nothing in Kalpavriksha could tell whether a generated answer was
any good.* ADR-0011 froze the Verification Subsystem years of briefs ago
and `BrowserVerifier` proved it generalises; this is the second Verifier,
and it is a handful of lines because of that.

**It lives here rather than in `verification/`** because that package has
been frozen since MB025 and adding a file to it would show up in the
guard diff with no ratified ADR permitting it. Nothing frozen is touched:
this imports the published contracts (`Verifier`, `ExpectedOutcome`,
`ObservationCheck`, `Evidence`) and implements the one abstract method,
exactly as a Worker outside `verification/` is expected to.

## The one interpretation this brief had to make

`Verifier.capture_observation_dict()` says: *re-observe current
real-world state fresh; never return a cached value from a prior
Execution.* For a browser that means reading the page again. For
generated text there is no page — **the answer is the artefact**.

The honest reading, and the one taken here: re-derive the observation
from the artefact by deterministic measurement, every time, and never
consult anybody's *opinion* of it. So the observation is length, word
count, whether it parses as JSON, what it contains — facts a second
reader could check — and the provider is never asked whether it thinks it
did well. That is the coupling ADR-0011 exists to prevent, stated for a
medium it did not originally have in mind.

## What this deliberately is not

**No model judges another model.** Asking an LLM whether an LLM's answer
was good needs an LLM to judge *that*, and something has to break the
recursion — ADR-0017 refused to start it for provider selection and
MB034 refused it for memory. A verdict here is arithmetic over an
`ExpectedOutcome` the caller stated in advance, which is also the only
kind of verdict that is falsifiable.

**No new operators.** The five in `verification/evaluator.py` —
`equals`, `contains`, `not_contains`, `exists`, `matches_regex` — express
everything below. A sixth would mean editing a frozen file to save
writing a regex.
"""
from __future__ import annotations

import json
from typing import Any

from master_agent.verification.evidence import (
    Evidence,
    ExpectedOutcome,
    ObservationCheck,
    Verdict,
)
from master_agent.verification.verifier import Verifier

VERIFIER_NAME = "text"
#: The "environment" this Verifier observes. Not a browser and not a
#: filesystem -- the artefact itself, which is why the name says so.
ENVIRONMENT = "generated_text"

#: How much of the text the observation keeps for a `contains` check.
#: Generous, because truncating the thing under test would make a check
#: pass or fail on where the cut fell.
MAX_OBSERVED = 100_000


def observe(text: str) -> dict[str, Any]:
    """A factual, JSON-shaped view of some generated text.

    Every field is something a second reader could recompute from the same
    string. Nothing here is an opinion, a score, or a claim by whoever
    produced it.

    `json` is present only when the text really parses, so a check on
    `json.name` fails honestly on prose rather than matching nothing in
    particular.
    """
    raw = text if isinstance(text, str) else ""
    clipped = raw[:MAX_OBSERVED]
    stripped = clipped.strip()
    lines = [line for line in clipped.splitlines() if line.strip()]

    observation: dict[str, Any] = {
        "text": clipped,
        # Lower-cased and whitespace-collapsed, so a `contains` check can be
        # written without the caller having to guess the model's casing or
        # line breaks.
        "normalised": " ".join(clipped.lower().split()),
        "empty": not stripped,
        "length": len(stripped),
        "word_count": len(stripped.split()),
        "line_count": len(lines),
        "first_line": lines[0].strip() if lines else "",
        "last_line": lines[-1].strip() if lines else "",
        "truncated": len(raw) > MAX_OBSERVED,
    }

    parsed, ok = _as_json(stripped)
    observation["is_json"] = ok
    if ok:
        observation["json"] = parsed
    return observation


def _as_json(text: str) -> tuple[Any, bool]:
    """Parsed JSON and whether it parsed. A fenced block is unwrapped
    first, because a model asked for JSON very often returns it inside
    ```json ... ``` and refusing that would be pedantry rather than
    verification."""
    if not text:
        return None, False
    candidate = text
    if candidate.startswith("```"):
        without_fence = candidate.split("\n", 1)[-1]
        candidate = without_fence.rsplit("```", 1)[0].strip()
    try:
        return json.loads(candidate), True
    except (ValueError, TypeError):
        return None, False


class TextVerifier(Verifier):
    """The second concrete `Verifier`. One method, as ADR-0011 intended.

    Constructed with the artefact rather than a way of fetching it,
    because for generated text there is nothing to fetch — see the module
    docstring. The observation is still recomputed on every `verify()`
    call rather than stored, so a verdict is always derived from the text
    in hand and never from a previous judgement of it.
    """

    worker_name = VERIFIER_NAME
    environment_name = ENVIRONMENT

    def __init__(self, text: str, worker: str = VERIFIER_NAME) -> None:
        self._text = text
        self.worker_name = worker

    def capture_observation_dict(self) -> dict[str, Any]:
        return observe(self._text)


def verify_text(
    text: str, expected: ExpectedOutcome, worker: str = VERIFIER_NAME
) -> Evidence:
    """Judge one answer against what was asked for. Returns `Evidence`,
    never a bare verdict — the checks and what they actually saw travel
    with it, so "why did that fail?" is answerable from the record."""
    return TextVerifier(text, worker=worker).verify(expected)


# ---- check builders ------------------------------------------------------
#
# Sugar over `ObservationCheck`, so a caller states what it wants in the
# vocabulary of text rather than in dot-paths and operator strings. Each
# one is a plain function returning the frozen shape -- nothing here is a
# new contract.


def not_empty() -> ObservationCheck:
    return ObservationCheck(
        field="empty",
        operator="equals",
        value=False,
        description="the answer is not blank",
    )


def contains(phrase: str) -> ObservationCheck:
    """Case- and whitespace-insensitive, because a model that answers
    "Blue." when asked for "blue" has answered."""
    return ObservationCheck(
        field="normalised",
        operator="contains",
        value=" ".join(str(phrase).lower().split()),
        description=f"mentions {phrase!r}",
    )


def excludes(phrase: str) -> ObservationCheck:
    return ObservationCheck(
        field="normalised",
        operator="not_contains",
        value=" ".join(str(phrase).lower().split()),
        description=f"does not mention {phrase!r}",
    )


def matches(pattern: str) -> ObservationCheck:
    return ObservationCheck(
        field="text",
        operator="matches_regex",
        value=pattern,
        description=f"matches /{pattern}/",
    )


def is_json() -> ObservationCheck:
    return ObservationCheck(
        field="is_json",
        operator="equals",
        value=True,
        description="the answer parses as JSON",
    )


def json_has(path: str) -> ObservationCheck:
    """A field inside the parsed JSON, by dot-path — `get_field` already
    walks dicts and lists, so `json.items.0.name` works with no new
    machinery."""
    return ObservationCheck(
        field=f"json.{path}",
        operator="exists",
        value=None,
        description=f"the JSON has {path!r}",
    )


def json_equals(path: str, value: Any) -> ObservationCheck:
    return ObservationCheck(
        field=f"json.{path}",
        operator="equals",
        value=value,
        description=f"JSON {path!r} is {value!r}",
    )


def at_least_words(count: int) -> ObservationCheck:
    """Expressed as a regex over the text rather than as a new `>=`
    operator, because adding one would mean editing a frozen file to save
    writing this line.

    The final `\\S+` is load-bearing. The first version ended in `\\S*`,
    which matches the empty string — so "at least 1 word" passed on a
    blank answer, which is precisely the silent pass this subsystem exists
    to prevent.
    """
    required = max(1, count)
    return ObservationCheck(
        field="text",
        operator="matches_regex",
        value=rf"(?:\S+\s+){{{required - 1}}}\S+",
        description=f"at least {required} word(s)",
    )


def expect(
    description: str = "a usable answer",
    contains_all: tuple[str, ...] | list[str] = (),
    excludes_all: tuple[str, ...] | list[str] = (),
    pattern: str = "",
    json_body: bool = False,
    json_fields: tuple[str, ...] | list[str] = (),
    min_words: int = 0,
    require_non_empty: bool = True,
) -> ExpectedOutcome:
    """Build an `ExpectedOutcome` for text from plain arguments.

    Every check is stated *before* the answer arrives, which is what makes
    the verdict falsifiable rather than a rationalisation of whatever came
    back.

    An outcome with no checks at all is left empty on purpose: the frozen
    evaluator already turns that into `ERROR` rather than a silent pass
    (ADR-0011), and reproducing that rule here would be a second opinion
    about it.
    """
    checks: list[ObservationCheck] = []
    if require_non_empty:
        checks.append(not_empty())
    checks.extend(contains(phrase) for phrase in contains_all)
    checks.extend(excludes(phrase) for phrase in excludes_all)
    if pattern:
        checks.append(matches(pattern))
    if json_body:
        checks.append(is_json())
    checks.extend(json_has(path) for path in json_fields)
    if min_words > 0:
        checks.append(at_least_words(min_words))
    return ExpectedOutcome(description=description, checks=checks)


def passed(evidence: Evidence | None) -> bool:
    """Did this answer earn its way into the cache and the Prompt Library?

    `MATCHED` only. `PARTIALLY_MATCHED` is deliberately not enough: half
    of what was asked for is not what was asked for, and a cache that
    remembered it would serve the same half answer forever.
    """
    return evidence is not None and evidence.verdict is Verdict.MATCHED
