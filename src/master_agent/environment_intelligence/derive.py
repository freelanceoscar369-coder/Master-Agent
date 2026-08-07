"""Derivation — the whole of C22's logic, and none of C22's scanning.

## What this module reads, and what it must never touch

It takes a `MachineInventory` the Desktop Executive already captured, and
derives meaning from it. That is the entire input.

**It never scans.** It imports no `SystemProbe`, calls no `subprocess`,
touches no filesystem, resolves no PATH and reads no registry. The scanner
answers *"what exists?"*; this answers *"what does it mean?"*, and the
brief's rule that there must be **no second catalog and no second
inventory** is held by importing the first one and adding nothing to it.

A test asserts the forbidden imports are absent, because a promise in a
docstring is not a boundary.

## The privacy line, and exactly where it falls

The brief forbids inspecting passwords, conversations and personal
documents, and permits cookie knowledge only as far as *"existence of a
valid session"*.

**This module goes nowhere near any of them, and the reason is stronger
than compliance: the inventory does not contain them.** A
`MachineInventory` holds application names, versions, install paths and a
process list. There is no cookie in it, no history, no document and no
credential. The privacy guarantee is therefore structural — this layer
could not violate it without first acquiring a capability it does not
have.

Two consequences the brief asks about, stated rather than worked around:

**Web AI availability is `UNKNOWN`, not `AVAILABLE`.** Determining whether
a browser is logged into ChatGPT requires reading that browser's profile
data. The brief permits checking *existence* of a session; the inventory
carries no such signal, and manufacturing one would mean building the
profile reader the brief forbids elsewhere. So the answer is `UNKNOWN`
with a reason saying why — except for the one case real evidence settles:
**no browser installed means no web access**, which is `UNAVAILABLE` on
sound evidence.

**`window_title` is never read.** `ProcessInfo` carries one, and a
browser's window title is the page the founder is looking at. Reading it
to infer an "active browser" would be inspecting browsing by another
route. Activity is derived from process *names* only.

## Why several answers are `UNKNOWN`

The brief asks for inference the current evidence cannot support. Rather
than fabricate, each is returned as `UNKNOWN` carrying the reason:

| Asked for | Why it is UNKNOWN |
|---|---|
| Default browser | Needs a registry or `xdg-settings` read |
| Brave, Arc | No catalog entry exists, so the scanner never looked |
| Office, Copilot | As above |
| Web AI sessions | Would require reading browser profile data |
| Trader, Creator, Office, Research | Nothing catalogued evidences them |

Every one of these is a gap in the *evidence*, not in this module, and
`EnvironmentIntelligence.uncatalogued` surfaces the catalog ones by name.
"""
from __future__ import annotations

from master_agent.desktop.catalog import AI, BROWSER, BY_KEY
from master_agent.desktop.inventory import (
    INSTALLED,
    UNAVAILABLE,
    InstalledApplication,
    MachineInventory,
)
from master_agent.environment_intelligence.evidence import (
    Availability,
    Confidence,
    Evidence,
    Inference,
    unknown,
)
from master_agent.environment_intelligence.models import (
    AIToolProfile,
    BrowserProfile,
    CapabilityEdge,
    CapabilityGraph,
    CapabilityNode,
    EnvironmentIntelligence,
    EnvironmentSummary,
    PreferenceModel,
    ProfileKind,
    ToolObservation,
    ToolState,
    UserProfile,
    WebAIAccess,
)

#: Applications the C22 brief names that `desktop/catalog.py` has no entry
#: for. Listed so their absence is reported as *"never looked"* rather
#: than mistaken for *"not installed"* — VEDA 04 §5's distinction between
#: not knowing and not having checked.
#:
#: Adding any of them is one entry in the scanner's own catalog, which is
#: that file's documented extension point. **C22 does not add them**: the
#: brief forbids a second catalog, and editing the first is scanner work
#: rather than enrichment.
UNCATALOGUED: tuple[str, ...] = (
    "Brave",
    "Arc",
    "Microsoft Office",
    "GitHub Copilot",
)

#: Web AI services the brief names. Availability only — never a session,
#: never a credential, never a conversation.
WEB_AI_SERVICES: tuple[str, ...] = (
    "ChatGPT",
    "Claude.ai",
    "Gemini",
    "Perplexity",
    "Kimi",
    "Copilot",
)

