"""App Knowledge Acquisition — safe, read-only confirmation of a
profile's claims (and discovery of a few new ones) against a real,
already-running application window.

**Absolute rule, enforced structurally, not by convention:** every method
here calls only read-only `UiaAutomationBridge` methods —
`find()`/`find_composer()`/`find_main_content()`/`find_new_content()`/
`snapshot_text_regions()`/`read_text()`/`describe()`. None of them ever
call `write_text()`, `click()`, or reach for a `KeyboardController`/
`MouseController` at all — those parameters simply do not exist on this
module's own functions, so there is no code path here that *could*
type, click, or submit anything. `tests/test_app_knowledge_acquisition.py`
has a dedicated regression guard for exactly this using a fake bridge
that raises if any mutating method is even looked up.

**Coding-agent separation applies here too.** `acquire_knowledge()`
refuses outright for any `is_coding_agent(spec)` spec, before touching
the machine at all — the same structural gate
`DesktopAppReasoningProvider.complete()` already applies at its own
step -1, reused here rather than re-derived, because "never interact
with a coding-agent session" is a rule about *this whole codebase*, not
one specific to reasoning `complete()` calls.

**What this produces.** A `dict[str, Fact]` of freshly `OBSERVED` facts,
keyed by *check* name (`"chat_tab_exact_match_present"`, not a profile
field name like `"chat_interface"`) — deliberately not
`AppKnowledgeProfile.merge_observations()`-ready as-is. A raw existence
check ("is there an exact-name 'Chat' element right now") is narrower
than the rich, structural knowledge a profile field like
`chat_interface` carries; auto-merging one into the other would silently
replace real structural description with a bare boolean the moment
acquisition runs. Translating a raw check result into an updated,
still-descriptive profile `Fact` is left as a deliberate step for the
caller (see `docs/audits/APP_KNOWLEDGE_ACQUISITION_1.md` for how this
session's own live validation pass did exactly that) — never automatic.
`merge_observations()` itself still exists and is still exercised by
tests; this module just does not assume its own output is a drop-in
argument for it.
"""
from __future__ import annotations

from master_agent.ai_infrastructure.catalog import ProviderSpec, is_coding_agent
from master_agent.app_knowledge.profile import Fact, KnowledgeType
from master_agent.desktop.execution.uia_control import UiaTargetNotFound, UiaUnavailable

#: A generic (not one application's own wording), case-insensitive
#: vocabulary of loading/reconnection status phrasing — found live, this
#: session, in Kimi Desktop's own real UI ("Reconnecting…", "Your
#: workspace is getting ready"). Used only to *detect and record* such a
#: state during acquisition, never to branch production automation on
#: one application's specific wording.
_LOADING_KEYWORDS = ("reconnecting", "getting ready", "loading", "connecting")

#: The dedicated reasoning session's required name — see the mission's
#: own rule #2. Acquisition only ever *searches* for this name (a read),
#: never creates or renames anything to match it.
DEDICATED_SESSION_NAME = "Kalpavriksha Reasoning"


class CodingAgentAcquisitionRefused(RuntimeError):
    """Raised by `acquire_knowledge()` when asked to inspect a
    coding-agent spec — refused before any machine interaction, the same
    posture `complete()`'s own step -1 already takes."""


def check_chat_tab(bridge, handle: int) -> Fact:
    """Read-only: does an exact-name 'Chat' tab exist and resolve to a
    visible element right now? A negative result is still a real
    observation (some applications, or some of their UI states, may not
    expose a distinctly-named Chat tab at all) — never silently dropped."""
    try:
        bridge.find(handle, name_exact="Chat", visible_only=True, retries=0)
        return Fact(
            value=True, knowledge_type=KnowledgeType.OBSERVED,
            source="live read-only UIA find(name_exact='Chat', visible_only=True)",
        )
    except (UiaTargetNotFound, UiaUnavailable) as exc:
        return Fact(
            value=False, knowledge_type=KnowledgeType.OBSERVED,
            source="live read-only UIA find(name_exact='Chat', visible_only=True)",
            note=f"no visible exact-name 'Chat' element found at the time of inspection ({exc})",
        )


def check_dedicated_session_present(bridge, handle: int) -> Fact:
    """Read-only: does a chat/session literally named 'Kalpavriksha
    Reasoning' already exist and resolve to a visible element? Informs
    step 5 of the mission's own runtime decision order ("create or
    locate the dedicated session") without itself creating or renaming
    anything."""
    try:
        bridge.find(handle, name_contains=DEDICATED_SESSION_NAME, visible_only=True, retries=0)
        return Fact(
            value=True, knowledge_type=KnowledgeType.OBSERVED,
            source=f"live read-only UIA find(name_contains={DEDICATED_SESSION_NAME!r}, visible_only=True)",
        )
    except (UiaTargetNotFound, UiaUnavailable):
        return Fact(
            value=False, knowledge_type=KnowledgeType.OBSERVED,
            source=f"live read-only UIA find(name_contains={DEDICATED_SESSION_NAME!r}, visible_only=True)",
            note="no dedicated 'Kalpavriksha Reasoning' session found at the time of inspection",
        )


