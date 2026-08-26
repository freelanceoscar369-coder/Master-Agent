"""Stable desktop interaction reference — what a technique *means*, when
it applies, and how you know it worked.

**Why this exists, and what it deliberately is not.** The execution ladder
already knows how to do these things: `uia_control.write_text()` tries
`ValuePattern.SetValue` first, clears with `ctrl+a`+`delete` before
replacing, verifies the clear and the write by read-back, and falls back
to physical keystrokes only as a last resort. None of that is repeated
here. What was missing was the *explanation* — the applicability, the
limits, and the provenance — so that "why did it choose that technique?"
has an answer that is not "because it was hardcoded".

This is reference DATA. It selects nothing, executes nothing, and always
loses to whatever the live control actually reports. A profile that
disagrees with the running UI is a profile to correct, never a reason to
distrust the UI.

**Layers stay separate.** Windows conventions, framework/control
semantics, and Chromium behaviour are three different subjects, and none
of them is application knowledge (`ApplicationOperationProfile`), chat
application knowledge (`app_knowledge`), or website knowledge
(`WebAiSite`).

**Provenance is not decoration.** Every entry reuses `Fact` and
`KnowledgeType` — the same four-way discipline the rest of this codebase
already enforces — so a first-party documented convention, something this
machine was actually watched doing, and an untested guess can never be
mistaken for one another. Several entries below are `OBSERVED` because
this tranche watched them happen; where a generic convention is asserted
from Microsoft's own documentation it is `DOCUMENTED` and cited; where
nothing has been established it says `UNKNOWN` rather than guessing.
"""
from __future__ import annotations

from dataclasses import dataclass

from master_agent.app_knowledge.profile import Fact, KnowledgeType

# ---- the three subjects -------------------------------------------------

WINDOWS = "windows"
UIA = "uia"
CHROMIUM = "chromium"


@dataclass(frozen=True)
class InteractionReference:
    """One interaction technique or control semantic, explained.

    `applicability` is the field that earns this type its place. A
    technique that is universally described and conditionally true is how
    an operator ends up confidently wrong — so the condition travels with
    the fact rather than in someone's memory.
    """

    topic: str
    layer: str
    meaning: str
    applicability: str
    verification: str
    fact: Fact

    @property
    def is_confirmed(self) -> bool:
        return self.fact.is_confirmed


def _observed(value: object, source: str) -> Fact:
    return Fact(value=value, knowledge_type=KnowledgeType.OBSERVED, source=source)


def _documented(value: object, source: str) -> Fact:
    return Fact(value=value, knowledge_type=KnowledgeType.DOCUMENTED, source=source)


def _unknown(source: str) -> Fact:
    return Fact(value=None, knowledge_type=KnowledgeType.UNKNOWN, source=source)


#: This tranche's own live evidence, cited by what was actually watched.
_THIS_TRANCHE = (
    "live read-only observation on the founder's Windows machine, "
    "Trusted Web closure tranche; see docs/audits/DESKTOP_BROWSER_FINAL_CLOSURE.md"
)

