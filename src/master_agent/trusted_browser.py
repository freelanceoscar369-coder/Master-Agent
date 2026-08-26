"""TrustedBrowserPort — the contract a provider uses to work inside the
founder's *own* browser, and the vocabulary it observes there.

**Why this exists.** Google refuses to sign in inside an
automation-controlled browser: the founder's live evidence is
*"Couldn't sign you in — This browser or app may not be secure."* That is
Google's security judgement, not a bug to be worked around, and no amount
of profile persistence changes it. The only browser that is genuinely
authenticated as the founder is the ordinary one they use themselves. So
a web AI service used as a *reasoning provider* is driven there, through
the Desktop Executive, exactly as a person would drive it.

**What this file is not.** It is not a second Browser Worker, and it is
not an automation library. It is a small port: a provider states what it
needs done, and an adapter built from existing Desktop Executive
capabilities does it. Ordinary browser missions -- open a page, search,
read, fill a form -- are untouched and still belong to the Browser
Executive and Playwright (MB022). This lane exists only for the case
where a *website is the AI*.

**Why it is a port rather than an import.** A provider that imported the
Desktop Executive would be a provider that could drive a machine, and
MB033 Rule 4 keeps those apart. It holds this Protocol, so the same
provider is exercised in tests against a scripted browser with no
machine involved at all.

**What the port deliberately does not know.** Nothing about Gemini,
ChatGPT, Claude, Perplexity or any other service. No URL, no selector, no
composer name, no response rule. Every one of those is site knowledge and
lives at the provider's own edge, which is what lets a second web AI
service reuse this file unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

# ---- what an observation of the page can say -------------------------
#
# Five states, because collapsing any two loses something a caller must
# act on differently. In particular "the site wants a password" is not a
# kind of "signed out": one is recoverable by asking the founder to
# finish, and the other is something Kalpavriksha must never touch.

#: The service is genuinely usable right now.
READY = "ready"
#: Reached the service, and it wants a sign-in that has not happened.
SIGNED_OUT = "signed_out"
#: The browser or the site is offering a choice of account/profile.
ACCOUNT_CHOICE = "account_choice"
#: A password, OTP, passkey or CAPTCHA is being asked for. Founder-only.
FOUNDER_ACTION_REQUIRED = "founder_action_required"
#: Observation succeeded but says nothing conclusive. Never treated as
#: permission to act -- see `TrustedBrowserPort.observe`.
UNKNOWN = "unknown"


@dataclass(frozen=True)
class PageElement:
    """One element the browser is showing, as the Desktop Executive
    already describes it. `role` is that layer's own classification
    (`composer`, `text_region`, `button`, ...), never a re-derivation."""

    role: str = ""
    name: str = ""
    control_type: int | None = None
    is_actionable: bool = False
    x: int | None = None
    y: int | None = None


@dataclass(frozen=True)
class PageObservation:
    """What the browser is showing, and enough evidence to prove the
    input that follows would land in the right place.

    `window_title`, `foreground` and `application` together are the
    invariant a caller checks before every consequential input: right
    application, right window in front, expected page. A provider that
    types without checking all three is typing hopefully, which is the
    one thing this lane must never do.
    """

    application: str = ""
    window_title: str = ""
    window_handle: int | None = None
    foreground: bool = False
    elements: tuple[PageElement, ...] = field(default_factory=tuple)
    #: Monotonic timestamp of the observation, so a caller can refuse to
    #: act on evidence that has gone stale.
    observed_at: float = 0.0

    def texts(self) -> tuple[str, ...]:
        """Every non-empty element name, in page order. This is the raw
        material a provider's own response rules work on."""
        return tuple(e.name for e in self.elements if (e.name or "").strip())

    def named(self, role: str) -> tuple[PageElement, ...]:
        return tuple(e for e in self.elements if e.role == role)


@dataclass(frozen=True)
class TrustedBrowserResult:
    """Whether one operation happened, and why not when it did not.

    Deliberately the same shape for every operation: a caller that has to
    interpret a different result per call will eventually skip the check.
    """

    ok: bool = False
    detail: str = ""
    observation: PageObservation | None = None


class TrustedBrowserUnavailable(RuntimeError):
    """No ordinary browser could be made available at all -- not
    installed, or it would not produce a window. Structural, and never
    raised for an ordinary navigation or targeting failure, which are
    reported as `TrustedBrowserResult(ok=False)`."""


@runtime_checkable
class TrustedBrowserPort(Protocol):
    """The whole contract. Every operation is something a person does to
    a browser, and nothing here is specific to any website.

    Implementations must satisfy one rule above all: **never act without
    fresh evidence**. Focus on a real desktop is perishable -- observed
    live, another application reclaimed the foreground about four seconds
    after it was granted -- so an implementation confirms the window is
    foreground as part of the acting call rather than trusting an earlier
    check, and refuses rather than acting when it cannot.
    """

    def ensure_available(self) -> TrustedBrowserResult:
        """Make the founder's ordinary browser available, reusing it if
        it is already running and launching it the ordinary way if not.
        Never with automation flags, never against a copied profile."""
        ...

    def open_task_tab(self, url: str) -> TrustedBrowserResult:
        """Open a NEW tab owned by this task and navigate it, leaving
        every tab the founder already had alone."""
        ...

    def navigate(self, url: str) -> TrustedBrowserResult:
        ...

    def observe(self) -> PageObservation:
        """Read the current page. Read-only, and the only source of truth
        about what is on screen: a previous observation is a fact about
        the past, and this lane acts only on the present."""
        ...

    def find(self, name_contains: str) -> PageElement | None:
        """Locate one element by its accessible name, or None."""
        ...

    def type_into(self, name_contains: str, text: str) -> TrustedBrowserResult:
        """Type into a semantically identified element, confirming the
        window is foreground as part of the same operation."""
        ...

    def press(self, key: str) -> TrustedBrowserResult:
        ...

    def click(self, element: PageElement) -> TrustedBrowserResult:
        """Click an element the caller already located semantically --
        never a coordinate the caller guessed."""
        ...

    def close_task_tab(self) -> TrustedBrowserResult:
        """Close only what this task opened, and only when it is safe to
        do so. A tab this task did not open is never closed."""
        ...