def check_composer_current_text(bridge, handle: int) -> Fact:
    """Read-only: locates the composer (via `find_composer()`'s own
    generic heuristic) and reads its *current* text — never writes,
    never clears. The reading may be a genuine empty-state placeholder or
    a leftover unsent draft; this method does not attempt to tell them
    apart (that distinction belongs to the mission's own "unsent draft is
    not conversation history" rule, applied at write time, not read
    time) — it only records what is actually there right now."""
    try:
        composer = bridge.find_composer(handle)
        text = bridge.read_text(composer)
        return Fact(
            value=text, knowledge_type=KnowledgeType.OBSERVED,
            source="live read-only UIA find_composer() + read_text()",
            note="current content only -- may be an empty-state placeholder or a leftover unsent draft; not distinguished here",
        )
    except (UiaTargetNotFound, UiaUnavailable) as exc:
        return Fact(
            value=None, knowledge_type=KnowledgeType.OBSERVED,
            source="live read-only UIA find_composer()",
            note=f"no composer-shaped element could be located at the time of inspection ({exc})",
        )


def check_offscreen_duplicates(bridge, handle: int, name_contains: str) -> Fact:
    """Read-only: for a given name fragment (e.g. 'chat'), compares an
    unfiltered match against a `visible_only` match — a difference means
    at least one same-named element is currently mounted but hidden
    (an inactive tab's own control, most commonly). Informs whether a
    caller must use `visible_only=True` when searching this application
    for that name, without itself resolving the ambiguity."""
    try:
        bridge.find(handle, name_contains=name_contains, visible_only=False, retries=0)
        any_match = True
    except (UiaTargetNotFound, UiaUnavailable):
        any_match = False
    try:
        bridge.find(handle, name_contains=name_contains, visible_only=True, retries=0)
        visible_match = True
    except (UiaTargetNotFound, UiaUnavailable):
        visible_match = False
    hidden_duplicate_exists = any_match and not visible_match
    return Fact(
        value=hidden_duplicate_exists, knowledge_type=KnowledgeType.OBSERVED,
        source=f"live read-only UIA find(name_contains={name_contains!r}) with and without visible_only",
        note="True means a same-named element exists but is currently off-screen -- visible_only matching is required for this name",
    )


def check_loading_state(bridge, handle: int) -> Fact:
    """Read-only: scans every currently-visible text region (via
    `snapshot_text_regions()`, itself read-only) for generic
    loading/reconnection wording. A hit is recorded as observed evidence
    that this application *can* show such a state, not proof it always
    will — this only reports what was seen during this one inspection."""
    try:
        regions = bridge.snapshot_text_regions(handle)
    except (UiaTargetNotFound, UiaUnavailable) as exc:
        return Fact(
            value=[], knowledge_type=KnowledgeType.OBSERVED,
            source="live read-only UIA snapshot_text_regions()",
            note=f"could not scan the window's visible text at the time of inspection ({exc})",
        )
    hits = sorted({
        text.strip() for text in regions.values()
        if text and any(keyword in text.lower() for keyword in _LOADING_KEYWORDS)
    })
    return Fact(
        value=hits, knowledge_type=KnowledgeType.OBSERVED,
        source="live read-only UIA snapshot_text_regions(), scanned for generic loading/reconnection wording",
        note="empty means no such text was visible at the moment of this one inspection, not that the application never shows one",
    )


def acquire_knowledge(spec: ProviderSpec, bridge, handle: int) -> dict[str, Fact]:
    """Run every safe, read-only check above against one real, already
    focused application window, returning freshly `OBSERVED` facts keyed
    by check name — see this module's own docstring for why that is
    deliberately *not* the same as a profile field name. Refuses
    immediately — before any machine interaction — for a coding-agent
    spec."""
    if is_coding_agent(spec):
        raise CodingAgentAcquisitionRefused(
            f"{spec.provider_id!r} is a coding-agent identity — knowledge acquisition, "
            "like reasoning selection, never targets one."
        )
    return {
        "chat_tab_exact_match_present": check_chat_tab(bridge, handle),
        "dedicated_reasoning_session_present": check_dedicated_session_present(bridge, handle),
        "composer_current_text": check_composer_current_text(bridge, handle),
        "loading_or_reconnection_text_visible": check_loading_state(bridge, handle),
    }
