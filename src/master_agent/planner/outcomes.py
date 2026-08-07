"""Turning a planned Step's stated success into an `ExpectedOutcome`
(Mission Brief 036).

MB035 built the checker and left the question of who states the
expectation. This is the answer: the Planner says, per Step, what a good
result looks like, in a **closed vocabulary it can validate before the
Step ever runs**.

## Why a closed vocabulary rather than raw `ObservationCheck`s

`ObservationCheck.field` is a dot-path into whatever observation dict a
Worker produces. Letting a provider write those directly would let it
invent `folder.exists_after` against a Verifier that observes no such
thing -- a check that can never fail, which is worse than no check,
because it reports as verified forever.

So a provider gets six keys, every one of which maps onto a check MB035
already builds and `observe()` already produces a field for. An
expectation the Planner emits is therefore always evaluable. Where a
Worker grows a richer observation later, the `ExpectedOutcome` contract
already carries arbitrary checks -- this module is a constraint on what
the *Planner* invents, not on what the contract permits.

## The limit, stated rather than hidden

These checks are structural and they are over **text**: what a Step's
result says. They catch a blank result, a refusal, a truncation, a wrong
shape. They cannot catch a Step that reports success and did the wrong
thing. That is the semantic gap ADR-0017 Decision 5 named and MB035
inherited; MB036 does not close it either, and a Step whose expectation
passes is *checked*, not *correct*.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from master_agent.ai_infrastructure.text_verifier import expect
from master_agent.verification.evidence import ExpectedOutcome

#: The only keys a provider may use inside a Step's `success` object.
#: Anything else is a malformed plan rather than a silently dropped key --
#: see `from_document`.
SUCCESS_KEYS = frozenset(
    {
        "description",
        "must_contain",
        "must_exclude",
        "must_be_json",
        "must_have_fields",
        "min_words",
    }
)


@dataclass(frozen=True)
class SuccessSpec:
    """What one Step promises its result will look like."""

    description: str
    must_contain: tuple[str, ...] = ()
    must_exclude: tuple[str, ...] = ()
    must_be_json: bool = False
    must_have_fields: tuple[str, ...] = ()
    min_words: int = 0

    def to_expected_outcome(self) -> ExpectedOutcome:
        """Delegate to MB035's builder rather than assembling checks here.

        There is exactly one place that knows how a text check is spelled,
        and it is the module that also knows how the text is observed. A
        second assembler would drift from it the first time `observe()`
        gains a field.
        """
        return expect(
            description=self.description,
            contains_all=self.must_contain,
            excludes_all=self.must_exclude,
            json_body=self.must_be_json,
            json_fields=self.must_have_fields,
            min_words=self.min_words,
            # Always on: a Step whose only stated expectation is "not
            # blank" is a weak check, but an `ExpectedOutcome` with no
            # checks at all evaluates to ERROR under the frozen evaluator
            # (MB035), and emitting one would mean the Planner produced a
            # Step that can never be verified.
            require_non_empty=True,
        )


class MalformedSuccess(ValueError):
    """The `success` object was not usable. Carries the sentence a founder
    reads, so the caller does not compose a second one."""


def _string_list(value: Any, key: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        # A provider writing `"must_contain": "created"` meant a list of
        # one. Accepting it is not guesswork -- there is exactly one
        # reading -- and refusing would fail a plan over punctuation.
        value = [value]
    if not isinstance(value, list):
        raise MalformedSuccess(f"`{key}` must be a list of strings")
    out = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise MalformedSuccess(f"`{key}` must contain non-empty strings")
        out.append(item)
    return tuple(out)


def from_document(document: Any, *, step_id: str) -> SuccessSpec:
    """Read one Step's `success` object out of the parsed plan.

    Raises `MalformedSuccess` rather than substituting a default. A Step
    whose expectation could not be read must fail the plan: quietly giving
    it "the answer is not blank" would manufacture a check nobody stated,
    and MB035's whole argument is that a check invented after the fact is
    a rationalisation.
    """
    if not isinstance(document, dict):
        raise MalformedSuccess(f"step `{step_id}` has no `success` object")

    unknown = sorted(set(document) - SUCCESS_KEYS)
    if unknown:
        raise MalformedSuccess(
            f"step `{step_id}` states unsupported success key(s): "
            + ", ".join(unknown)
            + "; supported: "
            + ", ".join(sorted(SUCCESS_KEYS))
        )

    description = document.get("description", "")
    if not isinstance(description, str) or not description.strip():
        raise MalformedSuccess(
            f"step `{step_id}` must describe what success looks like"
        )

    must_be_json = document.get("must_be_json", False)
    if not isinstance(must_be_json, bool):
        raise MalformedSuccess(f"step `{step_id}`: `must_be_json` must be true or false")

    min_words = document.get("min_words", 0)
    # `bool` is an `int` in Python, and `"min_words": true` is a mistake
    # that would otherwise silently become 1.
    if isinstance(min_words, bool) or not isinstance(min_words, int) or min_words < 0:
        raise MalformedSuccess(
            f"step `{step_id}`: `min_words` must be a whole number, 0 or more"
        )

    return SuccessSpec(
        description=description.strip(),
        must_contain=_string_list(document.get("must_contain"), "must_contain"),
        must_exclude=_string_list(document.get("must_exclude"), "must_exclude"),
        must_be_json=must_be_json,
        must_have_fields=_string_list(document.get("must_have_fields"), "must_have_fields"),
        min_words=min_words,
    )
