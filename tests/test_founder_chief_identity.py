"""Onkar is the founder. Somesh is the chief of staff. Kalpavriksha is
the system Somesh operates.

Three identities, routinely collapsed into two. `greet()` has always
been handed a `FounderIdentity` carrying both names and read neither, so
the greeting was "Good morning. I'm awake." -- correct in cadence and
addressed to nobody, in the founder's own product.

The failure mode this guards is not a missing name; it is a *swapped*
one. "Good morning, Somesh" greets the chief of staff as though it were
the founder, and no test that only checked for the presence of a name
would catch it.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from master_agent.founder_edition.boot import DEFAULT_FOUNDER_NAME
from master_agent.founder_identity import FounderContext, FounderIdentity, greet

FOUNDER = "Onkar"
CHIEF = "Somesh"
SYSTEM = "Kalpavriksha"


def context(hour: int = 9) -> FounderContext:
    return FounderContext(
        moment=datetime(2026, 8, 15, hour, tzinfo=UTC),
        environment_ready=True, conversation_ready=True, presence_ready=True,
    )


class TestTheThreeIdentities:

    def test_the_founder_is_onkar(self):
        assert DEFAULT_FOUNDER_NAME == FOUNDER

    def test_the_chief_of_staff_is_somesh(self):
        assert FounderIdentity(founder_name=FOUNDER).assistant_name == CHIEF

    def test_the_system_is_kalpavriksha_not_somesh(self):
        """Somesh is a founder-facing identity, not a rename of the
        product. The edition still names the system."""
        identity = FounderIdentity(founder_name=FOUNDER)
        assert SYSTEM in identity.edition
        assert identity.edition != CHIEF

    def test_founder_and_chief_are_never_the_same_person(self):
        identity = FounderIdentity(founder_name=FOUNDER)
        assert identity.founder_name != identity.assistant_name


class TestTheGreeting:

    @pytest.mark.parametrize("hour,opening", [(9, "Good morning"), (14, "Good afternoon"), (20, "Good evening")])
    def test_it_addresses_the_founder_and_names_the_speaker(self, hour, opening):
        reply = greet(FounderIdentity(founder_name=FOUNDER), context(hour))
        assert reply.startswith(f"{opening}, {FOUNDER}."), reply
        assert f"{CHIEF} here." in reply

    def test_the_identities_are_not_reversed(self):
        """The specific defect: greeting the chief of staff by name as
        though they were the founder."""
        reply = greet(FounderIdentity(founder_name=FOUNDER), context())
        assert f", {CHIEF}." not in reply, (
            "the chief of staff is being addressed as the founder"
        )
        assert f"{FOUNDER} here." not in reply, (
            "the founder is being made to introduce themselves"
        )

    def test_a_configured_name_beats_a_generic_label(self):
        reply = greet(FounderIdentity(founder_name=FOUNDER), context())
        for generic in ("Good morning, Founder", "Good morning, User", "Good morning, Chief"):
            assert generic not in reply

    def test_an_unconfigured_founder_is_not_called_founder(self):
        """"Good morning, Founder." is worse than no name at all -- the
        greeting omits the address rather than using a placeholder."""
        reply = greet(FounderIdentity(founder_name="Founder"), context())
        assert reply.startswith("Good morning.")
        assert f"{CHIEF} here." in reply

    def test_a_different_founder_is_greeted_by_their_own_name(self):
        """The names are configuration, not hardcoded prose."""
        reply = greet(FounderIdentity(founder_name="Priya"), context())
        assert reply.startswith("Good morning, Priya.")
        assert FOUNDER not in reply

    def test_the_name_is_used_once_not_sprinkled(self):
        """§17 -- names belong in greetings and acknowledgements, not in
        every sentence."""
        reply = greet(FounderIdentity(founder_name=FOUNDER), context())
        assert reply.count(FOUNDER) == 1
        assert reply.count(CHIEF) == 1


class TestTheDesktopCompositionUsesIt:

    def test_the_shipped_default_is_the_real_founder(self):
        import kalpavriksha_desktop as kd
        import inspect

        source = inspect.getsource(kd.main) if hasattr(kd, "main") else ""
        assert "KALPAVRIKSHA_FOUNDER_NAME" in source or "DEFAULT_FOUNDER_NAME" in source, (
            "the composition root no longer resolves a founder name"
        )
