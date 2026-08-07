# Health Report — Sprint 1, Component 32: Unified Communication Layer

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-07
**Status:** Complete. **Not committed, not tagged, no Rule 001.**
**Ground:** C1–C31. No speech recognition, no TTS, no audio libraries, no desktop, no Runtime mutation, no planning — none built.

---

## 1 · What was built

```
   VoiceInput.receive() ──┐
                          ├──►  CommunicationRequest  ──►  CommunicationEngine.handle()
   TextInput.receive() ───┘                                     │
                                                                  ▼
                                                          CommunicationRouter.route()
                                                                  │
                                        switches mode?  ──yes──►  flip mode, acknowledge
                                                (ConversationEngine never called)
                                                                  │ no
                                                                  ▼
                                                  ConversationEngine.reply(content, moment)
                                                                  │
                                                     no reply (UNKNOWN) ──►  RoutedResponse = None
                                                                  │ yes
                                                                  ▼
                                                     RoutedResponse(response, mode, channels)
                                                                  │
                                        ┌─────────────────────────┴──────────────────────┐
                                        ▼                                                  ▼
                              VoiceOutput.emit(response)                       TextOutput.emit(response)
                          (only if "voice" ∈ channels)                    (only if "text" ∈ channels)
```

**Five files, exactly the brief's own list**, plus `__init__.py`:

| File | Role | Statements |
|---|---|---|
| `request.py` | `Source`, `CommunicationRequest` — one shape, however the founder spoke | 25 |
| `response.py` | `CommunicationResponse` — three strings, never audio | 21 |
| `channels.py` | `OutputMode`, `VoiceInput`, `TextInput`, `VoiceOutput`, `TextOutput` — abstract only | 13 |
| `router.py` | `CommunicationRouter`, `RoutedResponse` — request → engine → response → channel names, plus mode switching | 56 |
| `engine.py` | `CommunicationEngine`, `ChannelNotRegistered` — the one public door | 41 |

**163 statements. 100% coverage. Ruff clean. 106 tests (minimum was 90).**

---

## 2 · The brief's own scenarios, run end to end

```
>>> comm.handle(request("Good morning Somesh", source=Source.VOICE))
RoutedResponse(response=..., mode=VOICE_ONLY, channels=("voice",))
>>> comm.handle(request("Good morning Somesh", source=Source.TEXT))
RoutedResponse(response=..., mode=VOICE_ONLY, channels=("voice",))
# identical .response.text for both — the router never told
# ConversationEngine which channel asked

>>> comm.handle(request("Somesh, switch to text."))
RoutedResponse(response=CommunicationResponse(text="Switched to text."),
                mode=TEXT_ONLY, channels=("text",))

>>> comm.handle(request("switch to both"))
>>> comm.handle(request("Continue"))
# both a SpyVoiceOutput and a SpyTextOutput receive the same
# CommunicationResponse object, in one call — voice and text
# simultaneously, from one round trip
```

`tests/test_communication.py::TestEndToEnd::test_the_briefs_own_switching_
dialogue` runs this exact sequence and counts what landed on each spy
channel at each step.

---

## 3 · Conversation Engine never learns the transport — proven, not promised

Two structural facts, each with its own test:

1. **`CommunicationRouter.route()` never passes `source` to
   `ConversationEngine.reply()`** — only `request.content` and
   `request.timestamp` cross that boundary.
   `test_the_conversation_engine_is_never_told_which_channel_asked` sends
   the identical text through `Source.VOICE` and `Source.TEXT` and
   asserts byte-identical replies.
2. **`communication/` cannot even *import* `founder_runtime`.**
   `test_runtime_is_never_imported_at_all` checks this directly — a
   stronger guarantee than *"does not mutate,"* since a package that
   cannot construct or hold a `FounderRuntime` reference cannot mutate
   one by construction, the same discipline C23's own door uses for
   Kernel authority (`AUTHORITY_UNREACHABLE`).

The only `master_agent.*` roots this package may import are itself,
`conversation_engine`, and `memory` —
`test_the_only_master_agent_door_is_communication_or_conversation_engine_
or_memory` checks the closed set by AST across every file. `desktop.*`,
`founder_edition`, `founder_runtime`, `founder_identity`, and
`master_agent.voice` are all in the forbidden root list — the last one
deliberately (see §5).

---

## 4 · No implementation — checked at the method-body level, not just the import level

*"Provide abstract interfaces only... No implementation."*
`TestNoImplementationLeakage::test_every_method_body_is_exactly_ellipsis`
parses `channels.py` by AST and asserts each of `VoiceInput.receive`,
`TextInput.receive`, `VoiceOutput.emit`, `TextOutput.emit` has a body of
exactly one statement — `...` — nothing that could be mistaken for a real
read, a real write, or a real network call. A second guard checks for
audio-shaped identifiers (`microphone`, `speaker`, `audio_bytes`,
`sample_rate`, `wav`/`mp3`/`pcm`) used as an actual name anywhere in the
package — narrowed to identifiers, not prose, so the docstrings'
own *"No microphone. No speakers."* do not trip their own guard.

**The guard was proven able to fail.** A throwaway file containing
`import subprocess`, `from master_agent.desktop.inventory import
discover`, and `import pyttsx3` was added to the package and both import
guards re-run — both tripped — then the file was deleted and the suite
returned to green.

---

## 5 · Two stated interpretation decisions

### 5.1 `OutputMode.BOTH` vs `VOICE_AND_TEXT`

