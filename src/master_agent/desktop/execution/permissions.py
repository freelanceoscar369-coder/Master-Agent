"""C26 · Founder Edition Permission boundary — stated, and enforced by
absence.

The brief gives two lists. Both are reproduced verbatim below as data, so
a test can check them mechanically rather than trusting a paraphrase:

> Founder Edition MAY: open software, close software, focus windows,
> type, click, paste, browse, interact with installed applications.
>
> It MUST NOT: install software, uninstall software, elevate privileges,
> change system settings, modify registry, access passwords, inspect
> private conversations.

**The enforcement is structural, not a runtime check.** There is no
`install()`, `uninstall()`, `elevate()`, `change_settings()`,
`modify_registry()`, `access_passwords()` or `inspect_conversations()`
method anywhere in `desktop/execution/` — not stubbed, not raising, not
present at all. `assert_never_forbidden()` exists so a test can name the
seven forbidden verbs and assert none of them is a callable anywhere in
the package, which is a stronger guarantee than a runtime gate that could
itself have a bug: a method that does not exist cannot be called by
mistake, called with the gate bypassed, or called before the gate runs.
"""
from __future__ import annotations

#: The brief's own eight, verbatim.
PERMITTED_OPERATIONS: tuple[str, ...] = (
    "open software",
    "close software",
    "focus windows",
    "type",
    "click",
    "paste",
    "browse",
    "interact with installed applications",
)

#: The brief's own seven, verbatim. No method of this name exists
#: anywhere in `desktop/execution/` — see `tests/test_desktop_execution.py`
#: `TestPermissionBoundaries`.
FORBIDDEN_OPERATIONS: tuple[str, ...] = (
    "install software",
    "uninstall software",
    "elevate privileges",
    "change system settings",
    "modify registry",
    "access passwords",
    "inspect private conversations",
)

#: The forbidden operations, as the method names a violation would have
#: to take. Held separately from the prose list above because a method
#: name and its English description are different strings, and a test
#: asserting method-name absence needs the method-name form.
FORBIDDEN_METHOD_NAMES: tuple[str, ...] = (
    "install",
    "uninstall",
    "elevate",
    "elevate_privileges",
    "change_settings",
    "modify_registry",
    "access_passwords",
    "read_passwords",
    "inspect_conversations",
    "read_conversations",
)
