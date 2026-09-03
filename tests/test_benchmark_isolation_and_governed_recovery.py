"""Two things that look like "try another provider" and must never be
confused.

**Benchmark isolation.** Measuring `gemini.api` means measuring
`gemini.api`. If a rate-limited call slides into the founder's browser,
the number produced is about neither provider. This happened in this
project: five straight benchmark attempts were answered by
`trusted-founder-web`, three of them recording *"the founder cancelled
the browser choice"* -- a benchmark putting dialogs in front of the
founder while attributing the result to a model that was never asked.

**Governed recovery.** A mission whose route is unavailable SHOULD reach
its intelligence another way. `DESKTOP_BROWSER_FINAL_CLOSURE.md` §2 fixes
the shape of that: *"A provider never selects another provider -- if the
trusted lane cannot execute, it returns a truthful failure and any second
attempt is a new Broker decision with its own record."*

So the difference is not whether another route is used. It is **who
decided**, and whether it was recorded.
"""
from __future__ import annotations

import inspect

from master_agent.ai_infrastructure.intelligence_stack import (
    API,
    AVAILABLE,
    FREE_QUOTA,
    FreeIntelligenceStack,
    Intelligence,
    Observation,
    PLANNER,
    QUOTA_EXHAUSTED,
    QUOTA_FAILURE,
    TRUSTED_WEB,
)


def gemini_stack():
    stack = FreeIntelligenceStack()
    stack.register(Intelligence(
        tool_id="gemini/3.6-flash", provider_id="gemini.api",
        intelligence="Gemini", access_lane=API, free_status=FREE_QUOTA,
        availability=AVAILABLE))
    stack.register(Intelligence(
        tool_id="gemini/web", provider_id="trusted-founder-web",
        intelligence="Gemini", access_lane=TRUSTED_WEB,
        free_status="web_free", availability=AVAILABLE))
    return stack


# ---------------------------------------------------------------------
# The architecture already forbids the wrong version of recovery
# ---------------------------------------------------------------------


def test_the_trusted_provider_may_not_choose_another_provider():
    """The existing guard, restated here because this brief's whole
    question is where fallback may live. It may not live in a provider."""
    from master_agent.providers import trusted_web_ai

    source = inspect.getsource(trusted_web_ai)
    for forbidden in ("def select", "def rank", "def choose", "def prefer",
                      "def fallback"):
        assert forbidden not in source, (
            f"the trusted provider defines {forbidden!r} -- a provider that "
            "picks another provider is the failure ADR-0017 excludes")


def test_the_trusted_provider_imports_no_selection_authority():
    from master_agent.providers import trusted_web_ai

    source = inspect.getsource(trusted_web_ai)
    for owner in ("from master_agent.broker", "from master_agent.planner",
                  "from master_agent.mission_control"):
        assert owner not in source, (
            f"the trusted provider imports {owner!r}; browser availability "
            "must never select a provider")


def test_the_runner_does_not_reach_for_the_browser_when_a_provider_is_pinned():
    """Benchmark isolation, structurally: the tier ladder scopes each
    attempt to that tier's providers, so a pinned provider cannot be
    answered by a different lane."""
    from master_agent.ai_infrastructure import tiered_runner

    source = inspect.getsource(tiered_runner.TieredPromptRunner._scope)

    assert "exclude_providers" in source
    assert "_all_ids - allowed_ids" in source


# ---------------------------------------------------------------------
# Recovery, as the stack must record it
# ---------------------------------------------------------------------


def test_an_unavailable_route_leaves_its_sibling_selectable():
    """The mission is not blocked because one route is: the other route
    remains a candidate for a NEW decision."""
    stack = gemini_stack()

    stack.observe(Observation(
        tool_id="gemini/3.6-flash", task=PLANNER, failure_class=QUOTA_FAILURE,
        availability=QUOTA_EXHAUSTED, failure_detail="HTTP 429 limit: 20"))

    routes = {r.tool_id: r.availability for r in stack.routes_to("Gemini")}

    assert routes["gemini/3.6-flash"] == QUOTA_EXHAUSTED
    assert routes["gemini/web"] == AVAILABLE


def test_the_route_failure_is_recorded_before_anything_else_is_tried():
    """"Record the route failure" is the first step of the sequence, and
    the reason recovery is not silent: the ledger shows why a second
    route was considered at all."""
    stack = gemini_stack()

    stack.observe(Observation(
        tool_id="gemini/3.6-flash", task=PLANNER, failure_class=QUOTA_FAILURE,
        availability=QUOTA_EXHAUSTED, failure_detail="HTTP 429"))

    recorded = stack.observations("gemini/3.6-flash")
    assert len(recorded) == 1
    assert recorded[0].failure_class == QUOTA_FAILURE
    assert recorded[0].availability == QUOTA_EXHAUSTED
    assert stack.get("gemini/3.6-flash").last_failure


def test_recovery_does_not_score_the_first_route_as_a_bad_model():
    """A quota failure is why we changed route, not evidence the model
    plans badly. Both matter, and they are different records."""
    stack = gemini_stack()
    stack.observe(Observation(
        tool_id="gemini/3.6-flash", task=PLANNER, failure_class=QUOTA_FAILURE,
        availability=QUOTA_EXHAUSTED))
    stack.observe(Observation(
        tool_id="gemini/web", task=PLANNER, accepted=True,
        latency_seconds=40.0))

    api = stack.get("gemini/3.6-flash").for_task(PLANNER)
    web = stack.get("gemini/web").for_task(PLANNER)

    assert api.attempts == 0 and api.rate is None
    assert web.attempts == 1 and web.accepted == 1
    # and the sample is still honest about its size
    assert "very small sample" in web.stated()


def test_the_stack_offers_routes_without_ordering_them():
    """Recovery selects; the stack only says what exists. Ordering here
    would put the choice in the wrong owner."""
    stack = gemini_stack()
    stack.observe(Observation(
        tool_id="gemini/3.6-flash", task=PLANNER, failure_class=QUOTA_FAILURE,
        availability=QUOTA_EXHAUSTED))

    routes = stack.routes_to("Gemini")

    assert len(routes) == 2
    assert not hasattr(stack, "next_route")
    assert not hasattr(stack, "best_route")
