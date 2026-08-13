"""What the Desktop Executive knows how to look for (Mission Brief 030).

A declarative catalogue: for each application, what it is called, what its
executable is named on each platform, where it tends to be installed, how
to ask it for a version, and which process name it runs as.

**This file contains facts about software, and nothing else.** No
ranking, no cost, no quality, no "better than". `category="ai"` is a
label for grouping in the Dashboard (MB030 Deliverable 8 asks which AI
software is installed) — it is emphatically not a judgement, and nothing
in `desktop/` reads it to make a choice. Deciding *which* intelligence to
use belongs exclusively to the AI Capability Broker (Rules 2 and 11).

Adding an application is one entry. Nothing else changes — the same
extension shape `FilesystemPlugin` uses for capabilities.
"""
from __future__ import annotations

from dataclasses import dataclass

#: Grouping labels. Descriptive only — see the module docstring.
DEVELOPER = "developer"
BROWSER = "browser"
RUNTIME = "runtime"
AI = "ai"
CONTAINER = "container"
SYSTEM = "system"


@dataclass(frozen=True)
class ApplicationSpec:
    """How to find one application.

    `executables` are tried on the PATH in order. `windows_paths` and
    `posix_paths` are fallbacks for applications that install without
    putting themselves on the PATH — which most GUI applications do.
    """

    key: str
    label: str
    category: str
    executables: tuple[str, ...] = ()
    windows_paths: tuple[str, ...] = ()
    posix_paths: tuple[str, ...] = ()
    #: Arguments that make the executable print a version and exit.
    #: `None` — not `()` — is the honest way to say *no such argument
    #: exists*: a GUI-only binary like `notepad.exe` has no version flag
    #: at all, and any argument (including none) makes it open a real,
    #: visible, blocking window rather than answer and exit. `()` still
    #: means "just run it with no extra arguments," which is exactly that
    #: same trap for a GUI-only executable — `None` is what actually
    #: tells `inventory.discover()` to skip the probe (Desktop Executive
    #: Foundation 1.0).
    version_args: tuple[str, ...] | None = ("--version",)
    process_names: tuple[str, ...] = ()
    #: Recommended means "the founder probably wants this", used only to
    #: populate MB030 Deliverable 4's "Missing Recommended Applications"
    #: list. It is a statement about a developer machine, never about AI.
    recommended: bool = False
    notes: str = ""

    def paths_for(self, platform: str) -> tuple[str, ...]:
        return self.windows_paths if platform == "win32" else self.posix_paths

    def process_candidates(self) -> tuple[str, ...]:
        return self.process_names or self.executables


