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


# ──────────────────────────────────────────────────────────────────────
# The live shape, measured on a settled obligation audit in ChatGPT
# Desktop on 2026-09-05: inside ONE traversal the echoed prompt's own
# fragments climbed from top=-946 to top=1691, and the reply -- walked
# straight after them, and drawn below them -- reported top=-442. The
# layout moves while the tree is read, so rectangles taken early and
# late in a walk describe different scroll positions and cannot be
# compared. Document order can.
# ──────────────────────────────────────────────────────────────────────

AUDIT_MARKER = "[Kalpavriksha Reasoning - ChatGPT Desktop - 2026-09-05 15:20:09 - 87a6021d]"
AUDIT_BODY = (
    'Audit the obligations. DETERMINISTIC SOURCE REGIONS: '
    '[{"region_index": 1, "text": "do the thing"}] '
    'Return JSON only: {"regions": [{"region_index": 1, '
    '"disposition": "..."}], "valid": true}'
)
AUDIT_PROMPT = AUDIT_MARKER + "\n\n" + AUDIT_BODY

#: How the prompt actually renders: a few long runs and a scattering of
#: one-character ones, because an underscore breaks a run in two.
ECHO = [
    (-946, AUDIT_MARKER),
    (200, "Audit the obligations. DETERMINISTIC SOURCE REGIONS:"),
    (700, '[{"region'),
    (700, "_"),
    (900, 'index": 1, "text": "do the thing"}]'),
    (1200, "Return JSON only:"),
    (1450, '{"regions": [{"region'),
    (1450, "_"),
    (1691, 'index": 1, "disposition": "..."}], "valid": true}'),
]

#: The answer, as inline runs, at tops that sit ABOVE the tail of the
#: prompt they follow.
ANSWER = [
    (-442, '{"regions"'),
    (-442, ':[{"region_index":1,"disposition":"omitted","anchor_id":"","notes":[]}]'),
    (12, ',"anchors"'),
    (12, ":[]"),
    (12, ',"valid"'),
    (12, ":false"),
    (12, "}"),
]
ANSWER_TEXT = "\n".join(text for _top, text in ANSWER)


def _audit_transcript():
    #: `left` varies per run because inline runs sharing a line start at
    #: different x, and regions are keyed by their whole rectangle --
    #: identical lefts would collapse two runs into one entry and test
    #: something the window never does.
    return [
        FakeUiaElement(name=f"e{i}", has_text=True,
                       rect=(i * 7, top, 400, top + 30), text=text,
                       is_offscreen=True)
        for i, (top, text) in enumerate(ECHO + ANSWER)
    ]


def _audit_reconstruct():
    bridge = _bridge_with_elements(_audit_transcript(),
                                   window_rect=(0, 0, 400, 823))
    return bridge.find_new_response(
        1, {}, exclude_text=AUDIT_PROMPT, min_height=8,
        turn_marker=AUDIT_MARKER,
    )


class TestCoordinatesThatShiftMidWalk:

    def test_the_answer_is_not_lost_below_a_floor_built_from_moving_rows(self):
        """The live failure. Every answer run sits at a smaller `top`
        than the prompt's last run, so a geometric floor discards all of
        it and the Brain is told the audit was not a JSON object."""
        assert _audit_reconstruct() == ANSWER_TEXT

    def test_it_parses(self):
        import json
        parsed = json.loads(_audit_reconstruct())
        assert parsed["valid"] is False
        assert parsed["anchors"] == []

    def test_the_echoed_prompt_is_spent_to_its_very_end(self):
        """Down to the one-character runs. Skipping short fragments
        strands the boundary inside our own question and hands its tail
        to the Brain as the answer."""
        result = _audit_reconstruct()
        assert "Return JSON only" not in result
        assert '"disposition": "..."' not in result

    def test_a_reply_opening_with_words_the_prompt_also_used_is_kept(self):
        """The prompt shows the schema, so it contains `{"regions"` too.
        Once the prompt is spent, the same characters arriving again are
        the answer."""
        assert _audit_reconstruct().startswith('{"regions"')


class TestARunIsNotMistakenForTheWholeAnswer:

    def test_inline_runs_are_not_collapsed_into_one_of_themselves(self):
        """`:[]` and `}` occur inside the big object run, so a plain
        containment count reaches two at once and returns that run alone
        -- a fragment of the answer, well-formed enough to look like all
        of it."""
        result = _audit_reconstruct()
        assert result != ANSWER[1][1]
        assert ',"valid"' in result
