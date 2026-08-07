"""Sprint 1, Component 22 — Environment Intelligence.

The scanner answers *"what exists?"*. This layer answers *"what does this
environment mean?"* — and the tests below are mostly about the second
half of that sentence being honest.

| Requirement | Source |
|---|---|
| Every inference carries confidence, reason, source | C22 brief |
| Never infer a user profile from one application alone | C22 brief |
| Web AI is only `available` / `unknown` / `unavailable` | C22 brief |
| Never inspect passwords, conversations, documents, cookies | C22 brief |
| Never execute, launch, install or mutate | C22 brief |
| No duplicate scanner logic, no second catalog, no second inventory | C22 brief |
| *I don't know* is a different sentence from *I haven't checked* | VEDA 04 §5 |
| Observations, never recommendations | `desktop/inventory.py` |

Every test builds a `MachineInventory` directly. **No probe is ever
constructed and no real machine is touched** — which is the same property
`desktop/`'s own suite relies on, and the reason a hundred of these can
run without launching Chrome.
"""
from __future__ import annotations

import ast
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from master_agent.desktop.inventory import (
    INSTALLED,
    MISSING,
    UNAVAILABLE,
    InstalledApplication,
    MachineInventory,
)
from master_agent.desktop.probe import ProcessInfo
from master_agent.environment_intelligence import (
    SECTIONS,
    UNCATALOGUED,
    WEB_AI_SERVICES,
    Availability,
    Confidence,
    Evidence,
    Inference,
    InvalidEvidence,
    ProfileKind,
    ToolState,
    derive_ai,
    derive_browsers,
    derive_graph,
    derive_intelligence,
    derive_preferences,
    derive_profile,
    unknown,
)

PACKAGE = (
    Path(__file__).resolve().parent.parent
    / "src" / "master_agent" / "environment_intelligence"
)

T0 = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)


def app(
    key: str,
    category: str,
    *,
    status: str = INSTALLED,
    healthy: bool = True,
    version: str | None = None,
    name: str | None = None,
) -> InstalledApplication:
    return InstalledApplication(
        key=key,
        name=name or key.replace("_", " ").title(),
        category=category,
        status=status,
        healthy=healthy,
        version=version,
    )


def inventory(
    *applications: InstalledApplication, running: tuple[str, ...] = ()
) -> MachineInventory:
    processes = [
        ProcessInfo(pid=100 + i, name=f"{key}.exe", owner=key)
        for i, key in enumerate(running)
    ]
    return MachineInventory(
        applications=list(applications),
        processes=processes,
        platform="win32",
        captured_at=T0,
    )


def _package_imports() -> list[str]:
    found: list[str] = []
    for path in PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.append(node.module)
    return found


def _package_identifiers() -> set[str]:
    """Executable names only.

    Checked instead of raw source because these modules' docstrings name
    the things they refuse to do — a text-matching guard would fail on its
    own explanation, which is a trap this project has already hit twice.
    """
    names: set[str] = set()
    for path in PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.alias):
                names.add(node.asname or node.name.rsplit(".", 1)[-1])
    return names


# ======================================================================
# Explainability — no black box
# ======================================================================


def test_every_inference_carries_confidence_reason_and_evidence() -> None:
    """The brief's central requirement, checked across a whole result."""
    result = derive_intelligence(
        inventory(
            app("git", "developer"),
            app("python", "runtime"),
            app("chrome", "browser"),
            running=("chrome",),
        )
    )

    seen = 0
    for node in _walk_inferences(result.as_dict()):
        seen += 1
        assert "confidence" in node
        assert node["reason"].strip()
        if node["confidence"] != Confidence.UNKNOWN.value:
            assert node["evidence"], node["reason"]
            for item in node["evidence"]:
                assert item["source"].strip()
                assert item["fact"].strip()
    assert seen > 10, "the walk should find every inference in the tree"


