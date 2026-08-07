# Health Report — C34.4: Founder Edition Finalization (Bluetooth device-detection fix)

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-07
**Status:** The device-detection bug `HEALTH_C34_3.md §3` found and reported (not fixed, per that report's own "requires architecture, stop and report" call) is now fixed — scoped exactly as this mission's founder authorized: "fix ONLY the device detection layer... do not redesign VoicePipeline."
**Ground:** No Kernel, Runtime, Conversation Engine, Communication Engine, Mission System, Desktop Executive/Operator touched. `VoicePipeline`'s state machine, VAD, interrupt handling, and stream lifecycle are structurally unchanged — this report's diff is additive (new injectable resolvers, new fallback-preserving branches), not a rewrite.

---

## 0 · What changed, in one sentence

`VoicePipeline` now accepts two optional callables — `input_device_resolver` / `output_device_resolver` — which, when injected, tell it what the OS's *actual live* default microphone/speaker is (via direct WASAPI `IMMDeviceEnumerator` access through `pycaw`, bypassing the PortAudio device-list cache `HEALTH_C34_3.md` proved never refreshes); when they name a device PortAudio's own table still lists, that device is opened by *explicit index* rather than through PortAudio's own stale "default" resolution. No resolver injected (tests, or a non-Windows dev run) → byte-for-byte the pre-C34.4 behavior.

---

## 1 · Where the code lives, and why there

Per the founder's explicit scoping ("fix ONLY the device detection layer... do not redesign VoicePipeline/ConversationEngine/CommunicationEngine"):

- The actual `pycaw`/COM calls (`_default_input_device_name`, `_default_output_device_name`) live in `kalpavriksha_desktop.py` — **not** `voice_pipeline.py`. This is the same pattern already established for `_windows_microphone_allowed` (registry) and `_open_microphone_settings` (`os.startfile`): `master_agent.founder_edition` is architecture-guarded against importing OS-touching modules directly (`test_founder_edition_boot.py::TestNothingExecutesOrCallsAI`), so anything that reaches the machine lives in the one file outside that guard and gets **injected** as a callable. Confirmed the guard still passes with this report's changes (§5).
- `voice_pipeline.py` gained two constructor parameters and three small methods (`_live_device_name`, `_resolve_input_device`, `_resolve_output_device`, `_names_match`) plus small, additive edits to `_open_stream`, `_device_watch_loop`, and `_speak_sync` — every edit either adds a new branch guarded by "was a resolver injected" or leaves the existing branch as the `else`. Nothing about the state machine (`STATE_TRANSITIONS`), the VAD, the interrupt/abandon mechanisms, or the stream lifecycle discipline changed.

---

## 2 · The fix, precisely

### 2.1 — Detection

`_device_watch_loop` (still polling every `DEVICE_POLL_INTERVAL_S` = 1.5s — the cadence is unchanged) now asks the injected resolver first: if it returns a name, that's what's compared against `self._current_device_name` to decide whether to reopen. Only when no resolver was injected does it fall back to the old `sd.query_devices(kind="input")` comparison — the exact behavior that `HEALTH_C34_3.md §3` proved goes stale.

### 2.2 — Opening the right physical device

Knowing the *name* of the live default isn't enough — `sd.InputStream()`/`sd.play()` need a PortAudio device *index* to actually bind to it. `_resolve_input_device`/`_resolve_output_device` search PortAudio's own device table (`sd.query_devices()`, no kind filter — the *enumeration*, not the stale *default pointer*) for an entry matching the live name, and pass that entry's index explicitly (`device=<idx>`) instead of leaving `device=None` (which is what invokes PortAudio's own stale default resolution). If no match is found — a device PortAudio has genuinely never enumerated — the fallback is `device=None`, unchanged pre-C34.4 behavior.

### 2.3 — The truncation bug found while building this

Discovered mid-implementation, not assumed: PortAudio lists the *same physical device* once per host API (MME, WDM-KS, DirectSound, WASAPI all appear separately in `sd.query_devices()`), and at least the classic MME entry truncates the device name to a fixed buffer. On this dev machine, `pycaw`'s live `FriendlyName` for the default mic is `"Microphone Array (2- Realtek(R) Audio)"`; PortAudio's MME-host entry for the identical hardware reads `"Microphone Array (2- Realtek(R)"` — cut off mid-word. An exact-string match would silently fail to find a match on any device whose *only* PortAudio entry happens to be truncated (this dev machine's Realtek mic happens to also have an untruncated WASAPI entry further down the table, which is why exact matching didn't visibly fail here — it would be a machine-dependent, hardware-dependent bug otherwise). Fixed with a prefix match (`_names_match`): the shorter of the two names must be a prefix of the longer. Verified by reverting to exact-match locally and re-running: `test_matches_a_portaudio_entry_truncated_relative_to_the_live_name` fails cleanly (§4).

---

## 3 · What was verified, and how