#: Editors, most specific first. Order is precedence for the preference
#: inference, and it is declared rather than computed so a reader can see
#: it.
EDITOR_KEYS: tuple[str, ...] = ("cursor", "vscode", "visualstudio")

#: Shells the catalog knows about.
TERMINAL_KEYS: tuple[str, ...] = ("powershell", "wsl")

#: What evidences a developer environment. Two distinct hits are required
#: before the profile is named.
DEVELOPER_KEYS: tuple[str, ...] = (
    "git",
    "python",
    "node",
    "vscode",
    "cursor",
    "visualstudio",
    "docker",
    "java",
    "wsl",
    "powershell",
)


def _source(key: str) -> str:
    return f"machine_inventory.applications[{key}]"


def _state_of(application: InstalledApplication) -> ToolState:
    if application.status == INSTALLED:
        return ToolState.USABLE if application.healthy else ToolState.UNUSABLE
    if application.status == UNAVAILABLE:
        return ToolState.UNUSABLE
    return ToolState.ABSENT


def _observe(
    inventory: MachineInventory, application: InstalledApplication
) -> ToolObservation:
    """One application, as the inventory reports it. No judgement."""
    return ToolObservation(
        key=application.key,
        label=application.name,
        state=_state_of(application),
        running=len(inventory.running(application.key)) > 0,
        version=application.version,
    )


def _by_category(
    inventory: MachineInventory, category: str
) -> tuple[ToolObservation, ...]:
    return tuple(
        _observe(inventory, application)
        for application in inventory.applications
        if application.category == category
    )


def _installed_evidence(tool: ToolObservation) -> Evidence:
    version = f" {tool.version}" if tool.version else ""
    return Evidence(
        source=_source(tool.key),
        fact=f"{tool.label}{version} is installed.",
    )


def _running_evidence(tool: ToolObservation) -> Evidence:
    return Evidence(
        source=f"machine_inventory.processes[owner={tool.key}]",
        fact=f"{tool.label} has a running process.",
    )


# ─────────────────────── preference from a candidate set ───────────────


def _prefer(
    candidates: tuple[ToolObservation, ...], noun: str
) -> Inference:
    """The one the evidence points to, or `UNKNOWN` naming the conflict.

    The rule, in order, and stated so it is auditable rather than clever:

    1. **Exactly one running** → that one. Running now is the strongest
       signal a machine inventory can give, and it is `OBSERVED` because
       nothing was inferred.
    2. **Several running** → `UNKNOWN`. Two browsers open says nothing
       about preference, and picking one would be a coin toss wearing a
       confidence band.
    3. **None running, exactly one installed** → that one, `STRONG`: it is
       installed and it is the only option, which is two facts.
    4. **None running, several installed** → `UNKNOWN`, naming them.
    """
    usable = tuple(c for c in candidates if c.state is ToolState.USABLE)
    running = tuple(c for c in usable if c.running)

    if len(running) == 1:
        chosen = running[0]
        return Inference(
            value=chosen.key,
            confidence=Confidence.OBSERVED,
            reason=(
                f"{chosen.label} is the only {noun} running, so it is the one "
                "in use."
            ),
            evidence=(_installed_evidence(chosen), _running_evidence(chosen)),
        )

    if len(running) > 1:
        names = ", ".join(c.label for c in running)
        return unknown(
            f"{len(running)} {noun}s are running ({names}); nothing in the "
            "inventory distinguishes which is preferred."
        )

    if len(usable) == 1:
        only = usable[0]
        return Inference(
            value=only.key,
            confidence=Confidence.STRONG,
            reason=(
                f"{only.label} is the only usable {noun} installed, so it is "
                "the only one that can be used."
            ),
            evidence=(_installed_evidence(only),),
        )

    if len(usable) > 1:
        names = ", ".join(c.label for c in usable)
        return unknown(
            f"{len(usable)} {noun}s are installed ({names}) and none is "
            "running; no evidence distinguishes them."
        )

    return unknown(f"no usable {noun} is installed.")


# ─────────────────────────── 1 · browsers ──────────────────────────────


