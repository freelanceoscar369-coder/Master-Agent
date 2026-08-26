"""Who owns which knowledge, and what knowledge may never decide.

Three owners, adjudicated from source rather than assumed:

  desktop/operations  generic application OPERATION knowledge, keyed by
                      ApplicationSpec.key -- launch, windows, failure
                      modes, recovery. Chrome and Comet live here.
  app_knowledge       reasoning/chat APPLICATION UI knowledge, keyed by
                      provider_id -- composer, sessions, rename, response.
                      ChatGPT/Kimi/Perplexity Desktop live here.
  WebAiSite           AI WEBSITE UI knowledge, at the provider edge.
                      Gemini lives here.

A browser is not a chat application and has no use for the second set, so
`provider_id` is the right identity for that narrower layer. An earlier
pass concluded the opposite and proposed migrating it; source says that
was a false gap.
"""
from __future__ import annotations

import ast
from pathlib import Path


def test_chrome_and_comet_are_owned_by_desktop_operations():
    from master_agent.desktop.operations.knowledge import PROFILES, RECOVERY_PLANS

    profiled = {p.key for p in PROFILES}
    recovered = {r.key for r in RECOVERY_PLANS}
    for browser in ("chrome", "comet"):
        assert browser in profiled, f"{browser} needs operation knowledge"
        assert browser in recovered, f"{browser} needs a recovery plan"


def test_browsers_do_not_masquerade_as_reasoning_providers():
    """The alternative to the adjudication above would have been
    registering Chrome as an AI provider to give it a profile. It is not."""
    from master_agent.app_knowledge.catalog import APP_KNOWLEDGE_CATALOG

    for browser in ("chrome", "comet"):
        assert browser not in APP_KNOWLEDGE_CATALOG


def test_chat_ui_knowledge_stays_with_chat_applications():
    from master_agent.app_knowledge.catalog import APP_KNOWLEDGE_CATALOG

    assert APP_KNOWLEDGE_CATALOG, "the reasoning-application layer still has subjects"
    for profile in APP_KNOWLEDGE_CATALOG.values():
        assert profile.provider_id, "this layer is keyed by provider identity"


def test_website_knowledge_is_not_in_either_desktop_owner():
    """Gemini is a website. It belongs to the provider edge, and putting it
    in an application profile would make a product architectural."""
    for path in ("src/master_agent/desktop/operations/knowledge.py",
                 "src/master_agent/app_knowledge/catalog.py"):
        text = Path(path).read_text(encoding="utf-8").lower()
        assert "gemini" not in text, f"{path} names a website"


def test_desktop_operations_knowledge_can_never_select_a_reasoning_provider():
    """The constitutional boundary.

    `DesktopExecutiveV2.recommend()` predates the AI Capability Broker and
    carries AI-flavoured capability names. The Broker is the sole authority
    for which provider serves a request, so nothing on the reasoning path
    may call it. Verified structurally: no module outside the operations
    package itself invokes it.
    """
    offenders = []
    for path in Path("src/master_agent").rglob("*.py"):
        if "desktop/operations" in path.as_posix():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "recommend"):
                offenders.append(path.as_posix())
    assert not offenders, (
        "provider selection belongs to the AI Capability Broker alone; "
        f"these call recommend(): {sorted(set(offenders))}"
    )
