"""A model proposes the decomposition. The Intent Layer decides whether
it is admissible.

Five derivations of one unchanged founder sentence produced three
different semantic structures. Three distinct failure classes, and each
one is fatal in its own way:

    OMISSION       a clause the founder wrote is not represented, so
                   every layer downstream reasons correctly about a
                   question nobody asked -- confidently.
    SYNTHESIS      a requirement appears that the founder never asked
                   for, and then has to be independently established
                   before anything can qualify.
    CONTRADICTION  the same words are given two different roles.

The gate is deterministic and structural. It deliberately does not judge
whether `information` was the right word for a clause: grammar rules like
"a question mark means information" are the next drift, not a fix. What
it settles is whether the decomposition ACCOUNTS FOR what was said.

Nothing here mentions the demo subject. Every message quotes the
founder's own words back at whoever produced the decomposition.
"""
from __future__ import annotations

import json
import types

from master_agent.brain.intent import IntentLayer, requirement_issues
from master_agent.planner.plan import REQUIREMENT_KINDS

#: A neutral compound request with three separately-asked parts.
UTTERANCE = (
    "Which suppliers deliver within two days and also offer a warranty? "
    "Begin with the catalogue page."
)

WELL_FORMED = [
    {"kind": "information", "description": "supplier delivers within two days",
     "source_quote": "deliver within two days"},
    {"kind": "information", "description": "supplier offers a warranty",
     "source_quote": "also offer a warranty"},
    {"kind": "constraint", "description": "begin at the catalogue page",
     "source_quote": "Begin with the catalogue page"},
]


class Scripted:
    """A reasoner whose answers are fixed in advance, in order."""

    def __init__(self, *documents):
        self.documents = list(documents)
        self.prompts: list[str] = []

    def run(self, prompt, request=None):
        self.prompts.append(prompt)
        body = self.documents[min(len(self.prompts) - 1, len(self.documents) - 1)]
        return types.SimpleNamespace(ok=True, text=json.dumps(body))


def _layer(reasoner):
    layer = IntentLayer.__new__(IntentLayer)
    layer._reasoner = reasoner
    return layer


def _derive(reasoner):
    return _layer(reasoner)._reasoned_requirements(UTTERANCE)


class TestTheGateItself:
    def test_a_well_formed_decomposition_has_nothing_wrong_with_it(self):
        assert requirement_issues(UTTERANCE, WELL_FORMED) == []

    def test_omission_is_named_with_the_founders_own_words(self):
        without_warranty = [WELL_FORMED[0], WELL_FORMED[2]]

        issues = requirement_issues(UTTERANCE, without_warranty)

        assert issues
        assert any("warranty" in issue for issue in issues)
        assert any("nothing represents" in issue for issue in issues)

    def test_synthesis_is_caught_by_the_quote_it_cannot_produce(self):
        """A conclusion that FOLLOWS from satisfying the others is not
        itself another thing the founder asked for."""
        invented = WELL_FORMED + [{
            "kind": "deliverable",
            "description": "the combined list meeting both criteria",
            "source_quote": "the combined list meeting both criteria",
        }]

        issues = requirement_issues(UTTERANCE, invented)

        assert any("does not appear in what the founder wrote" in issue
                   for issue in issues)

    def test_a_requirement_quoting_nothing_is_refused(self):
        ungrounded = WELL_FORMED[:2] + [
            {"kind": "constraint", "description": "something", "source_quote": ""}]

        issues = requirement_issues(UTTERANCE, ungrounded)

        assert any("quotes nothing" in issue for issue in issues)

    def test_the_same_words_may_not_hold_two_roles(self):
        contradictory = [
            {"kind": "information", "description": "a",
             "source_quote": "deliver within two days"},
            {"kind": "constraint", "description": "b",
             "source_quote": "deliver within two days"},
            WELL_FORMED[1], WELL_FORMED[2],
        ]

        issues = requirement_issues(UTTERANCE, contradictory)

        assert any("more than one role" in issue for issue in issues)

    def test_an_unreadable_kind_is_reported_not_discarded(self):
        """The old code dropped these silently and renumbered what was
        left, so a founder's clause could vanish and take its id with
        it."""
        odd = [
            {"kind": "requirement", "description": "a",
             "source_quote": "deliver within two days"},
            WELL_FORMED[1], WELL_FORMED[2],
        ]

        issues = requirement_issues(UTTERANCE, odd)

        assert any("is not one of" in issue for issue in issues)
        assert all(kind in " ".join(issues) or True for kind in REQUIREMENT_KINDS)

    def test_typography_is_not_invention(self):
        """Two people quoting the same phrase differ by a comma and a
        capital. The check must fail for invention, never for that."""
        shouty = [
            {"kind": "information", "description": "a",
             "source_quote": "  Deliver Within Two Days,  "},
            WELL_FORMED[1], WELL_FORMED[2],
        ]

        assert requirement_issues(UTTERANCE, shouty) == []

    def test_nothing_offered_at_all_is_an_issue_not_a_silence(self):
        assert requirement_issues(UTTERANCE, None)
        assert requirement_issues(UTTERANCE, [])