def derive_browsers(inventory: MachineInventory) -> BrowserProfile:
    """Browser intelligence from the inventory, and nothing else."""
    browsers = _by_category(inventory, BROWSER)
    running = tuple(b for b in browsers if b.running)

    if len(running) == 1:
        only = running[0]
        active = Inference(
            value=only.key,
            confidence=Confidence.OBSERVED,
            reason=f"{only.label} has a running process.",
            evidence=(_running_evidence(only),),
        )
    elif len(running) > 1:
        names = ", ".join(b.label for b in running)
        active = unknown(
            f"{len(running)} browsers are running ({names}); the inventory "
            "does not say which has focus, and reading a window title to "
            "find out would be inspecting browsing."
        )
    else:
        active = unknown("no browser process is running.")

    return BrowserProfile(
        browsers=browsers,
        preferred=_prefer(browsers, "browser"),
        default=unknown(
            "the machine inventory carries no operating-system default "
            "handler; determining it would need a registry or xdg-settings "
            "read the scanner does not perform."
        ),
        active=active,
    )


# ─────────────────────────── 2 · AI ecosystem ──────────────────────────


def derive_ai(inventory: MachineInventory) -> AIToolProfile:
    """The AI ecosystem: local applications, and web reachability."""
    tools = _by_category(inventory, AI)
    browsers = _by_category(inventory, BROWSER)
    has_browser = any(b.state is ToolState.USABLE for b in browsers)

    if has_browser:
        reachable = unknown(
            "a browser is installed, but determining whether it holds a "
            "signed-in session would require reading its profile data, "
            "which this layer does not do."
        )
        availability = Availability.UNKNOWN
    else:
        reachable = Inference(
            value="unavailable",
            confidence=Confidence.STRONG,
            reason=(
                "no usable browser is installed, so no web service can be "
                "reached from this machine."
            ),
            evidence=(
                Evidence(
                    source="machine_inventory.applications[category=browser]",
                    fact="No usable browser is installed.",
                ),
            ),
        )
        availability = Availability.UNAVAILABLE

    web_access = tuple(
        WebAIAccess(service=service, availability=availability, inference=reachable)
        for service in WEB_AI_SERVICES
    )

    return AIToolProfile(
        tools=tools,
        preferred=_prefer(tools, "AI tool"),
        web_access=web_access,
    )


# ─────────────────────────── 3 · capability graph ──────────────────────

#: What an installed application demonstrably provides. Each entry is a
#: capability the application's own presence establishes — nothing here
#: claims a capability that needs a second fact to be true.
_PROVIDES: tuple[tuple[str, str, str], ...] = (
    ("python", "python.runtime", "Python runtime"),
    ("node", "node.runtime", "Node runtime"),
    ("java", "java.runtime", "Java runtime"),
    ("git", "vcs", "Version control"),
    ("docker", "containers", "Container runtime"),
    ("wsl", "linux.subsystem", "Linux subsystem"),
    ("powershell", "shell", "Shell"),
    ("ollama", "local.models", "Local model serving"),
    ("lm_studio", "local.models", "Local model serving"),
    ("claude_desktop", "desktop.assistant", "Desktop assistant"),
    ("cursor", "desktop.assistant", "Desktop assistant"),
    ("chrome", "web.access", "Web access"),
    ("edge", "web.access", "Web access"),
    ("firefox", "web.access", "Web access"),
)


