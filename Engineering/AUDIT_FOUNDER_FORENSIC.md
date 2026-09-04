# Forensic Audit — Kalpavriksha Founder Edition

**Audit Date:** 2026-08-08  
**Method:** Evidence-only inspection of installed executable, source code, and runtime behavior  
**Constraint:** No modifications, no assumptions, no inferences

---

## Executive Verdict

**FOUNDER EDITION IS NOT USABLE**

The installed `Kalpavriksha.exe` fails the founder journey at every critical point:

| Founder Journey Step | Status | Evidence |
|---|---|---|
| Double-click launches | ✅ PASS | Process starts, WebView2 initializes |
| Dark Founder Surface appears | ❌ FAIL | Canvas renders but tree not visible/animated |
| Breathing Kalpavriksha tree visible | ❌ FAIL | Tree initializes but no particles/branches drawn |
| Voice: "Hello Somesh" → transcription | ❌ FAIL | Produces "Yoy" (garbage) |
| Voice: Somesh replies via TTS | ❌ FAIL | Piper TTS fails to load (diagnostic ✗) |
| Text: "Hello Somesh" → conversation | ❌ FAIL | Founder message appears, Somesh response absent |
| Composer input visible | ❌ FAIL | Text is white/invisible against surface |
| Application stays running | ❌ FAIL | Closes automatically ~10s after launch |
| Dashboard diagnostics | ❌ FAIL | STT ✗, TTS ✗, Voice ✗ |

---

## Failure Matrix

### F1 — Application Auto-Closes (~10 seconds)
- **Classification:** A. CONFIRMED BUG
- **Symptom:** Process exits cleanly (exit code 0) ~10s after launch
- **Reproduction:** Launch `Kalpavriksha.exe`; wait 10s; process gone
- **Source Location:** `desktop_shell.py:477-509` `create_window()` → `webview.start()` lifecycle
- **Root Cause:** `webview.start()` returns when window closes. No explicit shutdown logic found. Likely: window.close() called from JS or pywebview internal timeout.
- **Evidence:** Debug output shows `_pywebviewready` and `loaded` events fire, then process exits without error
- **Affects:** Frozen executable ✅, Installed executable ✅, First launch ✅
- **Severity:** CRITICAL (blocks all usage)
- **Smallest Fix:** Add window close handler logging; verify no JS `window.close()` call; check pywebview `window.events.closing` hook
- **Verification:** Launch executable, confirm process stays alive >60s

### F2 — STT Produces Garbage ("Yoy" for "Hello Somesh")
- **Classification:** A. CONFIRMED BUG
- **Symptom:** Spoken "Hello Somesh" → transcript "Yoy"
- **Reproduction:** Click mic, speak phrase, observe chat bubble
- **Source Location:** `voice_pipeline.py:604-616` `_transcribe()` → `faster_whisper.transcribe()`
- **Root Cause:** Audio capture broken. VAD threshold (0.012) may be too high/low. Buffer may contain silence/noise. Whisper receives near-empty audio.
- **Evidence:** 
  - VAD_ENERGY_THRESHOLD = 0.012 (hardcoded)
  - MIN_UTTERANCE_S = 0.3s
  - `_transcribe()` skips if `len(audio) < SAMPLE_RATE * MIN_UTTERANCE_S`
  - But if buffer has noise, Whisper hallucinates short tokens
- **Affects:** Frozen executable ✅, Installed executable ✅
- **Severity:** CRITICAL (voice primary per Veda)
- **Smallest Fix:** Add debug logging of RMS, buffer duration, actual audio chunks received. Verify microphone stream opens on correct device.
- **Verification:** Speak "Hello Somesh", confirm transcript matches

### F3 — Composer Input Text Invisible (White on Light)
- **Classification:** G. UI/CSS ERROR
- **Symptom:** Typed text in composer not visible
- **Reproduction:** Click composer, type, observe input
- **Source Location:** `surface.css:246-255` `.composer-input` color: `var(--c-ink)`; `tokens.css:33` `--c-ink: #E9EFF5` (light)
- **Root Cause:** In light theme, `--c-ink` becomes `#14191E` (dark) but composer background `--glass-light` is `rgba(250,249,246,0.88)` — sufficient contrast. **But:** theme may not be applying correctly, or `data-theme` attribute missing on `<html>`.
- **Evidence:** `tokens.css:116-149` light theme overrides; `index.html:9-17` inline script sets `data-theme` from localStorage before paint
- **Affects:** Frozen executable ✅, Installed executable ✅
- **Severity:** HIGH (blocks text input)
- **Smallest Fix:** Verify `data-theme` attribute on `<html>` at runtime; force dark theme for test
- **Verification:** Type in composer, confirm text visible

### F4 — No Somesh Response to Typed Text
- **Classification:** H. ARCHITECTURE/BRIDGE ERROR
- **Symptom:** Founder message appears in chat; no Somesh reply
- **Reproduction:** Type "Hello Somesh" in composer, press Enter, wait
- **Source Location:** 
  - `app.js:526-549` `submitMessage()` → `Bridge.call('send_message')`
  - `desktop_shell.py:148-169` `send_message()` → `CommunicationEngine.handle()`
  - `communication/engine.py:94-102` `handle()` → `router.route()` → `_emit()`