def _walk_inferences(value: object):
    """Yield every dict that looks like a projected `Inference`."""
    if isinstance(value, dict):
        if {"value", "confidence", "reason", "evidence"} <= set(value):
            yield value
        for item in value.values():
            yield from _walk_inferences(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_inferences(item)


def test_an_unknown_inference_never_carries_a_value() -> None:
    """Naming a value at UNKNOWN would be a guess presented as a finding."""
    with pytest.raises(InvalidEvidence):
        Inference(value="chrome", confidence=Confidence.UNKNOWN, reason="x")


def test_a_known_inference_must_carry_evidence() -> None:
    with pytest.raises(InvalidEvidence):
        Inference(value="chrome", confidence=Confidence.STRONG, reason="x")


def test_an_inference_must_state_a_reason() -> None:
    for blank in ("", "   "):
        with pytest.raises(InvalidEvidence):
            unknown(blank)


def test_evidence_must_name_its_source_and_fact() -> None:
    for bad in (("", "fact"), ("source", ""), ("  ", "fact")):
        with pytest.raises(InvalidEvidence):
            Evidence(source=bad[0], fact=bad[1])


# ======================================================================
# Confidence propagation
# ======================================================================


def test_confidence_is_ordered() -> None:
    assert Confidence.OBSERVED.rank < Confidence.STRONG.rank
    assert Confidence.STRONG.rank < Confidence.WEAK.rank
    assert Confidence.WEAK.rank < Confidence.UNKNOWN.rank


def test_a_conclusion_is_never_stronger_than_its_weakest_input() -> None:
    assert Confidence.weakest(Confidence.OBSERVED, Confidence.WEAK) is (
        Confidence.WEAK
    )
    assert Confidence.weakest(Confidence.OBSERVED, Confidence.UNKNOWN) is (
        Confidence.UNKNOWN
    )
    assert Confidence.weakest(Confidence.OBSERVED) is Confidence.OBSERVED


def test_two_weak_facts_do_not_become_a_strong_one() -> None:
    """No averaging, no boosting. That arithmetic is how a guess acquires
    authority it did not earn."""
    assert Confidence.weakest(Confidence.WEAK, Confidence.WEAK) is Confidence.WEAK


def test_weakest_of_nothing_is_unknown() -> None:
    assert Confidence.weakest() is Confidence.UNKNOWN


def test_readiness_inherits_the_weakest_input(  ) -> None:
    """`environment_ready` is derived from the profile, so it can never be
    more certain than the profile was."""
    result = derive_intelligence(
        inventory(app("git", "developer"), app("python", "runtime"))
    )
    ready = result.summary.environment_ready
    assert ready.confidence.rank >= result.profile.kind.confidence.rank


# ======================================================================
# Browsers — including the conflicting case
# ======================================================================


def test_a_single_running_browser_is_preferred_and_active() -> None:
    result = derive_browsers(
        inventory(
            app("chrome", "browser"),
            app("firefox", "browser"),
            running=("chrome",),
        )
    )
    assert result.preferred.value == "chrome"
    assert result.preferred.confidence is Confidence.OBSERVED
    assert result.active.value == "chrome"


def test_conflicting_browsers_produce_unknown_not_a_coin_toss() -> None:
    """Two browsers open says nothing about preference."""
    result = derive_browsers(
        inventory(
            app("chrome", "browser"),
            app("firefox", "browser"),
            running=("chrome", "firefox"),
        )
    )
    assert result.preferred.value is None
    assert result.preferred.confidence is Confidence.UNKNOWN
    assert "Chrome" in result.preferred.reason
    assert "Firefox" in result.preferred.reason


def test_the_only_installed_browser_is_preferred_without_running() -> None:
    result = derive_browsers(inventory(app("firefox", "browser")))
    assert result.preferred.value == "firefox"
    assert result.preferred.confidence is Confidence.STRONG


def test_several_installed_none_running_is_unknown_and_names_them() -> None:
    result = derive_browsers(
        inventory(app("chrome", "browser"), app("edge", "browser"))
    )
    assert result.preferred.confidence is Confidence.UNKNOWN
    assert "Chrome" in result.preferred.reason


def test_no_browser_installed_is_unknown_not_an_error() -> None:
    result = derive_browsers(inventory(app("git", "developer")))
    assert result.preferred.confidence is Confidence.UNKNOWN
    assert result.browsers == ()


def test_a_broken_browser_is_not_preferred() -> None:
    """`UNAVAILABLE` means present but unusable — the scanner's own word,
    and preferring it would recommend something that does not work."""
    result = derive_browsers(
        inventory(
            app("chrome", "browser", status=UNAVAILABLE, healthy=False),
            app("firefox", "browser"),
        )
    )
    assert result.preferred.value == "firefox"


def test_the_default_browser_is_always_unknown_and_says_why() -> None:
    """No registry read, no xdg-settings. The reason names the missing
    capability rather than implying nothing is installed."""
    result = derive_browsers(inventory(app("chrome", "browser")))
    assert result.default.confidence is Confidence.UNKNOWN
    assert "default handler" in result.default.reason


def test_two_running_browsers_do_not_produce_an_active_guess() -> None:
    result = derive_browsers(
        inventory(
            app("chrome", "browser"),
            app("edge", "browser"),
            running=("chrome", "edge"),
        )
    )
    assert result.active.confidence is Confidence.UNKNOWN
    assert "window title" in result.active.reason


# ======================================================================
# AI ecosystem
# ======================================================================


def test_multiple_ai_tools_running_produce_unknown() -> None:
    """The brief's 'multiple AI tools' adversarial case."""
    result = derive_ai(
        inventory(
            app("ollama", "ai"),
            app("claude_desktop", "ai"),
            running=("ollama", "claude_desktop"),
        )
    )
    assert result.preferred.confidence is Confidence.UNKNOWN
    assert "2 AI tools are running" in result.preferred.reason


def test_a_single_running_ai_tool_is_preferred() -> None:
    result = derive_ai(
        inventory(app("ollama", "ai"), app("lm_studio", "ai"), running=("ollama",))
    )
    assert result.preferred.value == "ollama"
    assert result.preferred.confidence is Confidence.OBSERVED


def test_local_and_running_are_reported_separately() -> None:
    result = derive_ai(
        inventory(
            app("ollama", "ai"),
            app("lm_studio", "ai"),
            app("cursor", "ai", status=MISSING),
            running=("ollama",),
        )
    )
    assert {t.key for t in result.local()} == {"ollama", "lm_studio"}
    assert {t.key for t in result.running()} == {"ollama"}


# ======================================================================
# Privacy — the line, and that it is structural
# ======================================================================


def test_web_ai_uses_only_the_three_permitted_values() -> None:
    result = derive_ai(inventory(app("chrome", "browser")))
    assert {w.availability for w in result.web_access} <= set(Availability)
    assert len(result.web_access) == len(WEB_AI_SERVICES)


def test_web_ai_is_unknown_when_a_browser_exists() -> None:
    """Determining a session would mean reading profile data. It is not
    read, and the reason says so rather than implying absence."""
    result = derive_ai(inventory(app("chrome", "browser")))
    for access in result.web_access:
        assert access.availability is Availability.UNKNOWN
        assert "profile data" in access.inference.reason


def test_web_ai_is_unavailable_only_when_no_browser_exists() -> None:
    """The one case real evidence settles: no browser, no web access."""
    result = derive_ai(inventory(app("git", "developer")))
    for access in result.web_access:
        assert access.availability is Availability.UNAVAILABLE
        assert access.inference.confidence is Confidence.STRONG


def test_no_service_is_ever_reported_available() -> None:
    """Nothing in a machine inventory can establish a signed-in session,
    so nothing may claim one."""
    for inv in (
        inventory(app("chrome", "browser")),
        inventory(app("git", "developer")),
        inventory(app("chrome", "browser"), app("claude_desktop", "ai")),
    ):
        for access in derive_ai(inv).web_access:
            assert access.availability is not Availability.AVAILABLE


def test_the_layer_never_reads_a_window_title() -> None:
    """`ProcessInfo` carries one, and a browser's window title is the page
    the founder is looking at."""
    assert "window_title" not in _package_identifiers()


def test_the_layer_names_no_privacy_sensitive_capability() -> None:
    """Structural: the inventory contains no cookie, credential, history
    or document, so this layer could not inspect one without first
    acquiring a capability it does not have."""
    identifiers = _package_identifiers()
    for forbidden in (
        "cookie", "cookies", "password", "credential", "history",
        "conversation", "document", "profile_path", "localstorage",
    ):
        assert not any(forbidden in name.lower() for name in identifiers), forbidden


# ======================================================================
# Never execute, launch, install or mutate
# ======================================================================


def test_the_layer_cannot_reach_the_machine() -> None:
    """No probe, no subprocess, no filesystem, no network."""
    imported = _package_imports()
    for forbidden in (
        "subprocess", "os", "shutil", "socket", "http", "urllib", "requests",
        "pathlib", "winreg", "ctypes",
    ):
        assert not any(
            name == forbidden or name.startswith(forbidden + ".")
            for name in imported
        ), forbidden


def test_the_layer_imports_no_probe() -> None:
    """The scanner's one door to the OS is `desktop.probe`. Importing
    `ProcessInfo` from it would be a type import; importing `SystemProbe`
    or `RealSystemProbe` would be the capability."""
    identifiers = _package_identifiers()
    for forbidden in ("SystemProbe", "RealSystemProbe", "CommandResult"):
        assert forbidden not in identifiers


def test_the_layer_executes_nothing() -> None:
    identifiers = _package_identifiers()
    for forbidden in (
        "run", "start", "launch", "execute", "spawn", "popen", "system",
        "install", "write", "delete", "remove", "mkdir",
    ):
        assert forbidden not in identifiers, forbidden


def test_the_layer_mutates_no_input() -> None:
    """A derivation that edited the inventory would corrupt the record the
    Desktop Executive holds."""
    inv = inventory(
        app("chrome", "browser"), app("git", "developer"), running=("chrome",)
    )
    before = inv.as_dict()
    derive_intelligence(inv)
    assert inv.as_dict() == before


# ======================================================================
# No duplicate scanner logic
# ======================================================================


def test_the_layer_defines_no_second_catalog() -> None:
    """One catalog exists, in `desktop/`. This layer imports from it."""
    imported = _package_imports()
    assert "master_agent.desktop.catalog" in imported
    identifiers = _package_identifiers()
    assert "ApplicationSpec" not in identifiers
    assert "CATALOG" not in identifiers


def test_the_layer_defines_no_second_inventory() -> None:
    imported = _package_imports()
    assert "master_agent.desktop.inventory" in imported
    identifiers = _package_identifiers()
    for forbidden in ("discover", "discover_application", "attribute_processes"):
        assert forbidden not in identifiers, forbidden


def test_the_layer_depends_only_on_the_scanner_and_itself() -> None:
    internal = {n for n in _package_imports() if n.startswith("master_agent")}
    assert all(
        n.startswith(
            ("master_agent.desktop.", "master_agent.environment_intelligence.")
        )
        for n in internal
    ), internal


def test_the_layer_touches_no_frozen_component() -> None:
    """`foundation/`, `kernel/`, `ledger/`, `coordinator/`,
    `runtime_bridge/` — none is imported."""
    imported = _package_imports()
    for frozen in (
        "master_agent.foundation", "master_agent.kernel", "master_agent.ledger",
        "master_agent.coordinator", "master_agent.runtime_bridge",
        "master_agent.api",
    ):
        assert not any(n.startswith(frozen) for n in imported), frozen


def test_the_layer_duplicates_no_kernel_vocabulary() -> None:
    identifiers = _package_identifiers()
    for owned in (
        "Warrant", "Attestation", "Receipt", "RefusalReason", "KernelRefusal",
        "ExecutionRequest", "Coverage", "CalmState",
    ):
        assert owned not in identifiers, owned


# ======================================================================
# User profile — never from one application alone
# ======================================================================


def test_one_application_never_names_a_profile() -> None:
    """The brief's hard rule."""
    result = derive_profile(inventory(app("git", "developer")))
    assert result.kind.value is None
    assert result.kind.confidence is Confidence.UNKNOWN
    assert "at least two" in result.kind.reason


def test_no_application_never_names_a_profile() -> None:
    result = derive_profile(inventory())
    assert result.kind.confidence is Confidence.UNKNOWN


def test_two_developer_applications_name_the_developer_profile() -> None:
    result = derive_profile(
        inventory(app("git", "developer"), app("python", "runtime"))
    )
    assert result.kind.value == ProfileKind.DEVELOPER.value
    assert result.kind.confidence is Confidence.STRONG
    assert len(result.kind.evidence) >= 2


def test_developer_plus_ai_is_mixed() -> None:
    """Two distinct kinds of use."""
    result = derive_profile(
        inventory(
            app("git", "developer"),
            app("python", "runtime"),
            app("claude_desktop", "ai"),
        )
    )
    assert result.kind.value == ProfileKind.MIXED.value


def test_an_unhealthy_application_does_not_evidence_a_profile() -> None:
    result = derive_profile(
        inventory(
            app("git", "developer"),
            app("python", "runtime", status=UNAVAILABLE, healthy=False),
        )
    )
    assert result.kind.confidence is Confidence.UNKNOWN


def test_the_unevidenceable_profiles_are_named_as_such() -> None:
    """Creator, office, trader and research have no catalogued
    application. Saying so is different from saying they are false."""
    result = derive_profile(
        inventory(app("git", "developer"), app("python", "runtime"))
    )
    assert result.considered
    assert "trader" in result.considered[0].reason


# ======================================================================
# Capability graph — evidence only
# ======================================================================


def test_an_installed_application_produces_a_node_and_an_edge() -> None:
    graph = derive_graph(inventory(app("python", "runtime")))
    assert graph.node("python") is not None
    assert graph.node("python.runtime") is not None
    assert graph.reaches("python", "python.runtime")


def test_a_missing_application_produces_nothing() -> None:
    graph = derive_graph(inventory(app("python", "runtime", status=MISSING)))
    assert graph.nodes == ()
    assert graph.edges == ()


def test_an_unusable_application_produces_nothing() -> None:
    graph = derive_graph(
        inventory(app("docker", "container", status=UNAVAILABLE, healthy=False))
    )
    assert graph.nodes == ()


def test_the_briefs_example_chain_stops_where_the_evidence_stops() -> None:
    """Claude Desktop → MCP → Filesystem → Trading Repository.

    The inventory carries no MCP signal, no filesystem-tool signal and no
    repository signal, so only the first hop is drawn. A graph that showed
    the rest would be describing a machine nobody looked at."""
    graph = derive_graph(inventory(app("claude_desktop", "ai")))

    assert graph.reaches("claude_desktop", "desktop.assistant")
    assert graph.node("mcp") is None
    assert not graph.reaches("claude_desktop", "trading.repository")


def test_two_applications_can_share_one_capability_node() -> None:
    graph = derive_graph(inventory(app("ollama", "ai"), app("lm_studio", "ai")))
    shared = [n for n in graph.nodes if n.key == "local.models"]
    assert len(shared) == 1
    assert len(graph.edges_from("ollama")) == 1
    assert len(graph.edges_from("lm_studio")) == 1


def test_every_edge_carries_its_evidence() -> None:
    graph = derive_graph(inventory(app("git", "developer")))
    for edge in graph.edges:
        assert edge.inference.evidence
        assert edge.inference.confidence is Confidence.OBSERVED


def test_reaches_returns_false_rather_than_assuming() -> None:
    graph = derive_graph(inventory(app("git", "developer")))
    assert not graph.reaches("git", "containers")


# ======================================================================
# Preferences
# ======================================================================


def test_the_preferred_editor_is_the_running_one() -> None:
    result = derive_preferences(
        inventory(app("cursor", "ai"), app("vscode", "developer"), running=("vscode",))
    )
    assert result.editor.value == "vscode"
    assert result.editor.confidence is Confidence.OBSERVED


def test_every_preference_is_explainable() -> None:
    result = derive_preferences(
        inventory(
            app("vscode", "developer"),
            app("chrome", "browser"),
            app("ollama", "ai"),
            app("powershell", "system"),
        )
    )
    for preference in (result.editor, result.browser, result.ai, result.terminal):
        assert preference.reason.strip()
        if preference.known:
            assert preference.evidence


def test_a_preference_with_no_candidates_is_unknown() -> None:
    result = derive_preferences(inventory())
    assert result.editor.confidence is Confidence.UNKNOWN
    assert result.terminal.confidence is Confidence.UNKNOWN


# ======================================================================
# Partial and missing environments
# ======================================================================


def test_an_empty_inventory_produces_a_complete_result() -> None:
    """Totality: every field is present, every answer is UNKNOWN, and
    nothing raises."""
    result = derive_intelligence(inventory())

    assert result.browsers.browsers == ()
    assert result.ai.tools == ()
    assert result.graph.nodes == ()
    assert result.profile.kind.confidence is Confidence.UNKNOWN
    assert result.preferences.editor.confidence is Confidence.UNKNOWN
    assert result.summary.environment_ready.confidence is Confidence.UNKNOWN


def test_a_partial_environment_reports_what_it_has() -> None:
    result = derive_intelligence(
        inventory(app("python", "runtime"), app("chrome", "browser"))
    )
    assert result.graph.node("python.runtime") is not None
    assert result.summary.developer_environment_healthy.confidence is (
        Confidence.UNKNOWN
    )
    assert "version control" in (
        result.summary.developer_environment_healthy.reason
    )


def test_a_healthy_developer_environment_is_named() -> None:
    result = derive_intelligence(
        inventory(app("python", "runtime"), app("git", "developer"))
    )
    healthy = result.summary.developer_environment_healthy
    assert healthy.value == "healthy"
    assert healthy.confidence is Confidence.STRONG


def test_uncatalogued_applications_are_surfaced_by_name() -> None:
    """Brave, Arc, Office and Copilot have no catalog entry, so the
    scanner never looked. That is different from not installed."""
    result = derive_intelligence(inventory())
    assert result.uncatalogued == UNCATALOGUED
    assert "Brave" in result.uncatalogued
    assert "Arc" in result.uncatalogued


# ======================================================================
# Summary — observations, never recommendations
# ======================================================================


def test_the_summary_recommends_nothing() -> None:
    """`desktop/inventory.py` draws this line: *"'Ollama not installed.'
    is a fact. 'Install Ollama.' is advice."*"""
    result = derive_intelligence(
        inventory(
            app("git", "developer"),
            app("python", "runtime"),
            app("chrome", "browser"),
            running=("chrome",),
        )
    )
    for line in result.summary.observations:
        lowered = line.lower()
        for advice in (
            "should", "recommend", "consider", "try ", "you could",
            "install ", "upgrade", "better", "best", "instead",
        ):
            assert advice not in lowered, line


def test_the_summary_reports_web_uncertainty_rather_than_hiding_it() -> None:
    result = derive_intelligence(inventory(app("chrome", "browser")))
    assert any("not inspected" in line for line in result.summary.observations)


def test_the_three_readiness_signals_are_present() -> None:
    """The C20 data contract the brief names."""
    result = derive_intelligence(inventory(app("git", "developer")))
    assert result.summary.environment_ready is not None
    assert result.summary.ai_available is not None
    assert result.summary.developer_environment_healthy is not None


def test_ai_available_is_unknown_without_an_ai_application() -> None:
    result = derive_intelligence(inventory(app("git", "developer")))
    assert result.summary.ai_available.confidence is Confidence.UNKNOWN


def test_ai_available_is_observed_with_one() -> None:
    result = derive_intelligence(inventory(app("ollama", "ai")))
    assert result.summary.ai_available.value == "available"
    assert result.summary.ai_available.confidence is Confidence.OBSERVED


# ======================================================================
# Determinism and the data contract
# ======================================================================


def test_the_derivation_is_deterministic() -> None:
    inv = inventory(
        app("git", "developer"), app("chrome", "browser"), running=("chrome",)
    )
    assert derive_intelligence(inv).as_dict() == derive_intelligence(inv).as_dict()


def test_the_layer_reads_no_clock() -> None:
    """`captured_at` is carried from the inventory: this describes when
    the machine was scanned, not when someone asked."""
    result = derive_intelligence(inventory(app("git", "developer")))
    assert result.captured_at == T0

    for path in PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        banned = {"datetime.now", "datetime.utcnow", "time.time"}
        assert not [
            ast.unparse(node.func)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and ".".join(ast.unparse(node.func).split(".")[-2:]) in banned
        ], path.name


def test_the_whole_result_serialises() -> None:
    """The data contract C20 Presence consumes."""
    result = derive_intelligence(
        inventory(
            app("git", "developer"),
            app("python", "runtime"),
            app("chrome", "browser"),
            app("ollama", "ai"),
            running=("chrome", "ollama"),
        )
    )
    encoded = json.dumps(result.as_dict(), sort_keys=False)
    restored = json.loads(encoded)

    assert set(restored) == {
        "browsers", "ai", "graph", "profile", "preferences", "summary",
        "captured_at", "uncatalogued",
    }
    assert restored["summary"]["environment_ready"]["confidence"]


def test_results_are_immutable() -> None:
    from dataclasses import FrozenInstanceError

    result = derive_intelligence(inventory(app("git", "developer")))
    with pytest.raises(FrozenInstanceError):
        result.profile = None


# ======================================================================
# Designed to be refreshed — structure only, no loop
# ======================================================================


def test_a_reading_is_a_moment_not_a_live_view() -> None:
    """Immutable and self-dated, so two can be held at once and told
    apart. A consumer holding an older one cannot have it change
    underneath them."""
    first = derive_intelligence(inventory(app("git", "developer")))
    second = derive_intelligence(
        inventory(app("git", "developer"), app("python", "runtime"))
    )
    assert first.profile.kind.confidence is Confidence.UNKNOWN
    assert second.profile.kind.value == ProfileKind.DEVELOPER.value


def test_refreshing_is_just_deriving_again() -> None:
    """No state to reset, no cache to invalidate, no warm-up. A later
    understanding is a new reading from a new inventory."""
    before = derive_intelligence(inventory(app("chrome", "browser")))
    after = derive_intelligence(
        inventory(app("chrome", "browser"), running=("chrome",))
    )
    assert before.browsers.preferred.confidence is Confidence.STRONG
    assert after.browsers.preferred.confidence is Confidence.OBSERVED


def test_ordering_uses_the_inventorys_moment_not_a_clock() -> None:
    later = MachineInventory(
        applications=[app("git", "developer")],
        processes=[],
        platform="win32",
        captured_at=datetime(2026, 8, 7, 12, 0, tzinfo=UTC),
    )
    first = derive_intelligence(inventory(app("git", "developer")))
    second = derive_intelligence(later)

    assert second.is_newer_than(first)
    assert not first.is_newer_than(second)


def test_an_undated_reading_is_never_newer() -> None:
    """"Unknown when" cannot be ordered against "known when"."""
    undated = MachineInventory(
        applications=[], processes=[], platform="win32", captured_at=None
    )
    a = derive_intelligence(undated)
    b = derive_intelligence(inventory(app("git", "developer")))
    assert not a.is_newer_than(b)
    assert not b.is_newer_than(a)


def test_changes_from_names_which_understanding_moved() -> None:
    """A refresh loop should act on what changed, not re-read
    everything."""
    before = derive_intelligence(inventory(app("git", "developer")))
    after = derive_intelligence(
        inventory(app("git", "developer"), app("python", "runtime"))
    )
    changed = after.changes_from(before)

    assert "profile" in changed
    assert "graph" in changed
    assert set(changed) <= set(SECTIONS)


def test_changes_from_is_empty_when_the_understanding_holds() -> None:
    """An unchanged meaning reports no change even when the moment
    differs."""
    same = derive_intelligence(inventory(app("git", "developer")))
    later = derive_intelligence(
        MachineInventory(
            applications=[app("git", "developer")],
            processes=[],
            platform="win32",
            captured_at=datetime(2026, 8, 7, tzinfo=UTC),
        )
    )
    assert later.changes_from(same) == ()
    assert later.is_newer_than(same)


def test_comparison_mutates_neither_reading() -> None:
    before = derive_intelligence(inventory(app("git", "developer")))
    after = derive_intelligence(inventory(app("python", "runtime")))
    snapshot = (before.as_dict(), after.as_dict())

    after.changes_from(before)
    after.is_newer_than(before)
    assert (before.as_dict(), after.as_dict()) == snapshot


def test_no_refresh_machinery_exists() -> None:
    """The constraint is explicit: structure for refresh, do not
    implement it. No scheduler, no timer, no polling, no cache, no
    subscription."""
    identifiers = _package_identifiers()
    for forbidden in (
        "refresh", "poll", "schedule", "subscribe", "listener", "cache",
        "interval", "sleep", "watch", "thread",
    ):
        assert not any(
            forbidden in name.lower() for name in identifiers
        ), forbidden


def test_tool_state_distinguishes_absent_from_uncatalogued() -> None:
    """VEDA 04 §5 — *I don't know* and *I haven't checked* are different
    sentences, and the distinction is a data property."""
    assert ToolState.ABSENT is not ToolState.UNCATALOGUED
    assert {s.value for s in ToolState} == {
        "usable", "unusable", "absent", "uncatalogued"
    }
