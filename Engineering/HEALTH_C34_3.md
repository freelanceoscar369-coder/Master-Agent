# Health Report — C34.3: Founder Experience Validation (Tree + Real Audio)

**Type:** Implementation health report. Working-directory evidence only.
**Date:** 2026-08-07
**Status:** Two real Product Veda compliance bugs found and fixed (§3.5, §3.7). One critical, previously-unknown bug found and **not** fixed — it requires architecture, per this mission's own rule to stop and report rather than redesign. See §3.
**Ground:** C1–C34.2, Product Veda v1.0. No Kernel, Runtime, Conversation Engine, Mission System, Desktop Executive/Operator touched. No new backend, no UI redesign, no feature additions — the one new capability (`abandon_capture`) completes an already-specified, already-partially-built backlog item (voice interruption), not a new feature.

---

## 0 · The headline finding

**Every prior claim this project has made about automatic Bluetooth/device tracking — including this session's own HEALTH_C34_1.md and HEALTH_C34_2.md — was based on fake `sounddevice` in unit tests or on reasoning about the 1.5s poll interval. Neither ever ran a real mid-session device switch against real hardware. This report is the first time that test was actually performed, and it fails.**

```
Confirmed by direct, repeatable, controlled test (§3.1):

  Query default input device in a running Python process:  "Realtek..."
  [external, verified-real OS device switch to Bluetooth headset]
  Query the SAME process again, 6+ seconds later:           "Realtek..." (still)
  Query a BRAND NEW process:                                "Bluetooth headset" (correct)

  Same result for output devices (§3.2).
```

The cause: PortAudio caches its device table at library initialization
and does not refresh it within a running process, even after explicitly
calling `sounddevice`'s own reinitialization hooks (tested, §3.1). This
means `_device_watch_loop`'s polling strategy — the mechanism this
project has relied on since C34.1 for "automatic device tracking" —
cannot detect a real default-device change for the lifetime of the
process. A founder who launches Kalpavriksha on the laptop mic and then
puts on a Bluetooth headset would not be followed automatically; only
relaunching the app would pick up the new device.

This is reported, not fixed. A correct fix means reading the OS's live
default device through a path that bypasses PortAudio's cache (direct
WASAPI/`IMMDeviceEnumerator` access) and explicitly selecting that
device when opening streams, instead of relying on PortAudio's own
"default" resolution — genuine new architecture, forbidden by this
mission's own rules. See §3.3 for what a fix would require.

---

## 1 · Tree state verification matrix

| State | Source | Verified this report | Result |
|---|---|---|---|
| Idle | `02_ANIMATION_SYSTEM §2.2.1` | Numeric params (session C34.2 audit) + live 60fps run (§4) | Match |
| Listening | `§2.2.2` | Numeric params (prior audit) | Match |
| Thinking | `§2.2.3` | Numeric params (prior audit) | Match |
| Speaking | `§2.2.4` | Numeric params + voice-envelope formulas (prior audit) | Match |
| Celebration | `§2.2.6` | Numeric params (prior audit) | Match |
| Waiting/Attention ("Vigilance") | `§2.2.5` | Numeric params (prior audit); Waiting→Speaking transition duration bug fixed (C34.2) | Match |
| Unavailable | `03_VOICE_EXPERIENCE §3.5` (mic state, not a tree state) | **Fixed this report** — was "holds whatever," now explicitly forces tree Idle | Match (after fix) |
| Denied | `§3.5` | **Fixed this report** — bloom now dims to 0.4 as specified; tree correctly still "holds whatever state it was in" | Match (after fix) |
| Recovering | Not a named state anywhere in Product Veda | No such state exists to verify — see §2 compliance note | N/A — not a spec concept |
| Growth (trunk→canopy) | `§6.5` | Timing table (`GROWTH_WINDOWS`) verified digit-for-digit against spec in prior session audit | Match |

**Breathing continuity:** measured live, 1136 real animation frames over
~19 seconds, zero dropped/skipped frames, steady 60fps (§4). No freeze,
no restart, no pop observed in the render loop or its frame-time
tracking.