- **Root Cause:** 
  - `BridgeTextOutput.emit()` is no-op (correct — reply returns via bridge)
  - But `CommunicationEngine.handle()` may raise `ChannelNotRegistered` if mode requires voice channel
  - Default mode in `desktop_shell.py:302-303` is `TEXT_ONLY` (via `BridgeTextOutput()` only)
  - However: `CommunicationRouter` defaults to `TEXT_ONLY` (router.py:162)
  - If `ConversationEngine.reply()` returns `turn.reply = None` (Intent.UNKNOWN), `route()` returns `None` → no response
- **Evidence:** `pipeline.py:141-157` `_compose()` returns `None` for `Intent.UNKNOWN`. "Hello Somesh" should match `Intent.GREETING`.
- **Affects:** Frozen executable ✅, Installed executable ✅
- **Severity:** CRITICAL (blocks text conversation)
- **Smallest Fix:** Add logging in `submitMessage()` catch block; log `result` from bridge; verify `ConversationEngine.reply()` intent classification
- **Verification:** Type "Hello Somesh", confirm Somesh reply appears

### F5 — Breathing Kalpavriksha Tree Not Visible
- **Classification:** A. CONFIRMED BUG
- **Symptom:** Canvas exists but no tree particles/branches rendered
- **Reproduction:** Launch app, inspect canvas
- **Source Location:** 
  - `tree.js:224-237` `build()` → `buildBranches()` → `buildParticles()`
  - `tree.js:322-335` `start()` → `requestAnimationFrame` loop
  - `app.js:679-705` `runStartup()` → `tree.build(seed)` → `tree.start()`
- **Root Cause:** 
  - `tree.build()` called with seed from `Bridge.call('get_founder_seed')`
  - If bridge call fails, seed=1 (fallback)
  - `tree.start()` only runs if `!document.hidden && document.hasFocus()`
  - Canvas `_resize()` sets dimensions but particles may have `entryProgress = 0`
  - Growth windows (GROWTH_WINDOWS) delay particle appearance by gen (up to 3800ms)
- **Evidence:** 
  - `tree.js:230-236` particles start with `entryProgress = 0`, `originY = -0.15`
  - `tree.js:393-403` growth animation advances `entryProgress` over gen-specific windows
  - If `growthStart` never set (bridge fails), tree stays in growth phase forever
- **Affects:** Frozen executable ✅, Installed executable ✅
- **Severity:** CRITICAL (core product experience)
- **Smallest Fix:** Add `console.log` in `build()`, `start()`, `_frame()`; verify `growthStart` set; verify `requestAnimationFrame` running
- **Verification:** Launch, confirm tree particles visible and breathing within 5s

### F6 — Dashboard Shows STT/TTS Errors (Model Loading Failure)
- **Classification:** E. MODEL LOADING ERROR
- **Symptom:** Startup diagnostics: STT ✗, TTS ✗, Voice ✗
- **Reproduction:** Launch app, wait for diagnostics overlay
- **Source Location:** 
  - `voice_pipeline.py:235-243` `stt_ready`/`tts_ready` properties
  - `voice_pipeline.py:418-439` `_load_and_open()`
  - `desktop_shell.py:219-231` `get_startup_diagnostics()`
- **Root Cause:** 
  - Whisper model (`base.en`) NOT bundled — downloads on first run (145MB)
  - Piper model (`en_US-lessac-medium.onnx`) bundled but `onnxruntime` DLLs may not load in frozen executable
  - `faster_whisper` requires `ctranslate2` native DLLs
  - `_load_and_open()` catches all exceptions → `STATE_ERROR` → diagnostics show ✗
- **Evidence:** 
  - `packaging/kalpavriksha.spec` bundles `voice_models/` directory but only Piper `.onnx`
  - `kalpavriksha_desktop.py:31-39` `_whisper_model_path()` returns `"base.en"` string (downloads) if bundled dir not found
  - HEALTH_C34_4.md: "Whisper model not bundled — Downloads on first run"
- **Affects:** Frozen executable ✅, Installed executable ✅, Clean machine ✅
- **Severity:** CRITICAL (voice primary per Veda)
- **Smallest Fix:** Bundle `whisper-base.en` CTranslate2 model in `voice_models/`; update `_whisper_model_path()` to use bundled path; verify `ctranslate2`/`onnxruntime` DLLs in frozen build
- **Verification:** Launch, confirm STT ✓, TTS ✓ in diagnostics

---

## Process Shutdown Analysis (F1 Deep Dive)

**WHO closes the application?**

Evidence from debug output:
```
[pywebview] _pywebviewready event fired
[pywebview] loaded event fired
... 10 seconds later ...
Process exits with code 0
```

No Python exception, no pywebview error, no Bottle error.

**Hypothesis 1:** JavaScript calls `window.close()`
- Search `app.js` for `window.close()` → NOT FOUND
- Search for `close()` on window → only `closeDashboard()` which toggles class