The brief names the same type two different ways: *"expose it as
`OutputMode.BOTH`"* in one section, and lists the actual members as
`VOICE_ONLY` / `TEXT_ONLY` / `VOICE_AND_TEXT` in its own *"Output Modes"*
section. `channels.OutputMode` uses `VOICE_AND_TEXT` — the spelling that
appears in the section that actually enumerates the type's members —
argued in `channels.py`'s own docstring at the point a reader would ask,
the same way C30 and C31 each recorded their own brief reconciliations.

### 5.2 Mode-switch phrases are recognised in `router.py`, not in C31's `IntentClassifier`

*"Founder can say 'switch to text.' Conversation Engine returns intent.
Communication layer changes routing."* Read literally, this asks C31 to
grow a seventh `Intent`. It was not: C31 is a complete, audited-pending
component (`Engineering/HEALTH_C31.md`), and *"switch to text"* is not
conversational content — it is an instruction about **how** Somesh
should answer, which is exactly the "transport" C31's own boundary says
it must never know about.

`router._requested_mode()` recognises the phrase **before**
`ConversationEngine.reply()` is ever called, using the same closed-
vocabulary discipline `founder_identity.continuity.is_continuation_
request` already established. A switch request therefore:

- never reaches `ConversationEngine` at all (`test_a_switch_never_
  reaches_the_conversation_engine` asserts zero turns recorded for it),
- never grows the conversation history (`test_a_mode_switch_does_not_
  grow_history`),
- and is answered by a fixed acknowledgement this router composes
  itself, never delegated prose.

This satisfies the requirement's own intent more literally than editing
C31 would: the routing decision is made by the layer that owns routing,
and `ConversationEngine` stays exactly as unaware of channels as its own
boundary requires — not merely unaware of *which* channel, but unaware
that a switch happened at all.

---

## 6 · Reuse, not duplication

| Reused (brief's own list) | How |
|---|---|
| Conversation Engine | `CommunicationRouter` holds one `ConversationEngine`, never constructs one |
| Conversation Memory | `CommunicationEngine.history()` reads the **same** `ConversationMemory` instance the caller's `ConversationEngine` already holds — never a second history (`test_history_reads_the_same_memory_the_engine_uses_not_a_copy`) |
| Founder Runtime | Not imported at all (§3) — reused *through* `ConversationEngine`, never reached directly |
| Founder Identity | Not imported — same reasoning; `ConversationEngine` already carries it |

`master_agent.voice` (`Speaker`/`Transcriber`) was **considered and not
reused.** It is a differently-scoped subsystem predating C1 (its own
docstrings cite `ARCHITECTURE.md §4.8`), both of its concrete
implementations already `raise NotImplementedError`, and depending on it
here would blur this package's own boundary for no benefit — every fact
`channels.py` needs about "a channel" is already expressible in
`CommunicationRequest`/`CommunicationResponse` alone. Recorded in
`channels.py`'s own docstring rather than silently decided.

---

## 7 · Known limitations

1. **`ConversationEngine.reply()` is always called with `desktop=None`.**
   `CommunicationRouter` has no way to obtain a `DesktopStatus` — it does
   not import `desktop.*` or `founder_edition` by design (§3) — so every
   status query routed through this layer answers as if desktop
   readiness were unknown. This is the same honest gap C31 itself
   already names in its own §8 (not wired into `founder_edition` yet);
   C32 does not close it, and closing it is composition work for
   whichever future step wires all three together.
2. **No real `VoiceInput`/`VoiceOutput`/`TextInput`/`TextOutput` exists.**
   By design (§4) — this component delivers the abstraction, not an
   implementation. Every test exercises the router and engine against
   spy/fixed subclasses built for the test file itself.
3. **Mode-switch phrases are a closed, English-only vocabulary.** The
   same trade-off C29's greeting/continuity recognisers already made:
   narrow and predictable rather than fuzzy and occasionally wrong.
4. **`conversation_id` is accepted and validated but not yet used to
   separate sessions.** `ConversationMemory` (Layer 1) holds one
   session's turns; there is no multi-conversation routing anywhere in
   C1–C31 for this field to select between. Carried as a forward-
   compatible field, honestly unused today — the same pattern C30's
   `DesktopStatus.detail` already established.
5. **Not wired into `founder_edition`.** Scoped identically to C31's own
   §8: this brief asked for `communication/` itself; connecting
   `CommunicationEngine` to `boot_founder_edition()` — and deciding how a
   real `VoiceInput`/`TextInput` eventually reaches it — is left for a
   future step.

---

## 8 · Test evidence

```
python -m pytest tests/test_communication.py -q
  106 passed

python -m pytest tests/test_communication.py --cov=master_agent.communication
  __init__.py     7 stmts   0 miss  100%
  channels.py    13 stmts   0 miss  100%
  engine.py      41 stmts   0 miss  100%
  request.py     25 stmts   0 miss  100%
  response.py    21 stmts   0 miss  100%
  router.py      56 stmts   0 miss  100%
  TOTAL         163 stmts   0 miss  100%

python -m ruff check src/master_agent/communication/ tests/test_communication.py
  All checks passed!

python -m pytest tests/test_communication.py tests/test_conversation_engine.py \
                tests/test_founder_identity.py tests/test_founder_runtime.py \
                tests/test_founder_edition_boot.py tests/test_founder_edition_assembly.py -q
  465 passed
```

**Frozen packages and prior deliverables:**

```
git status --porcelain -- foundation kernel ledger coordinator runtime_bridge api
→ (empty)

git status --porcelain -- founder_runtime founder_identity founder_edition
                          conversation_engine desktop voice
→ (only the untracked directories themselves; no tracked file modified)
```

Every source package C32 touched is `communication/`, new and untracked.

---

*End of report. Working-directory evidence only. No commits, no tags, no
Rule 001 milestone declared. Stop. Waiting for Hermes audit.*