**"Recovering" is not invented here.** The mission names it as a
required state; Product Veda does not define it (`03_VOICE_EXPERIENCE
§3.1`'s nine states are `idle/armed/listening/capturing-speech/
processing/muted/denied/unavailable/error` — no `recovering`). Per this
mission's own instruction ("if something appears inconsistent, STOP,
report it, do not invent"), this is reported rather than added. The
closest real behavior — a device or permission recovering automatically
— is the `error→armed` / `denied→armed` / `unavailable→armed`
transitions already in `STATE_TRANSITIONS` (C34.2), each with its own
brief visual state, not a separate named "recovering" state.

---

## 2 · Product Veda compliance report

| Item | Status | Detail |
|---|---|---|
| Tree geometry, particles, filaments, growth timing | **Implemented** | Verified digit-for-digit against `02_ANIMATION_SYSTEM §2.1` in prior session audit |
| Six tree states' parameter tables | **Implemented** | Verified numerically against `§2.2` in prior session audit |
| State transition duration table | **Implemented** | All cells verified against `§2.3.1`; one bug found and fixed (C34.2) |
| Colour interpolation (§2.3.3, "2% per frame") | **Different** | Implemented via native CSS `transition` on `.bloom` (per-state duration tokens) rather than literal per-frame 2% JS interpolation. Functionally equivalent — CSS transitions produce the same "felt before noticed" gradual shift — but the mechanism differs from the spec's literal prose. Not fixed: rewriting a working CSS transition into hand-rolled per-frame colour math to match the letter of §2.3.3 would be optimization/rewrite with no visible behavior change, explicitly out of scope ("no optimization unless required to fix an actual bug") |
| Performance degradation ladder (§2.4) | **Implemented** | `perfLevel` tracking, hysteresis, particle/filament reduction all present in `tree.js`; never triggered in this session's real runs (canvas work ~0.54ms/frame, far under the 12ms budget — §4) |
| Mic state matrix, all nine states (§3.1) | **Implemented** | `denied` reachability and OS-permission integration built in C34.2; all nine states reachable per `STATE_TRANSITIONS`' own reachability test |
| Listening indicator, waveform (§3.2, §3.3) | **Implemented** | Verified in prior session work |
| Interrupt — Somesh's speech (§3.4) | **Implemented** | All four triggers (mic click, VAD barge-in, typing, Escape); built and tested in prior session, re-verified this report |
| Mute states — muted/denied/unavailable (§3.5) | **Implemented** | Two gaps found and fixed this report (§1) |
| Noise handling — low confidence, high ambient noise (§3.6) | **Missing** | `faster-whisper`'s `transcribe()` call in `_transcribe()` discards the per-segment confidence (`avg_logprob`) and the SNR-adjacent info it returns; no threshold logic, no "Not quite sure — say that again?" UI, no "Background noise is high" notice exist anywhere in the codebase. This is a real feature gap, not a bug — extracting confidence scores and wiring new UI copy is new capability, forbidden by this mission ("no feature additions"). Reported, not built. |
| No-speech-detected (§3.6) | **Implemented** | Silence naturally returns the mic to `armed` with no copy — this is the spec's own requirement (deliberately no feedback), already the natural behavior of the existing silence-hangover logic |
| Interrupt — founder's own capture (§3.7) | **Fixed this report** | Was entirely missing; see §1 |
| Enter-key precedence (§3.7 "which input wins") | **Implemented** | Enter always submits composer text regardless of mic state; now also abandons any in-flight capture (this report's fix) |
| Composer/mic simultaneous independence (§3.7) | **Implemented** | Verified: composer expansion never suppresses the mic ring or vice versa (CSS/DOM structurally independent) |
| Interim/final transcript styling (§3.8) | **Not independently re-verified this report** | Believed implemented from prior work; not re-audited this pass — time was spent on the higher-priority findings above |
| Startup sequence, fast-forward, reduced motion (§6) | **Implemented** | Verified and two bugs fixed in prior session (`06_STARTUP_EXPERIENCE` audit) |
| Automatic device tracking, no restart (mission's own headline requirement) | **Impossible as currently architected** | §0, §3 — PortAudio device-list caching prevents the existing polling design from detecting a real mid-session default-device change. Reported per this mission's explicit instruction, not silently worked around. |

---

## 3 · Bluetooth validation log (real hardware)

Real devices on this machine (`Get-AudioDevice -List` via the
`AudioDeviceCmdlets` PowerShell module, installed this session
specifically to drive real OS-level default-device changes — no
simulation, no mock):

```
Playback:  Headphones (Airdopes Ultra Pro)        [Bluetooth, A2DP]
Playback:  Speakers (2- Realtek(R) Audio)          [built-in]
Recording: Headset (Airdopes Ultra Pro)            [Bluetooth, HFP]
Recording: Microphone Array (2- Realtek(R) Audio)  [built-in]
```

No separate USB microphone is available on this machine — not tested,
not claimed.

### 3.1 — Input device switch, real hardware, real OS API

```
$ python Engineering/bluetooth_switch_test.py     (real VoicePipeline, real sounddevice)
1786116071.864 starting pipeline
1786116073.278 state=armed device='Microphone Array (2- Realtek(R)'
[external: Set-AudioDevice -Index 3 — verified switch to 'Headset (Airdopes Ultra Pro)']
... 27 more seconds, polling every 1.5s ...
1786116101.869 test window complete
```

No second `state=` line ever appeared. The real default changed (confirmed independently — see below); the running pipeline never noticed.

**Isolated confirmation** (fresh process, no VoicePipeline, just `sounddevice` directly):
```
Query 1 (before switch):                    Microphone Array (2- Realtek(R)
[external switch to Bluetooth confirmed by Windows itself]
Query 2 (same process, 6s later):           Microphone Array (2- Realtek(R)   <- stale
Query 3 (after sd._terminate()+_initialize()): Microphone Array (2- Realtek(R) <- still stale
Query in a BRAND NEW process:                Headset (Airdopes Ultra Pro)     <- correct
```

### 3.2 — Output device switch, real hardware

Same result, output side:
```
Query 1 (before switch):                    Speakers (2- Realtek(R) Audio)
[external switch to Bluetooth headphones confirmed by Windows itself]
Query 2, 4s later, same process:            Speakers (2- Realtek(R) Audio)   <- stale
Query 3, 8s later, same process:            Speakers (2- Realtek(R) Audio)   <- stale
```

A founder switching output devices mid-conversation (e.g. taking off
Bluetooth headphones) would not have TTS follow — playback would keep
using whatever device was default when the app launched, silently,
until the founder closes and reopens Kalpavriksha.

### 3.3 — What a real fix would require (not attempted)

The device the app actually captures/plays through is bound at
`sounddevice`/PortAudio's `Pa_GetDefaultInputDevice()` /
`Pa_GetDefaultOutputDevice()`, cached at `Pa_Initialize()`. A correct
fix means:

1. Reading the OS's live default device through a path PortAudio's
   cache cannot poison — direct `IMMDeviceEnumerator::
   GetDefaultAudioEndpoint` via `comtypes`/`ctypes`, the same WASAPI
   surface the module's own docstring has named since C34.1 as "the
   most correct Windows mechanism" for device-change notification.
2. Explicitly resolving that device to a PortAudio device index/name
   and passing `device=<that index>` to `InputStream`/`sd.play()`,
   rather than relying on PortAudio's own unspecified-device default
   resolution.
3. Handling the case where the *previously bound* device disappears
   entirely (today's polling-based reopen logic still applies for
   that case — this isn't broken, only the "the OS default changed but
   my old device is still technically present" case is).

This is new architecture: new dependency (`comtypes` or `pycaw`), a new
Windows-API integration surface, and a change to how every stream in
this module resolves its device — squarely the kind of rework this
mission's own rules say to stop and report rather than build. Not
attempted here.

### 3.4 — What this does NOT invalidate

- A device that **disappears** (unplugged, Bluetooth actually
  disconnects) still recovers correctly: `query_devices()` raising or
  returning a different result than a device that's simply removed
  from the OS's table is a different code path from "the OS default
  silently changed to another still-technically-enumerable device," and
  the existing `_open_stream`/`_device_watch_loop` retry logic (C34.2's
  busy-device fix) still applies whenever the CURRENTLY-open stream
  itself errors out — that doesn't depend on PortAudio's device-list
  cache at all, only on the open stream's own health.
- The very first device the app opens on launch is always correct —
  the cache is only stale relative to what happened *after* the process
  started.

---

## 4 · Performance measurements

**Tree, measured live in-browser** (real `requestAnimationFrame` loop, not estimated):

```
Frames captured:        1136 over 18915ms
Average FPS:             60.0
Frame delta P50:         16.7ms   (target: 16.67ms for 60fps)
Frame delta P95:         16.9ms
Max frame delta:         17.9ms
Canvas work per frame:   0.54ms average   (budget: ≤12ms, §2.4)
Perf degradation level:  0 (nominal) — never triggered
Particle count:          170 (this viewport's breakpoint)
```

**Voice stack** — carried forward from `Engineering/HEALTH_C34_2.md §9`
(same real-model, real-hardware measurements; not repeated this
session):

```
whisper_load_ms:            632.3
piper_load_ms:               3087.3
interrupt_latency_ms:        193.0
stt_transcription_ms:       1446.7  (for ~2s of audio)
input_stream_open_ms:        773.6
ram_after_both_models_mb:     290.0
```

**Bluetooth recovery latency:** not a meaningful number to report —
§3 established that recovery does not currently happen at all within a
running session, so there is no latency to measure. Reporting "0ms" or
"1.5s" here would misrepresent a feature that doesn't work as one that
works quickly.

**CPU under sustained voice load:** not measured this session — would
need a multi-minute real conversation to be meaningful, flagged as not
done in HEALTH_C34_2.md §13 and still true here.

---

## 5 · Voice acceptance — what was and wasn't tested

| Scenario | Tested | How |
|---|---|---|
| Long replies, short replies | Yes | Real Piper synthesis, varying phrase length, HEALTH_C34_2.md §9 |
| Rapid interruptions | Yes | `TestNoOverlappingPlayback`, real concurrency tracking, HEALTH_C34_2.md §2.2 |
| No overlapping speech | Yes | Same — structurally guaranteed, not probabilistic |
| No dead microphone (busy device) | Yes | `TestOpenStreamRobustness`, reverted-and-confirmed, HEALTH_C34_2.md §2.1 |
| No stuck listening (abandoned utterance) | Yes | **This report** — `TestAbandonCapture`, reverted-and-confirmed (§1) |
| No duplicated playback | Yes | `TestNoOverlappingPlayback` |
| Silence (no speech detected) | Yes | Existing silence-hangover behavior, no UI, matches §3.6 |
| Live founder speaking "Hi Somesh" out loud | **No** | Requires a live human voice into a real microphone; this environment cannot produce that input. Nothing in this report claims otherwise. |
| Device switch felt by a live founder mid-conversation | **No — and per §3, would currently fail** | See §3 |

---

## 6 · Founder Acceptance Flow (Deliverable 5)

The exact script cannot be run end-to-end by this session — it requires
a human voice and human hands on Bluetooth hardware. What can be stated
honestly:

```
Launch                                   → verified: app boots, tree renders (§4)
Tree breathing                           → verified: 60fps, continuous, no freeze (§4)
Greeting uses system clock               → verified in prior session (founder_identity.greet())
Founder says "Hi Somesh"                 → NOT RUN — needs a live human voice
Somesh replies                           → mechanism verified (real STT/TTS round-trip,
                                            HEALTH_C34_1.md §0); full loop with live
                                            speech not run
Founder interrupts                       → verified: all 4 triggers, real audio,
                                            193ms real latency (HEALTH_C34_2.md §2.2, §9)
Somesh stops                             → verified, same evidence
Founder types                            → verified: composer, submit, abandon-capture (§1)
Somesh replies                           → verified (text path, same send_message/speak)
Bluetooth headset disconnected           → mechanism for a REMOVED device verified
                                            (existing retry logic, §3.4); a SWITCHED-
                                            but-still-present device is the case §3
                                            found broken
Application recovers                     → true for device removal, not for a live
                                            default-device switch (§3)
Bluetooth reconnect                      → same caveat
Application follows automatically        → **not currently true** — §3
Tree remains alive throughout             → verified: tree state is decoupled from
                                            voice pipeline health; a broken mic does
                                            not freeze the tree (§1, §4)
```

**Recommended for the founder to personally verify**, since this
session's environment cannot: the exact device-switch behavior with the
Bluetooth headset already paired on this machine — put it on, speak, see
whether the mic indicator ever shows anything other than the state it
had on launch.

---

## 7 · Remaining founder-facing issues

1. **Critical — device tracking does not survive a live default-device
   switch** (§3). Requires the WASAPI/`comtypes` rework in §3.3.
   Founder decision needed: is this worth the architecture exception,
   given the mission's own "no architecture" rule and this being the
   single biggest gap between the current build and the mission's
   success criteria?
2. **Minor — §3.6 noise handling is unbuilt** (low-confidence /
   high-ambient-noise UI feedback). Not a regression, never existed.
   Genuine feature work if wanted.
3. **Not re-verified this pass** — §3.8 (interim/final transcript
   styling). Believed correct from prior work; flagged rather than
   silently assumed.

---

## 8 · Test suite

```
tests/test_voice_pipeline.py:  57 tests (was 53 after C34.2; +4 for abandon_capture)
tests/test_desktop_shell.py:   +2 (abandon_voice_capture bridge coverage)
Founder Edition suite (voice_pipeline + desktop_shell + founder_edition_
boot + founder_edition_assembly): 228 passed
```

Both this report's code fixes (§3.5 denied/unavailable bloom mapping,
§3.7 abandon_capture) were verified by reverting locally and re-running
— the denied/unavailable fix confirmed live in-browser against a freshly
built tree; `abandon_capture`'s two most direct tests fail cleanly
against the reverted code (two of its four tests are timing-dependent
and don't catch the regression — noted honestly rather than claiming
all four do).
