"""Which account out there is the founder's, when a service offers a choice.

`identity.py` holds who the founder is to Kalpavriksha — a name, an
edition, a way of talking. This holds the far narrower fact needed when
an external service asks *"who are you signing in as?"*: the identity the
founder has authorised Kalpavriksha to use on their behalf.

## Why this exists rather than a rule in a provider

`DESKTOP_BROWSER_FINAL_CLOSURE.md` §6 says **"Never choose between
accounts or profiles"**, and it was written from a real measurement: the
founder's own machine offered three Chrome profiles, *two carrying the
same person's name*, so first / order / name-similarity would each have
picked wrong with full confidence.

That rule answers the question *"who is the founder, if nobody has
said?"* — and its answer is "do not guess", which remains correct. It was
never a rule that the founder may not tell us. With an explicit standing
identity, selecting the profile that matches it is not a guess; it is
carrying out a decision already made.

So the reconciliation is:

    no identity configured        -> never choose (unchanged)
    identity configured, one match -> select it, do not ask
    identity configured, several matches -> still ambiguous, still ask

The third line is the one that keeps the original measurement's lesson:
two profiles bearing the same name are *still* two profiles bearing the
same name, and a standing identity does not disambiguate them.

## What is deliberately not here

No password, no session cookie, no access token, no OTP. This is a name
and an address the founder has already made public to themselves; it is
the *criterion* for recognising their account, never the means of
entering it.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FounderWebIdentity:
    """The founder's authorised identity for external free services.

    `paid_usage_authorized` is false and is expected to stay false: it is
    here so that a component asking "may I?" gets an explicit no rather
    than finding no answer at all.
    """

    founder_name: str = ""
    email: str = ""
    may_select_matching_account: bool = True
    may_select_matching_profile: bool = True
    #: Whether the FOUNDER has authorised creating a free account. Note
    #: that authorisation is necessary and not sufficient — an operator
    #: may still be forbidden from performing signups itself.
    may_create_free_account: bool = False
    paid_usage_authorized: bool = False

    @property
    def configured(self) -> bool:
        return bool(self.founder_name.strip() or self.email.strip())

    def terms(self) -> tuple[str, ...]:
        """The strings that would identify this founder's account.

        The email's local part is included because profile choosers
        usually show a display name, not an address, and the two are
        commonly the same word.
        """
        found: list[str] = []
        name = self.founder_name.strip().casefold()
        if name:
            found.append(name)
        email = self.email.strip().casefold()
        if email:
            found.append(email)
            local = email.split("@", 1)[0]
            if local and local not in found:
                found.append(local)
        return tuple(found)

    def matches(self, label: str) -> bool:
        """Does this offered option name the founder's identity?

        Substring, deliberately: a chooser renders `Open Onkar profile`,
        not `Onkar`. Nothing fuzzy — no edit distance, no initials, no
        "closest" — because the failure this must not repeat is picking a
        similar name with confidence.
        """
        if not self.configured:
            return False
        haystack = (label or "").casefold()
        if not haystack:
            return False
        return any(term in haystack for term in self.terms())

    def sole_match(self, labels: tuple[str, ...]) -> int | None:
        """The index of the ONE option that matches, or `None`.

        `None` when nothing matches and — importantly — also when several
        do. Two profiles carrying the founder's name are exactly the case
        the original rule was written for, and a standing identity does
        not tell them apart.
        """
        if not self.configured:
            return None
        hits = [index for index, label in enumerate(labels) if self.matches(label)]
        return hits[0] if len(hits) == 1 else None
