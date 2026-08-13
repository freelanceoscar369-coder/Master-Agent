"""Initial App Knowledge Profiles — ChatGPT Desktop, Kimi Desktop,
Perplexity Desktop.

Every `OBSERVED` fact below cites the specific live session/audit
document it came from, not a bare "confirmed live" — a reader (or a
future mission) can walk back to the original evidence. Every
`DOCUMENTED` fact cites the specific external source consulted; where
that source is third-party (a blog, not the vendor's own first-party
help center — no first-party ChatGPT/Kimi/Perplexity help article was
found and confirmed reachable during this session's bounded research
pass), the `source` string says so plainly rather than implying more
authority than the citation actually carries.

Perplexity Desktop was never targeted by any live automation before this
package's own live read-only validation pass (see
`docs/audits/APP_KNOWLEDGE_ACQUISITION_1.md`) — its profile here is the
pre-validation baseline; fields updated by that pass are cited to that
document, not to third-party research, wherever a real observation
superseded a merely documented or inferred one.
"""
from __future__ import annotations

from master_agent.app_knowledge.profile import AppKnowledgeProfile, Fact, KnowledgeType, unknown

CHATGPT_DESKTOP = AppKnowledgeProfile(
    provider_id="chatgpt-desktop",
    label="ChatGPT Desktop",
    last_reviewed="2026-08-13",
    chat_interface=Fact(
        value=(
            "An exact-named 'Chat' tab/pill, distinct from a 'Codex' tab, at the top of the main "
            "window -- but only on the new-chat/landing view. Confirmed live, this mission's own "
            "read-only acquisition pass: with an existing conversation open, that tab selector is "
            "not shown at all (the header instead shows the open conversation's own title); an "
            "exact-name search for 'Chat' found nothing in that state, where it had reliably "
            "matched in every prior mission's fresh-landing-page state. A caller must not assume "
            "the tab selector is always present -- its absence does not by itself mean the "
            "application is in Codex/Work mode."
        ),
        knowledge_type=KnowledgeType.OBSERVED,
        source=(
            "live UIA read, this session (docs/audits/REASONING_SESSION_E2E_ACCEPTANCE_3.md, "
            "_4.md, and this mission's own read-only acquisition pass, "
            "docs/audits/APP_KNOWLEDGE_ACQUISITION_1.md): 'Chat' and 'Codex' confirmed as two "
            "exact-name-distinct top-level tabs when present; 'chat' as a substring also matches "
            "'New chat'/'Pin chat'/'Chats', so exact-name matching (not substring) is required "
            "when it is."
        ),
    ),
    other_modes=Fact(
        value=["Codex (coding-agent surface — never a reasoning target)"],
        knowledge_type=KnowledgeType.OBSERVED,
        source=(
            "live UIA read, this session — the 'Codex' tab is present and switchable to; "
            "never navigated into or interacted with, per the coding-agent-separation rule."
        ),
    ),
    new_session_creation=Fact(
        value="A 'New chat' control on the Chat tab; documented keyboard shortcut Ctrl+Shift+O.",
        knowledge_type=KnowledgeType.DOCUMENTED,
        source=(
            "https://www.hongkiat.com/blog/chatgpt-desktop-app-keyboard-shortcuts/ (third-party, "
            "not first-party OpenAI documentation). The 'New chat' UI control itself was "
            "independently confirmed live, this session, via generic vocabulary search, not via "
            "the keyboard shortcut."
        ),
    ),
    can_rename_chat=Fact(
        value=(
            "Documented as: long-press (or right-click) the chat in the sidebar, click the "
            "pencil/rename icon, type a new name, press Enter or click outside to save."
        ),
        knowledge_type=KnowledgeType.DOCUMENTED,
        source=(
            "https://botandhuman.com/rename-chatgpt-conversation/ (third-party); not "
            "independently confirmed live this session — no rename action has ever been "
            "performed against this application."
        ),
    ),
    dedicated_session_strategy=Fact(
        value=(
            "Current production automation does not rename the session at all — it embeds the "
            "identity '[Kalpavriksha Reasoning — ChatGPT Desktop · <timestamp> · <id>]' as the "
            "first line of every submitted prompt. Renaming (see can_rename_chat) is a real, "
            "documented capability that could be used to create-once/find-thereafter a literal "
            "'Kalpavriksha Reasoning' conversation, but doing so has not been implemented or "
            "attempted — it would be new automation surface, not something this profile itself "
            "authorizes building. Caution, confirmed live this mission: a substring search for "
            "'Kalpavriksha Reasoning' *does* currently find a match in the sidebar — not a single "
            "canonically-reused session, but one specific prior mission's own conversation, which "
            "ChatGPT itself auto-titled starting with that same phrase (other past runs were "
            "auto-titled differently, e.g. 'Kalpavriksha Final Confirmation'). A caller must not "
            "treat 'a name-matching conversation exists' as proof of a genuinely dedicated, "
            "intentionally-reused session under the current architecture."
        ),
        knowledge_type=KnowledgeType.OBSERVED,
        source=(
            "src/master_agent/providers/reasoning_session.py, "
            "src/master_agent/providers/desktop_app.py (current implementation, this session); "
            "sidebar match confirmed by this mission's own read-only acquisition pass, "
            "docs/audits/APP_KNOWLEDGE_ACQUISITION_1.md."
        ),
    ),
    composer_exposure=Fact(
        value=(
            "A focusable, text-bearing element (UIA accessible name observed as 'Message ChatGPT' "
            "when empty). Exposes a `ValuePattern` whose `SetValue()` can be silently a no-op "
            "(raises nothing, changes nothing) — writes only reliably land via focus + "
            "ctrl+a/delete + keystroke-or-paste, not via `SetValue()` alone."
        ),
        knowledge_type=KnowledgeType.OBSERVED,
        source=(
            "live UIA read/write, this session (docs/audits/REASONING_SESSION_E2E_ACCEPTANCE_2.md, "
            "_3.md, _4.md)."
        ),
    ),
    send_representation=Fact(
        value="An up-arrow send-icon button beside the composer; no confirmed accessible name captured (icon-only control).",
        knowledge_type=KnowledgeType.OBSERVED,
        source=(
            "live screenshots, this session (docs/audits/REASONING_SESSION_E2E_ACCEPTANCE_4.md) — "
            "visually present in every capture; never exercised as a fallback because Enter "
            "always submitted successfully."
        ),
    ),
    enter_submits=Fact(
        value="Yes.",
        knowledge_type=KnowledgeType.OBSERVED,
        source=(
            "live runs, this session (docs/audits/REASONING_SESSION_E2E_ACCEPTANCE_3.md, _4.md) — "
            "every successful submission used Enter; the generic Send-control fallback was never "
            "needed."
        ),
    ),
    response_exposure=Fact(
        value=(
            "The assistant's reply becomes its own separate, non-focusable text element (with its "
            "own copy/like/dislike/share controls) in the conversation pane — distinct from the "
            "composer and from sidebar/navigation chrome, which can otherwise be larger and be "
            "mistaken for the response by a naive 'largest text region' heuristic."
        ),
        knowledge_type=KnowledgeType.OBSERVED,
        source=(
            "live UIA read, this session (docs/audits/EXPERT_DESKTOP_EXECUTIVE_RESPONSE_DISCOVERY_1.md) "
            "— a clean, screen-observed run captured the reply text exactly, distinct from chrome."
        ),
    ),
    persists_unsent_drafts=Fact(
        value="Yes — an unsent composer draft survives an application restart and a full machine restart.",
        knowledge_type=KnowledgeType.OBSERVED,
        source="live restart-spanning test, this session (docs/audits/REASONING_SESSION_E2E_ACCEPTANCE_2.md).",
    ),
    inactive_tabs_in_uia_tree=Fact(
        value="Yes — an inactive tab's own elements can remain mounted in the accessibility tree, merely hidden (IsOffscreen), not removed.",
        knowledge_type=KnowledgeType.OBSERVED,
        source="live UIA read, this session — the finding behind `UiaAutomationBridge.find()`'s own `visible_only` parameter.",
    ),
    visibility_distinguishing_properties=Fact(
        value="UIA's IsOffscreen property (property id 30022) reliably distinguishes a mounted-but-hidden element from a genuinely on-screen one.",
        knowledge_type=KnowledgeType.OBSERVED,
        source="live UIA read, this session; used throughout desktop/execution/uia_control.py.",
    ),
    loading_reconnection_states=Fact(
        value=[],
        knowledge_type=KnowledgeType.UNKNOWN,
        source=(
            "No loading/reconnection status text was observed for ChatGPT Desktop this session "
            "(unlike Kimi Desktop's 'Reconnecting…'); it may genuinely not surface one the same "
            "way, or one simply was never caught mid-transition."
        ),
    ),
    safe_active_session_indicator=Fact(
        value=(
            "The sidebar shows a new, distinctly-titled entry for the just-created session, "
            "separate from every prior chat listed below it — directly visually confirmed via "
            "screenshot, not merely inferred from a successful click."
        ),
        knowledge_type=KnowledgeType.OBSERVED,
        source="live screenshot evidence, this session (docs/audits/REASONING_SESSION_E2E_ACCEPTANCE_4.md).",
    ),
)

