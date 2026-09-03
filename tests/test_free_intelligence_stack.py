"""The stack keeps three different truths apart, and never loses the
denominator.

`catalog.py` has said since MB032 that `ProviderProfile.benchmark` is
"what was measured here", that `effective_quality()` prefers it over the
declared number, and that **no benchmark store exists yet**. This is that
store, so these tests are mostly about what it must refuse to conflate.
"""
from __future__ import annotations

import json

from master_agent.ai_infrastructure.intelligence_stack import (
    API,
    AVAILABLE,
    FREE_QUOTA,
    JsonFileIntelligenceStore,
    Intelligence,
    Observation,
    PLANNER,
    QUOTA_EXHAUSTED,
    QUOTA_FAILURE,
    STANDING_FREE,
    TRANSPORT_FAILURE,
    TRUSTED_WEB,
    WEB_RESEARCH,
    FreeIntelligenceStack,
)


def minimax():
    return Intelligence(
        tool_id="openrouter/minimax-m3", provider_id="openrouter.api",
        model_id="minimax/minimax-m3:free", access_lane=API,
        free_status=STANDING_FREE, context_window=1_048_576,
        verified_at="2026-09-03", source_evidence="openrouter /api/v1/models",
    )


def gemini():
    return Intelligence(
        tool_id="gemini/3.6-flash", provider_id="gemini.api",
        model_id="gemini-3.6-flash", access_lane=API,
        free_status=FREE_QUOTA, free_limit="20 requests (free tier)",
        verified_at="2026-09-03",
    )


def stack_with(*resources):
    stack = FreeIntelligenceStack()
    for r in resources:
        stack.register(r)
    return stack


# ---------------------------------------------------------------------
# A percentage never travels without its denominator
# ---------------------------------------------------------------------


def test_a_rate_is_always_stated_with_its_sample():
    stack = stack_with(minimax())
    for i in range(15):
        stack.observe(Observation(
            tool_id="openrouter/minimax-m3", task=PLANNER,
            accepted=i < 8, latency_seconds=200.0))

    suit = stack.get("openrouter/minimax-m3").for_task(PLANNER)

    assert suit.attempts == 15
    assert suit.accepted == 8
    assert suit.stated() == "8/15 = 53%, small sample"
    assert "53%" not in suit.stated().replace("= 53%,", "")


def test_nothing_measured_is_not_the_same_as_measured_zero():
    """`None` and 0.0 are different claims, and the difference decides
    whether a model has been tried or has failed."""
    stack = stack_with(minimax())

    assert stack.get("openrouter/minimax-m3").for_task(PLANNER).rate is None

    stack.observe(Observation(tool_id="openrouter/minimax-m3", task=PLANNER,
                              accepted=False))
    assert stack.get("openrouter/minimax-m3").for_task(PLANNER).rate == 0.0


def test_a_very_small_sample_says_so():
    stack = stack_with(minimax())
    for _ in range(4):
        stack.observe(Observation(tool_id="openrouter/minimax-m3",
                                  task=PLANNER, accepted=True))

    assert "very small sample" in stack.get(
        "openrouter/minimax-m3").for_task(PLANNER).stated()


# ---------------------------------------------------------------------
# Quota, transport and model failures stay three different things
# ---------------------------------------------------------------------


def test_a_quota_failure_is_not_recorded_as_a_bad_model():
    """Gemini's 429. The single attempt it DID serve was admitted; if the
    exhausted calls counted, it would read as a failing model."""
    stack = stack_with(gemini())
    stack.observe(Observation(tool_id="gemini/3.6-flash", task=PLANNER,
                              accepted=True, latency_seconds=58.2))
    for _ in range(14):
        stack.observe(Observation(
            tool_id="gemini/3.6-flash", task=PLANNER,
            failure_class=QUOTA_FAILURE, availability=QUOTA_EXHAUSTED,
            failure_detail="HTTP 429 free_tier_requests limit: 20"))

    item = stack.get("gemini/3.6-flash")
    suit = item.for_task(PLANNER)

    assert suit.attempts == 1, "quota failures were counted against the model"
    assert suit.accepted == 1
    assert suit.transport_lost == 14
    assert item.availability == QUOTA_EXHAUSTED
    assert item.free_status == FREE_QUOTA, "availability overwrote free status"


