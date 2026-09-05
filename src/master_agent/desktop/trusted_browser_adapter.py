"""DesktopTrustedBrowser — the `TrustedBrowserPort` built out of the
Desktop Executive capabilities that already exist.

Every operation below composes actions that shipped long before this
file: `verified_launch_application`, `verified_bring_to_front`,
`find_target`, `desktop_observe`, `desktop_click`, `desktop_type_text`,
`desktop_press_key`. Nothing here talks to Win32 or UIA directly, and
nothing here knows what a website is -- this is an adapter, not a second
automation stack.

**Focus is perishable, and that shaped this file.** Measured on the
founder's own desktop: after `bring_to_front` succeeded, the browser held
the foreground for about four seconds before another running application
took it back. An earlier version observed the page (131 elements, several
seconds) *between* taking focus and typing, and by the time it typed the
foreground was gone -- the Desktop Executive correctly refused, three
attempts running. So the rule here is: **prepare first, then focus and
act back to back, with nothing in between.** `type_into` re-takes the
foreground itself immediately before typing rather than trusting a check
made earlier, and retries the pair a bounded number of times.

That refusal is worth being clear about: it is the Desktop Executive's
own invariant working. Typing into whatever happens to be in front is the
failure mode this whole lane exists to make impossible.
"""
from __future__ import annotations

import time
from typing import Any

from master_agent.trusted_browser import (
    BrowserCandidate,
    BrowserResolution,
    PageElement,
    PageObservation,
    TrustedBrowserResult,
    TrustedBrowserUnavailable,
)

#: The ordinary installed browsers this deployment may drive, as the
#: Desktop Executive's own application catalogue names them. Deployment
#: configuration and nothing more -- no code below branches on which one
#: it is, and the order here is NOT a preference: which browser executes
#: is decided by what is observed open, never by this list's order.
DEFAULT_CANDIDATES = ("chrome", "comet")

#: Deliberately NOT a default browser.
#:
#: There was one here, and it was a deployment preference hidden inside
#: execution: with no browser showing the target page, resolution fell
#: through to the first entry of `DEFAULT_CANDIDATES`, so the tuple's
#: order silently chose Chrome. Nothing observed justified it.
#:
#: A genuine tie between equally suitable browsers is a question for the
#: founder, not a position in a tuple. A deployment may configure an
#: explicit preferred browser in future; none may be inferred from
#: ordering.
NO_APPLICATION_RESOLVED = ""

#: How many times focus-then-type is retried before giving up. Bounded on
#: purpose -- another application winning the foreground forever is a real
#: state, and a caller waiting forever is worse than a truthful refusal.
_FOCUS_ATTEMPTS = 4
_FOCUS_RETRY_SECONDS = 1.0

#: Accessible names the browser itself uses. Browser chrome, not website
#: knowledge -- a provider never sees these.
_ADDRESS_BAR = "Address and search bar"
_NEW_TAB = "New Tab"