KIMI_DESKTOP = AppKnowledgeProfile(
    provider_id="kimi-desktop",
    label="Kimi Desktop",
    last_reviewed="2026-08-13",
    chat_interface=Fact(
        value="An exact-named 'Chat' tab, alongside a 'Work' tab, in the left sidebar.",
        knowledge_type=KnowledgeType.OBSERVED,
        source=(
            "live UIA read, this session (docs/audits/REASONING_SESSION_E2E_ACCEPTANCE_3.md, "
            "_4.md); independently corroborated by third-party documentation describing the "
            "same Chat/Work split: https://www.usecarly.com/blog/what-is-kimi-work/"
        ),
    ),
    other_modes=Fact(
        value=["Work (agent workspace — project/folder/permission-level based; never a reasoning target)"],
        knowledge_type=KnowledgeType.OBSERVED,
        source=(
            "live UIA read, this session; corroborated by third-party documentation — "
            "https://explainx.ai/blog/kimi-work-desktop-agent-webbridge-swarm-july-2026 and "
            "https://www.usecarly.com/blog/what-is-kimi-work/ describe 'Work' (launched "
            "2026-06-03, still labeled beta) as including local file mounting, browser "
            "automation via WebBridge, and a Cron engine — a coding/agent surface, consistent "
            "with why it is excluded as a reasoning target."
        ),
    ),
    new_session_creation=Fact(
        value=(
            "A generic 'New Task' control is the *only* reliably present 'start fresh' "
            "affordance observed in some UI states — confirmed live that Kimi Desktop can show "
            "no distinct 'New Chat' button at all even while the Chat tab is genuinely selected. "
            "In other states, a distinct 'New Chat' control (documented shortcut Ctrl+K) was "
            "also observed. Clicking either was confirmed, live, to create a genuinely new, "
            "isolated session."
        ),
        knowledge_type=KnowledgeType.OBSERVED,
        source=(
            "live UIA read, this session (docs/audits/REASONING_SESSION_E2E_ACCEPTANCE_3.md, "
            "_4.md) — both UI states directly observed across different runs of the same "
            "application."
        ),
    ),
    can_rename_chat=unknown("Not found in this session's bounded web research, and no rename action was ever performed live."),
    dedicated_session_strategy=Fact(
        value=(
            "Same approach as ChatGPT Desktop: current production automation embeds the "
            "'[Kalpavriksha Reasoning — ...]' identity in the submitted prompt text rather than "
            "renaming the session."
        ),
        knowledge_type=KnowledgeType.OBSERVED,
        source=(
            "src/master_agent/providers/reasoning_session.py, "
            "src/master_agent/providers/desktop_app.py (current implementation, this session)."
        ),
    ),
    composer_exposure=Fact(
        value=(
            "A focusable, text-bearing element whose UIA `TextPattern.DocumentRange` was observed, "
            "in one UI state (reached via the generic 'New Task' control), to concatenate a fixed, "
            "non-editable label ('Ask me. Task me.') with the real, editable content — a genuine "
            "write can land correctly while still reading back with this prefix attached. In a "
            "different UI state (the plain Chat-tab landing page), the composer instead showed a "
            "placeholder reading 'Type \"/\" to invoke plugins and skills' when empty, with no such "
            "fixed-label concatenation observed."
        ),
        knowledge_type=KnowledgeType.OBSERVED,
        source=(
            "live UIA read/write, this session (docs/audits/REASONING_SESSION_E2E_ACCEPTANCE_3.md) "
            "— this exact finding is what `UiaAutomationBridge._verify_readback()`'s "
            "containment-based comparison exists to tolerate."
        ),
    ),
    send_representation=Fact(
        value="An up-arrow send-icon button beside the composer; no confirmed accessible name captured.",
        knowledge_type=KnowledgeType.OBSERVED,
        source="live screenshots, this session — visually present; never exercised as a fallback because Enter submitted successfully.",
    ),
    enter_submits=Fact(
        value="Yes.",
        knowledge_type=KnowledgeType.OBSERVED,
        source="live runs, this session (docs/audits/REASONING_SESSION_E2E_ACCEPTANCE_3.md).",
    ),
    response_exposure=Fact(
        value=(
            "A real, correct assistant reply becomes its own named UIA element (confirmed live: an "
            "element whose accessible Name *was* the reply text itself). A naive 'largest text "
            "region' read instead frequently captured left-sidebar navigation chrome (nav items, "
            "an empty chat list, a 'Reconnecting…' status line) rather than the real reply."
        ),
        knowledge_type=KnowledgeType.OBSERVED,
        source=(
            "live UIA read, this session (docs/audits/REASONING_SESSION_E2E_ACCEPTANCE_3.md) — the "
            "finding behind `find_new_content()` replacing `find_main_content()` for response "
            "discovery."
        ),
    ),
    persists_unsent_drafts=Fact(
        value="Yes — an unsent composer draft survives an application restart and a full machine restart.",
        knowledge_type=KnowledgeType.OBSERVED,
        source="live restart-spanning test, this session (docs/audits/REASONING_SESSION_E2E_ACCEPTANCE_2.md).",
    ),
    inactive_tabs_in_uia_tree=unknown(
        "Confirmed for ChatGPT Desktop and Claude Desktop; not specifically re-verified against "
        "Kimi Desktop this session."
    ),
    visibility_distinguishing_properties=Fact(
        value="UIA's IsOffscreen property is the same generic signal used across every application in this codebase.",
        knowledge_type=KnowledgeType.INFERRED,
        source=(
            "Generalized from confirmed behavior on ChatGPT Desktop and Claude Desktop — "
            "IsOffscreen is a standard UIA property, not an application-specific implementation "
            "detail, so this is a low-risk inference, but it has not itself been directly "
            "observed against Kimi Desktop's own accessibility tree."
        ),
    ),
    loading_reconnection_states=Fact(
        value=["Your workspace is getting ready (with a 0% progress indicator)", "Reconnecting…"],
        knowledge_type=KnowledgeType.OBSERVED,
        source=(
            "live screenshots, this session (docs/audits/REASONING_SESSION_E2E_ACCEPTANCE_2.md, "
            "_3.md) — observed during cold launch and during a mid-session network interruption."
        ),
    ),
    safe_active_session_indicator=Fact(
        value=(
            "A genuinely fresh session shows the application's own idle/landing state (e.g. the "
            "'KIMI' wordmark centered, with an empty, placeholder-only composer) rather than any "
            "prior conversation's content; the sidebar's currently-highlighted chat/task entry "
            "also changes."
        ),
        knowledge_type=KnowledgeType.OBSERVED,
        source="live screenshots, this session (docs/audits/REASONING_SESSION_E2E_ACCEPTANCE_3.md).",
    ),
)