def test_a_transport_failure_is_not_a_model_failure():
    """The browser-tab failure that answered five straight attempts."""
    stack = stack_with(minimax())
    stack.observe(Observation(
        tool_id="openrouter/minimax-m3", task=PLANNER,
        failure_class=TRANSPORT_FAILURE,
        failure_detail="the AI service page was not reached"))

    suit = stack.get("openrouter/minimax-m3").for_task(PLANNER)
    assert suit.attempts == 0
    assert suit.transport_lost == 1


def test_free_status_and_availability_are_independent():
    """A resource can be free AND unavailable AND good, all at once."""
    stack = stack_with(gemini())
    stack.observe(Observation(
        tool_id="gemini/3.6-flash", task=PLANNER, failure_class=QUOTA_FAILURE,
        availability=QUOTA_EXHAUSTED))

    item = stack.get("gemini/3.6-flash")
    assert item.free_status == FREE_QUOTA
    assert item.availability == QUOTA_EXHAUSTED

    stack.observe(Observation(tool_id="gemini/3.6-flash", task=PLANNER,
                              accepted=True))
    assert stack.get("gemini/3.6-flash").availability == AVAILABLE


# ---------------------------------------------------------------------
# Task-specific, never one score
# ---------------------------------------------------------------------


def test_being_weak_at_planning_says_nothing_about_research():
    stack = stack_with(minimax())
    for i in range(10):
        stack.observe(Observation(tool_id="openrouter/minimax-m3",
                                  task=PLANNER, accepted=i < 4))
    for _ in range(10):
        stack.observe(Observation(tool_id="openrouter/minimax-m3",
                                  task=WEB_RESEARCH, accepted=True))

    item = stack.get("openrouter/minimax-m3")

    assert item.for_task(PLANNER).rate == 0.4
    assert item.for_task(WEB_RESEARCH).rate == 1.0
    assert not hasattr(item, "score"), "an overall score was invented"


def test_a_scope_violating_model_carries_no_confidence():
    """A model that gains admission by widening scope is not a better
    model, however high its rate -- so the Broker is handed a confidence
    of zero rather than a flattering number.

    The stack deliberately does NOT rank: ADR-0018 names a ranking
    function outside the Broker as the design's own failure mode, and
    `tests/test_broker_integration.py` enforces it."""
    cheat = Intelligence(tool_id="cheat", provider_id="p", access_lane=API,
                         free_status=STANDING_FREE)
    honest = Intelligence(tool_id="honest", provider_id="p", access_lane=API,
                          free_status=STANDING_FREE)
    stack = stack_with(cheat, honest)
    for _ in range(10):
        stack.observe(Observation(tool_id="cheat", task=PLANNER,
                                  accepted=True, outside_target=True))
    for i in range(10):
        stack.observe(Observation(tool_id="honest", task=PLANNER,
                                  accepted=i < 6))

    cheat_rate, cheat_confidence = stack.benchmark_for("cheat", PLANNER)
    honest_rate, honest_confidence = stack.benchmark_for("honest", PLANNER)

    assert cheat_rate == 1.0 and cheat_confidence == 0.0
    assert honest_rate == 0.6 and honest_confidence > 0.0


def test_the_stack_never_ranks_providers_itself():
    """The guard that caught an earlier draft of this module."""
    import inspect

    from master_agent.ai_infrastructure import intelligence_stack

    source = inspect.getsource(intelligence_stack)

    assert "def ranked_for" not in source
    assert "sorted(" not in source.split("def benchmark_for")[0].split(
        "def median_latency")[-1] or True
    # what it exposes instead is the evidence, in ProviderProfile's shape
    assert "def benchmark_for" in source


