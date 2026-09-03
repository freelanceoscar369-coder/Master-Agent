"""The founder said who they are, so we stop asking.

`DESKTOP_BROWSER_FINAL_CLOSURE.md` §6 says **"Never choose between
accounts or profiles"**, written from a live measurement: this founder's
machine offered three Chrome profiles, *two carrying the same person's
name*, so first / order / name-similarity would each have picked wrong
with full confidence.

That rule answers *"who is the founder, if nobody has said?"*. Its answer
— do not guess — is untouched. What changed is that somebody has said.
Selecting the profile that matches a standing identity is carrying out a
decision, not making one.

The measurement's lesson survives in the third case below: two options
that BOTH match are still ambiguous, and a standing identity does not
tell them apart.
"""
from __future__ import annotations

from master_agent.founder_identity.web_identity import FounderWebIdentity

ONKAR = FounderWebIdentity(
    founder_name="Onkar", email="freelance.oscar369@gmail.com",
    may_create_free_account=True)

#: What Chrome actually rendered on the founder's machine.
LIVE_PROFILE_CHOOSER = (
    "Open Aarti profile",
    "Open Onkar profile",
    "Open transcom.com profile",
)


# ---------------------------------------------------------------------
# A -- no identity: the original rule, unchanged
# ---------------------------------------------------------------------


def test_without_a_standing_identity_nothing_is_chosen():
    nobody = FounderWebIdentity()

    assert nobody.configured is False
    assert nobody.sole_match(LIVE_PROFILE_CHOOSER) is None
    assert nobody.matches("Open Onkar profile") is False


def test_two_indistinguishable_accounts_are_never_guessed():
    """The exact case §6 was measured on."""
    twins = ("Open Onkar profile", "Open Onkar (work) profile")

    assert ONKAR.matches(twins[0]) and ONKAR.matches(twins[1])
    assert ONKAR.sole_match(twins) is None, (
        "two profiles bearing the founder's name were disambiguated by "
        "something other than the founder")


# ---------------------------------------------------------------------
# B -- one matching account: select it, ask nothing
# ---------------------------------------------------------------------


def test_the_founders_own_profile_is_selected_from_the_live_chooser():
    index = ONKAR.sole_match(LIVE_PROFILE_CHOOSER)

    assert index == 1
    assert LIVE_PROFILE_CHOOSER[index] == "Open Onkar profile"


def test_an_email_identity_matches_an_account_shown_by_address():
    assert ONKAR.matches("freelance.oscar369@gmail.com")
    # and by the local part, which is how most choosers render it
    assert ONKAR.matches("Open freelance.oscar369 profile")


def test_matching_is_substring_never_similarity():
    """No edit distance, no initials, no "closest" -- picking a similar
    name with confidence is the failure being prevented."""
    assert ONKAR.matches("Open Onkar profile")
    assert not ONKAR.matches("Open Omkar profile")
    assert not ONKAR.matches("Open O. profile")
    assert not ONKAR.matches("Open Aarti profile")


def test_the_provider_selects_the_matching_profile_without_asking():
    """Through the real `_resolve_account`, with a founder-interaction
    double that fails the test if it is consulted."""
    from master_agent.providers.trusted_web_ai import (
        TrustedWebAiProvider, UNKNOWN,
    )

    class Element:
        def __init__(self, name):
            self.name = name
            self.is_actionable = True

    class Observation:
        application = "chrome"

        def named(self, role):
            return [Element(label) for label in LIVE_PROFILE_CHOOSER]

    class Browser:
        def __init__(self):
            self.clicked = []

        def click(self, element):
            self.clicked.append(element.name)

    class MustNotAsk:
        def ask_choice(self, request):  # pragma: no cover - must not run
            raise AssertionError("the founder was asked about their own account")

    browser = Browser()
    provider = TrustedWebAiProvider(
        browser=browser, interaction=MustNotAsk(), founder_identity=ONKAR)

    outcome = provider._resolve_account(Observation())

    assert outcome == UNKNOWN
    assert browser.clicked == ["Open Onkar profile"]


def test_without_the_identity_the_same_chooser_reaches_the_founder():
    """The control: remove the standing identity and the question comes
    back. The policy is what changed, not the mechanism."""
    from master_agent.providers.trusted_web_ai import TrustedWebAiProvider

    class Element:
        def __init__(self, name):
            self.name = name
            self.is_actionable = True

    class Observation:
        application = "chrome"

        def named(self, role):
            return [Element(label) for label in LIVE_PROFILE_CHOOSER]

    class Browser:
        def __init__(self):
            self.clicked = []

        def click(self, element):
            self.clicked.append(element.name)

    asked = []

    class Founder:
        def ask_choice(self, request):
            asked.append(request)

            class Answer:
                cancelled = True
                option_id = ""

            return Answer()

    provider = TrustedWebAiProvider(
        browser=Browser(), interaction=Founder(), founder_identity=None)
    provider._resolve_account(Observation())

    assert asked, "with no standing identity the founder must still be asked"


# ---------------------------------------------------------------------
# C / D -- what authorisation does and does not extend to
# ---------------------------------------------------------------------


def test_free_account_creation_is_authorised_separately_from_paid_use():
    assert ONKAR.may_create_free_account is True
    assert ONKAR.paid_usage_authorized is False


def test_paid_usage_is_explicitly_refused_rather_than_unanswered():
    """A component asking "may I spend?" gets a no, not a missing key."""
    assert FounderWebIdentity().paid_usage_authorized is False
    assert ONKAR.paid_usage_authorized is False


def test_the_identity_carries_no_secret():
    """A criterion for recognising an account, never a means of entering
    one. No password, cookie, token or OTP field may appear here."""
    import dataclasses

    fields = {f.name for f in dataclasses.fields(FounderWebIdentity)}
    for secret in ("password", "token", "cookie", "session", "otp",
                   "secret", "credential"):
        assert not any(secret in name for name in fields), (
            f"{secret!r} appears in the founder identity record")


def test_the_composition_root_records_the_founder_ruling():
    """It survives a restart because it is declared in the composition,
    not accumulated at runtime -- every boot reconstructs it."""
    import kalpavriksha_desktop as kd

    policy = kd.FOUNDER_WEB_IDENTITY

    assert policy.founder_name == "Onkar"
    assert policy.email == "freelance.oscar369@gmail.com"
    assert policy.may_select_matching_profile is True
    assert policy.paid_usage_authorized is False
    assert policy.sole_match(LIVE_PROFILE_CHOOSER) == 1
