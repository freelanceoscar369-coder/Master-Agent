"""Roadmap-derived presentation data (Mission Brief 029).

MB029's Deliverables 5, 6, and 8 all say the same thing: the founder view
must show what *should* exist, not only what does — which Executives are
planned, how far the build has got, and what to do next. None of that is
runtime state. It is what `ROADMAP.md` says.

**So it is declared here, once, and nothing computes it.** A progress bar
invented from a heuristic would be fabrication, and this project's
standing rule (ADR-0016) is that a plausible-looking number is worse than
an honest absence. These tables are a *transcription of the roadmap*, and
they are correct exactly as long as someone updates them when the roadmap
moves — which is why every entry names its source.

The one thing that is live: an Executive's readiness is checked against
what is actually registered, so "Ready" is never a claim this file makes.
"""
from __future__ import annotations

from dataclasses import dataclass

#: Status vocabulary for an Executive on the founder view.
READY = "Ready"
MISSING = "Missing"
PLANNED = "Planned"


@dataclass(frozen=True)
class ExpectedExecutive:
    """One Executive the roadmap says should exist.

    `executive_id` is what it registers as (so readiness can be checked
    live). `planned` marks the ones that are not built yet and are not
    supposed to be — the difference between "Missing" (should be here,
    isn't) and "Planned" (not due yet), which is the difference between
    something being wrong and something being unfinished.
    """

    label: str
    executive_id: str
    planned: bool = False
    source: str = ""


#: Transcribed from `ROADMAP.md` — Completed (022, 005) and Planned (6, 7).
EXPECTED_EXECUTIVES: tuple[ExpectedExecutive, ...] = (
    ExpectedExecutive("Filesystem", "filesystem", source="MB005, shipped"),
    ExpectedExecutive("Browser", "browser", source="MB022, shipped"),
    ExpectedExecutive(
        "Desktop", "desktop", planned=True, source="ROADMAP Future — not scheduled"
    ),
    ExpectedExecutive(
        "AI Broker", "ai_broker", planned=True, source="ROADMAP Planned item 6"
    ),
    ExpectedExecutive(
        "Reasoning", "reasoning", planned=True, source="ROADMAP Planned item 1"
    ),
)


@dataclass(frozen=True)
class RoadmapPhase:
    """One build phase and how far it has got, 0.0–1.0.

    Transcribed, not computed. `basis` records what the number is a
    reading of, so a founder can check it and a future session can update
    it honestly instead of nudging a bar.
    """

    label: str
    fraction: float
    basis: str


#: Read from `MIRACLE_LEDGER.md` and `ROADMAP.md` as of MB029.
SELF_DEVELOPMENT_PHASES: tuple[RoadmapPhase, ...] = (
    RoadmapPhase(
        "Architecture",
        0.8,
        "Constitution frozen; 20 ADRs; Broker + Learning Loop designed, "
        "Desktop and Capability Packages not yet",
    ),
    RoadmapPhase(
        "Implementation",
        0.6,
        "Mission Control, Runtime, Persistence, Dashboard, Launcher, "
        "Approval Workflow shipped; Broker, Planner, Desktop not",
    ),
    RoadmapPhase(
        "Testing",
        1.0,
        "1051 passing, 1 skipped, zero known regressions",
    ),
    RoadmapPhase(
        "Documentation",
        0.8,
        "Every Miracle has a brief and an architecture doc; no founder "
        "user guide yet",
    ),
)


@dataclass(frozen=True)
class RoadmapRecommendation:
    """A next step the roadmap already names.

    `requires_missing` gates it on live state: there is no point
    recommending an Executive that is already registered, and a
    recommendation a founder has already acted on is noise.
    """

    text: str
    requires_missing: str | None = None
    source: str = ""


#: Transcribed from `ROADMAP.md` "Planned — next up", in its order.
RECOMMENDATIONS: tuple[RoadmapRecommendation, ...] = (
    RoadmapRecommendation(
        "Implement the AI Capability Broker",
        requires_missing="ai_broker",
        source="ROADMAP Planned item 6",
    ),
    RoadmapRecommendation(
        "Build the real Planner (replace cli.py's regex stand-in)",
        requires_missing="reasoning",
        source="ROADMAP Planned item 1",
    ),
    RoadmapRecommendation(
        "Build the Desktop Executive",
        requires_missing="desktop",
        source="ROADMAP Future — non-filesystem local actions",
    ),
    RoadmapRecommendation(
        "Ratify or reject ADR-0015 and ADR-0020",
        source="ROADMAP Backlog — founder decisions, not defaults",
    ),
)

#: Shown when every gated recommendation has been satisfied. MB029
#: Deliverable 8 asks for this case explicitly, and it should be a real
#: answer rather than an empty panel.
NOTHING_NEEDED = "Nothing needed - everything on the roadmap is under way"