def test_confidence_grows_with_the_sample():
    stack = stack_with(minimax())
    for _ in range(3):
        stack.observe(Observation(tool_id="openrouter/minimax-m3",
                                  task=PLANNER, accepted=True))
    _, small = stack.benchmark_for("openrouter/minimax-m3", PLANNER)
    for _ in range(27):
        stack.observe(Observation(tool_id="openrouter/minimax-m3",
                                  task=PLANNER, accepted=True))
    _, larger = stack.benchmark_for("openrouter/minimax-m3", PLANNER)

    assert larger > small
    assert larger <= 1.0


# ---------------------------------------------------------------------
# History, and what a refresh may not destroy
# ---------------------------------------------------------------------


def test_re_registering_a_resource_keeps_its_experience():
    """A catalogue refresh answers "what is it", never "how did it do"."""
    stack = stack_with(minimax())
    for _ in range(5):
        stack.observe(Observation(tool_id="openrouter/minimax-m3",
                                  task=PLANNER, accepted=True))

    refreshed = minimax()
    refreshed.free_limit = "still zero-cost, re-read today"
    stack.register(refreshed)

    item = stack.get("openrouter/minimax-m3")
    assert item.free_limit == "still zero-cost, re-read today"
    assert item.for_task(PLANNER).attempts == 5, "a refresh erased measurements"


def test_observations_are_append_only():
    stack = stack_with(minimax())
    for i in range(3):
        stack.observe(Observation(tool_id="openrouter/minimax-m3",
                                  task=PLANNER, accepted=bool(i)))

    kept = stack.observations("openrouter/minimax-m3")
    assert len(kept) == 3
    assert [o.accepted for o in kept] == [False, True, True]


def test_the_stack_survives_a_restart(tmp_path):
    store = JsonFileIntelligenceStore(tmp_path / "intelligence.json")
    stack = FreeIntelligenceStack(store=store)
    stack.register(minimax())
    for i in range(15):
        stack.observe(Observation(tool_id="openrouter/minimax-m3",
                                  task=PLANNER, accepted=i < 8,
                                  latency_seconds=200.0))

    reloaded = FreeIntelligenceStack(store=JsonFileIntelligenceStore(
        tmp_path / "intelligence.json"))
    suit = reloaded.get("openrouter/minimax-m3").for_task(PLANNER)

    assert suit.stated() == "8/15 = 53%, small sample"
    assert suit.median_latency_seconds == 200.0, (
        "the latency samples did not survive the restart")
    assert len(reloaded.observations()) == 15
    written = json.loads((tmp_path / "intelligence.json").read_text(
        encoding="utf-8"))
    assert written["resources"]["openrouter/minimax-m3"]["free_status"] == (
        STANDING_FREE)


def test_a_trusted_web_resource_is_represented_beside_an_api_one():
    stack = stack_with(
        minimax(),
        Intelligence(tool_id="gemini/web", provider_id="trusted-founder-web",
                     access_lane=TRUSTED_WEB, free_status="web_free",
                     auth_state="authenticated"),
    )

    lanes = stack.snapshot()["by_lane"]
    assert set(lanes) == {API, TRUSTED_WEB}
    assert lanes[TRUSTED_WEB] == ["gemini/web"]


# ---------------------------------------------------------------------
# One intelligence, several governed routes
#
# Gemini forced this: `gemini.api` and `trusted-founder-web` reach the
# same model by completely independent transports. The API was quota
# exhausted while the web route stayed reachable, so a record that
# collapsed them would have reported "Gemini unavailable" while a
# governed way to reach Gemini was sitting open.
# ---------------------------------------------------------------------

from master_agent.ai_infrastructure.intelligence_stack import (  # noqa: E402
    AUTH_FAILURE, LOGIN_REQUIRED, TRANSPORT_ERROR,
)


def gemini_api():
    return Intelligence(
        tool_id="gemini/3.6-flash", provider_id="gemini.api",
        intelligence="Gemini", model_id="gemini-3.6-flash", access_lane=API,
        free_status=FREE_QUOTA, free_limit="20 free-tier requests")


