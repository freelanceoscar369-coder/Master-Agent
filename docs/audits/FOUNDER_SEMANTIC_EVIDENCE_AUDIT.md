# Founder semantic evidence: where it stops existing

**Question asked:** what is the FIRST point in the pipeline where founder
evidence becomes only the resolved value?

**Method:** measurement, not reading. A two-turn clarification with a
nested destination was driven through the real `IntentLayer` and the
resulting requirement ledger was printed. Reading the code hopefully is
how the defect below survived being "obviously fixed" once already.

---

## The two artefacts

Correspondence needs two things that were never allowed to collapse into
one:

| | Founder Semantic Evidence | Canonical Execution Interpretation |
|---|---|---|
| what it is | the founder's own words | the system's reading of them |
| example | `"d drive in Onkar folder"` | `location = d_drive` |
| where it lives | `SemanticRequirement.founder_evidence` | `SemanticRequirement.description` |
| who may write it | the Intent Layer, from what was said | whoever resolved the field |

If a requirement carries only the second, then outcome conformance
compares execution against the interpretation, and the only thing it can
ever discover is that the system agreed with itself. That is the
mechanism behind both failed acceptances — every link sound, the chain
internally consistent, the conclusion wrong.

---

## What the measurement found

Founder says `create a folder`, is asked the name, says `Rudra`, is asked
where, says `d drive in Onkar folder`. Ledger as it stood:

```
req_1  create a folder            evidence=''
req_2  name = Onkar/Rudra         evidence=''
req_3  location = d_drive         evidence='d drive in Onkar folder'
```

**First point: `req_2`, the composed argument.**

`CreateFolder` takes a single `name`, and a nested destination composes
it — `Onkar/Rudra` — out of `folder_name` and `parent`, supplied in two
different turns. The evidence lookup matched by field name and then by
value; the composed argument is called neither `folder_name` nor
`parent`, and its value equals nothing that was recorded. So it matched
nothing and the field came out empty.

The one requirement with no founder evidence was **the requirement
encoding the nested destination** — precisely the thing both failed
acceptances got wrong. Had the guard let a half-read reply through again,
this is the requirement that would have had nothing to audit it against.

`req_1` was empty for a duller reason: its `description` already is the
founder's objective, so nobody noticed the field beside it was blank.
A field that is *usually* redundant is still the field an audit reads.

## What was changed

- A composed argument now resolves its evidence from the parts it was
  built from, joined: `'Rudra; d drive in Onkar folder'`.
- The effect requirement carries the founder's objective explicitly.

```
req_1  create a folder            evidence='create a folder'
req_2  name = Onkar/Rudra         evidence='Rudra; d drive in Onkar folder'
req_3  location = d_drive         evidence='d drive in Onkar folder'
```

Evidence from an earlier turn survives to a requirement built at the end
of the conversation. Without that, every multi-turn mission silently
loses its earliest facts — and the name is almost always said first.

The audit is kept executable in
`tests/test_semantic_correspondence.py::TestFounderEvidenceReachesEveryRequirement`,
which fails if any requirement in that ledger carries the interpretation
alone. The answer to the question stays *no* by test, not by memory.

---

## What still does not have founder evidence

Stated plainly, because a partial audit reported as complete is the same
class of error it is auditing:

- **Requirements extracted from a compound objective by reasoning**
  (`_reasoned_requirements`) carry the objective as provenance, but their
  `description` is a model's paraphrase of a clause. The founder's exact
  words for each individual clause are not currently separated out.
  Conformance treats these no differently, so nothing is *reported* as
  satisfied on weaker grounds than elsewhere — but the audit trail is
  coarser for compound objectives than for the folder family.
- **Legacy records** written before this existed carry no requirements at
  all. `assess()` returns `UNKNOWN` for them, which is correct and is
  never rounded up.

Neither is a false SATISFIED. Both are places where an auditor would have
less to work with than the ledger above, and both are recorded rather
than closed tonight.
