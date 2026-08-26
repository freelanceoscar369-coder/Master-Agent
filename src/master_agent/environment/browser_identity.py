"""BrowserIdentityStore — where a *named* browser identity's authenticated
state lives on disk, and the only thing allowed to turn an identity id
into a filesystem path.

An anonymous browser session forgets everything the moment it closes: a
fresh `BrowserContext` has no cookies and no storage, which is exactly
right for a scripted mission and exactly wrong for a founder whose signed-in
session should still be there tomorrow. A *browser identity* is the
generic answer -- "open this session as `founder`" -- and this module owns
one question only: which directory is that, and is the caller allowed to
name it.

**Not the founder's own everyday profile.** This is deliberately a
dedicated Kalpavriksha identity, never the user-data directory the
founder's installed browser keeps for their daily use. Driving that would
put an automation process inside the browser they bank in, hold every
cookie they own open to a scripted page, and lock the profile for as long
as Kalpavriksha ran. The identity here starts empty and holds only what a
sign-in performed inside Kalpavriksha's own window put there.

**Nothing here is a credential store.** The directory holds whatever
the browser itself writes for a signed-in profile; Kalpavriksha never reads,
parses, copies or transmits its contents, and never asks for a password,
an OTP, a recovery code or a passkey. The one operation this module offers
over that state besides locating it is `forget()`, which deletes it.

**Why ids are validated rather than trusted.** An identity id arrives from
configuration, but it also arrives from a Planner-authored Action
parameter, and an id spelled `../../../` followed by a path would
otherwise resolve to precisely the directory the paragraph above forbids.
The pattern below admits no separator, no drive letter and no dots, so a
traversal cannot be spelled; `known` narrows it further to the identities a
deployment actually declared.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

#: Lowercase, digits, `_` and `-`; must start alphanumeric; at most 32
#: characters. Deliberately admits no `/`, `\`, `:`, `.` or whitespace --
#: every spelling of a traversal or an absolute path needs one of those,
#: so rejection is structural rather than a blacklist somebody has to keep
#: up to date.
IDENTITY_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")

#: The subdirectory of a deployment's application root that holds them.
IDENTITIES_DIRNAME = "browser_identities"


class BrowserIdentityError(Exception):
    """A refused identity id, or an identity a deployment never declared.

    An `Action` turns this into a structured `ExecutionResult` and
    `BrowserSessionManager` into a `BrowserSessionError`; it must never
    reach a founder as a traceback.
    """


class BrowserIdentityStore:
    """Resolves declared identity ids to directories under one root.

    `root` is configuration and comes from the deployment's own
    application directory -- never from this module, which has no opinion
    about where an application keeps things, and never from the repository.

    `known` is the deployment's declaration of which identities exist,
    mapping id to the human-facing label that identity should be called in
    a question put to the founder. `None` means "any well-formed id",
    which is what a test or a generic caller wants; a deployment that
    declares its identities gets an unknown id refused rather than
    silently created.
    """

    def __init__(
        self, root: Path | str, known: dict[str, str] | None = None
    ) -> None:
        self._root = Path(root)
        self._known = None if known is None else dict(known)

    @property
    def root(self) -> Path:
        return self._root

    def declared(self) -> tuple[str, ...]:
        """The identity ids this deployment declared, or `()` when it
        declared none and any well-formed id is acceptable."""
        return () if self._known is None else tuple(self._known)

    def label(self, identity_id: str) -> str:
        """The human-facing name for this identity -- what a founder is
        called in a question, e.g. `founder` -> `Onkar`.

        The label is deployment configuration and never architectural: no
        code branches on it, nothing is keyed by it, and a deployment that
        gives none gets the id back. That is the whole reason the id stays
        generic while the founder still sees their own name.
        """
        self._check(identity_id)
        if self._known is None:
            return identity_id
        return self._known.get(identity_id) or identity_id

    def path_for(self, identity_id: str, create: bool = True) -> Path:
        """The directory this identity's browser state lives in.

        Created on demand: a first run has no directory, and an identity
        that has never signed in anywhere is a perfectly ordinary state --
        it simply resolves to an empty profile, which is what lets a first
        visit report "signed out" truthfully rather than fail.
        """
        self._check(identity_id)
        path = self._root / identity_id
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def exists(self, identity_id: str) -> bool:
        """Whether anything has ever been persisted for this identity.

        A hint about the *past*, and deliberately never an answer to "is
        this identity authenticated" -- a profile directory outlives a
        session the site has since revoked. Only an observation of the
        live page answers that, and the layer that knows how to read a
        particular site's page is the provider, never this one.
        """
        self._check(identity_id)
        path = self._root / identity_id
        return path.is_dir() and any(path.iterdir())

    def forget(self, identity_id: str) -> bool:
        """Delete everything persisted for this identity.

        The founder's own way out -- signing Kalpavriksha out of a site is
        deleting this, and nothing else has to be reasoned about because
        nothing else was ever kept. Also how an expired-session test
        arranges its precondition without touching a real account.
        """
        self._check(identity_id)
        path = self._root / identity_id
        if not path.is_dir():
            return False
        shutil.rmtree(path, ignore_errors=True)
        return not path.exists()

    def _check(self, identity_id: str) -> None:
        if not isinstance(identity_id, str) or not IDENTITY_ID_PATTERN.match(
            identity_id
        ):
            raise BrowserIdentityError(
                f"invalid browser identity id: {identity_id!r}; "
                "expected lowercase letters, digits, '_' or '-' "
                "(no path separators, drive letters or dots)"
            )
        if self._known is not None and identity_id not in self._known:
            declared = ", ".join(sorted(self._known)) or "none"
            raise BrowserIdentityError(
                f"unknown browser identity: {identity_id!r}; declared: {declared}"
            )
