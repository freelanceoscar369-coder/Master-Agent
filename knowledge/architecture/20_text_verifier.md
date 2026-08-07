# Text Verifier Architecture

## Purpose
Documents the second concrete Verifier implementation that judges generated text against expectations stated before the answer arrived — enabling the Prompt Cache and Prompt Library to function.

---

## Frozen Constitution

### Constitution §10 (Verification Philosophy — RESEARCH-BACKED)
> **Three-Part Boundary:**
> 1. **Execution produces effects** — Worker's Action runs, returns Execution Result. Says nothing about real-world outcome.
> 2. **Verification produces Evidence** — Verification Subsystem re-observes Environment Instance, compares Observation against Expected Outcome. Output = Verdict + Observation + Expected Outcome = **Evidence**.
> 3. **Evidence flows back to Brain** — routed via Shared Infrastructure as input to "is Mission complete?"

> **Why Verification stays physically near Operator but architecturally separate:** Only Operator has Environment access. Verification uses its own contract — "observe, then compare against Expected Outcome" — never reuses Worker's `validate()`/`run()`, never folds result into plain Execution Result.

### Constitution §11 (Recovery Philosophy — EVOLVABLE)
> **Mission-Level Recovery:** A failed Verdict is the trigger for recovery. Evidence flows to the Brain; Brain decides retry, re-plan, or surface to human.

### Constitution §9.2 (Evidence Hierarchy — FROZEN)
1. **Observed Reality** — what Environment actually shows, what Verification actually measured
2. **Evidence** — structured, timestamped record of Observation compared against Expected Outcome
3. **Mission Record** — persisted record, survives restart
4. **Conversation Transcript** — debugging human intent only
5. **Reasoning Provider Output** — never treated as evidence of reality

> **When documentation and observed reality conflict, observed reality wins** (Rule 8). Extends to Permanent Knowledge.

---

## Architecture Design

### From `text_verifier.py` Module Docstring
> **MB033 shipped a Prompt Cache that never hits and MB034 shipped a Prompt Library with no automatic writer. Both were blocked on the same missing piece: nothing in Kalpavriksha could tell whether a generated answer was any good.**

> **ADR-0011 froze the Verification Subsystem years ago and `BrowserVerifier` proved it generalises; this is the second Verifier, and it is a handful of lines because of that.**

### The One Interpretation Required
> **`Verifier.capture_observation_dict()` says: re-observe current real-world state fresh; never return a cached value from a prior Execution.**
>
> For a browser that means reading the page again. **For generated text there is no page — the answer is the artefact.**
>
> **The honest reading:** re-derive the observation from the artefact by deterministic measurement, every time, and never consult anybody's *opinion* of it. The observation is length, word count, whether it parses as JSON, what it contains — facts a second reader could check — and the provider is never asked whether it thinks it did well.

### What This Deliberately Is Not

**1. No model judges another model.**
> Asking an LLM whether an LLM's answer was good needs an LLM to judge *that*, and something has to break the recursion — ADR-0011 refused to start it for provider selection and MB034 refused it for memory. A verdict here is arithmetic over an `ExpectedOutcome` the caller stated in advance, which is also the only kind of verdict that is falsifiable.

**2. No new operators.**
> The five in `verification/evaluator.py` — `equals`, `contains`, `not_contains`, `exists`, `matches_regex` — express everything below. A sixth would mean editing a frozen file to save writing a regex.

### Why It Lives in `ai_infrastructure/`, Not `verification/`
> `verification/` has been frozen since MB025. Adding a file would show up in the guard diff with no ratified ADR permitting it. **Nothing frozen is touched:** this imports the published contracts (`Verifier`, `ExpectedOutcome`, `ObservationCheck`, `Evidence`) and implements the one abstract method, exactly as a Worker outside `verification/` is expected to.

---

## Core Components

### 1. `observe(text) -> dict` — Factual, JSON-Shaped View
```python
def observe(text: str) -> dict[str, Any]:
    # Returns factual, JSON-shaped view of generated text
    # Every field is something a second reader could recompute from the same string
    # Nothing is an opinion, a score, or a claim by whoever produced it
```

**Observation Fields:**
| Field | Description |
|-------|-------------|
| `text` | Clipped text (max 100,000 chars) |
| `normalised` | Lower-cased, whitespace-collapsed for case-insensitive `contains` |
| `empty` | Boolean: is stripped text empty? |
| `length` | Character count of stripped text |
| `word_count` | Word count of stripped text |
| `line_count` | Non-empty line count |
| `first_line` | First non-empty line |
| `last_line` | Last non-empty line |
| `truncated` | Boolean: was text clipped? |
| `is_json` | Boolean: does text parse as JSON? |
| `json` | Parsed JSON object (if `is_json`) |