CATALOG: tuple[ApplicationSpec, ...] = (
    # ---- developer tooling ----
    ApplicationSpec(
        key="python",
        label="Python",
        category=RUNTIME,
        executables=("python", "python3"),
        process_names=("python.exe", "python3", "python"),
        recommended=True,
    ),
    ApplicationSpec(
        key="git",
        label="Git",
        category=DEVELOPER,
        executables=("git",),
        recommended=True,
    ),
    ApplicationSpec(
        key="node",
        label="Node.js",
        category=RUNTIME,
        executables=("node",),
        process_names=("node.exe", "node"),
        recommended=True,
    ),
    ApplicationSpec(
        key="vscode",
        label="VS Code",
        category=DEVELOPER,
        executables=("code",),
        windows_paths=(
            r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe",
            r"%PROGRAMFILES%\Microsoft VS Code\Code.exe",
        ),
        posix_paths=("/usr/share/code/code", "/Applications/Visual Studio Code.app"),
        process_names=("Code.exe", "code"),
        recommended=True,
    ),
    ApplicationSpec(
        key="cursor",
        label="Cursor",
        category=AI,
        executables=("cursor",),
        windows_paths=(r"%LOCALAPPDATA%\Programs\cursor\Cursor.exe",),
        posix_paths=("/Applications/Cursor.app",),
        process_names=("Cursor.exe", "cursor"),
    ),
    ApplicationSpec(
        key="visualstudio",
        label="Visual Studio",
        category=DEVELOPER,
        windows_paths=(
            r"%PROGRAMFILES%\Microsoft Visual Studio",
            r"%PROGRAMFILES(X86)%\Microsoft Visual Studio",
        ),
        process_names=("devenv.exe",),
    ),
    ApplicationSpec(
        key="notepad",
        label="Notepad",
        category=SYSTEM,
        executables=("notepad",),
        windows_paths=(r"%WINDIR%\system32\notepad.exe",),
        # `None`, not `()`: notepad.exe has no version flag, and any
        # argument opens a real, visible, blocking window — see
        # `ApplicationSpec.version_args`'s own docstring.
        version_args=None,
        process_names=("notepad.exe", "notepad"),
    ),
    # ---- browsers ----
    ApplicationSpec(
        key="chrome",
        label="Chrome",
        category=BROWSER,
        executables=("chrome", "google-chrome"),
        windows_paths=(
            r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe",
            r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe",
        ),
        posix_paths=("/usr/bin/google-chrome", "/Applications/Google Chrome.app"),
        process_names=("chrome.exe", "chrome"),
        recommended=True,
    ),
    ApplicationSpec(
        key="edge",
        label="Edge",
        category=BROWSER,
        executables=("msedge",),
        windows_paths=(
            r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe",
        ),
        process_names=("msedge.exe",),
    ),
    ApplicationSpec(
        key="firefox",
        label="Firefox",
        category=BROWSER,
        executables=("firefox",),
        windows_paths=(r"%PROGRAMFILES%\Mozilla Firefox\firefox.exe",),
        posix_paths=("/usr/bin/firefox", "/Applications/Firefox.app"),
        process_names=("firefox.exe", "firefox"),
    ),
    # ---- AI software (Deliverable 8) -- reported, never ranked ----
    ApplicationSpec(
        key="claude_desktop",
        label="Claude Desktop",
        category=AI,
        windows_paths=(r"%LOCALAPPDATA%\AnthropicClaude\claude.exe",),
        posix_paths=("/Applications/Claude.app",),
        process_names=("claude.exe", "Claude"),
    ),
    ApplicationSpec(
        key="chatgpt_desktop",
        label="ChatGPT",
        category=AI,
        windows_paths=(
            r"%LOCALAPPDATA%\Programs\ChatGPT\ChatGPT.exe",
            r"%LOCALAPPDATA%\Programs\ChatGPT\ChatGPT",
        ),
        posix_paths=("/Applications/ChatGPT.app",),
        process_names=("ChatGPT.exe", "ChatGPT"),
    ),
    ApplicationSpec(
        key="perplexity_desktop",
        label="Perplexity",
        category=AI,
        # No `windows_paths`: Perplexity is an MSIX/Start-Menu install with
        # no fixed path (confirmed live, Universal Windows Environment
        # Discovery) — a bare key/label entry only, so it can be referenced
        # by name; `discover()`'s own Start Menu/MSIX sources resolve the
        # real launch target, exactly like every other app in this file.
        process_names=("Perplexity.exe", "Perplexity"),
    ),
    ApplicationSpec(
        key="kimi_desktop",
        label="Kimi",
        category=AI,
        process_names=("Kimi.exe", "Kimi"),
    ),
    ApplicationSpec(
        key="ollama",
        label="Ollama",
        category=AI,
        executables=("ollama",),
        windows_paths=(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe",),
        posix_paths=("/usr/local/bin/ollama",),
        process_names=("ollama.exe", "ollama"),
    ),
    ApplicationSpec(
        key="lm_studio",
        label="LM Studio",
        category=AI,
        windows_paths=(r"%LOCALAPPDATA%\LM-Studio\LM Studio.exe",),
        posix_paths=("/Applications/LM Studio.app",),
        process_names=("LM Studio.exe",),
    ),
    ApplicationSpec(
        key="open_webui",
        label="Open WebUI",
        category=AI,
        executables=("open-webui",),
        process_names=("open-webui",),
    ),
    ApplicationSpec(
        key="continue_dev",
        label="Continue",
        category=AI,
        executables=("continue",),
        notes="usually an editor extension rather than a standalone binary",
    ),
    # ---- containers and shells ----
    ApplicationSpec(
        key="docker",
        label="Docker",
        category=CONTAINER,
        executables=("docker",),
        process_names=("docker.exe", "dockerd", "Docker Desktop.exe"),
    ),
    ApplicationSpec(
        key="wsl",
        label="WSL",
        category=SYSTEM,
        executables=("wsl",),
        version_args=("--version",),
    ),
    ApplicationSpec(
        key="powershell",
        label="PowerShell",
        category=SYSTEM,
        executables=("pwsh", "powershell"),
        version_args=("--version",),
        process_names=("powershell.exe", "pwsh.exe", "pwsh"),
    ),
    ApplicationSpec(
        key="java",
        label="Java",
        category=RUNTIME,
        executables=("java",),
        version_args=("-version",),
    ),
    ApplicationSpec(
        key="playwright",
        label="Playwright",
        category=DEVELOPER,
        executables=("playwright",),
        notes="also usable as a Python package without a CLI on PATH",
    ),
)

BY_KEY = {spec.key: spec for spec in CATALOG}

#: What the Dashboard's Machine Readiness panel checks — a fixed,
#: intentionally small set of everyday developer tools, not "every
#: catalog entry" (`dashboard/sources.py` reads this directly).
READINESS_KEYS: tuple[str, ...] = (
    "python",
    "git",
    "node",
    "docker",
    "ollama",
    "vscode",
    "chrome",
)


def find(key: str) -> ApplicationSpec | None:
    return BY_KEY.get(key)


def resolve(name: str) -> ApplicationSpec | None:
    """Look up by key or by label, case-insensitively -- a founder types
    "VS Code", a task payload says "vscode", and both should work."""
    lowered = (name or "").strip().lower()
    if not lowered:
        return None
    if lowered in BY_KEY:
        return BY_KEY[lowered]
    for spec in CATALOG:
        if spec.label.lower() == lowered:
            return spec
        if lowered in {executable.lower() for executable in spec.executables}:
            return spec
    return None


def ai_applications() -> tuple[ApplicationSpec, ...]:
    """Deliverable 8. A grouping, not a shortlist -- nothing here decides
    which of these should be used for anything."""
    return tuple(spec for spec in CATALOG if spec.category == AI)


def recommended() -> tuple[ApplicationSpec, ...]:
    return tuple(spec for spec in CATALOG if spec.recommended)