REFERENCES: tuple[InteractionReference, ...] = (
    # ---- Windows conventions -------------------------------------------
    InteractionReference(
        topic="foreground_vs_visible",
        layer=WINDOWS,
        meaning="A window can be visible without owning the foreground; only the "
                "foreground window receives synthesised keyboard input.",
        applicability="Always. Visibility is never evidence of focus.",
        verification="Compare the target handle against the active window at the "
                     "moment of the act, not earlier.",
        fact=_observed(
            "focus held roughly four seconds after bring_to_front succeeded before "
            "another application reclaimed it",
            _THIS_TRANCHE,
        ),
    ),
    InteractionReference(
        topic="select_all",
        layer=WINDOWS,
        meaning="Ctrl+A selects the whole contents of the focused editable control.",
        applicability="Depends on the focused control honouring the convention. It is "
                      "NOT a universal repair: a control that is not focused, or is not "
                      "editable, will not respond, and in some contexts Ctrl+A selects a "
                      "document rather than a field.",
        verification="Read the control back; a clear that cannot be read back was not "
                     "proven to have happened.",
        fact=_documented(
            "Ctrl+A = Select all",
            "Microsoft, 'Keyboard shortcuts in Windows' (support.microsoft.com) - "
            "a general Windows convention, not a per-control guarantee",
        ),
    ),
    InteractionReference(
        topic="clear_before_replace",
        layer=WINDOWS,
        meaning="Typing into a populated field inserts at the caret; replacing requires "
                "clearing first.",
        applicability="Any replacement of a complete editable value.",
        verification="Read back the emptied control before typing, then read back the "
                     "written value.",
        fact=_observed(
            "already implemented in uia_control.write_text(): ctrl+a then delete when "
            "append=False, each verified by read-back",
            "source inspection, desktop/execution/uia_control.py",
        ),
    ),
    InteractionReference(
        topic="escape_cancels",
        layer=WINDOWS,
        meaning="Escape dismisses a modal dialog or an open menu without committing.",
        applicability="Generic convention; an application may intercept it.",
        verification="Observe that the dialog or menu is gone.",
        fact=_documented(
            "Esc = Stop or leave the current task",
            "Microsoft, 'Keyboard shortcuts in Windows' (support.microsoft.com)",
        ),
    ),
    InteractionReference(
        topic="popup_menu_dismissal",
        layer=WINDOWS,
        meaning="A popup menu closes when focus leaves it; a modal dialog does not.",
        applicability="Distinguishes how long each is worth waiting for.",
        verification="Poll briefly for a menu; wait properly for a modal.",
        fact=_observed(
            "a conversation menu vanished during a 2.5s sleep on a contended desktop, "
            "while a modal opened by that menu survived and needed a longer wait",
            _THIS_TRANCHE,
        ),
    ),
    # ---- UI Automation control patterns ---------------------------------
    InteractionReference(
        topic="value_pattern",
        layer=UIA,
        meaning="ValuePattern exposes a control's value and, when not read-only, "
                "supports setting it directly.",
        applicability="Only where the element actually implements it. A Window or a "
                      "static Text element does not, and asking one for its value "
                      "yields nothing to compare against.",
        verification="Read the value back and require exact equality.",
        fact=_observed(
            "semantic value replacement succeeded first attempt on a Chromium Edit "
            "control once the correct element was targeted; no gesture was required",
            _THIS_TRANCHE,
        ),
    ),
    InteractionReference(
        topic="text_pattern",
        layer=UIA,
        meaning="TextPattern exposes document text and ranges for READING; it is not "
                "the mechanism for writing a value.",
        applicability="Read paths. Absent on many simple controls.",
        verification="Absence is a fact worth reporting, not an error to retry.",
        fact=_observed(
            "an element exposing neither TextPattern nor ValuePattern reported "
            "'NULL COM pointer access' on read - which is what an unreadable control "
            "looks like, not a failed write",
            _THIS_TRANCHE,
        ),
    ),
    InteractionReference(
        topic="control_type_identity",
        layer=UIA,
        meaning="An accessible name is not an identity. Control type distinguishes "
                "elements that share one.",
        applicability="Any target whose name may be shared. Modals commonly share a "
                      "name with their heading and their edit box.",
        verification="Confirm the resolved element's control type before acting.",
        fact=_observed(
            "a rename modal (Window 50032), its heading (Text 50020) and its field "
            "(Edit 50004) all answered to 'Rename this chat'; the name alone resolved "
            "the Window, and four write attempts failed their read-back as a result",
            _THIS_TRANCHE,
        ),
    ),
    InteractionReference(
        topic="invoke_pattern",
        layer=UIA,
        meaning="InvokePattern performs a control's single unambiguous action.",
        applicability="Controls that do one thing, such as buttons.",
        verification="Observe the effect; invocation success is not effect.",
        fact=_documented(
            "Invoke is for controls that initiate or perform a single, unambiguous action",
            "Microsoft, 'UI Automation Control Patterns Overview' (learn.microsoft.com)",
        ),
    ),
    InteractionReference(
        topic="window_pattern",
        layer=UIA,
        meaning="WindowPattern exposes window-level state such as modality.",
        applicability="Top-level and dialog windows.",
        verification="Read the state rather than assuming a dialog closed.",
        fact=_documented(
            "WindowPattern exposes window-specific state including modal and topmost",
            "Microsoft, 'UI Automation Control Patterns Overview' (learn.microsoft.com)",
        ),
    ),
    InteractionReference(
        topic="selection_patterns",
        layer=UIA,
        meaning="SelectionPattern and SelectionItemPattern describe container selection.",
        applicability="Lists, tabs and similar containers.",
        verification="Read the selected item back.",
        fact=_unknown(
            "not exercised by this tranche; the execution layer has not needed it yet, "
            "so no observed behaviour is recorded"
        ),
    ),
    InteractionReference(
        topic="scroll_toggle_expandcollapse",
        layer=UIA,
        meaning="ScrollPattern, TogglePattern and ExpandCollapsePattern describe "
                "scrolling, on/off state and disclosure.",
        applicability="Where implemented.",
        verification="Read the resulting state.",
        fact=_unknown(
            "named for completeness; not exercised, and support is whatever the "
            "execution layer actually implements, which is not these"
        ),
    ),
    # ---- Chromium -------------------------------------------------------
    InteractionReference(
        topic="triple_click",
        layer=CHROMIUM,
        meaning="A third rapid click extends selection beyond the word a double click "
                "selects.",
        applicability="CONTEXT DEPENDENT, and this is the point. In a single-line text "
                      "field it commonly selects the whole field; in document or editor "
                      "content it selects a paragraph or line. It is NOT a universal "
                      "select-all and must never be used as one.",
        verification="Read the selection or the resulting value back before replacing "
                     "anything.",
        fact=_unknown(
            "no triple-click was performed in this tranche - the rename was solved by "
            "targeting the correct Edit control, so this remains untested here and must "
            "not be promoted on the strength of general reputation"
        ),
    ),
    InteractionReference(
        topic="chromium_accessibility_availability",
        layer=CHROMIUM,
        meaning="A Chromium-family window exposes its web content through the "
                "accessibility tree, and that exposure can fail independently of the "
                "window being visible and titled.",
        applicability="Any Chromium-family browser. Behaviour varies by build.",
        verification="Attempt an observation; a readable title is not evidence the tree "
                     "is readable.",
        fact=_observed(
            "one Chromium-family browser showed the target page in its title and raised "
            "COMError on every deep accessibility enumeration, while another on the same "
            "machine was fully readable",
            _THIS_TRANCHE,
        ),
    ),
    InteractionReference(
        topic="address_bar_focus",
        layer=CHROMIUM,
        meaning="The address bar is a focusable Edit control and is also reachable by "
                "Ctrl+L.",
        applicability="Browser windows showing their normal toolbar; a profile "
                      "picker has no address bar at all.",
        verification="Confirm the control exists before typing a URL into it.",
        fact=_observed(
            "resolved semantically as an Edit named 'Address and search bar'; absent "
            "while the browser displayed its profile picker",
            _THIS_TRANCHE,
        ),
    ),
)

