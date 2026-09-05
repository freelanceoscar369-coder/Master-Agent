"""A reply taller than the window is still the whole reply.

Measured live on 2026-09-05, mid-reply, inside ChatGPT Desktop: of 470
text-bearing elements carrying content, 14 survived the candidate scan
and 454 were dropped by the `IsOffscreen` flag alone -- 349 of them
scrolled entirely above the viewport, complete text intact in the
accessibility tree. Nothing was virtualised away. The obligation audit's
opening `{"regions": [` was sitting right there and the scan would not
look at it, so the Brain was told the audit "was not a JSON object"
about an answer the model had got right.

Reading the scrollback is only safe if the turn can be bounded, and a
repeated prompt cannot bound it: a retry sends the same characters, so
its earlier self is indistinguishable, and anchoring on that hands back
the PREVIOUS exchange. The per-call session marker is what tells them
apart -- unique, timestamped, minted per request, and written into the
prompt's own visible text.
"""
from __future__ import annotations

from tests.test_desktop_uia import FakeUiaElement, _bridge_with_elements

MARKER_OLD = "[Kalpavriksha Reasoning - ChatGPT Desktop - 2026-09-05 12:00:00 - aaaaaaaa]"
MARKER_NOW = "[Kalpavriksha Reasoning - ChatGPT Desktop - 2026-09-05 15:00:00 - bbbbbbbb]"

#: Identical in both turns, which is the whole difficulty: the mission
#: retried, and the second request is character-for-character the first.
BODY = (
    "Audit whether the proposed obligations preserve the founder's meaning. "
    "Return a JSON object with one key, regions, and nothing else."
)
PROMPT_NOW = MARKER_NOW + "\n\n" + BODY

HEAD = '{"regions": ['
MIDDLE = '{"region_id": "region_1", "meaning": "create the folder"}'
TAIL = "]}"
WHOLE = "\n".join([HEAD, MIDDLE, TAIL])


def _transcript():
    """One window, two turns, the newer one taller than the viewport.

    The tops are the real shape: the older turn far above the window,
    this turn's own prompt above it too, and only the reply's last line
    still drawn inside the 0..900 viewport.
    """
    return [
        FakeUiaElement(name="m0", has_text=True, rect=(0, -900, 400, -870),
                       text=MARKER_OLD, is_offscreen=True),
        FakeUiaElement(name="p0", has_text=True, rect=(0, -860, 400, -820),
                       text=BODY, is_offscreen=True),
        FakeUiaElement(name="r0", has_text=True, rect=(0, -800, 400, -770),
                       text='{"regions": [{"region_id": "PREVIOUS_TURN"}]}',
                       is_offscreen=True),
        FakeUiaElement(name="m1", has_text=True, rect=(0, -700, 400, -670),
                       text=MARKER_NOW, is_offscreen=True),
        FakeUiaElement(name="p1", has_text=True, rect=(0, -660, 400, -620),
                       text=BODY, is_offscreen=True),
        FakeUiaElement(name="a1", has_text=True, rect=(0, -600, 400, -570),
                       text=HEAD, is_offscreen=True),
        FakeUiaElement(name="a2", has_text=True, rect=(0, -100, 400, -70),
                       text=MIDDLE, is_offscreen=True),
        FakeUiaElement(name="a3", has_text=True, rect=(0, 100, 400, 130),
                       text=TAIL, is_offscreen=False),
    ]


def _reconstruct(marker=MARKER_NOW, elements=None):
    bridge = _bridge_with_elements(elements or _transcript(),
                                   window_rect=(0, 0, 400, 900))
    return bridge.find_new_response(
        1, {}, exclude_text=PROMPT_NOW, min_height=8, turn_marker=marker,
    )


class TestTheWholeReplyIsRead:

    def test_the_head_that_scrolled_away_is_part_of_the_answer(self):
        """The live defect, exactly: an answer that opens with
        `{"regions": [` arriving without it."""
        assert HEAD in (_reconstruct() or "")

    def test_the_reply_is_reconstructed_whole_and_in_order(self):
        assert _reconstruct() == WHOLE

    def test_it_parses_as_the_json_the_brain_asked_for(self):
        import json
        json.loads(_reconstruct())


class TestTheTurnIsBounded:

    def test_the_previous_turns_reply_is_not_returned(self):
        """An identical earlier prompt sits above this one. Anchoring on
        that would put the previous answer -- complete, well-formed, and
        about the question before last -- in front of the Brain."""
        assert "PREVIOUS_TURN" not in (_reconstruct() or "")

    def test_this_turns_own_prompt_is_not_returned_as_the_answer(self):
        result = _reconstruct() or ""
        assert MARKER_NOW not in result
        assert BODY not in result

    def test_a_marker_that_is_nowhere_in_the_window_reads_only_the_viewport(self):
        """Not the whole scrollback. With no located identity there is no
        turn boundary, and sweeping the transcript would hand back the
        entire conversation as this one reply."""
        result = _reconstruct(marker="[Kalpavriksha Reasoning - nothing - zzzzzzzz]") or ""
        assert "PREVIOUS_TURN" not in result
        assert HEAD not in result

    def test_with_no_marker_at_all_nothing_widens(self):
        """Every existing caller passes none, and they must behave
        exactly as they did -- the viewport, and only the viewport."""
        result = _reconstruct(marker="") or ""
        assert "PREVIOUS_TURN" not in result
        assert HEAD not in result