def derive_graph(inventory: MachineInventory) -> CapabilityGraph:
    """What this environment can do, drawn only where evidence reaches.

    An application node exists when the inventory says the application is
    installed. A capability node exists when at least one installed
    application provides it. An edge exists only between those two.

    **The brief's illustrative chain stops where the evidence stops.**
    Claude Desktop → MCP → Filesystem → Trading Repository is drawn as far
    as `Claude Desktop → Desktop assistant` and no further: the inventory
    carries no MCP signal, no filesystem-tool signal, and no repository
    signal, so those three edges are not drawn. A graph that showed them
    would be describing a machine nobody looked at.
    """
    nodes: list[CapabilityNode] = []
    edges: list[CapabilityEdge] = []
    capability_seen: set[str] = set()

    for key, capability_key, capability_label in _PROVIDES:
        application = inventory.get(key)
        if application is None or not application.installed:
            continue
        tool = _observe(inventory, application)
        if tool.state is not ToolState.USABLE:
            continue

        spec = BY_KEY.get(key)
        label = spec.label if spec is not None else key
        evidence = _installed_evidence(tool)

        if inventory.get(key) is not None and not any(n.key == key for n in nodes):
            nodes.append(
                CapabilityNode(
                    key=key,
                    label=label,
                    inference=Inference(
                        value=key,
                        confidence=Confidence.OBSERVED,
                        reason=f"{label} is installed and usable.",
                        evidence=(evidence,),
                    ),
                )
            )

        if capability_key not in capability_seen:
            capability_seen.add(capability_key)
            nodes.append(
                CapabilityNode(
                    key=capability_key,
                    label=capability_label,
                    inference=Inference(
                        value=capability_key,
                        confidence=Confidence.OBSERVED,
                        reason=(
                            f"{capability_label} is provided by an installed "
                            "application."
                        ),
                        evidence=(evidence,),
                    ),
                )
            )

        edges.append(
            CapabilityEdge(
                source=key,
                target=capability_key,
                inference=Inference(
                    value=capability_key,
                    confidence=Confidence.OBSERVED,
                    reason=f"{label} provides {capability_label.lower()}.",
                    evidence=(evidence,),
                ),
            )
        )

    return CapabilityGraph(nodes=tuple(nodes), edges=tuple(edges))


# ─────────────────────────── 4 · user profile ──────────────────────────


def derive_profile(inventory: MachineInventory) -> UserProfile:
    """What kind of environment this is, from at least two applications.

    The brief's rule — *"never infer from a single application alone"* —
    is enforced structurally: a kind is named only when **two or more
    distinct** installed applications evidence it, and both appear in the
    inference.

    With the current catalog only `DEVELOPER` is evidenceable. Creator,
    Office User, Trader and Research User have no catalogued application
    that would establish them, so none is claimed and the reason says so.
    `MIXED` is returned when developer evidence exists alongside AI
    tooling, because that is a second distinct kind of use.
    """
    hits = tuple(
        _observe(inventory, application)
        for key in DEVELOPER_KEYS
        if (application := inventory.get(key)) is not None
        and application.status == INSTALLED
        and application.healthy
    )

    if len(hits) < 2:
        found = ", ".join(h.label for h in hits) if hits else "nothing"
        return UserProfile(
            kind=unknown(
                f"only {len(hits)} catalogued application evidences a profile "
                f"({found}); at least two are required before naming one."
            )
        )

    evidence = tuple(_installed_evidence(h) for h in hits)
    names = ", ".join(h.label for h in hits)

    ai_running = tuple(
        t for t in _by_category(inventory, AI) if t.state is ToolState.USABLE
    )
    if ai_running:
        kind = ProfileKind.MIXED
        reason = (
            f"{len(hits)} developer applications are installed ({names}) "
            f"alongside {len(ai_running)} AI application(s), which is two "
            "distinct kinds of use."
        )
        evidence = evidence + tuple(_installed_evidence(t) for t in ai_running)
    else:
        kind = ProfileKind.DEVELOPER
        reason = f"{len(hits)} developer applications are installed ({names})."

    considered = (
        unknown(
            "creator, office, trader and research profiles have no "
            "catalogued application that would evidence them."
        ),
    )

    return UserProfile(
        kind=Inference(
            value=kind.value,
            confidence=Confidence.STRONG,
            reason=reason,
            evidence=evidence,
        ),
        considered=considered,
    )


# ─────────────────────────── 5 · preferences ───────────────────────────


def derive_preferences(inventory: MachineInventory) -> PreferenceModel:
    """Four preferences, each explainable, none asked for."""
    editors = tuple(
        _observe(inventory, application)
        for key in EDITOR_KEYS
        if (application := inventory.get(key)) is not None
    )
    terminals = tuple(
        _observe(inventory, application)
        for key in TERMINAL_KEYS
        if (application := inventory.get(key)) is not None
    )

    return PreferenceModel(
        editor=_prefer(editors, "editor"),
        browser=_prefer(_by_category(inventory, BROWSER), "browser"),
        ai=_prefer(_by_category(inventory, AI), "AI tool"),
        terminal=_prefer(terminals, "terminal"),
    )