PERPLEXITY_DESKTOP = AppKnowledgeProfile(
    provider_id="perplexity-desktop",
    label="Perplexity Desktop",
    last_reviewed="2026-08-13",
    chat_interface=Fact(
        value=(
            "No separate, exact-named 'Chat' tab/section exists — confirmed live, this mission's "
            "own read-only acquisition pass: an exact-name search for 'Chat' found nothing. The "
            "application instead presents one unified surface: a single 'Ask anything…' composer "
            "with a mode dropdown ('Search') and a toggle ('Computer') beside it, no visible "
            "multi-tab Chat/Work/Codex-style split at the top level."
        ),
        knowledge_type=KnowledgeType.OBSERVED,
        source="live read-only UIA inspection + screenshot, this mission (docs/audits/APP_KNOWLEDGE_ACQUISITION_1.md).",
    ),
    other_modes=Fact(
        value=[
            "Focus mode (a search-source-scope toggle: Academic/Writing/YouTube/Reddit/Wolfram "
            "Alpha — a filter within the single chat surface, not a separate section; documented, "
            "not yet independently observed)",
            "A 'Computer' toggle observed live, directly in the composer bar next to a 'Search' "
            "mode dropdown — its exact behavior was not investigated (no click was performed, per "
            "the no-destructive-actions rule), but its presence and naming suggest a "
            "local-device/agentic capability worth the same caution as ChatGPT's 'Codex' or "
            "Kimi's 'Work' — flagged here for a future mission to characterize before ever being "
            "used as a reasoning surface, not itself confirmed unsafe or safe.",
        ],
        knowledge_type=KnowledgeType.OBSERVED,
        source=(
            "'Computer' toggle: live screenshot, this mission (docs/audits/APP_KNOWLEDGE_ACQUISITION_1.md). "
            "Focus mode: https://linuru.com/perplexity/, https://shortcut-tools.com/en/shortcuts/perplexity/ "
            "(third-party); not independently confirmed live."
        ),
    ),
    new_session_creation=Fact(
        value=(
            "Documented keyboard shortcuts: Ctrl+Shift+P or Ctrl+N for a new thread (sources "
            "disagree on which is current). A '+' icon is visible in the left sidebar in a "
            "position consistent with a 'new thread' action, but its accessible name was not "
            "queried this pass (no click was performed)."
        ),
        knowledge_type=KnowledgeType.DOCUMENTED,
        source=(
            "https://matthewcassinelli.com/shortcuts/new-thread-in-perplexity/, "
            "https://linuru.com/perplexity/ (third-party). Sidebar icon: live screenshot, this "
            "mission (docs/audits/APP_KNOWLEDGE_ACQUISITION_1.md) — visual only, not confirmed "
            "by accessible name."
        ),
    ),
    can_rename_chat=Fact(
        value="Documented for macOS via a shortcuts-editor panel; Windows desktop behavior not documented in sources found.",
        knowledge_type=KnowledgeType.DOCUMENTED,
        source="https://matthewcassinelli.com/new-shortcuts-library-perplexity/ (third-party, macOS-specific); not confirmed live, not confirmed for Windows.",
    ),
    dedicated_session_strategy=Fact(
        value="No conversation/thread named or containing 'Kalpavriksha Reasoning' exists yet — expected, since no automation has ever targeted this application.",
        knowledge_type=KnowledgeType.OBSERVED,
        source="live read-only UIA search, this mission (docs/audits/APP_KNOWLEDGE_ACQUISITION_1.md).",
    ),
    composer_exposure=Fact(
        value=(
            "`find_composer()`'s generic heuristic successfully located a composer-shaped element; "
            "its current text read as whitespace-only, consistent with the visible 'Ask anything…' "
            "placeholder (no leftover draft). Deeper structural exposure (ValuePattern writability, "
            "TextPattern concatenation quirks of the kind found on Kimi Desktop) was not "
            "investigated — doing so would require a write, which knowledge acquisition never "
            "performs."
        ),
        knowledge_type=KnowledgeType.OBSERVED,
        source="live read-only UIA inspection, this mission (docs/audits/APP_KNOWLEDGE_ACQUISITION_1.md).",
    ),
    send_representation=unknown("Not inspected this pass — a black circular icon is visible beside the composer in the screenshot but was not queried for an accessible name."),
    enter_submits=Fact(
        value="Shift+Enter is documented as 'new line' (implying, by the usual convention, that plain Enter submits) — a documented convention, not a confirmed observation for this specific application.",
        knowledge_type=KnowledgeType.DOCUMENTED,
        source="https://linuru.com/perplexity/ (third-party); not confirmed live -- confirming it would require submitting a prompt, which knowledge acquisition never does.",
    ),
    response_exposure=unknown("Not inspected this pass -- no prompt has ever been submitted to this application, so no response has ever existed to observe."),
    persists_unsent_drafts=unknown("Not inspected this pass -- the composer was found empty; whether a draft would survive a restart was not tested (would require typing first)."),
    inactive_tabs_in_uia_tree=unknown("Not inspected this pass -- no offscreen-duplicate check was run against Perplexity Desktop specifically."),
    visibility_distinguishing_properties=Fact(
        value="UIA's IsOffscreen property is the same generic, application-independent signal used throughout this codebase.",
        knowledge_type=KnowledgeType.INFERRED,
        source="Generalized from every other application already using this same standard UIA property; not itself observed against Perplexity Desktop.",
    ),
    loading_reconnection_states=Fact(
        value=[],
        knowledge_type=KnowledgeType.OBSERVED,
        source="live read-only text scan, this mission (docs/audits/APP_KNOWLEDGE_ACQUISITION_1.md) -- none visible at the moment of inspection; does not mean the application never shows one.",
    ),
    safe_active_session_indicator=unknown("Not inspected this pass -- no session has ever been created for this application, so no 'freshly created vs. reused' comparison has been made."),
)

#: Keyed by `provider_id` — the same join key `PROVIDER_CATALOG` already
#: uses, so a caller with a `ProviderSpec` in hand looks a profile up the
#: same way it looks up anything else per-application in this codebase.
APP_KNOWLEDGE_CATALOG: dict[str, AppKnowledgeProfile] = {
    profile.provider_id: profile
    for profile in (CHATGPT_DESKTOP, KIMI_DESKTOP, PERPLEXITY_DESKTOP)
}