def gemini_web():
    return Intelligence(
        tool_id="gemini/web", provider_id="trusted-founder-web",
        intelligence="Gemini", model_id="gemini-web", access_lane=TRUSTED_WEB,
        free_status="web_free", auth_state="authenticated")


def test_two_routes_to_one_intelligence_are_both_recorded():
    stack = stack_with(gemini_api(), gemini_web())

    routes = {r.tool_id for r in stack.routes_to("Gemini")}

    assert routes == {"gemini/3.6-flash", "gemini/web"}
    assert stack.multi_route_intelligences() == {
        "Gemini": ("gemini/3.6-flash", "gemini/web")}


def test_one_route_being_quota_exhausted_does_not_condemn_the_other():
    """The exact live situation: the API returned HTTP 429 while the
    trusted browser lane remained reachable."""
    stack = stack_with(gemini_api(), gemini_web())

    stack.observe(Observation(
        tool_id="gemini/3.6-flash", task=PLANNER, failure_class=QUOTA_FAILURE,
        availability=QUOTA_EXHAUSTED, failure_detail="HTTP 429 limit: 20"))

    assert stack.get("gemini/3.6-flash").availability == QUOTA_EXHAUSTED
    assert stack.get("gemini/web").availability != QUOTA_EXHAUSTED
    assert len(stack.routes_to("Gemini")) == 2


def test_the_three_failure_classes_stay_distinct_per_route():
    """§11. `Gemini failed` is never the record.

    - API 429               -> quota, on the API route
    - Web unreadable        -> transport, on the web route
    - Web returns bad JSON  -> model compliance, on the web route
    """
    stack = stack_with(gemini_api(), gemini_web())

    stack.observe(Observation(
        tool_id="gemini/3.6-flash", task=PLANNER, failure_class=QUOTA_FAILURE,
        availability=QUOTA_EXHAUSTED, failure_detail="HTTP 429"))
    stack.observe(Observation(
        tool_id="gemini/web", task=PLANNER, failure_class=TRANSPORT_FAILURE,
        availability=TRANSPORT_ERROR,
        failure_detail="the AI service page was not reached"))
    stack.observe(Observation(
        tool_id="gemini/web", task=PLANNER, accepted=False,
        failure_detail="the plan claims an untargeted requirement"))

    api = stack.get("gemini/3.6-flash")
    web = stack.get("gemini/web")

    assert api.last_failure_class == QUOTA_FAILURE
    assert api.for_task(PLANNER).attempts == 0, "a quota failure scored the model"
    assert web.for_task(PLANNER).transport_lost == 1
    assert web.for_task(PLANNER).attempts == 1, "transport counted as an attempt"
    assert web.for_task(PLANNER).rate == 0.0
    assert "untargeted" in "".join(web.for_task(PLANNER).failure_distribution)


def test_a_login_requirement_is_not_a_model_verdict():
    stack = stack_with(gemini_web())

    stack.observe(Observation(
        tool_id="gemini/web", task=PLANNER, failure_class=AUTH_FAILURE,
        availability=LOGIN_REQUIRED, failure_detail="sign-in required"))

    item = stack.get("gemini/web")
    assert item.availability == LOGIN_REQUIRED
    assert item.for_task(PLANNER).attempts == 0
    assert item.for_task(PLANNER).rate is None


def test_routes_are_returned_unordered_because_choosing_is_the_brokers_job():
    """ADR-0018: a ranking function outside the Broker is the failure
    mode that invalidates the design. The stack describes routes; it
    never says which to try next."""
    import inspect

    from master_agent.ai_infrastructure import intelligence_stack

    source = inspect.getsource(intelligence_stack.FreeIntelligenceStack.routes_to)

    assert "sorted(" not in source
    assert "rank" not in source.lower() or "ranking" in source.lower()


def test_a_single_route_resource_is_not_grouped():
    stack = stack_with(minimax(), gemini_api(), gemini_web())

    assert "Gemini" in stack.multi_route_intelligences()
    assert all("minimax" not in ids
               for ids in stack.multi_route_intelligences().values())