class DesktopTrustedBrowser:
    """Implements `TrustedBrowserPort` over the Desktop Executive.

    `actions` is the small set of Action classes this needs, injected so
    the whole adapter can be exercised without a machine. `context` is
    the Desktop Executive's own `DesktopContext`.
    """

    def __init__(
        self,
        context: Any,
        application: str = NO_APPLICATION_RESOLVED,
        actions: dict[str, Any] | None = None,
        sleep: Any = None,
        candidates: tuple[str, ...] = DEFAULT_CANDIDATES,
        windows: Any = None,
    ) -> None:
        self._context = context
        self._application = application
        self._candidates = tuple(candidates)
        self._actions = actions or _default_actions()
        self._sleep = sleep or time.sleep
        self._windows = windows
        #: Set once this task opens its own tab. Used only to decide
        #: whether closing something is this task's business.
        self._owns_tab = False

    # ---- which browser executes this request ----------------------------

    def _window_manager(self):
        if self._windows is None:
            from master_agent.desktop.execution.win32_backends import Win32WindowBackend
            from master_agent.desktop.execution.window import WindowManager

            self._windows = WindowManager(Win32WindowBackend())
        return self._windows

    def _running_windows(self, application: str) -> list[dict[str, Any]]:
        inventory = self._context.refresh(read_versions=False, deep=False)
        pids = frozenset(p.pid for p in inventory.running(application))
        if not pids:
            return []
        located = self._window_manager().locate_by_process(pids)
        if not located.success or not located.output:
            return []
        return list(located.output.get("windows") or [])

    def _foreground_handle(self) -> Any:
        active = self._window_manager().active()
        if not active.success or not active.output:
            return None
        return active.output.get("handle")

    def resolve(self, page_markers: tuple[str, ...]) -> BrowserResolution:
        """Observed reality decides, in this order.

        The founder's own machine is why this is not a preference list:
        the target page was open in one browser while another sat in the
        foreground with unrelated work. Preferring "whatever is in front"
        would have driven the wrong browser; preferring a fixed order
        would have been right by luck and wrong the next time.

        Which site the markers describe is the caller's business. This
        layer matches strings and never learns what they mean.
        """
        foreground = self._foreground_handle()
        candidates: list[BrowserCandidate] = []
        for application in self._candidates:
            for window in self._running_windows(application):
                title = str(window.get("title") or "")
                candidates.append(
                    BrowserCandidate(
                        application=application,
                        window_handle=window.get("handle"),
                        window_title=title,
                        has_target_page=_matches(title, page_markers),
                        is_foreground=window.get("handle") == foreground,
                    )
                )

        # Best first: already showing the target page beats not; being in
        # front breaks a tie between two that both show it.
        ordered = tuple(
            sorted(candidates, key=lambda c: (not c.has_target_page, not c.is_foreground))
        )
        showing = [c for c in candidates if c.has_target_page]

        if len(showing) == 1:
            return BrowserResolution(
                showing[0],
                f"{showing[0].application} is already showing the target page",
                ordered=ordered,
            )
        if len(showing) > 1:
            in_front = [c for c in showing if c.is_foreground]
            if len(in_front) == 1:
                return BrowserResolution(
                    in_front[0],
                    f"{in_front[0].application} is showing the target page and is in front",
                    ordered=ordered,
                )
            # Several hold the page and none is in front. Picking one would
            # be guessing at which session the founder means.
            return BrowserResolution(
                None, "several browsers already hold the target page",
                tuple(showing), ordered=ordered,
            )

        # Nothing is showing the target page. Reuse a running browser if
        # exactly one is running -- that is an observation, not a
        # preference. Several equally uninformative candidates is a real
        # tie, and a tie is the founder's to break.
        if len(candidates) == 1:
            running = candidates[0]
            return BrowserResolution(
                running,
                f"no browser is showing the target page; {running.application} is "
                "the only one running",
                ordered=ordered,
            )
        if candidates:
            return BrowserResolution(
                None,
                "several browsers are running and none is showing the target page",
                tuple(candidates), ordered,
            )

        # Nothing running at all. Which browser to OPEN is equally not a
        # tuple's decision; with one configured candidate there is nothing
        # to ask about, with several there is.
        to_open = tuple(
            BrowserCandidate(application=name, has_target_page=False)
            for name in self._candidates
        )
        if len(to_open) == 1:
            return BrowserResolution(
                to_open[0],
                f"no trusted browser is running; {to_open[0].application} is the "
                "only one configured",
                ordered=to_open,
            )
        return BrowserResolution(
            None, "no trusted browser is running and several are configured",
            to_open, to_open,
        )

    def alternatives(self, exclude: tuple[str, ...] = ()) -> tuple[BrowserCandidate, ...]:
        """Configured environments that are not in `exclude`.

        An environment that has just been proven unreadable is not a
        place to keep trying. This offers the ones that have not failed,
        in configured order, so a caller that found every RUNNING
        candidate undrivable can open a fresh one instead of insisting on
        the broken one.

        It names no application and expresses no preference: `exclude` is
        the caller's observation, and the order is the deployment's own
        configured order, which `resolve()` already refuses to treat as a
        preference among *running* browsers.
        """
        skip = {str(name).casefold() for name in exclude}
        return tuple(
            BrowserCandidate(application=name, has_target_page=False)
            for name in self._candidates
            if name.casefold() not in skip
        )

    def use(self, candidate: BrowserCandidate) -> TrustedBrowserResult:
        if not candidate.application:
            return TrustedBrowserResult(False, "the candidate names no application")
        self._application = candidate.application
        return TrustedBrowserResult(
            True, f"executing in {candidate.application} ({candidate.window_title[:60]})"
        )

    # ---- the Action boundary -------------------------------------------

    def _run(self, action_key: str, **parameters: Any):
        action_cls = self._actions.get(action_key)
        if action_cls is None:
            return _failed(f"no Desktop action registered for {action_key!r}")
        action = action_cls(self._context)
        errors = action.validate(parameters)
        if errors:
            return _failed("; ".join(errors))
        try:
            return action.run(parameters)
        except Exception as exc:  # noqa: BLE001 - an Action must never raise past here
            return _failed(f"{action_key} failed: {exc}")

    # ---- availability ---------------------------------------------------

    def ensure_available(self) -> TrustedBrowserResult:
        """Reuse the founder's browser if it is running; otherwise launch
        it the ordinary way.

        `verified_launch_application` runs the catalogue's own executable
        with no arguments at all -- no remote-debugging port, no
        automation user-data directory, no automation flag. That is the
        whole point: what starts is the browser the founder uses, with the
        profile and the sessions they already have.
        """
        if not self._application:
            return TrustedBrowserResult(
                False,
                "no browser has been resolved for this request; resolve() must "
                "choose one, or the founder must, before one is opened",
            )

        focused = self._run("bring_to_front", application=self._application)
        if focused.success:
            return TrustedBrowserResult(True, "already running; reused")

        launched = self._run("launch", application=self._application, focus=True)
        if not launched.success:
            raise TrustedBrowserUnavailable(
                f"could not make {self._application} available: "
                + ("; ".join(launched.errors) or "no window appeared")
            )
        return TrustedBrowserResult(True, "launched")

    # ---- navigation -----------------------------------------------------

    def open_task_tab(self, url: str) -> TrustedBrowserResult:
        """A new tab for this task, so the founder's own tabs are neither
        closed nor navigated away from.

        The new-tab control is located semantically and clicked; if the
        browser is not showing one, this says so and navigates in place
        rather than pretending a tab was created. Claiming ownership of a
        tab that was not opened here would license closing something that
        belongs to the founder.
        """
        button = self.find(_NEW_TAB)
        if button is None:
            result = self.navigate(url)
            return TrustedBrowserResult(
                result.ok,
                "no new-tab control was offered; navigated in place "
                "(this task does not own a tab)",
                result.observation,
            )
        clicked = self.click(button)
        if not clicked.ok:
            return clicked
        self._owns_tab = True
        return self.navigate(url)

    def navigate(self, url: str) -> TrustedBrowserResult:
        """Type the address, CONFIRM it, and only then commit.

        Measured live 2026-09-05: the founder's browser ended on
        `gemini.google.com/ap` -- one character short of `/app` -- and a
        real 404. An address bar is not an ordinary text field: it
        autocompletes while you type, and a suggestion can consume or
        replace the last keystroke. Pressing Enter without reading it back
        commits to whatever the omnibox decided, which is how a reasoning
        call navigated the founder's window to a page that does not exist.

        Enter is the irreversible half of this operation, so it is the
        half that gets the check. An address that does not read back as
        the one asked for is an uncertain target, and an uncertain target
        gets zero input.
        """
        typed = self.type_into(_ADDRESS_BAR, url)
        if not typed.ok:
            return TrustedBrowserResult(False, f"could not reach the address bar: {typed.detail}")
        settled = self._address_matches(url)
        if not settled:
            return TrustedBrowserResult(
                False,
                f"the address bar did not read back as {url!r}; nothing was "
                f"committed",
            )
        entered = self.press("enter")
        if not entered.ok:
            return entered
        return TrustedBrowserResult(True, f"navigated to {url}")

    def _address_matches(self, url: str) -> bool:
        """Does the address bar hold the address we asked for?

        Compared without the scheme and without a trailing slash, because
        the omnibox displays what it likes -- it hides `https://` and it
        may or may not keep a trailing separator. Those are presentation.
        A missing character is not.
        """
        element = self.find(_ADDRESS_BAR)
        if element is None:
            return False
        shown = (getattr(element, "name", "") or "").strip()
        try:
            observed = self._run("read_text", application=self._application,
                                 target_name_contains=_ADDRESS_BAR)
            if observed.success and observed.output:
                shown = str(observed.output.get("text") or shown)
        except Exception:  # noqa: BLE001 -- an unreadable bar is not a match
            return False

        def _bare(value: str) -> str:
            value = (value or "").strip().rstrip("/")
            for scheme in ("https://", "http://"):
                if value.startswith(scheme):
                    value = value[len(scheme):]
            return value.casefold()

        return bool(shown) and _bare(shown) == _bare(url)

    # ---- observation ----------------------------------------------------

    def observe(self) -> PageObservation:
        """One read of the live page, with the foreground fact attached.

        `foreground` is read here rather than assumed, because it is the
        half of the safety invariant a caller cannot get any other way.
        """
        observed = self._run("observe", application=self._application)
        if not observed.success or not observed.output:
            return PageObservation(application=self._application, observed_at=time.monotonic())

        output = observed.output
        elements = tuple(
            PageElement(
                role=str(item.get("role") or ""),
                name=str(item.get("name") or ""),
                control_type=item.get("control_type"),
                is_actionable=bool(item.get("is_actionable")),
                x=item.get("x"),
                y=item.get("y"),
            )
            for item in (output.get("elements") or [])
        )
        return PageObservation(
            application=self._application,
            window_title=str(output.get("window_title") or ""),
            window_handle=output.get("window_handle"),
            foreground=self._is_foreground(output.get("window_handle")),
            elements=elements,
            observed_at=time.monotonic(),
        )

    def _is_foreground(self, handle: Any) -> bool:
        active = self._run("active_window")
        if not active.success or not active.output:
            return False
        return bool(handle is not None and active.output.get("handle") == handle)

    def find(self, name_contains: str, control_type: int | None = None) -> PageElement | None:
        found = self._run(
            "find_target", application=self._application, name_contains=name_contains,
            control_type=control_type,
        )
        if not found.success or not found.output:
            return None
        output = found.output
        return PageElement(
            role="",
            name=str(output.get("name") or ""),
            control_type=output.get("control_type"),
            is_actionable=bool(output.get("is_enabled", True)),
            x=output.get("x"),
            y=output.get("y"),
        )

    # ---- acting ---------------------------------------------------------

    def type_into(
        self, name_contains: str, text: str, control_type: int | None = None
    ) -> TrustedBrowserResult:
        """Take the foreground and type, immediately, as one operation.

        The retry loop is not politeness -- it is the measured behaviour
        of a real desktop, where another application can and does reclaim
        the foreground between two calls. Each attempt re-takes focus so
        that no attempt is relying on a check made before the last one.
        """
        last = "no attempt was made"
        for attempt in range(_FOCUS_ATTEMPTS):
            focused = self._run("bring_to_front", application=self._application)
            if not focused.success:
                last = "; ".join(focused.errors) or "could not bring the window to the front"
                self._sleep(_FOCUS_RETRY_SECONDS)
                continue
            typed = self._run(
                "type_text", application=self._application,
                text=text, target_name_contains=name_contains,
                control_type=control_type,
            )
            if typed.success:
                return TrustedBrowserResult(True, f"typed into {name_contains!r}")
            last = "; ".join(typed.errors) or "typing was refused"
            self._sleep(_FOCUS_RETRY_SECONDS)
        return TrustedBrowserResult(
            False,
            f"could not type into {name_contains!r} after {_FOCUS_ATTEMPTS} attempts: {last}",
        )

    def press(self, key: str) -> TrustedBrowserResult:
        pressed = self._run("press_key", application=self._application, key=key)
        if pressed.success:
            return TrustedBrowserResult(True, f"pressed {key}")
        return TrustedBrowserResult(False, "; ".join(pressed.errors) or f"could not press {key}")

    def click(self, element: PageElement) -> TrustedBrowserResult:
        target = element
        if target.x is None or target.y is None:
            # An OBSERVED element carries a name and a role; it does not
            # carry geometry. Measured on this machine: every actionable
            # element in a Chrome window observation had `x=None`, so a
            # caller holding one could never click anything -- the account
            # chooser included, which is why that path had never worked.
            #
            # Resolving the same element by name through `find_target`
            # is what this method's own comment below already describes,
            # and it returns UIA's real bounding rectangle. Nothing is
            # guessed: an unresolvable name still refuses.
            resolved = self.find(target.name) if target.name else None
            if resolved is not None and resolved.x is not None:
                target = resolved
        if target.x is None or target.y is None:
            return TrustedBrowserResult(False, "the element carries no click point")
        # The point comes from UIA's own bounding rectangle via
        # `find_target`, never from a caller's guess -- which is the
        # difference `ClickControlAction`'s own docstring draws between a
        # resolved point and blind desktop clicking.
        clicked = self._run(
            "click", application=self._application, x=target.x, y=target.y
        )
        if clicked.success:
            return TrustedBrowserResult(True, f"clicked {target.name!r}")
        return TrustedBrowserResult(False, "; ".join(clicked.errors) or "the click was refused")

    def close_task_tab(self) -> TrustedBrowserResult:
        """Close this task's own tab, and nothing else.

        A task that never opened a tab closes nothing. The founder's
        browser is theirs, and the cost of being wrong here is destroying
        work that was never ours to touch.
        """
        if not self._owns_tab:
            return TrustedBrowserResult(True, "this task opened no tab; nothing to close")
        closed = self._run("press_key", application=self._application, key="ctrl+w")
        self._owns_tab = False
        if closed.success:
            return TrustedBrowserResult(True, "closed this task's tab")
        return TrustedBrowserResult(False, "; ".join(closed.errors) or "could not close the tab")