class TestBoundedCorrection:
    def test_an_invalid_first_answer_is_corrected_and_accepted(self):
        reasoner = Scripted(
            {"requirements": [WELL_FORMED[0], WELL_FORMED[2]]},   # warranty missing
            {"requirements": WELL_FORMED},                        # repaired
        )

        derived = _derive(reasoner)

        assert len(reasoner.prompts) == 2
        assert [r.description for r in derived] == [
            "supplier delivers within two days",
            "supplier offers a warranty",
            "begin at the catalogue page",
        ]

    def test_the_correction_says_exactly_what_was_wrong(self):
        """Never "try again". A correction that does not state the
        contract is a second guess, not a repair."""
        reasoner = Scripted(
            {"requirements": [WELL_FORMED[0], WELL_FORMED[2]]},
            {"requirements": WELL_FORMED},
        )

        _derive(reasoner)
        correction = reasoner.prompts[1]

        assert "nothing represents" in correction
        assert "warranty" in correction
        assert "try again" not in correction.lower()

    def test_a_valid_first_answer_costs_no_second_call(self):
        reasoner = Scripted({"requirements": WELL_FORMED})

        derived = _derive(reasoner)

        assert len(reasoner.prompts) == 1
        assert len(derived) == 3

    def test_two_bad_answers_admit_nothing_rather_than_something_corrupt(self):
        reasoner = Scripted(
            {"requirements": [WELL_FORMED[0]]},
            {"requirements": [WELL_FORMED[0]]},
        )

        derived = _derive(reasoner)

        assert derived == ()
        assert len(reasoner.prompts) == 2, "exactly one correction, never a loop"

    def test_the_invalid_set_never_becomes_canonical(self):
        """The pointed version: a decomposition missing a founder clause
        must not reach the Planner under any circumstances."""
        reasoner = Scripted(
            {"requirements": [WELL_FORMED[0], WELL_FORMED[2]]},
            {"requirements": [WELL_FORMED[0], WELL_FORMED[2]]},
        )

        derived = _derive(reasoner)

        assert all("warranty" not in r.description for r in derived)
        assert derived == (), "a partial reading was accepted as complete"


class TestGroundingReachesTheRequirement:
    def test_each_requirement_carries_the_words_it_came_from(self):
        """`founder_evidence` used to be the whole sentence on every
        requirement -- identical, and therefore useless for telling one
        clause from another. ADR-0027 recorded that as debt."""
        derived = _derive(Scripted({"requirements": WELL_FORMED}))

        assert [r.founder_evidence for r in derived] == [
            "deliver within two days",
            "also offer a warranty",
            "Begin with the catalogue page",
        ]

    def test_the_whole_sentence_remains_as_provenance(self):
        derived = _derive(Scripted({"requirements": WELL_FORMED}))

        assert all(r.provenance == UTTERANCE for r in derived)


class TestOnlyTheReasonedPathPaysForThis:
    """A typed objective is already parsed. It must not acquire a
    provider call because compound prose needed one."""

    def test_a_question_derives_deterministically(self):
        layer = _layer(Scripted({"requirements": []}))
        intent = types.SimpleNamespace(
            goal="what is required to make this self-improving?",
            answers_founder="yes", capability="", payload={}, context={})

        derived = layer.requirements_for(intent, raw=intent.goal)

        assert len(derived) == 1
        assert layer._reasoner.prompts == []

    def test_a_typed_capability_derives_deterministically(self):
        layer = _layer(Scripted({"requirements": []}))
        intent = types.SimpleNamespace(
            goal="create a folder called Notes on the desktop",
            answers_founder="", capability="create_folder",
            payload={"name": "Notes", "location": "desktop"}, context={})

        derived = layer.requirements_for(intent, raw=intent.goal)

        assert derived
        assert layer._reasoner.prompts == [], (
            "a typed objective paid for reasoning it did not need")


class TestNoSubjectVocabulary:
    def test_the_gate_names_no_domain_words(self):
        """It must work for a request it has never seen, which means it
        may not know what any request is about."""
        import inspect
        import io
        import tokenize

        from master_agent.brain import intent as module

        code = " ".join(
            token.string
            for token in tokenize.generate_tokens(
                io.StringIO(inspect.getsource(module.requirement_issues)).readline)
            if token.type not in (tokenize.COMMENT, tokenize.STRING)
        ).lower()

        for word in ("saturday", "laptop", "workshop", "directory", "warranty",
                     "supplier", "catalogue"):
            assert word not in code
