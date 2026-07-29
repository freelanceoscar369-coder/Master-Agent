"""Architecture / Constitution Compliance tests -- mechanically verifies
claims BROWSER_WORKER_ARCHITECTURE.md makes in prose, so they can't
silently drift false. See KALPAVRIKSHA_VISION_V2.md §14 (Product
Agnosticism) and Mission Brief 022's explicit "if a product name appears
anywhere... treat it as an architectural violation" rule.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from master_agent.plugins.browser_worker import BrowserWorker
from master_agent.verification import verifier as verifier_module

REPO_ROOT = Path(__file__).resolve().parent.parent

# Word-boundary matching, not bare substrings -- a naive substring scan for
# one of the forbidden names would false-positive on the word "Knowledge"
# (which ends in the same four letters as one forbidden browser name), an
# approved Constitution term this Mission Brief's own architecture uses
# throughout. See docs/MISSION_BRIEF_022.md for why this distinction
# matters. (For the same reason, this file avoids spelling out that
# ordinary English word as a standalone word anywhere in its own prose --
# see the forbidden-name list itself, a few lines below, for the one
# place it has to appear literally.)
FORBIDDEN_NAMES = [
    "google",
    "github",
    "chatgpt",
    "claude",
    "amazon",
    "facebook",
    "linkedin",
    "sap",
    "salesforce",
    "vs code",
    "chrome",
    "edge",
    "firefox",
]
_FORBIDDEN_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(name) for name in FORBIDDEN_NAMES) + r")\b", re.IGNORECASE
)

THIS_FILE = Path(__file__).resolve()

# Every file this Mission Brief's Browser Worker touches, scanned for
# forbidden product names -- except this file itself, which necessarily
# spells those names out literally in FORBIDDEN_NAMES below in order to
# check for them. That list is the one place they're allowed to appear;
# everywhere else (the other test files, the source, the architecture
# doc) is held to the real rule.
BROWSER_WORKER_FILES = [
    path
    for path in [
        REPO_ROOT / "BROWSER_WORKER_ARCHITECTURE.md",
        *sorted((REPO_ROOT / "src/master_agent/environment").glob("*.py")),
        *sorted((REPO_ROOT / "src/master_agent/verification").glob("*.py")),
        *sorted((REPO_ROOT / "src/master_agent/executor/actions/browser").glob("*.py")),
        *sorted((REPO_ROOT / "src/master_agent/plugins").glob("browser_*.py")),
        *sorted((REPO_ROOT / "tests").glob("test_browser_*.py")),
        REPO_ROOT / "tests" / "browser_test_support.py",
    ]
    if path.resolve() != THIS_FILE
]

# Modules that must never reference Playwright at all, per
# BROWSER_WORKER_ARCHITECTURE.md §9 -- the generic verification/ package
# and the Worker's own Plugin/Verifier/facade layer, which exist precisely
# so a future non-browser Worker can reuse them unchanged. (Some Action
# files, e.g. close_session.py/observe.py, also happen not to reference
# Playwright directly today -- they delegate to BrowserSessionManager/
# normalize_observation instead -- but that's an implementation detail,
# not an architectural guarantee this suite pins down.)
PLAYWRIGHT_FORBIDDEN_MODULES = {
    "master_agent.verification.evidence",
    "master_agent.verification.evaluator",
    "master_agent.verification.verifier",
    "master_agent.verification.audit",
    "master_agent.plugins.browser_verifier",
    "master_agent.plugins.browser_plugin",
    "master_agent.plugins.browser_worker",
}


@pytest.mark.parametrize("path", BROWSER_WORKER_FILES, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_no_forbidden_product_name_appears_anywhere(path: Path):
    assert path.exists(), f"expected file missing: {path}"
    text = path.read_text(encoding="utf-8")
    match = _FORBIDDEN_PATTERN.search(text)
    assert match is None, f"forbidden product name '{match.group(0)}' found in {path}"


@pytest.mark.parametrize("module_path", sorted(PLAYWRIGHT_FORBIDDEN_MODULES))
def test_generic_and_facade_modules_never_import_playwright(module_path: str):
    source = (REPO_ROOT / ("src/" + module_path.replace(".", "/") + ".py")).read_text(encoding="utf-8")
    assert "playwright" not in source.lower(), (
        f"{module_path} must never import playwright directly -- "
        "see BROWSER_WORKER_ARCHITECTURE.md §9"
    )


def test_browser_worker_has_no_reasoning_planning_or_knowledge_methods():
    """The Worker must never reason, plan, retry strategically, change the
    Mission, learn, or promote Knowledge -- Mission Brief 022's explicit
    'Browser Worker Responsibilities' boundary."""
    forbidden_method_names = {
        "plan",
        "replan",
        "re_plan",
        "retry",
        "learn",
        "promote",
        "promote_knowledge",
        "decide",
        "reason",
    }
    actual_methods = {name for name in dir(BrowserWorker) if not name.startswith("_")}
    overlap = actual_methods & forbidden_method_names
    assert not overlap, f"BrowserWorker exposes reasoning/planning-shaped methods: {overlap}"


def test_browser_worker_public_surface_is_exactly_run_step_and_audit_log():
    public_members = {name for name in dir(BrowserWorker) if not name.startswith("_")}
    assert public_members == {"run_step", "audit_log"}


def test_verifier_module_has_no_memory_or_knowledge_promotion_hooks():
    """Evidence must support future Knowledge Promotion but must NOT
    perform it (Mission Brief 022's explicit Evidence requirement) --
    verified by confirming the generic verification package exposes no
    promotion/memory-writing function at all."""
    exported = {name for name in dir(verifier_module) if not name.startswith("_")}
    assert not any("promote" in name.lower() or "memory" in name.lower() for name in exported)
