"""Where reasoning material came from decides how it may be handled.

## The defect

`Reasoning.Transform` defaults to `sensitive=True`, correctly: its
context is normally an earlier Step's output, and treating a founder's
own document as unrestricted would post it to whichever cloud provider
ranked first.

But the default described the CAPABILITY rather than the material. A
research mission that read three public web pages was refused with

    11 provider(s) considered, none eligible: excluded by the request;
    sensitive work may not go to a third party

for material that was never private. Public information does not become
private because `Reasoning.Transform` touched it.

## The rule, in both directions

The dangerous half is the other one, and it is why this exists as
deterministic provenance rather than as a parameter. `sensitive` arrives
in the plan PAYLOAD, so a model could write `"sensitive": false` over a
founder's private file and the request would go out. **Model-generated
output may never lower sensitivity.** Only what the material actually
came from may.

    public  + public   -> public
    public  + private  -> private
    anything unknown   -> unchanged, so the conservative default stands

Raising is always allowed. Lowering requires that every bound source be
known-public.

## Why here

`resolve_inputs` already knows every source task a bound value came from
-- it builds `provenance` from exactly that. It has the information and
the authority, and it runs after planning, so nothing a model writes can
reach past it.
"""
from __future__ import annotations

from typing import Any

#: Capabilities whose output is material the founder has published to
#: nobody -- their disk, their clipboard, their desktop, their
#: authenticated sessions.
#:
#: Named by DOMAIN rather than by listing every capability, so a
#: capability added to one of these families is private on the day it is
#: written rather than on the day somebody remembers to add it here.
_PRIVATE_DOMAINS: tuple[str, ...] = (
    "filesystem", "document", "desktop", "clipboard", "memory", "knowledge",
)

#: Capabilities that read the ordinary, unauthenticated public web.
#:
#: The Browser Executive's lane is anonymous by construction -- a fresh
#: automated context with none of the founder's sessions. That is what
#: makes its output public, and it is also why the TRUSTED browser is not
#: here: that one carries the founder's signed-in identity, and anything
#: it sees is theirs.
_PUBLIC_DOMAINS: tuple[str, ...] = ("browser",)

#: Reasoning inherits from whatever it was given, so it belongs to
#: neither list: a summary of a private file is private, a summary of a
#: public page is not.
PUBLIC = "public"
PRIVATE = "private"
UNKNOWN = "unknown"


def classify(capability: str) -> str:
    """What kind of material this capability's output is."""
    name = str(capability or "").strip().lower()
    if not name:
        return UNKNOWN
    domain = name.split(".", 1)[0]
    if domain in _PRIVATE_DOMAINS:
        return PRIVATE
    # The trusted lane is the founder's own signed-in browser, and its
    # material is theirs however much it looks like an ordinary page.
    if "trusted" in name:
        return PRIVATE
    if domain in _PUBLIC_DOMAINS:
        return PUBLIC
    return UNKNOWN


def derive(
    sources: list[str],
    declared: Any = None,
    *,
    intent_sensitive: bool | None = None,
) -> bool | None:
    """The sensitivity this invocation should actually run under.

    `sources` are the capabilities of the steps whose output was bound
    into this one. `declared` is whatever the plan said, which is the
    thing being checked rather than trusted.

    Returns `None` when there is nothing to say -- no bound sources, or
    sources this module does not recognise -- and the caller then leaves
    the existing conservative default alone.
    """
    if intent_sensitive is True:
        # Founder meaning is authoritative. Neither a model-authored
        # payload nor apparently public inputs may lower it.
        return True
    if not sources:
        # With no material inputs, the canonical Intent is the only
        # provenance available.  ``None`` preserves the conservative
        # historical default for callers that have not projected it yet.
        return False if intent_sensitive is False else (True if declared is True else None)

    kinds = {classify(source) for source in sources}
    if PRIVATE in kinds:
        # The join rule. One private input makes the whole invocation
        # private, whatever the plan claimed.
        return True
    if UNKNOWN in kinds:
        # With no declaration and no Intent projection, ``None`` retains
        # the action's conservative default.  Any explicit model claim or
        # projected Intent is insufficient to certify unknown material as
        # public, so execution is stamped sensitive.
        return (
            None
            if declared is None and intent_sensitive is None
            else True
        )
    if declared is True and intent_sensitive is None:
        # A legacy caller that did not project Intent may still raise the
        # classification. Only an authoritative public Intent plus wholly
        # public provenance may relax that conservative guess.
        return True
    return False


def apply_to(
    payload: dict[str, Any],
    sources: list[str],
    *,
    intent_sensitive: bool | None = None,
) -> dict[str, Any]:
    """Stamp the derived sensitivity onto a resolved payload.

    Mutates and returns the payload it was given, which is execution
    material -- never the persisted plan. What the Planner decided stays
    what the Planner decided; what runs is what provenance allows.
    """
    if "sensitive" not in payload and not sources and intent_sensitive is None:
        return payload
    derived = derive(
        sources,
        payload.get("sensitive"),
        intent_sensitive=intent_sensitive,
    )
    if derived is not None:
        payload["sensitive"] = derived
    return payload
