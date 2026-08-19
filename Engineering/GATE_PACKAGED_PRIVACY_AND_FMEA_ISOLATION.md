# KALPAVRIKSHA — PACKAGED PRIVACY & FMEA ISOLATION ACCEPTANCE REPORT

**Date:** 2026-08-19 · **Commit:** `3f7847c` (parent `b697b54`)
**Artifact:** `dist/Kalpavriksha/Kalpavriksha.exe` — 2026-08-19 14:01:52, 34,253,665 bytes

---

## 1. Verdicts

| Pass condition | Verdict |
|---|---|
| 1. Separate persistence / profile | **PROVEN** |
| 2. Physical microphone disabled | **PROVEN** (was FAILING; two defects fixed this session) |
| 3. Automation targets the FMEA process, not a Founder process | **PROVEN** |
| **SAFE FOR AUTOMATED PACKAGED FMEA** | **YES** |

The verdict on condition 2 changed during this gate. It is reported below as it
actually happened, because the earlier packaged FMEA runs were performed under a
belief about the microphone that was false.

---

## 2. What was wrong

`KALPAVRIKSHA_DISABLE_MIC` was read correctly at the composition root and passed
into `create_window`, which accepted `microphone_enabled` — and then never passed
it on to `_build_voice`. The flag died mid-chain.

Consequence: **every packaged FMEA session ever run built a real voice pipeline.**
It was quiet only because a separate fix earlier this session made the pipeline
boot muted. The gate had been reading that quiet as "microphone disabled".

Capability present and muted is not the same claim as capability absent. The gate
asks for the second, and Part 8 states it explicitly: *"physical microphone
capability is disabled — not merely `_muted = True`. These are different
requirements."*

### 2.1 The defect underneath

Fixing the thread caused the packaged app to **crash at startup**:

```
File "master_agent\founder_edition\desktop_shell.py", line 721, in create_window
AttributeError: 'NoneType' object has no attribute 'stop'
```

With the flag finally taking effect, `_build_voice` returned `None` and
`window.events.closing += voice.stop` raised at composition time, before any
window appeared. `DesktopShellApi` guards all fifteen of its own voice call sites
— it was written to run without a pipeline — but these two lifecycle bindings
were not.

This path had never executed, because the flag had never once worked.

### 2.2 Why the tests did not catch it

The test asserted that the identifier `"microphone_enabled"` appeared somewhere
in the module. It did — on the parameter, and in a comment — while the value was
dropped in between. **A string being present is not a value being threaded.**

Both assertions were replaced with ones that check the call site and the
None-safe wiring, and **each was verified by reintroducing its defect and
confirming the test fails**, then restoring.

---

## 3. Evidence — condition 2 (microphone)

Binary-level, not source-level. `microphone_enabled` appears in `create_window`'s
`KW_NAMES` tuple in the packaged bytecode extracted from the shipped exe:

```
('whisper_model', 'piper_model_path', 'mic_permission_checker',
 'input_device_resolver', 'output_device_resolver', 'microphone_enabled')
```

Live, on the reported artifact, read via PID-bound UI Automation:

| | Normal profile | FMEA profile (mic disabled) |
|---|---|---|
| Mic label | `MUTED` — state pushed by a live pipeline | `TAP TO SPEAK` — static default, nothing pushes state |
| Startup diagnostics | `✓ Voice pipeline` | **`✗ Voice pipeline`** (STT/TTS absent) |
| WebView bridge / Conversation Engine | `✓` | `✓` — app fully functional |

`✗ Voice pipeline` is the application's own diagnostic reporting that the pipeline
was never constructed.

A mission ran to completion in the mic-disabled session
(`C:\Users\DELL\Desktop\KVMicOff`, confirmed on disk), so FMEA remains usable
with no microphone.

---

## 4. Evidence — condition 1 (isolation)

Proven by physical storage, not by configuration intent.

| | Normal root (`%LOCALAPPDATA%\Kalpavriksha\state`) | FMEA root (temp) |
|---|---|---|
| Interactions | 10 → 11 | 3 |
| Shared session ids | **none** | **none** |
| FMEA artefact names present | **no** | — |

Sequence: the FMEA session wrote 3 records and its mission into its own root at
13:54:44. The normal profile then launched clean and appended its greeting as
record 11 at 13:55:50 **to the normal store**, while the FMEA store stayed frozen
at 3. State root correctly reverted; no FMEA config inherited (**Part 13 PASS**).

FMEA audit records carry full correlation — `in_reply_to` links the mission result
to the founder turn, with `mission_id` and `completion_id` populated.

---

## 5. Evidence — condition 3 (automation targeting)

All helpers are PID-bound; no global keystrokes, no screen coordinates. PID-binding
alone proves aim, not identity — the privacy incident happened with correctly
PID-bound automation. `_assert_fmea_target()` therefore requires proof of identity
and fails closed. Three refusals demonstrated:

- `KALPAVRIKSHA_STATE_DIR` unset → refused
- session marker absent → refused
- PID mismatch → `REFUSED: pid 7752 is not the FMEA session (12856). This is very likely a founder process.`

A malformed marker refuses rather than raising, so a traceback is never mistaken
for a guard that ran.

---

## 6. Test status — stated honestly

`tests/test_mute_truth_and_fmea_isolation.py`: **14/14 pass.**

The introduced-failure check was done by **set difference against a HEAD
baseline**, not by counting: the failure sets with and without this change are
byte-identical (8 and 8). **Zero failures introduced.**

Pre-existing failures, confirmed by stashing the change and re-running at HEAD —
**not caused by this work, and not fixed by it:**

| File | Test | Cause |
|---|---|---|
| `test_desktop_shell.py` | `test_exposes_exactly_the_nine_bridge_methods` | bridge grew 9 → 15 methods |
| `test_desktop_shell.py` | `test_wires_a_fake_webview_module...` | debug URL gained `?debug=1` |
| `test_desktop_shell.py` | `test_all_true_when_everything_is_wired` | startup diagnostics drift |
| `test_founder_edition_assembly.py` / `_boot.py` | 8 tests | earlier-mission drift |

These are stale expectations from earlier missions this session. They should be
trued up, but doing so is not this gate's scope.

### 6.1 A guard that caught me

An architecture test asserts the `founder_edition` package never reads the
environment, matching on **source text**. My first explanatory comment literally
named `KALPAVRIKSHA_DISABLE_MIC` and tripped it. I initially misattributed that
failure to pre-existing drift and had to correct the claim. The comment was
reworded; the flag still arrives as an argument, and the package still names no
environment variable.

---

## 7. Cleanup

- `C:\Users\DELL\Desktop\KVFMEA_iso`, `KVMicOff` — verified empty, removed
- All `kv_fmea_*` / `kv_gate_final` temp roots — removed (copies preserved in the
  session scratchpad as evidence)
- Kalpavriksha processes running: **none**

No existing audit was deleted or mutated. No founder content was reproduced in
tests, fixtures, commits, or this report; no credentials or tokens were persisted.

---

## 8. What this changes about earlier results

Packaged FMEA runs performed before commit `3f7847c` ran with a **live (muted)
microphone**, not an absent one. Their functional findings stand. Any claim in
those reports that the microphone was disabled does not.