| Claim | Evidence |
|---|---|
| `pycaw` reads the live default correctly | Cross-checked against `Get-AudioDevice` (PowerShell, `AudioDeviceCmdlets`) — matched exactly, both directions, `HEALTH_C34_3.md §3.1`/`§3.2` |
| The real `VoicePipeline`, wired with the real resolvers, opens correctly and runs without crashing | Ran for 20s against real hardware (real Realtek mic/speakers — this machine's Bluetooth headset is currently offline, see §6): `state=armed device='Microphone Array (2- Realtek(R) Audio)'` on first open, matching the resolver's own direct-call output exactly; no exceptions for the full window |
| The real packaged build still launches with the new dependency bundled | Rebuilt (`pyinstaller packaging/kalpavriksha.spec --noconfirm`), launched `dist/Kalpavriksha/Kalpavriksha.exe` directly: stayed alive, memory climbed 58MB → 387MB over ~20s (matching the pre-C34.4 baseline exactly), consistent with both voice models loading and the new resolver code executing without crashing |
| Detection triggers a reopen using the live name when the frozen `query_devices()` convenience query would miss it entirely | Unit test with a fake `sounddevice` module whose `query_devices(kind=...)` stays frozen at its construction-time name (deliberately reproducing the real bug's exact shape) while the injected resolver's return value changes — reverted the fix locally, test fails with the device staying on the frozen name; restored, test passes. `TestLiveDeviceResolution::test_watch_loop_detects_a_change_the_frozen_query_would_miss` |
| The truncation-prefix fix is real, not defensive dead code | Reverted to exact-match locally, re-ran: fails. Restored: passes. §2.3 |
| No regression to the pre-C34.4 fallback path (no resolver injected) | All 57 pre-existing `test_voice_pipeline.py` tests still pass unchanged — none of them inject a resolver, so all of them exercise the exact old code path |

### What was NOT verified, and why — stated plainly

**A real mid-session device switch, with the fix in place, actually being followed.** This machine's Bluetooth headset (`Airdopes Ultra Pro`) went offline between `HEALTH_C34_3.md` and this report — confirmed via `Get-PnpDevice`, its audio endpoints show `Status: Unknown` and it no longer appears in `Get-AudioDevice -List` at all. This is an environmental change outside this session's control (most likely the earbuds auto-powered off from inactivity), not something achievable from here. Every mechanism this fix depends on has been independently verified (§3), and the specific bug this fix targets was itself proven with this exact headset in `HEALTH_C34_3.md` — but the final, end-to-end "put on the headset, watch Kalpavriksha follow it" moment has not been re-run with the fix in place. **This is the one thing recommended for the founder to personally confirm before considering this closed.**

---

## 4 · Test suite

```
tests/test_voice_pipeline.py:  66 tests (was 57; +9 for C34.4:
  TestLiveDeviceResolution — 9 tests covering: known-device explicit
  index, unknown-device fallback, no-resolver-injected parity, a
  raising resolver falling back rather than crashing, watch-loop
  detection via the live resolver, output-side resolution + fallback,
  and the truncation-prefix match)
Founder Edition suite (voice_pipeline + desktop_shell + founder_edition_
boot + founder_edition_assembly): 237 passed
```

Three of this report's specific claims were verified by reverting the
relevant code locally and re-running (not just written and trusted):
the watch-loop live-detection test, the truncation-prefix test, and
(carried over from HEALTH_C34_3.md) the underlying bug itself.

---

## 5 · Architecture guard

`test_founder_edition_boot.py::TestNothingExecutesOrCallsAI` (the guard
against `master_agent.founder_edition` importing `os`/`winreg`/`ctypes`
directly) still passes — `pycaw`/`comtypes` are never imported inside
the guarded package, only in `kalpavriksha_desktop.py`, exactly the
established pattern.

---

## 6 · Packaging

- `pyproject.toml`: `pycaw` added to the `voice` extras group, gated
  `sys_platform == 'win32'` (it is a Windows-only COM library; the
  resolvers themselves already degrade to `None` — falling back to
  pre-C34.4 behavior — on any platform or failure, so this is belt and
  suspenders, not a hard requirement).
- `packaging/kalpavriksha.spec`: added `pycaw`, `pycaw.pycaw`,
  `comtypes`, `comtypes.stream` to `hiddenimports` — PyInstaller's
  static analysis does not always follow COM-based dynamic imports.
  Verified by an actual rebuild + launch (§3), not just editing the
  spec and assuming it works.

---

## 7 · Remaining for the founder

1. **Confirm the live Bluetooth follow with working hardware** — §3's
   one open item. Put on/connect the headset, launch Kalpavriksha, then
   switch the Windows default device (or connect/disconnect) and watch
   whether the mic indicator follows without a restart.
2. Everything else from `HEALTH_C34_3.md §7` (noise-handling feature
   gap, §3.8 not independently re-verified) is unchanged by this
   report and still stands as previously recorded.
