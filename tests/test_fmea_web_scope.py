"""The validation scope may isolate the web rung, and must not become policy.

`KALPAVRIKSHA_FMEA_REASONING_TIER` already existed to let a harness prove
one rung executes without the run falling through to whichever provider
happens to be healthy that minute. It understood `gemini`. It now also
understands `web`, for exactly the same reason and with exactly the same
status: validation configuration, never product routing.

The dangerous failure here is not "web scope does not work". It is "web
scope quietly becomes the product's behaviour". Most of this file guards
the second.
"""
from __future__ import annotations

import pytest

pytest.importorskip("playwright", reason="the composition imports the Browser Worker")

from master_agent.ai_infrastructure.tiered_runner import (
    TIER_BROWSER,
    TIER_DESKTOP,
    TIER_GEMINI,
)


def _tiers(monkeypatch, tmp_path, value=None):
    monkeypatch.setenv("KALPAVRIKSHA_STATE_DIR", str(tmp_path / "state"))
    if value is None:
        monkeypatch.delenv("KALPAVRIKSHA_FMEA_REASONING_TIER", raising=False)
    else:
        monkeypatch.setenv("KALPAVRIKSHA_FMEA_REASONING_TIER", value)

    import kalpavriksha_desktop as fe

    pipeline = fe._build_mission_pipeline()
    if pipeline is None:
        pytest.skip("this machine could not assemble the Founder Edition pipeline")
    return dict(pipeline[4]._tiers)


def test_unset_leaves_the_complete_configured_ladder(monkeypatch, tmp_path):
    """Every founder launch. Nothing may be missing from it."""
    tiers = _tiers(monkeypatch, tmp_path, None)

    assert tiers[TIER_GEMINI], "the API rung must be configured normally"
    assert tiers[TIER_DESKTOP], "the desktop rung must be configured normally"
    assert tiers[TIER_BROWSER], "the web rung must be configured normally"


def test_web_isolates_the_trusted_rung(monkeypatch, tmp_path):
    from master_agent.providers.trusted_web_ai import TRUSTED_WEB_PROVIDER_ID

    tiers = _tiers(monkeypatch, tmp_path, "web")

    assert tiers[TIER_GEMINI] == frozenset(), "the API rung must be emptied"
    assert tiers[TIER_DESKTOP] == frozenset(), "the desktop rung must be emptied"
    assert TRUSTED_WEB_PROVIDER_ID in tiers[TIER_BROWSER], (
        "the web rung keeps its NORMAL configured membership; isolation empties "
        "the others rather than inserting a provider here"
    )


def test_gemini_keeps_its_existing_behaviour_exactly(monkeypatch, tmp_path):
    """The pre-existing value must not shift because a second one was added."""
    tiers = _tiers(monkeypatch, tmp_path, "gemini")

    assert tiers[TIER_GEMINI], "the API rung stays configured under 'gemini'"
    assert tiers[TIER_DESKTOP] == frozenset(), "'gemini' empties the desktop rung"


@pytest.mark.parametrize("value", ["", "  ", "WEB ", "browser", "trusted", "nonsense"])
def test_an_unrecognised_value_is_treated_as_unset(monkeypatch, tmp_path, value):
    """Fail OPEN to the normal ladder, not closed to nothing.

    A typo in a harness variable must not silently disable a founder's
    fallback. `WEB ` is included deliberately: the existing contract
    lowercases and strips, so it is recognised, and that is the current
    behaviour rather than a new one.
    """
    tiers = _tiers(monkeypatch, tmp_path, value)

    if value.strip().lower() == "web":
        assert tiers[TIER_GEMINI] == frozenset()
        return
    assert tiers[TIER_GEMINI], f"{value!r} must not disable the API rung"
    assert tiers[TIER_DESKTOP], f"{value!r} must not disable the desktop rung"


def test_the_scope_is_read_from_the_one_existing_variable(monkeypatch, tmp_path):
    """No second scoping mechanism was invented."""
    from pathlib import Path

    source = Path("kalpavriksha_desktop.py").read_text(encoding="utf-8")
    assert source.count("KALPAVRIKSHA_FMEA_REASONING_TIER") == 1


def test_web_scope_does_not_change_the_web_rung_itself(monkeypatch, tmp_path):
    """Isolation must not smuggle in a provider the normal product lacks."""
    normal = _tiers(monkeypatch, tmp_path, None)[TIER_BROWSER]
    scoped = _tiers(monkeypatch, tmp_path, "web")[TIER_BROWSER]
    assert normal == scoped