# ─────────────────────────── 6 · summary ───────────────────────────────


def derive_summary(
    browsers: BrowserProfile,
    ai: AIToolProfile,
    graph: CapabilityGraph,
    profile: UserProfile,
) -> EnvironmentSummary:
    """Structured observations and the three C20 readiness signals.

    Every line is a statement about what is. Nothing here recommends,
    ranks, or urges — `desktop/inventory.py` draws that line and this
    holds it.
    """
    observations: list[str] = []

    for tool in ai.tools:
        if tool.state is ToolState.USABLE:
            observations.append(
                f"{tool.label} {'running' if tool.running else 'installed'}."
            )

    for browser in browsers.browsers:
        if browser.state is ToolState.USABLE and browser.running:
            observations.append(f"{browser.label} running.")

    if browsers.preferred is not None and browsers.preferred.known:
        observations.append(f"{browsers.preferred.value} preferred browser.")

    for node in graph.nodes:
        if node.key in {"python.runtime", "containers", "local.models"}:
            observations.append(f"{node.label} available.")

    web_unknown = sum(
        1 for w in ai.web_access if w.availability is Availability.UNKNOWN
    )
    if web_unknown:
        observations.append(
            f"{web_unknown} web AI services unknown; session state is not "
            "inspected."
        )

    usable_ai = tuple(t for t in ai.tools if t.state is ToolState.USABLE)
    if usable_ai:
        ai_available = Inference(
            value="available",
            confidence=Confidence.OBSERVED,
            reason=(
                f"{len(usable_ai)} AI application(s) are installed and usable."
            ),
            evidence=tuple(_installed_evidence(t) for t in usable_ai),
        )
    else:
        ai_available = unknown(
            "no AI application is installed and usable, and web session "
            "state is not inspected."
        )

    python = graph.node("python.runtime")
    vcs = graph.node("vcs")
    if python is not None and vcs is not None:
        healthy = Inference(
            value="healthy",
            confidence=Confidence.STRONG,
            reason="a language runtime and version control are both present.",
            evidence=python.inference.evidence + vcs.inference.evidence,
        )
    else:
        missing = []
        if python is None:
            missing.append("a language runtime")
        if vcs is None:
            missing.append("version control")
        healthy = unknown(
            "a developer environment cannot be confirmed: "
            + " and ".join(missing)
            + " not found."
        )

    if graph.nodes and profile.kind.known:
        ready = Inference(
            value="ready",
            confidence=Confidence.weakest(
                Confidence.OBSERVED, profile.kind.confidence
            ),
            reason=(
                f"{len(graph.nodes)} capability node(s) are evidenced and the "
                "environment resolves to a named profile."
            ),
            evidence=profile.kind.evidence,
        )
    else:
        ready = unknown(
            "the environment has too little evidence to be called ready: "
            f"{len(graph.nodes)} capability node(s), profile "
            f"{profile.kind.confidence.value}."
        )

    return EnvironmentSummary(
        observations=tuple(observations),
        environment_ready=ready,
        ai_available=ai_available,
        developer_environment_healthy=healthy,
    )


# ─────────────────────────── the entry point ───────────────────────────


def derive_intelligence(inventory: MachineInventory) -> EnvironmentIntelligence:
    """Everything C22 derives, from one inventory the scanner captured.

    Pure. Given the same inventory twice, returns equal results — there is
    no clock, no randomness and no I/O anywhere beneath this call.

    `captured_at` is carried from the inventory rather than read from a
    clock: this describes the moment the machine was scanned, not the
    moment someone asked about it.
    """
    browsers = derive_browsers(inventory)
    ai = derive_ai(inventory)
    graph = derive_graph(inventory)
    profile = derive_profile(inventory)
    preferences = derive_preferences(inventory)
    summary = derive_summary(browsers, ai, graph, profile)

    return EnvironmentIntelligence(
        browsers=browsers,
        ai=ai,
        graph=graph,
        profile=profile,
        preferences=preferences,
        summary=summary,
        captured_at=inventory.captured_at,
        uncatalogued=UNCATALOGUED,
    )