_BY_TOPIC = {reference.topic: reference for reference in REFERENCES}


def reference_for(topic: str) -> InteractionReference | None:
    """One technique's reference entry, or None when nothing is recorded.

    None is an ordinary answer. Most of what a desktop can do has no entry
    here and never will; this corpus covers what execution actually needs
    explained.
    """
    return _BY_TOPIC.get(topic)


def references_for_layer(layer: str) -> tuple[InteractionReference, ...]:
    return tuple(r for r in REFERENCES if r.layer == layer)


def confirmed_references() -> tuple[InteractionReference, ...]:
    """Only DOCUMENTED/OBSERVED entries — the ones safe to reason from.

    A caller narrowing its approach should consult these; an `INFERRED` or
    `UNKNOWN` entry exists to say honestly that nobody has established the
    answer, and must never be read as permission to act.
    """
    return tuple(r for r in REFERENCES if r.is_confirmed)


def explain(topic: str) -> str:
    """A human-readable answer to 'why that technique?'.

    Deliberately plain text assembled from stored data: the explanation a
    founder gets must be the knowledge the system actually held, not a
    sentence generated after the fact.
    """
    reference = reference_for(topic)
    if reference is None:
        return f"no reference knowledge is recorded for {topic!r}"
    return (
        f"{reference.topic} [{reference.layer}] — {reference.meaning}\n"
        f"  applicability: {reference.applicability}\n"
        f"  verification : {reference.verification}\n"
        f"  knowledge    : {reference.fact.knowledge_type.value} "
        f"({reference.fact.source})"
    )
