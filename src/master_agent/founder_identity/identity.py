"""`FounderIdentity` — who the founder is speaking to. C29.

Not a personality engine and not a config loader. This is the fixed,
declarative fact of the identity: a name, an edition, a way of talking. It
holds no state that changes turn to turn — that is `FounderSession`'s job
— and it makes no decision, plans nothing, and reaches nothing outside
this module.

"Founder Edition NEVER exposes internal architecture": nothing on this
type ever names Founder Runtime, a Kernel, a plugin or a component number.
`assistant_name` is `"Somesh"`, not `"Founder Runtime"`, and no field here
can be set to a string containing the word `Runtime`, `Kernel`, `Engine`
or `Bridge` — checked, not merely intended (`_INTERNAL_WORDS`).
"""
from __future__ import annotations

from dataclasses import dataclass, field

#: Words that would leak internal architecture into a founder-facing
#: identity field. Checked at construction so a typo cannot ship one.
_INTERNAL_WORDS: tuple[str, ...] = (
    "runtime",
    "kernel",
    "engine",
    "bridge",
    "coordinator",
    "orchestrator",
)

#: The three tones a greeting or acknowledgement may take. Closed, because
#: an unlisted fourth tone would be a mood this brief never asked for:
#: calm, professional, warm — "never over-enthusiastic, never robotic."
GREETING_STYLES: tuple[str, ...] = ("calm", "professional", "warm")

#: The personality this brief actually specifies, held as the default so
#: every `FounderIdentity` constructed without an override already reads
#: the way the brief describes Somesh, rather than an empty tuple that
#: happens to pass validation.
DEFAULT_TRAITS: tuple[str, ...] = ("calm", "professional", "warm", "focused")


def _contains_internal_word(value: str) -> str | None:
    lowered = value.lower()
    for word in _INTERNAL_WORDS:
        if word in lowered:
            return word
    return None


@dataclass(frozen=True)
class FounderIdentity:
    """The fixed shape of Somesh: a name, an edition, a manner of speech.

    Frozen — an identity that could be mutated mid-conversation would let
    one turn quietly become a different founder edition than the one that
    greeted the founder a moment before.
    """

    founder_name: str
    assistant_name: str = "Somesh"
    edition: str = "Kalpavriksha Founder Edition"
    version: str = "C29"
    greeting_style: str = "calm"
    personality_traits: tuple[str, ...] = field(default=DEFAULT_TRAITS)

    def __post_init__(self) -> None:
        if not self.founder_name.strip():
            raise ValueError("founder_name must be a non-empty string")
        if not self.assistant_name.strip():
            raise ValueError("assistant_name must be a non-empty string")
        if self.greeting_style not in GREETING_STYLES:
            raise ValueError(
                f"greeting_style must be one of {GREETING_STYLES}; got "
                f"{self.greeting_style!r}"
            )
        if not self.personality_traits:
            raise ValueError("personality_traits must not be empty")

        for field_name, value in (
            ("founder_name", self.founder_name),
            ("assistant_name", self.assistant_name),
            ("edition", self.edition),
        ):
            leaked = _contains_internal_word(value)
            if leaked is not None:
                raise ValueError(
                    f"{field_name} may not name internal architecture; "
                    f"{value!r} contains {leaked!r}"
                )

    def as_dict(self) -> dict[str, object]:
        return {
            "founder_name": self.founder_name,
            "assistant_name": self.assistant_name,
            "edition": self.edition,
            "version": self.version,
            "greeting_style": self.greeting_style,
            "personality_traits": list(self.personality_traits),
        }