def _matches(title: str, markers: tuple[str, ...]) -> bool:
    """Whether a window title says this browser is on the caller's site.

    A window title is what Windows itself publishes, so it needs no
    accessibility read and no page inspection -- which matters, because
    deciding *which* browser to drive must not require driving one.
    """
    lowered = (title or "").lower()
    return any(marker.lower() in lowered for marker in markers if marker)


def _failed(message: str):
    from master_agent.executor.action import ExecutionResult

    return ExecutionResult(success=False, errors=[message])


def _default_actions() -> dict[str, Any]:
    """The existing Desktop Executive actions this adapter composes.

    Imported here rather than at module scope so the adapter can be
    imported (and its contract read) on a machine where the Desktop
    Executive's optional Windows dependencies are absent.
    """
    from master_agent.desktop.actions_interaction import (
        ClickControlAction,
        FindTargetAction,
        ObserveDesktopAction,
        PressKeyAction,
        TypeIntoWindowAction,
        VerifiedBringToFrontAction,
        VerifiedLaunchApplicationAction,
    )

    return {
        "launch": VerifiedLaunchApplicationAction,
        "bring_to_front": VerifiedBringToFrontAction,
        "find_target": FindTargetAction,
        "observe": ObserveDesktopAction,
        "click": ClickControlAction,
        "type_text": TypeIntoWindowAction,
        "press_key": PressKeyAction,
        "active_window": _ActiveWindowAction,
    }


class _ActiveWindowAction:
    """The one fact the Action layer does not already publish: which
    window is in front *right now*.

    Deliberately a thin read over `WindowManager.active()` -- the same
    call `VerifiedFocusWindowAction` already makes to confirm its own
    work -- rather than a new capability registered onto the Executive.
    It is not part of the founder-facing capability surface; it exists so
    this adapter can attach the foreground fact to an observation.
    """

    def __init__(self, context: Any) -> None:
        self._context = context

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        return []

    def run(self, parameters: dict[str, Any]):
        from master_agent.desktop.execution.win32_backends import Win32WindowBackend
        from master_agent.desktop.execution.window import WindowManager

        return WindowManager(Win32WindowBackend()).active()