**JSON Parsing:** Handles fenced blocks (```json ... ```) — unwraps before parsing.

### 2. `TextVerifier` — Concrete Verifier Implementation
```python
class TextVerifier(Verifier):
    worker_name = "text"
    environment_name = "generated_text"
    
    def __init__(self, text: str, worker: str = "text"):
        self._text = text
        self.worker_name = worker
    
    def capture_observation_dict(self) -> dict[str, Any]:
        return observe(self._text)  # Re-derived every verify() call
```

**Key Principle:** Constructed with the artefact, not a way of fetching it — for generated text there is nothing to fetch. Observation **recomputed on every `verify()` call** rather than stored, so verdict always derived from text in hand, never from previous judgement.

### 3. `verify_text(text, expected) -> Evidence` — Convenience Function
```python
def verify_text(text: str, expected: ExpectedOutcome, worker: str = "text") -> Evidence:
    return TextVerifier(text, worker=worker).verify(expected)
```

---

## Check Builders (Sugar over `ObservationCheck`)

| Function | ObservationCheck Produced | Description |
|----------|---------------------------|-------------|
| `not_empty()` | `field="empty", operator="equals", value=False` | "the answer is not blank" |
| `contains(phrase)` | `field="normalised", operator="contains", value=normalised_phrase` | "mentions 'phrase'" |
| `excludes(phrase)` | `field="normalised", operator="not_contains", value=normalised_phrase` | "does not mention 'phrase'" |
| `matches(pattern)` | `field="text", operator="matches_regex", value=pattern` | "matches /pattern/" |
| `is_json()` | `field="is_json", operator="equals", value=True` | "the answer parses as JSON" |
| `json_has(path)` | `field="json.{path}", operator="exists"` | "the JSON has 'path'" |
| `json_equals(path, value)` | `field="json.{path}", operator="equals", value=value` | "JSON 'path' is 'value'" |
| `at_least_words(count)` | `field="text", operator="matches_regex", value=regex` | "at least N word(s)" |

### `expect()` — Build `ExpectedOutcome` from Plain Arguments
```python
def expect(
    description: str = "a usable answer",
    contains_all: tuple[str, ...] = (),
    excludes_all: tuple[str, ...] = (),
    pattern: str = "",
    json_body: bool = False,
    json_fields: tuple[str, ...] = (),
    min_words: int = 0,
    require_non_empty: bool = True,  # Always on by default
) -> ExpectedOutcome:
```
**Every check stated *before* the answer arrives** — falsifiable rather than rationalisation.

**`require_non_empty=True` always on by default:** An `ExpectedOutcome` with no checks at all evaluates to `ERROR` under frozen evaluator (ADR-0011), and emitting one would mean the Planner produced a Step that can never be verified.

### `at_least_words()` — The Load-Bearing Regex Detail
```python
value=rf"(?:\S+\s+){{{required - 1}}}\S+"  # Note: final \S+ not \S*
```
> **The final `\S+` is load-bearing.** First version ended in `\S*` which matches empty string — so "at least 1 word" passed on a blank answer, which is precisely the silent pass this subsystem exists to prevent.

### `passed(evidence) -> bool` — Cache/Prompt Library Gate
```python
def passed(evidence: Evidence | None) -> bool:
    return evidence is not None and evidence.verdict is Verdict.MATCHED
```
**`MATCHED` only.** `PARTIALLY_MATCHED` deliberately not enough — half of what was asked for is not what was asked for, and a cache that remembered it would serve the same half answer forever.

---

## Consequences (from `text_verifier.py`)

### 1. Prompt Cache Now Stores on Evidence
- **Not on caller's promise** — `PARTIALLY_MATCHED` deliberately not enough
- Cache **ships on** because the reason it was off is gone

### 2. Prompt Library Gets Automatic Writer
- A checked prompt writes itself into the Prompt Library through an outbound port

### 3. Founder Page Shows Verdict
- `not checked` distinguished from `not matched`

---

## Current Implementation Status