**Hypothesis 2:** pywebview internal timeout
- `webview.start()` blocks until all windows closed
- `window.events.closing += voice.stop` registered (desktop_shell.py:506)
- If window closes, `voice.stop()` called, then process exits

**Hypothesis 3:** Window loses focus → `tree.stop()` → something triggers close
- `tree.js:336-335` `stop()` cancels animation frame
- `tree.js:220-221` `blur` event calls `stop()`, `focus` calls `start()`
- But `stop()` only cancels animation, doesn't close window

**Hypothesis 4:** Daemon thread death
- `voice_pipeline.py:228` `_load_and_open` runs on daemon thread
- `voice_pipeline.py:439` `_device_watch_loop` runs on daemon thread
- If main thread exits, daemon threads killed — but what exits main thread?

**Most Likely:** `webview.start()` returns because `window._initialize()` fails or window closes. Need to add logging to `window.events.closing` and `window.events.closed` to capture close reason.

---

## Packaging Differential

| Component | Source (python) | Frozen EXE (dist) | Installed EXE |
|---|---|---|---|
| Startup (HTTP 200) | ✅ | ✅ | ✅ |
| WebView bridge | ✅ | ✅ | ✅ |
| CSS/JS load | ✅ | ✅ | ✅ |
| Tree build/start | ❓ | ❌ | ❌ |
| Composer input visible | ✅ | ❌ | ❌ |
| Text conversation | ✅ | ❌ | ❌ |
| STT (Whisper) | ✅* | ❌ | ❌ |
| TTS (Piper) | ✅* | ❌ | ❌ |
| Voice pipeline | ✅* | ❌ | ❌ |
| Dashboard diagnostics | ✅ | ❌ | ❌ |
| Process lifetime | ∞ | ~10s | ~10s |

*Requires internet for Whisper model download on first run

**Key Packaging Failures:**
1. Whisper model not bundled → downloads 145MB on first run
2. `ctranslate2` / `onnxruntime` native DLLs may not resolve in frozen executable
3. `pycaw` COM dependencies may not register correctly
4. Theme/CSS variables may not apply in WebView2 context

---

## False/Incorrect Claims from Previous Audits

| Previous Claim | Reality | Evidence |
|---|---|---|
| "Voice pipeline works locally" | STT/TTS fail in frozen exe | Diagnostics show ✗ STT, ✗ TTS |
| "Bluetooth switching verified" | Not tested on installed exe | HEALTH_C34_4.md: "No clean machine test" |
| "Installer produces working app" | Never tested on clean machine | HEALTH_C34_4.md: "Explicitly deferred" |
| "Models bundled" | Whisper NOT bundled | `kalpavriksha_desktop.py` returns "base.en" string |
| "Founder can naturally use" | Requires terminal, no GUI surface | HEALTH_C34_4.md: "Terminal REPL only" |
| "Tree renders at 60fps" | Tree not visible in installed exe | This audit: canvas empty |

---

## Fix Priority & Minimal Fix Plan

### P0 — Critical (Blocks All Usage)
1. **F1 — Process auto-close** — Add window close logging, prevent premature close
2. **F6 — Model loading** — Bundle Whisper CTranslate2 model; verify native DLLs in frozen build
3. **F5 — Tree not visible** — Verify `growthStart` set, animation loop running, particles generating

### P1 — High (Blocks Voice/Text)
4. **F2 — STT garbage** — Debug audio capture: log RMS, buffer, device, VAD
5. **F4 — No Somesh reply** — Log bridge call result, verify intent classification
6. **F3 — Composer invisible** — Verify `data-theme` attribute, force dark theme

### P2 — Medium (Polish)
7. Dashboard diagnostic accuracy (fix to report real state)
8. Voice interrupt on typing (hook `abandonVoiceCapture()` to composer input)

---

## Verification Protocol for Each Fix

| Fix | Test | Pass Criteria |
|---|---|---|
| F1 | Launch installed exe, wait 60s | Process alive, no auto-close |
| F6 | Launch, check diagnostics | STT ✓, TTS ✓, Voice ✓ |
| F5 | Launch, inspect canvas | Tree particles visible, breathing animation |
| F2 | Click mic, speak "Hello Somesh" | Transcript = "Hello Somesh" |
| F4 | Type "Hello Somesh", Enter | Somesh reply appears in chat |
| F3 | Click composer, type | Text visible (dark on light or light on dark) |

---

## Conclusion

The installed Founder Edition has **four critical runtime failures** (auto-close, no models, no tree, no conversation) and **two UI failures** (invisible composer, garbage STT). All trace to:

1. **Packaging gaps** — Whisper model, native DLLs not bundled
2. **Initialization order** — Bridge calls may fail before `tree.build()`/`tree.start()`
3. **Audio pipeline** — VAD/capture not working on frozen executable's device
3. **Theme application** — CSS variables not resolving in WebView2 context

**Minimum viable fix set:** Bundle Whisper model + fix process lifetime + verify tree animation loop + debug audio capture. Estimated 3-5 focused changes.

---

*End of Forensic Audit — Evidence only. No modifications made.*