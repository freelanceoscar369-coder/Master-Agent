"""Two browser lanes, deliberately separate, and neither may become the
other by accident.

## The two lanes

**Ordinary web automation** — open a page, read it, fill a form, click,
observe. Owned by the Browser Executive, executed through Playwright.
That is MB022's lane and it stays Playwright.

**Trusted authenticated web AI** — an AI *website* used as a reasoning
Provider. The Broker selects `trusted-founder-web`; the provider drives
the founder's own already-signed-in browser through
`DesktopTrustedBrowser`. Playwright is forbidden here, because the
founder's authenticated browser state IS the environment and an
automation-controlled context does not have it.

## Why guards rather than good intentions

A live mission had a large search engine redirect Playwright to its
bot-detection interstitial. Verification caught it and the mission failed
truthfully. The tempting repair — "we have a real authenticated browser
right there, use that instead" — would have collapsed the two lanes into
one, silently moved ordinary web automation into the founder's signed-in
session, and made a Worker decide something only the Brain may decide.

These tests make each half of the separation a structural fact:

* A · the ordinary Worker is Playwright-driven
* B · the trusted provider cannot reach Playwright at all
* C · trusted execution reaches `DesktopTrustedBrowser`
* D · the provider does not choose which browser
* E · the Broker has never heard of any browser product
* F · the Browser Executive does not fall back to the trusted lane
* G · the trusted lane does not substitute another provider
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src" / "master_agent"

#: Everything that drives a browser by automation protocol. The trusted
#: lane may touch none of them: it operates a real window through the
#: Desktop Executive, which is a different mechanism, not a variant.
AUTOMATION_DRIVERS = (
    "playwright", "BrowserSessionManager", "selenium", "webdriver",
    "puppeteer", "pyppeteer", "--remote-debugging-port", "remote_debugging",
    "CDP", "chrome_devtools",
)

#: The browser products the lower layers must never name -- read from the
#: adapter that legitimately knows them, never spelled out here.
#:
#: Two reasons, and the second is the interesting one. A hardcoded list
#: would go stale the day a browser is added, silently guarding less than
#: it claims. And this repository forbids product names in browser files
#: outright (`test_browser_constitution_compliance.py`), including in
#: tests -- a guard that had to break the rule to enforce it would be a
#: poor guard.
def browser_products() -> tuple[str, ...]:
    from master_agent.desktop.trusted_browser_adapter import DEFAULT_CANDIDATES

    return tuple(DEFAULT_CANDIDATES)


def source_of(relative: str) -> str:
    return (SRC / relative).read_text(encoding="utf-8")


def imports_of(relative: str) -> set[str]:
    tree = ast.parse(source_of(relative))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def executable_source(relative: str) -> str:
    """The module with every docstring removed.

    Docstrings legitimately *discuss* the other lane -- this file's own
    subject is the boundary between them. What must not exist is running
    code that crosses it.
    """
    tree = ast.parse(source_of(relative))
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ) and ast.get_docstring(node):
            node.body = node.body[1:]
    return ast.unparse(tree)


# =====================================================================
# A · the ordinary lane is Playwright, and that is not a defect
# =====================================================================


class TestOrdinaryAutomationStaysPlaywright:
    def test_the_browser_worker_drives_a_playwright_session_manager(self):
        assert "master_agent.environment.browser_session" in imports_of(
            "plugins/browser_worker.py"
        )

    def test_the_session_manager_is_the_playwright_one(self):
        assert "playwright" in source_of("environment/browser_session.py").lower()

    @pytest.mark.parametrize("action", [
        "open_session.py", "navigate.py", "click.py", "type_text.py",
        "observe.py", "close_session.py",
    ])
    def test_every_ordinary_browser_action_uses_the_session_manager(self, action):
        source = source_of(f"executor/actions/browser/{action}")
        assert "BrowserSessionManager" in source

    def test_the_ordinary_verifier_re_reads_the_page_through_playwright(self):
        source = source_of("plugins/browser_verifier.py")
        assert "BrowserSessionManager" in source
        assert "normalize_observation" in source


# =====================================================================
# B · the trusted lane cannot reach an automation driver
# =====================================================================


class TestTrustedWebAiCannotUseAutomation:
    @pytest.mark.parametrize("driver", AUTOMATION_DRIVERS)
    def test_the_provider_names_no_automation_driver(self, driver):
        assert driver.lower() not in executable_source(
            "providers/trusted_web_ai.py"
        ).lower(), (
            f"{driver!r} in the trusted web-AI provider -- the founder's "
            "authenticated browser state IS the environment, and an "
            "automation-controlled context does not have it"
        )

    @pytest.mark.parametrize("driver", AUTOMATION_DRIVERS)
    def test_the_port_names_no_automation_driver(self, driver):
        assert driver.lower() not in executable_source("trusted_browser.py").lower()

    @pytest.mark.parametrize("driver", AUTOMATION_DRIVERS)
    def test_the_desktop_adapter_names_no_automation_driver(self, driver):
        assert driver.lower() not in executable_source(
            "desktop/trusted_browser_adapter.py"
        ).lower()

    def test_the_provider_imports_no_environment_package(self):
        """`environment/` is where automation-controlled sessions live.
        The trusted lane's environment is a window the founder already
        has open, reached through the Desktop Executive."""
        assert not any(
            name.startswith("master_agent.environment")
            for name in imports_of("providers/trusted_web_ai.py")
        )


# =====================================================================
# C · trusted execution reaches the Desktop adapter
# =====================================================================


class TestTrustedExecutionReachesTheRealBrowser:
    def test_the_composition_root_hands_the_provider_the_desktop_adapter(self):
        import kalpavriksha_desktop as kd

        source = inspect.getsource(kd._build_mission_pipeline)
        assert "DesktopTrustedBrowser" in source
        assert "TrustedWebAiProvider(" in source
        # Constructed with the desktop adapter, not with anything else.
        assert "browser=DesktopTrustedBrowser(" in source

    def test_the_adapter_is_the_only_layer_that_names_browsers(self):
        """Somebody has to know. It is this layer, and only this layer."""
        assert browser_products(), (
            "the adapter names no browser candidates at all, so nothing "
            "below it could be checked against them"
        )

    def test_the_adapter_operates_windows_through_the_desktop_executive(self):
        source = source_of("desktop/trusted_browser_adapter.py")
        assert "master_agent.desktop" in source

    def test_the_provider_takes_its_browser_as_a_port(self):
        """Injected, never constructed. A provider that built its own
        browser would own the environment decision."""
        from master_agent.providers.trusted_web_ai import TrustedWebAiProvider

        parameters = inspect.signature(TrustedWebAiProvider.__init__).parameters
        assert "browser" in parameters


# =====================================================================
# D · E · nobody below the Trusted Browser layer names a browser
# =====================================================================


class TestNobodyElseChoosesTheBrowser:
    def test_the_provider_names_no_browser_product(self):
        body = executable_source("providers/trusted_web_ai.py").lower()
        for product in browser_products():
            assert product.lower() not in body, (
                "the provider names a browser -- the Broker chooses a "
                "PROVIDER and the Trusted Browser layer resolves the "
                "ENVIRONMENT afterwards; a provider naming a browser owns both"
            )

    def test_the_broker_names_no_browser_product(self):
        for module in ("ai_infrastructure/broker.py", "ai_infrastructure/catalog.py"):
            if not (SRC / module).exists():
                continue
            body = executable_source(module).lower()
            for product in browser_products():
                assert product.lower() not in body, (
                    f"{module} names a browser -- the Broker ranks providers "
                    "on economics and quality, and has no business knowing "
                    "what a browser is"
                )

    def test_the_port_carries_candidates_without_ranking_them(self):
        """The port may carry candidate names -- that is the layer whose
        job it is. What it must not do is prefer one."""
        from master_agent.trusted_browser import BrowserResolution

        fields = getattr(BrowserResolution, "__dataclass_fields__", {})
        assert "ordered" in fields or "candidates" in fields
        assert "preferred" not in fields
        assert "default" not in fields


# =====================================================================
# F · G · neither lane silently becomes the other
# =====================================================================


class TestNeitherLaneFallsBackToTheOther:
    def test_the_browser_worker_cannot_reach_the_trusted_lane(self):
        for module in ("plugins/browser_worker.py", "plugins/browser_gateway.py",
                       "plugins/browser_plugin.py"):
            names = imports_of(module)
            assert not any("trusted_browser" in name for name in names), module
            assert not any("trusted_web_ai" in name for name in names), module

    def test_no_ordinary_browser_action_reaches_the_trusted_lane(self):
        directory = SRC / "executor" / "actions" / "browser"
        for path in sorted(directory.glob("*.py")):
            source = path.read_text(encoding="utf-8")
            assert "trusted_browser" not in source, path.name
            assert "TrustedWebAi" not in source, path.name

    def test_a_blocked_page_produces_evidence_rather_than_a_lane_change(self):
        """The bot-detection case, as a rule rather than an anecdote.

        `bind_for_environment` compares the destination by EQUALITY on a
        normalised URL. A `contains` test would have passed on the
        interstitial -- its URL carries the whole intended search URL
        inside its `continue=` parameter -- and the mission would have
        read a CAPTCHA page and reasoned over it.
        """
        from master_agent.plugins.browser_expectations import bind_for_environment

        expected = bind_for_environment(
            capability="Browser.Navigate",
            payload={"session_id": "s1", "url": "https://www.example.test/search?q=x"},
            description="navigate",
        )
        check = expected.checks[0]
        assert check.operator == "equals"
        assert check.field == "destination_matches"

    def test_the_trusted_provider_never_selects_a_provider(self):
        """MB033 Rule 4. A provider that could pick a provider would make
        the Broker advisory."""
        source = executable_source("providers/trusted_web_ai.py").lower()
        for forbidden in ("capabilitybroker", "select_provider", "modelrouter",
                          "tieredpromptrunner", "promptexecutor"):
            assert forbidden not in source, forbidden

    def test_the_trusted_provider_reaches_no_decision_layer(self):
        names = imports_of("providers/trusted_web_ai.py")
        assert not any(name.startswith("master_agent.ai_infrastructure")
                       for name in names)
        assert not any(name.startswith("master_agent.broker") for name in names)
        assert not any(name.startswith("master_agent.mission_control")
                       for name in names)