| Component | Architecture Status | Implementation Status | Notes |
|-----------|---------------------|----------------------|-------|
| **`observe()` function** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | Factual, recomputed every call |
| **`TextVerifier` class** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | Implements `Verifier` ABC |
| **`verify_text()`** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | Convenience function |
| **Check Builders (8)** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | Sugar over `ObservationCheck` |
| **`expect()` builder** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | Builds `ExpectedOutcome` |
| **`at_least_words()` regex** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | Load-bearing `\S+` |
| **`passed()` gate** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | `MATCHED` only |
| **Prompt Cache Integration** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | Stores on evidence |
| **Prompt Library Writer** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | Automatic writer |
| **Founder Page Verdict** | RESEARCH-BACKED | ✅ **IMPLEMENTED** | Shows `not checked` vs `not matched` |

---

## Design vs Implementation Differences

| Area | Design (Architecture/Constitution) | Implementation | Status |
|------|-----------------------------------|----------------|--------|
| **Second Verifier** | ADR-0011 generalises | ✅ `TextVerifier` implements `Verifier` ABC | ✅ MATCH |
| **No Model Judges Model** | ADR-0011, ADR-0017 | ✅ Deterministic measurement only | ✅ MATCH |
| **No New Operators** | Five operators sufficient | ✅ Uses existing five | ✅ MATCH |
| **Lives Outside `verification/`** | Frozen package, no ADR | ✅ In `ai_infrastructure/` | ✅ MATCH |
| **Observation = Deterministic Measurement** | Re-derive from artefact | ✅ `observe()` computes facts | ✅ MATCH |
| **Re-observes Every Verify** | Never cached | ✅ `capture_observation_dict()` calls `observe()` | ✅ MATCH |
| **JSON Fence Unwrapping** | Models return fenced JSON | ✅ `_as_json()` unwraps ```json``` | ✅ MATCH |
| **`at_least_words()` Regex** | `\S+` not `\S*` | ✅ Load-bearing `\S+` | ✅ MATCH |
| **Cache on Evidence** | `MATCHED` only | ✅ `passed()` returns `verdict is MATCHED` | ✅ MATCH |
| **Prompt Library Auto-Writer** | Outbound port | ✅ Implemented | ✅ MATCH |

---

## Open Questions

1. **No Model Judges Model** — Courageous but limits semantic verification. "The answer is technically correct but misleading" cannot be caught. ADR-0011 explicitly chose this.

2. **Five Operators Fixed** — Extensibility requires editing frozen `evaluator.py`. Is the vocabulary truly complete for all text verification needs?

3. **JSON Path Dot-Notation** — `json.items.0.name` works via `get_field()`. Is this expressive enough for nested JSON verification?

4. **Truncation at 100K chars** — `MAX_OBSERVED = 100_000`. Large answers silently truncated. Is this acceptable for all use cases?

5. **No Semantic Similarity** — "The answer means the same thing" cannot be verified. Only structural/textual checks.

6. **Planner Expectation Accuracy** — `expect()` builds expectations; if Planner states wrong expectation (MB036 Finding 5), verification fails even if result is correct.

7. **`PARTIALLY_MATCHED` Not Enough** — Deliberate design choice. Half-correct answer not cached. Is this too strict for some use cases?

---

## Future Extraction Targets

1. `src/master_agent/ai_infrastructure/text_verifier.py` — Full implementation
2. `src/master_agent/verification/evaluator.py` — `evaluate_checks()`, 5 operators
3. `src/master_agent/verification/evidence.py` — `Evidence`, `ExpectedOutcome`, `Verdict`
4. `src/master_agent/verification/verifier.py` — `Verifier` ABC
5. `tests/test_text_verifier.py` — Text Verifier tests
6. `docs/MISSION_BRIEF_035.md` — Full Mission Brief with findings
7. `docs/adr/0011` — Verification as independent subsystem

---

## Wiki Links Added

- `[[KALPAVRIKSHA_VISION_V2.md]]` — Constitution §9.2, §10, §11
- `[[FOUNDER_CONSTITUTION_FREEZE.md]]` — Freeze record
- `[[AI_CAPABILITY_BROKER_ARCHITECTURE.md]]` — Broker architecture
- `[[11_verification_system.md]]` — Verification system overview
- `[[19_ai_capability_service.md]]` — AiCapabilityService wiring
- `[[system_overview.md]]` — System overview
- `[[docs/adr/0011]]` — Verification independent subsystem
- `[[docs/adr/0017]]` — AI Capability Broker (no model-judges-model)
- `[[docs/adr/0018]]` — Broker learning loop

---

*Document created from verified sources only. No Text Verifier architecture redesigned. Terminology preserved exactly. Constitution/Architecture/Implementation/Open Questions separated. Design/implementation differences recorded without reconciliation.*