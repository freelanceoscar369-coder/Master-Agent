"""The provider universe the reasoning ladder scopes against.

One invariant, and it is not academic. `TieredPromptRunner` places named
providers in tiers and excludes every *other* provider it knows about from
each tier's scoped Broker call. A provider the ladder does not know exists
cannot be excluded -- so it can win a tier it was never placed in, purely
because nothing told the ladder it was there.

That is exactly what happened: `all_known_provider_ids` was
`PROVIDER_CATALOG` plus one hand-written id, and `trusted-founder-web` is
registered by this composition rather than declared in the global
catalogue. It was visible to the Broker and invisible to the ladder.
"""
from __future__ import annotations

import pytest

pytest.importorskip("playwright", reason="Founder Edition composition imports the Browser Worker")


def _composition():
    """The real Founder Edition assembly, or a skip if this machine cannot
    build it. Never a stub -- the whole point is to check the wiring that
    actually ships."""
    import kalpavriksha_desktop as fe

    pipeline = fe._build_mission_pipeline()
    if pipeline is None:
        pytest.skip("this machine could not assemble the Founder Edition pipeline")
    return fe, pipeline


def test_every_broker_visible_provider_is_known_to_the_reasoning_ladder(monkeypatch, tmp_path):
    """Broker-visible provider ids MUST be a subset of the ladder's
    exclusion universe."""
    monkeypatch.setenv("KALPAVRIKSHA_STATE_DIR", str(tmp_path / "state"))
    _fe, pipeline = _composition()
    runner = pipeline[4]

    # Private attributes on purpose: this is an architecture invariant
    # about wiring, and the wiring is what the runner keeps privately.
    known = set(runner._all_ids)
    broker_visible = {
        profile.provider_id
        for profile in runner._executor._service.providers.profiles()
    }

    missing = broker_visible - known
    assert not missing, (
        "these providers are visible to the Broker but unknown to the ladder, "
        f"so no tier can exclude them: {sorted(missing)}"
    )


def test_the_trusted_web_provider_is_scoped_to_the_web_rung(monkeypatch, tmp_path):
    monkeypatch.setenv("KALPAVRIKSHA_STATE_DIR", str(tmp_path / "state"))
    _fe, pipeline = _composition()
    runner = pipeline[4]

    from master_agent.ai_infrastructure.tiered_runner import TIER_BROWSER
    from master_agent.providers.trusted_web_ai import TRUSTED_WEB_PROVIDER_ID

    web_rung = dict(runner._tiers)[TIER_BROWSER]
    assert TRUSTED_WEB_PROVIDER_ID in runner._all_ids
    assert TRUSTED_WEB_PROVIDER_ID in web_rung


def test_founder_edition_does_not_configure_the_automated_web_ai_lane(monkeypatch, tmp_path):
    """Known is not configured.

    `browser.free-ai` keeps its descriptor, because the provider and the
    Browser Worker behind it stay valid for other deployments. What Founder
    Edition must not do is register an executable implementation: Google
    refuses to sign in inside an automation-controlled browser, so that
    lane cannot serve an authenticated AI site here.
    """
    monkeypatch.setenv("KALPAVRIKSHA_STATE_DIR", str(tmp_path / "state"))
    _fe, pipeline = _composition()
    runner = pipeline[4]

    from master_agent.ai_infrastructure.tiered_runner import TIER_BROWSER
    from master_agent.providers.browser_free_ai import PROVIDER_ID as AUTOMATED_WEB

    web_rung = dict(runner._tiers)[TIER_BROWSER]
    assert AUTOMATED_WEB not in web_rung, (
        "the automated lane must not occupy Founder Edition's web rung"
    )
    # Still administratively known, so the Broker can say "unavailable"
    # about it honestly rather than never having heard of it.
    assert AUTOMATED_WEB in runner._all_ids
